#!/usr/bin/env python3
"""
aeo-init — Initialize an AEO workspace.

Writes aeo.config.json conforming to schemas/aeo-config-v1.json. Use this once
per project to declare the brand, competitors, prompts, and limits that the
rest of the v2 skills (aeo-baseline, aeo-track, aeo-report) will read.

Usage:
    # Interactive: prompts for each field
    python3 init.py

    # Flag-driven (good for agent use):
    python3 init.py \\
        --brand Tabiji --domain tabiji.ai \\
        --alias tabiji \\
        --competitor tripadvisor.com --competitor lonelyplanet.com \\
        --prompt "best travel planning tools" \\
        --prompt "AI travel apps for itineraries"

    # Refuse to overwrite without --force:
    python3 init.py --force --brand NewBrand ...

Output: ./aeo.config.json by default; override with --output PATH.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from typing import Iterable

SCHEMA_VERSION = "aeo-config-v1"
DEFAULT_OUTPUT = "aeo.config.json"
DEFAULT_PROVIDER = {
    "name": "gemini",
    "model": "gemini-3-flash-preview",
    "api_key_env": "GEMINI_API_KEY",
    "grounding": True,
}
DEFAULT_SAMPLING = {"default_runs": 20, "concurrency": 5, "retries_per_sample": 3}
DEFAULT_LIMITS = {"max_daily_cost_usd": 25, "max_runs_per_campaign": 100, "confirm_over_usd": 5}
DEFAULT_SCORING = {"methodology_version": "aeo-v1"}

# Valid prompt intents (matches the unified schema enum)
VALID_INTENTS = {
    "informational", "commercial", "navigational", "transactional",
    "comparison", "alternative", "research", "diagnostic",
    "category_discovery", "vendor_comparison", "alternatives",
    "pricing", "integration", "trust", "problem_solution", "other",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert a prompt-like string into a snake_case prompt_id."""
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:64] or "prompt"


def normalize_domain(s: str) -> str:
    """Lowercase + strip a literal 'https://' / 'http://' / 'www.' prefix."""
    s = s.strip().lower()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    if s.startswith("www."):
        s = s[4:]
    return s.rstrip("/")


def dedupe_preserving_order(items: Iterable[str]) -> list[str]:
    """Deduplicate while preserving first occurrence."""
    seen = set()
    out = []
    for x in items:
        x = x.strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ── Config Builder ──────────────────────────────────────────────────────────

def build_config(
    brand: str,
    domain: str,
    aliases: list[str] | None = None,
    competitors: list[str] | None = None,
    prompts: list[dict] | None = None,
    locale: str | None = None,
    persona: str | None = None,
    providers: list[dict] | None = None,
    sampling: dict | None = None,
    limits: dict | None = None,
    data_dir: str | None = None,
) -> dict:
    """Assemble a config dict that conforms to aeo-config-v1."""
    workspace = {
        "brand": brand,
        "domain": normalize_domain(domain) if domain else "",
    }
    if aliases:
        workspace["aliases"] = dedupe_preserving_order(aliases)
    if competitors:
        workspace["competitors"] = dedupe_preserving_order(normalize_domain(c) for c in competitors)
    if locale:
        workspace["locale"] = locale
    if persona:
        workspace["persona"] = persona

    # Deep-copy defaults so callers can mutate the returned config without
    # corrupting the module-level constants.
    config = {
        "schema_version": SCHEMA_VERSION,
        "workspace": workspace,
        "providers": copy.deepcopy(providers) if providers else [copy.deepcopy(DEFAULT_PROVIDER)],
        "prompts": list(prompts) if prompts else [],
        "sampling": copy.deepcopy(sampling) if sampling else copy.deepcopy(DEFAULT_SAMPLING),
        "limits": copy.deepcopy(limits) if limits else copy.deepcopy(DEFAULT_LIMITS),
        "scoring": copy.deepcopy(DEFAULT_SCORING),
    }
    if data_dir:
        config["data_dir"] = data_dir
    return config


def build_prompt(text: str, intent: str | None = None, prompt_id: str | None = None) -> dict:
    """Build a single prompt entry matching the prompts[] schema."""
    p = {
        "prompt_id": prompt_id or slugify(text),
        "text": text.strip(),
    }
    if intent:
        if intent not in VALID_INTENTS:
            raise ValueError(f"Invalid intent {intent!r}. Must be one of: {sorted(VALID_INTENTS)}")
        p["intent"] = intent
    return p


# ── Validation ──────────────────────────────────────────────────────────────

def basic_validate(config: dict) -> list[str]:
    """Return a list of validation errors. Empty list means OK."""
    errors = []
    if config.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}")
    ws = config.get("workspace", {})
    if not ws.get("brand"):
        errors.append("workspace.brand is required")
    if not config.get("providers"):
        errors.append("providers must contain at least one entry")
    for i, p in enumerate(config.get("providers", [])):
        env = p.get("api_key_env", "")
        if not re.match(r"^[A-Z][A-Z0-9_]*$", env):
            errors.append(f"providers[{i}].api_key_env must be UPPER_SNAKE_CASE, got {env!r}")
    for i, p in enumerate(config.get("prompts", [])):
        if not p.get("prompt_id"):
            errors.append(f"prompts[{i}].prompt_id is required")
        elif not re.match(r"^[a-z0-9_]+$", p["prompt_id"]):
            errors.append(f"prompts[{i}].prompt_id must match ^[a-z0-9_]+$, got {p['prompt_id']!r}")
        if not p.get("text"):
            errors.append(f"prompts[{i}].text is required")
        intent = p.get("intent")
        if intent and intent not in VALID_INTENTS:
            errors.append(f"prompts[{i}].intent {intent!r} not in valid set")
    return errors


def schema_validate(config: dict, schema_path: str | None = None) -> list[str]:
    """Optional full JSON Schema validation if jsonschema is available."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return []
    if not schema_path:
        # Auto-locate: walk up from this script to find schemas/
        here = os.path.dirname(os.path.abspath(__file__))
        for _ in range(4):
            candidate = os.path.join(here, "schemas", "aeo-config-v1.json")
            if os.path.isfile(candidate):
                schema_path = candidate
                break
            here = os.path.dirname(here)
    if not schema_path or not os.path.isfile(schema_path):
        return []
    with open(schema_path) as f:
        schema = json.load(f)
    errs = list(Draft202012Validator(schema).iter_errors(config))
    return [f"{'.'.join(str(x) for x in e.absolute_path) or '(root)'}: {e.message}" for e in errs]


# ── Interactive Mode ───────────────────────────────────────────────────────

def prompt(question: str, default: str | None = None) -> str:
    """Read a line from stdin with an optional default."""
    if default:
        suffix = f" [{default}]: "
    else:
        suffix = ": "
    try:
        value = input(question + suffix).strip()
    except EOFError:
        return default or ""
    return value or (default or "")


def prompt_list(question: str, defaults: list[str] | None = None) -> list[str]:
    """Read a comma-separated list."""
    default_str = ", ".join(defaults or [])
    response = prompt(question, default_str)
    return [x.strip() for x in response.split(",") if x.strip()]


def interactive_workspace() -> dict:
    """Walk the user through workspace setup."""
    print("\nLet's set up an AEO workspace. Press Enter to accept defaults.\n")
    brand = prompt("Brand name") or "Unknown"
    domain = prompt("Brand domain (e.g. example.com)")
    aliases = prompt_list("Aliases (comma-separated, optional)")
    competitors = prompt_list("Competitor domains (comma-separated)")
    locale = prompt("Locale", default="en-US")

    print("\nNow add prompts you want to track. Enter blank to finish.")
    prompts: list[dict] = []
    while True:
        text = prompt(f"Prompt #{len(prompts) + 1}")
        if not text:
            break
        intent = prompt("  Intent (optional)", default="commercial")
        try:
            prompts.append(build_prompt(text, intent=intent or None))
            print(f"  ✓ Added '{text}' as '{prompts[-1]['prompt_id']}'")
        except ValueError as e:
            print(f"  ✗ {e}")
    return {
        "brand": brand,
        "domain": domain,
        "aliases": aliases,
        "competitors": competitors,
        "locale": locale,
        "prompts": prompts,
    }


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Initialize an AEO workspace config (aeo.config.json).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--brand", help="Brand/company name to track")
    p.add_argument("--domain", help="Brand's primary domain (e.g. example.com)")
    p.add_argument("--alias", action="append", default=[], help="Add an alias/alternate name (repeatable)")
    p.add_argument("--competitor", action="append", default=[], help="Add a competitor domain (repeatable)")
    p.add_argument("--prompt", action="append", default=[], help="Add a prompt to track (repeatable)")
    p.add_argument("--prompt-intent", action="append", default=[], help="Intent for the most recent --prompt; positional pairing")
    p.add_argument("--locale", default=None, help="BCP-47 locale (e.g. en-US)")
    p.add_argument("--persona", default=None, help="Optional persona prefix for prompts")
    p.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output path (default: {DEFAULT_OUTPUT})")
    p.add_argument("--data-dir", default=None, help="Where baselines should write evidence (default: aeo-data)")
    p.add_argument("--force", action="store_true", help="Overwrite existing config without prompting")
    p.add_argument("--interactive", action="store_true", help="Force interactive mode even if flags are present")
    p.add_argument("--dry-run", action="store_true", help="Print the config to stdout instead of writing")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Decide mode: interactive if forced, or if no required args given.
    has_minimal_args = bool(args.brand and (args.domain or args.prompt))
    if args.interactive or not has_minimal_args:
        data = interactive_workspace()
        brand = data["brand"]
        domain = data["domain"]
        aliases = data["aliases"]
        competitors = data["competitors"]
        locale = data["locale"] or args.locale
        prompts = data["prompts"]
    else:
        brand = args.brand
        domain = args.domain or ""
        aliases = args.alias
        competitors = args.competitor
        locale = args.locale
        # Pair --prompt with --prompt-intent positionally (intent[i] applies to prompt[i] if present)
        prompts: list[dict] = []
        for i, text in enumerate(args.prompt):
            intent = args.prompt_intent[i] if i < len(args.prompt_intent) else None
            try:
                prompts.append(build_prompt(text, intent=intent))
            except ValueError as e:
                print(f"✗ {e}", file=sys.stderr)
                return 1

    if not brand:
        print("✗ Brand name is required (use --brand or --interactive)", file=sys.stderr)
        return 1

    config = build_config(
        brand=brand,
        domain=domain,
        aliases=aliases,
        competitors=competitors,
        prompts=prompts,
        locale=locale,
        persona=args.persona,
        data_dir=args.data_dir,
    )

    # Validate
    errors = basic_validate(config) + schema_validate(config)
    if errors:
        print("✗ Generated config failed validation:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    # Write
    if args.dry_run:
        print(json.dumps(config, indent=2))
        return 0

    if os.path.exists(args.output) and not args.force:
        print(f"✗ {args.output} already exists. Use --force to overwrite.", file=sys.stderr)
        return 2

    with open(args.output, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    print(f"✓ Wrote {args.output} with {len(prompts)} prompt(s).")
    if not prompts:
        print("  Add prompts later by re-running with --force, or edit the file directly.")
    print(f"  Next: ensure {config['providers'][0]['api_key_env']} is set, then run aeo-baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
