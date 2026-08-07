from collections.abc import Iterable

from sqlalchemy.orm import Session

from app import models


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
