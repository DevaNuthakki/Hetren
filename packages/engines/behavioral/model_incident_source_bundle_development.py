"""Portable source evidence for offline incident development controls.

This module reconstructs explicitly allowlisted source records and recomputes
the existing incident evaluation. It does not authenticate providers or claims
of genuine model execution, and it does not write files.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import hmac
import json
import math
import re

from environments.agent.incident_triage import TriageReport

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import EventKind, TraceEvent
from packages.engines.behavioral.incident_multistep_runtime_development import (
    IncidentWorkflowAction,
    IncidentWorkflowObservation,
    IncidentWorkflowState,
    IncidentWorkflowStep,
)
from packages.engines.behavioral.incident_scenario_development import (
    IncidentScenario,
    IncidentScenarioEvaluation,
)
from packages.engines.behavioral.model_incident_control_suite_development import (
    CONTROL_CASES,
    SyntheticControlSuiteResult,
    control_manifest_sha256,
)
from packages.engines.behavioral.model_incident_development_evaluation import (
    IncidentDevelopmentEvaluationInput,
    evaluate_incident_development_cases,
)
from packages.engines.behavioral.model_incident_multistep_recovery_development import (
    CaptureSourceInterruption,
    RecoveryAttempt,
    RecoveryObservation,
    ResilientMultistepIncidentRun,
)
from packages.engines.behavioral.model_incident_provider_observability_development import (
    CaptureCallObservation,
    ObservedResilientIncidentRun,
)
from packages.engines.behavioral.model_incident_portable_report_development import (
    serialize_portable_development_report,
    verify_portable_development_report,
)

SCHEMA_VERSION = 1
RECORD_TYPE = "SyntheticIncidentSourceEvidenceBundle"
REPORT_ID = "a510h-cc-development-v1"
MAX_BUNDLE_BYTES = 1048576
MAX_DEPTH = 96
MAX_NODES = 20000

# Frozen from the successful eight-case source-record inventory.
# Never dynamically import classes named by an untrusted bundle.
_ALLOWED_CLASSES = (
    TriageReport,
    EventKind,
    TraceEvent,
    IncidentWorkflowAction,
    IncidentWorkflowObservation,
    IncidentWorkflowState,
    IncidentWorkflowStep,
    IncidentScenario,
    IncidentScenarioEvaluation,
    IncidentDevelopmentEvaluationInput,
    CaptureSourceInterruption,
    RecoveryAttempt,
    RecoveryObservation,
    ResilientMultistepIncidentRun,
    CaptureCallObservation,
    ObservedResilientIncidentRun,
)

_TYPES = {
    cls.__module__ + "." + cls.__qualname__: cls
    for cls in _ALLOWED_CLASSES
}

if len(_ALLOWED_CLASSES) != 16 or len(_TYPES) != 16:
    raise RuntimeError("fixed evidence type registry is inconsistent")

_ALLOWED_IDENTITIES = frozenset(_ALLOWED_CLASSES)
_CASE_IDS = tuple(definition.case_id for definition in CONTROL_CASES)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _fail(reason: str) -> None:
    raise ContractError(f"synthetic source evidence bundle: {reason}")


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError) as exc:
        raise ContractError("invalid canonical evidence JSON") from exc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _check_digest(value: object, label: str) -> None:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        _fail(f"invalid {label}")


def _anchor(actual: str, expected: str | None, label: str) -> None:
    if expected is not None:
        _check_digest(expected, label)
        if not hmac.compare_digest(actual, expected):
            _fail(f"{label} mismatch")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON object key")
        result[key] = value
    return result


def _read_canonical(raw: bytes) -> object:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BUNDLE_BYTES:
        _fail("bundle must be nonempty bytes within size limit")

    try:
        decoded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: _fail("nonfinite JSON number"),
        )
        if _canonical(decoded) != raw:
            _fail("noncanonical bundle bytes")
        return decoded
    except ContractError:
        raise
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise ContractError("invalid source bundle JSON") from exc


def _tick(depth: int, budget: list[int]) -> None:
    budget[0] += 1
    if depth > MAX_DEPTH or budget[0] > MAX_NODES:
        _fail("source evidence complexity exceeds limit")


def _encode(value, active: set[int], budget: list[int], depth: int = 0):
    _tick(depth, budget)

    if value is None or type(value) in (bool, int, str):
        return value

    if type(value) is float:
        if not math.isfinite(value):
            _fail("nonfinite source evidence float")
        return value

    identity = id(value)
    if identity in active:
        _fail("cyclic source evidence graph")

    active.add(identity)
    try:
        cls = type(value)
        if cls in _ALLOWED_IDENTITIES and is_dataclass(value):
            name = cls.__module__ + "." + cls.__qualname__
            return {
                "$kind": "dataclass",
                "class": name,
                "fields": {
                    field.name: _encode(
                        getattr(value, field.name),
                        active,
                        budget,
                        depth + 1,
                    )
                    for field in fields(value)
                },
            }

        if cls in _ALLOWED_IDENTITIES and isinstance(value, Enum):
            name = cls.__module__ + "." + cls.__qualname__
            return {
                "$kind": "enum",
                "class": name,
                "value": _encode(value.value, active, budget, depth + 1),
            }

        if cls in (tuple, list):
            return {
                "$kind": "tuple" if cls is tuple else "list",
                "items": [
                    _encode(item, active, budget, depth + 1)
                    for item in value
                ],
            }

        if cls is dict:
            return {
                "$kind": "dict",
                "pairs": [
                    [
                        _encode(key, active, budget, depth + 1),
                        _encode(item, active, budget, depth + 1),
                    ]
                    for key, item in value.items()
                ],
            }

        if cls is bytes:
            return {"$kind": "bytes", "hex": value.hex()}

        _fail("source record type is not allowlisted")
    finally:
        active.remove(identity)


def _decode(value, budget: list[int], depth: int = 0):
    _tick(depth, budget)

    if value is None or type(value) in (bool, int, str):
        return value

    if type(value) is float:
        if not math.isfinite(value):
            _fail("nonfinite decoded evidence float")
        return value

    if type(value) is not dict:
        _fail("untagged evidence node")

    kind = value.get("$kind")

    if kind == "dataclass":
        if set(value) != {"$kind", "class", "fields"}:
            _fail("invalid dataclass envelope")
        name = value["class"]
        if type(name) is not str:
            _fail("invalid dataclass identity")
        cls = _TYPES.get(name)
        if cls is None or not is_dataclass(cls):
            _fail("unknown dataclass identity")

        incoming = value["fields"]
        field_specs = fields(cls)
        names = {field.name for field in field_specs}

        if type(incoming) is not dict or set(incoming) != names:
            _fail("dataclass field mismatch")

        restored = {
            name: _decode(item, budget, depth + 1)
            for name, item in incoming.items()
        }

        try:
            obj = cls(**{
                field.name: restored[field.name]
                for field in field_specs
                if field.init
            })
            for field in field_specs:
                if (
                    not field.init
                    and getattr(obj, field.name) != restored[field.name]
                ):
                    _fail("derived dataclass field mismatch")
            return obj
        except ContractError:
            raise
        except (
            TypeError, ValueError, AttributeError, KeyError, OverflowError,
        ) as exc:
            raise ContractError(
                "invalid reconstructed source dataclass"
            ) from exc

    if kind == "enum":
        if set(value) != {"$kind", "class", "value"}:
            _fail("invalid enum envelope")
        name = value["class"]
        if type(name) is not str:
            _fail("invalid enum identity")
        cls = _TYPES.get(name)
        if cls is None or not issubclass(cls, Enum):
            _fail("unknown enum identity")
        try:
            return cls(_decode(value["value"], budget, depth + 1))
        except ContractError:
            raise
        except (TypeError, ValueError) as exc:
            raise ContractError("invalid evidence enum value") from exc

    if kind in ("tuple", "list"):
        if set(value) != {"$kind", "items"}:
            _fail("invalid collection envelope")
        if type(value["items"]) is not list:
            _fail("invalid evidence collection")
        items = [
            _decode(item, budget, depth + 1)
            for item in value["items"]
        ]
        return tuple(items) if kind == "tuple" else items

    if kind == "dict":
        if set(value) != {"$kind", "pairs"}:
            _fail("invalid mapping envelope")
        if type(value["pairs"]) is not list:
            _fail("invalid evidence mapping")

        result = {}
        for pair in value["pairs"]:
            if type(pair) is not list or len(pair) != 2:
                _fail("invalid mapping pair")
            key = _decode(pair[0], budget, depth + 1)
            item = _decode(pair[1], budget, depth + 1)
            try:
                if key in result:
                    _fail("duplicate evidence mapping key")
                result[key] = item
            except TypeError as exc:
                raise ContractError(
                    "unhashable evidence mapping key"
                ) from exc
        return result

    if kind == "bytes":
        if set(value) != {"$kind", "hex"}:
            _fail("invalid bytes envelope")
        encoded = value["hex"]
        if (
            type(encoded) is not str
            or re.fullmatch(r"(?:[0-9a-f]{2})*\Z", encoded) is None
        ):
            _fail("invalid evidence byte encoding")
        return bytes.fromhex(encoded)

    _fail("unsupported evidence node kind")


@dataclass(frozen=True)
class VerifiedSyntheticSourceBundle:
    bundle_document_sha256: str
    report_document_sha256: str
    manifest_sha256: str
    evaluation_sha256: str
    suite_evidence_sha256: str
    case_count: int
    correct_count: int
    provider_authenticated: bool = False


def serialize_synthetic_source_bundle(
    suite: SyntheticControlSuiteResult,
    portable_report: bytes,
) -> bytes:
    """Serialize source inputs associated with the *same* offline execution."""
    if type(suite) is not SyntheticControlSuiteResult:
        _fail("expected exact synthetic suite result")

    verified = verify_portable_development_report(portable_report)

    if (
        suite.manifest_sha256 != control_manifest_sha256()
        or suite.report.report_id != REPORT_ID
        or verified.manifest_sha256 != suite.manifest_sha256
        or verified.evaluation_sha256 != suite.report.report_sha256
        or serialize_portable_development_report(suite) != portable_report
        or tuple(item.case_id for item in suite.inputs) != _CASE_IDS
    ):
        _fail("portable report and source execution do not match")

    source_records = _encode(suite.inputs, set(), [0])

    envelope = {
        "record_type": RECORD_TYPE,
        "schema_version": SCHEMA_VERSION,
        "development_only": True,
        "manifest_sha256": suite.manifest_sha256,
        "evaluation_sha256": suite.report.report_sha256,
        "suite_evidence_sha256": suite.evidence_sha256,
        "report_document_sha256": _sha(portable_report),
        "source_records": source_records,
    }

    raw = _canonical(envelope)
    if len(raw) > MAX_BUNDLE_BYTES:
        _fail("serialized bundle exceeds size limit")
    return raw


def verify_synthetic_source_bundle(
    bundle: bytes,
    portable_report: bytes,
    *,
    expected_bundle_sha256: str | None = None,
    expected_report_sha256: str | None = None,
) -> VerifiedSyntheticSourceBundle:
    """Reconstruct and reevaluate stored source evidence without source calls."""
    parsed = _read_canonical(bundle)
    bundle_digest = _sha(bundle)

    _anchor(bundle_digest, expected_bundle_sha256, "bundle SHA-256")

    portable_verified = verify_portable_development_report(
        portable_report,
        expected_document_sha256=expected_report_sha256,
    )

    if (
        type(parsed) is not dict
        or set(parsed) != {
            "record_type",
            "schema_version",
            "development_only",
            "manifest_sha256",
            "evaluation_sha256",
            "suite_evidence_sha256",
            "report_document_sha256",
            "source_records",
        }
        or parsed["record_type"] != RECORD_TYPE
        or type(parsed["schema_version"]) is not int
        or parsed["schema_version"] != SCHEMA_VERSION
        or parsed["development_only"] is not True
    ):
        _fail("source bundle envelope mismatch")

    for name in (
        "manifest_sha256",
        "evaluation_sha256",
        "suite_evidence_sha256",
        "report_document_sha256",
    ):
        _check_digest(parsed[name], name)

    report_digest = _sha(portable_report)

    if (
        parsed["report_document_sha256"] != report_digest
        or parsed["manifest_sha256"] != portable_verified.manifest_sha256
        or parsed["evaluation_sha256"] != portable_verified.evaluation_sha256
        or parsed["manifest_sha256"] != control_manifest_sha256()
    ):
        _fail("source bundle does not match portable report")

    restored = _decode(parsed["source_records"], [0])

    if (
        type(restored) is not tuple
        or len(restored) != len(_CASE_IDS)
        or any(
            type(item) is not IncidentDevelopmentEvaluationInput
            for item in restored
        )
        or tuple(item.case_id for item in restored) != _CASE_IDS
        or any(item.model != "offline" for item in restored)
    ):
        _fail("source evidence root or case identities invalid")

    rebuilt = evaluate_incident_development_cases(
        report_id=REPORT_ID,
        cases=restored,
    )

    restored_suite = SyntheticControlSuiteResult(
        manifest_sha256=parsed["manifest_sha256"],
        inputs=restored,
        report=rebuilt,
    )

    if (
        rebuilt.report_sha256 != parsed["evaluation_sha256"]
        or restored_suite.evidence_sha256 != parsed["suite_evidence_sha256"]
        or serialize_portable_development_report(restored_suite)
        != portable_report
    ):
        _fail("recomputed evidence or evaluation differs from report")

    return VerifiedSyntheticSourceBundle(
        bundle_document_sha256=bundle_digest,
        report_document_sha256=report_digest,
        manifest_sha256=parsed["manifest_sha256"],
        evaluation_sha256=rebuilt.report_sha256,
        suite_evidence_sha256=restored_suite.evidence_sha256,
        case_count=len(restored),
        correct_count=rebuilt.summary.correct_cases,
        provider_authenticated=False,
    )
