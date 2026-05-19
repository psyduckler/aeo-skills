#!/usr/bin/env python3
"""
aeo-baseline — Atomic AI visibility measurement.

Runs each configured prompt 20 times (default) against Gemini with Google Search
grounding, extracts every signal from those same 20 responses, computes Wilson
95% confidence intervals, applies the aeo-v1 visibility score, and writes an
append-only JSON evidence file conforming to schemas/aeo-evidence-v1.json.

Usage:
    python3 baseline.py [--config aeo.config.json] [--runs 20] [--output-dir aeo-data]
    python3 baseline.py --doctor                  # verify API keys, no API calls
    python3 baseline.py --estimate-cost           # print projected cost, no API calls
    python3 baseline.py --prompt "..."            # run a single ad-hoc prompt (skips config)

Requires: GEMINI_API_KEY env var.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# ── Shared imports ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared import (
    call_gemini, extract_response_text, extract_queries, extract_sources,
    extract_domain, domain_matches, classify_intent, get_api_key,
    DEFAULT_MODEL, DEFAULT_RUNS, DEFAULT_CONCURRENCY,
)

# ── Constants ───────────────────────────────────────────────────────────────

METHODOLOGY_VERSION = "aeo-v1"
SCHEMA_VERSION = "aeo-evidence-v1"

# Approximate cost per grounded Gemini Flash sample, USD.
# Override via GEMINI_COST_PER_SAMPLE_USD env var.
DEFAULT_COST_PER_SAMPLE_USD = 0.0003

# aeo-v1 scoring weights (per METHODOLOGY.md §4)
SCORE_WEIGHTS = {
    "mention_rate": 0.30,
    "citation_rate": 0.25,
    "position_score": 0.20,
    "recommendation_rate": 0.15,
    "sentiment_score": 0.10,
}

# Sentiment keyword lists (±50-char window around each mention)
POSITIVE_KEYWORDS = {
    "best", "leading", "top", "recommended", "popular", "excellent", "great",
    "strong", "favorite", "preferred", "go-to", "outstanding", "premier",
    "trusted", "reliable", "powerful", "innovative", "winner", "winners",
}
NEGATIVE_KEYWORDS = {
    "worst", "avoid", "poor", "limited", "outdated", "weak", "disappointing",
    "lacking", "inferior", "buggy", "unreliable", "deprecated", "abandoned",
}

# Tail-fraction of response considered "recommendation/conclusion"
RECOMMENDATION_TAIL_FRACTION = 0.25

# Stop words for entity extraction (common sentence-start capitalized words
# that aren't proper nouns). Stripped from the start of matched entity sequences
# so e.g. "Use Google Maps" → "Google Maps".
ENTITY_STOPWORDS = {
    # Articles / determiners
    "The", "A", "An", "This", "That", "These", "Those", "Some", "Many", "Most",
    "Several", "Other", "Another", "Each", "Every", "All", "Both", "Either",
    "Neither", "No", "Any",
    # Conjunctions / transitions
    "When", "If", "Where", "While", "Although", "Because", "However", "Therefore",
    "Additionally", "Moreover", "Furthermore", "But", "Or", "And", "Nor", "So", "Yet",
    # Ordinals / sequence
    "First", "Second", "Third", "Fourth", "Finally", "Then", "Next", "Last",
    # Pronouns
    "I", "You", "We", "They", "He", "She", "It", "Who", "What", "Which",
    # Imperatives (common sentence-starting verbs)
    "Use", "Try", "Click", "Look", "Visit", "Check", "Open", "See", "Read",
    "Get", "Make", "Take", "Find", "Consider", "Note", "Choose", "Pick",
    "Start", "Avoid", "Remember", "Compare",
    # Modal verbs
    "Can", "Should", "Could", "Would", "Might", "May", "Must", "Will", "Shall",
    # Time / place adverbs
    "Now", "Today", "Tomorrow", "Yesterday", "Here", "There", "Currently", "Recently",
}


# ── Wilson 95% Confidence Interval ──────────────────────────────────────────

def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval at the given z (default 95%, z=1.96).

    Returns (lower, upper) bounds clamped to [0, 1].
    """
    if n == 0:
        return (0.0, 0.0)
    p_hat = successes / n
    denom = 1 + z ** 2 / n
    center = (p_hat + z ** 2 / (2 * n)) / denom
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z ** 2 / (4 * n ** 2)) / denom
    lower = max(0.0, center - half)
    upper = min(1.0, center + half)
    return (round(lower, 4), round(upper, 4))


# ── Cost Estimation ─────────────────────────────────────────────────────────

def cost_per_sample() -> float:
    """Read per-sample cost from env or use default."""
    raw = os.environ.get("GEMINI_COST_PER_SAMPLE_USD")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return DEFAULT_COST_PER_SAMPLE_USD


def estimate_total_cost(num_prompts: int, samples_per_prompt: int) -> float:
    """Estimated cost for a full baseline run, USD."""
    return num_prompts * samples_per_prompt * cost_per_sample()


# ── Signal Extraction ───────────────────────────────────────────────────────

def _name_pattern(name: str) -> re.Pattern:
    """Build a case-insensitive whole-word regex for a brand/competitor name."""
    return re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)


def find_brand_mentions(text: str, brand: str, aliases: list[str]) -> list[dict]:
    """Find all whole-word, case-insensitive matches of brand or aliases in text.

    Returns a list of mention dicts with text, context, position_in_text, sentiment.
    """
    mentions = []
    seen_positions = set()
    candidates = [brand] + list(aliases or [])
    # Sort by length descending so longer aliases match first (avoid double-counting "Tabiji" inside "Tabiji AI")
    candidates = sorted(set(candidates), key=len, reverse=True)
    for name in candidates:
        if not name:
            continue
        for m in _name_pattern(name).finditer(text):
            start = m.start()
            # Skip if a longer alias already claimed this position
            if any(abs(start - s) < 3 for s in seen_positions):
                continue
            seen_positions.add(start)
            mentions.append({
                "text": m.group(0),
                "context": _context_window(text, start, m.end()),
                "position_in_text": start,
                "sentiment": classify_mention_sentiment(text, start, m.end()),
            })
    mentions.sort(key=lambda x: x["position_in_text"])
    return mentions


def _context_window(text: str, start: int, end: int, radius: int = 100) -> str:
    """Extract ±radius chars around a match for human-readable context."""
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    snippet = text[lo:hi]
    # Trim to whole words at the edges
    if lo > 0:
        snippet = "…" + snippet[snippet.find(" ") + 1:] if " " in snippet else snippet
    if hi < len(text):
        last_space = snippet.rfind(" ")
        if last_space > 0:
            snippet = snippet[:last_space] + "…"
    return snippet.strip()


def classify_mention_sentiment(text: str, start: int, end: int, window: int = 50) -> str:
    """Look ±window chars around a mention for positive/negative qualifier patterns."""
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    window_text = text[lo:hi].lower()
    words = set(re.findall(r"\b[a-z-]+\b", window_text))
    has_pos = bool(words & POSITIVE_KEYWORDS)
    has_neg = bool(words & NEGATIVE_KEYWORDS)
    if has_pos and has_neg:
        return "mixed"
    if has_pos:
        return "positive"
    if has_neg:
        return "negative"
    return "neutral"


def find_brand_citations(sources: list[dict], brand_domain: str, aliases: list[str]) -> list[dict]:
    """Extract citations whose domain matches the brand's domain or any alias.

    `sources` is the list returned by _shared.extract_sources (each has uri, title).
    Position is 1-based index in the sources list.
    """
    target_domains = [brand_domain] + [a for a in (aliases or []) if "." in a]
    citations = []
    for idx, source in enumerate(sources):
        uri = source.get("uri", "")
        if not uri:
            continue
        if any(domain_matches(uri, td) for td in target_domains):
            citations.append({
                "url": uri,
                "position": idx + 1,
                "domain": extract_domain(uri),
                "title": source.get("title", ""),
            })
    return citations


def _normalize_domain(s: str) -> str:
    """Lowercase + strip a literal 'www.' prefix. Avoid str.lstrip('www.') which
    strips any leading chars in {w, .} and corrupts domains like 'world.com'."""
    s = s.lower()
    if s.startswith("www."):
        s = s[4:]
    return s


def find_competitor_mentions(text: str, sources: list[dict], competitors: list[str]) -> list[dict]:
    """Find competitor mentions in both response text and grounding citations."""
    mentions = []
    seen = set()
    for comp in competitors or []:
        # Normalize for matching (e.g. tripadvisor.com → "tripadvisor.com")
        # Also extract a brand-like name root (tripadvisor.com → "tripadvisor" → "Tripadvisor")
        domain = _normalize_domain(comp)
        name_root = domain.split(".")[0]
        candidates_name = [comp, name_root, name_root.capitalize(), name_root.title()]

        # Look for the competitor in text by name root
        found_in_text = False
        for cand in candidates_name:
            if cand and _name_pattern(cand).search(text):
                found_in_text = True
                break

        # Look for citations from competitor's domain
        cited = False
        cited_position = None
        for idx, source in enumerate(sources):
            if domain_matches(source.get("uri", ""), domain):
                cited = True
                cited_position = idx + 1
                break

        if found_in_text or cited:
            if domain in seen:
                continue
            seen.add(domain)
            mentions.append({
                "name": name_root.capitalize(),
                "domain": domain,
                "cited": cited,
                "cited_position": cited_position,
            })
    return mentions


def extract_entities(text: str, known: set[str] | None = None) -> list[str]:
    """Extract proper-noun entities via regex. Conservative — multi-word capitalized
    sequences (with leading stopwords stripped) plus CamelCase single tokens.
    """
    found = set()
    # Multi-word capitalized sequences (e.g. "Lonely Planet", "Google Maps")
    for m in re.finditer(r"\b[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)+\b", text):
        words = m.group(0).strip().split()
        # Peel leading sentence-starters ("Use Google Maps" → "Google Maps")
        while words and words[0] in ENTITY_STOPWORDS:
            words = words[1:]
        # Keep only if 2+ words remain (single words go through the CamelCase pass below)
        if len(words) >= 2:
            found.add(" ".join(words))
    # Single-token CamelCase (e.g. "TripAdvisor")
    for m in re.finditer(r"\b[A-Z][a-z]+[A-Z][a-zA-Z]+\b", text):
        found.add(m.group(0))
    # Known names (brand + competitors) — always extract if present
    if known:
        for name in known:
            if name and _name_pattern(name).search(text):
                found.add(name)
    return sorted(found)


def is_in_recommendation_section(text: str, position: int, tail_fraction: float = RECOMMENDATION_TAIL_FRACTION) -> bool:
    """True if `position` falls within the trailing `tail_fraction` of the text."""
    if not text:
        return False
    threshold = len(text) * (1 - tail_fraction)
    return position >= threshold


# ── Sample-level Extraction ─────────────────────────────────────────────────

def extract_sample_signals(
    response: dict,
    sample_idx: int,
    workspace: dict,
) -> dict:
    """Extract all signals from one Gemini API response. Returns a sample dict
    matching the aeo-evidence-v1 sample schema.
    """
    if "error" in response:
        return {
            "sample_idx": sample_idx,
            "error": response["error"],
        }

    text = extract_response_text(response)
    queries = extract_queries(response)
    sources = extract_sources(response)

    brand = workspace["brand"]
    aliases = workspace.get("aliases", [])
    brand_domain = workspace.get("domain", "")
    competitors = workspace.get("competitors", [])

    brand_mentions = find_brand_mentions(text, brand, aliases)
    brand_citations = find_brand_citations(sources, brand_domain, aliases)
    competitor_mentions = find_competitor_mentions(text, sources, competitors)

    # Build the full citations list from grounding chunks (for the evidence file)
    all_citations = []
    for idx, source in enumerate(sources):
        uri = source.get("uri", "")
        if not uri:
            continue
        all_citations.append({
            "url": uri,
            "position": idx + 1,
            "domain": extract_domain(uri),
            "title": source.get("title", ""),
        })

    known_names = {brand, *(aliases or []), *[c.split(".")[0].capitalize() for c in (competitors or [])]}
    entities = extract_entities(text, known_names)

    return {
        "sample_idx": sample_idx,
        "raw_response_text": text,
        "queries_fired": queries,
        "citations": all_citations,
        "brand_mentions": brand_mentions,
        "competitor_mentions": [
            {
                "name": cm["name"],
                "domain": cm["domain"],
                "sentiment": "neutral",  # Could deepen later
            }
            for cm in competitor_mentions
        ],
        "entities": entities,
        # Helper fields (not in schema; popped before write)
        "_brand_cited": bool(brand_citations),
        "_brand_citation_position": brand_citations[0]["position"] if brand_citations else None,
        "_brand_in_recommendation": any(
            is_in_recommendation_section(text, m["position_in_text"]) for m in brand_mentions
        ),
        "_competitor_cited_domains": [cm["domain"] for cm in competitor_mentions if cm["cited"]],
    }


# ── Aggregation ─────────────────────────────────────────────────────────────

def aggregate_samples(samples: list[dict]) -> dict:
    """Roll up a list of sample dicts into the aggregates schema object."""
    successful = [s for s in samples if "error" not in s]
    n = len(successful)
    if n == 0:
        return {}

    mentioned = sum(1 for s in successful if s["brand_mentions"])
    cited = sum(1 for s in successful if s["_brand_cited"])
    recommended = sum(1 for s in successful if s["_brand_in_recommendation"])

    # Citation positions (only for samples where cited)
    positions = [s["_brand_citation_position"] for s in successful if s["_brand_citation_position"]]
    avg_position = round(sum(positions) / len(positions), 2) if positions else None

    # First-mention positions (where mentioned)
    first_positions = [s["brand_mentions"][0]["position_in_text"] for s in successful if s["brand_mentions"]]
    avg_first_position = round(sum(first_positions) / len(first_positions), 2) if first_positions else None

    # Query fan-out: fraction of samples where each query was fired
    query_counts = defaultdict(int)
    for s in successful:
        for q in set(s["queries_fired"]):
            query_counts[q] += 1
    query_fanout = {q: round(c / n, 4) for q, c in query_counts.items()}

    # Entity universe: total entity counts across all samples
    entity_counts = defaultdict(int)
    for s in successful:
        for e in s["entities"]:
            entity_counts[e] += 1
    entity_universe = dict(entity_counts)

    # Competitor share: fraction of samples where each competitor domain was cited
    competitor_share_counts = defaultdict(int)
    for s in successful:
        for d in set(s["_competitor_cited_domains"]):
            competitor_share_counts[d] += 1
    competitor_share = {d: round(c / n, 4) for d, c in competitor_share_counts.items()}

    # Sentiment distribution: counts of each sentiment across all brand mentions
    sentiment_counts = defaultdict(int)
    for s in successful:
        for m in s["brand_mentions"]:
            sentiment_counts[m["sentiment"]] += 1
    sentiment_distribution = {
        "positive": sentiment_counts.get("positive", 0),
        "neutral": sentiment_counts.get("neutral", 0),
        "negative": sentiment_counts.get("negative", 0),
        "mixed": sentiment_counts.get("mixed", 0),
        "unknown": sentiment_counts.get("unknown", 0),
    }

    mention_lo, mention_hi = wilson_ci(mentioned, n)
    cite_lo, cite_hi = wilson_ci(cited, n)

    aggregates = {
        "mention_rate": round(mentioned / n, 4),
        "mention_rate_ci": [mention_lo, mention_hi],
        "citation_rate": round(cited / n, 4),
        "citation_rate_ci": [cite_lo, cite_hi],
        "query_fanout": query_fanout,
        "entity_universe": entity_universe,
        "competitor_share": competitor_share,
        "sentiment_distribution": sentiment_distribution,
    }
    if avg_position is not None:
        aggregates["avg_citation_position"] = avg_position
    if avg_first_position is not None:
        aggregates["first_mention_position_avg"] = avg_first_position

    # Helper exposed for scoring
    aggregates["_recommendation_rate"] = round(recommended / n, 4)
    return aggregates


# ── Scoring (aeo-v1) ────────────────────────────────────────────────────────

def compute_visibility_score(aggregates: dict) -> dict:
    """Apply the aeo-v1 visibility score formula to an aggregates dict."""
    mention_rate = aggregates.get("mention_rate", 0.0)
    citation_rate = aggregates.get("citation_rate", 0.0)
    avg_pos = aggregates.get("avg_citation_position")
    if avg_pos is None:
        position_score = 0.0
    else:
        position_score = max(0.0, 1 - (avg_pos - 1) / 10)
    recommendation_rate = aggregates.get("_recommendation_rate", 0.0)

    sentiment = aggregates.get("sentiment_distribution", {})
    total_mentions = sum(sentiment.values()) or 1
    sentiment_score = (sentiment.get("positive", 0) + 0.5 * sentiment.get("neutral", 0)) / total_mentions

    component_values = {
        "mention_rate": mention_rate,
        "citation_rate": citation_rate,
        "position_score": round(position_score, 4),
        "recommendation_rate": recommendation_rate,
        "sentiment_score": round(sentiment_score, 4),
    }
    components = {}
    total = 0.0
    for name, value in component_values.items():
        weight = SCORE_WEIGHTS[name]
        contribution = round(weight * value * 100, 4)
        components[name] = {"value": value, "weight": weight, "contribution": contribution}
        total += contribution
    return {
        "value": round(total, 4),
        "methodology_version": METHODOLOGY_VERSION,
        "components": components,
    }


# ── Sample Orchestration ────────────────────────────────────────────────────

def run_one_prompt(
    prompt_id: str,
    prompt_text: str,
    intent: str | None,
    workspace: dict,
    api_key: str,
    model: str,
    runs: int,
    concurrency: int,
) -> dict:
    """Run a prompt N times concurrently and return a fully-aggregated promptResult dict."""
    print(f"\n▶ {prompt_id}: {prompt_text!r} × {runs} samples", file=sys.stderr)
    samples: list[dict] = []
    latencies: list[int] = []

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(_timed_call, prompt_text, api_key, model): i for i in range(runs)}
        for future in as_completed(futures):
            sample_idx = futures[future]
            try:
                resp, latency_ms = future.result()
                sample = extract_sample_signals(resp, sample_idx, workspace)
                sample["latency_ms"] = latency_ms
                samples.append(sample)
                latencies.append(latency_ms)
                marker = "✗" if "error" in sample else "✓"
                print(f"  {marker} sample {sample_idx + 1}/{runs} ({latency_ms}ms)", file=sys.stderr)
            except Exception as e:
                samples.append({"sample_idx": sample_idx, "error": str(e)})
                print(f"  ✗ sample {sample_idx + 1}/{runs} EXCEPTION: {e}", file=sys.stderr)

    samples.sort(key=lambda x: x["sample_idx"])
    successful = [s for s in samples if "error" not in s]
    aggregates = aggregate_samples(samples)
    visibility_score = compute_visibility_score(aggregates)

    # Strip helper fields before writing
    for s in samples:
        for k in list(s.keys()):
            if k.startswith("_"):
                del s[k]
    aggregates.pop("_recommendation_rate", None)

    result = {
        "prompt_id": prompt_id,
        "prompt_text": prompt_text,
        "successful_samples": len(successful),
        "failed_samples": len(samples) - len(successful),
        "samples": samples,
        "aggregates": aggregates,
        "visibility_score": visibility_score,
    }
    if intent:
        result["intent"] = intent
    return result


def _timed_call(prompt: str, api_key: str, model: str) -> tuple[dict, int]:
    """Wrap call_gemini to also return latency in ms."""
    t0 = time.time()
    resp = call_gemini(prompt, api_key, model)
    latency_ms = int((time.time() - t0) * 1000)
    return resp, latency_ms


# ── Doctor + Config ─────────────────────────────────────────────────────────

def doctor() -> int:
    """Verify GEMINI_API_KEY works with a 1-token probe. No storage; no extraction."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("✗ GEMINI_API_KEY env var not set", file=sys.stderr)
        return 1
    print(f"✓ GEMINI_API_KEY present (length {len(api_key)})")
    print("  Sending 1-token probe to Gemini...")
    resp = call_gemini("ping", api_key, DEFAULT_MODEL)
    if "error" in resp:
        print(f"✗ Gemini API error: {resp['error']}", file=sys.stderr)
        return 1
    print(f"✓ Gemini responded successfully (model: {DEFAULT_MODEL})")
    return 0


def load_config(path: str) -> dict:
    """Load and minimally validate aeo.config.json."""
    if not os.path.isfile(path):
        print(f"✗ Config file not found: {path}", file=sys.stderr)
        print("  Run aeo-init to create one, or pass --config <path>.", file=sys.stderr)
        sys.exit(2)
    with open(path) as f:
        config = json.load(f)
    if config.get("schema_version") != "aeo-config-v1":
        print(f"✗ Config schema_version is {config.get('schema_version')!r}, expected 'aeo-config-v1'", file=sys.stderr)
        sys.exit(2)
    if not config.get("workspace", {}).get("brand"):
        print("✗ Config workspace.brand is required", file=sys.stderr)
        sys.exit(2)
    return config


# ── Evidence File ───────────────────────────────────────────────────────────

def build_evidence(workspace: dict, run_meta: dict, prompt_results: list[dict]) -> dict:
    """Assemble the full aeo-evidence-v1 document."""
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": {
            "brand": workspace["brand"],
            "domain": workspace.get("domain", ""),
            "aliases": workspace.get("aliases", []),
            "competitors": workspace.get("competitors", []),
        },
        "run": run_meta,
        "prompts": prompt_results,
    }


def write_evidence(evidence: dict, output_dir: str, run_id: str) -> str:
    """Write evidence to <output_dir>/<run_id>.json. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{run_id}.json")
    with open(out_path, "w") as f:
        json.dump(evidence, f, indent=2)
    return out_path


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Take an AI visibility baseline measurement.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--config", default="aeo.config.json", help="Path to workspace config (default: aeo.config.json)")
    p.add_argument("--output-dir", default=None, help="Directory to write evidence file (default: from config)")
    p.add_argument("--runs", type=int, default=None, help=f"Samples per prompt (default: from config or {DEFAULT_RUNS})")
    p.add_argument("--concurrency", type=int, default=None, help=f"Max parallel API calls (default: from config or {DEFAULT_CONCURRENCY})")
    p.add_argument("--model", default=None, help=f"Gemini model (default: from config or {DEFAULT_MODEL})")
    p.add_argument("--prompt", default=None, help="Override config and run a single ad-hoc prompt")
    p.add_argument("--prompt-id", default="adhoc", help="ID to use when --prompt is given")
    p.add_argument("--doctor", action="store_true", help="Verify API key and exit; no measurements")
    p.add_argument("--estimate-cost", action="store_true", help="Print projected cost and exit; no API calls")
    p.add_argument("--yes", "-y", action="store_true", help="Skip cost-confirmation prompt")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.doctor:
        return doctor()

    # Load config (unless running an ad-hoc one-prompt mode that doesn't need workspace).
    # For --prompt mode, still load config if present so we get workspace context.
    config: dict | None = None
    if os.path.isfile(args.config):
        config = load_config(args.config)

    if args.prompt:
        # Ad-hoc mode: still need workspace for extraction. Synthesize a minimal one if no config.
        if config:
            workspace = config["workspace"]
        else:
            workspace = {"brand": "unknown", "domain": "", "aliases": [], "competitors": []}
            print(f"⚠ No config file; running ad-hoc prompt with empty workspace context", file=sys.stderr)
        prompts = [{"prompt_id": args.prompt_id, "text": args.prompt}]
    else:
        if not config:
            print(f"✗ No config file at {args.config} and no --prompt given", file=sys.stderr)
            return 2
        workspace = config["workspace"]
        prompts = config["prompts"]

    runs = args.runs or (config or {}).get("sampling", {}).get("default_runs", DEFAULT_RUNS)
    concurrency = args.concurrency or (config or {}).get("sampling", {}).get("concurrency", DEFAULT_CONCURRENCY)
    model = args.model or DEFAULT_MODEL
    output_dir = args.output_dir or (config or {}).get("data_dir", "aeo-data")

    # Cost gate
    est_cost = estimate_total_cost(len(prompts), runs)
    confirm_threshold = (config or {}).get("limits", {}).get("confirm_over_usd", 5)

    if args.estimate_cost:
        print(f"Projected cost: ${est_cost:.4f} ({len(prompts)} prompt(s) × {runs} samples × ${cost_per_sample():.6f}/sample)")
        return 0

    print(f"Projected cost: ${est_cost:.4f} ({len(prompts)} prompt(s) × {runs} samples)")
    if est_cost > confirm_threshold and not args.yes:
        try:
            resp = input(f"This exceeds the confirm_over_usd threshold (${confirm_threshold}). Continue? [y/N] ")
        except EOFError:
            resp = ""
        if resp.strip().lower() not in {"y", "yes"}:
            print("Aborted.")
            return 1

    # API key check
    api_key = get_api_key()

    # Build run metadata
    started_at = datetime.now(timezone.utc)
    run_id = "run_" + started_at.strftime("%Y-%m-%dT%H-%M-%SZ")
    run_meta = {
        "run_id": run_id,
        "timestamp": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider": "gemini",
        "model": model,
        "samples": runs,
        "methodology_version": METHODOLOGY_VERSION,
        "estimated_cost_usd": round(est_cost, 6),
    }

    # Run every prompt
    prompt_results = []
    t_start = time.time()
    latencies_all: list[int] = []
    for p in prompts:
        intent = p.get("intent")
        # If config didn't provide intent, classify from prompt text
        if not intent:
            intent = classify_intent(p["text"])
        result = run_one_prompt(
            prompt_id=p["prompt_id"],
            prompt_text=p["text"],
            intent=intent,
            workspace=workspace,
            api_key=api_key,
            model=model,
            runs=runs,
            concurrency=concurrency,
        )
        for s in result["samples"]:
            if "latency_ms" in s:
                latencies_all.append(s["latency_ms"])
        prompt_results.append(result)

    elapsed = time.time() - t_start
    if latencies_all:
        latencies_all.sort()
        run_meta["latency_ms_p50"] = latencies_all[len(latencies_all) // 2]

    # Actual cost = estimated * (successful samples / total samples)
    total_samples = sum(p["successful_samples"] + p["failed_samples"] for p in prompt_results)
    successful_total = sum(p["successful_samples"] for p in prompt_results)
    if total_samples > 0:
        run_meta["actual_cost_usd"] = round(est_cost * successful_total / total_samples, 6)

    evidence = build_evidence(workspace, run_meta, prompt_results)
    out_path = write_evidence(evidence, output_dir, run_id)

    print(f"\n✓ Baseline complete in {elapsed:.1f}s")
    print(f"  Successful samples: {successful_total} / {total_samples}")
    print(f"  Evidence file: {out_path}")
    for r in prompt_results:
        score = r["visibility_score"]["value"]
        rate = r["aggregates"].get("mention_rate", 0)
        print(f"  • {r['prompt_id']}: visibility={score:.1f}/100, mention_rate={rate * 100:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
