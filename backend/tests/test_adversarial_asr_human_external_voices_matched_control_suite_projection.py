from __future__ import annotations

from collections import Counter
from dataclasses import FrozenInstanceError
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from app.adversarial_asr_human_external_voices_matched_control_projection import (
    ASRAdversarialVOiCESMatchedControlProjectionBundle,
    project_asr_adversarial_voices_babble_matched_control_v1,
)
from app.adversarial_asr_human_external_voices_matched_control_suite_projection import (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_ARM,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_SOURCE,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_SOURCE_ARM,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_KEY,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_VERSION,
    ASRAdversarialVOiCESMatchedControlExecutionCase,
    ASRAdversarialVOiCESMatchedControlSuiteBundle,
    ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
    project_asr_adversarial_voices_babble_matched_control_suite_v1,
)
from app.adversarial_asr_human_external_voices_materialization_service import (
    ASRAdversarialVOiCESMaterializedCaptureCondition,
    ASRAdversarialVOiCESMaterializedEvidence,
    ASRAdversarialVOiCESMaterializedMedia,
)
from hvee.packs.asr.adversarial_evidence import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialDurationBucket,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSpeakingRate,
    build_asr_adversarial_evidence_v1,
    calculate_asr_adversarial_evidence_sha256,
    verify_asr_adversarial_evidence_v1,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
)
from hvee.packs.asr.adversarial_human_external_voices_reference_transcripts_v1 import (
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S,
)


def _sha256(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def _source_media(
    source_key: tuple[int, int, int],
) -> ASRAdversarialVOiCESMaterializedMedia:
    source_id = "-".join(
        str(
            value
        )
        for value in source_key
    )
    relative_path = (
        f"source/{source_id}.wav"
    )

    return ASRAdversarialVOiCESMaterializedMedia(
        relative_path=relative_path,
        path=(
            Path(
                "/verified"
            )
            / relative_path
        ),
        sha256=_sha256(
            relative_path
        ),
        byte_length=32_000,
        kind="source",
        source_key=source_key,
        codec_name="pcm_s16le",
        sample_rate_hz=16_000,
        channel_count=1,
        bits_per_sample=16,
        sample_width_bytes=2,
        sample_count=16_000,
        duration_seconds="1.000000",
    )


def _capture_media(
    *,
    source_key: tuple[int, int, int],
    room: str,
    distractor: str,
    microphone_id: int,
    suffix: str = "",
) -> ASRAdversarialVOiCESMaterializedMedia:
    source_id = "-".join(
        str(
            value
        )
        for value in source_key
    )
    relative_path = (
        "capture/"
        f"{source_id}-{room}-{distractor}-"
        f"mic{microphone_id}{suffix}.wav"
    )

    return ASRAdversarialVOiCESMaterializedMedia(
        relative_path=relative_path,
        path=(
            Path(
                "/verified"
            )
            / relative_path
        ),
        sha256=_sha256(
            relative_path
        ),
        byte_length=32_000,
        kind="capture",
        source_key=source_key,
        codec_name="pcm_s16le",
        sample_rate_hz=16_000,
        channel_count=1,
        bits_per_sample=16,
        sample_width_bytes=2,
        sample_count=16_000,
        duration_seconds="1.000000",
        capture_condition=(
            ASRAdversarialVOiCESMaterializedCaptureCondition(
                angle_degrees=10,
                room=room,
                distractor=distractor,
                microphone_id=microphone_id,
            )
        ),
    )


def _media_population(
    *,
    suffix: str = "",
) -> tuple[
    ASRAdversarialVOiCESMaterializedMedia,
    ...,
]:
    media = [
        _source_media(
            source_key
        )
        for source_key in (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
        )
    ]

    media.extend(
        _capture_media(
            source_key=source_key,
            room=room,
            distractor=distractor,
            microphone_id=microphone_id,
            suffix=suffix,
        )
        for source_key in (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
        )
        for room in (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS
        )
        for distractor in (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS
        )
        for microphone_id in (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS
        )
    )

    return tuple(
        media
    )


def _materialized_evidence(
    *,
    suffix: str = "",
) -> ASRAdversarialVOiCESMaterializedEvidence:
    return ASRAdversarialVOiCESMaterializedEvidence(
        controlled_contract_sha256=(
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
        ),
        identity_chain_sha256=_sha256(
            f"identity-chain{suffix}"
        ),
        selection_sha256=_sha256(
            f"selection{suffix}"
        ),
        materialization_manifest_sha256=_sha256(
            f"materialization-manifest{suffix}"
        ),
        media_report_sha256=_sha256(
            f"media-report{suffix}"
        ),
        observation_sha256=_sha256(
            f"observation{suffix}"
        ),
        rights_manifest_sha256=_sha256(
            f"rights-manifest{suffix}"
        ),
        media=_media_population(
            suffix=suffix
        ),
    )


def _matched_projection(
    *,
    suffix: str = "",
) -> ASRAdversarialVOiCESMatchedControlProjectionBundle:
    return (
        project_asr_adversarial_voices_babble_matched_control_v1(
            _materialized_evidence(
                suffix=suffix
            )
        )
    )


def _suite(
    *,
    suffix: str = "",
) -> ASRAdversarialVOiCESMatchedControlSuiteBundle:
    return (
        project_asr_adversarial_voices_babble_matched_control_suite_v1(
            _matched_projection(
                suffix=suffix
            )
        )
    )


def test_frozen_suite_constants_are_exact():
    assert (
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_SCHEMA_VERSION
        == 1
    )
    assert (
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_VERSION
        == "1.0.0"
    )
    assert (
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_KEY
        == (
            "hetren.asr.adversarial-human-external-"
            "voices-babble-matched-control-suite"
        )
    )
    assert (
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
        == 32
    )
    assert (
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_ARM
        == 16
    )
    assert (
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_SOURCE
        == 16
    )
    assert (
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_SOURCE_ARM
        == 8
    )


def test_projects_exact_execution_ready_suite_population():
    projection = _matched_projection()
    suite = (
        project_asr_adversarial_voices_babble_matched_control_suite_v1(
            projection
        )
    )

    assert isinstance(
        suite,
        ASRAdversarialVOiCESMatchedControlSuiteBundle,
    )
    assert len(
        suite.cases
    ) == 32
    assert len(
        suite.definition.cases
    ) == 32
    assert suite.definition.cases == tuple(
        binding.case
        for binding in suite.cases
    )
    assert suite.projection is projection
    assert suite.matched_control_projection_sha256 == (
        projection.sha256
    )
    assert all(
        isinstance(
            binding,
            ASRAdversarialVOiCESMatchedControlExecutionCase,
        )
        for binding in suite.cases
    )


def test_suite_is_deterministic_for_same_verified_projection():
    first = _suite()
    second = _suite()

    assert first == second
    assert first is not second
    assert first.payload == second.payload
    assert first.sha256 == second.sha256


def test_suite_sha256_is_canonical_lowercase_digest():
    suite = _suite()

    assert len(
        suite.sha256
    ) == 64
    assert set(
        suite.sha256
    ) <= set(
        "0123456789abcdef"
    )
    assert suite.sha256 == hashlib.sha256(
        __import__(
            "json"
        ).dumps(
            suite.payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            allow_nan=False,
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def test_suite_case_ids_are_unique_and_sorted():
    case_ids = tuple(
        binding.case.case_id
        for binding in _suite().cases
    )

    assert case_ids == tuple(
        sorted(
            case_ids
        )
    )
    assert len(
        case_ids
    ) == len(
        set(
            case_ids
        )
    ) == 32
    assert case_ids[0] == (
        "voices-babble-sp0652-ch129742-"
        "sg0003-rm1-mc01-dg010"
    )
    assert case_ids[-1] == (
        "voices-control-sp7850-ch111771-"
        "sg0004-rm4-mc05-dg010"
    )


def test_suite_audio_assets_are_exactly_projection_capture_assets():
    projection = _matched_projection()
    suite = (
        project_asr_adversarial_voices_babble_matched_control_suite_v1(
            projection
        )
    )

    expected = {
        media.sha256
        for pair in projection.pairs
        for media in (
            pair.interference,
            pair.control,
        )
    }

    observed = {
        binding.case.audio_asset_sha256
        for binding in suite.cases
    }

    assert observed == expected
    assert len(
        observed
    ) == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT
    )


def test_suite_has_exact_balanced_arms():
    counts = Counter(
        binding.arm
        for binding in _suite().cases
    )

    assert counts == Counter(
        {
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM: 16,
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM: 16,
        }
    )


def test_suite_has_exact_balanced_sources():
    counts = Counter(
        binding.pair_key.source_key
        for binding in _suite().cases
    )

    assert counts == Counter(
        {
            source_key: 16
            for source_key in (
                ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
            )
        }
    )


def test_suite_has_exact_source_arm_balance():
    counts = Counter(
        (
            binding.pair_key.source_key,
            binding.arm,
        )
        for binding in _suite().cases
    )

    assert counts == Counter(
        {
            (
                source_key,
                arm,
            ): 8
            for source_key in (
                ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
            )
            for arm in (
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
            )
        }
    )


def test_every_verified_pair_projects_both_arms():
    observed = Counter(
        binding.pair_key
        for binding in _suite().cases
    )

    assert len(
        observed
    ) == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
    )
    assert set(
        observed.values()
    ) == {
        2
    }


def test_reference_transcripts_map_exactly_by_source():
    expected = {
        source_key: transcript
        for source_key, transcript in zip(
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS,
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS,
            strict=True,
        )
    }

    for binding in _suite().cases:
        assert binding.case.reference_transcript == expected[
            binding.pair_key.source_key
        ]


def test_reference_transcript_hashes_map_exactly_by_source():
    expected = {
        source_key: transcript_sha256
        for source_key, transcript_sha256 in zip(
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS,
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S,
            strict=True,
        )
    }

    for binding in _suite().cases:
        assert (
            binding.reference_transcript_sha256
            == expected[
                binding.pair_key.source_key
            ]
        )
        assert hashlib.sha256(
            binding.case.reference_transcript.encode(
                "utf-8"
            )
        ).hexdigest() == (
            binding.reference_transcript_sha256
        )


def test_case_media_paths_remain_absolute_for_execution():
    assert all(
        binding.media.path.is_absolute()
        for binding in _suite().cases
    )


def test_absolute_local_paths_are_not_embedded_in_payload():
    suite = _suite()
    payload_text = str(
        suite.payload
    )

    assert "/verified/" not in payload_text
    assert all(
        binding.media.relative_path
        in payload_text
        for binding in suite.cases
    )


def test_all_cases_use_verified_linear_pcm_transport_metadata():
    for binding in _suite().cases:
        condition = binding.case.condition

        assert condition.channel == (
            ASRAdversarialChannel.CLEAN
        )
        assert condition.codec == (
            ASRAdversarialCodec.LINEAR_PCM
        )
        assert condition.sample_rate_hz == (
            binding.media.sample_rate_hz
        ) == 16_000


def test_channel_clean_value_is_not_claimed_as_acoustically_clean():
    methodology = _suite().payload[
        "condition_methodology"
    ]

    assert methodology[
        "channel_clean_value_means_non_telephony_transport"
    ] is True
    assert methodology[
        "physical_babble_presence_verified"
    ] is True
    assert methodology[
        "room_microphone_angle_metadata_verified"
    ] is True


def test_babble_cases_use_moderate_noise_without_overlap_claim():
    babble = (
        binding
        for binding in _suite().cases
        if binding.arm
        == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
    )

    for binding in babble:
        assert binding.case.condition.noise == (
            ASRAdversarialNoiseCondition.MODERATE
        )
        assert binding.case.condition.overlap == (
            ASRAdversarialOverlapCondition.NONE
        )
        assert (
            binding.media.require_capture_condition().distractor
            == ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE
        )


def test_control_cases_use_no_noise_and_no_overlap_claim():
    controls = (
        binding
        for binding in _suite().cases
        if binding.arm
        == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
    )

    for binding in controls:
        assert binding.case.condition.noise == (
            ASRAdversarialNoiseCondition.NONE
        )
        assert binding.case.condition.overlap == (
            ASRAdversarialOverlapCondition.NONE
        )
        assert (
            binding.media.require_capture_condition().distractor
            == ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL
        )


def test_microphone_classes_map_exact_verified_ids():
    for binding in _suite().cases:
        expected = (
            "studio-close"
            if binding.pair_key.microphone_id == 1
            else "studio-far"
        )

        assert (
            binding.case.condition.microphone_class
            == expected
        )


def test_caller_declared_rate_and_duration_buckets_are_conservative():
    for binding in _suite().cases:
        assert binding.case.condition.speaking_rate == (
            ASRAdversarialSpeakingRate.NORMAL
        )
        assert binding.case.condition.duration == (
            ASRAdversarialDurationBucket.SHORT
        )

    methodology = _suite().payload[
        "condition_methodology"
    ]

    assert methodology[
        "speaking_rate_bucket_caller_declared"
    ] is True
    assert methodology[
        "duration_bucket_caller_declared"
    ] is True


def test_speech_variety_keys_are_source_specific_without_attribute_inference():
    observed = {
        binding.case.condition.speech_variety_key
        for binding in _suite().cases
    }

    assert observed == {
        "voices-source-0652",
        "voices-source-7850",
    }


def test_cases_are_semantic_controls_not_critical_fidelity_cases():
    for binding in _suite().cases:
        semantic = binding.case.semantic_load

        assert semantic.total_critical_items == 0
        assert semantic.semantic_family_count == 0
        assert semantic.control_case is True
        assert semantic.spoken_number_variation is False
        assert semantic.multiple_critical_items is False
        assert semantic.duplicate_critical_items is False
        assert semantic.ordering_challenge is False


def test_babble_and_control_active_stress_counts_are_exact():
    observed = {
        arm: {
            binding.case.condition.active_stress_count
            for binding in _suite().cases
            if binding.arm == arm
        }
        for arm in (
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
        )
    }

    assert observed == {
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM: {
            1
        },
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM: {
            0
        },
    }


def test_case_tags_are_unique_sorted_and_boundary_specific():
    for binding in _suite().cases:
        tags = binding.case.tags

        assert tags == tuple(
            sorted(
                set(
                    tags
                )
            )
        )
        assert "voices" in tags
        assert "real-room" in tags
        assert "physical-capture" in tags
        assert "semantic-control" in tags

        expected_condition_tag = (
            "babble-interference"
            if binding.arm
            == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
            else "no-distractor-control"
        )
        assert expected_condition_tag in tags


def test_case_descriptions_state_exact_matched_design():
    for binding in _suite().cases:
        description = binding.case.description

        assert "Verified VOiCES real-room" in description
        assert "matched to an exact" in description
        assert "foreground" in description
        assert "sample-count" in description


def test_generic_adversarial_definition_identity_is_preserved():
    definition = _suite().definition

    assert definition.key == ASR_ADVERSARIAL_EVIDENCE_KEY
    assert definition.version == (
        ASR_ADVERSARIAL_EVIDENCE_VERSION
    )


def test_generic_adversarial_evidence_is_exactly_rebuildable():
    suite = _suite()
    rebuilt = build_asr_adversarial_evidence_v1(
        suite.definition
    )

    assert suite.evidence == rebuilt
    assert suite.evidence.sha256 == (
        calculate_asr_adversarial_evidence_sha256(
            suite.evidence.payload
        )
    )

    verified = verify_asr_adversarial_evidence_v1(
        payload=suite.evidence.payload,
        expected_sha256=suite.evidence.sha256,
        definition=suite.definition,
    )

    assert verified == suite.evidence


def test_suite_payload_binds_all_upstream_identities():
    projection = _matched_projection()
    suite = (
        project_asr_adversarial_voices_babble_matched_control_suite_v1(
            projection
        )
    )
    upstream = suite.payload[
        "upstream"
    ]

    assert upstream == {
        "matched_control_projection_sha256": (
            projection.sha256
        ),
        "reference_transcripts_contract_sha256": (
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
        ),
        "adversarial_evidence_sha256": (
            suite.evidence.sha256
        ),
    }


def test_suite_payload_binds_exact_population_and_order():
    suite = _suite()
    payload = suite.payload[
        "suite"
    ]

    assert payload[
        "case_count"
    ] == 32
    assert payload[
        "pair_count"
    ] == 16
    assert payload[
        "babble_case_count"
    ] == 16
    assert payload[
        "control_case_count"
    ] == 16
    assert payload[
        "ordered_case_ids"
    ] == [
        binding.case.case_id
        for binding in suite.cases
    ]
    assert payload[
        "ordered_audio_asset_sha256s"
    ] == [
        binding.case.audio_asset_sha256
        for binding in suite.cases
    ]
    assert len(
        payload[
            "case_bindings"
        ]
    ) == 32


@pytest.mark.parametrize(
    "field",
    (
        "development_evidence_only",
        "verified_materialized_media_consumed",
        "reference_transcripts_projected",
        "adversarial_suite_built",
        "execution_inputs_bound",
        "execution_ready",
    ),
)
def test_suite_evidence_boundary_positive_claims_are_exact(
    field: str,
):
    boundary = _suite().payload[
        "evidence_boundary"
    ]

    assert boundary[field] is True


@pytest.mark.parametrize(
    "field",
    (
        "raw_audio_embedded",
        "source_audio_spoken_content_independently_verified",
        "babble_speaker_transcripts_verified",
        "conversational_speaker_overlap_verified",
        "critical_semantic_qualification_supported",
        "asr_execution_verified",
        "qualification_threshold_applied",
        "certification_issued",
        "production_qualified",
        "release_enforcement_eligible",
        "official_release_verdict_modified",
    ),
)
def test_suite_evidence_boundary_does_not_overclaim(
    field: str,
):
    boundary = _suite().payload[
        "evidence_boundary"
    ]

    assert boundary[field] is False


def test_suite_object_authority_boundary_is_exact():
    suite = _suite()

    assert suite.development_evidence_only is True
    assert suite.reference_transcripts_projected is True
    assert suite.adversarial_suite_built is True
    assert suite.execution_ready is True
    assert suite.asr_execution_verified is False
    assert suite.qualification_threshold_applied is False
    assert suite.production_qualified is False
    assert suite.release_enforcement_eligible is False
    assert suite.official_release_verdict_modified is False


def test_execution_verification_requirement_fails_closed():
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="execution-ready.*no ASR execution",
    ):
        _suite().require_asr_execution_verified()


@pytest.mark.parametrize(
    "value",
    (
        None,
        object(),
        "projection",
        7,
    ),
)
def test_projector_rejects_non_projection_input(
    value: object,
):
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="requires verified matched-control pairs",
    ):
        project_asr_adversarial_voices_babble_matched_control_suite_v1(
            value
        )


def test_execution_case_rejects_wrong_arm():
    binding = _suite().cases[0]

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="arm is invalid",
    ):
        replace(
            binding,
            arm="unknown",
        )


def test_execution_case_rejects_wrong_transcript_hash():
    binding = _suite().cases[0]

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="transcript binding changed",
    ):
        replace(
            binding,
            reference_transcript_sha256=(
                "0" * 64
            ),
        )


def test_execution_case_rejects_wrong_audio_binding():
    binding = _suite().cases[0]
    changed_case = replace(
        binding.case,
        audio_asset_sha256=(
            "0" * 64
        ),
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="media binding changed",
    ):
        replace(
            binding,
            case=changed_case,
        )


def test_execution_case_rejects_overlap_escalation():
    binding = _suite().cases[0]
    changed_condition = replace(
        binding.case.condition,
        overlap=(
            ASRAdversarialOverlapCondition.NON_CRITICAL
        ),
    )
    changed_case = replace(
        binding.case,
        condition=changed_condition,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="condition mapping changed",
    ):
        replace(
            binding,
            case=changed_case,
        )


def test_execution_case_rejects_noise_mapping_change():
    binding = next(
        value
        for value in _suite().cases
        if value.arm
        == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
    )
    changed_condition = replace(
        binding.case.condition,
        noise=ASRAdversarialNoiseCondition.SEVERE_USABLE,
    )
    changed_case = replace(
        binding.case,
        condition=changed_condition,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="condition mapping changed",
    ):
        replace(
            binding,
            case=changed_case,
        )


def test_execution_case_rejects_semantic_authority_escalation():
    binding = _suite().cases[0]
    changed_semantic = replace(
        binding.case.semantic_load,
        critical_terminology_count=1,
        multiple_critical_items=False,
        control_case=False,
    )
    changed_case = replace(
        binding.case,
        semantic_load=changed_semantic,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="semantic boundary changed",
    ):
        replace(
            binding,
            case=changed_case,
        )


def test_execution_case_rejects_semantic_metadata_change():
    binding = _suite().cases[0]
    changed_semantic = replace(
        binding.case.semantic_load,
        critical_number_count=2,
        multiple_critical_items=True,
        duplicate_critical_items=True,
        ordering_challenge=True,
        control_case=False,
    )
    changed_case = replace(
        binding.case,
        semantic_load=changed_semantic,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="semantic boundary changed",
    ):
        replace(
            binding,
            case=changed_case,
        )


def test_execution_case_rejects_description_change():
    binding = _suite().cases[0]
    changed_case = replace(
        binding.case,
        description="Changed matched-control description.",
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="description changed",
    ):
        replace(
            binding,
            case=changed_case,
        )


def test_execution_case_rejects_non_pcm_media_mapping():
    binding = _suite().cases[0]
    changed_media = replace(
        binding.media,
        codec_name="flac",
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="linear-PCM mapping changed",
    ):
        replace(
            binding,
            media=changed_media,
        )


def test_suite_rejects_wrong_reference_contract_identity():
    suite = _suite()

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="reference-transcript identity changed",
    ):
        replace(
            suite,
            reference_transcripts_contract_sha256=(
                "0" * 64
            ),
        )


def test_suite_rejects_projection_hash_substitution():
    suite = _suite()

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="projection identity changed",
    ):
        replace(
            suite,
            matched_control_projection_sha256=(
                "0" * 64
            ),
        )


def test_suite_rejects_projection_substitution():
    suite = _suite()

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="projection identity changed",
    ):
        replace(
            suite,
            projection=_matched_projection(
                suffix="-substituted"
            ),
        )


def test_suite_rejects_missing_case():
    suite = _suite()

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="population changed",
    ):
        replace(
            suite,
            cases=suite.cases[:-1],
        )


def test_suite_rejects_non_tuple_case_population():
    suite = _suite()

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="population changed",
    ):
        replace(
            suite,
            cases=list(
                suite.cases
            ),
        )


def test_suite_rejects_evidence_substitution():
    suite = _suite()
    substituted_definition = _suite(
        suffix="-substituted"
    ).definition
    substituted_evidence = (
        build_asr_adversarial_evidence_v1(
            substituted_definition
        )
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="suite evidence changed",
    ):
        replace(
            suite,
            evidence=substituted_evidence,
        )


def test_suite_rejects_reference_transcript_substitution():
    suite = _suite()
    binding = suite.cases[0]
    transcript = (
        "substituted source transcript"
    )
    changed_case = replace(
        binding.case,
        reference_transcript=transcript,
    )
    changed_binding = replace(
        binding,
        case=changed_case,
        reference_transcript_sha256=(
            _sha256(
                transcript
            )
        ),
    )
    changed_cases = (
        changed_binding,
        *suite.cases[1:],
    )
    changed_definition = replace(
        suite.definition,
        cases=tuple(
            value.case
            for value in changed_cases
        ),
    )
    changed_evidence = build_asr_adversarial_evidence_v1(
        changed_definition
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="reference-transcript binding changed",
    ):
        replace(
            suite,
            cases=changed_cases,
            definition=changed_definition,
            evidence=changed_evidence,
        )


@pytest.mark.parametrize(
    (
        "field",
        "value",
    ),
    (
        (
            "development_evidence_only",
            False,
        ),
        (
            "reference_transcripts_projected",
            False,
        ),
        (
            "adversarial_suite_built",
            False,
        ),
        (
            "execution_ready",
            False,
        ),
        (
            "asr_execution_verified",
            True,
        ),
        (
            "qualification_threshold_applied",
            True,
        ),
        (
            "production_qualified",
            True,
        ),
        (
            "release_enforcement_eligible",
            True,
        ),
        (
            "official_release_verdict_modified",
            True,
        ),
    ),
)
def test_suite_rejects_authority_boundary_change(
    field: str,
    value: bool,
):
    suite = _suite()

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlSuiteProjectionError,
        match="authority boundary changed",
    ):
        replace(
            suite,
            **{
                field: value
            },
        )


def test_distinct_verified_projection_changes_suite_identity():
    first = _suite()
    second = _suite(
        suffix="-second"
    )

    assert first.matched_control_projection_sha256 != (
        second.matched_control_projection_sha256
    )
    assert first.evidence.sha256 != (
        second.evidence.sha256
    )
    assert first.sha256 != second.sha256


def test_execution_case_type_is_frozen_slots_dataclass():
    binding = _suite().cases[0]

    with pytest.raises(
        FrozenInstanceError
    ):
        binding.arm = "control"

    with pytest.raises(
        (
            AttributeError,
            TypeError,
        )
    ):
        binding.unexpected = True


def test_suite_type_is_frozen_slots_dataclass():
    suite = _suite()

    with pytest.raises(
        FrozenInstanceError
    ):
        suite.execution_ready = False

    with pytest.raises(
        (
            AttributeError,
            TypeError,
        )
    ):
        suite.unexpected = True


def test_case_bindings_preserve_pair_format_equality():
    suite = _suite()
    by_key = {}

    for binding in suite.cases:
        by_key.setdefault(
            binding.pair_key,
            {},
        )[
            binding.arm
        ] = binding

    for arms in by_key.values():
        babble = arms[
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
        ].media
        control = arms[
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
        ].media

        assert babble.codec_name == control.codec_name
        assert babble.sample_rate_hz == control.sample_rate_hz
        assert babble.channel_count == control.channel_count
        assert babble.bits_per_sample == control.bits_per_sample
        assert babble.sample_width_bytes == control.sample_width_bytes
        assert babble.sample_count == control.sample_count
        assert babble.duration_seconds == control.duration_seconds
