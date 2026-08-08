import pytest

from hvee.core.contracts import (
    EvaluatorVersion,
    HveeContractError,
    MetricDefinition,
    MetricDirection,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.core.validation import (
    validate_observation_contract,
)


def build_metric() -> MetricDefinition:
    return MetricDefinition(
        key="asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        value_type=MetricValueType.NUMBER,
        direction=MetricDirection.LOWER_IS_BETTER,
        unit="ratio",
        description="Word error rate.",
    )


def build_evaluator() -> EvaluatorVersion:
    return EvaluatorVersion(
        key="hetren.asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        description="Deterministic ASR WER evaluator.",
    )


def build_observation() -> Observation:
    return Observation(
        metric_key="asr.wer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=0.125,
    )


def test_matching_observation_contract_is_valid():
    validate_observation_contract(
        metric=build_metric(),
        evaluator=build_evaluator(),
        observation=build_observation(),
    )


def test_rejects_wrong_metric_key():
    observation = Observation(
        metric_key="asr.cer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=0.125,
    )

    with pytest.raises(
        HveeContractError,
        match="metric key",
    ):
        validate_observation_contract(
            metric=build_metric(),
            evaluator=build_evaluator(),
            observation=observation,
        )


def test_rejects_wrong_metric_version():
    observation = Observation(
        metric_key="asr.wer",
        metric_version="2.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=0.125,
    )

    with pytest.raises(
        HveeContractError,
        match="metric version",
    ):
        validate_observation_contract(
            metric=build_metric(),
            evaluator=build_evaluator(),
            observation=observation,
        )


def test_rejects_wrong_evaluator_key():
    observation = Observation(
        metric_key="asr.wer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.other",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=0.125,
    )

    with pytest.raises(
        HveeContractError,
        match="evaluator key",
    ):
        validate_observation_contract(
            metric=build_metric(),
            evaluator=build_evaluator(),
            observation=observation,
        )


def test_rejects_wrong_evaluator_version():
    observation = Observation(
        metric_key="asr.wer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="2.0.0",
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=0.125,
    )

    with pytest.raises(
        HveeContractError,
        match="evaluator version",
    ):
        validate_observation_contract(
            metric=build_metric(),
            evaluator=build_evaluator(),
            observation=observation,
        )


def test_rejects_metric_evaluation_type_mismatch():
    metric = MetricDefinition(
        key="asr.wer",
        version="1.0.0",
        evaluation_type="speech",
        value_type=MetricValueType.NUMBER,
        direction=MetricDirection.LOWER_IS_BETTER,
        description="Word error rate.",
    )

    with pytest.raises(
        HveeContractError,
        match="metric definition",
    ):
        validate_observation_contract(
            metric=metric,
            evaluator=build_evaluator(),
            observation=build_observation(),
        )


def test_rejects_evaluator_evaluation_type_mismatch():
    evaluator = EvaluatorVersion(
        key="hetren.asr.wer",
        version="1.0.0",
        evaluation_type="speech",
        description="Wrong-domain evaluator.",
    )

    with pytest.raises(
        HveeContractError,
        match="evaluator version",
    ):
        validate_observation_contract(
            metric=build_metric(),
            evaluator=evaluator,
            observation=build_observation(),
        )


def test_rejects_wrong_value_type():
    observation = Observation(
        metric_key="asr.wer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.INTEGER,
        value=1,
    )

    with pytest.raises(
        HveeContractError,
        match="value type",
    ):
        validate_observation_contract(
            metric=build_metric(),
            evaluator=build_evaluator(),
            observation=observation,
        )
