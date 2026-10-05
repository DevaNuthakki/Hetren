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
