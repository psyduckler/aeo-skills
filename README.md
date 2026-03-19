# AEO Skills — Answer Engine Optimization for AI Agents

A suite of open-source skills that help AI agents optimize content for **Answer Engines** (ChatGPT, Gemini, Perplexity, etc.). Built for [OpenClaw](https://openclaw.ai) agents but designed to be adaptable to any agent framework.

**Default model:** All skills that call the Gemini API default to **`gemini-3-flash-preview`** — the model powering Google Search AI Mode and AI Overviews. Using the same model Google uses means your measurements reflect real-world AI Overview behavior.

**Default sample count:** 20 runs per prompt. AI responses are probabilistic; a single run can miss mentions that appear 30-40% of the time. 20 samples balances accuracy with API cost.

## Skills

### Core Pipeline

The AEO loop: **Research → Create → Measure → Repeat**

| Skill | Description | Link |
|-------|-------------|------|
| **aeo-prompt-research-free** | Discover which AI prompts matter for a brand. Crawls a site, analyzes positioning, generates prioritized prompts, and audits content coverage. No API keys required. | [→ Skill](./aeo-prompt-research-free/) |
| **aeo-content-free** | Create or refresh content that AI assistants want to cite. Researches what models currently cite, builds a competitive brief, and produces citation-worthy content. No API keys required. | [→ Skill](./aeo-content-free/) |
| **aeo-analytics-free** | Track whether AI assistants mention and cite a brand over time. Measures visibility, detects trends, and identifies opportunities. Uses Gemini API free tier with grounding. | [→ Skill](./aeo-analytics-free/) |

### Analysis Tools

Understand how AI models search and what they cite.

| Skill | Description | Link |
|-------|-------------|------|
| **prompt-frequency-analyzer** | Analyze which search queries Gemini triggers when answering a prompt. Runs it multiple times with Google Search grounding and reports frequency distribution. | [→ Skill](./prompt-frequency-analyzer/) |
| **prompt-question-finder** | Find question-based Google Autocomplete suggestions for any topic. Prepends 13 question modifiers (what, how, why, will, are, do…) to discover what people actually ask. | [→ Skill](./prompt-question-finder/) |
| **aeo-grounding-query-mapper** | Map the exact search queries Gemini fires — with query clustering, pattern analysis, batch mode, and cross-prompt overlap detection. Upgraded version of prompt-frequency-analyzer. | [→ Skill](./aeo-grounding-query-mapper/) |

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

## The AEO Loop

These skills form a complete AEO workflow:

```
1. RESEARCH  →  2. CREATE/REFRESH  →  3. MEASURE  →  (repeat)
     ↑                                      |
     └──────────────────────────────────────┘
```

1. **Research** (`aeo-prompt-research-free`) — Find what questions people ask AI about your industry
2. **Analyze** (`prompt-frequency-analyzer`, `aeo-grounding-query-mapper`, `prompt-question-finder`) — Understand how AI models search and what they cite
3. **Create** (`aeo-content-free`, `aeo-schema-optimizer`) — Write content and add structured data optimized for AI citations
4. **Simulate** (`aeo-ai-overview-simulator`, `aeo-citation-gap-finder`) — Preview how your content performs in AI Overviews
5. **Measure** (`aeo-analytics-free`, `aeo-competitor-monitor`) — Track your visibility and competitors over time
6. **Repeat** — Use measurement data to refine your strategy

## Usage

Each skill has a `SKILL.md` with full instructions. Drop them into your agent's skills directory and they're ready to go.

### OpenClaw

```bash
# Install via ClawHub
clawhub install clearscope/aeo-prompt-research-free
clawhub install clearscope/aeo-content-free
clawhub install clearscope/aeo-analytics-free
clawhub install clearscope/aeo-ai-overview-simulator
clawhub install clearscope/aeo-citation-gap-finder
clawhub install clearscope/aeo-grounding-query-mapper
clawhub install clearscope/aeo-competitor-monitor
clawhub install clearscope/aeo-schema-optimizer
```

### Other Frameworks

Each skill is a self-contained directory with:
- `SKILL.md` — Instructions the agent follows (the "prompt")
- `references/` — Supporting docs and templates
- `scripts/` — Helper scripts (where applicable)

Read the `SKILL.md` files to understand the methodology, then adapt to your agent's tool-calling conventions.

## Requirements

- `web_search` — Any web search tool (Brave, Google, etc.)
- `web_fetch` — URL fetching / scraping capability
- LLM reasoning — The agent's own model
- **Gemini API key** (free from [aistudio.google.com](https://aistudio.google.com)) — Required for skills that use Gemini grounding (simulator, analyzers, monitors, analytics). Set as `GEMINI_API_KEY` env var.
- **Brave Search API key** (optional) — Used by citation-gap-finder for web search comparison. Set as `BRAVE_API_KEY` env var.

## License

MIT
