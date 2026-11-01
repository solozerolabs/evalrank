# Evidence Synthesis Method

## Status

The current public output is a **provisional aggregate**. It is useful for contract and replay work, but it is not a calibrated winner claim. A ranking group remains preview-only until its thresholds are calibrated on versioned historical holdouts and its evidence clears the manifest gates.

## Unit Of Comparison

Evidence is grouped first by the exact ranking group:

`(cell_id, entity_kind, interaction_policy, configuration_passport_class)`

Only evaluated configurations that satisfy that same key are comparable. A model configuration and an agent system never share a scale merely because they address the same cell. Missing configuration-passport fields exclude a row from ranking and remain visible as a disclosed evidence gap.

## Native Metric Families

Each benchmark family keeps its native observation model. Examples include item-level binary or categorical outcomes, bounded or continuous task scores, time-to-event outcomes, and crowd-pairwise preferences. The synthesis layer models the native metric and its sampling unit; it does not turn an aggregate percentage into invented Bernoulli trials or treat competitor count as task count.

Task, environment, grader, translation, suite, mirror, and rerun lineage determine independence. Multiple feeds over the same task lineage belong to one correlated-family group unless an admission report proves new independent decision information.

## Staged Eligibility

Eligibility is evaluated for each exact ranking group, never for a cell in aggregate.

- **Explorer:** at least one usable family may support a labeled evidence view, never a winner claim.
- **Top set:** at least three independent calibrated families plus the configured overlap, coverage, practical-effect, freshness, replay, and rights gates.
- **Single winner:** at least four independent calibrated families, the stricter overlap gate, calibrated bootstrap superiority above the configured threshold, a calibrated native practical effect, and leave-one-family-out stability.

The numeric policy in `catalog/manifest.json` begins `unvalidated`. Changing a constant cannot activate a group; calibration evidence and an admission record are required.

A resolved identity may still be explorer-only when the available families do not justify a top-set policy. Explorer-only groups keep top-set, winner, superiority, practical-effect, and leave-one-family-out fields null and cannot become `active`. CORE-Bench mainline and out-of-distribution feeds are declared correlated views of one family and therefore contribute at most one independent-family unit.

Evaluator validation is a separate future calibration layer. JudgeBench, RewardBench 2, or similar judge-focused suites may test grader reliability, but they do not measure the capability being ranked and never enter capability-family counts.

Cost families are not capability evidence either. A cost family, such as the Artificial Analysis cost per Intelligence Index task, records what one model configuration at a named reasoning effort spends to run a fixed suite. It binds no cell and no ranking group, carries a lower-is-better native metric, never ranks a configuration, and never enters capability-family counts. Its role is measured per-effort cost multipliers: cost per task at an effort divided by cost per task at medium for the same model on the same board.

## Top Sets And Tie Groups

The default publishable result is a top set. Configurations whose supported native effects do not clear the calibrated practical difference form a **tie group**. The receipt explains the group and may let user constraints choose among tied configurations without rewriting capability evidence.

A single-winner label is exceptional. It is withheld whenever the top identity changes under required leave-one-family-out analysis, the superiority threshold is missed, the practical effect is not meaningful, or exact overlap is insufficient.

## Uncertainty And Sensitivity

Uncertainty is derived from the source's real sampling unit. The baseline resamples whole paired **exact benchmark-version and lineage blocks** jointly across configurations, then gives each independent family equal total influence. It never invents a Gaussian likelihood from a reported standard error. Reported standard errors and intervals remain in native-unit practical-effect gates. When retained evidence has no raw task blocks, the result is labeled a family/version-block bootstrap rather than claiming within-task resampling.

Before any bootstrap output exists, the implementation constructs this exact aggregation document:

```json
{
  "admission_cohort_digest": "<64 lowercase hex>",
  "calibration_report_id": "calibration_<64 lowercase hex>",
  "methodology_version": "<non-empty string>",
  "observation_ids": ["obs_<64 lowercase hex>", "..."],
  "ranking_group": ["cell_id", "entity_kind", "interaction_policy", "configuration_passport_class"]
}
```

`observation_ids` is a non-empty semantic set supplied after admission and identical-mirror dedupe. Caller order is irrelevant: the public helper rejects invalid or duplicate IDs and sorts the unique IDs lexicographically into the preimage. Identical variants within one exact block and evaluated configuration must collapse upstream to one semantic observation identity; a content conflict quarantines that block instead of perturbing the seed.

The aggregation input digest is `sha256(restricted_jcs(aggregation_document))`. The seed document is exactly `{"aggregation_input_digest": "<64 lowercase hex>", "methodology_version": "<same non-empty string>"}`. Its restricted-JCS SHA-256 digest is converted to the bootstrap seed by reading the first eight bytes as one big-endian unsigned integer and applying `& 9007199254740991`. The final publication snapshot hashes the completed result, so bootstrap output never participates in its own seed.

Every publishable result records sensitivity to:

- leaving out each independent family;
- alternate allowed native-effect specifications;
- missing evaluated configurations;
- task/environment/grader lineage groups;
- freshness and rights exclusions.

Possible ceiling pressure is a research flag. It becomes an admission decision only after dated top-cohort spread, sample size, uncertainty, reproduction, and marginal discrimination are measured.

## Challenger Promotion

The published baseline remains active while a challenger is evaluated. A challenger can replace it only after the same versioned holdouts show calibrated coverage, stable top or tie sets, nominal uncertainty behavior, leave-one-family-out stability, and no degradation of abstention correctness. Failed promotion cannot mutate the active publication.

## Publication Rule

An immutable source artifact produces typed native observations, then a versioned synthesis candidate, then an immutable publication snapshot. Publication is a compare-and-swap of the active pointer only after every gate passes. Partial refresh failure retains the last-known-good snapshot and reports the failed family; it never silently republishes reduced coverage.

Safety vetoes, rights restrictions, stale evidence, invalid identity, and missing offer links remain explicit exclusions or abstentions. They are not hidden as score penalties.
