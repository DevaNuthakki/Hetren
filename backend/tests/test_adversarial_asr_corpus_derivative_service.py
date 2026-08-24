from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.adversarial_asr_corpus_derivative_service import (
    ASRAdversarialCorpusDerivativeError,
    generate_asr_adversarial_derivative_v1,
)
from app.adversarial_asr_corpus_verification_service import (
    ASRAdversarialMeasuredMedia,
)
from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV,
    ASRAdversarialFFmpegTransformResult,
)
from hvee.packs.asr.adversarial_corpus_records import (
    ASRAdversarialCorpusGenerationPlan,
    ASRAdversarialCorpusGenerationPlanEntry,
    ASRAdversarialCorpusTransformationRecord,
    build_asr_adversarial_corpus_generation_plan_v1,
    build_asr_adversarial_corpus_transformation_record_v1,
)


CASE_ID = "fixture.case"

SOURCE_BYTES = (
    b"deterministic-source-audio"
)

OUTPUT_BYTES = (
    b"deterministic-pcm16k-output"
)

PROVENANCE_SHA256 = hashlib.sha256(
    b"fixture-provenance"
).hexdigest()

RIGHTS_SHA256 = hashlib.sha256(
    b"fixture-rights"
).hexdigest()

TRANSFORMER_ENVIRONMENT_SHA256 = hashlib.sha256(
    b"fixture-ffmpeg-environment"
).hexdigest()


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


def _write_bundle(
    path: Path,
    bundle,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            {
                "payload": bundle.payload,
                "sha256": bundle.sha256,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class FakeTransformer:
    tool_key = "ffmpeg"
    reported_version = "5.1.9-test"
    transform_environment_sha256 = (
        TRANSFORMER_ENVIRONMENT_SHA256
    )
    recipe_argv = (
        ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
    )

    def __init__(
        self,
    ) -> None:
        self.calls = 0

    def transform_pcm16k(
        self,
        *,
        input_path: Path,
        output_path: Path,
    ):
        self.calls += 1

        parent = input_path.read_bytes()

        output_path.write_bytes(
            OUTPUT_BYTES
        )

        return (
            ASRAdversarialFFmpegTransformResult(
                parent_audio_sha256=(
                    _sha_bytes(
                        parent
                    )
                ),
                parent_byte_length=len(
                    parent
                ),
                output_audio_sha256=(
                    _sha_bytes(
                        OUTPUT_BYTES
                    )
                ),
                output_byte_length=len(
                    OUTPUT_BYTES
                ),
            )
        )


class FakeProbe:
    probe_key = "fixture.media-probe"
    probe_version = "1.0.0"
    probe_environment_sha256 = (
        _sha_text(
            "fixture-probe-environment"
        )
    )

    def __init__(
        self,
        *,
        sample_rate_hz: int = 16_000,
        channel_count: int = 1,
        codec_name: str = "pcm_s16le",
    ) -> None:
        self.sample_rate_hz = (
            sample_rate_hz
        )
        self.channel_count = (
            channel_count
        )
        self.codec_name = (
            codec_name
        )
        self.calls: list[Path] = []

    def probe(
        self,
        audio_path: Path,
    ):
        self.calls.append(
            audio_path
        )

        return ASRAdversarialMeasuredMedia(
            duration_ms=1_234,
            sample_rate_hz=(
                self.sample_rate_hz
            ),
            channel_count=(
                self.channel_count
            ),
            codec_name=(
                self.codec_name
            ),
        )


def _context(
    tmp_path: Path,
    *,
    derivative_transformation_sha256: (
        str | None
    ) = None,
    derivative_provenance_sha256: (
        str | None
    ) = None,
):
    corpus = (
        tmp_path
        / "corpus"
    )

    generated = (
        tmp_path
        / "generated"
    )

    source_path = (
        generated
        / "source"
        / f"{CASE_ID}.wav"
    )

    source_path.parent.mkdir(
        parents=True
    )

    source_path.write_bytes(
        SOURCE_BYTES
    )

    transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=(
                    "transform.fixture-case-pcm16k-v1"
                ),
                case_id=CASE_ID,
                parent_audio_sha256=(
                    _sha_bytes(
                        SOURCE_BYTES
                    )
                ),
                tool_key="ffmpeg",
                tool_version="5.1.9-test",
                tool_environment_sha256=(
                    TRANSFORMER_ENVIRONMENT_SHA256
                ),
                argv=(
                    ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
                ),
                output_relative_path=(
                    f"clean/{CASE_ID}.wav"
                ),
                expected_sample_rate_hz=(
                    16_000
                ),
                expected_channel_count=1,
                expected_codec_name=(
                    "pcm_s16le"
                ),
            )
        )
    )

    source_plan = (
        build_asr_adversarial_corpus_generation_plan_v1(
            ASRAdversarialCorpusGenerationPlan(
                corpus_id=(
                    "qualification.fixture-source"
                ),
                corpus_version="1.0.0",
                entries=(
                    ASRAdversarialCorpusGenerationPlanEntry(
                        case_id=CASE_ID,
                        output_relative_path=(
                            f"source/{CASE_ID}.wav"
                        ),
                        provenance_record_sha256=(
                            PROVENANCE_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_SHA256
                        ),
                        transformation_record_sha256=None,
                    ),
                ),
            )
        )
    )

    derivative_plan = (
        build_asr_adversarial_corpus_generation_plan_v1(
            ASRAdversarialCorpusGenerationPlan(
                corpus_id=(
                    "qualification.fixture-derivative"
                ),
                corpus_version="1.0.0",
                entries=(
                    ASRAdversarialCorpusGenerationPlanEntry(
                        case_id=CASE_ID,
                        output_relative_path=(
                            f"clean/{CASE_ID}.wav"
                        ),
                        provenance_record_sha256=(
                            derivative_provenance_sha256
                            or PROVENANCE_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_SHA256
                        ),
                        transformation_record_sha256=(
                            derivative_transformation_sha256
                            or transformation.sha256
                        ),
                    ),
                ),
            )
        )
    )

    _write_bundle(
        corpus
        / "specification"
        / "generation-plan.json",
        source_plan,
    )

    _write_bundle(
        corpus
        / "specification"
        / "derivative-plan.json",
        derivative_plan,
    )

    _write_bundle(
        corpus
        / "records"
        / "transformations"
        / f"{CASE_ID}.json",
        transformation,
    )

    return (
        corpus,
        generated,
        source_path,
        transformation,
    )


def _generate(
    *,
    corpus: Path,
    generated: Path,
    transformer=None,
    probe=None,
):
    return generate_asr_adversarial_derivative_v1(
        corpus_root=corpus,
        generated_root=generated,
        case_id=CASE_ID,
        transformer=(
            transformer
            or FakeTransformer()
        ),
        probe=(
            probe
            or FakeProbe()
        ),
    )


def test_generates_and_publishes_verified_derivative(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        _source,
        transformation,
    ) = _context(
        tmp_path
    )

    transformer = (
        FakeTransformer()
    )

    result = _generate(
        corpus=corpus,
        generated=generated,
        transformer=transformer,
    )

    destination = (
        generated
        / "clean"
        / f"{CASE_ID}.wav"
    )

    assert (
        destination.read_bytes()
        == OUTPUT_BYTES
    )

    assert (
        transformer.calls
        == 1
    )

    assert (
        result.case_id
        == CASE_ID
    )
    assert (
        result.source_relative_path
        == f"source/{CASE_ID}.wav"
    )
    assert (
        result.output_relative_path
        == f"clean/{CASE_ID}.wav"
    )
    assert (
        result.parent_audio_sha256
        == _sha_bytes(
            SOURCE_BYTES
        )
    )
    assert (
        result.audio_asset_sha256
        == _sha_bytes(
            OUTPUT_BYTES
        )
    )
    assert (
        result.byte_length
        == len(
            OUTPUT_BYTES
        )
    )
    assert (
        result.duration_ms
        == 1_234
    )
    assert (
        result.sample_rate_hz
        == 16_000
    )
    assert (
        result.channel_count
        == 1
    )
    assert (
        result.codec_name
        == "pcm_s16le"
    )
    assert (
        result.transformation_record_sha256
        == transformation.sha256
    )
    assert (
        result.development_evidence_only
        is True
    )


def test_regeneration_is_idempotent(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        _source,
        _transformation,
    ) = _context(
        tmp_path
    )

    transformer = (
        FakeTransformer()
    )

    first = _generate(
        corpus=corpus,
        generated=generated,
        transformer=transformer,
    )

    second = _generate(
        corpus=corpus,
        generated=generated,
        transformer=transformer,
    )

    assert (
        first.audio_asset_sha256
        == second.audio_asset_sha256
    )
    assert (
        first.byte_length
        == second.byte_length
    )
    assert (
        transformer.calls
        == 2
    )


def test_rejects_parent_audio_mismatch(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        source,
        _transformation,
    ) = _context(
        tmp_path
    )

    source.write_bytes(
        b"changed-source"
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match=(
            "generated source does not match"
        ),
    ):
        _generate(
            corpus=corpus,
            generated=generated,
        )


def test_rejects_transformation_commitment_mismatch(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        _source,
        _transformation,
    ) = _context(
        tmp_path,
        derivative_transformation_sha256=(
            _sha_text(
                "different-transform"
            )
        ),
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match=(
            "transformation commitment does not match"
        ),
    ):
        _generate(
            corpus=corpus,
            generated=generated,
        )


def test_rejects_provenance_binding_mismatch(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        _source,
        _transformation,
    ) = _context(
        tmp_path,
        derivative_provenance_sha256=(
            _sha_text(
                "different-provenance"
            )
        ),
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="provenance/rights binding",
    ):
        _generate(
            corpus=corpus,
            generated=generated,
        )


def test_rejects_runtime_transformer_identity_mismatch(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        _source,
        _transformation,
    ) = _context(
        tmp_path
    )

    transformer = (
        FakeTransformer()
    )

    transformer.transform_environment_sha256 = (
        _sha_text(
            "different-environment"
        )
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="runtime transformer",
    ):
        _generate(
            corpus=corpus,
            generated=generated,
            transformer=transformer,
        )


def test_rejects_runtime_recipe_mismatch(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        _source,
        _transformation,
    ) = _context(
        tmp_path
    )

    transformer = (
        FakeTransformer()
    )

    transformer.recipe_argv = (
        "-unexpected",
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="runtime transformer",
    ):
        _generate(
            corpus=corpus,
            generated=generated,
            transformer=transformer,
        )


def test_rejects_media_metadata_mismatch(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        _source,
        _transformation,
    ) = _context(
        tmp_path
    )

    probe = FakeProbe(
        sample_rate_hz=8_000
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="media does not match",
    ):
        _generate(
            corpus=corpus,
            generated=generated,
            probe=probe,
        )


def test_rejects_conflicting_existing_output(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        _source,
        _transformation,
    ) = _context(
        tmp_path
    )

    destination = (
        generated
        / "clean"
        / f"{CASE_ID}.wav"
    )

    destination.parent.mkdir(
        parents=True
    )

    destination.write_bytes(
        b"conflicting-existing-output"
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="conflicts with deterministic generation",
    ):
        _generate(
            corpus=corpus,
            generated=generated,
        )

    assert (
        destination.read_bytes()
        == b"conflicting-existing-output"
    )


def test_rejects_symlinked_source_asset(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        source,
        _transformation,
    ) = _context(
        tmp_path
    )

    external = (
        tmp_path
        / "external-source.wav"
    )

    external.write_bytes(
        SOURCE_BYTES
    )

    source.unlink()

    source.symlink_to(
        external
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="cannot contain symlinks",
    ):
        _generate(
            corpus=corpus,
            generated=generated,
        )


def test_rejects_symlinked_output_parent(
    tmp_path: Path,
):
    (
        corpus,
        generated,
        _source,
        _transformation,
    ) = _context(
        tmp_path
    )

    real_clean = (
        generated
        / "real-clean"
    )

    real_clean.mkdir()

    clean = (
        generated
        / "clean"
    )

    clean.symlink_to(
        real_clean,
        target_is_directory=True,
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="cannot contain symlinks",
    ):
        _generate(
            corpus=corpus,
            generated=generated,
        )
