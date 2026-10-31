# Archive: September 2026 Evidence

This branch (`archive/sept-2026-evidence`) preserves historical evidence
from the September 2026 Hetren research work. It is **not active code**
and is not part of the portfolio milestone line.

Everything is committed **in place** at its original path, unmodified, so
path references inside the evidence records still resolve.

## Contents

- `docs/research/baselines/`: Task 8 baseline research evidence chain,
  including every versioned attempt record.
- `docs/research/accounting/`: Task 9 accounting, ledger, and resource
  measurement contracts and red-team records.
- `tests/qualification/data/baseline_requirements_gen3/`: gen3 baseline
  qualification data, holdout generation packages, and attempt
  dispositions.
- `tests/qualification/data/task_9_accounting/`: Task 9 accounting
  contract attempts.
- `scripts/*baseline_requirements_gen3*`: the checker and runner scripts
  for the evidence above, including the unchanged `_v2` through `_v10`
  copies.
- `artifacts/`: previously gitignored local outputs (development incident
  reports such as `controls-*.json`, a model capture, and public H1
  protected_v1 records), force-added.

## Intentionally excluded

The evaluator-only files under `artifacts/**/evaluator/` (`raw_seed.bin`,
`hidden_truth_manifest.json`, `execution_v1/evaluator/evaluation.json`)
are not committed, consistent with
`docs/portfolio/h1-protected-v1-generation-freeze.md`. Their hashes are
recorded in the frozen public records.

Nothing on this branch is maintained, imported by active code, or run by CI.
