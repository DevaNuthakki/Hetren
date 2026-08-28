from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError

import pytest

from hvee.packs.asr.run04_protocol import (
    ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS,
    ASR_RUN04_BUDGET_BASIS_POINTS,
    ASR_RUN04_INVALID_CASE_FAMILIES,
    ASR_RUN04_PARTITIONS,
    ASR_RUN04_PREREQUISITE_COMMIT,
    ASR_RUN04_PROTOCOL_KEY,
    ASR_RUN04_PROTOCOL_SCHEMA_VERSION,
    ASR_RUN04_PROTOCOL_VERSION,
    ASR_RUN04_RANDOM_SEEDS,
    ASR_RUN04_REAL_EXECUTION_REPETITIONS,
    ASR_RUN04_SELECTOR_KEYS,
    ASR_RUN04_SEMANTIC_FAMILY_QUOTAS,
    build_asr_run04_ai_change_set,
    build_asr_run04_protocol_v1,
    calculate_asr_run04_protocol_sha256,
    verify_asr_run04_protocol_v1,
)


EXPECTED_RUN04_AI_CHANGE_SET_SHA256 = (
    "ff71db350ef0504cde13c34e6ea7b8ea3b6fcd17d86d2641d312d9d021dfaffe"
)
EXPECTED_RUN04_PROTOCOL_SHA256 = (
    "f3d0969f9bbae0c3627411aa6b8f9832e72e4fbacf473c62384181c9554cf846"
)


def _protocol():
    return build_asr_run04_protocol_v1()


def test_run04_protocol_is_deterministic_and_content_addressed():
    first = _protocol()
    second = _protocol()

    assert first == second
    assert first.sha256 == calculate_asr_run04_protocol_sha256(first.payload)
    assert first.sha256 == EXPECTED_RUN04_PROTOCOL_SHA256
    assert verify_asr_run04_protocol_v1(
        payload=first.payload,
        expected_sha256=first.sha256,
    )


def test_run04_protocol_identity_and_prerequisite_are_frozen():
    payload = _protocol().payload

    assert payload["schema_version"] == ASR_RUN04_PROTOCOL_SCHEMA_VERSION
    assert payload["artifact"] == {
        "key": ASR_RUN04_PROTOCOL_KEY,
        "version": ASR_RUN04_PROTOCOL_VERSION,
        "type": "asr_run04_preregistered_protocol",
    }
    assert payload["prerequisites"]["gate_zero_commit"] == (
        ASR_RUN04_PREREQUISITE_COMMIT
    )
    assert len(ASR_RUN04_PREREQUISITE_COMMIT) == 40


def test_run04_ai_change_set_binds_the_two_model_binaries():
    _, change_set = build_asr_run04_ai_change_set()
    payload = _protocol().payload

    assert payload["ai_change_set"] == {
        "payload": change_set.payload,
        "sha256": change_set.sha256,
    }
    assert change_set.sha256 == EXPECTED_RUN04_AI_CHANGE_SET_SHA256
    component = change_set.payload["components"][0]
    assert component["kind"] == "model"
    assert component["baseline_identity_sha256"] != (
        component["candidate_identity_sha256"]
    )
    assert change_set.payload["evidence_boundary"][
        "outcomes_observed"
    ] is False


def test_historical_runs_are_calibration_only_and_cannot_enter_holdout():
    historical = _protocol().payload["historical_calibration"]

    assert historical["b11h"]["total_real_transcription_count"] == 192
    assert historical["b11h"]["use"] == "calibration_only"
    assert historical["brutal_v1"]["case_count_per_model"] == 13
    assert historical["brutal_v1"]["use"] == (
        "renamed_control_calibration_only"
    )
    assert historical["exclusion"] == {
        "eligible_for_primary_run04_metrics": False,
        "eligible_for_fresh_holdout_membership": False,
        "eligible_for_algorithm_tuning": False,
        "historical_artifacts_rewritten": False,
    }


def test_fresh_corpus_has_128_valid_and_8_invalid_cases():
    corpus = _protocol().payload["fresh_corpus"]

    assert sum(ASR_RUN04_SEMANTIC_FAMILY_QUOTAS.values()) == 128
    assert set(ASR_RUN04_SEMANTIC_FAMILY_QUOTAS.values()) == {16}
    assert len(ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS) == 8
    assert min(ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS.values()) == 16
    assert len(ASR_RUN04_INVALID_CASE_FAMILIES) == 8
    assert corpus["valid_case_count"] == 128
    assert corpus["invalid_case_count"] == 8
    assert corpus["total_case_count"] == 136


def test_partitions_are_disjoint_by_policy_and_holdout_is_untunable():
    assert [item["key"] for item in ASR_RUN04_PARTITIONS] == [
        "development",
        "validation",
        "sealed_holdout",
    ]
    assert sum(item["valid_case_count"] for item in ASR_RUN04_PARTITIONS) == 128
    assert sum(item["invalid_case_count"] for item in ASR_RUN04_PARTITIONS) == 8

    by_key = {item["key"]: item for item in ASR_RUN04_PARTITIONS}
    assert by_key["development"]["tuning_allowed"] is True
    assert by_key["validation"]["tuning_allowed"] is False
    assert by_key["sealed_holdout"]["tuning_allowed"] is False
    assert by_key["sealed_holdout"]["label_visibility"] == (
        "blind_until_execution_completion"
    )


def test_speaker_and_commitment_controls_prevent_basic_leakage():
    corpus = _protocol().payload["fresh_corpus"]

    assert corpus["speaker_requirements"][
        "speaker_overlap_across_partitions"
    ] is False
    assert corpus["speaker_requirements"][
        "minimum_distinct_speakers"
    ] == 16
    assert corpus["commitment_order"][-1] == "open_no_hidden_labels"
    assert corpus["commitment_order"].index(
        "freeze_selector_implementations"
    ) < corpus["commitment_order"].index("open_no_hidden_labels")


def test_oracles_require_passports_mutations_and_blind_human_review():
    oracles = _protocol().payload["oracles"]
    existing = {item["key"]: item for item in oracles["existing_required"]}

    assert "hetren.asr.critical-number-fidelity.en-us" in existing
    assert "hetren.asr.critical-identifier-fidelity.en-us" in existing
    assert "hetren.asr.critical-terminology-fidelity.en-us" in existing
    assert existing["hetren.asr.wer.normalized-basic"]["decision_role"] == (
        "diagnostic_only"
    )
    assert existing["hetren.asr.cer.normalized-basic"]["decision_role"] == (
        "diagnostic_only"
    )
    assert all(
        item["status"] == "must_be_implemented_and_qualified"
        for item in oracles["new_required_before_execution"]
    )
    assert oracles["passport_requirements"][
        "unresolved_mutation_survival_allowed"
    ] is False
    assert oracles["human_adjudication"]["model_role_blinded"] is True
    assert oracles["human_adjudication"]["selector_blinded"] is True
    assert oracles["human_adjudication"]["independent_reviewers"] == 2


def test_ground_truth_execution_requires_three_full_replays():
    execution = _protocol().payload["ground_truth_execution"]

    assert ASR_RUN04_REAL_EXECUTION_REPETITIONS == 3
    assert execution["real_process_repetitions"] == 3
    assert execution["valid_transcriptions_per_repetition"] == 256
    assert execution["planned_valid_transcriptions"] == 768
    assert execution["planned_invalid_attempts"] == 48
    assert execution["full_replay_before_selector_scoring"] is True
    assert execution["outcomes_hidden_from_selectors"] is True
    assert execution["reproducibility_comparison"][
        "exact_transcript_identity_required"
    ] is True
    assert execution["reproducibility_comparison"][
        "runtime_duration_identity_required"
    ] is False


def test_selector_baselines_budgets_and_random_seeds_are_predeclared():
    benchmark = _protocol().payload["selector_benchmark"]

    assert tuple(item["key"] for item in benchmark["selectors"]) == (
        ASR_RUN04_SELECTOR_KEYS
    )
    assert len(ASR_RUN04_RANDOM_SEEDS) == 30
    assert len(set(ASR_RUN04_RANDOM_SEEDS)) == 30
    assert tuple(benchmark["random_seeds"]) == ASR_RUN04_RANDOM_SEEDS
    assert tuple(benchmark["budget_basis_points"]) == (
        ASR_RUN04_BUDGET_BASIS_POINTS
    )
    assert ASR_RUN04_BUDGET_BASIS_POINTS[-1] == 10000
    assert benchmark["equal_budget_required"] is True
    assert benchmark["ground_truth_labels_visible_during_selection"] is False
    assert benchmark["report_modes"] == [
        "raw_selector_only",
        "mandatory_safety_floor_plus_selector",
    ]


def test_run04_has_no_algorithmic_improvement_threshold():
    metrics = _protocol().payload["metrics"]

    assert metrics["algorithmic_improvement_threshold"] is None
    assert metrics["reporting"]["all_30_random_seeds_reported"] is True
    assert metrics["reporting"]["distribution_not_best_seed"] is True
    assert metrics["reporting"]["negative_results_preserved"] is True


def test_holdout_firewall_requires_fresh_protocol_after_unsealing():
    firewall = _protocol().payload["holdout_firewall"]

    assert firewall["labels_hidden_until_all_selectors_frozen"] is True
    assert firewall["dry_run_must_prove_no_label_oracle_leakage"] is True
    assert firewall["post_unseal_tuning_prohibited"] is True
    assert firewall[
        "post_unseal_change_requires_new_protocol_and_fresh_holdout"
    ] is True


def test_protocol_build_does_not_authorize_or_claim_execution():
    payload = _protocol().payload
    boundary = payload["evidence_boundary"]

    assert boundary == {
        "protocol_preregistered": True,
        "fresh_corpus_built": False,
        "selectors_implemented": False,
        "evaluator_passports_qualified": False,
        "holdout_dry_run_completed": False,
        "asr_execution_performed": False,
        "run04_completed": False,
        "governance_approval_granted": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
    }
    assert "assurancerank_superiority" in payload["claims_not_authorized"]
    assert "release_certification" in payload["claims_not_authorized"]


def test_rehashed_protocol_tampering_is_rejected():
    bundle = _protocol()
    altered = copy.deepcopy(bundle.payload)
    altered["evidence_boundary"]["run04_completed"] = True

    assert not verify_asr_run04_protocol_v1(
        payload=altered,
        expected_sha256=calculate_asr_run04_protocol_sha256(altered),
    )


def test_protocol_bundle_is_frozen():
    bundle = _protocol()

    with pytest.raises(FrozenInstanceError):
        bundle.sha256 = "0" * 64
