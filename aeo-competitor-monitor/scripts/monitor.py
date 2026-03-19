#!/usr/bin/env python3
"""
Competitor Monitor — Track competitor citations in AI Overviews over time.
Runs prompts through Gemini 3 Flash with grounding, records citation data,
and generates comparison reports.

Usage:
    python3 monitor.py scan --prompts "p1" "p2" --competitors "a.com" "b.com" [--data-file monitor-data.json] [--runs 20]
    python3 monitor.py report --data-file monitor-data.json [--output text|json]

Requires: GEMINI_API_KEY env var (for scan command)
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
from datetime import datetime, timezone
from pathlib import Path
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


def extract_response_text(response: dict) -> str:
    """Extract text from Gemini response."""
    texts = []
    for cand in response.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if "text" in part:
                texts.append(part["text"])
    return "\n".join(texts)


def extract_sources(response: dict) -> list:
    """Extract grounding sources from response."""
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


def find_domain_mentions(text: str, domain: str) -> list:
    """Find sentences mentioning a domain/brand in text."""
    brand = domain.split(".")[0] if "." in domain else domain
    sentences = re.split(r'(?<=[.!?])\s+', text)
    excerpts = []
    for s in sentences:
        if domain.lower() in s.lower() or brand.lower() in s.lower():
            excerpts.append(s.strip())
    return excerpts


# ── Data File ──────────────────────────────────────────────────────────────

def load_data(data_file: str) -> dict:
    """Load or initialize the data file."""
    if os.path.exists(data_file):
        with open(data_file) as f:
            return json.load(f)
    return {"scans": []}


def save_data(data: dict, data_file: str):
    """Save data file."""
    Path(data_file).parent.mkdir(parents=True, exist_ok=True)
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)


# ── Scan Command ───────────────────────────────────────────────────────────

def scan_prompt(prompt: str, competitors: list, runs: int, model: str,
                concurrency: int, api_key: str) -> dict:
    """Scan a single prompt and track competitor citations."""
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
                text = extract_response_text(resp)
                sources = extract_sources(resp)
                run_results.append({"text": text, "sources": sources})
                print(f"    Run {run_idx + 1}: {len(sources)} sources", file=sys.stderr)
            except Exception as e:
                errors += 1
                print(f"    Run {run_idx + 1}: EXCEPTION - {e}", file=sys.stderr)

    successful_runs = len(run_results)

    # Track each competitor
    competitor_data = {}
    for comp in competitors:
        comp_clean = comp.lower()
        if comp_clean.startswith("www."):
            comp_clean = comp_clean[4:]

        citation_count = 0
        mention_count = 0
        cited_urls = defaultdict(int)
        all_excerpts = []

        for run in run_results:
            # Check citations
            cited_in_run = False
            for source in run["sources"]:
                if comp_clean in get_domain(source["uri"]):
                    cited_in_run = True
                    cited_urls[source["uri"]] += 1
            if cited_in_run:
                citation_count += 1

            # Check mentions
            excerpts = find_domain_mentions(run["text"], comp_clean)
            if excerpts:
                mention_count += 1
                all_excerpts.extend(excerpts)

        unique_excerpts = list(dict.fromkeys(all_excerpts))[:5]

        competitor_data[comp] = {
            "citation_rate": round(citation_count / successful_runs * 100) if successful_runs else 0,
            "citation_count": citation_count,
            "mention_rate": round(mention_count / successful_runs * 100) if successful_runs else 0,
            "mention_count": mention_count,
            "cited_urls": dict(sorted(cited_urls.items(), key=lambda x: -x[1])),
            "excerpts": unique_excerpts,
        }

    # Track other (non-competitor) sources
    all_domains = defaultdict(int)
    comp_set = {c.lower().replace("www.", "") for c in competitors}
    for run in run_results:
        seen = set()
        for source in run["sources"]:
            d = get_domain(source["uri"])
            if d not in comp_set and d not in seen:
                all_domains[d] += 1
                seen.add(d)

    other_sources = [
        {"domain": d, "citation_rate": round(c / successful_runs * 100) if successful_runs else 0}
        for d, c in sorted(all_domains.items(), key=lambda x: -x[1])[:10]
    ]

    return {
        "successful_runs": successful_runs,
        "errors": errors,
        "competitors": competitor_data,
        "other_sources": other_sources,
    }


def cmd_scan(args):
    """Run a competitive scan."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)

    data = load_data(args.data_file)

    print(f"Competitor Monitor — Scanning {len(args.prompts)} prompts", file=sys.stderr)
    print(f"Competitors: {', '.join(args.competitors)}", file=sys.stderr)
    print(f"Model: {args.model} | Runs per prompt: {args.runs}", file=sys.stderr)

    scan_results = {}
    for prompt in args.prompts:
        result = scan_prompt(
            prompt, args.competitors, args.runs, args.model,
            args.concurrency, api_key
        )
        scan_results[prompt] = result

    # Save scan
    scan_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "runs_per_prompt": args.runs,
        "competitors_tracked": args.competitors,
        "results": scan_results,
    }
    data["scans"].append(scan_entry)
    save_data(data, args.data_file)

    scan_num = len(data["scans"])
    print(f"\nScan complete: {len(args.prompts)} prompts × {args.runs} runs", file=sys.stderr)
    print(f"Saved to {args.data_file} (scan #{scan_num})", file=sys.stderr)

    # Print quick summary
    print(f"\nQuick Results:")
    for prompt, result in scan_results.items():
        print(f"  \"{prompt}\":")
        for comp, cdata in sorted(result["competitors"].items(),
                                   key=lambda x: -x[1]["citation_rate"]):
            print(f"    {comp:25s} — {cdata['citation_rate']}% citation rate")


def cmd_report(args):
    """Generate a comparison report from scan data."""
    if not os.path.exists(args.data_file):
        print(f"Error: data file not found: {args.data_file}", file=sys.stderr)
        sys.exit(1)

    data = load_data(args.data_file)
    scans = data.get("scans", [])

    if not scans:
        print("No scan data found.", file=sys.stderr)
        sys.exit(1)

    # Collect all prompts and competitors across scans
    all_prompts = set()
    all_competitors = set()
    for scan in scans:
        all_prompts.update(scan["results"].keys())
        all_competitors.update(scan.get("competitors_tracked", []))

    # Calculate per-prompt, per-competitor trends
    prompt_trends = {}
    for prompt in sorted(all_prompts):
        comp_history = defaultdict(list)
        for scan in scans:
            if prompt in scan["results"]:
                result = scan["results"][prompt]
                timestamp = scan["timestamp"]
                for comp, cdata in result.get("competitors", {}).items():
                    comp_history[comp].append({
                        "timestamp": timestamp,
                        "citation_rate": cdata["citation_rate"],
                        "citation_count": cdata.get("citation_count", 0),
                    })
        prompt_trends[prompt] = dict(comp_history)

    # Calculate overall averages
    overall = defaultdict(list)
    latest_scan = scans[-1]
    for prompt, result in latest_scan["results"].items():
        for comp, cdata in result.get("competitors", {}).items():
            overall[comp].append(cdata["citation_rate"])

    overall_avg = {
        comp: round(sum(rates) / len(rates)) if rates else 0
        for comp, rates in overall.items()
    }

    # Determine date range
    first_date = scans[0]["timestamp"][:10]
    last_date = scans[-1]["timestamp"][:10]
    try:
        d1 = datetime.fromisoformat(scans[0]["timestamp"].replace("Z", "+00:00"))
        d2 = datetime.fromisoformat(scans[-1]["timestamp"].replace("Z", "+00:00"))
        days = (d2 - d1).days
    except Exception:
        days = 0

    report = {
        "data_file": args.data_file,
        "total_scans": len(scans),
        "date_range": {"first": first_date, "last": last_date, "days": days},
        "prompt_trends": prompt_trends,
        "overall_avg": overall_avg,
    }

    if args.output == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_report_text(report, scans))


def format_report_text(report: dict, scans: list) -> str:
    """Format report as text."""
    lines = []
    lines.append("Competitor Monitor Report")
    dr = report["date_range"]
    lines.append(f"Data: {report['data_file']} ({report['total_scans']} scans, {dr['days']} days)")
    lines.append("=" * 64)

    # Per-prompt breakdown
    lines.append("")
    lines.append("CITATION SHARE BY PROMPT:")

    for prompt, comp_history in report["prompt_trends"].items():
        scan_count = 0
        for comp, entries in comp_history.items():
            scan_count = max(scan_count, len(entries))
        lines.append(f"\n\"{prompt}\" ({scan_count} scans):")
        lines.append(f"  {'Competitor':<25s} {'Latest':>8s} {'Avg':>8s} {'Trend':>10s}")
        lines.append(f"  {'─' * 55}")

        for comp in sorted(comp_history.keys()):
            entries = comp_history[comp]
            if not entries:
                continue
            latest = entries[-1]["citation_rate"]
            avg = round(sum(e["citation_rate"] for e in entries) / len(entries))

            # Trend: compare latest to first
            if len(entries) >= 2:
                diff = latest - entries[0]["citation_rate"]
                if diff > 5:
                    trend = f"↑ +{diff}%"
                elif diff < -5:
                    trend = f"↓ {diff}%"
                else:
                    trend = "→ stable"
            else:
                trend = "—"

            lines.append(f"  {comp:<25s} {latest:>7d}% {avg:>7d}% {trend:>10s}")

    # Overall
    lines.append("")
    lines.append("OVERALL CITATION SHARE (across all prompts):")
    for comp, avg in sorted(report["overall_avg"].items(), key=lambda x: -x[1]):
        lines.append(f"  {comp:<25s} — {avg}% avg citation rate")

    # Notable changes
    lines.append("")
    lines.append("NOTABLE CHANGES:")
    changes_found = False
    for prompt, comp_history in report["prompt_trends"].items():
        for comp, entries in comp_history.items():
            if len(entries) >= 2:
                diff = entries[-1]["citation_rate"] - entries[-2]["citation_rate"]
                if abs(diff) >= 10:
                    changes_found = True
                    arrow = "↑" if diff > 0 else "↓"
                    lines.append(f"  {arrow} {comp} {'+' if diff > 0 else ''}{diff}% on \"{prompt}\"")
    if not changes_found:
        lines.append("  No significant changes (±10%) since last scan")

    # Cited URLs from latest scan
    lines.append("")
    lines.append("CITED URLS (latest scan):")
    latest = scans[-1]
    for prompt, result in latest["results"].items():
        for comp, cdata in result.get("competitors", {}).items():
            urls = cdata.get("cited_urls", {})
            if urls:
                lines.append(f"  {comp}:")
                for url, count in sorted(urls.items(), key=lambda x: -x[1])[:3]:
                    lines.append(f"    - {url} ({count}x)")

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Track competitor citations in AI Overviews over time"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Scan subcommand
    scan_parser = subparsers.add_parser("scan", help="Run a competitive scan")
    scan_parser.add_argument("--prompts", nargs="+", required=True,
                             help="Prompts to scan")
    scan_parser.add_argument("--competitors", nargs="+", required=True,
                             help="Competitor domains to track")
    scan_parser.add_argument("--data-file", default="monitor-data.json",
                             help="Data file path (default: monitor-data.json)")
    scan_parser.add_argument("--runs", type=int, default=20,
                             help="Runs per prompt (default: 20)")
    scan_parser.add_argument("--model", default="gemini-3-flash-preview",
                             help="Gemini model (default: gemini-3-flash-preview)")
    scan_parser.add_argument("--concurrency", type=int, default=5,
                             help="Max concurrent requests (default: 5)")

    # Report subcommand
    report_parser = subparsers.add_parser("report", help="Generate comparison report")
    report_parser.add_argument("--data-file", default="monitor-data.json",
                               help="Data file path (default: monitor-data.json)")
    report_parser.add_argument("--output", choices=["text", "json"], default="text",
                               help="Output format (default: text)")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()
