#!/usr/bin/env python3
"""Guard the public EvalRank repo boundary."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PRIVATE_IMPORT_PREFIXES = (
    "apps",
    "backend",
    "mobile",
    "syndai",
    "web",
)
DISALLOWED_IMPORT_PREFIXES = {
    "smithery": "smithery-import",
}
MIN_K_MARKERS = (
    "min_k",
    "min-k",
    "mink",
    "min_k_percent",
    "min-k-percent",
)
SECRET_FILENAMES = {
    ".env",
    "credentials.json",
    "doppler.yaml",
    "doppler.yml",
    "secrets.toml",
    "service-role-key.json",
}
PUBLIC_ENV_FILENAMES = {".env.example", ".env.sample"}
SECRET_SUFFIXES = {".key", ".pem", ".p8"}
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
)
# Private runtime internals that must never be named in the public repo. Each
# pattern targets a concrete private identity (a private system, a private DB
# role/table, or a private migration id) — not neutral English. The boundary
# checker and its own tests legitimately contain these strings as patterns and
# fixtures, so they are exempted via PRIVATE_INTERNAL_EXEMPT_FILES.
PRIVATE_INTERNAL_TERM_PATTERNS = (
    (re.compile(r"\bSyndai\b", re.IGNORECASE), "names the private runtime 'Syndai'"),
    (re.compile(r"\bFinn\b", re.IGNORECASE), "names the private system 'Finn'"),
    (re.compile(r"\bSavida\b", re.IGNORECASE), "names the private system 'Savida'"),
    (re.compile(r"\bSupabase\b", re.IGNORECASE), "names the private datastore vendor 'Supabase'"),
    (re.compile(r"\bStripe\b", re.IGNORECASE), "names the private billing vendor 'Stripe'"),
    (re.compile(r"\bpgmq\b", re.IGNORECASE), "names the private queue 'pgmq'"),
    (re.compile(r"\bDoppler\b", re.IGNORECASE), "names the private secrets manager 'Doppler'"),
    (re.compile(r"\bevalrank_cron\b", re.IGNORECASE), "names the private DB role 'evalrank_cron'"),
    (re.compile(r"\bevalrank_app\b", re.IGNORECASE), "names the private DB role 'evalrank_app'"),
    (re.compile(r"\bbudget_ledger\b", re.IGNORECASE), "names the private table 'budget_ledger'"),
    (re.compile(r"\bsource_cursors\b", re.IGNORECASE), "names the private table 'source_cursors'"),
    (re.compile(r"\bmanifest_feed_cadence\b", re.IGNORECASE), "names the private table 'manifest_feed_cadence'"),
    (re.compile(r"\bfeed_refresh_interval\b", re.IGNORECASE), "names the private table 'feed_refresh_interval'"),
    (re.compile(r"\btruth_kernel_state\b", re.IGNORECASE), "names the private table 'truth_kernel_state'"),
    (re.compile(r"\bparser_run_freshness\b", re.IGNORECASE), "names the private table 'parser_run_freshness'"),
    # Private migration id: YYYY_MM_DD_NNN_
    (re.compile(r"\b20\d\d_\d\d_\d\d_\d\d\d_"), "embeds a private migration id (YYYY_MM_DD_NNN_)"),
    # Row-level-security is a private DB access-control internal.
    (re.compile(r"\bRLS\b"), "references private row-level-security (RLS) internals"),
    (re.compile(r"\brow[\s-]?level[\s-]security\b", re.IGNORECASE), "references private row-level security"),
)
# The checker and its tests are the one place these strings must live.
PRIVATE_INTERNAL_EXEMPT_FILES = {
    "scripts/check_public_boundary.py",
    "tests/test_public_boundary.py",
    "tests/test_repo_docs.py",
}

SCANNED_FILENAMES = {"Makefile"}
PRIVATE_DATA_PATH_MARKERS = (
    "customer-data",
    "customer_data",
    "evidence-rows",
    "evidence_rows",
    "held-out",
    "heldout",
    "private-fixture",
    "private_fixture",
    "prod-telemetry",
    "prod_telemetry",
    "production-telemetry",
)
SCANNED_SUFFIXES = {".js", ".json", ".jsx", ".md", ".toml", ".ts", ".tsx", ".py", ".yaml", ".yml"}
IGNORED_DIRS = {
    ".claude",
    ".codex",
    ".git",
    ".impeccable",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


@dataclass(frozen=True)
class Violation:
    code: str
    path: str
    message: str


def check_repository(root: Path | str) -> Iterable[Violation]:
    root = Path(root).resolve()
    yield from _check_root_contract(root)
    yield from _check_package_contract(root)
    for path in _iter_files(root):
        yield from _check_public_path(root, path)
        if _should_scan_content(path):
            yield from _check_secret_values(root, path)
            yield from _check_private_internal_terms(root, path)
            yield from _check_python_imports(root, path)
            if _is_implementation_file(root, path):
                yield from _check_disallowed_markers(root, path)


def _check_root_contract(root: Path) -> Iterable[Violation]:
    for filename, code in (("LICENSE", "missing-root-license"), ("NOTICE", "missing-root-notice")):
        if not (root / filename).is_file():
            yield Violation(code, filename, f"Repository root must include {filename}.")


def _check_package_contract(root: Path) -> Iterable[Violation]:
    packages_root = root / "packages"
    if not packages_root.is_dir():
        return

    for package in sorted(path for path in packages_root.iterdir() if path.is_dir()):
        if not _has_package_content(package):
            continue
        for filename, code in (("LICENSE", "missing-package-license"), ("NOTICE", "missing-package-notice")):
            if not (package / filename).is_file():
                rel = _relative_to(root, package / filename)
                yield Violation(code, rel, f"Public package {package.name} must include {filename}.")


def _has_package_content(package: Path) -> bool:
    for path in package.rglob("*"):
        if _is_ignored(path):
            continue
        if path.is_file() and path.name not in {"LICENSE", "NOTICE"}:
            return True
    return False


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if _is_ignored(path):
            continue
        if path.is_file():
            yield path


def _should_scan_content(path: Path) -> bool:
    return path.name in SCANNED_FILENAMES or path.suffix.lower() in SCANNED_SUFFIXES or _is_secret_file(path)


def _check_public_path(root: Path, path: Path) -> Iterable[Violation]:
    rel = _relative_to(root, path)
    if _is_secret_file(path) or path.suffix.lower() in SECRET_SUFFIXES:
        yield Violation("secret-file", rel, "Public repo must not contain secret or credential files.")
    normalized_parts = [part.lower().replace(" ", "-") for part in path.relative_to(root).parts]
    if any(marker in part for marker in PRIVATE_DATA_PATH_MARKERS for part in normalized_parts):
        yield Violation("private-data-path", rel, "Public repo must not contain held-out/private fixture or production data paths.")


def _is_secret_file(path: Path) -> bool:
    name = path.name.lower()
    if name in SECRET_FILENAMES:
        return True
    return name.startswith(".env.") and name not in PUBLIC_ENV_FILENAMES


def _is_implementation_file(root: Path, path: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    if path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
        return False
    return len(rel_parts) >= 4 and rel_parts[0] == "packages" and rel_parts[2] == "src"


def _check_python_imports(root: Path, path: Path) -> Iterable[Violation]:
    if path.suffix != ".py":
        return
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        yield Violation("python-syntax-error", _relative_to(root, path), str(exc))
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield from _classify_import(root, path, alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield from _classify_import(root, path, node.module)


def _classify_import(root: Path, path: Path, module: str) -> Iterable[Violation]:
    top_level = module.split(".", 1)[0]
    rel = _relative_to(root, path)
    if top_level in PRIVATE_IMPORT_PREFIXES:
        yield Violation("private-import", rel, f"Public code imports private namespace '{module}'.")
    disallowed = DISALLOWED_IMPORT_PREFIXES.get(top_level)
    if disallowed:
        yield Violation(disallowed, rel, f"Public code imports disallowed dependency '{module}'.")


def _check_secret_values(root: Path, path: Path) -> Iterable[Violation]:
    rel = _relative_to(root, path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(text):
            yield Violation("secret-value", rel, "Public repo must not contain high-signal secret values.")
            return


def _check_private_internal_terms(root: Path, path: Path) -> Iterable[Violation]:
    rel = _relative_to(root, path)
    if rel in PRIVATE_INTERNAL_EXEMPT_FILES:
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern, reason in PRIVATE_INTERNAL_TERM_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            yield Violation(
                "private-internal-leak",
                rel,
                f"Public file {reason} ('{match.group(0)}'); private runtime internals must not be named.",
            )


def _check_disallowed_markers(root: Path, path: Path) -> Iterable[Violation]:
    rel = _relative_to(root, path)
    haystack = f"{rel}\n{path.read_text(encoding='utf-8', errors='ignore')}".lower()
    if any(marker in haystack for marker in MIN_K_MARKERS):
        yield Violation(
            "min-k-percent",
            rel,
            "Min-K% is excluded from the public EvalRank core boundary.",
        )


def _is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts)


def _relative_to(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    violations = list(check_repository(args.root))
    for violation in violations:
        print(f"{violation.code}\t{violation.path}\t{violation.message}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
