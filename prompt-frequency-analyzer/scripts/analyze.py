#!/usr/bin/env python3
"""
Prompt Frequency Analyzer — Run a prompt N times against Gemini with Google Search
grounding and report search query frequencies.

Usage:
    python3 analyze.py "your prompt here" [--runs 20] [--model gemini-3-flash-preview] [--concurrency 5] [--output json|text]

Requires: GEMINI_API_KEY env var
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Shared imports ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.gemini_client import (
    call_gemini, extract_queries, extract_sources, classify_intent, get_api_key,
    DEFAULT_MODEL, DEFAULT_RUNS, DEFAULT_CONCURRENCY,
)


def run_analysis(prompt: str, runs: int, model: str, concurrency: int):
    """Run prompt N times and collect search query data."""
    api_key = get_api_key()

    all_run_queries = []
    all_sources = []
    errors = 0

    print(f"Running '{prompt}' x{runs} against {model}...", file=sys.stderr)

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
                queries = extract_queries(resp)
                sources = extract_sources(resp)
                all_run_queries.append(queries)
                all_sources.extend(sources)
                print(f"  Run {run_idx + 1}: {len(queries)} queries", file=sys.stderr)
            except Exception as e:
                errors += 1
                print(f"  Run {run_idx + 1}: EXCEPTION - {e}", file=sys.stderr)

    successful_runs = len(all_run_queries)

    # Exact frequency: how many runs included each query
    query_run_count = defaultdict(int)
    for run_queries in all_run_queries:
        seen_in_run = set()
        for q in run_queries:
            ql = q.strip().lower()
            if ql not in seen_in_run:
                query_run_count[ql] += 1
                seen_in_run.add(ql)

    sorted_queries = sorted(query_run_count.items(), key=lambda x: (-x[1], x[0]))

    # Source frequency
    source_count = defaultdict(int)
    for s in all_sources:
        domain = s.get("title", s.get("uri", ""))
        source_count[domain] += 1
    sorted_sources = sorted(source_count.items(), key=lambda x: (-x[1], x[0]))

    # Build queries with intent classification
    queries_out = []
    intent_counts = defaultdict(int)
    for q, c in sorted_queries:
        intent = classify_intent(q)
        intent_counts[intent] += 1
        queries_out.append({
            "query": q,
            "count": c,
            "frequency": round(c / successful_runs * 100) if successful_runs else 0,
            "intent": intent,
        })

    total_unique = len(sorted_queries)
    intent_distribution = {}
    for intent_type in ["informational", "commercial", "navigational", "transactional"]:
        cnt = intent_counts.get(intent_type, 0)
        intent_distribution[intent_type] = round(cnt / total_unique * 100) if total_unique else 0

    return {
        "prompt": prompt,
        "model": model,
        "total_runs": runs,
        "successful_runs": successful_runs,
        "errors": errors,
        "unique_queries": len(sorted_queries),
        "queries": queries_out,
        "intent_distribution": intent_distribution,
        "sources": [
            {"domain": d, "count": c}
            for d, c in sorted_sources[:20]
        ],
    }


def format_text(result: dict) -> str:
    lines = []
    lines.append(f"Prompt: \"{result['prompt']}\"")
    lines.append(f"Model: {result['model']}")
    lines.append(f"Runs: {result['successful_runs']}/{result['total_runs']} successful")
    lines.append(f"Unique queries: {result['unique_queries']}")
    lines.append("")
    lines.append("Search Query Frequency:")
    lines.append("=" * 60)
    for q in result["queries"]:
        lines.append(f"  {q['frequency']}% ({q['count']}/{result['successful_runs']}) [{q['intent']}] — {q['query']}")
    if result.get("intent_distribution"):
        lines.append("")
        lines.append("Intent Distribution:")
        lines.append("=" * 60)
        dist = result["intent_distribution"]
        parts = [f"{dist.get(k, 0)}% {k}" for k in ["informational", "commercial", "navigational", "transactional"]]
        lines.append(f"  {', '.join(parts)}")
    if result["sources"]:
        lines.append("")
        lines.append("Top Sources Referenced:")
        lines.append("=" * 60)
        for s in result["sources"]:
            lines.append(f"  {s['count']}x — {s['domain']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze Gemini search query frequency for a prompt")
    parser.add_argument("prompt", help="The prompt to analyze")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="Number of runs (default: 20)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model (default: gemini-3-flash-preview)")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Max concurrent requests (default: 5)")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="Output format")
    args = parser.parse_args()

    result = run_analysis(args.prompt, args.runs, args.model, args.concurrency)

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
