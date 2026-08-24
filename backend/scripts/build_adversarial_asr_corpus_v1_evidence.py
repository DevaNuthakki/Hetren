"""Build committed source-visible evidence for adversarial ASR corpus v1."""

from __future__ import annotations

import json
from pathlib import Path

from hvee.packs.asr.adversarial_corpus_v1 import (
    build_asr_adversarial_corpus_v1,
)


BACKEND_ROOT = (
    Path(__file__).resolve().parents[1]
)

CORPUS_ROOT = (
    BACKEND_ROOT
    / "corpora/asr/adversarial/v1"
)


def _write_bundle(
    *,
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


def main() -> None:
    (
        _suite,
        suite_evidence,
        _definition,
        manifest,
    ) = build_asr_adversarial_corpus_v1()

    suite_path = (
        CORPUS_ROOT
        / "specification/suite-evidence.json"
    )

    manifest_path = (
        CORPUS_ROOT
        / "specification/corpus-manifest.json"
    )

    _write_bundle(
        path=suite_path,
        bundle=suite_evidence,
    )

    _write_bundle(
        path=manifest_path,
        bundle=manifest,
    )

    print(
        "suite_evidence_sha256:",
        suite_evidence.sha256,
    )
    print(
        "corpus_manifest_sha256:",
        manifest.sha256,
    )
    print(
        "suite_evidence_path:",
        suite_path,
    )
    print(
        "corpus_manifest_path:",
        manifest_path,
    )


if __name__ == "__main__":
    main()
