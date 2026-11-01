from __future__ import annotations

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "packages" / "core" / "src"
SCHEMAS = REPO_ROOT / "schemas"
GOLDEN = REPO_ROOT / "examples" / "decision-contract-v2.golden.json"
sys.path.insert(0, str(CORE_SRC))

from evalrank_core.canonical_json import sha256_hex  # noqa: E402
import evalrank_core.decision_contracts as decision_contracts  # noqa: E402
from evalrank_core.decision_contracts import (  # noqa: E402
    DEFAULT_AGENT_TASK_MIX,
    AdapterMetadataV1,
    AvailabilityFactV1,
    ConfigurationPassportV1,
    ContextFactV1,
    ContinuousMetricV1,
    DecisionCaveatV2,
    DecisionExclusionV2,
    DecisionFamilyV2,
    DecisionPriceV2,
    DecisionQueryV2,
    DecisionReceiptV2,
    DecisionSelectionV2,
    DecisionUsageV2,
    EffortMultiplierV2,
    EvaluatedConfigurationV1,
    IntervalUncertaintyV1,
    IDENTITY_TRIPLES,
    PairwisePreferenceMetricV1,
    PassAtKMetricV1,
    PricingScheduleFactV1,
    ProportionMetricV1,
    RankOnlyMetricV1,
    RunInputArtifactV1,
    RunProvenanceV1,
    ServingOfferV1,
    SourceArtifactV1,
    StandardErrorUncertaintyV1,
    TrialPolicyV1,
    UnknownUncertaintyV1,
    ObservationV1,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
ARTIFACT_A = f"artifact_{HASH_A}"
CONFIGURATION_ID = "config_"  # completed from the passport hash in helpers below
MANIFEST = json.loads((REPO_ROOT / "catalog" / "manifest.json").read_text(encoding="utf-8"))


class SourceAndRunProvenanceTests(unittest.TestCase):
    def test_source_artifact_identity_is_its_content_hash(self):
        artifact = _source_artifact()

        self.assertEqual(ARTIFACT_A, artifact.source_artifact_id)
        self.assertEqual(artifact, SourceArtifactV1.from_dict(artifact.to_dict()))

        with self.assertRaisesRegex(ValueError, "source_artifact_id"):
            replace(artifact, source_artifact_id=f"artifact_{HASH_B}")

    def test_source_artifact_rejects_unknown_or_mutable_source_fields(self):
        payload = _source_artifact().to_dict()
        payload["latest_url"] = "https://example.test/latest"

        with self.assertRaisesRegex(ValueError, "unknown fields"):
            SourceArtifactV1.from_dict(payload)

    def test_run_provenance_is_typed_closed_and_references_exact_artifact_inputs(self):
        provenance = _provenance()

        self.assertEqual(
            (
                RunInputArtifactV1(role="categories", source_artifact_id=f"artifact_{HASH_B}"),
                RunInputArtifactV1(role="primary", source_artifact_id=ARTIFACT_A),
            ),
            provenance.source_artifacts,
        )
        self.assertNotIn("canonical_url", provenance.to_dict())
        self.assertEqual(provenance, RunProvenanceV1.from_dict(provenance.to_dict()))

        missing = provenance.to_dict()
        del missing["source_artifacts"]
        with self.assertRaisesRegex(ValueError, "source_artifacts"):
            RunProvenanceV1.from_dict(missing)

        reversed_inputs = provenance.to_dict()
        reversed_inputs["source_artifacts"].reverse()
        with self.assertRaisesRegex(ValueError, "sorted by role"):
            RunProvenanceV1.from_dict(reversed_inputs)

        duplicate_artifact = provenance.to_dict()
        duplicate_artifact["source_artifacts"][0]["source_artifact_id"] = ARTIFACT_A
        with self.assertRaisesRegex(ValueError, "unique"):
            RunProvenanceV1.from_dict(duplicate_artifact)

        unknown = provenance.to_dict()
        unknown["source"] = "mutable-latest"
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            RunProvenanceV1.from_dict(unknown)

    def test_only_versioned_adapter_metadata_payload_is_open(self):
        provenance = _provenance()
        payload = provenance.to_dict()
        payload["adapter_metadata"]["payload"] = {"upstream_column": "score", "rows": 12}

        parsed = RunProvenanceV1.from_dict(payload)

        self.assertEqual("score", parsed.adapter_metadata.payload["upstream_column"])
        payload["adapter_metadata"]["unversioned"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            RunProvenanceV1.from_dict(payload)

    def test_adapter_metadata_is_recursively_immutable(self):
        metadata = AdapterMetadataV1(
            schema_version="1",
            payload={"nested": {"value": 1}, "items": [{"value": 2}]},
        )

        with self.assertRaises(TypeError):
            metadata.payload["nested"]["value"] = 99
        with self.assertRaises(TypeError):
            metadata.payload["items"][0]["value"] = 88
        self.assertEqual(
            {"nested": {"value": 1}, "items": [{"value": 2}]},
            metadata.to_dict()["payload"],
        )


class ObservationTests(unittest.TestCase):
    def test_metric_and_uncertainty_unions_round_trip(self):
        metrics = (
            ProportionMetricV1(value="0.75", numerator=3, denominator=4),
            ContinuousMetricV1(value="12.5", unit="seconds", n_items=20),
            PassAtKMetricV1(value="0.5", k=1, successful_items=5, evaluated_items=10),
            PairwisePreferenceMetricV1(value="1180", scale="elo", comparison_count=240),
            RankOnlyMetricV1(rank=2, candidate_count=17),
        )
        for metric in metrics:
            with self.subTest(metric=metric.kind):
                observation = ObservationV1(
                    observation_id=f"obs_{metric.kind}_unknown",
                    evaluated_configuration_id=_evaluated_configuration().evaluated_configuration_id,
                    metric=metric,
                    uncertainty=UnknownUncertaintyV1(),
                    provenance=_provenance(),
                )
                self.assertEqual(observation, ObservationV1.from_dict(observation.to_dict()))

        for uncertainty in (
            StandardErrorUncertaintyV1(value="0.04"),
            IntervalUncertaintyV1(
                low="0.6",
                high="0.9",
                confidence_level="0.95",
                method="wilson",
            ),
        ):
            with self.subTest(uncertainty=uncertainty.kind):
                observation = ObservationV1(
                    observation_id=f"obs_proportion_{uncertainty.kind}",
                    evaluated_configuration_id=_evaluated_configuration().evaluated_configuration_id,
                    metric=ProportionMetricV1(value="0.75", numerator=3, denominator=4),
                    uncertainty=uncertainty,
                    provenance=_provenance(),
                )
                self.assertEqual(observation, ObservationV1.from_dict(observation.to_dict()))

    def test_metrics_require_canonical_decimal_text_and_real_counts(self):
        invalid = (
            lambda: ProportionMetricV1(value="0.750", numerator=3, denominator=4),
            lambda: ProportionMetricV1(value="0.75", numerator=4, denominator=3),
            lambda: ProportionMetricV1(value="0.5", numerator=1, denominator=3),
            lambda: PassAtKMetricV1(value="1e-2", k=1, successful_items=1, evaluated_items=2),
            lambda: PassAtKMetricV1(value="0.5", k=True, successful_items=1, evaluated_items=2),
            lambda: ContinuousMetricV1(value="NaN", unit="seconds", n_items=1),
            lambda: RankOnlyMetricV1(rank=0, candidate_count=2),
        )

        for constructor in invalid:
            with self.subTest(constructor=constructor):
                with self.assertRaises((TypeError, ValueError)):
                    constructor()

        rounded = ProportionMetricV1(value="0.333333", numerator=1, denominator=3)
        self.assertEqual("0.333333", rounded.value)
        with self.assertRaisesRegex(ValueError, "six fractional digits"):
            ProportionMetricV1(value="0", numerator=1, denominator=2)

    def test_observation_requires_typed_provenance_and_rejects_unknown_keys(self):
        observation = _observation()
        payload = observation.to_dict()
        payload["provenance"] = {"source": "mutable-latest"}

        with self.assertRaisesRegex(ValueError, "source_artifacts"):
            ObservationV1.from_dict(payload)

        payload = observation.to_dict()
        payload["score"] = 0.75
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            ObservationV1.from_dict(payload)

    def test_observation_uncertainty_must_describe_the_native_metric(self):
        with self.assertRaisesRegex(ValueError, "contain metric"):
            ObservationV1(
                observation_id="obs_interval_mismatch",
                evaluated_configuration_id=_evaluated_configuration().evaluated_configuration_id,
                metric=ProportionMetricV1(value="0.75", numerator=3, denominator=4),
                uncertainty=IntervalUncertaintyV1(
                    low="0.1",
                    high="0.2",
                    confidence_level="0.95",
                    method="reported",
                ),
                provenance=_provenance(),
            )

        with self.assertRaisesRegex(ValueError, "rank_only"):
            ObservationV1(
                observation_id="obs_rank_uncertainty",
                evaluated_configuration_id=_evaluated_configuration().evaluated_configuration_id,
                metric=RankOnlyMetricV1(rank=2, candidate_count=3),
                uncertainty=StandardErrorUncertaintyV1(value="0.1"),
                provenance=_provenance(),
            )


class ConfigurationTests(unittest.TestCase):
    def test_only_manifest_resolved_identity_triples_are_allowed(self):
        allowed = {
            (
                row["entity_kind"],
                row["interaction_policy"],
                row["configuration_passport_class"],
            )
            for row in MANIFEST["ranking_groups"]
            if row["entity_kind"] != "unresolved"
        }

        self.assertEqual(allowed, IDENTITY_TRIPLES)

        for entity_kind, interaction_policy, passport_class in allowed:
            with self.subTest(entity_kind=entity_kind):
                passport = _passport(
                    entity_kind=entity_kind,
                    interaction_policy=interaction_policy,
                    configuration_passport_class=passport_class,
                    harness="harness-v1" if entity_kind == "agent_system" else None,
                    scaffold="scaffold-v1" if entity_kind == "agent_system" else None,
                )
                self.assertEqual(entity_kind, passport.entity_kind)

        schema = json.loads((SCHEMAS / "configuration-passport.schema.json").read_text(encoding="utf-8"))
        schema_triples = {
            (
                branch["properties"]["entity_kind"]["const"],
                branch["properties"]["interaction_policy"]["const"],
                branch["properties"]["configuration_passport_class"]["const"],
            )
            for branch in schema["allOf"][0]["oneOf"]
        }
        self.assertEqual(allowed, schema_triples)

        with self.assertRaisesRegex(ValueError, "resolved identity triple"):
            _passport(entity_kind="unresolved", interaction_policy="unresolved", configuration_passport_class="unresolved-v1")
        with self.assertRaisesRegex(ValueError, "resolved identity triple"):
            _passport(entity_kind="model_configuration", interaction_policy="agentic")

    def test_agent_system_requires_harness_and_scaffold(self):
        for missing in ("harness", "scaffold"):
            kwargs = {
                "entity_kind": "agent_system",
                "interaction_policy": "agentic",
                "configuration_passport_class": "agent-system-v1",
                "harness": "harness-v1",
                "scaffold": "scaffold-v1",
            }
            kwargs[missing] = None
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(ValueError, missing):
                    _passport(**kwargs)

    def test_passport_sorts_tools_and_rejects_duplicates(self):
        passport = _passport(tools=("web", "code"))

        self.assertEqual(("code", "web"), passport.tools)
        self.assertEqual(["code", "web"], passport.to_dict()["tools"])
        with self.assertRaisesRegex(ValueError, "tools must be unique"):
            _passport(tools=("code", "code"))

    def test_evaluated_configuration_id_hashes_the_exact_passport(self):
        evaluated = _evaluated_configuration()

        self.assertEqual(f"config_{sha256_hex(evaluated.passport.to_dict())}", evaluated.evaluated_configuration_id)
        self.assertEqual(evaluated, EvaluatedConfigurationV1.from_dict(evaluated.to_dict()))
        with self.assertRaisesRegex(ValueError, "evaluated_configuration_id"):
            replace(evaluated, evaluated_configuration_id=f"config_{HASH_B}")


class ServingOfferTests(unittest.TestCase):
    def test_v1_exposes_schedule_pricing_without_the_legacy_flat_fact(self):
        self.assertTrue(hasattr(decision_contracts, "PricingScheduleFactV1"))
        self.assertFalse(hasattr(decision_contracts, "PricingFactV1"))

    def test_projected_cost_joins_every_nonzero_component_and_ceilings_once(self):
        usage = decision_contracts.UsageProfileV1(
            basis="measured",
            uncached_input_tokens=1,
            cached_read_tokens=1,
            output_tokens=1,
            cache_writes=(decision_contracts.CacheWriteUsageV1(ttl_seconds=300, tokens=1),),
            cache_storage_token_seconds=1,
        )
        pricing = decision_contracts.PricingScheduleFactV1(
            uncached_input_microusd_per_million_tokens=1,
            cached_read_microusd_per_million_tokens=1,
            output_microusd_per_million_tokens=1,
            cache_write_rates=(
                decision_contracts.CacheWriteRateV1(
                    ttl_seconds=300,
                    microusd_per_million_tokens=1,
                ),
            ),
            cache_storage_microusd_per_million_token_hours=1,
            observed_at="2026-07-09T00:00:00Z",
            effective_at="2026-07-09T01:00:00Z",
            expires_at="2026-07-10T00:00:00Z",
            source_artifact_id=ARTIFACT_A,
        )

        self.assertEqual(1, decision_contracts.projected_cost_microusd(usage, pricing))
        self.assertEqual(pricing, decision_contracts.PricingScheduleFactV1.from_dict(pricing.to_dict()))

    def test_usage_profile_rejects_a_zero_workload(self):
        for storage in (0, 1):
            with self.subTest(storage=storage), self.assertRaisesRegex(
                ValueError, "non-zero workload"
            ):
                decision_contracts.UsageProfileV1(
                    basis="measured",
                    uncached_input_tokens=0,
                    cached_read_tokens=0,
                    output_tokens=0,
                    cache_writes=(),
                    cache_storage_token_seconds=storage,
                )

    def test_projected_cost_fails_closed_for_each_missing_nonzero_cache_rate(self):
        base_usage = decision_contracts.UsageProfileV1(
            basis="measured",
            uncached_input_tokens=0,
            cached_read_tokens=1,
            output_tokens=0,
            cache_writes=(),
            cache_storage_token_seconds=0,
        )
        base_pricing = decision_contracts.PricingScheduleFactV1(
            uncached_input_microusd_per_million_tokens=1,
            cached_read_microusd_per_million_tokens=None,
            output_microusd_per_million_tokens=1,
            cache_write_rates=(),
            cache_storage_microusd_per_million_token_hours=None,
            observed_at="2026-07-09T00:00:00Z",
            effective_at="2026-07-09T00:00:00Z",
            expires_at="2026-07-10T00:00:00Z",
            source_artifact_id=ARTIFACT_A,
        )

        self.assertIsNone(decision_contracts.projected_cost_microusd(base_usage, base_pricing))
        self.assertIsNone(
            decision_contracts.projected_cost_microusd(
                replace(
                    base_usage,
                    cached_read_tokens=0,
                    cache_writes=(decision_contracts.CacheWriteUsageV1(ttl_seconds=300, tokens=1),),
                ),
                base_pricing,
            )
        )
        self.assertIsNone(
            decision_contracts.projected_cost_microusd(
                replace(
                    base_usage,
                    uncached_input_tokens=1,
                    cached_read_tokens=0,
                    cache_storage_token_seconds=1,
                ),
                base_pricing,
            )
        )
        with self.assertRaisesRegex(ValueError, "non-zero workload"):
            replace(base_usage, cached_read_tokens=0)

    def test_offer_requires_three_independently_dated_sourced_facts(self):
        offer = _serving_offer()

        self.assertEqual(ARTIFACT_A, offer.context.source_artifact_id)
        self.assertEqual(ARTIFACT_A, offer.availability.source_artifact_id)
        self.assertEqual(ARTIFACT_A, offer.pricing.source_artifact_id)
        self.assertEqual(offer, ServingOfferV1.from_dict(offer.to_dict()))

        payload = offer.to_dict()
        del payload["pricing"]["source_artifact_id"]
        with self.assertRaisesRegex(ValueError, "source_artifact_id"):
            ServingOfferV1.from_dict(payload)


class DecisionQueryTests(unittest.TestCase):
    def test_three_fields_are_a_complete_query_and_only_sent_fields_serialize(self):
        query = DecisionQueryV2.from_dict(
            {"schema_version": "2", "cell_id": "writing", "objective": "lowest_cost_within_top_set"}
        )

        self.assertEqual(
            {
                "object": "decision_query",
                "schema_version": "2",
                "cell_id": "writing",
                "objective": "lowest_cost_within_top_set",
            },
            query.to_dict(),
        )
        self.assertEqual(query, DecisionQueryV2.from_dict(query.to_dict()))

    def test_query_sorts_set_filters_and_rejects_duplicates_nulls_and_unknown_fields(self):
        query = _query(provider_ids=("openai", "azure"), regions=("us-west", "eu-west"))

        self.assertEqual(("azure", "openai"), query.provider_ids)
        self.assertEqual(("eu-west", "us-west"), query.regions)
        with self.assertRaisesRegex(ValueError, "unique"):
            _query(provider_ids=("openai", "openai"))
        with self.assertRaisesRegex(ValueError, "must not be null"):
            DecisionQueryV2.from_dict({**_query().to_dict(), "provider_ids": None})
        for field, value in (
            ("ranking_group_id", "rg-writing"),
            ("entity_kind", "model_configuration"),
            ("interaction_policy", "direct_prompt"),
            ("configuration_passport_class", "model-configuration-v1"),
            ("monthly_budget_microusd", 5),
            ("zero_cache_sensitivity_usage_profile", _usage_profile().to_dict()),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "unknown fields"):
                DecisionQueryV2.from_dict({**_query().to_dict(), field: value})

    def test_query_rejects_v1_and_closed_enum_violations(self):
        with self.assertRaisesRegex(ValueError, "schema_version must be 2"):
            DecisionQueryV2.from_dict({**_query().to_dict(), "schema_version": "1"})
        for field, value in (
            ("objective", "top_set"),
            ("api", "completions"),
            ("reasoning_effort", "ultra"),
            ("via", "Open Router"),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                _query(**{field: value})

    def test_via_defaults_from_provider_ids(self):
        self.assertEqual("openai", _query(provider_ids=("openai",)).resolved_via)
        self.assertEqual("openrouter", _query(provider_ids=("openai", "azure")).resolved_via)
        self.assertEqual("openrouter", _query().resolved_via)
        self.assertEqual("anthropic", _query(via="anthropic").resolved_via)


class DecisionReceiptTests(unittest.TestCase):
    def test_receipt_id_hashes_the_full_canonical_body_except_receipt_id(self):
        receipt = _receipt()
        body = receipt.to_body_dict()

        self.assertNotIn("receipt_id", body)
        self.assertEqual(f"receipt_{sha256_hex(body)}", receipt.receipt_id)
        self.assertEqual(receipt, DecisionReceiptV2.from_dict(receipt.to_dict()))
        tampered = receipt.to_dict()
        tampered["decided_at"] = "2026-11-01T09:00:01Z"
        with self.assertRaisesRegex(ValueError, "receipt_id must hash"):
            DecisionReceiptV2.from_dict(tampered)

    def test_selections_keep_their_order_and_set_like_fields_sort(self):
        cheap = _selection("model-a", cost=100)
        dear = _selection("model-b", cost=200)
        receipt = _receipt(
            selections=(cheap, dear),
            snapshot_ids=(f"explorer_{HASH_B}", f"explorer_{HASH_A}"),
            exclusions=(
                DecisionExclusionV2(model_key="zeta", code="no_serving_offer"),
                DecisionExclusionV2(model_key="alpha", code="ambiguous_identity"),
            ),
        )
        body = receipt.to_body_dict()

        self.assertEqual(["model-a", "model-b"], [row["model_id"] for row in body["selections"]])
        self.assertEqual([f"explorer_{HASH_A}", f"explorer_{HASH_B}"], body["snapshot_ids"])
        self.assertEqual(["alpha", "zeta"], [row["model_key"] for row in body["exclusions"]])
        with self.assertRaisesRegex(ValueError, "cheapest"):
            _receipt(selections=(dear, cheap))

    def test_pick_and_abstain_shapes_are_exclusive(self):
        with self.assertRaisesRegex(ValueError, "abstain carries no selection"):
            _receipt(outcome="abstain", abstain_reasons=("no_ranked_candidate",))
        with self.assertRaisesRegex(ValueError, "abstain carries no selection"):
            _receipt(outcome="abstain", selections=())
        with self.assertRaisesRegex(ValueError, "pick carries"):
            _receipt(abstain_reasons=("stale_evidence",))
        with self.assertRaisesRegex(ValueError, "abstain_reasons item"):
            _receipt(outcome="abstain", selections=(), abstain_reasons=("insufficient_comparable_evidence",))
        for reason in ("no_ranked_candidate", "no_eligible_offer", "stale_evidence", "not_a_model_cell"):
            with self.subTest(reason=reason):
                receipt = _receipt(outcome="abstain", selections=(), snapshot_ids=(), abstain_reasons=(reason,))
                self.assertEqual((reason,), receipt.abstain_reasons)

    def test_value_objective_needs_priced_selections_and_capability_objective_picks_the_best(self):
        unpriced = _selection("model-c", cost=None)
        with self.assertRaisesRegex(ValueError, "priced configurations only"):
            _receipt(selections=(_selection("model-a", cost=100), unpriced))
        top = _query(objective="capability_top_set")
        best = _selection("model-c", cost=None, ratio_ppm=1_000_000)
        runner_up = _selection("model-a", cost=100, ratio_ppm=990_000)

        self.assertEqual("model-c", _receipt(query=top, selections=(best, runner_up)).selections[0].model_id)
        with self.assertRaisesRegex(ValueError, "highest-scoring"):
            _receipt(query=top, selections=(runner_up, best))

    def test_pinned_effort_api_and_provider_filters_bind_every_selection(self):
        with self.assertRaisesRegex(ValueError, "pinned reasoning_effort"):
            _receipt(query=_query(reasoning_effort="low"))
        with self.assertRaisesRegex(ValueError, "query's api"):
            _receipt(query=_query(api="responses"))
        with self.assertRaisesRegex(ValueError, "provider_ids"):
            _receipt(query=_query(provider_ids=("azure",)))
        pinned = _receipt(query=_query(reasoning_effort="low"), selections=(_selection("model-a", effort="low"),))
        self.assertEqual("low", pinned.selections[0].reasoning_effort)

    def test_usage_profile_echoes_the_caller_or_states_the_default_mix(self):
        self.assertEqual(
            DecisionUsageV2(basis="default_agent_task_mix", profile=DEFAULT_AGENT_TASK_MIX),
            _receipt().usage_profile,
        )
        self.assertEqual(
            {"basis": "estimated", "uncached_input_tokens": 1000, "cached_read_tokens": 8000, "output_tokens": 500, "cache_writes": [], "cache_storage_token_seconds": 0},
            DEFAULT_AGENT_TASK_MIX.to_dict(),
        )
        caller = _receipt(query=_query(usage_profile=_usage_profile()))
        self.assertEqual(DecisionUsageV2(basis="caller", profile=_usage_profile()), caller.usage_profile)
        payload = caller.to_dict()
        payload["usage_profile"]["basis"] = "default_agent_task_mix"
        with self.assertRaisesRegex(ValueError, "echo"):
            DecisionReceiptV2.from_dict(payload)

    def test_selection_cost_multiplier_and_caveats_are_consistent(self):
        with self.assertRaisesRegex(ValueError, "cost_unmeasured caveat"):
            replace(_selection("model-a"), caveats=(DecisionCaveatV2(code="cost_unmeasured"),))
        with self.assertRaisesRegex(ValueError, "effort_multiplier"):
            replace(_selection("model-a"), effort_multiplier=None)
        with self.assertRaisesRegex(ValueError, "exactly 1"):
            EffortMultiplierV2(multiplier_ppm=1_510_000, source="comparison_level")
        with self.assertRaisesRegex(ValueError, "other than the selection's"):
            replace(
                _selection("model-a"),
                caveats=(DecisionCaveatV2(code="effort_substituted", measured_effort="medium", gap_ppm=1),),
            )
        with self.assertRaisesRegex(ValueError, "must not exceed"):
            _selection("model-a", ratio_ppm=1_000_001)
        substituted = replace(
            _selection("model-a"),
            caveats=(DecisionCaveatV2(code="effort_substituted", measured_effort="max", gap_ppm=12_000),),
        )
        self.assertEqual(
            [{"code": "effort_substituted", "measured_effort": "max", "gap_ppm": 12_000}],
            substituted.to_dict()["caveats"],
        )
        self.assertEqual(substituted, DecisionSelectionV2.from_dict(substituted.to_dict()))

    def test_selections_never_repeat_a_configuration(self):
        with self.assertRaisesRegex(ValueError, "repeat"):
            _receipt(selections=(_selection("model-a"), _selection("model-a")))

    def test_golden_corpus_decodes_rehashes_and_covers_every_outcome(self):
        corpus = json.loads(GOLDEN.read_text(encoding="utf-8"))

        query = DecisionQueryV2.from_dict(corpus["query"]["input"])
        self.assertEqual(corpus["query"]["canonical"], query.canonical_json())
        names = []
        queries = set()
        for row in corpus["receipts"]:
            with self.subTest(name=row["name"]):
                receipt = DecisionReceiptV2.from_dict({**row["body"], "receipt_id": row["receipt_id"]})
                self.assertEqual(row["body"], receipt.to_body_dict())
                self.assertEqual(f"receipt_{row['body_sha256']}", receipt.receipt_id)
                self.assertEqual(row["body_sha256"], sha256_hex(row["body"]))
                names.append(row["name"])
                queries.add(receipt.query.canonical_json())
        self.assertEqual(
            [
                "value_pick",
                "top_set_pick",
                "pinned_level",
                "substituted_effort",
                "abstain_no_ranked_candidate",
                "abstain_no_eligible_offer",
                "abstain_stale_evidence",
                "abstain_not_a_model_cell",
            ],
            names,
        )
        self.assertEqual(len(names), len(queries), "every golden receipt answers a distinct query")
        by_name = {row["name"]: row["body"] for row in corpus["receipts"]}
        self.assertEqual(
            [{"code": "effort_substituted", "measured_effort": "max", "gap_ppm": 12000}],
            by_name["substituted_effort"]["selections"][0]["caveats"],
        )
        self.assertIn({"code": "cost_unmeasured"}, by_name["top_set_pick"]["selections"][0]["caveats"])
        self.assertEqual("openai/gpt-6-sol", by_name["top_set_pick"]["selections"][0]["model_id"])
        for name in ("abstain_no_ranked_candidate", "abstain_no_eligible_offer", "abstain_stale_evidence", "abstain_not_a_model_cell"):
            self.assertEqual([name.removeprefix("abstain_")], by_name[name]["abstain_reasons"])
        for row in corpus["rejection_vectors"][2:]:
            with self.subTest(rejection=row["name"]), self.assertRaises(ValueError):
                DecisionQueryV2.from_dict(row["value"])

    def test_golden_file_is_generated_by_its_builder(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "build_decision_golden.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_golden_cells_and_families_resolve_against_the_canonical_manifest(self):
        corpus = json.loads(GOLDEN.read_text(encoding="utf-8"))
        cells = {row["cell_id"] for row in MANIFEST["cells"]}
        families = {row["benchmark_family_id"] for row in MANIFEST["benchmark_families"]}

        for row in corpus["receipts"]:
            with self.subTest(name=row["name"]):
                self.assertIn(row["body"]["query"]["cell_id"], cells)
                for family in row["body"]["families"]:
                    self.assertIn(family["family_id"], families)
                for selection in row["body"]["selections"]:
                    multiplier = selection["effort_multiplier"]
                    if multiplier is not None and multiplier["source"] != "comparison_level":
                        self.assertIn(multiplier["source"], families)

    def test_examples_resolve_against_the_canonical_manifest(self):
        families = {row["benchmark_family_id"] for row in MANIFEST["benchmark_families"]}
        feeds = {(row["feed_id"], row["benchmark_family_id"]) for row in MANIFEST["feeds"]}
        provenance = _provenance()

        self.assertIn(provenance.benchmark_family_id, families)
        self.assertIn((provenance.feed_id, provenance.benchmark_family_id), feeds)


class WireSchemaTests(unittest.TestCase):
    def test_all_eight_wire_schemas_are_closed_and_uniquely_identified(self):
        names = (
            "source-artifact.schema.json",
            "run-provenance.schema.json",
            "observation.schema.json",
            "configuration-passport.schema.json",
            "evaluated-configuration.schema.json",
            "serving-offer.schema.json",
            "decision-query.schema.json",
            "decision-receipt.schema.json",
        )
        ids = set()
        for name in names:
            with self.subTest(name=name):
                schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
                self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
                self.assertEqual(f"https://evalrank.ai/schemas/{name}", schema["$id"])
                self.assertFalse(schema["additionalProperties"])
                ids.add(schema["$id"])
        self.assertEqual(len(names), len(ids))
        self.assertFalse((SCHEMAS / "evaluation-to-offer-link.schema.json").exists())

    def test_wire_schemas_match_the_core_v2_vocabulary(self):
        query = json.loads((SCHEMAS / "decision-query.schema.json").read_text(encoding="utf-8"))
        receipt = json.loads((SCHEMAS / "decision-receipt.schema.json").read_text(encoding="utf-8"))
        offer = json.loads((SCHEMAS / "serving-offer.schema.json").read_text(encoding="utf-8"))
        selection = receipt["$defs"]["Selection"]

        self.assertEqual("#/$defs/PricingScheduleFact", offer["properties"]["pricing"]["$ref"])
        self.assertEqual(["schema_version", "cell_id", "objective"], query["required"])
        self.assertEqual(
            {"object", "schema_version", "cell_id", "objective", *decision_contracts._QUERY_OPTIONAL},
            set(query["properties"]),
        )
        self.assertEqual(sorted(decision_contracts.DECISION_OBJECTIVES), sorted(query["properties"]["objective"]["enum"]))
        self.assertEqual(list(decision_contracts.REASONING_EFFORTS), query["properties"]["reasoning_effort"]["enum"])
        self.assertEqual(list(decision_contracts.REASONING_EFFORTS), selection["properties"]["reasoning_effort"]["enum"])
        self.assertEqual(sorted(decision_contracts.ABSTAIN_REASONS), sorted(receipt["properties"]["abstain_reasons"]["items"]["enum"]))
        self.assertEqual(sorted(decision_contracts.EXCLUSION_CODES), sorted(receipt["$defs"]["Exclusion"]["properties"]["code"]["enum"]))
        self.assertEqual(sorted(decision_contracts.LOCK_STATUSES), sorted(receipt["$defs"]["Family"]["properties"]["lock_status"]["enum"]))
        self.assertEqual(set(_selection("model-a").to_dict()), set(selection["required"]))
        self.assertEqual(set(_receipt().to_dict()), set(receipt["required"]))
        for retired in ("publication_snapshot", "methodology_version", "sensitivity", "evidence", "freshness", "reasons", "abstention_reason"):
            self.assertNotIn(retired, receipt["properties"])
        for retired in ("ranking_group_id", "entity_kind", "monthly_budget_microusd", "zero_cache_sensitivity_usage_profile"):
            self.assertNotIn(retired, query["properties"])
        for retired in ("EvaluationToOfferLinkV1", "PublicationSnapshotRefV1", "DecisionQueryV1", "DecisionReceiptV1", "monthly_cost_microusd"):
            self.assertFalse(hasattr(decision_contracts, retired))


def _source_artifact() -> SourceArtifactV1:
    return SourceArtifactV1(
        source_artifact_id=ARTIFACT_A,
        canonical_url="https://example.test/results/2026-07-09.json",
        upstream_version="2026-07-09",
        content_sha256=HASH_A,
        byte_length=1024,
        media_type="application/json",
        fetched_at="2026-07-09T00:00:00Z",
    )


def _provenance() -> RunProvenanceV1:
    return RunProvenanceV1(
        run_id="run_public_demo_01",
        benchmark_family_id="livecodebench",
        feed_id="livecodebench-discovery",
        source_artifacts=(
            RunInputArtifactV1(role="categories", source_artifact_id=f"artifact_{HASH_B}"),
            RunInputArtifactV1(role="primary", source_artifact_id=ARTIFACT_A),
        ),
        parser_id="livecodebench-json",
        parser_version="1",
        started_at="2026-07-09T00:01:00Z",
        completed_at="2026-07-09T00:02:00Z",
        harness_version="2026-07-01",
        environment_digest=None,
        scorer_version="1",
        trial_policy=TrialPolicyV1(attempts_per_item=1, seed_strategy="upstream", seed=None),
        adapter_metadata=AdapterMetadataV1(schema_version="1", payload={"column": "pass_rate"}),
    )


def _passport(**overrides) -> ConfigurationPassportV1:
    values = {
        "entity_kind": "model_configuration",
        "canonical_name": "public-demo-model",
        "revision": "2026-07-01",
        "interaction_policy": "direct_prompt",
        "configuration_passport_class": "model-configuration-v1",
        "harness": None,
        "scaffold": None,
        "tools": ("code",),
        "quantization": None,
        "system_prompt_policy": "benchmark-default",
        "environment": "public-sandbox-v1",
    }
    values.update(overrides)
    return ConfigurationPassportV1(**values)


def _evaluated_configuration() -> EvaluatedConfigurationV1:
    passport = _passport()
    return EvaluatedConfigurationV1(
        evaluated_configuration_id=f"config_{sha256_hex(passport.to_dict())}",
        passport=passport,
    )


def _observation() -> ObservationV1:
    return ObservationV1(
        observation_id="obs_public_demo_01",
        evaluated_configuration_id=_evaluated_configuration().evaluated_configuration_id,
        metric=ProportionMetricV1(value="0.75", numerator=3, denominator=4),
        uncertainty=IntervalUncertaintyV1(
            low="0.7",
            high="0.8",
            confidence_level="0.95",
            method="wilson",
        ),
        provenance=_provenance(),
    )


def _fact_times() -> dict[str, str]:
    return {
        "observed_at": "2026-07-09T00:00:00Z",
        "expires_at": "2026-07-10T00:00:00Z",
        "source_artifact_id": ARTIFACT_A,
    }


def _serving_offer() -> ServingOfferV1:
    return ServingOfferV1(
        serving_offer_id="offer_public-demo-us-west",
        provider_id="provider-public",
        sku="public-demo",
        region="us-west",
        context=ContextFactV1(context_window_tokens=128_000, **_fact_times()),
        availability=AvailabilityFactV1(status="available", **_fact_times()),
        pricing=PricingScheduleFactV1(
            uncached_input_microusd_per_million_tokens=1_000_000,
            cached_read_microusd_per_million_tokens=200_000,
            output_microusd_per_million_tokens=4_800_000,
            cache_write_rates=(
                decision_contracts.CacheWriteRateV1(
                    ttl_seconds=300,
                    microusd_per_million_tokens=1_200_000,
                ),
            ),
            cache_storage_microusd_per_million_token_hours=100_000,
            effective_at="2026-07-09T01:00:00Z",
            **_fact_times(),
        ),
    )


def _query(**overrides) -> DecisionQueryV2:
    values = {"cell_id": "writing", "objective": "lowest_cost_within_top_set"}
    values.update(overrides)
    return DecisionQueryV2(**values)


def _usage_profile() -> decision_contracts.UsageProfileV1:
    return decision_contracts.UsageProfileV1(
        basis="measured",
        uncached_input_tokens=2_400,
        cached_read_tokens=0,
        output_tokens=300,
        cache_writes=(),
        cache_storage_token_seconds=0,
    )


def _selection(model: str, *, cost: int | None = 100, ratio_ppm: int = 990_000, effort: str = "medium") -> DecisionSelectionV2:
    return DecisionSelectionV2(
        model_id=model,
        display_name=model.upper(),
        provider_id="openai",
        serving_offer_id=f"offer_{model}",
        reasoning_effort=effort,
        api="chat_completions",
        capability_ratio_ppm=ratio_ppm,
        family_coverage=2,
        price=DecisionPriceV2(
            input_microusd_per_million=1_250_000,
            cached_input_microusd_per_million=None,
            output_microusd_per_million=10_000_000,
        ),
        effort_multiplier=None if cost is None else EffortMultiplierV2(multiplier_ppm=1_000_000, source="comparison_level"),
        projected_cost_microusd=cost,
        latency_p50_ms=None,
        caveats=() if cost is not None else (DecisionCaveatV2(code="cost_unmeasured"),),
    )


def _receipt(**overrides) -> DecisionReceiptV2:
    values = {
        "query": _query(),
        "decided_at": "2026-11-01T09:00:00Z",
        "outcome": "pick",
        "snapshot_ids": (f"explorer_{HASH_A}",),
        "families": (
            DecisionFamilyV2(family_id="eqbench-creative-writing-v3", lock_status="admitted", weight_ppm=400_000, stale_at="2026-11-12T00:00:00Z"),
            DecisionFamilyV2(family_id="lmarena-instruction-following", lock_status="admitted", weight_ppm=600_000, stale_at=None),
        ),
        "selections": (_selection("model-a"),),
        "exclusions": (),
        "abstain_reasons": (),
    }
    values.update(overrides)
    return DecisionReceiptV2.create(**values)


if __name__ == "__main__":
    unittest.main()
