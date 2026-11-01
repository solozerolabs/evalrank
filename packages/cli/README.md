# EvalRank CLI

Scriptable command-line boundary for public EvalRank workflows.

Package metadata:

- Distribution: `evalrank-cli`
- Import: `evalrank_cli`
- Entrypoint: `evalrank`
- Runtime dependencies: `evalrank-core==0.0.0`, `evalrank-sdk==0.0.0`
- License: `Apache-2.0`

Fixture commands:

```sh
evalrank fixture fingerprint
evalrank fixture raw-entry
evalrank fixture problem
evalrank fixture observation
evalrank fixture use-cases
```

The fixture commands are deterministic and perform no network or database work.

Launch API commands:

```sh
evalrank use-cases --base-url https://evalrank.example
evalrank benchmark-health --base-url https://evalrank.example
evalrank decide --base-url https://evalrank.example --query query.json
evalrank decide --base-url https://evalrank.example --query - --share
evalrank receipt --base-url https://evalrank.example --receipt-id receipt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

`decide` validates `DecisionQueryV2` before posting. `--share` is explicit transport policy: it asks the server to retain an append-only public receipt that anyone with its ID can retrieve. Successful JSON goes to stdout, RFC 9457 Problem Details goes to stderr, contract/input errors exit `2`, and API errors exit `1`.

There are no `recommend` or `scoring-stages` compatibility commands. The CLI adds no auth, retries, service discovery, environment defaults, private DTOs, or database work.
