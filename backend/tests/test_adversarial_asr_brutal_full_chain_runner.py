from __future__ import annotations

import hashlib
import wave
from pathlib import Path
from types import MappingProxyType

import pytest

import app.adversarial_asr_brutal_full_chain_runner as runner
from app.adversarial_asr_brutal_campaign import (
    ASRBrutalValidationSuiteBundle,
    build_asr_brutal_validation_suite_v1,
)
from app.adversarial_asr_brutal_execution_runner import (
    ASR_BRUTAL_FROZEN_MODELS_V1,
)
from app.speech import TranscriptionResult
from hvee.core.counterexample_contract_promotion import (
    RegressionContractDefinition,
    build_counterexample_contract_proposal_bundle,
)
from hvee.packs.asr.adversarial_execution_evidence import (
    calculate_asr_adversarial_execution_evidence_sha256,
)


_METRICS = {
    "critical_number": (
        "asr.critical-number.preserved.en-us",
        "1.0.0",
        "hetren.asr.critical-number-fidelity.en-us",
        "1.1.0",
    ),
    "critical_identifier": (
        "asr.critical-identifier.preserved.en-us",
        "1.0.0",
        "hetren.asr.critical-identifier-fidelity.en-us",
        "1.0.0",
    ),
    "critical_terminology": (
        "asr.critical-terminology.preserved.en-us",
        "1.0.0",
        "hetren.asr.critical-terminology-fidelity.en-us",
        "1.0.0",
    ),
}


def _bundle(audio_paths=None):
    suite, evidence = build_asr_brutal_validation_suite_v1()
    return ASRBrutalValidationSuiteBundle(
        suite=suite,
        suite_evidence=evidence,
        audio_paths=MappingProxyType(audio_paths or {}),
    )


def _preserved(dimension: str, value: bool):
    metric_key, metric_version, evaluator_key, evaluator_version = (
        _METRICS[dimension]
    )
    return {
        "metric_key": metric_key,
        "metric_version": metric_version,
        "evaluator_key": evaluator_key,
        "evaluator_version": evaluator_version,
        "evaluation_type": "asr",
        "status": "success",
        "value_type": "boolean",
        "value": value,
        "status_detail": None,
    }


def _result(
    *,
    role: str,
    case,
    identifier_preserved: bool = True,
    audio_sha256: str | None = None,
    audio_byte_length: int = 123,
):
    semantic = {
        "critical_number": [
            _preserved("critical_number", True)
        ],
        "critical_identifier": [
            _preserved(
                "critical_identifier",
                identifier_preserved,
            )
        ],
        "critical_terminology": [
            _preserved("critical_terminology", True)
        ],
    }
    child_payload = {
        "schema_version": 1,
        "type": "test_child_execution_evidence",
        "role": role,
        "case_id": case.case_id,
    }
    child_sha256 = (
        calculate_asr_adversarial_execution_evidence_sha256(
            child_payload
        )
    )
    generated = case.reference_transcript
    if not identifier_preserved:
        generated = (
            "Administer 5 mg at 9.15 am. "
            "Confirmation code AD7K92."
        )
    return {
        "case_id": case.case_id,
        "audio_asset_sha256": audio_sha256 or case.audio_asset_sha256,
        "audio_byte_length": audio_byte_length,
        "generated_transcript": generated,
        "normalized_error_evidence": {
            "wer": {"status": "success", "value": 0.0},
            "cer": {"status": "success", "value": 0.0},
        },
        "environment": {
            "provider": "faster_whisper",
            "model_name": (
                "small.en" if role == "baseline" else "large-v3-turbo"
            ),
            "device": "cpu",
            "compute_type": "int8_float32",
        },
        "semantic_observations": semantic,
        "execution_evidence": {
            "payload": child_payload,
            "sha256": child_sha256,
        },
    }


def _campaigns(*, severe_identifier_preserved=False):
    bundle = _bundle()
    campaigns = {}
    for role in ("baseline", "candidate"):
        results = []
        for case in bundle.suite.cases:
            results.append(
                _result(
                    role=role,
                    case=case,
                    identifier_preserved=(
                        severe_identifier_preserved
                        if role == "candidate"
                        and case.case_id
                        == runner._PRIMARY_COUNTEREXAMPLE_CASE_ID
                        else True
                    ),
                )
            )
        campaigns[role] = {"completed_results": results}
    return bundle, campaigns


def test_execution_backed_cross_stage_chain_is_terminal_and_unpromoted():
    bundle, campaigns = _campaigns()
    fidelity, evaluations = runner._critical_fidelity_evidence(
        campaigns
    )
    assert len(fidelity["records"]) == 26
    assert evaluations[
        ("candidate", runner._PRIMARY_COUNTEREXAMPLE_CASE_ID)
    ].verdict.value == "fail"

    inventory, counterexamples = runner._counterexample_inventory(
        bundle=bundle,
        evaluations=evaluations,
    )
    assert inventory["primary_case_id"] == (
        runner._PRIMARY_COUNTEREXAMPLE_CASE_ID
    )
    primary = counterexamples[
        runner._PRIMARY_COUNTEREXAMPLE_CASE_ID
    ]

    search = runner._adaptive_search(
        bundle=bundle,
        evaluations=evaluations,
        counterexamples=counterexamples,
    )
    assert search.payload["search"]["status"] == "boundary_bracketed"
    assert search.observed_boundary is not None

    reduction = runner._minimal_reduction(
        bundle=bundle,
        evaluations=evaluations,
        primary=primary,
    )
    assert reduction.payload["reduction"]["status"] == "one_minimal"
    assert reduction.payload["outcome"][
        "one_minimal_within_declared_units"
    ] is True

    neighborhood = runner._neighborhood(
        bundle=bundle,
        evaluations=evaluations,
        counterexamples=counterexamples,
        primary=primary,
        reduction=reduction,
    )
    assert neighborhood.payload["neighborhood"]["status"] == "complete"
    assert neighborhood.payload["outcome"][
        "declared_neighborhood_fully_observed"
    ] is True

    proposal = build_counterexample_contract_proposal_bundle(
        definition=RegressionContractDefinition(
            key=(
                "hetren.asr.severe-noise-critical-identifier-regression"
            ),
            version="1.0.0",
            suite_key="hetren.asr.brutal-validation-regression-suite",
            suite_version="1.0.0",
        ),
        source_counterexample_payload=primary.payload,
        source_counterexample_sha256=primary.sha256,
        source_minimal_reduction_payload=reduction.payload,
        source_minimal_reduction_sha256=reduction.sha256,
        source_neighborhood_payload=neighborhood.payload,
        source_neighborhood_sha256=neighborhood.sha256,
    )
    assert proposal.payload["evidence_boundary"][
        "contract_promoted"
    ] is False
    assert proposal.payload["evidence_boundary"][
        "qualification_authority"
    ] is False


def test_chain_fails_closed_when_primary_counterexample_is_absent():
    bundle, campaigns = _campaigns(
        severe_identifier_preserved=True
    )
    _fidelity, evaluations = runner._critical_fidelity_evidence(
        campaigns
    )
    with pytest.raises(
        runner.ASRBrutalFullChainRunnerError,
        match="cannot be fabricated",
    ):
        runner._counterexample_inventory(
            bundle=bundle,
            evaluations=evaluations,
        )


def _write_wav(path: Path) -> bytes:
    with wave.open(str(path), "wb") as destination:
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(16_000)
        destination.writeframes(b"\x00\x00" * 1_600)
    return path.read_bytes()


class _ReplayProvider:
    provider_name = "faster_whisper"

    def __init__(self, transcript: str):
        self.transcript = transcript

    def transcribe(self, audio_path, model_name=None):
        assert Path(audio_path).is_file()
        return TranscriptionResult(
            transcript=self.transcript,
            provider="faster_whisper",
            model_name=str(model_name),
            device="cpu",
            compute_type="int8_float32",
        )


def test_incident_mode_executes_real_production_chain_with_live_adapter(
    monkeypatch,
    tmp_path: Path,
):
    audio_path = tmp_path / "severe.wav"
    audio_bytes = _write_wav(audio_path)
    audio_sha256 = hashlib.sha256(audio_bytes).hexdigest()

    base_bundle = _bundle()
    severe_case = next(
        case
        for case in base_bundle.suite.cases
        if case.case_id == runner._PRIMARY_COUNTEREXAMPLE_CASE_ID
    )
    bundle = ASRBrutalValidationSuiteBundle(
        suite=base_bundle.suite,
        suite_evidence=base_bundle.suite_evidence,
        audio_paths=MappingProxyType(
            {runner._PRIMARY_COUNTEREXAMPLE_CASE_ID: audio_path}
        ),
    )
    candidate_result = _result(
        role="candidate",
        case=severe_case,
        identifier_preserved=False,
        audio_sha256=audio_sha256,
        audio_byte_length=len(audio_bytes),
    )
    evaluation, _observation, _decision = (
        runner._critical_case_evaluation(
            role="candidate",
            result=candidate_result,
            required_dimensions=(
                "critical_number",
                "critical_identifier",
            ),
        )
    )
    primary = runner.build_counterexample_evidence_bundle(
        evaluation_type="asr",
        scenario_key="hetren.asr.brutal-validation-case",
        scenario_version="1.0.0",
        case_id=evaluation.case_id,
        parameters=runner._scenario_parameters(
            bundle=bundle,
            evaluation=evaluation,
        ),
        result_provenance_sha256=(
            evaluation.result_provenance_sha256
        ),
        observation_evidence_sha256=(
            evaluation.observation_evidence_sha256
        ),
        decision_evidence_sha256=evaluation.decision_evidence_sha256,
        failures=evaluation.failures,
    )
    candidate_model = next(
        model
        for model in ASR_BRUTAL_FROZEN_MODELS_V1
        if model.role == "candidate"
    )
    identity = {
        "role": candidate_model.role,
        "model_name": candidate_model.model_name,
        "repository": candidate_model.repository,
        "revision": candidate_model.revision,
        "model_binary_sha256": candidate_model.model_binary_sha256,
        "model_binary_bytes": candidate_model.model_binary_bytes,
        "resolved_offline": True,
    }

    monkeypatch.setattr(
        runner.importlib.metadata,
        "version",
        lambda _package: "1.1.0",
    )

    incident = runner._incident_chain(
        bundle=bundle,
        evaluation=evaluation,
        primary=primary,
        candidate_model_identity=identity,
        repository_commit="1" * 40,
        source_code_sha256="2" * 64,
        execution_summary_sha256="3" * 64,
        operator_authorization_sha256="4" * 64,
        provider_factory=lambda *_args, **_kwargs: _ReplayProvider(
            evaluation.generated_transcript
        ),
    )

    assert incident["outcome"]["controlled_replay_executed"] is True
    assert incident["outcome"]["integration_verified"] is True
    assert incident["outcome"]["reproduction_verdict"] == (
        "indeterminate"
    )
    assert incident["evidence_boundary"][
        "governance_assurance_completed"
    ] is False
    assert incident["evidence_boundary"][
        "qualification_authority"
    ] is False
