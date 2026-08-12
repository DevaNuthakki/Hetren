from collections.abc import Collection
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models, schemas
from app.asr_semantic_evidence_service import (
    ASRSemanticEvidenceIntegrityError,
    build_asr_semantic_evidence_read,
)
from app.auth.authorization import (
    PRODUCT_READ_ROLES,
    PRODUCT_WRITE_ROLES,
    DatasetAccess,
    DatasetNotAccessibleError,
    DatasetPermissionDeniedError,
    DebugCaseAccess,
    DebugCaseNotAccessibleError,
    DebugCasePermissionDeniedError,
    EvaluationResultAccess,
    EvaluationResultNotAccessibleError,
    EvaluationResultPermissionDeniedError,
    EvaluationRunAccess,
    EvaluationRunNotAccessibleError,
    EvaluationRunPermissionDeniedError,
    OrganizationAccess,
    OrganizationNotAccessibleError,
    OrganizationPermissionDeniedError,
    ProjectAccess,
    ProjectNotAccessibleError,
    ProjectPermissionDeniedError,
    RunComparisonAccess,
    RunComparisonNotAccessibleError,
    RunComparisonPermissionDeniedError,
    TestCaseAccess,
    TestCaseNotAccessibleError,
    TestCasePermissionDeniedError,
    authorize_dataset,
    authorize_debug_case,
    authorize_evaluation_result,
    authorize_evaluation_run,
    authorize_organization,
    authorize_project,
    authorize_run_comparison,
    authorize_test_case,
    list_accessible_projects,
)
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.critical_terminology_vocabulary_service import (
    CriticalTerminologyVocabularyIntegrityError,
    CriticalTerminologyVocabularyValidationError,
    get_critical_terminology_vocabulary_version,
    get_current_critical_terminology_vocabulary_version,
    list_critical_terminology_vocabulary_versions,
    stage_critical_terminology_vocabulary_version,
)
from app.database import check_database_connection, get_db
from app.evaluation_artifacts import (
    SUPPORTED_ASR_AUDIO_MEDIA_TYPES,
    EvaluationInputArtifactSealError,
    calculate_content_sha256,
    ensure_evaluation_input_artifact_seal,
    resolve_verified_sealed_artifact_path,
)
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
)
from app.evaluation_service import (
    build_error_summary,
    build_quality_label,
    persist_evaluation_result,
)
from app.release_safety import (
    ReleasePolicyThresholds,
    evaluate_release_safety,
)
from app.speech import TranscriptionError, get_asr_provider
from app.upload_io import (
    UploadTooLargeError,
    read_upload_bytes_limited,
    write_upload_file_limited,
)

router = APIRouter()


def _authorize_organization_for_request(
    db: Session,
    *,
    current_user: models.User,
    organization_id: int,
    required_roles: Collection[str],
) -> OrganizationAccess:
    try:
        return authorize_organization(
            db,
            user_id=current_user.id,
            organization_id=organization_id,
            required_roles=required_roles,
        )
    except OrganizationNotAccessibleError as exc:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        ) from exc
    except OrganizationPermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Organization permission denied",
        ) from exc


def _authorize_project_for_request(
    db: Session,
    *,
    current_user: models.User,
    project_id: int,
    required_roles: Collection[str],
) -> ProjectAccess:
    try:
        return authorize_project(
            db,
            user_id=current_user.id,
            project_id=project_id,
            required_roles=required_roles,
        )
    except ProjectNotAccessibleError as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ProjectPermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Project permission denied",
        ) from exc


def _authorize_dataset_for_request(
    db: Session,
    *,
    current_user: models.User,
    dataset_id: int,
    required_roles: Collection[str],
) -> DatasetAccess:
    try:
        return authorize_dataset(
            db,
            user_id=current_user.id,
            dataset_id=dataset_id,
            required_roles=required_roles,
        )
    except DatasetNotAccessibleError as exc:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found",
        ) from exc
    except DatasetPermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Dataset permission denied",
        ) from exc


def _authorize_test_case_for_request(
    db: Session,
    *,
    current_user: models.User,
    test_case_id: int,
    required_roles: Collection[str],
) -> TestCaseAccess:
    try:
        return authorize_test_case(
            db,
            user_id=current_user.id,
            test_case_id=test_case_id,
            required_roles=required_roles,
        )
    except TestCaseNotAccessibleError as exc:
        raise HTTPException(
            status_code=404,
            detail="Test case not found",
        ) from exc
    except TestCasePermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Test case permission denied",
        ) from exc


def _authorize_evaluation_run_for_request(
    db: Session,
    *,
    current_user: models.User,
    run_id: int,
    required_roles: Collection[str],
) -> EvaluationRunAccess:
    try:
        return authorize_evaluation_run(
            db,
            user_id=current_user.id,
            run_id=run_id,
            required_roles=required_roles,
        )
    except EvaluationRunNotAccessibleError as exc:
        raise HTTPException(
            status_code=404,
            detail="Evaluation run not found",
        ) from exc
    except EvaluationRunPermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Evaluation run permission denied",
        ) from exc


def _authorize_evaluation_result_for_request(
    db: Session,
    *,
    current_user: models.User,
    result_id: int,
    required_roles: Collection[str],
) -> EvaluationResultAccess:
    try:
        return authorize_evaluation_result(
            db,
            user_id=current_user.id,
            result_id=result_id,
            required_roles=required_roles,
        )
    except EvaluationResultNotAccessibleError as exc:
        raise HTTPException(
            status_code=404,
            detail="Evaluation result not found",
        ) from exc
    except EvaluationResultPermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Evaluation result permission denied",
        ) from exc


def _authorize_run_comparison_for_request(
    db: Session,
    *,
    current_user: models.User,
    comparison_id: int,
    required_roles: Collection[str],
) -> RunComparisonAccess:
    try:
        return authorize_run_comparison(
            db,
            user_id=current_user.id,
            comparison_id=comparison_id,
            required_roles=required_roles,
        )
    except RunComparisonNotAccessibleError as exc:
        raise HTTPException(
            status_code=404,
            detail="Run comparison not found",
        ) from exc
    except RunComparisonPermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Run comparison permission denied",
        ) from exc


def _authorize_debug_case_for_request(
    db: Session,
    *,
    current_user: models.User,
    debug_case_id: int,
    required_roles: Collection[str],
) -> DebugCaseAccess:
    try:
        return authorize_debug_case(
            db,
            user_id=current_user.id,
            debug_case_id=debug_case_id,
            required_roles=required_roles,
        )
    except DebugCaseNotAccessibleError as exc:
        raise HTTPException(
            status_code=404,
            detail="Debug case not found",
        ) from exc
    except DebugCasePermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Debug case permission denied",
        ) from exc


def build_comparison_status(wer_delta: float, cer_delta: float) -> str:
    if wer_delta >= 0.05 or cer_delta >= 0.03:
        return "regression"

    if wer_delta <= -0.05 or cer_delta <= -0.03:
        return "improvement"

    return "no_significant_change"


def build_comparison_summary(
    baseline_average_wer: float,
    current_average_wer: float,
    wer_delta: float,
    baseline_average_cer: float,
    current_average_cer: float,
    cer_delta: float,
    comparison_status: str,
) -> str:
    if comparison_status == "regression":
        opening = "Regression detected."
    elif comparison_status == "improvement":
        opening = "Improvement detected."
    else:
        opening = "No significant regression detected."

    return (
        f"{opening} "
        f"Baseline WER={baseline_average_wer:.3f}, current WER={current_average_wer:.3f}, "
        f"WER delta={wer_delta:.3f}. "
        f"Baseline CER={baseline_average_cer:.3f}, current CER={current_average_cer:.3f}, "
        f"CER delta={cer_delta:.3f}."
    )


def build_debug_case_severity(comparison_status: str, wer_delta: float) -> str:
    if comparison_status == "regression" and wer_delta >= 0.20:
        return "high"

    if comparison_status == "regression":
        return "medium"

    return "low"


def calculate_average_metric(results: list[models.EvaluationResult], metric_name: str) -> float:
    metric_values = [
        getattr(result, metric_name)
        for result in results
        if getattr(result, metric_name) is not None
    ]

    if not metric_values:
        raise HTTPException(
            status_code=400,
            detail=f"No {metric_name.upper()} values found for this run",
        )

    return sum(metric_values) / len(metric_values)


def get_optional_by_id(db: Session, model, object_id: int | None):
    if object_id is None:
        return None

    return db.query(model).filter(model.id == object_id).first()




def build_release_policy_thresholds(
    policy: models.ReleasePolicy,
) -> ReleasePolicyThresholds:
    return ReleasePolicyThresholds(
        warn_current_wer=policy.warn_current_wer,
        fail_current_wer=policy.fail_current_wer,
        warn_current_cer=policy.warn_current_cer,
        fail_current_cer=policy.fail_current_cer,
        warn_wer_delta=policy.warn_wer_delta,
        fail_wer_delta=policy.fail_wer_delta,
        warn_cer_delta=policy.warn_cer_delta,
        fail_cer_delta=policy.fail_cer_delta,
    )


def build_release_policy_snapshot(
    policy: models.ReleasePolicy,
) -> dict[str, object]:
    return {
        "policy_id": policy.id,
        "name": policy.name,
        "version": policy.version,
        **asdict(build_release_policy_thresholds(policy)),
    }


def find_active_release_policy(
    db: Session,
    project_id: int,
) -> models.ReleasePolicy | None:
    return (
        db.query(models.ReleasePolicy)
        .filter(models.ReleasePolicy.project_id == project_id)
        .filter(models.ReleasePolicy.is_active.is_(True))
        .order_by(
            models.ReleasePolicy.version.desc(),
            models.ReleasePolicy.created_at.desc(),
        )
        .first()
    )


def create_default_release_policy(
    db: Session,
    project_id: int,
) -> models.ReleasePolicy:
    default_thresholds = ReleasePolicyThresholds()

    db_policy = models.ReleasePolicy(
        project_id=project_id,
        name="Default release policy",
        version=1,
        is_active=True,
        **asdict(default_thresholds),
    )

    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)

    return db_policy

def find_worst_debug_result_pair(
    db: Session,
    baseline_run_id: int,
    current_run_id: int,
) -> tuple[
    models.EvaluationResult | None,
    models.EvaluationResult | None,
    models.TestCase | None,
]:
    baseline_results = (
        db.query(models.EvaluationResult)
        .filter(models.EvaluationResult.run_id == baseline_run_id)
        .all()
    )
    current_results = (
        db.query(models.EvaluationResult)
        .filter(models.EvaluationResult.run_id == current_run_id)
        .all()
    )

    if not current_results:
        return None, None, None

    baseline_by_test_case_id = {
        result.test_case_id: result for result in baseline_results
    }

    def result_priority(current_result: models.EvaluationResult) -> tuple[float, float, float]:
        baseline_result = baseline_by_test_case_id.get(current_result.test_case_id)

        current_wer = current_result.wer if current_result.wer is not None else -1.0
        current_cer = current_result.cer if current_result.cer is not None else -1.0

        if baseline_result and baseline_result.wer is not None and current_result.wer is not None:
            wer_delta = current_result.wer - baseline_result.wer
        else:
            wer_delta = current_wer

        return wer_delta, current_wer, current_cer

    current_result = max(current_results, key=result_priority)
    baseline_result = baseline_by_test_case_id.get(current_result.test_case_id)
    test_case = (
        db.query(models.TestCase)
        .filter(models.TestCase.id == current_result.test_case_id)
        .first()
    )

    return baseline_result, current_result, test_case


def build_debug_case_ai_suggestion(
    test_case: models.TestCase | None,
    current_result: models.EvaluationResult | None,
) -> str:
    if current_result is None:
        return (
            "Review the linked regression comparison and identify the failing sample "
            "before debugging model or transcript quality."
        )

    test_case_label = test_case.title if test_case is not None else "the selected test case"
    wer_text = f"{current_result.wer:.3f}" if current_result.wer is not None else "unknown"
    cer_text = f"{current_result.cer:.3f}" if current_result.cer is not None else "unknown"

    return (
        f"Start with {test_case_label}. Current result WER={wer_text}, CER={cer_text}. "
        "Review the transcript difference, confirm whether the reference transcript is correct, "
        "then check whether the model output changed because of audio quality, decoding, or model behavior."
    )


def tokenize_transcript(transcript: str) -> list[str]:
    return transcript.strip().split()


def build_structured_transcript_diff(
    reference_text: str,
    generated_text: str,
    result_id: int,
    test_case_id: int,
    wer_score: float | None,
    cer_score: float | None,
) -> dict:
    reference_words = tokenize_transcript(reference_text)
    generated_words = tokenize_transcript(generated_text)

    row_count = len(reference_words) + 1
    column_count = len(generated_words) + 1

    costs = [[0 for _ in range(column_count)] for _ in range(row_count)]

    for row in range(row_count):
        costs[row][0] = row

    for column in range(column_count):
        costs[0][column] = column

    for row in range(1, row_count):
        for column in range(1, column_count):
            if reference_words[row - 1].lower() == generated_words[column - 1].lower():
                substitution_cost = 0
            else:
                substitution_cost = 1

            costs[row][column] = min(
                costs[row - 1][column] + 1,
                costs[row][column - 1] + 1,
                costs[row - 1][column - 1] + substitution_cost,
            )

    tokens = []
    substitutions = 0
    insertions = 0
    deletions = 0
    matches = 0

    row = len(reference_words)
    column = len(generated_words)

    while row > 0 or column > 0:
        if (
            row > 0
            and column > 0
            and reference_words[row - 1].lower() == generated_words[column - 1].lower()
            and costs[row][column] == costs[row - 1][column - 1]
        ):
            word = reference_words[row - 1]
            tokens.append(
                {
                    "operation": "match",
                    "reference_word": word,
                    "generated_word": generated_words[column - 1],
                    "display_text": word,
                }
            )
            matches += 1
            row -= 1
            column -= 1
            continue

        if (
            row > 0
            and column > 0
            and costs[row][column] == costs[row - 1][column - 1] + 1
        ):
            reference_word = reference_words[row - 1]
            generated_word = generated_words[column - 1]
            tokens.append(
                {
                    "operation": "substitution",
                    "reference_word": reference_word,
                    "generated_word": generated_word,
                    "display_text": f"{reference_word} → {generated_word}",
                }
            )
            substitutions += 1
            row -= 1
            column -= 1
            continue

        if column > 0 and costs[row][column] == costs[row][column - 1] + 1:
            generated_word = generated_words[column - 1]
            tokens.append(
                {
                    "operation": "insertion",
                    "reference_word": None,
                    "generated_word": generated_word,
                    "display_text": generated_word,
                }
            )
            insertions += 1
            column -= 1
            continue

        if row > 0:
            reference_word = reference_words[row - 1]
            tokens.append(
                {
                    "operation": "deletion",
                    "reference_word": reference_word,
                    "generated_word": None,
                    "display_text": reference_word,
                }
            )
            deletions += 1
            row -= 1

    tokens.reverse()

    return {
        "result_id": result_id,
        "test_case_id": test_case_id,
        "reference_transcript": reference_text,
        "generated_transcript": generated_text,
        "wer": wer_score,
        "cer": cer_score,
        "substitutions": substitutions,
        "insertions": insertions,
        "deletions": deletions,
        "matches": matches,
        "tokens": tokens,
    }


def validate_text_file_extension(file_name: str, label: str) -> None:
    extension = Path(file_name).suffix.lower()

    if extension != ".txt":
        raise HTTPException(
            status_code=400,
            detail=f"{label} transcript must be a .txt file",
        )


def decode_transcript_file(file_content: bytes, label: str) -> str:
    if not file_content:
        raise HTTPException(
            status_code=400,
            detail=f"{label} transcript file is empty",
        )

    try:
        transcript_text = file_content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail=f"{label} transcript must be valid UTF-8 text",
        )

    transcript_text = transcript_text.strip()

    if not transcript_text:
        raise HTTPException(
            status_code=400,
            detail=f"{label} transcript text is empty",
        )

    return transcript_text


@router.get("/health")
def health_check():
    """Backward-compatible API health endpoint."""
    return {
        "status": "ok",
        "service": "hetren-api",
    }


@router.get("/health/live")
def liveness_check():
    """Confirm that the FastAPI process is running."""
    return {
        "status": "ok",
        "service": "hetren-api",
        "check": "liveness",
    }


@router.get("/health/ready")
def readiness_check():
    """Confirm that the API can communicate with PostgreSQL."""
    try:
        check_database_connection()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable",
        ) from exc

    return {
        "status": "ready",
        "service": "hetren-api",
        "database": "reachable",
    }


@router.post("/projects", response_model=schemas.ProjectRead)
def create_project(
    project: schemas.ProjectCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    organization_access = _authorize_organization_for_request(
        db,
        current_user=current_user,
        organization_id=project.organization_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    db_project = models.Project(
        organization_id=organization_access.organization.id,
        name=project.name,
        description=project.description,
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/projects", response_model=list[schemas.ProjectRead])
def list_projects(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_accessible_projects(
        db,
        user_id=current_user.id,
    )


@router.get("/projects/{project_id}", response_model=schemas.ProjectRead)
def get_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return access.project


def _critical_terminology_vocabulary_read(
    vocabulary: (
        models.CriticalTerminologyVocabularyVersion
    ),
) -> schemas.CriticalTerminologyVocabularyRead:
    """Build the public API representation of a vocabulary revision."""

    return schemas.CriticalTerminologyVocabularyRead(
        id=vocabulary.id,
        project_id=vocabulary.project_id,
        revision=vocabulary.revision,
        profile_schema_version=(
            vocabulary.profile_schema_version
        ),
        profile_key=vocabulary.profile_key,
        profile_version=(
            vocabulary.profile_version
        ),
        language=vocabulary.language,
        locale=vocabulary.locale,
        terms=vocabulary.terms_snapshot,
        vocabulary_sha256=(
            vocabulary.vocabulary_sha256
        ),
        created_by_user_id=(
            vocabulary.created_by_user_id
        ),
        created_at=vocabulary.created_at,
    )


@router.post(
    "/projects/{project_id}/critical-terminology-vocabularies",
    response_model=(
        schemas.CriticalTerminologyVocabularyRead
    ),
    status_code=201,
)
def create_critical_terminology_vocabulary(
    project_id: int,
    vocabulary: (
        schemas.CriticalTerminologyVocabularyCreate
    ),
    current_user: models.User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    access = _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    try:
        created = (
            stage_critical_terminology_vocabulary_version(
                db,
                project_id=access.project.id,
                created_by_user_id=(
                    current_user.id
                ),
                terms=[
                    term.model_dump()
                    for term in vocabulary.terms
                ],
            )
        )
    except CriticalTerminologyVocabularyValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except CriticalTerminologyVocabularyIntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Critical terminology vocabulary "
                "integrity check failed"
            ),
        ) from exc

    db.commit()
    db.refresh(created)

    return _critical_terminology_vocabulary_read(
        created
    )


@router.get(
    "/projects/{project_id}/critical-terminology-vocabularies",
    response_model=list[
        schemas.CriticalTerminologyVocabularyRead
    ],
)
def list_critical_terminology_vocabularies(
    project_id: int,
    current_user: models.User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    access = _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    try:
        vocabularies = (
            list_critical_terminology_vocabulary_versions(
                db,
                project_id=access.project.id,
            )
        )
    except CriticalTerminologyVocabularyIntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Critical terminology vocabulary "
                "integrity check failed"
            ),
        ) from exc

    return [
        _critical_terminology_vocabulary_read(
            vocabulary
        )
        for vocabulary in vocabularies
    ]


@router.get(
    "/projects/{project_id}/critical-terminology-vocabularies/current",
    response_model=(
        schemas.CriticalTerminologyVocabularyRead
    ),
)
def get_current_critical_terminology_vocabulary(
    project_id: int,
    current_user: models.User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    access = _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    try:
        vocabulary = (
            get_current_critical_terminology_vocabulary_version(
                db,
                project_id=access.project.id,
            )
        )
    except CriticalTerminologyVocabularyIntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Critical terminology vocabulary "
                "integrity check failed"
            ),
        ) from exc

    if vocabulary is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Critical terminology vocabulary "
                "is not configured"
            ),
        )

    return _critical_terminology_vocabulary_read(
        vocabulary
    )


@router.get(
    "/projects/{project_id}/critical-terminology-vocabularies/{revision}",
    response_model=(
        schemas.CriticalTerminologyVocabularyRead
    ),
)
def get_critical_terminology_vocabulary(
    project_id: int,
    revision: int,
    current_user: models.User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    access = _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    if revision <= 0:
        raise HTTPException(
            status_code=422,
            detail=(
                "Critical terminology vocabulary "
                "revision must be positive"
            ),
        )

    try:
        vocabulary = (
            get_critical_terminology_vocabulary_version(
                db,
                project_id=access.project.id,
                revision=revision,
            )
        )
    except CriticalTerminologyVocabularyIntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Critical terminology vocabulary "
                "integrity check failed"
            ),
        ) from exc

    if vocabulary is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Critical terminology vocabulary "
                "revision not found"
            ),
        )

    return _critical_terminology_vocabulary_read(
        vocabulary
    )


@router.get(
    "/projects/{project_id}/workflow-summary",
    response_model=schemas.ProjectWorkflowSummaryRead,
)
def get_project_workflow_summary(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    dataset_count = (
        db.query(models.Dataset)
        .filter(models.Dataset.project_id == project_id)
        .count()
    )

    test_case_count = (
        db.query(models.TestCase)
        .join(models.Dataset)
        .filter(models.Dataset.project_id == project_id)
        .count()
    )

    run_query = db.query(models.EvaluationRun).filter(
        models.EvaluationRun.project_id == project_id
    )

    run_count = run_query.count()
    evaluated_run_count = run_query.filter(
        models.EvaluationRun.status == "evaluated"
    ).count()

    latest_run = (
        db.query(models.EvaluationRun)
        .filter(models.EvaluationRun.project_id == project_id)
        .order_by(models.EvaluationRun.created_at.desc())
        .first()
    )

    result_count = (
        db.query(models.EvaluationResult)
        .join(models.EvaluationRun)
        .filter(models.EvaluationRun.project_id == project_id)
        .count()
    )

    project_run_ids = [
        run.id
        for run in db.query(models.EvaluationRun.id)
        .filter(models.EvaluationRun.project_id == project_id)
        .all()
    ]

    if project_run_ids:
        comparison_query = (
            db.query(models.RunComparison)
            .filter(models.RunComparison.baseline_run_id.in_(project_run_ids))
            .filter(models.RunComparison.current_run_id.in_(project_run_ids))
        )

        comparison_count = comparison_query.count()
        latest_comparison = comparison_query.order_by(
            models.RunComparison.created_at.desc()
        ).first()
    else:
        comparison_count = 0
        latest_comparison = None

    debug_case_query = db.query(models.DebugCase).filter(
        models.DebugCase.project_id == project_id
    )

    debug_case_count = debug_case_query.count()
    open_debug_case_count = debug_case_query.filter(
        models.DebugCase.status != "closed"
    ).count()

    return {
        "project_id": project_id,
        "dataset_count": dataset_count,
        "test_case_count": test_case_count,
        "run_count": run_count,
        "evaluated_run_count": evaluated_run_count,
        "result_count": result_count,
        "comparison_count": comparison_count,
        "debug_case_count": debug_case_count,
        "open_debug_case_count": open_debug_case_count,
        "latest_run": latest_run,
        "latest_comparison": latest_comparison,
    }


@router.post(
    "/projects/{project_id}/datasets",
    response_model=schemas.DatasetRead,
)
def create_dataset(
    project_id: int,
    dataset: schemas.DatasetCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    db_dataset = models.Dataset(
        project_id=access.project.id,
        name=dataset.name,
        description=dataset.description,
    )

    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)

    return db_dataset


@router.get(
    "/projects/{project_id}/datasets",
    response_model=list[schemas.DatasetRead],
)
def list_project_datasets(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return (
        db.query(models.Dataset)
        .filter(models.Dataset.project_id == project_id)
        .order_by(models.Dataset.created_at.desc())
        .all()
    )


@router.get(
    "/datasets/{dataset_id}",
    response_model=schemas.DatasetRead,
)
def get_dataset(
    dataset_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_dataset_for_request(
        db,
        current_user=current_user,
        dataset_id=dataset_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return access.dataset


@router.post(
    "/datasets/{dataset_id}/test-cases",
    response_model=schemas.TestCaseRead,
)
async def create_test_case(
    dataset_id: int,
    title: str = Form(...),
    audio_file: UploadFile = File(...),
    reference_file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_dataset_for_request(
        db,
        current_user=current_user,
        dataset_id=dataset_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    if not title.strip():
        raise HTTPException(status_code=400, detail="Test case title is required")

    if not audio_file.filename:
        raise HTTPException(status_code=400, detail="Audio file is required")

    if not reference_file.filename:
        raise HTTPException(status_code=400, detail="Reference transcript file is required")

    allowed_audio_extensions = {".wav", ".mp3", ".m4a"}
    audio_file_name = Path(audio_file.filename).name
    reference_file_name = Path(reference_file.filename).name

    audio_extension = Path(audio_file_name).suffix.lower()

    if audio_extension not in allowed_audio_extensions:
        raise HTTPException(
            status_code=400,
            detail="Invalid audio file type. Allowed types: .wav, .mp3, .m4a",
        )

    validate_text_file_extension(reference_file_name, "Reference")

    settings = get_settings()

    try:
        reference_content = await read_upload_bytes_limited(
            reference_file,
            max_bytes=settings.upload_max_transcript_bytes,
            label="Reference transcript",
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc

    reference_text = decode_transcript_file(
        reference_content,
        "Reference",
    )

    test_case_upload_dir = (
        Path("uploads")
        / "datasets"
        / str(dataset_id)
        / "test-cases"
    )
    audio_dir = test_case_upload_dir / "audio"
    reference_dir = test_case_upload_dir / "reference"

    audio_path = audio_dir / audio_file_name
    reference_path = reference_dir / reference_file_name

    try:
        audio_byte_length = (
            await write_upload_file_limited(
                audio_file,
                audio_path,
                max_bytes=settings.upload_max_audio_bytes,
                label="Audio file",
            )
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc

    if audio_byte_length == 0:
        audio_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="Audio file is empty",
        )

    try:
        reference_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        reference_path.write_text(
            reference_text,
            encoding="utf-8",
        )
    except Exception:
        audio_path.unlink(missing_ok=True)
        reference_path.unlink(missing_ok=True)
        raise

    db_test_case = models.TestCase(
        dataset_id=dataset_id,
        title=title.strip(),
        audio_file_path=str(audio_path),
        reference_file_path=str(reference_path),
        reference_transcript=reference_text,
    )

    db.add(db_test_case)

    try:
        db.commit()
    except Exception:
        db.rollback()
        audio_path.unlink(missing_ok=True)
        reference_path.unlink(missing_ok=True)
        raise

    db.refresh(db_test_case)

    return db_test_case


@router.get(
    "/datasets/{dataset_id}/test-cases",
    response_model=list[schemas.TestCaseRead],
)
def list_dataset_test_cases(
    dataset_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_dataset_for_request(
        db,
        current_user=current_user,
        dataset_id=dataset_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return (
        db.query(models.TestCase)
        .filter(models.TestCase.dataset_id == dataset_id)
        .order_by(models.TestCase.created_at.desc())
        .all()
    )


@router.get(
    "/test-cases/{test_case_id}",
    response_model=schemas.TestCaseRead,
)
def get_test_case(
    test_case_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_test_case_for_request(
        db,
        current_user=current_user,
        test_case_id=test_case_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return access.test_case


@router.post(
    "/projects/{project_id}/runs",
    response_model=schemas.EvaluationRunRead,
)
def create_evaluation_run(
    project_id: int,
    run: schemas.EvaluationRunCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    db_run = stage_evaluation_run_with_manifest(
        db,
        project_id=access.project.id,
        run_name=run.run_name,
        evaluation_type=run.evaluation_type,
        model_name=run.model_name or "not_configured",
        status="created",
    )

    db.commit()
    db.refresh(db_run)

    return db_run


@router.get(
    "/projects/{project_id}/runs",
    response_model=list[schemas.EvaluationRunRead],
)
def list_project_runs(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return (
        db.query(models.EvaluationRun)
        .filter(models.EvaluationRun.project_id == project_id)
        .order_by(models.EvaluationRun.created_at.desc())
        .all()
    )


@router.get(
    "/runs/{run_id}",
    response_model=schemas.EvaluationRunRead,
)
def get_evaluation_run(
    run_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_evaluation_run_for_request(
        db,
        current_user=current_user,
        run_id=run_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return access.run


@router.post(
    "/runs/{run_id}/test-cases/{test_case_id}/evaluate",
    response_model=schemas.EvaluationResultRead,
)
async def evaluate_test_case_for_run(
    run_id: int,
    test_case_id: int,
    generated_file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run_access = _authorize_evaluation_run_for_request(
        db,
        current_user=current_user,
        run_id=run_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )
    test_case_access = _authorize_test_case_for_request(
        db,
        current_user=current_user,
        test_case_id=test_case_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    if test_case_access.project.id != run_access.project.id:
        raise HTTPException(
            status_code=400,
            detail="Test case dataset does not belong to the same project as this run",
        )

    db_run = run_access.run
    db_test_case = test_case_access.test_case

    if not generated_file.filename:
        raise HTTPException(status_code=400, detail="Generated transcript file is required")

    generated_file_name = Path(generated_file.filename).name
    validate_text_file_extension(generated_file_name, "Generated")

    settings = get_settings()

    try:
        generated_content = await read_upload_bytes_limited(
            generated_file,
            max_bytes=settings.upload_max_transcript_bytes,
            label="Generated transcript",
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc

    generated_text = decode_transcript_file(
        generated_content,
        "Generated",
    )

    result_upload_dir = (
        Path("uploads")
        / "runs"
        / str(run_id)
        / "results"
        / str(test_case_id)
    )
    generated_dir = result_upload_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    generated_path = generated_dir / generated_file_name

    generated_path.write_text(
        generated_text,
        encoding="utf-8",
    )

    try:
        return persist_evaluation_result(
            db=db,
            db_run=db_run,
            db_test_case=db_test_case,
            generated_text=generated_text,
            generated_file_path=str(generated_path),
            execution_mode="uploaded_transcript",
        )
    except Exception:
        generated_path.unlink(missing_ok=True)
        raise


@router.post(
    "/runs/{run_id}/test-cases/{test_case_id}/transcribe-and-evaluate",
    response_model=schemas.TranscribeAndEvaluateRead,
)
def transcribe_and_evaluate_test_case_for_run(
    run_id: int,
    test_case_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run_access = _authorize_evaluation_run_for_request(
        db,
        current_user=current_user,
        run_id=run_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )
    test_case_access = _authorize_test_case_for_request(
        db,
        current_user=current_user,
        test_case_id=test_case_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    if test_case_access.project.id != run_access.project.id:
        raise HTTPException(
            status_code=400,
            detail="Test case dataset does not belong to the same project as this run",
        )

    db_run = run_access.run
    db_test_case = test_case_access.test_case

    if not db_test_case.audio_file_path:
        raise HTTPException(
            status_code=400,
            detail="Test case does not have an audio file path",
        )

    uploads_root = Path("uploads")
    artifact_storage_root = (
        uploads_root / "evaluation-inputs"
    )
    source_audio_path = Path(
        db_test_case.audio_file_path
    )

    media_type = (
        SUPPORTED_ASR_AUDIO_MEDIA_TYPES.get(
            source_audio_path.suffix.lower()
        )
    )

    if media_type is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Test case audio type is unsupported."
            ),
        )

    # Preserve execution inputs before committing the
    # artifact seal. SQLAlchemy may expire ORM state on
    # commit, and provider inference must not hold the
    # run-row lock used during seal creation.
    requested_model = db_run.model_name

    try:
        input_artifact_seal = (
            ensure_evaluation_input_artifact_seal(
                db,
                evaluation_run=db_run,
                test_case=db_test_case,
                source_path=source_audio_path,
                source_root=uploads_root,
                storage_root=(
                    artifact_storage_root
                ),
                media_type=media_type,
            )
        )

        sealed_audio_path = (
            resolve_verified_sealed_artifact_path(
                input_artifact_seal,
                storage_root=(
                    artifact_storage_root
                ),
                expected_run_manifest_sha256=(
                    db_run.manifest.manifest_sha256
                ),
            )
        )

        expected_content_sha256 = (
            input_artifact_seal.content_sha256
        )
        expected_byte_length = (
            input_artifact_seal.byte_length
        )

        # Persist the exact selected input and release
        # the database lock before provider inference.
        db.commit()

        # Verify again immediately before execution so
        # filesystem tampering after the commit fails
        # closed instead of reaching the provider.
        (
            observed_content_sha256,
            observed_byte_length,
        ) = calculate_content_sha256(
            sealed_audio_path
        )

        if (
            observed_content_sha256
            != expected_content_sha256
            or observed_byte_length
            != expected_byte_length
        ):
            raise EvaluationInputArtifactSealError(
                "Sealed evaluation input changed "
                "before execution."
            )

    except (
        EvaluationInputArtifactSealError,
        OSError,
        RuntimeError,
    ) as error:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=(
                "Evaluation input audio is invalid "
                "or unavailable."
            ),
        ) from error

    try:
        asr_provider = get_asr_provider()
        transcription = asr_provider.transcribe(
            audio_path=sealed_audio_path,
            model_name=requested_model,
        )
    except TranscriptionError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    result_upload_dir = Path("uploads") / "runs" / str(run_id) / "results" / str(test_case_id)
    generated_dir = result_upload_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    generated_path = generated_dir / "generated-by-asr.txt"
    generated_path.write_text(transcription.transcript, encoding="utf-8")

    db_result = persist_evaluation_result(
        db=db,
        db_run=db_run,
        db_test_case=db_test_case,
        generated_text=transcription.transcript,
        generated_file_path=str(generated_path),
        execution_mode="server_asr",
        server_observed={
            "provider": transcription.provider,
            "model_name": transcription.model_name,
            "execution_config": {
                "provider": transcription.provider,
                "model_name": transcription.model_name,
                "device": transcription.device,
                "compute_type": (
                    transcription.compute_type
                ),
            },
        },
        input_artifact_seal=(
            input_artifact_seal
        ),
    )

    return {
        "result": db_result,
        "provider": transcription.provider,
        "model_name": transcription.model_name,
        "generated_transcript": transcription.transcript,
    }


@router.get(
    "/runs/{run_id}/results",
    response_model=list[schemas.EvaluationResultRead],
)
def list_run_results(
    run_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_evaluation_run_for_request(
        db,
        current_user=current_user,
        run_id=run_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return (
        db.query(models.EvaluationResult)
        .filter(models.EvaluationResult.run_id == run_id)
        .order_by(models.EvaluationResult.created_at.desc())
        .all()
    )


@router.get(
    "/results/{result_id}",
    response_model=schemas.EvaluationResultRead,
)
def get_evaluation_result(
    result_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_evaluation_result_for_request(
        db,
        current_user=current_user,
        result_id=result_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return access.result


@router.get(
    "/results/{result_id}/semantic-evidence",
    response_model=schemas.ASRSemanticEvidenceRead,
)
def get_result_semantic_evidence(
    result_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_evaluation_result_for_request(
        db,
        current_user=current_user,
        result_id=result_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    try:
        return build_asr_semantic_evidence_read(
            db,
            result=access.result,
            evaluation_run=access.run,
        )
    except ASRSemanticEvidenceIntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Semantic evidence integrity "
                "check failed"
            ),
        ) from exc


@router.get(
    "/results/{result_id}/transcript-diff",
    response_model=schemas.TranscriptDiffRead,
)
def get_result_transcript_diff(
    result_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_evaluation_result_for_request(
        db,
        current_user=current_user,
        result_id=result_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return build_structured_transcript_diff(
        reference_text=access.test_case.reference_transcript,
        generated_text=access.result.generated_transcript,
        result_id=access.result.id,
        test_case_id=access.result.test_case_id,
        wer_score=access.result.wer,
        cer_score=access.result.cer,
    )


@router.post(
    "/runs/compare",
    response_model=schemas.RunComparisonRead,
)
def compare_runs(
    comparison: schemas.RunComparisonCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    baseline_access = _authorize_evaluation_run_for_request(
        db,
        current_user=current_user,
        run_id=comparison.baseline_run_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )
    current_access = _authorize_evaluation_run_for_request(
        db,
        current_user=current_user,
        run_id=comparison.current_run_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    baseline_run = baseline_access.run
    current_run = current_access.run

    if baseline_access.project.id != current_access.project.id:
        raise HTTPException(
            status_code=400,
            detail="Runs must belong to the same project",
        )

    baseline_results = (
        db.query(models.EvaluationResult)
        .filter(models.EvaluationResult.run_id == baseline_run.id)
        .all()
    )
    current_results = (
        db.query(models.EvaluationResult)
        .filter(models.EvaluationResult.run_id == current_run.id)
        .all()
    )

    if not baseline_results:
        raise HTTPException(
            status_code=400,
            detail="Baseline run has no evaluation results",
        )

    if not current_results:
        raise HTTPException(
            status_code=400,
            detail="Current run has no evaluation results",
        )

    baseline_average_wer = calculate_average_metric(baseline_results, "wer")
    current_average_wer = calculate_average_metric(current_results, "wer")
    wer_delta = current_average_wer - baseline_average_wer

    baseline_average_cer = calculate_average_metric(baseline_results, "cer")
    current_average_cer = calculate_average_metric(current_results, "cer")
    cer_delta = current_average_cer - baseline_average_cer

    comparison_status = build_comparison_status(
        wer_delta=wer_delta,
        cer_delta=cer_delta,
    )

    summary = build_comparison_summary(
        baseline_average_wer=baseline_average_wer,
        current_average_wer=current_average_wer,
        wer_delta=wer_delta,
        baseline_average_cer=baseline_average_cer,
        current_average_cer=current_average_cer,
        cer_delta=cer_delta,
        comparison_status=comparison_status,
    )

    db_comparison = models.RunComparison(
        baseline_run_id=baseline_run.id,
        current_run_id=current_run.id,
        baseline_average_wer=baseline_average_wer,
        current_average_wer=current_average_wer,
        wer_delta=wer_delta,
        baseline_average_cer=baseline_average_cer,
        current_average_cer=current_average_cer,
        cer_delta=cer_delta,
        comparison_status=comparison_status,
        summary=summary,
    )

    db.add(db_comparison)
    db.commit()
    db.refresh(db_comparison)

    return db_comparison


@router.get(
    "/comparisons/{comparison_id}",
    response_model=schemas.RunComparisonRead,
)
def get_run_comparison(
    comparison_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_run_comparison_for_request(
        db,
        current_user=current_user,
        comparison_id=comparison_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return access.comparison


@router.get(
    "/projects/{project_id}/comparisons",
    response_model=list[schemas.RunComparisonRead],
)
def list_project_comparisons(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    project_run_ids = [
        run.id
        for run in db.query(models.EvaluationRun)
        .filter(models.EvaluationRun.project_id == project_id)
        .all()
    ]

    if not project_run_ids:
        return []

    return (
        db.query(models.RunComparison)
        .filter(models.RunComparison.baseline_run_id.in_(project_run_ids))
        .filter(models.RunComparison.current_run_id.in_(project_run_ids))
        .order_by(models.RunComparison.created_at.desc())
        .all()
    )


@router.get(
    "/projects/{project_id}/release-policy",
    response_model=schemas.ReleasePolicyRead,
)
def get_release_policy(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    db_policy = find_active_release_policy(
        db=db,
        project_id=project_id,
    )

    if db_policy is None:
        raise HTTPException(
            status_code=404,
            detail="Active release policy not found",
        )

    return db_policy


@router.put(
    "/projects/{project_id}/release-policy",
    response_model=schemas.ReleasePolicyRead,
)
def upsert_release_policy(
    project_id: int,
    policy_update: schemas.ReleasePolicyUpsert,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    db_policy = find_active_release_policy(
        db=db,
        project_id=project_id,
    )
    policy_values = policy_update.model_dump()

    if db_policy is None:
        db_policy = models.ReleasePolicy(
            project_id=project_id,
            version=1,
            is_active=True,
            **policy_values,
        )
        db.add(db_policy)
    else:
        for field_name, field_value in policy_values.items():
            setattr(db_policy, field_name, field_value)

        db_policy.version += 1
        db_policy.is_active = True

    db.commit()
    db.refresh(db_policy)

    return db_policy


@router.post(
    "/comparisons/{comparison_id}/release-report",
    response_model=schemas.ReleaseReportRead,
)
def create_release_report(
    comparison_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comparison_access = _authorize_run_comparison_for_request(
        db,
        current_user=current_user,
        comparison_id=comparison_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    db_comparison = comparison_access.comparison
    baseline_run = comparison_access.baseline_run
    current_run = comparison_access.current_run

    required_metrics = {
        "current_average_wer": db_comparison.current_average_wer,
        "current_average_cer": db_comparison.current_average_cer,
        "wer_delta": db_comparison.wer_delta,
        "cer_delta": db_comparison.cer_delta,
    }
    missing_metrics = [
        metric_name
        for metric_name, metric_value in required_metrics.items()
        if metric_value is None
    ]

    if missing_metrics:
        raise HTTPException(
            status_code=400,
            detail=(
                "Comparison is missing required release metrics: "
                + ", ".join(missing_metrics)
            ),
        )

    project_id = comparison_access.project.id
    db_policy = find_active_release_policy(
        db=db,
        project_id=project_id,
    )

    if db_policy is None:
        db_policy = create_default_release_policy(
            db=db,
            project_id=project_id,
        )

    release_result = evaluate_release_safety(
        current_average_wer=float(
            db_comparison.current_average_wer
        ),
        current_average_cer=float(
            db_comparison.current_average_cer
        ),
        wer_delta=float(db_comparison.wer_delta),
        cer_delta=float(db_comparison.cer_delta),
        policy=build_release_policy_thresholds(db_policy),
    )

    report_values = {
        "project_id": project_id,
        "comparison_id": db_comparison.id,
        "policy_id": db_policy.id,
        "status": release_result.status,
        "severity": release_result.severity,
        "headline": release_result.headline,
        "summary": release_result.summary,
        "recommendation": release_result.recommendation,
        "policy_snapshot": build_release_policy_snapshot(
            db_policy
        ),
        "checks": [
            asdict(check)
            for check in release_result.checks
        ],
    }

    db_report = (
        db.query(models.ReleaseReport)
        .filter(
            models.ReleaseReport.comparison_id
            == db_comparison.id
        )
        .first()
    )

    if db_report is None:
        db_report = models.ReleaseReport(**report_values)
        db.add(db_report)
    else:
        if db_report.project_id != project_id:
            raise HTTPException(
                status_code=404,
                detail="Release report not found",
            )

        if db_report.policy_id is not None:
            existing_policy = db.get(
                models.ReleasePolicy,
                db_report.policy_id,
            )

            if (
                existing_policy is None
                or existing_policy.project_id != project_id
            ):
                raise HTTPException(
                    status_code=404,
                    detail="Release report not found",
                )

        for field_name, field_value in report_values.items():
            setattr(db_report, field_name, field_value)

    db.commit()
    db.refresh(db_report)

    return db_report


@router.get(
    "/comparisons/{comparison_id}/release-report",
    response_model=schemas.ReleaseReportRead,
)
def get_release_report(
    comparison_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comparison_access = _authorize_run_comparison_for_request(
        db,
        current_user=current_user,
        comparison_id=comparison_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    db_report = (
        db.query(models.ReleaseReport)
        .filter(
            models.ReleaseReport.comparison_id
            == comparison_id
        )
        .first()
    )

    if db_report is None:
        raise HTTPException(
            status_code=404,
            detail="Release report not found",
        )

    if db_report.project_id != comparison_access.project.id:
        raise HTTPException(
            status_code=404,
            detail="Release report not found",
        )

    if db_report.policy_id is not None:
        db_policy = db.get(
            models.ReleasePolicy,
            db_report.policy_id,
        )

        if (
            db_policy is None
            or db_policy.project_id
            != comparison_access.project.id
        ):
            raise HTTPException(
                status_code=404,
                detail="Release report not found",
            )

    return db_report


@router.post(
    "/comparisons/{comparison_id}/debug-case",
    response_model=schemas.DebugCaseRead,
)
def create_debug_case_from_comparison(
    comparison_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comparison_access = _authorize_run_comparison_for_request(
        db,
        current_user=current_user,
        comparison_id=comparison_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    db_comparison = comparison_access.comparison
    baseline_run = comparison_access.baseline_run
    current_run = comparison_access.current_run

    if db_comparison.comparison_status != "regression":
        raise HTTPException(
            status_code=400,
            detail="Debug case can only be created for regression comparisons",
        )

    baseline_result, current_result, db_test_case = find_worst_debug_result_pair(
        db=db,
        baseline_run_id=baseline_run.id,
        current_run_id=current_run.id,
    )

    existing_debug_case = (
        db.query(models.DebugCase)
        .filter(models.DebugCase.baseline_run_id == baseline_run.id)
        .filter(models.DebugCase.current_run_id == current_run.id)
        .first()
    )

    if existing_debug_case is not None:
        if (
            existing_debug_case.project_id
            != comparison_access.project.id
        ):
            raise HTTPException(
                status_code=404,
                detail="Debug case not found",
            )

        updated_existing_case = False

        if existing_debug_case.test_case_id is None and db_test_case is not None:
            existing_debug_case.test_case_id = db_test_case.id
            updated_existing_case = True

        if existing_debug_case.baseline_result_id is None and baseline_result is not None:
            existing_debug_case.baseline_result_id = baseline_result.id
            updated_existing_case = True

        if existing_debug_case.current_result_id is None and current_result is not None:
            existing_debug_case.current_result_id = current_result.id
            updated_existing_case = True

        if existing_debug_case.ai_suggestion is None:
            existing_debug_case.ai_suggestion = build_debug_case_ai_suggestion(
                test_case=db_test_case,
                current_result=current_result,
            )
            updated_existing_case = True

        if updated_existing_case:
            db.commit()
            db.refresh(existing_debug_case)

        return existing_debug_case

    severity = build_debug_case_severity(
        comparison_status=db_comparison.comparison_status,
        wer_delta=db_comparison.wer_delta or 0.0,
    )

    if db_test_case is not None:
        title = f"Regression detected in {db_test_case.title}"
    else:
        title = f"Regression detected: {baseline_run.run_name} vs {current_run.run_name}"

    db_debug_case = models.DebugCase(
        project_id=comparison_access.project.id,
        title=title,
        status="open",
        severity=severity,
        failure_type="asr_regression",
        baseline_run_id=baseline_run.id,
        current_run_id=current_run.id,
        test_case_id=db_test_case.id if db_test_case is not None else None,
        baseline_result_id=baseline_result.id if baseline_result is not None else None,
        current_result_id=current_result.id if current_result is not None else None,
        summary=db_comparison.summary,
        engineer_notes=None,
        ai_suggestion=build_debug_case_ai_suggestion(
            test_case=db_test_case,
            current_result=current_result,
        ),
    )

    db.add(db_debug_case)
    db.commit()
    db.refresh(db_debug_case)

    return db_debug_case


@router.get(
    "/projects/{project_id}/debug-cases",
    response_model=list[schemas.DebugCaseRead],
)
def list_project_debug_cases(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    debug_cases = (
        db.query(models.DebugCase)
        .filter(models.DebugCase.project_id == project_id)
        .order_by(models.DebugCase.created_at.desc())
        .all()
    )

    accessible_debug_cases: list[models.DebugCase] = []

    for debug_case in debug_cases:
        try:
            access = authorize_debug_case(
                db,
                user_id=current_user.id,
                debug_case_id=debug_case.id,
                required_roles=PRODUCT_READ_ROLES,
            )
        except DebugCaseNotAccessibleError:
            continue

        accessible_debug_cases.append(
            access.debug_case
        )

    return accessible_debug_cases


@router.get(
    "/debug-cases/{debug_case_id}",
    response_model=schemas.DebugCaseRead,
)
def get_debug_case(
    debug_case_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access = _authorize_debug_case_for_request(
        db,
        current_user=current_user,
        debug_case_id=debug_case_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    return access.debug_case


@router.get(
    "/debug-cases/{debug_case_id}/details",
    response_model=schemas.DebugCaseDetailRead,
)
def get_debug_case_details(
    debug_case_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    debug_access = _authorize_debug_case_for_request(
        db,
        current_user=current_user,
        debug_case_id=debug_case_id,
        required_roles=PRODUCT_READ_ROLES,
    )

    db_debug_case = debug_access.debug_case
    project_id = debug_access.project.id

    def fail_integrity() -> None:
        raise HTTPException(
            status_code=404,
            detail="Debug case not found",
        )

    def resolve_run(
        run_id: int | None,
    ) -> models.EvaluationRun | None:
        if run_id is None:
            return None

        try:
            access = authorize_evaluation_run(
                db,
                user_id=current_user.id,
                run_id=run_id,
                required_roles=PRODUCT_READ_ROLES,
            )
        except (
            EvaluationRunNotAccessibleError,
            EvaluationRunPermissionDeniedError,
        ):
            fail_integrity()

        if access.project.id != project_id:
            fail_integrity()

        return access.run

    def resolve_result(
        result_id: int | None,
    ) -> models.EvaluationResult | None:
        if result_id is None:
            return None

        try:
            access = authorize_evaluation_result(
                db,
                user_id=current_user.id,
                result_id=result_id,
                required_roles=PRODUCT_READ_ROLES,
            )
        except (
            EvaluationResultNotAccessibleError,
            EvaluationResultPermissionDeniedError,
        ):
            fail_integrity()

        if access.project.id != project_id:
            fail_integrity()

        return access.result

    def resolve_test_case(
        test_case_id: int | None,
    ) -> models.TestCase | None:
        if test_case_id is None:
            return None

        try:
            access = authorize_test_case(
                db,
                user_id=current_user.id,
                test_case_id=test_case_id,
                required_roles=PRODUCT_READ_ROLES,
            )
        except (
            TestCaseNotAccessibleError,
            TestCasePermissionDeniedError,
        ):
            fail_integrity()

        if access.project.id != project_id:
            fail_integrity()

        return access.test_case

    baseline_run = resolve_run(
        db_debug_case.baseline_run_id
    )
    current_run = resolve_run(
        db_debug_case.current_run_id
    )
    baseline_result = resolve_result(
        db_debug_case.baseline_result_id
    )
    current_result = resolve_result(
        db_debug_case.current_result_id
    )
    test_case = resolve_test_case(
        db_debug_case.test_case_id
    )

    if (
        (
            baseline_result is None
            or current_result is None
            or test_case is None
        )
        and baseline_run is not None
        and current_run is not None
    ):
        (
            fallback_baseline_result,
            fallback_current_result,
            fallback_test_case,
        ) = find_worst_debug_result_pair(
            db=db,
            baseline_run_id=baseline_run.id,
            current_run_id=current_run.id,
        )

        if (
            baseline_result is None
            and fallback_baseline_result is not None
        ):
            baseline_result = resolve_result(
                fallback_baseline_result.id
            )

        if (
            current_result is None
            and fallback_current_result is not None
        ):
            current_result = resolve_result(
                fallback_current_result.id
            )

        if (
            test_case is None
            and fallback_test_case is not None
        ):
            test_case = resolve_test_case(
                fallback_test_case.id
            )

    return {
        "debug_case": db_debug_case,
        "test_case": test_case,
        "baseline_run": baseline_run,
        "current_run": current_run,
        "baseline_result": baseline_result,
        "current_result": current_result,
    }


@router.post(
    "/runs/{run_id}/upload",
    deprecated=True,
)
async def upload_run_artifacts(
    run_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retired legacy run-level artifact upload endpoint.

    Evaluation evidence must be bound to a specific test case.
    The previous run-level upload contract could mark a run
    evaluated without creating a test-case-bound EvaluationResult
    or provenance record, so it is intentionally no longer accepted.
    """
    _authorize_evaluation_run_for_request(
        db,
        current_user=current_user,
        run_id=run_id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    raise HTTPException(
        status_code=410,
        detail=(
            "Legacy run artifact upload is retired. "
            "Use the test-case evaluation endpoints."
        ),
    )
