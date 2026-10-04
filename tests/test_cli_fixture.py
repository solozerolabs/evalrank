import json
import re
import sys
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Thread


REPO_ROOT = Path(__file__).resolve().parents[1]
for source in (
    REPO_ROOT / "packages" / "core" / "src",
    REPO_ROOT / "packages" / "cli" / "src",
    REPO_ROOT / "packages" / "sdk-python" / "src",
):
    sys.path.insert(0, str(source))

from evalrank_cli import main  # noqa: E402
from evalrank_core.fixtures import (  # noqa: E402
    PUBLIC_FIXTURE_KINDS,
    sample_problem_details,
    sample_public_fixture,
    sample_use_case_catalog,
)


def _decision_vector() -> tuple[dict, dict]:
    corpus = json.loads(
        (REPO_ROOT / "examples" / "decision-contract-v1.golden.json").read_text(
            encoding="utf-8"
        )
    )
    return corpus["receipt"]["body"]["query"], {
        **corpus["receipt"]["body"],
        "receipt_id": corpus["receipt"]["receipt_id"],
    }


class CliFixtureTests(unittest.TestCase):
    def test_cli_readme_lists_exact_public_fixture_commands(self):
        text = (REPO_ROOT / "packages" / "cli" / "README.md").read_text(encoding="utf-8")
        documented = set(re.findall(r"^evalrank fixture ([a-z-]+)$", text, re.M))

        self.assertEqual(set(PUBLIC_FIXTURE_KINDS), documented)
        self.assertNotIn("recommendation", documented)
        self.assertNotIn("scoring-stages", documented)

    def test_every_fixture_kind_writes_its_deterministic_public_json(self):
        for kind in PUBLIC_FIXTURE_KINDS:
            with self.subTest(kind=kind):
                stdout = StringIO()
                exit_code = main(["fixture", kind], stdout=stdout, stderr=StringIO())
                self.assertEqual(0, exit_code)
                self.assertEqual(sample_public_fixture(kind), json.loads(stdout.getvalue()))

    def test_use_case_fixture_matches_the_manifest_taxonomy(self):
        stdout = StringIO()
        self.assertEqual(0, main(["fixture", "use-cases"], stdout=stdout, stderr=StringIO()))
        payload = json.loads(stdout.getvalue())
        self.assertEqual(sample_use_case_catalog().to_dict(), payload)
        self.assertEqual(26, len(payload["use_cases"]))

    def test_invalid_fixture_exits_nonzero(self):
        stderr = StringIO()
        exit_code = main(["fixture", "unknown"], stdout=StringIO(), stderr=stderr)
        self.assertNotEqual(0, exit_code)
        self.assertIn("invalid choice", stderr.getvalue())

    def test_cli_readme_lists_exact_launch_commands_and_no_legacy_commands(self):
        text = (REPO_ROOT / "packages" / "cli" / "README.md").read_text(encoding="utf-8")
        for command in (
            "evalrank use-cases --base-url https://evalrank.example",
            "evalrank benchmark-health --base-url https://evalrank.example",
            "evalrank decide --base-url https://evalrank.example --query query.json",
            "evalrank decide --base-url https://evalrank.example --query - --share",
            "evalrank receipt --base-url https://evalrank.example --receipt-id receipt_",
        ):
            self.assertIn(command, text)
        self.assertNotRegex(text, r"(?m)^evalrank (?:recommend|scoring-stages)\b")

    def test_use_cases_and_benchmark_health_write_public_json(self):
        cases = (
            ("use-cases", "/v1/use-cases", sample_use_case_catalog().to_dict()),
            (
                "benchmark-health",
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
        for command, path, payload in cases:
            with self.subTest(command=command):
                server = _CliTestServer(response_status=200, response_body=payload)
                stdout = StringIO()
                try:
                    exit_code = main(
                        [command, "--base-url", server.base_url],
                        stdout=stdout,
                        stderr=StringIO(),
                    )
                finally:
                    server.close()
                self.assertEqual(0, exit_code)
                self.assertEqual(("GET", path), (server.method, server.path))
                self.assertEqual(payload, json.loads(stdout.getvalue()))

    def test_decide_reads_query_file_posts_share_and_writes_exact_receipt(self):
        query, receipt = _decision_vector()
        server = _CliTestServer(response_status=200, response_body=receipt)
        stdout = StringIO()
        try:
            with NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
                json.dump(query, handle)
                handle.flush()
                exit_code = main(
                    [
                        "decide",
                        "--base-url",
                        server.base_url,
                        "--query",
                        handle.name,
                        "--share",
                    ],
                    stdout=stdout,
                    stderr=StringIO(),
                )
        finally:
            server.close()

        self.assertEqual(0, exit_code)
        self.assertEqual(("POST", "/v1/decisions?share=true"), (server.method, server.path))
        self.assertEqual(query, server.request_json)
        self.assertEqual(receipt, json.loads(stdout.getvalue()))

    def test_decide_reads_query_from_stdin_without_sharing(self):
        query, receipt = _decision_vector()
        server = _CliTestServer(response_status=200, response_body=receipt)
        stdout = StringIO()
        original_stdin = sys.stdin
        sys.stdin = StringIO(json.dumps(query))
        try:
            exit_code = main(
                ["decide", "--base-url", server.base_url, "--query", "-"],
                stdout=stdout,
                stderr=StringIO(),
            )
        finally:
            sys.stdin = original_stdin
            server.close()
        self.assertEqual(0, exit_code)
        self.assertEqual("/v1/decisions", server.path)
        self.assertEqual(receipt, json.loads(stdout.getvalue()))

    def test_receipt_retrieves_exact_shared_receipt(self):
        _, receipt = _decision_vector()
        server = _CliTestServer(response_status=200, response_body=receipt)
        stdout = StringIO()
        try:
            exit_code = main(
                [
                    "receipt",
                    "--base-url",
                    server.base_url,
                    "--receipt-id",
                    receipt["receipt_id"],
                ],
                stdout=stdout,
                stderr=StringIO(),
            )
        finally:
            server.close()
        self.assertEqual(0, exit_code)
        self.assertEqual(f"/v1/decisions/{receipt['receipt_id']}", server.path)
        self.assertEqual(receipt, json.loads(stdout.getvalue()))

    def test_decide_writes_problem_details_to_stderr(self):
        query, _ = _decision_vector()
        problem = {**sample_problem_details().to_dict(), "status": 429}
        server = _CliTestServer(response_status=429, response_body=problem)
        stderr = StringIO()
        try:
            with NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
                json.dump(query, handle)
                handle.flush()
                exit_code = main(
                    ["decide", "--base-url", server.base_url, "--query", handle.name],
                    stdout=StringIO(),
                    stderr=stderr,
                )
        finally:
            server.close()
        self.assertEqual(1, exit_code)
        self.assertEqual(problem, json.loads(stderr.getvalue()))

    def test_decide_rejects_invalid_query_before_network(self):
        _, receipt = _decision_vector()
        server = _CliTestServer(response_status=200, response_body=receipt)
        stderr = StringIO()
        try:
            with NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
                json.dump({"object": "decision_query"}, handle)
                handle.flush()
                exit_code = main(
                    ["decide", "--base-url", server.base_url, "--query", handle.name],
                    stdout=StringIO(),
                    stderr=stderr,
                )
        finally:
            server.close()
        self.assertEqual(2, exit_code)
        self.assertIsNone(server.request_json)
        self.assertIn("invalid decision query", stderr.getvalue())

    def test_commands_reject_non_http_base_url(self):
        for command in (
            ["use-cases", "--base-url", "file:///tmp/evalrank"],
            ["benchmark-health", "--base-url", "file:///tmp/evalrank"],
            ["receipt", "--base-url", "file:///tmp/evalrank", "--receipt-id", "receipt_" + "a" * 64],
        ):
            with self.subTest(command=command[0]):
                stderr = StringIO()
                exit_code = main(command, stdout=StringIO(), stderr=stderr)
                self.assertEqual(2, exit_code)
                self.assertIn("base_url must be an http or https URL", stderr.getvalue())


class _CliTestServer:
    def __init__(self, *, response_status: int, response_body: dict) -> None:
        self.request_json: dict | None = None
        self.path: str | None = None
        self.method: str | None = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                owner.method = self.command
                owner.path = self.path
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                owner.request_json = json.loads(body.decode("utf-8"))
                self._write_json()

            def do_GET(self) -> None:
                owner.method = self.command
                owner.path = self.path
                owner.request_json = None
                self._write_json()

            def _write_json(self) -> None:
                encoded = json.dumps(response_body).encode("utf-8")
                self.send_response(response_status)
                self.send_header("Content-Type", "application/json")
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
