"""Generic mechanics for semantic-evaluator development portfolios.

Evaluator-specific scientific cases, expectations, observations, and
comparison rules remain owned by their domain modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from hvee.core.contracts import HveeContractError


class SemanticPortfolioCaseLike(Protocol):
    """Minimum case contract required by the generic laboratory."""

    case_id: str


class SemanticPortfolioCaseResultLike(Protocol):
    """Minimum comparison-result contract required by the laboratory."""

    case_id: str
    passed: bool


CaseT = TypeVar(
    "CaseT",
    bound=SemanticPortfolioCaseLike,
)
CaseResultT = TypeVar(
    "CaseResultT",
    bound=SemanticPortfolioCaseResultLike,
)


class RunSemanticPortfolioCase(
    Protocol[CaseT, CaseResultT]
):
    def __call__(
        self,
        case: CaseT,
        /,
    ) -> CaseResultT:
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


def _case_id(case: object) -> str:
    value = getattr(
        case,
        "case_id",
        None,
    )

    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise HveeContractError(
            "semantic laboratory cases require "
            "non-empty case ids"
        )

    return value


def _result_identity(
    result: object,
) -> tuple[str, bool]:
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

    if (
        not isinstance(case_id, str)
        or not case_id
        or case_id != case_id.strip()
    ):
        raise HveeContractError(
            "semantic portfolio results require "
            "non-empty case ids"
        )

    if not isinstance(passed, bool):
        raise HveeContractError(
            "semantic portfolio result passed "
            "must be bool"
        )

    return case_id, passed


def validate_semantic_cases(
    cases: tuple[CaseT, ...],
) -> tuple[str, ...]:
    """Require a non-empty tuple with unique stable case identities."""

    if (
        not isinstance(cases, tuple)
        or not cases
    ):
        raise HveeContractError(
            "semantic laboratory requires "
            "a non-empty tuple of cases"
        )

    case_ids = tuple(
        _case_id(case)
        for case in cases
    )

    if len(case_ids) != len(set(case_ids)):
        raise HveeContractError(
            "semantic laboratory case ids "
            "must be unique"
        )

    return case_ids


@dataclass(frozen=True, slots=True)
class SemanticPortfolioReport(
    Generic[CaseResultT]
):
    """Generic report mechanics shared by semantic portfolios."""

    portfolio_key: str
    portfolio_version: str
    case_results: tuple[
        CaseResultT,
        ...,
    ]

    def __post_init__(self) -> None:
        _require_identity_part(
            name="semantic portfolio key",
            value=self.portfolio_key,
        )
        _require_identity_part(
            name="semantic portfolio version",
            value=self.portfolio_version,
        )

        if not isinstance(
            self.case_results,
            tuple,
        ):
            raise HveeContractError(
                "semantic portfolio case results "
                "must be a tuple"
            )

        identities = tuple(
            _result_identity(result)
            for result in self.case_results
        )

        case_ids = tuple(
            case_id
            for case_id, _ in identities
        )

        if len(case_ids) != len(
            set(case_ids)
        ):
            raise HveeContractError(
                "semantic portfolio result case ids "
                "must be unique"
            )

    @property
    def total_cases(self) -> int:
        return len(self.case_results)

    @property
    def passed_cases(self) -> int:
        return sum(
            bool(
                getattr(
                    result,
                    "passed",
                )
            )
            for result in self.case_results
        )

    @property
    def failed_cases(self) -> int:
        return (
            self.total_cases
            - self.passed_cases
        )

    @property
    def passed(self) -> bool:
        return (
            self.total_cases > 0
            and self.failed_cases == 0
        )


def run_semantic_portfolio(
    *,
    portfolio_key: str,
    portfolio_version: str,
    cases: tuple[CaseT, ...],
    run_case: RunSemanticPortfolioCase[
        CaseT,
        CaseResultT,
    ],
) -> SemanticPortfolioReport[CaseResultT]:
    """
    Execute evaluator-specific cases using generic portfolio mechanics.

    The laboratory does not know how a semantic evaluator works. The caller
    owns scientific evaluation and comparison through ``run_case``.
    """

    _require_identity_part(
        name="semantic portfolio key",
        value=portfolio_key,
    )
    _require_identity_part(
        name="semantic portfolio version",
        value=portfolio_version,
    )

    case_ids = validate_semantic_cases(
        cases
    )

    if not callable(run_case):
        raise HveeContractError(
            "semantic portfolio run_case "
            "must be callable"
        )

    results: list[CaseResultT] = []

    for expected_case_id, case in zip(
        case_ids,
        cases,
        strict=True,
    ):
        result = run_case(case)

        result_case_id, _ = (
            _result_identity(result)
        )

        if result_case_id != expected_case_id:
            raise HveeContractError(
                "semantic portfolio result case id "
                "does not match its input case"
            )

        results.append(result)

    return SemanticPortfolioReport(
        portfolio_key=portfolio_key,
        portfolio_version=portfolio_version,
        case_results=tuple(results),
    )
