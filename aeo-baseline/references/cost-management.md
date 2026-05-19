# aeo-baseline: Cost Management

BYOK comes with a risk: an accidental loop or a misconfigured schedule can burn through credits. This skill builds three guards into the workflow.

## 1. Cost estimation before any API call

Every invocation prints a projected cost line:

```
Projected cost: $0.1200 (10 prompt(s) × 20 samples × $0.000600/sample)
```

The per-sample number is an approximation. The default is **$0.0003 per grounded Gemini Flash sample** — a conservative guess. Override it for your actual pricing:

```bash
export GEMINI_COST_PER_SAMPLE_USD=0.0005
```

To dry-run without any API calls:

```bash
python3 scripts/baseline.py --estimate-cost
```

## 2. Interactive confirmation over a threshold

If projected cost exceeds `limits.confirm_over_usd` in your config (default $5), the script pauses and asks before making any calls:

```
Projected cost: $7.5000 (15 prompt(s) × 50 samples)
This exceeds the confirm_over_usd threshold ($5). Continue? [y/N]
```

Override or skip:

- `--yes` / `-y` — non-interactive (use for cron / CI)
- Raise the threshold in `aeo.config.json`:
  ```json
  "limits": {"confirm_over_usd": 50}
  ```

## 3. Per-day cap (advisory in v1)

The `limits.max_daily_cost_usd` field in config (default $25) is advisory in this skill — `aeo-baseline` honors only the `confirm_over_usd` prompt. The daily cap is enforced by `aeo-track` (coming) when wrapping baselines in a recurring schedule.

## What's a reasonable baseline cost?

| Scope | Calls | Estimated cost |
|---|---|---|
| Quickstart (1 prompt × 20) | 20 | ~$0.006 |
| Standard workspace (10 prompts × 20) | 200 | ~$0.06 |
| Competitive analysis (10 prompts × 50) | 500 | ~$0.15 |
| Stakeholder report (10 prompts × 100) | 1000 | ~$0.30 |

Gemini's free tier has rate limits but no charge for development-scale usage. Paid pricing is current at the time of this writing; check [aistudio.google.com](https://aistudio.google.com) for live numbers.

## Best practices

- Set `confirm_over_usd` to something that matches your tolerance — $5 is sane for first-time use.
- Always run `--estimate-cost` after adding new prompts.
- `aeo-track` (when published) will reuse this skill's spend gates and add a daily ceiling.
- Don't `--yes` from a development shell — the threshold exists to catch fat-finger configs.
