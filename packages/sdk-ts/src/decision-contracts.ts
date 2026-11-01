/** Portable EvalRank provenance and decision contracts. */

export const MAX_SAFE_INTEGER = 9_007_199_254_740_991;

export type EntityKind =
  | "model_configuration"
  | "agent_system"
  | "system_configuration"
  | "component_configuration"
  | "arena_system";
export type InteractionPolicy =
  | "direct_prompt"
  | "agentic"
  | "system"
  | "retrieval"
  | "crowd_pairwise";
export type ConfigurationPassportClass =
  | "model-configuration-v1"
  | "agent-system-v1"
  | "system-configuration-v1"
  | "component-configuration-v1"
  | "arena-system-v1";

export const RESOLVED_IDENTITY_TRIPLES = [
  ["model_configuration", "direct_prompt", "model-configuration-v1"],
  ["agent_system", "agentic", "agent-system-v1"],
  ["system_configuration", "system", "system-configuration-v1"],
  ["component_configuration", "retrieval", "component-configuration-v1"],
  ["arena_system", "crowd_pairwise", "arena-system-v1"],
] as const;

export interface SourceArtifactV1 {
  object: "source_artifact";
  schema_version: "1";
  source_artifact_id: string;
  canonical_url: string;
  upstream_version: string;
  content_sha256: string;
  byte_length: number;
  media_type: string;
  fetched_at: string;
}

export interface TrialPolicyV1 {
  attempts_per_item: number;
  seed_strategy: "fixed" | "derived" | "upstream";
  seed: number | null;
}

export interface AdapterMetadataV1 {
  schema_version: string;
  payload: Record<string, unknown>;
}

export interface RunInputArtifactV1 {
  readonly role: string;
  readonly source_artifact_id: string;
}

export interface RunProvenanceV1 {
  object: "run_provenance";
  schema_version: "1";
  run_id: string;
  benchmark_family_id: string;
  feed_id: string;
  source_artifacts: readonly [RunInputArtifactV1, ...RunInputArtifactV1[]];
  parser_id: string;
  parser_version: string;
  started_at: string;
  completed_at: string;
  harness_version: string | null;
  environment_digest: string | null;
  scorer_version: string | null;
  trial_policy: TrialPolicyV1 | null;
  adapter_metadata: AdapterMetadataV1 | null;
}

export interface ProportionMetricV1 {
  kind: "proportion";
  value: string;
  numerator: number | null;
  denominator: number | null;
}

export interface ContinuousMetricV1 {
  kind: "continuous";
  value: string;
  unit: string;
  n_items: number | null;
}

export interface PassAtKMetricV1 {
  kind: "pass_at_k";
  value: string;
  k: number;
  successful_items: number | null;
  evaluated_items: number | null;
}

export interface PairwisePreferenceMetricV1 {
  kind: "pairwise_preference";
  value: string;
  scale: "probability" | "elo" | "margin";
  comparison_count: number | null;
}

export interface RankOnlyMetricV1 {
  kind: "rank_only";
  rank: number;
  candidate_count: number | null;
}

export type MetricV1 =
  | ProportionMetricV1
  | ContinuousMetricV1
  | PassAtKMetricV1
  | PairwisePreferenceMetricV1
  | RankOnlyMetricV1;

export interface UnknownUncertaintyV1 {
  kind: "unknown";
}

export interface StandardErrorUncertaintyV1 {
  kind: "standard_error";
  value: string;
}

export interface IntervalUncertaintyV1 {
  kind: "interval";
  low: string;
  high: string;
  confidence_level: string;
  method:
    | "reported"
    | "bootstrap_percentile"
    | "bootstrap_bca"
    | "clopper_pearson"
    | "wilson"
    | "normal_approximation"
    | "credible_interval";
}

export type UncertaintyV1 =
  | UnknownUncertaintyV1
  | StandardErrorUncertaintyV1
  | IntervalUncertaintyV1;

export interface ObservationV1 {
  object: "observation";
  schema_version: "1";
  observation_id: string;
  evaluated_configuration_id: string;
  metric: MetricV1;
  uncertainty: UncertaintyV1;
  provenance: RunProvenanceV1;
}

export interface ConfigurationPassportV1 {
  object: "configuration_passport";
  schema_version: "1";
  entity_kind: EntityKind;
  canonical_name: string;
  revision: string;
  interaction_policy: InteractionPolicy;
  configuration_passport_class: ConfigurationPassportClass;
  harness: string | null;
  scaffold: string | null;
  tools: string[];
  quantization: string | null;
  system_prompt_policy: string | null;
  environment: string | null;
}

export interface EvaluatedConfigurationV1 {
  object: "evaluated_configuration";
  schema_version: "1";
  evaluated_configuration_id: string;
  passport: ConfigurationPassportV1;
}

export interface DatedFactV1 {
  observed_at: string;
  expires_at: string;
  source_artifact_id: string;
}

export interface ContextFactV1 extends DatedFactV1 {
  context_window_tokens: number;
}

export interface AvailabilityFactV1 extends DatedFactV1 {
  status: "available" | "limited" | "unavailable";
}

export interface CacheWriteUsageV1 {
  ttl_seconds: number;
  tokens: number;
}

export interface UsageProfileV1 {
  basis: "measured" | "estimated";
  uncached_input_tokens: number;
  cached_read_tokens: number;
  output_tokens: number;
  cache_writes: CacheWriteUsageV1[];
  cache_storage_token_seconds: number;
}

export interface CacheWriteRateV1 {
  ttl_seconds: number;
  microusd_per_million_tokens: number;
}

export interface PricingScheduleFactV1 extends DatedFactV1 {
  uncached_input_microusd_per_million_tokens: number;
  cached_read_microusd_per_million_tokens: number | null;
  output_microusd_per_million_tokens: number;
  cache_write_rates: CacheWriteRateV1[];
  cache_storage_microusd_per_million_token_hours: number | null;
  effective_at: string;
}

export interface ServingOfferV1 {
  object: "serving_offer";
  schema_version: "1";
  serving_offer_id: string;
  provider_id: string;
  sku: string;
  region: string;
  context: ContextFactV1;
  availability: AvailabilityFactV1;
  pricing: PricingScheduleFactV1;
}

export const REASONING_EFFORTS = ["none", "minimal", "low", "medium", "high", "xhigh", "max"] as const;
export const DECISION_OBJECTIVES = ["lowest_cost_within_top_set", "capability_top_set"] as const;
export const DECISION_APIS = ["chat_completions", "responses"] as const;
export const ABSTAIN_REASONS = ["no_ranked_candidate", "no_eligible_offer", "stale_evidence", "not_a_model_cell"] as const;
export const EXCLUSION_CODES = [
  "ambiguous_identity",
  "effort_not_accepted",
  "api_not_supported",
  "no_serving_offer",
  "cost_unmeasured",
  "effort_gap_too_large",
  "constraints_not_met",
] as const;
export const LOCK_STATUSES = ["admitted", "held", "rejected", "unlocked"] as const;
/** Call surfaces with a probed effort vocabulary; any other `via` is a 422 `via_not_supported`. */
export const SUPPORTED_VIA = ["openai", "openrouter"] as const;
/** The usage profile a query without `usage_profile` is priced at: cache-heavy agent traffic. */
export const DEFAULT_AGENT_TASK_MIX: UsageProfileV1 = Object.freeze({
  basis: "estimated",
  uncached_input_tokens: 1_000,
  cached_read_tokens: 8_000,
  output_tokens: 500,
  cache_writes: [],
  cache_storage_token_seconds: 0,
}) as UsageProfileV1;

export type ReasoningEffort = (typeof REASONING_EFFORTS)[number];
export type DecisionObjective = (typeof DECISION_OBJECTIVES)[number];
export type DecisionApi = (typeof DECISION_APIS)[number];
export type AbstainReasonV2 = (typeof ABSTAIN_REASONS)[number];

export interface DecisionQueryV2 {
  object?: "decision_query";
  schema_version: "2";
  cell_id: string;
  objective: DecisionObjective;
  via?: string;
  provider_ids?: string[];
  api?: DecisionApi;
  reasoning_effort?: ReasoningEffort;
  regions?: string[];
  minimum_context_tokens?: number;
  usage_profile?: UsageProfileV1;
}

export interface DecisionFamilyV2 {
  family_id: string;
  lock_status: (typeof LOCK_STATUSES)[number];
  weight_ppm: number;
  stale_at: string | null;
}

export interface DecisionPriceV2 {
  input_microusd_per_million: number | null;
  cached_input_microusd_per_million: number | null;
  output_microusd_per_million: number | null;
}

export interface EffortMultiplierV2 {
  multiplier_ppm: number;
  /** Cost family id, or `comparison_level` for exactly 1. */
  source: string;
}

export type DecisionCaveatV2 =
  | { code: "effort_substituted"; measured_effort: ReasoningEffort; gap_ppm: number }
  | { code: "cost_unmeasured" };

export interface DecisionSelectionV2 {
  /** Host-native id for the query's via: `openai/gpt-6-sol` on openrouter, `gpt-6-sol` on openai. */
  model_id: string;
  display_name: string;
  provider_id: string;
  serving_offer_id: string;
  /** Always explicit: send it as returned. */
  reasoning_effort: ReasoningEffort;
  api: DecisionApi;
  capability_ratio_ppm: number;
  family_coverage: number;
  price: DecisionPriceV2;
  effort_multiplier: EffortMultiplierV2 | null;
  projected_cost_microusd: number | null;
  latency_p50_ms: number | null;
  caveats: DecisionCaveatV2[];
}

export interface DecisionExclusionV2 {
  model_key: string;
  code: (typeof EXCLUSION_CODES)[number];
  reasoning_effort?: ReasoningEffort;
  detail?: string;
}

export interface DecisionUsageV2 {
  basis: "caller" | "default_agent_task_mix";
  profile: UsageProfileV1;
}

/** `pick`: `selections[0]` is the pick and the rest is the band in order. `abstain`: no selection, one or more reasons. */
export interface DecisionReceiptV2 {
  object: "decision_receipt";
  schema_version: "2";
  receipt_id: string;
  query: DecisionQueryV2;
  decided_at: string;
  outcome: "pick" | "abstain";
  snapshot_ids: string[];
  families: DecisionFamilyV2[];
  selections: DecisionSelectionV2[];
  exclusions: DecisionExclusionV2[];
  usage_profile: DecisionUsageV2;
  abstain_reasons: AbstainReasonV2[];
}

export interface SnapshotSetDescriptorV1 {
  object: "snapshot_set_descriptor";
  schema_version: "1";
  cell_id: string;
  manifest_version: string;
  methodology_version: string;
  ranking_group_snapshots: RankingGroupSnapshotRefV1[];
}

export interface RankingGroupSnapshotRefV1 {
  ranking_group_id: string;
  evidence_snapshot_id: string;
}

const artifactIdPattern = /^artifact_[0-9a-f]{64}$/;
const configurationIdPattern = /^config_[0-9a-f]{64}$/;
const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const caveatPattern = /^[a-z0-9]+(?:(?:-|_)[a-z0-9]+)*$/;
const observationIdPattern = /^obs_[A-Za-z0-9][A-Za-z0-9._:-]*$/;
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const decimalPattern = /^(?:0|[1-9]\d*)(?:\.\d*[1-9])?$|^-(?:0\.\d*[1-9]|[1-9]\d*(?:\.\d*[1-9])?)$/;

const entityKinds = [
  "model_configuration",
  "agent_system",
  "system_configuration",
  "component_configuration",
  "arena_system",
] as const;
const interactionPolicies = ["direct_prompt", "agentic", "system", "retrieval", "crowd_pairwise"] as const;
const passportClasses = [
  "model-configuration-v1",
  "agent-system-v1",
  "system-configuration-v1",
  "component-configuration-v1",
  "arena-system-v1",
] as const;
const identityTriples = new Set(RESOLVED_IDENTITY_TRIPLES.map((row) => row.join("|")));

/** Restricted RFC 8785: valid Unicode, UTF-16 key order, safe integers, no floats. */
export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalValue(value, "$"));
}

export async function sha256Hex(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(canonicalJson(value));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function sourceArtifactId(contentSha256: string): string {
  if (!/^[0-9a-f]{64}$/.test(contentSha256)) {
    throw new TypeError("content_sha256 must be lowercase SHA-256 hex");
  }
  return `artifact_${contentSha256}`;
}

export async function evaluatedConfigurationId(passport: ConfigurationPassportV1): Promise<string> {
  return `config_${await sha256Hex(parseConfigurationPassportV1(passport))}`;
}

export async function receiptId(body: Record<string, unknown>): Promise<string> {
  if ("receipt_id" in body) {
    throw new TypeError("receipt body must exclude receipt_id");
  }
  return `receipt_${await sha256Hex(normalizeReceiptBody(body))}`;
}

export function parseSnapshotSetDescriptorV1(value: unknown): SnapshotSetDescriptorV1 {
  const payload = closed(value, [
    "object", "schema_version", "cell_id", "manifest_version", "methodology_version", "ranking_group_snapshots",
  ]);
  envelope(payload, "snapshot_set_descriptor");
  const references = array(payload.ranking_group_snapshots, "ranking_group_snapshots")
    .map(parseRankingGroupSnapshotRefV1);
  validateUniqueSnapshotOwnership(references);
  const ordered = sortRankingGroupSnapshots(references);
  if (references.some((reference, index) => !sameSnapshotReference(reference, ordered[index]))) {
    throw new TypeError("ranking_group_snapshots must be UTF-16 sorted on the wire");
  }
  return {
    object: "snapshot_set_descriptor",
    schema_version: "1",
    cell_id: patternString(payload.cell_id, /^[a-z0-9]+(?:-[a-z0-9]+)*$/, "cell_id"),
    manifest_version: patternString(payload.manifest_version, /^\d{4}-\d{2}-\d{2}\.[1-9]\d*$/, "manifest_version"),
    methodology_version: patternString(payload.methodology_version, /^\d{4}-\d{2}-\d{2}\.[1-9]\d*\.([a-z0-9]+-)*[a-z0-9]+$/, "methodology_version"),
    ranking_group_snapshots: references,
  };
}

export function parseRankingGroupSnapshotRefV1(value: unknown): RankingGroupSnapshotRefV1 {
  const payload = closed(value, ["ranking_group_id", "evidence_snapshot_id"]);
  return {
    ranking_group_id: patternString(
      payload.ranking_group_id,
      /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
      "ranking_group_id",
    ),
    evidence_snapshot_id: patternString(
      payload.evidence_snapshot_id,
      /^(snapshot|explorer)_[0-9a-f]{64}$/,
      "evidence_snapshot_id",
    ),
  };
}

export async function snapshotSetId(descriptor: SnapshotSetDescriptorV1): Promise<string> {
  const normalized = {
    ...descriptor,
    ranking_group_snapshots: sortRankingGroupSnapshots(
      array(descriptor.ranking_group_snapshots, "ranking_group_snapshots")
        .map(parseRankingGroupSnapshotRefV1),
    ),
  };
  validateUniqueSnapshotOwnership(normalized.ranking_group_snapshots);
  return `snapshot_set_${await sha256Hex(parseSnapshotSetDescriptorV1(normalized))}`;
}

export async function verifyLeaderboardSnapshotSet(payload: unknown): Promise<SnapshotSetDescriptorV1> {
  const leaderboard = record(payload, "leaderboard");
  for (const name of [
    "cell_id", "manifest_version", "methodology_version", "snapshot_set_id",
    "snapshot_set_descriptor", "ranking_groups",
  ]) {
    if (!(name in leaderboard)) throw new TypeError(`leaderboard is missing ${name}`);
  }
  const descriptor = parseSnapshotSetDescriptorV1(leaderboard.snapshot_set_descriptor);
  for (const name of ["cell_id", "manifest_version", "methodology_version"] as const) {
    if (leaderboard[name] !== descriptor[name]) {
      throw new TypeError(`leaderboard ${name} must match snapshot_set_descriptor`);
    }
  }
  const groups = array(leaderboard.ranking_groups, "ranking_groups");
  if (groups.length === 0) throw new TypeError("leaderboard ranking_groups must be a non-empty array");
  const references = groups.map((group) => {
    const row = record(group, "ranking group");
    return parseRankingGroupSnapshotRefV1({
      ranking_group_id: row.ranking_group_id,
      evidence_snapshot_id: row.evidence_snapshot_id,
    });
  });
  validateUniqueSnapshotOwnership(references);
  const ordered = sortRankingGroupSnapshots(references);
  if (
    ordered.length !== descriptor.ranking_group_snapshots.length
    || ordered.some((reference, index) => !sameSnapshotReference(
      reference,
      descriptor.ranking_group_snapshots[index],
    ))
  ) {
    throw new TypeError("snapshot_set_descriptor must contain the exact ranking-group snapshot pairs");
  }
  if (leaderboard.snapshot_set_id !== await snapshotSetId(descriptor)) {
    throw new TypeError("snapshot_set_id must hash the exact snapshot_set_descriptor");
  }
  return descriptor;
}

function sortRankingGroupSnapshots(
  references: RankingGroupSnapshotRefV1[],
): RankingGroupSnapshotRefV1[] {
  return [...references].sort((left, right) => {
    if (left.ranking_group_id < right.ranking_group_id) return -1;
    if (left.ranking_group_id > right.ranking_group_id) return 1;
    if (left.evidence_snapshot_id < right.evidence_snapshot_id) return -1;
    if (left.evidence_snapshot_id > right.evidence_snapshot_id) return 1;
    return 0;
  });
}

function sameSnapshotReference(
  left: RankingGroupSnapshotRefV1,
  right: RankingGroupSnapshotRefV1,
): boolean {
  return left.ranking_group_id === right.ranking_group_id
    && left.evidence_snapshot_id === right.evidence_snapshot_id;
}

function validateUniqueSnapshotOwnership(references: RankingGroupSnapshotRefV1[]): void {
  if (new Set(references.map((reference) => reference.ranking_group_id)).size !== references.length) {
    throw new TypeError("ranking_group_snapshots must own unique ranking_group_id values");
  }
  if (
    new Set(references.map((reference) => reference.evidence_snapshot_id)).size
    !== references.length
  ) {
    throw new TypeError("ranking_group_snapshots must own unique evidence_snapshot_id values");
  }
}

export async function verifyLeaderboardSemantics(
  payload: unknown,
): Promise<SnapshotSetDescriptorV1> {
  const complete = closed(payload, [
    "object", "schema_version", "cell_id", "cell_state", "manifest_version",
    "methodology_version", "snapshot_set_id", "snapshot_set_descriptor", "generated_at",
    "ranking_groups",
  ]);
  envelope(complete, "leaderboard");
  if (!["active", "preview", "shadow", "quarantined"].includes(String(complete.cell_state))) {
    throw new TypeError("leaderboard cell_state is invalid");
  }
  const generatedAt = utcTimestamp(complete.generated_at, "generated_at");
  const descriptor = await verifyLeaderboardSnapshotSet(payload);
  const leaderboard = record(payload, "leaderboard");
  const groupIds = new Set<string>();
  const configurationIds = new Set<string>();
  for (const value of array(leaderboard.ranking_groups, "ranking_groups")) {
    const group = closed(value, [
      "ranking_group_id", "entity_kind", "interaction_policy", "configuration_passport_class",
      "state", "evidence_snapshot_id", "eligibility_summary", "entries", "citations",
      "explorer_views",
    ]);
    const groupId = nonEmptyString(group.ranking_group_id, "ranking_group_id");
    if (!slugPattern.test(groupId)) throw new TypeError("ranking_group_id must be canonical");
    if (groupIds.has(groupId)) {
      throw new TypeError("ranking_group_id values must be unique");
    }
    groupIds.add(groupId);
    const entries = array(group.entries, "ranking group entries");
    verifyRankings(entries, configurationIds, true);
    for (const citation of array(group.citations, "ranking group citations")) {
      verifyCitation(citation);
    }
    const hasTopSet = entries.some((entry) =>
      verifyReadRanking(record(entry, "leaderboard entry").ranking).inTopSet
    );
    if (!["active", "preview", "shadow", "quarantined"].includes(String(group.state))) {
      throw new TypeError("ranking group state is invalid");
    }
    const identity = [
      group.entity_kind, group.interaction_policy, group.configuration_passport_class,
    ].join("|");
    if (!identityTriples.has(identity) && identity !== "unresolved|unresolved|unresolved-v1") {
      throw new TypeError("ranking group identity is invalid");
    }
    const explorerViews = array(group.explorer_views, "explorer_views");
    const evidenceSnapshotId = String(group.evidence_snapshot_id);
    // Publication visibility (state) is decoupled from claim strength: evidence,
    // exposure, and membership rules key on published_claim, not state. ANY published
    // state may carry EITHER claim.
    const publishedClaim = readPublishedClaim(group);
    verifyClaimTopSet(publishedClaim, hasTopSet);
    if (publishedClaim === "top_set" && !evidenceSnapshotId.startsWith("snapshot_")) {
      throw new TypeError("top_set groups require snapshot evidence");
    }
    if (publishedClaim === "explorer" && !evidenceSnapshotId.startsWith("explorer_")) {
      throw new TypeError("explorer groups require explorer evidence");
    }
    if (publishedClaim === "top_set" && explorerViews.length !== 0) {
      throw new TypeError("top_set groups cannot expose explorer views");
    }
    if (publishedClaim === "top_set" && entries.length !== 0
      && array(group.citations, "ranking group citations").length === 0) {
      throw new TypeError("top_set ranking entries require group citations");
    }
    if (group.state === "quarantined" && entries.length !== 0) {
      throw new TypeError("quarantined groups cannot expose entries");
    }
    if (publishedClaim === "explorer" && entries.length !== 0) {
      throw new TypeError("explorer groups cannot expose calibrated entries");
    }
    if (evidenceSnapshotId.startsWith("explorer_") && explorerViews.length === 0) {
      throw new TypeError("explorer evidence requires an explorer view");
    }
    if (evidenceSnapshotId.startsWith("snapshot_") && explorerViews.length !== 0) {
      throw new TypeError("snapshot evidence cannot expose explorer views");
    }
    const hasStaleView = verifyExplorerViews(explorerViews, generatedAt);
    const eligibility = verifyEligibility(group.eligibility_summary, {
      state: group.state,
      entityKind: group.entity_kind,
      entryCount: entries.length,
      hasTopSet,
    });
    if ((eligibility.gap_codes as string[]).includes("evidence_stale") !== hasStaleView) {
      throw new TypeError("evidence_stale gap must match explorer view freshness");
    }
  }
  return descriptor;
}

function verifyExplorerViews(value: unknown, generatedAt: Date): boolean {
  const views = array(value, "explorer_views");
  const orderings: string[][] = [];
  let anyStale = false;
  for (const viewValue of views) {
    const view = closed(viewValue, [
      "benchmark_family_id", "feed_id", "metric_direction", "observed_at", "expires_at",
      "agreement", "entries", "citations",
    ]);
    const observedAt = utcTimestamp(view.observed_at, "observed_at");
    const expiresAt = utcTimestamp(view.expires_at, "expires_at");
    const stale = generatedAt >= expiresAt;
    anyStale ||= stale;
    if (expiresAt <= observedAt) throw new TypeError("explorer expires_at must be after observed_at");
    if (!slugPattern.test(String(view.benchmark_family_id)) || !slugPattern.test(String(view.feed_id))) {
      throw new TypeError("explorer view identity is invalid");
    }
    if (view.metric_direction !== "higher" && view.metric_direction !== "lower") {
      throw new TypeError("explorer metric_direction is invalid");
    }
    for (const citationValue of array(view.citations, "explorer view citations")) {
      const citation = verifyCitation(citationValue);
      if (citation.benchmark_family_id !== view.benchmark_family_id) {
        throw new TypeError("explorer citation must match benchmark_family_id");
      }
    }
    const entries = array(view.entries, "explorer view entries");
    verifyRankings(entries, new Set<string>(), true);
    orderings.push(entries.map((entry) => String(record(entry, "explorer view entry").evaluated_configuration_id)));
    for (const entryValue of entries) {
      const entry = record(entryValue, "explorer view entry");
      const ranking = verifyReadRanking(entry.ranking);
      if (ranking.inTopSet) {
        throw new TypeError("explorer views cannot claim top-set membership");
      }
      const rawRanking = record(entry.ranking, "entity ranking");
      if (rawRanking.evidence_family_count !== 1) throw new TypeError("explorer evidence_family_count must equal 1");
      const caveats = array(rawRanking.caveat_codes, "caveat_codes");
      if (caveats.includes("evidence_stale") !== stale) {
        throw new TypeError("explorer evidence_stale must match expires_at");
      }
    }
  }
  const expected = views.length === 1
    ? "single_source"
    : orderings.slice(1).every((ordering) => JSON.stringify(ordering) === JSON.stringify(orderings[0]))
      ? "promising_not_proven"
      : "conflicting";
  if (views.some((view) => record(view, "explorer view").agreement !== expected)) {
    throw new TypeError("explorer agreement must be derived across views");
  }
  return anyStale;
}

export async function verifyEntityDetailSemantics(
  payload: unknown,
): Promise<SnapshotSetDescriptorV1> {
  const document = closed(payload, [
    "object", "schema_version", "cell_id", "manifest_version", "methodology_version",
    "snapshot_set_id", "snapshot_set_descriptor", "ranking_group_id", "state",
    "evidence_snapshot_id", "explorer_view", "eligibility_summary", "generated_at", "entity",
  ]);
  envelope(document, "entity_detail");
  utcTimestamp(document.generated_at, "generated_at");
  const descriptor = await verifySnapshotReference(document);
  const projection = closed(document.entity, ["evaluated_configuration", "ranking", "citations"]);
  await parseEvaluatedConfigurationV1(projection.evaluated_configuration);
  const ranking = verifyReadRanking(projection.ranking);
  verifyClaimTopSet(readPublishedClaim(document), ranking.inTopSet);
  verifyEligibilitySummaryState(document.eligibility_summary, document.state);
  verifySelectedExplorerView(document, projection.citations);
  return descriptor;
}

export async function verifyCompareResultSemantics(
  payload: unknown,
): Promise<SnapshotSetDescriptorV1> {
  const document = closed(payload, [
    "object", "schema_version", "cell_id", "manifest_version", "methodology_version",
    "snapshot_set_id", "snapshot_set_descriptor", "ranking_group_id", "entity_kind",
    "interaction_policy", "configuration_passport_class", "state", "evidence_snapshot_id",
    "explorer_view", "eligibility_summary", "generated_at", "entities",
  ]);
  envelope(document, "compare_result");
  utcTimestamp(document.generated_at, "generated_at");
  const descriptor = await verifySnapshotReference(document);
  const identity = [
    document.entity_kind, document.interaction_policy, document.configuration_passport_class,
  ].join("|");
  if (!identityTriples.has(identity)) {
    throw new TypeError("compare ranking-group identity is invalid");
  }
  const comparedEntities = array(document.entities, "compare entities");
  if (comparedEntities.length < 2 || comparedEntities.length > 4) {
    throw new TypeError("compare entities must contain two to four rows");
  }
  const configurationIds = new Set<string>();
  const ranks = new Set<number>();
  for (const value of comparedEntities) {
    const entity = closed(value, ["evaluated_configuration_id", "ranking", "citations"]);
    const configurationId = patternString(
      entity.evaluated_configuration_id,
      configurationIdPattern,
      "evaluated_configuration_id",
    );
    if (configurationIds.has(configurationId)) {
      throw new TypeError("compare evaluated_configuration_id values must be unique");
    }
    configurationIds.add(configurationId);
    const ranking = verifyReadRanking(entity.ranking);
    if (ranks.has(ranking.rank)) {
      throw new TypeError("compare ranks must be unique");
    }
    ranks.add(ranking.rank);
    verifyClaimTopSet(readPublishedClaim(document), ranking.inTopSet);
    verifySelectedExplorerView(document, entity.citations);
  }
  verifyEligibilitySummaryState(document.eligibility_summary, document.state);
  return descriptor;
}

async function verifySnapshotReference(
  payload: Record<string, unknown>,
): Promise<SnapshotSetDescriptorV1> {
  const descriptor = parseSnapshotSetDescriptorV1(payload.snapshot_set_descriptor);
  for (const name of ["cell_id", "manifest_version", "methodology_version"] as const) {
    if (payload[name] !== descriptor[name]) {
      throw new TypeError(`${name} must match snapshot_set_descriptor`);
    }
  }
  if (payload.snapshot_set_id !== await snapshotSetId(descriptor)) {
    throw new TypeError("snapshot_set_id must hash snapshot_set_descriptor");
  }
  const reference = parseRankingGroupSnapshotRefV1({
    ranking_group_id: payload.ranking_group_id,
    evidence_snapshot_id: payload.evidence_snapshot_id,
  });
  if (!["active", "preview", "shadow"].includes(String(payload.state))) {
    throw new TypeError("public read state is invalid");
  }
  if (!descriptor.ranking_group_snapshots.some((candidate) =>
    sameSnapshotReference(candidate, reference)
  )) {
    throw new TypeError(
      "ranking-group snapshot pair must belong to snapshot_set_descriptor",
    );
  }
  // Evidence prefix is bound to the claim (top_set⇒snapshot_, explorer⇒explorer_),
  // not to the publication state; any published state may carry either claim.
  const publishedClaim = readPublishedClaim(payload);
  if (publishedClaim === "top_set" && !reference.evidence_snapshot_id.startsWith("snapshot_")) {
    throw new TypeError("top_set reads require snapshot evidence");
  }
  if (publishedClaim === "explorer" && !reference.evidence_snapshot_id.startsWith("explorer_")) {
    throw new TypeError("explorer reads require explorer evidence");
  }
  return descriptor;
}

function verifySelectedExplorerView(payload: Record<string, unknown>, citations: unknown): void {
  let selector: Record<string, unknown> | null = null;
  if (readPublishedClaim(payload) === "top_set") {
    if (payload.explorer_view !== null) throw new TypeError("top_set reads cannot select an explorer view");
  } else {
    selector = closed(payload.explorer_view, ["benchmark_family_id", "feed_id"]);
    patternString(selector.benchmark_family_id, slugPattern, "benchmark_family_id");
    patternString(selector.feed_id, slugPattern, "feed_id");
  }
  const values = array(citations, "citations");
  if (values.length === 0) throw new TypeError("citations must be a non-empty array");
  for (const value of values) {
    const citation = verifyCitation(value);
    if (selector !== null && citation.benchmark_family_id !== selector.benchmark_family_id) {
      throw new TypeError("citations must match selected explorer benchmark_family_id");
    }
  }
}

function verifyRankings(
  entries: unknown[],
  configurationIds: Set<string>,
  requireContiguous: boolean,
): void {
  const ranks: number[] = [];
  for (const value of entries) {
    const entry = closed(value, ["evaluated_configuration_id", "ranking"]);
    const configurationId = patternString(
      entry.evaluated_configuration_id,
      configurationIdPattern,
      "evaluated_configuration_id",
    );
    if (configurationIds.has(configurationId)) {
      throw new TypeError("evaluated_configuration_id values must be unique");
    }
    configurationIds.add(configurationId);
    ranks.push(verifyReadRanking(entry.ranking).rank);
  }
  if (
    requireContiguous
    && ranks.some((rank, index) => rank !== index + 1)
  ) {
    throw new TypeError("leaderboard ranks must be contiguous from 1 in array order");
  }
}

function verifyReadRanking(value: unknown): { rank: number; inTopSet: boolean } {
  const ranking = closed(value, [
    "rank", "display_name", "capability_score", "uncertainty", "in_top_set",
    "evidence_family_count", "caveat_codes",
  ]);
  if (!Number.isSafeInteger(ranking.rank)) {
    throw new TypeError("entity ranking rank must be an integer");
  }
  if ((ranking.rank as number) < 1 || (ranking.rank as number) > MAX_SAFE_INTEGER) {
    throw new TypeError("entity ranking rank must be a positive safe integer");
  }
  if (typeof ranking.display_name !== "string" || ranking.display_name.length === 0) {
    throw new TypeError("entity ranking display_name must be non-empty");
  }
  if (typeof ranking.capability_score !== "number" || !Number.isFinite(ranking.capability_score)
    || ranking.capability_score < 0 || ranking.capability_score > 1) {
    throw new TypeError("entity ranking capability_score must be within [0,1]");
  }
  if (typeof ranking.in_top_set !== "boolean") {
    throw new TypeError("entity ranking in_top_set must be a boolean");
  }
  const uncertainty = closed(
    ranking.uncertainty,
    record(ranking.uncertainty, "uncertainty").kind === "unknown"
      ? ["kind"]
      : ["kind", "level", "lower", "upper"],
  );
  if (uncertainty.kind === "unknown") {
    // closed() enforces the sole valid field.
  } else if (uncertainty.kind === "interval") {
    if (
      typeof uncertainty.level !== "number" || !Number.isFinite(uncertainty.level)
      || uncertainty.level <= 0 || uncertainty.level > 1
      || typeof uncertainty.lower !== "number"
      || !Number.isFinite(uncertainty.lower)
      || typeof uncertainty.upper !== "number"
      || !Number.isFinite(uncertainty.upper)
    ) {
      throw new TypeError(
        "ranking interval must contain numeric lower and upper values",
      );
    }
    if (uncertainty.lower > uncertainty.upper) {
      throw new TypeError("ranking interval lower must be <= upper");
    }
    if (uncertainty.lower < 0 || uncertainty.upper > 1) {
      throw new TypeError("ranking interval must be within [0,1]");
    }
  } else {
    throw new TypeError("ranking uncertainty kind is invalid");
  }
  if (!Number.isSafeInteger(ranking.evidence_family_count)
    || (ranking.evidence_family_count as number) < 1) {
    throw new TypeError("entity ranking evidence_family_count must be a positive safe integer");
  }
  const caveats = array(ranking.caveat_codes, "caveat_codes");
  if (new Set(caveats).size !== caveats.length
    || caveats.some((value) => typeof value !== "string" || !caveatPattern.test(value))) {
    throw new TypeError("entity ranking caveat_codes must be unique canonical strings");
  }
  return { rank: ranking.rank as number, inTopSet: ranking.in_top_set };
}

function verifyCitation(value: unknown): Record<string, unknown> {
  const citation = closed(value, ["source_artifact_id", "benchmark_family_id", "title", "url"]);
  patternString(citation.source_artifact_id, artifactIdPattern, "source_artifact_id");
  patternString(citation.benchmark_family_id, slugPattern, "benchmark_family_id");
  nonEmptyString(citation.title, "citation title");
  if (typeof citation.url !== "string" || !/^https:\/\/\S+$/.test(citation.url)) {
    throw new TypeError("citation URL must use HTTPS");
  }
  return citation;
}

function utcTimestamp(value: unknown, name: string): Date {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) {
    throw new TypeError(`${name} must be a UTC-second timestamp`);
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf()) || parsed.toISOString() !== `${value.slice(0, -1)}.000Z`) {
    throw new TypeError(`${name} must be a UTC-second timestamp`);
  }
  return parsed;
}

function verifyEligibility(
  value: unknown,
  context: {
    state: unknown;
    entityKind: unknown;
    entryCount: number;
    hasTopSet: boolean;
  },
): Record<string, unknown> {
  const eligibility = verifyEligibilitySummaryState(value, context.state);
  if (eligibility.rank_eligible_configuration_count !== context.entryCount) {
    throw new TypeError(
      "rank_eligible_configuration_count must equal leaderboard entry count",
    );
  }
  const gaps = new Set(eligibility.gap_codes as string[]);
  if (
    context.entityKind === "unresolved"
    && (context.entryCount !== 0 || !gaps.has("unresolved_identity"))
  ) {
    throw new TypeError(
      "unresolved groups must be empty and disclose unresolved_identity",
    );
  }
  if (eligibility.published_claim === "top_set" && !context.hasTopSet) {
    throw new TypeError("top_set ranking groups must publish at least one top-set member");
  }
  return eligibility;
}

function verifyEligibilitySummaryState(
  value: unknown,
  state: unknown,
): Record<string, unknown> {
  const eligibility = closed(value, [
    "published_claim", "rank_eligible_configuration_count", "current_independent_family_count",
    "required_independent_family_count", "current_overlap_count", "required_overlap_count",
    "calibration_status", "gap_codes",
  ]);
  const gaps = array(eligibility.gap_codes, "eligibility gap_codes");
  if (
    gaps.some((gap) => typeof gap !== "string" || ![
      "calibration_unvalidated", "evidence_stale", "insufficient_configuration_overlap",
      "insufficient_independent_families", "no_rank_eligible_configurations", "quarantined",
      "unresolved_identity",
    ].includes(gap))
    || new Set(gaps).size !== gaps.length
  ) {
    throw new TypeError("eligibility gap_codes must be a unique array");
  }
  if (!["explorer", "top_set"].includes(String(eligibility.published_claim))
    || !["unvalidated", "validated"].includes(String(eligibility.calibration_status))) {
    throw new TypeError("eligibility enum value is invalid");
  }
  // Claim strength, not publication state, drives the calibration/gap gate.
  if (eligibility.published_claim === "top_set") {
    if (eligibility.calibration_status !== "validated" || gaps.length !== 0) {
      throw new TypeError("top_set reads require validated calibration with no gaps");
    }
  } else if (gaps.length === 0) {
    throw new TypeError("explorer reads require explicit gaps");
  }
  verifyEligibilityCountGaps(eligibility, new Set(gaps as string[]));
  if (state === "quarantined" && !gaps.includes("quarantined")) {
    throw new TypeError("quarantined reads must disclose the quarantined gap");
  }
  return eligibility;
}

function verifyEligibilityCountGaps(
  value: Record<string, unknown>,
  gaps: Set<string>,
): void {
  verifyCountGap(value, {
    current: "current_independent_family_count",
    required: "required_independent_family_count",
    code: "insufficient_independent_families",
  }, gaps);
  verifyCountGap(value, {
    current: "current_overlap_count",
    required: "required_overlap_count",
    code: "insufficient_configuration_overlap",
  }, gaps);
  const eligible = value.rank_eligible_configuration_count;
  if (!Number.isSafeInteger(eligible) || (eligible as number) < 0) {
    throw new TypeError("rank_eligible_configuration_count must be an integer");
  }
  if ((eligible === 0) !== gaps.has("no_rank_eligible_configurations")) {
    throw new TypeError(
      "no_rank_eligible_configurations gap must match eligibility count",
    );
  }
  if (
    (value.calibration_status === "unvalidated")
    !== gaps.has("calibration_unvalidated")
  ) {
    throw new TypeError(
      "calibration_unvalidated gap must match calibration_status",
    );
  }
}

function verifyCountGap(
  value: Record<string, unknown>,
  fields: { current: string; required: string; code: string },
  gaps: Set<string>,
): void {
  const current = value[fields.current];
  const required = value[fields.required];
  if (!Number.isSafeInteger(current) || !Number.isSafeInteger(required)
    || (current as number) < 0 || (required as number) < 1) {
    throw new TypeError("eligibility counts must be integers");
  }
  if (((current as number) < (required as number)) !== gaps.has(fields.code)) {
    throw new TypeError(`${fields.code} gap must match eligibility counts`);
  }
}

function readPublishedClaim(payload: Record<string, unknown>): unknown {
  const eligibility = payload.eligibility_summary;
  if (typeof eligibility !== "object" || eligibility === null) return undefined;
  return (eligibility as Record<string, unknown>).published_claim;
}

function verifyClaimTopSet(publishedClaim: unknown, inTopSet: boolean): void {
  if (publishedClaim === "explorer" && inTopSet) {
    throw new TypeError("explorer reads cannot claim top-set membership");
  }
}

export function parseSourceArtifactV1(value: unknown): SourceArtifactV1 {
  const payload = closed(value, [
    "object", "schema_version", "source_artifact_id", "canonical_url", "upstream_version",
    "content_sha256", "byte_length", "media_type", "fetched_at",
  ]);
  envelope(payload, "source_artifact");
  const contentHash = patternString(payload.content_sha256, /^[0-9a-f]{64}$/, "content_sha256");
  const artifact: SourceArtifactV1 = {
    object: "source_artifact",
    schema_version: "1",
    source_artifact_id: patternString(payload.source_artifact_id, artifactIdPattern, "source_artifact_id"),
    canonical_url: httpUrl(payload.canonical_url, "canonical_url"),
    upstream_version: nonEmptyString(payload.upstream_version, "upstream_version"),
    content_sha256: contentHash,
    byte_length: safeInteger(payload.byte_length, "byte_length", 0),
    media_type: patternString(payload.media_type, /^[A-Za-z0-9!#$&^_.+-]+\/[A-Za-z0-9!#$&^_.+-]+$/, "media_type"),
    fetched_at: timestamp(payload.fetched_at, "fetched_at"),
  };
  if (artifact.source_artifact_id !== sourceArtifactId(contentHash)) {
    throw new TypeError("source_artifact_id must be artifact_<content_sha256>");
  }
  return artifact;
}

export function parseRunProvenanceV1(value: unknown): RunProvenanceV1 {
  const raw = record(value, "run provenance");
  if (!("source_artifacts" in raw)) {
    throw new TypeError("missing required field: source_artifacts");
  }
  const payload = closed(raw, [
    "object", "schema_version", "run_id", "benchmark_family_id", "feed_id", "source_artifacts",
    "parser_id", "parser_version", "started_at", "completed_at", "harness_version",
    "environment_digest", "scorer_version", "trial_policy", "adapter_metadata",
  ]);
  envelope(payload, "run_provenance");
  const started = timestamp(payload.started_at, "started_at");
  const completed = timestamp(payload.completed_at, "completed_at");
  if (completed < started) {
    throw new TypeError("completed_at must be on or after started_at");
  }
  if (!Array.isArray(payload.source_artifacts) || payload.source_artifacts.length === 0) {
    throw new TypeError("source_artifacts must be a non-empty array");
  }
  const sourceArtifactsMutable = payload.source_artifacts.map((item) => {
    const input = closed(item, ["role", "source_artifact_id"]);
    return Object.freeze({
      role: patternString(input.role, /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/, "artifact input role"),
      source_artifact_id: patternString(input.source_artifact_id, artifactIdPattern, "source_artifact_id"),
    });
  });
  const sourceArtifacts = Object.freeze(sourceArtifactsMutable) as unknown as readonly [
    RunInputArtifactV1,
    ...RunInputArtifactV1[],
  ];
  const roles = sourceArtifacts.map((item) => item.role);
  const artifactIds = sourceArtifacts.map((item) => item.source_artifact_id);
  if (roles.some((role, index) => role !== [...roles].sort()[index])) {
    throw new TypeError("source_artifacts must be sorted by role");
  }
  if (new Set(roles).size !== roles.length || new Set(artifactIds).size !== artifactIds.length) {
    throw new TypeError("source_artifact roles and IDs must be unique");
  }
  if (roles.filter((role) => role === "primary").length !== 1) {
    throw new TypeError("source_artifacts must contain exactly one primary role");
  }
  return {
    object: "run_provenance",
    schema_version: "1",
    run_id: nonEmptyString(payload.run_id, "run_id"),
    benchmark_family_id: nonEmptyString(payload.benchmark_family_id, "benchmark_family_id"),
    feed_id: nonEmptyString(payload.feed_id, "feed_id"),
    source_artifacts: sourceArtifacts,
    parser_id: nonEmptyString(payload.parser_id, "parser_id"),
    parser_version: nonEmptyString(payload.parser_version, "parser_version"),
    started_at: started,
    completed_at: completed,
    harness_version: nullableString(payload.harness_version, "harness_version"),
    environment_digest: nullableString(payload.environment_digest, "environment_digest"),
    scorer_version: nullableString(payload.scorer_version, "scorer_version"),
    trial_policy: payload.trial_policy === null ? null : parseTrialPolicy(payload.trial_policy),
    adapter_metadata: payload.adapter_metadata === null ? null : parseAdapterMetadata(payload.adapter_metadata),
  };
}

export function parseObservationV1(value: unknown): ObservationV1 {
  const payload = closed(value, [
    "object", "schema_version", "observation_id", "evaluated_configuration_id", "metric", "uncertainty", "provenance",
  ]);
  envelope(payload, "observation");
  const metric = parseMetric(payload.metric);
  const uncertainty = parseUncertainty(payload.uncertainty);
  if (metric.kind === "rank_only" && uncertainty.kind !== "unknown") {
    throw new TypeError("rank_only observations require unknown uncertainty");
  }
  if (uncertainty.kind === "interval" && "value" in metric) {
    if (compareDecimals(uncertainty.low, metric.value) > 0 || compareDecimals(metric.value, uncertainty.high) > 0) {
      throw new TypeError("uncertainty interval must contain metric value");
    }
  }
  return {
    object: "observation",
    schema_version: "1",
    observation_id: patternString(payload.observation_id, observationIdPattern, "observation_id"),
    evaluated_configuration_id: patternString(payload.evaluated_configuration_id, configurationIdPattern, "evaluated_configuration_id"),
    metric,
    uncertainty,
    provenance: parseRunProvenanceV1(payload.provenance),
  };
}

export function parseConfigurationPassportV1(value: unknown): ConfigurationPassportV1 {
  const payload = closed(value, [
    "object", "schema_version", "entity_kind", "canonical_name", "revision", "interaction_policy",
    "configuration_passport_class", "harness", "scaffold", "tools", "quantization",
    "system_prompt_policy", "environment",
  ]);
  envelope(payload, "configuration_passport");
  const identity = parseIdentity(payload);
  const passport: ConfigurationPassportV1 = {
    object: "configuration_passport",
    schema_version: "1",
    ...identity,
    canonical_name: nonEmptyString(payload.canonical_name, "canonical_name"),
    revision: nonEmptyString(payload.revision, "revision"),
    harness: nullableString(payload.harness, "harness"),
    scaffold: nullableString(payload.scaffold, "scaffold"),
    tools: normalizedStringSet(payload.tools, "tools", true),
    quantization: nullableString(payload.quantization, "quantization"),
    system_prompt_policy: nullableString(payload.system_prompt_policy, "system_prompt_policy"),
    environment: nullableString(payload.environment, "environment"),
  };
  if (passport.entity_kind === "agent_system") {
    nonEmptyString(passport.harness, "harness");
    nonEmptyString(passport.scaffold, "scaffold");
  }
  return passport;
}

export async function parseEvaluatedConfigurationV1(value: unknown): Promise<EvaluatedConfigurationV1> {
  const payload = closed(value, ["object", "schema_version", "evaluated_configuration_id", "passport"]);
  envelope(payload, "evaluated_configuration");
  const passport = parseConfigurationPassportV1(payload.passport);
  const identifier = patternString(payload.evaluated_configuration_id, configurationIdPattern, "evaluated_configuration_id");
  if (identifier !== await evaluatedConfigurationId(passport)) {
    throw new TypeError("evaluated_configuration_id must hash the exact passport");
  }
  return { object: "evaluated_configuration", schema_version: "1", evaluated_configuration_id: identifier, passport };
}

export function parseServingOfferV1(value: unknown): ServingOfferV1 {
  const payload = closed(value, [
    "object", "schema_version", "serving_offer_id", "provider_id", "sku", "region", "context", "availability", "pricing",
  ]);
  envelope(payload, "serving_offer");
  return {
    object: "serving_offer",
    schema_version: "1",
    serving_offer_id: prefixString(payload.serving_offer_id, "offer_", "serving_offer_id"),
    provider_id: nonEmptyString(payload.provider_id, "provider_id"),
    sku: nonEmptyString(payload.sku, "sku"),
    region: nonEmptyString(payload.region, "region"),
    context: parseContextFact(payload.context),
    availability: parseAvailabilityFact(payload.availability),
    pricing: parsePricingScheduleFactV1(payload.pricing),
  };
}

const queryOptional = [
  "via", "provider_ids", "api", "reasoning_effort", "regions", "minimum_context_tokens", "usage_profile",
] as const;
const ppm = 1_000_000;

/** Validate and normalize a query: only sent fields survive, set filters sort, `object` is always present. */
export function parseDecisionQueryV2(value: unknown): DecisionQueryV2 {
  const payload = closed(value, ["schema_version", "cell_id", "objective"], ["object", ...queryOptional]);
  envelope({ object: "decision_query", ...payload }, "decision_query", "2");
  for (const name of queryOptional) {
    if (name in payload && payload[name] === null) {
      throw new TypeError(`${name} must not be null; omit it instead`);
    }
  }
  const query: DecisionQueryV2 = {
    object: "decision_query",
    schema_version: "2",
    cell_id: nonEmptyString(payload.cell_id, "cell_id"),
    objective: enumValue(payload.objective, DECISION_OBJECTIVES, "objective"),
  };
  if ("via" in payload) query.via = patternString(payload.via, /^[a-z0-9][a-z0-9-]*$/, "via");
  if ("provider_ids" in payload) query.provider_ids = normalizedStringSet(payload.provider_ids, "provider_ids");
  if ("api" in payload) query.api = enumValue(payload.api, DECISION_APIS, "api");
  if ("reasoning_effort" in payload) query.reasoning_effort = enumValue(payload.reasoning_effort, REASONING_EFFORTS, "reasoning_effort");
  if ("regions" in payload) query.regions = normalizedStringSet(payload.regions, "regions");
  if ("minimum_context_tokens" in payload) query.minimum_context_tokens = safeInteger(payload.minimum_context_tokens, "minimum_context_tokens", 1);
  if ("usage_profile" in payload) query.usage_profile = parseUsageProfileV1(payload.usage_profile);
  return query;
}

/** The call surface: the sent `via`, else openai for `provider_ids == ["openai"]`, else openrouter. */
export function resolvedVia(query: DecisionQueryV2): string {
  if (query.via !== undefined) return query.via;
  return query.provider_ids?.length === 1 && query.provider_ids[0] === "openai" ? "openai" : "openrouter";
}

export function decisionUsageFor(query: DecisionQueryV2): DecisionUsageV2 {
  return query.usage_profile === undefined
    ? { basis: "default_agent_task_mix", profile: parseUsageProfileV1(DEFAULT_AGENT_TASK_MIX) }
    : { basis: "caller", profile: query.usage_profile };
}

export async function parseDecisionReceiptV2(value: unknown): Promise<DecisionReceiptV2> {
  const payload = closed(value, ["receipt_id", ...receiptBodyFields]);
  const identifier = patternString(payload.receipt_id, /^receipt_[0-9a-f]{64}$/, "receipt_id");
  const { receipt_id: _ignored, ...rawBody } = payload;
  const body = normalizeReceiptBody(rawBody);
  if (identifier !== `receipt_${await sha256Hex(body)}`) {
    throw new TypeError("receipt_id must hash the full receipt body except receipt_id");
  }
  return { receipt_id: identifier, ...body };
}

const receiptBodyFields = [
  "object", "schema_version", "query", "decided_at", "outcome", "snapshot_ids", "families",
  "selections", "exclusions", "usage_profile", "abstain_reasons",
];

function normalizeReceiptBody(value: unknown): Omit<DecisionReceiptV2, "receipt_id"> {
  const payload = closed(value, receiptBodyFields);
  envelope(payload, "decision_receipt", "2");
  const query = parseDecisionQueryV2(payload.query);
  const selections = array(payload.selections, "selections").map(parseSelection);
  const configurations = selections.map((row) => `${row.serving_offer_id}|${row.reasoning_effort}`);
  if (new Set(configurations).size !== configurations.length) {
    throw new TypeError("selections must not repeat a (serving_offer_id, reasoning_effort) configuration");
  }
  const body: Omit<DecisionReceiptV2, "receipt_id"> = {
    object: "decision_receipt",
    schema_version: "2",
    query,
    decided_at: timestamp(payload.decided_at, "decided_at"),
    outcome: enumValue(payload.outcome, ["pick", "abstain"] as const, "outcome"),
    snapshot_ids: normalizedStringSet(payload.snapshot_ids, "snapshot_ids", true)
      .map((item) => patternString(item, /^explorer_.+$/, "snapshot_ids item")),
    families: normalizeRecords(array(payload.families, "families").map(parseFamily), (row) => [row.family_id], "families"),
    selections,
    exclusions: normalizeRecords(
      array(payload.exclusions, "exclusions").map(parseExclusion),
      (row) => [row.model_key, row.reasoning_effort ?? "", row.code],
      "exclusions",
    ),
    usage_profile: parseUsage(payload.usage_profile),
    abstain_reasons: normalizedStringSet(payload.abstain_reasons, "abstain_reasons", true)
      .map((item) => enumValue(item, ABSTAIN_REASONS, "abstain_reasons item")),
  };
  if (canonicalJson(body.usage_profile) !== canonicalJson(decisionUsageFor(query))) {
    throw new TypeError("usage_profile must echo the query's profile (caller) or the default agent task mix");
  }
  if (body.outcome === "pick") validatePick(body);
  else if (body.selections.length || !body.abstain_reasons.length) {
    throw new TypeError("abstain carries no selection and at least one abstain reason");
  }
  return body;
}

function validatePick(body: Omit<DecisionReceiptV2, "receipt_id">): void {
  const { query, selections } = body;
  if (!selections.length || body.abstain_reasons.length) {
    throw new TypeError("pick carries at least one selection and no abstain reason");
  }
  if (!body.snapshot_ids.length) throw new TypeError("pick must cite the explorer snapshots it ranked");
  if (query.reasoning_effort !== undefined && selections.some((row) => row.reasoning_effort !== query.reasoning_effort)) {
    throw new TypeError("a pinned reasoning_effort admits only configurations at that level");
  }
  if (query.api !== undefined && selections.some((row) => row.api !== query.api)) {
    throw new TypeError("every selection must use the query's api");
  }
  if (query.provider_ids !== undefined && selections.some((row) => !query.provider_ids!.includes(row.provider_id))) {
    throw new TypeError("every selection must come from the query's provider_ids");
  }
  const pick = selections[0];
  if (query.objective === "lowest_cost_within_top_set") {
    const costs = selections.map((row) => row.projected_cost_microusd);
    if (costs.some((cost) => cost === null)) {
      throw new TypeError("lowest_cost_within_top_set selects priced configurations only");
    }
    if (pick.projected_cost_microusd !== Math.min(...(costs as number[]))) {
      throw new TypeError("lowest_cost_within_top_set picks the cheapest configuration of the band");
    }
  } else if (pick.capability_ratio_ppm !== Math.max(...selections.map((row) => row.capability_ratio_ppm))) {
    throw new TypeError("capability_top_set picks the highest-scoring configuration");
  }
}

function parseFamily(value: unknown): DecisionFamilyV2 {
  const payload = closed(value, ["family_id", "lock_status", "weight_ppm", "stale_at"]);
  return {
    family_id: nonEmptyString(payload.family_id, "family_id"),
    lock_status: enumValue(payload.lock_status, LOCK_STATUSES, "lock_status"),
    weight_ppm: safeInteger(payload.weight_ppm, "weight_ppm", 0),
    stale_at: payload.stale_at === null ? null : timestamp(payload.stale_at, "stale_at"),
  };
}

function parseSelection(value: unknown): DecisionSelectionV2 {
  const payload = closed(value, [
    "model_id", "display_name", "provider_id", "serving_offer_id", "reasoning_effort", "api",
    "capability_ratio_ppm", "family_coverage", "price", "effort_multiplier", "projected_cost_microusd",
    "latency_p50_ms", "caveats",
  ]);
  const price = closed(payload.price, [
    "input_microusd_per_million", "cached_input_microusd_per_million", "output_microusd_per_million",
  ]);
  const selection: DecisionSelectionV2 = {
    model_id: nonEmptyString(payload.model_id, "model_id"),
    display_name: nonEmptyString(payload.display_name, "display_name"),
    provider_id: nonEmptyString(payload.provider_id, "provider_id"),
    serving_offer_id: nonEmptyString(payload.serving_offer_id, "serving_offer_id"),
    reasoning_effort: enumValue(payload.reasoning_effort, REASONING_EFFORTS, "reasoning_effort"),
    api: enumValue(payload.api, DECISION_APIS, "api"),
    capability_ratio_ppm: safeInteger(payload.capability_ratio_ppm, "capability_ratio_ppm", 0),
    family_coverage: safeInteger(payload.family_coverage, "family_coverage", 1),
    price: {
      input_microusd_per_million: nullableSafeInteger(price.input_microusd_per_million, "input_microusd_per_million", 0),
      cached_input_microusd_per_million: nullableSafeInteger(price.cached_input_microusd_per_million, "cached_input_microusd_per_million", 0),
      output_microusd_per_million: nullableSafeInteger(price.output_microusd_per_million, "output_microusd_per_million", 0),
    },
    effort_multiplier: payload.effort_multiplier === null ? null : parseMultiplier(payload.effort_multiplier),
    projected_cost_microusd: nullableSafeInteger(payload.projected_cost_microusd, "projected_cost_microusd", 0),
    latency_p50_ms: nullableSafeInteger(payload.latency_p50_ms, "latency_p50_ms", 0),
    caveats: normalizeRecords(array(payload.caveats, "caveats").map(parseCaveat), (row) => [row.code], "caveats"),
  };
  if (selection.capability_ratio_ppm > ppm) throw new TypeError("capability_ratio_ppm must not exceed 1000000");
  const unmeasured = selection.caveats.some((row) => row.code === "cost_unmeasured");
  if ((selection.projected_cost_microusd === null) !== unmeasured) {
    throw new TypeError("cost_unmeasured caveat is required exactly when projected_cost_microusd is null");
  }
  if (selection.projected_cost_microusd !== null && selection.effort_multiplier === null) {
    throw new TypeError("a priced selection needs its effort_multiplier");
  }
  for (const caveat of selection.caveats) {
    if (caveat.code === "effort_substituted" && caveat.measured_effort === selection.reasoning_effort) {
      throw new TypeError("effort_substituted must name a measured effort other than the selection's");
    }
  }
  return selection;
}

function parseMultiplier(value: unknown): EffortMultiplierV2 {
  const payload = closed(value, ["multiplier_ppm", "source"]);
  const multiplier = {
    multiplier_ppm: safeInteger(payload.multiplier_ppm, "multiplier_ppm", 0),
    source: nonEmptyString(payload.source, "source"),
  };
  if (multiplier.source === "comparison_level" && multiplier.multiplier_ppm !== ppm) {
    throw new TypeError("a comparison_level multiplier must be exactly 1 (1000000 ppm)");
  }
  return multiplier;
}

function parseCaveat(value: unknown): DecisionCaveatV2 {
  const code = record(value, "caveat").code;
  if (code === "effort_substituted") {
    const payload = closed(value, ["code", "measured_effort", "gap_ppm"]);
    return {
      code,
      measured_effort: enumValue(payload.measured_effort, REASONING_EFFORTS, "measured_effort"),
      gap_ppm: safeInteger(payload.gap_ppm, "gap_ppm", 0),
    };
  }
  const payload = closed(value, ["code"]);
  return { code: enumValue(payload.code, ["cost_unmeasured"] as const, "code") };
}

function parseExclusion(value: unknown): DecisionExclusionV2 {
  const payload = closed(value, ["model_key", "code"], ["reasoning_effort", "detail"]);
  const exclusion: DecisionExclusionV2 = {
    model_key: nonEmptyString(payload.model_key, "model_key"),
    code: enumValue(payload.code, EXCLUSION_CODES, "code"),
  };
  if ("reasoning_effort" in payload) exclusion.reasoning_effort = enumValue(payload.reasoning_effort, REASONING_EFFORTS, "reasoning_effort");
  if ("detail" in payload) {
    if (typeof payload.detail !== "string") throw new TypeError("detail must be a string");
    exclusion.detail = payload.detail;
  }
  return exclusion;
}

function parseUsage(value: unknown): DecisionUsageV2 {
  const payload = closed(value, ["basis", "profile"]);
  return {
    basis: enumValue(payload.basis, ["caller", "default_agent_task_mix"] as const, "basis"),
    profile: parseUsageProfileV1(payload.profile),
  };
}

function parseTrialPolicy(value: unknown): TrialPolicyV1 {
  const payload = closed(value, ["attempts_per_item", "seed_strategy", "seed"]);
  const policy: TrialPolicyV1 = {
    attempts_per_item: safeInteger(payload.attempts_per_item, "attempts_per_item", 1),
    seed_strategy: enumValue(payload.seed_strategy, ["fixed", "derived", "upstream"] as const, "seed_strategy"),
    seed: payload.seed === null ? null : safeInteger(payload.seed, "seed"),
  };
  if (policy.seed_strategy === "fixed" && policy.seed === null) throw new TypeError("seed is required for fixed seed_strategy");
  if (policy.seed_strategy !== "fixed" && policy.seed !== null) throw new TypeError("seed must be null unless seed_strategy is fixed");
  return policy;
}

function parseAdapterMetadata(value: unknown): AdapterMetadataV1 {
  const payload = closed(value, ["schema_version", "payload"]);
  const openPayload = record(payload.payload, "adapter_metadata.payload");
  const copied = JSON.parse(canonicalJson(openPayload)) as Record<string, unknown>;
  return { schema_version: nonEmptyString(payload.schema_version, "schema_version"), payload: copied };
}

function parseMetric(value: unknown): MetricV1 {
  const input = record(value, "metric");
  switch (input.kind) {
    case "proportion": {
      const payload = closed(input, ["kind", "value", "numerator", "denominator"]);
      const metric: ProportionMetricV1 = {
        kind: "proportion",
        value: unitDecimal(payload.value, "value"),
        numerator: nullableSafeInteger(payload.numerator, "numerator", 0),
        denominator: nullableSafeInteger(payload.denominator, "denominator", 1),
      };
      pairedCounts(metric.numerator, metric.denominator, "numerator", "denominator");
      if (metric.numerator !== null && !decimalMatchesRoundedRatio(metric.value, metric.numerator, metric.denominator!)) {
        throw new TypeError("value must equal numerator / denominator rounded half-even to its declared decimal scale");
      }
      return metric;
    }
    case "continuous": {
      const payload = closed(input, ["kind", "value", "unit", "n_items"]);
      return {
        kind: "continuous",
        value: decimal(payload.value, "value"),
        unit: nonEmptyString(payload.unit, "unit"),
        n_items: nullableSafeInteger(payload.n_items, "n_items", 1),
      };
    }
    case "pass_at_k": {
      const payload = closed(input, ["kind", "value", "k", "successful_items", "evaluated_items"]);
      const metric: PassAtKMetricV1 = {
        kind: "pass_at_k",
        value: unitDecimal(payload.value, "value"),
        k: safeInteger(payload.k, "k", 1),
        successful_items: nullableSafeInteger(payload.successful_items, "successful_items", 0),
        evaluated_items: nullableSafeInteger(payload.evaluated_items, "evaluated_items", 1),
      };
      pairedCounts(metric.successful_items, metric.evaluated_items, "successful_items", "evaluated_items");
      if (metric.successful_items !== null && metric.successful_items > metric.evaluated_items!) {
        throw new TypeError("successful_items must not exceed evaluated_items");
      }
      return metric;
    }
    case "pairwise_preference": {
      const payload = closed(input, ["kind", "value", "scale", "comparison_count"]);
      const scale = enumValue(payload.scale, ["probability", "elo", "margin"] as const, "scale");
      return {
        kind: "pairwise_preference",
        value: scale === "probability" ? unitDecimal(payload.value, "value") : decimal(payload.value, "value"),
        scale,
        comparison_count: nullableSafeInteger(payload.comparison_count, "comparison_count", 1),
      };
    }
    case "rank_only": {
      const payload = closed(input, ["kind", "rank", "candidate_count"]);
      const metric: RankOnlyMetricV1 = {
        kind: "rank_only",
        rank: safeInteger(payload.rank, "rank", 1),
        candidate_count: nullableSafeInteger(payload.candidate_count, "candidate_count", 1),
      };
      if (metric.candidate_count !== null && metric.rank > metric.candidate_count) {
        throw new TypeError("rank must not exceed candidate_count");
      }
      return metric;
    }
    default:
      throw new TypeError("metric.kind must be one of the five supported metric kinds");
  }
}

function parseUncertainty(value: unknown): UncertaintyV1 {
  const input = record(value, "uncertainty");
  switch (input.kind) {
    case "unknown":
      closed(input, ["kind"]);
      return { kind: "unknown" };
    case "standard_error": {
      const payload = closed(input, ["kind", "value"]);
      const result = decimal(payload.value, "value");
      if (result.startsWith("-")) throw new TypeError("standard error must be nonnegative");
      return { kind: "standard_error", value: result };
    }
    case "interval": {
      const payload = closed(input, ["kind", "low", "high", "confidence_level", "method"]);
      const uncertainty: IntervalUncertaintyV1 = {
        kind: "interval",
        low: decimal(payload.low, "low"),
        high: decimal(payload.high, "high"),
        confidence_level: positiveUnitDecimal(payload.confidence_level, "confidence_level"),
        method: enumValue(payload.method, [
          "reported", "bootstrap_percentile", "bootstrap_bca", "clopper_pearson", "wilson",
          "normal_approximation", "credible_interval",
        ] as const, "method"),
      };
      if (compareDecimals(uncertainty.low, uncertainty.high) > 0) throw new TypeError("low must be <= high");
      return uncertainty;
    }
    default:
      throw new TypeError("uncertainty.kind must be unknown, standard_error, or interval");
  }
}

function parseContextFact(value: unknown): ContextFactV1 {
  const payload = closed(value, ["context_window_tokens", "observed_at", "expires_at", "source_artifact_id"]);
  return {
    context_window_tokens: safeInteger(payload.context_window_tokens, "context_window_tokens", 1),
    ...datedFact(payload),
  };
}

function parseAvailabilityFact(value: unknown): AvailabilityFactV1 {
  const payload = closed(value, ["status", "observed_at", "expires_at", "source_artifact_id"]);
  return {
    status: enumValue(payload.status, ["available", "limited", "unavailable"] as const, "status"),
    ...datedFact(payload),
  };
}

export function parseUsageProfileV1(value: unknown): UsageProfileV1 {
  const payload = closed(value, [
    "basis", "uncached_input_tokens", "cached_read_tokens", "output_tokens",
    "cache_writes", "cache_storage_token_seconds",
  ]);
  const cacheWrites = normalizeTtlRecords(
    array(payload.cache_writes, "cache_writes").map((row) => {
      const item = closed(row, ["ttl_seconds", "tokens"]);
      return {
        ttl_seconds: safeInteger(item.ttl_seconds, "ttl_seconds", 1),
        tokens: safeInteger(item.tokens, "tokens", 1),
      };
    }),
    "cache_writes",
  );
  const usage = {
    basis: enumValue(payload.basis, ["measured", "estimated"] as const, "basis"),
    uncached_input_tokens: safeInteger(payload.uncached_input_tokens, "uncached_input_tokens", 0),
    cached_read_tokens: safeInteger(payload.cached_read_tokens, "cached_read_tokens", 0),
    output_tokens: safeInteger(payload.output_tokens, "output_tokens", 0),
    cache_writes: cacheWrites,
    cache_storage_token_seconds: safeInteger(
      payload.cache_storage_token_seconds,
      "cache_storage_token_seconds",
      0,
    ),
  };
  if (
    usage.uncached_input_tokens === 0
    && usage.cached_read_tokens === 0
    && usage.output_tokens === 0
    && usage.cache_writes.length === 0
  ) {
    throw new TypeError("usage profile must describe a non-zero workload");
  }
  return usage;
}

export function parsePricingScheduleFactV1(value: unknown): PricingScheduleFactV1 {
  const payload = closed(value, [
    "uncached_input_microusd_per_million_tokens", "cached_read_microusd_per_million_tokens",
    "output_microusd_per_million_tokens", "cache_write_rates",
    "cache_storage_microusd_per_million_token_hours", "observed_at", "effective_at",
    "expires_at", "source_artifact_id",
  ]);
  const fact = datedFact(payload);
  const effectiveAt = timestamp(payload.effective_at, "effective_at");
  if (fact.expires_at <= effectiveAt) throw new TypeError("expires_at must be after effective_at");
  const cacheWriteRates = normalizeTtlRecords(
    array(payload.cache_write_rates, "cache_write_rates").map((row) => {
      const item = closed(row, ["ttl_seconds", "microusd_per_million_tokens"]);
      return {
        ttl_seconds: safeInteger(item.ttl_seconds, "ttl_seconds", 1),
        microusd_per_million_tokens: safeInteger(
          item.microusd_per_million_tokens,
          "microusd_per_million_tokens",
          0,
        ),
      };
    }),
    "cache_write_rates",
  );
  return {
    uncached_input_microusd_per_million_tokens: safeInteger(
      payload.uncached_input_microusd_per_million_tokens,
      "uncached_input_microusd_per_million_tokens",
      0,
    ),
    cached_read_microusd_per_million_tokens: nullableSafeInteger(
      payload.cached_read_microusd_per_million_tokens,
      "cached_read_microusd_per_million_tokens",
      0,
    ),
    output_microusd_per_million_tokens: safeInteger(payload.output_microusd_per_million_tokens, "output_microusd_per_million_tokens", 0),
    cache_write_rates: cacheWriteRates,
    cache_storage_microusd_per_million_token_hours: nullableSafeInteger(
      payload.cache_storage_microusd_per_million_token_hours,
      "cache_storage_microusd_per_million_token_hours",
      0,
    ),
    effective_at: effectiveAt,
    ...fact,
  };
}

function normalizeTtlRecords<T extends { ttl_seconds: number }>(values: T[], name: string): T[] {
  const ttls = values.map((row) => row.ttl_seconds);
  if (new Set(ttls).size !== ttls.length) throw new TypeError(`${name} must be unique`);
  return [...values].sort((left, right) => {
    const leftKey = canonicalJson([left.ttl_seconds]);
    const rightKey = canonicalJson([right.ttl_seconds]);
    return leftKey < rightKey ? -1 : leftKey > rightKey ? 1 : 0;
  });
}

function datedFact(payload: Record<string, unknown>): DatedFactV1 {
  const observed = timestamp(payload.observed_at, "observed_at");
  const expires = timestamp(payload.expires_at, "expires_at");
  if (expires <= observed) throw new TypeError("expires_at must be after observed_at");
  return {
    observed_at: observed,
    expires_at: expires,
    source_artifact_id: patternString(payload.source_artifact_id, artifactIdPattern, "source_artifact_id"),
  };
}

/** Exact cost of `usage` under `pricing` (rounded up), or null when a needed rate is missing. */
export function projectedCostMicrousd(
  usage: UsageProfileV1,
  pricing: PricingScheduleFactV1,
): number | null {
  const normalizedUsage = parseUsageProfileV1(usage);
  const normalizedPricing = parsePricingScheduleFactV1(pricing);
  if (
    normalizedUsage.cached_read_tokens !== 0
    && normalizedPricing.cached_read_microusd_per_million_tokens === null
  ) {
    return null;
  }
  const cacheWriteRates = new Map(
    normalizedPricing.cache_write_rates.map((row) => [row.ttl_seconds, row.microusd_per_million_tokens]),
  );
  if (normalizedUsage.cache_writes.some((row) => !cacheWriteRates.has(row.ttl_seconds))) return null;
  if (
    normalizedUsage.cache_storage_token_seconds !== 0
    && normalizedPricing.cache_storage_microusd_per_million_token_hours === null
  ) {
    return null;
  }
  const cachedReadCostNumerator = normalizedUsage.cached_read_tokens === 0
    ? 0n
    : BigInt(normalizedUsage.cached_read_tokens)
      * BigInt(normalizedPricing.cached_read_microusd_per_million_tokens!);
  const storageCostNumerator = normalizedUsage.cache_storage_token_seconds === 0
    ? 0n
    : BigInt(normalizedUsage.cache_storage_token_seconds)
      * BigInt(normalizedPricing.cache_storage_microusd_per_million_token_hours!);
  const tokenRateMicrousd =
    BigInt(normalizedUsage.uncached_input_tokens)
      * BigInt(normalizedPricing.uncached_input_microusd_per_million_tokens)
    + cachedReadCostNumerator
    + BigInt(normalizedUsage.output_tokens)
      * BigInt(normalizedPricing.output_microusd_per_million_tokens)
    + normalizedUsage.cache_writes.reduce(
      (total, row) => total
        + BigInt(row.tokens) * BigInt(cacheWriteRates.get(row.ttl_seconds)!),
      0n,
    );
  const numerator = tokenRateMicrousd * 3_600n
    + storageCostNumerator;
  const divisor = 3_600_000_000n;
  const value = (numerator + divisor - 1n) / divisor;
  const result = Number(value);
  if (!Number.isSafeInteger(result)) throw new TypeError("computed projected cost must be a safe integer");
  return result;
}

function parseIdentity(payload: Record<string, unknown>): {
  entity_kind: EntityKind;
  interaction_policy: InteractionPolicy;
  configuration_passport_class: ConfigurationPassportClass;
} {
  const entityKind = enumValue(payload.entity_kind, entityKinds, "entity_kind");
  const interactionPolicy = enumValue(payload.interaction_policy, interactionPolicies, "interaction_policy");
  const passportClass = enumValue(payload.configuration_passport_class, passportClasses, "configuration_passport_class");
  if (!identityTriples.has(`${entityKind}|${interactionPolicy}|${passportClass}`)) {
    throw new TypeError("entity_kind, interaction_policy, and configuration_passport_class must be a resolved identity triple");
  }
  return { entity_kind: entityKind, interaction_policy: interactionPolicy, configuration_passport_class: passportClass };
}

function canonicalValue(value: unknown, path: string): unknown {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    if (typeof value === "string") validUnicode(value, path);
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError(`${path} must be finite`);
    if (!Number.isInteger(value)) throw new TypeError(`${path} must not be a float in restricted JCS`);
    if (!Number.isSafeInteger(value)) throw new TypeError(`${path} must be a safe integer`);
    return Object.is(value, -0) ? 0 : value;
  }
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      if (!(index in value)) throw new TypeError(`${path}[${index}] must not be a sparse array hole`);
    }
    return value.map((item, index) => canonicalValue(item, `${path}[${index}]`));
  }
  if (isPlainRecord(value)) {
    const result: Record<string, unknown> = {};
    for (const key of Object.keys(value).sort()) {
      validUnicode(key, `${path} key`);
      result[key] = canonicalValue(value[key], `${path}.${key}`);
    }
    return result;
  }
  throw new TypeError(`${path} has unsupported JSON type ${typeof value}`);
}

function validUnicode(value: string, path: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) throw new TypeError(`${path} contains a lone surrogate`);
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      throw new TypeError(`${path} contains a lone surrogate`);
    }
  }
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function record(value: unknown, name: string): Record<string, unknown> {
  if (!isPlainRecord(value)) throw new TypeError(`${name} must be a JSON object`);
  return value;
}

function closed(value: unknown, required: string[], optional: string[] = []): Record<string, unknown> {
  const payload = record(value, "contract value");
  for (const name of required) if (!(name in payload)) throw new TypeError(`missing required field: ${name}`);
  const allowed = new Set([...required, ...optional]);
  const unknown = Object.keys(payload).filter((key) => !allowed.has(key)).sort();
  if (unknown.length) throw new TypeError(`unknown fields: ${unknown.join(", ")}`);
  return payload;
}

function envelope(payload: Record<string, unknown>, objectName: string, schemaVersion = "1"): void {
  if (payload.object !== objectName) throw new TypeError(`object must be ${objectName}`);
  if (payload.schema_version !== schemaVersion) throw new TypeError(`schema_version must be ${schemaVersion}`);
}

function nonEmptyString(value: unknown, name: string): string {
  if (typeof value !== "string" || value.length === 0) throw new TypeError(`${name} must be a non-empty string`);
  validUnicode(value, name);
  return value;
}

function nullableString(value: unknown, name: string): string | null {
  return value === null ? null : nonEmptyString(value, name);
}

function patternString(value: unknown, pattern: RegExp, name: string): string {
  const result = nonEmptyString(value, name);
  if (!pattern.test(result)) throw new TypeError(`${name} has an invalid format`);
  return result;
}

function prefixString(value: unknown, prefix: string, name: string): string {
  const result = nonEmptyString(value, name);
  if (!result.startsWith(prefix)) throw new TypeError(`${name} must start with ${prefix}`);
  return result;
}

function enumValue<const T extends readonly string[]>(value: unknown, allowed: T, name: string): T[number] {
  if (typeof value !== "string" || !allowed.includes(value)) throw new TypeError(`${name} must be one of ${allowed.join(", ")}`);
  return value as T[number];
}

function safeInteger(value: unknown, name: string, minimum?: number): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  if (minimum !== undefined && value < minimum) throw new TypeError(`${name} must be >= ${minimum}`);
  return value;
}

function nullableSafeInteger(value: unknown, name: string, minimum?: number): number | null {
  return value === null ? null : safeInteger(value, name, minimum);
}

function timestamp(value: unknown, name: string): string {
  const result = patternString(value, timestampPattern, name);
  const instant = Date.parse(result);
  if (result.startsWith("0000-") || !Number.isFinite(instant) || new Date(instant).toISOString().replace(".000Z", "Z") !== result) {
    throw new TypeError(`${name} must be a valid UTC timestamp`);
  }
  return result;
}

function httpUrl(value: unknown, name: string): string {
  const result = nonEmptyString(value, name);
  const parsed = new URL(result);
  if (!["http:", "https:"].includes(parsed.protocol) || !parsed.host || parsed.username || parsed.password || parsed.hash) {
    throw new TypeError(`${name} must be a canonical public http(s) URL without credentials or fragment`);
  }
  return result;
}

function array(value: unknown, name: string): unknown[] {
  if (!Array.isArray(value)) throw new TypeError(`${name} must be an array`);
  return value;
}

function normalizedStringSet(value: unknown, name: string, allowEmpty = false): string[] {
  const values = array(value, name).map((item) => nonEmptyString(item, `${name} item`));
  if (!allowEmpty && values.length === 0) throw new TypeError(`${name} must not be empty`);
  if (new Set(values).size !== values.length) throw new TypeError(`${name} must be unique`);
  return values.sort();
}

function normalizeRecords<T>(values: T[], key: (value: T) => readonly string[] | string, name: string): T[] {
  const token = (value: T): string => canonicalJson(
    typeof key(value) === "string" ? [key(value)] : key(value),
  );
  const keys = values.map(token);
  if (new Set(keys).size !== keys.length) throw new TypeError(`${name} must be unique`);
  return [...values].sort((left, right) => token(left) < token(right) ? -1 : token(left) > token(right) ? 1 : 0);
}

function decimal(value: unknown, name: string): string {
  if (typeof value !== "string" || value.length > 128 || !decimalPattern.test(value)) {
    throw new TypeError(`${name} must be a canonical decimal string`);
  }
  return value;
}

function unitDecimal(value: unknown, name: string): string {
  const result = decimal(value, name);
  if (compareDecimals(result, "0") < 0 || compareDecimals(result, "1") > 0) throw new TypeError(`${name} must be in [0, 1]`);
  return result;
}

function positiveUnitDecimal(value: unknown, name: string): string {
  const result = unitDecimal(value, name);
  if (result === "0") throw new TypeError(`${name} must be in (0, 1]`);
  return result;
}

function compareDecimals(left: string, right: string): number {
  const first = decimalParts(left);
  const second = decimalParts(right);
  const scale = Math.max(first.scale, second.scale);
  const firstScaled = first.number * 10n ** BigInt(scale - first.scale);
  const secondScaled = second.number * 10n ** BigInt(scale - second.scale);
  return firstScaled < secondScaled ? -1 : firstScaled > secondScaled ? 1 : 0;
}

function decimalParts(value: string): { number: bigint; scale: number } {
  decimal(value, "decimal");
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [whole, fraction = ""] = unsigned.split(".");
  const number = BigInt(`${whole}${fraction}`) * (negative ? -1n : 1n);
  return { number, scale: fraction.length };
}

function decimalMatchesRoundedRatio(value: string, numerator: number, denominator: number): boolean {
  const parts = decimalParts(value);
  const exact = parts.number * BigInt(denominator) === BigInt(numerator) * 10n ** BigInt(parts.scale);
  if (!exact && parts.scale < 6) {
    throw new TypeError("value must use at least six fractional digits when counts are not exactly representable");
  }
  const scaledNumerator = BigInt(numerator) * 10n ** BigInt(parts.scale);
  const divisor = BigInt(denominator);
  const quotient = scaledNumerator / divisor;
  const remainder = scaledNumerator % divisor;
  const doubledRemainder = remainder * 2n;
  const rounded = doubledRemainder > divisor || (doubledRemainder === divisor && quotient % 2n !== 0n)
    ? quotient + 1n
    : quotient;
  return parts.number === rounded;
}

function pairedCounts(first: number | null, second: number | null, firstName: string, secondName: string): void {
  if ((first === null) !== (second === null)) throw new TypeError(`${firstName} and ${secondName} must both be integers or both be null`);
  if (first !== null && second !== null && first > second) throw new TypeError(`${firstName} must not exceed ${secondName}`);
}

function setEquals<T>(left: Set<T>, right: Set<T>): boolean {
  return left.size === right.size && [...left].every((value) => right.has(value));
}
