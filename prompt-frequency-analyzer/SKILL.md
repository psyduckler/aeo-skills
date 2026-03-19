---
name: aeo-prompt-frequency-analyzer
description: Analyze what search queries Gemini uses when answering a prompt, by running it multiple times with Google Search grounding and reporting frequency distribution. Use when investigating AEO query patterns, understanding how AI models search the web for a topic, or studying the probabilistic nature of AI-triggered search queries.
---

# Prompt Frequency Analyzer

Run a prompt N times against Gemini with Google Search grounding enabled. Collect and report the frequency of search queries Gemini generates across all runs.

**Why Gemini 3 Flash?** This is the model that powers Google Search AI Mode and AI Overviews — the most important answer engine for AEO. Running prompts through Gemini 3 Flash with grounding simulates what Google's AI actually does when users ask questions. 20 samples provides reliable frequency distribution for directional insights.

**The Retrieval Framework:** [Influence happens at retrieval, not inside the model.](https://www.clearscope.io/blog/how-to-influence-ai-answers) You can't edit a model's training data — but you can enter the "candidate set" the model selects from when it searches the web. Gemini is search-first: it fires real Google Search queries before nearly every answer, making it [more influenceable than GPT](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence). This tool reveals the **recurring retrieval set** — the queries, sources, and themes Gemini consistently draws from. Understanding query frequency is the first step to entering that set.

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
- **Intent classification** — each query is classified as `informational`, `commercial`, `navigational`, or `transactional`
- **Intent distribution summary** — breakdown of query intents across all unique queries
- Top web sources referenced

### Intent Classification

Every search query is automatically classified by intent:

- **informational** — knowledge-seeking queries ("what is X", "how does X work", "X explained")
- **commercial** — evaluation/comparison queries ("best X", "X vs Y", "top X for", "X review")
- **navigational** — brand/site-specific queries (contains domain names, "X login", "X website")
- **transactional** — purchase/action queries ("buy X", "X discount", "X free trial", "download X")

Example output:
```
Search Query Frequency:
  85% (17/20) [commercial] — best seo tools 2026
  60% (12/20) [informational] — how seo tools work
  40% (8/20) [navigational] — semrush.com features
  20% (4/20) [transactional] — seo tools free trial

Intent Distribution:
  45% informational, 30% commercial, 15% navigational, 10% transactional
```

Use intent data to understand what kind of content enters the **recurring retrieval set**. Each intent type maps to a content format the model searches for:
- **informational** → explanatory/educational content (guides, explainers)
- **commercial** → comparison/review content (vs pages, best-of lists)
- **navigational** → brand/product pages (homepages, feature pages)
- **transactional** → conversion pages (pricing, free trial, download)

If 60% of queries are commercial, the model is searching for comparison content — and that's the content type you need to create to enter the candidate set.

## Further Reading

- [How to Influence AI Answers](https://www.clearscope.io/blog/how-to-influence-ai-answers) — the retrieval-first framework for AEO
- [Gemini Creates More Opportunity; GPT Is Harder to Influence](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence) — why Gemini's search-first behavior matters

## Notes

- Gemini API key must be in `GEMINI_API_KEY` env var (stored in macOS Keychain under `google-api-key`)
- Each run is independent — Gemini may use different search queries each time
- Retries failed requests up to 3 times with exponential backoff
- Use `--output json` for programmatic consumption
