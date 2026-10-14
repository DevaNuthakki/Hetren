"""Portable, self-consistent reports for the synthetic incident-control suite.

This only verifies document structure and local evidence links; it cannot prove
provider authenticity, replay raw captures, or grant scientific qualification.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
import re

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.engines.behavioral.model_incident_control_suite_development import (
    CONTROL_CASES,
    SyntheticControlSuiteResult,
    control_manifest_payload,
    control_manifest_sha256,
)
from packages.engines.behavioral.model_incident_development_evaluation import (
    IncidentDevelopmentCaseScore,
    IncidentDevelopmentSummary,
)

_KIND = "PortableSyntheticIncidentEvaluation"
_SCHEMA_VERSION = 1
_MAX_BYTES = 262144
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_STATUSES = {
    "completed", "rejected", "interrupted", "recovery_exhausted",
    "budget_exhausted",
}
_INTEGER_CASE_FIELDS = {
    "attempts", "executed_actions", "injected_failures", "rejected_actions",
    "repeated_failed_action_rejections", "interrupted_captures", "capture_calls",
    "calls_with_reported_tokens", "calls_without_reported_tokens",
    "local_capture_elapsed_ns",
}
_INTEGER_SUMMARY_FIELDS = {
    field.name for field in fields(IncidentDevelopmentSummary)
} - {"known_call_token_sum", "complete_reported_tokens"}
_BOOLEAN_CASE_FIELDS = {"completed", "correct", "recovered_correctly"}
_SHA_CASE_FIELDS = {"scenario_sha256", "observed_sha256", "timeline_sha256"}
_OPTIONAL_CASE_FIELDS = {"known_call_token_sum", "complete_reported_tokens"}
_CASE_FIELDS = {field.name for field in fields(IncidentDevelopmentCaseScore)}
_SUMMARY_FIELDS = {field.name for field in fields(IncidentDevelopmentSummary)}
_FIXED_COUNTS = {
    "denominator_cases": 8,
    "correct_cases": 2,
    "completed_cases": 3,
    "completed_incorrect_cases": 1,
    "rejected_cases": 2,
    "interrupted_cases": 1,
    "recovery_exhausted_cases": 1,
    "budget_exhausted_cases": 1,
    "cases_with_injected_failures": 3,
    "recovered_correctly_cases": 1,
    "attempts": 27,
    "executed_actions": 22,
    "injected_failures": 3,
    "rejected_actions": 2,
    "interrupted_captures": 1,
    "capture_calls": 28,
    "calls_with_reported_tokens": 0,
    "calls_without_reported_tokens": 28,
    "repeated_failed_action_rejections": 1,
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _fail(message: str) -> None:
    raise ContractError(f"portable development report: {message}")


def _keys(value: object, expected: set[str], name: str) -> dict:
    if type(value) is not dict or set(value) != expected:
        _fail(f"invalid {name} structure")
    return value


def _sha(value: object, name: str) -> None:
    if type(value) is not str or _HEX.fullmatch(value) is None:
        _fail(f"invalid {name} digest")


def _nonnegative(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        _fail(f"invalid {name} count")


def _optional_count(value: object, name: str) -> None:
    if value is not None:
        _nonnegative(value, name)


def _distinct_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON property")
        result[key] = value
    return result


@dataclass(frozen=True)
class VerifiedPortableDevelopmentReport:
    manifest_sha256: str
    evaluation_sha256: str
    suite_sha256: str
    payload_sha256: str
    document_sha256: str
    case_count: int
    correct_count: int
    record_kind: str = "synthetic_development"

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "checks document integrity and structural consistency only",
            "cannot authenticate origin or reconstruct raw model captures",
            "without a separately trusted digest, a fully rehashed forgery is possible",
            "this offline matrix is not a live provider performance benchmark",
        )


def verify_portable_development_report(
    raw: bytes, *, expected_document_sha256: str | None = None,
) -> VerifiedPortableDevelopmentReport:
    """Fail closed on noncanonical, inconsistent, or unauthenticated-by-anchor bytes.

    If an external trusted digest is supplied, also require exact document identity.
    This does not independently verify model calls or stored source evidence.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_BYTES:
        _fail("invalid JSON byte size")
    if expected_document_sha256 is not None:
        _sha(expected_document_sha256, "trusted document")
        if hashlib.sha256(raw).hexdigest() != expected_document_sha256:
            _fail("trusted document digest mismatch")
    try:
        document = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_distinct_pairs,
            parse_constant=lambda _: _fail("nonfinite JSON number"),
        )
    except ContractError:
        raise
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise ContractError("portable development report: invalid JSON") from exc
    if _canonical_bytes(document) != raw:
        _fail("noncanonical JSON encoding")
    envelope = _keys(document, {"payload", "payload_sha256"}, "envelope")
    payload = _keys(envelope["payload"], {
        "record_type", "schema_version", "dataset_kind", "development_only",
        "manifest", "manifest_sha256", "case_records", "summary", "report",
        "report_sha256", "suite_evidence_sha256", "limitations",
    }, "payload")
    _sha(envelope["payload_sha256"], "payload")
    if envelope["payload_sha256"] != canonical_sha256(payload):
        _fail("payload digest mismatch")
    if (
        payload["record_type"] != _KIND
        or type(payload["schema_version"]) is not int
        or payload["schema_version"] != _SCHEMA_VERSION
        or payload["dataset_kind"] != "synthetic_development"
        or payload["development_only"] is not True
    ):
        _fail("invalid schema or development provenance")
    manifest = payload["manifest"]
    if manifest != control_manifest_payload():
        _fail("fixed control manifest mismatch")
    _sha(payload["manifest_sha256"], "manifest")
    if payload["manifest_sha256"] != control_manifest_sha256():
        _fail("manifest digest mismatch")
    if type(payload["limitations"]) is not list or payload["limitations"] != list(
        _LIMITATIONS
    ):
        _fail("provenance limitations mismatch")
    records = payload["case_records"]
    if type(records) is not list or len(records) != len(CONTROL_CASES):
        _fail("case count mismatch")
    case_digests = []
    case_scores = []
    for index, (record, definition) in enumerate(zip(records, CONTROL_CASES)):
        record = _keys(record, {"score", "case_evidence_sha256"}, "case record")
        score = _keys(record["score"], {
            "record_type", "schema_version", "development_only", *_CASE_FIELDS,
        }, "case score")
        if (
            score["record_type"] != "IncidentDevelopmentCaseScore"
            or type(score["schema_version"]) is not int
            or score["schema_version"] != 1
            or score["development_only"] is not True
            or score["case_id"] != definition.case_id
            or score["status"] != definition.expected_status
            or score["correct"] is not definition.expected_correct
            or score["status"] not in _STATUSES
        ):
            _fail(f"case {index} identity/outcome mismatch")
        for name in _SHA_CASE_FIELDS:
            _sha(score[name], f"case {index} {name}")
        for name in _BOOLEAN_CASE_FIELDS:
            if type(score[name]) is not bool:
                _fail(f"case {index} {name} is not boolean")
        for name in _INTEGER_CASE_FIELDS:
            _nonnegative(score[name], f"case {index} {name}")
        for name in _OPTIONAL_CASE_FIELDS:
            _optional_count(score[name], f"case {index} {name}")
        if (
            score["completed"] != (score["status"] == "completed")
            or (score["correct"] and not score["completed"])
            or score["recovered_correctly"] != (
                score["correct"] and score["injected_failures"] > 0
            )
            or score["attempts"] != (
                score["executed_actions"] + score["injected_failures"]
                + score["rejected_actions"]
            )
            or score["capture_calls"] != (
                score["attempts"] + score["interrupted_captures"]
            )
            or score["repeated_failed_action_rejections"] > score["rejected_actions"]
            or score["interrupted_captures"] != int(score["status"] == "interrupted")
            or score["rejected_actions"] != int(score["status"] == "rejected")
            or score["calls_with_reported_tokens"] != 0
            or score["calls_without_reported_tokens"] != score["capture_calls"]
            or score["complete_reported_tokens"] is not None
            or score["known_call_token_sum"] is not None
        ):
            _fail(f"case {index} internally inconsistent")
        _sha(record["case_evidence_sha256"], f"case {index}")
        if record["case_evidence_sha256"] != canonical_sha256(score):
            _fail(f"case {index} evidence hash mismatch")
        case_digests.append(record["case_evidence_sha256"])
        case_scores.append(score)
    summary = _keys(payload["summary"], _SUMMARY_FIELDS, "summary")
    for name in _INTEGER_SUMMARY_FIELDS:
        _nonnegative(summary[name], f"summary {name}")
    for name in ("known_call_token_sum", "complete_reported_tokens"):
        _optional_count(summary[name], f"summary {name}")
        if summary[name] is not None:
            _fail(f"offline summary cannot claim {name}")
    for name, expected in _FIXED_COUNTS.items():
        if summary[name] != expected:
            _fail(f"synthetic fixed aggregate changed: {name}")
    count_conditions = {
        "correct_cases": sum(x["correct"] for x in case_scores),
        "completed_cases": sum(x["completed"] for x in case_scores),
        "completed_incorrect_cases": sum(
            x["completed"] and not x["correct"] for x in case_scores
        ),
        "rejected_cases": sum(x["status"] == "rejected" for x in case_scores),
        "interrupted_cases": sum(x["status"] == "interrupted" for x in case_scores),
        "recovery_exhausted_cases": sum(
            x["status"] == "recovery_exhausted" for x in case_scores
        ),
        "budget_exhausted_cases": sum(
            x["status"] == "budget_exhausted" for x in case_scores
        ),
        "cases_with_injected_failures": sum(x["injected_failures"] > 0 for x in case_scores),
        "recovered_correctly_cases": sum(x["recovered_correctly"] for x in case_scores),
        "denominator_cases": len(case_scores),
    }
    for name in (
        "attempts", "executed_actions", "injected_failures", "rejected_actions",
        "repeated_failed_action_rejections", "interrupted_captures", "capture_calls",
        "calls_with_reported_tokens", "calls_without_reported_tokens",
        "local_capture_elapsed_ns",
    ):
        count_conditions[name] = sum(x[name] for x in case_scores)
    if any(summary[name] != expected for name, expected in count_conditions.items()):
        _fail("summary does not match cases")
    original_report = _keys(payload["report"], {
        "record_type", "schema_version", "dataset_kind", "report_id",
        "case_evidence_hashes", "summary",
    }, "evaluation report")
    if original_report != {
        "record_type": "IncidentDevelopmentEvaluationReport",
        "schema_version": 1,
        "dataset_kind": "synthetic_development",
        "report_id": "a510h-cc-development-v1",
        "case_evidence_hashes": case_digests,
        "summary": summary,
    }:
        _fail("embedded evaluation report is inconsistent")
    _sha(payload["report_sha256"], "evaluation report")
    if payload["report_sha256"] != canonical_sha256(original_report):
        _fail("evaluation report digest mismatch")
    _sha(payload["suite_evidence_sha256"], "suite")
    if payload["suite_evidence_sha256"] != canonical_sha256({
        "record_type": "SyntheticIncidentControlSuiteResult",
        "schema_version": 1,
        "development_only": True,
        "manifest_sha256": payload["manifest_sha256"],
        "report_sha256": payload["report_sha256"],
    }):
        _fail("suite evidence digest mismatch")
    return VerifiedPortableDevelopmentReport(
        manifest_sha256=payload["manifest_sha256"],
        evaluation_sha256=payload["report_sha256"],
        suite_sha256=payload["suite_evidence_sha256"],
        payload_sha256=envelope["payload_sha256"],
        document_sha256=hashlib.sha256(raw).hexdigest(),
        case_count=len(case_scores),
        correct_count=summary["correct_cases"],
    )


_LIMITATIONS = (
    "offline deterministic fixtures; not live inference",
    "software oracle and synthetic failures; no independent verification",
    "linked evidence hashes are copied, not independently replayed",
    "local wall-clock duration is not server latency",
    "fresh executions may have different report/document digests",
    "document hashes are integrity checks, not signatures or authenticity proofs",
    "no provider usage values or monetary cost claimed",
)


def serialize_portable_development_report(
    result: SyntheticControlSuiteResult,
) -> bytes:
    """Canonical JSON bytes of one already executed synthetic control suite."""
    if not isinstance(result, SyntheticControlSuiteResult):
        _fail("requires exact suite result")
    manifest = control_manifest_payload()
    if result.manifest_sha256 != control_manifest_sha256():
        _fail("suite manifest changed")
    payload = {
        "record_type": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "dataset_kind": "synthetic_development",
        "development_only": True,
        "manifest": manifest,
        "manifest_sha256": result.manifest_sha256,
        "case_records": [
            {
                "score": score.canonical_payload(),
                "case_evidence_sha256": score.case_evidence_sha256,
            }
            for score in result.report.cases
        ],
        "summary": result.report.summary.canonical_payload(),
        "report": result.report.canonical_payload(),
        "report_sha256": result.report.report_sha256,
        "suite_evidence_sha256": result.evidence_sha256,
        "limitations": list(_LIMITATIONS),
    }
    raw = _canonical_bytes({
        "payload": payload,
        "payload_sha256": canonical_sha256(payload),
    })
    verify_portable_development_report(raw)
    return raw
