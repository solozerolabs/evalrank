# EvalRank Tests

## Default Check

```sh
make check
```

## Test Map

- `tests/test_core_contracts.py` checks the independent discovery contracts, pinned and fail-closed use-case taxonomy envelope, strict extension-preserving Problem Details decoding, shared URI vectors, and complete absence of superseded request/recommendation/stage/ranked DTOs.
- `tests/test_decision_contracts.py` checks immutable source/run provenance including sorted unique role-typed multi-artifact inputs, the five native observation metric kinds, explicit uncertainty, resolved configuration passports, effective-dated serving-offer pricing schedules, exact-TTL monthly cost with one ceiling, fail-closed missing rates, evidence-basis offer links, measured/estimated usage, baseline and zero-cache projected costs, cross-profile hard budgets, required cost-sensitivity caveats, semantic query normalization, and deterministic full-body receipt identities.
- `tests/test_canonical_json.py` checks the restricted cross-language canonical JSON/hash domain plus shared Python/TypeScript aggregation-document, observation-set normalization, digest, seed-preimage, and safe-integer-mask parity from `catalog/aggregation-vectors.json`, with fail-closed rejection coverage.
- `tests/test_catalog_manifest.py` checks the canonical 28-cell taxonomy, exact 103-family/115-feed inventory, absence of retired aliases, unique cell/ranking-group/family/feed IDs, preview/discovery/shadow/quarantine truth, explicit native-metric direction for implemented feeds, coherent identity triples, resolved explorer ceilings, exact research-job mappings, shared-family and cross-family correlation (including the uncalibrated GitHub-issue SWE lineage), fail-closed admission states, independently counted active-family gates, cross-record links, rights/retention completeness, closed schema surface, and exact core-fixture projection.
- `tests/test_catalog_research_provenance.py` validates the closed Draft 2020-12 research-provenance companion with Ajv and checks exact manifest-version/family coverage, dated primary or official HTTPS sources, published-source, owner-attestation, and inference claim categorization, claim-source joins, one exact linked claim for every manifest research flag, and attributable evidence for every asserted approved right independently from separately published license metadata.
- `tests/test_catalog_feed_inventory.py` checks the generated `catalog/feeds.json` join: exact per-feed row count/order and manifest-family/feed/research object equality, missing/duplicate research and unknown-family failures, faithful copy of research flags, quarantines, arrays, duplicate source kinds, and `=`-bearing URLs, one compact physical line per feed, closed Ajv-validated schema reusing the manifest and research `$defs`, and stale/missing/hand-edited `--check` failure.
- `tests/test_core_fixtures.py` checks exact discovery/observation/problem/taxonomy fixture dispatch and proves retired recommendation-stage fixture kinds are absent.
- `tests/test_examples.py` checks the runnable public fixture bundle and the shared `DecisionQueryV1`/`DecisionReceiptV1` golden documentation.
- `tests/test_cli_fixture.py` checks deterministic fixtures, use-case/health reads, validated decision file/stdin submission, explicit share, shared-receipt retrieval, exit codes, and Problem Details.
- `tests/test_mcp_fixture.py` checks exact tool discovery, closed decision input, host-owned endpoint configuration, share/receipt semantics, metadata reads, golden receipt parity, and MCP error projection.
- `tests/test_package_metadata.py` checks public Python package `pyproject.toml` names, versions, licenses, Python floor, dependencies, CLI entrypoint, TypeScript package metadata, and exact package README metadata drift.
- `tests/test_schema_contracts.py` checks exact schema inventory, deleted recommendation-stage schemas, discovery hash contracts, taxonomy enums, Draft 2020-12, RFC 9457 Problem Details, and schema README drift.
- `tests/test_public_read_schemas.py` compiles and mutation-tests grouped leaderboard, family-scoped explorer views, entity detail, and same-group compare contracts, including empty no-evidence previews and fail-closed explorer top-set claims.
- `tests/test_read_contracts.py` verifies benchmark-health count/status truth, float-free snapshot-set identities, exact ranking-group/evidence-snapshot ownership (including swap rejection), closed runtime wire shapes, state/snapshot-prefix parity, per-view ranking and citation integrity, derived cross-view agreement, freshness truth, immutable explorer-view selection, eligibility-gap truth, interval ordering, and top-set ceilings.
- `tests/test_openapi_contract.py` checks the exact seven-path launch map, decision/share/receipt operations, reusable Problem Details responses, schema refs, deleted routes, and storage-free boundary.
- `tests/test_reference_server_e2e.py` drives raw HTTP, Python SDK, CLI, and MCP through the stdlib server; validates schema-valid family-scoped explorer reads and evidence snapshot identity, canonical golden receipt bytes, non-share invisibility, append-only sharing, and deleted-route `404`s.
- `tests/test_methods_docs.py` checks exact method README note coverage and verifies public method notes stay aligned with the use-case taxonomy, native-metric evidence synthesis, and staged eligibility.
- `tests/test_repo_docs.py` checks `CLAUDE.md` stays a one-line `@AGENTS.md` shim, scoped `AGENTS.md` files cover public work areas, `docs/REPO_STRUCTURE.md` tracks the public top-level directories and package directories exactly, status and test-map catalog counts/date follow the canonical manifest, `docs/STATUS.md` points to the canonical public authorities without traces of the separate private system, `docs/STATUS.md` mentions every current porting workstream from `docs/PORTING.md`, and public MCP docs do not advertise private evidence lookup.
- `tests/test_sdk_python.py` checks portable re-exports and validates decision/receipt/health clients, strict use-case response parsing, bounded request timeouts, strict receipt IDs, canonical request bytes, response hash verification, Problem Details, and absence of compatibility methods.
- `tests/test_sdk_ts.py` checks package metadata, mirrored public constants, launch read/decision types, fail-closed use-case parsing, all seven client paths, semantic verifiers, and absence of retired route vocabulary.
- `tests/test_public_boundary.py` checks repository boundary rules and CLI failure output.
- `scripts/check_public_boundary.py` rejects private imports, disallowed coupling, excluded implementation markers, secret files, high-signal secret values, private data paths, and missing package license/notice files.

## Package Checks

- TypeScript SDK syntax check: `npm run check --prefix packages/sdk-ts`
- Locked TypeScript test install: `npm ci --prefix packages/sdk-ts` installs the exact dev dependency graph from `packages/sdk-ts/package-lock.json` without changing the lock.
- TypeScript SDK runtime test: `npm run test --prefix packages/sdk-ts` runs the client/catalog suite plus the cross-language restricted-JCS aggregation identity, provenance, observation, configuration, offer-link, receipt, pair-owned evidence snapshot-set, explorer claim-ceiling, read-semantic parity, and Draft 2020-12 suite.
- Public fixture example smoke check: `python3 examples/public_fixture.py`

## Update Rules

- Add or update tests with every non-trivial contract, parser, CLI, MCP, SDK, schema, or boundary change.
- Keep test fixtures public and minimal. Do not copy private fixtures, held-out eval data, customer data, or telemetry into this repo; runtime persistence and hosted operation are maintained in a separate private system.
- If UI routes, API routes, or deeplinks come online, add `NAVIGATION.md` with route entrypoints and regression commands.
