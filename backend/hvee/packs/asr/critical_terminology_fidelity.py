"""Critical Terminology Fidelity v1 for US English ASR transcripts.

This evaluator measures preservation of an explicitly supplied, versioned
critical-term vocabulary.

The evaluator is intentionally deterministic and transcript-grounded. It
does not perform fuzzy matching, phonetic matching, embedding similarity,
automatic alias generation, language-model inference, or external knowledge
lookup.

A term is preserved only when the generated transcript contains a surface
form explicitly accepted by the supplied vocabulary profile.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import re
import unicodedata

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


CRITICAL_TERMINOLOGY_METRIC_VERSION = "1.0.0"
CRITICAL_TERMINOLOGY_EVALUATOR_VERSION = "1.0.0"
CRITICAL_TERMINOLOGY_PROFILE_SCHEMA_VERSION = 1


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _require_identifier(
    *,
    name: str,
    value: str,
) -> None:
    if (
        not isinstance(value, str)
        or not _IDENTIFIER_PATTERN.fullmatch(value)
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )


def _require_version(
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
            f"{name} must be a non-empty version string"
        )


def _normalize_term_surface(
    value: str,
) -> str:
    """
    Normalize registered terminology conservatively.

    Unicode NFKC, case folding, and whitespace collapsing are allowed.
    Punctuation and symbols remain semantically significant. Fuzzy matching,
    phonetic rewriting, transliteration, and automatic alias generation are
    intentionally excluded from v1.
    """

    if not isinstance(value, str):
        raise HveeContractError(
            "critical terminology surface must be a string"
        )

    normalized = unicodedata.normalize(
        "NFKC",
        value,
    ).casefold()

    return " ".join(
        normalized.split()
    )


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyTerm:
    """One stable critical concept and its explicitly accepted surfaces."""

    term_key: str
    canonical_text: str
    accepted_surfaces: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier(
            name="critical terminology term key",
            value=self.term_key,
        )

        if (
            not isinstance(self.canonical_text, str)
            or not self.canonical_text
            or self.canonical_text != self.canonical_text.strip()
        ):
            raise HveeContractError(
                "critical terminology canonical text "
                "must be a non-empty trimmed string"
            )

        if (
            not isinstance(self.accepted_surfaces, tuple)
            or not self.accepted_surfaces
        ):
            raise HveeContractError(
                "critical terminology term requires "
                "accepted surfaces"
            )

        normalized_surfaces: list[str] = []

        for surface in self.accepted_surfaces:
            if (
                not isinstance(surface, str)
                or not surface
                or surface != surface.strip()
            ):
                raise HveeContractError(
                    "critical terminology accepted surfaces "
                    "must be non-empty trimmed strings"
                )

            normalized = _normalize_term_surface(
                surface
            )

            if not normalized:
                raise HveeContractError(
                    "critical terminology accepted surface "
                    "cannot normalize to empty"
                )

            normalized_surfaces.append(
                normalized
            )

        if len(normalized_surfaces) != len(
            set(normalized_surfaces)
        ):
            raise HveeContractError(
                "critical terminology accepted surfaces "
                "must be unique after normalization"
            )

        canonical_normalized = (
            _normalize_term_surface(
                self.canonical_text
            )
        )

        if canonical_normalized not in set(
            normalized_surfaces
        ):
            raise HveeContractError(
                "critical terminology canonical text "
                "must be an accepted surface"
            )

    def to_json(self) -> dict[str, object]:
        return {
            "term_key": self.term_key,
            "canonical_text": self.canonical_text,
            "accepted_surfaces": list(
                self.accepted_surfaces
            ),
        }


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyProfile:
    """Versioned vocabulary used by Critical Terminology Fidelity v1."""

    key: str
    version: str
    language: str
    locale: str
    terms: tuple[
        ASRCriticalTerminologyTerm,
        ...,
    ]

    def __post_init__(self) -> None:
        _require_identifier(
            name="critical terminology profile key",
            value=self.key,
        )
        _require_version(
            name="critical terminology profile version",
            value=self.version,
        )

        if self.language != "en":
            raise HveeContractError(
                "critical terminology v1 requires language en"
            )

        if self.locale != "en-US":
            raise HveeContractError(
                "critical terminology v1 requires locale en-US"
            )

        if (
            not isinstance(self.terms, tuple)
            or not self.terms
            or not all(
                isinstance(
                    term,
                    ASRCriticalTerminologyTerm,
                )
                for term in self.terms
            )
        ):
            raise HveeContractError(
                "critical terminology profile "
                "requires terms"
            )

        term_keys = tuple(
            term.term_key
            for term in self.terms
        )

        if len(term_keys) != len(
            set(term_keys)
        ):
            raise HveeContractError(
                "critical terminology term keys "
                "must be unique"
            )

        surface_owners: dict[str, str] = {}

        for term in self.terms:
            for surface in term.accepted_surfaces:
                normalized = (
                    _normalize_term_surface(
                        surface
                    )
                )

                owner = surface_owners.get(
                    normalized
                )

                if (
                    owner is not None
                    and owner != term.term_key
                ):
                    raise HveeContractError(
                        "critical terminology normalized "
                        "surface cannot map to multiple terms"
                    )

                surface_owners[
                    normalized
                ] = term.term_key


def calculate_critical_terminology_vocabulary_sha256(
    profile: ASRCriticalTerminologyProfile,
) -> str:
    """Calculate deterministic vocabulary identity for audit provenance."""

    if not isinstance(
        profile,
        ASRCriticalTerminologyProfile,
    ):
        raise HveeContractError(
            "critical terminology vocabulary hash "
            "requires a profile"
        )

    payload = {
        "schema_version": (
            CRITICAL_TERMINOLOGY_PROFILE_SCHEMA_VERSION
        ),
        "profile": {
            "key": profile.key,
            "version": profile.version,
            "language": profile.language,
            "locale": profile.locale,
        },
        "terms": [
            {
                "term_key": term.term_key,
                "canonical_text": (
                    term.canonical_text
                ),
                "accepted_surfaces": sorted(
                    term.accepted_surfaces
                ),
            }
            for term in sorted(
                profile.terms,
                key=lambda item: item.term_key,
            )
        ],
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(
        serialized
    ).hexdigest()


class ASRCriticalTerminologyFindingType(StrEnum):
    MATCH = "match"
    SUBSTITUTION = "substitution"
    OMISSION = "omission"
    INSERTION = "insertion"
    ORDERING_CHANGE = "ordering_change"


class ASRCriticalTerminologyReasonCode(StrEnum):
    EXACT_SURFACE_MATCH = "exact_surface_match"
    ACCEPTED_ALIAS_EQUIVALENT = "accepted_alias_equivalent"
    TERM_SUBSTITUTION = "term_substitution"
    REFERENCE_TERM_OMITTED = "reference_term_omitted"
    GENERATED_TERM_INSERTED = "generated_term_inserted"
    TERM_ORDER_CHANGED = "term_order_changed"


class ASRCriticalTerminologyFidelityOutcome(StrEnum):
    PRESERVED = "preserved"
    NOT_PRESERVED = "not_preserved"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyEntity:
    term_key: str
    canonical_text: str
    text: str
    normalized_surface: str
    span_start: int
    span_end: int

    def __post_init__(self) -> None:
        _require_identifier(
            name="critical terminology entity term key",
            value=self.term_key,
        )

        if (
            not isinstance(self.canonical_text, str)
            or not self.canonical_text
        ):
            raise HveeContractError(
                "critical terminology entity requires "
                "canonical text"
            )

        if not isinstance(self.text, str):
            raise HveeContractError(
                "critical terminology entity text "
                "must be a string"
            )

        if (
            not isinstance(self.normalized_surface, str)
            or not self.normalized_surface
        ):
            raise HveeContractError(
                "critical terminology entity requires "
                "a normalized surface"
            )

        for name, value in (
            ("span start", self.span_start),
            ("span end", self.span_end),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise HveeContractError(
                    f"critical terminology {name} "
                    "must be a non-negative integer"
                )

        if self.span_end <= self.span_start:
            raise HveeContractError(
                "critical terminology entity span "
                "must be non-empty"
            )

    def to_json(self) -> dict[str, object]:
        return {
            "term_key": self.term_key,
            "canonical_text": self.canonical_text,
            "text": self.text,
            "normalized_surface": (
                self.normalized_surface
            ),
            "span": [
                self.span_start,
                self.span_end,
            ],
        }


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyFinding:
    finding_type: ASRCriticalTerminologyFindingType
    reason_code: ASRCriticalTerminologyReasonCode
    reference: ASRCriticalTerminologyEntity | None
    generated: ASRCriticalTerminologyEntity | None
    profile_key: str
    profile_version: str
    vocabulary_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.finding_type,
            ASRCriticalTerminologyFindingType,
        ):
            raise HveeContractError(
                "critical terminology finding "
                "requires a finding type"
            )

        if not isinstance(
            self.reason_code,
            ASRCriticalTerminologyReasonCode,
        ):
            raise HveeContractError(
                "critical terminology finding "
                "requires a reason code"
            )

        if (
            self.reference is None
            and self.generated is None
        ):
            raise HveeContractError(
                "critical terminology finding "
                "requires evidence"
            )

        paired_types = {
            ASRCriticalTerminologyFindingType.MATCH,
            ASRCriticalTerminologyFindingType.SUBSTITUTION,
            ASRCriticalTerminologyFindingType.ORDERING_CHANGE,
        }

        if self.finding_type in paired_types:
            if (
                self.reference is None
                or self.generated is None
            ):
                raise HveeContractError(
                    "paired critical terminology finding "
                    "requires reference and generated evidence"
                )

        elif self.finding_type == (
            ASRCriticalTerminologyFindingType.OMISSION
        ):
            if (
                self.reference is None
                or self.generated is not None
            ):
                raise HveeContractError(
                    "critical terminology omission requires "
                    "reference-only evidence"
                )

        elif self.finding_type == (
            ASRCriticalTerminologyFindingType.INSERTION
        ):
            if (
                self.reference is not None
                or self.generated is None
            ):
                raise HveeContractError(
                    "critical terminology insertion requires "
                    "generated-only evidence"
                )

        expected_reason_codes = {
            ASRCriticalTerminologyFindingType.MATCH: {
                ASRCriticalTerminologyReasonCode.EXACT_SURFACE_MATCH,
                (
                    ASRCriticalTerminologyReasonCode
                    .ACCEPTED_ALIAS_EQUIVALENT
                ),
            },
            ASRCriticalTerminologyFindingType.SUBSTITUTION: {
                ASRCriticalTerminologyReasonCode.TERM_SUBSTITUTION,
            },
            ASRCriticalTerminologyFindingType.OMISSION: {
                ASRCriticalTerminologyReasonCode.REFERENCE_TERM_OMITTED,
            },
            ASRCriticalTerminologyFindingType.INSERTION: {
                ASRCriticalTerminologyReasonCode.GENERATED_TERM_INSERTED,
            },
            ASRCriticalTerminologyFindingType.ORDERING_CHANGE: {
                ASRCriticalTerminologyReasonCode.TERM_ORDER_CHANGED,
            },
        }

        if self.reason_code not in expected_reason_codes[
            self.finding_type
        ]:
            raise HveeContractError(
                "critical terminology finding reason code "
                "is inconsistent with its finding type"
            )

        _require_identifier(
            name="critical terminology finding profile key",
            value=self.profile_key,
        )
        _require_version(
            name="critical terminology finding profile version",
            value=self.profile_version,
        )

        if not _SHA256_PATTERN.fullmatch(
            self.vocabulary_sha256
        ):
            raise HveeContractError(
                "critical terminology finding requires "
                "a canonical vocabulary SHA-256"
            )

    def to_json(self) -> dict[str, object]:
        return {
            "finding_type": self.finding_type.value,
            "reason_code": self.reason_code.value,
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
            "vocabulary_sha256": self.vocabulary_sha256,
        }


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyFidelityEvaluation:
    profile_key: str
    profile_version: str
    vocabulary_sha256: str
    evaluator_key: str
    evaluator_version: str
    outcome: ASRCriticalTerminologyFidelityOutcome
    reference_entities: tuple[
        ASRCriticalTerminologyEntity,
        ...,
    ]
    generated_entities: tuple[
        ASRCriticalTerminologyEntity,
        ...,
    ]
    findings: tuple[
        ASRCriticalTerminologyFinding,
        ...,
    ]

    @property
    def applicable(self) -> bool:
        return self.outcome != (
            ASRCriticalTerminologyFidelityOutcome
            .NOT_APPLICABLE
        )

    @property
    def preserved(self) -> bool | None:
        if self.outcome == (
            ASRCriticalTerminologyFidelityOutcome.PRESERVED
        ):
            return True

        if self.outcome == (
            ASRCriticalTerminologyFidelityOutcome.NOT_PRESERVED
        ):
            return False

        return None

    def _count(
        self,
        finding_type: ASRCriticalTerminologyFindingType,
    ) -> int:
        return sum(
            finding.finding_type == finding_type
            for finding in self.findings
        )

    @property
    def substitution_count(self) -> int:
        return self._count(
            ASRCriticalTerminologyFindingType.SUBSTITUTION
        )

    @property
    def omission_count(self) -> int:
        return self._count(
            ASRCriticalTerminologyFindingType.OMISSION
        )

    @property
    def insertion_count(self) -> int:
        return self._count(
            ASRCriticalTerminologyFindingType.INSERTION
        )

    @property
    def ordering_change_count(self) -> int:
        return self._count(
            ASRCriticalTerminologyFindingType.ORDERING_CHANGE
        )


CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.critical-terminology-fidelity.en-us",
    version=CRITICAL_TERMINOLOGY_EVALUATOR_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    description=(
        "Deterministic US English ASR evaluator for preservation "
        "of explicitly registered critical terminology."
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
        version=CRITICAL_TERMINOLOGY_METRIC_VERSION,
        evaluation_type=ASR_EVALUATION_TYPE,
        value_type=value_type,
        direction=direction,
        description=description,
        unit=unit,
    )


CRITICAL_TERMINOLOGY_APPLICABLE_METRIC = _metric(
    key="asr.critical-terminology.applicable.en-us",
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "Whether either transcript contains a term "
        "registered by the supplied critical vocabulary."
    ),
)

CRITICAL_TERMINOLOGY_PRESERVED_METRIC = _metric(
    key="asr.critical-terminology.preserved.en-us",
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.HIGHER_IS_BETTER,
    description=(
        "Whether all extracted critical terminology "
        "is preserved."
    ),
)

CRITICAL_TERMINOLOGY_OUTCOME_METRIC = _metric(
    key="asr.critical-terminology.outcome.en-us",
    value_type=MetricValueType.STRING,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "Versioned critical-terminology fidelity outcome."
    ),
)

CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC = _metric(
    key="asr.critical-terminology.vocabulary-sha256.en-us",
    value_type=MetricValueType.STRING,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "SHA-256 identity of the exact critical-term "
        "vocabulary used by the evaluation."
    ),
)

CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC = _metric(
    key="asr.critical-terminology.reference-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.INFORMATIONAL,
    unit="count",
    description=(
        "Count of critical terms extracted "
        "from the reference transcript."
    ),
)

CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC = _metric(
    key="asr.critical-terminology.generated-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.INFORMATIONAL,
    unit="count",
    description=(
        "Count of critical terms extracted "
        "from the generated transcript."
    ),
)

CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC = _metric(
    key="asr.critical-terminology.substitution-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Count of proven substitutions between "
        "registered critical terms."
    ),
)

CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC = _metric(
    key="asr.critical-terminology.omission-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Count of reference critical terms omitted "
        "from the generated transcript."
    ),
)

CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC = _metric(
    key="asr.critical-terminology.insertion-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Count of generated critical terms absent "
        "from the reference transcript."
    ),
)

CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC = _metric(
    key="asr.critical-terminology.ordering-change-count.en-us",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Count of proven ordered critical-term "
        "sequence changes."
    ),
)

CRITICAL_TERMINOLOGY_FINDINGS_METRIC = _metric(
    key="asr.critical-terminology.findings.en-us",
    value_type=MetricValueType.JSON,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "Auditable critical-terminology findings "
        "with source spans and vocabulary provenance."
    ),
)


CRITICAL_TERMINOLOGY_METRICS = (
    CRITICAL_TERMINOLOGY_APPLICABLE_METRIC,
    CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
    CRITICAL_TERMINOLOGY_OUTCOME_METRIC,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
    CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_FINDINGS_METRIC,
)


@dataclass(frozen=True, slots=True)
class _NormalizedTranscript:
    text: str
    source_spans: tuple[
        tuple[int, int],
        ...,
    ]


def _normalization_clusters(
    text: str,
) -> tuple[
    tuple[str, int, int],
    ...,
]:
    """
    Group a base code point with following combining marks.

    This lets NFKC operate across common decomposed Unicode sequences while
    retaining a deterministic source span for every normalized character.
    """

    if not text:
        return ()

    clusters: list[
        tuple[str, int, int]
    ] = []

    start = 0

    for index in range(1, len(text)):
        if unicodedata.combining(
            text[index]
        ) == 0:
            clusters.append(
                (
                    text[start:index],
                    start,
                    index,
                )
            )
            start = index

    clusters.append(
        (
            text[start:],
            start,
            len(text),
        )
    )

    return tuple(
        clusters
    )


def _normalize_transcript_with_span_map(
    text: str,
) -> _NormalizedTranscript:
    """
    Apply NFKC, case folding, and whitespace collapse with source provenance.

    Punctuation and symbols remain significant. Normalized characters retain
    the complete source span of the Unicode cluster that produced them.
    """

    normalized: list[str] = []
    source_spans: list[
        tuple[int, int]
    ] = []

    for (
        cluster,
        source_start,
        source_end,
    ) in _normalization_clusters(
        text
    ):
        folded = unicodedata.normalize(
            "NFKC",
            cluster,
        ).casefold()

        for folded_character in folded:
            if folded_character.isspace():
                if (
                    normalized
                    and normalized[-1] != " "
                ):
                    normalized.append(" ")
                    source_spans.append(
                        (
                            source_start,
                            source_end,
                        )
                    )
                continue

            normalized.append(
                folded_character
            )
            source_spans.append(
                (
                    source_start,
                    source_end,
                )
            )

    if normalized and normalized[-1] == " ":
        normalized.pop()
        source_spans.pop()

    return _NormalizedTranscript(
        text="".join(normalized),
        source_spans=tuple(
            source_spans
        ),
    )


def _source_span(
    *,
    original_text: str,
    normalized: _NormalizedTranscript,
    start: int,
    end: int,
) -> tuple[int, int]:
    if (
        start < 0
        or end <= start
        or end > len(normalized.source_spans)
    ):
        raise HveeContractError(
            "critical terminology normalized span "
            "is invalid"
        )

    source_start = (
        normalized.source_spans[start][0]
    )
    source_end = (
        normalized.source_spans[end - 1][1]
    )

    if (
        source_start < 0
        or source_end > len(original_text)
        or source_end <= source_start
    ):
        raise HveeContractError(
            "critical terminology source span "
            "could not be reconstructed"
        )

    return source_start, source_end


def _word_character(
    value: str,
) -> bool:
    return value.isalnum() or value == "_"


def _has_term_boundaries(
    *,
    text: str,
    start: int,
    end: int,
) -> bool:
    if (
        start > 0
        and _word_character(text[start - 1])
    ):
        return False

    if (
        end < len(text)
        and _word_character(text[end])
    ):
        return False

    return True


@dataclass(frozen=True, slots=True)
class _Candidate:
    start: int
    end: int
    term: ASRCriticalTerminologyTerm
    normalized_surface: str


def _candidate_matches(
    *,
    normalized_text: str,
    profile: ASRCriticalTerminologyProfile,
) -> tuple[_Candidate, ...]:
    candidates: list[_Candidate] = []

    for term in profile.terms:
        for surface in term.accepted_surfaces:
            normalized_surface = (
                _normalize_term_surface(
                    surface
                )
            )

            position = 0

            while True:
                start = normalized_text.find(
                    normalized_surface,
                    position,
                )

                if start < 0:
                    break

                end = (
                    start
                    + len(normalized_surface)
                )

                if _has_term_boundaries(
                    text=normalized_text,
                    start=start,
                    end=end,
                ):
                    candidates.append(
                        _Candidate(
                            start=start,
                            end=end,
                            term=term,
                            normalized_surface=(
                                normalized_surface
                            ),
                        )
                    )

                position = start + 1

    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.start,
                -(
                    candidate.end
                    - candidate.start
                ),
                candidate.term.term_key,
                candidate.normalized_surface,
            ),
        )
    )


def extract_critical_terminology_entities(
    text: str,
    *,
    profile: ASRCriticalTerminologyProfile,
) -> tuple[ASRCriticalTerminologyEntity, ...]:
    """
    Extract registered critical terms using deterministic longest-first spans.

    At each left-most candidate start, the longest registered surface wins.
    Selected entities cannot overlap.
    """

    if not isinstance(text, str):
        raise HveeContractError(
            "critical terminology extraction "
            "requires a string"
        )

    if not isinstance(
        profile,
        ASRCriticalTerminologyProfile,
    ):
        raise HveeContractError(
            "critical terminology extraction "
            "requires a profile"
        )

    normalized = (
        _normalize_transcript_with_span_map(
            text
        )
    )

    candidates = _candidate_matches(
        normalized_text=normalized.text,
        profile=profile,
    )

    selected: list[_Candidate] = []
    cursor = 0

    for candidate in candidates:
        if candidate.start < cursor:
            continue

        same_start = tuple(
            item
            for item in candidates
            if item.start == candidate.start
            and item.start >= cursor
        )

        chosen = max(
            same_start,
            key=lambda item: (
                item.end - item.start,
                item.term.term_key,
                item.normalized_surface,
            ),
        )

        if (
            selected
            and chosen.start
            < selected[-1].end
        ):
            continue

        selected.append(
            chosen
        )
        cursor = chosen.end

    entities: list[
        ASRCriticalTerminologyEntity
    ] = []

    seen_spans: set[
        tuple[int, int]
    ] = set()

    for candidate in selected:
        span_key = (
            candidate.start,
            candidate.end,
        )

        if span_key in seen_spans:
            continue

        seen_spans.add(
            span_key
        )

        source_start, source_end = (
            _source_span(
                original_text=text,
                normalized=normalized,
                start=candidate.start,
                end=candidate.end,
            )
        )

        entities.append(
            ASRCriticalTerminologyEntity(
                term_key=(
                    candidate.term.term_key
                ),
                canonical_text=(
                    candidate.term.canonical_text
                ),
                text=text[
                    source_start:source_end
                ],
                normalized_surface=(
                    candidate.normalized_surface
                ),
                span_start=source_start,
                span_end=source_end,
            )
        )

    return tuple(
        entities
    )


def _finding(
    *,
    finding_type: ASRCriticalTerminologyFindingType,
    reason_code: ASRCriticalTerminologyReasonCode,
    reference: ASRCriticalTerminologyEntity | None,
    generated: ASRCriticalTerminologyEntity | None,
    profile: ASRCriticalTerminologyProfile,
    vocabulary_sha256: str,
) -> ASRCriticalTerminologyFinding:
    return ASRCriticalTerminologyFinding(
        finding_type=finding_type,
        reason_code=reason_code,
        reference=reference,
        generated=generated,
        profile_key=profile.key,
        profile_version=profile.version,
        vocabulary_sha256=vocabulary_sha256,
    )


def _edit_script(
    reference: tuple[
        ASRCriticalTerminologyEntity,
        ...,
    ],
    generated: tuple[
        ASRCriticalTerminologyEntity,
        ...,
    ],
) -> tuple[
    tuple[str, int | None, int | None],
    ...,
]:
    rows = len(reference) + 1
    columns = len(generated) + 1

    cost = [
        [
            0
            for _ in range(columns)
        ]
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

            substitution_cost = (
                0
                if ref.term_key == gen.term_key
                else 1
            )

            cost[i][j] = min(
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
                (
                    cost[i - 1][j - 1]
                    + substitution_cost
                ),
            )

    operations: list[
        tuple[
            str,
            int | None,
            int | None,
        ]
    ] = []

    i = len(reference)
    j = len(generated)

    while i > 0 or j > 0:
        if i > 0 and j > 0:
            ref = reference[i - 1]
            gen = generated[j - 1]

            if (
                ref.term_key == gen.term_key
                and cost[i][j]
                == cost[i - 1][j - 1]
            ):
                operations.append(
                    ("match", i - 1, j - 1)
                )
                i -= 1
                j -= 1
                continue

            if (
                ref.term_key != gen.term_key
                and cost[i][j]
                == cost[i - 1][j - 1] + 1
            ):
                operations.append(
                    (
                        "substitution",
                        i - 1,
                        j - 1,
                    )
                )
                i -= 1
                j -= 1
                continue

        if (
            i > 0
            and cost[i][j]
            == cost[i - 1][j] + 1
        ):
            operations.append(
                ("omission", i - 1, None)
            )
            i -= 1
            continue

        if (
            j > 0
            and cost[i][j]
            == cost[i][j - 1] + 1
        ):
            operations.append(
                ("insertion", None, j - 1)
            )
            j -= 1
            continue

        raise HveeContractError(
            "critical terminology alignment "
            "could not be reconstructed"
        )

    operations.reverse()
    return tuple(
        operations
    )


def _align_entities(
    *,
    reference: tuple[
        ASRCriticalTerminologyEntity,
        ...,
    ],
    generated: tuple[
        ASRCriticalTerminologyEntity,
        ...,
    ],
    profile: ASRCriticalTerminologyProfile,
    vocabulary_sha256: str,
) -> tuple[
    ASRCriticalTerminologyFinding,
    ...,
]:
    reference_identity = tuple(
        entity.term_key
        for entity in reference
    )
    generated_identity = tuple(
        entity.term_key
        for entity in generated
    )

    if (
        len(reference_identity) > 1
        and len(reference_identity)
        == len(generated_identity)
        and reference_identity
        != generated_identity
        and Counter(reference_identity)
        == Counter(generated_identity)
    ):
        first_difference = next(
            index
            for index, pair in enumerate(
                zip(
                    reference,
                    generated,
                    strict=True,
                )
            )
            if pair[0].term_key
            != pair[1].term_key
        )

        return (
            _finding(
                finding_type=(
                    ASRCriticalTerminologyFindingType
                    .ORDERING_CHANGE
                ),
                reason_code=(
                    ASRCriticalTerminologyReasonCode
                    .TERM_ORDER_CHANGED
                ),
                reference=(
                    reference[
                        first_difference
                    ]
                ),
                generated=(
                    generated[
                        first_difference
                    ]
                ),
                profile=profile,
                vocabulary_sha256=(
                    vocabulary_sha256
                ),
            ),
        )

    findings: list[
        ASRCriticalTerminologyFinding
    ] = []

    for (
        operation,
        reference_index,
        generated_index,
    ) in _edit_script(
        reference,
        generated,
    ):
        ref = (
            reference[reference_index]
            if reference_index is not None
            else None
        )

        gen = (
            generated[generated_index]
            if generated_index is not None
            else None
        )

        if operation == "match":
            assert ref is not None
            assert gen is not None

            reason_code = (
                ASRCriticalTerminologyReasonCode
                .EXACT_SURFACE_MATCH
                if ref.normalized_surface
                == gen.normalized_surface
                else (
                    ASRCriticalTerminologyReasonCode
                    .ACCEPTED_ALIAS_EQUIVALENT
                )
            )

            findings.append(
                _finding(
                    finding_type=(
                        ASRCriticalTerminologyFindingType
                        .MATCH
                    ),
                    reason_code=reason_code,
                    reference=ref,
                    generated=gen,
                    profile=profile,
                    vocabulary_sha256=(
                        vocabulary_sha256
                    ),
                )
            )
            continue

        if operation == "substitution":
            assert ref is not None
            assert gen is not None

            findings.append(
                _finding(
                    finding_type=(
                        ASRCriticalTerminologyFindingType
                        .SUBSTITUTION
                    ),
                    reason_code=(
                        ASRCriticalTerminologyReasonCode
                        .TERM_SUBSTITUTION
                    ),
                    reference=ref,
                    generated=gen,
                    profile=profile,
                    vocabulary_sha256=(
                        vocabulary_sha256
                    ),
                )
            )
            continue

        if operation == "omission":
            assert ref is not None

            findings.append(
                _finding(
                    finding_type=(
                        ASRCriticalTerminologyFindingType
                        .OMISSION
                    ),
                    reason_code=(
                        ASRCriticalTerminologyReasonCode
                        .REFERENCE_TERM_OMITTED
                    ),
                    reference=ref,
                    generated=None,
                    profile=profile,
                    vocabulary_sha256=(
                        vocabulary_sha256
                    ),
                )
            )
            continue

        assert operation == "insertion"
        assert gen is not None

        findings.append(
            _finding(
                finding_type=(
                    ASRCriticalTerminologyFindingType
                    .INSERTION
                ),
                reason_code=(
                    ASRCriticalTerminologyReasonCode
                    .GENERATED_TERM_INSERTED
                ),
                reference=None,
                generated=gen,
                profile=profile,
                vocabulary_sha256=(
                    vocabulary_sha256
                ),
            )
        )

    return tuple(
        findings
    )


def _derive_outcome(
    *,
    reference: tuple[
        ASRCriticalTerminologyEntity,
        ...,
    ],
    generated: tuple[
        ASRCriticalTerminologyEntity,
        ...,
    ],
    findings: tuple[
        ASRCriticalTerminologyFinding,
        ...,
    ],
) -> ASRCriticalTerminologyFidelityOutcome:
    error_types = {
        ASRCriticalTerminologyFindingType.SUBSTITUTION,
        ASRCriticalTerminologyFindingType.OMISSION,
        ASRCriticalTerminologyFindingType.INSERTION,
        (
            ASRCriticalTerminologyFindingType
            .ORDERING_CHANGE
        ),
    }

    if any(
        finding.finding_type in error_types
        for finding in findings
    ):
        return (
            ASRCriticalTerminologyFidelityOutcome
            .NOT_PRESERVED
        )

    if not reference and not generated:
        return (
            ASRCriticalTerminologyFidelityOutcome
            .NOT_APPLICABLE
        )

    return (
        ASRCriticalTerminologyFidelityOutcome
        .PRESERVED
    )


def evaluate_critical_terminology_fidelity(
    *,
    reference_text: str,
    generated_text: str,
    profile: ASRCriticalTerminologyProfile,
) -> ASRCriticalTerminologyFidelityEvaluation:
    """Evaluate preservation of an explicit critical-term vocabulary."""

    if (
        not isinstance(reference_text, str)
        or not isinstance(generated_text, str)
    ):
        raise HveeContractError(
            "critical terminology evaluation "
            "requires string transcripts"
        )

    if not isinstance(
        profile,
        ASRCriticalTerminologyProfile,
    ):
        raise HveeContractError(
            "critical terminology evaluation "
            "requires a profile"
        )

    vocabulary_sha256 = (
        calculate_critical_terminology_vocabulary_sha256(
            profile
        )
    )

    reference = (
        extract_critical_terminology_entities(
            reference_text,
            profile=profile,
        )
    )

    generated = (
        extract_critical_terminology_entities(
            generated_text,
            profile=profile,
        )
    )

    findings = _align_entities(
        reference=reference,
        generated=generated,
        profile=profile,
        vocabulary_sha256=(
            vocabulary_sha256
        ),
    )

    return (
        ASRCriticalTerminologyFidelityEvaluation(
            profile_key=profile.key,
            profile_version=profile.version,
            vocabulary_sha256=(
                vocabulary_sha256
            ),
            evaluator_key=(
                CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR.key
            ),
            evaluator_version=(
                CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR.version
            ),
            outcome=_derive_outcome(
                reference=reference,
                generated=generated,
                findings=findings,
            ),
            reference_entities=reference,
            generated_entities=generated,
            findings=findings,
        )
    )


def _validate_evaluation_profile_binding(
    *,
    evaluation: ASRCriticalTerminologyFidelityEvaluation,
    profile: ASRCriticalTerminologyProfile,
) -> None:
    """Require the evaluation to bind the exact supplied vocabulary."""

    if not isinstance(
        profile,
        ASRCriticalTerminologyProfile,
    ):
        raise HveeContractError(
            "critical terminology observations "
            "require a vocabulary profile"
        )

    expected_sha256 = (
        calculate_critical_terminology_vocabulary_sha256(
            profile
        )
    )

    if (
        evaluation.profile_key != profile.key
        or evaluation.profile_version != profile.version
        or evaluation.vocabulary_sha256
        != expected_sha256
    ):
        raise HveeContractError(
            "critical terminology evaluation does not "
            "bind the exact vocabulary profile"
        )

    terms_by_key = {
        term.term_key: term
        for term in profile.terms
    }

    for entity in (
        *evaluation.reference_entities,
        *evaluation.generated_entities,
    ):
        term = terms_by_key.get(
            entity.term_key
        )

        if term is None:
            raise HveeContractError(
                "critical terminology evaluation contains "
                "an entity absent from its vocabulary"
            )

        accepted_surfaces = {
            _normalize_term_surface(surface)
            for surface in term.accepted_surfaces
        }

        if (
            entity.canonical_text
            != term.canonical_text
            or entity.normalized_surface
            not in accepted_surfaces
            or _normalize_term_surface(
                entity.text
            )
            != entity.normalized_surface
        ):
            raise HveeContractError(
                "critical terminology entity does not "
                "match its bound vocabulary definition"
            )

    for finding in evaluation.findings:
        if (
            finding.reference is not None
            and finding.reference
            not in evaluation.reference_entities
        ):
            raise HveeContractError(
                "critical terminology finding reference "
                "is not part of the evaluation evidence"
            )

        if (
            finding.generated is not None
            and finding.generated
            not in evaluation.generated_entities
        ):
            raise HveeContractError(
                "critical terminology finding generated "
                "entity is not part of the evaluation evidence"
            )


def _validate_evaluation_evidence_integrity(
    evaluation: ASRCriticalTerminologyFidelityEvaluation,
) -> None:
    """Require findings to exactly explain the extracted terminology."""

    ordering_findings = tuple(
        finding
        for finding in evaluation.findings
        if finding.finding_type
        == ASRCriticalTerminologyFindingType.ORDERING_CHANGE
    )

    reference_identity = tuple(
        entity.term_key
        for entity in evaluation.reference_entities
    )
    generated_identity = tuple(
        entity.term_key
        for entity in evaluation.generated_entities
    )

    if ordering_findings:
        if (
            len(evaluation.findings) != 1
            or len(ordering_findings) != 1
            or len(reference_identity) <= 1
            or len(reference_identity)
            != len(generated_identity)
            or reference_identity
            == generated_identity
            or Counter(reference_identity)
            != Counter(generated_identity)
        ):
            raise HveeContractError(
                "critical terminology ordering change requires "
                "the same reordered critical-term multiset"
            )

        ordering = ordering_findings[0]

        assert ordering.reference is not None
        assert ordering.generated is not None

        if (
            ordering.reference.term_key
            == ordering.generated.term_key
        ):
            raise HveeContractError(
                "critical terminology ordering-change evidence "
                "must identify a changed position"
            )

        return

    accounted_reference: list[
        ASRCriticalTerminologyEntity
    ] = []
    accounted_generated: list[
        ASRCriticalTerminologyEntity
    ] = []

    for finding in evaluation.findings:
        reference = finding.reference
        generated = finding.generated

        if finding.finding_type == (
            ASRCriticalTerminologyFindingType.MATCH
        ):
            assert reference is not None
            assert generated is not None

            if (
                reference.term_key
                != generated.term_key
            ):
                raise HveeContractError(
                    "critical terminology match must "
                    "preserve term identity"
                )

            expected_reason = (
                ASRCriticalTerminologyReasonCode
                .EXACT_SURFACE_MATCH
                if reference.normalized_surface
                == generated.normalized_surface
                else (
                    ASRCriticalTerminologyReasonCode
                    .ACCEPTED_ALIAS_EQUIVALENT
                )
            )

            if finding.reason_code != expected_reason:
                raise HveeContractError(
                    "critical terminology match reason "
                    "is inconsistent with its surfaces"
                )

        elif finding.finding_type == (
            ASRCriticalTerminologyFindingType.SUBSTITUTION
        ):
            assert reference is not None
            assert generated is not None

            if (
                reference.term_key
                == generated.term_key
            ):
                raise HveeContractError(
                    "critical terminology substitution "
                    "requires distinct term identities"
                )

        if reference is not None:
            accounted_reference.append(
                reference
            )

        if generated is not None:
            accounted_generated.append(
                generated
            )

    if (
        Counter(accounted_reference)
        != Counter(
            evaluation.reference_entities
        )
        or Counter(accounted_generated)
        != Counter(
            evaluation.generated_entities
        )
    ):
        raise HveeContractError(
            "critical terminology findings must account "
            "for every extracted entity exactly once"
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
        evaluator_key=(
            CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR.key
        ),
        evaluator_version=(
            CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR.version
        ),
        evaluation_type=ASR_EVALUATION_TYPE,
        status=status,
        value_type=metric.value_type,
        value=value,
        status_detail=status_detail,
    )


def build_critical_terminology_fidelity_observations(
    evaluation: ASRCriticalTerminologyFidelityEvaluation,
    *,
    profile: ASRCriticalTerminologyProfile,
) -> tuple[Observation, ...]:
    """Build versioned HVEE observations from one terminology evaluation."""

    if not isinstance(
        evaluation,
        ASRCriticalTerminologyFidelityEvaluation,
    ):
        raise HveeContractError(
            "critical terminology observations require "
            "ASRCriticalTerminologyFidelityEvaluation"
        )

    _validate_evaluation_profile_binding(
        evaluation=evaluation,
        profile=profile,
    )

    if (
        evaluation.evaluator_key
        != CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR.key
        or evaluation.evaluator_version
        != CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR.version
    ):
        raise HveeContractError(
            "critical terminology observations require "
            "evaluator v1.0.0"
        )

    _require_identifier(
        name="critical terminology evaluation profile key",
        value=evaluation.profile_key,
    )
    _require_version(
        name="critical terminology evaluation profile version",
        value=evaluation.profile_version,
    )

    if not _SHA256_PATTERN.fullmatch(
        evaluation.vocabulary_sha256
    ):
        raise HveeContractError(
            "critical terminology evaluation requires "
            "a canonical vocabulary SHA-256"
        )

    if any(
        (
            finding.profile_key
            != evaluation.profile_key
            or finding.profile_version
            != evaluation.profile_version
            or finding.vocabulary_sha256
            != evaluation.vocabulary_sha256
        )
        for finding in evaluation.findings
    ):
        raise HveeContractError(
            "critical terminology findings must "
            "retain vocabulary provenance"
        )

    _validate_evaluation_evidence_integrity(
        evaluation
    )

    expected_outcome = _derive_outcome(
        reference=evaluation.reference_entities,
        generated=evaluation.generated_entities,
        findings=evaluation.findings,
    )

    if evaluation.outcome != expected_outcome:
        raise HveeContractError(
            "critical terminology outcome is "
            "inconsistent with findings"
        )

    if evaluation.outcome in {
        ASRCriticalTerminologyFidelityOutcome.PRESERVED,
        (
            ASRCriticalTerminologyFidelityOutcome
            .NOT_PRESERVED
        ),
    }:
        preserved_status = (
            ObservationStatus.SUCCESS
        )
        preserved_value = evaluation.preserved
        preserved_detail = None
    else:
        preserved_status = (
            ObservationStatus.ABSTAINED
        )
        preserved_value = None
        preserved_detail = (
            evaluation.outcome.value
        )

    return (
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_APPLICABLE_METRIC
            ),
            value=evaluation.applicable,
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_PRESERVED_METRIC
            ),
            value=preserved_value,
            status=preserved_status,
            status_detail=preserved_detail,
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_OUTCOME_METRIC
            ),
            value=evaluation.outcome.value,
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC
            ),
            value=evaluation.vocabulary_sha256,
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC
            ),
            value=len(
                evaluation.reference_entities
            ),
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC
            ),
            value=len(
                evaluation.generated_entities
            ),
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC
            ),
            value=evaluation.substitution_count,
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC
            ),
            value=evaluation.omission_count,
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC
            ),
            value=evaluation.insertion_count,
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC
            ),
            value=evaluation.ordering_change_count,
        ),
        _observation(
            metric=(
                CRITICAL_TERMINOLOGY_FINDINGS_METRIC
            ),
            value=[
                finding.to_json()
                for finding in evaluation.findings
            ],
        ),
    )
