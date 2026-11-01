import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import Ajv2020 from "ajv/dist/2020.js";
import * as contracts from "./decision-contracts.ts";
import {
  aggregationInputDocument,
  bootstrapSeedDocument,
  deriveAggregationInputDigest,
  deriveBootstrapSeed,
} from "./index.ts";

import {
  canonicalJson,
  evaluatedConfigurationId,
  DEFAULT_AGENT_TASK_MIX,
  parseServingOfferV1,
  parseConfigurationPassportV1,
  parseDecisionQueryV2,
  parseDecisionReceiptV2,
  resolvedVia,
  SUPPORTED_VIA,
  parseObservationV1,
  parseRunProvenanceV1,
  parseSnapshotSetDescriptorV1,
  receiptId,
  RESOLVED_IDENTITY_TRIPLES,
  sha256Hex,
  snapshotSetId,
  sourceArtifactId,
  verifyCompareResultSemantics,
  verifyEntityDetailSemantics,
  verifyLeaderboardSemantics,
  verifyLeaderboardSnapshotSet,
} from "./decision-contracts.ts";


const golden = JSON.parse(
  readFileSync(new URL("../../../examples/decision-contract-v2.golden.json", import.meta.url), "utf8"),
) as {
  utf16_set_order: { input: string[]; canonical: string[] };
  query: { input: Record<string, unknown>; canonical: string };
  receipts: Array<{ name: string; body: Record<string, unknown>; body_sha256: string; receipt_id: string }>;
  problems: Array<{ name: string; query: Record<string, unknown>; problem: Record<string, unknown> }>;
  rejection_vectors: Array<{ name: string; value: unknown }>;
};
const aggregationGolden = JSON.parse(
  readFileSync(new URL("../../../catalog/aggregation-vectors.json", import.meta.url), "utf8"),
) as {
  vectors: Array<{
    aggregation_document: Record<string, unknown>;
    aggregation_canonical: string;
    aggregation_input_digest: string;
    seed_document: Record<string, unknown>;
    seed_canonical: string;
    seed_digest: string;
    seed_first_eight_bytes_hex: string;
    bootstrap_seed: number;
  }>;
};
const manifest = JSON.parse(
  readFileSync(new URL("../../../catalog/manifest.json", import.meta.url), "utf8"),
) as {
  cells: Array<{ cell_id: string }>;
  ranking_groups: Array<{ ranking_group_id: string; entity_kind: string; interaction_policy: string; configuration_passport_class: string }>;
  benchmark_families: Array<{ benchmark_family_id: string }>;
  feeds: Array<{ feed_id: string; benchmark_family_id: string }>;
};

test("restricted JCS matches the cross-language golden bytes", async () => {
  assert.equal(canonicalJson(golden.query.input), golden.query.canonical);
  for (const row of golden.receipts) {
    assert.equal(await sha256Hex(row.body), row.body_sha256, row.name);
    assert.equal(await receiptId(row.body), row.receipt_id, row.name);
  }
  for (const vector of golden.rejection_vectors.slice(0, 2)) {
    assert.throws(() => canonicalJson(vector.value), /float|safe integer/);
  }
  const nullFilter = golden.rejection_vectors.find((row) => row.name === "null_provider_filter")!;
  assert.throws(() => parseDecisionQueryV2(nullFilter.value), /must not be null/);
});

test("restricted JCS orders by UTF-16 and rejects unsafe hash material", () => {
  assert.equal(canonicalJson({ "\ue000": 2, "\u{10000}": 1 }), '{"\u{10000}":1,"\ue000":2}');
  for (const value of [1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => canonicalJson(value), /float|safe integer|finite/);
  }
  assert.throws(() => canonicalJson({ value: "\ud800" }), /surrogate/);
  assert.throws(() => canonicalJson(Array(1)), /sparse array hole/);
  assert.deepEqual(
    parseDecisionQueryV2({ ...golden.query.input, provider_ids: golden.utf16_set_order.input }).provider_ids,
    golden.utf16_set_order.canonical,
  );
});

test("aggregation identity matches the shared Python golden", async () => {
  const vector = aggregationGolden.vectors[0]!;
  const source = vector.aggregation_document;
  const document = aggregationInputDocument(source);

  assert.deepEqual(document, vector.aggregation_document);
  assert.equal(canonicalJson(document), vector.aggregation_canonical);
  assert.equal(await deriveAggregationInputDigest(source), vector.aggregation_input_digest);

  const seedDocument = bootstrapSeedDocument(
    vector.aggregation_input_digest,
    source.methodology_version,
  );
  assert.deepEqual(seedDocument, vector.seed_document);
  assert.equal(canonicalJson(seedDocument), vector.seed_canonical);
  assert.equal(await sha256Hex(seedDocument), vector.seed_digest);
  assert.equal(vector.seed_digest.slice(0, 16), vector.seed_first_eight_bytes_hex);
  assert.ok(BigInt(`0x${vector.seed_first_eight_bytes_hex}`) > BigInt(Number.MAX_SAFE_INTEGER));
  assert.equal(
    await deriveBootstrapSeed(vector.aggregation_input_digest, source.methodology_version),
    vector.bootstrap_seed,
  );
  assert.ok(vector.bootstrap_seed <= Number.MAX_SAFE_INTEGER);
});

test("aggregation identity preserves ranking-group slot order", async () => {
  const source = aggregationGolden.vectors[0]!.aggregation_document;
  const rankingGroup = source.ranking_group as unknown[];
  const reordered = {
    ...source,
    ranking_group: [rankingGroup[1], rankingGroup[0], ...rankingGroup.slice(2)],
  };

  assert.deepEqual(aggregationInputDocument(reordered).ranking_group, reordered.ranking_group);
  assert.notEqual(
    await deriveAggregationInputDigest(source),
    await deriveAggregationInputDigest(reordered),
  );
});

test("aggregation identity canonicalizes observation-set order", async () => {
  const source = aggregationGolden.vectors[0]!.aggregation_document;
  const reordered = {
    ...source,
    observation_ids: [...(source.observation_ids as string[])].reverse(),
  };

  assert.deepEqual(
    aggregationInputDocument(reordered).observation_ids,
    source.observation_ids,
  );
  assert.equal(
    await deriveAggregationInputDigest(reordered),
    await deriveAggregationInputDigest(source),
  );
});

test("aggregation identity rejects invalid observation arrays", () => {
  const source = aggregationGolden.vectors[0]!.aggregation_document;
  const observationIds = source.observation_ids as string[];
  const sparseObservations = Array(1);
  const invalidValues: unknown[] = [
    null,
    [],
    sparseObservations,
    [observationIds[0], observationIds[0]],
    [`observation_${"0".repeat(64)}`],
    [`obs_${"A".repeat(64)}`],
    [`obs_${"0".repeat(63)}`],
    [1],
  ];

  for (const observation_ids of invalidValues) {
    assert.throws(
      () => aggregationInputDocument({ ...source, observation_ids }),
      /observation_ids/,
    );
  }
});

test("aggregation identity rejects invalid or open documents", () => {
  const source = aggregationGolden.vectors[0]!.aggregation_document;
  const rankingGroup = source.ranking_group as unknown[];
  const sparseRankingGroup = Array(4);
  const { methodology_version: _methodologyVersion, ...missingMethodology } = source;
  const invalidDocuments: unknown[] = [
    null,
    { ...source, unknown: true },
    missingMethodology,
    { ...source, admission_cohort_digest: 1 },
    { ...source, admission_cohort_digest: "A".repeat(64) },
    { ...source, admission_cohort_digest: "0".repeat(63) },
    { ...source, calibration_report_id: null },
    { ...source, calibration_report_id: `report_${"0".repeat(64)}` },
    { ...source, calibration_report_id: `calibration_${"0".repeat(63)}` },
    { ...source, methodology_version: 1 },
    { ...source, methodology_version: "" },
    { ...source, methodology_version: "\ud800" },
    { ...source, ranking_group: rankingGroup.slice(0, 3) },
    { ...source, ranking_group: sparseRankingGroup },
    { ...source, ranking_group: [...rankingGroup, "extra"] },
    { ...source, ranking_group: ["", ...rankingGroup.slice(1)] },
    { ...source, ranking_group: [1, ...rankingGroup.slice(1)] },
    { ...source, ranking_group: ["\ud800", ...rankingGroup.slice(1)] },
  ];

  for (const document of invalidDocuments) {
    assert.throws(() => aggregationInputDocument(document));
  }
});

test("bootstrap seed rejects invalid inputs", async () => {
  const vector = aggregationGolden.vectors[0]!;
  const invalidInputs: Array<[unknown, unknown]> = [
    [null, "aggregation-v1"],
    ["A".repeat(64), "aggregation-v1"],
    [vector.aggregation_input_digest.slice(0, -1), "aggregation-v1"],
    [vector.aggregation_input_digest, 1],
    [vector.aggregation_input_digest, ""],
    [vector.aggregation_input_digest, "\ud800"],
  ];

  for (const [aggregationInputDigest, methodologyVersion] of invalidInputs) {
    await assert.rejects(
      () => deriveBootstrapSeed(aggregationInputDigest, methodologyVersion),
    );
  }
});

test("content-addressed artifact and evaluated configuration identities match Python", async () => {
  const artifactHash = "a".repeat(64);
  assert.equal(sourceArtifactId(artifactHash), `artifact_${artifactHash}`);

  const rawPassport = {
    object: "configuration_passport",
    schema_version: "1",
    entity_kind: "model_configuration",
    canonical_name: "public-demo-model",
    revision: "2026-07-01",
    interaction_policy: "direct_prompt",
    configuration_passport_class: "model-configuration-v1",
    harness: null,
    scaffold: null,
    tools: ["web", "code"],
    quantization: null,
    system_prompt_policy: "benchmark-default",
    environment: "public-sandbox-v1",
  };
  const passport = parseConfigurationPassportV1(rawPassport);
  assert.equal(await evaluatedConfigurationId(passport), `config_${await sha256Hex(passport)}`);
  assert.equal(await evaluatedConfigurationId(rawPassport), await evaluatedConfigurationId(passport));
});

test("agent passports require the exact identity triple, harness, and scaffold", () => {
  const agent = {
    object: "configuration_passport",
    schema_version: "1",
    entity_kind: "agent_system",
    canonical_name: "public-agent",
    revision: "1",
    interaction_policy: "agentic",
    configuration_passport_class: "agent-system-v1",
    harness: "harness-v1",
    scaffold: "scaffold-v1",
    tools: ["shell", "browser"],
    quantization: null,
    system_prompt_policy: null,
    environment: "sandbox-v1",
  };
  assert.deepEqual(parseConfigurationPassportV1(agent).tools, ["browser", "shell"]);
  assert.throws(() => parseConfigurationPassportV1({ ...agent, harness: null }), /harness/);
  assert.throws(
    () => parseConfigurationPassportV1({ ...agent, interaction_policy: "direct_prompt" }),
    /identity triple/,
  );
});

test("identity triples and example identifiers resolve from the canonical manifest", () => {
  const manifestTriples = [...new Set(
    manifest.ranking_groups
      .filter((row) => row.entity_kind !== "unresolved")
      .map((row) => [row.entity_kind, row.interaction_policy, row.configuration_passport_class].join("|")),
  )].sort();
  assert.deepEqual(RESOLVED_IDENTITY_TRIPLES.map((row) => row.join("|")).sort(), manifestTriples);
  assert.ok(manifest.cells.some((row) => row.cell_id === golden.query.input.cell_id));
  for (const row of golden.receipts) {
    const body = row.body as { query: { cell_id: string }; families: Array<{ family_id: string }> };
    assert.ok(manifest.cells.some((cell) => cell.cell_id === body.query.cell_id), row.name);
    for (const family of body.families) {
      assert.ok(manifest.benchmark_families.some((item) => item.benchmark_family_id === family.family_id), family.family_id);
    }
  }
  assert.ok(manifest.benchmark_families.some((row) => row.benchmark_family_id === "livecodebench"));
  assert.ok(manifest.feeds.some((row) => row.feed_id === "livecodebench-discovery" && row.benchmark_family_id === "livecodebench"));
});

test("query decoding canonicalizes unordered sets and rejects v1 fields, transport metadata and null filters", () => {
  const input = {
    ...golden.query.input,
    provider_ids: ["provider-b", "provider-a"],
    regions: ["us-west", "eu-west"],
  };
  const parsed = parseDecisionQueryV2(input);
  assert.deepEqual(parsed.provider_ids, ["provider-a", "provider-b"]);
  assert.deepEqual(parsed.regions, ["eu-west", "us-west"]);
  assert.throws(() => parseDecisionQueryV2({ ...input, request_id: "transport" }), /unknown fields/);
  assert.throws(() => parseDecisionQueryV2({ ...input, provider_ids: null }), /must not be null/);
  assert.throws(() => parseDecisionQueryV2({ ...input, provider_ids: ["a", "a"] }), /unique/);
  for (const field of ["ranking_group_id", "entity_kind", "monthly_budget_microusd", "zero_cache_sensitivity_usage_profile"]) {
    assert.throws(() => parseDecisionQueryV2({ ...input, [field]: "x" }), /unknown fields/, field);
  }
  assert.throws(() => parseDecisionQueryV2({ ...input, schema_version: "1" }), /schema_version must be 2/);
  assert.throws(() => parseDecisionQueryV2({ ...input, reasoning_effort: "ultra" }), /reasoning_effort/);
  const minimal = parseDecisionQueryV2({ schema_version: "2", cell_id: "writing", objective: "lowest_cost_within_top_set" });
  assert.deepEqual(minimal, { object: "decision_query", schema_version: "2", cell_id: "writing", objective: "lowest_cost_within_top_set" });
  assert.equal(resolvedVia(minimal), "openrouter");
  assert.equal(resolvedVia({ ...minimal, provider_ids: ["openai"] }), "openai");
  assert.equal(resolvedVia({ ...minimal, via: "anthropic" }), "anthropic");
  for (const row of golden.rejection_vectors.slice(2)) {
    assert.throws(() => parseDecisionQueryV2(row.value), undefined, row.name);
  }
});

test("typed provenance and observations fail closed", () => {
  const provenance = {
    object: "run_provenance",
    schema_version: "1",
    run_id: "run-public-01",
    benchmark_family_id: "livecodebench",
    feed_id: "livecodebench-discovery",
    source_artifacts: [
      { role: "categories", source_artifact_id: `artifact_${"b".repeat(64)}` },
      { role: "primary", source_artifact_id: `artifact_${"a".repeat(64)}` },
    ],
    parser_id: "json-parser",
    parser_version: "1",
    started_at: "2026-07-09T00:00:00Z",
    completed_at: "2026-07-09T00:01:00Z",
    harness_version: null,
    environment_digest: null,
    scorer_version: null,
    trial_policy: null,
    adapter_metadata: null,
  };
  const parsedProvenance = parseRunProvenanceV1(provenance);
  assert.equal(parsedProvenance.feed_id, "livecodebench-discovery");
  assert.throws(
    () => (parsedProvenance.source_artifacts as unknown as Array<unknown>).reverse(),
    TypeError,
  );
  assert.throws(
    () => Object.assign(parsedProvenance.source_artifacts[0], { role: "changed" }),
    TypeError,
  );
  assert.throws(
    () => parseRunProvenanceV1({ ...provenance, source_artifacts: [...provenance.source_artifacts].reverse() }),
    /sorted by role/,
  );
  assert.throws(
    () => parseRunProvenanceV1({
      ...provenance,
      source_artifacts: provenance.source_artifacts.map((item) => ({ ...item, source_artifact_id: `artifact_${"a".repeat(64)}` })),
    }),
    /unique/,
  );
  assert.throws(() => parseRunProvenanceV1({ ...provenance, source: "mutable-latest" }), /unknown fields/);
  assert.throws(
    () => parseRunProvenanceV1({ ...provenance, started_at: "0000-01-01T00:00:00Z" }),
    /valid UTC timestamp/,
  );

  const observation = {
    object: "observation",
    schema_version: "1",
    observation_id: "obs_public_01",
    evaluated_configuration_id: `config_${"b".repeat(64)}`,
    metric: { kind: "proportion", value: "0.75", numerator: 3, denominator: 4 },
    uncertainty: { kind: "unknown" },
    provenance,
  };
  assert.equal(parseObservationV1(observation).metric.kind, "proportion");
  assert.throws(
    () => parseObservationV1({ ...observation, metric: { kind: "proportion", value: 0.75, numerator: 3, denominator: 4 } }),
    /value/,
  );
  assert.equal(
    parseObservationV1({ ...observation, metric: { kind: "proportion", value: "0.333333", numerator: 1, denominator: 3 } }).metric.kind,
    "proportion",
  );
  assert.throws(
    () => parseObservationV1({ ...observation, metric: { kind: "proportion", value: "0.5", numerator: 1, denominator: 3 } }),
    /six fractional digits|rounded half-even/,
  );
  assert.throws(
    () => parseObservationV1({ ...observation, metric: { kind: "proportion", value: "0", numerator: 1, denominator: 2 } }),
    /six fractional digits/,
  );
});

test("schedule pricing uses BigInt, one final ceiling, and fails closed", () => {
  assert.equal("projectedCostMicrousd" in contracts, true);
  assert.equal("monthlyCostMicrousd" in contracts, false);
  assert.equal("parseEvaluationToOfferLinkV1" in contracts, false);
  const usage = {
    basis: "measured" as const,
    uncached_input_tokens: 1,
    cached_read_tokens: 1,
    output_tokens: 1,
    cache_writes: [{ ttl_seconds: 300, tokens: 1 }],
    cache_storage_token_seconds: 1,
  };
  const pricing = {
    uncached_input_microusd_per_million_tokens: 1,
    cached_read_microusd_per_million_tokens: 1,
    output_microusd_per_million_tokens: 1,
    cache_write_rates: [{ ttl_seconds: 300, microusd_per_million_tokens: 1 }],
    cache_storage_microusd_per_million_token_hours: 1,
    observed_at: "2026-07-09T00:00:00Z",
    effective_at: "2026-07-09T01:00:00Z",
    expires_at: "2026-07-10T00:00:00Z",
    source_artifact_id: `artifact_${"a".repeat(64)}`,
  };

  assert.equal(contracts.projectedCostMicrousd(usage, pricing), 1);
  assert.equal(
    contracts.projectedCostMicrousd(
      { ...usage, uncached_input_tokens: 0, cached_read_tokens: 1, output_tokens: 0, cache_writes: [], cache_storage_token_seconds: 0 },
      { ...pricing, cached_read_microusd_per_million_tokens: null },
    ),
    null,
  );
  assert.throws(
    () => contracts.parseUsageProfileV1({
      basis: "measured",
      uncached_input_tokens: 0,
      cached_read_tokens: 0,
      output_tokens: 0,
      cache_writes: [],
      cache_storage_token_seconds: 0,
    }),
    /non-zero workload/,
  );
  assert.throws(
    () => contracts.parseUsageProfileV1({
      basis: "measured",
      uncached_input_tokens: 0,
      cached_read_tokens: 0,
      output_tokens: 0,
      cache_writes: [],
      cache_storage_token_seconds: 1,
    }),
    /non-zero workload/,
  );
});

function goldenWire(name: string): Record<string, unknown> {
  const row = golden.receipts.find((item) => item.name === name)!;
  return structuredClone({ ...row.body, receipt_id: row.receipt_id });
}

async function rehashed(wire: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { receipt_id: _ignored, ...body } = wire;
  return { ...body, receipt_id: await receiptId(body) };
}

test("every golden receipt parses to its exact body and Python receipt id", async () => {
  for (const row of golden.receipts) {
    const parsed = await parseDecisionReceiptV2({ ...row.body, receipt_id: row.receipt_id });
    const { receipt_id: identifier, ...body } = parsed;
    assert.equal(identifier, row.receipt_id, row.name);
    assert.equal(canonicalJson(body), canonicalJson(row.body), row.name);
    assert.equal(await sha256Hex(row.body), row.body_sha256, row.name);
  }
  assert.deepEqual(golden.receipts.map((row) => row.name), [
    "value_pick", "top_set_pick", "pinned_level", "substituted_effort",
    "abstain_no_ranked_candidate", "abstain_no_eligible_offer", "abstain_stale_evidence", "abstain_not_a_model_cell",
  ]);
});

test("receipt parsing verifies the full-body hash and keeps selection order", async () => {
  const wire = goldenWire("value_pick");
  await assert.rejects(() => parseDecisionReceiptV2({ ...wire, decided_at: "2026-11-01T09:00:01Z" }), /receipt_id/);
  const unsorted = structuredClone(wire);
  (unsorted.exclusions as unknown[]).reverse();
  (unsorted.snapshot_ids as unknown[]).reverse();
  assert.equal((await parseDecisionReceiptV2(unsorted)).receipt_id, wire.receipt_id);
  const reordered = structuredClone(wire);
  (reordered.selections as unknown[]).reverse();
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(reordered)), /cheapest/);
});

test("receipt semantics match the Python validator", async () => {
  const pick = goldenWire("value_pick");
  const unpriced = structuredClone(pick);
  const first = (unpriced.selections as Array<Record<string, unknown>>)[1];
  first.projected_cost_microusd = null;
  first.effort_multiplier = null;
  first.caveats = [{ code: "cost_unmeasured" }];
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(unpriced)), /priced configurations only/);

  const noCaveat = structuredClone(unpriced);
  (noCaveat.selections as Array<Record<string, unknown>>)[1].caveats = [];
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(noCaveat)), /cost_unmeasured caveat/);

  const badMultiplier = structuredClone(pick);
  (badMultiplier.selections as Array<Record<string, unknown>>)[0].effort_multiplier = { multiplier_ppm: 2, source: "comparison_level" };
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(badMultiplier)), /exactly 1/);

  const pinned = structuredClone(pick);
  (pinned.query as Record<string, unknown>).reasoning_effort = "medium";
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(pinned)), /pinned reasoning_effort/);

  const wrongUsage = structuredClone(pick);
  (wrongUsage.usage_profile as Record<string, unknown>).basis = "caller";
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(wrongUsage)), /echo/);

  const abstainWithPick = structuredClone(pick);
  abstainWithPick.outcome = "abstain";
  abstainWithPick.abstain_reasons = ["stale_evidence"];
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(abstainWithPick)), /abstain carries no selection/);

  const v1Reason = goldenWire("abstain_stale_evidence");
  v1Reason.abstain_reasons = ["evidence_stale"];
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(v1Reason)), /abstain_reasons item/);

  const topSet = goldenWire("top_set_pick");
  (topSet.selections as unknown[]).reverse();
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(topSet)), /highest-scoring/);

  const substituted = goldenWire("substituted_effort");
  ((substituted.selections as Array<Record<string, unknown>>)[0].caveats as Array<Record<string, unknown>>)[0].measured_effort = "medium";
  await assert.rejects(async () => parseDecisionReceiptV2(await rehashed(substituted)), /other than the selection's/);

  const caller = goldenWire("pinned_level");
  assert.equal((await parseDecisionReceiptV2(caller)).usage_profile.basis, "caller");
  assert.deepEqual((await parseDecisionReceiptV2(pick)).usage_profile.profile, DEFAULT_AGENT_TASK_MIX);
});

test("via_not_supported is a public problem code with a golden example", () => {
  const problem = golden.problems.find((row) => row.name === "via_not_supported")!;
  assert.equal(problem.problem.code, "via_not_supported");
  assert.equal(problem.problem.status, 422);
  assert.deepEqual(problem.problem.supported_via, [...SUPPORTED_VIA]);
  assert.equal(resolvedVia(parseDecisionQueryV2(problem.query)), "anthropic");
  assert.equal((SUPPORTED_VIA as readonly string[]).includes("anthropic"), false);
});

test("snapshot-set IDs hash one normalized float-free descriptor", async () => {
  const ref = {
    ranking_group_id: "rg-reasoning-model-configuration-direct-prompt-model-configuration-v1",
    evidence_snapshot_id: `snapshot_${"a".repeat(64)}`,
  };
  assert.equal("publication_snapshot_id" in ref, false);
  const descriptor = {
    object: "snapshot_set_descriptor" as const,
    schema_version: "1" as const,
    cell_id: "code-generation",
    manifest_version: "2026-07-09.2",
    methodology_version: "2026-07-09.2.public-decision-v1",
    ranking_group_snapshots: [
      { ranking_group_id: "rg-b", evidence_snapshot_id: `snapshot_${"b".repeat(64)}` },
      { ranking_group_id: "rg-a", evidence_snapshot_id: `explorer_${"a".repeat(64)}` },
    ],
  };
  assert.equal(await snapshotSetId(descriptor), await snapshotSetId({
    ...descriptor,
    ranking_group_snapshots: [...descriptor.ranking_group_snapshots].reverse(),
  }));
  assert.equal(
    await snapshotSetId(descriptor),
    "snapshot_set_e9f71f01453b8bc1b61e2e895122a9ee9441fc4f40e8b6fb016870338fed151d",
  );
  assert.throws(() => parseSnapshotSetDescriptorV1(descriptor), /sorted on the wire/);
  assert.equal(
    parseSnapshotSetDescriptorV1({
      ...descriptor,
      ranking_group_snapshots: [...descriptor.ranking_group_snapshots].reverse(),
    }).ranking_group_snapshots[0].ranking_group_id,
    "rg-a",
  );
  assert.throws(
    () => parseSnapshotSetDescriptorV1({
      ...descriptor,
      ranking_group_snapshots: [{
        ...descriptor.ranking_group_snapshots[1],
        generated_at: "2026-07-09T00:00:00Z",
      }],
    }),
    /unknown fields/,
  );

  const orderedDescriptor = parseSnapshotSetDescriptorV1({
    ...descriptor,
    ranking_group_snapshots: [...descriptor.ranking_group_snapshots].reverse(),
  });
  const leaderboard = {
    cell_id: orderedDescriptor.cell_id,
    manifest_version: orderedDescriptor.manifest_version,
    methodology_version: orderedDescriptor.methodology_version,
    snapshot_set_id: await snapshotSetId(orderedDescriptor),
    snapshot_set_descriptor: orderedDescriptor,
    ranking_groups: orderedDescriptor.ranking_group_snapshots,
  };
  assert.equal((await verifyLeaderboardSnapshotSet(leaderboard)).cell_id, "code-generation");
  await assert.rejects(
    () => verifyLeaderboardSnapshotSet({
      ...leaderboard,
      ranking_groups: [{
        ranking_group_id: "rg-a",
        evidence_snapshot_id: `explorer_${"c".repeat(64)}`,
      }],
    }),
    /exact ranking-group snapshot pairs/,
  );
  await assert.rejects(
    () => verifyLeaderboardSnapshotSet({
      ...leaderboard,
      ranking_groups: [
        { ranking_group_id: "rg-a", evidence_snapshot_id: `snapshot_${"b".repeat(64)}` },
        { ranking_group_id: "rg-b", evidence_snapshot_id: `explorer_${"a".repeat(64)}` },
      ],
    }),
    /exact ranking-group snapshot pairs/,
  );
});

test("read semantic verifiers reject the same leaderboard mutations as Python", async () => {
  const leaderboard = await activeLeaderboard();
  assert.equal(
    (await verifyLeaderboardSemantics(leaderboard)).cell_id,
    "code-generation",
  );

  const duplicateConfiguration = structuredClone(leaderboard);
  const duplicateEntry = structuredClone(duplicateConfiguration.ranking_groups[0].entries[0]);
  duplicateEntry.ranking.rank = 2;
  duplicateConfiguration.ranking_groups[0].entries.push(duplicateEntry);
  duplicateConfiguration.ranking_groups[0].eligibility_summary.rank_eligible_configuration_count = 2;
  await assert.rejects(
    () => verifyLeaderboardSemantics(duplicateConfiguration),
    /evaluated_configuration_id values must be unique/,
  );

  const noncontiguousRanks = structuredClone(leaderboard);
  noncontiguousRanks.ranking_groups[0].entries[0].ranking.rank = 2;
  await assert.rejects(
    () => verifyLeaderboardSemantics(noncontiguousRanks),
    /contiguous from 1/,
  );

  const invertedInterval = structuredClone(leaderboard);
  invertedInterval.ranking_groups[0].entries[0].ranking.uncertainty = {
    kind: "interval",
    level: 0.95,
    lower: 0.9,
    upper: 0.8,
  };
  await assert.rejects(
    () => verifyLeaderboardSemantics(invertedInterval),
    /lower must be <= upper/,
  );

  const falseGap = await previewLeaderboard(leaderboard);
  falseGap.ranking_groups[0].eligibility_summary.gap_codes.push(
    "insufficient_independent_families",
  );
  await assert.rejects(
    () => verifyLeaderboardSemantics(falseGap),
    /insufficient_independent_families/,
  );

  const topSetExplorer = structuredClone(leaderboard);
  topSetExplorer.ranking_groups[0].explorer_views = [{ entries: [] }];
  await assert.rejects(
    () => verifyLeaderboardSemantics(topSetExplorer),
    /top_set groups cannot expose explorer views/,
  );

  const topSetExplorerIdentity = structuredClone(leaderboard);
  topSetExplorerIdentity.snapshot_set_descriptor.ranking_group_snapshots[0].evidence_snapshot_id = `explorer_${"e".repeat(64)}`;
  topSetExplorerIdentity.ranking_groups[0].evidence_snapshot_id = `explorer_${"e".repeat(64)}`;
  topSetExplorerIdentity.snapshot_set_id = await snapshotSetId(topSetExplorerIdentity.snapshot_set_descriptor);
  await assert.rejects(
    () => verifyLeaderboardSemantics(topSetExplorerIdentity),
    /top_set groups require snapshot evidence/,
  );

  // A top_set claim (snapshot evidence) may never expose explorer views, in ANY
  // published state — the rule keys on the claim, not the state.
  for (const state of ["active", "preview", "shadow"] as const) {
    const topSetWithView = structuredClone(leaderboard);
    topSetWithView.ranking_groups[0].state = state;
    topSetWithView.ranking_groups[0].explorer_views = [{ entries: [] }];
    await assert.rejects(
      () => verifyLeaderboardSemantics(topSetWithView),
      /top_set groups cannot expose explorer views/,
    );
  }

  // An explorer claim validates in ANY published state (state is decoupled from
  // claim strength), but its evidence must be explorer_-prefixed.
  for (const state of ["active", "preview", "shadow"] as const) {
    const explorerGroup = await previewLeaderboard(leaderboard);
    explorerGroup.ranking_groups[0].state = state;
    await verifyLeaderboardSemantics(explorerGroup);

    const snapshotEvidence = structuredClone(explorerGroup);
    snapshotEvidence.snapshot_set_descriptor.ranking_group_snapshots[0].evidence_snapshot_id = `snapshot_${"a".repeat(64)}`;
    snapshotEvidence.ranking_groups[0].evidence_snapshot_id = `snapshot_${"a".repeat(64)}`;
    snapshotEvidence.snapshot_set_id = await snapshotSetId(snapshotEvidence.snapshot_set_descriptor);
    await assert.rejects(
      () => verifyLeaderboardSemantics(snapshotEvidence),
      /explorer groups require explorer evidence/,
    );
  }

  const explorerWithoutView = await previewLeaderboard(leaderboard);
  explorerWithoutView.snapshot_set_descriptor.ranking_group_snapshots[0].evidence_snapshot_id = `explorer_${"e".repeat(64)}`;
  explorerWithoutView.ranking_groups[0].evidence_snapshot_id = `explorer_${"e".repeat(64)}`;
  explorerWithoutView.ranking_groups[0].explorer_views = [];
  explorerWithoutView.snapshot_set_id = await snapshotSetId(explorerWithoutView.snapshot_set_descriptor);
  await assert.rejects(
    () => verifyLeaderboardSemantics(explorerWithoutView),
    /explorer evidence requires an explorer view/,
  );

  const previewCalibrated = structuredClone(leaderboard);
  previewCalibrated.ranking_groups[0].state = "preview";
  previewCalibrated.ranking_groups[0].entries[0].ranking.in_top_set = false;
  previewCalibrated.ranking_groups[0].eligibility_summary = {
    ...previewEligibility(),
    rank_eligible_configuration_count: 1,
    gap_codes: ["calibration_unvalidated"],
  };
  await assert.rejects(
    () => verifyLeaderboardSemantics(previewCalibrated),
    /explorer groups/,
  );

  const previewTopSet = await previewLeaderboard(leaderboard);
  previewTopSet.ranking_groups[0].explorer_views[0].entries[0].ranking.in_top_set = true;
  await assert.rejects(
    () => verifyLeaderboardSemantics(previewTopSet),
    /explorer views cannot claim top-set membership/,
  );

  // An explorer claim cannot carry a calibrated top-set member (group-level).
  const explorerClaimsTopSet = await previewLeaderboard(leaderboard);
  const claimEntry = structuredClone(explorerClaimsTopSet.ranking_groups[0].explorer_views[0].entries[0]);
  claimEntry.ranking.in_top_set = true;
  explorerClaimsTopSet.ranking_groups[0].entries = [claimEntry];
  await assert.rejects(
    () => verifyLeaderboardSemantics(explorerClaimsTopSet),
    /explorer reads cannot claim top-set membership/,
  );

  // v2 rejection: a top_set claim must carry validated calibration and no gaps.
  const topSetWithGaps = structuredClone(leaderboard);
  topSetWithGaps.ranking_groups[0].eligibility_summary.calibration_status = "unvalidated";
  topSetWithGaps.ranking_groups[0].eligibility_summary.gap_codes = ["calibration_unvalidated"];
  await assert.rejects(
    () => verifyLeaderboardSemantics(topSetWithGaps),
    /top_set reads require validated calibration with no gaps/,
  );

  for (const [label, mutate, pattern] of [
    ["duplicate configuration", (value: typeof previewTopSet) => value.ranking_groups[0].explorer_views[0].entries.push(structuredClone(value.ranking_groups[0].explorer_views[0].entries[0])), /unique/],
    ["gapped rank", (value: typeof previewTopSet) => { value.ranking_groups[0].explorer_views[0].entries[0].ranking.rank = 2; }, /contiguous/],
    ["family count", (value: typeof previewTopSet) => { value.ranking_groups[0].explorer_views[0].entries[0].ranking.evidence_family_count = 2; }, /evidence_family_count/],
    ["citation family", (value: typeof previewTopSet) => { value.ranking_groups[0].explorer_views[0].citations[0].benchmark_family_id = "other-family"; }, /citation/],
    ["agreement", (value: typeof previewTopSet) => { value.ranking_groups[0].explorer_views[0].agreement = "conflicting"; }, /agreement/],
    ["freshness", (value: typeof previewTopSet) => {
      value.ranking_groups[0].explorer_views[0].observed_at = "2026-07-08T00:00:00Z";
      value.ranking_groups[0].explorer_views[0].expires_at = "2026-07-09T00:00:00Z";
    }, /evidence_stale/],
  ] as const) {
    const invalid = await previewLeaderboard(leaderboard);
    mutate(invalid);
    await assert.rejects(() => verifyLeaderboardSemantics(invalid), pattern, label);
  }

  const duplicateGroup = structuredClone(leaderboard);
  duplicateGroup.ranking_groups.push(structuredClone(duplicateGroup.ranking_groups[0]));
  await assert.rejects(
    () => verifyLeaderboardSemantics(duplicateGroup),
    /one-to-one|unique ranking_group_id|ranking_group_id values must be unique/,
  );
});

test("entity and compare semantic verifiers bind ownership and reject parity mutations", async () => {
  const leaderboard = await activeLeaderboard();
  const group = leaderboard.ranking_groups[0];
  const passport = {
    object: "configuration_passport" as const,
    schema_version: "1" as const,
    entity_kind: "model_configuration" as const,
    canonical_name: "Example",
    revision: "1",
    interaction_policy: "direct_prompt" as const,
    configuration_passport_class: "model-configuration-v1" as const,
    harness: null,
    scaffold: null,
    tools: [],
    quantization: null,
    system_prompt_policy: null,
    environment: null,
  };
  const evaluated_configuration_id = await evaluatedConfigurationId(passport);
  const common = {
    schema_version: "1",
    cell_id: leaderboard.cell_id,
    manifest_version: leaderboard.manifest_version,
    methodology_version: leaderboard.methodology_version,
    snapshot_set_id: leaderboard.snapshot_set_id,
    snapshot_set_descriptor: leaderboard.snapshot_set_descriptor,
    ranking_group_id: group.ranking_group_id,
    evidence_snapshot_id: group.evidence_snapshot_id,
    explorer_view: null,
    state: "active",
    eligibility_summary: group.eligibility_summary,
    generated_at: leaderboard.generated_at,
  };
  const ranking = structuredClone(group.entries[0].ranking);
  const entity = {
    object: "entity_detail",
    ...common,
    entity: {
      evaluated_configuration: {
        object: "evaluated_configuration",
        schema_version: "1",
        evaluated_configuration_id,
        passport,
      },
      ranking,
      citations: group.citations,
    },
  };
  const compare = {
    object: "compare_result",
    ...common,
    entity_kind: group.entity_kind,
    interaction_policy: group.interaction_policy,
    configuration_passport_class: group.configuration_passport_class,
    entities: [
      { evaluated_configuration_id, ranking: structuredClone(ranking), citations: group.citations },
      {
        evaluated_configuration_id: `config_${"d".repeat(64)}`,
        ranking: { ...structuredClone(ranking), rank: 2 }, citations: group.citations,
      },
    ],
  };
  await verifyEntityDetailSemantics(entity);
  await verifyCompareResultSemantics(compare);

  const mixedIdentity = structuredClone(compare);
  mixedIdentity.interaction_policy = "agentic";
  await assert.rejects(
    () => verifyCompareResultSemantics(mixedIdentity),
    /ranking-group identity/,
  );

  for (const [document, verifier] of [
    [entity, verifyEntityDetailSemantics],
    [compare, verifyCompareResultSemantics],
  ] as const) {
    await assert.rejects(
      () => verifier({ ...document, ranking_group_id: "rg-other" }),
      /ranking-group snapshot pair/,
    );
  }

  const duplicateCompare = structuredClone(compare);
  duplicateCompare.entities[1].evaluated_configuration_id = evaluated_configuration_id;
  await assert.rejects(
    () => verifyCompareResultSemantics(duplicateCompare),
    /evaluated_configuration_id values must be unique/,
  );

  const duplicateRank = structuredClone(compare);
  duplicateRank.entities[1].ranking.rank = 1;
  await assert.rejects(
    () => verifyCompareResultSemantics(duplicateRank),
    /compare ranks must be unique/,
  );

  const oneEntity = structuredClone(compare);
  oneEntity.entities = oneEntity.entities.slice(0, 1);
  await assert.rejects(() => verifyCompareResultSemantics(oneEntity), /two to four/);

  const fiveEntities = structuredClone(compare);
  for (const [rank, character] of [[3, "e"], [4, "f"], [5, "b"]] as const) {
    fiveEntities.entities.push({
      ...structuredClone(fiveEntities.entities[0]),
      evaluated_configuration_id: `config_${character.repeat(64)}`,
      ranking: { ...structuredClone(ranking), rank },
    });
  }
  await assert.rejects(() => verifyCompareResultSemantics(fiveEntities), /two to four/);

  const previewEntity = structuredClone(entity);
  previewEntity.state = "preview";
  previewEntity.eligibility_summary = previewEligibility();
  await assert.rejects(
    () => verifyEntityDetailSemantics(previewEntity),
    /explorer evidence/,
  );
});

test("read semantic verifier rejects invalid closed wire values and stale group gaps", async () => {
  type LeaderboardFixture = Awaited<ReturnType<typeof activeLeaderboard>>;
  const mutations: Array<[string, (value: LeaderboardFixture) => void]> = [
    ["citation id", (value) => { value.ranking_groups[0].citations[0].source_artifact_id = "artifact_bad"; }],
    ["citation title", (value) => { value.ranking_groups[0].citations[0].title = ""; }],
    ["citation URL", (value) => { value.ranking_groups[0].citations[0].url = "http://example.com"; }],
    ["score", (value) => { value.ranking_groups[0].entries[0].ranking.capability_score = 2; }],
    ["family count", (value) => { value.ranking_groups[0].entries[0].ranking.evidence_family_count = 0; }],
    ["uncertainty level", (value) => { value.ranking_groups[0].entries[0].ranking.uncertainty.level = 0; }],
    ["caveat", (value) => { value.ranking_groups[0].entries[0].ranking.caveat_codes = ["Not Canonical"]; }],
    ["eligibility count", (value) => { value.ranking_groups[0].eligibility_summary.required_overlap_count = 0; }],
    ["eligibility enum", (value) => { value.ranking_groups[0].eligibility_summary.calibration_status = "unknown"; }],
    ["timestamp", (value) => { value.generated_at = "2026-02-30T00:00:00Z"; }],
    ["mixed identity", (value) => { value.ranking_groups[0].interaction_policy = "agentic"; }],
    ["citationless active", (value) => { value.ranking_groups[0].citations = []; }],
    ["invalid cell state", (value) => { value.cell_state = "invalid"; }],
    ["quarantined entries", (value) => {
      value.ranking_groups[0].state = "quarantined";
      value.ranking_groups[0].entries[0].ranking.in_top_set = false;
    }],
  ];
  for (const [label, mutate] of mutations) {
    const invalid = await activeLeaderboard();
    mutate(invalid);
    await assert.rejects(() => verifyLeaderboardSemantics(invalid), undefined, label);
  }

  const staleWithoutGap = await previewLeaderboard(await activeLeaderboard());
  staleWithoutGap.generated_at = "2026-07-10T00:00:00Z";
  staleWithoutGap.ranking_groups[0].explorer_views[0].observed_at = "2026-07-08T00:00:00Z";
  staleWithoutGap.ranking_groups[0].explorer_views[0].expires_at = "2026-07-09T00:00:00Z";
  for (const entry of staleWithoutGap.ranking_groups[0].explorer_views[0].entries) {
    entry.ranking.caveat_codes = ["evidence_stale"];
  }
  await assert.rejects(() => verifyLeaderboardSemantics(staleWithoutGap), /evidence_stale gap/);

  const freshWithGap = await previewLeaderboard(await activeLeaderboard());
  freshWithGap.ranking_groups[0].eligibility_summary.gap_codes.push("evidence_stale");
  await assert.rejects(() => verifyLeaderboardSemantics(freshWithGap), /evidence_stale gap/);
});

async function activeLeaderboard() {
  const ranking_group_id = "rg-code-generation-model";
  const evidence_snapshot_id = `snapshot_${"a".repeat(64)}`;
  const snapshot_set_descriptor = parseSnapshotSetDescriptorV1({
    object: "snapshot_set_descriptor",
    schema_version: "1",
    cell_id: "code-generation",
    manifest_version: "2026-07-09.2",
    methodology_version: "2026-07-09.2.truth-kernel-v1",
    ranking_group_snapshots: [{ ranking_group_id, evidence_snapshot_id }],
  });
  return {
    object: "leaderboard",
    schema_version: "1",
    cell_state: "active",
    cell_id: snapshot_set_descriptor.cell_id,
    manifest_version: snapshot_set_descriptor.manifest_version,
    methodology_version: snapshot_set_descriptor.methodology_version,
    snapshot_set_id: await snapshotSetId(snapshot_set_descriptor),
    snapshot_set_descriptor,
    generated_at: "2026-07-10T00:00:00Z",
    ranking_groups: [{
      ranking_group_id,
      entity_kind: "model_configuration",
      interaction_policy: "direct_prompt",
      configuration_passport_class: "model-configuration-v1",
      state: "active",
      evidence_snapshot_id,
      eligibility_summary: {
        published_claim: "top_set",
        rank_eligible_configuration_count: 1,
        current_independent_family_count: 3,
        required_independent_family_count: 3,
        current_overlap_count: 2,
        required_overlap_count: 2,
        calibration_status: "validated",
        gap_codes: [] as string[],
      },
      entries: [{
        evaluated_configuration_id: `config_${"c".repeat(64)}`,
        ranking: {
          rank: 1,
          display_name: "Example",
          capability_score: 0.8,
          uncertainty: {
            kind: "interval",
            level: 0.95,
            lower: 0.75,
            upper: 0.85,
          },
          in_top_set: true,
          evidence_family_count: 3,
          caveat_codes: [],
        },
      }],
      citations: [{
        source_artifact_id: `artifact_${"a".repeat(64)}`,
        benchmark_family_id: "family-a",
        title: "Family A",
        url: "https://example.com/a",
      }],
      explorer_views: [],
    }],
  };
}

async function previewLeaderboard<T extends Awaited<ReturnType<typeof activeLeaderboard>>>(
  leaderboard: T,
): Promise<T> {
  const preview = structuredClone(leaderboard);
  preview.ranking_groups[0].state = "preview";
  preview.ranking_groups[0].eligibility_summary = previewEligibility();
  const entries = preview.ranking_groups[0].entries;
  entries.forEach((entry) => { entry.ranking.in_top_set = false; });
  preview.ranking_groups[0].entries = [];
  entries.forEach((entry) => {
    entry.ranking.evidence_family_count = 1;
  });
  preview.ranking_groups[0].explorer_views = [{
    benchmark_family_id: "family-a",
    feed_id: "family-a-feed",
    metric_direction: "higher",
    observed_at: "2026-07-10T00:00:00Z",
    expires_at: "2026-07-11T00:00:00Z",
    agreement: "single_source",
    entries,
    citations: preview.ranking_groups[0].citations,
  }];
  preview.snapshot_set_descriptor.ranking_group_snapshots[0].evidence_snapshot_id = `explorer_${"f".repeat(64)}`;
  preview.ranking_groups[0].evidence_snapshot_id = `explorer_${"f".repeat(64)}`;
  preview.snapshot_set_id = await snapshotSetId(preview.snapshot_set_descriptor);
  return preview;
}

function previewEligibility() {
  return {
    published_claim: "explorer",
    rank_eligible_configuration_count: 0,
    current_independent_family_count: 3,
    required_independent_family_count: 3,
    current_overlap_count: 2,
    required_overlap_count: 2,
    calibration_status: "unvalidated",
    gap_codes: ["calibration_unvalidated", "no_rank_eligible_configurations"],
  };
}

test("Draft 2020 schemas enforce the portable semantic shapes they can express", () => {
  const names = [
    "source-artifact", "run-provenance", "observation", "configuration-passport",
    "evaluated-configuration", "serving-offer", "decision-query", "decision-receipt", "problem",
  ];
  const schemas = names.map((name) => JSON.parse(
    readFileSync(new URL(`../../../schemas/${name}.schema.json`, import.meta.url), "utf8"),
  ));
  const ajv = new Ajv2020({
    allErrors: true,
    strict: false,
    formats: { uri: true, "uri-reference": true },
  });
  schemas.forEach((schema) => ajv.addSchema(schema));

  const queryValidator = ajv.getSchema("https://evalrank.ai/schemas/decision-query.schema.json")!;
  const receiptValidator = ajv.getSchema("https://evalrank.ai/schemas/decision-receipt.schema.json")!;
  const problemValidator = ajv.getSchema("https://evalrank.ai/schemas/problem.schema.json")!;
  const observationValidator = ajv.getSchema("https://evalrank.ai/schemas/observation.schema.json")!;
  const provenanceValidator = ajv.getSchema("https://evalrank.ai/schemas/run-provenance.schema.json")!;
  const offerValidator = ajv.getSchema("https://evalrank.ai/schemas/serving-offer.schema.json")!;
  assert.equal(queryValidator(golden.query.input), true, ajv.errorsText(queryValidator.errors));
  for (const row of golden.receipts) {
    assert.equal(
      receiptValidator({ ...row.body, receipt_id: row.receipt_id }),
      true,
      `${row.name}: ${ajv.errorsText(receiptValidator.errors)}`,
    );
  }
  for (const row of golden.problems) {
    assert.equal(problemValidator(row.problem), true, ajv.errorsText(problemValidator.errors));
    assert.equal(queryValidator(row.query), true, ajv.errorsText(queryValidator.errors));
  }
  assert.equal(queryValidator({ schema_version: "2", cell_id: "writing", objective: "lowest_cost_within_top_set" }), true);
  for (const row of golden.rejection_vectors.slice(2)) {
    assert.equal(queryValidator(row.value), false, row.name);
  }

  const partialUsage = structuredClone(golden.query.input);
  delete (partialUsage.usage_profile as Record<string, unknown>).output_tokens;
  assert.equal(queryValidator(partialUsage), false);
  const zeroUsage = structuredClone(golden.query.input);
  zeroUsage.usage_profile = {
    basis: "measured",
    uncached_input_tokens: 0,
    cached_read_tokens: 0,
    output_tokens: 0,
    cache_writes: [],
    cache_storage_token_seconds: 0,
  };
  assert.equal(queryValidator(zeroUsage), false);
  (zeroUsage.usage_profile as Record<string, unknown>).cache_storage_token_seconds = 1;
  assert.equal(queryValidator(zeroUsage), false);

  const pick = golden.receipts.find((row) => row.name === "value_pick")!;
  const wire = (): Record<string, unknown> => structuredClone({ ...pick.body, receipt_id: pick.receipt_id });
  const pickWithReason = wire();
  pickWithReason.abstain_reasons = ["stale_evidence"];
  assert.equal(receiptValidator(pickWithReason), false);
  const emptyPick = wire();
  emptyPick.selections = [];
  assert.equal(receiptValidator(emptyPick), false);
  const floatRatio = wire();
  (floatRatio.selections as Array<Record<string, unknown>>)[0].capability_ratio_ppm = 0.985;
  assert.equal(receiptValidator(floatRatio), false);
  const omittedEffort = wire();
  delete (omittedEffort.selections as Array<Record<string, unknown>>)[0].reasoning_effort;
  assert.equal(receiptValidator(omittedEffort), false);
  const v1Field = wire();
  v1Field.publication_snapshot = {};
  assert.equal(receiptValidator(v1Field), false);

  const offer = {
    object: "serving_offer",
    schema_version: "1",
    serving_offer_id: "offer_public-demo",
    provider_id: "provider-public",
    sku: "public-demo",
    region: "us-west",
    context: {
      context_window_tokens: 128000,
      observed_at: "2026-07-09T00:00:00Z",
      expires_at: "2026-07-10T00:00:00Z",
      source_artifact_id: `artifact_${"a".repeat(64)}`,
    },
    availability: {
      status: "available",
      observed_at: "2026-07-09T00:00:00Z",
      expires_at: "2026-07-10T00:00:00Z",
      source_artifact_id: `artifact_${"a".repeat(64)}`,
    },
    pricing: {
      uncached_input_microusd_per_million_tokens: 1,
      cached_read_microusd_per_million_tokens: null,
      output_microusd_per_million_tokens: 1,
      cache_write_rates: [],
      cache_storage_microusd_per_million_token_hours: null,
      observed_at: "2026-07-09T00:00:00Z",
      effective_at: "2026-07-09T00:00:00Z",
      expires_at: "2026-07-10T00:00:00Z",
      source_artifact_id: `artifact_${"a".repeat(64)}`,
    },
  };
  assert.equal(offerValidator(offer), true, ajv.errorsText(offerValidator.errors));
  assert.equal(parseServingOfferV1(offer).serving_offer_id, "offer_public-demo");
  const legacyPricing = structuredClone(offer) as Record<string, unknown>;
  legacyPricing.pricing = {
    input_microusd_per_million_tokens: 1,
    output_microusd_per_million_tokens: 1,
    observed_at: "2026-07-09T00:00:00Z",
    expires_at: "2026-07-10T00:00:00Z",
    source_artifact_id: `artifact_${"a".repeat(64)}`,
  };
  assert.equal(offerValidator(legacyPricing), false);

  const provenance = {
    object: "run_provenance",
    schema_version: "1",
    run_id: "run-public-01",
    benchmark_family_id: "livecodebench",
    feed_id: "livecodebench-discovery",
    source_artifacts: [
      { role: "primary", source_artifact_id: `artifact_${"a".repeat(64)}` },
    ],
    parser_id: "json-parser",
    parser_version: "1",
    started_at: "2026-07-09T00:00:00Z",
    completed_at: "2026-07-09T00:01:00Z",
    harness_version: null,
    environment_digest: null,
    scorer_version: null,
    trial_policy: null,
    adapter_metadata: null,
  };
  const observation = {
    object: "observation",
    schema_version: "1",
    observation_id: "obs_public_01",
    evaluated_configuration_id: `config_${"b".repeat(64)}`,
    metric: { kind: "proportion", value: "0.75", numerator: 3, denominator: 4 },
    uncertainty: { kind: "unknown" },
    provenance,
  };
  assert.equal(observationValidator(observation), true, ajv.errorsText(observationValidator.errors));
  assert.equal(
    provenanceValidator({
      ...provenance,
      source_artifacts: [
        { role: "categories", source_artifact_id: `artifact_${"a".repeat(64)}` },
      ],
    }),
    false,
  );
  assert.equal(
    provenanceValidator({
      ...provenance,
      source_artifacts: [
        { role: "primary", source_artifact_id: `artifact_${"a".repeat(64)}` },
        { role: "primary", source_artifact_id: `artifact_${"b".repeat(64)}` },
      ],
    }),
    false,
  );
  assert.equal(observationValidator({ ...observation, metric: { ...observation.metric, value: "1.1" } }), false);
  assert.equal(observationValidator({ ...observation, metric: { ...observation.metric, denominator: 0 } }), false);
});
