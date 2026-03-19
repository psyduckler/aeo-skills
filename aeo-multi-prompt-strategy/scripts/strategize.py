#!/usr/bin/env python3
"""
Multi-Prompt Strategy — Find pages that win across multiple prompts (authority hubs).
Cross-references citation data across prompts to identify hub pages and recommend
content consolidation strategies.

Usage:
    python3 strategize.py "prompt1" "prompt2" "prompt3" [--prompts-file file.txt] [--domain example.com] [--runs 20] [--model gemini-3-flash-preview] [--concurrency 5] [--output text|json]

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


# ── Core Logic ──────────────────────────────────────────────────────────────

def scan_prompt(prompt: str, runs: int, model: str, concurrency: int,
                api_key: str) -> dict:
    """Run a single prompt and collect citation data."""
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
        return {"successful_runs": 0, "errors": errors, "urls": {}, "domains": {}}

    # Count URL and domain citations
    url_cite_count = defaultdict(int)
    url_titles = {}
    domain_cite_count = defaultdict(int)

    for sources in run_results:
        seen_domains = set()
        seen_urls = set()
        for src in sources:
            uri = src["uri"]
            d = get_domain(uri)

            if uri not in seen_urls:
                url_cite_count[uri] += 1
                seen_urls.add(uri)
                if uri not in url_titles and src.get("title"):
                    url_titles[uri] = src["title"]

            if d and d not in seen_domains:
                domain_cite_count[d] += 1
                seen_domains.add(d)

    url_data = {
        url: {
            "citation_rate": round(count / successful_runs * 100),
            "citation_count": count,
            "title": url_titles.get(url, ""),
            "domain": get_domain(url),
        }
        for url, count in url_cite_count.items()
    }

    domain_data = {
        d: {
            "citation_rate": round(count / successful_runs * 100),
            "citation_count": count,
        }
        for d, count in domain_cite_count.items()
    }

    return {
        "successful_runs": successful_runs,
        "errors": errors,
        "urls": url_data,
        "domains": domain_data,
    }


def run_strategy(prompts: list, runs: int, model: str, concurrency: int,
                 domain: str = None):
    """Run all prompts and build cross-prompt strategy analysis."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)

    print(f"Multi-Prompt Strategy", file=sys.stderr)
    print(f"Prompts: {len(prompts)} | Model: {model} | Runs per prompt: {runs}", file=sys.stderr)
    if domain:
        print(f"Domain focus: {domain}", file=sys.stderr)

    # Scan each prompt
    prompt_results = {}
    for prompt in prompts:
        result = scan_prompt(prompt, runs, model, concurrency, api_key)
        prompt_results[prompt] = result

    total_prompts = len(prompts)

    # Build cross-prompt matrix: URL -> which prompts cite it
    url_prompt_map = defaultdict(lambda: {"prompts": {}, "title": "", "domain": ""})
    domain_prompt_map = defaultdict(lambda: {"prompts": {}})

    for prompt, result in prompt_results.items():
        for url, data in result["urls"].items():
            url_prompt_map[url]["prompts"][prompt] = data["citation_rate"]
            if not url_prompt_map[url]["title"] and data.get("title"):
                url_prompt_map[url]["title"] = data["title"]
            url_prompt_map[url]["domain"] = data["domain"]

        for d, data in result["domains"].items():
            domain_prompt_map[d]["prompts"][prompt] = data["citation_rate"]

    # Identify authority hubs (URLs cited for 2+ prompts)
    authority_hubs = []
    for url, data in url_prompt_map.items():
        prompt_count = len(data["prompts"])
        if prompt_count >= 2:
            avg_rate = round(sum(data["prompts"].values()) / prompt_count)
            authority_hubs.append({
                "url": url,
                "title": data["title"],
                "domain": data["domain"],
                "prompts_cited": prompt_count,
                "total_prompts": total_prompts,
                "hub_score": round(prompt_count / total_prompts * 100),
                "avg_citation_rate": avg_rate,
                "per_prompt": data["prompts"],
            })

    authority_hubs.sort(key=lambda x: (-x["prompts_cited"], -x["avg_citation_rate"]))

    # Domain-level cross-prompt presence
    domain_hubs = []
    for d, data in domain_prompt_map.items():
        prompt_count = len(data["prompts"])
        if prompt_count >= 2:
            avg_rate = round(sum(data["prompts"].values()) / prompt_count)
            domain_hubs.append({
                "domain": d,
                "prompts_cited": prompt_count,
                "total_prompts": total_prompts,
                "hub_score": round(prompt_count / total_prompts * 100),
                "avg_citation_rate": avg_rate,
                "per_prompt": data["prompts"],
            })

    domain_hubs.sort(key=lambda x: (-x["prompts_cited"], -x["avg_citation_rate"]))

    # Single-prompt winners (URLs cited for only 1 prompt but at high rate)
    single_winners = []
    for url, data in url_prompt_map.items():
        if len(data["prompts"]) == 1:
            prompt_name = list(data["prompts"].keys())[0]
            rate = list(data["prompts"].values())[0]
            if rate >= 30:  # Only notable single-prompt winners
                single_winners.append({
                    "url": url,
                    "title": data["title"],
                    "domain": data["domain"],
                    "prompt": prompt_name,
                    "citation_rate": rate,
                })

    single_winners.sort(key=lambda x: -x["citation_rate"])

    # Domain-specific analysis
    domain_analysis = None
    if domain:
        target = domain.lower()
        if target.startswith("www."):
            target = target[4:]

        my_hubs = [h for h in authority_hubs if target in h["domain"]]
        my_singles = [s for s in single_winners if target in s["domain"]]

        # Prompts where domain is absent
        absent_prompts = []
        for prompt, result in prompt_results.items():
            domain_cited = any(target in d for d in result["domains"].keys())
            if not domain_cited:
                absent_prompts.append(prompt)

        # Strategy recommendations
        recommendations = []

        if my_hubs:
            best_hub = my_hubs[0]
            recommendations.append(
                f"Your best hub page ({best_hub['url']}) is cited for "
                f"{best_hub['prompts_cited']}/{total_prompts} prompts. "
                f"Strengthen this page to maintain its authority hub status."
            )

        if my_singles and not my_hubs:
            recommendations.append(
                f"You have {len(my_singles)} single-prompt winners but no authority hubs. "
                f"Consider creating a comprehensive hub page that covers multiple prompts "
                f"instead of separate pages for each."
            )

        if my_singles and my_hubs:
            for s in my_singles[:3]:
                # Check if any hub covers a similar topic
                recommendations.append(
                    f"Single-prompt winner ({s['url']}) only wins \"{s['prompt']}\" — "
                    f"consider expanding a hub page to also cover this prompt."
                )

        if absent_prompts:
            recommendations.append(
                f"You're not cited for {len(absent_prompts)} of {total_prompts} prompts: "
                + "; ".join(f'"{p}"' for p in absent_prompts[:3])
                + (f" and {len(absent_prompts) - 3} more" if len(absent_prompts) > 3 else "")
                + ". Study the authority hubs that win these prompts for content inspiration."
            )

        if not my_hubs and not my_singles:
            recommendations.append(
                f"{domain} is not cited for any of the {total_prompts} prompts. "
                f"Start by targeting the prompt where competition is lowest, "
                f"then expand to build an authority hub."
            )

        domain_analysis = {
            "domain": domain,
            "hub_pages": my_hubs,
            "single_winners": my_singles,
            "absent_prompts": absent_prompts,
            "recommendations": recommendations,
        }

    result = {
        "model": model,
        "runs_per_prompt": runs,
        "total_prompts": total_prompts,
        "prompts": prompts,
        "prompt_results": {
            p: {
                "successful_runs": r["successful_runs"],
                "top_domains": sorted(
                    [{"domain": d, **data} for d, data in r["domains"].items()],
                    key=lambda x: -x["citation_rate"]
                )[:5],
            }
            for p, r in prompt_results.items()
        },
        "authority_hubs": authority_hubs[:20],
        "domain_hubs": domain_hubs[:15],
        "single_prompt_winners": single_winners[:15],
        "domain_analysis": domain_analysis,
    }

    return result


def format_text(result: dict) -> str:
    """Format results as human-readable text."""
    lines = []
    lines.append("Multi-Prompt Strategy")
    lines.append(f"Model: {result['model']} | Runs per prompt: {result['runs_per_prompt']}")
    lines.append(f"Prompts analyzed: {result['total_prompts']}")
    lines.append("")

    # Per-prompt summary
    lines.append("PER-PROMPT TOP DOMAINS:")
    lines.append("=" * 70)
    for prompt, data in result["prompt_results"].items():
        lines.append(f"\n  \"{prompt}\" ({data['successful_runs']} runs):")
        for d in data["top_domains"]:
            lines.append(f"    {d['citation_rate']}% — {d['domain']}")

    # Authority Hubs (URL-level)
    if result["authority_hubs"]:
        lines.append("")
        lines.append("AUTHORITY HUB PAGES (cited for 2+ prompts):")
        lines.append("=" * 70)
        for hub in result["authority_hubs"]:
            lines.append(f"\n  🏆 {hub['url']}")
            if hub.get("title"):
                lines.append(f"     Title: {hub['title']}")
            lines.append(f"     Hub score: {hub['hub_score']}% ({hub['prompts_cited']}/{hub['total_prompts']} prompts)")
            lines.append(f"     Avg citation rate: {hub['avg_citation_rate']}%")
            lines.append(f"     Per prompt:")
            for prompt, rate in sorted(hub["per_prompt"].items(), key=lambda x: -x[1]):
                lines.append(f"       {rate}% — \"{prompt}\"")
    else:
        lines.append("")
        lines.append("No authority hub pages found (no URL cited for 2+ prompts).")

    # Domain Hubs
    if result["domain_hubs"]:
        lines.append("")
        lines.append("AUTHORITY HUB DOMAINS (present for 2+ prompts):")
        lines.append("=" * 70)
        for hub in result["domain_hubs"][:10]:
            prompts_str = f"{hub['prompts_cited']}/{hub['total_prompts']} prompts"
            lines.append(f"  {hub['hub_score']:3d}% — {hub['domain']} ({prompts_str}, avg {hub['avg_citation_rate']}%)")

    # Single-prompt winners
    if result["single_prompt_winners"]:
        lines.append("")
        lines.append("SINGLE-PROMPT WINNERS (high rate, but only one prompt):")
        lines.append("=" * 70)
        for sw in result["single_prompt_winners"][:10]:
            lines.append(f"  {sw['citation_rate']}% — {sw['domain']}: {sw['url']}")
            lines.append(f"         Only wins: \"{sw['prompt']}\"")

    # Domain analysis
    da = result.get("domain_analysis")
    if da:
        lines.append("")
        lines.append(f"DOMAIN STRATEGY: {da['domain']}")
        lines.append("=" * 70)

        if da["hub_pages"]:
            lines.append(f"  Authority hub pages ({len(da['hub_pages'])}):")
            for hub in da["hub_pages"]:
                lines.append(f"    🏆 {hub['url']}")
                lines.append(f"       {hub['prompts_cited']}/{hub['total_prompts']} prompts, avg {hub['avg_citation_rate']}%")
        else:
            lines.append(f"  Authority hub pages: None")

        if da["single_winners"]:
            lines.append(f"  Single-prompt winners ({len(da['single_winners'])}):")
            for sw in da["single_winners"]:
                lines.append(f"    {sw['citation_rate']}% — {sw['url']} (only \"{sw['prompt']}\")")
        else:
            lines.append(f"  Single-prompt winners: None")

        if da["absent_prompts"]:
            lines.append(f"  Not cited for ({len(da['absent_prompts'])} prompts):")
            for p in da["absent_prompts"]:
                lines.append(f"    ✗ \"{p}\"")

        if da["recommendations"]:
            lines.append(f"\n  RECOMMENDATIONS:")
            for i, rec in enumerate(da["recommendations"], 1):
                lines.append(f"    {i}. {rec}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Find authority hub pages cited across multiple prompts — optimize one page to win many"
    )
    parser.add_argument("prompts", nargs="*", help="Prompts to analyze (3+ recommended)")
    parser.add_argument("--prompts-file",
                        help="File with one prompt per line (combined with positional)")
    parser.add_argument("--domain",
                        help="Domain to analyze (e.g., example.com)")
    parser.add_argument("--runs", type=int, default=20,
                        help="Runs per prompt (default: 20)")
    parser.add_argument("--model", default="gemini-3-flash-preview",
                        help="Gemini model (default: gemini-3-flash-preview)")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="Max concurrent requests (default: 5)")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    args = parser.parse_args()

    # Collect prompts
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

    if len(all_prompts) < 2:
        print("Error: at least 2 prompts required (3+ recommended for meaningful analysis)", file=sys.stderr)
        sys.exit(1)

    result = run_strategy(all_prompts, args.runs, args.model, args.concurrency, args.domain)

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
