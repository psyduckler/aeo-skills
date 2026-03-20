#!/usr/bin/env python3
"""Shared Gemini API client for AEO skills.

Provides common functions used across all AEO skill scripts:
- Gemini API calls with Google Search grounding and retry logic
- Response parsing (text, queries, sources)
- Domain/URL utilities
- Concurrent execution helpers
- Search query intent classification

Import from any script:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from shared.gemini_client import call_gemini, extract_sources, ...
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# ── Constants ───────────────────────────────────────────────────────────────

DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_RUNS = 20
DEFAULT_CONCURRENCY = 5
MAX_RETRIES = 5
API_BASE = "https://generativelanguage.googleapis.com/v1beta"


# ── API Key ─────────────────────────────────────────────────────────────────

def get_api_key() -> str:
    """Get GEMINI_API_KEY from env, exit with error if missing."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)
    return api_key


# ── Gemini API ──────────────────────────────────────────────────────────────

def call_gemini(prompt: str, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """Call Gemini API with Google Search grounding.

    Retries with exponential backoff on transient errors and 429 rate limits.
    Returns parsed JSON response dict, or {"error": "..."} on failure.
    """
    url = f"{API_BASE}/models/{model}:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait = (2 ** attempt) + 1
                print(f"    Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            elif attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                return {"error": f"HTTP {e.code}: {e.reason}"}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                return {"error": str(e)}


# ── Response Extraction ────────────────────────────────────────────────────

def extract_response_text(response: dict) -> str:
    """Extract the text content from a Gemini response."""
    texts = []
    for cand in response.get("candidates", []):
        content = cand.get("content", {})
        for part in content.get("parts", []):
            if "text" in part:
                texts.append(part["text"])
    return "\n".join(texts)


def extract_queries(response: dict) -> list:
    """Extract webSearchQueries from grounding metadata."""
    queries = []
    for cand in response.get("candidates", []):
        meta = cand.get("groundingMetadata", {})
        queries.extend(meta.get("webSearchQueries", []))
    return queries


def extract_sources(response: dict) -> list:
    """Extract grounding source URLs and titles from grounding chunks.

    Returns list of {"title": str, "uri": str} dicts, deduplicated by URI.
    """
    sources = []
    seen = set()
    for cand in response.get("candidates", []):
        meta = cand.get("groundingMetadata", {})
        for chunk in meta.get("groundingChunks", []):
            web = chunk.get("web", {})
            uri = web.get("uri", "")
            title = web.get("title", "")
            if uri and uri not in seen:
                seen.add(uri)
                sources.append({"title": title, "uri": uri})
    return sources


# ── Domain / URL Utilities ──────────────────────────────────────────────────

def extract_domain(url: str) -> str:
    """Extract clean domain from URL, stripping www. prefix."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def domain_matches(url: str, target_domain: str) -> bool:
    """Check if URL belongs to target domain (handles www prefix)."""
    target = target_domain.lower()
    if target.startswith("www."):
        target = target[4:]
    url_domain = extract_domain(url)
    return target in url_domain


# ── Concurrency ────────────────────────────────────────────────────────────

def run_concurrent(fn, items: list, concurrency: int = DEFAULT_CONCURRENCY) -> list:
    """Run a function concurrently over items with ThreadPoolExecutor.

    Args:
        fn: callable that takes a single item and returns a result
        items: list of items to process
        concurrency: max concurrent workers

    Returns:
        list of (index, result) tuples in completion order
    """
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(fn, item): i for i, item in enumerate(items)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                results.append((idx, result))
            except Exception as e:
                results.append((idx, {"error": str(e)}))
    return results


# ── Intent Classification ──────────────────────────────────────────────────

def classify_intent(query: str) -> str:
    """Classify search query intent: informational/commercial/navigational/transactional."""
    q = query.strip().lower()

    # Transactional — strongest signals, check first
    transactional_patterns = [
        r'\bbuy\b', r'\bpurchase\b', r'\border\b', r'\bsubscribe\b',
        r'\bdownload\b', r'\binstall\b', r'\bget started\b',
        r'\bfree trial\b', r'\btrial\b', r'\bdiscount\b', r'\bcoupon\b',
        r'\bpromo\b', r'\bdeal\b', r'\bpricing\b', r'\bprice\b',
        r'\bcost\b', r'\bcheap\b', r'\baffordable\b', r'\bsign up\b',
        r'\bregister\b', r'\bcheckout\b',
    ]
    for pat in transactional_patterns:
        if re.search(pat, q):
            return "transactional"

    # Navigational — brand/domain references
    navigational_patterns = [
        r'\blogin\b', r'\blog in\b', r'\bsign in\b', r'\bsignin\b',
        r'\bwebsite\b', r'\bofficial\b', r'\bhomepage\b',
        r'\b\w+\.(com|org|net|io|ai|co|dev)\b',
        r'\bapp\b', r'\bportal\b', r'\bdashboard\b', r'\baccount\b',
    ]
    for pat in navigational_patterns:
        if re.search(pat, q):
            return "navigational"

    # Commercial — comparison/evaluation signals
    commercial_patterns = [
        r'\bbest\b', r'\btop\b', r'\bvs\b', r'\bversus\b', r'\bcompare\b',
        r'\bcomparison\b', r'\breview\b', r'\breviews\b', r'\brating\b',
        r'\brated\b', r'\brecommend\b', r'\balternative\b', r'\balternatives\b',
        r'\bpros and cons\b', r'\bworth it\b', r'\bshould i\b',
        r'\bwhich\b.*\bbetter\b', r'\bbetter than\b',
    ]
    for pat in commercial_patterns:
        if re.search(pat, q):
            return "commercial"

    # Informational — default
    return "informational"
