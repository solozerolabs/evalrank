"""The web-search board harness: request shaping, result parsing, scoring, billing, refresh rule, results."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "boards" / "web-search"
_SPEC = importlib.util.spec_from_file_location("web_search_harness", BOARD / "harness.py")
harness = importlib.util.module_from_spec(_SPEC)
sys.modules["web_search_harness"] = harness
_SPEC.loader.exec_module(harness)


class RequestTests(unittest.TestCase):
    def test_the_query_goes_in_the_required_string_and_a_count_asks_for_five(self):
        schema = {"body": {"required": ["keyword"], "properties": {"keyword": {"type": "string"}, "limit": {"type": "integer"}}}}
        self.assertEqual({"kind": "body", "input": {"keyword": "{query}", "limit": 5}}, harness.build_request(schema))

    def test_a_required_string_list_takes_the_query_as_its_one_item(self):
        schema = {"body": {"required": ["search_queries"], "properties": {"search_queries": {"type": "array", "items": {"type": "string"}}}}}
        self.assertEqual({"search_queries": ["{query}"]}, harness.build_request(schema)["input"])

    def test_with_nothing_required_a_query_named_field_takes_it(self):
        schema = {"queryParams": {"properties": {"q": {"type": "string"}, "num": {"type": "integer", "minimum": 1}}}}
        self.assertEqual({"kind": "queryParams", "input": {"q": "{query}", "num": 5}}, harness.build_request(schema))

    def test_a_required_input_the_board_cannot_fill_is_not_a_candidate(self):
        schema = {"body": {"required": ["query", "region"], "properties": {"query": {"type": "string"}, "region": {"enum": ["us", "eu"]}}}}
        self.assertIsNone(harness.build_request(schema))
        self.assertIsNone(harness.build_request({"body": {"properties": {"url": {"type": "string"}}}}))

    def test_fill_puts_the_query_everywhere_the_placeholder_is(self):
        request = {"kind": "body", "input": {"search_queries": ["{query}"], "limit": 5}}
        self.assertEqual({"search_queries": ['say "hi"'], "limit": 5}, harness.fill(request, 'say "hi"'))


class ParseAndScoreTests(unittest.TestCase):
    def test_the_organic_list_wins_over_videos_and_related_lists(self):
        serp = {
            "inline_videos": [{"link": "https://youtube.com/v"}],
            "related_searches": [{"link": "https://google.com/s"}],
            "organic_results": [{"link": "https://acme.com/docs"}, {"link": "https://x.dev"}],
        }
        self.assertEqual(["https://acme.com/docs", "https://x.dev"], harness.result_urls(serp))

    def test_an_unnamed_nested_list_is_found(self):
        self.assertEqual(["https://a.io"], harness.result_urls({"payload": {"hits2": [{"url": "https://a.io"}]}}))
        self.assertEqual([], harness.result_urls({"answer": "no list"}))

    def test_official_hosts_take_subdomains_and_path_prefixes_only(self):
        self.assertTrue(harness.official("https://docs.acme.com/mcp", ["acme.com"]))
        self.assertFalse(harness.official("https://notacme.com/", ["acme.com"]))
        self.assertTrue(harness.official("https://github.com/acme/agent-toolkit", ["github.com/acme"]))
        self.assertFalse(harness.official("https://github.com/acme-samples/x", ["github.com/acme"]))

    def test_reciprocal_rank_counts_the_first_official_result_in_the_top_five(self):
        urls = ["https://blog.example/a", "https://acme.com/x", "https://acme.com/y"]
        self.assertEqual(0.5, harness.reciprocal_rank(urls, ["acme.com"]))
        self.assertEqual(0.0, harness.reciprocal_rank(["https://a.io"] * 5 + ["https://acme.com"], ["acme.com"]))

    def test_billing_reads_the_sync_and_the_polled_shape(self):
        self.assertEqual(0.015, harness.billed_usd({"billing": {"reportedCost": {"value": 15000, "unit": "MICRO_DOLLAR"}}}))
        self.assertEqual(0.0009, harness.billed_usd({"cost": {"value": 0.0009, "currency": "USD"}}))
        self.assertIsNone(harness.billed_usd({}))
        self.assertEqual(0.0, harness.billed_usd({"cost": {"value": 0}}))

    def test_a_row_scores_answered_queries_and_excludes_on_too_many_errors(self):
        candidate = {"model": "v/search", "provider": "v", "endpoint": "/search", "request": {}, "list_usd": 0.001}
        rows = [{"id": "a", "error": False, "rr": 1.0, "usd": 0.002, "seconds": 1.0},
                {"id": "b", "error": False, "rr": 0.5, "usd": 0.002, "seconds": 3.0},
                {"id": "c", "error": True, "code": "http_502"}]
        row = harness.summarize(candidate, rows)
        self.assertEqual((0.75, 0.5, 1, False, 0.002, 2.0), (row["score"], row["hit_at_1"], row["errors"], row["excluded"], row["usd_per_call"], row["seconds_p50"]))
        self.assertNotIn("usd", row["query_results"][0])
        unbilled = harness.summarize(candidate, [rows[0], {**rows[1], "usd": None}])
        self.assertIsNone(unbilled["usd_per_call"])
        bad = harness.summarize(candidate, [{"id": str(i), "error": True, "code": "x"} for i in range(4)])
        self.assertTrue(bad["excluded"])


class RefreshTests(unittest.TestCase):
    def test_new_endpoints_then_retries_then_the_stalest_old_row(self):
        now = datetime(2026, 12, 30, tzinfo=UTC)
        found = [{"model": m} for m in ("new", "old", "fresh", "retry", "dead")]
        results = {"models": [
            {"model": "old", "excluded": False, "scored_at": "2026-11-01T00:00:00Z"},
            {"model": "fresh", "excluded": False, "scored_at": "2026-12-29T00:00:00Z"},
            {"model": "retry", "excluded": True, "attempts": 1, "scored_at": "2026-12-29T00:00:00Z"},
            {"model": "dead", "excluded": True, "attempts": 3, "scored_at": "2026-12-29T00:00:00Z"},
        ]}
        self.assertEqual(["new", "retry", "old"], [c["model"] for c in harness.pick(results, found, now=now, max_models=0)])
        self.assertEqual(["new"], [c["model"] for c in harness.pick(results, found, now=now, max_models=1)])


class PublishedBoardTests(unittest.TestCase):
    def test_the_committed_board_matches_the_harness_identity(self):
        results = json.loads((BOARD / "results.json").read_text(encoding="utf-8"))
        fresh = harness.empty_results()
        for key in (*harness.IDENTITY, "object", "schema_version", "metric", "metric_direction", "datasets"):
            self.assertEqual(fresh[key], results[key], key)
        self.assertEqual(hashlib.sha256((BOARD / "items.json").read_bytes()).hexdigest(), results["datasets"][0]["sha256"])

    def test_every_row_agrees_with_its_queries(self):
        results = json.loads((BOARD / "results.json").read_text(encoding="utf-8"))
        names = [row["model"] for row in results["models"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(names), 3)
        for row in results["models"]:
            answered = [q for q in row["query_results"] if not q["error"]]
            self.assertEqual(row["queries"], len(row["query_results"]))
            self.assertEqual(row["errors"], row["queries"] - len(answered))
            self.assertIs(row["excluded"], row["errors"] > harness.MAX_ERRORS)
            if answered:
                self.assertAlmostEqual(row["score"], sum(q["rr"] for q in answered) / len(answered), places=3)
            self.assertTrue(0 <= row["score"] <= 1)
            self.assertIn(harness.QUERY, json.dumps(row["request"]))
            self.assertFalse(any("results_text" in q for q in row["query_results"]))


if __name__ == "__main__":
    unittest.main()
