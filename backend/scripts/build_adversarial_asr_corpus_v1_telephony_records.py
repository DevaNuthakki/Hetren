"""Build deterministic I3 telephony-stress corpus records.

This slice derives one 8 kHz mono linear-PCM development asset from the
sealed 16 kHz clean multi-number/identifier parent case.

It establishes deterministic lineage and transformation evidence only.
It does not establish human acoustic diversity, apply qualification
thresholds, certify ASR behavior, authorize production use, or alter
release authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV,
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
]:
    """Build the I3 telephony-bandwidth and codec-stress records."""

    telephony_transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=(
                    TRANSFORMATION_RECORD_ID
                ),
                case_id=CASE_ID,
                parent_audio_sha256=(
                    PARENT_AUDIO_SHA256
                ),
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
                expected_codec_name=(
                    "pcm_s16le"
                ),
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
                parent_audio_sha256=(
                    PARENT_AUDIO_SHA256
                ),
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
                expected_codec_name=(
                    "pcm_mulaw"
                ),
            )
        )
    )

    derivation_plan = (
        build_asr_adversarial_corpus_derivation_plan_v1(
            ASRAdversarialCorpusDerivationPlan(
                corpus_id=(
                    "qualification.synthetic-telephony-v1"
                ),
                corpus_version="1.0.0",
                parent_manifest_sha256=(
                    PARENT_MANIFEST_SHA256
                ),
                entries=(
                    ASRAdversarialCorpusDerivationPlanEntry(
                        case_id=MULAW_CASE_ID,
                        parent_case_id=(
                            PARENT_CASE_ID
                        ),
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
                        case_id=CASE_ID,
                        parent_case_id=(
                            PARENT_CASE_ID
                        ),
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
        derivation_plan,
    )


def main() -> None:
    (
        telephony_transformation,
        mulaw_transformation,
        derivation_plan,
    ) = build_records()

    telephony_transformation_path = (
        CORPUS_ROOT
        / "records"
        / "transformations"
        / f"{CASE_ID}.json"
    )

    mulaw_transformation_path = (
        CORPUS_ROOT
        / "records"
        / "transformations"
        / f"{MULAW_CASE_ID}.json"
    )

    derivation_plan_path = (
        CORPUS_ROOT
        / "specification"
        / "derivation-plan.json"
    )

    _write_if_changed(
        telephony_transformation_path,
        telephony_transformation,
    )

    _write_if_changed(
        mulaw_transformation_path,
        mulaw_transformation,
    )

    _write_if_changed(
        derivation_plan_path,
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
        "telephony_case_id:",
        CASE_ID,
    )
    print(
        "telephony_transformation_sha256:",
        telephony_transformation.sha256,
    )

    print()
    print(
        "mulaw_case_id:",
        MULAW_CASE_ID,
    )
    print(
        "mulaw_transformation_sha256:",
        mulaw_transformation.sha256,
    )
    print(
        "mulaw_output_relative_path:",
        MULAW_OUTPUT_RELATIVE_PATH,
    )

    print()
    print(
        "derivation_plan_sha256:",
        derivation_plan.sha256,
    )


if __name__ == "__main__":
    main()
