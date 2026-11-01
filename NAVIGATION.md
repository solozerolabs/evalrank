# EvalRank Navigation

The public API has exactly seven launch paths. `schemas/openapi.json` is authoritative; `scripts/reference_server.py` is the storage-free local exerciser.

| Route | Contract |
| --- | --- |
| `GET /v1/use-cases` | Public taxonomy. |
| `GET /v1/leaderboard/{use_case}` | One content-addressed cell snapshot set with separate ranking-group scales. |
| `GET /v1/entities/{entity_type}/{slug}` | One exact evaluated configuration pinned to its evidence snapshot; explorer reads may select an immutable benchmark-family/feed view. |
| `GET /v1/compare` | Two to four configurations within one ranking-group evidence snapshot and, for explorer evidence, one selected benchmark-family/feed view. |
| `GET /v1/benchmark-health` | Per-cell catalog, admission, publication, and rank-eligibility counts. |
| `POST /v1/decisions` | Closed `DecisionQueryV2` to a deterministic `DecisionReceiptV2` (pick or abstain; `422 via_not_supported` for an unprobed `via`); optional `?share=true` retains the receipt. |
| `GET /v1/decisions/{receipt_id}` | Exact retrieval of an explicitly shared immutable receipt. |

The old scoring-stage and recommendation paths do not exist and must return `404` in the reference server and hosted implementation.

Run `python3 -m unittest tests.test_openapi_contract tests.test_reference_server_e2e` after route changes.
