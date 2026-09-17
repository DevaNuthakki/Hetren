#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "check_success_contracts.py"


def make_repo() -> Path:
    temp = Path(tempfile.mkdtemp(prefix="hetren-success-contract-test-"))

    for relative in (
        "docs/mvp/03-success-contracts.md",
        "docs/decisions/0003-success-contracts.md",
        "docs/decisions/register.md",
    ):
        source = ROOT / relative
        target = temp / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    return temp


def run_validator(
    root: Path,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(root),
            *extra,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def mutate_file(
    root: Path,
    relative: str,
    old: str,
    new: str,
) -> None:
    path = root / relative
    text = path.read_text()

    if old not in text:
        raise AssertionError(f"mutation anchor missing: {old}")

    path.write_text(text.replace(old, new, 1))


def expect_fail(
    name: str,
    mutate,
    expected: str,
) -> None:
    root = make_repo()

    try:
        mutate(root)
        result = run_validator(root)
        output = result.stdout + result.stderr

        if result.returncode == 0:
            raise AssertionError(
                f"{name}: validator unexpectedly passed"
            )

        if expected not in output:
            raise AssertionError(
                f"{name}: expected {expected!r}, got:\n{output}"
            )

        print(f"PASS mutation killed: {name}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def positive_control() -> None:
    root = make_repo()

    try:
        result = run_validator(root)

        if result.returncode != 0:
            raise AssertionError(
                "positive control failed\n"
                f"{result.stdout}{result.stderr}"
            )

        print("PASS positive control")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def set_final_state(root: Path) -> None:
    def ensure_replace(
        relative: str,
        desired: str,
        *alternatives: str,
    ) -> None:
        target = root / relative
        current = target.read_text()

        if desired in current:
            return

        for old in alternatives:
            if old in current:
                target.write_text(
                    current.replace(old, desired, 1)
                )
                return

        raise AssertionError(
            f"final-state fixture anchor missing for {relative}: {desired}"
        )

    ensure_replace(
        "docs/mvp/03-success-contracts.md",
        "**Version:** 1.0.0",
        "**Version:** 0.1.0",
    )

    ensure_replace(
        "docs/mvp/03-success-contracts.md",
        "**Status:** Qualified",
        "**Status:** Requalifying",
        "**Status:** Draft",
    )

    ensure_replace(
        "docs/decisions/0003-success-contracts.md",
        "**Status:** `ACCEPTED`",
        "**Status:** `PROPOSED`",
    )

    ensure_replace(
        "docs/decisions/register.md",
        "| `0003` | `evaluation.success-contracts` | Define shared success-contract semantics | `ACCEPTED` |",
        "| `0003` | `evaluation.success-contracts` | Define shared success-contract semantics | `PROPOSED` |",
    )

    ensure_replace(
        "docs/decisions/0003-success-contracts.md",
        "Implemented and preserved in:\n\n"
        "- `docs/mvp/03-success-contracts.md`;\n"
        "- `scripts/check_success_contracts.py`;\n"
        "- `tests/qualification/test_success_contracts.py`.",
        "Pending Task 3 specification and executable qualification tooling.",
    )

    ensure_replace(
        "docs/decisions/0003-success-contracts.md",
        "Verified by `docs/decisions/qualification/0003-success-contracts.md` "
        "with structural, semantic, adversarial, mutation, authority, regression, "
        "and accepted-state qualification.",
        "Pending Task 3 positive, semantic, adversarial, mutation, authority-alignment,\n"
        "and regression qualification.",
    )

    qualification_path = (
        root
        / "docs/decisions/qualification/0003-success-contracts.md"
    )
    qualification_path.parent.mkdir(parents=True, exist_ok=True)
    qualification_path.write_text(
        "# Decision 0003 Qualification Record\n\n"
        "**Task:** `3 / 100`\n"
        "**Decision:** `0003`\n"
        "**Decision Key:** `evaluation.success-contracts`\n"
        "**Date:** `2026-09-17`\n"
        "**Result:** `PASS`\n"
        "**Qualification state:** `VERIFIED`\n"
        "**Specification:** `docs/mvp/03-success-contracts.md`\n"
        "**Specification version:** `1.0.0`\n"
        "**Validator:** `scripts/check_success_contracts.py`\n"
        "**Mutation suite:** `tests/qualification/test_success_contracts.py`\n"
        "**Qualification conditions:** `40 / 40`\n"
        "**Mutation result:** `25 / 25`\n"
        "**Execution authority:** `AUTH-HETREN-MVP-3.0`\n"
        "**Long-term authority:** `AUTH-HETREN-MASTER-2.0`\n"
        "**Task 1 regression:** `PASS`\n"
        "**Task 2 regression:** `PASS`\n"
        "**Diff check:** `PASS`\n"
        "**Final accepted-state qualification:** `PASS`\n\n"
        "## Scope\n\nTask 3 success-contract qualification.\n\n"
        "## Positive Qualification\n\nPASS.\n\n"
        "## Structural Qualification\n\nPASS.\n\n"
        "## Semantic Qualification\n\nPASS.\n\n"
        "## Adversarial Qualification\n\nPASS.\n\n"
        "## Authority And Regression Qualification\n\nPASS.\n\n"
        "## Limitations\n\nNo scientific hypothesis is established by this qualification.\n\n"
        "## Acceptance Decision\n\nDecision 0003 accepted-state qualification: PASS.\n"
    )


def final_positive_control() -> None:
    root = make_repo()
    try:
        set_final_state(root)
        result = run_validator(root, "--require-qualified")
        if result.returncode != 0:
            raise AssertionError(
                "final-state positive control failed\n"
                f"{result.stdout}{result.stderr}"
            )
        print("PASS final-state positive control")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def expect_final_fail(name: str, mutate, expected: str) -> None:
    root = make_repo()
    try:
        set_final_state(root)
        mutate(root)
        result = run_validator(root, "--require-qualified")
        output = result.stdout + result.stderr
        if result.returncode == 0:
            raise AssertionError(
                f"{name}: final validator unexpectedly passed"
            )
        if expected not in output:
            raise AssertionError(
                f"{name}: expected {expected!r}, got:\n{output}"
            )
        print(f"PASS final mutation killed: {name}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    positive_control()
    final_positive_control()

    expect_fail(
        "wrong MVP execution authority",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "**Execution authority:** `AUTH-HETREN-MVP-3.0`",
            "**Execution authority:** `AUTH-HETREN-MVP-9.9`",
        ),
        "success-contract metadata Execution authority",
    )

    expect_fail(
        "section topology changed",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "## 24. Independent Verification",
            "## 24. Optional Verification",
        ),
        "exactly ordered sections 1 through 29",
    )

    expect_fail(
        "evaluation outcome vocabulary expanded",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "- `INVALID`",
            "- `INVALID`\n- `UNKNOWN`",
        ),
        "evaluation outcome vocabulary must be exactly",
    )

    expect_fail(
        "condition 11 invalid-evidence protection weakened",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "11. invalid evidence cannot establish either `PASS` or `FAIL`;",
            "11. invalid evidence should usually be reviewed;",
        ),
        "Task 3 qualification condition 11 missing required semantics",
    )

    expect_fail(
        "condition 18 non-compensatory protection weakened",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "18. hard constraints and invariants are non-compensatory and cannot be",
            "18. hard constraints and invariants may sometimes be traded and can be",
        ),
        "Task 3 qualification condition 18 missing required semantics",
    )

    expect_fail(
        "condition 28 adaptive self-certification protection removed",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "28. no Adaptive Intelligence candidate may be the sole authority certifying",
            "28. an Adaptive Intelligence candidate may be the sole authority certifying",
        ),
        "Task 3 qualification condition 28 missing required semantics",
    )

    expect_fail(
        "condition 37 contract omission protection removed",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "37. authority-required acceptance predicates, constraints, invariants, budgets",
            "37. optional acceptance predicates, constraints, invariants, and budgets",
        ),
        "Task 3 qualification condition 37 missing required semantics",
    )

    expect_fail(
        "condition 38 consequential relabeling protection removed",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "38. consequential-claim requirements cannot be bypassed merely by labeling a",
            "38. consequential-claim requirements can be bypassed merely by labeling a",
        ),
        "Task 3 qualification condition 38 missing required semantics",
    )

    expect_fail(
        "condition 39 deterministic resolution removed",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "39. primary outcome resolution is deterministic when valid failure, invalid",
            "39. primary outcome resolution is discretionary when valid failure, invalid",
        ),
        "Task 3 qualification condition 39 missing required semantics",
    )

    expect_fail(
        "contract completeness weakened",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "Contract completeness is governed by applicable authority",
            "Contract completeness is chosen only by the contract author",
        ),
        "section 5",
    )

    expect_fail(
        "protected threshold anti-gaming removed",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "A failed protected result may not be converted into `PASS`",
            "A failed protected result may be converted into `PASS`",
        ),
        "section 14",
    )

    expect_fail(
        "adaptive candidate self-certification allowed",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "No adaptive candidate may certify its own scientific success.",
            "An adaptive candidate may certify its own scientific success.",
        ),
        "section 21",
    )

    expect_fail(
        "transfer claim separation removed",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "These are not interchangeable claims.",
            "These are interchangeable claims.",
        ),
        "section 22",
    )

    expect_fail(
        "verification candidate freeze removed",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "The candidate under consequential verification must be frozen sufficiently to",
            "The candidate under consequential verification may change freely to",
        ),
        "section 24",
    )

    expect_fail(
        "unsupported treated as extra outcome state",
        lambda root: mutate_file(
            root,
            "docs/mvp/03-success-contracts.md",
            "They are not additional\nevaluation outcome states.",
            "They are additional\nevaluation outcome states.",
        ),
        "section 25",
    )

    expect_fail(
        "Decision 0003 authority drift",
        lambda root: mutate_file(
            root,
            "docs/decisions/0003-success-contracts.md",
            "**Authority:** `AUTH-HETREN-MVP-3.0`",
            "**Authority:** `AUTH-HETREN-MVP-9.9`",
        ),
        "Decision 0003 metadata Authority",
    )

    expect_fail(
        "Decision 0003 register status mismatch",
        lambda root: mutate_file(
            root,
            "docs/decisions/register.md",
            "| `0003` | `evaluation.success-contracts` | Define shared success-contract semantics | `ACCEPTED` |",
            "| `0003` | `evaluation.success-contracts` | Define shared success-contract semantics | `PROPOSED` |",
        ),
        "Decision 0003 register status must match record status",
    )

    expect_final_fail(
        "qualification record missing",
        lambda root: (
            root
            / "docs/decisions/qualification/0003-success-contracts.md"
        ).unlink(),
        "missing Decision 0003 qualification evidence",
    )

    expect_final_fail(
        "qualification Task drift",
        lambda root: mutate_file(
            root,
            "docs/decisions/qualification/0003-success-contracts.md",
            "**Task:** `3 / 100`",
            "**Task:** `4 / 100`",
        ),
        "qualification metadata Task",
    )

    expect_final_fail(
        "qualification conditions incomplete",
        lambda root: mutate_file(
            root,
            "docs/decisions/qualification/0003-success-contracts.md",
            "**Qualification conditions:** `40 / 40`",
            "**Qualification conditions:** `39 / 40`",
        ),
        "qualification metadata Qualification conditions",
    )

    expect_final_fail(
        "mutation qualification incomplete",
        lambda root: mutate_file(
            root,
            "docs/decisions/qualification/0003-success-contracts.md",
            "**Mutation result:** `25 / 25`",
            "**Mutation result:** `24 / 25`",
        ),
        "requires all recorded mutations to be rejected",
    )

    expect_final_fail(
        "qualification state not verified",
        lambda root: mutate_file(
            root,
            "docs/decisions/qualification/0003-success-contracts.md",
            "**Qualification state:** `VERIFIED`",
            "**Qualification state:** `DRAFT`",
        ),
        "qualification metadata Qualification state",
    )

    expect_final_fail(
        "implementation evidence returned to pending",
        lambda root: mutate_file(
            root,
            "docs/decisions/0003-success-contracts.md",
            "Implemented and preserved in:",
            "Pending implementation evidence preserved in:",
        ),
        "Implementation Evidence remains pending",
    )

    expect_final_fail(
        "verification evidence returned to pending",
        lambda root: mutate_file(
            root,
            "docs/decisions/0003-success-contracts.md",
            "Verified by `docs/decisions/qualification/0003-success-contracts.md`",
            "Pending verification by `docs/decisions/qualification/0003-success-contracts.md`",
        ),
        "Verification Evidence remains pending",
    )

    expect_final_fail(
        "qualification specification version mismatch",
        lambda root: mutate_file(
            root,
            "docs/decisions/qualification/0003-success-contracts.md",
            "**Specification version:** `1.0.0`",
            "**Specification version:** `1.1.0`",
        ),
        "Specification version must match success-contract Version",
    )


    print("SUCCESS CONTRACT MUTATION SUITE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
