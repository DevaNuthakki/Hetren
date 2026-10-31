#!/opt/anaconda3/bin/python
"""One-shot P09.3 H1 protected-generation command.

DO NOT invoke casually.

This command creates the real protected seed and protected batch artifacts.

Required safeguards:

- exact confirmation phrase;
- expected repository HEAD supplied by the operator;
- portfolio/v1-foundation branch;
- SHA-1 Git object format;
- clean tracked worktree and clean index;
- frozen protocol;
- frozen P09.3C1 harness identity;
- frozen P09.3C2 generator bytes;
- all protected paths must be Git-ignored;
- protected_v1 must not already exist.

The command prints hashes and paths only.

It never prints raw seed bytes.
"""

import argparse
import hashlib
from pathlib import Path
import secrets
import subprocess
import sys


REPO_ROOT = Path(
    __file__
).resolve().parents[1]

if str(
    REPO_ROOT
) not in sys.path:
    sys.path.insert(
        0,
        str(
            REPO_ROOT
        ),
    )


from packages.engines.behavioral.h1_controlled_active_diagnosis_persistence import (  # noqa: E402
    persist_h1_generation_attempt,
)


CONFIRMATION_TEXT = (
    "CREATE_P09_3_H1_PROTECTED_BATCH_ONCE"
)

BATCH_ID = "protected_v1"

PROTOCOL_SHA256 = (
    "6b738092e28036ea400f6498a4ad1663"
    "dd8cbb1e1c9c1e54e48ff4030ceb6ef8"
)

HARNESS_COMMIT_ID = (
    "ccc65a6a7e3e1745e0ceda3968287507a2de81d2"
)

EXPECTED_GENERATOR_MODULE_SHA256 = (
    "17424bd4cc7ea8bb2215b18ea9d19468"
    "b2dde8bb35c1d1d91bea69d2288ff39b"
)

GENERATOR_MODULE = (
    REPO_ROOT
    / "packages"
    / "engines"
    / "behavioral"
    / "h1_controlled_active_diagnosis_generation.py"
)

ARTIFACT_ROOT = (
    REPO_ROOT
    / "artifacts"
    / "h1_controlled_active_diagnosis"
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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    return result.returncode == 0


def _require_confirmation(
    value: str,
) -> None:
    if value != CONFIRMATION_TEXT:
        raise SystemExit(
            "STOP: protected-generation confirmation phrase does not match"
        )


def _require_repository_ready(
    expected_head: str,
) -> str:
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

    current_head = _git(
        "rev-parse",
        "HEAD",
    )

    if current_head != expected_head:
        raise SystemExit(
            "STOP: repository HEAD does not match explicitly expected HEAD"
        )

    if len(
        current_head
    ) != 40:
        raise SystemExit(
            "STOP: expected a 40-hex Git commit ID"
        )

    try:
        int(
            current_head,
            16,
        )
    except ValueError as exc:
        raise SystemExit(
            "STOP: HEAD is not a hexadecimal Git commit ID"
        ) from exc

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

    return current_head


def _require_generator_bytes() -> str:
    actual = hashlib.sha256(
        GENERATOR_MODULE.read_bytes()
    ).hexdigest()

    if (
        actual
        != EXPECTED_GENERATOR_MODULE_SHA256
    ):
        raise SystemExit(
            "STOP: frozen generator module bytes changed"
        )

    return actual


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
            "STOP: H1 artifact root must not be a symbolic link"
        )

    batch_directory = (
        ARTIFACT_ROOT
        / BATCH_ID
    )

    if batch_directory.exists():
        raise SystemExit(
            "STOP: protected_v1 already exists; rerolling is forbidden"
        )

    candidates = (
        batch_directory
        / "public"
        / "generation_disposition.json",

        batch_directory
        / "public"
        / "seed_commitment.json",

        batch_directory
        / "public"
        / "public_manifest.json",

        batch_directory
        / "public"
        / "generation_record.json",

        batch_directory
        / "evaluator"
        / "raw_seed.bin",

        batch_directory
        / "evaluator"
        / "hidden_truth_manifest.json",
    )

    for path in candidates:
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
        )

        if result.returncode != 0:
            raise SystemExit(
                "STOP: protected artifact path is not Git-ignored: "
                + str(
                    relative
                )
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create the single-use P09.3 H1 protected batch. "
            "This command creates protected data."
        )
    )

    parser.add_argument(
        "--expected-head",
        required=True,
        help=(
            "Exact 40-hex repository HEAD approved by the "
            "pre-protected freeze gate."
        ),
    )

    parser.add_argument(
        "--confirm",
        required=True,
        help=(
            "Must exactly equal the protected-generation "
            "confirmation phrase."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    _require_confirmation(
        args.confirm
    )

    current_head = (
        _require_repository_ready(
            args.expected_head
        )
    )

    generator_sha256 = (
        _require_generator_bytes()
    )

    _require_safe_artifact_boundary()

    result = persist_h1_generation_attempt(
        artifact_root=ARTIFACT_ROOT,
        batch_id=BATCH_ID,
        protocol_sha256=PROTOCOL_SHA256,
        harness_commit_id=HARNESS_COMMIT_ID,
        repository_head_commit_id=current_head,
        generator_module_sha256=generator_sha256,
        seed_factory=secrets.token_bytes,
    )

    print(
        "P09.3 H1 protected generation: SUCCEEDED"
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
        "generator_module_sha256 =",
        result.generator_module_sha256,
    )

    print(
        "seed_commitment_sha256 =",
        result.seed_commitment_sha256,
    )

    print(
        "public_manifest_sha256 =",
        result.public_manifest_sha256,
    )

    print(
        "hidden_truth_manifest_sha256 =",
        result.hidden_truth_manifest_sha256,
    )

    print(
        "generation_record_sha256 =",
        result.generation_record_sha256,
    )

    print(
        "Raw seed bytes were not printed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
