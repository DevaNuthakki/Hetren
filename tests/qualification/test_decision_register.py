#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "check_decision_register.py"

CATEGORY_CONSEQUENCES = {
    "THESIS": "NEW_PROGRAM_VERSION_AND_RERUN",
    "METRIC": "RERUN_AFFECTED_QUALIFICATION",
    "DATA": "RERUN_AND_PRESERVE_DATA_DISTINCTIONS",
    "BASELINE": "RECOMPARE_STRONGEST_RESULT",
    "MODEL": "NEW_REPLICATION_RESULT",
    "ALGORITHM": "NEW_METHOD_VERSION_AND_PREREGISTRATION",
    "BUG": "INVALIDATE_AFFECTED_RESULTS_AND_RERUN",
    "INFRA": "SMOKE_AND_REGRESSION_RERUN_IF_NUMERICAL_CHANGE",
}


def make_repo() -> Path:
    temp = Path(tempfile.mkdtemp(prefix="hetren-decision-test-"))
    target = temp / "docs" / "decisions"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "docs" / "decisions", target)
    return temp


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(root),
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


def expect_fail(name: str, mutate, expected: str) -> None:
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


def expect_pass(name: str, mutate=None) -> None:
    root = make_repo()

    try:
        if mutate is not None:
            mutate(root)

        result = run_validator(root)

        if result.returncode != 0:
            raise AssertionError(
                f"{name}: validator unexpectedly failed\n"
                f"{result.stdout}{result.stderr}"
            )

        print(f"PASS valid case: {name}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def set_0002_status(root: Path, status: str) -> None:
    register_path = root / "docs/decisions/register.md"
    register_text = register_path.read_text()

    register_row = next(
        line
        for line in register_text.splitlines()
        if line.startswith(
            "| `0002` | `governance.decision-system` | "
            "Establish governed decision records |"
        )
    )

    fields = register_row.split(" | ")
    fields[3] = f"`{status}`"
    new_register_row = " | ".join(fields)

    register_path.write_text(
        register_text.replace(
            register_row,
            new_register_row,
            1,
        )
    )

    record_path = (
        root
        / "docs/decisions/0002-decision-governance.md"
    )
    record_text = record_path.read_text()

    status_line = next(
        line
        for line in record_text.splitlines()
        if line.startswith("**Status:**")
    )

    record_path.write_text(
        record_text.replace(
            status_line,
            f"**Status:** `{status}`",
            1,
        )
    )



def set_0002_research(
    root: Path,
    program: str,
    category: str,
    consequence: str,
) -> None:
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Research Program:** `NONE`",
        f"**Research Program:** `{program}`",
    )
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Research Change Category:** `NONE`",
        f"**Research Change Category:** `{category}`",
    )
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Evidence Consequence:** `NONE`",
        f"**Evidence Consequence:** `{consequence}`",
    )


def duplicate_id(root: Path) -> None:
    path = root / "docs/decisions/register.md"
    text = path.read_text()

    row = next(
        line
        for line in text.splitlines()
        if line.startswith("| `0001` |")
    )

    path.write_text(text + "\n" + row + "\n")


def duplicate_record_reference(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/register.md",
        "`0002-decision-governance.md`",
        "`0001-reset-active-repository.md`",
    )


def unknown_status(root: Path) -> None:
    set_0002_status(root, "UNKNOWN")



def unknown_class(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/register.md",
        "`GOVERNANCE` | `AUTH-HETREN-MVP-3.0` | "
        "`0002-decision-governance.md`",
        "`MAGIC` | `AUTH-HETREN-MVP-3.0` | "
        "`0002-decision-governance.md`",
    )
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Class:** `GOVERNANCE`",
        "**Class:** `MAGIC`",
    )



def invalid_authority(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/register.md",
        "`GOVERNANCE` | `AUTH-HETREN-MVP-3.0` | `0002-decision-governance.md`",
        "`GOVERNANCE` | `AUTH-MVP-PLAN-2.0` | `0002-decision-governance.md`",
    )
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Authority:** `AUTH-HETREN-MVP-3.0`",
        "**Authority:** `AUTH-MVP-PLAN-2.0`",
    )


def resurrect_old_authority_table(root: Path) -> None:
    path = root / "docs/decisions/register.md"
    text = path.read_text()

    anchor = (
        "| `AUTH-HETREN-MVP-3.0` | Hetren Unified MVP and Adaptive "
        "Intelligence Execution Plan v3.0 |"
    )

    replacement = (
        anchor
        + "\n"
        + "| `AUTH-MVP-PLAN-2.0` | Historical MVP v2 |"
    )

    assert anchor in text
    path.write_text(text.replace(anchor, replacement, 1))


def remove_current_authority(root: Path) -> None:
    path = root / "docs/decisions/register.md"
    text = path.read_text()

    line = (
        "| `AUTH-HETREN-MASTER-2.0` | Hetren Unified Product, "
        "Intelligence, and Adaptive Research Master Specification v2.0 |\n"
    )

    assert line in text
    path.write_text(text.replace(line, "", 1))


def invalid_register_version(root: Path) -> None:
    path = root / "docs/decisions/register.md"
    text = path.read_text()

    version_line = next(
        line
        for line in text.splitlines()
        if line.startswith("**Version:**")
    )

    path.write_text(
        text.replace(
            version_line,
            "**Version:** invalid-version",
            1,
        )
    )


def inactive_register_status(root: Path) -> None:
    path = root / "docs/decisions/register.md"
    text = path.read_text()

    status_line = next(
        line
        for line in text.splitlines()
        if line.startswith("**Status:**")
    )

    path.write_text(
        text.replace(
            status_line,
            "**Status:** Draft",
            1,
        )
    )


def corrupt_governing_header(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/register.md",
        "**Governing execution authority:** `AUTH-HETREN-MVP-3.0`",
        "**Governing execution authority:** `AUTH-MVP-PLAN-2.0`",
    )


def heading_id_mismatch(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "# Decision 0002:",
        "# Decision 9999:",
    )


def metadata_id_mismatch(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Decision ID:** `0002`",
        "**Decision ID:** `9999`",
    )


def metadata_title_mismatch(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Title:** `Establish governed decision records`",
        "**Title:** `Drifted title`",
    )


def heading_title_mismatch(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "# Decision 0002: Establish governed decision records",
        "# Decision 0002: Drifted heading title",
    )


def missing_record(root: Path) -> None:
    (
        root
        / "docs/decisions/0002-decision-governance.md"
    ).unlink()


def unregistered_record(root: Path) -> None:
    source = (
        root
        / "docs/decisions/0002-decision-governance.md"
    )
    target = root / "docs/decisions/0003-orphan.md"
    target.write_text(source.read_text())


def missing_metadata(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Research Program:** `NONE`",
        "**Removed Research Program:** `NONE`",
    )


def missing_section(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "## Research Impact",
        "## Removed Research Impact",
    )


def path_escape(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/register.md",
        "`0002-decision-governance.md`",
        "`../0002-decision-governance.md`",
    )


def invalid_reversibility(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Reversibility:** `CONDITIONALLY_REVERSIBLE`",
        "**Reversibility:** `MAGIC`",
    )


def impossible_calendar_date(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Date:** `2026-09-16`",
        "**Date:** `2026-02-30`",
    )


def invalid_key_format(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/register.md",
        "`governance.decision-system`",
        "`Governance BAD Key`",
    )
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Decision Key:** `governance.decision-system`",
        "**Decision Key:** `Governance BAD Key`",
    )


def template_missing_metadata(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/template.md",
        "**Research Program:**",
        "**Removed Research Program:**",
    )


def template_missing_section(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/template.md",
        "## Research Impact",
        "## Removed Research Impact",
    )


def template_missing_program_vocabulary(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/template.md",
        "CROSS_PROGRAM",
        "REMOVED_PROGRAM",
    )


def register_mapping_drift(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/register.md",
        "| `BUG` | `INVALIDATE_AFFECTED_RESULTS_AND_RERUN` |",
        "| `BUG` | `NEW_REPLICATION_RESULT` |",
    )


def conflicting_accepted_key(root: Path) -> None:
    set_0002_status(root, "ACCEPTED")

    mutate_file(
        root,
        "docs/decisions/register.md",
        "`governance.decision-system`",
        "`repository.active-foundation`",
    )
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Decision Key:** `governance.decision-system`",
        "**Decision Key:** `repository.active-foundation`",
    )



def accepted_pending_implementation(root: Path) -> None:
    set_0002_status(root, "ACCEPTED")

    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "Task 2 implementation currently consists of:",
        "Pending implementation evidence.",
    )


def accepted_pending_verification(root: Path) -> None:
    set_0002_status(root, "ACCEPTED")

    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "Task 2 verification completed on 2026-09-17.",
        "Pending verification evidence.",
    )


def accepted_missing_qualification(root: Path) -> None:
    set_0002_status(root, "ACCEPTED")
    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Qualification:** `Task 2 decision-governance qualification`",
        "**Qualification:** `Pending`",
    )


def asymmetric_supersession(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/register.md",
        "`repository.active-foundation` | Reset the active repository for MVP v2 | `ACCEPTED`",
        "`repository.active-foundation` | Reset the active repository for MVP v2 | `SUPERSEDED`",
    )
    mutate_file(
        root,
        "docs/decisions/0001-reset-active-repository.md",
        "**Status:** `ACCEPTED`",
        "**Status:** `SUPERSEDED`",
    )
    mutate_file(
        root,
        "docs/decisions/0001-reset-active-repository.md",
        "**Superseded By:** `None`",
        "**Superseded By:** `0002`",
    )


def supersession_key_mismatch(root: Path) -> None:
    mutate_file(
        root,
        "docs/decisions/register.md",
        "`repository.active-foundation` | Reset the active repository for MVP v2 | `ACCEPTED`",
        "`repository.active-foundation` | Reset the active repository for MVP v2 | `SUPERSEDED`",
    )
    mutate_file(
        root,
        "docs/decisions/0001-reset-active-repository.md",
        "**Status:** `ACCEPTED`",
        "**Status:** `SUPERSEDED`",
    )
    mutate_file(
        root,
        "docs/decisions/0001-reset-active-repository.md",
        "**Superseded By:** `None`",
        "**Superseded By:** `0002`",
    )

    set_0002_status(root, "ACCEPTED")

    mutate_file(
        root,
        "docs/decisions/0002-decision-governance.md",
        "**Supersedes:** `None`",
        "**Supersedes:** `0001`",
    )


def invalid_research_program(root: Path) -> None:
    set_0002_research(
        root,
        "MAGIC",
        "NONE",
        "NONE",
    )


def invalid_research_category(root: Path) -> None:
    set_0002_research(
        root,
        "NATIVE",
        "MAGIC",
        "NONE",
    )


def program_category_mismatch(root: Path) -> None:
    set_0002_research(
        root,
        "NATIVE",
        "NONE",
        "NONE",
    )


def category_without_program(root: Path) -> None:
    set_0002_research(
        root,
        "NONE",
        "THESIS",
        "NEW_PROGRAM_VERSION_AND_RERUN",
    )


def main() -> int:
    expect_pass("baseline governance")

    for category, consequence in CATEGORY_CONSEQUENCES.items():
        expect_pass(
            f"valid NATIVE {category} mapping",
            lambda root, c=category, e=consequence: set_0002_research(
                root,
                "NATIVE",
                c,
                e,
            ),
        )

    expect_pass(
        "valid ADAPTIVE research decision",
        lambda root: set_0002_research(
            root,
            "ADAPTIVE",
            "METRIC",
            CATEGORY_CONSEQUENCES["METRIC"],
        ),
    )

    expect_pass(
        "valid CROSS_PROGRAM research decision",
        lambda root: set_0002_research(
            root,
            "CROSS_PROGRAM",
            "DATA",
            CATEGORY_CONSEQUENCES["DATA"],
        ),
    )

    cases = [
        ("duplicate Decision ID", duplicate_id, "duplicate Decision ID"),
        (
            "duplicate record reference",
            duplicate_record_reference,
            "duplicate decision-record reference",
        ),
        ("unknown status", unknown_status, "unknown status UNKNOWN"),
        ("unknown class", unknown_class, "unknown class MAGIC"),
        (
            "old authority used by active decision",
            invalid_authority,
            "unknown authority AUTH-MVP-PLAN-2.0",
        ),
        (
            "old authority resurrected in authority table",
            resurrect_old_authority_table,
            "register contains non-current authority AUTH-MVP-PLAN-2.0",
        ),
        (
            "current authority removed",
            remove_current_authority,
            "register missing current authority AUTH-HETREN-MASTER-2.0",
        ),
        (
            "invalid register version",
            invalid_register_version,
            "register has invalid semantic Version",
        ),
        (
            "inactive accepted register",
            inactive_register_status,
            "register Status must be Active",
        ),
        (
            "governing authority header drift",
            corrupt_governing_header,
            "register missing required governing metadata",
        ),
        (
            "heading ID mismatch",
            heading_id_mismatch,
            "heading Decision ID mismatch",
        ),
        (
            "metadata ID mismatch",
            metadata_id_mismatch,
            "record Decision ID mismatch",
        ),
        (
            "metadata title mismatch",
            metadata_title_mismatch,
            "metadata Title mismatch",
        ),
        (
            "heading title mismatch",
            heading_title_mismatch,
            "title mismatch",
        ),
        ("missing record", missing_record, "missing record"),
        (
            "unregistered record",
            unregistered_record,
            "unregistered decision file",
        ),
        (
            "missing research metadata",
            missing_metadata,
            "missing metadata Research Program",
        ),
        (
            "missing Research Impact section",
            missing_section,
            "missing section Research Impact",
        ),
        ("record path escape", path_escape, "invalid record path"),
        (
            "invalid reversibility",
            invalid_reversibility,
            "unknown reversibility MAGIC",
        ),
        (
            "impossible calendar date",
            impossible_calendar_date,
            "invalid calendar date 2026-02-30",
        ),
        (
            "invalid Decision Key",
            invalid_key_format,
            "invalid Decision Key",
        ),
        (
            "template missing metadata",
            template_missing_metadata,
            "decision template missing metadata Research Program",
        ),
        (
            "template missing section",
            template_missing_section,
            "decision template missing section Research Impact",
        ),
        (
            "template missing research-program vocabulary",
            template_missing_program_vocabulary,
            "decision template missing Research Program CROSS_PROGRAM",
        ),
        (
            "register scientific mapping drift",
            register_mapping_drift,
            "register research evidence consequence map does not match validator contract",
        ),
        (
            "conflicting accepted key",
            conflicting_accepted_key,
            "conflicting ACCEPTED Decision Key",
        ),
        (
            "accepted pending implementation",
            accepted_pending_implementation,
            "ACCEPTED decision has pending implementation evidence",
        ),
        (
            "accepted pending verification",
            accepted_pending_verification,
            "ACCEPTED decision has pending verification",
        ),
        (
            "accepted missing qualification",
            accepted_missing_qualification,
            "ACCEPTED decision lacks qualification",
        ),
        (
            "asymmetric supersession",
            asymmetric_supersession,
            "asymmetric supersession",
        ),
        (
            "supersession across Decision Keys",
            supersession_key_mismatch,
            "supersession Decision Key mismatch",
        ),
        (
            "invalid research program",
            invalid_research_program,
            "invalid Research Program MAGIC",
        ),
        (
            "invalid research category",
            invalid_research_category,
            "invalid Research Change Category MAGIC",
        ),
        (
            "research program/category mismatch",
            program_category_mismatch,
            "research program/category mismatch",
        ),
        (
            "research category without program",
            category_without_program,
            "research category requires a research program",
        ),
    ]

    killed = 0

    for name, mutate, expected in cases:
        expect_fail(name, mutate, expected)
        killed += 1

    for category, consequence in CATEGORY_CONSEQUENCES.items():
        expect_fail(
            f"wrong evidence consequence for {category}",
            lambda root, c=category: set_0002_research(
                root,
                "NATIVE",
                c,
                "WRONG_CONSEQUENCE",
            ),
            f"{category} requires Evidence Consequence {consequence}",
        )
        killed += 1

    print()
    print(
        f"MUTATION QUALIFICATION: PASS "
        f"({killed}/{killed} mutations killed)"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
