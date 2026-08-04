import json
import re
import subprocess
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "catalog"
SCHEMAS = REPO_ROOT / "schemas"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class CatalogResearchProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(CATALOG / "manifest.json")
        cls.provenance = load_json(CATALOG / "research-provenance.json")
        cls.schema = load_json(
            SCHEMAS / "benchmark-research-provenance.schema.json"
        )

    def test_artifact_is_pinned_to_the_exact_manifest_family_inventory(self):
        expected_ids = [
            row["benchmark_family_id"]
            for row in self.manifest["benchmark_families"]
        ]
        actual_ids = [
            row["benchmark_family_id"]
            for row in self.provenance["families"]
        ]

        self.assertEqual("benchmark_research_provenance", self.provenance["object"])
        self.assertEqual("1", self.provenance["schema_version"])
        self.assertEqual("2026-08-04.1", self.provenance["manifest_version"])
        self.assertEqual(self.manifest["manifest_version"], self.provenance["manifest_version"])
        self.assertEqual(expected_ids, actual_ids)
        self.assertEqual(103, len(actual_ids))
        self.assertEqual(len(actual_ids), len(set(actual_ids)))

    def test_every_family_has_dated_primary_or_official_sources(self):
        allowed_source_kinds = {
            "official_dataset",
            "official_leaderboard",
            "official_repository",
            "official_site",
            "primary_paper",
        }

        for family in self.provenance["families"]:
            with self.subTest(family=family["benchmark_family_id"]):
                self.assertRegex(family["checked_on"], DATE_PATTERN)
                self.assertLessEqual(
                    date.fromisoformat(family["checked_on"]), date.today()
                )
                self.assertGreaterEqual(len(family["sources"]), 1)
                source_ids = [source["source_id"] for source in family["sources"]]
                urls = [source["url"] for source in family["sources"]]
                self.assertEqual(len(source_ids), len(set(source_ids)))
                self.assertEqual(len(urls), len(set(urls)))
                for source in family["sources"]:
                    self.assertIn(source["kind"], allowed_source_kinds)
                    parsed = urlsplit(source["url"])
                    self.assertEqual("https", parsed.scheme)
                    self.assertTrue(parsed.netloc)
                    self.assertIsNone(parsed.username)
                    self.assertIsNone(parsed.password)

    def test_every_manifest_research_flag_has_one_linked_categorized_claim(self):
        manifest_families = {
            row["benchmark_family_id"]: row
            for row in self.manifest["benchmark_families"]
        }

        for family in self.provenance["families"]:
            family_id = family["benchmark_family_id"]
            source_ids = {source["source_id"] for source in family["sources"]}
            flag_claims = [
                claim for claim in family["claims"]
                if claim["research_flag"] is not None
            ]
            actual_flags = [claim["research_flag"] for claim in flag_claims]
            expected_flags = manifest_families[family_id]["research_flags"]

            with self.subTest(family=family_id):
                self.assertEqual(expected_flags, actual_flags)
                self.assertEqual(len(actual_flags), len(set(actual_flags)))
                for claim in family["claims"]:
                    self.assertIn(
                        claim["basis"],
                        {"direct_source", "owner_attestation", "evalrank_inference"},
                    )
                    self.assertTrue(claim["statement"].strip())
                    self.assertGreaterEqual(len(claim["source_ids"]), 1)
                    self.assertEqual(
                        len(claim["source_ids"]), len(set(claim["source_ids"]))
                    )
                    self.assertLessEqual(set(claim["source_ids"]), source_ids)

    def test_new_research_families_record_current_scope_and_version_status(self):
        families = {
            row["benchmark_family_id"]: row
            for row in self.provenance["families"]
        }

        for family_id in (
            "gdpval",
            "mle-bench",
            "paperbench",
            "core-bench-reproducibility",
        ):
            with self.subTest(family=family_id):
                claims = families[family_id]["claims"]
                self.assertTrue(
                    any(
                        claim["research_flag"] is None
                        and claim["topic"] == "scope"
                        for claim in claims
                    )
                )
                self.assertTrue(
                    any(
                        claim["research_flag"] is None
                        and claim["topic"] == "version_status"
                        for claim in claims
                    )
                )

    def test_terminal_bench_records_pinned_current_schema_and_probe_evidence(self):
        family = next(
            row for row in self.provenance["families"]
            if row["benchmark_family_id"] == "terminal-bench-2-1"
        )
        sources = {row["source_id"]: row["url"] for row in family["sources"]}
        statements = "\n".join(claim["statement"] for claim in family["claims"])

        self.assertEqual(
            "https://www.tbench.ai/leaderboard/terminal-bench/2.1",
            sources["leaderboard"],
        )
        self.assertIn("a0c400b1138e8c2272c2fc7daa4fa35199b43bef", sources["schema_migration"])
        self.assertIn("67f1daf5b331fd10f5e8bc05bfc626aac26eeb39", sources["signed_labels_migration"])
        self.assertNotIn("EvalRank retains the repository aggregate artifacts", statements)
        reconciliation = next(
            claim for claim in family["claims"]
            if "exact-byte manual composite probe" in claim["statement"]
        )
        self.assertEqual("evalrank_inference", reconciliation["basis"])
        self.assertEqual("2026-07-23", family["checked_on"])
        for expected in (
            "exact-byte manual composite probe",
            "retention remained disabled",
            "probe evidence rather than replayable retained input",
        ):
            self.assertIn(expected, reconciliation["statement"])
        self.assertEqual(2, len(re.findall(r"\b[0-9a-f]{64}\b", reconciliation["statement"])))
        self.assertEqual(1, len(re.findall(r"\b[0-9a-f]{40}\b", reconciliation["statement"])))

    def test_every_quarantine_reason_has_one_linked_categorized_claim(self):
        manifest_families = {
            row["benchmark_family_id"]: row
            for row in self.manifest["benchmark_families"]
        }

        for family in self.provenance["families"]:
            family_id = family["benchmark_family_id"]
            quarantine_claims = [
                claim
                for claim in family["claims"]
                if claim["topic"] == "quarantine_reason"
            ]
            expected_count = int(
                manifest_families[family_id]["quarantine_reason"] is not None
            )
            with self.subTest(family=family_id):
                self.assertEqual(expected_count, len(quarantine_claims))
                for claim in quarantine_claims:
                    self.assertIsNone(claim["research_flag"])

    def test_every_approved_right_has_one_direct_source_claim(self):
        rights_fields = {
            "harness_code_license",
            "task_data_license",
            "commercial_use",
            "result_redistribution",
            "trajectory_redistribution",
            "environment_terms",
            "artifact_retention",
            "derived_score_publication",
        }
        provenance = {
            family["benchmark_family_id"]: family
            for family in self.provenance["families"]
        }

        for feed in self.manifest["feeds"]:
            if feed["rights"]["status"] != "approved":
                continue
            family = provenance[feed["benchmark_family_id"]]
            for field in rights_fields:
                if feed["rights"][field] in {None, "unknown"}:
                    continue
                claims = [
                    claim for claim in family["claims"]
                    if claim["topic"] == field
                ]
                with self.subTest(feed=feed["feed_id"], field=field):
                    self.assertEqual(1, len(claims))
                    self.assertIn(
                        claims[0]["basis"], {"direct_source", "owner_attestation"}
                    )
                    self.assertIsNone(claims[0]["research_flag"])

    def test_mteb_direct_permission_covers_leaderboard_data_rights(self):
        family_ids = {
            "mteb-beir",
            "mteb-eng-v2",
            "mteb-longembed",
            "mteb-followir",
            "mteb-rar-b",
            "mteb-multilingual-v2",
        }
        provenance = {
            family["benchmark_family_id"]: family
            for family in self.provenance["families"]
            if family["benchmark_family_id"] in family_ids
        }

        for feed in self.manifest["feeds"]:
            if feed["benchmark_family_id"] not in family_ids:
                continue
            with self.subTest(feed=feed["feed_id"]):
                self.assertEqual("approved", feed["rights"]["status"])
                self.assertEqual(
                    "Apache-2.0", feed["rights"]["harness_code_license"]
                )
                self.assertIsNone(feed["rights"]["task_data_license"])
                self.assertEqual("allowed", feed["rights"]["artifact_retention"])
                self.assertFalse(feed["retention"]["store_artifact_bytes"])

        for family_id, family in provenance.items():
            with self.subTest(family=family_id):
                claims = {claim["topic"]: claim for claim in family["claims"]}
                self.assertEqual(
                    ["mteb_license"], claims["harness_code_license"]["source_ids"]
                )
                self.assertIn("Apache-2.0", claims["harness_code_license"]["statement"])
                self.assertIn("direct source-owner permission", claims["task_data_license"]["statement"])

    def test_schema_is_closed_draft_2020_12_and_matches_artifact_shape(self):
        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema", self.schema["$schema"]
        )
        self.assertTrue(
            self.schema["$id"].endswith(
                "benchmark-research-provenance.schema.json"
            )
        )
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(
            set(self.provenance), set(self.schema["properties"])
        )

        family_schema = self.schema["$defs"]["BenchmarkFamilyResearch"]
        source_schema = self.schema["$defs"]["ResearchSource"]
        claim_schema = self.schema["$defs"]["ResearchClaim"]
        self.assertFalse(family_schema["additionalProperties"])
        self.assertFalse(source_schema["additionalProperties"])
        self.assertFalse(claim_schema["additionalProperties"])
        self.assertEqual(
            {"benchmark_family_id", "checked_on", "sources", "claims"},
            set(family_schema["required"]),
        )
        self.assertEqual(
            {"source_id", "kind", "url"}, set(source_schema["required"])
        )
        self.assertEqual(
            {"topic", "research_flag", "basis", "statement", "source_ids"},
            set(claim_schema["required"]),
        )

    def test_artifact_validates_with_ajv_draft_2020_12(self):
        script = """
import { readFileSync } from "node:fs";
import Ajv2020 from "./packages/sdk-ts/node_modules/ajv/dist/2020.js";

const schema = JSON.parse(readFileSync("schemas/benchmark-research-provenance.schema.json", "utf8"));
const artifact = JSON.parse(readFileSync("catalog/research-provenance.json", "utf8"));
const ajv = new Ajv2020({ allErrors: true, allowUnionTypes: true, strict: true });
const validate = ajv.compile(schema);

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function assertValid(value, label) {
  if (!validate(value)) {
    throw new Error(`${label} should be valid:\n${ajv.errorsText(validate.errors, { separator: "\\n" })}`);
  }
}

function assertInvalid(value, label) {
  if (validate(value)) {
    throw new Error(`${label} should be invalid`);
  }
}

assertValid(artifact, "canonical companion");

const extraSourceField = clone(artifact);
extraSourceField.families[0].sources[0].private_note = "closed";
assertInvalid(extraSourceField, "nested unknown source field");

const unversionedManifest = clone(artifact);
unversionedManifest.manifest_version = "latest";
assertInvalid(unversionedManifest, "unversioned manifest reference");

const insecureSource = clone(artifact);
insecureSource.families[0].sources[0].url = "http://example.com/benchmark";
assertInvalid(insecureSource, "non-HTTPS source");

const uncategorizedFlag = clone(artifact);
uncategorizedFlag.families.find((family) => family.claims.length > 0).claims[0].research_flag = "not-a-scope-claim";
assertInvalid(uncategorizedFlag, "research flag on scope claim");
"""
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
