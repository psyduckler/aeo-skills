---
name: aeo-pack-b2b-saas
description: >
  Curated prompt pack for B2B SaaS AEO visibility tracking. 20 vertical-specific
  prompts covering category discovery, vendor comparison, alternatives, pricing,
  integrations, and trust signals. Designed to be merged into an existing
  aeo.config.json before running aeo-baseline. Template variables (category,
  problem, vendor, integration, company_size) are filled in per workspace.
  Use when a user is setting up AEO tracking for a B2B SaaS product, wants
  a starter prompt set for software-category visibility, or asks for prompt
  ideas for a SaaS company.
---

# AEO Pack: B2B SaaS

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-pack-b2b-saas)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills) (v2 prompt packs)
> **Schema:** [prompt-pack-v1](https://github.com/psyduckler/aeo-skills/blob/main/schemas/prompt-pack-v1.json)

20 ready-to-track prompts for B2B SaaS visibility, covering the full purchase journey from category discovery to vendor evaluation.

## What's in the pack

| Intent | # of prompts | Example |
|---|---|---|
| Category discovery | 7 | "Top {{category}} software in 2026" |
| Vendor comparison | 1 | "{{vendor}} vs alternatives: which is best?" |
| Alternatives | 4 | "Alternatives to {{vendor}}" |
| Pricing | 2 | "How much does {{vendor}} cost?" |
| Integration | 2 | "Best {{category}} that integrates with {{integration}}" |
| Trust / security | 1 | "Is {{vendor}} secure? SOC 2 / GDPR / HIPAA compliance" |
| Research / evaluation | 3 | "Is {{vendor}} worth it for {{company_size}}?" |

Full prompt list lives in [`prompts.json`](./prompts.json).

## Template variables

Each prompt may contain `{{variable}}` placeholders. Fill them in with values specific to the workspace:

| Variable | Required | Example |
|---|---|---|
| `category` | yes | `project management`, `CRM`, `analytics`, `content optimization` |
| `problem` | yes | `tracking customer support tickets`, `managing remote team standups` |
| `vendor` | no | Your brand or a key competitor — used in vendor-specific prompts |
| `integration` | no | `Slack`, `Salesforce`, `Notion`, etc. |
| `company_size` | no | `startup`, `SMB`, `mid-market`, `enterprise` |

## How to use this pack

This pack is read-only data. To use it:

1. **Install** alongside the v2 core skills:
   ```bash
   npx skills add psyduckler/aeo-skills --skill aeo-pack-b2b-saas
   ```

2. **Open `prompts.json`** in the installed pack folder.

3. **Pick the prompts that apply to your workspace** — you usually don't need all 20. A focused set of 8–12 prompts gives better signal than 20 noisy ones (and is cheaper to run).

4. **Substitute variables** for your brand. For example, with `category = "content optimization"` and `vendor = "Surfer"`:
   - "Top {{category}} software in 2026" → "Top content optimization software in 2026"
   - "Alternatives to {{vendor}}" → "Alternatives to Surfer"

5. **Merge into your `aeo.config.json`** by adding the filled-in prompts to the `prompts` array. The agent doing this should preserve any existing prompts the user already had.

6. **Run `aeo-baseline`** to start tracking.

## Why these prompts

B2B SaaS visibility splits into roughly five clusters:

- **Discovery** — buyers who don't yet know which vendor they want; they search for the category. This is where the highest acquisition leverage lives, and where hub pages compete.
- **Comparison/alternatives** — buyers who've narrowed to 2–3 vendors and want differentiation. Citation rate here drives bottom-of-funnel conversion.
- **Pricing** — late-stage; signals readiness to buy. Pages cited here matter for sales-cycle acceleration.
- **Integration** — power users with existing stacks. Citation here drives expansion / cross-sell.
- **Trust** — compliance / security signal. Often where enterprise deals get blocked.

The pack covers each cluster with 2–7 prompts so a workspace can see balanced visibility data without 50+ prompt overhead.

## Notes

- Variables are unescaped JSON strings — keep them brand-safe (no `{{` or `}}` in your substitutions).
- If you want to add custom prompts, just edit your `aeo.config.json` directly. The pack is a starting point, not a constraint.
- Suggested first-baseline scope: 10 prompts × 20 samples = ~$0.06 estimated Gemini cost.
