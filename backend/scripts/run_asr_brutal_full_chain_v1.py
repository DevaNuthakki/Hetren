#!/usr/bin/env python3
"""Launch one immutable real ASR Brutal Validation full-chain run."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


from app.adversarial_asr_brutal_campaign import (
    bind_asr_brutal_validation_media_v1,
)
from app.adversarial_asr_brutal_full_chain_runner import (
    execute_asr_brutal_full_chain_run_v1,
)


_AUTHORIZATION_TYPE = (
    "brutal_incident_materialization_authorization"
)
_AUTHORIZATION_SCOPE = (
    "materialize_and_replay_locked_severe_noise_incident"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the real ten-stage ASR Brutal Validation evidence "
            "workflow. Governance remains withheld pending independent "
            "authorized human review."
        )
    )
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument("--corpus-generated-root", required=True, type=Path)
    parser.add_argument("--brutal-generated-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--operator-authorization", required=True, type=Path)
    return parser.parse_args()


def _authorization_sha256(
    *,
    path: Path,
    repository_commit: str,
    output_root: Path,
) -> str:
    resolved = path.resolve(strict=True)
    try:
        content = resolved.read_bytes()
        record = json.loads(content.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit(
            "Operator authorization must be a readable UTF-8 JSON file."
        ) from error

    required = {
        "schema_version",
        "type",
        "operator_key",
        "scope",
        "repository_commit",
        "output_root",
        "granted",
        "statement",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise SystemExit(
            "Operator authorization has an invalid evidence shape."
        )
    if (
        record["schema_version"] != 1
        or record["type"] != _AUTHORIZATION_TYPE
        or record["scope"] != _AUTHORIZATION_SCOPE
        or record["repository_commit"] != repository_commit
        or Path(record["output_root"]).resolve(strict=False)
        != output_root.resolve(strict=False)
        or record["granted"] is not True
        or not isinstance(record["operator_key"], str)
        or not record["operator_key"].strip()
        or not isinstance(record["statement"], str)
        or not record["statement"].strip()
    ):
        raise SystemExit(
            "Operator authorization does not authorize this exact run."
        )
    return hashlib.sha256(content).hexdigest()


def _actual_repository_commit(repository_root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit("Cannot resolve repository HEAD.") from error


def main() -> int:
    arguments = _arguments()
    repository = arguments.repository_root.resolve(strict=True)
    actual_commit = _actual_repository_commit(repository)
    if actual_commit != arguments.repository_commit:
        raise SystemExit(
            "--repository-commit does not match the current repository HEAD."
        )
    authorization_sha256 = _authorization_sha256(
        path=arguments.operator_authorization,
        repository_commit=actual_commit,
        output_root=arguments.output_root,
    )
    bundle = bind_asr_brutal_validation_media_v1(
        corpus_generated_root=arguments.corpus_generated_root,
        brutal_generated_root=arguments.brutal_generated_root,
    )

    print("===== REAL ASR BRUTAL FULL-CHAIN RUN =====", flush=True)
    print(f"repository_commit={actual_commit}", flush=True)
    print(f"case_count={len(bundle.suite.cases)}", flush=True)
    print("model_count=2", flush=True)
    print("planned_result_count=26", flush=True)
    print(f"output_root={arguments.output_root}", flush=True)
    print(
        f"operator_authorization_sha256={authorization_sha256}",
        flush=True,
    )
    print("contract_promotion_authorized=false", flush=True)
    print("certification_authorized=false", flush=True)
    print("qualification_authority=false", flush=True)
    print(
        "Real model execution and incident replay may be quiet for several "
        "minutes.",
        flush=True,
    )

    result = execute_asr_brutal_full_chain_run_v1(
        bundle=bundle,
        output_root=arguments.output_root,
        repository_root=repository,
        repository_commit=actual_commit,
        operator_authorization_sha256=authorization_sha256,
    )

    print("===== FULL-CHAIN RESULT =====", flush=True)
    print(json.dumps(
        {
            "payload": result.payload,
            "sha256": result.sha256,
        },
        indent=2,
        sort_keys=True,
    ))
    print(
        "FULL_CHAIN_EXECUTION_REACHED_GOVERNANCE_GATE=true",
        flush=True,
    )
    print(
        "GOVERNANCE_ASSURANCE_WITHHELD=true",
        flush=True,
    )
    print("CERTIFICATION_ISSUED=false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
