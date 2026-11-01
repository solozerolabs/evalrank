"""Portable EvalRank provenance and decision contracts.

These objects are storage-free public contracts. They deliberately separate
what was evaluated from where a configuration can be bought today. A decision
receipt answers a query with a callable pick and its priced band, or an
abstain with reasons, and its identity is the hash of its restricted canonical
JSON body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from types import MappingProxyType
from typing import Any, ClassVar, Mapping
from urllib.parse import urlparse

from evalrank_core.canonical_json import MAX_SAFE_INTEGER, canonical_json, sha256_hex


_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_ID_RE = re.compile(r"^artifact_[0-9a-f]{64}$")
_RUN_ARTIFACT_ROLE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_CONFIGURATION_ID_RE = re.compile(r"^config_[0-9a-f]{64}$")
_OBSERVATION_ID_RE = re.compile(r"^obs_[A-Za-z0-9][A-Za-z0-9._:-]*$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_MEDIA_TYPE_RE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
_DECIMAL_RE = re.compile(
    r"^(?:0|[1-9]\d*)(?:\.\d*[1-9])?$|^-(?:0\.\d*[1-9]|[1-9]\d*(?:\.\d*[1-9])?)$"
)

IDENTITY_TRIPLES = {
    ("model_configuration", "direct_prompt", "model-configuration-v1"),
    ("agent_system", "agentic", "agent-system-v1"),
    ("system_configuration", "system", "system-configuration-v1"),
    ("component_configuration", "retrieval", "component-configuration-v1"),
    ("arena_system", "crowd_pairwise", "arena-system-v1"),
}
INTERVAL_METHODS = {
    "reported",
    "bootstrap_percentile",
    "bootstrap_bca",
    "clopper_pearson",
    "wilson",
    "normal_approximation",
    "credible_interval",
}


@dataclass(frozen=True, slots=True, kw_only=True)
class AdapterMetadataV1:
    schema_version: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        _require_string("schema_version", self.schema_version)
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a JSON object")
        plain = dict(self.payload)
        canonical_json(plain)
        object.__setattr__(self, "payload", MappingProxyType(_copy_json_object(plain)))

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "payload": _thaw_json(self.payload)}

    @classmethod
    def from_dict(cls, value: Any) -> "AdapterMetadataV1":
        payload = _closed(value, required=("schema_version", "payload"))
        return cls(schema_version=payload["schema_version"], payload=payload["payload"])


@dataclass(frozen=True, slots=True, kw_only=True)
class TrialPolicyV1:
    attempts_per_item: int
    seed_strategy: str
    seed: int | None

    def __post_init__(self) -> None:
        _require_safe_integer("attempts_per_item", self.attempts_per_item, minimum=1)
        _require_enum("seed_strategy", self.seed_strategy, {"fixed", "derived", "upstream"})
        if self.seed_strategy == "fixed":
            _require_safe_integer("seed", self.seed)
        elif self.seed is not None:
            raise ValueError("seed must be null unless seed_strategy is fixed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempts_per_item": self.attempts_per_item,
            "seed_strategy": self.seed_strategy,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TrialPolicyV1":
        payload = _closed(value, required=("attempts_per_item", "seed_strategy", "seed"))
        return cls(**payload)


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceArtifactV1:
    object: ClassVar[str] = "source_artifact"
    schema_version: ClassVar[str] = "1"

    source_artifact_id: str
    canonical_url: str
    upstream_version: str
    content_sha256: str
    byte_length: int
    media_type: str
    fetched_at: str

    def __post_init__(self) -> None:
        _require_hash("content_sha256", self.content_sha256)
        if self.source_artifact_id != f"artifact_{self.content_sha256}":
            raise ValueError("source_artifact_id must be artifact_<content_sha256>")
        _require_http_url("canonical_url", self.canonical_url)
        _require_string("upstream_version", self.upstream_version)
        _require_safe_integer("byte_length", self.byte_length, minimum=0)
        if not isinstance(self.media_type, str) or not _MEDIA_TYPE_RE.fullmatch(self.media_type):
            raise ValueError("media_type must be an RFC media type without parameters")
        _parse_timestamp("fetched_at", self.fetched_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "schema_version": self.schema_version,
            "source_artifact_id": self.source_artifact_id,
            "canonical_url": self.canonical_url,
            "upstream_version": self.upstream_version,
            "content_sha256": self.content_sha256,
            "byte_length": self.byte_length,
            "media_type": self.media_type,
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "SourceArtifactV1":
        payload = _closed(
            value,
            required=(
                "object",
                "schema_version",
                "source_artifact_id",
                "canonical_url",
                "upstream_version",
                "content_sha256",
                "byte_length",
                "media_type",
                "fetched_at",
            ),
        )
        _envelope(payload, cls.object)
        return cls(**_without_envelope(payload))


@dataclass(frozen=True, slots=True, kw_only=True)
class RunInputArtifactV1:
    """One exact retained parser input with a stable source-owned role."""

    role: str
    source_artifact_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, str) or not _RUN_ARTIFACT_ROLE_RE.fullmatch(self.role):
            raise ValueError("artifact input role must be lower_snake_case ASCII")
        _require_pattern("source_artifact_id", self.source_artifact_id, _ARTIFACT_ID_RE)

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "source_artifact_id": self.source_artifact_id}

    @classmethod
    def from_dict(cls, value: Any) -> "RunInputArtifactV1":
        return cls(**_closed(value, required=("role", "source_artifact_id")))


@dataclass(frozen=True, slots=True, kw_only=True)
class RunProvenanceV1:
    object: ClassVar[str] = "run_provenance"
    schema_version: ClassVar[str] = "1"

    run_id: str
    benchmark_family_id: str
    feed_id: str
    source_artifacts: tuple[RunInputArtifactV1, ...]
    parser_id: str
    parser_version: str
    started_at: str
    completed_at: str
    harness_version: str | None = None
    environment_digest: str | None = None
    scorer_version: str | None = None
    trial_policy: TrialPolicyV1 | None = None
    adapter_metadata: AdapterMetadataV1 | None = None

    def __post_init__(self) -> None:
        for name in ("run_id", "benchmark_family_id", "feed_id", "parser_id", "parser_version"):
            _require_string(name, getattr(self, name))
        if not isinstance(self.source_artifacts, tuple) or not self.source_artifacts:
            raise ValueError("source_artifacts must be a non-empty tuple")
        if any(not isinstance(item, RunInputArtifactV1) for item in self.source_artifacts):
            raise TypeError("source_artifacts must contain RunInputArtifactV1 values")
        roles = tuple(item.role for item in self.source_artifacts)
        artifact_ids = tuple(item.source_artifact_id for item in self.source_artifacts)
        if roles != tuple(sorted(roles)):
            raise ValueError("source_artifacts must be sorted by role")
        if len(set(roles)) != len(roles) or len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("source_artifact roles and IDs must be unique")
        if roles.count("primary") != 1:
            raise ValueError("source_artifacts must contain exactly one primary role")
        started = _parse_timestamp("started_at", self.started_at)
        completed = _parse_timestamp("completed_at", self.completed_at)
        if completed < started:
            raise ValueError("completed_at must be on or after started_at")
        for name in ("harness_version", "environment_digest", "scorer_version"):
            _require_nullable_string(name, getattr(self, name))
        if self.trial_policy is not None and not isinstance(self.trial_policy, TrialPolicyV1):
            raise TypeError("trial_policy must be TrialPolicyV1 or null")
        if self.adapter_metadata is not None and not isinstance(self.adapter_metadata, AdapterMetadataV1):
            raise TypeError("adapter_metadata must be AdapterMetadataV1 or null")

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "benchmark_family_id": self.benchmark_family_id,
            "feed_id": self.feed_id,
            "source_artifacts": [item.to_dict() for item in self.source_artifacts],
            "parser_id": self.parser_id,
            "parser_version": self.parser_version,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "harness_version": self.harness_version,
            "environment_digest": self.environment_digest,
            "scorer_version": self.scorer_version,
            "trial_policy": None if self.trial_policy is None else self.trial_policy.to_dict(),
            "adapter_metadata": None if self.adapter_metadata is None else self.adapter_metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RunProvenanceV1":
        raw = _mapping(value)
        if "source_artifacts" not in raw:
            raise ValueError("missing required field: source_artifacts")
        payload = _closed(
            raw,
            required=(
                "object",
                "schema_version",
                "run_id",
                "benchmark_family_id",
                "feed_id",
                "source_artifacts",
                "parser_id",
                "parser_version",
                "started_at",
                "completed_at",
                "harness_version",
                "environment_digest",
                "scorer_version",
                "trial_policy",
                "adapter_metadata",
            ),
        )
        _envelope(payload, cls.object)
        values = _without_envelope(payload)
        if not isinstance(values["source_artifacts"], list):
            raise TypeError("source_artifacts must be an array")
        values["source_artifacts"] = tuple(
            RunInputArtifactV1.from_dict(item) for item in values["source_artifacts"]
        )
        values["trial_policy"] = (
            None if values["trial_policy"] is None else TrialPolicyV1.from_dict(values["trial_policy"])
        )
        values["adapter_metadata"] = (
            None
            if values["adapter_metadata"] is None
            else AdapterMetadataV1.from_dict(values["adapter_metadata"])
        )
        return cls(**values)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProportionMetricV1:
    kind: ClassVar[str] = "proportion"
    value: str
    numerator: int | None
    denominator: int | None

    def __post_init__(self) -> None:
        numeric = _require_decimal("value", self.value)
        _require_unit_interval("value", numeric)
        _validate_count_pair("numerator", self.numerator, "denominator", self.denominator)
        if self.numerator is not None:
            _require_rounded_ratio("value", self.value, self.numerator, self.denominator)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value, "numerator": self.numerator, "denominator": self.denominator}

    @classmethod
    def from_dict(cls, value: Any) -> "ProportionMetricV1":
        payload = _closed(value, required=("kind", "value", "numerator", "denominator"))
        _kind(payload, cls.kind)
        return cls(**_without_kind(payload))


@dataclass(frozen=True, slots=True, kw_only=True)
class ContinuousMetricV1:
    kind: ClassVar[str] = "continuous"
    value: str
    unit: str
    n_items: int | None

    def __post_init__(self) -> None:
        _require_decimal("value", self.value)
        _require_string("unit", self.unit)
        _require_nullable_safe_integer("n_items", self.n_items, minimum=1)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value, "unit": self.unit, "n_items": self.n_items}

    @classmethod
    def from_dict(cls, value: Any) -> "ContinuousMetricV1":
        payload = _closed(value, required=("kind", "value", "unit", "n_items"))
        _kind(payload, cls.kind)
        return cls(**_without_kind(payload))


@dataclass(frozen=True, slots=True, kw_only=True)
class PassAtKMetricV1:
    kind: ClassVar[str] = "pass_at_k"
    value: str
    k: int
    successful_items: int | None
    evaluated_items: int | None

    def __post_init__(self) -> None:
        numeric = _require_decimal("value", self.value)
        _require_unit_interval("value", numeric)
        _require_safe_integer("k", self.k, minimum=1)
        _validate_count_pair("successful_items", self.successful_items, "evaluated_items", self.evaluated_items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "k": self.k,
            "successful_items": self.successful_items,
            "evaluated_items": self.evaluated_items,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "PassAtKMetricV1":
        payload = _closed(value, required=("kind", "value", "k", "successful_items", "evaluated_items"))
        _kind(payload, cls.kind)
        return cls(**_without_kind(payload))


@dataclass(frozen=True, slots=True, kw_only=True)
class PairwisePreferenceMetricV1:
    kind: ClassVar[str] = "pairwise_preference"
    value: str
    scale: str
    comparison_count: int | None

    def __post_init__(self) -> None:
        _require_decimal("value", self.value)
        _require_enum("scale", self.scale, {"probability", "elo", "margin"})
        _require_nullable_safe_integer("comparison_count", self.comparison_count, minimum=1)
        if self.scale == "probability":
            _require_unit_interval("value", Decimal(self.value))

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value, "scale": self.scale, "comparison_count": self.comparison_count}

    @classmethod
    def from_dict(cls, value: Any) -> "PairwisePreferenceMetricV1":
        payload = _closed(value, required=("kind", "value", "scale", "comparison_count"))
        _kind(payload, cls.kind)
        return cls(**_without_kind(payload))


@dataclass(frozen=True, slots=True, kw_only=True)
class RankOnlyMetricV1:
    kind: ClassVar[str] = "rank_only"
    rank: int
    candidate_count: int | None

    def __post_init__(self) -> None:
        _require_safe_integer("rank", self.rank, minimum=1)
        _require_nullable_safe_integer("candidate_count", self.candidate_count, minimum=1)
        if self.candidate_count is not None and self.rank > self.candidate_count:
            raise ValueError("rank must not exceed candidate_count")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "rank": self.rank, "candidate_count": self.candidate_count}

    @classmethod
    def from_dict(cls, value: Any) -> "RankOnlyMetricV1":
        payload = _closed(value, required=("kind", "rank", "candidate_count"))
        _kind(payload, cls.kind)
        return cls(**_without_kind(payload))


MetricV1 = ProportionMetricV1 | ContinuousMetricV1 | PassAtKMetricV1 | PairwisePreferenceMetricV1 | RankOnlyMetricV1


@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownUncertaintyV1:
    kind: ClassVar[str] = "unknown"

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind}

    @classmethod
    def from_dict(cls, value: Any) -> "UnknownUncertaintyV1":
        payload = _closed(value, required=("kind",))
        _kind(payload, cls.kind)
        return cls()


@dataclass(frozen=True, slots=True, kw_only=True)
class StandardErrorUncertaintyV1:
    kind: ClassVar[str] = "standard_error"
    value: str

    def __post_init__(self) -> None:
        if _require_decimal("value", self.value) < 0:
            raise ValueError("value must be nonnegative")

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "value": self.value}

    @classmethod
    def from_dict(cls, value: Any) -> "StandardErrorUncertaintyV1":
        payload = _closed(value, required=("kind", "value"))
        _kind(payload, cls.kind)
        return cls(**_without_kind(payload))


@dataclass(frozen=True, slots=True, kw_only=True)
class IntervalUncertaintyV1:
    kind: ClassVar[str] = "interval"
    low: str
    high: str
    confidence_level: str
    method: str

    def __post_init__(self) -> None:
        low = _require_decimal("low", self.low)
        high = _require_decimal("high", self.high)
        if low > high:
            raise ValueError("low must be <= high")
        level = _require_decimal("confidence_level", self.confidence_level)
        if level <= 0 or level > 1:
            raise ValueError("confidence_level must be in (0, 1]")
        _require_enum("method", self.method, INTERVAL_METHODS)

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "low": self.low,
            "high": self.high,
            "confidence_level": self.confidence_level,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "IntervalUncertaintyV1":
        payload = _closed(value, required=("kind", "low", "high", "confidence_level", "method"))
        _kind(payload, cls.kind)
        return cls(**_without_kind(payload))


UncertaintyV1 = UnknownUncertaintyV1 | StandardErrorUncertaintyV1 | IntervalUncertaintyV1


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationV1:
    object: ClassVar[str] = "observation"
    schema_version: ClassVar[str] = "1"

    observation_id: str
    evaluated_configuration_id: str
    metric: MetricV1
    uncertainty: UncertaintyV1
    provenance: RunProvenanceV1

    def __post_init__(self) -> None:
        _require_pattern("observation_id", self.observation_id, _OBSERVATION_ID_RE)
        _require_pattern("evaluated_configuration_id", self.evaluated_configuration_id, _CONFIGURATION_ID_RE)
        if not isinstance(self.metric, (ProportionMetricV1, ContinuousMetricV1, PassAtKMetricV1, PairwisePreferenceMetricV1, RankOnlyMetricV1)):
            raise TypeError("metric must be a typed metric")
        if not isinstance(self.uncertainty, (UnknownUncertaintyV1, StandardErrorUncertaintyV1, IntervalUncertaintyV1)):
            raise TypeError("uncertainty must be a typed uncertainty")
        if not isinstance(self.provenance, RunProvenanceV1):
            raise TypeError("provenance must be RunProvenanceV1")
        if isinstance(self.metric, RankOnlyMetricV1) and not isinstance(self.uncertainty, UnknownUncertaintyV1):
            raise ValueError("rank_only observations require unknown uncertainty")
        if isinstance(self.uncertainty, IntervalUncertaintyV1) and hasattr(self.metric, "value"):
            metric_value = Decimal(self.metric.value)
            if not Decimal(self.uncertainty.low) <= metric_value <= Decimal(self.uncertainty.high):
                raise ValueError("uncertainty interval must contain metric value")

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "schema_version": self.schema_version,
            "observation_id": self.observation_id,
            "evaluated_configuration_id": self.evaluated_configuration_id,
            "metric": self.metric.to_dict(),
            "uncertainty": self.uncertainty.to_dict(),
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ObservationV1":
        payload = _closed(
            value,
            required=("object", "schema_version", "observation_id", "evaluated_configuration_id", "metric", "uncertainty", "provenance"),
        )
        _envelope(payload, cls.object)
        values = _without_envelope(payload)
        values["metric"] = _metric_from_dict(values["metric"])
        values["uncertainty"] = _uncertainty_from_dict(values["uncertainty"])
        values["provenance"] = RunProvenanceV1.from_dict(values["provenance"])
        return cls(**values)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigurationPassportV1:
    object: ClassVar[str] = "configuration_passport"
    schema_version: ClassVar[str] = "1"

    entity_kind: str
    canonical_name: str
    revision: str
    interaction_policy: str
    configuration_passport_class: str
    harness: str | None
    scaffold: str | None
    tools: tuple[str, ...] = ()
    quantization: str | None = None
    system_prompt_policy: str | None = None
    environment: str | None = None

    def __post_init__(self) -> None:
        _require_identity_triple(self.entity_kind, self.interaction_policy, self.configuration_passport_class)
        _require_string("canonical_name", self.canonical_name)
        _require_string("revision", self.revision)
        for name in ("harness", "scaffold", "quantization", "system_prompt_policy", "environment"):
            _require_nullable_string(name, getattr(self, name))
        if self.entity_kind == "agent_system":
            _require_string("harness", self.harness)
            _require_string("scaffold", self.scaffold)
        object.__setattr__(self, "tools", _normalize_string_set("tools", self.tools, allow_empty=True))

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "schema_version": self.schema_version,
            "entity_kind": self.entity_kind,
            "canonical_name": self.canonical_name,
            "revision": self.revision,
            "interaction_policy": self.interaction_policy,
            "configuration_passport_class": self.configuration_passport_class,
            "harness": self.harness,
            "scaffold": self.scaffold,
            "tools": list(self.tools),
            "quantization": self.quantization,
            "system_prompt_policy": self.system_prompt_policy,
            "environment": self.environment,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ConfigurationPassportV1":
        payload = _closed(
            value,
            required=(
                "object", "schema_version", "entity_kind", "canonical_name", "revision",
                "interaction_policy", "configuration_passport_class", "harness", "scaffold",
                "tools", "quantization", "system_prompt_policy", "environment",
            ),
        )
        _envelope(payload, cls.object)
        values = _without_envelope(payload)
        values["tools"] = _array_to_tuple("tools", values["tools"])
        return cls(**values)


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluatedConfigurationV1:
    object: ClassVar[str] = "evaluated_configuration"
    schema_version: ClassVar[str] = "1"

    evaluated_configuration_id: str
    passport: ConfigurationPassportV1

    def __post_init__(self) -> None:
        if not isinstance(self.passport, ConfigurationPassportV1):
            raise TypeError("passport must be ConfigurationPassportV1")
        expected = f"config_{sha256_hex(self.passport.to_dict())}"
        if self.evaluated_configuration_id != expected:
            raise ValueError("evaluated_configuration_id must hash the exact passport")

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "schema_version": self.schema_version,
            "evaluated_configuration_id": self.evaluated_configuration_id,
            "passport": self.passport.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "EvaluatedConfigurationV1":
        payload = _closed(value, required=("object", "schema_version", "evaluated_configuration_id", "passport"))
        _envelope(payload, cls.object)
        return cls(
            evaluated_configuration_id=payload["evaluated_configuration_id"],
            passport=ConfigurationPassportV1.from_dict(payload["passport"]),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextFactV1:
    context_window_tokens: int
    observed_at: str
    expires_at: str
    source_artifact_id: str

    def __post_init__(self) -> None:
        _require_safe_integer("context_window_tokens", self.context_window_tokens, minimum=1)
        _validate_dated_fact(self.observed_at, self.expires_at, self.source_artifact_id)

    def to_dict(self) -> dict[str, Any]:
        return _fact_dict(self, {"context_window_tokens": self.context_window_tokens})

    @classmethod
    def from_dict(cls, value: Any) -> "ContextFactV1":
        return cls(**_closed(value, required=("context_window_tokens", "observed_at", "expires_at", "source_artifact_id")))


@dataclass(frozen=True, slots=True, kw_only=True)
class AvailabilityFactV1:
    status: str
    observed_at: str
    expires_at: str
    source_artifact_id: str

    def __post_init__(self) -> None:
        _require_enum("status", self.status, {"available", "limited", "unavailable"})
        _validate_dated_fact(self.observed_at, self.expires_at, self.source_artifact_id)

    def to_dict(self) -> dict[str, Any]:
        return _fact_dict(self, {"status": self.status})

    @classmethod
    def from_dict(cls, value: Any) -> "AvailabilityFactV1":
        return cls(**_closed(value, required=("status", "observed_at", "expires_at", "source_artifact_id")))


@dataclass(frozen=True, slots=True, kw_only=True)
class CacheWriteUsageV1:
    ttl_seconds: int
    tokens: int

    def __post_init__(self) -> None:
        _require_safe_integer("ttl_seconds", self.ttl_seconds, minimum=1)
        _require_safe_integer("tokens", self.tokens, minimum=1)

    def to_dict(self) -> dict[str, int]:
        return {"ttl_seconds": self.ttl_seconds, "tokens": self.tokens}

    @classmethod
    def from_dict(cls, value: Any) -> "CacheWriteUsageV1":
        return cls(**_closed(value, required=("ttl_seconds", "tokens")))


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageProfileV1:
    basis: str
    uncached_input_tokens: int
    cached_read_tokens: int
    output_tokens: int
    cache_writes: tuple[CacheWriteUsageV1, ...]
    cache_storage_token_seconds: int

    def __post_init__(self) -> None:
        _require_enum("basis", self.basis, {"measured", "estimated"})
        for name in (
            "uncached_input_tokens",
            "cached_read_tokens",
            "output_tokens",
            "cache_storage_token_seconds",
        ):
            _require_safe_integer(name, getattr(self, name), minimum=0)
        object.__setattr__(
            self,
            "cache_writes",
            _normalize_typed_records(
                "cache_writes",
                self.cache_writes,
                CacheWriteUsageV1,
                lambda row: (row.ttl_seconds,),
            ),
        )
        if not (
            self.uncached_input_tokens
            or self.cached_read_tokens
            or self.output_tokens
            or self.cache_writes
        ):
            raise ValueError("usage profile must describe a non-zero workload")

    @property
    def has_cache_usage(self) -> bool:
        return bool(
            self.cached_read_tokens
            or self.cache_writes
            or self.cache_storage_token_seconds
        )

    @property
    def total_input_tokens(self) -> int:
        return self.uncached_input_tokens + self.cached_read_tokens + sum(
            row.tokens for row in self.cache_writes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "basis": self.basis,
            "uncached_input_tokens": self.uncached_input_tokens,
            "cached_read_tokens": self.cached_read_tokens,
            "output_tokens": self.output_tokens,
            "cache_writes": [row.to_dict() for row in self.cache_writes],
            "cache_storage_token_seconds": self.cache_storage_token_seconds,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "UsageProfileV1":
        payload = _closed(
            value,
            required=(
                "basis",
                "uncached_input_tokens",
                "cached_read_tokens",
                "output_tokens",
                "cache_writes",
                "cache_storage_token_seconds",
            ),
        )
        payload["cache_writes"] = tuple(
            CacheWriteUsageV1.from_dict(row)
            for row in _array("cache_writes", payload["cache_writes"])
        )
        return cls(**payload)


@dataclass(frozen=True, slots=True, kw_only=True)
class CacheWriteRateV1:
    ttl_seconds: int
    microusd_per_million_tokens: int

    def __post_init__(self) -> None:
        _require_safe_integer("ttl_seconds", self.ttl_seconds, minimum=1)
        _require_safe_integer(
            "microusd_per_million_tokens",
            self.microusd_per_million_tokens,
            minimum=0,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "ttl_seconds": self.ttl_seconds,
            "microusd_per_million_tokens": self.microusd_per_million_tokens,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "CacheWriteRateV1":
        return cls(
            **_closed(
                value,
                required=("ttl_seconds", "microusd_per_million_tokens"),
            )
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PricingScheduleFactV1:
    uncached_input_microusd_per_million_tokens: int
    cached_read_microusd_per_million_tokens: int | None
    output_microusd_per_million_tokens: int
    cache_write_rates: tuple[CacheWriteRateV1, ...]
    cache_storage_microusd_per_million_token_hours: int | None
    observed_at: str
    effective_at: str
    expires_at: str
    source_artifact_id: str

    def __post_init__(self) -> None:
        _require_safe_integer(
            "uncached_input_microusd_per_million_tokens",
            self.uncached_input_microusd_per_million_tokens,
            minimum=0,
        )
        _require_nullable_safe_integer(
            "cached_read_microusd_per_million_tokens",
            self.cached_read_microusd_per_million_tokens,
            minimum=0,
        )
        _require_safe_integer(
            "output_microusd_per_million_tokens",
            self.output_microusd_per_million_tokens,
            minimum=0,
        )
        object.__setattr__(
            self,
            "cache_write_rates",
            _normalize_typed_records(
                "cache_write_rates",
                self.cache_write_rates,
                CacheWriteRateV1,
                lambda row: (row.ttl_seconds,),
            ),
        )
        _require_nullable_safe_integer(
            "cache_storage_microusd_per_million_token_hours",
            self.cache_storage_microusd_per_million_token_hours,
            minimum=0,
        )
        _validate_dated_fact(self.observed_at, self.expires_at, self.source_artifact_id)
        if _parse_timestamp("expires_at", self.expires_at) <= _parse_timestamp(
            "effective_at", self.effective_at
        ):
            raise ValueError("expires_at must be after effective_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "uncached_input_microusd_per_million_tokens": self.uncached_input_microusd_per_million_tokens,
            "cached_read_microusd_per_million_tokens": self.cached_read_microusd_per_million_tokens,
            "output_microusd_per_million_tokens": self.output_microusd_per_million_tokens,
            "cache_write_rates": [row.to_dict() for row in self.cache_write_rates],
            "cache_storage_microusd_per_million_token_hours": self.cache_storage_microusd_per_million_token_hours,
            "observed_at": self.observed_at,
            "effective_at": self.effective_at,
            "expires_at": self.expires_at,
            "source_artifact_id": self.source_artifact_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "PricingScheduleFactV1":
        payload = _closed(
            value,
            required=(
                "uncached_input_microusd_per_million_tokens",
                "cached_read_microusd_per_million_tokens",
                "output_microusd_per_million_tokens",
                "cache_write_rates",
                "cache_storage_microusd_per_million_token_hours",
                "observed_at",
                "effective_at",
                "expires_at",
                "source_artifact_id",
            ),
        )
        payload["cache_write_rates"] = tuple(
            CacheWriteRateV1.from_dict(row)
            for row in _array("cache_write_rates", payload["cache_write_rates"])
        )
        return cls(**payload)


def projected_cost_microusd(
    usage: UsageProfileV1,
    pricing: PricingScheduleFactV1,
) -> int | None:
    """Return the exact cost of ``usage`` under ``pricing`` (rounded up), or ``None`` when a needed rate is missing."""

    if not isinstance(usage, UsageProfileV1):
        raise TypeError("usage must be UsageProfileV1")
    if not isinstance(pricing, PricingScheduleFactV1):
        raise TypeError("pricing must be PricingScheduleFactV1")
    if usage.cached_read_tokens and pricing.cached_read_microusd_per_million_tokens is None:
        return None
    cache_write_rates = {
        row.ttl_seconds: row.microusd_per_million_tokens
        for row in pricing.cache_write_rates
    }
    if any(row.ttl_seconds not in cache_write_rates for row in usage.cache_writes):
        return None
    if (
        usage.cache_storage_token_seconds
        and pricing.cache_storage_microusd_per_million_token_hours is None
    ):
        return None

    cached_read_cost_numerator = 0
    if usage.cached_read_tokens:
        cached_read_rate = pricing.cached_read_microusd_per_million_tokens
        if cached_read_rate is None:
            return None
        cached_read_cost_numerator = usage.cached_read_tokens * cached_read_rate
    storage_cost_numerator = 0
    if usage.cache_storage_token_seconds:
        storage_rate = pricing.cache_storage_microusd_per_million_token_hours
        if storage_rate is None:
            return None
        storage_cost_numerator = usage.cache_storage_token_seconds * storage_rate

    token_rate_microusd = (
        usage.uncached_input_tokens
        * pricing.uncached_input_microusd_per_million_tokens
        + cached_read_cost_numerator
        + usage.output_tokens * pricing.output_microusd_per_million_tokens
        + sum(
            row.tokens * cache_write_rates[row.ttl_seconds]
            for row in usage.cache_writes
        )
    )
    numerator = token_rate_microusd * 3_600 + storage_cost_numerator
    denominator = 3_600_000_000
    quotient, remainder = divmod(numerator, denominator)
    result = quotient + (1 if remainder else 0)
    _require_safe_integer("computed projected cost", result, minimum=0)
    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class ServingOfferV1:
    object: ClassVar[str] = "serving_offer"
    schema_version: ClassVar[str] = "1"

    serving_offer_id: str
    provider_id: str
    sku: str
    region: str
    context: ContextFactV1
    availability: AvailabilityFactV1
    pricing: PricingScheduleFactV1

    def __post_init__(self) -> None:
        for name in ("serving_offer_id", "provider_id", "sku", "region"):
            _require_string(name, getattr(self, name))
        if not self.serving_offer_id.startswith("offer_"):
            raise ValueError("serving_offer_id must start with offer_")
        if not isinstance(self.context, ContextFactV1):
            raise TypeError("context must be ContextFactV1")
        if not isinstance(self.availability, AvailabilityFactV1):
            raise TypeError("availability must be AvailabilityFactV1")
        if not isinstance(self.pricing, PricingScheduleFactV1):
            raise TypeError("pricing must be PricingScheduleFactV1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "schema_version": self.schema_version,
            "serving_offer_id": self.serving_offer_id,
            "provider_id": self.provider_id,
            "sku": self.sku,
            "region": self.region,
            "context": self.context.to_dict(),
            "availability": self.availability.to_dict(),
            "pricing": self.pricing.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ServingOfferV1":
        payload = _closed(value, required=("object", "schema_version", "serving_offer_id", "provider_id", "sku", "region", "context", "availability", "pricing"))
        _envelope(payload, cls.object)
        return cls(
            serving_offer_id=payload["serving_offer_id"],
            provider_id=payload["provider_id"],
            sku=payload["sku"],
            region=payload["region"],
            context=ContextFactV1.from_dict(payload["context"]),
            availability=AvailabilityFactV1.from_dict(payload["availability"]),
            pricing=PricingScheduleFactV1.from_dict(payload["pricing"]),
        )


REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
DECISION_OBJECTIVES = {"lowest_cost_within_top_set", "capability_top_set"}
DECISION_APIS = {"chat_completions", "responses"}
ABSTAIN_REASONS = {"no_ranked_candidate", "no_eligible_offer", "stale_evidence", "not_a_model_cell"}
EXCLUSION_CODES = {
    "ambiguous_identity",
    "effort_not_accepted",
    "api_not_supported",
    "no_serving_offer",
    "cost_unmeasured",
    "effort_gap_too_large",
    "constraints_not_met",
}
LOCK_STATUSES = {"admitted", "held", "rejected", "unlocked"}
USAGE_BASES = {"caller", "default_agent_task_mix"}
SUPPORTED_VIA = ("openai", "openrouter")
"""Call surfaces with a probed effort vocabulary; any other ``via`` is a 422 ``via_not_supported``."""
COMPARISON_LEVEL_SOURCE = "comparison_level"
PPM = 1_000_000
_VIA_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SNAPSHOT_ID_RE = re.compile(r"^explorer_.+$")


def _default_agent_task_mix() -> UsageProfileV1:
    return UsageProfileV1(
        basis="estimated",
        uncached_input_tokens=1_000,
        cached_read_tokens=8_000,
        output_tokens=500,
        cache_writes=(),
        cache_storage_token_seconds=0,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionQueryV2:
    """What the caller asks. Only sent fields serialize; defaults stay implicit."""

    object: ClassVar[str] = "decision_query"
    schema_version: ClassVar[str] = "2"

    cell_id: str
    objective: str
    via: str | None = None
    provider_ids: tuple[str, ...] | None = None
    api: str | None = None
    reasoning_effort: str | None = None
    regions: tuple[str, ...] | None = None
    minimum_context_tokens: int | None = None
    usage_profile: UsageProfileV1 | None = None

    def __post_init__(self) -> None:
        _require_string("cell_id", self.cell_id)
        _require_enum("objective", self.objective, DECISION_OBJECTIVES)
        if self.via is not None:
            _require_pattern("via", self.via, _VIA_RE)
        for name in ("provider_ids", "regions"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, _normalize_string_set(name, getattr(self, name)))
        if self.api is not None:
            _require_enum("api", self.api, DECISION_APIS)
        if self.reasoning_effort is not None:
            _require_enum("reasoning_effort", self.reasoning_effort, set(REASONING_EFFORTS))
        _require_nullable_safe_integer("minimum_context_tokens", self.minimum_context_tokens, minimum=1)
        if self.usage_profile is not None and not isinstance(self.usage_profile, UsageProfileV1):
            raise TypeError("usage_profile must be UsageProfileV1 or null")

    @property
    def resolved_via(self) -> str:
        """The call surface: the sent ``via``, else openai for ``provider_ids == ["openai"]``, else openrouter."""
        if self.via is not None:
            return self.via
        return "openai" if self.provider_ids == ("openai",) else "openrouter"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "object": self.object,
            "schema_version": self.schema_version,
            "cell_id": self.cell_id,
            "objective": self.objective,
        }
        for name in _QUERY_OPTIONAL:
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, tuple):
                payload[name] = list(value)
            elif isinstance(value, UsageProfileV1):
                payload[name] = value.to_dict()
            else:
                payload[name] = value
        return payload

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> "DecisionQueryV2":
        payload = _closed(value, required=("schema_version", "cell_id", "objective"), optional=("object", *_QUERY_OPTIONAL))
        _envelope({"object": cls.object, **payload}, cls.object, cls.schema_version)
        for name in _QUERY_OPTIONAL:
            if name in payload and payload[name] is None:
                raise ValueError(f"{name} must not be null; omit it instead")
        values = _without_envelope(payload)
        for name in ("provider_ids", "regions"):
            if name in values:
                values[name] = _array_to_tuple(name, values[name])
        if "usage_profile" in values:
            values["usage_profile"] = UsageProfileV1.from_dict(values["usage_profile"])
        return cls(**values)


_QUERY_OPTIONAL = (
    "via",
    "provider_ids",
    "api",
    "reasoning_effort",
    "regions",
    "minimum_context_tokens",
    "usage_profile",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionFamilyV2:
    family_id: str
    lock_status: str
    weight_ppm: int
    stale_at: str | None

    def __post_init__(self) -> None:
        _require_string("family_id", self.family_id)
        _require_enum("lock_status", self.lock_status, LOCK_STATUSES)
        _require_safe_integer("weight_ppm", self.weight_ppm, minimum=0)
        if self.stale_at is not None:
            _parse_timestamp("stale_at", self.stale_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "lock_status": self.lock_status,
            "weight_ppm": self.weight_ppm,
            "stale_at": self.stale_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "DecisionFamilyV2":
        return cls(**_closed(value, required=("family_id", "lock_status", "weight_ppm", "stale_at")))


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionPriceV2:
    """List price of the serving offer, micro-USD per million tokens; null when the host does not list it."""

    input_microusd_per_million: int | None
    cached_input_microusd_per_million: int | None
    output_microusd_per_million: int | None

    def __post_init__(self) -> None:
        for name in _PRICE_FIELDS:
            _require_nullable_safe_integer(name, getattr(self, name), minimum=0)

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in _PRICE_FIELDS}

    @classmethod
    def from_dict(cls, value: Any) -> "DecisionPriceV2":
        return cls(**_closed(value, required=_PRICE_FIELDS))


_PRICE_FIELDS = (
    "input_microusd_per_million",
    "cached_input_microusd_per_million",
    "output_microusd_per_million",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class EffortMultiplierV2:
    """Cost per task at the selection's effort / cost per task at the comparison level, on one cost board."""

    multiplier_ppm: int
    source: str

    def __post_init__(self) -> None:
        _require_safe_integer("multiplier_ppm", self.multiplier_ppm, minimum=0)
        _require_string("source", self.source)
        if self.source == COMPARISON_LEVEL_SOURCE and self.multiplier_ppm != PPM:
            raise ValueError("a comparison_level multiplier must be exactly 1 (1000000 ppm)")

    def to_dict(self) -> dict[str, Any]:
        return {"multiplier_ppm": self.multiplier_ppm, "source": self.source}

    @classmethod
    def from_dict(cls, value: Any) -> "EffortMultiplierV2":
        return cls(**_closed(value, required=("multiplier_ppm", "source")))


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionCaveatV2:
    """``effort_substituted`` (a board measured another level; ``gap_ppm`` is the curve's gap) or ``cost_unmeasured``."""

    code: str
    measured_effort: str | None = None
    gap_ppm: int | None = None

    def __post_init__(self) -> None:
        _require_enum("code", self.code, {"effort_substituted", "cost_unmeasured"})
        if self.code == "effort_substituted":
            _require_enum("measured_effort", self.measured_effort, set(REASONING_EFFORTS))
            _require_safe_integer("gap_ppm", self.gap_ppm, minimum=0)
        elif self.measured_effort is not None or self.gap_ppm is not None:
            raise ValueError("cost_unmeasured carries no measured_effort or gap_ppm")

    def to_dict(self) -> dict[str, Any]:
        if self.code == "cost_unmeasured":
            return {"code": self.code}
        return {"code": self.code, "measured_effort": self.measured_effort, "gap_ppm": self.gap_ppm}

    @classmethod
    def from_dict(cls, value: Any) -> "DecisionCaveatV2":
        payload = _mapping(value)
        if payload.get("code") == "effort_substituted":
            return cls(**_closed(payload, required=("code", "measured_effort", "gap_ppm")))
        return cls(**_closed(payload, required=("code",)))


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionSelectionV2:
    """One configuration, callable as returned: send ``model_id`` with ``reasoning_effort`` on ``api``."""

    model_id: str
    display_name: str
    provider_id: str
    serving_offer_id: str
    reasoning_effort: str
    api: str
    capability_ratio_ppm: int
    family_coverage: int
    price: DecisionPriceV2
    effort_multiplier: EffortMultiplierV2 | None
    projected_cost_microusd: int | None
    latency_p50_ms: int | None
    caveats: tuple[DecisionCaveatV2, ...]

    def __post_init__(self) -> None:
        for name in ("model_id", "display_name", "provider_id", "serving_offer_id"):
            _require_string(name, getattr(self, name))
        _require_enum("reasoning_effort", self.reasoning_effort, set(REASONING_EFFORTS))
        _require_enum("api", self.api, DECISION_APIS)
        _require_safe_integer("capability_ratio_ppm", self.capability_ratio_ppm, minimum=0)
        if self.capability_ratio_ppm > PPM:
            raise ValueError("capability_ratio_ppm must not exceed 1000000")
        _require_safe_integer("family_coverage", self.family_coverage, minimum=1)
        if not isinstance(self.price, DecisionPriceV2):
            raise TypeError("price must be DecisionPriceV2")
        if self.effort_multiplier is not None and not isinstance(self.effort_multiplier, EffortMultiplierV2):
            raise TypeError("effort_multiplier must be EffortMultiplierV2 or null")
        _require_nullable_safe_integer("projected_cost_microusd", self.projected_cost_microusd, minimum=0)
        _require_nullable_safe_integer("latency_p50_ms", self.latency_p50_ms, minimum=0)
        object.__setattr__(
            self,
            "caveats",
            _normalize_typed_records("caveats", self.caveats, DecisionCaveatV2, lambda row: (row.code,)),
        )
        codes = {row.code for row in self.caveats}
        if (self.projected_cost_microusd is None) != ("cost_unmeasured" in codes):
            raise ValueError("cost_unmeasured caveat is required exactly when projected_cost_microusd is null")
        if self.projected_cost_microusd is not None and self.effort_multiplier is None:
            raise ValueError("a priced selection needs its effort_multiplier")
        for caveat in self.caveats:
            if caveat.code == "effort_substituted" and caveat.measured_effort == self.reasoning_effort:
                raise ValueError("effort_substituted must name a measured effort other than the selection's")

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider_id": self.provider_id,
            "serving_offer_id": self.serving_offer_id,
            "reasoning_effort": self.reasoning_effort,
            "api": self.api,
            "capability_ratio_ppm": self.capability_ratio_ppm,
            "family_coverage": self.family_coverage,
            "price": self.price.to_dict(),
            "effort_multiplier": None if self.effort_multiplier is None else self.effort_multiplier.to_dict(),
            "projected_cost_microusd": self.projected_cost_microusd,
            "latency_p50_ms": self.latency_p50_ms,
            "caveats": [row.to_dict() for row in self.caveats],
        }

    @classmethod
    def from_dict(cls, value: Any) -> "DecisionSelectionV2":
        payload = _closed(
            value,
            required=(
                "model_id",
                "display_name",
                "provider_id",
                "serving_offer_id",
                "reasoning_effort",
                "api",
                "capability_ratio_ppm",
                "family_coverage",
                "price",
                "effort_multiplier",
                "projected_cost_microusd",
                "latency_p50_ms",
                "caveats",
            ),
        )
        payload["price"] = DecisionPriceV2.from_dict(payload["price"])
        if payload["effort_multiplier"] is not None:
            payload["effort_multiplier"] = EffortMultiplierV2.from_dict(payload["effort_multiplier"])
        payload["caveats"] = tuple(DecisionCaveatV2.from_dict(row) for row in _array("caveats", payload["caveats"]))
        return cls(**payload)


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionExclusionV2:
    model_key: str
    code: str
    reasoning_effort: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        _require_string("model_key", self.model_key)
        _require_enum("code", self.code, EXCLUSION_CODES)
        if self.reasoning_effort is not None:
            _require_enum("reasoning_effort", self.reasoning_effort, set(REASONING_EFFORTS))
        if self.detail is not None and not isinstance(self.detail, str):
            raise TypeError("detail must be a string")

    @property
    def sort_key(self) -> tuple[str, str, str]:
        return (self.model_key, self.reasoning_effort or "", self.code)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"model_key": self.model_key, "code": self.code}
        if self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "DecisionExclusionV2":
        return cls(**_closed(value, required=("model_key", "code"), optional=("reasoning_effort", "detail")))


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionUsageV2:
    """The usage profile the receipt priced, and whether the caller sent it."""

    basis: str
    profile: UsageProfileV1

    def __post_init__(self) -> None:
        _require_enum("basis", self.basis, USAGE_BASES)
        if not isinstance(self.profile, UsageProfileV1):
            raise TypeError("profile must be UsageProfileV1")

    @classmethod
    def for_query(cls, query: DecisionQueryV2) -> "DecisionUsageV2":
        if query.usage_profile is None:
            return cls(basis="default_agent_task_mix", profile=DEFAULT_AGENT_TASK_MIX)
        return cls(basis="caller", profile=query.usage_profile)

    def to_dict(self) -> dict[str, Any]:
        return {"basis": self.basis, "profile": self.profile.to_dict()}

    @classmethod
    def from_dict(cls, value: Any) -> "DecisionUsageV2":
        payload = _closed(value, required=("basis", "profile"))
        return cls(basis=payload["basis"], profile=UsageProfileV1.from_dict(payload["profile"]))


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionReceiptV2:
    """``pick``: ``selections[0]`` is the pick and the rest is the band in order. ``abstain``: no selection, one or more reasons."""

    object: ClassVar[str] = "decision_receipt"
    schema_version: ClassVar[str] = "2"

    receipt_id: str
    query: DecisionQueryV2
    decided_at: str
    outcome: str
    snapshot_ids: tuple[str, ...]
    families: tuple[DecisionFamilyV2, ...]
    selections: tuple[DecisionSelectionV2, ...]
    exclusions: tuple[DecisionExclusionV2, ...]
    usage_profile: DecisionUsageV2
    abstain_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.query, DecisionQueryV2):
            raise TypeError("query must be DecisionQueryV2")
        _parse_timestamp("decided_at", self.decided_at)
        _require_enum("outcome", self.outcome, {"pick", "abstain"})
        snapshot_ids = _normalize_string_set("snapshot_ids", self.snapshot_ids, allow_empty=True)
        for snapshot_id in snapshot_ids:
            _require_pattern("snapshot_ids item", snapshot_id, _SNAPSHOT_ID_RE)
        object.__setattr__(self, "snapshot_ids", snapshot_ids)
        object.__setattr__(
            self,
            "families",
            _normalize_typed_records("families", self.families, DecisionFamilyV2, lambda row: (row.family_id,)),
        )
        if not isinstance(self.selections, tuple) or any(
            not isinstance(row, DecisionSelectionV2) for row in self.selections
        ):
            raise TypeError("selections must be a tuple of DecisionSelectionV2")
        configurations = [(row.serving_offer_id, row.reasoning_effort) for row in self.selections]
        if len(set(configurations)) != len(configurations):
            raise ValueError("selections must not repeat a (serving_offer_id, reasoning_effort) configuration")
        object.__setattr__(
            self,
            "exclusions",
            _normalize_typed_records("exclusions", self.exclusions, DecisionExclusionV2, lambda row: row.sort_key),
        )
        if not isinstance(self.usage_profile, DecisionUsageV2):
            raise TypeError("usage_profile must be DecisionUsageV2")
        if self.usage_profile != DecisionUsageV2.for_query(self.query):
            raise ValueError("usage_profile must echo the query's profile (caller) or the default agent task mix")
        reasons = _normalize_string_set("abstain_reasons", self.abstain_reasons, allow_empty=True)
        for reason in reasons:
            _require_enum("abstain_reasons item", reason, ABSTAIN_REASONS)
        object.__setattr__(self, "abstain_reasons", reasons)
        if self.outcome == "pick":
            self._validate_pick()
        elif self.selections or not self.abstain_reasons:
            raise ValueError("abstain carries no selection and at least one abstain reason")
        expected = f"receipt_{sha256_hex(self.to_body_dict())}"
        if self.receipt_id != expected:
            raise ValueError("receipt_id must hash the full receipt body except receipt_id")

    def _validate_pick(self) -> None:
        if not self.selections or self.abstain_reasons:
            raise ValueError("pick carries at least one selection and no abstain reason")
        if not self.snapshot_ids:
            raise ValueError("pick must cite the explorer snapshots it ranked")
        pinned = self.query.reasoning_effort
        if pinned is not None and any(row.reasoning_effort != pinned for row in self.selections):
            raise ValueError("a pinned reasoning_effort admits only configurations at that level")
        if self.query.api is not None and any(row.api != self.query.api for row in self.selections):
            raise ValueError("every selection must use the query's api")
        if self.query.provider_ids is not None and any(
            row.provider_id not in self.query.provider_ids for row in self.selections
        ):
            raise ValueError("every selection must come from the query's provider_ids")
        pick = self.selections[0]
        if self.query.objective == "lowest_cost_within_top_set":
            costs = [row.projected_cost_microusd for row in self.selections]
            if any(cost is None for cost in costs):
                raise ValueError("lowest_cost_within_top_set selects priced configurations only")
            if pick.projected_cost_microusd != min(costs):
                raise ValueError("lowest_cost_within_top_set picks the cheapest configuration of the band")
        elif pick.capability_ratio_ppm != max(row.capability_ratio_ppm for row in self.selections):
            raise ValueError("capability_top_set picks the highest-scoring configuration")

    @classmethod
    def create(
        cls,
        *,
        query: DecisionQueryV2,
        decided_at: str,
        outcome: str,
        snapshot_ids: tuple[str, ...],
        families: tuple[DecisionFamilyV2, ...],
        selections: tuple[DecisionSelectionV2, ...],
        exclusions: tuple[DecisionExclusionV2, ...],
        abstain_reasons: tuple[str, ...],
    ) -> "DecisionReceiptV2":
        """Build a receipt; ``usage_profile`` is derived from the query and ``receipt_id`` from the body."""
        values = {
            "query": query,
            "decided_at": decided_at,
            "outcome": outcome,
            "snapshot_ids": snapshot_ids,
            "families": families,
            "selections": selections,
            "exclusions": exclusions,
            "usage_profile": DecisionUsageV2.for_query(query),
            "abstain_reasons": abstain_reasons,
        }
        unchecked = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(unchecked, name, value)
        return cls(receipt_id=f"receipt_{sha256_hex(unchecked.to_body_dict())}", **values)

    def to_body_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "schema_version": self.schema_version,
            "query": self.query.to_dict(),
            "decided_at": self.decided_at,
            "outcome": self.outcome,
            "snapshot_ids": sorted(self.snapshot_ids, key=lambda value: value.encode("utf-16-be")),
            "families": [row.to_dict() for row in sorted(self.families, key=lambda row: _portable_sort_key((row.family_id,)))],
            "selections": [row.to_dict() for row in self.selections],
            "exclusions": [row.to_dict() for row in sorted(self.exclusions, key=lambda row: _portable_sort_key(row.sort_key))],
            "usage_profile": self.usage_profile.to_dict(),
            "abstain_reasons": sorted(self.abstain_reasons),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.to_body_dict(), "receipt_id": self.receipt_id}

    @classmethod
    def from_dict(cls, value: Any) -> "DecisionReceiptV2":
        payload = _closed(
            value,
            required=(
                "object",
                "schema_version",
                "receipt_id",
                "query",
                "decided_at",
                "outcome",
                "snapshot_ids",
                "families",
                "selections",
                "exclusions",
                "usage_profile",
                "abstain_reasons",
            ),
        )
        _envelope(payload, cls.object, cls.schema_version)
        return cls(
            receipt_id=payload["receipt_id"],
            query=DecisionQueryV2.from_dict(payload["query"]),
            decided_at=payload["decided_at"],
            outcome=payload["outcome"],
            snapshot_ids=_array_to_tuple("snapshot_ids", payload["snapshot_ids"]),
            families=tuple(DecisionFamilyV2.from_dict(row) for row in _array("families", payload["families"])),
            selections=tuple(DecisionSelectionV2.from_dict(row) for row in _array("selections", payload["selections"])),
            exclusions=tuple(DecisionExclusionV2.from_dict(row) for row in _array("exclusions", payload["exclusions"])),
            usage_profile=DecisionUsageV2.from_dict(payload["usage_profile"]),
            abstain_reasons=_array_to_tuple("abstain_reasons", payload["abstain_reasons"]),
        )


def _metric_from_dict(value: Any) -> MetricV1:
    payload = _mapping(value)
    kind = payload.get("kind")
    parser = {
        "proportion": ProportionMetricV1.from_dict,
        "continuous": ContinuousMetricV1.from_dict,
        "pass_at_k": PassAtKMetricV1.from_dict,
        "pairwise_preference": PairwisePreferenceMetricV1.from_dict,
        "rank_only": RankOnlyMetricV1.from_dict,
    }.get(kind)
    if parser is None:
        raise ValueError("metric.kind must be one of the five supported metric kinds")
    return parser(payload)


def _uncertainty_from_dict(value: Any) -> UncertaintyV1:
    payload = _mapping(value)
    kind = payload.get("kind")
    parser = {
        "unknown": UnknownUncertaintyV1.from_dict,
        "standard_error": StandardErrorUncertaintyV1.from_dict,
        "interval": IntervalUncertaintyV1.from_dict,
    }.get(kind)
    if parser is None:
        raise ValueError("uncertainty.kind must be unknown, standard_error, or interval")
    return parser(payload)


def _closed(value: Any, *, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> dict[str, Any]:
    payload = _mapping(value)
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f"missing required field: {missing[0]}")
    unknown = set(payload) - set(required) - set(optional)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    return dict(payload)


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("contract value must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        raise TypeError("contract object keys must be strings")
    return value


def _envelope(payload: Mapping[str, Any], object_name: str, schema_version: str = "1") -> None:
    if payload["object"] != object_name:
        raise ValueError(f"object must be {object_name}")
    if payload["schema_version"] != schema_version:
        raise ValueError(f"schema_version must be {schema_version}")


def _without_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in {"object", "schema_version"}}


def _kind(payload: Mapping[str, Any], expected: str) -> None:
    if payload["kind"] != expected:
        raise ValueError(f"kind must be {expected}")


def _without_kind(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "kind"}


def _require_string(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    canonical_json(value)


def _require_nullable_string(name: str, value: Any) -> None:
    if value is not None:
        _require_string(name, value)


def _require_pattern(name: str, value: Any, pattern: re.Pattern[str]) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{name} has an invalid format")


def _require_hash(name: str, value: Any) -> None:
    _require_pattern(name, value, _HEX_RE)


def _require_enum(name: str, value: Any, allowed: set[str]) -> None:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{name} must be one of {sorted(allowed)}")


def _require_safe_integer(name: str, value: Any, *, minimum: int | None = None) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or abs(value) > MAX_SAFE_INTEGER:
        raise ValueError(f"{name} must be a safe integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _require_nullable_safe_integer(name: str, value: Any, *, minimum: int | None = None) -> None:
    if value is not None:
        _require_safe_integer(name, value, minimum=minimum)


def _require_decimal(name: str, value: Any) -> Decimal:
    if not isinstance(value, str) or len(value) > 128 or not _DECIMAL_RE.fullmatch(value):
        raise ValueError(f"{name} must be a canonical decimal string")
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{name} must be a canonical decimal string") from error


def _require_unit_interval(name: str, value: Decimal) -> None:
    if value < 0 or value > 1:
        raise ValueError(f"{name} must be in [0, 1]")


def _validate_count_pair(numerator_name: str, numerator: Any, denominator_name: str, denominator: Any) -> None:
    if (numerator is None) != (denominator is None):
        raise ValueError(f"{numerator_name} and {denominator_name} must both be integers or both be null")
    if numerator is None:
        return
    _require_safe_integer(numerator_name, numerator, minimum=0)
    _require_safe_integer(denominator_name, denominator, minimum=1)
    if numerator > denominator:
        raise ValueError(f"{numerator_name} must not exceed {denominator_name}")


def _parse_timestamp(name: str, value: Any) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP_RE.fullmatch(value):
        raise ValueError(f"{name} must be a UTC timestamp with second precision")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError(f"{name} must be a valid UTC timestamp") from error


def _require_http_url(name: str, value: Any) -> None:
    _require_string(name, value)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"{name} must be a canonical public http(s) URL without credentials or fragment")


def _require_identity_triple(entity_kind: Any, interaction_policy: Any, passport_class: Any) -> None:
    if (entity_kind, interaction_policy, passport_class) not in IDENTITY_TRIPLES:
        raise ValueError("entity_kind, interaction_policy, and configuration_passport_class must be a resolved identity triple")


def _normalize_string_set(name: str, values: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple")
    for value in values:
        _require_string(f"{name} item", value)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")
    if not allow_empty and not values:
        raise ValueError(f"{name} must not be empty")
    return tuple(sorted(values, key=lambda value: value.encode("utf-16-be")))


def _array(name: str, value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be an array")
    return value


def _array_to_tuple(name: str, value: Any) -> tuple[Any, ...]:
    return tuple(_array(name, value))


def _normalize_typed_records(name: str, values: Any, expected_type: type, key) -> tuple[Any, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple")
    if any(not isinstance(value, expected_type) for value in values):
        raise TypeError(f"{name} contains an invalid record")
    keys = [key(value) for value in values]
    if len(set(keys)) != len(keys):
        raise ValueError(f"{name} must be unique")
    return tuple(sorted(values, key=lambda value: _portable_sort_key(key(value))))


def _validate_dated_fact(observed_at: str, expires_at: str, source_artifact_id: str) -> None:
    observed = _parse_timestamp("observed_at", observed_at)
    expires = _parse_timestamp("expires_at", expires_at)
    if expires <= observed:
        raise ValueError("expires_at must be after observed_at")
    _require_pattern("source_artifact_id", source_artifact_id, _ARTIFACT_ID_RE)


def _fact_dict(fact: Any, values: dict[str, Any]) -> dict[str, Any]:
    return {
        **values,
        "observed_at": fact.observed_at,
        "expires_at": fact.expires_at,
        "source_artifact_id": fact.source_artifact_id,
    }


def _copy_json_object(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _copy_json_value(item) for key, item in value.items()}


def _copy_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(_copy_json_object(value))
    if isinstance(value, list):
        return tuple(_copy_json_value(item) for item in value)
    return value


def _portable_sort_key(value: Any) -> bytes:
    parts = value if isinstance(value, tuple) else (value,)
    return canonical_json(list(parts)).encode("utf-16-be")


def _require_rounded_ratio(name: str, value: str, numerator: int, denominator: int) -> None:
    decimal_value = Decimal(value)
    scale = max(0, -decimal_value.as_tuple().exponent)
    if decimal_value * denominator != numerator and scale < 6:
        raise ValueError(
            f"{name} must use at least six fractional digits when counts are not exactly representable"
        )
    quantum = Decimal(1).scaleb(-scale)
    with localcontext() as context:
        context.prec = max(256, scale + 64)
        expected = (Decimal(numerator) / Decimal(denominator)).quantize(
            quantum,
            rounding=ROUND_HALF_EVEN,
        )
    if decimal_value != expected:
        raise ValueError(
            f"{name} must equal numerator / denominator rounded half-even to its declared decimal scale"
        )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


# Built last: UsageProfileV1 validation needs the module helpers above.
DEFAULT_AGENT_TASK_MIX = _default_agent_task_mix()
"""The usage profile a query without ``usage_profile`` is priced at: cache-heavy agent traffic."""
