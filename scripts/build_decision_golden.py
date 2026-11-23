"""Build the shared decision golden, examples/decision-contract-v2.golden.json, from the core contracts.

Every receipt is built through ``DecisionReceiptV2.create`` so its body and id are the contract's own.
Run with ``--write`` after a contract change; ``--check`` fails when the committed file is stale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "examples" / "decision-contract-v2.golden.json"
sys.path.insert(0, str(REPO / "packages/core/src"))

from evalrank_core import (  # noqa: E402
    DEFAULT_AGENT_TASK_MIX,
    DecisionCaveatV2 as Caveat,
    DecisionExclusionV2 as Exclusion,
    DecisionFamilyV2 as Family,
    DecisionPriceV2 as Price,
    DecisionQueryV2 as Query,
    DecisionReceiptV2 as Receipt,
    DecisionRelaxationV2 as Relaxation,
    DecisionSelectionV2 as Selection,
    EffortMultiplierV2 as Multiplier,
    UsageProfileV1,
    canonical_json,
    sha256_hex,
)

DECIDED_AT = "2026-11-01T09:00:00Z"
AA_COST = "aa-intelligence-index-cost-per-task"
SNAP = {
    "writing": ("explorer_" + "1" * 64, "explorer_" + "2" * 64),
    "factuality": ("explorer_" + "3" * 64, "explorer_" + "4" * 64),
    "instruction-following": ("explorer_" + "5" * 64,),
    "reasoning": ("explorer_" + "6" * 64,),
    "legal": ("explorer_" + "7" * 64,),
    "math-reasoning": ("explorer_" + "8" * 64,),
}
PRICES = {
    "gpt-6-sol": (1_250_000, 125_000, 10_000_000),
    "gpt-6-astra": (5_000_000, 500_000, 40_000_000),
    "gpt-5-mini": (250_000, 25_000, 2_000_000),
    "lyra-3": (2_000_000, 200_000, 12_000_000),
}
DISPLAY = {"gpt-6-sol": "GPT-6 Sol", "gpt-6-astra": "GPT-6 Astra", "gpt-5-mini": "GPT-5 mini", "lyra-3": "Lyra 3"}


def base_cost(model: str, usage: UsageProfileV1) -> int:
    uncached, cached, output = PRICES[model]
    numerator = (
        usage.uncached_input_tokens * uncached
        + usage.cached_read_tokens * cached
        + usage.output_tokens * output
    )
    return -(-numerator // 1_000_000)


def selection(
    model: str,
    effort: str,
    ratio_ppm: int,
    *,
    usage: UsageProfileV1 = DEFAULT_AGENT_TASK_MIX,
    via: str = "openai",
    api: str = "chat_completions",
    multiplier_ppm: int | None = 1_000_000,
    coverage: int = 2,
    latency: int | None = 900,
    caveats: tuple[Caveat, ...] = (),
    vendor: str = "openai",
    refusal: tuple[str, float | None] | None = None,
) -> Selection:
    if multiplier_ppm is None:
        multiplier, cost = None, None
        caveats = (*caveats, Caveat(code="cost_unmeasured"))
    else:
        source = "comparison_level" if multiplier_ppm == 1_000_000 else AA_COST
        multiplier = Multiplier(multiplier_ppm=multiplier_ppm, source=source)
        cost = -(-base_cost(model, usage) * multiplier_ppm // 1_000_000)
    uncached, cached, output = PRICES[model]
    return Selection(
        model_id=model if via == "openai" else f"{vendor}/{model}",
        display_name=DISPLAY[model],
        provider_id=vendor,
        serving_offer_id=f"offer_{via}-{model}",
        reasoning_effort=effort,
        api=api,
        capability_ratio_ppm=ratio_ppm,
        family_coverage=coverage,
        price=Price(
            input_microusd_per_million=uncached,
            cached_input_microusd_per_million=cached,
            output_microusd_per_million=output,
        ),
        effort_multiplier=multiplier,
        projected_cost_microusd=cost,
        latency_p50_ms=latency,
        caveats=caveats,
        model_family=None if refusal is None else refusal[0],
        refusal_score=None if refusal is None else refusal[1],
    )


def families(*rows: tuple[str, str, int, str | None]) -> tuple[Family, ...]:
    return tuple(Family(family_id=f, lock_status=s, weight_ppm=w, stale_at=t) for f, s, w, t in rows)


def receipt(name, query, outcome, cell, fams, selections=(), exclusions=(), reasons=(), snapshots=None, relaxation=None):
    built = Receipt.create(
        query=query,
        decided_at=DECIDED_AT,
        outcome=outcome,
        snapshot_ids=SNAP.get(cell, ()) if snapshots is None else snapshots,
        families=fams,
        selections=tuple(selections),
        exclusions=tuple(exclusions),
        abstain_reasons=tuple(reasons),
        relaxation=relaxation,
    )
    body = built.to_body_dict()
    assert Receipt.from_dict(built.to_dict()) == built
    return {"name": name, "body": body, "body_sha256": sha256_hex(body, allow_floats=True), "receipt_id": built.receipt_id}


WRITING_FAMILIES = families(
    ("eqbench-creative-writing-v3", "admitted", 400_000, "2026-11-12T00:00:00Z"),
    ("lmarena-instruction-following", "admitted", 600_000, "2026-11-10T00:00:00Z"),
)
FACTUALITY_FAMILIES = families(
    ("aa-omniscience", "admitted", 350_000, "2026-11-08T00:00:00Z"),
    ("facts-grounding-v2", "admitted", 300_000, "2026-11-09T00:00:00Z"),
    ("simpleqa-verified", "admitted", 350_000, "2026-11-11T00:00:00Z"),
    ("vectara-hhem", "held", 0, "2026-11-07T00:00:00Z"),
)

receipts = [
    receipt(
        "value_pick",
        Query(cell_id="writing", objective="lowest_cost_within_top_set", provider_ids=("openai",)),
        "pick",
        "writing",
        WRITING_FAMILIES,
        selections=(
            selection("gpt-6-sol", "medium", 985_000),
            selection("gpt-6-sol", "high", 1_000_000, multiplier_ppm=1_510_000),
            selection("gpt-6-astra", "medium", 990_000),
        ),
        exclusions=(
            Exclusion(model_key="gpt53codex", code="api_not_supported", reasoning_effort="medium", detail="codex skus answer only on api responses"),
            Exclusion(model_key="gpt6sol", code="effort_not_accepted", reasoning_effort="max", detail="max is not in the openai effort vocabulary"),
            Exclusion(model_key="gpt5mini", code="constraints_not_met", reasoning_effort="medium", detail="capability ratio 0.81 is below the 0.97 band"),
        ),
    ),
    receipt(
        "top_set_pick",
        Query(cell_id="reasoning", objective="capability_top_set", via="openrouter", provider_ids=("openai",)),
        "pick",
        "reasoning",
        families(("livebench-reasoning", "admitted", 1_000_000, "2026-11-13T00:00:00Z")),
        selections=(
            selection("gpt-6-sol", "max", 1_000_000, via="openrouter", multiplier_ppm=None, coverage=1, latency=None),
            selection("gpt-6-sol", "medium", 992_000, via="openrouter", coverage=1),
        ),
    ),
    receipt(
        "pinned_level",
        Query(
            cell_id="instruction-following",
            objective="lowest_cost_within_top_set",
            provider_ids=("openai",),
            reasoning_effort="low",
            usage_profile=UsageProfileV1(
                basis="measured",
                uncached_input_tokens=2_400,
                cached_read_tokens=0,
                output_tokens=300,
                cache_writes=(),
                cache_storage_token_seconds=0,
            ),
        ),
        "pick",
        "instruction-following",
        families(("aa-ifbench", "admitted", 1_000_000, "2026-11-04T00:00:00Z")),
        selections=(
            selection(
                "gpt-5-mini",
                "low",
                975_000,
                coverage=1,
                usage=UsageProfileV1(basis="measured", uncached_input_tokens=2_400, cached_read_tokens=0, output_tokens=300, cache_writes=(), cache_storage_token_seconds=0),
            ),
            selection(
                "gpt-6-sol",
                "low",
                1_000_000,
                coverage=1,
                usage=UsageProfileV1(basis="measured", uncached_input_tokens=2_400, cached_read_tokens=0, output_tokens=300, cache_writes=(), cache_storage_token_seconds=0),
            ),
        ),
    ),
    receipt(
        "substituted_effort",
        Query(cell_id="factuality", objective="lowest_cost_within_top_set", provider_ids=("openai",)),
        "pick",
        "factuality",
        FACTUALITY_FAMILIES,
        selections=(
            selection(
                "gpt-6-sol",
                "medium",
                1_000_000,
                coverage=3,
                caveats=(Caveat(code="effort_substituted", measured_effort="max", gap_ppm=12_000),),
            ),
        ),
        exclusions=(
            Exclusion(model_key="gpt6nano", code="effort_gap_too_large", reasoning_effort="medium", detail="measured only at xhigh; the effort curve gap is 0.081"),
        ),
    ),
    receipt(
        "fallback_chain_pick",
        Query(cell_id="writing", objective="fallback_chain", via="openrouter", max_refusal_score=0.4),
        "pick",
        "writing",
        WRITING_FAMILIES,
        selections=(
            selection("gpt-6-sol", "high", 1_000_000, via="openrouter", multiplier_ppm=1_510_000, coverage=1, refusal=("openai", 0.25)),
            selection("lyra-3", "medium", 960_000, via="openrouter", vendor="lyra", coverage=1, refusal=("lyra", 0.125)),
        ),
        exclusions=(
            Exclusion(model_key="gpt6sol", code="constraints_not_met", reasoning_effort="medium", detail="a more capable configuration of the same model leads the chain"),
            Exclusion(model_key="gpt6astra", code="constraints_not_met", reasoning_effort="medium", detail="a more capable model of the same vendor leads the chain"),
            Exclusion(model_key="gpt5mini", code="refusal_score_unknown", reasoning_effort="medium"),
        ),
    ),
    receipt(
        "abstain_refusal_relaxation",
        Query(cell_id="writing", objective="capability_top_set", via="openrouter", max_refusal_score=0.1),
        "abstain",
        "writing",
        WRITING_FAMILIES,
        exclusions=(
            Exclusion(model_key="gpt6sol", code="refusal_score_above_max", reasoning_effort="medium", detail="refusal score 0.25 is above 0.1"),
            Exclusion(model_key="lyra3", code="refusal_score_above_max", reasoning_effort="medium", detail="refusal score 0.125 is above 0.1"),
            Exclusion(model_key="gpt5mini", code="refusal_score_unknown", reasoning_effort="medium"),
        ),
        reasons=("no_eligible_offer",),
        relaxation=Relaxation(max_refusal_score=0.125),
    ),
    receipt(
        "abstain_no_ranked_candidate",
        Query(cell_id="legal", objective="lowest_cost_within_top_set"),
        "abstain",
        "legal",
        families(("legalbench", "unlocked", 0, "2026-11-06T00:00:00Z")),
        exclusions=(Exclusion(model_key="gpt6sol", code="ambiguous_identity", detail="two skus resolve to one key"),),
        reasons=("no_ranked_candidate",),
    ),
    receipt(
        "abstain_no_eligible_offer",
        Query(cell_id="math-reasoning", objective="lowest_cost_within_top_set", provider_ids=("openai",), regions=("eu-west",)),
        "abstain",
        "math-reasoning",
        families(("matharena", "admitted", 1_000_000, "2026-11-05T00:00:00Z")),
        exclusions=(Exclusion(model_key="gpt6sol", code="no_serving_offer", reasoning_effort="medium", detail="no live offer in eu-west"),),
        reasons=("no_eligible_offer",),
    ),
    receipt(
        "abstain_stale_evidence",
        Query(cell_id="writing", objective="capability_top_set"),
        "abstain",
        "writing",
        families(
            ("eqbench-creative-writing-v3", "admitted", 400_000, "2026-10-28T00:00:00Z"),
            ("lmarena-instruction-following", "admitted", 600_000, "2026-10-30T00:00:00Z"),
        ),
        reasons=("stale_evidence",),
    ),
    receipt(
        "abstain_not_a_model_cell",
        Query(cell_id="code-review", objective="lowest_cost_within_top_set"),
        "abstain",
        "code-review",
        families(("macroscopebench-medium", "admitted", 1_000_000, "2026-11-10T00:00:00Z")),
        reasons=("not_a_model_cell",),
        snapshots=(),
    ),
]

query_input = {
    "object": "decision_query",
    "schema_version": "2",
    "cell_id": "writing",
    "objective": "lowest_cost_within_top_set",
    "via": "openai",
    "provider_ids": ["azure", "openai"],
    "api": "responses",
    "reasoning_effort": "medium",
    "regions": ["eu-west", "us-west"],
    "minimum_context_tokens": 32000,
    "usage_profile": {
        "basis": "estimated",
        "uncached_input_tokens": 1000,
        "cached_read_tokens": 8000,
        "output_tokens": 500,
        "cache_writes": [{"ttl_seconds": 300, "tokens": 2000}],
        "cache_storage_token_seconds": 0,
    },
}
corpus = {
    "schema_version": "2",
    "utf16_set_order": {"input": ["", "\U00010000"], "canonical": ["\U00010000", ""]},
    "query": {"input": query_input, "canonical": Query.from_dict(query_input).canonical_json()},
    "receipts": receipts,
    "problems": [
        {
            "name": "via_not_supported",
            "query": {"schema_version": "2", "cell_id": "writing", "objective": "lowest_cost_within_top_set", "via": "anthropic"},
            "problem": {
                "type": "https://evalrank.ai/problems/via-not-supported",
                "title": "Call surface not supported",
                "status": 422,
                "detail": "via anthropic has no probed effort vocabulary; call through openrouter",
                "code": "via_not_supported",
                "retriable": False,
                "field": "via",
                "supported_via": ["fal", "openai", "openrouter"],
            },
        }
    ],
    "rejection_vectors": [
        {"name": "float", "value": 1.5},
        {"name": "unsafe_integer", "value": 9007199254740992},
        {"name": "null_provider_filter", "value": {**{k: v for k, v in query_input.items()}, "provider_ids": None}},
        {"name": "v1_schema_version", "value": {**{k: v for k, v in query_input.items()}, "schema_version": "1"}},
        {"name": "v1_ranking_group", "value": {**{k: v for k, v in query_input.items()}, "ranking_group_id": "rg-writing"}},
        {"name": "v1_monthly_budget", "value": {**{k: v for k, v in query_input.items()}, "monthly_budget_microusd": 5}},
    ],
}
canonical_json(corpus["query"]["input"])


def render() -> str:
    return json.dumps(corpus, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        GOLDEN.write_text(render(), encoding="utf-8")
        return 0
    if not GOLDEN.exists() or GOLDEN.read_text(encoding="utf-8") != render():
        print(f"{GOLDEN.relative_to(REPO)} is stale: run scripts/build_decision_golden.py --write", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
