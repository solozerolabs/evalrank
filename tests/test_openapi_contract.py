import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = REPO_ROOT / "schemas"
OPENAPI = SCHEMAS / "openapi.json"


class OpenApiContractTests(unittest.TestCase):
    def test_launch_route_map_is_exact_and_contains_no_legacy_operations(self):
        spec = _openapi()

        self.assertEqual("3.1.1", spec["openapi"])
        self.assertEqual(
            {
                "/v1/use-cases",
                "/v1/leaderboard/{use_case}",
                "/v1/entities/{entity_type}/{slug}",
                "/v1/compare",
                "/v1/benchmark-health",
                "/v1/decisions",
                "/v1/decisions/{receipt_id}",
            },
            set(spec["paths"]),
        )
        serialized = json.dumps(spec)
        for legacy in (
            "/v1/recommendations",
            "/v1/scoring-stages",
            "recommendation_not_published",
            "invalid_evaluation_request",
        ):
            self.assertNotIn(legacy, serialized)

    def test_decision_create_contract_is_closed_and_share_is_transport_only(self):
        operation = _openapi()["paths"]["/v1/decisions"]["post"]

        self.assertEqual("createDecision", operation["operationId"])
        self.assertEqual(["decisions"], operation["tags"])
        self.assertEqual(
            "#/components/schemas/DecisionQuery",
            operation["requestBody"]["content"]["application/json"]["schema"]["$ref"],
        )
        self.assertEqual(
            "#/components/schemas/DecisionReceipt",
            operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"],
        )
        self.assertEqual(1, len(operation["parameters"]))
        share = operation["parameters"][0]
        self.assertEqual(("share", "query", False), (share["name"], share["in"], share["required"]))
        self.assertEqual({"type": "boolean", "default": False}, share["schema"])
        self.assertEqual(
            {
                "400": "BadRequest",
                "415": "UnsupportedMediaType",
                "422": "DecisionValidationError",
                "429": "RateLimited",
                "503": "ServiceUnavailable",
                "504": "UpstreamTimeout",
            },
            {
                status: response["$ref"].rsplit("/", 1)[1]
                for status, response in operation["responses"].items()
                if status != "200"
            },
        )

    def test_shared_receipt_read_has_exact_id_and_problem_contract(self):
        operation = _openapi()["paths"]["/v1/decisions/{receipt_id}"]["get"]

        self.assertEqual("getDecisionReceipt", operation["operationId"])
        self.assertEqual(["decisions"], operation["tags"])
        self.assertEqual(1, len(operation["parameters"]))
        receipt_id = operation["parameters"][0]
        self.assertEqual(("receipt_id", "path", True), (receipt_id["name"], receipt_id["in"], receipt_id["required"]))
        self.assertEqual("^receipt_[0-9a-f]{64}$", receipt_id["schema"]["pattern"])
        self.assertEqual(
            "#/components/schemas/DecisionReceipt",
            operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"],
        )
        self.assertEqual(
            {"400", "404", "429", "503"},
            set(operation["responses"]) - {"200"},
        )

    def test_metadata_routes_reference_public_schemas(self):
        spec = _openapi()
        cases = (
            ("/v1/use-cases", "listUseCases", "UseCaseCatalog"),
            ("/v1/benchmark-health", "getBenchmarkHealth", "BenchmarkHealth"),
        )
        for path, operation_id, schema_name in cases:
            with self.subTest(path=path):
                operation = spec["paths"][path]["get"]
                self.assertEqual(operation_id, operation["operationId"])
                self.assertEqual(["metadata"], operation["tags"])
                self.assertNotIn("requestBody", operation)
                self.assertEqual(
                    f"#/components/schemas/{schema_name}",
                    operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"],
                )

    def test_grouped_read_routes_keep_exact_parameters_and_schemas(self):
        spec = _openapi()
        cases = (
            ("/v1/entities/{entity_type}/{slug}", "getEntityDetail", "EntityDetail", {"entity_type": "path", "slug": "path", "benchmark_family_id": "query", "feed_id": "query"}),
            ("/v1/compare", "compareEntities", "CompareResult", {"use_case": "query", "entities": "query", "benchmark_family_id": "query", "feed_id": "query"}),
            ("/v1/leaderboard/{use_case}", "getLeaderboard", "Leaderboard", {"use_case": "path"}),
        )
        for path, operation_id, response_schema, expected_parameters in cases:
            with self.subTest(path=path):
                operation = spec["paths"][path]["get"]
                self.assertEqual(operation_id, operation["operationId"])
                self.assertEqual(["explorer"], operation["tags"])
                self.assertEqual(
                    f"#/components/schemas/{response_schema}",
                    operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"],
                )
                self.assertEqual(expected_parameters, {row["name"]: row["in"] for row in operation["parameters"]})

        entities = spec["paths"]["/v1/compare"]["get"]["parameters"][1]
        self.assertEqual((2, 4, True), (entities["schema"]["minItems"], entities["schema"]["maxItems"], entities["schema"]["uniqueItems"]))
        self.assertEqual(("form", False), (entities["style"], entities["explode"]))

    def test_components_reference_existing_public_schemas(self):
        components = _openapi()["components"]["schemas"]
        expected = {
            "DecisionQuery": "decision-query.schema.json",
            "DecisionReceipt": "decision-receipt.schema.json",
            "UseCaseCatalog": "use-case-catalog.schema.json",
            "BenchmarkHealth": "benchmark-health.schema.json",
            "EntityDetail": "entity-detail.schema.json",
            "CompareResult": "compare-result.schema.json",
            "Leaderboard": "leaderboard.schema.json",
            "ProblemDetails": "problem.schema.json",
        }

        self.assertEqual(expected, {name: value["$ref"] for name, value in components.items()})
        for filename in expected.values():
            self.assertTrue((SCHEMAS / filename).is_file(), filename)

    def test_problem_responses_pin_status_and_generic_validation_vocabulary(self):
        responses = _openapi()["components"]["responses"]
        expected = {
            "BadRequest": (400, "validation", False),
            "UnsupportedMediaType": (415, "validation", False),
            "NotFound": (404, "not_found", False),
            "ValidationError": (422, "validation", False),
            "RateLimited": (429, "rate_limited", True),
            "UpstreamTimeout": (504, "upstream_timeout", True),
        }
        for name, (status, code, retriable) in expected.items():
            with self.subTest(name=name):
                typed = responses[name]["content"]["application/problem+json"]["schema"]["allOf"][1]
                self.assertEqual(status, typed["properties"]["status"]["const"])
                self.assertEqual(code, typed["properties"]["code"]["const"])
                self.assertEqual(retriable, typed["properties"]["retriable"]["const"])

    def test_decision_422_admits_validation_and_via_not_supported_only(self):
        typed = _openapi()["components"]["responses"]["DecisionValidationError"]["content"][
            "application/problem+json"
        ]["schema"]["allOf"][1]
        problem = json.loads((SCHEMAS / "problem.schema.json").read_text(encoding="utf-8"))

        self.assertEqual(422, typed["properties"]["status"]["const"])
        self.assertEqual(["validation", "via_not_supported"], typed["properties"]["code"]["enum"])
        self.assertFalse(typed["properties"]["retriable"]["const"])
        self.assertEqual("array", typed["properties"]["supported_via"]["type"])
        self.assertIn("via_not_supported", problem["properties"]["code"]["enum"])

    def test_openapi_contract_stays_storage_free(self):
        spec = _openapi()

        self.assertNotIn("servers", spec)
        self.assertNotIn("security", spec)
        self.assertNotIn("securitySchemes", spec.get("components", {}))


def _openapi() -> dict:
    return json.loads(OPENAPI.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
