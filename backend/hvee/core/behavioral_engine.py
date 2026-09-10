from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import re

from hvee.core.adaptive_scenario_search import (
    AdaptiveScenarioObservation,
    AdaptiveScenarioSearchBundle,
    verify_adaptive_scenario_search_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.experiment_protocol import (
    ExperimentDefinition,
    ExperimentEngineKind,
    ExperimentObservation,
    ExperimentObservationStatus,
    ExperimentProtocolBundle,
    ExperimentProposal,
    build_experiment_protocol_bundle,
    verify_experiment_protocol_bundle,
)
from hvee.core.minimal_counterexample_reduction import (
    CounterexampleReductionObservation,
    MinimalCounterexampleReductionBundle,
    verify_minimal_counterexample_reduction_bundle,
)
from hvee.core.neighborhood_generation import (
    NeighborhoodGenerationBundle,
    NeighborhoodObservation,
    verify_neighborhood_generation_bundle,
)


BEHAVIORAL_ENGINE_SCHEMA_VERSION = 1
BEHAVIORAL_ENGINE_DEFINITION_KEY = "hetren.behavioral-engine.experiment"
BEHAVIORAL_ENGINE_DEFINITION_VERSION = "1.0.0"

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class BehavioralEngineOperation(StrEnum):
    ADAPTIVE_SCENARIO_SEARCH = "adaptive_scenario_search"
    MINIMAL_COUNTEREXAMPLE_REDUCTION = "minimal_counterexample_reduction"
    NEIGHBORHOOD_GENERATION = "neighborhood_generation"


@dataclass(frozen=True)
class BehavioralEngineExperimentBundle:
    payload: dict[str, object]
    experiment_protocol: ExperimentProtocolBundle
    sha256: str


def _canonical_json(
    value: object,
) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "behavioral engine payload must be " "canonical JSON"
        ) from exc


def _calculate_sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _require_sha256(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise HveeContractError(f"{field} must be lowercase SHA-256 hex")

    return value


def _require_positive_integer(
    value: object,
    *,
    field: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise HveeContractError(f"{field} must be a positive integer")

    return value


def _source_contract(
    operation: BehavioralEngineOperation,
) -> tuple[
    type,
    str,
    str,
]:
    if operation == BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH:
        return (
            AdaptiveScenarioSearchBundle,
            "adaptive_scenario_search",
            "search",
        )

    if operation == BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION:
        return (
            MinimalCounterexampleReductionBundle,
            "minimal_counterexample_reduction",
            "reduction",
        )

    if operation == BehavioralEngineOperation.NEIGHBORHOOD_GENERATION:
        return (
            NeighborhoodGenerationBundle,
            "neighborhood_generation",
            "neighborhood",
        )

    raise HveeContractError("unsupported behavioral engine operation")


def _verify_source_bundle(
    *,
    operation: BehavioralEngineOperation,
    payload: object,
    expected_sha256: object,
) -> bool:
    if operation == BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH:
        return verify_adaptive_scenario_search_bundle(
            payload=payload,
            expected_sha256=expected_sha256,
        )

    if operation == BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION:
        return verify_minimal_counterexample_reduction_bundle(
            payload=payload,
            expected_sha256=expected_sha256,
        )

    if operation == BehavioralEngineOperation.NEIGHBORHOOD_GENERATION:
        return verify_neighborhood_generation_bundle(
            payload=payload,
            expected_sha256=expected_sha256,
        )

    return False


def _validated_source_bundle(
    *,
    operation: BehavioralEngineOperation,
    source_bundle: object,
) -> tuple[
    dict[str, object],
    str,
]:
    (
        expected_type,
        _payload_type,
        _status_section,
    ) = _source_contract(operation)

    if not isinstance(
        source_bundle,
        expected_type,
    ):
        raise HveeContractError("source bundle does not match " "behavioral operation")

    payload = source_bundle.payload
    source_sha256 = _require_sha256(
        source_bundle.sha256,
        field="source_bundle.sha256",
    )

    if not _verify_source_bundle(
        operation=operation,
        payload=payload,
        expected_sha256=source_sha256,
    ):
        raise HveeContractError("source behavioral component " "failed verification")

    return (
        payload,
        source_sha256,
    )


def _source_snapshot(
    *,
    operation: BehavioralEngineOperation,
    source_payload: dict[str, object],
) -> tuple[
    str,
    dict[str, object],
    str,
]:
    (
        _expected_type,
        expected_payload_type,
        status_section_key,
    ) = _source_contract(operation)

    if source_payload.get("type") != expected_payload_type:
        raise HveeContractError(
            "source behavioral payload type " "does not match operation"
        )

    component_section = source_payload.get(status_section_key)

    if not isinstance(
        component_section,
        dict,
    ):
        raise HveeContractError("source behavioral status section " "is invalid")

    source_status = component_section.get("status")

    if (
        not isinstance(
            source_status,
            str,
        )
        or not source_status
    ):
        raise HveeContractError("source behavioral status is invalid")

    outcome = source_payload.get("outcome")

    if not isinstance(
        outcome,
        dict,
    ):
        raise HveeContractError("source behavioral outcome is invalid")

    native_proposal = outcome.get("next_proposal")

    if native_proposal is None:
        raise HveeContractError("source behavioral component " "has no next proposal")

    if not isinstance(
        native_proposal,
        dict,
    ):
        raise HveeContractError("source behavioral next proposal " "must be an object")

    reason_code = native_proposal.get("reason")

    if (
        not isinstance(
            reason_code,
            str,
        )
        or not reason_code
    ):
        raise HveeContractError("source behavioral proposal " "reason is invalid")

    return (
        source_status,
        deepcopy(native_proposal),
        reason_code,
    )


def calculate_behavioral_engine_experiment_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("behavioral engine payload " "must be an object")

    return _calculate_sha256(payload)


def build_behavioral_engine_experiment_bundle(
    *,
    operation: BehavioralEngineOperation,
    source_bundle: object,
    campaign_key: str,
    campaign_version: str,
    subject_sha256: str,
    target_sha256: str,
    estimated_cost_units: int = 1,
    maximum_cost_units: int = 1,
) -> BehavioralEngineExperimentBundle:
    if not isinstance(
        operation,
        BehavioralEngineOperation,
    ):
        raise HveeContractError("operation must be " "BehavioralEngineOperation")

    (
        source_payload,
        source_sha256,
    ) = _validated_source_bundle(
        operation=operation,
        source_bundle=source_bundle,
    )

    (
        source_status,
        native_proposal,
        reason_code,
    ) = _source_snapshot(
        operation=operation,
        source_payload=source_payload,
    )

    subject_sha256 = _require_sha256(
        subject_sha256,
        field="subject_sha256",
    )

    target_sha256 = _require_sha256(
        target_sha256,
        field="target_sha256",
    )

    estimated_cost_units = _require_positive_integer(
        estimated_cost_units,
        field="estimated_cost_units",
    )

    maximum_cost_units = _require_positive_integer(
        maximum_cost_units,
        field="maximum_cost_units",
    )

    native_proposal_sha256 = _calculate_sha256(native_proposal)

    parameters = {
        "native_proposal": (native_proposal),
        "native_proposal_sha256": (native_proposal_sha256),
        "source_bundle_sha256": (source_sha256),
        "source_component": (operation.value),
        "source_status": (source_status),
    }

    protocol = build_experiment_protocol_bundle(
        definition=ExperimentDefinition(
            key=(BEHAVIORAL_ENGINE_DEFINITION_KEY),
            version=(BEHAVIORAL_ENGINE_DEFINITION_VERSION),
            engine_kind=(ExperimentEngineKind.BEHAVIORAL),
            operation_key=(operation.value),
            operation_version="1.0.0",
        ),
        campaign_key=campaign_key,
        campaign_version=campaign_version,
        subject_sha256=subject_sha256,
        maximum_experiments=1,
        maximum_cost_units=(maximum_cost_units),
        proposals=[
            ExperimentProposal(
                sequence=0,
                proposal_key=(f"{operation.value}.next"),
                target_sha256=(target_sha256),
                parameters=parameters,
                estimated_cost_units=(estimated_cost_units),
                reason_code=(reason_code),
                source_evidence_sha256=(source_sha256),
            )
        ],
        observations=[],
    )

    payload: dict[str, object] = {
        "schema_version": (BEHAVIORAL_ENGINE_SCHEMA_VERSION),
        "type": ("behavioral_engine_experiment"),
        "operation": (operation.value),
        "source": {
            "bundle_sha256": (source_sha256),
            "native_proposal_sha256": (native_proposal_sha256),
            "status": (source_status),
        },
        "experiment_protocol": (deepcopy(protocol.payload)),
        "experiment_protocol_sha256": (protocol.sha256),
        "evidence_boundary": {
            "behavioral_performance_qualified": (False),
            "experiment_executed": (False),
            "internal_engine_used": (False),
            "native_component_algorithm_modified": (False),
            "production_qualified": (False),
            "raw_content_persisted": (False),
            "release_decision_issued": (False),
            "source_component_verified": (True),
        },
    }

    payload = deepcopy(payload)

    return BehavioralEngineExperimentBundle(
        payload=payload,
        experiment_protocol=protocol,
        sha256=(calculate_behavioral_engine_experiment_sha256(payload)),
    )


def build_adaptive_search_experiment_bundle(
    *,
    source_bundle: AdaptiveScenarioSearchBundle,
    campaign_key: str,
    campaign_version: str,
    subject_sha256: str,
    target_sha256: str,
    estimated_cost_units: int = 1,
    maximum_cost_units: int = 1,
) -> BehavioralEngineExperimentBundle:
    return build_behavioral_engine_experiment_bundle(
        operation=(BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH),
        source_bundle=source_bundle,
        campaign_key=campaign_key,
        campaign_version=campaign_version,
        subject_sha256=subject_sha256,
        target_sha256=target_sha256,
        estimated_cost_units=(estimated_cost_units),
        maximum_cost_units=(maximum_cost_units),
    )


def build_minimal_reduction_experiment_bundle(
    *,
    source_bundle: MinimalCounterexampleReductionBundle,
    campaign_key: str,
    campaign_version: str,
    subject_sha256: str,
    target_sha256: str,
    estimated_cost_units: int = 1,
    maximum_cost_units: int = 1,
) -> BehavioralEngineExperimentBundle:
    return build_behavioral_engine_experiment_bundle(
        operation=(BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION),
        source_bundle=source_bundle,
        campaign_key=campaign_key,
        campaign_version=campaign_version,
        subject_sha256=subject_sha256,
        target_sha256=target_sha256,
        estimated_cost_units=(estimated_cost_units),
        maximum_cost_units=(maximum_cost_units),
    )


def build_neighborhood_experiment_bundle(
    *,
    source_bundle: NeighborhoodGenerationBundle,
    campaign_key: str,
    campaign_version: str,
    subject_sha256: str,
    target_sha256: str,
    estimated_cost_units: int = 1,
    maximum_cost_units: int = 1,
) -> BehavioralEngineExperimentBundle:
    return build_behavioral_engine_experiment_bundle(
        operation=(BehavioralEngineOperation.NEIGHBORHOOD_GENERATION),
        source_bundle=source_bundle,
        campaign_key=campaign_key,
        campaign_version=campaign_version,
        subject_sha256=subject_sha256,
        target_sha256=target_sha256,
        estimated_cost_units=(estimated_cost_units),
        maximum_cost_units=(maximum_cost_units),
    )


def verify_behavioral_engine_experiment_bundle(
    *,
    payload: object,
    expected_sha256: object,
    source_bundle: object,
) -> bool:
    try:
        expected_sha256 = _require_sha256(
            expected_sha256,
            field="expected_sha256",
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        expected_fields = {
            "schema_version",
            "type",
            "operation",
            "source",
            "experiment_protocol",
            "experiment_protocol_sha256",
            "evidence_boundary",
        }

        if set(payload) != expected_fields:
            return False

        if payload["schema_version"] != BEHAVIORAL_ENGINE_SCHEMA_VERSION:
            return False

        if payload["type"] != "behavioral_engine_experiment":
            return False

        operation = BehavioralEngineOperation(payload["operation"])

        (
            source_payload,
            source_sha256,
        ) = _validated_source_bundle(
            operation=operation,
            source_bundle=source_bundle,
        )

        (
            source_status,
            native_proposal,
            reason_code,
        ) = _source_snapshot(
            operation=operation,
            source_payload=source_payload,
        )

        native_proposal_sha256 = _calculate_sha256(native_proposal)

        source = payload["source"]

        if not isinstance(
            source,
            dict,
        ):
            return False

        if set(source) != {
            "bundle_sha256",
            "native_proposal_sha256",
            "status",
        }:
            return False

        if source != {
            "bundle_sha256": (source_sha256),
            "native_proposal_sha256": (native_proposal_sha256),
            "status": (source_status),
        }:
            return False

        protocol_payload = payload["experiment_protocol"]

        protocol_sha256 = _require_sha256(
            payload["experiment_protocol_sha256"],
            field=("experiment_protocol_sha256"),
        )

        if not (
            verify_experiment_protocol_bundle(
                protocol_payload,
                protocol_sha256,
            )
        ):
            return False

        if not isinstance(
            protocol_payload,
            dict,
        ):
            return False

        definition = protocol_payload["definition"]

        if definition != {
            "engine_kind": "behavioral",
            "key": (BEHAVIORAL_ENGINE_DEFINITION_KEY),
            "operation_key": (operation.value),
            "operation_version": ("1.0.0"),
            "version": (BEHAVIORAL_ENGINE_DEFINITION_VERSION),
        }:
            return False

        proposals = protocol_payload["proposals"]

        observations = protocol_payload["observations"]

        if (
            not isinstance(
                proposals,
                list,
            )
            or len(proposals) != 1
        ):
            return False

        if observations != []:
            return False

        proposal = proposals[0]

        if not isinstance(
            proposal,
            dict,
        ):
            return False

        if proposal.get("source_evidence_sha256") != source_sha256:
            return False

        if proposal.get("reason_code") != reason_code:
            return False

        parameters = proposal.get("parameters")

        expected_parameters = {
            "native_proposal": (native_proposal),
            "native_proposal_sha256": (native_proposal_sha256),
            "source_bundle_sha256": (source_sha256),
            "source_component": (operation.value),
            "source_status": (source_status),
        }

        if parameters != expected_parameters:
            return False

        if (
            protocol_payload["evidence_boundary"]["experiment_execution_proven"]
            is not False
        ):
            return False

        expected_boundary = {
            "behavioral_performance_qualified": (False),
            "experiment_executed": (False),
            "internal_engine_used": (False),
            "native_component_algorithm_modified": (False),
            "production_qualified": (False),
            "raw_content_persisted": (False),
            "release_decision_issued": (False),
            "source_component_verified": (True),
        }

        if payload["evidence_boundary"] != expected_boundary:
            return False

        if calculate_behavioral_engine_experiment_sha256(payload) != expected_sha256:
            return False

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False

    return True


@dataclass(frozen=True)
class BehavioralEngineObservationReturnBundle:
    payload: dict[str, object]
    experiment_observation: ExperimentObservation
    native_observation: (
        AdaptiveScenarioObservation
        | CounterexampleReductionObservation
        | NeighborhoodObservation
    )
    sha256: str


def _require_optional_sha256(
    value: object,
    *,
    field: str,
) -> str | None:
    if value is None:
        return None

    return _require_sha256(
        value,
        field=field,
    )


def _require_binary_verdict(
    value: object,
) -> DecisionVerdict:
    if not isinstance(
        value,
        DecisionVerdict,
    ):
        raise HveeContractError("verdict must be DecisionVerdict")

    if value not in {
        DecisionVerdict.PASS,
        DecisionVerdict.FAIL,
    }:
        raise HveeContractError(
            "behavioral observation verdict " "must be pass or fail"
        )

    return value


def _require_non_negative_index(
    value: object,
    *,
    field: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HveeContractError(f"{field} must be a non-negative integer")

    return value


def _native_proposal_index(
    *,
    operation: BehavioralEngineOperation,
    native_proposal: dict[str, object],
) -> int:
    if operation == BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH:
        return _require_non_negative_index(
            native_proposal.get("candidate_index"),
            field=("adaptive proposal candidate_index"),
        )

    if operation == BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION:
        removed_unit = native_proposal.get("removed_unit")

        if not isinstance(
            removed_unit,
            dict,
        ):
            raise HveeContractError(
                "reduction proposal removed_unit " "must be an object"
            )

        return _require_non_negative_index(
            removed_unit.get("index"),
            field=("reduction proposal removed_unit.index"),
        )

    if operation == BehavioralEngineOperation.NEIGHBORHOOD_GENERATION:
        candidate = native_proposal.get("candidate")

        if not isinstance(
            candidate,
            dict,
        ):
            raise HveeContractError(
                "neighborhood proposal candidate " "must be an object"
            )

        return _require_non_negative_index(
            candidate.get("index"),
            field=("neighborhood proposal candidate.index"),
        )

    raise HveeContractError("unsupported behavioral operation")


def _native_observation_payload(
    *,
    operation: BehavioralEngineOperation,
    observation: (
        AdaptiveScenarioObservation
        | CounterexampleReductionObservation
        | NeighborhoodObservation
    ),
) -> dict[str, object]:
    common = {
        "counterexample_evidence_sha256": (observation.counterexample_evidence_sha256),
        "decision_evidence_sha256": (observation.decision_evidence_sha256),
        "observation_evidence_sha256": (observation.observation_evidence_sha256),
        "result_provenance_sha256": (observation.result_provenance_sha256),
        "scenario_sha256": (observation.scenario_sha256),
        "sequence": (observation.sequence),
        "verdict": (observation.verdict.value),
    }

    if operation == BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH:
        if not isinstance(
            observation,
            AdaptiveScenarioObservation,
        ):
            raise HveeContractError(
                "native observation type does not " "match adaptive search"
            )

        return {
            **common,
            "candidate_index": (observation.candidate_index),
        }

    if operation == BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION:
        if not isinstance(
            observation,
            CounterexampleReductionObservation,
        ):
            raise HveeContractError(
                "native observation type does not " "match minimal reduction"
            )

        return {
            **common,
            "removed_unit_index": (observation.removed_unit_index),
        }

    if operation == BehavioralEngineOperation.NEIGHBORHOOD_GENERATION:
        if not isinstance(
            observation,
            NeighborhoodObservation,
        ):
            raise HveeContractError(
                "native observation type does not " "match neighborhood generation"
            )

        return {
            **common,
            "candidate_index": (observation.candidate_index),
        }

    raise HveeContractError("unsupported behavioral operation")


def calculate_behavioral_engine_observation_return_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("observation return payload " "must be an object")

    return _calculate_sha256(payload)


def build_behavioral_engine_observation_return_bundle(
    *,
    experiment_bundle: BehavioralEngineExperimentBundle,
    source_bundle: object,
    scenario_sha256: str,
    verdict: DecisionVerdict,
    result_provenance_sha256: str,
    observation_evidence_sha256: str,
    decision_evidence_sha256: str,
    counterexample_evidence_sha256: str | None = None,
    actual_cost_units: int = 1,
) -> BehavioralEngineObservationReturnBundle:
    if not isinstance(
        experiment_bundle,
        BehavioralEngineExperimentBundle,
    ):
        raise HveeContractError(
            "experiment_bundle must be " "BehavioralEngineExperimentBundle"
        )

    if not verify_behavioral_engine_experiment_bundle(
        payload=experiment_bundle.payload,
        expected_sha256=experiment_bundle.sha256,
        source_bundle=source_bundle,
    ):
        raise HveeContractError("behavioral experiment bundle " "failed verification")

    try:
        operation = BehavioralEngineOperation(experiment_bundle.payload["operation"])
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "behavioral experiment operation " "is invalid"
        ) from exc

    (
        source_payload,
        source_sha256,
    ) = _validated_source_bundle(
        operation=operation,
        source_bundle=source_bundle,
    )

    (
        source_status,
        native_proposal,
        _reason_code,
    ) = _source_snapshot(
        operation=operation,
        source_payload=source_payload,
    )

    observations = source_payload.get("observations")

    if not isinstance(
        observations,
        list,
    ):
        raise HveeContractError("source observations must be a list")

    native_sequence = len(observations) + 1

    native_index = _native_proposal_index(
        operation=operation,
        native_proposal=native_proposal,
    )

    scenario_sha256 = _require_sha256(
        scenario_sha256,
        field="scenario_sha256",
    )

    result_provenance_sha256 = _require_sha256(
        result_provenance_sha256,
        field=("result_provenance_sha256"),
    )

    observation_evidence_sha256 = _require_sha256(
        observation_evidence_sha256,
        field=("observation_evidence_sha256"),
    )

    decision_evidence_sha256 = _require_sha256(
        decision_evidence_sha256,
        field=("decision_evidence_sha256"),
    )

    counterexample_evidence_sha256 = _require_optional_sha256(
        counterexample_evidence_sha256,
        field=("counterexample_evidence_sha256"),
    )

    verdict = _require_binary_verdict(verdict)

    if verdict == DecisionVerdict.FAIL and counterexample_evidence_sha256 is None:
        raise HveeContractError(
            "failing behavioral observation " "requires counterexample evidence"
        )

    if verdict == DecisionVerdict.PASS and counterexample_evidence_sha256 is not None:
        raise HveeContractError(
            "passing behavioral observation " "must not include counterexample evidence"
        )

    actual_cost_units = _require_positive_integer(
        actual_cost_units,
        field="actual_cost_units",
    )

    protocol_payload = experiment_bundle.experiment_protocol.payload

    budget = protocol_payload.get("budget")

    if not isinstance(
        budget,
        dict,
    ):
        raise HveeContractError("experiment protocol budget " "is invalid")

    maximum_cost_units = _require_positive_integer(
        budget.get("maximum_cost_units"),
        field=("experiment maximum_cost_units"),
    )

    if actual_cost_units > (maximum_cost_units):
        raise HveeContractError("actual cost exceeds " "experiment maximum_cost_units")

    proposals = protocol_payload.get("proposals")

    if (
        not isinstance(
            proposals,
            list,
        )
        or len(proposals) != 1
        or not isinstance(
            proposals[0],
            dict,
        )
    ):
        raise HveeContractError(
            "behavioral experiment must contain " "exactly one canonical proposal"
        )

    proposal_payload = proposals[0]

    proposal_sha256 = _calculate_sha256(proposal_payload)

    experiment_observation = ExperimentObservation(
        proposal_sequence=0,
        proposal_sha256=(proposal_sha256),
        status=(ExperimentObservationStatus.COMPLETED),
        outcome_key=verdict.value,
        actual_cost_units=(actual_cost_units),
        result_evidence_sha256=(result_provenance_sha256),
        evaluator_evidence_sha256=(decision_evidence_sha256),
    )

    common = {
        "sequence": native_sequence,
        "scenario_sha256": (scenario_sha256),
        "verdict": verdict,
        "result_provenance_sha256": (result_provenance_sha256),
        "observation_evidence_sha256": (observation_evidence_sha256),
        "decision_evidence_sha256": (decision_evidence_sha256),
        "counterexample_evidence_sha256": (counterexample_evidence_sha256),
    }

    if operation == BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH:
        native_observation = AdaptiveScenarioObservation(
            candidate_index=(native_index),
            **common,
        )

    elif operation == BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION:
        native_observation = CounterexampleReductionObservation(
            removed_unit_index=(native_index),
            **common,
        )

    elif operation == BehavioralEngineOperation.NEIGHBORHOOD_GENERATION:
        native_observation = NeighborhoodObservation(
            candidate_index=(native_index),
            **common,
        )

    else:
        raise HveeContractError("unsupported behavioral operation")

    native_payload = _native_observation_payload(
        operation=operation,
        observation=native_observation,
    )

    native_proposal_sha256 = _calculate_sha256(native_proposal)

    experiment_observation_payload = {
        "actual_cost_units": (experiment_observation.actual_cost_units),
        "evaluator_evidence_sha256": (experiment_observation.evaluator_evidence_sha256),
        "outcome_key": (experiment_observation.outcome_key),
        "proposal_sequence": (experiment_observation.proposal_sequence),
        "proposal_sha256": (experiment_observation.proposal_sha256),
        "result_evidence_sha256": (experiment_observation.result_evidence_sha256),
        "status": (experiment_observation.status.value),
    }

    payload: dict[str, object] = {
        "schema_version": 1,
        "type": ("behavioral_engine_observation_return"),
        "operation": (operation.value),
        "experiment_bundle_sha256": (experiment_bundle.sha256),
        "experiment_protocol_sha256": (experiment_bundle.experiment_protocol.sha256),
        "source": {
            "bundle_sha256": (source_sha256),
            "native_proposal_sha256": (native_proposal_sha256),
            "status_before_observation": (source_status),
        },
        "experiment_observation": (experiment_observation_payload),
        "native_observation": (native_payload),
        "evidence_boundary": {
            "behavioral_performance_qualified": (False),
            "execution_evidence_referenced": (True),
            "execution_evidence_verified": (False),
            "internal_engine_used": (False),
            "native_observation_constructed": (True),
            "native_state_advanced": (False),
            "production_qualified": (False),
            "raw_content_persisted": (False),
            "release_decision_issued": (False),
        },
    }

    payload = deepcopy(payload)

    return BehavioralEngineObservationReturnBundle(
        payload=payload,
        experiment_observation=(experiment_observation),
        native_observation=(native_observation),
        sha256=(calculate_behavioral_engine_observation_return_sha256(payload)),
    )


def verify_behavioral_engine_observation_return_bundle(
    *,
    payload: object,
    expected_sha256: object,
    experiment_bundle: BehavioralEngineExperimentBundle,
    source_bundle: object,
) -> bool:
    try:
        expected_sha256 = _require_sha256(
            expected_sha256,
            field="expected_sha256",
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        expected_fields = {
            "schema_version",
            "type",
            "operation",
            "experiment_bundle_sha256",
            "experiment_protocol_sha256",
            "source",
            "experiment_observation",
            "native_observation",
            "evidence_boundary",
        }

        if set(payload) != (expected_fields):
            return False

        if payload["schema_version"] != 1:
            return False

        if payload["type"] != ("behavioral_engine_" "observation_return"):
            return False

        operation = BehavioralEngineOperation(payload["operation"])

        if operation.value != experiment_bundle.payload["operation"]:
            return False

        native = payload["native_observation"]

        experiment_observation = payload["experiment_observation"]

        if not isinstance(
            native,
            dict,
        ):
            return False

        if not isinstance(
            experiment_observation,
            dict,
        ):
            return False

        verdict = DecisionVerdict(native["verdict"])

        rebuilt = build_behavioral_engine_observation_return_bundle(
            experiment_bundle=(experiment_bundle),
            source_bundle=(source_bundle),
            scenario_sha256=(native["scenario_sha256"]),
            verdict=verdict,
            result_provenance_sha256=(native["result_provenance_sha256"]),
            observation_evidence_sha256=(native["observation_evidence_sha256"]),
            decision_evidence_sha256=(native["decision_evidence_sha256"]),
            counterexample_evidence_sha256=(native["counterexample_evidence_sha256"]),
            actual_cost_units=(experiment_observation["actual_cost_units"]),
        )

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False

    if rebuilt.payload != payload:
        return False

    if rebuilt.sha256 != (expected_sha256):
        return False

    return True
