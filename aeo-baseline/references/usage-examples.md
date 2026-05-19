# aeo-baseline: Usage Examples

## First baseline for a new brand

```bash
# 1. Set up workspace config (will be aeo-init in a future PR)
cat > aeo.config.json <<'EOF'
{
  "schema_version": "aeo-config-v1",
  "workspace": {
    "brand": "Tabiji",
    "domain": "tabiji.ai",
    "aliases": ["tabiji"],
    "competitors": ["tripadvisor.com", "lonelyplanet.com"]
  },
  "providers": [
    {"name": "gemini", "model": "gemini-3-flash-preview", "api_key_env": "GEMINI_API_KEY"}
  ],
  "prompts": [
    {"prompt_id": "best_travel_planning_tools", "text": "What are the best travel planning tools?", "intent": "commercial"},
    {"prompt_id": "ai_travel_apps", "text": "Best AI travel apps for itinerary planning", "intent": "commercial"}
  ],
  "sampling": {"default_runs": 20, "concurrency": 5},
  "limits": {"max_daily_cost_usd": 25, "confirm_over_usd": 5}
}
EOF

# 2. Verify the API key works
python3 scripts/baseline.py --doctor

# 3. Check projected cost
python3 scripts/baseline.py --estimate-cost

# 4. Run the baseline
python3 scripts/baseline.py
```

## Higher-confidence measurement (50 samples)

For competitive analysis or stakeholder reporting:

```bash
python3 scripts/baseline.py --runs 50
```

At N=50, expect Wilson 95% CI widths of ~20pp for mid-range rates — meaningfully tighter than the default 30pp at N=20.

## One-off ad-hoc prompt

To check visibility for a single prompt without setting up a config:

```bash
GEMINI_API_KEY="$GEMINI_API_KEY" python3 scripts/baseline.py \
  --prompt "best AI content detection APIs" \
  --prompt-id ai_detection_apis
```

Note: without a config, the workspace context is empty, so brand/competitor extraction won't fire. Best used to inspect raw Gemini behavior on a new prompt before committing to tracking it.

## Scheduled / CI mode (no interactive prompt)

```bash
python3 scripts/baseline.py --yes
```

`--yes` skips the cost confirmation. The `aeo-track` skill (coming) wraps this for daily cron execution.

## Inspect a single sample's raw response

After a run:

```bash
# Pick the latest evidence file
LATEST=$(ls -t aeo-data/run_*.json | head -1)

# Read the first sample's raw response
python3 -c "
import json
data = json.load(open('$LATEST'))
sample = data['prompts'][0]['samples'][0]
print(sample['raw_response_text'])
"
```

## Reduce evidence file size

If you don't need raw response text persisted:

```bash
python3 scripts/baseline.py
# Then strip raw text from the resulting file
python3 -c "
import json, sys, glob
for path in sorted(glob.glob('aeo-data/run_*.json'))[-1:]:
    data = json.load(open(path))
    for p in data['prompts']:
        for s in p['samples']:
            s.pop('raw_response_text', None)
    json.dump(data, open(path, 'w'), indent=2)
"
```

Trade-off: you lose the ability to audit extraction decisions or re-extract signals later. Keep raw text unless storage is a real concern.
