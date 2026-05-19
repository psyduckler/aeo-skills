#!/usr/bin/env python3
"""
aeo-report — Read accumulated aeo-baseline evidence files and produce a
visibility report with trends, decay detection, cannibalization analysis,
hub-page identification, and competitor share-of-voice changes.

Reads:  ./aeo-data/*.json  (or --data-dir DIR)
Writes: ./aeo-reports/<timestamp>.md + .html

Usage:
    python3 report.py                            # default paths
    python3 report.py --data-dir aeo-data --output-dir aeo-reports
    python3 report.py --format md                # markdown only
    python3 report.py --format html              # html only
    python3 report.py --format all               # both (default)

This skill never calls a provider API — it's pure analysis over local files.
"""
from __future__ import annotations

import argparse
import glob
import html
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

SCHEMA_VERSION = "aeo-evidence-v1"
DEFAULT_DATA_DIR = "aeo-data"
DEFAULT_OUTPUT_DIR = "aeo-reports"

# Decay threshold: trailing 3-run citation rate must drop by this fraction
# below the leading 3-run rate to be flagged.
DECAY_THRESHOLD_FRACTION = 0.20
DECAY_MIN_RUNS = 4

# Hub-page threshold: a URL must be cited for at least this fraction of
# tracked prompts in the latest run to count as a hub.
HUB_PAGE_MIN_PROMPTS = 2
HUB_PAGE_MIN_FRACTION = 0.30


# ── Domain matching ─────────────────────────────────────────────────────────

def domain_matches_brand(citation_domain: str, brand_domain: str) -> bool:
    """Exact match OR subdomain match. NOT a substring match.

    'tabiji.ai' matches 'tabiji.ai' and 'www.tabiji.ai' and 'blog.tabiji.ai'.
    'tabiji.ai' does NOT match 'notabiji.ai' or 'tabiji.ai.attacker.com'.
    """
    if not citation_domain or not brand_domain:
        return False
    cd = citation_domain.lower().lstrip(".")
    bd = brand_domain.lower().lstrip(".")
    return cd == bd or cd.endswith("." + bd)


# ── Evidence Loading ───────────────────────────────────────────────────────

def load_evidence_files(data_dir: str) -> list[dict]:
    """Load every aeo-evidence-v1 file from the data dir, sorted by timestamp."""
    paths = sorted(glob.glob(os.path.join(data_dir, "*.json")))
    out = []
    for p in paths:
        try:
            with open(p) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠ Skipping {p}: {e}", file=sys.stderr)
            continue
        if data.get("schema_version") != SCHEMA_VERSION:
            print(f"⚠ Skipping {p}: schema_version {data.get('schema_version')!r} != {SCHEMA_VERSION!r}", file=sys.stderr)
            continue
        out.append(data)
    out.sort(key=lambda d: d["run"]["timestamp"])
    return out


def group_by_prompt(evidence: list[dict]) -> dict[str, list[tuple[dict, dict]]]:
    """Return {prompt_id: [(run_meta, prompt_result), ...]} ordered by timestamp."""
    by_prompt: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for ev in evidence:
        run = ev["run"]
        for p in ev["prompts"]:
            by_prompt[p["prompt_id"]].append((run, p))
    return dict(by_prompt)


# ── Trend Analysis ─────────────────────────────────────────────────────────

def trend_arrow(prev: float | None, curr: float | None, eps: float = 0.02) -> str:
    """Return ↑ / ↓ / → based on direction. eps is the noise threshold."""
    if prev is None or curr is None:
        return "—"
    delta = curr - prev
    if delta > eps:
        return "↑"
    if delta < -eps:
        return "↓"
    return "→"


def series(history: list[tuple[dict, dict]], path: list[str]) -> list[float | None]:
    """Pull a metric path from each (run, prompt_result) pair, e.g.
    series(history, ['aggregates', 'mention_rate']) → [0.55, 0.6, ...]"""
    out = []
    for _, p in history:
        node = p
        for key in path:
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        out.append(node if isinstance(node, (int, float)) else None)
    return out


def detect_decay(history: list[tuple[dict, dict]], metric_path: list[str]) -> dict | None:
    """Flag a metric that has materially declined in the trailing runs.

    Compare mean of last 3 with mean of first 3 (need ≥ DECAY_MIN_RUNS runs).
    Returns {trailing_mean, leading_mean, delta_fraction, severity} if decayed,
    else None.
    """
    values = [v for v in series(history, metric_path) if v is not None]
    if len(values) < DECAY_MIN_RUNS:
        return None
    leading = sum(values[:3]) / 3
    trailing = sum(values[-3:]) / 3
    if leading == 0:
        return None
    delta_frac = (leading - trailing) / leading
    if delta_frac < DECAY_THRESHOLD_FRACTION:
        return None
    severity = "HIGH" if delta_frac > 0.5 else "MEDIUM" if delta_frac > 0.3 else "LOW"
    return {
        "leading_mean": round(leading, 4),
        "trailing_mean": round(trailing, 4),
        "delta_fraction": round(delta_frac, 4),
        "severity": severity,
    }


def detect_cannibalization(history: list[tuple[dict, dict]], brand_domain: str) -> dict | None:
    """For a single prompt's history: if multiple URLs from the brand's domain
    are cited across recent samples (the brand's own pages compete), flag it.

    Looks at the most recent run's samples.
    """
    if not history:
        return None
    _, p = history[-1]
    brand_url_counts: dict[str, int] = defaultdict(int)
    for sample in p.get("samples", []):
        seen_in_sample = set()
        for cit in sample.get("citations", []):
            if not isinstance(cit, dict):
                continue
            if domain_matches_brand(cit.get("domain", ""), brand_domain):
                url = cit.get("url", "")
                if url and url not in seen_in_sample:
                    brand_url_counts[url] += 1
                    seen_in_sample.add(url)
    distinct_urls = {url: count for url, count in brand_url_counts.items() if count >= 2}
    if len(distinct_urls) < 2:
        return None
    total = sum(distinct_urls.values())
    leader_url, leader_count = max(distinct_urls.items(), key=lambda kv: kv[1])
    leader_share = leader_count / total if total else 0
    severity = "HIGH" if leader_share < 0.5 else "MEDIUM" if leader_share < 0.7 else "LOW"
    return {
        "urls": distinct_urls,
        "leader_url": leader_url,
        "leader_share": round(leader_share, 4),
        "severity": severity,
    }


def detect_hub_pages(by_prompt: dict[str, list[tuple[dict, dict]]], brand_domain: str) -> list[dict]:
    """Find URLs from the brand's domain that win citations across multiple prompts.

    A URL is a "hub" if it's cited in the latest run for >= HUB_PAGE_MIN_PROMPTS prompts.
    """
    url_prompts: dict[str, set[str]] = defaultdict(set)
    total_prompts = len(by_prompt)
    for prompt_id, history in by_prompt.items():
        if not history:
            continue
        _, p = history[-1]
        seen_urls_for_prompt = set()
        for sample in p.get("samples", []):
            for cit in sample.get("citations", []):
                if not isinstance(cit, dict):
                    continue
                url = cit.get("url", "")
                if url and domain_matches_brand(cit.get("domain", ""), brand_domain):
                    seen_urls_for_prompt.add(url)
        for url in seen_urls_for_prompt:
            url_prompts[url].add(prompt_id)

    hubs = []
    for url, prompts in url_prompts.items():
        if len(prompts) >= HUB_PAGE_MIN_PROMPTS and (
            total_prompts == 0 or len(prompts) / total_prompts >= HUB_PAGE_MIN_FRACTION
        ):
            hubs.append({
                "url": url,
                "prompt_count": len(prompts),
                "prompts": sorted(prompts),
                "coverage": round(len(prompts) / total_prompts, 4) if total_prompts else 0,
            })
    hubs.sort(key=lambda h: (-h["prompt_count"], h["url"]))
    return hubs


def competitor_share_changes(history: list[tuple[dict, dict]]) -> list[dict]:
    """For one prompt: show competitor share-of-voice trend across runs."""
    if len(history) < 2:
        return []
    first_run = history[0][1].get("aggregates", {}).get("competitor_share", {})
    last_run = history[-1][1].get("aggregates", {}).get("competitor_share", {})
    all_competitors = set(first_run) | set(last_run)
    changes = []
    for c in all_competitors:
        old = first_run.get(c, 0.0)
        new = last_run.get(c, 0.0)
        if abs(new - old) > 0.05:  # >5pp shift to flag
            changes.append({
                "competitor": c,
                "first_run_rate": round(old, 4),
                "latest_rate": round(new, 4),
                "delta": round(new - old, 4),
            })
    changes.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return changes


# ── SVG Chart Generation ───────────────────────────────────────────────────

def svg_line_chart(
    label: str,
    points: list[tuple[float, float | None]],
    y_max: float = 1.0,
    y_label: str = "rate",
    width: int = 600,
    height: int = 240,
) -> str:
    """Render a simple SVG line chart. Points: list of (x, y) where y can be None.

    x values are positional indices 0..N-1 normalized to the chart width.
    """
    pad_l, pad_r, pad_t, pad_b = 50, 20, 30, 40
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    if not points:
        return f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"><text x="20" y="30" font-family="sans-serif" font-size="14">No data</text></svg>'

    n = len(points)
    xs = [pad_l + (i / max(n - 1, 1)) * chart_w for i in range(n)]
    ys = []
    for i in range(n):
        y_val = points[i][1]
        if y_val is None:
            ys.append(None)
        else:
            y_norm = min(max(y_val / y_max, 0.0), 1.0)
            ys.append(pad_t + (1 - y_norm) * chart_h)

    # Build path string, splitting on None gaps
    path_segs = []
    current_seg: list[str] = []
    for i in range(n):
        if ys[i] is None:
            if current_seg:
                path_segs.append(" ".join(current_seg))
                current_seg = []
            continue
        prefix = "M" if not current_seg else "L"
        current_seg.append(f"{prefix} {xs[i]:.1f} {ys[i]:.1f}")
    if current_seg:
        path_segs.append(" ".join(current_seg))

    paths_svg = "".join(f'<path d="{seg}" fill="none" stroke="#0066cc" stroke-width="2"/>' for seg in path_segs)

    # Points
    points_svg = "".join(
        f'<circle cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="3" fill="#0066cc"/>'
        for i in range(n) if ys[i] is not None
    )

    # Gridlines
    gridlines = []
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + (1 - frac) * chart_h
        v = frac * y_max
        gridlines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" stroke="#eee"/>')
        gridlines.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" font-family="sans-serif" font-size="10" text-anchor="end" fill="#666">{v:.2f}</text>')
    grid_svg = "".join(gridlines)

    # X axis labels: show first, middle, last
    label_indices = sorted({0, n // 2, n - 1}) if n > 1 else [0]
    x_labels = []
    for i in label_indices:
        x_labels.append(
            f'<text x="{xs[i]:.1f}" y="{height - pad_b + 18}" font-family="sans-serif" '
            f'font-size="10" text-anchor="middle" fill="#666">{points[i][0]}</text>'
        )
    x_labels_svg = "".join(x_labels)

    title = (
        f'<text x="{width / 2:.0f}" y="18" font-family="sans-serif" font-size="13" '
        f'text-anchor="middle" fill="#333">{html.escape(label)}</text>'
    )
    y_axis_label = (
        f'<text x="14" y="{pad_t + chart_h / 2:.0f}" font-family="sans-serif" font-size="11" '
        f'text-anchor="middle" fill="#666" transform="rotate(-90 14 {pad_t + chart_h / 2:.0f})">'
        f'{html.escape(y_label)}</text>'
    )

    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'{title}{y_axis_label}{grid_svg}{paths_svg}{points_svg}{x_labels_svg}</svg>'
    )


def short_date(iso_timestamp: str) -> str:
    """ISO 8601 → MM-DD short label."""
    try:
        return iso_timestamp[5:10]  # MM-DD slice from YYYY-MM-DDT...
    except (TypeError, IndexError):
        return ""


# ── Markdown Rendering ─────────────────────────────────────────────────────

def format_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.0f}%"


def format_ci(ci: list | None) -> str:
    if not ci or len(ci) != 2:
        return ""
    return f" ({ci[0] * 100:.0f}–{ci[1] * 100:.0f}%)"


def render_markdown(evidence: list[dict], by_prompt: dict[str, list[tuple[dict, dict]]]) -> tuple[str, dict[str, str]]:
    """Build the Markdown report. Returns (markdown, charts_by_id).

    charts_by_id holds SVG strings keyed by an ID we reference from the Markdown.
    The HTML rendering pass substitutes these in; the Markdown rendering uses
    placeholders like `[chart: prompt_id]`.
    """
    if not evidence:
        return "# AEO Visibility Report\n\nNo evidence files found.\n", {}

    workspace = evidence[-1]["workspace"]
    brand = workspace.get("brand", "Unknown")
    brand_domain = (workspace.get("domain") or "").lower()
    first_ts = evidence[0]["run"]["timestamp"]
    last_ts = evidence[-1]["run"]["timestamp"]
    n_runs = len(evidence)
    n_prompts = len(by_prompt)
    charts: dict[str, str] = {}

    lines = [
        f"# AEO Visibility Report — {brand}",
        "",
        f"**Brand:** {brand} ({workspace.get('domain', '')})  ",
        f"**Date range:** {first_ts} → {last_ts}  ",
        f"**Runs:** {n_runs} baseline run(s)  ",
        f"**Prompts tracked:** {n_prompts}  ",
        f"**Methodology:** {evidence[-1]['run'].get('methodology_version', 'aeo-v1')}  ",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
    ]

    # Mean visibility score across prompts in the latest run
    latest_scores: list[float] = []
    for hist in by_prompt.values():
        if not hist:
            continue
        vs = hist[-1][1].get("visibility_score", {})
        val = vs.get("value")
        if isinstance(val, (int, float)):
            latest_scores.append(val)

    mean_score = sum(latest_scores) / len(latest_scores) if latest_scores else 0.0
    lines.append(f"- **Average visibility score (latest run):** {mean_score:.1f}/100 across {len(latest_scores)} prompt(s)")

    # Trend in mean score if multiple runs
    if n_runs >= 2:
        # Mean of first-run scores
        first_scores = []
        for hist in by_prompt.values():
            for run_ts, p in hist:
                if run_ts["timestamp"] == evidence[0]["run"]["timestamp"]:
                    val = p.get("visibility_score", {}).get("value")
                    if isinstance(val, (int, float)):
                        first_scores.append(val)
                    break
        if first_scores:
            first_mean = sum(first_scores) / len(first_scores)
            arrow = trend_arrow(first_mean, mean_score, eps=1.0)
            delta = mean_score - first_mean
            lines.append(f"- **Trend since first run:** {arrow} ({delta:+.1f} points; {first_mean:.1f} → {mean_score:.1f})")

    # Decay alerts across all prompts
    decayed = []
    for prompt_id, hist in by_prompt.items():
        d = detect_decay(hist, ["aggregates", "citation_rate"])
        if d:
            decayed.append((prompt_id, d))
    if decayed:
        lines.append(f"- **Decay alerts:** {len(decayed)} prompt(s) with declining citation rate")

    # Hub-page opportunities
    hubs = detect_hub_pages(by_prompt, brand_domain) if brand_domain else []
    if hubs:
        lines.append(f"- **Hub-page candidates:** {len(hubs)} URL(s) cited across multiple prompts")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-prompt detail
    lines.append("## Per-Prompt Detail")
    lines.append("")
    for prompt_id in sorted(by_prompt.keys()):
        hist = by_prompt[prompt_id]
        if not hist:
            continue
        latest_run, latest_p = hist[-1]
        text = latest_p.get("prompt_text", prompt_id)
        intent = latest_p.get("intent", "—")
        agg = latest_p.get("aggregates", {})
        vs = latest_p.get("visibility_score", {})

        lines.append(f"### {prompt_id}")
        lines.append("")
        lines.append(f"> {text}")
        lines.append("")
        lines.append(f"- **Intent:** {intent}")
        lines.append(f"- **Visibility score:** {vs.get('value', 0):.1f}/100")
        mention = agg.get("mention_rate")
        mention_ci = agg.get("mention_rate_ci")
        cite = agg.get("citation_rate")
        cite_ci = agg.get("citation_rate_ci")
        pos = agg.get("avg_citation_position")
        lines.append(f"- **Mention rate:** {format_pct(mention)}{format_ci(mention_ci)}")
        lines.append(f"- **Citation rate:** {format_pct(cite)}{format_ci(cite_ci)}")
        if pos is not None:
            lines.append(f"- **Avg citation position:** #{pos:.1f}")

        # Trend lines if multi-run
        if len(hist) >= 2:
            chart_id = f"chart-{prompt_id}"
            ts_labels = [short_date(run["timestamp"]) for run, _ in hist]
            score_points = [(ts_labels[i], series(hist, ["visibility_score", "value"])[i]) for i in range(len(hist))]
            charts[chart_id] = svg_line_chart(
                f"{prompt_id}: visibility score over time",
                score_points,
                y_max=100,
                y_label="score (0–100)",
            )
            lines.append("")
            lines.append(f"<!-- chart: {chart_id} -->")

        # Top entities (top 5 from the universe)
        entity_universe = agg.get("entity_universe", {})
        if entity_universe:
            top_entities = sorted(entity_universe.items(), key=lambda kv: -kv[1])[:5]
            ent_str = ", ".join(f"{e} ({c})" for e, c in top_entities)
            lines.append("")
            lines.append(f"- **Top entities:** {ent_str}")

        # Per-prompt decay
        d = detect_decay(hist, ["aggregates", "citation_rate"])
        if d:
            lines.append(
                f"- **⚠ Citation decay ({d['severity']}):** {format_pct(d['leading_mean'])} "
                f"→ {format_pct(d['trailing_mean'])} (–{d['delta_fraction'] * 100:.0f}%)"
            )

        # Cannibalization
        c = detect_cannibalization(hist, brand_domain)
        if c:
            lines.append(
                f"- **⚠ Cannibalization ({c['severity']}):** {len(c['urls'])} owned URLs cited; "
                f"leader = {c['leader_url']} ({c['leader_share'] * 100:.0f}% share)"
            )

        # Competitor share changes
        comp_changes = competitor_share_changes(hist)
        if comp_changes:
            top = comp_changes[:3]
            change_strs = [f"{c['competitor']} {c['first_run_rate'] * 100:.0f}% → {c['latest_rate'] * 100:.0f}%" for c in top]
            lines.append(f"- **Competitor share shifts:** {' | '.join(change_strs)}")

        lines.append("")

    # Cross-prompt sections
    if hubs:
        lines.append("---")
        lines.append("")
        lines.append("## Hub-Page Opportunities")
        lines.append("")
        lines.append("URLs from your domain that get cited across multiple tracked prompts. These are existing pages worth doubling down on.")
        lines.append("")
        for h in hubs:
            lines.append(f"- **{h['url']}** — cited for {h['prompt_count']}/{n_prompts} prompts ({h['coverage'] * 100:.0f}% coverage)")
            lines.append(f"  - Prompts: {', '.join(h['prompts'])}")
        lines.append("")

    # Aggregate decay list
    if decayed:
        lines.append("---")
        lines.append("")
        lines.append("## Decay Alerts")
        lines.append("")
        lines.append("Prompts where the brand's citation rate has materially declined.")
        lines.append("")
        for prompt_id, d in decayed:
            lines.append(
                f"- **{prompt_id}** ({d['severity']}): "
                f"{format_pct(d['leading_mean'])} → {format_pct(d['trailing_mean'])} "
                f"(–{d['delta_fraction'] * 100:.0f}%)"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("All metrics derived from raw responses stored in `aeo-data/`. Reproduce by reading the source evidence files directly. See [METHODOLOGY.md](https://github.com/psyduckler/aeo-skills/blob/main/METHODOLOGY.md) for extraction rules and the visibility score formula.")
    lines.append("")
    lines.append(f"*Report generated by aeo-report against {n_runs} evidence file(s).*")
    lines.append("")
    return "\n".join(lines), charts


# ── HTML Rendering ─────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; max-width: 820px; margin: 2em auto; padding: 0 1em; line-height: 1.55; color: #222; }}
  h1, h2, h3 {{ color: #111; }}
  h1 {{ border-bottom: 2px solid #0066cc; padding-bottom: 0.3em; }}
  h2 {{ border-bottom: 1px solid #eee; padding-bottom: 0.2em; margin-top: 2em; }}
  h3 {{ margin-top: 1.5em; }}
  blockquote {{ border-left: 3px solid #0066cc; margin: 0.5em 0; padding: 0.2em 1em; color: #555; }}
  code {{ background: #f4f4f4; padding: 0.1em 0.3em; border-radius: 3px; font-size: 0.92em; }}
  ul {{ margin: 0.4em 0; }}
  li {{ margin: 0.2em 0; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 2em 0; }}
  .chart {{ margin: 0.8em 0; }}
  .warn {{ color: #b30000; }}
  table {{ border-collapse: collapse; margin: 0.8em 0; }}
  th, td {{ border: 1px solid #eee; padding: 0.3em 0.6em; text-align: left; }}
  th {{ background: #f4f4f4; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def markdown_to_html(md: str, charts: dict[str, str]) -> str:
    """Minimal Markdown → HTML conversion sufficient for our report style.

    Supports: headings (#, ##, ###), bold (**), italic (*), code (`),
    blockquotes (>), unordered lists (-), horizontal rules (---), paragraphs,
    and chart placeholders (<!-- chart: ID -->).
    """
    lines = md.split("\n")
    out = []
    in_list = False
    in_para = False
    para_buf: list[str] = []

    def flush_para():
        nonlocal in_para, para_buf
        if para_buf:
            out.append("<p>" + " ".join(inline(p) for p in para_buf) + "</p>")
            para_buf = []
        in_para = False

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def inline(s: str) -> str:
        s = html.escape(s)
        # Code
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        # Bold then italic
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
        return s

    for raw in lines:
        line = raw.rstrip()

        # Chart placeholder
        chart_match = re.match(r"<!-- chart: (.+?) -->$", line)
        if chart_match:
            flush_para()
            flush_list()
            cid = chart_match.group(1)
            if cid in charts:
                out.append(f'<div class="chart">{charts[cid]}</div>')
            continue

        if not line.strip():
            flush_para()
            flush_list()
            continue

        # Headings
        m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            flush_para()
            flush_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue

        # HR
        if line.strip() == "---":
            flush_para()
            flush_list()
            out.append("<hr>")
            continue

        # Blockquote
        if line.startswith("> "):
            flush_para()
            flush_list()
            out.append(f"<blockquote>{inline(line[2:])}</blockquote>")
            continue

        # List item
        m = re.match(r"^- (.*)$", line)
        if m:
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue

        # Nested list (2-space indent)
        m = re.match(r"^  - (.*)$", line)
        if m and in_list:
            out.append(f"<li style=\"margin-left:1em\">{inline(m.group(1))}</li>")
            continue

        # Paragraph
        flush_list()
        in_para = True
        para_buf.append(line.strip())

    flush_para()
    flush_list()

    title_match = re.search(r"^# (.+)$", md, re.MULTILINE)
    title = title_match.group(1) if title_match else "AEO Visibility Report"
    return HTML_TEMPLATE.format(title=html.escape(title), body="\n".join(out))


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate an AEO visibility trend report from accumulated baselines.",
    )
    p.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help=f"Directory of evidence files (default: {DEFAULT_DATA_DIR})")
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"Where to write reports (default: {DEFAULT_OUTPUT_DIR})")
    p.add_argument("--format", choices=("md", "html", "all"), default="all", help="Output format(s)")
    p.add_argument("--stdout", action="store_true", help="Print markdown to stdout instead of writing files")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not os.path.isdir(args.data_dir):
        print(f"✗ Data directory not found: {args.data_dir}", file=sys.stderr)
        print("  Run aeo-baseline first to produce evidence files.", file=sys.stderr)
        return 2
    evidence = load_evidence_files(args.data_dir)
    if not evidence:
        print(f"✗ No valid evidence files in {args.data_dir}/", file=sys.stderr)
        return 2

    by_prompt = group_by_prompt(evidence)
    md, charts = render_markdown(evidence, by_prompt)

    if args.stdout:
        print(md)
        return 0

    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

    written = []
    if args.format in ("md", "all"):
        md_path = os.path.join(args.output_dir, f"{timestamp}-report.md")
        with open(md_path, "w") as f:
            f.write(md)
        written.append(md_path)
    if args.format in ("html", "all"):
        html_path = os.path.join(args.output_dir, f"{timestamp}-report.html")
        with open(html_path, "w") as f:
            f.write(markdown_to_html(md, charts))
        written.append(html_path)

    print(f"✓ Wrote {len(written)} report(s):")
    for p in written:
        print(f"  • {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
