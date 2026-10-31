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

V3_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v3.json"
)

V4_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v4.json"
)

ATTEMPT3_FAILURE_FILE = (
    DATA_DIR
    / "generation_isolation_failure_attempt_3.json"
)

ATTEMPT3_DISPOSITION_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_attempt_3_disposition.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)


EXPECTED_V3_SHA = (
    "0d55267ee6b40ac69fd07470dcf09e57"
    "14ba3002686f62d4cc6a5a9625ebe8ff"
)

EXPECTED_V4_SHA = (
    "5dbf26fffa27c1b02112d296a6f56602"
    "3b080f733afae54d363e2df09cb866de"
)

EXPECTED_ATTEMPT3_FAILURE_SHA = (
    "626f272c0c4142c8677fcc73dd400794"
    "ef1842e054fef7a616fe2f9ec4ece241"
)

EXPECTED_ATTEMPT3_DISPOSITION_SHA = (
    "4b326483d210d1c230920c2aa12ea44d"
    "c67e867e3b956ff5efa30d6dabd1f59e"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)


def sha256(target_file):
    return hashlib.sha256(
        target_file.read_bytes()
    ).hexdigest()


def load_json(target_file):
    return json.loads(
        target_file.read_text()
    )


def main():
    #
    # Exact governed bytes.
    #
    assert sha256(
        V3_FILE
    ) == EXPECTED_V3_SHA

    assert sha256(
        V4_FILE
    ) == EXPECTED_V4_SHA

    assert sha256(
        ATTEMPT3_FAILURE_FILE
    ) == EXPECTED_ATTEMPT3_FAILURE_SHA

    assert sha256(
        ATTEMPT3_DISPOSITION_FILE
    ) == EXPECTED_ATTEMPT3_DISPOSITION_SHA

    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA


    v3 = load_json(
        V3_FILE
    )

    v4 = load_json(
        V4_FILE
    )

    disposition3 = load_json(
        ATTEMPT3_DISPOSITION_FILE
    )


    #
    # Package identity.
    #
    assert v4[
        "schema_version"
    ] == "4.0.0"

    assert v4[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ISOLATED_FRESH_"
        "HOLDOUT_GENERATION_PACKAGE_V4"
    )

    assert v4[
        "state"
    ] == (
        "READY_FOR_ISOLATED_GENERATION_ATTEMPT_4"
    )

    assert v4[
        "generation_attempt"
    ] == 4

    assert v4[
        "contains_holdout_cases"
    ] is False

    assert v4[
        "attempt_4_cases_generated"
    ] is False

    assert v4[
        "target_evaluator_executed"
    ] is False

    assert v4[
        "fresh_holdout_generation"
    ] is True

    assert v4[
        "protected_evaluation"
    ] is True

    assert v4[
        "authoritative"
    ] is False

    assert v4[
        "scientific_support_established"
    ] is False


    #
    # Top-level bounded-successor surface.
    #
    allowed_changed_common_keys = {
        "schema_version",
        "artifact_type",
        "state",
        "generation_attempt",
        "allowed_generator_inputs",
        "forbidden_generator_inputs",
        "generator_isolation_rule",
        "freshness_scope",
        "operationalized_design",
        "case_schema",
        "generation_rules",
        "required_generator_attestations",
        "expected_output",
        "generation_session_isolation_contract",
        "required_success_output_isolation_state",
        "expected_isolation_failure_output",
    }

    expected_removed_keys = {
        "attempt_3_cases_generated",
    }

    expected_added_keys = {
        "attempt_4_cases_generated",
        "permitted_success_output_isolation_metadata",
    }


    removed = (
        set(v3)
        - set(v4)
    )

    added = (
        set(v4)
        - set(v3)
    )

    assert removed == expected_removed_keys, removed
    assert added == expected_added_keys, added


    common = (
        set(v3)
        & set(v4)
    )

    changed_common = {
        key
        for key in common
        if v3[key] != v4[key]
    }

    assert (
        changed_common
        <= allowed_changed_common_keys
    ), sorted(
        changed_common
        - allowed_changed_common_keys
    )


    #
    # Scientific authority and target interface are immutable.
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
        assert v4[key] == v3[key], key


    public_contract = v4[
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
    # Holdout design differs only by the case-ID namespace.
    #
    design3 = v3[
        "operationalized_design"
    ]

    design4 = v4[
        "operationalized_design"
    ]

    assert set(
        design3
    ) == set(
        design4
    )

    for key in design3:
        if key not in {
            "case_id_pattern",
            "case_ids",
        }:
            assert design4[key] == design3[key], key


    assert design4[
        "case_count"
    ] == 54

    assert design4[
        "primary_requirement_count"
    ] == 27

    assert design4[
        "cases_per_primary_requirement"
    ] == 2

    assert design4[
        "per_requirement_expectation_pattern"
    ] == {
        "MUST_ACCEPT": 1,
        "MUST_REJECT": 1,
    }

    assert design4[
        "total_must_accept"
    ] == 27

    assert design4[
        "total_must_reject"
    ] == 27

    assert design4[
        "case_id_pattern"
    ] == "G3-H4-NNN"

    assert design4[
        "case_ids"
    ] == [
        f"G3-H4-{number:03d}"
        for number in range(
            1,
            55,
        )
    ]

    assert set(
        design4[
            "environment_values"
        ]
    ) == {
        "E1",
        "E2",
        "E3",
        "CROSS_ENV",
    }

    assert design4[
        "minimum_cases_per_environment"
    ] == 6

    assert design4[
        "minimum_cross_requirement_interaction_cases"
    ] == 12


    #
    # Case schema differs only by ID namespace.
    #
    schema3 = v3[
        "case_schema"
    ]

    schema4 = v4[
        "case_schema"
    ]

    assert set(
        schema3
    ) == set(
        schema4
    )

    for key in schema3:
        if key != "id_format":
            assert schema4[key] == schema3[key], key

    assert schema4[
        "id_format"
    ] == "G3-H4-NNN"


    #
    # Attempt-4 isolation semantics.
    #
    isolation = v4[
        "generation_session_isolation_contract"
    ]

    assert isolation[
        "gate_timing"
    ] == "BEFORE_ANY_CASE_GENERATION"

    assert isolation[
        "fail_closed"
    ] is True

    assert isolation[
        "package_v4_must_be_only_hetren_specific_context"
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


    false_fields = [
        key
        for key in isolation
        if key.endswith(
            "_detected_required_value"
        )
    ]

    expected_false_fields = {
        "nonpackage_hetren_context_detected_required_value",
        "nonpackage_hetren_project_context_detected_required_value",
        "nonpackage_hetren_memory_or_saved_context_detected_required_value",
        "nonpackage_prior_hetren_chat_or_summary_detected_required_value",
        "nonpackage_prior_hetren_generation_request_excerpt_detected_required_value",
        "nonpackage_prior_hetren_generation_attempt_detected_required_value",
        "nonpackage_hetren_repository_material_detected_required_value",
        "nonpackage_target_evaluator_information_detected_required_value",
        "nonpackage_prior_hetren_cases_mutations_predictions_results_detected_required_value",
        "nonpackage_hetren_remediation_history_detected_required_value",
        "ambiguous_potentially_hetren_specific_context_detected_required_value",
    }

    assert set(
        false_fields
    ) == expected_false_fields

    for key in false_fields:
        assert isolation[key] is False, key


    assert isolation[
        "if_any_required_false_field_is_true"
    ] == "ABORT_WITHOUT_GENERATING_CASES"

    assert isolation[
        "abort_output_filename"
    ] == (
        "generation_isolation_failure_attempt_4.json"
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
    # Allowed input explicitly distinguishes unrelated context.
    #
    allowed_inputs = v4[
        "allowed_generator_inputs"
    ]

    assert any(
        "unrelated non-Hetren"
        in value
        for value in allowed_inputs
    )


    #
    # Every forbidden input is Hetren-specific.
    #
    forbidden_inputs = v4[
        "forbidden_generator_inputs"
    ]

    assert forbidden_inputs

    for value in forbidden_inputs:
        assert "Hetren" in value, value


    #
    # Prose rule agrees with structured isolation semantics.
    # These checks test concepts, not arbitrary duplicate wording.
    #
    rule = v4[
        "generator_isolation_rule"
    ]

    assert (
        "HETREN-SPECIFIC"
        in rule
    )

    assert (
        "unrelated account memory"
        in rule
    )

    assert (
        "MUST NOT by itself cause an abort"
        in rule
    )

    assert (
        "non-package Hetren-specific information"
        in rule
    )

    assert (
        "If any context is clearly Hetren-specific"
        in rule
    )

    assert (
        "Do not use unrelated non-Hetren context to design cases"
        in rule
    )


    #
    # Successful isolation state is machine-readable.
    #
    success = v4[
        "required_success_output_isolation_state"
    ]

    success_false_fields = {
        key
        for key, value in success.items()
        if key != "isolation_gate_passed_before_case_generation"
        and value is False
    }

    expected_success_false_fields = {
        "nonpackage_hetren_context_detected",
        "nonpackage_hetren_project_context_detected",
        "nonpackage_hetren_memory_or_saved_context_detected",
        "nonpackage_prior_hetren_chat_or_summary_detected",
        "nonpackage_prior_hetren_generation_request_excerpt_detected",
        "nonpackage_prior_hetren_generation_attempt_detected",
        "nonpackage_hetren_repository_material_detected",
        "nonpackage_target_evaluator_information_detected",
        "nonpackage_prior_hetren_cases_mutations_predictions_results_detected",
        "nonpackage_hetren_remediation_history_detected",
        "ambiguous_potentially_hetren_specific_context_detected",
    }

    assert (
        success_false_fields
        == expected_success_false_fields
    )

    assert set(
        success
    ) == (
        expected_success_false_fields
        | {
            "isolation_gate_passed_before_case_generation"
        }
    )

    assert success[
        "isolation_gate_passed_before_case_generation"
    ] is True


    #
    # Unrelated context may be transparently disclosed.
    #
    metadata = v4[
        "permitted_success_output_isolation_metadata"
    ]

    expected_metadata_keys = {
        "unrelated_non_hetren_context_present",
        "unrelated_non_hetren_project_context_present",
        "unrelated_non_hetren_memory_or_saved_context_present",
        "unrelated_non_hetren_prior_chat_or_summary_present",
    }

    assert set(
        metadata
    ) == expected_metadata_keys

    for key in expected_metadata_keys:
        spec = metadata[
            key
        ]

        assert spec[
            "allowed_values"
        ] == [
            True,
            False,
        ]

        assert spec[
            "does_not_affect_isolation_pass"
        ] is True


    #
    # Required generator attestations.
    #
    attestations = v4[
        "required_generator_attestations"
    ]

    expected_attestations = {
        "received_only_generation_package_v4_as_hetren_specific_input",
        "hetren_specific_context_gate_checked_before_case_generation",
        "no_nonpackage_hetren_context_received",
        "no_nonpackage_hetren_project_context_received",
        "no_nonpackage_hetren_memory_or_saved_context_received",
        "no_nonpackage_prior_hetren_chat_or_summary_received",
        "no_nonpackage_prior_hetren_generation_request_excerpt_received",
        "did_not_read_any_prior_hetren_generation_attempt",
        "did_not_read_target_hetren_evaluator_source",
        "did_not_read_target_hetren_evaluator_branch_conditions",
        "did_not_read_known_hetren_development_cases",
        "did_not_read_known_hetren_mutations",
        "did_not_read_prior_hetren_predictions_or_results",
        "did_not_read_hetren_remediation_history",
        "unrelated_non_hetren_context_not_used_for_case_design",
        "generated_all_54_cases_before_target_execution",
        "did_not_execute_or_simulate_target_evaluator",
    }

    assert set(
        attestations
    ) == expected_attestations

    assert all(
        attestations.values()
    )


    #
    # Success output identity.
    #
    output = v4[
        "expected_output"
    ]

    assert output[
        "filename"
    ] == "fresh_holdout_cases_attempt_4.json"

    assert output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_FRESH_ADVERSARIAL_"
        "HOLDOUT_CASES_ATTEMPT_4"
    )

    assert output[
        "state"
    ] == "GENERATED_NOT_EXECUTED"

    assert output[
        "generation_attempt"
    ] == 4

    assert output[
        "fresh_holdout"
    ] is True

    assert output[
        "protected_evaluation"
    ] is True

    assert output[
        "authoritative"
    ] is False

    assert output[
        "scientific_support_established"
    ] is False

    assert (
        "generation_session_isolation"
        in output[
            "required_top_level_fields"
        ]
    )


    #
    # Failure output identity.
    #
    failure_output = v4[
        "expected_isolation_failure_output"
    ]

    assert failure_output[
        "filename"
    ] == (
        "generation_isolation_failure_attempt_4.json"
    )

    assert failure_output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_GENERATION_"
        "ISOLATION_FAILURE_ATTEMPT_4"
    )

    assert failure_output[
        "state"
    ] == "ABORTED_BEFORE_CASE_GENERATION"

    assert failure_output[
        "generation_attempt"
    ] == 4

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
    # Generation rule count remains stable.
    #
    rules3 = v3[
        "generation_rules"
    ]

    rules4 = v4[
        "generation_rules"
    ]

    assert len(
        rules4
    ) == len(
        rules3
    )

    assert (
        "non-package Hetren-specific context"
        in rules4[0]
    )

    assert (
        "Unrelated non-Hetren"
        in rules4[0]
    )

    assert (
        "does not trigger abort"
        in rules4[0]
    )

    assert all(
        "G3-H3-"
        not in rule
        for rule in rules4
    )

    assert any(
        "G3-H4-001 through G3-H4-054"
        in rule
        for rule in rules4
    )


    #
    # Historical Attempt-3 evidence is not exposed in v4.
    #
    package_text = V4_FILE.read_text()

    for forbidden_value in [
        EXPECTED_ATTEMPT3_FAILURE_SHA,
        EXPECTED_ATTEMPT3_DISPOSITION_SHA,
    ]:
        assert forbidden_value not in package_text


    for forbidden_filename in [
        "generation_isolation_failure_attempt_3.json",
        "fresh_holdout_generation_attempt_3_disposition.json",
    ]:
        assert forbidden_filename not in package_text


    assert "G3-H3-" not in package_text


    #
    # Attempt-3 disposition authorizes this successor.
    #
    assert disposition3[
        "state"
    ] == (
        "ABORTED_PRE_CASE_GENERATION_HANDOFF_SCOPE_MISMATCH"
    )

    assert disposition3[
        "cases_generated"
    ] is False

    assert disposition3[
        "target_evaluator_executed"
    ] is False

    assert disposition3[
        "target_predictions_produced"
    ] is False

    assert disposition3[
        "protected_evidence_leakage_proven"
    ] is False

    assert disposition3[
        "target_freshness_consumed"
    ] is False

    successor = disposition3[
        "successor_requirement"
    ]

    assert successor[
        "next_attempt"
    ] == 4

    assert successor[
        "unrelated_non_hetren_context_must_not_trigger_abort"
    ] is True

    assert successor[
        "nonpackage_hetren_context_must_trigger_abort"
    ] is True

    assert successor[
        "handoff_instruction_must_not_broaden_package_scope"
    ] is True


    print(
        "PASS: exact Generation Package v4"
    )

    print(
        "PASS: bounded-successor top-level diff"
    )

    print(
        "PASS: G3/D1/public evaluator semantics unchanged"
    )

    print(
        "PASS: frozen target evaluator binding unchanged"
    )

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
        design4[
            "case_count"
        ],
    )

    print(
        "Case namespace:",
        design4[
            "case_id_pattern"
        ],
    )

    print(
        "Unrelated non-Hetren context blocks generation: NO"
    )

    print(
        "Non-package Hetren context blocks generation: YES"
    )

    print(
        "Ambiguous potentially Hetren-specific context blocks generation: YES"
    )

    print(
        "Prior Attempt-3 evidence embedded: NO"
    )

    print(
        "Target evaluator executed: NO"
    )


if __name__ == "__main__":
    main()
