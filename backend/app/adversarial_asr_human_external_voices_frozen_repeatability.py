"""Verify the frozen real B11F VOiCES repeatability evidence.

B11G binds the three content-free B11F run checkpoints and their final
repeatability artifact to exact byte identities, then independently rebuilds
the semantic relationships that make the evidence meaningful.  The verifier
does not load audio, invoke an ASR provider, or trust derived aggregates merely
because their enclosing JSON file was pinned.

This remains development evidence.  Same-environment campaign repetition is
not cross-host reproducibility, qualification, certification, or release
authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable


ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_KEY = (
    "hetren.asr.adversarial-human-external-voices-"
    "frozen-real-repeatability-verification"
)

B11F_ARTIFACT_KEY = "hetren.asr.b11f-real-repeatability-evidence"
B11F_ARTIFACT_VERSION = "1.0.0"
B11F_ARTIFACT_TYPE = "pinned-real-same-environment-campaign-repeatability"
B11F_ARTIFACT_BYTES = 501_439
B11F_ARTIFACT_SHA256 = (
    "d4e68272debfdbc1e1980ef798e3a596"
    "eb11c14b657a6491c69ac3a283bf41fb"
)
B11F_REPEATABILITY_SHA256 = (
    "0291eedfd15f885b48176939c364316c"
    "c95228bb9fff612b41dc0e035950b420"
)
B11F_SOURCE_BRANCH = "feature/hvee-asr-adversarial-qualification-v1"
B11F_SOURCE_GIT_HEAD = "9b5bde9a5502629a9fba48b4b6732ebf416c3a2f"
B11F_STATUS = "stable"
B11F_RUNTIME_ENVIRONMENT_SHA256 = (
    "4daeb597fb1450bebf3e7de6839fcbe0"
    "ec60e409b0cfadfcc0973f9c717aacf2"
)
B11F_MATCHED_CONTROL_PROJECTION_SHA256 = (
    "4c86b6aa1ddcdae6cfec7776289e73e5"
    "69ecd9a8bbc59bf8d9614e87647f1063"
)
B11F_MATCHED_CONTROL_SUITE_SHA256 = (
    "a5d4a0d17ba91a0bcc13e2f1721e0d6"
    "bbd5830511101a76d54e298f194b48933"
)
B11F_ADVERSARIAL_SUITE_EVIDENCE_SHA256 = (
    "dece60176bf46742bd4323fbb70c1fc36"
    "da1a6b742ce2fb1215151928b878af3"
)
B11F_RUN_CHECKPOINT_BYTES = (91_940, 91_940, 91_940)
B11F_RUN_CHECKPOINT_FILE_SHA256S = (
    "191170e70b44a08fa695235f221c46d28e3412f5b48b852acd13f8c39ec2628e",
    "c33b370587d4d0a97f0e354537b8ecce2872d1f1f97cc6598a1999ac514f8dcb",
    "a13680fe004e343eefa4e581c520ad4398bac699fd65f280ac1b4ce91600489f",
)
B11F_RUN_OBSERVATION_SHA256S = (
    "4a533748ca5482301c3ffb2d9a3d66a3a7395b4e4b1a89c3ddbe12bd247c6157",
    "896ade30945a5b84e030e00091035e30303790dcb57098c0fb52e1cff1dcf194",
    "e3b8fa5bb92e7df2c527091f6d23522fa76d740fd120d4d20ead5d32351c9368",
)
B11F_B9_EXECUTION_SHA256S = (
    "df931151422bf8d3af738d6a742c053d5ff8bd7ee7b5020ec09d561d7dc4d60c",
    "2169bf041d37815f44a84d97da36a70d52ddaa8785d0840a88bb3894fda483e0",
    "d4c8e99251dd8e667f01b3f95963c62f923cd5e65725012dc0b5fb006dc6a358",
)
B11F_RUN_IDS = (
    "b11f-same-environment-run-01",
    "b11f-same-environment-run-02",
    "b11f-same-environment-run-03",
)

_SCHEMA_VERSION = 1
_RUN_COUNT = 3
_MODEL_COUNT = 2
_CASE_COUNT_PER_MODEL = 32
_UNIT_COUNT = 64
_EXECUTION_COUNT = 192
_ROLES = ("baseline", "candidate")
_ARMS = ("babble", "control")
_METRICS = ("wer", "cer")
_SHA256_HEX = frozenset("0123456789abcdef")
_METRIC_EQUALITY_ABSOLUTE_TOLERANCE = 1e-12

_SOURCE_CODE = {
    "branch": B11F_SOURCE_BRANCH,
    "git_head": B11F_SOURCE_GIT_HEAD,
}
_EXECUTION_PROTOCOL = {
    "campaign_version": "1.0.0",
    "case_count_per_model": _CASE_COUNT_PER_MODEL,
    "case_model_units_per_run": _UNIT_COUNT,
    "fresh_model_instances_per_campaign": True,
    "fresh_provider_instances_per_campaign": True,
    "model_count": _MODEL_COUNT,
    "model_instance_cache_reused_across_campaigns": False,
    "model_instance_cache_reused_within_campaign": True,
    "operating_system_process_identity_recorded": False,
    "run_count": _RUN_COUNT,
    "single_python_process_required_across_campaigns": False,
    "total_transcription_count": _EXECUTION_COUNT,
}
_MODELS = {
    "baseline": {
        "canonical_repository": "Systran/faster-whisper-small.en",
        "model_binary_bytes": 483_545_366,
        "model_binary_sha256": (
            "62b2a45b05ee59acb4a5341b33ee35e"
            "041395d378d418a18acfe4c9e768ee37a"
        ),
        "repository": "Systran/faster-whisper-small.en",
        "requested_name": "small.en",
        "revision": "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
    },
    "candidate": {
        "canonical_repository": (
            "dropbox-dash/faster-whisper-large-v3-turbo"
        ),
        "model_binary_bytes": 1_617_884_929,
        "model_binary_sha256": (
            "e76620f83d5f5b69efd3d87e3dc180c1"
            "bd21df9fbebacfd4335e5e1efcc018da"
        ),
        "repository": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "requested_name": "large-v3-turbo",
        "revision": "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
    },
}
_RUNTIME_ENVIRONMENT = {
    "asr_runtime": {
        "compute_type": "int8_float32",
        "device": "cpu",
        "supported_cpu_compute_types": [
            "float32",
            "int16",
            "int8",
            "int8_float32",
        ],
    },
    "packages": {
        "av": "18.1.0",
        "ctranslate2": "4.8.1",
        "faster-whisper": "1.2.1",
        "huggingface-hub": "1.28.0",
        "onnxruntime": "1.23.2",
        "tokenizers": "0.23.1",
    },
    "platform": {
        "machine": "x86_64",
        "release": "24.4.0",
        "system": "Darwin",
        "version": (
            "Darwin Kernel Version 24.4.0: Fri Apr 11 18:28:23 PDT "
            "2025; root:xnu-11417.101.15~117/RELEASE_X86_64"
        ),
    },
    "python": {"implementation": "CPython", "version": "3.13.1"},
}
_RUN_MODELS = (
    {
        "baseline": {
            "campaign_id": "voices-b11f-run-01-small-en-baseline",
            "campaign_sha256": (
                "a058fb7d8ed17463671f93011ccb4ef7"
                "09efe39a1cce284c4d5c73b01d2e09e2"
            ),
            "campaign_version": "1.0.0",
            "metrics_sha256": (
                "4f61f2b62fa76d892f4a1959fbaccbde"
                "7aabb9fdfb743876b17cb1c7eb1306fa"
            ),
            "model_key": "small.en",
            "provider_key": "faster_whisper",
        },
        "candidate": {
            "campaign_id": "voices-b11f-run-01-large-v3-turbo-candidate",
            "campaign_sha256": (
                "2e5e0990068566b2d1b36fe8289518a9"
                "38f1d269487ab667ebae0470e586c920"
            ),
            "campaign_version": "1.0.0",
            "metrics_sha256": (
                "733006735beda54f24f9fc00ee400693"
                "02941b4ec84e70cef5cf9a1efddb53a1"
            ),
            "model_key": "large-v3-turbo",
            "provider_key": "faster_whisper",
        },
    },
    {
        "baseline": {
            "campaign_id": "voices-b11f-run-02-small-en-baseline",
            "campaign_sha256": (
                "07505929d0dbd939b6ed149e2c09b3f3"
                "415d1bf3805b6d51fae652fb49a841bd"
            ),
            "campaign_version": "1.0.0",
            "metrics_sha256": (
                "43bb1f70194aaa5df2d3f99ba5fae05"
                "bf5b1273d27fa5f4d84461614162e5e63"
            ),
            "model_key": "small.en",
            "provider_key": "faster_whisper",
        },
        "candidate": {
            "campaign_id": "voices-b11f-run-02-large-v3-turbo-candidate",
            "campaign_sha256": (
                "31226d17c956e717179d3dd135e1ee23"
                "3430233965e7138df55bbfd6c4783b99"
            ),
            "campaign_version": "1.0.0",
            "metrics_sha256": (
                "14007e39e2d617fa39fe9b35b44e98f"
                "9a6da57382b20f31918776007dbe4209a"
            ),
            "model_key": "large-v3-turbo",
            "provider_key": "faster_whisper",
        },
    },
    {
        "baseline": {
            "campaign_id": "voices-b11f-run-03-small-en-baseline",
            "campaign_sha256": (
                "92645e53fc6f13e53a057d5d0aeb4637"
                "1646a8977f9ceda28de74f7e5292bd1f"
            ),
            "campaign_version": "1.0.0",
            "metrics_sha256": (
                "d5c79f5b132e6855ac308c6e4424eec"
                "6326d00483d3904990a336d07b4e5a067"
            ),
            "model_key": "small.en",
            "provider_key": "faster_whisper",
        },
        "candidate": {
            "campaign_id": "voices-b11f-run-03-large-v3-turbo-candidate",
            "campaign_sha256": (
                "bb5c1c2af1f33481a7aa2b6ad4ed65e8"
                "a92c2a2e6e83b35c3dd4ac07364a6c38"
            ),
            "campaign_version": "1.0.0",
            "metrics_sha256": (
                "5dd3bd9aed2c42caeef0ec9fcf034a66"
                "52edcfd6c2a81b02fa6cb84cbcae87c9"
            ),
            "model_key": "large-v3-turbo",
            "provider_key": "faster_whisper",
        },
    },
)
_CHECKPOINT_BOUNDARY = {
    "absolute_audio_paths_embedded": False,
    "certification_issued": False,
    "cross_host_reproducibility_evaluated": False,
    "development_evidence_only": True,
    "independent_operating_system_processes_verified": False,
    "production_qualified": False,
    "qualification_threshold_applied": False,
    "raw_audio_embedded": False,
    "raw_generated_transcripts_embedded": False,
    "raw_reference_transcripts_embedded": False,
    "release_enforcement_eligible": False,
    "reproducibility_claimed": False,
    "same_environment_campaign_repeatability": True,
}
_ROOT_BOUNDARY = {
    "absolute_audio_paths_embedded": False,
    "certification_issued": False,
    "cross_host_reproducibility_evaluated": False,
    "development_evidence_only": True,
    "independent_operating_system_processes_verified": False,
    "model_winner_declared": False,
    "official_release_verdict_modified": False,
    "production_qualified": False,
    "qualification_threshold_applied": False,
    "raw_audio_embedded": False,
    "raw_generated_transcripts_embedded": False,
    "raw_reference_transcripts_embedded": False,
    "release_enforcement_eligible": False,
    "repeatability_evaluated": True,
    "repeatability_status": "stable",
    "reproducibility_claimed": False,
    "same_environment_campaign_repeatability": True,
    "statistical_generalization_claimed": False,
    "three_complete_b9_runs_reverified": True,
    "v1_reliability_scorecard_modified": False,
}
_INNER_ARTIFACT = {
    "key": (
        "hetren.asr.adversarial-human-external-voices-"
        "same-environment-campaign-repeatability"
    ),
    "type": "same_environment_campaign_repeatability_evidence",
    "version": "1.0.0",
}
_INNER_PROTOCOL = {
    "campaign_identity_rule": "distinct_per_role_per_run",
    "comparison_direction": "candidate_minus_baseline",
    "expected_run_count": _RUN_COUNT,
    "fixed_input_rule": "exact_hash_identity",
    "lower_error_values_are_better": True,
    "metric_equality": {
        "absolute_tolerance": _METRIC_EQUALITY_ABSOLUTE_TOLERANCE,
        "canonical_zero": True,
        "relative_tolerance": 0.0,
    },
    "normalized_transcript_rule": "exact_sha256_equality",
    "run_unit": "fixed_model_and_case_across_complete_campaigns",
    "transcript_rule": "exact_sha256_equality",
}
_INNER_MODELS = {
    "baseline": {
        "campaign_version": "1.0.0",
        "model_key": "small.en",
        "provider_key": "faster_whisper",
    },
    "candidate": {
        "campaign_version": "1.0.0",
        "model_key": "large-v3-turbo",
        "provider_key": "faster_whisper",
    },
}
_EXECUTION_ENVIRONMENT_SHA256S = {
    "baseline": (
        "dc24ecb529ce56f2a542e6e9c62ea70c"
        "dda53f65ebcd4b374dbd8f2ecd2a102d"
    ),
    "candidate": (
        "0877f1dc360f3beddbe9d22484b3a421"
        "bbe40fdcd7e81ace2a746555bc6f25c0"
    ),
}
_INNER_BOUNDARY = {
    "certification_issued": False,
    "complete_b9_runs_reverified_before_projection": True,
    "cross_host_reproducibility_evaluated": False,
    "development_evidence_only": True,
    "distinct_campaign_identities_verified": True,
    "fixed_cohort_and_model_identities_verified": True,
    "independent_operating_system_processes_verified": False,
    "model_winner_declared": False,
    "official_release_verdict_modified": False,
    "production_qualified": False,
    "qualification_threshold_applied": False,
    "raw_audio_embedded": False,
    "raw_generated_transcripts_embedded": False,
    "raw_reference_transcripts_embedded": False,
    "release_enforcement_eligible": False,
    "repeatability_threshold_applied": False,
    "reproducibility_claimed": False,
    "reproducibility_verified": None,
    "same_environment_campaign_repeatability_evaluated": True,
    "statistical_generalization_claimed": False,
    "v1_reliability_scorecard_modified": False,
}
_ENGINEER_METRICS = {
    "comparison_signal_stability": (
        "Metric and direction stability of aggregate comparisons."
    ),
    "exact_transcript_repeatability": (
        "Exact generated-transcript commitment stability."
    ),
    "metric_drift_envelope": (
        "Maximum and macro-mean WER/CER range across runs."
    ),
    "normalized_transcript_repeatability": (
        "Normalized transcript commitment stability."
    ),
    "runtime_identity_conformance": (
        "Fixed model/case environment commitment stability."
    ),
}


class ASRAdversarialVOiCESFrozenRepeatabilityError(ValueError):
    """Raised when frozen B11F evidence fails byte or semantic verification."""


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
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F evidence must be deterministic JSON."
        ) from error


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ASRAdversarialVOiCESFrozenRepeatabilityError(
                f"Frozen B11F JSON repeated key {key!r}."
            )
        value[key] = item
    return value


def _reject_non_finite(value: str) -> object:
    raise ASRAdversarialVOiCESFrozenRepeatabilityError(
        f"Frozen B11F JSON contains non-finite number {value!r}."
    )


def _parse_json(raw: bytes, *, name: str) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            f"{name} must be immutable bytes."
        )
    try:
        decoded = raw.decode("utf-8", errors="strict")
        value = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except ASRAdversarialVOiCESFrozenRepeatabilityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            f"{name} must be valid UTF-8 JSON."
        ) from error
    if not isinstance(value, dict):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            f"{name} root must be an object."
        )
    return value


def _require_exact_keys(
    value: object,
    *,
    expected: set[str],
    name: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            f"{name} keys changed."
        )
    return value


def _require_exact(value: object, expected: object, *, name: str) -> None:
    if _canonical_json_bytes(value) != _canonical_json_bytes(expected):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            f"{name} changed."
        )


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_HEX for character in value)
    ):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            f"{name} must be a lowercase SHA-256."
        )
    return value


def _require_text(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            f"{name} must be non-empty trimmed text."
        )
    return value


def _require_positive_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            f"{name} must be a positive integer."
        )
    return value


def _require_metric(value: object, *, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            f"{name} must be a finite non-negative metric."
        )
    return float(value)


def _canonical_metric(value: float) -> float:
    if math.isclose(
        value,
        0.0,
        rel_tol=0.0,
        abs_tol=_METRIC_EQUALITY_ABSOLUTE_TOLERANCE,
    ):
        return 0.0
    return value


def _metric_stable(values: tuple[float, ...]) -> bool:
    return all(
        math.isclose(
            values[0],
            value,
            rel_tol=0.0,
            abs_tol=_METRIC_EQUALITY_ABSOLUTE_TOLERANCE,
        )
        for value in values[1:]
    )


def _mean(values: Iterable[float]) -> float:
    values = tuple(values)
    if not values:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F mean requires observations."
        )
    return _canonical_metric(math.fsum(values) / len(values))


def _drift(values: tuple[float, ...]) -> float:
    return _canonical_metric(max(values) - min(values))


def _direction(value: float) -> str:
    value = _canonical_metric(value)
    if value == 0.0:
        return "equal"
    return "candidate_better" if value < 0 else "candidate_worse"


def _rate_payload(*, successful: int, observed: int) -> dict[str, object]:
    return {
        "successful_count": successful,
        "observed_count": observed,
        "rate": successful / observed,
        "score_percent": (successful / observed) * 100.0,
    }


def _pair_token(value: dict[str, object]) -> tuple[object, ...]:
    pair = _require_exact_keys(
        value,
        expected={"source_key", "room", "microphone_id", "angle_degrees"},
        name="Frozen B11F pair key",
    )
    source = pair["source_key"]
    if (
        not isinstance(source, list)
        or len(source) != 3
        or any(
            isinstance(item, bool)
            or not isinstance(item, int)
            or item <= 0
            for item in source
        )
    ):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F source key changed."
        )
    room = _require_text(pair["room"], name="Frozen B11F room")
    microphone = _require_positive_int(
        pair["microphone_id"], name="Frozen B11F microphone id"
    )
    angle = _require_positive_int(
        pair["angle_degrees"], name="Frozen B11F angle"
    )
    return (tuple(source), room, microphone, angle)


def _validate_case(
    value: object,
    *,
    role: str,
    model: dict[str, object],
) -> dict[str, object]:
    case = _require_exact_keys(
        value,
        expected={
            "role",
            "provider_key",
            "model_key",
            "case_id",
            "arm",
            "pair_key",
            "fixed_inputs",
            "outputs",
            "metrics",
        },
        name="Frozen B11F case-model unit",
    )
    if case["role"] != role:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F role ordering changed."
        )
    if (
        case["provider_key"] != model["provider_key"]
        or case["model_key"] != model["model_key"]
    ):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F case model identity changed."
        )
    _require_text(case["case_id"], name="Frozen B11F case id")
    if case["arm"] not in _ARMS:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F arm changed."
        )
    _pair_token(case["pair_key"])
    fixed = _require_exact_keys(
        case["fixed_inputs"],
        expected={
            "audio_asset_sha256",
            "reference_transcript_sha256",
            "normalized_reference_utf8_sha256",
        },
        name="Frozen B11F fixed inputs",
    )
    for key in fixed:
        _require_sha256(fixed[key], name=f"Frozen B11F {key}")
    outputs = _require_exact_keys(
        case["outputs"],
        expected={
            "execution_environment_sha256",
            "execution_evidence_sha256",
            "generated_transcript_sha256",
            "normalized_generated_utf8_sha256",
        },
        name="Frozen B11F outputs",
    )
    for key in outputs:
        _require_sha256(outputs[key], name=f"Frozen B11F {key}")
    if (
        outputs["execution_environment_sha256"]
        != _EXECUTION_ENVIRONMENT_SHA256S[role]
    ):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F execution environment link changed."
        )
    metrics = _require_exact_keys(
        case["metrics"],
        expected={"wer", "cer"},
        name="Frozen B11F case metrics",
    )
    for key in _METRICS:
        _require_metric(metrics[key], name=f"Frozen B11F {key.upper()}")
    return case


def _fixed_identity(case: dict[str, object]) -> tuple[object, ...]:
    return (
        case["case_id"],
        case["arm"],
        _pair_token(case["pair_key"]),
        _canonical_json_bytes(case["fixed_inputs"]),
    )


def _validate_run(value: object, *, index: int) -> dict[str, object]:
    run = _require_exact_keys(
        value,
        expected={
            "run_id",
            "execution_sha256",
            "upstream",
            "models",
            "case_model_units",
            "comparison_signals",
        },
        name="Frozen B11F run observation",
    )
    if run["run_id"] != B11F_RUN_IDS[index]:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F run identity changed."
        )
    if run["execution_sha256"] != B11F_B9_EXECUTION_SHA256S[index]:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F execution link changed."
        )
    _require_exact(
        run["upstream"],
        {
            "matched_control_suite_sha256": B11F_MATCHED_CONTROL_SUITE_SHA256,
            "adversarial_suite_evidence_sha256": (
                B11F_ADVERSARIAL_SUITE_EVIDENCE_SHA256
            ),
        },
        name="Frozen B11F run upstream identity",
    )
    _require_exact(
        run["models"],
        _RUN_MODELS[index],
        name="Frozen B11F run model links",
    )
    units = run["case_model_units"]
    if not isinstance(units, list) or len(units) != _UNIT_COUNT:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F run population changed."
        )
    baseline = tuple(
        _validate_case(value, role="baseline", model=_INNER_MODELS["baseline"])
        for value in units[:_CASE_COUNT_PER_MODEL]
    )
    candidate = tuple(
        _validate_case(value, role="candidate", model=_INNER_MODELS["candidate"])
        for value in units[_CASE_COUNT_PER_MODEL:]
    )
    baseline_ids = tuple(_fixed_identity(case) for case in baseline)
    candidate_ids = tuple(_fixed_identity(case) for case in candidate)
    if baseline_ids != candidate_ids or len(set(baseline_ids)) != len(baseline_ids):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F paired fixed inputs changed."
        )
    for role_cases in (baseline, candidate):
        pairs: dict[tuple[object, ...], set[str]] = {}
        for case in role_cases:
            pairs.setdefault(_pair_token(case["pair_key"]), set()).add(case["arm"])
        if len(pairs) != 16 or any(arms != set(_ARMS) for arms in pairs.values()):
            raise ASRAdversarialVOiCESFrozenRepeatabilityError(
                "Frozen B11F matched-control pairing changed."
            )
    signals = _require_exact_keys(
        run["comparison_signals"],
        expected={
            "general_accuracy_candidate_minus_baseline",
            "matched_control_robustness_candidate_minus_baseline",
        },
        name="Frozen B11F comparison signals",
    )
    for signal in signals.values():
        metric = _require_exact_keys(
            signal,
            expected={"wer", "cer"},
            name="Frozen B11F comparison signal",
        )
        for key in _METRICS:
            observed = metric[key]
            if (
                isinstance(observed, bool)
                or not isinstance(observed, (int, float))
                or not math.isfinite(observed)
            ):
                raise ASRAdversarialVOiCESFrozenRepeatabilityError(
                    "Frozen B11F comparison signal must be finite."
                )
    baseline_by_id = {case["case_id"]: case for case in baseline}
    candidate_by_id = {case["case_id"]: case for case in candidate}
    for metric_name in _METRICS:
        expected_general = _mean(
            float(candidate_by_id[case_id]["metrics"][metric_name])
            - float(baseline_by_id[case_id]["metrics"][metric_name])
            for case_id in baseline_by_id
        )
        actual_general = float(
            signals["general_accuracy_candidate_minus_baseline"][metric_name]
        )
        if not math.isclose(
            actual_general,
            expected_general,
            rel_tol=0.0,
            abs_tol=_METRIC_EQUALITY_ABSOLUTE_TOLERANCE,
        ):
            raise ASRAdversarialVOiCESFrozenRepeatabilityError(
                "Frozen B11F general-accuracy signal changed."
            )
        pair_deltas = []
        for pair in {
            _pair_token(case["pair_key"])
            for case in baseline
        }:
            b = {
                case["arm"]: case
                for case in baseline
                if _pair_token(case["pair_key"]) == pair
            }
            c = {
                case["arm"]: case
                for case in candidate
                if _pair_token(case["pair_key"]) == pair
            }
            baseline_delta = _canonical_metric(
                float(b["babble"]["metrics"][metric_name])
                - float(b["control"]["metrics"][metric_name])
            )
            candidate_delta = _canonical_metric(
                float(c["babble"]["metrics"][metric_name])
                - float(c["control"]["metrics"][metric_name])
            )
            pair_deltas.append(
                _canonical_metric(candidate_delta - baseline_delta)
            )
        expected_robustness = _mean(pair_deltas)
        actual_robustness = float(
            signals[
                "matched_control_robustness_candidate_minus_baseline"
            ][metric_name]
        )
        if not math.isclose(
            actual_robustness,
            expected_robustness,
            rel_tol=0.0,
            abs_tol=_METRIC_EQUALITY_ABSOLUTE_TOLERANCE,
        ):
            raise ASRAdversarialVOiCESFrozenRepeatabilityError(
                "Frozen B11F matched-control signal changed."
            )
    observed_sha256 = hashlib.sha256(_canonical_json_bytes(run)).hexdigest()
    if observed_sha256 != B11F_RUN_OBSERVATION_SHA256S[index]:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F run observation identity changed."
        )
    return run


def _unit_payload(
    cases: tuple[dict[str, object], ...],
) -> dict[str, object]:
    anchor = cases[0]
    outputs = tuple(case["outputs"] for case in cases)
    metrics = tuple(case["metrics"] for case in cases)
    wer_values = tuple(float(value["wer"]) for value in metrics)
    cer_values = tuple(float(value["cer"]) for value in metrics)
    return {
        "role": anchor["role"],
        "provider_key": anchor["provider_key"],
        "model_key": anchor["model_key"],
        "case_id": anchor["case_id"],
        "arm": anchor["arm"],
        "pair_key": anchor["pair_key"],
        "fixed_inputs": anchor["fixed_inputs"],
        "run_observations": [
            {
                "run_id": B11F_RUN_IDS[index],
                "execution_environment_sha256": value[
                    "execution_environment_sha256"
                ],
                "execution_evidence_sha256": value[
                    "execution_evidence_sha256"
                ],
                "generated_transcript_sha256": value[
                    "generated_transcript_sha256"
                ],
                "normalized_generated_utf8_sha256": value[
                    "normalized_generated_utf8_sha256"
                ],
                "wer": metrics[index]["wer"],
                "cer": metrics[index]["cer"],
            }
            for index, value in enumerate(outputs)
        ],
        "metrics": {
            "raw_transcript_stable": len(
                {value["generated_transcript_sha256"] for value in outputs}
            )
            == 1,
            "normalized_transcript_stable": len(
                {
                    value["normalized_generated_utf8_sha256"]
                    for value in outputs
                }
            )
            == 1,
            "runtime_identity_conformant": len(
                {value["execution_environment_sha256"] for value in outputs}
            )
            == 1,
            "wer_stable": _metric_stable(wer_values),
            "cer_stable": _metric_stable(cer_values),
            "wer_drift_envelope": _drift(wer_values),
            "cer_drift_envelope": _drift(cer_values),
        },
    }


def _unit_aggregate(units: tuple[dict[str, object], ...]) -> dict[str, object]:
    observed = len(units)
    metrics = tuple(value["metrics"] for value in units)
    wer_drifts = tuple(float(value["wer_drift_envelope"]) for value in metrics)
    cer_drifts = tuple(float(value["cer_drift_envelope"]) for value in metrics)
    return {
        "unit_count": observed,
        "exact_transcript_repeatability": _rate_payload(
            successful=sum(value["raw_transcript_stable"] for value in metrics),
            observed=observed,
        ),
        "normalized_transcript_repeatability": _rate_payload(
            successful=sum(
                value["normalized_transcript_stable"] for value in metrics
            ),
            observed=observed,
        ),
        "runtime_identity_conformance": _rate_payload(
            successful=sum(
                value["runtime_identity_conformant"] for value in metrics
            ),
            observed=observed,
        ),
        "wer_stability": _rate_payload(
            successful=sum(value["wer_stable"] for value in metrics),
            observed=observed,
        ),
        "cer_stability": _rate_payload(
            successful=sum(value["cer_stable"] for value in metrics),
            observed=observed,
        ),
        "wer_drift_envelope": {
            "maximum": max(wer_drifts),
            "macro_mean": _mean(wer_drifts),
        },
        "cer_drift_envelope": {
            "maximum": max(cer_drifts),
            "macro_mean": _mean(cer_drifts),
        },
    }


def _signal_stability(
    *,
    runs: tuple[dict[str, object], ...],
    section: str,
    metric: str,
) -> dict[str, object]:
    values = tuple(
        float(run["comparison_signals"][section][metric]) for run in runs
    )
    directions = tuple(_direction(value) for value in values)
    return {
        "values_by_run": [
            {
                "run_id": B11F_RUN_IDS[index],
                "value": value,
                "direction": directions[index],
            }
            for index, value in enumerate(values)
        ],
        "metric_stable": _metric_stable(values),
        "direction_stable": len(set(directions)) == 1,
        "drift_envelope": _drift(values),
    }


def _derive_repeatability(
    runs: tuple[dict[str, object], ...],
) -> tuple[tuple[dict[str, object], ...], dict[str, object], str]:
    first_units = runs[0]["case_model_units"]
    identities = tuple(
        (value["role"], value["case_id"]) for value in first_units
    )
    if len(set(identities)) != len(identities):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F unit identity repeated."
        )
    by_run = tuple(
        {
            (value["role"], value["case_id"]): value
            for value in run["case_model_units"]
        }
        for run in runs
    )
    if any(tuple(value) != identities for value in by_run[1:]):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F unit ordering changed across runs."
        )
    units = []
    for identity in identities:
        cases = tuple(value[identity] for value in by_run)
        anchor = cases[0]
        if any(
            _fixed_identity(value) != _fixed_identity(anchor)
            or value["provider_key"] != anchor["provider_key"]
            or value["model_key"] != anchor["model_key"]
            for value in cases[1:]
        ):
            raise ASRAdversarialVOiCESFrozenRepeatabilityError(
                "Frozen B11F fixed unit changed across runs."
            )
        units.append(_unit_payload(cases))
    units_tuple = tuple(units)
    overall = _unit_aggregate(units_tuple)
    by_role = {
        role: tuple(value for value in units_tuple if value["role"] == role)
        for role in _ROLES
    }
    signals = {
        "general_accuracy_wer": _signal_stability(
            runs=runs,
            section="general_accuracy_candidate_minus_baseline",
            metric="wer",
        ),
        "general_accuracy_cer": _signal_stability(
            runs=runs,
            section="general_accuracy_candidate_minus_baseline",
            metric="cer",
        ),
        "matched_control_robustness_wer": _signal_stability(
            runs=runs,
            section="matched_control_robustness_candidate_minus_baseline",
            metric="wer",
        ),
        "matched_control_robustness_cer": _signal_stability(
            runs=runs,
            section="matched_control_robustness_candidate_minus_baseline",
            metric="cer",
        ),
    }
    aggregate = {
        "overall": overall,
        "models": {
            role: _unit_aggregate(values) for role, values in by_role.items()
        },
        "comparison_signal_stability": signals,
    }
    stable = (
        all(
            overall[key]["successful_count"] == _UNIT_COUNT
            for key in (
                "exact_transcript_repeatability",
                "normalized_transcript_repeatability",
                "runtime_identity_conformance",
                "wer_stability",
                "cer_stability",
            )
        )
        and all(
            value["metric_stable"] and value["direction_stable"]
            for value in signals.values()
        )
    )
    return units_tuple, aggregate, "stable" if stable else "variation_observed"


@dataclass(frozen=True, slots=True)
class _VerifiedFrozenRepeatability:
    root: dict[str, object]
    aggregate: dict[str, object]
    checkpoint_file_sha256s: tuple[str, ...]


def _verify_checkpoint(
    raw: bytes,
    *,
    index: int,
    expected_run: dict[str, object],
) -> str:
    if len(raw) != B11F_RUN_CHECKPOINT_BYTES[index]:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F checkpoint byte length changed."
        )
    observed_file_sha256 = hashlib.sha256(raw).hexdigest()
    if observed_file_sha256 != B11F_RUN_CHECKPOINT_FILE_SHA256S[index]:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F checkpoint file identity changed."
        )
    root = _parse_json(raw, name="Frozen B11F checkpoint")
    _require_exact_keys(
        root,
        expected={
            "schema_version",
            "artifact",
            "source_code",
            "execution_protocol",
            "models",
            "runtime_environment",
            "runtime_environment_sha256",
            "run_observation",
            "run_observation_sha256",
            "evidence_boundary",
        },
        name="Frozen B11F checkpoint root",
    )
    _require_exact(root["schema_version"], _SCHEMA_VERSION, name="checkpoint schema")
    _require_exact(
        root["artifact"],
        {
            "key": "hetren.asr.b11f-real-repeatability-run-observation",
            "type": "content-free-complete-b9-run-observation",
            "version": "1.0.0",
        },
        name="Frozen B11F checkpoint artifact",
    )
    for name, expected in (
        ("source_code", _SOURCE_CODE),
        ("execution_protocol", _EXECUTION_PROTOCOL),
        ("models", _MODELS),
        ("runtime_environment", _RUNTIME_ENVIRONMENT),
        ("runtime_environment_sha256", B11F_RUNTIME_ENVIRONMENT_SHA256),
        ("evidence_boundary", _CHECKPOINT_BOUNDARY),
        ("run_observation", expected_run),
        ("run_observation_sha256", B11F_RUN_OBSERVATION_SHA256S[index]),
    ):
        _require_exact(root[name], expected, name=f"Frozen B11F checkpoint {name}")
    return observed_file_sha256


def _verify_frozen_evidence(
    *,
    artifact_bytes: bytes,
    run_checkpoint_bytes: tuple[bytes, ...],
) -> _VerifiedFrozenRepeatability:
    if not isinstance(artifact_bytes, bytes):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F artifact must be immutable bytes."
        )
    if (
        not isinstance(run_checkpoint_bytes, tuple)
        or len(run_checkpoint_bytes) != _RUN_COUNT
        or any(not isinstance(value, bytes) for value in run_checkpoint_bytes)
    ):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F requires exactly three immutable checkpoint files."
        )
    if len(artifact_bytes) != B11F_ARTIFACT_BYTES:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F artifact byte length changed."
        )
    if hashlib.sha256(artifact_bytes).hexdigest() != B11F_ARTIFACT_SHA256:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F artifact file identity changed."
        )
    root = _parse_json(artifact_bytes, name="Frozen B11F artifact")
    _require_exact_keys(
        root,
        expected={
            "schema_version",
            "artifact",
            "source_code",
            "execution_protocol",
            "models",
            "runtime_environment",
            "runtime_environment_sha256",
            "upstream",
            "repeatability",
            "repeatability_sha256",
            "evidence_boundary",
        },
        name="Frozen B11F artifact root",
    )
    static_sections = (
        ("schema_version", _SCHEMA_VERSION),
        (
            "artifact",
            {
                "key": B11F_ARTIFACT_KEY,
                "type": B11F_ARTIFACT_TYPE,
                "version": B11F_ARTIFACT_VERSION,
            },
        ),
        ("source_code", _SOURCE_CODE),
        ("execution_protocol", _EXECUTION_PROTOCOL),
        ("models", _MODELS),
        ("runtime_environment", _RUNTIME_ENVIRONMENT),
        ("runtime_environment_sha256", B11F_RUNTIME_ENVIRONMENT_SHA256),
        ("evidence_boundary", _ROOT_BOUNDARY),
    )
    for name, expected in static_sections:
        _require_exact(root[name], expected, name=f"Frozen B11F {name}")
    runtime_sha256 = hashlib.sha256(
        _canonical_json_bytes(root["runtime_environment"])
    ).hexdigest()
    if runtime_sha256 != B11F_RUNTIME_ENVIRONMENT_SHA256:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F runtime environment commitment changed."
        )
    _require_exact(
        root["upstream"],
        {
            "adversarial_suite_evidence_sha256": (
                B11F_ADVERSARIAL_SUITE_EVIDENCE_SHA256
            ),
            "matched_control_projection_sha256": (
                B11F_MATCHED_CONTROL_PROJECTION_SHA256
            ),
            "matched_control_suite_sha256": B11F_MATCHED_CONTROL_SUITE_SHA256,
            "ordered_run_checkpoint_file_sha256s": list(
                B11F_RUN_CHECKPOINT_FILE_SHA256S
            ),
            "ordered_run_observation_sha256s": list(
                B11F_RUN_OBSERVATION_SHA256S
            ),
        },
        name="Frozen B11F outer upstream links",
    )
    inner = _require_exact_keys(
        root["repeatability"],
        expected={
            "schema_version",
            "artifact",
            "protocol",
            "upstream",
            "status",
            "models",
            "population",
            "runs",
            "repeatability",
            "evidence_boundary",
        },
        name="Frozen B11F repeatability payload",
    )
    for name, expected in (
        ("schema_version", _SCHEMA_VERSION),
        ("artifact", _INNER_ARTIFACT),
        ("protocol", _INNER_PROTOCOL),
        (
            "upstream",
            {
                "adversarial_suite_evidence_sha256": (
                    B11F_ADVERSARIAL_SUITE_EVIDENCE_SHA256
                ),
                "matched_control_suite_sha256": (
                    B11F_MATCHED_CONTROL_SUITE_SHA256
                ),
                "ordered_b9_execution_sha256s": list(B11F_B9_EXECUTION_SHA256S),
                "ordered_run_observation_sha256s": list(
                    B11F_RUN_OBSERVATION_SHA256S
                ),
            },
        ),
        ("models", _INNER_MODELS),
        (
            "population",
            {
                "run_count": _RUN_COUNT,
                "model_count": _MODEL_COUNT,
                "case_count_per_model": _CASE_COUNT_PER_MODEL,
                "case_model_unit_count": _UNIT_COUNT,
                "execution_count": _EXECUTION_COUNT,
                "ordered_run_ids": list(B11F_RUN_IDS),
            },
        ),
        ("evidence_boundary", _INNER_BOUNDARY),
    ):
        _require_exact(inner[name], expected, name=f"Frozen B11F inner {name}")
    raw_runs = inner["runs"]
    if not isinstance(raw_runs, list) or len(raw_runs) != _RUN_COUNT:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F run count changed."
        )
    runs = tuple(
        _validate_run(value, index=index)
        for index, value in enumerate(raw_runs)
    )
    units, aggregate, status = _derive_repeatability(runs)
    derived = _require_exact_keys(
        inner["repeatability"],
        expected={"engineer_metrics", "aggregate", "case_model_units"},
        name="Frozen B11F derived repeatability",
    )
    _require_exact(
        derived["engineer_metrics"],
        _ENGINEER_METRICS,
        name="Frozen B11F engineer metric definitions",
    )
    _require_exact(
        derived["case_model_units"],
        list(units),
        name="Frozen B11F derived unit evidence",
    )
    _require_exact(
        derived["aggregate"],
        aggregate,
        name="Frozen B11F derived aggregate",
    )
    if status != B11F_STATUS or inner["status"] != status:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F repeatability status changed."
        )
    observed_repeatability_sha256 = hashlib.sha256(
        _canonical_json_bytes(inner)
    ).hexdigest()
    if (
        observed_repeatability_sha256 != B11F_REPEATABILITY_SHA256
        or root["repeatability_sha256"] != B11F_REPEATABILITY_SHA256
    ):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F repeatability identity changed."
        )
    checkpoint_sha256s = tuple(
        _verify_checkpoint(
            raw,
            index=index,
            expected_run=runs[index],
        )
        for index, raw in enumerate(run_checkpoint_bytes)
    )
    return _VerifiedFrozenRepeatability(
        root=root,
        aggregate=aggregate,
        checkpoint_file_sha256s=checkpoint_sha256s,
    )


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESFrozenRepeatabilityBundle:
    """Tamper-detecting B11G verification of the exact real B11F evidence."""

    artifact_bytes: bytes = field(repr=False)
    run_checkpoint_bytes: tuple[bytes, ...] = field(repr=False)
    _verified: _VerifiedFrozenRepeatability = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_verified",
            _verify_frozen_evidence(
                artifact_bytes=self.artifact_bytes,
                run_checkpoint_bytes=self.run_checkpoint_bytes,
            ),
        )

    @property
    def payload(self) -> dict[str, object]:
        aggregate = self._verified.aggregate
        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_SCHEMA_VERSION
            ),
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_KEY,
                "version": ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_VERSION,
                "type": "frozen_real_repeatability_semantic_verification",
            },
            "frozen_evidence": {
                "source_branch": B11F_SOURCE_BRANCH,
                "source_git_head": B11F_SOURCE_GIT_HEAD,
                "artifact_bytes": B11F_ARTIFACT_BYTES,
                "artifact_file_sha256": B11F_ARTIFACT_SHA256,
                "repeatability_sha256": B11F_REPEATABILITY_SHA256,
                "ordered_run_checkpoint_file_sha256s": list(
                    self._verified.checkpoint_file_sha256s
                ),
                "ordered_run_observation_sha256s": list(
                    B11F_RUN_OBSERVATION_SHA256S
                ),
            },
            "verification": {
                "exact_artifact_bytes_verified": True,
                "three_exact_checkpoint_files_verified": True,
                "duplicate_json_keys_rejected": True,
                "source_runtime_and_model_pins_verified": True,
                "checkpoint_to_final_run_links_verified": True,
                "fixed_cohort_links_verified": True,
                "run_observation_hashes_recomputed": True,
                "comparison_signals_independently_checked": True,
                "unit_metrics_and_aggregates_recomputed": True,
                "repeatability_identity_recomputed": True,
            },
            "result": {
                "status": B11F_STATUS,
                "population": {
                    "run_count": _RUN_COUNT,
                    "model_count": _MODEL_COUNT,
                    "case_count_per_model": _CASE_COUNT_PER_MODEL,
                    "case_model_unit_count": _UNIT_COUNT,
                    "execution_count": _EXECUTION_COUNT,
                },
                "models": _INNER_MODELS,
                "overall": aggregate["overall"],
                "comparison_signal_stability": aggregate[
                    "comparison_signal_stability"
                ],
            },
            "evidence_boundary": {
                "development_evidence_only": True,
                "content_free_json_evidence_only": True,
                "audio_reexecuted_by_frozen_verifier": False,
                "same_environment_campaign_repeatability_verified": True,
                "independent_operating_system_processes_verified": False,
                "cross_host_reproducibility_evaluated": False,
                "reproducibility_verified": None,
                "reproducibility_claimed": False,
                "repeatability_threshold_applied": False,
                "qualification_threshold_applied": False,
                "statistical_generalization_claimed": False,
                "model_winner_declared": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
                "v1_reliability_scorecard_modified": False,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()

    def require_reproducibility_verified(self) -> None:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen same-environment repeatability cannot establish "
            "cross-host reproducibility."
        )

    def require_repeatability_qualification(self) -> None:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "B11G verifies frozen descriptive evidence; no qualification "
            "threshold or release verdict was applied."
        )


def evaluate_asr_adversarial_voices_frozen_repeatability_v1(
    *,
    artifact_bytes: bytes,
    run_checkpoint_bytes: tuple[bytes, ...],
) -> ASRAdversarialVOiCESFrozenRepeatabilityBundle:
    """Verify the exact final B11F artifact and its three run checkpoints."""

    return ASRAdversarialVOiCESFrozenRepeatabilityBundle(
        artifact_bytes=artifact_bytes,
        run_checkpoint_bytes=run_checkpoint_bytes,
    )


def evaluate_asr_adversarial_voices_frozen_repeatability_files_v1(
    *,
    artifact_path: str | Path,
    run_checkpoint_paths: tuple[str | Path, ...],
) -> ASRAdversarialVOiCESFrozenRepeatabilityBundle:
    """Read B11F evidence without embedding caller paths in the result."""

    if (
        not isinstance(run_checkpoint_paths, tuple)
        or len(run_checkpoint_paths) != _RUN_COUNT
    ):
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F file verification requires exactly three checkpoints."
        )
    try:
        artifact_bytes = Path(artifact_path).read_bytes()
        checkpoint_bytes = tuple(
            Path(value).read_bytes() for value in run_checkpoint_paths
        )
    except (OSError, TypeError, ValueError) as error:
        raise ASRAdversarialVOiCESFrozenRepeatabilityError(
            "Frozen B11F evidence files could not be read."
        ) from error
    return evaluate_asr_adversarial_voices_frozen_repeatability_v1(
        artifact_bytes=artifact_bytes,
        run_checkpoint_bytes=checkpoint_bytes,
    )
