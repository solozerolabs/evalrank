# EvalRank Core

Reference Python package for public EvalRank evidence, read, and decision contracts.

Package metadata:

- Distribution: `evalrank-core`
- Import: `evalrank_core`
- License: `Apache-2.0`

Use `evalrank_core.fixtures.sample_public_fixture(kind)` with `PUBLIC_FIXTURE_KINDS`, or individual fixture helpers such as `sample_problem_details()`, for public examples and contract tests.

`RunProvenanceV1` carries a sorted tuple of `RunInputArtifactV1` values with stable roles and exactly one `primary`. This records every retained parser input directly; multi-file upstream releases never hide auxiliary bytes in mutable adapter metadata.

Public contract surface: `CapabilityFingerprintInput`, `RawEntry`, `SourceArtifactV1`, `RunProvenanceV1`, `ObservationV1`, `ConfigurationPassportV1`, `EvaluatedConfigurationV1`, `UsageProfileV1`, `PricingScheduleFactV1`, `ServingOfferV1`, `DecisionQueryV2`, `DecisionReceiptV2`, `RankingGroupSnapshotRefV1`, `SnapshotSetDescriptorV1`, `UseCaseCatalog`, and `ProblemDetails`. `projected_cost_microusd` prices a usage profile against exact TTL-qualified schedule rows with integer arithmetic and one final ceiling; it returns `None` whenever a nonzero component lacks a rate. `DecisionReceiptV2.create` builds a pick (ordered selections: the pick, then the priced band, each with its explicit `reasoning_effort`, `api`, price, `effort_multiplier`, and caveats) or an abstain with reasons, echoes the priced usage profile (the caller's or `DEFAULT_AGENT_TASK_MIX`), and content-addresses the body. `SUPPORTED_VIA` lists the call surfaces with a probed effort vocabulary. `canonical_json`, `restricted_jcs`, and `sha256_hex` implement the restricted cross-language hash domain. A snapshot-set descriptor hashes the UTF-16-sorted, one-to-one `ranking_group_id`/`evidence_snapshot_id` ownership pairs, where evidence identity is either `snapshot_<sha256>` or `explorer_<sha256>`; the read verifiers reject pair swaps, duplicate identities, invalid ranks or intervals, false eligibility gaps, and top-set claims inside explorer views.

`aggregation_input_document` and `derive_aggregation_input_digest` validate the portable aggregation inputs, canonicalize the semantic observation-ID set, and bind the exact ordered ranking-group tuple. `bootstrap_seed_document` and `derive_bootstrap_seed` expose the corresponding restricted-JCS seed preimage and JavaScript-safe deterministic seed. The helpers add no scorer, persistence, or private benchmark behavior.

Capability fingerprint and raw entry public string fields must be actual non-empty strings. They are discovery inputs only and never ranking or publication truth.

Observations separate immutable source bytes, typed run provenance, exact evaluated-configuration identity, metric kind, counts, and uncertainty. Decimal measurements are canonical strings; counts are safe integers. Mutable URLs and untyped provenance maps are not accepted.

Use case catalog payloads expose public taxonomy metadata only. Benchmark weights, IRT clusters, confidence policy, synthesis rules, and storage tables stay outside this package.

Public `methodology_version` values use calendar-valid `YYYY-MM-DD.SEQ.slug`, for example `2026-06-25.1.public-fixture-v1`.

Public event timestamps use UTC `YYYY-MM-DDTHH:MM:SSZ` strings for generated, fetched, and observed timestamps.

Problem Details payloads expose the public RFC 9457 error shape plus retry-safe public extensions. Optional `doc_url` values must be public HTTP(S) URLs. Private problem types, tenant context, hosted internals, and production telemetry stay outside this package.
