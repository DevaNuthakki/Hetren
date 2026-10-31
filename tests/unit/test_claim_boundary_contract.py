from dataclasses import (
    FrozenInstanceError,
    fields,
    replace,
)

import pytest

from packages.contracts import (
    ClaimBoundary,
    ClaimBoundaryDemonstration,
    ClaimBoundaryExternalStatus,
    ClaimBoundarySource,
    ContractError,
    GoalContract,
    SystemSnapshot,
)


ZERO = "0" * 64
ONE = "1" * 64
TWO = "2" * 64
THREE = "3" * 64
FOUR = "4" * 64


def make_goal() -> GoalContract:
    return GoalContract(
        tenant_id="tenant-1",
        project_id="project-1",
        contract_id="goal-1",
        contract_version="1",
        system_id="system-1",
        system_version_id="candidate-v1",
        claim_scope="bounded HEAL claim",
        objective="Assess the registered repair claim",
        metrics=(
            "bounded-correctness",
        ),
        minimum_effect="registered threshold",
        baseline_reference="baseline-1",
        acceptance_predicates=(
            "registered target behavior",
        ),
        hard_constraints=(),
        invariants=(),
        eligible_changes=(
            "configuration",
        ),
        budget_constraints=(
            "bounded evaluation budget",
        ),
        reviewer_version="reviewer-v1",
        evaluator_version="evaluator-v1",
        evidence_requirements=(
            "bounded evidence",
        ),
        protected_evaluation_requirements=(
            "protected outcomes remain isolated",
        ),
        uncertainty_policy=(
            "preserve unsupported uncertainty"
        ),
        failure_invalidity_policy=(
            "preserve failures and invalid runs separately"
        ),
        verification_requirements=(
            "verification remains distinct from ordinary evaluation",
        ),
    )


def make_snapshot() -> SystemSnapshot:
    return SystemSnapshot(
        tenant_id="tenant-1",
        project_id="project-1",
        snapshot_id="candidate-snapshot",
        system_id="system-1",
        system_version_id="candidate-v1",
        environment_family="controlled-agent",
        component_version_ids=(
            "candidate-v1",
        ),
        provider_binding_ids=(),
        adapter_binding_ids=(),
        evaluator_binding_ids=(
            "evaluator-v1",
        ),
        code_identity=ZERO,
        data_identity=None,
        prompt_identity=ONE,
        runtime_identity="python-3.12",
        state_references=(
            "state://candidate",
        ),
        artifact_references=(),
    )


def default_sources():
    return (
        ClaimBoundarySource(
            reference="artifact://repair-contrast",
            sha256=TWO,
        ),
        ClaimBoundarySource(
            reference="artifact://verification",
            sha256=THREE,
        ),
        ClaimBoundarySource(
            reference="artifact://vsp",
            sha256=FOUR,
        ),
    )


def default_demonstrated_properties():
    return (
        ClaimBoundaryDemonstration(
            statement=(
                "the registered repair passed the bounded "
                "repair-contrast and verification procedure"
            ),
            source_references=(
                "artifact://repair-contrast",
                "artifact://verification",
            ),
        ),
    )


def make_boundary(
    *,
    goal=None,
    snapshot=None,
    **overrides,
) -> ClaimBoundary:
    if goal is None:
        goal = make_goal()

    if snapshot is None:
        snapshot = make_snapshot()

    values = {
        "tenant_id": goal.tenant_id,
        "project_id": goal.project_id,
        "boundary_id": "claim-boundary-1",
        "goal_contract_id": goal.contract_id,
        "goal_contract_sha256": goal.contract_sha256,
        "system_snapshot_id": snapshot.snapshot_id,
        "system_snapshot_sha256": snapshot.snapshot_sha256,
        "qualifier_id": "claim-boundary-qualifier",
        "qualifier_version": "1",
        "protocol_reference": "protocol://heal/claim-boundary/v1",
        "protocol_sha256": ZERO,
        "sources": default_sources(),
        "demonstrated_properties": (
            default_demonstrated_properties()
        ),
        "assumptions": (
            "source artifact provenance is authentic",
        ),
        "unresolved_uncertainty": (
            "realistic stochastic workload performance is unestablished",
        ),
        "unsupported_generalizations": (
            "does not establish general AI-agent reliability",
            "does not establish multi-fault capability",
            "does not establish state-of-the-art superiority",
        ),
        "authorization_status": (
            ClaimBoundaryExternalStatus.NOT_ESTABLISHED
        ),
        "deployment_status": (
            ClaimBoundaryExternalStatus.NOT_ESTABLISHED
        ),
        "rationale": (
            "state only what the bounded accumulated evidence supports"
        ),
        "limitations": (
            "qualifier-reported boundary",
            "source identities do not prove external truth",
        ),
    }

    values.update(
        overrides
    )

    return ClaimBoundary(
        **values
    )


def test_external_status_vocabulary_is_non_authoritative():
    assert tuple(
        item.value
        for item in ClaimBoundaryExternalStatus
    ) == (
        "NOT_ESTABLISHED",
        "UNKNOWN",
        "OUTSIDE_SCOPE",
    )

    values = {
        item.value
        for item in ClaimBoundaryExternalStatus
    }

    assert "AUTHORIZED" not in values
    assert "DEPLOYED" not in values


def test_source_payload_is_deterministic():
    source = ClaimBoundarySource(
        reference="artifact://one",
        sha256=ZERO,
    )

    assert source.canonical_payload() == {
        "reference": "artifact://one",
        "sha256": ZERO,
    }


def test_valid_boundary_binds_goal_and_snapshot():
    goal = make_goal()
    snapshot = make_snapshot()

    boundary = make_boundary(
        goal=goal,
        snapshot=snapshot,
    )

    boundary.validate_against(
        goal=goal,
        snapshot=snapshot,
    )


def test_boundary_hash_is_deterministic_and_source_bound():
    first = make_boundary()
    second = make_boundary()

    changed_sources = (
        ClaimBoundarySource(
            reference="artifact://repair-contrast",
            sha256=TWO,
        ),
        ClaimBoundarySource(
            reference="artifact://verification",
            sha256=THREE,
        ),
        ClaimBoundarySource(
            reference="artifact://vsp",
            sha256="5" * 64,
        ),
    )

    changed = make_boundary(
        sources=changed_sources,
    )

    assert (
        first.boundary_sha256
        == second.boundary_sha256
    )

    assert (
        first.boundary_sha256
        != changed.boundary_sha256
    )


def test_source_is_frozen():
    source = default_sources()[0]

    with pytest.raises(
        FrozenInstanceError
    ):
        source.reference = "changed"


def test_boundary_is_frozen():
    boundary = make_boundary()

    with pytest.raises(
        FrozenInstanceError
    ):
        boundary.rationale = "changed"


def test_sources_must_be_a_tuple():
    with pytest.raises(
        ContractError,
        match="sources must be a tuple",
    ):
        make_boundary(
            sources=list(
                default_sources()
            ),
        )


def test_source_members_must_have_correct_type():
    sources = list(
        default_sources()
    )

    sources[0] = "not-a-source"

    with pytest.raises(
        ContractError,
        match="ClaimBoundarySource",
    ):
        make_boundary(
            sources=tuple(sources),
        )


def test_source_references_must_be_unique():
    source = default_sources()[0]

    with pytest.raises(
        ContractError,
        match="source references must be unique",
    ):
        make_boundary(
            sources=(
                source,
                source,
            ),
        )


def test_sources_must_be_canonically_sorted():
    sources = tuple(
        reversed(
            default_sources()
        )
    )

    with pytest.raises(
        ContractError,
        match="sorted by reference",
    ):
        make_boundary(
            sources=sources,
        )


def test_demonstrated_property_requires_source_references():
    with pytest.raises(
        ContractError,
        match="requires source references",
    ):
        ClaimBoundaryDemonstration(
            statement="bounded positive statement",
            source_references=(),
        )


def test_demonstrated_property_source_references_must_be_unique():
    with pytest.raises(
        ContractError,
        match="source references must be unique",
    ):
        ClaimBoundaryDemonstration(
            statement="bounded positive statement",
            source_references=(
                "artifact://one",
                "artifact://one",
            ),
        )


def test_demonstrated_properties_require_correct_member_type():
    values = (
        "not-a-demonstration",
    )

    with pytest.raises(
        ContractError,
        match="ClaimBoundaryDemonstration",
    ):
        make_boundary(
            demonstrated_properties=values,
        )


def test_demonstrated_property_sources_must_be_declared():
    unsupported = ClaimBoundaryDemonstration(
        statement="bounded positive statement",
        source_references=(
            "artifact://not-declared",
        ),
    )

    with pytest.raises(
        ContractError,
        match="not declared by Claim Boundary",
    ):
        make_boundary(
            demonstrated_properties=(
                unsupported,
            ),
        )


def test_demonstrated_properties_require_provenance():
    with pytest.raises(
        ContractError,
        match="demonstrated properties require source provenance",
    ):
        make_boundary(
            sources=(),
        )


def test_boundary_must_contain_claim_content():
    with pytest.raises(
        ContractError,
        match="at least one claim-boundary statement",
    ):
        make_boundary(
            sources=(),
            demonstrated_properties=(),
            assumptions=(),
            unresolved_uncertainty=(),
            unsupported_generalizations=(),
        )


def test_goal_identity_must_match():
    goal = make_goal()
    snapshot = make_snapshot()

    boundary = make_boundary(
        goal=goal,
        snapshot=snapshot,
    )

    changed_goal = replace(
        goal,
        contract_id="different-goal",
    )

    with pytest.raises(
        ContractError,
        match="goal_contract_id",
    ):
        boundary.validate_against(
            goal=changed_goal,
            snapshot=snapshot,
        )


def test_snapshot_identity_must_match():
    goal = make_goal()
    snapshot = make_snapshot()

    boundary = make_boundary(
        goal=goal,
        snapshot=snapshot,
    )

    changed_snapshot = replace(
        snapshot,
        snapshot_id="different-snapshot",
    )

    with pytest.raises(
        ContractError,
        match="system_snapshot_id",
    ):
        boundary.validate_against(
            goal=goal,
            snapshot=changed_snapshot,
        )


def test_snapshot_must_belong_to_goal_system():
    goal = make_goal()
    snapshot = make_snapshot()

    boundary = make_boundary(
        goal=goal,
        snapshot=snapshot,
    )

    changed_snapshot = replace(
        snapshot,
        system_id="different-system",
    )

    with pytest.raises(
        ContractError,
        match="snapshot.system_id",
    ):
        boundary.validate_against(
            goal=goal,
            snapshot=changed_snapshot,
        )


def test_claim_categories_remain_string_tuples():
    with pytest.raises(
        ContractError,
        match="assumptions",
    ):
        make_boundary(
            assumptions=[
                "not a tuple",
            ],
        )


def test_external_status_requires_enum():
    with pytest.raises(
        ContractError,
        match="authorization_status",
    ):
        make_boundary(
            authorization_status="NOT_ESTABLISHED",
        )


def test_boundary_has_no_authority_or_completion_surface():
    names = {
        field.name
        for field in fields(
            ClaimBoundary
        )
    }

    assert names.isdisjoint(
        {
            "authorized",
            "authorization_reference",
            "approval",
            "approved",
            "deployment_authority",
            "deploy",
            "deployed",
            "can_deploy",
            "eligible",
            "verified",
            "lifecycle_state",
            "complete",
            "is_complete",
        }
    )
