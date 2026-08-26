from __future__ import annotations

import hashlib
from pathlib import Path
from types import MappingProxyType

import pytest

import app.adversarial_asr_brutal_campaign as campaign_module
from app.adversarial_asr_brutal_campaign import (
    ASRBrutalValidationCampaignError,
    ASRBrutalValidationMediaIdentity,
    ASRBrutalValidationSuiteBundle,
    ASR_BRUTAL_TERMINOLOGY_BINDING_V1,
    ASR_BRUTAL_VALIDATION_MEDIA_V1,
    ASR_BRUTAL_VALIDATION_MODELS_V1,
    _verified_path,
    build_asr_brutal_validation_suite_v1,
    execute_asr_brutal_validation_campaign_v1,
)
from hvee.packs.asr import (
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialNoiseCondition,
    ASRAdversarialTerminologyState,
)
from hvee.packs.asr.adversarial_corpus_v1 import (
    build_asr_adversarial_corpus_v1,
)
from hvee.packs.asr.brutal_validation_plan import (
    ASR_BRUTAL_VALIDATION_CASES_V1,
)


def _case_map():
    suite, _evidence = build_asr_brutal_validation_suite_v1()
    return {
        case.case_id: case
        for case in suite.cases
    }


def test_suite_has_exact_frozen_membership_and_order():
    suite, evidence = build_asr_brutal_validation_suite_v1()
    repeated_suite, repeated_evidence = (
        build_asr_brutal_validation_suite_v1()
    )

    observed = tuple(
        case.case_id
        for case in suite.cases
    )
    planned = tuple(
        case.case_id
        for case in ASR_BRUTAL_VALIDATION_CASES_V1
    )

    assert len(observed) == 13
    assert len(set(observed)) == 13
    assert observed == tuple(sorted(observed))
    assert set(observed) == set(planned)
    assert repeated_suite == suite
    assert repeated_evidence == evidence
    assert repeated_evidence.sha256 == evidence.sha256


def test_suite_media_identities_are_exact_and_unique():
    suite, _evidence = build_asr_brutal_validation_suite_v1()
    suite_ids = {
        case.case_id
        for case in suite.cases
    }
    identities = ASR_BRUTAL_VALIDATION_MEDIA_V1
    identity_ids = {
        identity.case_id
        for identity in identities
    }

    assert len(identities) == 13
    assert len(identity_ids) == 13
    assert identity_ids == suite_ids
    assert all(
        len(identity.audio_asset_sha256) == 64
        for identity in identities
    )


def test_derived_cases_preserve_parent_semantics():
    (
        canonical_suite,
        _evidence,
        _definition,
        _manifest,
    ) = build_asr_adversarial_corpus_v1()

    canonical = {
        case.case_id: case
        for case in canonical_suite.cases
    }
    cases = _case_map()
    multi_number = canonical[
        "clean.multi-number-id"
    ]
    clean_critical = canonical[
        "control.clean-critical"
    ]

    for case_id in (
        "stress.codec-aac.multi-number-id",
        "stress.codec-alaw.multi-number-id",
        "stress.codec-mp3.multi-number-id",
        "stress.codec-mulaw.multi-number-id",
        "stress.noise-moderate.multi-number-id",
        "stress.noise-severe-usable.multi-number-id",
        "stress.telephony-bandwidth.multi-number-id",
    ):
        assert cases[
            case_id
        ].reference_transcript == (
            multi_number.reference_transcript
        )
        assert cases[case_id].semantic_load == multi_number.semantic_load

    for case_id in (
        "brutal.compound-critical.telephony-noise",
        "brutal.terminology.telephony-noise",
    ):
        assert cases[case_id].reference_transcript == (
            clean_critical.reference_transcript
        )
        assert cases[case_id].semantic_load == clean_critical.semantic_load


def test_frozen_models_and_terminology_binding():
    assert ASR_BRUTAL_VALIDATION_MODELS_V1 == (
        "small.en",
        "large-v3-turbo",
    )
    assert ASR_BRUTAL_TERMINOLOGY_BINDING_V1.state is (
        ASRAdversarialTerminologyState.CONFIGURED
    )
    assert ASR_BRUTAL_TERMINOLOGY_BINDING_V1.profile_key == (
        "brutal-validation.terminology-profile"
    )
    assert ASR_BRUTAL_TERMINOLOGY_BINDING_V1.profile_version == "1.0.0"


def test_critical_condition_projection_is_exact():
    cases = _case_map()
    expected = {
        "brutal.compound-critical.telephony-noise": (
            ASRAdversarialChannel.TELEPHONY,
            ASRAdversarialCodec.MULAW,
            8_000,
            ASRAdversarialNoiseCondition.SEVERE_USABLE,
        ),
        "brutal.terminology.telephony-noise": (
            ASRAdversarialChannel.TELEPHONY,
            ASRAdversarialCodec.LINEAR_PCM,
            8_000,
            ASRAdversarialNoiseCondition.MODERATE,
        ),
    }

    for case_id, condition in expected.items():
        observed = cases[case_id].condition
        assert (
            observed.channel,
            observed.codec,
            observed.sample_rate_hz,
            observed.noise,
        ) == condition


def test_verified_path_accepts_exact_identity(tmp_path: Path):
    audio = tmp_path / "case.wav"
    audio.write_bytes(b"brutal-campaign-audio")
    identity = ASRBrutalValidationMediaIdentity(
        case_id="brutal.test.case",
        relative_path="case.wav",
        audio_asset_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),
    )

    assert _verified_path(tmp_path.resolve(), identity) == audio.resolve()


def test_verified_path_rejects_identity_mismatch(tmp_path: Path):
    audio = tmp_path / "case.wav"
    audio.write_bytes(b"brutal-campaign-audio")
    identity = ASRBrutalValidationMediaIdentity(
        case_id="brutal.test.case",
        relative_path="case.wav",
        audio_asset_sha256="0" * 64,
    )

    with pytest.raises(
        ASRBrutalValidationCampaignError,
        match="Audio identity mismatch",
    ):
        _verified_path(tmp_path.resolve(), identity)


def test_invalid_model_is_rejected_before_execution():
    with pytest.raises(
        ASRBrutalValidationCampaignError,
        match="outside the frozen",
    ):
        execute_asr_brutal_validation_campaign_v1(
            campaign_id="brutal.invalid-model",
            requested_model_name="unfrozen-model",
            provider=object(),
            bundle=object(),
        )


@pytest.mark.parametrize(
    "model_name",
    ASR_BRUTAL_VALIDATION_MODELS_V1,
)
def test_frozen_model_delegates_to_generic_campaign(
    monkeypatch,
    model_name: str,
):
    suite, evidence = build_asr_brutal_validation_suite_v1()
    audio_paths = MappingProxyType(
        {
            case.case_id: Path(f"/{case.case_id}.wav")
            for case in suite.cases
        }
    )
    bundle = ASRBrutalValidationSuiteBundle(
        suite=suite,
        suite_evidence=evidence,
        audio_paths=audio_paths,
    )
    provider = object()
    sentinel = object()
    captured = {}

    def fake_campaign(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        campaign_module,
        "execute_asr_adversarial_campaign",
        fake_campaign,
    )

    result = execute_asr_brutal_validation_campaign_v1(
        campaign_id=f"brutal.{model_name}",
        requested_model_name=model_name,
        provider=provider,
        bundle=bundle,
    )

    assert result is sentinel
    assert captured["requested_model_name"] == model_name
    assert captured["provider"] is provider
    assert captured["audio_paths"] is audio_paths
    assert captured["suite"] is suite
    assert captured["suite_evidence"] is evidence
    assert captured["terminology"] is (
        ASR_BRUTAL_TERMINOLOGY_BINDING_V1
    )
