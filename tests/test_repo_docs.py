import json
import re
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def repository_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [Path(line) for line in result.stdout.splitlines()]


class RepoDocsTests(unittest.TestCase):
    def test_claude_md_is_agents_shim(self):
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

        self.assertEqual("@AGENTS.md\n", text)

    def test_scoped_agents_cover_public_work_areas(self):
        package_dirs = {
            f"packages/{path.parts[1]}"
            for path in repository_paths()
            if len(path.parts) > 2 and path.parts[0] == "packages"
        }
        scoped_dirs = {
            "docs",
            "examples",
            "catalog",
            "methods",
            "packages",
            "schemas",
            "scripts",
            "tests",
            *package_dirs,
        }
        missing = sorted(
            directory
            for directory in scoped_dirs
            if not (REPO_ROOT / directory / "AGENTS.md").is_file()
        )

        self.assertEqual([], missing)

    def test_repo_structure_tracks_public_top_level_directories(self):
        text = (REPO_ROOT / "docs" / "REPO_STRUCTURE.md").read_text(encoding="utf-8")
        top_level_dirs = {path.parts[0] for path in repository_paths() if len(path.parts) > 1}
        expected_refs = {
            ".github": ".github/workflows/",
            "catalog": "catalog/",
            "docs": "docs/",
            "examples": "examples/",
            "methods": "methods/",
            "packages": "packages/",
            "schemas": "schemas/",
            "scripts": "scripts/",
            "tests": "tests/",
        }

        self.assertEqual(set(expected_refs), top_level_dirs)
        missing_refs = {
            directory: ref
            for directory, ref in expected_refs.items()
            if f"`{ref}`" not in text
        }
        self.assertEqual({}, missing_refs)

    def test_repo_structure_lists_package_directories_exactly(self):
        text = (REPO_ROOT / "docs" / "REPO_STRUCTURE.md").read_text(encoding="utf-8")
        documented = set(re.findall(r"`packages/([^`/]+)/`", text))
        expected = {
            path.parts[1]
            for path in repository_paths()
            if len(path.parts) > 2 and path.parts[0] == "packages"
        }

        self.assertEqual(expected, documented)

    def test_status_points_to_current_authorities_without_private_runtime_traces(self):
        text = (REPO_ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8")

        for authority in (
            "docs/PRODUCT.md",
            "catalog/manifest.json",
            "methods/evidence-synthesis.md",
        ):
            self.assertIn(authority, text)
        for forbidden in (
            "Stripe",
            "billing settlement",
            "private table count",
            "live snapshot",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIsNone(
            re.search(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
                text,
                re.I,
            )
        )

    def test_catalog_inventory_docs_follow_canonical_manifest(self):
        manifest = json.loads(
            (REPO_ROOT / "catalog" / "manifest.json").read_text(encoding="utf-8")
        )
        counts = {
            key: len(manifest[key])
            for key in ("cells", "ranking_groups", "benchmark_families", "feeds")
        }
        status = (REPO_ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8")
        tests = (REPO_ROOT / "TESTS.md").read_text(encoding="utf-8")

        self.assertIn(f"Last updated: {manifest['manifest_version'].split('.')[0]}", status)
        self.assertIn(
            f"canonical {counts['cells']}-cell/{counts['ranking_groups']}-ranking-group "
            f"inventory, {counts['benchmark_families']}-family/{counts['feeds']}-feed research queue",
            status,
        )
        self.assertIn(
            f"canonical {counts['cells']}-cell taxonomy, exact "
            f"{counts['benchmark_families']}-family/{counts['feeds']}-feed inventory",
            tests,
        )

    def test_status_mentions_current_porting_workstreams(self):
        status_text = (REPO_ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8")
        porting_text = (REPO_ROOT / "docs" / "PORTING.md").read_text(encoding="utf-8")
        match = re.search(
            r"## Current Workstreams\n\n(?P<body>.*?)(?:\n## |\Z)",
            porting_text,
            re.S,
        )
        self.assertIsNotNone(match)
        workstreams = [
            item.strip()
            for item in re.findall(r"^- ([^:\n]+):", match.group("body"), re.M)
        ]
        missing = [
            workstream for workstream in workstreams if workstream not in status_text
        ]

        self.assertNotEqual([], workstreams)
        self.assertEqual([], missing)

    def test_product_contract_pins_the_user_job_and_decision_boundaries(self):
        text = (REPO_ROOT / "docs" / "PRODUCT.md").read_text(encoding="utf-8")

        for phrase in (
            "## User Job",
            "evaluated configuration",
            "ServingOffer",
            "## Receipt UX",
            "## Catalog And Publication",
            "## Demand Gates",
            "## Explicit Exclusions",
            "There is no predeclared launch cell",
            "cross-cutting safety veto",
        ):
            self.assertIn(phrase, text)

    def test_current_public_plan_contains_only_portable_work(self):
        path = (
            REPO_ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-07-09-evalrank-public-contract-gap-closure.md"
        )
        text = path.read_text(encoding="utf-8")

        for phrase in (
            "portable contracts",
            "catalog/manifest.json",
            "exact ranking groups",
            "clean checkout",
        ):
            self.assertIn(phrase, text.lower())
        for forbidden in (
            "/Users/",
            "Syndai/",
            "Supabase",
            "service role",
            "production deploy",
        ):
            self.assertNotIn(forbidden, text)

    def test_default_check_bootstraps_locked_node_dependencies_once(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        install = "npm ci --prefix packages/sdk-ts"
        check = "make check"

        self.assertIn(install, makefile)
        self.assertIn("packages/sdk-ts/node_modules/.package-lock.json", makefile)
        self.assertIn(check, workflow)
        self.assertNotIn(install, workflow)
        self.assertTrue((REPO_ROOT / "packages" / "sdk-ts" / "package-lock.json").is_file())

        for relative_path in ("AGENTS.md", "README.md", "TESTS.md", "docs/STATUS.md"):
            with self.subTest(relative_path=relative_path):
                text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn(check, text)

    def test_status_reports_public_contract_progress_only(self):
        text = (REPO_ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8")

        required_markers = (
            "## Product Contract",
            "## Current Public Surface",
            "## Evidence State",
            "## Next Public Work",
        )
        missing = [marker for marker in required_markers if marker not in text]

        self.assertEqual([], missing)
        self.assertNotIn("Full-Spec Dashboard", text)
        self.assertNotIn("billing", text.lower())

    def test_public_mcp_docs_do_not_advertise_private_evidence_lookup(self):
        checked_paths = (
            "README.md",
            "packages/mcp/AGENTS.md",
            "packages/mcp/README.md",
        )
        forbidden_phrases = (
            "evidence lookup tools",
            "evidence and evaluation tools",
        )
        offenders = []
        for relative_path in checked_paths:
            text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            for phrase in forbidden_phrases:
                if phrase in text:
                    offenders.append(f"{relative_path}: {phrase}")

        self.assertEqual([], offenders)

    def test_public_route_docs_describe_only_the_receipt_first_contract(self):
        checked_paths = (
            "README.md",
            "packages/sdk-python/README.md",
            "packages/sdk-ts/README.md",
            "packages/cli/README.md",
            "packages/mcp/README.md",
            "docs/STATUS.md",
            "docs/PORTING.md",
        )

        for relative_path in checked_paths:
            text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(relative_path=relative_path):
                for retired in (
                    "/v1/recommendations",
                    "/v1/scoring-stages",
                    "recommendation_not_published",
                    "invalid_evaluation_request",
                ):
                    self.assertNotIn(retired, text)

        root = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("POST /v1/decisions", root)
        self.assertIn("GET /v1/benchmark-health", root)
        self.assertIn("GET /v1/decisions/{receipt_id}", root)
        self.assertIn("?share=true", root)

    def test_tests_map_uses_current_decision_receipt_contract(self):
        text = (REPO_ROOT / "TESTS.md").read_text(encoding="utf-8")

        self.assertIn("DecisionQueryV1", text)
        self.assertIn("DecisionReceiptV1", text)
        self.assertIn("tests/test_reference_server_e2e.py", text)


if __name__ == "__main__":
    unittest.main()
