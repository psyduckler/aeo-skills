---
name: aeo-citation-gap-finder
description: >
  Compare what different AI models cite for the same prompts. Runs prompts through Gemini 3
  Flash with grounding to get Google's citations, then uses web search to approximate what
  ChatGPT and Perplexity would cite. Identifies gaps: sources cited by Google but not others,
  by others but not Google, or by all. For a target domain, shows where it appears vs where
  it's missing across AI citation landscapes.
  Use when a user wants to: find citation gaps between AI models, understand why they rank
  on one AI but not another, discover cross-platform AEO opportunities, or compare their
  visibility across Google AI, ChatGPT, and Perplexity.
---

# AEO Citation Gap Finder

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-citation-gap-finder)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Compare what different AI models cite for the same prompts. Find gaps in your cross-platform AI visibility.

## Why This Matters

Different AI models cite different sources for the same query. Google's AI Overviews (Gemini 3 Flash) use Google Search grounding. ChatGPT uses Bing. Perplexity uses its own search stack. A page that dominates Google AI citations may be invisible in ChatGPT, and vice versa.

This skill identifies those gaps so you can optimize content for cross-platform AI visibility.

## How It Works

1. **Google AI citations** — Runs the prompt 20 times through Gemini 3 Flash with `google_search` grounding. This simulates real AI Overviews and gives reliable citation frequency data.
2. **Web search citations** — Searches the same prompt via Brave Search API (or web_search tool). The top organic results approximate what ChatGPT (Bing-powered) and Perplexity would cite, since they all draw from similar web indexes.
3. **Gap analysis** — Compares the two source sets:
   - **Google-only:** Cited by Gemini but not in top web results → Google's AI has unique source preferences
   - **Web-only:** In top web results but not cited by Gemini → traditional SEO winners that AI overlooks
   - **Both:** Cited everywhere → strong cross-platform authority
4. **Domain tracking** — If you specify a domain, shows exactly where it appears vs where it's missing.

## Requirements

- **Gemini API key** (free) — set as `GEMINI_API_KEY` env var
- **Brave Search API key** (optional) — set as `BRAVE_API_KEY` env var. If not set, web search comparison is skipped.
- Python 3.9+
- No pip dependencies (stdlib only)

## Usage

```bash
# Full gap analysis with domain tracking
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
BRAVE_API_KEY=$(security find-generic-password -s "brave-search" -w) \
  python3 scripts/find_gaps.py "best SEO tools for content optimization" --domain acme.com

# Without Brave (Gemini-only analysis)
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
  python3 scripts/find_gaps.py "best SEO tools for content optimization" --domain acme.com

# JSON output
GEMINI_API_KEY=$(security find-generic-password -s "google-api-key" -w) \
BRAVE_API_KEY=$(security find-generic-password -s "brave-search" -w) \
  python3 scripts/find_gaps.py "best SEO tools for content optimization" --domain acme.com --output json
```

Run from the skill directory. Resolve `scripts/find_gaps.py` relative to this SKILL.md.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `prompt` | (required) | The query to analyze |
| `--domain` | (required) | Domain to track across citation sources |
| `--runs` | 20 | Number of Gemini grounding runs |
| `--model` | `gemini-3-flash-preview` | Gemini model to use |
| `--output` | `text` | Output format: `text` or `json` |

## Output

### Text Output

```
Citation Gap Analysis: "best SEO tools for content optimization"
Domain: acme.com
================================================================

GOOGLE AI CITATIONS (Gemini 3 Flash, 20 runs):
  85% — acme.com
  70% — surferseo.com
  55% — semrush.com
  40% — ahrefs.com

WEB SEARCH RESULTS (Brave, top 20):
  #1 — g2.com/categories/seo-content-optimization
  #2 — surferseo.com/blog/best-seo-tools
  #3 — acme.com
  ...

GAP ANALYSIS:
  Google AI Only (not in web top 20):
    - contentharmony.com (cited 25% in AI)
    - frase.io (cited 20% in AI)

  Web Only (not cited by Google AI):
    - g2.com (web rank #1, 0% AI citation)
    - backlinko.com (web rank #5, 0% AI citation)

  Both (cross-platform authority):
    - acme.com (85% AI citation, web rank #3)
    - surferseo.com (70% AI citation, web rank #2)

DOMAIN REPORT: acme.com
  Google AI: ✅ Cited in 85% of runs
  Web Search: ✅ Appears in top 20
  Status: STRONG — cross-platform visibility
  
RECOMMENDATIONS:
  → Your domain has strong Google AI visibility (85%). Maintain current content.
  → Consider targeting web-only sources' topics to strengthen Bing/ChatGPT presence.
```

## Tips

- Run against your top 5-10 target prompts to find patterns across queries
- "Google AI Only" sources reveal what Gemini specifically values — study their content structure
- "Web Only" sources that rank well but aren't AI-cited often lack extractable, direct answers
- Pair with `aeo-content-free` to fix content gaps identified by this analysis
- Pair with `aeo-ai-overview-simulator` for deeper single-prompt analysis

## Notes

- Gemini API key in macOS Keychain under `google-api-key`
- Brave Search API key in macOS Keychain under `brave-search`
- If Brave API key is not available, the tool runs Gemini-only analysis (no web comparison)
- Retries with exponential backoff for API failures
