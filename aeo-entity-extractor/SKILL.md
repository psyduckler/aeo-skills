---
name: aeo-entity-extractor
description: >
  Extract the specific entities (brands, people, statistics, tools, URLs) that Gemini
  mentions in its grounded responses for a given prompt. Aggregates entity frequency across
  20 runs to reveal the "entity universe" for a topic. Optionally performs entity gap
  analysis to show what a specific domain's content should include.
  Use when a user wants to: see what brands/tools Gemini recommends, find missing entities
  in their content, understand what statistics AI responses cite, map the competitive
  entity landscape, or discover which entities to include for better AI citation rates.
---

# AEO Entity Extractor

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-entity-extractor)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Map the entity universe of the recurring retrieval set — the specific brands, stats, people, and tools that Gemini weaves into its answers.

## Background

When Gemini retrieves information to answer a prompt, it doesn't just cite sources — it extracts and repeats specific entities from those sources: brand names, statistics, people, product names, and data points. These entities form the **entity universe** of the recurring retrieval set for that topic.

If your content doesn't include the entities Gemini expects for a topic, you're less likely to enter the candidate set. Conversely, if your content mentions the same brands, cites the same statistics, and references the same tools that Gemini consistently includes in its answers, you signal topical alignment and comprehensiveness. In Gemini's search-first architecture, the model builds its response from retrieved content — your content needs to speak the same entity language as the rest of the candidate set.

The "long long tail" of Gemini's varied search queries means entities that appear across many different query variations are the strongest signals of topic authority. This skill identifies those high-frequency entities.

## Defaults

- **Model:** `gemini-3-flash-preview` — the same model powering Google AI Overviews
- **Samples:** 20 runs per prompt — captures the full entity universe

## Requirements

- **Gemini API key** (free from [aistudio.google.com](https://aistudio.google.com)) — set as `GEMINI_API_KEY` env var
- Python 3.9+
- No pip dependencies (stdlib only)

## Usage

```bash
# Basic — extract entities from Gemini responses
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/extract_entities.py "best project management tools for startups"

# With entity gap analysis for your domain
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/extract_entities.py "best project management tools for startups" --domain monday.com

# JSON output
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/extract_entities.py "best CRM software 2025" --output json
```

Run from the skill directory. Resolve `scripts/extract_entities.py` relative to this SKILL.md.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `prompt` | (required) | The query to analyze |
| `--domain` | (none) | Domain for entity gap analysis (e.g., `example.com`) |
| `--runs` | 20 | Number of Gemini runs |
| `--model` | `gemini-3-flash-preview` | Gemini model to use |
| `--concurrency` | 5 | Max parallel API calls (keep ≤5) |
| `--output` | `text` | Output format: `text` or `json` |

## Output

### Text Output

```
Entity Extractor: "best project management tools for startups"
Model: gemini-3-flash-preview
Runs: 20/20 successful
Total unique entities: 87

🏢 BRANDS & PROPER NOUNS:
============================================================
   90% (18x) ██████████████████ Monday.com
   85% (17x) █████████████████ Asana
   70% (14x) ██████████████ ClickUp
   65% (13x) █████████████ Trello
   55% (11x) ███████████ Notion
   40% ( 8x) ████████ Jira
   30% ( 6x) ██████ Basecamp

📊 STATISTICS & NUMBERS:
============================================================
   60% (12x) ████████████ over 90% of Fortune 500 companies
   45% ( 9x) █████████ $8/user/month
   40% ( 8x) ████████ 1.5 million teams
   35% ( 7x) ███████ top 10

🔧 TOOLS & PRODUCTS:
============================================================
   75% (15x) ███████████████ ClickUp
   50% (10x) ██████████ HubSpot
   40% ( 8x) ████████ Slack.com
   35% ( 7x) ███████ GitHub

👤 PEOPLE:
============================================================
   25% ( 5x) █████ by Jason Fried

TOP SOURCE DOMAINS:
============================================================
   45x — monday.com
   38x — asana.com
   ...

ENTITY GAP ANALYSIS: monday.com
============================================================
  Domain status: ✓ Cited
  Your brand mentioned as:
    18x — Monday.com (brands)

  High-frequency entities to include in your content:
    85% — Asana (brands)
    70% — ClickUp (brands)
    60% — over 90% of Fortune 500 companies (statistics)
    55% — Notion (brands)

  → Your content should mention these high-frequency entities...
```

### JSON Output

Structured JSON with per-type entity rankings, source domains, and gap analysis.

## Entity Types

| Type | Detection Method | Examples |
|------|-----------------|----------|
| **Brands** | Capitalized multi-word sequences, CamelCase | "Google Analytics", "HubSpot" |
| **Statistics** | Numbers with %, $, context words | "85%", "$1.2 million", "top 10" |
| **People** | Name patterns with attribution context | "CEO John Smith", "by Jane Doe" |
| **Tools** | CamelCase, .com/.io domains, suffix patterns | "ClickUp", "notion.so" |
| **URLs** | HTTP(S) links in response text | "https://example.com/guide" |

## How It Works

1. Sends the prompt to Gemini 20 times with Google Search grounding
2. From each response **text** (not grounding metadata), extracts entities using regex patterns:
   - Capitalized multi-word sequences (brand names, proper nouns)
   - Numbers with percentages, currencies, and context words (statistics)
   - CamelCase words and domain-like patterns (tools/products)
   - Name patterns following attribution words (people)
   - Full URLs mentioned in text
3. Aggregates entity frequency across all runs
4. Ranks entities by how often they appear (higher frequency = more consistently part of the entity universe)
5. If `--domain` provided: identifies high-frequency entities the domain's content should include but may not

## Tips

- **High-frequency entities (>50%)** are part of the recurring retrieval set — your content *must* mention these to be topically aligned
- **Medium-frequency entities (20-50%)** are commonly included — mentioning them strengthens your coverage
- **The gap analysis tells you what to add** — if competitors' brands appear but yours doesn't, you need better entity coverage
- Use entities as a **content checklist** — before publishing, verify your content mentions the key brands, stats, and tools Gemini expects
- Pair with `aeo-source-authority-profiler` to see both the page-level blueprint and the entity-level requirements
- Pair with `aeo-content-free` to create content that includes the right entities from the start
- Run for related prompts and compare entity overlap — shared entities reveal the core topic vocabulary

## References



## Notes

- Gemini API key stored in macOS Keychain under `google-api-key`
- Entity extraction is regex-based (no NLP libraries) — optimized for brands, stats, and products
- Common English words and sentence starters are filtered out to reduce noise
- Some false positives are expected — review the entity list and focus on high-frequency items
- Retries API calls up to 5 times with exponential backoff
