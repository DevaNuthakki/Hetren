from __future__ import annotations

from dataclasses import dataclass

import pytest

from hvee.core.contracts import HveeContractError
from hvee.laboratory.semantic.portfolio import (
    SemanticPortfolioReport,
    run_semantic_portfolio,
    validate_semantic_cases,
)


@dataclass(frozen=True, slots=True)
class SyntheticCase:
    case_id: str
    should_pass: bool


@dataclass(frozen=True, slots=True)
class SyntheticResult:
    case_id: str
    passed: bool


def _run_case(
    case: SyntheticCase,
) -> SyntheticResult:
    return SyntheticResult(
        case_id=case.case_id,
        passed=case.should_pass,
    )


def test_semantic_portfolio_runs_without_domain_knowledge():
    report = run_semantic_portfolio(
        portfolio_key="synthetic.semantic.portfolio",
        portfolio_version="1.0.0",
        cases=(
            SyntheticCase(
                case_id="case.pass",
                should_pass=True,
            ),
            SyntheticCase(
                case_id="case.fail",
                should_pass=False,
            ),
        ),
        run_case=_run_case,
    )

    assert report.total_cases == 2
    assert report.passed_cases == 1
    assert report.failed_cases == 1
    assert report.passed is False


def test_semantic_portfolio_passes_only_when_every_case_passes():
    report = run_semantic_portfolio(
        portfolio_key="synthetic.semantic.portfolio",
        portfolio_version="1.0.0",
        cases=(
            SyntheticCase(
                case_id="case.one",
                should_pass=True,
            ),
            SyntheticCase(
                case_id="case.two",
                should_pass=True,
            ),
        ),
        run_case=_run_case,
    )

    assert report.total_cases == 2
    assert report.passed_cases == 2
    assert report.failed_cases == 0
    assert report.passed is True


def test_empty_report_is_not_a_passing_portfolio():
    report = SemanticPortfolioReport[
        SyntheticResult
    ](
        portfolio_key="synthetic.semantic.portfolio",
        portfolio_version="1.0.0",
        case_results=(),
    )

    assert report.total_cases == 0
    assert report.passed is False


def test_semantic_cases_require_unique_ids():
    cases = (
        SyntheticCase(
            case_id="duplicate",
            should_pass=True,
        ),
        SyntheticCase(
            case_id="duplicate",
            should_pass=True,
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="case ids must be unique",
    ):
        validate_semantic_cases(cases)


def test_semantic_portfolio_rejects_mismatched_result_identity():
    def wrong_result(
        case: SyntheticCase,
    ) -> SyntheticResult:
        return SyntheticResult(
            case_id="different.case",
            passed=True,
        )

    with pytest.raises(
        HveeContractError,
        match="does not match",
    ):
        run_semantic_portfolio(
            portfolio_key="synthetic.semantic.portfolio",
            portfolio_version="1.0.0",
            cases=(
                SyntheticCase(
                    case_id="expected.case",
                    should_pass=True,
                ),
            ),
            run_case=wrong_result,
        )


def test_semantic_report_rejects_duplicate_result_ids():
    with pytest.raises(
        HveeContractError,
        match="result case ids must be unique",
    ):
        SemanticPortfolioReport[
            SyntheticResult
        ](
            portfolio_key="synthetic.semantic.portfolio",
            portfolio_version="1.0.0",
            case_results=(
                SyntheticResult(
                    case_id="duplicate",
                    passed=True,
                ),
                SyntheticResult(
                    case_id="duplicate",
                    passed=False,
                ),
            ),
        )
