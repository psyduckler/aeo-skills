---
name: aeo-grounding-query-mapper
description: >
  Map the exact search queries Gemini 3 Flash fires when answering prompts. Run prompts
  multiple times with Google Search grounding to capture query frequency, cluster similar
  queries, identify patterns/themes, and analyze query evolution. Supports single prompts
  and batch mode (file input). Upgraded version of prompt-frequency-analyzer with richer
  analysis including query clustering, cross-prompt overlap, and theme detection.
  Use when investigating: what Google's AI actually searches for, query pattern analysis
  across related prompts, how to align content with AI search behavior, or comparing
  query strategies across different prompt phrasings.
---

# AEO Grounding Query Mapper

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-grounding-query-mapper)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Map the exact search queries Gemini 3 Flash fires when answering prompts — with clustering, pattern analysis, and cross-prompt comparison.

## Why This Matters

When Gemini 3 Flash generates an AI Overview, it doesn't just answer from memory — it fires real Google Search queries to ground its response. [Influence happens at retrieval, not inside the model](https://www.clearscope.io/blog/how-to-influence-ai-answers) — you can't edit training data, but you can enter the "candidate set" the model selects from when it searches. Gemini is [search-first](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence): it searches before nearly every answer, making it more influenceable than GPT.

Understanding *what* it searches for reveals the **recurring retrieval set** — the queries, sources, and themes the model consistently draws from:

- **What topics to cover** — queries reveal the sub-topics the AI considers essential
- **How to phrase content** — match the exact language the AI searches for
- **Cross-prompt patterns** — similar prompts may trigger overlapping queries, revealing core themes
- **What content type to create** — query intent (informational, commercial, navigational, transactional) tells you what format enters the candidate set

This is an upgraded version of `prompt-frequency-analyzer` with three key additions:
1. **Query clustering** — groups similar queries by shared terms
2. **Cross-prompt overlap** — shows which queries appear across multiple prompts
3. **Batch mode** — process many prompts from a file in one run

## Requirements

- **Gemini API key** (free) — set as `GEMINI_API_KEY` env var
- Python 3.9+
- No pip dependencies (stdlib only)

## Usage

```bash
# Single prompt
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/map_queries.py "best CRM for small business"

# Multiple prompts
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/map_queries.py "best CRM for small business" "CRM vs spreadsheet" "how to choose a CRM"

# Batch mode from file (one prompt per line)
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/map_queries.py --prompts-file prompts.txt

# JSON output
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/map_queries.py "best CRM for small business" --output json
```

Run from the skill directory. Resolve `scripts/map_queries.py` relative to this SKILL.md.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `prompt` | (positional, one or more) | Prompts to analyze |
| `--prompts-file` | (none) | File with one prompt per line |
| `--runs` | 20 | Runs per prompt |
| `--model` | `gemini-3-flash-preview` | Gemini model |
| `--concurrency` | 5 | Max parallel API calls |
| `--output` | `text` | Output format: `text` or `json` |

## Output

### Per-Prompt Analysis

For each prompt:
- **Query frequency** — each unique search query with run count and percentage
- **Intent classification** — each query classified as `informational`, `commercial`, `navigational`, or `transactional`
- **Intent distribution** — percentage breakdown of query intents across all unique queries
- **Query clusters** — groups of similar queries sharing key terms
- **Top sources** — domains cited most frequently

### Intent Classification

Every search query is automatically classified by intent:

- **informational** — knowledge-seeking queries ("what is X", "how does X work")
- **commercial** — evaluation/comparison queries ("best X", "X vs Y", "X review")
- **navigational** — brand/site-specific queries (contains domain names, "X login")
- **transactional** — purchase/action queries ("buy X", "X discount", "X free trial")

### Cross-Prompt Analysis (when multiple prompts)

- **Shared queries** — queries that appear across 2+ prompts (core themes)
- **Unique queries** — queries specific to a single prompt
- **Query overlap matrix** — which prompt pairs share the most queries

### Text Example

```
Prompt 1: "best CRM for small business"
Model: gemini-3-flash-preview | Runs: 20/20

Query Frequency:
  90% (18/20) [commercial] — best crm for small business
  55% (11/20) [commercial] — small business crm comparison
  40% (8/20)  [transactional] — crm software pricing 2025
  25% (5/20)  [commercial] — hubspot vs salesforce small business

Intent Distribution:
  30% informational, 50% commercial, 10% navigational, 10% transactional

Query Clusters:
  [crm comparison] (3 queries, 75% of runs)
    - small business crm comparison (55%)
    - best crm comparison 2025 (30%)
    - crm software pricing 2025 (40%)
  [specific brands] (2 queries, 45% of runs)
    - hubspot vs salesforce small business (25%)
    - zoho crm review (20%)

──────────────────────────────────────────

Cross-Prompt Overlap:
  "best crm" appears in 3/3 prompts — core theme
  "small business" appears in 2/3 prompts
  "comparison" appears in 2/3 prompts
```

## Tips

- Use batch mode to analyze a set of related prompts and find themes
- High-frequency queries (>60%) are the AI's "go-to" searches — align your content with them
- Low-frequency queries (<20%) reveal edge-case sub-topics the AI sometimes explores
- Cross-prompt overlap reveals core themes you must cover regardless of phrasing
- Pair with `aeo-content-free` — use discovered queries as section headings and topics

## Notes

- Gemini API key in macOS Keychain under `google-api-key`
- Retries with exponential backoff (up to 5 attempts)
- Keep `--concurrency` ≤5 to avoid rate limits
- Prompts are processed sequentially (concurrency applies within each prompt's runs)
