import json
import sys
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "packages" / "core" / "src"
SDK_SRC = REPO_ROOT / "packages" / "sdk-python" / "src"
sys.path.insert(0, str(CORE_SRC))
sys.path.insert(0, str(SDK_SRC))

from evalrank_core import contracts as core_contracts  # noqa: E402
from evalrank_core.contracts import CapabilityFingerprintInput as CoreCapabilityFingerprintInput  # noqa: E402
from evalrank_core.contracts import ProblemDetails as CoreProblemDetails  # noqa: E402
from evalrank_core.contracts import RawEntry as CoreRawEntry  # noqa: E402
from evalrank_core.decision_contracts import ObservationV1 as CoreObservationV1  # noqa: E402
from evalrank_core.contracts import UseCaseCatalog as CoreUseCaseCatalog  # noqa: E402
from evalrank_core.fixtures import PUBLIC_FIXTURE_KINDS as CorePublicFixtureKinds  # noqa: E402
from evalrank_core.fixtures import sample_public_fixture as core_sample_public_fixture  # noqa: E402
from evalrank_core.fixtures import sample_problem_details as core_sample_problem_details  # noqa: E402
from evalrank_sdk import (  # noqa: E402
    CapabilityFingerprintInput,
    DecisionQueryV1,
    DecisionReceiptV1,
    EvalRankApiError,
    EvalRankClient,
    ObservationV1,
    ProblemDetails,
    RawEntry,
    UseCaseCatalog,
    PUBLIC_FIXTURE_KINDS,
    sample_capability_fingerprint_input,
    sample_observation,
    sample_public_fixture,
    sample_problem_details,
    sample_raw_entry,
    sample_use_case_catalog,
    restricted_jcs,
)

def _manifest_use_cases() -> list[dict]:
    cells = json.loads((REPO_ROOT / "catalog" / "manifest.json").read_text(encoding="utf-8"))["cells"]
    return [
        {
            "object": "use_case",
            "id": cell["cell_id"],
            "name": cell["name"],
            "definition": cell["definition"],
            "entity_kinds": cell["entity_kinds"],
            "rank_policy": "ranked",
            "is_overlay": False,
        }
        for cell in cells
    ]


def _decision_vector() -> tuple[DecisionQueryV1, dict]:
    corpus = json.loads(
        (REPO_ROOT / "examples" / "decision-contract-v1.golden.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = {
        **corpus["receipt"]["body"],
        "receipt_id": corpus["receipt"]["receipt_id"],
    }
    DecisionReceiptV1.from_dict(receipt)
    return DecisionQueryV1.from_dict(receipt["query"]), receipt


class PythonSdkTests(unittest.TestCase):
    def test_sdk_re_exports_monthly_schedule_pricing_contracts(self):
        import evalrank_core  # noqa: PLC0415
        import evalrank_sdk  # noqa: PLC0415

        for name in (
            "CacheWriteRateV1",
            "CacheWriteUsageV1",
            "PricingScheduleFactV1",
            "UsageProfileV1",
            "monthly_cost_microusd",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(evalrank_core, name))
                self.assertIs(getattr(evalrank_sdk, name), getattr(evalrank_core, name))
        self.assertFalse(hasattr(evalrank_core, "PricingFactV1"))
        self.assertFalse(hasattr(evalrank_sdk, "PricingFactV1"))

    def test_sdk_re_exports_aggregation_identity_contract(self):
        import evalrank_core  # noqa: PLC0415
        import evalrank_sdk  # noqa: PLC0415

        for name in (
            "aggregation_input_document",
            "bootstrap_seed_document",
            "derive_aggregation_input_digest",
            "derive_bootstrap_seed",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(evalrank_core, name))
                self.assertIs(getattr(evalrank_sdk, name), getattr(evalrank_core, name))

    def test_sdk_readme_lists_public_reexport_surface(self):
        text = (REPO_ROOT / "packages" / "sdk-python" / "README.md").read_text(encoding="utf-8")

        for name in (
            "CapabilityFingerprintInput",
            "RawEntry",
            "ObservationV1",
            "UseCaseCatalog",
            "DecisionQueryV1",
            "DecisionReceiptV1",
            "ProblemDetails",
            "PROBLEM_CODES",
            "EvalRankClient",
            "EvalRankApiError",
            "PUBLIC_FIXTURE_KINDS",
            "sample_public_fixture",
            "aggregation_input_document",
            "bootstrap_seed_document",
            "derive_aggregation_input_digest",
            "derive_bootstrap_seed",
        ):
            self.assertIn(name, text)

    def test_sdk_re_exports_public_fixture_dispatch(self):
        self.assertIs(PUBLIC_FIXTURE_KINDS, CorePublicFixtureKinds)
        self.assertIs(sample_public_fixture, core_sample_public_fixture)
        self.assertNotIn("recommendation", PUBLIC_FIXTURE_KINDS)
        self.assertNotIn("request", PUBLIC_FIXTURE_KINDS)
        self.assertNotIn("scoring-stages", PUBLIC_FIXTURE_KINDS)

    def test_sdk_does_not_reexport_superseded_recommendation_pipeline(self):
        import evalrank_sdk  # noqa: PLC0415

        for name in (
            "Abstention",
            "CandidateSet",
            "COMPARABILITY_MODES",
            "EntityRef",
            "EvaluationRequest",
            "EvidenceItem",
            "EvidenceSet",
            "Exclusion",
            "RankedEntity",
            "RankingGroup",
            "Recommendation",
            "ScoringStage",
            "ScoringStageCatalog",
            "StageCandidate",
            "THE_CALL_DECISIONS",
            "TheCall",
            "materialize_recommendation",
        ):
            self.assertFalse(hasattr(evalrank_sdk, name), name)

    def test_sdk_re_exports_public_problem_fixture(self):
        self.assertIs(sample_problem_details, core_sample_problem_details)
        self.assertEqual("validation", sample_problem_details().to_dict()["code"])

    def test_sdk_re_exports_public_vocabulary_constants(self):
        import evalrank_sdk  # noqa: PLC0415

        for name in ("PROBLEM_CODES",):
            with self.subTest(name=name):
                self.assertIs(getattr(evalrank_sdk, name), getattr(core_contracts, name))

    def test_sdk_re_exports_core_capability_fingerprint_contracts(self):
        fingerprint_input = sample_capability_fingerprint_input()

        self.assertIs(CapabilityFingerprintInput, CoreCapabilityFingerprintInput)
        self.assertIsInstance(fingerprint_input, CoreCapabilityFingerprintInput)
        self.assertEqual(64, len(fingerprint_input.to_dict()["capability_fingerprint"]))

    def test_sdk_re_exports_core_problem_details_contract(self):
        problem = ProblemDetails(
            type="about:blank",
            title="Validation failed",
            status=422,
            detail="request_id is required",
            code="validation",
        )

        self.assertIs(ProblemDetails, CoreProblemDetails)
        self.assertEqual("validation", problem.to_dict()["code"])

    def test_sdk_re_exports_core_raw_entry_contracts(self):
        entry = sample_raw_entry()

        self.assertIs(RawEntry, CoreRawEntry)
        self.assertIsInstance(entry, CoreRawEntry)
        self.assertEqual("raw_entry", entry.to_dict()["object"])

    def test_sdk_re_exports_typed_observation_contract(self):
        observation = sample_observation()

        self.assertIs(ObservationV1, CoreObservationV1)
        self.assertIsInstance(observation, CoreObservationV1)
        self.assertEqual("observation", observation.to_dict()["object"])

    def test_sdk_re_exports_core_use_case_catalog_contracts(self):
        catalog = sample_use_case_catalog()

        self.assertIs(UseCaseCatalog, CoreUseCaseCatalog)
        self.assertIsInstance(catalog, CoreUseCaseCatalog)
        self.assertEqual("use_case_catalog", catalog.to_dict()["object"])
        self.assertEqual(24, len(catalog.to_dict()["use_cases"]))
        self.assertEqual(
            "writing",
            catalog.to_dict()["use_cases"][-1]["id"],
        )
        self.assertTrue(all(row["rank_policy"] == "ranked" for row in catalog.to_dict()["use_cases"]))
        self.assertEqual(_manifest_use_cases(), catalog.to_dict()["use_cases"])

    def test_decide_posts_canonical_query_and_returns_validated_receipt(self):
        query, receipt = _decision_vector()
        server = _SdkTestServer(response_status=200, response_body=receipt)
        try:
            response = EvalRankClient(server.base_url).decide(query, share=True)
        finally:
            server.close()

        self.assertEqual(receipt, response)
        self.assertEqual("/v1/decisions?share=true", server.path)
        self.assertEqual("application/json", server.headers["Content-Type"])
        self.assertEqual("application/json, application/problem+json", server.headers["Accept"])
        self.assertEqual(query.to_dict(), server.request_json)
        self.assertEqual(restricted_jcs(query.to_dict()), server.request_body)

    def test_decide_raises_public_problem_details_error(self):
        query, _ = _decision_vector()
        problem = {**core_sample_problem_details().to_dict(), "status": 429}
        server = _SdkTestServer(
            response_status=429,
            response_body=problem,
            response_headers={"Content-Type": "application/problem+json", "Retry-After": "3"},
        )
        try:
            with self.assertRaises(EvalRankApiError) as raised:
                EvalRankClient(server.base_url).decide(query)
        finally:
            server.close()

        self.assertEqual(429, raised.exception.status)
        self.assertIsInstance(raised.exception.problem, CoreProblemDetails)
        self.assertEqual(problem, raised.exception.problem.to_dict())
        self.assertEqual(3, raised.exception.retry_after)

    def test_decide_treats_malformed_retry_after_as_absent(self):
        query, _ = _decision_vector()
        problem = {**core_sample_problem_details().to_dict(), "status": 429}
        server = _SdkTestServer(
            response_status=429,
            response_body=problem,
            response_headers={"Content-Type": "application/problem+json", "Retry-After": "3 seconds"},
        )
        try:
            with self.assertRaises(EvalRankApiError) as raised:
                EvalRankClient(server.base_url).decide(query)
        finally:
            server.close()

        self.assertEqual(429, raised.exception.status)
        self.assertEqual(problem, raised.exception.problem.to_dict())
        self.assertIsNone(raised.exception.retry_after)

    def test_use_cases_gets_public_catalog_json(self):
        server = _SdkTestServer(response_status=200, response_body=sample_use_case_catalog().to_dict())
        try:
            response = EvalRankClient(server.base_url).use_cases()
        finally:
            server.close()

        self.assertEqual("use_case_catalog", response["object"])
        self.assertEqual("/v1/use-cases", server.path)
        self.assertEqual("application/json, application/problem+json", server.headers["Accept"])
        self.assertIsNone(server.request_json)

    def test_use_cases_rejects_malformed_catalog_responses(self):
        malformed = sample_use_case_catalog().to_dict()
        malformed["use_cases"][0]["entity_kinds"] = ["private_kind"]
        server = _SdkTestServer(response_status=200, response_body=malformed)
        try:
            with self.assertRaisesRegex(ValueError, "entity_kinds"):
                EvalRankClient(server.base_url).use_cases()
        finally:
            server.close()

    def test_client_uses_a_bounded_timeout_by_default(self):
        self.assertEqual(30.0, EvalRankClient("https://evalrank.example").timeout)
        with self.assertRaisesRegex(ValueError, "timeout"):
            EvalRankClient("https://evalrank.example", timeout=0)

    def test_benchmark_health_gets_public_health_json(self):
        health = {
            "object": "benchmark_health",
            "schema_version": "1",
            "manifest_version": "2026-07-09.3",
            "generated_at": "2026-07-09T00:00:00Z",
            "cells": [
                {
                    "cell_id": "code-generation",
                    "status": "unavailable",
                    "ranking_group_count": 1,
                    "published_ranking_group_count": 0,
                    "benchmark_family_count": 1,
                    "candidate_feed_count": 1,
                    "implemented_feed_count": 0,
                    "admitted_feed_count": 0,
                    "rank_eligible_feed_count": 0,
                }
            ],
        }
        server = _SdkTestServer(response_status=200, response_body=health)
        try:
            response = EvalRankClient(server.base_url).benchmark_health()
        finally:
            server.close()

        self.assertEqual("benchmark_health", response["object"])
        self.assertEqual("/v1/benchmark-health", server.path)
        self.assertEqual("application/json, application/problem+json", server.headers["Accept"])
        self.assertIsNone(server.request_json)

    def test_decision_receipt_get_validates_id_and_response(self):
        _, receipt = _decision_vector()
        server = _SdkTestServer(response_status=200, response_body=receipt)
        try:
            response = EvalRankClient(server.base_url).decision_receipt(receipt["receipt_id"])
        finally:
            server.close()

        self.assertEqual(receipt, response)
        self.assertEqual(f"/v1/decisions/{receipt['receipt_id']}", server.path)
        with self.assertRaisesRegex(ValueError, "receipt_id"):
            EvalRankClient("https://evalrank.example").decision_receipt("bad")

    def test_client_has_no_legacy_route_methods(self):
        client = EvalRankClient("https://evalrank.example")
        self.assertFalse(hasattr(client, "recommend"))
        self.assertFalse(hasattr(client, "scoring_stages"))

    def test_metadata_route_raises_public_problem_details_error(self):
        problem = {**core_sample_problem_details().to_dict(), "status": 503}
        server = _SdkTestServer(
            response_status=503,
            response_body=problem,
            response_headers={"Content-Type": "application/problem+json", "Retry-After": "5"},
        )
        try:
            with self.assertRaises(EvalRankApiError) as raised:
                EvalRankClient(server.base_url).use_cases()
        finally:
            server.close()

        self.assertEqual(503, raised.exception.status)
        self.assertEqual(problem, raised.exception.problem.to_dict())
        self.assertEqual(5, raised.exception.retry_after)

    def test_client_preserves_unknown_problem_extensions_and_rejects_malformed_known_fields(self):
        problem = {
            **core_sample_problem_details().to_dict(),
            "status": 429,
            "provider_window": {"limit": 100, "seconds": 60},
        }
        server = _SdkTestServer(response_status=429, response_body=problem)
        try:
            with self.assertRaises(EvalRankApiError) as raised:
                EvalRankClient(server.base_url).use_cases()
        finally:
            server.close()
        self.assertEqual(problem, raised.exception.problem.to_dict())

        mismatched = {**problem, "status": 503}
        server = _SdkTestServer(response_status=429, response_body=mismatched)
        try:
            with self.assertRaisesRegex(ValueError, "status does not match"):
                EvalRankClient(server.base_url).use_cases()
        finally:
            server.close()

        malformed = {**problem, "status": "429"}
        server = _SdkTestServer(response_status=429, response_body=malformed)
        try:
            with self.assertRaisesRegex(ValueError, "Problem Details"):
                EvalRankClient(server.base_url).use_cases()
        finally:
            server.close()

    def test_client_rejects_non_http_base_url(self):
        with self.assertRaisesRegex(ValueError, "base_url must be an http or https URL"):
            EvalRankClient("file:///tmp/evalrank")


class _SdkTestServer:
    def __init__(
        self,
        *,
        response_status: int,
        response_body: dict,
        response_headers: dict[str, str] | None = None,
    ) -> None:
        self.request_json: dict | None = None
        self.request_body: bytes | None = None
        self.headers: dict[str, str] = {}
        self.path = ""

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                owner.path = self.path
                owner.headers = {key: self.headers[key] for key in self.headers}
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                owner.request_body = body
                owner.request_json = json.loads(body.decode("utf-8"))
                self._write_json()

            def do_GET(self) -> None:
                owner.path = self.path
                owner.headers = {key: self.headers[key] for key in self.headers}
                owner.request_json = None
                owner.request_body = None
                self._write_json()

            def _write_json(self) -> None:
                encoded = json.dumps(response_body).encode("utf-8")
                self.send_response(response_status)
                for key, value in (response_headers or {"Content-Type": "application/json"}).items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format: str, *args: object) -> None:
                return

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._server.server_address
        self.base_url = f"http://{host}:{port}"

    def close(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._server.server_close()


if __name__ == "__main__":
    unittest.main()
