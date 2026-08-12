from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.critical_terminology_vocabulary_service import (
    CriticalTerminologyVocabularyIntegrityError,
)
from app.evaluation_provenance import (
    CRITICAL_TERMINOLOGY_MANIFEST_STATUS_CONFIGURED,
    CRITICAL_TERMINOLOGY_MANIFEST_STATUS_NOT_CONFIGURED,
    LEGACY_EVALUATION_MANIFEST_SCHEMA_VERSION,
    resolve_evaluation_run_critical_terminology_profile,
    verify_evaluation_result_observation_binding,
    verify_evaluation_run_manifest,
)
from app.hvee_observation_evidence import (
    HveeObservationEvidenceError,
    load_test_case_observation_evidence_records,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.packs.asr import (
    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
    CRITICAL_IDENTIFIER_METRICS,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_METRICS,
    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
    CRITICAL_TERMINOLOGY_METRICS,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
)


class ASRSemanticEvidenceIntegrityError(ValueError):
    """Raised when persisted ASR semantic evidence cannot be trusted."""


def _serialize_observation(
    record: ObservationEvidenceRecord,
) -> dict[str, object]:
    return {
        "metric_key": record.metric_key,
        "metric_version": record.metric_version,
        "evaluator_key": record.evaluator_key,
        "evaluator_version": record.evaluator_version,
        "status": record.status.value,
        "value_type": record.value_type.value,
        "value": record.value,
        "status_detail": record.status_detail,
    }


def _load_result_bound_run_manifest(
    db: Session,
    *,
    result: models.EvaluationResult,
    evaluation_run: models.EvaluationRun,
) -> models.EvaluationRunManifest | None:
    """
    Require the current persisted run manifest to be the exact manifest
    sealed into this result's immutable provenance.

    A manifest that is later replaced and independently rehashed must
    not be allowed to reinterpret historical semantic evidence.
    """

    provenance = result.provenance

    if provenance is None:
        raise ASRSemanticEvidenceIntegrityError(
            "evaluation result provenance is missing"
        )

    payload = provenance.provenance_payload

    if not isinstance(payload, dict):
        raise ASRSemanticEvidenceIntegrityError(
            "evaluation result provenance payload "
            "is invalid"
        )

    bound_manifest = payload.get("run_manifest")

    if not isinstance(bound_manifest, dict):
        raise ASRSemanticEvidenceIntegrityError(
            "evaluation result provenance is missing "
            "run-manifest evidence"
        )

    manifest = db.scalar(
        select(models.EvaluationRunManifest).where(
            models.EvaluationRunManifest.run_id
            == evaluation_run.id
        )
    )

    if manifest is None:
        expected = {
            "status": "legacy_unsealed",
            "schema_version": None,
            "sha256": None,
        }
    else:
        if (
            manifest.run_id != evaluation_run.id
            or manifest.evaluation_type
            != evaluation_run.evaluation_type
            or not verify_evaluation_run_manifest(
                manifest
            )
        ):
            raise ASRSemanticEvidenceIntegrityError(
                "evaluation run manifest integrity "
                "check failed"
            )

        expected = {
            "status": "sealed",
            "schema_version": manifest.schema_version,
            "sha256": manifest.manifest_sha256,
        }

    if bound_manifest != expected:
        raise ASRSemanticEvidenceIntegrityError(
            "evaluation result is not bound to "
            "the current run manifest"
        )

    return manifest


def _build_available_family(
    *,
    records: Sequence[ObservationEvidenceRecord],
    expected_metrics,
    expected_evaluator,
    metric_prefix: str,
    evaluation_run_id: int,
    test_case_id: int,
) -> dict[str, object]:
    """
    Validate and serialize one exact semantic evidence family.

    The family must contain every canonical metric exactly once and
    every record must be bound to the canonical evaluator, run, test
    case, scope, evaluation type, and metric value type.
    """

    expected_by_identity = {
        (metric.key, metric.version): metric
        for metric in expected_metrics
    }

    family_records = [
        record
        for record in records
        if record.metric_key.startswith(metric_prefix)
    ]

    records_by_identity: dict[
        tuple[str, str],
        ObservationEvidenceRecord,
    ] = {}

    for record in family_records:
        identity = (
            record.metric_key,
            record.metric_version,
        )

        expected_metric = expected_by_identity.get(identity)

        if expected_metric is None:
            raise ASRSemanticEvidenceIntegrityError(
                "semantic evidence contains an "
                "unexpected metric identity"
            )

        if identity in records_by_identity:
            raise ASRSemanticEvidenceIntegrityError(
                "semantic evidence contains a "
                "duplicate metric identity"
            )

        if (
            record.evaluator_key
            != expected_evaluator.key
            or record.evaluator_version
            != expected_evaluator.version
            or record.evaluation_type
            != expected_evaluator.evaluation_type
            or record.scope != "test_case"
            or record.evaluation_run_id
            != evaluation_run_id
            or record.test_case_id
            != test_case_id
            or record.value_type
            != expected_metric.value_type
        ):
            raise ASRSemanticEvidenceIntegrityError(
                "semantic evidence identity does not "
                "match the canonical family contract"
            )

        records_by_identity[identity] = record

    if set(records_by_identity) != set(expected_by_identity):
        raise ASRSemanticEvidenceIntegrityError(
            "semantic evidence family is incomplete"
        )

    ordered_records = [
        records_by_identity[
            (metric.key, metric.version)
        ]
        for metric in expected_metrics
    ]

    return {
        "status": "available",
        "observations": [
            _serialize_observation(record)
            for record in ordered_records
        ],
    }


def _build_terminology_family(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    manifest: models.EvaluationRunManifest | None,
    test_case_id: int,
    records: Sequence[ObservationEvidenceRecord],
) -> dict[str, object]:
    """
    Build Critical Terminology evidence according to the run manifest.

    Legacy runs may legitimately have no terminology evidence.
    Schema-v2 unconfigured runs must have none.
    Configured runs must have the complete canonical 11-metric family
    and must still reproduce the exact run-pinned vocabulary profile.
    """

    terminology_records = [
        record
        for record in records
        if record.metric_key.startswith(
            "asr.critical-terminology."
        )
    ]

    if manifest is None:
        if terminology_records:
            raise ASRSemanticEvidenceIntegrityError(
                "legacy run unexpectedly contains "
                "Critical Terminology evidence"
            )

        return {
            "status": "legacy_unavailable",
            "observations": [],
        }

    if not verify_evaluation_run_manifest(manifest):
        raise ASRSemanticEvidenceIntegrityError(
            "evaluation run manifest integrity "
            "check failed"
        )

    if (
        manifest.schema_version
        == LEGACY_EVALUATION_MANIFEST_SCHEMA_VERSION
    ):
        if terminology_records:
            raise ASRSemanticEvidenceIntegrityError(
                "legacy manifest unexpectedly contains "
                "Critical Terminology evidence"
            )

        return {
            "status": "legacy_unavailable",
            "observations": [],
        }

    binding = manifest.manifest_payload[
        "critical_terminology"
    ]
    manifest_status = binding["status"]

    if (
        manifest_status
        == CRITICAL_TERMINOLOGY_MANIFEST_STATUS_NOT_CONFIGURED
    ):
        if terminology_records:
            raise ASRSemanticEvidenceIntegrityError(
                "unconfigured run unexpectedly contains "
                "Critical Terminology evidence"
            )

        return {
            "status": "not_configured",
            "observations": [],
        }

    if (
        manifest_status
        != CRITICAL_TERMINOLOGY_MANIFEST_STATUS_CONFIGURED
    ):
        raise ASRSemanticEvidenceIntegrityError(
            "unsupported Critical Terminology "
            "manifest state"
        )

    try:
        profile = (
            resolve_evaluation_run_critical_terminology_profile(
                db,
                evaluation_run=evaluation_run,
            )
        )
    except CriticalTerminologyVocabularyIntegrityError as exc:
        raise ASRSemanticEvidenceIntegrityError(
            "run-pinned Critical Terminology "
            "profile cannot be verified"
        ) from exc

    if profile is None:
        raise ASRSemanticEvidenceIntegrityError(
            "configured run is missing its "
            "Critical Terminology profile"
        )

    family = _build_available_family(
        records=records,
        expected_metrics=CRITICAL_TERMINOLOGY_METRICS,
        expected_evaluator=(
            CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR
        ),
        metric_prefix="asr.critical-terminology.",
        evaluation_run_id=evaluation_run.id,
        test_case_id=test_case_id,
    )

    vocabulary_observation = next(
        (
            observation
            for observation in family["observations"]
            if observation["metric_key"]
            == CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC.key
        ),
        None,
    )

    if (
        vocabulary_observation is None
        or vocabulary_observation["status"]
        != "success"
        or vocabulary_observation["value"]
        != binding["vocabulary_sha256"]
    ):
        raise ASRSemanticEvidenceIntegrityError(
            "Critical Terminology evidence does not "
            "match the run-pinned vocabulary"
        )

    return family


def build_asr_semantic_evidence_read(
    db: Session,
    *,
    result: models.EvaluationResult,
    evaluation_run: models.EvaluationRun,
) -> dict[str, object]:
    """
    Build read-only semantic ASR evidence from persisted observations.

    This path never executes an evaluator, stages observations, changes
    quality or release state, or commits a transaction.
    """

    if (
        result.id is None
        or evaluation_run.id is None
        or result.run_id != evaluation_run.id
        or evaluation_run.evaluation_type != "asr"
    ):
        raise ASRSemanticEvidenceIntegrityError(
            "evaluation result/run identity is invalid"
        )

    if (
        result.test_case_id is None
        or result.test_case_id < 1
    ):
        raise ASRSemanticEvidenceIntegrityError(
            "evaluation result test-case identity is invalid"
        )

    if result.provenance is None:
        raise ASRSemanticEvidenceIntegrityError(
            "evaluation result provenance is missing"
        )

    if not verify_evaluation_result_observation_binding(
        db,
        result.provenance,
    ):
        raise ASRSemanticEvidenceIntegrityError(
            "evaluation result observation binding "
            "does not verify"
        )

    manifest = _load_result_bound_run_manifest(
        db,
        result=result,
        evaluation_run=evaluation_run,
    )

    try:
        records = (
            load_test_case_observation_evidence_records(
                db,
                evaluation_run_id=evaluation_run.id,
                test_case_id=result.test_case_id,
            )
        )
    except HveeObservationEvidenceError as exc:
        raise ASRSemanticEvidenceIntegrityError(
            "persisted semantic evidence cannot "
            "be reconstructed"
        ) from exc

    critical_number = _build_available_family(
        records=records,
        expected_metrics=CRITICAL_NUMBER_METRICS,
        expected_evaluator=(
            CRITICAL_NUMBER_FIDELITY_EVALUATOR
        ),
        metric_prefix="asr.critical-number.",
        evaluation_run_id=evaluation_run.id,
        test_case_id=result.test_case_id,
    )

    critical_identifier = _build_available_family(
        records=records,
        expected_metrics=CRITICAL_IDENTIFIER_METRICS,
        expected_evaluator=(
            CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR
        ),
        metric_prefix="asr.critical-identifier.",
        evaluation_run_id=evaluation_run.id,
        test_case_id=result.test_case_id,
    )

    critical_terminology = _build_terminology_family(
        db,
        evaluation_run=evaluation_run,
        manifest=manifest,
        test_case_id=result.test_case_id,
        records=records,
    )

    return {
        "result_id": result.id,
        "evaluation_run_id": evaluation_run.id,
        "test_case_id": result.test_case_id,
        "evaluation_type": "asr",
        "critical_number": critical_number,
        "critical_identifier": critical_identifier,
        "critical_terminology": critical_terminology,
    }
