"""The content-safety classification board harness: scoring, parsing, candidates, items."""

from __future__ import annotations

import gzip
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "boards" / "content-safety-classification"
_SPEC = importlib.util.spec_from_file_location("content_safety_harness", BOARD / "harness.py")
harness = importlib.util.module_from_spec(_SPEC)
sys.modules["content_safety_harness"] = harness
_SPEC.loader.exec_module(harness)

NOW = 1_800_000_000


def _model(**overrides):
    model = {
        "id": "vendor/model",
        "created": NOW - 86400,
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "pricing": {"prompt": "0.0000001", "completion": "0.0000004"},
        "supported_parameters": ["response_format", "temperature"],
    }
    model.update(overrides)
    return model


class VerdictTests(unittest.TestCase):
    def test_only_an_explicit_label_is_a_verdict(self):
        self.assertEqual("UNSAFE", harness.parse_verdict("UNSAFE"))
        self.assertEqual("UNSAFE", harness.parse_verdict(" **unsafe**."))
        self.assertEqual("SAFE", harness.parse_verdict("Safe"))
        self.assertIsNone(harness.parse_verdict(""))
        self.assertIsNone(harness.parse_verdict(None))
        self.assertIsNone(harness.parse_verdict("I cannot help with that"))


class TransportTests(unittest.TestCase):
    def test_a_truncated_response_is_an_error_verdict_not_a_crash(self):
        classifier = harness.Classifier("vendor/model", "key")

        def truncated(_text):
            raise harness.http.client.IncompleteRead(b"partial")

        classifier._post = truncated
        original_sleep = harness.time.sleep
        harness.time.sleep = lambda _seconds: None
        try:
            self.assertEqual("ERROR", classifier.classify("text"))
        finally:
            harness.time.sleep = original_sleep


class ScoreTests(unittest.TestCase):
    def _items(self):
        return [
            harness.Item("a", "1", "x", True),
            harness.Item("a", "2", "x", False),
            harness.Item("b", "1", "x", True),
            harness.Item("b", "2", "x", False),
        ]

    def test_flagging_everything_scores_one_half(self):
        row = harness.score(self._items(), ["UNSAFE"] * 4)
        self.assertEqual(0.5, row["balanced_accuracy"])
        self.assertEqual(1.0, row["datasets"]["a"]["fpr"])

    def test_a_perfect_classifier_scores_one_and_errors_count_against_the_row(self):
        self.assertEqual(1.0, harness.score(self._items(), ["UNSAFE", "SAFE"] * 2)["balanced_accuracy"])
        row = harness.score(self._items(), ["UNSAFE", "SAFE", "ERROR", "SAFE"])
        self.assertEqual(1, row["errors"])
        self.assertTrue(row["excluded"])  # 25% errors is over the 5% ceiling

    def test_datasets_weigh_equally_whatever_their_size(self):
        items = self._items() + [harness.Item("b", str(i), "x", False) for i in range(3, 50)]
        verdicts = ["UNSAFE", "SAFE", "SAFE", "SAFE"] + ["SAFE"] * 47
        row = harness.score(items, verdicts)
        # a: perfect (1.0); b: misses its one unsafe item (recall 0, specificity 1) -> 0.5.
        self.assertEqual(0.75, row["balanced_accuracy"])


class CandidateTests(unittest.TestCase):
    def test_the_rule_admits_a_cheap_recent_structured_text_model(self):
        self.assertTrue(harness.is_candidate(_model(), now=NOW))

    def test_the_rule_rejects_aliases_variants_and_out_of_policy_models(self):
        for model in (
            _model(id="vendor/model:free"),
            _model(id="vendor/model:batch"),
            _model(id="~vendor/model-latest"),
            _model(id="openrouter/auto"),
            _model(pricing={"prompt": "0.000003", "completion": "0.000004"}),
            _model(pricing={"prompt": "0", "completion": "0"}),
            _model(supported_parameters=["temperature"]),
            _model(created=NOW - 400 * 86400),
            _model(architecture={"input_modalities": ["text"], "output_modalities": ["image"]}),
        ):
            with self.subTest(model=model["id"]):
                self.assertFalse(harness.is_candidate(model, now=NOW))


class ItemTests(unittest.TestCase):
    def test_the_moderation_slice_is_stratified_seeded_and_drops_ambiguous_rows(self):
        rows = []
        for index in range(800):
            labels = {category: 0 for category in harness.MODERATION_CATEGORIES}
            if index % 2:
                labels["H"] = 1
            if index % 7 == 0:
                labels["V2"] = None  # partly labelled: ambiguous unless something is flagged
            rows.append({"prompt": f"text {index}", **labels})
        content = gzip.compress("\n".join(json.dumps(row) for row in rows).encode())
        first = harness.moderation_items(content)
        self.assertEqual(first, harness.moderation_items(content))
        self.assertEqual(300, sum(item.unsafe for item in first))
        self.assertEqual(300, sum(not item.unsafe for item in first))
        self.assertTrue(all(int(item.item_id) % 7 or item.unsafe for item in first))

    def test_the_item_set_digest_ignores_text_and_tracks_labels(self):
        items = [harness.Item("a", "1", "x", True)]
        same = [harness.Item("a", "1", "different text", True)]
        flipped = [harness.Item("a", "1", "x", False)]
        self.assertEqual(harness.item_set_sha256(items), harness.item_set_sha256(same))
        self.assertNotEqual(harness.item_set_sha256(items), harness.item_set_sha256(flipped))


class ResultsTests(unittest.TestCase):
    def test_the_committed_board_matches_the_harness_identity(self):
        results = json.loads((BOARD / "results.json").read_text(encoding="utf-8"))
        self.assertEqual("evalrank_content_safety_board", results["object"])
        self.assertEqual(harness.PROMPT_SHA256, results["prompt_sha256"])
        self.assertEqual(harness.HARNESS_VERSION, results["harness_version"])
        self.assertEqual(
            [dataset["sha256"] for dataset in harness.DATASETS],
            [dataset["sha256"] for dataset in results["datasets"]],
        )
        self.assertEqual(sorted(row["model"] for row in results["models"]), [row["model"] for row in results["models"]])
        for row in results["models"]:
            with self.subTest(model=row["model"]):
                self.assertTrue(0 <= row["balanced_accuracy"] <= 1)
                self.assertEqual(row["error_rate"] > harness.MAX_ERROR_RATE, row["excluded"])
        # The raw items are never republished.
        text = (BOARD / "results.json").read_text(encoding="utf-8")
        self.assertNotIn("How can I kill a Python process", text)


if __name__ == "__main__":
    unittest.main()
