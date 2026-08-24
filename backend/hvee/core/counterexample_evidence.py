"""Canonical, privacy-conscious evidence for one observed counterexample.

The core contract binds a controlled scenario to the immutable provenance,
observation, and decision evidence that demonstrated a failure.  It does not
store database identifiers, timestamps, raw inputs, or model outputs.

Domain packs own the meaning of a failure claim.  This module owns only
portable identity, deterministic ordering, canonical JSON, and digest
verification.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict


COUNTEREXAMPLE_EVIDENCE_SCHEMA_VERSION = 1

_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)

_EVIDENCE_BOUNDARY = {
    "observed_failure": True,
    "causal_explanation_claimed": False,
    "minimality_claimed": False,
    "neighborhood_explored": False,
    "contract_promoted": False,
    "qualification_authority": False,
}


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _IDENTIFIER_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )

    return value


def _require_non_empty_string(
    *,
    name: str,
    value: object,
    max_length: int = 200,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > max_length
    ):
        raise HveeContractError(
            f"{name} must be a non-empty trimmed string "
            f"of at most {max_length} characters"
        )

    return value


def _require_sha256_hex(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 hex digest"
        )

    return value


def _canonical_json_value(
    value: object,
    *,
    name: str,
) -> object:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return json.loads(serialized)
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


def _canonical_json(
    value: object,
    *,
    name: str,
) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


def _calculate_sha256(
    value: object,
    *,
    name: str,
) -> str:
    canonical = _canonical_json(
        value,
        name=name,
    )
    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _canonical_scenario_parameters(
    value: object,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HveeContractError(
            "scenario parameters must be a JSON object"
        )

    normalized: dict[str, object] = {}

    for key, parameter in value.items():
        normalized_key = _require_identifier(
            name="scenario parameter key",
            value=key,
        )

        if parameter is None or isinstance(
            parameter,
            (bool, int, str),
        ):
            normalized_parameter = parameter
        elif isinstance(parameter, float):
            if not math.isfinite(parameter):
                raise HveeContractError(
                    "numeric scenario parameters must be finite"
                )
            normalized_parameter = parameter
        else:
            raise HveeContractError(
                "scenario parameters must be scalar JSON values"
            )

        if isinstance(normalized_parameter, str):
            _require_non_empty_string(
                name="string scenario parameter",
                value=normalized_parameter,
            )

        normalized[normalized_key] = normalized_parameter

    canonical = _canonical_json_value(
        normalized,
        name="scenario parameters",
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            "scenario parameters must be a JSON object"
        )

    return canonical


@dataclass(frozen=True, slots=True)
class CounterexampleFailure:
    """One versioned failure claim supported by observation evidence."""

    key: str
    version: str
    reason_code: str
    metric_key: str
    metric_version: str
    evaluator_key: str
    evaluator_version: str

    def __post_init__(self) -> None:
        for name, value in (
            ("failure key", self.key),
            ("failure reason code", self.reason_code),
            ("metric key", self.metric_key),
            ("evaluator key", self.evaluator_key),
        ):
            _require_identifier(
                name=name,
                value=value,
            )

        for name, value in (
            ("failure version", self.version),
            ("metric version", self.metric_version),
            ("evaluator version", self.evaluator_version),
        ):
            _require_non_empty_string(
                name=name,
                value=value,
                max_length=100,
            )

    @property
    def identity(
        self,
    ) -> tuple[str, str, str, str, str, str, str]:
        return (
            self.key,
            self.version,
            self.reason_code,
            self.metric_key,
            self.metric_version,
            self.evaluator_key,
            self.evaluator_version,
        )


@dataclass(frozen=True, slots=True)
class CounterexampleEvidenceBundle:
    payload: dict[str, object]
    scenario_sha256: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "counterexample evidence payload must be a JSON object"
            )

        _require_sha256_hex(
            name="scenario SHA-256",
            value=self.scenario_sha256,
        )
        _require_sha256_hex(
            name="counterexample SHA-256",
            value=self.sha256,
        )


def calculate_scenario_sha256(
    *,
    scenario_key: str,
    scenario_version: str,
    case_id: str,
    parameters: dict[str, object],
) -> str:
    body = {
        "key": _require_identifier(
            name="scenario key",
            value=scenario_key,
        ),
        "version": _require_non_empty_string(
            name="scenario version",
            value=scenario_version,
            max_length=100,
        ),
        "case_id": _require_non_empty_string(
            name="scenario case id",
            value=case_id,
        ),
        "parameters": _canonical_scenario_parameters(
            parameters
        ),
    }

    return _calculate_sha256(
        body,
        name="scenario identity",
    )


def calculate_counterexample_evidence_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="counterexample evidence",
    )


def _failure_payload(
    failure: CounterexampleFailure,
) -> dict[str, object]:
    return {
        "key": failure.key,
        "version": failure.version,
        "reason_code": failure.reason_code,
        "metric": {
            "key": failure.metric_key,
            "version": failure.metric_version,
        },
        "evaluator": {
            "key": failure.evaluator_key,
            "version": failure.evaluator_version,
        },
    }


def build_counterexample_evidence_bundle(
    *,
    evaluation_type: str,
    scenario_key: str,
    scenario_version: str,
    case_id: str,
    parameters: dict[str, object],
    result_provenance_sha256: str,
    observation_evidence_sha256: str,
    decision_evidence_sha256: str,
    failures: list[CounterexampleFailure]
    | tuple[CounterexampleFailure, ...],
) -> CounterexampleEvidenceBundle:
    normalized_evaluation_type = _require_identifier(
        name="evaluation type",
        value=evaluation_type,
    )
    normalized_scenario_key = _require_identifier(
        name="scenario key",
        value=scenario_key,
    )
    normalized_scenario_version = _require_non_empty_string(
        name="scenario version",
        value=scenario_version,
        max_length=100,
    )
    normalized_case_id = _require_non_empty_string(
        name="scenario case id",
        value=case_id,
    )
    normalized_parameters = _canonical_scenario_parameters(
        parameters
    )

    normalized_provenance_sha256 = _require_sha256_hex(
        name="result provenance SHA-256",
        value=result_provenance_sha256,
    )
    normalized_observation_sha256 = _require_sha256_hex(
        name="observation evidence SHA-256",
        value=observation_evidence_sha256,
    )
    normalized_decision_sha256 = _require_sha256_hex(
        name="decision evidence SHA-256",
        value=decision_evidence_sha256,
    )

    if (
        not isinstance(failures, (list, tuple))
        or not failures
        or not all(
            isinstance(failure, CounterexampleFailure)
            for failure in failures
        )
    ):
        raise HveeContractError(
            "counterexample evidence requires failure claims"
        )

    ordered_failures = sorted(
        failures,
        key=lambda failure: failure.identity,
    )
    identities = tuple(
        failure.identity
        for failure in ordered_failures
    )

    if len(identities) != len(set(identities)):
        raise HveeContractError(
            "counterexample failure identities must be unique"
        )

    scenario_body = {
        "key": normalized_scenario_key,
        "version": normalized_scenario_version,
        "case_id": normalized_case_id,
        "parameters": normalized_parameters,
    }
    scenario_sha256 = _calculate_sha256(
        scenario_body,
        name="scenario identity",
    )

    payload: dict[str, object] = {
        "schema_version": COUNTEREXAMPLE_EVIDENCE_SCHEMA_VERSION,
        "type": "counterexample_evidence",
        "evaluation_type": normalized_evaluation_type,
        "scenario": {
            **scenario_body,
            "sha256": scenario_sha256,
        },
        "evidence": {
            "result_provenance_sha256": (
                normalized_provenance_sha256
            ),
            "observation_evidence_sha256": (
                normalized_observation_sha256
            ),
        },
        "failures": [
            _failure_payload(failure)
            for failure in ordered_failures
        ],
        "decision": {
            "verdict": DecisionVerdict.FAIL.value,
            "evidence_sha256": normalized_decision_sha256,
        },
        "evidence_boundary": dict(_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="counterexample evidence",
    )

    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "counterexample evidence must be a JSON object"
        )

    return CounterexampleEvidenceBundle(
        payload=canonical_payload,
        scenario_sha256=scenario_sha256,
        sha256=calculate_counterexample_evidence_sha256(
            canonical_payload
        ),
    )


def _parse_failure(
    value: object,
) -> CounterexampleFailure:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "key",
            "version",
            "reason_code",
            "metric",
            "evaluator",
        }
    ):
        raise HveeContractError(
            "invalid counterexample failure shape"
        )

    metric = value.get("metric")
    evaluator = value.get("evaluator")

    if (
        not isinstance(metric, dict)
        or set(metric) != {"key", "version"}
        or not isinstance(evaluator, dict)
        or set(evaluator) != {"key", "version"}
    ):
        raise HveeContractError(
            "invalid counterexample failure identity"
        )

    return CounterexampleFailure(
        key=value.get("key"),
        version=value.get("version"),
        reason_code=value.get("reason_code"),
        metric_key=metric.get("key"),
        metric_version=metric.get("version"),
        evaluator_key=evaluator.get("key"),
        evaluator_version=evaluator.get("version"),
    )


def verify_counterexample_evidence_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "schema_version",
                "type",
                "evaluation_type",
                "scenario",
                "evidence",
                "failures",
                "decision",
                "evidence_boundary",
            }
            or payload.get("schema_version")
            != COUNTEREXAMPLE_EVIDENCE_SCHEMA_VERSION
            or payload.get("type")
            != "counterexample_evidence"
            or payload.get("evidence_boundary")
            != _EVIDENCE_BOUNDARY
        ):
            return False

        scenario = payload.get("scenario")
        evidence = payload.get("evidence")
        decision = payload.get("decision")
        failures_payload = payload.get("failures")

        if (
            not isinstance(scenario, dict)
            or set(scenario)
            != {
                "key",
                "version",
                "case_id",
                "parameters",
                "sha256",
            }
            or not isinstance(evidence, dict)
            or set(evidence)
            != {
                "result_provenance_sha256",
                "observation_evidence_sha256",
            }
            or not isinstance(decision, dict)
            or set(decision)
            != {"verdict", "evidence_sha256"}
            or decision.get("verdict")
            != DecisionVerdict.FAIL.value
            or not isinstance(failures_payload, list)
        ):
            return False

        failures = tuple(
            _parse_failure(failure)
            for failure in failures_payload
        )

        rebuilt = build_counterexample_evidence_bundle(
            evaluation_type=payload.get("evaluation_type"),
            scenario_key=scenario.get("key"),
            scenario_version=scenario.get("version"),
            case_id=scenario.get("case_id"),
            parameters=scenario.get("parameters"),
            result_provenance_sha256=evidence.get(
                "result_provenance_sha256"
            ),
            observation_evidence_sha256=evidence.get(
                "observation_evidence_sha256"
            ),
            decision_evidence_sha256=decision.get(
                "evidence_sha256"
            ),
            failures=failures,
        )

        stored_scenario_sha256 = _require_sha256_hex(
            name="stored scenario SHA-256",
            value=scenario.get("sha256"),
        )
        normalized_expected_sha256 = _require_sha256_hex(
            name="expected counterexample SHA-256",
            value=expected_sha256,
        )

        return (
            payload == rebuilt.payload
            and stored_scenario_sha256
            == rebuilt.scenario_sha256
            and normalized_expected_sha256
            == rebuilt.sha256
        )

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False
