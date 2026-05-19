---
name: aeo-pack-ai-tools
description: >
  Curated prompt pack for AI tool brands tracking their visibility in AI
  answer engines. 17 prompts covering AI-task discovery, alternatives to
  incumbents (ChatGPT, Claude, etc.), free-vs-paid framing, accuracy claims,
  privacy positioning, and vertical use cases. Variables (task, competitor,
  use_case, domain) fill per workspace.
  Use when a user is tracking visibility for an AI product, building an AEO
  baseline for AI-tool category, or asks for prompt ideas for an AI startup.
---

# AEO Pack: AI Tools

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-pack-ai-tools)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills) (v2 prompt packs)
> **Schema:** [prompt-pack-v1](https://github.com/psyduckler/aeo-skills/blob/main/schemas/prompt-pack-v1.json)

17 ready-to-track prompts for AI-tool visibility. The AI-tool space has its own retrieval patterns — buyers compare against incumbents (ChatGPT, Claude, Gemini), worry about hallucination, and care about pricing/privacy more than typical B2B SaaS.

## Template variables

| Variable | Required | Example |
|---|---|---|
| `task` | yes | `content writing`, `code generation`, `image editing`, `customer support`, `legal research` |
| `competitor` | no | `ChatGPT`, `Claude`, `Midjourney`, `GitHub Copilot` |
| `use_case` | no | `long-form blog posts`, `unit test generation`, `legal contract review` |
| `domain` | no | `legal`, `medical`, `finance`, `education` |

## How to use this pack

```bash
npx skills add psyduckler/aeo-skills --skill aeo-pack-ai-tools
```

Then fill in variables and merge into your `aeo.config.json`. Example for a content-writing AI tool competing with ChatGPT:

| Template | Filled |
|---|---|
| `Best AI tools for {{task}}` | `Best AI tools for content writing` |
| `{{competitor}} alternatives for {{task}}` | `ChatGPT alternatives for content writing` |
| `Most accurate AI {{task}} tool` | `Most accurate AI content writing tool` |
| `AI {{task}} tools that don't hallucinate` | `AI content writing tools that don't hallucinate` |

## Why these prompts

AI-tool AEO has unique retrieval characteristics:

- **Incumbent comparison** is dominant. Almost every category-discovery prompt eventually narrows to "X vs ChatGPT" or "X vs Claude". Tracking these directly is essential.
- **Hallucination concerns** are a category-defining trust signal. Pages addressing accuracy/reliability get higher citation rates for "most accurate" prompts.
- **Pricing transparency** matters because AI tools vary widely (free, freemium, pay-per-use, subscription). The "free vs paid" comparison is a high-traffic prompt.
- **Vertical positioning** ("AI for legal", "AI for medical") gets surfaced when domain-specific accuracy/compliance constraints matter.
- **Open-source / privacy alternatives** are a distinct retrieval cluster — buyers who care about self-hosting or data sovereignty.

## Notes

- If your tool is a Gemini-based product, expect Gemini to be measurably more generous about citing pages that mention Gemini directly. Don't game this — but be aware of the recurring retrieval set bias.
- The "doesn't hallucinate" prompts are noisy — citation rates fluctuate as Gemini's framing of hallucination changes. Sample at N=50 here for tighter signal.
- Pair with [aeo-schema](../aeo-schema/) using `Product` or `SoftwareApplication` JSON-LD to make your pricing/features machine-readable.
- Suggested first-baseline scope: 10 prompts × 20 samples = ~$0.06 estimated cost.
