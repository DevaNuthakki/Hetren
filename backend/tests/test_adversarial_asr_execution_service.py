from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from hvee.core.contracts import HveeContractError

from app.adversarial_asr_execution_service import (
    ASRAdversarialExecutionServiceError,
    execute_asr_adversarial_case,
)
from app.speech import (
    TranscriptionError,
    TranscriptionResult,
)
from hvee.packs.asr import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCase,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialCondition,
    ASRAdversarialDurationBucket,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialLongContextPosition,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSemanticLoad,
    ASRAdversarialSpeakingRate,
    ASRAdversarialSuiteDefinition,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
    ASRCriticalTerminologyProfile,
    ASRCriticalTerminologyTerm,
    build_asr_adversarial_evidence_v1,
    calculate_asr_adversarial_evidence_sha256,
    calculate_asr_adversarial_transcript_sha256,
)


AUDIO_BYTES = b"hetren-adversarial-audio-fixture"

REFERENCE = (
    "Administer Cardiovex 250 mg "
    "using confirmation code AB-123."
)


def _audio_sha256(
    value: bytes = AUDIO_BYTES,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _profile() -> ASRCriticalTerminologyProfile:
    return ASRCriticalTerminologyProfile(
        key="qualification.terminology-profile",
        version="1.0.0",
        language="en",
        locale="en-US",
        terms=(
            ASRCriticalTerminologyTerm(
                term_key="medication.cardiovex",
                canonical_text="Cardiovex",
                accepted_surfaces=(
                    "Cardiovex",
                ),
            ),
        ),
    )


def _terminology(
    *,
    configured: bool = True,
) -> ASRAdversarialTerminologyBinding:
    if not configured:
        return ASRAdversarialTerminologyBinding(
            state=(
                ASRAdversarialTerminologyState
                .NOT_CONFIGURED
            ),
        )

    return ASRAdversarialTerminologyBinding(
        state=(
            ASRAdversarialTerminologyState
            .CONFIGURED
        ),
        profile=_profile(),
    )


def _suite(
    *,
    terminology_count: int = 1,
):
    total = (
        1
        + 1
        + terminology_count
    )

    reference = (
        REFERENCE
        if terminology_count
        else (
            "Administer 250 mg using "
            "confirmation code AB-123."
        )
    )

    case = ASRAdversarialCase(
        case_id="qualification.case-one",
        audio_asset_sha256=(
            _audio_sha256()
        ),
        reference_transcript=reference,
        condition=ASRAdversarialCondition(
            channel=(
                ASRAdversarialChannel.TELEPHONY
            ),
            codec=ASRAdversarialCodec.MULAW,
            sample_rate_hz=8_000,
            microphone_class="headset",
            noise=(
                ASRAdversarialNoiseCondition
                .MODERATE
            ),
            speaking_rate=(
                ASRAdversarialSpeakingRate.FAST
            ),
            speech_variety_key=(
                "declared.fixture-a"
            ),
            overlap=(
                ASRAdversarialOverlapCondition
                .NONE
            ),
            duration=(
                ASRAdversarialDurationBucket
                .SHORT
            ),
        ),
        semantic_load=ASRAdversarialSemanticLoad(
            critical_number_count=1,
            critical_identifier_count=1,
            critical_terminology_count=(
                terminology_count
            ),
            spoken_number_variation=False,
            multiple_critical_items=(
                total > 1
            ),
            duplicate_critical_items=False,
            ordering_challenge=False,
            long_context_position=(
                ASRAdversarialLongContextPosition
                .NONE
            ),
        ),
        description=(
            "Application execution fixture."
        ),
        tags=(
            "asr",
            "telephony",
        ),
    )

    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(case,),
    )

    return (
        suite,
        build_asr_adversarial_evidence_v1(
            suite
        ),
    )


def _audio_file(
    tmp_path: Path,
) -> Path:
    path = (
        tmp_path
        / "qualification-case.wav"
    )

    path.write_bytes(
        AUDIO_BYTES
    )

    return path


class RecordingProvider:
    provider_name = "test_provider"

    def __init__(
        self,
        *,
        transcript: str = REFERENCE,
        returned_provider: str | None = None,
        returned_model: str | None = None,
        device: str | None = "CPU",
        compute_type: str | None = "INT8",
        failure: Exception | None = None,
        mutate_audio: bool = False,
    ):
        self.transcript = transcript
        self.returned_provider = (
            returned_provider
        )
        self.returned_model = returned_model
        self.device = device
        self.compute_type = compute_type
        self.failure = failure
        self.mutate_audio = mutate_audio
        self.calls: list[
            dict[str, object]
        ] = []

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ) -> TranscriptionResult:
        path = Path(
            audio_path
        )

        self.calls.append(
            {
                "audio_path": path,
                "model_name": model_name,
            }
        )

        if self.failure is not None:
            raise self.failure

        if self.mutate_audio:
            # Keep the exact original byte length so this
            # specifically proves SHA-256 detects mutation.
            path.write_bytes(
                b"x" * len(AUDIO_BYTES)
            )

        return TranscriptionResult(
            transcript=self.transcript,
            provider=(
                self.returned_provider
                if self.returned_provider
                is not None
                else self.provider_name
            ),
            model_name=(
                self.returned_model
                if self.returned_model
                is not None
                else (
                    model_name
                    or "missing-model"
                )
            ),
            device=self.device,
            compute_type=(
                self.compute_type
            ),
        )


def _execute(
    *,
    tmp_path: Path,
    provider: RecordingProvider | None = None,
    terminology_count: int = 1,
    terminology_configured: bool = True,
):
    suite, evidence = _suite(
        terminology_count=(
            terminology_count
        )
    )

    selected_provider = (
        provider
        if provider is not None
        else RecordingProvider()
    )

    return execute_asr_adversarial_case(
        execution_id=(
            "qualification.execution-one"
        ),
        case_id="qualification.case-one",
        audio_path=_audio_file(
            tmp_path
        ),
        requested_model_name=(
            "large-v3-turbo"
        ),
        provider=selected_provider,
        terminology=_terminology(
            configured=(
                terminology_configured
            )
        ),
        suite=suite,
        suite_evidence=evidence,
    )


def test_executes_provider_semantics_and_evidence(
    tmp_path: Path,
):
    provider = RecordingProvider()

    result = _execute(
        tmp_path=tmp_path,
        provider=provider,
    )

    assert len(provider.calls) == 1

    assert provider.calls[0][
        "model_name"
    ] == "large-v3-turbo"

    assert (
        result.audio_asset_sha256
        == _audio_sha256()
    )
    assert (
        result.audio_byte_length
        == len(AUDIO_BYTES)
    )

    assert result.generated_transcript == (
        REFERENCE
    )

    assert (
        len(
            result.semantic_observations
            .critical_number
        )
        == 10
    )
    assert (
        len(
            result.semantic_observations
            .critical_identifier
        )
        == 11
    )
    assert (
        len(
            result.semantic_observations
            .critical_terminology
        )
        == 11
    )

    assert (
        result.execution_definition
        .execution_environment_sha256
        == result.environment.sha256
    )

    assert (
        result.execution_definition
        .generated_transcript_sha256
        == calculate_asr_adversarial_transcript_sha256(
            REFERENCE
        )
    )

    assert (
        result.execution_evidence.payload[
            "execution"
        ]["status"]
        == "completed"
    )


def test_environment_uses_observed_runtime_identity(
    tmp_path: Path,
):
    result = _execute(
        tmp_path=tmp_path,
        provider=RecordingProvider(
            device=" CUDA ",
            compute_type=" FLOAT16 ",
        ),
    )

    assert (
        result.environment.provider
        == "test_provider"
    )
    assert (
        result.environment.model_name
        == "large-v3-turbo"
    )
    assert result.environment.device == (
        "cuda"
    )
    assert (
        result.environment.compute_type
        == "float16"
    )

    assert result.environment.payload[
        "execution_config"
    ] == {
        "provider": "test_provider",
        "model_name": (
            "large-v3-turbo"
        ),
        "device": "cuda",
        "compute_type": "float16",
    }


def test_unknown_runtime_fields_remain_unknown(
    tmp_path: Path,
):
    result = _execute(
        tmp_path=tmp_path,
        provider=RecordingProvider(
            device=None,
            compute_type=None,
        ),
    )

    assert (
        result.environment.device
        is None
    )
    assert (
        result.environment.compute_type
        is None
    )


def test_generated_transcript_is_normalized_before_semantics_and_commitment(
    tmp_path: Path,
):
    provider = RecordingProvider(
        transcript=(
            "  "
            + REFERENCE
            + "  "
        ),
    )

    result = _execute(
        tmp_path=tmp_path,
        provider=provider,
    )

    assert (
        result.generated_transcript
        == REFERENCE
    )

    assert (
        result.execution_definition
        .generated_transcript_sha256
        == calculate_asr_adversarial_transcript_sha256(
            REFERENCE
        )
    )


def test_audio_hash_mismatch_fails_before_provider(
    tmp_path: Path,
):
    suite, evidence = _suite()
    provider = RecordingProvider()

    audio = tmp_path / "wrong.wav"
    audio.write_bytes(
        b"different-audio"
    )

    with pytest.raises(
        ASRAdversarialExecutionServiceError,
        match="does not match the sealed case",
    ):
        execute_asr_adversarial_case(
            execution_id=(
                "qualification.execution-one"
            ),
            case_id=(
                "qualification.case-one"
            ),
            audio_path=audio,
            requested_model_name=(
                "large-v3-turbo"
            ),
            provider=provider,
            terminology=_terminology(),
            suite=suite,
            suite_evidence=evidence,
        )

    assert provider.calls == []


def test_audio_change_during_provider_execution_fails_closed(
    tmp_path: Path,
):
    provider = RecordingProvider(
        mutate_audio=True,
    )

    with pytest.raises(
        ASRAdversarialExecutionServiceError,
        match="changed during execution",
    ):
        _execute(
            tmp_path=tmp_path,
            provider=provider,
        )

    assert len(provider.calls) == 1


def test_provider_identity_mismatch_is_rejected(
    tmp_path: Path,
):
    with pytest.raises(
        ASRAdversarialExecutionServiceError,
        match="provider identity",
    ):
        _execute(
            tmp_path=tmp_path,
            provider=RecordingProvider(
                returned_provider=(
                    "different_provider"
                ),
            ),
        )


def test_model_identity_mismatch_is_rejected(
    tmp_path: Path,
):
    with pytest.raises(
        ASRAdversarialExecutionServiceError,
        match="model identity",
    ):
        _execute(
            tmp_path=tmp_path,
            provider=RecordingProvider(
                returned_model="small.en",
            ),
        )


def test_empty_provider_transcript_is_rejected(
    tmp_path: Path,
):
    with pytest.raises(
        ASRAdversarialExecutionServiceError,
        match="generated transcript",
    ):
        _execute(
            tmp_path=tmp_path,
            provider=RecordingProvider(
                transcript="   ",
            ),
        )


def test_provider_exception_propagates(
    tmp_path: Path,
):
    failure = TranscriptionError(
        "provider failed"
    )

    with pytest.raises(
        TranscriptionError,
        match="provider failed",
    ):
        _execute(
            tmp_path=tmp_path,
            provider=RecordingProvider(
                failure=failure,
            ),
        )


def test_case_reference_drives_semantic_evaluation(
    tmp_path: Path,
):
    result = _execute(
        tmp_path=tmp_path,
        provider=RecordingProvider(
            transcript=(
                "Administer Cardiovex 500 mg "
                "using confirmation code AB-123."
            ),
        ),
    )

    preserved = next(
        observation
        for observation
        in result.semantic_observations
        .critical_number
        if observation.metric_key
        == "asr.critical-number.preserved.en-us"
    )

    assert preserved.value is False


def test_not_configured_terminology_path(
    tmp_path: Path,
):
    result = _execute(
        tmp_path=tmp_path,
        provider=RecordingProvider(
            transcript=(
                "Administer 250 mg using "
                "confirmation code AB-123."
            ),
        ),
        terminology_count=0,
        terminology_configured=False,
    )

    assert (
        result.semantic_observations
        .critical_terminology
        == ()
    )

    configuration = (
        result.execution_evidence.payload[
            "semantic_configuration"
        ]["critical_terminology"]
    )

    assert configuration == {
        "state": "not_configured",
        "profile": None,
    }


def test_declared_terminology_requires_configuration_before_provider(
    tmp_path: Path,
):
    suite, evidence = _suite(
        terminology_count=1
    )
    provider = RecordingProvider()

    with pytest.raises(
        ASRAdversarialExecutionServiceError,
        match="requires a configured profile",
    ):
        execute_asr_adversarial_case(
            execution_id=(
                "qualification.execution-one"
            ),
            case_id=(
                "qualification.case-one"
            ),
            audio_path=_audio_file(
                tmp_path
            ),
            requested_model_name=(
                "large-v3-turbo"
            ),
            provider=provider,
            terminology=_terminology(
                configured=False
            ),
            suite=suite,
            suite_evidence=evidence,
        )

    assert provider.calls == []


def test_rehashed_suite_tampering_fails_before_provider(
    tmp_path: Path,
):
    suite, evidence = _suite()
    provider = RecordingProvider()

    tampered = copy.deepcopy(
        evidence.payload
    )

    tampered["scientific_boundary"][
        "production_qualified"
    ] = True

    tampered_evidence = (
        ASRAdversarialEvidenceBundle(
            payload=tampered,
            sha256=(
                calculate_asr_adversarial_evidence_sha256(
                    tampered
                )
            ),
        )
    )

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        execute_asr_adversarial_case(
            execution_id=(
                "qualification.execution-one"
            ),
            case_id=(
                "qualification.case-one"
            ),
            audio_path=_audio_file(
                tmp_path
            ),
            requested_model_name=(
                "large-v3-turbo"
            ),
            provider=provider,
            terminology=_terminology(),
            suite=suite,
            suite_evidence=(
                tampered_evidence
            ),
        )

    assert provider.calls == []


def test_environment_commitment_is_deterministic(
    tmp_path: Path,
):
    first = _execute(
        tmp_path=tmp_path,
    )

    second = _execute(
        tmp_path=tmp_path,
    )

    assert (
        first.environment.payload
        == second.environment.payload
    )
    assert (
        first.environment.sha256
        == second.environment.sha256
    )
