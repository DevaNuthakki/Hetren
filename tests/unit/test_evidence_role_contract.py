from dataclasses import (
    FrozenInstanceError,
    fields,
)

import pytest

from packages.contracts import (
    ContractError,
    EvidenceRole,
    EvidenceRoleAssignment,
)


DIGEST = "0" * 64


def make_assignment(
    **overrides,
) -> EvidenceRoleAssignment:
    values = {
        "tenant_id": "tenant-1",
        "project_id": "project-1",
        "assignment_id": "evidence-role-1",
        "evidence_reference": (
            "fixture://evidence/incident-report-1"
        ),
        "evidence_sha256": DIGEST,
        "qualifier_id": "evidence-qualifier",
        "qualifier_version": "1",
        "qualification_reference": (
            "protocol://heal/evidence-role/v1"
        ),
        "qualification_sha256": "1" * 64,
        "roles": (
            EvidenceRole.OBSERVATION,
            EvidenceRole.REPRODUCTION,
        ),
        "rationale": (
            "The artifact records the observed result "
            "and reproduces the bounded failure."
        ),
        "uncertainty": (
            "Role assignment does not prove causal correctness."
        ),
        "limitations": (
            "controlled evidence only",
            "role assignment is qualifier-reported",
        ),
    }

    values.update(
        overrides
    )

    return EvidenceRoleAssignment(
        **values
    )


def test_evidence_role_enum_matches_preregistered_roles():
    assert {
        role.value
        for role in EvidenceRole
    } == {
        "OBSERVATION",
        "REPRODUCTION",
        "CAUSE_DISCRIMINATING",
        "REPAIR_DISCRIMINATING",
        "REGRESSION",
        "INDEPENDENT_VERIFICATION",
    }


def test_assignment_preserves_multiple_sorted_roles():
    assignment = make_assignment()

    assert assignment.roles == (
        EvidenceRole.OBSERVATION,
        EvidenceRole.REPRODUCTION,
    )

    assert assignment.canonical_payload()[
        "roles"
    ] == (
        "OBSERVATION",
        "REPRODUCTION",
    )


def test_assignment_hash_is_deterministic_role_and_protocol_bound():
    first = make_assignment()
    second = make_assignment()

    changed_role = make_assignment(
        roles=(
            EvidenceRole.REPRODUCTION,
        ),
    )

    changed_protocol = make_assignment(
        qualification_sha256="2" * 64,
    )

    assert (
        first.assignment_sha256
        == second.assignment_sha256
    )

    assert (
        first.assignment_sha256
        != changed_role.assignment_sha256
    )

    assert (
        first.assignment_sha256
        != changed_protocol.assignment_sha256
    )


def test_assignment_is_frozen():
    assignment = make_assignment()

    with pytest.raises(
        FrozenInstanceError
    ):
        assignment.rationale = "changed"


def test_empty_roles_are_rejected():
    with pytest.raises(
        ContractError,
        match="at least one EvidenceRole",
    ):
        make_assignment(
            roles=(),
        )


def test_duplicate_roles_are_rejected():
    with pytest.raises(
        ContractError,
        match="roles must be unique",
    ):
        make_assignment(
            roles=(
                EvidenceRole.OBSERVATION,
                EvidenceRole.OBSERVATION,
            ),
        )


def test_unsorted_roles_are_rejected():
    with pytest.raises(
        ContractError,
        match="sorted",
    ):
        make_assignment(
            roles=(
                EvidenceRole.REPRODUCTION,
                EvidenceRole.OBSERVATION,
            ),
        )


def test_non_role_member_is_rejected():
    with pytest.raises(
        ContractError,
        match="only EvidenceRole",
    ):
        make_assignment(
            roles=(
                "OBSERVATION",
            ),
        )


def test_invalid_evidence_sha256_is_rejected():
    with pytest.raises(
        ContractError,
        match="evidence_sha256",
    ):
        make_assignment(
            evidence_sha256="not-a-digest",
        )


def test_empty_evidence_reference_is_rejected():
    with pytest.raises(
        ContractError,
        match="evidence_reference",
    ):
        make_assignment(
            evidence_reference="",
        )


def test_empty_qualification_reference_is_rejected():
    with pytest.raises(
        ContractError,
        match="qualification_reference",
    ):
        make_assignment(
            qualification_reference="",
        )


def test_invalid_qualification_sha256_is_rejected():
    with pytest.raises(
        ContractError,
        match="qualification_sha256",
    ):
        make_assignment(
            qualification_sha256="not-a-digest",
        )


def test_limitations_must_be_a_tuple():
    with pytest.raises(
        ContractError,
        match="limitations",
    ):
        make_assignment(
            limitations=[
                "not a tuple",
            ],
        )


def test_assignment_has_no_authority_or_verdict_surface():
    names = {
        field.name
        for field in fields(
            EvidenceRoleAssignment
        )
    }

    assert names.isdisjoint(
        {
            "outcome",
            "verdict",
            "verified",
            "eligible",
            "authorization",
            "authorized",
            "approval",
            "approved",
            "can_execute",
            "can_deploy",
            "deployment_authority",
            "lifecycle_state",
            "complete",
            "is_complete",
        }
    )

    independent = make_assignment(
        roles=(
            EvidenceRole.INDEPENDENT_VERIFICATION,
        ),
        limitations=(
            "role label does not prove independence",
        ),
    )

    assert independent.roles == (
        EvidenceRole.INDEPENDENT_VERIFICATION,
    )
