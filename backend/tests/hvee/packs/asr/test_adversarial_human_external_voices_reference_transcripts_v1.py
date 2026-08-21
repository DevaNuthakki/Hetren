from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import hashlib

import pytest

import hvee.packs.asr as asr_pack
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_COLLECTION_KEY,
    ASR_ADVERSARIAL_VOICES_COLLECTION_VERSION,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
    ASR_ADVERSARIAL_VOICES_DEVKIT_ARCHIVE_SHA256,
)
from hvee.packs.asr.adversarial_human_external_voices_reference_transcripts_v1 import (
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_ANGLE_DEGREES,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROW_COUNT,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROWS_PER_SOURCE,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_DISTRACTORS,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_KEY,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_MICROPHONE_IDS,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_ROOMS,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SELECTED_INDEX_SHA256,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_COUNT,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_ARCHIVE_PATH,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_BYTES,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_RETAINED_PATH,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_SHA256,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_VERSION,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S,
    ASRAdversarialVOiCESReferenceTranscriptsBundle,
    build_asr_adversarial_voices_reference_transcripts_v1,
    calculate_asr_adversarial_voices_reference_transcripts_sha256,
    verify_asr_adversarial_voices_reference_transcripts_v1,
)


EXPECTED_FIRST_TRANSCRIPT = (
    "cabbage salad chop or shave fine half "
    "a medium size head of cabbage that has "
    "been left in cold water until crisp "
    "then drain"
)

EXPECTED_SECOND_TRANSCRIPT = (
    "indeed if ever a general deserved honor "
    "grant had won it he had opened the "
    "mississippi to navigation and had "
    "captured nearly one hundred thousand "
    "prisoners and arms"
)


def _bundle(
) -> ASRAdversarialVOiCESReferenceTranscriptsBundle:
    return build_asr_adversarial_voices_reference_transcripts_v1()


def _payload(
) -> dict[str, object]:
    return copy.deepcopy(
        _bundle().payload
    )


def _sources(
    payload: dict[str, object],
) -> list[dict[str, object]]:
    sources = payload[
        "source_reference_transcripts"
    ]
    assert isinstance(
        sources,
        list,
    )
    assert all(
        isinstance(
            source,
            dict,
        )
        for source in sources
    )
    return sources


def test_frozen_identity_constants_are_exact():
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SCHEMA_VERSION
        == 1
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_VERSION
        == "1.0.0"
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_KEY
        == (
            "hetren.asr.adversarial-human-external-"
            "voices-reference-transcripts"
        )
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
        == (
            "b6a87eda150c732a13513ccc1b50e08e"
            "33195203800cd7c94c2a6bbddfa1fc45"
        )
    )


def test_official_train_index_commitment_is_exact():
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_ARCHIVE_PATH
        == "VOiCES_devkit/references/train_index.csv"
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_RETAINED_PATH
        == "references/train_index.csv"
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_BYTES
        == 7_170_342
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_SHA256
        == (
            "223219468240d96889dd74f52c26e081"
            "2453a24ae6462f76077d4b95819552b4"
        )
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SELECTED_INDEX_SHA256
        == (
            "5d32141bff6340beb4b7c47687e2824f"
            "f52ffaf52269a50530917aa6613b4d5b"
        )
    )


def test_selected_source_and_lattice_constants_are_exact():
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS
        == (
            (
                652,
                129742,
                3,
            ),
            (
                7850,
                111771,
                4,
            ),
        )
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_COUNT
        == 2
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROWS_PER_SOURCE
        == 32
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROW_COUNT
        == 64
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_ROOMS
        == (
            "rm1",
            "rm2",
            "rm3",
            "rm4",
        )
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_DISTRACTORS
        == (
            "babb",
            "musi",
            "none",
            "tele",
        )
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_MICROPHONE_IDS
        == (
            1,
            5,
        )
    )
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_ANGLE_DEGREES
        == 10
    )


def test_reference_transcripts_are_exact():
    assert (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS
        == (
            EXPECTED_FIRST_TRANSCRIPT,
            EXPECTED_SECOND_TRANSCRIPT,
        )
    )


def test_reference_transcript_hashes_match_exact_utf8_text():
    observed = tuple(
        hashlib.sha256(
            transcript.encode(
                "utf-8"
            )
        ).hexdigest()
        for transcript in (
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS
        )
    )

    assert observed == (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S
    )
    assert observed == (
        (
            "63f61783189d5e3ce9bc6e900e80d29b"
            "35a55775e07cc5d24698fc20b20d90f8"
        ),
        (
            "085ab0d18cd4d3e5e495fc38b6a69077"
            "695746d272d9f487548405392f8e97e9"
        ),
    )


def test_build_is_deterministic_and_frozen():
    first = _bundle()
    second = _bundle()

    assert first == second
    assert first is not second
    assert first.payload is not second.payload
    assert first.sha256 == (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
    )


def test_calculated_payload_identity_is_frozen():
    bundle = _bundle()

    assert (
        calculate_asr_adversarial_voices_reference_transcripts_sha256(
            bundle.payload
        )
        == bundle.sha256
        == ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
    )


def test_payload_binds_upstream_voices_evidence():
    upstream = _bundle().payload[
        "upstream"
    ]

    assert upstream == {
        "collection_key": (
            ASR_ADVERSARIAL_VOICES_COLLECTION_KEY
        ),
        "collection_version": (
            ASR_ADVERSARIAL_VOICES_COLLECTION_VERSION
        ),
        "voices_devkit_archive_sha256": (
            ASR_ADVERSARIAL_VOICES_DEVKIT_ARCHIVE_SHA256
        ),
        "controlled_voices_sha256": (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
        ),
        "babble_matched_control_sha256": (
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
        ),
        "train_index_archive_path": (
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_ARCHIVE_PATH
        ),
        "train_index_retained_path": (
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_RETAINED_PATH
        ),
        "train_index_bytes": (
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_BYTES
        ),
        "train_index_sha256": (
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_SHA256
        ),
        "selected_index_projection_sha256": (
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SELECTED_INDEX_SHA256
        ),
    }


def test_payload_binds_exact_source_keys_in_order():
    sources = _sources(
        _payload()
    )

    observed = tuple(
        (
            source["source_key"]["speaker_id"],
            source["source_key"]["chapter_id"],
            source["source_key"]["segment_id"],
        )
        for source in sources
    )

    assert observed == (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS
    )


def test_payload_binds_exact_source_paths():
    sources = _sources(
        _payload()
    )

    assert [
        source[
            "source_relative_path"
        ]
        for source in sources
    ] == [
        (
            "source-16k/train/sp0652/"
            "Lab41-SRI-VOiCES-src-"
            "sp0652-ch129742-sg0003.wav"
        ),
        (
            "source-16k/train/sp7850/"
            "Lab41-SRI-VOiCES-src-"
            "sp7850-ch111771-sg0004.wav"
        ),
    ]


def test_payload_binds_exact_reference_text_and_hashes():
    sources = _sources(
        _payload()
    )

    assert tuple(
        source[
            "reference_transcript"
        ]
        for source in sources
    ) == ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS

    assert tuple(
        source[
            "reference_transcript_sha256"
        ]
        for source in sources
    ) == ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S


def test_payload_binds_exact_source_media_statistics():
    sources = _sources(
        _payload()
    )

    assert [
        (
            source["source_sample_count"],
            source["source_sample_rate_hz"],
            source["source_duration_seconds"],
        )
        for source in sources
    ] == [
        (
            146_880,
            16_000,
            "9.18",
        ),
        (
            176_081,
            16_000,
            "11.0050625",
        ),
    ]


def test_payload_binds_exact_capture_row_counts():
    sources = _sources(
        _payload()
    )

    assert {
        source[
            "official_index_capture_row_count"
        ]
        for source in sources
    } == {
        32
    }

    verification = _bundle().payload[
        "verification"
    ]

    assert verification[
        "selected_source_count"
    ] == 2
    assert verification[
        "official_index_capture_row_count"
    ] == 64
    assert verification[
        "official_index_capture_rows_per_source"
    ] == 32


@pytest.mark.parametrize(
    "field",
    (
        "complete_train_index_bytes_verified",
        "complete_train_index_sha256_verified",
        "selected_rows_parsed_by_column_name",
        "exact_source_keys_verified",
        "source_paths_consistent_per_source",
        "reference_transcripts_consistent_per_source",
        "source_media_statistics_consistent_per_source",
        "exact_capture_condition_lattice_verified",
    ),
)
def test_verification_claims_are_exactly_positive(
    field: str,
):
    verification = _bundle().payload[
        "verification"
    ]

    assert verification[field] is True


def test_evidence_boundary_exposes_verified_reference_metadata():
    boundary = _bundle().payload[
        "evidence_boundary"
    ]

    assert boundary[
        "development_evidence_only"
    ] is True
    assert boundary[
        "official_dataset_reference_metadata_verified"
    ] is True
    assert boundary[
        "source_declared_reference_transcripts_bound"
    ] is True
    assert boundary[
        "matched_control_foreground_reference_text_ready"
    ] is True


@pytest.mark.parametrize(
    "field",
    (
        "source_audio_spoken_content_independently_verified",
        "babble_speaker_transcripts_verified",
        "secondary_speaker_identity_verified",
        "secondary_speaker_timing_verified",
        "speaker_overlap_condition_verified",
        "natural_crosstalk_verified",
        "adversarial_suite_built",
        "asr_execution_verified",
        "qualification_threshold_applied",
        "certification_issued",
        "production_qualified",
        "release_enforcement_eligible",
        "official_release_verdict_modified",
    ),
)
def test_evidence_boundary_does_not_overclaim(
    field: str,
):
    boundary = _bundle().payload[
        "evidence_boundary"
    ]

    assert boundary[field] is False


def test_verifier_accepts_only_exact_frozen_payload():
    bundle = _bundle()

    verified = (
        verify_asr_adversarial_voices_reference_transcripts_v1(
            payload=copy.deepcopy(
                bundle.payload
            ),
            expected_sha256=bundle.sha256,
        )
    )

    assert verified == bundle


@pytest.mark.parametrize(
    "expected_sha256",
    (
        "0" * 64,
        "A" * 64,
        "short",
        7,
        None,
    ),
)
def test_verifier_rejects_unsupported_or_invalid_identity(
    expected_sha256: object,
):
    with pytest.raises(
        HveeContractError
    ):
        verify_asr_adversarial_voices_reference_transcripts_v1(
            payload=_payload(),
            expected_sha256=expected_sha256,
        )


@pytest.mark.parametrize(
    (
        "path",
        "replacement",
    ),
    (
        (
            (
                "upstream",
                "train_index_sha256",
            ),
            "0" * 64,
        ),
        (
            (
                "upstream",
                "train_index_bytes",
            ),
            7_170_341,
        ),
        (
            (
                "upstream",
                "selected_index_projection_sha256",
            ),
            "0" * 64,
        ),
        (
            (
                "verification",
                "official_index_capture_row_count",
            ),
            63,
        ),
        (
            (
                "evidence_boundary",
                "asr_execution_verified",
            ),
            True,
        ),
    ),
)
def test_verifier_rejects_top_level_evidence_mutation(
    path: tuple[str, str],
    replacement: object,
):
    payload = _payload()
    parent = payload[path[0]]
    assert isinstance(
        parent,
        dict,
    )
    parent[path[1]] = replacement

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_reference_transcripts_v1(
            payload=payload,
            expected_sha256=(
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
            ),
        )


@pytest.mark.parametrize(
    (
        "source_index",
        "field",
        "replacement",
    ),
    (
        (
            0,
            "reference_transcript",
            "changed transcript",
        ),
        (
            0,
            "reference_transcript_sha256",
            "0" * 64,
        ),
        (
            0,
            "source_relative_path",
            "source-16k/train/substituted.wav",
        ),
        (
            0,
            "source_sample_count",
            146_879,
        ),
        (
            1,
            "reference_transcript",
            "changed transcript",
        ),
        (
            1,
            "source_duration_seconds",
            "11.0",
        ),
    ),
)
def test_verifier_rejects_source_record_mutation(
    source_index: int,
    field: str,
    replacement: object,
):
    payload = _payload()
    sources = _sources(
        payload
    )
    sources[source_index][field] = replacement

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_reference_transcripts_v1(
            payload=payload,
            expected_sha256=(
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
            ),
        )


def test_verifier_rejects_source_reordering():
    payload = _payload()
    sources = _sources(
        payload
    )
    sources.reverse()

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_reference_transcripts_v1(
            payload=payload,
            expected_sha256=(
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
            ),
        )


def test_verifier_rejects_extra_payload_field():
    payload = _payload()
    payload["unexpected"] = True

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_reference_transcripts_v1(
            payload=payload,
            expected_sha256=(
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
            ),
        )


def test_bundle_rejects_non_object_payload():
    with pytest.raises(
        HveeContractError,
        match="payload must be an object",
    ):
        ASRAdversarialVOiCESReferenceTranscriptsBundle(
            payload=[],
            sha256=(
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
            ),
        )


def test_bundle_rejects_invalid_or_mismatched_hash():
    with pytest.raises(
        HveeContractError
    ):
        ASRAdversarialVOiCESReferenceTranscriptsBundle(
            payload=_payload(),
            sha256="0" * 64,
        )


def test_bundle_is_frozen_slots_dataclass():
    bundle = _bundle()

    with pytest.raises(
        FrozenInstanceError
    ):
        bundle.sha256 = "0" * 64

    with pytest.raises(
        (
            AttributeError,
            TypeError,
        )
    ):
        bundle.unexpected = True


@pytest.mark.parametrize(
    "name",
    (
        "ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256",
        "ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS",
        "ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS",
        "ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S",
        "ASRAdversarialVOiCESReferenceTranscriptsBundle",
        "build_asr_adversarial_voices_reference_transcripts_v1",
        "calculate_asr_adversarial_voices_reference_transcripts_sha256",
        "verify_asr_adversarial_voices_reference_transcripts_v1",
    ),
)
def test_public_asr_pack_exports_reference_transcript_api(
    name: str,
):
    assert name in asr_pack.__all__
    assert hasattr(
        asr_pack,
        name,
    )
