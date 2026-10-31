#!/opt/anaconda3/bin/python

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import secrets
import subprocess
import sys


REPO_ROOT = Path(
    __file__
).resolve().parents[
    1
]


if str(
    REPO_ROOT
) not in sys.path:
    sys.path.insert(
        0,
        str(
            REPO_ROOT
        ),
    )


from packages.engines.behavioral.p09_4_protected_persistence import (
    persist_p09_4_generation_attempt as _persist_generation_attempt,
)


CONFIRMATION_TEXT = (
    "CREATE_P09_4_PROTECTED_POPULATION_ONCE"
)

BATCH_ID = (
    "protected_v1"
)

PROTOCOL_SHA256 = (
    "46ea27e825bedbfbd8ee0443173884f904f20881fc929a4c44fae30c550e7621"
)

SOURCE_COMMIT = (
    "dab6585c751ac457b2b6578a622ea25d49847d4f"
)

EXPECTED_GENERATOR_MODULE_SHA256 = (
    "adff1938a5709ffd04ae27f8bd7744e25e2bcc295bfd7dca857994ba6572ac6b"
)

EXPECTED_MATERIALIZER_MODULE_SHA256 = (
    "b5861344b66c9a3cf8ea6e4c8921441fd34410f52fbce3d5745eba67fa71d027"
)

EXPECTED_PERSISTENCE_MODULE_SHA256 = (
    "4aafffdba38b86aa3836bc62f8258bbcea54d09bf98c01661c481b0ee08b40a4"
)


PROTOCOL_DOCUMENT = (
    REPO_ROOT
    / "docs"
    / "portfolio"
    / "p09.4-protected-study-preregistration.md"
)

GENERATOR_MODULE = (
    REPO_ROOT
    / "packages"
    / "engines"
    / "behavioral"
    / "p09_4_protected_generation.py"
)

MATERIALIZER_MODULE = (
    REPO_ROOT
    / "packages"
    / "engines"
    / "behavioral"
    / "p09_4_protected_materialization.py"
)

PERSISTENCE_MODULE = (
    REPO_ROOT
    / "packages"
    / "engines"
    / "behavioral"
    / "p09_4_protected_persistence.py"
)

ARTIFACT_ROOT = (
    REPO_ROOT
    / "artifacts"
    / "p09_4_scientific_arms"
)


_PROTECTED_RELATIVE_PATHS = (
    "public/generation_disposition.json",
    "public/generation_seed_commitment.json",
    "public/public_population_manifest.json",
    "public/generation_record.json",
    "evaluator/generation_raw_seed.bin",
    "evaluator/hidden_assignment_manifest.json",
)


def _git(
    *args: str,
) -> str:
    return subprocess.check_output(
        [
            "/usr/bin/git",
            *args,
        ],
        cwd=REPO_ROOT,
        text=True,
    ).strip()


def _git_quiet(
    *args: str,
) -> bool:
    result = subprocess.run(
        [
            "/usr/bin/git",
            *args,
        ],
        cwd=REPO_ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return (
        result.returncode
        == 0
    )


def _require_confirmation(
    value: str,
) -> None:
    if value != CONFIRMATION_TEXT:
        raise SystemExit(
            "STOP: protected-generation confirmation phrase does not match"
        )


def _require_commit_id(
    value: str,
    name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or len(
            value
        )
        != 40
    ):
        raise SystemExit(
            "STOP: "
            + name
            + " must be an exact 40-hex Git commit ID"
        )

    try:
        int(
            value,
            16,
        )
    except ValueError as exc:
        raise SystemExit(
            "STOP: "
            + name
            + " is not hexadecimal"
        ) from exc

    return value


def _require_repository_ready(
    expected_head: str,
) -> str:
    expected_head = (
        _require_commit_id(
            expected_head,
            "expected_head",
        )
    )

    _require_commit_id(
        SOURCE_COMMIT,
        "SOURCE_COMMIT",
    )

    if _git(
        "branch",
        "--show-current",
    ) != "portfolio/v1-foundation":
        raise SystemExit(
            "STOP: protected generation requires portfolio/v1-foundation"
        )

    if _git(
        "rev-parse",
        "--show-object-format",
    ) != "sha1":
        raise SystemExit(
            "STOP: unexpected Git object format"
        )

    current_head = (
        _git(
            "rev-parse",
            "HEAD",
        )
    )

    if current_head != expected_head:
        raise SystemExit(
            "STOP: repository HEAD does not match explicitly expected HEAD"
        )

    if not _git_quiet(
        "diff",
        "--quiet",
    ):
        raise SystemExit(
            "STOP: tracked worktree is not clean"
        )

    if not _git_quiet(
        "diff",
        "--cached",
        "--quiet",
    ):
        raise SystemExit(
            "STOP: index is not clean"
        )

    if not _git_quiet(
        "cat-file",
        "-e",
        SOURCE_COMMIT
        + "^{commit}",
    ):
        raise SystemExit(
            "STOP: frozen SOURCE_COMMIT does not exist"
        )

    if not _git_quiet(
        "merge-base",
        "--is-ancestor",
        SOURCE_COMMIT,
        current_head,
    ):
        raise SystemExit(
            "STOP: authorized HEAD does not descend from frozen SOURCE_COMMIT"
        )

    return current_head


def _sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _require_frozen_bytes() -> None:
    checks = (
        (
            PROTOCOL_DOCUMENT,
            PROTOCOL_SHA256,
            "protected-study protocol",
        ),
        (
            GENERATOR_MODULE,
            EXPECTED_GENERATOR_MODULE_SHA256,
            "protected generator",
        ),
        (
            MATERIALIZER_MODULE,
            EXPECTED_MATERIALIZER_MODULE_SHA256,
            "protected materializer",
        ),
        (
            PERSISTENCE_MODULE,
            EXPECTED_PERSISTENCE_MODULE_SHA256,
            "protected persistence",
        ),
    )

    for (
        path,
        expected,
        label,
    ) in checks:
        actual = (
            _sha256_file(
                path
            )
        )

        if actual != expected:
            raise SystemExit(
                "STOP: frozen "
                + label
                + " bytes changed"
            )


def _git_ignored(
    path: Path,
) -> bool:
    relative = path.relative_to(
        REPO_ROOT
    )

    result = subprocess.run(
        [
            "/usr/bin/git",
            "check-ignore",
            "-q",
            "--no-index",
            str(
                relative
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return (
        result.returncode
        == 0
    )


def _require_safe_artifact_boundary() -> None:
    artifacts_directory = (
        REPO_ROOT
        / "artifacts"
    )

    if artifacts_directory.is_symlink():
        raise SystemExit(
            "STOP: artifacts directory must not be a symbolic link"
        )

    if ARTIFACT_ROOT.is_symlink():
        raise SystemExit(
            "STOP: P09.4 artifact root must not be a symbolic link"
        )

    batch_directory = (
        ARTIFACT_ROOT
        / BATCH_ID
    )

    if batch_directory.exists():
        raise SystemExit(
            "STOP: protected_v1 already exists; rerolling is forbidden"
        )

    for relative in _PROTECTED_RELATIVE_PATHS:
        candidate = (
            batch_directory
            / relative
        )

        if not _git_ignored(
            candidate
        ):
            raise SystemExit(
                "STOP: protected artifact path is not Git-ignored: "
                + str(
                    candidate.relative_to(
                        REPO_ROOT
                    )
                )
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create the single-use P09.4 protected population. "
            "This command creates irreversible protected generation evidence. "
            "Do not run it before explicit K5E authorization."
        )
    )

    parser.add_argument(
        "--expected-head",
        required=True,
        help=(
            "Exact 40-hex repository HEAD explicitly approved by the "
            "K5E protected-generation authorization gate."
        ),
    )

    parser.add_argument(
        "--confirm",
        required=True,
        help=(
            "Must exactly equal the irreversible protected-generation "
            "confirmation phrase."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = (
        parse_args()
    )

    _require_confirmation(
        args.confirm
    )

    current_head = (
        _require_repository_ready(
            args.expected_head
        )
    )

    _require_frozen_bytes()

    _require_safe_artifact_boundary()

    result = (
        _persist_generation_attempt(
            artifact_root=(
                ARTIFACT_ROOT
            ),
            batch_id=(
                BATCH_ID
            ),
            protocol_sha256=(
                PROTOCOL_SHA256
            ),
            source_commit=(
                SOURCE_COMMIT
            ),
            repository_head_commit_id=(
                current_head
            ),
            generator_module_sha256=(
                EXPECTED_GENERATOR_MODULE_SHA256
            ),
            materializer_module_sha256=(
                EXPECTED_MATERIALIZER_MODULE_SHA256
            ),
            persistence_module_sha256=(
                EXPECTED_PERSISTENCE_MODULE_SHA256
            ),
            seed_factory=(
                secrets.token_bytes
            ),
        )
    )

    print(
        "P09.4 protected population generation: SUCCEEDED"
    )

    print(
        "batch_directory =",
        result.batch_directory,
    )

    print(
        "repository_head_commit_id =",
        result.repository_head_commit_id,
    )

    print(
        "source_commit =",
        result.source_commit,
    )

    print(
        "generator_module_sha256 =",
        result.generator_module_sha256,
    )

    print(
        "materializer_module_sha256 =",
        result.materializer_module_sha256,
    )

    print(
        "persistence_module_sha256 =",
        result.persistence_module_sha256,
    )

    print(
        "generation_seed_sha256 =",
        result.generation_seed_sha256,
    )

    print(
        "generation_seed_commitment_file_sha256 =",
        result.generation_seed_commitment_file_sha256,
    )

    print(
        "public_population_manifest_sha256 =",
        result.public_population_manifest_sha256,
    )

    print(
        "hidden_assignment_manifest_sha256 =",
        result.hidden_assignment_manifest_sha256,
    )

    print(
        "generation_record_sha256 =",
        result.generation_record_sha256,
    )

    print(
        "Raw generation-seed bytes were not printed."
    )

    print(
        "This population generation does not authorize treatment execution."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
