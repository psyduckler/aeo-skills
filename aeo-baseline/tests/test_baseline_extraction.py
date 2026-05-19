"""Fixture-based extraction tests for aeo-baseline.

These verify the extraction logic against canned Gemini responses without
making any API calls. Run via:

    python3 -m unittest aeo-baseline/tests/test_baseline_extraction.py -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest

# Make the baseline script importable
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import baseline as b  # noqa: E402


# ── Fixture builders ────────────────────────────────────────────────────────

def gemini_response(text: str, queries: list[str] = None, sources: list[dict] = None) -> dict:
    """Build a fake Gemini API response in the shape that _shared expects."""
    return {
        "candidates": [{
            "content": {"parts": [{"text": text}]},
            "groundingMetadata": {
                "webSearchQueries": queries or [],
                "groundingChunks": [{"web": s} for s in (sources or [])],
            },
        }],
    }


TABIJI_WORKSPACE = {
    "brand": "Tabiji",
    "domain": "tabiji.ai",
    "aliases": ["tabiji"],
    "competitors": ["tripadvisor.com", "lonelyplanet.com"],
}


# ── Wilson CI ───────────────────────────────────────────────────────────────

class TestWilsonCI(unittest.TestCase):

    def test_zero_of_n_returns_low_upper_bound(self):
        lo, hi = b.wilson_ci(0, 20)
        self.assertEqual(lo, 0.0)
        self.assertGreater(hi, 0.10)
        self.assertLess(hi, 0.20)

    def test_all_of_n_returns_high_lower_bound(self):
        lo, hi = b.wilson_ci(20, 20)
        self.assertGreater(lo, 0.80)
        self.assertEqual(hi, 1.0)

    def test_midpoint(self):
        lo, hi = b.wilson_ci(10, 20)
        # ~27%-73% per the methodology table
        self.assertAlmostEqual(lo, 0.299, delta=0.05)
        self.assertAlmostEqual(hi, 0.701, delta=0.05)

    def test_n_zero(self):
        self.assertEqual(b.wilson_ci(0, 0), (0.0, 0.0))


# ── Mention extraction ──────────────────────────────────────────────────────

class TestMentionExtraction(unittest.TestCase):

    def test_finds_simple_mention(self):
        text = "When planning a trip, Tabiji is a strong AI-powered option."
        ms = b.find_brand_mentions(text, "Tabiji", [])
        self.assertEqual(len(ms), 1)
        self.assertEqual(ms[0]["text"], "Tabiji")
        self.assertEqual(ms[0]["sentiment"], "positive")

    def test_alias_match(self):
        text = "I've been using tabiji for two years."
        ms = b.find_brand_mentions(text, "Tabiji", ["tabiji"])
        self.assertGreaterEqual(len(ms), 1)

    def test_case_insensitive(self):
        text = "TABIJI offers itinerary planning."
        ms = b.find_brand_mentions(text, "Tabiji", [])
        self.assertEqual(len(ms), 1)

    def test_no_false_positive_on_substring(self):
        text = "The new tabijiverse platform is unrelated."
        ms = b.find_brand_mentions(text, "Tabiji", [])
        self.assertEqual(ms, [])

    def test_negative_sentiment(self):
        text = "Tabiji is poor and outdated compared to alternatives."
        ms = b.find_brand_mentions(text, "Tabiji", [])
        self.assertEqual(ms[0]["sentiment"], "negative")

    def test_mixed_sentiment(self):
        text = "Tabiji is a top option but the UI is poor."
        ms = b.find_brand_mentions(text, "Tabiji", [])
        self.assertEqual(ms[0]["sentiment"], "mixed")

    def test_neutral_default(self):
        text = "Tabiji is an AI travel platform."
        ms = b.find_brand_mentions(text, "Tabiji", [])
        self.assertEqual(ms[0]["sentiment"], "neutral")

    def test_position_recorded(self):
        text = "Use TripAdvisor for reviews. Then check Tabiji for itineraries."
        ms = b.find_brand_mentions(text, "Tabiji", [])
        self.assertEqual(len(ms), 1)
        self.assertGreater(ms[0]["position_in_text"], 30)


# ── Citation extraction ────────────────────────────────────────────────────

class TestCitationExtraction(unittest.TestCase):

    def setUp(self):
        self.sources = [
            {"uri": "https://tripadvisor.com/best-tools", "title": "Best Tools"},
            {"uri": "https://lonelyplanet.com/planning", "title": "Planning Guide"},
            {"uri": "https://wanderlog.com/", "title": "Wanderlog"},
            {"uri": "https://tabiji.ai/", "title": "Tabiji"},
        ]

    def test_brand_citation_found_with_position(self):
        cits = b.find_brand_citations(self.sources, "tabiji.ai", [])
        self.assertEqual(len(cits), 1)
        self.assertEqual(cits[0]["position"], 4)
        self.assertEqual(cits[0]["domain"], "tabiji.ai")

    def test_no_citation_if_domain_absent(self):
        sources = [{"uri": "https://tripadvisor.com/x", "title": "x"}]
        cits = b.find_brand_citations(sources, "tabiji.ai", [])
        self.assertEqual(cits, [])

    def test_www_normalized(self):
        sources = [{"uri": "https://www.tabiji.ai/page", "title": "p"}]
        cits = b.find_brand_citations(sources, "tabiji.ai", [])
        self.assertEqual(len(cits), 1)


class TestDomainNormalization(unittest.TestCase):
    """Regression tests for the lstrip('www.') footgun.

    str.lstrip(chars) strips any leading char in the set, not the literal prefix.
    So 'world.com'.lstrip('www.') returns 'orld.com'. Use _normalize_domain.
    """

    def test_strips_literal_www_prefix(self):
        self.assertEqual(b._normalize_domain("www.tabiji.ai"), "tabiji.ai")

    def test_leaves_w_prefixed_domain_alone(self):
        # Without the fix, this would return "orld.com" or "test.com"
        self.assertEqual(b._normalize_domain("world.com"), "world.com")
        self.assertEqual(b._normalize_domain("wtest.com"), "wtest.com")

    def test_lowercases(self):
        self.assertEqual(b._normalize_domain("EXAMPLE.com"), "example.com")

    def test_competitor_mention_preserves_w_prefix(self):
        sources = [{"uri": "https://world.com/page", "title": "x"}]
        mentions = b.find_competitor_mentions("Some text mentions World.", sources, ["world.com"])
        self.assertEqual(len(mentions), 1)
        # The bug would have produced "orld.com" here
        self.assertEqual(mentions[0]["domain"], "world.com")


# ── Recommendation detection ───────────────────────────────────────────────

class TestRecommendation(unittest.TestCase):

    def test_brand_in_tail_25pct_counts(self):
        text = "Many tools exist for travel planning. " * 20
        text += " I recommend Tabiji for AI-powered itineraries."
        position = text.rfind("Tabiji")
        self.assertTrue(b.is_in_recommendation_section(text, position))

    def test_brand_in_head_does_not_count(self):
        text = "Tabiji is one of many options. " * 20
        position = text.find("Tabiji")
        self.assertFalse(b.is_in_recommendation_section(text, position))


# ── Entity extraction ──────────────────────────────────────────────────────

class TestEntityExtraction(unittest.TestCase):

    def test_multi_word_capitalized(self):
        text = "Use Google Maps for directions and Lonely Planet for guides."
        entities = b.extract_entities(text)
        self.assertIn("Google Maps", entities)
        self.assertIn("Lonely Planet", entities)

    def test_camelcase_single_token(self):
        text = "TripAdvisor is the most established option."
        entities = b.extract_entities(text)
        self.assertIn("TripAdvisor", entities)

    def test_stopwords_filtered(self):
        text = "The platform Tabiji is new. When planning a trip use Google Maps."
        entities = b.extract_entities(text, known={"Tabiji"})
        # Should not flag bare "The" or "When"
        self.assertNotIn("The", entities)
        self.assertNotIn("When", entities)
        # But should include known brand
        self.assertIn("Tabiji", entities)


# ── Full sample extraction ─────────────────────────────────────────────────

class TestSampleExtraction(unittest.TestCase):

    def test_full_pipeline(self):
        response = gemini_response(
            text=(
                "When planning a trip, several tools stand out. "
                "TripAdvisor is the most established platform for reviews. "
                "Lonely Planet offers in-depth destination guides. "
                "Tabiji is a strong newer entrant focused on AI itineraries."
            ),
            queries=["best travel planning tools 2026", "AI travel itinerary planner"],
            sources=[
                {"uri": "https://tripadvisor.com/best", "title": "Best Travel"},
                {"uri": "https://lonelyplanet.com/guides", "title": "Guides"},
                {"uri": "https://wanderlog.com/", "title": "Wanderlog"},
                {"uri": "https://tabiji.ai/", "title": "Tabiji"},
            ],
        )
        sample = b.extract_sample_signals(response, sample_idx=0, workspace=TABIJI_WORKSPACE)

        self.assertEqual(sample["sample_idx"], 0)
        self.assertIn("Tabiji", sample["raw_response_text"])
        self.assertEqual(len(sample["brand_mentions"]), 1)
        self.assertEqual(sample["brand_mentions"][0]["sentiment"], "positive")
        self.assertEqual(len(sample["queries_fired"]), 2)
        self.assertTrue(sample["_brand_cited"])
        self.assertEqual(sample["_brand_citation_position"], 4)
        self.assertGreaterEqual(len(sample["competitor_mentions"]), 1)
        self.assertIn("Tabiji", sample["entities"])

    def test_error_sample_short_circuits(self):
        response = {"error": "HTTP 503: Service unavailable"}
        sample = b.extract_sample_signals(response, sample_idx=3, workspace=TABIJI_WORKSPACE)
        self.assertEqual(sample["sample_idx"], 3)
        self.assertIn("error", sample)
        self.assertNotIn("brand_mentions", sample)


# ── Aggregation ────────────────────────────────────────────────────────────

def _sample_template(sample_idx: int, mentioned: bool, cited: bool, in_rec: bool,
                     sentiment: str = "neutral", queries: list[str] = None,
                     competitor_cited: list[str] = None, entities: list[str] = None) -> dict:
    """Build a minimal sample dict matching the structure aggregate_samples expects."""
    return {
        "sample_idx": sample_idx,
        "raw_response_text": "...",
        "queries_fired": queries or ["q1"],
        "citations": [],
        "brand_mentions": [{"text": "Tabiji", "context": "...", "position_in_text": 100, "sentiment": sentiment}] if mentioned else [],
        "competitor_mentions": [],
        "entities": entities or ["Tabiji"],
        "_brand_cited": cited,
        "_brand_citation_position": 3 if cited else None,
        "_brand_in_recommendation": in_rec,
        "_competitor_cited_domains": competitor_cited or [],
    }


class TestAggregation(unittest.TestCase):

    def test_mention_rate(self):
        samples = [
            _sample_template(i, mentioned=(i < 13), cited=False, in_rec=False)
            for i in range(20)
        ]
        agg = b.aggregate_samples(samples)
        self.assertEqual(agg["mention_rate"], 0.65)

    def test_citation_rate_with_ci(self):
        samples = [
            _sample_template(i, mentioned=True, cited=(i < 9), in_rec=False)
            for i in range(20)
        ]
        agg = b.aggregate_samples(samples)
        self.assertEqual(agg["citation_rate"], 0.45)
        lo, hi = agg["citation_rate_ci"]
        self.assertLess(lo, 0.45)
        self.assertGreater(hi, 0.45)

    def test_query_fanout(self):
        samples = [
            _sample_template(i, True, False, False, queries=["q1", "q2"] if i < 17 else ["q1"])
            for i in range(20)
        ]
        agg = b.aggregate_samples(samples)
        self.assertEqual(agg["query_fanout"]["q1"], 1.0)
        self.assertEqual(agg["query_fanout"]["q2"], 0.85)

    def test_competitor_share(self):
        samples = [
            _sample_template(i, True, False, False, competitor_cited=["tripadvisor.com"] if i < 16 else [])
            for i in range(20)
        ]
        agg = b.aggregate_samples(samples)
        self.assertEqual(agg["competitor_share"]["tripadvisor.com"], 0.80)

    def test_sentiment_distribution(self):
        samples = (
            [_sample_template(i, True, False, False, sentiment="positive") for i in range(6)]
            + [_sample_template(i, True, False, False, sentiment="neutral") for i in range(13)]
            + [_sample_template(20, True, False, False, sentiment="negative")]
        )
        agg = b.aggregate_samples(samples)
        self.assertEqual(agg["sentiment_distribution"]["positive"], 6)
        self.assertEqual(agg["sentiment_distribution"]["neutral"], 13)
        self.assertEqual(agg["sentiment_distribution"]["negative"], 1)

    def test_empty_returns_empty(self):
        self.assertEqual(b.aggregate_samples([{"error": "oops", "sample_idx": 0}]), {})


# ── Scoring ────────────────────────────────────────────────────────────────

class TestVisibilityScore(unittest.TestCase):

    def test_known_inputs_match_methodology(self):
        """Replicate the example fixture's math.

        From METHODOLOGY.md aeo-v1 with mention=0.65, citation=0.45, position=avg 3.2
        (→ 0.78), recommendation=0.10, sentiment=positive=6/neutral=13/total=20
        (→ (6 + 0.5*13)/20 = 0.625).
        """
        aggregates = {
            "mention_rate": 0.65,
            "citation_rate": 0.45,
            "avg_citation_position": 3.2,
            "_recommendation_rate": 0.10,
            "sentiment_distribution": {"positive": 6, "neutral": 13, "negative": 1, "mixed": 0, "unknown": 0},
        }
        score = b.compute_visibility_score(aggregates)
        # Sanity: components sum to value
        total = sum(c["contribution"] for c in score["components"].values())
        self.assertAlmostEqual(total, score["value"], places=2)
        # Sanity: weights match methodology
        self.assertEqual(score["components"]["mention_rate"]["weight"], 0.30)
        self.assertEqual(score["components"]["citation_rate"]["weight"], 0.25)
        self.assertEqual(score["components"]["position_score"]["weight"], 0.20)
        self.assertEqual(score["components"]["recommendation_rate"]["weight"], 0.15)
        self.assertEqual(score["components"]["sentiment_score"]["weight"], 0.10)
        # Methodology version disclosed
        self.assertEqual(score["methodology_version"], "aeo-v1")

    def test_uncited_zeroes_position_component(self):
        aggregates = {
            "mention_rate": 0.50,
            "citation_rate": 0.0,
            "_recommendation_rate": 0.0,
            "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0, "unknown": 0},
        }
        score = b.compute_visibility_score(aggregates)
        self.assertEqual(score["components"]["position_score"]["value"], 0.0)

    def test_position_1_is_max_position_score(self):
        aggregates = {
            "mention_rate": 1.0,
            "citation_rate": 1.0,
            "avg_citation_position": 1.0,
            "_recommendation_rate": 0.0,
            "sentiment_distribution": {},
        }
        score = b.compute_visibility_score(aggregates)
        self.assertEqual(score["components"]["position_score"]["value"], 1.0)


# ── Cost Estimation ────────────────────────────────────────────────────────

class TestCostEstimation(unittest.TestCase):

    def test_default(self):
        # 10 prompts × 20 samples × $0.0003 = $0.06
        cost = b.estimate_total_cost(10, 20)
        self.assertAlmostEqual(cost, 0.06, places=4)

    def test_env_override(self):
        os.environ["GEMINI_COST_PER_SAMPLE_USD"] = "0.001"
        try:
            self.assertEqual(b.cost_per_sample(), 0.001)
        finally:
            del os.environ["GEMINI_COST_PER_SAMPLE_USD"]


# ── Schema conformance ─────────────────────────────────────────────────────

class TestSchemaConformance(unittest.TestCase):
    """If jsonschema is installed, verify produced evidence validates against the schema."""

    def test_built_evidence_validates(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema_path = os.path.join(HERE, "..", "..", "schemas", "aeo-evidence-v1.json")
        schema = json.load(open(schema_path))

        # Build a sample evidence document from mock samples
        samples = [
            _sample_template(i, mentioned=(i < 13), cited=(i < 9), in_rec=(i < 2))
            for i in range(20)
        ]
        # Strip helper fields
        clean = []
        for s in samples:
            s_clean = {k: v for k, v in s.items() if not k.startswith("_")}
            clean.append(s_clean)

        agg = b.aggregate_samples(samples)
        score = b.compute_visibility_score(agg)
        agg.pop("_recommendation_rate", None)

        for s in samples:
            for k in list(s.keys()):
                if k.startswith("_"):
                    del s[k]

        evidence = b.build_evidence(
            TABIJI_WORKSPACE,
            {
                "run_id": "run_2026-05-19T00-00-00Z",
                "timestamp": "2026-05-19T00:00:00Z",
                "provider": "gemini",
                "model": "gemini-3-flash-preview",
                "samples": 20,
                "methodology_version": "aeo-v1",
                "estimated_cost_usd": 0.006,
            },
            [{
                "prompt_id": "test_prompt",
                "prompt_text": "test",
                "intent": "commercial",
                "successful_samples": 20,
                "failed_samples": 0,
                "samples": samples,
                "aggregates": agg,
                "visibility_score": score,
            }]
        )
        errors = list(Draft202012Validator(schema).iter_errors(evidence))
        if errors:
            for e in errors:
                print(f"  {'.'.join(str(x) for x in e.absolute_path)}: {e.message}")
        self.assertEqual(errors, [], "Built evidence must validate against aeo-evidence-v1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
