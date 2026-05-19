# Examples

A complete sample AEO workspace you can read for reference.

## `tabiji/`

A dogfooded example for `tabiji.ai`. Shows the full v2 loop with realistic data:

```
tabiji/
├── aeo.config.json                            ← what aeo-init writes
├── aeo-data/
│   ├── 2026-05-18T14-30-00Z.json              ← run 1: score 50.85
│   ├── 2026-05-19T14-30-00Z.json              ← run 2: score 57.25 (↑)
│   └── 2026-05-20T14-30-00Z.json              ← run 3: score 62.25 (↑)
└── aeo-reports/
    ├── <ts>-report.md                          ← what aeo-report writes
    └── <ts>-report.html                        ← single-file HTML w/ inline SVG chart
```

### What this example demonstrates

- **`aeo-config-v1` shape** — a complete workspace config with one prompt, one provider (Gemini), default sampling, default spend limits
- **`aeo-evidence-v1` shape** — three timestamped baselines covering one prompt, each with full per-sample data + aggregates + visibility score
- **A trend** — the score climbs from 50.85 → 57.25 → 62.25 over three runs (synthetic but realistic shape)
- **`aeo-report` output** — Markdown and single-file HTML with an embedded SVG line chart of the visibility score over time

### How the data was generated

These evidence files are hand-crafted to illustrate the schema. They don't represent real Gemini API calls — they're fixtures. The numbers (mention rate, citation rate, position, score) were chosen to show a modest upward trend with consistent component-to-score math (each `visibility_score.value` equals the sum of its `components[*].contribution`, per `aeo-v1` methodology).

CI validates these files against the schema on every push, so if the schema evolves and the example doesn't get updated, CI catches it.

### Try it yourself

```bash
# Generate a fresh report from this example
python3 ../aeo-report/scripts/report.py \
  --data-dir examples/tabiji/aeo-data \
  --output-dir /tmp/test-report \
  --format all

open /tmp/test-report/*.html
```

You should see a 3-point line chart climbing from ~51 to ~62.

### Replacing tabiji with your own brand

The exact files in `tabiji/` are what your project directory would look like after a few days of running aeo-baseline. To start a real workspace:

```bash
mkdir my-aeo-project && cd my-aeo-project
python3 /path/to/aeo-init/scripts/init.py --brand "Your Brand" --domain "your-domain.com" ...
```

…and let `aeo-baseline` + `aeo-track` produce the equivalents of these files over time.
