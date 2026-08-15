from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_minilibrispeech_v1 import (
    ASR_ADVERSARIAL_MINILIBRISPEECH_CASES,
    ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256,
    build_asr_adversarial_minilibrispeech_record_pairs_v1,
)
from hvee.packs.asr.adversarial_human_external_portfolio_v1 import (
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_KEY,
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SCHEMA_VERSION,
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SHA256,
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_VERSION,
    ASRAdversarialHumanExternalPortfolioBundle,
    build_asr_adversarial_human_external_portfolio_v1,
    calculate_asr_adversarial_human_external_portfolio_sha256,
    verify_asr_adversarial_human_external_portfolio_v1,
)


def test_human_external_portfolio_identity_is_frozen():
    first = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    second = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    assert first == second

    assert first.sha256 == (
        ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SHA256
    )

    assert len(
        first.sha256
    ) == 64

    assert first.sha256 == (
        first.sha256.lower()
    )


def test_human_external_portfolio_binds_exact_artifact_identity():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    assert bundle.payload[
        "schema_version"
    ] == (
        ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SCHEMA_VERSION
    )

    artifact = bundle.payload[
        "artifact"
    ]

    assert artifact == {
        "key": (
            ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_KEY
        ),
        "version": (
            ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_VERSION
        ),
        "type": (
            "source_visible_adversarial_"
            "human_external_source_portfolio"
        ),
    }


def test_human_external_portfolio_binds_frozen_minilibrispeech_selection():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    slices = bundle.payload[
        "source_slices"
    ]

    assert isinstance(
        slices,
        list,
    )

    assert len(
        slices
    ) == 1

    source_slice = slices[0]

    assert source_slice[
        "selection_sha256"
    ] == (
        ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256
    )

    assert source_slice[
        "selected_asset_count"
    ] == 8


def test_human_external_portfolio_population_is_exact():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    population = bundle.payload[
        "population"
    ]

    assert population == {
        "selected_asset_count": 8,
        "distinct_source_defined_speaker_id_count": 8,
        "distinct_source_defined_chapter_id_count": 8,
        "distinct_source_audio_sha256_count": 8,
        "distinct_reference_transcript_sha256_count": 8,
    }


def test_human_external_portfolio_reports_only_measured_technical_facts():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    technical = bundle.payload[
        "technical_portfolio"
    ]

    assert technical[
        "codec_names"
    ] == [
        "flac"
    ]

    assert technical[
        "format_names"
    ] == [
        "flac"
    ]

    assert technical[
        "sample_rates_hz"
    ] == [
        16_000
    ]

    assert technical[
        "channel_counts"
    ] == [
        1
    ]

    assert technical[
        "duration_ms"
    ] == {
        "minimum": 1_850,
        "maximum": 22_680,
        "total": 84_085,
        "distinct_value_count": 8,
    }

    assert technical[
        "audio_bytes"
    ] == {
        "total": 1_544_941,
    }


def test_human_external_portfolio_declared_metadata_is_absent():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    coverage = bundle.payload[
        "declared_metadata_coverage"
    ]

    assert coverage == {
        "selected_asset_count": 8,
        "speaker_metadata_commitment_count": 0,
        "recording_metadata_commitment_count": 0,
        "speaker_metadata_complete": False,
        "recording_metadata_complete": False,
    }

    for case in bundle.payload[
        "cases"
    ]:
        assert case[
            "declared_metadata_commitments"
        ] == {
            "speaker_metadata_sha256": None,
            "recording_metadata_sha256": None,
        }


def test_human_external_portfolio_binds_all_source_defined_identifiers():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    cases = bundle.payload[
        "cases"
    ]

    assert len(
        cases
    ) == 8

    assert {
        case[
            "source_defined_speaker_id"
        ]
        for case in cases
    } == {
        case.speaker_id
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    }

    assert {
        case[
            "source_defined_chapter_id"
        ]
        for case in cases
    } == {
        case.chapter_id
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    }


def test_human_external_portfolio_binds_provenance_and_rights_records():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    expected_pairs = {
        provenance.payload[
            "record"
        ][
            "case_id"
        ]: (
            provenance.sha256,
            rights.sha256,
        )
        for provenance, rights in (
            build_asr_adversarial_minilibrispeech_record_pairs_v1()
        )
    }

    for case in bundle.payload[
        "cases"
    ]:
        commitments = case[
            "commitments"
        ]

        expected_provenance, expected_rights = (
            expected_pairs[
                case[
                    "case_id"
                ]
            ]
        )

        assert commitments[
            "provenance_record_sha256"
        ] == expected_provenance

        assert commitments[
            "rights_record_sha256"
        ] == expected_rights


def test_human_external_portfolio_rights_boundary_remains_non_authoritative():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    rights = bundle.payload[
        "rights_portfolio"
    ]

    assert rights == {
        "record_count": 8,
        "not_adjudicated_record_count": 8,
        "development_use_only_record_count": 8,
        "rights_bases": [
            "dataset_license"
        ],
        "repository_media_policies": [
            "not_committed"
        ],
    }


def test_human_external_portfolio_scientific_boundary_stays_negative():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "source_speaker_ids_are_source_defined"
    ] is True

    assert boundary[
        "source_chapter_ids_are_source_defined"
    ] is True

    for field_name in (
        "source_chapter_ids_treated_as_recording_sessions",
        "source_chapter_ids_treated_as_recording_environments",
        "speaker_attributes_inferred",
        "accent_inferred",
        "microphone_class_inferred",
        "recording_environment_inferred",
        "technical_variation_establishes_acoustic_diversity",
        "human_acoustic_diversity_established",
        "rights_adjudicated",
        "qualification_threshold_applied",
        "certification_issued",
        "production_qualified",
        "release_enforcement_eligible",
        "official_release_verdict_modified",
    ):
        assert boundary[
            field_name
        ] is False

    assert boundary[
        "development_evidence_only"
    ] is True


def test_human_external_portfolio_contains_no_run_timestamp():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    serialized = repr(
        bundle.payload
    ).lower()

    assert "timestamp" not in serialized
    assert "created_at" not in serialized
    assert "generated_at" not in serialized


def test_human_external_portfolio_verifies_exact_identity():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    verified = (
        verify_asr_adversarial_human_external_portfolio_v1(
            payload=bundle.payload,
            expected_sha256=bundle.sha256,
        )
    )

    assert verified == bundle


def test_human_external_portfolio_rejects_tampering():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
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
        verify_asr_adversarial_human_external_portfolio_v1(
            payload=tampered,
            expected_sha256=bundle.sha256,
        )


def test_human_external_portfolio_rehashed_substitution_is_unsupported():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered[
        "population"
    ][
        "distinct_source_defined_speaker_id_count"
    ] = 7

    substituted_sha256 = (
        calculate_asr_adversarial_human_external_portfolio_sha256(
            tampered
        )
    )

    assert substituted_sha256 != (
        bundle.sha256
    )

    with pytest.raises(
        HveeContractError,
        match="identity is unsupported",
    ):
        verify_asr_adversarial_human_external_portfolio_v1(
            payload=tampered,
            expected_sha256=substituted_sha256,
        )


def test_human_external_portfolio_bundle_rejects_wrong_digest():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    with pytest.raises(
        HveeContractError,
        match="does not match its payload",
    ):
        ASRAdversarialHumanExternalPortfolioBundle(
            payload=bundle.payload,
            sha256="0" * 64,
        )


def test_human_external_portfolio_case_order_matches_frozen_selection():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    portfolio_case_ids = tuple(
        case[
            "case_id"
        ]
        for case in bundle.payload[
            "cases"
        ]
    )

    expected_case_ids = tuple(
        case.case_id
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    )

    assert portfolio_case_ids == (
        expected_case_ids
    )

    assert len(
        portfolio_case_ids
    ) == len(
        set(
            portfolio_case_ids
        )
    )


def test_human_external_portfolio_contains_no_raw_source_locator():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    serialized = repr(
        bundle.payload
    )

    assert "LibriSpeech/" not in serialized
    assert "/Users/" not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized

    for case in bundle.payload[
        "cases"
    ]:
        commitments = case[
            "commitments"
        ]

        assert (
            "source_locator_sha256"
            in commitments
        )

        assert len(
            commitments[
                "source_locator_sha256"
            ]
        ) == 64


def test_human_external_portfolio_does_not_convert_chapters_to_sessions():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "source_chapter_ids_are_source_defined"
    ] is True

    assert boundary[
        "source_chapter_ids_treated_as_recording_sessions"
    ] is False

    assert boundary[
        "source_chapter_ids_treated_as_recording_environments"
    ] is False


def test_human_external_portfolio_technical_uniformity_is_not_acoustic_claim():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    technical = bundle.payload[
        "technical_portfolio"
    ]

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert len(
        technical[
            "codec_names"
        ]
    ) == 1

    assert len(
        technical[
            "sample_rates_hz"
        ]
    ) == 1

    assert len(
        technical[
            "channel_counts"
        ]
    ) == 1

    assert boundary[
        "technical_variation_establishes_acoustic_diversity"
    ] is False

    assert boundary[
        "human_acoustic_diversity_established"
    ] is False


def test_human_external_portfolio_has_no_inferred_human_attributes():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    for field_name in (
        "speaker_attributes_inferred",
        "accent_inferred",
        "microphone_class_inferred",
        "recording_environment_inferred",
    ):
        assert boundary[
            field_name
        ] is False

    serialized = repr(
        bundle.payload
    ).lower()

    for prohibited_field in (
        "gender",
        "ethnicity",
        "race",
        "age_group",
        "microphone_model",
        "room_type",
    ):
        assert prohibited_field not in (
            serialized
        )


def test_human_external_portfolio_case_rights_are_all_development_only():
    bundle = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    cases = bundle.payload[
        "cases"
    ]

    assert len(
        cases
    ) == 8

    for case in cases:
        rights = case[
            "rights_boundary"
        ]

        assert rights == {
            "rights_basis": (
                "dataset_license"
            ),
            "repository_media_policy": (
                "not_committed"
            ),
            "review_status": (
                "not_adjudicated"
            ),
            "development_use_only": True,
        }


def test_human_external_portfolio_is_publicly_exported():
    import hvee.packs.asr as asr

    expected_names = (
        "ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_KEY",
        "ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SCHEMA_VERSION",
        "ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SHA256",
        "ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_VERSION",
        "ASRAdversarialHumanExternalPortfolioBundle",
        "build_asr_adversarial_human_external_portfolio_v1",
        "calculate_asr_adversarial_human_external_portfolio_sha256",
        "verify_asr_adversarial_human_external_portfolio_v1",
    )

    for name in expected_names:
        assert hasattr(
            asr,
            name,
        )

        assert name in (
            asr.__all__
        )

    assert (
        asr.ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SHA256
        == ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SHA256
    )
