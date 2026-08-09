"""Private-holdout preregistration for Critical Number Fidelity v1.

This module provides deterministic commitments for a private evaluator
holdout.  It deliberately contains no private transcript, expected label,
commitment salt, certification verdict, persistence, or release-enforcement
logic.  A plan is sealed before evaluator outputs exist.  A blind-run receipt
then retains one opaque output commitment for every selected case before
expected results are revealed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
    ASRCriticalNumberAssuranceStatus,
    verify_critical_number_assurance_profile_v1,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    EN_US_CRITICAL_NUMBER_PROFILE,
)


CRITICAL_NUMBER_PRIVATE_HOLDOUT_PLAN_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRIVATE_HOLDOUT_RUN_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_KEY = (
    "hetren.asr.critical-number-private-holdout.en-us"
)
CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_VERSION = "1.0.0"
CRITICAL_NUMBER_PRIVATE_COMMITMENT_SCHEME = "sha256-canonical-json-private-salt-v1"

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_EXPECTED_EVALUATOR_IDENTITY = (
    "hetren.asr.critical-number-fidelity.en-us",
    "1.0.0",
    "asr",
)
_EXPECTED_PROFILE_IDENTITY = (
    "hetren.asr.critical-number-profile.en-us",
    "1.0.0",
    "en",
    "en-US",
)


class ASRCriticalNumberPrivateHoldoutExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    INVALID = "invalid"


def _canonicalize_json_value(value: object, *, name: str) -> object:
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


def _canonical_json(value: object, *, name: str) -> str:
    canonical = _canonicalize_json_value(value, name=name)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _require_identifier(*, name: str, value: object) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise HveeContractError(f"{name} must be a canonical lowercase identifier")
    return value


def _require_version(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 100
    ):
        raise HveeContractError(f"{name} must be a non-empty, trimmed version")
    return value


def calculate_critical_number_private_holdout_sha256(
    payload: object,
) -> str:
    """Hash deterministic private-holdout evidence."""

    canonical = _canonical_json(
        payload,
        name="critical-number private-holdout payload",
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def calculate_critical_number_private_commitment(
    *,
    payload: object,
    private_salt: str,
) -> str:
    """Commit to private JSON without placing its content in an artifact."""

    if not isinstance(private_salt, str) or len(private_salt.encode("utf-8")) < 32:
        raise HveeContractError(
            "critical-number private commitment salt must contain at least "
            "32 UTF-8 bytes"
        )
    canonical_payload = _canonicalize_json_value(
        payload,
        name="critical-number private commitment payload",
    )
    commitment = {
        "domain": CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_KEY,
        "scheme": CRITICAL_NUMBER_PRIVATE_COMMITMENT_SCHEME,
        "payload": canonical_payload,
        "private_salt": private_salt,
    }
    return calculate_critical_number_private_holdout_sha256(commitment)


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateHoldoutCaseCommitment:
    """Opaque commitments for one selected private case."""

    case_token: str
    case_payload_sha256: str
    expected_result_sha256: str
    provenance_sha256: str
    slice_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha256(name="private case token", value=self.case_token)
        _require_sha256(
            name="private case payload commitment",
            value=self.case_payload_sha256,
        )
        _require_sha256(
            name="private expected-result commitment",
            value=self.expected_result_sha256,
        )
        _require_sha256(
            name="private provenance commitment",
            value=self.provenance_sha256,
        )
        if (
            not isinstance(self.slice_keys, tuple)
            or not self.slice_keys
            or not all(
                isinstance(key, str) and _IDENTIFIER_PATTERN.fullmatch(key)
                for key in self.slice_keys
            )
        ):
            raise HveeContractError(
                "private holdout case requires canonical slice keys"
            )
        if tuple(sorted(set(self.slice_keys))) != self.slice_keys:
            raise HveeContractError(
                "private holdout slice keys must be unique and sorted"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateHoldoutPlanDefinition:
    """A caller-owned preregistration with no private contents or labels."""

    plan_id: str
    plan_version: str
    run_id: str
    holdout_set_key: str
    holdout_set_version: str
    holdout_manifest_sha256: str
    population_snapshot_sha256: str
    risk_register_sha256: str
    historical_evidence_sha256: str
    sampling_protocol_sha256: str
    analysis_protocol_sha256: str
    cases: tuple[ASRCriticalNumberPrivateHoldoutCaseCommitment, ...]
    supersedes_plan_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(name="private holdout plan id", value=self.plan_id)
        _require_version(
            name="private holdout plan version",
            value=self.plan_version,
        )
        _require_identifier(name="private holdout run id", value=self.run_id)
        _require_identifier(
            name="private holdout set key",
            value=self.holdout_set_key,
        )
        _require_version(
            name="private holdout set version",
            value=self.holdout_set_version,
        )
        for name, value in (
            ("private holdout manifest", self.holdout_manifest_sha256),
            ("population snapshot", self.population_snapshot_sha256),
            ("risk register", self.risk_register_sha256),
            ("historical evidence", self.historical_evidence_sha256),
            ("sampling protocol", self.sampling_protocol_sha256),
            ("analysis protocol", self.analysis_protocol_sha256),
        ):
            _require_sha256(name=f"{name} SHA-256", value=value)
        if self.supersedes_plan_sha256 is not None:
            _require_sha256(
                name="superseded private holdout plan SHA-256",
                value=self.supersedes_plan_sha256,
            )
        if (
            not isinstance(self.cases, tuple)
            or not self.cases
            or not all(
                isinstance(
                    case,
                    ASRCriticalNumberPrivateHoldoutCaseCommitment,
                )
                for case in self.cases
            )
        ):
            raise HveeContractError("private holdout plan requires case commitments")
        case_tokens = tuple(case.case_token for case in self.cases)
        if tuple(sorted(case_tokens)) != case_tokens:
            raise HveeContractError(
                "private holdout cases must be ordered by case token"
            )
        for name, values in (
            ("case tokens", case_tokens),
            (
                "case payload commitments",
                tuple(case.case_payload_sha256 for case in self.cases),
            ),
            (
                "expected-result commitments",
                tuple(case.expected_result_sha256 for case in self.cases),
            ),
        ):
            if len(values) != len(set(values)):
                raise HveeContractError(f"private holdout {name} must be unique")


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateHoldoutPlanBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        canonical = _canonicalize_json_value(
            self.payload,
            name="critical-number private-holdout plan payload",
        )
        if not isinstance(canonical, dict):
            raise HveeContractError(
                "critical-number private-holdout plan must be an object"
            )
        _require_sha256(
            name="critical-number private-holdout plan SHA-256",
            value=self.sha256,
        )
        expected = calculate_critical_number_private_holdout_sha256(canonical)
        if self.sha256 != expected:
            raise HveeContractError(
                "critical-number private-holdout plan SHA-256 does not "
                "match its payload"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateHoldoutCaseExecution:
    """Opaque evaluator-output evidence captured before label reveal."""

    case_token: str
    status: ASRCriticalNumberPrivateHoldoutExecutionStatus
    evaluator_output_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(name="private run case token", value=self.case_token)
        if not isinstance(
            self.status,
            ASRCriticalNumberPrivateHoldoutExecutionStatus,
        ):
            raise HveeContractError(
                "private holdout execution requires a versioned status"
            )
        _require_sha256(
            name="private evaluator-output commitment",
            value=self.evaluator_output_sha256,
        )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateHoldoutBlindRunDefinition:
    run_id: str
    plan_sha256: str
    executor_manifest_sha256: str
    environment_manifest_sha256: str
    blinding_attestation_sha256: str
    executions: tuple[ASRCriticalNumberPrivateHoldoutCaseExecution, ...]

    def __post_init__(self) -> None:
        _require_identifier(name="private holdout run id", value=self.run_id)
        for name, value in (
            ("private holdout plan", self.plan_sha256),
            ("private executor manifest", self.executor_manifest_sha256),
            ("private environment manifest", self.environment_manifest_sha256),
            ("private blinding attestation", self.blinding_attestation_sha256),
        ):
            _require_sha256(name=f"{name} SHA-256", value=value)
        if (
            not isinstance(self.executions, tuple)
            or not self.executions
            or not all(
                isinstance(
                    execution,
                    ASRCriticalNumberPrivateHoldoutCaseExecution,
                )
                for execution in self.executions
            )
        ):
            raise HveeContractError("private blind run requires case executions")
        case_tokens = tuple(execution.case_token for execution in self.executions)
        if tuple(sorted(case_tokens)) != case_tokens:
            raise HveeContractError(
                "private blind-run executions must be ordered by case token"
            )
        if len(case_tokens) != len(set(case_tokens)):
            raise HveeContractError("private blind-run case tokens must be unique")


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateHoldoutBlindRunBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        canonical = _canonicalize_json_value(
            self.payload,
            name="critical-number private blind-run payload",
        )
        if not isinstance(canonical, dict):
            raise HveeContractError(
                "critical-number private blind run must be an object"
            )
        _require_sha256(
            name="critical-number private blind-run SHA-256",
            value=self.sha256,
        )
        expected = calculate_critical_number_private_holdout_sha256(canonical)
        if self.sha256 != expected:
            raise HveeContractError(
                "critical-number private blind-run SHA-256 does not match its payload"
            )


def _require_v1_bindings() -> str:
    assurance = verify_critical_number_assurance_profile_v1()
    evaluator_identity = (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
    )
    if evaluator_identity != _EXPECTED_EVALUATOR_IDENTITY:
        raise HveeContractError("private holdout evaluator identity changed")
    profile_identity = (
        EN_US_CRITICAL_NUMBER_PROFILE.key,
        EN_US_CRITICAL_NUMBER_PROFILE.version,
        EN_US_CRITICAL_NUMBER_PROFILE.language,
        EN_US_CRITICAL_NUMBER_PROFILE.locale,
    )
    if profile_identity != _EXPECTED_PROFILE_IDENTITY:
        raise HveeContractError("private holdout evaluation profile identity changed")
    if assurance.sha256 != CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1:
        raise HveeContractError("private holdout assurance binding changed")
    profile = assurance.payload.get("assurance_profile")
    if not isinstance(profile, dict) or profile.get("status") != (
        ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value
    ):
        raise HveeContractError(
            "private holdout requires the experimental assurance profile"
        )
    return assurance.sha256


def _bindings(assurance_sha256: str) -> dict[str, object]:
    return {
        "evaluator": {
            "key": CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
            "version": CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
            "evaluation_type": (CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type),
        },
        "evaluation_profile": {
            "key": EN_US_CRITICAL_NUMBER_PROFILE.key,
            "version": EN_US_CRITICAL_NUMBER_PROFILE.version,
            "language": EN_US_CRITICAL_NUMBER_PROFILE.language,
            "locale": EN_US_CRITICAL_NUMBER_PROFILE.locale,
        },
        "assurance_profile": {
            "key": CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
            "version": CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
            "status": ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value,
            "sha256": assurance_sha256,
        },
    }


def _qualification_boundary() -> dict[str, object]:
    return {
        "evaluator_status": (ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value),
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def _slice_counts(
    cases: tuple[ASRCriticalNumberPrivateHoldoutCaseCommitment, ...],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        for key in case.slice_keys:
            counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _case_snapshot(
    case: ASRCriticalNumberPrivateHoldoutCaseCommitment,
) -> dict[str, object]:
    return {
        "case_token": case.case_token,
        "case_payload_sha256": case.case_payload_sha256,
        "expected_result_sha256": case.expected_result_sha256,
        "provenance_sha256": case.provenance_sha256,
        "slice_keys": list(case.slice_keys),
    }


def build_critical_number_private_holdout_plan(
    definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
) -> ASRCriticalNumberPrivateHoldoutPlanBundle:
    """Seal a preregistered sample before evaluator outputs are revealed."""

    if not isinstance(
        definition,
        ASRCriticalNumberPrivateHoldoutPlanDefinition,
    ):
        raise HveeContractError(
            "critical-number private holdout requires a plan definition"
        )
    assurance_sha256 = _require_v1_bindings()
    payload = {
        "schema_version": CRITICAL_NUMBER_PRIVATE_HOLDOUT_PLAN_SCHEMA_VERSION,
        "protocol": {
            "key": CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_VERSION,
            "artifact": "preregistered_private_holdout_plan",
            "commitment_scheme": (CRITICAL_NUMBER_PRIVATE_COMMITMENT_SCHEME),
        },
        "bindings": _bindings(assurance_sha256),
        "preregistration": {
            "plan_id": definition.plan_id,
            "plan_version": definition.plan_version,
            "run_id": definition.run_id,
            "supersedes_plan_sha256": definition.supersedes_plan_sha256,
            "holdout_set": {
                "key": definition.holdout_set_key,
                "version": definition.holdout_set_version,
                "manifest_sha256": definition.holdout_manifest_sha256,
            },
            "design_commitments": {
                "population_snapshot_sha256": (definition.population_snapshot_sha256),
                "risk_register_sha256": definition.risk_register_sha256,
                "historical_evidence_sha256": (definition.historical_evidence_sha256),
                "sampling_protocol_sha256": (definition.sampling_protocol_sha256),
                "analysis_protocol_sha256": (definition.analysis_protocol_sha256),
            },
            "selected_sample": {
                "case_count": len(definition.cases),
                "slice_counts": _slice_counts(definition.cases),
                "cases": [_case_snapshot(case) for case in definition.cases],
            },
            "locks": {
                "sealed_before_evaluator_outputs": True,
                "case_replacement_after_seal_allowed": False,
                "expected_result_change_after_seal_allowed": False,
                "post_reveal_plan_tuning_allowed": False,
                "redesign_requires_new_plan_and_run": True,
            },
        },
        "confidentiality": {
            "private_case_content_in_artifact": False,
            "expected_results_in_artifact": False,
            "private_salts_in_artifact": False,
            "salted_commitments_only": True,
        },
        "qualification": _qualification_boundary(),
    }
    canonical = _canonicalize_json_value(
        payload,
        name="critical-number private-holdout plan payload",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError(
            "critical-number private-holdout plan must canonicalize to an object"
        )
    return ASRCriticalNumberPrivateHoldoutPlanBundle(
        payload=canonical,
        sha256=calculate_critical_number_private_holdout_sha256(canonical),
    )


def verify_critical_number_private_holdout_plan(
    *,
    payload: object,
    expected_sha256: object,
    definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
) -> ASRCriticalNumberPrivateHoldoutPlanBundle:
    """Rebuild a preregistration and require exact evidence equality."""

    expected_digest = _require_sha256(
        name="expected private-holdout plan SHA-256",
        value=expected_sha256,
    )
    supplied = _canonicalize_json_value(
        payload,
        name="supplied private-holdout plan payload",
    )
    if not isinstance(supplied, dict):
        raise HveeContractError("supplied private-holdout plan must be an object")
    if calculate_critical_number_private_holdout_sha256(supplied) != expected_digest:
        raise HveeContractError(
            "supplied private-holdout plan does not match expected SHA-256"
        )
    rebuilt = build_critical_number_private_holdout_plan(definition)
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "private-holdout plan does not match the preregistered definition"
        )
    return rebuilt


def build_critical_number_private_holdout_plan_revision(
    *,
    previous_plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    previous_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    revised_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
) -> ASRCriticalNumberPrivateHoldoutPlanBundle:
    """Require a new plan identity and run for any post-seal redesign."""

    if not isinstance(
        previous_plan,
        ASRCriticalNumberPrivateHoldoutPlanBundle,
    ):
        raise HveeContractError(
            "private holdout revision requires the previous sealed plan"
        )
    verify_critical_number_private_holdout_plan(
        payload=previous_plan.payload,
        expected_sha256=previous_plan.sha256,
        definition=previous_definition,
    )
    if revised_definition.supersedes_plan_sha256 != previous_plan.sha256:
        raise HveeContractError(
            "revised private holdout plan must bind the previous plan SHA-256"
        )
    if (
        revised_definition.plan_id,
        revised_definition.plan_version,
    ) == (
        previous_definition.plan_id,
        previous_definition.plan_version,
    ):
        raise HveeContractError(
            "revised private holdout plan requires a new plan identity"
        )
    if revised_definition.run_id == previous_definition.run_id:
        raise HveeContractError("revised private holdout plan requires a new run id")
    return build_critical_number_private_holdout_plan(revised_definition)


def _execution_snapshot(
    execution: ASRCriticalNumberPrivateHoldoutCaseExecution,
) -> dict[str, object]:
    return {
        "case_token": execution.case_token,
        "status": execution.status.value,
        "evaluator_output_sha256": execution.evaluator_output_sha256,
    }


def _execution_counts(
    executions: tuple[ASRCriticalNumberPrivateHoldoutCaseExecution, ...],
) -> dict[str, int]:
    return {
        status.value: sum(execution.status == status for execution in executions)
        for status in ASRCriticalNumberPrivateHoldoutExecutionStatus
    }


def build_critical_number_private_holdout_blind_run(
    *,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
) -> ASRCriticalNumberPrivateHoldoutBlindRunBundle:
    """Seal every selected evaluator output before expected-result reveal."""

    if not isinstance(plan, ASRCriticalNumberPrivateHoldoutPlanBundle):
        raise HveeContractError(
            "critical-number private blind run requires a sealed plan"
        )
    if not isinstance(
        run_definition,
        ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    ):
        raise HveeContractError(
            "critical-number private blind run requires a run definition"
        )
    verified_plan = verify_critical_number_private_holdout_plan(
        payload=plan.payload,
        expected_sha256=plan.sha256,
        definition=plan_definition,
    )
    if run_definition.plan_sha256 != verified_plan.sha256:
        raise HveeContractError("private blind run does not bind the sealed plan")
    if run_definition.run_id != plan_definition.run_id:
        raise HveeContractError(
            "private blind run id does not match the preregistered run"
        )
    planned_tokens = tuple(case.case_token for case in plan_definition.cases)
    executed_tokens = tuple(
        execution.case_token for execution in run_definition.executions
    )
    if executed_tokens != planned_tokens:
        raise HveeContractError(
            "private blind run must retain every preregistered case exactly"
        )

    assurance_sha256 = _require_v1_bindings()
    payload = {
        "schema_version": CRITICAL_NUMBER_PRIVATE_HOLDOUT_RUN_SCHEMA_VERSION,
        "protocol": {
            "key": CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_VERSION,
            "artifact": "blind_private_holdout_run",
            "commitment_scheme": (CRITICAL_NUMBER_PRIVATE_COMMITMENT_SCHEME),
        },
        "bindings": _bindings(assurance_sha256),
        "plan": {
            "plan_id": plan_definition.plan_id,
            "plan_version": plan_definition.plan_version,
            "run_id": run_definition.run_id,
            "plan_sha256": verified_plan.sha256,
        },
        "execution": {
            "executor_manifest_sha256": (run_definition.executor_manifest_sha256),
            "environment_manifest_sha256": (run_definition.environment_manifest_sha256),
            "blinding_attestation_sha256": (run_definition.blinding_attestation_sha256),
            "selected_case_count": len(plan_definition.cases),
            "retained_case_count": len(run_definition.executions),
            "status_counts": _execution_counts(run_definition.executions),
            "cases": [
                _execution_snapshot(execution)
                for execution in run_definition.executions
            ],
        },
        "blinding": {
            "sealed_before_expected_result_reveal": True,
            "expected_results_in_artifact": False,
            "evaluator_outputs_in_artifact": False,
            "evaluator_output_commitments_only": True,
            "all_selected_cases_retained": True,
            "failed_case_replacement_allowed": False,
        },
        "qualification": _qualification_boundary(),
    }
    canonical = _canonicalize_json_value(
        payload,
        name="critical-number private blind-run payload",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError(
            "critical-number private blind run must canonicalize to an object"
        )
    return ASRCriticalNumberPrivateHoldoutBlindRunBundle(
        payload=canonical,
        sha256=calculate_critical_number_private_holdout_sha256(canonical),
    )


def verify_critical_number_private_holdout_blind_run(
    *,
    payload: object,
    expected_sha256: object,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
) -> ASRCriticalNumberPrivateHoldoutBlindRunBundle:
    """Rebuild a blind receipt and require exact evidence equality."""

    expected_digest = _require_sha256(
        name="expected private blind-run SHA-256",
        value=expected_sha256,
    )
    supplied = _canonicalize_json_value(
        payload,
        name="supplied private blind-run payload",
    )
    if not isinstance(supplied, dict):
        raise HveeContractError("supplied private blind run must be an object")
    if calculate_critical_number_private_holdout_sha256(supplied) != expected_digest:
        raise HveeContractError(
            "supplied private blind run does not match expected SHA-256"
        )
    rebuilt = build_critical_number_private_holdout_blind_run(
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "private blind run does not match the preregistered execution"
        )
    return rebuilt
