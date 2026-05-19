# Workspace Setup Reference

A workspace is a project directory containing:

```
my-aeo-project/
├── aeo.config.json     ← written by aeo-init
├── .env                ← optional, holds GEMINI_API_KEY (gitignored)
├── aeo-data/           ← created by aeo-baseline on first run
│   └── run_*.json
└── aeo-reports/        ← created by aeo-report
    └── *.html
```

## Fields in aeo.config.json

### workspace (required)

| Field | Required | Description |
|---|---|---|
| `brand` | yes | Display name of the brand |
| `domain` | yes | Primary domain, e.g. `tabiji.ai` |
| `aliases` | no | Other spellings/abbreviations (e.g. `["Tabiji AI"]`) |
| `competitors` | no | Competitor domains, normalized |
| `locale` | no | BCP-47 (e.g. `en-US`); defaults to `en-US` |
| `persona` | no | Persona string prepended to prompts by some skills |

### providers

A list of providers. v1 supports Gemini only:

```json
{
  "name": "gemini",
  "model": "gemini-3-flash-preview",
  "api_key_env": "GEMINI_API_KEY",
  "grounding": true
}
```

`api_key_env` must be `UPPER_SNAKE_CASE`. The actual key value lives in your environment, never in the config.

### prompts

Each prompt has:

```json
{
  "prompt_id": "best_travel_planning_tools",
  "text": "What are the best travel planning tools?",
  "intent": "commercial",
  "tags": ["travel", "discovery"],
  "enabled": true
}
```

Valid intents (from the unified enum across all v2 schemas):

`informational`, `commercial`, `navigational`, `transactional`, `comparison`, `alternative`, `research`, `diagnostic`, `category_discovery`, `vendor_comparison`, `alternatives`, `pricing`, `integration`, `trust`, `problem_solution`, `other`

### sampling

```json
{
  "default_runs": 20,
  "concurrency": 5,
  "retries_per_sample": 3
}
```

The default 20 samples gives Wilson 95% CI widths of ~30pp for mid-range rates. Bump to 50 for competitive analysis, 100 for stakeholder reporting. See [METHODOLOGY.md](https://github.com/psyduckler/aeo-skills/blob/main/METHODOLOGY.md) §2.

### limits

Spend controls honored by `aeo-baseline` and `aeo-track`:

```json
{
  "max_daily_cost_usd": 25,
  "max_runs_per_campaign": 100,
  "confirm_over_usd": 5
}
```

- `confirm_over_usd` — `aeo-baseline` prompts before any single run estimated above this
- `max_daily_cost_usd` — `aeo-track` enforces this across scheduled runs

### scoring

```json
{"methodology_version": "aeo-v1"}
```

When the methodology bumps (e.g. to `aeo-v1.1`), update this field and re-run baselines to refresh stored scores. Raw evidence stays valid forever.

### data_dir (optional)

Path where evidence files are written. Default: `aeo-data` (relative to the config file).

## Editing by hand

The config is just JSON. Common manual edits:

- Add a prompt: append to `prompts`
- Disable a prompt without deleting: set `enabled: false`
- Change models: edit `providers[0].model`
- Bump default sample count: change `sampling.default_runs`

After hand-editing, you can re-validate by re-running `aeo-init --dry-run` with the same flags, or via `jsonschema` directly:

```bash
python3 -m jsonschema -i aeo.config.json /path/to/schemas/aeo-config-v1.json
```
