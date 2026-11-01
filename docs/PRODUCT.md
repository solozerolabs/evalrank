# EvalRank Product Contract

## User Job

EvalRank helps a person choose what to use for a concrete AI workload. A useful answer names the evaluated configuration, explains the evidence and uncertainty, applies the person's constraints, and says when the evidence is too weak to decide.

EvalRank is a decision system, not a generic leaderboard. The primary interaction is a structured question followed by a reproducible decision receipt. Browsable catalog and comparison views help discovery, but they never imply that every catalog cell has a publishable ranking.

## Product Promise

For a versioned query, EvalRank should answer:

1. Which comparable evaluated configurations form the supported top set?
2. What evidence, uncertainty, freshness, and sensitivity support that set?
3. Which constraints or missing facts change the answer?
4. Can an evaluated configuration be linked exactly to an available serving offer?
5. If the evidence cannot support the requested claim, why did EvalRank abstain?

Accuracy and honest uncertainty outrank breadth. Cost-aware advice follows only after evidence quality; latency and implementation cost do not justify a false comparison.

## Entity Ontology

An **evaluated configuration** is the indivisible subject of a result. Its configuration passport identifies the model or system, version, harness, tools, scaffold, prompting or interaction policy, environment, and other settings needed to reproduce the measurement. Results from different passports are not silently collapsed into a bare model or product name.

Rankings never pool unlike evidence: each **ranking group** is one exact

`(cell_id, entity_kind, interaction_policy, configuration_passport_class)`

A decision asks for one cell. It ranks that cell's model configurations (a model at a named reasoning effort) from the lock-admitted families of its explorer evidence, compares them like-for-like at one comparison level (`medium` by default), and answers with a callable pick or an abstain. A cell whose admitted families are all agent systems abstains with `not_a_model_cell`; recommending model-plus-harness systems is a separate product.

The public entity kinds exposed by the use-case catalog remain model, tool, and agent. Benchmark-family and feed records use more exact configuration kinds so model configurations, agent systems, retrieval components, end-to-end systems, and crowd-pairwise systems cannot be pooled accidentally.

A **ServingOffer** is a separately dated, provider-specific purchasable or runnable offer. A decision joins ranked configurations to live offers at read time, per call surface (`via`): the receipt returns the host-native `model_id`, the `reasoning_effort` to send, and the `api` shape, so a caller never re-maps names, re-prices offers, or guesses an effort. An effort the host cannot accept, or a host whose effort vocabulary was never probed, is excluded or refused (`422 via_not_supported`), never guessed.

## Catalog And Publication

[`catalog/manifest.json`](../catalog/manifest.json) is the canonical public registry for cells, candidate benchmark families, feeds, explicit higher/lower native-metric direction, rights state, cadence, retention policy, lineage, and publication eligibility. It contains exactly 28 canonical cells and no compatibility aliases. Every cell begins in `preview`; research leads remain `discovered` until a dated successful exact-byte parse, then `shadow` until publication gates pass. `shadow` is that dated parser evidence only: it is not durable replay and implies no retention, scheduling, or publication.

[`catalog/feeds.json`](../catalog/feeds.json) is a generated, non-normative join that pairs each manifest feed, in order, with its exact benchmark-family, feed, and research objects. It is produced by `scripts/export_catalog_feeds.py --write` and adds no facts beyond the manifest and its research companion.

Catalog membership means “EvalRank understands this decision question.” It does not mean the cell is ranked, launch-ready, or supported by enough independent evidence. A publication snapshot may expose a top set only after the exact ranking group clears rights, identity, overlap, health, calibration, freshness, replay, and sensitivity gates. Thin cells disclose the missing-family gap instead of emitting a thin ranking.

Professional deliverable creation, machine-learning engineering, and computational research reproduction are separate preview research jobs because their task units and evaluated configurations do not match a domain aggregate, generic software engineering, deep research, or terminal operations. GDPval is not projected into legal, finance, medical, or support cells; MLE-bench is not projected into software engineering; and PaperBench or CORE-Bench is not projected into deep research or DevOps. These hypotheses are explorer-only until additional independent evidence and calibration justify a stronger claim.

Safety and robustness are a cross-cutting safety veto and disclosure layer, not a 27th ranking cell. A safety condition can exclude or qualify a candidate without being averaged into task capability. Evaluator validation is also a separate calibration concern: evaluator-focused suites such as JudgeBench or RewardBench 2 may later validate graders, but they are not capability families and cannot inflate capability-family counts.

## Receipt UX

A decision receipt keeps the complete typed query, the explorer snapshots it ranked, each family's lock status, weight, and staleness, the ordered selections (the pick first, then the priced band, each with its capability ratio, family coverage, price, effort multiplier, projected cost, latency, and caveats), exclusions with reasons, the priced usage profile and its basis, and any abstain reasons. It should remain interpretable without private runtime context.

The default decision response is ephemeral. A public share receipt exists only after an explicit share action and contains no free-form private prompt. The interface must state that anyone with the link can view it. New evidence must not change an existing receipt.

## Demand Gates

Demand evidence prioritizes research and interface work; it never weakens evidence eligibility. Structured, consented research sessions and auditable product interactions may change which preview cell is investigated next. They do not make a family independent, grant redistribution rights, repair identity, or promote a ranking group.

There is no predeclared launch cell. Each ranking group earns publication independently through the method in [`methods/evidence-synthesis.md`](../methods/evidence-synthesis.md).

## Explicit Exclusions

The public core does not contain customer data, private prompts, proprietary task banks, answer keys, production telemetry, credentials, private persistence layouts, or hosted control-plane behavior. The initial product does not run arbitrary user-supplied evaluations, promise medical/legal/financial advice, or infer a purchasable offer from a model name.

EvalRank does not:

- manufacture item-level trials from aggregate benchmark scores;
- pool model and agent evidence or count reruns of one task lineage as independent families;
- publish a winner from an uncalibrated threshold or a single benchmark family;
- treat possible benchmark saturation as fact without dated discrimination evidence;
- hide stale, missing, quarantined, or rights-blocked evidence behind a generic score;
- treat catalog breadth as product readiness.

## Authority

This document defines the product. The manifest defines the inventory and gates. The evidence-synthesis note defines the public method. Older build logs are historical context and are non-normative when they conflict with these three authorities.
