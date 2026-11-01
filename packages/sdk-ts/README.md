# EvalRank TypeScript SDK

Native-fetch TypeScript client and portable contract boundary.

Package metadata:

- Package: `@evalrank/sdk`
- Type: `module`
- Types: `./src/index.ts`
- License: `Apache-2.0`
- Publish status: `private`

## Public Surface

- `DecisionQueryV2` and `DecisionReceiptV2` provide the closed semantic query and content-addressed receipt contracts: a `pick` (ordered selections, each callable as returned with `model_id`, `reasoning_effort`, and `api`) or an `abstain` with reasons. `resolvedVia`, `SUPPORTED_VIA`, `DEFAULT_AGENT_TASK_MIX`, and `projectedCostMicrousd` mirror the Python core.
- `BenchmarkHealth`, `Leaderboard`, `ExplorerEvidenceView`, `ExplorerViewIdentity`, `EntityDetail`, and `CompareResult` type launch reads, immutable family/feed selectors, and truthful evidence snapshot identity.
- `EvalRankClient` covers `useCases`, `benchmarkHealth`, `leaderboard`, `entity`, `compare`, `decide`, and `decisionReceipt`.
- Read methods verify benchmark-health counts/status, leaderboard snapshots, entity details, and comparisons; decision methods validate the query and receipt hash.
- `ProblemDetails`, `EvalRankApiError`, `PUBLIC_FIXTURE_KINDS`, and `PublicFixtureKind` mirror the public error and fixture vocabulary.
- `AggregationInputDocument`, `BootstrapSeedDocument`, `RankingGroupIdentity`, `aggregationInputDocument`, `deriveAggregationInputDigest`, `bootstrapSeedDocument`, and `deriveBootstrapSeed` share the restricted-JCS identity domain with Python.
- Independent ingestion primitives `CapabilityFingerprint`, `RawEntry`, and `ObservationV1` remain portable; obsolete recommendation-stage DTOs are absent.

There are no recommendation or scoring-stage client methods or response aliases.

## Example

```ts
import { EvalRankClient, type DecisionQueryV2 } from "@evalrank/sdk";

const query: DecisionQueryV2 = JSON.parse(await Bun.file("query.json").text());
const client = new EvalRankClient("https://evalrank.example");
const receipt = await client.decide(query, { share: true });
const replayed = await client.decisionReceipt(receipt.receipt_id);
const health = await client.benchmarkHealth();
```

The client sends no auth, installation identity, retries, service discovery, environment defaults, or private data.

## Check

```sh
npm ci --prefix packages/sdk-ts
npm run check --prefix packages/sdk-ts
npm run test --prefix packages/sdk-ts
```

Ajv is a lockfile-pinned test dependency only; it is not part of the runtime surface.
