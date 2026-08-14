"""Generate one pinned adversarial ASR synthetic source asset."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.adversarial_asr_corpus_generation_service import (
    generate_asr_adversarial_synthetic_source_v1,
)
from app.adversarial_asr_espeak import (
    ASRAdversarialEspeak,
)
from app.adversarial_asr_ffprobe import (
    ASRAdversarialFFprobe,
)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--case-id",
        required=True,
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=Path(
            "corpora/asr/adversarial/v1"
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            "corpora/asr/adversarial/v1/generated"
        ),
    )
    parser.add_argument(
        "--espeak",
        type=Path,
        default=Path(
            "/usr/bin/espeak-ng"
        ),
    )
    parser.add_argument(
        "--dpkg-query",
        type=Path,
        default=Path(
            "/usr/bin/dpkg-query"
        ),
    )
    parser.add_argument(
        "--ffprobe",
        type=Path,
        default=Path(
            "/usr/bin/ffprobe"
        ),
    )

    arguments = parser.parse_args()

    synthesizer = (
        ASRAdversarialEspeak(
            executable_path=(
                arguments.espeak
            ),
            dpkg_query_path=(
                arguments.dpkg_query
            ),
        )
    )

    probe = ASRAdversarialFFprobe(
        executable_path=(
            arguments.ffprobe
        ),
    )

    generated = (
        generate_asr_adversarial_synthetic_source_v1(
            corpus_root=(
                arguments.corpus_root
            ),
            output_root=(
                arguments.output_root
            ),
            case_id=(
                arguments.case_id
            ),
            synthesizer=synthesizer,
            media_probe=probe,
        )
    )

    print(
        json.dumps(
            asdict(
                generated
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
