# EvalRank Python SDK

Dependency-light Python client and public contract re-export boundary.

Package metadata:

- Distribution: `evalrank-sdk`
- Import: `evalrank_sdk`
- Runtime dependency: `evalrank-core==0.0.0`
- License: `Apache-2.0`

The SDK re-exports the portable core, including `CapabilityFingerprintInput`, `RawEntry`, `ObservationV1`, `DecisionQueryV2`, `DecisionReceiptV2`, `UseCaseCatalog`, `ProblemDetails`, `PROBLEM_CODES`, `PUBLIC_FIXTURE_KINDS`, and `sample_public_fixture`. Identity helpers such as `aggregation_input_document`, `derive_aggregation_input_digest`, `bootstrap_seed_document`, and `derive_bootstrap_seed` are the exact `evalrank_core` implementations, not forks.

`EvalRankClient` and `EvalRankApiError` cover all seven launch routes:

- `use_cases()` and `benchmark_health()`
- `leaderboard(use_case)`, `entity(entity_type, slug, explorer_view=(family_id, feed_id))`, and `compare(use_case, entities, explorer_view=(family_id, feed_id))` with closed-shape semantic verification
- `decide(query, share=False)` with local `DecisionQueryV2` validation and `DecisionReceiptV2` hash verification
- `decision_receipt(receipt_id)` for an explicitly shared immutable receipt

There are no `recommend` or `scoring_stages` compatibility methods.

```python
import json
from evalrank_sdk import EvalRankClient

client = EvalRankClient("https://evalrank.example")
query = json.load(open("query.json", encoding="utf-8"))
receipt = client.decide(query)
shared = client.decide(query, share=True)
replayed = client.decision_receipt(shared["receipt_id"])
health = client.benchmark_health()
```

The client accepts only explicit HTTP(S) base URLs and sends no auth, installation identity, retries, service discovery, environment defaults, or private DTOs.
