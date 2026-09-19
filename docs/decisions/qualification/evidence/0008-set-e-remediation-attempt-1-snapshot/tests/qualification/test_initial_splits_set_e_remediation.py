from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import shutil
import sys

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]

DATA = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "initial_splits"
    / "set_e_remediation_cases.json"
)

SCHEMA = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "initial_splits"
    / "set_e_remediation_cases.schema.json"
)

SET_C = (
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


helpers = load_module(
    "task7_post_set_e_helpers",
    SET_C,
)


def main() -> int:
    data = json.loads(
        DATA.read_text()
    )

    schema = json.loads(
        SCHEMA.read_text()
    )

    Draft202012Validator.check_schema(
        schema
    )

    Draft202012Validator(
        schema
    ).validate(
        data
    )

    assert data[
        "evidence_class"
    ] == "KNOWN_REGRESSION"

    assert data[
        "case_count"
    ] == 13

    correct = 0
    failures = []

    print(
        "===== POST-SET-E KNOWN REGRESSIONS ====="
    )

    for case in data[
        "cases"
    ]:
        root = (
            helpers.helpers.make_repo()
        )

        try:
            helpers.helpers.set_development_state(
                root
            )

            helpers.append_to_numbered_section(
                root,
                case[
                    "section_number"
                ],
                case[
                    "section_title"
                ],
                case[
                    "addition"
                ],
            )

            result = (
                helpers.helpers.run_validator(
                    root
                )
            )

            output = (
                result.stdout
                + result.stderr
            )

            if (
                case[
                    "expected"
                ]
                == "MUST_ACCEPT"
            ):
                case_correct = (
                    result.returncode == 0
                )

            else:
                case_correct = (
                    result.returncode != 0
                    and case[
                        "expected_label"
                    ]
                    in output
                )

            if case_correct:
                correct += 1

                print(
                    f"PASS {case['case_id']} "
                    f"{case['expected']}"
                )

                continue

            failures.append(
                case[
                    "case_id"
                ]
            )

            print(
                f"FAIL {case['case_id']} "
                f"{case['expected']}"
            )

            print(
                output.strip()
                if output.strip()
                else "<no validator output>"
            )

        finally:
            shutil.rmtree(
                root
            )

    print()
    print(
        f"Correct: {correct}/13"
    )

    print(
        f"Incorrect: {len(failures)}/13"
    )

    if failures:
        print(
            "TASK 7 POST-SET-E REMEDIATION REGRESSIONS: "
            f"FAIL ({correct}/13 correct)"
        )

        print(
            "Failures:",
            ", ".join(
                failures
            )
        )

        return 1

    print(
        "TASK 7 POST-SET-E REMEDIATION REGRESSIONS: "
        "PASS (13/13 correct)"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
