#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import re


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
    / "fresh_holdout_generation_package_v2.json"
)

GEN3_FILE = (
    ROOT
    / "docs"
    / "research"
    / "baselines"
    / "task-08-baseline-requirements-gen3.json"
)

PREREG_FILE = (
    DATA_DIR
    / "fresh_holdout_contract.json"
)

PUBLIC_CONTRACT_FILE = (
    DATA_DIR
    / "public_evaluator_contract.json"
)

PUBLIC_MANIFEST_FILE = (
    DATA_DIR
    / "public_evaluator_contract_manifest.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)


EXPECTED_PACKAGE_SHA = (
    "ac273519cea881f75ea89ab9efa7eeba"
    "c7eb2bf5a10a250a5d261c0e22e1074c"
)

EXPECTED_GEN3_SHA = (
    "d01e39439d601fd28ed1b15cdb618214"
    "a0e5d84b2f88c142dd020dbf80930217"
)

EXPECTED_PREREG_SHA = (
    "4b62eb6feb6b2085cb8a90b2153e4544"
    "9749ca520da277782a9a6bdcac35f037"
)

EXPECTED_PUBLIC_CONTRACT_SHA = (
    "70a61f7ee6a3f3f95614ad1ebacf3479"
    "8377062b3f1cd8a30a0c1246ffc4250c"
)

EXPECTED_PUBLIC_MANIFEST_SHA = (
    "08ee63f8e2f277f52d7a6d44106b2ff"
    "58d806d3ea317aab9cf7d8b78052c684e"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)

ALLOWED_D1_PROVENANCE_SHA = (
    "da22d819a6cbfab8c5c076f80e207951"
    "2463b16d7b127b0b8d7e602a48d7d3ba"
)

ALLOWED_D1_PROVENANCE_PATH = (
    "$.embedded_preregistration_contract."
    "frozen_inputs.successful_regression_sha256"
)


def sha256(target_file):
    return hashlib.sha256(
        target_file.read_bytes()
    ).hexdigest()


def walk_entries(value, path="$"):
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"

            yield {
                "path": child,
                "kind": "KEY",
                "value": key,
            }

            yield from walk_entries(
                item,
                child,
            )

    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_entries(
                item,
                f"{path}[{index}]",
            )

    elif isinstance(value, str):
        yield {
            "path": path,
            "kind": "VALUE",
            "value": value,
        }


def main():
    #
    # Frozen external identities.
    #
    assert sha256(
        PACKAGE_FILE
    ) == EXPECTED_PACKAGE_SHA

    assert sha256(
        GEN3_FILE
    ) == EXPECTED_GEN3_SHA

    assert sha256(
        PREREG_FILE
    ) == EXPECTED_PREREG_SHA

    assert sha256(
        PUBLIC_CONTRACT_FILE
    ) == EXPECTED_PUBLIC_CONTRACT_SHA

    assert sha256(
        PUBLIC_MANIFEST_FILE
    ) == EXPECTED_PUBLIC_MANIFEST_SHA

    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA


    package = json.loads(
        PACKAGE_FILE.read_text()
    )

    gen3 = json.loads(
        GEN3_FILE.read_text()
    )

    prereg = json.loads(
        PREREG_FILE.read_text()
    )

    public_contract = json.loads(
        PUBLIC_CONTRACT_FILE.read_text()
    )


    #
    # Package lifecycle.
    #
    assert package[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ISOLATED_FRESH_HOLDOUT_GENERATION_PACKAGE_V2"
    )

    assert package[
        "state"
    ] == (
        "READY_FOR_ISOLATED_GENERATION_ATTEMPT_2"
    )

    assert package[
        "generation_attempt"
    ] == 2

    assert package[
        "contains_holdout_cases"
    ] is False

    assert package[
        "attempt_2_cases_generated"
    ] is False

    assert package[
        "target_evaluator_executed"
    ] is False

    assert package[
        "fresh_holdout_generation"
    ] is True

    assert package[
        "protected_evaluation"
    ] is True

    assert package[
        "authoritative"
    ] is False

    assert package[
        "scientific_support_established"
    ] is False


    #
    # Exact source bindings.
    #
    bindings = package[
        "source_bindings"
    ]

    assert bindings[
        "generation_3_sha256"
    ] == EXPECTED_GEN3_SHA

    assert bindings[
        "preregistration_contract_sha256"
    ] == EXPECTED_PREREG_SHA

    assert bindings[
        "public_evaluator_contract_sha256"
    ] == EXPECTED_PUBLIC_CONTRACT_SHA

    assert bindings[
        "public_evaluator_contract_manifest_sha256"
    ] == EXPECTED_PUBLIC_MANIFEST_SHA

    assert bindings[
        "frozen_target_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA


    #
    # Embedded objects must equal frozen source objects.
    #
    assert package[
        "embedded_generation_3_requirements"
    ] == gen3

    assert package[
        "embedded_preregistration_contract"
    ] == prereg

    assert package[
        "embedded_public_evaluator_contract"
    ] == public_contract


    embedded_keys = {
        key
        for key in package
        if key.startswith(
            "embedded_"
        )
    }

    assert embedded_keys == {
        "embedded_generation_3_requirements",
        "embedded_preregistration_contract",
        "embedded_public_evaluator_contract",
    }


    #
    # Operationalized holdout design.
    #
    design = package[
        "operationalized_design"
    ]

    assert design[
        "case_count"
    ] == 54

    assert design[
        "primary_requirement_count"
    ] == 27

    assert design[
        "cases_per_primary_requirement"
    ] == 2

    assert design[
        "per_requirement_expectation_pattern"
    ] == {
        "MUST_ACCEPT": 1,
        "MUST_REJECT": 1,
    }

    assert design[
        "total_must_accept"
    ] == 27

    assert design[
        "total_must_reject"
    ] == 27

    assert design[
        "case_ids"
    ] == [
        f"G3-H2-{number:03d}"
        for number in range(
            1,
            55,
        )
    ]

    assert set(
        design[
            "environment_values"
        ]
    ) == {
        "E1",
        "E2",
        "E3",
        "CROSS_ENV",
    }

    assert design[
        "minimum_cases_per_environment"
    ] == 6

    assert design[
        "minimum_cross_requirement_interaction_cases"
    ] == 12

    for key in [
        "all_cases_generated_before_target_execution",
        "case_order_frozen_before_target_execution",
        "expectations_frozen_before_target_execution",
        "facts_frozen_before_target_execution",
        "expected_violation_codes_frozen_before_target_execution",
    ]:
        assert design[key] is True


    #
    # Executable scoring boundary.
    #
    executable = package[
        "executable_case_contract"
    ]

    assert executable[
        "evaluator_call_count_per_case"
    ] == 1

    assert executable[
        "call_protocol"
    ] == (
        "evaluate(primary_requirement, facts, environment)"
    )

    assert "do not trigger" in executable[
        "secondary_requirements"
    ].lower()

    assert executable[
        "expectation_is_not_evaluator_input"
    ] is True

    assert executable[
        "expected_violation_codes_are_not_evaluator_input"
    ] is True

    assert executable[
        "all_predictions_before_scoring"
    ] is True

    assert executable[
        "must_accept_rule"
    ][
        "expected_violation_codes"
    ] == []

    assert executable[
        "must_reject_rule"
    ][
        "future_scoring_relation"
    ] == (
        "EXPECTED_CODES_SUBSET_OF_ACTUAL_CODES"
    )

    assert executable[
        "must_reject_rule"
    ][
        "additional_actual_codes_allowed"
    ] is True


    #
    # Public interface must remain the frozen 115/79 boundary.
    #
    interface = package[
        "embedded_public_evaluator_contract"
    ]

    assert interface[
        "interface_totals"
    ][
        "complete_fact_keys"
    ] == 115

    assert interface[
        "interface_totals"
    ][
        "complete_violation_codes"
    ] == 79

    assert len(
        interface[
            "requirements"
        ]
    ) == 27


    #
    # Generator isolation.
    #
    assert all(
        package[
            "required_generator_attestations"
        ].values()
    )

    assert all(
        package[
            "claim_limits"
        ].values()
    )


    #
    # Path-aware historical-provenance check.
    #
    entries = list(
        walk_entries(
            package
        )
    )

    allowed_hits = [
        item
        for item in entries
        if (
            item["kind"] == "VALUE"
            and item["value"]
            == ALLOWED_D1_PROVENANCE_SHA
        )
    ]

    assert allowed_hits == [
        {
            "path":
                ALLOWED_D1_PROVENANCE_PATH,

            "kind":
                "VALUE",

            "value":
                ALLOWED_D1_PROVENANCE_SHA,
        }
    ]

    assert prereg[
        "frozen_inputs"
    ][
        "successful_regression_sha256"
    ] == ALLOWED_D1_PROVENANCE_SHA


    forbidden_exact_values = {
        (
            "775fc3249e6b20e4a27787396e3fec492"
            "f126ada173e40fe26c7d14a6dfe88f5"
        ),
        (
            "c80f5ace7bfeb7ee264084672b9dc693"
            "945d46ba2644e917d3c6f2ec7de53684"
        ),
    }

    forbidden_substrings = [
        "G3-M-001",
        "G3-M-011",
        "G3-M-018",
        "G3-M-020",
        "G3-M-022",
        "G3-M-024",
        "G3-M-028",
        "G3-M-029",
        "G3-M-030",
        "G3-M-031",
        "G3-M-034",
        "semantic_wall_first_run.json",
        "mutation_wall_first_run.json",
        "semantic_evaluator_first_mutation_run.py",
        "mutation_wall_first_run_classification",
        "remediation_regression_result.json",
    ]


    unexpected = []

    for item in entries:
        value = str(
            item["value"]
        )

        if (
            item["kind"] == "VALUE"
            and value
            in forbidden_exact_values
        ):
            unexpected.append(
                item
            )

        for token in forbidden_substrings:
            if token in value:
                unexpected.append(
                    {
                        **item,
                        "matched":
                            token,
                    }
                )


    assert not unexpected, unexpected


    #
    # No raw target implementation.
    #
    package_text = PACKAGE_FILE.read_text()

    forbidden_source_fragments = [
        "def evaluate(",
        "def _flag(",
        "def _add(",
        "elif primary_requirement ==",
        "violations.append(",
    ]

    for fragment in forbidden_source_fragments:
        assert fragment not in package_text


    forbidden_structure_keys = {
        "helper_sources",
        "evaluator_source",
        "implementation_source",
        "source_code",
        "branch_conditions",
        "raw_ast",
        "ast_dump",
        "python_source",
    }

    present_keys = {
        item["value"]
        for item in entries
        if item["kind"] == "KEY"
    }

    assert not (
        forbidden_structure_keys
        & present_keys
    )


    #
    # Output contract remains generation-only.
    #
    expected_output = package[
        "expected_output"
    ]

    assert expected_output[
        "filename"
    ] == "fresh_holdout_cases_attempt_2.json"

    assert expected_output[
        "state"
    ] == "GENERATED_NOT_EXECUTED"

    assert expected_output[
        "generation_attempt"
    ] == 2

    assert expected_output[
        "fresh_holdout"
    ] is True

    assert expected_output[
        "protected_evaluation"
    ] is True

    assert expected_output[
        "authoritative"
    ] is False

    assert expected_output[
        "scientific_support_established"
    ] is False


    print(
        "PASS: exact Generation Package v2"
    )

    print(
        "Embedded semantic sources: 3"
    )

    print(
        "Required cases:",
        design["case_count"],
    )

    print(
        "MUST_ACCEPT:",
        design["total_must_accept"],
    )

    print(
        "MUST_REJECT:",
        design["total_must_reject"],
    )

    print(
        "Public fact keys:",
        interface[
            "interface_totals"
        ][
            "complete_fact_keys"
        ],
    )

    print(
        "Public violation codes:",
        interface[
            "interface_totals"
        ][
            "complete_violation_codes"
        ],
    )

    print(
        "Raw target implementation embedded: NO"
    )

    print(
        "Prior qualification evidence embedded: NO"
    )

    print(
        "Allowed inherited D1 provenance binding: YES"
    )

    print(
        "Target evaluator executed: NO"
    )


if __name__ == "__main__":
    main()
