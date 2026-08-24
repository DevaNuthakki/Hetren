"""Build deterministic I3 synthetic acoustic-stress corpus records.

This builder derives telephony-bandwidth, G.711 codec, lossy-compression,
and numerically calibrated synthetic-noise development assets from the
sealed 16 kHz clean multi-number/identifier parent case.

It establishes deterministic lineage and transformation evidence only.
Synthetic white-noise cases remain development evidence and do not
represent natural environmental noise or human acoustic diversity.
This builder does not apply qualification thresholds, certify ASR
behavior, authorize production use, or alter release authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV,
    ASR_ADVERSARIAL_FFMPEG_ALAW8K_ARGV,
    ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_ARGV,
    ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV,
    ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV,
    ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV,
    ASR_ADVERSARIAL_FFMPEG_PCM8K_ARGV,
)
from hvee.packs.asr.adversarial_corpus_records import (
    ASRAdversarialCorpusDerivationPlan,
    ASRAdversarialCorpusDerivationPlanEntry,
    ASRAdversarialCorpusRecordBundle,
    ASRAdversarialCorpusTransformationRecord,
    build_asr_adversarial_corpus_derivation_plan_v1,
    build_asr_adversarial_corpus_transformation_record_v1,
)


CORPUS_ROOT = Path(
    "corpora/asr/adversarial/v1"
)

PARENT_MANIFEST_SHA256 = (
    "9823b12023ed39ff482f8636dd8625d0"
    "294905f7f4e406a555506e3ecb766f38"
)

PARENT_CASE_ID = (
    "clean.multi-number-id"
)

PARENT_RELATIVE_PATH = (
    "clean/clean.multi-number-id.wav"
)

PARENT_AUDIO_SHA256 = (
    "23f9af39d01afe47e932bd061467bd0b"
    "5f49dc8bf520c2a8296a4556c54f1297"
)

PROVENANCE_RECORD_SHA256 = (
    "f804bf7391cc39286bc54d5727ebe01f"
    "61d3a460f169a1b9b4d9d43a903113b4"
)

RIGHTS_RECORD_SHA256 = (
    "0b38e02c548a775ed4db61603fdcc681"
    "48840d3396feaef59ac8d51c6b3c6ae7"
)

CASE_ID = (
    "stress.telephony-bandwidth.multi-number-id"
)

OUTPUT_RELATIVE_PATH = (
    "telephony/"
    "stress.telephony-bandwidth.multi-number-id.wav"
)

TRANSFORMATION_RECORD_ID = (
    "transform.stress-telephony-bandwidth-multi-number-id-v1"
)

FFMPEG_VERSION = (
    "5.1.9-0+deb12u1"
)

FFMPEG_PCM8K_ENVIRONMENT_SHA256 = (
    "3ac14031af8e2b8f316415b8758b28e1"
    "daa5207677305b064601cb5f6dfb8aa0"
)

MULAW_CASE_ID = (
    "stress.codec-mulaw.multi-number-id"
)

MULAW_OUTPUT_RELATIVE_PATH = (
    "telephony/"
    "stress.codec-mulaw.multi-number-id.wav"
)

MULAW_TRANSFORMATION_RECORD_ID = (
    "transform.stress-codec-mulaw-multi-number-id-v1"
)

FFMPEG_MULAW8K_ENVIRONMENT_SHA256 = (
    "db90491d9804eeb81620b6585ee361ee"
    "15095716bd739b51f5b09e954fa419d4"
)

ALAW_CASE_ID = (
    "stress.codec-alaw.multi-number-id"
)

ALAW_OUTPUT_RELATIVE_PATH = (
    "telephony/"
    "stress.codec-alaw.multi-number-id.wav"
)

ALAW_TRANSFORMATION_RECORD_ID = (
    "transform.stress-codec-alaw-multi-number-id-v1"
)

FFMPEG_ALAW8K_ENVIRONMENT_SHA256 = (
    "73e3a2fd247e2f0ecf4fdb68e5ed4e9"
    "f96e582eb58515ef699ca0361fdf79d42"
)

AAC_CASE_ID = (
    "stress.codec-aac.multi-number-id"
)

AAC_OUTPUT_RELATIVE_PATH = (
    "lossy/"
    "stress.codec-aac.multi-number-id.m4a"
)

AAC_TRANSFORMATION_RECORD_ID = (
    "transform.stress-codec-aac-multi-number-id-v1"
)

FFMPEG_AAC_M4A_CBR32_ENVIRONMENT_SHA256 = (
    "8a23edea7a13d66422dbd083023cf7e8"
    "12cc8dbed8bb788d51fe799f9a62a877"
)

MP3_CASE_ID = (
    "stress.codec-mp3.multi-number-id"
)

MP3_OUTPUT_RELATIVE_PATH = (
    "lossy/"
    "stress.codec-mp3.multi-number-id.mp3"
)

MP3_TRANSFORMATION_RECORD_ID = (
    "transform.stress-codec-mp3-multi-number-id-v1"
)

FFMPEG_MP3_CBR32_ENVIRONMENT_SHA256 = (
    "9f442ee2686f49578f817b29a7303241"
    "b379b0b47d1743fc2d1684de77cb1bb3"
)


NOISE_MODERATE_CASE_ID = (
    "stress.noise-moderate.multi-number-id"
)

NOISE_MODERATE_OUTPUT_RELATIVE_PATH = (
    "noise/"
    "stress.noise-moderate.multi-number-id.wav"
)

NOISE_MODERATE_TRANSFORMATION_RECORD_ID = (
    "transform.stress-noise-moderate-multi-number-id-v1"
)

FFMPEG_NOISE_MODERATE_ENVIRONMENT_SHA256 = (
    "2f71f0619cb588a211f68de064125301"
    "2ec8209cc633e53b0a15dbe94dfb4682"
)

NOISE_SEVERE_USABLE_CASE_ID = (
    "stress.noise-severe-usable.multi-number-id"
)

NOISE_SEVERE_USABLE_OUTPUT_RELATIVE_PATH = (
    "noise/"
    "stress.noise-severe-usable.multi-number-id.wav"
)

NOISE_SEVERE_USABLE_TRANSFORMATION_RECORD_ID = (
    "transform.stress-noise-severe-usable-multi-number-id-v1"
)

FFMPEG_NOISE_SEVERE_USABLE_ENVIRONMENT_SHA256 = (
    "410054a787ab53be40332d8efcec98c1"
    "91229d772d047626a1c073e946036043"
)


def _canonical_document(
    bundle: ASRAdversarialCorpusRecordBundle,
) -> str:
    return (
        json.dumps(
            {
                "payload": bundle.payload,
                "sha256": bundle.sha256,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _write_if_changed(
    path: Path,
    bundle: ASRAdversarialCorpusRecordBundle,
) -> None:
    content = _canonical_document(
        bundle
    )

    if (
        path.is_file()
        and path.read_text(
            encoding="utf-8"
        )
        == content
    ):
        return

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content,
        encoding="utf-8",
    )


def build_records() -> tuple[
    ASRAdversarialCorpusRecordBundle,
    ASRAdversarialCorpusRecordBundle,
    ASRAdversarialCorpusRecordBundle,
    ASRAdversarialCorpusRecordBundle,
    ASRAdversarialCorpusRecordBundle,
    ASRAdversarialCorpusRecordBundle,
    ASRAdversarialCorpusRecordBundle,
    ASRAdversarialCorpusRecordBundle,
]:
    """Build the I3 synthetic acoustic-stress record portfolio."""

    telephony_transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=TRANSFORMATION_RECORD_ID,
                case_id=CASE_ID,
                parent_audio_sha256=PARENT_AUDIO_SHA256,
                tool_key="ffmpeg",
                tool_version=FFMPEG_VERSION,
                tool_environment_sha256=(
                    FFMPEG_PCM8K_ENVIRONMENT_SHA256
                ),
                argv=(
                    ASR_ADVERSARIAL_FFMPEG_PCM8K_ARGV
                ),
                output_relative_path=(
                    OUTPUT_RELATIVE_PATH
                ),
                expected_sample_rate_hz=8_000,
                expected_channel_count=1,
                expected_codec_name="pcm_s16le",
            )
        )
    )

    mulaw_transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=(
                    MULAW_TRANSFORMATION_RECORD_ID
                ),
                case_id=MULAW_CASE_ID,
                parent_audio_sha256=PARENT_AUDIO_SHA256,
                tool_key="ffmpeg",
                tool_version=FFMPEG_VERSION,
                tool_environment_sha256=(
                    FFMPEG_MULAW8K_ENVIRONMENT_SHA256
                ),
                argv=(
                    ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV
                ),
                output_relative_path=(
                    MULAW_OUTPUT_RELATIVE_PATH
                ),
                expected_sample_rate_hz=8_000,
                expected_channel_count=1,
                expected_codec_name="pcm_mulaw",
            )
        )
    )

    alaw_transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=(
                    ALAW_TRANSFORMATION_RECORD_ID
                ),
                case_id=ALAW_CASE_ID,
                parent_audio_sha256=PARENT_AUDIO_SHA256,
                tool_key="ffmpeg",
                tool_version=FFMPEG_VERSION,
                tool_environment_sha256=(
                    FFMPEG_ALAW8K_ENVIRONMENT_SHA256
                ),
                argv=(
                    ASR_ADVERSARIAL_FFMPEG_ALAW8K_ARGV
                ),
                output_relative_path=(
                    ALAW_OUTPUT_RELATIVE_PATH
                ),
                expected_sample_rate_hz=8_000,
                expected_channel_count=1,
                expected_codec_name="pcm_alaw",
            )
        )
    )

    aac_transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=(
                    AAC_TRANSFORMATION_RECORD_ID
                ),
                case_id=AAC_CASE_ID,
                parent_audio_sha256=PARENT_AUDIO_SHA256,
                tool_key="ffmpeg",
                tool_version=FFMPEG_VERSION,
                tool_environment_sha256=(
                    FFMPEG_AAC_M4A_CBR32_ENVIRONMENT_SHA256
                ),
                argv=(
                    ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV
                ),
                output_relative_path=(
                    AAC_OUTPUT_RELATIVE_PATH
                ),
                expected_sample_rate_hz=16_000,
                expected_channel_count=1,
                expected_codec_name="aac",
            )
        )
    )

    mp3_transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=(
                    MP3_TRANSFORMATION_RECORD_ID
                ),
                case_id=MP3_CASE_ID,
                parent_audio_sha256=PARENT_AUDIO_SHA256,
                tool_key="ffmpeg",
                tool_version=FFMPEG_VERSION,
                tool_environment_sha256=(
                    FFMPEG_MP3_CBR32_ENVIRONMENT_SHA256
                ),
                argv=(
                    ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_ARGV
                ),
                output_relative_path=(
                    MP3_OUTPUT_RELATIVE_PATH
                ),
                expected_sample_rate_hz=16_000,
                expected_channel_count=1,
                expected_codec_name="mp3",
            )
        )
    )

    moderate_noise_transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=(
                    NOISE_MODERATE_TRANSFORMATION_RECORD_ID
                ),
                case_id=NOISE_MODERATE_CASE_ID,
                parent_audio_sha256=PARENT_AUDIO_SHA256,
                tool_key="ffmpeg",
                tool_version=FFMPEG_VERSION,
                tool_environment_sha256=(
                    FFMPEG_NOISE_MODERATE_ENVIRONMENT_SHA256
                ),
                argv=(
                    ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV
                ),
                output_relative_path=(
                    NOISE_MODERATE_OUTPUT_RELATIVE_PATH
                ),
                expected_sample_rate_hz=16_000,
                expected_channel_count=1,
                expected_codec_name="pcm_s16le",
            )
        )
    )

    severe_usable_noise_transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=(
                    NOISE_SEVERE_USABLE_TRANSFORMATION_RECORD_ID
                ),
                case_id=NOISE_SEVERE_USABLE_CASE_ID,
                parent_audio_sha256=PARENT_AUDIO_SHA256,
                tool_key="ffmpeg",
                tool_version=FFMPEG_VERSION,
                tool_environment_sha256=(
                    FFMPEG_NOISE_SEVERE_USABLE_ENVIRONMENT_SHA256
                ),
                argv=(
                    ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV
                ),
                output_relative_path=(
                    NOISE_SEVERE_USABLE_OUTPUT_RELATIVE_PATH
                ),
                expected_sample_rate_hz=16_000,
                expected_channel_count=1,
                expected_codec_name="pcm_s16le",
            )
        )
    )

    derivation_plan = (
        build_asr_adversarial_corpus_derivation_plan_v1(
            ASRAdversarialCorpusDerivationPlan(
                corpus_id=(
                    "qualification.synthetic-acoustic-stress-v1"
                ),
                corpus_version="1.0.0",
                parent_manifest_sha256=(
                    PARENT_MANIFEST_SHA256
                ),
                entries=(
                    ASRAdversarialCorpusDerivationPlanEntry(
                        case_id=AAC_CASE_ID,
                        parent_case_id=PARENT_CASE_ID,
                        parent_relative_path=(
                            PARENT_RELATIVE_PATH
                        ),
                        parent_audio_sha256=(
                            PARENT_AUDIO_SHA256
                        ),
                        output_relative_path=(
                            AAC_OUTPUT_RELATIVE_PATH
                        ),
                        provenance_record_sha256=(
                            PROVENANCE_RECORD_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_RECORD_SHA256
                        ),
                        transformation_record_sha256=(
                            aac_transformation.sha256
                        ),
                    ),
                    ASRAdversarialCorpusDerivationPlanEntry(
                        case_id=ALAW_CASE_ID,
                        parent_case_id=PARENT_CASE_ID,
                        parent_relative_path=(
                            PARENT_RELATIVE_PATH
                        ),
                        parent_audio_sha256=(
                            PARENT_AUDIO_SHA256
                        ),
                        output_relative_path=(
                            ALAW_OUTPUT_RELATIVE_PATH
                        ),
                        provenance_record_sha256=(
                            PROVENANCE_RECORD_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_RECORD_SHA256
                        ),
                        transformation_record_sha256=(
                            alaw_transformation.sha256
                        ),
                    ),
                    ASRAdversarialCorpusDerivationPlanEntry(
                        case_id=MP3_CASE_ID,
                        parent_case_id=PARENT_CASE_ID,
                        parent_relative_path=(
                            PARENT_RELATIVE_PATH
                        ),
                        parent_audio_sha256=(
                            PARENT_AUDIO_SHA256
                        ),
                        output_relative_path=(
                            MP3_OUTPUT_RELATIVE_PATH
                        ),
                        provenance_record_sha256=(
                            PROVENANCE_RECORD_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_RECORD_SHA256
                        ),
                        transformation_record_sha256=(
                            mp3_transformation.sha256
                        ),
                    ),
                    ASRAdversarialCorpusDerivationPlanEntry(
                        case_id=MULAW_CASE_ID,
                        parent_case_id=PARENT_CASE_ID,
                        parent_relative_path=(
                            PARENT_RELATIVE_PATH
                        ),
                        parent_audio_sha256=(
                            PARENT_AUDIO_SHA256
                        ),
                        output_relative_path=(
                            MULAW_OUTPUT_RELATIVE_PATH
                        ),
                        provenance_record_sha256=(
                            PROVENANCE_RECORD_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_RECORD_SHA256
                        ),
                        transformation_record_sha256=(
                            mulaw_transformation.sha256
                        ),
                    ),
                    ASRAdversarialCorpusDerivationPlanEntry(
                        case_id=NOISE_MODERATE_CASE_ID,
                        parent_case_id=PARENT_CASE_ID,
                        parent_relative_path=(
                            PARENT_RELATIVE_PATH
                        ),
                        parent_audio_sha256=(
                            PARENT_AUDIO_SHA256
                        ),
                        output_relative_path=(
                            NOISE_MODERATE_OUTPUT_RELATIVE_PATH
                        ),
                        provenance_record_sha256=(
                            PROVENANCE_RECORD_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_RECORD_SHA256
                        ),
                        transformation_record_sha256=(
                            moderate_noise_transformation.sha256
                        ),
                    ),
                    ASRAdversarialCorpusDerivationPlanEntry(
                        case_id=NOISE_SEVERE_USABLE_CASE_ID,
                        parent_case_id=PARENT_CASE_ID,
                        parent_relative_path=(
                            PARENT_RELATIVE_PATH
                        ),
                        parent_audio_sha256=(
                            PARENT_AUDIO_SHA256
                        ),
                        output_relative_path=(
                            NOISE_SEVERE_USABLE_OUTPUT_RELATIVE_PATH
                        ),
                        provenance_record_sha256=(
                            PROVENANCE_RECORD_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_RECORD_SHA256
                        ),
                        transformation_record_sha256=(
                            severe_usable_noise_transformation.sha256
                        ),
                    ),
                    ASRAdversarialCorpusDerivationPlanEntry(
                        case_id=CASE_ID,
                        parent_case_id=PARENT_CASE_ID,
                        parent_relative_path=(
                            PARENT_RELATIVE_PATH
                        ),
                        parent_audio_sha256=(
                            PARENT_AUDIO_SHA256
                        ),
                        output_relative_path=(
                            OUTPUT_RELATIVE_PATH
                        ),
                        provenance_record_sha256=(
                            PROVENANCE_RECORD_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_RECORD_SHA256
                        ),
                        transformation_record_sha256=(
                            telephony_transformation.sha256
                        ),
                    ),
                ),
            )
        )
    )

    return (
        telephony_transformation,
        mulaw_transformation,
        alaw_transformation,
        moderate_noise_transformation,
        severe_usable_noise_transformation,
        aac_transformation,
        mp3_transformation,
        derivation_plan,
    )


def main() -> None:
    (
        telephony_transformation,
        mulaw_transformation,
        alaw_transformation,
        moderate_noise_transformation,
        severe_usable_noise_transformation,
        aac_transformation,
        mp3_transformation,
        derivation_plan,
    ) = build_records()

    transformation_root = (
        CORPUS_ROOT
        / "records"
        / "transformations"
    )

    _write_if_changed(
        transformation_root
        / f"{CASE_ID}.json",
        telephony_transformation,
    )

    _write_if_changed(
        transformation_root
        / f"{MULAW_CASE_ID}.json",
        mulaw_transformation,
    )

    _write_if_changed(
        transformation_root
        / f"{ALAW_CASE_ID}.json",
        alaw_transformation,
    )

    _write_if_changed(
        transformation_root
        / f"{AAC_CASE_ID}.json",
        aac_transformation,
    )

    _write_if_changed(
        transformation_root
        / f"{MP3_CASE_ID}.json",
        mp3_transformation,
    )

    _write_if_changed(
        transformation_root
        / f"{NOISE_MODERATE_CASE_ID}.json",
        moderate_noise_transformation,
    )

    _write_if_changed(
        transformation_root
        / f"{NOISE_SEVERE_USABLE_CASE_ID}.json",
        severe_usable_noise_transformation,
    )

    _write_if_changed(
        CORPUS_ROOT
        / "specification"
        / "derivation-plan.json",
        derivation_plan,
    )

    print(
        "parent_case_id:",
        PARENT_CASE_ID,
    )
    print(
        "parent_audio_sha256:",
        PARENT_AUDIO_SHA256,
    )

    print()
    print(
        "telephony_transformation_sha256:",
        telephony_transformation.sha256,
    )
    print(
        "mulaw_transformation_sha256:",
        mulaw_transformation.sha256,
    )
    print(
        "alaw_transformation_sha256:",
        alaw_transformation.sha256,
    )
    print(
        "aac_transformation_sha256:",
        aac_transformation.sha256,
    )
    print(
        "mp3_transformation_sha256:",
        mp3_transformation.sha256,
    )
    print(
        "moderate_noise_transformation_sha256:",
        moderate_noise_transformation.sha256,
    )
    print(
        "severe_usable_noise_transformation_sha256:",
        severe_usable_noise_transformation.sha256,
    )

    print()
    print(
        "derivation_plan_sha256:",
        derivation_plan.sha256,
    )


if __name__ == "__main__":
    main()
