#!/usr/bin/env python3
"""
Entity Extractor — Extract specific entities (brands, people, stats, tools, URLs)
that Gemini mentions in its grounded responses. Map the entity universe of the
recurring retrieval set.

Usage:
    python3 extract_entities.py "prompt" [--domain example.com] [--runs 20] [--model gemini-3-flash-preview] [--concurrency 5] [--output text|json]

Requires: GEMINI_API_KEY env var
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse


# ── Gemini API ──────────────────────────────────────────────────────────────

def call_gemini(prompt: str, api_key: str, model: str) -> dict:
    """Call Gemini API with Google Search grounding."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                wait = (2 ** attempt) + 1
                print(f"    Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            elif attempt < 4:
                time.sleep(2 ** attempt)
            else:
                return {"error": f"HTTP {e.code}: {e.reason}"}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < 4:
                time.sleep(2 ** attempt)
            else:
                return {"error": str(e)}


def extract_response_text(response: dict) -> str:
    """Extract text from Gemini response."""
    texts = []
    for cand in response.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if "text" in part:
                texts.append(part["text"])
    return "\n".join(texts)


def extract_sources(response: dict) -> list:
    """Extract grounding source URLs from response."""
    sources = []
    seen = set()
    for cand in response.get("candidates", []):
        meta = cand.get("groundingMetadata", {})
        for chunk in meta.get("groundingChunks", []):
            web = chunk.get("web", {})
            uri = web.get("uri", "")
            if uri and uri not in seen:
                seen.add(uri)
                sources.append(uri)
    return sources


def get_domain(uri: str) -> str:
    """Extract clean domain from URI."""
    try:
        parsed = urlparse(uri)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


# ── Entity Extraction (regex-based) ────────────────────────────────────────

# Common words that look like proper nouns but aren't entities
STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "these", "those",
    "have", "has", "had", "been", "being", "will", "would", "could",
    "should", "may", "might", "can", "are", "were", "was", "not", "but",
    "its", "their", "your", "our", "his", "her", "they", "them", "also",
    "some", "many", "most", "more", "such", "than", "when", "where",
    "which", "while", "what", "how", "why", "who", "each", "both",
    "all", "any", "few", "here", "there", "then", "now", "just", "only",
    "very", "well", "even", "still", "also", "too", "yet", "much",
    "however", "therefore", "moreover", "furthermore", "additionally",
    "overall", "typically", "generally", "usually", "often", "sometimes",
    "according", "based", "including", "following", "considering",
    "regarding", "unlike", "like", "unlike", "during", "after", "before",
    "between", "among", "through", "about", "into", "over", "under",
    "above", "below", "key", "top", "best", "first", "last", "new",
    "other", "another", "one", "two", "three", "four", "five",
    "several", "various", "different", "specific", "particular",
    "important", "significant", "major", "main", "primary",
    "note", "example", "examples", "conclusion", "introduction",
    "summary", "overview", "features", "benefits", "pros", "cons",
    "free", "paid", "premium", "basic", "advanced", "standard",
    "you", "your", "it", "its",
}

# Sentence starters and common patterns to exclude
EXCLUDE_PATTERNS = {
    "In", "On", "At", "By", "To", "As", "If", "So", "Or", "No", "Do",
    "It", "Is", "An", "Up", "We", "My", "He", "Be",
}


def extract_brands(text: str) -> list:
    """Extract brand names / proper nouns (capitalized multi-word sequences)."""
    brands = []

    # Pattern: 2+ capitalized words in sequence (e.g., "Google Analytics", "Microsoft Teams")
    for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
        name = match.group(1)
        words = name.split()
        # Skip if all words are stop words or too short
        if all(w.lower() in STOP_WORDS or w in EXCLUDE_PATTERNS for w in words):
            continue
        if len(name) > 3:
            brands.append(name)

    # Single capitalized words that look like brand names (followed by ™, ®, or in specific contexts)
    for match in re.finditer(r'\b([A-Z][a-z]{2,}(?:\.(?:com|io|ai|co|org|net))?)(?:\s*[™®])?(?:\s+(?:is|was|has|offers|provides|includes|features|helps|enables|allows))', text):
        name = match.group(1)
        if name.lower() not in STOP_WORDS and name not in EXCLUDE_PATTERNS:
            brands.append(name)

    # CamelCase or all-caps brand names (e.g., "HubSpot", "SEMrush", "SEO")
    for match in re.finditer(r'\b([A-Z][a-z]+[A-Z][a-zA-Z]*)\b', text):
        brands.append(match.group(1))

    return brands


def extract_statistics(text: str) -> list:
    """Extract numbers and statistics with context."""
    stats = []

    # Percentages: "85%", "over 90%", "approximately 45.2%"
    for match in re.finditer(r'(?:approximately |about |over |under |nearly |around |up to )?(\d[\d,]*\.?\d*)\s*%', text):
        full = match.group(0).strip()
        stats.append(full)

    # Dollar/currency amounts: "$1.2 million", "$500", "€100"
    for match in re.finditer(r'[\$€£¥][\d,]+(?:\.\d+)?(?:\s*(?:million|billion|trillion|M|B|K))?', text):
        stats.append(match.group(0).strip())

    # Large numbers with context: "1.5 million users", "10,000 customers"
    for match in re.finditer(r'\b(\d[\d,]+(?:\.\d+)?)\s*(million|billion|trillion|thousand|users|customers|employees|downloads|subscribers|companies|businesses|teams|organizations)\b', text, re.IGNORECASE):
        stats.append(match.group(0).strip())

    # Years that indicate data freshness: "in 2024", "2025 report", "as of 2024"
    for match in re.finditer(r'\b((?:in|as of|since|from|by|updated?)\s+)?20[2-3]\d\b', text):
        full = match.group(0).strip()
        if len(full) > 4:  # Only if there's context, not just a bare year
            stats.append(full)

    # Numbered lists/rankings: "#1", "top 10", "ranked #3"
    for match in re.finditer(r'(?:#\d+|top\s+\d+|ranked?\s+#?\d+)', text, re.IGNORECASE):
        stats.append(match.group(0).strip())

    return stats


def extract_people(text: str) -> list:
    """Extract people names (First Last patterns)."""
    people = []

    # Pattern: First Last, possibly with middle initial
    # Preceded by attribution context to reduce false positives
    for match in re.finditer(
        r'(?:by|author|CEO|CTO|founder|co-founder|director|VP|professor|Dr\.|Mr\.|Ms\.|Mrs\.)\s+'
        r'([A-Z][a-z]+\s+(?:[A-Z]\.\s+)?[A-Z][a-z]+)',
        text
    ):
        people.append(match.group(1).strip())

    # Also look for "Name, Title at Company" patterns
    for match in re.finditer(
        r'([A-Z][a-z]+\s+[A-Z][a-z]+),\s*(?:CEO|CTO|founder|co-founder|director|VP|head|lead|chief)',
        text
    ):
        people.append(match.group(1).strip())

    return people


def extract_tools_products(text: str) -> list:
    """Extract tool/product names (often CamelCase or with trademark patterns)."""
    tools = []

    # CamelCase words (HubSpot, ClickUp, etc.)
    for match in re.finditer(r'\b([A-Z][a-z]+[A-Z][a-zA-Z]+)\b', text):
        tools.append(match.group(1))

    # Words ending in common tool suffixes
    for match in re.finditer(
        r'\b([A-Z][a-z]+(?:ly|io|ify|ful|hub|spot|flow|stack|base|kit|lab|box|desk|cloud|craft|wise))\b',
        text, re.IGNORECASE
    ):
        name = match.group(1)
        if name[0].isupper() and name.lower() not in STOP_WORDS:
            tools.append(name)

    # ".com/.io/.ai" domains mentioned in text as products
    for match in re.finditer(r'\b([A-Za-z]+\.(?:com|io|ai|co|app|dev))\b', text):
        tools.append(match.group(1))

    return tools


def extract_urls_from_text(text: str) -> list:
    """Extract URLs mentioned in the response text."""
    urls = []
    for match in re.finditer(r'https?://[^\s)\]>,"]+', text):
        urls.append(match.group(0).rstrip(".,;:"))
    return urls


def extract_all_entities(text: str) -> dict:
    """Extract all entity types from text."""
    return {
        "brands": extract_brands(text),
        "statistics": extract_statistics(text),
        "people": extract_people(text),
        "tools": extract_tools_products(text),
        "urls": extract_urls_from_text(text),
    }


# ── Main Logic ──────────────────────────────────────────────────────────────

def run_extractor(prompt: str, runs: int, model: str, concurrency: int, domain: str = None):
    """Run prompt N times and extract entities from responses."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)

    print(f"Entity Extractor: \"{prompt}\"", file=sys.stderr)
    print(f"Model: {model} | Runs: {runs}", file=sys.stderr)
    if domain:
        print(f"Gap analysis domain: {domain}", file=sys.stderr)
    print(file=sys.stderr)

    # Phase 1: Run prompt and collect responses
    all_entities_by_type = defaultdict(lambda: defaultdict(int))
    all_source_domains = defaultdict(int)
    errors = 0
    successful_runs = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(call_gemini, prompt, api_key, model): i for i in range(runs)}
        for future in as_completed(futures):
            run_idx = futures[future]
            try:
                resp = future.result()
                if "error" in resp:
                    errors += 1
                    print(f"  Run {run_idx + 1}: ERROR - {resp['error']}", file=sys.stderr)
                    continue

                text = extract_response_text(resp)
                sources = extract_sources(resp)
                successful_runs += 1

                # Extract entities from response text
                entities = extract_all_entities(text)
                for entity_type, items in entities.items():
                    for item in items:
                        all_entities_by_type[entity_type][item] += 1

                # Track source domains
                for src in sources:
                    d = get_domain(src)
                    if d:
                        all_source_domains[d] += 1

                entity_count = sum(len(v) for v in entities.values())
                print(f"  Run {run_idx + 1}: {entity_count} entities, {len(sources)} sources", file=sys.stderr)
            except Exception as e:
                errors += 1
                print(f"  Run {run_idx + 1}: EXCEPTION - {e}", file=sys.stderr)

    if successful_runs == 0:
        print("Error: No successful runs", file=sys.stderr)
        sys.exit(1)

    # Build ranked entity lists
    entity_rankings = {}
    for entity_type, counts in all_entities_by_type.items():
        sorted_entities = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        entity_rankings[entity_type] = [
            {
                "entity": name,
                "count": count,
                "frequency": round(count / successful_runs * 100),
            }
            for name, count in sorted_entities
        ]

    # Total unique entities
    total_unique = sum(len(v) for v in entity_rankings.values())

    # Domain gap analysis
    gap_analysis = None
    if domain:
        gap_analysis = analyze_entity_gap(prompt, domain, entity_rankings, all_source_domains)

    result = {
        "prompt": prompt,
        "model": model,
        "total_runs": runs,
        "successful_runs": successful_runs,
        "errors": errors,
        "total_unique_entities": total_unique,
        "entities": entity_rankings,
        "top_source_domains": [
            {"domain": d, "count": c}
            for d, c in sorted(all_source_domains.items(), key=lambda x: -x[1])[:15]
        ],
        "gap_analysis": gap_analysis,
    }

    return result


def analyze_entity_gap(prompt: str, domain: str, entity_rankings: dict,
                       source_domains: dict) -> dict:
    """Analyze which high-frequency entities a domain should include."""
    target = domain.lower()
    if target.startswith("www."):
        target = target[4:]
    brand = target.split(".")[0]

    # Check if domain is even being cited
    domain_cited = any(target in d for d in source_domains.keys())

    # Find entities that mention the brand/domain
    own_entities = []
    for entity_type, rankings in entity_rankings.items():
        for item in rankings:
            name = item["entity"].lower()
            if brand in name or target in name:
                own_entities.append({
                    "type": entity_type,
                    "entity": item["entity"],
                    "count": item["count"],
                })

    # High-frequency entities the domain should include
    # (entities appearing in >30% of runs that aren't the domain itself)
    should_include = []
    for entity_type, rankings in entity_rankings.items():
        for item in rankings:
            if item["frequency"] >= 30:
                name = item["entity"].lower()
                if brand not in name and target not in name:
                    should_include.append({
                        "type": entity_type,
                        "entity": item["entity"],
                        "frequency": item["frequency"],
                    })

    return {
        "domain": domain,
        "is_cited": domain_cited,
        "own_entities_mentioned": own_entities,
        "high_frequency_entities": should_include,
        "recommendation": (
            f"Your content should mention these high-frequency entities "
            f"to align with what Gemini includes in its responses. "
            f"{'Your domain IS being cited — reinforce these entities to maintain position.' if domain_cited else 'Your domain is NOT being cited — including these entities may help enter the candidate set.'}"
        ),
    }


def format_text(result: dict) -> str:
    """Format results as human-readable text."""
    lines = []
    lines.append(f"Entity Extractor: \"{result['prompt']}\"")
    lines.append(f"Model: {result['model']}")
    lines.append(f"Runs: {result['successful_runs']}/{result['total_runs']} successful")
    lines.append(f"Total unique entities: {result['total_unique_entities']}")
    lines.append("")

    type_labels = {
        "brands": "🏢 BRANDS & PROPER NOUNS",
        "statistics": "📊 STATISTICS & NUMBERS",
        "people": "👤 PEOPLE",
        "tools": "🔧 TOOLS & PRODUCTS",
        "urls": "🔗 URLs MENTIONED IN TEXT",
    }

    for entity_type in ["brands", "statistics", "tools", "people", "urls"]:
        rankings = result["entities"].get(entity_type, [])
        if not rankings:
            continue

        label = type_labels.get(entity_type, entity_type.upper())
        lines.append(f"{label}:")
        lines.append("=" * 60)

        for item in rankings[:20]:
            bar = "█" * max(1, item["frequency"] // 5)
            lines.append(f"  {item['frequency']:3d}% ({item['count']:2d}x) {bar} {item['entity']}")

        lines.append("")

    # Source domains
    if result.get("top_source_domains"):
        lines.append("TOP SOURCE DOMAINS:")
        lines.append("=" * 60)
        for d in result["top_source_domains"][:10]:
            lines.append(f"  {d['count']:3d}x — {d['domain']}")
        lines.append("")

    # Gap analysis
    ga = result.get("gap_analysis")
    if ga:
        lines.append(f"ENTITY GAP ANALYSIS: {ga['domain']}")
        lines.append("=" * 60)
        cited_str = "✓ Cited" if ga["is_cited"] else "✗ Not cited"
        lines.append(f"  Domain status: {cited_str}")

        if ga["own_entities_mentioned"]:
            lines.append(f"  Your brand mentioned as:")
            for item in ga["own_entities_mentioned"]:
                lines.append(f"    {item['count']}x — {item['entity']} ({item['type']})")

        if ga["high_frequency_entities"]:
            lines.append(f"\n  High-frequency entities to include in your content:")
            for item in ga["high_frequency_entities"][:15]:
                lines.append(f"    {item['frequency']}% — {item['entity']} ({item['type']})")

        lines.append(f"\n  → {ga['recommendation']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Extract entities Gemini mentions in grounded responses — map the entity universe"
    )
    parser.add_argument("prompt", help="The query/prompt to analyze")
    parser.add_argument("--domain",
                        help="Domain for entity gap analysis (e.g., example.com)")
    parser.add_argument("--runs", type=int, default=20,
                        help="Number of runs (default: 20)")
    parser.add_argument("--model", default="gemini-3-flash-preview",
                        help="Gemini model (default: gemini-3-flash-preview)")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="Max concurrent requests (default: 5)")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    args = parser.parse_args()

    result = run_extractor(args.prompt, args.runs, args.model, args.concurrency, args.domain)

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
