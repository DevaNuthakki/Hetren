from __future__ import annotations
import hashlib
from hvee.core.behavioral_structural_frontier_closure_planner_v2 import (
    StructuralPlannerVariant,
)
from copy import deepcopy
import hashlib
import inspect
import pytest
from hvee.core.behavioral_engine import BehavioralEngineOperation
from hvee.core.behavioral_structural_frontier_closure_planner_v2_engine import (
    build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle,
    build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle,
    verify_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle,
    verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle,
)
from hvee.core.behavioral_structural_frontier_closure_planner_v2_adapter import (
    build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.experiment_protocol import verify_experiment_protocol_bundle
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
)


def _sha(*parts: object) -> str:
    return hashlib.sha256(
        "|".join((str(part) for part in parts)).encode("utf-8")
    ).hexdigest()


def _targets(count: int) -> tuple[str, ...]:
    return tuple((_sha("target", index) for index in range(count)))


def _prior_observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
    targets: tuple[str, ...],
) -> FailureFamilyObservation:
    return FailureFamilyObservation(
        sequence=sequence,
        candidate_index=candidate_index,
        verdict=verdict,
        source=FailureFamilyObservationSource.EVALUATION,
        cost_units=1,
        scenario_sha256=targets[candidate_index],
        result_provenance_sha256=_sha(
            "prior-result", sequence, candidate_index, verdict.value
        ),
        observation_evidence_sha256=_sha(
            "prior-observation", sequence, candidate_index, verdict.value
        ),
        decision_evidence_sha256=_sha(
            "prior-decision", sequence, candidate_index, verdict.value
        ),
        counterexample_evidence_sha256=(
            _sha("prior-counterexample", sequence, candidate_index)
            if verdict is DecisionVerdict.FAIL
            else None
        ),
    )


def _adapter(
    *,
    candidate_values=(0, 1, 2, 3, 4),
    maximum_evaluations=None,
    observations=(),
    targets=None,
):
    candidate_values = tuple(candidate_values)
    if targets is None:
        targets = _targets(len(candidate_values))
    if maximum_evaluations is None:
        maximum_evaluations = len(candidate_values)
    return build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
        campaign_key="engine_test",
        campaign_version="1.0.0",
        subject_sha256=_sha("subject"),
        axis_key="synthetic_axis",
        axis_version="1.0.0",
        axis_unit=None,
        candidate_values=candidate_values,
        candidate_target_sha256s=targets,
        maximum_evaluations=maximum_evaluations,
        observations=observations,
        variant=StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE,
    )


def _return(adapter_bundle, *, verdict=DecisionVerdict.PASS, counterexample=None):
    if verdict is DecisionVerdict.FAIL and counterexample is None:
        counterexample = _sha("counterexample")
    return build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
        adapter_bundle=adapter_bundle,
        verdict=verdict,
        result_provenance_sha256=_sha("result", adapter_bundle.sha256, verdict.value),
        observation_evidence_sha256=_sha(
            "observation", adapter_bundle.sha256, verdict.value
        ),
        decision_evidence_sha256=_sha("decision", adapter_bundle.sha256, verdict.value),
        counterexample_evidence_sha256=counterexample,
        actual_cost_units=1,
    )


def test_observation_return_binds_exact_planner_selected_candidate():
    adapter = _adapter()
    returned = _return(adapter)
    selected = adapter.payload["planner_decision"]["selected_candidate_index"]
    targets = adapter.payload["axis"]["candidate_target_sha256s"]
    assert returned.failure_family_observation.candidate_index == selected
    assert returned.failure_family_observation.scenario_sha256 == targets[selected]
    assert (
        returned.payload["proposal_sha256"]
        == returned.experiment_observation.proposal_sha256
    )


def test_observed_protocol_is_valid_and_contains_completed_observation():
    adapter = _adapter()
    returned = _return(adapter)
    observed = returned.observed_experiment_protocol
    assert verify_experiment_protocol_bundle(observed.payload, observed.sha256) is True
    assert observed.payload["observations"][0]["status"] == "completed"
    assert observed.payload["observations"][0]["outcome_key"] == "pass"


def test_fail_requires_counterexample_evidence():
    adapter = _adapter()
    with pytest.raises(HveeContractError):
        build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
            adapter_bundle=adapter,
            verdict=DecisionVerdict.FAIL,
            result_provenance_sha256=_sha("result"),
            observation_evidence_sha256=_sha("observation"),
            decision_evidence_sha256=_sha("decision"),
            counterexample_evidence_sha256=None,
            actual_cost_units=1,
        )


def test_pass_rejects_counterexample_evidence():
    adapter = _adapter()
    with pytest.raises(HveeContractError):
        _return(
            adapter, verdict=DecisionVerdict.PASS, counterexample=_sha("unexpected")
        )


def test_raw_string_verdict_fails_closed():
    adapter = _adapter()
    with pytest.raises(HveeContractError):
        build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
            adapter_bundle=adapter,
            verdict="pass",
            result_provenance_sha256=_sha("result"),
            observation_evidence_sha256=_sha("observation"),
            decision_evidence_sha256=_sha("decision"),
            counterexample_evidence_sha256=None,
            actual_cost_units=1,
        )


def test_non_unit_cost_fails_closed():
    adapter = _adapter()
    with pytest.raises(HveeContractError):
        build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
            adapter_bundle=adapter,
            verdict=DecisionVerdict.PASS,
            result_provenance_sha256=_sha("result"),
            observation_evidence_sha256=_sha("observation"),
            decision_evidence_sha256=_sha("decision"),
            counterexample_evidence_sha256=None,
            actual_cost_units=2,
        )


def test_observation_return_is_reverifiable():
    adapter = _adapter()
    returned = _return(adapter)
    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
            payload=returned.payload,
            expected_sha256=returned.sha256,
            adapter_bundle=adapter,
        )
        is True
    )


def test_observation_return_verifier_rejects_target_tamper():
    adapter = _adapter()
    returned = _return(adapter)
    payload = deepcopy(returned.payload)
    payload["failure_family_observation"]["scenario_sha256"] = _sha("tampered-target")
    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
            payload=payload, expected_sha256=returned.sha256, adapter_bundle=adapter
        )
        is False
    )


def test_observation_return_verifier_rejects_observed_protocol_tamper():
    adapter = _adapter()
    returned = _return(adapter)
    payload = deepcopy(returned.payload)
    payload["observed_experiment_protocol"]["observations"][0]["outcome_key"] = "fail"
    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
            payload=payload, expected_sha256=returned.sha256, adapter_bundle=adapter
        )
        is False
    )


def test_closed_loop_advances_exactly_one_observation():
    adapter = _adapter()
    returned = _return(adapter)
    step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=returned
    )
    transition = step.payload["state_transition"]
    assert transition["observation_count_before"] == 0
    assert transition["observation_count_after"] == 1
    assert len(step.advanced_adapter_bundle.payload["observations"]) == 1


def test_closed_loop_next_target_is_derived_from_advanced_planner():
    adapter = _adapter()
    returned = _return(adapter)
    step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=returned
    )
    advanced = step.advanced_adapter_bundle
    selected = advanced.payload["planner_decision"]["selected_candidate_index"]
    targets = advanced.payload["axis"]["candidate_target_sha256s"]
    assert step.payload["next_target_sha256"] == targets[selected]
    assert step.next_experiment_protocol is not None
    assert (
        step.next_experiment_protocol.payload["proposals"][0]["target_sha256"]
        == targets[selected]
    )


def test_budget_exhaustion_is_terminal_and_emits_no_protocol():
    adapter = _adapter(maximum_evaluations=1)
    returned = _return(adapter)
    step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=returned
    )
    assert step.payload["state_transition"]["status_after"] == "budget_exhausted"
    assert step.payload["state_transition"]["terminal"] is True
    assert step.next_experiment_protocol is None
    assert step.payload["next_target_sha256"] is None


def test_grid_exhaustion_is_terminal_and_emits_no_protocol():
    targets = _targets(2)
    adapter = _adapter(candidate_values=(0, 1), maximum_evaluations=2, targets=targets)
    first_return = _return(adapter, verdict=DecisionVerdict.PASS)
    first_step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=first_return
    )
    assert first_step.payload["state_transition"]["status_after"] == "ready"
    second_adapter = first_step.advanced_adapter_bundle
    second_return = _return(second_adapter, verdict=DecisionVerdict.FAIL)
    second_step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=second_adapter, observation_return_bundle=second_return
    )
    assert second_step.payload["state_transition"]["status_after"] == "grid_exhausted"
    assert second_step.payload["state_transition"]["terminal"] is True
    assert second_step.next_experiment_protocol is None


def test_closed_loop_step_is_reverifiable():
    adapter = _adapter()
    returned = _return(adapter)
    step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=returned
    )
    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
            payload=step.payload,
            expected_sha256=step.sha256,
            adapter_bundle=adapter,
            observation_return_bundle=returned,
            advanced_adapter_bundle=step.advanced_adapter_bundle,
            next_experiment_protocol=step.next_experiment_protocol,
        )
        is True
    )


def test_closed_loop_verifier_rejects_next_target_tamper():
    adapter = _adapter()
    returned = _return(adapter)
    step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=returned
    )
    payload = deepcopy(step.payload)
    payload["next_target_sha256"] = _sha("wrong-next-target")
    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
            payload=payload,
            expected_sha256=step.sha256,
            adapter_bundle=adapter,
            observation_return_bundle=returned,
            advanced_adapter_bundle=step.advanced_adapter_bundle,
            next_experiment_protocol=step.next_experiment_protocol,
        )
        is False
    )


def test_current_adapter_tamper_blocks_observation_return():
    adapter = _adapter()
    adapter.payload["planner_decision"]["selected_candidate_index"] = 0
    with pytest.raises(HveeContractError):
        _return(adapter)


def test_build_closed_loop_has_no_caller_next_target_parameter():
    parameters = inspect.signature(
        build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle
    ).parameters
    assert "next_target_sha256" not in parameters
    assert set(parameters) == {"adapter_bundle", "observation_return_bundle"}


def test_legacy_behavioral_operation_enum_remains_exactly_three_operations():
    assert {item.value for item in BehavioralEngineOperation} == {
        "adaptive_scenario_search",
        "minimal_counterexample_reduction",
        "neighborhood_generation",
    }


def test_new_engine_is_deterministic():
    adapter = _adapter()
    first_return = _return(adapter)
    second_return = _return(adapter)
    assert first_return.payload == second_return.payload
    assert first_return.sha256 == second_return.sha256
    first_step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=first_return
    )
    second_step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=second_return
    )
    assert first_step.payload == second_step.payload
    assert first_step.sha256 == second_step.sha256


def test_evidence_boundary_remains_conservative():
    adapter = _adapter()
    returned = _return(adapter)
    step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=returned
    )
    boundary = step.payload["evidence_boundary"]
    assert boundary["next_target_binding_verified"] is True
    assert boundary["behavioral_performance_qualified"] is False
    assert boundary["execution_evidence_independently_verified"] is False
    assert boundary["internal_engine_used"] is False
    assert boundary["production_qualified"] is False
    assert boundary["release_decision_issued"] is False


def test_new_engine_payload_contains_no_raw_content_fields():
    adapter = _adapter()
    returned = _return(adapter)
    step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=returned
    )
    combined = (repr(returned.payload) + repr(step.payload)).lower()
    for forbidden in (
        "raw_audio",
        "raw_text",
        "transcript_text",
        "prompt_text",
        "customer_content",
        "model_weights",
    ):
        assert forbidden not in combined


@pytest.mark.parametrize("variant", tuple(StructuralPlannerVariant))
def test_v2_variant_identity_survives_closed_loop_engine_step(variant):
    candidate_values = tuple((float(index) for index in range(7)))
    targets = tuple(
        (
            hashlib.sha256(
                ("v2-engine-variant-target-" + str(index)).encode("utf-8")
            ).hexdigest()
            for index in range(7)
        )
    )
    subject = hashlib.sha256(b"v2-engine-variant-subject").hexdigest()
    adapter = build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
        campaign_key="hetren.v2.engine.variant",
        campaign_version="1.0.0",
        subject_sha256=subject,
        axis_key="synthetic.index",
        axis_version="1.0.0",
        axis_unit="index",
        candidate_values=candidate_values,
        candidate_target_sha256s=targets,
        maximum_evaluations=7,
        observations=(),
        variant=variant,
    )
    returned = build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
        adapter_bundle=adapter,
        verdict=DecisionVerdict.PASS,
        result_provenance_sha256=hashlib.sha256(b"v2-engine-result").hexdigest(),
        observation_evidence_sha256=hashlib.sha256(
            b"v2-engine-observation"
        ).hexdigest(),
        decision_evidence_sha256=hashlib.sha256(b"v2-engine-decision").hexdigest(),
        counterexample_evidence_sha256=None,
        actual_cost_units=1,
    )
    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
            payload=returned.payload,
            expected_sha256=returned.sha256,
            adapter_bundle=adapter,
        )
        is True
    )
    step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
        adapter_bundle=adapter, observation_return_bundle=returned
    )
    assert step.advanced_adapter_bundle.payload["adapter"]["variant"] == variant.value
    assert step.advanced_adapter_bundle.payload["planner"]["variant"] == variant.value
    if step.next_experiment_protocol is not None:
        proposal = step.next_experiment_protocol.payload["proposals"][0]
        assert proposal["parameters"]["variant"] == variant.value
    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
            payload=step.payload,
            expected_sha256=step.sha256,
            adapter_bundle=adapter,
            observation_return_bundle=returned,
            advanced_adapter_bundle=step.advanced_adapter_bundle,
            next_experiment_protocol=step.next_experiment_protocol,
        )
        is True
    )
