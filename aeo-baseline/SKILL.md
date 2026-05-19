---
name: aeo-baseline
description: >
  Take an atomic AI visibility baseline for a brand. Runs each configured prompt
  20 times against Gemini with Google Search grounding, extracts every signal
  (brand mentions, citations, citation position, query fan-out, entities,
  sentiment, competitor citations) from those same 20 responses, computes
  Wilson 95% confidence intervals, applies the aeo-v1 visibility score, and
  writes an append-only JSON evidence file conforming to schemas/aeo-evidence-v1.json.
  Use when a user wants to: measure where their brand sits in AI search
  retrieval, establish a starting visibility baseline before content work,
  produce a single evidence file that aeo-report and aeo-optimize can consume,
  or get a one-shot visibility snapshot for a specific prompt.
---

# AEO Baseline

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-baseline)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)
> **Methodology:** [aeo-v1](https://github.com/psyduckler/aeo-skills/blob/main/METHODOLOGY.md)
> **Output schema:** [aeo-evidence-v1](https://github.com/psyduckler/aeo-skills/blob/main/schemas/aeo-evidence-v1.json)

The atomic measurement primitive for AI visibility tracking. One command, one run, one evidence file with every signal you can extract from 20 grounded Gemini responses per prompt.

## The Retrieval Framework

You cannot edit a model's training data. But for search-grounded models like Gemini, you can influence what enters the **candidate set** the model selects from when it grounds an answer. That candidate set — the recurring retrieval set for a prompt — is what this skill measures.

Every metric in the output traces back to a saved raw response. If you disagree with the score, recompute it from the evidence file — components are stored separately.

## Requirements

- **Gemini API key** (free from [aistudio.google.com](https://aistudio.google.com)) — set as `GEMINI_API_KEY`
- **Python 3.9+** — stdlib only, no pip install needed
- A workspace config — either an existing `aeo.config.json` (produced by `aeo-init`) or a one-off via `--prompt`

## Usage

```bash
# Default: read aeo.config.json, run 20 samples per prompt, write to aeo-data/
GEMINI_API_KEY="$GEMINI_API_KEY" python3 scripts/baseline.py

# Verify the API key works without running a measurement
python3 scripts/baseline.py --doctor

# Print projected cost without making any API calls
python3 scripts/baseline.py --estimate-cost

# Run a single ad-hoc prompt (skips most of the config)
GEMINI_API_KEY="$GEMINI_API_KEY" python3 scripts/baseline.py --prompt "best CRM for small business"

# Override sample count for higher-confidence measurements
GEMINI_API_KEY="$GEMINI_API_KEY" python3 scripts/baseline.py --runs 50

# Skip the cost confirmation prompt (for cron / CI use)
GEMINI_API_KEY="$GEMINI_API_KEY" python3 scripts/baseline.py --yes
```

Run from the skill directory. Resolve `scripts/baseline.py` relative to this SKILL.md.

## Options

| Option | Default | Description |
|---|---|---|
| `--config` | `aeo.config.json` | Path to workspace config |
| `--output-dir` | (from config) | Where to write the evidence JSON file |
| `--runs N` | (from config, fallback 20) | Samples per prompt |
| `--concurrency N` | (from config, fallback 5) | Max parallel API calls |
| `--model NAME` | `gemini-3-flash-preview` | Gemini model identifier |
| `--prompt "TEXT"` | — | Run a single ad-hoc prompt instead of the config |
| `--prompt-id ID` | `adhoc` | ID to record when `--prompt` is used |
| `--doctor` | — | Verify API key with a 1-token probe; exit |
| `--estimate-cost` | — | Print projected cost; exit |
| `--yes` / `-y` | — | Skip the cost-confirmation prompt |

## Signals Extracted

Each of the 20 samples per prompt contributes to:

- **Brand mention** — whole-word match for the brand name and any aliases
- **Brand citation** — domain match in grounding chunks, with 1-based position
- **Competitor mention** — text + grounding match for each tracked competitor
- **Query fan-out** — the literal Google Search queries Gemini fired
- **Entities** — proper-noun extraction (CamelCase + multi-word capitalized)
- **Sentiment** — ±50-char window scan for positive/negative keywords near each brand mention
- **Recommendation** — brand mention in the trailing 25% of the response

All extraction is deterministic and rule-based — same response in, same numbers out. Sentiment will move to LLM-based in v1.2.

## Output

A single file: `<output-dir>/run_<UTC-timestamp>.json` matching the public [aeo-evidence-v1](https://github.com/psyduckler/aeo-skills/blob/main/schemas/aeo-evidence-v1.json) schema.

The file is **append-only** by design — each run produces a new timestamped file. Trend analysis is done by `aeo-report` reading the whole directory.

Top-level layout:

```jsonc
{
  "schema_version": "aeo-evidence-v1",
  "workspace": {...},
  "run": {"run_id", "timestamp", "provider", "model", "samples", "methodology_version", "estimated_cost_usd", "actual_cost_usd", "latency_ms_p50"},
  "prompts": [
    {
      "prompt_id", "prompt_text", "intent",
      "successful_samples", "failed_samples",
      "samples": [/* each sample with raw text, queries, citations, mentions, entities */],
      "aggregates": {"mention_rate", "mention_rate_ci", "citation_rate", ..., "query_fanout", "entity_universe", "competitor_share", "sentiment_distribution"},
      "visibility_score": {"value", "methodology_version", "components": {/* mention, citation, position, recommendation, sentiment */}}
    }
  ]
}
```

## Cost Management

This skill respects two limits from `aeo.config.json`:

- `limits.confirm_over_usd` — if the projected cost exceeds this, the user is prompted to confirm before any API calls (default $5)
- `limits.max_daily_cost_usd` — informational only in v1; honored by `aeo-track` for scheduled runs (default $25)

Override the per-sample cost estimate via env var:

```bash
export GEMINI_COST_PER_SAMPLE_USD=0.0005
```

Use `--estimate-cost` to dry-run.

## Scoring (aeo-v1)

The composite visibility score is a transparent weighted average, scaled 0–100:

```
visibility_score = 100 × (
    0.30 × mention_rate
  + 0.25 × citation_rate
  + 0.20 × position_score
  + 0.15 × recommendation_rate
  + 0.10 × sentiment_score
)
```

Every component is stored in the evidence file. To re-score with different weights, modify them and recompute from the raw samples — no new API calls needed.

See [METHODOLOGY.md](https://github.com/psyduckler/aeo-skills/blob/main/METHODOLOGY.md) for the full definitions.

## Pairs With

- **[aeo-init](https://github.com/psyduckler/aeo-skills/tree/main/aeo-init)** (coming) — creates `aeo.config.json`
- **[aeo-track](https://github.com/psyduckler/aeo-skills/tree/main/aeo-track)** (coming) — installs a daily cron to re-run this skill
- **[aeo-report](https://github.com/psyduckler/aeo-skills/tree/main/aeo-report)** (coming) — reads accumulated evidence files and generates Markdown + SVG trend reports
- **[aeo-optimize](https://github.com/psyduckler/aeo-skills/tree/main/aeo-optimize)** (coming) — reads the latest evidence file and recommends concrete content actions

## Notes

- Each sample's raw response text is stored in the evidence file. If you want to reduce file size, you can post-process the JSON to drop `samples[].raw_response_text` after extraction.
- Failed samples (HTTP errors, timeouts) are recorded with `error` rather than dropped silently. `successful_samples` and `failed_samples` are explicit at the prompt level.
- Wilson 95% CI is reported alongside every proportion metric — at N=20, expect a width of ~30 percentage points for mid-range rates. See METHODOLOGY.md §2 for the full table.
- Gemini grounding occasionally rate-limits at high concurrency. `_shared.call_gemini` retries with exponential backoff up to 5 attempts.
