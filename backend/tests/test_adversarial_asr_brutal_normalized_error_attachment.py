from types import SimpleNamespace

import pytest

from app.adversarial_asr_brutal_execution_runner import (
    ASR_BRUTAL_EXECUTION_RUN_VERSION,
    ASRBrutalExecutionRunnerError,
    _completed_result_payload,
)
from hvee.packs.asr.adversarial_execution_evidence import (
    calculate_asr_adversarial_transcript_sha256,
)


REFERENCE = (
    "Administer five milligrams at nine fifteen AM. "
    "Confirmation code AB7K92."
)

GENERATED = (
    "Administer 5 mg at 9.15 am. "
    "Confirmation code AD7K92."
)


def _bundle(case_id="case.one"):
    return SimpleNamespace(
        suite=SimpleNamespace(
            cases=(
                SimpleNamespace(
                    case_id=case_id,
                    reference_transcript=REFERENCE,
                ),
            ),
        ),
    )


def _result(case_id="case.one"):
    return SimpleNamespace(
        case_id=case_id,
        audio_asset_sha256="a" * 64,
        audio_byte_length=123,
        generated_transcript=GENERATED,
        environment={
            "provider": "test-provider",
            "model_name": "test-model",
        },
        semantic_observations={
            "critical_number": (),
            "critical_identifier": (),
            "critical_terminology": (),
        },
        execution_definition={
            "execution_id": "test.execution",
        },
        execution_evidence=SimpleNamespace(
            payload={"artifact": "existing-v1-child-evidence"},
            sha256="b" * 64,
        ),
    )


def test_brutal_run_artifact_version_is_bumped_for_normalized_attachment():
    assert ASR_BRUTAL_EXECUTION_RUN_VERSION == "1.1.0"


def test_completed_result_attaches_canonical_normalized_wer_and_cer():
    payload = _completed_result_payload(
        _result(),
        bundle=_bundle(),
    )

    normalized = payload["normalized_error_evidence"]

    assert normalized["attachment_version"] == "1.0.0"

    assert normalized["normalization"] == {
        "key": "hetren.asr.text.basic",
        "version": "1.0.0",
    }

    assert normalized["reference_transcript_sha256"] == (
        calculate_asr_adversarial_transcript_sha256(
            REFERENCE
        )
    )

    assert normalized["generated_transcript_sha256"] == (
        calculate_asr_adversarial_transcript_sha256(
            GENERATED
        )
    )

    wer = normalized["wer"]
    cer = normalized["cer"]

    assert wer["metric_key"] == "asr.wer.normalized-basic"
    assert wer["metric_version"] == "1.0.0"
    assert wer["evaluator_key"] == (
        "hetren.asr.wer.normalized-basic"
    )
    assert wer["evaluator_version"] == "1.0.0"

    assert cer["metric_key"] == "asr.cer.normalized-basic"
    assert cer["metric_version"] == "1.0.0"
    assert cer["evaluator_key"] == (
        "hetren.asr.cer.normalized-basic"
    )
    assert cer["evaluator_version"] == "1.0.0"

    assert wer["value"] == pytest.approx(0.5)
    assert cer["value"] == pytest.approx(
        0.34285714285714286
    )


def test_existing_semantic_and_child_execution_evidence_are_preserved():
    result = _result()

    payload = _completed_result_payload(
        result,
        bundle=_bundle(),
    )

    assert payload["semantic_observations"] == {
        "critical_number": [],
        "critical_identifier": [],
        "critical_terminology": [],
    }

    assert payload["execution_evidence"] == {
        "payload": result.execution_evidence.payload,
        "sha256": result.execution_evidence.sha256,
    }


def test_completed_result_fails_closed_for_unknown_suite_case():
    with pytest.raises(
        ASRBrutalExecutionRunnerError,
        match="does not map to exactly one suite case",
    ):
        _completed_result_payload(
            _result(case_id="unknown.case"),
            bundle=_bundle(case_id="case.one"),
        )
