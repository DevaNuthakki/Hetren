#!/opt/anaconda3/bin/python
"""Guarded one-shot P09.3 H1 protected execution command.

Direct-script execution is intentionally supported. The repository root is
inserted into sys.path before Hetren package imports.

Creating or importing this command does not authorize protected execution.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(
    __file__
).resolve().parents[
    1
]


repo_root_text = str(
    REPO_ROOT
)


if repo_root_text not in sys.path:
    sys.path.insert(
        0,
        repo_root_text,
    )


from packages.engines.behavioral.h1_controlled_active_diagnosis_protected_execution_persistence import (
    persist_h1_protected_execution_attempt,
)


BATCH_ID = "protected_v1"
ATTEMPT_ID = "execution_v1"

CONFIRMATION_TEXT = (
    "EXECUTE_P09_3_H1_PROTECTED_V1_ONCE"
)

BATCH_DIRECTORY = (
    REPO_ROOT
    / "artifacts"
    / "h1_controlled_active_diagnosis"
    / BATCH_ID
)

PUBLIC_MANIFEST = (
    BATCH_DIRECTORY
    / "public"
    / "public_manifest.json"
)

HIDDEN_MANIFEST = (
    BATCH_DIRECTORY
    / "evaluator"
    / "hidden_truth_manifest.json"
)

GENERATION_DISPOSITION = (
    BATCH_DIRECTORY
    / "public"
    / "generation_disposition.json"
)

SEED_COMMITMENT = (
    BATCH_DIRECTORY
    / "public"
    / "seed_commitment.json"
)

GENERATION_RECORD = (
    BATCH_DIRECTORY
    / "public"
    / "generation_record.json"
)

RAW_SEED = (
    BATCH_DIRECTORY
    / "evaluator"
    / "raw_seed.bin"
)

ATTEMPT_DIRECTORY = (
    BATCH_DIRECTORY
    / ATTEMPT_ID
)

ENVIRONMENT_MODULE = (
    REPO_ROOT
    / "environments"
    / "agent"
    / "h1_controlled_active_diagnosis.py"
)

TREATMENT_MODULE = (
    REPO_ROOT
    / "packages"
    / "engines"
    / "behavioral"
    / "h1_controlled_active_diagnosis_protected_execution.py"
)

EVALUATION_MODULE = (
    REPO_ROOT
    / "packages"
    / "engines"
    / "behavioral"
    / "h1_controlled_active_diagnosis_protected_evaluation.py"
)

PERSISTENCE_MODULE = (
    REPO_ROOT
    / "packages"
    / "engines"
    / "behavioral"
    / "h1_controlled_active_diagnosis_protected_execution_persistence.py"
)

THIS_COMMAND = Path(
    __file__
).resolve()


D1_CONTRACT_COMMIT_ID = (
    "e00358f781cb23581a7bb6b8a423081350a6830d"
)

GENERATION_FREEZE_COMMIT_ID = (
    "aba783582336b9add67ed7d93bb1185e1243f430"
)

GENERATION_RECORD_SHA256 = (
    "5cff5a433c5cb841a7a06e37ddc01a041"
    "8534a9a68a3ea3172a4a6991264291f"
)

EXPECTED_PUBLIC_MANIFEST_SHA256 = (
    "b88d9c3bd280f18a56ea9c9c6bb05127"
    "cacba8ebf6d7fbb91deb1b70a9e12c01"
)

EXPECTED_HIDDEN_MANIFEST_SHA256 = (
    "b709a96d33d405d89c545b6c2fa2c923"
    "f6f4c66eb3380b0412faf501bae5e60c"
)

EXPECTED_ENVIRONMENT_MODULE_SHA256 = (
    "960c5a058bb92266e4c54430722f3a1e9"
    "9933423f6fe9f0dda923bd250fdfd2e"
)

EXPECTED_TREATMENT_MODULE_SHA256 = (
    "22a2b6b6e88cddd9057d79c500aa4f620"
    "f0081daf634bf566b31ad7a6488656f"
)

EXPECTED_EVALUATION_MODULE_SHA256 = (
    "c8f38aed18859ecb4f8720ef583953979"
    "0ef1723d46517c547852dcc5deec167"
)

EXPECTED_PERSISTENCE_MODULE_SHA256 = (
    "ee976830cf84ea7dcc17e6e9431902c28ed87a3b23d1243197d5bae44e974184"
)


EXPECTED_GENERATION_ARTIFACT_SHA256 = {
    GENERATION_DISPOSITION:
        "95161cffe0db2aac8a8029243d57febaf"
        "aba68f7198af71a9cfc2101b3c6a9c1",

    SEED_COMMITMENT:
        "1a04be21e6c908e390ea17ba8701dd124"
        "e5cd886d0d4ab23b887094858593c53",

    PUBLIC_MANIFEST:
        "b88d9c3bd280f18a56ea9c9c6bb05127"
        "cacba8ebf6d7fbb91deb1b70a9e12c01",

    RAW_SEED:
        "c1cd47afe62a4ee303334c3cac443e5a"
        "263ff3725ddfec48b7695eafe783cf3d",

    HIDDEN_MANIFEST:
        "b709a96d33d405d89c545b6c2fa2c923"
        "f6f4c66eb3380b0412faf501bae5e60c",

    GENERATION_RECORD:
        "5cff5a433c5cb841a7a06e37ddc01a041"
        "8534a9a68a3ea3172a4a6991264291f",
}


def _git(
    *arguments: str,
) -> str:
    return subprocess.check_output(
        [
            "/usr/bin/git",
            *arguments,
        ],
        cwd=REPO_ROOT,
        text=True,
    ).strip()


def _git_quiet(
    *arguments: str,
) -> bool:
    result = subprocess.run(
        [
            "/usr/bin/git",
            *arguments,
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    return (
        result.returncode
        == 0
    )


def _sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _require_confirmation(
    value: str,
) -> None:
    if value != CONFIRMATION_TEXT:
        raise SystemExit(
            "STOP: protected-execution confirmation "
            "phrase does not match"
        )


def _require_ancestor(
    commit_id: str,
    current_head: str,
    label: str,
) -> None:
    result = subprocess.run(
        [
            "/usr/bin/git",
            "merge-base",
            "--is-ancestor",
            commit_id,
            current_head,
        ],
        cwd=REPO_ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result.returncode != 0:
        raise SystemExit(
            "STOP: "
            + label
            + " is not an ancestor of current HEAD"
        )


def _require_repository_ready(
    expected_head: str,
) -> str:
    if _git(
        "branch",
        "--show-current",
    ) != "portfolio/v1-foundation":
        raise SystemExit(
            "STOP: protected execution requires "
            "portfolio/v1-foundation"
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
            "STOP: repository HEAD does not match "
            "explicitly expected HEAD"
        )

    if len(current_head) != 40:
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
            "STOP: HEAD is not hexadecimal"
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

    _require_ancestor(
        GENERATION_FREEZE_COMMIT_ID,
        current_head,
        "generation-freeze checkpoint",
    )

    _require_ancestor(
        D1_CONTRACT_COMMIT_ID,
        current_head,
        "D1 contract checkpoint",
    )

    return current_head


def _require_tracked_exact(
    path: Path,
    *,
    expected_sha256: str | None,
) -> str:
    relative = path.relative_to(
        REPO_ROOT
    )

    result = subprocess.run(
        [
            "/usr/bin/git",
            "ls-files",
            "--error-unmatch",
            "--",
            str(relative),
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(
            "STOP: protected execution source is not "
            "tracked at current HEAD: "
            + str(relative)
        )

    head_bytes = subprocess.check_output(
        [
            "/usr/bin/git",
            "show",
            "HEAD:"
            + str(relative),
        ],
        cwd=REPO_ROOT,
    )

    worktree_bytes = (
        path.read_bytes()
    )

    head_sha = hashlib.sha256(
        head_bytes
    ).hexdigest()

    worktree_sha = hashlib.sha256(
        worktree_bytes
    ).hexdigest()

    if head_sha != worktree_sha:
        raise SystemExit(
            "STOP: protected execution source differs "
            "from HEAD: "
            + str(relative)
        )

    if (
        expected_sha256 is not None
        and worktree_sha
        != expected_sha256
    ):
        raise SystemExit(
            "STOP: frozen protected-execution source "
            "bytes changed: "
            + str(relative)
        )

    return worktree_sha


def _require_frozen_source_bytes() -> str:
    if (
        _sha256_file(
            ENVIRONMENT_MODULE
        )
        != EXPECTED_ENVIRONMENT_MODULE_SHA256
    ):
        raise SystemExit(
            "STOP: controlled environment bytes changed"
        )

    if (
        _sha256_file(
            TREATMENT_MODULE
        )
        != EXPECTED_TREATMENT_MODULE_SHA256
    ):
        raise SystemExit(
            "STOP: frozen D1 treatment bytes changed"
        )

    if (
        _sha256_file(
            EVALUATION_MODULE
        )
        != EXPECTED_EVALUATION_MODULE_SHA256
    ):
        raise SystemExit(
            "STOP: frozen D1 evaluator bytes changed"
        )

    persistence_sha = (
        _require_tracked_exact(
            PERSISTENCE_MODULE,
            expected_sha256=(
                EXPECTED_PERSISTENCE_MODULE_SHA256
            ),
        )
    )

    _require_tracked_exact(
        THIS_COMMAND,
        expected_sha256=None,
    )

    return persistence_sha


def _require_generation_artifacts() -> None:
    for (
        path,
        expected_sha256,
    ) in (
        EXPECTED_GENERATION_ARTIFACT_SHA256
        .items()
    ):
        if (
            _sha256_file(path)
            != expected_sha256
        ):
            raise SystemExit(
                "STOP: protected generation artifact "
                "changed: "
                + str(
                    path.relative_to(
                        REPO_ROOT
                    )
                )
            )

    disposition = json.loads(
        GENERATION_DISPOSITION.read_text(
            encoding="utf-8"
        )
    )

    if (
        disposition.get("status")
        != "SUCCEEDED"
        or disposition.get("phase")
        != "SUCCEEDED"
    ):
        raise SystemExit(
            "STOP: protected generation disposition "
            "is not SUCCEEDED"
        )

    if (
        disposition.get("batch_id")
        != BATCH_ID
    ):
        raise SystemExit(
            "STOP: generation disposition batch ID changed"
        )


def _require_safe_artifact_boundary() -> None:
    artifacts_directory = (
        REPO_ROOT
        / "artifacts"
    )

    h1_root = (
        artifacts_directory
        / "h1_controlled_active_diagnosis"
    )

    if artifacts_directory.is_symlink():
        raise SystemExit(
            "STOP: artifacts directory must not "
            "be a symbolic link"
        )

    if h1_root.is_symlink():
        raise SystemExit(
            "STOP: H1 artifact root must not "
            "be a symbolic link"
        )

    if (
        not BATCH_DIRECTORY.is_dir()
        or BATCH_DIRECTORY.is_symlink()
    ):
        raise SystemExit(
            "STOP: protected_v1 directory boundary "
            "is invalid"
        )

    if ATTEMPT_DIRECTORY.exists():
        raise SystemExit(
            "STOP: execution_v1 already exists; "
            "rerunning is forbidden"
        )

    expected_generation_files = {
        "public/generation_disposition.json",
        "public/seed_commitment.json",
        "public/public_manifest.json",
        "public/generation_record.json",
        "evaluator/raw_seed.bin",
        "evaluator/hidden_truth_manifest.json",
    }

    actual_generation_files = {
        str(
            path.relative_to(
                BATCH_DIRECTORY
            )
        )
        for path
        in BATCH_DIRECTORY.rglob("*")
        if path.is_file()
    }

    if (
        actual_generation_files
        != expected_generation_files
    ):
        raise SystemExit(
            "STOP: protected_v1 pre-execution "
            "file surface changed"
        )

    candidates = (
        ATTEMPT_DIRECTORY
        / "public"
        / "execution_disposition.json",

        ATTEMPT_DIRECTORY
        / "public"
        / "treatment_batch.json",

        ATTEMPT_DIRECTORY
        / "public"
        / "execution_record.json",

        ATTEMPT_DIRECTORY
        / "evaluator"
        / "evaluation.json",
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
                str(relative),
            ],
            cwd=REPO_ROOT,
            check=False,
        )

        if result.returncode != 0:
            raise SystemExit(
                "STOP: protected execution artifact "
                "is not Git-ignored: "
                + str(relative)
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "One-shot P09.3 H1 protected execution. "
            "Do not run without explicit authorization."
        )
    )

    parser.add_argument(
        "--expected-head",
        required=True,
    )

    parser.add_argument(
        "--confirm",
        required=True,
    )

    return parser


def main() -> None:
    args = _parser().parse_args()

    _require_confirmation(
        args.confirm
    )

    repository_head = (
        _require_repository_ready(
            args.expected_head
        )
    )

    persistence_sha = (
        _require_frozen_source_bytes()
    )

    _require_generation_artifacts()

    _require_safe_artifact_boundary()

    result = (
        persist_h1_protected_execution_attempt(
            batch_directory=(
                BATCH_DIRECTORY
            ),
            batch_id=BATCH_ID,
            attempt_id=ATTEMPT_ID,
            public_manifest_path=(
                PUBLIC_MANIFEST
            ),
            hidden_manifest_path=(
                HIDDEN_MANIFEST
            ),
            expected_public_manifest_sha256=(
                EXPECTED_PUBLIC_MANIFEST_SHA256
            ),
            expected_hidden_manifest_sha256=(
                EXPECTED_HIDDEN_MANIFEST_SHA256
            ),
            repository_head_commit_id=(
                repository_head
            ),
            d1_contract_commit_id=(
                D1_CONTRACT_COMMIT_ID
            ),
            generation_freeze_commit_id=(
                GENERATION_FREEZE_COMMIT_ID
            ),
            generation_record_sha256=(
                GENERATION_RECORD_SHA256
            ),
            environment_module_sha256=(
                EXPECTED_ENVIRONMENT_MODULE_SHA256
            ),
            treatment_module_sha256=(
                EXPECTED_TREATMENT_MODULE_SHA256
            ),
            evaluation_module_sha256=(
                EXPECTED_EVALUATION_MODULE_SHA256
            ),
            execution_persistence_module_sha256=(
                persistence_sha
            ),
        )
    )

    print(
        "P09.3 H1 protected execution: SUCCEEDED"
    )

    print(
        "attempt_directory =",
        result.attempt_directory,
    )

    print(
        "treatment_batch_sha256 =",
        result.treatment_batch_sha256,
    )

    print(
        "evaluation_sha256 =",
        result.evaluation_sha256,
    )

    print(
        "execution_record_sha256 =",
        result.execution_record_sha256,
    )

    print(
        "Hidden assignments and evaluator metrics "
        "were not printed."
    )


if __name__ == "__main__":
    main()
