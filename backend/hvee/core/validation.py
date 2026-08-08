from __future__ import annotations

from hvee.core.contracts import (
    EvaluatorVersion,
    HveeContractError,
    MetricDefinition,
    Observation,
)


def validate_observation_contract(
    *,
    metric: MetricDefinition,
    evaluator: EvaluatorVersion,
    observation: Observation,
) -> None:
    """
    Validate the identities and types that bind an observation to the
    metric definition and evaluator version that produced it.

    This validation is intentionally independent of persistence and
    application infrastructure.
    """

    if observation.metric_key != metric.key:
        raise HveeContractError(
            "observation metric key does not match metric definition"
        )

    if observation.metric_version != metric.version:
        raise HveeContractError(
            "observation metric version does not match metric definition"
        )

    if observation.evaluator_key != evaluator.key:
        raise HveeContractError(
            "observation evaluator key does not match evaluator version"
        )

    if observation.evaluator_version != evaluator.version:
        raise HveeContractError(
            "observation evaluator version does not match evaluator version"
        )

    if observation.evaluation_type != metric.evaluation_type:
        raise HveeContractError(
            "observation evaluation type does not match metric definition"
        )

    if observation.evaluation_type != evaluator.evaluation_type:
        raise HveeContractError(
            "observation evaluation type does not match evaluator version"
        )

    if metric.evaluation_type != evaluator.evaluation_type:
        raise HveeContractError(
            "metric definition and evaluator version have "
            "different evaluation types"
        )

    if observation.value_type != metric.value_type:
        raise HveeContractError(
            "observation value type does not match metric definition"
        )
