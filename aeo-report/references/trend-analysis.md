# Trend Analysis Reference

How `aeo-report` derives trends from evidence files.

## Inputs

All evidence files in `aeo-data/`, sorted by `run.timestamp`. Each file is one baseline run; each prompt has aggregated metrics and a visibility score.

The report does not re-read raw samples for trend analysis (except for cannibalization and hub-page detection, which scan the latest run's samples). Aggregates and scores are pre-computed by `aeo-baseline` per [METHODOLOGY.md](https://github.com/psyduckler/aeo-skills/blob/main/METHODOLOGY.md).

## Series math

For any metric on a single prompt, the report builds a series across all runs:

```
[run_1.aggregates.mention_rate, run_2..., ..., run_N...]
```

Missing values (e.g. a prompt added later) are `None` and propagate through chart rendering as gaps.

## Trend arrow

Each prompt shows an arrow comparing first-run vs latest-run value of a metric:

| Arrow | Meaning |
|---|---|
| ↑ | improved by more than `eps` |
| ↓ | declined by more than `eps` |
| → | flat (within `eps`) |
| — | insufficient data |

`eps` defaults to 0.02 for rates (2pp) and 1.0 for the 0–100 visibility score.

## Decay detection

A signal "decays" if its trailing 3-run mean is ≥20% below its leading 3-run mean. Requires ≥4 runs.

```
leading_mean = mean(values[:3])
trailing_mean = mean(values[-3:])
delta_fraction = (leading_mean - trailing_mean) / leading_mean
flag if delta_fraction >= 0.20
```

Severity:
- HIGH if `delta_fraction > 0.5`
- MEDIUM if `delta_fraction > 0.3`
- LOW otherwise

The default metric is `aggregates.citation_rate` — citation decay is the operationally meaningful signal (you've fallen out of the recurring retrieval set). Other metrics can be plugged in by extending `report.py`.

## Cannibalization detection

For each prompt's latest run, look at all samples and count distinct URLs from the brand's domain that appear in citations. If ≥2 distinct URLs each appear in ≥2 samples, the prompt is "cannibalized" — multiple owned pages are competing for the same retrieval slot.

```
For each sample in the latest run:
  Count each brand-domain URL once
Find URLs cited in ≥ 2 samples
If ≥ 2 such URLs exist, flag
```

Severity is derived from the share of the top URL relative to the others:
- HIGH if leader share < 50% (urls are fighting)
- MEDIUM if 50–70%
- LOW if > 70% (one URL clearly winning)

## Hub-page detection

A URL is a "hub" if it appears in the latest run's citations for ≥2 different prompts AND its coverage (prompt_count / total_prompts) is ≥30%.

```
For each prompt's latest run:
  Collect the set of brand URLs cited in any sample
For each URL:
  If it appears in ≥ 2 prompts AND covers ≥ 30% of all prompts:
    It's a hub
```

Hubs are sorted by prompt count descending. These are existing pages worth doubling down on — a single optimization affects multiple prompts.

## Competitor share-of-voice shifts

For each prompt, compare `aggregates.competitor_share` between the first and latest runs. Flag competitors whose citation rate has shifted by >5 percentage points.

```
delta = latest_rate - first_run_rate
If abs(delta) > 0.05:
  Flag
```

Sorted by absolute delta descending — biggest shifts at the top.

## When trends are unreliable

The Wilson CI table from METHODOLOGY.md applies to every aggregate the report shows. At N=20 samples per run, expect proportion CIs of ~30pp width for mid-range rates. A "decay" from 50% to 35% might be within noise.

The report does not show CIs on trend deltas — interpret movement of <10pp at N=20 with skepticism. Bump samples or rely on the trailing-3-run smoothing for tighter signal.
