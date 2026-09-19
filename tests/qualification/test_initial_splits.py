#!/usr/bin/env python3

from __future__ import annotations

import ast
import copy
import hashlib
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
    / "check_initial_splits.py"
)

SPEC = "docs/mvp/07-initial-splits.md"

DECISION = (
    "docs/decisions/"
    "0008-initial-split-protocol.md"
)

REGISTER = "docs/decisions/register.md"

QUALIFICATION = (
    "docs/decisions/qualification/"
    "0008-initial-split-protocol.md"
)

DEVELOPMENT_MUTATIONS_EXPECTED = 52
FINAL_MUTATIONS_EXPECTED = 16
EXPECTED_MUTATIONS = 68

DEVELOPMENT_MUTATIONS_KILLED = 0
FINAL_MUTATIONS_KILLED = 0

DEVELOPMENT_MUTATIONS_SURVIVED: list[str] = []
FINAL_MUTATIONS_SURVIVED: list[str] = []

assert (
    DEVELOPMENT_MUTATIONS_EXPECTED
    + FINAL_MUTATIONS_EXPECTED
    == EXPECTED_MUTATIONS
)


def make_repo() -> Path:
    temp = Path(
        tempfile.mkdtemp(
            prefix="hetren-initial-splits-test-"
        )
    )

    for relative in (
        SPEC,
        DECISION,
        REGISTER,
    ):
        source = ROOT / relative
        destination = temp / relative

        if not source.is_file():
            raise AssertionError(
                f"required source missing: {source}"
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

    source = ROOT / QUALIFICATION

    if source.is_file():
        destination = temp / QUALIFICATION

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
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

    count = text.count(old)

    if count != 1:
        raise AssertionError(
            "mutation/state anchor count mismatch in "
            f"{relative}: expected 1, found {count}\n"
            f"anchor: {old}"
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

    target.write_text(
        updated
    )


def replace_once_in_numbered_section(
    root: Path,
    relative: str,
    section_number: int,
    section_title: str,
    old: str,
    new: str,
) -> None:
    target = root / relative
    text = target.read_text()

    pattern = (
        rf"(?ms)^## {section_number}\. "
        rf"{re.escape(section_title)}\n"
        r"(.*?)"
        r"(?=^## [0-9]+\. |\Z)"
    )

    match = re.search(
        pattern,
        text,
    )

    if not match:
        raise AssertionError(
            "numbered section not found: "
            f"{section_number}. {section_title}"
        )

    body = match.group(1)

    count = body.count(
        old
    )

    if count != 1:
        raise AssertionError(
            "section-scoped mutation anchor count mismatch "
            f"in {relative}, section {section_number}: "
            f"expected 1, found {count}\n"
            f"anchor: {old}"
        )

    updated_body = body.replace(
        old,
        new,
        1,
    )

    updated = (
        text[:match.start(1)]
        + updated_body
        + text[match.end(1):]
    )

    target.write_text(
        updated
    )



def regex_replace_once_in_numbered_section(
    root: Path,
    relative: str,
    section_number: int,
    section_title: str,
    pattern: str,
    replacement: str,
) -> None:
    target = root / relative
    text = target.read_text()

    section_pattern = (
        rf"(?ms)^## {section_number}\. "
        rf"{re.escape(section_title)}\n"
        r"(.*?)"
        r"(?=^## [0-9]+\. |\Z)"
    )

    section_match = re.search(
        section_pattern,
        text,
    )

    if not section_match:
        raise AssertionError(
            "numbered section not found: "
            f"{section_number}. {section_title}"
        )

    body = section_match.group(1)

    updated_body, count = re.subn(
        pattern,
        replacement,
        body,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    if count != 1:
        raise AssertionError(
            "section-scoped regex mutation failed "
            f"in {relative}, section {section_number}: "
            f"{pattern}"
        )

    updated = (
        text[:section_match.start(1)]
        + updated_body
        + text[section_match.end(1):]
    )

    target.write_text(
        updated
    )



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

    target.write_text(
        updated
    )


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

    pattern = (
        r"^(\| `0008` \| "
        r"`research\.evaluation\.initial-splits` \| "
        r"Govern the initial MVP split protocol \| )"
        r"`(?:PROPOSED|ACCEPTED)`"
        r"( \| `DATA` \| "
        r"`AUTH-HETREN-MVP-3\.0` \| "
        r"`0008-initial-split-protocol\.md` \|)$"
    )

    updated, count = re.subn(
        pattern,
        rf"\1`{status}`\2",
        text,
        count=1,
        flags=re.MULTILINE,
    )

    if count != 1:
        raise AssertionError(
            "Decision 0008 register status "
            "replacement failed"
        )

    target.write_text(
        updated
    )


def remove_qualification(
    root: Path,
) -> None:
    target = root / QUALIFICATION

    if target.exists():
        target.unlink()


def set_development_state(
    root: Path,
) -> None:
    """
    Normalize a copied repository into the canonical
    Task 7 development lifecycle.

    This keeps development mutations valid after the real
    repository eventually reaches final acceptance.
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
        "Pending.",
    )

    replace_markdown_section(
        root,
        DECISION,
        "Verification Evidence",
        "Pending.",
    )

    remove_qualification(
        root
    )


def final_qualification_record() -> str:
    """
    Synthetic accepted-state qualification evidence used only
    inside temporary qualification-test repositories.

    This is not the real Decision 0008 qualification record.
    """

    return """# Decision 0008 Qualification Record

**Task:** `7 / 100`
**Decision:** `0008`
**Decision Key:** `research.evaluation.initial-splits`
**Date:** `2026-09-18`
**Result:** `PASS`
**Qualification state:** `VERIFIED`
**Specification:** `docs/mvp/07-initial-splits.md`
**Specification version:** `1.0.0`
**Validator:** `scripts/check_initial_splits.py`
**Mutation suite:** `tests/qualification/test_initial_splits.py`
**Qualification conditions:** `50 / 50`
**Mutation result:** `68 / 68`
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Task 1 regression:** `PASS`
**Task 2 regression:** `PASS`
**Task 3 regression:** `PASS`
**Task 4 regression:** `PASS`
**Task 5 regression:** `PASS`
**Task 6 regression:** `PASS`
**Diff check:** `PASS`
**Scientific support established:** `NO`
**Task 5 capability support promoted:** `NO`
**Final accepted-state qualification:** `PASS`

## Scope

This synthetic fixture represents the accepted governance state for Task 7
validator qualification testing.

It does not establish scientific support and does not promote any Task 5
capability to `QUALIFIED_SUPPORTED`.

## Positive Qualification

PASS.

The Task 7 specification contains exactly 50 governed numbered sections and
exactly 50 ordered Task 7 qualification conditions.

## Adversarial Qualification

PASS.

The frozen Task 7 mutation target is `68 / 68`:

- `52 / 52` development-state mutations;
- `16 / 16` final accepted-state mutations.

## Authority And Regression Qualification

PASS.

Tasks 1 through 6 regression qualification: PASS.

Development-state qualification: PASS.

Final accepted-state qualification: PASS.

## Evidence Interpretation

The original frozen P1 first run remains `22 / 24`.

The original frozen Set D first run remains `21 / 32`.

Later remediation and regression success do not rewrite those original
first-run results.

Scientific support established: `NO`.

Task 5 capability support promoted: `NO`.

## Acceptance Decision

Decision 0008 is `ACCEPTED`.

The Task 7 initial-splits specification is version `1.0.0` and `Qualified`.

Final accepted-state qualification: PASS.
"""


def set_final_state(
    root: Path,
) -> None:
    """
    Normalize a copied repository into the synthetic accepted
    Task 7 lifecycle used only by final-state qualification tests.
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
        (
            "Implemented. Task 7 split governance, qualification "
            "validators, structured qualification data, and preserved "
            "evidence are present and bound to Decision 0008."
        ),
    )

    replace_markdown_section(
        root,
        DECISION,
        "Verification Evidence",
        (
            "Verified. Development-state qualification, adversarial "
            "mutation qualification, Tasks 1 through 6 regression "
            "qualification, structured evidence validation, and final "
            "accepted-state qualification pass."
        ),
    )

    target = (
        root
        / QUALIFICATION
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_text(
        final_qualification_record()
    )


def replace_qualification_once(
    root: Path,
    old: str,
    new: str,
) -> None:
    replace_once(
        root,
        QUALIFICATION,
        old,
        new,
    )


def final_positive_control() -> None:
    root = make_repo()

    try:
        set_final_state(
            root
        )

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
            root
        )


def expect_final_fail(
    label: str,
    mutate,
) -> None:
    global FINAL_MUTATIONS_KILLED

    root = make_repo()

    try:
        set_final_state(
            root
        )

        mutate(
            root
        )

        result = run_validator(
            root,
            "--require-qualified",
        )

        if result.returncode == 0:
            FINAL_MUTATIONS_SURVIVED.append(
                label
            )

            print(
                f"FAIL final mutation survived: {label}"
            )

            return

        FINAL_MUTATIONS_KILLED += 1

        print(
            f"PASS final mutation killed: {label}"
        )

    finally:
        shutil.rmtree(
            root
        )


def set_decision_key_drift(
    root: Path,
) -> None:
    replace_once(
        root,
        DECISION,
        (
            "**Decision Key:** "
            "`research.evaluation.initial-splits`"
        ),
        (
            "**Decision Key:** "
            "`research.evaluation.initial-splitz`"
        ),
    )


def set_spec_final_version_drift(
    root: Path,
) -> None:
    set_spec_metadata(
        root,
        version="1.0.1",
        status="Qualified",
    )


def set_qualification_date_invalid(
    root: Path,
) -> None:
    replace_qualification_once(
        root,
        "**Date:** `2026-09-18`",
        "**Date:** `2026-99-99`",
    )


def run_final_mutations() -> None:
    cases = (
        (
            "qualification record missing",
            lambda root: remove_qualification(
                root
            ),
        ),
        (
            "qualification Result changed to FAIL",
            lambda root: replace_qualification_once(
                root,
                "**Result:** `PASS`",
                "**Result:** `FAIL`",
            ),
        ),
        (
            "qualification state left PENDING",
            lambda root: replace_qualification_once(
                root,
                "**Qualification state:** `VERIFIED`",
                "**Qualification state:** `PENDING`",
            ),
        ),
        (
            "Qualified specification version drift",
            set_spec_final_version_drift,
        ),
        (
            "mutation evidence incomplete",
            lambda root: replace_qualification_once(
                root,
                "**Mutation result:** `68 / 68`",
                "**Mutation result:** `67 / 68`",
            ),
        ),
        (
            "scientific support incorrectly promoted",
            lambda root: replace_qualification_once(
                root,
                "**Scientific support established:** `NO`",
                "**Scientific support established:** `YES`",
            ),
        ),
        (
            "Task 5 capability support incorrectly promoted",
            lambda root: replace_qualification_once(
                root,
                "**Task 5 capability support promoted:** `NO`",
                "**Task 5 capability support promoted:** `YES`",
            ),
        ),
        (
            "Decision 0008 demoted after qualification",
            lambda root: set_decision_status(
                root,
                "PROPOSED",
            ),
        ),
        (
            "Decision 0008 register demoted after qualification",
            lambda root: set_register_status(
                root,
                "PROPOSED",
            ),
        ),
        (
            "implementation evidence remains Pending",
            lambda root: replace_markdown_section(
                root,
                DECISION,
                "Implementation Evidence",
                "Pending.",
            ),
        ),
        (
            "verification evidence remains Pending",
            lambda root: replace_markdown_section(
                root,
                DECISION,
                "Verification Evidence",
                "Pending.",
            ),
        ),
        (
            "Decision 0008 key drift",
            set_decision_key_drift,
        ),
        (
            "qualification specification version mismatch",
            lambda root: replace_qualification_once(
                root,
                "**Specification version:** `1.0.0`",
                "**Specification version:** `0.1.0`",
            ),
        ),
        (
            "Tasks 1 through 6 regression evidence changed to FAIL",
            lambda root: replace_qualification_once(
                root,
                "**Task 6 regression:** `PASS`",
                "**Task 6 regression:** `FAIL`",
            ),
        ),
        (
            "final accepted-state qualification changed to FAIL",
            lambda root: replace_qualification_once(
                root,
                (
                    "**Final accepted-state qualification:** "
                    "`PASS`"
                ),
                (
                    "**Final accepted-state qualification:** "
                    "`FAIL`"
                ),
            ),
        ),
        (
            "qualification date invalid",
            set_qualification_date_invalid,
        ),
    )

    assert len(
        cases
    ) == FINAL_MUTATIONS_EXPECTED

    for label, mutate in cases:
        expect_final_fail(
            label,
            mutate,
        )


def positive_control() -> None:
    root = make_repo()

    try:
        set_development_state(
            root
        )

        result = run_validator(
            root
        )

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
            root
        )


def expect_fail(
    label: str,
    mutate,
) -> None:
    global DEVELOPMENT_MUTATIONS_KILLED

    root = make_repo()

    try:
        set_development_state(
            root
        )

        mutate(
            root
        )

        result = run_validator(
            root
        )

        if result.returncode == 0:
            DEVELOPMENT_MUTATIONS_SURVIVED.append(
                label
            )

            print(
                f"FAIL mutation survived: {label}"
            )

            return

        DEVELOPMENT_MUTATIONS_KILLED += 1

        print(
            f"PASS mutation killed: {label}"
        )

    finally:
        shutil.rmtree(
            root
        )



def run_development_mutations_part1() -> None:
    cases = (
        (
            "execution authority drift",
            lambda root: replace_once(
                root,
                SPEC,
                "**Execution authority:** "
                "`AUTH-HETREN-MVP-3.0`",
                "**Execution authority:** "
                "`AUTH-HETREN-MVP-2.0`",
            ),
        ),
        (
            "PartitionRole vocabulary expanded",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                5,
                "PartitionRole Vocabulary",
                "- `PROTECTED`.",
                "- `PROTECTED`;\n- `TEST`.",
            ),
        ),
        (
            "validation promoted to protected evidence",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                7,
                "VALIDATION Semantics",
                (
                    "Once validation outcomes influence candidate "
                    "selection, the partition is not\n"
                    "protected evidence for that candidate lineage."
                ),
                (
                    "Once validation outcomes influence candidate "
                    "selection, the partition is\n"
                    "valid protected evidence for that candidate lineage."
                ),
            ),
        ),
        (
            "protected outcomes allowed to tune candidate",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                8,
                "PROTECTED Semantics",
                (
                    "A `PROTECTED` partition is reserved for evidence "
                    "that must not be used to tune\n"
                    "the candidate or manufacture the governed claim."
                ),
                (
                    "A `PROTECTED` partition is reserved for evidence "
                    "that may be used to tune\n"
                    "the candidate while producing the governed claim."
                ),
            ),
        ),
        (
            "PartitionPurpose vocabulary expanded",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                9,
                "PartitionPurpose Vocabulary",
                "- `CRITICAL_INVARIANT`.",
                (
                    "- `CRITICAL_INVARIANT`;\n"
                    "- `POST_HOC_ANALYSIS`."
                ),
            ),
        ),
        (
            "role and purpose axes collapsed",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                10,
                "Role And Purpose Are Separate Axes",
                (
                    "A split contract must record both:\n\n"
                    "- `PartitionRole`;\n"
                    "- one or more applicable `PartitionPurpose` values."
                ),
                (
                    "A split contract may infer `PartitionPurpose` "
                    "directly from `PartitionRole`."
                ),
            ),
        ),
        (
            "SplitPlan versionless identity weakened",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                11,
                "SplitPlan",
                (
                    "A `SplitPlan` ID is intentionally versionless."
                ),
                (
                    "A `SplitPlan` ID is usually versionless but "
                    "may encode execution versions."
                ),
            ),
        ),
        (
            "SplitVersion made mutable",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                12,
                "SplitVersion",
                (
                    "A `SplitVersion` is the immutable governed version "
                    "of a `SplitPlan` used by an\n"
                    "experiment or qualification attempt."
                ),
                (
                    "A `SplitVersion` is the mutable governed version "
                    "of a `SplitPlan` used by an\n"
                    "experiment or qualification attempt."
                ),
            ),
        ),
        (
            "partition membership allowed to retain identity",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                13,
                "PartitionIdentity",
                (
                    "Changing membership does not silently preserve "
                    "the same partition identity."
                ),
                (
                    "Changing membership may preserve the same "
                    "partition identity."
                ),
            ),
        ),
        (
            "repeated observations manufacture independence",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                14,
                "EvaluationUnit",
                (
                    "Repeated observations from one evaluation unit "
                    "do not create new independent\n"
                    "units merely by repetition."
                ),
                (
                    "Repeated observations from one evaluation unit "
                    "may create new independent\n"
                    "units merely by repetition."
                ),
            ),
        ),
        (
            "resampling manufactures independent unit",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                14,
                "EvaluationUnit",
                (
                    "Resampling one unit does not create another "
                    "independent unit."
                ),
                (
                    "Resampling one unit may create another "
                    "independent unit."
                ),
            ),
        ),
        (
            "random seed manufactures independent unit",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                14,
                "EvaluationUnit",
                (
                    "Rerunning one unit with a different random seed "
                    "does not create another\n"
                    "independent unit unless the governing scientific "
                    "contract explicitly defines\n"
                    "the seed-level process itself as the independent "
                    "evidence-generating unit."
                ),
                (
                    "Rerunning one unit with a different random seed "
                    "creates another\n"
                    "independent unit even when the underlying "
                    "evidence-generating unit is unchanged."
                ),
            ),
        ),
        (
            "same independence group allowed to count independently",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                15,
                "IndependenceGroup",
                (
                    "Two units may count as separately independent "
                    "only when they belong to\n"
                    "different governed independence groups and the "
                    "experiment records the basis\n"
                    "for that separation."
                ),
                (
                    "Two units may count as separately independent "
                    "even when they belong to\n"
                    "the same governed independence group."
                ),
            ),
        ),
        (
            "different IDs manufacture independence",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                15,
                "IndependenceGroup",
                (
                    "Assigning two different IDs to correlated "
                    "evidence does not manufacture\n"
                    "independence."
                ),
                (
                    "Assigning two different IDs to correlated "
                    "evidence is sufficient to manufacture\n"
                    "independence."
                ),
            ),
        ),
        (
            "hash inequality treated as independence proof",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                17,
                "Membership And Provenance",
                (
                    "Hash inequality alone does not prove independence."
                ),
                (
                    "Hash inequality alone proves independence."
                ),
            ),
        ),
        (
            "transformed protected copy treated as fresh",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                17,
                "Membership And Provenance",
                (
                    "A transformed copy of protected evidence remains "
                    "derived from protected\n"
                    "evidence even when its bytes differ."
                ),
                (
                    "A transformed copy of protected evidence becomes "
                    "independent protected\n"
                    "evidence whenever its bytes differ."
                ),
            ),
        ),
        (
            "protected membership selected after outcomes",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                18,
                "Protected Contract Freeze",
                (
                    "Protected membership must not be selected after "
                    "inspecting protected outcomes."
                ),
                (
                    "Protected membership may be selected after "
                    "inspecting protected outcomes."
                ),
            ),
        ),
        (
            "independence boundaries redefined post-result",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                18,
                "Protected Contract Freeze",
                (
                    "Independence boundaries must not be redefined "
                    "after seeing protected results."
                ),
                (
                    "Independence boundaries may be redefined "
                    "after seeing protected results."
                ),
            ),
        ),
        (
            "protected lifecycle vocabulary expanded",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                19,
                "Protected Evidence Lifecycle",
                (
                    "- `INVALIDATED`."
                ),
                (
                    "- `INVALIDATED`;\n"
                    "- `REUSABLE`."
                ),
            ),
        ),
        (
            "sealed outcomes returned to candidate path",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                21,
                "SEALED State",
                (
                    "`SEALED` means protected outcome information is "
                    "withheld from unauthorized\n"
                    "candidate-producing or tuning processes."
                ),
                (
                    "`SEALED` means protected outcome information may "
                    "be returned to\n"
                    "candidate-producing or tuning processes."
                ),
            ),
        ),
        (
            "candidate freeze permits protected tuning",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                22,
                "Candidate Freeze",
                (
                    "Before a consequential protected evaluation "
                    "begins, the governed candidate must\n"
                    "be frozen sufficiently to prevent protected "
                    "outcomes from being tuned into the\n"
                    "candidate."
                ),
                (
                    "Before a consequential protected evaluation "
                    "begins, the governed candidate may\n"
                    "remain mutable so protected outcomes can be "
                    "tuned into the candidate."
                ),
            ),
        ),
        (
            "evaluation feedback returned for interactive tuning",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                23,
                "EVALUATING State",
                (
                    "- protected outcomes must not be returned to "
                    "the candidate-producing path;\n"
                    "- acceptance signals must not be used for "
                    "interactive tuning;"
                ),
                (
                    "- protected outcomes may be returned to "
                    "the candidate-producing path;\n"
                    "- acceptance signals may be used for "
                    "interactive tuning;"
                ),
            ),
        ),
        (
            "disclosed evidence automatically fresh for descendants",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                24,
                "DISCLOSED State",
                (
                    "However, after disclosure, that evidence is not "
                    "automatically fresh protected\n"
                    "evidence for a descendant candidate whose "
                    "construction or tuning can be\n"
                    "influenced by the disclosed information."
                ),
                (
                    "After disclosure, that evidence is automatically "
                    "fresh protected\n"
                    "evidence for every descendant candidate even "
                    "when construction or tuning is\n"
                    "influenced by the disclosed information."
                ),
            ),
        ),
        (
            "deleting access history restores freshness",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                25,
                "ProtectedAccessEvent",
                (
                    "Deleting access history does not restore freshness."
                ),
                (
                    "Deleting access history restores freshness."
                ),
            ),
        ),
        (
            "evaluator-feedback leakage removed",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                26,
                "Leakage Taxonomy",
                (
                    "- `EVALUATOR_FEEDBACK_LEAKAGE`;"
                ),
                (
                    "- `EVALUATOR_FEEDBACK_EXPOSURE_ALLOWED`;"
                ),
            ),
        ),
        (
            "best-of-many protected peeking allowed",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                28,
                "Repeated Protected Peeking",
                (
                    "Trying many candidates against one protected "
                    "split and reporting only the best\n"
                    "result is not a valid single protected evaluation "
                    "unless that selection process\n"
                    "was itself part of the preregistered governed "
                    "protocol."
                ),
                (
                    "Trying many candidates against one protected "
                    "split and reporting only the best\n"
                    "result is a valid protected evaluation even when "
                    "that selection process was not\n"
                    "part of the preregistered governed protocol."
                ),
            ),
        ),
    )

    if len(cases) != 26:
        raise AssertionError(
            "Task 7 development mutation part 1 "
            f"definition count mismatch: {len(cases)} != 26"
        )

    for label, mutate in cases:
        expect_fail(
            label,
            mutate,
        )




def run_development_mutations_part2a() -> None:
    cases = (
        (
            "contamination vocabulary expanded",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                27,
                "ContaminationState",
                r"- `UNKNOWN`\.",
                (
                    "- `UNKNOWN`;\n"
                    "- `CLEARED`."
                ),
            ),
        ),
        (
            "non-clean contamination silently laundered to CLEAN",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                27,
                "ContaminationState",
                (
                    r"must not be silently represented as\s+"
                    r"`CLEAN`"
                ),
                "may be silently represented as `CLEAN`",
            ),
        ),
        (
            "invalidation stops preserving original result",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                29,
                "Invalidation And Split Revision",
                "- original result;",
                "- replacement result;",
            ),
        ),
        (
            "replacement split erases invalid result",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                29,
                "Invalidation And Split Revision",
                (
                    "A replacement split does not erase "
                    "the invalid result."
                ),
                (
                    "A replacement split erases "
                    "the invalid result."
                ),
            ),
        ),
        (
            "physically new file automatically treated as fresh",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                30,
                "Fresh Protected Evidence",
                (
                    "A physically new file is not necessarily "
                    "fresh evidence."
                ),
                (
                    "A physically new file is automatically "
                    "fresh evidence."
                ),
            ),
        ),
        (
            "transformed exposed descendant treated as fresh",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                30,
                "Fresh Protected Evidence",
                (
                    r"A copied, transformed, resampled, or "
                    r"re-encoded descendant of exposed\s+"
                    r"protected evidence inherits the relevant "
                    r"exposure unless a governed analysis\s+"
                    r"establishes otherwise\."
                ),
                (
                    "A copied, transformed, resampled, or "
                    "re-encoded descendant of exposed\n"
                    "protected evidence is automatically fresh "
                    "whenever its bytes differ."
                ),
            ),
        ),
        (
            "N-H1 reduced to one protected evaluation unit",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                31,
                "N-H1 Split Binding",
                (
                    "- at least two protected governed "
                    "`EvaluationUnit` values;"
                ),
                (
                    "- at least one protected governed "
                    "`EvaluationUnit` value;"
                ),
            ),
        ),
        (
            "N-H1 same IndependenceGroup accepted",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                32,
                "N-H1 Independent Evaluation Units",
                (
                    r"- those units to belong to different "
                    r"applicable `IndependenceGroup` values;"
                ),
                (
                    "- those units may belong to the same "
                    "applicable `IndependenceGroup` value;"
                ),
            ),
        ),
        (
            "N-H1 one behavior silently establishes another",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                31,
                "N-H1 Split Binding",
                (
                    "Evidence for one behavior must not silently "
                    "establish another."
                ),
                (
                    "Evidence for one behavior may silently "
                    "establish another."
                ),
            ),
        ),
        (
            "N-H1 validation reused as fresh protected evidence",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                33,
                "N-H1 Development And Validation Use",
                (
                    r"Validation results used to choose the final "
                    r"Native candidate must not later be\s+"
                    r"reported as fresh protected evidence for "
                    r"that candidate\."
                ),
                (
                    "Validation results used to choose the final "
                    "Native candidate may later be\n"
                    "reported as fresh protected evidence for "
                    "that candidate."
                ),
            ),
        ),
        (
            "N-H2 target family chosen after protected outcomes",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                34,
                "N-H2 Split Binding",
                (
                    r"The target environment family must be "
                    r"predeclared before protected target\s+"
                    r"outcomes are inspected\."
                ),
                (
                    "The target environment family may be chosen "
                    "after protected target\n"
                    "outcomes are inspected."
                ),
            ),
        ),
        (
            "N-H2 best boundary may be selected post hoc",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                35,
                "N-H2 Leave-One-Family-Out Boundaries",
                (
                    r"- success is not selected post hoc from "
                    r"whichever boundary performs best;"
                ),
                (
                    "- success may be selected post hoc from "
                    "whichever boundary performs best;"
                ),
            ),
        ),
        (
            "N-H2 protected target-outcome tuning permitted",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                36,
                "N-H2 Transfer Leakage Controls",
                (
                    "The central prohibition is protected "
                    "target-outcome tuning."
                ),
                (
                    "The central permission is protected "
                    "target-outcome tuning."
                ),
            ),
        ),
    )

    if len(cases) != 13:
        raise AssertionError(
            "Task 7 development mutation part 2A "
            f"definition count mismatch: {len(cases)} != 13"
        )

    for label, mutate in cases:
        expect_fail(
            label,
            mutate,
        )




def run_development_mutations_part2b() -> None:
    cases = (
        (
            "A-H1 separation contradicted while correct rule remains",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                37,
                "A-H1 Split Binding",
                (
                    r"(The adaptation input and protected outcome "
                    r"evidence must remain separately\s+"
                    r"identified even when they concern the same "
                    r"general target behavior\.)"
                ),
                (
                    r"\1\n\n"
                    "However, an implementation may merge adaptation "
                    "input and protected outcome evidence whenever "
                    "that is operationally convenient."
                ),
            ),
        ),
        (
            "A-H1 protected evaluator outputs become adaptation input",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                38,
                "A-H1 Adaptation Input And Protected Outcome Separation",
                (
                    r"(- protected aggregate scores;\s+"
                    r"- protected per-case scores;)"
                ),
                (
                    r"\1\n"
                    "- protected aggregate and per-case scores may "
                    "also be returned as adaptation input after "
                    "each evaluation batch;"
                ),
            ),
        ),
        (
            "A-H1 leakage no longer invalidates result",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                38,
                "A-H1 Adaptation Input And Protected Outcome Separation",
                (
                    r"(If protected outcome information materially "
                    r"influences the adaptive candidate\s+"
                    r"before candidate freeze, the affected protected "
                    r"adaptation result is invalid\s+"
                    r"for `A-H1`\.)"
                ),
                (
                    r"\1\n\n"
                    "A later implementation may nevertheless preserve "
                    "the same A-H1 result as valid when the leakage "
                    "improved adaptation quality."
                ),
            ),
        ),
        (
            "A-H2 paired observations also counted as independent",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                40,
                "A-H2 Paired Pre/Post/Rollback Evaluation",
                (
                    r"(Using the same unit at those three measurement "
                    r"points does not by itself create\s+"
                    r"three independent evaluation units\.)"
                ),
                (
                    r"\1\n\n"
                    "For statistical qualification, those same "
                    "pre-adaptation, post-adaptation, and post-rollback "
                    "observations may also be counted as three "
                    "independent evaluation units."
                ),
            ),
        ),
        (
            "A-H2 rollback description accepted without execution",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                40,
                "A-H2 Paired Pre/Post/Rollback Evaluation",
                (
                    r"(A description of rollback is not a rollback "
                    r"evaluation\.)"
                ),
                (
                    r"\1\n\n"
                    "A sufficiently detailed rollback description "
                    "may substitute for actual rollback execution."
                ),
            ),
        ),
        (
            "Task 5 split identity alone promotes capability support",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                41,
                "Task 5 Capability Qualification Split Bindings",
                (
                    r"(They do not establish that any Task 5 "
                    r"capability is\s+"
                    r"`QUALIFIED_SUPPORTED`\.)"
                ),
                (
                    r"\1\n\n"
                    "Possession of one of these governed SplitPlan "
                    "identities is nevertheless sufficient to promote "
                    "the corresponding capability to "
                    "`QUALIFIED_SUPPORTED`."
                ),
            ),
        ),
        (
            "grouped leakage allowed under random record split",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                43,
                "Environment-Family Partitioning Rules",
                (
                    r"(A random record-level split is invalid when "
                    r"it allows a material grouped\s+"
                    r"dependency to leak across the protected "
                    r"boundary\.)"
                ),
                (
                    r"\1\n\n"
                    "Random record-level splitting remains acceptable "
                    "even when a material grouped dependency crosses "
                    "the protected boundary."
                ),
            ),
        ),
        (
            "candidate-producing path allowed to manipulate verification evidence",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                44,
                "Independent Verification And Authority Separation",
                (
                    r"(For a consequential protected claim, the "
                    r"verification path must have enough\s+"
                    r"separation that the process producing the "
                    r"candidate cannot manipulate the\s+"
                    r"protected evidence used to certify it\.)"
                ),
                (
                    r"\1\n\n"
                    "The candidate-producing process may also alter "
                    "or curate the protected verification evidence "
                    "when it judges the changes beneficial."
                ),
            ),
        ),
        (
            "verification replay authorizes iterative protected tuning",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                44,
                "Independent Verification And Authority Separation",
                (
                    r"(That permitted replay does not authorize "
                    r"iterative candidate tuning against the\s+"
                    r"same protected outcomes\.)"
                ),
                (
                    r"\1\n\n"
                    "Repeated verification replay may additionally "
                    "be used for iterative candidate tuning against "
                    "those same protected outcomes."
                ),
            ),
        ),
        (
            "Task 7 may deliberately select weak baseline",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                45,
                "Task 8 Baseline Handoff",
                (
                    r"(Task 7 must not select a weak baseline to "
                    r"improve the apparent candidate\s+"
                    r"result\.)"
                ),
                (
                    r"\1\n\n"
                    "Task 7 may select a weaker available baseline "
                    "when doing so produces a clearer candidate "
                    "advantage."
                ),
            ),
        ),
        (
            "post-result resource accounting may manufacture pass",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                46,
                "Task 9 Cost And Resource Handoff",
                (
                    r"(Changing resource accounting after seeing "
                    r"protected results must not be used to\s+"
                    r"retroactively manufacture a passing comparison\.)"
                ),
                (
                    r"\1\n\n"
                    "Resource accounting may later be redefined from "
                    "the observed protected results when that converts "
                    "the comparison into a passing result."
                ),
            ),
        ),
        (
            "successor split allowed to overwrite historical manifest",
            lambda root: regex_replace_once_in_numbered_section(
                root,
                SPEC,
                47,
                "Change Control And Evidence Consequence",
                (
                    r"(A successor split must not overwrite the old "
                    r"manifest\.)"
                ),
                (
                    r"\1\n\n"
                    "A successor split may overwrite the historical "
                    "manifest when maintaining both versions would "
                    "increase storage or operational cost."
                ),
            ),
        ),
        (
            "Decision 0008 acceptance treated as scientific support",
            lambda root: replace_once(
                root,
                DECISION,
                (
                    "Acceptance does not establish scientific support "
                    "for `N-H1`, `N-H2`, `A-H1`,\n"
                    "or `A-H2`."
                ),
                (
                    "Acceptance does not establish scientific support "
                    "for `N-H1`, `N-H2`, `A-H1`,\n"
                    "or `A-H2`.\n\n"
                    "Nevertheless, acceptance may be treated as "
                    "sufficient scientific evidence to mark those "
                    "hypotheses supported when no experiment is "
                    "available."
                ),
            ),
        ),
    )

    if len(cases) != 13:
        raise AssertionError(
            "Task 7 development mutation part 2B "
            f"definition count mismatch: {len(cases)} != 13"
        )

    for label, mutate in cases:
        expect_fail(
            label,
            mutate,
        )




DEVELOPMENT_ATTACK_DEFINITION_FUNCTIONS = (
    "run_development_mutations_part1",
    "run_development_mutations_part2a",
    "run_development_mutations_part2b",
)


def _stable_ast_dump(node: ast.AST) -> str:
    """
    Return a Python-version-stable AST representation for governed
    mutation definitions.

    Python 3.12 and 3.13 differ in whether ast.dump() displays empty
    list fields by default. Remove only those empty-list attributes
    from a deep copy before serialization.

    Semantic values, including Constant(value=None), are preserved.
    """

    normalized = copy.deepcopy(
        node
    )

    def remove_empty_lists(
        value,
    ) -> None:
        if not isinstance(
            value,
            ast.AST,
        ):
            return

        for field_name in tuple(
            value._fields
        ):
            if not hasattr(
                value,
                field_name,
            ):
                continue

            field_value = getattr(
                value,
                field_name,
            )

            if isinstance(
                field_value,
                list,
            ):
                if not field_value:
                    delattr(
                        value,
                        field_name,
                    )

                    continue

                for item in field_value:
                    remove_empty_lists(
                        item
                    )

                continue

            if isinstance(
                field_value,
                ast.AST,
            ):
                remove_empty_lists(
                    field_value
                )

    remove_empty_lists(
        normalized
    )

    return ast.dump(
        normalized,
        annotate_fields=True,
        include_attributes=False,
    )


def development_attack_definition_hash() -> str:
    """
    Return a line-number-independent fingerprint of the frozen
    52 development-mutation definitions only.

    Unrelated final-state test additions must not change this
    development evidence identity.
    """

    source = Path(__file__).read_text()

    tree = ast.parse(
        source,
        filename=str(
            Path(__file__)
        ),
    )

    nodes = {
        node.name: node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            in DEVELOPMENT_ATTACK_DEFINITION_FUNCTIONS
        )
    }

    assert set(
        nodes
    ) == set(
        DEVELOPMENT_ATTACK_DEFINITION_FUNCTIONS
    )

    normalized = "\n".join(
        _stable_ast_dump(
            nodes[name]
        )
        for name
        in DEVELOPMENT_ATTACK_DEFINITION_FUNCTIONS
    )

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()

def main() -> None:
    print(
        "===== POSITIVE CONTROL ====="
    )

    positive_control()

    print()
    print(
        "===== DEVELOPMENT MUTATIONS 1-26 ====="
    )

    run_development_mutations_part1()

    print()
    print(
        "===== PART 1 RESULT ====="
    )

    print(
        "Killed: "
        f"{DEVELOPMENT_MUTATIONS_KILLED}/26"
    )

    if DEVELOPMENT_MUTATIONS_SURVIVED:
        print(
            "Survived:"
        )

        for label in DEVELOPMENT_MUTATIONS_SURVIVED:
            print(
                f"- {label}"
            )

        raise AssertionError(
            "Task 7 validator has surviving "
            "development mutations in part 1"
        )

    if DEVELOPMENT_MUTATIONS_KILLED != 26:
        raise AssertionError(
            "Task 7 development mutation part 1 "
            "cardinality mismatch"
        )

    print(
        "TASK 7 DEVELOPMENT MUTATIONS PART 1: PASS "
        "(26/26 mutations killed)"
    )

    print()
    print(
        "===== DEVELOPMENT MUTATIONS 27-39 ====="
    )

    killed_before_part2a = (
        DEVELOPMENT_MUTATIONS_KILLED
    )

    run_development_mutations_part2a()

    killed_part2a = (
        DEVELOPMENT_MUTATIONS_KILLED
        - killed_before_part2a
    )

    print()
    print(
        "===== PART 2A RESULT ====="
    )

    print(
        f"Killed: {killed_part2a}/13"
    )

    if DEVELOPMENT_MUTATIONS_SURVIVED:
        print(
            "Survived:"
        )

        for label in DEVELOPMENT_MUTATIONS_SURVIVED:
            print(
                f"- {label}"
            )

        raise AssertionError(
            "Task 7 validator has surviving "
            "development mutations in part 2A"
        )

    if killed_part2a != 13:
        raise AssertionError(
            "Task 7 development mutation part 2A "
            "cardinality mismatch"
        )

    if DEVELOPMENT_MUTATIONS_KILLED != 39:
        raise AssertionError(
            "Task 7 cumulative development mutation "
            "cardinality mismatch after part 2A"
        )

    print(
        "TASK 7 DEVELOPMENT MUTATIONS PART 2A: PASS "
        "(13/13 mutations killed)"
    )

    print(
        "TASK 7 DEVELOPMENT MUTATIONS SO FAR: PASS "
        "(39/39 mutations killed)"
    )

    print()
    print(
        "===== DEVELOPMENT MUTATIONS 40-52 ====="
    )

    killed_before_part2b = (
        DEVELOPMENT_MUTATIONS_KILLED
    )

    run_development_mutations_part2b()

    killed_part2b = (
        DEVELOPMENT_MUTATIONS_KILLED
        - killed_before_part2b
    )

    print()
    print(
        "===== PART 2B RESULT ====="
    )

    print(
        f"Killed: {killed_part2b}/13"
    )

    if DEVELOPMENT_MUTATIONS_SURVIVED:
        print(
            "Survived:"
        )

        for label in DEVELOPMENT_MUTATIONS_SURVIVED:
            print(
                f"- {label}"
            )

        raise AssertionError(
            "Task 7 validator has surviving "
            "development mutations in part 2B"
        )

    if killed_part2b != 13:
        raise AssertionError(
            "Task 7 development mutation part 2B "
            "cardinality mismatch"
        )

    if (
        DEVELOPMENT_MUTATIONS_KILLED
        != DEVELOPMENT_MUTATIONS_EXPECTED
    ):
        raise AssertionError(
            "Task 7 development mutation cardinality "
            "mismatch after all 52 attacks"
        )

    print(
        "TASK 7 DEVELOPMENT MUTATIONS PART 2B: PASS "
        "(13/13 mutations killed)"
    )

    print(
        "TASK 7 DEVELOPMENT MUTATIONS: PASS "
        f"({DEVELOPMENT_MUTATIONS_KILLED}/"
        f"{DEVELOPMENT_MUTATIONS_EXPECTED} mutations killed)"
    )

    print()
    print(
        "- development mutation target: "
        f"{DEVELOPMENT_MUTATIONS_EXPECTED}"
    )
    print(
        "- final-state mutation target: "
        f"{FINAL_MUTATIONS_EXPECTED}"
    )
    print(
        "- total frozen mutation target: "
        f"{EXPECTED_MUTATIONS}"
    )

    print()
    print(
        "===== FINAL-STATE POSITIVE CONTROL ====="
    )

    final_positive_control()

    print()
    print(
        "===== FINAL-STATE MUTATIONS 1-16 ====="
    )

    run_final_mutations()

    print()
    print(
        "===== FINAL-STATE MUTATION RESULT ====="
    )

    print(
        f"Killed: {FINAL_MUTATIONS_KILLED}/"
        f"{FINAL_MUTATIONS_EXPECTED}"
    )

    print(
        f"Survived: {len(FINAL_MUTATIONS_SURVIVED)}/"
        f"{FINAL_MUTATIONS_EXPECTED}"
    )

    if FINAL_MUTATIONS_SURVIVED:
        print(
            "Final-state survivors:"
        )

        for label in FINAL_MUTATIONS_SURVIVED:
            print(
                f"- {label}"
            )

        raise AssertionError(
            "Task 7 validator has surviving "
            "final-state mutations"
        )

    if (
        FINAL_MUTATIONS_KILLED
        != FINAL_MUTATIONS_EXPECTED
    ):
        raise AssertionError(
            "Task 7 final-state mutation "
            "cardinality mismatch"
        )

    print(
        "TASK 7 FINAL-STATE MUTATIONS: PASS "
        f"({FINAL_MUTATIONS_KILLED}/"
        f"{FINAL_MUTATIONS_EXPECTED} mutations killed)"
    )

    total_killed = (
        DEVELOPMENT_MUTATIONS_KILLED
        + FINAL_MUTATIONS_KILLED
    )

    assert total_killed == EXPECTED_MUTATIONS

    print(
        "TASK 7 TOTAL MUTATIONS: PASS "
        f"({total_killed}/{EXPECTED_MUTATIONS} mutations killed)"
    )


if __name__ == "__main__":
    main()
