from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.evaluator_mutation import (
    ASR_EVALUATOR_MUTATIONS_V1,
    ASR_EVALUATOR_MUTATION_SUITE_KEY,
    ASR_EVALUATOR_MUTATION_SUITE_VERSION,
    ASREvaluatorMutationReport,
    run_asr_evaluator_mutation_suite,
)
from hvee.packs.asr.portfolio import (
    ASRPortfolioCase,
    ASRPortfolioDefinition,
)
from hvee.packs.asr.portfolio_runner import (
    ASRPortfolioCaseResult,
    ASRPortfolioReport,
    run_asr_portfolio,
)


ASR_PORTFOLIO_EVIDENCE_SCHEMA_VERSION = 1


def _canonicalize_json_value(
    value: object,
    *,
    name: str,
) -> object:
    """
    Canonicalize JSON using the established Hetren evidence convention.

    This intentionally matches decision and observation evidence:
    UTF-8 JSON, Unicode preserved, keys sorted, compact separators,
    and non-finite numeric values rejected.
    """

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


def calculate_asr_portfolio_evidence_sha256(
    payload: object,
) -> str:
    canonical = _canonical_json(
        payload,
        name="ASR portfolio evidence payload",
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRPortfolioEvidenceBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        canonical = _canonicalize_json_value(
            self.payload,
            name="ASR portfolio evidence payload",
        )

        if not isinstance(canonical, dict):
            raise HveeContractError(
                "ASR portfolio evidence payload "
                "must be a JSON object"
            )

        _require_sha256_hex(
            name="ASR portfolio evidence SHA-256",
            value=self.sha256,
        )

        expected = (
            calculate_asr_portfolio_evidence_sha256(
                canonical
            )
        )

        if self.sha256 != expected:
            raise HveeContractError(
                "ASR portfolio evidence SHA-256 "
                "does not match its payload"
            )


def _case_snapshot(
    case: ASRPortfolioCase,
) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "mutation": case.mutation.value,
        "reference_text": case.reference_text,
        "generated_text": case.generated_text,
        "description": case.description,
        "tags": list(case.tags),
        "expectations": [
            {
                "metric_key": expectation.metric_key,
                "metric_version": (
                    expectation.metric_version
                ),
                "evaluator_key": (
                    expectation.evaluator_key
                ),
                "evaluator_version": (
                    expectation.evaluator_version
                ),
                "value_type": (
                    expectation.value_type.value
                ),
                "expected_value": (
                    expectation.expected_value
                ),
            }
            for expectation
            in case.expectations
        ],
    }


def _case_result_snapshot(
    result: ASRPortfolioCaseResult,
) -> dict[str, object]:
    return {
        "case_id": result.case_id,
        "mutation": result.mutation.value,
        "passed": result.passed,
        "total_expectations": (
            result.total_expectations
        ),
        "matched_expectations": (
            result.matched_expectations
        ),
        "mismatched_expectations": (
            result.mismatched_expectations
        ),
        "expectation_results": [
            {
                "metric_key": (
                    item.expectation.metric_key
                ),
                "metric_version": (
                    item.expectation.metric_version
                ),
                "evaluator_key": (
                    item.expectation.evaluator_key
                ),
                "evaluator_version": (
                    item.expectation.evaluator_version
                ),
                "value_type": (
                    item.expectation.value_type.value
                ),
                "expected_value": (
                    item.expectation.expected_value
                ),
                "actual_status": (
                    item.actual_status.value
                ),
                "actual_value": item.actual_value,
                "matched": item.matched,
            }
            for item
            in result.expectation_results
        ],
    }


def _portfolio_report_snapshot(
    report: ASRPortfolioReport,
) -> dict[str, object]:
    return {
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "failed_cases": report.failed_cases,
        "total_expectations": (
            report.total_expectations
        ),
        "matched_expectations": (
            report.matched_expectations
        ),
        "mismatched_expectations": (
            report.mismatched_expectations
        ),
        "passed": report.passed,
        "case_results": [
            _case_result_snapshot(result)
            for result
            in report.case_results
        ],
    }


def _mutation_report_snapshot(
    report: ASREvaluatorMutationReport,
) -> dict[str, object]:
    return {
        "key": ASR_EVALUATOR_MUTATION_SUITE_KEY,
        "version": (
            ASR_EVALUATOR_MUTATION_SUITE_VERSION
        ),
        "mutations": [
            mutation.value
            for mutation
            in ASR_EVALUATOR_MUTATIONS_V1
        ],
        "total_mutants": report.total_mutants,
        "killed_mutants": report.killed_mutants,
        "survived_mutants": (
            report.survived_mutants
        ),
        "mutation_score": report.mutation_score,
        "results": [
            {
                "mutation": result.mutation.value,
                "changed_case_ids": list(
                    result.changed_case_ids
                ),
                "detected_case_ids": list(
                    result.detected_case_ids
                ),
                "changed_cases": (
                    result.changed_cases
                ),
                "detected_cases": (
                    result.detected_cases
                ),
                "killed": result.killed,
            }
            for result
            in report.results
        ],
    }


def build_asr_portfolio_evidence_bundle(
    portfolio: ASRPortfolioDefinition,
) -> ASRPortfolioEvidenceBundle:
    """
    Build reproducible evaluator-calibration evidence.

    The bundle binds the exact portfolio definition, pinned evaluator
    expectations, actual baseline evaluator results, and the exact
    versioned synthetic evaluator-mutation suite/results.

    No timestamps are included because time is not part of the
    scientific identity of this deterministic calibration artifact.
    """

    if not isinstance(
        portfolio,
        ASRPortfolioDefinition,
    ):
        raise HveeContractError(
            "ASR portfolio evidence requires "
            "ASRPortfolioDefinition"
        )

    baseline = run_asr_portfolio(
        portfolio
    )

    if not baseline.passed:
        raise HveeContractError(
            "ASR portfolio evidence requires "
            "a passing baseline portfolio"
        )

    mutations = (
        run_asr_evaluator_mutation_suite(
            portfolio
        )
    )

    payload = {
        "schema_version": (
            ASR_PORTFOLIO_EVIDENCE_SCHEMA_VERSION
        ),
        "evaluation_type": "asr",
        "portfolio": {
            "key": portfolio.key,
            "version": portfolio.version,
            "cases": [
                _case_snapshot(case)
                for case
                in portfolio.cases
            ],
        },
        "baseline": (
            _portfolio_report_snapshot(
                baseline
            )
        ),
        "evaluator_mutation_suite": (
            _mutation_report_snapshot(
                mutations
            )
        ),
    }

    canonical = _canonicalize_json_value(
        payload,
        name="ASR portfolio evidence payload",
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            "ASR portfolio evidence payload "
            "must canonicalize to a JSON object"
        )

    return ASRPortfolioEvidenceBundle(
        payload=canonical,
        sha256=(
            calculate_asr_portfolio_evidence_sha256(
                canonical
            )
        ),
    )


def verify_asr_portfolio_evidence_bundle(
    *,
    portfolio: ASRPortfolioDefinition,
    payload: object,
    expected_sha256: object,
) -> ASRPortfolioEvidenceBundle:
    """
    Re-run the exact portfolio and mutation suite and verify binding.

    This verifies deterministic integrity and reproducibility against
    the currently installed evaluator implementations identified by
    the portfolio's pinned scientific identities.

    It is not a claim that the finite portfolio covers every possible
    ASR or evaluator failure.
    """

    expected_digest = _require_sha256_hex(
        name="expected ASR portfolio evidence SHA-256",
        value=expected_sha256,
    )

    supplied_payload = _canonicalize_json_value(
        payload,
        name="supplied ASR portfolio evidence payload",
    )

    if not isinstance(
        supplied_payload,
        dict,
    ):
        raise HveeContractError(
            "supplied ASR portfolio evidence "
            "payload must be a JSON object"
        )

    supplied_digest = (
        calculate_asr_portfolio_evidence_sha256(
            supplied_payload
        )
    )

    if supplied_digest != expected_digest:
        raise HveeContractError(
            "supplied ASR portfolio evidence "
            "does not match expected SHA-256"
        )

    rebuilt = (
        build_asr_portfolio_evidence_bundle(
            portfolio
        )
    )

    if supplied_payload != rebuilt.payload:
        raise HveeContractError(
            "ASR portfolio evidence does not match "
            "the reproducibly rebuilt evidence"
        )

    if expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "ASR portfolio evidence SHA-256 does not "
            "match the reproducibly rebuilt evidence"
        )

    return rebuilt
