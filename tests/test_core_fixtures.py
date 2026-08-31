import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parents[1] / "packages" / "core" / "src"
sys.path.insert(0, str(CORE_SRC))

from evalrank_core.fixtures import (  # noqa: E402
    PUBLIC_CATALOG_GENERATED_AT,
    PUBLIC_CATALOG_METHODOLOGY_VERSION,
    PUBLIC_FIXTURE_KINDS,
    sample_capability_fingerprint_input,
    sample_observation,
    sample_problem_details,
    sample_public_fixture,
    sample_raw_entry,
    sample_use_case_catalog,
)


class CoreFixtureTests(unittest.TestCase):
    def test_public_fixture_dispatch_is_the_exact_current_surface(self):
        self.assertEqual(
            ("fingerprint", "observation", "problem", "raw-entry", "use-cases"),
            PUBLIC_FIXTURE_KINDS,
        )
        for kind in PUBLIC_FIXTURE_KINDS:
            self.assertTrue(sample_public_fixture(kind))
        with self.assertRaisesRegex(ValueError, "fixture kind"):
            sample_public_fixture("candidate-set")

    def test_independent_discovery_fixtures_are_content_addressed(self):
        fingerprint = sample_capability_fingerprint_input().to_dict()
        raw = sample_raw_entry().to_dict()
        self.assertRegex(fingerprint["capability_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertRegex(raw["content_hash"], r"^[0-9a-f]{64}$")

    def test_observation_fixture_is_typed_and_artifact_linked(self):
        payload = sample_observation().to_dict()
        self.assertEqual("observation", payload["object"])
        self.assertRegex(payload["evaluated_configuration_id"], r"^config_[0-9a-f]{64}$")
        self.assertEqual("proportion", payload["metric"]["kind"])
        self.assertRegex(
            payload["provenance"]["source_artifacts"][0]["source_artifact_id"],
            r"^artifact_[0-9a-f]{64}$",
        )

    def test_problem_fixture_is_public_rfc9457(self):
        payload = sample_problem_details().to_dict()
        self.assertEqual((422, "validation", False), (
            payload["status"], payload["code"], payload["retriable"]
        ))

    def test_use_case_fixture_matches_the_manifest_release(self):
        payload = sample_use_case_catalog().to_dict()
        self.assertEqual("2026-08-04.1.catalog-manifest-v1", PUBLIC_CATALOG_METHODOLOGY_VERSION)
        self.assertEqual("2026-08-04T00:00:00Z", PUBLIC_CATALOG_GENERATED_AT)
        self.assertEqual(24, len(payload["use_cases"]))
        self.assertEqual("coding-general", payload["use_cases"][0]["id"])


if __name__ == "__main__":
    unittest.main()
