#!/usr/bin/env python3

from __future__ import annotations

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
    "hetren_task7_canonical_helpers",
    CANONICAL,
)

if module_spec is None or module_spec.loader is None:
    raise RuntimeError(
        "could not load canonical Task 7 helper module"
    )

helpers = importlib.util.module_from_spec(
    module_spec
)

module_spec.loader.exec_module(
    helpers
)


SPEC = helpers.SPEC
DECISION = helpers.DECISION

HOLDOUT_EXPECTED = 12


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


def run_holdout() -> tuple[int, list[str]]:
    killed = 0
    survived: list[str] = []

    cases = (
        (
            "distant fourth PartitionRole authorization",
            lambda root: append_to_numbered_section(
                root,
                48,
                "Governed Extension",
                (
                    "Operational implementations may additionally "
                    "use `CALIBRATION` as a fourth `PartitionRole` "
                    "without revising the three-value governed "
                    "vocabulary."
                ),
            ),
        ),
        (
            "distant eighth PartitionPurpose authorization",
            lambda root: append_to_numbered_section(
                root,
                48,
                "Governed Extension",
                (
                    "A deployment may introduce "
                    "`TUNING_FEEDBACK` as an additional "
                    "`PartitionPurpose` without changing the "
                    "seven-value purpose contract."
                ),
            ),
        ),
        (
            "SplitVersion membership edited in place",
            lambda root: append_to_numbered_section(
                root,
                12,
                "SplitVersion",
                (
                    "Membership may be edited in place while "
                    "retaining the existing `SplitVersion` when "
                    "the manifest checksum and modification "
                    "timestamp are updated."
                ),
            ),
        ),
        (
            "materially changed candidate keeps identity",
            lambda root: append_to_numbered_section(
                root,
                22,
                "Candidate Freeze",
                (
                    "A materially modified candidate may retain "
                    "its existing candidate identity when the "
                    "operator considers the change semantically "
                    "equivalent."
                ),
            ),
        ),
        (
            "UNKNOWN contamination automatically expires to CLEAN",
            lambda root: append_to_numbered_section(
                root,
                27,
                "ContaminationState",
                (
                    "`UNKNOWN` contamination may automatically "
                    "transition to `CLEAN` after thirty days when "
                    "no additional contamination evidence has "
                    "been recorded."
                ),
            ),
        ),
        (
            "unlimited aggregate protected-score peeking",
            lambda root: append_to_numbered_section(
                root,
                28,
                "Repeated Protected Peeking",
                (
                    "Aggregate-only protected scores may be "
                    "inspected without an evaluation-count limit "
                    "because individual protected cases are not "
                    "revealed."
                ),
            ),
        ),
        (
            "generated summaries declared freshness-neutral",
            lambda root: append_to_numbered_section(
                root,
                30,
                "Fresh Protected Evidence",
                (
                    "Generated summaries of protected evidence "
                    "are freshness-neutral and may influence a "
                    "descendant candidate without affecting that "
                    "candidate's protected-evidence freshness."
                ),
            ),
        ),
        (
            "same N-H1 source counted independent with different evaluators",
            lambda root: append_to_numbered_section(
                root,
                32,
                "N-H1 Independent Evaluation Units",
                (
                    "Two evaluations derived from the same "
                    "underlying protected case may satisfy the "
                    "two-unit independence gate when separate "
                    "human evaluators perform them."
                ),
            ),
        ),
        (
            "three N-H2 boundaries manufacture universal transfer",
            lambda root: append_to_numbered_section(
                root,
                35,
                "N-H2 Leave-One-Family-Out Boundaries",
                (
                    "Passing all three initial held-out family "
                    "boundaries is sufficient to claim universal "
                    "Native transfer beyond the evaluated MVP "
                    "environment families."
                ),
            ),
        ),
        (
            "A-H1 success automatically satisfies A-H2",
            lambda root: append_to_numbered_section(
                root,
                39,
                "A-H2 Split Binding",
                (
                    "A passing `A-H1` result automatically "
                    "satisfies `A-H2` when both experiments use "
                    "the same adapted candidate."
                ),
            ),
        ),
        (
            "originating process self-certifies with audit log",
            lambda root: append_to_numbered_section(
                root,
                44,
                "Independent Verification And Authority Separation",
                (
                    "The originating candidate-construction "
                    "process may perform its own certification "
                    "when it retains a complete audit log of "
                    "the verification run."
                ),
            ),
        ),
        (
            "comparator selected after outcomes for favorable efficiency",
            lambda root: append_to_numbered_section(
                root,
                45,
                "Task 8 Baseline Handoff",
                (
                    "After protected outcomes are available, the "
                    "comparison may switch to a lower-cost "
                    "comparator when that comparator produces a "
                    "more favorable efficiency conclusion."
                ),
            ),
        ),
    )

    if len(cases) != HOLDOUT_EXPECTED:
        raise AssertionError(
            "holdout cardinality mismatch: "
            f"{len(cases)} != {HOLDOUT_EXPECTED}"
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
                    f"FAIL holdout survived: {label}"
                )

            else:
                killed += 1

                print(
                    f"PASS holdout killed: {label}"
                )

        finally:
            shutil.rmtree(
                root
            )

    return killed, survived


def main() -> None:
    print(
        "===== HOLDOUT POSITIVE CONTROL ====="
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
                "holdout positive control failed:\n"
                + result.stdout
                + result.stderr
            )

        print(
            "PASS holdout positive control"
        )

    finally:
        shutil.rmtree(
            root
        )

    print()
    print(
        "===== SET A DISCOVERED RED-TEAM REGRESSION 1-12 ====="
    )

    killed, survived = run_holdout()

    print()
    print(
        "===== HOLDOUT RESULT ====="
    )
    print(
        f"Killed: {killed}/{HOLDOUT_EXPECTED}"
    )
    print(
        f"Survived: {len(survived)}/{HOLDOUT_EXPECTED}"
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
            "Task 7 validator has Set A red-team survivors"
        )

    print(
        "TASK 7 SET A RED-TEAM REGRESSION: PASS "
        f"({killed}/{HOLDOUT_EXPECTED} attacks killed)"
    )


if __name__ == "__main__":
    main()
