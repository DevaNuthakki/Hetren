from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)


OBSERVATION_EVIDENCE_SCHEMA_VERSION = 1

_ALLOWED_SCOPES = frozenset(
    {
        "run",
        "test_case",
    }
)


def _require_non_empty_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
    ):
        raise HveeContractError(
            f"{name} must be a non-empty string "
            "without surrounding whitespace"
        )

    return value


def _require_positive_integer(
    *,
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        raise HveeContractError(
            f"{name} must be a positive integer"
        )

    return value


def _canonicalize_json_value(
    value: object,
) -> object:
    """
    Normalize a JSON-compatible value through deterministic JSON.

    This also rejects NaN, infinity, unserializable values, and
    dictionary key combinations that cannot be deterministically
    sorted.
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
            "observation JSON value must be valid "
            "deterministic JSON"
        ) from exc


def _canonicalize_evidence_body(
    body: dict[str, Any],
) -> str:
    try:
        return json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "observation evidence must contain valid "
            "deterministic JSON"
        ) from exc


def calculate_observation_evidence_sha256(
    body: dict[str, Any],
) -> str:
    canonical = _canonicalize_evidence_body(
        body
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ObservationEvidenceRecord:
    metric_key: str
    metric_version: str
    evaluator_key: str
    evaluator_version: str
    evaluation_type: str
    scope: str
    evaluation_run_id: int
    test_case_id: int | None
    status: ObservationStatus
    value_type: MetricValueType
    value: object | None
    status_detail: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(
            name="metric key",
            value=self.metric_key,
        )
        _require_non_empty_string(
            name="metric version",
            value=self.metric_version,
        )
        _require_non_empty_string(
            name="evaluator key",
            value=self.evaluator_key,
        )
        _require_non_empty_string(
            name="evaluator version",
            value=self.evaluator_version,
        )
        _require_non_empty_string(
            name="evaluation type",
            value=self.evaluation_type,
        )

        if self.scope not in _ALLOWED_SCOPES:
            raise HveeContractError(
                "observation evidence scope must be "
                "'run' or 'test_case'"
            )

        _require_positive_integer(
            name="evaluation run id",
            value=self.evaluation_run_id,
        )

        if self.scope == "run":
            if self.test_case_id is not None:
                raise HveeContractError(
                    "run-scoped observation evidence "
                    "cannot target a test case"
                )
        else:
            _require_positive_integer(
                name="test case id",
                value=self.test_case_id,
            )

        if not isinstance(
            self.status,
            ObservationStatus,
        ):
            raise HveeContractError(
                "observation evidence status must be "
                "an ObservationStatus"
            )

        if not isinstance(
            self.value_type,
            MetricValueType,
        ):
            raise HveeContractError(
                "observation evidence value type must "
                "be a MetricValueType"
            )

        if (
            self.status
            != ObservationStatus.SUCCESS
        ):
            if self.value is not None:
                raise HveeContractError(
                    "non-success observation evidence "
                    "cannot contain a value"
                )

            if (
                not isinstance(
                    self.status_detail,
                    str,
                )
                or not self.status_detail.strip()
            ):
                raise HveeContractError(
                    "non-success observation evidence "
                    "requires status detail"
                )

            return

        if (
            self.status_detail is not None
            and not isinstance(
                self.status_detail,
                str,
            )
        ):
            raise HveeContractError(
                "observation status detail must be "
                "a string or null"
            )

        if (
            self.value_type
            == MetricValueType.NUMBER
        ):
            if (
                isinstance(self.value, bool)
                or not isinstance(
                    self.value,
                    (int, float),
                )
                or not math.isfinite(
                    float(self.value)
                )
            ):
                raise HveeContractError(
                    "number observation evidence requires "
                    "a finite numeric value"
                )

        elif (
            self.value_type
            == MetricValueType.INTEGER
        ):
            if (
                isinstance(self.value, bool)
                or not isinstance(
                    self.value,
                    int,
                )
            ):
                raise HveeContractError(
                    "integer observation evidence requires "
                    "an integer value"
                )

        elif (
            self.value_type
            == MetricValueType.BOOLEAN
        ):
            if not isinstance(
                self.value,
                bool,
            ):
                raise HveeContractError(
                    "boolean observation evidence requires "
                    "a boolean value"
                )

        elif (
            self.value_type
            == MetricValueType.STRING
        ):
            if not isinstance(
                self.value,
                str,
            ):
                raise HveeContractError(
                    "string observation evidence requires "
                    "a string value"
                )

        elif (
            self.value_type
            == MetricValueType.JSON
        ):
            if self.value is None:
                raise HveeContractError(
                    "JSON observation evidence requires "
                    "a non-null value"
                )

            _canonicalize_json_value(
                self.value
            )


def _record_identity(
    record: ObservationEvidenceRecord,
) -> tuple[
    str,
    str,
    int,
    int,
    str,
    str,
    str,
    str,
]:
    return (
        record.evaluation_type,
        record.scope,
        record.evaluation_run_id,
        (
            -1
            if record.test_case_id is None
            else record.test_case_id
        ),
        record.metric_key,
        record.metric_version,
        record.evaluator_key,
        record.evaluator_version,
    )


def _canonical_value(
    record: ObservationEvidenceRecord,
) -> object | None:
    if (
        record.status
        != ObservationStatus.SUCCESS
    ):
        return None

    if (
        record.value_type
        == MetricValueType.NUMBER
    ):
        return float(record.value)

    if (
        record.value_type
        == MetricValueType.JSON
    ):
        return _canonicalize_json_value(
            record.value
        )

    return record.value


def _record_payload(
    record: ObservationEvidenceRecord,
) -> dict[str, object]:
    return {
        "metric": {
            "key": record.metric_key,
            "version": record.metric_version,
        },
        "evaluator": {
            "key": record.evaluator_key,
            "version": record.evaluator_version,
        },
        "evaluation_type": (
            record.evaluation_type
        ),
        "scope": record.scope,
        "target": {
            "evaluation_run_id": (
                record.evaluation_run_id
            ),
            "test_case_id": (
                record.test_case_id
            ),
        },
        "status": record.status.value,
        "value_type": (
            record.value_type.value
        ),
        "value": _canonical_value(
            record
        ),
        "status_detail": (
            record.status_detail
        ),
    }


def build_observation_evidence_bundle(
    records: list[
        ObservationEvidenceRecord
    ]
    | tuple[
        ObservationEvidenceRecord,
        ...,
    ],
) -> dict[str, object]:
    if not isinstance(
        records,
        (list, tuple),
    ):
        raise HveeContractError(
            "observation evidence records must be "
            "a list or tuple"
        )

    for record in records:
        if not isinstance(
            record,
            ObservationEvidenceRecord,
        ):
            raise HveeContractError(
                "observation evidence contains "
                "an invalid record"
            )

    ordered_records = sorted(
        records,
        key=_record_identity,
    )

    identities = [
        _record_identity(record)
        for record in ordered_records
    ]

    if len(identities) != len(
        set(identities)
    ):
        raise HveeContractError(
            "observation evidence contains "
            "duplicate identities"
        )

    observations = [
        _record_payload(record)
        for record in ordered_records
    ]

    body: dict[str, object] = {
        "schema_version": (
            OBSERVATION_EVIDENCE_SCHEMA_VERSION
        ),
        "count": len(observations),
        "observations": observations,
    }

    return {
        **body,
        "sha256": (
            calculate_observation_evidence_sha256(
                body
            )
        ),
    }


def _parse_record_payload(
    payload: object,
) -> ObservationEvidenceRecord:
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "metric",
            "evaluator",
            "evaluation_type",
            "scope",
            "target",
            "status",
            "value_type",
            "value",
            "status_detail",
        }
    ):
        raise HveeContractError(
            "invalid observation evidence record shape"
        )

    metric = payload.get("metric")
    evaluator = payload.get("evaluator")
    target = payload.get("target")

    if (
        not isinstance(metric, dict)
        or set(metric)
        != {"key", "version"}
    ):
        raise HveeContractError(
            "invalid observation metric identity"
        )

    if (
        not isinstance(evaluator, dict)
        or set(evaluator)
        != {"key", "version"}
    ):
        raise HveeContractError(
            "invalid observation evaluator identity"
        )

    if (
        not isinstance(target, dict)
        or set(target)
        != {
            "evaluation_run_id",
            "test_case_id",
        }
    ):
        raise HveeContractError(
            "invalid observation target identity"
        )

    try:
        status = ObservationStatus(
            payload.get("status")
        )
        value_type = MetricValueType(
            payload.get("value_type")
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "invalid observation evidence enum value"
        ) from exc

    return ObservationEvidenceRecord(
        metric_key=metric.get("key"),
        metric_version=metric.get(
            "version"
        ),
        evaluator_key=evaluator.get("key"),
        evaluator_version=evaluator.get(
            "version"
        ),
        evaluation_type=payload.get(
            "evaluation_type"
        ),
        scope=payload.get("scope"),
        evaluation_run_id=target.get(
            "evaluation_run_id"
        ),
        test_case_id=target.get(
            "test_case_id"
        ),
        status=status,
        value_type=value_type,
        value=payload.get("value"),
        status_detail=payload.get(
            "status_detail"
        ),
    )


def verify_observation_evidence_bundle(
    bundle: object,
) -> bool:
    try:
        if (
            not isinstance(bundle, dict)
            or set(bundle)
            != {
                "schema_version",
                "count",
                "observations",
                "sha256",
            }
        ):
            return False

        if (
            bundle.get("schema_version")
            != OBSERVATION_EVIDENCE_SCHEMA_VERSION
        ):
            return False

        count = bundle.get("count")
        observations = bundle.get(
            "observations"
        )
        sha256 = bundle.get("sha256")

        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or not isinstance(
                observations,
                list,
            )
            or count != len(observations)
            or not isinstance(sha256, str)
            or len(sha256) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in sha256
            )
        ):
            return False

        records = [
            _parse_record_payload(
                observation
            )
            for observation in observations
        ]

        rebuilt = (
            build_observation_evidence_bundle(
                records
            )
        )

        return bundle == rebuilt

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False
