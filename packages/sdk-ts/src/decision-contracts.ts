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

export interface EvaluationToOfferLinkV1 {
  object: "evaluation_to_offer_link";
  schema_version: "1";
  evaluation_to_offer_link_id: string;
  evaluated_configuration_id: string;
  serving_offer_id: string;
  compatibility: "exact" | "incompatible" | "unresolved";
  evidence_basis: "benchmark_exact" | "provider_attested" | "operator_reviewed" | "inferred";
  evidence_source_artifact_id: string;
  observed_at: string;
  expires_at: string;
  review_state: "pending" | "approved" | "rejected";
}

export interface DecisionQueryV1 {
  object: "decision_query";
  schema_version: "1";
  cell_id: string;
  ranking_group_id: string;
  entity_kind: EntityKind;
  interaction_policy: InteractionPolicy;
  configuration_passport_class: ConfigurationPassportClass;
  objective: "capability_top_set" | "lowest_cost_within_top_set";
  provider_ids?: string[];
  regions?: string[];
  minimum_context_tokens?: number;
  usage_profile?: UsageProfileV1;
  zero_cache_sensitivity_usage_profile?: UsageProfileV1;
  monthly_budget_microusd?: number;
}

export interface PublicationSnapshotRefV1 {
  publication_snapshot_id: string;
  ranking_group_id: string;
  manifest_version: string;
  published_at: string;
}

export interface DecisionSelectionV1 {
  evaluated_configuration_id: string;
  serving_offer_id: string | null;
  capability_rank: number;
  projected_monthly_cost_microusd: number | null;
  zero_cache_sensitivity_projected_monthly_cost_microusd: number | null;
}

export interface DecisionExclusionV1 {
  evaluated_configuration_id: string;
  code:
    | "constraints_not_met"
    | "not_in_capability_top_set"
    | "serving_offer_unverified"
    | "evidence_stale"
    | "incompatible_configuration";
  evidence_ids: string[];
}

export interface DecisionFreshnessV1 {
  observed_at: string;
  expires_at: string;
}

export interface DecisionReasonV1 {
  reason_type: "best_when" | "avoid_when";
  code:
    | "strongest_capability_evidence"
    | "within_capability_top_set"
    | "lowest_cost_under_usage_profile"
    | "budget_fit_under_declared_profiles"
    | "provider_constraint_match"
    | "region_constraint_match"
    | "context_requirement_met"
    | "insufficient_evidence"
    | "serving_offer_unverified"
    | "budget_exceeded"
    | "stale_evidence";
  subject_id: string;
  predicate: "eq" | "ne" | "lt" | "lte" | "gt" | "gte" | "within_top_set" | "unavailable";
  axis: "capability" | "monthly_cost" | "context" | "availability" | "freshness" | "provider" | "region";
  observed_value: string;
  unit: "probability" | "score" | "microusd_per_month" | "tokens" | "status" | "timestamp" | "provider_id" | "region_id";
  threshold: string | null;
  evidence_ids: string[];
  freshness: DecisionFreshnessV1;
  caveat_codes: Array<
    | "provider_offer_link_required"
    | "limited_availability"
    | "evidence_near_expiry"
    | "incomplete_family_coverage"
    | "cost_sensitive_to_usage"
  >;
}

export interface DecisionSensitivityV1 {
  scenario: "price_plus_20_percent" | "price_minus_20_percent" | "usage_double" | "leave_one_family_out";
  stable: boolean;
  selected_configuration_ids: string[];
}

export interface ObservationEvidenceV1 {
  kind: "observation";
  evidence_id: string;
  observation: ObservationV1;
}

export interface ServingOfferEvidenceV1 {
  kind: "serving_offer";
  evidence_id: string;
  serving_offer: ServingOfferV1;
}

export interface EvaluationToOfferLinkEvidenceV1 {
  kind: "evaluation_to_offer_link";
  evidence_id: string;
  evaluation_to_offer_link: EvaluationToOfferLinkV1;
}

export type DecisionEvidenceV1 =
  | ObservationEvidenceV1
  | ServingOfferEvidenceV1
  | EvaluationToOfferLinkEvidenceV1;

export type AbstentionReasonV1 =
  | "insufficient_comparable_evidence"
  | "no_eligible_serving_offer"
  | "constraints_eliminate_all_candidates"
  | "evidence_stale"
  | "methodology_unavailable";

export interface DecisionReceiptV1 {
  object: "decision_receipt";
  schema_version: "1";
  receipt_id: string;
  query: DecisionQueryV1;
  publication_snapshot: PublicationSnapshotRefV1;
  methodology_version: string;
  decided_at: string;
  outcome: "top_set" | "abstain";
  selections: DecisionSelectionV1[];
  exclusions: DecisionExclusionV1[];
  reasons: DecisionReasonV1[];
  sensitivity: DecisionSensitivityV1[];
  evidence: DecisionEvidenceV1[];
  freshness: DecisionFreshnessV1;
  abstention_reason: AbstentionReasonV1 | null;
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

export function parseEvaluationToOfferLinkV1(value: unknown): EvaluationToOfferLinkV1 {
  const payload = closed(value, [
    "object", "schema_version", "evaluation_to_offer_link_id", "evaluated_configuration_id",
    "serving_offer_id", "compatibility", "evidence_basis", "evidence_source_artifact_id", "observed_at", "expires_at", "review_state",
  ]);
  envelope(payload, "evaluation_to_offer_link");
  const observed = timestamp(payload.observed_at, "observed_at");
  const expires = timestamp(payload.expires_at, "expires_at");
  if (expires <= observed) {
    throw new TypeError("expires_at must be after observed_at");
  }
  return {
    object: "evaluation_to_offer_link",
    schema_version: "1",
    evaluation_to_offer_link_id: prefixString(payload.evaluation_to_offer_link_id, "link_", "evaluation_to_offer_link_id"),
    evaluated_configuration_id: patternString(payload.evaluated_configuration_id, configurationIdPattern, "evaluated_configuration_id"),
    serving_offer_id: prefixString(payload.serving_offer_id, "offer_", "serving_offer_id"),
    compatibility: enumValue(payload.compatibility, ["exact", "incompatible", "unresolved"] as const, "compatibility"),
    evidence_basis: enumValue(
      payload.evidence_basis,
      ["benchmark_exact", "provider_attested", "operator_reviewed", "inferred"] as const,
      "evidence_basis",
    ),
    evidence_source_artifact_id: patternString(payload.evidence_source_artifact_id, artifactIdPattern, "evidence_source_artifact_id"),
    observed_at: observed,
    expires_at: expires,
    review_state: enumValue(payload.review_state, ["pending", "approved", "rejected"] as const, "review_state"),
  };
}

export function isEvaluationToOfferLinkEligible(link: unknown, asOf: unknown): boolean {
  try {
    return normalizedLinkIsEligible(
      parseEvaluationToOfferLinkV1(link),
      timestamp(asOf, "as_of"),
    );
  } catch {
    return false;
  }
}

export function isServingOfferDecisionEligible(
  offer: unknown,
  link: unknown,
  asOf: unknown,
): boolean {
  try {
    const normalizedOffer = parseServingOfferV1(offer);
    const normalizedLink = parseEvaluationToOfferLinkV1(link);
    const instant = timestamp(asOf, "as_of");
    if (
      normalizedLink.serving_offer_id !== normalizedOffer.serving_offer_id
      || normalizedOffer.availability.status !== "available"
      || !normalizedLinkIsEligible(normalizedLink, instant)
    ) return false;
    return [normalizedOffer.context, normalizedOffer.availability].every(
      (fact) => fact.observed_at <= instant && instant < fact.expires_at,
    ) && normalizedOffer.pricing.observed_at <= instant
      && normalizedOffer.pricing.effective_at <= instant
      && instant < normalizedOffer.pricing.expires_at;
  } catch {
    return false;
  }
}

function normalizedLinkIsEligible(
  link: EvaluationToOfferLinkV1,
  instant: string,
): boolean {
  return link.compatibility === "exact"
    && link.review_state === "approved"
    && link.evidence_basis !== "inferred"
    && link.observed_at <= instant
    && instant < link.expires_at;
}

export function parseDecisionQueryV1(value: unknown): DecisionQueryV1 {
  const required = [
    "object", "schema_version", "cell_id", "ranking_group_id", "entity_kind", "interaction_policy",
    "configuration_passport_class", "objective",
  ];
  const optional = [
    "provider_ids", "regions", "minimum_context_tokens", "usage_profile",
    "zero_cache_sensitivity_usage_profile", "monthly_budget_microusd",
  ];
  const payload = closed(value, required, optional);
  envelope(payload, "decision_query");
  for (const name of optional) {
    if (name in payload && payload[name] === null) {
      throw new TypeError(`${name} must not be null; omit it instead`);
    }
  }
  const query: DecisionQueryV1 = {
    object: "decision_query",
    schema_version: "1",
    cell_id: nonEmptyString(payload.cell_id, "cell_id"),
    ranking_group_id: nonEmptyString(payload.ranking_group_id, "ranking_group_id"),
    ...parseIdentity(payload),
    objective: enumValue(payload.objective, ["capability_top_set", "lowest_cost_within_top_set"] as const, "objective"),
  };
  if ("provider_ids" in payload) query.provider_ids = normalizedStringSet(payload.provider_ids, "provider_ids");
  if ("regions" in payload) query.regions = normalizedStringSet(payload.regions, "regions");
  if ("minimum_context_tokens" in payload) query.minimum_context_tokens = safeInteger(payload.minimum_context_tokens, "minimum_context_tokens", 1);
  if ("usage_profile" in payload) query.usage_profile = parseUsageProfileV1(payload.usage_profile);
  if ("zero_cache_sensitivity_usage_profile" in payload) {
    query.zero_cache_sensitivity_usage_profile = parseUsageProfileV1(payload.zero_cache_sensitivity_usage_profile);
  }
  if ("monthly_budget_microusd" in payload) query.monthly_budget_microusd = safeInteger(payload.monthly_budget_microusd, "monthly_budget_microusd", 0);
  if (query.objective === "lowest_cost_within_top_set" && query.usage_profile === undefined) {
    throw new TypeError("lowest_cost_within_top_set requires usage_profile");
  }
  if (query.monthly_budget_microusd !== undefined && query.usage_profile === undefined) {
    throw new TypeError("monthly_budget_microusd requires usage_profile");
  }
  validateZeroCacheSensitivity(query);
  return query;
}

function validateZeroCacheSensitivity(query: DecisionQueryV1): void {
  const usage = query.usage_profile;
  const sensitivity = query.zero_cache_sensitivity_usage_profile;
  const hasCacheUsage = usage !== undefined && (
    usage.cached_read_tokens !== 0
    || usage.cache_writes.length !== 0
    || usage.cache_storage_token_seconds !== 0
  );
  const required = usage?.basis === "estimated" && hasCacheUsage;
  if (required && sensitivity === undefined) {
    throw new TypeError("estimated cached usage requires zero_cache_sensitivity_usage_profile");
  }
  if (!required && sensitivity !== undefined) {
    const basis = usage?.basis === "measured" ? "measured" : "uncached";
    throw new TypeError(`zero_cache_sensitivity_usage_profile is not allowed for ${basis} usage`);
  }
  if (usage === undefined || sensitivity === undefined) return;
  if (sensitivity.basis !== "estimated") {
    throw new TypeError("zero_cache_sensitivity_usage_profile must be estimated");
  }
  if (
    sensitivity.cached_read_tokens !== 0
    || sensitivity.cache_writes.length !== 0
    || sensitivity.cache_storage_token_seconds !== 0
  ) {
    throw new TypeError("zero_cache_sensitivity_usage_profile must contain no cache usage");
  }
  if (totalInputTokens(sensitivity) !== totalInputTokens(usage)) {
    throw new TypeError("zero_cache_sensitivity_usage_profile must preserve total input tokens");
  }
  if (sensitivity.output_tokens !== usage.output_tokens) {
    throw new TypeError("zero_cache_sensitivity_usage_profile must preserve output tokens");
  }
}

function totalInputTokens(usage: UsageProfileV1): bigint {
  return BigInt(usage.uncached_input_tokens)
    + BigInt(usage.cached_read_tokens)
    + usage.cache_writes.reduce((total, row) => total + BigInt(row.tokens), 0n);
}

export async function parseDecisionReceiptV1(value: unknown): Promise<DecisionReceiptV1> {
  const payload = closed(value, [
    "object", "schema_version", "receipt_id", "query", "publication_snapshot", "methodology_version", "decided_at",
    "outcome", "selections", "exclusions", "reasons", "sensitivity", "evidence", "freshness", "abstention_reason",
  ]);
  envelope(payload, "decision_receipt");
  const identifier = patternString(payload.receipt_id, /^receipt_[0-9a-f]{64}$/, "receipt_id");
  const { receipt_id: _ignored, ...rawBody } = payload;
  const body = normalizeReceiptBody(rawBody);
  if (identifier !== `receipt_${await sha256Hex(body)}`) {
    throw new TypeError("receipt_id must hash the full receipt body except receipt_id");
  }
  return { receipt_id: identifier, ...body };
}

function normalizeReceiptBody(value: unknown): Omit<DecisionReceiptV1, "receipt_id"> {
  const payload = closed(value, [
    "object", "schema_version", "query", "publication_snapshot", "methodology_version", "decided_at",
    "outcome", "selections", "exclusions", "reasons", "sensitivity", "evidence", "freshness", "abstention_reason",
  ]);
  envelope(payload, "decision_receipt");
  const body: Omit<DecisionReceiptV1, "receipt_id"> = {
    object: "decision_receipt",
    schema_version: "1",
    query: parseDecisionQueryV1(payload.query),
    publication_snapshot: parsePublicationSnapshot(payload.publication_snapshot),
    methodology_version: patternString(payload.methodology_version, /^\d{4}-\d{2}-\d{2}\.[1-9]\d*\.([a-z0-9]+-)*[a-z0-9]+$/, "methodology_version"),
    decided_at: timestamp(payload.decided_at, "decided_at"),
    outcome: enumValue(payload.outcome, ["top_set", "abstain"] as const, "outcome"),
    selections: normalizeRecords(array(payload.selections, "selections").map(parseSelection), (row) => [row.evaluated_configuration_id], "selections"),
    exclusions: normalizeRecords(array(payload.exclusions, "exclusions").map(parseExclusion), (row) => [row.evaluated_configuration_id, row.code], "exclusions"),
    reasons: normalizeRecords(array(payload.reasons, "reasons").map(parseReason), (row) => [row.reason_type, row.code, row.subject_id, row.axis], "reasons"),
    sensitivity: normalizeRecords(array(payload.sensitivity, "sensitivity").map(parseSensitivity), (row) => [row.scenario], "sensitivity"),
    evidence: normalizeRecords(array(payload.evidence, "evidence").map(parseEvidence), (row) => [row.evidence_id], "evidence"),
    freshness: parseFreshness(payload.freshness),
    abstention_reason: payload.abstention_reason === null
      ? null
      : enumValue(payload.abstention_reason, [
          "insufficient_comparable_evidence", "no_eligible_serving_offer", "constraints_eliminate_all_candidates",
          "evidence_stale", "methodology_unavailable",
        ] as const, "abstention_reason"),
  };
  const evidenceTargets = body.evidence.map(evidenceTarget);
  if (new Set(evidenceTargets).size !== evidenceTargets.length) {
    throw new TypeError("evidence targets must be unique");
  }
  validateReceiptSemantics(body);
  return body;
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

function parsePublicationSnapshot(value: unknown): PublicationSnapshotRefV1 {
  const payload = closed(value, ["publication_snapshot_id", "ranking_group_id", "manifest_version", "published_at"]);
  return {
    publication_snapshot_id: patternString(payload.publication_snapshot_id, /^snapshot_[0-9a-f]{64}$/, "publication_snapshot_id"),
    ranking_group_id: nonEmptyString(payload.ranking_group_id, "ranking_group_id"),
    manifest_version: patternString(payload.manifest_version, /^\d{4}-\d{2}-\d{2}\.[1-9]\d*$/, "manifest_version"),
    published_at: timestamp(payload.published_at, "published_at"),
  };
}

function parseSelection(value: unknown): DecisionSelectionV1 {
  const payload = closed(value, [
    "evaluated_configuration_id", "serving_offer_id", "capability_rank",
    "projected_monthly_cost_microusd", "zero_cache_sensitivity_projected_monthly_cost_microusd",
  ]);
  const selection: DecisionSelectionV1 = {
    evaluated_configuration_id: patternString(payload.evaluated_configuration_id, configurationIdPattern, "evaluated_configuration_id"),
    serving_offer_id: payload.serving_offer_id === null ? null : prefixString(payload.serving_offer_id, "offer_", "serving_offer_id"),
    capability_rank: safeInteger(payload.capability_rank, "capability_rank", 1),
    projected_monthly_cost_microusd: nullableSafeInteger(payload.projected_monthly_cost_microusd, "projected_monthly_cost_microusd", 0),
    zero_cache_sensitivity_projected_monthly_cost_microusd: nullableSafeInteger(
      payload.zero_cache_sensitivity_projected_monthly_cost_microusd,
      "zero_cache_sensitivity_projected_monthly_cost_microusd",
      0,
    ),
  };
  if (
    (selection.projected_monthly_cost_microusd !== null
      || selection.zero_cache_sensitivity_projected_monthly_cost_microusd !== null)
    && selection.serving_offer_id === null
  ) {
    throw new TypeError("serving_offer_id is required when a monthly cost is present");
  }
  return selection;
}

function parseExclusion(value: unknown): DecisionExclusionV1 {
  const payload = closed(value, ["evaluated_configuration_id", "code", "evidence_ids"]);
  return {
    evaluated_configuration_id: patternString(payload.evaluated_configuration_id, configurationIdPattern, "evaluated_configuration_id"),
    code: enumValue(payload.code, [
      "constraints_not_met", "not_in_capability_top_set", "serving_offer_unverified", "evidence_stale", "incompatible_configuration",
    ] as const, "code"),
    evidence_ids: normalizedStringSet(payload.evidence_ids, "evidence_ids"),
  };
}

function parseFreshness(value: unknown): DecisionFreshnessV1 {
  const payload = closed(value, ["observed_at", "expires_at"]);
  const observed = timestamp(payload.observed_at, "observed_at");
  const expires = timestamp(payload.expires_at, "expires_at");
  if (expires <= observed) throw new TypeError("expires_at must be after observed_at");
  return { observed_at: observed, expires_at: expires };
}

function parseReason(value: unknown): DecisionReasonV1 {
  const payload = closed(value, [
    "reason_type", "code", "subject_id", "predicate", "axis", "observed_value", "unit", "threshold",
    "evidence_ids", "freshness", "caveat_codes",
  ]);
  const reason: DecisionReasonV1 = {
    reason_type: enumValue(payload.reason_type, ["best_when", "avoid_when"] as const, "reason_type"),
    code: enumValue(payload.code, [
      "strongest_capability_evidence", "within_capability_top_set", "lowest_cost_under_usage_profile", "budget_fit_under_declared_profiles",
      "provider_constraint_match", "region_constraint_match", "context_requirement_met", "insufficient_evidence",
      "serving_offer_unverified", "budget_exceeded", "stale_evidence",
    ] as const, "code"),
    subject_id: nonEmptyString(payload.subject_id, "subject_id"),
    predicate: enumValue(payload.predicate, ["eq", "ne", "lt", "lte", "gt", "gte", "within_top_set", "unavailable"] as const, "predicate"),
    axis: enumValue(payload.axis, ["capability", "monthly_cost", "context", "availability", "freshness", "provider", "region"] as const, "axis"),
    observed_value: nonEmptyString(payload.observed_value, "observed_value"),
    unit: enumValue(payload.unit, ["probability", "score", "microusd_per_month", "tokens", "status", "timestamp", "provider_id", "region_id"] as const, "unit"),
    threshold: nullableString(payload.threshold, "threshold"),
    evidence_ids: normalizedStringSet(payload.evidence_ids, "evidence_ids"),
    freshness: parseFreshness(payload.freshness),
    caveat_codes: normalizedEnumSet(payload.caveat_codes, [
      "provider_offer_link_required", "limited_availability", "evidence_near_expiry",
      "incomplete_family_coverage", "cost_sensitive_to_usage",
    ] as const, "caveat_codes", true),
  };
  if (!["status", "timestamp", "provider_id", "region_id"].includes(reason.unit)) {
    decimal(reason.observed_value, "observed_value");
    if (reason.threshold !== null) decimal(reason.threshold, "threshold");
  }
  const requiredShape: Partial<Record<DecisionReasonV1["code"], [DecisionReasonV1["axis"], DecisionReasonV1["unit"], DecisionReasonV1["predicate"]]>> = {
    strongest_capability_evidence: ["capability", "score", "gte"],
    within_capability_top_set: ["capability", "score", "within_top_set"],
    provider_constraint_match: ["provider", "provider_id", "eq"],
    region_constraint_match: ["region", "region_id", "eq"],
    lowest_cost_under_usage_profile: ["monthly_cost", "microusd_per_month", "eq"],
    budget_fit_under_declared_profiles: ["monthly_cost", "microusd_per_month", "lte"],
    budget_exceeded: ["monthly_cost", "microusd_per_month", "gt"],
    context_requirement_met: ["context", "tokens", "gte"],
    insufficient_evidence: ["capability", "status", "unavailable"],
    serving_offer_unverified: ["availability", "status", "unavailable"],
    stale_evidence: ["freshness", "timestamp", "lt"],
  };
  const expected = requiredShape[reason.code];
  if (expected && (reason.axis !== expected[0] || reason.unit !== expected[1] || reason.predicate !== expected[2])) {
    throw new TypeError(`${reason.code} requires axis=${expected[0]}, unit=${expected[1]}, predicate=${expected[2]}`);
  }
  if (["eq", "ne", "lt", "lte", "gt", "gte"].includes(reason.predicate) && reason.threshold === null) {
    throw new TypeError(`${reason.predicate} predicate requires threshold`);
  }
  if (["within_top_set", "unavailable"].includes(reason.predicate) && reason.threshold !== null) {
    throw new TypeError(`${reason.predicate} predicate requires a null threshold`);
  }
  const positive = new Set<DecisionReasonV1["code"]>([
    "strongest_capability_evidence", "within_capability_top_set", "lowest_cost_under_usage_profile",
    "budget_fit_under_declared_profiles", "provider_constraint_match", "region_constraint_match", "context_requirement_met",
  ]);
  if (positive.has(reason.code) !== (reason.reason_type === "best_when")) {
    throw new TypeError(`${reason.code} requires reason_type=${positive.has(reason.code) ? "best_when" : "avoid_when"}`);
  }
  if (reason.unit === "timestamp") {
    timestamp(reason.observed_value, "observed_value");
    if (reason.threshold !== null) timestamp(reason.threshold, "threshold");
  }
  if (reason.unit === "status") {
    const statuses = ["available", "limited", "unavailable", "sufficient", "insufficient", "fresh", "stale"] as const;
    enumValue(reason.observed_value, statuses, "observed_value");
    if (reason.threshold !== null) enumValue(reason.threshold, statuses, "threshold");
  }
  return reason;
}

function parseSensitivity(value: unknown): DecisionSensitivityV1 {
  const payload = closed(value, ["scenario", "stable", "selected_configuration_ids"]);
  const identifiers = normalizedStringSet(payload.selected_configuration_ids, "selected_configuration_ids", true);
  identifiers.forEach((identifier) => patternString(identifier, configurationIdPattern, "selected_configuration_ids item"));
  if (typeof payload.stable !== "boolean") throw new TypeError("stable must be a boolean");
  return {
    scenario: enumValue(payload.scenario, ["price_plus_20_percent", "price_minus_20_percent", "usage_double", "leave_one_family_out"] as const, "scenario"),
    stable: payload.stable,
    selected_configuration_ids: identifiers,
  };
}

function parseEvidence(value: unknown): DecisionEvidenceV1 {
  const input = record(value, "decision evidence");
  if (input.kind === "observation") {
    const payload = closed(input, ["kind", "evidence_id", "observation"]);
    return {
      kind: "observation",
      evidence_id: nonEmptyString(payload.evidence_id, "evidence_id"),
      observation: parseObservationV1(payload.observation),
    };
  }
  if (input.kind === "serving_offer") {
    const payload = closed(input, ["kind", "evidence_id", "serving_offer"]);
    return {
      kind: "serving_offer",
      evidence_id: nonEmptyString(payload.evidence_id, "evidence_id"),
      serving_offer: parseServingOfferV1(payload.serving_offer),
    };
  }
  if (input.kind === "evaluation_to_offer_link") {
    const payload = closed(input, ["kind", "evidence_id", "evaluation_to_offer_link"]);
    return {
      kind: "evaluation_to_offer_link",
      evidence_id: nonEmptyString(payload.evidence_id, "evidence_id"),
      evaluation_to_offer_link: parseEvaluationToOfferLinkV1(payload.evaluation_to_offer_link),
    };
  }
  throw new TypeError("evidence.kind must be observation, serving_offer, or evaluation_to_offer_link");
}

function validateReceiptSemantics(receipt: Omit<DecisionReceiptV1, "receipt_id">): void {
  if (receipt.publication_snapshot.ranking_group_id !== receipt.query.ranking_group_id) {
    throw new TypeError("publication_snapshot ranking_group_id must match query");
  }
  if (receipt.decided_at < receipt.publication_snapshot.published_at) {
    throw new TypeError("decided_at must be on or after publication_snapshot.published_at");
  }
  if (!(receipt.freshness.observed_at <= receipt.decided_at && receipt.decided_at < receipt.freshness.expires_at)) {
    throw new TypeError("receipt freshness must contain decided_at");
  }
  if (receipt.outcome === "top_set") {
    if (receipt.selections.length === 0) throw new TypeError("top_set outcome requires at least one selection");
    if (receipt.abstention_reason !== null) throw new TypeError("abstention_reason must be null for top_set");
    if (receipt.reasons.length === 0) throw new TypeError("top_set outcome requires reasons");
    if (receipt.evidence.length === 0) throw new TypeError("top_set outcome requires evidence");
  } else {
    if (receipt.selections.length !== 0) throw new TypeError("abstain outcome must not contain selections");
    if (receipt.abstention_reason === null) throw new TypeError("abstention_reason is required for abstain");
  }
  if (receipt.outcome === "top_set" && receipt.query.objective === "lowest_cost_within_top_set") {
    for (const selection of receipt.selections) {
      if (selection.serving_offer_id === null) throw new TypeError("lowest_cost_within_top_set requires serving_offer_id for every selection");
      if (selection.projected_monthly_cost_microusd === null) throw new TypeError("lowest_cost_within_top_set requires projected_monthly_cost_microusd for every selection");
      if (receipt.query.monthly_budget_microusd !== undefined && selection.projected_monthly_cost_microusd > receipt.query.monthly_budget_microusd) {
        throw new TypeError("selection cost must not exceed monthly_budget_microusd");
      }
      if (
        receipt.query.monthly_budget_microusd !== undefined
        && receipt.query.zero_cache_sensitivity_usage_profile !== undefined
        && (
          selection.zero_cache_sensitivity_projected_monthly_cost_microusd === null
          || selection.zero_cache_sensitivity_projected_monthly_cost_microusd
            > receipt.query.monthly_budget_microusd
        )
      ) {
        throw new TypeError(
          "zero-cache sensitivity projected monthly cost must not exceed monthly_budget_microusd",
        );
      }
    }
    if (new Set(receipt.selections.map((row) => row.projected_monthly_cost_microusd)).size !== 1) {
      throw new TypeError("lowest_cost_within_top_set selections must share one equal minimum cost");
    }
  }
  if (receipt.outcome === "top_set" && receipt.selections.length === 1) {
    const winner = receipt.selections[0].evaluated_configuration_id;
    const leaveOneOut = receipt.sensitivity.find((row) => row.scenario === "leave_one_family_out");
    if (!leaveOneOut || !leaveOneOut.stable || leaveOneOut.selected_configuration_ids.length !== 1 || leaveOneOut.selected_configuration_ids[0] !== winner) {
      throw new TypeError("a single selection requires stable leave_one_family_out sensitivity for the same winner");
    }
  }
  const selected = new Set(receipt.selections.map((row) => row.evaluated_configuration_id));
  const excluded = new Set(receipt.exclusions.map((row) => row.evaluated_configuration_id));
  if (receipt.exclusions.some((row) => selected.has(row.evaluated_configuration_id))) {
    throw new TypeError("a configuration cannot be both selected and excluded");
  }
  if (receipt.outcome === "top_set") {
    const leaveOneOut = receipt.sensitivity.find((row) => row.scenario === "leave_one_family_out");
    if (!leaveOneOut || !leaveOneOut.stable || !setEquals(selected, new Set(leaveOneOut.selected_configuration_ids))) {
      throw new TypeError("every top_set requires stable leave_one_family_out sensitivity for the exact selected set");
    }
    if (receipt.query.objective === "lowest_cost_within_top_set") {
      for (const scenario of ["price_plus_20_percent", "price_minus_20_percent", "usage_double"] as const) {
        if (!receipt.sensitivity.some((row) => row.scenario === scenario)) {
          throw new TypeError(`lowest_cost_within_top_set requires ${scenario} sensitivity`);
        }
      }
    }
    for (const sensitivity of receipt.sensitivity) {
      const sensitivityIds = new Set(sensitivity.selected_configuration_ids);
      const same = setEquals(selected, sensitivityIds);
      if (sensitivity.stable && !same) throw new TypeError("stable sensitivity must preserve the exact selected configuration set");
      if (!sensitivity.stable && same) throw new TypeError("unstable sensitivity must change the selected configuration set");
      if ([...sensitivityIds].some((identifier) => !selected.has(identifier) && !excluded.has(identifier))) {
        throw new TypeError("sensitivity selected_configuration_ids must be known decision candidates");
      }
    }
    for (const selection of receipt.selections) {
      const covered = receipt.reasons.some((reason) =>
        reason.subject_id === selection.evaluated_configuration_id || reason.subject_id === selection.serving_offer_id
      );
      if (!covered) throw new TypeError("reasons must cover every selected configuration or serving offer");
    }
    validateSelectedDecisionEvidence(receipt);
  }
  const evidence = new Map(receipt.evidence.map((row) => [row.evidence_id, row]));
  for (const identifier of [...receipt.exclusions.flatMap((row) => row.evidence_ids), ...receipt.reasons.flatMap((row) => row.evidence_ids)]) {
    if (!evidence.has(identifier)) throw new TypeError("every cited evidence_id must be present in evidence");
  }
  for (const exclusion of receipt.exclusions) {
    if (exclusion.evidence_ids.length === 0 || !exclusion.evidence_ids.every(
      (identifier) => evidenceConfigurationId(evidence.get(identifier)!) === exclusion.evaluated_configuration_id,
    )) {
      throw new TypeError("exclusion evidence must concern its excluded configuration");
    }
  }
}

function evidenceTarget(evidence: DecisionEvidenceV1): string {
  if (evidence.kind === "observation") return canonicalJson([evidence.kind, evidence.observation.observation_id]);
  if (evidence.kind === "serving_offer") return canonicalJson([evidence.kind, evidence.serving_offer.serving_offer_id]);
  const link = evidence.evaluation_to_offer_link;
  return canonicalJson([evidence.kind, link.evaluated_configuration_id, link.serving_offer_id]);
}

function evidenceConfigurationId(evidence: DecisionEvidenceV1): string | null {
  if (evidence.kind === "observation") return evidence.observation.evaluated_configuration_id;
  if (evidence.kind === "evaluation_to_offer_link") return evidence.evaluation_to_offer_link.evaluated_configuration_id;
  return null;
}

function validateSelectedDecisionEvidence(receipt: Omit<DecisionReceiptV1, "receipt_id">): void {
  const evidence = new Map(receipt.evidence.map((row) => [row.evidence_id, row]));
  for (const reason of receipt.reasons) {
    if (reason.reason_type === "best_when" && !(reason.freshness.observed_at <= receipt.decided_at && receipt.decided_at < reason.freshness.expires_at)) {
      throw new TypeError("positive reason freshness must contain decided_at");
    }
  }
  for (const selection of receipt.selections) {
    const capabilityReasons = receipt.reasons.filter(
      (reason) => reason.subject_id === selection.evaluated_configuration_id
        && ["strongest_capability_evidence", "within_capability_top_set"].includes(reason.code),
    );
    if (capabilityReasons.length === 0 || !capabilityReasons.every((reason) =>
      reason.evidence_ids.length > 0 && reason.evidence_ids.every((identifier) => {
        const row = evidence.get(identifier);
        return row?.kind === "observation"
          && row.observation.evaluated_configuration_id === selection.evaluated_configuration_id;
      })
    )) {
      throw new TypeError("every selected configuration requires matching capability observation evidence");
    }

    const query = receipt.query;
    const offerRequired = selection.serving_offer_id !== null
      || query.objective === "lowest_cost_within_top_set"
      || query.provider_ids !== undefined
      || query.regions !== undefined
      || query.minimum_context_tokens !== undefined
      || query.usage_profile !== undefined
      || query.monthly_budget_microusd !== undefined;
    if (!offerRequired) continue;
    if (selection.serving_offer_id === null) throw new TypeError("selected configuration requires serving_offer_id for applied offer constraints");
    const offerEvidence = receipt.evidence.find(
      (row): row is ServingOfferEvidenceV1 => row.kind === "serving_offer" && row.serving_offer.serving_offer_id === selection.serving_offer_id,
    );
    const linkEvidence = receipt.evidence.find(
      (row): row is EvaluationToOfferLinkEvidenceV1 => row.kind === "evaluation_to_offer_link"
        && row.evaluation_to_offer_link.evaluated_configuration_id === selection.evaluated_configuration_id
        && row.evaluation_to_offer_link.serving_offer_id === selection.serving_offer_id,
    );
    if (!offerEvidence) throw new TypeError("selected serving offer requires full typed serving-offer evidence");
    if (!linkEvidence) throw new TypeError("selected serving offer requires full typed offer-link evidence");
    const offer = offerEvidence.serving_offer;
    const link = linkEvidence.evaluation_to_offer_link;
    if (!isServingOfferDecisionEligible(offer, link, receipt.decided_at)) {
      throw new TypeError("selected offer and link must be exact, approved, non-inferred, available, and current at decided_at");
    }
    if (query.provider_ids && !query.provider_ids.includes(offer.provider_id)) throw new TypeError("selected offer provider must satisfy provider_ids");
    if (query.regions && !query.regions.includes(offer.region)) throw new TypeError("selected offer region must satisfy regions");
    if (query.minimum_context_tokens !== undefined && offer.context.context_window_tokens < query.minimum_context_tokens) {
      throw new TypeError("selected offer must satisfy minimum_context_tokens");
    }
    let computedCost: number | null = null;
    if (query.usage_profile !== undefined) {
      computedCost = monthlyCostMicrousd(query.usage_profile, offer.pricing);
      if (computedCost === null) {
        throw new TypeError("pricing schedule lacks a rate for nonzero usage; decision must abstain");
      }
      if (selection.projected_monthly_cost_microusd !== computedCost) {
        throw new TypeError("projected_monthly_cost_microusd must equal the computed monthly cost");
      }
      if (query.monthly_budget_microusd !== undefined && computedCost > query.monthly_budget_microusd) {
        throw new TypeError("computed monthly cost must not exceed monthly_budget_microusd");
      }
    } else if (selection.projected_monthly_cost_microusd !== null) {
      throw new TypeError("projected_monthly_cost_microusd must be null when query usage is omitted");
    }
    const sensitivity = query.zero_cache_sensitivity_usage_profile;
    let sensitivityCost: number | null = null;
    if (sensitivity !== undefined) {
      sensitivityCost = monthlyCostMicrousd(sensitivity, offer.pricing);
      if (sensitivityCost === null) {
        throw new TypeError("pricing schedule lacks a rate for zero-cache sensitivity usage; decision must abstain");
      }
      if (selection.zero_cache_sensitivity_projected_monthly_cost_microusd !== sensitivityCost) {
        throw new TypeError("zero_cache_sensitivity_projected_monthly_cost_microusd must equal the computed sensitivity cost");
      }
      if (
        query.monthly_budget_microusd !== undefined
        && sensitivityCost > query.monthly_budget_microusd
      ) {
        throw new TypeError(
          "zero-cache sensitivity projected monthly cost must not exceed monthly_budget_microusd",
        );
      }
    } else if (selection.zero_cache_sensitivity_projected_monthly_cost_microusd !== null) {
      throw new TypeError("zero_cache_sensitivity_projected_monthly_cost_microusd must be null when query sensitivity is omitted");
    }
    const requiredIds = new Set([offerEvidence.evidence_id, linkEvidence.evidence_id]);
    const observedAt = [
      offer.context.observed_at,
      offer.availability.observed_at,
      offer.pricing.observed_at,
      offer.pricing.effective_at,
      link.observed_at,
    ].sort().at(-1)!;
    const expiresAt = [offer.context.expires_at, offer.availability.expires_at, offer.pricing.expires_at, link.expires_at].sort()[0];
    const costSensitiveToUsage = query.usage_profile?.basis === "estimated"
      && sensitivityCost !== null
      && computedCost !== sensitivityCost;
    if (costSensitiveToUsage && !receipt.reasons.some(
      (reason) => reason.caveat_codes.includes("cost_sensitive_to_usage")
        && (
          reason.subject_id === selection.evaluated_configuration_id
          || reason.subject_id === selection.serving_offer_id
        ),
    )) {
      throw new TypeError(
        "differing estimated profile costs require cost_sensitive_to_usage on a matching selected configuration or offer reason",
      );
    }
    if (query.objective === "lowest_cost_within_top_set") {
      requireOfferReason(
        receipt,
        selection,
        "lowest_cost_under_usage_profile",
        String(computedCost),
        String(computedCost),
        requiredIds,
        observedAt,
        expiresAt,
        costSensitiveToUsage,
      );
    }
    if (query.monthly_budget_microusd !== undefined) {
      const declaredProfileCost = Math.max(
        ...[computedCost, sensitivityCost].filter((cost): cost is number => cost !== null),
      );
      requireOfferReason(
        receipt,
        selection,
        "budget_fit_under_declared_profiles",
        String(declaredProfileCost),
        String(query.monthly_budget_microusd),
        requiredIds,
        observedAt,
        expiresAt,
        costSensitiveToUsage,
      );
    }
    if (query.provider_ids) requireOfferReason(receipt, selection, "provider_constraint_match", offer.provider_id, offer.provider_id, requiredIds, observedAt, expiresAt);
    if (query.regions) requireOfferReason(receipt, selection, "region_constraint_match", offer.region, offer.region, requiredIds, observedAt, expiresAt);
    if (query.minimum_context_tokens !== undefined) {
      requireOfferReason(receipt, selection, "context_requirement_met", String(offer.context.context_window_tokens), String(query.minimum_context_tokens), requiredIds, observedAt, expiresAt);
    }
  }
  const positive = receipt.reasons.filter((row) => row.reason_type === "best_when");
  if (positive.length) {
    const observedAt = positive.map((row) => row.freshness.observed_at).sort().at(-1)!;
    const expiresAt = positive.map((row) => row.freshness.expires_at).sort()[0];
    if (receipt.freshness.observed_at !== observedAt || receipt.freshness.expires_at !== expiresAt) {
      throw new TypeError("receipt freshness must equal the intersection of positive reason freshness");
    }
  }
}

function requireOfferReason(
  receipt: Omit<DecisionReceiptV1, "receipt_id">,
  selection: DecisionSelectionV1,
  code: DecisionReasonV1["code"],
  observedValue: string,
  threshold: string,
  evidenceIds: Set<string>,
  observedAt: string,
  expiresAt: string,
  requireCostSensitiveCaveat = false,
): void {
  const reason = receipt.reasons.find((row) => row.code === code && row.subject_id === selection.serving_offer_id);
  if (!reason) throw new TypeError(`applied query constraint requires ${code} reason`);
  if (reason.observed_value !== observedValue || reason.threshold !== threshold) {
    throw new TypeError(`${code} observed_value/threshold must match the selected offer and query`);
  }
  if (!setEquals(evidenceIds, new Set(reason.evidence_ids))) {
    throw new TypeError(`${code} must cite exactly the matching serving-offer and offer-link evidence`);
  }
  if (reason.freshness.observed_at !== observedAt || reason.freshness.expires_at !== expiresAt) {
    throw new TypeError(`${code} freshness must equal the selected offer/link validity intersection`);
  }
  if (requireCostSensitiveCaveat && !reason.caveat_codes.includes("cost_sensitive_to_usage")) {
    throw new TypeError(
      `${code} requires cost_sensitive_to_usage when estimated profile costs differ`,
    );
  }
}

export function monthlyCostMicrousd(
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
  if (!Number.isSafeInteger(result)) throw new TypeError("computed monthly cost must be a safe integer");
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

function envelope(payload: Record<string, unknown>, objectName: string): void {
  if (payload.object !== objectName) throw new TypeError(`object must be ${objectName}`);
  if (payload.schema_version !== "1") throw new TypeError("schema_version must be 1");
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

function normalizedPatternSet(value: unknown, name: string, pattern: RegExp): string[] {
  return normalizedStringSet(value, name).map((item) => patternString(item, pattern, `${name} item`));
}

function normalizedEnumSet<const T extends readonly string[]>(value: unknown, allowed: T, name: string, allowEmpty = false): T[number][] {
  return normalizedStringSet(value, name, allowEmpty).map((item) => enumValue(item, allowed, `${name} item`));
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
