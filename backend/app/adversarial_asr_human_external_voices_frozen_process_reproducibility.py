"""Verify the exact frozen B11H VOiCES process-evidence file set.

B11I consumes the ten content-free JSON files retained by the real B11H
controller: three launch precommitments, three child results, three finalized
process runs, and one final process-reproducibility artifact.  It pins their
raw byte identities, rejects ambiguous JSON, replays the B11H loaders, checks
every cross-file link, recomputes the process aggregate, and verifies the
outer source/runtime/model/cohort commitments.

The verifier never loads an ASR model, reads audio, or reruns transcription.
Its positive result is limited to the exact same-host, process-isolated
development evidence.  It does not establish cross-host reproducibility,
qualification, certification, production readiness, or release authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from os import PathLike
from pathlib import Path
from typing import Any, Mapping

from app.adversarial_asr_human_external_voices_process_reproducibility import (
    ASRAdversarialVOiCESProcessReproducibilityBundle,
    ASRAdversarialVOiCESProcessReproducibilityError,
    ASRAdversarialVOiCESProcessRunObservation,
    evaluate_asr_adversarial_voices_process_reproducibility_v1,
    load_asr_adversarial_voices_child_process_result_v1,
    load_asr_adversarial_voices_process_launch_definition_v1,
    load_asr_adversarial_voices_process_run_observation_v1,
)


ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_KEY = (
    "hetren.asr.adversarial-human-external-voices-"
    "frozen-same-host-process-isolated-reproducibility"
)

B11H_SOURCE_BRANCH = "feature/hvee-asr-adversarial-qualification-v1"
B11H_SOURCE_GIT_HEAD = "4edb29bc509e5c34d317ab8f784c64305514a795"
B11H_FINAL_ARTIFACT_NAME = (
    "b11h-small-en-vs-large-v3-turbo-process-reproducibility.json"
)
B11H_FINAL_ARTIFACT_BYTES = 339_377
B11H_FINAL_ARTIFACT_SHA256 = (
    "21a19684920a2b27a25ae2fde0d57b0b"
    "d06c96cd7da95588eff5b936d7a955d2"
)
B11H_PROCESS_REPRODUCIBILITY_SHA256 = (
    "a1674360751c03d1706bf6a977dbc9d8"
    "cea84bbed02d33def09b25d372ecb75d"
)

B11H_FROZEN_FILE_IDENTITIES: Mapping[str, Mapping[str, object]] = {
    "launch-01.json": {
        "bytes": 1_059,
        "sha256": (
            "5329735d0f753d8757a9eb75ccc59a23"
            "cff0747f50bd9e8d182b0308cd09e322"
        ),
    },
    "launch-02.json": {
        "bytes": 1_059,
        "sha256": (
            "2ca0c36b0b90787d4cb379f10c9bb2b"
            "dccb94a57fd1b1789fb16123c4eee43d2"
        ),
    },
    "launch-03.json": {
        "bytes": 1_059,
        "sha256": (
            "6a4470ac34700da3ff4bbb384e529fca"
            "95ce012e15e1fdacd4592ef7589f4f6a"
        ),
    },
    "child-result-01.json": {
        "bytes": 92_087,
        "sha256": (
            "373d866ab0dbcf3bfa4b6c740111eb5a"
            "a388135e5899796c7579f2d2834a862e"
        ),
    },
    "child-result-02.json": {
        "bytes": 92_087,
        "sha256": (
            "f8309d7a1a94f67b7b423e39a8d68d0"
            "1262a4d9e91b54b4d5c1fae057e2850f8"
        ),
    },
    "child-result-03.json": {
        "bytes": 92_087,
        "sha256": (
            "16baab408d90b06b3cd8990c38e8674c"
            "ded4374525602c10d6281b6c3c0a9407"
        ),
    },
    "process-run-01.json": {
        "bytes": 92_378,
        "sha256": (
            "2f03748dd0bc9e9b418b540034e15382"
            "ca31e5264a03c3232a48d3199fbfb130"
        ),
    },
    "process-run-02.json": {
        "bytes": 92_378,
        "sha256": (
            "d37ecc0b306530dbd55675a7dc1f290b"
            "cae33c2a2fcae2a8bedc71fe299ae14b"
        ),
    },
    "process-run-03.json": {
        "bytes": 92_378,
        "sha256": (
            "46ea3c8d8e164214d73c625e76a89773"
            "8add3f385734a90aef8fc27bd4e163a9"
        ),
    },
    B11H_FINAL_ARTIFACT_NAME: {
        "bytes": B11H_FINAL_ARTIFACT_BYTES,
        "sha256": B11H_FINAL_ARTIFACT_SHA256,
    },
}

_RUN_IDS = tuple(
    f"b11h-same-host-process-run-{number:02d}" for number in range(1, 4)
)
_LAUNCH_NAMES = tuple(f"launch-{number:02d}.json" for number in range(1, 4))
_CHILD_NAMES = tuple(
    f"child-result-{number:02d}.json" for number in range(1, 4)
)
_PROCESS_NAMES = tuple(
    f"process-run-{number:02d}.json" for number in range(1, 4)
)

_B11H_FINAL_ARTIFACT = {
    "key": "hetren.asr.b11h-real-same-host-process-isolated-reproducibility",
    "version": "1.0.0",
    "type": "pinned-real-same-host-process-isolated-reproducibility-evidence",
}
_B11H_EXECUTION_PROTOCOL = {
    "process_run_count": 3,
    "model_count": 2,
    "case_count_per_model": 32,
    "case_model_units_per_process": 64,
    "total_real_transcription_count": 192,
    "controller_precommits_each_launch": True,
    "direct_child_process_per_complete_b9_run": True,
    "fresh_provider_instances_per_child": True,
    "fresh_model_instances_per_child": True,
    "parent_observes_child_pid_and_exit_code": True,
    "child_reports_pid_parent_pid_and_commitments": True,
    "cross_host_execution": False,
    "campaign_version": "1.0.0",
}
_B11H_MODELS = {
    "baseline": {
        "requested_name": "small.en",
        "repository": "Systran/faster-whisper-small.en",
        "canonical_repository": "Systran/faster-whisper-small.en",
        "revision": "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
        "model_binary_bytes": 483_545_366,
        "model_binary_sha256": (
            "62b2a45b05ee59acb4a5341b33ee35e0"
            "41395d378d418a18acfe4c9e768ee37a"
        ),
    },
    "candidate": {
        "requested_name": "large-v3-turbo",
        "repository": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "canonical_repository": "dropbox-dash/faster-whisper-large-v3-turbo",
        "revision": "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
        "model_binary_bytes": 1_617_884_929,
        "model_binary_sha256": (
            "e76620f83d5f5b69efd3d87e3dc180c1"
            "bd21df9fbebacfd4335e5e1efcc018da"
        ),
    },
}
_B11H_RUNTIME_ENVIRONMENT = {
    "python": {"implementation": "CPython", "version": "3.13.1"},
    "packages": {
        "faster-whisper": "1.2.1",
        "ctranslate2": "4.8.1",
        "huggingface-hub": "1.28.0",
        "tokenizers": "0.23.1",
        "onnxruntime": "1.23.2",
        "av": "18.1.0",
    },
    "asr_runtime": {
        "device": "cpu",
        "compute_type": "int8_float32",
        "supported_cpu_compute_types": [
            "float32",
            "int16",
            "int8",
            "int8_float32",
        ],
    },
}
_B11H_HOST_ENVIRONMENT = {
    "platform": {
        "system": "Darwin",
        "release": "24.4.0",
        "version": (
            "Darwin Kernel Version 24.4.0: Fri Apr 11 18:28:23 PDT 2025; "
            "root:xnu-11417.101.15~117/RELEASE_X86_64"
        ),
        "machine": "x86_64",
    }
}
_B11H_SOURCE_FILES = [
    {
        "label": (
            "backend/app/adversarial_asr_human_external_voices_"
            "process_reproducibility.py"
        ),
        "bytes": 68_474,
        "sha256": (
            "13e8f4e9b4b8b9583cc394504df41acc"
            "9431812932da31e015a844a6479827ef"
        ),
    },
    {
        "label": (
            "backend/app/adversarial_asr_human_external_voices_"
            "repeatability.py"
        ),
        "bytes": 44_097,
        "sha256": (
            "07dc6e9e102655786f2cdb5ac65f5952"
            "430b768eefefde9b7d3817947bf1bee0"
        ),
    },
    {
        "label": (
            "backend/app/adversarial_asr_human_external_voices_"
            "model_comparison_execution.py"
        ),
        "bytes": 21_453,
        "sha256": (
            "fdf9129280b774118173ded74a6a978e1"
            "531056a7aa7cfbcdf206c85a9b46a0a"
        ),
    },
    {
        "label": (
            "backend/app/adversarial_asr_human_external_voices_"
            "materialization_service.py"
        ),
        "bytes": 85_631,
        "sha256": (
            "9648011626bd38ea241ae5c2d31abaccd"
            "14e7b2ce597f049509e9e56704bc82d"
        ),
    },
    {
        "label": (
            "backend/app/adversarial_asr_human_external_voices_"
            "matched_control_projection.py"
        ),
        "bytes": 25_367,
        "sha256": (
            "e18f2e9f49cebc73b86685d943cd69cf"
            "8c917418df58953fd1ac5f8e1ee525ed"
        ),
    },
    {
        "label": (
            "backend/app/adversarial_asr_human_external_voices_"
            "matched_control_suite_projection.py"
        ),
        "bytes": 36_468,
        "sha256": (
            "15e86318e56e790d52638f35e413e7fb"
            "006647dde22c5320a088f4c17c5aea2a"
        ),
    },
    {
        "label": "backend/app/speech/faster_whisper_provider.py",
        "bytes": 7_104,
        "sha256": (
            "85e09fcce1ea8bddca0c520e798b3e3d"
            "7299361c3105c5cd26c4794ea15c57eb"
        ),
    },
    {
        "label": "runtime/hetren_b11f_real_repeatability.py",
        "bytes": 24_608,
        "sha256": (
            "034e1bfadd4323dd3e4f4b86c495ce11"
            "b6e6a31362a160e4ba0dc1abb886953c"
        ),
    },
    {
        "label": "runtime/hetren_b11h_real_process_reproducibility.py",
        "bytes": 32_980,
        "sha256": (
            "5c73fcb20d2dead99e802e6fb99f331e"
            "223fce09ad232f91f80216c252be8abb"
        ),
    },
]
_B11H_SOURCE_MANIFEST = {
    "branch": B11H_SOURCE_BRANCH,
    "git_head": B11H_SOURCE_GIT_HEAD,
    "files": _B11H_SOURCE_FILES,
}
_B11H_SOURCE_CODE_SHA256 = (
    "85393073bc837b4dd685680a360622eb2"
    "b410aec13d38d2e2119f536eb727a2d"
)
_B11H_PYTHON_EXECUTABLE_SHA256 = (
    "20c9c2144a9f5202177620417e67643f"
    "b551aa31586e5d3c1361627b920cadb0"
)
_B11H_RUNTIME_ENVIRONMENT_SHA256 = (
    "ddb0541baa1fd8578284c9981a9ce04f"
    "ff06f2bd521ba63bf2909e16cf66a39f"
)
_B11H_HOST_ENVIRONMENT_SHA256 = (
    "8f992cea0b800c9e152f57d2645c697a"
    "14e1b565601d9b3248864f91ff312b01"
)
_B11H_MODEL_SET_SHA256 = (
    "f2da5bf4ff8424ed92475cb99f9d6824"
    "c7850ed3be1e6a8dd74c63290347966e"
)
_MATCHED_CONTROL_PROJECTION_SHA256 = (
    "4c86b6aa1ddcdae6cfec7776289e73e5"
    "69ecd9a8bbc59bf8d9614e87647f1063"
)
_MATCHED_CONTROL_SUITE_SHA256 = (
    "a5d4a0d17ba91a0bcc13e2f1721e0d6"
    "bbd5830511101a76d54e298f194b48933"
)
_ADVERSARIAL_SUITE_EVIDENCE_SHA256 = (
    "dece60176bf46742bd4323fbb70c1fc36"
    "da1a6b742ce2fb1215151928b878af3"
)
_B11H_CONTROLLER_INVOCATION = {
    "artifact_key": "hetren.asr.b11h-real-same-host-process-controller",
    "artifact_version": "1.0.0",
    "branch": B11H_SOURCE_BRANCH,
    "git_head": B11H_SOURCE_GIT_HEAD,
    "controller_script_sha256": _B11H_SOURCE_FILES[-1]["sha256"],
    "python_executable_sha256": _B11H_PYTHON_EXECUTABLE_SHA256,
    "ordered_run_ids": list(_RUN_IDS),
    "execution_protocol": _B11H_EXECUTION_PROTOCOL,
}
_B11H_CONTROLLER_INVOCATION_SHA256 = (
    "fcd50ea793d16cc13361a5c7efcf6e02"
    "829a4ad0b472621e02192098b5edf534"
)
_B11H_OUTER_BOUNDARY = {
    "development_evidence_only": True,
    "three_fresh_complete_b9_runs_executed": True,
    "three_direct_child_processes_verified": True,
    "same_host_process_isolated_reproducibility_evaluated": True,
    "same_host_process_reproducibility_verified": True,
    "cross_host_reproducibility_evaluated": False,
    "cross_host_reproducibility_verified": None,
    "reproducibility_verified": None,
    "qualification_threshold_applied": False,
    "statistical_generalization_claimed": False,
    "model_winner_declared": False,
    "certification_issued": False,
    "production_qualified": False,
    "release_enforcement_eligible": False,
    "official_release_verdict_modified": False,
    "v1_reliability_scorecard_modified": False,
}

_FINAL_ROOT_KEYS = (
    "schema_version",
    "artifact",
    "source_code",
    "models",
    "runtime_environment",
    "runtime_environment_sha256",
    "host_environment",
    "host_environment_sha256",
    "model_set_sha256",
    "python_executable_sha256",
    "controller_invocation",
    "controller_invocation_sha256",
    "execution_protocol",
    "upstream",
    "process_reproducibility_sha256",
    "process_reproducibility",
    "evidence_boundary",
)


class ASRAdversarialVOiCESFrozenProcessReproducibilityError(ValueError):
    """Raised when the exact frozen B11H evidence cannot be trusted."""


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
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            "Frozen B11H evidence must be deterministic JSON."
        ) from error


def _sha256_payload(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
                f"Frozen B11H JSON contains duplicate key {key!r}."
            )
        result[key] = value
    return result


def _reject_non_finite(value: str) -> object:
    raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
        f"Frozen B11H JSON contains non-finite value {value}."
    )


def _parse_json(raw: bytes, *, name: str) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            f"{name} must be non-empty bytes."
        )
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except ASRAdversarialVOiCESFrozenProcessReproducibilityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            f"{name} is not valid UTF-8 JSON."
        ) from error
    if not isinstance(value, dict):
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            f"{name} JSON root must be an object."
        )
    return value


def _require_exact_keys(
    value: object,
    *,
    keys: tuple[str, ...],
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            f"{name} must contain exactly {list(keys)}."
        )
    return value


def _verify_file_identity(*, name: str, raw: bytes) -> str:
    if not isinstance(raw, bytes) or not raw:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            f"Frozen B11H {name} must be non-empty bytes."
        )
    try:
        identity = B11H_FROZEN_FILE_IDENTITIES[name]
    except KeyError as error:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            f"Frozen B11H file identity is not declared for {name}."
        ) from error
    if len(raw) != identity["bytes"]:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            f"Frozen B11H {name} byte length changed."
        )
    observed = hashlib.sha256(raw).hexdigest()
    if observed != identity["sha256"]:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            f"Frozen B11H {name} SHA-256 changed."
        )
    return observed


def _load_process_evidence(
    *,
    launch_file_bytes: tuple[bytes, ...],
    child_result_file_bytes: tuple[bytes, ...],
    process_run_file_bytes: tuple[bytes, ...],
) -> tuple[
    tuple[ASRAdversarialVOiCESProcessRunObservation, ...],
    tuple[dict[str, Any], ...],
]:
    for name, values in (
        ("launch files", launch_file_bytes),
        ("child-result files", child_result_file_bytes),
        ("process-run files", process_run_file_bytes),
    ):
        if not isinstance(values, tuple) or len(values) != 3:
            raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
                f"Frozen B11H requires exactly three {name}."
            )

    runs: list[ASRAdversarialVOiCESProcessRunObservation] = []
    run_payloads: list[dict[str, Any]] = []
    try:
        for index, (launch_raw, child_raw, run_raw) in enumerate(
            zip(
                launch_file_bytes,
                child_result_file_bytes,
                process_run_file_bytes,
                strict=True,
            ),
            start=1,
        ):
            launch_name = _LAUNCH_NAMES[index - 1]
            child_name = _CHILD_NAMES[index - 1]
            process_name = _PROCESS_NAMES[index - 1]
            _verify_file_identity(name=launch_name, raw=launch_raw)
            _verify_file_identity(name=child_name, raw=child_raw)
            _verify_file_identity(name=process_name, raw=run_raw)

            launch_payload = _parse_json(
                launch_raw,
                name=f"Frozen B11H {launch_name}",
            )
            child_payload = _parse_json(
                child_raw,
                name=f"Frozen B11H {child_name}",
            )
            process_payload = _parse_json(
                run_raw,
                name=f"Frozen B11H {process_name}",
            )
            launch = load_asr_adversarial_voices_process_launch_definition_v1(
                launch_raw
            )
            child = load_asr_adversarial_voices_child_process_result_v1(
                child_raw
            )
            process_run = (
                load_asr_adversarial_voices_process_run_observation_v1(
                    run_raw
                )
            )
            if (
                launch.payload != launch_payload
                or child.payload != child_payload
                or process_run.payload != process_payload
            ):
                raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
                    f"Frozen B11H run {index} canonical replay changed."
                )
            if (
                child.launch != launch
                or process_run.process_launch.launch != launch
                or process_run.process_launch.child_report
                != child.child_report
                or process_run.run_observation != child.run_observation
            ):
                raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
                    f"Frozen B11H run {index} cross-file links changed."
                )
            if (
                launch.run_id != _RUN_IDS[index - 1]
                or launch.launch_id != f"b11h-process-launch-{index:02d}"
            ):
                raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
                    f"Frozen B11H run {index} ordered identity changed."
                )
            runs.append(process_run)
            run_payloads.append(process_payload)
    except ASRAdversarialVOiCESFrozenProcessReproducibilityError:
        raise
    except ASRAdversarialVOiCESProcessReproducibilityError as error:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            "Frozen B11H launch, child, or process evidence failed replay."
        ) from error
    return tuple(runs), tuple(run_payloads)


def _expected_source_code() -> dict[str, object]:
    return {
        "branch": B11H_SOURCE_BRANCH,
        "git_head": B11H_SOURCE_GIT_HEAD,
        "source_manifest": _B11H_SOURCE_MANIFEST,
        "source_code_sha256": _B11H_SOURCE_CODE_SHA256,
    }


def _expected_outer_upstream(
    *,
    launch_file_bytes: tuple[bytes, ...],
    child_result_file_bytes: tuple[bytes, ...],
    process_run_file_bytes: tuple[bytes, ...],
) -> dict[str, object]:
    return {
        "matched_control_projection_sha256": (
            _MATCHED_CONTROL_PROJECTION_SHA256
        ),
        "matched_control_suite_sha256": _MATCHED_CONTROL_SUITE_SHA256,
        "adversarial_suite_evidence_sha256": (
            _ADVERSARIAL_SUITE_EVIDENCE_SHA256
        ),
        "ordered_launch_file_sha256s": [
            hashlib.sha256(value).hexdigest() for value in launch_file_bytes
        ],
        "ordered_child_result_file_sha256s": [
            hashlib.sha256(value).hexdigest()
            for value in child_result_file_bytes
        ],
        "ordered_process_run_file_sha256s": [
            hashlib.sha256(value).hexdigest()
            for value in process_run_file_bytes
        ],
    }


def _verify_outer_artifact(
    *,
    final_artifact_bytes: bytes,
    launch_file_bytes: tuple[bytes, ...],
    child_result_file_bytes: tuple[bytes, ...],
    process_run_file_bytes: tuple[bytes, ...],
    runs: tuple[ASRAdversarialVOiCESProcessRunObservation, ...],
) -> tuple[dict[str, Any], object]:
    _verify_file_identity(
        name=B11H_FINAL_ARTIFACT_NAME,
        raw=final_artifact_bytes,
    )
    root = _require_exact_keys(
        _parse_json(
            final_artifact_bytes,
            name="Frozen B11H final artifact",
        ),
        keys=_FINAL_ROOT_KEYS,
        name="Frozen B11H final root",
    )
    try:
        recomputed = (
            evaluate_asr_adversarial_voices_process_reproducibility_v1(
                runs=runs
            )
        )
    except ASRAdversarialVOiCESProcessReproducibilityError as error:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            "Frozen B11H process aggregate could not be recomputed."
        ) from error

    model_set = {
        "models": _B11H_MODELS,
        "device": "cpu",
        "compute_type": "int8_float32",
    }
    exact_checks = (
        root["schema_version"]
        == ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION,
        root["artifact"] == _B11H_FINAL_ARTIFACT,
        root["source_code"] == _expected_source_code(),
        root["models"] == _B11H_MODELS,
        root["runtime_environment"] == _B11H_RUNTIME_ENVIRONMENT,
        root["host_environment"] == _B11H_HOST_ENVIRONMENT,
        root["execution_protocol"] == _B11H_EXECUTION_PROTOCOL,
        root["controller_invocation"] == _B11H_CONTROLLER_INVOCATION,
        root["evidence_boundary"] == _B11H_OUTER_BOUNDARY,
        root["upstream"]
        == _expected_outer_upstream(
            launch_file_bytes=launch_file_bytes,
            child_result_file_bytes=child_result_file_bytes,
            process_run_file_bytes=process_run_file_bytes,
        ),
        root["runtime_environment_sha256"]
        == _B11H_RUNTIME_ENVIRONMENT_SHA256,
        root["host_environment_sha256"]
        == _B11H_HOST_ENVIRONMENT_SHA256,
        root["model_set_sha256"] == _B11H_MODEL_SET_SHA256,
        root["python_executable_sha256"]
        == _B11H_PYTHON_EXECUTABLE_SHA256,
        root["controller_invocation_sha256"]
        == _B11H_CONTROLLER_INVOCATION_SHA256,
        root["process_reproducibility_sha256"]
        == B11H_PROCESS_REPRODUCIBILITY_SHA256,
        _sha256_payload(_B11H_SOURCE_MANIFEST)
        == _B11H_SOURCE_CODE_SHA256,
        _sha256_payload(_B11H_RUNTIME_ENVIRONMENT)
        == _B11H_RUNTIME_ENVIRONMENT_SHA256,
        _sha256_payload(_B11H_HOST_ENVIRONMENT)
        == _B11H_HOST_ENVIRONMENT_SHA256,
        _sha256_payload(model_set) == _B11H_MODEL_SET_SHA256,
        _sha256_payload(_B11H_CONTROLLER_INVOCATION)
        == _B11H_CONTROLLER_INVOCATION_SHA256,
        root["process_reproducibility"] == recomputed.payload,
        _sha256_payload(root["process_reproducibility"])
        == B11H_PROCESS_REPRODUCIBILITY_SHA256,
        recomputed.sha256 == B11H_PROCESS_REPRODUCIBILITY_SHA256,
    )
    if not all(exact_checks):
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            "Frozen B11H final identity, commitments, aggregate, or boundary "
            "changed."
        )
    return root, recomputed


@dataclass(frozen=True, slots=True)
class _VerifiedFrozenProcessEvidence:
    final_artifact: dict[str, Any]
    process_bundle: ASRAdversarialVOiCESProcessReproducibilityBundle


def _verify_frozen_evidence(
    *,
    launch_file_bytes: tuple[bytes, ...],
    child_result_file_bytes: tuple[bytes, ...],
    process_run_file_bytes: tuple[bytes, ...],
    final_artifact_bytes: bytes,
) -> _VerifiedFrozenProcessEvidence:
    runs, _ = _load_process_evidence(
        launch_file_bytes=launch_file_bytes,
        child_result_file_bytes=child_result_file_bytes,
        process_run_file_bytes=process_run_file_bytes,
    )
    final, process_bundle = _verify_outer_artifact(
        final_artifact_bytes=final_artifact_bytes,
        launch_file_bytes=launch_file_bytes,
        child_result_file_bytes=child_result_file_bytes,
        process_run_file_bytes=process_run_file_bytes,
        runs=runs,
    )
    return _VerifiedFrozenProcessEvidence(
        final_artifact=final,
        process_bundle=process_bundle,
    )


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESFrozenProcessReproducibilityBundle:
    """Deterministic verification over the exact ten retained B11H files."""

    launch_file_bytes: tuple[bytes, ...] = field(repr=False)
    child_result_file_bytes: tuple[bytes, ...] = field(repr=False)
    process_run_file_bytes: tuple[bytes, ...] = field(repr=False)
    final_artifact_bytes: bytes = field(repr=False)
    _verified: _VerifiedFrozenProcessEvidence = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_verified",
            _verify_frozen_evidence(
                launch_file_bytes=self.launch_file_bytes,
                child_result_file_bytes=self.child_result_file_bytes,
                process_run_file_bytes=self.process_run_file_bytes,
                final_artifact_bytes=self.final_artifact_bytes,
            ),
        )

    @property
    def status(self) -> str:
        return self._verified.process_bundle.status

    @property
    def process_reproducibility_sha256(self) -> str:
        return self._verified.process_bundle.sha256

    @property
    def payload(self) -> dict[str, object]:
        process = self._verified.process_bundle
        aggregate = process.reproduction
        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION
            ),
            "artifact": {
                "key": (
                    ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_KEY
                ),
                "version": (
                    ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_VERSION
                ),
                "type": (
                    "frozen-content-free-same-host-process-evidence-verification"
                ),
            },
            "upstream": {
                "b11h_final_artifact": {
                    "artifact_key": _B11H_FINAL_ARTIFACT["key"],
                    "artifact_version": _B11H_FINAL_ARTIFACT["version"],
                    "bytes": len(self.final_artifact_bytes),
                    "sha256": hashlib.sha256(
                        self.final_artifact_bytes
                    ).hexdigest(),
                },
                "source_code": _expected_source_code(),
                "frozen_file_identities": [
                    {
                        "name": name,
                        "bytes": B11H_FROZEN_FILE_IDENTITIES[name]["bytes"],
                        "sha256": B11H_FROZEN_FILE_IDENTITIES[name]["sha256"],
                    }
                    for name in (
                        *_LAUNCH_NAMES,
                        *_CHILD_NAMES,
                        *_PROCESS_NAMES,
                        B11H_FINAL_ARTIFACT_NAME,
                    )
                ],
                "process_reproducibility_sha256": (
                    self.process_reproducibility_sha256
                ),
            },
            "verification": {
                "exact_ten_file_byte_identities_verified": True,
                "duplicate_json_keys_rejected": True,
                "non_finite_json_numbers_rejected": True,
                "three_launch_precommitments_replayed": True,
                "three_child_results_replayed": True,
                "three_parent_finalized_process_runs_replayed": True,
                "launch_child_and_process_links_verified": True,
                "parent_child_pid_and_timeline_links_verified": True,
                "fixed_source_runtime_host_model_links_verified": True,
                "fixed_cohort_links_verified": True,
                "source_manifest_identity_recomputed": True,
                "runtime_host_model_and_controller_identities_recomputed": True,
                "process_reproducibility_aggregate_recomputed": True,
                "process_reproducibility_identity_recomputed": True,
                "outer_evidence_boundary_verified": True,
            },
            "result": {
                "status": process.status,
                "population": process.payload["population"],
                "process_isolated_reproduction_index": aggregate[
                    "process_isolated_reproduction_index"
                ],
                "overall": aggregate["overall"],
                "process_integrity": aggregate["process_integrity"],
                "comparison_signal_reproduction": aggregate[
                    "comparison_signal_reproduction"
                ],
            },
            "evidence_boundary": {
                "development_evidence_only": True,
                "content_free_json_evidence_only": True,
                "audio_reexecuted_by_frozen_verifier": False,
                "models_loaded_by_frozen_verifier": False,
                "transcriptions_executed_by_frozen_verifier": False,
                "exact_b11h_file_set_reverified": True,
                "independent_operating_system_processes_verified": True,
                "same_host_process_isolated_reproducibility_evaluated": True,
                "same_host_process_reproducibility_verified": (
                    process.status == "reproduced"
                ),
                "cross_host_reproducibility_evaluated": False,
                "cross_host_reproducibility_verified": None,
                "reproducibility_verified": None,
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
        return _sha256_payload(self.payload)

    def require_same_host_process_reproducibility_verified(self) -> None:
        if self.status != "reproduced":
            raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
                "Frozen B11H same-host process evidence contains variation."
            )

    def require_cross_host_reproducibility_verified(self) -> None:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            "Frozen same-host process evidence cannot establish cross-host "
            "reproducibility."
        )

    def require_qualification(self) -> None:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            "Frozen B11H is descriptive development evidence; no "
            "qualification threshold was applied."
        )

    def require_release_enforcement(self) -> None:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            "Frozen B11H evidence does not authorize release enforcement."
        )


def evaluate_asr_adversarial_voices_frozen_process_reproducibility_v1(
    *,
    launch_file_bytes: tuple[bytes, ...],
    child_result_file_bytes: tuple[bytes, ...],
    process_run_file_bytes: tuple[bytes, ...],
    final_artifact_bytes: bytes,
) -> ASRAdversarialVOiCESFrozenProcessReproducibilityBundle:
    """Verify and recompute the exact ten-file frozen B11H evidence set."""

    return ASRAdversarialVOiCESFrozenProcessReproducibilityBundle(
        launch_file_bytes=launch_file_bytes,
        child_result_file_bytes=child_result_file_bytes,
        process_run_file_bytes=process_run_file_bytes,
        final_artifact_bytes=final_artifact_bytes,
    )


def evaluate_asr_adversarial_voices_frozen_process_reproducibility_directory_v1(
    *,
    evidence_root: str | PathLike[str],
) -> ASRAdversarialVOiCESFrozenProcessReproducibilityBundle:
    """Read one exact B11H directory without embedding its local path."""

    try:
        root = Path(evidence_root)
        if not root.is_dir():
            raise OSError("B11H evidence root is not a directory")
        observed_names = {
            value.name for value in root.iterdir() if value.is_file()
        }
        expected_names = set(B11H_FROZEN_FILE_IDENTITIES)
        if observed_names != expected_names:
            raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
                "Frozen B11H directory file population changed."
            )
        launches = tuple((root / name).read_bytes() for name in _LAUNCH_NAMES)
        children = tuple((root / name).read_bytes() for name in _CHILD_NAMES)
        runs = tuple((root / name).read_bytes() for name in _PROCESS_NAMES)
        final = (root / B11H_FINAL_ARTIFACT_NAME).read_bytes()
    except ASRAdversarialVOiCESFrozenProcessReproducibilityError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise ASRAdversarialVOiCESFrozenProcessReproducibilityError(
            "Frozen B11H evidence directory could not be read."
        ) from error
    return evaluate_asr_adversarial_voices_frozen_process_reproducibility_v1(
        launch_file_bytes=launches,
        child_result_file_bytes=children,
        process_run_file_bytes=runs,
        final_artifact_bytes=final,
    )
