# EvalRank

EvalRank is a public, product-neutral truth and decision contract for comparing exact model or agent configurations with reproducible evidence. It separates benchmark exploration from publishable claims and returns typed, content-addressed decision receipts instead of opaque recommendations.

## Repository Layout

- `catalog/` — canonical cells, ranking groups, benchmark families, feeds, rights, cadence, lineage, retention, and eligibility.
- `methods/` — native-metric evidence synthesis and publication rules.
- `schemas/` — JSON Schemas and the public OpenAPI contract.
- `packages/core` — portable Python contracts, canonical identities, and semantic verifiers.
- `packages/sdk-python` and `packages/sdk-ts` — dependency-light clients.
- `packages/cli` and `packages/mcp` — scriptable adapters.
- `scripts/reference_server.py` — stdlib-only synthetic HTTP contract exerciser.
- `examples/` — public fixtures and the cross-language decision golden.
- `docs/STATUS.md`, `docs/PRODUCT.md`, and `docs/PORTING.md` — current product and ownership state.

## Public API Contract

`schemas/openapi.json` owns exactly seven launch paths:

- `GET /v1/use-cases`
- `GET /v1/leaderboard/{use_case}`
- `GET /v1/entities/{entity_type}/{slug}`
- `GET /v1/compare`
- `GET /v1/benchmark-health`
- `POST /v1/decisions`
- `GET /v1/decisions/{receipt_id}`

`POST /v1/decisions` accepts only `DecisionQueryV2`; three fields are a complete query: `{"schema_version":"2","cell_id":"writing","objective":"lowest_cost_within_top_set","provider_ids":["openai"]}`. A supplied usage profile must describe non-zero work; without one the receipt states the default agent task mix it priced. The optional `?share=true` parameter is transport policy, not query semantics: it retains an append-only public-safe receipt that anyone with the ID can retrieve. A non-shared result is returned but is not retrievable. `DecisionReceiptV2` is a 200 in one of two shapes: a `pick` (ordered selections, the pick first and then the priced band, each callable as returned with `model_id`, `reasoning_effort`, and `api`) or an `abstain` with machine-readable reasons. A `via` without a probed effort vocabulary is a `422 via_not_supported`; `503` means an outage, never missing evidence. The receipt ID hashes the full restricted-JCS body.

There are no recommendation or scoring-stage route aliases. Legacy paths return `404` in the reference server.

## Local Contract Exerciser

The stdlib reference server validates the complete query, exposes schema-valid synthetic reads for all launch GET shapes, and returns the exact golden receipt only for its published synthetic queries.

```sh
PYTHONPATH=packages/core/src python3 scripts/reference_server.py --port 8000
```

Use `examples/decision-contract-v2.golden.json` as the request/receipt reference and run:

```sh
python3 -m unittest tests.test_reference_server_e2e
```

## Portable Clients

```python
import json
from evalrank_sdk import EvalRankClient

client = EvalRankClient("http://127.0.0.1:8000")
query = json.load(open("query.json", encoding="utf-8"))
receipt = client.decide(query, share=True)
assert client.decision_receipt(receipt["receipt_id"]) == receipt
```

```sh
evalrank use-cases --base-url http://127.0.0.1:8000
evalrank benchmark-health --base-url http://127.0.0.1:8000
evalrank decide --base-url http://127.0.0.1:8000 --query query.json --share
evalrank receipt --base-url http://127.0.0.1:8000 --receipt-id receipt_...
```

Fixture commands remain available for ingestion and evidence primitives, but recommendation and scoring-stage fixture kinds are retired.

## Public/Private Boundary

The hosted runtime, persistence, scheduler, private source adapters, held-out evals, customer data, telemetry, credentials, deployment configuration, and proprietary experiments stay outside this Apache-2.0 repo. Runtime persistence and hosted operation are maintained in a separate private system. A private runtime must pin an immutable public EvalRank revision and may not fork the taxonomy or wire contract.

## Verification

```sh
make check
```

The gate runs the public-boundary scanner, Python suites, TypeScript syntax/runtime suites, schema drift checks, and cross-client reference-server E2E without network access or private credentials.
