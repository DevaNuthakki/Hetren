from __future__ import annotations

import copy
import hashlib
from dataclasses import replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_campaign_evidence import (
    ASRAdversarialCampaignAttempt,
    ASRAdversarialCampaignDefinition,
    ASRAdversarialCampaignEvidenceBundle,
    build_asr_adversarial_campaign_evidence_v1,
    calculate_asr_adversarial_campaign_evidence_sha256,
    verify_asr_adversarial_campaign_evidence_v1,
)
from hvee.packs.asr.adversarial_evidence import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCase,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialCondition,
    ASRAdversarialDurationBucket,
    ASRAdversarialLongContextPosition,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSemanticLoad,
    ASRAdversarialSpeakingRate,
    ASRAdversarialSuiteDefinition,
    build_asr_adversarial_evidence_v1,
)
from hvee.packs.asr.adversarial_execution_evidence import (
    ASRAdversarialExecutionDefinition,
    ASRAdversarialExecutionEvidenceBundle,
    ASRAdversarialExecutionStatus,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
    build_asr_adversarial_execution_evidence_v1,
    calculate_asr_adversarial_execution_evidence_sha256,
    calculate_asr_adversarial_transcript_sha256,
)
from hvee.packs.asr.adversarial_semantic_execution import (
    evaluate_asr_adversarial_semantics,
)


MODEL = "large-v3-turbo"
PROVIDER = "test_provider"


def _sha(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _condition() -> ASRAdversarialCondition:
    return ASRAdversarialCondition(
        channel=ASRAdversarialChannel.TELEPHONY,
        codec=ASRAdversarialCodec.MULAW,
        sample_rate_hz=8_000,
        microphone_class="headset",
        noise=ASRAdversarialNoiseCondition.MODERATE,
        speaking_rate=ASRAdversarialSpeakingRate.FAST,
        speech_variety_key="declared.fixture-a",
        overlap=ASRAdversarialOverlapCondition.NONE,
        duration=ASRAdversarialDurationBucket.SHORT,
    )


def _semantic_load() -> ASRAdversarialSemanticLoad:
    return ASRAdversarialSemanticLoad(
        critical_number_count=1,
        critical_identifier_count=1,
        critical_terminology_count=0,
        spoken_number_variation=False,
        multiple_critical_items=True,
        duplicate_critical_items=False,
        ordering_challenge=False,
        long_context_position=(
            ASRAdversarialLongContextPosition.NONE
        ),
    )


def _case(
    *,
    case_id: str,
    audio_key: str,
    reference: str,
) -> ASRAdversarialCase:
    return ASRAdversarialCase(
        case_id=case_id,
        audio_asset_sha256=_sha(audio_key),
        reference_transcript=reference,
        condition=_condition(),
        semantic_load=_semantic_load(),
        description="Campaign evidence fixture.",
        tags=("campaign", "telephony"),
    )


def _suite():
    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(
            _case(
                case_id="qualification.case-a",
                audio_key="audio-a",
                reference=(
                    "Take 250 mg using confirmation "
                    "code AB-123."
                ),
            ),
            _case(
                case_id="qualification.case-b",
                audio_key="audio-b",
                reference=(
                    "Take 500 mg using confirmation "
                    "code XY-456."
                ),
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


def _completed_child(
    *,
    suite,
    suite_evidence,
    case_id: str = "qualification.case-a",
    execution_id: str = "qualification.execution-a",
    provider_key: str = PROVIDER,
    model_key: str = MODEL,
):
    case = next(
        item
        for item in suite.cases
        if item.case_id == case_id
    )

    semantic = evaluate_asr_adversarial_semantics(
        reference_text=case.reference_transcript,
        generated_text=case.reference_transcript,
        terminology=_terminology(),
    )

    definition = ASRAdversarialExecutionDefinition(
        execution_id=execution_id,
        case_id=case.case_id,
        provider_key=provider_key,
        model_key=model_key,
        execution_environment_sha256=(
            _sha("environment-" + execution_id)
        ),
        status=(
            ASRAdversarialExecutionStatus.COMPLETED
        ),
        terminology=_terminology(),
        generated_transcript_sha256=(
            calculate_asr_adversarial_transcript_sha256(
                case.reference_transcript
            )
        ),
        semantic_observations=semantic,
    )

    evidence = (
        build_asr_adversarial_execution_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    return definition, evidence


def _completed_attempt(
    *,
    suite,
    suite_evidence,
    case_id="qualification.case-a",
    execution_id="qualification.execution-a",
    provider_key=PROVIDER,
    model_key=MODEL,
):
    definition, evidence = _completed_child(
        suite=suite,
        suite_evidence=suite_evidence,
        case_id=case_id,
        execution_id=execution_id,
        provider_key=provider_key,
        model_key=model_key,
    )

    return ASRAdversarialCampaignAttempt(
        case_id=case_id,
        execution_id=execution_id,
        status=(
            ASRAdversarialExecutionStatus.COMPLETED
        ),
        execution_definition=definition,
        execution_evidence=evidence,
    )


def _failed_attempt(
    *,
    case_id="qualification.case-b",
    execution_id="qualification.execution-b",
    status=ASRAdversarialExecutionStatus.FAILED,
    detail="provider failed before transcription",
):
    return ASRAdversarialCampaignAttempt(
        case_id=case_id,
        execution_id=execution_id,
        status=status,
        status_detail=detail,
    )


def _definition(
    *,
    suite,
    suite_evidence,
):
    return ASRAdversarialCampaignDefinition(
        campaign_id="qualification.campaign-one",
        campaign_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        provider_key=PROVIDER,
        model_key=MODEL,
        attempts=(
            _completed_attempt(
                suite=suite,
                suite_evidence=suite_evidence,
            ),
            _failed_attempt(),
        ),
    )


def test_builds_mixed_campaign_with_exact_coverage():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite=suite,
        suite_evidence=suite_evidence,
    )

    evidence = (
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    campaign = evidence.payload["campaign"]

    assert campaign["coverage"] == {
        "expected_case_count": 2,
        "recorded_case_count": 2,
        "coverage_complete": True,
        "expected_case_ids": [
            "qualification.case-a",
            "qualification.case-b",
        ],
        "recorded_case_ids": [
            "qualification.case-a",
            "qualification.case-b",
        ],
    }

    assert campaign["status_counts"] == {
        "completed": 1,
        "failed": 1,
        "timed_out": 0,
        "cancelled": 0,
        "invalid": 0,
    }

    completed, failed = campaign["attempts"]

    assert (
        completed["execution_evidence_sha256"]
        == definition.attempts[0]
        .execution_evidence.sha256
    )

    assert (
        failed["execution_evidence_sha256"]
        is None
    )


def test_campaign_evidence_is_deterministic():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite=suite,
        suite_evidence=suite_evidence,
    )

    first = build_asr_adversarial_campaign_evidence_v1(
        definition,
        suite=suite,
        suite_evidence=suite_evidence,
    )

    second = build_asr_adversarial_campaign_evidence_v1(
        definition,
        suite=suite,
        suite_evidence=suite_evidence,
    )

    assert first.payload == second.payload
    assert first.sha256 == second.sha256


def test_completed_attempt_requires_execution_definition():
    suite, suite_evidence = _suite()
    _, evidence = _completed_child(
        suite=suite,
        suite_evidence=suite_evidence,
    )

    with pytest.raises(
        HveeContractError,
        match="requires an execution definition",
    ):
        ASRAdversarialCampaignAttempt(
            case_id="qualification.case-a",
            execution_id="qualification.execution-a",
            status=ASRAdversarialExecutionStatus.COMPLETED,
            execution_evidence=evidence,
        )


def test_completed_attempt_requires_execution_evidence():
    suite, suite_evidence = _suite()
    definition, _ = _completed_child(
        suite=suite,
        suite_evidence=suite_evidence,
    )

    with pytest.raises(
        HveeContractError,
        match="requires execution evidence",
    ):
        ASRAdversarialCampaignAttempt(
            case_id="qualification.case-a",
            execution_id="qualification.execution-a",
            status=ASRAdversarialExecutionStatus.COMPLETED,
            execution_definition=definition,
        )


def test_completed_attempt_rejects_failure_detail():
    suite, suite_evidence = _suite()
    definition, evidence = _completed_child(
        suite=suite,
        suite_evidence=suite_evidence,
    )

    with pytest.raises(
        HveeContractError,
        match="cannot contain failure detail",
    ):
        ASRAdversarialCampaignAttempt(
            case_id="qualification.case-a",
            execution_id="qualification.execution-a",
            status=ASRAdversarialExecutionStatus.COMPLETED,
            execution_definition=definition,
            execution_evidence=evidence,
            status_detail="not allowed",
        )


def test_noncompleted_attempt_rejects_slice_b_evidence():
    suite, suite_evidence = _suite()
    definition, evidence = _completed_child(
        suite=suite,
        suite_evidence=suite_evidence,
    )

    with pytest.raises(
        HveeContractError,
        match="cannot claim Slice B execution evidence",
    ):
        ASRAdversarialCampaignAttempt(
            case_id="qualification.case-a",
            execution_id="qualification.execution-a",
            status=ASRAdversarialExecutionStatus.FAILED,
            execution_definition=definition,
            execution_evidence=evidence,
            status_detail="provider failed",
        )


def test_noncompleted_attempt_requires_status_detail():
    with pytest.raises(
        HveeContractError,
        match="status detail",
    ):
        ASRAdversarialCampaignAttempt(
            case_id="qualification.case-b",
            execution_id="qualification.execution-b",
            status=ASRAdversarialExecutionStatus.TIMED_OUT,
            status_detail="",
        )


def test_campaign_attempts_must_be_sorted():
    suite, suite_evidence = _suite()

    with pytest.raises(
        HveeContractError,
        match="ordered by case id",
    ):
        ASRAdversarialCampaignDefinition(
            campaign_id="qualification.campaign-one",
            campaign_version="1.0.0",
            suite_sha256=suite_evidence.sha256,
            provider_key=PROVIDER,
            model_key=MODEL,
            attempts=(
                _failed_attempt(),
                _completed_attempt(
                    suite=suite,
                    suite_evidence=suite_evidence,
                ),
            ),
        )


def test_campaign_case_ids_must_be_unique():
    suite, suite_evidence = _suite()
    first = _completed_attempt(
        suite=suite,
        suite_evidence=suite_evidence,
    )

    duplicate = _failed_attempt(
        case_id="qualification.case-a",
        execution_id="qualification.execution-b",
    )

    with pytest.raises(
        HveeContractError,
        match="case ids must be unique",
    ):
        ASRAdversarialCampaignDefinition(
            campaign_id="qualification.campaign-one",
            campaign_version="1.0.0",
            suite_sha256=suite_evidence.sha256,
            provider_key=PROVIDER,
            model_key=MODEL,
            attempts=(first, duplicate),
        )


def test_campaign_execution_ids_must_be_unique():
    suite, suite_evidence = _suite()

    first = _completed_attempt(
        suite=suite,
        suite_evidence=suite_evidence,
    )

    second = _failed_attempt(
        execution_id="qualification.execution-a",
    )

    with pytest.raises(
        HveeContractError,
        match="execution ids must be unique",
    ):
        ASRAdversarialCampaignDefinition(
            campaign_id="qualification.campaign-one",
            campaign_version="1.0.0",
            suite_sha256=suite_evidence.sha256,
            provider_key=PROVIDER,
            model_key=MODEL,
            attempts=(first, second),
        )


def test_campaign_rejects_missing_suite_case():
    suite, suite_evidence = _suite()

    definition = ASRAdversarialCampaignDefinition(
        campaign_id="qualification.campaign-one",
        campaign_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        provider_key=PROVIDER,
        model_key=MODEL,
        attempts=(
            _completed_attempt(
                suite=suite,
                suite_evidence=suite_evidence,
            ),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="retain every sealed suite case exactly",
    ):
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_campaign_rejects_undeclared_case():
    suite, suite_evidence = _suite()

    definition = ASRAdversarialCampaignDefinition(
        campaign_id="qualification.campaign-one",
        campaign_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        provider_key=PROVIDER,
        model_key=MODEL,
        attempts=(
            _completed_attempt(
                suite=suite,
                suite_evidence=suite_evidence,
            ),
            _failed_attempt(
                case_id="qualification.case-z",
            ),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="retain every sealed suite case exactly",
    ):
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_campaign_requires_exact_suite_sha():
    suite, suite_evidence = _suite()

    definition = replace(
        _definition(
            suite=suite,
            suite_evidence=suite_evidence,
        ),
        suite_sha256=_sha("different-suite"),
    )

    with pytest.raises(
        HveeContractError,
        match="does not bind the sealed suite",
    ):
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_completed_child_provider_must_match_campaign():
    suite, suite_evidence = _suite()

    completed = _completed_attempt(
        suite=suite,
        suite_evidence=suite_evidence,
        provider_key="different_provider",
    )

    definition = ASRAdversarialCampaignDefinition(
        campaign_id="qualification.campaign-one",
        campaign_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        provider_key=PROVIDER,
        model_key=MODEL,
        attempts=(
            completed,
            _failed_attempt(),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="provider does not match campaign",
    ):
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_completed_child_model_must_match_campaign():
    suite, suite_evidence = _suite()

    completed = _completed_attempt(
        suite=suite,
        suite_evidence=suite_evidence,
        model_key="small.en",
    )

    definition = ASRAdversarialCampaignDefinition(
        campaign_id="qualification.campaign-one",
        campaign_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        provider_key=PROVIDER,
        model_key=MODEL,
        attempts=(
            completed,
            _failed_attempt(),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="model does not match campaign",
    ):
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_rehashed_child_tampering_is_rejected():
    suite, suite_evidence = _suite()

    child_definition, child_evidence = (
        _completed_child(
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    tampered = copy.deepcopy(
        child_evidence.payload
    )
    tampered["scientific_boundary"][
        "production_qualified"
    ] = True

    tampered_child = (
        ASRAdversarialExecutionEvidenceBundle(
            payload=tampered,
            sha256=(
                calculate_asr_adversarial_execution_evidence_sha256(
                    tampered
                )
            ),
        )
    )

    attempt = ASRAdversarialCampaignAttempt(
        case_id="qualification.case-a",
        execution_id="qualification.execution-a",
        status=ASRAdversarialExecutionStatus.COMPLETED,
        execution_definition=child_definition,
        execution_evidence=tampered_child,
    )

    definition = ASRAdversarialCampaignDefinition(
        campaign_id="qualification.campaign-one",
        campaign_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        provider_key=PROVIDER,
        model_key=MODEL,
        attempts=(
            attempt,
            _failed_attempt(),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_rehashed_campaign_tampering_is_rejected():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite=suite,
        suite_evidence=suite_evidence,
    )

    evidence = (
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    tampered = copy.deepcopy(
        evidence.payload
    )
    tampered["scientific_boundary"][
        "production_qualified"
    ] = True

    tampered_evidence = (
        ASRAdversarialCampaignEvidenceBundle(
            payload=tampered,
            sha256=(
                calculate_asr_adversarial_campaign_evidence_sha256(
                    tampered
                )
            ),
        )
    )

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        verify_asr_adversarial_campaign_evidence_v1(
            payload=tampered_evidence.payload,
            expected_sha256=tampered_evidence.sha256,
            definition=definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_campaign_scientific_boundary_has_no_authority():
    suite, suite_evidence = _suite()

    evidence = (
        build_asr_adversarial_campaign_evidence_v1(
            _definition(
                suite=suite,
                suite_evidence=suite_evidence,
            ),
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    boundary = evidence.payload[
        "scientific_boundary"
    ]

    assert (
        boundary[
            "completed_child_execution_evidence_reverified_when_present"
        ]
        is True
    )
    assert boundary["development_evidence_only"] is True
    assert boundary["qualification_threshold_applied"] is False
    assert boundary["certification_issued"] is False
    assert boundary["production_qualified"] is False
    assert boundary["release_enforcement_eligible"] is False
    assert boundary["official_release_verdict_modified"] is False


@pytest.mark.parametrize(
    "status",
    [
        ASRAdversarialExecutionStatus.FAILED,
        ASRAdversarialExecutionStatus.TIMED_OUT,
        ASRAdversarialExecutionStatus.CANCELLED,
        ASRAdversarialExecutionStatus.INVALID,
    ],
)
def test_all_noncompleted_statuses_are_descriptive_without_child_evidence(
    status,
):
    attempt = ASRAdversarialCampaignAttempt(
        case_id="qualification.case-a",
        execution_id="qualification.execution-a",
        status=status,
        status_detail="controlled non-completed attempt",
    )

    assert attempt.execution_definition is None
    assert attempt.execution_evidence is None


def test_rehashed_suite_tampering_is_rejected_before_campaign_build():
    suite, suite_evidence = _suite()

    tampered = copy.deepcopy(
        suite_evidence.payload
    )

    tampered["scientific_boundary"][
        "production_qualified"
    ] = True

    from hvee.packs.asr.adversarial_evidence import (
        ASRAdversarialEvidenceBundle,
        calculate_asr_adversarial_evidence_sha256,
    )

    tampered_suite_evidence = (
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
        build_asr_adversarial_campaign_evidence_v1(
            _definition(
                suite=suite,
                suite_evidence=suite_evidence,
            ),
            suite=suite,
            suite_evidence=tampered_suite_evidence,
        )


def test_completed_child_definition_and_evidence_must_match():
    suite, suite_evidence = _suite()

    child_definition, child_evidence = (
        _completed_child(
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    mismatched_definition = replace(
        child_definition,
        execution_environment_sha256=(
            _sha("different-environment")
        ),
    )

    attempt = ASRAdversarialCampaignAttempt(
        case_id="qualification.case-a",
        execution_id="qualification.execution-a",
        status=ASRAdversarialExecutionStatus.COMPLETED,
        execution_definition=(
            mismatched_definition
        ),
        execution_evidence=child_evidence,
    )

    definition = ASRAdversarialCampaignDefinition(
        campaign_id="qualification.campaign-one",
        campaign_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        provider_key=PROVIDER,
        model_key=MODEL,
        attempts=(
            attempt,
            _failed_attempt(),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_campaign_can_truthfully_record_no_completed_attempts():
    suite, suite_evidence = _suite()

    definition = ASRAdversarialCampaignDefinition(
        campaign_id="qualification.campaign-one",
        campaign_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        provider_key=PROVIDER,
        model_key=MODEL,
        attempts=(
            _failed_attempt(
                case_id="qualification.case-a",
                execution_id="qualification.execution-a",
                status=(
                    ASRAdversarialExecutionStatus
                    .TIMED_OUT
                ),
                detail="provider timed out",
            ),
            _failed_attempt(
                case_id="qualification.case-b",
                execution_id="qualification.execution-b",
                status=(
                    ASRAdversarialExecutionStatus
                    .FAILED
                ),
            ),
        ),
    )

    evidence = (
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    campaign = evidence.payload["campaign"]

    assert campaign["coverage"][
        "coverage_complete"
    ] is True

    assert campaign["status_counts"] == {
        "completed": 0,
        "failed": 1,
        "timed_out": 1,
        "cancelled": 0,
        "invalid": 0,
    }

    assert all(
        attempt["execution_evidence_sha256"]
        is None
        for attempt in campaign["attempts"]
    )


def test_adversarial_campaign_contract_is_publicly_exported():
    import hvee.packs.asr as asr

    expected = {
        "ASR_ADVERSARIAL_CAMPAIGN_EVIDENCE_KEY",
        "ASR_ADVERSARIAL_CAMPAIGN_EVIDENCE_SCHEMA_VERSION",
        "ASR_ADVERSARIAL_CAMPAIGN_EVIDENCE_VERSION",
        "ASRAdversarialCampaignAttempt",
        "ASRAdversarialCampaignDefinition",
        "ASRAdversarialCampaignEvidenceBundle",
        "build_asr_adversarial_campaign_evidence_v1",
        "calculate_asr_adversarial_campaign_evidence_sha256",
        "verify_asr_adversarial_campaign_evidence_v1",
    }

    for name in expected:
        assert hasattr(asr, name)
        assert name in asr.__all__
