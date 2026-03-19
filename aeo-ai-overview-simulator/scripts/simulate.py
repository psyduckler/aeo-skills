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


def run_simulation(prompt: str, runs: int, model: str, concurrency: int, domain: str = None):
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
    args = parser.parse_args()

    result = run_simulation(args.prompt, args.runs, args.model, args.concurrency, args.domain)

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
