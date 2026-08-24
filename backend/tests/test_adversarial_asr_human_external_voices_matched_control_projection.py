from dataclasses import fields
from dataclasses import FrozenInstanceError
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from app.adversarial_asr_human_external_voices_matched_control_projection import (
    ASRAdversarialVOiCESMatchedControlPair,
    ASRAdversarialVOiCESMatchedControlPairKey,
    ASRAdversarialVOiCESMatchedControlProjectionBundle,
    ASRAdversarialVOiCESMatchedControlProjectionError,
    project_asr_adversarial_voices_babble_matched_control_v1,
)
from app.adversarial_asr_human_external_voices_materialization_service import (
    ASRAdversarialVOiCESMaterializedCaptureCondition,
    ASRAdversarialVOiCESMaterializedEvidence,
    ASRAdversarialVOiCESMaterializedMedia,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
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


def _evidence(
    *,
    media: tuple[
        ASRAdversarialVOiCESMaterializedMedia,
        ...,
    ] | None = None,
    controlled_contract_sha256: str = (
        ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
    ),
) -> ASRAdversarialVOiCESMaterializedEvidence:
    return ASRAdversarialVOiCESMaterializedEvidence(
        controlled_contract_sha256=(
            controlled_contract_sha256
        ),
        identity_chain_sha256=_sha256(
            "identity-chain"
        ),
        selection_sha256=_sha256(
            "selection"
        ),
        materialization_manifest_sha256=_sha256(
            "materialization-manifest"
        ),
        media_report_sha256=_sha256(
            "media-report"
        ),
        observation_sha256=_sha256(
            "observation"
        ),
        rights_manifest_sha256=_sha256(
            "rights-manifest"
        ),
        media=(
            _media_population()
            if media is None
            else media
        ),
    )


def _project(
) -> ASRAdversarialVOiCESMatchedControlProjectionBundle:
    return (
        project_asr_adversarial_voices_babble_matched_control_v1(
            _evidence()
        )
    )


def test_projects_exact_frozen_matched_control_population():
    projection = _project()

    assert isinstance(
        projection,
        ASRAdversarialVOiCESMatchedControlProjectionBundle,
    )

    assert len(
        projection.pairs
    ) == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
    )

    assert sum(
        2
        for _pair in projection.pairs
    ) == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT
    )

    assert {
        pair.key.source_key
        for pair in projection.pairs
    } == set(
        ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
    )


def test_projection_pairs_are_deterministically_ordered():
    projection = _project()
    keys = tuple(
        pair.key
        for pair in projection.pairs
    )

    assert keys == tuple(
        sorted(
            keys
        )
    )


def test_each_pair_contains_exact_babble_and_control_conditions():
    projection = _project()

    for pair in projection.pairs:
        interference = (
            pair.interference.require_capture_condition()
        )
        control = (
            pair.control.require_capture_condition()
        )

        assert interference.distractor == (
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE
        )
        assert control.distractor == (
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL
        )
        assert interference.room == control.room
        assert (
            interference.microphone_id
            == control.microphone_id
        )
        assert (
            interference.angle_degrees
            == control.angle_degrees
        )


def test_projection_binds_exact_upstream_evidence_identities():
    projection = _project()

    assert projection.controlled_contract_sha256 == (
        ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
    )
    assert projection.matched_control_contract_sha256 == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
    )

    upstream = projection.payload[
        "upstream"
    ]

    assert upstream[
        "identity_chain_sha256"
    ] == _sha256(
        "identity-chain"
    )
    assert upstream[
        "selection_sha256"
    ] == _sha256(
        "selection"
    )
    assert upstream[
        "rights_manifest_sha256"
    ] == _sha256(
        "rights-manifest"
    )


def test_projection_payload_and_sha256_are_deterministic():
    first = _project()
    second = _project()

    assert first.payload == second.payload
    assert first.sha256 == second.sha256
    assert len(
        first.sha256
    ) == 64


def test_projection_preserves_fail_closed_authority_boundary():
    projection = _project()
    boundary = projection.payload[
        "evidence_boundary"
    ]

    assert projection.development_evidence_only is True
    assert projection.reference_transcripts_projected is False
    assert projection.adversarial_suite_built is False
    assert projection.asr_execution_verified is False
    assert projection.qualification_threshold_applied is False
    assert projection.production_qualified is False
    assert projection.release_enforcement_eligible is False
    assert projection.official_release_verdict_modified is False

    assert boundary == {
        "development_evidence_only": True,
        "verified_materialized_media_consumed": True,
        "matched_babble_control_pairs_projected": True,
        "raw_audio_embedded": False,
        "reference_transcripts_projected": False,
        "adversarial_suite_built": False,
        "asr_execution_verified": False,
        "qualification_threshold_applied": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def test_projection_fails_closed_before_suite_construction():
    projection = _project()

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlProjectionError,
        match="reference transcripts",
    ):
        projection.require_adversarial_suite_ready()


def test_projection_requires_verified_materialized_evidence():
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlProjectionError,
        match="verified materialized evidence",
    ):
        project_asr_adversarial_voices_babble_matched_control_v1(
            object()
        )


def test_projection_rejects_wrong_controlled_contract_identity():
    evidence = _evidence(
        controlled_contract_sha256=(
            "0" * 64
        )
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlProjectionError,
        match="upstream identity",
    ):
        project_asr_adversarial_voices_babble_matched_control_v1(
            evidence
        )


def test_projection_rejects_missing_pair_capture():
    media = tuple(
        value
        for value in _media_population()
        if not (
            value.kind == "capture"
            and value.source_key
            == ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS[
                0
            ]
            and value.require_capture_condition().room
            == "rm1"
            and value.require_capture_condition().microphone_id
            == 1
            and value.require_capture_condition().distractor
            == ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL
        )
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlProjectionError,
        match="pair is incomplete",
    ):
        project_asr_adversarial_voices_babble_matched_control_v1(
            _evidence(
                media=media
            )
        )


def test_projection_rejects_duplicate_capture_condition():
    duplicate = _capture_media(
        source_key=(
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS[
                0
            ]
        ),
        room="rm1",
        distractor=(
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE
        ),
        microphone_id=1,
        suffix="-duplicate",
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlProjectionError,
        match="duplicate capture condition",
    ):
        project_asr_adversarial_voices_babble_matched_control_v1(
            _evidence(
                media=(
                    _media_population()
                    + (
                        duplicate,
                    )
                )
            )
        )


def test_projection_rejects_unmatched_sample_count():
    media = list(
        _media_population()
    )

    for index, value in enumerate(
        media
    ):
        if (
            value.kind == "capture"
            and value.require_capture_condition().distractor
            == ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE
        ):
            media[
                index
            ] = replace(
                value,
                sample_count=(
                    value.sample_count
                    + 1
                ),
            )
            break

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlProjectionError,
        match="sample count",
    ):
        project_asr_adversarial_voices_babble_matched_control_v1(
            _evidence(
                media=tuple(
                    media
                )
            )
        )


def test_projection_rejects_changed_source_population():
    first_source = (
        ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS[
            0
        ]
    )
    media = tuple(
        value
        for value in _media_population()
        if not (
            value.kind == "source"
            and value.source_key == first_source
        )
    )

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlProjectionError,
        match="source population",
    ):
        project_asr_adversarial_voices_babble_matched_control_v1(
            _evidence(
                media=media
            )
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "reference_transcripts_projected",
        "adversarial_suite_built",
        "asr_execution_verified",
        "qualification_threshold_applied",
        "production_qualified",
        "release_enforcement_eligible",
        "official_release_verdict_modified",
    ),
)
def test_projection_bundle_rejects_authority_escalation(
    field_name: str,
):
    projection = _project()

    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlProjectionError,
        match="cannot escalate",
    ):
        replace(
            projection,
            **{
                field_name: True,
            },
        )


def test_projection_types_are_frozen_slots_dataclasses():
    projection = _project()
    pair = projection.pairs[
        0
    ]

    assert {
        field.name
        for field in fields(
            ASRAdversarialVOiCESMatchedControlPairKey
        )
    } == {
        "source_key",
        "room",
        "microphone_id",
        "angle_degrees",
    }

    assert isinstance(
        pair,
        ASRAdversarialVOiCESMatchedControlPair,
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        pair.key.room = "rm2"

    with pytest.raises(
        (
            AttributeError,
            TypeError,
        )
    ):
        pair.unexpected = True
