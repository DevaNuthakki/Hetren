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

POSITIVE_DATA = (
    DATA_DIR
    / "positive_cases.json"
)

POSITIVE_SCHEMA = (
    DATA_DIR
    / "positive_cases.schema.json"
)

INVARIANTS = (
    DATA_DIR
    / "invariants.json"
)

SET_C_SUITE = (
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
    "task7_positive_set_c_helpers",
    SET_C_SUITE,
)


def validate_positive_data():
    data = load_json(
        POSITIVE_DATA
    )

    schema = load_json(
        POSITIVE_SCHEMA
    )

    invariants = load_json(
        INVARIANTS
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

    assert len(cases) == 24
    assert data[
        "positive_case_count"
    ] == 24

    assert data[
        "family_count"
    ] == 8

    assert data[
        "variants_per_family"
    ] == 3

    case_ids = [
        case["case_id"]
        for case in cases
    ]

    assert len(case_ids) == len(
        set(case_ids)
    )

    family_counts = Counter(
        case["family_id"]
        for case in cases
    )

    assert family_counts == Counter(
        {
            f"C{number:02d}": 3
            for number in range(
                1,
                9,
            )
        }
    )

    known_invariants = {
        item["invariant_id"]
        for item in invariants[
            "invariants"
        ]
    }

    for case in cases:
        assert case[
            "expected"
        ] == "MUST_ACCEPT"

        missing = (
            set(
                case[
                    "related_invariant_ids"
                ]
            )
            - known_invariants
        )

        assert not missing, (
            f"{case['case_id']} references "
            f"unknown invariants: "
            f"{sorted(missing)}"
        )

    return data


def apply_operation(
    root: Path,
    operation: dict,
) -> None:
    kind = operation[
        "operation"
    ]

    if kind == "APPEND_SPEC_SECTION":
        assert operation[
            "document"
        ] == "SPEC"

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

    if kind == "APPEND_DECISION_SECTION":
        assert operation[
            "document"
        ] == "DECISION"

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
        f"unsupported positive operation: {kind}"
    )


def run_baseline_positive_control() -> None:
    root = set_c.helpers.make_repo()

    try:
        set_c.helpers.set_development_state(
            root
        )

        result = (
            set_c.helpers.run_validator(
                root
            )
        )

        if result.returncode != 0:
            output = (
                result.stdout
                + result.stderr
            )

            raise AssertionError(
                "baseline development state "
                "failed before positive cases:\n"
                + output
            )

    finally:
        shutil.rmtree(
            root
        )


def run_positive_cases():
    data = validate_positive_data()

    cases = data[
        "cases"
    ]

    passed = 0
    failures = []

    family_results = {
        f"C{number:02d}": {
            "passed": 0,
            "total": 0,
        }
        for number in range(
            1,
            9,
        )
    }

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

            accepted = (
                result.returncode == 0
            )

            family = case[
                "family_id"
            ]

            family_results[
                family
            ][
                "total"
            ] += 1

            if accepted:
                passed += 1

                family_results[
                    family
                ][
                    "passed"
                ] += 1

                print(
                    "PASS MUST_ACCEPT accepted: "
                    f"{case['case_id']} "
                    f"{case['family']}"
                )

                continue

            output = (
                result.stdout
                + result.stderr
            ).strip()

            failures.append(
                {
                    "case_id": (
                        case[
                            "case_id"
                        ]
                    ),
                    "family_id": family,
                    "family": case[
                        "family"
                    ],
                    "output": output,
                }
            )

            print(
                "FAIL MUST_ACCEPT rejected: "
                f"{case['case_id']} "
                f"{case['family']}"
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

    return (
        passed,
        failures,
        family_results,
    )


def main() -> int:
    print(
        "===== POSITIVE DATA VALIDATION ====="
    )

    validate_positive_data()

    print(
        "PASS: positive data and invariant "
        "references validated"
    )

    print()
    print(
        "===== BASELINE POSITIVE CONTROL ====="
    )

    run_baseline_positive_control()

    print(
        "PASS: unmodified development "
        "contract accepted"
    )

    print()
    print(
        "===== MUST_ACCEPT FIRST-RUN CASES ====="
    )

    (
        passed,
        failures,
        family_results,
    ) = run_positive_cases()

    print()
    print(
        "===== FAMILY RESULTS ====="
    )

    for family in sorted(
        family_results
    ):
        result = family_results[
            family
        ]

        print(
            f"{family}: "
            f"{result['passed']}/"
            f"{result['total']} accepted"
        )

    total = (
        passed
        + len(failures)
    )

    print()
    print(
        "===== POSITIVE RESULT ====="
    )

    print(
        f"Accepted: {passed}/{total}"
    )

    print(
        f"Rejected: {len(failures)}/{total}"
    )

    if failures:
        print(
            "TASK 7 MUST_ACCEPT SUITE: "
            f"FAIL ({len(failures)} "
            "valid cases rejected)"
        )

        print()
        print(
            "Rejected case IDs:"
        )

        for failure in failures:
            print(
                f"- {failure['case_id']}"
            )

        return 1

    print(
        "TASK 7 MUST_ACCEPT SUITE: "
        f"PASS ({passed}/{total} accepted)"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
