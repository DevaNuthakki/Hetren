from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from hvee.core.contracts import (
    EvaluatorVersion,
    HveeContractError,
    MetricDefinition,
    MetricDirection,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.evaluation import (
    ASR_EVALUATION_TYPE,
)


NUMERIC_TOKEN_METRIC_VERSION = "1.0.0"
NUMERIC_TOKEN_EVALUATOR_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ASRNumericTokenExtractionProfile:
    key: str
    version: str
    description: str


DIGIT_FORM_NUMERIC_EXTRACTION = (
    ASRNumericTokenExtractionProfile(
        key="hetren.asr.numeric.digit-form",
        version="1.0.0",
        description=(
            "Hetren ASR numeric-token extraction using Unicode NFKC "
            "followed by exact ASCII digit-form extraction. Numeric "
            "groups may contain period, comma, colon, slash, or hyphen "
            "separators when those separators occur between digits."
        ),
    )
)


_NUMERIC_TOKEN_PATTERN = re.compile(
    r"[0-9]+(?:[.,:/-][0-9]+)*"
)


REFERENCE_NUMERIC_TOKEN_COUNT_METRIC = MetricDefinition(
    key="asr.numeric-reference-count.digit-form",
    version=NUMERIC_TOKEN_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.INFORMATIONAL,
    unit="count",
    description=(
        "Count of digit-form numeric tokens extracted from the "
        "reference transcript using Hetren numeric extraction v1.0.0."
    ),
)


GENERATED_NUMERIC_TOKEN_COUNT_METRIC = MetricDefinition(
    key="asr.numeric-generated-count.digit-form",
    version=NUMERIC_TOKEN_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.INFORMATIONAL,
    unit="count",
    description=(
        "Count of digit-form numeric tokens extracted from the "
        "generated transcript using Hetren numeric extraction v1.0.0."
    ),
)


NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC = MetricDefinition(
    key="asr.numeric-token-sequence-match.digit-form",
    version=NUMERIC_TOKEN_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.HIGHER_IS_BETTER,
    description=(
        "Whether the complete ordered sequence of extracted digit-form "
        "numeric tokens exactly matches between reference and generated "
        "transcripts."
    ),
)


MISSING_NUMERIC_TOKEN_COUNT_METRIC = MetricDefinition(
    key="asr.numeric-missing-count.digit-form",
    version=NUMERIC_TOKEN_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Multiset count of reference digit-form numeric tokens that "
        "are not preserved in the generated transcript."
    ),
)


UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC = MetricDefinition(
    key="asr.numeric-unexpected-count.digit-form",
    version=NUMERIC_TOKEN_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Multiset count of generated digit-form numeric tokens that "
        "are not present in the reference transcript."
    ),
)


NUMERIC_TOKEN_PRESERVATION_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.numeric-preservation.digit-form",
    version=NUMERIC_TOKEN_EVALUATOR_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    description=(
        "Deterministic Hetren evaluator comparing exact digit-form "
        "numeric tokens extracted from ASR reference and generated "
        "transcripts."
    ),
)


@dataclass(frozen=True, slots=True)
class ASRNumericPreservationEvaluation:
    extraction_key: str
    extraction_version: str
    reference_tokens: tuple[str, ...]
    generated_tokens: tuple[str, ...]
    reference_count: int
    generated_count: int
    sequence_match: bool
    missing_count: int
    unexpected_count: int


def extract_digit_form_numeric_tokens(
    text: str,
) -> tuple[str, ...]:
    """
    Extract numeric digit forms without assigning semantic meaning.

    Version 1.0.0 applies Unicode NFKC but intentionally does not
    perform number-word conversion, locale interpretation, currency
    parsing, date parsing, or other semantic canonicalization.
    """

    if not isinstance(text, str):
        raise HveeContractError(
            "ASR numeric-token extraction requires a string"
        )

    normalized = unicodedata.normalize(
        "NFKC",
        text,
    )

    return tuple(
        match.group(0)
        for match in _NUMERIC_TOKEN_PATTERN.finditer(
            normalized
        )
    )


def evaluate_numeric_preservation(
    *,
    reference_text: str,
    generated_text: str,
) -> ASRNumericPreservationEvaluation:
    reference_tokens = (
        extract_digit_form_numeric_tokens(
            reference_text
        )
    )
    generated_tokens = (
        extract_digit_form_numeric_tokens(
            generated_text
        )
    )

    reference_counter = Counter(
        reference_tokens
    )
    generated_counter = Counter(
        generated_tokens
    )

    missing_count = sum(
        (
            reference_counter
            - generated_counter
        ).values()
    )

    unexpected_count = sum(
        (
            generated_counter
            - reference_counter
        ).values()
    )

    return ASRNumericPreservationEvaluation(
        extraction_key=(
            DIGIT_FORM_NUMERIC_EXTRACTION.key
        ),
        extraction_version=(
            DIGIT_FORM_NUMERIC_EXTRACTION.version
        ),
        reference_tokens=reference_tokens,
        generated_tokens=generated_tokens,
        reference_count=len(reference_tokens),
        generated_count=len(generated_tokens),
        sequence_match=(
            reference_tokens
            == generated_tokens
        ),
        missing_count=missing_count,
        unexpected_count=unexpected_count,
    )


def _build_observation(
    *,
    metric: MetricDefinition,
    value: int | bool,
) -> Observation:
    return Observation(
        metric_key=metric.key,
        metric_version=metric.version,
        evaluator_key=(
            NUMERIC_TOKEN_PRESERVATION_EVALUATOR.key
        ),
        evaluator_version=(
            NUMERIC_TOKEN_PRESERVATION_EVALUATOR.version
        ),
        evaluation_type=ASR_EVALUATION_TYPE,
        status=ObservationStatus.SUCCESS,
        value_type=metric.value_type,
        value=value,
    )


def build_numeric_preservation_observations(
    evaluation: ASRNumericPreservationEvaluation,
) -> tuple[
    Observation,
    Observation,
    Observation,
    Observation,
    Observation,
]:
    if (
        evaluation.extraction_key
        != DIGIT_FORM_NUMERIC_EXTRACTION.key
        or evaluation.extraction_version
        != DIGIT_FORM_NUMERIC_EXTRACTION.version
    ):
        raise HveeContractError(
            "ASR numeric-preservation observations require "
            "the Hetren digit-form extraction profile v1.0.0"
        )

    return (
        _build_observation(
            metric=REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
            value=evaluation.reference_count,
        ),
        _build_observation(
            metric=GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
            value=evaluation.generated_count,
        ),
        _build_observation(
            metric=NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
            value=evaluation.sequence_match,
        ),
        _build_observation(
            metric=MISSING_NUMERIC_TOKEN_COUNT_METRIC,
            value=evaluation.missing_count,
        ),
        _build_observation(
            metric=UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
            value=evaluation.unexpected_count,
        ),
    )
