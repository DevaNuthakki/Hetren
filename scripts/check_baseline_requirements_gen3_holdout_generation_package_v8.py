from copy import deepcopy
from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parents[1]

DATA = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "baseline_requirements_gen3"
)

G3_FILE = (
    ROOT
    / "docs"
    / "research"
    / "baselines"
    / "task-08-baseline-requirements-gen3.json"
)

PREREG_FILE = (
    DATA
    / "fresh_holdout_contract.json"
)

PUBLIC_CONTRACT_FILE = (
    DATA
    / "public_evaluator_contract.json"
)

PUBLIC_CONTRACT_MANIFEST_FILE = (
    DATA
    / "public_evaluator_contract_manifest.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)

V7_FILE = (
    DATA
    / "fresh_holdout_generation_package_v7.json"
)

V7_MANIFEST_FILE = (
    DATA
    / "fresh_holdout_generation_package_v7_manifest.json"
)

ATTEMPT7_FAILURE_FILE = (
    DATA
    / "generation_isolation_failure_attempt_7.json"
)

ATTEMPT7_DISPOSITION_FILE = (
    DATA
    / "fresh_holdout_generation_attempt_7_disposition.json"
)

DECISION8_FILE = (
    DATA
    / "generation_environment_decision_attempt_8.json"
)

V8_FILE = (
    DATA
    / "fresh_holdout_generation_package_v8.json"
)

V8_MANIFEST_FILE = (
    DATA
    / "fresh_holdout_generation_package_v8_manifest.json"
)


EXPECTED_G3_SHA = (
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

EXPECTED_PUBLIC_CONTRACT_MANIFEST_SHA = (
    "08ee63f8e2f277f52d7a6d44106b2ff"
    "58d806d3ea317aab9cf7d8b78052c684e"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)

EXPECTED_V7_SHA = (
    "990a611b7be68448bf899a111323ac4d"
    "108ba5b01378831c67a635788e9c21e6"
)

EXPECTED_V7_MANIFEST_SHA = (
    "b98f843e17ca7878ef217fb06e2a86d"
    "441d93449346ec8a996959d95dac96606"
)

EXPECTED_ATTEMPT7_FAILURE_SHA = (
    "db458c5d83b2c2735d2101fb0510303e"
    "0de9020abaaf3ef40b71acc602377fd9"
)

EXPECTED_ATTEMPT7_DISPOSITION_SHA = (
    "db1ab828397d9741439d60a600e127305"
    "db0dde747207a827571827c4eac2c06"
)

EXPECTED_DECISION8_SHA = (
    "4571104befe9d261bd4632442056cb843"
    "cce460d860a1fe10b7a86ee72f61f95"
)

EXPECTED_V8_SHA = (
    "383753fc816ea1a6a2ffb264fb0d2325"
    "f0b45276fc74c75a902c7f090908b02a"
)

EXPECTED_V8_MANIFEST_SHA = (
    "13815948557e63a226c7881ae097d890"
    "60d34fe503cb163f4493b440bd42d805"
)


FORWARD_REPLACEMENTS = [
    (
        "generation_package_v7",
        "generation_package_v8",
    ),
    (
        "package_v7",
        "package_v8",
    ),
    (
        "PACKAGE_V7",
        "PACKAGE_V8",
    ),
    (
        "Generation Package v7",
        "Generation Package v8",
    ),
    (
        "Package v7",
        "Package v8",
    ),
    (
        "Package-v7",
        "Package-v8",
    ),
    (
        "package-v7",
        "package-v8",
    ),
    (
        "attempt_7",
        "attempt_8",
    ),
    (
        "ATTEMPT_7",
        "ATTEMPT_8",
    ),
    (
        "Attempt 7",
        "Attempt 8",
    ),
    (
        "attempt 7",
        "attempt 8",
    ),
    (
        "G3-H7",
        "G3-H8",
    ),
]


AUTHORIZED_NONMECHANICAL_FIELDS = {
    "allowed_generator_inputs",
    "forbidden_generator_inputs",
    "generator_isolation_rule",
    "freshness_scope",
    "generation_rules",
    "required_generator_attestations",
    "generation_session_isolation_contract",
    "required_success_output_isolation_state",
    "expected_isolation_failure_output",
    "permitted_success_output_isolation_metadata",
}


FROZEN_AUTHORITY_KEYS = [
    "embedded_generation_3_requirements",
    "embedded_preregistration_contract",
    "embedded_public_evaluator_contract",
    "source_bindings",
    "authority_order",
    "executable_case_contract",
    "claim_limits",
]


def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(path):
    return json.loads(
        path.read_text()
    )


def replace_text(value):
    for old, new in FORWARD_REPLACEMENTS:
        value = value.replace(
            old,
            new,
        )

    return value


def transform(value):
    if isinstance(value, dict):
        result = {}

        for key, item in value.items():
            new_key = replace_text(
                key
            )

            if (
                new_key == "generation_attempt"
                and item == 7
            ):
                new_item = 8
            else:
                new_item = transform(
                    item
                )

            result[
                new_key
            ] = new_item

        return result

    if isinstance(value, list):
        return [
            transform(item)
            for item in value
        ]

    if isinstance(value, str):
        return replace_text(
            value
        )

    return value


def main():
    #
    # 1. Exact governed bytes.
    #
    exact_hashes = [
        (
            G3_FILE,
            EXPECTED_G3_SHA,
        ),
        (
            PREREG_FILE,
            EXPECTED_PREREG_SHA,
        ),
        (
            PUBLIC_CONTRACT_FILE,
            EXPECTED_PUBLIC_CONTRACT_SHA,
        ),
        (
            PUBLIC_CONTRACT_MANIFEST_FILE,
            EXPECTED_PUBLIC_CONTRACT_MANIFEST_SHA,
        ),
        (
            EVALUATOR_FILE,
            EXPECTED_EVALUATOR_SHA,
        ),
        (
            V7_FILE,
            EXPECTED_V7_SHA,
        ),
        (
            V7_MANIFEST_FILE,
            EXPECTED_V7_MANIFEST_SHA,
        ),
        (
            ATTEMPT7_FAILURE_FILE,
            EXPECTED_ATTEMPT7_FAILURE_SHA,
        ),
        (
            ATTEMPT7_DISPOSITION_FILE,
            EXPECTED_ATTEMPT7_DISPOSITION_SHA,
        ),
        (
            DECISION8_FILE,
            EXPECTED_DECISION8_SHA,
        ),
        (
            V8_FILE,
            EXPECTED_V8_SHA,
        ),
        (
            V8_MANIFEST_FILE,
            EXPECTED_V8_MANIFEST_SHA,
        ),
    ]

    for path, expected in exact_hashes:
        assert path.exists(), path
        assert sha256(
            path
        ) == expected, path

    v7 = load_json(
        V7_FILE
    )

    failure7 = load_json(
        ATTEMPT7_FAILURE_FILE
    )

    disposition7 = load_json(
        ATTEMPT7_DISPOSITION_FILE
    )

    decision8 = load_json(
        DECISION8_FILE
    )

    v8 = load_json(
        V8_FILE
    )

    manifest8 = load_json(
        V8_MANIFEST_FILE
    )

    #
    # 2. Attempt-7 historical boundary.
    #
    assert failure7[
        "generation_attempt"
    ] == 7

    assert failure7[
        "state"
    ] == "ABORTED_BEFORE_CASE_GENERATION"

    assert failure7[
        "cases_generated"
    ] is False

    assert failure7[
        "target_evaluator_executed"
    ] is False

    assert failure7[
        "target_evaluator_simulated"
    ] is False

    assert failure7[
        "target_predictions_produced"
    ] is False

    assert failure7[
        "target_freshness_consumed"
    ] is False

    assert disposition7[
        "generation_attempt"
    ] == 7

    assert disposition7[
        "state"
    ] == (
        "ABORTED_PRE_CASE_GENERATION_"
        "ISOLATION_FAILURE"
    )

    classification = disposition7[
        "classification"
    ]

    assert classification[
        "category"
    ] == "GENERATION_ENVIRONMENT_ISOLATION_ABORT"

    assert classification[
        "generation_environment_isolation_failure"
    ] is True

    assert classification[
        "package_v7_semantic_contract_defect_established"
    ] is False

    assert classification[
        "package_v7_public_interface_defect_established"
    ] is False

    assert classification[
        "package_v7_handoff_hash_defect_established"
    ] is False

    assert classification[
        "package_v7_generator_preflight_defect_established"
    ] is False

    assert classification[
        "target_evaluator_defect_established"
    ] is False

    generation_state = disposition7[
        "generation_state"
    ]

    assert generation_state[
        "cases_generated"
    ] is False

    assert generation_state[
        "generated_cases_accepted_for_protected_execution"
    ] is False

    assert generation_state[
        "generator_output_preflight_reached"
    ] is False

    assert generation_state[
        "target_evaluator_executed"
    ] is False

    assert generation_state[
        "target_evaluator_simulated"
    ] is False

    assert generation_state[
        "target_predictions_produced"
    ] is False

    assert generation_state[
        "target_freshness_consumed"
    ] is False

    successor = disposition7[
        "successor_requirement"
    ]

    required_successor_values = {
        "next_attempt": 8,
        "new_generation_environment_required": True,
        "new_generation_session_required": True,
        "attempt_7_generation_environment_must_not_be_reused": True,
        "attempt_7_generation_session_must_not_be_reused": True,
        "attempt_7_failure_artifact_must_not_be_supplied_to_successor_generator": True,
        "prior_generation_attempt_artifacts_must_not_be_supplied_to_successor_generator": True,
        "prior_generation_packages_must_not_be_supplied_to_successor_generator": True,
        "prior_cases_mutations_predictions_results_must_not_be_supplied_to_successor_generator": True,
        "target_evaluator_must_remain_frozen": True,
        "successor_package_must_preserve_same_scientific_contract": True,
        "successor_package_must_preserve_same_public_evaluator_interface": True,
        "successor_package_must_preserve_same_scoring_contract": True,
        "successor_package_must_preserve_v7_output_preflight_hardening": True,
        "successor_generation_environment_design_must_be_governed_before_handoff": True,
        "successor_environment_isolation_must_rely_on_auditable_observable_boundaries": True,
        "generator_must_not_be_required_to_introspect_unverifiable_hidden_provider_state": True,
        "target_freshness_available_for_successor_attempt": True,
    }

    for key, expected in required_successor_values.items():
        assert successor[
            key
        ] == expected, key

    #
    # 3. Attempt-8 generation-environment decision.
    #
    assert decision8[
        "schema_version"
    ] == "1.0.0"

    assert decision8[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ATTEMPT_8_"
        "GENERATION_ENVIRONMENT_DECISION"
    )

    assert decision8[
        "state"
    ] == "DECIDED_BEFORE_PACKAGE_V8"

    assert decision8[
        "generation_attempt"
    ] == 8

    assert decision8[
        "decision"
    ] == (
        "CHATGPT_TEMPORARY_UNPERSONALIZED_"
        "OBSERVABLE_ISOLATION"
    )

    predecessor = decision8[
        "governed_predecessor"
    ]

    assert predecessor[
        "attempt"
    ] == 7

    assert predecessor[
        "disposition_sha256"
    ] == EXPECTED_ATTEMPT7_DISPOSITION_SHA

    assert predecessor[
        "cases_generated"
    ] is False

    assert predecessor[
        "target_freshness_consumed"
    ] is False

    environment = decision8[
        "selected_environment"
    ]

    expected_environment = {
        "provider": "OpenAI",
        "product": "ChatGPT",
        "account": "SAME_USER_ACCOUNT_PERMITTED",
        "conversation_type": "TEMPORARY_CHAT",
        "personalization_mode": "UNPERSONALIZED",
        "must_start_from_general_new_chat": True,
        "must_not_start_inside_hetren_project": True,
        "must_not_be_added_to_project": True,
        "custom_gpt_prohibited": True,
        "plugins_prohibited": True,
        "connectors_prohibited": True,
        "automatic_library_search_required_off": True,
        "package_attachment_source": "LOCAL_DISK_ONLY",
        "add_from_library_prohibited": True,
        "web_search_prohibited": True,
        "external_retrieval_prohibited": True,
        "external_tools_prohibited": True,
        "prior_messages_required": 0,
        "first_user_message_must_be_generation_handoff": True,
        "only_hetren_specific_attachment": "FROZEN_PACKAGE_V8",
        "only_hetren_specific_text": "MINIMAL_GOVERNED_HANDOFF_INSTRUCTION",
        "followup_after_first_generator_response_prohibited": True,
        "temporary_chat_must_not_be_saved": True,
        "temporary_chat_must_not_be_converted_to_regular_chat": True,
    }

    assert environment == expected_environment

    visible_gate = decision8[
        "generator_visible_isolation_rule"
    ]

    assert visible_gate[
        "scope"
    ] == "OBSERVABLE_CONVERSATION_INPUTS_ONLY"

    assert visible_gate[
        "fail_closed_on_observable_boundary_violation"
    ] is True

    prohibited_hidden_checks = set(
        visible_gate[
            "generator_must_not_be_asked_to_determine"
        ]
    )

    assert prohibited_hidden_checks == {
        "undocumented provider-internal state",
        "provider retention systems",
        "provider safety infrastructure",
        "hidden server-side implementation details",
        "whether model pretraining ever contained related public material",
    }

    one_shot = decision8[
        "one_shot_generation_rule"
    ]

    assert one_shot[
        "single_first_response_is_attempt_artifact"
    ] is True

    assert one_shot[
        "generator_correction_turn_prohibited"
    ] is True

    assert one_shot[
        "generator_regeneration_turn_prohibited"
    ] is True

    assert one_shot[
        "generator_feedback_after_output_prohibited"
    ] is True

    assert one_shot[
        "first_response_must_be_preserved_before_static_validation"
    ] is True

    assert one_shot[
        "static_validation_occurs_outside_generation_session"
    ] is True

    assert one_shot[
        "target_execution_prohibited_until_static_validation_passes"
    ] is True

    package_requirements = decision8[
        "attempt_8_package_requirements"
    ]

    for key in [
        "preserve_generation_3_requirements",
        "preserve_preregistration_contract",
        "preserve_public_evaluator_interface",
        "preserve_scoring_contract",
        "preserve_frozen_target_evaluator",
        "preserve_v7_output_preflight_hardening",
        "replace_hidden_state_isolation_introspection_with_observable_input_gate",
        "preserve_fail_closed_semantics_for_observable_boundary_violations",
        "package_v8_must_not_embed_attempt_7_failure_contents",
        "package_v8_must_not_embed_attempt_7_disposition_contents",
        "package_v8_must_not_embed_prior_cases",
        "package_v8_must_not_embed_prior_predictions_or_results",
    ]:
        assert package_requirements[
            key
        ] is True, key

    assert decision8[
        "target_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA

    assert decision8[
        "target_freshness_consumed"
    ] is False

    assert decision8[
        "attempt_8_generation_started"
    ] is False

    assert decision8[
        "package_v8_created"
    ] is False

    #
    # 4. Package-v8 identity.
    #
    assert v8[
        "schema_version"
    ] == "8.0.0"

    assert v8[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ISOLATED_FRESH_"
        "HOLDOUT_GENERATION_PACKAGE_V8"
    )

    assert v8[
        "state"
    ] == (
        "READY_FOR_ISOLATED_GENERATION_ATTEMPT_8"
    )

    assert v8[
        "generation_attempt"
    ] == 8

    assert v8[
        "contains_holdout_cases"
    ] is False

    assert v8[
        "attempt_8_cases_generated"
    ] is False

    assert v8[
        "target_evaluator_executed"
    ] is False

    assert v8[
        "fresh_holdout_generation"
    ] is True

    assert v8[
        "protected_evaluation"
    ] is True

    assert v8[
        "authoritative"
    ] is False

    assert v8[
        "scientific_support_established"
    ] is False

    #
    # 5. Exact authorized v7 -> v8 delta.
    #
    mechanical = transform(
        deepcopy(v7)
    )

    mechanical[
        "schema_version"
    ] = "8.0.0"

    assert set(
        mechanical
    ) == set(
        v8
    )

    for key in sorted(v8):
        if key in AUTHORIZED_NONMECHANICAL_FIELDS:
            continue

        assert v8[
            key
        ] == mechanical[
            key
        ], (
            "Unauthorized non-mechanical "
            f"v7->v8 change: {key}"
        )

    #
    # 6. Frozen scientific/evaluator/scoring authority.
    #
    for key in FROZEN_AUTHORITY_KEYS:
        assert v8[
            key
        ] == v7[
            key
        ], key

    source_bindings = v8[
        "source_bindings"
    ]

    assert source_bindings[
        "generation_3_sha256"
    ] == EXPECTED_G3_SHA

    assert source_bindings[
        "preregistration_contract_sha256"
    ] == EXPECTED_PREREG_SHA

    assert source_bindings[
        "public_evaluator_contract_sha256"
    ] == EXPECTED_PUBLIC_CONTRACT_SHA

    assert source_bindings[
        "public_evaluator_contract_manifest_sha256"
    ] == EXPECTED_PUBLIC_CONTRACT_MANIFEST_SHA

    assert source_bindings[
        "frozen_target_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA

    #
    # 7. Attempt-8 generator input boundary.
    #
    assert v8[
        "allowed_generator_inputs"
    ] == [
        (
            "this Generation Package v8 as the complete Hetren Task 8 "
            "semantic and executable-interface input"
        ),
        (
            "the minimal governed handoff instruction accompanying the "
            "package attachment"
        ),
    ]

    forbidden_inputs = v8[
        "forbidden_generator_inputs"
    ]

    assert (
        "web search results or externally retrieved material "
        "during the generation session"
    ) in forbidden_inputs

    assert (
        "any prior Hetren generation attempt or generated holdout cases"
    ) in forbidden_inputs

    assert (
        "target Hetren semantic evaluator source or implementation"
    ) in forbidden_inputs

    assert (
        "Hetren Task 8 remediation history"
    ) in forbidden_inputs

    #
    # 8. Observable isolation replaces hidden-state introspection.
    #
    expected_isolation = {
        "gate_timing": "BEFORE_ANY_CASE_GENERATION",
        "fail_closed": True,
        "scope": "OBSERVABLE_CONVERSATION_INPUTS_ONLY",
        "package_v8_must_be_only_hetren_specific_attachment": True,
        "minimal_governed_handoff_must_be_only_other_hetren_specific_text": True,
        "conversation_must_have_zero_prior_messages_before_handoff": True,
        "additional_attachment_detected_required_value": False,
        "earlier_conversation_message_detected_required_value": False,
        "observable_nonpackage_hetren_context_detected_required_value": False,
        "generator_must_not_introspect_hidden_provider_state": True,
        "if_observable_boundary_violation": "ABORT_WITHOUT_GENERATING_CASES",
        "abort_output_filename": "generation_isolation_failure_attempt_8.json",
        "abort_output_must_contain_cases": False,
        "abort_does_not_consume_target_freshness": True,
        "generator_must_not_continue_after_abort": True,
    }

    assert v8[
        "generation_session_isolation_contract"
    ] == expected_isolation

    assert v8[
        "required_success_output_isolation_state"
    ] == {
        "observable_nonpackage_hetren_context_detected": False,
        "additional_attachment_detected": False,
        "earlier_conversation_message_detected": False,
        "isolation_gate_passed_before_case_generation": True,
    }

    assert v8[
        "expected_isolation_failure_output"
    ] == {
        "filename": "generation_isolation_failure_attempt_8.json",
        "artifact_type": "TASK_8_GEN3_GENERATION_ISOLATION_FAILURE_ATTEMPT_8",
        "state": "ABORTED_BEFORE_CASE_GENERATION",
        "generation_attempt": 8,
        "cases_must_be_absent": True,
        "target_evaluator_executed": False,
        "target_predictions_produced": False,
        "required_fields": [
            "schema_version",
            "artifact_type",
            "state",
            "generation_attempt",
            "generation_package_sha256",
            "generation_session_isolation",
            "abort_reason",
        ],
    }

    assert v8[
        "permitted_success_output_isolation_metadata"
    ] == {}

    #
    # 9. Attempt-8 attestations.
    #
    expected_attestations = {
        "received_generation_package_v8_as_only_hetren_specific_attachment": True,
        "received_only_minimal_governed_handoff_as_other_hetren_specific_text": True,
        "observable_input_gate_checked_before_case_generation": True,
        "no_observable_nonpackage_hetren_context_received": True,
        "no_additional_attachment_visible": True,
        "no_earlier_conversation_message_visible": True,
        "did_not_read_any_prior_hetren_generation_attempt": True,
        "did_not_read_target_hetren_evaluator_source": True,
        "did_not_read_target_hetren_evaluator_branch_conditions": True,
        "did_not_read_known_hetren_development_cases": True,
        "did_not_read_known_hetren_mutations": True,
        "did_not_read_prior_hetren_predictions_or_results": True,
        "did_not_read_hetren_remediation_history": True,
        "did_not_use_web_or_external_retrieval": True,
        "did_not_attempt_hidden_provider_state_introspection": True,
        "generated_all_54_cases_before_target_execution": True,
        "did_not_execute_or_simulate_target_evaluator": True,
        "completed_generator_output_preflight_before_returning_success_artifact": True,
        "generator_output_preflight_passed_all_required_assertions": True,
        "generation_package_sha256_copied_from_verified_handoff_filename_sha256": True,
    }

    assert v8[
        "required_generator_attestations"
    ] == expected_attestations

    #
    # 10. No-retrieval generation rules.
    #
    expected_rules = deepcopy(
        mechanical[
            "generation_rules"
        ]
    )

    old_rule_1 = (
        "External research may supply adversarial challenge patterns "
        "only; it may not override G3 semantics."
    )

    old_rule_2 = (
        "If external research is used, record stable locators and its "
        "limited challenge-generation role."
    )

    new_rule_1 = (
        "Attempt 8 generation must not use web search, external "
        "retrieval, plugins, connectors, or external tools."
    )

    new_rule_2 = (
        "The Attempt 8 success artifact external_sources field must "
        "be an empty list because external retrieval is prohibited "
        "in the governed generation session."
    )

    assert old_rule_1 in expected_rules
    assert old_rule_2 in expected_rules

    expected_rules[
        expected_rules.index(
            old_rule_1
        )
    ] = new_rule_1

    expected_rules[
        expected_rules.index(
            old_rule_2
        )
    ] = new_rule_2

    expected_rules[0] = (
        "Before generating any case, apply the observable conversation-input "
        "isolation gate. The conversation must contain zero prior user or "
        "assistant messages before the handoff, Package v8 must be the only "
        "attachment, and the minimal governed handoff must be the only other "
        "Hetren-specific text. If any earlier conversation message, any "
        "additional attachment, or any observable non-package Hetren-specific "
        "context is present, abort before case generation. Do not inspect or "
        "infer hidden provider state."
    )

    assert v8[
        "generation_rules"
    ] == expected_rules

    #
    # 11. Preserve v7 output-preflight hardening.
    #
    design = v8[
        "operationalized_design"
    ]

    expected_case_ids = [
        f"G3-H8-{number:03d}"
        for number in range(
            1,
            55,
        )
    ]

    expected_requirement_ids = [
        f"G3-BR-{number:03d}"
        for number in range(
            1,
            28,
        )
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
    ] == "G3-H8-NNN"

    assert design[
        "case_ids"
    ] == expected_case_ids

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

    preflight = v8[
        "generator_output_preflight_contract"
    ]

    assert preflight[
        "timing"
    ] == (
        "AFTER_ALL_CASES_ARE_GENERATED_AND_"
        "BEFORE_RETURNING_SUCCESS_OUTPUT"
    )

    assert preflight[
        "scope"
    ] == "STRUCTURAL_AND_CONTRACT_VALIDATION_ONLY"

    assert preflight[
        "target_evaluator_must_not_be_executed"
    ] is True

    assert preflight[
        "target_evaluator_must_not_be_simulated"
    ] is True

    assert preflight[
        "protected_outcomes_must_not_be_available"
    ] is True

    assertions = preflight[
        "assertions"
    ]

    assert assertions[
        "generation_package_sha256_matches_verified_handoff_filename_sha256"
    ] is True

    assert assertions[
        "case_count"
    ] == 54

    assert assertions[
        "case_ids_exactly"
    ] == expected_case_ids

    assert assertions[
        "case_ids_unique"
    ] is True

    assert assertions[
        "unique_case_id_count"
    ] == 54

    assert assertions[
        "must_accept_count"
    ] == 27

    assert assertions[
        "must_reject_count"
    ] == 27

    assert assertions[
        "primary_requirement_ids_exactly"
    ] == expected_requirement_ids

    assert assertions[
        "each_primary_requirement_exactly_one_must_accept_and_one_must_reject"
    ] is True

    assert assertions[
        "minimum_cases_per_environment"
    ] == 6

    assert assertions[
        "minimum_cross_requirement_interaction_cases"
    ] == 12

    assert assertions[
        "all_required_case_fields_present"
    ] is True

    assert assertions[
        "must_accept_expected_violation_codes_empty"
    ] is True

    assert assertions[
        "must_reject_expected_violation_codes_nonempty"
    ] is True

    assert assertions[
        "expected_violation_codes_from_primary_requirement_public_vocabulary_only"
    ] is True

    assert assertions[
        "facts_use_primary_requirement_public_interface_only"
    ] is True

    assert assertions[
        "target_evaluator_executed"
    ] is False

    assert assertions[
        "target_evaluator_simulated"
    ] is False

    output_schema = v8[
        "success_output_preflight_schema"
    ]

    assert output_schema[
        "field_name"
    ] == "generator_output_preflight"

    assert output_schema[
        "required"
    ] is True

    assert output_schema[
        "required_values"
    ][
        "case_count"
    ] == 54

    assert output_schema[
        "required_values"
    ][
        "unique_case_id_count"
    ] == 54

    assert output_schema[
        "required_values"
    ][
        "must_accept_count"
    ] == 27

    assert output_schema[
        "required_values"
    ][
        "must_reject_count"
    ] == 27

    assert output_schema[
        "required_values"
    ][
        "target_evaluator_executed"
    ] is False

    assert output_schema[
        "required_values"
    ][
        "target_evaluator_simulated"
    ] is False

    assert output_schema[
        "interaction_case_count_constraint"
    ] == "INTEGER_GREATER_THAN_OR_EQUAL_TO_12"

    #
    # 12. Attempt-8 success output contract.
    #
    output = v8[
        "expected_output"
    ]

    assert output[
        "filename"
    ] == "fresh_holdout_cases_attempt_8.json"

    assert output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_FRESH_ADVERSARIAL_"
        "HOLDOUT_CASES_ATTEMPT_8"
    )

    assert output[
        "state"
    ] == "GENERATED_NOT_EXECUTED"

    assert output[
        "generation_attempt"
    ] == 8

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

    required_output_fields = set(
        output[
            "required_top_level_fields"
        ]
    )

    for required in [
        "generation_package_sha256",
        "public_evaluator_contract_sha256",
        "generator_provenance",
        "generator_attestations",
        "external_sources",
        "cases",
        "generation_session_isolation",
        "generator_output_preflight",
    ]:
        assert required in required_output_fields

    #
    # 13. Handoff integrity.
    #
    handoff = v8[
        "handoff_integrity_contract"
    ]

    assert handoff[
        "external_handoff_filename_pattern"
    ] == (
        "generation_package_v8_"
        "<EXACT_64_LOWERCASE_HEX_SHA256_OF_PACKAGE_BYTES>.json"
    )

    assert handoff[
        "handoff_creator_must_verify_filename_sha256_suffix_matches_exact_package_bytes"
    ] is True

    assert handoff[
        "success_output_generation_package_sha256_source"
    ] == (
        "COPY_THE_EXACT_64_LOWERCASE_HEX_SHA256_SUFFIX_"
        "FROM_THE_ATTACHED_HANDOFF_FILENAME"
    )

    assert handoff[
        "success_output_generation_package_sha256_must_bind_exact_package_bytes"
    ] is True

    assert handoff[
        "embedded_source_hashes_must_not_be_used_as_generation_package_sha256"
    ] is True

    #
    # 14. No predecessor-evidence leakage.
    #
    package_text = V8_FILE.read_text()

    forbidden_values = [
        EXPECTED_ATTEMPT7_FAILURE_SHA,
        EXPECTED_ATTEMPT7_DISPOSITION_SHA,
        "generation_isolation_failure_attempt_7.json",
        "fresh_holdout_generation_attempt_7_disposition.json",
        "fresh_holdout_generation_package_v7.json",
        "fresh_holdout_generation_package_v7_manifest.json",
        "fresh_holdout_cases_attempt_7.json",
        "G3-H7-",
        "Package-v7",
        "Package v7",
        "generation_package_v7",
        "attempt_7_cases_generated",
    ]

    for value in forbidden_values:
        assert value not in package_text, value

    #
    # 15. Manifest binds exact repaired Package-v8 bytes and decision.
    #
    assert manifest8 == {
        "schema_version": "1.0.0",
        "artifact_type": "TASK_8_GEN3_FRESH_HOLDOUT_GENERATION_PACKAGE_V8_MANIFEST",
        "generation_attempt": 8,
        "package_path": (
            "tests/qualification/data/"
            "baseline_requirements_gen3/"
            "fresh_holdout_generation_package_v8.json"
        ),
        "package_sha256": EXPECTED_V8_SHA,
        "generation_environment_decision_path": (
            "tests/qualification/data/"
            "baseline_requirements_gen3/"
            "generation_environment_decision_attempt_8.json"
        ),
        "generation_environment_decision_sha256": EXPECTED_DECISION8_SHA,
        "contains_holdout_cases": False,
        "target_evaluator_executed": False,
        "target_freshness_consumed": False,
    }

    #
    # 16. Attempt-8 execution artifacts must still be absent.
    #
    forbidden_execution_artifacts = [
        "generation_environment_attestation_attempt_8.json",
        "generation_isolation_failure_attempt_8.json",
        "fresh_holdout_generation_attempt_8.json",
        "fresh_holdout_generation_attempt_8_disposition.json",
        "fresh_holdout_cases_attempt_8.json",
        "fresh_holdout_cases.json",
        "fresh_holdout_freeze_manifest.json",
        "fresh_holdout_first_run.json",
    ]

    existing = [
        name
        for name in forbidden_execution_artifacts
        if (
            DATA
            / name
        ).exists()
    ]

    assert not existing, existing

    #
    # 17. Final qualification output.
    #
    print("PASS: exact governed Package-v8 bytes")
    print("PASS: exact Package-v8 manifest bytes")
    print("PASS: Attempt-7 abort preserved as historical environment evidence")
    print("PASS: Attempt-7 established no package/evaluator/scientific defect")
    print("PASS: Attempt 8 is the authorized successor")
    print("PASS: C8A-1 generation-environment decision bound exactly")
    print("PASS: Temporary + Unpersonalized observable isolation required")
    print("PASS: zero prior messages required")
    print("PASS: Project/custom-GPT/plugin/connector context prohibited")
    print("PASS: Library auto-search off + local-disk package required")
    print("PASS: web/external retrieval prohibited")
    print("PASS: hidden-provider-state introspection prohibited")
    print("PASS: one-shot generator semantics preserved")
    print("PASS: exact authorized v7 -> v8 delta only")
    print("PASS: G3/preregistration/public evaluator/scoring authority unchanged")
    print("PASS: frozen target evaluator byte-identical")
    print("PASS: v7 output-preflight hardening preserved")
    print("PASS: exact G3-H8-001..054 required")
    print("PASS: 54 unique cases required")
    print("PASS: 27 MUST_ACCEPT / 27 MUST_REJECT required")
    print("PASS: every G3-BR-001..027 requires one accept + one reject")
    print("PASS: >=12 material interaction cases required")
    print("PASS: Package-v8 exact-byte SHA handoff enforced")
    print("PASS: Attempt-7 evidence embedded in Package-v8: NO")
    print("PASS: Attempt-8 execution artifacts absent")
    print("PASS: target freshness remains available")


if __name__ == "__main__":
    main()
