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

PACKAGE9_FILE = (
    DATA
    / "fresh_holdout_generation_package_v9.json"
)

PACKAGE10_FILE = (
    DATA
    / "fresh_holdout_generation_package_v10.json"
)

MANIFEST10_FILE = (
    DATA
    / "fresh_holdout_generation_package_v10_manifest.json"
)

DESIGN10_FILE = (
    DATA
    / "generation_successor_design_attempt_10.json"
)

DECISION10_FILE = (
    DATA
    / "generation_environment_decision_attempt_10.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)


EXPECTED_PACKAGE9_SHA = (
    "d43ae3a3362f216b86bd436ddfdbc109"
    "bbd2fd0506665ead314025b49264d876"
)

EXPECTED_PACKAGE10_SHA = (
    "f36f37aec79ce30c0585b5b07e8dee6e"
    "25cc8de570b23ca9a786faef1d7f8009"
)

EXPECTED_MANIFEST10_SHA = (
    "dc0893e5bb155cbcd8f9ad7822d99ece"
    "872eff6f1ca90f641049693fa77d8edd"
)

EXPECTED_DESIGN10_SHA = (
    "0dc572c1e0af16aee893dab05d398630"
    "86f6be9e64ce848cc65a7cd3c0f0adc3"
)

EXPECTED_DECISION10_SHA = (
    "d16b7fcbc61fd562700d7bfae3d0d73f"
    "3343a16b207a286966e04585242246d6"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)

REMOVED_RULE_SHA = (
    "423b0a423c29edecb9126c0c51a4b248"
    "c185aa1a4bd4299dd23c357268bee6ec"
)


def sha256_bytes(value):
    return hashlib.sha256(
        value
    ).hexdigest()


def sha256(path):
    return sha256_bytes(
        path.read_bytes()
    )


def load_json(path):
    return json.loads(
        path.read_text()
    )


def replace_text(value, replacements):
    for old, new in replacements:
        value = value.replace(
            old,
            new,
        )

    return value


def mechanical_transform(
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
                new_item = mechanical_transform(
                    item,
                    replacements,
                    generation_from,
                    generation_to,
                )

            result[new_key] = new_item

        return result

    if isinstance(value, list):
        return [
            mechanical_transform(
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


def reconstruct_expected_v10(
    package9,
    design10,
):
    replacements = [
        ("PACKAGE_V9", "PACKAGE_V10"),
        ("Package-v9", "Package-v10"),
        ("Package v9", "Package v10"),
        ("package_v9", "package_v10"),

        ("ATTEMPT_9", "ATTEMPT_10"),
        ("Attempt 9", "Attempt 10"),
        ("attempt_9", "attempt_10"),

        ("G3-H9-", "G3-H10-"),
    ]

    mechanical = mechanical_transform(
        package9,
        replacements,
        9,
        10,
    )

    mechanical[
        "schema_version"
    ] = "10.0.0"


    generator_input_use_contract = {
        "version": "1.0.0",

        "purpose": (
            "Define how the generator must use the supplied semantic "
            "inputs without asking the generator to determine or certify "
            "ChatGPT UI state, conversation isolation, attachment state, "
            "project membership, personalization state, memory state, "
            "or provider-internal state."
        ),

        "semantic_authority": (
            "Package v10 is the complete Hetren Task 8 semantic and "
            "executable-interface authority for this generation."
        ),

        "permitted_user_instruction": (
            "The minimal governed handoff accompanying Package v10."
        ),

        "orchestration_boundary": (
            "User-visible application-state isolation is governed and "
            "attested outside the generator. That external attestation "
            "is not generator input and must not be reconstructed, "
            "inferred, or adjudicated by the generator."
        ),

        "generator_must_not_adjudicate": [
            "conversation history",
            "attachment count",
            "project membership",
            "memory state",
            "personalization state",
            "provider system context",
            "provider safety context",
            "provider retention state",
            "other hidden or session metadata",
        ],

        "generator_must_not_seek_or_use": [
            "prior Task 8 generation attempts",
            "prior generated holdout cases",
            "prior Task 8 predictions or results",
            "prior Task 8 failure evidence",
            "prior Task 8 remediation history",
            "target semantic evaluator source or implementation",
            "target evaluator branch conditions",
            "known Task 8 development cases",
            "known Task 8 mutation cases",
            "non-package Hetren repository material",
            "web or external retrieval",
        ],

        "generator_must_not_abort_based_on_perceived_chat_ui_or_hidden_state":
            True,

        "generator_must_not_emit_isolation_pass_metadata":
            True,

        "generator_must_not_emit_isolation_failure_artifact":
            True,

        "target_evaluator_execution_during_generation":
            False,

        "target_evaluator_simulation_during_generation":
            False,
    }


    expected = {}

    for key, value in mechanical.items():

        if key == "generator_isolation_rule":

            expected[
                "generator_input_use_contract"
            ] = generator_input_use_contract

            continue

        if key in {
            "generation_session_isolation_contract",
            "required_success_output_isolation_state",
            "expected_isolation_failure_output",
            "permitted_success_output_isolation_metadata",
        }:
            continue

        expected[key] = deepcopy(
            value
        )


    expected[
        "freshness_scope"
    ] = (
        "Attempt 10 is intended to be fresh relative to the hidden "
        "target implementation and non-package Hetren development and "
        "qualification evidence under an externally attested "
        "user-visible application-level generation boundary. The "
        "generator does not adjudicate conversation/UI isolation or "
        "provider-internal state. This does not claim complete "
        "model-visible context knowledge, provider-internal "
        "statelessness, model-pretraining nonexposure, independent "
        "third-party evaluation, or external scientific replication."
    )


    old_rules = deepcopy(
        mechanical[
            "generation_rules"
        ]
    )

    assert old_rules[
        0
    ].startswith(
        "Before generating any case, apply the observable "
        "conversation-input isolation gate."
    )

    expected[
        "generation_rules"
    ] = [
        (
            "Use Package v10 as the complete Hetren Task 8 semantic "
            "and executable-interface authority for generation."
        ),

        (
            "Do not search for, infer, describe, certify, or adjudicate "
            "conversation history, attachment count, project membership, "
            "memory state, personalization state, provider system "
            "context, provider safety context, provider retention state, "
            "or other hidden/session metadata."
        ),

        (
            "Do not seek or use prior Task 8 attempts, prior generated "
            "cases, prior predictions or results, failure evidence, "
            "remediation history, target evaluator source or branch "
            "logic, known development or mutation cases, or other "
            "non-package Hetren repository material."
        ),
    ] + old_rules[1:]


    old_attestations = deepcopy(
        mechanical[
            "required_generator_attestations"
        ]
    )

    remove_attestations = {
        "received_generation_package_v10_as_only_hetren_specific_attachment",
        "received_only_minimal_governed_handoff_as_other_hetren_specific_text",
        "observable_input_gate_checked_before_case_generation",
        "no_observable_nonpackage_hetren_context_received",
        "no_additional_attachment_visible",
        "no_earlier_conversation_message_visible",

        "did_not_read_any_prior_hetren_generation_attempt",
        "did_not_read_target_hetren_evaluator_source",
        "did_not_read_target_hetren_evaluator_branch_conditions",
        "did_not_read_known_hetren_development_cases",
        "did_not_read_known_hetren_mutations",
        "did_not_read_prior_hetren_predictions_or_results",
        "did_not_read_hetren_remediation_history",

        "did_not_attempt_hidden_provider_state_introspection",
    }

    assert remove_attestations.issubset(
        old_attestations.keys()
    )

    remaining_attestations = {
        key: value
        for key, value in old_attestations.items()
        if key not in remove_attestations
    }

    expected[
        "required_generator_attestations"
    ] = {
        "used_generation_package_v10_as_complete_task_8_semantic_and_executable_interface_authority":
            True,

        "did_not_seek_or_use_nonpackage_task_8_history_or_target_evaluator_implementation":
            True,

        "did_not_adjudicate_chat_history_attachment_project_memory_personalization_or_provider_internal_state":
            True,

        **remaining_attestations,
    }


    expected_output = deepcopy(
        mechanical[
            "expected_output"
        ]
    )

    required_fields = expected_output[
        "required_top_level_fields"
    ]

    assert required_fields.count(
        "generation_session_isolation"
    ) == 1

    expected_output[
        "required_top_level_fields"
    ] = [
        field
        for field in required_fields
        if field != "generation_session_isolation"
    ]

    expected[
        "expected_output"
    ] = expected_output


    claim_limits = deepcopy(
        mechanical[
            "claim_limits"
        ]
    )

    claim_limits.update(
        {
            "generation_does_not_establish_provider_internal_statelessness":
                True,

            "generation_does_not_establish_complete_model_visible_context":
                True,

            "user_visible_environment_isolation_is_orchestration_attested_not_generator_self_audited":
                True,
        }
    )

    expected[
        "claim_limits"
    ] = claim_limits


    hardening = deepcopy(
        mechanical[
            "environment_self_consistency_preflight_contract"
        ]
    )

    matching = [
        rule
        for rule in hardening[
            "rules"
        ]
        if sha256_bytes(
            rule.encode(
                "utf-8"
            )
        ) == REMOVED_RULE_SHA
    ]

    assert len(
        matching
    ) == 1

    hardening[
        "rules"
    ] = [
        rule
        for rule in hardening[
            "rules"
        ]
        if rule != matching[0]
    ]

    assert hardening == design10[
        "generic_environment_self_consistency_hardening"
    ]

    expected[
        "environment_self_consistency_preflight_contract"
    ] = hardening

    return mechanical, expected


def main():
    #
    # Exact immutable byte boundary.
    #
    assert sha256(
        PACKAGE9_FILE
    ) == EXPECTED_PACKAGE9_SHA

    assert sha256(
        PACKAGE10_FILE
    ) == EXPECTED_PACKAGE10_SHA

    assert sha256(
        MANIFEST10_FILE
    ) == EXPECTED_MANIFEST10_SHA

    assert sha256(
        DESIGN10_FILE
    ) == EXPECTED_DESIGN10_SHA

    assert sha256(
        DECISION10_FILE
    ) == EXPECTED_DECISION10_SHA

    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA


    package9 = load_json(
        PACKAGE9_FILE
    )

    package10 = load_json(
        PACKAGE10_FILE
    )

    manifest10 = load_json(
        MANIFEST10_FILE
    )

    design10 = load_json(
        DESIGN10_FILE
    )

    decision10 = load_json(
        DECISION10_FILE
    )


    #
    # Governance authority.
    #
    assert design10[
        "generation_attempt"
    ] == 10

    assert design10[
        "attempt_10_design_state"
    ][
        "successor_design_complete"
    ] is True

    assert decision10[
        "generation_attempt"
    ] == 10

    assert decision10[
        "decision_state"
    ][
        "package_v10_construction_authorized"
    ] is True

    assert decision10[
        "decision_state"
    ][
        "protected_generation_authorized"
    ] is False

    assert decision10[
        "package_v10_authorized_transformation"
    ][
        "removed_rule_sha256"
    ] == REMOVED_RULE_SHA


    #
    # Independent reconstruction.
    #
    mechanical, expected = (
        reconstruct_expected_v10(
            package9,
            design10,
        )
    )

    expected_bytes = (
        json.dumps(
            expected,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    actual_bytes = (
        PACKAGE10_FILE.read_bytes()
    )

    assert expected_bytes == actual_bytes

    assert sha256_bytes(
        expected_bytes
    ) == EXPECTED_PACKAGE10_SHA


    #
    # Exact non-mechanical change surface.
    #
    all_keys = set(
        mechanical
    ) | set(
        package10
    )

    modified = {
        key
        for key in all_keys
        if mechanical.get(
            key,
            object(),
        ) != package10.get(
            key,
            object(),
        )
    }

    expected_modified = {
        "generator_isolation_rule",
        "generator_input_use_contract",
        "freshness_scope",
        "generation_rules",
        "required_generator_attestations",
        "expected_output",
        "claim_limits",
        "generation_session_isolation_contract",
        "required_success_output_isolation_state",
        "expected_isolation_failure_output",
        "permitted_success_output_isolation_metadata",
        "environment_self_consistency_preflight_contract",
    }

    assert modified == expected_modified


    #
    # Package identity.
    #
    assert package10[
        "schema_version"
    ] == "10.0.0"

    assert package10[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ISOLATED_FRESH_HOLDOUT_"
        "GENERATION_PACKAGE_V10"
    )

    assert package10[
        "state"
    ] == (
        "READY_FOR_ISOLATED_GENERATION_ATTEMPT_10"
    )

    assert package10[
        "generation_attempt"
    ] == 10

    assert package10[
        "contains_holdout_cases"
    ] is False

    assert package10[
        "target_evaluator_executed"
    ] is False

    assert package10[
        "attempt_10_cases_generated"
    ] is False


    #
    # Frozen science / public executable interface.
    #
    for key in [
        "source_bindings",
        "authority_order",
        "embedded_generation_3_requirements",
        "embedded_preregistration_contract",
        "embedded_public_evaluator_contract",
    ]:
        assert package10[
            key
        ] == package9[
            key
        ], key

    assert package10[
        "source_bindings"
    ][
        "generation_3_sha256"
    ] == (
        "d01e39439d601fd28ed1b15cdb618214"
        "a0e5d84b2f88c142dd020dbf80930217"
    )

    assert package10[
        "source_bindings"
    ][
        "preregistration_contract_sha256"
    ] == (
        "4b62eb6feb6b2085cb8a90b2153e4544"
        "9749ca520da277782a9a6bdcac35f037"
    )

    assert package10[
        "source_bindings"
    ][
        "public_evaluator_contract_sha256"
    ] == (
        "70a61f7ee6a3f3f95614ad1ebacf3479"
        "8377062b3f1cd8a30a0c1246ffc4250c"
    )

    assert package10[
        "source_bindings"
    ][
        "public_evaluator_contract_manifest_sha256"
    ] == (
        "08ee63f8e2f277f52d7a6d44106b2ff5"
        "8d806d3ea317aab9cf7d8b78052c684e"
    )

    assert package10[
        "source_bindings"
    ][
        "frozen_target_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA


    #
    # Exact H10 identity and balance contract.
    #
    ids = [
        f"G3-H10-{i:03d}"
        for i in range(
            1,
            55,
        )
    ]

    assert package10[
        "operationalized_design"
    ][
        "case_count"
    ] == 54

    assert package10[
        "operationalized_design"
    ][
        "total_must_accept"
    ] == 27

    assert package10[
        "operationalized_design"
    ][
        "total_must_reject"
    ] == 27

    assert package10[
        "operationalized_design"
    ][
        "case_ids"
    ] == ids

    assert package10[
        "case_schema"
    ][
        "id_format"
    ] == "G3-H10-NNN"

    assert package10[
        "generator_output_preflight_contract"
    ][
        "assertions"
    ][
        "case_ids_exactly"
    ] == ids

    assert package10[
        "generator_output_preflight_contract"
    ][
        "assertions"
    ][
        "case_count"
    ] == 54

    assert package10[
        "generator_output_preflight_contract"
    ][
        "assertions"
    ][
        "must_accept_count"
    ] == 27

    assert package10[
        "generator_output_preflight_contract"
    ][
        "assertions"
    ][
        "must_reject_count"
    ] == 27

    assert package10[
        "generator_output_preflight_contract"
    ][
        "assertions"
    ][
        "minimum_cases_per_environment"
    ] == 6

    assert package10[
        "generator_output_preflight_contract"
    ][
        "assertions"
    ][
        "minimum_cross_requirement_interaction_cases"
    ] == 12


    #
    # Generator-side UI isolation adjudication must be absent.
    #
    for key in [
        "generator_isolation_rule",
        "generation_session_isolation_contract",
        "required_success_output_isolation_state",
        "expected_isolation_failure_output",
        "permitted_success_output_isolation_metadata",
    ]:
        assert key not in package10, key

    assert (
        "generator_input_use_contract"
        in package10
    )

    input_contract = package10[
        "generator_input_use_contract"
    ]

    assert input_contract[
        "generator_must_not_abort_based_on_perceived_chat_ui_or_hidden_state"
    ] is True

    assert input_contract[
        "generator_must_not_emit_isolation_pass_metadata"
    ] is True

    assert input_contract[
        "generator_must_not_emit_isolation_failure_artifact"
    ] is True

    assert input_contract[
        "target_evaluator_execution_during_generation"
    ] is False

    assert input_contract[
        "target_evaluator_simulation_during_generation"
    ] is False


    #
    # Success output must not ask for generator-reported
    # session-isolation state.
    #
    assert (
        "generation_session_isolation"
        not in package10[
            "expected_output"
        ][
            "required_top_level_fields"
        ]
    )

    assert package10[
        "expected_output"
    ][
        "filename"
    ] == (
        "fresh_holdout_cases_attempt_10.json"
    )

    assert package10[
        "expected_output"
    ][
        "generation_attempt"
    ] == 10


    #
    # Old self-audit attestations must be absent.
    #
    forbidden_attestations = {
        "received_generation_package_v10_as_only_hetren_specific_attachment",
        "received_only_minimal_governed_handoff_as_other_hetren_specific_text",
        "observable_input_gate_checked_before_case_generation",
        "no_observable_nonpackage_hetren_context_received",
        "no_additional_attachment_visible",
        "no_earlier_conversation_message_visible",
        "did_not_read_any_prior_hetren_generation_attempt",
        "did_not_read_target_hetren_evaluator_source",
        "did_not_read_target_hetren_evaluator_branch_conditions",
        "did_not_read_known_hetren_development_cases",
        "did_not_read_known_hetren_mutations",
        "did_not_read_prior_hetren_predictions_or_results",
        "did_not_read_hetren_remediation_history",
        "did_not_attempt_hidden_provider_state_introspection",
    }

    attestations = package10[
        "required_generator_attestations"
    ]

    assert not (
        forbidden_attestations
        & set(
            attestations
        )
    )

    assert attestations[
        "used_generation_package_v10_as_complete_task_8_semantic_and_executable_interface_authority"
    ] is True

    assert attestations[
        "did_not_seek_or_use_nonpackage_task_8_history_or_target_evaluator_implementation"
    ] is True

    assert attestations[
        "did_not_adjudicate_chat_history_attachment_project_memory_personalization_or_provider_internal_state"
    ] is True

    assert attestations[
        "did_not_use_web_or_external_retrieval"
    ] is True

    assert attestations[
        "generated_all_54_cases_before_target_execution"
    ] is True

    assert attestations[
        "did_not_execute_or_simulate_target_evaluator"
    ] is True


    #
    # Generic environment consistency hardening.
    #
    hardening = package10[
        "environment_self_consistency_preflight_contract"
    ]

    assert hardening == design10[
        "generic_environment_self_consistency_hardening"
    ]

    assert hardening[
        "target_evaluator_execution_required"
    ] is False

    assert hardening[
        "target_evaluator_simulation_required"
    ] is False

    assert hardening[
        "deterministic_preflight"
    ][
        "mismatch_count_required_value"
    ] == 0

    assert hardening[
        "semantic_preflight"
    ][
        "required_result"
    ] == (
        "NO_INTERNAL_ENVIRONMENT_CONTRADICTION"
    )

    assert all(
        sha256_bytes(
            rule.encode(
                "utf-8"
            )
        ) != REMOVED_RULE_SHA
        for rule in hardening[
            "rules"
        ]
    )

    hardening_text = json.dumps(
        hardening,
        sort_keys=True,
    )

    assert "G3-BR-027" not in hardening_text
    assert "G3-H8-" not in hardening_text
    assert "G3-H9-" not in hardening_text


    #
    # Structural output preflight remains non-target.
    #
    preflight = package10[
        "generator_output_preflight_contract"
    ]

    assert preflight[
        "scope"
    ] == (
        "STRUCTURAL_AND_CONTRACT_VALIDATION_ONLY"
    )

    assert preflight[
        "target_evaluator_must_not_be_executed"
    ] is True

    assert preflight[
        "target_evaluator_must_not_be_simulated"
    ] is True

    assert preflight[
        "protected_outcomes_must_not_be_available"
    ] is True

    assert preflight[
        "assertions"
    ][
        "target_evaluator_executed"
    ] is False

    assert preflight[
        "assertions"
    ][
        "target_evaluator_simulated"
    ] is False

    assert preflight[
        "assertions"
    ][
        "environment_self_consistency_checked"
    ] is True

    assert preflight[
        "assertions"
    ][
        "environment_self_consistency_passed"
    ] is True

    assert preflight[
        "assertions"
    ][
        "environment_binding_token_mismatch_count"
    ] == 0

    assert preflight[
        "assertions"
    ][
        "semantic_environment_consistency_review_passed"
    ] is True


    #
    # Success-output preflight evidence stays required.
    #
    output_schema = package10[
        "success_output_preflight_schema"
    ]

    assert output_schema[
        "required"
    ] is True

    assert output_schema[
        "field_name"
    ] == "generator_output_preflight"

    required_values = output_schema[
        "required_values"
    ]

    assert required_values[
        "case_count"
    ] == 54

    assert required_values[
        "unique_case_id_count"
    ] == 54

    assert required_values[
        "must_accept_count"
    ] == 27

    assert required_values[
        "must_reject_count"
    ] == 27

    assert required_values[
        "target_evaluator_executed"
    ] is False

    assert required_values[
        "target_evaluator_simulated"
    ] is False

    assert required_values[
        "environment_self_consistency_passed"
    ] is True

    assert required_values[
        "environment_binding_token_mismatch_count"
    ] == 0

    assert output_schema[
        "interaction_case_count_constraint"
    ] == (
        "INTEGER_GREATER_THAN_OR_EQUAL_TO_12"
    )


    #
    # Handoff integrity mechanically advanced to v10.
    #
    handoff = package10[
        "handoff_integrity_contract"
    ]

    assert handoff[
        "external_handoff_filename_pattern"
    ] == (
        "generation_package_v10_"
        "<EXACT_64_LOWERCASE_HEX_SHA256_OF_PACKAGE_BYTES>.json"
    )

    assert handoff[
        "handoff_creator_must_verify_filename_sha256_suffix_matches_exact_package_bytes"
    ] is True

    assert handoff[
        "success_output_generation_package_sha256_must_bind_exact_package_bytes"
    ] is True

    assert (
        "Package-v10"
        in handoff[
            "reason"
        ]
    )


    #
    # Historical/governance evidence must not leak into
    # generator package.
    #
    serialized = json.dumps(
        package10,
        sort_keys=True,
    )

    forbidden_strings = [
        "generation_isolation_failure_attempt_9.json",
        "fresh_holdout_cases_attempt_9.json",
        "fresh_holdout_generation_attempt_9_disposition.json",
        "generation_environment_attestation_attempt_9.json",
        "generation_isolation_investigation_attempt_9.json",
        "generation_successor_environment_comparison_attempt_10.json",
        "generation_api_capability_preflight_attempt_10_disposition.json",
        "generation_successor_design_attempt_10.json",
        "generation_environment_decision_attempt_10.json",

        "957610200d7e1975052673e4ce5202edde12dea86b59d32fad7e55e70fc07b8e",
        "293a6be70c8afa1d1913f9a668d191f1cbdccb7bc222ae10487bad535eaf7c56",
        "36b4bcdbabefaa146bb0a1b6bbc6bd498308f2eeda502892d8114e7d35808886",
        "857af7583a1c95eedb628b45151dcb689153b72fdc4f3673f748f21003078577",
        "f40edb522176d7170834ad8c3592407466cee104341402ba4a2158c1656bdc99",
        "c31b3de95ff7f11e5353d8bd1c8a70850b52e5806a2982ed6cab11493a8955df",
        "0dc572c1e0af16aee893dab05d39863086f6be9e64ce848cc65a7cd3c0f0adc3",
        "d16b7fcbc61fd562700d7bfae3d0d73f3343a16b207a286966e04585242246d6",
        REMOVED_RULE_SHA,

        "G3-H9-",
        "Package v9",
        "Package-v9",
    ]

    for value in forbidden_strings:
        assert value not in serialized, value


    #
    # Claim limits reflect narrower externally attested scope.
    #
    claims = package10[
        "claim_limits"
    ]

    assert claims[
        "generation_does_not_establish_provider_internal_statelessness"
    ] is True

    assert claims[
        "generation_does_not_establish_complete_model_visible_context"
    ] is True

    assert claims[
        "user_visible_environment_isolation_is_orchestration_attested_not_generator_self_audited"
    ] is True


    #
    # Manifest validation.
    #
    assert manifest10[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_FRESH_HOLDOUT_"
        "GENERATION_PACKAGE_V10_MANIFEST"
    )

    assert manifest10[
        "state"
    ] == (
        "PACKAGE_V10_CONSTRUCTED_NOT_GENERATED"
    )

    assert manifest10[
        "generation_attempt"
    ] == 10

    assert manifest10[
        "package"
    ][
        "sha256"
    ] == EXPECTED_PACKAGE10_SHA

    assert manifest10[
        "package"
    ][
        "size_bytes"
    ] == len(
        PACKAGE10_FILE.read_bytes()
    )

    assert manifest10[
        "package"
    ][
        "size_bytes"
    ] == 92463

    assert manifest10[
        "package"
    ][
        "schema_version"
    ] == "10.0.0"

    assert manifest10[
        "lineage"
    ][
        "parent_package_v9_sha256"
    ] == EXPECTED_PACKAGE9_SHA

    assert manifest10[
        "lineage"
    ][
        "attempt_10_successor_design_sha256"
    ] == EXPECTED_DESIGN10_SHA

    assert manifest10[
        "lineage"
    ][
        "attempt_10_environment_decision_sha256"
    ] == EXPECTED_DECISION10_SHA

    assert manifest10[
        "lineage"
    ][
        "frozen_target_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA

    authorized = manifest10[
        "authorized_transformation"
    ]

    assert authorized[
        "mechanical_attempt_9_to_10_identity_substitution"
    ] is True

    assert authorized[
        "generator_side_ui_isolation_self_audit_removed"
    ] is True

    assert authorized[
        "orchestration_side_attestation_remains_external_to_package"
    ] is True

    assert authorized[
        "non_self_auditing_generator_input_use_contract_added"
    ] is True

    assert authorized[
        "generator_isolation_success_metadata_removed"
    ] is True

    assert authorized[
        "generator_isolation_failure_contract_removed"
    ] is True

    assert authorized[
        "requirement_specific_environment_hardening_rules_removed"
    ] == 1

    assert authorized[
        "removed_rule_sha256"
    ] == REMOVED_RULE_SHA

    assert authorized[
        "generic_environment_self_consistency_hardening_preserved"
    ] is True

    assert authorized[
        "structural_generator_output_preflight_preserved"
    ] is True

    assert authorized[
        "handoff_integrity_contract_preserved"
    ] is True


    frozen_manifest = manifest10[
        "frozen_contracts"
    ]

    for key, value in frozen_manifest.items():
        assert value == package10[
            "source_bindings"
        ][
            key
        ], key


    identity = manifest10[
        "generation_identity"
    ]

    assert identity[
        "case_count"
    ] == 54

    assert identity[
        "must_accept_count"
    ] == 27

    assert identity[
        "must_reject_count"
    ] == 27

    assert identity[
        "first_case_id"
    ] == "G3-H10-001"

    assert identity[
        "last_case_id"
    ] == "G3-H10-054"

    assert identity[
        "success_output_filename"
    ] == (
        "fresh_holdout_cases_attempt_10.json"
    )


    #
    # Manifest is a construction-time snapshot; it must not be
    # retroactively mutated merely because this checker now exists.
    #
    construction = manifest10[
        "construction_state"
    ]

    assert construction[
        "package_constructed"
    ] is True

    assert construction[
        "independent_package_checker_created"
    ] is False

    assert construction[
        "independent_package_validation_completed"
    ] is False

    assert construction[
        "local_disk_handoff_created"
    ] is False

    assert construction[
        "pre_generation_environment_attestation_created"
    ] is False

    assert construction[
        "generator_chat_started"
    ] is False

    assert construction[
        "first_generator_message_sent"
    ] is False

    assert construction[
        "cases_generated"
    ] is False

    assert construction[
        "target_evaluator_executed"
    ] is False

    assert construction[
        "target_evaluator_simulated"
    ] is False

    assert construction[
        "target_predictions_produced"
    ] is False

    assert construction[
        "target_freshness_consumed"
    ] is False

    assert manifest10[
        "next_required_gate"
    ] == (
        "INDEPENDENT_PACKAGE_V10_VALIDATION_BEFORE_HANDOFF"
    )


    #
    # Environment decision still prohibits protected generation.
    #
    state = decision10[
        "decision_state"
    ]

    assert state[
        "package_v10_construction_authorized"
    ] is True

    assert state[
        "package_v10_created"
    ] is False

    assert state[
        "attempt_10_attestation_created"
    ] is False

    assert state[
        "attempt_10_generator_chat_started"
    ] is False

    assert state[
        "attempt_10_first_message_sent"
    ] is False

    assert state[
        "attempt_10_cases_generated"
    ] is False

    assert state[
        "target_evaluator_executed"
    ] is False

    assert state[
        "target_evaluator_simulated"
    ] is False

    assert state[
        "target_predictions_produced"
    ] is False

    assert state[
        "target_freshness_consumed"
    ] is False

    assert state[
        "protected_generation_authorized"
    ] is False


    #
    # Protected execution artifacts must still be absent.
    #
    forbidden_files = [
        DATA
        / "generation_environment_attestation_attempt_10.json",

        DATA
        / "generation_isolation_failure_attempt_10.json",

        DATA
        / "fresh_holdout_cases_attempt_10.json",

        DATA
        / "fresh_holdout_generation_attempt_10_disposition.json",

        DATA
        / "fresh_holdout_first_run.json",

        DATA
        / "fresh_holdout_freeze_manifest.json",
    ]

    existing = [
        str(path)
        for path in forbidden_files
        if path.exists()
    ]

    assert not existing, existing


    print("PASS: exact Package-v9 parent bytes")
    print("PASS: exact Package-v10 bytes")
    print("PASS: exact Package-v10 manifest bytes")
    print("PASS: frozen Attempt-10 design and decision")
    print("PASS: frozen target evaluator hash")
    print("PASS: independent v9 -> v10 reconstruction")
    print("PASS: reconstructed serialized bytes equal Package v10 byte-for-byte")
    print("PASS: authorized non-mechanical change surface is exact")
    print("PASS: G3 requirements unchanged")
    print("PASS: preregistration contract unchanged")
    print("PASS: public evaluator interface unchanged")
    print("PASS: exact G3-H10-001..054 identity")
    print("PASS: 54 / 27 / 27 generation contract preserved")
    print("PASS: environment and interaction minimums preserved")
    print("PASS: generator-side conversation isolation gate absent")
    print("PASS: generator-side isolation failure contract absent")
    print("PASS: generator-reported session isolation output absent")
    print("PASS: UI/input-state self-attestations absent")
    print("PASS: non-self-auditing input-use contract present")
    print("PASS: generic environment consistency hardening exact")
    print("PASS: requirement-specific hardening rule absent")
    print("PASS: deterministic mismatch requirement remains zero")
    print("PASS: semantic environment review remains required")
    print("PASS: target cannot execute or be simulated during generation/preflight")
    print("PASS: structural output preflight preserved")
    print("PASS: SHA-suffixed Package-v10 handoff contract preserved")
    print("PASS: predecessor/governance evidence absent from generator package")
    print("PASS: manifest binds exact Package-v10 bytes")
    print("PASS: manifest remains immutable construction-time snapshot")
    print("PASS: protected Attempt-10 generation still unauthorized")
    print("PASS: no Attempt-10 execution artifact exists")
    print("PASS: target freshness remains available")
    print()
    print("===== PACKAGE-V10 INDEPENDENT CHECK PASS =====")


if __name__ == "__main__":
    main()
