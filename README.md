# AEO Skills — Answer Engine Optimization for AI Agents

[![skills.sh](https://skills.sh/b/psyduckler/aeo-skills)](https://skills.sh/psyduckler/aeo-skills)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Open-source agent skills that measure, track, and improve a brand's visibility in AI answer engines (Gemini AI Overviews, ChatGPT, Perplexity). **BYOK** (bring your own Gemini key), **evidence-first** (every metric traces back to a raw response), **no vendor lock-in** (data lives in your project as JSON).

## Quickstart

```bash
# 1. Install all skills into your agent (Claude Code, Cursor, Codex, OpenCode, etc.)
npx skills add psyduckler/aeo-skills

# 2. Set your Gemini key (free from aistudio.google.com)
export GEMINI_API_KEY="your_key_here"

# 3. Ask your agent: "Use aeo-analytics-free to track AI visibility for tabiji.ai"
```

The skills.sh CLI works with [Claude Code, Cursor, Codex, OpenCode, and 50+ other agents](https://skills.sh/docs).

### Alternative installs

```bash
# ClawHub (for OpenClaw agents)
clawhub install psyduckler/aeo-analytics-free

# Manual: clone and point your agent at the skill folders
git clone https://github.com/psyduckler/aeo-skills
```

### Install a single skill

```bash
# Only install the analytics tracker (skills are self-contained)
npx skills add psyduckler/aeo-skills --skill aeo-analytics-free
```

## What's coming in v2

A streamlined six-skill suite (`aeo-init`, `aeo-baseline`, `aeo-track`, `aeo-report`, `aeo-optimize`, `aeo-schema`) plus a single public **evidence schema** (`schemas/aeo-evidence-v1.json`) and **methodology document** ([METHODOLOGY.md](METHODOLOGY.md)) that every skill reads from and writes to.

The v1 skills below remain installable. v2 is being developed in parallel and will land on this branch as it stabilizes.

---

## Why Gemini Is the Only Model That Matters for AEO (Right Now)

We ran a 7-day study across 4 prompt types × 2 models (ChatGPT GPT-5 and Gemini), analyzing 1,963 responses. The results are clear: **optimizing for Gemini is the only AEO strategy that makes sense today.**

### Gemini searches the web 100% of the time. ChatGPT only ~45%.

Gemini issued web searches on **every single response** and used **265 unique search queries**. ChatGPT only searched **45% of the time** with just **4 unique queries total**. That's a 66× difference in search diversity.

![Gemini vs ChatGPT search behavior](./assets/gemini-vs-chatgpt-search-behavior.png)

**What this means:** Gemini's responses are deeply dependent on live web content — your content's presence (or absence) in search results directly determines whether Gemini cites you. ChatGPT mostly relies on its parametric knowledge and rarely searches, making it nearly impossible to influence through content optimization alone.

**Why ChatGPT doesn't search much:**
- **Cost** — Web search is expensive at ChatGPT's scale. Every search query adds latency and API costs.
- **Legal risk** — There are ongoing concerns about ChatGPT searching Google at scale.
- **Architecture** — ChatGPT was designed as a parametric model first, with search as an optional enhancement. Gemini was built with Google Search as a native, always-on capability.

### A single 20-sample run captures 74–100% of query diversity

Our control run analysis shows that a single batch of responses captures the vast majority of the search query universe for any given prompt. Informational prompts had **100% coverage** — zero new queries over 7 days. Even dynamic prompts (research, fresh, commercial) showed **74–83% coverage** from the initial sample.

![Control run coverage](./assets/control-run-coverage.png)

**This is why we default to 20 samples.** It's enough to reliably map the query landscape for a prompt — catching most of the search queries Gemini will use, without burning excessive API credits.

### The bottom line

If you're doing AEO/GEO today, **focus on Gemini**. It's the model that:
1. **Always searches the web** — your content can actually influence its responses
2. **Powers Google AI Overviews** — the largest answer engine by traffic (25% of Google searches trigger AI Overviews)
3. **Uses diverse search queries** — creating multiple pathways for your content to get discovered and cited
4. **Is measurable** — the Gemini API with grounding lets you simulate exactly what the model does

---

## Understanding Sample Sizes and Confidence

We default to 20 samples per prompt. Here's what that means statistically (Wilson 95% CI):

| Observed Rate | 95% Confidence Interval | Interpretation |
|---------------|------------------------|----------------|
| 0% (0/20) | 0% – 17% | Likely not cited, but can't rule out rare appearances |
| 25% (5/20) | 9% – 49% | Weak signal — could be noise or genuine low-frequency citation |
| 50% (10/20) | 27% – 73% | Directional — you're in the candidate set but not dominant |
| 75% (15/20) | 51% – 91% | Strong signal — consistently part of the recurring retrieval set |
| 100% (20/20) | 83% – 100% | Very strong — core part of the retrieval set for this prompt |

### When to Use More Samples

- **20 samples (default):** Directional insights, initial audits, identifying obvious gaps
- **50 samples:** Competitive analysis where small differences matter (source authority, competitor monitoring)
- **100 samples:** High-confidence measurements for stakeholder reporting

All scripts accept `--runs N` to override the default. See [METHODOLOGY.md](METHODOLOGY.md) for the full statistical reasoning.

---

## Skills

### v2 Core (new)

The streamlined v2 measurement core. Built against [`schemas/aeo-evidence-v1.json`](schemas/aeo-evidence-v1.json) and [METHODOLOGY.md](METHODOLOGY.md). More v2 skills land in subsequent PRs.

| Skill | Description | Link |
|-------|-------------|------|
| **aeo-init** | Initialize an AEO workspace. Interactive or flag-driven, generates a schema-conforming `aeo.config.json` with brand, competitors, prompts, providers, sampling, and spend limits. Never calls an API. | [→ Skill](./aeo-init/) |
| **aeo-baseline** | Atomic AI visibility measurement. Runs each configured prompt 20× against Gemini with grounding, extracts every signal (mentions, citations, position, query fan-out, entities, sentiment, competitors) from the same 20 responses, computes Wilson 95% CIs, and writes one append-only JSON evidence file. Built-in `--doctor` and `--estimate-cost` modes; honors spend caps. | [→ Skill](./aeo-baseline/) |
| **aeo-track** | Schedule recurring `aeo-baseline` runs. Generates a launchd plist (macOS) or crontab entry (Linux) plus a wrapper script that loads `.env` and invokes baseline. Dry-run by default; `--apply` installs. Idempotent install/remove with per-workspace state. | [→ Skill](./aeo-track/) |
| **aeo-report** | Read accumulated `aeo-data/*.json` and produce a visibility trend report: Markdown + single-file HTML with embedded SVG line charts. Surfaces decay (declining citation rate), cannibalization (multiple owned URLs competing), hub-page opportunities (one URL across many prompts), and competitor share shifts. Pure analysis — no API calls. | [→ Skill](./aeo-report/) |

### Core Pipeline (v1)

The AEO loop: **Research → Create → Measure → Repeat**

| Skill | Description | Link |
|-------|-------------|------|
| **aeo-prompt-research-free** | Discover which AI prompts matter for a brand. Crawls a site, analyzes positioning, generates prioritized prompts, audits content coverage. No API keys required. | [→ Skill](./aeo-prompt-research-free/) |
| **aeo-content-free** | Create or refresh content that AI assistants want to cite. Researches what models currently cite, builds a competitive brief, produces citation-worthy content. No API keys required. | [→ Skill](./aeo-content-free/) |
| **aeo-analytics-free** | Track whether AI assistants mention and cite a brand over time. Measures visibility, detects trends, identifies opportunities. Uses Gemini API free tier with grounding. | [→ Skill](./aeo-analytics-free/) |

### Analysis Tools

Understand how AI models search and what they cite.

| Skill | Description | Link |
|-------|-------------|------|
| **aeo-prompt-frequency-analyzer** | Analyze which search queries Gemini triggers when answering a prompt. Runs it multiple times with Google Search grounding and reports frequency distribution. | [→ Skill](./aeo-prompt-frequency-analyzer/) |
| **aeo-prompt-question-finder** | Find question-based Google Autocomplete suggestions for any topic. Prepends 13 question modifiers (what, how, why, will, are, do…) to discover what people actually ask. | [→ Skill](./aeo-prompt-question-finder/) |
| **aeo-grounding-query-mapper** | Map the exact search queries Gemini fires — with query clustering, pattern analysis, batch mode, and cross-prompt overlap detection. Upgraded version of aeo-prompt-frequency-analyzer. | [→ Skill](./aeo-grounding-query-mapper/) |

### Simulation & Monitoring

Simulate AI Overviews, compare AI models, and track competitors.

| Skill | Description | Link |
|-------|-------------|------|
| **aeo-ai-overview-simulator** | Simulate Google AI Overviews by running prompts through Gemini 3 Flash with grounding. See which sources get cited, how often, and track a specific domain's citation rate. | [→ Skill](./aeo-ai-overview-simulator/) |
| **aeo-citation-gap-finder** | Compare what Google AI cites vs what web search surfaces. Find cross-platform citation gaps between Gemini, ChatGPT, and Perplexity. | [→ Skill](./aeo-citation-gap-finder/) |
| **aeo-competitor-monitor** | Track competitor citations in AI Overviews over time. Append-only data file with trend analysis and citation share reports. | [→ Skill](./aeo-competitor-monitor/) |

### Optimization

Improve your content's AI-readiness.

| Skill | Description | Link |
|-------|-------------|------|
| **aeo-schema-optimizer** | Analyze pages and generate structured data (JSON-LD) optimized for AI citation. Includes templates for Article, FAQ, HowTo, Product, LocalBusiness, and BreadcrumbList. | [→ Skill](./aeo-schema-optimizer/) |

### Advanced Strategy

Deep analysis for competitive AEO.

| Skill | Description | Link |
|-------|-------------|------|
| **aeo-source-authority-profiler** | Analyze why certain sources get cited. Fetches top-cited pages and profiles them (word count, schema, freshness, entities) to build a "citation blueprint." | [→ Skill](./aeo-source-authority-profiler/) |
| **aeo-cannibalization-detector** | Detect when your own pages compete against each other for the same AI prompts. Scores severity and recommends consolidation or differentiation. | [→ Skill](./aeo-cannibalization-detector/) |
| **aeo-freshness-decay-tracker** | Track how citation rates change over time. Detects content decay, correlates with freshness, flags pages needing urgent refresh. | [→ Skill](./aeo-freshness-decay-tracker/) |
| **aeo-entity-extractor** | Extract the specific entities (brands, people, stats, tools) that Gemini mentions in responses. Find entity gaps in your content. | [→ Skill](./aeo-entity-extractor/) |
| **aeo-multi-prompt-strategy** | Find authority hub pages cited across multiple prompts. Optimize one page to win many prompts instead of building separate pages for each. | [→ Skill](./aeo-multi-prompt-strategy/) |

---

## The AEO Loop

These skills form a complete AEO workflow:

```
1. RESEARCH  →  2. CREATE/REFRESH  →  3. MEASURE  →  4. STRATEGIZE  →  (repeat)
     ↑                                                       |
     └───────────────────────────────────────────────────────┘
```

1. **Research** (`aeo-prompt-research-free`) — Find what questions people ask AI about your industry
2. **Analyze** (`aeo-prompt-frequency-analyzer`, `aeo-grounding-query-mapper`, `aeo-prompt-question-finder`) — Understand how AI models search and what they cite
3. **Create** (`aeo-content-free`, `aeo-schema-optimizer`) — Write content and add structured data optimized for AI citations
4. **Simulate** (`aeo-ai-overview-simulator`, `aeo-citation-gap-finder`) — Preview how your content performs in AI Overviews
5. **Measure** (`aeo-analytics-free`, `aeo-competitor-monitor`, `aeo-freshness-decay-tracker`) — Track your visibility, competitors, content decay over time
6. **Profile** (`aeo-source-authority-profiler`, `aeo-entity-extractor`) — Understand WHY top sources get cited
7. **Strategize** (`aeo-multi-prompt-strategy`, `aeo-cannibalization-detector`) — Find authority hub opportunities and fix self-competition
8. **Repeat** — Use insights to prioritize research and content creation

---

## Requirements

- **`npx`** (Node.js 18+) — for the [skills.sh](https://skills.sh) installer
- **Python 3.9+** — most measurement skills are Python stdlib only (no `pip install` required)
- **Gemini API key** (free from [aistudio.google.com](https://aistudio.google.com)) — Required for skills that use Gemini grounding (simulator, analyzers, monitors, analytics). Set as `GEMINI_API_KEY` env var.
- **Brave Search API key** (optional) — Used by `aeo-citation-gap-finder` for web search comparison. Set as `BRAVE_API_KEY` env var.
- **Web search + web fetch** — Provided by your agent (Claude Code, Cursor, etc.); used by no-API-key skills.

---

## Structure

Each skill is a self-contained directory:

```
aeo-<skill-name>/
├── SKILL.md         # Instructions the agent follows (the "prompt")
├── references/      # Supporting docs and templates (optional)
└── scripts/         # Helper scripts (where applicable)
    ├── <main>.py
    └── _shared.py   # Vendored Gemini client helpers (auto-synced)
```

The `_shared.py` in each skill is a vendored copy of common Gemini helpers. They are kept byte-identical via `tests/test_compile.py`; to update them all at once, run `scripts/sync-shared.sh`.

---

## Schemas (v2 preview)

Public, versioned data schemas live in `schemas/`:

- [`schemas/aeo-evidence-v1.json`](schemas/aeo-evidence-v1.json) — The output format every measurement skill writes. The moat.
- [`schemas/aeo-config-v1.json`](schemas/aeo-config-v1.json) — Workspace configuration.
- [`schemas/prompt-pack-v1.json`](schemas/prompt-pack-v1.json) — Vertical prompt pack format.

See [METHODOLOGY.md](METHODOLOGY.md) for the retrieval framework, sampling rationale, and scoring formula.

---

## Tests

```bash
python3 tests/test_compile.py
```

Verifies that every script compiles, accepts `--help`, every skill vendors its own `_shared.py`, all vendored copies are byte-identical, and missing-key error handling is clean.

---

## Contributing

Contributions welcome — especially:
- New skills (see [CONTRIBUTING.md](CONTRIBUTING.md))
- Vertical prompt packs (industry-specific prompt sets)
- Additional provider adapters (OpenAI, Anthropic, Perplexity for v2)
- Real-world example reports

---

## License

MIT
