"""Generic controlled-mutation mechanics for semantic evaluator laboratories.

The laboratory coordinates the experiment. Domain modules continue to own
their evaluator, comparison semantics, and the actual synthetic defects.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, replace
from typing import Generic, Protocol, TypeVar

from hvee.core.contracts import (
    HveeContractError,
    Observation,
    ObservationStatus,
)
from hvee.laboratory.semantic.portfolio import (
    SemanticPortfolioCaseLike,
    SemanticPortfolioCaseResultLike,
    validate_semantic_cases,
)


CaseT = TypeVar(
    "CaseT",
    bound=SemanticPortfolioCaseLike,
)
CaseResultT = TypeVar(
    "CaseResultT",
    bound=SemanticPortfolioCaseResultLike,
)
MutationT = TypeVar(
    "MutationT",
    bound=Hashable,
)


class EvaluateSemanticCase(
    Protocol[CaseT]
):
    def __call__(
        self,
        case: CaseT,
        /,
    ) -> tuple[Observation, ...]:
        ...


class CompareSemanticCase(
    Protocol[CaseT, CaseResultT]
):
    def __call__(
        self,
        *,
        case: CaseT,
        observations: tuple[
            Observation,
            ...,
        ],
    ) -> CaseResultT:
        ...


class ApplySemanticMutation(
    Protocol[MutationT]
):
    def __call__(
        self,
        *,
        mutation: MutationT,
        observations: tuple[
            Observation,
            ...,
        ],
    ) -> tuple[Observation, ...]:
        ...


def _require_identity_part(
    *,
    name: str,
    value: str,
) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise HveeContractError(
            f"{name} must be a non-empty string "
            "without surrounding whitespace"
        )


def _validate_observations(
    observations: tuple[
        Observation,
        ...,
    ],
) -> None:
    if (
        not isinstance(observations, tuple)
        or not all(
            isinstance(
                observation,
                Observation,
            )
            for observation in observations
        )
    ):
        raise HveeContractError(
            "semantic mutation laboratory requires "
            "a tuple of Observation values"
        )


def _observation_contract_signature(
    observations: tuple[
        Observation,
        ...,
    ],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
            observation.evaluation_type,
            observation.status,
            observation.value_type,
            observation.status_detail,
        )
        for observation in observations
    )


def _validate_case_result(
    *,
    expected_case_id: str,
    result: object,
) -> bool:
    case_id = getattr(
        result,
        "case_id",
        None,
    )
    passed = getattr(
        result,
        "passed",
        None,
    )

    if case_id != expected_case_id:
        raise HveeContractError(
            "semantic mutation comparison result "
            "case id does not match its input case"
        )

    if not isinstance(passed, bool):
        raise HveeContractError(
            "semantic mutation comparison result "
            "passed must be bool"
        )

    return passed


@dataclass(frozen=True, slots=True)
class SemanticMutationResult(
    Generic[MutationT]
):
    mutation: MutationT
    changed_case_ids: tuple[str, ...]
    detected_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.mutation,
            Hashable,
        ):
            raise HveeContractError(
                "semantic mutation identity "
                "must be hashable"
            )

        for name, values in (
            (
                "changed case ids",
                self.changed_case_ids,
            ),
            (
                "detected case ids",
                self.detected_case_ids,
            ),
        ):
            if (
                not isinstance(values, tuple)
                or not all(
                    isinstance(value, str)
                    and bool(value)
                    and value == value.strip()
                    for value in values
                )
            ):
                raise HveeContractError(
                    f"semantic mutation {name} "
                    "must be a tuple of non-empty strings"
                )

            if len(values) != len(
                set(values)
            ):
                raise HveeContractError(
                    f"semantic mutation {name} "
                    "must be unique"
                )

        if not set(
            self.detected_case_ids
        ) <= set(
            self.changed_case_ids
        ):
            raise HveeContractError(
                "semantic mutation detected cases "
                "must be changed cases"
            )

    @property
    def changed_cases(self) -> int:
        return len(self.changed_case_ids)

    @property
    def detected_cases(self) -> int:
        return len(self.detected_case_ids)

    @property
    def killed(self) -> bool:
        return bool(
            self.detected_case_ids
        )


@dataclass(frozen=True, slots=True)
class SemanticMutationReport(
    Generic[MutationT]
):
    portfolio_key: str
    portfolio_version: str
    suite_key: str
    suite_version: str
    results: tuple[
        SemanticMutationResult[MutationT],
        ...,
    ]

    def __post_init__(self) -> None:
        for name, value in (
            (
                "semantic mutation portfolio key",
                self.portfolio_key,
            ),
            (
                "semantic mutation portfolio version",
                self.portfolio_version,
            ),
            (
                "semantic mutation suite key",
                self.suite_key,
            ),
            (
                "semantic mutation suite version",
                self.suite_version,
            ),
        ):
            _require_identity_part(
                name=name,
                value=value,
            )

        if (
            not isinstance(self.results, tuple)
            or not all(
                isinstance(
                    result,
                    SemanticMutationResult,
                )
                for result in self.results
            )
        ):
            raise HveeContractError(
                "semantic mutation report results "
                "must be SemanticMutationResult values"
            )

        mutations = tuple(
            result.mutation
            for result in self.results
        )

        if len(mutations) != len(
            set(mutations)
        ):
            raise HveeContractError(
                "semantic mutation report mutations "
                "must be unique"
            )

    @property
    def total_mutants(self) -> int:
        return len(self.results)

    @property
    def killed_mutants(self) -> int:
        return sum(
            result.killed
            for result in self.results
        )

    @property
    def survived_mutants(self) -> int:
        return (
            self.total_mutants
            - self.killed_mutants
        )

    @property
    def mutation_score(self) -> float:
        if not self.results:
            return 0.0

        return (
            self.killed_mutants
            / self.total_mutants
        )


def replace_success_observation_value(
    observations: tuple[
        Observation,
        ...,
    ],
    *,
    metric_key: str,
    current_value: object,
    new_value: object,
) -> tuple[Observation, ...]:
    """
    Replace matching successful metric values without changing identity.

    A no-op is valid here. The higher-level mutation runner requires that a
    defined mutation changes at least one case across its portfolio.
    """

    _validate_observations(
        observations
    )

    if (
        not isinstance(metric_key, str)
        or not metric_key
        or metric_key != metric_key.strip()
    ):
        raise HveeContractError(
            "semantic mutation metric key "
            "must be non-empty"
        )

    return tuple(
        (
            replace(
                observation,
                value=new_value,
            )
            if (
                observation.metric_key
                == metric_key
                and observation.status
                == ObservationStatus.SUCCESS
                and observation.value
                == current_value
            )
            else observation
        )
        for observation in observations
    )


def run_semantic_evaluator_mutation(
    *,
    cases: tuple[CaseT, ...],
    mutation: MutationT,
    evaluate_case: EvaluateSemanticCase[
        CaseT
    ],
    compare_case: CompareSemanticCase[
        CaseT,
        CaseResultT,
    ],
    apply_mutation: ApplySemanticMutation[
        MutationT
    ],
) -> SemanticMutationResult[MutationT]:
    """
    Run one controlled evaluator defect against a passing portfolio.

    Scientific observation identity, status, value type, ordering, and status
    detail must remain unchanged. Controlled mutations may change values only.
    """

    case_ids = validate_semantic_cases(
        cases
    )

    if not isinstance(
        mutation,
        Hashable,
    ):
        raise HveeContractError(
            "semantic mutation identity "
            "must be hashable"
        )

    if not all(
        callable(callback)
        for callback in (
            evaluate_case,
            compare_case,
            apply_mutation,
        )
    ):
        raise HveeContractError(
            "semantic mutation laboratory callbacks "
            "must be callable"
        )

    changed: list[str] = []
    detected: list[str] = []

    for case_id, case in zip(
        case_ids,
        cases,
        strict=True,
    ):
        observations = evaluate_case(case)
        _validate_observations(
            observations
        )

        baseline = compare_case(
            case=case,
            observations=observations,
        )

        baseline_passed = (
            _validate_case_result(
                expected_case_id=case_id,
                result=baseline,
            )
        )

        if not baseline_passed:
            raise HveeContractError(
                "semantic mutation testing requires "
                "a passing baseline"
            )

        mutated = apply_mutation(
            mutation=mutation,
            observations=observations,
        )
        _validate_observations(
            mutated
        )

        if (
            _observation_contract_signature(
                mutated
            )
            != _observation_contract_signature(
                observations
            )
        ):
            raise HveeContractError(
                "semantic mutation changed observation "
                "identity, status, type, ordering, "
                "or status detail"
            )

        if mutated != observations:
            changed.append(case_id)

        result = compare_case(
            case=case,
            observations=mutated,
        )

        passed = _validate_case_result(
            expected_case_id=case_id,
            result=result,
        )

        if not passed:
            if mutated == observations:
                raise HveeContractError(
                    "semantic mutation comparison changed "
                    "without an observation mutation"
                )

            detected.append(case_id)

    if not changed:
        raise HveeContractError(
            "semantic evaluator mutation "
            "had no portfolio effect"
        )

    return SemanticMutationResult(
        mutation=mutation,
        changed_case_ids=tuple(changed),
        detected_case_ids=tuple(detected),
    )


def run_semantic_evaluator_mutation_suite(
    *,
    portfolio_key: str,
    portfolio_version: str,
    suite_key: str,
    suite_version: str,
    cases: tuple[CaseT, ...],
    mutations: tuple[
        MutationT,
        ...,
    ],
    evaluate_case: EvaluateSemanticCase[
        CaseT
    ],
    compare_case: CompareSemanticCase[
        CaseT,
        CaseResultT,
    ],
    apply_mutation: ApplySemanticMutation[
        MutationT
    ],
) -> SemanticMutationReport[MutationT]:
    """Run an explicitly defined controlled mutation set."""

    for name, value in (
        (
            "semantic mutation portfolio key",
            portfolio_key,
        ),
        (
            "semantic mutation portfolio version",
            portfolio_version,
        ),
        (
            "semantic mutation suite key",
            suite_key,
        ),
        (
            "semantic mutation suite version",
            suite_version,
        ),
    ):
        _require_identity_part(
            name=name,
            value=value,
        )

    validate_semantic_cases(
        cases
    )

    if (
        not isinstance(mutations, tuple)
        or not mutations
        or not all(
            isinstance(
                mutation,
                Hashable,
            )
            for mutation in mutations
        )
    ):
        raise HveeContractError(
            "semantic mutation suite requires "
            "a non-empty tuple of hashable mutations"
        )

    if len(mutations) != len(
        set(mutations)
    ):
        raise HveeContractError(
            "semantic mutation suite mutations "
            "must be unique"
        )

    return SemanticMutationReport(
        portfolio_key=portfolio_key,
        portfolio_version=portfolio_version,
        suite_key=suite_key,
        suite_version=suite_version,
        results=tuple(
            run_semantic_evaluator_mutation(
                cases=cases,
                mutation=mutation,
                evaluate_case=evaluate_case,
                compare_case=compare_case,
                apply_mutation=apply_mutation,
            )
            for mutation in mutations
        ),
    )
