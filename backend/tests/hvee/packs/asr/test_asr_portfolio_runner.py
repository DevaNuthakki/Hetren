from __future__ import annotations

from dataclasses import replace

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.portfolio import (
    ASR_EVALUATION_PORTFOLIO_V1,
    ASRPortfolioExpectedObservation,
)
from hvee.packs.asr.portfolio_runner import (
    compare_asr_portfolio_case,
    evaluate_asr_portfolio_case_observations,
    run_asr_portfolio,
    run_asr_portfolio_case,
)


def _case(case_id: str):
    matches = [
        case
        for case
        in ASR_EVALUATION_PORTFOLIO_V1.cases
        if case.case_id == case_id
    ]

    assert len(matches) == 1
    return matches[0]


def test_runner_produces_current_transcript_observation_bundle():
    case = _case("control.exact")

    observations = (
        evaluate_asr_portfolio_case_observations(
            case
        )
    )

    assert len(observations) == 15

    identities = {
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
        )
        for observation
        in observations
    }

    assert len(identities) == 15

    assert all(
        observation.status
        == ObservationStatus.SUCCESS
        for observation
        in observations
    )


def test_exact_control_passes_real_evaluators():
    result = run_asr_portfolio_case(
        _case("control.exact")
    )

    assert result.passed is True
    assert result.total_expectations == 8
    assert result.matched_expectations == 8
    assert result.mismatched_expectations == 0


def test_normalization_equivalent_control_passes_real_evaluators():
    result = run_asr_portfolio_case(
        _case(
            "control.normalization-equivalent"
        )
    )

    assert result.passed is True
    assert result.mismatched_expectations == 0


@pytest.mark.parametrize(
    "case_id",
    [
        "mutation.word-substitution",
        "mutation.word-deletion",
        "mutation.word-insertion",
        "mutation.missing-output",
        "mutation.unexpected-output",
        "mutation.numeric-substitution",
        "mutation.numeric-deletion",
        "mutation.numeric-insertion",
        "mutation.numeric-reorder",
    ],
)
def test_controlled_mutation_is_recognized(
    case_id: str,
):
    result = run_asr_portfolio_case(
        _case(case_id)
    )

    assert result.passed is True
    assert result.mismatched_expectations == 0


def test_full_portfolio_passes_current_pinned_evaluators():
    report = run_asr_portfolio(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    assert report.portfolio_key == (
        "hetren.asr.evaluation-portfolio"
    )
    assert report.portfolio_version == "1.0.0"

    assert report.total_cases == 12
    assert report.passed_cases == 12
    assert report.failed_cases == 0

    assert report.total_expectations == 103
    assert report.matched_expectations == 103
    assert report.mismatched_expectations == 0

    assert report.passed is True


def test_wrong_expected_value_is_reported_as_mismatch():
    original = _case("control.exact")

    exact_expectation = next(
        expectation
        for expectation
        in original.expectations
        if expectation.metric_key
        == "asr.exact-match.normalized-basic"
    )

    wrong_expectation = replace(
        exact_expectation,
        expected_value=False,
    )

    modified = replace(
        original,
        expectations=(wrong_expectation,),
    )

    result = run_asr_portfolio_case(
        modified
    )

    assert result.passed is False
    assert result.total_expectations == 1
    assert result.matched_expectations == 0
    assert result.mismatched_expectations == 1

    expectation_result = (
        result.expectation_results[0]
    )

    assert (
        expectation_result.actual_status
        == ObservationStatus.SUCCESS
    )
    assert expectation_result.actual_value is True
    assert expectation_result.matched is False


def test_missing_expected_identity_fails_loudly():
    case = _case("control.exact")

    observations = (
        evaluate_asr_portfolio_case_observations(
            case
        )
    )

    missing_identity_observations = tuple(
        observation
        for observation
        in observations
        if observation.metric_key
        != "asr.exact-match.normalized-basic"
    )

    with pytest.raises(
        HveeContractError,
        match="was not produced",
    ):
        compare_asr_portfolio_case(
            case=case,
            observations=(
                missing_identity_observations
            ),
        )


def test_duplicate_observation_identity_fails_loudly():
    case = _case("control.exact")

    observations = (
        evaluate_asr_portfolio_case_observations(
            case
        )
    )

    with pytest.raises(
        HveeContractError,
        match="duplicate scientific identity",
    ):
        compare_asr_portfolio_case(
            case=case,
            observations=(
                observations
                + (observations[0],)
            ),
        )


def test_same_identity_with_changed_value_type_fails_loudly():
    case = _case("control.exact")

    expectation = next(
        expectation
        for expectation
        in case.expectations
        if expectation.metric_key
        == "asr.exact-match.normalized-basic"
    )

    changed_type = Observation(
        metric_key=expectation.metric_key,
        metric_version=expectation.metric_version,
        evaluator_key=expectation.evaluator_key,
        evaluator_version=(
            expectation.evaluator_version
        ),
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.INTEGER,
        value=1,
    )

    modified_case = replace(
        case,
        expectations=(expectation,),
    )

    with pytest.raises(
        HveeContractError,
        match="changed value type",
    ):
        compare_asr_portfolio_case(
            case=modified_case,
            observations=(changed_type,),
        )


def test_non_success_observation_does_not_satisfy_expectation():
    case = _case("control.exact")

    expectation = next(
        expectation
        for expectation
        in case.expectations
        if expectation.metric_key
        == "asr.exact-match.normalized-basic"
    )

    unavailable = Observation(
        metric_key=expectation.metric_key,
        metric_version=expectation.metric_version,
        evaluator_key=expectation.evaluator_key,
        evaluator_version=(
            expectation.evaluator_version
        ),
        evaluation_type="asr",
        status=ObservationStatus.ABSTAINED,
        value_type=expectation.value_type,
        status_detail=(
            "controlled portfolio abstention"
        ),
    )

    modified_case = replace(
        case,
        expectations=(expectation,),
    )

    result = compare_asr_portfolio_case(
        case=modified_case,
        observations=(unavailable,),
    )

    assert result.passed is False

    expectation_result = (
        result.expectation_results[0]
    )

    assert (
        expectation_result.actual_status
        == ObservationStatus.ABSTAINED
    )
    assert expectation_result.actual_value is None
    assert expectation_result.matched is False


def test_portfolio_expected_identity_remains_version_pinned():
    case = _case("control.exact")

    expectation = (
        ASRPortfolioExpectedObservation(
            metric_key=(
                "asr.exact-match.normalized-basic"
            ),
            metric_version="999.0.0",
            evaluator_key=(
                "hetren.asr.transcript-integrity."
                "normalized-basic"
            ),
            evaluator_version="1.0.0",
            value_type=MetricValueType.BOOLEAN,
            expected_value=True,
        )
    )

    modified_case = replace(
        case,
        expectations=(expectation,),
    )

    with pytest.raises(
        HveeContractError,
        match="was not produced",
    ):
        run_asr_portfolio_case(
            modified_case
        )
