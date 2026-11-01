from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, ClassVar
from urllib.parse import urlparse

from evalrank_core.canonical_json import MAX_SAFE_INTEGER, restricted_jcs


USE_CASE_ENTITY_KINDS = {"model", "tool", "agent"}
USE_CASE_RANK_POLICIES = {"ranked", "veto_overlay"}
PROBLEM_CODES = {
    "rate_limited",
    "upstream_timeout",
    "validation",
    "not_found",
    "methodology_stale",
    "internal",
    "unauthorized",
    "forbidden",
    "via_not_supported",
}
_PUBLIC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_METHODOLOGY_VERSION_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}\.[1-9]\d*\.([a-z0-9]+-)*[a-z0-9]+$"
)
_PROBLEM_DETAIL_FIELDS = {
    "type",
    "title",
    "status",
    "detail",
    "instance",
    "code",
    "retriable",
    "retry_after",
    "field",
    "request_id",
    "doc_url",
}
_URI_REFERENCE_RE = re.compile(r"^[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+$")
_INVALID_PERCENT_ESCAPE_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")


@dataclass(frozen=True)
class CapabilityFingerprintInput:
    """Portable discovery identity input, independent of ranking or decisions."""

    object: ClassVar[str] = "capability_fingerprint"

    id_scheme: str
    canonical_id: str
    entity_kind: str
    declared_capability_shape: dict[str, Any]

    def __post_init__(self) -> None:
        for name in ("id_scheme", "canonical_id", "entity_kind"):
            _require_nonempty_string(name, getattr(self, name))
        if not isinstance(self.declared_capability_shape, dict) or not self.declared_capability_shape:
            raise ValueError("declared_capability_shape is required")
        _require_string_keys("declared_capability_shape", self.declared_capability_shape)
        _normalize_json_object("declared_capability_shape", self.declared_capability_shape)

    def fingerprint(self) -> str:
        return hashlib.sha256(restricted_jcs(self._hash_input())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            **self._hash_input(),
            "capability_fingerprint": self.fingerprint(),
        }

    def _hash_input(self) -> dict[str, Any]:
        return {
            "id_scheme": self.id_scheme,
            "canonical_id": self.canonical_id,
            "entity_kind": self.entity_kind,
            "declared_capability_shape": _normalize_json_object(
                "declared_capability_shape", self.declared_capability_shape
            ),
        }


@dataclass(frozen=True)
class RawEntry:
    """Portable source-discovery record, never ranking or publication truth."""

    object: ClassVar[str] = "raw_entry"

    source: str
    source_id: str
    entity_kind: str
    canonical_id: str
    raw_metadata: dict[str, Any]
    declared_capability_shape: dict[str, Any]
    fetched_at: str

    def __post_init__(self) -> None:
        for name in ("source", "source_id", "entity_kind", "canonical_id"):
            _require_nonempty_string(name, getattr(self, name))
        _require_public_timestamp("fetched_at", self.fetched_at)
        if not self.declared_capability_shape:
            raise ValueError("declared_capability_shape is required")
        for name, value in (
            ("raw_metadata", self.raw_metadata),
            ("declared_capability_shape", self.declared_capability_shape),
        ):
            if not isinstance(value, dict):
                raise ValueError(f"{name} must be a JSON object")
            _require_string_keys(name, value)
            _normalize_json_object(name, value)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(restricted_jcs(self._hash_input())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            **self._hash_input(),
            "fetched_at": self.fetched_at,
            "content_hash": self.content_hash,
        }

    def _hash_input(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_id": self.source_id,
            "entity_kind": self.entity_kind,
            "canonical_id": self.canonical_id,
            "raw_metadata": _normalize_json_object("raw_metadata", self.raw_metadata),
            "declared_capability_shape": _normalize_json_object(
                "declared_capability_shape", self.declared_capability_shape
            ),
        }


@dataclass(frozen=True)
class UseCase:
    object: ClassVar[str] = "use_case"

    id: str
    name: str
    definition: str
    entity_kinds: tuple[str, ...]
    rank_policy: str = "ranked"
    is_overlay: bool = False

    def __post_init__(self) -> None:
        for name in ("id", "name", "definition"):
            _require_nonempty_string(name, getattr(self, name))
        if not isinstance(self.entity_kinds, tuple) or not self.entity_kinds:
            raise ValueError("entity_kinds is required")
        if len(set(self.entity_kinds)) != len(self.entity_kinds):
            raise ValueError("entity_kinds must be unique")
        if any(kind not in USE_CASE_ENTITY_KINDS for kind in self.entity_kinds):
            raise ValueError(f"entity_kinds must be one of {sorted(USE_CASE_ENTITY_KINDS)}")
        if self.rank_policy not in USE_CASE_RANK_POLICIES:
            raise ValueError(f"rank_policy must be one of {sorted(USE_CASE_RANK_POLICIES)}")
        if not isinstance(self.is_overlay, bool):
            raise ValueError("is_overlay must be a boolean")
        if self.is_overlay != (self.rank_policy == "veto_overlay"):
            raise ValueError("overlay and rank_policy must agree")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> UseCase:
        fields = {
            "object",
            "id",
            "name",
            "definition",
            "entity_kinds",
            "rank_policy",
            "is_overlay",
        }
        if not isinstance(payload, dict) or set(payload) != fields:
            raise ValueError("use_case fields are invalid")
        if payload["object"] != cls.object:
            raise ValueError("use_case object is invalid")
        entity_kinds = payload["entity_kinds"]
        if not isinstance(entity_kinds, list):
            raise ValueError("entity_kinds must be an array")
        return cls(
            id=payload["id"],
            name=payload["name"],
            definition=payload["definition"],
            entity_kinds=tuple(entity_kinds),
            rank_policy=payload["rank_policy"],
            is_overlay=payload["is_overlay"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "id": self.id,
            "name": self.name,
            "definition": self.definition,
            "entity_kinds": list(self.entity_kinds),
            "rank_policy": self.rank_policy,
            "is_overlay": self.is_overlay,
        }


@dataclass(frozen=True)
class UseCaseCatalog:
    object: ClassVar[str] = "use_case_catalog"

    methodology_version: str
    generated_at: str
    use_cases: tuple[UseCase, ...]

    def __post_init__(self) -> None:
        _require_methodology_version(self.methodology_version)
        _require_public_timestamp("generated_at", self.generated_at)
        if not isinstance(self.use_cases, tuple) or not self.use_cases:
            raise ValueError("use_cases is required")
        if any(not isinstance(use_case, UseCase) for use_case in self.use_cases):
            raise TypeError("use_cases must contain UseCase values")
        identifiers = [use_case.id for use_case in self.use_cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate use_case id")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> UseCaseCatalog:
        fields = {"object", "methodology_version", "generated_at", "use_cases"}
        if not isinstance(payload, dict) or set(payload) != fields:
            raise ValueError("use_case_catalog fields are invalid")
        if payload["object"] != cls.object:
            raise ValueError("use_case_catalog object is invalid")
        use_cases = payload["use_cases"]
        if not isinstance(use_cases, list):
            raise ValueError("use_cases must be an array")
        return cls(
            methodology_version=payload["methodology_version"],
            generated_at=payload["generated_at"],
            use_cases=tuple(UseCase.from_dict(row) for row in use_cases),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "methodology_version": self.methodology_version,
            "generated_at": self.generated_at,
            "use_cases": [use_case.to_dict() for use_case in self.use_cases],
        }


@dataclass(frozen=True)
class ProblemDetails:
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: str | None = None
    retriable: bool | None = None
    retry_after: int | None = None
    extensions: dict[str, Any] = field(default_factory=dict)
    field: str | None = None
    request_id: str | None = None
    doc_url: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProblemDetails:
        if not isinstance(payload, dict):
            raise TypeError("Problem Details payload must be a JSON object")
        _require_string_keys("Problem Details payload", payload)
        required = {"type", "title", "status", "detail"}
        missing = required - set(payload)
        if missing:
            raise ValueError(
                "Problem Details payload is missing " + ", ".join(sorted(missing))
            )
        for name in (_PROBLEM_DETAIL_FIELDS - required) & set(payload):
            if payload[name] is None:
                raise ValueError(f"{name} must be omitted instead of null")
        extensions = {
            key: value for key, value in payload.items() if key not in _PROBLEM_DETAIL_FIELDS
        }
        known = {key: payload[key] for key in _PROBLEM_DETAIL_FIELDS if key in payload}
        return cls(**known, extensions=extensions)

    def __post_init__(self) -> None:
        _require_uri_reference("type", self.type)
        for name in ("title", "detail"):
            _require_nonempty_string(name, getattr(self, name))
        if (
            not isinstance(self.status, int)
            or isinstance(self.status, bool)
            or not 400 <= self.status <= 599
        ):
            raise ValueError("status must be an integer from 400 to 599")
        if self.instance is not None:
            _require_uri_reference("instance", self.instance)
        for name in ("field", "request_id"):
            value = getattr(self, name)
            if value is not None:
                _require_nonempty_string(name, value)
        if self.doc_url is not None:
            _require_http_url("doc_url", self.doc_url)
        if self.code is not None and self.code not in PROBLEM_CODES:
            raise ValueError(f"code must be one of {sorted(PROBLEM_CODES)}")
        if self.retriable is not None and not isinstance(self.retriable, bool):
            raise ValueError("retriable must be a boolean")
        if self.retry_after is not None and (
            not isinstance(self.retry_after, int)
            or isinstance(self.retry_after, bool)
            or not 0 <= self.retry_after <= MAX_SAFE_INTEGER
        ):
            raise ValueError("retry_after must be a safe integer >= 0")
        if not isinstance(self.extensions, dict):
            raise ValueError("extensions must be a JSON object")
        if set(self.extensions) & _PROBLEM_DETAIL_FIELDS:
            raise ValueError("extensions must not override Problem Details fields")
        _require_string_keys("extensions", self.extensions)
        _normalize_json_object("extensions", self.extensions)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
        }
        for name in (
            "instance",
            "code",
            "retriable",
            "retry_after",
            "field",
            "request_id",
            "doc_url",
        ):
            value = getattr(self, name)
            if value is not None:
                payload[name] = value
        payload.update(_normalize_json_object("extensions", self.extensions))
        return payload


def _require_nonempty_string(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} is required")


def _require_methodology_version(value: str) -> None:
    if not isinstance(value, str) or not _METHODOLOGY_VERSION_RE.fullmatch(value):
        raise ValueError("methodology_version must match YYYY-MM-DD.SEQ.slug")
    try:
        date.fromisoformat(value.split(".", 1)[0])
    except ValueError as exc:
        raise ValueError("methodology_version must match YYYY-MM-DD.SEQ.slug") from exc


def _require_public_timestamp(name: str, value: str) -> None:
    if not isinstance(value, str) or not _PUBLIC_TIMESTAMP_RE.fullmatch(value):
        raise ValueError(f"{name} must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must match YYYY-MM-DDTHH:MM:SSZ") from exc


def _require_http_url(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an http or https URL")
    _require_uri_reference(name, value)
    parsed = urlparse(value)
    try:
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise ValueError(f"{name} must be an http or https URL") from exc
    if (
        not value.startswith(("http://", "https://"))
        or parsed.scheme not in {"http", "https"}
        or not hostname
    ):
        raise ValueError(f"{name} must be an http or https URL")


def _require_uri_reference(name: str, value: Any) -> None:
    if (
        not isinstance(value, str)
        or not value
        or _URI_REFERENCE_RE.fullmatch(value) is None
        or _INVALID_PERCENT_ESCAPE_RE.search(value) is not None
    ):
        raise ValueError(f"{name} must be a valid URI reference")
    try:
        parsed = urlparse(value)
        if value.startswith(("http://", "https://", "//")) and not parsed.netloc:
            raise ValueError
        if parsed.netloc:
            parsed.port
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid URI reference") from exc


def _require_string_keys(name: str, value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{name} keys must be strings")
            _require_string_keys(f"{name}.{key}", child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _require_string_keys(name, child)


def _normalize_json_object(name: str, value: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON serializable") from exc
