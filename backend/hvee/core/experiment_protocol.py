from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import math
import re

from hvee.core.contracts import HveeContractError


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$")

_FORBIDDEN_RAW_CONTENT_KEYS = frozenset(
    {
        "audio",
        "audio_bytes",
        "audio_content",
        "generated_text",
        "image",
        "image_bytes",
        "input_text",
        "prediction_text",
        "prompt_text",
        "raw_audio",
        "raw_content",
        "raw_input",
        "raw_output",
        "raw_transcript_text",
        "reference_text",
        "transcript",
    }
)


class ExperimentEngineKind(StrEnum):
    BEHAVIORAL = "behavioral"
    INTERNAL = "internal"


class ExperimentObservationStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    ABSTAINED = "abstained"


@dataclass(frozen=True)
class ExperimentDefinition:
    key: str
    version: str
    engine_kind: ExperimentEngineKind
    operation_key: str
    operation_version: str


@dataclass(frozen=True)
class ExperimentProposal:
    sequence: int
    proposal_key: str
    target_sha256: str
    parameters: dict[str, object]
    estimated_cost_units: int
    reason_code: str
    source_evidence_sha256: str | None = None


@dataclass(frozen=True)
class ExperimentObservation:
    proposal_sequence: int
    proposal_sha256: str
    status: ExperimentObservationStatus
    outcome_key: str
    actual_cost_units: int
    result_evidence_sha256: str
    evaluator_evidence_sha256: str | None = None


@dataclass(frozen=True)
class ExperimentProtocolBundle:
    payload: dict[str, object]
    proposal_set_sha256: str
    observation_set_sha256: str
    sha256: str


def _require_identifier(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise HveeContractError(
            f"{field} must be a string"
        )

    if not value:
        raise HveeContractError(
            f"{field} must not be empty"
        )

    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise HveeContractError(
            f"{field} is not canonical"
        )

    return value


def _require_sha256(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise HveeContractError(
            f"{field} must be a SHA-256 string"
        )

    if not _SHA256_PATTERN.fullmatch(value):
        raise HveeContractError(
            f"{field} must be lowercase SHA-256 hex"
        )

    return value


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


def _require_non_negative_integer(
    value: object,
    *,
    field: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise HveeContractError(
            f"{field} must be a non-negative integer"
        )

    return value


def _require_positive_integer(
    value: object,
    *,
    field: str,
) -> int:
    value = _require_non_negative_integer(
        value,
        field=field,
    )

    if value == 0:
        raise HveeContractError(
            f"{field} must be positive"
        )

    return value


def _canonical_json_value(
    value: object,
    *,
    location: str = "$",
) -> object:
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise HveeContractError(
                f"{location} contains a non-finite number"
            )

        return value

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return [
            _canonical_json_value(
                item,
                location=f"{location}[]",
            )
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            _canonical_json_value(
                item,
                location=f"{location}[]",
            )
            for item in value
        ]

    if isinstance(value, dict):
        result: dict[str, object] = {}

        for key in sorted(value):
            if not isinstance(key, str):
                raise HveeContractError(
                    f"{location} contains a non-string key"
                )

            if key in _FORBIDDEN_RAW_CONTENT_KEYS:
                raise HveeContractError(
                    f"{location}.{key} is raw-content material "
                    "and cannot be persisted in the experiment protocol"
                )

            result[key] = _canonical_json_value(
                value[key],
                location=f"{location}.{key}",
            )

        return result

    raise HveeContractError(
        f"{location} contains unsupported JSON value "
        f"{type(value).__name__}"
    )


def _canonical_json(
    value: object,
) -> bytes:
    canonical = _canonical_json_value(
        value
    )

    return json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _calculate_sha256(
    value: object,
) -> str:
    return hashlib.sha256(
        _canonical_json(value)
    ).hexdigest()


def _definition_payload(
    definition: ExperimentDefinition,
) -> dict[str, object]:
    if not isinstance(
        definition,
        ExperimentDefinition,
    ):
        raise HveeContractError(
            "definition must be ExperimentDefinition"
        )

    if not isinstance(
        definition.engine_kind,
        ExperimentEngineKind,
    ):
        raise HveeContractError(
            "definition.engine_kind must be ExperimentEngineKind"
        )

    return {
        "engine_kind": (
            definition.engine_kind.value
        ),
        "key": _require_identifier(
            definition.key,
            field="definition.key",
        ),
        "operation_key": _require_identifier(
            definition.operation_key,
            field="definition.operation_key",
        ),
        "operation_version": _require_identifier(
            definition.operation_version,
            field="definition.operation_version",
        ),
        "version": _require_identifier(
            definition.version,
            field="definition.version",
        ),
    }


def _proposal_payload(
    proposal: ExperimentProposal,
) -> dict[str, object]:
    if not isinstance(
        proposal,
        ExperimentProposal,
    ):
        raise HveeContractError(
            "proposal must be ExperimentProposal"
        )

    parameters = _canonical_json_value(
        deepcopy(proposal.parameters),
        location="proposal.parameters",
    )

    if not isinstance(parameters, dict):
        raise HveeContractError(
            "proposal.parameters must be an object"
        )

    return {
        "estimated_cost_units": (
            _require_positive_integer(
                proposal.estimated_cost_units,
                field="proposal.estimated_cost_units",
            )
        ),
        "parameters": parameters,
        "parameters_sha256": (
            _calculate_sha256(parameters)
        ),
        "proposal_key": _require_identifier(
            proposal.proposal_key,
            field="proposal.proposal_key",
        ),
        "reason_code": _require_identifier(
            proposal.reason_code,
            field="proposal.reason_code",
        ),
        "sequence": _require_non_negative_integer(
            proposal.sequence,
            field="proposal.sequence",
        ),
        "source_evidence_sha256": (
            _require_optional_sha256(
                proposal.source_evidence_sha256,
                field="proposal.source_evidence_sha256",
            )
        ),
        "target_sha256": _require_sha256(
            proposal.target_sha256,
            field="proposal.target_sha256",
        ),
    }


def calculate_experiment_proposal_sha256(
    proposal: ExperimentProposal,
) -> str:
    return _calculate_sha256(
        _proposal_payload(proposal)
    )


def _canonical_proposals(
    proposals: (
        list[ExperimentProposal]
        | tuple[ExperimentProposal, ...]
    ),
) -> list[dict[str, object]]:
    if not isinstance(
        proposals,
        (list, tuple),
    ):
        raise HveeContractError(
            "proposals must be a list or tuple"
        )

    payloads = [
        _proposal_payload(proposal)
        for proposal in proposals
    ]

    expected_sequences = list(
        range(len(payloads))
    )

    actual_sequences = [
        int(item["sequence"])
        for item in payloads
    ]

    if actual_sequences != expected_sequences:
        raise HveeContractError(
            "proposal sequences must be contiguous "
            "and start at zero"
        )

    proposal_keys = [
        str(item["proposal_key"])
        for item in payloads
    ]

    if len(set(proposal_keys)) != len(
        proposal_keys
    ):
        raise HveeContractError(
            "proposal keys must be unique"
        )

    proposal_hashes = [
        _calculate_sha256(item)
        for item in payloads
    ]

    if len(set(proposal_hashes)) != len(
        proposal_hashes
    ):
        raise HveeContractError(
            "proposal identities must be unique"
        )

    return payloads


def calculate_experiment_proposal_set_sha256(
    proposals: (
        list[ExperimentProposal]
        | tuple[ExperimentProposal, ...]
    ),
) -> str:
    return _calculate_sha256(
        _canonical_proposals(proposals)
    )


def _observation_payload(
    observation: ExperimentObservation,
) -> dict[str, object]:
    if not isinstance(
        observation,
        ExperimentObservation,
    ):
        raise HveeContractError(
            "observation must be ExperimentObservation"
        )

    if not isinstance(
        observation.status,
        ExperimentObservationStatus,
    ):
        raise HveeContractError(
            "observation.status must be "
            "ExperimentObservationStatus"
        )

    return {
        "actual_cost_units": (
            _require_positive_integer(
                observation.actual_cost_units,
                field="observation.actual_cost_units",
            )
        ),
        "evaluator_evidence_sha256": (
            _require_optional_sha256(
                observation.evaluator_evidence_sha256,
                field="observation.evaluator_evidence_sha256",
            )
        ),
        "outcome_key": _require_identifier(
            observation.outcome_key,
            field="observation.outcome_key",
        ),
        "proposal_sequence": (
            _require_non_negative_integer(
                observation.proposal_sequence,
                field="observation.proposal_sequence",
            )
        ),
        "proposal_sha256": _require_sha256(
            observation.proposal_sha256,
            field="observation.proposal_sha256",
        ),
        "result_evidence_sha256": (
            _require_sha256(
                observation.result_evidence_sha256,
                field="observation.result_evidence_sha256",
            )
        ),
        "status": observation.status.value,
    }


def _canonical_observations(
    observations: (
        list[ExperimentObservation]
        | tuple[ExperimentObservation, ...]
    ),
) -> list[dict[str, object]]:
    if not isinstance(
        observations,
        (list, tuple),
    ):
        raise HveeContractError(
            "observations must be a list or tuple"
        )

    payloads = [
        _observation_payload(observation)
        for observation in observations
    ]

    observed_sequences = [
        int(item["proposal_sequence"])
        for item in payloads
    ]

    if len(set(observed_sequences)) != len(
        observed_sequences
    ):
        raise HveeContractError(
            "a proposal may have at most one observation"
        )

    if observed_sequences != sorted(
        observed_sequences
    ):
        raise HveeContractError(
            "observations must follow proposal sequence order"
        )

    return payloads


def calculate_experiment_observation_set_sha256(
    observations: (
        list[ExperimentObservation]
        | tuple[ExperimentObservation, ...]
    ),
) -> str:
    return _calculate_sha256(
        _canonical_observations(
            observations
        )
    )


def calculate_experiment_protocol_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(payload, dict):
        raise HveeContractError(
            "payload must be an object"
        )

    return _calculate_sha256(payload)


def build_experiment_protocol_bundle(
    *,
    definition: ExperimentDefinition,
    campaign_key: str,
    campaign_version: str,
    subject_sha256: str,
    maximum_experiments: int,
    maximum_cost_units: int,
    proposals: (
        list[ExperimentProposal]
        | tuple[ExperimentProposal, ...]
    ),
    observations: (
        list[ExperimentObservation]
        | tuple[ExperimentObservation, ...]
    ),
) -> ExperimentProtocolBundle:
    definition_payload = (
        _definition_payload(
            definition
        )
    )

    campaign_key = _require_identifier(
        campaign_key,
        field="campaign_key",
    )

    campaign_version = _require_identifier(
        campaign_version,
        field="campaign_version",
    )

    subject_sha256 = _require_sha256(
        subject_sha256,
        field="subject_sha256",
    )

    maximum_experiments = (
        _require_positive_integer(
            maximum_experiments,
            field="maximum_experiments",
        )
    )

    maximum_cost_units = (
        _require_positive_integer(
            maximum_cost_units,
            field="maximum_cost_units",
        )
    )

    proposal_payloads = (
        _canonical_proposals(
            proposals
        )
    )

    observation_payloads = (
        _canonical_observations(
            observations
        )
    )

    if len(proposal_payloads) > (
        maximum_experiments
    ):
        raise HveeContractError(
            "proposal count exceeds maximum_experiments"
        )

    proposal_hashes = {
        int(item["sequence"]): (
            _calculate_sha256(item)
        )
        for item in proposal_payloads
    }

    for observation in observation_payloads:
        sequence = int(
            observation[
                "proposal_sequence"
            ]
        )

        expected_proposal_sha256 = (
            proposal_hashes.get(sequence)
        )

        if expected_proposal_sha256 is None:
            raise HveeContractError(
                "observation references an unknown proposal"
            )

        if (
            observation[
                "proposal_sha256"
            ]
            != expected_proposal_sha256
        ):
            raise HveeContractError(
                "observation does not bind the exact proposal"
            )

    observed_cost_units = sum(
        int(item["actual_cost_units"])
        for item in observation_payloads
    )

    if observed_cost_units > (
        maximum_cost_units
    ):
        raise HveeContractError(
            "observed cost exceeds maximum_cost_units"
        )

    proposed_cost_units = sum(
        int(item["estimated_cost_units"])
        for item in proposal_payloads
    )

    if proposed_cost_units > (
        maximum_cost_units
    ):
        raise HveeContractError(
            "proposed cost exceeds maximum_cost_units"
        )

    proposal_set_sha256 = (
        _calculate_sha256(
            proposal_payloads
        )
    )

    observation_set_sha256 = (
        _calculate_sha256(
            observation_payloads
        )
    )

    payload: dict[str, object] = {
        "budget": {
            "maximum_cost_units": (
                maximum_cost_units
            ),
            "maximum_experiments": (
                maximum_experiments
            ),
            "observed_cost_units": (
                observed_cost_units
            ),
            "proposed_cost_units": (
                proposed_cost_units
            ),
        },
        "campaign": {
            "key": campaign_key,
            "version": campaign_version,
        },
        "definition": (
            definition_payload
        ),
        "evidence_boundary": {
            "causal_mechanism_established": False,
            "experiment_execution_proven": (
                bool(observation_payloads)
            ),
            "production_qualified": False,
            "release_decision_issued": False,
            "raw_content_persisted": False,
        },
        "observation_set_sha256": (
            observation_set_sha256
        ),
        "observations": (
            observation_payloads
        ),
        "proposal_set_sha256": (
            proposal_set_sha256
        ),
        "proposals": proposal_payloads,
        "schema_version": 1,
        "subject_sha256": (
            subject_sha256
        ),
    }

    payload = deepcopy(payload)

    protocol_sha256 = (
        calculate_experiment_protocol_sha256(
            payload
        )
    )

    return ExperimentProtocolBundle(
        payload=payload,
        proposal_set_sha256=(
            proposal_set_sha256
        ),
        observation_set_sha256=(
            observation_set_sha256
        ),
        sha256=protocol_sha256,
    )


def _parse_definition(
    payload: object,
) -> ExperimentDefinition:
    if not isinstance(payload, dict):
        raise HveeContractError(
            "definition payload must be an object"
        )

    if set(payload) != {
        "engine_kind",
        "key",
        "operation_key",
        "operation_version",
        "version",
    }:
        raise HveeContractError(
            "definition payload fields are not canonical"
        )

    try:
        engine_kind = ExperimentEngineKind(
            payload["engine_kind"]
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "definition.engine_kind is invalid"
        ) from exc

    return ExperimentDefinition(
        key=payload["key"],
        version=payload["version"],
        engine_kind=engine_kind,
        operation_key=(
            payload["operation_key"]
        ),
        operation_version=(
            payload["operation_version"]
        ),
    )


def _parse_proposal(
    payload: object,
) -> ExperimentProposal:
    if not isinstance(payload, dict):
        raise HveeContractError(
            "proposal payload must be an object"
        )

    expected_fields = {
        "estimated_cost_units",
        "parameters",
        "parameters_sha256",
        "proposal_key",
        "reason_code",
        "sequence",
        "source_evidence_sha256",
        "target_sha256",
    }

    if set(payload) != expected_fields:
        raise HveeContractError(
            "proposal payload fields are not canonical"
        )

    parameters = payload["parameters"]

    if not isinstance(parameters, dict):
        raise HveeContractError(
            "proposal.parameters must be an object"
        )

    calculated_parameters_sha256 = (
        _calculate_sha256(parameters)
    )

    if (
        payload["parameters_sha256"]
        != calculated_parameters_sha256
    ):
        raise HveeContractError(
            "proposal parameters digest mismatch"
        )

    return ExperimentProposal(
        sequence=payload["sequence"],
        proposal_key=payload["proposal_key"],
        target_sha256=payload["target_sha256"],
        parameters=deepcopy(parameters),
        estimated_cost_units=(
            payload["estimated_cost_units"]
        ),
        reason_code=payload["reason_code"],
        source_evidence_sha256=(
            payload[
                "source_evidence_sha256"
            ]
        ),
    )


def _parse_observation(
    payload: object,
) -> ExperimentObservation:
    if not isinstance(payload, dict):
        raise HveeContractError(
            "observation payload must be an object"
        )

    expected_fields = {
        "actual_cost_units",
        "evaluator_evidence_sha256",
        "outcome_key",
        "proposal_sequence",
        "proposal_sha256",
        "result_evidence_sha256",
        "status",
    }

    if set(payload) != expected_fields:
        raise HveeContractError(
            "observation payload fields are not canonical"
        )

    try:
        status = ExperimentObservationStatus(
            payload["status"]
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "observation.status is invalid"
        ) from exc

    return ExperimentObservation(
        proposal_sequence=(
            payload["proposal_sequence"]
        ),
        proposal_sha256=(
            payload["proposal_sha256"]
        ),
        status=status,
        outcome_key=(
            payload["outcome_key"]
        ),
        actual_cost_units=(
            payload["actual_cost_units"]
        ),
        result_evidence_sha256=(
            payload[
                "result_evidence_sha256"
            ]
        ),
        evaluator_evidence_sha256=(
            payload[
                "evaluator_evidence_sha256"
            ]
        ),
    )


def verify_experiment_protocol_bundle(
    payload: object,
    expected_sha256: object,
) -> bool:
    expected_sha256 = _require_sha256(
        expected_sha256,
        field="expected_sha256",
    )

    if not isinstance(payload, dict):
        return False

    expected_fields = {
        "budget",
        "campaign",
        "definition",
        "evidence_boundary",
        "observation_set_sha256",
        "observations",
        "proposal_set_sha256",
        "proposals",
        "schema_version",
        "subject_sha256",
    }

    if set(payload) != expected_fields:
        return False

    if payload.get("schema_version") != 1:
        return False

    try:
        campaign = payload["campaign"]

        if not isinstance(campaign, dict):
            return False

        if set(campaign) != {
            "key",
            "version",
        }:
            return False

        budget = payload["budget"]

        if not isinstance(budget, dict):
            return False

        if set(budget) != {
            "maximum_cost_units",
            "maximum_experiments",
            "observed_cost_units",
            "proposed_cost_units",
        }:
            return False

        evidence_boundary = payload[
            "evidence_boundary"
        ]

        if not isinstance(
            evidence_boundary,
            dict,
        ):
            return False

        if evidence_boundary != {
            "causal_mechanism_established": False,
            "experiment_execution_proven": bool(
                payload["observations"]
            ),
            "production_qualified": False,
            "raw_content_persisted": False,
            "release_decision_issued": False,
        }:
            return False

        definition = _parse_definition(
            payload["definition"]
        )

        proposals_payload = (
            payload["proposals"]
        )

        observations_payload = (
            payload["observations"]
        )

        if not isinstance(
            proposals_payload,
            list,
        ):
            return False

        if not isinstance(
            observations_payload,
            list,
        ):
            return False

        proposals = [
            _parse_proposal(item)
            for item in proposals_payload
        ]

        observations = [
            _parse_observation(item)
            for item in observations_payload
        ]

        rebuilt = (
            build_experiment_protocol_bundle(
                definition=definition,
                campaign_key=(
                    campaign["key"]
                ),
                campaign_version=(
                    campaign["version"]
                ),
                subject_sha256=(
                    payload["subject_sha256"]
                ),
                maximum_experiments=(
                    budget[
                        "maximum_experiments"
                    ]
                ),
                maximum_cost_units=(
                    budget[
                        "maximum_cost_units"
                    ]
                ),
                proposals=proposals,
                observations=observations,
            )
        )

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False

    if (
        rebuilt.proposal_set_sha256
        != payload[
            "proposal_set_sha256"
        ]
    ):
        return False

    if (
        rebuilt.observation_set_sha256
        != payload[
            "observation_set_sha256"
        ]
    ):
        return False

    if rebuilt.payload != payload:
        return False

    if rebuilt.sha256 != expected_sha256:
        return False

    return True
