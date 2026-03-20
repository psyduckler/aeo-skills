#!/usr/bin/env python3
"""
Grounding Query Mapper — Map the search queries Gemini 3 Flash fires when
answering prompts. Clusters similar queries, identifies patterns, and
supports cross-prompt analysis.

Usage:
    python3 map_queries.py "prompt" [--runs 20] [--model gemini-3-flash-preview] [--concurrency 5] [--output text|json]
    python3 map_queries.py "prompt1" "prompt2" "prompt3"
    python3 map_queries.py --prompts-file prompts.txt

Requires: GEMINI_API_KEY env var
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Shared imports ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.gemini_client import (
    call_gemini, extract_queries, extract_sources, classify_intent, get_api_key,
    DEFAULT_MODEL, DEFAULT_RUNS, DEFAULT_CONCURRENCY,
)


# ── Query Clustering ────────────────────────────────────────────────────────

STOP_WORDS = frozenset([
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "these", "those", "what", "which", "who",
    "how", "when", "where", "why", "do", "does", "did", "has", "have", "had",
    "can", "could", "will", "would", "should", "may", "might", "vs", "vs.",
])


def tokenize(text: str) -> set:
    """Tokenize a query into meaningful words."""
    words = set(re.findall(r'[a-z0-9]+', text.lower()))
    return words - STOP_WORDS


def cluster_queries(queries_with_freq: list, min_shared: int = 2) -> list:
    """Cluster queries that share significant terms."""
    if not queries_with_freq:
        return []

    query_tokens = []
    for q, count, freq in queries_with_freq:
        tokens = tokenize(q)
        query_tokens.append((q, count, freq, tokens))

    term_groups = defaultdict(list)
    for q, count, freq, tokens in query_tokens:
        sorted_tokens = sorted(tokens)
        for i in range(len(sorted_tokens)):
            for j in range(i + 1, min(i + 4, len(sorted_tokens) + 1)):
                key = " ".join(sorted_tokens[i:j])
                if len(sorted_tokens[i:j]) >= min_shared:
                    term_groups[key].append((q, count, freq))

    candidate_clusters = []
    for label, members in term_groups.items():
        if len(members) >= 2:
            max_freq = max(f for _, _, f in members)
            candidate_clusters.append({
                "label": label,
                "queries": [{"query": q, "count": c, "frequency": f} for q, c, f in members],
                "coverage": max_freq,
                "size": len(members),
            })

    candidate_clusters.sort(key=lambda c: -(c["size"] * c["coverage"]))

    used_queries = set()
    final_clusters = []
    for cluster in candidate_clusters:
        new_queries = [q for q in cluster["queries"] if q["query"] not in used_queries]
        if len(new_queries) >= 2:
            for q in new_queries:
                used_queries.add(q["query"])
            cluster["queries"] = new_queries
            cluster["size"] = len(new_queries)
            final_clusters.append(cluster)

        if len(final_clusters) >= 8:
            break

    return final_clusters


# ── Per-Prompt Analysis ────────────────────────────────────────────────────

def analyze_prompt(prompt: str, runs: int, model: str, concurrency: int, api_key: str) -> dict:
    """Run a single prompt N times and analyze query patterns."""
    all_run_queries = []
    all_sources = []
    errors = 0

    print(f"\nAnalyzing: \"{prompt}\" ({runs} runs)...", file=sys.stderr)

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

    query_run_count = defaultdict(int)
    for run_queries in all_run_queries:
        seen_in_run = set()
        for q in run_queries:
            ql = q.strip().lower()
            if ql not in seen_in_run:
                query_run_count[ql] += 1
                seen_in_run.add(ql)

    sorted_queries = sorted(query_run_count.items(), key=lambda x: (-x[1], x[0]))

    queries_with_freq = [
        (q, c, round(c / successful_runs * 100) if successful_runs else 0)
        for q, c in sorted_queries
    ]

    clusters = cluster_queries(queries_with_freq)

    intent_counts = defaultdict(int)
    queries_out = []
    for q, c, f in queries_with_freq:
        intent = classify_intent(q)
        intent_counts[intent] += 1
        queries_out.append({"query": q, "count": c, "frequency": f, "intent": intent})

    total_unique = len(queries_with_freq)
    intent_distribution = {}
    for intent_type in ["informational", "commercial", "navigational", "transactional"]:
        cnt = intent_counts.get(intent_type, 0)
        intent_distribution[intent_type] = round(cnt / total_unique * 100) if total_unique else 0

    source_count = defaultdict(int)
    for s in all_sources:
        domain = s.get("title", s.get("uri", ""))
        source_count[domain] += 1
    sorted_sources = sorted(source_count.items(), key=lambda x: (-x[1], x[0]))

    return {
        "prompt": prompt,
        "model": model,
        "total_runs": runs,
        "successful_runs": successful_runs,
        "errors": errors,
        "unique_queries": len(sorted_queries),
        "queries": queries_out,
        "intent_distribution": intent_distribution,
        "clusters": clusters,
        "sources": [
            {"domain": d, "count": c}
            for d, c in sorted_sources[:20]
        ],
    }


# ── Cross-Prompt Analysis ──────────────────────────────────────────────────

def cross_prompt_analysis(prompt_results: list) -> dict:
    """Analyze query overlap across multiple prompts."""
    if len(prompt_results) < 2:
        return {}

    query_prompts = defaultdict(set)
    for i, result in enumerate(prompt_results):
        for q in result["queries"]:
            query_prompts[q["query"]].add(i)

    shared = []
    for query, prompt_indices in sorted(query_prompts.items(), key=lambda x: -len(x[1])):
        if len(prompt_indices) >= 2:
            shared.append({
                "query": query,
                "prompt_count": len(prompt_indices),
                "prompt_indices": sorted(prompt_indices),
            })

    unique_per_prompt = defaultdict(list)
    for query, prompt_indices in query_prompts.items():
        if len(prompt_indices) == 1:
            idx = next(iter(prompt_indices))
            unique_per_prompt[idx].append(query)

    n = len(prompt_results)
    overlap_matrix = []
    for i in range(n):
        row = []
        queries_i = {q["query"] for q in prompt_results[i]["queries"]}
        for j in range(n):
            if i == j:
                row.append(len(queries_i))
            else:
                queries_j = {q["query"] for q in prompt_results[j]["queries"]}
                row.append(len(queries_i & queries_j))
        overlap_matrix.append(row)

    return {
        "shared_queries": shared[:20],
        "unique_queries_per_prompt": {
            str(k): v[:10] for k, v in unique_per_prompt.items()
        },
        "overlap_matrix": overlap_matrix,
    }


# ── Output Formatting ──────────────────────────────────────────────────────

def format_prompt_text(result: dict, index: int = None) -> list:
    """Format a single prompt's results as text lines."""
    lines = []
    prefix = f"Prompt {index}: " if index is not None else ""
    lines.append(f"{prefix}\"{result['prompt']}\"")
    lines.append(f"Model: {result['model']} | Runs: {result['successful_runs']}/{result['total_runs']}")
    lines.append(f"Unique queries: {result['unique_queries']}")
    lines.append("")

    lines.append("Query Frequency:")
    lines.append("-" * 60)
    for q in result["queries"]:
        lines.append(f"  {q['frequency']}% ({q['count']}/{result['successful_runs']}) [{q['intent']}] — {q['query']}")

    if result.get("intent_distribution"):
        lines.append("")
        lines.append("Intent Distribution:")
        lines.append("-" * 60)
        dist = result["intent_distribution"]
        parts = [f"{dist.get(k, 0)}% {k}" for k in ["informational", "commercial", "navigational", "transactional"]]
        lines.append(f"  {', '.join(parts)}")

    if result["clusters"]:
        lines.append("")
        lines.append("Query Clusters:")
        lines.append("-" * 60)
        for cluster in result["clusters"]:
            lines.append(f"  [{cluster['label']}] ({cluster['size']} queries)")
            for q in cluster["queries"]:
                lines.append(f"    - {q['query']} ({q['frequency']}%)")

    if result["sources"]:
        lines.append("")
        lines.append("Top Sources:")
        lines.append("-" * 60)
        for s in result["sources"][:10]:
            lines.append(f"  {s['count']}x — {s['domain']}")

    return lines


def format_text(prompt_results: list, cross: dict) -> str:
    """Format all results as text."""
    lines = []

    for i, result in enumerate(prompt_results):
        if i > 0:
            lines.append("")
            lines.append("=" * 64)
        idx = i + 1 if len(prompt_results) > 1 else None
        lines.extend(format_prompt_text(result, idx))

    if cross:
        lines.append("")
        lines.append("=" * 64)
        lines.append("CROSS-PROMPT ANALYSIS")
        lines.append("=" * 64)

        if cross["shared_queries"]:
            lines.append("")
            lines.append("Shared Queries (appear in multiple prompts):")
            for sq in cross["shared_queries"][:15]:
                prompts_str = ", ".join(str(i + 1) for i in sq["prompt_indices"])
                lines.append(f"  \"{sq['query']}\" — prompts {prompts_str} ({sq['prompt_count']}/{len(prompt_results)})")

        if cross.get("unique_queries_per_prompt"):
            lines.append("")
            lines.append("Unique Queries (specific to one prompt):")
            for idx_str, queries in cross["unique_queries_per_prompt"].items():
                idx = int(idx_str)
                lines.append(f"  Prompt {idx + 1}: {len(queries)} unique queries")
                for q in queries[:5]:
                    lines.append(f"    - {q}")

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Map search queries Gemini fires when answering prompts"
    )
    parser.add_argument("prompt", nargs="*", help="One or more prompts to analyze")
    parser.add_argument("--prompts-file", help="File with one prompt per line")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="Runs per prompt (default: 20)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="Gemini model (default: gemini-3-flash-preview)")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help="Max concurrent requests (default: 5)")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    args = parser.parse_args()

    prompts = list(args.prompt) if args.prompt else []
    if args.prompts_file:
        try:
            with open(args.prompts_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        prompts.append(line)
        except FileNotFoundError:
            print(f"Error: prompts file not found: {args.prompts_file}", file=sys.stderr)
            sys.exit(1)

    if not prompts:
        print("Error: provide at least one prompt (positional or via --prompts-file)", file=sys.stderr)
        sys.exit(1)

    api_key = get_api_key()

    prompt_results = []
    for prompt in prompts:
        result = analyze_prompt(prompt, args.runs, args.model, args.concurrency, api_key)
        prompt_results.append(result)

    cross = cross_prompt_analysis(prompt_results) if len(prompt_results) > 1 else {}

    if args.output == "json":
        output = {
            "prompts": prompt_results,
            "cross_prompt_analysis": cross,
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_text(prompt_results, cross))


if __name__ == "__main__":
    main()
