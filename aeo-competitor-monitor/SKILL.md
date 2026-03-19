---
name: aeo-competitor-monitor
description: >
  Track competitor citations in AI Overviews over time. Runs prompts through Gemini 3 Flash
  with grounding and records which competitor domains get cited, how often, and with what
  snippets. Saves results to an append-only JSON data file for trend analysis. Generates
  comparison reports showing citation share changes over time.
  Use when a user wants to: track competitors' AI visibility, compare citation share across
  brands, monitor who's winning AI Overviews for key prompts, or detect when competitors
  gain or lose AI citations.
---

# AEO Competitor Monitor

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-competitor-monitor)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Track which competitors get cited in AI Overviews — and how that changes over time.

## Why This Matters

AI Overviews create a new competitive landscape. The sources Gemini cites for your key prompts are your real competitors in the AI-driven search world. Tracking their citation share over time reveals:

- **Who's gaining ground** — new content that's winning AI citations
- **Who's losing ground** — previously-cited pages dropping off
- **Market dynamics** — how citation share shifts with content updates, algorithm changes
- **Your relative position** — where you stand vs competitors across key prompts

## Requirements

- **Gemini API key** (free) — set as `GEMINI_API_KEY` env var
- Python 3.9+
- No pip dependencies (stdlib only)

## Usage

### Scan — Run a new competitive scan

```bash
# Scan two prompts, tracking three competitors
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/monitor.py scan \
    --prompts "best SEO tools" "content optimization software" \
    --competitors clearscope.io surferseo.com semrush.com \
    --data-file monitor-data.json

# With custom run count
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/monitor.py scan \
    --prompts "best SEO tools" \
    --competitors clearscope.io surferseo.com \
    --data-file monitor-data.json \
    --runs 30
```

### Report — Generate a comparison report

```bash
# Text report
python3 scripts/monitor.py report --data-file monitor-data.json

# JSON report
python3 scripts/monitor.py report --data-file monitor-data.json --output json
```

Run from the skill directory. Resolve `scripts/monitor.py` relative to this SKILL.md.

## Options

### Scan Options

| Option | Default | Description |
|--------|---------|-------------|
| `--prompts` | (required) | One or more prompts to scan |
| `--competitors` | (required) | One or more competitor domains to track |
| `--data-file` | `monitor-data.json` | Path to the data file (created if missing) |
| `--runs` | 20 | Runs per prompt |
| `--model` | `gemini-3-flash-preview` | Gemini model |
| `--concurrency` | 5 | Max parallel API calls |

### Report Options

| Option | Default | Description |
|--------|---------|-------------|
| `--data-file` | `monitor-data.json` | Path to the data file |
| `--output` | `text` | Output format: `text` or `json` |

## Output

### Scan Output

After each scan, prints a quick summary:

```
Scan complete: 2 prompts × 20 runs
Saved to monitor-data.json (scan #3)

Quick Results:
  "best SEO tools":
    clearscope.io  — 75% citation rate
    surferseo.com  — 60% citation rate
    semrush.com    — 85% citation rate

  "content optimization software":
    clearscope.io  — 80% citation rate
    surferseo.com  — 45% citation rate
    semrush.com    — 55% citation rate
```

### Report Output

```
Competitor Monitor Report
Data: monitor-data.json (3 scans, 14 days)
================================================================

CITATION SHARE BY PROMPT:

"best SEO tools" (3 scans):
  Competitor        Latest    Avg     Trend
  ─────────────────────────────────────────
  semrush.com        85%      80%     ↑ +10%
  clearscope.io      75%      70%     → stable
  surferseo.com      60%      65%     ↓ -5%

"content optimization software" (3 scans):
  Competitor        Latest    Avg     Trend
  ─────────────────────────────────────────
  clearscope.io      80%      75%     ↑ +10%
  semrush.com        55%      60%     ↓ -10%
  surferseo.com      45%      50%     ↓ -5%

OVERALL CITATION SHARE (across all prompts):
  semrush.com    — 70% avg citation rate
  clearscope.io  — 78% avg citation rate
  surferseo.com  — 53% avg citation rate

NOTABLE CHANGES:
  ↑ clearscope.io gained +10% on "content optimization software"
  ↓ semrush.com dropped -10% on "content optimization software"

CITED URLS:
  clearscope.io:
    - https://clearscope.io/blog/content-optimization (12x)
    - https://clearscope.io/product (5x)
  ...
```

## Data File Format

The data file is append-only JSON. Each scan adds an entry:

```json
{
  "scans": [
    {
      "timestamp": "2025-03-15T14:30:00Z",
      "model": "gemini-3-flash-preview",
      "runs_per_prompt": 20,
      "results": {
        "best SEO tools": {
          "successful_runs": 20,
          "competitors": {
            "clearscope.io": {
              "citation_rate": 75,
              "citation_count": 15,
              "cited_urls": {"https://clearscope.io/blog/seo-tools": 10},
              "mentioned": true,
              "excerpts": ["Clearscope is a leading content optimization..."]
            }
          },
          "other_sources": [
            {"domain": "g2.com", "citation_rate": 40}
          ]
        }
      }
    }
  ]
}
```

## Tips

- Run scans weekly or biweekly for meaningful trend data
- Track 5-10 prompts and 3-5 competitors for focused insights
- After publishing new content, wait 2-4 weeks before expecting citation changes
- Use alongside `aeo-analytics-free` for your own brand tracking
- Use `aeo-ai-overview-simulator` for deep-dive into specific prompts
- Citation rates fluctuate naturally (±5-10%) — look for sustained trends over 3+ scans

## Notes

- Gemini API key in macOS Keychain under `google-api-key`
- Data file is created automatically on first scan
- Never overwrites historical data — each scan appends
- Retries with exponential backoff for API failures
- API cost: ~400 calls per scan (20 prompts × 20 runs). Free tier supports this.
