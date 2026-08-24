"""Canonical evidence for an observed pass/fail boundary bracket.

An ObservedBoundary contains exactly two executed scenario observations on
one numeric axis.  Their verdicts differ, so the pair brackets a transition
that was actually observed.  The contract deliberately makes no claim about
unexecuted values, interpolation, causality, minimality, or qualification.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict


OBSERVED_BOUNDARY_SCHEMA_VERSION = 1

_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)

_EVIDENCE_BOUNDARY = {
    "observed_endpoint_count": 2,
    "unobserved_values_evaluated": False,
    "interpolation_claimed": False,
    "causal_boundary_claimed": False,
    "minimality_claimed": False,
    "qualification_authority": False,
}


class BoundaryDirection(StrEnum):
    PASS_TO_FAIL = "pass_to_fail"
    FAIL_TO_PASS = "fail_to_pass"


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


def _canonical_invariant_parameters(
    value: object,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HveeContractError(
            "boundary invariant parameters must be a JSON object"
        )

    normalized: dict[str, object] = {}

    for key, parameter in value.items():
        normalized_key = _require_identifier(
            name="boundary invariant parameter key",
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
                    "numeric invariant parameters must be finite"
                )
            normalized_parameter = parameter
        else:
            raise HveeContractError(
                "boundary invariant parameters must be "
                "scalar JSON values"
            )

        if isinstance(normalized_parameter, str):
            _require_non_empty_string(
                name="string invariant parameter",
                value=normalized_parameter,
            )

        normalized[normalized_key] = normalized_parameter

    canonical = _canonical_json_value(
        normalized,
        name="boundary invariant parameters",
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            "boundary invariant parameters must be a JSON object"
        )

    return canonical


def _normalize_axis_value(
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise HveeContractError(
            "boundary axis values must be finite numbers"
        )

    normalized = float(value)
    return 0.0 if normalized == 0.0 else normalized


@dataclass(frozen=True, slots=True)
class ObservedBoundaryEndpoint:
    axis_value: int | float
    scenario_sha256: str
    verdict: DecisionVerdict
    result_provenance_sha256: str
    observation_evidence_sha256: str
    decision_evidence_sha256: str
    counterexample_evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        _normalize_axis_value(self.axis_value)

        for name, value in (
            ("scenario SHA-256", self.scenario_sha256),
            (
                "result provenance SHA-256",
                self.result_provenance_sha256,
            ),
            (
                "observation evidence SHA-256",
                self.observation_evidence_sha256,
            ),
            (
                "decision evidence SHA-256",
                self.decision_evidence_sha256,
            ),
        ):
            _require_sha256_hex(
                name=name,
                value=value,
            )

        if self.verdict not in {
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        }:
            raise HveeContractError(
                "boundary endpoints require pass or fail verdicts"
            )

        if self.verdict == DecisionVerdict.FAIL:
            _require_sha256_hex(
                name="counterexample evidence SHA-256",
                value=self.counterexample_evidence_sha256,
            )
        elif self.counterexample_evidence_sha256 is not None:
            raise HveeContractError(
                "passing boundary endpoints cannot reference "
                "counterexample evidence"
            )


@dataclass(frozen=True, slots=True)
class ObservedBoundaryBundle:
    payload: dict[str, object]
    invariant_parameters_sha256: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "observed boundary payload must be a JSON object"
            )

        _require_sha256_hex(
            name="invariant parameters SHA-256",
            value=self.invariant_parameters_sha256,
        )
        _require_sha256_hex(
            name="observed boundary SHA-256",
            value=self.sha256,
        )


def calculate_observed_boundary_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="observed boundary",
    )


def _endpoint_payload(
    *,
    position: str,
    endpoint: ObservedBoundaryEndpoint,
) -> dict[str, object]:
    return {
        "position": position,
        "axis_value": _normalize_axis_value(
            endpoint.axis_value
        ),
        "scenario_sha256": endpoint.scenario_sha256,
        "verdict": endpoint.verdict.value,
        "evidence": {
            "result_provenance_sha256": (
                endpoint.result_provenance_sha256
            ),
            "observation_evidence_sha256": (
                endpoint.observation_evidence_sha256
            ),
            "decision_evidence_sha256": (
                endpoint.decision_evidence_sha256
            ),
            "counterexample_evidence_sha256": (
                endpoint.counterexample_evidence_sha256
            ),
        },
    }


def build_observed_boundary_bundle(
    *,
    evaluation_type: str,
    boundary_key: str,
    boundary_version: str,
    search_key: str,
    search_version: str,
    axis_key: str,
    axis_version: str,
    axis_unit: str | None,
    invariant_parameters: dict[str, object],
    endpoints: list[ObservedBoundaryEndpoint]
    | tuple[ObservedBoundaryEndpoint, ...],
) -> ObservedBoundaryBundle:
    normalized_evaluation_type = _require_identifier(
        name="evaluation type",
        value=evaluation_type,
    )
    normalized_boundary_key = _require_identifier(
        name="boundary key",
        value=boundary_key,
    )
    normalized_boundary_version = _require_non_empty_string(
        name="boundary version",
        value=boundary_version,
        max_length=100,
    )
    normalized_search_key = _require_identifier(
        name="search key",
        value=search_key,
    )
    normalized_search_version = _require_non_empty_string(
        name="search version",
        value=search_version,
        max_length=100,
    )
    normalized_axis_key = _require_identifier(
        name="axis key",
        value=axis_key,
    )
    normalized_axis_version = _require_non_empty_string(
        name="axis version",
        value=axis_version,
        max_length=100,
    )

    normalized_axis_unit: str | None = None
    if axis_unit is not None:
        normalized_axis_unit = _require_non_empty_string(
            name="axis unit",
            value=axis_unit,
            max_length=64,
        )

    normalized_invariants = _canonical_invariant_parameters(
        invariant_parameters
    )
    invariant_parameters_sha256 = _calculate_sha256(
        normalized_invariants,
        name="boundary invariant parameters",
    )

    if (
        not isinstance(endpoints, (list, tuple))
        or len(endpoints) != 2
        or not all(
            isinstance(endpoint, ObservedBoundaryEndpoint)
            for endpoint in endpoints
        )
    ):
        raise HveeContractError(
            "observed boundary requires exactly two endpoints"
        )

    ordered = sorted(
        endpoints,
        key=lambda endpoint: _normalize_axis_value(
            endpoint.axis_value
        ),
    )
    lower, upper = ordered
    lower_value = _normalize_axis_value(lower.axis_value)
    upper_value = _normalize_axis_value(upper.axis_value)

    if lower_value == upper_value:
        raise HveeContractError(
            "observed boundary endpoints require distinct axis values"
        )

    if lower.verdict == upper.verdict:
        raise HveeContractError(
            "observed boundary endpoints require different verdicts"
        )

    if lower.scenario_sha256 == upper.scenario_sha256:
        raise HveeContractError(
            "observed boundary endpoints require distinct scenarios"
        )

    width = upper_value - lower_value
    if not math.isfinite(width) or width <= 0.0:
        raise HveeContractError(
            "observed boundary interval width must be finite and positive"
        )

    direction = (
        BoundaryDirection.PASS_TO_FAIL
        if lower.verdict == DecisionVerdict.PASS
        else BoundaryDirection.FAIL_TO_PASS
    )

    payload: dict[str, object] = {
        "schema_version": OBSERVED_BOUNDARY_SCHEMA_VERSION,
        "type": "observed_boundary",
        "evaluation_type": normalized_evaluation_type,
        "boundary": {
            "key": normalized_boundary_key,
            "version": normalized_boundary_version,
            "status": "bracketed",
            "direction": direction.value,
        },
        "search": {
            "key": normalized_search_key,
            "version": normalized_search_version,
        },
        "axis": {
            "key": normalized_axis_key,
            "version": normalized_axis_version,
            "unit": normalized_axis_unit,
            "interval": {
                "lower": lower_value,
                "upper": upper_value,
                "width": width,
            },
        },
        "invariants": {
            "parameters": normalized_invariants,
            "sha256": invariant_parameters_sha256,
        },
        "endpoints": [
            _endpoint_payload(
                position="lower",
                endpoint=lower,
            ),
            _endpoint_payload(
                position="upper",
                endpoint=upper,
            ),
        ],
        "evidence_boundary": dict(_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="observed boundary",
    )

    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "observed boundary must be a JSON object"
        )

    return ObservedBoundaryBundle(
        payload=canonical_payload,
        invariant_parameters_sha256=(
            invariant_parameters_sha256
        ),
        sha256=calculate_observed_boundary_sha256(
            canonical_payload
        ),
    )


def _parse_endpoint(
    value: object,
) -> ObservedBoundaryEndpoint:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "position",
            "axis_value",
            "scenario_sha256",
            "verdict",
            "evidence",
        }
        or value.get("position") not in {"lower", "upper"}
    ):
        raise HveeContractError(
            "invalid observed boundary endpoint shape"
        )

    evidence = value.get("evidence")
    if (
        not isinstance(evidence, dict)
        or set(evidence)
        != {
            "result_provenance_sha256",
            "observation_evidence_sha256",
            "decision_evidence_sha256",
            "counterexample_evidence_sha256",
        }
    ):
        raise HveeContractError(
            "invalid observed boundary endpoint evidence"
        )

    return ObservedBoundaryEndpoint(
        axis_value=value.get("axis_value"),
        scenario_sha256=value.get("scenario_sha256"),
        verdict=DecisionVerdict(value.get("verdict")),
        result_provenance_sha256=evidence.get(
            "result_provenance_sha256"
        ),
        observation_evidence_sha256=evidence.get(
            "observation_evidence_sha256"
        ),
        decision_evidence_sha256=evidence.get(
            "decision_evidence_sha256"
        ),
        counterexample_evidence_sha256=evidence.get(
            "counterexample_evidence_sha256"
        ),
    )


def verify_observed_boundary_bundle(
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
                "boundary",
                "search",
                "axis",
                "invariants",
                "endpoints",
                "evidence_boundary",
            }
            or payload.get("schema_version")
            != OBSERVED_BOUNDARY_SCHEMA_VERSION
            or payload.get("type") != "observed_boundary"
            or payload.get("evidence_boundary")
            != _EVIDENCE_BOUNDARY
        ):
            return False

        boundary = payload.get("boundary")
        search = payload.get("search")
        axis = payload.get("axis")
        invariants = payload.get("invariants")
        endpoint_payloads = payload.get("endpoints")

        if (
            not isinstance(boundary, dict)
            or set(boundary)
            != {"key", "version", "status", "direction"}
            or boundary.get("status") != "bracketed"
            or not isinstance(search, dict)
            or set(search) != {"key", "version"}
            or not isinstance(axis, dict)
            or set(axis)
            != {"key", "version", "unit", "interval"}
            or not isinstance(axis.get("interval"), dict)
            or set(axis["interval"])
            != {"lower", "upper", "width"}
            or not isinstance(invariants, dict)
            or set(invariants) != {"parameters", "sha256"}
            or not isinstance(endpoint_payloads, list)
            or len(endpoint_payloads) != 2
        ):
            return False

        endpoints = tuple(
            _parse_endpoint(endpoint)
            for endpoint in endpoint_payloads
        )

        rebuilt = build_observed_boundary_bundle(
            evaluation_type=payload.get("evaluation_type"),
            boundary_key=boundary.get("key"),
            boundary_version=boundary.get("version"),
            search_key=search.get("key"),
            search_version=search.get("version"),
            axis_key=axis.get("key"),
            axis_version=axis.get("version"),
            axis_unit=axis.get("unit"),
            invariant_parameters=invariants.get("parameters"),
            endpoints=endpoints,
        )

        stored_invariant_sha256 = _require_sha256_hex(
            name="stored invariant parameters SHA-256",
            value=invariants.get("sha256"),
        )
        normalized_expected_sha256 = _require_sha256_hex(
            name="expected observed boundary SHA-256",
            value=expected_sha256,
        )

        return (
            payload == rebuilt.payload
            and boundary.get("direction")
            == rebuilt.payload["boundary"]["direction"]
            and stored_invariant_sha256
            == rebuilt.invariant_parameters_sha256
            and normalized_expected_sha256
            == rebuilt.sha256
        )

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False
