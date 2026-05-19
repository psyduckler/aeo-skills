---
name: aeo-track
description: >
  Schedule recurring aeo-baseline runs without standing up Airflow, cron-monitor,
  or any external service. Generates a platform-appropriate scheduled job
  (launchd on macOS, cron on Linux), a wrapper shell script that loads the
  workspace's .env and runs aeo-baseline --yes, and tracks install state so
  the schedule can be inspected or removed cleanly. Default is dry-run — pass
  --apply to actually install. Multiple workspaces can be scheduled
  independently; state lives under ~/.aeo-track/<workspace-id>/.
  Use when a user wants to: set up daily/weekly visibility tracking, automate
  aeo-baseline so trends accumulate, see what's currently scheduled, or remove
  a previously-installed schedule.
---

# AEO Track

> **Source:** [github.com/psyduckler/aeo-skills](https://github.com/psyduckler/aeo-skills/tree/main/aeo-track)
> **Part of:** [AEO Skills Suite](https://github.com/psyduckler/aeo-skills)

The scheduling layer for AEO visibility tracking. One command per workspace, one schedule, no infrastructure.

## Requirements

- Python 3.9+ (stdlib only)
- macOS (launchd) OR Linux (cron)
- An `aeo.config.json` in the workspace directory (run `aeo-init` first)
- `aeo-baseline` installed somewhere this skill can find it

## Usage

```bash
# Dry-run: see what would be installed
python3 scripts/track.py --install --schedule daily

# Actually install
python3 scripts/track.py --install --schedule daily --apply

# Custom schedule and time
python3 scripts/track.py --install --schedule weekly --hour 8 --apply

# Inspect current install
python3 scripts/track.py --status

# Remove
python3 scripts/track.py --remove --apply
```

Run from inside the workspace directory (the one containing `aeo.config.json`), or pass `--workdir PATH`.

## How it works

1. **Generates a wrapper script** at `~/.aeo-track/<id>/run.sh` that:
   - `cd`s into the workspace directory
   - Sources `.env` from that directory if present (loads `GEMINI_API_KEY`)
   - Runs `python3 /path/to/aeo-baseline/scripts/baseline.py --yes`
   - Appends stdout/stderr to `aeo-data/aeo-track.log`

2. **Installs a scheduled job** that invokes the wrapper:
   - macOS → `~/Library/LaunchAgents/ai.skills.aeo-track.<id>.plist` + `launchctl load`
   - Linux → `crontab -l` line with a unique marker for safe removal

3. **Records state** at `~/.aeo-track/<id>/state.json` so `--status` and `--remove` know what to do.

`<id>` is `sha1(absolute_workdir)[:12]` — same workspace → same ID. Different workspaces don't collide.

## Options

| Option | Description |
|---|---|
| `--install` | (Default) Set up the schedule |
| `--remove` | Tear down the schedule |
| `--status` | Show install info for the workspace |
| `--workdir PATH` | Workspace directory (default: cwd) |
| `--baseline-script PATH` | Absolute path to `baseline.py` (auto-detected if omitted) |
| `--schedule SPEC` | `daily` (default) \| `weekly` \| `hourly` \| `'every Nm'` |
| `--hour N` | Hour-of-day for daily/weekly (default: 9) |
| `--minute N` | Minute (default: 0) |
| `--apply` | Actually install/remove (default is print-only) |

## Schedule syntax

| `--schedule` value | macOS launchd | Linux cron |
|---|---|---|
| `daily` | `StartCalendarInterval{Hour, Minute}` | `<min> <hour> * * *` |
| `weekly` | `StartCalendarInterval{Weekday=1, Hour, Minute}` | `<min> <hour> * * 1` (Monday) |
| `hourly` | `StartCalendarInterval{Minute}` | `<min> * * * *` |
| `every 15m` | `StartInterval=900` | `*/15 * * * *` |

## Setting up the API key

The wrapper script sources `.env` from the workspace dir if present. Put your API key there:

```bash
# In the workspace dir
cat > .env <<'EOF'
GEMINI_API_KEY=your_key_here
EOF
echo .env >> .gitignore
```

Both launchd and cron run with minimal shell environment by default, so the scheduled job won't see env vars from your interactive shell. The `.env` file is the bridge.

## Inspect logs

After scheduled runs accumulate, check the log:

```bash
tail -f aeo-data/aeo-track.log
```

Each run produces a fresh evidence file in `aeo-data/run_<timestamp>.json` — same format as a manual `aeo-baseline` invocation.

## Idempotency

- Re-installing (with `--apply`) on the same workspace replaces the previous schedule. On macOS this unloads + reloads the plist; on Linux it strips matching lines from `crontab -l` before appending the new one.
- `--remove --apply` is safe to run even if nothing is installed.
- State is per-workspace, so installing in multiple project directories doesn't collide.

## Limitations (v0)

- **Windows is not supported** for `--apply`. The dry-run still prints the wrapper script so you can wire it into Task Scheduler manually.
- The wrapper runs with the *user's* environment, so cron-style limits on subprocess resource usage apply.
- No retry logic at the schedule layer — if a scheduled run fails, the next one tries fresh. `aeo-baseline` itself retries failed API calls internally.
- `--status` confirms launchd has the job loaded; for cron it only checks the recorded state file (run `crontab -l | grep aeo-track` for the live view).

## Pairs With

- **[aeo-init](https://github.com/psyduckler/aeo-skills/tree/main/aeo-init)** — creates the `aeo.config.json` that this skill schedules
- **[aeo-baseline](https://github.com/psyduckler/aeo-skills/tree/main/aeo-baseline)** — the script that actually runs on each tick
- **[aeo-report](https://github.com/psyduckler/aeo-skills/tree/main/aeo-report)** (coming) — reads the accumulated baselines and generates trend reports
