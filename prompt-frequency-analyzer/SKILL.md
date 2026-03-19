---
name: aeo-prompt-frequency-analyzer
description: Analyze what search queries Gemini uses when answering a prompt, by running it multiple times with Google Search grounding and reporting frequency distribution. Use when investigating AEO query patterns, understanding how AI models search the web for a topic, or studying the probabilistic nature of AI-triggered search queries.
---

# Prompt Frequency Analyzer

Run a prompt N times against Gemini with Google Search grounding enabled. Collect and report the frequency of search queries Gemini generates across all runs.

**Why Gemini 3 Flash?** This is the model that powers Google Search AI Mode and AI Overviews — the most important answer engine for AEO. Running prompts through Gemini 3 Flash with grounding simulates what Google's AI actually does when users ask questions. 20 samples provides reliable frequency distribution for directional insights.

## Usage

```bash
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/analyze.py "your prompt here" [--runs 20] [--model gemini-3-flash-preview] [--concurrency 5] [--output text|json]
```

Run from the skill directory. Resolve `scripts/analyze.py` relative to this SKILL.md.

## Options

- `--runs N` — Number of times to run the prompt (default: 20; 20 samples gives good directional signal)
- `--model NAME` — Gemini model to use (default: gemini-3-flash-preview — the model powering Google AI Overviews)
- `--concurrency N` — Max parallel API calls (default: 5; keep ≤5 to avoid rate limits)
- `--output text|json` — Output format (default: text)

## Output

Reports for each unique search query:
- Frequency percentage (how many runs used that query)
- Raw count
- Top web sources referenced

## Notes

- Gemini API key must be in `GEMINI_API_KEY` env var (stored in macOS Keychain under `google-api-key`)
- Each run is independent — Gemini may use different search queries each time
- Retries failed requests up to 3 times with exponential backoff
- Use `--output json` for programmatic consumption
