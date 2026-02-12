# AEO Skills — Answer Engine Optimization for AI Agents

A suite of open-source skills that help AI agents optimize content for **Answer Engines** (ChatGPT, Gemini, Perplexity, etc.). Built for [OpenClaw](https://openclaw.ai) agents but designed to be adaptable to any agent framework.

No paid APIs required. These skills use web search, web scraping, and LLM reasoning to do the heavy lifting.

## Skills

| Skill | Description | Link |
|-------|-------------|------|
| **aeo-prompt-research-free** | Discover which AI prompts matter for a brand. Crawls a site, analyzes positioning, generates prioritized prompts, and audits content coverage. | [→ Skill](./aeo-prompt-research-free/) |
| **aeo-content-free** | Create or refresh content that AI assistants want to cite. Researches what models currently cite, builds a competitive brief, and produces citation-worthy content. | [→ Skill](./aeo-content-free/) |
| **aeo-analytics-free** | Track whether AI assistants mention and cite a brand over time. Measures visibility, detects trends, and identifies opportunities. | [→ Skill](./aeo-analytics-free/) |

## The AEO Loop

These three skills form a complete AEO workflow:

```
1. RESEARCH  →  2. CREATE/REFRESH  →  3. MEASURE  →  (repeat)
```

1. **Prompt Research** — Find what questions people ask AI about your industry
2. **Content** — Write or update content optimized for AI citations
3. **Analytics** — Track if AI models actually mention you, and how that changes

## Usage

Each skill has a `SKILL.md` with full instructions. Drop them into your agent's skills directory and they're ready to go.

### OpenClaw

```bash
# Install via ClawHub
clawhub install clearscope/aeo-prompt-research-free
clawhub install clearscope/aeo-content-free
clawhub install clearscope/aeo-analytics-free
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
- **Optional:** Gemini API key (free tier) for grounded analytics

## License

MIT
