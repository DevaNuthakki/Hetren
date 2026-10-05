from dataclasses import FrozenInstanceError

import pytest

from packages.contracts import (
    ContractError,
    GoalContract,
    SystemSnapshot,
)


DIGEST = "0" * 64


def make_goal(**overrides):
    values = {
        "tenant_id": "tenant-1",
        "project_id": "project-1",
        "contract_id": "goal-1",
        "contract_version": "1",
        "system_id": "system-1",
        "system_version_id": "system-version-1",
        "claim_scope": "bounded repair claim",
        "objective": "Improve target behavior under governed constraints",
        "metrics": ("primary_metric",),
        "minimum_effect": "minimum governed improvement",
        "baseline_reference": "baseline-1",
        "acceptance_predicates": ("primary_metric improves",),
        "hard_constraints": (),
        "invariants": (),
        "eligible_changes": ("configuration",),
        "budget_constraints": ("within governed budget",),
        "reviewer_version": "reviewer-v1",
        "evaluator_version": "evaluator-v1",
        "evidence_requirements": ("execution evidence",),
        "protected_evaluation_requirements": (
            "criteria frozen before protected evaluation",
        ),
        "uncertainty_policy": "report inconclusive when evidence is insufficient",
        "failure_invalidity_policy": "distinguish failure from invalid evidence",
        "verification_requirements": (
            "independent verification required for consequential claims",
        ),
    }

    values.update(overrides)
    return GoalContract(**values)


def make_snapshot(**overrides):
    values = {
        "tenant_id": "tenant-1",
        "project_id": "project-1",
        "snapshot_id": "snapshot-1",
        "system_id": "system-1",
        "system_version_id": "system-version-1",
        "environment_family": "E1_AGENT",
        "component_version_ids": ("component-version-1",),
        "provider_binding_ids": ("provider-binding-1",),
        "adapter_binding_ids": ("adapter-binding-1",),
        "evaluator_binding_ids": ("evaluator-binding-1",),
        "code_identity": DIGEST,
        "data_identity": DIGEST,
        "prompt_identity": DIGEST,
        "runtime_identity": "runtime-v1",
        "state_references": ("state-1",),
        "artifact_references": ("artifact-1",),
    }

    values.update(overrides)
    return SystemSnapshot(**values)


def test_goal_contract_is_immutable():
    goal = make_goal()

    with pytest.raises(FrozenInstanceError):
        goal.objective = "changed"


def test_system_snapshot_is_immutable():
    snapshot = make_snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.environment_family = "E2_STRUCTURED_ML"


def test_goal_contract_requires_non_empty_metrics():
    with pytest.raises(ContractError):
        make_goal(metrics=())


def test_goal_contract_requires_tuple_collections():
    with pytest.raises(ContractError):
        make_goal(metrics=["primary_metric"])


def test_goal_contract_allows_optional_baseline_reference():
    goal = make_goal(baseline_reference=None)

    assert goal.baseline_reference is None


def test_goal_contract_requires_core_identity_fields():
    with pytest.raises(ContractError):
        make_goal(system_version_id="")


def test_goal_contract_digest_is_deterministic():
    assert make_goal().contract_sha256 == make_goal().contract_sha256


def test_goal_contract_digest_changes_when_definition_changes():
    assert (
        make_goal().contract_sha256
        != make_goal(objective="different objective").contract_sha256
    )


def test_goal_contract_has_no_runtime_outcome_fields():
    fields = GoalContract.__dataclass_fields__

    assert "verdict" not in fields
    assert "score" not in fields
    assert "authorization" not in fields
    assert "execution_result" not in fields


def test_system_snapshot_requires_explicit_environment_family():
    with pytest.raises(ContractError):
        make_snapshot(environment_family="")


def test_system_snapshot_collection_fields_are_tuples():
    with pytest.raises(ContractError):
        make_snapshot(component_version_ids=["component-version-1"])


def test_system_snapshot_allows_same_system_version_in_multiple_snapshots():
    first = make_snapshot(snapshot_id="snapshot-1")
    second = make_snapshot(
        snapshot_id="snapshot-2",
        state_references=("different-state",),
    )

    assert first.system_version_id == second.system_version_id
    assert first.snapshot_id != second.snapshot_id
    assert first.snapshot_sha256 != second.snapshot_sha256


def test_system_snapshot_digest_is_deterministic():
    assert make_snapshot().snapshot_sha256 == make_snapshot().snapshot_sha256


def test_system_snapshot_does_not_define_capability_support():
    fields = SystemSnapshot.__dataclass_fields__

    assert "supported" not in fields
    assert "qualified" not in fields
    assert "verdict" not in fields
    assert "authorization" not in fields



from dataclasses import FrozenInstanceError, fields
import inspect

from packages.contracts.records import (
    CapabilityProfile,
    CapabilitySupportState,
    ContractError,
    MethodProposal,
)


def make_capability_profile(
    *,
    support_state=CapabilitySupportState.UNKNOWN,
    qualification_evidence_references=(),
):
    return CapabilityProfile(
        tenant_id="tenant-1",
        project_id="project-1",
        profile_id="cap-1",
        profile_version="1",
        system_id="system-1",
        system_version_id="system-version-1",
        declared_scope="tool invocation",
        environment_family="agent",
        capability_kind="action",
        investigation_surface="behavioral",
        mvp_requirement="required",
        support_state=support_state,
        action_semantics=("invoke tool",),
        required_access=("tool-access",),
        schema_reference="schema-1",
        system_form_constraints=(),
        adapter_requirements=("adapter-1",),
        evaluator_requirements=("evaluator-1",),
        provider_constraints=(),
        target_component_constraints=(),
        compatibility_requirements=(),
        authorization_prerequisites=(
            "gateway-policy",
        ),
        qualification_evidence_references=(
            qualification_evidence_references
        ),
        known_limitations=(),
        invalidation_conditions=(),
        requalification_conditions=(),
        cost=("unit-cost",),
        limits=("one-at-a-time",),
    )


def make_method_proposal():
    return MethodProposal(
        tenant_id="tenant-1",
        project_id="project-1",
        proposal_id="proposal-1",
        proposal_version="1",
        goal_contract_id="goal-1",
        system_snapshot_id="snapshot-1",
        question=(
            "Which intervention best tests "
            "the leading explanation?"
        ),
        alternatives=(
            "baseline",
            "intervention",
        ),
        expected_outcomes=(
            "baseline remains unchanged",
        ),
        controls=("no-op control",),
        generated_program=(
            "run the declared comparison procedure"
        ),
        dependencies=("cap-1",),
        stopping_rule=(
            "stop when the evidence "
            "requirement is satisfied"
        ),
    )


def test_capability_support_state_values_are_explicit():
    assert {
        state.value for state in CapabilitySupportState
    } == {
        "qualified_supported",
        "unqualified",
        "unsupported",
        "incompatible",
        "blocked",
        "unknown",
    }


def test_capability_profile_has_governed_semantic_surface():
    assert {
        field.name
        for field in fields(CapabilityProfile)
    } == {
        "tenant_id",
        "project_id",
        "profile_id",
        "profile_version",
        "system_id",
        "system_version_id",
        "declared_scope",
        "environment_family",
        "capability_kind",
        "investigation_surface",
        "mvp_requirement",
        "support_state",
        "action_semantics",
        "required_access",
        "schema_reference",
        "system_form_constraints",
        "adapter_requirements",
        "evaluator_requirements",
        "provider_constraints",
        "target_component_constraints",
        "compatibility_requirements",
        "authorization_prerequisites",
        "qualification_evidence_references",
        "known_limitations",
        "invalidation_conditions",
        "requalification_conditions",
        "cost",
        "limits",
    }


def test_unqualified_profile_can_have_no_evidence():
    profile = make_capability_profile(
        support_state=CapabilitySupportState.UNQUALIFIED,
    )

    assert profile.qualification_evidence_references == ()


def test_qualified_supported_requires_evidence():
    try:
        make_capability_profile(
            support_state=(
                CapabilitySupportState.QUALIFIED_SUPPORTED
            ),
        )
    except ContractError:
        return

    raise AssertionError(
        "qualified_supported accepted without evidence"
    )


def test_qualified_supported_preserves_evidence():
    profile = make_capability_profile(
        support_state=(
            CapabilitySupportState.QUALIFIED_SUPPORTED
        ),
        qualification_evidence_references=("evidence-1",),
    )

    assert profile.qualification_evidence_references == (
        "evidence-1",
    )


def test_capability_profile_rejects_raw_support_state():
    try:
        make_capability_profile(
            support_state="qualified_supported",
            qualification_evidence_references="evidence-1",
        )
    except ContractError:
        return

    raise AssertionError(
        "raw support state string was accepted"
    )


def test_capability_profile_is_immutable():
    profile = make_capability_profile()

    try:
        profile.declared_scope = "changed"
    except FrozenInstanceError:
        return

    raise AssertionError(
        "CapabilityProfile is mutable"
    )


def test_identical_capability_profiles_have_identical_hashes():
    first = make_capability_profile()
    second = make_capability_profile()

    assert first.profile_sha256 == second.profile_sha256


def test_material_capability_change_changes_hash():
    first = make_capability_profile()
    payload = first.canonical_payload()
    payload["declared_scope"] = "different scope"

    second = CapabilityProfile(
        **{
            **payload,
            "support_state": first.support_state,
        }
    )

    assert first.profile_sha256 != second.profile_sha256


def test_capability_profile_has_no_authority_fields():
    names = {
        field.name
        for field in fields(CapabilityProfile)
    }

    assert "authorization" not in names
    assert "execution_authority" not in names
    assert "approval" not in names
    assert "can_execute" not in names


def test_capability_profile_has_no_execution_imports():
    source = inspect.getsource(CapabilityProfile)

    assert "subprocess" not in source
    assert "requests" not in source
    assert "httpx" not in source


def test_method_proposal_has_minimum_governed_surface():
    assert {
        field.name
        for field in fields(MethodProposal)
    } == {
        "tenant_id",
        "project_id",
        "proposal_id",
        "proposal_version",
        "goal_contract_id",
        "system_snapshot_id",
        "question",
        "alternatives",
        "expected_outcomes",
        "controls",
        "generated_program",
        "dependencies",
        "stopping_rule",
    }


def test_method_proposal_is_immutable():
    proposal = make_method_proposal()

    try:
        proposal.question = "changed"
    except FrozenInstanceError:
        return

    raise AssertionError(
        "MethodProposal is mutable"
    )


def test_identical_method_proposals_have_identical_hashes():
    first = make_method_proposal()
    second = make_method_proposal()

    assert first.proposal_sha256 == second.proposal_sha256


def test_material_method_change_changes_hash():
    first = make_method_proposal()
    payload = first.canonical_payload()
    payload["question"] = "A different question"

    second = MethodProposal(**payload)

    assert first.proposal_sha256 != second.proposal_sha256


def test_method_proposal_has_no_authority_or_outcome_fields():
    names = {
        field.name
        for field in fields(MethodProposal)
    }

    forbidden = {
        "authorization",
        "execution_authority",
        "approval",
        "verdict",
        "evaluation",
        "verification",
        "execution_record",
    }

    assert names.isdisjoint(forbidden)
