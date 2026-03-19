#!/usr/bin/env python3
"""
Source Authority Profiler — Analyze WHY certain sources get cited by Gemini.
Fetches top-cited pages and profiles them (word count, schema, freshness, entities)
to build a "citation blueprint."

Usage:
    python3 profile.py "prompt" [--domain example.com] [--runs 20] [--model gemini-3-flash-preview] [--top 10] [--concurrency 5] [--output text|json]

Requires: GEMINI_API_KEY env var
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.parse import urlparse


# ── Gemini API ──────────────────────────────────────────────────────────────

def call_gemini(prompt: str, api_key: str, model: str) -> dict:
    """Call Gemini API with Google Search grounding. Returns parsed JSON response."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                wait = (2 ** attempt) + 1
                print(f"    Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            elif attempt < 4:
                time.sleep(2 ** attempt)
            else:
                return {"error": f"HTTP {e.code}: {e.reason}"}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < 4:
                time.sleep(2 ** attempt)
            else:
                return {"error": str(e)}


def extract_sources(response: dict) -> list:
    """Extract grounding source URLs and titles from Gemini response."""
    sources = []
    seen = set()
    for cand in response.get("candidates", []):
        meta = cand.get("groundingMetadata", {})
        for chunk in meta.get("groundingChunks", []):
            web = chunk.get("web", {})
            uri = web.get("uri", "")
            title = web.get("title", "")
            if uri and uri not in seen:
                seen.add(uri)
                sources.append({"title": title, "uri": uri})
    return sources


def get_domain(uri: str) -> str:
    """Extract clean domain from URI."""
    try:
        parsed = urlparse(uri)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


# ── HTML Page Analysis ──────────────────────────────────────────────────────

class PageAnalyzer(HTMLParser):
    """Parse HTML and extract structured page profile data."""

    def __init__(self):
        super().__init__()
        self.headings = {"h1": [], "h2": [], "h3": []}
        self.json_ld_blocks = []
        self.meta_dates = {}
        self._current_tag = None
        self._current_data = []
        self._in_heading = False
        self._in_script = False
        self._script_type = None
        self._script_data = []
        self._all_text = []
        self._in_body = False
        self._skip_tags = {"script", "style", "noscript"}
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attrs_dict = dict(attrs)

        if tag_lower == "body":
            self._in_body = True

        if tag_lower in self._skip_tags and tag_lower != "script":
            self._skip_depth += 1

        if tag_lower in ("h1", "h2", "h3"):
            self._in_heading = True
            self._current_tag = tag_lower
            self._current_data = []

        if tag_lower == "script":
            self._in_script = True
            self._script_type = attrs_dict.get("type", "")
            self._script_data = []

        if tag_lower == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")
            date_names = [
                "date", "publish_date", "article:published_time",
                "article:modified_time", "datePublished", "dateModified",
                "last-modified", "pubdate", "dc.date", "sailthru.date",
            ]
            for dn in date_names:
                if dn in name or dn in prop:
                    self.meta_dates[dn] = content
                    break

    def handle_endtag(self, tag):
        tag_lower = tag.lower()

        if tag_lower in self._skip_tags and tag_lower != "script":
            self._skip_depth = max(0, self._skip_depth - 1)

        if tag_lower in ("h1", "h2", "h3") and self._in_heading:
            text = "".join(self._current_data).strip()
            if text:
                self.headings[tag_lower].append(text)
            self._in_heading = False
            self._current_tag = None

        if tag_lower == "script" and self._in_script:
            if "ld+json" in self._script_type:
                raw = "".join(self._script_data).strip()
                if raw:
                    try:
                        self.json_ld_blocks.append(json.loads(raw))
                    except json.JSONDecodeError:
                        pass
            self._in_script = False
            self._script_type = None

    def handle_data(self, data):
        if self._in_heading:
            self._current_data.append(data)
        if self._in_script:
            self._script_data.append(data)
        if self._in_body and self._skip_depth == 0 and not self._in_script:
            self._all_text.append(data)

    def get_word_count(self) -> int:
        text = " ".join(self._all_text)
        words = text.split()
        return len(words)

    def get_json_ld_types(self) -> list:
        types = []
        for block in self.json_ld_blocks:
            if isinstance(block, dict):
                t = block.get("@type", "")
                if isinstance(t, list):
                    types.extend(t)
                elif t:
                    types.append(t)
                # Check @graph
                for item in block.get("@graph", []):
                    if isinstance(item, dict):
                        gt = item.get("@type", "")
                        if isinstance(gt, list):
                            types.extend(gt)
                        elif gt:
                            types.append(gt)
        return list(set(types))


def fetch_page(url: str, timeout: int = 10) -> str:
    """Fetch a page's HTML content. Returns empty string on failure."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AEO-Profiler/1.0",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            # Try UTF-8 first, then latin-1 as fallback
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("latin-1", errors="replace")
    except Exception:
        return ""


def count_entities(text: str) -> int:
    """Count specific entities: proper nouns, numbers/stats, quoted terms."""
    count = 0
    # Capitalized multi-word sequences (proper nouns / brand names)
    count += len(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', text))
    # Numbers with context (percentages, dollar amounts, large numbers)
    count += len(re.findall(r'\b\d[\d,]*\.?\d*\s*[%$€£]|\$[\d,]+\.?\d*|\b\d{2,}[\d,]*\b', text))
    # Quoted terms
    count += len(re.findall(r'"[^"]{2,50}"', text))
    return count


def analyze_page(url: str) -> dict:
    """Fetch and analyze a single page. Returns profile dict."""
    html = fetch_page(url)
    if not html:
        return {"url": url, "domain": get_domain(url), "error": "fetch_failed"}

    analyzer = PageAnalyzer()
    try:
        analyzer.feed(html)
    except Exception:
        return {"url": url, "domain": get_domain(url), "error": "parse_failed"}

    word_count = analyzer.get_word_count()
    h1_count = len(analyzer.headings["h1"])
    h2_count = len(analyzer.headings["h2"])
    h3_count = len(analyzer.headings["h3"])
    json_ld_types = analyzer.get_json_ld_types()
    has_structured_data = len(json_ld_types) > 0
    dates = analyzer.meta_dates

    # Count entities in visible text
    visible_text = " ".join(analyzer._all_text)
    entity_count = count_entities(visible_text)

    # Extract publication date (best guess)
    pub_date = None
    for key in ["article:published_time", "publish_date", "datePublished", "pubdate", "date", "dc.date"]:
        if key in dates:
            pub_date = dates[key]
            break

    mod_date = None
    for key in ["article:modified_time", "dateModified", "last-modified"]:
        if key in dates:
            mod_date = dates[key]
            break

    return {
        "url": url,
        "domain": get_domain(url),
        "word_count": word_count,
        "headings": {
            "h1": h1_count,
            "h2": h2_count,
            "h3": h3_count,
            "total": h1_count + h2_count + h3_count,
        },
        "structured_data": {
            "has_json_ld": has_structured_data,
            "types": json_ld_types,
        },
        "dates": {
            "published": pub_date,
            "modified": mod_date,
        },
        "entity_count": entity_count,
        "h1_texts": analyzer.headings["h1"][:3],
    }


# ── Main Logic ──────────────────────────────────────────────────────────────

def run_profiler(prompt: str, runs: int, model: str, concurrency: int,
                 top: int, domain: str = None):
    """Run prompt N times, collect sources, profile top pages."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)

    print(f"Source Authority Profiler: \"{prompt}\"", file=sys.stderr)
    print(f"Model: {model} | Runs: {runs} | Top: {top}", file=sys.stderr)
    if domain:
        print(f"Highlight domain: {domain}", file=sys.stderr)
    print(file=sys.stderr)

    # Phase 1: Run prompt and collect citations
    print("Phase 1: Collecting citations...", file=sys.stderr)
    url_cite_count = defaultdict(int)
    url_titles = {}
    errors = 0
    successful_runs = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(call_gemini, prompt, api_key, model): i for i in range(runs)}
        for future in as_completed(futures):
            run_idx = futures[future]
            try:
                resp = future.result()
                if "error" in resp:
                    errors += 1
                    print(f"  Run {run_idx + 1}: ERROR - {resp['error']}", file=sys.stderr)
                    continue
                sources = extract_sources(resp)
                successful_runs += 1
                for src in sources:
                    url_cite_count[src["uri"]] += 1
                    if src["uri"] not in url_titles and src["title"]:
                        url_titles[src["uri"]] = src["title"]
                print(f"  Run {run_idx + 1}: {len(sources)} sources", file=sys.stderr)
            except Exception as e:
                errors += 1
                print(f"  Run {run_idx + 1}: EXCEPTION - {e}", file=sys.stderr)

    if successful_runs == 0:
        print("Error: No successful runs", file=sys.stderr)
        sys.exit(1)

    # Rank URLs by citation frequency
    sorted_urls = sorted(url_cite_count.items(), key=lambda x: -x[1])
    top_urls = sorted_urls[:top]

    print(f"\nPhase 1 complete: {successful_runs}/{runs} runs, {len(url_cite_count)} unique URLs", file=sys.stderr)

    # Phase 2: Fetch and profile top pages
    print(f"\nPhase 2: Profiling top {min(top, len(top_urls))} pages...", file=sys.stderr)
    profiles = []

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        future_map = {}
        for url, count in top_urls:
            f = pool.submit(analyze_page, url)
            future_map[f] = (url, count)

        for future in as_completed(future_map):
            url, count = future_map[future]
            try:
                profile = future.result()
                profile["citation_count"] = count
                profile["citation_rate"] = round(count / successful_runs * 100)
                profile["title"] = url_titles.get(url, "")
                profiles.append(profile)
                status = "OK" if "error" not in profile else profile["error"]
                print(f"  {get_domain(url)}: {status}", file=sys.stderr)
            except Exception as e:
                print(f"  {get_domain(url)}: EXCEPTION - {e}", file=sys.stderr)

    # Sort profiles by citation rate
    profiles.sort(key=lambda x: -x.get("citation_rate", 0))

    # Phase 3: Build citation blueprint
    print(f"\nPhase 3: Building citation blueprint...", file=sys.stderr)
    successful_profiles = [p for p in profiles if "error" not in p]
    blueprint = build_blueprint(successful_profiles)

    # Phase 4: Domain analysis (if provided)
    domain_analysis = None
    if domain:
        target = domain.lower()
        if target.startswith("www."):
            target = target[4:]

        domain_profiles = [p for p in profiles if target in p.get("domain", "")]
        non_domain = [p for p in successful_profiles if target not in p.get("domain", "")]

        domain_analysis = {
            "domain": domain,
            "pages_in_top": len(domain_profiles),
            "pages": domain_profiles,
            "vs_blueprint": compare_to_blueprint(domain_profiles, blueprint) if domain_profiles else None,
        }

    result = {
        "prompt": prompt,
        "model": model,
        "total_runs": runs,
        "successful_runs": successful_runs,
        "errors": errors,
        "total_unique_urls": len(url_cite_count),
        "profiles": profiles,
        "blueprint": blueprint,
        "domain_analysis": domain_analysis,
    }

    return result


def build_blueprint(profiles: list) -> dict:
    """Build a citation blueprint from successfully profiled pages."""
    if not profiles:
        return {"note": "No pages could be profiled"}

    word_counts = [p["word_count"] for p in profiles]
    heading_totals = [p["headings"]["total"] for p in profiles]
    entity_counts = [p["entity_count"] for p in profiles]
    has_schema = [1 for p in profiles if p["structured_data"]["has_json_ld"]]
    all_schema_types = []
    for p in profiles:
        all_schema_types.extend(p["structured_data"]["types"])

    # Count schema types
    schema_type_counts = defaultdict(int)
    for t in all_schema_types:
        schema_type_counts[t] += 1

    # Domain diversity
    domains = [p["domain"] for p in profiles]
    unique_domains = len(set(domains))

    n = len(profiles)

    return {
        "sample_size": n,
        "word_count": {
            "avg": round(sum(word_counts) / n) if n else 0,
            "min": min(word_counts) if word_counts else 0,
            "max": max(word_counts) if word_counts else 0,
            "median": sorted(word_counts)[n // 2] if word_counts else 0,
        },
        "headings": {
            "avg_total": round(sum(heading_totals) / n) if n else 0,
            "min": min(heading_totals) if heading_totals else 0,
            "max": max(heading_totals) if heading_totals else 0,
        },
        "structured_data": {
            "pages_with_json_ld": len(has_schema),
            "pct_with_json_ld": round(len(has_schema) / n * 100) if n else 0,
            "common_types": sorted(schema_type_counts.items(), key=lambda x: -x[1]),
        },
        "entities": {
            "avg_count": round(sum(entity_counts) / n) if n else 0,
            "min": min(entity_counts) if entity_counts else 0,
            "max": max(entity_counts) if entity_counts else 0,
        },
        "domain_diversity": unique_domains,
        "dates": {
            "pages_with_pub_date": sum(1 for p in profiles if p["dates"]["published"]),
            "pages_with_mod_date": sum(1 for p in profiles if p["dates"]["modified"]),
        },
    }


def compare_to_blueprint(domain_profiles: list, blueprint: dict) -> dict:
    """Compare domain pages to the citation blueprint."""
    comparisons = []
    for p in domain_profiles:
        if "error" in p:
            comparisons.append({"url": p["url"], "error": p["error"]})
            continue

        bp_avg_wc = blueprint.get("word_count", {}).get("avg", 0)
        bp_avg_headings = blueprint.get("headings", {}).get("avg_total", 0)
        bp_avg_entities = blueprint.get("entities", {}).get("avg_count", 0)
        bp_schema_pct = blueprint.get("structured_data", {}).get("pct_with_json_ld", 0)

        comparisons.append({
            "url": p["url"],
            "word_count": p["word_count"],
            "word_count_vs_avg": p["word_count"] - bp_avg_wc,
            "headings_total": p["headings"]["total"],
            "headings_vs_avg": p["headings"]["total"] - bp_avg_headings,
            "has_schema": p["structured_data"]["has_json_ld"],
            "entity_count": p["entity_count"],
            "entities_vs_avg": p["entity_count"] - bp_avg_entities,
        })

    return comparisons


def format_text(result: dict) -> str:
    """Format results as human-readable text."""
    lines = []
    lines.append(f"Source Authority Profiler: \"{result['prompt']}\"")
    lines.append(f"Model: {result['model']}")
    lines.append(f"Runs: {result['successful_runs']}/{result['total_runs']} successful")
    lines.append(f"Unique URLs cited: {result['total_unique_urls']}")
    lines.append("")

    # Top cited pages with profiles
    lines.append("TOP CITED PAGES:")
    lines.append("=" * 70)
    for i, p in enumerate(result["profiles"], 1):
        lines.append(f"\n  #{i} — {p.get('citation_rate', 0)}% ({p.get('citation_count', 0)}/{result['successful_runs']} runs)")
        lines.append(f"  URL: {p['url']}")
        if p.get("title"):
            lines.append(f"  Title: {p['title']}")
        lines.append(f"  Domain: {p['domain']}")

        if "error" in p:
            lines.append(f"  ⚠ Could not fetch page: {p['error']}")
            continue

        lines.append(f"  Word count: {p['word_count']:,}")
        h = p["headings"]
        lines.append(f"  Headings: {h['total']} total (H1:{h['h1']}, H2:{h['h2']}, H3:{h['h3']})")
        sd = p["structured_data"]
        if sd["has_json_ld"]:
            lines.append(f"  Schema: ✓ JSON-LD ({', '.join(sd['types'])})")
        else:
            lines.append(f"  Schema: ✗ No JSON-LD detected")
        dates = p["dates"]
        if dates["published"]:
            lines.append(f"  Published: {dates['published']}")
        if dates["modified"]:
            lines.append(f"  Modified: {dates['modified']}")
        lines.append(f"  Entity density: {p['entity_count']} entities detected")

    # Citation Blueprint
    bp = result["blueprint"]
    lines.append("")
    lines.append("CITATION BLUEPRINT:")
    lines.append("=" * 70)
    lines.append(f"Based on {bp.get('sample_size', 0)} successfully profiled pages")
    lines.append("")

    wc = bp.get("word_count", {})
    lines.append(f"  Word count:        avg {wc.get('avg', 0):,} | "
                 f"median {wc.get('median', 0):,} | "
                 f"range {wc.get('min', 0):,}–{wc.get('max', 0):,}")

    hd = bp.get("headings", {})
    lines.append(f"  Headings:          avg {hd.get('avg_total', 0)} | "
                 f"range {hd.get('min', 0)}–{hd.get('max', 0)}")

    sd = bp.get("structured_data", {})
    lines.append(f"  JSON-LD schema:    {sd.get('pct_with_json_ld', 0)}% of pages ({sd.get('pages_with_json_ld', 0)}/{bp.get('sample_size', 0)})")
    if sd.get("common_types"):
        types_str = ", ".join(f"{t}({c})" for t, c in sd["common_types"][:5])
        lines.append(f"  Schema types:      {types_str}")

    ent = bp.get("entities", {})
    lines.append(f"  Entity density:    avg {ent.get('avg_count', 0)} | "
                 f"range {ent.get('min', 0)}–{ent.get('max', 0)}")

    dt = bp.get("dates", {})
    lines.append(f"  With pub date:     {dt.get('pages_with_pub_date', 0)}/{bp.get('sample_size', 0)}")
    lines.append(f"  With mod date:     {dt.get('pages_with_mod_date', 0)}/{bp.get('sample_size', 0)}")
    lines.append(f"  Domain diversity:  {bp.get('domain_diversity', 0)} unique domains in top results")

    # Domain comparison
    da = result.get("domain_analysis")
    if da:
        lines.append("")
        lines.append(f"DOMAIN ANALYSIS: {da['domain']}")
        lines.append("=" * 70)
        lines.append(f"  Pages in top {len(result['profiles'])}: {da['pages_in_top']}")

        if da["pages_in_top"] == 0:
            lines.append(f"  ⚠ {da['domain']} has NO pages in the top cited sources.")
            lines.append(f"  To get cited, match the blueprint above:")
            lines.append(f"    → Target ~{wc.get('avg', 0):,} words")
            lines.append(f"    → Use ~{hd.get('avg_total', 0)} headings (H1-H3)")
            if sd.get("pct_with_json_ld", 0) > 50:
                lines.append(f"    → Add JSON-LD structured data")
            lines.append(f"    → Include ~{ent.get('avg_count', 0)} specific entities (names, numbers, stats)")
        elif da.get("vs_blueprint"):
            for comp in da["vs_blueprint"]:
                if "error" in comp:
                    continue
                lines.append(f"\n  {comp['url']}")
                wc_diff = comp.get("word_count_vs_avg", 0)
                wc_sym = "+" if wc_diff >= 0 else ""
                lines.append(f"    Word count: {comp['word_count']:,} ({wc_sym}{wc_diff:,} vs avg)")
                h_diff = comp.get("headings_vs_avg", 0)
                h_sym = "+" if h_diff >= 0 else ""
                lines.append(f"    Headings:   {comp['headings_total']} ({h_sym}{h_diff} vs avg)")
                lines.append(f"    Schema:     {'✓' if comp['has_schema'] else '✗'}")
                e_diff = comp.get("entities_vs_avg", 0)
                e_sym = "+" if e_diff >= 0 else ""
                lines.append(f"    Entities:   {comp['entity_count']} ({e_sym}{e_diff} vs avg)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze why certain sources get cited by Gemini — build a citation blueprint"
    )
    parser.add_argument("prompt", help="The query/prompt to analyze")
    parser.add_argument("--domain", help="Domain to highlight (e.g., example.com)")
    parser.add_argument("--runs", type=int, default=20,
                        help="Number of runs (default: 20)")
    parser.add_argument("--model", default="gemini-3-flash-preview",
                        help="Gemini model (default: gemini-3-flash-preview)")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of top URLs to profile (default: 10)")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="Max concurrent requests (default: 5)")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    args = parser.parse_args()

    result = run_profiler(args.prompt, args.runs, args.model, args.concurrency,
                          args.top, args.domain)

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
