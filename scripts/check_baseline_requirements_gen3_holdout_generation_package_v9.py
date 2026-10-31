#!/usr/bin/env python3

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

V8_FILE = (
    DATA
    / "fresh_holdout_generation_package_v8.json"
)

V9_FILE = (
    DATA
    / "fresh_holdout_generation_package_v9.json"
)

V9_MANIFEST_FILE = (
    DATA
    / "fresh_holdout_generation_package_v9_manifest.json"
)

ATTEMPT8_DISPOSITION_FILE = (
    DATA
    / "fresh_holdout_generation_attempt_8_disposition.json"
)

DESIGN9_FILE = (
    DATA
    / "generation_successor_design_attempt_9.json"
)

DECISION9_FILE = (
    DATA
    / "generation_environment_decision_attempt_9.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)


EXPECTED_V8_SHA = (
    "383753fc816ea1a6a2ffb264fb0d2325"
    "f0b45276fc74c75a902c7f090908b02a"
)

EXPECTED_V9_SHA = (
    "d43ae3a3362f216b86bd436ddfdbc109"
    "bbd2fd0506665ead314025b49264d876"
)

EXPECTED_V9_MANIFEST_SHA = (
    "9d6cbb0ec10de760d10efb4b11471bf6"
    "74a0dd382f907bd948472ed32fd4a6bd"
)

EXPECTED_ATTEMPT8_DISPOSITION_SHA = (
    "bc20d26f111c27eef3e45bf99f931675"
    "35e14ca0f221dd76c15099fb2814a1eb"
)

EXPECTED_DESIGN9_SHA = (
    "823c14d063e2a326e67fdd1a78261ca3"
    "581948341d77f1af2eaf6d93a5afd246"
)

EXPECTED_DECISION9_SHA = (
    "6095bbb82b994cda04cc859ec9efa621"
    "29c323451a8e58015a1c910a3a01ffe5"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)


FORWARD_REPLACEMENTS = [
    ("generation_package_v8", "generation_package_v9"),
    ("package_v8", "package_v9"),
    ("PACKAGE_V8", "PACKAGE_V9"),
    ("Generation Package v8", "Generation Package v9"),
    ("Package v8", "Package v9"),
    ("Package-v8", "Package-v9"),
    ("package-v8", "package-v9"),
    ("attempt_8", "attempt_9"),
    ("ATTEMPT_8", "ATTEMPT_9"),
    ("Attempt 8", "Attempt 9"),
    ("attempt 8", "attempt 9"),
    ("G3-H8", "G3-H9"),
]

REVERSE_REPLACEMENTS = [
    ("generation_package_v9", "generation_package_v8"),
    ("package_v9", "package_v8"),
    ("PACKAGE_V9", "PACKAGE_V8"),
    ("Generation Package v9", "Generation Package v8"),
    ("Package v9", "Package v8"),
    ("Package-v9", "Package-v8"),
    ("package-v9", "package-v8"),
    ("attempt_9", "attempt_8"),
    ("ATTEMPT_9", "ATTEMPT_8"),
    ("Attempt 9", "Attempt 8"),
    ("attempt 9", "attempt 8"),
    ("G3-H9", "G3-H8"),
]


NEW_GENERATION_RULE = (
    "Before returning the single final success artifact, execute "
    "environment_self_consistency_preflight_contract without "
    "executing or simulating the target evaluator. Do not return "
    "success unless every required environment self-consistency "
    "check passes."
)


ENVIRONMENT_ASSERTIONS = {
    "environment_self_consistency_checked": True,
    "environment_self_consistency_passed": True,
    "environment_binding_token_mismatch_count": 0,
    "semantic_environment_consistency_review_passed": True,
}


def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


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


def transform(
    value,
    replacements,
    from_attempt,
    to_attempt,
):
    if isinstance(value, dict):
        out = {}

        for key, item in value.items():
            new_key = replace_text(
                key,
                replacements,
            )

            if (
                new_key == "generation_attempt"
                and item == from_attempt
            ):
                out[new_key] = to_attempt
            else:
                out[new_key] = transform(
                    item,
                    replacements,
                    from_attempt,
                    to_attempt,
                )

        return out

    if isinstance(value, list):
        return [
            transform(
                item,
                replacements,
                from_attempt,
                to_attempt,
            )
            for item in value
        ]

    if isinstance(value, str):
        return replace_text(
            value,
            replacements,
        )

    return value


def build_expected_v9(v8, design9):
    expected = transform(
        deepcopy(v8),
        FORWARD_REPLACEMENTS,
        8,
        9,
    )

    expected["schema_version"] = "9.0.0"

    expected[
        "environment_self_consistency_preflight_contract"
    ] = deepcopy(
        design9[
            "generic_environment_self_consistency_hardening"
        ]
    )

    expected[
        "generation_rules"
    ].append(
        NEW_GENERATION_RULE
    )

    expected[
        "required_generator_attestations"
    ][
        "completed_environment_self_consistency_preflight_before_returning_success_artifact"
    ] = True

    expected[
        "required_generator_attestations"
    ][
        "environment_self_consistency_preflight_passed_all_required_assertions"
    ] = True

    expected[
        "generator_output_preflight_contract"
    ][
        "assertions"
    ].update(
        ENVIRONMENT_ASSERTIONS
    )

    schema = expected[
        "success_output_preflight_schema"
    ]

    for field in ENVIRONMENT_ASSERTIONS:
        schema[
            "required_fields"
        ].append(field)

    schema[
        "required_values"
    ].update(
        ENVIRONMENT_ASSERTIONS
    )

    return expected


def reconstruct_v8(v9):
    candidate = deepcopy(v9)

    candidate.pop(
        "environment_self_consistency_preflight_contract"
    )

    assert (
        candidate["generation_rules"][-1]
        == NEW_GENERATION_RULE
    )

    candidate[
        "generation_rules"
    ].pop()

    candidate[
        "required_generator_attestations"
    ].pop(
        "completed_environment_self_consistency_preflight_before_returning_success_artifact"
    )

    candidate[
        "required_generator_attestations"
    ].pop(
        "environment_self_consistency_preflight_passed_all_required_assertions"
    )

    for key in ENVIRONMENT_ASSERTIONS:
        candidate[
            "generator_output_preflight_contract"
        ][
            "assertions"
        ].pop(key)

        candidate[
            "success_output_preflight_schema"
        ][
            "required_fields"
        ].remove(key)

        candidate[
            "success_output_preflight_schema"
        ][
            "required_values"
        ].pop(key)

    reconstructed = transform(
        candidate,
        REVERSE_REPLACEMENTS,
        9,
        8,
    )

    reconstructed[
        "schema_version"
    ] = "8.0.0"

    return reconstructed


def main():
    #
    # Exact bytes.
    #
    assert sha256(V8_FILE) == EXPECTED_V8_SHA
    assert sha256(V9_FILE) == EXPECTED_V9_SHA

    assert (
        sha256(V9_MANIFEST_FILE)
        == EXPECTED_V9_MANIFEST_SHA
    )

    assert (
        sha256(ATTEMPT8_DISPOSITION_FILE)
        == EXPECTED_ATTEMPT8_DISPOSITION_SHA
    )

    assert (
        sha256(DESIGN9_FILE)
        == EXPECTED_DESIGN9_SHA
    )

    assert (
        sha256(DECISION9_FILE)
        == EXPECTED_DECISION9_SHA
    )

    assert (
        sha256(EVALUATOR_FILE)
        == EXPECTED_EVALUATOR_SHA
    )


    v8 = load_json(V8_FILE)
    v9 = load_json(V9_FILE)
    manifest = load_json(
        V9_MANIFEST_FILE
    )
    disposition8 = load_json(
        ATTEMPT8_DISPOSITION_FILE
    )
    design9 = load_json(
        DESIGN9_FILE
    )
    decision9 = load_json(
        DECISION9_FILE
    )


    #
    # Predecessor governance.
    #
    assert disposition8[
        "generation_attempt"
    ] == 8

    assert disposition8[
        "state"
    ] == (
        "REJECTED_PRE_EXECUTION_"
        "HOLDOUT_ORACLE_DEFECT"
    )

    assert disposition8[
        "classification"
    ][
        "category"
    ] == "HOLDOUT_ORACLE_DEFECT"

    generation_state = disposition8[
        "generation_state"
    ]

    assert generation_state[
        "generated_cases_accepted_for_protected_execution"
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


    successor = disposition8[
        "successor_requirement"
    ]

    assert successor[
        "next_attempt"
    ] == 9

    assert successor[
        "new_generation_session_required"
    ] is True

    assert successor[
        "attempt_8_generated_cases_must_not_be_supplied_to_successor_generator"
    ] is True

    assert successor[
        "attempt_8_generated_artifact_must_not_be_repaired_for_protected_use"
    ] is True

    assert successor[
        "target_evaluator_must_remain_frozen"
    ] is True

    assert successor[
        "successor_package_must_add_generic_environment_self_consistency_preflight"
    ] is True

    assert successor[
        "target_freshness_available_for_successor_attempt"
    ] is True


    #
    # Attempt-9 successor design.
    #
    assert design9[
        "generation_attempt"
    ] == 9

    assert design9[
        "state"
    ] == "DESIGNED_BEFORE_PACKAGE_V9"

    assert design9[
        "governed_predecessor"
    ][
        "disposition_sha256"
    ] == EXPECTED_ATTEMPT8_DISPOSITION_SHA

    frozen = design9[
        "frozen_boundary"
    ]

    for key in [
        "generation_3_requirements_change_allowed",
        "preregistration_contract_change_allowed",
        "public_evaluator_interface_change_allowed",
        "scoring_contract_change_allowed",
        "target_evaluator_change_allowed",
    ]:
        assert frozen[key] is False

    assert frozen[
        "target_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA


    #
    # Attempt-9 environment decision.
    #
    assert decision9[
        "generation_attempt"
    ] == 9

    assert decision9[
        "state"
    ] == "DECIDED_BEFORE_PACKAGE_V9"

    assert decision9[
        "decision"
    ] == (
        "CHATGPT_TEMPORARY_UNPERSONALIZED_"
        "OBSERVABLE_ISOLATION"
    )

    assert decision9[
        "governed_predecessor"
    ][
        "disposition_sha256"
    ] == EXPECTED_ATTEMPT8_DISPOSITION_SHA

    assert decision9[
        "successor_design_binding"
    ][
        "sha256"
    ] == EXPECTED_DESIGN9_SHA

    env = decision9[
        "selected_environment"
    ]

    assert env[
        "conversation_type"
    ] == "TEMPORARY_CHAT"

    assert env[
        "personalization_mode"
    ] == "UNPERSONALIZED"

    assert env[
        "must_use_new_conversation_not_attempt_8_session"
    ] is True

    assert env[
        "prior_messages_required"
    ] == 0

    assert env[
        "automatic_library_search_required_off"
    ] is True

    assert env[
        "package_attachment_source"
    ] == "LOCAL_DISK_ONLY"

    assert env[
        "custom_gpt_prohibited"
    ] is True

    assert env[
        "plugins_prohibited"
    ] is True

    assert env[
        "connectors_prohibited"
    ] is True

    assert env[
        "web_search_prohibited"
    ] is True

    assert env[
        "external_retrieval_prohibited"
    ] is True

    assert env[
        "external_tools_prohibited"
    ] is True

    assert env[
        "only_hetren_specific_attachment"
    ] == "FROZEN_PACKAGE_V9"

    assert decision9[
        "target_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA

    assert decision9[
        "target_freshness_consumed"
    ] is False

    assert decision9[
        "attempt_9_generation_started"
    ] is False


    #
    # Manifest.
    #
    assert manifest[
        "schema_version"
    ] == "1.0.0"

    assert manifest[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_FRESH_HOLDOUT_"
        "GENERATION_PACKAGE_V9_MANIFEST"
    )

    assert manifest[
        "generation_attempt"
    ] == 9

    assert (
        ROOT / manifest["package_path"]
    ).resolve() == V9_FILE.resolve()

    assert manifest[
        "package_sha256"
    ] == EXPECTED_V9_SHA

    assert (
        ROOT
        / manifest[
            "generation_environment_decision_path"
        ]
    ).resolve() == DECISION9_FILE.resolve()

    assert manifest[
        "generation_environment_decision_sha256"
    ] == EXPECTED_DECISION9_SHA

    assert manifest[
        "contains_holdout_cases"
    ] is False

    assert manifest[
        "target_evaluator_executed"
    ] is False

    assert manifest[
        "target_freshness_consumed"
    ] is False


    #
    # Exact Package-v9 identity.
    #
    assert v9[
        "schema_version"
    ] == "9.0.0"

    assert v9[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ISOLATED_FRESH_"
        "HOLDOUT_GENERATION_PACKAGE_V9"
    )

    assert v9[
        "state"
    ] == (
        "READY_FOR_ISOLATED_GENERATION_ATTEMPT_9"
    )

    assert v9[
        "generation_attempt"
    ] == 9

    assert v9[
        "contains_holdout_cases"
    ] is False

    assert v9[
        "target_evaluator_executed"
    ] is False

    assert v9[
        "fresh_holdout_generation"
    ] is True

    assert v9[
        "protected_evaluation"
    ] is True

    assert v9[
        "authoritative"
    ] is False

    assert v9[
        "scientific_support_established"
    ] is False

    assert v9[
        "attempt_9_cases_generated"
    ] is False


    #
    # Reconstruct the exact authorized expected v9
    # independently from frozen v8 + design9.
    #
    expected_v9 = build_expected_v9(
        v8,
        design9,
    )

    assert v9 == expected_v9


    #
    # Reverse reconstruction must recover frozen v8.
    #
    reconstructed_v8 = reconstruct_v8(
        v9
    )

    assert reconstructed_v8 == v8

    reconstructed_bytes = (
        json.dumps(
            reconstructed_v8,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    ).encode()

    assert (
        reconstructed_bytes
        == V8_FILE.read_bytes()
    )


    #
    # Frozen scientific/public/scoring authority.
    #
    for key in [
        "source_bindings",
        "authority_order",
        "executable_case_contract",
        "claim_limits",
        "embedded_generation_3_requirements",
        "embedded_preregistration_contract",
        "embedded_public_evaluator_contract",
    ]:
        assert v9[key] == v8[key], key


    #
    # Exact H9 identity.
    #
    expected_ids = [
        f"G3-H9-{i:03d}"
        for i in range(1, 55)
    ]

    assert v9[
        "operationalized_design"
    ][
        "case_ids"
    ] == expected_ids

    assertions = v9[
        "generator_output_preflight_contract"
    ][
        "assertions"
    ]

    assert assertions[
        "case_ids_exactly"
    ] == expected_ids

    assert assertions[
        "case_count"
    ] == 54

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
        "each_primary_requirement_exactly_one_must_accept_and_one_must_reject"
    ] is True

    assert assertions[
        "minimum_cases_per_environment"
    ] == 6

    assert assertions[
        "minimum_cross_requirement_interaction_cases"
    ] == 12


    #
    # Generic environment-consistency hardening.
    #
    hardening = v9[
        "environment_self_consistency_preflight_contract"
    ]

    assert hardening == design9[
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
    ] == "NO_INTERNAL_ENVIRONMENT_CONTRADICTION"

    assert (
        v9["generation_rules"][-1]
        == NEW_GENERATION_RULE
    )

    attestations = v9[
        "required_generator_attestations"
    ]

    assert attestations[
        "completed_environment_self_consistency_preflight_before_returning_success_artifact"
    ] is True

    assert attestations[
        "environment_self_consistency_preflight_passed_all_required_assertions"
    ] is True

    for key, expected in (
        ENVIRONMENT_ASSERTIONS.items()
    ):
        assert assertions[key] == expected


    #
    # Success artifact must expose all hardening evidence.
    #
    output_schema = v9[
        "success_output_preflight_schema"
    ]

    for key, expected in (
        ENVIRONMENT_ASSERTIONS.items()
    ):
        assert key in output_schema[
            "required_fields"
        ]

        assert output_schema[
            "required_values"
        ][key] == expected


    #
    # Handoff integrity.
    #
    handoff = v9[
        "handoff_integrity_contract"
    ]

    assert handoff[
        "external_handoff_filename_pattern"
    ] == (
        "generation_package_v9_"
        "<EXACT_64_LOWERCASE_HEX_SHA256_OF_PACKAGE_BYTES>.json"
    )

    assert handoff[
        "handoff_creator_must_verify_filename_sha256_suffix_matches_exact_package_bytes"
    ] is True

    assert handoff[
        "success_output_generation_package_sha256_must_bind_exact_package_bytes"
    ] is True

    assert handoff[
        "embedded_source_hashes_must_not_be_used_as_generation_package_sha256"
    ] is True


    #
    # Isolation contract.
    #
    isolation = v9[
        "generation_session_isolation_contract"
    ]

    assert isolation[
        "gate_timing"
    ] == "BEFORE_ANY_CASE_GENERATION"

    assert isolation[
        "fail_closed"
    ] is True

    assert isolation[
        "scope"
    ] == "OBSERVABLE_CONVERSATION_INPUTS_ONLY"

    assert isolation[
        "package_v9_must_be_only_hetren_specific_attachment"
    ] is True

    assert isolation[
        "minimal_governed_handoff_must_be_only_other_hetren_specific_text"
    ] is True

    assert isolation[
        "conversation_must_have_zero_prior_messages_before_handoff"
    ] is True

    assert isolation[
        "generator_must_not_introspect_hidden_provider_state"
    ] is True

    assert isolation[
        "abort_output_filename"
    ] == "generation_isolation_failure_attempt_9.json"

    assert isolation[
        "abort_does_not_consume_target_freshness"
    ] is True


    #
    # Expected success artifact.
    #
    expected_output = v9[
        "expected_output"
    ]

    assert expected_output[
        "filename"
    ] == "fresh_holdout_cases_attempt_9.json"

    assert expected_output[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_FRESH_ADVERSARIAL_"
        "HOLDOUT_CASES_ATTEMPT_9"
    )

    assert expected_output[
        "state"
    ] == "GENERATED_NOT_EXECUTED"

    assert expected_output[
        "generation_attempt"
    ] == 9

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


    #
    # Target evaluator remains frozen and inaccessible to generator.
    #
    assert v9[
        "source_bindings"
    ][
        "frozen_target_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA

    preflight = v9[
        "generator_output_preflight_contract"
    ]

    assert preflight[
        "target_evaluator_must_not_be_executed"
    ] is True

    assert preflight[
        "target_evaluator_must_not_be_simulated"
    ] is True

    assert preflight[
        "protected_outcomes_must_not_be_available"
    ] is True


    #
    # No predecessor case / disposition / defect instance
    # may be embedded into Package v9.
    #
    package_text = V9_FILE.read_text()

    forbidden_values = [
        "G3-H8-",
        "G3-H8-053",
        "fresh_holdout_cases_attempt_8.json",
        "fresh_holdout_generation_attempt_8_disposition.json",
        EXPECTED_ATTEMPT8_DISPOSITION_SHA,
        (
            "54951a06e6cd431e43e83d2e3c516ed"
            "b1e378cc7ac11a799738fe363e56bdf5a"
        ),
        "E3 vision-only offline scoring",
        "no agent trajectory surface",
    ]

    for value in forbidden_values:
        assert value not in package_text, value


    #
    # Attempt 9 must still be pre-generation.
    #
    premature = [
        DATA
        / "generation_environment_attestation_attempt_9.json",

        DATA
        / "generation_isolation_failure_attempt_9.json",

        DATA
        / "fresh_holdout_cases_attempt_9.json",

        DATA
        / "fresh_holdout_generation_attempt_9_disposition.json",

        DATA
        / "fresh_holdout_first_run.json",

        DATA
        / "fresh_holdout_freeze_manifest.json",
    ]

    existing = [
        str(path)
        for path in premature
        if path.exists()
    ]

    assert not existing, existing


    print("PASS: exact Package-v9 bytes")
    print("PASS: exact Package-v9 manifest bytes")
    print("PASS: exact Attempt-9 environment-decision bytes")
    print("PASS: exact Attempt-9 successor-design bytes")
    print("PASS: exact Attempt-8 disposition governance")
    print("PASS: frozen target evaluator bytes")
    print("PASS: manifest binds Package-v9 exactly")
    print("PASS: manifest binds Attempt-9 environment decision exactly")
    print("PASS: Attempt 9 authorized successor")
    print("PASS: new isolated generation session required")
    print("PASS: Package-v9 reconstructed independently from v8 + design9")
    print("PASS: authorized v8 -> v9 hardening surface only")
    print("PASS: stripping v9 hardening + reversing 9 -> 8 reconstructs v8 bytes")
    print("PASS: G3/preregistration/public evaluator/scoring authority unchanged")
    print("PASS: exact G3-H9-001..054 required")
    print("PASS: 54 unique case IDs required")
    print("PASS: 27 MUST_ACCEPT / 27 MUST_REJECT required")
    print("PASS: one accept + one reject per G3 requirement required")
    print("PASS: >=6 cases per environment required")
    print("PASS: >=12 interaction cases required")
    print("PASS: generic environment self-consistency hardening exact")
    print("PASS: deterministic environment mismatch count must be zero")
    print("PASS: semantic environment consistency review required")
    print("PASS: environment hardening evidence required in success output")
    print("PASS: exact SHA-suffixed handoff contract")
    print("PASS: observable isolation contract preserved")
    print("PASS: zero-prior-message boundary preserved")
    print("PASS: predecessor case/disposition/defect instance embedded: NO")
    print("PASS: target evaluator cannot execute or simulate during generation")
    print("PASS: Attempt-9 attestation/cases/results still absent")
    print("PASS: target freshness remains available")


if __name__ == "__main__":
    main()
