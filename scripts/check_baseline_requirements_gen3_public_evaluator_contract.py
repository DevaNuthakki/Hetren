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

CONTRACT_FILE = (
    DATA_DIR
    / "public_evaluator_contract.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
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

ATTEMPT1_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_attempt_1.json"
)

ATTEMPT1_DISPOSITION = (
    DATA_DIR
    / "fresh_holdout_generation_attempt_1_disposition.json"
)


EXPECTED_CONTRACT_SHA = (
    "70a61f7ee6a3f3f95614ad1ebacf3479"
    "8377062b3f1cd8a30a0c1246ffc4250c"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)

EXPECTED_GEN3_SHA = (
    "d01e39439d601fd28ed1b15cdb618214"
    "a0e5d84b2f88c142dd020dbf80930217"
)

EXPECTED_PREREG_SHA = (
    "4b62eb6feb6b2085cb8a90b2153e4544"
    "9749ca520da277782a9a6bdcac35f037"
)

EXPECTED_ATTEMPT1_SHA = (
    "c80f5ace7bfeb7ee264084672b9dc693"
    "945d46ba2644e917d3c6f2ec7de53684"
)


def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk_keys(item)

    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


def main():
    assert sha256(
        CONTRACT_FILE
    ) == EXPECTED_CONTRACT_SHA

    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA

    assert sha256(
        GEN3_FILE
    ) == EXPECTED_GEN3_SHA

    assert sha256(
        PREREG_FILE
    ) == EXPECTED_PREREG_SHA

    assert sha256(
        ATTEMPT1_FILE
    ) == EXPECTED_ATTEMPT1_SHA


    contract = json.loads(
        CONTRACT_FILE.read_text()
    )

    disposition = json.loads(
        ATTEMPT1_DISPOSITION.read_text()
    )


    assert contract[
        "artifact_type"
    ] == "TASK_8_GEN3_PUBLIC_EVALUATOR_CONTRACT"

    assert contract[
        "state"
    ] == "FROZEN_BEFORE_ATTEMPT_2"

    assert contract[
        "source_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA

    assert contract[
        "generation_attempt_2_started"
    ] is False

    assert contract[
        "fresh_holdout_executed"
    ] is False

    assert contract[
        "evaluator_executed"
    ] is False

    assert contract[
        "authoritative"
    ] is False

    assert contract[
        "scientific_support_established"
    ] is False


    protocol = contract[
        "evaluate_protocol"
    ]

    assert protocol[
        "positional_arguments"
    ] == [
        "primary_requirement",
        "facts",
        "environment",
    ]

    assert protocol[
        "environment_values"
    ] == [
        "CROSS_ENV",
        "E1",
        "E2",
        "E3",
    ]

    assert protocol[
        "decision_values"
    ] == [
        "ACCEPT",
        "REJECT",
    ]

    assert protocol[
        "global_input_error_codes"
    ] == [
        "MISSING_FACTS",
        "UNKNOWN_ENVIRONMENT",
        "UNKNOWN_REQUIREMENT",
    ]

    assert protocol[
        "primary_requirement_values"
    ] == [
        f"G3-BR-{number:03d}"
        for number in range(1, 28)
    ]


    closed_enums = contract[
        "fact_semantics"
    ][
        "closed_enums"
    ]

    assert closed_enums[
        "environment"
    ] == [
        "CROSS_ENV",
        "E1",
        "E2",
        "E3",
    ]

    assert closed_enums[
        "reproducibility_class"
    ] == [
        "BEHAVIORAL_REPLAY",
        "CONTROLLED_RECONSTRUCTION",
        "EXACT_RECONSTRUCTION",
        "IRREPRODUCIBLE_EXTERNAL_DEPENDENCY",
    ]

    assert closed_enums[
        "applicability_state"
    ] == [
        "APPLICABLE",
        "NOT_APPLICABLE",
    ]


    requirements = contract[
        "requirements"
    ]

    expected_requirements = [
        f"G3-BR-{number:03d}"
        for number in range(1, 28)
    ]

    assert list(
        requirements
    ) == expected_requirements


    all_fact_keys = set()
    all_violation_codes = set()


    for requirement in expected_requirements:
        item = requirements[
            requirement
        ]

        facts = set(
            item[
                "fact_keys"
            ]
        )

        boolean_facts = set(
            item[
                "boolean_fact_keys"
            ]
        )

        non_boolean_facts = set(
            item[
                "non_boolean_fact_keys"
            ]
        )

        defaults = item[
            "effective_boolean_defaults"
        ]

        violations = set(
            item[
                "violation_codes"
            ]
        )


        assert facts

        assert boolean_facts.issubset(
            facts
        )

        assert non_boolean_facts.issubset(
            facts
        )

        assert not (
            boolean_facts
            & non_boolean_facts
        )

        assert (
            boolean_facts
            | non_boolean_facts
        ) == facts

        assert set(
            defaults
        ) == boolean_facts

        assert all(
            isinstance(value, bool)
            for value in defaults.values()
        )

        assert violations


        dynamic_real_world_codes = {
            "REAL_WORLD_SCOPE_MISSING:"
            "population_scope_declared",

            "REAL_WORLD_SCOPE_MISSING:"
            "sampling_method_declared",

            "REAL_WORLD_SCOPE_MISSING:"
            "deployment_scope_declared",

            "REAL_WORLD_SCOPE_MISSING:"
            "time_window_declared",
        }


        for code in violations:
            standard_code = re.fullmatch(
                r"[A-Z0-9_:.-]+",
                code,
            )

            dynamic_real_world_code = (
                code
                in dynamic_real_world_codes
            )

            assert (
                standard_code
                or dynamic_real_world_code
            ), (
                requirement,
                code,
            )


        all_fact_keys.update(
            facts
        )

        all_violation_codes.update(
            violations
        )


    totals = contract[
        "interface_totals"
    ]

    assert totals[
        "direct_fact_keys"
    ] == 108

    assert totals[
        "complete_fact_keys"
    ] == 115

    assert totals[
        "direct_violation_codes"
    ] == 72

    assert totals[
        "complete_violation_codes"
    ] == 79

    assert len(
        all_fact_keys
    ) == 115

    assert len(
        all_violation_codes
    ) == 79


    expected_dynamic_facts = {
        "deployment_scope_declared",
        "evaluator_identity_present",
        "evaluator_scoring_procedure_present",
        "evaluator_version_present",
        "population_scope_declared",
        "sampling_method_declared",
        "time_window_declared",
    }

    assert set(
        totals[
            "dynamic_only_fact_keys"
        ]
    ) == expected_dynamic_facts


    expected_dynamic_codes = {
        "EVALUATOR_IDENTITY_MISSING",
        "EVALUATOR_SCORING_PROCEDURE_MISSING",
        "EVALUATOR_VERSION_MISSING",
        "REAL_WORLD_SCOPE_MISSING:"
        "deployment_scope_declared",
        "REAL_WORLD_SCOPE_MISSING:"
        "population_scope_declared",
        "REAL_WORLD_SCOPE_MISSING:"
        "sampling_method_declared",
        "REAL_WORLD_SCOPE_MISSING:"
        "time_window_declared",
    }

    assert set(
        totals[
            "dynamic_only_violation_codes"
        ]
    ) == expected_dynamic_codes


    scoring = contract[
        "scoring_contract"
    ]

    assert scoring[
        "calls_per_case"
    ] == 1

    assert scoring[
        "call_protocol"
    ] == (
        "evaluate(primary_requirement, facts, environment)"
    )

    assert scoring[
        "secondary_requirements"
    ] == (
        "SEMANTIC_CONTEXT_ONLY_NO_ADDITIONAL_EVALUATOR_CALLS"
    )

    assert scoring[
        "must_accept_rule"
    ][
        "required_decision"
    ] == "ACCEPT"

    assert scoring[
        "must_accept_rule"
    ][
        "required_violations"
    ] == []

    assert scoring[
        "must_reject_rule"
    ][
        "required_decision"
    ] == "REJECT"

    assert scoring[
        "must_reject_rule"
    ][
        "required_violation_relation"
    ] == (
        "EXPECTED_CODES_SUBSET_OF_ACTUAL_CODES"
    )

    assert scoring[
        "must_reject_rule"
    ][
        "additional_actual_codes_allowed"
    ] is True

    assert scoring[
        "expectation_passed_to_evaluator"
    ] is False

    assert scoring[
        "expected_violation_codes_passed_to_evaluator"
    ] is False

    assert scoring[
        "all_predictions_before_scoring"
    ] is True


    rules = contract[
        "attempt_2_generation_rules"
    ]

    assert all(
        rules.values()
    )


    scope = contract[
        "contract_scope"
    ]

    assert scope[
        "implementation_logic_exposed"
    ] is False

    assert scope[
        "source_code_exposed"
    ] is False

    assert scope[
        "branch_conditions_exposed"
    ] is False

    assert scope[
        "allowed_for_case_generation"
    ] is True

    assert scope[
        "does_not_replace_generation_3_semantics"
    ] is True


    #
    # Verify that raw implementation-source structures were
    # not accidentally embedded in the public contract.
    #
    forbidden_keys = {
        "helper_sources",
        "source_code",
        "evaluator_source",
        "implementation_source",
        "branch_conditions",
        "raw_ast",
        "ast_dump",
    }

    present_keys = set(
        walk_keys(
            contract
        )
    )

    assert not (
        forbidden_keys
        & present_keys
    )


    contract_text = CONTRACT_FILE.read_text()

    evaluator_source = EVALUATOR_FILE.read_text()

    assert evaluator_source not in contract_text

    assert "def evaluate(" not in contract_text
    assert "def _flag(" not in contract_text
    assert "def _add(" not in contract_text
    assert "elif primary_requirement" not in contract_text


    #
    # Attempt 1 remains historical and unexecuted.
    #
    assert disposition[
        "target_evaluator_executed"
    ] is False

    assert disposition[
        "target_predictions_produced"
    ] is False


    print(
        "PASS: exact frozen public evaluator contract"
    )

    print(
        "Complete fact keys:",
        len(all_fact_keys),
    )

    print(
        "Complete violation codes:",
        len(all_violation_codes),
    )

    print(
        "Requirement interfaces:",
        len(requirements),
    )

    print(
        "Raw evaluator source embedded: NO"
    )

    print(
        "Branch implementation embedded: NO"
    )

    print(
        "Attempt 1 executed: NO"
    )


if __name__ == "__main__":
    main()
