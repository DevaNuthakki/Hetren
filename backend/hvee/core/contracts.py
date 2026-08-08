from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)


class HveeContractError(ValueError):
    """Raised when an HVEE domain contract is invalid."""


class MetricValueType(StrEnum):
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING = "string"
    JSON = "json"


class MetricDirection(StrEnum):
    LOWER_IS_BETTER = "lower_is_better"
    HIGHER_IS_BETTER = "higher_is_better"
    TARGET_IS_BETTER = "target_is_better"
    INFORMATIONAL = "informational"


class ObservationStatus(StrEnum):
    SUCCESS = "success"
    ABSTAINED = "abstained"
    UNSUPPORTED = "unsupported"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INVALID = "invalid"


def _validate_identifier(
    field_name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(
        value
    ):
        raise HveeContractError(
            f"{field_name} must be a canonical lowercase identifier"
        )


def _validate_version(
    field_name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise HveeContractError(
            f"{field_name} must be a non-empty string"
        )

    if value != value.strip():
        raise HveeContractError(
            f"{field_name} cannot contain surrounding whitespace"
        )

    if len(value) > 100:
        raise HveeContractError(
            f"{field_name} cannot exceed 100 characters"
        )


def _validate_description(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise HveeContractError(
            "description must be a non-empty string"
        )


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    key: str
    version: str
    evaluation_type: str
    value_type: MetricValueType
    direction: MetricDirection
    description: str
    unit: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("metric key", self.key)
        _validate_identifier(
            "evaluation type",
            self.evaluation_type,
        )
        _validate_version(
            "metric version",
            self.version,
        )
        _validate_description(self.description)

        if self.unit is not None:
            if not isinstance(self.unit, str) or not self.unit.strip():
                raise HveeContractError(
                    "metric unit must be non-empty when provided"
                )

            if len(self.unit) > 64:
                raise HveeContractError(
                    "metric unit cannot exceed 64 characters"
                )


@dataclass(frozen=True, slots=True)
class EvaluatorVersion:
    key: str
    version: str
    evaluation_type: str
    description: str

    def __post_init__(self) -> None:
        _validate_identifier("evaluator key", self.key)
        _validate_identifier(
            "evaluation type",
            self.evaluation_type,
        )
        _validate_version(
            "evaluator version",
            self.version,
        )
        _validate_description(self.description)


@dataclass(frozen=True, slots=True)
class Observation:
    metric_key: str
    metric_version: str
    evaluator_key: str
    evaluator_version: str
    evaluation_type: str
    status: ObservationStatus
    value_type: MetricValueType
    value: Any | None = None
    status_detail: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier(
            "metric key",
            self.metric_key,
        )
        _validate_version(
            "metric version",
            self.metric_version,
        )
        _validate_identifier(
            "evaluator key",
            self.evaluator_key,
        )
        _validate_version(
            "evaluator version",
            self.evaluator_version,
        )
        _validate_identifier(
            "evaluation type",
            self.evaluation_type,
        )

        if self.status != ObservationStatus.SUCCESS:
            if self.value is not None:
                raise HveeContractError(
                    "non-success observations cannot contain a value"
                )

            if (
                self.status_detail is None
                or not self.status_detail.strip()
            ):
                raise HveeContractError(
                    "non-success observations require status detail"
                )

            return

        if self.value is None:
            raise HveeContractError(
                "successful observations must contain a value"
            )

        self._validate_value()

    def _validate_value(self) -> None:
        if self.value_type == MetricValueType.NUMBER:
            if (
                isinstance(self.value, bool)
                or not isinstance(self.value, (int, float))
                or not isfinite(float(self.value))
            ):
                raise HveeContractError(
                    "number observations require a finite numeric value"
                )

        elif self.value_type == MetricValueType.INTEGER:
            if (
                isinstance(self.value, bool)
                or not isinstance(self.value, int)
            ):
                raise HveeContractError(
                    "integer observations require an integer value"
                )

        elif self.value_type == MetricValueType.BOOLEAN:
            if not isinstance(self.value, bool):
                raise HveeContractError(
                    "boolean observations require a boolean value"
                )

        elif self.value_type == MetricValueType.STRING:
            if not isinstance(self.value, str):
                raise HveeContractError(
                    "string observations require a string value"
                )

        elif self.value_type == MetricValueType.JSON:
            try:
                json.dumps(
                    self.value,
                    allow_nan=False,
                )
            except (TypeError, ValueError) as exc:
                raise HveeContractError(
                    "JSON observations require a JSON-serializable value"
                ) from exc
