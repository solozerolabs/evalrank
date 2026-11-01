import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from evalrank_core import (
    ABSTAIN_REASONS,
    DEFAULT_AGENT_TASK_MIX,
    DecisionCaveatV2,
    DecisionExclusionV2,
    DecisionFamilyV2,
    DecisionPriceV2,
    DecisionSelectionV2,
    DecisionUsageV2,
    EffortMultiplierV2,
    REASONING_EFFORTS,
    SUPPORTED_VIA,
    AdapterMetadataV1,
    AvailabilityFactV1,
    CacheWriteRateV1,
    CacheWriteUsageV1,
    CapabilityFingerprintInput,
    ConfigurationPassportV1,
    ContextFactV1,
    ContinuousMetricV1,
    EvaluatedConfigurationV1,
    IntervalUncertaintyV1,
    MAX_SAFE_INTEGER,
    ObservationV1,
    PairwisePreferenceMetricV1,
    PassAtKMetricV1,
    PricingScheduleFactV1,
    PROBLEM_CODES,
    ProblemDetails,
    ProportionMetricV1,
    RankOnlyMetricV1,
    RawEntry,
    RankingGroupSnapshotRefV1,
    RunInputArtifactV1,
    RunProvenanceV1,
    PUBLIC_FIXTURE_KINDS,
    ServingOfferV1,
    SourceArtifactV1,
    SnapshotSetDescriptorV1,
    StandardErrorUncertaintyV1,
    TrialPolicyV1,
    USE_CASE_ENTITY_KINDS,
    USE_CASE_RANK_POLICIES,
    UseCase,
    UseCaseCatalog,
    UnknownUncertaintyV1,
    UsageProfileV1,
    DecisionQueryV2,
    DecisionReceiptV2,
    aggregation_input_document,
    bootstrap_seed_document,
    canonical_json,
    derive_aggregation_input_digest,
    derive_bootstrap_seed,
    projected_cost_microusd,
    restricted_jcs,
    sha256_hex,
    verify_leaderboard_snapshot_set,
    verify_benchmark_health_semantics,
    verify_leaderboard_semantics,
    verify_entity_detail_semantics,
    verify_compare_result_semantics,
    sample_capability_fingerprint_input,
    sample_observation,
    sample_problem_details,
    sample_public_fixture,
    sample_raw_entry,
    sample_use_case_catalog,
)

__version__ = "0.0.0"


class EvalRankApiError(Exception):
    def __init__(self, *, status: int, problem: ProblemDetails, retry_after: int | None = None) -> None:
        self.status = status
        self.problem = problem
        self.retry_after = retry_after
        super().__init__(f"EvalRank API error {status}: {problem.title}")


class EvalRankClient:
    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an http or https URL")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a finite positive number of seconds")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def decide(
        self,
        query: DecisionQueryV2 | dict[str, Any],
        *,
        share: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(share, bool):
            raise TypeError("share must be a boolean")
        parsed_query = (
            query if isinstance(query, DecisionQueryV2) else DecisionQueryV2.from_dict(query)
        )
        body = restricted_jcs(parsed_query.to_dict())
        response = self._request_json(
            "/v1/decisions?share=true" if share else "/v1/decisions",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        return DecisionReceiptV2.from_dict(response).to_dict()

    def decision_receipt(self, receipt_id: str) -> dict[str, Any]:
        if not isinstance(receipt_id, str) or not re.fullmatch(
            r"receipt_[0-9a-f]{64}", receipt_id
        ):
            raise ValueError("receipt_id must be receipt_<64 lowercase hex characters>")
        response = self._request_json(f"/v1/decisions/{receipt_id}")
        return DecisionReceiptV2.from_dict(response).to_dict()

    def use_cases(self) -> dict[str, Any]:
        return UseCaseCatalog.from_dict(self._request_json("/v1/use-cases")).to_dict()

    def benchmark_health(self) -> dict[str, Any]:
        response = self._request_json("/v1/benchmark-health")
        return verify_benchmark_health_semantics(response)

    def leaderboard(self, use_case: str) -> dict[str, Any]:
        _require_slug("use_case", use_case)
        response = self._request_json(f"/v1/leaderboard/{use_case}")
        verify_leaderboard_semantics(response)
        return response

    def entity(
        self,
        entity_type: str,
        slug: str,
        *,
        explorer_view: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        if entity_type not in {
            "agent_system",
            "arena_system",
            "component_configuration",
            "model_configuration",
            "system_configuration",
        }:
            raise ValueError("entity_type is not a public evaluated-configuration kind")
        _require_entity_slug(slug)
        selector = _explorer_view_query(explorer_view)
        response = self._request_json(f"/v1/entities/{entity_type}/{slug}{selector}")
        verify_entity_detail_semantics(response)
        _verify_requested_explorer_view(response, explorer_view)
        return response

    def compare(
        self,
        use_case: str,
        entities: tuple[str, ...],
        *,
        explorer_view: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        _require_slug("use_case", use_case)
        if not isinstance(entities, tuple) or not 2 <= len(entities) <= 4:
            raise ValueError("entities must be a tuple containing two to four references")
        if len(set(entities)) != len(entities):
            raise ValueError("entities must be unique")
        if any(
            not isinstance(entity, str)
            or not re.fullmatch(
                r"(agent_system|arena_system|component_configuration|model_configuration|system_configuration):"
                r"[a-z0-9]+(?:[._:-][a-z0-9]+)*",
                entity,
            )
            for entity in entities
        ):
            raise ValueError("entities contains an invalid evaluated-configuration reference")
        parameters = {"use_case": use_case, "entities": ",".join(entities)}
        if explorer_view is not None:
            family_id, feed_id = _validate_explorer_view(explorer_view)
            parameters.update(benchmark_family_id=family_id, feed_id=feed_id)
        query = urllib.parse.urlencode(parameters)
        response = self._request_json(f"/v1/compare?{query}")
        verify_compare_result_semantics(response)
        _verify_requested_explorer_view(response, explorer_view)
        return response

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        http_request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json, application/problem+json",
                **(headers or {}),
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                raw_problem = json.loads(exc.read().decode("utf-8"))
            finally:
                exc.close()
            try:
                problem = ProblemDetails.from_dict(raw_problem)
            except (TypeError, ValueError) as problem_error:
                raise ValueError("response contained malformed Problem Details") from problem_error
            if problem.status != exc.code:
                raise ValueError("Problem Details status does not match the HTTP response")
            raise EvalRankApiError(status=exc.code, problem=problem, retry_after=_retry_after(exc.headers)) from exc


def _retry_after(headers: Any) -> int | None:
    value = headers.get("Retry-After")
    if value is None:
        return None
    text = str(value).strip()
    if not text.isdigit():
        return None
    return int(text)


def _require_slug(name: str, value: Any) -> None:
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-z0-9]+(?:-[a-z0-9]+)*", value
    ):
        raise ValueError(f"{name} must be a canonical slug")


def _validate_explorer_view(value: tuple[str, str]) -> tuple[str, str]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError("explorer_view must be a benchmark-family/feed tuple")
    _require_slug("benchmark_family_id", value[0])
    _require_slug("feed_id", value[1])
    return value


def _explorer_view_query(value: tuple[str, str] | None) -> str:
    if value is None:
        return ""
    family_id, feed_id = _validate_explorer_view(value)
    return "?" + urllib.parse.urlencode(
        {"benchmark_family_id": family_id, "feed_id": feed_id}
    )


def _verify_requested_explorer_view(
    response: dict[str, Any], requested: tuple[str, str] | None
) -> None:
    if requested is not None and response.get("explorer_view") != {
        "benchmark_family_id": requested[0],
        "feed_id": requested[1],
    }:
        raise ValueError("response explorer_view does not match the explicit selector")


def _require_entity_slug(value: Any) -> None:
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-z0-9]+(?:[._:-][a-z0-9]+)*", value
    ):
        raise ValueError("slug must be a canonical public entity slug or configuration ID")

__all__ = [
    "ABSTAIN_REASONS",
    "DEFAULT_AGENT_TASK_MIX",
    "DecisionCaveatV2",
    "DecisionExclusionV2",
    "DecisionFamilyV2",
    "DecisionPriceV2",
    "DecisionSelectionV2",
    "DecisionUsageV2",
    "EffortMultiplierV2",
    "REASONING_EFFORTS",
    "SUPPORTED_VIA",
    "AdapterMetadataV1",
    "EvalRankApiError",
    "EvalRankClient",
    "CapabilityFingerprintInput",
    "AvailabilityFactV1",
    "CacheWriteRateV1",
    "CacheWriteUsageV1",
    "ConfigurationPassportV1",
    "ContextFactV1",
    "ContinuousMetricV1",
    "EvaluatedConfigurationV1",
    "IntervalUncertaintyV1",
    "MAX_SAFE_INTEGER",
    "ObservationV1",
    "PairwisePreferenceMetricV1",
    "PassAtKMetricV1",
    "PricingScheduleFactV1",
    "PROBLEM_CODES",
    "ProblemDetails",
    "ProportionMetricV1",
    "RankOnlyMetricV1",
    "RawEntry",
    "RankingGroupSnapshotRefV1",
    "RunInputArtifactV1",
    "RunProvenanceV1",
    "PUBLIC_FIXTURE_KINDS",
    "ServingOfferV1",
    "SourceArtifactV1",
    "SnapshotSetDescriptorV1",
    "StandardErrorUncertaintyV1",
    "TrialPolicyV1",
    "USE_CASE_ENTITY_KINDS",
    "USE_CASE_RANK_POLICIES",
    "UseCase",
    "UseCaseCatalog",
    "UnknownUncertaintyV1",
    "UsageProfileV1",
    "DecisionQueryV2",
    "DecisionReceiptV2",
    "aggregation_input_document",
    "bootstrap_seed_document",
    "canonical_json",
    "derive_aggregation_input_digest",
    "derive_bootstrap_seed",
    "projected_cost_microusd",
    "restricted_jcs",
    "sha256_hex",
    "verify_leaderboard_snapshot_set",
    "verify_benchmark_health_semantics",
    "verify_leaderboard_semantics",
    "verify_entity_detail_semantics",
    "verify_compare_result_semantics",
    "sample_capability_fingerprint_input",
    "sample_observation",
    "sample_problem_details",
    "sample_public_fixture",
    "sample_raw_entry",
    "sample_use_case_catalog",
    "__version__",
]
