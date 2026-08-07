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


EVALUATION_RESULT_PROVENANCE_SCHEMA_VERSION = 1

SUPPORTED_RESULT_EXECUTION_MODES = frozenset(
    {
        "uploaded_transcript",
        "server_asr",
        "runner_asr",
        "seed_fixture",
    }
)


def calculate_text_sha256(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Evidence text must be a string."
        )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _build_run_manifest_evidence(
    evaluation_run: models.EvaluationRun,
) -> dict[str, object]:
    manifest = evaluation_run.manifest

    if manifest is None:
        return {
            "status": "legacy_unsealed",
            "schema_version": None,
            "sha256": None,
        }

    if (
        manifest.run_id != evaluation_run.id
        or not verify_evaluation_run_manifest(
            manifest
        )
    ):
        raise ValueError(
            "Evaluation run manifest is invalid."
        )

    return {
        "status": "sealed",
        "schema_version": (
            manifest.schema_version
        ),
        "sha256": manifest.manifest_sha256,
    }


def build_evaluation_result_provenance_payload(
    *,
    result: models.EvaluationResult,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    execution_mode: str,
    server_observed: dict[str, object] | None = None,
    external_reported: dict[str, object] | None = None,
) -> dict[str, object]:
    normalized_mode = (
        execution_mode.strip()
        if isinstance(execution_mode, str)
        else ""
    )

    if (
        normalized_mode
        not in SUPPORTED_RESULT_EXECUTION_MODES
    ):
        raise ValueError(
            "Unsupported evaluation execution mode."
        )

    if result.id is None:
        raise ValueError(
            "Evaluation result must be flushed "
            "before provenance is built."
        )

    if (
        result.run_id != evaluation_run.id
        or result.test_case_id != test_case.id
    ):
        raise ValueError(
            "Evaluation result provenance resources "
            "do not match."
        )

    reference_text = test_case.reference_transcript
    generated_text = result.generated_transcript

    if not isinstance(reference_text, str):
        raise ValueError(
            "Reference transcript is unavailable."
        )

    if not isinstance(generated_text, str):
        raise ValueError(
            "Generated transcript is unavailable."
        )

    reference_bytes = reference_text.encode(
        "utf-8"
    )
    generated_bytes = generated_text.encode(
        "utf-8"
    )

    payload: dict[str, object] = {
        "schema_version": (
            EVALUATION_RESULT_PROVENANCE_SCHEMA_VERSION
        ),
        "evaluation_type": ASR_EVALUATION_TYPE,
        "result": {
            "id": result.id,
            "run_id": result.run_id,
            "test_case_id": result.test_case_id,
        },
        "run_manifest": (
            _build_run_manifest_evidence(
                evaluation_run
            )
        ),
        "evidence": {
            "reference_transcript": {
                "sha256": calculate_text_sha256(
                    reference_text
                ),
                "utf8_bytes": len(
                    reference_bytes
                ),
            },
            "generated_transcript": {
                "sha256": calculate_text_sha256(
                    generated_text
                ),
                "utf8_bytes": len(
                    generated_bytes
                ),
            },
        },
        "evaluation": {
            "engine": HETREN_EVALUATOR_ENGINE,
            "contract_version": (
                ASR_EVALUATOR_CONTRACT_VERSION
            ),
            "wer": result.wer,
            "cer": result.cer,
            "quality_label": (
                result.quality_label
            ),
        },
        "execution": {
            "mode": normalized_mode,
            "requested_model": (
                evaluation_run.model_name
            ),
            "server_observed": dict(
                server_observed or {}
            ),
            "external_reported": dict(
                external_reported or {}
            ),
        },
    }

    # Validate that the complete evidence payload is
    # deterministic JSON before it can be persisted.
    canonicalize_json(payload)

    return payload


def stage_evaluation_result_provenance(
    db: Session,
    *,
    result: models.EvaluationResult,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    execution_mode: str,
    server_observed: dict[str, object] | None = None,
    external_reported: dict[str, object] | None = None,
) -> models.EvaluationResultProvenance:
    if result.id is None:
        db.flush()

    if result.provenance is not None:
        raise ValueError(
            "Evaluation result provenance already exists."
        )

    payload = (
        build_evaluation_result_provenance_payload(
            result=result,
            evaluation_run=evaluation_run,
            test_case=test_case,
            execution_mode=execution_mode,
            server_observed=server_observed,
            external_reported=external_reported,
        )
    )

    provenance = models.EvaluationResultProvenance(
        result_id=result.id,
        schema_version=(
            EVALUATION_RESULT_PROVENANCE_SCHEMA_VERSION
        ),
        evaluation_type=ASR_EVALUATION_TYPE,
        execution_mode=execution_mode.strip(),
        provenance_payload=payload,
        provenance_sha256=(
            calculate_manifest_sha256(payload)
        ),
    )

    db.add(provenance)

    return provenance


def verify_evaluation_result_provenance(
    provenance: models.EvaluationResultProvenance,
) -> bool:
    payload = provenance.provenance_payload

    if not isinstance(payload, dict):
        return False

    if (
        provenance.schema_version
        != EVALUATION_RESULT_PROVENANCE_SCHEMA_VERSION
        or provenance.evaluation_type
        != ASR_EVALUATION_TYPE
        or payload.get("schema_version")
        != provenance.schema_version
        or payload.get("evaluation_type")
        != provenance.evaluation_type
    ):
        return False

    execution = payload.get("execution")

    if (
        not isinstance(execution, dict)
        or execution.get("mode")
        != provenance.execution_mode
    ):
        return False

    try:
        expected_sha256 = (
            calculate_manifest_sha256(
                payload
            )
        )
    except ValueError:
        return False

    return (
        provenance.provenance_sha256
        == expected_sha256
    )
