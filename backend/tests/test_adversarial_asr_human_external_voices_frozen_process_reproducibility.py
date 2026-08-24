from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json

import pytest

from app import (
    adversarial_asr_human_external_voices_frozen_process_reproducibility
    as frozen,
)
from app.adversarial_asr_human_external_voices_frozen_process_reproducibility import (
    ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_KEY,
    ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_VERSION,
    ASRAdversarialVOiCESFrozenProcessReproducibilityBundle,
    ASRAdversarialVOiCESFrozenProcessReproducibilityError,
    B11H_FINAL_ARTIFACT_NAME,
    evaluate_asr_adversarial_voices_frozen_process_reproducibility_directory_v1,
    evaluate_asr_adversarial_voices_frozen_process_reproducibility_v1,
)
from app.adversarial_asr_human_external_voices_process_reproducibility import (
    ASRAdversarialVOiCESChildProcessReport,
    ASRAdversarialVOiCESChildProcessResult,
    ASRAdversarialVOiCESProcessLaunchDefinition,
    ASRAdversarialVOiCESProcessLaunchObservation,
    ASRAdversarialVOiCESProcessRunObservation,
    evaluate_asr_adversarial_voices_process_reproducibility_v1,
)
from app.adversarial_asr_human_external_voices_repeatability import (
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT,
    ASRAdversarialVOiCESRepeatabilityCaseObservation,
    ASRAdversarialVOiCESRepeatabilityPairKey,
    ASRAdversarialVOiCESRepeatabilityRunObservation,
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _encode(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _pair_key(index: int) -> ASRAdversarialVOiCESRepeatabilityPairKey:
    pair = (index // 2) + 1
    return ASRAdversarialVOiCESRepeatabilityPairKey(
        source_key=(pair, pair + 100, pair + 200),
        room="rm1",
        microphone_id=1,
        angle_degrees=10,
    )


def _case(
    *,
    run: int,
    role: str,
    index: int,
) -> ASRAdversarialVOiCESRepeatabilityCaseObservation:
    run_id = frozen._RUN_IDS[run - 1]
    return ASRAdversarialVOiCESRepeatabilityCaseObservation(
        run_id=run_id,
        role=role,
        provider_key="faster_whisper",
        model_key=("small.en" if role == "baseline" else "large-v3-turbo"),
        pair_key=_pair_key(index),
        arm="babble" if index % 2 == 0 else "control",
        case_id=f"voices-case-{index:02d}",
        audio_asset_sha256=_sha256_text(f"audio-{index}"),
        reference_transcript_sha256=_sha256_text(f"reference-{index}"),
        normalized_reference_sha256=_sha256_text(
            f"normalized-reference-{index}"
        ),
        execution_environment_sha256=_sha256_text(
            f"environment-{role}-{index}"
        ),
        execution_evidence_sha256=_sha256_text(
            f"execution-{run}-{role}-{index}"
        ),
        generated_transcript_sha256=_sha256_text(
            f"generated-{role}-{index}"
        ),
        normalized_generated_sha256=_sha256_text(
            f"normalized-generated-{role}-{index}"
        ),
        wer=(0.10 if role == "baseline" else 0.05) + index / 1000,
        cer=(0.08 if role == "baseline" else 0.03) + index / 2000,
    )


def _run(run: int) -> ASRAdversarialVOiCESRepeatabilityRunObservation:
    cases = tuple(
        _case(run=run, role=role, index=index)
        for role in ("baseline", "candidate")
        for index in range(ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT)
    )
    return ASRAdversarialVOiCESRepeatabilityRunObservation(
        run_id=frozen._RUN_IDS[run - 1],
        execution_sha256=_sha256_text(f"b9-execution-{run}"),
        matched_control_suite_sha256=frozen._MATCHED_CONTROL_SUITE_SHA256,
        adversarial_suite_evidence_sha256=(
            frozen._ADVERSARIAL_SUITE_EVIDENCE_SHA256
        ),
        baseline_campaign_id=f"baseline-process-{run}",
        baseline_campaign_version="1.0.0",
        baseline_campaign_sha256=_sha256_text(
            f"baseline-campaign-{run}"
        ),
        baseline_metrics_sha256=_sha256_text(f"baseline-metrics-{run}"),
        baseline_provider_key="faster_whisper",
        baseline_model_key="small.en",
        candidate_campaign_id=f"candidate-process-{run}",
        candidate_campaign_version="1.0.0",
        candidate_campaign_sha256=_sha256_text(
            f"candidate-campaign-{run}"
        ),
        candidate_metrics_sha256=_sha256_text(f"candidate-metrics-{run}"),
        candidate_provider_key="faster_whisper",
        candidate_model_key="large-v3-turbo",
        cases=cases,
        general_accuracy_wer_differential=-0.05,
        general_accuracy_cer_differential=-0.05,
        robustness_wer_differential=0.02,
        robustness_cer_differential=0.01,
    )


def _process_run(run: int) -> ASRAdversarialVOiCESProcessRunObservation:
    run_observation = _run(run)
    launch = ASRAdversarialVOiCESProcessLaunchDefinition(
        run_id=frozen._RUN_IDS[run - 1],
        launch_id=f"b11h-process-launch-{run:02d}",
        launch_challenge_sha256=_sha256_text(f"challenge-{run}"),
        controller_invocation_sha256=(
            frozen._B11H_CONTROLLER_INVOCATION_SHA256
        ),
        controller_process_id=500,
        source_code_sha256=frozen._B11H_SOURCE_CODE_SHA256,
        python_executable_sha256=frozen._B11H_PYTHON_EXECUTABLE_SHA256,
        runtime_environment_sha256=(
            frozen._B11H_RUNTIME_ENVIRONMENT_SHA256
        ),
        host_environment_sha256=frozen._B11H_HOST_ENVIRONMENT_SHA256,
        model_set_sha256=frozen._B11H_MODEL_SET_SHA256,
        matched_control_suite_sha256=frozen._MATCHED_CONTROL_SUITE_SHA256,
        adversarial_suite_evidence_sha256=(
            frozen._ADVERSARIAL_SUITE_EVIDENCE_SHA256
        ),
    )
    start = 1_000_000_000 + run * 10_000
    report = ASRAdversarialVOiCESChildProcessReport(
        run_id=launch.run_id,
        launch_definition_sha256=launch.sha256,
        launch_challenge_sha256=launch.launch_challenge_sha256,
        controller_invocation_sha256=launch.controller_invocation_sha256,
        process_id=1_000 + run,
        parent_process_id=launch.controller_process_id,
        started_at_unix_ns=start,
        completed_at_unix_ns=start + 100,
        source_code_sha256=launch.source_code_sha256,
        python_executable_sha256=launch.python_executable_sha256,
        runtime_environment_sha256=launch.runtime_environment_sha256,
        host_environment_sha256=launch.host_environment_sha256,
        model_set_sha256=launch.model_set_sha256,
        run_observation_sha256=run_observation.sha256,
    )
    return ASRAdversarialVOiCESProcessRunObservation(
        process_launch=ASRAdversarialVOiCESProcessLaunchObservation(
            launch=launch,
            child_report=report,
            parent_spawn_started_at_unix_ns=start - 100,
            parent_observed_child_process_id=report.process_id,
            parent_observed_exit_code=0,
            parent_observed_completed_at_unix_ns=start + 200,
        ),
        run_observation=run_observation,
    )


def _file_identity(raw: bytes) -> dict[str, object]:
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _synthetic_files(monkeypatch) -> dict[str, bytes]:
    runs = tuple(_process_run(value) for value in range(1, 4))
    process_bundle = evaluate_asr_adversarial_voices_process_reproducibility_v1(
        runs=runs
    )
    launches = tuple(_encode(value.process_launch.launch.payload) for value in runs)
    children = tuple(
        _encode(
            ASRAdversarialVOiCESChildProcessResult(
                launch=value.process_launch.launch,
                child_report=value.process_launch.child_report,
                run_observation=value.run_observation,
            ).payload
        )
        for value in runs
    )
    process_files = tuple(_encode(value.payload) for value in runs)
    outer = {
        "schema_version": 1,
        "artifact": deepcopy(frozen._B11H_FINAL_ARTIFACT),
        "source_code": deepcopy(frozen._expected_source_code()),
        "models": deepcopy(frozen._B11H_MODELS),
        "runtime_environment": deepcopy(frozen._B11H_RUNTIME_ENVIRONMENT),
        "runtime_environment_sha256": (
            frozen._B11H_RUNTIME_ENVIRONMENT_SHA256
        ),
        "host_environment": deepcopy(frozen._B11H_HOST_ENVIRONMENT),
        "host_environment_sha256": frozen._B11H_HOST_ENVIRONMENT_SHA256,
        "model_set_sha256": frozen._B11H_MODEL_SET_SHA256,
        "python_executable_sha256": frozen._B11H_PYTHON_EXECUTABLE_SHA256,
        "controller_invocation": deepcopy(frozen._B11H_CONTROLLER_INVOCATION),
        "controller_invocation_sha256": (
            frozen._B11H_CONTROLLER_INVOCATION_SHA256
        ),
        "execution_protocol": deepcopy(frozen._B11H_EXECUTION_PROTOCOL),
        "upstream": frozen._expected_outer_upstream(
            launch_file_bytes=launches,
            child_result_file_bytes=children,
            process_run_file_bytes=process_files,
        ),
        "process_reproducibility_sha256": process_bundle.sha256,
        "process_reproducibility": process_bundle.payload,
        "evidence_boundary": deepcopy(frozen._B11H_OUTER_BOUNDARY),
    }
    files = {
        **dict(zip(frozen._LAUNCH_NAMES, launches, strict=True)),
        **dict(zip(frozen._CHILD_NAMES, children, strict=True)),
        **dict(zip(frozen._PROCESS_NAMES, process_files, strict=True)),
        B11H_FINAL_ARTIFACT_NAME: _encode(outer),
    }
    monkeypatch.setattr(
        frozen,
        "B11H_FROZEN_FILE_IDENTITIES",
        {name: _file_identity(raw) for name, raw in files.items()},
    )
    monkeypatch.setattr(
        frozen,
        "B11H_PROCESS_REPRODUCIBILITY_SHA256",
        process_bundle.sha256,
    )
    return files


def _evaluate(files: dict[str, bytes]):
    return evaluate_asr_adversarial_voices_frozen_process_reproducibility_v1(
        launch_file_bytes=tuple(files[name] for name in frozen._LAUNCH_NAMES),
        child_result_file_bytes=tuple(
            files[name] for name in frozen._CHILD_NAMES
        ),
        process_run_file_bytes=tuple(
            files[name] for name in frozen._PROCESS_NAMES
        ),
        final_artifact_bytes=files[B11H_FINAL_ARTIFACT_NAME],
    )


def _repin(monkeypatch, files: dict[str, bytes], name: str, raw: bytes) -> None:
    files[name] = raw
    identities = deepcopy(frozen.B11H_FROZEN_FILE_IDENTITIES)
    identities[name] = _file_identity(raw)
    monkeypatch.setattr(frozen, "B11H_FROZEN_FILE_IDENTITIES", identities)


def test_constants_pin_the_real_b11h_artifact():
    assert ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_FROZEN_PROCESS_REPRODUCIBILITY_KEY.endswith(
        "frozen-same-host-process-isolated-reproducibility"
    )
    assert frozen.B11H_FINAL_ARTIFACT_BYTES == 339_377
    assert frozen.B11H_FINAL_ARTIFACT_SHA256 == (
        "21a19684920a2b27a25ae2fde0d57b0b"
        "d06c96cd7da95588eff5b936d7a955d2"
    )
    assert len(frozen.B11H_FROZEN_FILE_IDENTITIES) == 10


def test_valid_frozen_set_recomputes_the_complete_result(monkeypatch):
    bundle = _evaluate(_synthetic_files(monkeypatch))
    result = bundle.payload["result"]

    assert bundle.status == "reproduced"
    assert result["population"]["execution_count"] == 192
    assert result["process_isolated_reproduction_index"][
        "score_percent"
    ] == 100.0
    assert result["process_isolated_reproduction_index"][
        "hard_conditions_all_passed"
    ] is True
    assert all(bundle.payload["verification"].values())


def test_bundle_is_deterministic_content_free_and_frozen(monkeypatch):
    files = _synthetic_files(monkeypatch)
    first = _evaluate(files)
    second = _evaluate(files)
    encoded = frozen._canonical_json_bytes(first.payload)

    assert first.payload == second.payload
    assert first.sha256 == second.sha256
    assert b"/Users/" not in encoded
    assert b".wav" not in encoded
    assert b"generated transcript text" not in encoded
    with pytest.raises((FrozenInstanceError, AttributeError)):
        first.final_artifact_bytes = b"changed"


def test_boundary_and_authority_methods_are_exact(monkeypatch):
    bundle = _evaluate(_synthetic_files(monkeypatch))
    boundary = bundle.payload["evidence_boundary"]

    assert boundary["models_loaded_by_frozen_verifier"] is False
    assert boundary["transcriptions_executed_by_frozen_verifier"] is False
    assert boundary["same_host_process_reproducibility_verified"] is True
    assert boundary["cross_host_reproducibility_verified"] is None
    assert boundary["reproducibility_verified"] is None
    assert boundary["qualification_threshold_applied"] is False
    bundle.require_same_host_process_reproducibility_verified()
    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="cross-host",
    ):
        bundle.require_cross_host_reproducibility_verified()
    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="qualification threshold",
    ):
        bundle.require_qualification()
    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="release enforcement",
    ):
        bundle.require_release_enforcement()


@pytest.mark.parametrize(
    "name",
    (
        "launch-01.json",
        "child-result-01.json",
        "process-run-01.json",
        B11H_FINAL_ARTIFACT_NAME,
    ),
)
def test_any_raw_file_tampering_fails_closed(monkeypatch, name):
    files = _synthetic_files(monkeypatch)
    files[name] += b" "

    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="byte length changed",
    ):
        _evaluate(files)


def test_reordered_child_file_is_rejected_even_when_repinned(monkeypatch):
    files = _synthetic_files(monkeypatch)
    changed = files["child-result-02.json"]
    _repin(monkeypatch, files, "child-result-01.json", changed)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="cross-file links changed",
    ):
        _evaluate(files)


def test_launch_order_tampering_is_rejected_when_repinned(monkeypatch):
    files = _synthetic_files(monkeypatch)
    payload = json.loads(files["launch-01.json"])
    payload["run_id"] = "different-run"
    changed = _encode(payload)
    _repin(monkeypatch, files, "launch-01.json", changed)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="ordered identity changed|failed replay|cross-file links changed",
    ):
        _evaluate(files)


def test_child_parent_pid_tampering_is_rejected_when_repinned(monkeypatch):
    files = _synthetic_files(monkeypatch)
    payload = json.loads(files["child-result-01.json"])
    payload["child_report"]["process"]["parent_process_id"] = 999
    report = payload["child_report"]
    process = report["process"]
    process["process_instance_sha256"] = frozen._sha256_payload(
        {
            "process_id": process["process_id"],
            "parent_process_id": process["parent_process_id"],
            "started_at_unix_ns": process["started_at_unix_ns"],
        }
    )
    payload["child_report_sha256"] = frozen._sha256_payload(report)
    changed = _encode(payload)
    _repin(monkeypatch, files, "child-result-01.json", changed)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="failed replay",
    ):
        _evaluate(files)


def test_parent_observed_pid_tampering_is_rejected_when_repinned(monkeypatch):
    files = _synthetic_files(monkeypatch)
    payload = json.loads(files["process-run-01.json"])
    payload["process_launch"]["parent_observation"][
        "observed_child_process_id"
    ] = 999
    changed = _encode(payload)
    _repin(monkeypatch, files, "process-run-01.json", changed)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="failed replay",
    ):
        _evaluate(files)


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("evidence_boundary", "production_qualified"), True),
        (("source_code", "git_head"), "changed"),
        (("execution_protocol", "cross_host_execution"), True),
        (("process_reproducibility", "status"), "variation_observed"),
    ),
)
def test_final_semantic_tampering_is_rejected_when_repinned(
    monkeypatch,
    path,
    value,
):
    files = _synthetic_files(monkeypatch)
    payload = json.loads(files[B11H_FINAL_ARTIFACT_NAME])
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    changed = _encode(payload)
    _repin(monkeypatch, files, B11H_FINAL_ARTIFACT_NAME, changed)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="final identity",
    ):
        _evaluate(files)


def test_final_duplicate_keys_and_non_finite_values_are_rejected(monkeypatch):
    files = _synthetic_files(monkeypatch)
    duplicate = b'{"schema_version":1,"schema_version":1}'
    _repin(monkeypatch, files, B11H_FINAL_ARTIFACT_NAME, duplicate)
    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="duplicate key",
    ):
        _evaluate(files)

    files = _synthetic_files(monkeypatch)
    non_finite = b'{"schema_version":NaN}'
    _repin(monkeypatch, files, B11H_FINAL_ARTIFACT_NAME, non_finite)
    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="non-finite",
    ):
        _evaluate(files)


def test_directory_api_replays_without_embedding_path(monkeypatch, tmp_path):
    files = _synthetic_files(monkeypatch)
    for name, raw in files.items():
        (tmp_path / name).write_bytes(raw)

    bundle = (
        evaluate_asr_adversarial_voices_frozen_process_reproducibility_directory_v1(
            evidence_root=tmp_path
        )
    )
    encoded = frozen._canonical_json_bytes(bundle.payload)

    assert bundle.status == "reproduced"
    assert str(tmp_path).encode("utf-8") not in encoded


def test_directory_api_rejects_missing_extra_or_non_directory(
    monkeypatch,
    tmp_path,
):
    files = _synthetic_files(monkeypatch)
    for name, raw in files.items():
        (tmp_path / name).write_bytes(raw)
    (tmp_path / "unexpected.json").write_bytes(b"{}")

    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="population changed",
    ):
        evaluate_asr_adversarial_voices_frozen_process_reproducibility_directory_v1(
            evidence_root=tmp_path
        )

    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="could not be read",
    ):
        evaluate_asr_adversarial_voices_frozen_process_reproducibility_directory_v1(
            evidence_root=tmp_path / "missing"
        )


def test_exactly_three_ordered_files_are_required(monkeypatch):
    files = _synthetic_files(monkeypatch)
    with pytest.raises(
        ASRAdversarialVOiCESFrozenProcessReproducibilityError,
        match="exactly three launch files",
    ):
        evaluate_asr_adversarial_voices_frozen_process_reproducibility_v1(
            launch_file_bytes=(files["launch-01.json"],),
            child_result_file_bytes=tuple(
                files[name] for name in frozen._CHILD_NAMES
            ),
            process_run_file_bytes=tuple(
                files[name] for name in frozen._PROCESS_NAMES
            ),
            final_artifact_bytes=files[B11H_FINAL_ARTIFACT_NAME],
        )


def test_bundle_type_and_result_identity_are_exposed(monkeypatch):
    bundle = _evaluate(_synthetic_files(monkeypatch))

    assert isinstance(
        bundle,
        ASRAdversarialVOiCESFrozenProcessReproducibilityBundle,
    )
    assert (
        bundle.process_reproducibility_sha256
        == frozen.B11H_PROCESS_REPRODUCIBILITY_SHA256
    )
    assert len(bundle.sha256) == 64
