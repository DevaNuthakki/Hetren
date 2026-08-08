from collections.abc import Iterable

from sqlalchemy.orm import Session

from app import models
from app.evaluation_provenance import (
    stage_evaluation_result_provenance,
)


def resolve_seed_organization_id(
    db: Session,
    *,
    project_names: Iterable[str],
) -> int:
    """
    Resolve the organization that should own regenerated demo data.

    Existing owned demo projects take precedence. If there is no
    existing owned demo project, a single organization may be used as
    an unambiguous local fallback. Ambiguous ownership fails closed.
    """
    normalized_names = sorted(
        {
            name.strip()
            for name in project_names
            if isinstance(name, str) and name.strip()
        }
    )

    if not normalized_names:
        raise ValueError(
            "At least one demo project name is required."
        )

    existing_projects = (
        db.query(models.Project)
        .filter(
            models.Project.name.in_(
                normalized_names
            )
        )
        .all()
    )

    existing_organization_ids = {
        project.organization_id
        for project in existing_projects
        if project.organization_id is not None
    }

    if len(existing_organization_ids) > 1:
        raise RuntimeError(
            "Existing demo projects belong to multiple "
            "organizations. Refusing to guess ownership."
        )

    if len(existing_organization_ids) == 1:
        return next(iter(existing_organization_ids))

    organizations = (
        db.query(models.Organization.id)
        .order_by(models.Organization.id.asc())
        .limit(2)
        .all()
    )

    if len(organizations) == 1:
        return organizations[0][0]

    if not organizations:
        raise RuntimeError(
            "No organization exists for demo seed data. "
            "Create or select an organization first."
        )

    raise RuntimeError(
        "Multiple organizations exist and existing demo "
        "ownership cannot determine which one to use."
    )


def stage_seed_fixture_result(
    db: Session,
    *,
    run: models.EvaluationRun,
    test_case: models.TestCase,
    generated_text: str,
    generated_file_path: str | None,
    wer_score: float,
    cer_score: float,
    quality_label: str,
    error_summary: str,
    seed_source: str,
) -> models.EvaluationResult:
    """
    Stage a synthetic validation result with explicit fixture provenance.

    Seed fixtures may intentionally use controlled metrics, so this helper
    preserves the supplied values rather than recalculating them through
    the live evaluator.

    Because those metrics are synthetic, the fixture deliberately does
    not fabricate live HVEE observation evidence. Its execution metadata
    identifies it as a seed fixture and its provenance remains schema v3.
    """
    normalized_seed_source = (
        seed_source.strip()
        if isinstance(seed_source, str)
        else ""
    )

    if not normalized_seed_source:
        raise ValueError(
            "Seed fixture source is required."
        )

    result = models.EvaluationResult(
        run_id=run.id,
        test_case_id=test_case.id,
        generated_transcript=generated_text,
        generated_file_path=generated_file_path,
        wer=wer_score,
        cer=cer_score,
        quality_label=quality_label,
        error_summary=error_summary,
    )
    db.add(result)

    run.reference_transcript = (
        test_case.reference_transcript
    )
    run.generated_transcript = generated_text
    run.wer = wer_score
    run.cer = cer_score
    run.quality_label = quality_label
    run.error_summary = error_summary
    run.status = "evaluated"

    db.flush()

    stage_evaluation_result_provenance(
        db,
        result=result,
        evaluation_run=run,
        test_case=test_case,
        execution_mode="seed_fixture",
        server_observed={
            "fixture": True,
            "seed_source": normalized_seed_source,
        },
        external_reported={},
        bind_observation_evidence=False,
    )

    # Surface provenance constraint failures before the outer seed
    # transaction commits.
    db.flush()

    return result
