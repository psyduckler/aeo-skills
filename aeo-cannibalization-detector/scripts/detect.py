#!/usr/bin/env python3
"""
Cannibalization Detector — Check if a brand's own pages compete against each
other for the same AI prompts. Detects when Gemini can't decide which of your
pages to cite.

Usage:
    python3 detect.py --domain example.com "prompt1" "prompt2" [--prompts-file file.txt] [--runs 20] [--model gemini-3-flash-preview] [--concurrency 5] [--output text|json]

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


def get_path(uri: str) -> str:
    """Extract path from URI for display."""
    try:
        parsed = urlparse(uri)
        return parsed.path or "/"
    except Exception:
        return "/"


# ── Core Logic ──────────────────────────────────────────────────────────────

def analyze_prompt(prompt: str, domain: str, runs: int, model: str,
                   concurrency: int, api_key: str) -> dict:
    """Run a single prompt and detect cannibalization for the target domain."""
    print(f"\n  Scanning: \"{prompt}\" ({runs} runs)...", file=sys.stderr)

    run_results = []
    errors = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(call_gemini, prompt, api_key, model): i for i in range(runs)}
        for future in as_completed(futures):
            run_idx = futures[future]
            try:
                resp = future.result()
                if "error" in resp:
                    errors += 1
                    print(f"    Run {run_idx + 1}: ERROR - {resp['error']}", file=sys.stderr)
                    continue
                sources = extract_sources(resp)
                run_results.append(sources)
                print(f"    Run {run_idx + 1}: {len(sources)} sources", file=sys.stderr)
            except Exception as e:
                errors += 1
                print(f"    Run {run_idx + 1}: EXCEPTION - {e}", file=sys.stderr)

    successful_runs = len(run_results)
    if successful_runs == 0:
        return {
            "prompt": prompt,
            "successful_runs": 0,
            "errors": errors,
            "cannibalization": None,
        }

    # Extract domain URLs across all runs
    target = domain.lower()
    if target.startswith("www."):
        target = target[4:]

    url_run_count = defaultdict(int)  # how many runs each URL was cited in
    url_titles = {}

    for run_sources in run_results:
        seen_in_run = set()
        for src in run_sources:
            src_domain = get_domain(src["uri"])
            if target in src_domain and src["uri"] not in seen_in_run:
                url_run_count[src["uri"]] += 1
                seen_in_run.add(src["uri"])
                if src["uri"] not in url_titles and src["title"]:
                    url_titles[src["uri"]] = src["title"]

    domain_urls = dict(url_run_count)
    total_domain_urls = len(domain_urls)

    # No cannibalization if 0 or 1 URL
    if total_domain_urls <= 1:
        single_url = list(domain_urls.keys())[0] if domain_urls else None
        single_rate = round(domain_urls[single_url] / successful_runs * 100) if single_url else 0
        return {
            "prompt": prompt,
            "successful_runs": successful_runs,
            "errors": errors,
            "domain_urls_found": total_domain_urls,
            "cannibalization": {
                "detected": False,
                "severity": "NONE",
                "urls": {single_url: {"citation_rate": single_rate, "title": url_titles.get(single_url, "")}} if single_url else {},
                "recommendation": "No cannibalization — single URL cited consistently." if single_url else f"No {domain} URLs cited for this prompt.",
            },
        }

    # Multiple URLs found — analyze competition
    url_rates = {}
    for url, count in domain_urls.items():
        rate = round(count / successful_runs * 100)
        url_rates[url] = {
            "citation_rate": rate,
            "citation_count": count,
            "title": url_titles.get(url, ""),
            "path": get_path(url),
        }

    # Determine severity
    max_rate = max(r["citation_rate"] for r in url_rates.values())
    if max_rate > 80:
        severity = "LOW"
        recommendation = (
            f"One URL dominates ({max_rate}%). Minor cannibalization — the other "
            f"URL(s) appear occasionally but don't significantly dilute citations. "
            f"Consider canonicalizing or merging the weaker pages."
        )
    elif max_rate >= 50:
        severity = "MEDIUM"
        recommendation = (
            f"Top URL only cited {max_rate}% of the time. Gemini is splitting "
            f"citations between your pages. Consider differentiating the pages' "
            f"focus or consolidating content into a single authoritative page."
        )
    else:
        severity = "HIGH"
        recommendation = (
            f"No single URL exceeds 50% citation rate. Gemini can't decide which "
            f"of your pages to cite — citations are diluted across {total_domain_urls} "
            f"URLs. Strongly recommend consolidating into one comprehensive page "
            f"or clearly differentiating each page's topic."
        )

    return {
        "prompt": prompt,
        "successful_runs": successful_runs,
        "errors": errors,
        "domain_urls_found": total_domain_urls,
        "cannibalization": {
            "detected": True,
            "severity": severity,
            "max_citation_rate": max_rate,
            "urls": url_rates,
            "recommendation": recommendation,
        },
    }


def run_detector(domain: str, prompts: list, runs: int, model: str, concurrency: int):
    """Run cannibalization detection across all prompts."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)

    print(f"Cannibalization Detector — {domain}", file=sys.stderr)
    print(f"Prompts: {len(prompts)} | Model: {model} | Runs per prompt: {runs}", file=sys.stderr)

    results = []
    for prompt in prompts:
        result = analyze_prompt(prompt, domain, runs, model, concurrency, api_key)
        results.append(result)

    # Summary
    cannibalized = [r for r in results if r.get("cannibalization", {}).get("detected")]
    severity_counts = defaultdict(int)
    for r in cannibalized:
        sev = r["cannibalization"]["severity"]
        severity_counts[sev] += 1

    summary = {
        "domain": domain,
        "total_prompts": len(prompts),
        "prompts_with_cannibalization": len(cannibalized),
        "severity_breakdown": dict(severity_counts),
        "worst_offenders": [],
    }

    # Find worst offenders (HIGH severity first, then MEDIUM)
    for r in sorted(cannibalized, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(
            x["cannibalization"]["severity"], 3)):
        summary["worst_offenders"].append({
            "prompt": r["prompt"],
            "severity": r["cannibalization"]["severity"],
            "competing_urls": len(r["cannibalization"]["urls"]),
            "max_citation_rate": r["cannibalization"].get("max_citation_rate", 0),
        })

    return {
        "domain": domain,
        "model": model,
        "runs_per_prompt": runs,
        "results": results,
        "summary": summary,
    }


def format_text(data: dict) -> str:
    """Format results as human-readable text."""
    lines = []
    lines.append(f"Cannibalization Detector: {data['domain']}")
    lines.append(f"Model: {data['model']} | Runs per prompt: {data['runs_per_prompt']}")
    lines.append("")

    # Per-prompt results
    lines.append("RESULTS BY PROMPT:")
    lines.append("=" * 70)

    for r in data["results"]:
        lines.append(f"\n\"{r['prompt']}\"")
        lines.append(f"  Runs: {r['successful_runs']} | Domain URLs found: {r.get('domain_urls_found', 0)}")

        cannibal = r.get("cannibalization")
        if not cannibal:
            lines.append("  ⚠ No data (all runs failed)")
            continue

        if not cannibal["detected"]:
            lines.append(f"  Status: ✓ No cannibalization")
            urls = cannibal.get("urls", {})
            for url, info in urls.items():
                lines.append(f"    {info['citation_rate']}% — {url}")
            lines.append(f"  {cannibal['recommendation']}")
            continue

        severity = cannibal["severity"]
        icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")
        lines.append(f"  Status: {icon} {severity} cannibalization")
        lines.append(f"  Competing URLs:")

        for url, info in sorted(cannibal["urls"].items(),
                                 key=lambda x: -x[1]["citation_rate"]):
            title = f" — {info['title']}" if info.get("title") else ""
            lines.append(f"    {info['citation_rate']}% ({info['citation_count']}/{r['successful_runs']}) {info['path']}{title}")
            lines.append(f"      {url}")

        lines.append(f"  → {cannibal['recommendation']}")

    # Summary
    s = data["summary"]
    lines.append("")
    lines.append("SUMMARY:")
    lines.append("=" * 70)
    lines.append(f"  Domain: {s['domain']}")
    lines.append(f"  Prompts analyzed: {s['total_prompts']}")
    lines.append(f"  Cannibalization detected: {s['prompts_with_cannibalization']}/{s['total_prompts']}")

    if s["severity_breakdown"]:
        sev_str = ", ".join(f"{k}: {v}" for k, v in sorted(s["severity_breakdown"].items()))
        lines.append(f"  Severity: {sev_str}")

    if s["worst_offenders"]:
        lines.append(f"\n  Worst offenders:")
        for wo in s["worst_offenders"][:5]:
            icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(wo["severity"], "⚪")
            lines.append(f"    {icon} \"{wo['prompt']}\" — {wo['severity']} "
                         f"({wo['competing_urls']} URLs, max {wo['max_citation_rate']}%)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Detect when your own pages compete against each other for AI citations"
    )
    parser.add_argument("prompts", nargs="*", help="Prompts to analyze")
    parser.add_argument("--domain", required=True,
                        help="Your domain to check (e.g., example.com)")
    parser.add_argument("--prompts-file",
                        help="File with one prompt per line (in addition to positional prompts)")
    parser.add_argument("--runs", type=int, default=20,
                        help="Runs per prompt (default: 20)")
    parser.add_argument("--model", default="gemini-3-flash-preview",
                        help="Gemini model (default: gemini-3-flash-preview)")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="Max concurrent requests (default: 5)")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    args = parser.parse_args()

    # Collect prompts from args and file
    all_prompts = list(args.prompts) if args.prompts else []
    if args.prompts_file:
        try:
            with open(args.prompts_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        all_prompts.append(line)
        except FileNotFoundError:
            print(f"Error: prompts file not found: {args.prompts_file}", file=sys.stderr)
            sys.exit(1)

    if not all_prompts:
        print("Error: at least one prompt required (positional or --prompts-file)", file=sys.stderr)
        sys.exit(1)

    result = run_detector(args.domain, all_prompts, args.runs, args.model, args.concurrency)

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
