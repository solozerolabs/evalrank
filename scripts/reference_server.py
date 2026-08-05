#!/usr/bin/env python3
"""Storage-free local server for exercising EvalRank's public HTTP contract.

The server intentionally supports one synthetic decision vector. It is a
portable contract exerciser, not a hosted ranking runtime.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlsplit


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = DEFAULT_REPO_ROOT / "packages" / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from evalrank_core.canonical_json import restricted_jcs, sha256_hex  # noqa: E402
from evalrank_core.decision_contracts import (  # noqa: E402
    ConfigurationPassportV1,
    DecisionQueryV1,
    DecisionReceiptV1,
    EvaluatedConfigurationV1,
)
from evalrank_core.fixtures import sample_use_case_catalog  # noqa: E402
from evalrank_core.read_contracts import (  # noqa: E402
    RankingGroupSnapshotRefV1,
    SnapshotSetDescriptorV1,
)


_MAX_REQUEST_BYTES = 1_000_000
_RECEIPT_PATH_RE = re.compile(r"^/v1/decisions/(receipt_[0-9a-f]{64})$")
_LEADERBOARD_PATH_RE = re.compile(r"^/v1/leaderboard/([a-z0-9]+(?:-[a-z0-9]+)*)$")
_ENTITY_PATH_RE = re.compile(
    r"^/v1/entities/"
    r"(agent_system|arena_system|component_configuration|model_configuration|system_configuration)/"
    r"([a-z0-9]+(?:[._:-][a-z0-9]+)*)$"
)


class _ReferenceServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], *, repo_root: Path) -> None:
        super().__init__(address, _ReferenceHandler)
        self.repo_root = repo_root
        corpus = json.loads(
            (repo_root / "examples" / "decision-contract-v1.golden.json").read_text(
                encoding="utf-8"
            )
        )
        receipt_payload = {
            **corpus["receipt"]["body"],
            "receipt_id": corpus["receipt"]["receipt_id"],
        }
        self.golden_receipt = DecisionReceiptV1.from_dict(receipt_payload)
        self.golden_receipt_bytes = restricted_jcs(self.golden_receipt.to_dict())
        self.golden_query_canonical = self.golden_receipt.query.canonical_json()
        self.use_cases_bytes = restricted_jcs(sample_use_case_catalog().to_dict())
        self.benchmark_health_bytes = restricted_jcs(_benchmark_health(repo_root))
        read_fixtures = _public_read_fixtures()
        self.leaderboard_bytes = restricted_jcs(read_fixtures["leaderboard"])
        self.entity_bytes_by_slug = {
            slug: restricted_jcs(entity)
            for slug, entity in read_fixtures["entities"].items()
        }
        self.compare_bytes = restricted_jcs(read_fixtures["compare"])
        self.compare_entity_refs = read_fixtures["compare_entity_refs"]
        self.shared_receipts: dict[str, bytes] = {}
        self.shared_receipts_lock = Lock()

    def retain_receipt(self, receipt_id: str, payload: bytes) -> None:
        with self.shared_receipts_lock:
            retained = self.shared_receipts.setdefault(receipt_id, payload)
            if retained != payload:
                raise RuntimeError("content-addressed receipt collision")

    def receipt_bytes(self, receipt_id: str) -> bytes | None:
        with self.shared_receipts_lock:
            return self.shared_receipts.get(receipt_id)


class _ReferenceHandler(BaseHTTPRequestHandler):
    server: _ReferenceServer

    def do_GET(self) -> None:
        target = urlsplit(self.path)
        if target.path == "/v1/compare":
            self._serve_compare(target.query)
            return
        if target.path == "/v1/use-cases":
            self._json(200, self.server.use_cases_bytes)
            return
        if target.path == "/v1/benchmark-health":
            self._json(200, self.server.benchmark_health_bytes)
            return
        leaderboard_match = _LEADERBOARD_PATH_RE.fullmatch(target.path)
        if leaderboard_match is not None:
            if leaderboard_match.group(1) != "code-generation":
                self._problem(404, "not_found", "The requested cell was not found")
                return
            self._json(200, self.server.leaderboard_bytes)
            return
        entity_match = _ENTITY_PATH_RE.fullmatch(target.path)
        if entity_match is not None:
            if not _selected_reference_view(target.query):
                self._problem(400, "validation", "Explorer selectors must identify the reference family and feed")
                return
            if entity_match.group(1) != "model_configuration":
                self._problem(404, "not_found", "The requested entity was not found")
                return
            body = self.server.entity_bytes_by_slug.get(entity_match.group(2))
            if body is None:
                self._problem(404, "not_found", "The requested entity was not found")
                return
            self._json(200, body)
            return
        if target.query:
            self._problem(400, "validation", "This GET route does not accept query parameters")
            return
        match = _RECEIPT_PATH_RE.fullmatch(target.path)
        if match is not None:
            retained = self.server.receipt_bytes(match.group(1))
            if retained is not None:
                self._json(200, retained, cache_control="no-store")
                return
            self._problem(404, "not_found", "The requested receipt was not found")
            return
        if target.path.startswith("/v1/decisions/"):
            self._problem(400, "validation", "receipt_id has an invalid format")
            return
        self._problem(404, "not_found", "The requested public resource was not found")

    def _serve_compare(self, query_string: str) -> None:
        try:
            query = parse_qs(
                query_string,
                keep_blank_values=True,
                strict_parsing=True,
            )
        except ValueError:
            self._problem(400, "validation", "Malformed compare query parameters")
            return
        if set(query) not in (
            {"use_case", "entities"},
            {"use_case", "entities", "benchmark_family_id", "feed_id"},
        ) or any(
            len(values) != 1 for values in query.values()
        ):
            self._problem(400, "validation", "compare requires one use_case and one entities value")
            return
        if not _selected_reference_view_values(query):
            self._problem(400, "validation", "Explorer selectors must identify the reference family and feed")
            return
        if query["use_case"][0] != "code-generation":
            self._problem(404, "not_found", "The requested cell was not found")
            return
        entity_refs = tuple(query["entities"][0].split(","))
        if entity_refs != self.server.compare_entity_refs:
            self._problem(404, "not_found", "The requested comparison was not found")
            return
        self._json(200, self.server.compare_bytes)

    def do_POST(self) -> None:
        target = urlsplit(self.path)
        if target.path != "/v1/decisions":
            self._discard_request_body()
            self._problem(404, "not_found", "The requested public resource was not found")
            return
        share = _share_parameter(target.query)
        if share is None:
            self._discard_request_body()
            self._problem(400, "validation", "share must be omitted or exactly true or false")
            return
        media_type, charset_ok = _json_content_type(self.headers.get("Content-Type"))
        if media_type != "application/json" or not charset_ok:
            self._discard_request_body()
            self._problem(415, "validation", "Content-Type must be application/json with UTF-8")
            return
        try:
            request_bytes = self._read_request_body()
            payload = json.loads(request_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._problem(400, "validation", f"Malformed JSON request: {error}")
            return
        try:
            query = DecisionQueryV1.from_dict(payload)
        except (TypeError, ValueError) as error:
            self._problem(422, "validation", f"DecisionQueryV1 validation failed: {error}")
            return
        if query.canonical_json() != self.server.golden_query_canonical:
            self._problem(
                422,
                "validation",
                "The reference server supports only its published synthetic decision vector",
            )
            return
        if share:
            self.server.retain_receipt(
                self.server.golden_receipt.receipt_id,
                self.server.golden_receipt_bytes,
            )
        self._json(200, self.server.golden_receipt_bytes, cache_control="no-store")

    def do_HEAD(self) -> None:
        self._problem(405, "validation", "HEAD is not implemented by the reference server")

    def do_PUT(self) -> None:
        self._discard_request_body()
        self._problem(405, "validation", "Method not allowed")

    def do_PATCH(self) -> None:
        self._discard_request_body()
        self._problem(405, "validation", "Method not allowed")

    def do_DELETE(self) -> None:
        self._problem(405, "validation", "Method not allowed")

    def _read_request_body(self) -> bytes:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None or not raw_length.isdigit():
            raise ValueError("Content-Length must be a nonnegative integer")
        length = int(raw_length)
        if length > _MAX_REQUEST_BYTES:
            raise ValueError("request body exceeds 1000000 bytes")
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("request body ended before Content-Length")
        return body

    def _discard_request_body(self) -> None:
        raw_length = self.headers.get("Content-Length", "0")
        if raw_length.isdigit():
            self.rfile.read(min(int(raw_length), _MAX_REQUEST_BYTES))

    def _json(
        self,
        status: int,
        body: bytes,
        *,
        content_type: str = "application/json",
        cache_control: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if cache_control is not None:
            self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(body)

    def _problem(self, status: int, code: str, detail: str) -> None:
        title = {
            400: "Invalid request",
            404: "Not found",
            405: "Method not allowed",
            415: "Unsupported media type",
            422: "Validation failed",
        }[status]
        body = restricted_jcs(
            {
                "type": f"https://evalrank.ai/problems/{code}",
                "title": title,
                "status": status,
                "detail": detail,
                "code": code,
                "retriable": False,
            }
        )
        self._json(status, body, content_type="application/problem+json", cache_control="no-store")

    def log_message(self, format: str, *args: object) -> None:
        return


def _share_parameter(query: str) -> bool | None:
    if not query:
        return False
    try:
        parsed = parse_qs(query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    if parsed == {"share": ["true"]}:
        return True
    if parsed == {"share": ["false"]}:
        return False
    return None


def _selected_reference_view(query: str) -> bool:
    if not query:
        return True
    try:
        return _selected_reference_view_values(
            parse_qs(query, keep_blank_values=True, strict_parsing=True)
        )
    except ValueError:
        return False


def _selected_reference_view_values(query: dict[str, list[str]]) -> bool:
    selectors = {key: value for key, value in query.items() if key not in {"use_case", "entities"}}
    return not selectors or selectors == {
        "benchmark_family_id": ["reference-public-family"],
        "feed_id": ["reference-public-feed"],
    }


def _json_content_type(value: str | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    parts = [part.strip() for part in value.split(";")]
    media_type = parts[0].lower()
    if len(parts) == 1:
        return media_type, True
    if len(parts) == 2 and parts[1].lower().replace(" ", "") == "charset=utf-8":
        return media_type, True
    return media_type, False


def _benchmark_health(repo_root: Path) -> dict[str, Any]:
    manifest = json.loads((repo_root / "catalog" / "manifest.json").read_text(encoding="utf-8"))
    groups_by_cell: dict[str, list[dict[str, Any]]] = {}
    families_by_cell: dict[str, set[str]] = {}
    feeds_by_cell: dict[str, list[dict[str, Any]]] = {}
    for group in manifest["ranking_groups"]:
        groups_by_cell.setdefault(group["cell_id"], []).append(group)
    for family in manifest["benchmark_families"]:
        for cell_id in family["candidate_cells"]:
            families_by_cell.setdefault(cell_id, set()).add(family["benchmark_family_id"])
    for feed in manifest["feeds"]:
        for cell_id in feed["candidate_cells"]:
            feeds_by_cell.setdefault(cell_id, []).append(feed)
    rows = []
    for cell in manifest["cells"]:
        cell_id = cell["cell_id"]
        groups = groups_by_cell.get(cell_id, [])
        feeds = feeds_by_cell.get(cell_id, [])
        published_group_count = sum(group["state"] == "active" for group in groups)
        implemented_feed_count = sum(
            feed["state"] in {"shadow", "active"} for feed in feeds
        )
        health_status = (
            "active"
            if published_group_count
            else "preview"
            if implemented_feed_count
            else "unavailable"
        )
        rows.append(
            {
                "cell_id": cell_id,
                "status": health_status,
                "ranking_group_count": len(groups),
                "published_ranking_group_count": published_group_count,
                "benchmark_family_count": len(families_by_cell.get(cell_id, set())),
                "candidate_feed_count": len(feeds),
                "implemented_feed_count": implemented_feed_count,
                "admitted_feed_count": sum(
                    feed["state"] == "active" for feed in feeds
                ),
                "rank_eligible_feed_count": sum(
                    feed["state"] == "active"
                    and feed["rank_eligible_count"] is not None
                    and feed["rank_eligible_count"] > 0
                    for feed in feeds
                ),
            }
        )
    return {
        "object": "benchmark_health",
        "schema_version": "1",
        "manifest_version": manifest["manifest_version"],
        "generated_at": "2026-08-04T00:00:00Z",
        "cells": rows,
    }


def _public_read_fixtures() -> dict[str, Any]:
    evidence_snapshot_id = f"explorer_{'b' * 64}"
    ranking_group_id = (
        "rg-code-generation-model-configuration-direct-prompt-model-configuration-v1"
    )
    descriptor = SnapshotSetDescriptorV1(
        cell_id="code-generation",
        manifest_version="2026-07-10.1",
        methodology_version="2026-07-10.1.reference-server-v1",
        ranking_group_snapshots=(
            RankingGroupSnapshotRefV1(
                ranking_group_id=ranking_group_id,
                evidence_snapshot_id=evidence_snapshot_id,
            ),
        ),
    )
    configurations = tuple(
        _reference_configuration(name)
        for name in ("reference-model-a", "reference-model-b")
    )
    citations = [
        {
            "source_artifact_id": f"artifact_{'d' * 64}",
            "benchmark_family_id": "reference-public-family",
            "title": "Synthetic public reference evidence",
            "url": "https://example.com/evalrank/reference-evidence",
        }
    ]
    eligibility = {
        "published_claim": "explorer",
        "rank_eligible_configuration_count": 0,
        "current_independent_family_count": 1,
        "required_independent_family_count": 3,
        "current_overlap_count": 2,
        "required_overlap_count": 2,
        "calibration_status": "unvalidated",
        "gap_codes": [
            "calibration_unvalidated",
            "insufficient_independent_families",
            "no_rank_eligible_configurations",
        ],
    }
    rankings = (
        {
            "rank": 1,
            "display_name": "Reference model A",
            "capability_score": 1,
            "uncertainty": {"kind": "interval", "level": 1, "lower": 1, "upper": 1},
            "in_top_set": False,
            "evidence_family_count": 1,
            "caveat_codes": [],
        },
        {
            "rank": 2,
            "display_name": "Reference model B",
            "capability_score": 0,
            "uncertainty": {"kind": "interval", "level": 1, "lower": 0, "upper": 0},
            "in_top_set": False,
            "evidence_family_count": 1,
            "caveat_codes": [],
        },
    )
    envelope = {
        "schema_version": "1",
        "cell_id": descriptor.cell_id,
        "manifest_version": descriptor.manifest_version,
        "methodology_version": descriptor.methodology_version,
        "snapshot_set_id": descriptor.snapshot_set_id,
        "snapshot_set_descriptor": descriptor.to_dict(),
        "generated_at": "2026-07-10T00:00:00Z",
    }
    leaderboard = {
        "object": "leaderboard",
        **envelope,
        "cell_state": "preview",
        "ranking_groups": [
            {
                "ranking_group_id": ranking_group_id,
                "entity_kind": "model_configuration",
                "interaction_policy": "direct_prompt",
                "configuration_passport_class": "model-configuration-v1",
                "state": "preview",
                "evidence_snapshot_id": evidence_snapshot_id,
                "eligibility_summary": eligibility,
                "entries": [],
                "citations": [],
                "explorer_views": [
                    {
                        "benchmark_family_id": "reference-public-family",
                        "feed_id": "reference-public-feed",
                        "metric_direction": "higher",
                        "observed_at": "2026-07-10T00:00:00Z",
                        "expires_at": "2026-07-17T00:00:00Z",
                        "agreement": "single_source",
                        "entries": [
                            {
                                "evaluated_configuration_id": configuration.evaluated_configuration_id,
                                "ranking": ranking,
                            }
                            for configuration, ranking in zip(
                                configurations, rankings, strict=True
                            )
                        ],
                        "citations": citations,
                    }
                ],
            }
        ],
    }
    entities: dict[str, dict[str, Any]] = {}
    for configuration, ranking in zip(configurations, rankings, strict=True):
        entity = {
            "object": "entity_detail",
            **envelope,
            "ranking_group_id": ranking_group_id,
            "state": "preview",
            "evidence_snapshot_id": evidence_snapshot_id,
            "explorer_view": {
                "benchmark_family_id": "reference-public-family",
                "feed_id": "reference-public-feed",
            },
            "eligibility_summary": eligibility,
            "entity": {
                "evaluated_configuration": configuration.to_dict(),
                "ranking": ranking,
                "citations": citations,
            },
        }
        entities[configuration.evaluated_configuration_id] = entity
        entities[configuration.passport.canonical_name] = entity
    compare = {
        "object": "compare_result",
        **envelope,
        "ranking_group_id": ranking_group_id,
        "entity_kind": "model_configuration",
        "interaction_policy": "direct_prompt",
        "configuration_passport_class": "model-configuration-v1",
        "state": "preview",
        "evidence_snapshot_id": evidence_snapshot_id,
        "explorer_view": {
            "benchmark_family_id": "reference-public-family",
            "feed_id": "reference-public-feed",
        },
        "eligibility_summary": eligibility,
        "entities": [
            {
                "evaluated_configuration_id": configuration.evaluated_configuration_id,
                "ranking": ranking,
                "citations": citations,
            }
            for configuration, ranking in zip(configurations, rankings, strict=True)
        ],
    }
    entity_refs = tuple(
        f"model_configuration:{configuration.evaluated_configuration_id}"
        for configuration in configurations
    )
    return {
        "leaderboard": leaderboard,
        "entities": entities,
        "compare": compare,
        "compare_entity_refs": entity_refs,
    }


def _reference_configuration(canonical_name: str) -> EvaluatedConfigurationV1:
    passport = ConfigurationPassportV1(
        entity_kind="model_configuration",
        canonical_name=canonical_name,
        revision="2026-07-10",
        interaction_policy="direct_prompt",
        configuration_passport_class="model-configuration-v1",
        harness=None,
        scaffold=None,
    )
    return EvaluatedConfigurationV1(
        evaluated_configuration_id=f"config_{sha256_hex(passport.to_dict())}",
        passport=passport,
    )


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    repo_root: Path | str = DEFAULT_REPO_ROOT,
) -> ThreadingHTTPServer:
    return _ReferenceServer((host, port), repo_root=Path(repo_root).resolve())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    server = create_server(args.host, args.port)
    host, port = server.server_address
    print(f"EvalRank reference server listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
