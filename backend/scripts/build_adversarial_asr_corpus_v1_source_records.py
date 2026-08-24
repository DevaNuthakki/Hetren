"""Build deterministic synthetic-source records for ASR corpus v1.

This builder expands the committed source-generation inventory while
preserving the already-sealed control source identities.

It writes source-visible provenance and rights records plus the
generation plan. It does not generate audio, apply qualification
thresholds, issue certification, authorize production use, or modify
release authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hvee.packs.asr.adversarial_corpus_records import (
    ASRAdversarialCorpusGenerationPlan,
    ASRAdversarialCorpusGenerationPlanEntry,
    ASRAdversarialCorpusProvenanceRecord,
    ASRAdversarialCorpusRightsRecord,
    build_asr_adversarial_corpus_generation_plan_v1,
    build_asr_adversarial_corpus_provenance_record_v1,
    build_asr_adversarial_corpus_rights_record_v1,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]

CORPUS_ROOT = (
    BACKEND_ROOT
    / "corpora/asr/adversarial/v1"
)

TRANSCRIPT_ROOT = (
    CORPUS_ROOT
    / "specification/transcripts"
)

PROVENANCE_ROOT = (
    CORPUS_ROOT
    / "records/provenance"
)

RIGHTS_ROOT = (
    CORPUS_ROOT
    / "records/rights"
)

GENERATION_PLAN_PATH = (
    CORPUS_ROOT
    / "specification/generation-plan.json"
)


CORPUS_ID = "qualification.synthetic-v1"
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


GENERATOR_KEY = "espeak-ng"

GENERATOR_VERSION = (
    "1.51+dfsg-10+deb12u2"
)

GENERATOR_EXECUTABLE_SHA256 = (
    "0a2f26e328f1dd4cec926987d3dc22bf"
    "841879132fd3aa497dd4fcad0d4d77a3"
)

VOICE_KEY = "en-us"

# 150 WPM is the existing reproducible corpus baseline.
# The current scientific contract does not define numeric
# thresholds for slow/normal/fast speaking-rate labels.
SPEED_WPM = 150

PITCH = 50
AMPLITUDE = 100
PLATFORM_KEY = "linux-amd64"

SOURCE_PACKAGE_KEY = "debian.espeak-ng"

SOURCE_PACKAGE_VERSION = (
    GENERATOR_VERSION
)

PACKAGED_COPYRIGHT_SHA256 = (
    "bf721eede49d50f84bd2c50f96888629"
    "ced572b66ad4087c7a224c4a5e1193bb"
)


CONTROL_TRANSCRIPT_SHA256 = (
    "cb85655794bc5b0c2a5d5d5c1626b0e"
    "3b208bc28ecfce4aa3275ed73ea2e6744"
)

CONTROL_PROVENANCE_SHA256 = (
    "30d7a75e8ad8dca1f03a3576d167a12b"
    "62bff7df2fbd5bfe7a2e825771dde1c4"
)

CONTROL_RIGHTS_SHA256 = (
    "cfcc0861946a6fe96da954f6efda69e7"
    "45e7bd2533e1f9b8718e0084d7bcdb14"
)


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _record_id(
    *,
    prefix: str,
    case_id: str,
) -> str:
    return (
        prefix
        + "."
        + case_id.replace(".", "-")
        + "-v1"
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


def _build_provenance(
    *,
    case_id: str,
    transcript_sha256: str,
):
    return (
        build_asr_adversarial_corpus_provenance_record_v1(
            ASRAdversarialCorpusProvenanceRecord(
                record_id=_record_id(
                    prefix="source",
                    case_id=case_id,
                ),
                case_id=case_id,
                transcript_sha256=(
                    transcript_sha256
                ),
                generator_key=GENERATOR_KEY,
                generator_version=(
                    GENERATOR_VERSION
                ),
                generator_executable_sha256=(
                    GENERATOR_EXECUTABLE_SHA256
                ),
                voice_key=VOICE_KEY,
                speed_wpm=SPEED_WPM,
                pitch=PITCH,
                amplitude=AMPLITUDE,
                platform_key=PLATFORM_KEY,
            )
        )
    )


def _build_rights(
    *,
    case_id: str,
):
    return (
        build_asr_adversarial_corpus_rights_record_v1(
            ASRAdversarialCorpusRightsRecord(
                record_id=_record_id(
                    prefix="rights",
                    case_id=case_id,
                ),
                case_id=case_id,
                source_package_key=(
                    SOURCE_PACKAGE_KEY
                ),
                source_package_version=(
                    SOURCE_PACKAGE_VERSION
                ),
                packaged_copyright_sha256=(
                    PACKAGED_COPYRIGHT_SHA256
                ),
                review_status="not_adjudicated",
                development_use_only=True,
            )
        )
    )


def _verify_control_files(
    *,
    provenance,
    rights,
) -> None:
    control_provenance_path = (
        PROVENANCE_ROOT
        / f"{CONTROL_CASE_ID}.json"
    )

    control_rights_path = (
        RIGHTS_ROOT
        / f"{CONTROL_CASE_ID}.json"
    )

    if (
        not control_provenance_path.is_file()
        or control_provenance_path.is_symlink()
    ):
        raise RuntimeError(
            "committed control provenance record "
            "is missing or invalid"
        )

    if (
        not control_rights_path.is_file()
        or control_rights_path.is_symlink()
    ):
        raise RuntimeError(
            "committed control rights record "
            "is missing or invalid"
        )

    provenance_document = json.loads(
        control_provenance_path.read_text(
            encoding="utf-8"
        )
    )

    rights_document = json.loads(
        control_rights_path.read_text(
            encoding="utf-8"
        )
    )

    if provenance.sha256 != CONTROL_PROVENANCE_SHA256:
        raise RuntimeError(
            "rebuilt control provenance identity changed"
        )

    if rights.sha256 != CONTROL_RIGHTS_SHA256:
        raise RuntimeError(
            "rebuilt control rights identity changed"
        )

    if (
        provenance_document
        != {
            "payload": provenance.payload,
            "sha256": provenance.sha256,
        }
    ):
        raise RuntimeError(
            "committed control provenance does not "
            "match rebuilt canonical evidence"
        )

    if (
        rights_document
        != {
            "payload": rights.payload,
            "sha256": rights.sha256,
        }
    ):
        raise RuntimeError(
            "committed control rights do not "
            "match rebuilt canonical evidence"
        )


def main() -> None:
    if CASE_IDS != tuple(
        sorted(CASE_IDS)
    ):
        raise RuntimeError(
            "I2 case inventory must remain sorted"
        )

    entries = []

    for case_id in CASE_IDS:
        transcript_file = (
            TRANSCRIPT_ROOT
            / f"{case_id}.txt"
        )

        if (
            transcript_file.is_symlink()
            or not transcript_file.is_file()
        ):
            raise RuntimeError(
                "missing regular transcript for "
                f"{case_id}"
            )

        transcript_sha256 = (
            _sha256_file(
                transcript_file
            )
        )

        if (
            case_id == CONTROL_CASE_ID
            and transcript_sha256
            != CONTROL_TRANSCRIPT_SHA256
        ):
            raise RuntimeError(
                "existing control transcript "
                "identity changed"
            )

        provenance = _build_provenance(
            case_id=case_id,
            transcript_sha256=(
                transcript_sha256
            ),
        )

        rights = _build_rights(
            case_id=case_id,
        )

        if case_id == CONTROL_CASE_ID:
            _verify_control_files(
                provenance=provenance,
                rights=rights,
            )
        else:
            _write_bundle(
                file_path=(
                    PROVENANCE_ROOT
                    / f"{case_id}.json"
                ),
                bundle=provenance,
            )

            _write_bundle(
                file_path=(
                    RIGHTS_ROOT
                    / f"{case_id}.json"
                ),
                bundle=rights,
            )

        entries.append(
            ASRAdversarialCorpusGenerationPlanEntry(
                case_id=case_id,
                output_relative_path=(
                    f"source/{case_id}.wav"
                ),
                provenance_record_sha256=(
                    provenance.sha256
                ),
                rights_record_sha256=(
                    rights.sha256
                ),
                transformation_record_sha256=None,
            )
        )

        print(
            f"{case_id}:"
        )
        print(
            "  transcript_sha256:",
            transcript_sha256,
        )
        print(
            "  provenance_sha256:",
            provenance.sha256,
        )
        print(
            "  rights_sha256:",
            rights.sha256,
        )

    plan = (
        build_asr_adversarial_corpus_generation_plan_v1(
            ASRAdversarialCorpusGenerationPlan(
                corpus_id=CORPUS_ID,
                corpus_version=CORPUS_VERSION,
                entries=tuple(entries),
            )
        )
    )

    _write_bundle(
        file_path=GENERATION_PLAN_PATH,
        bundle=plan,
    )

    print()
    print(
        "generation_plan_sha256:",
        plan.sha256,
    )
    print(
        "case_count:",
        len(entries),
    )


if __name__ == "__main__":
    main()
