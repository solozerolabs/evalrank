import importlib.util
import json
import subprocess
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Thread


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "packages" / "core" / "src"
SDK_SRC = REPO_ROOT / "packages" / "sdk-python" / "src"
CLI_SRC = REPO_ROOT / "packages" / "cli" / "src"
MCP_SRC = REPO_ROOT / "packages" / "mcp" / "src"
sys.path.insert(0, str(CORE_SRC))
sys.path.insert(0, str(SDK_SRC))
sys.path.insert(0, str(CLI_SRC))
sys.path.insert(0, str(MCP_SRC))

from evalrank_core.canonical_json import restricted_jcs  # noqa: E402
from evalrank_core.decision_contracts import (  # noqa: E402
    DecisionQueryV1,
    DecisionReceiptV1,
)
from evalrank_core.read_contracts import (  # noqa: E402
    verify_compare_result_semantics,
    verify_entity_detail_semantics,
    verify_leaderboard_semantics,
)
from evalrank_cli import main as cli_main  # noqa: E402
from evalrank_mcp import call_tool  # noqa: E402
from evalrank_sdk import EvalRankClient  # noqa: E402


def _load_reference_server():
    path = REPO_ROOT / "scripts" / "reference_server.py"
    spec = importlib.util.spec_from_file_location("evalrank_reference_server", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load reference server")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _golden() -> dict:
    return json.loads(
        (REPO_ROOT / "examples" / "decision-contract-v1.golden.json").read_text(
            encoding="utf-8"
        )
    )


class ReferenceServerE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        module = _load_reference_server()
        self.server = module.create_server("127.0.0.1", 0, repo_root=REPO_ROOT)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()

    def test_non_shared_decision_returns_exact_golden_receipt_but_is_not_retrievable(self):
        corpus = _golden()
        query = dict(reversed(list(corpus["receipt"]["body"]["query"].items())))
        expected_receipt = {
            **corpus["receipt"]["body"],
            "receipt_id": corpus["receipt"]["receipt_id"],
        }

        status, headers, body = self._request(
            "/v1/decisions",
            method="POST",
            payload=query,
        )

        self.assertEqual(200, status)
        self.assertEqual("application/json", headers.get_content_type())
        self.assertEqual(restricted_jcs(expected_receipt), body)
        self.assertEqual(expected_receipt, DecisionReceiptV1.from_dict(json.loads(body)).to_dict())
        self.assertEqual(query, DecisionQueryV1.from_dict(query).to_dict())

        status, _, problem = self._request(
            f"/v1/decisions/{expected_receipt['receipt_id']}"
        )
        self.assertEqual(404, status)
        self.assertEqual("not_found", json.loads(problem)["code"])

    def test_explicit_false_share_is_valid_and_does_not_retain_the_receipt(self):
        corpus = _golden()
        query = corpus["receipt"]["body"]["query"]
        receipt_id = corpus["receipt"]["receipt_id"]

        status, _, body = self._request(
            "/v1/decisions?share=false",
            method="POST",
            payload=query,
        )
        self.assertEqual(200, status)
        self.assertEqual(receipt_id, json.loads(body)["receipt_id"])

        status, _, problem = self._request(f"/v1/decisions/{receipt_id}")
        self.assertEqual(404, status)
        self.assertEqual("not_found", json.loads(problem)["code"])

    def test_shared_decision_is_retrieved_byte_for_byte_and_repeated_shares_are_idempotent(self):
        corpus = _golden()
        query = corpus["receipt"]["body"]["query"]
        receipt_id = corpus["receipt"]["receipt_id"]

        first = self._request("/v1/decisions?share=true", method="POST", payload=query)
        second = self._request("/v1/decisions?share=true", method="POST", payload=query)
        retrieved = self._request(f"/v1/decisions/{receipt_id}")

        self.assertEqual((200, 200, 200), (first[0], second[0], retrieved[0]))
        self.assertEqual(first[2], second[2])
        self.assertEqual(first[2], retrieved[2])
        self.assertEqual("no-store", retrieved[1]["Cache-Control"])

    def test_reference_server_rejects_unknown_decisions_and_deleted_routes(self):
        corpus = _golden()
        unsupported_query = corpus["query"]["input"]

        status, _, body = self._request(
            "/v1/decisions",
            method="POST",
            payload=unsupported_query,
        )
        self.assertEqual(422, status)
        self.assertEqual("validation", json.loads(body)["code"])

        for method, path in (
            ("GET", "/v1/scoring-stages"),
            ("POST", "/v1/recommendations"),
            ("GET", "/v1/decisions/receipt_" + "a" * 64),
        ):
            with self.subTest(method=method, path=path):
                status, _, body = self._request(
                    path,
                    method=method,
                    payload={} if method == "POST" else None,
                )
                self.assertEqual(404, status)
                self.assertEqual("not_found", json.loads(body)["code"])

        status, _, body = self._request("/v1/decisions/not-a-receipt")
        self.assertEqual(400, status)
        self.assertEqual("validation", json.loads(body)["code"])

    def test_reference_server_validates_transport_and_query_contract(self):
        corpus = _golden()
        query = corpus["receipt"]["body"]["query"]

        status, _, body = self._request(
            "/v1/decisions?share=yes",
            method="POST",
            payload=query,
        )
        self.assertEqual(400, status)
        self.assertEqual("validation", json.loads(body)["code"])

        invalid_query = {**query, "unknown": True}
        status, _, body = self._request(
            "/v1/decisions",
            method="POST",
            payload=invalid_query,
        )
        self.assertEqual(422, status)
        self.assertEqual("validation", json.loads(body)["code"])

        status, _, body = self._request(
            "/v1/decisions",
            method="POST",
            raw=b"not-json",
            content_type="application/json",
        )
        self.assertEqual(400, status)
        self.assertEqual("validation", json.loads(body)["code"])

        status, _, body = self._request(
            "/v1/decisions",
            method="POST",
            raw=restricted_jcs(query),
            content_type="text/plain",
        )
        self.assertEqual(415, status)
        self.assertEqual("validation", json.loads(body)["code"])

    def test_reference_server_exposes_deterministic_use_case_and_health_reads(self):
        status, _, use_cases_body = self._request("/v1/use-cases")
        self.assertEqual(200, status)
        use_cases = json.loads(use_cases_body)
        self.assertEqual("use_case_catalog", use_cases["object"])
        self.assertEqual(28, len(use_cases["use_cases"]))

        status, _, health_body = self._request("/v1/benchmark-health")
        self.assertEqual(200, status)
        health = json.loads(health_body)
        self.assertEqual("benchmark_health", health["object"])
        self.assertEqual("1", health["schema_version"])
        self.assertEqual("2026-08-04.1", health["manifest_version"])
        self.assertEqual("2026-08-04T00:00:00Z", health["generated_at"])
        self.assertEqual(28, len(health["cells"]))
        # v2: publication decoupled from validation. Every cell with a published
        # (active) ranking group is now "active", so none remain in the "preview"
        # or "unavailable" holding states.
        self.assertEqual(
            set(),
            {row["cell_id"] for row in health["cells"] if row["status"] == "preview"},
        )
        self.assertEqual(0, sum(row["status"] == "unavailable" for row in health["cells"]))
        self.assertTrue(
            all(
                (row["status"] == "active")
                == (row["published_ranking_group_count"] > 0)
                for row in health["cells"]
            )
        )
        self.assertTrue(
            all(
                row["status"] != "preview" or row["implemented_feed_count"] > 0
                for row in health["cells"]
            )
        )
        _assert_schema_valid("benchmark-health.schema.json", health)

    def test_benchmark_health_maps_quarantined_catalog_state_to_unavailable(self):
        module = _load_reference_server()
        manifest = json.loads(
            (REPO_ROOT / "catalog" / "manifest.json").read_text(encoding="utf-8")
        )
        manifest["cells"][0]["state"] = "quarantined"
        for group in manifest["ranking_groups"]:
            if group["cell_id"] == "code-generation":
                group["state"] = "quarantined"
                group["rank_eligible_count"] = None
                group["quarantine_reason"] = "synthetic health regression"
        for feed in manifest["feeds"]:
            if "code-generation" in feed["candidate_cells"]:
                feed["state"] = "quarantined"
                feed["rank_eligible_count"] = None
                feed["quarantine_reason"] = "synthetic health regression"

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog").mkdir()
            (root / "catalog" / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            health = module._benchmark_health(root)

        code_generation = next(
            row for row in health["cells"] if row["cell_id"] == "code-generation"
        )
        self.assertEqual("unavailable", code_generation["status"])
        self.assertEqual(0, code_generation["published_ranking_group_count"])
        self.assertEqual(0, code_generation["implemented_feed_count"])
        _assert_schema_valid("benchmark-health.schema.json", health)

    def test_reference_server_exercises_all_explorer_reads_and_validates_parameters(self):
        status, _, body = self._request("/v1/leaderboard/code-generation")
        self.assertEqual(200, status)
        leaderboard = json.loads(body)
        _assert_schema_valid("leaderboard.schema.json", leaderboard)
        verify_leaderboard_semantics(leaderboard)
        group = leaderboard["ranking_groups"][0]
        self.assertTrue(group["evidence_snapshot_id"].startswith("explorer_"))
        self.assertNotIn("publication_snapshot_id", group)
        self.assertEqual([], group["entries"])
        self.assertEqual(1, len(group["explorer_views"]))
        entries = group["explorer_views"][0]["entries"]
        self.assertFalse(any(entry["ranking"]["in_top_set"] for entry in entries))
        client = EvalRankClient(self.base_url)
        self.assertEqual(leaderboard, client.leaderboard("code-generation"))

        status, _, body = self._request(
            "/v1/entities/model_configuration/reference-model-a"
        )
        self.assertEqual(200, status)
        entity = json.loads(body)
        _assert_schema_valid("entity-detail.schema.json", entity)
        verify_entity_detail_semantics(entity)
        self.assertEqual(group["evidence_snapshot_id"], entity["evidence_snapshot_id"])
        self.assertNotIn("publication_snapshot_id", entity)
        self.assertEqual(
            entity,
            client.entity("model_configuration", "reference-model-a"),
        )

        status, _, body = self._request(
            "/v1/entities/model_configuration/reference-model-b"
        )
        self.assertEqual(200, status)
        second_entity = json.loads(body)
        _assert_schema_valid("entity-detail.schema.json", second_entity)
        verify_entity_detail_semantics(second_entity)
        self.assertEqual(
            entries[1]["evaluated_configuration_id"],
            second_entity["entity"]["evaluated_configuration"][
                "evaluated_configuration_id"
            ],
        )

        entity_refs = [
            f"model_configuration:{entry['evaluated_configuration_id']}"
            for entry in entries
        ]
        query = urllib.parse.urlencode(
            {
                "use_case": "code-generation",
                "entities": ",".join(entity_refs),
            }
        )
        status, _, body = self._request(f"/v1/compare?{query}")
        self.assertEqual(200, status)
        comparison = json.loads(body)
        _assert_schema_valid("compare-result.schema.json", comparison)
        verify_compare_result_semantics(comparison)
        self.assertEqual(group["evidence_snapshot_id"], comparison["evidence_snapshot_id"])
        self.assertNotIn("publication_snapshot_id", comparison)
        self.assertEqual(
            comparison,
            client.compare("code-generation", tuple(entity_refs)),
        )

        mismatched_entity = deepcopy(entity)
        mismatched_entity["explorer_view"] = {
            "benchmark_family_id": "other-family",
            "feed_id": "other-feed",
        }
        for citation in mismatched_entity["entity"]["citations"]:
            citation["benchmark_family_id"] = "other-family"
        mismatch_client = EvalRankClient(self.base_url)
        mismatch_client._request_json = lambda _path: mismatched_entity
        with self.assertRaisesRegex(ValueError, "explicit selector"):
            mismatch_client.entity(
                "model_configuration",
                "reference-model-a",
                explorer_view=("reference-public-family", "reference-public-feed"),
            )

        mismatched_compare = deepcopy(comparison)
        mismatched_compare["explorer_view"] = {
            "benchmark_family_id": "other-family",
            "feed_id": "other-feed",
        }
        for compared in mismatched_compare["entities"]:
            for citation in compared["citations"]:
                citation["benchmark_family_id"] = "other-family"
        mismatch_client._request_json = lambda _path: mismatched_compare
        with self.assertRaisesRegex(ValueError, "explicit selector"):
            mismatch_client.compare(
                "code-generation",
                tuple(entity_refs),
                explorer_view=("reference-public-family", "reference-public-feed"),
            )

        for path, expected_status in (
            ("/v1/leaderboard/coding", 404),
            ("/v1/entities/model_configuration/unknown-model", 404),
            ("/v1/compare?use_case=code-generation", 400),
            ("/v1/compare?x", 400),
        ):
            with self.subTest(path=path):
                status, _, problem = self._request(path)
                self.assertEqual(expected_status, status)
                self.assertIn(json.loads(problem)["code"], {"not_found", "validation"})

    def test_python_sdk_cli_and_mcp_return_the_exact_same_golden_receipt(self):
        corpus = _golden()
        query = corpus["receipt"]["body"]["query"]
        expected = restricted_jcs(
            {
                **corpus["receipt"]["body"],
                "receipt_id": corpus["receipt"]["receipt_id"],
            }
        )
        client = EvalRankClient(self.base_url)

        sdk_receipt = client.decide(query, share=True)

        with NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
            json.dump(query, handle)
            handle.flush()
            stdout = StringIO()
            exit_code = cli_main(
                [
                    "decide",
                    "--base-url",
                    self.base_url,
                    "--query",
                    handle.name,
                    "--share",
                ],
                stdout=stdout,
                stderr=StringIO(),
            )
        self.assertEqual(0, exit_code)
        cli_receipt = json.loads(stdout.getvalue())

        mcp_result = call_tool(
            "evalrank.decide",
            {"query": query, "share": True},
            base_url=self.base_url,
        )
        mcp_receipt = json.loads(mcp_result["content"][0]["text"])

        for receipt in (sdk_receipt, cli_receipt, mcp_receipt):
            self.assertEqual(expected, restricted_jcs(receipt))

        receipt_id = corpus["receipt"]["receipt_id"]
        self.assertEqual(expected, restricted_jcs(client.decision_receipt(receipt_id)))
        receipt_tool = call_tool(
            "evalrank.decision_receipt",
            {"receipt_id": receipt_id},
            base_url=self.base_url,
        )
        self.assertEqual(
            expected,
            restricted_jcs(json.loads(receipt_tool["content"][0]["text"])),
        )

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
        raw: bytes | None = None,
        content_type: str = "application/json",
    ):
        body = raw
        if payload is not None:
            body = restricted_jcs(payload)
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json, application/problem+json",
                **({"Content-Type": content_type} if body is not None else {}),
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            try:
                return error.code, error.headers, error.read()
            finally:
                error.close()


def _assert_schema_valid(filename: str, payload: dict) -> None:
    script = f'''
import {{ readFileSync, readdirSync }} from "node:fs";
import Ajv2020 from "./packages/sdk-ts/node_modules/ajv/dist/2020.js";
const ajv = new Ajv2020({{ allErrors: true, allowUnionTypes: true, strict: false }});
for (const name of readdirSync("schemas").filter((value) => value.endsWith(".schema.json"))) {{
  ajv.addSchema(JSON.parse(readFileSync(`schemas/${{name}}`, "utf8")));
}}
const validate = ajv.getSchema("https://evalrank.ai/schemas/{filename}");
const payload = JSON.parse(readFileSync(0, "utf8"));
if (!validate || !validate(payload)) {{
  throw new Error(ajv.errorsText(validate?.errors));
}}
'''
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=REPO_ROOT,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr)


if __name__ == "__main__":
    unittest.main()
