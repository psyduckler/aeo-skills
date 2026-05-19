---
name: aeo-init
description: >
  Initialize an AEO workspace by writing aeo.config.json — the workspace
  configuration file that every other v2 skill (aeo-baseline, aeo-track,
  aeo-report, aeo-optimize) reads. Captures the brand name and domain,
  aliases, competitors, the prompts to track, and spend limits. Supports both
  interactive prompts (for first-time setup) and flag-driven invocation (for
  agents). The output conforms to schemas/aeo-config-v1.json and validates
  against it when jsonschema is available.
  Use when a user wants to: start a new AEO tracking project, scaffold the
  config that aeo-baseline reads, regenerate a workspace config from scratch,
  or add prompts to an existing setup.
---

# AEO Init

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-init)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)
> **Output schema:** [aeo-config-v1](https://github.com/psyduckler/aeo-skills/blob/main/schemas/aeo-config-v1.json)

The workspace bootstrapper. One command, one config file, then `aeo-baseline` knows what to measure.

## Requirements

- Python 3.9+
- No API keys (this skill never calls a provider)
- Optional: `pip install jsonschema` for full schema validation at write time

## Usage

```bash
# Interactive — walks through every field
python3 scripts/init.py

# Flag-driven — best for agent use
python3 scripts/init.py \
  --brand Tabiji --domain tabiji.ai \
  --alias tabiji \
  --competitor tripadvisor.com --competitor lonelyplanet.com \
  --prompt "best travel planning tools" \
  --prompt "AI travel apps for itineraries" \
  --prompt-intent commercial --prompt-intent commercial

# Print the would-be config without writing
python3 scripts/init.py --brand X --domain x.com --prompt "best X" --dry-run

# Overwrite an existing config (safety: refuses unless --force)
python3 scripts/init.py --brand NewName --domain new.com --force

# Custom output path
python3 scripts/init.py --output /path/to/aeo.config.json ...
```

Interactive mode triggers automatically when neither `--brand` nor a useful flag combination is provided. Pass `--interactive` to force it even with flags.

## Options

| Option | Description |
|---|---|
| `--brand` | Brand/company name to track (required for non-interactive mode) |
| `--domain` | Brand's primary domain (e.g. `example.com`) |
| `--alias` (repeatable) | Alternate spellings/abbreviations |
| `--competitor` (repeatable) | Competitor domains to track |
| `--prompt` (repeatable) | Prompts to track for visibility |
| `--prompt-intent` (repeatable) | Intent for each `--prompt`, paired by position |
| `--locale` | BCP-47 locale (default: `en-US`) |
| `--persona` | Optional persona prefix used by some downstream skills |
| `--output PATH` | Where to write the config (default: `./aeo.config.json`) |
| `--data-dir PATH` | Where baselines should write evidence files |
| `--force` | Overwrite an existing config without prompting |
| `--interactive` | Force interactive prompts even when flags are set |
| `--dry-run` | Print the config to stdout instead of writing |

## What gets written

A JSON file conforming to [`aeo-config-v1.json`](https://github.com/psyduckler/aeo-skills/blob/main/schemas/aeo-config-v1.json). The default skeleton includes:

- One Gemini provider (model `gemini-3-flash-preview`, env var `GEMINI_API_KEY`, grounding enabled)
- Sampling: 20 runs default, 5 concurrency, 3 retries per sample
- Limits: $25/day cap, $5 confirm-over threshold, 100 runs per campaign
- Scoring: `aeo-v1` methodology
- Empty prompts list if none were provided (add later with `--force` or edit the file)

## Domain normalization

Competitor and brand domains are normalized before writing:
- Lowercased
- `https://` / `http://` prefixes stripped
- Literal `www.` prefix stripped (using `startswith`, not the `lstrip('www.')` footgun that would corrupt `world.com`)
- Trailing `/` stripped

So `https://WWW.TripAdvisor.com/` becomes `tripadvisor.com`.

## Prompt IDs

When you pass `--prompt "Best CRM for small business"`, the prompt is auto-assigned `prompt_id = "best_crm_for_small_business"`. IDs are `snake_case`, deduplicated by truncation to 64 chars. Override by editing the JSON post-hoc.

## Validation

After building the config, two validation layers run:

1. **Built-in:** required fields, `api_key_env` shape (`^[A-Z][A-Z0-9_]*$`), `prompt_id` shape (`^[a-z0-9_]+$`), intent enum membership.
2. **JSON Schema** (if `jsonschema` is importable): full structural validation against `aeo-config-v1.json`.

If validation fails, the script prints the errors and exits with a non-zero code without writing.

## Pairs With

- **[aeo-baseline](https://github.com/psyduckler/aeo-skills/tree/main/aeo-baseline)** — reads the config this skill writes
- **[aeo-track](https://github.com/psyduckler/aeo-skills/tree/main/aeo-track)** — schedules `aeo-baseline` runs from this config
- Future prompt packs (e.g. `aeo-pack-b2b-saas`) will populate the prompts array

## Notes

- This skill never calls a provider API and never reads secrets.
- The output is editable JSON — re-running with `--force` regenerates; editing in place is also fine.
- For a starter prompt list, run the (future) `aeo-prompt-research-free` skill first and feed its suggestions back into `init` via `--prompt` flags.
