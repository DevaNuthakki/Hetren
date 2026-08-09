"""Advisory Critical Number evidence for matched ASR releases.

This module reconstructs Critical Number Fidelity v1 evidence from the
versioned observations already bound to baseline and candidate results.  It
produces a separate hypothetical decision for shadow comparison only.  The
official matched-release decision remains unchanged, and this module performs
no persistence or release enforcement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    MetricDefinition,
    ObservationStatus,
)
from hvee.core.decision import (
    CriticalAssessment,
    DecisionInputs,
    DecisionResult,
    EvidenceAssessment,
    IntegrityAssessment,
    decide,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
    ASRCriticalNumberAssuranceStatus,
    verify_critical_number_assurance_profile_v1,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_APPLICABLE_METRIC,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_FINDINGS_METRIC,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    EN_US_CRITICAL_NUMBER_PROFILE,
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberFindingType,
    ASRCriticalNumberReasonCode,
    ASRCriticalNumberType,
)
from hvee.packs.asr.matched_evidence import (
    build_asr_matched_quality_cohorts,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.release_decision import (
    ASRMatchedReleaseDecisionResult,
    evaluate_asr_matched_release_decision,
)


CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_KEY = (
    "hetren.asr.critical-number-matched-release-shadow.en-us"
)
CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_VERSION = "1.0.0"


class ASRCriticalNumberShadowEvidenceState(StrEnum):
    PRESERVED = "preserved"
    VIOLATED = "violated"
    NOT_APPLICABLE = "not_applicable"
    INCONCLUSIVE = "inconclusive"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


class ASRCriticalNumberShadowTransition(StrEnum):
    CLEAR = "clear"
    INTRODUCED_VIOLATION = "introduced_violation"
    PERSISTING_VIOLATION = "persisting_violation"
    CANDIDATE_VIOLATION = "candidate_violation"
    RESOLVED_VIOLATION = "resolved_violation"
    UNRESOLVED = "unresolved"


_REQUIRED_METRICS = (
    CRITICAL_NUMBER_APPLICABLE_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_FINDINGS_METRIC,
)

_DETERMINATE_CLEAR_STATES = frozenset(
    {
        ASRCriticalNumberShadowEvidenceState.PRESERVED,
        ASRCriticalNumberShadowEvidenceState.NOT_APPLICABLE,
    }
)

_INTEGRITY_FAILURE_STATES = frozenset(
    {
        ASRCriticalNumberShadowEvidenceState.DUPLICATE,
        ASRCriticalNumberShadowEvidenceState.INVALID,
    }
)

_PROVEN_ERROR_FINDINGS = frozenset(
    {
        ASRCriticalNumberFindingType.SUBSTITUTION,
        ASRCriticalNumberFindingType.OMISSION,
        ASRCriticalNumberFindingType.INSERTION,
    }
)

_FINDING_KEYS = frozenset(
    {
        "finding_type",
        "reason_code",
        "numeric_type",
        "reference",
        "generated",
        "context_anchor",
        "profile_key",
        "profile_version",
    }
)

_ENTITY_KEYS = frozenset(
    {
        "numeric_type",
        "text",
        "span",
        "canonical_value",
        "canonical_unit",
        "context_before",
        "context_after",
        "issue_reason_code",
    }
)


def _canonical_json(value: object) -> str:
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
            "critical-number shadow findings must be deterministic JSON"
        ) from exc


def _valid_string_list(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str)
        for item in value
    )


def _validate_entity_snapshot(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _ENTITY_KEYS:
        raise HveeContractError(
            "critical-number shadow finding contains an invalid entity"
        )

    try:
        ASRCriticalNumberType(value["numeric_type"])
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "critical-number shadow entity has an invalid numeric type"
        ) from exc

    if not isinstance(value["text"], str):
        raise HveeContractError(
            "critical-number shadow entity text must be a string"
        )

    span = value["span"]
    if (
        not isinstance(span, list)
        or len(span) != 2
        or any(
            isinstance(item, bool)
            or not isinstance(item, int)
            or item < 0
            for item in span
        )
        or span[1] < span[0]
    ):
        raise HveeContractError(
            "critical-number shadow entity span is invalid"
        )

    if not isinstance(value["canonical_value"], str):
        raise HveeContractError(
            "critical-number shadow canonical value must be a string"
        )

    if (
        value["canonical_unit"] is not None
        and not isinstance(value["canonical_unit"], str)
    ):
        raise HveeContractError(
            "critical-number shadow canonical unit is invalid"
        )

    if not _valid_string_list(value["context_before"]):
        raise HveeContractError(
            "critical-number shadow context-before evidence is invalid"
        )

    if not _valid_string_list(value["context_after"]):
        raise HveeContractError(
            "critical-number shadow context-after evidence is invalid"
        )

    issue = value["issue_reason_code"]
    if issue is not None:
        try:
            ASRCriticalNumberReasonCode(issue)
        except (TypeError, ValueError) as exc:
            raise HveeContractError(
                "critical-number shadow entity issue code is invalid"
            ) from exc


def _validate_findings(
    value: object,
) -> tuple[
    str,
    tuple[ASRCriticalNumberFindingType, ...],
]:
    if not isinstance(value, list):
        raise HveeContractError(
            "critical-number shadow findings must be a JSON array"
        )

    finding_types = []

    for finding in value:
        if (
            not isinstance(finding, dict)
            or set(finding) != _FINDING_KEYS
        ):
            raise HveeContractError(
                "critical-number shadow finding has an invalid schema"
            )

        try:
            finding_type = ASRCriticalNumberFindingType(
                finding["finding_type"]
            )
            ASRCriticalNumberReasonCode(finding["reason_code"])
            ASRCriticalNumberType(finding["numeric_type"])
        except (TypeError, ValueError) as exc:
            raise HveeContractError(
                "critical-number shadow finding identity is invalid"
            ) from exc

        if (
            finding["profile_key"]
            != EN_US_CRITICAL_NUMBER_PROFILE.key
            or finding["profile_version"]
            != EN_US_CRITICAL_NUMBER_PROFILE.version
        ):
            raise HveeContractError(
                "critical-number shadow finding uses the wrong profile"
            )

        if not _valid_string_list(finding["context_anchor"]):
            raise HveeContractError(
                "critical-number shadow context anchor is invalid"
            )

        for side in ("reference", "generated"):
            entity = finding[side]
            if entity is not None:
                _validate_entity_snapshot(entity)

        finding_types.append(finding_type)

    return _canonical_json(value), tuple(finding_types)


def _record_matches_metric(
    record: ObservationEvidenceRecord,
    *,
    metric: MetricDefinition,
    evaluation_run_id: int,
    test_case_id: int,
) -> bool:
    return (
        record.metric_key == metric.key
        and record.metric_version == metric.version
        and record.evaluator_key
        == CRITICAL_NUMBER_FIDELITY_EVALUATOR.key
        and record.evaluator_version
        == CRITICAL_NUMBER_FIDELITY_EVALUATOR.version
        and record.evaluation_type
        == CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type
        and record.scope == "test_case"
        and record.evaluation_run_id == evaluation_run_id
        and record.test_case_id == test_case_id
    )


def _invalid_side(
    *,
    evaluation_run_id: int,
    test_case_id: int,
    state: ASRCriticalNumberShadowEvidenceState,
    detail: str,
) -> ASRCriticalNumberShadowSide:
    return ASRCriticalNumberShadowSide(
        evaluation_run_id=evaluation_run_id,
        test_case_id=test_case_id,
        state=state,
        outcome=None,
        findings_json="[]",
        status_detail=detail,
    )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberShadowSide:
    evaluation_run_id: int
    test_case_id: int
    state: ASRCriticalNumberShadowEvidenceState
    outcome: ASRCriticalNumberFidelityOutcome | None
    findings_json: str
    status_detail: str | None

    def __post_init__(self) -> None:
        for name, value in (
            ("evaluation run id", self.evaluation_run_id),
            ("test case id", self.test_case_id),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
            ):
                raise HveeContractError(
                    f"critical-number shadow {name} must be positive"
                )

        if not isinstance(
            self.state,
            ASRCriticalNumberShadowEvidenceState,
        ):
            raise HveeContractError(
                "critical-number shadow side state is invalid"
            )

        if self.outcome is not None and not isinstance(
            self.outcome,
            ASRCriticalNumberFidelityOutcome,
        ):
            raise HveeContractError(
                "critical-number shadow side outcome is invalid"
            )

        try:
            findings = json.loads(self.findings_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise HveeContractError(
                "critical-number shadow findings JSON is invalid"
            ) from exc

        if not isinstance(findings, list):
            raise HveeContractError(
                "critical-number shadow findings JSON must be an array"
            )

        canonical_findings, finding_types = _validate_findings(findings)
        if self.findings_json != canonical_findings:
            raise HveeContractError(
                "critical-number shadow findings JSON is not canonical"
            )

        conclusive_states = {
            ASRCriticalNumberShadowEvidenceState.PRESERVED,
            ASRCriticalNumberShadowEvidenceState.VIOLATED,
            ASRCriticalNumberShadowEvidenceState.NOT_APPLICABLE,
            ASRCriticalNumberShadowEvidenceState.INCONCLUSIVE,
        }
        if self.state in conclusive_states:
            if self.outcome is None:
                raise HveeContractError(
                    "critical-number shadow evidence requires an outcome"
                )
        elif self.outcome is not None or findings:
            raise HveeContractError(
                "unusable critical-number shadow evidence cannot claim "
                "an outcome or findings"
            )

        proven_error = any(
            finding_type in _PROVEN_ERROR_FINDINGS
            for finding_type in finding_types
        )
        uncertain = any(
            finding_type
            in {
                ASRCriticalNumberFindingType.AMBIGUITY,
                ASRCriticalNumberFindingType.UNSUPPORTED,
            }
            for finding_type in finding_types
        )
        valid_state_outcome = {
            ASRCriticalNumberShadowEvidenceState.PRESERVED: (
                self.outcome
                == ASRCriticalNumberFidelityOutcome.PRESERVED
                and bool(finding_types)
                and not proven_error
                and not uncertain
            ),
            ASRCriticalNumberShadowEvidenceState.VIOLATED: (
                self.outcome
                == ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
                and proven_error
            ),
            ASRCriticalNumberShadowEvidenceState.NOT_APPLICABLE: (
                self.outcome
                == ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE
                and not finding_types
            ),
            ASRCriticalNumberShadowEvidenceState.INCONCLUSIVE: (
                self.outcome
                == ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
                and uncertain
                and not proven_error
            ),
        }
        if (
            self.state in conclusive_states
            and not valid_state_outcome[self.state]
        ):
            raise HveeContractError(
                "critical-number shadow state does not match its "
                "outcome and findings"
            )

        if self.state in _INTEGRITY_FAILURE_STATES | {
            ASRCriticalNumberShadowEvidenceState.MISSING,
        }:
            if not isinstance(self.status_detail, str) or not (
                self.status_detail.strip()
            ):
                raise HveeContractError(
                    "unusable critical-number shadow evidence requires "
                    "status detail"
                )

    @property
    def findings(self) -> tuple[dict[str, object], ...]:
        loaded = json.loads(self.findings_json)
        return tuple(loaded)


def _build_side(
    *,
    evaluation_run_id: int,
    test_case_id: int,
    records: tuple[ObservationEvidenceRecord, ...],
) -> ASRCriticalNumberShadowSide:
    selected: dict[str, ObservationEvidenceRecord] = {}
    missing = []

    for metric in _REQUIRED_METRICS:
        matches = tuple(
            record
            for record in records
            if _record_matches_metric(
                record,
                metric=metric,
                evaluation_run_id=evaluation_run_id,
                test_case_id=test_case_id,
            )
        )

        if len(matches) > 1:
            return _invalid_side(
                evaluation_run_id=evaluation_run_id,
                test_case_id=test_case_id,
                state=(
                    ASRCriticalNumberShadowEvidenceState.DUPLICATE
                ),
                detail=(
                    "duplicate critical-number observation for "
                    f"{metric.key}"
                ),
            )

        if not matches:
            missing.append(metric.key)
            continue

        record = matches[0]
        if record.value_type != metric.value_type:
            return _invalid_side(
                evaluation_run_id=evaluation_run_id,
                test_case_id=test_case_id,
                state=ASRCriticalNumberShadowEvidenceState.INVALID,
                detail=(
                    "critical-number observation value type does not "
                    f"match {metric.key}"
                ),
            )

        selected[metric.key] = record

    if missing:
        return _invalid_side(
            evaluation_run_id=evaluation_run_id,
            test_case_id=test_case_id,
            state=ASRCriticalNumberShadowEvidenceState.MISSING,
            detail=(
                "missing critical-number observations: "
                + ", ".join(sorted(missing))
            ),
        )

    applicable = selected[CRITICAL_NUMBER_APPLICABLE_METRIC.key]
    preserved = selected[CRITICAL_NUMBER_PRESERVED_METRIC.key]
    outcome_record = selected[CRITICAL_NUMBER_OUTCOME_METRIC.key]
    findings_record = selected[CRITICAL_NUMBER_FINDINGS_METRIC.key]

    if (
        applicable.status != ObservationStatus.SUCCESS
        or outcome_record.status != ObservationStatus.SUCCESS
        or findings_record.status != ObservationStatus.SUCCESS
    ):
        return _invalid_side(
            evaluation_run_id=evaluation_run_id,
            test_case_id=test_case_id,
            state=ASRCriticalNumberShadowEvidenceState.INVALID,
            detail=(
                "critical-number applicable, outcome, and findings "
                "observations must be successful"
            ),
        )

    try:
        outcome = ASRCriticalNumberFidelityOutcome(outcome_record.value)
        findings_json, finding_types = _validate_findings(
            findings_record.value
        )
    except HveeContractError as exc:
        return _invalid_side(
            evaluation_run_id=evaluation_run_id,
            test_case_id=test_case_id,
            state=ASRCriticalNumberShadowEvidenceState.INVALID,
            detail=str(exc),
        )
    except (TypeError, ValueError):
        return _invalid_side(
            evaluation_run_id=evaluation_run_id,
            test_case_id=test_case_id,
            state=ASRCriticalNumberShadowEvidenceState.INVALID,
            detail="critical-number outcome is invalid",
        )

    proven_error = any(
        finding_type in _PROVEN_ERROR_FINDINGS
        for finding_type in finding_types
    )
    uncertain = any(
        finding_type
        in {
            ASRCriticalNumberFindingType.AMBIGUITY,
            ASRCriticalNumberFindingType.UNSUPPORTED,
        }
        for finding_type in finding_types
    )

    state: ASRCriticalNumberShadowEvidenceState
    expected_applicable: bool

    if outcome == ASRCriticalNumberFidelityOutcome.PRESERVED:
        state = ASRCriticalNumberShadowEvidenceState.PRESERVED
        expected_applicable = True
        valid_preserved = (
            preserved.status == ObservationStatus.SUCCESS
            and preserved.value is True
            and bool(finding_types)
            and not proven_error
            and not uncertain
        )
    elif outcome == ASRCriticalNumberFidelityOutcome.NOT_PRESERVED:
        state = ASRCriticalNumberShadowEvidenceState.VIOLATED
        expected_applicable = True
        valid_preserved = (
            preserved.status == ObservationStatus.SUCCESS
            and preserved.value is False
            and proven_error
        )
    elif outcome == ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE:
        state = ASRCriticalNumberShadowEvidenceState.NOT_APPLICABLE
        expected_applicable = False
        valid_preserved = (
            preserved.status == ObservationStatus.ABSTAINED
            and not finding_types
        )
    else:
        state = ASRCriticalNumberShadowEvidenceState.INCONCLUSIVE
        expected_applicable = True
        valid_preserved = (
            preserved.status
            in {
                ObservationStatus.ABSTAINED,
                ObservationStatus.UNSUPPORTED,
            }
            and not proven_error
            and uncertain
        )

    if applicable.value is not expected_applicable or not valid_preserved:
        return _invalid_side(
            evaluation_run_id=evaluation_run_id,
            test_case_id=test_case_id,
            state=ASRCriticalNumberShadowEvidenceState.INVALID,
            detail=(
                "critical-number observations contain inconsistent "
                "applicability, preservation, outcome, or findings"
            ),
        )

    return ASRCriticalNumberShadowSide(
        evaluation_run_id=evaluation_run_id,
        test_case_id=test_case_id,
        state=state,
        outcome=outcome,
        findings_json=findings_json,
        status_detail=preserved.status_detail,
    )


def _transition(
    *,
    baseline: ASRCriticalNumberShadowSide,
    candidate: ASRCriticalNumberShadowSide,
) -> ASRCriticalNumberShadowTransition:
    baseline_violated = (
        baseline.state
        == ASRCriticalNumberShadowEvidenceState.VIOLATED
    )
    candidate_violated = (
        candidate.state
        == ASRCriticalNumberShadowEvidenceState.VIOLATED
    )
    baseline_clear = baseline.state in _DETERMINATE_CLEAR_STATES
    candidate_clear = candidate.state in _DETERMINATE_CLEAR_STATES

    if candidate_violated:
        if baseline_violated:
            return (
                ASRCriticalNumberShadowTransition.PERSISTING_VIOLATION
            )
        if baseline_clear:
            return (
                ASRCriticalNumberShadowTransition.INTRODUCED_VIOLATION
            )
        return ASRCriticalNumberShadowTransition.CANDIDATE_VIOLATION

    if candidate_clear and baseline_violated:
        return ASRCriticalNumberShadowTransition.RESOLVED_VIOLATION

    if candidate_clear and baseline_clear:
        return ASRCriticalNumberShadowTransition.CLEAR

    return ASRCriticalNumberShadowTransition.UNRESOLVED


def _build_case(
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    test_case_id: int,
    records: tuple[ObservationEvidenceRecord, ...],
) -> ASRCriticalNumberShadowCase:
    baseline = _build_side(
        evaluation_run_id=baseline_run_id,
        test_case_id=test_case_id,
        records=records,
    )
    candidate = _build_side(
        evaluation_run_id=candidate_run_id,
        test_case_id=test_case_id,
        records=records,
    )

    return ASRCriticalNumberShadowCase(
        test_case_id=test_case_id,
        baseline=baseline,
        candidate=candidate,
        transition=_transition(
            baseline=baseline,
            candidate=candidate,
        ),
    )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberShadowCase:
    test_case_id: int
    baseline: ASRCriticalNumberShadowSide
    candidate: ASRCriticalNumberShadowSide
    transition: ASRCriticalNumberShadowTransition

    def __post_init__(self) -> None:
        if (
            isinstance(self.test_case_id, bool)
            or not isinstance(self.test_case_id, int)
            or self.test_case_id < 1
        ):
            raise HveeContractError(
                "critical-number shadow case id must be positive"
            )

        if (
            self.baseline.test_case_id != self.test_case_id
            or self.candidate.test_case_id != self.test_case_id
            or self.baseline.evaluation_run_id
            == self.candidate.evaluation_run_id
        ):
            raise HveeContractError(
                "critical-number shadow case has invalid matched targets"
            )

        if self.transition != _transition(
            baseline=self.baseline,
            candidate=self.candidate,
        ):
            raise HveeContractError(
                "critical-number shadow case transition is inconsistent"
            )


def _derive_shadow_assessments(
    cases: tuple[ASRCriticalNumberShadowCase, ...],
) -> tuple[
    IntegrityAssessment,
    EvidenceAssessment,
    CriticalAssessment | None,
]:
    # The release invariant concerns the candidate.  Baseline Critical Number
    # evidence is diagnostic context for transitions; a baseline rollout gap
    # must not hide a conclusive candidate result.
    candidate_states = tuple(
        case.candidate.state
        for case in cases
    )

    integrity = (
        IntegrityAssessment.INVALID
        if any(
            state in _INTEGRITY_FAILURE_STATES
            for state in candidate_states
        )
        else IntegrityAssessment.VALID
    )

    if any(
        state == ASRCriticalNumberShadowEvidenceState.VIOLATED
        for state in candidate_states
    ):
        critical = CriticalAssessment.VIOLATED
    elif all(
        state in _DETERMINATE_CLEAR_STATES
        for state in candidate_states
    ):
        critical = CriticalAssessment.CLEAR
    else:
        critical = None

    evidence = (
        EvidenceAssessment.SUFFICIENT
        if critical is not None
        else EvidenceAssessment.INSUFFICIENT
    )

    return integrity, evidence, critical


def _hypothetical_decision(
    *,
    official: ASRMatchedReleaseDecisionResult,
    critical_integrity: IntegrityAssessment,
    critical_evidence: EvidenceAssessment,
    hypothetical_critical: CriticalAssessment | None,
) -> DecisionResult:
    integrity = (
        IntegrityAssessment.INVALID
        if (
            official.assurance.integrity
            == IntegrityAssessment.INVALID
            or critical_integrity == IntegrityAssessment.INVALID
        )
        else IntegrityAssessment.VALID
    )
    evidence = (
        EvidenceAssessment.INSUFFICIENT
        if (
            official.assurance.evidence
            == EvidenceAssessment.INSUFFICIENT
            or critical_evidence == EvidenceAssessment.INSUFFICIENT
        )
        else EvidenceAssessment.SUFFICIENT
    )

    return decide(
        DecisionInputs(
            integrity=integrity,
            critical=(
                hypothetical_critical
                if hypothetical_critical is not None
                else CriticalAssessment.CLEAR
            ),
            evidence=evidence,
            claim=official.assurance.claim,
        )
    )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberMatchedReleaseShadowResult:
    shadow_key: str
    shadow_version: str
    assurance_profile_key: str
    assurance_profile_version: str
    assurance_status: ASRCriticalNumberAssuranceStatus
    assurance_sha256: str
    production_qualified: bool
    release_enforcement_eligible: bool
    official: ASRMatchedReleaseDecisionResult
    cases: tuple[ASRCriticalNumberShadowCase, ...]
    critical_integrity: IntegrityAssessment
    critical_evidence: EvidenceAssessment
    hypothetical_critical: CriticalAssessment | None
    hypothetical_decision: DecisionResult
    would_change_official_decision: bool

    def __post_init__(self) -> None:
        if (
            self.shadow_key
            != CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_KEY
            or self.shadow_version
            != CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_VERSION
        ):
            raise HveeContractError(
                "critical-number matched-release shadow identity changed"
            )

        if (
            self.assurance_profile_key
            != CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY
            or self.assurance_profile_version
            != CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION
            or self.assurance_status
            != ASRCriticalNumberAssuranceStatus.EXPERIMENTAL
            or self.production_qualified is not False
            or self.release_enforcement_eligible is not False
        ):
            raise HveeContractError(
                "critical-number matched-release shadow must remain "
                "experimental and non-enforcing"
            )

        if self.assurance_sha256 != (
            CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
        ):
            raise HveeContractError(
                "critical-number shadow assurance digest is not the "
                "sealed v1 artifact"
            )

        if not isinstance(
            self.official,
            ASRMatchedReleaseDecisionResult,
        ):
            raise HveeContractError(
                "critical-number shadow requires an official decision"
            )

        expected_case_ids = self.official.assurance.declared_test_case_ids
        if tuple(case.test_case_id for case in self.cases) != (
            expected_case_ids
        ):
            raise HveeContractError(
                "critical-number shadow cases must match the official cohort"
            )

        for case in self.cases:
            if (
                case.baseline.evaluation_run_id
                != self.official.assurance.baseline_run_id
                or case.candidate.evaluation_run_id
                != self.official.assurance.candidate_run_id
            ):
                raise HveeContractError(
                    "critical-number shadow cases use the wrong run pair"
                )

        expected_integrity, expected_evidence, expected_critical = (
            _derive_shadow_assessments(self.cases)
        )
        if (
            self.critical_integrity != expected_integrity
            or self.critical_evidence != expected_evidence
            or self.hypothetical_critical != expected_critical
        ):
            raise HveeContractError(
                "critical-number shadow assessments are inconsistent"
            )

        expected_decision = _hypothetical_decision(
            official=self.official,
            critical_integrity=expected_integrity,
            critical_evidence=expected_evidence,
            hypothetical_critical=expected_critical,
        )
        if self.hypothetical_decision != expected_decision:
            raise HveeContractError(
                "critical-number shadow decision is inconsistent"
            )

        if (
            not isinstance(self.would_change_official_decision, bool)
            or self.would_change_official_decision
            != (expected_decision != self.official.decision)
        ):
            raise HveeContractError(
                "critical-number shadow comparison flag is inconsistent"
            )


def evaluate_asr_critical_number_matched_release_shadow(
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    declared_test_case_ids: tuple[int, ...],
    policy: ASRMatchedReleaseAssurancePolicyV1,
    records: tuple[ObservationEvidenceRecord, ...],
) -> ASRCriticalNumberMatchedReleaseShadowResult:
    """Build an advisory Critical Number comparison from raw evidence.

    The official v1 matched-release result is rebuilt unchanged from the same
    raw observation tuple.  Precomputed cohorts, assessments, and verdicts are
    intentionally not accepted.  Critical Number observations produce a
    separate hypothetical result that is not persisted to or enforced through
    the official path.
    """

    if not isinstance(policy, ASRMatchedReleaseAssurancePolicyV1):
        raise HveeContractError(
            "critical-number shadow requires the v1 assurance policy"
        )

    if not isinstance(records, tuple) or any(
        not isinstance(record, ObservationEvidenceRecord)
        for record in records
    ):
        raise HveeContractError(
            "critical-number shadow records must be an observation tuple"
        )

    assurance = verify_critical_number_assurance_profile_v1()
    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        declared_test_case_ids=declared_test_case_ids,
        records=records,
    )
    official = evaluate_asr_matched_release_decision(
        cohorts=cohorts,
        policy=policy,
    )

    cases = tuple(
        _build_case(
            baseline_run_id=cohorts.baseline_run_id,
            candidate_run_id=cohorts.candidate_run_id,
            test_case_id=test_case_id,
            records=records,
        )
        for test_case_id in cohorts.declared_test_case_ids
    )

    critical_integrity, critical_evidence, hypothetical_critical = (
        _derive_shadow_assessments(cases)
    )
    hypothetical_decision = _hypothetical_decision(
        official=official,
        critical_integrity=critical_integrity,
        critical_evidence=critical_evidence,
        hypothetical_critical=hypothetical_critical,
    )

    return ASRCriticalNumberMatchedReleaseShadowResult(
        shadow_key=CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_KEY,
        shadow_version=CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_VERSION,
        assurance_profile_key=CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
        assurance_profile_version=CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
        assurance_status=ASRCriticalNumberAssuranceStatus.EXPERIMENTAL,
        assurance_sha256=assurance.sha256,
        production_qualified=False,
        release_enforcement_eligible=False,
        official=official,
        cases=cases,
        critical_integrity=critical_integrity,
        critical_evidence=critical_evidence,
        hypothetical_critical=hypothetical_critical,
        hypothetical_decision=hypothetical_decision,
        would_change_official_decision=(
            hypothetical_decision != official.decision
        ),
    )
