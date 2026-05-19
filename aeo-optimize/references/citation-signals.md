# Citation Signals Reference

What makes a page get cited by Gemini (and the AI Overviews it powers). Synthesized from the [7-day retrieval study](https://github.com/psyduckler/aeo-skills#why-gemini-is-the-only-model-that-matters-for-aeo-right-now) and observed patterns in the recurring retrieval set.

## Hierarchy of signals

In rough order of how strongly each correlates with citation rate (per the patterns surfaced by `aeo-source-authority-profiler`):

1. **Topical authority on the prompt's intent** — the page is recognized as a canonical answer for *this kind of question*
2. **Entity coverage** — the page names the entities Gemini searches for
3. **Structured data** — JSON-LD (especially `Article`, `FAQ`, `HowTo`) makes the page machine-readable
4. **Freshness signals** — recent publish/update dates; explicit timestamps; current stats
5. **Comparison/list framing** — pages structured as "best X" / "X vs Y" enter the retrieval set for commercial-intent prompts
6. **Domain authority** — overall sitewide trust still matters, but less than classical SEO
7. **Page depth** — word count and section count; thin pages lose to comprehensive ones

## The "candidate set" framing

Gemini doesn't rank pages the way Google Search results do. It builds a candidate set of pages for each prompt by running multiple search queries, then synthesizes an answer drawing on the candidate set. Citation = your URL appears in the candidate set.

Practical implication: **you don't need to rank #1 organically**. You need to be one of the ~5–10 pages Gemini retrieves for the prompt's search queries. That's a different (often lower) bar.

## What's in the evidence file you can use

From `aeo-data/<run>.json` for any prompt:

| Field | What it tells you |
|---|---|
| `aggregates.citation_rate` | Fraction of samples where your domain was cited |
| `aggregates.avg_citation_position` | Mean 1-based position when cited (lower is better) |
| `aggregates.query_fanout` | The actual search queries Gemini fired — match your content's language to these |
| `aggregates.entity_universe` | Every entity Gemini mentioned across the 20 samples — these are the topical anchors |
| `aggregates.competitor_share` | Which competitor domains dominate the recurring retrieval set |
| `samples[].citations` | Per-sample citation lists — exact URLs cited, in position order |

The richest signal is `query_fanout` + `entity_universe` + `competitor_share`. Together they tell you what Gemini is searching for, what topics it expects to see, and who currently wins.

## Patterns that predict high citation

Pages with most of these get cited more:

- **Headline matches the prompt's intent.** "Best AI Travel Apps in 2026" cites for commercial-intent prompts. "What Is an AI Travel App?" cites for informational prompts.
- **Explicit comparison structure.** Pages with `<table>` comparing options, or repeated `<h2>` blocks per item, are easy for Gemini to surface as a list.
- **Entity density.** Mention the brands, products, places, and statistics that show up in `entity_universe` — natural mentions, not keyword stuffing.
- **Freshness on the page.** A visible "Updated: <date>" with a current date. Avoid 2-year-old listicles.
- **JSON-LD schema.** Use `Article` for posts, `FAQPage` for FAQs, `HowTo` for step-by-steps, `Product` for products. See [aeo-schema](../../aeo-schema/) for templates.
- **Direct answer in the first 100 words.** Lead with the answer, then explain. Gemini quotes early content more.
- **Author/publisher attribution.** `Article` schema with `author` and `publisher` tells Gemini who wrote it.

## Patterns that predict low citation

Pages with these usually don't cite:

- Thin content (<500 words) without unique value
- Blog posts with no clear answer to a named question
- Marketing copy without entity coverage
- Pages with no structured data
- "Listicle" pages where the actual brand entries are below the fold
- Pages buried behind an interstitial, login, or aggressive consent dialog
- Pages with stale dates or broken links

## When the evidence says "you have content but it's not cited"

Diagnostic flow:

1. Check `aggregates.mention_rate` vs `aggregates.citation_rate`
   - If mention rate is high but citation rate is low, Gemini knows you exist but isn't pulling from your page. Likely cause: a competitor page covers the topic better, or your page lacks structural signals (schema, depth, freshness).
   - If both are low, you're not in the candidate set at all. Likely cause: topical coverage gap or search visibility issue.

2. Check `samples[*].citations` for which competitor URLs are getting cited instead
   - Fetch one or two of them. What do they have that yours doesn't?

3. Check `aggregates.query_fanout` for the queries Gemini fired
   - Does your page's content actually answer those queries? Often a "best X" prompt fires queries like "X reviews", "X alternatives", "X pricing" — if your page only covers one of those, you'll cite for some samples but not others.

## On entity coverage specifically

The `entity_universe` aggregate is one of the most underused signals.

Example: for prompt "best travel planning tools", `entity_universe` shows `{TripAdvisor: 18, Tabiji: 13, Lonely Planet: 9, Google Maps: 7, Wanderlog: 5}` over 20 samples.

That tells you:
- Gemini considers all 5 brands part of the answer space
- Your brand (Tabiji) is in the universe but underweighted
- A competitor page that mentions all 5 by name is more likely to cite for synthesis
- Adding paragraphs about each adjacent entity (where genuine and accurate) helps your page enter the synthesis context

**Don't keyword-stuff.** Write naturally about the adjacent entities. The signal isn't keyword density — it's "this page has context that connects multiple entities the model needs."
