# Scheduling Platforms Reference

How aeo-track maps schedule specs onto each platform.

## macOS (launchd)

A plist is written to `~/Library/LaunchAgents/ai.skills.aeo-track.<id>.plist` and loaded with `launchctl load`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ...>
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>ai.skills.aeo-track.abc123def456</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/.../​.aeo-track/abc.../run.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>9</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  ...
</dict>
</plist>
```

Inspect a loaded job:

```bash
launchctl list | grep aeo-track
launchctl print gui/$UID/ai.skills.aeo-track.<id>
```

Re-load after editing the plist by hand:

```bash
launchctl unload ~/Library/LaunchAgents/ai.skills.aeo-track.<id>.plist
launchctl load ~/Library/LaunchAgents/ai.skills.aeo-track.<id>.plist
```

## Linux (cron)

A line is appended to your user crontab (`crontab -l` shows it). Lines are tagged with a unique marker comment so `--remove` can safely strip just the workspace's entries:

```
0 9 * * * /bin/bash /home/.../​.aeo-track/abc.../run.sh  # aeo-track: abc123def456
```

Inspect:

```bash
crontab -l | grep aeo-track
```

Manually remove (if the skill's --remove path fails):

```bash
crontab -l | grep -v 'aeo-track:' | crontab -
```

## Windows (manual)

Dry-run mode prints the wrapper script. Wire it into Task Scheduler:

1. `aeo-track --install --schedule daily` to print the wrapper
2. Save the printed wrapper to a `.bat` or `.ps1`
3. Open Task Scheduler, create a Basic Task pointing at the wrapper script
4. Adjust the trigger to match `--schedule`

Windows support for `--apply` is on the v1.1 roadmap.

## Schedule semantics

| Spec | Meaning | launchd field | cron field |
|---|---|---|---|
| `daily` | Once per day at `--hour:--minute` | `StartCalendarInterval` | `<min> <hour> * * *` |
| `weekly` | Once per week on Monday at `--hour:--minute` | `StartCalendarInterval` with Weekday=1 | `<min> <hour> * * 1` |
| `hourly` | Once per hour at `--minute` past | `StartCalendarInterval` with only Minute | `<min> * * * *` |
| `every 15m` | Every 15 minutes (for testing only) | `StartInterval=900` (seconds) | `*/15 * * * *` |

`every Nm` is intended for testing. For production tracking, use `daily` (most common) or `weekly`.

## What runs

The scheduled job invokes the generated wrapper, which:

1. `set -e` — fail fast on any error
2. `cd` to the workspace directory
3. `source .env` if it exists (loads API keys)
4. `python3 path/to/baseline.py --yes` — `--yes` skips the interactive cost-confirmation prompt
5. Output appended to `aeo-data/aeo-track.log`

That last step means the log grows unbounded. Rotate it manually if needed (`logrotate` on Linux, or a periodic `truncate` in a separate scheduled task on macOS).

## Why a wrapper instead of inlining the python call

The wrapper exists for three reasons:

1. **Env loading.** Both launchd and cron strip the user's shell environment. The wrapper sources `.env` so the scheduled job sees `GEMINI_API_KEY`.
2. **Working directory.** `aeo-baseline` reads `./aeo.config.json` — the wrapper guarantees the right cwd.
3. **Edit access.** If a user needs to change what runs (e.g. add `--runs 50`), they can edit the wrapper without touching the plist/cron entry.

The wrapper is auto-generated and gets a header comment warning. If you edit it by hand, re-running `aeo-track --install --apply` will overwrite your changes.
