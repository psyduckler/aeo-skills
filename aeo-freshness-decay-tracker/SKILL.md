---
name: aeo-freshness-decay-tracker
description: >
  Monitor how citation rates change as content ages. Runs prompts against Gemini 3 Flash
  with grounding and records citation/mention rates over time in an append-only JSON file.
  Detects decay trends, estimates time until citation loss, and flags pages needing urgent
  refresh.
  Use when a user wants to: track citation rate changes over time, detect content decay,
  find pages losing AI visibility, prioritize content refreshes, or monitor whether content
  updates restored citations.
---

# AEO Freshness Decay Tracker

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-freshness-decay-tracker)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Monitor when your content exits the recurring retrieval set — and catch decay before you disappear.

## Background

Being cited once doesn't matter. [Influence compounds through repeated inclusion](https://www.clearscope.io/blog/how-to-influence-ai-answers) in the **recurring retrieval set** — the group of sources Gemini consistently draws from when answering a prompt. But that set isn't static. As content ages, competitors publish fresher alternatives, and the model's search queries evolve, your pages can slip out of the candidate set entirely.

In a [search-first system like Gemini](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence), retrievability depends on alignment with the queries the model generates, comprehensive topic coverage, and freshness signals. When any of these degrade, your citation rate decays. This skill tracks that decay over time so you can catch it early and refresh before you lose your position in the recurring retrieval set.

The "long long tail" of Gemini's search behavior means the model generates varied, specific queries — and as those queries evolve, previously-cited content may no longer match. Tracking decay reveals when this happens.

## Defaults

- **Model:** `gemini-3-flash-preview` — the same model powering Google AI Overviews
- **Samples:** 20 runs per prompt — captures probabilistic citation patterns
- **Data format:** Append-only JSON — never overwrites historical data

## Requirements

- **Gemini API key** (free from [aistudio.google.com](https://aistudio.google.com)) — set as `GEMINI_API_KEY` env var
- Python 3.9+
- No pip dependencies (stdlib only)

## Usage

### Scan — Record current citation rates

```bash
# Scan prompts and save to data file
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/track.py scan \
    --domain clearscope.io \
    --prompts "best content optimization tools" "SEO content software" \
    --data-file freshness.json

# With prompts from a file
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/track.py scan \
    --domain clearscope.io \
    --prompts-file prompts.txt \
    --data-file freshness.json
```

### Report — Analyze decay patterns

```bash
# Text report
python3 scripts/track.py report --data-file freshness.json

# JSON report
python3 scripts/track.py report --data-file freshness.json --output json
```

Run from the skill directory. Resolve `scripts/track.py` relative to this SKILL.md.

## Options

### Scan Options

| Option | Default | Description |
|--------|---------|-------------|
| `--domain` | (required) | Domain to track |
| `--prompts` | (required*) | One or more prompts to scan |
| `--prompts-file` | (none) | File with one prompt per line (*can use instead of `--prompts`) |
| `--data-file` | `freshness.json` | Path to append-only data file |
| `--runs` | 20 | Runs per prompt |
| `--model` | `gemini-3-flash-preview` | Gemini model |
| `--concurrency` | 5 | Max parallel API calls |

### Report Options

| Option | Default | Description |
|--------|---------|-------------|
| `--data-file` | `freshness.json` | Path to data file |
| `--output` | `text` | Output format: `text` or `json` |

## Output

### Scan Output

Quick summary after each scan:

```
Freshness Decay Tracker — Scan
Domain: clearscope.io | Prompts: 2 | Model: gemini-3-flash-preview

Scan complete: 2 prompts × 20 runs
Saved to freshness.json (scan #3)

Quick Results (clearscope.io):
  "best content optimization tools":
    Mention: 85% | Citation: 80%
  "SEO content software":
    Mention: 60% | Citation: 55%
```

### Report Output

```
Freshness Decay Tracker — Report
Data: freshness.json (5 scans)
Period: 2025-01-15 → 2025-03-15
Domain(s): clearscope.io
======================================================================

REFRESH URGENCY SUMMARY:
  🔴 HIGH:   1 prompts — content losing citations fast
  🟡 MEDIUM: 1 prompts — gradual decline
  Declining: 2 of 4 prompts

PROMPT-BY-PROMPT ANALYSIS:
======================================================================

🔴 "best content optimization tools"
  Urgency: HIGH | Trend: rapid_decline
  Citation rate dropped from 80% to 35% over 8 weeks.
  At this rate, citations may reach 0 in ~6 weeks.
  Timeline:
    2025-01-15: citation 80% | mention 85%
    2025-02-01: citation 70% | mention 80%
    2025-02-15: citation 55% | mention 65%
    2025-03-01: citation 40% | mention 50%
    2025-03-15: citation 35% | mention 45%
  Cited URLs:
    https://clearscope.io/blog/content-optimization-tools
      Counts across scans: 14 → 12 → 9 → 6 → 5

🟢 "SEO content software"
  Urgency: LOW | Trend: stable
  Citation rate stable at 55% (was 60%).
  ...

PAGES MOST IN NEED OF REFRESH:
======================================================================
  🔴 https://clearscope.io/blog/content-optimization-tools
    Prompt: "best content optimization tools" | Change: -45%
```

## Data File Format

Append-only JSON. Each `scan` adds an entry, never modifying previous data:

```json
{
  "scans": [
    {
      "timestamp": "2025-01-15T14:30:00+00:00",
      "domain": "clearscope.io",
      "model": "gemini-3-flash-preview",
      "runs_per_prompt": 20,
      "results": {
        "best content optimization tools": {
          "successful_runs": 20,
          "mention_rate": 85,
          "mention_count": 17,
          "citation_rate": 80,
          "citation_count": 16,
          "cited_urls": {
            "https://clearscope.io/blog/content-optimization-tools": 14
          }
        }
      }
    }
  ]
}
```

## Refresh Urgency Levels

| Urgency | Condition | Meaning |
|---------|-----------|---------|
| **HIGH** | Was cited >30%, dropped >20% | Rapid decay — content is exiting the recurring retrieval set |
| **MEDIUM** | Declining 5–20% | Gradual erosion — content still cited but losing ground |
| **LOW** | Stable or growing | No action needed — content maintains its position |
| **UNKNOWN** | <2 data points | Not enough history to determine trend |

## How It Works

### Scan
1. Runs each prompt 20 times against Gemini with Google Search grounding
2. Records mention rate (brand in text), citation rate (domain in sources), and which URLs were cited
3. Appends scan data with timestamp to the JSON file — never overwrites

### Report
1. Reads historical scan data
2. For each prompt, builds a time series of citation rates
3. Detects trends: stable, growing, declining, rapid decline
4. Estimates weeks until zero citations (for declining prompts)
5. Ranks prompts by refresh urgency
6. Lists specific URLs that need refreshing

## Tips

- Run scans **weekly** for active prompts — this gives the report enough data points to detect meaningful trends
- Set up a cron job or heartbeat task to automate weekly scans
- Focus refresh efforts on **HIGH urgency** prompts first — those pages are actively losing their position in the candidate set
- After refreshing content, continue scanning to verify citations recover (expect 2–4 weeks for re-indexing)
- Pair with `aeo-source-authority-profiler` to understand what the *new* top-cited pages look like (your blueprint may have shifted)
- Pair with `aeo-content-free` to refresh decaying content using the latest competitive intelligence
- Use the same prompts file across scans for consistent tracking

## References

- [How to Influence AI Answers](https://www.clearscope.io/blog/how-to-influence-ai-answers) — Why repeated inclusion in the recurring retrieval set matters
- [Gemini Creates More Opportunity; GPT Is Harder to Influence](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence) — The long tail of search queries and why freshness matters in search-first systems

## Notes

- Gemini API key stored in macOS Keychain under `google-api-key`
- Data file is created automatically on first scan
- Append-only: historical data is never deleted or modified
- Prompts file supports comments (`#`) and blank lines
- Retries API calls up to 5 times with exponential backoff
- Need at least 2 scans to detect any trends; 4+ scans for reliable decay detection
