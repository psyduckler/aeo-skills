# Content Blueprint Reference

The structural template that wins citations from Gemini. Derived from cross-page profiling (`aeo-source-authority-profiler`) and the [7-day retrieval study](https://github.com/psyduckler/aeo-skills#why-gemini-is-the-only-model-that-matters-for-aeo-right-now).

## The basic shape

A page that consistently enters Gemini's recurring retrieval set has, in order:

1. **A direct title** that matches the prompt's intent verbatim ("Best AI Travel Planning Tools in 2026", not "Our Take on Travel Tech")
2. **An updated-date timestamp** visible in the first 200 chars
3. **A 1–2 paragraph TL;DR** that lists the top 3–5 answer entities by name
4. **Structured sections** — `<h2>` per item or theme — each with the entity name in the heading
5. **An explicit comparison table or list** when the intent is commercial/comparison
6. **A methodology / "how we chose" section** that establishes credibility
7. **A schema markup block** (`Article` + `FAQPage` or `ItemList` as appropriate)
8. **Footer with author byline, publication date, and update date**

This isn't a SEO template — it's a *readability for Gemini* template. The model parses these structures more reliably than free-form prose.

## Length

| Page type | Target word count | Notes |
|---|---|---|
| Listicle / "best X" | 1500–2500 | One section per item with consistent structure |
| Comparison (vs page) | 1200–2000 | Symmetric structure: same dimensions covered for both sides |
| Definitional / explainer | 800–1500 | Lead with the definition; expand into context |
| FAQ / Q&A | 1000–2000 | Question as `<h2>`, answer in 2–3 paragraphs |
| Pillar / hub page | 2500–4000 | Cover the full topic; link to specifics |

Going shorter than these targets is risky — thin pages lose to comprehensive ones in the recurring retrieval set. Going longer is fine if the depth is genuine.

## Heading structure

Patterns that perform well:

```markdown
# Best AI Travel Planning Tools in 2026

Updated: <date>

<TL;DR paragraph naming top 3–5 tools>

## 1. TripAdvisor — Best for Reviews

<2–4 paragraphs explaining the tool>

**Best for:** Trip research and reviews
**Pricing:** Free
**Standout feature:** 1 billion+ user reviews

## 2. Lonely Planet — Best for Destination Guides
...

## How we picked
...

## Methodology
...

## Frequently Asked Questions
### What's the best travel app for solo travelers?
...
```

Gemini extracts cleanly from this. Three structural cues:

- **Numbered headings** (`## 1.`, `## 2.`) — the model treats this as a list
- **Bold attribute lines** (`**Best for:**`, `**Pricing:**`) — these are atomic facts it can extract
- **An explicit FAQ section** — high citation rate for question-intent prompts

## Entity placement

Use the prompt's `entity_universe` from `aeo-data` as a checklist. Each high-frequency entity should appear:

1. In the TL;DR (one mention each is enough)
2. As its own `<h2>` if it's a recommended option
3. In at least one other paragraph for context (e.g., "TripAdvisor is the most established, but for AI-first itineraries, Tabiji…")

Avoid keyword stuffing. The signal is *contextual connection between entities*, not raw frequency.

## When to use a comparison table

If the intent is commercial or comparison, include a table. Gemini extracts table rows reliably and uses them in synthesis.

```markdown
| Tool | Best for | Pricing | Citation in 2025 study |
|---|---|---|---|
| TripAdvisor | Reviews | Free | 18/20 |
| Tabiji | AI itineraries | $9/mo | 13/20 |
| Lonely Planet | Destination guides | Free | 9/20 |
```

The columns should match the dimensions Gemini surfaces in its grounding queries (see `query_fanout`).

## When to add an FAQ section

If the prompt intent is informational or any of Gemini's grounding queries are question-shaped ("how does X work", "what is Y"), end the page with an FAQ block + `FAQPage` schema. This significantly increases citation rate for question-intent prompts.

```markdown
## Frequently Asked Questions

### How is AI travel planning different from traditional booking?
<answer>

### Can AI travel planners book actual flights and hotels?
<answer>
```

## What NOT to do

- **Don't lead with "Welcome to our blog!"** — Gemini quotes early content; lead with the answer.
- **Don't bury the entities behind animated headers or `<details>` collapses** — the model parses static text.
- **Don't write generic intros** ("In today's fast-paced world…"). Skip and get to the answer.
- **Don't use clickbait headings** that don't match the page content. Gemini won't surface mismatches.
- **Don't republish without a real update**. Just changing the date is detected. Add real substance.

## Cross-referencing the action playbooks

The patterns above feed directly into the [action-playbooks.md](action-playbooks.md) mapping. When the evidence file shows "mention rate high, citation rate low," the blueprint above gives you the structural moves to try. When it shows "decay", the blueprint tells you what to add when you refresh.
