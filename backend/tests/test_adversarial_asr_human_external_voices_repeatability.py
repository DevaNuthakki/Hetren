from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
from types import SimpleNamespace

import pytest

import app.adversarial_asr_human_external_voices_repeatability as repeatability
from app.adversarial_asr_human_external_voices_model_comparison_execution import (
    ASRAdversarialVOiCESModelComparisonExecutionStatus,
)
from app.adversarial_asr_human_external_voices_repeatability import (
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_KEY,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_MODEL_COUNT,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_VERSION,
    ASRAdversarialVOiCESRepeatabilityBundle,
    ASRAdversarialVOiCESRepeatabilityCaseObservation,
    ASRAdversarialVOiCESRepeatabilityError,
    ASRAdversarialVOiCESRepeatabilityPairKey,
    ASRAdversarialVOiCESRepeatabilityRunObservation,
    evaluate_asr_adversarial_voices_repeatability_v1,
    project_asr_adversarial_voices_repeatability_run_v1,
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
    case_id = f"voices-case-{index:02d}"
    provider = "faster_whisper"
    model = "small.en" if role == "baseline" else "large-v3-turbo"
    return ASRAdversarialVOiCESRepeatabilityCaseObservation(
        run_id=f"repeat-{run}",
        role=role,
        provider_key=provider,
        model_key=model,
        pair_key=_pair_key(index),
        arm="babble" if index % 2 == 0 else "control",
        case_id=case_id,
        audio_asset_sha256=_sha256(f"audio-{index}"),
        reference_transcript_sha256=_sha256(f"reference-{index}"),
        normalized_reference_sha256=_sha256(f"normalized-reference-{index}"),
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
        + (index / 1000)
        + wer_offset,
        cer=(0.08 if role == "baseline" else 0.03)
        + (index / 2000)
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
    robustness_wer: float = -0.02,
    robustness_cer: float = -0.01,
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
        run_id=f"repeat-{run}",
        execution_sha256=_sha256(f"b9-execution-{run}"),
        matched_control_suite_sha256=_sha256("matched-control-suite"),
        adversarial_suite_evidence_sha256=_sha256("adversarial-suite"),
        baseline_campaign_id=f"baseline-repeat-{run}",
        baseline_campaign_version="1.0.0",
        baseline_campaign_sha256=_sha256(f"baseline-campaign-{run}"),
        baseline_metrics_sha256=_sha256(f"baseline-metrics-{run}"),
        baseline_provider_key="faster_whisper",
        baseline_model_key="small.en",
        candidate_campaign_id=f"candidate-repeat-{run}",
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


def _stable_bundle() -> ASRAdversarialVOiCESRepeatabilityBundle:
    return evaluate_asr_adversarial_voices_repeatability_v1(
        runs=tuple(_run(value) for value in range(1, 4))
    )


def test_constants_are_exact():
    assert ASR_ADVERSARIAL_VOICES_REPEATABILITY_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_REPEATABILITY_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_REPEATABILITY_KEY == (
        "hetren.asr.adversarial-human-external-voices-"
        "same-environment-campaign-repeatability"
    )
    assert ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT == 3
    assert ASR_ADVERSARIAL_VOICES_REPEATABILITY_MODEL_COUNT == 2
    assert ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT == 32
    assert ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT == 64


def test_stable_runs_produce_complete_engineer_readable_evidence():
    bundle = _stable_bundle()
    payload = bundle.payload
    overall = payload["repeatability"]["aggregate"]["overall"]

    assert bundle.status == "stable"
    assert payload["population"] == {
        "run_count": 3,
        "model_count": 2,
        "case_count_per_model": 32,
        "case_model_unit_count": 64,
        "execution_count": 192,
        "ordered_run_ids": ["repeat-1", "repeat-2", "repeat-3"],
    }
    assert overall["exact_transcript_repeatability"]["rate"] == 1.0
    assert overall["normalized_transcript_repeatability"]["rate"] == 1.0
    assert overall["runtime_identity_conformance"]["rate"] == 1.0
    assert overall["wer_stability"]["rate"] == 1.0
    assert overall["cer_stability"]["rate"] == 1.0
    assert overall["wer_drift_envelope"] == {
        "maximum": 0.0,
        "macro_mean": 0.0,
    }
    assert overall["cer_drift_envelope"] == {
        "maximum": 0.0,
        "macro_mean": 0.0,
    }


def test_raw_commitment_variation_does_not_erase_normalized_stability():
    bundle = evaluate_asr_adversarial_voices_repeatability_v1(
        runs=(
            _run(1),
            _run(2),
            _run(3, changed_raw=("baseline", 0)),
        )
    )
    overall = bundle.aggregate["overall"]

    assert bundle.status == "variation_observed"
    assert overall["exact_transcript_repeatability"] == {
        "successful_count": 63,
        "observed_count": 64,
        "rate": 63 / 64,
        "score_percent": (63 / 64) * 100.0,
    }
    assert overall["normalized_transcript_repeatability"]["rate"] == 1.0
    assert overall["wer_stability"]["rate"] == 1.0


def test_normalized_and_metric_drift_are_reported_without_imputation():
    bundle = evaluate_asr_adversarial_voices_repeatability_v1(
        runs=(
            _run(1),
            _run(2),
            _run(
                3,
                changed_normalized=("candidate", 5),
                changed_metric=("candidate", 5),
            ),
        )
    )
    overall = bundle.aggregate["overall"]

    assert bundle.status == "variation_observed"
    assert overall["normalized_transcript_repeatability"][
        "successful_count"
    ] == 63
    assert overall["wer_stability"]["successful_count"] == 63
    assert overall["cer_stability"]["successful_count"] == 63
    assert overall["wer_drift_envelope"]["maximum"] == pytest.approx(0.01)
    assert overall["cer_drift_envelope"]["maximum"] == pytest.approx(0.005)


def test_runtime_drift_is_visible_but_not_mislabeled_reproducibility():
    bundle = evaluate_asr_adversarial_voices_repeatability_v1(
        runs=(
            _run(1),
            _run(2),
            _run(3, changed_environment=("candidate", 7)),
        )
    )
    boundary = bundle.payload["evidence_boundary"]

    assert bundle.aggregate["overall"]["runtime_identity_conformance"][
        "successful_count"
    ] == 63
    assert bundle.status == "variation_observed"
    assert boundary["cross_host_reproducibility_evaluated"] is False
    assert boundary["reproducibility_verified"] is None
    assert boundary["reproducibility_claimed"] is False
    assert boundary["v1_reliability_scorecard_modified"] is False


def test_comparison_metric_and_direction_stability_are_separate():
    bundle = evaluate_asr_adversarial_voices_repeatability_v1(
        runs=(
            _run(1),
            _run(2),
            _run(3, general_wer=0.05),
        )
    )
    signal = bundle.aggregate["comparison_signal_stability"][
        "general_accuracy_wer"
    ]

    assert signal["metric_stable"] is False
    assert signal["direction_stable"] is False
    assert signal["drift_envelope"] == pytest.approx(0.10)
    assert [value["direction"] for value in signal["values_by_run"]] == [
        "candidate_better",
        "candidate_better",
        "candidate_worse",
    ]


def test_bundle_is_deterministic_hash_bound_and_contains_no_content():
    first = _stable_bundle()
    second = _stable_bundle()

    assert first is not second
    assert first.payload == second.payload
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64

    encoded = repeatability._canonical_json_bytes(first.payload)
    assert b"generated transcript text" not in encoded
    assert b"/Users/" not in encoded
    assert b".wav" not in encoded


def test_bundle_rejects_missing_or_duplicate_run_evidence():
    first = _run(1)
    second = _run(2)
    third = _run(3)

    with pytest.raises(
        ASRAdversarialVOiCESRepeatabilityError,
        match="exactly three",
    ):
        evaluate_asr_adversarial_voices_repeatability_v1(
            runs=(first, second)
        )

    with pytest.raises(
        ASRAdversarialVOiCESRepeatabilityError,
        match="execution identities",
    ):
        evaluate_asr_adversarial_voices_repeatability_v1(
            runs=(
                first,
                second,
                replace(third, execution_sha256=first.execution_sha256),
            )
        )

    with pytest.raises(
        ASRAdversarialVOiCESRepeatabilityError,
        match="baseline campaigns",
    ):
        evaluate_asr_adversarial_voices_repeatability_v1(
            runs=(
                first,
                second,
                replace(third, baseline_campaign_id=first.baseline_campaign_id),
            )
        )


def test_bundle_rejects_cohort_or_model_identity_drift():
    first = _run(1)
    second = _run(2)
    third = _run(3)

    with pytest.raises(
        ASRAdversarialVOiCESRepeatabilityError,
        match="cohort or model identity",
    ):
        evaluate_asr_adversarial_voices_repeatability_v1(
            runs=(
                first,
                second,
                replace(
                    third,
                    matched_control_suite_sha256=_sha256("different-suite"),
                ),
            )
        )

    changed_cases = tuple(
        replace(value, model_key="different-model")
        if value.role == "candidate"
        else value
        for value in third.cases
    )
    changed_model = replace(
        third,
        candidate_model_key="different-model",
        cases=changed_cases,
    )
    with pytest.raises(
        ASRAdversarialVOiCESRepeatabilityError,
        match="cohort or model identity",
    ):
        evaluate_asr_adversarial_voices_repeatability_v1(
            runs=(first, second, changed_model)
        )


def test_run_observation_rejects_cross_model_input_drift():
    source = _run(1)
    changed = tuple(
        replace(value, audio_asset_sha256=_sha256("changed-audio"))
        if value.role == "candidate" and value.case_id == "voices-case-00"
        else value
        for value in source.cases
    )

    with pytest.raises(
        ASRAdversarialVOiCESRepeatabilityError,
        match="identical inputs",
    ):
        replace(source, cases=changed)


def test_projection_rejects_incomplete_b9_before_reading_outputs(monkeypatch):
    incomplete = SimpleNamespace(
        status=(
            ASRAdversarialVOiCESModelComparisonExecutionStatus
            .BASELINE_INCOMPLETE
        ),
        baseline_metrics=None,
        candidate_metrics=None,
    )
    monkeypatch.setattr(
        repeatability,
        "_reverify_execution",
        lambda value: value,
    )

    with pytest.raises(
        ASRAdversarialVOiCESRepeatabilityError,
        match="complete B9 run",
    ):
        project_asr_adversarial_voices_repeatability_run_v1(
            run_id="repeat-1",
            execution=incomplete,
        )


def test_projection_maps_complete_b9_without_transcript_content(monkeypatch):
    def role_values(role: str):
        model = "small.en" if role == "baseline" else "large-v3-turbo"
        definition = SimpleNamespace(
            campaign_id=f"{role}-campaign-1",
            campaign_version="1.0.0",
            provider_key="faster_whisper",
            model_key=model,
        )
        cases = []
        attempts = []
        for index in range(32):
            key = SimpleNamespace(
                source_key=((index // 2) + 1, 101, 201),
                room="rm1",
                microphone_id=1,
                angle_degrees=10,
            )
            cases.append(
                SimpleNamespace(
                    pair_key=key,
                    arm="babble" if index % 2 == 0 else "control",
                    case_id=f"voices-case-{index:02d}",
                    audio_asset_sha256=_sha256(f"audio-{index}"),
                    reference_transcript_sha256=_sha256(
                        f"reference-{index}"
                    ),
                    normalized_reference_sha256=_sha256(
                        f"normalized-reference-{index}"
                    ),
                    execution_evidence_sha256=_sha256(
                        f"execution-{role}-{index}"
                    ),
                    generated_transcript_sha256=_sha256(
                        f"generated-{role}-{index}"
                    ),
                    normalized_generated_sha256=_sha256(
                        f"normalized-{role}-{index}"
                    ),
                    evaluation=SimpleNamespace(wer=0.1, cer=0.05),
                )
            )
            attempts.append(
                SimpleNamespace(
                    case_id=f"voices-case-{index:02d}",
                    execution_definition=SimpleNamespace(
                        execution_environment_sha256=_sha256(
                            f"environment-{role}-{index}"
                        )
                    ),
                )
            )
        campaign = SimpleNamespace(
            sha256=_sha256(f"{role}-campaign"),
            campaign=SimpleNamespace(
                definition=definition,
                attempts=tuple(attempts),
            ),
            suite=SimpleNamespace(
                evidence=SimpleNamespace(sha256=_sha256("suite-evidence"))
            ),
        )
        metrics = SimpleNamespace(
            sha256=_sha256(f"{role}-metrics"),
            cases=tuple(cases),
        )
        return campaign, metrics

    baseline_campaign, baseline_metrics = role_values("baseline")
    candidate_campaign, candidate_metrics = role_values("candidate")
    comparison = SimpleNamespace(
        aggregate={
            "case_macro_mean": {
                "all": {
                    "candidate_minus_baseline": {
                        "wer": -0.05,
                        "cer": -0.04,
                    }
                }
            },
            "pair_noise_degradation_macro_mean": {
                "candidate_minus_baseline": {
                    "wer": -0.02,
                    "cer": -0.01,
                }
            },
        }
    )
    complete = SimpleNamespace(
        status=ASRAdversarialVOiCESModelComparisonExecutionStatus.COMPLETED,
        sha256=_sha256("complete-b9"),
        matched_control_suite_sha256=_sha256("matched-suite"),
        baseline_campaign=baseline_campaign,
        candidate_campaign=candidate_campaign,
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        require_complete_comparison=lambda: comparison,
    )
    monkeypatch.setattr(
        repeatability,
        "_reverify_execution",
        lambda value: value,
    )

    observed = project_asr_adversarial_voices_repeatability_run_v1(
        run_id="repeat-1",
        execution=complete,
    )

    assert len(observed.cases) == 64
    assert observed.baseline_model_key == "small.en"
    assert observed.candidate_model_key == "large-v3-turbo"
    assert observed.general_accuracy_wer_differential == -0.05
    assert observed.robustness_cer_differential == -0.01


def test_repeatability_evidence_refuses_unsupported_authority():
    bundle = _stable_bundle()

    with pytest.raises(
        ASRAdversarialVOiCESRepeatabilityError,
        match="cross-host reproducibility",
    ):
        bundle.require_reproducibility_verified()

    with pytest.raises(
        ASRAdversarialVOiCESRepeatabilityError,
        match="no threshold",
    ):
        bundle.require_repeatability_qualification()


def test_repeatability_contracts_are_frozen_slots_dataclasses():
    bundle = _stable_bundle()

    with pytest.raises((FrozenInstanceError, AttributeError)):
        bundle.runs = ()

    with pytest.raises((FrozenInstanceError, AttributeError)):
        bundle.runs[0].run_id = "changed"

    with pytest.raises((FrozenInstanceError, AttributeError)):
        bundle.units[0].observations = ()
