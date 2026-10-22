# EvalRank Repo Structure

This repo is the public core. Runtime persistence and hosted operation are maintained in a separate private system, along with production evidence data, held-out fixtures, and billing/admin internals; those stay out of this repo.

## Root

- `README.md` explains the project and high-level boundaries.
- `AGENTS.md` is the root agent contract.
- `CLAUDE.md` stays a one-line shim to `@AGENTS.md`.
- `NAVIGATION.md` maps public route contract entrypoints.
- `TESTS.md` maps runnable checks.
- `Makefile` owns the default local `make check` gate.
- `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, and `SECURITY.md` are public-repo hygiene files.

## Code And Packages

- `packages/` owns public package workspaces.
- `packages/core/` owns portable Python contracts and shared public behavior.
- `packages/mcp/` owns the public MCP adapter boundary.
- `packages/cli/` owns scriptable command-line workflows.
- `packages/sdk-python/` owns the Python SDK package boundary.
- `packages/sdk-ts/` owns the TypeScript SDK package boundary.

Package directories should keep their own `README.md`, `LICENSE`, `NOTICE`, and scoped `AGENTS.md`.

## Public Contracts

- `catalog/` owns the canonical public cell, benchmark-family, feed, governance, cadence, lineage, and eligibility manifest.
- `schemas/` owns public JSON Schema contracts and the public OpenAPI route/error contract.
- `methods/` owns public methodology notes and exclusion boundaries.
- `boards/` owns EvalRank's own open benchmark boards: a stdlib harness, its method README and the published `results.json` per board (today `boards/content-safety-classification/`).
- `examples/` owns public runnable examples.

The catalog and schemas define portable interoperability policy, not private storage tables.

## Project Docs

- `docs/` owns public project docs, build logs, and public-safe agent plans.
- `docs/STATUS.md` is the living progress tracker.
- `docs/REPO_STRUCTURE.md` is this directory ownership map.
- `docs/PORTING.md` maps what should be ported from private workstreams and what must stay private.
- `docs/PORTING.md` also routes private-side EvalRank changes to the correct public or private workstream before any port starts.
- `docs/build-log/` stores dated progress, build-order, and port-over snapshots. Entries must be public-safe summaries, not raw private planning text.
- `docs/superpowers/plans/` stores public-safe implementation plans for agentic work.
- `docs/AGENTS.md` gives scoped doc-editing rules.
- Adjacent private planning areas are not EvalRank directories. Route them through `docs/PORTING.md` only when an explicit EvalRank storage-free contract is extracted.

## Tests And Scripts

- `tests/` owns stdlib `unittest` coverage.
- `scripts/` owns deterministic repo maintenance scripts.
- `.github/workflows/` owns public CI.

## When To Add Files

- Add a scoped `AGENTS.md` when a directory has local ownership rules or commands.
- Add or update `TESTS.md` when checks change.
- Update `NAVIGATION.md` when public API routes, UI routes, deeplinks, or navigation-critical docs change.
- Update `docs/PORTING.md` before moving private work into this repo.
- Add a dated build log when progress status, build order, or porting ownership changes.
- Do not add private data, secrets, private fixtures, or production evidence rows anywhere in this repo.
- Do not add persistence/migration directories until EvalRank owns its own deploy path or its own hosted project.
