from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "packages" / "core" / "src"
SCHEMAS = REPO_ROOT / "schemas"
GOLDEN = REPO_ROOT / "examples" / "decision-contract-v1.golden.json"
sys.path.insert(0, str(CORE_SRC))

from evalrank_core.canonical_json import sha256_hex  # noqa: E402
import evalrank_core.decision_contracts as decision_contracts  # noqa: E402
from evalrank_core.decision_contracts import (  # noqa: E402
    AdapterMetadataV1,
    AvailabilityFactV1,
    ConfigurationPassportV1,
    ContextFactV1,
    ContinuousMetricV1,
    DecisionExclusionV1,
    DecisionFreshnessV1,
    DecisionQueryV1,
    DecisionReasonV1,
    DecisionReceiptV1,
    DecisionSelectionV1,
    DecisionSensitivityV1,
    EvaluatedConfigurationV1,
    EvaluationToOfferLinkV1,
    EvaluationToOfferLinkEvidenceV1,
    IntervalUncertaintyV1,
    IDENTITY_TRIPLES,
    PairwisePreferenceMetricV1,
    PassAtKMetricV1,
    PricingScheduleFactV1,
    ProportionMetricV1,
    PublicationSnapshotRefV1,
    RankOnlyMetricV1,
    RunInputArtifactV1,
    RunProvenanceV1,
    ServingOfferV1,
    SourceArtifactV1,
    StandardErrorUncertaintyV1,
    TrialPolicyV1,
    UnknownUncertaintyV1,
    ObservationV1,
    ObservationEvidenceV1,
    ServingOfferEvidenceV1,
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

    def test_monthly_cost_joins_every_nonzero_component_and_ceilings_once(self):
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

        self.assertEqual(1, decision_contracts.monthly_cost_microusd(usage, pricing))
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

    def test_monthly_cost_fails_closed_for_each_missing_nonzero_cache_rate(self):
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

        self.assertIsNone(decision_contracts.monthly_cost_microusd(base_usage, base_pricing))
        self.assertIsNone(
            decision_contracts.monthly_cost_microusd(
                replace(
                    base_usage,
                    cached_read_tokens=0,
                    cache_writes=(decision_contracts.CacheWriteUsageV1(ttl_seconds=300, tokens=1),),
                ),
                base_pricing,
            )
        )
        self.assertIsNone(
            decision_contracts.monthly_cost_microusd(
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

    def test_pricing_effective_at_controls_offer_eligibility(self):
        offer = _serving_offer()
        link = _offer_link()

        self.assertFalse(offer.is_decision_eligible(link, as_of="2026-07-09T00:30:00Z"))
        self.assertTrue(offer.is_decision_eligible(link, as_of="2026-07-09T01:00:00Z"))

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

    def test_offer_eligibility_requires_current_facts_and_exact_approved_link(self):
        offer = _serving_offer()
        link = _offer_link()

        self.assertTrue(offer.is_decision_eligible(link, as_of="2026-07-09T12:00:00Z"))
        for basis in ("benchmark_exact", "provider_attested", "operator_reviewed"):
            with self.subTest(basis=basis):
                self.assertTrue(replace(link, evidence_basis=basis).is_eligible(as_of="2026-07-09T12:00:00Z"))
        self.assertFalse(replace(link, evidence_basis="inferred").is_eligible(as_of="2026-07-09T12:00:00Z"))
        self.assertFalse(offer.is_decision_eligible(replace(link, compatibility="unresolved"), as_of="2026-07-09T12:00:00Z"))
        self.assertFalse(offer.is_decision_eligible(replace(link, review_state="pending"), as_of="2026-07-09T12:00:00Z"))
        self.assertFalse(offer.is_decision_eligible(link, as_of="2026-07-11T00:00:00Z"))

    def test_link_never_serializes_a_stale_eligibility_boolean(self):
        link = _offer_link()

        self.assertNotIn("eligible", link.to_dict())
        self.assertTrue(link.is_eligible(as_of="2026-07-09T12:00:00Z"))
        self.assertFalse(link.is_eligible(as_of="2026-07-10T00:00:00Z"))


class DecisionQueryTests(unittest.TestCase):
    def test_estimated_cached_usage_requires_an_exact_zero_cache_sensitivity(self):
        usage = _usage_profile()
        sensitivity = _zero_cache_sensitivity(usage)
        query = _query(usage_profile=usage, zero_cache_sensitivity_usage_profile=sensitivity)

        self.assertEqual(20_000_000, sensitivity.uncached_input_tokens)
        self.assertEqual(usage.output_tokens, sensitivity.output_tokens)
        self.assertEqual((), sensitivity.cache_writes)
        self.assertEqual(query, DecisionQueryV1.from_dict(query.to_dict()))

        with self.assertRaisesRegex(ValueError, "zero_cache_sensitivity"):
            replace(query, zero_cache_sensitivity_usage_profile=None)
        with self.assertRaisesRegex(ValueError, "total input"):
            replace(
                query,
                zero_cache_sensitivity_usage_profile=replace(
                    sensitivity,
                    uncached_input_tokens=sensitivity.uncached_input_tokens - 1,
                ),
            )
        with self.assertRaisesRegex(ValueError, "measured"):
            replace(query, usage_profile=replace(usage, basis="measured"))

    def test_query_rejects_removed_per_request_usage_axes(self):
        payload = _query().to_dict()
        payload["input_tokens_per_request"] = 1

        with self.assertRaisesRegex(ValueError, "unknown fields"):
            DecisionQueryV1.from_dict(payload)

    def test_query_sorts_set_filters_and_rejects_duplicates(self):
        first = _query(provider_ids=("provider-b", "provider-a"), regions=("us-west", "eu-west"))
        second = _query(provider_ids=("provider-a", "provider-b"), regions=("eu-west", "us-west"))

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(("provider-a", "provider-b"), first.provider_ids)
        with self.assertRaisesRegex(ValueError, "provider_ids must be unique"):
            _query(provider_ids=("provider-a", "provider-a"))

        corpus = json.loads(GOLDEN.read_text(encoding="utf-8"))
        vector = corpus["utf16_set_order"]
        self.assertEqual(
            vector["canonical"],
            DecisionQueryV1.from_dict({
                **_query().to_dict(),
                "provider_ids": vector["input"],
            }).to_dict()["provider_ids"],
        )

    def test_query_rejects_transport_free_text_and_null_filters(self):
        payload = _query().to_dict()
        for forbidden in ("request_id", "customer_id", "requested_at", "workload", "risk", "latency"):
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(ValueError, "unknown fields"):
                    DecisionQueryV1.from_dict({**payload, forbidden: "transport-does-not-belong-here"})

        for nullable_filter in ("provider_ids", "regions", "minimum_context_tokens", "monthly_budget_microusd"):
            with self.subTest(nullable_filter=nullable_filter):
                with self.assertRaisesRegex(ValueError, "must not be null"):
                    DecisionQueryV1.from_dict({**payload, nullable_filter: None})

    def test_lowest_cost_objective_requires_explicit_monthly_usage(self):
        payload = _query().to_dict()
        del payload["usage_profile"]
        del payload["zero_cache_sensitivity_usage_profile"]
        with self.assertRaisesRegex(ValueError, "usage_profile"):
            DecisionQueryV1.from_dict(payload)

        with self.assertRaisesRegex(ValueError, "safe integer"):
            replace(_usage_profile(), uncached_input_tokens=2**53)

        capability = _query(
            objective="capability_top_set",
            usage_profile=None,
            zero_cache_sensitivity_usage_profile=None,
            monthly_budget_microusd=None,
        )
        with self.assertRaisesRegex(ValueError, "monthly_budget_microusd"):
            replace(capability, monthly_budget_microusd=1)


class DecisionReceiptTests(unittest.TestCase):
    def test_cost_receipt_uses_projected_cost_vocabulary_only(self):
        selection = DecisionSelectionV1.from_dict({
            "evaluated_configuration_id": _evaluated_configuration().evaluated_configuration_id,
            "serving_offer_id": "offer_public-demo-us-west",
            "capability_rank": 1,
            "projected_monthly_cost_microusd": 41_100_000,
            "zero_cache_sensitivity_projected_monthly_cost_microusd": 44_000_000,
        })

        self.assertEqual(41_100_000, selection.projected_monthly_cost_microusd)
        legacy_cost_field = "estimated" + "_monthly_cost_microusd"
        legacy_sensitivity_field = (
            "zero_cache_sensitivity" + "_monthly_cost_microusd"
        )
        self.assertNotIn(legacy_cost_field, selection.to_dict())
        self.assertNotIn(
            legacy_sensitivity_field,
            selection.to_dict(),
        )

    def test_declared_zero_cache_sensitivity_must_also_fit_the_hard_budget(self):
        values = _receipt_kwargs()
        values["query"] = replace(values["query"], monthly_budget_microusd=42_000_000)
        values["reasons"] = tuple(
            replace(reason, threshold="42000000")
            if reason.code == "budget_fit_under_declared_profiles"
            else reason
            for reason in values["reasons"]
        )

        with self.assertRaisesRegex(ValueError, "zero-cache sensitivity.*budget"):
            DecisionReceiptV1.create(
                **values,
                outcome="top_set",
                selections=(_selection(),),
                abstention_reason=None,
            )

    def test_differing_estimated_cost_projections_require_an_explicit_caveat(self):
        values = _receipt_kwargs()
        cost_codes = {
            "lowest_cost_under_usage_profile",
            "budget_fit_under_declared_profiles",
        }
        values["reasons"] = tuple(
            replace(
                reason,
                caveat_codes=tuple(
                    code
                    for code in reason.caveat_codes
                    if code != "cost_sensitive_to_usage"
                ),
            )
            if reason.code in cost_codes
            else reason
            for reason in values["reasons"]
        )

        with self.assertRaisesRegex(ValueError, "cost_sensitive_to_usage"):
            DecisionReceiptV1.create(
                **values,
                outcome="top_set",
                selections=(_selection(),),
                abstention_reason=None,
            )

    def test_capability_receipt_still_discloses_differing_projected_costs(self):
        values = _receipt_kwargs()
        values["query"] = replace(
            values["query"],
            objective="capability_top_set",
            provider_ids=None,
            regions=None,
            minimum_context_tokens=None,
            monthly_budget_microusd=None,
        )
        capability_reason = next(
            reason
            for reason in values["reasons"]
            if reason.code == "within_capability_top_set"
        )
        values["reasons"] = (capability_reason,)
        values["sensitivity"] = tuple(
            row
            for row in values["sensitivity"]
            if row.scenario == "leave_one_family_out"
        )
        values["freshness"] = DecisionFreshnessV1(
            observed_at="2026-07-09T00:00:00Z",
            expires_at="2026-07-10T00:00:00Z",
        )

        with self.assertRaisesRegex(ValueError, "cost_sensitive_to_usage"):
            DecisionReceiptV1.create(
                **values,
                outcome="top_set",
                selections=(_selection(),),
                abstention_reason=None,
            )

        values["reasons"] = (
            replace(capability_reason, caveat_codes=("cost_sensitive_to_usage",)),
        )
        receipt = DecisionReceiptV1.create(
            **values,
            outcome="top_set",
            selections=(_selection(),),
            abstention_reason=None,
        )
        self.assertEqual(
            ("cost_sensitive_to_usage",),
            receipt.reasons[0].caveat_codes,
        )

    def test_cost_reasons_use_declared_profile_vocabulary(self):
        base = _receipt_kwargs()["reasons"][0]

        lowest = replace(base, code="lowest_cost_under_usage_profile")
        budget = replace(
            base,
            code="budget_fit_under_declared_profiles",
            predicate="lte",
            threshold="50000000",
        )

        self.assertEqual("lowest_cost_under_usage_profile", lowest.code)
        self.assertEqual("budget_fit_under_declared_profiles", budget.code)

    def test_estimated_cached_receipt_recomputes_zero_cache_sensitivity_cost(self):
        receipt = _receipt()

        self.assertEqual(
            44_000_000,
            receipt.selections[0].zero_cache_sensitivity_projected_monthly_cost_microusd,
        )
        with self.assertRaisesRegex(ValueError, "zero_cache_sensitivity"):
            DecisionReceiptV1.create(
                **_receipt_kwargs(),
                outcome="top_set",
                selections=(
                    replace(
                        _selection(),
                        zero_cache_sensitivity_projected_monthly_cost_microusd=43_000_000,
                    ),
                ),
                abstention_reason=None,
            )

    def test_receipt_fails_closed_when_pricing_omits_a_nonzero_usage_rate(self):
        values = _receipt_kwargs()
        values["evidence"] = tuple(
            replace(
                row,
                serving_offer=replace(
                    row.serving_offer,
                    pricing=replace(
                        row.serving_offer.pricing,
                        cached_read_microusd_per_million_tokens=None,
                    ),
                ),
            )
            if isinstance(row, ServingOfferEvidenceV1)
            else row
            for row in values["evidence"]
        )

        with self.assertRaisesRegex(ValueError, "pricing.*nonzero usage"):
            DecisionReceiptV1.create(
                **values,
                outcome="top_set",
                selections=(_selection(),),
                abstention_reason=None,
            )

    def test_receipt_id_hashes_full_body_except_receipt_id(self):
        receipt = _receipt()
        body = receipt.to_body_dict()

        self.assertEqual(f"receipt_{sha256_hex(body)}", receipt.receipt_id)
        self.assertEqual(receipt, DecisionReceiptV1.from_dict(receipt.to_dict()))

        changed = receipt.to_dict()
        changed["methodology_version"] = "2026-07-09.2.changed"
        with self.assertRaisesRegex(ValueError, "receipt_id"):
            DecisionReceiptV1.from_dict(changed)

    def test_decided_at_pins_offer_and_link_eligibility(self):
        values = _receipt_kwargs()
        values["decided_at"] = "2026-07-10T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "decided_at"):
            DecisionReceiptV1.create(
                **values,
                outcome="top_set",
                selections=(_selection(),),
                abstention_reason=None,
            )

    def test_cost_receipt_recomputes_cost_and_requires_typed_capability_offer_and_link_evidence(self):
        values = _receipt_kwargs()
        with self.assertRaisesRegex(ValueError, "computed monthly cost"):
            DecisionReceiptV1.create(
                **values,
                outcome="top_set",
                selections=(replace(_selection(), projected_monthly_cost_microusd=43_000_000),),
                abstention_reason=None,
            )

        without_link = {
            **values,
            "evidence": tuple(
                row for row in values["evidence"]
                if not isinstance(row, EvaluationToOfferLinkEvidenceV1)
            ),
        }
        with self.assertRaisesRegex(ValueError, "offer-link evidence|cited evidence_id"):
            DecisionReceiptV1.create(
                **without_link,
                outcome="top_set",
                selections=(_selection(),),
                abstention_reason=None,
            )

    def test_receipt_sorts_set_like_evidence_and_rejects_duplicates(self):
        receipt = _receipt()

        self.assertEqual(
            ["evidence-link", "evidence-offer"],
            receipt.reasons[0].to_dict()["evidence_ids"],
        )
        with self.assertRaisesRegex(ValueError, "evidence_ids must be unique"):
            replace(receipt.reasons[0], evidence_ids=("evidence-link", "evidence-link"))

    def test_receipt_outcome_and_abstention_are_consistent(self):
        with self.assertRaisesRegex(ValueError, "top_set"):
            DecisionReceiptV1.create(
                **_receipt_kwargs(),
                outcome="top_set",
                selections=(),
                abstention_reason=None,
            )

    def test_cost_objective_requires_verified_offer_cost_within_budget(self):
        values = _receipt_kwargs()
        evaluated_id = _evaluated_configuration().evaluated_configuration_id
        valid = DecisionSelectionV1(
            evaluated_configuration_id=evaluated_id,
            serving_offer_id="offer_public-demo-us-west",
            capability_rank=1,
            projected_monthly_cost_microusd=41_100_000,
            zero_cache_sensitivity_projected_monthly_cost_microusd=44_000_000,
        )

        for selection, message in (
            (replace(valid, projected_monthly_cost_microusd=None), "projected_monthly_cost_microusd"),
            (replace(valid, projected_monthly_cost_microusd=50_000_001), "monthly_budget_microusd"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    DecisionReceiptV1.create(
                        **values,
                        outcome="top_set",
                        selections=(selection,),
                        abstention_reason=None,
                    )

        with self.assertRaisesRegex(ValueError, "serving_offer_id"):
            DecisionSelectionV1(
                evaluated_configuration_id=evaluated_id,
                serving_offer_id=None,
                capability_rank=1,
                projected_monthly_cost_microusd=1,
                zero_cache_sensitivity_projected_monthly_cost_microusd=1,
            )

        higher_cost = DecisionSelectionV1(
            evaluated_configuration_id="config_" + HASH_B,
            serving_offer_id="offer_public-demo-two",
            capability_rank=2,
            projected_monthly_cost_microusd=45_000_000,
            zero_cache_sensitivity_projected_monthly_cost_microusd=48_000_000,
        )
        with self.assertRaisesRegex(ValueError, "equal minimum cost"):
            DecisionReceiptV1.create(
                **values,
                outcome="top_set",
                selections=(valid, higher_cost),
                abstention_reason=None,
            )

        with self.assertRaisesRegex(ValueError, "selections must be unique"):
            DecisionReceiptV1.create(
                **values,
                outcome="top_set",
                selections=(valid, replace(valid, serving_offer_id="offer_public-demo-two")),
                abstention_reason=None,
            )

    def test_structured_provider_and_region_reasons_use_matching_axes_and_units(self):
        base = _receipt_kwargs()["reasons"][0]
        provider = replace(
            base,
            code="provider_constraint_match",
            predicate="eq",
            axis="provider",
            observed_value="provider-public",
            unit="provider_id",
            threshold="provider-public",
        )
        region = replace(
            base,
            code="region_constraint_match",
            predicate="eq",
            axis="region",
            observed_value="us-west",
            unit="region_id",
            threshold="us-west",
        )

        self.assertEqual("provider", provider.axis)
        self.assertEqual("region", region.axis)
        with self.assertRaisesRegex(ValueError, "provider_constraint_match"):
            replace(
                provider,
                axis="monthly_cost",
                unit="microusd_per_month",
                observed_value="1",
                threshold="1",
            )

    def test_single_selection_requires_stable_leave_one_family_out(self):
        values = _receipt_kwargs()
        evaluated_id = _evaluated_configuration().evaluated_configuration_id
        selection = DecisionSelectionV1(
            evaluated_configuration_id=evaluated_id,
            serving_offer_id="offer_public-demo-us-west",
            capability_rank=1,
            projected_monthly_cost_microusd=41_100_000,
            zero_cache_sensitivity_projected_monthly_cost_microusd=44_000_000,
        )
        values["sensitivity"] = ()

        with self.assertRaisesRegex(ValueError, "leave_one_family_out"):
            DecisionReceiptV1.create(
                **values,
                outcome="top_set",
                selections=(selection,),
                abstention_reason=None,
            )

    def test_every_top_set_requires_stable_leave_one_family_out_and_cost_scenarios(self):
        values = _receipt_kwargs()
        for scenario in (
            "leave_one_family_out",
            "price_plus_20_percent",
            "price_minus_20_percent",
            "usage_double",
        ):
            invalid = {
                **values,
                "sensitivity": tuple(row for row in values["sensitivity"] if row.scenario != scenario),
            }
            with self.subTest(scenario=scenario):
                with self.assertRaisesRegex(ValueError, scenario):
                    DecisionReceiptV1.create(
                        **invalid,
                        outcome="top_set",
                        selections=(_selection(),),
                        abstention_reason=None,
                    )
        with self.assertRaisesRegex(ValueError, "abstention_reason"):
            DecisionReceiptV1.create(
                **_receipt_kwargs(),
                outcome="abstain",
                selections=(),
                abstention_reason=None,
            )

    def test_golden_receipt_and_query_decode_and_rehash(self):
        corpus = json.loads(GOLDEN.read_text(encoding="utf-8"))

        query = DecisionQueryV1.from_dict(corpus["query"]["input"])
        receipt = DecisionReceiptV1.from_dict({
            **corpus["receipt"]["body"],
            "receipt_id": corpus["receipt"]["receipt_id"],
        })

        self.assertEqual(corpus["query"]["canonical"], query.canonical_json())
        self.assertEqual(corpus["receipt"]["receipt_id"], receipt.receipt_id)
        null_filter = next(
            row["value"]
            for row in corpus["rejection_vectors"]
            if row["name"] == "null_provider_filter"
        )
        with self.assertRaisesRegex(ValueError, "must not be null"):
            DecisionQueryV1.from_dict(null_filter)

    def test_examples_resolve_against_the_canonical_manifest(self):
        cells = {row["cell_id"] for row in MANIFEST["cells"]}
        groups = {row["ranking_group_id"] for row in MANIFEST["ranking_groups"]}
        families = {row["benchmark_family_id"] for row in MANIFEST["benchmark_families"]}
        feeds = {(row["feed_id"], row["benchmark_family_id"]) for row in MANIFEST["feeds"]}

        query = _query()
        provenance = _provenance()
        self.assertIn(query.cell_id, cells)
        self.assertIn(query.ranking_group_id, groups)
        self.assertIn(provenance.benchmark_family_id, families)
        self.assertIn((provenance.feed_id, provenance.benchmark_family_id), feeds)

    def test_top_set_requires_explanation_and_evidence(self):
        values = _receipt_kwargs()
        evaluated_id = _evaluated_configuration().evaluated_configuration_id
        selection = DecisionSelectionV1(
            evaluated_configuration_id=evaluated_id,
            serving_offer_id="offer_public-demo-us-west",
            capability_rank=1,
            projected_monthly_cost_microusd=41_100_000,
            zero_cache_sensitivity_projected_monthly_cost_microusd=44_000_000,
        )
        for field in ("reasons", "evidence"):
            invalid = {**values, field: ()}
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    DecisionReceiptV1.create(
                        **invalid,
                        outcome="top_set",
                        selections=(selection,),
                        abstention_reason=None,
                    )

    def test_sensitivity_stability_matches_the_selected_set(self):
        values = _receipt_kwargs()
        evaluated_id = _evaluated_configuration().evaluated_configuration_id
        selection = DecisionSelectionV1(
            evaluated_configuration_id=evaluated_id,
            serving_offer_id="offer_public-demo-us-west",
            capability_rank=1,
            projected_monthly_cost_microusd=41_100_000,
            zero_cache_sensitivity_projected_monthly_cost_microusd=44_000_000,
        )
        stable = next(row for row in values["sensitivity"] if row.scenario == "leave_one_family_out")
        unrelated = replace(
            next(row for row in values["sensitivity"] if row.scenario == "usage_double"),
            selected_configuration_ids=("config_" + "c" * 64,),
        )
        for row in (
            replace(stable, selected_configuration_ids=("config_" + HASH_B,)),
            replace(stable, stable=False),
            unrelated,
        ):
            invalid = {
                **values,
                "sensitivity": tuple(
                    row if current.scenario == row.scenario else current
                    for current in values["sensitivity"]
                ),
            }
            with self.subTest(row=row):
                with self.assertRaisesRegex(ValueError, "sensitivity"):
                    DecisionReceiptV1.create(
                        **invalid,
                        outcome="top_set",
                        selections=(selection,),
                        abstention_reason=None,
                    )

    def test_all_nine_wire_schemas_are_closed_and_uniquely_identified(self):
        names = (
            "source-artifact.schema.json",
            "run-provenance.schema.json",
            "observation.schema.json",
            "configuration-passport.schema.json",
            "evaluated-configuration.schema.json",
            "serving-offer.schema.json",
            "evaluation-to-offer-link.schema.json",
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

    def test_wire_schemas_publish_only_monthly_schedule_pricing(self):
        offer = json.loads((SCHEMAS / "serving-offer.schema.json").read_text(encoding="utf-8"))
        query = json.loads((SCHEMAS / "decision-query.schema.json").read_text(encoding="utf-8"))
        link = json.loads((SCHEMAS / "evaluation-to-offer-link.schema.json").read_text(encoding="utf-8"))
        receipt = json.loads((SCHEMAS / "decision-receipt.schema.json").read_text(encoding="utf-8"))

        self.assertEqual("#/$defs/PricingScheduleFact", offer["properties"]["pricing"]["$ref"])
        self.assertNotIn("PricingFact", offer["$defs"])
        self.assertIn("UsageProfile", query["$defs"])
        self.assertNotIn("input_tokens_per_request", query["properties"])
        self.assertIn("evidence_basis", link["required"])
        self.assertIn(
            "zero_cache_sensitivity_projected_monthly_cost_microusd",
            receipt["$defs"]["Selection"]["required"],
        )
        selection_fields = receipt["$defs"]["Selection"]["properties"]
        self.assertIn("projected_monthly_cost_microusd", selection_fields)
        self.assertNotIn("estimated" + "_monthly_cost_microusd", selection_fields)
        reason_codes = receipt["$defs"]["Reason"]["properties"]["code"]["enum"]
        self.assertIn("lowest_cost_under_usage_profile", reason_codes)
        self.assertIn("budget_fit_under_declared_profiles", reason_codes)
        self.assertNotIn("lowest_" + "verified_cost", reason_codes)
        self.assertNotIn("budget_" + "constraint_met", reason_codes)


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


def _offer_link() -> EvaluationToOfferLinkV1:
    return EvaluationToOfferLinkV1(
        evaluation_to_offer_link_id="link_public-demo-us-west",
        evaluated_configuration_id=_evaluated_configuration().evaluated_configuration_id,
        serving_offer_id="offer_public-demo-us-west",
        compatibility="exact",
        evidence_basis="benchmark_exact",
        evidence_source_artifact_id=ARTIFACT_A,
        observed_at="2026-07-09T00:00:00Z",
        expires_at="2026-07-10T00:00:00Z",
        review_state="approved",
    )


def _query(**overrides) -> DecisionQueryV1:
    values = {
        "cell_id": "coding-general",
        "ranking_group_id": "rg-coding-general-model-configuration-direct-prompt-model-configuration-v1",
        "entity_kind": "model_configuration",
        "interaction_policy": "direct_prompt",
        "configuration_passport_class": "model-configuration-v1",
        "objective": "lowest_cost_within_top_set",
        "provider_ids": ("provider-public",),
        "regions": ("us-west",),
        "minimum_context_tokens": 32_000,
        "usage_profile": _usage_profile(),
        "zero_cache_sensitivity_usage_profile": _zero_cache_sensitivity(_usage_profile()),
        "monthly_budget_microusd": 50_000_000,
    }
    values.update(overrides)
    return DecisionQueryV1(**values)


def _usage_profile() -> decision_contracts.UsageProfileV1:
    return decision_contracts.UsageProfileV1(
        basis="estimated",
        uncached_input_tokens=10_000_000,
        cached_read_tokens=5_000_000,
        output_tokens=5_000_000,
        cache_writes=(
            decision_contracts.CacheWriteUsageV1(ttl_seconds=300, tokens=5_000_000),
        ),
        cache_storage_token_seconds=3_600_000_000,
    )


def _zero_cache_sensitivity(
    usage: decision_contracts.UsageProfileV1,
) -> decision_contracts.UsageProfileV1:
    return decision_contracts.UsageProfileV1(
        basis="estimated",
        uncached_input_tokens=usage.total_input_tokens,
        cached_read_tokens=0,
        output_tokens=usage.output_tokens,
        cache_writes=(),
        cache_storage_token_seconds=0,
    )


def _receipt_kwargs() -> dict:
    evaluated_id = _evaluated_configuration().evaluated_configuration_id
    excluded_observation = ObservationV1(
        observation_id="obs_public_demo_excluded",
        evaluated_configuration_id="config_" + HASH_B,
        metric=ProportionMetricV1(value="0.5", numerator=1, denominator=2),
        uncertainty=UnknownUncertaintyV1(),
        provenance=_provenance(),
    )
    return {
        "query": _query(),
        "publication_snapshot": PublicationSnapshotRefV1(
            publication_snapshot_id="snapshot_" + HASH_B,
            ranking_group_id="rg-coding-general-model-configuration-direct-prompt-model-configuration-v1",
            manifest_version="2026-07-09.2",
            published_at="2026-07-09T00:00:00Z",
        ),
        "methodology_version": "2026-07-09.2.public-decision-v1",
        "decided_at": "2026-07-09T12:00:00Z",
        "exclusions": (
            DecisionExclusionV1(
                evaluated_configuration_id="config_" + HASH_B,
                code="constraints_not_met",
                evidence_ids=("evidence-excluded",),
            ),
        ),
        "reasons": (
            DecisionReasonV1(
                reason_type="best_when",
                code="lowest_cost_under_usage_profile",
                subject_id="offer_public-demo-us-west",
                predicate="eq",
                axis="monthly_cost",
                observed_value="41100000",
                unit="microusd_per_month",
                threshold="41100000",
                evidence_ids=("evidence-link", "evidence-offer"),
                freshness=DecisionFreshnessV1(
                    observed_at="2026-07-09T01:00:00Z",
                    expires_at="2026-07-10T00:00:00Z",
                ),
                caveat_codes=(
                    "cost_sensitive_to_usage",
                    "provider_offer_link_required",
                ),
            ),
            DecisionReasonV1(
                reason_type="best_when",
                code="budget_fit_under_declared_profiles",
                subject_id="offer_public-demo-us-west",
                predicate="lte",
                axis="monthly_cost",
                observed_value="44000000",
                unit="microusd_per_month",
                threshold="50000000",
                evidence_ids=("evidence-link", "evidence-offer"),
                freshness=DecisionFreshnessV1(
                    observed_at="2026-07-09T01:00:00Z",
                    expires_at="2026-07-10T00:00:00Z",
                ),
                caveat_codes=(
                    "cost_sensitive_to_usage",
                    "provider_offer_link_required",
                ),
            ),
            DecisionReasonV1(
                reason_type="best_when",
                code="provider_constraint_match",
                subject_id="offer_public-demo-us-west",
                predicate="eq",
                axis="provider",
                observed_value="provider-public",
                unit="provider_id",
                threshold="provider-public",
                evidence_ids=("evidence-link", "evidence-offer"),
                freshness=DecisionFreshnessV1(
                    observed_at="2026-07-09T01:00:00Z",
                    expires_at="2026-07-10T00:00:00Z",
                ),
                caveat_codes=("provider_offer_link_required",),
            ),
            DecisionReasonV1(
                reason_type="best_when",
                code="region_constraint_match",
                subject_id="offer_public-demo-us-west",
                predicate="eq",
                axis="region",
                observed_value="us-west",
                unit="region_id",
                threshold="us-west",
                evidence_ids=("evidence-link", "evidence-offer"),
                freshness=DecisionFreshnessV1(
                    observed_at="2026-07-09T01:00:00Z",
                    expires_at="2026-07-10T00:00:00Z",
                ),
                caveat_codes=("provider_offer_link_required",),
            ),
            DecisionReasonV1(
                reason_type="best_when",
                code="context_requirement_met",
                subject_id="offer_public-demo-us-west",
                predicate="gte",
                axis="context",
                observed_value="128000",
                unit="tokens",
                threshold="32000",
                evidence_ids=("evidence-link", "evidence-offer"),
                freshness=DecisionFreshnessV1(
                    observed_at="2026-07-09T01:00:00Z",
                    expires_at="2026-07-10T00:00:00Z",
                ),
                caveat_codes=("provider_offer_link_required",),
            ),
            DecisionReasonV1(
                reason_type="best_when",
                code="within_capability_top_set",
                subject_id=evaluated_id,
                predicate="within_top_set",
                axis="capability",
                observed_value="0.75",
                unit="score",
                threshold=None,
                evidence_ids=("evidence-observation",),
                freshness=DecisionFreshnessV1(
                    observed_at="2026-07-09T00:00:00Z",
                    expires_at="2026-07-10T00:00:00Z",
                ),
                caveat_codes=(),
            ),
        ),
        "sensitivity": (
            DecisionSensitivityV1(
                scenario="leave_one_family_out",
                stable=True,
                selected_configuration_ids=(evaluated_id,),
            ),
            DecisionSensitivityV1(
                scenario="price_minus_20_percent",
                stable=True,
                selected_configuration_ids=(evaluated_id,),
            ),
            DecisionSensitivityV1(
                scenario="price_plus_20_percent",
                stable=False,
                selected_configuration_ids=(),
            ),
            DecisionSensitivityV1(
                scenario="usage_double",
                stable=False,
                selected_configuration_ids=(),
            ),
        ),
        "evidence": (
            ObservationEvidenceV1(
                evidence_id="evidence-observation",
                observation=_observation(),
            ),
            ObservationEvidenceV1(
                evidence_id="evidence-excluded",
                observation=excluded_observation,
            ),
            ServingOfferEvidenceV1(
                evidence_id="evidence-offer",
                serving_offer=_serving_offer(),
            ),
            EvaluationToOfferLinkEvidenceV1(
                evidence_id="evidence-link",
                evaluation_to_offer_link=_offer_link(),
            ),
        ),
        "freshness": DecisionFreshnessV1(
            observed_at="2026-07-09T01:00:00Z",
            expires_at="2026-07-10T00:00:00Z",
        ),
    }


def _receipt() -> DecisionReceiptV1:
    return DecisionReceiptV1.create(
        **_receipt_kwargs(),
        outcome="top_set",
        selections=(_selection(),),
        abstention_reason=None,
    )


def _selection() -> DecisionSelectionV1:
    return DecisionSelectionV1(
        evaluated_configuration_id=_evaluated_configuration().evaluated_configuration_id,
        serving_offer_id="offer_public-demo-us-west",
        capability_rank=1,
        projected_monthly_cost_microusd=41_100_000,
        zero_cache_sensitivity_projected_monthly_cost_microusd=44_000_000,
    )


if __name__ == "__main__":
    unittest.main()
