"""Conservative, deterministic critical-number fidelity for US English ASR.

This evaluator makes transcript-grounded claims only. It does not infer an
acoustic cause, assume an unstated locale, or use an LLM as an evidence or
release authority. Numeric Preservation v1 remains a separate strict
digit-token signal with unchanged historical meaning.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date as calendar_date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from hvee.core.contracts import (
    EvaluatorVersion,
    HveeContractError,
    MetricDefinition,
    MetricDirection,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.evaluation import ASR_EVALUATION_TYPE


CRITICAL_NUMBER_METRIC_VERSION = "1.0.0"
CRITICAL_NUMBER_EVALUATOR_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberProfile:
    key: str
    version: str
    language: str
    locale: str
    description: str


EN_US_CRITICAL_NUMBER_PROFILE = ASRCriticalNumberProfile(
    key="hetren.asr.critical-number-profile.en-us",
    version="1.0.0",
    language="en",
    locale="en-US",
    description=(
        "Conservative US English critical-number interpretation for "
        "cardinals, decimals, percentages, US currency, selected "
        "measurements, clock times, and unambiguous calendar dates."
    ),
)


class ASRCriticalNumberType(StrEnum):
    CARDINAL_DECIMAL = "cardinal_decimal"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    MEASUREMENT = "measurement"
    CLOCK_TIME = "clock_time"
    CALENDAR_DATE = "calendar_date"
    UNKNOWN = "unknown"


class ASRCriticalNumberFindingType(StrEnum):
    MATCH = "match"
    SUBSTITUTION = "substitution"
    OMISSION = "omission"
    INSERTION = "insertion"
    AMBIGUITY = "ambiguity"
    UNSUPPORTED = "unsupported"


class ASRCriticalNumberReasonCode(StrEnum):
    FORMAT_EQUIVALENT = "format_equivalent"
    VALUE_SUBSTITUTION = "value_substitution"
    TYPE_SUBSTITUTION = "type_substitution"
    UNIT_SUBSTITUTION = "unit_substitution"
    CURRENCY_SUBSTITUTION = "currency_substitution"
    REFERENCE_ENTITY_OMITTED = "reference_entity_omitted"
    GENERATED_ENTITY_INSERTED = "generated_entity_inserted"
    REFERENCE_EXPRESSION_AMBIGUOUS = (
        "reference_expression_ambiguous"
    )
    GENERATED_EXPRESSION_AMBIGUOUS = (
        "generated_expression_ambiguous"
    )
    REFERENCE_EXPRESSION_UNSUPPORTED = (
        "reference_expression_unsupported"
    )
    GENERATED_EXPRESSION_UNSUPPORTED = (
        "generated_expression_unsupported"
    )
    CONTEXT_ALIGNMENT_AMBIGUOUS = (
        "context_alignment_ambiguous"
    )


class ASRCriticalNumberFidelityOutcome(StrEnum):
    PRESERVED = "preserved"
    NOT_PRESERVED = "not_preserved"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberEntity:
    numeric_type: ASRCriticalNumberType
    text: str
    span_start: int
    span_end: int
    canonical_value: str
    canonical_unit: str | None
    context_before: tuple[str, ...]
    context_after: tuple[str, ...]
    issue_reason_code: ASRCriticalNumberReasonCode | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "numeric_type": self.numeric_type.value,
            "text": self.text,
            "span": [self.span_start, self.span_end],
            "canonical_value": self.canonical_value,
            "canonical_unit": self.canonical_unit,
            "context_before": list(self.context_before),
            "context_after": list(self.context_after),
            "issue_reason_code": (
                self.issue_reason_code.value
                if self.issue_reason_code is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberFinding:
    finding_type: ASRCriticalNumberFindingType
    reason_code: ASRCriticalNumberReasonCode
    numeric_type: ASRCriticalNumberType
    reference: ASRCriticalNumberEntity | None
    generated: ASRCriticalNumberEntity | None
    context_anchor: tuple[str, ...]
    profile_key: str
    profile_version: str

    def to_json(self) -> dict[str, object]:
        return {
            "finding_type": self.finding_type.value,
            "reason_code": self.reason_code.value,
            "numeric_type": self.numeric_type.value,
            "reference": (
                self.reference.to_json()
                if self.reference is not None
                else None
            ),
            "generated": (
                self.generated.to_json()
                if self.generated is not None
                else None
            ),
            "context_anchor": list(self.context_anchor),
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
        }


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberFidelityEvaluation:
    profile_key: str
    profile_version: str
    evaluator_key: str
    evaluator_version: str
    outcome: ASRCriticalNumberFidelityOutcome
    reference_entities: tuple[ASRCriticalNumberEntity, ...]
    generated_entities: tuple[ASRCriticalNumberEntity, ...]
    findings: tuple[ASRCriticalNumberFinding, ...]

    @property
    def applicable(self) -> bool:
        return self.outcome != (
            ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE
        )

    @property
    def preserved(self) -> bool | None:
        if self.outcome == ASRCriticalNumberFidelityOutcome.PRESERVED:
            return True
        if self.outcome == ASRCriticalNumberFidelityOutcome.NOT_PRESERVED:
            return False
        return None

    def _count(
        self,
        finding_type: ASRCriticalNumberFindingType,
    ) -> int:
        return sum(
            finding.finding_type == finding_type
            for finding in self.findings
        )

    @property
    def substitution_count(self) -> int:
        return self._count(
            ASRCriticalNumberFindingType.SUBSTITUTION
        )

    @property
    def omission_count(self) -> int:
        return self._count(
            ASRCriticalNumberFindingType.OMISSION
        )

    @property
    def insertion_count(self) -> int:
        return self._count(
            ASRCriticalNumberFindingType.INSERTION
        )

    @property
    def ambiguity_count(self) -> int:
        return self._count(
            ASRCriticalNumberFindingType.AMBIGUITY
        )


CRITICAL_NUMBER_FIDELITY_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.critical-number-fidelity.en-us",
    version=CRITICAL_NUMBER_EVALUATOR_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    description=(
        "Deterministic US English ASR evaluator for preservation of "
        "typed, context-bound critical-number evidence."
    ),
)


def _metric(
    *,
    key: str,
    value_type: MetricValueType,
    direction: MetricDirection,
    description: str,
    unit: str | None = None,
) -> MetricDefinition:
    return MetricDefinition(
        key=key,
        version=CRITICAL_NUMBER_METRIC_VERSION,
        evaluation_type=ASR_EVALUATION_TYPE,
        value_type=value_type,
        direction=direction,
        description=description,
        unit=unit,
    )


CRITICAL_NUMBER_APPLICABLE_METRIC = _metric(
    key="asr.critical-number.applicable.en-us",
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "Whether either transcript contains supported, ambiguous, or "
        "unsupported critical-number evidence under the en-US profile."
    ),
)

CRITICAL_NUMBER_PRESERVED_METRIC = _metric(
    key="asr.critical-number.preserved.en-us",
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.HIGHER_IS_BETTER,
    description=(
        "Whether all conclusive critical-number evidence is preserved."
    ),
)

CRITICAL_NUMBER_OUTCOME_METRIC = _metric(
    key="asr.critical-number.outcome.en-us",
    value_type=MetricValueType.STRING,
    direction=MetricDirection.INFORMATIONAL,
    description="Versioned critical-number fidelity outcome.",
)

CRITICAL_NUMBER_REFERENCE_COUNT_METRIC = _metric(
    key="asr.critical-number.reference-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.INFORMATIONAL,
    unit="count",
    description="Count of conclusively typed reference entities.",
)

CRITICAL_NUMBER_GENERATED_COUNT_METRIC = _metric(
    key="asr.critical-number.generated-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.INFORMATIONAL,
    unit="count",
    description="Count of conclusively typed generated entities.",
)

CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC = _metric(
    key="asr.critical-number.substitution-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description="Count of proven critical-number substitutions.",
)

CRITICAL_NUMBER_OMISSION_COUNT_METRIC = _metric(
    key="asr.critical-number.omission-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description="Count of proven critical-number omissions.",
)

CRITICAL_NUMBER_INSERTION_COUNT_METRIC = _metric(
    key="asr.critical-number.insertion-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description="Count of proven critical-number insertions.",
)

CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC = _metric(
    key="asr.critical-number.ambiguity-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description="Count of explicit critical-number ambiguities.",
)

CRITICAL_NUMBER_FINDINGS_METRIC = _metric(
    key="asr.critical-number.findings.en-us",
    value_type=MetricValueType.JSON,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "Auditable typed findings with canonical values, source spans, "
        "context anchors, and stable reason codes."
    ),
)


CRITICAL_NUMBER_METRICS = (
    CRITICAL_NUMBER_APPLICABLE_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_REFERENCE_COUNT_METRIC,
    CRITICAL_NUMBER_GENERATED_COUNT_METRIC,
    CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC,
    CRITICAL_NUMBER_OMISSION_COUNT_METRIC,
    CRITICAL_NUMBER_INSERTION_COUNT_METRIC,
    CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_NUMBER_FINDINGS_METRIC,
)


_NUMBER_LITERAL = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?"
_WORD_TOKEN_PATTERN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_MONTH_PATTERN = "|".join(
    sorted(_MONTHS, key=len, reverse=True)
)

_UNIT_ALIASES = {
    "mcg": "mcg",
    "microgram": "mcg",
    "micrograms": "mcg",
    "mg": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ml": "mL",
    "milliliter": "mL",
    "milliliters": "mL",
    "millilitre": "mL",
    "millilitres": "mL",
    "l": "L",
    "liter": "L",
    "liters": "L",
    "litre": "L",
    "litres": "L",
    "mm": "mm",
    "millimeter": "mm",
    "millimeters": "mm",
    "cm": "cm",
    "centimeter": "cm",
    "centimeters": "cm",
    "m": "m",
    "meter": "m",
    "meters": "m",
    "km": "km",
    "kilometer": "km",
    "kilometers": "km",
}

_SMALL_NUMBERS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_SCALES = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}

_NUMBER_WORDS = frozenset(
    (*_SMALL_NUMBERS, *_TENS, *_SCALES, "hundred", "and", "point")
)

_NUMBER_WORD_COMPONENT_PATTERN = "|".join(
    sorted(
        _NUMBER_WORDS - {"and", "point"},
        key=len,
        reverse=True,
    )
)

_NUMBER_WORD_SEQUENCE_PATTERN = (
    rf"(?:{_NUMBER_WORD_COMPONENT_PATTERN})"
    rf"(?:[\s-]+(?:and[\s-]+)?"
    rf"(?:{_NUMBER_WORD_COMPONENT_PATTERN}))*"
)


@dataclass(frozen=True, slots=True)
class _Token:
    text: str
    lower: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _RawEntity:
    numeric_type: ASRCriticalNumberType
    start: int
    end: int
    canonical_value: str
    canonical_unit: str | None
    issue_reason_code: ASRCriticalNumberReasonCode | None = None


def _validate_profile(profile: ASRCriticalNumberProfile) -> None:
    if not isinstance(profile, ASRCriticalNumberProfile):
        raise HveeContractError(
            "critical-number evaluation requires ASRCriticalNumberProfile"
        )
    if profile != EN_US_CRITICAL_NUMBER_PROFILE:
        raise HveeContractError(
            "critical-number fidelity v1 requires the explicit "
            "Hetren en-US profile v1.0.0"
        )


def _normalize_with_span_map(text: str) -> tuple[str, tuple[int, ...]]:
    normalized_parts: list[str] = []
    source_indices: list[int] = []
    for index, character in enumerate(text):
        part = unicodedata.normalize("NFKC", character)
        normalized_parts.append(part)
        source_indices.extend(index for _ in part)
    return "".join(normalized_parts), tuple(source_indices)


def _source_span(
    start: int,
    end: int,
    source_map: tuple[int, ...],
    source_length: int,
) -> tuple[int, int]:
    if not source_map:
        return 0, 0
    source_start = source_map[start] if start < len(source_map) else source_length
    source_end = (
        source_map[end - 1] + 1
        if end > start and end - 1 < len(source_map)
        else source_start
    )
    return source_start, source_end


def _canonical_decimal(value: str | Decimal | int) -> str:
    try:
        decimal_value = (
            value
            if isinstance(value, Decimal)
            else Decimal(str(value).replace(",", ""))
        )
    except InvalidOperation as exc:
        raise HveeContractError("invalid canonical numeric value") from exc
    if not decimal_value.is_finite():
        raise HveeContractError("canonical numeric value must be finite")
    normalized = format(decimal_value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    if normalized in {"", "-0"}:
        return "0"
    return normalized


def _parse_integer_words(words: tuple[str, ...]) -> int | None:
    filtered = tuple(word for word in words if word != "and")
    if not filtered:
        return None
    total = 0
    group = 0
    previous = "start"
    for word in filtered:
        if word in _SMALL_NUMBERS:
            value = _SMALL_NUMBERS[word]
            if previous == "small" or (
                previous == "tens" and value >= 10
            ):
                return None
            group += value
            previous = "small"
        elif word in _TENS:
            if previous in {"small", "tens"}:
                return None
            group += _TENS[word]
            previous = "tens"
        elif word == "hundred":
            if group <= 0 or group > 99 or previous == "hundred":
                return None
            group *= 100
            previous = "hundred"
        elif word in _SCALES:
            if group <= 0:
                return None
            total += group * _SCALES[word]
            group = 0
            previous = "scale"
        else:
            return None
    return total + group


def _parse_number_words(words: tuple[str, ...]) -> Decimal | None:
    if not words or any(word not in _NUMBER_WORDS for word in words):
        return None
    if words.count("point") > 1:
        return None
    if "point" not in words:
        integer = _parse_integer_words(words)
        return Decimal(integer) if integer is not None else None
    point_index = words.index("point")
    integer_words = words[:point_index]
    fraction_words = words[point_index + 1 :]
    integer = _parse_integer_words(integer_words)
    if integer is None or not fraction_words:
        return None
    digits: list[str] = []
    for word in fraction_words:
        value = _SMALL_NUMBERS.get(word)
        if value is None or value > 9:
            return None
        digits.append(str(value))
    return Decimal(f"{integer}.{''.join(digits)}")


def _number_word_tokens(normalized: str) -> tuple[_Token, ...]:
    return tuple(
        _Token(
            text=match.group(0),
            lower=match.group(0).lower(),
            start=match.start(),
            end=match.end(),
        )
        for match in _WORD_TOKEN_PATTERN.finditer(normalized)
    )


def _is_between_only_space_or_hyphen(
    text: str,
    left: int,
    right: int,
) -> bool:
    return bool(re.fullmatch(r"[\s-]*", text[left:right]))


def _extract_raw_entities(normalized: str) -> tuple[_RawEntity, ...]:
    entities: list[_RawEntity] = []

    def free(start: int, end: int) -> bool:
        return not any(
            start < existing.end and end > existing.start
            for existing in entities
        )

    def add(entity: _RawEntity) -> None:
        if free(entity.start, entity.end):
            entities.append(entity)

    iso_date_pattern = re.compile(
        r"\b(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-"
        r"(?P<day>[0-9]{2})\b"
    )
    for match in iso_date_pattern.finditer(normalized):
        year = int(match.group("year"))
        month = int(match.group("month"))
        day = int(match.group("day"))
        try:
            calendar_date(year, month, day)
        except ValueError:
            add(
                _RawEntity(
                    ASRCriticalNumberType.CALENDAR_DATE,
                    match.start(),
                    match.end(),
                    match.group(0),
                    None,
                    ASRCriticalNumberReasonCode.REFERENCE_EXPRESSION_UNSUPPORTED,
                )
            )
        else:
            add(
                _RawEntity(
                    ASRCriticalNumberType.CALENDAR_DATE,
                    match.start(),
                    match.end(),
                    f"{year:04d}-{month:02d}-{day:02d}",
                    None,
                )
            )

    month_date_pattern = re.compile(
        rf"\b(?P<month>{_MONTH_PATTERN})\.?\s+"
        r"(?P<day>[0-9]{1,2})(?:st|nd|rd|th)?"
        r",?\s+(?P<year>[0-9]{4})\b",
        re.IGNORECASE,
    )
    for match in month_date_pattern.finditer(normalized):
        month = _MONTHS[match.group("month").lower()]
        day = int(match.group("day"))
        year = int(match.group("year"))
        try:
            calendar_date(year, month, day)
        except ValueError:
            add(
                _RawEntity(
                    ASRCriticalNumberType.CALENDAR_DATE,
                    match.start(),
                    match.end(),
                    match.group(0),
                    None,
                    ASRCriticalNumberReasonCode.REFERENCE_EXPRESSION_UNSUPPORTED,
                )
            )
        else:
            add(
                _RawEntity(
                    ASRCriticalNumberType.CALENDAR_DATE,
                    match.start(),
                    match.end(),
                    f"{year:04d}-{month:02d}-{day:02d}",
                    None,
                )
            )

    digit_time_pattern = re.compile(
        r"\b(?P<hour>[0-9]{1,2}):(?P<minute>[0-9]{2})"
        r"\s*(?P<period>a\.?m\.?|p\.?m\.?)\b",
        re.IGNORECASE,
    )
    for match in digit_time_pattern.finditer(normalized):
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        period = match.group("period").lower().replace(".", "")
        if 1 <= hour <= 12 and 0 <= minute <= 59:
            hour = hour % 12 + (12 if period == "pm" else 0)
            add(
                _RawEntity(
                    ASRCriticalNumberType.CLOCK_TIME,
                    match.start(),
                    match.end(),
                    f"{hour:02d}:{minute:02d}",
                    None,
                )
            )

    twenty_four_hour_pattern = re.compile(
        r"\b(?P<hour>[01]?[0-9]|2[0-3]):(?P<minute>[0-5][0-9])\b"
    )
    for match in twenty_four_hour_pattern.finditer(normalized):
        add(
            _RawEntity(
                ASRCriticalNumberType.CLOCK_TIME,
                match.start(),
                match.end(),
                f"{int(match.group('hour')):02d}:"
                f"{int(match.group('minute')):02d}",
                None,
            )
        )

    unsupported_patterns = (
        re.compile(r"\b(?:[0-9]{1,3}\.){2,}[0-9]{1,3}\b"),
        re.compile(rf"\b{_NUMBER_LITERAL}[eE][+-]?[0-9]+\b"),
        re.compile(r"\b(?:\+1\s*)?(?:\([0-9]{3}\)|[0-9]{3})"
                   r"[-.\s][0-9]{3}[-.\s][0-9]{4}\b"),
        re.compile(rf"\b{_NUMBER_LITERAL}\s*[-–—]\s*{_NUMBER_LITERAL}\b"),
        re.compile(
            rf"\b{_NUMBER_LITERAL}\s+(?:to|over)\s+"
            rf"{_NUMBER_LITERAL}\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\b(?:between|from)\s+{_NUMBER_LITERAL}\s+"
            rf"(?:and|to)\s+{_NUMBER_LITERAL}\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b[0-9]{4}/[0-9]{1,2}/[0-9]{1,2}\b"),
        re.compile(r"\b[0-9]+/[0-9]+\b"),
        re.compile(r"\b[0-9]+:[0-9]+\b"),
        re.compile(r"\b[0-9]+,[0-9]{1,2}\b"),
        re.compile(r"\b[0-9]+,[0-9]{4,}\b"),
        re.compile(
            r"\b(?:account|acct|id|identifier|phone|pin|code)"
            r"(?:\s+(?:number|no))?\s*[:#-]?\s*[0-9][0-9-]{2,}\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\b{_NUMBER_WORD_SEQUENCE_PATTERN}\s+(?:to|over)\s+"
            rf"{_NUMBER_WORD_SEQUENCE_PATTERN}\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\b(?:between|from)\s+{_NUMBER_WORD_SEQUENCE_PATTERN}\s+"
            rf"(?:and|to)\s+{_NUMBER_WORD_SEQUENCE_PATTERN}\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\b{_NUMBER_WORD_SEQUENCE_PATTERN}\s+"
            r"(?:(?:and\s+)?a\s+)?"
            r"(?:half|halves|quarter|quarters|third|thirds)\b",
            re.IGNORECASE,
        ),
        re.compile(rf"(?<!\w)[€£¥]\s*{_NUMBER_LITERAL}\b"),
        re.compile(
            rf"\b{_NUMBER_LITERAL}\s+(?:euros?|pounds?|yen)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b[0-9]{7,}\b"),
    )
    ambiguous_date_pattern = re.compile(
        r"\b[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}\b"
    )
    for match in ambiguous_date_pattern.finditer(normalized):
        add(
            _RawEntity(
                ASRCriticalNumberType.CALENDAR_DATE,
                match.start(),
                match.end(),
                match.group(0),
                None,
                ASRCriticalNumberReasonCode.REFERENCE_EXPRESSION_AMBIGUOUS,
            )
        )
    for pattern in unsupported_patterns:
        for match in pattern.finditer(normalized):
            add(
                _RawEntity(
                    ASRCriticalNumberType.UNKNOWN,
                    match.start(),
                    match.end(),
                    match.group(0).lower(),
                    None,
                    ASRCriticalNumberReasonCode.REFERENCE_EXPRESSION_UNSUPPORTED,
                )
            )

    currency_patterns = (
        re.compile(rf"(?<!\w)\$\s*(?P<value>{_NUMBER_LITERAL})\b"),
        re.compile(
            rf"\b(?P<value>{_NUMBER_LITERAL})\s*"
            r"(?:US\s+dollars?|USD|dollars?)\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\bUSD\s*(?P<value>{_NUMBER_LITERAL})\b",
            re.IGNORECASE,
        ),
    )
    for pattern in currency_patterns:
        for match in pattern.finditer(normalized):
            add(
                _RawEntity(
                    ASRCriticalNumberType.CURRENCY,
                    match.start(),
                    match.end(),
                    _canonical_decimal(match.group("value")),
                    "USD",
                )
            )

    percentage_pattern = re.compile(
        rf"\b(?P<value>{_NUMBER_LITERAL})\s*"
        r"(?:%(?!\w)|percent(?:age)?\b)",
        re.IGNORECASE,
    )
    for match in percentage_pattern.finditer(normalized):
        add(
            _RawEntity(
                ASRCriticalNumberType.PERCENTAGE,
                match.start(),
                match.end(),
                _canonical_decimal(match.group("value")),
                "percent",
            )
        )

    unit_pattern = "|".join(
        sorted(_UNIT_ALIASES, key=len, reverse=True)
    )
    measurement_pattern = re.compile(
        rf"\b(?P<value>{_NUMBER_LITERAL})\s*"
        rf"(?P<unit>{unit_pattern})\b",
        re.IGNORECASE,
    )
    for match in measurement_pattern.finditer(normalized):
        add(
            _RawEntity(
                ASRCriticalNumberType.MEASUREMENT,
                match.start(),
                match.end(),
                _canonical_decimal(match.group("value")),
                _UNIT_ALIASES[match.group("unit").lower()],
            )
        )

    tokens = _number_word_tokens(normalized)
    token_claimed = [False] * len(tokens)
    for index, token in enumerate(tokens):
        token_claimed[index] = not free(token.start, token.end)

    for period_index, period_token in enumerate(tokens):
        if period_token.lower not in {"am", "pm"} or token_claimed[period_index]:
            continue
        start_index = period_index - 1
        while (
            start_index >= 0
            and not token_claimed[start_index]
            and tokens[start_index].lower in _NUMBER_WORDS
            and _is_between_only_space_or_hyphen(
                normalized,
                tokens[start_index].end,
                tokens[start_index + 1].start,
            )
        ):
            start_index -= 1
        start_index += 1
        words = tuple(
            token.lower for token in tokens[start_index:period_index]
        )
        chosen: tuple[int, int] | None = None
        for split in range(1, len(words)):
            hour_value = _parse_number_words(words[:split])
            minute_value = _parse_number_words(words[split:])
            if (
                hour_value is not None
                and minute_value is not None
                and hour_value == hour_value.to_integral_value()
                and minute_value == minute_value.to_integral_value()
                and 1 <= int(hour_value) <= 12
                and 0 <= int(minute_value) <= 59
            ):
                chosen = (int(hour_value), int(minute_value))
                break
        if chosen is None:
            continue
        hour, minute = chosen
        hour = hour % 12 + (12 if period_token.lower == "pm" else 0)
        add(
            _RawEntity(
                ASRCriticalNumberType.CLOCK_TIME,
                tokens[start_index].start,
                period_token.end,
                f"{hour:02d}:{minute:02d}",
                None,
            )
        )
        for claimed_index in range(start_index, period_index + 1):
            token_claimed[claimed_index] = True

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token_claimed[index] or token.lower not in _NUMBER_WORDS:
            index += 1
            continue
        end_index = index
        while (
            end_index + 1 < len(tokens)
            and not token_claimed[end_index + 1]
            and tokens[end_index + 1].lower in _NUMBER_WORDS
            and _is_between_only_space_or_hyphen(
                normalized,
                tokens[end_index].end,
                tokens[end_index + 1].start,
            )
        ):
            end_index += 1
        chosen_end: int | None = None
        chosen_value: Decimal | None = None
        for candidate_end in range(end_index, index - 1, -1):
            words = tuple(
                item.lower for item in tokens[index : candidate_end + 1]
            )
            if words[-1] in {"and", "point"}:
                continue
            value = _parse_number_words(words)
            if value is not None:
                chosen_end = candidate_end
                chosen_value = value
                break
        if chosen_end is None or chosen_value is None:
            index += 1
            continue
        suffix_index = chosen_end + 1
        numeric_type = ASRCriticalNumberType.CARDINAL_DECIMAL
        unit: str | None = None
        entity_end = tokens[chosen_end].end
        if (
            suffix_index < len(tokens)
            and not token_claimed[suffix_index]
            and _is_between_only_space_or_hyphen(
                normalized,
                tokens[chosen_end].end,
                tokens[suffix_index].start,
            )
        ):
            suffix = tokens[suffix_index].lower
            if suffix in {"percent", "percentage"}:
                numeric_type = ASRCriticalNumberType.PERCENTAGE
                unit = "percent"
                entity_end = tokens[suffix_index].end
            elif suffix in {"dollar", "dollars", "usd"}:
                numeric_type = ASRCriticalNumberType.CURRENCY
                unit = "USD"
                entity_end = tokens[suffix_index].end
            elif suffix in _UNIT_ALIASES:
                numeric_type = ASRCriticalNumberType.MEASUREMENT
                unit = _UNIT_ALIASES[suffix]
                entity_end = tokens[suffix_index].end
        add(
            _RawEntity(
                numeric_type,
                token.start,
                entity_end,
                _canonical_decimal(chosen_value),
                unit,
            )
        )
        for claimed_index in range(index, chosen_end + 1):
            token_claimed[claimed_index] = True
        if entity_end > tokens[chosen_end].end:
            token_claimed[suffix_index] = True
            index = suffix_index + 1
        else:
            index = chosen_end + 1

    digit_pattern = re.compile(rf"(?<![\w.]){_NUMBER_LITERAL}(?![\w.])")
    for match in digit_pattern.finditer(normalized):
        add(
            _RawEntity(
                ASRCriticalNumberType.CARDINAL_DECIMAL,
                match.start(),
                match.end(),
                _canonical_decimal(match.group(0)),
                None,
            )
        )

    return tuple(sorted(entities, key=lambda entity: (entity.start, entity.end)))


def _context_words(
    normalized: str,
    start: int,
    end: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    before = tuple(
        match.group(0).lower()
        for match in _WORD_TOKEN_PATTERN.finditer(normalized[:start])
    )[-2:]
    after = tuple(
        match.group(0).lower()
        for match in _WORD_TOKEN_PATTERN.finditer(normalized[end:])
    )[:2]
    return before, after


def extract_critical_number_entities(
    *,
    text: str,
    profile: ASRCriticalNumberProfile,
) -> tuple[ASRCriticalNumberEntity, ...]:
    if not isinstance(text, str):
        raise HveeContractError(
            "critical-number extraction requires a string"
        )
    _validate_profile(profile)
    normalized, source_map = _normalize_with_span_map(text)
    result: list[ASRCriticalNumberEntity] = []
    for raw in _extract_raw_entities(normalized):
        source_start, source_end = _source_span(
            raw.start,
            raw.end,
            source_map,
            len(text),
        )
        before, after = _context_words(
            normalized,
            raw.start,
            raw.end,
        )
        result.append(
            ASRCriticalNumberEntity(
                numeric_type=raw.numeric_type,
                text=text[source_start:source_end],
                span_start=source_start,
                span_end=source_end,
                canonical_value=raw.canonical_value,
                canonical_unit=raw.canonical_unit,
                context_before=before,
                context_after=after,
                issue_reason_code=raw.issue_reason_code,
            )
        )
    return tuple(result)


def _equivalent(
    reference: ASRCriticalNumberEntity,
    generated: ASRCriticalNumberEntity,
) -> bool:
    return (
        reference.numeric_type == generated.numeric_type
        and reference.canonical_value == generated.canonical_value
        and reference.canonical_unit == generated.canonical_unit
    )


def _context_overlap(
    reference: ASRCriticalNumberEntity,
    generated: ASRCriticalNumberEntity,
) -> int:
    reference_words = set(
        (*reference.context_before, *reference.context_after)
    )
    generated_words = set(
        (*generated.context_before, *generated.context_after)
    )
    return len(reference_words & generated_words)


def _pair_cost(
    reference: ASRCriticalNumberEntity,
    generated: ASRCriticalNumberEntity,
) -> int:
    if _equivalent(reference, generated):
        return 0
    if _context_overlap(reference, generated) > 0:
        return 1
    if reference.numeric_type == generated.numeric_type:
        return 2
    return 3


AlignmentOperation = tuple[str, int | None, int | None]


def _align_entities(
    reference: tuple[ASRCriticalNumberEntity, ...],
    generated: tuple[ASRCriticalNumberEntity, ...],
) -> tuple[tuple[AlignmentOperation, ...], bool]:
    gap_cost = 2
    reference_count = len(reference)
    generated_count = len(generated)
    costs = [
        [0] * (generated_count + 1)
        for _ in range(reference_count + 1)
    ]
    ambiguous = [
        [False] * (generated_count + 1)
        for _ in range(reference_count + 1)
    ]
    choices: list[list[str | None]] = [
        [None] * (generated_count + 1)
        for _ in range(reference_count + 1)
    ]

    for reference_index in range(reference_count - 1, -1, -1):
        costs[reference_index][generated_count] = (
            gap_cost + costs[reference_index + 1][generated_count]
        )
        choices[reference_index][generated_count] = "omit"
    for generated_index in range(generated_count - 1, -1, -1):
        costs[reference_count][generated_index] = (
            gap_cost + costs[reference_count][generated_index + 1]
        )
        choices[reference_count][generated_index] = "insert"

    for reference_index in range(reference_count - 1, -1, -1):
        for generated_index in range(generated_count - 1, -1, -1):
            candidates = (
                (
                    "pair",
                    _pair_cost(
                        reference[reference_index],
                        generated[generated_index],
                    )
                    + costs[reference_index + 1][generated_index + 1],
                    ambiguous[reference_index + 1][generated_index + 1],
                ),
                (
                    "omit",
                    gap_cost + costs[reference_index + 1][generated_index],
                    ambiguous[reference_index + 1][generated_index],
                ),
                (
                    "insert",
                    gap_cost + costs[reference_index][generated_index + 1],
                    ambiguous[reference_index][generated_index + 1],
                ),
            )
            minimum = min(cost for _, cost, _ in candidates)
            minimum_candidates = tuple(
                candidate for candidate in candidates if candidate[1] == minimum
            )
            choices[reference_index][generated_index] = minimum_candidates[0][0]
            costs[reference_index][generated_index] = minimum
            ambiguous[reference_index][generated_index] = (
                len(minimum_candidates) > 1
                or any(candidate[2] for candidate in minimum_candidates)
            )

    path: list[AlignmentOperation] = []
    reference_index = 0
    generated_index = 0
    while reference_index < reference_count or generated_index < generated_count:
        operation = choices[reference_index][generated_index]
        if operation == "pair":
            path.append(("pair", reference_index, generated_index))
            reference_index += 1
            generated_index += 1
        elif operation == "omit":
            path.append(("omit", reference_index, None))
            reference_index += 1
        elif operation == "insert":
            path.append(("insert", None, generated_index))
            generated_index += 1
        else:
            raise HveeContractError(
                "critical-number alignment could not select a path"
            )

    return tuple(path), ambiguous[0][0]


def _anchor(
    reference: ASRCriticalNumberEntity | None,
    generated: ASRCriticalNumberEntity | None,
) -> tuple[str, ...]:
    reference_words = (
        (*reference.context_before, *reference.context_after)
        if reference is not None
        else ()
    )
    generated_words = (
        (*generated.context_before, *generated.context_after)
        if generated is not None
        else ()
    )
    common = tuple(
        word for word in reference_words if word in set(generated_words)
    )
    if common:
        return tuple(dict.fromkeys(common))[:4]
    return tuple(dict.fromkeys((*reference_words, *generated_words)))[:4]


def _substitution_reason(
    reference: ASRCriticalNumberEntity,
    generated: ASRCriticalNumberEntity,
) -> ASRCriticalNumberReasonCode:
    if reference.numeric_type != generated.numeric_type:
        return ASRCriticalNumberReasonCode.TYPE_SUBSTITUTION
    if (
        reference.numeric_type == ASRCriticalNumberType.CURRENCY
        and reference.canonical_unit != generated.canonical_unit
    ):
        return ASRCriticalNumberReasonCode.CURRENCY_SUBSTITUTION
    if (
        reference.numeric_type == ASRCriticalNumberType.MEASUREMENT
        and reference.canonical_unit != generated.canonical_unit
    ):
        return ASRCriticalNumberReasonCode.UNIT_SUBSTITUTION
    return ASRCriticalNumberReasonCode.VALUE_SUBSTITUTION


def _uncertain_correspondence(
    conclusive: ASRCriticalNumberEntity,
    uncertain: tuple[ASRCriticalNumberEntity, ...],
) -> ASRCriticalNumberEntity | None:
    for candidate in uncertain:
        if candidate.numeric_type == conclusive.numeric_type:
            return candidate
        if (
            candidate.numeric_type == ASRCriticalNumberType.UNKNOWN
            and _context_overlap(conclusive, candidate) > 0
        ):
            return candidate
    return None


def _finding(
    *,
    finding_type: ASRCriticalNumberFindingType,
    reason_code: ASRCriticalNumberReasonCode,
    numeric_type: ASRCriticalNumberType,
    reference: ASRCriticalNumberEntity | None,
    generated: ASRCriticalNumberEntity | None,
    profile: ASRCriticalNumberProfile,
) -> ASRCriticalNumberFinding:
    return ASRCriticalNumberFinding(
        finding_type=finding_type,
        reason_code=reason_code,
        numeric_type=numeric_type,
        reference=reference,
        generated=generated,
        context_anchor=_anchor(reference, generated),
        profile_key=profile.key,
        profile_version=profile.version,
    )


def _derive_outcome(
    *,
    reference: tuple[ASRCriticalNumberEntity, ...],
    generated: tuple[ASRCriticalNumberEntity, ...],
    findings: tuple[ASRCriticalNumberFinding, ...],
) -> ASRCriticalNumberFidelityOutcome:
    failure_types = {
        ASRCriticalNumberFindingType.SUBSTITUTION,
        ASRCriticalNumberFindingType.OMISSION,
        ASRCriticalNumberFindingType.INSERTION,
    }
    if any(finding.finding_type in failure_types for finding in findings):
        return ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
    if any(
        finding.finding_type
        in {
            ASRCriticalNumberFindingType.AMBIGUITY,
            ASRCriticalNumberFindingType.UNSUPPORTED,
        }
        for finding in findings
    ):
        return ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
    if not reference and not generated:
        return ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE
    return ASRCriticalNumberFidelityOutcome.PRESERVED


def evaluate_critical_number_fidelity(
    *,
    reference_text: str,
    generated_text: str,
    profile: ASRCriticalNumberProfile,
) -> ASRCriticalNumberFidelityEvaluation:
    if not isinstance(reference_text, str) or not isinstance(generated_text, str):
        raise HveeContractError(
            "critical-number evaluation requires string transcripts"
        )
    _validate_profile(profile)
    reference_all = extract_critical_number_entities(
        text=reference_text,
        profile=profile,
    )
    generated_all = extract_critical_number_entities(
        text=generated_text,
        profile=profile,
    )
    reference = tuple(
        entity for entity in reference_all if entity.issue_reason_code is None
    )
    generated = tuple(
        entity for entity in generated_all if entity.issue_reason_code is None
    )
    reference_uncertain = tuple(
        entity for entity in reference_all if entity.issue_reason_code is not None
    )
    generated_uncertain = tuple(
        entity for entity in generated_all if entity.issue_reason_code is not None
    )
    findings: list[ASRCriticalNumberFinding] = []

    for entity in reference_all:
        if entity.issue_reason_code is None:
            continue
        finding_type = (
            ASRCriticalNumberFindingType.AMBIGUITY
            if entity.issue_reason_code
            == ASRCriticalNumberReasonCode.REFERENCE_EXPRESSION_AMBIGUOUS
            else ASRCriticalNumberFindingType.UNSUPPORTED
        )
        findings.append(
            _finding(
                finding_type=finding_type,
                reason_code=entity.issue_reason_code,
                numeric_type=entity.numeric_type,
                reference=entity,
                generated=None,
                profile=profile,
            )
        )

    for entity in generated_all:
        if entity.issue_reason_code is None:
            continue
        if entity.issue_reason_code == (
            ASRCriticalNumberReasonCode.REFERENCE_EXPRESSION_AMBIGUOUS
        ):
            reason_code = (
                ASRCriticalNumberReasonCode.GENERATED_EXPRESSION_AMBIGUOUS
            )
            finding_type = ASRCriticalNumberFindingType.AMBIGUITY
        else:
            reason_code = (
                ASRCriticalNumberReasonCode.GENERATED_EXPRESSION_UNSUPPORTED
            )
            finding_type = ASRCriticalNumberFindingType.UNSUPPORTED
        findings.append(
            _finding(
                finding_type=finding_type,
                reason_code=reason_code,
                numeric_type=entity.numeric_type,
                reference=None,
                generated=entity,
                profile=profile,
            )
        )

    path, alignment_ambiguous = _align_entities(reference, generated)
    for operation, reference_index, generated_index in path:
        reference_entity = (
            reference[reference_index]
            if reference_index is not None
            else None
        )
        generated_entity = (
            generated[generated_index]
            if generated_index is not None
            else None
        )
        if operation == "pair":
            assert reference_entity is not None
            assert generated_entity is not None
            if _equivalent(reference_entity, generated_entity):
                findings.append(
                    _finding(
                        finding_type=ASRCriticalNumberFindingType.MATCH,
                        reason_code=ASRCriticalNumberReasonCode.FORMAT_EQUIVALENT,
                        numeric_type=reference_entity.numeric_type,
                        reference=reference_entity,
                        generated=generated_entity,
                        profile=profile,
                    )
                )
            else:
                findings.append(
                    _finding(
                        finding_type=ASRCriticalNumberFindingType.SUBSTITUTION,
                        reason_code=_substitution_reason(
                            reference_entity,
                            generated_entity,
                        ),
                        numeric_type=reference_entity.numeric_type,
                        reference=reference_entity,
                        generated=generated_entity,
                        profile=profile,
                    )
                )
        elif operation == "omit":
            assert reference_entity is not None
            uncertain_generated = _uncertain_correspondence(
                reference_entity,
                generated_uncertain,
            )
            if uncertain_generated is not None:
                findings.append(
                    _finding(
                        finding_type=ASRCriticalNumberFindingType.AMBIGUITY,
                        reason_code=(
                            ASRCriticalNumberReasonCode
                            .CONTEXT_ALIGNMENT_AMBIGUOUS
                        ),
                        numeric_type=reference_entity.numeric_type,
                        reference=reference_entity,
                        generated=uncertain_generated,
                        profile=profile,
                    )
                )
            else:
                findings.append(
                    _finding(
                        finding_type=ASRCriticalNumberFindingType.OMISSION,
                        reason_code=(
                            ASRCriticalNumberReasonCode.REFERENCE_ENTITY_OMITTED
                        ),
                        numeric_type=reference_entity.numeric_type,
                        reference=reference_entity,
                        generated=None,
                        profile=profile,
                    )
                )
        else:
            assert generated_entity is not None
            uncertain_reference = _uncertain_correspondence(
                generated_entity,
                reference_uncertain,
            )
            if uncertain_reference is not None:
                findings.append(
                    _finding(
                        finding_type=ASRCriticalNumberFindingType.AMBIGUITY,
                        reason_code=(
                            ASRCriticalNumberReasonCode
                            .CONTEXT_ALIGNMENT_AMBIGUOUS
                        ),
                        numeric_type=generated_entity.numeric_type,
                        reference=uncertain_reference,
                        generated=generated_entity,
                        profile=profile,
                    )
                )
            else:
                findings.append(
                    _finding(
                        finding_type=ASRCriticalNumberFindingType.INSERTION,
                        reason_code=(
                            ASRCriticalNumberReasonCode.GENERATED_ENTITY_INSERTED
                        ),
                        numeric_type=generated_entity.numeric_type,
                        reference=None,
                        generated=generated_entity,
                        profile=profile,
                    )
                )

    if alignment_ambiguous:
        findings.append(
            _finding(
                finding_type=ASRCriticalNumberFindingType.AMBIGUITY,
                reason_code=(
                    ASRCriticalNumberReasonCode.CONTEXT_ALIGNMENT_AMBIGUOUS
                ),
                numeric_type=ASRCriticalNumberType.UNKNOWN,
                reference=reference[0] if reference else None,
                generated=generated[0] if generated else None,
                profile=profile,
            )
        )

    finding_tuple = tuple(findings)
    outcome = _derive_outcome(
        reference=reference,
        generated=generated,
        findings=finding_tuple,
    )

    return ASRCriticalNumberFidelityEvaluation(
        profile_key=profile.key,
        profile_version=profile.version,
        evaluator_key=CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        evaluator_version=CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        outcome=outcome,
        reference_entities=reference,
        generated_entities=generated,
        findings=finding_tuple,
    )


def _observation(
    *,
    metric: MetricDefinition,
    value: object | None,
    status: ObservationStatus = ObservationStatus.SUCCESS,
    status_detail: str | None = None,
) -> Observation:
    return Observation(
        metric_key=metric.key,
        metric_version=metric.version,
        evaluator_key=CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        evaluator_version=CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        evaluation_type=ASR_EVALUATION_TYPE,
        status=status,
        value_type=metric.value_type,
        value=value,
        status_detail=status_detail,
    )


def build_critical_number_fidelity_observations(
    evaluation: ASRCriticalNumberFidelityEvaluation,
) -> tuple[Observation, ...]:
    if not isinstance(evaluation, ASRCriticalNumberFidelityEvaluation):
        raise HveeContractError(
            "critical-number observations require "
            "ASRCriticalNumberFidelityEvaluation"
        )
    if (
        evaluation.profile_key != EN_US_CRITICAL_NUMBER_PROFILE.key
        or evaluation.profile_version != EN_US_CRITICAL_NUMBER_PROFILE.version
        or evaluation.evaluator_key != CRITICAL_NUMBER_FIDELITY_EVALUATOR.key
        or evaluation.evaluator_version
        != CRITICAL_NUMBER_FIDELITY_EVALUATOR.version
    ):
        raise HveeContractError(
            "critical-number observations require en-US evaluator v1.0.0"
        )

    if any(
        entity.issue_reason_code is not None
        for entity in (
            *evaluation.reference_entities,
            *evaluation.generated_entities,
        )
    ):
        raise HveeContractError(
            "critical-number conclusive entity collections cannot contain "
            "uncertain evidence"
        )
    if any(
        finding.profile_key != evaluation.profile_key
        or finding.profile_version != evaluation.profile_version
        for finding in evaluation.findings
    ):
        raise HveeContractError(
            "critical-number findings must retain profile provenance"
        )
    aligned_reference_count = len(
        {
            finding.reference
            for finding in evaluation.findings
            if finding.reference in evaluation.reference_entities
        }
    )
    aligned_generated_count = len(
        {
            finding.generated
            for finding in evaluation.findings
            if finding.generated in evaluation.generated_entities
        }
    )
    if aligned_reference_count != len(evaluation.reference_entities) or (
        aligned_generated_count != len(evaluation.generated_entities)
    ):
        raise HveeContractError(
            "critical-number findings must account for every conclusive entity"
        )
    derived_outcome = _derive_outcome(
        reference=evaluation.reference_entities,
        generated=evaluation.generated_entities,
        findings=evaluation.findings,
    )
    if evaluation.outcome != derived_outcome:
        raise HveeContractError(
            "critical-number outcome is inconsistent with its evidence"
        )

    if evaluation.outcome == ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE:
        preserved_status = ObservationStatus.ABSTAINED
        preserved_detail = (
            "no supported or uncertain critical-number evidence was present"
        )
    elif evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
    ):
        has_unsupported = any(
            finding.finding_type == ASRCriticalNumberFindingType.UNSUPPORTED
            for finding in evaluation.findings
        )
        preserved_status = (
            ObservationStatus.UNSUPPORTED
            if has_unsupported
            else ObservationStatus.ABSTAINED
        )
        preserved_detail = (
            "critical-number fidelity is inconclusive because evidence "
            + ("is unsupported" if has_unsupported else "is ambiguous")
        )
    else:
        preserved_status = ObservationStatus.SUCCESS
        preserved_detail = None

    preserved_observation = _observation(
        metric=CRITICAL_NUMBER_PRESERVED_METRIC,
        value=(
            evaluation.preserved
            if preserved_status == ObservationStatus.SUCCESS
            else None
        ),
        status=preserved_status,
        status_detail=preserved_detail,
    )

    return (
        _observation(
            metric=CRITICAL_NUMBER_APPLICABLE_METRIC,
            value=evaluation.applicable,
        ),
        preserved_observation,
        _observation(
            metric=CRITICAL_NUMBER_OUTCOME_METRIC,
            value=evaluation.outcome.value,
        ),
        _observation(
            metric=CRITICAL_NUMBER_REFERENCE_COUNT_METRIC,
            value=len(evaluation.reference_entities),
        ),
        _observation(
            metric=CRITICAL_NUMBER_GENERATED_COUNT_METRIC,
            value=len(evaluation.generated_entities),
        ),
        _observation(
            metric=CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC,
            value=evaluation.substitution_count,
        ),
        _observation(
            metric=CRITICAL_NUMBER_OMISSION_COUNT_METRIC,
            value=evaluation.omission_count,
        ),
        _observation(
            metric=CRITICAL_NUMBER_INSERTION_COUNT_METRIC,
            value=evaluation.insertion_count,
        ),
        _observation(
            metric=CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC,
            value=evaluation.ambiguity_count,
        ),
        _observation(
            metric=CRITICAL_NUMBER_FINDINGS_METRIC,
            value=[finding.to_json() for finding in evaluation.findings],
        ),
    )
