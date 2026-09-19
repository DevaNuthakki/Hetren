from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[2]

VALIDATOR = (
    ROOT
    / "scripts"
    / "check_initial_splits_data.py"
)


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "task7_data_validator_under_test",
        VALIDATOR,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


validator = load_validator()


def case_by_suite(
    historical,
    suite,
    ordinal,
):
    matches = [
        item
        for item in historical["cases"]
        if (
            item["suite"] == suite
            and item["ordinal"] == ordinal
        )
    ]

    assert len(matches) == 1

    return matches[0]


def generated_case(
    historical,
    generated_case_id,
):
    matches = [
        item
        for item in historical["cases"]
        if (
            item.get("generated_case_id")
            == generated_case_id
        )
    ]

    assert len(matches) == 1

    return matches[0]


def mutate_declared_case_count(
    historical,
    invariants,
):
    historical[
        "historical_case_count"
    ] = 139


def mutate_canonical_order(
    historical,
    invariants,
):
    historical["cases"][0], historical["cases"][1] = (
        historical["cases"][1],
        historical["cases"][0],
    )


def mutate_canonical_ordinal(
    historical,
    invariants,
):
    case_by_suite(
        historical,
        "CANONICAL",
        1,
    )["ordinal"] = 2


def mutate_canonical_case_id(
    historical,
    invariants,
):
    case_by_suite(
        historical,
        "CANONICAL",
        1,
    )["case_id"] = "T7-DEV-999"


def mutate_set_c_identity_history(
    historical,
    invariants,
):
    survivor = generated_case(
        historical,
        "C01.01",
    )

    rejected = generated_case(
        historical,
        "C01.02",
    )

    assert (
        survivor["first_run_disposition"]
        == "SURVIVED"
    )

    assert (
        rejected["first_run_disposition"]
        == "REJECTED"
    )

    survivor[
        "first_run_disposition"
    ] = "REJECTED"

    rejected[
        "first_run_disposition"
    ] = "SURVIVED"


def mutate_set_c_generated_identity(
    historical,
    invariants,
):
    first = generated_case(
        historical,
        "C01.01",
    )

    second = generated_case(
        historical,
        "C01.02",
    )

    first["generated_case_id"], second["generated_case_id"] = (
        second["generated_case_id"],
        first["generated_case_id"],
    )


def mutate_source_hash(
    historical,
    invariants,
):
    historical[
        "sources"
    ][
        "canonical"
    ][
        "historical_file_sha256"
    ] = "0" * 64


def mutate_canonical_snapshot_ref(
    historical,
    invariants,
):
    historical[
        "sources"
    ][
        "canonical"
    ][
        "historical_snapshot_ref"
    ] = (
        "docs/decisions/qualification/evidence/"
        "0008-post-remediation-boundary.sha256"
    )


def mutate_canonical_attack_hash(
    historical,
    invariants,
):
    historical[
        "sources"
    ][
        "canonical"
    ][
        "attack_definition_sha256"
    ] = "2" * 64


def mutate_attack_hash(
    historical,
    invariants,
):
    historical[
        "sources"
    ][
        "set_b"
    ][
        "attack_definition_sha256"
    ] = "1" * 64


def mutate_invariant_count(
    historical,
    invariants,
):
    invariants[
        "invariant_count"
    ] = 43


def mutate_invariant_source_line(
    historical,
    invariants,
):
    invariants[
        "invariants"
    ][0][
        "source_line"
    ] += 1


def mutate_semantic_helper_identity(
    historical,
    invariants,
):
    item = next(
        item
        for item in invariants["invariants"]
        if (
            item["enforcement_kind"]
            == "SEMANTIC_HELPER"
            and item["helper"]
            == "forbid_permissive_relationship"
        )
    )

    item[
        "helper"
    ] = "forbid_semantic_patterns"


def mutate_invariant_order(
    historical,
    invariants,
):
    entries = invariants[
        "invariants"
    ]

    entries[0], entries[1] = (
        entries[1],
        entries[0],
    )


MUTATIONS = (
    (
        "declared historical case count drift",
        mutate_declared_case_count,
    ),
    (
        "canonical evidence order drift",
        mutate_canonical_order,
    ),
    (
        "canonical ordinal identity drift",
        mutate_canonical_ordinal,
    ),
    (
        "canonical stable case ID drift",
        mutate_canonical_case_id,
    ),
    (
        "Set C swaps original rejected identity while preserving 17/47",
        mutate_set_c_identity_history,
    ),
    (
        "Set C generated identity order drift",
        mutate_set_c_generated_identity,
    ),
    (
        "canonical historical snapshot hash drift",
        mutate_source_hash,
    ),
    (
        "canonical historical snapshot reference drift",
        mutate_canonical_snapshot_ref,
    ),
    (
        "canonical development attack-definition hash drift",
        mutate_canonical_attack_hash,
    ),
    (
        "Set B attack-definition hash drift",
        mutate_attack_hash,
    ),
    (
        "declared invariant count drift",
        mutate_invariant_count,
    ),
    (
        "invariant source-line drift",
        mutate_invariant_source_line,
    ),
    (
        "semantic helper identity drift",
        mutate_semantic_helper_identity,
    ),
    (
        "invariant registry order drift",
        mutate_invariant_order,
    ),
)


def positive_control():
    validator.validate_all()

    print(
        "PASS data semantic positive control"
    )


def run_mutations():
    baseline_historical = validator.load_json(
        validator.HISTORICAL
    )

    baseline_invariants = validator.load_json(
        validator.INVARIANTS
    )

    killed = 0
    survivors = []

    for label, mutate in MUTATIONS:
        historical = deepcopy(
            baseline_historical
        )

        invariants = deepcopy(
            baseline_invariants
        )

        mutate(
            historical,
            invariants,
        )

        # Every attack in this suite must remain valid under
        # the structural JSON schemas. Otherwise this is not
        # testing the semantic layer.
        try:
            validator.validate_schemas(
                historical,
                invariants,
            )
        except Exception as exc:
            raise AssertionError(
                f"mutation is not schema-valid: {label}"
            ) from exc

        try:
            validator.validate_historical_semantics(
                historical
            )

            validator.validate_invariant_semantics(
                invariants
            )

        except AssertionError:
            killed += 1

            print(
                f"PASS semantic mutation killed: {label}"
            )

            continue

        survivors.append(
            label
        )

        print(
            f"FAIL semantic mutation survived: {label}"
        )

    print()
    print("===== DATA SEMANTIC MUTATION RESULT =====")
    print(
        f"Killed: {killed}/{len(MUTATIONS)}"
    )
    print(
        f"Survived: {len(survivors)}/{len(MUTATIONS)}"
    )

    assert not survivors, (
        "Task 7 data semantic validator has survivors: "
        + ", ".join(survivors)
    )

    assert killed == len(
        MUTATIONS
    )

    print(
        "TASK 7 DATA SEMANTIC MUTATIONS: "
        f"PASS ({killed}/{len(MUTATIONS)} killed)"
    )


def main():
    print(
        "===== DATA SEMANTIC POSITIVE CONTROL ====="
    )

    positive_control()

    print()
    print(
        "===== SCHEMA-VALID SEMANTIC MUTATIONS ====="
    )

    run_mutations()


if __name__ == "__main__":
    main()
