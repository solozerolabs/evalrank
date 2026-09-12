import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "catalog"
SCHEMAS = REPO_ROOT / "schemas"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import export_catalog_feeds as exporter  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest(families, feeds, version="2026-07-21.1") -> dict:
    return {
        "manifest_version": version,
        "benchmark_families": families,
        "feeds": feeds,
    }


def _family(family_id, **extra) -> dict:
    return {"benchmark_family_id": family_id, **extra}


def _feed(feed_id, family_id, **extra) -> dict:
    return {"feed_id": feed_id, "benchmark_family_id": family_id, **extra}


def _research(family_id, **extra) -> dict:
    return {"benchmark_family_id": family_id, **extra}


class FeedInventoryBuilderTests(unittest.TestCase):
    def test_joins_every_feed_in_manifest_order_to_exact_objects(self):
        fam_a, fam_b = _family("a"), _family("b")
        feed_1, feed_2 = _feed("f1", "b"), _feed("f2", "a")
        res_a, res_b = _research("a"), _research("b")

        inventory = exporter.build_inventory(
            _manifest([fam_a, fam_b], [feed_1, feed_2]),
            {"manifest_version": "2026-07-21.1", "families": [res_a, res_b]},
        )

        self.assertEqual(["f1", "f2"], [e["feed"]["feed_id"] for e in inventory["feeds"]])
        # exact (identity) nesting of the manifest and research objects
        self.assertIs(feed_1, inventory["feeds"][0]["feed"])
        self.assertIs(fam_b, inventory["feeds"][0]["benchmark_family"])
        self.assertIs(res_b, inventory["feeds"][0]["research"])
        self.assertIs(fam_a, inventory["feeds"][1]["benchmark_family"])
        self.assertIs(res_a, inventory["feeds"][1]["research"])
        self.assertEqual("2026-07-21.1", inventory["manifest_version"])
        self.assertEqual("evalrank_feed_inventory", inventory["object"])

    def test_missing_research_for_a_feed_family_raises(self):
        manifest = _manifest([_family("a")], [_feed("f1", "a")])
        with self.assertRaisesRegex(ValueError, "no research"):
            exporter.build_inventory(manifest, {"manifest_version": "2026-07-21.1", "families": []})

    def test_duplicate_research_family_raises(self):
        manifest = _manifest([_family("a")], [_feed("f1", "a")])
        provenance = {"manifest_version": "2026-07-21.1", "families": [_research("a"), _research("a")]}
        with self.assertRaisesRegex(ValueError, "duplicate research"):
            exporter.build_inventory(manifest, provenance)

    def test_manifest_and_research_versions_must_match(self):
        manifest = _manifest([_family("a")], [_feed("f1", "a")])
        provenance = {"manifest_version": "2026-07-10.5", "families": [_research("a")]}
        with self.assertRaisesRegex(ValueError, "versions must match"):
            exporter.build_inventory(manifest, provenance)

    def test_duplicate_benchmark_family_raises(self):
        manifest = _manifest([_family("a"), _family("a")], [_feed("f1", "a")])
        with self.assertRaisesRegex(ValueError, "duplicate benchmark family"):
            exporter.build_inventory(manifest, {"manifest_version": "2026-07-21.1", "families": [_research("a")]})

    def test_feed_referencing_unknown_family_raises(self):
        manifest = _manifest([_family("a")], [_feed("f1", "ghost")])
        with self.assertRaisesRegex(ValueError, "unknown family"):
            exporter.build_inventory(manifest, {"manifest_version": "2026-07-21.1", "families": [_research("a")]})

    def test_faithfully_nests_flags_quarantines_arrays_dup_kinds_and_equals_urls(self):
        family = _family(
            "a",
            candidate_cells=["one", "two"],
            research_flags=["provisional"],
            state="quarantined",
            quarantine_reason="blocked pending repair",
        )
        feed = _feed(
            "f1",
            "a",
            state="quarantined",
            quarantine_reason="blocked pending repair",
            candidate_cells=["one", "two"],
        )
        research = _research(
            "a",
            sources=[
                {"source_id": "a", "kind": "official_repository", "url": "https://x.test/r"},
                {"source_id": "b", "kind": "official_repository", "url": "https://y.test/q?a=1&b=2"},
            ],
            claims=[
                {"topic": "research_flag", "research_flag": "provisional", "basis": "direct_source"},
            ],
        )

        inventory = exporter.build_inventory(
            _manifest([family], [feed]), {"manifest_version": "2026-07-21.1", "families": [research]}
        )
        entry = inventory["feeds"][0]

        self.assertEqual(family, entry["benchmark_family"])
        self.assertEqual(feed, entry["feed"])
        self.assertEqual(research, entry["research"])
        # duplicate source kinds and nested arrays survive verbatim
        self.assertEqual(
            ["official_repository", "official_repository"],
            [s["kind"] for s in entry["research"]["sources"]],
        )
        # a URL containing '=' round-trips through the rendered line unescaped
        rendered = exporter.render(inventory)
        self.assertIn("https://y.test/q?a=1&b=2", rendered)
        self.assertEqual(inventory, json.loads(rendered))


class FeedInventoryRenderTests(unittest.TestCase):
    def test_each_feed_entry_is_exactly_one_compact_physical_line(self):
        inventory = exporter.build_inventory(
            _manifest([_family("a"), _family("b")], [_feed("f1", "a"), _feed("f2", "b")]),
            {"manifest_version": "2026-07-21.1", "families": [_research("a"), _research("b")]},
        )
        lines = exporter.render(inventory).splitlines()
        start = lines.index('  "feeds": [')
        end = lines.index("  ]", start)
        entry_lines = lines[start + 1 : end]

        self.assertEqual(2, len(entry_lines))
        for line in entry_lines:
            stripped = line.strip().rstrip(",")
            self.assertNotIn(" ", stripped)  # compact: no separator whitespace
            self.assertTrue(json.loads(stripped))


class FeedInventoryArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(CATALOG / "manifest.json")
        cls.provenance = load_json(CATALOG / "research-provenance.json")
        cls.feeds = load_json(CATALOG / "feeds.json")
        cls.schema = load_json(SCHEMAS / "feed-inventory.schema.json")

    def test_exact_row_count_order_and_object_equality(self):
        manifest_feeds = self.manifest["feeds"]
        families = {f["benchmark_family_id"]: f for f in self.manifest["benchmark_families"]}
        research = {f["benchmark_family_id"]: f for f in self.provenance["families"]}

        self.assertEqual(len(manifest_feeds), len(self.feeds["feeds"]))
        self.assertEqual(
            [f["feed_id"] for f in manifest_feeds],
            [e["feed"]["feed_id"] for e in self.feeds["feeds"]],
        )
        for feed, entry in zip(manifest_feeds, self.feeds["feeds"]):
            family_id = feed["benchmark_family_id"]
            self.assertEqual(feed, entry["feed"])
            self.assertEqual(families[family_id], entry["benchmark_family"])
            self.assertEqual(research[family_id], entry["research"])
            self.assertEqual(
                {family_id},
                {
                    entry["benchmark_family"]["benchmark_family_id"],
                    entry["feed"]["benchmark_family_id"],
                    entry["research"]["benchmark_family_id"],
                },
            )

    def test_envelope_is_version_locked_to_the_manifest(self):
        self.assertEqual("../schemas/feed-inventory.schema.json", self.feeds["$schema"])
        self.assertEqual("evalrank_feed_inventory", self.feeds["object"])
        self.assertEqual("1", self.feeds["schema_version"])
        self.assertEqual(self.manifest["manifest_version"], self.feeds["manifest_version"])
        self.assertEqual("2026-08-27.1", self.feeds["manifest_version"])

    def test_committed_file_is_one_compact_line_per_feed(self):
        lines = (CATALOG / "feeds.json").read_text(encoding="utf-8").splitlines()
        start = lines.index('  "feeds": [')
        end = lines.index("  ]", start)
        entry_lines = lines[start + 1 : end]
        self.assertEqual(len(self.feeds["feeds"]), len(entry_lines))
        for line, entry in zip(entry_lines, self.feeds["feeds"]):
            self.assertEqual(entry, json.loads(line.strip().rstrip(",")))

    def test_schema_is_closed_and_refs_the_manifest_and_research_defs(self):
        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema", self.schema["$schema"]
        )
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(set(self.feeds), set(self.schema["properties"]))
        entry = self.schema["$defs"]["FeedInventoryEntry"]
        self.assertFalse(entry["additionalProperties"])
        self.assertEqual(
            {"benchmark_family", "feed", "research"}, set(entry["required"])
        )
        props = entry["properties"]
        self.assertEqual(
            "https://evalrank.ai/schemas/evalrank-manifest.schema.json#/$defs/BenchmarkFamily",
            props["benchmark_family"]["$ref"],
        )
        self.assertEqual(
            "https://evalrank.ai/schemas/evalrank-manifest.schema.json#/$defs/Feed",
            props["feed"]["$ref"],
        )
        self.assertEqual(
            "https://evalrank.ai/schemas/benchmark-research-provenance.schema.json#/$defs/BenchmarkFamilyResearch",
            props["research"]["$ref"],
        )


class FeedInventoryCheckModeTests(unittest.TestCase):
    def setUp(self):
        self._original = exporter.FEEDS_PATH
        self._tmp = Path(tempfile.mkdtemp()) / "feeds.json"
        exporter.FEEDS_PATH = self._tmp

    def tearDown(self):
        exporter.FEEDS_PATH = self._original

    def test_check_passes_on_freshly_written_bytes_and_write_is_idempotent(self):
        self.assertEqual(0, exporter.main(["--write"]))
        self.assertEqual(0, exporter.main(["--check"]))
        # committed file matches a fresh export
        committed = self._original.read_text(encoding="utf-8")
        self.assertEqual(committed, self._tmp.read_text(encoding="utf-8"))

    def test_check_fails_when_missing(self):
        self.assertFalse(self._tmp.exists())
        self.assertEqual(1, exporter.main(["--check"]))

    def test_check_fails_when_stale_or_hand_edited(self):
        exporter.main(["--write"])
        text = self._tmp.read_text(encoding="utf-8")
        self._tmp.write_text(text.replace("evalrank_feed_inventory", "hand_edited", 1), encoding="utf-8")
        self.assertEqual(1, exporter.main(["--check"]))


class FeedInventorySchemaClosureAjvTests(unittest.TestCase):
    def test_artifact_validates_and_rejects_unknown_fields(self):
        script = """
import { readFileSync } from "node:fs";
import Ajv2020 from "./packages/sdk-ts/node_modules/ajv/dist/2020.js";

const manifestSchema = JSON.parse(readFileSync("schemas/evalrank-manifest.schema.json", "utf8"));
const researchSchema = JSON.parse(readFileSync("schemas/benchmark-research-provenance.schema.json", "utf8"));
const schema = JSON.parse(readFileSync("schemas/feed-inventory.schema.json", "utf8"));
const artifact = JSON.parse(readFileSync("catalog/feeds.json", "utf8"));

const ajv = new Ajv2020({ allErrors: true, allowUnionTypes: true, strict: true });
ajv.addSchema(manifestSchema);
ajv.addSchema(researchSchema);
const validate = ajv.compile(schema);

const clone = (v) => JSON.parse(JSON.stringify(v));
function assertValid(value, label) {
  if (!validate(value)) {
    throw new Error(`${label} should be valid:\\n${ajv.errorsText(validate.errors, { separator: "\\n" })}`);
  }
}
function assertInvalid(value, label) {
  if (validate(value)) {
    throw new Error(`${label} should be invalid`);
  }
}

assertValid(artifact, "canonical feed inventory");

const extraTop = clone(artifact);
extraTop.private_note = "closed";
assertInvalid(extraTop, "unknown top-level field");

const extraEntry = clone(artifact);
extraEntry.feeds[0].private_note = "closed";
assertInvalid(extraEntry, "unknown entry field");

const extraFeed = clone(artifact);
extraFeed.feeds[0].feed.private_note = "closed";
assertInvalid(extraFeed, "unknown nested feed field");
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
