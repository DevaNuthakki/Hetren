from __future__ import annotations

from collections import Counter
from pathlib import Path
import importlib.util
import json
import shutil
import sys

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "initial_splits"
)

DATA_FILE = (
    DATA_DIR
    / "set_e_cases.json"
)

SCHEMA_FILE = (
    DATA_DIR
    / "set_e_cases.schema.json"
)

INVARIANTS_FILE = (
    DATA_DIR
    / "invariants.json"
)

SET_C_FILE = (
    ROOT
    / "tests"
    / "qualification"
    / "test_initial_splits_holdout_c.py"
)


def load_module(
    name: str,
    path: Path,
):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    if spec is None or spec.loader is None:
        raise AssertionError(
            f"cannot import {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


def load_json(
    path: Path,
):
    return json.loads(
        path.read_text()
    )


set_c = load_module(
    "task7_set_e_helpers",
    SET_C_FILE,
)


def validate_definition_data():
    data = load_json(
        DATA_FILE
    )

    schema = load_json(
        SCHEMA_FILE
    )

    invariants = load_json(
        INVARIANTS_FILE
    )

    Draft202012Validator.check_schema(
        schema
    )

    Draft202012Validator(
        schema
    ).validate(
        data
    )

    cases = data[
        "cases"
    ]

    assert len(cases) == 32

    assert Counter(
        case["expected"]
        for case in cases
    ) == Counter(
        {
            "MUST_REJECT": 16,
            "MUST_ACCEPT": 16,
        }
    )

    invariant_labels = {
        item["invariant_id"]:
            item["label"]
        for item in invariants[
            "invariants"
        ]
    }

    for case in cases:
        for invariant_id in case[
            "related_invariant_ids"
        ]:
            assert (
                invariant_id
                in invariant_labels
            )

    return (
        data,
        invariant_labels,
    )


def apply_operation(
    root: Path,
    operation: dict,
) -> None:
    if (
        operation["operation"]
        == "APPEND_SPEC_SECTION"
    ):
        set_c.append_to_numbered_section(
            root,
            operation[
                "section_number"
            ],
            operation[
                "section_title"
            ],
            operation[
                "addition"
            ],
        )

        return

    if (
        operation["operation"]
        == "APPEND_DECISION_SECTION"
    ):
        set_c.append_to_decision_section(
            root,
            operation[
                "section_title"
            ],
            operation[
                "addition"
            ],
        )

        return

    raise AssertionError(
        "unsupported Set E operation: "
        f"{operation['operation']}"
    )


def main() -> int:
    (
        data,
        invariant_labels,
    ) = validate_definition_data()

    cases = data[
        "cases"
    ]

    correct = 0
    failures = []

    family_results = {
        f"E{number:02d}": {
            "correct": 0,
            "total": 0,
        }
        for number in range(
            1,
            9,
        )
    }

    print(
        "===== FROZEN SET E ====="
    )

    print(
        "Cases: 32"
    )

    print(
        "MUST_REJECT: 16"
    )

    print(
        "MUST_ACCEPT: 16"
    )

    for case in cases:
        root = (
            set_c.helpers.make_repo()
        )

        try:
            set_c.helpers.set_development_state(
                root
            )

            for operation in case[
                "operations"
            ]:
                apply_operation(
                    root,
                    operation,
                )

            result = (
                set_c.helpers.run_validator(
                    root
                )
            )

            output = (
                result.stdout
                + result.stderr
            ).strip()

            expected = case[
                "expected"
            ]

            if expected == "MUST_ACCEPT":
                case_correct = (
                    result.returncode == 0
                )

            else:
                related_labels = [
                    invariant_labels[
                        invariant_id
                    ]
                    for invariant_id in case[
                        "related_invariant_ids"
                    ]
                ]

                case_correct = (
                    result.returncode != 0
                    and any(
                        label in output
                        for label in related_labels
                    )
                )

            family = case[
                "family_id"
            ]

            family_results[
                family
            ][
                "total"
            ] += 1

            if case_correct:
                correct += 1

                family_results[
                    family
                ][
                    "correct"
                ] += 1

                print(
                    f"PASS {case['case_id']} "
                    f"{expected}"
                )

                continue

            failures.append(
                {
                    "case_id": case[
                        "case_id"
                    ],
                    "family_id": family,
                    "expected": expected,
                    "returncode": (
                        result.returncode
                    ),
                    "output": output,
                }
            )

            print(
                f"FAIL {case['case_id']} "
                f"{expected}"
            )

            print(
                "----- validator output -----"
            )

            print(
                output
                if output
                else "<no output>"
            )

            print(
                "----------------------------"
            )

        finally:
            shutil.rmtree(
                root
            )

    print()
    print(
        "===== SET E FAMILY RESULTS ====="
    )

    for family in sorted(
        family_results
    ):
        result = family_results[
            family
        ]

        print(
            f"{family}: "
            f"{result['correct']}/"
            f"{result['total']} correct"
        )

    print()
    print(
        "===== SET E RESULT ====="
    )

    print(
        f"Correct: {correct}/32"
    )

    print(
        f"Incorrect: {len(failures)}/32"
    )

    if failures:
        print(
            "TASK 7 SET E HOLDOUT: "
            f"FAIL ({correct}/32 correct)"
        )

        print()
        print(
            "Incorrect case IDs:"
        )

        for failure in failures:
            print(
                f"- {failure['case_id']} "
                f"expected={failure['expected']}"
            )

        return 1

    print(
        "TASK 7 SET E HOLDOUT: "
        "PASS (32/32 correct)"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
