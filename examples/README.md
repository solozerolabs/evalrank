# Examples

Runnable public examples use synthetic, product-neutral fixtures only.

## Public Fixture

```sh
python3 examples/public_fixture.py
```

The command emits `fingerprint`, `observation`, `problem`, `raw_entry`, and `use_cases`.

## Decision Golden

`decision-contract-v2.golden.json` is the shared Python/TypeScript corpus for `DecisionQueryV2` restricted-JCS bytes and content-addressed `DecisionReceiptV2` identity: a value pick, a top-set pick, a pinned level, a substituted effort, one abstain per reason, and the `422 via_not_supported` Problem Details example. `scripts/build_decision_golden.py --write` regenerates it from the core contracts and `--check` guards it. The local reference server answers each receipt's exact semantic query with that golden receipt, returns the golden problem for an unprobed `via`, and retains a receipt only when `?share=true` is explicit.

Run the end-to-end contract exerciser with:

```sh
PYTHONPATH=packages/core/src python3 scripts/reference_server.py --port 8000
python3 -m unittest tests.test_reference_server_e2e
```
