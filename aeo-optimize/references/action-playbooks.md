# Action Playbooks

The mapping from "what the evidence file shows" to "what to recommend." Each playbook has a trigger condition (read from `aeo-data/<latest>.json`), a recommended action, an effort estimate, and an expected gain.

## P1: Mentioned but not cited

**Trigger:** `aggregates.mention_rate > 0.5` AND `aggregates.citation_rate < 0.2`.

**Diagnosis:** Gemini knows your brand exists (it shows up in the response text from training/general knowledge), but isn't pulling from your pages. You're outside the candidate set.

**Action:**
1. Identify which brand URLs *should* be cited. Pick the one that best matches the prompt's intent.
2. Fetch it. Compare against the citation blueprint in [content-blueprint.md](content-blueprint.md).
3. Apply at least 3 of these:
   - Add a TL;DR paragraph naming the top entities from `entity_universe`
   - Add `Article` JSON-LD (use [aeo-schema](../../aeo-schema/))
   - Add the entities surfaced in the prompt's `query_fanout` as sections
   - Update the publish/update date if the content is stale
   - Add an FAQ section if the prompt has question-intent fan-out queries

**Effort:** 1–2 hours per page.
**Expected gain:** Citation rate from <20% to 40–60% over 2–4 weeks.

---

## P2: Cited at a low position

**Trigger:** `aggregates.citation_rate > 0.5` AND `aggregates.avg_citation_position > 4`.

**Diagnosis:** Your page is in the candidate set but the model treats competitor pages as more authoritative. Your structural signals are weaker than theirs.

**Action:**
1. Pick 2–3 of the citations consistently at positions #1–#3. Fetch them.
2. Compare your page to theirs on the dimensions in [content-blueprint.md](content-blueprint.md): heading structure, entity coverage, schema, length, freshness.
3. Close the gap on at least 2 dimensions.

**Effort:** 2–4 hours.
**Expected gain:** Position from #5+ to #2–3 over 4–8 weeks.

---

## P3: Entity universe coverage gap

**Trigger:** `aggregates.entity_universe` shows entities with `count >= 5` (i.e. appears in ≥25% of samples) that are NOT covered on your cited brand URL.

**Diagnosis:** Gemini's recurring retrieval set for this prompt expects context that connects these entities. Your page doesn't.

**Action:**
1. List the under-covered entities (sort `entity_universe` descending; take the top 5 not on your page).
2. Add a 2–3 paragraph section to the brand URL covering each — explain the relationship between the entity and your brand/category.
3. Don't fabricate connections. If you can't honestly mention an entity, skip it.

**Effort:** ~30 min per entity.
**Expected gain:** Citation rate +10–20pp; better synthesis context.

---

## P4: Decay flagged

**Trigger:** `aeo-report` output shows decay (or compute it yourself: trailing 3-run citation_rate is ≥20% below leading 3-run).

**Diagnosis:** Your page is falling out of the recurring retrieval set. Common causes: a competitor refreshed content; the prompt's grounding queries have shifted; your content is stale.

**Action:**
1. Identify the page driving the decay (most likely the one previously cited).
2. Fetch it. Check: publish/update date, broken links, stat freshness, missing recent entities.
3. Update at least one of:
   - Publish/update date (only if you make real changes)
   - Top-3 stats with current numbers
   - Mention of recent industry events / launches
   - New section addressing any new entities in `entity_universe`
4. Re-publish (don't just save — make sure the URL serves new content with a fresh `last-modified`).

**Effort:** ~1 hour.
**Expected gain:** Reverse decay; restore to 70%+ of pre-decay rate over 2–4 weeks.

---

## P5: Cannibalization flagged

**Trigger:** `aeo-report` flags cannibalization (≥2 owned URLs each cited in ≥2 samples of the latest run). Or detect manually by scanning `samples[].citations` for multiple brand-domain URLs.

**Diagnosis:** Your own pages compete for the same retrieval slot. Gemini can't decide which to cite; both end up weaker.

**Action:**
1. Pick the canonical URL — usually the older, more comprehensive, or higher-traffic one.
2. 301-redirect the others to the canonical.
3. Merge any unique content from the redirected pages into the canonical.
4. If the pages genuinely cover different aspects (e.g. "pricing" vs "features"), don't redirect — instead, ensure their headings make the distinction obvious and they don't repeat the same H2s.

**Effort:** ~1 hour.
**Expected gain:** Concentrated citation share on one URL; cleaner signal.

---

## P6: Hub-page opportunity

**Trigger:** `aeo-report` flags a URL cited across ≥2 prompts AND coverage ≥30% of tracked prompts. Or compute manually.

**Diagnosis:** This URL has earned authority across multiple intents. It's your highest-leverage page.

**Action:**
1. Read `aggregates.entity_universe` and `query_fanout` for each prompt the hub cites for.
2. Add a section to the hub page for any entity that appears in ≥3 of those prompts but is not on the page yet.
3. Add internal links from related pages to the hub.

**Effort:** ~2 hours.
**Expected gain:** Reinforces hub status; may pick up 1–2 adjacent prompts.

---

## P7: Comparison gap on commercial-intent prompts

**Trigger:** Prompt has `intent: commercial` OR `vendor_comparison` AND the citations show competitor `<X>.com/<you>-vs-<X>` pages but no comparable page on your domain.

**Diagnosis:** People shopping for your category are reading comparison pages — and the only side of the story Gemini surfaces is your competitor's.

**Action:**
1. Identify the top 1–2 competitors based on `competitor_share` (those with the highest citation rate).
2. Draft a `<You> vs <Competitor>` page following the comparison blueprint in [content-blueprint.md](content-blueprint.md).
3. Be honest. If the competitor wins on a dimension, say so. Pages that overclaim get downranked.
4. Add `Article` JSON-LD; consider `FAQPage` JSON-LD for the "which should I choose" section.

**Effort:** ~4 hours per page.
**Expected gain:** Entry into the recurring retrieval set for that prompt; ~15–25pp citation rate lift over 4–8 weeks. Comparison pages compound — once you're seen as a comparison destination, future comparison prompts get easier.

---

## P8: Missing schema markup

**Trigger:** Cited competitor pages on a prompt have `Article` or `FAQPage` schema; your equivalent page does not. (Detect by fetching competitor URLs and inspecting their HTML for `application/ld+json` blocks.)

**Diagnosis:** Structural signal gap. Schema isn't a ranking factor in classical SEO terms, but it materially helps AI parse content.

**Action:** Use [aeo-schema](../../aeo-schema/) to generate and add the appropriate JSON-LD block(s).

**Effort:** ~15–30 min.
**Expected gain:** Improves machine readability; correlated with citation rate gains of 5–15pp in observed studies.

---

## P9: Query fan-out mismatch

**Trigger:** `aggregates.query_fanout` shows queries that your cited brand URL does not address. Example: prompt is "best travel planning tools" but Gemini fires "travel planning tools pricing" 40% of the time and your page has no pricing info.

**Diagnosis:** Gemini's search behavior reveals what users actually want from this prompt. If your page misses those dimensions, it won't synthesize as a comprehensive answer.

**Action:**
1. List the top-5 highest-frequency queries from `query_fanout`.
2. For each, check whether your cited brand URL answers it.
3. Add a section addressing each unaddressed query. Use the query itself as a heading variant.

**Effort:** ~30 min per query.
**Expected gain:** Better synthesis surface area; +5–15pp citation rate.

---

## When to recommend nothing

If the evidence file shows:
- `citation_rate > 0.7` AND `avg_citation_position <= 2` AND no decay flag

…the prompt is winning. Recommend monitoring (let `aeo-track` continue) rather than touching the page. Effort spent on a winning page is opportunity cost on a losing one.

## Prioritization

Default ranking when multiple playbooks apply:

1. **P5 Cannibalization** — first, because everything else is harder to measure when your own pages are competing
2. **P4 Decay** — reverse losses before chasing gains
3. **P6 Hub-page consolidation** — highest leverage per hour
4. **P1 Mentioned but not cited** — closest to a quick win
5. **P3 Entity coverage gap** — incremental but compounds
6. **P9 Query fan-out mismatch** — adds breadth
7. **P2 Position improvement** — useful but slower
8. **P7 Comparison gap** — high effort, high payoff
9. **P8 Schema** — small but free

Tune for the user's actual constraints. If they have 1 hour, give them P5 or P4. If they have a full week, give them P7.
