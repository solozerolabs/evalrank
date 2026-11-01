from __future__ import annotations

import json
from typing import Any

from evalrank_core.decision_contracts import REASONING_EFFORTS, SUPPORTED_VIA
from evalrank_core.fixtures import (
    PUBLIC_FIXTURE_KINDS,
    sample_public_fixture,
)
from evalrank_sdk import EvalRankApiError, EvalRankClient


__version__ = "0.0.0"
FIXTURE_TOOL_NAME = "evalrank.fixture"
DECIDE_TOOL_NAME = "evalrank.decide"
DECISION_RECEIPT_TOOL_NAME = "evalrank.decision_receipt"
USE_CASES_TOOL_NAME = "evalrank.use_cases"
BENCHMARK_HEALTH_TOOL_NAME = "evalrank.benchmark_health"


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": FIXTURE_TOOL_NAME,
            "description": "Return a deterministic public EvalRank fixture payload.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind"],
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": list(PUBLIC_FIXTURE_KINDS),
                    }
                },
            },
        },
        {
            "name": DECIDE_TOOL_NAME,
            "description": "Return one EvalRank decision receipt: a callable pick with its priced band, or an abstain with reasons.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query"],
                "properties": {
                    "query": _decision_query_schema(),
                    "share": {
                        "type": "boolean",
                        "default": False,
                        "description": "Retain an append-only public receipt retrievable by ID.",
                    },
                },
            },
        },
        {
            "name": DECISION_RECEIPT_TOOL_NAME,
            "description": "Retrieve one explicitly shared public decision receipt.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["receipt_id"],
                "properties": {
                    "receipt_id": {
                        "type": "string",
                        "pattern": "^receipt_[0-9a-f]{64}$",
                    },
                },
            },
        },
        {
            "name": USE_CASES_TOOL_NAME,
            "description": "Call the public EvalRank use-case metadata API.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        },
        {
            "name": BENCHMARK_HEALTH_TOOL_NAME,
            "description": "Read public benchmark admission and publication health.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        },
    ]


def call_tool(
    name: str,
    arguments: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
) -> dict[str, Any]:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    if name == FIXTURE_TOOL_NAME:
        return _text_result(sample_public_fixture(arguments.get("kind")))
    if name not in {
        DECIDE_TOOL_NAME,
        DECISION_RECEIPT_TOOL_NAME,
        USE_CASES_TOOL_NAME,
        BENCHMARK_HEALTH_TOOL_NAME,
    }:
        raise ValueError(f"unknown tool: {name}")
    if not isinstance(base_url, str) or not base_url:
        raise ValueError("base_url must be configured by the MCP host")
    if name == DECIDE_TOOL_NAME:
        return _decide(base_url, arguments)
    if name == DECISION_RECEIPT_TOOL_NAME:
        return _decision_receipt(base_url, arguments)
    if name == USE_CASES_TOOL_NAME:
        return _metadata(base_url, "use_cases")
    if name == BENCHMARK_HEALTH_TOOL_NAME:
        return _metadata(base_url, "benchmark_health")
    raise ValueError(f"unknown tool: {name}")


def _decide(base_url: str, arguments: dict[str, Any]) -> dict[str, Any]:
    query = arguments.get("query")
    share = arguments.get("share", False)
    if not isinstance(query, dict):
        raise ValueError("query must be an object")
    if not isinstance(share, bool):
        raise ValueError("share must be a boolean")
    try:
        return _text_result(EvalRankClient(base_url).decide(query, share=share))
    except EvalRankApiError as exc:
        return _text_result(exc.problem.to_dict(), is_error=True)


def _decision_receipt(base_url: str, arguments: dict[str, Any]) -> dict[str, Any]:
    receipt_id = arguments.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id:
        raise ValueError("receipt_id is required")
    try:
        return _text_result(EvalRankClient(base_url).decision_receipt(receipt_id))
    except EvalRankApiError as exc:
        return _text_result(exc.problem.to_dict(), is_error=True)


def _metadata(base_url: str, method: str) -> dict[str, Any]:
    client = EvalRankClient(base_url)
    try:
        if method == "use_cases":
            return _text_result(client.use_cases())
        if method == "benchmark_health":
            return _text_result(client.benchmark_health())
    except EvalRankApiError as exc:
        return _text_result(exc.problem.to_dict(), is_error=True)
    raise ValueError(f"unknown metadata method: {method}")


def _text_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "isError": is_error,
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            }
        ],
    }


def _decision_query_schema() -> dict[str, Any]:
    usage_profile = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "basis",
            "uncached_input_tokens",
            "cached_read_tokens",
            "output_tokens",
            "cache_writes",
            "cache_storage_token_seconds",
        ],
        "properties": {
            "basis": {"type": "string", "enum": ["measured", "estimated"]},
            "uncached_input_tokens": {"type": "integer", "minimum": 0},
            "cached_read_tokens": {"type": "integer", "minimum": 0},
            "output_tokens": {"type": "integer", "minimum": 0},
            "cache_writes": {
                "type": "array",
                "uniqueItems": True,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ttl_seconds", "tokens"],
                    "properties": {
                        "ttl_seconds": {"type": "integer", "minimum": 1},
                        "tokens": {"type": "integer", "minimum": 1},
                    },
                },
            },
            "cache_storage_token_seconds": {"type": "integer", "minimum": 0},
        },
    }
    string_set = {
        "type": "array",
        "minItems": 1,
        "uniqueItems": True,
        "items": {"type": "string", "minLength": 1},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "cell_id", "objective"],
        "properties": {
            "object": {"const": "decision_query"},
            "schema_version": {"const": "2"},
            "cell_id": {"type": "string", "minLength": 1},
            "objective": {
                "type": "string",
                "enum": ["lowest_cost_within_top_set", "capability_top_set"],
            },
            "via": {
                "type": "string",
                "enum": list(SUPPORTED_VIA),
                "description": "Call surface; default openai when provider_ids is [\"openai\"], else openrouter.",
            },
            "provider_ids": string_set,
            "api": {"type": "string", "enum": ["chat_completions", "responses"]},
            "reasoning_effort": {
                "type": "string",
                "enum": list(REASONING_EFFORTS),
                "description": "Comparison level, default medium; capability_top_set ignores it unless pinned.",
            },
            "regions": string_set,
            "minimum_context_tokens": {"type": "integer", "minimum": 1},
            "usage_profile": usage_profile,
        },
    }


__all__ = [
    "BENCHMARK_HEALTH_TOOL_NAME",
    "DECIDE_TOOL_NAME",
    "DECISION_RECEIPT_TOOL_NAME",
    "FIXTURE_TOOL_NAME",
    "USE_CASES_TOOL_NAME",
    "call_tool",
    "list_tools",
    "__version__",
]
