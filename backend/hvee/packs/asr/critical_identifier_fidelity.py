"""Conservative deterministic critical-identifier fidelity for US English ASR.

The evaluator makes transcript-grounded claims only. Critical identifiers are
recognized only when introduced by an explicitly supported cue. Version 1
supports compact ASCII alphanumeric identifiers, hyphen-separated compact
forms, and sequences of individually spaced symbols.

It intentionally does not perform fuzzy matching, phonetic interpretation,
NATO/spoken-alphabet conversion, arbitrary named-entity recognition, or
audio-grounded inference.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
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


CRITICAL_IDENTIFIER_METRIC_VERSION = "1.0.0"
CRITICAL_IDENTIFIER_EVALUATOR_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierProfile:
    key: str
    version: str
    language: str
    locale: str
    description: str


EN_US_CRITICAL_IDENTIFIER_PROFILE = ASRCriticalIdentifierProfile(
    key="hetren.asr.critical-identifier-profile.en-us",
    version="1.0.0",
    language="en",
    locale="en-US",
    description=(
        "Conservative US English cue-bound identifier interpretation "
        "for confirmation codes, reference IDs, ticket IDs, case IDs, "
        "order IDs, account IDs, serial numbers, and booking references."
    ),
)


class ASRCriticalIdentifierType(StrEnum):
    CONFIRMATION_CODE = "confirmation_code"
    REFERENCE_ID = "reference_id"
    TICKET_ID = "ticket_id"
    CASE_ID = "case_id"
    ORDER_ID = "order_id"
    ACCOUNT_ID = "account_id"
    SERIAL_NUMBER = "serial_number"
    BOOKING_REFERENCE = "booking_reference"


class ASRCriticalIdentifierFindingType(StrEnum):
    MATCH = "match"
    SUBSTITUTION = "substitution"
    OMISSION = "omission"
    INSERTION = "insertion"
    ORDERING_CHANGE = "ordering_change"
    AMBIGUITY = "ambiguity"
    UNSUPPORTED = "unsupported"


class ASRCriticalIdentifierReasonCode(StrEnum):
    EXACT_MATCH = "exact_match"
    FORMAT_EQUIVALENT = "format_equivalent"
    VALUE_SUBSTITUTION = "value_substitution"
    REFERENCE_IDENTIFIER_OMITTED = "reference_identifier_omitted"
    GENERATED_IDENTIFIER_INSERTED = "generated_identifier_inserted"
    IDENTIFIER_ORDER_CHANGED = "identifier_order_changed"
    REFERENCE_SURFACE_UNSUPPORTED = "reference_surface_unsupported"
    GENERATED_SURFACE_UNSUPPORTED = "generated_surface_unsupported"
    REFERENCE_EXTRACTION_AMBIGUOUS = "reference_extraction_ambiguous"
    GENERATED_EXTRACTION_AMBIGUOUS = "generated_extraction_ambiguous"


class ASRCriticalIdentifierFidelityOutcome(StrEnum):
    PRESERVED = "preserved"
    NOT_PRESERVED = "not_preserved"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierEntity:
    identifier_type: ASRCriticalIdentifierType
    cue: str
    text: str
    span_start: int
    span_end: int
    canonical_value: str
    issue_reason_code: ASRCriticalIdentifierReasonCode | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "identifier_type": self.identifier_type.value,
            "cue": self.cue,
            "text": self.text,
            "span": [self.span_start, self.span_end],
            "canonical_value": self.canonical_value,
            "issue_reason_code": (
                self.issue_reason_code.value
                if self.issue_reason_code is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierFinding:
    finding_type: ASRCriticalIdentifierFindingType
    reason_code: ASRCriticalIdentifierReasonCode
    identifier_type: ASRCriticalIdentifierType
    reference: ASRCriticalIdentifierEntity | None
    generated: ASRCriticalIdentifierEntity | None
    profile_key: str
    profile_version: str

    def to_json(self) -> dict[str, object]:
        return {
            "finding_type": self.finding_type.value,
            "reason_code": self.reason_code.value,
            "identifier_type": self.identifier_type.value,
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
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
        }


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierFidelityEvaluation:
    profile_key: str
    profile_version: str
    evaluator_key: str
    evaluator_version: str
    outcome: ASRCriticalIdentifierFidelityOutcome
    reference_entities: tuple[ASRCriticalIdentifierEntity, ...]
    generated_entities: tuple[ASRCriticalIdentifierEntity, ...]
    findings: tuple[ASRCriticalIdentifierFinding, ...]

    @property
    def applicable(self) -> bool:
        return self.outcome != (
            ASRCriticalIdentifierFidelityOutcome.NOT_APPLICABLE
        )

    @property
    def preserved(self) -> bool | None:
        if self.outcome == (
            ASRCriticalIdentifierFidelityOutcome.PRESERVED
        ):
            return True
        if self.outcome == (
            ASRCriticalIdentifierFidelityOutcome.NOT_PRESERVED
        ):
            return False
        return None

    def _count(
        self,
        finding_type: ASRCriticalIdentifierFindingType,
    ) -> int:
        return sum(
            finding.finding_type == finding_type
            for finding in self.findings
        )

    @property
    def substitution_count(self) -> int:
        return self._count(
            ASRCriticalIdentifierFindingType.SUBSTITUTION
        )

    @property
    def omission_count(self) -> int:
        return self._count(
            ASRCriticalIdentifierFindingType.OMISSION
        )

    @property
    def insertion_count(self) -> int:
        return self._count(
            ASRCriticalIdentifierFindingType.INSERTION
        )

    @property
    def ordering_change_count(self) -> int:
        return self._count(
            ASRCriticalIdentifierFindingType.ORDERING_CHANGE
        )

    @property
    def ambiguity_count(self) -> int:
        return self._count(
            ASRCriticalIdentifierFindingType.AMBIGUITY
        )


CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.critical-identifier-fidelity.en-us",
    version=CRITICAL_IDENTIFIER_EVALUATOR_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    description=(
        "Deterministic US English ASR evaluator for preservation of "
        "explicitly cue-bound critical identifier symbol sequences."
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
        version=CRITICAL_IDENTIFIER_METRIC_VERSION,
        evaluation_type=ASR_EVALUATION_TYPE,
        value_type=value_type,
        direction=direction,
        description=description,
        unit=unit,
    )


CRITICAL_IDENTIFIER_APPLICABLE_METRIC = _metric(
    key="asr.critical-identifier.applicable.en-us",
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "Whether either transcript contains supported or uncertain "
        "cue-bound critical-identifier evidence."
    ),
)

CRITICAL_IDENTIFIER_PRESERVED_METRIC = _metric(
    key="asr.critical-identifier.preserved.en-us",
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.HIGHER_IS_BETTER,
    description=(
        "Whether all conclusive cue-bound critical identifiers are preserved."
    ),
)

CRITICAL_IDENTIFIER_OUTCOME_METRIC = _metric(
    key="asr.critical-identifier.outcome.en-us",
    value_type=MetricValueType.STRING,
    direction=MetricDirection.INFORMATIONAL,
    description="Versioned critical-identifier fidelity outcome.",
)

CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC = _metric(
    key="asr.critical-identifier.reference-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.INFORMATIONAL,
    unit="count",
    description="Count of conclusively extracted reference identifiers.",
)

CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC = _metric(
    key="asr.critical-identifier.generated-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.INFORMATIONAL,
    unit="count",
    description="Count of conclusively extracted generated identifiers.",
)

CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC = _metric(
    key="asr.critical-identifier.substitution-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description="Count of proven critical-identifier substitutions.",
)

CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC = _metric(
    key="asr.critical-identifier.omission-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description="Count of proven critical-identifier omissions.",
)

CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC = _metric(
    key="asr.critical-identifier.insertion-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description="Count of proven critical-identifier insertions.",
)

CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC = _metric(
    key="asr.critical-identifier.ordering-change-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Count of proven ordered identifier-sequence changes."
    ),
)

CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC = _metric(
    key="asr.critical-identifier.ambiguity-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description="Count of explicit critical-identifier ambiguities.",
)

CRITICAL_IDENTIFIER_FINDINGS_METRIC = _metric(
    key="asr.critical-identifier.findings.en-us",
    value_type=MetricValueType.JSON,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "Auditable cue-bound identifier findings with canonical values, "
        "source spans, profile provenance, and stable reason codes."
    ),
)


CRITICAL_IDENTIFIER_METRICS = (
    CRITICAL_IDENTIFIER_APPLICABLE_METRIC,
    CRITICAL_IDENTIFIER_PRESERVED_METRIC,
    CRITICAL_IDENTIFIER_OUTCOME_METRIC,
    CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC,
    CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC,
    CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_IDENTIFIER_FINDINGS_METRIC,
)


_CUE_SPECS = (
    ("confirmation code", ASRCriticalIdentifierType.CONFIRMATION_CODE),
    ("booking reference", ASRCriticalIdentifierType.BOOKING_REFERENCE),
    ("serial number", ASRCriticalIdentifierType.SERIAL_NUMBER),
    ("reference id", ASRCriticalIdentifierType.REFERENCE_ID),
    ("ticket id", ASRCriticalIdentifierType.TICKET_ID),
    ("account id", ASRCriticalIdentifierType.ACCOUNT_ID),
    ("order id", ASRCriticalIdentifierType.ORDER_ID),
    ("case id", ASRCriticalIdentifierType.CASE_ID),
)

_CUE_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(
        re.escape(cue).replace(r"\ ", r"[ \t]+")
        for cue, _ in _CUE_SPECS
    )
    + r")\b",
    re.IGNORECASE,
)

_CUE_TYPES = {
    cue: identifier_type
    for cue, identifier_type in _CUE_SPECS
}

_SPACED_SYMBOL_PATTERN = re.compile(
    r"[A-Za-z0-9](?![A-Za-z0-9])"
    r"(?:[ 	]+[A-Za-z0-9](?![A-Za-z0-9])){1,31}"
)

_COMPACT_IDENTIFIER_PATTERN = re.compile(
    r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
)

_FIRST_WORD_PATTERN = re.compile(r"[A-Za-z]+")

_ALT_SEPARATOR_PATTERN = re.compile(
    r"[ \t]*(?:/|\bor\b)[ \t]*",
    re.IGNORECASE,
)

_SPOKEN_SYMBOL_WORDS = frozenset(
    {
        "alpha",
        "bravo",
        "charlie",
        "delta",
        "echo",
        "foxtrot",
        "golf",
        "hotel",
        "india",
        "juliett",
        "juliet",
        "kilo",
        "lima",
        "mike",
        "november",
        "oscar",
        "papa",
        "quebec",
        "romeo",
        "sierra",
        "tango",
        "uniform",
        "victor",
        "whiskey",
        "xray",
        "yankee",
        "zulu",
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "double",
        "triple",
    }
)


def _normalize_cue(value: str) -> str:
    return " ".join(value.lower().split())


def _canonical_identifier(value: str) -> str:
    return re.sub(r"[- \t]", "", value).upper()


def _skip_introducer(text: str, position: int) -> int:
    while position < len(text) and text[position] in " \t":
        position += 1

    if position < len(text) and text[position] in ":#":
        position += 1
        while position < len(text) and text[position] in " \t":
            position += 1

    match = re.match(r"is\b", text[position:], re.IGNORECASE)
    if match is not None:
        position += match.end()
        while position < len(text) and text[position] in " \t":
            position += 1

    return position


def _parse_supported_surface(
    text: str,
    position: int,
) -> tuple[str, int] | None:
    spaced = _SPACED_SYMBOL_PATTERN.match(text, position)
    if spaced is not None:
        value = spaced.group(0)
        canonical = _canonical_identifier(value)
        if 2 <= len(canonical) <= 32:
            return value, spaced.end()

    compact = _COMPACT_IDENTIFIER_PATTERN.match(text, position)
    if compact is None:
        return None

    value = compact.group(0)
    canonical = _canonical_identifier(value)

    if not 2 <= len(canonical) <= 32:
        return None

    return value, compact.end()


def _unsupported_malformed_hyphen_surface_end(
    text: str,
    surface_end: int,
) -> int | None:
    """
    Detect malformed hyphen continuations unsupported by v1.

    The supported compact grammar permits hyphens only between
    non-empty alphanumeric groups. Surfaces such as ``AB--12``,
    ``AB-``, and ``AB- 12`` must not be silently truncated to
    ``AB``.
    """

    if (
        surface_end >= len(text)
        or text[surface_end] != "-"
    ):
        return None

    position = surface_end

    while (
        position < len(text)
        and text[position] == "-"
    ):
        position += 1

    while (
        position < len(text)
        and text[position] in " \t"
    ):
        position += 1

    continuation = _COMPACT_IDENTIFIER_PATTERN.match(
        text,
        position,
    )

    if continuation is not None:
        return continuation.end()

    return max(
        surface_end + 1,
        position,
    )


def _unsupported_grouped_surface_end(
    text: str,
    surface_end: int,
) -> int | None:
    """
    Detect grouped identifier continuations unsupported by v1.

    Examples such as ``QF 2841`` and ``AB7K 92`` must not be
    silently truncated to the first compact group.

    Ordinary following prose such as ``93BZK was created`` is not
    considered part of the identifier.
    """

    if (
        surface_end >= len(text)
        or text[surface_end] not in " \t"
    ):
        return None

    position = surface_end

    while (
        position < len(text)
        and text[position] in " \t"
    ):
        position += 1

    following = _COMPACT_IDENTIFIER_PATTERN.match(
        text,
        position,
    )
    if following is None:
        return None

    value = following.group(0)

    if (
        any(
            character.isdigit()
            for character in value
        )
        or len(value) == 1
    ):
        return following.end()

    return None


def _issue_entity(
    *,
    identifier_type: ASRCriticalIdentifierType,
    cue: str,
    text: str,
    span_start: int,
    span_end: int,
    reason_code: ASRCriticalIdentifierReasonCode,
) -> ASRCriticalIdentifierEntity:
    return ASRCriticalIdentifierEntity(
        identifier_type=identifier_type,
        cue=cue,
        text=text,
        span_start=span_start,
        span_end=span_end,
        canonical_value="",
        issue_reason_code=reason_code,
    )


def _extract_identifier_evidence(
    text: str,
    *,
    reference_side: bool,
) -> tuple[
    tuple[ASRCriticalIdentifierEntity, ...],
    tuple[ASRCriticalIdentifierEntity, ...],
]:
    if not isinstance(text, str):
        raise HveeContractError(
            "critical-identifier extraction requires a string"
        )

    conclusive: list[ASRCriticalIdentifierEntity] = []
    uncertain: list[ASRCriticalIdentifierEntity] = []

    unsupported_reason = (
        ASRCriticalIdentifierReasonCode.REFERENCE_SURFACE_UNSUPPORTED
        if reference_side
        else ASRCriticalIdentifierReasonCode.GENERATED_SURFACE_UNSUPPORTED
    )
    ambiguity_reason = (
        ASRCriticalIdentifierReasonCode.REFERENCE_EXTRACTION_AMBIGUOUS
        if reference_side
        else ASRCriticalIdentifierReasonCode.GENERATED_EXTRACTION_AMBIGUOUS
    )

    for cue_match in _CUE_PATTERN.finditer(text):
        cue = cue_match.group(0)
        normalized_cue = _normalize_cue(cue)
        identifier_type = _CUE_TYPES[normalized_cue]
        surface_start = _skip_introducer(
            text,
            cue_match.end(),
        )

        first_word = _FIRST_WORD_PATTERN.match(
            text,
            surface_start,
        )
        if (
            first_word is not None
            and first_word.group(0).lower()
            in _SPOKEN_SYMBOL_WORDS
        ):
            uncertain.append(
                _issue_entity(
                    identifier_type=identifier_type,
                    cue=cue,
                    text=first_word.group(0),
                    span_start=first_word.start(),
                    span_end=first_word.end(),
                    reason_code=unsupported_reason,
                )
            )
            continue

        parsed = _parse_supported_surface(
            text,
            surface_start,
        )
        if parsed is None:
            end = surface_start
            while (
                end < len(text)
                and not text[end].isspace()
                and text[end] not in ".,;!?"
            ):
                end += 1
            uncertain.append(
                _issue_entity(
                    identifier_type=identifier_type,
                    cue=cue,
                    text=text[surface_start:end],
                    span_start=surface_start,
                    span_end=end,
                    reason_code=unsupported_reason,
                )
            )
            continue

        surface, surface_end = parsed

        malformed_hyphen_end = (
            _unsupported_malformed_hyphen_surface_end(
                text,
                surface_end,
            )
        )
        if malformed_hyphen_end is not None:
            uncertain.append(
                _issue_entity(
                    identifier_type=identifier_type,
                    cue=cue,
                    text=text[
                        surface_start:malformed_hyphen_end
                    ],
                    span_start=surface_start,
                    span_end=malformed_hyphen_end,
                    reason_code=unsupported_reason,
                )
            )
            continue

        grouped_surface_end = (
            _unsupported_grouped_surface_end(
                text,
                surface_end,
            )
        )
        if grouped_surface_end is not None:
            uncertain.append(
                _issue_entity(
                    identifier_type=identifier_type,
                    cue=cue,
                    text=text[
                        surface_start:grouped_surface_end
                    ],
                    span_start=surface_start,
                    span_end=grouped_surface_end,
                    reason_code=unsupported_reason,
                )
            )
            continue

        alternative = _ALT_SEPARATOR_PATTERN.match(
            text,
            surface_end,
        )
        if alternative is not None:
            alternate = _parse_supported_surface(
                text,
                alternative.end(),
            )
            if alternate is not None:
                _, alternate_end = alternate
                uncertain.append(
                    _issue_entity(
                        identifier_type=identifier_type,
                        cue=cue,
                        text=text[surface_start:alternate_end],
                        span_start=surface_start,
                        span_end=alternate_end,
                        reason_code=ambiguity_reason,
                    )
                )
                continue

        if (
            surface_end < len(text)
            and text[surface_end] in "_/"
        ):
            end = surface_end + 1
            while (
                end < len(text)
                and (
                    text[end].isalnum()
                    or text[end] in "_/-"
                )
            ):
                end += 1
            uncertain.append(
                _issue_entity(
                    identifier_type=identifier_type,
                    cue=cue,
                    text=text[surface_start:end],
                    span_start=surface_start,
                    span_end=end,
                    reason_code=unsupported_reason,
                )
            )
            continue

        conclusive.append(
            ASRCriticalIdentifierEntity(
                identifier_type=identifier_type,
                cue=cue,
                text=surface,
                span_start=surface_start,
                span_end=surface_end,
                canonical_value=_canonical_identifier(
                    surface
                ),
            )
        )

    return tuple(conclusive), tuple(uncertain)


def extract_critical_identifier_entities(
    text: str,
    *,
    profile: ASRCriticalIdentifierProfile,
) -> tuple[ASRCriticalIdentifierEntity, ...]:
    """Extract all supported and uncertain cue-bound identifier evidence."""

    if profile != EN_US_CRITICAL_IDENTIFIER_PROFILE:
        raise HveeContractError(
            "critical-identifier extraction requires the exact "
            "en-US profile v1.0.0"
        )

    conclusive, uncertain = _extract_identifier_evidence(
        text,
        reference_side=True,
    )

    return tuple(
        sorted(
            (*conclusive, *uncertain),
            key=lambda entity: (
                entity.span_start,
                entity.span_end,
            ),
        )
    )


def _finding(
    *,
    finding_type: ASRCriticalIdentifierFindingType,
    reason_code: ASRCriticalIdentifierReasonCode,
    identifier_type: ASRCriticalIdentifierType,
    reference: ASRCriticalIdentifierEntity | None,
    generated: ASRCriticalIdentifierEntity | None,
    profile: ASRCriticalIdentifierProfile,
) -> ASRCriticalIdentifierFinding:
    return ASRCriticalIdentifierFinding(
        finding_type=finding_type,
        reason_code=reason_code,
        identifier_type=identifier_type,
        reference=reference,
        generated=generated,
        profile_key=profile.key,
        profile_version=profile.version,
    )


def _edit_script(
    reference: tuple[ASRCriticalIdentifierEntity, ...],
    generated: tuple[ASRCriticalIdentifierEntity, ...],
) -> tuple[tuple[str, int | None, int | None], ...]:
    rows = len(reference) + 1
    columns = len(generated) + 1

    cost = [
        [0 for _ in range(columns)]
        for _ in range(rows)
    ]

    for i in range(1, rows):
        cost[i][0] = i
    for j in range(1, columns):
        cost[0][j] = j

    for i in range(1, rows):
        for j in range(1, columns):
            ref = reference[i - 1]
            gen = generated[j - 1]

            if (
                ref.identifier_type == gen.identifier_type
                and ref.canonical_value == gen.canonical_value
            ):
                substitution_cost = 0
            elif ref.identifier_type == gen.identifier_type:
                substitution_cost = 1
            else:
                substitution_cost = 3

            cost[i][j] = min(
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
                cost[i - 1][j - 1] + substitution_cost,
            )

    operations: list[
        tuple[str, int | None, int | None]
    ] = []

    i = len(reference)
    j = len(generated)

    while i > 0 or j > 0:
        if i > 0 and j > 0:
            ref = reference[i - 1]
            gen = generated[j - 1]

            if (
                ref.identifier_type == gen.identifier_type
                and ref.canonical_value == gen.canonical_value
                and cost[i][j] == cost[i - 1][j - 1]
            ):
                operations.append(("match", i - 1, j - 1))
                i -= 1
                j -= 1
                continue

            if (
                ref.identifier_type == gen.identifier_type
                and cost[i][j]
                == cost[i - 1][j - 1] + 1
            ):
                operations.append(
                    ("substitution", i - 1, j - 1)
                )
                i -= 1
                j -= 1
                continue

        if (
            i > 0
            and cost[i][j] == cost[i - 1][j] + 1
        ):
            operations.append(("omission", i - 1, None))
            i -= 1
            continue

        if (
            j > 0
            and cost[i][j] == cost[i][j - 1] + 1
        ):
            operations.append(("insertion", None, j - 1))
            j -= 1
            continue

        raise HveeContractError(
            "critical-identifier alignment could not be reconstructed"
        )

    operations.reverse()
    return tuple(operations)


def _align_conclusive_entities(
    *,
    reference: tuple[ASRCriticalIdentifierEntity, ...],
    generated: tuple[ASRCriticalIdentifierEntity, ...],
    reference_uncertain: tuple[ASRCriticalIdentifierEntity, ...],
    generated_uncertain: tuple[ASRCriticalIdentifierEntity, ...],
    profile: ASRCriticalIdentifierProfile,
) -> tuple[ASRCriticalIdentifierFinding, ...]:
    uncertain_types = {
        entity.identifier_type
        for entity in (
            *reference_uncertain,
            *generated_uncertain,
        )
    }

    safe_reference = tuple(
        entity
        for entity in reference
        if entity.identifier_type not in uncertain_types
    )
    safe_generated = tuple(
        entity
        for entity in generated
        if entity.identifier_type not in uncertain_types
    )

    reference_identity = tuple(
        (
            entity.identifier_type,
            entity.canonical_value,
        )
        for entity in safe_reference
    )
    generated_identity = tuple(
        (
            entity.identifier_type,
            entity.canonical_value,
        )
        for entity in safe_generated
    )

    if (
        len(reference_identity) > 1
        and len(reference_identity) == len(generated_identity)
        and reference_identity != generated_identity
        and Counter(reference_identity)
        == Counter(generated_identity)
    ):
        first_difference = next(
            index
            for index, pair
            in enumerate(
                zip(
                    reference_identity,
                    generated_identity,
                    strict=True,
                )
            )
            if pair[0] != pair[1]
        )
        ref = safe_reference[first_difference]
        gen = safe_generated[first_difference]
        return (
            _finding(
                finding_type=(
                    ASRCriticalIdentifierFindingType.ORDERING_CHANGE
                ),
                reason_code=(
                    ASRCriticalIdentifierReasonCode
                    .IDENTIFIER_ORDER_CHANGED
                ),
                identifier_type=ref.identifier_type,
                reference=ref,
                generated=gen,
                profile=profile,
            ),
        )

    findings: list[ASRCriticalIdentifierFinding] = []

    for operation, reference_index, generated_index in _edit_script(
        safe_reference,
        safe_generated,
    ):
        ref = (
            safe_reference[reference_index]
            if reference_index is not None
            else None
        )
        gen = (
            safe_generated[generated_index]
            if generated_index is not None
            else None
        )

        if operation == "match":
            assert ref is not None
            assert gen is not None
            reason = (
                ASRCriticalIdentifierReasonCode.EXACT_MATCH
                if ref.text == gen.text
                else (
                    ASRCriticalIdentifierReasonCode
                    .FORMAT_EQUIVALENT
                )
            )
            findings.append(
                _finding(
                    finding_type=(
                        ASRCriticalIdentifierFindingType.MATCH
                    ),
                    reason_code=reason,
                    identifier_type=ref.identifier_type,
                    reference=ref,
                    generated=gen,
                    profile=profile,
                )
            )
            continue

        if operation == "substitution":
            assert ref is not None
            assert gen is not None
            findings.append(
                _finding(
                    finding_type=(
                        ASRCriticalIdentifierFindingType.SUBSTITUTION
                    ),
                    reason_code=(
                        ASRCriticalIdentifierReasonCode
                        .VALUE_SUBSTITUTION
                    ),
                    identifier_type=ref.identifier_type,
                    reference=ref,
                    generated=gen,
                    profile=profile,
                )
            )
            continue

        if operation == "omission":
            assert ref is not None
            findings.append(
                _finding(
                    finding_type=(
                        ASRCriticalIdentifierFindingType.OMISSION
                    ),
                    reason_code=(
                        ASRCriticalIdentifierReasonCode
                        .REFERENCE_IDENTIFIER_OMITTED
                    ),
                    identifier_type=ref.identifier_type,
                    reference=ref,
                    generated=None,
                    profile=profile,
                )
            )
            continue

        assert operation == "insertion"
        assert gen is not None
        findings.append(
            _finding(
                finding_type=(
                    ASRCriticalIdentifierFindingType.INSERTION
                ),
                reason_code=(
                    ASRCriticalIdentifierReasonCode
                    .GENERATED_IDENTIFIER_INSERTED
                ),
                identifier_type=gen.identifier_type,
                reference=None,
                generated=gen,
                profile=profile,
            )
        )

    return tuple(findings)


def _uncertain_findings(
    *,
    reference_uncertain: tuple[ASRCriticalIdentifierEntity, ...],
    generated_uncertain: tuple[ASRCriticalIdentifierEntity, ...],
    profile: ASRCriticalIdentifierProfile,
) -> tuple[ASRCriticalIdentifierFinding, ...]:
    findings: list[ASRCriticalIdentifierFinding] = []

    for entity in reference_uncertain:
        assert entity.issue_reason_code is not None
        findings.append(
            _finding(
                finding_type=(
                    ASRCriticalIdentifierFindingType.AMBIGUITY
                    if entity.issue_reason_code
                    == (
                        ASRCriticalIdentifierReasonCode
                        .REFERENCE_EXTRACTION_AMBIGUOUS
                    )
                    else ASRCriticalIdentifierFindingType.UNSUPPORTED
                ),
                reason_code=entity.issue_reason_code,
                identifier_type=entity.identifier_type,
                reference=entity,
                generated=None,
                profile=profile,
            )
        )

    for entity in generated_uncertain:
        assert entity.issue_reason_code is not None
        findings.append(
            _finding(
                finding_type=(
                    ASRCriticalIdentifierFindingType.AMBIGUITY
                    if entity.issue_reason_code
                    == (
                        ASRCriticalIdentifierReasonCode
                        .GENERATED_EXTRACTION_AMBIGUOUS
                    )
                    else ASRCriticalIdentifierFindingType.UNSUPPORTED
                ),
                reason_code=entity.issue_reason_code,
                identifier_type=entity.identifier_type,
                reference=None,
                generated=entity,
                profile=profile,
            )
        )

    return tuple(findings)


def _derive_outcome(
    *,
    reference: tuple[ASRCriticalIdentifierEntity, ...],
    generated: tuple[ASRCriticalIdentifierEntity, ...],
    findings: tuple[ASRCriticalIdentifierFinding, ...],
) -> ASRCriticalIdentifierFidelityOutcome:
    error_types = {
        ASRCriticalIdentifierFindingType.SUBSTITUTION,
        ASRCriticalIdentifierFindingType.OMISSION,
        ASRCriticalIdentifierFindingType.INSERTION,
        ASRCriticalIdentifierFindingType.ORDERING_CHANGE,
    }

    if any(
        finding.finding_type in error_types
        for finding in findings
    ):
        return ASRCriticalIdentifierFidelityOutcome.NOT_PRESERVED

    if any(
        finding.finding_type
        in {
            ASRCriticalIdentifierFindingType.AMBIGUITY,
            ASRCriticalIdentifierFindingType.UNSUPPORTED,
        }
        for finding in findings
    ):
        return (
            ASRCriticalIdentifierFidelityOutcome.INSUFFICIENT_EVIDENCE
        )

    if not reference and not generated:
        return ASRCriticalIdentifierFidelityOutcome.NOT_APPLICABLE

    return ASRCriticalIdentifierFidelityOutcome.PRESERVED


def evaluate_critical_identifier_fidelity(
    *,
    reference_text: str,
    generated_text: str,
    profile: ASRCriticalIdentifierProfile,
) -> ASRCriticalIdentifierFidelityEvaluation:
    """Evaluate exact cue-bound critical-identifier preservation."""

    if not isinstance(reference_text, str) or not isinstance(
        generated_text,
        str,
    ):
        raise HveeContractError(
            "critical-identifier evaluation requires string transcripts"
        )

    if profile != EN_US_CRITICAL_IDENTIFIER_PROFILE:
        raise HveeContractError(
            "critical-identifier evaluation requires the exact "
            "en-US profile v1.0.0"
        )

    reference, reference_uncertain = (
        _extract_identifier_evidence(
            reference_text,
            reference_side=True,
        )
    )
    generated, generated_uncertain = (
        _extract_identifier_evidence(
            generated_text,
            reference_side=False,
        )
    )

    findings = (
        *_align_conclusive_entities(
            reference=reference,
            generated=generated,
            reference_uncertain=reference_uncertain,
            generated_uncertain=generated_uncertain,
            profile=profile,
        ),
        *_uncertain_findings(
            reference_uncertain=reference_uncertain,
            generated_uncertain=generated_uncertain,
            profile=profile,
        ),
    )
    finding_tuple = tuple(findings)

    return ASRCriticalIdentifierFidelityEvaluation(
        profile_key=profile.key,
        profile_version=profile.version,
        evaluator_key=CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.key,
        evaluator_version=CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.version,
        outcome=_derive_outcome(
            reference=reference,
            generated=generated,
            findings=finding_tuple,
        ),
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
        evaluator_key=CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.key,
        evaluator_version=CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.version,
        evaluation_type=ASR_EVALUATION_TYPE,
        status=status,
        value_type=metric.value_type,
        value=value,
        status_detail=status_detail,
    )


def build_critical_identifier_fidelity_observations(
    evaluation: ASRCriticalIdentifierFidelityEvaluation,
) -> tuple[Observation, ...]:
    """Build versioned HVEE observations from one identifier evaluation."""

    if not isinstance(
        evaluation,
        ASRCriticalIdentifierFidelityEvaluation,
    ):
        raise HveeContractError(
            "critical-identifier observations require "
            "ASRCriticalIdentifierFidelityEvaluation"
        )

    if (
        evaluation.profile_key
        != EN_US_CRITICAL_IDENTIFIER_PROFILE.key
        or evaluation.profile_version
        != EN_US_CRITICAL_IDENTIFIER_PROFILE.version
        or evaluation.evaluator_key
        != CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.key
        or evaluation.evaluator_version
        != CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.version
    ):
        raise HveeContractError(
            "critical-identifier observations require "
            "en-US evaluator v1.0.0"
        )

    if any(
        entity.issue_reason_code is not None
        for entity in (
            *evaluation.reference_entities,
            *evaluation.generated_entities,
        )
    ):
        raise HveeContractError(
            "critical-identifier conclusive entity collections "
            "cannot contain uncertain evidence"
        )

    if any(
        finding.profile_key != evaluation.profile_key
        or finding.profile_version != evaluation.profile_version
        for finding in evaluation.findings
    ):
        raise HveeContractError(
            "critical-identifier findings must retain profile provenance"
        )

    expected_outcome = _derive_outcome(
        reference=evaluation.reference_entities,
        generated=evaluation.generated_entities,
        findings=evaluation.findings,
    )
    if evaluation.outcome != expected_outcome:
        raise HveeContractError(
            "critical-identifier outcome is inconsistent with findings"
        )

    if evaluation.outcome in {
        ASRCriticalIdentifierFidelityOutcome.PRESERVED,
        ASRCriticalIdentifierFidelityOutcome.NOT_PRESERVED,
    }:
        preserved_status = ObservationStatus.SUCCESS
        preserved_value = evaluation.preserved
        preserved_detail = None
    else:
        preserved_status = ObservationStatus.ABSTAINED
        preserved_value = None
        preserved_detail = evaluation.outcome.value

    return (
        _observation(
            metric=CRITICAL_IDENTIFIER_APPLICABLE_METRIC,
            value=evaluation.applicable,
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_PRESERVED_METRIC,
            value=preserved_value,
            status=preserved_status,
            status_detail=preserved_detail,
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_OUTCOME_METRIC,
            value=evaluation.outcome.value,
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC,
            value=len(evaluation.reference_entities),
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC,
            value=len(evaluation.generated_entities),
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC,
            value=evaluation.substitution_count,
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC,
            value=evaluation.omission_count,
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC,
            value=evaluation.insertion_count,
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC,
            value=evaluation.ordering_change_count,
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC,
            value=evaluation.ambiguity_count,
        ),
        _observation(
            metric=CRITICAL_IDENTIFIER_FINDINGS_METRIC,
            value=[
                finding.to_json()
                for finding in evaluation.findings
            ],
        ),
    )
