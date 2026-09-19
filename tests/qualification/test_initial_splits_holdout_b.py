#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CANONICAL = (
    ROOT
    / "tests"
    / "qualification"
    / "test_initial_splits.py"
)

module_spec = importlib.util.spec_from_file_location(
    "hetren_task7_set_b_helpers",
    CANONICAL,
)

if module_spec is None or module_spec.loader is None:
    raise RuntimeError(
        "could not load canonical Task 7 helpers"
    )

helpers = importlib.util.module_from_spec(
    module_spec
)

module_spec.loader.exec_module(
    helpers
)

SPEC = helpers.SPEC
DECISION = helpers.DECISION

SET_B_EXPECTED = 12


def append_to_numbered_section(
    root: Path,
    section_number: int,
    section_title: str,
    addition: str,
) -> None:
    target = root / SPEC
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

    body = match.group(1).rstrip()

    updated_body = (
        body
        + "\n\n"
        + addition.strip()
        + "\n"
    )

    updated = (
        text[:match.start(1)]
        + updated_body
        + text[match.end(1):]
    )

    target.write_text(
        updated
    )


def append_to_decision_section(
    root: Path,
    section_title: str,
    addition: str,
) -> None:
    target = root / DECISION
    text = target.read_text()

    pattern = (
        rf"(?ms)^## {re.escape(section_title)}\n"
        r"(.*?)"
        r"(?=^## |\Z)"
    )

    match = re.search(
        pattern,
        text,
    )

    if not match:
        raise AssertionError(
            "decision section not found: "
            f"{section_title}"
        )

    body = match.group(1).rstrip()

    updated_body = (
        body
        + "\n\n"
        + addition.strip()
        + "\n"
    )

    target.write_text(
        text[:match.start(1)]
        + updated_body
        + text[match.end(1):]
    )


def mutate_distributed_baseline_cost(
    root: Path,
) -> None:
    append_to_numbered_section(
        root,
        45,
        "Task 8 Baseline Handoff",
        (
            "The baseline identity can remain frozen even when "
            "later resource eligibility determines which frozen "
            "comparator is included in the reported comparison."
        ),
    )

    append_to_numbered_section(
        root,
        46,
        "Task 9 Cost And Resource Handoff",
        (
            "Once protected measurements are known, eligibility "
            "may be narrowed by changing the accounting window so "
            "that only the comparator yielding the preferred "
            "efficiency conclusion remains reportable."
        ),
    )


def set_b_cases():
    return (
        (
            "operational alias bypasses closed PartitionRole vocabulary",
            lambda root: append_to_numbered_section(
                root,
                48,
                "Governed Extension",
                (
                    "Implementations may persist `TRAINING` wherever "
                    "`DEVELOPMENT` is expected and normalize it to "
                    "`DEVELOPMENT` only when reports are emitted. "
                    "This operational alias is not considered an "
                    "extension of `PartitionRole`."
                ),
            ),
        ),
        (
            "operational alias bypasses closed PartitionPurpose vocabulary",
            lambda root: append_to_numbered_section(
                root,
                48,
                "Governed Extension",
                (
                    "Systems may persist `OPTIMIZATION_TARGET` as an "
                    "operational alias of `PRIMARY_OUTCOME` and "
                    "normalize the value only at evidence-export time. "
                    "The alias need not be registered as a distinct "
                    "`PartitionPurpose`."
                ),
            ),
        ),
        (
            "frozen SplitVersion repointed to revised member set",
            lambda root: append_to_numbered_section(
                root,
                12,
                "SplitVersion",
                (
                    "A frozen `SplitVersion` may keep its identifier "
                    "after its manifest is repointed to a revised "
                    "member set, provided the previous digest remains "
                    "available in the audit trail."
                ),
            ),
        ),
        (
            "protected telemetry dashboard influences descendant candidate",
            lambda root: append_to_numbered_section(
                root,
                30,
                "Fresh Protected Evidence",
                (
                    "A dashboard computed only from protected-case "
                    "metrics may be shown to developers and used to "
                    "choose the next candidate when raw protected "
                    "records are hidden. Such telemetry is not treated "
                    "as protected-outcome exposure."
                ),
            ),
        ),
        (
            "SUSPECTED contamination treated as CLEAN below confidence threshold",
            lambda root: append_to_numbered_section(
                root,
                27,
                "ContaminationState",
                (
                    "`SUSPECTED` may be treated as `CLEAN` for release "
                    "gating when estimated contamination probability "
                    "is below `0.05`, without changing the stored "
                    "contamination state."
                ),
            ),
        ),
        (
            "INVALIDATED protected result restored without rerun",
            lambda root: append_to_numbered_section(
                root,
                29,
                "Invalidation And Split Revision",
                (
                    "An `INVALIDATED` protected result may return to "
                    "`DISCLOSED` after reviewer sign-off without a new "
                    "`SplitVersion` or rerun when the discovered defect "
                    "is subsequently judged immaterial."
                ),
            ),
        ),
        (
            "shared upstream source counted independent via disjoint windows",
            lambda root: append_to_numbered_section(
                root,
                32,
                "N-H1 Independent Evaluation Units",
                (
                    "Two evaluation units sampled from non-overlapping "
                    "time windows of one upstream source may count as "
                    "independent when their identifiers and time ranges "
                    "are distinct."
                ),
            ),
        ),
        (
            "target-family performance bands used for N-H2 method selection",
            lambda root: append_to_numbered_section(
                root,
                36,
                "N-H2 Transfer Leakage Controls",
                (
                    "Before target candidate freeze, transfer methods "
                    "may be ranked using evaluator-produced target-family "
                    "performance bands when per-case labels and exact "
                    "scores remain hidden."
                ),
            ),
        ),
        (
            "A-H2 retroactively validates contaminated A-H1",
            lambda root: append_to_numbered_section(
                root,
                39,
                "A-H2 Split Binding",
                (
                    "A successful `A-H2` retention and rollback result "
                    "may retroactively validate an `A-H1` adaptation "
                    "result whose original outcome separation was "
                    "incomplete."
                ),
            ),
        ),
        (
            "separate process masquerades as independent verifier",
            lambda root: append_to_numbered_section(
                root,
                44,
                "Independent Verification And Authority Separation",
                (
                    "A verifier running in a separate operating-system "
                    "process may certify the candidate even when both "
                    "processes share the same controlling agent, "
                    "writable evidence store, and credentials."
                ),
            ),
        ),
        (
            "distributed baseline and cost rules manufacture preferred comparison",
            mutate_distributed_baseline_cost,
        ),
        (
            "Decision 0008 permits material DATA rerun waiver",
            lambda root: append_to_decision_section(
                root,
                "Decision",
                (
                    "After this decision is accepted, an authorized "
                    "reviewer may waive "
                    "`RERUN_AND_PRESERVE_DATA_DISTINCTIONS` for a "
                    "material split revision when prior results appear "
                    "stable enough to reuse."
                ),
            ),
        ),
    )


def attack_definition_hash() -> str:
    source = Path(__file__).read_text()

    match = re.search(
        r"(?ms)^def set_b_cases\(\):\n.*?^def attack_definition_hash",
        source,
    )

    if not match:
        raise AssertionError(
            "Set B attack-definition block not found"
        )

    return hashlib.sha256(
        match.group(0).encode()
    ).hexdigest()


def run_set_b() -> tuple[int, list[str]]:
    killed = 0
    survived: list[str] = []

    cases = set_b_cases()

    if len(cases) != SET_B_EXPECTED:
        raise AssertionError(
            "Set B cardinality mismatch: "
            f"{len(cases)} != {SET_B_EXPECTED}"
        )

    for label, mutate in cases:
        root = helpers.make_repo()

        try:
            helpers.set_development_state(
                root
            )

            mutate(
                root
            )

            result = helpers.run_validator(
                root
            )

            if result.returncode == 0:
                survived.append(
                    label
                )

                print(
                    f"FAIL Set B survived: {label}"
                )

            else:
                killed += 1

                print(
                    f"PASS Set B killed: {label}"
                )

        finally:
            shutil.rmtree(
                root
            )

    return killed, survived


def main() -> None:
    print(
        "===== SET B POSITIVE CONTROL ====="
    )

    root = helpers.make_repo()

    try:
        helpers.set_development_state(
            root
        )

        result = helpers.run_validator(
            root
        )

        if result.returncode != 0:
            raise AssertionError(
                "Set B positive control failed:\n"
                + result.stdout
                + result.stderr
            )

        print(
            "PASS Set B positive control"
        )

    finally:
        shutil.rmtree(
            root
        )

    print()
    print(
        "===== SET B DISCOVERED RED-TEAM REGRESSION ====="
    )

    print(
        "Attack-definition SHA-256: "
        + attack_definition_hash()
    )

    killed, survived = run_set_b()

    print()
    print(
        "===== SET B RESULT ====="
    )

    print(
        f"Killed: {killed}/{SET_B_EXPECTED}"
    )

    print(
        f"Survived: {len(survived)}/{SET_B_EXPECTED}"
    )

    if survived:
        print(
            "Survivors:"
        )

        for label in survived:
            print(
                f"- {label}"
            )

        raise AssertionError(
            "Task 7 validator has Set B regression survivors"
        )

    print(
        "TASK 7 SET B RED-TEAM REGRESSION: PASS "
        f"({killed}/{SET_B_EXPECTED} attacks killed)"
    )


if __name__ == "__main__":
    main()
