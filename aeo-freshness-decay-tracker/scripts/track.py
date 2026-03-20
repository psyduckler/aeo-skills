#!/usr/bin/env python3
"""
Freshness Decay Tracker — Monitor how citation rates change as content ages.
Append-only data file with trend analysis and decay detection.

Usage:
    python3 track.py scan --domain example.com --prompts "p1" "p2" [--data-file freshness.json] [--runs 20]
    python3 track.py report --data-file freshness.json [--output text|json]

Requires: GEMINI_API_KEY env var (for scan command)
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# ── Shared imports ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.gemini_client import (
    call_gemini, extract_response_text, extract_sources, extract_domain,
    domain_matches, get_api_key,
    DEFAULT_MODEL, DEFAULT_RUNS, DEFAULT_CONCURRENCY,
)


def find_domain_mentions(text: str, domain: str) -> bool:
    """Check if domain/brand is mentioned in text."""
    brand = domain.split(".")[0] if "." in domain else domain
    text_lower = text.lower()
    return domain.lower() in text_lower or brand.lower() in text_lower


# ── Data File ──────────────────────────────────────────────────────────────

def load_data(data_file: str) -> dict:
    if os.path.exists(data_file):
        with open(data_file) as f:
            return json.load(f)
    return {"scans": []}


def save_data(data: dict, data_file: str):
    Path(data_file).parent.mkdir(parents=True, exist_ok=True)
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)


# ── Scan Command ───────────────────────────────────────────────────────────

def scan_prompt(prompt: str, domain: str, runs: int, model: str,
                concurrency: int, api_key: str) -> dict:
    """Scan a single prompt for domain citation rates."""
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
    if successful_runs == 0:
        return {"successful_runs": 0, "errors": errors}

    target = domain.lower()
    if target.startswith("www."):
        target = target[4:]

    mention_count = 0
    citation_count = 0
    cited_urls = defaultdict(int)

    for run in run_results:
        if find_domain_mentions(run["text"], target):
            mention_count += 1

        cited_in_run = False
        for src in run["sources"]:
            if target in extract_domain(src["uri"]):
                cited_in_run = True
                cited_urls[src["uri"]] += 1
        if cited_in_run:
            citation_count += 1

    return {
        "successful_runs": successful_runs,
        "errors": errors,
        "mention_rate": round(mention_count / successful_runs * 100),
        "mention_count": mention_count,
        "citation_rate": round(citation_count / successful_runs * 100),
        "citation_count": citation_count,
        "cited_urls": dict(sorted(cited_urls.items(), key=lambda x: -x[1])),
    }


def cmd_scan(args):
    """Run a freshness scan and append results."""
    api_key = get_api_key()

    prompts = list(args.prompts) if args.prompts else []
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
        print("Error: at least one prompt required", file=sys.stderr)
        sys.exit(1)

    data = load_data(args.data_file)

    print(f"Freshness Decay Tracker — Scan", file=sys.stderr)
    print(f"Domain: {args.domain} | Prompts: {len(prompts)} | Model: {args.model}", file=sys.stderr)

    scan_results = {}
    for prompt in prompts:
        result = scan_prompt(prompt, args.domain, args.runs, args.model,
                             args.concurrency, api_key)
        scan_results[prompt] = result

    scan_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": args.domain,
        "model": args.model,
        "runs_per_prompt": args.runs,
        "results": scan_results,
    }
    data["scans"].append(scan_entry)
    save_data(data, args.data_file)

    scan_num = len(data["scans"])
    print(f"\nScan complete: {len(prompts)} prompts × {args.runs} runs", file=sys.stderr)
    print(f"Saved to {args.data_file} (scan #{scan_num})", file=sys.stderr)

    print(f"\nQuick Results ({args.domain}):")
    for prompt, result in scan_results.items():
        mr = result.get("mention_rate", 0)
        cr = result.get("citation_rate", 0)
        print(f"  \"{prompt}\":")
        print(f"    Mention: {mr}% | Citation: {cr}%")


def cmd_report(args):
    """Generate a decay analysis report from historical data."""
    if not os.path.exists(args.data_file):
        print(f"Error: data file not found: {args.data_file}", file=sys.stderr)
        sys.exit(1)

    data = load_data(args.data_file)
    scans = data.get("scans", [])

    if not scans:
        print("No scan data found.", file=sys.stderr)
        sys.exit(1)

    prompt_series = defaultdict(list)
    domains_seen = set()

    for scan in scans:
        ts = scan["timestamp"]
        domain = scan.get("domain", "unknown")
        domains_seen.add(domain)
        for prompt, result in scan.get("results", {}).items():
            prompt_series[prompt].append({
                "timestamp": ts,
                "citation_rate": result.get("citation_rate", 0),
                "mention_rate": result.get("mention_rate", 0),
                "cited_urls": result.get("cited_urls", {}),
                "successful_runs": result.get("successful_runs", 0),
            })

    prompt_analysis = {}
    for prompt, series in prompt_series.items():
        if len(series) < 2:
            prompt_analysis[prompt] = {
                "data_points": len(series),
                "latest_citation_rate": series[-1]["citation_rate"] if series else 0,
                "latest_mention_rate": series[-1]["mention_rate"] if series else 0,
                "trend": "insufficient_data",
                "urgency": "UNKNOWN",
                "note": "Need at least 2 scans to detect trends",
            }
            continue

        first = series[0]
        latest = series[-1]
        cr_first = first["citation_rate"]
        cr_latest = latest["citation_rate"]
        cr_diff = cr_latest - cr_first

        try:
            d1 = datetime.fromisoformat(first["timestamp"].replace("Z", "+00:00"))
            d2 = datetime.fromisoformat(latest["timestamp"].replace("Z", "+00:00"))
            weeks = max(1, (d2 - d1).days // 7)
        except Exception:
            weeks = 1

        if cr_diff < -20:
            trend = "rapid_decline"
        elif cr_diff < -5:
            trend = "declining"
        elif cr_diff > 20:
            trend = "rapid_growth"
        elif cr_diff > 5:
            trend = "growing"
        else:
            trend = "stable"

        if trend in ("rapid_decline",) and cr_first > 30:
            urgency = "HIGH"
            est_weeks = None
            if cr_diff != 0:
                rate_per_week = cr_diff / weeks if weeks > 0 else cr_diff
                if rate_per_week < 0 and cr_latest > 0:
                    est_weeks = round(-cr_latest / rate_per_week)
            note = f"Citation rate dropped from {cr_first}% to {cr_latest}% over {weeks} weeks."
            if est_weeks:
                note += f" At this rate, citations may reach 0 in ~{est_weeks} weeks."
        elif trend == "declining":
            urgency = "MEDIUM"
            note = f"Citation rate declined from {cr_first}% to {cr_latest}% over {weeks} weeks."
        elif trend == "stable":
            urgency = "LOW"
            note = f"Citation rate stable at {cr_latest}% (was {cr_first}%)."
        else:
            urgency = "LOW"
            note = f"Citation rate {trend}: {cr_first}% → {cr_latest}% over {weeks} weeks."

        url_timeline = defaultdict(list)
        for entry in series:
            for url, count in entry.get("cited_urls", {}).items():
                url_timeline[url].append(count)

        prompt_analysis[prompt] = {
            "data_points": len(series),
            "first_citation_rate": cr_first,
            "latest_citation_rate": cr_latest,
            "change": cr_diff,
            "first_mention_rate": first["mention_rate"],
            "latest_mention_rate": latest["mention_rate"],
            "weeks_tracked": weeks,
            "trend": trend,
            "urgency": urgency,
            "note": note,
            "rates_over_time": [
                {"timestamp": e["timestamp"][:10], "citation_rate": e["citation_rate"],
                 "mention_rate": e["mention_rate"]}
                for e in series
            ],
            "cited_urls": dict(url_timeline),
        }

    urgency_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3}
    sorted_prompts = sorted(
        prompt_analysis.items(),
        key=lambda x: (urgency_order.get(x[1]["urgency"], 9), -abs(x[1].get("change", 0)))
    )

    high_count = sum(1 for _, a in sorted_prompts if a["urgency"] == "HIGH")
    medium_count = sum(1 for _, a in sorted_prompts if a["urgency"] == "MEDIUM")
    declining_prompts = [p for p, a in sorted_prompts if a.get("trend", "").endswith("decline") or a.get("trend") == "declining"]

    report = {
        "data_file": args.data_file,
        "total_scans": len(scans),
        "domains": list(domains_seen),
        "date_range": {
            "first": scans[0]["timestamp"][:10],
            "last": scans[-1]["timestamp"][:10],
        },
        "prompts_analyzed": len(prompt_analysis),
        "urgency_summary": {
            "high": high_count,
            "medium": medium_count,
            "declining_prompts": len(declining_prompts),
        },
        "prompt_analysis": dict(sorted_prompts),
    }

    if args.output == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_report_text(report))


def format_report_text(report: dict) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("Freshness Decay Tracker — Report")
    lines.append(f"Data: {report['data_file']} ({report['total_scans']} scans)")
    dr = report["date_range"]
    lines.append(f"Period: {dr['first']} → {dr['last']}")
    lines.append(f"Domain(s): {', '.join(report['domains'])}")
    lines.append("=" * 70)

    us = report["urgency_summary"]
    lines.append("")
    lines.append("REFRESH URGENCY SUMMARY:")
    lines.append(f"  🔴 HIGH:   {us['high']} prompts — content losing citations fast")
    lines.append(f"  🟡 MEDIUM: {us['medium']} prompts — gradual decline")
    lines.append(f"  Declining: {us['declining_prompts']} of {report['prompts_analyzed']} prompts")

    lines.append("")
    lines.append("PROMPT-BY-PROMPT ANALYSIS:")
    lines.append("=" * 70)

    for prompt, analysis in report["prompt_analysis"].items():
        icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "UNKNOWN": "⚪"}.get(
            analysis["urgency"], "⚪")

        lines.append(f"\n{icon} \"{prompt}\"")
        lines.append(f"  Urgency: {analysis['urgency']} | Trend: {analysis['trend']}")
        lines.append(f"  {analysis['note']}")

        if analysis.get("rates_over_time"):
            lines.append(f"  Timeline:")
            for entry in analysis["rates_over_time"]:
                lines.append(f"    {entry['timestamp']}: citation {entry['citation_rate']}% | mention {entry['mention_rate']}%")

        if analysis.get("cited_urls"):
            lines.append(f"  Cited URLs:")
            for url, counts in list(analysis["cited_urls"].items())[:3]:
                counts_str = " → ".join(str(c) for c in counts)
                lines.append(f"    {url}")
                lines.append(f"      Counts across scans: {counts_str}")

    lines.append("")
    lines.append("PAGES MOST IN NEED OF REFRESH:")
    lines.append("=" * 70)

    refresh_candidates = []
    for prompt, analysis in report["prompt_analysis"].items():
        if analysis["urgency"] in ("HIGH", "MEDIUM"):
            for url in analysis.get("cited_urls", {}).keys():
                refresh_candidates.append({
                    "url": url,
                    "prompt": prompt,
                    "urgency": analysis["urgency"],
                    "change": analysis.get("change", 0),
                })

    if refresh_candidates:
        seen_urls = {}
        for rc in refresh_candidates:
            if rc["url"] not in seen_urls or \
               {"HIGH": 0, "MEDIUM": 1}.get(rc["urgency"], 2) < \
               {"HIGH": 0, "MEDIUM": 1}.get(seen_urls[rc["url"]]["urgency"], 2):
                seen_urls[rc["url"]] = rc

        for url, rc in sorted(seen_urls.items(),
                               key=lambda x: {"HIGH": 0, "MEDIUM": 1}.get(x[1]["urgency"], 2)):
            icon = "🔴" if rc["urgency"] == "HIGH" else "🟡"
            lines.append(f"  {icon} {url}")
            lines.append(f"    Prompt: \"{rc['prompt']}\" | Change: {rc['change']:+d}%")
    else:
        lines.append("  No urgent refresh needed — all prompts are stable or growing.")

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Track how citation rates change over time — detect content freshness decay"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Run a freshness scan")
    scan_parser.add_argument("--domain", required=True, help="Domain to track")
    scan_parser.add_argument("--prompts", nargs="+", help="Prompts to scan")
    scan_parser.add_argument("--prompts-file", help="File with one prompt per line")
    scan_parser.add_argument("--data-file", default="freshness.json",
                             help="Data file path (default: freshness.json)")
    scan_parser.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                             help="Runs per prompt (default: 20)")
    scan_parser.add_argument("--model", default=DEFAULT_MODEL,
                             help="Gemini model (default: gemini-3-flash-preview)")
    scan_parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                             help="Max concurrent requests (default: 5)")

    report_parser = subparsers.add_parser("report", help="Analyze decay patterns")
    report_parser.add_argument("--data-file", default="freshness.json",
                               help="Data file path (default: freshness.json)")
    report_parser.add_argument("--output", choices=["text", "json"], default="text",
                               help="Output format (default: text)")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()
