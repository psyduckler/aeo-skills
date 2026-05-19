"""Tests for aeo-report. Operates entirely on fixture evidence dicts —
no filesystem evidence files needed for unit tests."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import report as r  # noqa: E402


# ── Fixture builders ────────────────────────────────────────────────────────

def make_evidence(
    timestamp: str,
    prompts: list[dict],
    brand: str = "Tabiji",
    domain: str = "tabiji.ai",
    competitors: list[str] | None = None,
) -> dict:
    """Build a complete aeo-evidence-v1 document for testing."""
    return {
        "schema_version": "aeo-evidence-v1",
        "workspace": {
            "brand": brand,
            "domain": domain,
            "aliases": [brand.lower()],
            "competitors": competitors or ["tripadvisor.com", "lonelyplanet.com"],
        },
        "run": {
            "run_id": f"run_{timestamp.replace(':', '-')}",
            "timestamp": timestamp,
            "provider": "gemini",
            "model": "gemini-3-flash-preview",
            "samples": 20,
            "methodology_version": "aeo-v1",
        },
        "prompts": prompts,
    }


def make_prompt_result(
    prompt_id: str,
    mention_rate: float,
    citation_rate: float,
    visibility_score: float,
    avg_position: float | None = None,
    competitor_share: dict | None = None,
    samples: list[dict] | None = None,
    text: str | None = None,
) -> dict:
    """Build a single prompts[] entry."""
    aggregates = {
        "mention_rate": mention_rate,
        "mention_rate_ci": [max(0.0, mention_rate - 0.15), min(1.0, mention_rate + 0.15)],
        "citation_rate": citation_rate,
        "citation_rate_ci": [max(0.0, citation_rate - 0.15), min(1.0, citation_rate + 0.15)],
        "query_fanout": {},
        "entity_universe": {"Tabiji": 12, "TripAdvisor": 18},
        "competitor_share": competitor_share or {},
        "sentiment_distribution": {"positive": 5, "neutral": 14, "negative": 1, "mixed": 0, "unknown": 0},
    }
    if avg_position is not None:
        aggregates["avg_citation_position"] = avg_position
    return {
        "prompt_id": prompt_id,
        "prompt_text": text or f"Test prompt for {prompt_id}",
        "intent": "commercial",
        "successful_samples": 20,
        "failed_samples": 0,
        "samples": samples or [],
        "aggregates": aggregates,
        "visibility_score": {
            "value": visibility_score,
            "methodology_version": "aeo-v1",
            "components": {},
        },
    }


# ── Loading ────────────────────────────────────────────────────────────────

class TestLoadEvidence(unittest.TestCase):

    def test_loads_and_sorts_by_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            # Write in reverse-timestamp order on disk
            for ts in ["2026-05-19T00:00:00Z", "2026-05-17T00:00:00Z", "2026-05-18T00:00:00Z"]:
                ev = make_evidence(ts, [make_prompt_result("p1", 0.5, 0.3, 40.0)])
                with open(os.path.join(d, f"file_{ts}.json"), "w") as f:
                    json.dump(ev, f)
            loaded = r.load_evidence_files(d)
            timestamps = [ev["run"]["timestamp"] for ev in loaded]
            self.assertEqual(timestamps, ["2026-05-17T00:00:00Z", "2026-05-18T00:00:00Z", "2026-05-19T00:00:00Z"])

    def test_skips_wrong_schema(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "good.json"), "w") as f:
                json.dump(make_evidence("2026-05-18T00:00:00Z", []), f)
            with open(os.path.join(d, "bad.json"), "w") as f:
                json.dump({"schema_version": "wrong", "prompts": []}, f)
            loaded = r.load_evidence_files(d)
            self.assertEqual(len(loaded), 1)

    def test_skips_corrupt_json(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "good.json"), "w") as f:
                json.dump(make_evidence("2026-05-18T00:00:00Z", []), f)
            with open(os.path.join(d, "corrupt.json"), "w") as f:
                f.write("{not valid json")
            loaded = r.load_evidence_files(d)
            self.assertEqual(len(loaded), 1)


class TestGroupByPrompt(unittest.TestCase):

    def test_groups_across_runs(self):
        ev1 = make_evidence("2026-05-17T00:00:00Z", [
            make_prompt_result("p1", 0.5, 0.3, 40.0),
            make_prompt_result("p2", 0.6, 0.4, 50.0),
        ])
        ev2 = make_evidence("2026-05-18T00:00:00Z", [
            make_prompt_result("p1", 0.55, 0.32, 42.0),
        ])
        grouped = r.group_by_prompt([ev1, ev2])
        self.assertEqual(set(grouped.keys()), {"p1", "p2"})
        self.assertEqual(len(grouped["p1"]), 2)
        self.assertEqual(len(grouped["p2"]), 1)


# ── Trend Math ─────────────────────────────────────────────────────────────

class TestTrendArrow(unittest.TestCase):

    def test_up(self):
        self.assertEqual(r.trend_arrow(0.5, 0.6), "↑")

    def test_down(self):
        self.assertEqual(r.trend_arrow(0.6, 0.5), "↓")

    def test_flat_within_epsilon(self):
        self.assertEqual(r.trend_arrow(0.5, 0.51), "→")

    def test_none_inputs(self):
        self.assertEqual(r.trend_arrow(None, 0.5), "—")


class TestDomainMatchesBrand(unittest.TestCase):
    """Regression tests: the old `brand_domain in domain` substring match
    would have falsely flagged 'notabiji.ai' as matching 'tabiji.ai'."""

    def test_exact(self):
        self.assertTrue(r.domain_matches_brand("tabiji.ai", "tabiji.ai"))

    def test_subdomain(self):
        self.assertTrue(r.domain_matches_brand("blog.tabiji.ai", "tabiji.ai"))
        self.assertTrue(r.domain_matches_brand("www.tabiji.ai", "tabiji.ai"))

    def test_false_substring(self):
        # The exact bug the helper exists to prevent
        self.assertFalse(r.domain_matches_brand("notabiji.ai", "tabiji.ai"))

    def test_attacker_appended(self):
        self.assertFalse(r.domain_matches_brand("tabiji.ai.attacker.com", "tabiji.ai"))

    def test_empty(self):
        self.assertFalse(r.domain_matches_brand("", "tabiji.ai"))
        self.assertFalse(r.domain_matches_brand("tabiji.ai", ""))

    def test_case_insensitive(self):
        self.assertTrue(r.domain_matches_brand("Tabiji.AI", "tabiji.ai"))


class TestSeries(unittest.TestCase):

    def test_pulls_values(self):
        hist = [
            ({}, {"aggregates": {"mention_rate": 0.4}}),
            ({}, {"aggregates": {"mention_rate": 0.5}}),
            ({}, {"aggregates": {"mention_rate": 0.6}}),
        ]
        self.assertEqual(r.series(hist, ["aggregates", "mention_rate"]), [0.4, 0.5, 0.6])

    def test_missing_path_returns_none(self):
        hist = [({}, {"aggregates": {}}), ({}, {})]
        self.assertEqual(r.series(hist, ["aggregates", "mention_rate"]), [None, None])


# ── Decay Detection ────────────────────────────────────────────────────────

class TestDecayDetection(unittest.TestCase):

    def _hist(self, rates: list[float]) -> list:
        return [({}, make_prompt_result("p", 0.5, rate, 40.0)) for rate in rates]

    def test_no_decay_when_stable(self):
        hist = self._hist([0.5, 0.5, 0.5, 0.5, 0.5])
        self.assertIsNone(r.detect_decay(hist, ["aggregates", "citation_rate"]))

    def test_detects_steep_decline(self):
        hist = self._hist([0.8, 0.75, 0.7, 0.3, 0.25, 0.2])
        result = r.detect_decay(hist, ["aggregates", "citation_rate"])
        self.assertIsNotNone(result)
        self.assertEqual(result["severity"], "HIGH")

    def test_detects_mild_decline(self):
        # Use 0.5 → 0.35 so delta_fraction = 0.30 (above the 0.20 threshold,
        # well clear of float-precision edges, and lands in MEDIUM range)
        hist = self._hist([0.5, 0.5, 0.5, 0.35, 0.35, 0.35])
        result = r.detect_decay(hist, ["aggregates", "citation_rate"])
        self.assertIsNotNone(result)
        self.assertIn(result["severity"], {"LOW", "MEDIUM"})

    def test_skips_when_too_few_runs(self):
        hist = self._hist([0.8, 0.2])
        self.assertIsNone(r.detect_decay(hist, ["aggregates", "citation_rate"]))


# ── Cannibalization ────────────────────────────────────────────────────────

class TestCannibalization(unittest.TestCase):

    def _samples_with_owned_urls(self, urls: list[str]) -> list[dict]:
        """Build 5 samples where each sample cites each given URL."""
        samples = []
        for i in range(5):
            samples.append({
                "sample_idx": i,
                "citations": [
                    {"url": u, "position": j + 1, "domain": "tabiji.ai"} for j, u in enumerate(urls)
                ],
                "brand_mentions": [],
                "competitor_mentions": [],
                "entities": [],
                "queries_fired": [],
            })
        return samples

    def test_no_cannibalization_with_single_url(self):
        p = make_prompt_result("p", 0.5, 0.5, 40.0, samples=self._samples_with_owned_urls(["https://tabiji.ai/a"]))
        hist = [({}, p)]
        self.assertIsNone(r.detect_cannibalization(hist, "tabiji.ai"))

    def test_detects_multiple_urls(self):
        p = make_prompt_result("p", 0.5, 0.5, 40.0, samples=self._samples_with_owned_urls([
            "https://tabiji.ai/a", "https://tabiji.ai/b", "https://tabiji.ai/c"
        ]))
        hist = [({}, p)]
        result = r.detect_cannibalization(hist, "tabiji.ai")
        self.assertIsNotNone(result)
        self.assertEqual(len(result["urls"]), 3)


# ── Hub Pages ──────────────────────────────────────────────────────────────

class TestHubPages(unittest.TestCase):

    def _samples_citing(self, urls: list[str]) -> list[dict]:
        return [
            {"sample_idx": 0, "citations": [{"url": u, "position": 1, "domain": "tabiji.ai"} for u in urls],
             "brand_mentions": [], "competitor_mentions": [], "entities": [], "queries_fired": []},
        ]

    def test_hub_url_across_prompts(self):
        # Same URL cited in p1 and p2; another URL only in p1
        hub_url = "https://tabiji.ai/best-tools"
        single_url = "https://tabiji.ai/single"
        ev1 = make_evidence("2026-05-18T00:00:00Z", [
            make_prompt_result("p1", 0.5, 0.5, 40.0, samples=self._samples_citing([hub_url, single_url])),
            make_prompt_result("p2", 0.5, 0.5, 40.0, samples=self._samples_citing([hub_url])),
            make_prompt_result("p3", 0.5, 0.5, 40.0, samples=self._samples_citing([hub_url])),
        ])
        by_prompt = r.group_by_prompt([ev1])
        hubs = r.detect_hub_pages(by_prompt, "tabiji.ai")
        urls = [h["url"] for h in hubs]
        self.assertIn(hub_url, urls)
        self.assertNotIn(single_url, urls)

    def test_no_hubs_when_each_url_unique(self):
        ev1 = make_evidence("2026-05-18T00:00:00Z", [
            make_prompt_result("p1", 0.5, 0.5, 40.0, samples=self._samples_citing(["https://tabiji.ai/a"])),
            make_prompt_result("p2", 0.5, 0.5, 40.0, samples=self._samples_citing(["https://tabiji.ai/b"])),
        ])
        by_prompt = r.group_by_prompt([ev1])
        hubs = r.detect_hub_pages(by_prompt, "tabiji.ai")
        self.assertEqual(hubs, [])


# ── Competitor Share Changes ───────────────────────────────────────────────

class TestCompetitorShareChanges(unittest.TestCase):

    def test_flags_large_swings(self):
        hist = [
            ({}, make_prompt_result("p", 0.5, 0.5, 40.0, competitor_share={"a.com": 0.8, "b.com": 0.2})),
            ({}, make_prompt_result("p", 0.5, 0.5, 40.0, competitor_share={"a.com": 0.3, "b.com": 0.7})),
        ]
        changes = r.competitor_share_changes(hist)
        names = {c["competitor"] for c in changes}
        self.assertIn("a.com", names)
        self.assertIn("b.com", names)
        # First entry should be the biggest delta
        self.assertEqual(abs(changes[0]["delta"]), 0.5)

    def test_ignores_tiny_swings(self):
        hist = [
            ({}, make_prompt_result("p", 0.5, 0.5, 40.0, competitor_share={"a.com": 0.5})),
            ({}, make_prompt_result("p", 0.5, 0.5, 40.0, competitor_share={"a.com": 0.51})),
        ]
        self.assertEqual(r.competitor_share_changes(hist), [])

    def test_returns_empty_when_only_one_run(self):
        hist = [({}, make_prompt_result("p", 0.5, 0.5, 40.0, competitor_share={"a.com": 0.5}))]
        self.assertEqual(r.competitor_share_changes(hist), [])


# ── SVG Chart ──────────────────────────────────────────────────────────────

class TestSVGChart(unittest.TestCase):

    def test_well_formed(self):
        svg = r.svg_line_chart("test", [("d1", 0.5), ("d2", 0.7)], y_max=1.0, y_label="rate")
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn("<path", svg)
        self.assertIn("rate", svg)
        self.assertIn(">test<", svg)

    def test_empty_input(self):
        svg = r.svg_line_chart("test", [])
        self.assertIn("No data", svg)

    def test_handles_none_gaps(self):
        # Gap in the middle should not crash
        svg = r.svg_line_chart("test", [("d1", 0.5), ("d2", None), ("d3", 0.6)])
        self.assertIn("<svg", svg)
        # Two separate path segments expected
        self.assertEqual(svg.count("<path"), 2)


class TestShortDate(unittest.TestCase):

    def test_extracts_md(self):
        self.assertEqual(r.short_date("2026-05-19T14:30:00Z"), "05-19")

    def test_missing_returns_empty(self):
        self.assertEqual(r.short_date(""), "")
        self.assertEqual(r.short_date(None), "")


# ── End-to-end Markdown rendering ─────────────────────────────────────────

class TestRenderMarkdown(unittest.TestCase):

    def test_empty_evidence_returns_placeholder(self):
        md, charts = r.render_markdown([], {})
        self.assertIn("No evidence files found", md)
        self.assertEqual(charts, {})

    def test_minimal_evidence_produces_report(self):
        ev = make_evidence("2026-05-18T00:00:00Z", [make_prompt_result("p1", 0.6, 0.4, 50.0, avg_position=3.0)])
        by_prompt = r.group_by_prompt([ev])
        md, charts = r.render_markdown([ev], by_prompt)
        self.assertIn("# AEO Visibility Report — Tabiji", md)
        self.assertIn("## Executive Summary", md)
        self.assertIn("## Per-Prompt Detail", md)
        self.assertIn("p1", md)

    def test_multi_run_includes_chart_placeholder(self):
        evs = [
            make_evidence(f"2026-05-{18 + i:02d}T00:00:00Z", [make_prompt_result("p1", 0.5 + i * 0.05, 0.3, 40.0)])
            for i in range(3)
        ]
        by_prompt = r.group_by_prompt(evs)
        md, charts = r.render_markdown(evs, by_prompt)
        self.assertIn("<!-- chart: chart-p1 -->", md)
        self.assertIn("chart-p1", charts)


# ── Markdown → HTML ────────────────────────────────────────────────────────

class TestMarkdownToHtml(unittest.TestCase):

    def test_basic_doc(self):
        md = "# Title\n\nThis is a paragraph.\n\n- item one\n- item two\n"
        out = r.markdown_to_html(md, {})
        self.assertIn("<title>Title</title>", out)
        self.assertIn("<h1>Title</h1>", out)
        self.assertIn("<p>This is a paragraph.</p>", out)
        self.assertIn("<li>item one</li>", out)

    def test_chart_substitution(self):
        md = "Some text.\n\n<!-- chart: foo -->\n\nMore text.\n"
        charts = {"foo": "<svg>fake</svg>"}
        out = r.markdown_to_html(md, charts)
        self.assertIn('<div class="chart"><svg>fake</svg></div>', out)

    def test_escapes_html_in_content(self):
        md = "# Hello <script>alert(1)</script>\n"
        out = r.markdown_to_html(md, {})
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_bold_and_italic(self):
        out = r.markdown_to_html("**bold** and *italic*\n", {})
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn("<em>italic</em>", out)

    def test_hr(self):
        out = r.markdown_to_html("Para\n\n---\n\nMore\n", {})
        self.assertIn("<hr>", out)


# ── End-to-end CLI ────────────────────────────────────────────────────────

class TestCLIEndToEnd(unittest.TestCase):

    def test_writes_both_formats(self):
        with tempfile.TemporaryDirectory() as d:
            data_dir = os.path.join(d, "data")
            output_dir = os.path.join(d, "reports")
            os.makedirs(data_dir)
            ev = make_evidence("2026-05-18T00:00:00Z", [make_prompt_result("p1", 0.6, 0.4, 50.0)])
            with open(os.path.join(data_dir, "run.json"), "w") as f:
                json.dump(ev, f)
            rc = r.main(["--data-dir", data_dir, "--output-dir", output_dir, "--format", "all"])
            self.assertEqual(rc, 0)
            files = os.listdir(output_dir)
            self.assertTrue(any(f.endswith(".md") for f in files))
            self.assertTrue(any(f.endswith(".html") for f in files))

    def test_errors_when_data_dir_missing(self):
        rc = r.main(["--data-dir", "/nonexistent/path"])
        self.assertEqual(rc, 2)

    def test_errors_when_no_evidence_files(self):
        with tempfile.TemporaryDirectory() as d:
            rc = r.main(["--data-dir", d])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
