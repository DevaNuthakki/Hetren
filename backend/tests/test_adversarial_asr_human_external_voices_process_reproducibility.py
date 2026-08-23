from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

import app.adversarial_asr_human_external_voices_process_reproducibility as process
from app.adversarial_asr_human_external_voices_process_reproducibility import (
    ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_AXIS_WEIGHT,
    ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_KEY,
    ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT,
    ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_VERSION,
    ASRAdversarialVOiCESChildProcessReport,
    ASRAdversarialVOiCESChildProcessResult,
    ASRAdversarialVOiCESProcessLaunchDefinition,
    ASRAdversarialVOiCESProcessLaunchObservation,
    ASRAdversarialVOiCESProcessReproducibilityError,
    ASRAdversarialVOiCESProcessRunObservation,
    calculate_python_executable_sha256_v1,
    capture_asr_adversarial_voices_child_process_report_v1,
    evaluate_asr_adversarial_voices_process_reproducibility_v1,
    finalize_asr_adversarial_voices_child_process_result_v1,
    load_asr_adversarial_voices_child_process_result_v1,
    load_asr_adversarial_voices_process_launch_definition_v1,
    load_asr_adversarial_voices_process_run_file_v1,
    load_asr_adversarial_voices_process_run_observation_v1,
)
from app.adversarial_asr_human_external_voices_repeatability import (
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT,
    ASRAdversarialVOiCESRepeatabilityCaseObservation,
    ASRAdversarialVOiCESRepeatabilityPairKey,
    ASRAdversarialVOiCESRepeatabilityRunObservation,
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    raw_suffix: str = "stable",
    normalized_suffix: str = "stable",
    environment_suffix: str = "stable",
    wer_offset: float = 0.0,
    cer_offset: float = 0.0,
) -> ASRAdversarialVOiCESRepeatabilityCaseObservation:
    return ASRAdversarialVOiCESRepeatabilityCaseObservation(
        run_id=f"process-run-{run}",
        role=role,
        provider_key="faster_whisper",
        model_key=("small.en" if role == "baseline" else "large-v3-turbo"),
        pair_key=_pair_key(index),
        arm="babble" if index % 2 == 0 else "control",
        case_id=f"voices-case-{index:02d}",
        audio_asset_sha256=_sha256(f"audio-{index}"),
        reference_transcript_sha256=_sha256(f"reference-{index}"),
        normalized_reference_sha256=_sha256(
            f"normalized-reference-{index}"
        ),
        execution_environment_sha256=_sha256(
            f"environment-{role}-{index}-{environment_suffix}"
        ),
        execution_evidence_sha256=_sha256(
            f"execution-{run}-{role}-{index}"
        ),
        generated_transcript_sha256=_sha256(
            f"generated-{role}-{index}-{raw_suffix}"
        ),
        normalized_generated_sha256=_sha256(
            f"normalized-generated-{role}-{index}-{normalized_suffix}"
        ),
        wer=(0.10 if role == "baseline" else 0.05)
        + index / 1000
        + wer_offset,
        cer=(0.08 if role == "baseline" else 0.03)
        + index / 2000
        + cer_offset,
    )


def _run(
    run: int,
    *,
    changed_raw: tuple[str, int] | None = None,
    changed_normalized: tuple[str, int] | None = None,
    changed_environment: tuple[str, int] | None = None,
    changed_metric: tuple[str, int] | None = None,
    general_wer: float = -0.05,
    general_cer: float = -0.05,
    robustness_wer: float = 0.02,
    robustness_cer: float = 0.01,
    matched_suite: str | None = None,
) -> ASRAdversarialVOiCESRepeatabilityRunObservation:
    cases = []
    for role in ("baseline", "candidate"):
        for index in range(ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT):
            identity = (role, index)
            cases.append(
                _case(
                    run=run,
                    role=role,
                    index=index,
                    raw_suffix=(
                        f"changed-{run}"
                        if identity == changed_raw
                        else "stable"
                    ),
                    normalized_suffix=(
                        f"changed-{run}"
                        if identity == changed_normalized
                        else "stable"
                    ),
                    environment_suffix=(
                        f"changed-{run}"
                        if identity == changed_environment
                        else "stable"
                    ),
                    wer_offset=0.01 if identity == changed_metric else 0.0,
                    cer_offset=0.005 if identity == changed_metric else 0.0,
                )
            )
    return ASRAdversarialVOiCESRepeatabilityRunObservation(
        run_id=f"process-run-{run}",
        execution_sha256=_sha256(f"b9-execution-{run}"),
        matched_control_suite_sha256=(
            _sha256("matched-control-suite")
            if matched_suite is None
            else matched_suite
        ),
        adversarial_suite_evidence_sha256=_sha256("adversarial-suite"),
        baseline_campaign_id=f"baseline-process-{run}",
        baseline_campaign_version="1.0.0",
        baseline_campaign_sha256=_sha256(f"baseline-campaign-{run}"),
        baseline_metrics_sha256=_sha256(f"baseline-metrics-{run}"),
        baseline_provider_key="faster_whisper",
        baseline_model_key="small.en",
        candidate_campaign_id=f"candidate-process-{run}",
        candidate_campaign_version="1.0.0",
        candidate_campaign_sha256=_sha256(f"candidate-campaign-{run}"),
        candidate_metrics_sha256=_sha256(f"candidate-metrics-{run}"),
        candidate_provider_key="faster_whisper",
        candidate_model_key="large-v3-turbo",
        cases=tuple(cases),
        general_accuracy_wer_differential=general_wer,
        general_accuracy_cer_differential=general_cer,
        robustness_wer_differential=robustness_wer,
        robustness_cer_differential=robustness_cer,
    )


def _launch(
    run: int,
    *,
    controller_process_id: int = 500,
    challenge: str | None = None,
    runtime: str | None = None,
    matched_suite: str | None = None,
) -> ASRAdversarialVOiCESProcessLaunchDefinition:
    return ASRAdversarialVOiCESProcessLaunchDefinition(
        run_id=f"process-run-{run}",
        launch_id=f"process-launch-{run}",
        launch_challenge_sha256=_sha256(
            f"challenge-{run}" if challenge is None else challenge
        ),
        controller_invocation_sha256=_sha256("controller-invocation"),
        controller_process_id=controller_process_id,
        source_code_sha256=_sha256("source-code"),
        python_executable_sha256=_sha256("python-executable"),
        runtime_environment_sha256=(
            _sha256("runtime-environment") if runtime is None else runtime
        ),
        host_environment_sha256=_sha256("host-environment"),
        model_set_sha256=_sha256("model-set"),
        matched_control_suite_sha256=(
            _sha256("matched-control-suite")
            if matched_suite is None
            else matched_suite
        ),
        adversarial_suite_evidence_sha256=_sha256("adversarial-suite"),
    )


def _process_run(
    run: int,
    *,
    run_observation: ASRAdversarialVOiCESRepeatabilityRunObservation | None = None,
    launch: ASRAdversarialVOiCESProcessLaunchDefinition | None = None,
    process_id: int | None = None,
    started_at: int | None = None,
) -> ASRAdversarialVOiCESProcessRunObservation:
    selected_run = _run(run) if run_observation is None else run_observation
    selected_launch = _launch(run) if launch is None else launch
    pid = 1000 + run if process_id is None else process_id
    start = 1_000_000_000 + run * 10_000 if started_at is None else started_at
    report = ASRAdversarialVOiCESChildProcessReport(
        run_id=selected_launch.run_id,
        launch_definition_sha256=selected_launch.sha256,
        launch_challenge_sha256=selected_launch.launch_challenge_sha256,
        controller_invocation_sha256=(
            selected_launch.controller_invocation_sha256
        ),
        process_id=pid,
        parent_process_id=selected_launch.controller_process_id,
        started_at_unix_ns=start,
        completed_at_unix_ns=start + 100,
        source_code_sha256=selected_launch.source_code_sha256,
        python_executable_sha256=selected_launch.python_executable_sha256,
        runtime_environment_sha256=(
            selected_launch.runtime_environment_sha256
        ),
        host_environment_sha256=selected_launch.host_environment_sha256,
        model_set_sha256=selected_launch.model_set_sha256,
        run_observation_sha256=selected_run.sha256,
    )
    return ASRAdversarialVOiCESProcessRunObservation(
        process_launch=ASRAdversarialVOiCESProcessLaunchObservation(
            launch=selected_launch,
            child_report=report,
            parent_spawn_started_at_unix_ns=start - 100,
            parent_observed_child_process_id=pid,
            parent_observed_exit_code=0,
            parent_observed_completed_at_unix_ns=start + 200,
        ),
        run_observation=selected_run,
    )


def _stable_bundle():
    return evaluate_asr_adversarial_voices_process_reproducibility_v1(
        runs=tuple(_process_run(value) for value in range(1, 4))
    )


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


def test_constants_are_exact():
    assert ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_KEY == (
        "hetren.asr.adversarial-human-external-voices-"
        "same-host-process-isolated-reproducibility"
    )
    assert ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT == 3
    assert ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_AXIS_WEIGHT == 0.25


def test_stable_process_runs_produce_complete_reproducibility_evidence():
    bundle = _stable_bundle()
    payload = bundle.payload
    aggregate = payload["reproducibility"]["aggregate"]
    overall = aggregate["overall"]
    index = aggregate["process_isolated_reproduction_index"]

    assert bundle.status == "reproduced"
    assert payload["population"]["execution_count"] == 192
    assert payload["population"]["process_run_count"] == 3
    assert overall["exact_transcript_reproduction"]["rate"] == 1.0
    assert overall["normalized_transcript_reproduction"]["rate"] == 1.0
    assert overall["wer_reproduction"]["rate"] == 1.0
    assert overall["cer_reproduction"]["rate"] == 1.0
    assert index["score_percent"] == 100.0
    assert index["hard_conditions_all_passed"] is True
    assert set(index["axes"]) == {
        "output_identity",
        "metric_stability",
        "execution_and_process_integrity",
        "comparison_signal_stability",
    }
    assert all(value["weight"] == 0.25 for value in index["axes"].values())


def test_process_integrity_is_engineer_readable_and_hard_gated():
    aggregate = _stable_bundle().reproduction
    process_integrity = aggregate["process_integrity"]

    assert set(process_integrity) == {
        "parent_child_pid_link_conformance",
        "unique_launch_challenge_conformance",
        "distinct_process_instance_conformance",
        "clean_child_exit_conformance",
        "fixed_execution_commitment_conformance",
    }
    assert all(value["rate"] == 1.0 for value in process_integrity.values())
    assert aggregate["process_isolated_reproduction_index"][
        "qualification_threshold_applied"
    ] is False


def test_raw_output_variation_is_visible_in_axis_and_hard_status():
    bundle = evaluate_asr_adversarial_voices_process_reproducibility_v1(
        runs=(
            _process_run(1),
            _process_run(2),
            _process_run(
                3,
                run_observation=_run(3, changed_raw=("baseline", 0)),
            ),
        )
    )
    aggregate = bundle.reproduction
    exact = aggregate["overall"]["exact_transcript_reproduction"]
    index = aggregate["process_isolated_reproduction_index"]

    assert bundle.status == "variation_observed"
    assert exact["successful_count"] == 63
    assert exact["observed_count"] == 64
    assert index["axes"]["output_identity"]["score_percent"] == pytest.approx(
        ((63 / 64) * 100.0 + 100.0) / 2
    )
    assert index["score_percent"] < 100.0
    assert index["hard_conditions_all_passed"] is False


def test_normalized_metric_and_runtime_variation_remain_separate():
    changed = _run(
        3,
        changed_normalized=("candidate", 5),
        changed_metric=("candidate", 5),
        changed_environment=("candidate", 7),
    )
    bundle = evaluate_asr_adversarial_voices_process_reproducibility_v1(
        runs=(
            _process_run(1),
            _process_run(2),
            _process_run(3, run_observation=changed),
        )
    )
    overall = bundle.reproduction["overall"]

    assert bundle.status == "variation_observed"
    assert overall["exact_transcript_reproduction"]["successful_count"] == 64
    assert overall["normalized_transcript_reproduction"][
        "successful_count"
    ] == 63
    assert overall["wer_reproduction"]["successful_count"] == 63
    assert overall["cer_reproduction"]["successful_count"] == 63
    assert overall["runtime_identity_conformance"]["successful_count"] == 63
    assert overall["wer_cross_process_drift_envelope"][
        "maximum"
    ] == pytest.approx(0.01)
    assert overall["cer_cross_process_drift_envelope"][
        "maximum"
    ] == pytest.approx(0.005)


def test_comparison_metric_and_direction_reproduction_are_separate():
    bundle = evaluate_asr_adversarial_voices_process_reproducibility_v1(
        runs=(
            _process_run(1),
            _process_run(2),
            _process_run(
                3,
                run_observation=_run(3, general_wer=0.05),
            ),
        )
    )
    signal = bundle.reproduction["comparison_signal_reproduction"][
        "general_accuracy_wer"
    ]

    assert bundle.status == "variation_observed"
    assert signal["metric_stable"] is False
    assert signal["direction_stable"] is False
    assert signal["drift_envelope"] == pytest.approx(0.10)
    assert bundle.reproduction["comparison_signal_reproduction_rate"][
        "successful_count"
    ] == 3


def test_parent_observed_child_pid_must_equal_child_report():
    source = _process_run(1).process_launch
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="parent-child process identity",
    ):
        replace(source, parent_observed_child_process_id=9999)


def test_child_parent_pid_must_equal_declared_controller():
    source = _process_run(1).process_launch
    changed = replace(source.child_report, parent_process_id=9999)
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="parent-child process identity",
    ):
        replace(source, child_report=changed)


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"parent_observed_exit_code": 1}, "did not exit successfully"),
        (
            {"parent_spawn_started_at_unix_ns": 2_000_000_000},
            "timeline is invalid",
        ),
        (
            {"parent_observed_completed_at_unix_ns": 1},
            "timeline is invalid",
        ),
    ),
)
def test_parent_exit_and_timeline_are_integrity_gates(changes, message):
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match=message,
    ):
        replace(_process_run(1).process_launch, **changes)


def test_bundle_rejects_reused_launch_challenge():
    third_launch = _launch(3, challenge="challenge-1")
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="launch challenges",
    ):
        evaluate_asr_adversarial_voices_process_reproducibility_v1(
            runs=(
                _process_run(1),
                _process_run(2),
                _process_run(3, launch=third_launch),
            )
        )


def test_bundle_rejects_reused_process_instance_even_with_new_launch():
    first = _process_run(1)
    second = _process_run(2)
    third = _process_run(
        3,
        process_id=first.process_launch.child_report.process_id,
        started_at=first.process_launch.child_report.started_at_unix_ns,
    )
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="process instances",
    ):
        evaluate_asr_adversarial_voices_process_reproducibility_v1(
            runs=(first, second, third)
        )


def test_bundle_rejects_runtime_or_controller_commitment_drift():
    changed_runtime = _sha256("different-runtime")
    third = _process_run(3, launch=_launch(3, runtime=changed_runtime))
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="fixed execution commitments",
    ):
        evaluate_asr_adversarial_voices_process_reproducibility_v1(
            runs=(_process_run(1), _process_run(2), third)
        )


def test_process_run_rejects_run_observation_hash_or_suite_mismatch():
    source = _process_run(1)
    changed_report = replace(
        source.process_launch.child_report,
        run_observation_sha256=_sha256("different-run"),
    )
    changed_launch = replace(source.process_launch, child_report=changed_report)
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="run observation links",
    ):
        ASRAdversarialVOiCESProcessRunObservation(
            process_launch=changed_launch,
            run_observation=source.run_observation,
        )


def test_b11f_cohort_drift_is_revalidated_under_process_evidence():
    source = _run(3)
    changed_cases = tuple(
        replace(value, model_key="different-model")
        if value.role == "candidate"
        else value
        for value in source.cases
    )
    third_run = replace(
        source,
        candidate_model_key="different-model",
        cases=changed_cases,
    )
    third = _process_run(
        3,
        run_observation=third_run,
    )
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="B11F cohort",
    ):
        evaluate_asr_adversarial_voices_process_reproducibility_v1(
            runs=(_process_run(1), _process_run(2), third)
        )


def test_process_run_json_round_trip_revalidates_every_identity():
    original = _process_run(1)
    loaded = load_asr_adversarial_voices_process_run_observation_v1(
        _encode(original.payload)
    )

    assert loaded is not original
    assert loaded.payload == original.payload
    assert loaded.sha256 == original.sha256
    assert loaded.run_observation.sha256 == original.run_observation.sha256


def test_launch_and_child_result_round_trip_before_parent_finalization():
    process_run = _process_run(1)
    launch = process_run.process_launch.launch
    report = process_run.process_launch.child_report
    run = process_run.run_observation
    child_result = ASRAdversarialVOiCESChildProcessResult(
        launch=launch,
        child_report=report,
        run_observation=run,
    )

    loaded_launch = load_asr_adversarial_voices_process_launch_definition_v1(
        _encode(launch.payload)
    )
    loaded_result = load_asr_adversarial_voices_child_process_result_v1(
        _encode(child_result.payload)
    )
    finalized = finalize_asr_adversarial_voices_child_process_result_v1(
        child_result=loaded_result,
        parent_spawn_started_at_unix_ns=(
            process_run.process_launch.parent_spawn_started_at_unix_ns
        ),
        parent_observed_child_process_id=(
            process_run.process_launch.parent_observed_child_process_id
        ),
        parent_observed_exit_code=0,
        parent_observed_completed_at_unix_ns=(
            process_run.process_launch.parent_observed_completed_at_unix_ns
        ),
    )

    assert loaded_launch == launch
    assert loaded_result.payload == child_result.payload
    assert loaded_result.sha256 == child_result.sha256
    assert finalized.payload == process_run.payload


def test_child_result_loader_rejects_independently_tampered_links():
    source = _process_run(1)
    child_result = ASRAdversarialVOiCESChildProcessResult(
        launch=source.process_launch.launch,
        child_report=source.process_launch.child_report,
        run_observation=source.run_observation,
    ).payload
    child_result["child_report_sha256"] = _sha256("repinned-but-wrong")

    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="derived identity changed",
    ):
        load_asr_adversarial_voices_child_process_result_v1(
            _encode(child_result)
        )


def test_process_run_json_rejects_duplicate_keys_and_non_finite_values():
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="duplicate key",
    ):
        load_asr_adversarial_voices_process_run_observation_v1(
            b'{"schema_version":1,"schema_version":1}'
        )

    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="non-finite",
    ):
        load_asr_adversarial_voices_process_run_observation_v1(
            b'{"value":NaN}'
        )


def test_process_run_json_rejects_schema_or_derived_identity_tampering():
    source = _process_run(1).payload
    source["extra"] = True
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="must contain exactly",
    ):
        load_asr_adversarial_voices_process_run_observation_v1(
            _encode(source)
        )

    source = _process_run(1).payload
    source["run_observation_sha256"] = _sha256("tampered")
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="run-observation identity",
    ):
        load_asr_adversarial_voices_process_run_observation_v1(
            _encode(source)
        )


def test_process_run_file_api_does_not_embed_local_path(tmp_path):
    path = tmp_path / "process-run.json"
    path.write_bytes(_encode(_process_run(1).payload))

    loaded = load_asr_adversarial_voices_process_run_file_v1(path)
    encoded = process._canonical_json_bytes(loaded.payload)

    assert loaded.sha256 == _process_run(1).sha256
    assert str(tmp_path).encode("utf-8") not in encoded


def test_child_capture_uses_actual_pid_ppid_and_python_binary():
    run = _run(1)
    executable_sha = calculate_python_executable_sha256_v1()
    launch = replace(
        _launch(1, controller_process_id=os.getppid()),
        python_executable_sha256=executable_sha,
    )
    start = 1
    report = capture_asr_adversarial_voices_child_process_report_v1(
        launch=launch,
        run_observation=run,
        child_started_at_unix_ns=start,
        observed_source_code_sha256=launch.source_code_sha256,
        observed_runtime_environment_sha256=(
            launch.runtime_environment_sha256
        ),
        observed_host_environment_sha256=launch.host_environment_sha256,
        observed_model_set_sha256=launch.model_set_sha256,
        child_completed_at_unix_ns=start + 1,
    )

    assert report.process_id == os.getpid()
    assert report.parent_process_id == os.getppid()
    assert report.python_executable_sha256 == executable_sha
    assert report.run_observation_sha256 == run.sha256


def test_child_capture_rejects_wrong_parent_or_execution_commitment():
    run = _run(1)
    executable_sha = calculate_python_executable_sha256_v1()
    wrong_parent = replace(
        _launch(1, controller_process_id=os.getpid()),
        python_executable_sha256=executable_sha,
    )
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="not linked",
    ):
        capture_asr_adversarial_voices_child_process_report_v1(
            launch=wrong_parent,
            run_observation=run,
            child_started_at_unix_ns=1,
            observed_source_code_sha256=wrong_parent.source_code_sha256,
            observed_runtime_environment_sha256=(
                wrong_parent.runtime_environment_sha256
            ),
            observed_host_environment_sha256=(
                wrong_parent.host_environment_sha256
            ),
            observed_model_set_sha256=wrong_parent.model_set_sha256,
            child_completed_at_unix_ns=2,
        )

    correct_parent = replace(
        wrong_parent,
        controller_process_id=os.getppid(),
    )
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="commitments do not match",
    ):
        capture_asr_adversarial_voices_child_process_report_v1(
            launch=correct_parent,
            run_observation=run,
            child_started_at_unix_ns=1,
            observed_source_code_sha256=_sha256("wrong-source"),
            observed_runtime_environment_sha256=(
                correct_parent.runtime_environment_sha256
            ),
            observed_host_environment_sha256=(
                correct_parent.host_environment_sha256
            ),
            observed_model_set_sha256=correct_parent.model_set_sha256,
            child_completed_at_unix_ns=2,
        )


def test_python_executable_hash_rejects_missing_file(tmp_path):
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="does not exist",
    ):
        calculate_python_executable_sha256_v1(tmp_path / "missing-python")


def test_bundle_is_deterministic_content_free_and_frozen():
    first = _stable_bundle()
    second = _stable_bundle()
    encoded = process._canonical_json_bytes(first.payload)

    assert first.payload == second.payload
    assert first.sha256 == second.sha256
    assert b"generated transcript text" not in encoded
    assert b"/Users/" not in encoded
    assert b".wav" not in encoded

    with pytest.raises((FrozenInstanceError, AttributeError)):
        first.runs = ()
    with pytest.raises((FrozenInstanceError, AttributeError)):
        first.runs[0].run_observation = _run(1)


def test_evidence_boundary_and_authority_are_exact():
    bundle = _stable_bundle()
    boundary = bundle.payload["evidence_boundary"]

    assert boundary["independent_operating_system_processes_verified"] is True
    assert boundary["same_host_process_reproducibility_verified"] is True
    assert boundary["cross_host_reproducibility_evaluated"] is False
    assert boundary["cross_host_reproducibility_verified"] is None
    assert boundary["reproducibility_verified"] is None
    assert boundary["qualification_threshold_applied"] is False
    assert boundary["v1_reliability_scorecard_modified"] is False

    bundle.require_same_host_process_reproducibility_verified()
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="cross-host reproducibility",
    ):
        bundle.require_cross_host_reproducibility_verified()
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="no qualification threshold",
    ):
        bundle.require_process_reproduction_qualification()


def test_variation_bundle_refuses_positive_same_host_requirement():
    varied = evaluate_asr_adversarial_voices_process_reproducibility_v1(
        runs=(
            _process_run(1),
            _process_run(2),
            _process_run(
                3,
                run_observation=_run(3, changed_raw=("candidate", 2)),
            ),
        )
    )
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="contains variation",
    ):
        varied.require_same_host_process_reproducibility_verified()


def test_invalid_input_types_are_rejected():
    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="exactly three",
    ):
        evaluate_asr_adversarial_voices_process_reproducibility_v1(
            runs=(_process_run(1), _process_run(2))
        )

    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="non-empty bytes",
    ):
        load_asr_adversarial_voices_process_run_observation_v1(b"")

    with pytest.raises(
        ASRAdversarialVOiCESProcessReproducibilityError,
        match="could not be read",
    ):
        load_asr_adversarial_voices_process_run_file_v1(Path("missing.json"))
