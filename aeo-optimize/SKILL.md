---
name: aeo-optimize
description: >
  Turn an AEO visibility baseline into a concrete content work queue. Reads
  the latest aeo-evidence-v1 file from aeo-data/, optionally reads aeo-report
  output and fetched page content, then produces a prioritized Markdown task
  list. Each task is evidence-backed: it cites the prompt_id, the metric
  driving the recommendation (mention rate, citation rate, position, decay,
  cannibalization, hub-page opportunity), and concrete next steps (refresh
  URL X, create page A vs B, add JSON-LD type Z, surface entity Y).
  SKILL.md-only — the agent reasons over the methodology in references/ and
  applies it to the user's data. No script, no API calls.
  Use when a user wants to: turn baseline data into action, decide what
  content to refresh or create next, plan an AEO sprint, build a backlog
  from a visibility report, or close the gap between "what's broken" and
  "what should I do about it".
---

# AEO Optimize

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-optimize)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills) (v2 Core)
> **Reads:** `aeo-data/*.json` (evidence) + optional `aeo-reports/*.md`
> **Writes:** A Markdown work queue (printed to chat or saved to file)

The action layer of the AEO loop. `aeo-baseline` measures, `aeo-report` analyzes, `aeo-optimize` recommends.

## How this skill works

This is a SKILL.md-only skill — there is no script to run. The agent reads the methodology in this file plus the references in `references/`, then applies that methodology to the user's actual data.

The agent should:

1. **Locate the latest evidence file.** Sort `aeo-data/*.json` by run timestamp and load the latest.
2. **Optionally read the latest aeo-report output** at `aeo-reports/*.md` for pre-computed trend signals.
3. **Optionally fetch one or more brand URLs** when a recommendation involves a specific page (use `web_fetch`).
4. **Apply the playbooks in `references/action-playbooks.md`** to map gaps in the data to concrete actions.
5. **Output a prioritized Markdown work queue** with the structure shown below.

## Output format

```markdown
# AEO Action Plan — <brand>

Generated from `aeo-data/<latest-evidence-file>` covering prompts: <list>.

## Quick wins (high impact, low effort)

### 1. Refresh `<url>` with entity "<entity>"
**Evidence:** Mentioned in 14/20 Gemini responses for prompt `<prompt_id>` but missing from your page (`citation_rate = 60%, position avg #4.2`).
**Action:** Add a section that names "<entity>" and explains how it relates to <topic>. Aim for 2–3 sentences of natural mention.
**Effort:** ~30 min
**Expected gain:** Citation rate from 60% → 75–80% based on the recurring retrieval set.

### 2. Add JSON-LD `<schema-type>` to `<url>`
**Evidence:** All cited competitor pages on prompt `<prompt_id>` include `<schema-type>` markup; your page does not.
**Action:** Use [aeo-schema](../aeo-schema/) to generate the JSON-LD block.
**Effort:** ~15 min
**Expected gain:** Improves structural signals for citation.

## Strategic plays (higher effort, higher impact)

### 3. Create comparison page: `<You> vs <Competitor>`
**Evidence:** 8/20 Gemini runs for prompt `<prompt_id>` cited a comparison page from <competitor> (`<competitor>.com/<you>-vs-<competitor>`). You have no comparison page in your sitemap.
**Action:** Draft a 1500–2000 word vs page covering pricing, features, integrations, ideal use case.
**Effort:** ~4 hours
**Expected gain:** Entry into the recurring retrieval set for this prompt; ~15–25pp lift in citation rate over 4–8 weeks.

## Maintenance (alerts, decay)

### 4. Refresh `<url>` — citation rate decaying
**Evidence:** prompt `<prompt_id>` shows citation rate decay: 80% → 45% over the last 6 baselines (METHODOLOGY.md §4: HIGH severity).
**Action:** Audit the page for stale claims, outdated stats, missing competitive context. Update timestamps. Re-publish.
**Effort:** ~1 hour
**Expected gain:** Reverse the decay; restore to 70%+ over 2–4 weeks.

## Hub-page consolidation

### 5. Double down on `<url>` — your strongest hub
**Evidence:** This URL is cited across 4 of 6 tracked prompts (66% coverage). It is your highest-leverage page.
**Action:** Add 3–5 additional sections covering the entities and questions surfaced in `aeo-report` for those prompts. One page that wins more prompts is cheaper than five pages winning one each.
**Effort:** ~2 hours
**Expected gain:** Reinforces hub status; may pick up additional prompts.

## Cannibalization fixes

### 6. Consolidate `<url-a>` and `<url-b>`
**Evidence:** Both pages are cited for prompt `<prompt_id>` with 60%/40% share — the model can't decide which to surface. Internal competition is diluting both.
**Action:** Pick the canonical URL (the one ranking better; usually the older or more comprehensive). 301 the other. Merge unique content into the canonical.
**Effort:** ~1 hour
**Expected gain:** Concentrated citation share on one URL; cleaner signal to the model.
```

Every recommendation includes: **the prompt_id driving it**, **the metric/evidence backing it**, **the specific action**, **the rough effort estimate**, and **the expected gain**. No vibes, no vague advice.

## How to choose what to recommend

Read [references/action-playbooks.md](references/action-playbooks.md) for the full mapping. Summary:

| Gap signal in the evidence file | Recommended action |
|---|---|
| Brand mentioned but not cited (`mention_rate > 0.5`, `citation_rate < 0.2`) | Add/improve a brand URL that should be cited; check schema; submit to Search Console |
| Brand cited at position #5+ when competitors are at #1 | Improve content depth/freshness on the brand URL; entity coverage |
| Entity in `entity_universe` with high frequency but not on your page | Add a section covering that entity |
| Decay flagged in `aeo-report` | Refresh the page; update stats; add new sections; re-publish |
| Cannibalization flagged | Consolidate competing URLs; 301; canonical |
| Hub-page coverage ≥30% | Double down — add sections for adjacent prompts |
| Citation gap on comparison-intent prompt (no comparison page) | Build a `<You> vs <Competitor>` page |
| No JSON-LD on a cited brand page when competitors have it | Run [aeo-schema](../aeo-schema/) |

## Pairs With

- **[aeo-baseline](https://github.com/psyduckler/aeo-skills/tree/main/aeo-baseline)** — produces the evidence file this skill reads
- **[aeo-report](https://github.com/psyduckler/aeo-skills/tree/main/aeo-report)** — produces trend reports this skill can cross-reference
- **[aeo-schema](https://github.com/psyduckler/aeo-skills/tree/main/aeo-schema)** — execute the "add JSON-LD" recommendations
- **[aeo-content-free](https://github.com/psyduckler/aeo-skills/tree/main/aeo-content-free)** — execute the "create new page" recommendations

## Principles

1. **Every recommendation must cite evidence.** If you can't point to a specific prompt + metric, the recommendation is vibes.
2. **Prioritize by leverage, not novelty.** Refreshing a hub page is almost always higher-leverage than creating a new page.
3. **One owner per recommendation.** Tasks that need cross-team coordination are weaker than tasks one person can ship.
4. **Effort estimates matter.** "Refresh a page" is 1 hour; "build a new comparison page" is 4. Knowing this helps the user pick what fits their week.
5. **Be honest about uncertainty.** Expected gain is a directional estimate, not a promise. At N=20 samples, Wilson 95% CI widths are ~30pp — small movements are noise.

## Notes for the agent

- If `aeo-data/` is empty or missing, recommend running `aeo-baseline` first — do not invent recommendations from prior knowledge.
- If only one evidence file exists, you can still recommend based on snapshot data, but flag that decay and trend signals are unavailable.
- If multiple brand URLs are cited for the same prompt, consider cannibalization before recommending a refresh — fix the duplicate problem first.
- When fetching brand URLs for context, respect rate limits. The user's `web_fetch` allowance matters.
- Default output: print the work queue to chat. If the user asks, save it to `aeo-reports/<timestamp>-action-plan.md`.
