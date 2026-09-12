from __future__ import annotations
from hvee.core.behavioral_structural_frontier_closure_planner_v2 import (
    StructuralPlannerVariant,
)
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
from hvee.core.behavioral_structural_frontier_closure_planner_v2_adapter import (
    BehavioralStructuralFrontierClosurePlannerV2AdapterBundle,
    BehavioralStructuralFrontierClosurePlannerV2AdapterStatus,
    build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle,
    verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.experiment_protocol import (
    ExperimentDefinition,
    ExperimentEngineKind,
    ExperimentObservation,
    ExperimentObservationStatus,
    ExperimentProposal,
    ExperimentProtocolBundle,
    build_experiment_protocol_bundle,
    verify_experiment_protocol_bundle,
)
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
)

ENGINE_SCHEMA_VERSION = 1
OBSERVATION_RETURN_TYPE = (
    "behavioral_structural_frontier_closure_planner_v2_engine_observation_return"
)
CLOSED_LOOP_STEP_TYPE = (
    "behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step"
)
_SHA256_PATTERN = re.compile("^[0-9a-f]{64}$")


@dataclass(frozen=True)
class BehavioralStructuralFrontierClosurePlannerV2EngineObservationReturnBundle:
    payload: dict[str, object]
    experiment_observation: ExperimentObservation
    failure_family_observation: FailureFamilyObservation
    observed_experiment_protocol: ExperimentProtocolBundle
    sha256: str


@dataclass(frozen=True)
class BehavioralStructuralFrontierClosurePlannerV2EngineClosedLoopStepBundle:
    payload: dict[str, object]
    advanced_adapter_bundle: BehavioralStructuralFrontierClosurePlannerV2AdapterBundle
    next_experiment_protocol: ExperimentProtocolBundle | None
    sha256: str


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "multi-objective engine value is not canonically JSON serializable"
        ) from exc


def _calculate_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def calculate_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_sha256(
    payload: object,
) -> str:
    if not isinstance(payload, dict):
        raise HveeContractError(
            "multi-objective observation-return payload must be an object"
        )
    return _calculate_sha256(payload)


def calculate_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_sha256(
    payload: object,
) -> str:
    if not isinstance(payload, dict):
        raise HveeContractError("multi-objective closed-loop payload must be an object")
    return _calculate_sha256(payload)


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise HveeContractError(f"{field} must be a lowercase SHA-256")
    return value


def _require_strict_verdict(value: object) -> DecisionVerdict:
    if not isinstance(value, DecisionVerdict) or value not in (
        DecisionVerdict.PASS,
        DecisionVerdict.FAIL,
    ):
        raise HveeContractError("verdict must be strict DecisionVerdict PASS or FAIL")
    return value


def _require_unit_cost(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != 1:
        raise HveeContractError(
            "multi-objective engine observations cost exactly one unit"
        )
    return value


def _adapter_status(
    adapter_bundle: BehavioralStructuralFrontierClosurePlannerV2AdapterBundle,
) -> BehavioralStructuralFrontierClosurePlannerV2AdapterStatus:
    if not isinstance(
        adapter_bundle, BehavioralStructuralFrontierClosurePlannerV2AdapterBundle
    ):
        raise HveeContractError(
            "adapter_bundle must be BehavioralStructuralFrontierClosurePlannerV2AdapterBundle"
        )
    if not verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
        payload=adapter_bundle.payload, expected_sha256=adapter_bundle.sha256
    ):
        raise HveeContractError("multi-objective adapter bundle failed verification")
    try:
        status = BehavioralStructuralFrontierClosurePlannerV2AdapterStatus(
            adapter_bundle.payload["adapter"]["status"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HveeContractError("multi-objective adapter status is invalid") from exc
    return status


def _experiment_observation_payload(
    observation: ExperimentObservation,
) -> dict[str, object]:
    return {
        "proposal_sequence": observation.proposal_sequence,
        "proposal_sha256": observation.proposal_sha256,
        "status": observation.status.value,
        "outcome_key": observation.outcome_key,
        "actual_cost_units": observation.actual_cost_units,
        "result_evidence_sha256": observation.result_evidence_sha256,
        "evaluator_evidence_sha256": observation.evaluator_evidence_sha256,
    }


def _failure_family_observation_payload(
    observation: FailureFamilyObservation,
) -> dict[str, object]:
    return {
        "sequence": observation.sequence,
        "candidate_index": observation.candidate_index,
        "verdict": observation.verdict.value,
        "source": observation.source.value,
        "cost_units": observation.cost_units,
        "scenario_sha256": observation.scenario_sha256,
        "result_provenance_sha256": observation.result_provenance_sha256,
        "observation_evidence_sha256": observation.observation_evidence_sha256,
        "decision_evidence_sha256": observation.decision_evidence_sha256,
        "counterexample_evidence_sha256": observation.counterexample_evidence_sha256,
    }


def _failure_family_observation_from_payload(value: object) -> FailureFamilyObservation:
    expected_fields = {
        "sequence",
        "candidate_index",
        "verdict",
        "source",
        "cost_units",
        "scenario_sha256",
        "result_provenance_sha256",
        "observation_evidence_sha256",
        "decision_evidence_sha256",
        "counterexample_evidence_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise HveeContractError("stored multi-objective observation is invalid")
    try:
        verdict = DecisionVerdict(value["verdict"])
        source = FailureFamilyObservationSource(value["source"])
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "stored multi-objective observation enum is invalid"
        ) from exc
    return FailureFamilyObservation(
        sequence=value["sequence"],
        candidate_index=value["candidate_index"],
        verdict=verdict,
        source=source,
        cost_units=value["cost_units"],
        scenario_sha256=value["scenario_sha256"],
        result_provenance_sha256=value["result_provenance_sha256"],
        observation_evidence_sha256=value["observation_evidence_sha256"],
        decision_evidence_sha256=value["decision_evidence_sha256"],
        counterexample_evidence_sha256=value["counterexample_evidence_sha256"],
    )


def _protocol_components(
    protocol: ExperimentProtocolBundle,
) -> tuple[ExperimentDefinition, ExperimentProposal, str, str, str, int, int]:
    if not isinstance(protocol, ExperimentProtocolBundle):
        raise HveeContractError("experiment protocol must be ExperimentProtocolBundle")
    if not verify_experiment_protocol_bundle(protocol.payload, protocol.sha256):
        raise HveeContractError("experiment protocol failed verification")
    payload = protocol.payload
    try:
        definition_payload = payload["definition"]
        campaign_payload = payload["campaign"]
        budget_payload = payload["budget"]
        subject_sha256 = payload["subject_sha256"]
        proposals = payload["proposals"]
    except KeyError as exc:
        raise HveeContractError("experiment protocol surface is incomplete") from exc
    if (
        not isinstance(definition_payload, dict)
        or not isinstance(campaign_payload, dict)
        or (not isinstance(budget_payload, dict))
        or (not isinstance(proposals, list))
        or (len(proposals) != 1)
        or (not isinstance(proposals[0], dict))
    ):
        raise HveeContractError("experiment protocol surface is invalid")
    proposal_payload = proposals[0]
    try:
        definition = ExperimentDefinition(
            key=definition_payload["key"],
            version=definition_payload["version"],
            engine_kind=ExperimentEngineKind(definition_payload["engine_kind"]),
            operation_key=definition_payload["operation_key"],
            operation_version=definition_payload["operation_version"],
        )
        proposal = ExperimentProposal(
            sequence=proposal_payload["sequence"],
            proposal_key=proposal_payload["proposal_key"],
            target_sha256=proposal_payload["target_sha256"],
            parameters=deepcopy(proposal_payload["parameters"]),
            estimated_cost_units=proposal_payload["estimated_cost_units"],
            reason_code=proposal_payload["reason_code"],
            source_evidence_sha256=proposal_payload["source_evidence_sha256"],
        )
        campaign_key = campaign_payload["key"]
        campaign_version = campaign_payload["version"]
        maximum_experiments = budget_payload["maximum_experiments"]
        maximum_cost_units = budget_payload["maximum_cost_units"]
    except (KeyError, TypeError, ValueError) as exc:
        raise HveeContractError("experiment protocol components are invalid") from exc
    return (
        definition,
        proposal,
        campaign_key,
        campaign_version,
        subject_sha256,
        maximum_experiments,
        maximum_cost_units,
    )


def _ready_protocol(
    adapter_bundle: BehavioralStructuralFrontierClosurePlannerV2AdapterBundle,
) -> tuple[ExperimentProtocolBundle, dict[str, object], int]:
    status = _adapter_status(adapter_bundle)
    if status is not BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.READY:
        raise HveeContractError(
            "multi-objective observation return requires READY adapter state"
        )
    protocol = adapter_bundle.experiment_protocol
    if protocol is None:
        raise HveeContractError("READY adapter state requires an experiment protocol")
    if not verify_experiment_protocol_bundle(protocol.payload, protocol.sha256):
        raise HveeContractError("READY adapter experiment protocol failed verification")
    try:
        selected_candidate_index = adapter_bundle.payload["planner_decision"][
            "selected_candidate_index"
        ]
        targets = adapter_bundle.payload["axis"]["candidate_target_sha256s"]
        proposals = protocol.payload["proposals"]
    except KeyError as exc:
        raise HveeContractError("READY adapter surface is incomplete") from exc
    if isinstance(selected_candidate_index, bool) or not isinstance(
        selected_candidate_index, int
    ):
        raise HveeContractError("READY adapter selected candidate is invalid")
    if (
        not isinstance(targets, list)
        or selected_candidate_index < 0
        or selected_candidate_index >= len(targets)
    ):
        raise HveeContractError("READY adapter target surface is invalid")
    if (
        not isinstance(proposals, list)
        or len(proposals) != 1
        or (not isinstance(proposals[0], dict))
    ):
        raise HveeContractError("READY adapter proposal surface is invalid")
    proposal_payload = proposals[0]
    expected_target = targets[selected_candidate_index]
    if proposal_payload.get("target_sha256") != expected_target:
        raise HveeContractError(
            "READY adapter proposal target does not match planner-selected target"
        )
    return (protocol, proposal_payload, selected_candidate_index)


def build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
    *,
    adapter_bundle: BehavioralStructuralFrontierClosurePlannerV2AdapterBundle,
    verdict: DecisionVerdict,
    result_provenance_sha256: str,
    observation_evidence_sha256: str,
    decision_evidence_sha256: str,
    counterexample_evidence_sha256: str | None,
    actual_cost_units: int = 1,
) -> BehavioralStructuralFrontierClosurePlannerV2EngineObservationReturnBundle:
    normalized_verdict = _require_strict_verdict(verdict)
    normalized_cost = _require_unit_cost(actual_cost_units)
    normalized_result_sha = _require_sha256(
        result_provenance_sha256, field="result_provenance_sha256"
    )
    normalized_observation_sha = _require_sha256(
        observation_evidence_sha256, field="observation_evidence_sha256"
    )
    normalized_decision_sha = _require_sha256(
        decision_evidence_sha256, field="decision_evidence_sha256"
    )
    normalized_counterexample_sha = None
    if normalized_verdict is DecisionVerdict.FAIL:
        normalized_counterexample_sha = _require_sha256(
            counterexample_evidence_sha256, field="counterexample_evidence_sha256"
        )
    elif counterexample_evidence_sha256 is not None:
        raise HveeContractError(
            "PASS observation must not include counterexample evidence"
        )
    protocol, proposal_payload, selected_candidate_index = _ready_protocol(
        adapter_bundle
    )
    proposal_sha256 = _calculate_sha256(proposal_payload)
    target_sha256 = _require_sha256(
        proposal_payload.get("target_sha256"), field="proposal target_sha256"
    )
    try:
        evaluated_count = adapter_bundle.payload["budget"]["evaluated_count"]
        stored_observations = adapter_bundle.payload["observations"]
    except KeyError as exc:
        raise HveeContractError("adapter history surface is incomplete") from exc
    if (
        isinstance(evaluated_count, bool)
        or not isinstance(evaluated_count, int)
        or evaluated_count < 0
        or (not isinstance(stored_observations, list))
        or (len(stored_observations) != evaluated_count)
    ):
        raise HveeContractError("adapter observation history is invalid")
    sequence = evaluated_count + 1
    experiment_observation = ExperimentObservation(
        proposal_sequence=0,
        proposal_sha256=proposal_sha256,
        status=ExperimentObservationStatus.COMPLETED,
        outcome_key=normalized_verdict.value,
        actual_cost_units=normalized_cost,
        result_evidence_sha256=normalized_result_sha,
        evaluator_evidence_sha256=normalized_decision_sha,
    )
    failure_family_observation = FailureFamilyObservation(
        sequence=sequence,
        candidate_index=selected_candidate_index,
        verdict=normalized_verdict,
        source=FailureFamilyObservationSource.EVALUATION,
        cost_units=normalized_cost,
        scenario_sha256=target_sha256,
        result_provenance_sha256=normalized_result_sha,
        observation_evidence_sha256=normalized_observation_sha,
        decision_evidence_sha256=normalized_decision_sha,
        counterexample_evidence_sha256=normalized_counterexample_sha,
    )
    (
        definition,
        proposal,
        campaign_key,
        campaign_version,
        subject_sha256,
        maximum_experiments,
        maximum_cost_units,
    ) = _protocol_components(protocol)
    observed_protocol = build_experiment_protocol_bundle(
        definition=definition,
        campaign_key=campaign_key,
        campaign_version=campaign_version,
        subject_sha256=subject_sha256,
        maximum_experiments=maximum_experiments,
        maximum_cost_units=maximum_cost_units,
        proposals=[proposal],
        observations=[experiment_observation],
    )
    if not verify_experiment_protocol_bundle(
        observed_protocol.payload, observed_protocol.sha256
    ):
        raise HveeContractError(
            "observed multi-objective experiment protocol failed verification"
        )
    payload: dict[str, object] = {
        "schema_version": ENGINE_SCHEMA_VERSION,
        "type": OBSERVATION_RETURN_TYPE,
        "adapter_bundle_sha256": adapter_bundle.sha256,
        "experiment_protocol_sha256": protocol.sha256,
        "proposal_sha256": proposal_sha256,
        "experiment_observation": _experiment_observation_payload(
            experiment_observation
        ),
        "failure_family_observation": _failure_family_observation_payload(
            failure_family_observation
        ),
        "observed_experiment_protocol": deepcopy(observed_protocol.payload),
        "observed_experiment_protocol_sha256": observed_protocol.sha256,
        "evidence_boundary": {
            "adapter_verified": True,
            "experiment_protocol_verified": True,
            "proposal_binding_verified": True,
            "selected_candidate_binding_verified": True,
            "observed_protocol_verified": True,
            "execution_evidence_independently_verified": False,
            "planner_performance_qualified": False,
            "raw_content_persisted": False,
        },
    }
    payload = deepcopy(payload)
    return BehavioralStructuralFrontierClosurePlannerV2EngineObservationReturnBundle(
        payload=payload,
        experiment_observation=experiment_observation,
        failure_family_observation=failure_family_observation,
        observed_experiment_protocol=observed_protocol,
        sha256=calculate_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_sha256(
            payload
        ),
    )


def verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
    *,
    payload: object,
    expected_sha256: object,
    adapter_bundle: BehavioralStructuralFrontierClosurePlannerV2AdapterBundle,
) -> bool:
    try:
        normalized_expected_sha = _require_sha256(
            expected_sha256, field="expected_sha256"
        )
        if not isinstance(payload, dict):
            return False
        expected_fields = {
            "schema_version",
            "type",
            "adapter_bundle_sha256",
            "experiment_protocol_sha256",
            "proposal_sha256",
            "experiment_observation",
            "failure_family_observation",
            "observed_experiment_protocol",
            "observed_experiment_protocol_sha256",
            "evidence_boundary",
        }
        if set(payload) != expected_fields:
            return False
        if (
            payload["schema_version"] != ENGINE_SCHEMA_VERSION
            or payload["type"] != OBSERVATION_RETURN_TYPE
        ):
            return False
        failure_payload = payload["failure_family_observation"]
        if not isinstance(failure_payload, dict):
            return False
        verdict = DecisionVerdict(failure_payload["verdict"])
        rebuilt = build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
            adapter_bundle=adapter_bundle,
            verdict=verdict,
            result_provenance_sha256=failure_payload["result_provenance_sha256"],
            observation_evidence_sha256=failure_payload["observation_evidence_sha256"],
            decision_evidence_sha256=failure_payload["decision_evidence_sha256"],
            counterexample_evidence_sha256=failure_payload[
                "counterexample_evidence_sha256"
            ],
            actual_cost_units=failure_payload["cost_units"],
        )
        if rebuilt.payload != payload:
            return False
        if rebuilt.sha256 != normalized_expected_sha:
            return False
        observed_payload = payload["observed_experiment_protocol"]
        observed_sha = payload["observed_experiment_protocol_sha256"]
        if not verify_experiment_protocol_bundle(observed_payload, observed_sha):
            return False
        return True
    except (HveeContractError, KeyError, TypeError, ValueError):
        return False


def _rebuild_adapter_with_appended_observation(
    *,
    adapter_bundle: BehavioralStructuralFrontierClosurePlannerV2AdapterBundle,
    appended: FailureFamilyObservation,
) -> BehavioralStructuralFrontierClosurePlannerV2AdapterBundle:
    payload = adapter_bundle.payload
    try:
        adapter_section = payload["adapter"]
        axis = payload["axis"]
        budget = payload["budget"]
        observations_payload = payload["observations"]
    except KeyError as exc:
        raise HveeContractError("adapter rebuild surface is incomplete") from exc
    if (
        not isinstance(adapter_section, dict)
        or not isinstance(axis, dict)
        or (not isinstance(budget, dict))
        or (not isinstance(observations_payload, list))
    ):
        raise HveeContractError("adapter rebuild surface is invalid")
    prior_observations = tuple(
        (
            _failure_family_observation_from_payload(item)
            for item in observations_payload
        )
    )
    if appended.sequence != len(prior_observations) + 1:
        raise HveeContractError(
            "closed-loop advancement must append exactly one observation"
        )
    rebuilt = build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
        campaign_key=adapter_section["campaign_key"],
        campaign_version=adapter_section["campaign_version"],
        subject_sha256=adapter_section["subject_sha256"],
        axis_key=axis["key"],
        axis_version=axis["version"],
        axis_unit=axis["unit"],
        candidate_values=axis["candidate_values"],
        candidate_target_sha256s=axis["candidate_target_sha256s"],
        maximum_evaluations=budget["maximum_evaluations"],
        observations=prior_observations + (appended,),
        variant=StructuralPlannerVariant(adapter_bundle.payload["adapter"]["variant"]),
    )
    if not verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
        payload=rebuilt.payload, expected_sha256=rebuilt.sha256
    ):
        raise HveeContractError("advanced multi-objective adapter failed verification")
    return rebuilt


def build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
    *,
    adapter_bundle: BehavioralStructuralFrontierClosurePlannerV2AdapterBundle,
    observation_return_bundle: BehavioralStructuralFrontierClosurePlannerV2EngineObservationReturnBundle,
) -> BehavioralStructuralFrontierClosurePlannerV2EngineClosedLoopStepBundle:
    status_before = _adapter_status(adapter_bundle)
    if (
        status_before
        is not BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.READY
    ):
        raise HveeContractError("closed-loop advancement requires READY adapter state")
    if not isinstance(
        observation_return_bundle,
        BehavioralStructuralFrontierClosurePlannerV2EngineObservationReturnBundle,
    ):
        raise HveeContractError(
            "observation_return_bundle must be BehavioralStructuralFrontierClosurePlannerV2EngineObservationReturnBundle"
        )
    if not verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
        payload=observation_return_bundle.payload,
        expected_sha256=observation_return_bundle.sha256,
        adapter_bundle=adapter_bundle,
    ):
        raise HveeContractError(
            "multi-objective observation return failed verification"
        )
    try:
        observation_count_before = adapter_bundle.payload["budget"]["evaluated_count"]
    except KeyError as exc:
        raise HveeContractError("adapter budget is incomplete") from exc
    advanced_adapter = _rebuild_adapter_with_appended_observation(
        adapter_bundle=adapter_bundle,
        appended=observation_return_bundle.failure_family_observation,
    )
    status_after = _adapter_status(advanced_adapter)
    try:
        observation_count_after = advanced_adapter.payload["budget"]["evaluated_count"]
    except KeyError as exc:
        raise HveeContractError("advanced adapter budget is incomplete") from exc
    if observation_count_after != observation_count_before + 1:
        raise HveeContractError(
            "closed-loop advancement must extend history by exactly one"
        )
    terminal = (
        status_after
        is not BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.READY
    )
    next_protocol = advanced_adapter.experiment_protocol
    next_protocol_sha256 = None
    next_target_sha256 = None
    if terminal:
        if next_protocol is not None:
            raise HveeContractError(
                "terminal multi-objective adapter must not emit protocol"
            )
    else:
        if next_protocol is None:
            raise HveeContractError("READY advanced adapter requires next protocol")
        if not verify_experiment_protocol_bundle(
            next_protocol.payload, next_protocol.sha256
        ):
            raise HveeContractError(
                "next multi-objective experiment protocol failed verification"
            )
        try:
            proposals = next_protocol.payload["proposals"]
            selected_index = advanced_adapter.payload["planner_decision"][
                "selected_candidate_index"
            ]
            targets = advanced_adapter.payload["axis"]["candidate_target_sha256s"]
        except KeyError as exc:
            raise HveeContractError(
                "advanced adapter next-target surface is incomplete"
            ) from exc
        if (
            not isinstance(proposals, list)
            or len(proposals) != 1
            or (not isinstance(proposals[0], dict))
            or isinstance(selected_index, bool)
            or (not isinstance(selected_index, int))
            or (not isinstance(targets, list))
            or (selected_index < 0)
            or (selected_index >= len(targets))
        ):
            raise HveeContractError("advanced adapter next-target surface is invalid")
        next_target_sha256 = _require_sha256(
            proposals[0].get("target_sha256"), field="next_target_sha256"
        )
        if next_target_sha256 != targets[selected_index]:
            raise HveeContractError(
                "next experiment target does not match advanced planner selection"
            )
        next_protocol_sha256 = next_protocol.sha256
    payload: dict[str, object] = {
        "schema_version": ENGINE_SCHEMA_VERSION,
        "type": CLOSED_LOOP_STEP_TYPE,
        "adapter_bundle_sha256_before": adapter_bundle.sha256,
        "observation_return_sha256": observation_return_bundle.sha256,
        "adapter_bundle_sha256_after": advanced_adapter.sha256,
        "state_transition": {
            "status_before": status_before.value,
            "status_after": status_after.value,
            "observation_count_before": observation_count_before,
            "observation_count_after": observation_count_after,
            "terminal": terminal,
        },
        "next_experiment_protocol_sha256": next_protocol_sha256,
        "next_target_sha256": next_target_sha256,
        "evidence_boundary": {
            "adapter_before_verified": True,
            "observation_return_verified": True,
            "adapter_after_verified": True,
            "history_extension_verified": True,
            "next_target_binding_verified": True,
            "behavioral_performance_qualified": False,
            "execution_evidence_independently_verified": False,
            "internal_engine_used": False,
            "production_qualified": False,
            "release_decision_issued": False,
            "raw_content_persisted": False,
        },
    }
    payload = deepcopy(payload)
    return BehavioralStructuralFrontierClosurePlannerV2EngineClosedLoopStepBundle(
        payload=payload,
        advanced_adapter_bundle=advanced_adapter,
        next_experiment_protocol=next_protocol,
        sha256=calculate_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_sha256(
            payload
        ),
    )


def verify_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
    *,
    payload: object,
    expected_sha256: object,
    adapter_bundle: BehavioralStructuralFrontierClosurePlannerV2AdapterBundle,
    observation_return_bundle: BehavioralStructuralFrontierClosurePlannerV2EngineObservationReturnBundle,
    advanced_adapter_bundle: BehavioralStructuralFrontierClosurePlannerV2AdapterBundle,
    next_experiment_protocol: ExperimentProtocolBundle | None,
) -> bool:
    try:
        normalized_expected_sha = _require_sha256(
            expected_sha256, field="expected_sha256"
        )
        if not isinstance(payload, dict):
            return False
        expected_fields = {
            "schema_version",
            "type",
            "adapter_bundle_sha256_before",
            "observation_return_sha256",
            "adapter_bundle_sha256_after",
            "state_transition",
            "next_experiment_protocol_sha256",
            "next_target_sha256",
            "evidence_boundary",
        }
        if set(payload) != expected_fields:
            return False
        if (
            payload["schema_version"] != ENGINE_SCHEMA_VERSION
            or payload["type"] != CLOSED_LOOP_STEP_TYPE
        ):
            return False
        rebuilt = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
            adapter_bundle=adapter_bundle,
            observation_return_bundle=observation_return_bundle,
        )
        if rebuilt.payload != payload:
            return False
        if rebuilt.sha256 != normalized_expected_sha:
            return False
        if (
            rebuilt.advanced_adapter_bundle.payload != advanced_adapter_bundle.payload
            or rebuilt.advanced_adapter_bundle.sha256 != advanced_adapter_bundle.sha256
        ):
            return False
        if rebuilt.next_experiment_protocol is None:
            if next_experiment_protocol is not None:
                return False
        else:
            if next_experiment_protocol is None:
                return False
            if (
                rebuilt.next_experiment_protocol.payload
                != next_experiment_protocol.payload
                or rebuilt.next_experiment_protocol.sha256
                != next_experiment_protocol.sha256
            ):
                return False
        return True
    except (HveeContractError, KeyError, TypeError, ValueError):
        return False


__all__ = [
    "CLOSED_LOOP_STEP_TYPE",
    "ENGINE_SCHEMA_VERSION",
    "OBSERVATION_RETURN_TYPE",
    "BehavioralStructuralFrontierClosurePlannerV2EngineClosedLoopStepBundle",
    "BehavioralStructuralFrontierClosurePlannerV2EngineObservationReturnBundle",
    "build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle",
    "build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle",
    "calculate_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_sha256",
    "calculate_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_sha256",
    "verify_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle",
    "verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle",
]
