---
name: aeo-analytics-free
description: >
  Track AI visibility — measure whether a brand is mentioned and cited by AI assistants
  (Gemini, ChatGPT, Perplexity) for target prompts. Runs scans, tracks mention/citation
  rates over time, detects trends, and identifies opportunities. Uses Gemini API free tier
  (with grounding) as primary method, web search as fallback.
  Use when a user wants to: check if AI models mention their brand, track AI citation
  changes over time, measure AEO content effectiveness, monitor competitor AI visibility,
  or audit their brand's presence in AI-generated answers.
  Pairs with aeo-prompt-research-free (identifies prompts) and aeo-content-free
  (creates/refreshes content). This skill closes the loop by measuring results.
---

# AEO Analytics (Free)

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-analytics-free)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills) — [Prompt Research](https://github.com/psyduckler/aeo-skills/tree/main/aeo-prompt-research-free) → [Content](https://github.com/psyduckler/aeo-skills/tree/main/aeo-content-free) → Analytics

Track whether AI assistants mention and cite your brand — and how that changes over time.

**The Retrieval Framework:** [Influence happens at retrieval, not inside the model.](https://www.clearscope.io/blog/how-to-influence-ai-answers) You can't edit a model's training data — but you can enter the "candidate set" the model selects from when it searches the web. This skill measures whether you're in that candidate set, where you sit in it (citation position), and whether your position is improving over time. [Gemini is search-first](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence), searching before nearly every answer — influence compounds through repeated inclusion in the recurring retrieval set.

## Requirements

- **Primary:** Gemini API key (free from aistudio.google.com) — enables grounding with source data
- **Fallback:** `web_search` only — weaker signal but zero API keys needed
- `web_fetch` — optional, for deeper analysis of cited pages

## Defaults

- **Model:** `gemini-3-flash-preview` — This is the model powering Google Search AI Mode and AI Overviews, making it the most relevant model for AEO analytics. Using the same model Google uses means your measurements reflect real-world AI Overview behavior.
- **Samples per prompt:** 20 — Run each prompt 20 times to get reliable directional data. AI responses are probabilistic; a single run can miss mentions that appear 30-40% of the time. 20 samples balances accuracy with API cost.

## Input

- **Domain** (required) — the brand's website (e.g., `tabiji.ai`)
- **Brand names** (required) — names to search for in responses (e.g., `["tabiji", "tabiji.ai"]`)
- **Prompts** (required for first scan) — list of target prompts to track. Can come from `aeo-prompt-research-free` output.
- **Data file path** (optional) — where to store scan history. Default: `aeo-analytics/<domain>.json`

## Commands

The skill supports three commands:

### `scan` — Run a new visibility scan

Execute all tracked prompts against the AI model and record results.

### `report` — Generate a visibility report

Analyze accumulated scan data and produce a formatted report.

### `add-prompts` / `remove-prompts` — Manage tracked prompts

Add or remove prompts from the tracking list.

---

## Scan Workflow

### Step 1: Load or Initialize Data

Check if a data file exists for this domain. If yes, load it. If no, create a new one.
See `references/data-schema.md` for the full JSON schema.

### Step 2: Run Prompts

For each tracked prompt, run 20 samples to get reliable frequency data:

**Method A — Gemini API with grounding (preferred):**
See `references/gemini-grounding.md` for API details.
Use model `gemini-3-flash-preview` (the same model powering Google AI Overviews).

1. Send prompt to Gemini API with `googleSearch` tool enabled — run 20 times per prompt
2. From each response, extract:
   - **Response text** — the AI's answer
   - **Grounding chunks** — the web sources cited (URLs + titles)
   - **Web search queries** — what the AI searched for

3. Analyze the response:
   - **Mentioned?** — Search response text for brand names (case-insensitive, word-boundary match)
   - **Mention excerpt** — Extract the sentence(s) containing the brand name
   - **Cited?** — Check if brand's domain appears in any grounding chunk URI
   - **Cited URLs** — List the specific brand URLs cited
   - **Citation position** — Record the position (1st, 2nd, 3rd...) of the brand's domain in the grounding chunks array. This tells you where you sit in the candidate set — position #1 means your content has the highest structural influence on the answer, shaping the AI Overview's opening statement. Track as `citation_position` (1-indexed, null if not cited).
   - **Sentiment** — Classify the mention context as positive/neutral/negative
   - **Competitors** — Extract other brand names and domains from response + citations

**Method B — Web search fallback (if no Gemini API key):**
1. `web_search` the exact prompt text
2. Check if brand's domain appears in search results
3. Record as "web-proxy" method (less direct than grounding)

### Step 3: Save Results

Append the scan results to the data file. Never overwrite previous scans — history is the whole point.

### Step 4: Quick Summary

After scanning, output a brief summary:
- Prompts scanned
- Current mention rate and citation rate
- Change vs. last scan (if applicable)
- Any notable changes (new mentions, lost citations)

---

## Report Workflow

### Per-Prompt Detail

For each tracked prompt, show:

```
1. "[prompt text]"
   Scans: [total] (since [first scan date])
   Mentioned: [count]/[total] ([%]) — [trend arrow] [trend description]
   Cited: [count]/[total] ([%])
   Citation position: avg #[X.X] (range: #[min]-#[max]) — [trend description]
   Latest: [✅/❌ Mentioned] + [✅/❌ Cited] [position: #X]
   Sentiment: [positive/neutral/negative]
   Competitors mentioned: [list]
```

If mentioned in latest scan, include the mention excerpt.
If not mentioned, note which sources were cited instead and rate the opportunity (HIGH/MEDIUM/LOW).

Position tracking across scans:
- Show average citation position per prompt across all scans where cited
- Format: "Average position: #3.2 (range: #1-#7)"
- Trend: "Position improved from avg #5 to avg #2 over last 4 scans"
- If not cited, position is null (don't include in averages)

### Summary Section

```
VISIBILITY SCORE
  Brand mentioned: [X]/[total] prompts ([%]) in latest scan
  Brand cited: [X]/[total] prompts ([%]) in latest scan
  Average citation position: #[X.X] (closer to #1 = more prominent)
  Position trend: [improving/declining/stable]

TRENDS (last [N] days, [N] scans)
  Mention rate: [%] → [trend]
  Citation rate: [%] → [trend]
  Citation position: avg #[X] → avg #[Y] ([improving/declining/stable])
  Most improved: [prompt] ([old rate] → [new rate])
  Most volatile: [prompt] (mentioned [X]/[N] scans)
  Consistently absent: [list of prompts never mentioned]

COMPETITOR SHARE OF VOICE
  [Competitor 1] — mentioned in [X]/[total] prompts
  [Competitor 2] — mentioned in [X]/[total] prompts
  [Brand] — mentioned in [X]/[total] prompts

NEXT ACTIONS
  → [Prioritized recommendations based on gaps and trends]
```

### Recommendations Logic

- **High opportunity:** Prompt has 0% mention rate + no strong owner in citations → create content
- **Close to winning:** Prompt has mentions but no citations → refresh content for citation-worthiness
- **Volatile:** Mention rate between 20-60% → content exists but needs strengthening
- **Won:** Mention rate >80% + citation rate >50% → maintain, monitor for decay

---

## Data Management

- Data file location: `aeo-analytics/<domain>.json`
- Schema: see `references/data-schema.md`
- Each scan appends to the `scans` array — never delete history
- Prompts can be added/removed without affecting historical data
- When adding new prompts, they start with 0 scans (no backfill)

## Tips

- Run scans at consistent intervals (weekly or biweekly) for meaningful trend data
- After publishing new AEO content, wait 2-4 weeks for indexing before expecting changes
- Gemini's grounding results can vary run-to-run — that's normal and exactly why we run 20 samples per prompt. Aggregate data over multiple samples and scans is more reliable than any single result
- Track 10-20 prompts max for a focused view. Too many dilutes the signal (20 prompts × 20 samples = 400 API calls per scan)
- Citation position matters — being the 1st grounding source means your content shapes the AI Overview's opening statement. Position #1 gets the most prominent mention and the highest structural influence on the answer. Track position trends alongside citation rate to understand your place in the candidate set.
- Position trend is as important as citation rate trend — you can be cited consistently but be drifting from position #2 to position #6, meaning your structural influence is declining even though you're still in the retrieval set
- This skill completes the AEO loop: Research (aeo-prompt-research-free) → Create/Refresh (aeo-content-free) → Measure (this skill) → repeat

## Further Reading

- [How to Influence AI Answers](https://www.clearscope.io/blog/how-to-influence-ai-answers) — the retrieval-first framework for AEO
- [Gemini Creates More Opportunity; GPT Is Harder to Influence](https://www.clearscope.io/blog/gemini-creates-more-opportunity-gpt-is-harder-to-influence) — why Gemini's search-first behavior matters
