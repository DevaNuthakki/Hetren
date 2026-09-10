"""Deterministic assurance candidate for Critical Number Fidelity v1.1.

This evidence is an input to the Run-04 evaluator precommitment. It neither
reads Run-04 model results nor grants production or release authority. The
historical v1.0 assurance artifact remains independently sealed and unchanged.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError, Observation
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    verify_critical_number_assurance_profile_v1,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    EN_US_CRITICAL_NUMBER_PROFILE,
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberType,
    evaluate_critical_number_fidelity,
)
from hvee.packs.asr.critical_number_mutation import (
    CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1,
    CRITICAL_NUMBER_MUTATION_SUITE_KEY,
    CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
    run_critical_number_evaluator_mutation_suite,
)
from hvee.packs.asr.critical_number_portfolio import (
    CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
    CRITICAL_NUMBER_PORTFOLIO_KEY,
    CRITICAL_NUMBER_PORTFOLIO_VERSION,
    ASRCriticalNumberPortfolioCase,
    evaluate_critical_number_portfolio_case_observations,
    run_critical_number_portfolio,
)


CRITICAL_NUMBER_ASSURANCE_V1_1_SCHEMA_VERSION = 1
CRITICAL_NUMBER_ASSURANCE_V1_1_KEY = (
    "hetren.asr.critical-number-evaluator-assurance-profile.en-us"
)
CRITICAL_NUMBER_ASSURANCE_V1_1_VERSION = "1.1.0"
CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BASE_CASES = 29
CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BOUNDARY_CASES = 6
CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_MUTANTS = 9
CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_DANGEROUS_CASES = 20
CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_EQUIVALENCE_CASES = 6
CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_ABSTENTION_CASES = 2
CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_NOT_APPLICABLE_CASES = 1


_EXPECTED_EVALUATOR_IDENTITY = (
    "hetren.asr.critical-number-fidelity.en-us",
    "1.1.0",
    "asr",
)
_EXPECTED_PROFILE_IDENTITY = (
    "hetren.asr.critical-number-profile.en-us",
    "1.0.0",
    "en",
    "en-US",
)
_EXPECTED_PORTFOLIO_IDENTITY = (
    "hetren.asr.critical-number-fidelity-portfolio.en-us",
    "1.0.0",
)
_EXPECTED_MUTATION_SUITE_IDENTITY = (
    "hetren.asr.critical-number-evaluator-mutation-suite.en-us",
    "1.0.0",
)
_EXPECTED_MUTATIONS = (
    "outcome_false_pass",
    "preservation_false_pass",
    "equivalence_false_failure",
    "substitution_blind",
    "omission_blind",
    "insertion_blind",
    "ambiguity_blind",
    "no_number_applicability_blind",
    "detailed_findings_blind",
)


@dataclass(frozen=True, slots=True)
class _BoundaryCase:
    case_id: str
    reference_text: str
    generated_text: str
    expected_outcome: str
    expected_preserved: bool
    expected_clock_values: tuple[str, ...]
    expected_decimal_values: tuple[str, ...] | None = None
    required_reason_codes: tuple[str, ...] = ()


_BOUNDARY_CASES = (
    _BoundaryCase(
        case_id="qualification.clock-time-dot-am-equivalence",
        reference_text="meet at nine fifteen AM tomorrow",
        generated_text="meet at 9.15 a.m. tomorrow",
        expected_outcome=ASRCriticalNumberFidelityOutcome.PRESERVED.value,
        expected_preserved=True,
        expected_clock_values=("09:15",),
        required_reason_codes=("format_equivalent",),
    ),
    _BoundaryCase(
        case_id="qualification.clock-time-dot-pm-equivalence",
        reference_text="meet at nine fifteen PM tomorrow",
        generated_text="meet at 9.15 p.m. tomorrow",
        expected_outcome=ASRCriticalNumberFidelityOutcome.PRESERVED.value,
        expected_preserved=True,
        expected_clock_values=("21:15",),
        required_reason_codes=("format_equivalent",),
    ),
    _BoundaryCase(
        case_id="qualification.decimal-dot-remains-decimal",
        reference_text="threshold is 9.15",
        generated_text="threshold is 9.15",
        expected_outcome=ASRCriticalNumberFidelityOutcome.PRESERVED.value,
        expected_preserved=True,
        expected_clock_values=(),
        expected_decimal_values=("9.15",),
    ),
    _BoundaryCase(
        case_id="qualification.clock-time-dot-substitution",
        reference_text="meet at nine fifteen AM tomorrow",
        generated_text="meet at 9.50 a.m. tomorrow",
        expected_outcome=ASRCriticalNumberFidelityOutcome.NOT_PRESERVED.value,
        expected_preserved=False,
        expected_clock_values=("09:50",),
        required_reason_codes=("value_substitution",),
    ),
    _BoundaryCase(
        case_id="qualification.invalid-dot-minute-not-clock",
        reference_text="meet at nine fifteen AM tomorrow",
        generated_text="meet at 9.75 AM tomorrow",
        expected_outcome=ASRCriticalNumberFidelityOutcome.NOT_PRESERVED.value,
        expected_preserved=False,
        expected_clock_values=(),
    ),
    _BoundaryCase(
        case_id="qualification.invalid-dot-hour-not-clock",
        reference_text="meet at nine fifteen PM tomorrow",
        generated_text="meet at 13.15 PM tomorrow",
        expected_outcome=ASRCriticalNumberFidelityOutcome.NOT_PRESERVED.value,
        expected_preserved=False,
        expected_clock_values=(),
    ),
)


_LIMITATIONS = (
    {
        "code": "en_us_scope_only",
        "description": "The evaluator and assurance evidence are scoped to en-US.",
    },
    {
        "code": "source_visible_portfolio",
        "description": "The inherited portfolio is source-visible, not private.",
    },
    {
        "code": "synthetic_boundary_cases",
        "description": "The v1.1 boundary cases are deterministic synthetic cases.",
    },
    {
        "code": "no_production_certification",
        "description": "This evidence grants no production or release authority.",
    },
)


def _canonicalize(value: object, *, name: str) -> object:
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


def calculate_critical_number_assurance_v1_1_sha256(payload: object) -> str:
    canonical = _canonicalize(
        payload,
        name="critical-number assurance v1.1 payload",
    )
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberAssuranceV11Bundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if (
            len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise HveeContractError(
                "critical-number assurance v1.1 SHA-256 is invalid"
            )
        if self.sha256 != calculate_critical_number_assurance_v1_1_sha256(
            self.payload
        ):
            raise HveeContractError(
                "critical-number assurance v1.1 SHA-256 does not match its payload"
            )


def _require_identities() -> None:
    evaluator_identity = (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
    )
    if evaluator_identity != _EXPECTED_EVALUATOR_IDENTITY:
        raise HveeContractError(
            "critical-number assurance v1.1 evaluator identity changed"
        )

    profile_identity = (
        EN_US_CRITICAL_NUMBER_PROFILE.key,
        EN_US_CRITICAL_NUMBER_PROFILE.version,
        EN_US_CRITICAL_NUMBER_PROFILE.language,
        EN_US_CRITICAL_NUMBER_PROFILE.locale,
    )
    if profile_identity != _EXPECTED_PROFILE_IDENTITY:
        raise HveeContractError(
            "critical-number assurance v1.1 profile identity changed"
        )

    portfolio_identity = (
        CRITICAL_NUMBER_PORTFOLIO_KEY,
        CRITICAL_NUMBER_PORTFOLIO_VERSION,
    )
    if portfolio_identity != _EXPECTED_PORTFOLIO_IDENTITY:
        raise HveeContractError(
            "critical-number assurance v1.1 portfolio identity changed"
        )

    suite_identity = (
        CRITICAL_NUMBER_MUTATION_SUITE_KEY,
        CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
    )
    if suite_identity != _EXPECTED_MUTATION_SUITE_IDENTITY:
        raise HveeContractError(
            "critical-number assurance v1.1 mutation-suite identity changed"
        )

    mutations = tuple(
        mutation.value for mutation in CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1
    )
    if mutations != _EXPECTED_MUTATIONS:
        raise HveeContractError(
            "critical-number assurance v1.1 mutation-suite definition changed"
        )


def _portfolio_case_snapshot(
    case: ASRCriticalNumberPortfolioCase,
) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "partition": case.partition.value,
        "operation": case.operation.value,
        "numeric_type": case.numeric_type.value,
        "reference_text": case.reference_text,
        "generated_text": case.generated_text,
        "expected_outcome": case.expected_outcome.value,
        "expected_applicable": case.expected_applicable,
        "expected_preserved_status": case.expected_preserved_status.value,
        "expected_preserved": case.expected_preserved,
        "expected_reference_count": case.expected_reference_count,
        "expected_generated_count": case.expected_generated_count,
        "expected_substitution_count": case.expected_substitution_count,
        "expected_omission_count": case.expected_omission_count,
        "expected_insertion_count": case.expected_insertion_count,
        "expected_ambiguity_count": case.expected_ambiguity_count,
        "required_reason_codes": [
            reason.value for reason in case.required_reason_codes
        ],
        "description": case.description,
    }


def _observation_snapshot(observation: Observation) -> dict[str, object]:
    return {
        "metric_key": observation.metric_key,
        "metric_version": observation.metric_version,
        "evaluator_key": observation.evaluator_key,
        "evaluator_version": observation.evaluator_version,
        "evaluation_type": observation.evaluation_type,
        "status": observation.status.value,
        "value_type": observation.value_type.value,
        "value": observation.value,
        "status_detail": observation.status_detail,
    }


def _inherited_measurements() -> dict[str, object]:
    evaluations = {
        case.case_id: evaluate_critical_number_fidelity(
            reference_text=case.reference_text,
            generated_text=case.generated_text,
            profile=EN_US_CRITICAL_NUMBER_PROFILE,
            evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR,
        )
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
    }
    dangerous = tuple(
        case
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
        if case.expected_outcome
        == ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
    )
    equivalence = tuple(
        case
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
        if case.expected_outcome == ASRCriticalNumberFidelityOutcome.PRESERVED
    )
    abstention = tuple(
        case
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
        if case.expected_outcome
        == ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
    )
    not_applicable = tuple(
        case
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
        if case.expected_outcome
        == ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE
    )
    false_passes = sum(
        evaluations[case.case_id].outcome
        == ASRCriticalNumberFidelityOutcome.PRESERVED
        for case in dangerous
    )
    false_failures = sum(
        evaluations[case.case_id].outcome
        != ASRCriticalNumberFidelityOutcome.PRESERVED
        for case in equivalence
    )
    abstention_errors = sum(
        evaluations[case.case_id].outcome
        != ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
        for case in abstention
    )
    not_applicable_errors = sum(
        evaluations[case.case_id].outcome
        != ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE
        for case in not_applicable
    )
    measurements = {
        "dangerous_false_passes": {
            "cases": len(dangerous),
            "false_passes": false_passes,
            "detection_rate": (
                (len(dangerous) - false_passes) / len(dangerous)
            ),
        },
        "equivalence_false_failures": {
            "cases": len(equivalence),
            "false_failures": false_failures,
            "acceptance_rate": (
                (len(equivalence) - false_failures) / len(equivalence)
            ),
        },
        "abstention": {
            "expected_cases": len(abstention),
            "correct": len(abstention) - abstention_errors,
            "errors": abstention_errors,
        },
        "not_applicable": {
            "expected_cases": len(not_applicable),
            "correct": len(not_applicable) - not_applicable_errors,
            "errors": not_applicable_errors,
        },
    }
    if measurements != {
        "dangerous_false_passes": {
            "cases": CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_DANGEROUS_CASES,
            "false_passes": 0,
            "detection_rate": 1.0,
        },
        "equivalence_false_failures": {
            "cases": CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_EQUIVALENCE_CASES,
            "false_failures": 0,
            "acceptance_rate": 1.0,
        },
        "abstention": {
            "expected_cases": (
                CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_ABSTENTION_CASES
            ),
            "correct": CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_ABSTENTION_CASES,
            "errors": 0,
        },
        "not_applicable": {
            "expected_cases": (
                CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_NOT_APPLICABLE_CASES
            ),
            "correct": (
                CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_NOT_APPLICABLE_CASES
            ),
            "errors": 0,
        },
    }:
        raise HveeContractError(
            "critical-number assurance v1.1 inherited measurements changed"
        )
    return measurements


def _boundary_measurements(
    boundary_runs: list[dict[str, object]],
) -> dict[str, object]:
    dangerous = tuple(
        item
        for item in boundary_runs
        if item["definition"]["expected_preserved"] is False
    )
    equivalence = tuple(
        item
        for item in boundary_runs
        if item["definition"]["expected_preserved"] is True
    )
    false_passes = sum(
        item["actual"]["preserved"] is True for item in dangerous
    )
    false_failures = sum(
        item["actual"]["preserved"] is not True for item in equivalence
    )
    measurements = {
        "dangerous_false_passes": {
            "cases": len(dangerous),
            "false_passes": false_passes,
            "detection_rate": (
                (len(dangerous) - false_passes) / len(dangerous)
            ),
        },
        "equivalence_false_failures": {
            "cases": len(equivalence),
            "false_failures": false_failures,
            "acceptance_rate": (
                (len(equivalence) - false_failures) / len(equivalence)
            ),
        },
    }
    if measurements != {
        "dangerous_false_passes": {
            "cases": 3,
            "false_passes": 0,
            "detection_rate": 1.0,
        },
        "equivalence_false_failures": {
            "cases": 3,
            "false_failures": 0,
            "acceptance_rate": 1.0,
        },
    }:
        raise HveeContractError(
            "critical-number assurance v1.1 boundary measurements changed"
        )
    return measurements


def _run_boundary_case(case: _BoundaryCase) -> dict[str, object]:
    evaluation = evaluate_critical_number_fidelity(
        reference_text=case.reference_text,
        generated_text=case.generated_text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    )
    clock_values = tuple(
        entity.canonical_value
        for entity in evaluation.generated_entities
        if entity.numeric_type == ASRCriticalNumberType.CLOCK_TIME
    )
    decimal_values = tuple(
        entity.canonical_value
        for entity in evaluation.generated_entities
        if entity.numeric_type == ASRCriticalNumberType.CARDINAL_DECIMAL
    )
    reason_codes = tuple(finding.reason_code.value for finding in evaluation.findings)

    failed: list[str] = []
    if evaluation.outcome.value != case.expected_outcome:
        failed.append("outcome")
    if evaluation.preserved is not case.expected_preserved:
        failed.append("preserved")
    if clock_values != case.expected_clock_values:
        failed.append("clock_values")
    if (
        case.expected_decimal_values is not None
        and decimal_values != case.expected_decimal_values
    ):
        failed.append("decimal_values")
    for required in case.required_reason_codes:
        if required not in reason_codes:
            failed.append(f"reason:{required}")

    return {
        "definition": {
            "case_id": case.case_id,
            "reference_text": case.reference_text,
            "generated_text": case.generated_text,
            "expected_outcome": case.expected_outcome,
            "expected_preserved": case.expected_preserved,
            "expected_clock_values": list(case.expected_clock_values),
            "expected_decimal_values": (
                None
                if case.expected_decimal_values is None
                else list(case.expected_decimal_values)
            ),
            "required_reason_codes": list(case.required_reason_codes),
        },
        "actual": {
            "outcome": evaluation.outcome.value,
            "preserved": evaluation.preserved,
            "clock_values": list(clock_values),
            "decimal_values": list(decimal_values),
            "reason_codes": list(reason_codes),
        },
        "passed": not failed,
        "failed_checks": failed,
    }


def _mutation_snapshot(report) -> dict[str, object]:
    return {
        "key": report.suite_key,
        "version": report.suite_version,
        "mutations": [
            mutation.value for mutation in CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1
        ],
        "total_mutants": report.total_mutants,
        "killed_mutants": report.killed_mutants,
        "survived_mutants": report.survived_mutants,
        "mutation_score": report.mutation_score,
        "results": [
            {
                "mutation": result.mutation.value,
                "changed_case_ids": list(result.changed_case_ids),
                "detected_case_ids": list(result.detected_case_ids),
                "killed": result.killed,
            }
            for result in report.results
        ],
    }


def build_critical_number_assurance_v1_1_candidate(
) -> ASRCriticalNumberAssuranceV11Bundle:
    """Build timestamp-free v1.1 assurance evidence without Run-04 results."""

    _require_identities()
    legacy = verify_critical_number_assurance_profile_v1()
    if legacy.sha256 != CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1:
        raise HveeContractError("historical critical-number assurance changed")

    baseline = run_critical_number_portfolio(
        CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    )
    mutations = run_critical_number_evaluator_mutation_suite(
        CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    )
    boundary_runs = [_run_boundary_case(case) for case in _BOUNDARY_CASES]
    boundary_failures = sum(not item["passed"] for item in boundary_runs)
    inherited_measurements = _inherited_measurements()
    boundary_measurements = _boundary_measurements(boundary_runs)

    if (
        baseline.total_cases
        != CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BASE_CASES
        or baseline.failed_cases != 0
        or not baseline.passed
    ):
        raise HveeContractError(
            "critical-number assurance v1.1 requires the passing inherited portfolio"
        )
    if (
        len(boundary_runs)
        != CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BOUNDARY_CASES
        or boundary_failures != 0
    ):
        raise HveeContractError(
            "critical-number assurance v1.1 boundary cases failed"
        )
    if (
        mutations.total_mutants
        != CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_MUTANTS
        or mutations.survived_mutants != 0
    ):
        raise HveeContractError(
            "critical-number assurance v1.1 requires all mutations to be killed"
        )

    result_by_id = {result.case_id: result for result in baseline.case_results}
    observations_by_id = {
        case.case_id: evaluate_critical_number_portfolio_case_observations(
            case,
            evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR,
        )
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
    }
    payload = {
        "schema_version": CRITICAL_NUMBER_ASSURANCE_V1_1_SCHEMA_VERSION,
        "evaluation_type": "asr",
        "assurance_profile": {
            "key": CRITICAL_NUMBER_ASSURANCE_V1_1_KEY,
            "version": CRITICAL_NUMBER_ASSURANCE_V1_1_VERSION,
            "status": "experimental",
            "intended_use": "run04_public_v2_evaluator_qualification_input",
            "production_qualified": False,
            "release_enforcement_eligible": False,
        },
        "bindings": {
            "evaluator": {
                "key": CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
                "version": CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
                "evaluation_type": CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
            },
            "evaluation_profile": {
                "key": EN_US_CRITICAL_NUMBER_PROFILE.key,
                "version": EN_US_CRITICAL_NUMBER_PROFILE.version,
                "language": EN_US_CRITICAL_NUMBER_PROFILE.language,
                "locale": EN_US_CRITICAL_NUMBER_PROFILE.locale,
            },
            "inherited_portfolio": {
                "key": CRITICAL_NUMBER_PORTFOLIO_KEY,
                "version": CRITICAL_NUMBER_PORTFOLIO_VERSION,
            },
            "mutation_suite": {
                "key": CRITICAL_NUMBER_MUTATION_SUITE_KEY,
                "version": CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
            },
            "historical_v1_assurance_sha256": legacy.sha256,
        },
        "inherited_baseline": {
            "total_cases": baseline.total_cases,
            "passed_cases": baseline.passed_cases,
            "failed_cases": baseline.failed_cases,
            "passed": baseline.passed,
            "case_runs": [
                {
                    "definition": _portfolio_case_snapshot(case),
                    "result": {
                        "passed": result_by_id[case.case_id].passed,
                        "failed_checks": list(
                            result_by_id[case.case_id].failed_checks
                        ),
                    },
                    "observations": [
                        _observation_snapshot(observation)
                        for observation in observations_by_id[case.case_id]
                    ],
                }
                for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
            ],
        },
        "v1_1_boundary": {
            "total_cases": len(boundary_runs),
            "passed_cases": len(boundary_runs) - boundary_failures,
            "failed_cases": boundary_failures,
            "case_runs": boundary_runs,
        },
        "qualification_measurements": {
            "inherited_portfolio": inherited_measurements,
            "v1_1_boundary": boundary_measurements,
        },
        "evaluator_mutation_suite": _mutation_snapshot(mutations),
        "validity": {
            "expires_on_evaluator_identity_change": True,
            "expires_on_profile_identity_change": True,
            "expires_on_portfolio_identity_change": True,
            "expires_on_mutation_suite_identity_change": True,
            "does_not_supersede_historical_v1_evidence": True,
        },
        "limitations": list(_LIMITATIONS),
    }
    canonical = _canonicalize(
        payload,
        name="critical-number assurance v1.1 payload",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError(
            "critical-number assurance v1.1 payload must be an object"
        )
    return ASRCriticalNumberAssuranceV11Bundle(
        payload=canonical,
        sha256=calculate_critical_number_assurance_v1_1_sha256(canonical),
    )


def verify_critical_number_assurance_v1_1_candidate(
    *,
    payload: object,
    expected_sha256: object,
) -> ASRCriticalNumberAssuranceV11Bundle:
    if not isinstance(expected_sha256, str):
        raise HveeContractError(
            "expected critical-number assurance v1.1 SHA-256 must be a string"
        )
    canonical = _canonicalize(
        payload,
        name="supplied critical-number assurance v1.1 payload",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError(
            "supplied critical-number assurance v1.1 payload must be an object"
        )
    supplied = ASRCriticalNumberAssuranceV11Bundle(
        payload=canonical,
        sha256=expected_sha256,
    )
    rebuilt = build_critical_number_assurance_v1_1_candidate()
    if supplied != rebuilt:
        raise HveeContractError(
            "critical-number assurance v1.1 does not match the reproducible build"
        )
    return rebuilt


__all__ = [
    "ASRCriticalNumberAssuranceV11Bundle",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BASE_CASES",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_DANGEROUS_CASES",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_EQUIVALENCE_CASES",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_ABSTENTION_CASES",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_NOT_APPLICABLE_CASES",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BOUNDARY_CASES",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_MUTANTS",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_KEY",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_SCHEMA_VERSION",
    "CRITICAL_NUMBER_ASSURANCE_V1_1_VERSION",
    "build_critical_number_assurance_v1_1_candidate",
    "calculate_critical_number_assurance_v1_1_sha256",
    "verify_critical_number_assurance_v1_1_candidate",
]
