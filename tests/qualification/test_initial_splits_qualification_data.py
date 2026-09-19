from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import importlib.util
import sys

from jsonschema import ValidationError


ROOT = Path(__file__).resolve().parents[2]

CHECKER = (
    ROOT
    / "scripts"
    / "check_initial_splits_qualification_data.py"
)


def load_module(
    name,
    path,
):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
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


validator = load_module(
    "task7_qualification_data_validator",
    CHECKER,
)


def case_by_id(
    qualification,
    case_id,
):
    return next(
        item
        for item in qualification[
            "cases"
        ]
        if item[
            "case_id"
        ] == case_id
    )


def mutate_declared_count(
    qualification,
):
    qualification[
        "qualification_case_count"
    ] = 195


def mutate_suite_count(
    qualification,
):
    qualification[
        "suite_counts"
    ][
        "SET_D"
    ] = 31


def mutate_expectation_count(
    qualification,
):
    qualification[
        "expectation_counts"
    ][
        "MUST_ACCEPT"
    ] = 39


def mutate_first_summary(
    qualification,
):
    qualification[
        "first_run_summary"
    ][
        "ACCEPTED"
    ] = 119


def mutate_current_summary(
    qualification,
):
    qualification[
        "current_summary"
    ][
        "REJECTED"
    ] = 155


def mutate_case_order(
    qualification,
):
    qualification[
        "cases"
    ][0], qualification[
        "cases"
    ][1] = (
        qualification[
            "cases"
        ][1],
        qualification[
            "cases"
        ][0],
    )


def mutate_case_id(
    qualification,
):
    case_by_id(
        qualification,
        "T7-DEV-001",
    )[
        "case_id"
    ] = "T7-DEV-999"


def mutate_p1_original_failure(
    qualification,
):
    case_by_id(
        qualification,
        "T7-POS-C05-01",
    )[
        "first_run_disposition"
    ] = "ACCEPTED"


def mutate_p1_second_failure(
    qualification,
):
    case_by_id(
        qualification,
        "T7-POS-C05-03",
    )[
        "first_run_disposition"
    ] = "ACCEPTED"


def mutate_set_d_false_negative(
    qualification,
):
    case_by_id(
        qualification,
        "T7-D-01-01",
    )[
        "first_run_disposition"
    ] = "REJECTED"


def mutate_set_d_false_positive(
    qualification,
):
    case_by_id(
        qualification,
        "T7-D-05-04",
    )[
        "first_run_disposition"
    ] = "ACCEPTED"


def mutate_set_d_expectation(
    qualification,
):
    case_by_id(
        qualification,
        "T7-D-01-01",
    )[
        "expected"
    ] = "MUST_ACCEPT"


def mutate_historical_unseen(
    qualification,
):
    case_by_id(
        qualification,
        "T7-A-001",
    )[
        "historical_unseen"
    ] = False


def mutate_current_disposition(
    qualification,
):
    case_by_id(
        qualification,
        "T7-POS-C01-01",
    )[
        "current_disposition"
    ] = "REJECTED"


def mutate_definition_ref(
    qualification,
):
    case_by_id(
        qualification,
        "T7-D-01-01",
    )[
        "definition_ref"
    ] = (
        "tests/qualification/"
        "test_initial_splits_holdout_d.py"
    )


def mutate_first_evidence_ref(
    qualification,
):
    case_by_id(
        qualification,
        "T7-POS-C01-01",
    )[
        "first_run_evidence_ref"
    ] = (
        "docs/decisions/qualification/"
        "evidence/"
        "0008-red-team-set-d-first-run.txt"
    )


def mutate_current_evidence_ref(
    qualification,
):
    case_by_id(
        qualification,
        "T7-D-01-01",
    )[
        "current_evidence_ref"
    ] = (
        "docs/decisions/qualification/"
        "evidence/"
        "0008-red-team-set-d-first-run.txt"
    )


def mutate_source_hash(
    qualification,
):
    key = (
        "tests/qualification/data/"
        "initial_splits/positive_cases.json"
    )

    qualification[
        "source_hashes"
    ][
        key
    ] = "0" * 64



def mutate_set_e_false_negative_history(
    qualification,
):
    case_by_id(
        qualification,
        "T7-E-01-02",
    )[
        "first_run_disposition"
    ] = "REJECTED"


def mutate_set_e_false_positive_history(
    qualification,
):
    case_by_id(
        qualification,
        "T7-E-03-03",
    )[
        "first_run_disposition"
    ] = "ACCEPTED"


def mutate_set_e_unseen_provenance(
    qualification,
):
    case_by_id(
        qualification,
        "T7-E-01-01",
    )[
        "historical_unseen"
    ] = False


def mutate_set_e_current_disposition(
    qualification,
):
    case_by_id(
        qualification,
        "T7-E-01-01",
    )[
        "current_disposition"
    ] = "ACCEPTED"


def mutate_set_e_current_evidence_ref(
    qualification,
):
    case_by_id(
        qualification,
        "T7-E-01-01",
    )[
        "current_evidence_ref"
    ] = (
        "docs/decisions/qualification/evidence/"
        "0008-set-e-remediation-attempt-2-wall.txt"
    )


def mutate_known_regression_first_provenance(
    qualification,
):
    case_by_id(
        qualification,
        "T7-E-REG-01",
    )[
        "first_run_disposition"
    ] = "REJECTED"


def mutate_known_regression_unseen_provenance(
    qualification,
):
    case_by_id(
        qualification,
        "T7-E-REG-01",
    )[
        "historical_unseen"
    ] = True


def mutate_set_e_source_hash(
    qualification,
):
    key = (
        "docs/decisions/qualification/evidence/"
        "0008-red-team-set-e-first-run.txt"
    )

    qualification[
        "source_hashes"
    ][
        key
    ] = "0" * 64


MUTATIONS = (
    (
        "declared qualification case count drift",
        mutate_declared_count,
    ),
    (
        "suite count drift",
        mutate_suite_count,
    ),
    (
        "expectation count drift",
        mutate_expectation_count,
    ),
    (
        "first-run summary drift",
        mutate_first_summary,
    ),
    (
        "current summary drift",
        mutate_current_summary,
    ),
    (
        "qualification case order drift",
        mutate_case_order,
    ),
    (
        "stable qualification case ID drift",
        mutate_case_id,
    ),
    (
        "P1 first false-positive history rewritten",
        mutate_p1_original_failure,
    ),
    (
        "P1 second false-positive history rewritten",
        mutate_p1_second_failure,
    ),
    (
        "Set D false-negative history rewritten",
        mutate_set_d_false_negative,
    ),
    (
        "Set D false-positive history rewritten",
        mutate_set_d_false_positive,
    ),
    (
        "Set D expected disposition rewritten",
        mutate_set_d_expectation,
    ),
    (
        "historical unseen provenance drift",
        mutate_historical_unseen,
    ),
    (
        "current regression disposition drift",
        mutate_current_disposition,
    ),
    (
        "definition reference drift",
        mutate_definition_ref,
    ),
    (
        "first-run evidence reference drift",
        mutate_first_evidence_ref,
    ),
    (
        "current evidence reference drift",
        mutate_current_evidence_ref,
    ),
    (
        "authoritative source hash drift",
        mutate_source_hash,
    ),
    (
        "Set E false-negative first-run history rewritten",
        mutate_set_e_false_negative_history,
    ),
    (
        "Set E false-positive first-run history rewritten",
        mutate_set_e_false_positive_history,
    ),
    (
        "Set E unseen provenance rewritten",
        mutate_set_e_unseen_provenance,
    ),
    (
        "Set E current regression disposition rewritten",
        mutate_set_e_current_disposition,
    ),
    (
        "Set E regression evidence reference drift",
        mutate_set_e_current_evidence_ref,
    ),
    (
        "known-regression first-run provenance rewritten",
        mutate_known_regression_first_provenance,
    ),
    (
        "known-regression incorrectly promoted to unseen",
        mutate_known_regression_unseen_provenance,
    ),
    (
        "Set E first-run source hash drift",
        mutate_set_e_source_hash,
    ),
)


def main() -> int:
    baseline = validator.load_json(
        validator.QUALIFICATION
    )

    schema = validator.load_json(
        validator.QUALIFICATION_SCHEMA
    )

    validator.Draft202012Validator(
        schema
    ).validate(
        baseline
    )

    validator.validate_qualification_semantics(
        baseline
    )

    print(
        "===== QUALIFICATION DATA POSITIVE CONTROL ====="
    )

    print(
        "PASS qualification data positive control"
    )

    schema_mutations = MUTATIONS[:5]
    semantic_mutations = MUTATIONS[5:]

    assert len(
        schema_mutations
    ) == 5

    assert len(
        semantic_mutations
    ) == 21

    print()
    print(
        "===== SCHEMA ENFORCEMENT MUTATIONS ====="
    )

    schema_killed = 0

    for label, mutate in schema_mutations:
        mutant = deepcopy(
            baseline
        )

        mutate(
            mutant
        )

        try:
            validator.Draft202012Validator(
                schema
            ).validate(
                mutant
            )
        except ValidationError:
            schema_killed += 1

            print(
                f"PASS schema mutation killed: {label}"
            )

            continue

        print(
            f"FAIL schema mutation survived: {label}"
        )

    print()
    print(
        "===== SCHEMA-VALID SEMANTIC MUTATIONS ====="
    )

    semantic_killed = 0

    for label, mutate in semantic_mutations:
        mutant = deepcopy(
            baseline
        )

        mutate(
            mutant
        )

        try:
            validator.Draft202012Validator(
                schema
            ).validate(
                mutant
            )
        except ValidationError as exc:
            raise AssertionError(
                "semantic mutation was expected to remain "
                f"schema-valid: {label}"
            ) from exc

        try:
            validator.validate_qualification_semantics(
                mutant
            )
        except AssertionError:
            semantic_killed += 1

            print(
                f"PASS semantic mutation killed: {label}"
            )

            continue

        print(
            f"FAIL semantic mutation survived: {label}"
        )

    total_killed = (
        schema_killed
        + semantic_killed
    )

    total_mutations = len(
        MUTATIONS
    )

    print()
    print(
        "===== QUALIFICATION DATA MUTATION RESULT ====="
    )

    print(
        f"Schema killed: "
        f"{schema_killed}/{len(schema_mutations)}"
    )

    print(
        f"Semantic killed: "
        f"{semantic_killed}/{len(semantic_mutations)}"
    )

    print(
        f"Total killed: "
        f"{total_killed}/{total_mutations}"
    )

    print(
        f"Survived: "
        f"{total_mutations - total_killed}/{total_mutations}"
    )

    if (
        schema_killed
        != len(
            schema_mutations
        )
    ):
        raise AssertionError(
            "Task 7 qualification evidence "
            "schema mutations survived"
        )

    if (
        semantic_killed
        != len(
            semantic_mutations
        )
    ):
        raise AssertionError(
            "Task 7 qualification evidence "
            "semantic mutations survived"
        )

    print(
        "TASK 7 QUALIFICATION DATA MUTATIONS: "
        f"PASS ({total_killed}/{total_mutations} killed; "
        f"schema={schema_killed}, "
        f"semantic={semantic_killed})"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
