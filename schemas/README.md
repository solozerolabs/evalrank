# Schemas

Public EvalRank JSON Schema contracts live here.

- `openapi.json` defines the public REST route contract and references the payload schemas below.

- `evalrank-manifest.schema.json` defines Manifest V1 for the canonical public cell, benchmark-family, feed, governance, cadence, lineage, and eligibility inventory in `catalog/manifest.json`.
- `benchmark-research-provenance.schema.json` defines the closed V1 companion contract for dated primary/official family sources and categorized source-backed, owner-attested, or EvalRank-inference claims in `catalog/research-provenance.json`.
- `feed-inventory.schema.json` defines the closed V1 contract for the generated `catalog/feeds.json` join: one row per manifest feed, nesting the exact manifest benchmark-family object, the exact manifest feed object, and the exact family research object by reusing the manifest and research-provenance `$defs`.
- `source-artifact.schema.json` content-addresses replayable upstream bytes and their canonical source coordinates.
- `run-provenance.schema.json` records one closed parser/run envelope with a non-empty role-typed artifact-input set and exactly one `primary`; runtime validators additionally enforce canonical role order and unique artifact IDs.
- `observation.schema.json` defines closed metric and uncertainty unions for one evaluated configuration.
- `configuration-passport.schema.json` pins one resolved manifest identity and reproducible configuration.
- `evaluated-configuration.schema.json` content-addresses a configuration passport.
- `serving-offer.schema.json` separates dated context and availability from effective-dated integer-microusd pricing schedules, including nullable cached-read/storage rates and TTL-qualified cache-write rates.
- `decision-query.schema.json` defines Decision Query V2: three required fields (`schema_version`, `cell_id`, `objective`) and optional `via`, `provider_ids`, `api`, `reasoning_effort` (the comparison level, default `medium`), `regions`, `minimum_context_tokens`, and a closed per-task `usage_profile`.
- `decision-receipt.schema.json` defines Decision Receipt V2: `pick` (ordered `selections`, the pick first and then the priced band, each callable as returned with `model_id`, `reasoning_effort`, and `api`) or `abstain` (`no_ranked_candidate`, `no_eligible_offer`, `stale_evidence`, `not_a_model_cell`), plus the explorer `snapshot_ids`, per-family lock status and weight, `exclusions`, and the priced `usage_profile` with its basis. Ratios are integer parts per million.
- `benchmark-health.schema.json` defines closed per-cell catalog, implementation, admission, publication, and rank-eligibility counts. Runtime projection reports `active` only with a published group, `preview` only with an implemented shadow/active feed, and `unavailable` otherwise.
- `leaderboard.schema.json` defines a cell snapshot set with separate calibrated ranking groups and family-scoped explorer evidence views, plus an optional `positional_consensus` rollup (`lock_weighted_ratio`: entries keyed by the resolved model key, each a 0..1 lock-weighted ratio to the head). Its content-addressed descriptor carries a closed, UTF-16-sorted list of exact `ranking_group_id`/`evidence_snapshot_id` ownership pairs; exact `explorer_<sha256>` evidence requires at least one view, while groups without exact explorer evidence expose an empty view list.
- `entity-detail.schema.json` defines one exact evaluated configuration and ranking projection.
- `compare-result.schema.json` defines a two-to-four configuration comparison on one group scale.
- `capability-fingerprint.schema.json` mirrors `CapabilityFingerprintInput.to_dict()`.
- `raw-entry.schema.json` mirrors `RawEntry.to_dict()`.
- `use-case-catalog.schema.json` mirrors `UseCaseCatalog.to_dict()`.
- `problem.schema.json` pins the RFC 9457 Problem Details error shape and public retry extensions for public route contracts.

Schemas that expose `methodology_version` require `YYYY-MM-DD.SEQ.slug`.

Generated public hashes use 64-character lowercase hex strings.

Observation uncertainty is a closed typed object and decimal measurements remain canonical strings.

Public event timestamp fields use UTC `YYYY-MM-DDTHH:MM:SSZ` strings; private scheduler cadence and runtime refresh policy stay outside the schemas.

Artifact, evaluated-configuration, semantic-query, and receipt identities use the shared restricted RFC 8785 subset: UTF-16 object-key ordering, UTF-8 without whitespace, safe integers, no floats, valid Unicode, and no normalization. Set-valued query fields reject duplicates and serialize sorted.

Projected cost is computed per task from uncached input, cached reads, output, exact-TTL cache writes, and cache-storage token-seconds using integer arithmetic over one common denominator and one final ceiling. A missing rate for any nonzero component leaves the cost null, never a zero-price default. At the comparison level every selection is priced on one usage profile (the caller's, or the stated default agent task mix of 1,000 uncached input, 8,000 cached-read, and 500 output tokens); another effort is priced as that base cost times a measured `effort_multiplier` from a cost family, and an unmeasured one carries `cost_unmeasured`. Pick ordering (cheapest under `lowest_cost_within_top_set`, highest ratio under `capability_top_set`), pinned-effort, `api`, and `provider_ids` binding, caveat truth, the usage echo, and the receipt hash are enforced by the Python and TypeScript semantic validators where JSON Schema cannot express them. A `via` without a probed effort vocabulary is a `422` `via_not_supported` problem, never a receipt.

Manifest identity triples are one of five explicit versioned resolved combinations (model, agent, system, component, or arena) or exactly `unresolved`/`unresolved`/`unresolved-v1`; mixed or invented combinations are invalid. Unresolved identities must be explorer-only, and resolved identities may also be explorer-only when the evidence policy cannot support a top set. Every explorer ceiling keeps top-set, winner, superiority, practical-effect, and leave-one-family-out fields null; active groups must use the single-winner-capable policy. Discovery keeps adapter IDs, metric direction, rank counts, cadence thresholds, and task/environment/grader lineage IDs null. Shadow feeds require an adapter and an explicit higher/lower native-metric direction while rank-eligible counts remain null. Active feeds additionally require a positive rank count, approved rights, validated ordered cadence, validated lineage, and a validated correlation group; active ranking groups require calibrated evidence, a positive rank count, and enough independently counted active families for their top-set gate. Quarantine requires an explicit reason and null rank count, while non-quarantined records keep the reason null. A family may expose multiple feeds, but feeds sharing a declared correlation group count once.

`npm run test --prefix packages/sdk-ts` compiles the manifest schema with Ajv's Draft 2020-12 implementation, validates the canonical manifest, and mutation-tests the closed identity, cadence, lineage, correlation, quarantine, and admission branches. `tests/test_catalog_manifest.py` guards cross-record cell, family, feed, ranking-group, and independent-family joins that JSON Schema cannot express.

`tests/test_catalog_research_provenance.py` validates the research companion with Ajv's Draft 2020-12 implementation and guards exact manifest-version/family coverage, dated HTTPS source references, claim-source joins, direct-versus-inference categorization, and exact research-flag linkage. Research sources do not establish runtime lineage, rights, or admission.

`tests/test_catalog_feed_inventory.py` validates the generated `catalog/feeds.json` against the closed feed-inventory schema with Ajv (adding the manifest and research schemas so the reused `$defs` resolve) and guards exact row count/order/object equality, missing/duplicate research, one compact physical line per feed, and stale/missing/hand-edited `--check` failure. `catalog/feeds.json` is generated by `scripts/export_catalog_feeds.py`; never hand-edit it.

Core contract tests also guard public string fields that JSON Schema already constrains; those values must be actual non-empty strings before serialization.

Observation schemas never duplicate mutable source URLs or hashes inside run provenance. They preserve proportion, continuous, pass-at-k, pairwise-preference, and rank-only evidence without coercing unlike metrics onto one scale. Unknown, standard-error, and interval uncertainty remain explicit.

Use case catalog schemas expose public taxonomy metadata: slugs, names, one-line definitions, entity-kind spans, and rank policy. The canonical cell inventory and calibrated-gate policy live in `catalog/manifest.json`; evidence synthesis lives in `methods/evidence-synthesis.md`. Private observations and persistence semantics stay outside this repo.

Problem Details schemas intentionally allow extension members. Public extensions are limited to `code`, `retriable`, `retry_after`, `field`, `request_id`, `doc_url`, and `supported_via` (on `via_not_supported`); optional `doc_url` values are public HTTP(S) URLs. Private problem types, hosted error internals, auth context, and tenant details stay outside this repo.

The OpenAPI contract contains exactly seven launch paths: taxonomy, grouped leaderboard/entity/compare reads, benchmark health, deterministic decision creation, and explicitly shared receipt retrieval. It reuses response components for malformed requests, unsupported media, validation errors (decision creation adds `via_not_supported`), not-found reads, rate limits, temporary unavailability, and upstream timeouts. `429` responses expose `Retry-After`, `RateLimit`, and `RateLimit-Policy` header contracts; the repo does not implement live throttling.

Run:

```sh
python3 -m unittest tests.test_schema_contracts tests.test_openapi_contract
```
