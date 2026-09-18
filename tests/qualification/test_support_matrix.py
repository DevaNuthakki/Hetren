#!/usr/bin/env python3

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

VALIDATOR = (
    ROOT
    / "scripts"
    / "check_support_matrix.py"
)

SPEC = "docs/mvp/05-support-matrix.md"

DECISION = (
    "docs/decisions/"
    "0005-mvp-support-matrix.md"
)

REGISTER = "docs/decisions/register.md"

QUALIFICATION = (
    "docs/decisions/qualification/"
    "0005-mvp-support-matrix.md"
)

EXPECTED_MUTATIONS = 46
MUTATIONS_KILLED = 0


def make_repo() -> Path:
    temp = Path(
        tempfile.mkdtemp(
            prefix="hetren-support-matrix-test-"
        )
    )

    for relative in (
        SPEC,
        DECISION,
        REGISTER,
    ):
        source = ROOT / relative
        destination = temp / relative

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

    source_qualification = ROOT / QUALIFICATION

    if source_qualification.is_file():
        destination = temp / QUALIFICATION

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source_qualification,
            destination,
        )

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


def replace_once(
    root: Path,
    relative: str,
    old: str,
    new: str,
) -> None:
    target = root / relative
    text = target.read_text()

    if old not in text:
        raise AssertionError(
            "mutation/state anchor missing in "
            f"{relative}: {old}"
        )

    target.write_text(
        text.replace(
            old,
            new,
            1,
        )
    )


def regex_replace_once(
    root: Path,
    relative: str,
    pattern: str,
    replacement: str,
) -> None:
    target = root / relative
    text = target.read_text()

    updated, count = re.subn(
        pattern,
        replacement,
        text,
        count=1,
        flags=re.MULTILINE,
    )

    if count != 1:
        raise AssertionError(
            "regex replacement failed in "
            f"{relative}: {pattern}"
        )

    target.write_text(updated)


def replace_markdown_section(
    root: Path,
    relative: str,
    heading: str,
    body: str,
) -> None:
    target = root / relative
    text = target.read_text()

    pattern = (
        rf"(## {re.escape(heading)}\n)"
        r".*?"
        r"(?=\n## |\Z)"
    )

    replacement = (
        rf"\1"
        + "\n"
        + body.strip()
        + "\n"
    )

    updated, count = re.subn(
        pattern,
        replacement,
        text,
        count=1,
        flags=re.DOTALL,
    )

    if count != 1:
        raise AssertionError(
            "section replacement failed: "
            f"{heading}"
        )

    target.write_text(updated)


def set_spec_metadata(
    root: Path,
    *,
    version: str,
    status: str,
) -> None:
    regex_replace_once(
        root,
        SPEC,
        r"^\*\*Version:\*\* .+$",
        f"**Version:** {version}",
    )

    regex_replace_once(
        root,
        SPEC,
        r"^\*\*Status:\*\* .+$",
        f"**Status:** {status}",
    )


def set_decision_status(
    root: Path,
    status: str,
) -> None:
    regex_replace_once(
        root,
        DECISION,
        r"^\*\*Status:\*\* .+$",
        f"**Status:** `{status}`",
    )


def set_register_status(
    root: Path,
    status: str,
) -> None:
    target = root / REGISTER
    text = target.read_text()

    pattern = re.compile(
        r"(?m)^(\| `0005` "
        r"\| `product\.mvp-support-matrix` "
        r"\| Freeze the initial MVP "
        r"capability-support matrix "
        r"\| `)(PROPOSED|ACCEPTED)(` "
        r"\| `PRODUCT` "
        r"\| `AUTH-HETREN-MVP-3\.0` "
        r"\| `0005-mvp-support-matrix\.md` "
        r"\|)$"
    )

    updated, count = pattern.subn(
        rf"\g<1>{status}\g<3>",
        text,
        count=1,
    )

    if count != 1:
        raise AssertionError(
            "Decision 0005 register status "
            "replacement failed"
        )

    target.write_text(updated)


DEVELOPMENT_IMPLEMENTATION_EVIDENCE = """
Initial specification draft:

- `docs/mvp/05-support-matrix.md`.

Task 5 validator and mutation-suite implementation remain pending while this
decision is `PROPOSED`.
"""


DEVELOPMENT_VERIFICATION_EVIDENCE = """
Pending.

Decision 0005 must remain `PROPOSED` until Task 5 qualification evidence
exists and the accepted-state qualification path can pass without weakening
the declared contract.
"""


FINAL_IMPLEMENTATION_EVIDENCE = """
Implemented and preserved in:

- `docs/mvp/05-support-matrix.md`;
- `scripts/check_support_matrix.py`;
- `tests/qualification/test_support_matrix.py`.
"""


FINAL_VERIFICATION_EVIDENCE = """
Verified by
`docs/decisions/qualification/0005-mvp-support-matrix.md`
with structural, semantic, adversarial, mutation, authority, regression,
and accepted-state qualification.
"""


def write_synthetic_qualification(
    root: Path,
) -> None:
    target = root / QUALIFICATION

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_text(
        """# Decision 0005 Qualification Record

**Task:** `5 / 100`
**Decision:** `0005`
**Decision Key:** `product.mvp-support-matrix`
**Date:** `2026-09-17`
**Result:** `PASS`
**Qualification state:** `VERIFIED`
**Specification:** `docs/mvp/05-support-matrix.md`
**Specification version:** `1.0.0`
**Validator:** `scripts/check_support_matrix.py`
**Mutation suite:** `tests/qualification/test_support_matrix.py`
**Qualification conditions:** `50 / 50`
**Mutation result:** `46 / 46`
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Task 1 regression:** `PASS`
**Task 2 regression:** `PASS`
**Task 3 regression:** `PASS`
**Task 4 regression:** `PASS`
**Diff check:** `PASS`
**Final accepted-state qualification:** `PASS`

## Scope

Synthetic Task 5 accepted-state qualification fixture.

## Positive Qualification

PASS.

## Structural Qualification

PASS.

## Semantic Qualification

PASS.

## Adversarial Qualification

PASS.

## Authority And Regression Qualification

PASS.

## Limitations

This fixture exists only to exercise the accepted-state validator path.

## Acceptance Decision

Decision 0005 is ACCEPTED after qualification.

Final accepted-state qualification: PASS.
"""
    )


def set_development_state(
    root: Path,
) -> None:
    """
    Reconstruct the Task 5 pre-acceptance state.

    This intentionally works whether the source repository
    is currently Draft or has later become Qualified.
    """

    set_spec_metadata(
        root,
        version="0.1.0",
        status="Draft",
    )

    set_decision_status(
        root,
        "PROPOSED",
    )

    set_register_status(
        root,
        "PROPOSED",
    )

    replace_markdown_section(
        root,
        DECISION,
        "Implementation Evidence",
        DEVELOPMENT_IMPLEMENTATION_EVIDENCE,
    )

    replace_markdown_section(
        root,
        DECISION,
        "Verification Evidence",
        DEVELOPMENT_VERIFICATION_EVIDENCE,
    )

    qualification = root / QUALIFICATION

    if qualification.exists():
        qualification.unlink()


def set_final_state(
    root: Path,
) -> None:
    """
    Construct a valid synthetic Task 5 accepted state.

    The synthetic mutation result uses the frozen Task 5
    mutation cardinality of 46 / 46.
    """

    set_spec_metadata(
        root,
        version="1.0.0",
        status="Qualified",
    )

    set_decision_status(
        root,
        "ACCEPTED",
    )

    set_register_status(
        root,
        "ACCEPTED",
    )

    replace_markdown_section(
        root,
        DECISION,
        "Implementation Evidence",
        FINAL_IMPLEMENTATION_EVIDENCE,
    )

    replace_markdown_section(
        root,
        DECISION,
        "Verification Evidence",
        FINAL_VERIFICATION_EVIDENCE,
    )

    write_synthetic_qualification(root)


def positive_control() -> None:
    root = make_repo()

    try:
        set_development_state(root)

        result = run_validator(root)

        if result.returncode != 0:
            raise AssertionError(
                "development positive control failed:\n"
                + result.stdout
                + result.stderr
            )

        print(
            "PASS positive control"
        )
    finally:
        shutil.rmtree(
            root,
            ignore_errors=True,
        )


def final_positive_control() -> None:
    root = make_repo()

    try:
        set_final_state(root)

        result = run_validator(
            root,
            "--require-qualified",
        )

        if result.returncode != 0:
            raise AssertionError(
                "final-state positive control failed:\n"
                + result.stdout
                + result.stderr
            )

        print(
            "PASS final-state positive control"
        )
    finally:
        shutil.rmtree(
            root,
            ignore_errors=True,
        )



def expect_fail(
    name: str,
    mutate,
    expected: str,
) -> None:
    global MUTATIONS_KILLED

    root = make_repo()

    try:
        set_development_state(root)
        mutate(root)

        result = run_validator(root)
        output = result.stdout + result.stderr

        if result.returncode == 0:
            raise AssertionError(
                f"{name}: validator unexpectedly passed"
            )

        if expected not in output:
            raise AssertionError(
                f"{name}: expected {expected!r}, "
                f"got:\n{output}"
            )

        MUTATIONS_KILLED += 1

        print(
            f"PASS mutation killed: {name}"
        )

    finally:
        shutil.rmtree(
            root,
            ignore_errors=True,
        )



def expect_final_fail(
    name: str,
    mutate,
    expected: str,
) -> None:
    global MUTATIONS_KILLED

    root = make_repo()

    try:
        set_final_state(root)
        mutate(root)

        result = run_validator(
            root,
            "--require-qualified",
        )

        output = result.stdout + result.stderr

        if result.returncode == 0:
            raise AssertionError(
                f"{name}: final validator "
                "unexpectedly passed"
            )

        if expected not in output:
            raise AssertionError(
                f"{name}: expected {expected!r}, "
                f"got:\n{output}"
            )

        MUTATIONS_KILLED += 1

        print(
            f"PASS final mutation killed: {name}"
        )

    finally:
        shutil.rmtree(
            root,
            ignore_errors=True,
        )


def remove_qualification(
    root: Path,
) -> None:
    qualification = root / QUALIFICATION

    if not qualification.is_file():
        raise AssertionError(
            "qualification fixture missing before deletion"
        )

    qualification.unlink()


def run_development_mutations() -> None:
    # 1
    expect_fail(
        "specification heading drift",
        lambda root: replace_once(
            root,
            SPEC,
            "# Hetren MVP Support Matrix",
            "# Hetren MVP Capability Matrix",
        ),
        "support-matrix specification heading mismatch",
    )

    # 2
    expect_fail(
        "governing decision metadata drift",
        lambda root: replace_once(
            root,
            SPEC,
            "**Governing decision:** `0005`",
            "**Governing decision:** `0006`",
        ),
        "Task 5 specification metadata Governing decision",
    )

    # 3
    expect_fail(
        "section topology drift",
        lambda root: replace_once(
            root,
            SPEC,
            "## 9. Cross-Domain Behavioral Product Matrix",
            "## 9. Behavioral Product Matrix",
        ),
        "must contain exactly 34 numbered sections",
    )

    # 4
    expect_fail(
        "qualification condition topology drift",
        lambda root: regex_replace_once(
            root,
            SPEC,
            r"^50\.\s+",
            "51. ",
        ),
        "must contain exactly conditions 1 through 50 in order",
    )

    # 5
    expect_fail(
        "manufactured Behavioral support",
        lambda root: replace_once(
            root,
            SPEC,
            "| `E1_AGENT` | `REGRESSION_REPAIR` | "
            "`BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |",
            "| `E1_AGENT` | `REGRESSION_REPAIR` | "
            "`BEHAVIORAL` | `REQUIRED` | "
            "`QUALIFIED_SUPPORTED` |",
        ),
        "Behavioral product matrix must contain exactly",
    )

    # 6
    expect_fail(
        "E1 improvement no longer required",
        lambda root: replace_once(
            root,
            SPEC,
            "| `E1_AGENT` | `CONSTRAINED_IMPROVEMENT` | "
            "`BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |",
            "| `E1_AGENT` | `CONSTRAINED_IMPROVEMENT` | "
            "`BEHAVIORAL` | `PERMITTED` | `UNQUALIFIED` |",
        ),
        "Behavioral product matrix must contain exactly",
    )

    # 7
    expect_fail(
        "E2 repair support fabricated",
        lambda root: replace_once(
            root,
            SPEC,
            "| `E2_STRUCTURED_ML` | `REGRESSION_REPAIR` | "
            "`BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |",
            "| `E2_STRUCTURED_ML` | `REGRESSION_REPAIR` | "
            "`BEHAVIORAL` | `REQUIRED` | "
            "`QUALIFIED_SUPPORTED` |",
        ),
        "Behavioral product matrix must contain exactly",
    )

    # 8
    expect_fail(
        "E2 improvement no longer Behavioral",
        lambda root: replace_once(
            root,
            SPEC,
            "| `E2_STRUCTURED_ML` | "
            "`CONSTRAINED_IMPROVEMENT` | `BEHAVIORAL` | "
            "`REQUIRED` | `UNQUALIFIED` |",
            "| `E2_STRUCTURED_ML` | "
            "`CONSTRAINED_IMPROVEMENT` | "
            "`AUTHORIZED_INTERNAL` | "
            "`REQUIRED` | `UNQUALIFIED` |",
        ),
        "Behavioral product matrix must contain exactly",
    )

    # 9
    expect_fail(
        "E3 repair no longer required",
        lambda root: replace_once(
            root,
            SPEC,
            "| `E3_VISION` | `REGRESSION_REPAIR` | "
            "`BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |",
            "| `E3_VISION` | `REGRESSION_REPAIR` | "
            "`BEHAVIORAL` | `EXCLUDED` | `UNQUALIFIED` |",
        ),
        "Behavioral product matrix must contain exactly",
    )

    # 10
    expect_fail(
        "E3 improvement support fabricated",
        lambda root: replace_once(
            root,
            SPEC,
            "| `E3_VISION` | `CONSTRAINED_IMPROVEMENT` | "
            "`BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |",
            "| `E3_VISION` | `CONSTRAINED_IMPROVEMENT` | "
            "`BEHAVIORAL` | `REQUIRED` | "
            "`QUALIFIED_SUPPORTED` |",
        ),
        "Behavioral product matrix must contain exactly",
    )

    # 11
    expect_fail(
        "CNN Internal support fabricated",
        lambda root: replace_once(
            root,
            SPEC,
            "| small open CNN-family system binding | "
            "`AUTHORIZED_INTERNAL` | `REQUIRED` | `UNQUALIFIED` |",
            "| small open CNN-family system binding | "
            "`AUTHORIZED_INTERNAL` | `REQUIRED` | "
            "`QUALIFIED_SUPPORTED` |",
        ),
        "Internal overlay must contain exactly",
    )

    # 12
    expect_fail(
        "Transformer Internal surface weakened",
        lambda root: replace_once(
            root,
            SPEC,
            "| small open Transformer-family system binding | "
            "`AUTHORIZED_INTERNAL` | `REQUIRED` | `UNQUALIFIED` |",
            "| small open Transformer-family system binding | "
            "`BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |",
        ),
        "Internal overlay must contain exactly",
    )

    # 13
    expect_fail(
        "combined obligation support fabricated",
        lambda root: replace_once(
            root,
            SPEC,
            "| Behavioral and authorized Internal evidence used "
            "within the same governed investigation and decision path "
            "| `REQUIRED` | `UNQUALIFIED` |",
            "| Behavioral and authorized Internal evidence used "
            "within the same governed investigation and decision path "
            "| `REQUIRED` | `QUALIFIED_SUPPORTED` |",
        ),
        "combined Behavioral/Internal obligation",
    )

    # 14
    expect_fail(
        "Internal surface grants permission",
        lambda root: replace_once(
            root,
            SPEC,
            "It does not grant permission.",
            "AUTHORIZED_INTERNAL grants permission.",
        ),
        "Task 5 Internal authorization boundary",
    )

    # 15
    expect_fail(
        "Internal declaration bypasses authorization",
        lambda root: replace_once(
            root,
            SPEC,
            "No Internal support declaration may be used to bypass "
            "authorization.",
            "An Internal support declaration may bypass authorization.",
        ),
        "Task 5 Internal authorization boundary",
    )

    # 16
    expect_fail(
        "one successful execution qualifies support",
        lambda root: replace_once(
            root,
            SPEC,
            "A profile must not infer `QUALIFIED_SUPPORTED` "
            "from one successful execution.",
            "A profile may infer `QUALIFIED_SUPPORTED` "
            "from one successful execution.",
        ),
        "Task 5 CapabilityProfile mapping",
    )

    # 17
    expect_fail(
        "one failed evaluation means unsupported",
        lambda root: replace_once(
            root,
            SPEC,
            "It does not automatically convert the applicable "
            "capability to `UNSUPPORTED`.",
            "It automatically converts the applicable "
            "capability to `UNSUPPORTED`.",
        ),
        "Task 5 failure/support separation",
    )

    # 18
    expect_fail(
        "later support state erases history",
        lambda root: replace_once(
            root,
            SPEC,
            "A later state must not erase the existence "
            "of an earlier state.",
            "A later state may erase the existence "
            "of an earlier state.",
        ),
        "Task 5 capability-state transition governance",
    )

    # 19
    expect_fail(
        "requalification discards prior result",
        lambda root: replace_once(
            root,
            SPEC,
            "Requalification must preserve the previous "
            "qualification result",
            "Requalification may discard the previous "
            "qualification result",
        ),
        "Task 5 invalidation and requalification",
    )

    # 20
    expect_fail(
        "initial Behavioral obligations fabricated supported",
        lambda root: replace_once(
            root,
            SPEC,
            "six Behavioral obligations are `UNQUALIFIED`",
            "six Behavioral obligations are `QUALIFIED_SUPPORTED`",
        ),
        "Task 5 static matrix/current state boundary",
    )

    # 21
    expect_fail(
        "Task 5 completion overclaims capability completion",
        lambda root: replace_once(
            root,
            SPEC,
            "Task 5 completion does not mean that the nine "
            "mandatory capability obligations",
            "Task 5 completion means that the nine "
            "mandatory capability obligations",
        ),
        "Task 5 completion boundary",
    )

    # 22
    expect_fail(
        "Task 6 ownership stolen by Task 5",
        lambda root: replace_once(
            root,
            SPEC,
            "Task 6 owns:",
            "Task 5 owns:",
        ),
        "Task 5 deferred later-task boundaries",
    )

    # 23
    expect_fail(
        "historical semantics silently rewritten",
        lambda root: replace_once(
            root,
            SPEC,
            "Accepted historical Task 5 semantics must not be "
            "silently rewritten in place.",
            "Accepted historical Task 5 semantics may be "
            "silently rewritten in place.",
        ),
        "Task 5 governed extension",
    )

    # 24
    expect_fail(
        "Decision fabricates all nine supports",
        lambda root: replace_once(
            root,
            DECISION,
            "all nine initial mandatory obligations beginning "
            "as `UNQUALIFIED`",
            "all nine initial mandatory obligations beginning "
            "as `QUALIFIED_SUPPORTED`",
        ),
        "Decision 0005 missing required semantic fragment",
    )

    # 25
    expect_fail(
        "Decision permits initial qualified support",
        lambda root: replace_once(
            root,
            DECISION,
            "No initial Task 5 obligation is declared "
            "`QUALIFIED_SUPPORTED`.",
            "Every initial Task 5 obligation is declared "
            "`QUALIFIED_SUPPORTED`.",
        ),
        "Decision 0005 missing required semantic fragment",
    )

    # 26
    expect_fail(
        "Decision weakens qualification criteria",
        lambda root: replace_once(
            root,
            DECISION,
            "Qualification criteria must not be weakened "
            "merely to obtain acceptance.",
            "Qualification criteria may be weakened "
            "to obtain acceptance.",
        ),
        "Decision 0005 missing required semantic fragment",
    )

    # 27
    expect_fail(
        "Decision key drift",
        lambda root: replace_once(
            root,
            DECISION,
            "**Decision Key:** `product.mvp-support-matrix`",
            "**Decision Key:** `product.support-matrix`",
        ),
        "Decision 0005 metadata Decision Key",
    )

    # 28
    expect_fail(
        "register key drift",
        lambda root: replace_once(
            root,
            REGISTER,
            "| `0005` | `product.mvp-support-matrix` |",
            "| `0005` | `product.support-matrix` |",
        ),
        "Decision 0005 register field key must be",
    )

    # 29
    expect_fail(
        "register prematurely accepted",
        lambda root: set_register_status(
            root,
            "ACCEPTED",
        ),
        "decision/register status mismatch",
    )

    # 30
    expect_fail(
        "Decision prematurely accepted",
        lambda root: set_decision_status(
            root,
            "ACCEPTED",
        ),
        "decision/register status mismatch",
    )



def run_final_mutations() -> None:
    # 31
    expect_final_fail(
        "qualification record missing",
        remove_qualification,
        "missing Decision 0005 qualification evidence",
    )

    # 32
    expect_final_fail(
        "qualification result falsified",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Result:** `PASS`",
            "**Result:** `FAIL`",
        ),
        "qualification metadata Result must be 'PASS'",
    )

    # 33
    expect_final_fail(
        "qualification state not verified",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Qualification state:** `VERIFIED`",
            "**Qualification state:** `UNVERIFIED`",
        ),
        "qualification metadata Qualification state "
        "must be 'VERIFIED'",
    )

    # 34
    expect_final_fail(
        "qualification specification version drift",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Specification version:** `1.0.0`",
            "**Specification version:** `0.1.0`",
        ),
        "qualification Specification version must match",
    )

    # 35
    expect_final_fail(
        "mutation evidence incomplete",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Mutation result:** `46 / 46`",
            "**Mutation result:** `0 / 1`",
        ),
        "requires all recorded mutations to be killed",
    )

    # 36
    expect_final_fail(
        "zero mutation cardinality",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Mutation result:** `46 / 46`",
            "**Mutation result:** `0 / 0`",
        ),
        "requires a nonzero mutation-suite cardinality",
    )

    # 37
    expect_final_fail(
        "qualification execution authority drift",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Execution authority:** "
            "`AUTH-HETREN-MVP-3.0`",
            "**Execution authority:** "
            "`AUTH-HETREN-MVP-2.0`",
        ),
        "qualification metadata Execution authority",
    )

    # 38
    expect_final_fail(
        "Task 4 regression not passing",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Task 4 regression:** `PASS`",
            "**Task 4 regression:** `FAIL`",
        ),
        "qualification metadata Task 4 regression",
    )

    # 39
    expect_final_fail(
        "final accepted-state qualification not passing",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Final accepted-state qualification:** `PASS`",
            "**Final accepted-state qualification:** `FAIL`",
        ),
        "qualification metadata "
        "Final accepted-state qualification",
    )

    # 40
    expect_final_fail(
        "qualification condition count falsified",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Qualification conditions:** `50 / 50`",
            "**Qualification conditions:** `49 / 50`",
        ),
        "qualification metadata Qualification conditions",
    )

    # 41
    expect_final_fail(
        "mutation-suite identity drift",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "**Mutation suite:** "
            "`tests/qualification/test_support_matrix.py`",
            "**Mutation suite:** "
            "`tests/qualification/test_other_matrix.py`",
        ),
        "qualification metadata Mutation suite",
    )

    # 42
    expect_final_fail(
        "semantic qualification section missing",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "## Semantic Qualification",
            "## Semantic Evidence",
        ),
        "qualification missing section "
        "Semantic Qualification",
    )

    # 43
    expect_final_fail(
        "acceptance record points to wrong decision",
        lambda root: replace_once(
            root,
            QUALIFICATION,
            "Decision 0005 is ACCEPTED after qualification.",
            "Decision 0006 is ACCEPTED after qualification.",
        ),
        "qualification acceptance missing required "
        "semantic fragment: Decision 0005",
    )

    # 44
    expect_final_fail(
        "accepted implementation evidence left pending",
        lambda root: replace_once(
            root,
            DECISION,
            "Implemented and preserved in:",
            "Pending.\n\nImplemented and preserved in:",
        ),
        "accepted Decision 0005 implementation "
        "evidence cannot remain pending",
    )

    # 45
    expect_final_fail(
        "accepted verification evidence left pending",
        lambda root: replace_once(
            root,
            DECISION,
            "Verified by\n"
            "`docs/decisions/qualification/"
            "0005-mvp-support-matrix.md`",
            "Pending.\n\nVerified by\n"
            "`docs/decisions/qualification/"
            "0005-mvp-support-matrix.md`",
        ),
        "accepted Decision 0005 verification "
        "evidence cannot remain pending",
    )

    # 46
    expect_final_fail(
        "accepted register demoted to proposed",
        lambda root: set_register_status(
            root,
            "PROPOSED",
        ),
        "final qualification requires "
        "Decision 0005 register status ACCEPTED",
    )


def main() -> None:
    positive_control()
    final_positive_control()

    print()
    print("===== DEVELOPMENT MUTATIONS =====")
    run_development_mutations()

    development_killed = MUTATIONS_KILLED

    print()
    print(
        "TASK 5 DEVELOPMENT MUTATIONS: PASS "
        f"({development_killed} mutations killed)"
    )

    print()
    print("===== FINAL-STATE MUTATIONS =====")
    run_final_mutations()

    final_killed = (
        MUTATIONS_KILLED
        - development_killed
    )

    print()
    print(
        "TASK 5 FINAL-STATE MUTATIONS: PASS "
        f"({final_killed} mutations killed)"
    )

    if MUTATIONS_KILLED != EXPECTED_MUTATIONS:
        raise AssertionError(
            "Task 5 mutation cardinality mismatch: "
            f"expected {EXPECTED_MUTATIONS}, "
            f"killed {MUTATIONS_KILLED}"
        )

    print()
    print(
        "TASK 5 MUTATION SUITE: PASS "
        f"({MUTATIONS_KILLED}/{EXPECTED_MUTATIONS} "
        "mutations killed)"
    )


if __name__ == "__main__":
    main()
