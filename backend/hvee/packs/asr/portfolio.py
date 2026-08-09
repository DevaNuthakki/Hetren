from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    EvaluatorVersion,
    HveeContractError,
    MetricDefinition,
    MetricValueType,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
    NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
)
from hvee.packs.asr.numeric_preservation import (
    GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
    MISSING_NUMERIC_TOKEN_COUNT_METRIC,
    NUMERIC_TOKEN_PRESERVATION_EVALUATOR,
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
    UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
)
from hvee.packs.asr.transcript_integrity import (
    EXACT_NORMALIZED_MATCH_METRIC,
    GENERATED_EMPTY_METRIC,
    MISSING_OUTPUT_METRIC,
    REFERENCE_EMPTY_METRIC,
    TRANSCRIPT_INTEGRITY_EVALUATOR,
    UNEXPECTED_OUTPUT_METRIC,
)


ASR_EVALUATION_PORTFOLIO_KEY = (
    "hetren.asr.evaluation-portfolio"
)
ASR_EVALUATION_PORTFOLIO_VERSION = "1.0.0"


class ASRPortfolioMutation(StrEnum):
    """
    Controlled transcript transformations used by Portfolio v1.

    NONE and NORMALIZATION_EQUIVALENT are controls. The remaining
    values deliberately introduce known transcript-level failures.

    These mutations make no claims about the acoustic cause of a
    transcript difference.
    """

    NONE = "none"
    NORMALIZATION_EQUIVALENT = (
        "normalization_equivalent"
    )

    WORD_SUBSTITUTION = "word_substitution"
    WORD_DELETION = "word_deletion"
    WORD_INSERTION = "word_insertion"

    MISSING_OUTPUT = "missing_output"
    UNEXPECTED_OUTPUT = "unexpected_output"

    NUMERIC_SUBSTITUTION = "numeric_substitution"
    NUMERIC_DELETION = "numeric_deletion"
    NUMERIC_INSERTION = "numeric_insertion"
    NUMERIC_REORDER = "numeric_reorder"


@dataclass(frozen=True, slots=True)
class ASRPortfolioExpectedObservation:
    """
    Ground-truth expectation for one versioned evaluator signal.

    The expectation is deliberately pinned to exact metric and
    evaluator versions so evaluator changes can be benchmarked rather
    than silently changing the portfolio's interpretation.
    """

    metric_key: str
    metric_version: str
    evaluator_key: str
    evaluator_version: str
    value_type: MetricValueType
    expected_value: int | float | bool

    def __post_init__(self) -> None:
        for name, value in (
            ("metric key", self.metric_key),
            ("metric version", self.metric_version),
            ("evaluator key", self.evaluator_key),
            ("evaluator version", self.evaluator_version),
        ):
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
            ):
                raise HveeContractError(
                    f"portfolio {name} must be a "
                    "non-empty trimmed string"
                )

        if not isinstance(
            self.value_type,
            MetricValueType,
        ):
            raise HveeContractError(
                "portfolio expectation requires "
                "MetricValueType"
            )

        if self.value_type == MetricValueType.BOOLEAN:
            if not isinstance(
                self.expected_value,
                bool,
            ):
                raise HveeContractError(
                    "boolean portfolio expectation "
                    "requires bool"
                )

        elif self.value_type == MetricValueType.INTEGER:
            if (
                isinstance(
                    self.expected_value,
                    bool,
                )
                or not isinstance(
                    self.expected_value,
                    int,
                )
            ):
                raise HveeContractError(
                    "integer portfolio expectation "
                    "requires int"
                )

        elif self.value_type == MetricValueType.NUMBER:
            if (
                isinstance(
                    self.expected_value,
                    bool,
                )
                or not isinstance(
                    self.expected_value,
                    (int, float),
                )
                or not math.isfinite(
                    float(self.expected_value)
                )
            ):
                raise HveeContractError(
                    "numeric portfolio expectation "
                    "requires a finite number"
                )

        else:
            raise HveeContractError(
                "Portfolio v1 currently supports only "
                "boolean, integer, and numeric expectations"
            )

    @property
    def identity(
        self,
    ) -> tuple[str, str, str, str]:
        return (
            self.metric_key,
            self.metric_version,
            self.evaluator_key,
            self.evaluator_version,
        )


@dataclass(frozen=True, slots=True)
class ASRPortfolioCase:
    case_id: str
    mutation: ASRPortfolioMutation
    reference_text: str
    generated_text: str
    description: str
    expectations: tuple[
        ASRPortfolioExpectedObservation,
        ...,
    ]
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(
                self.case_id,
                str,
            )
            or not self.case_id
            or self.case_id
            != self.case_id.strip()
        ):
            raise HveeContractError(
                "ASR portfolio case id must be "
                "a non-empty trimmed string"
            )

        if not isinstance(
            self.mutation,
            ASRPortfolioMutation,
        ):
            raise HveeContractError(
                "ASR portfolio case requires "
                "ASRPortfolioMutation"
            )

        if not isinstance(
            self.reference_text,
            str,
        ) or not isinstance(
            self.generated_text,
            str,
        ):
            raise HveeContractError(
                "ASR portfolio transcripts must be strings"
            )

        if (
            not isinstance(
                self.description,
                str,
            )
            or not self.description.strip()
        ):
            raise HveeContractError(
                "ASR portfolio case requires a description"
            )

        if (
            not isinstance(
                self.expectations,
                tuple,
            )
            or not self.expectations
            or not all(
                isinstance(
                    expectation,
                    ASRPortfolioExpectedObservation,
                )
                for expectation
                in self.expectations
            )
        ):
            raise HveeContractError(
                "ASR portfolio case requires "
                "versioned expectations"
            )

        identities = tuple(
            expectation.identity
            for expectation
            in self.expectations
        )

        if len(identities) != len(
            set(identities)
        ):
            raise HveeContractError(
                "ASR portfolio case cannot contain "
                "duplicate expectation identities"
            )

        if (
            not isinstance(
                self.tags,
                tuple,
            )
            or not self.tags
            or any(
                not isinstance(tag, str)
                or not tag
                or tag != tag.strip()
                for tag in self.tags
            )
            or len(self.tags)
            != len(set(self.tags))
        ):
            raise HveeContractError(
                "ASR portfolio tags must be unique "
                "non-empty trimmed strings"
            )


@dataclass(frozen=True, slots=True)
class ASRPortfolioDefinition:
    key: str
    version: str
    cases: tuple[ASRPortfolioCase, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.key, str)
            or not self.key
            or self.key != self.key.strip()
            or not isinstance(
                self.version,
                str,
            )
            or not self.version
            or self.version
            != self.version.strip()
        ):
            raise HveeContractError(
                "ASR portfolio identity must be valid"
            )

        if (
            not isinstance(
                self.cases,
                tuple,
            )
            or not self.cases
            or not all(
                isinstance(
                    case,
                    ASRPortfolioCase,
                )
                for case in self.cases
            )
        ):
            raise HveeContractError(
                "ASR portfolio requires cases"
            )

        case_ids = tuple(
            case.case_id
            for case in self.cases
        )

        if len(case_ids) != len(
            set(case_ids)
        ):
            raise HveeContractError(
                "ASR portfolio case ids must be unique"
            )


def _expect(
    *,
    metric: MetricDefinition,
    evaluator: EvaluatorVersion,
    value: int | float | bool,
) -> ASRPortfolioExpectedObservation:
    return ASRPortfolioExpectedObservation(
        metric_key=metric.key,
        metric_version=metric.version,
        evaluator_key=evaluator.key,
        evaluator_version=evaluator.version,
        value_type=metric.value_type,
        expected_value=value,
    )


def _integrity(
    *,
    exact: bool,
    reference_empty: bool = False,
    generated_empty: bool = False,
    unexpected_output: bool = False,
    missing_output: bool = False,
) -> tuple[
    ASRPortfolioExpectedObservation,
    ...,
]:
    return (
        _expect(
            metric=EXACT_NORMALIZED_MATCH_METRIC,
            evaluator=(
                TRANSCRIPT_INTEGRITY_EVALUATOR
            ),
            value=exact,
        ),
        _expect(
            metric=REFERENCE_EMPTY_METRIC,
            evaluator=(
                TRANSCRIPT_INTEGRITY_EVALUATOR
            ),
            value=reference_empty,
        ),
        _expect(
            metric=GENERATED_EMPTY_METRIC,
            evaluator=(
                TRANSCRIPT_INTEGRITY_EVALUATOR
            ),
            value=generated_empty,
        ),
        _expect(
            metric=UNEXPECTED_OUTPUT_METRIC,
            evaluator=(
                TRANSCRIPT_INTEGRITY_EVALUATOR
            ),
            value=unexpected_output,
        ),
        _expect(
            metric=MISSING_OUTPUT_METRIC,
            evaluator=(
                TRANSCRIPT_INTEGRITY_EVALUATOR
            ),
            value=missing_output,
        ),
    )


def _word_edits(
    *,
    substitutions: int,
    insertions: int,
    deletions: int,
) -> tuple[
    ASRPortfolioExpectedObservation,
    ...,
]:
    return (
        _expect(
            metric=NORMALIZED_SUBSTITUTIONS_METRIC,
            evaluator=(
                NORMALIZED_WORD_ALIGNMENT_EVALUATOR
            ),
            value=substitutions,
        ),
        _expect(
            metric=NORMALIZED_INSERTIONS_METRIC,
            evaluator=(
                NORMALIZED_WORD_ALIGNMENT_EVALUATOR
            ),
            value=insertions,
        ),
        _expect(
            metric=NORMALIZED_DELETIONS_METRIC,
            evaluator=(
                NORMALIZED_WORD_ALIGNMENT_EVALUATOR
            ),
            value=deletions,
        ),
    )


def _numeric(
    *,
    reference_count: int,
    generated_count: int,
    sequence_match: bool,
    missing_count: int,
    unexpected_count: int,
) -> tuple[
    ASRPortfolioExpectedObservation,
    ...,
]:
    return (
        _expect(
            metric=REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
            evaluator=(
                NUMERIC_TOKEN_PRESERVATION_EVALUATOR
            ),
            value=reference_count,
        ),
        _expect(
            metric=GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
            evaluator=(
                NUMERIC_TOKEN_PRESERVATION_EVALUATOR
            ),
            value=generated_count,
        ),
        _expect(
            metric=NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
            evaluator=(
                NUMERIC_TOKEN_PRESERVATION_EVALUATOR
            ),
            value=sequence_match,
        ),
        _expect(
            metric=MISSING_NUMERIC_TOKEN_COUNT_METRIC,
            evaluator=(
                NUMERIC_TOKEN_PRESERVATION_EVALUATOR
            ),
            value=missing_count,
        ),
        _expect(
            metric=UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
            evaluator=(
                NUMERIC_TOKEN_PRESERVATION_EVALUATOR
            ),
            value=unexpected_count,
        ),
    )


ASR_EVALUATION_PORTFOLIO_V1 = (
    ASRPortfolioDefinition(
        key=ASR_EVALUATION_PORTFOLIO_KEY,
        version=ASR_EVALUATION_PORTFOLIO_VERSION,
        cases=(
            ASRPortfolioCase(
                case_id="control.exact",
                mutation=ASRPortfolioMutation.NONE,
                reference_text="the quick brown fox",
                generated_text="the quick brown fox",
                description=(
                    "Exact transcript control with no "
                    "intentional mutation."
                ),
                expectations=(
                    _integrity(
                        exact=True,
                    )
                    + _word_edits(
                        substitutions=0,
                        insertions=0,
                        deletions=0,
                    )
                ),
                tags=(
                    "control",
                    "exact",
                ),
            ),
            ASRPortfolioCase(
                case_id=(
                    "control.normalization-equivalent"
                ),
                mutation=(
                    ASRPortfolioMutation
                    .NORMALIZATION_EQUIVALENT
                ),
                reference_text="Hello, WORLD!",
                generated_text="hello world",
                description=(
                    "Surface-form variation expected to become "
                    "equivalent under basic normalization."
                ),
                expectations=(
                    _integrity(
                        exact=True,
                    )
                    + _word_edits(
                        substitutions=0,
                        insertions=0,
                        deletions=0,
                    )
                ),
                tags=(
                    "control",
                    "normalization",
                ),
            ),
            ASRPortfolioCase(
                case_id="control.numeric-preserved",
                mutation=ASRPortfolioMutation.NONE,
                reference_text=(
                    "invoice 125 is due at 5:30"
                ),
                generated_text=(
                    "invoice 125 is due at 5:30"
                ),
                description=(
                    "Positive numeric-preservation control "
                    "with digit-form tokens."
                ),
                expectations=(
                    _integrity(
                        exact=True,
                    )
                    + _numeric(
                        reference_count=2,
                        generated_count=2,
                        sequence_match=True,
                        missing_count=0,
                        unexpected_count=0,
                    )
                ),
                tags=(
                    "control",
                    "numeric",
                ),
            ),
            ASRPortfolioCase(
                case_id="mutation.word-substitution",
                mutation=(
                    ASRPortfolioMutation
                    .WORD_SUBSTITUTION
                ),
                reference_text="alpha beta gamma",
                generated_text="alpha delta gamma",
                description=(
                    "One controlled normalized word substitution."
                ),
                expectations=(
                    _integrity(
                        exact=False,
                    )
                    + _word_edits(
                        substitutions=1,
                        insertions=0,
                        deletions=0,
                    )
                ),
                tags=(
                    "mutation",
                    "word-error",
                    "substitution",
                ),
            ),
            ASRPortfolioCase(
                case_id="mutation.word-deletion",
                mutation=(
                    ASRPortfolioMutation.WORD_DELETION
                ),
                reference_text="alpha beta gamma",
                generated_text="alpha gamma",
                description=(
                    "One controlled normalized word deletion."
                ),
                expectations=(
                    _integrity(
                        exact=False,
                    )
                    + _word_edits(
                        substitutions=0,
                        insertions=0,
                        deletions=1,
                    )
                ),
                tags=(
                    "mutation",
                    "word-error",
                    "deletion",
                ),
            ),
            ASRPortfolioCase(
                case_id="mutation.word-insertion",
                mutation=(
                    ASRPortfolioMutation.WORD_INSERTION
                ),
                reference_text="alpha beta gamma",
                generated_text=(
                    "alpha beta extra gamma"
                ),
                description=(
                    "One controlled normalized word insertion."
                ),
                expectations=(
                    _integrity(
                        exact=False,
                    )
                    + _word_edits(
                        substitutions=0,
                        insertions=1,
                        deletions=0,
                    )
                ),
                tags=(
                    "mutation",
                    "word-error",
                    "insertion",
                ),
            ),
            ASRPortfolioCase(
                case_id="mutation.missing-output",
                mutation=(
                    ASRPortfolioMutation.MISSING_OUTPUT
                ),
                reference_text="alpha beta",
                generated_text="",
                description=(
                    "Non-empty reference with deliberately "
                    "missing generated transcript."
                ),
                expectations=(
                    _integrity(
                        exact=False,
                        generated_empty=True,
                        missing_output=True,
                    )
                    + _word_edits(
                        substitutions=0,
                        insertions=0,
                        deletions=2,
                    )
                ),
                tags=(
                    "mutation",
                    "integrity",
                    "missing-output",
                ),
            ),
            ASRPortfolioCase(
                case_id="mutation.unexpected-output",
                mutation=(
                    ASRPortfolioMutation
                    .UNEXPECTED_OUTPUT
                ),
                reference_text="",
                generated_text="unexpected words",
                description=(
                    "Empty reference with deliberately "
                    "non-empty generated transcript. This is "
                    "a transcript-level unexpected-output case, "
                    "not proof of acoustic hallucination."
                ),
                expectations=_integrity(
                    exact=False,
                    reference_empty=True,
                    unexpected_output=True,
                ),
                tags=(
                    "mutation",
                    "integrity",
                    "unexpected-output",
                ),
            ),
            ASRPortfolioCase(
                case_id="mutation.numeric-substitution",
                mutation=(
                    ASRPortfolioMutation
                    .NUMERIC_SUBSTITUTION
                ),
                reference_text="send 25 dollars",
                generated_text="send 35 dollars",
                description=(
                    "One digit-form numeric token is replaced."
                ),
                expectations=(
                    _integrity(
                        exact=False,
                    )
                    + _numeric(
                        reference_count=1,
                        generated_count=1,
                        sequence_match=False,
                        missing_count=1,
                        unexpected_count=1,
                    )
                ),
                tags=(
                    "mutation",
                    "numeric",
                    "substitution",
                ),
            ),
            ASRPortfolioCase(
                case_id="mutation.numeric-deletion",
                mutation=(
                    ASRPortfolioMutation.NUMERIC_DELETION
                ),
                reference_text="code 1234 now",
                generated_text="code now",
                description=(
                    "One reference digit-form numeric token "
                    "is removed."
                ),
                expectations=(
                    _integrity(
                        exact=False,
                    )
                    + _numeric(
                        reference_count=1,
                        generated_count=0,
                        sequence_match=False,
                        missing_count=1,
                        unexpected_count=0,
                    )
                ),
                tags=(
                    "mutation",
                    "numeric",
                    "deletion",
                ),
            ),
            ASRPortfolioCase(
                case_id="mutation.numeric-insertion",
                mutation=(
                    ASRPortfolioMutation.NUMERIC_INSERTION
                ),
                reference_text="call support now",
                generated_text="call 911 support now",
                description=(
                    "One unexpected digit-form numeric token "
                    "is inserted."
                ),
                expectations=(
                    _integrity(
                        exact=False,
                    )
                    + _numeric(
                        reference_count=0,
                        generated_count=1,
                        sequence_match=False,
                        missing_count=0,
                        unexpected_count=1,
                    )
                ),
                tags=(
                    "mutation",
                    "numeric",
                    "insertion",
                ),
            ),
            ASRPortfolioCase(
                case_id="mutation.numeric-reorder",
                mutation=(
                    ASRPortfolioMutation.NUMERIC_REORDER
                ),
                reference_text="values 10 then 20",
                generated_text="values 20 then 10",
                description=(
                    "The numeric multiset is preserved but "
                    "the ordered numeric sequence is changed."
                ),
                expectations=(
                    _integrity(
                        exact=False,
                    )
                    + _numeric(
                        reference_count=2,
                        generated_count=2,
                        sequence_match=False,
                        missing_count=0,
                        unexpected_count=0,
                    )
                ),
                tags=(
                    "mutation",
                    "numeric",
                    "ordering",
                ),
            ),
        ),
    )
)
