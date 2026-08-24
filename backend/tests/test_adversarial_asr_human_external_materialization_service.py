from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.adversarial_asr_corpus_verification_service import (
    ASRAdversarialMeasuredMedia,
)
from app.adversarial_asr_human_external_materialization_service import (
    ASRAdversarialHumanExternalMaterializationDefinition,
    ASRAdversarialHumanExternalMaterializationError,
    materialize_asr_adversarial_human_external_source,
    materialize_asr_adversarial_minilibrispeech_source_v1,
)


AUDIO = (
    b"deterministic-human-audio-fixture"
)

TRANSCRIPT = (
    b"TEN SECONDS\n"
)


def _sha256(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


class RecordingProbe:
    def __init__(
        self,
        *,
        measured: ASRAdversarialMeasuredMedia | None = None,
        mutate_audio_path: Path | None = None,
        mutate_audio_bytes: bytes | None = None,
        mutate_transcript_path: Path | None = None,
        mutate_transcript_bytes: bytes | None = None,
    ):
        self.measured = (
            measured
            or ASRAdversarialMeasuredMedia(
                duration_ms=1_850,
                sample_rate_hz=16_000,
                channel_count=1,
                codec_name="flac",
            )
        )
        self.mutate_audio_path = mutate_audio_path
        self.mutate_audio_bytes = mutate_audio_bytes
        self.mutate_transcript_path = (
            mutate_transcript_path
        )
        self.mutate_transcript_bytes = (
            mutate_transcript_bytes
        )
        self.calls: list[Path] = []

    def probe(
        self,
        audio_path: Path,
    ):
        self.calls.append(
            audio_path
        )

        if (
            self.mutate_audio_path
            is not None
        ):
            self.mutate_audio_path.write_bytes(
                self.mutate_audio_bytes
                or b"X" * len(AUDIO)
            )

        if (
            self.mutate_transcript_path
            is not None
        ):
            self.mutate_transcript_path.write_bytes(
                self.mutate_transcript_bytes
                or b"Y" * len(TRANSCRIPT)
            )

        return self.measured


def _write_source(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
]:
    root = (
        tmp_path
        / "evidence"
    )

    case_root = (
        root
        / "selected"
        / "fixture-item"
    )

    case_root.mkdir(
        parents=True
    )

    audio = (
        case_root
        / "fixture-item.flac"
    )

    transcript = (
        case_root
        / "fixture-item.txt"
    )

    audio.write_bytes(
        AUDIO
    )

    transcript.write_bytes(
        TRANSCRIPT
    )

    return (
        root,
        audio,
        transcript,
    )


def _definition(
    **overrides,
):
    values = {
        "case_id": (
            "human.fixture.fixture-item"
        ),
        "source_item_id": (
            "fixture-item"
        ),
        "audio_relative_path": (
            "selected/fixture-item/"
            "fixture-item.flac"
        ),
        "transcript_relative_path": (
            "selected/fixture-item/"
            "fixture-item.txt"
        ),
        "expected_audio_sha256": (
            _sha256(
                AUDIO
            )
        ),
        "expected_audio_byte_length": (
            len(
                AUDIO
            )
        ),
        "expected_transcript_sha256": (
            _sha256(
                TRANSCRIPT
            )
        ),
        "expected_duration_ms": 1_850,
        "expected_sample_rate_hz": 16_000,
        "expected_channel_count": 1,
        "expected_codec_name": "flac",
        "source_selection_sha256": (
            _sha256(
                b"selection"
            )
        ),
        "provenance_record_sha256": (
            _sha256(
                b"provenance"
            )
        ),
        "rights_record_sha256": (
            _sha256(
                b"rights"
            )
        ),
    }

    values.update(
        overrides
    )

    return (
        ASRAdversarialHumanExternalMaterializationDefinition(
            **values
        )
    )


def test_materializes_exact_external_source(
    tmp_path: Path,
):
    root, audio, transcript = (
        _write_source(
            tmp_path
        )
    )

    probe = RecordingProbe()

    result = (
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=probe,
        )
    )

    assert result.case_id == (
        "human.fixture.fixture-item"
    )
    assert result.source_item_id == (
        "fixture-item"
    )
    assert result.audio_path == (
        audio.resolve()
    )
    assert result.transcript_path == (
        transcript.resolve()
    )
    assert result.reference_transcript == (
        "TEN SECONDS\n"
    )
    assert result.audio_sha256 == (
        _sha256(
            AUDIO
        )
    )
    assert result.audio_byte_length == (
        len(
            AUDIO
        )
    )
    assert result.transcript_sha256 == (
        _sha256(
            TRANSCRIPT
        )
    )
    assert result.transcript_byte_length == (
        len(
            TRANSCRIPT
        )
    )
    assert result.duration_ms == 1_850
    assert result.sample_rate_hz == 16_000
    assert result.channel_count == 1
    assert result.codec_name == "flac"
    assert result.development_evidence_only is True
    assert result.rights_adjudicated is False
    assert result.production_qualified is False
    assert result.release_enforcement_eligible is False

    assert probe.calls == [
        audio.resolve()
    ]


def test_relative_root_is_rejected(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.chdir(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="must be absolute",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=Path(
                "evidence"
            ),
            definition=_definition(),
            media_probe=RecordingProbe(),
        )


def test_missing_root_is_rejected(
    tmp_path: Path,
):
    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="root is unavailable",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=(
                tmp_path
                / "missing"
            ),
            definition=_definition(),
            media_probe=RecordingProbe(),
        )


def test_root_file_is_rejected(
    tmp_path: Path,
):
    root_file = (
        tmp_path
        / "root-file"
    )

    root_file.write_bytes(
        b"x"
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="must be a directory",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root_file,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )


def test_symlink_root_is_rejected(
    tmp_path: Path,
):
    root, _audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    alias = (
        tmp_path
        / "evidence-alias"
    )

    try:
        alias.symlink_to(
            root,
            target_is_directory=True,
        )
    except (
        OSError,
        NotImplementedError,
    ):
        pytest.skip(
            "symlinks unavailable"
        )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="root cannot be a symlink",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=alias,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )


def test_symlink_intermediate_directory_is_rejected(
    tmp_path: Path,
):
    root, _audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    selected = (
        root
        / "selected"
    )

    real_selected = (
        root
        / "real-selected"
    )

    selected.rename(
        real_selected
    )

    try:
        selected.symlink_to(
            real_selected,
            target_is_directory=True,
        )
    except (
        OSError,
        NotImplementedError,
    ):
        pytest.skip(
            "symlinks unavailable"
        )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="cannot contain symlinks",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )


@pytest.mark.parametrize(
    "which_file",
    (
        "audio",
        "transcript",
    ),
)
def test_symlink_source_file_is_rejected(
    tmp_path: Path,
    which_file: str,
):
    root, audio, transcript = (
        _write_source(
            tmp_path
        )
    )

    source = (
        audio
        if which_file == "audio"
        else transcript
    )

    target = (
        source.parent
        / (
            source.stem
            + "-real"
            + source.suffix
        )
    )

    source.rename(
        target
    )

    try:
        source.symlink_to(
            target
        )
    except (
        OSError,
        NotImplementedError,
    ):
        pytest.skip(
            "symlinks unavailable"
        )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="cannot contain symlinks",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )


@pytest.mark.parametrize(
    "which_file",
    (
        "audio",
        "transcript",
    ),
)
def test_missing_source_file_is_rejected(
    tmp_path: Path,
    which_file: str,
):
    root, audio, transcript = (
        _write_source(
            tmp_path
        )
    )

    (
        audio
        if which_file == "audio"
        else transcript
    ).unlink()

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="is unavailable",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )


def test_audio_hash_substitution_is_rejected(
    tmp_path: Path,
):
    root, audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    audio.write_bytes(
        b"substituted-audio"
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="audio does not match",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )


def test_audio_byte_length_mismatch_is_rejected(
    tmp_path: Path,
):
    root, _audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="audio does not match",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(
                expected_audio_byte_length=(
                    len(AUDIO)
                    + 1
                )
            ),
            media_probe=RecordingProbe(),
        )


def test_transcript_hash_substitution_is_rejected(
    tmp_path: Path,
):
    root, _audio, transcript = (
        _write_source(
            tmp_path
        )
    )

    transcript.write_bytes(
        b"NINE SECONDS\n"
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="transcript does not match",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )


def test_invalid_utf8_transcript_is_rejected(
    tmp_path: Path,
):
    root, _audio, transcript = (
        _write_source(
            tmp_path
        )
    )

    invalid = b"\xff\xfe\xfd"

    transcript.write_bytes(
        invalid
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="valid UTF-8",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(
                expected_transcript_sha256=(
                    _sha256(
                        invalid
                    )
                )
            ),
            media_probe=RecordingProbe(),
        )


@pytest.mark.parametrize(
    (
        "measured",
        "message",
    ),
    (
        (
            ASRAdversarialMeasuredMedia(
                duration_ms=1_851,
                sample_rate_hz=16_000,
                channel_count=1,
                codec_name="flac",
            ),
            "duration",
        ),
        (
            ASRAdversarialMeasuredMedia(
                duration_ms=1_850,
                sample_rate_hz=8_000,
                channel_count=1,
                codec_name="flac",
            ),
            "sample rate",
        ),
        (
            ASRAdversarialMeasuredMedia(
                duration_ms=1_850,
                sample_rate_hz=16_000,
                channel_count=2,
                codec_name="flac",
            ),
            "channel count",
        ),
        (
            ASRAdversarialMeasuredMedia(
                duration_ms=1_850,
                sample_rate_hz=16_000,
                channel_count=1,
                codec_name="pcm_s16le",
            ),
            "codec",
        ),
    ),
)
def test_measured_media_mismatch_is_rejected(
    tmp_path: Path,
    measured,
    message: str,
):
    root, _audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match=message,
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(
                measured=measured
            ),
        )


def test_invalid_probe_result_is_rejected(
    tmp_path: Path,
):
    class InvalidProbe:
        def probe(
            self,
            _audio_path: Path,
        ):
            return {
                "codec_name": "flac"
            }

    root, _audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="invalid result",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=InvalidProbe(),
        )


def test_same_length_audio_mutation_during_probe_is_rejected(
    tmp_path: Path,
):
    root, audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    replacement = (
        b"X"
        * len(
            AUDIO
        )
    )

    assert len(
        replacement
    ) == len(
        AUDIO
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="audio changed during media verification",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(
                mutate_audio_path=audio,
                mutate_audio_bytes=replacement,
            ),
        )


def test_same_length_transcript_mutation_during_probe_is_rejected(
    tmp_path: Path,
):
    root, _audio, transcript = (
        _write_source(
            tmp_path
        )
    )

    replacement = (
        b"Y"
        * len(
            TRANSCRIPT
        )
    )

    assert len(
        replacement
    ) == len(
        TRANSCRIPT
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="transcript changed during media verification",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(
                mutate_transcript_path=transcript,
                mutate_transcript_bytes=replacement,
            ),
        )


def test_unexpected_probe_failure_is_not_swallowed(
    tmp_path: Path,
):
    class BrokenProbe:
        def probe(
            self,
            _audio_path: Path,
        ):
            raise RuntimeError(
                "probe implementation defect"
            )

    root, _audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    with pytest.raises(
        RuntimeError,
        match="probe implementation defect",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=BrokenProbe(),
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "audio_relative_path",
        "transcript_relative_path",
    ),
)
@pytest.mark.parametrize(
    "bad_path",
    (
        "../escape.flac",
        "/absolute/file.flac",
        "selected/../escape.flac",
        "./selected/file.flac",
    ),
)
def test_definition_rejects_unsafe_relative_paths(
    field_name: str,
    bad_path: str,
):
    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="is invalid",
    ):
        _definition(
            **{
                field_name: bad_path,
            }
        )


def test_definition_rejects_same_audio_and_transcript_path():
    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="must be distinct",
    ):
        _definition(
            transcript_relative_path=(
                "selected/fixture-item/"
                "fixture-item.flac"
            )
        )


def test_unknown_minilibrispeech_item_fails_closed(
    tmp_path: Path,
):
    root = (
        tmp_path
        / "evidence"
    )

    root.mkdir()

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="canonical verification",
    ):
        materialize_asr_adversarial_minilibrispeech_source_v1(
            evidence_root=root,
            utterance_id="9999-999999-9999",
            media_probe=RecordingProbe(),
        )


def test_invalid_definition_object_is_rejected_before_filesystem_use(
    tmp_path: Path,
):
    root = tmp_path / "evidence"
    root.mkdir()

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="definition is invalid",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=object(),
            media_probe=RecordingProbe(),
        )


def test_invalid_probe_object_is_rejected_before_filesystem_use(
    tmp_path: Path,
):
    root = tmp_path / "evidence"
    root.mkdir()

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="media probe is invalid",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=object(),
        )


def test_audio_commitment_failure_occurs_before_probe(
    tmp_path: Path,
):
    root, audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    audio.write_bytes(
        b"X" * len(AUDIO)
    )

    probe = RecordingProbe()

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="audio does not match",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=probe,
        )

    assert probe.calls == []


def test_transcript_commitment_failure_occurs_before_probe(
    tmp_path: Path,
):
    root, _audio, transcript = (
        _write_source(
            tmp_path
        )
    )

    transcript.write_bytes(
        b"Y" * len(TRANSCRIPT)
    )

    probe = RecordingProbe()

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="transcript does not match",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=probe,
        )

    assert probe.calls == []


def test_same_length_replacement_between_resolution_and_hash_is_rejected(
    monkeypatch,
    tmp_path: Path,
):
    import app.adversarial_asr_human_external_materialization_service as service

    root, audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    original_resolver = (
        service._resolve_direct_file
    )

    replaced = False

    def replacing_resolver(
        *,
        root: Path,
        relative_path: str,
        name: str,
    ) -> Path:
        nonlocal replaced

        resolved = original_resolver(
            root=root,
            relative_path=relative_path,
            name=name,
        )

        if (
            name == "human external audio"
            and not replaced
        ):
            replacement = (
                b"Z"
                * len(
                    AUDIO
                )
            )

            assert len(
                replacement
            ) == len(
                AUDIO
            )

            audio.write_bytes(
                replacement
            )

            replaced = True

        return resolved

    monkeypatch.setattr(
        service,
        "_resolve_direct_file",
        replacing_resolver,
    )

    probe = RecordingProbe()

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="audio does not match",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=probe,
        )

    assert replaced is True
    assert probe.calls == []


def test_symlink_replacement_during_probe_is_rejected_before_result_publication(
    tmp_path: Path,
):
    root, audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    outside = (
        tmp_path
        / "outside.flac"
    )

    outside.write_bytes(
        AUDIO
    )

    class ReplacingProbe(
        RecordingProbe
    ):
        def probe(
            self,
            audio_path: Path,
        ):
            self.calls.append(
                audio_path
            )

            audio_path.unlink()

            try:
                audio_path.symlink_to(
                    outside
                )
            except (
                OSError,
                NotImplementedError,
            ):
                pytest.skip(
                    "symlinks unavailable"
                )

            return self.measured

    probe = ReplacingProbe()

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="cannot contain symlinks",
    ):
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=probe,
        )

    assert probe.calls


@pytest.mark.parametrize(
    (
        "field_name",
        "unsafe_value",
        "message",
    ),
    (
        (
            "development_evidence_only",
            False,
            "development-evidence-only",
        ),
        (
            "rights_adjudicated",
            True,
            "not adjudicated",
        ),
        (
            "production_qualified",
            True,
            "not production-qualified",
        ),
        (
            "release_enforcement_eligible",
            True,
            "ineligible for release enforcement",
        ),
    ),
)
def test_materialized_result_cannot_escalate_authority(
    tmp_path: Path,
    field_name: str,
    unsafe_value: bool,
    message: str,
):
    from dataclasses import replace

    root, _audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    result = (
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match=message,
    ):
        replace(
            result,
            **{
                field_name: unsafe_value,
            },
        )


def test_materialized_result_rejects_relative_filesystem_paths(
    tmp_path: Path,
):
    from dataclasses import replace

    root, _audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    result = (
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )
    )

    with pytest.raises(
        ASRAdversarialHumanExternalMaterializationError,
        match="absolute Path",
    ):
        replace(
            result,
            audio_path=Path(
                "relative.flac"
            ),
        )


def test_materialized_audio_matches_execution_integrity_boundary(
    tmp_path: Path,
):
    from app.adversarial_asr_execution_service import (
        _verify_audio_content,
    )

    root, _audio, _transcript = (
        _write_source(
            tmp_path
        )
    )

    result = (
        materialize_asr_adversarial_human_external_source(
            evidence_root=root,
            definition=_definition(),
            media_probe=RecordingProbe(),
        )
    )

    observed_sha256, observed_byte_length = (
        _verify_audio_content(
            audio_path=result.audio_path,
            expected_sha256=(
                result.audio_sha256
            ),
            expected_byte_length=(
                result.audio_byte_length
            ),
        )
    )

    assert observed_sha256 == (
        result.audio_sha256
    )

    assert observed_byte_length == (
        result.audio_byte_length
    )
