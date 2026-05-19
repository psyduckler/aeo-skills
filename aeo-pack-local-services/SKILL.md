---
name: aeo-pack-local-services
description: >
  Curated prompt pack for local service businesses (plumbers, dentists,
  lawyers, mechanics, restaurants, contractors, etc.) tracking AEO visibility.
  16 prompts covering near-me searches, ratings/reviews, pricing, emergency,
  trust signals, and specialty filtering. Template variables (service, city,
  specialty, neighborhood) are filled per workspace.
  Use when a user is setting up AEO tracking for a local service business,
  wants a starter prompt set for geographic queries, or asks for prompt
  ideas for a brick-and-mortar service provider.
---

# AEO Pack: Local Services

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-pack-local-services)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills) (v2 prompt packs)
> **Schema:** [prompt-pack-v1](https://github.com/psyduckler/aeo-skills/blob/main/schemas/prompt-pack-v1.json)

16 ready-to-track prompts for local service business visibility, covering the journey from "find a provider near me" to "is this one trustworthy?"

## Template variables

| Variable | Required | Example |
|---|---|---|
| `service` | yes | `plumber`, `dentist`, `lawyer`, `mechanic`, `restaurant`, `electrician` |
| `city` | yes | `Austin`, `San Francisco`, `Brooklyn` |
| `specialty` | no | `emergency`, `family`, `criminal`, `pediatric` |
| `neighborhood` | no | `South Congress`, `Mission District` |

## How to use this pack

```bash
npx skills add psyduckler/aeo-skills --skill aeo-pack-local-services
```

Then merge the filled-in prompts from [`prompts.json`](./prompts.json) into your `aeo.config.json`. Example for an Austin-area emergency plumbing service:

| Template | Filled |
|---|---|
| `Best {{service}} in {{city}}` | `Best plumber in Austin` |
| `Emergency {{service}} {{city}}` | `Emergency plumber Austin` |
| `{{service}} reviews {{city}}` | `plumber reviews Austin` |
| `How much does a {{service}} cost in {{city}}?` | `How much does a plumber cost in Austin?` |

## Why these prompts

Local-service AI search splits differently than B2B:

- **Proximity + service** is the dominant pattern. "best plumber in Austin" is the canonical query.
- **Trust signals** (reviews, licensure, "trustworthy") matter more than in B2B — high cost of choosing wrong.
- **Urgency** matters (emergency / open now) — Gemini's grounding behavior shifts for time-sensitive intent.
- **Educational queries** ("what to expect from a {{service}} visit") drive top-of-funnel awareness even when the user isn't actively shopping.

## Notes

- This pack pairs with **local SEO best practices**: Google Business Profile, NAP (Name/Address/Phone) consistency, review acquisition. AEO visibility tracks the AI-Overview side; classical local SEO drives the citations Gemini surfaces.
- Add `LocalBusiness` JSON-LD via [aeo-schema](../aeo-schema/) to improve machine-readability of the business page.
- Suggested first-baseline scope: 8–10 prompts × 20 samples = ~$0.05 estimated cost.
