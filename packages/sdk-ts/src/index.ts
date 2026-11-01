import {
  canonicalJson,
  parseDecisionQueryV2,
  parseDecisionReceiptV2,
  type DecisionQueryV2,
  type DecisionReceiptV2,
  type SnapshotSetDescriptorV1,
  verifyCompareResultSemantics,
  verifyEntityDetailSemantics,
  verifyLeaderboardSemantics,
} from "./decision-contracts.ts";

export const USE_CASE_ENTITY_KINDS = [
  "agent",
  "model",
  "tool",
] as const;

export const USE_CASE_RANK_POLICIES = [
  "ranked",
  "veto_overlay",
] as const;

export const PROBLEM_CODES = [
  "rate_limited",
  "upstream_timeout",
  "validation",
  "not_found",
  "methodology_stale",
  "internal",
  "unauthorized",
  "forbidden",
  "via_not_supported",
] as const;

export const PUBLIC_FIXTURE_KINDS = [
  "fingerprint",
  "observation",
  "problem",
  "raw-entry",
  "use-cases",
] as const;

export type UseCaseEntityKind = (typeof USE_CASE_ENTITY_KINDS)[number];
export type UseCaseRankPolicy = (typeof USE_CASE_RANK_POLICIES)[number];
export type ProblemCode = (typeof PROBLEM_CODES)[number];
export type PublicFixtureKind = (typeof PUBLIC_FIXTURE_KINDS)[number];
export type NonEmptyArray<T> = [T, ...T[]];

export interface CapabilityFingerprint {
  object: "capability_fingerprint";
  id_scheme: string;
  canonical_id: string;
  entity_kind: string;
  declared_capability_shape: Record<string, unknown>;
  capability_fingerprint: string;
}

export interface RawEntry {
  object: "raw_entry";
  source: string;
  source_id: string;
  entity_kind: string;
  canonical_id: string;
  raw_metadata: Record<string, unknown>;
  declared_capability_shape: Record<string, unknown>;
  fetched_at: string;
  content_hash: string;
}

export interface UseCaseBase {
  object: "use_case";
  id: string;
  name: string;
  definition: string;
  entity_kinds: NonEmptyArray<UseCaseEntityKind>;
}

export interface RankedUseCase extends UseCaseBase {
  rank_policy: "ranked";
  is_overlay: false;
}

export interface OverlayUseCase extends UseCaseBase {
  rank_policy: "veto_overlay";
  is_overlay: true;
}

export type UseCase = RankedUseCase | OverlayUseCase;

export interface UseCaseCatalog {
  object: "use_case_catalog";
  methodology_version: string;
  generated_at: string;
  use_cases: NonEmptyArray<UseCase>;
}

export function verifyUseCaseCatalog(value: unknown): UseCaseCatalog {
  if (!isRecord(value) || !hasExactFields(value, ["object", "methodology_version", "generated_at", "use_cases"])) {
    throw new TypeError("use-case catalog fields are invalid");
  }
  if (
    value.object !== "use_case_catalog"
    || typeof value.methodology_version !== "string"
    || !/^\d{4}-\d{2}-\d{2}\.[1-9]\d*\.([a-z0-9]+-)*[a-z0-9]+$/.test(value.methodology_version)
    || !isUtcSecondTimestamp(value.generated_at)
    || !Array.isArray(value.use_cases)
    || value.use_cases.length === 0
  ) {
    throw new TypeError("use-case catalog envelope is invalid");
  }
  const ids = new Set<string>();
  const fields = ["object", "id", "name", "definition", "entity_kinds", "rank_policy", "is_overlay"];
  for (const row of value.use_cases) {
    if (!isRecord(row) || !hasExactFields(row, fields)) {
      throw new TypeError("use-case fields are invalid");
    }
    if (
      row.object !== "use_case"
      || typeof row.id !== "string"
      || row.id.length === 0
      || ids.has(row.id)
      || typeof row.name !== "string"
      || row.name.length === 0
      || typeof row.definition !== "string"
      || row.definition.length === 0
    ) {
      throw new TypeError("use-case ids must be unique and text fields non-empty");
    }
    ids.add(row.id);
    if (
      !Array.isArray(row.entity_kinds)
      || row.entity_kinds.length === 0
      || new Set(row.entity_kinds).size !== row.entity_kinds.length
      || row.entity_kinds.some((kind) => !USE_CASE_ENTITY_KINDS.includes(kind as UseCaseEntityKind))
    ) {
      throw new TypeError("use-case entity_kinds must be unique public entity kinds");
    }
    if (
      (row.rank_policy !== "ranked" && row.rank_policy !== "veto_overlay")
      || typeof row.is_overlay !== "boolean"
      || row.is_overlay !== (row.rank_policy === "veto_overlay")
    ) {
      throw new TypeError("use-case rank_policy and is_overlay must agree");
    }
  }
  return value as unknown as UseCaseCatalog;
}

export interface BenchmarkHealthCell {
  cell_id: string;
  status: "active" | "preview" | "unavailable";
  ranking_group_count: number;
  published_ranking_group_count: number;
  benchmark_family_count: number;
  candidate_feed_count: number;
  implemented_feed_count: number;
  admitted_feed_count: number;
  rank_eligible_feed_count: number;
}

export interface BenchmarkHealth {
  object: "benchmark_health";
  schema_version: "1";
  manifest_version: string;
  generated_at: string;
  cells: BenchmarkHealthCell[];
}

export function verifyBenchmarkHealthSemantics(value: unknown): BenchmarkHealth {
  if (!isRecord(value)) {
    throw new TypeError("benchmark health must be a JSON object");
  }
  const envelopeFields = ["object", "schema_version", "manifest_version", "generated_at", "cells"];
  if (!hasExactFields(value, envelopeFields)) {
    throw new TypeError("benchmark health fields are invalid");
  }
  if (
    value.object !== "benchmark_health"
    || value.schema_version !== "1"
    || typeof value.manifest_version !== "string"
    || !/^\d{4}-\d{2}-\d{2}\.[1-9]\d*$/.test(value.manifest_version)
    || !isUtcSecondTimestamp(value.generated_at)
    || !Array.isArray(value.cells)
    || value.cells.length === 0
  ) {
    throw new TypeError("benchmark health envelope is invalid");
  }
  const countFields = [
    "ranking_group_count",
    "published_ranking_group_count",
    "benchmark_family_count",
    "candidate_feed_count",
    "implemented_feed_count",
    "admitted_feed_count",
    "rank_eligible_feed_count",
  ] as const;
  const cellFields = ["cell_id", "status", ...countFields];
  const cellIds = new Set<string>();
  for (const cell of value.cells) {
    if (!isRecord(cell) || !hasExactFields(cell, cellFields)) {
      throw new TypeError("benchmark health cell fields are invalid");
    }
    if (
      typeof cell.cell_id !== "string"
      || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(cell.cell_id)
      || cellIds.has(cell.cell_id)
    ) {
      throw new TypeError("benchmark health cell_id values must be unique canonical slugs");
    }
    cellIds.add(cell.cell_id);
    for (const field of countFields) {
      if (!Number.isSafeInteger(cell[field]) || (cell[field] as number) < 0) {
        throw new TypeError(`benchmark health ${field} must be a safe nonnegative integer`);
      }
    }
    const published = cell.published_ranking_group_count as number;
    const groups = cell.ranking_group_count as number;
    const candidate = cell.candidate_feed_count as number;
    const implemented = cell.implemented_feed_count as number;
    const admitted = cell.admitted_feed_count as number;
    const eligible = cell.rank_eligible_feed_count as number;
    if (published > groups || !(eligible <= admitted && admitted <= implemented && implemented <= candidate)) {
      throw new TypeError("benchmark health counts are inconsistent");
    }
    const expectedStatus = published > 0 ? "active" : implemented > 0 ? "preview" : "unavailable";
    if (cell.status !== expectedStatus) {
      throw new TypeError("benchmark health status must match publication and implementation counts");
    }
  }
  return value as unknown as BenchmarkHealth;
}

export interface Citation {
  source_artifact_id: string;
  benchmark_family_id: string;
  title: string;
  url: string;
}

export interface LeaderboardEntry {
  evaluated_configuration_id: string;
  ranking: {
    rank: number;
    display_name: string;
    capability_score: number;
    uncertainty: Record<string, unknown>;
    in_top_set: boolean;
    evidence_family_count: number;
    caveat_codes: string[];
  };
}

export interface ExplorerEvidenceView {
  benchmark_family_id: string;
  feed_id: string;
  metric_direction: "higher" | "lower";
  observed_at: string;
  expires_at: string;
  agreement: "single_source" | "promising_not_proven" | "conflicting";
  entries: LeaderboardEntry[];
  citations: Citation[];
}

export interface ExplorerViewIdentity {
  benchmark_family_id: string;
  feed_id: string;
}

export interface LeaderboardSection {
  ranking_group_id: string;
  entity_kind: string;
  interaction_policy: string;
  configuration_passport_class: string;
  state: string;
  evidence_snapshot_id: string;
  eligibility_summary: Record<string, unknown>;
  entries: LeaderboardEntry[];
  citations: Citation[];
  explorer_views: ExplorerEvidenceView[];
}

export interface Leaderboard {
  object: "leaderboard";
  schema_version: "1";
  cell_id: string;
  cell_state: string;
  manifest_version: string;
  methodology_version: string;
  snapshot_set_id: string;
  snapshot_set_descriptor: SnapshotSetDescriptorV1;
  generated_at: string;
  ranking_groups: LeaderboardSection[];
}

export interface EntityDetail {
  object: "entity_detail";
  schema_version: "1";
  cell_id: string;
  manifest_version: string;
  methodology_version: string;
  snapshot_set_id: string;
  snapshot_set_descriptor: SnapshotSetDescriptorV1;
  ranking_group_id: string;
  state: string;
  evidence_snapshot_id: string;
  explorer_view: ExplorerViewIdentity | null;
  eligibility_summary: Record<string, unknown>;
  generated_at: string;
  entity: Record<string, unknown>;
}

export interface CompareResult {
  object: "compare_result";
  schema_version: "1";
  cell_id: string;
  manifest_version: string;
  methodology_version: string;
  snapshot_set_id: string;
  snapshot_set_descriptor: SnapshotSetDescriptorV1;
  ranking_group_id: string;
  entity_kind: string;
  interaction_policy: string;
  configuration_passport_class: string;
  state: string;
  evidence_snapshot_id: string;
  explorer_view: ExplorerViewIdentity | null;
  eligibility_summary: Record<string, unknown>;
  generated_at: string;
  entities: Array<Record<string, unknown>>;
}

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  code?: ProblemCode;
  retriable?: boolean;
  retry_after?: number;
  field?: string;
  request_id?: string;
  doc_url?: string;
  [key: string]: unknown;
}

export function parseProblemDetails(value: unknown): ProblemDetails {
  if (!isRecord(value)) {
    throw new TypeError("Problem Details must be a JSON object");
  }
  for (const name of ["title", "detail"] as const) {
    if (typeof value[name] !== "string" || value[name].length === 0) {
      throw new TypeError(`Problem Details ${name} must be a non-empty string`);
    }
  }
  uriReference(value.type, "type");
  if (!Number.isInteger(value.status) || (value.status as number) < 400 || (value.status as number) > 599) {
    throw new TypeError("Problem Details status must be an integer from 400 to 599");
  }
  if ("instance" in value) {
    uriReference(value.instance, "instance");
  }
  for (const name of ["field", "request_id"] as const) {
    if (name in value && (typeof value[name] !== "string" || value[name].length === 0)) {
      throw new TypeError(`Problem Details ${name} must be a non-empty string`);
    }
  }
  if (
    "code" in value &&
    (typeof value.code !== "string" || !PROBLEM_CODES.includes(value.code as ProblemCode))
  ) {
    throw new TypeError("Problem Details code is not public");
  }
  if ("retriable" in value && typeof value.retriable !== "boolean") {
    throw new TypeError("Problem Details retriable must be a boolean");
  }
  if (
    "retry_after" in value &&
    (!Number.isSafeInteger(value.retry_after) || (value.retry_after as number) < 0)
  ) {
    throw new TypeError("Problem Details retry_after must be a safe integer >= 0");
  }
  if (
    "doc_url" in value &&
    !isHttpUrl(value.doc_url)
  ) {
    throw new TypeError("Problem Details doc_url must be an http or https URL");
  }
  if (!isJsonValue(value)) {
    throw new TypeError("Problem Details extensions must be valid JSON");
  }
  return value as ProblemDetails;
}

export class EvalRankApiError extends Error {
  readonly status: number;
  readonly problem: ProblemDetails;
  readonly retryAfter: number | null;

  constructor(status: number, problem: ProblemDetails, retryAfter: number | null = null) {
    super(`EvalRank API error ${status}: ${problem.title ?? "request failed"}`);
    this.name = "EvalRankApiError";
    this.status = status;
    this.problem = problem;
    this.retryAfter = retryAfter;
  }
}

export class EvalRankClient {
  readonly baseUrl: string;

  constructor(baseUrl: string) {
    const parsed = new URL(baseUrl);
    if (!["http:", "https:"].includes(parsed.protocol) || !parsed.host) {
      throw new TypeError("baseUrl must be an http or https URL");
    }
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  async useCases(): Promise<UseCaseCatalog> {
    return verifyUseCaseCatalog(await this.requestJson<unknown>("/v1/use-cases"));
  }

  async benchmarkHealth(): Promise<BenchmarkHealth> {
    return verifyBenchmarkHealthSemantics(
      await this.requestJson<unknown>("/v1/benchmark-health"),
    );
  }

  async leaderboard(useCase: string): Promise<Leaderboard> {
    requireSlug(useCase, "useCase");
    const response = await this.requestJson<Leaderboard>(`/v1/leaderboard/${useCase}`);
    await verifyLeaderboardSemantics(response);
    return response;
  }

  async entity(
    entityType: "agent_system" | "arena_system" | "component_configuration" | "model_configuration" | "system_configuration",
    slug: string,
    explorerView?: ExplorerViewIdentity,
  ): Promise<EntityDetail> {
    if (![
      "agent_system",
      "arena_system",
      "component_configuration",
      "model_configuration",
      "system_configuration",
    ].includes(entityType)) {
      throw new TypeError("entityType is not a public evaluated-configuration kind");
    }
    if (!/^[a-z0-9]+(?:[._:-][a-z0-9]+)*$/.test(slug)) {
      throw new TypeError("slug must be a canonical public entity slug or configuration ID");
    }
    const selector = explorerView === undefined ? "" : `?${explorerViewSearch(explorerView)}`;
    const response = await this.requestJson<EntityDetail>(`/v1/entities/${entityType}/${slug}${selector}`);
    await verifyEntityDetailSemantics(response);
    verifyRequestedExplorerView(response, explorerView);
    return response;
  }

  async compare(useCase: string, entities: string[], explorerView?: ExplorerViewIdentity): Promise<CompareResult> {
    requireSlug(useCase, "useCase");
    if (!Array.isArray(entities) || entities.length < 2 || entities.length > 4) {
      throw new TypeError("entities must contain two to four references");
    }
    if (new Set(entities).size !== entities.length) {
      throw new TypeError("entities must be unique");
    }
    if (entities.some((entity) => !/^(agent_system|arena_system|component_configuration|model_configuration|system_configuration):[a-z0-9]+(?:[._:-][a-z0-9]+)*$/.test(entity))) {
      throw new TypeError("entities contains an invalid evaluated-configuration reference");
    }
    const search = new URLSearchParams({
      use_case: useCase,
      entities: entities.join(","),
    });
    if (explorerView !== undefined) {
      requireExplorerView(explorerView);
      search.set("benchmark_family_id", explorerView.benchmark_family_id);
      search.set("feed_id", explorerView.feed_id);
    }
    const response = await this.requestJson<CompareResult>(`/v1/compare?${search}`);
    await verifyCompareResultSemantics(response);
    verifyRequestedExplorerView(response, explorerView);
    return response;
  }

  async decide(
    query: DecisionQueryV2,
    options: { share?: boolean } = {},
  ): Promise<DecisionReceiptV2> {
    if (options.share !== undefined && typeof options.share !== "boolean") {
      throw new TypeError("share must be a boolean");
    }
    const parsed = parseDecisionQueryV2(query);
    const response = await this.requestJson<unknown>(
      options.share ? "/v1/decisions?share=true" : "/v1/decisions",
      {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: canonicalJson(parsed),
      },
    );
    return parseDecisionReceiptV2(response);
  }

  async decisionReceipt(receiptId: string): Promise<DecisionReceiptV2> {
    if (!/^receipt_[0-9a-f]{64}$/.test(receiptId)) {
      throw new TypeError("receiptId must be receipt_<64 lowercase hex characters>");
    }
    const response = await this.requestJson<unknown>(`/v1/decisions/${receiptId}`);
    return parseDecisionReceiptV2(response);
  }

  private async requestJson<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        Accept: "application/json, application/problem+json",
        ...init.headers,
      },
    });
    const body: unknown = await response.json();
    if (!response.ok) {
      const problem = parseProblemDetails(body);
      if (problem.status !== response.status) {
        throw new TypeError("Problem Details status does not match the HTTP response");
      }
      throw new EvalRankApiError(response.status, problem, retryAfter(response.headers));
    }
    return body as T;
  }
}

function verifyRequestedExplorerView(
  response: EntityDetail | CompareResult,
  requested: ExplorerViewIdentity | undefined,
): void {
  if (
    requested !== undefined
    && (
      response.explorer_view === null
      || response.explorer_view.benchmark_family_id !== requested.benchmark_family_id
      || response.explorer_view.feed_id !== requested.feed_id
    )
  ) {
    throw new TypeError("response explorer_view does not match the explicit selector");
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactFields(value: Record<string, unknown>, fields: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...fields].sort();
  return actual.length === expected.length && actual.every((field, index) => field === expected[index]);
}

function isUtcSecondTimestamp(value: unknown): value is string {
  if (typeof value !== "string" || value.startsWith("0000-") || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) {
    return false;
  }
  const parsed = new Date(value);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString() === `${value.slice(0, -1)}.000Z`;
}

function uriReference(value: unknown, name: string): string {
  if (
    typeof value !== "string"
    || !/^[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+$/.test(value)
    || /%(?![0-9A-Fa-f]{2})/.test(value)
  ) {
    throw new TypeError(`Problem Details ${name} must be a valid URI reference`);
  }
  try {
    const parsed = new URL(value, "https://evalrank.invalid");
    if ((/^https?:\/\//.test(value) || value.startsWith("//")) && parsed.host.length === 0) {
      throw new TypeError();
    }
  } catch {
    throw new TypeError(`Problem Details ${name} must be a valid URI reference`);
  }
  return value;
}

function isHttpUrl(value: unknown): value is string {
  if (typeof value !== "string" || !/^https?:\/\//.test(value)) {
    return false;
  }
  try {
    const parsed = new URL(value);
    return ["http:", "https:"].includes(parsed.protocol) && parsed.host.length > 0;
  } catch {
    return false;
  }
}

function isJsonValue(value: unknown): boolean {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return true;
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }
  if (isRecord(value)) {
    return Object.values(value).every(isJsonValue);
  }
  return false;
}

function retryAfter(headers: Headers): number | null {
  const value = headers.get("Retry-After");
  if (value === null) {
    return null;
  }
  const trimmed = value.trim();
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

function requireSlug(value: string, name: string): void {
  if (typeof value !== "string" || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value)) {
    throw new TypeError(`${name} must be a canonical slug`);
  }
}

function requireExplorerView(value: ExplorerViewIdentity): void {
  if (typeof value !== "object" || value === null) throw new TypeError("explorerView must be an object");
  requireSlug(value.benchmark_family_id, "benchmark_family_id");
  requireSlug(value.feed_id, "feed_id");
}

function explorerViewSearch(value: ExplorerViewIdentity): URLSearchParams {
  requireExplorerView(value);
  return new URLSearchParams({
    benchmark_family_id: value.benchmark_family_id,
    feed_id: value.feed_id,
  });
}

export * from "./decision-contracts.ts";
export * from "./aggregation-identity.ts";
