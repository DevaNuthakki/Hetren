from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib

import pytest

from app import (
    adversarial_asr_human_external_voices_cross_host_reproducibility
    as cross_host,
)
from app.adversarial_asr_human_external_voices_cross_host_reproducibility import (
    ASR_ADVERSARIAL_VOICES_CROSS_HOST_ATTESTATION_SCHEMES,
    ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_KEY,
    ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_VERSION,
    ASRAdversarialVOiCESCrossHostObservation,
    ASRAdversarialVOiCESCrossHostReproducibilityBundle,
    ASRAdversarialVOiCESCrossHostReproducibilityError,
    evaluate_asr_adversarial_voices_cross_host_reproducibility_v1,
)
from app.adversarial_asr_human_external_voices_process_reproducibility import (
    ASRAdversarialVOiCESChildProcessReport,
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


_EXPERIMENT_SHA256 = hashlib.sha256(b"b11j-experiment").hexdigest()
_SOURCE_SHA256 = hashlib.sha256(b"source").hexdigest()
_RUNTIME_SHA256 = hashlib.sha256(b"runtime").hexdigest()
_MODEL_SET_SHA256 = hashlib.sha256(b"model-set").hexdigest()
_MATCHED_SUITE_SHA256 = hashlib.sha256(b"matched-suite").hexdigest()
_ADVERSARIAL_SUITE_SHA256 = hashlib.sha256(
    b"adversarial-suite"
).hexdigest()


def _sha256_text(value: str) -> str:
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
    host: str,
    run: int,
    role: str,
    index: int,
    raw_change: bool,
    normalized_change: bool,
    wer_delta: float,
    cer_delta: float,
    fixed_input_change: bool,
    within_host_variation: bool,
    candidate_model_key: str,
) -> ASRAdversarialVOiCESRepeatabilityCaseObservation:
    run_id = f"{host}-process-run-{run:02d}"
    changed_unit = role == "baseline" and index == 0
    raw_suffix = ""
    normalized_suffix = ""
    if host == "reproduction_host" and changed_unit:
        raw_suffix = "-changed" if raw_change else ""
        normalized_suffix = "-changed" if normalized_change else ""
    if within_host_variation and run == 3 and changed_unit:
        raw_suffix = "-within-host-change"
        normalized_suffix = "-within-host-change"
    metric_wer_delta = (
        wer_delta
        if host == "reproduction_host" and changed_unit
        else 0.0
    )
    metric_cer_delta = (
        cer_delta
        if host == "reproduction_host" and changed_unit
        else 0.0
    )
    reference_key = f"reference-{index}"
    if (
        host == "reproduction_host"
        and index == 0
        and fixed_input_change
    ):
        reference_key += "-changed"
    model_key = (
        "small.en" if role == "baseline" else candidate_model_key
    )
    return ASRAdversarialVOiCESRepeatabilityCaseObservation(
        run_id=run_id,
        role=role,
        provider_key="faster_whisper",
        model_key=model_key,
        pair_key=_pair_key(index),
        arm="babble" if index % 2 == 0 else "control",
        case_id=f"voices-case-{index:02d}",
        audio_asset_sha256=_sha256_text(f"audio-{index}"),
        reference_transcript_sha256=_sha256_text(reference_key),
        normalized_reference_sha256=_sha256_text(
            f"normalized-{reference_key}"
        ),
        execution_environment_sha256=_sha256_text(
            f"execution-environment-{host}-{role}-{index}"
        ),
        execution_evidence_sha256=_sha256_text(
            f"execution-evidence-{host}-{run}-{role}-{index}"
        ),
        generated_transcript_sha256=_sha256_text(
            f"generated-{role}-{index}{raw_suffix}"
        ),
        normalized_generated_sha256=_sha256_text(
            f"normalized-generated-{role}-{index}{normalized_suffix}"
        ),
        wer=(0.10 if role == "baseline" else 0.05)
        + index / 1000
        + metric_wer_delta,
        cer=(0.08 if role == "baseline" else 0.03)
        + index / 2000
        + metric_cer_delta,
    )


def _run(
    *,
    host: str,
    run: int,
    raw_change: bool = False,
    normalized_change: bool = False,
    wer_delta: float = 0.0,
    cer_delta: float = 0.0,
    fixed_input_change: bool = False,
    within_host_variation: bool = False,
    signal_delta: float = 0.0,
    candidate_model_key: str = "large-v3-turbo",
    matched_suite_sha256: str = _MATCHED_SUITE_SHA256,
    adversarial_suite_sha256: str = _ADVERSARIAL_SUITE_SHA256,
) -> ASRAdversarialVOiCESRepeatabilityRunObservation:
    cases = tuple(
        _case(
            host=host,
            run=run,
            role=role,
            index=index,
            raw_change=raw_change,
            normalized_change=normalized_change,
            wer_delta=wer_delta,
            cer_delta=cer_delta,
            fixed_input_change=fixed_input_change,
            within_host_variation=within_host_variation,
            candidate_model_key=candidate_model_key,
        )
        for role in ("baseline", "candidate")
        for index in range(ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT)
    )
    return ASRAdversarialVOiCESRepeatabilityRunObservation(
        run_id=f"{host}-process-run-{run:02d}",
        execution_sha256=_sha256_text(f"b9-execution-{host}-{run}"),
        matched_control_suite_sha256=matched_suite_sha256,
        adversarial_suite_evidence_sha256=adversarial_suite_sha256,
        baseline_campaign_id=f"baseline-{host}-{run}",
        baseline_campaign_version="1.0.0",
        baseline_campaign_sha256=_sha256_text(
            f"baseline-campaign-{host}-{run}"
        ),
        baseline_metrics_sha256=_sha256_text(
            f"baseline-metrics-{host}-{run}"
        ),
        baseline_provider_key="faster_whisper",
        baseline_model_key="small.en",
        candidate_campaign_id=f"candidate-{host}-{run}",
        candidate_campaign_version="1.0.0",
        candidate_campaign_sha256=_sha256_text(
            f"candidate-campaign-{host}-{run}"
        ),
        candidate_metrics_sha256=_sha256_text(
            f"candidate-metrics-{host}-{run}"
        ),
        candidate_provider_key="faster_whisper",
        candidate_model_key=candidate_model_key,
        cases=cases,
        general_accuracy_wer_differential=-0.07 + signal_delta,
        general_accuracy_cer_differential=-0.05,
        robustness_wer_differential=0.03,
        robustness_cer_differential=0.02,
    )


def _process_bundle(
    *,
    host: str,
    raw_change: bool = False,
    normalized_change: bool = False,
    wer_delta: float = 0.0,
    cer_delta: float = 0.0,
    fixed_input_change: bool = False,
    within_host_variation: bool = False,
    signal_delta: float = 0.0,
    source_sha256: str = _SOURCE_SHA256,
    runtime_sha256: str = _RUNTIME_SHA256,
    model_set_sha256: str = _MODEL_SET_SHA256,
    matched_suite_sha256: str = _MATCHED_SUITE_SHA256,
    adversarial_suite_sha256: str = _ADVERSARIAL_SUITE_SHA256,
    candidate_model_key: str = "large-v3-turbo",
):
    runs = []
    controller_process_id = 500 if host == "reference_host" else 600
    for run in range(1, 4):
        run_observation = _run(
            host=host,
            run=run,
            raw_change=raw_change,
            normalized_change=normalized_change,
            wer_delta=wer_delta,
            cer_delta=cer_delta,
            fixed_input_change=fixed_input_change,
            within_host_variation=within_host_variation,
            signal_delta=signal_delta,
            candidate_model_key=candidate_model_key,
            matched_suite_sha256=matched_suite_sha256,
            adversarial_suite_sha256=adversarial_suite_sha256,
        )
        launch = ASRAdversarialVOiCESProcessLaunchDefinition(
            run_id=run_observation.run_id,
            launch_id=f"{host}-launch-{run:02d}",
            launch_challenge_sha256=_sha256_text(
                f"launch-challenge-{host}-{run}"
            ),
            controller_invocation_sha256=_sha256_text(
                f"controller-{host}"
            ),
            controller_process_id=controller_process_id,
            source_code_sha256=source_sha256,
            python_executable_sha256=_sha256_text(f"python-{host}"),
            runtime_environment_sha256=runtime_sha256,
            host_environment_sha256=_sha256_text(
                f"host-environment-{host}"
            ),
            model_set_sha256=model_set_sha256,
            matched_control_suite_sha256=matched_suite_sha256,
            adversarial_suite_evidence_sha256=adversarial_suite_sha256,
        )
        start = 1_000_000_000 + run * 10_000
        report = ASRAdversarialVOiCESChildProcessReport(
            run_id=launch.run_id,
            launch_definition_sha256=launch.sha256,
            launch_challenge_sha256=launch.launch_challenge_sha256,
            controller_invocation_sha256=(
                launch.controller_invocation_sha256
            ),
            process_id=controller_process_id + run,
            parent_process_id=controller_process_id,
            started_at_unix_ns=start,
            completed_at_unix_ns=start + 100,
            source_code_sha256=launch.source_code_sha256,
            python_executable_sha256=launch.python_executable_sha256,
            runtime_environment_sha256=launch.runtime_environment_sha256,
            host_environment_sha256=launch.host_environment_sha256,
            model_set_sha256=launch.model_set_sha256,
            run_observation_sha256=run_observation.sha256,
        )
        runs.append(
            ASRAdversarialVOiCESProcessRunObservation(
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
        )
    return evaluate_asr_adversarial_voices_process_reproducibility_v1(
        runs=tuple(runs)
    )


def _observation(
    *,
    host_role: str,
    experiment_sha256: str = _EXPERIMENT_SHA256,
    host_instance_sha256: str | None = None,
    host_attestation_evidence_sha256: str | None = None,
    host_challenge_sha256: str | None = None,
    process_bundle=None,
) -> ASRAdversarialVOiCESCrossHostObservation:
    return ASRAdversarialVOiCESCrossHostObservation(
        host_role=host_role,
        cross_host_experiment_sha256=experiment_sha256,
        host_challenge_sha256=(
            host_challenge_sha256
            or _sha256_text(f"host-challenge-{host_role}")
        ),
        host_instance_sha256=(
            host_instance_sha256
            or _sha256_text(f"host-instance-{host_role}")
        ),
        host_attestation_evidence_sha256=(
            host_attestation_evidence_sha256
            or _sha256_text(f"host-attestation-{host_role}")
        ),
        host_attestation_scheme="operator_witnessed_distinct_host_v1",
        process_reproducibility=(
            process_bundle or _process_bundle(host=host_role)
        ),
    )


def _bundle(**reproduction_changes):
    return evaluate_asr_adversarial_voices_cross_host_reproducibility_v1(
        observations=(
            _observation(host_role="reference_host"),
            _observation(
                host_role="reproduction_host",
                process_bundle=_process_bundle(
                    host="reproduction_host",
                    **reproduction_changes,
                ),
            ),
        )
    )


def test_constants_define_a_two_host_descriptive_protocol():
    assert ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_KEY.endswith(
        "cross-host-process-isolated-reproducibility"
    )
    assert ASR_ADVERSARIAL_VOICES_CROSS_HOST_ATTESTATION_SCHEMES == {
        "operator_witnessed_distinct_host_v1",
        "cloud_instance_identity_document_v1",
        "hardware_backed_host_attestation_v1",
    }


def test_valid_distinct_hosts_reproduce_every_unit_and_signal():
    bundle = _bundle()
    aggregate = bundle.aggregate

    assert bundle.status == "reproduced"
    assert bundle.payload["population"]["execution_count"] == 384
    assert aggregate["overall"]["unit_count"] == 64
    assert aggregate["cross_host_reproduction_index"][
        "score_percent"
    ] == 100.0
    assert aggregate["cross_host_reproduction_index"][
        "hard_conditions_all_passed"
    ] is True
    assert all(
        value["metric_reproduced"] and value["direction_reproduced"]
        for value in aggregate["comparison_signal_reproduction"].values()
    )


def test_host_environment_and_python_identities_may_differ():
    bundle = _bundle()
    observations = bundle.observations

    assert (
        observations[0].anchor.host_environment_sha256
        != observations[1].anchor.host_environment_sha256
    )
    assert (
        observations[0].anchor.python_executable_sha256
        != observations[1].anchor.python_executable_sha256
    )
    assert bundle.status == "reproduced"


def test_bundle_is_deterministic_content_free_and_frozen():
    first = _bundle()
    second = _bundle()
    encoded = cross_host._canonical_json_bytes(first.payload)

    assert first.payload == second.payload
    assert first.sha256 == second.sha256
    assert b".wav" not in encoded
    assert b"generated transcript text" not in encoded
    with pytest.raises((FrozenInstanceError, AttributeError)):
        first.observations = ()


def test_raw_transcript_cross_host_variation_is_reported_not_rejected():
    bundle = _bundle(raw_change=True)
    exact = bundle.aggregate["overall"]["exact_transcript_reproduction"]

    assert all(
        value.process_bundle.status == "reproduced"
        for value in bundle.observations
    )
    assert bundle.status == "variation_observed"
    assert exact["successful_count"] == 63
    assert exact["observed_count"] == 64
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="contains variation",
    ):
        bundle.require_cross_host_reproducibility_verified()


def test_normalized_transcript_cross_host_variation_is_reported():
    bundle = _bundle(normalized_change=True)
    normalized = bundle.aggregate["overall"][
        "normalized_transcript_reproduction"
    ]

    assert bundle.status == "variation_observed"
    assert normalized["successful_count"] == 63


@pytest.mark.parametrize(
    ("change", "metric"),
    (
        ({"wer_delta": 0.001}, "wer_reproduction"),
        ({"cer_delta": 0.001}, "cer_reproduction"),
    ),
)
def test_metric_cross_host_variation_is_reported(change, metric):
    bundle = _bundle(**change)
    result = bundle.aggregate["overall"][metric]

    assert bundle.status == "variation_observed"
    assert result["successful_count"] == 63


def test_metric_equality_uses_the_canonical_absolute_tolerance():
    tolerance = (
        cross_host.ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE
    )

    assert _bundle(wer_delta=tolerance / 2).status == "reproduced"
    assert _bundle(wer_delta=tolerance * 2).status == "variation_observed"


def test_comparison_signal_cross_host_variation_is_reported():
    bundle = _bundle(signal_delta=0.01)
    signal = bundle.aggregate["comparison_signal_reproduction"][
        "general_accuracy_wer"
    ]

    assert bundle.status == "variation_observed"
    assert signal["metric_reproduced"] is False
    assert signal["direction_reproduced"] is True


def test_comparison_signal_direction_change_is_reported():
    bundle = _bundle(signal_delta=0.08)
    signal = bundle.aggregate["comparison_signal_reproduction"][
        "general_accuracy_wer"
    ]

    assert bundle.status == "variation_observed"
    assert signal["metric_reproduced"] is False
    assert signal["direction_reproduced"] is False


@pytest.mark.parametrize(
    "field",
    (
        "host_instance_sha256",
        "host_attestation_evidence_sha256",
        "host_challenge_sha256",
    ),
)
def test_distinct_host_attestation_fields_are_required(field):
    reference = _observation(host_role="reference_host")
    reproduction_kwargs = {
        field: getattr(reference, field),
    }
    reproduction = _observation(
        host_role="reproduction_host",
        **reproduction_kwargs,
    )

    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="requires distinct",
    ):
        evaluate_asr_adversarial_voices_cross_host_reproducibility_v1(
            observations=(reference, reproduction)
        )


def test_one_b11h_bundle_cannot_be_reused_as_both_hosts():
    process = _process_bundle(host="reference_host")

    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="distinct B11H process bundles",
    ):
        evaluate_asr_adversarial_voices_cross_host_reproducibility_v1(
            observations=(
                _observation(
                    host_role="reference_host",
                    process_bundle=process,
                ),
                _observation(
                    host_role="reproduction_host",
                    process_bundle=process,
                ),
            )
        )


def test_host_observations_must_share_one_experiment_identity():
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="experiment identity",
    ):
        evaluate_asr_adversarial_voices_cross_host_reproducibility_v1(
            observations=(
                _observation(host_role="reference_host"),
                _observation(
                    host_role="reproduction_host",
                    experiment_sha256=_sha256_text("different-experiment"),
                ),
            )
        )


@pytest.mark.parametrize(
    "change",
    (
        {"source_sha256": _sha256_text("different-source")},
        {"runtime_sha256": _sha256_text("different-runtime")},
        {"model_set_sha256": _sha256_text("different-model-set")},
        {"matched_suite_sha256": _sha256_text("different-suite")},
        {
            "adversarial_suite_sha256": _sha256_text(
                "different-adversarial-suite"
            )
        },
    ),
)
def test_portable_execution_commitments_must_match(change):
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="source, runtime, model, or cohort",
    ):
        _bundle(**change)


def test_model_identity_must_match_even_with_same_model_set_commitment():
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="provider, model, or campaign version",
    ):
        _bundle(candidate_model_key="different-candidate")


def test_fixed_input_identity_must_match_across_hosts():
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="fixed-input identity",
    ):
        _bundle(fixed_input_change=True)


def test_within_host_variation_prevents_cross_host_verification():
    bundle = _bundle(within_host_variation=True)
    host_rate = bundle.aggregate["host_process_reproduction"]

    assert bundle.observations[1].process_bundle.status == "variation_observed"
    assert bundle.status == "variation_observed"
    assert host_rate["successful_count"] == 1
    assert bundle.aggregate["cross_host_reproduction_index"][
        "hard_conditions"
    ]["both_hosts_process_reproduced"] is False


def test_canonical_host_role_order_and_exact_types_are_required():
    reference = _observation(host_role="reference_host")
    reproduction = _observation(host_role="reproduction_host")

    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="canonical role order",
    ):
        evaluate_asr_adversarial_voices_cross_host_reproducibility_v1(
            observations=(reproduction, reference)
        )
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="exactly two",
    ):
        evaluate_asr_adversarial_voices_cross_host_reproducibility_v1(
            observations=(reference,)
        )
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="exactly two",
    ):
        evaluate_asr_adversarial_voices_cross_host_reproducibility_v1(
            observations=[reference, reproduction]
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("host_role", "invalid", "host role"),
        ("host_instance_sha256", "invalid", "lowercase SHA-256"),
        ("host_attestation_scheme", "invalid", "unsupported"),
    ),
)
def test_host_observation_rejects_invalid_identity_fields(
    field,
    value,
    message,
):
    values = {
        "host_role": "reference_host",
        "cross_host_experiment_sha256": _EXPERIMENT_SHA256,
        "host_challenge_sha256": _sha256_text("challenge"),
        "host_instance_sha256": _sha256_text("instance"),
        "host_attestation_evidence_sha256": _sha256_text("attestation"),
        "host_attestation_scheme": (
            "operator_witnessed_distinct_host_v1"
        ),
        "process_reproducibility": _process_bundle(
            host="reference_host"
        ),
    }
    values[field] = value

    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match=message,
    ):
        ASRAdversarialVOiCESCrossHostObservation(**values)


def test_host_observation_requires_an_exact_b11h_bundle():
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="exact B11H",
    ):
        ASRAdversarialVOiCESCrossHostObservation(
            host_role="reference_host",
            cross_host_experiment_sha256=_EXPERIMENT_SHA256,
            host_challenge_sha256=_sha256_text("challenge"),
            host_instance_sha256=_sha256_text("instance"),
            host_attestation_evidence_sha256=_sha256_text("attestation"),
            host_attestation_scheme=(
                "operator_witnessed_distinct_host_v1"
            ),
            process_reproducibility=object(),
        )


def test_boundary_and_authority_methods_are_exact():
    bundle = _bundle()
    boundary = bundle.payload["evidence_boundary"]

    assert boundary["cross_host_reproducibility_evaluated"] is True
    assert boundary["cross_host_reproducibility_verified"] is True
    assert boundary["reproducibility_verified"] is True
    assert boundary["qualification_threshold_applied"] is False
    assert boundary["production_qualified"] is False
    assert boundary["release_enforcement_eligible"] is False
    bundle.require_cross_host_reproducibility_verified()
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="no qualification threshold",
    ):
        bundle.require_qualification()
    with pytest.raises(
        ASRAdversarialVOiCESCrossHostReproducibilityError,
        match="does not authorize release enforcement",
    ):
        bundle.require_release_enforcement()


def test_bundle_type_and_identity_are_exposed():
    bundle = _bundle()

    assert isinstance(
        bundle,
        ASRAdversarialVOiCESCrossHostReproducibilityBundle,
    )
    assert len(bundle.sha256) == 64
    assert len(bundle.observations[0].sha256) == 64
