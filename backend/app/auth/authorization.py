from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


ALL_MEMBERSHIP_ROLES = frozenset(
    {
        "owner",
        "admin",
        "engineer",
        "viewer",
        "billing_admin",
    }
)

PRODUCT_READ_ROLES = frozenset(
    {
        "owner",
        "admin",
        "engineer",
        "viewer",
    }
)

PRODUCT_WRITE_ROLES = frozenset(
    {
        "owner",
        "admin",
        "engineer",
    }
)


@dataclass(frozen=True)
class OrganizationAccess:
    organization: models.Organization
    membership: models.OrganizationMembership


@dataclass(frozen=True)
class ProjectAccess:
    project: models.Project
    membership: models.OrganizationMembership


class OrganizationNotAccessibleError(LookupError):
    """
    Raised when an organization must not be disclosed to the user.
    """


class OrganizationPermissionDeniedError(PermissionError):
    """
    Raised when the user belongs to the organization but lacks the role.
    """


class ProjectNotAccessibleError(LookupError):
    """
    Raised when a project must not be disclosed to the user.
    """


class ProjectPermissionDeniedError(PermissionError):
    """
    Raised when the user belongs to the tenant but lacks project permission.
    """


def _validate_required_roles(
    required_roles: Collection[str],
) -> frozenset[str]:
    roles = frozenset(required_roles)

    if not roles:
        raise ValueError(
            "At least one required role must be configured"
        )

    unknown_roles = roles - ALL_MEMBERSHIP_ROLES

    if unknown_roles:
        raise ValueError(
            "Unknown organization membership roles: "
            + ", ".join(sorted(unknown_roles))
        )

    return roles


def authorize_organization(
    db: Session,
    *,
    user_id: int,
    organization_id: int,
    required_roles: Collection[str],
) -> OrganizationAccess:
    """
    Resolve one organization through the user's membership.

    Missing organizations and organizations belonging to another tenant
    intentionally produce the same not-accessible result.
    """
    roles = _validate_required_roles(required_roles)

    row = db.execute(
        select(
            models.Organization,
            models.OrganizationMembership,
        )
        .join(
            models.OrganizationMembership,
            (
                models.OrganizationMembership.organization_id
                == models.Organization.id
            ),
        )
        .where(
            models.Organization.id == organization_id,
            models.OrganizationMembership.user_id == user_id,
        )
    ).one_or_none()

    if row is None:
        raise OrganizationNotAccessibleError(
            "Organization is not accessible."
        )

    organization, membership = row

    if membership.role not in roles:
        raise OrganizationPermissionDeniedError(
            "Organization permission is denied."
        )

    return OrganizationAccess(
        organization=organization,
        membership=membership,
    )


def authorize_project(
    db: Session,
    *,
    user_id: int,
    project_id: int,
    required_roles: Collection[str],
) -> ProjectAccess:
    """
    Resolve a project only through an organization membership.

    Projects without organization ownership fail closed. Projects in
    another organization are intentionally indistinguishable from
    nonexistent projects.
    """
    roles = _validate_required_roles(required_roles)

    row = db.execute(
        select(
            models.Project,
            models.OrganizationMembership,
        )
        .join(
            models.OrganizationMembership,
            (
                models.OrganizationMembership.organization_id
                == models.Project.organization_id
            ),
        )
        .where(
            models.Project.id == project_id,
            models.Project.organization_id.is_not(None),
            models.OrganizationMembership.user_id == user_id,
        )
    ).one_or_none()

    if row is None:
        raise ProjectNotAccessibleError(
            "Project is not accessible."
        )

    project, membership = row

    if membership.role not in roles:
        raise ProjectPermissionDeniedError(
            "Project permission is denied."
        )

    return ProjectAccess(
        project=project,
        membership=membership,
    )


def list_accessible_projects(
    db: Session,
    *,
    user_id: int,
) -> list[models.Project]:
    """
    List product-data projects visible to a human user.

    Billing-only memberships and legacy projects without tenant ownership
    are deliberately excluded.
    """
    statement = (
        select(models.Project)
        .join(
            models.OrganizationMembership,
            (
                models.OrganizationMembership.organization_id
                == models.Project.organization_id
            ),
        )
        .where(
            models.Project.organization_id.is_not(None),
            models.OrganizationMembership.user_id == user_id,
            models.OrganizationMembership.role.in_(
                tuple(sorted(PRODUCT_READ_ROLES))
            ),
        )
        .order_by(
            models.Project.created_at.desc(),
            models.Project.id.desc(),
        )
    )

    return list(
        db.scalars(statement).all()
    )
