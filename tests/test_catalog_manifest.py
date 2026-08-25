import json
import sys
import unittest
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "packages" / "core" / "src"
sys.path.insert(0, str(CORE_SRC))

from evalrank_core.fixtures import sample_use_case_catalog  # noqa: E402


EXPECTED_CELL_IDS = (
    "code-generation",
    "autonomous-swe-agent",
    "function-calling",
    "mcp-tool-orchestration",
    "web-browsing",
    "computer-use",
    "deep-research",
    "customer-support",
    "enterprise-crm-workflow",
    "math-reasoning",
    "general-knowledge-qa",
    "rag-retrieval",
    "long-term-memory",
    "finance",
    "legal",
    "medical",
    "multilingual",
    "vision-multimodal",
    "web-frontend-code-generation",
    "sre-incident-response",
    "devops-lifecycle",
    "terminal-generalist",
    "mobile-codegen",
    "reasoning",
    "factuality",
    "professional-deliverable-creation",
    "machine-learning-engineering",
    "computational-research-reproduction",
)

EXPECTED_FAMILY_IDS = (
    "livecodebench",
    "aider-polyglot",
    "bigcodebench",
    "scicode",
    "swe-bench-live",
    "terminal-bench-2-1",
    "swe-lancer",
    "swe-rebench",
    "liveswebench",
    "bfcl-v4",
    "complexfuncbench",
    "tau2-bench",
    "mcp-universe",
    "mcpmark",
    "mcp-bench",
    "webarena-verified",
    "online-mind2web",
    "browsecomp-plus",
    "real-benchmark",
    "osworld-verified",
    "windowsagentarena",
    "androidworld",
    "screenspot-pro",
    "deepresearch-bench",
    "hle-with-tools",
    "futuresearch-drb",
    "tau-voice",
    "crmarena-pro-service",
    "crmarena-pro",
    "workarena-plus-plus",
    "theagentcompany",
    "gaia2-are",
    "matharena",
    "frontiermath-v2",
    "putnambench",
    "hle",
    "simpleqa-verified",
    "facts-parametric",
    "mmlu-pro",
    "facts-grounding-v2",
    "mteb-beir",
    "crag",
    "frames",
    "longmemeval",
    "locomo",
    "beam-memory",
    "vals-fab-v2",
    "finsearchcomp",
    "financebench",
    "legalbench",
    "vlair",
    "healthbench",
    "healthbench-professional",
    "medhelm",
    "global-mmlu",
    "mmlu-prox",
    "wmt24-plus-plus",
    "mmmu-pro",
    "mathvista",
    "video-mme",
    "webdev-arena",
    "design-arena",
    "swe-bench-multimodal",
    "itbench",
    "aiopslab",
    "sregym",
    "devops-gym",
    "android-bench",
    "appforge",
    "swifteval",
    "swe-bench-mobile",
    "livebench-reasoning",
    "arc-agi-2",
    "swe-bench-verified",
    "swe-bench-pro",
    "steel-current-composites",
    "gdpval",
    "mle-bench",
    "paperbench",
    "core-bench-reproducibility",
    "mcp-atlas",
    "browsecomp",
    "toolathlon",
    "agents-last-exam",
    "automationbench",
    "officeqa-pro",
    "finance-agent-v2",
    "deepswe",
    "mteb-eng-v2",
    "mteb-longembed",
    "mteb-followir",
    "mteb-rar-b",
    "mteb-multilingual-v2",
    "widesearch",
    "deepsearchqa",
    "gpqa-diamond",
    "kernelbench",
    "profbench",
    "bixbench",
    "medxpertqa",
    "bbeh",
    "musr",
    "legalagentbench",
)

# MTEB families each expose an embedder + a reranker feed (both retrieval
# components) rather than a single ``-discovery`` feed.
_MTEB_FAMILY_IDS = (
    "mteb-beir",
    "mteb-eng-v2",
    "mteb-longembed",
    "mteb-followir",
    "mteb-rar-b",
    "mteb-multilingual-v2",
)

# A benchmark whose scores are also published as a search configuration carries
# that second feed alongside its own ``-discovery`` feed. The configuration feed
# is a distinct ranking identity — it resolves to ``system_configuration`` while
# the discovery feed does not — and is never a duplicate of the same one. A
# second source that resolves to an identity a family already carries earns a
# provenance source, not a feed row.
_AGGREGATED_FAMILY_FEEDS = {
    "browsecomp": ("browsecomp-discovery", "browsecomp-openrouter-search"),
    "hle-with-tools": (
        "hle-with-tools-discovery",
        "hle-with-tools-openrouter-search",
    ),
    "widesearch": ("widesearch-discovery", "widesearch-openrouter-search"),
    "deepsearchqa": (
        "deepsearchqa-discovery",
        "deepsearchqa-openrouter-search",
    ),
}

EXPECTED_FEED_IDS = tuple(
    feed_id
    for family_id in EXPECTED_FAMILY_IDS
    for feed_id in {
        "itbench": ("itbench-discovery", "itbench-aa-discovery"),
        "mle-bench": ("mle-bench-v1-discovery",),
        "paperbench": ("paperbench-full-discovery",),
        "core-bench-reproducibility": (
            "core-bench-v1-1-mainline-discovery",
            "core-bench-v1-1-ood-discovery",
        ),
        **{
            fam: (f"{fam}-embedding-discovery", f"{fam}-reranking-discovery")
            for fam in _MTEB_FAMILY_IDS
        },
        **_AGGREGATED_FAMILY_FEEDS,
    }.get(family_id, (f"{family_id}-discovery",))
)

# Exact ranking identities project into the deliberately smaller public catalog
# ontology. A system is public-facing as either a tool or agent depending on the
# cell; unresolved identities cannot make a compatibility claim.
PUBLIC_ENTITY_KINDS_BY_CONFIGURATION_KIND = {
    "model_configuration": frozenset({"model"}),
    "agent_system": frozenset({"agent"}),
    "component_configuration": frozenset({"tool"}),
    "system_configuration": frozenset({"tool", "agent"}),
    "arena_system": frozenset({"model", "agent"}),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def manifest() -> dict:
    return load_json(REPO_ROOT / "catalog" / "manifest.json")


def derived_family_state(feeds: list[dict]) -> str:
    states = {feed["state"] for feed in feeds}
    if "active" in states:
        return "active"
    if "shadow" in states:
        return "shadow"
    if "discovered" in states:
        return "discovered"
    return "quarantined"


def manifest_semantic_errors(payload: dict) -> list[str]:
    errors: list[str] = []
    cell_ids = {row["cell_id"] for row in payload["cells"]}
    cell_by_id = {row["cell_id"]: row for row in payload["cells"]}
    group_by_id = {
        row["ranking_group_id"]: row for row in payload["ranking_groups"]
    }
    family_by_id = {
        row["benchmark_family_id"]: row for row in payload["benchmark_families"]
    }

    for group in payload["ranking_groups"]:
        if group["cell_id"] not in cell_ids:
            errors.append(
                f"ranking group {group['ranking_group_id']} references unknown cell "
                f"{group['cell_id']}"
            )
        elif (
            group["state"] == "active"
            and cell_by_id[group["cell_id"]]["state"] != "active"
        ):
            errors.append(
                f"active ranking group {group['ranking_group_id']} cell is not active"
            )
        elif group["entity_kind"] != "unresolved":
            compatible_public_kinds = PUBLIC_ENTITY_KINDS_BY_CONFIGURATION_KIND[
                group["entity_kind"]
            ]
            declared_public_kinds = set(
                cell_by_id[group["cell_id"]]["entity_kinds"]
            )
            if declared_public_kinds.isdisjoint(compatible_public_kinds):
                errors.append(
                    f"ranking group {group['ranking_group_id']} entity kind "
                    f"{group['entity_kind']} is absent from its cell's public ontology"
                )
        # v2: publication is decoupled from validation. An active (published) group
        # no longer must carry a validated top-set overlap; its eligibility fields
        # report the real (often explorer/unvalidated) evidence.

    for family in payload["benchmark_families"]:
        unknown_cells = set(family["candidate_cells"]) - cell_ids
        if unknown_cells:
            errors.append(
                f"benchmark family {family['benchmark_family_id']} references unknown cells "
                f"{sorted(unknown_cells)}"
            )
        if family["state"] == "active":
            if "unresolved" in family["entity_kinds"]:
                errors.append(
                    f"active benchmark family {family['benchmark_family_id']} "
                    "has unresolved entity identity"
                )
            # v2: publication decoupled from validation. An active family keeps its
            # real rank_eligible_count / correlation_status / correlated_family_group
            # (often null/unknown); these no longer gate publication.

    for feed in payload["feeds"]:
        family = family_by_id.get(feed["benchmark_family_id"])
        if family is None:
            errors.append(
                f"feed {feed['feed_id']} references unknown family "
                f"{feed['benchmark_family_id']}"
            )
            continue
        if feed["state"] == "active" and feed["entity_kind"] == "unresolved":
            errors.append(f"active feed {feed['feed_id']} has unresolved identity")
        if feed["state"] in {"active", "shadow"} and feed["metric_direction"] not in {
            "higher",
            "lower",
        }:
            errors.append(
                f"implemented feed {feed['feed_id']} has no metric direction"
            )
        if feed["state"] == "discovered" and feed["metric_direction"] is not None:
            errors.append(
                f"discovered feed {feed['feed_id']} claims an unverified metric direction"
            )
        if feed["state"] != "active" and feed["rank_eligible_count"] is not None:
            errors.append(
                f"non-active feed {feed['feed_id']} claims rank-eligible observations"
            )
        if feed["candidate_cells"] != family["candidate_cells"]:
            errors.append(
                f"feed {feed['feed_id']} candidate cells differ from family "
                f"{family['benchmark_family_id']}"
            )
        feed_kind_is_family_candidate = (
            feed["entity_kind"] in family["entity_kinds"]
            or (
                feed["entity_kind"] == "unresolved"
                and len(family["entity_kinds"]) > 1
            )
        )
        if not feed_kind_is_family_candidate:
            errors.append(
                f"feed {feed['feed_id']} entity kind is absent from family "
                f"{family['benchmark_family_id']}"
            )
        if (
            feed["lineage"]["correlated_family_group"]
            != family["correlated_family_group"]
        ):
            errors.append(
                f"feed {feed['feed_id']} correlation group differs from family "
                f"{family['benchmark_family_id']}"
            )

        expected_group_ids = {
            group["ranking_group_id"]
            for group in payload["ranking_groups"]
            if group["cell_id"] in feed["candidate_cells"]
            and group["entity_kind"] == feed["entity_kind"]
            and group["interaction_policy"] == feed["interaction_policy"]
            and group["configuration_passport_class"]
            == feed["configuration_passport_class"]
        }
        actual_group_ids = set(feed["ranking_group_ids"])
        if actual_group_ids != expected_group_ids:
            errors.append(
                f"feed {feed['feed_id']} ranking groups do not match its identity"
            )
        unknown_group_ids = actual_group_ids - set(group_by_id)
        if unknown_group_ids:
            errors.append(
                f"feed {feed['feed_id']} references unknown ranking groups "
                f"{sorted(unknown_group_ids)}"
            )

    feeds_by_family = {
        family_id: [
            feed
            for feed in payload["feeds"]
            if feed["benchmark_family_id"] == family_id
        ]
        for family_id in family_by_id
    }
    for family_id, family_feeds in feeds_by_family.items():
        if not family_feeds:
            continue
        expected_state = derived_family_state(family_feeds)
        if family_by_id[family_id]["state"] != expected_state:
            errors.append(
                f"benchmark family {family_id} state is not the derived feed aggregate"
            )

    active_group_cell_ids = {
        group["cell_id"]
        for group in payload["ranking_groups"]
        if group["state"] == "active"
    }
    for cell in payload["cells"]:
        if cell["state"] == "active" and cell["cell_id"] not in active_group_cell_ids:
            errors.append(
                f"active cell {cell['cell_id']} has no active ranking group"
            )

    # v2: publication decoupled from validation. An active (published) group no
    # longer requires a validated top-set gate or a minimum number of independent
    # validated families; explorer-claim groups publish their real evidence and
    # disclose gaps rather than being withheld.

    return errors


class CatalogManifestTests(unittest.TestCase):
    def test_catalog_readme_documents_portable_aggregation_vectors(self):
        text = (REPO_ROOT / "catalog" / "README.md").read_text(encoding="utf-8")

        for phrase in (
            "aggregation-vectors.json",
            "post-admission",
            "identical-mirror",
            "semantic observation",
            "conflict",
            "metric_direction",
            "must never infer direction",
        ):
            self.assertIn(phrase, text)

    def test_manifest_has_unique_cells_ranking_groups_families_and_feeds(self):
        payload = manifest()

        self.assertEqual("evalrank_manifest", payload["object"])
        self.assertEqual("1", payload["schema_version"])
        self.assertEqual("2026-08-04.1", payload["manifest_version"])
        for key, id_key in (
            ("cells", "cell_id"),
            ("ranking_groups", "ranking_group_id"),
            ("benchmark_families", "benchmark_family_id"),
            ("feeds", "feed_id"),
        ):
            with self.subTest(key=key):
                ids = [row[id_key] for row in payload[key]]
                self.assertEqual(len(ids), len(set(ids)))

    def test_terminal_bench_feed_uses_the_composite_adapter_contract(self):
        payload = manifest()
        feed = next(
            row for row in payload["feeds"]
            if row["feed_id"] == "terminal-bench-2-1-discovery"
        )

        self.assertEqual(
            "terminal-bench-2-1-official-hub-repository-v1",
            feed["adapter_id"],
        )
        self.assertEqual(["terminal-generalist"], feed["candidate_cells"])
        self.assertTrue(feed["retention"]["store_artifact_bytes"])

    def test_manifest_is_the_exact_public_taxonomy(self):
        payload = manifest()
        cells = payload["cells"]

        self.assertEqual(EXPECTED_CELL_IDS, tuple(row["cell_id"] for row in cells))
        self.assertNotIn("aliases", payload)
        # v2: cells are the published (active) public taxonomy.
        self.assertTrue(all(row["state"] == "active" for row in cells))
        self.assertTrue(all("rank_eligible_count" not in row for row in cells))
        self.assertTrue(all("eligibility" not in row for row in cells))
        self.assertNotIn("safety-robustness", EXPECTED_CELL_IDS)
        new_cells = {row["cell_id"]: row for row in cells[-3:]}
        self.assertEqual(
            {
                "professional-deliverable-creation": {
                    "name": "Professional deliverables",
                    "definition": (
                        "Create review-ready professional work products from a complete "
                        "brief, domain context, and reference files."
                    ),
                    "entity_kinds": ["model", "agent"],
                },
                "machine-learning-engineering": {
                    "name": "Machine-learning engineering",
                    "definition": (
                        "Build, train, and optimize machine-learning solutions from datasets "
                        "and scored task objectives."
                    ),
                    "entity_kinds": ["agent"],
                },
                "computational-research-reproduction": {
                    "name": "Computational research reproduction",
                    "definition": (
                        "Reproduce published computational results by implementing or "
                        "executing experiments from papers, code, data, and environments."
                    ),
                    "entity_kinds": ["agent"],
                },
            },
            {
                cell_id: {
                    "name": row["name"],
                    "definition": row["definition"],
                    "entity_kinds": row["entity_kinds"],
                }
                for cell_id, row in new_cells.items()
            },
        )

    def test_every_cell_has_explicit_ordered_ranking_group_eligibility(self):
        payload = manifest()
        cell_ids = {cell["cell_id"] for cell in payload["cells"]}
        self.assertEqual(42, len(payload["ranking_groups"]))
        group_keys = set()
        covered_cells = set()

        for group in payload["ranking_groups"]:
            eligibility = group["eligibility"]
            key = tuple(group[dimension] for dimension in payload["ranking_group_dimensions"])
            with self.subTest(ranking_group_id=group["ranking_group_id"]):
                self.assertIn(group["cell_id"], cell_ids)
                self.assertNotIn(key, group_keys)
                group_keys.add(key)
                covered_cells.add(group["cell_id"])
                unresolved_dimensions = (
                    group["entity_kind"] == "unresolved",
                    group["interaction_policy"] == "unresolved",
                    group["configuration_passport_class"] == "unresolved-v1",
                )
                self.assertIn(sum(unresolved_dimensions), {0, 3})
                # v2: publication is decoupled from validation. An active
                # (published) group may report unvalidated calibration and a null
                # rank-eligible count; those fields no longer gate publication.
                if group["state"] == "quarantined":
                    self.assertIsNone(group["rank_eligible_count"])
                    self.assertTrue(group["quarantine_reason"])
                else:
                    self.assertIsNone(group["quarantine_reason"])
                self.assertGreaterEqual(eligibility["explorer"]["minimum_families"], 1)
                if any(unresolved_dimensions):
                    self.assertEqual("explorer", group["claim_ceiling"])
                if group["claim_ceiling"] == "explorer":
                    self.assertEqual("explorer", group["claim_ceiling"])
                    self.assertIsNone(eligibility["top_set"])
                    self.assertIsNone(eligibility["single_winner"])
                    self.assertIsNone(eligibility["superiority_threshold"])
                    self.assertIsNone(eligibility["practical_effect_floor"])
                    self.assertIsNone(eligibility["leave_one_family_out"])
                else:
                    self.assertEqual("single_winner", group["claim_ceiling"])
                    # v2: single-source rankings are allowed; the family floors
                    # may be as low as 1. The ordering invariant below still holds.
                    self.assertGreaterEqual(eligibility["top_set"]["minimum_families"], 1)
                    self.assertGreaterEqual(eligibility["single_winner"]["minimum_families"], 1)
                    self.assertGreaterEqual(
                        eligibility["single_winner"]["minimum_overlap"],
                        eligibility["top_set"]["minimum_overlap"],
                    )
                    self.assertIsNotNone(eligibility["superiority_threshold"])
                    self.assertIsNotNone(eligibility["practical_effect_floor"])
                    self.assertIsNotNone(eligibility["leave_one_family_out"])
                self.assertLess(0, eligibility["bootstrap_coverage_target"])
                self.assertLess(eligibility["bootstrap_coverage_target"], 1)
                self.assertEqual(10_000, eligibility["block_bootstrap"]["replicates"])
                self.assertEqual(
                    "uint64be(sha256(restricted_jcs({aggregation_input_digest,methodology_version}))[0:8])"
                    "&9007199254740991",
                    eligibility["block_bootstrap"]["seed_derivation"],
                )
                self.assertIn("native", eligibility["native_effect_policy"])
                self.assertIn("exclude", eligibility["missing_configuration_policy"])
                if eligibility["leave_one_family_out"] is not None:
                    self.assertTrue(eligibility["leave_one_family_out"]["required_for_single_winner"])

        self.assertEqual(cell_ids, covered_cells)

        new_groups = {
            group["cell_id"]: group
            for group in payload["ranking_groups"]
            if group["cell_id"] in set(EXPECTED_CELL_IDS[-3:])
        }
        self.assertEqual(set(EXPECTED_CELL_IDS[-3:]), set(new_groups))
        self.assertEqual(
            {
                "professional-deliverable-creation": (
                    "rg-professional-deliverable-creation-system-configuration-"
                    "system-system-configuration-v1"
                ),
                "machine-learning-engineering": (
                    "rg-machine-learning-engineering-agent-system-agentic-agent-system-v1"
                ),
                "computational-research-reproduction": (
                    "rg-computational-research-reproduction-agent-system-agentic-"
                    "agent-system-v1"
                ),
            },
            {
                cell_id: group["ranking_group_id"]
                for cell_id, group in new_groups.items()
            },
        )
        self.assertEqual(
            ("system_configuration", "system", "system-configuration-v1"),
            tuple(
                new_groups["professional-deliverable-creation"][key]
                for key in (
                    "entity_kind",
                    "interaction_policy",
                    "configuration_passport_class",
                )
            ),
        )
        for cell_id in (
            "machine-learning-engineering",
            "computational-research-reproduction",
        ):
            self.assertEqual(
                ("agent_system", "agentic", "agent-system-v1"),
                tuple(
                    new_groups[cell_id][key]
                    for key in (
                        "entity_kind",
                        "interaction_policy",
                        "configuration_passport_class",
                    )
                ),
            )
        self.assertTrue(
            all(group["claim_ceiling"] == "explorer" for group in new_groups.values())
        )
        self.assertTrue(all(group["state"] == "active" for group in new_groups.values()))
        self.assertTrue(
            all(group["rank_eligible_count"] is None for group in new_groups.values())
        )
        self.assertTrue(
            all(
                group["eligibility"]["calibration_status"] == "unvalidated"
                for group in new_groups.values()
            )
        )

        feed_states_by_group = {group["ranking_group_id"]: [] for group in payload["ranking_groups"]}
        for feed in payload["feeds"]:
            for group_id in feed["ranking_group_ids"]:
                feed_states_by_group[group_id].append(feed["state"])
        for group in payload["ranking_groups"]:
            feed_states = feed_states_by_group[group["ranking_group_id"]]
            if group["state"] == "quarantined":
                self.assertTrue(all(state == "quarantined" for state in feed_states))
            else:
                self.assertTrue(any(state != "quarantined" for state in feed_states))

    def test_discovery_inventory_does_not_claim_admission(self):
        families = manifest()["benchmark_families"]
        family_by_id = {row["benchmark_family_id"]: row for row in families}
        cell_ids = {row["cell_id"] for row in manifest()["cells"]}
        quarantined = {
            family_id
            for family_id, row in family_by_id.items()
            if row["state"] == "quarantined"
        }
        # v2: formerly-shadow families are now published (active). Publication
        # is decoupled from validation, so these carry their real (still
        # unvalidated / null-count) evidence while being active.
        active = {
            family_id
            for family_id, row in family_by_id.items()
            if row["state"] == "active"
        }

        self.assertEqual(
            {"swe-bench-verified", "swe-bench-pro", "steel-current-composites"},
            quarantined,
        )
        self.assertEqual(
            {
                "aider-polyglot",
                "agents-last-exam",
                "arc-agi-2",
                "bfcl-v4",
                "deepswe",
                "frontiermath-v2",
                "hle",
                "livebench-reasoning",
                "livecodebench",
                "scicode",
                "simpleqa-verified",
                "swe-bench-live",
                "tau2-bench",
                "tau-voice",
                "terminal-bench-2-1",
                "theagentcompany",
                "video-mme",
                "webdev-arena",
                "mteb-beir",
                "mteb-eng-v2",
                "mteb-longembed",
                "mteb-followir",
                "mteb-rar-b",
                "mteb-multilingual-v2",
            },
            active,
        )
        self.assertEqual(103, len(families))
        self.assertEqual(EXPECTED_FAMILY_IDS, tuple(row["benchmark_family_id"] for row in families))
        self.assertTrue(all(row["rank_eligible_count"] is None for row in families))
        self.assertTrue(all(set(row["candidate_cells"]) <= cell_ids for row in families))
        self.assertTrue(all("saturated" not in row for row in families))
        self.assertTrue(
            all(
                bool(row["quarantine_reason"]) == (row["state"] == "quarantined")
                for row in families
            )
        )
        self.assertTrue(all(
            row["state"] == "discovered"
            for row in families
            if row["benchmark_family_id"] not in quarantined | active
        ))

        declared_correlations = {
            row["benchmark_family_id"]: row["correlated_family_group"]
            for row in families
            if row["correlation_status"] == "declared"
        }
        self.assertEqual(
            {
                "tau2-bench": "tau2",
                "tau-voice": "tau2",
                "hle-with-tools": "hle",
                "hle": "hle",
                "crmarena-pro-service": "crmarena-pro",
                "crmarena-pro": "crmarena-pro",
                "healthbench": "healthbench",
                "healthbench-professional": "healthbench",
                "core-bench-reproducibility": "core-bench",
                "aider-polyglot": "aider-polyglot",
                "itbench": "k8s-live-incident",
                "aiopslab": "k8s-live-incident",
                "sregym": "k8s-live-incident",
                "swe-bench-live": "github-issue-resolution",
                "swe-rebench": "github-issue-resolution",
                "mmlu-pro": "mmlu-lineage",
                "mmlu-prox": "mmlu-lineage",
                "global-mmlu": "mmlu-lineage",
                "browsecomp-plus": "browsecomp",
                "browsecomp": "browsecomp",
                "terminal-bench-2-1": "terminal-bench-2-1",
                "scicode": "scicode",
                "arc-agi-2": "arc-agi-2",
                "frontiermath-v2": "frontiermath",
                "simpleqa-verified": "simpleqa",
                "theagentcompany": "theagentcompany",
                "video-mme": "video-mme",
                "webdev-arena": "webdev-arena",
                "mteb-beir": "mteb-beir",
                "mteb-eng-v2": "mteb-eng-v2",
                "mteb-longembed": "mteb-longembed",
                "mteb-followir": "mteb-followir",
                "mteb-rar-b": "mteb-rar-b",
                "mteb-multilingual-v2": "mteb-multilingual-v2",
            },
            declared_correlations,
        )
        feeds = manifest()["feeds"]
        self.assertEqual(115, len(feeds))
        self.assertEqual(EXPECTED_FEED_IDS, tuple(row["feed_id"] for row in feeds))

    def test_itbench_is_not_executable_without_exact_configuration_identity(self):
        payload = manifest()
        family = next(
            row for row in payload["benchmark_families"] if row["benchmark_family_id"] == "itbench"
        )
        feed = next(row for row in payload["feeds"] if row["feed_id"] == "itbench-discovery")

        self.assertEqual("discovered", family["state"])
        self.assertEqual("quarantined", feed["state"])
        self.assertIn("exact evaluated configuration identity", feed["quarantine_reason"])

    def test_user_value_research_wave_maps_to_existing_decision_groups(self):
        payload = manifest()
        family_by_id = {
            row["benchmark_family_id"]: row for row in payload["benchmark_families"]
        }
        _RESEARCH_WAVE_FAMILIES = frozenset({
            "mcp-atlas",
            "browsecomp",
            "toolathlon",
            "agents-last-exam",
            "automationbench",
            "officeqa-pro",
            "finance-agent-v2",
            "deepswe",
        })
        # A family may now carry additional aggregator feeds alongside its
        # discovery feed; this wave assertion is about the discovery feed.
        feed_by_family = {
            row["benchmark_family_id"]: row for row in payload["feeds"]
            if row["benchmark_family_id"] in _RESEARCH_WAVE_FAMILIES
            and row["feed_id"].endswith("-discovery")
        }
        expected = {
            "mcp-atlas": ("mcp-tool-orchestration", "rg-mcp-tool-orchestration-agent-system-agentic-agent-system-v1"),
            "browsecomp": ("web-browsing", "rg-web-browsing-agent-system-agentic-agent-system-v1"),
            "toolathlon": ("mcp-tool-orchestration", "rg-mcp-tool-orchestration-agent-system-agentic-agent-system-v1"),
            "agents-last-exam": ("professional-deliverable-creation", "rg-professional-deliverable-creation-system-configuration-system-system-configuration-v1"),
            "automationbench": ("enterprise-crm-workflow", "rg-enterprise-crm-workflow-agent-system-agentic-agent-system-v1"),
            "officeqa-pro": ("rag-retrieval", "rg-rag-retrieval-system-configuration-system-system-configuration-v1"),
            "finance-agent-v2": ("finance", "rg-finance-agent-system-agentic-agent-system-v1"),
            "deepswe": ("autonomous-swe-agent", "rg-autonomous-swe-agent-agent-system-agentic-agent-system-v1"),
        }

        self.assertEqual(set(expected), set(feed_by_family))

        # The one wave family that also carries a search-configuration feed is
        # asserted directly, since the discovery filter above excludes it.
        browsecomp_search = next(
            row for row in payload["feeds"]
            if row["feed_id"] == "browsecomp-openrouter-search"
        )
        self.assertEqual("system_configuration", browsecomp_search["entity_kind"])
        self.assertEqual(
            ["rg-web-browsing-system-configuration-system-system-configuration-v1"],
            browsecomp_search["ranking_group_ids"],
        )

        for family_id, (cell_id, group_id) in expected.items():
            with self.subTest(family_id=family_id):
                family = family_by_id[family_id]
                feed = feed_by_family[family_id]
                self.assertEqual([cell_id], family["candidate_cells"])
                self.assertEqual([cell_id], feed["candidate_cells"])
                self.assertEqual([group_id], feed["ranking_group_ids"])
                if family_id not in {"agents-last-exam", "deepswe"}:
                    self.assertEqual("discovered", family["state"])
                    self.assertEqual("discovered", feed["state"])
                    self.assertIsNone(feed["adapter_id"])
                    self.assertEqual("approved", feed["rights"]["status"])
                    self.assertEqual("unvalidated", feed["cadence"]["status"])
                    self.assertFalse(feed["retention"]["store_artifact_bytes"])

    def test_replayable_user_value_feeds_are_refreshable_but_not_rank_eligible(self):
        payload = manifest()
        families = {row["benchmark_family_id"]: row for row in payload["benchmark_families"]}
        feeds = {row["benchmark_family_id"]: row for row in payload["feeds"]}
        expected = {
            "agents-last-exam": ("agents-last-exam-official-json-v1", "CC-BY-4.0"),
            "deepswe": ("deepswe-v1-1-official-json-v1", "Apache-2.0"),
        }

        for family_id, (adapter_id, data_license) in expected.items():
            with self.subTest(family_id=family_id):
                family = families[family_id]
                feed = feeds[family_id]
                # v2: now published (active); evidence fields unchanged.
                self.assertEqual("active", family["state"])
                self.assertEqual("active", feed["state"])
                self.assertEqual(adapter_id, feed["adapter_id"])
                self.assertEqual("higher", feed["metric_direction"])
                self.assertIsNone(feed["rank_eligible_count"])
                self.assertEqual("approved", feed["rights"]["status"])
                self.assertEqual(data_license, feed["rights"]["task_data_license"])
                self.assertEqual("allowed", feed["rights"]["result_redistribution"])
                self.assertEqual("allowed", feed["rights"]["artifact_retention"])
                self.assertEqual("allowed", feed["rights"]["environment_terms"])
                self.assertTrue(feed["retention"]["store_artifact_bytes"])
                self.assertEqual(
                    {
                        "status": "validated",
                        "mode": "periodic",
                        "stale_after_seconds": 172_800,
                        "stop_recommending_after_seconds": 604_800,
                        "as_of": None,
                        "upstream_version": None,
                    },
                    feed["cadence"],
                )
                self.assertEqual("validated", feed["lineage"]["validation_status"])
                self.assertEqual("unknown", feed["lineage"]["correlation_status"])
                self.assertIsNone(feed["lineage"]["correlated_family_group"])

    def test_tau2_feeds_are_active_published(self):
        payload = manifest()
        families = {row["benchmark_family_id"]: row for row in payload["benchmark_families"]}
        feeds = {row["benchmark_family_id"]: row for row in payload["feeds"]}
        expected = {
            "tau2-bench": "tau2-bench-submissions-json-v1",
            "tau-voice": "tau-voice-submissions-json-v1",
        }

        for family_id, adapter_id in expected.items():
            with self.subTest(family_id=family_id):
                family = families[family_id]
                feed = feeds[family_id]
                # v2: publication decoupled from validation — now active while
                # keeping their declared correlation lineage.
                self.assertEqual("active", family["state"])
                self.assertEqual("active", feed["state"])
                self.assertEqual(adapter_id, feed["adapter_id"])
                self.assertEqual("higher", feed["metric_direction"])
                self.assertIsNone(feed["rank_eligible_count"])
                self.assertEqual("approved", feed["rights"]["status"])
                self.assertEqual("MIT", feed["rights"]["task_data_license"])
                self.assertEqual(
                    "not-applicable-repo-data-view", feed["rights"]["harness_code_license"]
                )
                self.assertTrue(feed["retention"]["store_artifact_bytes"])
                self.assertEqual(
                    {
                        "status": "validated",
                        "mode": "periodic",
                        "stale_after_seconds": 2_592_000,
                        "stop_recommending_after_seconds": 15_552_000,
                        "as_of": None,
                        "upstream_version": None,
                    },
                    feed["cadence"],
                )
                self.assertEqual("declared", feed["lineage"]["correlation_status"])
                self.assertEqual("tau2", feed["lineage"]["correlated_family_group"])

    def test_github_issue_swe_families_share_one_uncalibrated_lineage(self):
        payload = manifest()
        family_ids = {"swe-bench-live", "swe-rebench"}
        families = [
            family
            for family in payload["benchmark_families"]
            if family["benchmark_family_id"] in family_ids
        ]
        feeds = [
            feed
            for feed in payload["feeds"]
            if feed["benchmark_family_id"] in family_ids
        ]

        self.assertEqual(
            family_ids,
            {family["benchmark_family_id"] for family in families},
        )
        self.assertEqual(
            {("declared", "github-issue-resolution")},
            {
                (family["correlation_status"], family["correlated_family_group"])
                for family in families
            },
        )
        self.assertEqual(
            {("declared", "github-issue-resolution")},
            {
                (
                    feed["lineage"]["correlation_status"],
                    feed["lineage"]["correlated_family_group"],
                )
                for feed in feeds
            },
        )

    def test_new_research_jobs_are_exact_preview_hypotheses(self):
        payload = manifest()
        family_by_id = {
            row["benchmark_family_id"]: row for row in payload["benchmark_families"]
        }
        expected = {
            "gdpval": (
                "GDPval",
                "professional-deliverable-creation",
                "system_configuration",
                {
                    "cross-occupation-mixture",
                    "one-shot-complete-context",
                    "tooling-scaffold-sensitive",
                    "human-pairwise-primary",
                    "automated-grader-not-independent",
                },
            ),
            "mle-bench": (
                "MLE-bench",
                "machine-learning-engineering",
                "agent_system",
                {
                    "leaderboard-submissions-paused",
                    "v1-known-health-defects",
                    "v2-pending",
                    "high-cost",
                    "scaffold-sensitive",
                    "competition-lineage",
                    "contamination-risk",
                },
            ),
            "paperbench": (
                "PaperBench",
                "computational-research-reproduction",
                "agent_system",
                {
                    "ml-paper-only",
                    "from-scratch-implementation",
                    "judge-model-dependent",
                    "third-party-assets",
                    "high-cost",
                },
            ),
            "core-bench-reproducibility": (
                "CORE-Bench (computational reproducibility)",
                "computational-research-reproduction",
                "agent_system",
                {
                    "measured-top-cohort-compression",
                    "active-validity-revision",
                    "scaffold-sensitive",
                    "multidimensional-utility",
                },
            ),
        }

        for family_id, (display_name, cell_id, entity_kind, flags) in expected.items():
            with self.subTest(family_id=family_id):
                family = family_by_id[family_id]
                self.assertEqual(display_name, family["display_name"])
                self.assertEqual([cell_id], family["candidate_cells"])
                self.assertEqual([entity_kind], family["entity_kinds"])
                self.assertEqual("discovered", family["state"])
                self.assertIsNone(family["rank_eligible_count"])
                self.assertEqual(flags, set(family["research_flags"]))

        self.assertFalse(
            any(
                "judge" in family_id or "rewardbench" in family_id
                for family_id in family_by_id
            )
        )

        feeds = {
            row["feed_id"]: row
            for row in payload["feeds"]
            if row["benchmark_family_id"] in expected
        }
        self.assertEqual(
            {
                "gdpval-discovery",
                "mle-bench-v1-discovery",
                "paperbench-full-discovery",
                "core-bench-v1-1-mainline-discovery",
                "core-bench-v1-1-ood-discovery",
            },
            set(feeds),
        )
        for feed in feeds.values():
            with self.subTest(feed_id=feed["feed_id"]):
                family = family_by_id[feed["benchmark_family_id"]]
                self.assertEqual(family["candidate_cells"], feed["candidate_cells"])
                self.assertEqual("discovered", feed["state"])
                self.assertIsNone(feed["adapter_id"])
                self.assertIsNone(feed["rank_eligible_count"])
                self.assertEqual("approved", feed["rights"]["status"])
                self.assertEqual("unvalidated", feed["cadence"]["status"])
                self.assertEqual("unknown", feed["lineage"]["validation_status"])
                self.assertFalse(feed["retention"]["store_artifact_bytes"])

        core_feeds = [
            row
            for row in feeds.values()
            if row["benchmark_family_id"] == "core-bench-reproducibility"
        ]
        self.assertEqual(2, len(core_feeds))
        self.assertEqual(
            {("declared", "core-bench")},
            {
                (
                    feed["lineage"]["correlation_status"],
                    feed["lineage"]["correlated_family_group"],
                )
                for feed in core_feeds
            },
        )
        self.assertEqual(
            {tuple(feed["ranking_group_ids"]) for feed in core_feeds},
            {
                (
                    "rg-computational-research-reproduction-agent-system-"
                    "agentic-agent-system-v1",
                )
            },
        )

    def test_feeds_have_complete_rights_cadence_retention_and_lineage(self):
        payload = manifest()
        family_by_id = {
            row["benchmark_family_id"]: row for row in payload["benchmark_families"]
        }
        feed_family_ids = set()
        rights_keys = {
            "status",
            "harness_code_license",
            "task_data_license",
            "commercial_use",
            "result_redistribution",
            "trajectory_redistribution",
            "environment_terms",
            "artifact_retention",
            "derived_score_publication",
        }

        for feed in payload["feeds"]:
            with self.subTest(feed_id=feed["feed_id"]):
                family = family_by_id[feed["benchmark_family_id"]]
                feed_family_ids.add(feed["benchmark_family_id"])
                self.assertEqual(family["candidate_cells"], feed["candidate_cells"])
                self.assertIsNone(feed["rank_eligible_count"])
                self.assertTrue(feed["ranking_group_ids"])
                if feed["state"] == "discovered":
                    self.assertIsNone(feed["adapter_id"])
                    self.assertIsNone(feed["metric_direction"])
                if feed["state"] in {"active", "shadow"}:
                    self.assertIn(feed["metric_direction"], {"higher", "lower"})
                self.assertEqual(rights_keys, set(feed["rights"]))
                self.assertIn(feed["rights"]["status"], {"approved", "blocked", "unknown"})
                self.assertIn(feed["cadence"]["status"], {"unvalidated", "validated"})
                if feed["cadence"]["status"] == "unvalidated":
                    self.assertTrue(
                        all(feed["cadence"][key] is None for key in (
                            "mode", "stale_after_seconds",
                            "stop_recommending_after_seconds", "as_of", "upstream_version",
                        ))
                    )
                elif feed["cadence"]["mode"] == "frozen":
                    self.assertIsNotNone(feed["cadence"]["as_of"])
                    self.assertIsNotNone(feed["cadence"]["upstream_version"])
                self.assertIsInstance(feed["retention"]["store_artifact_bytes"], bool)
                if feed["rights"]["artifact_retention"] == "unknown":
                    self.assertFalse(feed["retention"]["store_artifact_bytes"])
                self.assertIsNone(feed["retention"]["maximum_days"])
                if feed["lineage"]["validation_status"] == "unknown":
                    self.assertIsNone(feed["lineage"]["task_lineage_id"])
                    self.assertIsNone(feed["lineage"]["environment_lineage_id"])
                    self.assertIsNone(feed["lineage"]["grader_lineage_id"])
                else:
                    self.assertTrue(feed["lineage"]["task_lineage_id"])
                    self.assertTrue(feed["lineage"]["environment_lineage_id"])
                    self.assertTrue(feed["lineage"]["grader_lineage_id"])
                self.assertEqual(
                    family["correlated_family_group"],
                    feed["lineage"]["correlated_family_group"],
                )
                if family["correlation_status"] == "unknown":
                    self.assertIsNone(family["correlated_family_group"])

        self.assertEqual(set(family_by_id), feed_family_ids)
        recovered_directions = {
            feed["feed_id"]: feed["metric_direction"]
            for feed in payload["feeds"]
            if feed["metric_direction"] is not None
        }
        self.assertEqual(
            {
                "agents-last-exam-discovery": "higher",
                "arc-agi-2-discovery": "higher",
                "bfcl-v4-discovery": "higher",
                "deepswe-discovery": "higher",
                "aider-polyglot-discovery": "higher",
                "frontiermath-v2-discovery": "higher",
                "hle-discovery": "higher",
                "itbench-discovery": "higher",
                "livebench-reasoning-discovery": "higher",
                "livecodebench-discovery": "higher",
                "scicode-discovery": "higher",
                "simpleqa-verified-discovery": "higher",
                "swe-bench-live-discovery": "higher",
                "tau2-bench-discovery": "higher",
                "tau-voice-discovery": "higher",
                "terminal-bench-2-1-discovery": "higher",
                "theagentcompany-discovery": "higher",
                "video-mme-discovery": "higher",
                "webdev-arena-discovery": "higher",
                "mteb-beir-embedding-discovery": "higher",
                "mteb-beir-reranking-discovery": "higher",
                "mteb-eng-v2-embedding-discovery": "higher",
                "mteb-eng-v2-reranking-discovery": "higher",
                "mteb-longembed-embedding-discovery": "higher",
                "mteb-longembed-reranking-discovery": "higher",
                "mteb-followir-embedding-discovery": "higher",
                "mteb-followir-reranking-discovery": "higher",
                "mteb-rar-b-embedding-discovery": "higher",
                "mteb-rar-b-reranking-discovery": "higher",
                "mteb-multilingual-v2-embedding-discovery": "higher",
                "mteb-multilingual-v2-reranking-discovery": "higher",
            },
            recovered_directions,
        )
        feed_counts = Counter(feed["benchmark_family_id"] for feed in payload["feeds"])
        self.assertEqual(2, feed_counts.pop("core-bench-reproducibility"))
        self.assertEqual(2, feed_counts.pop("itbench"))
        # Each MTEB family exposes an embedder + a reranker feed.
        for mteb_family in _MTEB_FAMILY_IDS:
            self.assertEqual(2, feed_counts.pop(mteb_family))
        # Families whose scores are also published by an aggregator carry that
        # aggregator's feed alongside their own discovery feed.
        for aggregated_family, expected_feeds in _AGGREGATED_FAMILY_FEEDS.items():
            self.assertEqual(len(expected_feeds), feed_counts.pop(aggregated_family))
        self.assertTrue(all(count == 1 for count in feed_counts.values()))

        self.assertEqual([], manifest_semantic_errors(payload))

    def test_cross_record_semantic_guard_rejects_broken_links(self):
        mutations = {
            "unknown group cell": lambda payload: payload["ranking_groups"][0].update(
                cell_id="missing-cell"
            ),
            "unknown family cell": lambda payload: payload["benchmark_families"][0][
                "candidate_cells"
            ].append("missing-cell"),
            "unknown feed family": lambda payload: payload["feeds"][0].update(
                benchmark_family_id="missing-family"
            ),
            "feed-family candidate mismatch": lambda payload: payload["feeds"][0][
                "candidate_cells"
            ].append("factuality"),
            # feeds[0] is active; drop it to discovered so its family's derived
            # aggregate state no longer matches the declared active family state.
            "feed-family state mismatch": lambda payload: payload["feeds"][0].update(
                state="discovered", adapter_id=None, metric_direction=None
            ),
            "implemented feed without metric direction": lambda payload: payload[
                "feeds"
            ][0].update(metric_direction=None),
            # v2: rank-eligible counts are allowed on active feeds; the retained
            # rule is that a NON-active feed may not claim them.
            "non-active feed with rank-eligible observations": lambda payload: next(
                feed for feed in payload["feeds"] if feed["state"] == "discovered"
            ).update(rank_eligible_count=1),
            "feed-family entity mismatch": lambda payload: payload["feeds"][0].update(
                entity_kind="unresolved"
            ),
            "feed-group identity mismatch": lambda payload: payload["feeds"][0].update(
                ranking_group_ids=[payload["ranking_groups"][-1]["ranking_group_id"]]
            ),
            "feed-family correlation mismatch": lambda payload: payload["feeds"][0][
                "lineage"
            ].update(
                correlation_status="declared",
                correlated_family_group="wrong-family",
            ),
            # v2: the retained active-cell invariant is that an active
            # (published) cell must still be covered by an active ranking group.
            # Quarantine the sole group of an active cell to violate it.
            "active cell without active group": lambda payload: next(
                group
                for group in payload["ranking_groups"]
                if group["cell_id"] == "factuality"
            ).update(state="quarantined"),
            "group-cell public entity mismatch": lambda payload: next(
                cell
                for cell in payload["cells"]
                if cell["cell_id"] == "function-calling"
            ).update(entity_kinds=["model", "tool"]),
        }

        for name, mutate in mutations.items():
            with self.subTest(name=name):
                candidate = manifest()
                mutate(candidate)
                self.assertTrue(manifest_semantic_errors(candidate))

    def test_multi_feed_family_lifecycle_is_derived_without_lockstep(self):
        payload = manifest()
        family = next(
            row
            for row in payload["benchmark_families"]
            if row["benchmark_family_id"] == "core-bench-reproducibility"
        )
        feeds = [
            row
            for row in payload["feeds"]
            if row["benchmark_family_id"] == family["benchmark_family_id"]
        ]
        self.assertEqual(2, len(feeds))

        feeds[0]["state"] = "shadow"
        feeds[0]["adapter_id"] = "core-mainline-v1"
        feeds[0]["metric_direction"] = "higher"
        family["state"] = "shadow"
        self.assertEqual([], manifest_semantic_errors(payload))

        feeds[1]["state"] = "quarantined"
        feeds[1]["quarantine_reason"] = "OOD feed is not yet replayable."
        self.assertIsNone(family["quarantine_reason"])
        self.assertEqual([], manifest_semantic_errors(payload))

    def test_active_group_publication_is_decoupled_from_independent_validation(self):
        # v2: publication (state) is decoupled from validation. An active
        # (published) ranking group with unvalidated calibration, a null
        # rank-eligible count, and no independent validated families is coherent
        # — the removed rules no longer withhold it. The live manifest already
        # publishes such a group, so it must carry no semantic errors.
        group_id = (
            "rg-code-generation-model-configuration-direct-prompt-"
            "model-configuration-v1"
        )
        baseline = manifest()
        group = next(
            row
            for row in baseline["ranking_groups"]
            if row["ranking_group_id"] == group_id
        )
        self.assertEqual("active", group["state"])
        self.assertEqual("unvalidated", group["eligibility"]["calibration_status"])
        self.assertIsNone(group["rank_eligible_count"])
        self.assertEqual([], manifest_semantic_errors(baseline))

        # The one active-group invariant kept under v2: an active group whose
        # cell is not itself active is still incoherent and must error.
        broken = manifest()
        next(
            cell for cell in broken["cells"] if cell["cell_id"] == "code-generation"
        )["state"] = "preview"
        state_errors = manifest_semantic_errors(broken)
        self.assertTrue(
            any(
                "active ranking group" in error and "cell is not active" in error
                for error in state_errors
            ),
            state_errors,
        )

    def test_manifest_matches_its_closed_public_schema_surface(self):
        payload = manifest()
        schema = load_json(REPO_ROOT / "schemas" / "evalrank-manifest.schema.json")

        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(payload), set(schema["properties"]))
        self.assertEqual(set(payload), set(schema["required"]))
        self.assertEqual("1", schema["properties"]["schema_version"]["const"])

        for rows_key, definition_name in (
            ("cells", "Cell"),
            ("ranking_groups", "RankingGroup"),
            ("benchmark_families", "BenchmarkFamily"),
            ("feeds", "Feed"),
        ):
            definition = schema["$defs"][definition_name]
            self.assertFalse(definition["additionalProperties"])
            for row in payload[rows_key]:
                with self.subTest(rows_key=rows_key, row=row):
                    self.assertEqual(set(row), set(definition["properties"]))
                    self.assertEqual(set(row), set(definition["required"]))

        for feed in payload["feeds"]:
            for key, definition_name in (
                ("rights", "Rights"),
                ("cadence", "Cadence"),
                ("retention", "Retention"),
                ("lineage", "Lineage"),
            ):
                definition = schema["$defs"][definition_name]
                self.assertEqual(set(feed[key]), set(definition["properties"]))
                self.assertEqual(set(feed[key]), set(definition["required"]))

    def test_core_fixture_is_an_exact_manifest_projection(self):
        fixture_rows = sample_use_case_catalog().to_dict()["use_cases"]
        manifest_rows = manifest()["cells"]
        expected_rows = [
            {
                "object": "use_case",
                "id": row["cell_id"],
                "name": row["name"],
                "definition": row["definition"],
                "entity_kinds": row["entity_kinds"],
                "rank_policy": "ranked",
                "is_overlay": False,
            }
            for row in manifest_rows
        ]

        self.assertEqual(expected_rows, fixture_rows)


if __name__ == "__main__":
    unittest.main()
