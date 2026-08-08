from dataclasses import FrozenInstanceError

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


def test_metric_definition_has_stable_identity():
    metric = MetricDefinition(
        key="asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        value_type=MetricValueType.NUMBER,
        direction=MetricDirection.LOWER_IS_BETTER,
        unit="ratio",
        description="Word error rate.",
    )

    assert metric.key == "asr.wer"
    assert metric.version == "1.0.0"


def test_metric_definition_is_frozen():
    metric = MetricDefinition(
        key="asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        value_type=MetricValueType.NUMBER,
        direction=MetricDirection.LOWER_IS_BETTER,
        description="Word error rate.",
    )

    with pytest.raises(FrozenInstanceError):
        metric.key = "asr.cer"


def test_metric_definition_rejects_noncanonical_key():
    with pytest.raises(HveeContractError):
        MetricDefinition(
            key="ASR WER",
            version="1.0.0",
            evaluation_type="asr",
            value_type=MetricValueType.NUMBER,
            direction=MetricDirection.LOWER_IS_BETTER,
            description="Word error rate.",
        )


def test_evaluator_version_has_identity_separate_from_metric():
    evaluator = EvaluatorVersion(
        key="hetren.asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        description="Deterministic ASR WER evaluator.",
    )

    assert evaluator.key == "hetren.asr.wer"
    assert evaluator.version == "1.0.0"


def test_successful_numeric_observation():
    observation = Observation(
        metric_key="asr.wer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=0.125,
    )

    assert observation.value == 0.125


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
    ],
)
def test_numeric_observation_rejects_invalid_values(value):
    with pytest.raises(HveeContractError):
        Observation(
            metric_key="asr.wer",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.wer",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            status=ObservationStatus.SUCCESS,
            value_type=MetricValueType.NUMBER,
            value=value,
        )


def test_successful_observation_requires_value():
    with pytest.raises(HveeContractError):
        Observation(
            metric_key="asr.wer",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.wer",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            status=ObservationStatus.SUCCESS,
            value_type=MetricValueType.NUMBER,
        )


@pytest.mark.parametrize(
    "status",
    [
        ObservationStatus.ABSTAINED,
        ObservationStatus.UNSUPPORTED,
        ObservationStatus.TIMED_OUT,
        ObservationStatus.FAILED,
        ObservationStatus.CANCELLED,
        ObservationStatus.INVALID,
    ],
)
def test_non_success_observation_has_no_value(status):
    observation = Observation(
        metric_key="asr.wer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=status,
        value_type=MetricValueType.NUMBER,
        status_detail="Evaluator did not produce a measurement.",
    )

    assert observation.value is None


def test_non_success_observation_requires_status_detail():
    with pytest.raises(HveeContractError):
        Observation(
            metric_key="asr.wer",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.wer",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            status=ObservationStatus.FAILED,
            value_type=MetricValueType.NUMBER,
        )


def test_non_success_observation_rejects_value():
    with pytest.raises(HveeContractError):
        Observation(
            metric_key="asr.wer",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.wer",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            status=ObservationStatus.FAILED,
            value_type=MetricValueType.NUMBER,
            value=0.10,
            status_detail="Evaluator failed.",
        )


def test_boolean_is_not_accepted_as_integer():
    with pytest.raises(HveeContractError):
        Observation(
            metric_key="asr.error_count",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.error_count",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            status=ObservationStatus.SUCCESS,
            value_type=MetricValueType.INTEGER,
            value=True,
        )


def test_json_observation_requires_json_serializable_value():
    with pytest.raises(HveeContractError):
        Observation(
            metric_key="asr.alignment",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.alignment",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            status=ObservationStatus.SUCCESS,
            value_type=MetricValueType.JSON,
            value={"invalid": {1, 2, 3}},
        )


def test_json_observation_rejects_non_finite_number():
    with pytest.raises(HveeContractError):
        Observation(
            metric_key="asr.alignment",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.alignment",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            status=ObservationStatus.SUCCESS,
            value_type=MetricValueType.JSON,
            value={"score": float("nan")},
        )
