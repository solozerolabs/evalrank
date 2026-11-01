from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "packages" / "core" / "src"
GOLDEN = REPO_ROOT / "examples" / "decision-contract-v2.golden.json"
AGGREGATION_GOLDEN = REPO_ROOT / "catalog" / "aggregation-vectors.json"
sys.path.insert(0, str(CORE_SRC))

from evalrank_core import (  # noqa: E402
    aggregation_input_document,
    bootstrap_seed_document,
    derive_aggregation_input_digest,
    derive_bootstrap_seed,
)
from evalrank_core.canonical_json import (  # noqa: E402
    MAX_SAFE_INTEGER,
    canonical_json,
    restricted_jcs,
    sha256_hex,
)


class CanonicalJsonTests(unittest.TestCase):
    def test_serializes_restricted_jcs_without_whitespace(self):
        value = {
            "z": [True, None, "line\nfeed"],
            "a": {"quote": '"', "slash": "/"},
        }

        self.assertEqual(
            '{"a":{"quote":"\\\"","slash":"/"},"z":[true,null,"line\\nfeed"]}',
            canonical_json(value),
        )
        self.assertEqual(canonical_json(value).encode("utf-8"), restricted_jcs(value))

    def test_orders_object_keys_by_utf16_code_units(self):
        # U+10000 sorts before U+E000 under RFC 8785's UTF-16 ordering.
        value = {"\ue000": 2, "\U00010000": 1}

        self.assertEqual('{"\U00010000":1,"\ue000":2}', canonical_json(value))

    def test_preserves_unicode_without_normalizing(self):
        decomposed = "e\u0301"
        composed = "\u00e9"

        self.assertNotEqual(canonical_json({"value": decomposed}), canonical_json({"value": composed}))
        self.assertIn(decomposed, canonical_json({"value": decomposed}))

    def test_rejects_values_outside_the_restricted_subset(self):
        invalid_values = (
            1.0,
            float("nan"),
            float("inf"),
            MAX_SAFE_INTEGER + 1,
            -(MAX_SAFE_INTEGER + 1),
            {1: "non-string-key"},
            {"value": "\ud800"},
            {"\udfff": "lone-surrogate-key"},
        )

        for value in invalid_values:
            with self.subTest(value=repr(value)):
                with self.assertRaises((TypeError, ValueError)):
                    canonical_json(value)

    def test_rejects_non_json_python_values(self):
        for value in ({1, 2}, (1, 2), b"bytes"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypeError):
                    canonical_json(value)

    def test_sha256_hex_hashes_exact_canonical_bytes(self):
        self.assertEqual(
            "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777",
            sha256_hex({"b": 2, "a": 1}),
        )

    def test_python_matches_cross_language_golden_canonicalization(self):
        corpus = json.loads(GOLDEN.read_text(encoding="utf-8"))

        self.assertEqual(corpus["query"]["canonical"], canonical_json(corpus["query"]["input"]))
        self.assertEqual(corpus["receipts"][0]["body_sha256"], sha256_hex(corpus["receipts"][0]["body"]))

        for vector in corpus["rejection_vectors"][:2]:
            with self.subTest(vector=vector["name"]):
                with self.assertRaises((TypeError, ValueError)):
                    canonical_json(vector["value"])


class AggregationIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vector = json.loads(AGGREGATION_GOLDEN.read_text(encoding="utf-8"))["vectors"][0]

    def test_python_matches_portable_aggregation_golden(self):
        expected = self.vector
        source = expected["aggregation_document"]

        document = aggregation_input_document(**source)
        self.assertEqual(expected["aggregation_document"], document)
        self.assertEqual(expected["aggregation_canonical"], canonical_json(document))
        self.assertEqual(
            expected["aggregation_input_digest"],
            derive_aggregation_input_digest(**source),
        )

        seed_document = bootstrap_seed_document(
            expected["aggregation_input_digest"],
            source["methodology_version"],
        )
        self.assertEqual(expected["seed_document"], seed_document)
        self.assertEqual(expected["seed_canonical"], canonical_json(seed_document))
        self.assertEqual(expected["seed_digest"], sha256_hex(seed_document))
        self.assertEqual(
            expected["seed_first_eight_bytes_hex"],
            expected["seed_digest"][:16],
        )
        self.assertGreater(int(expected["seed_first_eight_bytes_hex"], 16), MAX_SAFE_INTEGER)
        self.assertEqual(
            expected["bootstrap_seed"],
            derive_bootstrap_seed(
                expected["aggregation_input_digest"],
                source["methodology_version"],
            ),
        )
        self.assertLessEqual(expected["bootstrap_seed"], MAX_SAFE_INTEGER)

    def test_aggregation_identity_preserves_ranking_group_slot_order(self):
        source = self.vector["aggregation_document"]
        reordered = {
            **source,
            "ranking_group": [
                source["ranking_group"][1],
                source["ranking_group"][0],
                *source["ranking_group"][2:],
            ],
        }

        self.assertEqual(reordered["ranking_group"], aggregation_input_document(**reordered)["ranking_group"])
        self.assertNotEqual(
            derive_aggregation_input_digest(**source),
            derive_aggregation_input_digest(**reordered),
        )

    def test_aggregation_identity_canonicalizes_observation_set_order(self):
        source = self.vector["aggregation_document"]
        reordered = {**source, "observation_ids": list(reversed(source["observation_ids"]))}

        self.assertEqual(
            source["observation_ids"],
            aggregation_input_document(**reordered)["observation_ids"],
        )
        self.assertEqual(
            derive_aggregation_input_digest(**source),
            derive_aggregation_input_digest(**reordered),
        )

    def test_aggregation_identity_rejects_invalid_observation_arrays(self):
        source = self.vector["aggregation_document"]
        observation_ids = source["observation_ids"]
        invalid_values = (
            (),
            [],
            [observation_ids[0], observation_ids[0]],
            ["observation_" + "0" * 64],
            ["obs_" + "A" * 64],
            ["obs_" + "0" * 63],
            [1],
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    aggregation_input_document(**{**source, "observation_ids": value})

    def test_aggregation_identity_rejects_invalid_document_fields(self):
        source = self.vector["aggregation_document"]
        invalid_overrides = (
            {"admission_cohort_digest": 1},
            {"admission_cohort_digest": "A" * 64},
            {"admission_cohort_digest": "0" * 63},
            {"calibration_report_id": None},
            {"calibration_report_id": "report_" + "0" * 64},
            {"calibration_report_id": "calibration_" + "0" * 63},
            {"methodology_version": 1},
            {"methodology_version": ""},
            {"methodology_version": "\ud800"},
            {"ranking_group": tuple(source["ranking_group"])},
            {"ranking_group": source["ranking_group"][:3]},
            {"ranking_group": [*source["ranking_group"], "extra"]},
            {"ranking_group": ["", *source["ranking_group"][1:]]},
            {"ranking_group": [1, *source["ranking_group"][1:]]},
            {"ranking_group": ["\ud800", *source["ranking_group"][1:]]},
        )

        for override in invalid_overrides:
            with self.subTest(override=repr(override)):
                with self.assertRaises((TypeError, ValueError)):
                    aggregation_input_document(**{**source, **override})

        with self.assertRaises(TypeError):
            aggregation_input_document(**{**source, "unknown": True})
        without_methodology = {**source}
        del without_methodology["methodology_version"]
        with self.assertRaises(TypeError):
            aggregation_input_document(**without_methodology)

    def test_bootstrap_seed_rejects_invalid_inputs(self):
        digest = self.vector["aggregation_input_digest"]
        invalid_inputs = (
            (None, "aggregation-v1"),
            ("A" * 64, "aggregation-v1"),
            (digest[:-1], "aggregation-v1"),
            (digest, 1),
            (digest, ""),
            (digest, "\ud800"),
        )

        for aggregation_input_digest, methodology_version in invalid_inputs:
            with self.subTest(
                aggregation_input_digest=aggregation_input_digest,
                methodology_version=repr(methodology_version),
            ):
                with self.assertRaises((TypeError, ValueError)):
                    derive_bootstrap_seed(aggregation_input_digest, methodology_version)


if __name__ == "__main__":
    unittest.main()
