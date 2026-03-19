---
name: aeo-ai-overview-simulator
description: >
  Simulate Google AI Overviews by running prompts through Gemini 3 Flash with Google Search
  grounding. See which sources get cited, how often, and what snippets get pulled — before
  checking the real AI Overview. Track a specific domain to measure mention rate, citation
  rate, and exact excerpts. Use when a user wants to: preview what an AI Overview would
  look like for a query, see which sources Google's AI cites, measure a domain's citation
  share, or understand what content Gemini pulls from their site.
---

# AEO AI Overview Simulator

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-ai-overview-simulator)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Simulate Google AI Overviews by running prompts through the same model that powers them — **Gemini 3 Flash** with Google Search grounding.

## Why This Works

Google's AI Overviews and Search AI Mode are powered by Gemini 3 Flash (`gemini-3-flash-preview`). When you run a prompt through this model with `google_search` grounding enabled, you're simulating exactly what happens when a user triggers an AI Overview in Google Search. The model searches the web, selects sources, and generates a grounded answer — the same pipeline Google uses.

[Influence happens at retrieval, not inside the model.](https://www.clearscope.io/blog/how-to-influence-ai-answers) You can't edit training data, but you can enter the "candidate set" the model selects from when it searches. [Gemini is search-first](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence) — it searches before nearly every answer, making it more influenceable than GPT. This simulator reveals the **recurring retrieval set** — the sources, themes, and response patterns the model consistently draws from.

Running 20 samples per prompt captures the probabilistic nature of AI responses. A source cited in 15/20 runs is reliably featured; one cited in 3/20 is marginal. This frequency data is far more actionable than a single snapshot.

## Requirements

- **Gemini API key** (free from [aistudio.google.com](https://aistudio.google.com)) — set as `GEMINI_API_KEY` env var
- Python 3.9+
- No pip dependencies (stdlib only)

## Usage

```bash
# Basic — simulate an AI Overview for a query
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/simulate.py "best project management tools for startups"

# Track a specific domain
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/simulate.py "best project management tools for startups" --domain monday.com

# With response text diffing — see stable core vs volatile insertion points
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/simulate.py "best project management tools for startups" --domain monday.com --diff

# More runs for higher confidence
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/simulate.py "best project management tools for startups" --domain monday.com --runs 40

# JSON output for programmatic use
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/simulate.py "best project management tools for startups" --output json
```

Run from the skill directory. Resolve `scripts/simulate.py` relative to this SKILL.md.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `prompt` | (required) | The query to simulate |
| `--domain` | (none) | Domain to track (e.g., `example.com`) |
| `--runs` | 20 | Number of simulation runs |
| `--model` | `gemini-3-flash-preview` | Gemini model to use |
| `--concurrency` | 5 | Max parallel API calls (keep ≤5 to avoid rate limits) |
| `--output` | `text` | Output format: `text` or `json` |
| `--diff` | off | Enable response text diffing — analyze sentence stability across runs |

## Output

### Text Output

```
AI Overview Simulation: "best project management tools for startups"
Model: gemini-3-flash-preview
Runs: 20/20 successful

Top Cited Sources:
============================================================
  85% (17/20) — monday.com
  70% (14/20) — asana.com
  55% (11/20) — clickup.com
  40% (8/20)  — notion.so
  25% (5/20)  — trello.com

Search Queries Used:
============================================================
  90% (18/20) — best project management tools for startups
  45% (9/20)  — project management software comparison
  30% (6/20)  — startup project management tools 2025

Domain Tracking: monday.com
============================================================
  Mention rate: 90% (18/20 runs)
  Citation rate: 85% (17/20 runs)
  Cited URLs:
    12x — https://monday.com/blog/project-management/best-tools/
    5x  — https://monday.com/s/project-management
  Excerpts:
    - "Monday.com offers an intuitive interface ideal for startups..."
    - "For budget-conscious startups, Monday.com's free tier..."
```

### JSON Output

Structured JSON with `sources`, `queries`, `domain_tracking`, and per-run detail.

## Response Text Diffing (`--diff`)

When `--diff` is enabled, the simulator analyzes the response text across all runs to reveal the **stable core vs volatile periphery** of the recurring retrieval set:

- **Stable sentences (>80%)** — appear in almost every run. These form the core of the AI Overview and are hard to displace. They're backed by entrenched sources in the recurring retrieval set.
- **Common sentences (40-80%)** — usually included but not locked in. These are the mid-tier — present more often than not.
- **Volatile sentences (10-40%)** — the **insertion points** where your content can have impact. These sentences change between runs because the model is choosing between competing sources. Create content that wins these competitive slots.
- **Rare sentences (<10%)** — edge cases the model occasionally surfaces. Low priority.
- **Entity volatility** — brands, tools, and domains that appear inconsistently. These are **competitive slots** — the model is undecided about which entity to feature, meaning your brand can compete for these mentions.

### Text Output with `--diff`

```
Response Stability Analysis:
============================================================

Stable (>80% of runs — core of the AI Overview, hard to displace):
  [95%] Project management tools help startups organize tasks and track progress...
  [90%] Key features to look for include task management, collaboration, and...

Volatile (10-40% — insertion points, your content can influence these):
  [35%] For bootstrapped startups, free tiers from tools like ClickUp offer...
  [25%] Integration with existing tools like Slack and Google Workspace is...

Entity Volatility (brands/entities that appear inconsistently — competitive slots):
  [40%] ClickUp (8/20 runs)
  [30%] Basecamp (6/20 runs)
  [20%] Linear (4/20 runs)
```

### JSON Output with `--diff`

Adds a `response_analysis` object with `stable_sentences`, `common_sentences`, `volatile_sentences`, `rare_sentences`, and `entity_frequency` arrays.

**Note:** `--diff` adds processing time since it compares sentences across all runs. Off by default.

## How It Works

1. Sends the prompt to Gemini 3 Flash with `google_search` grounding tool enabled
2. Repeats this 20 times (default) — each run is independent
3. From each response, extracts:
   - **Response text** — the generated AI Overview
   - **Grounding sources** — URLs and titles of cited web pages
   - **Search queries** — what queries the model fired against Google Search
   - **Grounding support** — which parts of the response are supported by which sources
4. Aggregates across all runs:
   - Source citation frequency (which domains/URLs appear most)
   - Search query frequency (what the model searches for)
   - Response consistency (how stable the answer is)
5. If `--domain` provided:
   - Calculates mention rate (brand name in response text)
   - Calculates citation rate (domain in grounding sources)
   - Extracts exact excerpts where the domain is referenced

## Tips

- Start with your most important queries — the ones you'd want to appear in AI Overviews for
- Compare citation rates before and after content changes (wait 2-4 weeks for re-indexing)
- A citation rate >50% means you're reliably featured; <20% means you're marginal
- Use `--output json` to feed results into other AEO skills (analytics, gap finder)
- Pair with `aeo-content-free` to improve content that isn't getting cited
- Pair with `aeo-analytics-free` to track citation rates over time

## Further Reading

- [How to Influence AI Answers](https://www.clearscope.io/blog/how-to-influence-ai-answers) — the retrieval-first framework for AEO
- [Gemini Creates More Opportunity; GPT Is Harder to Influence](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence) — why Gemini's search-first behavior matters

## Notes

- Gemini API key stored in macOS Keychain under `google-api-key`
- Retries failed requests up to 5 times with exponential backoff
- Rate-limited to respect API quotas — keep `--concurrency` ≤5
- Results may vary between runs — that's expected and exactly why we sample multiple times
