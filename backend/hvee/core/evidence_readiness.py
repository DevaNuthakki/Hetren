from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.decision import (
    EvidenceAssessment,
    IntegrityAssessment,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)


_UNAVAILABLE_STATUSES = frozenset(
    {
        ObservationStatus.ABSTAINED,
        ObservationStatus.UNSUPPORTED,
        ObservationStatus.TIMED_OUT,
        ObservationStatus.FAILED,
        ObservationStatus.CANCELLED,
    }
)


def _require_identity_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
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


@dataclass(frozen=True, slots=True)
class EvidenceTarget:
    """
    Resource target for one evidence-readiness decision.

    A test-case target carries both run and test-case identity.
    Run-scoped requirements use the run identity and require the
    observation itself to have no test-case target.
    """

    evaluation_run_id: int
    test_case_id: int | None = None

    def __post_init__(self) -> None:
        _require_positive_integer(
            name="evaluation run id",
            value=self.evaluation_run_id,
        )

        if self.test_case_id is not None:
            _require_positive_integer(
                name="test case id",
                value=self.test_case_id,
            )


@dataclass(frozen=True, slots=True)
class ObservationRequirement:
    """
    One versioned observation contract required by a decision.

    Scientific identity is metric/evaluator/evaluation-type/scope.
    value_type is a contract expectation rather than part of that
    identity, and is verified separately before evidence is usable.
    """

    metric_key: str
    metric_version: str
    evaluator_key: str
    evaluator_version: str
    evaluation_type: str
    scope: str
    value_type: MetricValueType

    def __post_init__(self) -> None:
        _require_identity_string(
            name="metric key",
            value=self.metric_key,
        )
        _require_identity_string(
            name="metric version",
            value=self.metric_version,
        )
        _require_identity_string(
            name="evaluator key",
            value=self.evaluator_key,
        )
        _require_identity_string(
            name="evaluator version",
            value=self.evaluator_version,
        )
        _require_identity_string(
            name="evaluation type",
            value=self.evaluation_type,
        )

        if self.scope not in {
            "run",
            "test_case",
        }:
            raise HveeContractError(
                "observation requirement scope must be "
                "'run' or 'test_case'"
            )

        if not isinstance(
            self.value_type,
            MetricValueType,
        ):
            raise HveeContractError(
                "observation requirement value type "
                "must be a MetricValueType"
            )

    @property
    def identity(
        self,
    ) -> tuple[
        str,
        str,
        str,
        str,
        str,
        str,
    ]:
        return (
            self.evaluation_type,
            self.scope,
            self.metric_key,
            self.metric_version,
            self.evaluator_key,
            self.evaluator_version,
        )


@dataclass(frozen=True, slots=True)
class UnavailableEvidence:
    requirement: ObservationRequirement
    status: ObservationStatus
    status_detail: str

    def __post_init__(self) -> None:
        if self.status not in _UNAVAILABLE_STATUSES:
            raise HveeContractError(
                "unavailable evidence must use an "
                "unavailable observation status"
            )

        if (
            not isinstance(
                self.status_detail,
                str,
            )
            or not self.status_detail.strip()
        ):
            raise HveeContractError(
                "unavailable evidence requires status detail"
            )


@dataclass(frozen=True, slots=True)
class InvalidEvidence:
    requirement: ObservationRequirement
    status_detail: str

    def __post_init__(self) -> None:
        if (
            not isinstance(
                self.status_detail,
                str,
            )
            or not self.status_detail.strip()
        ):
            raise HveeContractError(
                "invalid evidence requires status detail"
            )


@dataclass(frozen=True, slots=True)
class EvidenceReadinessResult:
    integrity: IntegrityAssessment
    evidence: EvidenceAssessment
    required_count: int
    usable_count: int
    missing: tuple[
        ObservationRequirement,
        ...,
    ]
    unavailable: tuple[
        UnavailableEvidence,
        ...,
    ]
    invalid: tuple[
        InvalidEvidence,
        ...,
    ]
    duplicates: tuple[
        ObservationRequirement,
        ...,
    ]

    def __post_init__(self) -> None:
        if not isinstance(
            self.integrity,
            IntegrityAssessment,
        ):
            raise HveeContractError(
                "readiness integrity must be "
                "an IntegrityAssessment"
            )

        if not isinstance(
            self.evidence,
            EvidenceAssessment,
        ):
            raise HveeContractError(
                "readiness evidence must be "
                "an EvidenceAssessment"
            )

        for name, value in (
            (
                "required count",
                self.required_count,
            ),
            (
                "usable count",
                self.usable_count,
            ),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise HveeContractError(
                    f"{name} must be a "
                    "non-negative integer"
                )

        if self.usable_count > self.required_count:
            raise HveeContractError(
                "usable count cannot exceed required count"
            )


def _record_identity(
    record: ObservationEvidenceRecord,
) -> tuple[
    str,
    str,
    str,
    str,
    str,
    str,
]:
    return (
        record.evaluation_type,
        record.scope,
        record.metric_key,
        record.metric_version,
        record.evaluator_key,
        record.evaluator_version,
    )


def _record_matches_target(
    *,
    record: ObservationEvidenceRecord,
    requirement: ObservationRequirement,
    target: EvidenceTarget,
) -> bool:
    if (
        record.evaluation_run_id
        != target.evaluation_run_id
    ):
        return False

    if requirement.scope == "run":
        return record.test_case_id is None

    return (
        target.test_case_id is not None
        and record.test_case_id
        == target.test_case_id
    )


def assess_evidence_readiness(
    *,
    records: list[
        ObservationEvidenceRecord
    ]
    | tuple[
        ObservationEvidenceRecord,
        ...,
    ],
    requirements: list[
        ObservationRequirement
    ]
    | tuple[
        ObservationRequirement,
        ...,
    ],
    target: EvidenceTarget,
) -> EvidenceReadinessResult:
    """
    Assess whether required observations are usable for one target.

    Additional observations, including observations for other targets,
    are allowed and do not affect this decision.

    Missing/non-success evidence is insufficient. INVALID evidence,
    duplicate matching observations, or a value-type contract mismatch
    invalidates evidence integrity.
    """

    if not isinstance(
        records,
        (list, tuple),
    ):
        raise HveeContractError(
            "evidence records must be a list or tuple"
        )

    if not isinstance(
        requirements,
        (list, tuple),
    ):
        raise HveeContractError(
            "evidence requirements must be a list or tuple"
        )

    if not isinstance(
        target,
        EvidenceTarget,
    ):
        raise HveeContractError(
            "evidence target must be EvidenceTarget"
        )

    if not requirements:
        raise HveeContractError(
            "at least one evidence requirement is required"
        )

    for record in records:
        if not isinstance(
            record,
            ObservationEvidenceRecord,
        ):
            raise HveeContractError(
                "evidence contains an invalid record"
            )

    for requirement in requirements:
        if not isinstance(
            requirement,
            ObservationRequirement,
        ):
            raise HveeContractError(
                "evidence requirements contain "
                "an invalid requirement"
            )

        if (
            requirement.scope == "test_case"
            and target.test_case_id is None
        ):
            raise HveeContractError(
                "test-case evidence requirements "
                "require a test-case target"
            )

    requirement_identities = [
        requirement.identity
        for requirement in requirements
    ]

    if len(requirement_identities) != len(
        set(requirement_identities)
    ):
        raise HveeContractError(
            "evidence requirements contain "
            "duplicate scientific identities"
        )

    ordered_requirements = sorted(
        requirements,
        key=lambda requirement: (
            requirement.identity
        ),
    )

    missing: list[
        ObservationRequirement
    ] = []
    unavailable: list[
        UnavailableEvidence
    ] = []
    invalid: list[
        InvalidEvidence
    ] = []
    duplicates: list[
        ObservationRequirement
    ] = []

    usable_count = 0

    for requirement in ordered_requirements:
        matches = [
            record
            for record in records
            if (
                _record_identity(record)
                == requirement.identity
                and _record_matches_target(
                    record=record,
                    requirement=requirement,
                    target=target,
                )
            )
        ]

        if not matches:
            missing.append(
                requirement
            )
            continue

        if len(matches) != 1:
            duplicates.append(
                requirement
            )
            continue

        record = matches[0]

        if (
            record.value_type
            != requirement.value_type
        ):
            invalid.append(
                InvalidEvidence(
                    requirement=requirement,
                    status_detail=(
                        "observation value type does not "
                        "match the required metric contract"
                    ),
                )
            )
            continue

        if (
            record.status
            == ObservationStatus.SUCCESS
        ):
            usable_count += 1
            continue

        if (
            record.status
            == ObservationStatus.INVALID
        ):
            invalid.append(
                InvalidEvidence(
                    requirement=requirement,
                    status_detail=(
                        record.status_detail
                        or ""
                    ),
                )
            )
            continue

        if record.status in _UNAVAILABLE_STATUSES:
            unavailable.append(
                UnavailableEvidence(
                    requirement=requirement,
                    status=record.status,
                    status_detail=(
                        record.status_detail
                        or ""
                    ),
                )
            )
            continue

        raise HveeContractError(
            "unsupported observation status "
            "in evidence readiness"
        )

    integrity = (
        IntegrityAssessment.INVALID
        if invalid or duplicates
        else IntegrityAssessment.VALID
    )

    evidence = (
        EvidenceAssessment.SUFFICIENT
        if (
            usable_count
            == len(ordered_requirements)
            and not missing
            and not unavailable
            and not invalid
            and not duplicates
        )
        else EvidenceAssessment.INSUFFICIENT
    )

    return EvidenceReadinessResult(
        integrity=integrity,
        evidence=evidence,
        required_count=len(
            ordered_requirements
        ),
        usable_count=usable_count,
        missing=tuple(missing),
        unavailable=tuple(unavailable),
        invalid=tuple(invalid),
        duplicates=tuple(duplicates),
    )
