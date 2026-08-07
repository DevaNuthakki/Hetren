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


@dataclass(frozen=True)
class DatasetAccess:
    dataset: models.Dataset
    project: models.Project
    membership: models.OrganizationMembership


@dataclass(frozen=True)
class TestCaseAccess:
    test_case: models.TestCase
    dataset: models.Dataset
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


class DatasetNotAccessibleError(LookupError):
    """
    Raised when a dataset must not be disclosed to the user.
    """


class DatasetPermissionDeniedError(PermissionError):
    """
    Raised when the user belongs to the tenant but lacks dataset permission.
    """


class TestCaseNotAccessibleError(LookupError):
    """
    Raised when a test case must not be disclosed to the user.
    """


class TestCasePermissionDeniedError(PermissionError):
    """
    Raised when the user belongs to the tenant but lacks test-case permission.
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



def authorize_dataset(
    db: Session,
    *,
    user_id: int,
    dataset_id: int,
    required_roles: Collection[str],
) -> DatasetAccess:
    """
    Resolve a dataset through its project and tenant membership.

    Missing datasets, cross-tenant datasets, and datasets belonging to
    legacy projects without organization ownership all fail closed.
    """
    roles = _validate_required_roles(required_roles)

    row = db.execute(
        select(
            models.Dataset,
            models.Project,
            models.OrganizationMembership,
        )
        .join(
            models.Project,
            models.Project.id == models.Dataset.project_id,
        )
        .join(
            models.OrganizationMembership,
            (
                models.OrganizationMembership.organization_id
                == models.Project.organization_id
            ),
        )
        .where(
            models.Dataset.id == dataset_id,
            models.Project.organization_id.is_not(None),
            models.OrganizationMembership.user_id == user_id,
        )
    ).one_or_none()

    if row is None:
        raise DatasetNotAccessibleError(
            "Dataset is not accessible."
        )

    dataset, project, membership = row

    if membership.role not in roles:
        raise DatasetPermissionDeniedError(
            "Dataset permission is denied."
        )

    return DatasetAccess(
        dataset=dataset,
        project=project,
        membership=membership,
    )


def authorize_test_case(
    db: Session,
    *,
    user_id: int,
    test_case_id: int,
    required_roles: Collection[str],
) -> TestCaseAccess:
    """
    Resolve a test case through dataset, project, and tenant membership.

    A direct test-case identifier never bypasses the project tenant
    boundary.
    """
    roles = _validate_required_roles(required_roles)

    row = db.execute(
        select(
            models.TestCase,
            models.Dataset,
            models.Project,
            models.OrganizationMembership,
        )
        .join(
            models.Dataset,
            models.Dataset.id == models.TestCase.dataset_id,
        )
        .join(
            models.Project,
            models.Project.id == models.Dataset.project_id,
        )
        .join(
            models.OrganizationMembership,
            (
                models.OrganizationMembership.organization_id
                == models.Project.organization_id
            ),
        )
        .where(
            models.TestCase.id == test_case_id,
            models.Project.organization_id.is_not(None),
            models.OrganizationMembership.user_id == user_id,
        )
    ).one_or_none()

    if row is None:
        raise TestCaseNotAccessibleError(
            "Test case is not accessible."
        )

    test_case, dataset, project, membership = row

    if membership.role not in roles:
        raise TestCasePermissionDeniedError(
            "Test case permission is denied."
        )

    return TestCaseAccess(
        test_case=test_case,
        dataset=dataset,
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
