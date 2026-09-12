"""Portable helpers for content-addressed public read snapshots."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from evalrank_core.canonical_json import MAX_SAFE_INTEGER, sha256_hex
from evalrank_core.decision_contracts import IDENTITY_TRIPLES, EvaluatedConfigurationV1


_MANIFEST_VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.[1-9]\d*$")
_METHODOLOGY_VERSION_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}\.[1-9]\d*\.([a-z0-9]+-)*[a-z0-9]+$"
)
_EVIDENCE_SNAPSHOT_ID_RE = re.compile(r"^(snapshot|explorer)_[0-9a-f]{64}$")
_CONFIGURATION_ID_RE = re.compile(r"^config_[0-9a-f]{64}$")
_CELL_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ARTIFACT_ID_RE = re.compile(r"^artifact_[0-9a-f]{64}$")
_CAVEAT_RE = re.compile(r"^[a-z0-9]+(?:(?:-|_)[a-z0-9]+)*$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_GROUP_STATES = {"active", "preview", "shadow", "quarantined"}
_ENTITY_KINDS = {"agent_system", "arena_system", "component_configuration", "model_configuration", "system_configuration", "unresolved"}
_INTERACTION_POLICIES = {"agentic", "crowd_pairwise", "direct_prompt", "retrieval", "system", "unresolved"}
_PASSPORT_CLASSES = {"agent-system-v1", "arena-system-v1", "component-configuration-v1", "model-configuration-v1", "system-configuration-v1", "unresolved-v1"}
_GAP_CODES = {"calibration_unvalidated", "evidence_stale", "insufficient_configuration_overlap", "insufficient_independent_families", "no_rank_eligible_configurations", "quarantined", "unresolved_identity"}


def verify_benchmark_health_semantics(payload: Any) -> dict[str, Any]:
    """Verify closed per-cell health rows and their count-derived status."""

    if not isinstance(payload, dict):
        raise TypeError("benchmark health must be a JSON object")
    expected = {"object", "schema_version", "manifest_version", "generated_at", "cells"}
    if set(payload) != expected:
        raise ValueError("benchmark health fields are invalid")
    if payload["object"] != "benchmark_health" or payload["schema_version"] != "1":
        raise ValueError("benchmark health envelope is invalid")
    if not isinstance(payload["manifest_version"], str) or not _MANIFEST_VERSION_RE.fullmatch(
        payload["manifest_version"]
    ):
        raise ValueError("benchmark health manifest_version is invalid")
    if not isinstance(payload["generated_at"], str) or not _TIMESTAMP_RE.fullmatch(
        payload["generated_at"]
    ):
        raise ValueError("benchmark health generated_at is invalid")
    try:
        datetime.fromisoformat(payload["generated_at"].removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ValueError("benchmark health generated_at is invalid") from error
    cells = payload["cells"]
    if not isinstance(cells, list) or not cells:
        raise ValueError("benchmark health cells must be a non-empty array")
    cell_ids: set[str] = set()
    count_fields = (
        "ranking_group_count",
        "published_ranking_group_count",
        "benchmark_family_count",
        "candidate_feed_count",
        "implemented_feed_count",
        "admitted_feed_count",
        "rank_eligible_feed_count",
    )
    row_fields = {"cell_id", "status", *count_fields}
    for row in cells:
        if not isinstance(row, dict) or set(row) != row_fields:
            raise ValueError("benchmark health cell fields are invalid")
        cell_id = row["cell_id"]
        if not isinstance(cell_id, str) or not _CELL_ID_RE.fullmatch(cell_id):
            raise ValueError("benchmark health cell_id is invalid")
        if cell_id in cell_ids:
            raise ValueError("benchmark health cell_id values must be unique")
        cell_ids.add(cell_id)
        for field in count_fields:
            value = row[field]
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                or value > MAX_SAFE_INTEGER
            ):
                raise ValueError(f"benchmark health {field} must be a safe nonnegative integer")
        if row["published_ranking_group_count"] > row["ranking_group_count"]:
            raise ValueError("published ranking groups cannot exceed ranking groups")
        if not (
            row["rank_eligible_feed_count"]
            <= row["admitted_feed_count"]
            <= row["implemented_feed_count"]
            <= row["candidate_feed_count"]
        ):
            raise ValueError("benchmark health feed counts must be monotonically nested")
        expected_status = (
            "active"
            if row["published_ranking_group_count"] > 0
            else "preview"
            if row["implemented_feed_count"] > 0
            else "unavailable"
        )
        if row["status"] != expected_status:
            raise ValueError("benchmark health status must match publication and implementation counts")
    return payload


@dataclass(frozen=True, slots=True, kw_only=True)
class RankingGroupSnapshotRefV1:
    """One ranking group's owned evidence snapshot in a snapshot set."""

    ranking_group_id: str
    evidence_snapshot_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.ranking_group_id, str) or not _CELL_ID_RE.fullmatch(
            self.ranking_group_id
        ):
            raise ValueError("ranking_group_id must be a canonical manifest slug")
        if not isinstance(
            self.evidence_snapshot_id, str
        ) or not _EVIDENCE_SNAPSHOT_ID_RE.fullmatch(self.evidence_snapshot_id):
            raise ValueError("evidence_snapshot_id must be snapshot_<sha256> or explorer_<sha256>")

    @property
    def utf16_sort_key(self) -> tuple[bytes, bytes]:
        return (
            self.ranking_group_id.encode("utf-16-be"),
            self.evidence_snapshot_id.encode("utf-16-be"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "ranking_group_id": self.ranking_group_id,
            "evidence_snapshot_id": self.evidence_snapshot_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RankingGroupSnapshotRefV1":
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise TypeError("ranking-group snapshot reference must be a JSON object")
        expected = {"ranking_group_id", "evidence_snapshot_id"}
        if set(value) != expected:
            missing = expected - set(value)
            unknown = set(value) - expected
            detail = (
                "missing " + ", ".join(sorted(missing))
                if missing
                else "unknown " + ", ".join(sorted(unknown))
            )
            raise ValueError(f"ranking-group snapshot reference fields are invalid: {detail}")
        return cls(
            ranking_group_id=value["ranking_group_id"],
            evidence_snapshot_id=value["evidence_snapshot_id"],
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotSetDescriptorV1:
    """The float-free, portable preimage for a cell snapshot-set identity."""

    object: ClassVar[str] = "snapshot_set_descriptor"
    schema_version: ClassVar[str] = "1"

    cell_id: str
    manifest_version: str
    methodology_version: str
    ranking_group_snapshots: tuple[RankingGroupSnapshotRefV1, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cell_id, str) or not _CELL_ID_RE.fullmatch(self.cell_id):
            raise ValueError("cell_id must be a canonical manifest slug")
        if not isinstance(self.manifest_version, str) or not _MANIFEST_VERSION_RE.fullmatch(
            self.manifest_version
        ):
            raise ValueError("manifest_version must match YYYY-MM-DD.N")
        if not isinstance(self.methodology_version, str) or not _METHODOLOGY_VERSION_RE.fullmatch(
            self.methodology_version
        ):
            raise ValueError("methodology_version must match YYYY-MM-DD.N.slug")
        if not isinstance(self.ranking_group_snapshots, tuple) or not self.ranking_group_snapshots:
            raise ValueError("ranking_group_snapshots must be a non-empty tuple")
        if any(
            not isinstance(reference, RankingGroupSnapshotRefV1)
            for reference in self.ranking_group_snapshots
        ):
            raise TypeError(
                "ranking_group_snapshots must contain RankingGroupSnapshotRefV1 values"
            )
        group_ids = [reference.ranking_group_id for reference in self.ranking_group_snapshots]
        snapshot_ids = [
            reference.evidence_snapshot_id for reference in self.ranking_group_snapshots
        ]
        if len(set(group_ids)) != len(group_ids):
            raise ValueError("ranking_group_snapshots must own unique ranking_group_id values")
        if len(set(snapshot_ids)) != len(snapshot_ids):
            raise ValueError(
                "ranking_group_snapshots must own unique evidence_snapshot_id values"
            )
        object.__setattr__(
            self,
            "ranking_group_snapshots",
            tuple(
                sorted(
                    self.ranking_group_snapshots,
                    key=lambda reference: reference.utf16_sort_key,
                )
            ),
        )

    @property
    def snapshot_set_id(self) -> str:
        return f"snapshot_set_{sha256_hex(self.to_dict())}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object,
            "schema_version": self.schema_version,
            "cell_id": self.cell_id,
            "manifest_version": self.manifest_version,
            "methodology_version": self.methodology_version,
            "ranking_group_snapshots": [
                reference.to_dict() for reference in self.ranking_group_snapshots
            ],
        }

    @classmethod
    def from_dict(cls, value: Any) -> "SnapshotSetDescriptorV1":
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise TypeError("snapshot-set descriptor must be a JSON object")
        expected = {
            "object",
            "schema_version",
            "cell_id",
            "manifest_version",
            "methodology_version",
            "ranking_group_snapshots",
        }
        if set(value) != expected:
            missing = expected - set(value)
            unknown = set(value) - expected
            detail = "missing " + ", ".join(sorted(missing)) if missing else "unknown " + ", ".join(sorted(unknown))
            raise ValueError(f"snapshot-set descriptor fields are invalid: {detail}")
        if value["object"] != cls.object or value["schema_version"] != cls.schema_version:
            raise ValueError("snapshot-set descriptor envelope is invalid")
        raw_references = value["ranking_group_snapshots"]
        if not isinstance(raw_references, list):
            raise TypeError("ranking_group_snapshots must be an array")
        references = tuple(
            RankingGroupSnapshotRefV1.from_dict(reference)
            for reference in raw_references
        )
        ordered = tuple(sorted(references, key=lambda reference: reference.utf16_sort_key))
        if references != ordered:
            raise ValueError("ranking_group_snapshots must be UTF-16 sorted on the wire")
        return cls(
            cell_id=value["cell_id"],
            manifest_version=value["manifest_version"],
            methodology_version=value["methodology_version"],
            ranking_group_snapshots=references,
        )


def verify_leaderboard_snapshot_set(payload: Any) -> SnapshotSetDescriptorV1:
    """Bind a leaderboard envelope and its exact group snapshots to its content ID."""

    if not isinstance(payload, dict):
        raise TypeError("leaderboard must be a JSON object")
    required = {
        "cell_id",
        "manifest_version",
        "methodology_version",
        "snapshot_set_id",
        "snapshot_set_descriptor",
        "ranking_groups",
    }
    missing = required - set(payload)
    if missing:
        raise ValueError(f"leaderboard is missing {', '.join(sorted(missing))}")
    descriptor = SnapshotSetDescriptorV1.from_dict(payload["snapshot_set_descriptor"])
    for name in ("cell_id", "manifest_version", "methodology_version"):
        if payload[name] != getattr(descriptor, name):
            raise ValueError(f"leaderboard {name} must match snapshot_set_descriptor")
    groups = payload["ranking_groups"]
    if not isinstance(groups, list) or not groups:
        raise ValueError("leaderboard ranking_groups must be a non-empty array")
    group_snapshots: list[RankingGroupSnapshotRefV1] = []
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("every ranking group must be an object")
        try:
            group_snapshots.append(
                RankingGroupSnapshotRefV1(
                    ranking_group_id=group["ranking_group_id"],
                    evidence_snapshot_id=group["evidence_snapshot_id"],
                )
            )
        except KeyError as error:
            raise ValueError(
                "every ranking group must carry ranking_group_id and evidence_snapshot_id"
            ) from error
    try:
        expected = SnapshotSetDescriptorV1(
            cell_id=descriptor.cell_id,
            manifest_version=descriptor.manifest_version,
            methodology_version=descriptor.methodology_version,
            ranking_group_snapshots=tuple(group_snapshots),
        ).ranking_group_snapshots
    except (TypeError, ValueError) as error:
        raise ValueError("ranking-group snapshot pairs must be one-to-one") from error
    if descriptor.ranking_group_snapshots != expected:
        raise ValueError(
            "snapshot_set_descriptor must contain the exact ranking-group snapshot pairs"
        )
    if payload["snapshot_set_id"] != descriptor.snapshot_set_id:
        raise ValueError("snapshot_set_id must hash the exact snapshot_set_descriptor")
    return descriptor


def verify_leaderboard_semantics(payload: Any) -> SnapshotSetDescriptorV1:
    """Verify keyed uniqueness, ranks, claims, and evidence-gap truth after schema validation."""

    _verify_fields(
        payload,
        {
            "object", "schema_version", "cell_id", "cell_state", "manifest_version",
            "methodology_version", "snapshot_set_id", "snapshot_set_descriptor",
            "generated_at", "ranking_groups",
        },
        label="leaderboard",
    )
    if payload["object"] != "leaderboard" or payload["schema_version"] != "1":
        raise ValueError("leaderboard envelope is invalid")
    if payload["cell_state"] not in _GROUP_STATES:
        raise ValueError("leaderboard cell_state is invalid")
    generated_at = _parse_timestamp(payload["generated_at"], label="generated_at")
    descriptor = verify_leaderboard_snapshot_set(payload)
    group_ids: set[str] = set()
    configuration_ids: set[str] = set()
    for group in payload["ranking_groups"]:
        _verify_fields(
            group,
            {
                "ranking_group_id", "entity_kind", "interaction_policy",
                "configuration_passport_class", "state", "evidence_snapshot_id",
                "eligibility_summary", "entries", "citations", "explorer_views",
            },
            label="ranking group",
        )
        group_id = group.get("ranking_group_id")
        if not isinstance(group_id, str) or not _CELL_ID_RE.fullmatch(group_id):
            raise ValueError("every ranking group must carry ranking_group_id")
        if group_id in group_ids:
            raise ValueError("ranking_group_id values must be unique")
        group_ids.add(group_id)
        entries = group.get("entries")
        if not isinstance(entries, list):
            raise ValueError("ranking group entries must be an array")
        _verify_rankings(entries, configuration_ids=configuration_ids, require_contiguous=True)
        citations = group.get("citations")
        if not isinstance(citations, list):
            raise ValueError("ranking group citations must be an array")
        for citation in citations:
            _verify_citation(citation)
        has_top_set = any(entry["ranking"]["in_top_set"] for entry in entries)
        state = group.get("state")
        identity_triple = (
            group.get("entity_kind"),
            group.get("interaction_policy"),
            group.get("configuration_passport_class"),
        )
        if state not in _GROUP_STATES or identity_triple not in {
            *IDENTITY_TRIPLES,
            ("unresolved", "unresolved", "unresolved-v1"),
        }:
            raise ValueError("ranking group identity or state is invalid")
        evidence_snapshot_id = group.get("evidence_snapshot_id")
        explorer_views = group.get("explorer_views")
        eligibility = group.get("eligibility_summary")
        # Publication visibility (state) is decoupled from claim strength: a read's
        # evidence, exposure, and membership rules key on published_claim, not state.
        # ANY published state may carry EITHER claim.
        published_claim = _read_published_claim(group)
        _verify_claim_top_set(published_claim, has_top_set)
        if published_claim == "top_set" and not str(evidence_snapshot_id).startswith("snapshot_"):
            raise ValueError("top_set groups require snapshot evidence")
        if published_claim == "explorer" and not str(evidence_snapshot_id).startswith("explorer_"):
            raise ValueError("explorer groups require explorer evidence")
        if published_claim == "top_set" and explorer_views:
            raise ValueError("top_set groups cannot expose explorer views")
        if published_claim == "top_set" and entries and not citations:
            raise ValueError("top_set ranking entries require group citations")
        if state == "quarantined" and entries:
            raise ValueError("quarantined groups cannot expose entries")
        if published_claim == "explorer" and entries:
            raise ValueError("explorer groups cannot expose calibrated entries")
        if str(evidence_snapshot_id).startswith("explorer_") and not explorer_views:
            raise ValueError("explorer evidence requires an explorer view")
        if str(evidence_snapshot_id).startswith("snapshot_") and explorer_views:
            raise ValueError("snapshot evidence cannot expose explorer views")
        has_stale_view = _verify_explorer_views(explorer_views, generated_at=generated_at)
        _verify_eligibility(
            eligibility,
            state=group.get("state"),
            entity_kind=group.get("entity_kind"),
            entry_count=len(entries),
            has_top_set=has_top_set,
        )
        if ("evidence_stale" in eligibility["gap_codes"]) != has_stale_view:
            raise ValueError("evidence_stale gap must match explorer view freshness")
    return descriptor


def _verify_explorer_views(value: Any, *, generated_at: datetime) -> bool:
    if not isinstance(value, list):
        raise ValueError("explorer_views must be an array")
    orderings: list[tuple[str, ...]] = []
    any_stale = False
    for view in value:
        _verify_fields(
            view,
            {
                "benchmark_family_id", "feed_id", "metric_direction", "observed_at",
                "expires_at", "agreement", "entries", "citations",
            },
            label="explorer view",
        )
        if not isinstance(view.get("entries"), list):
            raise ValueError("explorer view entries must be an array")
        observed_at = _parse_timestamp(view["observed_at"], label="observed_at")
        expires_at = _parse_timestamp(view["expires_at"], label="expires_at")
        if expires_at <= observed_at:
            raise ValueError("explorer expires_at must be after observed_at")
        family_id = view["benchmark_family_id"]
        if not isinstance(family_id, str) or not _CELL_ID_RE.fullmatch(family_id) or not isinstance(view["feed_id"], str) or not _CELL_ID_RE.fullmatch(view["feed_id"]):
            raise ValueError("explorer view identity is invalid")
        if view["metric_direction"] not in {"higher", "lower"}:
            raise ValueError("explorer metric_direction is invalid")
        citations = view["citations"]
        if not isinstance(citations, list):
            raise ValueError("explorer view citations must be an array")
        for citation in citations:
            _verify_citation(citation)
            if citation["benchmark_family_id"] != family_id:
                raise ValueError("explorer citation must match benchmark_family_id")
        configuration_ids: set[str] = set()
        _verify_rankings(
            view["entries"],
            configuration_ids=configuration_ids,
            require_contiguous=True,
        )
        orderings.append(tuple(entry["evaluated_configuration_id"] for entry in view["entries"]))
        stale = generated_at >= expires_at
        any_stale = any_stale or stale
        for entry in view["entries"]:
            ranking = entry.get("ranking")
            if ranking["in_top_set"]:
                raise ValueError("explorer views cannot claim top-set membership")
            if ranking.get("evidence_family_count") != 1:
                raise ValueError("explorer evidence_family_count must equal 1")
            caveats = ranking.get("caveat_codes")
            if not isinstance(caveats, list) or (("evidence_stale" in caveats) != stale):
                raise ValueError("explorer evidence_stale must match expires_at")
    expected_agreement = (
        "single_source"
        if len(value) == 1
        else "promising_not_proven"
        if orderings and all(ordering == orderings[0] for ordering in orderings[1:])
        else "conflicting"
    )
    if any(view["agreement"] != expected_agreement for view in value):
        raise ValueError("explorer agreement must be derived across views")
    return any_stale


def verify_entity_detail_semantics(payload: Any) -> SnapshotSetDescriptorV1:
    """Verify one detail projection against its snapshot and configuration identity."""

    _verify_fields(
        payload,
        {
            "object", "schema_version", "cell_id", "manifest_version", "methodology_version",
            "snapshot_set_id", "snapshot_set_descriptor", "ranking_group_id", "state",
            "evidence_snapshot_id", "explorer_view", "eligibility_summary", "generated_at", "entity",
        },
        label="entity detail",
    )
    if payload["object"] != "entity_detail" or payload["schema_version"] != "1":
        raise ValueError("entity detail envelope is invalid")
    _parse_timestamp(payload["generated_at"], label="generated_at")
    descriptor = _verify_snapshot_reference(payload)
    projection = payload.get("entity")
    _verify_fields(
        projection,
        {"evaluated_configuration", "ranking", "citations"},
        label="entity projection",
    )
    configuration = EvaluatedConfigurationV1.from_dict(projection.get("evaluated_configuration"))
    ranking = projection.get("ranking")
    _verify_ranking(ranking)
    _verify_selected_explorer_view(payload, projection["citations"])
    _verify_claim_top_set(_read_published_claim(payload), ranking["in_top_set"])
    _verify_eligibility_summary_state(payload.get("eligibility_summary"), payload.get("state"))
    if configuration.evaluated_configuration_id != projection["evaluated_configuration"]["evaluated_configuration_id"]:
        raise ValueError("entity detail evaluated_configuration_id is invalid")
    return descriptor


def verify_compare_result_semantics(payload: Any) -> SnapshotSetDescriptorV1:
    """Verify compare-key uniqueness and snapshot/claim consistency after schema validation."""

    _verify_fields(
        payload,
        {
            "object", "schema_version", "cell_id", "manifest_version", "methodology_version",
            "snapshot_set_id", "snapshot_set_descriptor", "ranking_group_id", "entity_kind",
            "interaction_policy", "configuration_passport_class", "state", "evidence_snapshot_id",
            "explorer_view", "eligibility_summary", "generated_at", "entities",
        },
        label="compare result",
    )
    if payload["object"] != "compare_result" or payload["schema_version"] != "1":
        raise ValueError("compare result envelope is invalid")
    _parse_timestamp(payload["generated_at"], label="generated_at")
    descriptor = _verify_snapshot_reference(payload)
    identity_triple = (
        payload.get("entity_kind"),
        payload.get("interaction_policy"),
        payload.get("configuration_passport_class"),
    )
    if identity_triple not in IDENTITY_TRIPLES:
        raise ValueError("compare ranking-group identity is invalid")
    entities = payload.get("entities")
    if not isinstance(entities, list) or not 2 <= len(entities) <= 4:
        raise ValueError("compare entities must contain two to four rows")
    configuration_ids: set[str] = set()
    ranks: set[int] = set()
    for entity in entities:
        _verify_fields(
            entity,
            {"evaluated_configuration_id", "ranking", "citations"},
            label="compared entity",
        )
        configuration_id = entity.get("evaluated_configuration_id")
        if not isinstance(configuration_id, str) or not _CONFIGURATION_ID_RE.fullmatch(configuration_id):
            raise ValueError("compare evaluated_configuration_id has an invalid format")
        if configuration_id in configuration_ids:
            raise ValueError("compare evaluated_configuration_id values must be unique")
        configuration_ids.add(configuration_id)
        ranking = entity.get("ranking")
        _verify_ranking(ranking)
        rank = ranking["rank"]
        if rank in ranks:
            raise ValueError("compare ranks must be unique")
        ranks.add(rank)
        _verify_claim_top_set(_read_published_claim(payload), ranking["in_top_set"])
        _verify_selected_explorer_view(payload, entity["citations"])
    _verify_eligibility_summary_state(payload.get("eligibility_summary"), payload.get("state"))
    return descriptor


def _verify_snapshot_reference(payload: Any) -> SnapshotSetDescriptorV1:
    if not isinstance(payload, dict):
        raise TypeError("public read document must be a JSON object")
    descriptor = SnapshotSetDescriptorV1.from_dict(payload.get("snapshot_set_descriptor"))
    for name in ("cell_id", "manifest_version", "methodology_version"):
        if payload.get(name) != getattr(descriptor, name):
            raise ValueError(f"{name} must match snapshot_set_descriptor")
    if payload.get("snapshot_set_id") != descriptor.snapshot_set_id:
        raise ValueError("snapshot_set_id must hash snapshot_set_descriptor")
    reference = RankingGroupSnapshotRefV1(
        ranking_group_id=payload.get("ranking_group_id"),
        evidence_snapshot_id=payload.get("evidence_snapshot_id"),
    )
    if reference not in descriptor.ranking_group_snapshots:
        raise ValueError(
            "ranking-group snapshot pair must belong to snapshot_set_descriptor"
        )
    state = payload.get("state")
    if state not in {"active", "preview", "shadow"}:
        raise ValueError("public read state is invalid")
    # Evidence prefix is bound to the claim (top_set⇒snapshot_, explorer⇒explorer_),
    # not to the publication state; any published state may carry either claim.
    published_claim = _read_published_claim(payload)
    if published_claim == "top_set" and not reference.evidence_snapshot_id.startswith("snapshot_"):
        raise ValueError("top_set reads require snapshot evidence")
    if published_claim == "explorer" and not reference.evidence_snapshot_id.startswith("explorer_"):
        raise ValueError("explorer reads require explorer evidence")
    return descriptor


def _verify_selected_explorer_view(payload: dict[str, Any], citations: Any) -> None:
    selector = payload["explorer_view"]
    if _read_published_claim(payload) == "top_set":
        if selector is not None:
            raise ValueError("top_set reads cannot select an explorer view")
    else:
        _verify_fields(
            selector,
            {"benchmark_family_id", "feed_id"},
            label="explorer_view",
        )
        if not _CELL_ID_RE.fullmatch(selector["benchmark_family_id"]) or not _CELL_ID_RE.fullmatch(selector["feed_id"]):
            raise ValueError("explorer_view identity is invalid")
    if not isinstance(citations, list) or not citations:
        raise ValueError("citations must be a non-empty array")
    for citation in citations:
        _verify_citation(citation)
        if selector is not None and citation["benchmark_family_id"] != selector["benchmark_family_id"]:
            raise ValueError("citations must match selected explorer benchmark_family_id")


def _verify_rankings(
    entries: list[Any],
    *,
    configuration_ids: set[str],
    require_contiguous: bool,
) -> None:
    ranks: list[int] = []
    for entry in entries:
        _verify_fields(entry, {"evaluated_configuration_id", "ranking"}, label="leaderboard entry")
        configuration_id = entry.get("evaluated_configuration_id")
        if (
            not isinstance(configuration_id, str)
            or not _CONFIGURATION_ID_RE.fullmatch(configuration_id)
            or configuration_id in configuration_ids
        ):
            raise ValueError("evaluated_configuration_id values must be unique")
        configuration_ids.add(configuration_id)
        ranking = entry.get("ranking")
        _verify_ranking(ranking)
        ranks.append(ranking["rank"])
    if require_contiguous and ranks != list(range(1, len(entries) + 1)):
        raise ValueError("leaderboard ranks must be contiguous from 1 in array order")


def _verify_ranking(ranking: Any) -> None:
    _verify_fields(
        ranking,
        {
            "rank", "display_name", "capability_score", "uncertainty", "in_top_set",
            "evidence_family_count", "caveat_codes",
        },
        label="entity ranking",
    )
    rank = ranking.get("rank")
    if not isinstance(rank, int) or isinstance(rank, bool) or not 1 <= rank <= MAX_SAFE_INTEGER:
        raise ValueError("entity ranking rank must be a positive safe integer")
    if not isinstance(ranking.get("display_name"), str) or not ranking["display_name"]:
        raise ValueError("entity ranking display_name must be non-empty")
    score = ranking.get("capability_score")
    if not isinstance(score, (int, float, Decimal)) or isinstance(score, bool) or not Decimal(str(score)).is_finite() or not Decimal(0) <= Decimal(str(score)) <= Decimal(1):
        raise ValueError("entity ranking capability_score must be within [0,1]")
    if not isinstance(ranking.get("in_top_set"), bool):
        raise ValueError("entity ranking in_top_set must be a boolean")
    family_count = ranking.get("evidence_family_count")
    if not isinstance(family_count, int) or isinstance(family_count, bool) or not 1 <= family_count <= MAX_SAFE_INTEGER:
        raise ValueError("entity ranking evidence_family_count must be a positive safe integer")
    caveats = ranking.get("caveat_codes")
    if not isinstance(caveats, list) or len(set(caveats)) != len(caveats) or any(not isinstance(item, str) or _CAVEAT_RE.fullmatch(item) is None for item in caveats):
        raise ValueError("entity ranking caveat_codes must be unique canonical strings")
    uncertainty = ranking.get("uncertainty")
    if not isinstance(uncertainty, dict):
        raise ValueError("ranking uncertainty must be an object")
    if uncertainty.get("kind") == "unknown":
        if set(uncertainty) != {"kind"}:
            raise ValueError("unknown uncertainty fields are invalid")
    elif uncertainty.get("kind") == "interval":
        if set(uncertainty) != {"kind", "level", "lower", "upper"}:
            raise ValueError("interval uncertainty fields are invalid")
        try:
            level = Decimal(str(uncertainty["level"]))
            lower = Decimal(str(uncertainty["lower"]))
            upper = Decimal(str(uncertainty["upper"]))
        except (InvalidOperation, KeyError, TypeError) as error:
            raise ValueError("ranking interval must contain numeric lower and upper values") from error
        if lower > upper:
            raise ValueError("ranking interval lower must be <= upper")
        if not level.is_finite() or not lower.is_finite() or not upper.is_finite() or not Decimal(0) < level <= Decimal(1) or not Decimal(0) <= lower <= upper <= Decimal(1):
            raise ValueError("ranking interval must be a valid unit interval")
    else:
        raise ValueError("ranking uncertainty kind is invalid")


def _verify_eligibility(
    value: Any,
    *,
    state: Any,
    entity_kind: Any,
    entry_count: int,
    has_top_set: bool,
) -> None:
    _verify_eligibility_summary_state(value, state)
    if not isinstance(value, dict):
        raise ValueError("eligibility_summary must be an object")
    if value.get("rank_eligible_configuration_count") != entry_count:
        raise ValueError("rank_eligible_configuration_count must equal leaderboard entry count")
    gaps = set(value.get("gap_codes", ()))
    if entity_kind == "unresolved":
        if entry_count or "unresolved_identity" not in gaps:
            raise ValueError("unresolved groups must be empty and disclose unresolved_identity")
    if value.get("published_claim") == "top_set" and not has_top_set:
        raise ValueError("top_set ranking groups must publish at least one top-set member")


def _verify_eligibility_summary_state(value: Any, state: Any) -> None:
    _verify_fields(
        value,
        {
            "published_claim", "rank_eligible_configuration_count",
            "current_independent_family_count", "required_independent_family_count",
            "current_overlap_count", "required_overlap_count", "calibration_status",
            "gap_codes",
        },
        label="eligibility_summary",
    )
    gaps = value.get("gap_codes")
    if not isinstance(gaps, list) or len(set(gaps)) != len(gaps) or any(item not in _GAP_CODES for item in gaps):
        raise ValueError("eligibility gap_codes must be a unique array")
    if value.get("published_claim") not in {"explorer", "top_set"} or value.get("calibration_status") not in {"unvalidated", "validated"}:
        raise ValueError("eligibility enum value is invalid")
    # Claim strength, not publication state, drives the calibration/gap gate.
    if value.get("published_claim") == "top_set":
        if value.get("calibration_status") != "validated" or gaps:
            raise ValueError("top_set reads require validated calibration with no gaps")
    else:
        if not gaps:
            raise ValueError("explorer reads require explicit gaps")
    _verify_eligibility_count_gaps(value, gaps)
    if state == "quarantined" and "quarantined" not in gaps:
        raise ValueError("quarantined reads must disclose the quarantined gap")


def _read_published_claim(payload: Any) -> Any:
    eligibility = payload.get("eligibility_summary") if isinstance(payload, dict) else None
    return eligibility.get("published_claim") if isinstance(eligibility, dict) else None


def _verify_claim_top_set(published_claim: Any, in_top_set: bool) -> None:
    if published_claim == "explorer" and in_top_set:
        raise ValueError("explorer reads cannot claim top-set membership")


def _verify_count_gap(
    value: dict[str, Any],
    *,
    current: str,
    required: str,
    code: str,
    gaps: set[str],
) -> None:
    current_value = value.get(current)
    required_value = value.get(required)
    if not isinstance(current_value, int) or isinstance(current_value, bool) or not isinstance(required_value, int) or isinstance(required_value, bool) or not 0 <= current_value <= MAX_SAFE_INTEGER or not 1 <= required_value <= MAX_SAFE_INTEGER:
        raise ValueError("eligibility counts must be safe and nonnegative/positive")
    if (current_value < required_value) != (code in gaps):
        raise ValueError(f"{code} gap must match eligibility counts")


def _verify_eligibility_count_gaps(value: dict[str, Any], gaps: set[str]) -> None:
    _verify_count_gap(
        value,
        current="current_independent_family_count",
        required="required_independent_family_count",
        code="insufficient_independent_families",
        gaps=gaps,
    )
    _verify_count_gap(
        value,
        current="current_overlap_count",
        required="required_overlap_count",
        code="insufficient_configuration_overlap",
        gaps=gaps,
    )
    rank_eligible_count = value.get("rank_eligible_configuration_count")
    if not isinstance(rank_eligible_count, int) or isinstance(rank_eligible_count, bool) or not 0 <= rank_eligible_count <= MAX_SAFE_INTEGER:
        raise ValueError("rank_eligible_configuration_count must be a safe nonnegative integer")
    if (rank_eligible_count == 0) != ("no_rank_eligible_configurations" in gaps):
        raise ValueError("no_rank_eligible_configurations gap must match eligibility count")
    if (value.get("calibration_status") == "unvalidated") != ("calibration_unvalidated" in gaps):
        raise ValueError("calibration_unvalidated gap must match calibration_status")


def _verify_fields(value: Any, expected: set[str], *, label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} fields are invalid")


def _parse_timestamp(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP_RE.fullmatch(value):
        raise ValueError(f"{label} is invalid")
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ValueError(f"{label} is invalid") from error


def _verify_citation(value: Any) -> None:
    _verify_fields(
        value,
        {"source_artifact_id", "benchmark_family_id", "title", "url"},
        label="citation",
    )
    if not isinstance(value["source_artifact_id"], str) or not _ARTIFACT_ID_RE.fullmatch(value["source_artifact_id"]):
        raise ValueError("citation source_artifact_id is invalid")
    if not isinstance(value["benchmark_family_id"], str) or not _CELL_ID_RE.fullmatch(value["benchmark_family_id"]):
        raise ValueError("citation benchmark_family_id is invalid")
    if not isinstance(value["title"], str) or not value["title"]:
        raise ValueError("citation title must be non-empty")
    if not isinstance(value["url"], str) or re.fullmatch(r"https://\S+", value["url"]) is None:
        raise ValueError("citation URL must use HTTPS")
