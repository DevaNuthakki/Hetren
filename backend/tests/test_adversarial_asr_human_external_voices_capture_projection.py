"""Red-gate tests for trusted VOiCES capture-condition projection."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.adversarial_asr_human_external_voices_materialization_service import (
    ASRAdversarialVOiCESMaterializationError,
    ASRAdversarialVOiCESMaterializedCaptureCondition,
    ASRAdversarialVOiCESMaterializedMedia,
)


SHA256 = "a" * 64
ABSOLUTE_MEDIA_PATH = Path(
    "/verified/voices/capture.wav"
)


def _condition(
    **overrides: object,
) -> ASRAdversarialVOiCESMaterializedCaptureCondition:
    values: dict[str, object] = {
        "angle_degrees": 10,
        "room": "rm1",
        "distractor": "none",
        "microphone_id": 1,
    }
    values.update(overrides)

    return (
        ASRAdversarialVOiCESMaterializedCaptureCondition(
            **values,
        )
    )


def _media(
    *,
    kind: str,
    capture_condition: (
        ASRAdversarialVOiCESMaterializedCaptureCondition
        | None
    ),
) -> ASRAdversarialVOiCESMaterializedMedia:
    return ASRAdversarialVOiCESMaterializedMedia(
        relative_path=(
            f"{kind}/capture.wav"
        ),
        path=ABSOLUTE_MEDIA_PATH,
        sha256=SHA256,
        byte_length=32,
        kind=kind,
        source_key=(1, 2, 3),
        codec_name="pcm_s16le",
        sample_rate_hz=16_000,
        channel_count=1,
        bits_per_sample=16,
        sample_width_bytes=2,
        sample_count=16_000,
        duration_seconds="1.000000",
        capture_condition=capture_condition,
    )


def test_capture_condition_is_frozen_slots_dataclass():
    condition = _condition()

    assert condition.angle_degrees == 10
    assert condition.room == "rm1"
    assert condition.distractor == "none"
    assert condition.microphone_id == 1
    assert not hasattr(
        condition,
        "__dict__",
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        condition.room = "rm2"


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("angle_degrees", True),
        ("microphone_id", False),
    ),
)
def test_capture_condition_rejects_boolean_integer_substitution(
    field_name: str,
    value: object,
):
    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
    ):
        _condition(
            **{
                field_name: value,
            }
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "room",
        "distractor",
    ),
)
def test_capture_condition_rejects_empty_identifiers(
    field_name: str,
):
    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
    ):
        _condition(
            **{
                field_name: " ",
            }
        )


def test_capture_media_requires_capture_condition():
    media = _media(
        kind="capture",
        capture_condition=None,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="capture.*condition",
    ):
        media.require_capture_condition()


def test_source_media_rejects_capture_condition():
    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="source.*condition",
    ):
        _media(
            kind="source",
            capture_condition=_condition(),
        )


def test_capture_media_preserves_verified_condition():
    condition = _condition(
        room="rm2",
        distractor="babb",
        microphone_id=2,
    )

    media = _media(
        kind="capture",
        capture_condition=condition,
    )

    assert media.capture_condition == condition
    assert media.require_capture_condition() == condition
