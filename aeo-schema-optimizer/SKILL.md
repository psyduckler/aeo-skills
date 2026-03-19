---
name: aeo-schema-optimizer
description: >
  Analyze web pages and generate structured data (JSON-LD) optimized for AI citation.
  Fetches a page, analyzes its content structure, checks existing schema markup, and
  generates optimized JSON-LD that helps Gemini 3 Flash and other AI models identify
  and cite the content. Includes templates for Article, FAQ, HowTo, Product, LocalBusiness,
  and BreadcrumbList. SKILL.md-only skill — no script, the agent follows the methodology.
  Use when a user wants to: add or improve structured data on a page, optimize schema
  for AI Overviews, generate JSON-LD for their content, or audit existing schema markup.
---

# AEO Schema Optimizer

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-schema-optimizer)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

Generate structured data (JSON-LD) optimized for AI citation. Help Gemini 3 Flash and other AI models find, understand, and cite your content.

## Why Structured Data Matters for AEO

When Gemini 3 Flash generates AI Overviews, it needs to quickly identify:
- **What type of content** is on the page (article, FAQ, how-to guide, product)
- **What questions** it answers
- **What entities** it covers (people, products, organizations)
- **How authoritative** the source is (author, publication date, organization)

Schema markup explicitly declares all of this. Pages with proper schema give AI models a structured signal layer on top of the content — making them easier to parse, trust, and cite.

## Requirements

- `web_fetch` — to analyze the target page
- LLM reasoning — to determine optimal schema types and generate JSON-LD
- Templates in `references/schema-templates.md`

No API keys required.

## Input

- **URL** (required) — the page to optimize
- **Target prompt** (optional) — the AI prompt this page should win citations for

## Workflow

### Step 1: Fetch and Analyze the Page

Use `web_fetch` on the target URL. Extract:

1. **Page title** and meta description
2. **Content structure** — headings (H1-H3), sections, lists
3. **Content type** — determine what kind of page this is:
   - **Article/Blog** — long-form content, guides, analysis
   - **FAQ** — question-and-answer format
   - **How-To** — step-by-step instructions
   - **Product** — product page with specs, pricing, reviews
   - **Local Business** — location with address, hours, contact
   - **Landing Page** — mixed content, multiple purposes
4. **Key entities** — people (authors), organizations, products, tools mentioned
5. **Existing schema** — check for any `<script type="application/ld+json">` blocks

### Step 2: Audit Existing Schema

If schema already exists:
- Is it valid JSON-LD?
- Does it match the page content type?
- Is it complete (all recommended properties filled)?
- Are there missing schema types that would help? (e.g., article page without FAQ schema for Q&A sections)
- Are dates current (datePublished, dateModified)?

Output audit findings: what's present, what's missing, what's incorrect.

### Step 3: Determine Optimal Schema Strategy

Based on content type and structure, recommend which schema types to implement:

| Content Type | Primary Schema | Additional Schema |
|---|---|---|
| Guide/Article | `Article` | `FAQ` (if Q&A sections), `BreadcrumbList`, `HowTo` (if steps) |
| FAQ Page | `FAQPage` | `Article`, `BreadcrumbList` |
| Tutorial/How-To | `HowTo` | `Article`, `FAQ` (for troubleshooting), `BreadcrumbList` |
| Product Page | `Product` | `FAQ`, `BreadcrumbList`, `AggregateRating` |
| Local Business | `LocalBusiness` | `FAQ`, `BreadcrumbList` |
| Comparison | `Article` | `FAQ`, `ItemList`, `BreadcrumbList` |
| Listicle | `Article` + `ItemList` | `BreadcrumbList` |

**Key principle:** Layer multiple schema types. An article that includes a FAQ section should have both `Article` AND `FAQPage` schema. This gives AI models multiple structured entry points.

### Step 4: Generate Optimized JSON-LD

Use templates from `references/schema-templates.md` and populate with actual page data.

**Critical properties for AI citation:**

For `Article`:
- `headline` — match the H1, keep under 110 chars
- `description` — the meta description or a 150-char summary
- `author` — full name + credentials URL (sameAs)
- `datePublished` + `dateModified` — ISO 8601, must be current
- `publisher` — organization with logo
- `mainEntityOfPage` — canonical URL
- `about` — what the article covers (link to entities)

For `FAQPage`:
- Extract every Q&A pair from the page
- Each `Question` gets the exact heading text
- Each `acceptedAnswer` gets the first 1-2 sentences (the direct answer)
- Limit to 10 most important Q&As

For `HowTo`:
- `name` — the process being described
- `step` — each step with `name` and `text`
- `totalTime` — ISO 8601 duration if mentioned
- `estimatedCost` — if applicable
- `supply` / `tool` — materials or tools needed

For `Product`:
- `name`, `description`, `brand`
- `offers` — pricing, availability
- `aggregateRating` — if reviews exist
- `review` — individual reviews

For `LocalBusiness`:
- `name`, `address`, `telephone`
- `openingHoursSpecification`
- `geo` — latitude/longitude
- `priceRange`

### Step 5: Validate and Deliver

Before delivering the JSON-LD:

1. **Validate JSON syntax** — ensure it parses correctly
2. **Check required properties** — every schema type has required fields
3. **Verify entity consistency** — author, publisher, dates match across schema blocks
4. **Test nested structures** — FAQ questions, HowTo steps are properly structured
5. **Check URL references** — mainEntityOfPage, sameAs, url fields are correct

Output:
- Complete JSON-LD block(s) ready to paste into `<head>`
- Implementation notes (where to place, what to update when content changes)
- If existing schema was found: diff showing what changed

### Step 6: Verification Guidance

After implementation, recommend:
- Test with [Google Rich Results Test](https://search.google.com/test/rich-results)
- Validate with [Schema.org Validator](https://validator.schema.org)
- Wait 2-4 weeks for Google to re-crawl and process
- Use `aeo-ai-overview-simulator` to measure citation impact before/after

## Schema Types Gemini Prioritizes

Based on observed AI Overview behavior, these schema signals matter most:

1. **FAQPage** — directly provides Q&A pairs the AI can cite; highest impact for question prompts
2. **Article with dateModified** — freshness signal; AI models prefer recently-updated content
3. **HowTo** — structured steps are easy for AI to extract and present
4. **Author with credentials** — expertise signal (E-E-A-T); helps for YMYL topics
5. **BreadcrumbList** — helps AI understand site structure and topic hierarchy
6. **Product with reviews** — for commercial queries; aggregateRating is a trust signal

## Tips

- **Don't over-schema.** Only add schema types that match actual page content. Misleading schema can trigger penalties.
- **FAQ is the highest-ROI schema for AEO.** If your page answers questions (even implicitly), extract those Q&As into FAQPage schema.
- **Keep dateModified current.** Every time you update content, update the dateModified. Stale dates signal stale content.
- **Author schema matters for YMYL.** Health, finance, legal content benefits enormously from detailed author schema with credentials.
- **Pair with content optimization.** Schema helps AI *find* your answers; the answers themselves still need to be clear, concise, and extractable. Use `aeo-content-free` for that.
