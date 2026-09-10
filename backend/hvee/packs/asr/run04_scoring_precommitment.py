"""Run-04 Public-v2 deterministic scoring precommitment.

This module freezes the scoring policy before Run-04 prediction values are
used for model-quality evaluation.

It deliberately preserves the historical Run-04 protocol. Critical-number
v1.2 is recorded as a separately qualified post-execution, pre-scoring
correction rather than being retroactively substituted into that protocol.

This precommitment does not itself open Run-04 prediction or reference text,
score models, grant release authority, or inspect a private holdout.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_identifier_fidelity import (
    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
    EN_US_CRITICAL_IDENTIFIER_PROFILE,
)
from hvee.packs.asr.critical_number_assurance_v1_2 import (
    build_critical_number_assurance_v1_2_candidate,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    EN_US_CRITICAL_NUMBER_PROFILE,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.run04_protocol import build_asr_run04_protocol_v1


RUN04_SCORING_PRECOMMITMENT_SCHEMA_VERSION = 1
RUN04_SCORING_PRECOMMITMENT_KEY = (
    "hetren.asr.run04-public-v2.scoring-precommitment"
)
RUN04_SCORING_PRECOMMITMENT_VERSION = "1.0.1"

RUN04_PRIOR_SCORING_PRECOMMITMENT_SHA256 = (
    "2bffc9b2a51d9b07f8fa6da5483cdbab"
    "9ca6c8ba32dffb55d3c32cea75c343d1"
)

RUN04_FIRST_SCORING_ATTEMPT_CODE_COMMIT = (
    "72440515cb6394eaf7840cb96fe91e34a1b8f555"
)

RUN04_EXECUTION_SUCCESS_STATUS = "SUCCESS"
RUN04_OPERATOR_INTERRUPTION_STATUS = "ERROR"

RUN04_SCORING_BASE_COMMIT = (
    "4b412b098190928e3377e5054c8b4bfc6c7271d0"
)

RUN04_PROTOCOL_SHA256 = (
    "f3d0969f9bbae0c3627411aa6b8f9832"
    "e72e4fbacf473c62384181c9554cf846"
)

RUN04_CRITICAL_NUMBER_V1_2_ASSURANCE_SHA256 = (
    "d155a2d7b0792319e736bf87433442b3"
    "70181a403341fc39a8de97b10ed22717"
)

RUN04_EXPECTED_TERMINAL_SLOTS = 42472
RUN04_EXPECTED_RECORDINGS = 21236
RUN04_EXPECTED_SUCCESSFUL_TRANSCRIPTS = 42471
RUN04_EXPECTED_OPERATOR_INTERRUPTION_SLOTS = 1
RUN04_EXPECTED_GLOBAL_COMPLETE_PAIRS = 21235

RUN04_OPERATOR_INTERRUPTION_SLOT_ORDINAL = 293
RUN04_OPERATOR_INTERRUPTION_MODEL_ROLE = "baseline"

RUN04_MODEL_ROLES = ("baseline", "candidate")

RUN04_EXPECTED_PROMPT_DEVELOPMENT_COMPLETE_PAIRS = 16988
RUN04_EXPECTED_PROMPT_VALIDATION_COMPLETE_PAIRS = 4247
RUN04_EXPECTED_SPEAKER_VALIDATION_COMPLETE_PAIRS = 3627
RUN04_EXPECTED_LINE_VALIDATION_COMPLETE_PAIRS = 3575
RUN04_EXPECTED_CRITICAL_NUMBER_VALIDATION_COMPLETE_PAIRS = 875

RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS = {
    "critical_number_prompt_generalization": {
        "development": 3501,
        "outside_lane_universe": 16859,
        "validation": 875,
    },
    "prompt_generalization": {
        "development": 16988,
        "validation": 4247,
    },
    "slr83_line_generalization": {
        "development": 14302,
        "outside_lane_universe": 3358,
        "validation": 3575,
    },
    "slr83_speaker_generalization": {
        "development": 14250,
        "outside_lane_universe": 3358,
        "validation": 3627,
    },
}

RUN04_SOURCE_BINDINGS = {
    "run04_protocol.py": (
        "05aebf5c38854e0b65b7543273354cfe"
        "cbce06c473190c2b5c9ba376b167b169"
    ),
    "normalized_evaluation.py": (
        "110719af47a24e43fbb0c2e6233e9318"
        "04140d0ce0fdfc1e41c9f7cc1caadd78"
    ),
    "critical_number_fidelity.py": (
        "415a58057006fb6b334972b7bdec7e5a"
        "20d6868ac7fc2f1d7b972ec000c603c4"
    ),
    "critical_identifier_fidelity.py": (
        "ed9fa0dea74a95ff3842caed161e7e1b"
        "d9af7094feeff8e1f1cdce486280e09f"
    ),
}

RUN04_INPUT_ARTIFACTS = {
    "execution_plan": {
        "relative_path": (
            "run04-v2-model-execution-precommitment-"
            "20260830T045615Z/model-execution-plan.jsonl"
        ),
        "sha256": (
            "0b4ec98a0b3113fd184ce6602950bb43"
            "7956c5dff01d49d27fc9cc3a70312e95"
        ),
        "rows": 42472,
    },
    "raw_execution_results": {
        "relative_path": (
            "run04-v2-corrected-model-execution-"
            "be5a0edf71159b2a-ca082978e85ab184/"
            "raw-execution-results.jsonl"
        ),
        "sha256": (
            "3feaa0100194c3ae0f50e57631a6c159"
            "37ca06b7fe9ba4ac58ef37661548c9aa"
        ),
        "rows": 42472,
    },
    "reference_records": {
        "relative_path": (
            "run04-v2-reference-candidate-"
            "20260909T193622945125Z/reference-records.jsonl"
        ),
        "sha256": (
            "cf3372f365d2e76032eb6c141c90f396"
            "684e5761faac0fdd7d918f174d360724"
        ),
        "rows": 21236,
    },
    "official_membership_freeze": {
        "relative_path": (
            "run04-v2-official-membership-materialization-"
            "20260830T035031Z/freeze-manifest.json"
        ),
        "sha256": (
            "8fa779e86fd439eebcafb3610e4bd65d"
            "718a1d564cb7e5222d325e2fb7587be9"
        ),
        "rows": None,
    },
    "execution_freeze": {
        "relative_path": (
            "run04-v2-corrected-model-execution-"
            "be5a0edf71159b2a-ca082978e85ab184/"
            "freeze-manifest.json"
        ),
        "sha256": (
            "0515b3849bab54bc97c34ab4438d9980"
            "99d42a40f34572c993f34aad0628e645"
        ),
        "rows": None,
    },
    "slot_293_adjudication": {
        "relative_path": (
            "run04-v2-corrected-model-execution-"
            "be5a0edf71159b2a-ca082978e85ab184/"
            "slot-293-operator-interruption-adjudication.json"
        ),
        "sha256": (
            "caf468c4890dc236fbfe85e4d2899f13"
            "f1486702cf5bf1e3d302b320cfd3b5d2"
        ),
        "rows": None,
    },
    "slot_293_terminalization_freeze": {
        "relative_path": (
            "run04-v2-corrected-model-execution-"
            "be5a0edf71159b2a-ca082978e85ab184/"
            "slot-293-operator-interruption-terminalization-freeze.json"
        ),
        "sha256": (
            "ee2c8eba5ee146e1eb78510835c3be51"
            "348d11af84425023156c9856880e780e"
        ),
        "rows": None,
    },
}


def _canonicalize(value: object, *, name: str) -> object:
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain deterministic JSON"
        ) from exc


def calculate_run04_scoring_precommitment_sha256(
    payload: object,
) -> str:
    canonical = _canonicalize(
        payload,
        name="Run-04 scoring precommitment",
    )

    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError as exc:
        raise HveeContractError(
            f"required scoring dependency is missing: {package}"
        ) from exc


def _evaluator_identity(evaluator) -> dict[str, str]:
    return {
        "key": evaluator.key,
        "version": evaluator.version,
        "evaluation_type": evaluator.evaluation_type,
    }


@dataclass(frozen=True, slots=True)
class ASRRun04ScoringPrecommitmentBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if (
            len(self.sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.sha256
            )
        ):
            raise HveeContractError(
                "Run-04 scoring precommitment SHA-256 is invalid"
            )

        expected = calculate_run04_scoring_precommitment_sha256(
            self.payload
        )

        if self.sha256 != expected:
            raise HveeContractError(
                "Run-04 scoring precommitment SHA-256 "
                "does not match its payload"
            )


def build_run04_scoring_precommitment_v1(
) -> ASRRun04ScoringPrecommitmentBundle:
    protocol = build_asr_run04_protocol_v1()

    if protocol.sha256 != RUN04_PROTOCOL_SHA256:
        raise HveeContractError(
            "Run-04 historical protocol identity changed"
        )

    assurance = build_critical_number_assurance_v1_2_candidate()

    if (
        assurance.sha256
        != RUN04_CRITICAL_NUMBER_V1_2_ASSURANCE_SHA256
    ):
        raise HveeContractError(
            "critical-number v1.2 assurance identity changed"
        )

    if CRITICAL_NUMBER_FIDELITY_EVALUATOR.version != "1.1.0":
        raise HveeContractError(
            "historical default critical-number evaluator changed"
        )

    if CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.version != "1.2.0":
        raise HveeContractError(
            "Run-04 corrected critical-number evaluator changed"
        )

    runtime = {
        "python": sys.version.split()[0],
        "unicode": unicodedata.unidata_version,
        "jiwer": _package_version("jiwer"),
        "rapidfuzz": _package_version("rapidfuzz"),
        "numpy": _package_version("numpy"),
    }

    expected_runtime = {
        "python": "3.13.1",
        "unicode": "15.1.0",
        "jiwer": "4.0.0",
        "rapidfuzz": "3.14.5",
        "numpy": "2.5.2",
    }

    if runtime != expected_runtime:
        raise HveeContractError(
            "Run-04 scoring runtime identity changed: "
            f"{runtime!r}"
        )

    payload = {
        "schema_version": RUN04_SCORING_PRECOMMITMENT_SCHEMA_VERSION,
        "precommitment": {
            "key": RUN04_SCORING_PRECOMMITMENT_KEY,
            "version": RUN04_SCORING_PRECOMMITMENT_VERSION,
            "status": "experimental",
            "base_evaluator_commit": RUN04_SCORING_BASE_COMMIT,
            "supersedes_precommitment_sha256": (
                RUN04_PRIOR_SCORING_PRECOMMITMENT_SHA256
            ),
            "production_qualified": False,
            "release_decision_authority": False,
            "certification_issued": False,
        },
        "historical_protocol": {
            "sha256": RUN04_PROTOCOL_SHA256,
            "critical_number_evaluator_version": "1.1.0",
            "protocol_is_not_rewritten": True,
        },
        "post_execution_pre_scoring_correction": {
            "applies": True,
            "reason": (
                "terminal punctuation boundary defect discovered "
                "before Run-04 model-quality scoring"
            ),
            "historical_evaluator_version": "1.1.0",
            "corrected_evaluator_version": "1.2.0",
            "assurance_sha256": (
                RUN04_CRITICAL_NUMBER_V1_2_ASSURANCE_SHA256
            ),
            "correction_was_sealed_before_scoring": True,
        },
        "post_unlock_pre_result_publication_correction": {
            "applies": True,
            "correction_type": (
                "execution_status_serialization_compatibility"
            ),
            "failed_scoring_code_commit": (
                RUN04_FIRST_SCORING_ATTEMPT_CODE_COMMIT
            ),
            "prior_precommitment_sha256": (
                RUN04_PRIOR_SCORING_PRECOMMITMENT_SHA256
            ),
            "observed_complete_result_status": (
                RUN04_EXECUTION_SUCCESS_STATUS
            ),
            "observed_governed_interruption_status": (
                RUN04_OPERATOR_INTERRUPTION_STATUS
            ),
            "status_comparison_is_case_sensitive": True,
            "first_attempt_opened_real_prediction_values": True,
            "first_attempt_opened_real_reference_values": True,
            "transient_pair_evaluation_may_have_occurred": True,
            "published_model_quality_summary_before_correction": False,
            "persisted_scoring_artifacts_before_correction": False,
            "model_quality_outcome_inspected_before_correction": False,
            "hidden_holdout_opened_before_correction": False,
            "asr_execution_performed_before_correction": False,
        },
        "runtime": runtime,
        "source_bindings": RUN04_SOURCE_BINDINGS,
        "input_artifacts": RUN04_INPUT_ARTIFACTS,
        "accounting": {
            "terminal_slots": RUN04_EXPECTED_TERMINAL_SLOTS,
            "recordings": RUN04_EXPECTED_RECORDINGS,
            "successful_transcripts": (
                RUN04_EXPECTED_SUCCESSFUL_TRANSCRIPTS
            ),
            "expected_execution_status_counts": {
                RUN04_EXECUTION_SUCCESS_STATUS: (
                    RUN04_EXPECTED_SUCCESSFUL_TRANSCRIPTS
                ),
                RUN04_OPERATOR_INTERRUPTION_STATUS: (
                    RUN04_EXPECTED_OPERATOR_INTERRUPTION_SLOTS
                ),
            },
            "operator_interruption_slots": (
                RUN04_EXPECTED_OPERATOR_INTERRUPTION_SLOTS
            ),
            "global_complete_pairs": (
                RUN04_EXPECTED_GLOBAL_COMPLETE_PAIRS
            ),
            "expected_lane_complete_pairs": {
                "prompt_development": (
                    RUN04_EXPECTED_PROMPT_DEVELOPMENT_COMPLETE_PAIRS
                ),
                "prompt_validation": (
                    RUN04_EXPECTED_PROMPT_VALIDATION_COMPLETE_PAIRS
                ),
                "speaker_validation": (
                    RUN04_EXPECTED_SPEAKER_VALIDATION_COMPLETE_PAIRS
                ),
                "line_validation": (
                    RUN04_EXPECTED_LINE_VALIDATION_COMPLETE_PAIRS
                ),
                "critical_number_prompt_validation": (
                    RUN04_EXPECTED_CRITICAL_NUMBER_VALIDATION_COMPLETE_PAIRS
                ),
            },
            "expected_lane_role_complete_pairs": {
                lane_key: dict(role_counts)
                for lane_key, role_counts in sorted(
                    RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS.items()
                )
            },
        },
        "pairing_policy": {
            "model_roles": list(RUN04_MODEL_ROLES),
            "recording_key": "recording_id",
            "recording_identity_key": "recording_identity_sha256",
            "reference_field": "reference_text",
            "generated_field": "raw_transcript_text",
            "complete_result_status": (
                RUN04_EXECUTION_SUCCESS_STATUS
            ),
            "governed_interruption_status": (
                RUN04_OPERATOR_INTERRUPTION_STATUS
            ),
            "status_comparison_is_case_sensitive": True,
            "unrecognized_execution_status_rejected": True,
            "pair_requires_both_model_transcripts": True,
            "all_observed_lane_role_categories_are_reported": True,
            "lane_category_selection_after_scoring_allowed": False,
        },
        "operator_interruption_policy": {
            "execution_slot_ordinal": (
                RUN04_OPERATOR_INTERRUPTION_SLOT_ORDINAL
            ),
            "model_role": RUN04_OPERATOR_INTERRUPTION_MODEL_ROLE,
            "quality_semantics": "missing_quality_evidence",
            "excluded_from_model_quality_denominator": True,
            "must_not_be_interpreted_as_empty_transcript": True,
            "must_not_be_interpreted_as_model_failure": True,
        },
        "active_oracles": {
            "normalized_wer": {
                **_evaluator_identity(NORMALIZED_WER_EVALUATOR),
                "metric_key": NORMALIZED_WER_METRIC.key,
                "metric_version": NORMALIZED_WER_METRIC.version,
                "role": "diagnostic_only",
                "lower_is_better": True,
            },
            "normalized_cer": {
                **_evaluator_identity(NORMALIZED_CER_EVALUATOR),
                "metric_key": NORMALIZED_CER_METRIC.key,
                "metric_version": NORMALIZED_CER_METRIC.version,
                "role": "diagnostic_only",
                "lower_is_better": True,
            },
            "critical_number": {
                **_evaluator_identity(
                    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2
                ),
                "profile_key": EN_US_CRITICAL_NUMBER_PROFILE.key,
                "profile_version": (
                    EN_US_CRITICAL_NUMBER_PROFILE.version
                ),
                "assurance_sha256": (
                    RUN04_CRITICAL_NUMBER_V1_2_ASSURANCE_SHA256
                ),
                "role": "report_only",
            },
            "critical_identifier": {
                **_evaluator_identity(
                    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR
                ),
                "profile_key": (
                    EN_US_CRITICAL_IDENTIFIER_PROFILE.key
                ),
                "profile_version": (
                    EN_US_CRITICAL_IDENTIFIER_PROFILE.version
                ),
                "role": "report_only",
            },
        },
        "not_activated_by_this_scoring_pass": {
            "critical_terminology": {
                "reason": (
                    "no exact Run-04 terminology vocabulary/profile "
                    "binding was established in the pre-scoring capture"
                ),
                "must_not_be_inferred_from_model_outputs": True,
            },
            "negation_fidelity": {
                "reason": (
                    "historical protocol required a separately "
                    "implemented and qualified evaluator"
                ),
            },
            "media_validity": {
                "reason": (
                    "historical protocol required a separately "
                    "implemented and qualified oracle"
                ),
            },
        },
        "reporting_policy": {
            "raw_reference_text_persisted_in_scored_output": False,
            "raw_prediction_text_persisted_in_scored_output": False,
            "reference_text_sha256_persisted": True,
            "prediction_text_sha256_persisted": True,
            "global_summary_required": True,
            "all_lane_role_categories_required": True,
            "critical_outcome_transition_matrices_required": True,
            "no_release_decision_from_this_artifact": True,
        },
        "validity": {
            "expires_on_input_artifact_identity_change": True,
            "expires_on_runtime_identity_change": True,
            "expires_on_active_evaluator_identity_change": True,
            "expires_on_scoring_policy_change": True,
            "hidden_holdout_is_out_of_scope": True,
        },
    }

    canonical = _canonicalize(
        payload,
        name="Run-04 scoring precommitment payload",
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            "Run-04 scoring precommitment must be an object"
        )

    return ASRRun04ScoringPrecommitmentBundle(
        payload=canonical,
        sha256=calculate_run04_scoring_precommitment_sha256(
            canonical
        ),
    )


__all__ = [
    "ASRRun04ScoringPrecommitmentBundle",
    "RUN04_EXECUTION_SUCCESS_STATUS",
    "RUN04_EXPECTED_GLOBAL_COMPLETE_PAIRS",
    "RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS",
    "RUN04_EXPECTED_RECORDINGS",
    "RUN04_EXPECTED_TERMINAL_SLOTS",
    "RUN04_INPUT_ARTIFACTS",
    "RUN04_MODEL_ROLES",
    "RUN04_OPERATOR_INTERRUPTION_MODEL_ROLE",
    "RUN04_OPERATOR_INTERRUPTION_SLOT_ORDINAL",
    "RUN04_OPERATOR_INTERRUPTION_STATUS",
    "RUN04_PRIOR_SCORING_PRECOMMITMENT_SHA256",
    "RUN04_SCORING_BASE_COMMIT",
    "RUN04_SCORING_PRECOMMITMENT_KEY",
    "RUN04_SCORING_PRECOMMITMENT_VERSION",
    "build_run04_scoring_precommitment_v1",
    "calculate_run04_scoring_precommitment_sha256",
]
