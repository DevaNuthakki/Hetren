from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import hashlib
import json

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_evidence import (
    ASRAdversarialOverlapCondition,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_BYTES,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_SHA256,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ORDERED_PAIR_SHA256,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256,
    ASRAdversarialVOiCESBabbleMatchedControlBundle,
    build_asr_adversarial_voices_babble_matched_control_v1,
    calculate_asr_adversarial_voices_babble_matched_control_sha256,
    verify_asr_adversarial_voices_babble_matched_control_v1,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
)


def _ordered_digest(
) -> str:
    raw = json.dumps(
        list(
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S
        ),
        ensure_ascii=False,
        sort_keys=False,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        raw
    ).hexdigest()


def test_builds_exact_frozen_contract():
    bundle = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    assert isinstance(
        bundle,
        ASRAdversarialVOiCESBabbleMatchedControlBundle,
    )

    assert bundle.sha256 == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
    )

    assert (
        calculate_asr_adversarial_voices_babble_matched_control_sha256(
            bundle.payload
        )
        == bundle.sha256
    )


def test_binds_exact_external_evidence_identity():
    bundle = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    upstream = bundle.payload[
        "upstream"
    ]

    assert upstream[
        "controlled_voices_sha256"
    ] == ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256

    assert upstream[
        "external_evidence_sha256"
    ] == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_SHA256
    )

    assert upstream[
        "external_evidence_bytes"
    ] == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_BYTES
    )

    assert (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_SHA256
        == (
            "a9958c8c0520ce2b070bf16b9a10ef8d"
            "23dcf65e50e5f8358b26f95d718941c4"
        )
    )

    assert (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_BYTES
        == 19_254
    )


def test_binds_exact_ordered_pair_identity():
    assert len(
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S
    ) == 16

    assert len(
        set(
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S
        )
    ) == 16

    assert _ordered_digest() == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ORDERED_PAIR_SHA256
    )

    assert (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ORDERED_PAIR_SHA256
        == (
            "dd13eef17694c22689dacaa253e465ec"
            "01edcef33bf8d17f326e486e1663ce64"
        )
    )


def test_matched_control_design_is_exact():
    bundle = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    design = bundle.payload[
        "matched_control_design"
    ]

    assert design[
        "pair_count"
    ] == ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT

    assert design[
        "audio_file_count"
    ] == ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT

    assert design[
        "pair_count"
    ] == 16

    assert design[
        "audio_file_count"
    ] == 32

    assert design[
        "foreground_source_count"
    ] == 2

    assert design[
        "rooms"
    ] == [
        "rm1",
        "rm2",
        "rm3",
        "rm4",
    ]

    assert design[
        "microphone_ids"
    ] == [
        1,
        5,
    ]

    assert design[
        "microphone_type_codes"
    ] == [
        "stu",
    ]

    assert design[
        "microphone_location_codes"
    ] == [
        "clo",
        "far",
    ]

    assert design[
        "constant_angle_degrees"
    ] == 10

    assert design[
        "interference_condition"
    ] == "babb"

    assert design[
        "control_condition"
    ] == "none"

    assert tuple(
        design[
            "ordered_pair_sha256s"
        ]
    ) == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S
    )


def test_source_methodology_is_explicitly_source_declared():
    methodology = (
        build_asr_adversarial_voices_babble_matched_control_v1()
        .payload[
            "source_methodology"
        ]
    )

    assert methodology == {
        "real_room_recording_source_declared": True,
        "simultaneous_distractor_playback_source_declared": True,
        "babble_distractor_source_declared": True,
        "no_distractor_control_source_declared": True,
        "distractor_distance_metadata_source_declared": True,
    }


def test_boundary_establishes_only_narrow_interference_authority():
    boundary = (
        build_asr_adversarial_voices_babble_matched_control_v1()
        .payload[
            "evidence_boundary"
        ]
    )

    assert boundary[
        "development_evidence_only"
    ] is True

    assert boundary[
        "source_declared_real_room_recording"
    ] is True

    assert boundary[
        "source_declared_simultaneous_distractor_playback"
    ] is True

    assert boundary[
        "source_declared_babble_interference"
    ] is True

    assert boundary[
        "matched_no_distractor_control_verified"
    ] is True

    assert boundary[
        "selected_media_bytes_reverified"
    ] is True

    assert boundary[
        "physical_acoustic_babble_interference_supported"
    ] is True

    assert boundary[
        "real_room_capture_supported"
    ] is True

    assert boundary[
        "selected_capture_is_post_hoc_digital_mix"
    ] is False


@pytest.mark.parametrize(
    "field",
    (
        "live_human_conversational_overlap_verified",
        "secondary_speaker_identity_verified",
        "secondary_speaker_transcript_verified",
        "secondary_speaker_timing_verified",
        "speaker_overlap_condition_verified",
        "natural_crosstalk_verified",
        "spoken_content_independently_verified",
        "asr_execution_verified",
        "rights_adjudicated",
        "qualification_threshold_applied",
        "certification_issued",
        "production_qualified",
        "release_enforcement_eligible",
        "official_release_verdict_modified",
    ),
)
def test_boundary_does_not_escalate_unearned_authority(
    field: str,
):
    boundary = (
        build_asr_adversarial_voices_babble_matched_control_v1()
        .payload[
            "evidence_boundary"
        ]
    )

    assert boundary[
        field
    ] is False


def test_existing_overlap_enum_remains_separate():
    assert tuple(
        item.value
        for item in ASRAdversarialOverlapCondition
    ) == (
        "none",
        "non_critical",
        "critical",
    )

    boundary = (
        build_asr_adversarial_voices_babble_matched_control_v1()
        .payload[
            "evidence_boundary"
        ]
    )

    assert boundary[
        "speaker_overlap_condition_verified"
    ] is False


def test_verifier_accepts_exact_contract():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    verified = (
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=expected.payload,
            expected_sha256=expected.sha256,
        )
    )

    assert verified == expected


def test_verifier_rejects_wrong_expected_identity():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    with pytest.raises(
        HveeContractError,
        match="identity is unsupported",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=expected.payload,
            expected_sha256=(
                "0" * 64
            ),
        )


def test_verifier_rejects_tampered_pair_identity():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "matched_control_design"
    ][
        "ordered_pair_sha256s"
    ][0] = (
        "0" * 64
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_bundle_rejects_payload_hash_mismatch():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "matched_control_design"
    ][
        "pair_count"
    ] = 15

    with pytest.raises(
        HveeContractError,
        match="does not match its payload",
    ):
        ASRAdversarialVOiCESBabbleMatchedControlBundle(
            payload=payload,
            sha256=expected.sha256,
        )


def test_bundle_is_frozen_slots_dataclass():
    bundle = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    assert "__slots__" in (
        type(
            bundle
        ).__dict__
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        bundle.sha256 = (
            "0" * 64
        )


def test_payload_contains_no_host_paths_or_urls():
    payload = (
        build_asr_adversarial_voices_babble_matched_control_v1()
        .payload
    )

    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
    )

    for forbidden in (
        "/Users/",
        "/private/",
        "Documents/hetren-local-evidence",
        "file://",
        "http://",
        "https://",
        "s3://",
    ):
        assert forbidden not in text


def test_bundle_rejects_rehashed_authority_escalation():
    """A matching hash must not turn an altered payload into trusted v1 evidence."""

    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "evidence_boundary"
    ][
        "speaker_overlap_condition_verified"
    ] = True

    altered_sha256 = (
        calculate_asr_adversarial_voices_babble_matched_control_sha256(
            payload
        )
    )

    assert altered_sha256 != (
        expected.sha256
    )

    with pytest.raises(
        HveeContractError,
        match="identity|unsupported|canonical",
    ):
        ASRAdversarialVOiCESBabbleMatchedControlBundle(
            payload=payload,
            sha256=altered_sha256,
        )


def test_bundle_rejects_rehashed_upstream_identity_substitution():
    """A caller cannot mint another supported v1 artifact by rehashing it."""

    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "upstream"
    ][
        "external_evidence_sha256"
    ] = (
        "0" * 64
    )

    altered_sha256 = (
        calculate_asr_adversarial_voices_babble_matched_control_sha256(
            payload
        )
    )

    assert altered_sha256 != (
        expected.sha256
    )

    with pytest.raises(
        HveeContractError,
        match="identity|unsupported|canonical",
    ):
        ASRAdversarialVOiCESBabbleMatchedControlBundle(
            payload=payload,
            sha256=altered_sha256,
        )


def test_verifier_rejects_boolean_schema_version_substitution():
    """JSON true must not compare equal to integer schema version 1."""

    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "schema_version"
    ] = True

    assert (
        calculate_asr_adversarial_voices_babble_matched_control_sha256(
            payload
        )
        != expected.sha256
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_boolean_microphone_id_substitution():
    """JSON true must not compare equal to microphone ID 1."""

    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "matched_control_design"
    ][
        "microphone_ids"
    ][0] = True

    assert (
        calculate_asr_adversarial_voices_babble_matched_control_sha256(
            payload
        )
        != expected.sha256
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_float_integer_substitution():
    """JSON 16.0 must not compare equal to integer pair count 16."""

    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "matched_control_design"
    ][
        "pair_count"
    ] = 16.0

    assert (
        calculate_asr_adversarial_voices_babble_matched_control_sha256(
            payload
        )
        != expected.sha256
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_reordered_pair_commitments():
    """Pair ordering is part of the frozen experimental identity."""

    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    pair_hashes = payload[
        "matched_control_design"
    ][
        "ordered_pair_sha256s"
    ]

    pair_hashes[
        0
    ], pair_hashes[
        1
    ] = (
        pair_hashes[
            1
        ],
        pair_hashes[
            0
        ],
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_accepts_canonically_equivalent_mapping_order():
    """JSON object key insertion order is not evidence identity."""

    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = dict(
        reversed(
            tuple(
                expected.payload.items()
            )
        )
    )

    assert (
        calculate_asr_adversarial_voices_babble_matched_control_sha256(
            payload
        )
        == expected.sha256
    )

    verified = (
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )
    )

    assert verified == expected


def test_verifier_rejects_duplicate_pair_commitment():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    pair_hashes = payload[
        "matched_control_design"
    ][
        "ordered_pair_sha256s"
    ]

    pair_hashes[
        1
    ] = pair_hashes[
        0
    ]

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_missing_pair_commitment():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "matched_control_design"
    ][
        "ordered_pair_sha256s"
    ].pop()

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_extra_pair_commitment():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "matched_control_design"
    ][
        "ordered_pair_sha256s"
    ].append(
        payload[
            "matched_control_design"
        ][
            "ordered_pair_sha256s"
        ][0]
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_malformed_pair_commitment():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "matched_control_design"
    ][
        "ordered_pair_sha256s"
    ][0] = "not-a-sha256"

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_wrong_controlled_upstream_identity():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "upstream"
    ][
        "controlled_voices_sha256"
    ] = (
        "0" * 64
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_missing_evidence_boundary_field():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    del payload[
        "evidence_boundary"
    ][
        "speaker_overlap_condition_verified"
    ]

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


@pytest.mark.parametrize(
    "payload",
    (
        None,
        [],
        (),
        "not-an-object",
        1,
        True,
    ),
)
def test_verifier_rejects_non_object_payload(
    payload: object,
):
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_non_json_serializable_payload():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "unexpected"
    ] = {
        "not",
        "json",
        "serializable",
    }

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_non_finite_numeric_payload():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "matched_control_design"
    ][
        "pair_count"
    ] = float(
        "nan"
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=payload,
            expected_sha256=expected.sha256,
        )


def test_verifier_rejects_malformed_expected_sha256():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    with pytest.raises(
        HveeContractError,
        match="lowercase SHA-256",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=expected.payload,
            expected_sha256="not-a-sha256",
        )


def test_verifier_rejects_uppercase_expected_sha256():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    with pytest.raises(
        HveeContractError,
        match="lowercase SHA-256",
    ):
        verify_asr_adversarial_voices_babble_matched_control_v1(
            payload=expected.payload,
            expected_sha256=(
                expected.sha256.upper()
            ),
        )


def test_exact_v1_constructor_accepts_only_exact_identity():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    rebuilt = (
        ASRAdversarialVOiCESBabbleMatchedControlBundle(
            payload=copy.deepcopy(
                expected.payload
            ),
            sha256=expected.sha256,
        )
    )

    assert rebuilt == expected


def test_exact_v1_constructor_rejects_exact_payload_with_wrong_identity():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    with pytest.raises(
        HveeContractError,
        match="identity is unsupported",
    ):
        ASRAdversarialVOiCESBabbleMatchedControlBundle(
            payload=copy.deepcopy(
                expected.payload
            ),
            sha256=(
                "0" * 64
            ),
        )


def test_exact_v1_constructor_rejects_modified_payload_with_frozen_identity():
    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    payload = copy.deepcopy(
        expected.payload
    )

    payload[
        "evidence_boundary"
    ][
        "production_qualified"
    ] = True

    with pytest.raises(
        HveeContractError,
        match="identity is unsupported",
    ):
        ASRAdversarialVOiCESBabbleMatchedControlBundle(
            payload=payload,
            sha256=expected.sha256,
        )



def test_package_exports_i4e_a_supported_api_once():
    import hvee.packs.asr as asr
    import hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 as module

    expected = (
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ANGLE_DEGREES",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_BYTES",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_SHA256",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_KEY",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_IDS",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_LOCATIONS",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_TYPES",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ORDERED_PAIR_SHA256",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ROOMS",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SCHEMA_VERSION",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SOURCE_COUNT",
        "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_VERSION",
        "ASRAdversarialVOiCESBabbleMatchedControlBundle",
        "build_asr_adversarial_voices_babble_matched_control_v1",
        "calculate_asr_adversarial_voices_babble_matched_control_sha256",
        "verify_asr_adversarial_voices_babble_matched_control_v1",
    )

    assert expected == tuple(
        module.__all__
    )

    for name in expected:
        assert hasattr(
            asr,
            name,
        )

        assert name in asr.__all__

        assert asr.__all__.count(
            name
        ) == 1

        assert getattr(
            asr,
            name,
        ) is getattr(
            module,
            name,
        )

    for private_name in (
        "_matched_control_payload",
        "_ordered_pair_hashes_sha256",
        "_require_sha256",
    ):
        assert private_name not in (
            asr.__all__
        )
