import json
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = REPO_ROOT / "schemas"


def _schema(filename: str) -> dict:
    return json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))


class PublicReadSchemaTests(unittest.TestCase):
    def test_read_documents_are_closed_versioned_draft_2020_12_contracts(self):
        for filename in (
            "benchmark-health.schema.json",
            "entity-detail.schema.json",
            "compare-result.schema.json",
            "leaderboard.schema.json",
        ):
            with self.subTest(filename=filename):
                schema = _schema(filename)
                self.assertEqual(
                    "https://json-schema.org/draft/2020-12/schema",
                    schema["$schema"],
                )
                self.assertEqual(
                    f"https://evalrank.ai/schemas/{filename}", schema["$id"]
                )
                self.assertEqual("object", schema["type"])
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(set(schema["properties"]), set(schema["required"]))
                self.assertEqual("1", schema["properties"]["schema_version"]["const"])

    def test_benchmark_health_is_closed_and_uses_safe_nonnegative_counts(self):
        schema = _schema("benchmark-health.schema.json")
        cell = schema["$defs"]["CellHealth"]

        self.assertEqual("benchmark_health", schema["properties"]["object"]["const"])
        self.assertFalse(cell["additionalProperties"])
        self.assertEqual(set(cell["properties"]), set(cell["required"]))
        self.assertEqual(
            {"active", "preview", "unavailable"},
            set(cell["properties"]["status"]["enum"]),
        )
        self.assertEqual(0, schema["$defs"]["SafeCount"]["minimum"])
        self.assertEqual(9007199254740991, schema["$defs"]["SafeCount"]["maximum"])

    def test_leaderboard_is_a_cell_snapshot_set_of_isolated_ranking_groups(self):
        schema = _schema("leaderboard.schema.json")
        group = schema["$defs"]["RankingGroup"]
        entry = schema["$defs"]["LeaderboardEntry"]

        self.assertEqual("leaderboard", schema["properties"]["object"]["const"])
        self.assertRegex(
            schema["properties"]["snapshot_set_id"]["pattern"],
            "snapshot",
        )
        self.assertEqual("array", schema["properties"]["ranking_groups"]["type"])
        self.assertEqual("#/$defs/RankingGroup", schema["properties"]["ranking_groups"]["items"]["$ref"])
        self.assertTrue(schema["properties"]["ranking_groups"]["uniqueItems"])

        self.assertFalse(group["additionalProperties"])
        self.assertEqual(set(group["properties"]), set(group["required"]))
        self.assertIn("ranking_group_id", group["required"])
        self.assertIn("entity_kind", group["required"])
        self.assertIn("interaction_policy", group["required"])
        self.assertIn("configuration_passport_class", group["required"])
        self.assertIn("state", group["required"])
        self.assertIn("evidence_snapshot_id", group["required"])
        self.assertNotIn("publication_snapshot_id", group["properties"])
        self.assertIn("explorer_views", group["required"])
        self.assertIn("entries", group["required"])
        self.assertIn("citations", group["required"])
        self.assertIn("unresolved", group["properties"]["entity_kind"]["enum"])
        self.assertIn("unresolved", group["properties"]["interaction_policy"]["enum"])
        self.assertIn("unresolved-v1", group["properties"]["configuration_passport_class"]["enum"])
        self.assertEqual(
            "evalrank-manifest.schema.json#/$defs/IdentityTriple",
            group["allOf"][0]["$ref"],
        )

        self.assertFalse(entry["additionalProperties"])
        self.assertNotIn("entity_kind", entry["properties"])
        self.assertNotIn("interaction_policy", entry["properties"])
        self.assertNotIn("configuration_passport_class", entry["properties"])
        ranking = schema["$defs"]["EntityRanking"]
        score = ranking["properties"]["capability_score"]
        self.assertEqual("number", score["type"])
        self.assertEqual(0, score["minimum"])
        self.assertEqual(1, score["maximum"])
        self.assertEqual(9007199254740991, ranking["properties"]["rank"]["maximum"])
        self.assertEqual(9007199254740991, ranking["properties"]["evidence_family_count"]["maximum"])
        eligibility = schema["$defs"]["EligibilitySummary"]
        for field in (
            "rank_eligible_configuration_count",
            "current_independent_family_count",
            "required_independent_family_count",
            "current_overlap_count",
            "required_overlap_count",
        ):
            self.assertEqual(9007199254740991, eligibility["properties"][field]["maximum"])
        descriptor = schema["$defs"]["SnapshotSetDescriptor"]
        self.assertIn("ranking_group_snapshots", descriptor["required"])
        self.assertNotIn("publication_snapshot_ids", descriptor["properties"])
        snapshot_ref = schema["$defs"]["RankingGroupSnapshotRef"]
        self.assertFalse(snapshot_ref["additionalProperties"])
        self.assertEqual(
            {"ranking_group_id", "evidence_snapshot_id"},
            set(snapshot_ref["required"]),
        )
        evidence_snapshot_id = schema["$defs"]["EvidenceSnapshotId"]
        self.assertEqual("^(snapshot|explorer)_[0-9a-f]{64}$", evidence_snapshot_id["pattern"])
        explorer_view = schema["$defs"]["ExplorerEvidenceView"]
        self.assertFalse(explorer_view["additionalProperties"])
        self.assertEqual(set(explorer_view["properties"]), set(explorer_view["required"]))
        self.assertEqual(
            {"single_source", "promising_not_proven", "conflicting"},
            set(explorer_view["properties"]["agreement"]["enum"]),
        )

    def test_entity_detail_uses_the_exact_evaluated_configuration_contract(self):
        schema = _schema("entity-detail.schema.json")

        self.assertEqual("entity_detail", schema["properties"]["object"]["const"])
        projection = schema["$defs"]["EntityProjection"]
        self.assertEqual("#/$defs/EntityProjection", schema["properties"]["entity"]["$ref"])
        self.assertTrue(
            {
                "entity_kind",
                "interaction_policy",
                "configuration_passport_class",
            }.isdisjoint(schema["properties"])
        )
        self.assertEqual(
            "evaluated-configuration.schema.json",
            projection["properties"]["evaluated_configuration"]["$ref"],
        )
        self.assertEqual(
            "leaderboard.schema.json#/$defs/EntityRanking",
            projection["properties"]["ranking"]["$ref"],
        )
        self.assertEqual(
            "leaderboard.schema.json#/$defs/Citation",
            projection["properties"]["citations"]["items"]["$ref"],
        )

    def test_compare_contains_two_to_four_unique_entity_details(self):
        schema = _schema("compare-result.schema.json")
        entities = schema["properties"]["entities"]

        self.assertEqual("compare_result", schema["properties"]["object"]["const"])
        self.assertEqual(2, entities["minItems"])
        self.assertEqual(4, entities["maxItems"])
        self.assertTrue(entities["uniqueItems"])
        self.assertEqual("#/$defs/ComparedEntity", entities["items"]["$ref"])
        projection = schema["$defs"]["ComparedEntity"]
        self.assertEqual(
            {
                "evaluated_configuration_id",
                "ranking",
                "citations",
            },
            set(projection["properties"]),
        )
        self.assertTrue(
            {
                "ranking_group_id",
                "entity_kind",
                "interaction_policy",
                "configuration_passport_class",
                "evidence_snapshot_id",
            }.isdisjoint(projection["properties"])
        )

    def test_read_schemas_compile_and_reject_cross_group_and_null_score_mutations(self):
        script = r'''
import { readFileSync, readdirSync } from "node:fs";
import Ajv2020 from "./packages/sdk-ts/node_modules/ajv/dist/2020.js";

const ajv = new Ajv2020({ allErrors: true, allowUnionTypes: true, strict: true });
for (const filename of readdirSync("schemas").filter((name) => name.endsWith(".schema.json"))) {
  ajv.addSchema(JSON.parse(readFileSync(`schemas/${filename}`, "utf8")));
}

const validateLeaderboard = ajv.getSchema("https://evalrank.ai/schemas/leaderboard.schema.json");
const validateEntity = ajv.getSchema("https://evalrank.ai/schemas/entity-detail.schema.json");
const validateCompare = ajv.getSchema("https://evalrank.ai/schemas/compare-result.schema.json");
if (!validateLeaderboard || !validateEntity || !validateCompare) {
  throw new Error("public read schemas were not registered");
}

const artifact = (hex) => `artifact_${hex.repeat(64)}`;
const config = (hex) => `config_${hex.repeat(64)}`;
const snapshot = (hex) => `snapshot_${hex.repeat(64)}`;
const explorer = (hex) => `explorer_${hex.repeat(64)}`;
const snapshotDescriptor = {
  object: "snapshot_set_descriptor",
  schema_version: "1",
  cell_id: "code-generation",
  manifest_version: "2026-07-09.2",
  methodology_version: "2026-07-10.1.truth-kernel-v1",
  ranking_group_snapshots: [{
    ranking_group_id: "rg-code-generation-model-configuration-direct-prompt-model-configuration-v1",
    evidence_snapshot_id: snapshot("b")
  }]
};
const activeEligibility = {
  published_claim: "top_set",
  rank_eligible_configuration_count: 2,
  current_independent_family_count: 3,
  required_independent_family_count: 3,
  current_overlap_count: 2,
  required_overlap_count: 2,
  calibration_status: "validated",
  gap_codes: []
};
const payload = {
  object: "leaderboard",
  schema_version: "1",
  cell_id: "code-generation",
  cell_state: "active",
  manifest_version: "2026-07-09.2",
  methodology_version: "2026-07-10.1.truth-kernel-v1",
  snapshot_set_id: `snapshot_set_${"a".repeat(64)}`,
  snapshot_set_descriptor: snapshotDescriptor,
  generated_at: "2026-07-10T00:00:00Z",
  ranking_groups: [{
    ranking_group_id: "rg-code-generation-model-configuration-direct-prompt-model-configuration-v1",
    entity_kind: "model_configuration",
    interaction_policy: "direct_prompt",
    configuration_passport_class: "model-configuration-v1",
    state: "active",
    evidence_snapshot_id: snapshot("b"),
    eligibility_summary: activeEligibility,
    entries: [{
      evaluated_configuration_id: config("c"),
      ranking: {
        rank: 1,
        display_name: "Example model configuration",
        capability_score: 0.82,
        uncertainty: { kind: "interval", level: 0.95, lower: 0.78, upper: 0.86 },
        in_top_set: true,
        evidence_family_count: 3,
        caveat_codes: []
      }
    }],
    citations: [{
      source_artifact_id: artifact("d"),
      benchmark_family_id: "livebench-reasoning",
      title: "LiveBench",
      url: "https://example.com/livebench"
    }],
    explorer_views: []
  }]
};

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function assertValid(validate, value, label) {
  if (!validate(value)) throw new Error(`${label} should be valid:\n${ajv.errorsText(validate.errors)}`);
}
function assertInvalid(validate, value, label) {
  if (validate(value)) throw new Error(`${label} should be invalid`);
}

assertValid(validateLeaderboard, payload, "canonical grouped leaderboard");

const unresolvedExplorer = clone(payload);
unresolvedExplorer.cell_state = "preview";
unresolvedExplorer.cell_id = "deep-research";
unresolvedExplorer.snapshot_set_descriptor = {
  ...snapshotDescriptor,
  cell_id: "deep-research",
  ranking_group_snapshots: [{
    ranking_group_id: "rg-deep-research-unresolved-unresolved-unresolved-v1",
    evidence_snapshot_id: explorer("e")
  }]
};
unresolvedExplorer.ranking_groups = [{
  ranking_group_id: "rg-deep-research-unresolved-unresolved-unresolved-v1",
  entity_kind: "unresolved",
  interaction_policy: "unresolved",
  configuration_passport_class: "unresolved-v1",
  state: "preview",
  evidence_snapshot_id: explorer("e"),
  eligibility_summary: {
    published_claim: "explorer",
    rank_eligible_configuration_count: 0,
    current_independent_family_count: 0,
    required_independent_family_count: 1,
    current_overlap_count: 0,
    required_overlap_count: 1,
    calibration_status: "unvalidated",
    gap_codes: ["no_rank_eligible_configurations", "unresolved_identity"]
  },
  entries: [],
  citations: [],
  explorer_views: [{
    benchmark_family_id: "deepswe",
    feed_id: "deepswe-discovery",
    metric_direction: "higher",
    observed_at: "2026-07-10T03:00:00Z",
    expires_at: "2026-07-17T03:00:00Z",
    agreement: "single_source",
    entries: [],
    citations: []
  }]
}];
assertValid(validateLeaderboard, unresolvedExplorer, "canonical unresolved explorer group");

const openExplorerView = clone(unresolvedExplorer);
openExplorerView.ranking_groups[0].explorer_views[0].note = "not public";
assertInvalid(validateLeaderboard, openExplorerView, "open explorer view");

const previewWithoutExplorerView = clone(unresolvedExplorer);
previewWithoutExplorerView.ranking_groups[0].explorer_views = [];
assertInvalid(validateLeaderboard, previewWithoutExplorerView, "preview without exact explorer evidence");

// v2: publication state is decoupled from claim strength. An ACTIVE read carrying
// an explorer claim (explorer evidence, disclosed gaps, a view, no in_top_set) is
// valid — state no longer forces the top_set tier.
const activeExplorer = clone(unresolvedExplorer);
activeExplorer.cell_state = "active";
activeExplorer.ranking_groups[0].state = "active";
assertValid(validateLeaderboard, activeExplorer, "active explorer group decoupled from state");

// An explorer claim must still carry explorer_ evidence; snapshot_ evidence under an
// explorer claim is a claim/evidence inconsistency.
const explorerClaimSnapshotEvidence = clone(unresolvedExplorer);
explorerClaimSnapshotEvidence.snapshot_set_descriptor.ranking_group_snapshots[0].evidence_snapshot_id = snapshot("f");
explorerClaimSnapshotEvidence.ranking_groups[0].evidence_snapshot_id = snapshot("f");
assertInvalid(validateLeaderboard, explorerClaimSnapshotEvidence, "explorer claim with snapshot evidence");

const explorerTopSetClaim = clone(unresolvedExplorer);
explorerTopSetClaim.ranking_groups[0].explorer_views[0].entries = clone(payload.ranking_groups[0].entries);
assertInvalid(validateLeaderboard, explorerTopSetClaim, "explorer view claiming top-set membership");

const unresolvedWithEntry = clone(unresolvedExplorer);
unresolvedWithEntry.ranking_groups[0].entries = clone(payload.ranking_groups[0].entries);
assertInvalid(validateLeaderboard, unresolvedWithEntry, "unresolved group with entries");

const activeWithoutTopSet = clone(payload);
activeWithoutTopSet.ranking_groups[0].entries[0].ranking.in_top_set = false;
assertInvalid(validateLeaderboard, activeWithoutTopSet, "active group without top-set member");

const previewWithRankedEntry = clone(unresolvedExplorer);
previewWithRankedEntry.ranking_groups[0].entries = clone(payload.ranking_groups[0].entries);
previewWithRankedEntry.ranking_groups[0].entries[0].ranking.in_top_set = false;
assertInvalid(validateLeaderboard, previewWithRankedEntry, "preview group with ranked entry");

const activeWithExplorerView = clone(payload);
activeWithExplorerView.ranking_groups[0].explorer_views = clone(unresolvedExplorer.ranking_groups[0].explorer_views);
assertInvalid(validateLeaderboard, activeWithExplorerView, "active group with explorer view");

const activeWithExplorerIdentity = clone(payload);
activeWithExplorerIdentity.snapshot_set_descriptor.ranking_group_snapshots[0].evidence_snapshot_id = explorer("a");
activeWithExplorerIdentity.ranking_groups[0].evidence_snapshot_id = explorer("a");
assertInvalid(validateLeaderboard, activeWithExplorerIdentity, "active group with explorer identity");

for (const state of ["preview", "shadow"]) {
  const snapshotWithExplorerView = clone(unresolvedExplorer);
  snapshotWithExplorerView.ranking_groups[0].state = state;
  snapshotWithExplorerView.snapshot_set_descriptor.ranking_group_snapshots[0].evidence_snapshot_id = snapshot("f");
  snapshotWithExplorerView.ranking_groups[0].evidence_snapshot_id = snapshot("f");
  assertInvalid(validateLeaderboard, snapshotWithExplorerView, `${state} snapshot with explorer view`);
}

const legacySnapshotField = clone(payload);
legacySnapshotField.ranking_groups[0].publication_snapshot_id = legacySnapshotField.ranking_groups[0].evidence_snapshot_id;
delete legacySnapshotField.ranking_groups[0].evidence_snapshot_id;
assertInvalid(validateLeaderboard, legacySnapshotField, "legacy publication snapshot field");

const nullScore = clone(payload);
nullScore.ranking_groups[0].entries[0].ranking.capability_score = null;
assertInvalid(validateLeaderboard, nullScore, "null capability score");

const mixedIdentity = clone(payload);
mixedIdentity.ranking_groups[0].entity_kind = "agent_system";
assertInvalid(validateLeaderboard, mixedIdentity, "mixed identity triple");

const entryIdentity = clone(payload);
entryIdentity.ranking_groups[0].entries[0].entity_kind = "agent_system";
assertInvalid(validateLeaderboard, entryIdentity, "entry-level identity override");

const unknownGroupField = clone(payload);
unknownGroupField.ranking_groups[0].scale = "other";
assertInvalid(validateLeaderboard, unknownGroupField, "unknown group field");

const ranking = clone(payload.ranking_groups[0].entries[0].ranking);
const citations = clone(payload.ranking_groups[0].citations);
const evaluatedConfiguration = {
  object: "evaluated_configuration",
  schema_version: "1",
  evaluated_configuration_id: config("c"),
  passport: {
    object: "configuration_passport",
    schema_version: "1",
    entity_kind: "model_configuration",
    canonical_name: "example-model",
    revision: "2026-07-10",
    interaction_policy: "direct_prompt",
    configuration_passport_class: "model-configuration-v1",
    harness: null,
    scaffold: null,
    tools: [],
    quantization: null,
    system_prompt_policy: null,
    environment: null
  }
};
const entity = {
  object: "entity_detail",
  schema_version: "1",
  cell_id: payload.cell_id,
  manifest_version: payload.manifest_version,
  methodology_version: payload.methodology_version,
  snapshot_set_id: payload.snapshot_set_id,
  snapshot_set_descriptor: payload.snapshot_set_descriptor,
  ranking_group_id: payload.ranking_groups[0].ranking_group_id,
  state: "active",
  evidence_snapshot_id: payload.ranking_groups[0].evidence_snapshot_id,
  explorer_view: null,
  eligibility_summary: activeEligibility,
  generated_at: payload.generated_at,
  entity: { evaluated_configuration: evaluatedConfiguration, ranking, citations }
};
assertValid(validateEntity, entity, "exact entity detail");

const previewEntity = clone(entity);
previewEntity.state = "preview";
previewEntity.evidence_snapshot_id = explorer("f");
previewEntity.explorer_view = { benchmark_family_id: "family-a", feed_id: "family-a-feed" };
previewEntity.eligibility_summary = {
  ...activeEligibility,
  published_claim: "explorer",
  calibration_status: "unvalidated",
  gap_codes: ["calibration_unvalidated"]
};
assertInvalid(validateEntity, previewEntity, "preview entity claiming top-set membership");
previewEntity.entity.ranking.in_top_set = false;
assertValid(validateEntity, previewEntity, "preview entity without top-set claim");

// v2: an ACTIVE entity carrying an explorer claim validates — state is decoupled.
const activeExplorerEntity = clone(previewEntity);
activeExplorerEntity.state = "active";
assertValid(validateEntity, activeExplorerEntity, "active explorer entity decoupled from state");

const duplicateEntityIdentity = clone(entity);
duplicateEntityIdentity.entity_kind = "agent_system";
assertInvalid(validateEntity, duplicateEntityIdentity, "duplicate envelope identity");

const comparedEntity = {
  evaluated_configuration_id: config("c"),
  ranking,
  citations
};
const secondComparedEntity = clone(comparedEntity);
secondComparedEntity.evaluated_configuration_id = config("e");
secondComparedEntity.ranking.display_name = "Second model configuration";
secondComparedEntity.ranking.rank = 2;
const compare = {
  object: "compare_result",
  schema_version: "1",
  cell_id: payload.cell_id,
  manifest_version: payload.manifest_version,
  methodology_version: payload.methodology_version,
  snapshot_set_id: payload.snapshot_set_id,
  snapshot_set_descriptor: payload.snapshot_set_descriptor,
  ranking_group_id: payload.ranking_groups[0].ranking_group_id,
  entity_kind: "model_configuration",
  interaction_policy: "direct_prompt",
  configuration_passport_class: "model-configuration-v1",
  state: "active",
  evidence_snapshot_id: payload.ranking_groups[0].evidence_snapshot_id,
  explorer_view: null,
  eligibility_summary: activeEligibility,
  generated_at: payload.generated_at,
  entities: [comparedEntity, secondComparedEntity]
};
assertValid(validateCompare, compare, "same-group comparison");

const previewCompare = clone(compare);
previewCompare.state = "preview";
previewCompare.evidence_snapshot_id = explorer("f");
previewCompare.explorer_view = { benchmark_family_id: "family-a", feed_id: "family-a-feed" };
previewCompare.eligibility_summary = {
  ...activeEligibility,
  published_claim: "explorer",
  calibration_status: "unvalidated",
  gap_codes: ["calibration_unvalidated"]
};
assertInvalid(validateCompare, previewCompare, "preview compare claiming top-set membership");
previewCompare.entities.forEach((item) => { item.ranking.in_top_set = false; });
assertValid(validateCompare, previewCompare, "preview compare without top-set claim");

// v2: an ACTIVE compare carrying an explorer claim validates — state is decoupled.
const activeExplorerCompare = clone(previewCompare);
activeExplorerCompare.state = "active";
assertValid(validateCompare, activeExplorerCompare, "active explorer compare decoupled from state");

const duplicateCompare = clone(compare);
duplicateCompare.entities[1] = clone(duplicateCompare.entities[0]);
assertInvalid(validateCompare, duplicateCompare, "duplicate compared entity");

const mixedCompare = clone(compare);
mixedCompare.entities[0].ranking_group_id = "rg-other";
assertInvalid(validateCompare, mixedCompare, "per-entity group override");
'''
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
