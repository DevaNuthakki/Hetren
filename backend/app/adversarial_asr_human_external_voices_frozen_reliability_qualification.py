"""Qualify the one pinned B10D VOiCES development-evidence artifact.

B11D evaluates a live, in-memory B9 execution.  The retained B10D JSON file
does not contain those Python objects or database EvaluationRun identities,
so this B11E adapter deliberately does not pretend to rehydrate them.  It
instead verifies the exact retained file, every embedded B6--B9 section hash,
their scientific cross-links, model/runtime identity, and the complete frozen
population before projecting the hash-verified B8 metrics into Reliability
contracts.

The resulting decision is development evidence only.  It never certifies a
model, qualifies production use, declares a winner, changes an official
release verdict, or authorizes release enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from os import PathLike
from pathlib import Path
from typing import Any

from hvee.core.contracts import HveeContractError, ObservationStatus
from hvee.core.observation_evidence import ObservationEvidenceRecord
from hvee.packs.asr.matched_evidence import (
    ASRMatchedQualityCohorts,
    build_asr_matched_quality_cohorts,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.release_assurance import (
    ASRMatchedReleaseAssuranceResult,
    ASRMetricNoninferiorityAssessment,
    evaluate_asr_matched_release_assurance,
)
from hvee.packs.asr.reliability_profile import (
    ASR_RELIABILITY_PROFILE_V1,
    verify_asr_reliability_profile_v1,
)
from hvee.packs.asr.reliability_qualification import (
    ASR_RELIABILITY_QUALIFICATION_RESULT_KEY,
    ASR_RELIABILITY_QUALIFICATION_RESULT_VERSION,
    ASRReliabilityQualificationResult,
    evaluate_asr_reliability_qualification_v1,
)
from hvee.packs.asr.reliability_qualification_policy import (
    ASRReliabilityQualificationPolicyV1,
    verify_asr_reliability_qualification_policy_v1,
)
from hvee.packs.asr.reliability_scoring import (
    ASREvidenceAssuranceEvidence,
    ASRMatchedControlRobustnessEvidence,
    ASROperationalFitnessEvidence,
    ASRReliabilityGateEvidence,
    ASRReliabilityPerformanceEvidence,
    ASRReliabilityRateEvidence,
    ASRReliabilityScoringEvidence,
)
from hvee.packs.asr.transcript_integrity import (
    MISSING_OUTPUT_METRIC,
    UNEXPECTED_OUTPUT_METRIC,
)


ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_KEY = (
    "hetren.asr.adversarial-human-external-voices-"
    "frozen-reliability-qualification"
)

B10D_ARTIFACT_KEY = (
    "hetren.asr.b10d-real-two-model-matched-control-development-evidence"
)
B10D_ARTIFACT_VERSION = "1.0.0"
B10D_ARTIFACT_TYPE = "pinned_real_two_model_matched_control_execution"
B10D_ARTIFACT_BYTES = 274_649
B10D_ARTIFACT_SHA256 = (
    "7d7c0422194415c383079eb4066952990"
    "1b987ed7585d1d426d90360ffe3111d"
)
B10D_SOURCE_BRANCH = "feature/hvee-asr-adversarial-qualification-v1"
B10D_SOURCE_GIT_HEAD = "a7225821e51d074d2f1dbda23d792e226aad949e"
B10D_CASE_COUNT = 32
B10D_MATCHED_CONTROL_PAIR_COUNT = 16
B10D_EXECUTION_COUNT = 64
B10D_OBSERVATION_COUNT = 128
B10D_BASELINE_LOCAL_RUN_ID = 1
B10D_CANDIDATE_LOCAL_RUN_ID = 2
B10D_LOCAL_RUN_NAMESPACE = f"b10d-file-sha256:{B10D_ARTIFACT_SHA256}"

B10D_ARTIFACT_SHA256S = {
    "b6_baseline_campaign": (
        "2760d03b7a80aa847dcc6e386e9316d7"
        "466e8361f3226cd40803fac9809ee3d8"
    ),
    "b6_candidate_campaign": (
        "44f38d090746563b7451a1bb30e17baf"
        "1883b469a24230620966a01188fb6b8c"
    ),
    "b7_baseline_metrics": (
        "ce61dd404cc3f1ec1df7c34beb7bc8ea"
        "e9f0fb78803304a1491f4f01b40d39c3"
    ),
    "b7_candidate_metrics": (
        "9f497e1b585c902b4d7a8a1f2a810b1"
        "178c27a14e8ffb8926ecd096b0e6ee25e"
    ),
    "b8_comparison": (
        "3ec7a43912dea241bb06d52d486001a6"
        "00e1157bceb359cf92c8fe641ce7167f"
    ),
    "b9_execution": (
        "1082348ac350f0d46d8eff01c0d4b254"
        "f6b9de44daeba49f196100aa5c53d61a"
    ),
}

B10D_FROZEN_EVIDENCE = {
    "controlled_contract_sha256": (
        "2f2749622f34ef6332ba6fa7f2f9219f"
        "dcc39f30617e153033a888693f61ffe9"
    ),
    "identity_chain_sha256": (
        "8634bd69c092335c1c2c20d16ae8c01"
        "b3ee965e02c77938f8b32720db9a7e354"
    ),
    "matched_control_projection_sha256": (
        "4c86b6aa1ddcdae6cfec7776289e73e5"
        "69ecd9a8bbc59bf8d9614e87647f1063"
    ),
    "matched_control_suite_sha256": (
        "a5d4a0d17ba91a0bcc13e2f1721e0d6b"
        "bd5830511101a76d54e298f194b48933"
    ),
    "matched_pair_count": 16,
    "materialization_manifest_sha256": (
        "de02c18cbf82e00ef1b3e9ff6be64dc7"
        "f74b156c51538a4499c992ff73a7886c"
    ),
    "materialized_media_count": 66,
    "media_report_sha256": (
        "7d5f75110c241cc7d62335ce23b10838"
        "2bb4111cbe6bf30a5126e361888f733b"
    ),
    "observation_sha256": (
        "69c2f06c099a8b209f42d2f22d61d6b"
        "f3397be1b2d378766b0a015a6f4fd8380"
    ),
    "rights_manifest_sha256": (
        "48d3464a9d7718b72db92e6ded490d9a"
        "0f99e373c38de00a91b7e38ee9a25cf7"
    ),
    "selection_sha256": (
        "5919f15396171255f5ce5905e9cc26fe"
        "c8743df3e58a95c8d5649726f02c7c2e"
    ),
    "suite_case_count": 32,
}

B10D_MODELS = {
    "baseline": {
        "canonical_repository": "Systran/faster-whisper-small.en",
        "mapped_repository": "Systran/faster-whisper-small.en",
        "model_binary_bytes": 483_545_366,
        "model_binary_sha256": (
            "62b2a45b05ee59acb4a5341b33ee35e0"
            "41395d378d418a18acfe4c9e768ee37a"
        ),
        "requested_name": "small.en",
        "resolved_revision": "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
    },
    "candidate": {
        "canonical_repository": (
            "dropbox-dash/faster-whisper-large-v3-turbo"
        ),
        "mapped_repository": (
            "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
        ),
        "model_binary_bytes": 1_617_884_929,
        "model_binary_sha256": (
            "e76620f83d5f5b69efd3d87e3dc180c1"
            "bd21df9fbebacfd4335e5e1efcc018da"
        ),
        "requested_name": "large-v3-turbo",
        "resolved_revision": "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
    },
}

B10D_RUNTIME = {
    "beam_size": 5,
    "compute_type": "int8_float32",
    "ctranslate2_version": "4.8.1",
    "device": "cpu",
    "faster_whisper_version": "1.2.1",
}

_ROOT_KEYS = {
    "artifact",
    "artifact_sha256s",
    "artifacts",
    "evidence_boundary",
    "frozen_evidence",
    "models",
    "runtime",
    "schema_version",
    "source_code",
}
_SECTION_KEYS = set(B10D_ARTIFACT_SHA256S)
_SHA256_EMPTY_UTF8 = hashlib.sha256(b"").hexdigest()
_SHA256_HEX = frozenset("0123456789abcdef")
_METRIC_KEYS = {"cer", "deletions", "insertions", "substitutions", "wer"}
_OUTPUT_KEYS = {
    "execution_evidence_sha256",
    "generated_transcript_sha256",
    "normalized_generated_utf8_sha256",
}
_FIXED_INPUT_KEYS = {
    "audio_asset_sha256",
    "normalized_reference_utf8_sha256",
    "reference_transcript_sha256",
}
_CASE_KEYS = {
    "arm",
    "baseline",
    "baseline_outputs",
    "candidate",
    "candidate_minus_baseline",
    "candidate_outputs",
    "case_id",
    "fixed_inputs",
    "pair_key",
}
_PAIR_KEYS = {
    "baseline",
    "candidate",
    "candidate_minus_baseline_noise_degradation",
    "pair_key",
}
_STATUS_COUNTS = {
    "cancelled": 0,
    "completed": 32,
    "failed": 0,
    "invalid": 0,
    "timed_out": 0,
}
_ADVERSARIAL_SUITE_SHA256 = (
    "dece60176bf46742bd4323fbb70c1fc36"
    "da1a6b742ce2fb1215151928b878af3"
)
_ROOT_EVIDENCE_BOUNDARY = {
    "absolute_audio_paths_embedded": False,
    "development_evidence_only": True,
    "model_winner_declared": False,
    "official_release_verdict_modified": False,
    "production_qualified": False,
    "qualification_threshold_applied": False,
    "raw_audio_embedded": False,
    "raw_generated_transcripts_embedded": False,
    "raw_reference_transcripts_embedded": False,
    "release_enforcement_eligible": False,
    "statistical_significance_claimed": False,
}
_MODEL_IDENTITIES = {
    "baseline": {
        "campaign_id": "voices-b10d-small-en-baseline",
        "campaign_version": "1.0.0",
        "provider_key": "faster_whisper",
        "model_key": "small.en",
    },
    "candidate": {
        "campaign_id": "voices-b10d-large-v3-turbo-candidate",
        "campaign_version": "1.0.0",
        "provider_key": "faster_whisper",
        "model_key": "large-v3-turbo",
    },
}
_EXPECTED_B7_METHODOLOGY = {
    "aggregate_method": "equal_weight_macro_mean_over_16_pairs",
    "cer": {
        "evaluator_key": NORMALIZED_CER_EVALUATOR.key,
        "evaluator_version": NORMALIZED_CER_EVALUATOR.version,
        "metric_key": NORMALIZED_CER_METRIC.key,
        "metric_version": NORMALIZED_CER_METRIC.version,
    },
    "normalization": {"key": "hetren.asr.text.basic", "version": "1.0.0"},
    "pair_delta_direction": "babble_minus_control",
    "wer": {
        "evaluator_key": NORMALIZED_WER_EVALUATOR.key,
        "evaluator_version": NORMALIZED_WER_EVALUATOR.version,
        "metric_key": NORMALIZED_WER_METRIC.key,
        "metric_version": NORMALIZED_WER_METRIC.version,
    },
    "word_alignment": {
        "deletions": {
            "metric_key": "asr.deletions.normalized-basic",
            "metric_version": "1.0.0",
        },
        "evaluator_key": "hetren.asr.word-alignment.normalized-basic",
        "evaluator_version": "1.0.0",
        "insertions": {
            "metric_key": "asr.insertions.normalized-basic",
            "metric_version": "1.0.0",
        },
        "substitutions": {
            "metric_key": "asr.substitutions.normalized-basic",
            "metric_version": "1.0.0",
        },
    },
}
_SECTION_ARTIFACT_IDENTITIES = {
    "b6_baseline_campaign": {
        "key": (
            "hetren.asr.adversarial-human-external-voices-babble-"
            "matched-control-campaign"
        ),
        "version": "1.0.0",
        "type": "reverified_matched_control_asr_campaign",
    },
    "b6_candidate_campaign": {
        "key": (
            "hetren.asr.adversarial-human-external-voices-babble-"
            "matched-control-campaign"
        ),
        "version": "1.0.0",
        "type": "reverified_matched_control_asr_campaign",
    },
    "b7_baseline_metrics": {
        "key": (
            "hetren.asr.adversarial-human-external-voices-babble-"
            "matched-control-normalized-metrics"
        ),
        "version": "1.0.0",
        "type": "normalized_babble_control_paired_metrics",
    },
    "b7_candidate_metrics": {
        "key": (
            "hetren.asr.adversarial-human-external-voices-babble-"
            "matched-control-normalized-metrics"
        ),
        "version": "1.0.0",
        "type": "normalized_babble_control_paired_metrics",
    },
    "b8_comparison": {
        "key": (
            "hetren.asr.adversarial-human-external-voices-babble-"
            "matched-control-model-comparison"
        ),
        "version": "1.0.0",
        "type": "reverified_matched_control_model_comparison",
    },
    "b9_execution": {
        "key": (
            "hetren.asr.adversarial-human-external-voices-babble-"
            "matched-control-model-comparison-execution"
        ),
        "version": "1.0.0",
        "type": "two_model_matched_control_execution",
    },
}
_EXPECTED_B8_AGGREGATE = {
    "case_direction_counts": {
        "cer": {"candidate_higher": 5, "candidate_lower": 17, "equal": 10},
        "wer": {"candidate_higher": 4, "candidate_lower": 18, "equal": 10},
    },
    "case_macro_mean": {
        "all": {
            "baseline": {"cer": 0.13948170731707318, "wer": 0.20461309523809523},
            "candidate": {"cer": 0.0898755081300813, "wer": 0.1328125},
            "candidate_minus_baseline": {
                "cer": -0.04960619918699187,
                "wer": -0.07180059523809523,
            },
            "case_count": 32,
        },
        "babble": {
            "baseline": {"cer": 0.18546747967479676, "wer": 0.2726934523809524},
            "candidate": {"cer": 0.15294715447154472, "wer": 0.21614583333333331},
            "candidate_minus_baseline": {
                "cer": -0.032520325203252036,
                "wer": -0.05654761904761905,
            },
            "case_count": 16,
        },
        "control": {
            "baseline": {"cer": 0.0934959349593496, "wer": 0.13653273809523808},
            "candidate": {"cer": 0.026803861788617888, "wer": 0.049479166666666664},
            "candidate_minus_baseline": {
                "cer": -0.06669207317073171,
                "wer": -0.08705357142857142,
            },
            "case_count": 16,
        },
    },
    "pair_noise_degradation_direction_counts": {
        "cer": {"candidate_higher": 8, "candidate_lower": 5, "equal": 3},
        "wer": {"candidate_higher": 9, "candidate_lower": 4, "equal": 3},
    },
    "pair_noise_degradation_macro_mean": {
        "baseline_babble_minus_control": {
            "cer": 0.09197154471544716,
            "wer": 0.13616071428571427,
        },
        "candidate_babble_minus_control": {
            "cer": 0.12614329268292682,
            "wer": 0.16666666666666666,
        },
        "candidate_minus_baseline": {
            "cer": 0.03417174796747967,
            "wer": 0.030505952380952384,
        },
    },
    "word_alignment_totals": {
        "baseline": {"deletions": 28, "insertions": 12, "substitutions": 131},
        "candidate": {"deletions": 13, "insertions": 8, "substitutions": 89},
        "candidate_minus_baseline": {
            "deletions": -15,
            "insertions": -4,
            "substitutions": -42,
        },
    },
}


class ASRAdversarialVOiCESFrozenReliabilityQualificationError(
    HveeContractError
):
    """Raised when pinned B10D evidence or its projection is inconsistent."""


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen VOiCES qualification must be deterministic JSON."
        ) from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    observed: dict[str, Any] = {}
    for key, value in pairs:
        if key in observed:
            raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                f"Frozen B10D JSON contains duplicate key {key!r}."
            )
        observed[key] = value
    return observed


def _parse_json(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B10D artifact must be supplied as immutable bytes."
        )
    try:
        decoded = raw.decode("utf-8")
        payload = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
    except ASRAdversarialVOiCESFrozenReliabilityQualificationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B10D artifact is not strict duplicate-free UTF-8 JSON."
        ) from error
    if not isinstance(payload, dict):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B10D artifact root must be an object."
        )
    return payload


def _require_exact_keys(
    value: object,
    expected: set[str],
    *,
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            f"{name} keys changed."
        )
    return value


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_HEX for character in value)
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            f"{name} must be a lowercase SHA-256."
        )
    return value


def _require_number(
    value: object,
    *,
    name: str,
    nonnegative: bool,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or (nonnegative and float(value) < 0.0)
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            f"{name} must be a finite numeric value."
        )
    return float(value)


def _require_count(value: object, *, name: str, allow_negative: bool) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or (not allow_negative and value < 0)
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            f"{name} must be an integer count."
        )
    return value


def _pair_key_token(value: object) -> bytes:
    key = _require_exact_keys(
        value,
        {"angle_degrees", "microphone_id", "room", "source_key"},
        name="VOiCES pair key",
    )
    if (
        isinstance(key["angle_degrees"], bool)
        or not isinstance(key["angle_degrees"], int)
        or isinstance(key["microphone_id"], bool)
        or not isinstance(key["microphone_id"], int)
        or not isinstance(key["room"], str)
        or not key["room"]
        or not isinstance(key["source_key"], list)
        or len(key["source_key"]) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) for item in key["source_key"])
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "VOiCES pair key structure changed."
        )
    return _canonical_json_bytes(key)


def _verify_metric_payload(value: object, *, name: str) -> dict[str, Any]:
    metric = _require_exact_keys(value, _METRIC_KEYS, name=name)
    _require_number(metric["wer"], name=f"{name} WER", nonnegative=True)
    _require_number(metric["cer"], name=f"{name} CER", nonnegative=True)
    for key in ("deletions", "insertions", "substitutions"):
        _require_count(metric[key], name=f"{name} {key}", allow_negative=False)
    return metric


def _verify_delta_payload(value: object, *, name: str) -> dict[str, Any]:
    delta = _require_exact_keys(value, _METRIC_KEYS, name=name)
    _require_number(delta["wer"], name=f"{name} WER", nonnegative=False)
    _require_number(delta["cer"], name=f"{name} CER", nonnegative=False)
    for key in ("deletions", "insertions", "substitutions"):
        _require_count(delta[key], name=f"{name} {key}", allow_negative=True)
    return delta


def _verify_output_payload(value: object, *, name: str) -> dict[str, Any]:
    output = _require_exact_keys(value, _OUTPUT_KEYS, name=name)
    for key, item in output.items():
        _require_sha256(item, name=f"{name} {key}")
    return output


def _verify_fixed_inputs(value: object) -> dict[str, Any]:
    fixed = _require_exact_keys(
        value,
        _FIXED_INPUT_KEYS,
        name="VOiCES fixed inputs",
    )
    for key, item in fixed.items():
        _require_sha256(item, name=f"VOiCES fixed input {key}")
    return fixed


def _verify_section_identities(artifacts: dict[str, Any]) -> None:
    for key, expected in _SECTION_ARTIFACT_IDENTITIES.items():
        section = artifacts[key]
        if (
            not isinstance(section, dict)
            or section.get("schema_version") != 1
            or section.get("artifact") != expected
        ):
            raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                f"Frozen {key} artifact identity changed."
            )


def _verify_campaign(
    section: dict[str, Any],
    *,
    label: str,
) -> dict[str, dict[str, Any]]:
    identity = _MODEL_IDENTITIES[label]
    campaign = section.get("campaign")
    if not isinstance(campaign, dict):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            f"Frozen {label} B6 campaign is missing."
        )
    for key, expected in identity.items():
        if campaign.get(key) != expected:
            raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                f"Frozen {label} B6 model identity changed."
            )
    if (
        campaign.get("attempt_count") != B10D_CASE_COUNT
        or campaign.get("completed_pair_count")
        != B10D_MATCHED_CONTROL_PAIR_COUNT
        or campaign.get("all_cases_completed") is not True
        or campaign.get("status_counts") != _STATUS_COUNTS
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            f"Frozen {label} B6 completion population changed."
        )
    attempts = campaign.get("ordered_attempts")
    if not isinstance(attempts, list) or len(attempts) != B10D_CASE_COUNT:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            f"Frozen {label} B6 attempts changed."
        )
    by_case: dict[str, dict[str, Any]] = {}
    execution_ids: set[str] = set()
    arm_counts = {"babble": 0, "control": 0}
    for attempt in attempts:
        attempt = _require_exact_keys(
            attempt,
            {
                "arm",
                "case_id",
                "execution_environment_sha256",
                "execution_evidence_sha256",
                "execution_id",
                "generated_transcript_sha256",
                "status",
                "status_detail",
            },
            name=f"Frozen {label} B6 attempt",
        )
        case_id = attempt["case_id"]
        execution_id = attempt["execution_id"]
        arm = attempt["arm"]
        if (
            not isinstance(case_id, str)
            or not case_id
            or not isinstance(execution_id, str)
            or not execution_id
            or arm not in arm_counts
            or attempt["status"] != "completed"
            or attempt["status_detail"] is not None
            or case_id in by_case
            or execution_id in execution_ids
        ):
            raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                f"Frozen {label} B6 attempt identity or status changed."
            )
        for key in (
            "execution_environment_sha256",
            "execution_evidence_sha256",
            "generated_transcript_sha256",
        ):
            _require_sha256(attempt[key], name=f"Frozen {label} B6 {key}")
        by_case[case_id] = attempt
        execution_ids.add(execution_id)
        arm_counts[arm] += 1
    if arm_counts != {"babble": 16, "control": 16}:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            f"Frozen {label} B6 arm population changed."
        )
    return by_case


def _verify_b7_links(
    artifacts: dict[str, Any],
    *,
    label: str,
) -> None:
    b6_key = f"b6_{label}_campaign"
    b7_key = f"b7_{label}_metrics"
    b6 = artifacts[b6_key]
    b7 = artifacts[b7_key]
    upstream = b7.get("upstream")
    b6_upstream = b6.get("upstream")
    if (
        b7.get("model_identity") != _MODEL_IDENTITIES[label]
        or b7.get("methodology") != _EXPECTED_B7_METHODOLOGY
        or not isinstance(upstream, dict)
        or not isinstance(b6_upstream, dict)
        or upstream.get("matched_control_campaign_sha256")
        != B10D_ARTIFACT_SHA256S[b6_key]
        or upstream.get("campaign_evidence_sha256")
        != b6_upstream.get("campaign_evidence_sha256")
        or upstream.get("adversarial_suite_evidence_sha256")
        != _ADVERSARIAL_SUITE_SHA256
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            f"Frozen {label} B6-to-B7 linkage changed."
        )


def _verify_b8(
    artifacts: dict[str, Any],
    baseline_attempts: dict[str, dict[str, Any]],
    candidate_attempts: dict[str, dict[str, Any]],
) -> None:
    comparison = artifacts["b8_comparison"]
    upstream = comparison.get("upstream")
    expected_models = {
        "baseline": {
            **_MODEL_IDENTITIES["baseline"],
            "campaign_sha256": B10D_ARTIFACT_SHA256S[
                "b6_baseline_campaign"
            ],
            "metrics_sha256": B10D_ARTIFACT_SHA256S[
                "b7_baseline_metrics"
            ],
        },
        "candidate": {
            **_MODEL_IDENTITIES["candidate"],
            "campaign_sha256": B10D_ARTIFACT_SHA256S[
                "b6_candidate_campaign"
            ],
            "metrics_sha256": B10D_ARTIFACT_SHA256S[
                "b7_candidate_metrics"
            ],
        },
    }
    if (
        comparison.get("models") != expected_models
        or not isinstance(upstream, dict)
        or upstream.get("matched_control_suite_sha256")
        != B10D_FROZEN_EVIDENCE["matched_control_suite_sha256"]
        or upstream.get("adversarial_suite_evidence_sha256")
        != _ADVERSARIAL_SUITE_SHA256
        or upstream.get("baseline_metrics_sha256")
        != B10D_ARTIFACT_SHA256S["b7_baseline_metrics"]
        or upstream.get("candidate_metrics_sha256")
        != B10D_ARTIFACT_SHA256S["b7_candidate_metrics"]
        or comparison.get("aggregate") != _EXPECTED_B8_AGGREGATE
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B8 identity, links, or aggregate changed."
        )
    cases = comparison.get("cases")
    pairs = comparison.get("pairs")
    if (
        not isinstance(cases, list)
        or len(cases) != B10D_CASE_COUNT
        or not isinstance(pairs, list)
        or len(pairs) != B10D_MATCHED_CONTROL_PAIR_COUNT
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B8 population changed."
        )
    case_ids: set[str] = set()
    pair_arms: dict[bytes, set[str]] = {}
    for case in cases:
        case = _require_exact_keys(case, _CASE_KEYS, name="Frozen B8 case")
        case_id = case["case_id"]
        arm = case["arm"]
        if (
            not isinstance(case_id, str)
            or not case_id
            or case_id in case_ids
            or arm not in {"babble", "control"}
            or case_id not in baseline_attempts
            or case_id not in candidate_attempts
            or baseline_attempts[case_id]["arm"] != arm
            or candidate_attempts[case_id]["arm"] != arm
        ):
            raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                "Frozen B8 case identity or B6 linkage changed."
            )
        baseline = _verify_metric_payload(case["baseline"], name="B8 baseline")
        candidate = _verify_metric_payload(case["candidate"], name="B8 candidate")
        delta = _verify_delta_payload(
            case["candidate_minus_baseline"],
            name="B8 candidate-minus-baseline",
        )
        for key in _METRIC_KEYS:
            observed = float(candidate[key]) - float(baseline[key])
            if not math.isclose(
                float(delta[key]),
                observed,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                    "Frozen B8 case delta changed."
                )
        baseline_output = _verify_output_payload(
            case["baseline_outputs"],
            name="B8 baseline output",
        )
        candidate_output = _verify_output_payload(
            case["candidate_outputs"],
            name="B8 candidate output",
        )
        _verify_fixed_inputs(case["fixed_inputs"])
        for output, attempt in (
            (baseline_output, baseline_attempts[case_id]),
            (candidate_output, candidate_attempts[case_id]),
        ):
            if (
                output["execution_evidence_sha256"]
                != attempt["execution_evidence_sha256"]
                or output["generated_transcript_sha256"]
                != attempt["generated_transcript_sha256"]
            ):
                raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                    "Frozen B6-to-B8 execution output linkage changed."
                )
        token = _pair_key_token(case["pair_key"])
        pair_arms.setdefault(token, set()).add(arm)
        case_ids.add(case_id)
    if (
        case_ids != set(baseline_attempts)
        or case_ids != set(candidate_attempts)
        or len(pair_arms) != B10D_MATCHED_CONTROL_PAIR_COUNT
        or any(arms != {"babble", "control"} for arms in pair_arms.values())
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B8 matched-control coverage changed."
        )
    pair_tokens: set[bytes] = set()
    for pair in pairs:
        pair = _require_exact_keys(pair, _PAIR_KEYS, name="Frozen B8 pair")
        token = _pair_key_token(pair["pair_key"])
        if token in pair_tokens or token not in pair_arms:
            raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                "Frozen B8 pair identity changed."
            )
        for label in ("baseline", "candidate"):
            value = _require_exact_keys(
                pair[label],
                {"babble_minus_control"},
                name=f"Frozen B8 {label} pair",
            )
            _verify_delta_payload(
                value["babble_minus_control"],
                name=f"Frozen B8 {label} degradation",
            )
        _verify_delta_payload(
            pair["candidate_minus_baseline_noise_degradation"],
            name="Frozen B8 difference-in-differences",
        )
        pair_tokens.add(token)
    if pair_tokens != set(pair_arms):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B8 pair population changed."
        )


def _verify_b9(artifacts: dict[str, Any]) -> None:
    b9 = artifacts["b9_execution"]
    upstream = b9.get("upstream")
    if (
        b9.get("status") != "completed"
        or b9.get("comparison_sha256")
        != B10D_ARTIFACT_SHA256S["b8_comparison"]
        or not isinstance(upstream, dict)
        or upstream.get("matched_control_suite_sha256")
        != B10D_FROZEN_EVIDENCE["matched_control_suite_sha256"]
        or upstream.get("adversarial_suite_evidence_sha256")
        != _ADVERSARIAL_SUITE_SHA256
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B9 status or upstream linkage changed."
        )
    for label in ("baseline", "candidate"):
        summary = b9.get(label)
        b6_key = f"b6_{label}_campaign"
        b7_key = f"b7_{label}_metrics"
        campaign = artifacts[b6_key]["campaign"]
        campaign_upstream = artifacts[b6_key]["upstream"]
        expected = {
            **_MODEL_IDENTITIES[label],
            "campaign_sha256": B10D_ARTIFACT_SHA256S[b6_key],
            "campaign_evidence_sha256": campaign_upstream[
                "campaign_evidence_sha256"
            ],
            "status_counts": _STATUS_COUNTS,
            "completed_pair_count": B10D_MATCHED_CONTROL_PAIR_COUNT,
            "metrics_sha256": B10D_ARTIFACT_SHA256S[b7_key],
        }
        if summary != expected or campaign.get("status_counts") != _STATUS_COUNTS:
            raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                f"Frozen B9 {label} summary changed."
            )


def _verify_frozen_artifact(raw: bytes) -> dict[str, Any]:
    if len(raw) != B10D_ARTIFACT_BYTES:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Pinned B10D artifact byte length changed."
        )
    observed_file_sha256 = hashlib.sha256(raw).hexdigest()
    if observed_file_sha256 != B10D_ARTIFACT_SHA256:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Pinned B10D artifact SHA-256 changed."
        )
    payload = _parse_json(raw)
    _require_exact_keys(payload, _ROOT_KEYS, name="Frozen B10D root")
    if (
        payload["schema_version"] != 1
        or payload["artifact"]
        != {
            "key": B10D_ARTIFACT_KEY,
            "version": B10D_ARTIFACT_VERSION,
            "type": B10D_ARTIFACT_TYPE,
        }
        or payload["artifact_sha256s"] != B10D_ARTIFACT_SHA256S
        or payload["frozen_evidence"] != B10D_FROZEN_EVIDENCE
        or payload["source_code"]
        != {"branch": B10D_SOURCE_BRANCH, "git_head": B10D_SOURCE_GIT_HEAD}
        or payload["models"] != B10D_MODELS
        or payload["runtime"] != B10D_RUNTIME
        or payload["evidence_boundary"] != _ROOT_EVIDENCE_BOUNDARY
    ):
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Pinned B10D root identity or evidence boundary changed."
        )
    artifacts = _require_exact_keys(
        payload["artifacts"],
        _SECTION_KEYS,
        name="Frozen B10D artifacts",
    )
    for key, expected_sha256 in B10D_ARTIFACT_SHA256S.items():
        observed = hashlib.sha256(_canonical_json_bytes(artifacts[key])).hexdigest()
        if observed != expected_sha256:
            raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
                f"Frozen {key} canonical SHA-256 changed."
            )
    _verify_section_identities(artifacts)
    baseline_attempts = _verify_campaign(
        artifacts["b6_baseline_campaign"],
        label="baseline",
    )
    candidate_attempts = _verify_campaign(
        artifacts["b6_candidate_campaign"],
        label="candidate",
    )
    _verify_b7_links(artifacts, label="baseline")
    _verify_b7_links(artifacts, label="candidate")
    _verify_b8(artifacts, baseline_attempts, candidate_attempts)
    _verify_b9(artifacts)
    return payload


def _reverify_policy(
    value: object,
) -> ASRReliabilityQualificationPolicyV1:
    try:
        return verify_asr_reliability_qualification_policy_v1(value)
    except Exception as error:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen VOiCES qualification requires the exact B11A policy."
        ) from error


def _observation_record(
    *,
    metric,
    evaluator,
    run_id: int,
    test_case_id: int,
    value: float,
) -> ObservationEvidenceRecord:
    return ObservationEvidenceRecord(
        metric_key=metric.key,
        metric_version=metric.version,
        evaluator_key=evaluator.key,
        evaluator_version=evaluator.version,
        evaluation_type=metric.evaluation_type,
        scope="test_case",
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
        status=ObservationStatus.SUCCESS,
        value_type=metric.value_type,
        value=value,
    )


def _observation_records(
    artifact: dict[str, Any],
) -> tuple[ObservationEvidenceRecord, ...]:
    cases = artifact["artifacts"]["b8_comparison"]["cases"]
    records: list[ObservationEvidenceRecord] = []
    for test_case_id, case in enumerate(cases, start=1):
        for run_id, label in (
            (B10D_BASELINE_LOCAL_RUN_ID, "baseline"),
            (B10D_CANDIDATE_LOCAL_RUN_ID, "candidate"),
        ):
            result = case[label]
            records.extend(
                (
                    _observation_record(
                        metric=NORMALIZED_WER_METRIC,
                        evaluator=NORMALIZED_WER_EVALUATOR,
                        run_id=run_id,
                        test_case_id=test_case_id,
                        value=float(result["wer"]),
                    ),
                    _observation_record(
                        metric=NORMALIZED_CER_METRIC,
                        evaluator=NORMALIZED_CER_EVALUATOR,
                        run_id=run_id,
                        test_case_id=test_case_id,
                        value=float(result["cer"]),
                    ),
                )
            )
    observed = tuple(records)
    if len(observed) != B10D_OBSERVATION_COUNT:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen VOiCES observation population changed."
        )
    return observed


def _cohorts(
    artifact: dict[str, Any],
) -> ASRMatchedQualityCohorts:
    return build_asr_matched_quality_cohorts(
        baseline_run_id=B10D_BASELINE_LOCAL_RUN_ID,
        candidate_run_id=B10D_CANDIDATE_LOCAL_RUN_ID,
        declared_test_case_ids=tuple(range(1, B10D_CASE_COUNT + 1)),
        records=_observation_records(artifact),
    )


def _gate_counts(artifact: dict[str, Any]) -> tuple[int, int]:
    missing = 0
    unexpected = 0
    for case in artifact["artifacts"]["b8_comparison"]["cases"]:
        reference_empty = (
            case["fixed_inputs"]["normalized_reference_utf8_sha256"]
            == _SHA256_EMPTY_UTF8
        )
        for label in ("baseline", "candidate"):
            generated_empty = (
                case[f"{label}_outputs"]["normalized_generated_utf8_sha256"]
                == _SHA256_EMPTY_UTF8
            )
            missing += int(not reference_empty and generated_empty)
            unexpected += int(reference_empty and not generated_empty)
    return missing, unexpected


def _operational_evidence(
    artifact: dict[str, Any],
) -> ASROperationalFitnessEvidence:
    b9 = artifact["artifacts"]["b9_execution"]
    counts = {
        key: b9["baseline"]["status_counts"][key]
        + b9["candidate"]["status_counts"][key]
        for key in _STATUS_COUNTS
    }
    observed = sum(counts.values())
    if observed != B10D_EXECUTION_COUNT:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen VOiCES operational population changed."
        )
    return ASROperationalFitnessEvidence(
        execution_completion=ASRReliabilityRateEvidence(
            successful_count=counts["completed"],
            observed_count=observed,
            expected_count=B10D_EXECUTION_COUNT,
        ),
        timeout_free=ASRReliabilityRateEvidence(
            successful_count=observed - counts["timed_out"],
            observed_count=observed,
            expected_count=B10D_EXECUTION_COUNT,
        ),
        cancellation_free=ASRReliabilityRateEvidence(
            successful_count=observed - counts["cancelled"],
            observed_count=observed,
            expected_count=B10D_EXECUTION_COUNT,
        ),
        provider_error_free=ASRReliabilityRateEvidence(
            successful_count=observed - counts["failed"],
            observed_count=observed,
            expected_count=B10D_EXECUTION_COUNT,
        ),
    )


def _scoring_evidence(
    artifact: dict[str, Any],
) -> ASRReliabilityScoringEvidence:
    try:
        verify_asr_reliability_profile_v1(ASR_RELIABILITY_PROFILE_V1)
    except Exception as error:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen VOiCES projection requires Reliability Profile v1."
        ) from error
    aggregate = artifact["artifacts"]["b8_comparison"]["aggregate"]
    differential = aggregate["pair_noise_degradation_macro_mean"][
        "candidate_minus_baseline"
    ]
    missing, unexpected = _gate_counts(artifact)
    return ASRReliabilityScoringEvidence(
        performance=ASRReliabilityPerformanceEvidence(
            matched_control_robustness=ASRMatchedControlRobustnessEvidence(
                wer_differential=float(differential["wer"]),
                cer_differential=float(differential["cer"]),
                observed_pair_count=B10D_MATCHED_CONTROL_PAIR_COUNT,
                expected_pair_count=B10D_MATCHED_CONTROL_PAIR_COUNT,
            ),
            critical_number_integrity=None,
            critical_identifier_integrity=None,
            critical_terminology_integrity=None,
        ),
        assurance=ASREvidenceAssuranceEvidence(
            profile_and_evaluators_verified=True,
            input_provenance_verified=True,
            runtime_identity_verified=True,
            reproducibility_verified=None,
        ),
        operational=_operational_evidence(artifact),
        missing_output_gate=ASRReliabilityGateEvidence(
            metric_key=MISSING_OUTPUT_METRIC.key,
            violation_count=missing,
            observed_count=B10D_EXECUTION_COUNT,
            expected_count=B10D_EXECUTION_COUNT,
        ),
        unexpected_output_gate=ASRReliabilityGateEvidence(
            metric_key=UNEXPECTED_OUTPUT_METRIC.key,
            violation_count=unexpected,
            observed_count=B10D_EXECUTION_COUNT,
            expected_count=B10D_EXECUTION_COUNT,
        ),
    )


@dataclass(frozen=True, slots=True)
class _DerivedReliabilityEvidence:
    records: tuple[ObservationEvidenceRecord, ...]
    cohorts: ASRMatchedQualityCohorts
    matched_assurance: ASRMatchedReleaseAssuranceResult
    scoring_evidence: ASRReliabilityScoringEvidence
    qualification: ASRReliabilityQualificationResult


def _derive_reliability_evidence(
    *,
    artifact: dict[str, Any],
    policy: ASRReliabilityQualificationPolicyV1,
) -> _DerivedReliabilityEvidence:
    records = _observation_records(artifact)
    cohorts = _cohorts(artifact)
    matched_assurance = evaluate_asr_matched_release_assurance(
        cohorts=cohorts,
        policy=policy.matched_release_assurance,
    )
    scoring_evidence = _scoring_evidence(artifact)
    qualification = evaluate_asr_reliability_qualification_v1(
        scoring_evidence=scoring_evidence,
        matched_assurance=matched_assurance,
        policy=policy,
    )
    return _DerivedReliabilityEvidence(
        records=records,
        cohorts=cohorts,
        matched_assurance=matched_assurance,
        scoring_evidence=scoring_evidence,
        qualification=qualification,
    )


def _record_payload(record: ObservationEvidenceRecord) -> dict[str, object]:
    return {
        "metric_key": record.metric_key,
        "metric_version": record.metric_version,
        "evaluator_key": record.evaluator_key,
        "evaluator_version": record.evaluator_version,
        "evaluation_type": record.evaluation_type,
        "scope": record.scope,
        "artifact_local_run_id": record.evaluation_run_id,
        "test_case_id": record.test_case_id,
        "status": record.status.value,
        "value_type": record.value_type.value,
        "value": record.value,
        "status_detail": record.status_detail,
    }


def _scoring_evidence_payload(
    evidence: ASRReliabilityScoringEvidence,
) -> dict[str, object]:
    robustness = evidence.performance.matched_control_robustness
    return {
        "performance": {
            "matched_control_robustness": (
                None if robustness is None else robustness.payload
            ),
            "critical_number_integrity": None,
            "critical_identifier_integrity": None,
            "critical_terminology_integrity": None,
        },
        "assurance": dict(evidence.assurance.values),
        "operational": {
            key: None if value is None else value.payload
            for key, value in evidence.operational.values
        },
        "hard_gates": {
            "missing_output": (
                None
                if evidence.missing_output_gate is None
                else evidence.missing_output_gate.payload
            ),
            "unexpected_output": (
                None
                if evidence.unexpected_output_gate is None
                else evidence.unexpected_output_gate.payload
            ),
        },
    }


def _interval_payload(
    assessment: ASRMetricNoninferiorityAssessment | None,
) -> dict[str, object] | None:
    if assessment is None:
        return None
    interval = assessment.interval
    return {
        "metric_key": assessment.metric_key,
        "metric_version": assessment.metric_version,
        "noninferiority_margin": assessment.noninferiority_margin,
        "method": interval.method.value,
        "confidence_level": interval.confidence_level,
        "minimum_usable_pairs": interval.minimum_usable_pairs,
        "resamples": interval.resamples,
        "random_seed": interval.random_seed,
        "total_cases": interval.total_cases,
        "usable_pairs": interval.usable_pairs,
        "integrity": interval.integrity.value,
        "evidence": interval.evidence.value,
        "reason": interval.reason.value,
        "mean_delta": interval.mean_delta,
        "lower_bound": interval.lower_bound,
        "upper_bound": interval.upper_bound,
        "claim": assessment.claim.value,
    }


def _matched_assurance_payload(
    assurance: ASRMatchedReleaseAssuranceResult,
) -> dict[str, object]:
    return {
        "policy": {
            "key": assurance.policy_key,
            "version": assurance.policy_version,
        },
        "runs": {
            "baseline_artifact_local_run_id": assurance.baseline_run_id,
            "candidate_artifact_local_run_id": assurance.candidate_run_id,
        },
        "declared_test_case_ids": list(assurance.declared_test_case_ids),
        "normalized_wer": _interval_payload(assurance.normalized_wer),
        "normalized_cer": _interval_payload(assurance.normalized_cer),
        "assessment": {
            "integrity": assurance.integrity.value,
            "evidence": assurance.evidence.value,
            "claim": assurance.claim.value,
        },
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESFrozenReliabilityQualificationBundle:
    """Deterministic B11E decision over exactly one pinned frozen file."""

    artifact_bytes: bytes
    policy: ASRReliabilityQualificationPolicyV1
    _derived_evidence: _DerivedReliabilityEvidence = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        artifact = _verify_frozen_artifact(self.artifact_bytes)
        policy = _reverify_policy(self.policy)
        object.__setattr__(
            self,
            "_derived_evidence",
            _derive_reliability_evidence(artifact=artifact, policy=policy),
        )

    @property
    def frozen_artifact(self) -> dict[str, Any]:
        return _verify_frozen_artifact(self.artifact_bytes)

    @property
    def derived(self) -> _DerivedReliabilityEvidence:
        return self._derived_evidence

    @property
    def qualification(self) -> ASRReliabilityQualificationResult:
        return self.derived.qualification

    @property
    def payload(self) -> dict[str, object]:
        artifact = self.frozen_artifact
        derived = self.derived
        comparison = artifact["artifacts"]["b8_comparison"]
        qualification = derived.qualification
        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_SCHEMA_VERSION
            ),
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_KEY,
                "version": ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_VERSION,
                "type": "pinned_frozen_development_evidence_qualification",
            },
            "upstream": {
                "b10d_file": {
                    "artifact_key": B10D_ARTIFACT_KEY,
                    "artifact_version": B10D_ARTIFACT_VERSION,
                    "bytes": len(self.artifact_bytes),
                    "sha256": B10D_ARTIFACT_SHA256,
                },
                "source_code": dict(artifact["source_code"]),
                "section_sha256s": dict(artifact["artifact_sha256s"]),
                "frozen_evidence": dict(artifact["frozen_evidence"]),
                "qualification": {
                    "key": ASR_RELIABILITY_QUALIFICATION_RESULT_KEY,
                    "version": ASR_RELIABILITY_QUALIFICATION_RESULT_VERSION,
                    "sha256": qualification.sha256,
                },
            },
            "bindings": {
                "policy": {
                    "key": self.policy.key,
                    "version": self.policy.version,
                    "sha256": self.policy.sha256,
                },
                "decision_kernel": "hvee.core.decision.decide",
                "profile_projection_verified_at_b11e": True,
                "frozen_source_profile_claimed": False,
                "input_provenance_verification_scope": (
                    "exact_frozen_hash_chain_not_external_source_revalidation"
                ),
                "runtime_identity_verification_scope": (
                    "exact_frozen_runtime_and_execution_evidence_identity"
                ),
            },
            "models": artifact["models"],
            "runtime": artifact["runtime"],
            "run_identity": {
                "namespace": B10D_LOCAL_RUN_NAMESPACE,
                "identity_kind": "artifact_local_ordinal",
                "database_evaluation_run_identity_claimed": False,
                "nested_qualification_run_ids_use_this_namespace": True,
                "baseline": {
                    "artifact_local_run_id": B10D_BASELINE_LOCAL_RUN_ID,
                    **_MODEL_IDENTITIES["baseline"],
                },
                "candidate": {
                    "artifact_local_run_id": B10D_CANDIDATE_LOCAL_RUN_ID,
                    **_MODEL_IDENTITIES["candidate"],
                },
            },
            "methodology": {
                "frozen_file_verification": (
                    "exact_raw_file_sha256_then_canonical_embedded_section_sha256"
                ),
                "metrics_source": (
                    "hash_verified_frozen_b8_development_metrics"
                ),
                "raw_transcript_metric_recomputation": False,
                "live_b9_object_rehydration": False,
                "test_case_identity_mapping": (
                    "one_based_ordinal_over_verified_frozen_b8_order"
                ),
                "matched_quality_metrics": [
                    NORMALIZED_WER_METRIC.key,
                    NORMALIZED_CER_METRIC.key,
                ],
                "normalized_integrity_gates": (
                    "derived_from_frozen_normalized_utf8_sha256_empty_sentinel"
                ),
                "robustness_signal": (
                    "candidate_minus_baseline_change_in_"
                    "babble_minus_control_macro_mean"
                ),
                "critical_content_projection": (
                    "withheld_general_voices_cohort_not_preregistered_"
                    "for_critical_content_qualification"
                ),
                "reproducibility_projection": (
                    "withheld_single_campaign_per_model"
                ),
                "qualification_policy_caller_supplied": True,
            },
            "population": {
                "case_count": len(comparison["cases"]),
                "matched_control_pair_count": len(comparison["pairs"]),
                "execution_count": B10D_EXECUTION_COUNT,
                "observation_record_count": len(derived.records),
                "case_identity_map": [
                    {
                        "test_case_id": index,
                        "voices_case_id": case["case_id"],
                    }
                    for index, case in enumerate(comparison["cases"], start=1)
                ],
            },
            "matched_observation_records": [
                _record_payload(value) for value in derived.records
            ],
            "scoring_evidence": _scoring_evidence_payload(
                derived.scoring_evidence
            ),
            "matched_release_assurance": _matched_assurance_payload(
                derived.matched_assurance
            ),
            "decision": qualification.payload["decision"],
            "support": qualification.payload["support"],
            "qualification": qualification.payload,
            "evidence_boundary": {
                "development_evidence_only": True,
                "exact_b10d_file_reverified": True,
                "all_b6_through_b9_section_hashes_reverified": True,
                "all_b6_through_b9_cross_links_reverified": True,
                "frozen_b8_metrics_projected": True,
                "raw_transcript_metrics_recomputed": False,
                "live_b9_execution_rehydrated": False,
                "database_evaluation_run_ids_claimed": False,
                "external_source_artifacts_reread": False,
                "explicit_b11a_policy_applied": True,
                "decision_kernel_called": True,
                "critical_content_qualification_evidence_claimed": False,
                "reproducibility_claimed": False,
                "non_authoritative_model_qualification_verdict_issued": True,
                "model_winner_declared": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()

    def require_live_b9_execution(self) -> None:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B11E evidence cannot rehydrate the original live B9 "
            "Python execution bundle."
        )

    def require_certification(self) -> None:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B11E is non-authoritative development evidence; it does "
            "not certify a model or qualify production use."
        )

    def require_release_enforcement(self) -> None:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Frozen B11E does not authorize release enforcement or modify an "
            "official release verdict."
        )


def evaluate_asr_adversarial_voices_frozen_reliability_qualification_v1(
    *,
    artifact_bytes: bytes,
    policy: ASRReliabilityQualificationPolicyV1,
) -> ASRAdversarialVOiCESFrozenReliabilityQualificationBundle:
    """Verify exact frozen B10D bytes and apply one explicit B11A policy."""

    return ASRAdversarialVOiCESFrozenReliabilityQualificationBundle(
        artifact_bytes=artifact_bytes,
        policy=_reverify_policy(policy),
    )


def evaluate_asr_adversarial_voices_frozen_reliability_file_v1(
    *,
    artifact_path: str | PathLike[str],
    policy: ASRReliabilityQualificationPolicyV1,
) -> ASRAdversarialVOiCESFrozenReliabilityQualificationBundle:
    """Read one local file without embedding its absolute path in evidence."""

    try:
        raw = Path(artifact_path).read_bytes()
    except (OSError, TypeError, ValueError) as error:
        raise ASRAdversarialVOiCESFrozenReliabilityQualificationError(
            "Pinned B10D artifact could not be read."
        ) from error
    return evaluate_asr_adversarial_voices_frozen_reliability_qualification_v1(
        artifact_bytes=raw,
        policy=policy,
    )
