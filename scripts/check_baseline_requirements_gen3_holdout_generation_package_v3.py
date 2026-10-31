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

V2_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v2.json"
)

V3_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v3.json"
)

ATTEMPT2_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_attempt_2.json"
)

ATTEMPT2_DISPOSITION_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_attempt_2_disposition.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)


EXPECTED_V2_SHA = (
    "ac273519cea881f75ea89ab9efa7eeba"
    "c7eb2bf5a10a250a5d261c0e22e1074c"
)

EXPECTED_V3_SHA = (
    "0d55267ee6b40ac69fd07470dcf09e57"
    "14ba3002686f62d4cc6a5a9625ebe8ff"
)

EXPECTED_ATTEMPT2_SHA = (
    "91557fcea5f2202fdc634cc19fb79d55"
    "f33718b146172a838978ce5e7037ca0a"
)

EXPECTED_ATTEMPT2_DISPOSITION_SHA = (
    "c16fd6827db35fea4e48a4711e5ee146"
    "65bf664541441c59fe12b20cda17ee2b"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)


def sha256(target_file):
    return hashlib.sha256(
        target_file.read_bytes()
    ).hexdigest()


def main():
    assert sha256(
        V2_FILE
    ) == EXPECTED_V2_SHA

    assert sha256(
        V3_FILE
    ) == EXPECTED_V3_SHA

    assert sha256(
        ATTEMPT2_FILE
    ) == EXPECTED_ATTEMPT2_SHA

    assert sha256(
        ATTEMPT2_DISPOSITION_FILE
    ) == EXPECTED_ATTEMPT2_DISPOSITION_SHA

    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA


    v2 = json.loads(
        V2_FILE.read_text()
    )

    v3 = json.loads(
        V3_FILE.read_text()
    )

    attempt2_disposition = json.loads(
        ATTEMPT2_DISPOSITION_FILE.read_text()
    )


    #
    # Governed successor identity.
    #
    assert v3[
        "schema_version"
    ] == "3.0.0"

    assert v3[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ISOLATED_FRESH_"
        "HOLDOUT_GENERATION_PACKAGE_V3"
    )

    assert v3[
        "state"
    ] == (
        "READY_FOR_ISOLATED_GENERATION_ATTEMPT_3"
    )

    assert v3[
        "generation_attempt"
    ] == 3

    assert v3[
        "contains_holdout_cases"
    ] is False

    assert v3[
        "attempt_3_cases_generated"
    ] is False

    assert v3[
        "target_evaluator_executed"
    ] is False

    assert v3[
        "fresh_holdout_generation"
    ] is True

    assert v3[
        "protected_evaluation"
    ] is True

    assert v3[
        "authoritative"
    ] is False

    assert v3[
        "scientific_support_established"
    ] is False


    #
    # Semantic authority and executable semantics are unchanged.
    #
    immutable_semantic_keys = [
        "embedded_generation_3_requirements",
        "embedded_preregistration_contract",
        "embedded_public_evaluator_contract",
        "source_bindings",
        "authority_order",
        "executable_case_contract",
        "claim_limits",
    ]

    for key in immutable_semantic_keys:
        assert v3[key] == v2[key], key


    public_contract = v3[
        "embedded_public_evaluator_contract"
    ]

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
    # Core generation design remains 54 / 27+27 / 27 BRs.
    #
    design = v3[
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
        "total_must_accept"
    ] == 27

    assert design[
        "total_must_reject"
    ] == 27

    assert design[
        "per_requirement_expectation_pattern"
    ] == {
        "MUST_ACCEPT": 1,
        "MUST_REJECT": 1,
    }

    assert design[
        "case_id_pattern"
    ] == "G3-H3-NNN"

    assert design[
        "case_ids"
    ] == [
        f"G3-H3-{number:03d}"
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


    assert v3[
        "case_schema"
    ][
        "id_format"
    ] == "G3-H3-NNN"


    #
    # Fail-closed session isolation.
    #
    isolation = v3[
        "generation_session_isolation_contract"
    ]

    assert isolation[
        "gate_timing"
    ] == "BEFORE_ANY_CASE_GENERATION"

    assert isolation[
        "fail_closed"
    ] is True

    assert isolation[
        "package_v3_must_be_only_hetren_specific_context"
    ] is True

    assert isolation[
        "nonpackage_hetren_context_detected_required_value"
    ] is False

    assert isolation[
        "project_context_detected_required_value"
    ] is False

    assert isolation[
        "memory_or_saved_context_detected_required_value"
    ] is False

    assert isolation[
        "prior_chat_or_summary_detected_required_value"
    ] is False

    assert isolation[
        "prior_generation_request_excerpt_detected_required_value"
    ] is False

    assert isolation[
        "prior_generation_attempt_detected_required_value"
    ] is False

    assert isolation[
        "repository_material_detected_required_value"
    ] is False

    assert isolation[
        "target_evaluator_information_detected_required_value"
    ] is False

    assert isolation[
        "prior_cases_mutations_predictions_results_detected_required_value"
    ] is False

    assert isolation[
        "remediation_history_detected_required_value"
    ] is False

    assert isolation[
        "if_any_required_false_field_is_true"
    ] == "ABORT_WITHOUT_GENERATING_CASES"

    assert isolation[
        "abort_output_filename"
    ] == (
        "generation_isolation_failure_attempt_3.json"
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
    # Successful output must itself attest machine-readable
    # isolation state.
    #
    success_isolation = v3[
        "required_success_output_isolation_state"
    ]

    expected_false_fields = {
        "nonpackage_hetren_context_detected",
        "project_context_detected",
        "memory_or_saved_context_detected",
        "prior_chat_or_summary_detected",
        "prior_generation_request_excerpt_detected",
        "prior_generation_attempt_detected",
        "repository_material_detected",
        "target_evaluator_information_detected",
        "prior_cases_mutations_predictions_results_detected",
        "remediation_history_detected",
    }

    assert (
        set(success_isolation)
        == expected_false_fields
        | {
            "isolation_gate_passed_before_case_generation"
        }
    )

    for key in expected_false_fields:
        assert success_isolation[
            key
        ] is False

    assert success_isolation[
        "isolation_gate_passed_before_case_generation"
    ] is True


    #
    # Generator attestations are strict and complete.
    #
    expected_attestation_keys = {
        "received_only_generation_package_v3_as_hetren_input",
        "ambient_context_gate_checked_before_case_generation",
        "no_nonpackage_hetren_context_received",
        "no_hetren_project_context_received",
        "no_hetren_memory_or_saved_context_received",
        "no_prior_hetren_chat_or_summary_received",
        "no_prior_generation_request_excerpt_received",
        "did_not_read_any_prior_generation_attempt",
        "did_not_read_target_evaluator_source",
        "did_not_read_target_evaluator_branch_conditions",
        "did_not_read_known_development_cases",
        "did_not_read_known_mutations",
        "did_not_read_prior_predictions_or_results",
        "did_not_read_remediation_history",
        "generated_all_54_cases_before_target_execution",
        "did_not_execute_or_simulate_target_evaluator",
    }

    attestations = v3[
        "required_generator_attestations"
    ]

    assert set(
        attestations
    ) == expected_attestation_keys

    assert all(
        attestations.values()
    )


    #
    # Isolation instructions explicitly include the classes that
    # invalidated Attempt 2.
    #
    isolation_rule = v3[
        "generator_isolation_rule"
    ]

    for required_phrase in [
        "project instructions or project context",
        "memory or saved personal context",
        "prior-chat content or summaries",
        "earlier generation-request excerpts",
        "prior attempts",
        "repository material",
        "evaluator information",
        "cases",
        "mutations",
        "predictions",
        "results",
        "remediation history",
    ]:
        assert (
            required_phrase
            in isolation_rule
        ), required_phrase


    #
    # Success and abort outputs are distinct.
    #
    success_output = v3[
        "expected_output"
    ]

    assert success_output[
        "filename"
    ] == "fresh_holdout_cases_attempt_3.json"

    assert success_output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_FRESH_ADVERSARIAL_"
        "HOLDOUT_CASES_ATTEMPT_3"
    )

    assert success_output[
        "state"
    ] == "GENERATED_NOT_EXECUTED"

    assert success_output[
        "generation_attempt"
    ] == 3

    assert (
        "generation_session_isolation"
        in success_output[
            "required_top_level_fields"
        ]
    )


    abort_output = v3[
        "expected_isolation_failure_output"
    ]

    assert abort_output[
        "filename"
    ] == (
        "generation_isolation_failure_attempt_3.json"
    )

    assert abort_output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_GENERATION_"
        "ISOLATION_FAILURE_ATTEMPT_3"
    )

    assert abort_output[
        "state"
    ] == (
        "ABORTED_BEFORE_CASE_GENERATION"
    )

    assert abort_output[
        "generation_attempt"
    ] == 3

    assert abort_output[
        "cases_must_be_absent"
    ] is True

    assert abort_output[
        "target_evaluator_executed"
    ] is False

    assert abort_output[
        "target_predictions_produced"
    ] is False


    #
    # Prior Attempt-2 evidence is historical lineage only and
    # must not be embedded in the generation package.
    #
    package_text = V3_FILE.read_text()

    forbidden_exact_values = [
        EXPECTED_ATTEMPT2_SHA,
        EXPECTED_ATTEMPT2_DISPOSITION_SHA,
        (
            "9e4b88a946a889dcb37b8e80567140c4"
            "54fcf903da1281cf510243de4dbcf6cd"
        ),
    ]

    for value in forbidden_exact_values:
        assert value not in package_text


    for forbidden_name in [
        "fresh_holdout_generation_attempt_2.json",
        "fresh_holdout_generation_attempt_2_disposition.json",
    ]:
        assert forbidden_name not in package_text


    #
    # Existing frozen evaluator remains unchanged.
    #
    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA


    #
    # Historical Attempt 2 remains rejected, unexecuted,
    # and freshness-preserving.
    #
    assert attempt2_disposition[
        "state"
    ] == (
        "REJECTED_PRE_EXECUTION_INPUT_BOUNDARY_MISMATCH"
    )

    assert attempt2_disposition[
        "target_evaluator_executed"
    ] is False

    assert attempt2_disposition[
        "protected_evidence_leakage_proven"
    ] is False

    assert attempt2_disposition[
        "freshness_consequence"
    ][
        "target_freshness_consumed"
    ] is False

    assert attempt2_disposition[
        "successor_requirement"
    ][
        "next_attempt"
    ] == 3


    print(
        "PASS: exact Generation Package v3"
    )

    print(
        "Semantic authorities unchanged: YES"
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
        "Fail-closed isolation gate: YES"
    )

    print(
        "Successful isolation state machine-checkable: YES"
    )

    print(
        "Prior Attempt-2 evidence embedded: NO"
    )

    print(
        "Target evaluator executed: NO"
    )


if __name__ == "__main__":
    main()
