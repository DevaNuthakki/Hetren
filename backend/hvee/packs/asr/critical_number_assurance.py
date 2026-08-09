"""Deterministic assurance evidence for Critical Number Fidelity v1.

This module calibrates the evaluator; it does not make release decisions.
The sealed v1 profile is intentionally experimental and remains in advisory
shadow use until private certification and production-derived evidence exist.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_APPLICABLE_METRIC,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    EN_US_CRITICAL_NUMBER_PROFILE,
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberType,
)
from hvee.packs.asr.critical_number_mutation import (
    CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1,
    CRITICAL_NUMBER_MUTATION_SUITE_KEY,
    CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
    ASRCriticalNumberMutationReport,
    run_critical_number_evaluator_mutation_suite,
)
from hvee.packs.asr.critical_number_portfolio import (
    CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
    CRITICAL_NUMBER_PORTFOLIO_KEY,
    CRITICAL_NUMBER_PORTFOLIO_VERSION,
    ASRCriticalNumberPortfolioCase,
    ASRCriticalNumberPortfolioDefinition,
    ASRCriticalNumberPortfolioOperation,
    ASRCriticalNumberPortfolioPartition,
    ASRCriticalNumberPortfolioReport,
    evaluate_critical_number_portfolio_case_observations,
    run_critical_number_portfolio,
)


CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SCHEMA_VERSION = 1
CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY = (
    "hetren.asr.critical-number-evaluator-assurance-profile.en-us"
)
CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION = "1.0.0"

CRITICAL_NUMBER_ASSURANCE_EXPECTED_CASES_V1 = 29
CRITICAL_NUMBER_ASSURANCE_EXPECTED_MUTANTS_V1 = 9

# Updated only when the versioned scientific artifact is deliberately revised.
# A same-version evaluator, profile, portfolio, or mutation-suite change must
# fail verification rather than silently changing the assurance claim.
CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1 = (
    "e8459e209a022883007f5c6f72972c43"
    "f48758c0c6442e0d4d31d4ad20c24a72"
)


class ASRCriticalNumberAssuranceStatus(StrEnum):
    EXPERIMENTAL = "experimental"


_EXPECTED_EVALUATOR_IDENTITY_V1 = (
    "hetren.asr.critical-number-fidelity.en-us",
    "1.0.0",
    "asr",
)
_EXPECTED_EVALUATION_PROFILE_IDENTITY_V1 = (
    "hetren.asr.critical-number-profile.en-us",
    "1.0.0",
    "en",
    "en-US",
)
_EXPECTED_PORTFOLIO_IDENTITY_V1 = (
    "hetren.asr.critical-number-fidelity-portfolio.en-us",
    "1.0.0",
)
_EXPECTED_MUTATION_SUITE_IDENTITY_V1 = (
    "hetren.asr.critical-number-evaluator-mutation-suite.en-us",
    "1.0.0",
)
_EXPECTED_MUTATIONS_V1 = (
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

_DANGEROUS_OPERATIONS = frozenset(
    {
        ASRCriticalNumberPortfolioOperation.SUBSTITUTION,
        ASRCriticalNumberPortfolioOperation.OMISSION,
        ASRCriticalNumberPortfolioOperation.INSERTION,
    }
)
_FULL_ERROR_MATRIX_OPERATIONS = frozenset(
    {
        ASRCriticalNumberPortfolioOperation.EQUIVALENCE,
        ASRCriticalNumberPortfolioOperation.SUBSTITUTION,
        ASRCriticalNumberPortfolioOperation.OMISSION,
        ASRCriticalNumberPortfolioOperation.INSERTION,
    }
)
_SUPPORTED_NUMERIC_TYPES = tuple(
    numeric_type
    for numeric_type in ASRCriticalNumberType
    if numeric_type != ASRCriticalNumberType.UNKNOWN
)

_LIMITATIONS_V1 = (
    {
        "code": "en_us_scope_only",
        "description": (
            "The evaluator and assurance evidence cover US English only."
        ),
    },
    {
        "code": "source_visible_regression_holdout",
        "description": (
            "The regression-holdout cases are source-visible development "
            "fixtures, not a private certification set."
        ),
    },
    {
        "code": "no_private_certification_set",
        "description": (
            "No private evaluator-certification set is included in v1."
        ),
    },
    {
        "code": "no_production_derived_cases",
        "description": (
            "No production-derived real-world cases are included in v1."
        ),
    },
)


def _canonicalize_json_value(
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


def calculate_critical_number_assurance_sha256(
    payload: object,
) -> str:
    canonical = _canonical_json(
        payload,
        name="critical-number assurance payload",
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberAssuranceEvidenceBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        canonical = _canonicalize_json_value(
            self.payload,
            name="critical-number assurance payload",
        )
        if not isinstance(canonical, dict):
            raise HveeContractError(
                "critical-number assurance payload must be a JSON object"
            )
        _require_sha256_hex(
            name="critical-number assurance SHA-256",
            value=self.sha256,
        )
        expected = calculate_critical_number_assurance_sha256(canonical)
        if self.sha256 != expected:
            raise HveeContractError(
                "critical-number assurance SHA-256 does not match its payload"
            )


def _require_v1_identities(
    portfolio: ASRCriticalNumberPortfolioDefinition,
) -> None:
    if not isinstance(portfolio, ASRCriticalNumberPortfolioDefinition):
        raise HveeContractError(
            "critical-number assurance requires the versioned portfolio"
        )

    evaluator_identity = (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
    )
    if evaluator_identity != _EXPECTED_EVALUATOR_IDENTITY_V1:
        raise HveeContractError(
            "critical-number assurance evaluator identity changed"
        )

    profile_identity = (
        EN_US_CRITICAL_NUMBER_PROFILE.key,
        EN_US_CRITICAL_NUMBER_PROFILE.version,
        EN_US_CRITICAL_NUMBER_PROFILE.language,
        EN_US_CRITICAL_NUMBER_PROFILE.locale,
    )
    if profile_identity != _EXPECTED_EVALUATION_PROFILE_IDENTITY_V1:
        raise HveeContractError(
            "critical-number assurance evaluation profile identity changed"
        )

    portfolio_identity = (portfolio.key, portfolio.version)
    if portfolio_identity != _EXPECTED_PORTFOLIO_IDENTITY_V1:
        raise HveeContractError(
            "critical-number assurance portfolio identity changed"
        )

    suite_identity = (
        CRITICAL_NUMBER_MUTATION_SUITE_KEY,
        CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
    )
    if suite_identity != _EXPECTED_MUTATION_SUITE_IDENTITY_V1:
        raise HveeContractError(
            "critical-number assurance mutation-suite identity changed"
        )

    mutations = tuple(
        mutation.value
        for mutation in CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1
    )
    if mutations != _EXPECTED_MUTATIONS_V1:
        raise HveeContractError(
            "critical-number assurance mutation-suite definition changed"
        )


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


def _case_definition_snapshot(
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


def _mutation_report_snapshot(
    report: ASRCriticalNumberMutationReport,
) -> dict[str, object]:
    return {
        "key": report.suite_key,
        "version": report.suite_version,
        "mutations": [
            mutation.value
            for mutation in CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1
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
                "changed_cases": result.changed_cases,
                "detected_cases": result.detected_cases,
                "killed": result.killed,
            }
            for result in report.results
        ],
    }


def _observations_by_key(
    observations: tuple[Observation, ...],
) -> dict[str, Observation]:
    by_key: dict[str, Observation] = {}
    for observation in observations:
        if observation.metric_key in by_key:
            raise HveeContractError(
                "critical-number assurance observations contain duplicates"
            )
        by_key[observation.metric_key] = observation
    return by_key


def _has_success_value(
    observations: dict[str, Observation],
    *,
    metric_key: str,
    expected: object,
) -> bool:
    observation = observations.get(metric_key)
    return bool(
        observation is not None
        and observation.status == ObservationStatus.SUCCESS
        and observation.value == expected
    )


def _build_measurements(
    *,
    portfolio: ASRCriticalNumberPortfolioDefinition,
    observations_by_case: dict[str, dict[str, Observation]],
) -> dict[str, object]:
    dangerous_cases = tuple(
        case
        for case in portfolio.cases
        if case.operation in _DANGEROUS_OPERATIONS
    )
    dangerous_false_passes = sum(
        _has_success_value(
            observations_by_case[case.case_id],
            metric_key=CRITICAL_NUMBER_OUTCOME_METRIC.key,
            expected=ASRCriticalNumberFidelityOutcome.PRESERVED.value,
        )
        or _has_success_value(
            observations_by_case[case.case_id],
            metric_key=CRITICAL_NUMBER_PRESERVED_METRIC.key,
            expected=True,
        )
        for case in dangerous_cases
    )

    equivalence_cases = tuple(
        case
        for case in portfolio.cases
        if case.operation == ASRCriticalNumberPortfolioOperation.EQUIVALENCE
    )
    equivalence_false_failures = sum(
        not (
            _has_success_value(
                observations_by_case[case.case_id],
                metric_key=CRITICAL_NUMBER_OUTCOME_METRIC.key,
                expected=ASRCriticalNumberFidelityOutcome.PRESERVED.value,
            )
            and _has_success_value(
                observations_by_case[case.case_id],
                metric_key=CRITICAL_NUMBER_PRESERVED_METRIC.key,
                expected=True,
            )
        )
        for case in equivalence_cases
    )

    applicability_errors = sum(
        not _has_success_value(
            observations_by_case[case.case_id],
            metric_key=CRITICAL_NUMBER_APPLICABLE_METRIC.key,
            expected=case.expected_applicable,
        )
        for case in portfolio.cases
    )

    abstention_cases = tuple(
        case
        for case in portfolio.cases
        if case.expected_preserved_status == ObservationStatus.ABSTAINED
    )
    abstention_errors = sum(
        observations_by_case[case.case_id][
            CRITICAL_NUMBER_PRESERVED_METRIC.key
        ].status
        != ObservationStatus.ABSTAINED
        for case in abstention_cases
    )

    unsupported_cases = tuple(
        case
        for case in portfolio.cases
        if case.expected_preserved_status == ObservationStatus.UNSUPPORTED
    )
    unsupported_errors = sum(
        observations_by_case[case.case_id][
            CRITICAL_NUMBER_PRESERVED_METRIC.key
        ].status
        != ObservationStatus.UNSUPPORTED
        for case in unsupported_cases
    )

    operations_by_type = {
        numeric_type: {
            case.operation
            for case in portfolio.cases
            if case.numeric_type == numeric_type
        }
        for numeric_type in _SUPPORTED_NUMERIC_TYPES
    }
    complete_types = tuple(
        numeric_type
        for numeric_type in _SUPPORTED_NUMERIC_TYPES
        if _FULL_ERROR_MATRIX_OPERATIONS <= operations_by_type[numeric_type]
    )
    missing_types = tuple(
        numeric_type
        for numeric_type in _SUPPORTED_NUMERIC_TYPES
        if numeric_type not in complete_types
    )

    return {
        "dangerous_false_passes": {
            "cases": len(dangerous_cases),
            "false_passes": dangerous_false_passes,
            "detection_rate": (
                (len(dangerous_cases) - dangerous_false_passes)
                / len(dangerous_cases)
            ),
        },
        "equivalence_false_failures": {
            "cases": len(equivalence_cases),
            "false_failures": equivalence_false_failures,
            "acceptance_rate": (
                (len(equivalence_cases) - equivalence_false_failures)
                / len(equivalence_cases)
            ),
        },
        "applicability": {
            "cases": len(portfolio.cases),
            "correct": len(portfolio.cases) - applicability_errors,
            "errors": applicability_errors,
        },
        "abstention": {
            "expected_cases": len(abstention_cases),
            "correct": len(abstention_cases) - abstention_errors,
            "errors": abstention_errors,
        },
        "unsupported": {
            "expected_cases": len(unsupported_cases),
            "correct": len(unsupported_cases) - unsupported_errors,
            "errors": unsupported_errors,
        },
        "numeric_type_coverage": {
            "supported_types": [
                numeric_type.value
                for numeric_type in _SUPPORTED_NUMERIC_TYPES
            ],
            "required_operations": sorted(
                operation.value
                for operation in _FULL_ERROR_MATRIX_OPERATIONS
            ),
            "types_with_full_error_matrix": [
                numeric_type.value for numeric_type in complete_types
            ],
            "missing_types": [
                numeric_type.value for numeric_type in missing_types
            ],
        },
    }


def _require_expected_v1_results(
    *,
    baseline: ASRCriticalNumberPortfolioReport,
    mutations: ASRCriticalNumberMutationReport,
    measurements: dict[str, object],
) -> None:
    if (
        baseline.total_cases != CRITICAL_NUMBER_ASSURANCE_EXPECTED_CASES_V1
        or baseline.passed_cases
        != CRITICAL_NUMBER_ASSURANCE_EXPECTED_CASES_V1
        or baseline.failed_cases != 0
        or not baseline.passed
    ):
        raise HveeContractError(
            "critical-number assurance requires the passing 29-case baseline"
        )
    if (
        mutations.total_mutants
        != CRITICAL_NUMBER_ASSURANCE_EXPECTED_MUTANTS_V1
        or mutations.killed_mutants
        != CRITICAL_NUMBER_ASSURANCE_EXPECTED_MUTANTS_V1
        or mutations.survived_mutants != 0
    ):
        raise HveeContractError(
            "critical-number assurance requires all nine mutants to be killed"
        )

    dangerous = measurements["dangerous_false_passes"]
    equivalence = measurements["equivalence_false_failures"]
    applicability = measurements["applicability"]
    abstention = measurements["abstention"]
    unsupported = measurements["unsupported"]
    coverage = measurements["numeric_type_coverage"]
    if not all(
        isinstance(item, dict)
        for item in (
            dangerous,
            equivalence,
            applicability,
            abstention,
            unsupported,
            coverage,
        )
    ):
        raise HveeContractError(
            "critical-number assurance measurements are malformed"
        )
    if (
        dangerous["false_passes"] != 0
        or equivalence["false_failures"] != 0
        or applicability["errors"] != 0
        or abstention["errors"] != 0
        or unsupported["errors"] != 0
        or coverage["missing_types"] != []
    ):
        raise HveeContractError(
            "critical-number assurance measurements do not satisfy v1"
        )


def build_critical_number_assurance_evidence_bundle(
    portfolio: ASRCriticalNumberPortfolioDefinition = (
        CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1
    ),
) -> ASRCriticalNumberAssuranceEvidenceBundle:
    """Build exact, timestamp-free evaluator-assurance evidence for v1."""

    _require_v1_identities(portfolio)
    baseline = run_critical_number_portfolio(portfolio)
    mutations = run_critical_number_evaluator_mutation_suite(portfolio)

    result_by_case = {
        result.case_id: result for result in baseline.case_results
    }
    observations_by_case: dict[str, dict[str, Observation]] = {}
    case_runs: list[dict[str, object]] = []
    for case in portfolio.cases:
        result = result_by_case.get(case.case_id)
        if result is None:
            raise HveeContractError(
                "critical-number assurance baseline is missing a case"
            )
        observations = evaluate_critical_number_portfolio_case_observations(
            case
        )
        by_key = _observations_by_key(observations)
        observations_by_case[case.case_id] = by_key
        case_runs.append(
            {
                "definition": _case_definition_snapshot(case),
                "result": {
                    "passed": result.passed,
                    "failed_checks": list(result.failed_checks),
                },
                "observations": [
                    _observation_snapshot(observation)
                    for observation in observations
                ],
            }
        )

    measurements = _build_measurements(
        portfolio=portfolio,
        observations_by_case=observations_by_case,
    )
    _require_expected_v1_results(
        baseline=baseline,
        mutations=mutations,
        measurements=measurements,
    )

    partition_counts = {
        partition.value: sum(
            case.partition == partition for case in portfolio.cases
        )
        for partition in ASRCriticalNumberPortfolioPartition
    }

    payload = {
        "schema_version": CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SCHEMA_VERSION,
        "evaluation_type": "asr",
        "assurance_profile": {
            "key": CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
            "version": CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
            "status": ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value,
            "intended_use": "advisory_shadow_evidence",
            "production_qualified": False,
            "release_enforcement_eligible": False,
        },
        "bindings": {
            "evaluator": {
                "key": CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
                "version": CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
                "evaluation_type": (
                    CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type
                ),
            },
            "evaluation_profile": {
                "key": EN_US_CRITICAL_NUMBER_PROFILE.key,
                "version": EN_US_CRITICAL_NUMBER_PROFILE.version,
                "language": EN_US_CRITICAL_NUMBER_PROFILE.language,
                "locale": EN_US_CRITICAL_NUMBER_PROFILE.locale,
            },
            "portfolio": {
                "key": portfolio.key,
                "version": portfolio.version,
            },
            "mutation_suite": {
                "key": CRITICAL_NUMBER_MUTATION_SUITE_KEY,
                "version": CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
            },
        },
        "baseline": {
            "total_cases": baseline.total_cases,
            "passed_cases": baseline.passed_cases,
            "failed_cases": baseline.failed_cases,
            "passed": baseline.passed,
            "partition_counts": partition_counts,
            "case_runs": case_runs,
        },
        "assurance_measurements": measurements,
        "evaluator_mutation_suite": _mutation_report_snapshot(mutations),
        "limitations": list(_LIMITATIONS_V1),
    }

    canonical = _canonicalize_json_value(
        payload,
        name="critical-number assurance payload",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError(
            "critical-number assurance payload must canonicalize to an object"
        )
    return ASRCriticalNumberAssuranceEvidenceBundle(
        payload=canonical,
        sha256=calculate_critical_number_assurance_sha256(canonical),
    )


def verify_critical_number_assurance_evidence_bundle(
    *,
    payload: object,
    expected_sha256: object,
    portfolio: ASRCriticalNumberPortfolioDefinition = (
        CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1
    ),
) -> ASRCriticalNumberAssuranceEvidenceBundle:
    """Rebuild the v1 evidence and require exact payload and digest equality."""

    expected_digest = _require_sha256_hex(
        name="expected critical-number assurance SHA-256",
        value=expected_sha256,
    )
    supplied = _canonicalize_json_value(
        payload,
        name="supplied critical-number assurance payload",
    )
    if not isinstance(supplied, dict):
        raise HveeContractError(
            "supplied critical-number assurance payload must be an object"
        )
    if calculate_critical_number_assurance_sha256(supplied) != expected_digest:
        raise HveeContractError(
            "supplied critical-number assurance evidence does not match "
            "expected SHA-256"
        )

    rebuilt = build_critical_number_assurance_evidence_bundle(portfolio)
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "critical-number assurance evidence does not match the "
            "reproducibly rebuilt v1 profile"
        )
    return rebuilt


def verify_critical_number_assurance_profile_v1(
) -> ASRCriticalNumberAssuranceEvidenceBundle:
    """Fail closed unless the installed v1 artifact matches its sealed digest."""

    rebuilt = build_critical_number_assurance_evidence_bundle()
    if rebuilt.sha256 != CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1:
        raise HveeContractError(
            "critical-number assurance v1 does not match its sealed SHA-256"
        )
    return rebuilt
