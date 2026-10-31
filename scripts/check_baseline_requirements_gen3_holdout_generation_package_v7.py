#!/usr/bin/env python3

from copy import deepcopy
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

V6_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v6.json"
)

V7_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_package_v7.json"
)

ATTEMPT6_GENERATION_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_attempt_6.json"
)

ATTEMPT6_DISPOSITION_FILE = (
    DATA_DIR
    / "fresh_holdout_generation_attempt_6_disposition.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)


EXPECTED_V6_SHA = (
    "f05eaa07ce5bcbbbef15117b49a3bc82"
    "a8e4c4212a0a086f16cddc56d49d65d8"
)

EXPECTED_V7_SHA = (
    "990a611b7be68448bf899a111323ac4d"
    "108ba5b01378831c67a635788e9c21e6"
)

EXPECTED_ATTEMPT6_GENERATION_SHA = (
    "8b8c408517d6cb653b9a69b1a1ae184c"
    "a638b44e60b15524e2cf8d6dcea1ef54"
)

EXPECTED_ATTEMPT6_DISPOSITION_SHA = (
    "e5c2f9a097f632890cee4fbabdf57d63"
    "b90e1dfb7e87260113bfc4a11ed732ea"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)


FORWARD_REPLACEMENTS = [
    ("generation_package_v6", "generation_package_v7"),
    ("package_v6", "package_v7"),
    ("PACKAGE_V6", "PACKAGE_V7"),
    ("Package v6", "Package v7"),
    ("Generation Package v6", "Generation Package v7"),
    ("attempt_6", "attempt_7"),
    ("ATTEMPT_6", "ATTEMPT_7"),
    ("Attempt 6", "Attempt 7"),
    ("attempt 6", "attempt 7"),
    ("G3-H6", "G3-H7"),
]

REVERSE_REPLACEMENTS = [
    (new, old)
    for old, new in reversed(
        FORWARD_REPLACEMENTS
    )
]


NEW_TOP_LEVEL_KEYS = {
    "handoff_integrity_contract",
    "generator_output_preflight_contract",
    "success_output_preflight_schema",
}


NEW_ATTESTATION_KEYS = {
    "completed_generator_output_preflight_before_returning_success_artifact",
    "generator_output_preflight_passed_all_required_assertions",
    "generation_package_sha256_copied_from_verified_handoff_filename_sha256",
}


NEW_GENERATION_RULES = [
    (
        "Before returning the single final success artifact, execute "
        "generator_output_preflight_contract. Do not return a success "
        "artifact unless every listed assertion passes."
    ),
    (
        "Populate generation_package_sha256 only from the exact "
        "64-character SHA-256 suffix of the verified attached Package-v7 "
        "handoff filename. Do not substitute generation_3_sha256, "
        "preregistration_contract_sha256, public evaluator hashes, "
        "target evaluator hashes, or any other embedded source hash."
    ),
    (
        "Before returning success, verify that case IDs are exactly "
        "G3-H7-001 through G3-H7-054 with no duplicates and no omissions."
    ),
    (
        "Before returning success, verify exactly 54 cases, exactly "
        "27 MUST_ACCEPT and 27 MUST_REJECT, and exactly one of each "
        "expectation for every G3-BR-001 through G3-BR-027."
    ),
    (
        "Before returning success, verify at least twelve cases have "
        "one or more material secondary_requirements interactions."
    ),
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
        V6_FILE
    ) == EXPECTED_V6_SHA

    assert sha256(
        V7_FILE
    ) == EXPECTED_V7_SHA

    assert sha256(
        ATTEMPT6_GENERATION_FILE
    ) == EXPECTED_ATTEMPT6_GENERATION_SHA

    assert sha256(
        ATTEMPT6_DISPOSITION_FILE
    ) == EXPECTED_ATTEMPT6_DISPOSITION_SHA

    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA


    v6 = load_json(
        V6_FILE
    )

    v7 = load_json(
        V7_FILE
    )

    disposition6 = load_json(
        ATTEMPT6_DISPOSITION_FILE
    )


    #
    # Attempt-7 package identity.
    #
    assert v7[
        "schema_version"
    ] == "7.0.0"

    assert v7[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ISOLATED_FRESH_"
        "HOLDOUT_GENERATION_PACKAGE_V7"
    )

    assert v7[
        "state"
    ] == (
        "READY_FOR_ISOLATED_GENERATION_ATTEMPT_7"
    )

    assert v7[
        "generation_attempt"
    ] == 7

    assert v7[
        "contains_holdout_cases"
    ] is False

    assert v7[
        "attempt_7_cases_generated"
    ] is False

    assert v7[
        "target_evaluator_executed"
    ] is False

    assert v7[
        "fresh_holdout_generation"
    ] is True

    assert v7[
        "protected_evaluation"
    ] is True

    assert v7[
        "authoritative"
    ] is False

    assert v7[
        "scientific_support_established"
    ] is False


    #
    # Verify exact top-level hardening surface.
    #
    mechanically_renamed_v6 = transform(
        v6,
        FORWARD_REPLACEMENTS,
        6,
        7,
    )

    mechanically_renamed_v6[
        "schema_version"
    ] = "7.0.0"


    v6_successor_keys = set(
        mechanically_renamed_v6
    )

    v7_keys = set(
        v7
    )


    assert (
        v7_keys
        - v6_successor_keys
    ) == NEW_TOP_LEVEL_KEYS

    assert (
        v6_successor_keys
        - v7_keys
    ) == set()


    #
    # Strip all authorized hardening additions and prove that
    # frozen Package v6 reconstructs exactly.
    #
    stripped = deepcopy(
        v7
    )

    for key in NEW_TOP_LEVEL_KEYS:
        del stripped[
            key
        ]


    for key in NEW_ATTESTATION_KEYS:
        assert stripped[
            "required_generator_attestations"
        ][
            key
        ] is True

        del stripped[
            "required_generator_attestations"
        ][
            key
        ]


    required_fields = stripped[
        "expected_output"
    ][
        "required_top_level_fields"
    ]

    assert required_fields[
        -1
    ] == "generator_output_preflight"

    required_fields.pop()


    assert stripped[
        "generation_rules"
    ][
        -len(
            NEW_GENERATION_RULES
        ):
    ] == NEW_GENERATION_RULES

    del stripped[
        "generation_rules"
    ][
        -len(
            NEW_GENERATION_RULES
        ):
    ]


    reconstructed_v6 = transform(
        stripped,
        REVERSE_REPLACEMENTS,
        7,
        6,
    )

    reconstructed_v6[
        "schema_version"
    ] = "6.0.0"


    assert reconstructed_v6 == v6


    #
    # Scientific authority must remain byte-for-byte semantic-equal.
    #
    scientific_keys = [
        "embedded_generation_3_requirements",
        "embedded_preregistration_contract",
        "embedded_public_evaluator_contract",
        "source_bindings",
        "authority_order",
        "executable_case_contract",
        "claim_limits",
    ]


    for key in scientific_keys:
        assert v7[
            key
        ] == v6[
            key
        ], key


    #
    # Original operational design stays scientifically identical,
    # except the attempt-specific H7 namespace.
    #
    design = v7[
        "operationalized_design"
    ]

    expected_case_ids = [
        f"G3-H7-{number:03d}"
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
    ] == "G3-H7-NNN"

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


    #
    # Package-hash handoff integrity.
    #
    handoff = v7[
        "handoff_integrity_contract"
    ]

    assert handoff[
        "external_handoff_filename_pattern"
    ] == (
        "generation_package_v7_"
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

    forbidden_hash_sources = set(
        handoff[
            "explicitly_forbidden_hash_substitutions"
        ]
    )

    assert forbidden_hash_sources == {
        "source_bindings.generation_3_sha256",
        "source_bindings.preregistration_contract_sha256",
        "source_bindings.public_evaluator_contract_sha256",
        "source_bindings.public_evaluator_contract_manifest_sha256",
        "source_bindings.frozen_target_evaluator_sha256",
    }


    #
    # Generator output preflight.
    #
    preflight_contract = v7[
        "generator_output_preflight_contract"
    ]

    assert preflight_contract[
        "timing"
    ] == (
        "AFTER_ALL_CASES_ARE_GENERATED_AND_"
        "BEFORE_RETURNING_SUCCESS_OUTPUT"
    )

    assert preflight_contract[
        "scope"
    ] == "STRUCTURAL_AND_CONTRACT_VALIDATION_ONLY"

    assert preflight_contract[
        "target_evaluator_must_not_be_executed"
    ] is True

    assert preflight_contract[
        "target_evaluator_must_not_be_simulated"
    ] is True

    assert preflight_contract[
        "protected_outcomes_must_not_be_available"
    ] is True

    assert preflight_contract[
        "intermediate_invalid_success_artifact_must_not_be_returned"
    ] is True

    assert preflight_contract[
        "if_any_assertion_fails"
    ] == (
        "REVISE_OR_REGENERATE_WITHIN_THE_GENERATION_PROCESS_"
        "BEFORE_RETURNING_THE_SINGLE_FINAL_SUCCESS_ARTIFACT"
    )


    assertions = preflight_contract[
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


    #
    # Success output must expose evidence that preflight occurred.
    #
    output_schema = v7[
        "success_output_preflight_schema"
    ]

    assert output_schema[
        "field_name"
    ] == "generator_output_preflight"

    assert output_schema[
        "required"
    ] is True

    required_preflight_fields = set(
        output_schema[
            "required_fields"
        ]
    )

    assert required_preflight_fields == {
        "performed_before_return",
        "passed",
        "generation_package_sha256_matches_handoff_filename",
        "case_count",
        "unique_case_id_count",
        "exact_case_identity_set",
        "must_accept_count",
        "must_reject_count",
        "primary_requirement_pairing_valid",
        "environment_minimums_satisfied",
        "interaction_case_count",
        "minimum_interaction_requirement_satisfied",
        "all_case_schema_checks_passed",
        "target_evaluator_executed",
        "target_evaluator_simulated",
    }


    required_values = output_schema[
        "required_values"
    ]

    assert required_values[
        "performed_before_return"
    ] is True

    assert required_values[
        "passed"
    ] is True

    assert required_values[
        "generation_package_sha256_matches_handoff_filename"
    ] is True

    assert required_values[
        "case_count"
    ] == 54

    assert required_values[
        "unique_case_id_count"
    ] == 54

    assert required_values[
        "exact_case_identity_set"
    ] is True

    assert required_values[
        "must_accept_count"
    ] == 27

    assert required_values[
        "must_reject_count"
    ] == 27

    assert required_values[
        "primary_requirement_pairing_valid"
    ] is True

    assert required_values[
        "environment_minimums_satisfied"
    ] is True

    assert required_values[
        "minimum_interaction_requirement_satisfied"
    ] is True

    assert required_values[
        "all_case_schema_checks_passed"
    ] is True

    assert required_values[
        "target_evaluator_executed"
    ] is False

    assert required_values[
        "target_evaluator_simulated"
    ] is False

    assert output_schema[
        "interaction_case_count_constraint"
    ] == "INTEGER_GREATER_THAN_OR_EQUAL_TO_12"


    #
    # Required top-level success field.
    #
    assert (
        "generator_output_preflight"
        in v7[
            "expected_output"
        ][
            "required_top_level_fields"
        ]
    )


    #
    # Added attestations must be exact.
    #
    attestations = v7[
        "required_generator_attestations"
    ]

    for key in NEW_ATTESTATION_KEYS:
        assert attestations[
            key
        ] is True


    #
    # New rules must exist exactly as the final appended block.
    #
    assert v7[
        "generation_rules"
    ][
        -len(
            NEW_GENERATION_RULES
        ):
    ] == NEW_GENERATION_RULES


    #
    # Isolation remains unchanged except H6 -> H7 identity.
    #
    isolation_v7 = v7[
        "generation_session_isolation_contract"
    ]

    isolation_v6_as_v7 = transform(
        v6[
            "generation_session_isolation_contract"
        ],
        FORWARD_REPLACEMENTS,
        6,
        7,
    )

    assert isolation_v7 == isolation_v6_as_v7


    #
    # Frozen public evaluator remains bound.
    #
    public_contract = v7[
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
    # Attempt-6 evidence cannot be embedded in Package v7.
    #
    package_text = V7_FILE.read_text()

    forbidden_values = [
        EXPECTED_ATTEMPT6_GENERATION_SHA,
        EXPECTED_ATTEMPT6_DISPOSITION_SHA,
        "fresh_holdout_generation_attempt_6.json",
        "fresh_holdout_generation_attempt_6_disposition.json",
        "G3-H6-",
    ]

    for value in forbidden_values:
        assert value not in package_text, value


    #
    # Attempt-6 disposition governs Attempt 7.
    #
    assert disposition6[
        "state"
    ] == (
        "REJECTED_PRE_EXECUTION_"
        "GENERATED_ARTIFACT_CONTRACT_FAILURE"
    )

    assert disposition6[
        "cases_generated"
    ] is True

    assert disposition6[
        "generated_cases_accepted_for_protected_execution"
    ] is False

    assert disposition6[
        "target_evaluator_executed"
    ] is False

    assert disposition6[
        "target_evaluator_simulated"
    ] is False

    assert disposition6[
        "target_predictions_produced"
    ] is False

    assert disposition6[
        "target_freshness_consumed"
    ] is False


    successor = disposition6[
        "successor_requirement"
    ]

    assert successor[
        "next_attempt"
    ] == 7

    assert successor[
        "new_generation_session_required"
    ] is True

    assert successor[
        "attempt_6_generation_session_must_not_be_reused"
    ] is True

    assert successor[
        "attempt_6_generated_cases_must_not_be_supplied_to_successor_generator"
    ] is True

    assert successor[
        "attempt_6_generated_artifact_must_not_be_repaired_for_protected_use"
    ] is True

    assert successor[
        "prior_attempt_artifacts_must_not_be_supplied_to_successor_generator"
    ] is True

    assert successor[
        "target_evaluator_must_remain_frozen"
    ] is True

    assert successor[
        "successor_package_must_preserve_same_scientific_contract"
    ] is True

    assert successor[
        "successor_generation_must_satisfy_exact_case_identity_set"
    ] is True

    assert successor[
        "successor_generation_must_satisfy_minimum_12_interaction_cases"
    ] is True

    assert successor[
        "successor_generation_must_bind_its_exact_package_sha256"
    ] is True

    assert successor[
        "freshness_available_for_successor_attempt"
    ] is True


    print("PASS: exact hardened Generation Package v7")
    print("PASS: authorized hardening surface only")
    print("PASS: stripping hardening reconstructs frozen Package v6 exactly")
    print("PASS: G3/D1/public evaluator/scoring authority unchanged")
    print("PASS: exact G3-H7-001..054 preflight required")
    print("PASS: 54 unique IDs required")
    print("PASS: 27 MUST_ACCEPT / 27 MUST_REJECT required")
    print("PASS: every G3-BR-001..027 must have one accept + one reject")
    print("PASS: >=12 interaction cases required")
    print("PASS: package hash source is handoff filename SHA")
    print("PASS: embedded source-hash substitution prohibited")
    print("PASS: preflight evidence required in success output")
    print("PASS: preflight cannot execute or simulate target evaluator")
    print("PASS: Attempt-6 evidence embedded: NO")
    print("PASS: Attempt 7 remains authorized successor")
    print("PASS: target freshness remains unconsumed")

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


if __name__ == "__main__":
    main()
