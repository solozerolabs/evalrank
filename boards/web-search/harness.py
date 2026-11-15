"""Web-search board: every web search API sold through Monid's pay-per-call gateway, on 51 queries.

Candidates are discovered each run (``POST /v1/discover``, then ``/v1/inspect`` for the input
schema); there is no hand list. Each candidate answers every query in ``items.json`` with its own
defaults, asked for 5 results; a query scores the reciprocal rank of the first official result
(1, 1/2, ... 1/5, else 0). The board metric is ``search_score``: that mean (MRR@5), a unit
interval, higher is better. Every call's price is the USD the gateway billed for it
(``billing.reportedCost``), so ``usd_per_call`` is measured from the bill, never a list price.

    MONID_API_KEY=... python3 harness.py run --results results.json
    MONID_API_KEY=... python3 harness.py candidates
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ITEMS = HERE / "items.json"
API = "https://api.monid.ai"
HARNESS_VERSION = "2"
LIMIT = 5
DISCOVERY_QUERIES = ("web search", "search engine results api", "search the web google results")
CATEGORY = "web-search"
#: Verticals that are not a general web search (news, images, places, AI answers, ...).
NOT_GENERAL = re.compile(
    r"news|image|video|local|place|map|scholar|shopping|ai[-_.]?mode|copilot|ask|answer|compan|website|content|trend|job|patent",
    re.I,
)
QUERY_KEYS = ("query", "q", "p", "objective", "search_query")
LIMIT_KEYS = ("num", "limit", "count", "max_results", "numResults", "num_results", "maxResults", "size")
URL_KEYS = ("url", "link", "href")
#: Result lists by name, best first: a SERP also carries video, "related" and navigation lists.
RESULT_KEYS = ("organic", "organic_results", "results", "web", "items", "data", "hits", "documents")
#: A listed price above this per call is not a candidate (the board must stay cheap to run).
MAX_LIST_USD = 0.01
MAX_ERRORS = 3  # of 51 queries; more makes the row unjudged (excluded) and retried
MAX_ATTEMPTS = 3
RESCORE_DAYS = 28
QUERY = "{query}"  # the placeholder a published request carries where the query goes
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def items() -> dict:
    return json.loads(ITEMS.read_text(encoding="utf-8"))


def item_set_sha256(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec["items"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def official(url: str, owners: list[str]) -> bool:
    """``url`` is on one of ``owners``: an apex (any subdomain) or a ``host/path`` prefix."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    for owner in owners:
        if "/" in owner:
            o_host, o_path = owner.split("/", 1)
            if host == o_host and (parts.path.lower() + "/").startswith(f"/{o_path.lower()}/"):
                return True
        elif host == owner or host.endswith("." + owner):
            return True
    return False


def reciprocal_rank(urls: list[str], owners: list[str]) -> float:
    for rank, url in enumerate(urls[:LIMIT], 1):
        if official(url, owners):
            return round(1 / rank, 4)
    return 0.0


def result_urls(output: object) -> list[str]:
    """URLs of the result list in ``output``, in order: the list of URL-bearing objects whose key
    ranks best in ``RESULT_KEYS`` (an unnamed one ranks last), the shallowest on a tie."""
    found: list[tuple[int, int, list[str]]] = []
    queue: list[tuple[object, str, int]] = [(output, "", 0)]
    while queue:
        node, key, depth = queue.pop(0)
        if isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
            urls = [str(next(x[k] for k in URL_KEYS if x.get(k))) for x in node if any(x.get(k) for k in URL_KEYS)]
            if urls:
                name = key.lower()
                found.append((RESULT_KEYS.index(name) if name in RESULT_KEYS else len(RESULT_KEYS), depth, urls))
        if isinstance(node, dict):
            queue.extend((v, k, depth + 1) for k, v in node.items() if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            queue.extend((v, key, depth + 1) for v in node if isinstance(v, (dict, list)))
    return min(found, key=lambda f: (f[0], f[1]))[2] if found else []


def _types(prop: dict) -> list:
    kind = prop.get("type")
    return kind if isinstance(kind, list) else [kind]


def build_request(schema: dict) -> dict | None:
    """``{kind, input}`` with ``QUERY`` where the query goes, or None when the board cannot fill it."""
    for kind in ("body", "queryParams"):
        doc = schema.get(kind)
        if isinstance(doc, dict) and isinstance(doc.get("properties"), dict):
            break
    else:
        return None
    props, required = doc["properties"], set(doc.get("required") or ())
    values: dict = {}
    for name in sorted(required):
        prop = props.get(name) or {}
        if "string" in _types(prop) and "enum" not in prop:
            values[name] = QUERY
        elif "array" in _types(prop) and (prop.get("items") or {}).get("type") == "string":
            values[name] = [QUERY]
        elif "default" not in prop:
            return None
    if QUERY not in json.dumps(values):
        name = next((k for k in QUERY_KEYS if k in props), None)
        if name is None:
            return None
        values[name] = QUERY
    for name in LIMIT_KEYS:
        prop = props.get(name)
        if isinstance(prop, dict) and "integer" in _types(prop):
            values[name] = max(LIMIT, int(prop.get("minimum") or 1))
            break
    return {"kind": kind, "input": values}


def fill(request: dict, query: str) -> dict:
    return json.loads(json.dumps(request["input"]).replace(json.dumps(QUERY), json.dumps(query)))


class Monid:
    def __init__(self, key: str) -> None:
        self.key = key

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 60) -> dict:
        req = urllib.request.Request(
            API + path,
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https host
            return json.loads(resp.read() or b"{}")

    def run(self, provider: str, endpoint: str, kind: str, values: dict, deadline_s: float = 60) -> tuple[object, float | None, float]:
        """``(output, usd billed, seconds)``; raises on a failed run."""
        start = time.monotonic()
        run = self.call("POST", "/v1/run", {"provider": provider, "endpoint": endpoint, "input": {kind: values}})
        while run.get("status") not in {"COMPLETED", "FAILED", "BLOCKED", "STOPPED", "TIMED_OUT"}:
            if time.monotonic() - start > deadline_s:
                raise TimeoutError("run did not finish")
            time.sleep(1)
            run = self.call("GET", f"/v1/runs/{run['runId']}")
        if run["status"] != "COMPLETED":
            raise RuntimeError(f"run {run['status']}")
        return run.get("output"), billed_usd(run), time.monotonic() - start


def billed_usd(run: dict) -> float | None:
    """What the gateway billed for a run: ``billing.reportedCost`` (micro-dollars) on a sync
    answer, ``cost`` (dollars) on a polled one; None when it reported neither (never free)."""
    reported = (run.get("billing") or {}).get("reportedCost")
    if isinstance(reported, dict) and reported.get("value") is not None:
        return float(reported["value"]) / 1e6
    cost = (run.get("cost") or {}).get("value")
    return None if cost is None else float(cost)


def listed_usd(price: object) -> float:
    if not isinstance(price, dict):
        return 0.0
    amount = price.get("amount")
    value = amount.get("value") if isinstance(amount, dict) else amount
    fee = (price.get("flatFee") or {}).get("value") or 0
    return float(value or 0) + float(fee)


def candidates(monid: Monid) -> list[dict]:
    """Every general web search endpoint the gateway sells that the board can call."""
    seen: dict[tuple[str, str], dict] = {}
    for query in DISCOVERY_QUERIES:
        for hit in monid.call("POST", "/v1/discover", {"query": query, "limit": 20}).get("results", []):
            key = (hit["provider"], hit["endpoint"])
            if key not in seen and not NOT_GENERAL.search(hit["endpoint"]) and listed_usd(hit.get("price")) <= MAX_LIST_USD:
                seen[key] = hit
    found = []
    for (provider, endpoint), hit in sorted(seen.items()):
        spec = monid.call("POST", "/v1/inspect", {"provider": provider, "endpoint": endpoint})
        if CATEGORY not in (spec.get("categories") or []):
            continue
        request = build_request(spec.get("input") or {})
        if request is None:
            continue
        found.append({
            "model": f"{provider}{endpoint}",
            "provider": provider,
            "endpoint": endpoint,
            "request": request,
            "list_usd": listed_usd(hit.get("price")),
        })
    return found


def summarize(candidate: dict, rows: list[dict]) -> dict:
    answered = [r for r in rows if not r["error"]]
    errors = len(rows) - len(answered)
    bills = [r["usd"] for r in answered if r["usd"] is not None]
    billed = sum(bills)
    n = len(answered)
    return {
        "model": candidate["model"],
        "provider": candidate["provider"],
        "endpoint": candidate["endpoint"],
        "request": candidate["request"],
        "score": round(sum(r["rr"] for r in answered) / n, 4) if n else 0.0,
        "hit_at_1": round(sum(r["rr"] == 1 for r in answered) / n, 4) if n else 0.0,
        "queries": len(rows),
        "errors": errors,
        "excluded": errors > MAX_ERRORS,
        "seconds_p50": round(statistics.median(r["seconds"] for r in answered), 2) if n else None,
        # An unreadable bill on any answered call leaves the row unpriced, never free.
        "usd_per_call": round(billed / n, 6) if n and len(bills) == n else None,
        "billed_usd": round(billed, 6),
        "list_usd": candidate["list_usd"],
        "scored_at": datetime.now(UTC).strftime(STAMP),
        "query_results": [{k: v for k, v in r.items() if k != "usd"} for r in rows],
    }


def score_model(candidate: dict, monid: Monid, *, concurrency: int) -> dict:
    def one(item: dict) -> dict:
        try:
            output, usd, seconds = monid.run(
                candidate["provider"], candidate["endpoint"], candidate["request"]["kind"], fill(candidate["request"], item["query"])
            )
        except (urllib.error.URLError, TimeoutError, RuntimeError, KeyError, ValueError, OSError) as exc:
            code = f"http_{exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            return {"id": item["id"], "error": True, "code": code}
        urls = result_urls(output)
        return {"id": item["id"], "error": False, "rr": reciprocal_rank(urls, item["official"]), "results": len(urls), "usd": usd, "seconds": round(seconds, 2)}

    queries = items()["items"]
    first = one(queries[0])
    if not first["error"] and (first["usd"] or 0) > MAX_LIST_USD:
        # A listed price can understate the bill (a $0-listed actor billed $0.07 a call).
        raise RuntimeError(f"billed ${first['usd']} for one call, over the ${MAX_LIST_USD} ceiling")
    with concurrent.futures.ThreadPoolExecutor(concurrency) as pool:
        return summarize(candidate, [first, *pool.map(one, queries[1:])])


def empty_results() -> dict:
    spec = items()
    return {
        "object": "evalrank_web_search_board",
        "schema_version": "1",
        "harness_version": HARNESS_VERSION,
        "metric": "search_score",
        "metric_direction": "higher",
        "limit": LIMIT,
        "item_set_sha256": item_set_sha256(spec),
        "datasets": [{
            "dataset_id": "evalrank-web-search",
            "url": "boards/web-search/items.json",
            "sha256": hashlib.sha256(ITEMS.read_bytes()).hexdigest(),
            "license": spec["license"],
            "attribution": spec["attribution"],
            "items": len(spec["items"]),
        }],
        "updated_at": None,
        "models": [],
    }


IDENTITY = ("item_set_sha256", "harness_version", "limit")


def load_results(path: Path) -> dict:
    fresh = empty_results()
    if not path.exists():
        return fresh
    current = json.loads(path.read_text(encoding="utf-8"))
    return current if all(current.get(key) == fresh[key] for key in IDENTITY) else fresh


def pick(results: dict, found: list[dict], *, now: datetime, max_models: int) -> list[dict]:
    """Never-scored endpoints, excluded ones under ``MAX_ATTEMPTS``, then rows older than
    ``RESCORE_DAYS``, stalest first (search indexes drift, so every row is re-scored)."""
    rows = {r["model"]: r for r in results["models"]}
    new = [
        c for c in found
        if c["model"] not in rows or (rows[c["model"]]["excluded"] and rows[c["model"]].get("attempts", 1) < MAX_ATTEMPTS)
    ]
    cutoff = (now - timedelta(days=RESCORE_DAYS)).strftime(STAMP)
    stale = sorted(
        (c for c in found if c["model"] in rows and c not in new and rows[c["model"]]["scored_at"] < cutoff),
        key=lambda c: rows[c["model"]]["scored_at"],
    )
    todo = new + stale
    return todo[:max_models] if max_models else todo


def merge(results: dict, rows: list[dict]) -> dict:
    by_model = {r["model"]: r for r in results["models"]}
    for row in rows:
        before = by_model.get(row["model"])
        row["attempts"] = before.get("attempts", 1) + 1 if before and before["excluded"] else 1
        by_model[row["model"]] = row
    models = sorted(by_model.values(), key=lambda r: (r["excluded"], -r["score"], r["model"]))
    return {**results, "models": models, "updated_at": datetime.now(UTC).strftime(STAMP)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--results", type=Path, required=True)
    run.add_argument("--max-models", type=int, default=0, help="score at most this many (the weekly cost cap); 0 = every one due")
    run.add_argument("--concurrency", type=int, default=6)
    sub.add_parser("candidates")
    args = parser.parse_args(argv)
    key = os.environ.get("MONID_API_KEY", "")
    if not key:
        print("error: MONID_API_KEY must be set", file=sys.stderr)
        return 2
    monid = Monid(key)
    found = candidates(monid)
    if args.command == "candidates":
        for c in found:
            print(f"{c['model']}\t${c['list_usd']}\t{json.dumps(c['request'])}")
        return 0
    results = load_results(args.results)
    todo = pick(results, found, now=datetime.now(UTC), max_models=args.max_models)
    if not todo:
        print("nothing to score", file=sys.stderr)
        return 0
    for candidate in todo:
        try:
            row = score_model(candidate, monid, concurrency=args.concurrency)
        except Exception as exc:  # noqa: BLE001 - one endpoint's failure never stops the run
            print(f"{candidate['model']}: failed ({type(exc).__name__}: {exc}); not recorded", file=sys.stderr)
            continue
        results = merge(results, [row])
        args.results.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
        print(f"{row['model']}: score={row['score']} errors={row['errors']} p50={row['seconds_p50']}s usd/call={row['usd_per_call']}", file=sys.stderr)
    print(f"{len(results['models'])} endpoints on the board", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
