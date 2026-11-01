import http.server
import json
import re
import sys
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
for source in (
    REPO_ROOT / "packages" / "core" / "src",
    REPO_ROOT / "packages" / "sdk-python" / "src",
    REPO_ROOT / "packages" / "mcp" / "src",
):
    sys.path.insert(0, str(source))

from evalrank_core.fixtures import (  # noqa: E402
    PUBLIC_FIXTURE_KINDS,
    sample_public_fixture,
    sample_use_case_catalog,
)
from evalrank_mcp import call_tool, list_tools  # noqa: E402


def _decision_vector() -> tuple[dict, dict]:
    corpus = json.loads(
        (REPO_ROOT / "examples" / "decision-contract-v2.golden.json").read_text(
            encoding="utf-8"
        )
    )
    return corpus["receipts"][0]["body"]["query"], {
        **corpus["receipts"][0]["body"],
        "receipt_id": corpus["receipts"][0]["receipt_id"],
    }


class McpFixtureTests(unittest.TestCase):
    def test_mcp_readme_lists_exact_fixture_kinds_and_launch_tools(self):
        text = (REPO_ROOT / "packages" / "mcp" / "README.md").read_text(encoding="utf-8")
        documented_fixtures = set(re.findall(r'"kind": "([a-z-]+)"', text))
        documented_tools = set(re.findall(r'call_tool\("(evalrank\.[a-z_]+)"', text))

        self.assertEqual(set(PUBLIC_FIXTURE_KINDS), documented_fixtures)
        self.assertEqual(
            {
                "evalrank.fixture",
                "evalrank.decide",
                "evalrank.decision_receipt",
                "evalrank.use_cases",
                "evalrank.benchmark_health",
            },
            documented_tools,
        )
        self.assertNotIn("evalrank.recommend", text)
        self.assertNotIn("evalrank.scoring_stages", text)

    def test_list_tools_exposes_closed_decision_and_receipt_inputs(self):
        tools = list_tools()
        self.assertEqual(
            [
                "evalrank.fixture",
                "evalrank.decide",
                "evalrank.decision_receipt",
                "evalrank.use_cases",
                "evalrank.benchmark_health",
            ],
            [tool["name"] for tool in tools],
        )
        decide = tools[1]["inputSchema"]
        self.assertEqual(["query"], decide["required"])
        self.assertFalse(decide["additionalProperties"])
        query = decide["properties"]["query"]
        self.assertFalse(query["additionalProperties"])
        self.assertEqual("decision_query", query["properties"]["object"]["const"])
        self.assertEqual(["schema_version", "cell_id", "objective"], query["required"])
        self.assertEqual("2", query["properties"]["schema_version"]["const"])
        self.assertEqual(["openai", "openrouter"], query["properties"]["via"]["enum"])
        for retired in ("ranking_group_id", "entity_kind", "monthly_budget_microusd", "zero_cache_sensitivity_usage_profile"):
            self.assertNotIn(retired, query["properties"])
        self.assertEqual("boolean", decide["properties"]["share"]["type"])
        receipt = tools[2]["inputSchema"]
        self.assertEqual(["receipt_id"], receipt["required"])
        self.assertEqual(
            "^receipt_[0-9a-f]{64}$",
            receipt["properties"]["receipt_id"]["pattern"],
        )
        for tool in tools[1:]:
            self.assertNotIn("base_url", tool["inputSchema"]["properties"])

    def test_every_fixture_tool_result_matches_core_dispatch(self):
        for kind in PUBLIC_FIXTURE_KINDS:
            with self.subTest(kind=kind):
                result = call_tool("evalrank.fixture", {"kind": kind})
                self.assertFalse(result["isError"])
                self.assertEqual(
                    sample_public_fixture(kind),
                    json.loads(result["content"][0]["text"]),
                )

    def test_decide_posts_query_and_returns_exact_receipt_text(self):
        query, receipt = _decision_vector()
        with LocalApiServer(200, receipt) as server:
            result = call_tool(
                "evalrank.decide",
                {"query": query, "share": True},
                base_url=server.base_url,
            )

        self.assertFalse(result["isError"])
        self.assertEqual(receipt, json.loads(result["content"][0]["text"]))
        self.assertEqual(("POST", "/v1/decisions?share=true"), (server.method, server.path))
        self.assertEqual(query, server.request_json)

    def test_decision_receipt_gets_exact_retained_receipt(self):
        _, receipt = _decision_vector()
        with LocalApiServer(200, receipt) as server:
            result = call_tool(
                "evalrank.decision_receipt",
                {"receipt_id": receipt["receipt_id"]},
                base_url=server.base_url,
            )
        self.assertFalse(result["isError"])
        self.assertEqual(receipt, json.loads(result["content"][0]["text"]))
        self.assertEqual(f"/v1/decisions/{receipt['receipt_id']}", server.path)

    def test_metadata_tools_get_use_cases_and_benchmark_health(self):
        cases = (
            ("evalrank.use_cases", "/v1/use-cases", sample_use_case_catalog().to_dict()),
            (
                "evalrank.benchmark_health",
                "/v1/benchmark-health",
                {
                    "object": "benchmark_health",
                    "schema_version": "1",
                    "manifest_version": "2026-07-09.3",
                    "generated_at": "2026-07-09T00:00:00Z",
                    "cells": [{
                        "cell_id": "code-generation",
                        "status": "unavailable",
                        "ranking_group_count": 1,
                        "published_ranking_group_count": 0,
                        "benchmark_family_count": 1,
                        "candidate_feed_count": 1,
                        "implemented_feed_count": 0,
                        "admitted_feed_count": 0,
                        "rank_eligible_feed_count": 0,
                    }],
                },
            ),
        )
        for tool, path, payload in cases:
            with self.subTest(tool=tool):
                with LocalApiServer(200, payload) as server:
                    result = call_tool(tool, {}, base_url=server.base_url)
                self.assertFalse(result["isError"])
                self.assertEqual(payload, json.loads(result["content"][0]["text"]))
                self.assertEqual(("GET", path), (server.method, server.path))

    def test_problem_details_are_returned_as_mcp_errors(self):
        query, _ = _decision_vector()
        problem = {
            "type": "https://evalrank.ai/problems/rate-limited",
            "title": "Rate limited",
            "status": 429,
            "detail": "too many requests",
            "code": "rate_limited",
            "retriable": True,
            "retry_after": 3,
        }
        with LocalApiServer(429, problem, {"Retry-After": "3"}) as server:
            result = call_tool(
                "evalrank.decide",
                {"query": query},
                base_url=server.base_url,
            )
        self.assertTrue(result["isError"])
        self.assertEqual(problem, json.loads(result["content"][0]["text"]))

    def test_tools_reject_invalid_arguments_and_legacy_names(self):
        query, _ = _decision_vector()
        with self.assertRaisesRegex(ValueError, "arguments must be an object"):
            call_tool("evalrank.decide", [])
        with self.assertRaisesRegex(ValueError, "base_url must be configured by the MCP host"):
            call_tool("evalrank.decide", {"query": query})
        with self.assertRaisesRegex(ValueError, "query must be an object"):
            call_tool("evalrank.decide", {"query": []}, base_url="https://evalrank.example")
        with self.assertRaisesRegex(ValueError, "share must be a boolean"):
            call_tool(
                "evalrank.decide",
                {"query": query, "share": "yes"},
                base_url="https://evalrank.example",
            )
        for name in ("evalrank.recommend", "evalrank.scoring_stages", "evalrank.unknown"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "unknown tool"):
                call_tool(name, {})


class LocalApiServer:
    def __init__(
        self,
        response_status: int,
        response_body: dict,
        response_headers: dict[str, str] | None = None,
    ) -> None:
        self.response_status = response_status
        self.response_body = response_body
        self.response_headers = response_headers or {}
        self.path: str | None = None
        self.headers: dict[str, str] = {}
        self.method: str | None = None
        self.request_json: dict | None = None
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("server is not running")
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> "LocalApiServer":
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                owner.method = self.command
                owner.path = self.path
                owner.headers = {key.lower(): value for key, value in self.headers.items()}
                length = int(self.headers.get("Content-Length", "0"))
                owner.request_json = json.loads(self.rfile.read(length).decode("utf-8"))
                self._write_json()

            def do_GET(self) -> None:  # noqa: N802
                owner.method = self.command
                owner.path = self.path
                owner.headers = {key.lower(): value for key, value in self.headers.items()}
                owner.request_json = None
                self._write_json()

            def _write_json(self) -> None:
                encoded = json.dumps(owner.response_body).encode("utf-8")
                self.send_response(owner.response_status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                for key, value in owner.response_headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format: str, *args: object) -> None:
                return

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join()


if __name__ == "__main__":
    unittest.main()
