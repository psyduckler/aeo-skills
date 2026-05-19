# AEO Methodology

**Version:** `aeo-v1`
**Status:** Stable for v1. Will be versioned forward (`aeo-v2`, etc.) when weights or extraction logic change.

This document is the trust layer of the AEO Skills suite. Every measurement skill is an implementation of this methodology. Every metric in the output evidence file is derived from rules documented here. If you disagree with the methodology, you can re-score the raw evidence yourself — that's the whole point of evidence-first measurement.

---

## 1. The Retrieval Framework

The core thesis: **AI visibility is a retrieval problem, not a training problem.**

You cannot edit a model's training data. But for search-grounded models like Gemini, you *can* influence what enters the "candidate set" the model selects from when it grounds an answer in real-time web search. That candidate set — the **recurring retrieval set** for a prompt — is what these skills measure.

A useful mental model:

```
prompt → model fires N web search queries → retrieves pages → grounds answer
                                                ↓
                                  this is the candidate set
                                  this is what you can influence
```

Every metric in this suite is a measurement of *where you sit in the recurring retrieval set* for a target prompt. The skills do not pretend to measure parametric knowledge — only retrieval behavior.

### Why Gemini-first

We ran a 7-day study across 4 prompt types × 2 models (ChatGPT GPT-5 and Gemini), analyzing 1,963 responses:

- **Gemini issued web searches on 100% of responses** with 265 unique queries.
- **ChatGPT searched on 45% of responses** with only 4 unique queries total.

That's a 66× difference in search diversity. Gemini's responses are deeply dependent on live web content; ChatGPT's are mostly parametric. For AEO measurement, that means:

1. **Gemini is influenceable through content.** ChatGPT mostly isn't (today).
2. **Gemini is measurable through grounding.** The API exposes the exact search queries fired and pages cited.
3. **Gemini powers Google AI Overviews.** ~25% of Google searches now trigger an AI Overview. That's the largest answer engine surface today.

The v1 measurement core is Gemini-only. Multi-provider adapters (OpenAI, Anthropic, Perplexity) are on the v1.1 roadmap; the evidence schema is already provider-agnostic.

---

## 2. Sampling

### Why 20 samples by default

AI responses are probabilistic. A single run can miss mentions that appear 30–40% of the time. We default to 20 samples per prompt because:

1. **Coverage:** Our control-run study showed 20 samples capture 74–100% of the search query universe for a prompt (100% for informational, 74–83% for dynamic/research/fresh prompts).
2. **Confidence:** 20 samples produces usefully tight Wilson 95% CIs for binary metrics like mention rate.
3. **Cost:** 20 prompts × 20 samples = 400 calls per baseline. Free-tier Gemini API supports this comfortably.

### Confidence intervals

We report **Wilson score intervals at 95% confidence** for all proportion metrics (mention rate, citation rate, competitor share). Wilson is the right choice for proportions with small N because the simpler normal approximation breaks down at the boundaries (rates near 0 or 1).

Reference table at N=20:

| Observed | 95% Wilson CI | Interpretation |
|---|---|---|
| 0/20 (0%) | 0% – 17% | Likely not cited, but rare appearances possible |
| 5/20 (25%) | 9% – 49% | Weak signal — could be noise |
| 10/20 (50%) | 27% – 73% | Directional — in the candidate set but not dominant |
| 15/20 (75%) | 51% – 91% | Strong — consistently retrieved |
| 20/20 (100%) | 83% – 100% | Very strong — core of the retrieval set |

### When to use more samples

| Use case | Samples |
|---|---|
| Initial audit, directional insight | 20 (default) |
| Competitive analysis, source authority profiling | 50 |
| Stakeholder reporting, content investment decisions | 100 |

All scripts accept `--runs N` to override.

### Idempotency

A "baseline run" is one execution that produces one evidence file. Two baseline runs of the same workspace produce two evidence files (different timestamps). Append-only by design — we never overwrite history.

---

## 3. Signal Extraction

Every measurement skill extracts these signals from raw responses. Definitions are deterministic.

### 3.1 Brand mention

A brand is "mentioned" in a sample if any of `workspace.brand` or `workspace.aliases` appears in `raw_response_text` as a whole-word match (case-insensitive, word-boundary regex `\b<term>\b`).

**Not** a mention:
- Substring matches (e.g., "tabijiverse" doesn't count for "tabiji")
- Matches inside cited URLs only (those are citations, separate signal)

### 3.2 Citation

A citation exists when the brand's domain (or aliases) appears in any of the response's grounding chunk URIs. We record:

- `url`: the full cited URL
- `position`: 1-based index in the grounding chunks array (lower = more prominent)
- `domain`: normalized (lowercase, `www.` stripped)
- `title`: the title the provider returned for the chunk

Position #1 is the source the model considered most authoritative — it typically shapes the AI Overview's opening statement.

### 3.3 Competitor mention

Competitors are tracked the same way as brand mentions, using the `workspace.competitors` list. Each competitor's domain is normalized identically to the brand's. Mentions can be in the response text OR in the citations — both are recorded with provenance.

### 3.4 Query fan-out

Each Gemini grounded response exposes `groundingMetadata.webSearchQueries` — the literal queries the model issued. We aggregate across samples as:

```
query_fanout[query] = (count of samples that fired this query) / total successful samples
```

A query with `query_fanout = 1.0` was fired on every single sample — that query is part of the deterministic retrieval pattern for this prompt. Queries below 0.20 are likely noise.

### 3.5 Entity universe

We extract named entities (brands, products, people, tools) from raw response text using regex-based patterns tuned for common AEO-relevant entity types. The output is a frequency map:

```
entity_universe[entity_name] = total count across all sample responses
```

Entities that appear in >50% of samples are part of the prompt's "stable retrieval vocabulary" — they're what AI considers essential context for this topic.

### 3.6 Sentiment

Sentiment classification is **rules-based** in v1 — we look for positive/negative qualifier patterns within ±50 characters of each brand mention. v1 sentiment is intentionally crude; treat anything beyond "positive vs not-positive" as low-confidence. v1.5 will swap to an LLM classifier.

Values: `positive`, `neutral`, `negative`, `mixed`, `unknown`.

### 3.7 Intent classification

Each prompt and each grounding query is classified into an intent bucket using keyword rules (see `_shared.classify_intent`). Intent helps reason about what kind of content enters the retrieval set:

| Intent | Signal patterns | Content type |
|---|---|---|
| informational | "what is", "how does", "explained" | Guides, explainers |
| commercial | "best", "vs", "review", "alternatives" | Comparison pages, listicles |
| navigational | brand names, domains, "login" | Homepages, product pages |
| transactional | "buy", "pricing", "free trial" | Conversion pages |

---

## 4. Visibility Score (aeo-v1)

The composite visibility score is **a transparent weighted average of five normalized signals**, scaled 0–100.

```
visibility_score = 100 × (
  0.30 × mention_rate
+ 0.25 × citation_rate
+ 0.20 × position_score
+ 0.15 × recommendation_rate
+ 0.10 × sentiment_score
)
```

Every term is in [0, 1].

### Component definitions

| Signal | Definition | Range |
|---|---|---|
| `mention_rate` | Fraction of samples where the brand was mentioned (whole-word) | 0–1 |
| `citation_rate` | Fraction of samples where the brand's domain was cited in grounding chunks | 0–1 |
| `position_score` | `1 - (avg_citation_position - 1) / 10`, clamped to [0, 1]. Position #1 = 1.0; position #11+ = 0.0; uncited = 0.0 | 0–1 |
| `recommendation_rate` | Fraction of samples where the brand appears in the final recommendation/conclusion of the response | 0–1 |
| `sentiment_score` | `(positive_count + 0.5 × neutral_count) / total_samples` | 0–1 |

### Why these weights

The weights reflect what we believe matters for influence today:

- **Mention (30%)** is the lowest bar — the brand is at least in the candidate set.
- **Citation (25%)** is the meaningful signal — the brand's *page* shaped the answer.
- **Position (20%)** matters because position #1 carries far more structural influence than position #8.
- **Recommendation (15%)** captures "did the model actually endorse you" — strong but rarer signal.
- **Sentiment (10%)** is weighted low because v1 sentiment is rules-based and noisy.

### Reversibility

If you disagree with the weights, **you can recompute the score from the raw evidence file** without re-running any API calls. That's the whole point of storing components separately. Future methodology versions (`aeo-v2`, `aeo-v3`) will reweight signals; historical data does not need to be re-collected.

---

## 5. Methodology Versioning

Every evidence file declares the methodology version that produced its scores (`run.methodology_version`). Every visibility score declares the version it was computed under (`visibility_score.methodology_version`).

When this document changes in a way that changes a score, the version increments:

| Change | New version |
|---|---|
| Weight rebalance | minor bump (`aeo-v1.1`) |
| New signal added | minor bump |
| Signal definition change (e.g., new sentiment classifier) | minor bump |
| Major framework change (e.g., dropping retrieval-set framing) | major bump (`aeo-v2`) |

Old evidence files remain valid forever — they just declare an older methodology version. Reports always disclose which version they're rendering under.

---

## 6. Provider Capabilities

Not every provider exposes every signal. The evidence schema is provider-agnostic, but missing fields are explicit (omitted, not zeroed).

| Capability | Gemini | OpenAI (v1.1) | Anthropic (v1.1) | Perplexity (v1.5) |
|---|---|---|---|---|
| Always-on web search | ✓ | ⚠️ (45% of responses) | ✗ | ✓ |
| Citation URLs in response | ✓ (groundingChunks) | ⚠️ (when search runs) | ✗ | ✓ |
| Search queries fired | ✓ (webSearchQueries) | ✗ | ✗ | ⚠️ |
| Citation position | ✓ | ⚠️ | ✗ | ✓ |
| Streaming | ✓ | ✓ | ✓ | ✓ |

For v1, only Gemini-derived rows have complete data. ChatGPT and Claude rows (if/when enabled) will have `citation_rate` and `query_fanout` omitted rather than zero.

---

## 7. What This Methodology Does *Not* Claim

- **Does not measure parametric knowledge.** "Does Gemini know what your brand does?" requires non-grounded probes; out of scope.
- **Does not reproduce consumer UI behavior perfectly.** Web UI answers may use personalization, account memory, and product-specific routing the API doesn't expose. API mode is reproducible; UI mode requires `manual_import` in a future skill.
- **Does not predict revenue impact.** Visibility correlates with brand awareness, but the causal chain from "cited by Gemini" to "user converted" requires your own attribution.
- **Does not claim ranking equivalence with classical SEO.** Position #1 in grounding chunks is *not* the same thing as position #1 in Google Search results. Different system.

---

## 8. Open Questions / Roadmap

- **v1.1:** Multi-provider adapters (OpenAI, Anthropic). Evidence schema unchanged.
- **v1.2:** LLM-based sentiment classifier (replace rules-based).
- **v1.5:** Provider capability metadata in evidence file (explicit "this provider does not expose X").
- **v2:** Possible rebalance of visibility score weights based on outcome data once enough users have run baselines for 6+ months.

If you have a stronger methodology, fork it. The schema is open. The point of this document is that *someone, somewhere, knows exactly how every number was produced.*
