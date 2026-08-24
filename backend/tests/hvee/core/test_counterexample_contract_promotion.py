from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.counterexample_contract_promotion import (
    COUNTEREXAMPLE_CONTRACT_PROMOTION_SCHEMA_VERSION,
    COUNTEREXAMPLE_CONTRACT_PROPOSAL_SCHEMA_VERSION,
    ContractPromotionApproval,
    PromotionReviewDecision,
    PromotionReviewerKind,
    RegressionContractDefinition,
    build_counterexample_contract_promotion_bundle,
    build_counterexample_contract_proposal_bundle,
    calculate_contract_promotion_approval_sha256,
    calculate_counterexample_contract_promotion_sha256,
    calculate_counterexample_contract_proposal_sha256,
    calculate_regression_contract_specification_sha256,
    verify_counterexample_contract_promotion_bundle,
    verify_counterexample_contract_proposal_bundle,
)
from hvee.core.counterexample_evidence import (
    CounterexampleFailure,
    build_counterexample_evidence_bundle,
)
from hvee.core.decision import DecisionVerdict
from hvee.core.minimal_counterexample_reduction import (
    CounterexampleReductionObservation,
    CounterexampleReductionUnit,
    build_minimal_counterexample_reduction_bundle,
)
from hvee.core.neighborhood_generation import (
    NeighborhoodCandidate,
    NeighborhoodMutationDirection,
    NeighborhoodObservation,
    build_neighborhood_generation_bundle,
)


def _sha(character: str) -> str:
    return character * 64


def _failure(
    *,
    key: str = "asr.numeric-fidelity",
    reason_code: str = "required-token-missing",
) -> CounterexampleFailure:
    return CounterexampleFailure(
        key=key,
        version="1.0.0",
        reason_code=reason_code,
        metric_key="asr.missing-numeric-token-count",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.numeric-preservation",
        evaluator_version="1.0.0",
    )


def _counterexample(
    *,
    evaluation_type: str = "asr",
    failures: tuple[CounterexampleFailure, ...] | None = None,
):
    return build_counterexample_evidence_bundle(
        evaluation_type=evaluation_type,
        scenario_key="hetren.asr.minimized-noise-case",
        scenario_version="1.0.0",
        case_id="account-number-01",
        parameters={
            "noise_kind": "babble",
            "snr_db": 4.0,
        },
        result_provenance_sha256=_sha("a"),
        observation_evidence_sha256=_sha("b"),
        decision_evidence_sha256=_sha("c"),
        failures=failures or (_failure(),),
    )


def _unit(
    key: str,
    character: str,
) -> CounterexampleReductionUnit:
    return CounterexampleReductionUnit(
        key=key,
        version="1.0.0",
        content_sha256=_sha(character),
    )


def _reduction_observation(
    *,
    sequence: int,
    removed_unit_index: int,
    verdict: DecisionVerdict,
    scenario_sha256: str,
    counterexample_sha256: str | None = None,
) -> CounterexampleReductionObservation:
    return CounterexampleReductionObservation(
        sequence=sequence,
        removed_unit_index=removed_unit_index,
        scenario_sha256=scenario_sha256,
        verdict=verdict,
        result_provenance_sha256=_sha("a"),
        observation_evidence_sha256=_sha("b"),
        decision_evidence_sha256=_sha("c"),
        counterexample_evidence_sha256=counterexample_sha256,
    )


def _terminal_reduction_observations(counterexample):
    return (
        _reduction_observation(
            sequence=1,
            removed_unit_index=0,
            verdict=DecisionVerdict.PASS,
            scenario_sha256=_sha("1"),
        ),
        _reduction_observation(
            sequence=2,
            removed_unit_index=1,
            verdict=DecisionVerdict.FAIL,
            scenario_sha256=counterexample.scenario_sha256,
            counterexample_sha256=counterexample.sha256,
        ),
        _reduction_observation(
            sequence=3,
            removed_unit_index=0,
            verdict=DecisionVerdict.PASS,
            scenario_sha256=_sha("3"),
        ),
        _reduction_observation(
            sequence=4,
            removed_unit_index=2,
            verdict=DecisionVerdict.PASS,
            scenario_sha256=_sha("4"),
        ),
    )


def _reduction(
    counterexample,
    *,
    evaluation_type: str = "asr",
    observations=None,
):
    return build_minimal_counterexample_reduction_bundle(
        evaluation_type=evaluation_type,
        reduction_key="hetren.asr.minimal-counterexample",
        reduction_version="1.0.0",
        source_scenario_sha256=_sha("f"),
        source_counterexample_evidence_sha256=_sha("e"),
        units=(
            _unit("segment-000", "5"),
            _unit("segment-001", "6"),
            _unit("segment-002", "7"),
        ),
        maximum_observations=6,
        observations=(
            _terminal_reduction_observations(counterexample)
            if observations is None
            else observations
        ),
    )


def _candidate(
    *,
    key: str,
    dimension_key: str,
    direction: NeighborhoodMutationDirection,
    character: str,
) -> NeighborhoodCandidate:
    return NeighborhoodCandidate(
        key=key,
        version="1.0.0",
        dimension_key=dimension_key,
        generator_key="hetren.asr.local-mutation",
        generator_version="1.0.0",
        direction=direction,
        ordinal_distance=1,
        specification_sha256=_sha(character),
    )


def _candidates():
    return (
        _candidate(
            key="snr-lower-01",
            dimension_key="snr-db",
            direction=NeighborhoodMutationDirection.LOWER,
            character="8",
        ),
        _candidate(
            key="snr-upper-01",
            dimension_key="snr-db",
            direction=NeighborhoodMutationDirection.UPPER,
            character="9",
        ),
    )


def _neighborhood_observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
    character: str,
) -> NeighborhoodObservation:
    return NeighborhoodObservation(
        sequence=sequence,
        candidate_index=candidate_index,
        scenario_sha256=_sha(character),
        verdict=verdict,
        result_provenance_sha256=_sha("a"),
        observation_evidence_sha256=_sha("b"),
        decision_evidence_sha256=_sha("c"),
        counterexample_evidence_sha256=(
            _sha("d")
            if verdict == DecisionVerdict.FAIL
            else None
        ),
    )


def _terminal_neighborhood_observations():
    return (
        _neighborhood_observation(
            sequence=1,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
            character="5",
        ),
        _neighborhood_observation(
            sequence=2,
            candidate_index=1,
            verdict=DecisionVerdict.FAIL,
            character="6",
        ),
    )


def _neighborhood(
    counterexample,
    reduction,
    *,
    evaluation_type: str = "asr",
    maximum_observations: int = 2,
    observations=None,
):
    return build_neighborhood_generation_bundle(
        evaluation_type=evaluation_type,
        neighborhood_key="hetren.asr.local-neighborhood",
        neighborhood_version="1.0.0",
        source_scenario_sha256=counterexample.scenario_sha256,
        source_counterexample_evidence_sha256=(
            counterexample.sha256
        ),
        source_minimal_reduction_sha256=reduction.sha256,
        candidates=_candidates(),
        maximum_observations=maximum_observations,
        observations=(
            _terminal_neighborhood_observations()
            if observations is None
            else observations
        ),
    )


def _definition() -> RegressionContractDefinition:
    return RegressionContractDefinition(
        key="hetren.asr.account-number-regression",
        version="1.0.0",
        suite_key="hetren.asr.regression-suite",
        suite_version="1.0.0",
    )


def _source_chain(
    *,
    counterexample=None,
    reduction=None,
    neighborhood=None,
):
    selected_counterexample = counterexample or _counterexample()
    selected_reduction = reduction or _reduction(
        selected_counterexample
    )
    selected_neighborhood = neighborhood or _neighborhood(
        selected_counterexample,
        selected_reduction,
    )
    return (
        selected_counterexample,
        selected_reduction,
        selected_neighborhood,
    )


def _proposal(
    *,
    definition=None,
    counterexample=None,
    reduction=None,
    neighborhood=None,
):
    counterexample, reduction, neighborhood = _source_chain(
        counterexample=counterexample,
        reduction=reduction,
        neighborhood=neighborhood,
    )
    return build_counterexample_contract_proposal_bundle(
        definition=definition or _definition(),
        source_counterexample_payload=counterexample.payload,
        source_counterexample_sha256=counterexample.sha256,
        source_minimal_reduction_payload=reduction.payload,
        source_minimal_reduction_sha256=reduction.sha256,
        source_neighborhood_payload=neighborhood.payload,
        source_neighborhood_sha256=neighborhood.sha256,
    )


def _approval(
    proposal_sha256: str,
    *,
    decision: PromotionReviewDecision = (
        PromotionReviewDecision.APPROVED
    ),
    approval_evidence_sha256: str | None = None,
) -> ContractPromotionApproval:
    return ContractPromotionApproval(
        proposal_sha256=proposal_sha256,
        reviewer_key="reviewer-001",
        reviewer_role_key="reliability-owner",
        reviewer_kind=PromotionReviewerKind.HUMAN,
        review_policy_key="hetren.contract-promotion-review",
        review_policy_version="1.0.0",
        decision=decision,
        rationale_code="verified-regression-value",
        approval_evidence_sha256=(
            approval_evidence_sha256 or _sha("9")
        ),
    )


def _promotion():
    proposal = _proposal()
    return build_counterexample_contract_promotion_bundle(
        proposal_payload=proposal.payload,
        expected_proposal_sha256=proposal.sha256,
        approval=_approval(proposal.sha256),
    )


def test_contract_definition_is_frozen():
    definition = _definition()

    with pytest.raises(FrozenInstanceError):
        definition.key = "changed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("key", "Bad Contract"),
        ("version", " 1.0.0"),
        ("suite_key", "Bad Suite"),
        ("suite_version", ""),
    ],
)
def test_contract_definition_rejects_noncanonical_identity(
    field,
    value,
):
    values = {
        "key": "hetren.asr.account-number-regression",
        "version": "1.0.0",
        "suite_key": "hetren.asr.regression-suite",
        "suite_version": "1.0.0",
    }
    values[field] = value

    with pytest.raises(HveeContractError):
        RegressionContractDefinition(**values)


def test_approval_is_frozen():
    approval = _approval(_sha("1"))

    with pytest.raises(FrozenInstanceError):
        approval.reviewer_key = "changed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("proposal_sha256", "bad"),
        ("reviewer_key", "Reviewer 1"),
        ("reviewer_role_key", "Reliability Owner"),
        ("review_policy_key", "Bad Policy"),
        ("review_policy_version", " 1.0.0"),
        ("rationale_code", "Human words"),
        ("approval_evidence_sha256", "BAD"),
    ],
)
def test_approval_rejects_noncanonical_fields(field, value):
    values = {
        "proposal_sha256": _sha("1"),
        "reviewer_key": "reviewer-001",
        "reviewer_role_key": "reliability-owner",
        "reviewer_kind": PromotionReviewerKind.HUMAN,
        "review_policy_key": "hetren.contract-promotion-review",
        "review_policy_version": "1.0.0",
        "decision": PromotionReviewDecision.APPROVED,
        "rationale_code": "verified-regression-value",
        "approval_evidence_sha256": _sha("2"),
    }
    values[field] = value

    with pytest.raises(HveeContractError):
        ContractPromotionApproval(**values)


def test_approval_requires_canonical_reviewer_kind():
    with pytest.raises(HveeContractError, match="reviewer kind"):
        ContractPromotionApproval(
            proposal_sha256=_sha("1"),
            reviewer_key="reviewer-001",
            reviewer_role_key="reliability-owner",
            reviewer_kind="human",
            review_policy_key="hetren.contract-promotion-review",
            review_policy_version="1.0.0",
            decision=PromotionReviewDecision.APPROVED,
            rationale_code="verified-regression-value",
            approval_evidence_sha256=_sha("2"),
        )


def test_governance_body_can_record_explicit_approval():
    proposal = _proposal()
    approval = ContractPromotionApproval(
        proposal_sha256=proposal.sha256,
        reviewer_key="asr-reliability-council",
        reviewer_role_key="contract-governance",
        reviewer_kind=PromotionReviewerKind.GOVERNANCE_BODY,
        review_policy_key="hetren.contract-promotion-review",
        review_policy_version="1.0.0",
        decision=PromotionReviewDecision.APPROVED,
        rationale_code="verified-regression-value",
        approval_evidence_sha256=_sha("2"),
    )

    promotion = build_counterexample_contract_promotion_bundle(
        proposal_payload=proposal.payload,
        expected_proposal_sha256=proposal.sha256,
        approval=approval,
    )

    assert promotion.payload["approval"]["reviewer"]["kind"] == (
        "governance_body"
    )


def test_builds_verified_awaiting_approval_proposal():
    proposal = _proposal()

    assert proposal.payload["schema_version"] == (
        COUNTEREXAMPLE_CONTRACT_PROPOSAL_SCHEMA_VERSION
    )
    assert proposal.payload["type"] == (
        "counterexample_contract_promotion_proposal"
    )
    assert proposal.payload["contract"]["status"] == (
        "awaiting_approval"
    )
    assert proposal.payload["promotion"] == {
        "status": "awaiting_approval",
        "explicit_approval_required": True,
        "automatic_promotion_allowed": False,
    }
    assert verify_counterexample_contract_proposal_bundle(
        payload=proposal.payload,
        expected_sha256=proposal.sha256,
    )


def test_proposal_contracts_exact_minimized_scenario():
    counterexample, reduction, neighborhood = _source_chain()
    proposal = _proposal(
        counterexample=counterexample,
        reduction=reduction,
        neighborhood=neighborhood,
    )

    assert proposal.payload["contract"]["scenario"] == {
        "scope": "exact_minimized_scenario",
        "sha256": counterexample.scenario_sha256,
    }
    assert reduction.payload["outcome"][
        "current_scenario_sha256"
    ] == counterexample.scenario_sha256


def test_proposal_derives_forbidden_failure_fingerprints():
    proposal = _proposal()
    expectation = proposal.payload["contract"]["expectation"]

    assert expectation["decision_verdict"] == "pass"
    assert expectation["forbidden_failure_fingerprints"] == [
        {
            "key": "asr.numeric-fidelity",
            "version": "1.0.0",
            "reason_code": "required-token-missing",
            "metric": {
                "key": "asr.missing-numeric-token-count",
                "version": "1.0.0",
            },
            "evaluator": {
                "key": "hetren.asr.numeric-preservation",
                "version": "1.0.0",
            },
        }
    ]


def test_proposal_records_verified_source_chain():
    counterexample, reduction, neighborhood = _source_chain()
    proposal = _proposal(
        counterexample=counterexample,
        reduction=reduction,
        neighborhood=neighborhood,
    )
    sources = proposal.payload["source_evidence"]

    assert sources["counterexample"] == {
        "sha256": counterexample.sha256,
        "verified": True,
    }
    assert sources["minimal_counterexample_reduction"] == {
        "sha256": reduction.sha256,
        "status": "one_minimal",
        "verified": True,
    }
    assert sources["neighborhood_generation"]["sha256"] == (
        neighborhood.sha256
    )
    assert sources["neighborhood_generation"]["status"] == (
        "complete"
    )
    assert sources["neighborhood_generation"]["verified"] is True


def test_proposal_records_neighborhood_outcome_without_inference():
    proposal = _proposal()
    neighborhood = proposal.payload["source_evidence"][
        "neighborhood_generation"
    ]

    assert neighborhood["planned_candidate_count"] == 2
    assert neighborhood["passing_candidate_count"] == 1
    assert neighborhood["failing_candidate_count"] == 1
    assert neighborhood["mixed_observed_verdicts"] is True


def test_contract_specification_digest_is_reproducible():
    proposal = _proposal()
    contract = deepcopy(proposal.payload["contract"])
    stored = contract.pop("specification_sha256")

    assert stored == proposal.contract_specification_sha256
    assert stored == calculate_regression_contract_specification_sha256(
        contract
    )


def test_proposal_is_deterministic_for_same_source_chain():
    first = _proposal()
    second = _proposal()

    assert first == second


def test_proposal_canonicalizes_failure_fingerprint_order():
    first = _failure()
    second = _failure(
        key="asr.exact-match",
        reason_code="normalized-mismatch",
    )
    counterexample = _counterexample(failures=(first, second))
    reduction = _reduction(counterexample)
    neighborhood = _neighborhood(counterexample, reduction)
    proposal = _proposal(
        counterexample=counterexample,
        reduction=reduction,
        neighborhood=neighborhood,
    )
    keys = [
        failure["key"]
        for failure in proposal.payload["contract"]["expectation"][
            "forbidden_failure_fingerprints"
        ]
    ]

    assert keys == ["asr.exact-match", "asr.numeric-fidelity"]


def test_proposal_detaches_mutable_source_payloads():
    counterexample, reduction, neighborhood = _source_chain()
    proposal = _proposal(
        counterexample=counterexample,
        reduction=reduction,
        neighborhood=neighborhood,
    )

    counterexample.payload["scenario"]["case_id"] = "changed"
    neighborhood.payload["outcome"]["mixed_observed_verdicts"] = False

    assert proposal.payload["contract"]["scenario"]["sha256"] != (
        "changed"
    )
    assert proposal.payload["source_evidence"][
        "neighborhood_generation"
    ]["mixed_observed_verdicts"] is True


@pytest.mark.parametrize(
    "source_name",
    ["counterexample", "reduction", "neighborhood"],
)
def test_proposal_rejects_tampered_source_evidence(source_name):
    counterexample, reduction, neighborhood = _source_chain()
    selected = {
        "counterexample": counterexample,
        "reduction": reduction,
        "neighborhood": neighborhood,
    }[source_name]
    selected.payload["tampered"] = True

    with pytest.raises(HveeContractError, match="must verify"):
        _proposal(
            counterexample=counterexample,
            reduction=reduction,
            neighborhood=neighborhood,
        )


@pytest.mark.parametrize(
    "source_name",
    ["counterexample", "reduction", "neighborhood"],
)
def test_proposal_rejects_wrong_source_digest(source_name):
    counterexample, reduction, neighborhood = _source_chain()
    values = {
        "definition": _definition(),
        "source_counterexample_payload": counterexample.payload,
        "source_counterexample_sha256": counterexample.sha256,
        "source_minimal_reduction_payload": reduction.payload,
        "source_minimal_reduction_sha256": reduction.sha256,
        "source_neighborhood_payload": neighborhood.payload,
        "source_neighborhood_sha256": neighborhood.sha256,
    }
    digest_field = {
        "counterexample": "source_counterexample_sha256",
        "reduction": "source_minimal_reduction_sha256",
        "neighborhood": "source_neighborhood_sha256",
    }[source_name]
    values[digest_field] = _sha("0")

    with pytest.raises(HveeContractError, match="must verify"):
        build_counterexample_contract_proposal_bundle(**values)


def test_proposal_rejects_non_terminal_reduction():
    counterexample = _counterexample()
    reduction = _reduction(counterexample, observations=())
    neighborhood = _neighborhood(counterexample, reduction)

    with pytest.raises(HveeContractError, match="one-minimal"):
        _proposal(
            counterexample=counterexample,
            reduction=reduction,
            neighborhood=neighborhood,
        )


@pytest.mark.parametrize(
    ("maximum_observations", "observations"),
    [
        (2, ()),
        (1, _terminal_neighborhood_observations()[:1]),
    ],
)
def test_proposal_rejects_non_complete_neighborhood(
    maximum_observations,
    observations,
):
    counterexample = _counterexample()
    reduction = _reduction(counterexample)
    neighborhood = _neighborhood(
        counterexample,
        reduction,
        maximum_observations=maximum_observations,
        observations=observations,
    )

    with pytest.raises(HveeContractError, match="must be complete"):
        _proposal(
            counterexample=counterexample,
            reduction=reduction,
            neighborhood=neighborhood,
        )


def test_proposal_rejects_mismatched_evaluation_types():
    counterexample = _counterexample(evaluation_type="asr")
    reduction = _reduction(
        counterexample,
        evaluation_type="speech",
    )
    neighborhood = _neighborhood(
        counterexample,
        reduction,
        evaluation_type="speech",
    )

    with pytest.raises(HveeContractError, match="types must match"):
        _proposal(
            counterexample=counterexample,
            reduction=reduction,
            neighborhood=neighborhood,
        )


def test_proposal_rejects_non_terminal_counterexample_link():
    terminal_counterexample = _counterexample()
    other_counterexample = build_counterexample_evidence_bundle(
        evaluation_type="asr",
        scenario_key="hetren.asr.other-case",
        scenario_version="1.0.0",
        case_id="other-01",
        parameters={"snr_db": 3},
        result_provenance_sha256=_sha("a"),
        observation_evidence_sha256=_sha("b"),
        decision_evidence_sha256=_sha("c"),
        failures=(_failure(),),
    )
    reduction = _reduction(terminal_counterexample)
    neighborhood = _neighborhood(terminal_counterexample, reduction)

    with pytest.raises(HveeContractError, match="terminal minimized"):
        _proposal(
            counterexample=other_counterexample,
            reduction=reduction,
            neighborhood=neighborhood,
        )


def test_proposal_rejects_mismatched_neighborhood_chain():
    counterexample = _counterexample()
    reduction = _reduction(counterexample)
    other_reduction = _reduction(counterexample, observations=())
    neighborhood = _neighborhood(
        counterexample,
        other_reduction,
    )

    with pytest.raises(HveeContractError, match="chain does not match"):
        _proposal(
            counterexample=counterexample,
            reduction=reduction,
            neighborhood=neighborhood,
        )


def test_proposal_requires_canonical_definition_object():
    counterexample, reduction, neighborhood = _source_chain()

    with pytest.raises(HveeContractError, match="must be canonical"):
        build_counterexample_contract_proposal_bundle(
            definition={"key": "not-a-definition"},
            source_counterexample_payload=counterexample.payload,
            source_counterexample_sha256=counterexample.sha256,
            source_minimal_reduction_payload=reduction.payload,
            source_minimal_reduction_sha256=reduction.sha256,
            source_neighborhood_payload=neighborhood.payload,
            source_neighborhood_sha256=neighborhood.sha256,
        )


def test_proposal_verifier_rejects_wrong_digest():
    proposal = _proposal()

    assert not verify_counterexample_contract_proposal_bundle(
        payload=proposal.payload,
        expected_sha256=_sha("0"),
    )


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("contract", "version", "2.0.0"),
        ("promotion", "automatic_promotion_allowed", True),
        (
            "evidence_boundary",
            "qualification_authority",
            True,
        ),
    ],
)
def test_proposal_verifier_rejects_tampering(
    section,
    field,
    value,
):
    proposal = _proposal()
    tampered = deepcopy(proposal.payload)
    tampered[section][field] = value

    assert not verify_counterexample_contract_proposal_bundle(
        payload=tampered,
        expected_sha256=proposal.sha256,
    )


def test_proposal_verifier_rejects_recomputed_tampering():
    counterexample = _counterexample(
        failures=(
            _failure(),
            _failure(
                key="asr.exact-match",
                reason_code="normalized-mismatch",
            ),
        )
    )
    reduction = _reduction(counterexample)
    neighborhood = _neighborhood(counterexample, reduction)
    proposal = _proposal(
        counterexample=counterexample,
        reduction=reduction,
        neighborhood=neighborhood,
    )
    tampered = deepcopy(proposal.payload)
    tampered["contract"]["expectation"][
        "forbidden_failure_fingerprints"
    ].reverse()
    recomputed = calculate_counterexample_contract_proposal_sha256(
        tampered
    )

    assert not verify_counterexample_contract_proposal_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_proposal_verifier_rejects_extra_fields():
    proposal = _proposal()
    tampered = deepcopy(proposal.payload)
    tampered["automatic_release_authority"] = True
    recomputed = calculate_counterexample_contract_proposal_sha256(
        tampered
    )

    assert not verify_counterexample_contract_proposal_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("planned_candidate_count", 3),
        ("passing_candidate_count", 2),
        ("failing_candidate_count", 0),
        ("mixed_observed_verdicts", False),
    ],
)
def test_proposal_verifier_rejects_inconsistent_neighborhood_summary(
    field,
    value,
):
    proposal = _proposal()
    tampered = deepcopy(proposal.payload)
    tampered["source_evidence"]["neighborhood_generation"][
        field
    ] = value
    recomputed = calculate_counterexample_contract_proposal_sha256(
        tampered
    )

    assert not verify_counterexample_contract_proposal_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_proposal_evidence_boundary_is_explicit():
    boundary = _proposal().payload["evidence_boundary"]

    assert boundary == {
        "source_counterexample_verified": True,
        "source_one_minimal_reduction_verified": True,
        "source_complete_neighborhood_verified": True,
        "exact_minimized_scenario_scope": True,
        "explicit_approval_required": True,
        "human_or_governance_review_required": True,
        "approval_recorded": False,
        "contract_promoted": False,
        "activation_mode": "none",
        "blocking_release_gate_enabled": False,
        "release_enforcement_eligible": False,
        "production_qualified": False,
        "certification_issued": False,
        "causal_explanation_claimed": False,
        "statistical_generalization_claimed": False,
        "raw_content_embedded": False,
        "qualification_authority": False,
    }


def test_builds_explicitly_approved_shadow_promotion():
    promotion = _promotion()

    assert promotion.payload["schema_version"] == (
        COUNTEREXAMPLE_CONTRACT_PROMOTION_SCHEMA_VERSION
    )
    assert promotion.payload["type"] == (
        "counterexample_contract_promotion"
    )
    assert promotion.payload["promotion"] == {
        "status": "promoted_to_shadow",
        "contract_key": "hetren.asr.account-number-regression",
        "contract_version": "1.0.0",
        "contract_specification_sha256": (
            promotion.payload["proposal"]["payload"]["contract"]
            ["specification_sha256"]
        ),
        "activation_mode": "shadow",
    }
    assert verify_counterexample_contract_promotion_bundle(
        payload=promotion.payload,
        expected_sha256=promotion.sha256,
    )


def test_approval_digest_is_independently_reproducible():
    proposal = _proposal()
    approval = _approval(proposal.sha256)
    promotion = build_counterexample_contract_promotion_bundle(
        proposal_payload=proposal.payload,
        expected_proposal_sha256=proposal.sha256,
        approval=approval,
    )

    assert promotion.approval_sha256 == (
        calculate_contract_promotion_approval_sha256(approval)
    )
    assert promotion.payload["approval"]["sha256"] == (
        promotion.approval_sha256
    )


def test_promotion_embeds_and_binds_exact_proposal():
    proposal = _proposal()
    promotion = build_counterexample_contract_promotion_bundle(
        proposal_payload=proposal.payload,
        expected_proposal_sha256=proposal.sha256,
        approval=_approval(proposal.sha256),
    )

    assert promotion.payload["proposal"] == {
        "payload": proposal.payload,
        "sha256": proposal.sha256,
    }
    assert promotion.payload["approval"]["proposal_sha256"] == (
        proposal.sha256
    )


def test_rejected_review_cannot_promote_contract():
    proposal = _proposal()

    with pytest.raises(HveeContractError, match="rejected review"):
        build_counterexample_contract_promotion_bundle(
            proposal_payload=proposal.payload,
            expected_proposal_sha256=proposal.sha256,
            approval=_approval(
                proposal.sha256,
                decision=PromotionReviewDecision.REJECTED,
            ),
        )


def test_approval_must_bind_exact_proposal():
    proposal = _proposal()

    with pytest.raises(HveeContractError, match="exact contract"):
        build_counterexample_contract_promotion_bundle(
            proposal_payload=proposal.payload,
            expected_proposal_sha256=proposal.sha256,
            approval=_approval(_sha("0")),
        )


def test_approval_evidence_must_be_distinct_from_proposal():
    proposal = _proposal()

    with pytest.raises(HveeContractError, match="must be distinct"):
        build_counterexample_contract_promotion_bundle(
            proposal_payload=proposal.payload,
            expected_proposal_sha256=proposal.sha256,
            approval=_approval(
                proposal.sha256,
                approval_evidence_sha256=proposal.sha256,
            ),
        )


def test_tampered_proposal_cannot_be_promoted():
    proposal = _proposal()
    tampered = deepcopy(proposal.payload)
    tampered["contract"]["version"] = "2.0.0"

    with pytest.raises(HveeContractError, match="must verify"):
        build_counterexample_contract_promotion_bundle(
            proposal_payload=tampered,
            expected_proposal_sha256=proposal.sha256,
            approval=_approval(proposal.sha256),
        )


def test_wrong_trusted_proposal_digest_cannot_be_promoted():
    proposal = _proposal()

    with pytest.raises(HveeContractError, match="must verify"):
        build_counterexample_contract_promotion_bundle(
            proposal_payload=proposal.payload,
            expected_proposal_sha256=_sha("0"),
            approval=_approval(_sha("0")),
        )


def test_promotion_verifier_rejects_wrong_digest():
    promotion = _promotion()

    assert not verify_counterexample_contract_promotion_bundle(
        payload=promotion.payload,
        expected_sha256=_sha("0"),
    )


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("approval", "decision", "rejected"),
        ("promotion", "activation_mode", "blocking"),
        (
            "evidence_boundary",
            "release_enforcement_eligible",
            True,
        ),
    ],
)
def test_promotion_verifier_rejects_tampering(
    section,
    field,
    value,
):
    promotion = _promotion()
    tampered = deepcopy(promotion.payload)
    tampered[section][field] = value

    assert not verify_counterexample_contract_promotion_bundle(
        payload=tampered,
        expected_sha256=promotion.sha256,
    )


def test_promotion_verifier_rejects_embedded_proposal_tampering():
    promotion = _promotion()
    tampered = deepcopy(promotion.payload)
    tampered["proposal"]["payload"]["contract"]["version"] = (
        "2.0.0"
    )
    recomputed = calculate_counterexample_contract_promotion_sha256(
        tampered
    )

    assert not verify_counterexample_contract_promotion_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_promotion_verifier_rejects_recomputed_approval_tampering():
    promotion = _promotion()
    tampered = deepcopy(promotion.payload)
    tampered["approval"]["reviewer"]["key"] = "another-reviewer"
    recomputed = calculate_counterexample_contract_promotion_sha256(
        tampered
    )

    assert not verify_counterexample_contract_promotion_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_promotion_verifier_rejects_extra_fields():
    promotion = _promotion()
    tampered = deepcopy(promotion.payload)
    tampered["release_gate"] = "enabled"
    recomputed = calculate_counterexample_contract_promotion_sha256(
        tampered
    )

    assert not verify_counterexample_contract_promotion_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_promotion_evidence_boundary_is_explicit():
    boundary = _promotion().payload["evidence_boundary"]

    assert boundary == {
        "source_counterexample_verified": True,
        "source_one_minimal_reduction_verified": True,
        "source_complete_neighborhood_verified": True,
        "exact_minimized_scenario_scope": True,
        "explicit_approval_required": True,
        "human_or_governance_review_required": True,
        "human_or_governance_review_recorded": True,
        "approval_recorded": True,
        "contract_promoted": True,
        "activation_mode": "shadow",
        "blocking_release_gate_enabled": False,
        "release_enforcement_eligible": False,
        "production_qualified": False,
        "certification_issued": False,
        "causal_explanation_claimed": False,
        "statistical_generalization_claimed": False,
        "raw_content_embedded": False,
        "qualification_authority": False,
    }


@pytest.mark.parametrize(
    "builder",
    [_proposal, _promotion],
)
def test_evidence_excludes_raw_content_and_local_identity(builder):
    serialized = str(builder().payload).lower()

    for forbidden in (
        "evaluation_run_id",
        "result_id",
        "created_at",
        "reviewed_at",
        "reviewer_email",
        "audio_file_path",
        "reference_transcript",
        "generated_transcript",
        "raw_audio",
        "raw_mutation_value",
    ):
        assert forbidden not in serialized


def test_promotion_never_enables_release_or_qualification_authority():
    promotion = _promotion().payload
    boundary = promotion["evidence_boundary"]

    assert promotion["promotion"]["activation_mode"] == "shadow"
    assert boundary["blocking_release_gate_enabled"] is False
    assert boundary["release_enforcement_eligible"] is False
    assert boundary["production_qualified"] is False
    assert boundary["certification_issued"] is False
    assert boundary["qualification_authority"] is False
