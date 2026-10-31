#!/usr/bin/env python3

VALID_ENVIRONMENTS = {
    "E1",
    "E2",
    "E3",
    "CROSS_ENV",
}


SUPPORTED_REQUIREMENTS = {
    f"G3-BR-{number:03d}"
    for number in range(1, 28)
}


def _flag(facts, key, default=False):
    return bool(
        facts.get(
            key,
            default,
        )
    )


def _add(violations, condition, code):
    if condition:
        violations.append(code)


def evaluate(
    primary_requirement,
    facts,
    environment,
):
    violations = []

    if primary_requirement not in SUPPORTED_REQUIREMENTS:
        return {
            "decision": "REJECT",
            "violations": [
                "UNKNOWN_REQUIREMENT",
            ],
        }

    if environment not in VALID_ENVIRONMENTS:
        return {
            "decision": "REJECT",
            "violations": [
                "UNKNOWN_ENVIRONMENT",
            ],
        }

    if not isinstance(facts, dict) or not facts:
        return {
            "decision": "REJECT",
            "violations": [
                "MISSING_FACTS",
            ],
        }

    if primary_requirement == "G3-BR-001":
        backend_known = _flag(
            facts,
            "backend_revision_known",
        )

        claims_exact = _flag(
            facts,
            "claims_exact_version_pin",
        )

        _add(
            violations,
            claims_exact and not backend_known,
            "FALSE_EXACT_VERSION_CLAIM",
        )

        if not backend_known:
            _add(
                violations,
                facts.get(
                    "revision_state"
                ) not in {
                    "UNKNOWN",
                    "UNAVAILABLE",
                },
                "UNKNOWN_REVISION_NOT_RECORDED",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "reproducibility_limitation_recorded",
                )
                and not claims_exact,
                "REPRODUCIBILITY_LIMITATION_MISSING",
            )

    elif primary_requirement == "G3-BR-002":
        changed = _flag(
            facts,
            "baseline_changed_after_protected",
        )

        if changed:
            _add(
                violations,
                not _flag(
                    facts,
                    "successor_evidence_created",
                ),
                "SUCCESSOR_EVIDENCE_MISSING",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "prior_result_preserved",
                ),
                "PRIOR_RESULT_NOT_PRESERVED",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "task7_lineage_applied",
                ),
                "TASK7_LINEAGE_NOT_APPLIED",
            )

    elif primary_requirement == "G3-BR-003":
        _add(
            violations,
            not _flag(
                facts,
                "search_scope_predeclared",
            ),
            "SEARCH_SCOPE_NOT_PREDECLARED",
        )

        _add(
            violations,
            not _flag(
                facts,
                "search_cutoff_predeclared",
            ),
            "SEARCH_CUTOFF_NOT_PREDECLARED",
        )

        _add(
            violations,
            not _flag(
                facts,
                "material_comparators_preserved",
            ),
            "COMPARATOR_PROVENANCE_MISSING",
        )

        _add(
            violations,
            not _flag(
                facts,
                "exclusion_reasons_preserved",
            ),
            "EXCLUSION_REASONS_MISSING",
        )

        _add(
            violations,
            _flag(
                facts,
                "protected_outcomes_used_for_selection",
            ),
            "PROTECTED_SELECTION_LEAKAGE",
        )

    elif primary_requirement == "G3-BR-004":
        diagnostic = (
            facts.get(
                "anchor_role"
            ) == "DIAGNOSTIC"
        )

        anchor_win = _flag(
            facts,
            "candidate_beats_anchor",
        )

        strongest_win = _flag(
            facts,
            "candidate_beats_strongest_comparator",
        )

        general_claim = _flag(
            facts,
            "reported_as_general_superiority",
        )

        _add(
            violations,
            diagnostic
            and anchor_win
            and not strongest_win
            and general_claim,
            "DIAGNOSTIC_ANCHOR_MASQUERADES_AS_STRONG_BASELINE",
        )

    elif primary_requirement == "G3-BR-005":
        candidate_state = facts.get(
            "candidate_retrieval_cache"
        )

        baseline_state = facts.get(
            "baseline_retrieval_cache"
        )

        state_difference = (
            candidate_state is not None
            and baseline_state is not None
            and candidate_state != baseline_state
        )

        _add(
            violations,
            state_difference
            and not _flag(
                facts,
                "state_difference_is_treatment",
            ),
            "PERSISTENT_INFORMATION_ASYMMETRY",
        )

        transcript_fields_present = (
            "candidate_prior_transcript_available" in facts
            and "baseline_prior_transcript_available" in facts
        )

        if transcript_fields_present:
            transcript_difference = (
                _flag(
                    facts,
                    "candidate_prior_transcript_available",
                )
                != _flag(
                    facts,
                    "baseline_prior_transcript_available",
                )
            )

            _add(
                violations,
                transcript_difference
                and not _flag(
                    facts,
                    "state_difference_is_treatment",
                ),
                "PERSISTENT_INFORMATION_ASYMMETRY",
            )

        if "persistent_state_matched" in facts:
            _add(
                violations,
                (
                    not _flag(
                        facts,
                        "persistent_state_matched",
                    )
                    and not _flag(
                        facts,
                        "state_difference_is_treatment",
                    )
                ),
                "PERSISTENT_STATE_NOT_MATCHED",
            )

    elif primary_requirement == "G3-BR-006":
        mutable = _flag(
            facts,
            "environment_mutable",
        )

        if mutable:
            controlled = any([
                _flag(
                    facts,
                    "same_snapshot",
                ),
                _flag(
                    facts,
                    "paired_execution",
                ),
                _flag(
                    facts,
                    "controlled_replay",
                ),
                _flag(
                    facts,
                    "temporal_drift_qualified",
                ),
            ])

            _add(
                violations,
                not controlled,
                "TEMPORAL_ENVIRONMENT_DRIFT_UNCONTROLLED",
            )

    elif primary_requirement == "G3-BR-007":
        material = _flag(
            facts,
            "material_asymmetry",
        )

        if material:
            _add(
                violations,
                not _flag(
                    facts,
                    "asymmetry_predeclared",
                ),
                "ASYMMETRY_NOT_PREDECLARED",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "asymmetry_matches_claimed_treatment",
                ),
                "ASYMMETRY_NOT_CAUSALLY_RELEVANT",
            )

    elif primary_requirement == "G3-BR-008":
        candidate_iterations = facts.get(
            "candidate_manual_iterations"
        )

        baseline_iterations = facts.get(
            "baseline_manual_iterations"
        )

        if (
            candidate_iterations is not None
            and baseline_iterations is not None
            and candidate_iterations != baseline_iterations
        ):
            _add(
                violations,
                not _flag(
                    facts,
                    "asymmetry_scientifically_justified",
                ),
                "TUNING_OPPORTUNITY_ASYMMETRY",
            )

        _add(
            violations,
            not _flag(
                facts,
                "tuning_policy_predeclared",
            ),
            "TUNING_POLICY_NOT_PREDECLARED",
        )

    elif primary_requirement == "G3-BR-009":
        revision_available = _flag(
            facts,
            "evaluator_revision_available",
        )

        if revision_available:
            _add(
                violations,
                not _flag(
                    facts,
                    "evaluator_revision_field_present",
                ),
                "AVAILABLE_PROVENANCE_NOT_RECORDED",
            )

        if not revision_available:
            _add(
                violations,
                not _flag(
                    facts,
                    "evaluator_revision_field_present",
                ),
                "MATERIAL_PROVENANCE_FIELD_OMITTED",
            )

            if _flag(
                facts,
                "evaluator_revision_field_present",
            ):
                _add(
                    violations,
                    facts.get(
                        "evaluator_revision"
                    ) not in {
                        "UNKNOWN",
                        "UNAVAILABLE",
                    },
                    "UNAVAILABLE_PROVENANCE_NOT_EXPLICIT",
                )

    elif primary_requirement == "G3-BR-010":
        unpinned = _flag(
            facts,
            "external_api_unpinned",
        )

        reproduction_class = facts.get(
            "reproducibility_class"
        )

        valid_classes = {
            "EXACT_RECONSTRUCTION",
            "CONTROLLED_RECONSTRUCTION",
            "BEHAVIORAL_REPLAY",
            "IRREPRODUCIBLE_EXTERNAL_DEPENDENCY",
        }

        _add(
            violations,
            reproduction_class not in valid_classes,
            "INVALID_REPRODUCIBILITY_CLASS",
        )

        _add(
            violations,
            unpinned
            and reproduction_class
            == "EXACT_RECONSTRUCTION",
            "FALSE_EXACT_RECONSTRUCTION",
        )

        if (
            unpinned
            and reproduction_class
            != "EXACT_RECONSTRUCTION"
        ):
            _add(
                violations,
                not _flag(
                    facts,
                    "limitation_recorded",
                ),
                "EXTERNAL_DEPENDENCY_LIMITATION_MISSING",
            )

    elif primary_requirement == "G3-BR-011":
        _add(
            violations,
            _flag(
                facts,
                "outcome_driven_stopping",
            )
            and not _flag(
                facts,
                "stopping_rule_predeclared",
            ),
            "OPTIONAL_STOPPING",
        )

        _add(
            violations,
            _flag(
                facts,
                "repeated_runs_claimed_independent",
            ),
            "PSEUDOREPLICATION",
        )

    elif primary_requirement == "G3-BR-012":
        _add(
            violations,
            not _flag(
                facts,
                "analysis_uses_task7_evaluation_units",
            ),
            "TASK7_EVALUATION_UNIT_IGNORED",
        )

        _add(
            violations,
            not _flag(
                facts,
                "analysis_uses_independence_groups",
            ),
            "INDEPENDENCE_GROUP_IGNORED",
        )

        _add(
            violations,
            _flag(
                facts,
                "repeated_seeds_treated_independent",
            ),
            "REPEATED_SEEDS_TREATED_INDEPENDENT",
        )

    elif primary_requirement == "G3-BR-013":
        primary_passed = _flag(
            facts,
            "primary_metric_passed",
        )

        secondary_promoted = _flag(
            facts,
            "secondary_promoted_after_outcome",
        )

        _add(
            violations,
            not primary_passed
            and secondary_promoted,
            "POST_HOC_SECONDARY_PROMOTION",
        )

        if not primary_passed:
            _add(
                violations,
                not _flag(
                    facts,
                    "primary_claim_remains_failed",
                ),
                "FAILED_PRIMARY_CLAIM_NOT_PRESERVED",
            )

    elif primary_requirement == "G3-BR-014":
        claim_affecting = _flag(
            facts,
            "constraint_affects_claim",
            True,
        )

        if claim_affecting:
            _add(
                violations,
                not _flag(
                    facts,
                    "hard_constraint_bound_before_protected",
                ),
                "HARD_CONSTRAINT_NOT_FROZEN",
            )

        if _flag(
            facts,
            "hard_constraint_bound_before_protected",
        ):
            _add(
                violations,
                not _flag(
                    facts,
                    "constraint_violation_blocks_pass",
                ),
                "HARD_CONSTRAINT_CAN_BE_AVERAGED_AWAY",
            )

    elif primary_requirement == "G3-BR-015":
        _add(
            violations,
            not _flag(
                facts,
                "sampling_rule_predeclared",
            ),
            "BENCHMARK_SAMPLING_NOT_PREDECLARED",
        )

        _add(
            violations,
            _flag(
                facts,
                "weights_changed_after_outcomes",
            ),
            "POST_OUTCOME_BENCHMARK_REWEIGHTING",
        )

        _add(
            violations,
            not _flag(
                facts,
                "difficulty_distribution_preserved",
            ),
            "DIFFICULTY_DISTRIBUTION_NOT_PRESERVED",
        )

    elif primary_requirement == "G3-BR-016":
        dynamic = _flag(
            facts,
            "benchmark_dynamic",
        )

        contamination_state = facts.get(
            "contamination_state"
        )

        cleanliness_evidence = _flag(
            facts,
            "cleanliness_evidence_available",
        )

        _add(
            violations,
            contamination_state == "CLEAN"
            and not cleanliness_evidence,
            "UNSUPPORTED_CLEAN_CONTAMINATION_CLAIM",
        )

        _add(
            violations,
            dynamic
            and contamination_state == "CLEAN"
            and not cleanliness_evidence,
            "DYNAMIC_BENCHMARK_FALSE_CLEANLINESS",
        )

        _add(
            violations,
            _flag(
                facts,
                "dynamic_implies_clean",
            ),
            "DYNAMISM_USED_AS_CLEANLINESS_PROOF",
        )

    elif primary_requirement == "G3-BR-017":
        same_family = _flag(
            facts,
            "judge_same_family_as_candidate",
        )

        material = _flag(
            facts,
            "claim_depends_on_judge",
            True,
        )

        explicit_evaluator_fields = [
            (
                "evaluator_identity_present",
                "EVALUATOR_IDENTITY_MISSING",
            ),
            (
                "evaluator_version_present",
                "EVALUATOR_VERSION_MISSING",
            ),
            (
                "evaluator_scoring_procedure_present",
                "EVALUATOR_SCORING_PROCEDURE_MISSING",
            ),
        ]

        for field_name, violation_code in explicit_evaluator_fields:
            if field_name in facts:
                _add(
                    violations,
                    not _flag(
                        facts,
                        field_name,
                    ),
                    violation_code,
                )

        if same_family and material:
            _add(
                violations,
                not _flag(
                    facts,
                    "relationship_recorded",
                ),
                "EVALUATOR_RELATIONSHIP_UNDISCLOSED",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "bias_control_performed",
                ),
                "SELF_PREFERENCE_NOT_CONTROLLED",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "alternative_crosscheck_present",
                ),
                "ALTERNATIVE_EVALUATION_PATH_MISSING",
            )

    elif primary_requirement == "G3-BR-018":
        observable = _flag(
            facts,
            "hidden_side_effects_observable",
            True,
        )

        _add(
            violations,
            not _flag(
                facts,
                "observation_boundary_declared",
            ),
            "OBSERVATION_BOUNDARY_UNDECLARED",
        )

        _add(
            violations,
            not observable
            and _flag(
                facts,
                "claims_absence_of_side_effects",
            ),
            "UNOBSERVED_TREATED_AS_ABSENT",
        )

        if not observable:
            _add(
                violations,
                facts.get(
                    "unobservable_state_disposition"
                ) not in {
                    "UNKNOWN",
                    "UNAVAILABLE",
                },
                "UNOBSERVABLE_STATE_NOT_EXPLICIT",
            )

    elif primary_requirement == "G3-BR-019":
        target_information_channel = any([
            _flag(
                facts,
                "target_specific_prompt_engineering",
            ),
            _flag(
                facts,
                "target_specific_retrieval",
            ),
            _flag(
                facts,
                "target_specific_onboarding",
            ),
            _flag(
                facts,
                "target_specific_demonstrations",
            ),
            _flag(
                facts,
                "manual_target_engineering",
            ),
        ])

        if target_information_channel:
            _add(
                violations,
                not _flag(
                    facts,
                    "channel_classified_separately",
                ),
                "TARGET_INFORMATION_CHANNEL_HIDDEN",
            )

            _add(
                violations,
                (
                    _flag(
                        facts,
                        "manual_target_engineering",
                    )
                    and _flag(
                        facts,
                        "claimed_as_learned_transfer",
                    )
                    and not _flag(
                        facts,
                        "channel_classified_separately",
                    )
                ),
                "MANUAL_ENGINEERING_MASQUERADES_AS_TRANSFER",
            )

    elif primary_requirement == "G3-BR-020":
        candidate_input = facts.get(
            "candidate_adaptation_input"
        )

        baseline_input = facts.get(
            "baseline_adaptation_input"
        )

        mismatch = (
            candidate_input is not None
            and baseline_input is not None
            and candidate_input != baseline_input
        )

        _add(
            violations,
            mismatch
            and not _flag(
                facts,
                "difference_is_declared_treatment",
            ),
            "ADAPTATION_INPUT_ASYMMETRY",
        )

        _add(
            violations,
            not _flag(
                facts,
                "strongest_applicable_baseline_used",
            ),
            "STRONG_ADAPTATION_BASELINE_MISSING",
        )

    elif primary_requirement == "G3-BR-021":
        declared_success = _flag(
            facts,
            "declared_rollback_success",
            True,
        )

        if declared_success:
            _add(
                violations,
                not _flag(
                    facts,
                    "rollback_command_succeeded",
                ),
                "ROLLBACK_OPERATION_FAILED",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "persistent_index_restored",
                ),
                "ROLLBACK_STATE_NOT_RESTORED",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "behavioral_restoration_checked",
                ),
                "ROLLBACK_BEHAVIOR_NOT_VERIFIED",
            )

            if _flag(
                facts,
                "persistent_memory_material",
            ):
                _add(
                    violations,
                    not _flag(
                        facts,
                        "persistent_memory_restored",
                    ),
                    "ROLLBACK_MATERIAL_STATE_NOT_RESTORED",
                )

    elif primary_requirement == "G3-BR-022":
        _add(
            violations,
            not _flag(
                facts,
                "resource_regime_frozen_before_protected",
            ),
            "RESOURCE_REGIME_NOT_FROZEN",
        )

        _add(
            violations,
            not _flag(
                facts,
                "quality_and_resource_reported_separately",
            ),
            "QUALITY_RESOURCE_TRADEOFF_COLLAPSED",
        )

        _add(
            violations,
            _flag(
                facts,
                "single_weighted_score_only",
            ),
            "SINGLE_AGGREGATE_HIDES_TRADEOFF",
        )

    elif primary_requirement == "G3-BR-023":
        stronger = _flag(
            facts,
            "credible_stronger_comparator_evidence",
        )

        if stronger:
            _add(
                violations,
                not _flag(
                    facts,
                    "reassessment_triggered",
                ),
                "BASELINE_REASSESSMENT_NOT_TRIGGERED",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "review_as_of_date_recorded",
                ),
                "BASELINE_REVIEW_DATE_MISSING",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "historical_result_preserved",
                ),
                "HISTORICAL_BASELINE_RESULT_REWRITTEN",
            )

    elif primary_requirement == "G3-BR-024":
        unavailable = not _flag(
            facts,
            "required_comparator_available",
            True,
        )

        if unavailable:
            _add(
                violations,
                not _flag(
                    facts,
                    "broader_claim_blocked",
                ),
                "BROADER_CLAIM_NOT_BLOCKED",
            )

            _add(
                violations,
                _flag(
                    facts,
                    "narrow_claim_implies_broader_superiority",
                ),
                "NARROW_CLAIM_IMPLIES_BLOCKED_SUPERIORITY",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "original_evidence_gap_preserved",
                ),
                "ORIGINAL_EVIDENCE_GAP_LOST",
            )

    elif primary_requirement == "G3-BR-025":
        required_scope_fields = [
            "population_scope_declared",
            "sampling_method_declared",
            "time_window_declared",
            "deployment_scope_declared",
        ]

        for field in required_scope_fields:
            _add(
                violations,
                not _flag(
                    facts,
                    field,
                ),
                f"REAL_WORLD_SCOPE_MISSING:{field}",
            )

        _add(
            violations,
            _flag(
                facts,
                "selection_based_on_favorable_results",
            ),
            "REAL_WORLD_SELECTION_CHERRY_PICKED",
        )

    elif primary_requirement == "G3-BR-026":
        same_model_family = _flag(
            facts,
            "same_model_family",
        )

        shared = any([
            _flag(
                facts,
                "same_judge_model",
            ),
            _flag(
                facts,
                "same_preprocessing",
            ),
            same_model_family,
        ])

        if same_model_family:
            _add(
                violations,
                not _flag(
                    facts,
                    "shared_dependencies_disclosed",
                ),
                "COMMON_MODE_MODEL_FAMILY_UNDISCLOSED",
            )

        if shared:
            _add(
                violations,
                not _flag(
                    facts,
                    "shared_dependencies_disclosed",
                ),
                "COMMON_MODE_DEPENDENCY_UNDISCLOSED",
            )

        _add(
            violations,
            not _flag(
                facts,
                "material_independent_path_present",
            ),
            "MATERIAL_INDEPENDENT_PATH_MISSING",
        )

    elif primary_requirement == "G3-BR-027":
        state = facts.get(
            "applicability_state"
        )

        if "applicability_state" in facts:
            _add(
                violations,
                state not in {
                    "APPLICABLE",
                    "NOT_APPLICABLE",
                },
                "INVALID_APPLICABILITY_STATE",
            )

        if state == "NOT_APPLICABLE":
            _add(
                violations,
                not _flag(
                    facts,
                    "governed_reason_present",
                ),
                "NOT_APPLICABLE_REASON_MISSING",
            )

            _add(
                violations,
                not _flag(
                    facts,
                    "control_genuinely_inapplicable",
                ),
                "NOT_APPLICABLE_USED_AS_ESCAPE",
            )

            _add(
                violations,
                _flag(
                    facts,
                    "omission_changes_claim_meaning",
                ),
                "NOT_APPLICABLE_CHANGES_CLAIM_MEANING",
            )

            _add(
                violations,
                not bool(
                    facts.get(
                        "environment_binding"
                    )
                ),
                "ENVIRONMENT_BINDING_MISSING",
            )

    return {
        "decision": (
            "REJECT"
            if violations
            else "ACCEPT"
        ),
        "violations": violations,
    }
