from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError

import pytest

from hvee.core.ai_change_set import (
    AI_CHANGE_SET_KEY,
    AI_CHANGE_SET_SCHEMA_VERSION,
    AI_CHANGE_SET_VERSION,
    AIChangeComponent,
    AIChangeKind,
    AIChangeRiskTier,
    AIChangeSetDefinition,
    build_ai_change_set,
    calculate_ai_change_set_sha256,
    verify_ai_change_set,
)
from hvee.core.contracts import HveeContractError


def _digest(value: str) -> str:
    return (value * 64)[:64]


def _definition() -> AIChangeSetDefinition:
    return AIChangeSetDefinition(
        change_set_key="hetren.test.model-substitution",
        change_set_version="1.0.0",
        baseline_system_key="hetren.test.baseline",
        candidate_system_key="hetren.test.candidate",
        risk_tier=AIChangeRiskTier.HIGH,
        purpose="Exercise the domain-neutral change identity.",
        components=(
            AIChangeComponent(
                kind=AIChangeKind.MODEL,
                component_key="model.primary",
                baseline_identity_sha256=_digest("a"),
                candidate_identity_sha256=_digest("b"),
                declared_behavior_impacts=(
                    "behavior.accuracy",
                    "behavior.robustness",
                ),
            ),
        ),
        declared_unknowns=(
            "unknown.cross-host",
            "unknown.future-distribution",
        ),
    )


def test_change_set_is_deterministic_and_content_addressed():
    first = build_ai_change_set(_definition())
    second = build_ai_change_set(_definition())

    assert first == second
    assert first.sha256 == calculate_ai_change_set_sha256(first.payload)
    assert verify_ai_change_set(
        payload=first.payload,
        expected_sha256=first.sha256,
        definition=_definition(),
    )


def test_change_set_schema_and_non_authority_are_explicit():
    bundle = build_ai_change_set(_definition())

    assert bundle.payload["schema_version"] == AI_CHANGE_SET_SCHEMA_VERSION
    assert bundle.payload["artifact"] == {
        "key": AI_CHANGE_SET_KEY,
        "version": AI_CHANGE_SET_VERSION,
        "type": "ai_change_set",
    }
    assert bundle.payload["evidence_boundary"] == {
        "impact_predicted": False,
        "experiments_selected": False,
        "systems_executed": False,
        "outcomes_observed": False,
        "release_decision_issued": False,
        "production_authority": False,
    }


def test_change_set_preserves_before_and_after_component_identities():
    component = build_ai_change_set(_definition()).payload["components"][0]

    assert component["kind"] == "model"
    assert component["baseline_identity_sha256"] == _digest("a")
    assert component["candidate_identity_sha256"] == _digest("b")
    assert component["declared_behavior_impacts"] == [
        "behavior.accuracy",
        "behavior.robustness",
    ]


def test_change_set_rejects_equal_component_identities():
    with pytest.raises(
        HveeContractError,
        match="identities must differ",
    ):
        AIChangeComponent(
            kind=AIChangeKind.MODEL,
            component_key="model.primary",
            baseline_identity_sha256=_digest("a"),
            candidate_identity_sha256=_digest("a"),
            declared_behavior_impacts=("behavior.accuracy",),
        )


def test_change_set_requires_canonical_component_order():
    first = AIChangeComponent(
        kind=AIChangeKind.MODEL,
        component_key="model.zeta",
        baseline_identity_sha256=_digest("a"),
        candidate_identity_sha256=_digest("b"),
        declared_behavior_impacts=("behavior.accuracy",),
    )
    second = AIChangeComponent(
        kind=AIChangeKind.RUNTIME,
        component_key="environment.alpha",
        baseline_identity_sha256=_digest("c"),
        candidate_identity_sha256=_digest("d"),
        declared_behavior_impacts=("behavior.latency",),
    )

    with pytest.raises(HveeContractError, match="ordered"):
        AIChangeSetDefinition(
            change_set_key="hetren.test.multi-change",
            change_set_version="1.0.0",
            baseline_system_key="hetren.test.baseline",
            candidate_system_key="hetren.test.candidate",
            risk_tier=AIChangeRiskTier.HIGH,
            purpose="Reject nondeterministic ordering.",
            components=(first, second),
            declared_unknowns=("unknown.future",),
        )


def test_change_set_rejects_unordered_or_duplicate_behavior_impacts():
    with pytest.raises(HveeContractError, match="lexical order"):
        AIChangeComponent(
            kind=AIChangeKind.MODEL,
            component_key="model.primary",
            baseline_identity_sha256=_digest("a"),
            candidate_identity_sha256=_digest("b"),
            declared_behavior_impacts=(
                "behavior.robustness",
                "behavior.accuracy",
            ),
        )


def test_change_set_verifier_rejects_rehashed_tampering():
    bundle = build_ai_change_set(_definition())
    altered = copy.deepcopy(bundle.payload)
    altered["evidence_boundary"]["release_decision_issued"] = True

    assert not verify_ai_change_set(
        payload=altered,
        expected_sha256=calculate_ai_change_set_sha256(altered),
        definition=_definition(),
    )


def test_change_set_definition_is_frozen():
    definition = _definition()

    with pytest.raises(FrozenInstanceError):
        definition.purpose = "changed"
