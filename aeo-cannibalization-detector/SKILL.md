---
name: aeo-cannibalization-detector
description: >
  Detect when a brand's own pages compete against each other for the same AI prompt
  citations. Runs prompts through Gemini 3 Flash with grounding and checks if multiple
  URLs from the same domain get cited across runs. Scores severity (LOW/MEDIUM/HIGH)
  and recommends consolidation or differentiation.
  Use when a user wants to: check if their pages cannibalize each other in AI answers,
  find which pages compete for the same AI prompts, decide whether to consolidate or
  differentiate competing content, or audit their site's AI citation efficiency.
---

# AEO Cannibalization Detector

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-cannibalization-detector)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Detect when your own pages compete against each other for the same slots in Gemini's candidate set.

## Background

Influence over AI answers [happens at retrieval, not inside the model](https://www.clearscope.io/blog/how-to-influence-ai-answers). When Gemini searches the web to answer a prompt, it builds a **candidate set** of pages to cite. If two of your own pages both enter that candidate set for the same prompt, you're competing against yourself — Gemini alternates between citing page A and page B, diluting the citation strength of both.

This matters because [influence compounds through repeated inclusion](https://www.clearscope.io/blog/how-to-influence-ai-answers) in the **recurring retrieval set**. A page that gets cited 90% of the time is building authority. Two pages that each get cited 40% are neither building authority. In a search-first system like Gemini, where [every response triggers web retrieval](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence), having a single strong page in the candidate set beats splitting your authority across competing pages.

## Defaults

- **Model:** `gemini-3-flash-preview` — the same model powering Google AI Overviews
- **Samples:** 20 runs per prompt — enough to detect citation splits

## Requirements

- **Gemini API key** (free from [aistudio.google.com](https://aistudio.google.com)) — set as `GEMINI_API_KEY` env var
- Python 3.9+
- No pip dependencies (stdlib only)

## Usage

```bash
# Check two prompts for cannibalization
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/detect.py --domain clearscope.io \
    "best content optimization tools" \
    "SEO content software"

# Load prompts from a file
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/detect.py --domain clearscope.io --prompts-file prompts.txt

# Both positional prompts and file, JSON output
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/detect.py --domain clearscope.io \
    "content optimization" \
    --prompts-file more-prompts.txt \
    --output json

# Higher confidence with more runs
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/detect.py --domain clearscope.io \
    "best SEO tools" --runs 30
```

Run from the skill directory. Resolve `scripts/detect.py` relative to this SKILL.md.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `prompts` | (positional) | One or more prompts to analyze |
| `--domain` | (required) | Your domain to check (e.g., `example.com`) |
| `--prompts-file` | (none) | File with one prompt per line (combined with positional) |
| `--runs` | 20 | Runs per prompt |
| `--model` | `gemini-3-flash-preview` | Gemini model to use |
| `--concurrency` | 5 | Max parallel API calls (keep ≤5 to avoid rate limits) |
| `--output` | `text` | Output format: `text` or `json` |

## Output

### Text Output

```
Cannibalization Detector: clearscope.io
Model: gemini-3-flash-preview | Runs per prompt: 20

RESULTS BY PROMPT:
======================================================================

"best content optimization tools"
  Runs: 20 | Domain URLs found: 3
  Status: 🔴 HIGH cannibalization
  Competing URLs:
    45% (9/20) /blog/content-optimization-tools — Best Content Optimization Tools (2025)
      https://clearscope.io/blog/content-optimization-tools
    35% (7/20) /product — Clearscope - Content Optimization Platform
      https://clearscope.io/product
    15% (3/20) /blog/seo-content-tools — SEO Content Tools Guide
      https://clearscope.io/blog/seo-content-tools
  → No single URL exceeds 50% citation rate. Gemini can't decide which
    of your pages to cite — citations are diluted across 3 URLs.
    Strongly recommend consolidating into one comprehensive page.

"SEO content software"
  Runs: 20 | Domain URLs found: 1
  Status: ✓ No cannibalization
    85% — https://clearscope.io/product
  No cannibalization — single URL cited consistently.

SUMMARY:
======================================================================
  Domain: clearscope.io
  Prompts analyzed: 2
  Cannibalization detected: 1/2
  Severity: HIGH: 1

  Worst offenders:
    🔴 "best content optimization tools" — HIGH (3 URLs, max 45%)
```

### JSON Output

Structured JSON with per-prompt `cannibalization` details (severity, URLs, rates) and a `summary` with worst offenders.

## Severity Levels

| Severity | Condition | Meaning |
|----------|-----------|---------|
| **NONE** | 0–1 domain URLs cited | No competition — clean |
| **LOW** | One URL dominates >80% | Minor leakage — one URL is clearly winning |
| **MEDIUM** | Top URL 50–80% | Noticeable split — Gemini sometimes picks the wrong page |
| **HIGH** | No URL >50% | Severe dilution — no page has established recurring retrieval position |

## How It Works

1. Runs each prompt 20 times against Gemini with Google Search grounding
2. Extracts all cited URLs from grounding chunks
3. Filters to URLs matching the target domain
4. If 2+ different domain URLs appear across runs for the same prompt → cannibalization detected
5. Scores severity based on the top URL's citation rate
6. Recommends consolidation (merge pages) or differentiation (make topics distinct)

## Tips

- Run this before creating new content — check if an existing page already targets the same prompt
- **HIGH severity** is your highest priority: consolidate those pages into one comprehensive resource
- **MEDIUM severity** might mean the pages cover overlapping subtopics — consider differentiating with clearer focus
- **LOW severity** is usually fine — the right page is winning, the other just appears occasionally
- Pair with `aeo-source-authority-profiler` to understand what the winning competing page does differently
- Pair with `aeo-multi-prompt-strategy` to see if competing pages are winning *different* prompts (deliberate vs accidental)
- Use `--prompts-file` with a list of your target prompts for a full site audit

## References

- [How to Influence AI Answers](https://www.clearscope.io/blog/how-to-influence-ai-answers) — Why influence requires entering the candidate set, not splitting across it
- [Gemini Creates More Opportunity; GPT Is Harder to Influence](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence) — Search-first retrieval and the permeability of Gemini's citation pipeline

## Notes

- Gemini API key stored in macOS Keychain under `google-api-key`
- Prompts file supports comments (lines starting with `#`) and blank lines
- Retries API calls up to 5 times with exponential backoff
- Subdomains are matched — `blog.example.com` counts as `example.com`
