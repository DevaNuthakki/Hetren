import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app import models


EVALUATION_MANIFEST_SCHEMA_VERSION = 1
ASR_EVALUATION_TYPE = "asr"
HETREN_EVALUATOR_ENGINE = "hetren"
ASR_EVALUATOR_CONTRACT_VERSION = "asr-v1"


def canonicalize_json(
    payload: dict[str, Any],
) -> str:
    """
    Serialize structured provenance deterministically.

    Sorting keys and removing insignificant whitespace ensures that the
    same logical manifest always produces the same SHA-256 digest.
    """
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Evaluation provenance must contain valid "
            "JSON-serializable values."
        ) from exc


def calculate_manifest_sha256(
    payload: dict[str, Any],
) -> str:
    canonical_payload = canonicalize_json(payload)

    return hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()


def build_evaluation_run_manifest_payload(
    *,
    run_id: int,
    project_id: int,
    run_name: str,
    model_name: str,
) -> dict[str, Any]:
    """
    Build the immutable facts known when an ASR run is created.

    Test cases, artifacts, runner identity, provider metadata, and
    generated outputs are intentionally excluded because they are not
    necessarily known at run-creation time.
    """
    return {
        "schema_version": (
            EVALUATION_MANIFEST_SCHEMA_VERSION
        ),
        "evaluation_type": ASR_EVALUATION_TYPE,
        "run": {
            "id": run_id,
            "project_id": project_id,
            "name": run_name,
        },
        "model": {
            "name": model_name,
        },
        "evaluator": {
            "engine": HETREN_EVALUATOR_ENGINE,
            "contract_version": (
                ASR_EVALUATOR_CONTRACT_VERSION
            ),
        },
    }


def stage_evaluation_run_manifest(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
) -> models.EvaluationRunManifest:
    """
    Stage one sealed manifest for a newly created evaluation run.

    The caller owns the transaction so run creation and manifest
    creation can commit atomically.
    """
    if evaluation_run.id is None:
        raise ValueError(
            "Evaluation run must be flushed before "
            "creating its manifest."
        )

    payload = build_evaluation_run_manifest_payload(
        run_id=evaluation_run.id,
        project_id=evaluation_run.project_id,
        run_name=evaluation_run.run_name,
        model_name=evaluation_run.model_name,
    )

    manifest = models.EvaluationRunManifest(
        run_id=evaluation_run.id,
        schema_version=(
            EVALUATION_MANIFEST_SCHEMA_VERSION
        ),
        evaluation_type=ASR_EVALUATION_TYPE,
        manifest_payload=payload,
        manifest_sha256=(
            calculate_manifest_sha256(payload)
        ),
    )

    db.add(manifest)

    return manifest



def stage_evaluation_run_with_manifest(
    db: Session,
    *,
    project_id: int,
    run_name: str,
    model_name: str = "not_configured",
    status: str = "created",
) -> models.EvaluationRun:
    """
    Stage a new evaluation run and its sealed manifest together.

    The caller owns the transaction. Flushing assigns the run ID
    before the manifest is built, so both records can be committed
    atomically.
    """
    evaluation_run = models.EvaluationRun(
        project_id=project_id,
        run_name=run_name,
        model_name=model_name,
        status=status,
    )

    db.add(evaluation_run)
    db.flush()

    stage_evaluation_run_manifest(
        db,
        evaluation_run=evaluation_run,
    )

    return evaluation_run


def verify_evaluation_run_manifest(
    manifest: models.EvaluationRunManifest,
) -> bool:
    """
    Verify that the stored manifest payload still matches its digest
    and its indexed schema/type fields.
    """
    payload = manifest.manifest_payload

    if not isinstance(payload, dict):
        return False

    if (
        payload.get("schema_version")
        != manifest.schema_version
    ):
        return False

    if (
        payload.get("evaluation_type")
        != manifest.evaluation_type
    ):
        return False

    return (
        calculate_manifest_sha256(payload)
        == manifest.manifest_sha256
    )
