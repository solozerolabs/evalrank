import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PublicExampleTests(unittest.TestCase):
    def test_public_fixture_example_prints_current_public_fixture_surface(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "examples" / "public_fixture.py")],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(
            [
                "fingerprint",
                "observation",
                "problem",
                "raw_entry",
                "use_cases",
            ],
            sorted(payload),
        )
        self.assertNotIn("request", payload)
        self.assertEqual("capability_fingerprint", payload["fingerprint"]["object"])
        self.assertEqual("observation", payload["observation"]["object"])
        self.assertEqual("raw_entry", payload["raw_entry"]["object"])
        self.assertEqual("use_case_catalog", payload["use_cases"]["object"])
        self.assertEqual("validation", payload["problem"]["code"])

    def test_public_fixture_readme_lists_current_output_keys(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "examples" / "public_fixture.py")],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        readme = (REPO_ROOT / "examples" / "README.md").read_text(encoding="utf-8")
        for key in sorted(payload):
            with self.subTest(key=key):
                self.assertIn(f"`{key}`", readme)

    def test_examples_document_the_decision_golden_instead_of_legacy_outputs(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "examples" / "public_fixture.py")],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        readme = (REPO_ROOT / "examples" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("recommendation", payload)
        self.assertNotIn("scoring_stages", payload)
        for ref in ("decision-contract-v2.golden.json", "DecisionQueryV2", "DecisionReceiptV2", "build_decision_golden.py"):
            with self.subTest(ref=ref):
                self.assertIn(ref, readme)


if __name__ == "__main__":
    unittest.main()
