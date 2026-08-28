"""Pre-registered protocol for Hetren ASR Run-04.

Run-04 creates renamed, replayable ground truth before any AssuranceRank,
Behavioral Response Field, or HCAS claim is tested.  Historical B11H and
Brutal evidence are calibration-only.  Fresh development, validation, and
sealed-holdout cases form the Run-04 evidence population.

Building this artifact performs no transcription and grants no execution,
qualification, certification, production, or release authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from hvee.core.ai_change_set import (
    AIChangeComponent,
    AIChangeKind,
    AIChangeRiskTier,
    AIChangeSetDefinition,
    build_ai_change_set,
    verify_ai_change_set,
)
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_identifier_fidelity import (
    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
)
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
)


ASR_RUN04_PROTOCOL_SCHEMA_VERSION = 1
ASR_RUN04_PROTOCOL_KEY = "hetren.asr.run-04.renamed-ground-truth"
ASR_RUN04_PROTOCOL_VERSION = "1.0.0"
ASR_RUN04_PREREQUISITE_COMMIT = (
    "20b22211fe2e20bb5dcc92329c046d561680a74a"
)

ASR_RUN04_BRUTAL_V1_PLAN_SHA256 = (
    "e79fa34de900baf56db01cc3335d2fe95b6ae11840a813da8c54a1ee296b218d"
)
ASR_RUN04_BRUTAL_V1_SUITE_SHA256 = (
    "801b2e65efeb0138cdef9f09103987427232be523fada9cc92f6b15380362f7d"
)
ASR_RUN04_B11H_FINAL_ARTIFACT_SHA256 = (
    "21a19684920a2b27a25ae2fde0d57b0bd06c96cd7da95588eff5b936d7a955d2"
)
ASR_RUN04_B11H_PROCESS_REPRODUCIBILITY_SHA256 = (
    "a1674360751c03d1706bf6a977dbc9d8cea84bbed02d33def09b25d372ecb75d"
)
ASR_RUN04_B11H_VERIFICATION_SHA256 = (
    "66cc94e4f21bc46048ee380e2ebb1c8b820e6ef79fa06888b71762e9e99f6b7d"
)
ASR_RUN04_BRUTAL_RUN03_SUMMARY_FILE_SHA256 = (
    "fa00dc6256422fa6693df97ed220c463b59a6b6a400b6ecf7eb2a7b4e6449592"
)

ASR_RUN04_BASELINE_MODEL = {
    "role": "baseline",
    "model_name": "small.en",
    "repository": "Systran/faster-whisper-small.en",
    "revision": "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
    "model_binary_bytes": 483_545_366,
    "model_binary_sha256": (
        "62b2a45b05ee59acb4a5341b33ee35e0"
        "41395d378d418a18acfe4c9e768ee37a"
    ),
}
ASR_RUN04_CANDIDATE_MODEL = {
    "role": "candidate",
    "model_name": "large-v3-turbo",
    "repository": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "revision": "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
    "model_binary_bytes": 1_617_884_929,
    "model_binary_sha256": (
        "e76620f83d5f5b69efd3d87e3dc180c1"
        "bd21df9fbebacfd4335e5e1efcc018da"
    ),
}

ASR_RUN04_RANDOM_SEEDS = (
    100003,
    100019,
    100043,
    100049,
    100057,
    100069,
    100103,
    100109,
    100129,
    100151,
    100153,
    100169,
    100183,
    100189,
    100193,
    100207,
    100213,
    100237,
    100267,
    100271,
    100279,
    100291,
    100297,
    100313,
    100333,
    100343,
    100357,
    100361,
    100363,
    100379,
)
ASR_RUN04_BUDGET_BASIS_POINTS = (500, 1000, 2000, 4000, 10000)
ASR_RUN04_REAL_EXECUTION_REPETITIONS = 3

ASR_RUN04_SEMANTIC_FAMILY_QUOTAS = {
    "compound-critical-semantics": 16,
    "control-no-critical-content": 16,
    "critical-identifiers": 16,
    "critical-numbers": 16,
    "critical-terminology-and-names": 16,
    "long-form-and-multi-utterance": 16,
    "negation-and-polarity": 16,
    "silence-overlap-and-nonspeech": 16,
}
ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS = {
    "clean": 16,
    "lossy-codec": 16,
    "microphone-and-room": 16,
    "mixed-stress": 16,
    "noise": 16,
    "overlap": 16,
    "speed-and-prosody": 16,
    "telephony": 16,
}
ASR_RUN04_INVALID_CASE_FAMILIES = (
    "corrupt-container",
    "empty-audio",
    "excessive-duration",
    "mismatched-extension",
    "truncated-media",
    "unsupported-channel-layout",
    "unsupported-codec",
    "zero-byte-input",
)

ASR_RUN04_PARTITIONS = (
    {
        "key": "development",
        "valid_case_count": 64,
        "invalid_case_count": 4,
        "scenario_visibility": "source_visible",
        "label_visibility": "development_visible",
        "tuning_allowed": True,
    },
    {
        "key": "validation",
        "valid_case_count": 32,
        "invalid_case_count": 2,
        "scenario_visibility": "frozen_after_corpus_commitment",
        "label_visibility": "hidden_until_selector_freeze",
        "tuning_allowed": False,
    },
    {
        "key": "sealed_holdout",
        "valid_case_count": 32,
        "invalid_case_count": 2,
        "scenario_visibility": "runner_only_declared_metadata",
        "label_visibility": "blind_until_execution_completion",
        "tuning_allowed": False,
    },
)

ASR_RUN04_SELECTOR_KEYS = (
    "full_replay",
    "similarity_retrieval",
    "static_risk_heuristic",
    "stratified_random",
    "uniform_random",
)

_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class ASRRun04ProtocolBundle:
    """Canonical, non-authoritative Run-04 preregistration."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "Run-04 protocol payload must be a JSON object"
            )
        _require_sha256("Run-04 protocol SHA-256", self.sha256)


def _require_sha256(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise HveeContractError(
            "Run-04 protocol content must be canonical JSON"
        ) from error


def calculate_asr_run04_protocol_sha256(payload: object) -> str:
    """Return the canonical protocol identity."""

    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def build_asr_run04_ai_change_set():
    """Declare the model substitution under evaluation."""

    definition = AIChangeSetDefinition(
        change_set_key=(
            "hetren.asr.run-04.small-en-to-large-v3-turbo"
        ),
        change_set_version="1.0.0",
        baseline_system_key="hetren.asr.system.small-en",
        candidate_system_key="hetren.asr.system.large-v3-turbo",
        risk_tier=AIChangeRiskTier.CRITICAL,
        purpose=(
            "Measure behavior changes caused by the frozen ASR model "
            "substitution without declaring a model winner."
        ),
        components=(
            AIChangeComponent(
                kind=AIChangeKind.MODEL,
                component_key="asr.model.primary",
                baseline_identity_sha256=(
                    ASR_RUN04_BASELINE_MODEL["model_binary_sha256"]
                ),
                candidate_identity_sha256=(
                    ASR_RUN04_CANDIDATE_MODEL["model_binary_sha256"]
                ),
                declared_behavior_impacts=(
                    "asr.behavior.channel-robustness",
                    "asr.behavior.critical-identifier-fidelity",
                    "asr.behavior.critical-number-fidelity",
                    "asr.behavior.critical-terminology-fidelity",
                    "asr.behavior.negation-preservation",
                    "asr.behavior.transcript-accuracy",
                ),
            ),
        ),
        declared_unknowns=(
            "asr.unknown.cross-host-reproducibility",
            "asr.unknown.future-distributions",
            "asr.unknown.non-english-languages",
            "asr.unknown.third-party-architectures",
            "asr.unknown.unseen-speaker-populations",
        ),
    )
    return definition, build_ai_change_set(definition)


def _validate_protocol_constants() -> None:
    for value in (
        ASR_RUN04_BRUTAL_V1_PLAN_SHA256,
        ASR_RUN04_BRUTAL_V1_SUITE_SHA256,
        ASR_RUN04_B11H_FINAL_ARTIFACT_SHA256,
        ASR_RUN04_B11H_PROCESS_REPRODUCIBILITY_SHA256,
        ASR_RUN04_B11H_VERIFICATION_SHA256,
        ASR_RUN04_BRUTAL_RUN03_SUMMARY_FILE_SHA256,
        ASR_RUN04_BASELINE_MODEL["model_binary_sha256"],
        ASR_RUN04_CANDIDATE_MODEL["model_binary_sha256"],
    ):
        _require_sha256("Run-04 bound identity", value)
    if _GIT_COMMIT.fullmatch(ASR_RUN04_PREREQUISITE_COMMIT) is None:
        raise HveeContractError(
            "Run-04 prerequisite commit must be a full Git identity"
        )
    if (
        len(ASR_RUN04_RANDOM_SEEDS) != 30
        or len(set(ASR_RUN04_RANDOM_SEEDS)) != 30
        or ASR_RUN04_RANDOM_SEEDS != tuple(sorted(ASR_RUN04_RANDOM_SEEDS))
    ):
        raise HveeContractError(
            "Run-04 requires 30 unique ordered random seeds"
        )
    if ASR_RUN04_BUDGET_BASIS_POINTS != (
        500,
        1000,
        2000,
        4000,
        10000,
    ):
        raise HveeContractError("Run-04 budget schedule changed")
    if ASR_RUN04_REAL_EXECUTION_REPETITIONS != 3:
        raise HveeContractError("Run-04 requires three real repetitions")
    if sum(ASR_RUN04_SEMANTIC_FAMILY_QUOTAS.values()) != 128:
        raise HveeContractError("Run-04 must contain 128 fresh valid cases")
    if len(ASR_RUN04_SEMANTIC_FAMILY_QUOTAS) != 8:
        raise HveeContractError("Run-04 semantic family count changed")
    if any(
        minimum < 16
        for minimum in ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS.values()
    ):
        raise HveeContractError(
            "Run-04 acoustic families require at least 16 cases"
        )
    if len(ASR_RUN04_INVALID_CASE_FAMILIES) != 8:
        raise HveeContractError("Run-04 invalid-case family count changed")
    if sum(item["valid_case_count"] for item in ASR_RUN04_PARTITIONS) != 128:
        raise HveeContractError("Run-04 valid partition count changed")
    if sum(item["invalid_case_count"] for item in ASR_RUN04_PARTITIONS) != 8:
        raise HveeContractError("Run-04 invalid partition count changed")
    if ASR_RUN04_SELECTOR_KEYS != tuple(sorted(ASR_RUN04_SELECTOR_KEYS)):
        raise HveeContractError("Run-04 selector keys must remain ordered")
    definition, bundle = build_asr_run04_ai_change_set()
    if not verify_ai_change_set(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
        definition=definition,
    ):
        raise HveeContractError("Run-04 AIChangeSet failed verification")


def _evaluator_identity(evaluator) -> dict[str, object]:
    return {
        "key": evaluator.key,
        "version": evaluator.version,
        "evaluation_type": evaluator.evaluation_type,
    }


def build_asr_run04_protocol_v1() -> ASRRun04ProtocolBundle:
    """Build the exact Run-04 protocol without authorizing execution."""

    _validate_protocol_constants()
    _, change_set = build_asr_run04_ai_change_set()

    payload: dict[str, object] = {
        "schema_version": ASR_RUN04_PROTOCOL_SCHEMA_VERSION,
        "artifact": {
            "key": ASR_RUN04_PROTOCOL_KEY,
            "version": ASR_RUN04_PROTOCOL_VERSION,
            "type": "asr_run04_preregistered_protocol",
        },
        "objective": (
            "Create clean renamed ASR ground truth and reproducible selector "
            "baselines before adaptive assurance intelligence is introduced."
        ),
        "prerequisites": {
            "gate_zero_commit": ASR_RUN04_PREREQUISITE_COMMIT,
            "working_tree_clean_required": True,
            "mandatory_repository_gate_required": True,
            "identity_migration_check_required": True,
        },
        "ai_change_set": {
            "payload": change_set.payload,
            "sha256": change_set.sha256,
        },
        "historical_calibration": {
            "b11h": {
                "case_count_per_model": 32,
                "model_count": 2,
                "process_run_count": 3,
                "total_real_transcription_count": 192,
                "final_artifact_sha256": (
                    ASR_RUN04_B11H_FINAL_ARTIFACT_SHA256
                ),
                "process_reproducibility_sha256": (
                    ASR_RUN04_B11H_PROCESS_REPRODUCIBILITY_SHA256
                ),
                "frozen_verification_sha256": (
                    ASR_RUN04_B11H_VERIFICATION_SHA256
                ),
                "same_host_process_reproducibility_verified": True,
                "cross_host_reproducibility_verified": None,
                "use": "calibration_only",
            },
            "brutal_v1": {
                "case_count_per_model": 13,
                "model_count": 2,
                "plan_sha256": ASR_RUN04_BRUTAL_V1_PLAN_SHA256,
                "suite_evidence_sha256": ASR_RUN04_BRUTAL_V1_SUITE_SHA256,
                "run03_summary_file_sha256": (
                    ASR_RUN04_BRUTAL_RUN03_SUMMARY_FILE_SHA256
                ),
                "use": "renamed_control_calibration_only",
            },
            "exclusion": {
                "eligible_for_primary_run04_metrics": False,
                "eligible_for_fresh_holdout_membership": False,
                "eligible_for_algorithm_tuning": False,
                "historical_artifacts_rewritten": False,
            },
        },
        "systems": {
            "frozen_models": [
                dict(ASR_RUN04_BASELINE_MODEL),
                dict(ASR_RUN04_CANDIDATE_MODEL),
            ],
            "runtime": {
                "provider": "faster_whisper",
                "device": "cpu",
                "compute_type": "int8_float32",
                "network_allowed": False,
            },
            "architecture_extension": {
                "desired": True,
                "required_when_licensing_and_environment_allow": True,
                "identity_must_be_frozen_before_labels_open": True,
                "absence_requires_explicit_limitation": True,
            },
        },
        "fresh_corpus": {
            "valid_case_count": 128,
            "invalid_case_count": 8,
            "total_case_count": 136,
            "semantic_family_exact_quotas": dict(
                ASR_RUN04_SEMANTIC_FAMILY_QUOTAS
            ),
            "acoustic_family_minimums": dict(
                ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS
            ),
            "invalid_case_families": list(
                ASR_RUN04_INVALID_CASE_FAMILIES
            ),
            "partitions": [dict(item) for item in ASR_RUN04_PARTITIONS],
            "speaker_requirements": {
                "minimum_distinct_speakers": 16,
                "minimum_human_speakers_when_rights_allow": 8,
                "speaker_overlap_across_partitions": False,
                "demographic_balance_report_required": True,
                "accent_coverage_report_required": True,
            },
            "content_requirements": {
                "critical_numbers": True,
                "critical_identifiers": True,
                "critical_terminology_and_names": True,
                "negation_and_polarity": True,
                "compound_semantics": True,
                "no_critical_content_controls": True,
                "unsupported_and_invalid_inputs": True,
            },
            "commitment_order": [
                "freeze_case_specifications",
                "freeze_source_and_rights_records",
                "materialize_and_hash_media",
                "freeze_partition_commitments",
                "freeze_evaluator_passports",
                "freeze_selector_implementations",
                "open_no_hidden_labels",
            ],
        },
        "oracles": {
            "existing_required": [
                _evaluator_identity(
                    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR
                ),
                _evaluator_identity(CRITICAL_NUMBER_FIDELITY_EVALUATOR),
                _evaluator_identity(
                    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR
                ),
                {
                    **_evaluator_identity(NORMALIZED_WER_EVALUATOR),
                    "metric_key": NORMALIZED_WER_METRIC.key,
                    "metric_version": NORMALIZED_WER_METRIC.version,
                    "decision_role": "diagnostic_only",
                },
                {
                    **_evaluator_identity(NORMALIZED_CER_EVALUATOR),
                    "metric_key": NORMALIZED_CER_METRIC.key,
                    "metric_version": NORMALIZED_CER_METRIC.version,
                    "decision_role": "diagnostic_only",
                },
            ],
            "new_required_before_execution": [
                {
                    "key": "hetren.asr.negation-fidelity.en-us",
                    "version": "1.0.0",
                    "status": "must_be_implemented_and_qualified",
                },
                {
                    "key": "hetren.asr.media-validity",
                    "version": "1.0.0",
                    "status": "must_be_implemented_and_qualified",
                },
            ],
            "passport_requirements": {
                "identity_and_applicability": True,
                "normalizer_and_dependency_identities": True,
                "mutation_campaign_required": True,
                "sensitivity_specificity_abstention_report_required": True,
                "known_limitations_required": True,
                "expiry_and_supersession_required": True,
                "deterministic_oracle_mutation_detection_required": True,
                "unresolved_mutation_survival_allowed": False,
            },
            "human_adjudication": {
                "model_role_blinded": True,
                "selector_blinded": True,
                "independent_reviewers": 2,
                "third_adjudicator_on_disagreement": True,
                "review_all_critical_disagreements": True,
                "review_all_unknown_or_conflicting_results": True,
                "stratified_agreement_audit_basis_points": 1000,
                "reviewer_identity_authority_and_rationale_recorded": True,
            },
        },
        "ground_truth_execution": {
            "real_process_repetitions": (
                ASR_RUN04_REAL_EXECUTION_REPETITIONS
            ),
            "valid_transcriptions_per_repetition": 256,
            "invalid_attempts_per_repetition": 16,
            "planned_valid_transcriptions": 768,
            "planned_invalid_attempts": 48,
            "fresh_provider_instance_per_model_per_repetition": True,
            "full_replay_before_selector_scoring": True,
            "outcomes_hidden_from_selectors": True,
            "preserve_partial_failed_invalid_and_unknown": True,
            "reproducibility_comparison": {
                "exact_transcript_identity_required": True,
                "exact_normalized_transcript_identity_required": True,
                "exact_deterministic_evaluator_identity_required": True,
                "exact_failure_label_identity_required": True,
                "runtime_duration_identity_required": False,
                "pid_timestamp_and_run_id_identity_required": False,
            },
        },
        "selector_benchmark": {
            "selectors": [
                {
                    "key": "full_replay",
                    "seeded": False,
                    "definition": "all eligible cases in canonical order",
                },
                {
                    "key": "similarity_retrieval",
                    "seeded": False,
                    "definition": (
                        "deterministic TF-IDF cosine over allowed change and "
                        "scenario metadata with lexical case-id tie breaking"
                    ),
                    "outcome_features_allowed": False,
                },
                {
                    "key": "static_risk_heuristic",
                    "seeded": False,
                    "definition": (
                        "declared severity, mandatory-contract status, semantic "
                        "dimension count, and acoustic stress only"
                    ),
                    "observed_outcomes_allowed": False,
                },
                {
                    "key": "stratified_random",
                    "seeded": True,
                    "strata": [
                        "partition",
                        "semantic_family",
                        "acoustic_family",
                        "validity_class",
                    ],
                },
                {
                    "key": "uniform_random",
                    "seeded": True,
                },
            ],
            "random_seeds": list(ASR_RUN04_RANDOM_SEEDS),
            "budget_basis_points": list(ASR_RUN04_BUDGET_BASIS_POINTS),
            "cost_basis": "measured_model_seconds",
            "equal_budget_required": True,
            "report_modes": [
                "raw_selector_only",
                "mandatory_safety_floor_plus_selector",
            ],
            "mandatory_safety_floor_shared_by_all_selectors": True,
            "ground_truth_labels_visible_during_selection": False,
            "selection_trace_and_tie_breaks_preserved": True,
        },
        "metrics": {
            "primary": [
                "critical_failure_recall_at_matched_cost",
                "critical_failures_found_per_model_second",
                "unsafe_false_pass_rate",
            ],
            "secondary": [
                "apfdc",
                "invalid_classification_accuracy",
                "selector_stability",
                "time_to_first_critical_failure",
                "total_failure_recall",
                "unknown_and_conflict_rate",
            ],
            "reporting": {
                "all_30_random_seeds_reported": True,
                "distribution_not_best_seed": True,
                "per_partition_results_required": True,
                "per_family_results_required": True,
                "negative_results_preserved": True,
                "missing_results_never_imputed_as_pass": True,
            },
            "algorithmic_improvement_threshold": None,
            "reason": (
                "Run-04 measures baselines and infrastructure; it does not "
                "test AssuranceRank superiority."
            ),
        },
        "holdout_firewall": {
            "commitment_before_execution_required": True,
            "case_membership_hashes_sealed": True,
            "labels_hidden_until_all_selectors_frozen": True,
            "selector_code_hashes_frozen_before_unsealing": True,
            "dry_run_uses_synthetic_non_holdout_records": True,
            "dry_run_must_prove_no_label_oracle_leakage": True,
            "post_unseal_tuning_prohibited": True,
            "post_unseal_change_requires_new_protocol_and_fresh_holdout": True,
        },
        "execution_order": [
            "verify_gate_zero_and_protocol_identity",
            "bind_historical_calibration_without_tuning",
            "build_and_commit_fresh_corpus",
            "qualify_and_freeze_evaluator_passports",
            "implement_and_freeze_baseline_selectors",
            "dry_run_holdout_firewall",
            "execute_three_full_replay_ground_truth_repetitions",
            "freeze_reconciled_ground_truth",
            "score_selectors_offline_at_equal_budgets",
            "execute_blind_holdout_once",
            "compile_statistics_and_evidence_manifest",
            "record_human_review_and_limitations",
        ],
        "exit_gate": {
            "mandatory_repository_gate_green": True,
            "protocol_and_all_input_identities_verified": True,
            "fresh_corpus_contract_satisfied": True,
            "three_ground_truth_repetitions_complete": True,
            "semantic_outputs_reproduced_exactly": True,
            "evaluator_passports_qualified": True,
            "holdout_firewall_dry_run_passed": True,
            "all_selector_baselines_reported": True,
            "human_adjudication_complete": True,
            "unknown_invalid_and_negative_results_preserved": True,
            "independent_replay_package_complete": True,
        },
        "claims_not_authorized": [
            "assurancerank_superiority",
            "cross_company_transfer",
            "cross_domain_generality",
            "cross_host_reproducibility",
            "production_safety",
            "regulatory_compliance",
            "release_certification",
        ],
        "evidence_boundary": {
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
        },
    }
    return ASRRun04ProtocolBundle(
        payload=payload,
        sha256=calculate_asr_run04_protocol_sha256(payload),
    )


def verify_asr_run04_protocol_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> bool:
    """Verify exact protocol reconstruction and content identity."""

    try:
        expected = _require_sha256(
            "expected Run-04 protocol SHA-256",
            expected_sha256,
        )
        if not isinstance(payload, dict):
            return False
        rebuilt = build_asr_run04_protocol_v1()
        return (
            calculate_asr_run04_protocol_sha256(payload) == expected
            and payload == rebuilt.payload
            and expected == rebuilt.sha256
        )
    except (HveeContractError, TypeError, ValueError):
        return False


__all__ = [
    "ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS",
    "ASR_RUN04_BASELINE_MODEL",
    "ASR_RUN04_BUDGET_BASIS_POINTS",
    "ASR_RUN04_CANDIDATE_MODEL",
    "ASR_RUN04_INVALID_CASE_FAMILIES",
    "ASR_RUN04_PARTITIONS",
    "ASR_RUN04_PREREQUISITE_COMMIT",
    "ASR_RUN04_PROTOCOL_KEY",
    "ASR_RUN04_PROTOCOL_SCHEMA_VERSION",
    "ASR_RUN04_PROTOCOL_VERSION",
    "ASR_RUN04_RANDOM_SEEDS",
    "ASR_RUN04_REAL_EXECUTION_REPETITIONS",
    "ASR_RUN04_SELECTOR_KEYS",
    "ASR_RUN04_SEMANTIC_FAMILY_QUOTAS",
    "ASRRun04ProtocolBundle",
    "build_asr_run04_ai_change_set",
    "build_asr_run04_protocol_v1",
    "calculate_asr_run04_protocol_sha256",
    "verify_asr_run04_protocol_v1",
]
