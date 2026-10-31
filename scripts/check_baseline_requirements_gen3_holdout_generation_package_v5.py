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

V4_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v4.json"
)

V5_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v5.json"
)

ATTEMPT4_FAILURE_FILE = (
    DATA_DIR
    / "generation_isolation_failure_attempt_4.json"
)

ATTEMPT4_DISPOSITION_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_attempt_4_disposition.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)


EXPECTED_V4_SHA = (
    "5dbf26fffa27c1b02112d296a6f56602"
    "3b080f733afae54d363e2df09cb866de"
)

EXPECTED_V5_SHA = (
    "ff785b10d526ef59269e1311e4ca4364"
    "185cd0041123602f7c6f0c634d468f83"
)

EXPECTED_ATTEMPT4_FAILURE_SHA = (
    "f0215c24848ad985f0ee52ed954ec7ee"
    "0d309bd1df419ccf4714cdfc8d2932ff"
)

EXPECTED_ATTEMPT4_DISPOSITION_SHA = (
    "c5be16ba58f2300fba8d54fd8694030f"
    "1560d2598feb4bd353e38b9737d932d5"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)


FORWARD_REPLACEMENTS = [
    ("generation_package_v4", "generation_package_v5"),
    ("package_v4", "package_v5"),
    ("PACKAGE_V4", "PACKAGE_V5"),
    ("Package v4", "Package v5"),
    ("Generation Package v4", "Generation Package v5"),
    ("attempt_4", "attempt_5"),
    ("ATTEMPT_4", "ATTEMPT_5"),
    ("Attempt 4", "Attempt 5"),
    ("attempt 4", "attempt 5"),
    ("G3-H4", "G3-H5"),
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
    if isinstance(
        value,
        dict,
    ):
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

            result[
                new_key
            ] = new_item

        return result

    if isinstance(
        value,
        list,
    ):
        return [
            transform(
                item,
                replacements,
                generation_from,
                generation_to,
            )
            for item in value
        ]

    if isinstance(
        value,
        str,
    ):
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
        V4_FILE
    ) == EXPECTED_V4_SHA

    assert sha256(
        V5_FILE
    ) == EXPECTED_V5_SHA

    assert sha256(
        ATTEMPT4_FAILURE_FILE
    ) == EXPECTED_ATTEMPT4_FAILURE_SHA

    assert sha256(
        ATTEMPT4_DISPOSITION_FILE
    ) == EXPECTED_ATTEMPT4_DISPOSITION_SHA

    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA


    v4 = load_json(
        V4_FILE
    )

    v5 = load_json(
        V5_FILE
    )

    disposition4 = load_json(
        ATTEMPT4_DISPOSITION_FILE
    )


    #
    # Successor identity.
    #
    assert v5[
        "schema_version"
    ] == "5.0.0"

    assert v5[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ISOLATED_FRESH_"
        "HOLDOUT_GENERATION_PACKAGE_V5"
    )

    assert v5[
        "state"
    ] == (
        "READY_FOR_ISOLATED_GENERATION_ATTEMPT_5"
    )

    assert v5[
        "generation_attempt"
    ] == 5

    assert v5[
        "contains_holdout_cases"
    ] is False

    assert v5[
        "attempt_5_cases_generated"
    ] is False

    assert v5[
        "target_evaluator_executed"
    ] is False

    assert v5[
        "fresh_holdout_generation"
    ] is True

    assert v5[
        "protected_evaluation"
    ] is True

    assert v5[
        "authoritative"
    ] is False

    assert v5[
        "scientific_support_established"
    ] is False


    #
    # Independent bounded-successor proof.
    #
    reconstructed_v4 = transform(
        v5,
        REVERSE_REPLACEMENTS,
        5,
        4,
    )

    reconstructed_v4[
        "schema_version"
    ] = "4.0.0"

    assert reconstructed_v4 == v4


    #
    # Top-level structure differs only by the renamed attempt key.
    #
    v4_keys = set(
        v4
    )

    v5_keys = set(
        v5
    )

    assert (
        v4_keys
        - v5_keys
    ) == {
        "attempt_4_cases_generated",
    }

    assert (
        v5_keys
        - v4_keys
    ) == {
        "attempt_5_cases_generated",
    }


    #
    # Scientific/evaluator content must canonicalize exactly
    # back to the frozen v4 content.
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
        canonical_v5 = transform(
            v5[
                key
            ],
            REVERSE_REPLACEMENTS,
            5,
            4,
        )

        assert canonical_v5 == v4[
            key
        ], key


    public_contract = v5[
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
    # Holdout design.
    #
    design = v5[
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
    ] == "G3-H5-NNN"

    assert design[
        "case_ids"
    ] == [
        f"G3-H5-{number:03d}"
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
    assert v5[
        "case_schema"
    ][
        "id_format"
    ] == "G3-H5-NNN"


    #
    # Isolation policy remains fail-closed for Hetren context,
    # while unrelated non-Hetren context remains non-blocking.
    #
    isolation = v5[
        "generation_session_isolation_contract"
    ]

    assert isolation[
        "gate_timing"
    ] == "BEFORE_ANY_CASE_GENERATION"

    assert isolation[
        "fail_closed"
    ] is True

    assert isolation[
        "package_v5_must_be_only_hetren_specific_context"
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
        "generation_isolation_failure_attempt_5.json"
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
    # Required generator attestations.
    #
    attestations = v5[
        "required_generator_attestations"
    ]

    assert attestations[
        "received_only_generation_package_v5_as_hetren_specific_input"
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
    output = v5[
        "expected_output"
    ]

    assert output[
        "filename"
    ] == "fresh_holdout_cases_attempt_5.json"

    assert output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_FRESH_ADVERSARIAL_"
        "HOLDOUT_CASES_ATTEMPT_5"
    )

    assert output[
        "state"
    ] == "GENERATED_NOT_EXECUTED"

    assert output[
        "generation_attempt"
    ] == 5


    failure_output = v5[
        "expected_isolation_failure_output"
    ]

    assert failure_output[
        "filename"
    ] == (
        "generation_isolation_failure_attempt_5.json"
    )

    assert failure_output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_GENERATION_"
        "ISOLATION_FAILURE_ATTEMPT_5"
    )

    assert failure_output[
        "state"
    ] == "ABORTED_BEFORE_CASE_GENERATION"

    assert failure_output[
        "generation_attempt"
    ] == 5

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
    # Old operational namespaces/evidence cannot leak into v5.
    #
    package_text = V5_FILE.read_text()

    forbidden_values = [
        EXPECTED_ATTEMPT4_FAILURE_SHA,
        EXPECTED_ATTEMPT4_DISPOSITION_SHA,
        "generation_isolation_failure_attempt_4.json",
        "fresh_holdout_generation_attempt_4_disposition.json",
        "generation_package_v3_0d55267e.json",
        "G3-H4-",
        "G3-H3-",
    ]

    for value in forbidden_values:
        assert value not in package_text, value


    #
    # Attempt-4 disposition authorizes Attempt 5.
    #
    assert disposition4[
        "state"
    ] == (
        "ABORTED_PRE_CASE_GENERATION_"
        "AMBIGUOUS_PRIOR_PACKAGE_BREADCRUMB"
    )

    assert disposition4[
        "cases_generated"
    ] is False

    assert disposition4[
        "target_evaluator_executed"
    ] is False

    assert disposition4[
        "target_predictions_produced"
    ] is False

    assert disposition4[
        "target_freshness_consumed"
    ] is False

    assert disposition4[
        "protected_evidence_leakage_proven"
    ] is False

    successor = disposition4[
        "successor_requirement"
    ]

    assert successor[
        "next_attempt"
    ] == 5

    assert successor[
        "new_generation_session_required"
    ] is True

    assert successor[
        "attempt_4_session_must_not_be_reused"
    ] is True

    assert successor[
        "package_v4_semantics_should_remain_unchanged_unless_separately_invalidated"
    ] is True

    assert successor[
        "target_evaluator_must_remain_frozen"
    ] is True

    assert successor[
        "freshness_available_for_successor_attempt"
    ] is True


    print("PASS: exact Generation Package v5")
    print("PASS: v5 reverses exactly to frozen v4")
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
        "Attempt-4 evidence embedded: NO"
    )

    print(
        "Target evaluator executed: NO"
    )

    print(
        "Target freshness consumed: NO"
    )


if __name__ == "__main__":
    main()
