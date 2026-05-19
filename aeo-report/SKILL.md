---
name: aeo-report
description: >
  Read accumulated aeo-baseline evidence files and produce a visibility trend
  report. Surfaces visibility score trends, citation-rate decay, content
  cannibalization (multiple owned URLs competing for the same prompt),
  hub-page opportunities (one URL winning across many prompts), and competitor
  share-of-voice changes. Outputs Markdown + single-file HTML with embedded
  SVG charts. Pure analysis — no provider API calls, no API keys required.
  Use when a user wants to: see how their AI visibility is changing over
  time, find pages losing citations, identify which owned URLs are working
  across multiple prompts, share a visibility report with stakeholders, or
  understand competitor share trends.
---

# AEO Report

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-report)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Reads `aeo-data/*.json` (evidence files written by [aeo-baseline](https://github.com/psyduckler/aeo-skills/tree/main/aeo-baseline)) and produces a shareable visibility report. The skill that makes the daily cron actually useful.

## Requirements

- Python 3.9+ (stdlib only)
- At least one `aeo-evidence-v1` file in your data directory
- No API keys (this skill never calls a provider)

## Usage

```bash
# Default: read aeo-data/, write Markdown + HTML to aeo-reports/
python3 scripts/report.py

# Specify directories
python3 scripts/report.py --data-dir custom-data --output-dir custom-reports

# Markdown only (good for piping)
python3 scripts/report.py --format md

# Print to stdout (good for one-off review)
python3 scripts/report.py --stdout
```

Output filenames are timestamped: `<UTC-timestamp>-report.md` and `<UTC-timestamp>-report.html`.

## Options

| Option | Default | Description |
|---|---|---|
| `--data-dir` | `aeo-data` | Directory of evidence files |
| `--output-dir` | `aeo-reports` | Where to write reports |
| `--format` | `all` | `md` \| `html` \| `all` |
| `--stdout` | — | Print Markdown to stdout instead of writing files |

## What's in the report

### Executive summary

- Average visibility score across all prompts (latest run)
- Trend vs. first run (if multiple runs)
- Count of decay alerts
- Count of hub-page candidates

### Per-prompt detail

For each prompt:
- Latest visibility score, mention rate, citation rate (with Wilson 95% CIs)
- Average citation position (when cited)
- Embedded SVG chart of visibility score over time (when ≥2 runs exist)
- Top 5 entities from the entity universe
- Decay flag if citation rate has fallen
- Cannibalization flag if multiple owned URLs compete
- Competitor share-of-voice shifts

### Cross-prompt sections

- **Hub-Page Opportunities** — owned URLs cited across multiple prompts
- **Decay Alerts** — prompts with declining citation rate

## Detection thresholds

| Signal | Trigger |
|---|---|
| Decay | Trailing 3-run mean is ≥20% below leading 3-run mean (HIGH if ≥50%, MEDIUM ≥30%, LOW otherwise). Needs ≥4 runs. |
| Cannibalization | ≥2 distinct owned URLs are each cited in ≥2 samples within the latest run. |
| Hub page | A URL is cited for ≥2 prompts AND covers ≥30% of tracked prompts in the latest run. |
| Competitor share shift | First-run vs latest-run share differs by >5 percentage points. |

All thresholds live as constants at the top of `scripts/report.py`. Bump them for your workspace if needed.

## SVG charts

Charts are hand-rendered SVG (no matplotlib, no pip install). Each chart is embedded inline in the HTML output via a `<!-- chart: <id> -->` placeholder in the Markdown. Currently:

- One **line chart per prompt** showing visibility score over time (only when ≥2 runs exist)

Future charts (deferred): entity-frequency bar charts, competitor-share stacked area, citation-position over time.

## Pure analysis

This skill is read-only. It never:
- Calls a provider API
- Mutates evidence files
- Requires an API key

So it's safe to run from CI, in pre-commit hooks, or anywhere else.

## Pairs With

- **[aeo-init](https://github.com/psyduckler/aeo-skills/tree/main/aeo-init)** — sets up the workspace
- **[aeo-baseline](https://github.com/psyduckler/aeo-skills/tree/main/aeo-baseline)** — produces the evidence files this skill reads
- **[aeo-track](https://github.com/psyduckler/aeo-skills/tree/main/aeo-track)** — schedules baselines so trends accumulate
- **aeo-optimize** (coming) — reads the latest baseline + report and produces a Markdown work queue

## Notes

- Reports are append-only by default (one file per invocation). Delete old reports manually if directory growth is a concern.
- The HTML output is a single self-contained file (inline CSS + SVG). Email-safe, easy to share.
- For very large workspaces (50+ prompts × 365 days), report generation is O(N) over evidence files — typically subsecond.
