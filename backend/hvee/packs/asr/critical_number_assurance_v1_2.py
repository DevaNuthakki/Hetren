"""Deterministic assurance candidate for Critical Number Fidelity v1.2.

This artifact is an experimental Run-04 evaluator-qualification input.

It does not read Run-04 model predictions, reference records, hidden holdouts,
or model scores. It grants no production qualification, release enforcement,
or certification authority.

Historical v1.0 and v1.1 evaluator identities and assurance evidence remain
independently reproducible and unchanged.
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
from hvee.packs.asr.critical_number_assurance_v1_1 import (
    build_critical_number_assurance_v1_1_candidate,
)
from hvee.packs.asr.critical_number_fidelity import (
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberType,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    EN_US_CRITICAL_NUMBER_PROFILE,
    evaluate_critical_number_fidelity,
)
from hvee.packs.asr.critical_number_mutation import (
    CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1,
    CRITICAL_NUMBER_MUTATION_SUITE_KEY,
    CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
    run_critical_number_evaluator_mutation_suite,
)
from hvee.packs.asr.critical_number_portfolio import (
    ASRCriticalNumberPortfolioCase,
    CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
    CRITICAL_NUMBER_PORTFOLIO_KEY,
    CRITICAL_NUMBER_PORTFOLIO_VERSION,
    evaluate_critical_number_portfolio_case_observations,
    run_critical_number_portfolio,
)


CRITICAL_NUMBER_ASSURANCE_V1_2_SCHEMA_VERSION = 1
CRITICAL_NUMBER_ASSURANCE_V1_2_KEY = (
    "hetren.asr.critical-number-evaluator-assurance-profile.en-us"
)
CRITICAL_NUMBER_ASSURANCE_V1_2_VERSION = "1.2.0"

CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BASE_CASES = 29
CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_V1_1_BOUNDARY_CASES = 6
CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BOUNDARY_CASES = 85
CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_INHERITED_MUTANTS = 9
CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_NEW_MUTANTS = 2

_HISTORICAL_V1_SHA256 = (
    "e8459e209a022883007f5c6f72972c43"
    "f48758c0c6442e0d4d31d4ad20c24a72"
)
_HISTORICAL_V1_1_SHA256 = (
    "fdd4a72abd5c4c568fbef14244299eb97"
    "1928ea81e7b3beba602a236b63efe24"
)

_EXPECTED_EVALUATOR_IDENTITY = (
    "hetren.asr.critical-number-fidelity.en-us",
    "1.2.0",
    "asr",
)
_EXPECTED_DEFAULT_EVALUATOR_IDENTITY = (
    "hetren.asr.critical-number-fidelity.en-us",
    "1.1.0",
    "asr",
)
_EXPECTED_HISTORICAL_EVALUATOR_IDENTITY = (
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
_EXPECTED_PORTFOLIO_IDENTITY = (
    "hetren.asr.critical-number-fidelity-portfolio.en-us",
    "1.0.0",
)
_EXPECTED_MUTATION_SUITE_IDENTITY = (
    "hetren.asr.critical-number-evaluator-mutation-suite.en-us",
    "1.0.0",
)


@dataclass(frozen=True, slots=True)
class _BoundaryCase:
    case_id: str
    reference_text: str
    generated_text: str
    expected_outcome: str
    expected_preserved: bool | None
    expected_reference_values: tuple[str, ...] | None = None
    expected_generated_values: tuple[str, ...] | None = None
    required_reason_codes: tuple[str, ...] = ()
    required_finding_types: tuple[str, ...] = ()


_V1_1_BOUNDARY_CASES = (
    _BoundaryCase(
        case_id="inherited-v1-1.clock-time-dot-am-equivalence",
        reference_text="meet at nine fifteen AM tomorrow",
        generated_text="meet at 9.15 a.m. tomorrow",
        expected_outcome="preserved",
        expected_preserved=True,
        expected_reference_values=("09:15",),
        expected_generated_values=("09:15",),
        required_reason_codes=("format_equivalent",),
    ),
    _BoundaryCase(
        case_id="inherited-v1-1.clock-time-dot-pm-equivalence",
        reference_text="meet at nine fifteen PM tomorrow",
        generated_text="meet at 9.15 p.m. tomorrow",
        expected_outcome="preserved",
        expected_preserved=True,
        expected_reference_values=("21:15",),
        expected_generated_values=("21:15",),
        required_reason_codes=("format_equivalent",),
    ),
    _BoundaryCase(
        case_id="inherited-v1-1.decimal-dot-remains-decimal",
        reference_text="threshold is 9.15",
        generated_text="threshold is 9.15",
        expected_outcome="preserved",
        expected_preserved=True,
        expected_reference_values=("9.15",),
        expected_generated_values=("9.15",),
    ),
    _BoundaryCase(
        case_id="inherited-v1-1.clock-time-dot-substitution",
        reference_text="meet at nine fifteen AM tomorrow",
        generated_text="meet at 9.50 a.m. tomorrow",
        expected_outcome="not_preserved",
        expected_preserved=False,
        expected_reference_values=("09:15",),
        expected_generated_values=("09:50",),
        required_reason_codes=("value_substitution",),
    ),
    _BoundaryCase(
        case_id="inherited-v1-1.invalid-dot-minute-not-clock",
        reference_text="meet at nine fifteen AM tomorrow",
        generated_text="meet at 9.75 AM tomorrow",
        expected_outcome="not_preserved",
        expected_preserved=False,
    ),
    _BoundaryCase(
        case_id="inherited-v1-1.invalid-dot-hour-not-clock",
        reference_text="meet at nine fifteen PM tomorrow",
        generated_text="meet at 13.15 PM tomorrow",
        expected_outcome="not_preserved",
        expected_preserved=False,
    ),
)


def _make_v1_2_boundary_cases() -> tuple[_BoundaryCase, ...]:
    cases: list[_BoundaryCase] = []

    integer_patterns = (
        "The value is {value}.",
        "The value is {value}!",
        "The value is {value}?",
        "The value is {value};",
        "The value is {value}:",
        "The value is {value}, next.",
        'The value is "{value}".',
        "The value is ({value}).",
        "The value is {value}...",
        "The value is {value}.\n",
    )
    integer_pairs = (
        ("2", "3"),
        ("10", "11"),
    )

    counter = 1
    for reference_value, generated_value in integer_pairs:
        for pattern in integer_patterns:
            cases.append(
                _BoundaryCase(
                    case_id=f"v1-2.integer-substitution.{counter:03d}",
                    reference_text=pattern.format(value=reference_value),
                    generated_text=pattern.format(value=generated_value),
                    expected_outcome="not_preserved",
                    expected_preserved=False,
                    expected_reference_values=(reference_value,),
                    expected_generated_values=(generated_value,),
                    required_reason_codes=("value_substitution",),
                    required_finding_types=("substitution",),
                )
            )
            counter += 1

    decimal_patterns = (
        "The value is {value}.",
        "The value is {value}!",
        "The value is {value}?",
        "The value is {value};",
        "The value is {value}...",
    )
    decimal_pairs = (
        ("2.5", "3.5"),
        ("0.25", "0.5"),
        ("2.5", "25"),
    )

    counter = 1
    for reference_value, generated_value in decimal_pairs:
        for pattern in decimal_patterns:
            cases.append(
                _BoundaryCase(
                    case_id=f"v1-2.decimal-substitution.{counter:03d}",
                    reference_text=pattern.format(value=reference_value),
                    generated_text=pattern.format(value=generated_value),
                    expected_outcome="not_preserved",
                    expected_preserved=False,
                    required_reason_codes=("value_substitution",),
                    required_finding_types=("substitution",),
                )
            )
            counter += 1

    word_digit = (
        ("one", "1", "1"),
        ("two", "2", "2"),
        ("three", "3", "3"),
        ("four", "4", "4"),
        ("five", "5", "5"),
        ("six", "6", "6"),
        ("seven", "7", "7"),
        ("eight", "8", "8"),
        ("nine", "9", "9"),
        ("ten", "10", "10"),
    )

    counter = 1
    for word, digit, canonical in word_digit:
        cases.append(
            _BoundaryCase(
                case_id=f"v1-2.word-digit-equivalence.{counter:03d}",
                reference_text=f"The value is {word}.",
                generated_text=f"The value is {digit}.",
                expected_outcome="preserved",
                expected_preserved=True,
                expected_reference_values=(canonical,),
                expected_generated_values=(canonical,),
                required_reason_codes=("format_equivalent",),
                required_finding_types=("match",),
            )
        )
        counter += 1

    formatting_cases = (
        (
            "grouped-1234",
            "The value is 1,234.",
            "The value is 1234.",
            "1234",
        ),
        (
            "grouped-5678",
            "The value is 5,678.",
            "The value is 5678.",
            "5678",
        ),
        (
            "grouped-decimal",
            "The value is 1,234.50.",
            "The value is 1234.50.",
            "1234.5",
        ),
        (
            "decimal-zero-normalization",
            "The value is 2.50.",
            "The value is 2.5.",
            "2.5",
        ),
        (
            "decimal-trailing-zero-normalization",
            "The value is 12.750.",
            "The value is 12.75.",
            "12.75",
        ),
    )

    for name, reference_text, generated_text, canonical in formatting_cases:
        cases.append(
            _BoundaryCase(
                case_id=f"v1-2.format-equivalence.{name}",
                reference_text=reference_text,
                generated_text=generated_text,
                expected_outcome="preserved",
                expected_preserved=True,
                expected_reference_values=(canonical,),
                expected_generated_values=(canonical,),
                required_reason_codes=("format_equivalent",),
                required_finding_types=("match",),
            )
        )

    multi_patterns = (
        "The first value is {first} and the second value is {second}.",
        "The first value is {first} and the second value is {second}!",
        "The first value is {first} and the second value is {second}?",
        "The first value is {first} and the second value is {second}...",
        'The first value is {first} and the second value is "{second}".',
    )
    multi_pairs = (
        ("10", "2", "3"),
        ("20", "4", "5"),
        ("30", "6", "7"),
    )

    counter = 1
    for first, reference_second, generated_second in multi_pairs:
        for pattern in multi_patterns:
            cases.append(
                _BoundaryCase(
                    case_id=f"v1-2.multiple-number.{counter:03d}",
                    reference_text=pattern.format(
                        first=first,
                        second=reference_second,
                    ),
                    generated_text=pattern.format(
                        first=first,
                        second=generated_second,
                    ),
                    expected_outcome="not_preserved",
                    expected_preserved=False,
                    expected_reference_values=(first, reference_second),
                    expected_generated_values=(first, generated_second),
                    required_reason_codes=("value_substitution",),
                    required_finding_types=("substitution",),
                )
            )
            counter += 1

    unsupported_texts = (
        "The value is 2..",
        "The value is 2....",
        "The value is 2.....",
        "The value is 2.5..",
        "The value is 2.5....",
        "The value is 1,23.",
        "The value is 12,34.",
        "The value is 1,23,456.",
        "The value is 1234,567.",
        "The version is 1.2.3.",
    )

    for index, text in enumerate(unsupported_texts, start=1):
        cases.append(
            _BoundaryCase(
                case_id=f"v1-2.unsupported-boundary.{index:03d}",
                reference_text=text,
                generated_text=text,
                expected_outcome="insufficient_evidence",
                expected_preserved=None,
                required_finding_types=("unsupported",),
            )
        )

    identity_cases = (
        ("integer-period", "The value is 2.", "2"),
        ("integer-bang", "The value is 2!", "2"),
        ("integer-question", "The value is 2?", "2"),
        ("integer-semicolon", "The value is 2;", "2"),
        ("integer-colon", "The value is 2:", "2"),
        ("integer-ellipsis", "The value is 2...", "2"),
        ("integer-newline", "The value is 2.\n", "2"),
        ("decimal-period", "The value is 2.5.", "2.5"),
        ("grouped-period", "The value is 1,234.", "1234"),
        ("grouped-decimal-period", "The value is 1,234.50.", "1234.5"),
    )

    for name, text, canonical in identity_cases:
        cases.append(
            _BoundaryCase(
                case_id=f"v1-2.identity-control.{name}",
                reference_text=text,
                generated_text=text,
                expected_outcome="preserved",
                expected_preserved=True,
                expected_reference_values=(canonical,),
                expected_generated_values=(canonical,),
                required_finding_types=("match",),
            )
        )

    result = tuple(cases)

    if len(result) != CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BOUNDARY_CASES:
        raise HveeContractError(
            "critical-number assurance v1.2 boundary-case count changed: "
            f"{len(result)}"
        )

    if len({case.case_id for case in result}) != len(result):
        raise HveeContractError(
            "critical-number assurance v1.2 boundary case IDs are not unique"
        )

    return result


_V1_2_BOUNDARY_CASES = _make_v1_2_boundary_cases()


_LIMITATIONS = (
    {
        "code": "en_us_scope_only",
        "description": (
            "The evaluator and this assurance evidence are scoped to en-US."
        ),
    },
    {
        "code": "source_visible_synthetic_assurance",
        "description": (
            "The inherited portfolio and v1.2 boundary cases are "
            "source-visible development assurance, not a private holdout."
        ),
    },
    {
        "code": "bounded_expression_support",
        "description": (
            "Unsupported or ambiguous numeric forms remain fail-closed rather "
            "than being interpreted beyond the evaluator's declared scope."
        ),
    },
    {
        "code": "no_production_certification",
        "description": (
            "This artifact grants no production qualification, certification, "
            "release enforcement, or official release authority."
        ),
    },
    {
        "code": "no_run04_model_evidence",
        "description": (
            "This artifact contains evaluator-assurance evidence only and "
            "does not contain Run-04 model predictions or scores."
        ),
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


def calculate_critical_number_assurance_v1_2_sha256(
    payload: object,
) -> str:
    canonical = _canonicalize(
        payload,
        name="critical-number assurance v1.2 payload",
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
class ASRCriticalNumberAssuranceV12Bundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if (
            len(self.sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.sha256
            )
        ):
            raise HveeContractError(
                "critical-number assurance v1.2 SHA-256 is invalid"
            )

        if self.sha256 != calculate_critical_number_assurance_v1_2_sha256(
            self.payload
        ):
            raise HveeContractError(
                "critical-number assurance v1.2 SHA-256 "
                "does not match its payload"
            )


def _require_identities() -> None:
    current = (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.key,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.version,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.evaluation_type,
    )
    default = (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
    )
    historical = (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.key,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.version,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.evaluation_type,
    )
    profile = (
        EN_US_CRITICAL_NUMBER_PROFILE.key,
        EN_US_CRITICAL_NUMBER_PROFILE.version,
        EN_US_CRITICAL_NUMBER_PROFILE.language,
        EN_US_CRITICAL_NUMBER_PROFILE.locale,
    )
    portfolio = (
        CRITICAL_NUMBER_PORTFOLIO_KEY,
        CRITICAL_NUMBER_PORTFOLIO_VERSION,
    )
    mutation_suite = (
        CRITICAL_NUMBER_MUTATION_SUITE_KEY,
        CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
    )

    if current != _EXPECTED_EVALUATOR_IDENTITY:
        raise HveeContractError(
            "critical-number assurance v1.2 evaluator identity changed"
        )

    if default != _EXPECTED_DEFAULT_EVALUATOR_IDENTITY:
        raise HveeContractError(
            "critical-number assurance v1.2 requires default evaluator "
            "to remain v1.1"
        )

    if historical != _EXPECTED_HISTORICAL_EVALUATOR_IDENTITY:
        raise HveeContractError(
            "historical critical-number evaluator identity changed"
        )

    if profile != _EXPECTED_PROFILE_IDENTITY:
        raise HveeContractError(
            "critical-number assurance v1.2 profile identity changed"
        )

    if portfolio != _EXPECTED_PORTFOLIO_IDENTITY:
        raise HveeContractError(
            "critical-number assurance v1.2 portfolio identity changed"
        )

    if mutation_suite != _EXPECTED_MUTATION_SUITE_IDENTITY:
        raise HveeContractError(
            "critical-number assurance v1.2 inherited mutation identity changed"
        )

    if len(CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1) != 9:
        raise HveeContractError(
            "critical-number assurance v1.2 requires nine inherited mutants"
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


def _observation_snapshot(
    observation: Observation,
) -> dict[str, object]:
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


def _boundary_definition(
    case: _BoundaryCase,
) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "reference_text": case.reference_text,
        "generated_text": case.generated_text,
        "expected_outcome": case.expected_outcome,
        "expected_preserved": case.expected_preserved,
        "expected_reference_values": (
            None
            if case.expected_reference_values is None
            else list(case.expected_reference_values)
        ),
        "expected_generated_values": (
            None
            if case.expected_generated_values is None
            else list(case.expected_generated_values)
        ),
        "required_reason_codes": list(case.required_reason_codes),
        "required_finding_types": list(case.required_finding_types),
    }


def _evaluate_boundary(
    case: _BoundaryCase,
    *,
    evaluator,
    strip_periods: bool = False,
) -> dict[str, object]:
    reference_text = case.reference_text
    generated_text = case.generated_text

    if strip_periods:
        reference_text = reference_text.replace(".", "")
        generated_text = generated_text.replace(".", "")

    evaluation = evaluate_critical_number_fidelity(
        reference_text=reference_text,
        generated_text=generated_text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
        evaluator=evaluator,
    )

    reference_values = tuple(
        entity.canonical_value
        for entity in evaluation.reference_entities
    )
    generated_values = tuple(
        entity.canonical_value
        for entity in evaluation.generated_entities
    )
    reason_codes = tuple(
        finding.reason_code.value
        for finding in evaluation.findings
    )
    finding_types = tuple(
        finding.finding_type.value
        for finding in evaluation.findings
    )

    failed: list[str] = []

    if evaluation.outcome.value != case.expected_outcome:
        failed.append("outcome")

    if evaluation.preserved is not case.expected_preserved:
        failed.append("preserved")

    if (
        case.expected_reference_values is not None
        and reference_values != case.expected_reference_values
    ):
        failed.append("reference_values")

    if (
        case.expected_generated_values is not None
        and generated_values != case.expected_generated_values
    ):
        failed.append("generated_values")

    for reason in case.required_reason_codes:
        if reason not in reason_codes:
            failed.append(f"reason:{reason}")

    for finding_type in case.required_finding_types:
        if finding_type not in finding_types:
            failed.append(f"finding_type:{finding_type}")

    return {
        "definition": _boundary_definition(case),
        "actual": {
            "evaluator_version": evaluation.evaluator_version,
            "outcome": evaluation.outcome.value,
            "preserved": evaluation.preserved,
            "reference_values": list(reference_values),
            "generated_values": list(generated_values),
            "reason_codes": list(reason_codes),
            "finding_types": list(finding_types),
        },
        "passed": not failed,
        "failed_checks": failed,
    }


def _boundary_suite_snapshot(
    cases: tuple[_BoundaryCase, ...],
) -> dict[str, object]:
    runs = [
        _evaluate_boundary(
            case,
            evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
        )
        for case in cases
    ]

    failures = sum(not run["passed"] for run in runs)

    return {
        "total_cases": len(runs),
        "passed_cases": len(runs) - failures,
        "failed_cases": failures,
        "passed": failures == 0,
        "case_runs": runs,
    }


def _inherited_mutation_snapshot(report) -> dict[str, object]:
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
                "killed": result.killed,
            }
            for result in report.results
        ],
    }


def _semantic_mutation_result(
    *,
    mutation: str,
) -> dict[str, object]:
    changed_case_ids: list[str] = []

    for case in _V1_2_BOUNDARY_CASES:
        if mutation == "restore_legacy_v1_1_behavior":
            run = _evaluate_boundary(
                case,
                evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR,
            )
        elif mutation == "strip_all_periods":
            run = _evaluate_boundary(
                case,
                evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
                strip_periods=True,
            )
        else:
            raise HveeContractError(
                f"unknown v1.2 semantic mutation: {mutation}"
            )

        if not run["passed"]:
            changed_case_ids.append(case.case_id)

    return {
        "mutation": mutation,
        "changed_case_ids": changed_case_ids,
        "killed": bool(changed_case_ids),
    }


def _semantic_mutation_snapshot() -> dict[str, object]:
    names = (
        "restore_legacy_v1_1_behavior",
        "strip_all_periods",
    )
    results = [
        _semantic_mutation_result(mutation=name)
        for name in names
    ]
    killed = sum(result["killed"] for result in results)

    return {
        "key": (
            "hetren.asr.critical-number-evaluator-"
            "v1-2-boundary-mutations.en-us"
        ),
        "version": "1.0.0",
        "mutations": list(names),
        "total_mutants": len(results),
        "killed_mutants": killed,
        "survived_mutants": len(results) - killed,
        "mutation_score": killed / len(results),
        "results": results,
    }


def build_critical_number_assurance_v1_2_candidate(
) -> ASRCriticalNumberAssuranceV12Bundle:
    _require_identities()

    historical_v1 = verify_critical_number_assurance_profile_v1()
    historical_v1_1 = build_critical_number_assurance_v1_1_candidate()

    if historical_v1.sha256 != CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1:
        raise HveeContractError(
            "historical critical-number v1 assurance changed"
        )

    if historical_v1.sha256 != _HISTORICAL_V1_SHA256:
        raise HveeContractError(
            "historical critical-number v1 assurance digest changed"
        )

    if historical_v1_1.sha256 != _HISTORICAL_V1_1_SHA256:
        raise HveeContractError(
            "historical critical-number v1.1 assurance digest changed"
        )

    baseline = run_critical_number_portfolio(
        CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    )

    inherited_mutations = run_critical_number_evaluator_mutation_suite(
        CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    )

    v1_1_boundary = _boundary_suite_snapshot(_V1_1_BOUNDARY_CASES)
    v1_2_boundary = _boundary_suite_snapshot(_V1_2_BOUNDARY_CASES)
    semantic_mutations = _semantic_mutation_snapshot()

    if (
        baseline.total_cases
        != CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BASE_CASES
        or baseline.failed_cases != 0
        or not baseline.passed
    ):
        raise HveeContractError(
            "critical-number assurance v1.2 inherited portfolio failed"
        )

    if (
        v1_1_boundary["total_cases"]
        != CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_V1_1_BOUNDARY_CASES
        or v1_1_boundary["failed_cases"] != 0
    ):
        raise HveeContractError(
            "critical-number assurance v1.2 failed inherited v1.1 boundaries"
        )

    if (
        v1_2_boundary["total_cases"]
        != CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BOUNDARY_CASES
        or v1_2_boundary["failed_cases"] != 0
    ):
        raise HveeContractError(
            "critical-number assurance v1.2 hostile boundary cases failed"
        )

    if (
        inherited_mutations.total_mutants
        != CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_INHERITED_MUTANTS
        or inherited_mutations.survived_mutants != 0
    ):
        raise HveeContractError(
            "critical-number assurance v1.2 failed inherited mutations"
        )

    if (
        semantic_mutations["total_mutants"]
        != CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_NEW_MUTANTS
        or semantic_mutations["survived_mutants"] != 0
    ):
        raise HveeContractError(
            "critical-number assurance v1.2 failed new semantic mutations"
        )

    result_by_id = {
        result.case_id: result
        for result in baseline.case_results
    }

    observations_by_id = {
        case.case_id: evaluate_critical_number_portfolio_case_observations(
            case,
            evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
        )
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
    }

    payload = {
        "schema_version": CRITICAL_NUMBER_ASSURANCE_V1_2_SCHEMA_VERSION,
        "evaluation_type": "asr",
        "assurance_profile": {
            "key": CRITICAL_NUMBER_ASSURANCE_V1_2_KEY,
            "version": CRITICAL_NUMBER_ASSURANCE_V1_2_VERSION,
            "status": "experimental",
            "intended_use": "run04_public_v2_evaluator_qualification_input",
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "certification_issued": False,
        },
        "bindings": {
            "evaluator": {
                "key": CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.key,
                "version": CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.version,
                "evaluation_type": (
                    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.evaluation_type
                ),
            },
            "default_evaluator_preserved": {
                "key": CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
                "version": CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
                "evaluation_type": (
                    CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type
                ),
            },
            "historical_evaluator_preserved": {
                "key": CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.key,
                "version": CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.version,
                "evaluation_type": (
                    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.evaluation_type
                ),
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
            "inherited_mutation_suite": {
                "key": CRITICAL_NUMBER_MUTATION_SUITE_KEY,
                "version": CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
            },
            "historical_v1_assurance_sha256": historical_v1.sha256,
            "historical_v1_1_assurance_sha256": historical_v1_1.sha256,
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
        "inherited_v1_1_boundary": v1_1_boundary,
        "v1_2_boundary": v1_2_boundary,
        "mutation_assurance": {
            "inherited": _inherited_mutation_snapshot(
                inherited_mutations
            ),
            "v1_2_semantic": semantic_mutations,
        },
        "validity": {
            "expires_on_evaluator_identity_change": True,
            "expires_on_profile_identity_change": True,
            "expires_on_portfolio_identity_change": True,
            "expires_on_mutation_suite_identity_change": True,
            "does_not_supersede_historical_v1_evidence": True,
            "does_not_supersede_historical_v1_1_evidence": True,
            "does_not_promote_default_evaluator": True,
            "does_not_grant_production_authority": True,
        },
        "limitations": list(_LIMITATIONS),
    }

    canonical = _canonicalize(
        payload,
        name="critical-number assurance v1.2 payload",
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            "critical-number assurance v1.2 payload must be an object"
        )

    return ASRCriticalNumberAssuranceV12Bundle(
        payload=canonical,
        sha256=calculate_critical_number_assurance_v1_2_sha256(
            canonical
        ),
    )


def verify_critical_number_assurance_v1_2_candidate(
    *,
    payload: object,
    expected_sha256: object,
) -> ASRCriticalNumberAssuranceV12Bundle:
    if not isinstance(expected_sha256, str):
        raise HveeContractError(
            "expected critical-number assurance v1.2 SHA-256 "
            "must be a string"
        )

    canonical = _canonicalize(
        payload,
        name="supplied critical-number assurance v1.2 payload",
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            "supplied critical-number assurance v1.2 payload "
            "must be an object"
        )

    supplied = ASRCriticalNumberAssuranceV12Bundle(
        payload=canonical,
        sha256=expected_sha256,
    )

    rebuilt = build_critical_number_assurance_v1_2_candidate()

    if supplied != rebuilt:
        raise HveeContractError(
            "critical-number assurance v1.2 does not match "
            "the reproducible build"
        )

    return rebuilt


__all__ = [
    "ASRCriticalNumberAssuranceV12Bundle",
    "CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BASE_CASES",
    "CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BOUNDARY_CASES",
    "CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_INHERITED_MUTANTS",
    "CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_NEW_MUTANTS",
    "CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_V1_1_BOUNDARY_CASES",
    "CRITICAL_NUMBER_ASSURANCE_V1_2_KEY",
    "CRITICAL_NUMBER_ASSURANCE_V1_2_SCHEMA_VERSION",
    "CRITICAL_NUMBER_ASSURANCE_V1_2_VERSION",
    "build_critical_number_assurance_v1_2_candidate",
    "calculate_critical_number_assurance_v1_2_sha256",
    "verify_critical_number_assurance_v1_2_candidate",
]
