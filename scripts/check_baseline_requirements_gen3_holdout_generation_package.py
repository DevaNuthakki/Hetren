#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "baseline_requirements_gen3"
)

PACKAGE_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package.json"
)

GEN3_FILE = (
    ROOT
    / "docs"
    / "research"
    / "baselines"
    / "task-08-baseline-requirements-gen3.json"
)

CONTRACT_FILE = (
    DATA_DIR
    / "fresh_holdout_contract.json"
)


def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def main():
    package = json.loads(
        PACKAGE_FILE.read_text()
    )

    gen3 = json.loads(
        GEN3_FILE.read_text()
    )

    contract = json.loads(
        CONTRACT_FILE.read_text()
    )

    assert package["state"] == \
        "READY_FOR_ISOLATED_GENERATION"

    assert package[
        "contains_holdout_cases"
    ] is False

    assert package[
        "fresh_holdout_generation"
    ] is True

    assert package[
        "protected_evaluation"
    ] is True

    assert package["authoritative"] is False

    assert package[
        "scientific_support_established"
    ] is False

    assert package[
        "source_bindings"
    ][
        "generation_3_sha256"
    ] == sha256(GEN3_FILE)

    assert package[
        "source_bindings"
    ][
        "preregistration_contract_sha256"
    ] == sha256(CONTRACT_FILE)

    assert package[
        "embedded_generation_3_requirements"
    ] == gen3

    assert package[
        "embedded_preregistration_contract"
    ] == contract

    design = package[
        "operationalized_design"
    ]

    assert design["case_count"] == 54
    assert design["requirements"] == 27

    assert design[
        "cases_per_primary_requirement"
    ] == 2

    assert design[
        "total_must_accept"
    ] == 27

    assert design[
        "total_must_reject"
    ] == 27

    assert design[
        "minimum_cross_requirement_interaction_cases"
    ] == 12

    assert design[
        "minimum_cases_per_environment"
    ] == 6

    assert set(
        design["required_environment_values"]
    ) == {
        "E1",
        "E2",
        "E3",
        "CROSS_ENV",
    }

    attestations = package[
        "required_generator_attestations"
    ]

    assert all(
        attestations.values()
    )

    expected_output = package[
        "expected_output"
    ]

    assert expected_output[
        "filename"
    ] == "fresh_holdout_cases.json"

    assert expected_output[
        "state"
    ] == "GENERATED_NOT_EXECUTED"

    assert expected_output[
        "fresh_holdout"
    ] is True

    #
    # Critical package-isolation check:
    # only the two explicitly allowed embedded Hetren
    # semantic inputs may be present.
    #
    forbidden_embedded_keys = {
        "semantic_evaluator_source",
        "known_development_cases",
        "known_mutations",
        "historical_predictions",
        "historical_results",
        "remediation_history",
        "mutation_classification",
    }

    assert not (
        forbidden_embedded_keys
        & set(package)
    )

    #
    # Fresh case artifacts must still not exist.
    #
    forbidden_live_artifacts = [
        DATA_DIR / "fresh_holdout_cases.json",
        DATA_DIR / "fresh_holdout_freeze_manifest.json",
        DATA_DIR / "fresh_holdout_first_run.json",
    ]

    assert not any(
        path.exists()
        for path in forbidden_live_artifacts
    )

    print(
        "PASS: isolated fresh-holdout "
        "generation package"
    )

    print(
        "Embedded semantic inputs:",
        [
            "Generation 3 requirements",
            "D1 preregistration contract",
        ],
    )

    print("Holdout cases present: NO")
    print("Evaluator source embedded: NO")
    print("Known development answers embedded: NO")
    print("Known mutation answers embedded: NO")
    print("Fresh execution performed: NO")


if __name__ == "__main__":
    main()
