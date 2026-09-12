import sys
import unittest
from copy import deepcopy
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parents[1] / "packages" / "core" / "src"
sys.path.insert(0, str(CORE_SRC))

from evalrank_core.canonical_json import sha256_hex  # noqa: E402
from evalrank_core.read_contracts import (  # noqa: E402
    RankingGroupSnapshotRefV1,
    SnapshotSetDescriptorV1,
    verify_benchmark_health_semantics,
    verify_compare_result_semantics,
    verify_entity_detail_semantics,
    verify_leaderboard_semantics,
    verify_leaderboard_snapshot_set,
)


class BenchmarkHealthSemanticTests(unittest.TestCase):
    def test_health_status_and_nested_counts_are_derived_truthfully(self):
        payload = _benchmark_health()

        self.assertIs(payload, verify_benchmark_health_semantics(payload))

        wrong_status = deepcopy(payload)
        wrong_status["cells"][0]["status"] = "active"
        with self.assertRaisesRegex(ValueError, "status"):
            verify_benchmark_health_semantics(wrong_status)

        impossible_counts = deepcopy(payload)
        impossible_counts["cells"][0]["admitted_feed_count"] = 3
        with self.assertRaisesRegex(ValueError, "nested"):
            verify_benchmark_health_semantics(impossible_counts)

    def test_health_rejects_duplicate_cells_unknown_fields_and_unsafe_counts(self):
        duplicate = _benchmark_health()
        duplicate["cells"].append(deepcopy(duplicate["cells"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            verify_benchmark_health_semantics(duplicate)

        unknown = _benchmark_health()
        unknown["cells"][0]["detail"] = "not public"
        with self.assertRaisesRegex(ValueError, "fields"):
            verify_benchmark_health_semantics(unknown)

        unsafe = _benchmark_health()
        unsafe["cells"][0]["candidate_feed_count"] = 2**53
        with self.assertRaisesRegex(ValueError, "safe"):
            verify_benchmark_health_semantics(unsafe)

        invalid_timestamp = _benchmark_health()
        invalid_timestamp["generated_at"] = "2026-02-30T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "generated_at"):
            verify_benchmark_health_semantics(invalid_timestamp)


def _benchmark_health() -> dict:
    return {
        "object": "benchmark_health",
        "schema_version": "1",
        "manifest_version": "2026-07-09.3",
        "generated_at": "2026-07-10T00:00:00Z",
        "cells": [
            {
                "cell_id": "code-generation",
                "status": "preview",
                "ranking_group_count": 2,
                "published_ranking_group_count": 0,
                "benchmark_family_count": 3,
                "candidate_feed_count": 4,
                "implemented_feed_count": 2,
                "admitted_feed_count": 0,
                "rank_eligible_feed_count": 0,
            }
        ],
    }


class SnapshotSetDescriptorTests(unittest.TestCase):
    def test_snapshot_set_id_hashes_one_float_free_sorted_descriptor(self):
        first = SnapshotSetDescriptorV1(
            cell_id="code-generation",
            manifest_version="2026-07-09.2",
            methodology_version="2026-07-09.2.public-decision-v1",
            ranking_group_snapshots=(
                RankingGroupSnapshotRefV1(
                    ranking_group_id="rg-b",
                    evidence_snapshot_id=f"snapshot_{'b' * 64}",
                ),
                RankingGroupSnapshotRefV1(
                    ranking_group_id="rg-a",
                    evidence_snapshot_id=f"explorer_{'a' * 64}",
                ),
            ),
        )
        reordered = SnapshotSetDescriptorV1(
            cell_id=first.cell_id,
            manifest_version=first.manifest_version,
            methodology_version=first.methodology_version,
            ranking_group_snapshots=tuple(reversed(first.ranking_group_snapshots)),
        )

        self.assertEqual(first.to_dict(), reordered.to_dict())
        self.assertEqual(
            f"snapshot_set_{sha256_hex(first.to_dict())}",
            first.snapshot_set_id,
        )
        self.assertEqual(
            "snapshot_set_e9f71f01453b8bc1b61e2e895122a9ee9441fc4f40e8b6fb016870338fed151d",
            first.snapshot_set_id,
        )
        self.assertEqual(first.snapshot_set_id, reordered.snapshot_set_id)

    def test_wire_descriptor_must_be_closed_and_already_sorted(self):
        descriptor = SnapshotSetDescriptorV1(
            cell_id="code-generation",
            manifest_version="2026-07-09.2",
            methodology_version="2026-07-09.2.truth-kernel-v1",
            ranking_group_snapshots=(
                RankingGroupSnapshotRefV1(
                    ranking_group_id="rg-a",
                    evidence_snapshot_id=f"explorer_{'a' * 64}",
                ),
                RankingGroupSnapshotRefV1(
                    ranking_group_id="rg-b",
                    evidence_snapshot_id=f"snapshot_{'b' * 64}",
                ),
            ),
        )
        self.assertEqual(descriptor, SnapshotSetDescriptorV1.from_dict(descriptor.to_dict()))

        unsorted = descriptor.to_dict()
        unsorted["ranking_group_snapshots"].reverse()
        with self.assertRaisesRegex(ValueError, "sorted"):
            SnapshotSetDescriptorV1.from_dict(unsorted)

        open_pair = descriptor.to_dict()
        open_pair["ranking_group_snapshots"][0]["generated_at"] = "2026-07-09T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "unknown"):
            SnapshotSetDescriptorV1.from_dict(open_pair)

        unknown = {**descriptor.to_dict(), "generated_at": "2026-07-09T00:00:00Z"}
        with self.assertRaisesRegex(ValueError, "unknown"):
            SnapshotSetDescriptorV1.from_dict(unknown)

        invalid_cell = {**descriptor.to_dict(), "cell_id": "Not a slug"}
        with self.assertRaisesRegex(ValueError, "canonical manifest slug"):
            SnapshotSetDescriptorV1.from_dict(invalid_cell)

        legacy_pair = descriptor.to_dict()
        pair = legacy_pair["ranking_group_snapshots"][0]
        pair["publication_snapshot_id"] = pair.pop("evidence_snapshot_id")
        with self.assertRaisesRegex(ValueError, "fields are invalid"):
            SnapshotSetDescriptorV1.from_dict(legacy_pair)

    def test_leaderboard_verifier_binds_envelope_and_exact_group_snapshots(self):
        descriptor = SnapshotSetDescriptorV1(
            cell_id="code-generation",
            manifest_version="2026-07-09.2",
            methodology_version="2026-07-09.2.truth-kernel-v1",
            ranking_group_snapshots=(
                RankingGroupSnapshotRefV1(
                    ranking_group_id="rg-a",
                    evidence_snapshot_id=f"explorer_{'a' * 64}",
                ),
                RankingGroupSnapshotRefV1(
                    ranking_group_id="rg-b",
                    evidence_snapshot_id=f"snapshot_{'b' * 64}",
                ),
            ),
        )
        leaderboard = {
            **{
                key: value
                for key, value in descriptor.to_dict().items()
                if key not in {"object", "schema_version", "ranking_group_snapshots"}
            },
            "snapshot_set_id": descriptor.snapshot_set_id,
            "snapshot_set_descriptor": descriptor.to_dict(),
            "ranking_groups": [
                snapshot.to_dict() for snapshot in descriptor.ranking_group_snapshots
            ],
        }

        self.assertEqual(descriptor, verify_leaderboard_snapshot_set(leaderboard))
        for field, value in (
            ("cell_id", "other-cell"),
            ("snapshot_set_id", f"snapshot_set_{'c' * 64}"),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    verify_leaderboard_snapshot_set({**leaderboard, field: value})

        wrong_groups = {
            **leaderboard,
            "ranking_groups": [
                {
                    "ranking_group_id": "rg-a",
                    "evidence_snapshot_id": f"explorer_{'c' * 64}",
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "exact ranking-group snapshot pairs"):
            verify_leaderboard_snapshot_set(wrong_groups)

        swapped_ownership = deepcopy(leaderboard)
        swapped_ownership["ranking_groups"][0]["evidence_snapshot_id"] = f"snapshot_{'b' * 64}"
        swapped_ownership["ranking_groups"][1]["evidence_snapshot_id"] = f"explorer_{'a' * 64}"
        with self.assertRaisesRegex(ValueError, "exact ranking-group snapshot pairs"):
            verify_leaderboard_snapshot_set(swapped_ownership)

    def test_leaderboard_semantics_reject_keyed_duplicates_bad_intervals_and_false_gaps(self):
        leaderboard = _active_leaderboard()
        verify_leaderboard_semantics(leaderboard)

        duplicate = deepcopy(leaderboard)
        second = deepcopy(duplicate["ranking_groups"][0]["entries"][0])
        second["ranking"]["rank"] = 2
        second["ranking"]["display_name"] = "Same configuration, different row"
        duplicate["ranking_groups"][0]["entries"].append(second)
        duplicate["ranking_groups"][0]["eligibility_summary"]["rank_eligible_configuration_count"] = 2
        with self.assertRaisesRegex(ValueError, "evaluated_configuration_id values must be unique"):
            verify_leaderboard_semantics(duplicate)

        bad_interval = deepcopy(leaderboard)
        bad_interval["ranking_groups"][0]["entries"][0]["ranking"]["uncertainty"] = {
            "kind": "interval",
            "level": 0.95,
            "lower": 0.9,
            "upper": 0.8,
        }
        with self.assertRaisesRegex(ValueError, "lower must be <= upper"):
            verify_leaderboard_semantics(bad_interval)

        false_gap = _explorer_leaderboard()
        false_gap["ranking_groups"][0]["eligibility_summary"]["gap_codes"].remove(
            "insufficient_independent_families"
        )
        with self.assertRaisesRegex(ValueError, "insufficient_independent_families"):
            verify_leaderboard_semantics(false_gap)

        top_set_explorer = deepcopy(leaderboard)
        top_set_explorer["ranking_groups"][0]["explorer_views"] = [{"entries": []}]
        with self.assertRaisesRegex(ValueError, "top_set groups cannot expose explorer views"):
            verify_leaderboard_semantics(top_set_explorer)

        top_set_explorer_identity = _with_evidence_snapshot_id(
            leaderboard, f"explorer_{'e' * 64}"
        )
        with self.assertRaisesRegex(ValueError, "top_set groups require snapshot evidence"):
            verify_leaderboard_semantics(top_set_explorer_identity)

        preview_calibrated = deepcopy(leaderboard)
        preview_group = preview_calibrated["ranking_groups"][0]
        preview_group["state"] = "preview"
        preview_group["entries"][0]["ranking"]["in_top_set"] = False
        preview_group["eligibility_summary"] = {
            **preview_group["eligibility_summary"],
            "published_claim": "explorer",
            "calibration_status": "unvalidated",
            "gap_codes": ["calibration_unvalidated"],
        }
        with self.assertRaisesRegex(ValueError, "explorer groups"):
            verify_leaderboard_semantics(preview_calibrated)

        # A top_set claim (snapshot evidence) may never expose explorer views, in ANY
        # published state — the rule keys on the claim, not the state.
        for state in ("active", "preview", "shadow"):
            top_set_with_view = deepcopy(leaderboard)
            top_set_with_view["ranking_groups"][0]["state"] = state
            top_set_with_view["ranking_groups"][0]["explorer_views"] = [{"entries": []}]
            with self.subTest(state=state):
                with self.assertRaisesRegex(
                    ValueError, "top_set groups cannot expose explorer views"
                ):
                    verify_leaderboard_semantics(top_set_with_view)

        # An explorer claim validates in ANY published state, but its evidence must be
        # explorer_-prefixed; a snapshot_ evidence id under an explorer claim is a
        # claim/evidence inconsistency.
        for state in ("active", "preview", "shadow"):
            explorer_group = _explorer_leaderboard()
            explorer_group["ranking_groups"][0]["state"] = state
            with self.subTest(state=state):
                verify_leaderboard_semantics(explorer_group)

            snapshot_evidence = _with_evidence_snapshot_id(
                explorer_group, f"snapshot_{'a' * 64}"
            )
            with self.subTest(state=state, mutation="snapshot-evidence"):
                with self.assertRaisesRegex(
                    ValueError, "explorer groups require explorer evidence"
                ):
                    verify_leaderboard_semantics(snapshot_evidence)

        explorer_without_view = _explorer_leaderboard()
        explorer_without_view["ranking_groups"][0]["explorer_views"] = []
        with self.assertRaisesRegex(ValueError, "explorer evidence requires an explorer view"):
            verify_leaderboard_semantics(explorer_without_view)

        # An explorer claim cannot carry a calibrated top-set member.
        explorer_claims_top_set = _explorer_leaderboard()
        claim_group = explorer_claims_top_set["ranking_groups"][0]
        top_set_entry = deepcopy(claim_group["explorer_views"][0]["entries"][0])
        top_set_entry["ranking"]["in_top_set"] = True
        claim_group["entries"] = [top_set_entry]
        with self.assertRaisesRegex(
            ValueError, "explorer reads cannot claim top-set membership"
        ):
            verify_leaderboard_semantics(explorer_claims_top_set)

        explorer_top_set = _explorer_leaderboard()
        explorer_top_set["ranking_groups"][0]["explorer_views"][0]["entries"][0][
            "ranking"
        ]["in_top_set"] = True
        with self.assertRaisesRegex(ValueError, "explorer views cannot claim top-set"):
            verify_leaderboard_semantics(explorer_top_set)

        # v2 acceptance: an ACTIVE read carrying an explorer claim (explorer evidence,
        # disclosed gaps, no in_top_set) is decoupled from state and MUST be accepted.
        active_explorer = _explorer_leaderboard()
        active_explorer["cell_state"] = "active"
        active_explorer["ranking_groups"][0]["state"] = "active"
        verify_leaderboard_semantics(active_explorer)

        # v2 rejection: a top_set claim must carry validated calibration and no gaps,
        # regardless of state.
        top_set_with_gaps = deepcopy(leaderboard)
        top_set_gap_eligibility = top_set_with_gaps["ranking_groups"][0]["eligibility_summary"]
        top_set_gap_eligibility["calibration_status"] = "unvalidated"
        top_set_gap_eligibility["gap_codes"] = ["calibration_unvalidated"]
        with self.assertRaisesRegex(
            ValueError, "top_set reads require validated calibration with no gaps"
        ):
            verify_leaderboard_semantics(top_set_with_gaps)

    def test_explorer_views_are_independently_ranked_family_bound_and_freshness_truthful(self):
        leaderboard = _explorer_leaderboard()
        verify_leaderboard_semantics(leaderboard)

        mutations = (
            ("duplicate configuration", lambda view: view["entries"].append(deepcopy(view["entries"][0])), "unique"),
            ("gapped rank", lambda view: view["entries"][1]["ranking"].__setitem__("rank", 3), "contiguous"),
            ("wrong family citation", lambda view: view["citations"][0].__setitem__("benchmark_family_id", "other-family"), "citation"),
            ("wrong family count", lambda view: view["entries"][0]["ranking"].__setitem__("evidence_family_count", 2), "evidence_family_count"),
            ("wrong agreement", lambda view: view.__setitem__("agreement", "promising_not_proven"), "agreement"),
            ("expired but fresh", lambda view: view["entries"][0]["ranking"].__setitem__("caveat_codes", []), "evidence_stale"),
            ("invalid expiry order", lambda view: view.__setitem__("expires_at", "2026-07-08T00:00:00Z"), "expires_at"),
        )
        for label, mutate, message in mutations:
            with self.subTest(label=label):
                invalid = deepcopy(leaderboard)
                mutate(invalid["ranking_groups"][0]["explorer_views"][0])
                with self.assertRaisesRegex(ValueError, message):
                    verify_leaderboard_semantics(invalid)

    def test_runtime_read_verifiers_enforce_closed_shape_and_state_prefix(self):
        leaderboard = _active_leaderboard()
        group = leaderboard["ranking_groups"][0]
        for state, snapshot_id in (("active", f"explorer_{'e' * 64}"),):
            invalid = _with_evidence_snapshot_id(leaderboard, snapshot_id)
            invalid["ranking_groups"][0]["state"] = state
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "evidence"):
                    verify_leaderboard_semantics(invalid)

        # An explorer claim carries explorer_ evidence and a disclosing view even when
        # it publishes no calibrated entry (a low-evidence holding cell).
        explorer_holding = _with_evidence_snapshot_id(leaderboard, f"explorer_{'e' * 64}")
        group = explorer_holding["ranking_groups"][0]
        group["state"] = "preview"
        group["entries"] = []
        group["citations"] = []
        group["explorer_views"] = [
            {
                "benchmark_family_id": "family-a",
                "feed_id": "family-a-feed",
                "metric_direction": "higher",
                "observed_at": "2026-07-10T00:00:00Z",
                "expires_at": "2026-07-17T00:00:00Z",
                "agreement": "single_source",
                "entries": [],
                "citations": [],
            }
        ]
        group["eligibility_summary"] = {
            "published_claim": "explorer",
            "rank_eligible_configuration_count": 0,
            "current_independent_family_count": 0,
            "required_independent_family_count": 3,
            "current_overlap_count": 0,
            "required_overlap_count": 2,
            "calibration_status": "unvalidated",
            "gap_codes": ["calibration_unvalidated", "insufficient_configuration_overlap", "insufficient_independent_families", "no_rank_eligible_configurations"],
        }
        verify_leaderboard_semantics(explorer_holding)

        missing = deepcopy(leaderboard)
        del missing["generated_at"]
        with self.assertRaisesRegex(ValueError, "fields"):
            verify_leaderboard_semantics(missing)
        extra = deepcopy(leaderboard)
        extra["private"] = True
        with self.assertRaisesRegex(ValueError, "fields"):
            verify_leaderboard_semantics(extra)

    def test_runtime_read_verifier_rejects_invalid_closed_wire_values(self):
        mutations = (
            ("citation id", lambda doc: doc["ranking_groups"][0]["citations"][0].__setitem__("source_artifact_id", "artifact_bad")),
            ("citation title", lambda doc: doc["ranking_groups"][0]["citations"][0].__setitem__("title", "")),
            ("citation url", lambda doc: doc["ranking_groups"][0]["citations"][0].__setitem__("url", "http://example.com")),
            ("score", lambda doc: doc["ranking_groups"][0]["entries"][0]["ranking"].__setitem__("capability_score", 2)),
            ("family count", lambda doc: doc["ranking_groups"][0]["entries"][0]["ranking"].__setitem__("evidence_family_count", 0)),
            ("uncertainty extra", lambda doc: doc["ranking_groups"][0]["entries"][0]["ranking"]["uncertainty"].__setitem__("private", True)),
            ("uncertainty level", lambda doc: doc["ranking_groups"][0]["entries"][0]["ranking"]["uncertainty"].__setitem__("level", 0)),
            ("caveat", lambda doc: doc["ranking_groups"][0]["entries"][0]["ranking"].__setitem__("caveat_codes", ["Not Canonical"])),
            ("eligibility extra", lambda doc: doc["ranking_groups"][0]["eligibility_summary"].__setitem__("private", True)),
            ("eligibility count", lambda doc: doc["ranking_groups"][0]["eligibility_summary"].__setitem__("required_overlap_count", 0)),
            ("eligibility enum", lambda doc: doc["ranking_groups"][0]["eligibility_summary"].__setitem__("calibration_status", "unknown")),
            ("group slug", lambda doc: doc["ranking_groups"][0].__setitem__("ranking_group_id", "Not Canonical")),
            ("timestamp", lambda doc: doc.__setitem__("generated_at", "2026-02-30T00:00:00Z")),
            ("entry extra", lambda doc: doc["ranking_groups"][0]["entries"][0].__setitem__("private", True)),
            ("mixed identity", lambda doc: doc["ranking_groups"][0].__setitem__("interaction_policy", "agentic")),
            ("citationless active", lambda doc: doc["ranking_groups"][0].__setitem__("citations", [])),
            ("invalid cell state", lambda doc: doc.__setitem__("cell_state", "invalid")),
            ("quarantined entries", lambda doc: (doc["ranking_groups"][0].__setitem__("state", "quarantined"), doc["ranking_groups"][0]["entries"][0]["ranking"].__setitem__("in_top_set", False))),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                invalid = _active_leaderboard()
                mutate(invalid)
                with self.assertRaises((TypeError, ValueError)):
                    verify_leaderboard_semantics(invalid)

    def test_group_stale_gap_is_exactly_derived_from_view_expiry(self):
        stale_without_gap = _explorer_leaderboard()
        stale_without_gap["ranking_groups"][0]["eligibility_summary"]["gap_codes"].remove("evidence_stale")
        with self.assertRaisesRegex(ValueError, "evidence_stale gap"):
            verify_leaderboard_semantics(stale_without_gap)

        fresh_with_gap = _explorer_leaderboard()
        fresh_with_gap["generated_at"] = "2026-07-09T06:00:00Z"
        for entry in fresh_with_gap["ranking_groups"][0]["explorer_views"][0]["entries"]:
            entry["ranking"]["caveat_codes"] = []
        with self.assertRaisesRegex(ValueError, "evidence_stale gap"):
            verify_leaderboard_semantics(fresh_with_gap)

    def test_compare_semantics_reject_same_configuration_with_different_rows(self):
        leaderboard = _active_leaderboard()
        group = leaderboard["ranking_groups"][0]
        first = deepcopy(group["entries"][0])
        second = deepcopy(first)
        second["evaluated_configuration_id"] = f"config_{'d' * 64}"
        second["ranking"]["rank"] = 2
        compare = {
            "object": "compare_result",
            "schema_version": "1",
            "cell_id": leaderboard["cell_id"],
            "manifest_version": leaderboard["manifest_version"],
            "methodology_version": leaderboard["methodology_version"],
            "snapshot_set_id": leaderboard["snapshot_set_id"],
            "snapshot_set_descriptor": leaderboard["snapshot_set_descriptor"],
            "ranking_group_id": group["ranking_group_id"],
            "entity_kind": group["entity_kind"],
            "interaction_policy": group["interaction_policy"],
            "configuration_passport_class": group["configuration_passport_class"],
            "evidence_snapshot_id": group["evidence_snapshot_id"],
            "explorer_view": None,
            "state": "active",
            "eligibility_summary": group["eligibility_summary"],
            "generated_at": leaderboard["generated_at"],
            "entities": [
                {**first, "citations": deepcopy(group["citations"])},
                {**second, "citations": deepcopy(group["citations"])},
            ],
        }
        verify_compare_result_semantics(compare)

        mixed_identity = deepcopy(compare)
        mixed_identity["interaction_policy"] = "agentic"
        with self.assertRaisesRegex(ValueError, "ranking-group identity"):
            verify_compare_result_semantics(mixed_identity)

        duplicate = deepcopy(compare)
        duplicate["entities"][1]["evaluated_configuration_id"] = duplicate["entities"][0]["evaluated_configuration_id"]
        with self.assertRaisesRegex(ValueError, "evaluated_configuration_id values must be unique"):
            verify_compare_result_semantics(duplicate)

        one = deepcopy(compare)
        one["entities"] = one["entities"][:1]
        with self.assertRaisesRegex(ValueError, "two to four"):
            verify_compare_result_semantics(one)

        five = deepcopy(compare)
        for rank, character in enumerate(("e", "f", "b"), start=3):
            added = deepcopy(five["entities"][0])
            added["evaluated_configuration_id"] = f"config_{character * 64}"
            added["ranking"]["rank"] = rank
            five["entities"].append(added)
        with self.assertRaisesRegex(ValueError, "two to four"):
            verify_compare_result_semantics(five)

    def test_entity_and_compare_bind_the_outer_ranking_group_snapshot_pair(self):
        leaderboard = _active_leaderboard()
        group = leaderboard["ranking_groups"][0]
        entry = deepcopy(group["entries"][0])
        evaluated_configuration = {
            "object": "evaluated_configuration",
            "schema_version": "1",
            "evaluated_configuration_id": entry["evaluated_configuration_id"],
            "passport": {
                "object": "configuration_passport",
                "schema_version": "1",
                "entity_kind": "model_configuration",
                "canonical_name": "Example",
                "revision": "1",
                "interaction_policy": "direct_prompt",
                "configuration_passport_class": "model-configuration-v1",
                "harness": None,
                "scaffold": None,
                "tools": [],
                "quantization": None,
                "system_prompt_policy": None,
                "environment": None,
            },
        }
        # Replace the fixture ID with the passport's actual content-addressed identity.
        evaluated_configuration["evaluated_configuration_id"] = (
            f"config_{sha256_hex(evaluated_configuration['passport'])}"
        )
        entry["evaluated_configuration_id"] = evaluated_configuration["evaluated_configuration_id"]
        common = {
            "cell_id": leaderboard["cell_id"],
            "manifest_version": leaderboard["manifest_version"],
            "methodology_version": leaderboard["methodology_version"],
            "snapshot_set_id": leaderboard["snapshot_set_id"],
            "snapshot_set_descriptor": leaderboard["snapshot_set_descriptor"],
            "ranking_group_id": group["ranking_group_id"],
            "evidence_snapshot_id": group["evidence_snapshot_id"],
            "explorer_view": None,
            "state": "active",
            "eligibility_summary": group["eligibility_summary"],
            "generated_at": leaderboard["generated_at"],
        }
        entity = {
            "object": "entity_detail",
            "schema_version": "1",
            **common,
            "entity": {
                "evaluated_configuration": evaluated_configuration,
                "ranking": entry["ranking"],
                "citations": deepcopy(group["citations"]),
            },
        }
        compare = {
            "object": "compare_result",
            "schema_version": "1",
            **common,
            "entity_kind": group["entity_kind"],
            "interaction_policy": group["interaction_policy"],
            "configuration_passport_class": group["configuration_passport_class"],
            "entities": [
                {**entry, "citations": deepcopy(group["citations"])},
                {
                    **entry,
                    "evaluated_configuration_id": f"config_{'d' * 64}",
                    "ranking": {**entry["ranking"], "rank": 2},
                    "citations": deepcopy(group["citations"]),
                },
            ],
        }
        verify_entity_detail_semantics(entity)
        verify_compare_result_semantics(compare)

        for document, verifier in (
            (entity, verify_entity_detail_semantics),
            (compare, verify_compare_result_semantics),
        ):
            with self.subTest(verifier=verifier.__name__):
                wrong_group = {**document, "ranking_group_id": "rg-other"}
                with self.assertRaisesRegex(ValueError, "ranking-group snapshot pair"):
                    verifier(wrong_group)


def _active_leaderboard() -> dict:
    snapshot_id = f"snapshot_{'a' * 64}"
    ranking_group_id = "rg-code-generation-model"
    descriptor = SnapshotSetDescriptorV1(
        cell_id="code-generation",
        manifest_version="2026-07-09.2",
        methodology_version="2026-07-09.2.truth-kernel-v1",
        ranking_group_snapshots=(
            RankingGroupSnapshotRefV1(
                ranking_group_id=ranking_group_id,
                evidence_snapshot_id=snapshot_id,
            ),
        ),
    )
    return {
        "object": "leaderboard",
        "schema_version": "1",
        "cell_state": "active",
        "cell_id": descriptor.cell_id,
        "manifest_version": descriptor.manifest_version,
        "methodology_version": descriptor.methodology_version,
        "snapshot_set_id": descriptor.snapshot_set_id,
        "snapshot_set_descriptor": descriptor.to_dict(),
        "generated_at": "2026-07-10T00:00:00Z",
        "ranking_groups": [
            {
                "ranking_group_id": ranking_group_id,
                "entity_kind": "model_configuration",
                "interaction_policy": "direct_prompt",
                "configuration_passport_class": "model-configuration-v1",
                "state": "active",
                "evidence_snapshot_id": snapshot_id,
                "eligibility_summary": {
                    "published_claim": "top_set",
                    "rank_eligible_configuration_count": 1,
                    "current_independent_family_count": 3,
                    "required_independent_family_count": 3,
                    "current_overlap_count": 2,
                    "required_overlap_count": 2,
                    "calibration_status": "validated",
                    "gap_codes": [],
                },
                "entries": [
                    {
                        "evaluated_configuration_id": f"config_{'c' * 64}",
                        "ranking": {
                            "rank": 1,
                            "display_name": "Example",
                            "capability_score": 0.8,
                            "uncertainty": {
                                "kind": "interval",
                                "level": 0.95,
                                "lower": 0.75,
                                "upper": 0.85,
                            },
                            "in_top_set": True,
                            "evidence_family_count": 3,
                            "caveat_codes": [],
                        },
                    }
                ],
                "citations": [{
                    "benchmark_family_id": "family-a",
                    "source_artifact_id": f"artifact_{'a' * 64}",
                    "title": "Family A",
                    "url": "https://example.com/a",
                }],
                "explorer_views": [],
            }
        ],
    }


def _explorer_leaderboard() -> dict:
    leaderboard = _active_leaderboard()
    group = leaderboard["ranking_groups"][0]
    first = deepcopy(group["entries"][0])
    first["ranking"].update(rank=1, in_top_set=False, evidence_family_count=1, caveat_codes=["evidence_stale"])
    second = deepcopy(first)
    second["evaluated_configuration_id"] = f"config_{'d' * 64}"
    second["ranking"].update(rank=2, display_name="Second")
    group.update(
        state="preview",
        entries=[],
        explorer_views=[{
            "benchmark_family_id": "family-a",
            "feed_id": "family-a-feed",
            "metric_direction": "higher",
            "observed_at": "2026-07-09T00:00:00Z",
            "expires_at": "2026-07-09T12:00:00Z",
            "agreement": "single_source",
            "entries": [first, second],
            "citations": [{
                "benchmark_family_id": "family-a",
                "source_artifact_id": f"artifact_{'a' * 64}",
                "title": "Family A",
                "url": "https://example.com/a",
            }],
        }],
        eligibility_summary={
            "published_claim": "explorer",
            "rank_eligible_configuration_count": 0,
            "current_independent_family_count": 1,
            "required_independent_family_count": 3,
            "current_overlap_count": 2,
            "required_overlap_count": 2,
            "calibration_status": "unvalidated",
            "gap_codes": ["calibration_unvalidated", "evidence_stale", "insufficient_independent_families", "no_rank_eligible_configurations"],
        },
    )
    return _with_evidence_snapshot_id(leaderboard, f"explorer_{'e' * 64}")


def _with_evidence_snapshot_id(leaderboard: dict, evidence_snapshot_id: str) -> dict:
    updated = deepcopy(leaderboard)
    descriptor = SnapshotSetDescriptorV1.from_dict(updated["snapshot_set_descriptor"])
    replacement = SnapshotSetDescriptorV1(
        cell_id=descriptor.cell_id,
        manifest_version=descriptor.manifest_version,
        methodology_version=descriptor.methodology_version,
        ranking_group_snapshots=(
            RankingGroupSnapshotRefV1(
                ranking_group_id=updated["ranking_groups"][0]["ranking_group_id"],
                evidence_snapshot_id=evidence_snapshot_id,
            ),
        ),
    )
    updated["snapshot_set_descriptor"] = replacement.to_dict()
    updated["snapshot_set_id"] = replacement.snapshot_set_id
    updated["ranking_groups"][0]["evidence_snapshot_id"] = evidence_snapshot_id
    return updated


if __name__ == "__main__":
    unittest.main()
