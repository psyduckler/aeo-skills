#!/usr/bin/env python3
"""
Citation Gap Finder — Compare what Google AI (Gemini 3 Flash) cites vs what
web search surfaces for the same prompt. Identify cross-platform citation gaps.

Usage:
    python3 find_gaps.py "prompt" --domain example.com [--runs 20] [--model gemini-3-flash-preview] [--output text|json]

Requires: GEMINI_API_KEY env var
Optional: BRAVE_API_KEY env var (for web search comparison)
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse


# ── Gemini API ──────────────────────────────────────────────────────────────

def call_gemini(prompt: str, api_key: str, model: str) -> dict:
    """Call Gemini API with Google Search grounding."""
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
    """Extract grounding sources from Gemini response."""
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


def extract_response_text(response: dict) -> str:
    """Extract text from Gemini response."""
    texts = []
    for cand in response.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if "text" in part:
                texts.append(part["text"])
    return "\n".join(texts)


# ── Brave Search API ───────────────────────────────────────────────────────

def search_brave(query: str, api_key: str, count: int = 20) -> list:
    """Search Brave and return list of {title, url, domain, rank}."""
    params = urllib.parse.urlencode({"q": query, "count": count})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                # Handle gzip
                if resp.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    data = gzip.decompress(data)
                result = json.loads(data)
                results = []
                for i, item in enumerate(result.get("web", {}).get("results", [])):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "domain": get_domain(item.get("url", "")),
                        "rank": i + 1,
                    })
                return results
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"  Brave search error: {e}", file=sys.stderr)
                return []


import urllib.parse


# ── Utilities ──────────────────────────────────────────────────────────────

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


# ── Main Analysis ─────────────────────────────────────────────────────────

def run_gemini_analysis(prompt: str, runs: int, model: str, concurrency: int):
    """Run prompt through Gemini with grounding and aggregate sources."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)

    domain_cite_count = defaultdict(int)
    domain_urls = defaultdict(set)
    total_ok = 0
    errors = 0

    print(f"Running Gemini grounding analysis ({runs} runs)...", file=sys.stderr)

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
                total_ok += 1
                seen_domains = set()
                for s in sources:
                    d = get_domain(s["uri"])
                    domain_urls[d].add(s["uri"])
                    if d not in seen_domains:
                        domain_cite_count[d] += 1
                        seen_domains.add(d)
                print(f"  Run {run_idx + 1}: {len(sources)} sources", file=sys.stderr)
            except Exception as e:
                errors += 1
                print(f"  Run {run_idx + 1}: EXCEPTION - {e}", file=sys.stderr)

    sorted_domains = sorted(domain_cite_count.items(), key=lambda x: (-x[1], x[0]))
    return {
        "successful_runs": total_ok,
        "errors": errors,
        "domains": {
            d: {
                "citation_rate": round(c / total_ok * 100) if total_ok else 0,
                "count": c,
                "urls": sorted(domain_urls.get(d, set())),
            }
            for d, c in sorted_domains
        },
    }


def run_analysis(prompt: str, domain: str, runs: int, model: str, concurrency: int = 5):
    """Full gap analysis: Gemini grounding + Brave web search."""
    # 1. Gemini grounding analysis
    gemini = run_gemini_analysis(prompt, runs, model, concurrency)

    # 2. Brave web search
    brave_key = os.environ.get("BRAVE_API_KEY")
    web_results = []
    web_domains = set()
    if brave_key:
        print("Running Brave web search...", file=sys.stderr)
        web_results = search_brave(prompt, brave_key, count=20)
        web_domains = {r["domain"] for r in web_results}
    else:
        print("BRAVE_API_KEY not set — skipping web search comparison", file=sys.stderr)

    # 3. Gap analysis
    gemini_domains = set(gemini["domains"].keys())

    google_only = []
    web_only = []
    both = []

    for d, info in gemini["domains"].items():
        if d in web_domains:
            web_rank = next((r["rank"] for r in web_results if r["domain"] == d), None)
            both.append({
                "domain": d,
                "ai_citation_rate": info["citation_rate"],
                "web_rank": web_rank,
            })
        else:
            google_only.append({
                "domain": d,
                "ai_citation_rate": info["citation_rate"],
            })

    for r in web_results:
        if r["domain"] not in gemini_domains and r["domain"] not in {w["domain"] for w in web_only}:
            web_only.append({
                "domain": r["domain"],
                "web_rank": r["rank"],
                "title": r["title"],
            })

    # 4. Domain-specific report
    target = domain.lower()
    if target.startswith("www."):
        target = target[4:]

    domain_report = {
        "domain": domain,
        "in_google_ai": target in gemini["domains"],
        "ai_citation_rate": gemini["domains"].get(target, {}).get("citation_rate", 0),
        "ai_cited_urls": gemini["domains"].get(target, {}).get("urls", []),
        "in_web_search": target in web_domains,
        "web_rank": next((r["rank"] for r in web_results if r["domain"] == target), None),
    }

    # Determine status
    if domain_report["in_google_ai"] and domain_report["in_web_search"]:
        domain_report["status"] = "STRONG"
        domain_report["status_detail"] = "Cross-platform visibility — cited by Google AI and ranks in web search"
    elif domain_report["in_google_ai"]:
        domain_report["status"] = "AI-ONLY"
        domain_report["status_detail"] = "Cited by Google AI but not in web top results — strong AI signals but weak traditional SEO"
    elif domain_report["in_web_search"]:
        domain_report["status"] = "WEB-ONLY"
        domain_report["status_detail"] = "Ranks in web search but not cited by Google AI — content may lack extractable answers"
    else:
        domain_report["status"] = "ABSENT"
        domain_report["status_detail"] = "Not found in Google AI citations or web top results — content gap"

    # 5. Recommendations
    recommendations = []
    if domain_report["status"] == "STRONG":
        recommendations.append("Maintain current content quality — you have cross-platform authority")
        recommendations.append("Monitor citation rate over time with aeo-analytics-free")
    elif domain_report["status"] == "AI-ONLY":
        recommendations.append("Strengthen traditional SEO (backlinks, technical SEO) to appear in web search")
        recommendations.append("Your content structure is AI-friendly — keep the extractable answer format")
    elif domain_report["status"] == "WEB-ONLY":
        recommendations.append("Add clear, extractable answers at the top of each section")
        recommendations.append("Use structured data (FAQ, HowTo) to help AI models identify citeable content")
        recommendations.append("Study Google-only sources' content structure — they're winning AI citations")
    elif domain_report["status"] == "ABSENT":
        recommendations.append("Create targeted content for this prompt using aeo-content-free")
        recommendations.append("Study both Google-only and web-top sources to understand what gets cited")

    if google_only:
        recommendations.append(f"Study {len(google_only)} Google AI-only sources — they have signals Gemini values")
    if web_only:
        recommendations.append(f"Note: {len(web_only)} web-ranking sources aren't cited by AI — traditional SEO alone isn't enough")

    result = {
        "prompt": prompt,
        "domain": domain,
        "model": model,
        "runs": runs,
        "gemini_analysis": {
            "successful_runs": gemini["successful_runs"],
            "errors": gemini["errors"],
            "top_domains": [
                {"domain": d, **info}
                for d, info in sorted(
                    gemini["domains"].items(),
                    key=lambda x: -x[1]["citation_rate"]
                )[:20]
            ],
        },
        "web_search": {
            "available": bool(brave_key),
            "results_count": len(web_results),
            "top_results": web_results[:10],
        },
        "gaps": {
            "google_ai_only": google_only[:15],
            "web_only": web_only[:15],
            "both": sorted(both, key=lambda x: -x["ai_citation_rate"])[:15],
        },
        "domain_report": domain_report,
        "recommendations": recommendations,
    }

    return result


def format_text(result: dict) -> str:
    lines = []
    lines.append(f"Citation Gap Analysis: \"{result['prompt']}\"")
    lines.append(f"Domain: {result['domain']}")
    lines.append("=" * 64)
    lines.append("")

    # Google AI citations
    ga = result["gemini_analysis"]
    lines.append(f"GOOGLE AI CITATIONS (Gemini 3 Flash, {ga['successful_runs']} runs):")
    for d in ga["top_domains"][:10]:
        lines.append(f"  {d['citation_rate']}% — {d['domain']}")
    lines.append("")

    # Web search results
    ws = result["web_search"]
    if ws["available"]:
        lines.append(f"WEB SEARCH RESULTS (Brave, top {ws['results_count']}):")
        for r in ws["top_results"]:
            lines.append(f"  #{r['rank']} — {r['domain']} — {r['title'][:60]}")
        lines.append("")

    # Gap analysis
    gaps = result["gaps"]
    if ws["available"]:
        lines.append("GAP ANALYSIS:")
        if gaps["google_ai_only"]:
            lines.append("  Google AI Only (not in web top 20):")
            for g in gaps["google_ai_only"][:8]:
                lines.append(f"    - {g['domain']} (cited {g['ai_citation_rate']}% in AI)")
        if gaps["web_only"]:
            lines.append("  Web Only (not cited by Google AI):")
            for w in gaps["web_only"][:8]:
                lines.append(f"    - {w['domain']} (web rank #{w['web_rank']})")
        if gaps["both"]:
            lines.append("  Both (cross-platform authority):")
            for b in gaps["both"][:8]:
                lines.append(f"    - {b['domain']} ({b['ai_citation_rate']}% AI, web #{b['web_rank']})")
        lines.append("")

    # Domain report
    dr = result["domain_report"]
    lines.append(f"DOMAIN REPORT: {dr['domain']}")
    ai_mark = "✅" if dr["in_google_ai"] else "❌"
    lines.append(f"  Google AI: {ai_mark} {'Cited in ' + str(dr['ai_citation_rate']) + '% of runs' if dr['in_google_ai'] else 'Not cited'}")
    if ws["available"]:
        web_mark = "✅" if dr["in_web_search"] else "❌"
        rank_str = f" (rank #{dr['web_rank']})" if dr["web_rank"] else ""
        lines.append(f"  Web Search: {web_mark} {'Appears in top 20' + rank_str if dr['in_web_search'] else 'Not in top 20'}")
    lines.append(f"  Status: {dr['status']} — {dr['status_detail']}")
    if dr.get("ai_cited_urls"):
        lines.append("  Cited URLs:")
        for url in dr["ai_cited_urls"][:5]:
            lines.append(f"    - {url}")
    lines.append("")

    # Recommendations
    if result["recommendations"]:
        lines.append("RECOMMENDATIONS:")
        for rec in result["recommendations"]:
            lines.append(f"  → {rec}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Find citation gaps between Google AI and web search for a prompt"
    )
    parser.add_argument("prompt", help="The query/prompt to analyze")
    parser.add_argument("--domain", required=True, help="Domain to track (e.g., example.com)")
    parser.add_argument("--runs", type=int, default=20, help="Number of Gemini runs (default: 20)")
    parser.add_argument("--model", default="gemini-3-flash-preview",
                        help="Gemini model (default: gemini-3-flash-preview)")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    args = parser.parse_args()

    result = run_analysis(args.prompt, args.domain, args.runs, args.model)

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
