# The portfolio slice

Moved here from the repository README (as of `4f1fcc1`) when the README was rewritten for the v1.0.0 release: the text is unchanged. The sections describe the deterministic portfolio slice the repository began with; Milestone 1 is in `docs/milestone-1/README.md`.

Hetren is an engineering portfolio project exploring evidence-driven diagnosis and bounded repair for tool-using AI-agent behavior.

The current executable slice is deliberately small and deterministic. It demonstrates explicit boundaries between diagnosis, repair, execution, evaluation, verification, policy review, provenance, and reproducibility without claiming general autonomous repair.

## Executable slice

```text
visible failure
    -> diagnosis
    -> bounded repair
    -> candidate execution
    -> evaluation
    -> separate verification
    -> eligibility policy
```

Two controlled faults are demonstrated:

```text
tool_selection -> tool_selection_fault -> replace_tool
parameter_transformation -> parameter_transformation_fault -> override_parameter
```

The slice deliberately preserves these distinctions:

```text
PASS != VERIFIED
VERIFIED != automatically ELIGIBLE
ELIGIBLE != authorized
ELIGIBLE != deployment approval
```

## Quick start

Use Python 3.12 (the version CI uses) in a virtual environment and install the pinned development dependencies (`jsonschema==4.26.0`, `openai==3.42.0`, `openai-agents==0.24.0`, `pytest==9.0.3`):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Run the modern test suite:

```bash
python -m pytest -q
```

Run the reviewer-facing demonstration:

```bash
python -m packages.portfolio_demo
```

Generate deterministic machine-readable evidence:

```bash
python -m packages.portfolio_demo --format json
```

## Validation boundaries

Pytest owns the modern portfolio tests under `tests/unit` and `tests/integration`.

The earlier qualification system under `tests/qualification` remains script-driven and is executed directly together with its `scripts/check_*` validators.

Historical evidence snapshots under `docs/decisions/...` are preservation artifacts, not live pytest targets.

## Key surfaces

- `packages/contracts/` — provenance and governance contracts
- `packages/core/hetren_diagnosis/` — diagnosis lifecycle and planner
- `packages/engines/behavioral/` — deterministic agent environment and repair execution
- `packages/verification/` — verification and eligibility orchestration
- `packages/portfolio_demo.py` — reproducible executable demonstration
- `tests/unit/` — contract, lifecycle, and planner tests
- `tests/integration/` — executable vertical-slice tests
- `docs/portfolio/` — design rationale and claim boundaries

## Reproducibility

The committed repository reproduces the portfolio demonstration without the historical Task 8/9 working material, which is preserved on the `archive/sept-2026-evidence` branch.

The deterministic JSON report contains provenance hashes for diagnosis, repair, candidate identity, execution, evaluation, verification, policy review, and the final report.

## Claim limits

The current implementation does not establish repair of arbitrary AI agents, general autonomous program repair, external LLM repair quality, production safety, infrastructure independence, deployment approval, or universal candidate correctness.

Separate records and provenance references demonstrate procedural separation; they do not by themselves prove stronger forms of independence.

## Portfolio direction

Future work should deepen the environment and evaluation challenge rather than add unnecessary product or lifecycle abstractions.
