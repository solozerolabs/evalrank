from __future__ import annotations

import argparse
import json
import sys
from contextlib import redirect_stderr
from typing import TextIO

from evalrank_core.fixtures import (
    PUBLIC_FIXTURE_KINDS,
    sample_public_fixture,
)
from evalrank_sdk import EvalRankApiError, EvalRankClient


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _parser()

    try:
        with redirect_stderr(stderr):
            args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    if args.command == "fixture":
        payload = sample_public_fixture(args.kind)
        stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    if args.command == "use-cases":
        try:
            payload = EvalRankClient(args.base_url).use_cases()
        except ValueError as exc:
            stderr.write(str(exc) + "\n")
            return 2
        except EvalRankApiError as exc:
            stderr.write(json.dumps(exc.problem.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")
            return 1
        stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    if args.command == "benchmark-health":
        try:
            payload = EvalRankClient(args.base_url).benchmark_health()
        except ValueError as exc:
            stderr.write(str(exc) + "\n")
            return 2
        except EvalRankApiError as exc:
            stderr.write(json.dumps(exc.problem.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")
            return 1
        stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    if args.command == "receipt":
        try:
            payload = EvalRankClient(args.base_url).decision_receipt(args.receipt_id)
        except ValueError as exc:
            stderr.write(str(exc) + "\n")
            return 2
        except EvalRankApiError as exc:
            stderr.write(json.dumps(exc.problem.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")
            return 1
        stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    if args.command == "decide":
        try:
            client = EvalRankClient(args.base_url)
        except ValueError as exc:
            stderr.write(str(exc) + "\n")
            return 2
        try:
            payload = _read_query(args.query)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            stderr.write(f"invalid decision query JSON: {exc}\n")
            return 2
        try:
            receipt = client.decide(payload, share=args.share)
        except (TypeError, ValueError) as exc:
            stderr.write(f"invalid decision query: {exc}\n")
            return 2
        except EvalRankApiError as exc:
            stderr.write(json.dumps(exc.problem.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")
            return 1
        stdout.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
        return 0

    parser.print_help(file=stderr)
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evalrank")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fixture = subparsers.add_parser("fixture", help="write a public fixture payload")
    fixture.add_argument(
        "kind",
        choices=PUBLIC_FIXTURE_KINDS,
    )
    use_cases = subparsers.add_parser("use-cases", help="call the public use-case metadata API")
    use_cases.add_argument("--base-url", required=True)
    health = subparsers.add_parser("benchmark-health", help="read public benchmark health")
    health.add_argument("--base-url", required=True)
    receipt = subparsers.add_parser("receipt", help="retrieve one explicitly shared decision receipt")
    receipt.add_argument("--base-url", required=True)
    receipt.add_argument("--receipt-id", required=True)
    decide = subparsers.add_parser("decide", help="call the public decision API")
    decide.add_argument("--base-url", required=True)
    decide.add_argument("--query", required=True, help="DecisionQueryV2 JSON file, or '-' for stdin")
    decide.add_argument(
        "--share",
        action="store_true",
        help="retain an append-only public receipt that anyone with its ID can retrieve",
    )

    return parser


def _read_query(path: str) -> dict:
    if path == "-":
        payload = json.load(sys.stdin)
    else:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("decision query JSON must be an object")
    return payload


__all__ = ["main"]
