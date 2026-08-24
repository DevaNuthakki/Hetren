from __future__ import annotations

import copy

import pytest
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_evidence import (
    ASRAdversarialHumanExternalRepositoryMediaPolicy,
    calculate_asr_adversarial_human_external_sha256,
    verify_asr_adversarial_human_external_record_pair_v1,
)
from hvee.packs.asr.adversarial_human_external_minilibrispeech_v1 import (
    ASR_ADVERSARIAL_MINILIBRISPEECH_ARCHIVE_SHA256,
    ASR_ADVERSARIAL_MINILIBRISPEECH_CASES,
    ASR_ADVERSARIAL_MINILIBRISPEECH_I4B2_SELECTION_REPORT_SHA256,
    ASR_ADVERSARIAL_MINILIBRISPEECH_I4B3_MEDIA_REPORT_SHA256,
    ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256,
    build_asr_adversarial_minilibrispeech_record_pair_v1,
    build_asr_adversarial_minilibrispeech_record_pairs_v1,
    build_asr_adversarial_minilibrispeech_selection_v1,
    get_asr_adversarial_minilibrispeech_case_v1,
    verify_asr_adversarial_minilibrispeech_selection_v1,
)


def test_minilibrispeech_selection_identity_is_frozen():
    first = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )
    second = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    assert first == second
    assert first.sha256 == (
        ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256
    )
    assert first.sha256 == (
        "019d09f3989ac16da9484bba48653fe8"
        "9663905ef3db1cb74cae2d287721f409"
    )


def test_minilibrispeech_selection_binds_acquisition_evidence():
    bundle = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    source = bundle.payload["source"]
    acquisition = bundle.payload[
        "acquisition_evidence"
    ]

    assert source["archive_sha256"] == (
        ASR_ADVERSARIAL_MINILIBRISPEECH_ARCHIVE_SHA256
    )
    assert source["declared_license"] == "CC BY 4.0"
    assert source["repository_media_policy"] == (
        ASRAdversarialHumanExternalRepositoryMediaPolicy
        .NOT_COMMITTED
        .value
    )

    assert acquisition[
        "selection_report_sha256"
    ] == (
        ASR_ADVERSARIAL_MINILIBRISPEECH_I4B2_SELECTION_REPORT_SHA256
    )

    assert acquisition[
        "media_verification_report_sha256"
    ] == (
        ASR_ADVERSARIAL_MINILIBRISPEECH_I4B3_MEDIA_REPORT_SHA256
    )


def test_minilibrispeech_selection_has_eight_distinct_sources():
    assert len(
        ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
    ) == 8

    utterance_ids = tuple(
        case.utterance_id
        for case in ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
    )
    speaker_ids = tuple(
        case.speaker_id
        for case in ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
    )

    assert utterance_ids == tuple(
        sorted(utterance_ids)
    )

    assert len(
        set(utterance_ids)
    ) == 8

    assert len(
        set(speaker_ids)
    ) == 8


def test_minilibrispeech_selected_media_contract_is_exact():
    expected = {
        "1272-141231-0016": (37_052, 1_850),
        "174-168635-0004": (232_298, 12_770),
        "2412-153948-0004": (404_370, 22_680),
        "251-118436-0003": (204_641, 11_020),
        "3000-15664-0017": (239_228, 14_085),
        "3576-138058-0038": (185_316, 9_650),
        "5895-34622-0003": (102_457, 5_080),
        "6241-61943-0000": (139_579, 6_950),
    }

    for case in ASR_ADVERSARIAL_MINILIBRISPEECH_CASES:
        assert (
            case.audio_bytes,
            case.duration_ms,
        ) == expected[
            case.utterance_id
        ]

        assert case.codec_name == "flac"
        assert case.format_name == "flac"
        assert case.sample_rate_hz == 16_000
        assert case.channel_count == 1


def test_minilibrispeech_selection_keeps_scientific_boundary_negative():
    bundle = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "source_speaker_ids_are_source_defined"
    ] is True

    for field_name in (
        "speaker_attributes_inferred",
        "accent_inferred",
        "microphone_class_inferred",
        "human_acoustic_diversity_established",
        "rights_adjudicated",
        "qualification_threshold_applied",
        "production_qualified",
        "release_enforcement_eligible",
        "official_release_verdict_modified",
    ):
        assert boundary[field_name] is False

    assert boundary[
        "development_evidence_only"
    ] is True


def test_minilibrispeech_selection_contains_no_raw_locator():
    serialized = str(
        build_asr_adversarial_minilibrispeech_selection_v1()
        .payload
    )

    assert "https://" not in serialized
    assert "http://" not in serialized


def test_minilibrispeech_selection_verifies_exact_identity():
    bundle = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    verified = (
        verify_asr_adversarial_minilibrispeech_selection_v1(
            payload=bundle.payload,
            expected_sha256=bundle.sha256,
        )
    )

    assert verified == bundle


def test_minilibrispeech_selection_rejects_tampering():
    bundle = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered[
        "evidence_boundary"
    ][
        "production_qualified"
    ] = True

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_minilibrispeech_selection_v1(
            payload=tampered,
            expected_sha256=bundle.sha256,
        )


def test_minilibrispeech_rehashed_substitution_is_unsupported():
    bundle = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    substituted = copy.deepcopy(
        bundle.payload
    )

    substituted["cases"][0][
        "commitments"
    ][
        "source_audio_sha256"
    ] = "a" * 64

    substituted_sha256 = (
        calculate_asr_adversarial_human_external_sha256(
            substituted
        )
    )

    assert substituted_sha256 != bundle.sha256

    with pytest.raises(
        HveeContractError,
        match="unsupported",
    ):
        verify_asr_adversarial_minilibrispeech_selection_v1(
            payload=substituted,
            expected_sha256=substituted_sha256,
        )


@pytest.mark.parametrize(
    "case",
    ASR_ADVERSARIAL_MINILIBRISPEECH_CASES,
)
def test_minilibrispeech_builds_valid_i4a_record_pair(
    case,
):
    provenance, rights = (
        build_asr_adversarial_minilibrispeech_record_pair_v1(
            case.utterance_id
        )
    )

    assert (
        verify_asr_adversarial_human_external_record_pair_v1(
            provenance=provenance,
            rights=rights,
        )
        == (
            provenance,
            rights,
        )
    )

    provenance_record = provenance.payload[
        "record"
    ]

    assert provenance_record[
        "case_id"
    ] == case.case_id

    assert provenance_record[
        "source_kind"
    ] == "licensed_dataset"

    assert provenance_record[
        "source_collection"
    ] == {
        "key": "openslr-mini-librispeech",
        "version": "slr31.dev-clean-2",
        "item_id": case.utterance_id,
    }

    assert provenance_record[
        "commitments"
    ][
        "source_audio_sha256"
    ] == case.source_audio_sha256

    assert provenance_record[
        "commitments"
    ][
        "reference_transcript_sha256"
    ] == case.reference_transcript_sha256

    assert provenance_record[
        "declared_metadata_commitments"
    ] == {
        "speaker_metadata_sha256": None,
        "recording_metadata_sha256": None,
    }

    rights_record = rights.payload[
        "record"
    ]

    assert rights_record[
        "case_id"
    ] == case.case_id

    assert rights_record[
        "rights_basis"
    ] == "dataset_license"

    assert rights_record[
        "repository_media_policy"
    ] == "not_committed"

    assert rights_record[
        "review_status"
    ] == "not_adjudicated"

    assert rights_record[
        "development_use_only"
    ] is True


def test_minilibrispeech_builds_all_eight_record_pairs():
    pairs = (
        build_asr_adversarial_minilibrispeech_record_pairs_v1()
    )

    assert len(pairs) == 8

    case_ids = tuple(
        provenance.payload[
            "record"
        ][
            "case_id"
        ]
        for provenance, _ in pairs
    )

    assert len(
        set(case_ids)
    ) == 8


def test_minilibrispeech_unknown_source_item_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="unsupported",
    ):
        get_asr_adversarial_minilibrispeech_case_v1(
            "9999-999999-9999"
        )


def test_minilibrispeech_source_speaker_ids_are_not_demographics():
    bundle = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    cases = bundle.payload[
        "cases"
    ]

    assert all(
        "source_defined_speaker_id" in case
        for case in cases
    )

    serialized = str(
        bundle.payload
    ).lower()

    for forbidden in (
        "gender",
        "ethnicity",
        "race",
        "male",
        "female",
        "microphone_model",
    ):
        assert forbidden not in serialized


def test_minilibrispeech_contract_is_publicly_exported():
    import hvee.packs.asr as asr_pack

    expected_names = (
        "ASR_ADVERSARIAL_MINILIBRISPEECH_ARCHIVE_SHA256",
        "ASR_ADVERSARIAL_MINILIBRISPEECH_CASES",
        "ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_KEY",
        "ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256",
        "ASRAdversarialMiniLibriSpeechCase",
        "ASRAdversarialMiniLibriSpeechSelectionBundle",
        "build_asr_adversarial_minilibrispeech_record_pair_v1",
        "build_asr_adversarial_minilibrispeech_record_pairs_v1",
        "build_asr_adversarial_minilibrispeech_selection_v1",
        "get_asr_adversarial_minilibrispeech_case_v1",
        "verify_asr_adversarial_minilibrispeech_selection_v1",
    )

    for name in expected_names:
        assert hasattr(
            asr_pack,
            name,
        )

        assert name in asr_pack.__all__


def test_minilibrispeech_record_pairs_bind_exact_rights_evidence():
    from hvee.packs.asr.adversarial_human_external_minilibrispeech_v1 import (
        ASR_ADVERSARIAL_MINILIBRISPEECH_RIGHTS_EVIDENCE_SHA256,
        ASR_ADVERSARIAL_MINILIBRISPEECH_TERMS_EVIDENCE_SHA256,
    )

    pairs = (
        build_asr_adversarial_minilibrispeech_record_pairs_v1()
    )

    for _, rights in pairs:
        evidence = rights.payload[
            "record"
        ][
            "evidence"
        ]

        assert evidence[
            "rights_evidence_sha256"
        ] == (
            ASR_ADVERSARIAL_MINILIBRISPEECH_RIGHTS_EVIDENCE_SHA256
        )

        assert evidence[
            "terms_evidence_sha256"
        ] == (
            ASR_ADVERSARIAL_MINILIBRISPEECH_TERMS_EVIDENCE_SHA256
        )


def test_minilibrispeech_cross_case_pair_is_rejected():
    pairs = (
        build_asr_adversarial_minilibrispeech_record_pairs_v1()
    )

    first_provenance, _ = pairs[0]
    _, second_rights = pairs[1]

    with pytest.raises(
        HveeContractError,
        match="same source",
    ):
        verify_asr_adversarial_human_external_record_pair_v1(
            provenance=first_provenance,
            rights=second_rights,
        )


def test_minilibrispeech_selection_case_ids_match_record_pairs():
    selection = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    selection_case_ids = tuple(
        case[
            "case_id"
        ]
        for case in selection.payload[
            "cases"
        ]
    )

    record_case_ids = tuple(
        provenance.payload[
            "record"
        ][
            "case_id"
        ]
        for provenance, _ in (
            build_asr_adversarial_minilibrispeech_record_pairs_v1()
        )
    )

    assert selection_case_ids == record_case_ids
