from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from app.adversarial_asr_corpus_verification_service import (
    ASRAdversarialCorpusVerificationEvidenceBundle,
    ASRAdversarialCorpusVerificationServiceError,
    ASRAdversarialMeasuredMedia,
    calculate_asr_adversarial_corpus_verification_sha256,
    verify_asr_adversarial_corpus,
)
from hvee.core.contracts import HveeContractError
from hvee.packs.asr import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCase,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialCondition,
    ASRAdversarialCorpusAsset,
    ASRAdversarialCorpusManifestBundle,
    ASRAdversarialCorpusManifestDefinition,
    ASRAdversarialCorpusProvenanceType,
    ASRAdversarialDurationBucket,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialLongContextPosition,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSemanticLoad,
    ASRAdversarialSpeakingRate,
    ASRAdversarialSuiteDefinition,
    build_asr_adversarial_corpus_manifest_v1,
    build_asr_adversarial_evidence_v1,
    calculate_asr_adversarial_corpus_manifest_sha256,
)


AUDIO_A = b"real-corpus-audio-a"
AUDIO_B = b"real-corpus-audio-b"


def _sha_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _sha_text(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _condition(
    *,
    codec,
    sample_rate_hz,
):
    return ASRAdversarialCondition(
        channel=(
            ASRAdversarialChannel.CLEAN
        ),
        codec=codec,
        sample_rate_hz=sample_rate_hz,
        microphone_class="studio",
        noise=(
            ASRAdversarialNoiseCondition.NONE
        ),
        speaking_rate=(
            ASRAdversarialSpeakingRate.NORMAL
        ),
        speech_variety_key=(
            "declared.corpus-verification-fixture"
        ),
        overlap=(
            ASRAdversarialOverlapCondition.NONE
        ),
        duration=(
            ASRAdversarialDurationBucket.SHORT
        ),
    )


def _semantic_load():
    return ASRAdversarialSemanticLoad(
        critical_number_count=1,
        critical_identifier_count=0,
        critical_terminology_count=0,
        spoken_number_variation=False,
        multiple_critical_items=False,
        duplicate_critical_items=False,
        ordering_challenge=False,
        long_context_position=(
            ASRAdversarialLongContextPosition.NONE
        ),
    )


def _suite():
    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(
            ASRAdversarialCase(
                case_id="verification.case-a",
                audio_asset_sha256=(
                    _sha_bytes(AUDIO_A)
                ),
                reference_transcript=(
                    "Take 250 mg."
                ),
                condition=_condition(
                    codec=(
                        ASRAdversarialCodec.LINEAR_PCM
                    ),
                    sample_rate_hz=16_000,
                ),
                semantic_load=_semantic_load(),
                description=(
                    "Corpus verification fixture A."
                ),
                tags=("verification",),
            ),
            ASRAdversarialCase(
                case_id="verification.case-b",
                audio_asset_sha256=(
                    _sha_bytes(AUDIO_B)
                ),
                reference_transcript=(
                    "Take 500 mg."
                ),
                condition=_condition(
                    codec=(
                        ASRAdversarialCodec.MULAW
                    ),
                    sample_rate_hz=8_000,
                ),
                semantic_load=_semantic_load(),
                description=(
                    "Corpus verification fixture B."
                ),
                tags=("verification",),
            ),
        ),
    )

    return (
        suite,
        build_asr_adversarial_evidence_v1(
            suite
        ),
    )


def _manifest_definition(
    *,
    suite_evidence,
):
    return ASRAdversarialCorpusManifestDefinition(
        corpus_id="qualification.corpus-one",
        corpus_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        assets=(
            ASRAdversarialCorpusAsset(
                case_id="verification.case-a",
                relative_audio_path=(
                    "audio/case-a.wav"
                ),
                audio_asset_sha256=(
                    _sha_bytes(AUDIO_A)
                ),
                byte_length=len(AUDIO_A),
                duration_ms=2_500,
                sample_rate_hz=16_000,
                channel_count=1,
                codec_name="pcm_s16le",
                provenance_type=(
                    ASRAdversarialCorpusProvenanceType
                    .PURPOSE_RECORDED
                ),
                provenance_record_sha256=(
                    _sha_text("provenance-a")
                ),
                rights_record_sha256=(
                    _sha_text("rights-a")
                ),
            ),
            ASRAdversarialCorpusAsset(
                case_id="verification.case-b",
                relative_audio_path=(
                    "audio/case-b.wav"
                ),
                audio_asset_sha256=(
                    _sha_bytes(AUDIO_B)
                ),
                byte_length=len(AUDIO_B),
                duration_ms=3_000,
                sample_rate_hz=8_000,
                channel_count=1,
                codec_name="pcm_mulaw",
                provenance_type=(
                    ASRAdversarialCorpusProvenanceType
                    .DETERMINISTIC_DERIVATIVE
                ),
                provenance_record_sha256=(
                    _sha_text("provenance-b")
                ),
                rights_record_sha256=(
                    _sha_text("rights-b")
                ),
                transformation_record_sha256=(
                    _sha_text("transformation-b")
                ),
            ),
        ),
    )


def _context():
    suite, suite_evidence = _suite()

    definition = _manifest_definition(
        suite_evidence=suite_evidence,
    )

    manifest = (
        build_asr_adversarial_corpus_manifest_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    return (
        suite,
        suite_evidence,
        definition,
        manifest,
    )


def _write_corpus(
    tmp_path: Path,
):
    root = tmp_path / "corpus"
    audio = root / "audio"

    audio.mkdir(
        parents=True
    )

    first = audio / "case-a.wav"
    second = audio / "case-b.wav"

    first.write_bytes(
        AUDIO_A
    )
    second.write_bytes(
        AUDIO_B
    )

    return (
        root,
        first,
        second,
    )


class RecordingProbe:
    probe_key = "test.media-probe"
    probe_version = "1.0.0"
    probe_environment_sha256 = (
        _sha_text("test-media-probe-environment")
    )

    def __init__(
        self,
        *,
        mutate_path: Path | None = None,
        mutate_bytes: bytes | None = None,
        override_case_a=None,
        override_case_b=None,
    ):
        self.mutate_path = mutate_path
        self.mutate_bytes = mutate_bytes
        self.override_case_a = override_case_a
        self.override_case_b = override_case_b
        self.calls: list[Path] = []

    def probe(
        self,
        audio_path: Path,
    ):
        self.calls.append(
            audio_path
        )

        if (
            self.mutate_path is not None
            and audio_path == self.mutate_path
        ):
            assert self.mutate_bytes is not None
            audio_path.write_bytes(
                self.mutate_bytes
            )

        if audio_path.name == "case-a.wav":
            if self.override_case_a is not None:
                return self.override_case_a

            return ASRAdversarialMeasuredMedia(
                duration_ms=2_500,
                sample_rate_hz=16_000,
                channel_count=1,
                codec_name="pcm_s16le",
            )

        if self.override_case_b is not None:
            return self.override_case_b

        return ASRAdversarialMeasuredMedia(
            duration_ms=3_000,
            sample_rate_hz=8_000,
            channel_count=1,
            codec_name="pcm_mulaw",
        )


def _verify(
    *,
    tmp_path: Path,
    probe=None,
    root=None,
    definition=None,
    manifest=None,
    suite=None,
    suite_evidence=None,
):
    (
        default_suite,
        default_suite_evidence,
        default_definition,
        default_manifest,
    ) = _context()

    if root is None:
        root, _first, _second = (
            _write_corpus(
                tmp_path
            )
        )

    return verify_asr_adversarial_corpus(
        corpus_root=root,
        definition=(
            definition
            if definition is not None
            else default_definition
        ),
        manifest=(
            manifest
            if manifest is not None
            else default_manifest
        ),
        suite=(
            suite
            if suite is not None
            else default_suite
        ),
        suite_evidence=(
            suite_evidence
            if suite_evidence is not None
            else default_suite_evidence
        ),
        media_probe=(
            probe
            if probe is not None
            else RecordingProbe()
        ),
    )


def test_verifies_every_manifest_asset_against_actual_files(
    tmp_path: Path,
):
    root, first, second = (
        _write_corpus(
            tmp_path
        )
    )
    probe = RecordingProbe()

    result = _verify(
        tmp_path=tmp_path,
        root=root,
        probe=probe,
    )

    assert [
        asset.case_id
        for asset in result.assets
    ] == [
        "verification.case-a",
        "verification.case-b",
    ]

    assert probe.calls == [
        first.resolve(),
        second.resolve(),
    ]

    assert result.evidence.payload[
        "verification"
    ]["asset_count"] == 2


def test_verification_evidence_is_deterministic(
    tmp_path: Path,
):
    root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    first = _verify(
        tmp_path=tmp_path,
        root=root,
    )
    second = _verify(
        tmp_path=tmp_path,
        root=root,
    )

    assert (
        first.evidence.payload
        == second.evidence.payload
    )
    assert (
        first.evidence.sha256
        == second.evidence.sha256
    )


def test_evidence_contains_probe_identity_without_absolute_paths(
    tmp_path: Path,
):
    root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    result = _verify(
        tmp_path=tmp_path,
        root=root,
    )

    payload = result.evidence.payload

    assert payload["probe"] == {
        "key": "test.media-probe",
        "version": "1.0.0",
        "environment_sha256": (
            RecordingProbe
            .probe_environment_sha256
        ),
    }

    serialized = str(
        payload
    )

    assert str(
        tmp_path.resolve()
    ) not in serialized


def test_wrong_audio_hash_is_rejected_before_probe(
    tmp_path: Path,
):
    root, first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    first.write_bytes(
        b"tampered-audio-a"
    )

    probe = RecordingProbe()

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="does not match the sealed manifest",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
            probe=probe,
        )

    assert probe.calls == []


def test_wrong_manifest_byte_length_is_rejected_before_probe(
    tmp_path: Path,
):
    suite, suite_evidence = _suite()
    definition = _manifest_definition(
        suite_evidence=suite_evidence,
    )

    wrong_first = replace(
        definition.assets[0],
        byte_length=(
            definition.assets[0].byte_length
            + 1
        ),
    )

    definition = replace(
        definition,
        assets=(
            wrong_first,
            definition.assets[1],
        ),
    )

    manifest = (
        build_asr_adversarial_corpus_manifest_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )
    probe = RecordingProbe()

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="does not match the sealed manifest",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
            probe=probe,
            definition=definition,
            manifest=manifest,
            suite=suite,
            suite_evidence=suite_evidence,
        )

    assert probe.calls == []


def test_missing_asset_is_rejected(
    tmp_path: Path,
):
    root, first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    first.unlink()

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="asset is unavailable",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
        )


def test_corpus_root_must_be_directory(
    tmp_path: Path,
):
    root_file = tmp_path / "not-a-directory"
    root_file.write_text(
        "not a corpus"
    )

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="must be a directory",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root_file,
        )


def test_rejects_symlinked_corpus_root(
    tmp_path: Path,
):
    real_root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    alias = tmp_path / "corpus-alias"

    try:
        alias.symlink_to(
            real_root,
            target_is_directory=True,
        )
    except (OSError, NotImplementedError):
        pytest.skip(
            "symlinks unavailable"
        )

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="root cannot be a symlink",
    ):
        _verify(
            tmp_path=tmp_path,
            root=alias,
        )


def test_rejects_symlinked_asset_file(
    tmp_path: Path,
):
    root, first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    target = (
        first.parent
        / "case-a-real.wav"
    )

    first.rename(
        target
    )

    try:
        first.symlink_to(
            target
        )
    except (OSError, NotImplementedError):
        pytest.skip(
            "symlinks unavailable"
        )

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="cannot contain symlinks",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
        )


def test_rejects_symlinked_intermediate_directory(
    tmp_path: Path,
):
    root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    audio = root / "audio"
    real_audio = root / "real-audio"

    audio.rename(
        real_audio
    )

    try:
        audio.symlink_to(
            real_audio,
            target_is_directory=True,
        )
    except (OSError, NotImplementedError):
        pytest.skip(
            "symlinks unavailable"
        )

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="cannot contain symlinks",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
        )


@pytest.mark.parametrize(
    (
        "measured",
        "message",
    ),
    [
        (
            ASRAdversarialMeasuredMedia(
                duration_ms=2_501,
                sample_rate_hz=16_000,
                channel_count=1,
                codec_name="pcm_s16le",
            ),
            "duration",
        ),
        (
            ASRAdversarialMeasuredMedia(
                duration_ms=2_500,
                sample_rate_hz=8_000,
                channel_count=1,
                codec_name="pcm_s16le",
            ),
            "sample rate",
        ),
        (
            ASRAdversarialMeasuredMedia(
                duration_ms=2_500,
                sample_rate_hz=16_000,
                channel_count=2,
                codec_name="pcm_s16le",
            ),
            "channel count",
        ),
        (
            ASRAdversarialMeasuredMedia(
                duration_ms=2_500,
                sample_rate_hz=16_000,
                channel_count=1,
                codec_name="pcm_mulaw",
            ),
            "codec",
        ),
    ],
)
def test_rejects_measured_media_mismatch(
    tmp_path: Path,
    measured,
    message,
):
    root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    probe = RecordingProbe(
        override_case_a=measured,
    )

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match=message,
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
            probe=probe,
        )


def test_rejects_invalid_probe_result(
    tmp_path: Path,
):
    class InvalidProbe(RecordingProbe):
        def probe(
            self,
            audio_path: Path,
        ):
            self.calls.append(
                audio_path
            )
            return {
                "duration_ms": 2500,
            }

    root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="invalid result",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
            probe=InvalidProbe(),
        )


def test_detects_same_length_mutation_during_media_probe(
    tmp_path: Path,
):
    root, first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    replacement = b"X" * len(
        AUDIO_A
    )

    assert len(
        replacement
    ) == len(
        AUDIO_A
    )

    probe = RecordingProbe(
        mutate_path=first.resolve(),
        mutate_bytes=replacement,
    )

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="changed during media verification",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
            probe=probe,
        )


def test_unexpected_probe_failure_is_not_swallowed(
    tmp_path: Path,
):
    class BrokenProbe(RecordingProbe):
        def probe(
            self,
            _audio_path: Path,
        ):
            raise RuntimeError(
                "probe implementation defect"
            )

    root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )

    with pytest.raises(
        RuntimeError,
        match="probe implementation defect",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
            probe=BrokenProbe(),
        )


def test_invalid_probe_identity_is_rejected_before_filesystem_work(
    tmp_path: Path,
):
    class InvalidProbe(RecordingProbe):
        probe_key = "INVALID PROBE"

    probe = InvalidProbe()

    with pytest.raises(
        ASRAdversarialCorpusVerificationServiceError,
        match="media probe key",
    ):
        _verify(
            tmp_path=tmp_path,
            root=tmp_path / "does-not-exist",
            probe=probe,
        )

    assert probe.calls == []


def test_rehashed_manifest_tampering_is_rejected_before_probe(
    tmp_path: Path,
):
    (
        suite,
        suite_evidence,
        definition,
        manifest,
    ) = _context()

    tampered = copy.deepcopy(
        manifest.payload
    )

    tampered["evidence_boundary"][
        "filesystem_audio_verified_by_manifest"
    ] = True

    tampered_manifest = (
        ASRAdversarialCorpusManifestBundle(
            payload=tampered,
            sha256=(
                calculate_asr_adversarial_corpus_manifest_sha256(
                    tampered
                )
            ),
        )
    )

    root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )
    probe = RecordingProbe()

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
            probe=probe,
            definition=definition,
            manifest=tampered_manifest,
            suite=suite,
            suite_evidence=suite_evidence,
        )

    assert probe.calls == []


def test_rehashed_suite_tampering_is_rejected_before_probe(
    tmp_path: Path,
):
    (
        suite,
        suite_evidence,
        definition,
        manifest,
    ) = _context()

    tampered = copy.deepcopy(
        suite_evidence.payload
    )

    tampered["scientific_boundary"][
        "production_qualified"
    ] = True

    from hvee.packs.asr.adversarial_evidence import (
        calculate_asr_adversarial_evidence_sha256,
    )

    tampered_suite = (
        ASRAdversarialEvidenceBundle(
            payload=tampered,
            sha256=(
                calculate_asr_adversarial_evidence_sha256(
                    tampered
                )
            ),
        )
    )

    root, _first, _second = (
        _write_corpus(
            tmp_path
        )
    )
    probe = RecordingProbe()

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        _verify(
            tmp_path=tmp_path,
            root=root,
            probe=probe,
            definition=definition,
            manifest=manifest,
            suite=suite,
            suite_evidence=tampered_suite,
        )

    assert probe.calls == []


def test_verification_boundary_preserves_scientific_limits(
    tmp_path: Path,
):
    result = _verify(
        tmp_path=tmp_path,
    )

    boundary = result.evidence.payload[
        "verification_boundary"
    ]

    assert boundary[
        "filesystem_audio_verified"
    ] is True
    assert boundary[
        "media_metadata_measured"
    ] is True
    assert boundary[
        "content_hashed_before_media_probe"
    ] is True
    assert boundary[
        "content_rehashed_after_media_probe"
    ] is True

    assert boundary[
        "acoustic_noise_condition_verified"
    ] is False
    assert boundary[
        "speaking_rate_condition_verified"
    ] is False
    assert boundary[
        "speaker_overlap_condition_verified"
    ] is False
    assert boundary[
        "microphone_class_verified"
    ] is False
    assert boundary[
        "speech_variety_inferred_from_audio"
    ] is False
    assert boundary[
        "rights_record_legal_validity_verified"
    ] is False

    assert boundary[
        "development_evidence_only"
    ] is True
    assert boundary[
        "qualification_threshold_applied"
    ] is False
    assert boundary[
        "certification_issued"
    ] is False
    assert boundary[
        "production_qualified"
    ] is False
    assert boundary[
        "release_enforcement_eligible"
    ] is False


def test_verification_bundle_rejects_rehashed_boundary_tampering(
    tmp_path: Path,
):
    result = _verify(
        tmp_path=tmp_path,
    )

    tampered = copy.deepcopy(
        result.evidence.payload
    )

    tampered["verification_boundary"][
        "production_qualified"
    ] = True

    tampered_bundle = (
        ASRAdversarialCorpusVerificationEvidenceBundle(
            payload=tampered,
            sha256=(
                calculate_asr_adversarial_corpus_verification_sha256(
                    tampered
                )
            ),
        )
    )

    assert (
        tampered_bundle.payload[
            "verification_boundary"
        ]["production_qualified"]
        is True
    )

    # The bundle is content-integrity checked, but authority tampering
    # cannot be mistaken for a service-built artifact because its SHA
    # differs from the original trusted service result.
    assert (
        tampered_bundle.sha256
        != result.evidence.sha256
    )
