import json
import re
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "packages" / "core" / "src"
SDK_TS = REPO_ROOT / "packages" / "sdk-ts"
sys.path.insert(0, str(CORE_SRC))

from evalrank_core.contracts import (  # noqa: E402
    PROBLEM_CODES,
    USE_CASE_ENTITY_KINDS,
    USE_CASE_RANK_POLICIES,
)
from evalrank_core.fixtures import PUBLIC_FIXTURE_KINDS  # noqa: E402


class TypeScriptSdkTests(unittest.TestCase):
    def test_retired_route_and_result_vocabulary_is_absent(self):
        source = (SDK_TS / "src" / "index.ts").read_text(encoding="utf-8")
        for retired in (
            "ResultRow",
            "result-row",
            "/v1/recommendations",
            "/v1/scoring-stages",
            "async recommend(",
            "async scoringStages(",
            "RecommendationBase",
            "ScoringStageCatalog",
            "EvaluationRequest",
            "COMPARABILITY_MODES",
            "THE_CALL_DECISIONS",
            "interface Abstention",
            "recommendation_not_published",
            "invalid_evaluation_request",
            "interface CandidateSet",
            "interface EvidenceItem",
            "interface EvidenceSet",
            "interface Exclusion",
            "interface RankedEntity",
            "interface RankingGroup",
            "interface StageCandidate",
        ):
            self.assertNotIn(retired, source)

    def test_sdk_readme_lists_current_decision_and_read_surface(self):
        text = (SDK_TS / "README.md").read_text(encoding="utf-8")
        for name in (
            "DecisionQueryV2",
            "DecisionReceiptV2",
            "BenchmarkHealth",
            "Leaderboard",
            "EntityDetail",
            "CompareResult",
            "EvalRankClient",
            "EvalRankApiError",
            "PUBLIC_FIXTURE_KINDS",
            "AggregationInputDocument",
            "deriveAggregationInputDigest",
        ):
            self.assertIn(name, text)
        self.assertNotIn("recommendation_not_published", text)
        self.assertNotRegex(text, r"(?m)\.recommend\(")

    def test_package_metadata_exposes_public_typescript_entrypoint(self):
        package = json.loads((SDK_TS / "package.json").read_text(encoding="utf-8"))

        self.assertEqual("@evalrank/sdk", package["name"])
        self.assertEqual("0.0.0", package["version"])
        self.assertEqual("Apache-2.0", package["license"])
        self.assertTrue(package["private"])
        self.assertEqual("module", package["type"])
        self.assertEqual("./src/index.ts", package["types"])
        self.assertEqual("./src/index.ts", package["exports"]["."]["types"])
        self.assertEqual("./src/index.ts", package["exports"]["."]["default"])
        self.assertIn("decision-contracts.ts", package["scripts"]["check"])
        self.assertIn("index.test.ts", package["scripts"]["test"])

    def test_public_constants_match_core_contracts(self):
        source = (SDK_TS / "src" / "index.ts").read_text(encoding="utf-8")
        self.assertIn('export * from "./decision-contracts.ts";', source)
        self.assertIn('export * from "./aggregation-identity.ts";', source)

        self.assertEqual(PROBLEM_CODES, _exported_string_array(source, "PROBLEM_CODES"))
        self.assertEqual(USE_CASE_ENTITY_KINDS, _exported_string_array(source, "USE_CASE_ENTITY_KINDS"))
        self.assertEqual(USE_CASE_RANK_POLICIES, _exported_string_array(source, "USE_CASE_RANK_POLICIES"))
        self.assertEqual(set(PUBLIC_FIXTURE_KINDS), _exported_string_array(source, "PUBLIC_FIXTURE_KINDS"))

    def test_public_interfaces_and_client_cover_all_launch_routes(self):
        source = (SDK_TS / "src" / "index.ts").read_text(encoding="utf-8")
        decision_source = (SDK_TS / "src" / "decision-contracts.ts").read_text(encoding="utf-8")

        for name in (
            "BenchmarkHealth",
            "Leaderboard",
            "EntityDetail",
            "CompareResult",
            "ProblemDetails",
            "UseCaseCatalog",
        ):
            self.assertIn(f"export interface {name}", source)
        for name in ("DecisionQueryV2", "DecisionReceiptV2"):
            self.assertIn(f"export interface {name}", decision_source)

        for method in (
            "async useCases(): Promise<UseCaseCatalog>",
            "async benchmarkHealth(): Promise<BenchmarkHealth>",
            "async leaderboard(useCase: string): Promise<Leaderboard>",
            "async entity(",
            "async compare(useCase: string, entities: string[], explorerView?: ExplorerViewIdentity): Promise<CompareResult>",
            "async decide(",
            "async decisionReceipt(receiptId: string): Promise<DecisionReceiptV2>",
        ):
            self.assertIn(method, source)
        for path in (
            "/v1/use-cases",
            "/v1/benchmark-health",
            "/v1/leaderboard/",
            "/v1/entities/",
            "/v1/compare?",
            "/v1/decisions",
        ):
            self.assertIn(path, source)

        self.assertIn("parseDecisionQueryV2(query)", source)
        self.assertIn("parseDecisionReceiptV2(response)", source)
        self.assertIn("verifyLeaderboardSemantics(response)", source)
        self.assertIn("verifyEntityDetailSemantics(response)", source)
        self.assertIn("verifyCompareResultSemantics(response)", source)
        self.assertIn("verifyBenchmarkHealthSemantics(", source)
        self.assertIn("export type ProblemCode = (typeof PROBLEM_CODES)[number];", source)
        self.assertIn("export type PublicFixtureKind = (typeof PUBLIC_FIXTURE_KINDS)[number];", source)
        self.assertIn("export type NonEmptyArray<T> = [T, ...T[]];", source)


def _exported_string_array(source: str, name: str) -> set[str]:
    match = re.search(rf"export const {name} = \[(?P<body>.*?)\] as const;", source, re.S)
    if not match:
        raise AssertionError(f"{name} export not found")
    return set(re.findall(r'"([^"]+)"', match.group("body")))


if __name__ == "__main__":
    unittest.main()
