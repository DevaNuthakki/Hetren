from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from app.adversarial_asr_campaign_service import (
    ASRAdversarialCampaignCancelledError,
    ASRAdversarialCampaignCaseTimedOutError,
    ASRAdversarialCampaignServiceError,
    CANCELLED_DETAIL,
    FAILED_DETAIL,
    INVALID_DETAIL,
    MISSING_AUDIO_DETAIL,
    TIMED_OUT_DETAIL,
    execute_asr_adversarial_campaign,
)
from app.adversarial_asr_execution_service import (
    execute_asr_adversarial_case,
)
from app.speech import (
    TranscriptionError,
    TranscriptionResult,
)
from hvee.core.contracts import HveeContractError
from hvee.packs.asr import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCase,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialCondition,
    ASRAdversarialDurationBucket,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialExecutionStatus,
    ASRAdversarialLongContextPosition,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSemanticLoad,
    ASRAdversarialSpeakingRate,
    ASRAdversarialSuiteDefinition,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
    build_asr_adversarial_evidence_v1,
    calculate_asr_adversarial_evidence_sha256,
)


MODEL = "large-v3-turbo"
AUDIO_A = b"campaign-audio-a"
AUDIO_B = b"campaign-audio-b"

REFERENCE_A = (
    "Take 250 mg using confirmation code AB-123."
)
REFERENCE_B = (
    "Take 500 mg using confirmation code XY-456."
)


def _sha_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _condition():
    return ASRAdversarialCondition(
        channel=(
            ASRAdversarialChannel
            .TELEPHONY
        ),
        codec=(
            ASRAdversarialCodec
            .MULAW
        ),
        sample_rate_hz=8_000,
        microphone_class="headset",
        noise=(
            ASRAdversarialNoiseCondition
            .MODERATE
        ),
        speaking_rate=(
            ASRAdversarialSpeakingRate
            .FAST
        ),
        speech_variety_key=(
            "declared.campaign-fixture"
        ),
        overlap=(
            ASRAdversarialOverlapCondition
            .NONE
        ),
        duration=(
            ASRAdversarialDurationBucket
            .SHORT
        ),
    )


def _load():
    return ASRAdversarialSemanticLoad(
        critical_number_count=1,
        critical_identifier_count=1,
        critical_terminology_count=0,
        spoken_number_variation=False,
        multiple_critical_items=True,
        duplicate_critical_items=False,
        ordering_challenge=False,
        long_context_position=(
            ASRAdversarialLongContextPosition
            .NONE
        ),
    )


def _suite():
    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(
            ASRAdversarialCase(
                case_id="qualification.case-a",
                audio_asset_sha256=(
                    _sha_bytes(AUDIO_A)
                ),
                reference_transcript=(
                    REFERENCE_A
                ),
                condition=_condition(),
                semantic_load=_load(),
                description=(
                    "Campaign service fixture A."
                ),
                tags=("campaign",),
            ),
            ASRAdversarialCase(
                case_id="qualification.case-b",
                audio_asset_sha256=(
                    _sha_bytes(AUDIO_B)
                ),
                reference_transcript=(
                    REFERENCE_B
                ),
                condition=_condition(),
                semantic_load=_load(),
                description=(
                    "Campaign service fixture B."
                ),
                tags=("campaign",),
            ),
        ),
    )

    return (
        suite,
        build_asr_adversarial_evidence_v1(
            suite
        ),
    )


def _terminology():
    return ASRAdversarialTerminologyBinding(
        state=(
            ASRAdversarialTerminologyState
            .NOT_CONFIGURED
        ),
    )


def _audio_paths(
    tmp_path: Path,
):
    first = tmp_path / "case-a.wav"
    second = tmp_path / "case-b.wav"

    first.write_bytes(
        AUDIO_A
    )
    second.write_bytes(
        AUDIO_B
    )

    return {
        "qualification.case-a": first,
        "qualification.case-b": second,
    }


class RecordingProvider:
    provider_name = "test_provider"

    def __init__(
        self,
        *,
        failure_on_call: int | None = None,
        sensitive_message: str = (
            "sensitive provider failure"
        ),
    ):
        self.failure_on_call = (
            failure_on_call
        )
        self.sensitive_message = (
            sensitive_message
        )
        self.calls: list[
            dict[str, object]
        ] = []

    def transcribe(
        self,
        audio_path,
        model_name=None,
    ):
        path = Path(
            audio_path
        )

        self.calls.append(
            {
                "audio_path": path,
                "model_name": model_name,
            }
        )

        if (
            self.failure_on_call
            == len(self.calls)
        ):
            raise TranscriptionError(
                self.sensitive_message
            )

        content = path.read_bytes()

        if content == AUDIO_A:
            transcript = REFERENCE_A
        elif content == AUDIO_B:
            transcript = REFERENCE_B
        else:
            transcript = (
                "unexpected audio"
            )

        return TranscriptionResult(
            transcript=transcript,
            provider=self.provider_name,
            model_name=(
                model_name
                or MODEL
            ),
            device=None,
            compute_type=None,
        )


class RecordingStopEvent:
    def __init__(
        self,
        *,
        initially_set: bool = False,
    ):
        self.value = initially_set

    def is_set(self):
        return self.value

    def set(self):
        self.value = True


def _execute(
    *,
    tmp_path: Path,
    provider=None,
    audio_paths=None,
    stop_event=None,
    case_executor=(
        execute_asr_adversarial_case
    ),
):
    suite, suite_evidence = _suite()

    return execute_asr_adversarial_campaign(
        campaign_id=(
            "qualification.campaign-one"
        ),
        campaign_version="1.0.0",
        audio_paths=(
            audio_paths
            if audio_paths is not None
            else _audio_paths(tmp_path)
        ),
        requested_model_name=MODEL,
        provider=(
            provider
            if provider is not None
            else RecordingProvider()
        ),
        terminology=_terminology(),
        suite=suite,
        suite_evidence=suite_evidence,
        stop_event=stop_event,
        case_executor=case_executor,
    )


def test_executes_all_cases_in_sealed_suite_order(
    tmp_path: Path,
):
    provider = RecordingProvider()
    paths = _audio_paths(
        tmp_path
    )

    reversed_paths = {
        "qualification.case-b": (
            paths[
                "qualification.case-b"
            ]
        ),
        "qualification.case-a": (
            paths[
                "qualification.case-a"
            ]
        ),
    }

    result = _execute(
        tmp_path=tmp_path,
        provider=provider,
        audio_paths=reversed_paths,
    )

    assert [
        call["audio_path"].name
        for call in provider.calls
    ] == [
        "case-a.wav",
        "case-b.wav",
    ]

    assert [
        attempt.case_id
        for attempt in result.attempts
    ] == [
        "qualification.case-a",
        "qualification.case-b",
    ]

    assert all(
        attempt.status
        == ASRAdversarialExecutionStatus.COMPLETED
        for attempt in result.attempts
    )

    assert len(
        result.completed_results
    ) == 2


def test_completed_campaign_binds_slice_b_evidence(
    tmp_path: Path,
):
    result = _execute(
        tmp_path=tmp_path,
    )

    campaign = result.evidence.payload[
        "campaign"
    ]

    assert campaign[
        "status_counts"
    ] == {
        "completed": 2,
        "failed": 0,
        "timed_out": 0,
        "cancelled": 0,
        "invalid": 0,
    }

    for attempt_payload, attempt in zip(
        campaign["attempts"],
        result.attempts,
        strict=True,
    ):
        assert (
            attempt_payload[
                "execution_evidence_sha256"
            ]
            == attempt.execution_evidence.sha256
        )


def test_execution_ids_are_deterministic(
    tmp_path: Path,
):
    result = _execute(
        tmp_path=tmp_path,
    )

    assert [
        attempt.execution_id
        for attempt in result.attempts
    ] == [
        (
            "qualification.campaign-one."
            "qualification.case-a"
        ),
        (
            "qualification.campaign-one."
            "qualification.case-b"
        ),
    ]


def test_provider_failure_becomes_failed_and_campaign_continues(
    tmp_path: Path,
):
    provider = RecordingProvider(
        failure_on_call=1,
    )

    result = _execute(
        tmp_path=tmp_path,
        provider=provider,
    )

    assert [
        attempt.status
        for attempt in result.attempts
    ] == [
        ASRAdversarialExecutionStatus.FAILED,
        ASRAdversarialExecutionStatus.COMPLETED,
    ]

    assert result.attempts[
        0
    ].status_detail == FAILED_DETAIL

    assert (
        result.attempts[0]
        .execution_evidence
        is None
    )

    assert len(provider.calls) == 2


def test_provider_failure_detail_does_not_leak_into_campaign(
    tmp_path: Path,
):
    sensitive = (
        "secret provider token ABC-123"
    )

    result = _execute(
        tmp_path=tmp_path,
        provider=RecordingProvider(
            failure_on_call=1,
            sensitive_message=sensitive,
        ),
    )

    serialized = str(
        result.evidence.payload
    )

    assert sensitive not in serialized
    assert FAILED_DETAIL in serialized


def test_tampered_audio_becomes_invalid_and_campaign_continues(
    tmp_path: Path,
):
    paths = _audio_paths(
        tmp_path
    )

    paths[
        "qualification.case-a"
    ].write_bytes(
        b"tampered"
    )

    provider = RecordingProvider()

    result = _execute(
        tmp_path=tmp_path,
        provider=provider,
        audio_paths=paths,
    )

    assert [
        attempt.status
        for attempt in result.attempts
    ] == [
        ASRAdversarialExecutionStatus.INVALID,
        ASRAdversarialExecutionStatus.COMPLETED,
    ]

    assert (
        result.attempts[0].status_detail
        == INVALID_DETAIL
    )

    # Slice D rejects the tampered first case before
    # provider inference, so only case B reaches ASR.
    assert len(provider.calls) == 1


def test_missing_audio_becomes_invalid_without_provider_call(
    tmp_path: Path,
):
    paths = _audio_paths(
        tmp_path
    )

    paths.pop(
        "qualification.case-a"
    )

    provider = RecordingProvider()

    result = _execute(
        tmp_path=tmp_path,
        provider=provider,
        audio_paths=paths,
    )

    assert result.attempts[
        0
    ].status == (
        ASRAdversarialExecutionStatus.INVALID
    )

    assert (
        result.attempts[0].status_detail
        == MISSING_AUDIO_DETAIL
    )

    assert len(provider.calls) == 1


def test_undeclared_audio_mapping_key_is_rejected_before_provider(
    tmp_path: Path,
):
    paths = _audio_paths(
        tmp_path
    )

    paths[
        "qualification.case-z"
    ] = tmp_path / "extra.wav"

    provider = RecordingProvider()

    with pytest.raises(
        ASRAdversarialCampaignServiceError,
        match="undeclared suite cases",
    ):
        _execute(
            tmp_path=tmp_path,
            provider=provider,
            audio_paths=paths,
        )

    assert provider.calls == []


def test_typed_case_timeout_becomes_timed_out_and_continues(
    tmp_path: Path,
):
    calls = []

    def executor(**kwargs):
        calls.append(
            kwargs["case_id"]
        )

        if (
            kwargs["case_id"]
            == "qualification.case-a"
        ):
            raise (
                ASRAdversarialCampaignCaseTimedOutError(
                    "internal timeout detail"
                )
            )

        return execute_asr_adversarial_case(
            **kwargs
        )

    result = _execute(
        tmp_path=tmp_path,
        case_executor=executor,
    )

    assert [
        attempt.status
        for attempt in result.attempts
    ] == [
        ASRAdversarialExecutionStatus.TIMED_OUT,
        ASRAdversarialExecutionStatus.COMPLETED,
    ]

    assert (
        result.attempts[0].status_detail
        == TIMED_OUT_DETAIL
    )

    assert calls == [
        "qualification.case-a",
        "qualification.case-b",
    ]


def test_typed_cancellation_cancels_current_and_remaining_cases(
    tmp_path: Path,
):
    calls = []

    def executor(**kwargs):
        calls.append(
            kwargs["case_id"]
        )

        raise (
            ASRAdversarialCampaignCancelledError(
                "internal cancellation detail"
            )
        )

    result = _execute(
        tmp_path=tmp_path,
        case_executor=executor,
    )

    assert [
        attempt.status
        for attempt in result.attempts
    ] == [
        ASRAdversarialExecutionStatus.CANCELLED,
        ASRAdversarialExecutionStatus.CANCELLED,
    ]

    assert calls == [
        "qualification.case-a"
    ]

    assert all(
        attempt.status_detail
        == CANCELLED_DETAIL
        for attempt in result.attempts
    )


def test_preexisting_stop_signal_cancels_all_without_execution(
    tmp_path: Path,
):
    stop = RecordingStopEvent(
        initially_set=True
    )

    calls = []

    def executor(**kwargs):
        calls.append(
            kwargs
        )
        raise AssertionError(
            "Executor must not run."
        )

    result = _execute(
        tmp_path=tmp_path,
        stop_event=stop,
        case_executor=executor,
    )

    assert calls == []

    assert all(
        attempt.status
        == ASRAdversarialExecutionStatus.CANCELLED
        for attempt in result.attempts
    )


def test_late_stop_discards_success_and_cancels_remaining(
    tmp_path: Path,
):
    stop = RecordingStopEvent()
    calls = []

    def executor(**kwargs):
        calls.append(
            kwargs["case_id"]
        )

        result = (
            execute_asr_adversarial_case(
                **kwargs
            )
        )

        stop.set()
        return result

    result = _execute(
        tmp_path=tmp_path,
        stop_event=stop,
        case_executor=executor,
    )

    assert calls == [
        "qualification.case-a"
    ]

    assert [
        attempt.status
        for attempt in result.attempts
    ] == [
        ASRAdversarialExecutionStatus.CANCELLED,
        ASRAdversarialExecutionStatus.CANCELLED,
    ]

    assert (
        result.completed_results
        == ()
    )


def test_cancellation_takes_precedence_over_provider_failure(
    tmp_path: Path,
):
    stop = RecordingStopEvent()

    def executor(**_kwargs):
        stop.set()

        raise TranscriptionError(
            "provider stopped"
        )

    result = _execute(
        tmp_path=tmp_path,
        stop_event=stop,
        case_executor=executor,
    )

    assert all(
        attempt.status
        == ASRAdversarialExecutionStatus.CANCELLED
        for attempt in result.attempts
    )


def test_cancellation_takes_precedence_over_timeout_signal(
    tmp_path: Path,
):
    stop = RecordingStopEvent()

    def executor(**_kwargs):
        stop.set()

        raise (
            ASRAdversarialCampaignCaseTimedOutError(
                "timeout"
            )
        )

    result = _execute(
        tmp_path=tmp_path,
        stop_event=stop,
        case_executor=executor,
    )

    assert all(
        attempt.status
        == ASRAdversarialExecutionStatus.CANCELLED
        for attempt in result.attempts
    )


def test_unexpected_runtime_error_is_not_swallowed(
    tmp_path: Path,
):
    def executor(**_kwargs):
        raise RuntimeError(
            "programming defect"
        )

    with pytest.raises(
        RuntimeError,
        match="programming defect",
    ):
        _execute(
            tmp_path=tmp_path,
            case_executor=executor,
        )


def test_unexpected_assertion_error_is_not_swallowed(
    tmp_path: Path,
):
    def executor(**_kwargs):
        raise AssertionError(
            "unexpected defect"
        )

    with pytest.raises(
        AssertionError,
        match="unexpected defect",
    ):
        _execute(
            tmp_path=tmp_path,
            case_executor=executor,
        )


def test_rehashed_suite_tampering_escapes_as_contract_failure(
    tmp_path: Path,
):
    suite, suite_evidence = _suite()

    tampered = copy.deepcopy(
        suite_evidence.payload
    )

    tampered["scientific_boundary"][
        "production_qualified"
    ] = True

    tampered_bundle = (
        ASRAdversarialEvidenceBundle(
            payload=tampered,
            sha256=(
                calculate_asr_adversarial_evidence_sha256(
                    tampered
                )
            ),
        )
    )

    provider = RecordingProvider()

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        execute_asr_adversarial_campaign(
            campaign_id=(
                "qualification.campaign-one"
            ),
            campaign_version="1.0.0",
            audio_paths=_audio_paths(
                tmp_path
            ),
            requested_model_name=MODEL,
            provider=provider,
            terminology=_terminology(),
            suite=suite,
            suite_evidence=(
                tampered_bundle
            ),
        )

    assert provider.calls == []


def test_empty_provider_identity_is_rejected_before_execution(
    tmp_path: Path,
):
    class InvalidProvider:
        provider_name = " "

    with pytest.raises(
        ASRAdversarialCampaignServiceError,
        match="campaign ASR provider",
    ):
        _execute(
            tmp_path=tmp_path,
            provider=InvalidProvider(),
        )


def test_empty_model_is_rejected_before_execution(
    tmp_path: Path,
):
    suite, suite_evidence = _suite()
    provider = RecordingProvider()

    with pytest.raises(
        ASRAdversarialCampaignServiceError,
        match="requested ASR model",
    ):
        execute_asr_adversarial_campaign(
            campaign_id=(
                "qualification.campaign-one"
            ),
            campaign_version="1.0.0",
            audio_paths=_audio_paths(
                tmp_path
            ),
            requested_model_name=" ",
            provider=provider,
            terminology=_terminology(),
            suite=suite,
            suite_evidence=suite_evidence,
        )

    assert provider.calls == []


def test_invalid_stop_event_is_rejected(
    tmp_path: Path,
):
    with pytest.raises(
        ASRAdversarialCampaignServiceError,
        match="stop event is invalid",
    ):
        _execute(
            tmp_path=tmp_path,
            stop_event=object(),
        )


def test_invalid_case_executor_result_is_rejected(
    tmp_path: Path,
):
    def executor(**_kwargs):
        return {
            "not": "a Slice D result",
        }

    with pytest.raises(
        ASRAdversarialCampaignServiceError,
        match="invalid result",
    ):
        _execute(
            tmp_path=tmp_path,
            case_executor=executor,
        )


def test_campaign_evidence_retains_every_case_after_mixed_outcomes(
    tmp_path: Path,
):
    calls = []

    def executor(**kwargs):
        case_id = kwargs[
            "case_id"
        ]
        calls.append(
            case_id
        )

        if (
            case_id
            == "qualification.case-a"
        ):
            raise TranscriptionError(
                "failure"
            )

        return execute_asr_adversarial_case(
            **kwargs
        )

    result = _execute(
        tmp_path=tmp_path,
        case_executor=executor,
    )

    coverage = (
        result.evidence.payload[
            "campaign"
        ]["coverage"]
    )

    assert coverage[
        "coverage_complete"
    ] is True

    assert coverage[
        "expected_case_ids"
    ] == [
        "qualification.case-a",
        "qualification.case-b",
    ]

    assert coverage[
        "recorded_case_ids"
    ] == [
        "qualification.case-a",
        "qualification.case-b",
    ]


def test_campaign_service_has_no_qualification_authority(
    tmp_path: Path,
):
    result = _execute(
        tmp_path=tmp_path,
    )

    boundary = (
        result.evidence.payload[
            "scientific_boundary"
        ]
    )

    assert (
        boundary[
            "development_evidence_only"
        ]
        is True
    )

    assert (
        boundary[
            "qualification_threshold_applied"
        ]
        is False
    )

    assert (
        boundary[
            "certification_issued"
        ]
        is False
    )

    assert (
        boundary[
            "production_qualified"
        ]
        is False
    )

    assert (
        boundary[
            "release_enforcement_eligible"
        ]
        is False
    )


def test_wrong_case_identity_from_executor_is_rejected(
    tmp_path: Path,
):
    def executor(**kwargs):
        result = execute_asr_adversarial_case(
            **kwargs
        )

        return replace(
            result,
            case_id="qualification.case-b",
        )

    with pytest.raises(
        ASRAdversarialCampaignServiceError,
        match="wrong case identity",
    ):
        _execute(
            tmp_path=tmp_path,
            case_executor=executor,
        )


def test_hvee_contract_error_from_case_executor_is_not_swallowed(
    tmp_path: Path,
):
    def executor(**_kwargs):
        raise HveeContractError(
            "unexpected evaluator contract defect"
        )

    with pytest.raises(
        HveeContractError,
        match="unexpected evaluator contract defect",
    ):
        _execute(
            tmp_path=tmp_path,
            case_executor=executor,
        )


def test_cancellation_between_cases_preserves_completed_case(
    tmp_path: Path,
):
    class SequencedStopEvent:
        def __init__(self):
            self.calls = 0

        def is_set(self):
            self.calls += 1

            # Case A pre-check: False
            # Case A late-check: False
            # Case B pre-check: True
            return self.calls >= 3

    stop = SequencedStopEvent()

    result = _execute(
        tmp_path=tmp_path,
        stop_event=stop,
    )

    assert [
        attempt.status
        for attempt in result.attempts
    ] == [
        ASRAdversarialExecutionStatus.COMPLETED,
        ASRAdversarialExecutionStatus.CANCELLED,
    ]

    assert len(
        result.completed_results
    ) == 1

    assert (
        result.completed_results[0].case_id
        == "qualification.case-a"
    )

    assert (
        result.attempts[1].execution_evidence
        is None
    )
