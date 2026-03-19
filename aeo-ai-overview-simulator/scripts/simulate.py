#!/usr/bin/env python3
"""
AI Overview Simulator — Simulate Google AI Overviews by running prompts through
Gemini 3 Flash with Google Search grounding.

Usage:
    python3 simulate.py "prompt" [--domain example.com] [--runs 20] [--model gemini-3-flash-preview] [--concurrency 5] [--output text|json]

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
from urllib.parse import urlparse


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


def extract_response_text(response: dict) -> str:
    """Extract the text content from a Gemini response."""
    texts = []
    for cand in response.get("candidates", []):
        content = cand.get("content", {})
        for part in content.get("parts", []):
            if "text" in part:
                texts.append(part["text"])
    return "\n".join(texts)


def extract_queries(response: dict) -> list:
    """Extract web search queries from Gemini grounding metadata."""
    queries = []
    for cand in response.get("candidates", []):
        meta = cand.get("groundingMetadata", {})
        queries.extend(meta.get("webSearchQueries", []))
    return queries


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


def extract_grounding_supports(response: dict) -> list:
    """Extract grounding support segments — which parts of the response are grounded."""
    supports = []
    for cand in response.get("candidates", []):
        meta = cand.get("groundingMetadata", {})
        for support in meta.get("groundingSupports", []):
            segment = support.get("segment", {})
            chunk_indices = [
                idx.get("groundingChunkIndex", 0)
                for idx in support.get("groundingChunkIndices", [])
            ]
            supports.append({
                "text": segment.get("text", ""),
                "start": segment.get("startIndex", 0),
                "end": segment.get("endIndex", 0),
                "chunk_indices": chunk_indices,
            })
    return supports


def get_domain(uri: str) -> str:
    """Extract domain from a URI."""
    try:
        parsed = urlparse(uri)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def check_domain_mention(text: str, domain: str) -> list:
    """Check if a domain/brand is mentioned in text. Returns matching excerpts."""
    excerpts = []
    # Strip TLD for brand name matching (e.g., "monday.com" -> also search "monday")
    brand = domain.split(".")[0] if "." in domain else domain
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        if domain.lower() in sentence.lower() or brand.lower() in sentence.lower():
            excerpts.append(sentence.strip())
    return excerpts


def normalize_sentence(s: str) -> str:
    """Normalize a sentence for comparison: lowercase, strip punctuation, collapse whitespace."""
    s = s.lower()
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def tokenize_words(s: str) -> set:
    """Extract word set from normalized text."""
    return set(s.split())


def sentences_similar(a: str, b: str, threshold: float = 0.8) -> bool:
    """Check if two sentences are similar (>80% word overlap)."""
    a_norm = normalize_sentence(a)
    b_norm = normalize_sentence(b)
    if a_norm == b_norm:
        return True
    words_a = tokenize_words(a_norm)
    words_b = tokenize_words(b_norm)
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b)
    max_len = max(len(words_a), len(words_b))
    return (overlap / max_len) >= threshold


def analyze_response_diff(run_results: list) -> dict:
    """Analyze response text stability across runs.

    Groups similar sentences and classifies them by frequency:
    - Stable (>80%): always included
    - Common (40-80%): usually included
    - Volatile (10-40%): sometimes mentioned
    - Rare (<10%): edge case mentions
    """
    successful_runs = len(run_results)
    if successful_runs == 0:
        return {}

    # Split each response into sentences
    all_run_sentences = []
    for run in run_results:
        text = run.get("text", "")
        # Split on sentence boundaries
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        all_run_sentences.append(sentences)

    # Group similar sentences across runs
    # Each group: {"canonical": str, "count": int, "variants": list}
    sentence_groups = []
    for run_idx, sentences in enumerate(all_run_sentences):
        for sentence in sentences:
            if len(sentence) < 10:  # skip tiny fragments
                continue
            # Try to match to an existing group
            matched = False
            for group in sentence_groups:
                if sentences_similar(sentence, group["canonical"]):
                    if run_idx not in group["run_indices"]:
                        group["count"] += 1
                        group["run_indices"].add(run_idx)
                    if sentence != group["canonical"] and sentence not in group["variants"]:
                        group["variants"].append(sentence)
                    matched = True
                    break
            if not matched:
                sentence_groups.append({
                    "canonical": sentence,
                    "count": 1,
                    "run_indices": {run_idx},
                    "variants": [],
                })

    # Classify by frequency
    stable = []  # >80%
    common = []  # 40-80%
    volatile = []  # 10-40%
    rare = []  # <10%

    for group in sentence_groups:
        freq = round(group["count"] / successful_runs * 100)
        entry = {
            "sentence": group["canonical"],
            "frequency": freq,
            "count": group["count"],
        }
        if freq > 80:
            stable.append(entry)
        elif freq >= 40:
            common.append(entry)
        elif freq >= 10:
            volatile.append(entry)
        else:
            rare.append(entry)

    # Sort each category by frequency desc
    for lst in [stable, common, volatile, rare]:
        lst.sort(key=lambda x: -x["frequency"])

    # Entity frequency — extract capitalized multi-word names and domains
    entity_counts = defaultdict(int)
    entity_run_presence = defaultdict(set)
    entity_pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b')
    domain_pattern = re.compile(r'\b([a-zA-Z0-9][-a-zA-Z0-9]*\.(?:com|org|net|io|ai|co|dev))\b')

    for run_idx, run in enumerate(run_results):
        text = run.get("text", "")
        # Named entities
        for match in entity_pattern.finditer(text):
            name = match.group(1)
            if len(name) > 2:  # skip short matches
                entity_counts[name] += 1
                entity_run_presence[name].add(run_idx)
        # Domains
        for match in domain_pattern.finditer(text):
            domain = match.group(1).lower()
            entity_counts[domain] += 1
            entity_run_presence[domain].add(run_idx)

    entity_frequency = []
    for entity, count in sorted(entity_counts.items(), key=lambda x: -x[1]):
        run_count = len(entity_run_presence[entity])
        freq = round(run_count / successful_runs * 100)
        if freq < 100:  # skip entities that appear in every run (likely generic words)
            entity_frequency.append({
                "entity": entity,
                "frequency": freq,
                "run_count": run_count,
            })

    # Keep top 20 volatile entities (not in every run)
    volatile_entities = [e for e in entity_frequency if e["frequency"] < 80][:20]

    return {
        "stable_sentences": stable[:15],
        "common_sentences": common[:15],
        "volatile_sentences": volatile[:15],
        "rare_sentences": rare[:10],
        "entity_frequency": volatile_entities,
    }


def run_simulation(prompt: str, runs: int, model: str, concurrency: int, domain: str = None, diff: bool = False):
    """Run prompt N times and collect AI Overview simulation data."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)

    run_results = []
    errors = 0

    print(f"Simulating AI Overview for: \"{prompt}\"", file=sys.stderr)
    print(f"Model: {model} | Runs: {runs} | Concurrency: {concurrency}", file=sys.stderr)
    if domain:
        print(f"Tracking domain: {domain}", file=sys.stderr)
    print(file=sys.stderr)

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
                text = extract_response_text(resp)
                queries = extract_queries(resp)
                sources = extract_sources(resp)
                supports = extract_grounding_supports(resp)
                run_results.append({
                    "run": run_idx + 1,
                    "text": text,
                    "queries": queries,
                    "sources": sources,
                    "supports": supports,
                })
                print(f"  Run {run_idx + 1}: {len(sources)} sources, {len(queries)} queries", file=sys.stderr)
            except Exception as e:
                errors += 1
                print(f"  Run {run_idx + 1}: EXCEPTION - {e}", file=sys.stderr)

    successful_runs = len(run_results)

    # Aggregate source citation frequency (by domain)
    domain_cite_count = defaultdict(int)
    url_cite_count = defaultdict(int)
    domain_urls = defaultdict(set)
    for run in run_results:
        seen_domains = set()
        for source in run["sources"]:
            d = get_domain(source["uri"])
            url_cite_count[source["uri"]] += 1
            domain_urls[d].add(source["uri"])
            if d not in seen_domains:
                domain_cite_count[d] += 1
                seen_domains.add(d)

    sorted_domains = sorted(domain_cite_count.items(), key=lambda x: (-x[1], x[0]))

    # Aggregate search query frequency
    query_run_count = defaultdict(int)
    for run in run_results:
        seen_in_run = set()
        for q in run["queries"]:
            ql = q.strip().lower()
            if ql not in seen_in_run:
                query_run_count[ql] += 1
                seen_in_run.add(ql)
    sorted_queries = sorted(query_run_count.items(), key=lambda x: (-x[1], x[0]))

    # Domain tracking
    domain_tracking = None
    if domain and successful_runs > 0:
        target_domain = domain.lower()
        if target_domain.startswith("www."):
            target_domain = target_domain[4:]

        mention_count = 0
        citation_count = 0
        all_excerpts = []
        cited_urls_count = defaultdict(int)

        for run in run_results:
            # Check mentions in text
            excerpts = check_domain_mention(run["text"], target_domain)
            if excerpts:
                mention_count += 1
                all_excerpts.extend(excerpts)

            # Check citations in sources
            cited_in_run = False
            for source in run["sources"]:
                if target_domain in get_domain(source["uri"]):
                    cited_in_run = True
                    cited_urls_count[source["uri"]] += 1
            if cited_in_run:
                citation_count += 1

        # Deduplicate excerpts
        unique_excerpts = list(dict.fromkeys(all_excerpts))[:10]

        domain_tracking = {
            "domain": domain,
            "mention_rate": round(mention_count / successful_runs * 100),
            "mention_count": mention_count,
            "citation_rate": round(citation_count / successful_runs * 100),
            "citation_count": citation_count,
            "cited_urls": [
                {"url": url, "count": count}
                for url, count in sorted(cited_urls_count.items(), key=lambda x: -x[1])
            ],
            "excerpts": unique_excerpts,
        }

    # Response diff analysis (if enabled)
    response_analysis = None
    if diff and run_results:
        print(f"\nAnalyzing response stability...", file=sys.stderr)
        response_analysis = analyze_response_diff(run_results)

    result = {
        "prompt": prompt,
        "model": model,
        "total_runs": runs,
        "successful_runs": successful_runs,
        "errors": errors,
        "sources": [
            {
                "domain": d,
                "citation_rate": round(c / successful_runs * 100) if successful_runs else 0,
                "count": c,
                "urls": sorted(domain_urls.get(d, set())),
            }
            for d, c in sorted_domains
        ],
        "queries": [
            {
                "query": q,
                "frequency": round(c / successful_runs * 100) if successful_runs else 0,
                "count": c,
            }
            for q, c in sorted_queries
        ],
        "domain_tracking": domain_tracking,
        "response_analysis": response_analysis,
    }

    return result


def format_text(result: dict) -> str:
    lines = []
    lines.append(f"AI Overview Simulation: \"{result['prompt']}\"")
    lines.append(f"Model: {result['model']}")
    lines.append(f"Runs: {result['successful_runs']}/{result['total_runs']} successful")
    lines.append("")

    # Top cited sources
    lines.append("Top Cited Sources:")
    lines.append("=" * 60)
    for s in result["sources"][:20]:
        lines.append(f"  {s['citation_rate']}% ({s['count']}/{result['successful_runs']}) — {s['domain']}")
        for url in s["urls"][:3]:
            lines.append(f"      {url}")

    # Search queries
    if result["queries"]:
        lines.append("")
        lines.append("Search Queries Used:")
        lines.append("=" * 60)
        for q in result["queries"][:15]:
            lines.append(f"  {q['frequency']}% ({q['count']}/{result['successful_runs']}) — {q['query']}")

    # Domain tracking
    dt = result.get("domain_tracking")
    if dt:
        lines.append("")
        lines.append(f"Domain Tracking: {dt['domain']}")
        lines.append("=" * 60)
        lines.append(f"  Mention rate: {dt['mention_rate']}% ({dt['mention_count']}/{result['successful_runs']} runs)")
        lines.append(f"  Citation rate: {dt['citation_rate']}% ({dt['citation_count']}/{result['successful_runs']} runs)")
        if dt["cited_urls"]:
            lines.append("  Cited URLs:")
            for u in dt["cited_urls"]:
                lines.append(f"    {u['count']}x — {u['url']}")
        if dt["excerpts"]:
            lines.append("  Excerpts:")
            for ex in dt["excerpts"][:5]:
                lines.append(f"    - \"{ex}\"")

    # Response stability analysis
    ra = result.get("response_analysis")
    if ra:
        lines.append("")
        lines.append("Response Stability Analysis:")
        lines.append("=" * 60)

        if ra.get("stable_sentences"):
            lines.append("")
            lines.append("Stable (>80% of runs — core of the AI Overview, hard to displace):")
            for s in ra["stable_sentences"][:10]:
                lines.append(f"  [{s['frequency']}%] {s['sentence'][:120]}{'...' if len(s['sentence']) > 120 else ''}")

        if ra.get("common_sentences"):
            lines.append("")
            lines.append("Common (40-80% — usually included):")
            for s in ra["common_sentences"][:8]:
                lines.append(f"  [{s['frequency']}%] {s['sentence'][:120]}{'...' if len(s['sentence']) > 120 else ''}")

        if ra.get("volatile_sentences"):
            lines.append("")
            lines.append("Volatile (10-40% — insertion points, your content can influence these):")
            for s in ra["volatile_sentences"][:8]:
                lines.append(f"  [{s['frequency']}%] {s['sentence'][:120]}{'...' if len(s['sentence']) > 120 else ''}")

        if ra.get("entity_frequency"):
            lines.append("")
            lines.append("Entity Volatility (brands/entities that appear inconsistently — competitive slots):")
            for e in ra["entity_frequency"][:10]:
                lines.append(f"  [{e['frequency']}%] {e['entity']} ({e['run_count']}/{result['successful_runs']} runs)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Simulate Google AI Overviews using Gemini 3 Flash with Google Search grounding"
    )
    parser.add_argument("prompt", help="The query/prompt to simulate")
    parser.add_argument("--domain", help="Domain to track (e.g., example.com)")
    parser.add_argument("--runs", type=int, default=20, help="Number of simulation runs (default: 20)")
    parser.add_argument("--model", default="gemini-3-flash-preview",
                        help="Gemini model (default: gemini-3-flash-preview)")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="Max concurrent requests (default: 5)")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--diff", action="store_true",
                        help="Enable response text diffing — analyze sentence stability across runs")
    args = parser.parse_args()

    result = run_simulation(args.prompt, args.runs, args.model, args.concurrency, args.domain, args.diff)

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
