---
name: aeo-multi-prompt-strategy
description: >
  Find pages that win across multiple prompts — authority hubs that enter the recurring
  retrieval set for many query patterns at once. Runs multiple prompts through Gemini 3
  Flash with grounding and cross-references which URLs and domains get cited across
  prompts. Identifies hub pages, single-prompt winners, and gaps. Recommends whether to
  build comprehensive hub pages or optimize existing single-winners.
  Use when a user wants to: find which pages win multiple AI prompts, identify authority
  hub opportunities, decide between one hub page vs many focused pages, discover
  cross-prompt citation patterns, or build a multi-prompt content strategy.
---

# AEO Multi-Prompt Strategy

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-multi-prompt-strategy)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Find authority hub pages that enter the recurring retrieval set for multiple query patterns — win many prompts with one page.

## Background

Influence over AI answers compounds through repeated inclusion in the **recurring retrieval set**. But the most powerful form of authority isn't being cited for one prompt — it's being cited for *many*. When a single page enters the candidate set for 5 different prompts, it becomes an **authority hub**: the model has learned to retrieve it across diverse query patterns.

This matters because Gemini generates varied, specific search queries — the "long long tail" of its search behavior means each prompt generates different queries, yet the same authoritative pages keep surfacing. Authority hubs exploit this: they're comprehensive enough to match multiple query patterns, creating expanding entry points across the retrieval landscape.

In Gemini's search-first architecture, every prompt fires fresh web searches. A page that appears in the results for prompts A, B, and C is seen by the model three times as often as a page that only appears for prompt A. This repeated visibility across different retrieval contexts is what builds durable authority — not in the model's weights, but in the model's consistent retrieval behavior.

The strategic question this skill answers: should you build one comprehensive hub page, or many focused pages? The data tells you which approach the model's retrieval behavior actually rewards.

## Defaults

- **Model:** `gemini-3-flash-preview` — the same model powering Google AI Overviews
- **Samples:** 20 runs per prompt — captures cross-prompt citation patterns

## Requirements

- **Gemini API key** (free from [aistudio.google.com](https://aistudio.google.com)) — set as `GEMINI_API_KEY` env var
- Python 3.9+
- No pip dependencies (stdlib only)

## Usage

```bash
# Basic — analyze 3 related prompts
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/strategize.py \
    "best content optimization tools" \
    "how to optimize content for SEO" \
    "content optimization software comparison"

# With domain analysis
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/strategize.py \
    "best content optimization tools" \
    "how to optimize content for SEO" \
    "content optimization software comparison" \
    --domain acme.com

# Load prompts from file
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/strategize.py --prompts-file my-prompts.txt --domain acme.com

# JSON output
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/strategize.py \
    "best CRM for startups" "CRM software comparison" "what CRM should I use" \
    --output json
```

Run from the skill directory. Resolve `scripts/strategize.py` relative to this SKILL.md.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `prompts` | (positional) | Two or more prompts (3+ recommended) |
| `--prompts-file` | (none) | File with one prompt per line (combined with positional) |
| `--domain` | (none) | Domain to analyze (e.g., `example.com`) |
| `--runs` | 20 | Runs per prompt |
| `--model` | `gemini-3-flash-preview` | Gemini model to use |
| `--concurrency` | 5 | Max parallel API calls (keep ≤5) |
| `--output` | `text` | Output format: `text` or `json` |

## Output

### Text Output

```
Multi-Prompt Strategy
Model: gemini-3-flash-preview | Runs per prompt: 20
Prompts analyzed: 3

PER-PROMPT TOP DOMAINS:
======================================================================

  "best content optimization tools" (20 runs):
    85% — acme.com
    70% — surferseo.com
    55% — semrush.com

  "how to optimize content for SEO" (20 runs):
    75% — acme.com
    65% — searchenginejournal.com
    50% — moz.com

  "content optimization software comparison" (20 runs):
    80% — g2.com
    70% — acme.com
    55% — surferseo.com

AUTHORITY HUB PAGES (cited for 2+ prompts):
======================================================================

  🏆 https://acme.com/blog/content-optimization-guide
     Title: The Complete Guide to Content Optimization
     Hub score: 100% (3/3 prompts)
     Avg citation rate: 77%
     Per prompt:
       85% — "best content optimization tools"
       75% — "how to optimize content for SEO"
       70% — "content optimization software comparison"

  🏆 https://surferseo.com/blog/content-optimization/
     Hub score: 67% (2/3 prompts)
     Avg citation rate: 63%
     ...

AUTHORITY HUB DOMAINS (present for 2+ prompts):
======================================================================
  100% — acme.com (3/3 prompts, avg 77%)
   67% — surferseo.com (2/3 prompts, avg 63%)
   67% — semrush.com (2/3 prompts, avg 45%)

SINGLE-PROMPT WINNERS (high rate, but only one prompt):
======================================================================
  80% — g2.com: https://g2.com/categories/content-optimization
         Only wins: "content optimization software comparison"

DOMAIN STRATEGY: acme.com
======================================================================
  Authority hub pages (1):
    🏆 https://acme.com/blog/content-optimization-guide
       3/3 prompts, avg 77%
  Single-prompt winners: None
  Not cited for (0 prompts)

  RECOMMENDATIONS:
    1. Your best hub page is cited for 3/3 prompts. Strengthen this
       page to maintain its authority hub status.
```

### JSON Output

Structured JSON with `authority_hubs`, `domain_hubs`, `single_prompt_winners`, cross-prompt citation matrix, and `domain_analysis`.

## How It Works

1. Runs each prompt 20 times against Gemini with Google Search grounding
2. For each prompt, extracts all cited URLs and domains with their citation rates
3. Cross-references: which URLs/domains appear across multiple prompts
4. Identifies **authority hubs** — individual URLs cited for 2+ different prompts
5. Calculates hub scores: what percentage of prompts cite each URL/domain
6. Identifies **single-prompt winners** — pages that dominate one prompt but don't appear elsewhere
7. If `--domain` provided: shows which of your pages are hubs, singles, or absent — and recommends strategy

## Strategy Concepts

| Concept | Meaning |
|---------|---------|
| **Authority Hub** | A single URL cited for multiple prompts — the model retrieves it across diverse queries |
| **Hub Score** | Percentage of analyzed prompts that cite a URL (higher = more authoritative) |
| **Single-Prompt Winner** | Cited strongly for one prompt but not others — focused but not a hub |
| **Domain Hub** | A domain that appears across multiple prompts (may use different URLs per prompt) |

## Tips

- **Use related prompts** — pick 3-5 prompts that are topically related but phrased differently. This reveals whether the model sees them as the same topic (citing the same pages) or different (citing different pages).
- **Hub pages are more efficient** — one comprehensive page that wins 5 prompts is better than 5 separate pages that each win one. Authority hubs get more total retrieval exposure.
- **Don't force it** — if prompts are genuinely different topics, separate pages are correct. Hub strategy works for prompts that share a topical core.
- **Build toward hub status** — if you have single-prompt winners, consider expanding those pages to cover adjacent prompts. The entity extractor can show you what entities to add.
- Pair with `aeo-source-authority-profiler` to understand the on-page profile of existing authority hubs
- Pair with `aeo-cannibalization-detector` to check if your multiple pages are competing (cannibalization) or complementary (different prompts)
- Pair with `aeo-content-free` to create or expand hub pages that target multiple prompts

## References



## Notes

- Gemini API key stored in macOS Keychain under `google-api-key`
- Minimum 2 prompts required; 3+ recommended for meaningful cross-prompt analysis
- Prompts file supports comments (`#`) and blank lines
- Retries API calls up to 5 times with exponential backoff
- API cost scales with prompt count: N prompts × 20 runs = N×20 API calls
