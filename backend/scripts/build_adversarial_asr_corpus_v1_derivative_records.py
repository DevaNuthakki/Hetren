"""Build source-visible deterministic derivative records for ASR corpus v1.

This builder expands the clean synthetic derivative plan while preserving
the already-sealed control transformation record byte-for-byte.

Generated audio is intentionally not committed. The transformation records
bind the deterministic source-audio SHA-256 values established by the pinned
synthetic generation environment.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV,
)
from hvee.packs.asr.adversarial_corpus_records import (
    ASRAdversarialCorpusGenerationPlan,
    ASRAdversarialCorpusGenerationPlanEntry,
    ASRAdversarialCorpusTransformationRecord,
    build_asr_adversarial_corpus_generation_plan_v1,
    build_asr_adversarial_corpus_transformation_record_v1,
    verify_asr_adversarial_corpus_record_v1,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]

CORPUS_ROOT = (
    BACKEND_ROOT
    / "corpora/asr/adversarial/v1"
)

SOURCE_PLAN_PATH = (
    CORPUS_ROOT
    / "specification/generation-plan.json"
)

DERIVATIVE_PLAN_PATH = (
    CORPUS_ROOT
    / "specification/derivative-plan.json"
)

TRANSFORMATION_ROOT = (
    CORPUS_ROOT
    / "records/transformations"
)


SOURCE_CORPUS_ID = "qualification.synthetic-v1"

DERIVATIVE_CORPUS_ID = (
    "qualification.synthetic-derivative-v1"
)

CORPUS_VERSION = "1.0.0"

CONTROL_CASE_ID = "control.clean-critical"


CASE_IDS = (
    "clean.identifier-account-order",
    "clean.identifier-confirmation",
    "clean.identifier-multiple",
    "clean.multi-number-id",
    "clean.number-currency-time",
    "clean.number-measurement",
    "clean.number-percentage",
    CONTROL_CASE_ID,
)


SOURCE_PLAN_SHA256 = (
    "7c3f4a729a490ea2471f86ef4077e1c4"
    "eb38f5c095ba29e66373c139a14e1c57"
)


CONTROL_TRANSFORMATION_SHA256 = (
    "4cd349d56ca7c5fc60c773024dc36488"
    "b75f3944a4b1a98da260178c726c3f0f"
)


FFMPEG_TOOL_KEY = "ffmpeg"

FFMPEG_TOOL_VERSION = "5.1.9-0+deb12u1"

FFMPEG_ENVIRONMENT_SHA256 = (
    "e400ae359be1dc681937ba5caefc2d1f"
    "a077247c8939aa04aee0067e67fc87fc"
)


PARENT_AUDIO_SHA256 = {
    "clean.identifier-account-order": (
        "bfd7493488c37023b5b4429b25022462"
        "60a9dd1723bc2214439309c493d04e6a"
    ),
    "clean.identifier-confirmation": (
        "2ed4f6de5b2ae6ea96a7b49c635d030e"
        "2679a42c55e5511911b82bbc56227936"
    ),
    "clean.identifier-multiple": (
        "5124ea409f0d0c8022da5ea36a1ace63"
        "bb57385c9d28b4196ad85ccacaeb4179"
    ),
    "clean.multi-number-id": (
        "61f967d306ab7e819133a27792ef666f4"
        "8069d72965b4d6918580e12f3f6e9e8"
    ),
    "clean.number-currency-time": (
        "191dbd877ad0cd425e4223b3e00b7916"
        "5790ab3bed76194f5384d01a5629272e"
    ),
    "clean.number-measurement": (
        "1e5aeed9bf1d861b041de5283b96c78b"
        "1e1e09b71bba3f01e15f68c12e50f3bb"
    ),
    "clean.number-percentage": (
        "464d479c353cabb37123f58971b61d973"
        "0dd85ce4d03ee76681cf4b76537d5b6"
    ),
    CONTROL_CASE_ID: (
        "d1fe44656a114a0e66fb6ea950ae4217"
        "d31691486842f4421eff8317cc6ab440"
    ),
}


def _load_bundle(
    file_path: Path,
):
    document = json.loads(
        file_path.read_text(
            encoding="utf-8"
        )
    )

    return verify_asr_adversarial_corpus_record_v1(
        payload=document["payload"],
        expected_sha256=document["sha256"],
    )


def _write_bundle(
    *,
    file_path: Path,
    bundle,
) -> None:
    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if (
        file_path.exists()
        and (
            file_path.is_symlink()
            or not file_path.is_file()
        )
    ):
        raise RuntimeError(
            f"Refusing invalid output path: {file_path}"
        )

    file_path.write_text(
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


def _record_id(
    case_id: str,
) -> str:
    normalized = case_id.replace(
        ".",
        "-",
    )

    return (
        f"transform.{normalized}-pcm16k-v1"
    )


def _validate_source_plan():
    source_plan = _load_bundle(
        SOURCE_PLAN_PATH
    )

    if source_plan.sha256 != SOURCE_PLAN_SHA256:
        raise RuntimeError(
            "Committed source generation plan identity changed."
        )

    record = source_plan.payload[
        "record"
    ]

    if (
        record["corpus_id"]
        != SOURCE_CORPUS_ID
        or record["corpus_version"]
        != CORPUS_VERSION
    ):
        raise RuntimeError(
            "Source generation plan identity is invalid."
        )

    entries = record["entries"]

    actual_case_ids = tuple(
        entry["case_id"]
        for entry in entries
    )

    if actual_case_ids != CASE_IDS:
        raise RuntimeError(
            "Source generation plan case inventory changed."
        )

    for entry in entries:
        if (
            entry[
                "transformation_record_sha256"
            ]
            is not None
        ):
            raise RuntimeError(
                "Source generation plan unexpectedly "
                "contains a transformation."
            )

    return source_plan


def _validate_control_transformation():
    file_path = (
        TRANSFORMATION_ROOT
        / f"{CONTROL_CASE_ID}.json"
    )

    bundle = _load_bundle(
        file_path
    )

    if (
        bundle.sha256
        != CONTROL_TRANSFORMATION_SHA256
    ):
        raise RuntimeError(
            "Sealed control transformation identity changed."
        )

    record = bundle.payload[
        "record"
    ]

    expected_output = record[
        "expected_output"
    ]

    if (
        record["case_id"]
        != CONTROL_CASE_ID
        or record["parent_audio_sha256"]
        != PARENT_AUDIO_SHA256[
            CONTROL_CASE_ID
        ]
        or record["tool"]["key"]
        != FFMPEG_TOOL_KEY
        or record["tool"]["version"]
        != FFMPEG_TOOL_VERSION
        or record["tool"]["environment_sha256"]
        != FFMPEG_ENVIRONMENT_SHA256
        or tuple(record["argv"])
        != ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
        or expected_output
        != {
            "relative_path": (
                "clean/control.clean-critical.wav"
            ),
            "sample_rate_hz": 16_000,
            "channel_count": 1,
            "codec_name": "pcm_s16le",
        }
    ):
        raise RuntimeError(
            "Sealed control transformation contract changed."
        )

    return bundle


def main() -> None:
    source_plan = _validate_source_plan()

    control_transformation = (
        _validate_control_transformation()
    )

    source_entries = source_plan.payload[
        "record"
    ]["entries"]

    transformations = {
        CONTROL_CASE_ID: (
            control_transformation
        )
    }

    for case_id in CASE_IDS:
        if case_id == CONTROL_CASE_ID:
            continue

        transformation = (
            build_asr_adversarial_corpus_transformation_record_v1(
                ASRAdversarialCorpusTransformationRecord(
                    record_id=_record_id(
                        case_id
                    ),
                    case_id=case_id,
                    parent_audio_sha256=(
                        PARENT_AUDIO_SHA256[
                            case_id
                        ]
                    ),
                    tool_key=FFMPEG_TOOL_KEY,
                    tool_version=(
                        FFMPEG_TOOL_VERSION
                    ),
                    tool_environment_sha256=(
                        FFMPEG_ENVIRONMENT_SHA256
                    ),
                    argv=(
                        ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
                    ),
                    output_relative_path=(
                        f"clean/{case_id}.wav"
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

        transformations[
            case_id
        ] = transformation

        _write_bundle(
            file_path=(
                TRANSFORMATION_ROOT
                / f"{case_id}.json"
            ),
            bundle=transformation,
        )

    derivative_entries = []

    for source_entry in source_entries:
        case_id = source_entry[
            "case_id"
        ]

        transformation = (
            transformations[
                case_id
            ]
        )

        derivative_entries.append(
            ASRAdversarialCorpusGenerationPlanEntry(
                case_id=case_id,
                output_relative_path=(
                    f"clean/{case_id}.wav"
                ),
                provenance_record_sha256=(
                    source_entry[
                        "provenance_record_sha256"
                    ]
                ),
                rights_record_sha256=(
                    source_entry[
                        "rights_record_sha256"
                    ]
                ),
                transformation_record_sha256=(
                    transformation.sha256
                ),
            )
        )

    derivative_plan = (
        build_asr_adversarial_corpus_generation_plan_v1(
            ASRAdversarialCorpusGenerationPlan(
                corpus_id=(
                    DERIVATIVE_CORPUS_ID
                ),
                corpus_version=(
                    CORPUS_VERSION
                ),
                entries=tuple(
                    derivative_entries
                ),
            )
        )
    )

    _write_bundle(
        file_path=DERIVATIVE_PLAN_PATH,
        bundle=derivative_plan,
    )

    print(
        "source_plan_sha256:",
        source_plan.sha256,
    )
    print(
        "control_transformation_sha256:",
        control_transformation.sha256,
    )

    print()

    for case_id in CASE_IDS:
        transformation = transformations[
            case_id
        ]

        print(
            f"{case_id}:"
        )
        print(
            "  parent_audio_sha256:",
            PARENT_AUDIO_SHA256[
                case_id
            ],
        )
        print(
            "  transformation_sha256:",
            transformation.sha256,
        )
        print(
            "  output:",
            f"clean/{case_id}.wav",
        )

    print()
    print(
        "derivative_plan_sha256:",
        derivative_plan.sha256,
    )
    print(
        "case_count:",
        len(
            derivative_entries
        ),
    )


if __name__ == "__main__":
    main()
