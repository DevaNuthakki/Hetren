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

V5_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v5.json"
)

V6_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v6.json"
)

ATTEMPT5_FAILURE_FILE = (
    DATA_DIR
    / "generation_isolation_failure_attempt_5.json"
)

ATTEMPT5_DISPOSITION_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_attempt_5_disposition.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)


EXPECTED_V5_SHA = (
    "ff785b10d526ef59269e1311e4ca4364"
    "185cd0041123602f7c6f0c634d468f83"
)

EXPECTED_V6_SHA = (
    "f05eaa07ce5bcbbbef15117b49a3bc82"
    "a8e4c4212a0a086f16cddc56d49d65d8"
)

EXPECTED_ATTEMPT5_FAILURE_SHA = (
    "0a4b4d08dab5bac8d28698359cb635d2"
    "246352bc1ee2942090863e6c850c8964"
)

EXPECTED_ATTEMPT5_DISPOSITION_SHA = (
    "9ea8b7e6383721cfc4187862853fff2e"
    "ba18a4d56cbbd649b38d7bc272926684"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)


FORWARD_REPLACEMENTS = [
    ("generation_package_v5", "generation_package_v6"),
    ("package_v5", "package_v6"),
    ("PACKAGE_V5", "PACKAGE_V6"),
    ("Package v5", "Package v6"),
    ("Generation Package v5", "Generation Package v6"),
    ("attempt_5", "attempt_6"),
    ("ATTEMPT_5", "ATTEMPT_6"),
    ("Attempt 5", "Attempt 6"),
    ("attempt 5", "attempt 6"),
    ("G3-H5", "G3-H6"),
]

REVERSE_REPLACEMENTS = [
    (new, old)
    for old, new in reversed(
        FORWARD_REPLACEMENTS
    )
]


def sha256(target_file):
    return hashlib.sha256(
        target_file.read_bytes()
    ).hexdigest()


def load_json(target_file):
    return json.loads(
        target_file.read_text()
    )


def replace_text(value, replacements):
    for old, new in replacements:
        value = value.replace(
            old,
            new,
        )

    return value


def transform(
    value,
    replacements,
    generation_from,
    generation_to,
):
    if isinstance(value, dict):
        result = {}

        for key, item in value.items():
            new_key = replace_text(
                key,
                replacements,
            )

            if (
                new_key == "generation_attempt"
                and item == generation_from
            ):
                new_item = generation_to
            else:
                new_item = transform(
                    item,
                    replacements,
                    generation_from,
                    generation_to,
                )

            result[new_key] = new_item

        return result

    if isinstance(value, list):
        return [
            transform(
                item,
                replacements,
                generation_from,
                generation_to,
            )
            for item in value
        ]

    if isinstance(value, str):
        return replace_text(
            value,
            replacements,
        )

    return value


def main():
    #
    # Exact governed bytes.
    #
    assert sha256(
        V5_FILE
    ) == EXPECTED_V5_SHA

    assert sha256(
        V6_FILE
    ) == EXPECTED_V6_SHA

    assert sha256(
        ATTEMPT5_FAILURE_FILE
    ) == EXPECTED_ATTEMPT5_FAILURE_SHA

    assert sha256(
        ATTEMPT5_DISPOSITION_FILE
    ) == EXPECTED_ATTEMPT5_DISPOSITION_SHA

    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA


    v5 = load_json(
        V5_FILE
    )

    v6 = load_json(
        V6_FILE
    )

    disposition5 = load_json(
        ATTEMPT5_DISPOSITION_FILE
    )


    #
    # Successor identity.
    #
    assert v6[
        "schema_version"
    ] == "6.0.0"

    assert v6[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ISOLATED_FRESH_"
        "HOLDOUT_GENERATION_PACKAGE_V6"
    )

    assert v6[
        "state"
    ] == (
        "READY_FOR_ISOLATED_GENERATION_ATTEMPT_6"
    )

    assert v6[
        "generation_attempt"
    ] == 6

    assert v6[
        "contains_holdout_cases"
    ] is False

    assert v6[
        "attempt_6_cases_generated"
    ] is False

    assert v6[
        "target_evaluator_executed"
    ] is False

    assert v6[
        "fresh_holdout_generation"
    ] is True

    assert v6[
        "protected_evaluation"
    ] is True

    assert v6[
        "authoritative"
    ] is False

    assert v6[
        "scientific_support_established"
    ] is False


    #
    # Independent bounded-successor proof.
    #
    reconstructed_v5 = transform(
        v6,
        REVERSE_REPLACEMENTS,
        6,
        5,
    )

    reconstructed_v5[
        "schema_version"
    ] = "5.0.0"

    assert reconstructed_v5 == v5


    #
    # Top-level difference must only be renamed attempt state.
    #
    v5_keys = set(v5)
    v6_keys = set(v6)

    assert (
        v5_keys
        - v6_keys
    ) == {
        "attempt_5_cases_generated",
    }

    assert (
        v6_keys
        - v5_keys
    ) == {
        "attempt_6_cases_generated",
    }


    #
    # Scientific authority and evaluator-facing semantics.
    #
    semantic_keys = [
        "embedded_generation_3_requirements",
        "embedded_preregistration_contract",
        "embedded_public_evaluator_contract",
        "source_bindings",
        "authority_order",
        "executable_case_contract",
        "claim_limits",
    ]

    for key in semantic_keys:
        canonical_v6 = transform(
            v6[key],
            REVERSE_REPLACEMENTS,
            6,
            5,
        )

        assert canonical_v6 == v5[key], key


    public_contract = v6[
        "embedded_public_evaluator_contract"
    ]

    assert public_contract[
        "source_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA

    assert public_contract[
        "interface_totals"
    ][
        "complete_fact_keys"
    ] == 115

    assert public_contract[
        "interface_totals"
    ][
        "complete_violation_codes"
    ] == 79

    assert len(
        public_contract[
            "requirements"
        ]
    ) == 27


    #
    # Holdout design remains fixed.
    #
    design = v6[
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
        "case_id_pattern"
    ] == "G3-H6-NNN"

    assert design[
        "case_ids"
    ] == [
        f"G3-H6-{number:03d}"
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


    #
    # Case schema.
    #
    assert v6[
        "case_schema"
    ][
        "id_format"
    ] == "G3-H6-NNN"


    #
    # Isolation contract remains fail-closed.
    #
    isolation = v6[
        "generation_session_isolation_contract"
    ]

    assert isolation[
        "gate_timing"
    ] == "BEFORE_ANY_CASE_GENERATION"

    assert isolation[
        "fail_closed"
    ] is True

    assert isolation[
        "package_v6_must_be_only_hetren_specific_context"
    ] is True

    assert isolation[
        "unrelated_non_hetren_context_is_permitted"
    ] is True

    assert isolation[
        "unrelated_non_hetren_context_must_not_trigger_abort"
    ] is True

    assert isolation[
        "unrelated_non_hetren_context_must_not_inform_case_design"
    ] is True

    assert isolation[
        "ambiguous_potentially_hetren_specific_context_detected_required_value"
    ] is False

    assert isolation[
        "if_any_required_false_field_is_true"
    ] == "ABORT_WITHOUT_GENERATING_CASES"

    assert isolation[
        "abort_output_filename"
    ] == (
        "generation_isolation_failure_attempt_6.json"
    )

    assert isolation[
        "abort_output_must_contain_cases"
    ] is False

    assert isolation[
        "abort_does_not_consume_target_freshness"
    ] is True

    assert isolation[
        "generator_must_not_continue_after_abort"
    ] is True


    #
    # Generator attestations.
    #
    attestations = v6[
        "required_generator_attestations"
    ]

    assert attestations[
        "received_only_generation_package_v6_as_hetren_specific_input"
    ] is True

    assert attestations[
        "hetren_specific_context_gate_checked_before_case_generation"
    ] is True

    assert attestations[
        "no_nonpackage_hetren_context_received"
    ] is True

    assert attestations[
        "unrelated_non_hetren_context_not_used_for_case_design"
    ] is True

    assert attestations[
        "generated_all_54_cases_before_target_execution"
    ] is True

    assert attestations[
        "did_not_execute_or_simulate_target_evaluator"
    ] is True


    #
    # Success/failure output identities.
    #
    output = v6[
        "expected_output"
    ]

    assert output[
        "filename"
    ] == "fresh_holdout_cases_attempt_6.json"

    assert output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_FRESH_ADVERSARIAL_"
        "HOLDOUT_CASES_ATTEMPT_6"
    )

    assert output[
        "state"
    ] == "GENERATED_NOT_EXECUTED"

    assert output[
        "generation_attempt"
    ] == 6


    failure_output = v6[
        "expected_isolation_failure_output"
    ]

    assert failure_output[
        "filename"
    ] == (
        "generation_isolation_failure_attempt_6.json"
    )

    assert failure_output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_GENERATION_"
        "ISOLATION_FAILURE_ATTEMPT_6"
    )

    assert failure_output[
        "state"
    ] == "ABORTED_BEFORE_CASE_GENERATION"

    assert failure_output[
        "generation_attempt"
    ] == 6

    assert failure_output[
        "cases_must_be_absent"
    ] is True

    assert failure_output[
        "target_evaluator_executed"
    ] is False

    assert failure_output[
        "target_predictions_produced"
    ] is False


    #
    # Prior Attempt-5 evidence must not leak into generator-visible v6.
    #
    package_text = V6_FILE.read_text()

    forbidden_values = [
        EXPECTED_ATTEMPT5_FAILURE_SHA,
        EXPECTED_ATTEMPT5_DISPOSITION_SHA,
        "generation_isolation_failure_attempt_5.json",
        "fresh_holdout_generation_attempt_5_disposition.json",
        "G3-H5-",
        "G3-H4-",
        "G3-H3-",
    ]

    for value in forbidden_values:
        assert value not in package_text, value


    #
    # Attempt-5 disposition governs successor Attempt 6.
    #
    assert disposition5[
        "state"
    ] == (
        "ABORTED_PRE_CASE_GENERATION_"
        "AMBIGUOUS_SAVED_CONTEXT_BREADCRUMBS"
    )

    assert disposition5[
        "cases_generated"
    ] is False

    assert disposition5[
        "target_evaluator_executed"
    ] is False

    assert disposition5[
        "target_evaluator_simulated"
    ] is False

    assert disposition5[
        "target_predictions_produced"
    ] is False

    assert disposition5[
        "target_freshness_consumed"
    ] is False

    successor = disposition5[
        "successor_requirement"
    ]

    assert successor[
        "next_attempt"
    ] == 6

    assert successor[
        "new_generation_environment_required"
    ] is True

    assert successor[
        "attempt_5_environment_must_not_be_reused"
    ] is True

    assert successor[
        "generation_environment_must_not_expose_prior_hetren_breadcrumbs"
    ] is True

    assert successor[
        "generation_environment_must_not_expose_nonpackage_hetren_context"
    ] is True

    assert successor[
        "generation_environment_must_not_expose_ambiguous_potentially_hetren_specific_context"
    ] is True

    assert successor[
        "unrelated_non_hetren_context_remains_permitted"
    ] is True

    assert successor[
        "package_v5_semantics_should_remain_unchanged_unless_separately_invalidated"
    ] is True

    assert successor[
        "target_evaluator_must_remain_frozen"
    ] is True

    assert successor[
        "freshness_available_for_successor_attempt"
    ] is True


    print("PASS: exact Generation Package v6")
    print("PASS: v6 reverses exactly to frozen v5")
    print("PASS: only authorized operational identity substitutions exist")
    print("PASS: G3/D1/public evaluator semantics preserved")
    print("PASS: frozen target evaluator binding unchanged")

    print(
        "Public interface:",
        public_contract[
            "interface_totals"
        ][
            "complete_fact_keys"
        ],
        "facts /",
        public_contract[
            "interface_totals"
        ][
            "complete_violation_codes"
        ],
        "codes",
    )

    print(
        "Required cases:",
        design[
            "case_count"
        ],
    )

    print(
        "Case namespace:",
        design[
            "case_id_pattern"
        ],
    )

    print(
        "Unrelated non-Hetren context blocks generation: NO"
    )

    print(
        "Non-package/ambiguous Hetren context blocks generation: YES"
    )

    print(
        "Attempt-5 evidence embedded: NO"
    )

    print(
        "Target evaluator executed: NO"
    )

    print(
        "Target freshness consumed: NO"
    )


if __name__ == "__main__":
    main()
