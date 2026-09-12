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
  isEvaluationToOfferLinkEligible,
  isServingOfferDecisionEligible,
  parseServingOfferV1,
  parseConfigurationPassportV1,
  parseDecisionQueryV1,
  parseDecisionReceiptV1,
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
  readFileSync(new URL("../../../examples/decision-contract-v1.golden.json", import.meta.url), "utf8"),
) as {
  utf16_set_order: { input: string[]; canonical: string[] };
  query: { input: Record<string, unknown>; canonical: string };
  receipt: { body: Record<string, unknown>; body_sha256: string; receipt_id: string };
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
  assert.equal(await sha256Hex(golden.receipt.body), golden.receipt.body_sha256);
  assert.equal(await receiptId(golden.receipt.body), golden.receipt.receipt_id);
  for (const vector of golden.rejection_vectors.slice(0, 2)) {
    assert.throws(() => canonicalJson(vector.value), /float|safe integer/);
  }
  const nullFilter = golden.rejection_vectors.find((row) => row.name === "null_provider_filter")!;
  assert.throws(() => parseDecisionQueryV1(nullFilter.value), /must not be null/);
});

test("restricted JCS orders by UTF-16 and rejects unsafe hash material", () => {
  assert.equal(canonicalJson({ "\ue000": 2, "\u{10000}": 1 }), '{"\u{10000}":1,"\ue000":2}');
  for (const value of [1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => canonicalJson(value), /float|safe integer|finite/);
  }
  assert.throws(() => canonicalJson({ value: "\ud800" }), /surrogate/);
  assert.throws(() => canonicalJson(Array(1)), /sparse array hole/);
  assert.deepEqual(
    parseDecisionQueryV1({ ...golden.query.input, provider_ids: golden.utf16_set_order.input }).provider_ids,
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
  assert.ok(manifest.ranking_groups.some((row) => row.ranking_group_id === golden.query.input.ranking_group_id));
  assert.ok(manifest.benchmark_families.some((row) => row.benchmark_family_id === "livecodebench"));
  assert.ok(manifest.feeds.some((row) => row.feed_id === "livecodebench-discovery" && row.benchmark_family_id === "livecodebench"));
});

test("query decoding canonicalizes unordered sets and rejects transport metadata and null filters", () => {
  const input = {
    ...golden.query.input,
    provider_ids: ["provider-b", "provider-a"],
    regions: ["us-west", "eu-west"],
  };
  const parsed = parseDecisionQueryV1(input);
  assert.deepEqual(parsed.provider_ids, ["provider-a", "provider-b"]);
  assert.deepEqual(parsed.regions, ["eu-west", "us-west"]);
  assert.throws(() => parseDecisionQueryV1({ ...input, request_id: "transport" }), /unknown fields/);
  assert.throws(() => parseDecisionQueryV1({ ...input, provider_ids: null }), /must not be null/);
  assert.throws(
    () => parseDecisionQueryV1({ ...input, provider_ids: ["provider-a", "provider-a"] }),
    /unique/,
  );
  const withoutUsage = structuredClone(input);
  withoutUsage.objective = "capability_top_set";
  delete withoutUsage.usage_profile;
  delete withoutUsage.zero_cache_sensitivity_usage_profile;
  assert.throws(() => parseDecisionQueryV1(withoutUsage), /monthly_budget_microusd/);

  const missingZeroCache = structuredClone(input);
  delete missingZeroCache.zero_cache_sensitivity_usage_profile;
  assert.throws(() => parseDecisionQueryV1(missingZeroCache), /zero_cache_sensitivity/);
  const wrongZeroCache = structuredClone(input);
  (wrongZeroCache.zero_cache_sensitivity_usage_profile as Record<string, unknown>).uncached_input_tokens = 19_999_999;
  assert.throws(() => parseDecisionQueryV1(wrongZeroCache), /total input/);
  const measured = structuredClone(input);
  (measured.usage_profile as Record<string, unknown>).basis = "measured";
  delete measured.zero_cache_sensitivity_usage_profile;
  assert.equal(parseDecisionQueryV1(measured).usage_profile?.basis, "measured");
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

test("offer-link eligibility is exact, approved, and evaluated at the caller's as-of time", () => {
  const link = {
    object: "evaluation_to_offer_link",
    schema_version: "1",
    evaluation_to_offer_link_id: "link_public-demo",
    evaluated_configuration_id: `config_${"b".repeat(64)}`,
    serving_offer_id: "offer_public-demo",
    compatibility: "exact" as const,
    evidence_basis: "benchmark_exact" as const,
    evidence_source_artifact_id: `artifact_${"a".repeat(64)}`,
    observed_at: "2026-07-09T00:00:00Z",
    expires_at: "2026-07-10T00:00:00Z",
    review_state: "approved" as const,
  };
  assert.equal(isEvaluationToOfferLinkEligible(link, "2026-07-09T12:00:00Z"), true);
  assert.equal(isEvaluationToOfferLinkEligible({ ...link, evidence_basis: "inferred" }, "2026-07-09T12:00:00Z"), false);
  assert.equal(isEvaluationToOfferLinkEligible({ ...link, review_state: "pending" }, "2026-07-09T12:00:00Z"), false);
  assert.equal(isEvaluationToOfferLinkEligible(link, "2026-07-10T00:00:00Z"), false);
  assert.equal("eligible" in link, false);

  const fact = {
    observed_at: "2026-07-09T00:00:00Z",
    expires_at: "2026-07-10T00:00:00Z",
    source_artifact_id: `artifact_${"a".repeat(64)}`,
  };
  const offer = parseServingOfferV1({
    object: "serving_offer",
    schema_version: "1",
    serving_offer_id: "offer_public-demo",
    provider_id: "provider-public",
    sku: "public-demo",
    region: "us-west",
    context: { context_window_tokens: 128000, ...fact },
    availability: { status: "available", ...fact },
    pricing: {
      uncached_input_microusd_per_million_tokens: 1000000,
      cached_read_microusd_per_million_tokens: 200000,
      output_microusd_per_million_tokens: 4800000,
      cache_write_rates: [{ ttl_seconds: 300, microusd_per_million_tokens: 1200000 }],
      cache_storage_microusd_per_million_token_hours: 100000,
      effective_at: "2026-07-09T01:00:00Z",
      ...fact,
    },
  });
  assert.equal(isServingOfferDecisionEligible(offer, link, "2026-07-09T12:00:00Z"), true);
  assert.equal(isServingOfferDecisionEligible(offer, link, "2026-07-09T00:30:00Z"), false);
  assert.equal(
    isServingOfferDecisionEligible({ ...offer, availability: { ...offer.availability, status: "unavailable" } }, link, "2026-07-09T12:00:00Z"),
    false,
  );
  assert.equal(isServingOfferDecisionEligible(offer, link, "2026-07-10T00:00:00Z"), false);
});

test("eligibility helpers fail closed for malformed runtime input", () => {
  const link = {
    object: "evaluation_to_offer_link",
    schema_version: "1",
    evaluation_to_offer_link_id: "link_public-demo",
    evaluated_configuration_id: `config_${"b".repeat(64)}`,
    serving_offer_id: "offer_public-demo",
    compatibility: "exact",
    evidence_basis: "benchmark_exact",
    evidence_source_artifact_id: `artifact_${"a".repeat(64)}`,
    observed_at: "2026-07-09T00:00:00Z",
    expires_at: "2026-07-10T00:00:00Z",
    review_state: "approved",
  } satisfies Record<string, unknown>;
  const fact = {
    observed_at: "2026-07-09T00:00:00Z",
    expires_at: "2026-07-10T00:00:00Z",
    source_artifact_id: `artifact_${"a".repeat(64)}`,
  };
  const offer = {
    object: "serving_offer",
    schema_version: "1",
    serving_offer_id: "offer_public-demo",
    provider_id: "provider-public",
    sku: "public-demo",
    region: "us-west",
    context: { context_window_tokens: 128000, ...fact },
    availability: { status: "available", ...fact },
    pricing: {
      uncached_input_microusd_per_million_tokens: 1000000,
      cached_read_microusd_per_million_tokens: 200000,
      output_microusd_per_million_tokens: 4800000,
      cache_write_rates: [{ ttl_seconds: 300, microusd_per_million_tokens: 1200000 }],
      cache_storage_microusd_per_million_token_hours: 100000,
      effective_at: "2026-07-09T01:00:00Z",
      ...fact,
    },
  } satisfies Record<string, unknown>;

  for (const malformed of [
    { ...link, evidence_basis: "invented" },
    { ...link, evidence_source_artifact_id: "mutable-latest" },
    { ...link, observed_at: "not-a-timestamp" },
  ]) {
    assert.equal(isEvaluationToOfferLinkEligible(malformed, "2026-07-09T12:00:00Z"), false);
    assert.equal(isServingOfferDecisionEligible(offer, malformed, "2026-07-09T12:00:00Z"), false);
  }
  assert.equal(isEvaluationToOfferLinkEligible(link, "not-a-timestamp"), false);
  assert.equal(
    isServingOfferDecisionEligible(
      { ...offer, pricing: { ...(offer.pricing as Record<string, unknown>), effective_at: "bad" } },
      link,
      "2026-07-09T12:00:00Z",
    ),
    false,
  );
});

test("monthly schedule pricing uses BigInt, one final ceiling, and fails closed", () => {
  assert.equal("monthlyCostMicrousd" in contracts, true);
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

  assert.equal(contracts.monthlyCostMicrousd(usage, pricing), 1);
  assert.equal(
    contracts.monthlyCostMicrousd(
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

test("receipt parsing verifies the full-body hash", async () => {
  const wire = { ...golden.receipt.body, receipt_id: golden.receipt.receipt_id };
  assert.equal((await parseDecisionReceiptV1(wire)).receipt_id, golden.receipt.receipt_id);
  await assert.rejects(
    () => parseDecisionReceiptV1({ ...wire, methodology_version: "2026-07-09.2.changed" }),
    /receipt_id/,
  );

  const unsortedBody = structuredClone(golden.receipt.body);
  (unsortedBody.evidence as unknown[]).reverse();
  (unsortedBody.sensitivity as unknown[]).reverse();
  assert.equal(await receiptId(unsortedBody), golden.receipt.receipt_id);

  await assert.rejects(
    () => parseDecisionReceiptV1({ ...wire, reasons: [] }),
    /reasons/,
  );
  const badSensitivity = structuredClone(wire);
  (badSensitivity.sensitivity as Array<Record<string, unknown>>)[0].selected_configuration_ids = [`config_${"b".repeat(64)}`];
  await assert.rejects(() => parseDecisionReceiptV1(badSensitivity), /sensitivity|leave_one_family_out/);

  await assert.rejects(
    () => parseDecisionReceiptV1({ ...wire, decided_at: "2026-07-10T00:00:00Z" }),
    /decided_at|current/,
  );
  const wrongCost = structuredClone(wire);
  (wrongCost.selections as Array<Record<string, unknown>>)[0].projected_monthly_cost_microusd = 43000000;
  await assert.rejects(() => parseDecisionReceiptV1(wrongCost), /computed monthly cost/);
  const missingLinkEvidence = structuredClone(wire);
  missingLinkEvidence.evidence = (missingLinkEvidence.evidence as Array<Record<string, unknown>>)
    .filter((row) => row.kind !== "evaluation_to_offer_link");
  await assert.rejects(() => parseDecisionReceiptV1(missingLinkEvidence), /offer-link evidence|cited evidence_id/);

  const unequalCosts = structuredClone(wire);
  (unequalCosts.selections as Array<Record<string, unknown>>).push({
    evaluated_configuration_id: `config_${"c".repeat(64)}`,
    serving_offer_id: "offer_public-demo-two",
    capability_rank: 2,
    projected_monthly_cost_microusd: 45000000,
    zero_cache_sensitivity_projected_monthly_cost_microusd: 48000000,
  });
  await assert.rejects(() => parseDecisionReceiptV1(unequalCosts), /equal minimum cost/);

  const duplicateConfiguration = structuredClone(wire);
  (duplicateConfiguration.selections as Array<Record<string, unknown>>).push({
    ...(duplicateConfiguration.selections as Array<Record<string, unknown>>)[0],
    serving_offer_id: "offer_public-demo-two",
  });
  await assert.rejects(() => parseDecisionReceiptV1(duplicateConfiguration), /selections must be unique/);
});

test("receipt cost fields and reasons describe projections under declared profiles", () => {
  const selection = (golden.receipt.body.selections as Array<Record<string, unknown>>)[0];
  assert.equal("projected_monthly_cost_microusd" in selection, true);
  assert.equal("zero_cache_sensitivity_projected_monthly_cost_microusd" in selection, true);
  assert.equal(`${"estimated"}_monthly_cost_microusd` in selection, false);
  assert.equal(`${"zero_cache_sensitivity"}_monthly_cost_microusd` in selection, false);
  const codes = new Set(
    (golden.receipt.body.reasons as Array<Record<string, unknown>>)
      .map((reason) => reason.code),
  );
  assert.equal(codes.has("lowest_cost_under_usage_profile"), true);
  assert.equal(codes.has("budget_fit_under_declared_profiles"), true);
  assert.equal(codes.has(`${"lowest"}_verified_cost`), false);
  assert.equal(codes.has(`${"budget"}_constraint_met`), false);
});

test("hard budgets cover every declared profile and differing estimated projections are caveated", async () => {
  const uncaveated = structuredClone(golden.receipt.body);
  for (const reason of uncaveated.reasons as Array<Record<string, unknown>>) {
    if (["lowest_cost_under_usage_profile", "budget_fit_under_declared_profiles"].includes(String(reason.code))) {
      reason.caveat_codes = (reason.caveat_codes as unknown[])
        .filter((code) => code !== "cost_sensitive_to_usage");
    }
  }
  const uncaveatedReceipt = {
    ...uncaveated,
    receipt_id: golden.receipt.receipt_id,
  };
  await assert.rejects(
    () => parseDecisionReceiptV1(uncaveatedReceipt),
    /cost_sensitive_to_usage/,
  );

  const overBudgetSensitivity = structuredClone(golden.receipt.body);
  (overBudgetSensitivity.query as Record<string, unknown>).monthly_budget_microusd = 42_000_000;
  for (const reason of overBudgetSensitivity.reasons as Array<Record<string, unknown>>) {
    if (reason.code === "budget_fit_under_declared_profiles") reason.threshold = "42000000";
  }
  const overBudgetSensitivityReceipt = {
    ...overBudgetSensitivity,
    receipt_id: golden.receipt.receipt_id,
  };
  await assert.rejects(
    () => parseDecisionReceiptV1(overBudgetSensitivityReceipt),
    /zero-cache sensitivity.*budget/,
  );
});

test("capability receipts still disclose differing projected costs", async () => {
  const capabilityBody = structuredClone(golden.receipt.body);
  const query = capabilityBody.query as Record<string, unknown>;
  query.objective = "capability_top_set";
  for (const field of [
    "provider_ids",
    "regions",
    "minimum_context_tokens",
    "monthly_budget_microusd",
  ]) delete query[field];
  capabilityBody.reasons = (capabilityBody.reasons as Array<Record<string, unknown>>)
    .filter((reason) => reason.code === "within_capability_top_set");
  capabilityBody.sensitivity = (capabilityBody.sensitivity as Array<Record<string, unknown>>)
    .filter((row) => row.scenario === "leave_one_family_out");
  capabilityBody.freshness = {
    observed_at: "2026-07-09T00:00:00Z",
    expires_at: "2026-07-10T00:00:00Z",
  };

  const uncaveatedCapabilityReceipt = {
    ...capabilityBody,
    receipt_id: golden.receipt.receipt_id,
  };
  await assert.rejects(
    () => parseDecisionReceiptV1(uncaveatedCapabilityReceipt),
    /cost_sensitive_to_usage/,
  );

  (capabilityBody.reasons as Array<Record<string, unknown>>)[0].caveat_codes = [
    "cost_sensitive_to_usage",
  ];
  const receipt = await parseDecisionReceiptV1({
    ...capabilityBody,
    receipt_id: await receiptId(capabilityBody),
  });
  assert.deepEqual(receipt.reasons[0].caveat_codes, ["cost_sensitive_to_usage"]);
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
    "evaluated-configuration", "serving-offer", "evaluation-to-offer-link", "decision-query", "decision-receipt",
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
  const observationValidator = ajv.getSchema("https://evalrank.ai/schemas/observation.schema.json")!;
  const provenanceValidator = ajv.getSchema("https://evalrank.ai/schemas/run-provenance.schema.json")!;
  const offerValidator = ajv.getSchema("https://evalrank.ai/schemas/serving-offer.schema.json")!;
  const linkValidator = ajv.getSchema("https://evalrank.ai/schemas/evaluation-to-offer-link.schema.json")!;
  assert.equal(queryValidator(golden.query.input), true, ajv.errorsText(queryValidator.errors));
  assert.equal(
    receiptValidator({ ...golden.receipt.body, receipt_id: golden.receipt.receipt_id }),
    true,
    ajv.errorsText(receiptValidator.errors),
  );

  const partialUsage = structuredClone(golden.query.input);
  delete (partialUsage.usage_profile as Record<string, unknown>).output_tokens;
  assert.equal(queryValidator(partialUsage), false);
  const missingZeroCache = structuredClone(golden.query.input);
  delete missingZeroCache.zero_cache_sensitivity_usage_profile;
  assert.equal(queryValidator(missingZeroCache), false);
  const measured = structuredClone(golden.query.input);
  (measured.usage_profile as Record<string, unknown>).basis = "measured";
  delete measured.zero_cache_sensitivity_usage_profile;
  assert.equal(queryValidator(measured), true, ajv.errorsText(queryValidator.errors));
  const zeroUsage = structuredClone(measured);
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

  const evidence = golden.receipt.body.evidence as Array<Record<string, unknown>>;
  const offer = structuredClone(evidence.find((row) => row.kind === "serving_offer")!.serving_offer);
  const link = structuredClone(evidence.find((row) => row.kind === "evaluation_to_offer_link")!.evaluation_to_offer_link);
  assert.equal(offerValidator(offer), true, ajv.errorsText(offerValidator.errors));
  assert.equal(linkValidator(link), true, ajv.errorsText(linkValidator.errors));
  delete (link as Record<string, unknown>).evidence_basis;
  assert.equal(linkValidator(link), false);
  const legacyPricing = structuredClone(offer) as Record<string, unknown>;
  legacyPricing.pricing = {
    input_microusd_per_million_tokens: 1,
    output_microusd_per_million_tokens: 1,
    observed_at: "2026-07-09T00:00:00Z",
    expires_at: "2026-07-10T00:00:00Z",
    source_artifact_id: `artifact_${"a".repeat(64)}`,
  };
  assert.equal(offerValidator(legacyPricing), false);

  const emptyReasons = { ...golden.receipt.body, receipt_id: golden.receipt.receipt_id, reasons: [] };
  assert.equal(receiptValidator(emptyReasons), false);
  const removedCostVocabulary = structuredClone({
    ...golden.receipt.body,
    receipt_id: golden.receipt.receipt_id,
  });
  const removedSelection = (
    removedCostVocabulary.selections as Array<Record<string, unknown>>
  )[0];
  removedSelection[`${"estimated"}_monthly_cost_microusd`] =
    removedSelection.projected_monthly_cost_microusd;
  delete removedSelection.projected_monthly_cost_microusd;
  assert.equal(receiptValidator(removedCostVocabulary), false);
  const missingLeaveOneOut = structuredClone({ ...golden.receipt.body, receipt_id: golden.receipt.receipt_id });
  missingLeaveOneOut.sensitivity = (missingLeaveOneOut.sensitivity as Array<Record<string, unknown>>)
    .filter((row) => row.scenario !== "leave_one_family_out");
  assert.equal(receiptValidator(missingLeaveOneOut), false);

  const honestCostAbstention = structuredClone({
    ...golden.receipt.body,
    receipt_id: golden.receipt.receipt_id,
  });
  honestCostAbstention.outcome = "abstain";
  honestCostAbstention.selections = [];
  honestCostAbstention.exclusions = [];
  honestCostAbstention.reasons = [];
  honestCostAbstention.sensitivity = [];
  honestCostAbstention.evidence = [];
  honestCostAbstention.abstention_reason = "no_eligible_serving_offer";
  assert.equal(
    receiptValidator(honestCostAbstention),
    true,
    ajv.errorsText(receiptValidator.errors),
  );

  const invalidComparisonThreshold = structuredClone({
    ...golden.receipt.body,
    receipt_id: golden.receipt.receipt_id,
  });
  const contextReason = (invalidComparisonThreshold.reasons as Array<Record<string, unknown>>)
    .find((row) => row.code === "context_requirement_met")!;
  contextReason.threshold = null;
  assert.equal(receiptValidator(invalidComparisonThreshold), false);

  const invalidStatus = structuredClone({
    ...honestCostAbstention,
    reasons: [{
      reason_type: "avoid_when",
      code: "insufficient_evidence",
      subject_id: `config_${"a".repeat(64)}`,
      predicate: "unavailable",
      axis: "capability",
      observed_value: "invented-status",
      unit: "status",
      threshold: null,
      evidence_ids: ["evidence-observation"],
      freshness: honestCostAbstention.freshness,
      caveat_codes: [],
    }],
  });
  assert.equal(receiptValidator(invalidStatus), false);

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
