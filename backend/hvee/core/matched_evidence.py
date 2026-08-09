from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.evidence_readiness import (
    EvidenceTarget,
    ObservationRequirement,
    assess_evidence_readiness,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)


class MatchedEvidenceState(StrEnum):
    USABLE = "usable"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class MatchedEvidenceSide:
    evaluation_run_id: int
    test_case_id: int
    state: MatchedEvidenceState
    value: float | None = None
    observation_status: ObservationStatus | None = None
    status_detail: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            (
                "evaluation run id",
                self.evaluation_run_id,
            ),
            (
                "test case id",
                self.test_case_id,
            ),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
            ):
                raise HveeContractError(
                    f"{name} must be a positive integer"
                )

        if not isinstance(
            self.state,
            MatchedEvidenceState,
        ):
            raise HveeContractError(
                "matched evidence state must be "
                "MatchedEvidenceState"
            )

        if self.state == MatchedEvidenceState.USABLE:
            if (
                isinstance(self.value, bool)
                or not isinstance(
                    self.value,
                    (int, float),
                )
            ):
                raise HveeContractError(
                    "usable matched evidence requires "
                    "a numeric value"
                )

            if self.observation_status != (
                ObservationStatus.SUCCESS
            ):
                raise HveeContractError(
                    "usable matched evidence requires "
                    "SUCCESS observation status"
                )

            if self.status_detail is not None:
                raise HveeContractError(
                    "usable matched evidence cannot "
                    "contain status detail"
                )
            return

        if self.value is not None:
            raise HveeContractError(
                "non-usable matched evidence cannot "
                "contain a numeric value"
            )

        if (
            self.state
            == MatchedEvidenceState.UNAVAILABLE
        ):
            if self.observation_status not in {
                ObservationStatus.ABSTAINED,
                ObservationStatus.UNSUPPORTED,
                ObservationStatus.TIMED_OUT,
                ObservationStatus.FAILED,
                ObservationStatus.CANCELLED,
            }:
                raise HveeContractError(
                    "unavailable matched evidence "
                    "requires an unavailable status"
                )

            if (
                not isinstance(
                    self.status_detail,
                    str,
                )
                or not self.status_detail.strip()
            ):
                raise HveeContractError(
                    "unavailable matched evidence "
                    "requires status detail"
                )
        elif (
            self.state
            == MatchedEvidenceState.INVALID
        ):
            if not isinstance(
                self.observation_status,
                ObservationStatus,
            ):
                raise HveeContractError(
                    "invalid matched evidence requires "
                    "the underlying observation status"
                )

            if (
                not isinstance(
                    self.status_detail,
                    str,
                )
                or not self.status_detail.strip()
            ):
                raise HveeContractError(
                    "invalid matched evidence "
                    "requires status detail"
                )
        elif self.state in {
            MatchedEvidenceState.MISSING,
            MatchedEvidenceState.DUPLICATE,
        }:
            if self.observation_status is not None:
                raise HveeContractError(
                    "missing/duplicate matched evidence "
                    "cannot carry observation status"
                )


@dataclass(frozen=True, slots=True)
class MatchedObservationPair:
    test_case_id: int
    baseline: MatchedEvidenceSide
    candidate: MatchedEvidenceSide

    def __post_init__(self) -> None:
        if (
            isinstance(self.test_case_id, bool)
            or not isinstance(
                self.test_case_id,
                int,
            )
            or self.test_case_id < 1
        ):
            raise HveeContractError(
                "matched pair test case id must "
                "be a positive integer"
            )

        if (
            self.baseline.test_case_id
            != self.test_case_id
            or self.candidate.test_case_id
            != self.test_case_id
        ):
            raise HveeContractError(
                "matched pair sides must target "
                "the same test case"
            )

        if (
            self.baseline.evaluation_run_id
            == self.candidate.evaluation_run_id
        ):
            raise HveeContractError(
                "matched pair requires different "
                "baseline and candidate runs"
            )

    @property
    def usable(self) -> bool:
        return (
            self.baseline.state
            == MatchedEvidenceState.USABLE
            and self.candidate.state
            == MatchedEvidenceState.USABLE
        )

    @property
    def delta(self) -> float | None:
        if not self.usable:
            return None

        assert self.baseline.value is not None
        assert self.candidate.value is not None

        return (
            self.candidate.value
            - self.baseline.value
        )


@dataclass(frozen=True, slots=True)
class MatchedObservationCohort:
    baseline_run_id: int
    candidate_run_id: int
    requirement: ObservationRequirement
    declared_test_case_ids: tuple[int, ...]
    pairs: tuple[MatchedObservationPair, ...]

    def __post_init__(self) -> None:
        if (
            self.baseline_run_id
            == self.candidate_run_id
        ):
            raise HveeContractError(
                "matched cohort requires different "
                "baseline and candidate runs"
            )

        if (
            self.requirement.scope
            != "test_case"
        ):
            raise HveeContractError(
                "matched cohort requires a "
                "test-case observation requirement"
            )

        if self.requirement.value_type not in {
            MetricValueType.NUMBER,
            MetricValueType.INTEGER,
        }:
            raise HveeContractError(
                "matched cohort v1 requires a "
                "numeric observation requirement"
            )

        if not self.declared_test_case_ids:
            raise HveeContractError(
                "matched cohort requires at least "
                "one declared test case"
            )

        if (
            tuple(
                sorted(
                    self.declared_test_case_ids
                )
            )
            != self.declared_test_case_ids
        ):
            raise HveeContractError(
                "declared test case ids must be "
                "stored in sorted order"
            )

        if len(
            self.declared_test_case_ids
        ) != len(
            set(
                self.declared_test_case_ids
            )
        ):
            raise HveeContractError(
                "declared test case ids must be unique"
            )

        if tuple(
            pair.test_case_id
            for pair
            in self.pairs
        ) != self.declared_test_case_ids:
            raise HveeContractError(
                "matched pairs must exactly cover "
                "the declared cohort"
            )

    @property
    def total_cases(self) -> int:
        return len(self.pairs)

    @property
    def usable_pairs(self) -> int:
        return sum(
            pair.usable
            for pair
            in self.pairs
        )

    @property
    def incomplete_pairs(self) -> int:
        return (
            self.total_cases
            - self.usable_pairs
        )

    @property
    def complete(self) -> bool:
        return (
            self.total_cases > 0
            and self.incomplete_pairs == 0
        )

    @property
    def integrity_valid(self) -> bool:
        return not any(
            side.state
            in {
                MatchedEvidenceState.INVALID,
                MatchedEvidenceState.DUPLICATE,
            }
            for pair
            in self.pairs
            for side
            in (
                pair.baseline,
                pair.candidate,
            )
        )

    @property
    def deltas(self) -> tuple[float, ...]:
        return tuple(
            delta
            for pair
            in self.pairs
            if (
                delta := pair.delta
            )
            is not None
        )


def _matches_requirement_target(
    *,
    record: ObservationEvidenceRecord,
    requirement: ObservationRequirement,
    run_id: int,
    test_case_id: int,
) -> bool:
    return (
        record.evaluation_type
        == requirement.evaluation_type
        and record.scope
        == requirement.scope
        and record.metric_key
        == requirement.metric_key
        and record.metric_version
        == requirement.metric_version
        and record.evaluator_key
        == requirement.evaluator_key
        and record.evaluator_version
        == requirement.evaluator_version
        and record.evaluation_run_id
        == run_id
        and record.test_case_id
        == test_case_id
    )


def _build_side(
    *,
    records: tuple[
        ObservationEvidenceRecord,
        ...,
    ],
    requirement: ObservationRequirement,
    run_id: int,
    test_case_id: int,
) -> MatchedEvidenceSide:
    target = EvidenceTarget(
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
    )

    readiness = assess_evidence_readiness(
        records=records,
        requirements=(requirement,),
        target=target,
    )

    matches = tuple(
        record
        for record
        in records
        if _matches_requirement_target(
            record=record,
            requirement=requirement,
            run_id=run_id,
            test_case_id=test_case_id,
        )
    )

    if readiness.duplicates:
        return MatchedEvidenceSide(
            evaluation_run_id=run_id,
            test_case_id=test_case_id,
            state=MatchedEvidenceState.DUPLICATE,
        )

    if readiness.invalid:
        record = (
            matches[0]
            if len(matches) == 1
            else None
        )

        return MatchedEvidenceSide(
            evaluation_run_id=run_id,
            test_case_id=test_case_id,
            state=MatchedEvidenceState.INVALID,
            observation_status=(
                None
                if record is None
                else record.status
            ),
            status_detail=(
                "invalid observation evidence"
                if record is None
                else (
                    record.status_detail
                    or "invalid observation evidence"
                )
            ),
        )

    if readiness.missing:
        return MatchedEvidenceSide(
            evaluation_run_id=run_id,
            test_case_id=test_case_id,
            state=MatchedEvidenceState.MISSING,
        )

    if readiness.unavailable:
        unavailable = readiness.unavailable[0]

        return MatchedEvidenceSide(
            evaluation_run_id=run_id,
            test_case_id=test_case_id,
            state=MatchedEvidenceState.UNAVAILABLE,
            observation_status=unavailable.status,
            status_detail=(
                unavailable.status_detail
            ),
        )

    if len(matches) != 1:
        raise HveeContractError(
            "usable matched evidence must resolve "
            "to exactly one observation"
        )

    record = matches[0]

    if (
        record.status
        != ObservationStatus.SUCCESS
    ):
        raise HveeContractError(
            "usable matched evidence requires "
            "successful observation"
        )

    return MatchedEvidenceSide(
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
        state=MatchedEvidenceState.USABLE,
        value=float(record.value),
        observation_status=record.status,
    )


def build_matched_observation_cohort(
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    declared_test_case_ids: tuple[int, ...],
    requirement: ObservationRequirement,
    records: tuple[
        ObservationEvidenceRecord,
        ...,
    ],
) -> MatchedObservationCohort:
    """
    Build exact candidate-vs-baseline matched evidence accounting.

    The caller must explicitly declare the intended test-case cohort.
    Every declared test case is represented in the output, including
    missing, unavailable, invalid, and duplicate evidence.

    This function performs no statistical inference and makes no
    release decision.
    """

    for name, value in (
        ("baseline run id", baseline_run_id),
        ("candidate run id", candidate_run_id),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 1
        ):
            raise HveeContractError(
                f"{name} must be a positive integer"
            )

    if baseline_run_id == candidate_run_id:
        raise HveeContractError(
            "baseline and candidate runs must differ"
        )

    if not isinstance(
        requirement,
        ObservationRequirement,
    ):
        raise HveeContractError(
            "matched cohort requires "
            "ObservationRequirement"
        )

    if requirement.scope != "test_case":
        raise HveeContractError(
            "matched cohort requires a "
            "test-case observation requirement"
        )

    if requirement.value_type not in {
        MetricValueType.NUMBER,
        MetricValueType.INTEGER,
    }:
        raise HveeContractError(
            "matched cohort v1 requires a "
            "numeric observation requirement"
        )

    if (
        not isinstance(
            declared_test_case_ids,
            tuple,
        )
        or not declared_test_case_ids
    ):
        raise HveeContractError(
            "declared test case ids must be "
            "a non-empty tuple"
        )

    for test_case_id in declared_test_case_ids:
        if (
            isinstance(test_case_id, bool)
            or not isinstance(
                test_case_id,
                int,
            )
            or test_case_id < 1
        ):
            raise HveeContractError(
                "declared test case ids must "
                "be positive integers"
            )

    if len(
        declared_test_case_ids
    ) != len(
        set(
            declared_test_case_ids
        )
    ):
        raise HveeContractError(
            "declared test case ids must be unique"
        )

    if (
        not isinstance(records, tuple)
        or not all(
            isinstance(
                record,
                ObservationEvidenceRecord,
            )
            for record
            in records
        )
    ):
        raise HveeContractError(
            "matched cohort records must be "
            "a tuple of ObservationEvidenceRecord"
        )

    ordered_test_case_ids = tuple(
        sorted(
            declared_test_case_ids
        )
    )

    pairs = tuple(
        MatchedObservationPair(
            test_case_id=test_case_id,
            baseline=_build_side(
                records=records,
                requirement=requirement,
                run_id=baseline_run_id,
                test_case_id=test_case_id,
            ),
            candidate=_build_side(
                records=records,
                requirement=requirement,
                run_id=candidate_run_id,
                test_case_id=test_case_id,
            ),
        )
        for test_case_id
        in ordered_test_case_ids
    )

    return MatchedObservationCohort(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        requirement=requirement,
        declared_test_case_ids=(
            ordered_test_case_ids
        ),
        pairs=pairs,
    )
