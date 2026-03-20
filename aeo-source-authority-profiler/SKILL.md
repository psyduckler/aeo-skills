---
name: aeo-source-authority-profiler
description: >
  Analyze WHY certain sources get cited by Gemini over others. Runs a prompt through
  Gemini 3 Flash with grounding, ranks cited sources by frequency, then fetches and
  profiles the top pages — word count, headings, structured data (JSON-LD), publication
  dates, and entity density. Outputs a "citation blueprint" showing what top-cited pages
  have in common. Optionally highlights where a specific domain's pages stand vs the
  blueprint.
  Use when a user wants to: understand what makes pages get cited by AI, reverse-engineer
  citation patterns, build a content template based on what Gemini prefers, compare their
  content to competitors' cited pages, or audit page-level factors that correlate with
  AI citations.
---

# AEO Source Authority Profiler

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-source-authority-profiler)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Reverse-engineer WHY certain pages get cited by Gemini — and build a blueprint to replicate their success.

## Background

Influence over AI answers happens at retrieval, not inside the model. You can't edit Gemini's weights, but you can enter the **candidate set** it selects from when it searches the web. Every prompt triggers a retrieval step — Gemini fires search queries, evaluates the results, and picks sources to ground its answer. The pages it picks consistently form the **recurring retrieval set** for that topic.

This skill profiles the pages *inside* that recurring set. By analyzing what they have in common — length, structure, schema, freshness, entity density — you get a concrete blueprint for what it takes to enter and stay in the candidate set. Gemini's search-first architecture creates more entry points than recall-first models like GPT, which means the on-page profile of cited sources matters more than ever: retrievability requires alignment with query patterns, comprehensive coverage, and structural clarity.

## Why This Works

Not all pages are created equal. When Gemini answers a prompt, it consistently cites certain sources over others. This skill reveals the common profile of those cited pages: their length, structure, schema markup, freshness, and entity density. By running 20 samples, you see which sources are *reliably* part of the recurring retrieval set (not just lucky once), then by profiling those pages, you discover the on-page signals that correlate with AI citation.

The result is a **citation blueprint** — a concrete spec for what your content needs to look like to enter the candidate set for that prompt. Influence compounds through repeated inclusion; one-off citations don't matter, but matching the blueprint puts you in the recurring set.

## Defaults

- **Model:** `gemini-3-flash-preview` — the same model powering Google AI Overviews
- **Samples:** 20 runs per prompt — captures probabilistic citation patterns
- **Top pages:** 10 — profiles the 10 most-cited URLs

## Requirements

- **Gemini API key** (free from [aistudio.google.com](https://aistudio.google.com)) — set as `GEMINI_API_KEY` env var
- Python 3.9+
- No pip dependencies (stdlib only)

## Usage

```bash
# Basic — profile top-cited sources for a prompt
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/profile.py "best project management tools for startups"

# Highlight how your domain compares to the blueprint
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/profile.py "best project management tools for startups" --domain monday.com

# Profile more pages with higher confidence
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/profile.py "best CRM software" --domain hubspot.com --runs 30 --top 15

# JSON output for programmatic use
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/profile.py "best SEO tools" --output json
```

Run from the skill directory. Resolve `scripts/profile.py` relative to this SKILL.md.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `prompt` | (required) | The query to analyze |
| `--domain` | (none) | Domain to highlight vs the blueprint (e.g., `example.com`) |
| `--runs` | 20 | Number of Gemini runs |
| `--model` | `gemini-3-flash-preview` | Gemini model to use |
| `--top` | 10 | Number of top URLs to fetch and profile |
| `--concurrency` | 5 | Max parallel requests (keep ≤5 to avoid rate limits) |
| `--output` | `text` | Output format: `text` or `json` |

## Output

### Text Output

```
Source Authority Profiler: "best project management tools for startups"
Model: gemini-3-flash-preview
Runs: 20/20 successful
Unique URLs cited: 34

TOP CITED PAGES:
======================================================================

  #1 — 85% (17/20 runs)
  URL: https://monday.com/blog/project-management/best-tools/
  Title: Best Project Management Tools for Startups (2025)
  Domain: monday.com
  Word count: 3,450
  Headings: 18 total (H1:1, H2:8, H3:9)
  Schema: ✓ JSON-LD (Article, BreadcrumbList)
  Published: 2025-01-15
  Modified: 2025-03-01
  Entity density: 42 entities detected

  #2 — 70% (14/20 runs)
  ...

CITATION BLUEPRINT:
======================================================================
Based on 8 successfully profiled pages

  Word count:        avg 2,850 | median 2,600 | range 1,200–5,100
  Headings:          avg 14 | range 6–24
  JSON-LD schema:    75% of pages (6/8)
  Schema types:      Article(5), BreadcrumbList(4), Organization(2)
  Entity density:    avg 35 | range 12–58
  With pub date:     6/8
  With mod date:     5/8
  Domain diversity:  7 unique domains in top results

DOMAIN ANALYSIS: monday.com
======================================================================
  Pages in top 10: 2

  https://monday.com/blog/project-management/best-tools/
    Word count: 3,450 (+600 vs avg)
    Headings:   18 (+4 vs avg)
    Schema:     ✓
    Entities:   42 (+7 vs avg)
```

### JSON Output

Structured JSON with `profiles` (per-page data), `blueprint` (aggregate pattern), and `domain_analysis` (if domain provided).

## How It Works

1. **Phase 1 — Citation Collection:** Sends the prompt to Gemini 20 times with Google Search grounding. Extracts all cited URLs from grounding chunks and ranks by frequency.
2. **Phase 2 — Page Profiling:** Fetches the top 10 most-cited URLs using urllib. For each page, parses HTML to extract:
   - Word count (visible body text)
   - Headings (H1, H2, H3 counts)
   - JSON-LD structured data (types like Article, FAQ, Product)
   - Publication and modification dates from meta tags
   - Entity density (proper nouns, numbers, statistics, quoted terms)
3. **Phase 3 — Blueprint Generation:** Aggregates page profiles into a "citation blueprint" — averages, ranges, and common patterns across all profiled pages.
4. **Phase 4 — Domain Analysis:** If `--domain` provided, compares that domain's pages against the blueprint, showing where they exceed or fall short.

## Tips

- Use the blueprint as a **content spec** — match the word count, heading structure, and entity density of pages in the recurring retrieval set
- If your domain isn't in the top results, the blueprint tells you what to aim for to enter the candidate set
- Pages with JSON-LD schema (especially Article, FAQ) get cited more often — use `aeo-schema-optimizer` to add it
- Run for your most important prompts and compare blueprints — different query types may need different content profiles
- Pair with `aeo-content-free` to create content that matches the blueprint
- Pair with `aeo-ai-overview-simulator` for deeper citation rate tracking over time
- Pair with `aeo-multi-prompt-strategy` to find pages that enter the recurring retrieval set across multiple prompts

## References



## Notes

- Gemini API key stored in macOS Keychain under `google-api-key`
- Pages that fail to fetch (timeouts, 403s) are noted but don't crash the analysis
- HTML parsing uses stdlib `html.parser` — no external dependencies
- Retries API calls up to 5 times with exponential backoff
- Page fetching uses a 10-second timeout to avoid slow pages blocking the analysis
