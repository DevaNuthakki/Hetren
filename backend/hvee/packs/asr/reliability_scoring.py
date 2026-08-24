"""Compute deterministic, explainable Hetren ASR Reliability scores.

B10G declares which ASR signals belong to the Reliability Profile.  This
module defines the first aggregate scoring methodology over that exact
profile.  It keeps performance, evidence assurance, and operational fitness
separate so engineers can see why a score moved.  Qualification thresholds,
winner selection, certification, and release authority remain outside this
layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from enum import StrEnum
import hashlib
import json

from hvee.packs.asr.reliability_profile import (
    ASR_RELIABILITY_PROFILE_V1,
    ASR_RELIABILITY_PROFILE_V1_SHA256,
    ASRReliabilityProfileDefinition,
    verify_asr_reliability_profile_v1,
)
from hvee.packs.asr.transcript_integrity import (
    MISSING_OUTPUT_METRIC,
    UNEXPECTED_OUTPUT_METRIC,
)


ASR_RELIABILITY_SCORING_SCHEMA_VERSION = 1
ASR_RELIABILITY_SCORING_VERSION = "1.0.0"
ASR_RELIABILITY_SCORING_KEY = "hetren.asr.reliability-scoring"
ASR_RELIABILITY_SCORE_MINIMUM = 0.0
ASR_RELIABILITY_SCORE_MAXIMUM = 100.0
ASR_RELIABILITY_SCORE_DECIMAL_PLACES = 12

_SCORE_QUANTUM = Decimal("0.000000000001")
_ONE_HUNDRED = Decimal("100")


class ASRReliabilityScoringError(ValueError):
    """Raised when Reliability scoring evidence or output is invalid."""


class ASRReliabilityIndexStatus(StrEnum):
    COMPLETE = "complete"
    PROVISIONAL = "provisional"
    WITHHELD = "withheld"
    HARD_GATE_TRIGGERED = "hard_gate_triggered"


class ASRReliabilityMaturityStatus(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PARTIAL_DESCRIPTIVE_EVIDENCE = "partial_descriptive_evidence"
    COMPLETE_DESCRIPTIVE_EVIDENCE = "complete_descriptive_evidence"
    HARD_GATE_FAILURE_OBSERVED = "hard_gate_failure_observed"


class ASRReliabilityGateStatus(StrEnum):
    CLEAR = "clear"
    UNRESOLVED = "unresolved"
    TRIGGERED = "triggered"


def _require_text(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRReliabilityScoringError(
            f"{name} must be non-empty trimmed text."
        )

    return value


def _require_bool_or_none(*, name: str, value: object) -> None:
    if value is not None and not isinstance(value, bool):
        raise ASRReliabilityScoringError(
            f"{name} must be boolean or missing."
        )


def _require_count(*, name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ASRReliabilityScoringError(
            f"{name} must be a non-negative integer."
        )

    return value


def _decimal(value: int | float | str | Decimal) -> Decimal:
    if isinstance(value, bool):
        raise ASRReliabilityScoringError(
            "Reliability numeric values cannot be booleans."
        )

    try:
        result = Decimal(str(value))
    except Exception as error:
        raise ASRReliabilityScoringError(
            "Reliability numeric value is invalid."
        ) from error

    if not result.is_finite():
        raise ASRReliabilityScoringError(
            "Reliability numeric values must be finite."
        )

    return result


def _score(value: Decimal | int | float) -> float:
    observed = _decimal(value)

    if observed < 0 or observed > _ONE_HUNDRED:
        raise ASRReliabilityScoringError(
            "Reliability scores must be between 0 and 100."
        )

    quantized = observed.quantize(
        _SCORE_QUANTUM,
        rounding=ROUND_HALF_EVEN,
    )

    if quantized == 0:
        return 0.0

    if quantized == _ONE_HUNDRED:
        return 100.0

    return float(quantized)


def _ratio(*, numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise ASRReliabilityScoringError(
            "Reliability ratios require a positive denominator."
        )

    return _score(
        _ONE_HUNDRED
        * Decimal(numerator)
        / Decimal(denominator)
    )


def _coverage(*, observed: int, expected: int) -> float:
    return _score(
        _ONE_HUNDRED
        * Decimal(observed)
        / Decimal(expected)
    ) / 100.0


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ASRReliabilityScoringError(
            "Reliability scoring must be deterministic JSON."
        ) from error


def _weighted_geometric_mean(
    values: tuple[tuple[float, Decimal], ...],
) -> float | None:
    if not values:
        return None

    for value, _weight in values:
        if value == 0:
            return 0.0

    total_weight = sum(
        (weight for _value, weight in values),
        Decimal("0"),
    )

    if total_weight <= 0:
        raise ASRReliabilityScoringError(
            "Reliability aggregation requires positive weight."
        )

    with localcontext() as context:
        context.prec = 50
        log_sum = sum(
            (
                weight
                * (_decimal(value) / _ONE_HUNDRED).ln()
                for value, weight in values
            ),
            Decimal("0"),
        )
        result = (log_sum / total_weight).exp() * _ONE_HUNDRED

    return _score(result)


@dataclass(frozen=True, slots=True)
class ASRReliabilityRateEvidence:
    """Observed successes and coverage for one rate-based component."""

    successful_count: int
    observed_count: int
    expected_count: int

    def __post_init__(self) -> None:
        successful = _require_count(
            name="Reliability successful count",
            value=self.successful_count,
        )
        observed = _require_count(
            name="Reliability observed count",
            value=self.observed_count,
        )
        expected = _require_count(
            name="Reliability expected count",
            value=self.expected_count,
        )

        if expected <= 0:
            raise ASRReliabilityScoringError(
                "Reliability expected count must be positive."
            )

        if successful > observed or observed > expected:
            raise ASRReliabilityScoringError(
                "Reliability counts must satisfy successful <= observed "
                "<= expected."
            )

    @property
    def score(self) -> float | None:
        if self.observed_count == 0:
            return None

        return _ratio(
            numerator=self.successful_count,
            denominator=self.observed_count,
        )

    @property
    def coverage_ratio(self) -> float:
        return _coverage(
            observed=self.observed_count,
            expected=self.expected_count,
        )

    @property
    def complete(self) -> bool:
        return self.observed_count == self.expected_count

    @property
    def payload(self) -> dict[str, object]:
        return {
            "successful_count": self.successful_count,
            "observed_count": self.observed_count,
            "expected_count": self.expected_count,
            "score": self.score,
            "coverage_ratio": self.coverage_ratio,
            "complete": self.complete,
        }


@dataclass(frozen=True, slots=True)
class ASRMatchedControlRobustnessEvidence:
    """Candidate-minus-baseline matched-control robustness evidence."""

    wer_differential: float | None
    cer_differential: float | None
    observed_pair_count: int
    expected_pair_count: int

    def __post_init__(self) -> None:
        observed = _require_count(
            name="Observed matched-control pair count",
            value=self.observed_pair_count,
        )
        expected = _require_count(
            name="Expected matched-control pair count",
            value=self.expected_pair_count,
        )

        if expected <= 0 or observed > expected:
            raise ASRReliabilityScoringError(
                "Matched-control pairs require 0 <= observed <= "
                "positive expected."
            )

        for name, value in (
            ("WER robustness differential", self.wer_differential),
            ("CER robustness differential", self.cer_differential),
        ):
            if value is not None:
                _decimal(value)

        if observed == 0 and (
            self.wer_differential is not None
            or self.cer_differential is not None
        ):
            raise ASRReliabilityScoringError(
                "Robustness differentials require observed pairs."
            )

        if observed > 0 and (
            self.wer_differential is None
            and self.cer_differential is None
        ):
            raise ASRReliabilityScoringError(
                "Observed pairs require a robustness differential."
            )

    @staticmethod
    def transform_differential(value: float) -> float:
        """Map non-regression to 100 and positive regression to lost points."""

        observed = _decimal(value)
        regression = max(observed, Decimal("0"))
        retained = max(
            Decimal("0"),
            Decimal("1") - regression,
        )
        return _score(retained * _ONE_HUNDRED)

    @property
    def wer_score(self) -> float | None:
        if self.wer_differential is None:
            return None

        return self.transform_differential(self.wer_differential)

    @property
    def cer_score(self) -> float | None:
        if self.cer_differential is None:
            return None

        return self.transform_differential(self.cer_differential)

    @property
    def score(self) -> float | None:
        observed = tuple(
            value
            for value in (self.wer_score, self.cer_score)
            if value is not None
        )

        if not observed:
            return None

        return min(observed)

    @property
    def coverage_ratio(self) -> float:
        signal_coverage = sum(
            value is not None
            for value in (
                self.wer_differential,
                self.cer_differential,
            )
        ) / 2
        pair_coverage = self.observed_pair_count / self.expected_pair_count
        return _score(
            Decimal(str(signal_coverage))
            * Decimal(str(pair_coverage))
            * _ONE_HUNDRED
        ) / 100.0

    @property
    def complete(self) -> bool:
        return (
            self.wer_differential is not None
            and self.cer_differential is not None
            and self.observed_pair_count == self.expected_pair_count
        )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "wer_differential": self.wer_differential,
            "cer_differential": self.cer_differential,
            "wer_score": self.wer_score,
            "cer_score": self.cer_score,
            "aggregation": "conservative_minimum_correlated_signal_score",
            "score": self.score,
            "observed_pair_count": self.observed_pair_count,
            "expected_pair_count": self.expected_pair_count,
            "coverage_ratio": self.coverage_ratio,
            "complete": self.complete,
        }


@dataclass(frozen=True, slots=True)
class ASRReliabilityGateEvidence:
    metric_key: str
    violation_count: int
    observed_count: int
    expected_count: int

    def __post_init__(self) -> None:
        _require_text(name="Reliability gate metric key", value=self.metric_key)
        violations = _require_count(
            name="Reliability gate violation count",
            value=self.violation_count,
        )
        observed = _require_count(
            name="Reliability gate observed count",
            value=self.observed_count,
        )
        expected = _require_count(
            name="Reliability gate expected count",
            value=self.expected_count,
        )

        if expected <= 0:
            raise ASRReliabilityScoringError(
                "Reliability gate expected count must be positive."
            )

        if violations > observed or observed > expected:
            raise ASRReliabilityScoringError(
                "Gate counts must satisfy violations <= observed <= expected."
            )

    @property
    def triggered(self) -> bool:
        return self.violation_count > 0

    @property
    def resolved(self) -> bool:
        return self.observed_count == self.expected_count

    @property
    def payload(self) -> dict[str, object]:
        return {
            "metric_key": self.metric_key,
            "violation_count": self.violation_count,
            "observed_count": self.observed_count,
            "expected_count": self.expected_count,
            "triggered": self.triggered,
            "resolved": self.resolved,
        }


@dataclass(frozen=True, slots=True)
class ASRReliabilityPerformanceEvidence:
    matched_control_robustness: ASRMatchedControlRobustnessEvidence | None = None
    critical_number_integrity: ASRReliabilityRateEvidence | None = None
    critical_identifier_integrity: ASRReliabilityRateEvidence | None = None
    critical_terminology_integrity: ASRReliabilityRateEvidence | None = None


@dataclass(frozen=True, slots=True)
class ASREvidenceAssuranceEvidence:
    profile_and_evaluators_verified: bool | None = None
    input_provenance_verified: bool | None = None
    runtime_identity_verified: bool | None = None
    reproducibility_verified: bool | None = None

    def __post_init__(self) -> None:
        for name, value in self.values:
            _require_bool_or_none(name=name, value=value)

    @property
    def values(self) -> tuple[tuple[str, bool | None], ...]:
        return (
            (
                "profile_and_evaluators_verified",
                self.profile_and_evaluators_verified,
            ),
            ("input_provenance_verified", self.input_provenance_verified),
            ("runtime_identity_verified", self.runtime_identity_verified),
            ("reproducibility_verified", self.reproducibility_verified),
        )


@dataclass(frozen=True, slots=True)
class ASROperationalFitnessEvidence:
    execution_completion: ASRReliabilityRateEvidence | None = None
    timeout_free: ASRReliabilityRateEvidence | None = None
    cancellation_free: ASRReliabilityRateEvidence | None = None
    provider_error_free: ASRReliabilityRateEvidence | None = None

    @property
    def values(
        self,
    ) -> tuple[tuple[str, ASRReliabilityRateEvidence | None], ...]:
        return (
            ("execution_completion", self.execution_completion),
            ("timeout_free", self.timeout_free),
            ("cancellation_free", self.cancellation_free),
            ("provider_error_free", self.provider_error_free),
        )


@dataclass(frozen=True, slots=True)
class ASRReliabilityScoringEvidence:
    performance: ASRReliabilityPerformanceEvidence
    assurance: ASREvidenceAssuranceEvidence
    operational: ASROperationalFitnessEvidence
    missing_output_gate: ASRReliabilityGateEvidence | None = None
    unexpected_output_gate: ASRReliabilityGateEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.performance, ASRReliabilityPerformanceEvidence):
            raise ASRReliabilityScoringError(
                "Reliability performance evidence is invalid."
            )
        if not isinstance(self.assurance, ASREvidenceAssuranceEvidence):
            raise ASRReliabilityScoringError(
                "Evidence assurance input is invalid."
            )
        if not isinstance(self.operational, ASROperationalFitnessEvidence):
            raise ASRReliabilityScoringError(
                "Operational fitness input is invalid."
            )

        for value in (
            self.missing_output_gate,
            self.unexpected_output_gate,
        ):
            if value is not None and not isinstance(
                value,
                ASRReliabilityGateEvidence,
            ):
                raise ASRReliabilityScoringError(
                    "Reliability gate evidence is invalid."
                )

        expected_gate_keys = (
            MISSING_OUTPUT_METRIC.key,
            UNEXPECTED_OUTPUT_METRIC.key,
        )

        for value, expected_key in zip(
            (self.missing_output_gate, self.unexpected_output_gate),
            expected_gate_keys,
            strict=True,
        ):
            if value is not None and value.metric_key != expected_key:
                raise ASRReliabilityScoringError(
                    "Reliability gate metric identity is invalid."
                )


@dataclass(frozen=True, slots=True)
class ASRReliabilityIndexComponent:
    key: str
    engineer_label: str
    engineer_interpretation: str
    weight: float
    score: float | None
    coverage_ratio: float
    complete: bool

    def __post_init__(self) -> None:
        _require_text(name="Reliability component key", value=self.key)
        _require_text(
            name="Reliability component label",
            value=self.engineer_label,
        )
        _require_text(
            name="Reliability component interpretation",
            value=self.engineer_interpretation,
        )
        weight = _decimal(self.weight)
        coverage = _decimal(self.coverage_ratio)

        if weight <= 0:
            raise ASRReliabilityScoringError(
                "Reliability component weight must be positive."
            )
        if coverage < 0 or coverage > 1:
            raise ASRReliabilityScoringError(
                "Reliability component coverage must be between 0 and 1."
            )
        if self.score is not None:
            _score(self.score)
        if self.complete != (coverage == 1):
            raise ASRReliabilityScoringError(
                "Reliability component completeness must match coverage."
            )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "engineer_label": self.engineer_label,
            "engineer_interpretation": self.engineer_interpretation,
            "weight": self.weight,
            "score": self.score,
            "coverage_ratio": self.coverage_ratio,
            "complete": self.complete,
        }


@dataclass(frozen=True, slots=True)
class ASRReliabilityIndexResult:
    key: str
    engineer_label: str
    status: ASRReliabilityIndexStatus
    score: float | None
    observed_score: float | None
    coverage_ratio: float
    components: tuple[ASRReliabilityIndexComponent, ...]

    @property
    def payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "engineer_label": self.engineer_label,
            "status": self.status.value,
            "score": self.score,
            "observed_score": self.observed_score,
            "coverage_ratio": self.coverage_ratio,
            "components": [value.payload for value in self.components],
        }


@dataclass(frozen=True, slots=True)
class ASRReliabilityScoringDefinitionV1:
    key: str = ASR_RELIABILITY_SCORING_KEY
    version: str = ASR_RELIABILITY_SCORING_VERSION
    profile_sha256: str = ASR_RELIABILITY_PROFILE_V1_SHA256

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema_version": ASR_RELIABILITY_SCORING_SCHEMA_VERSION,
            "scoring": {
                "key": self.key,
                "version": self.version,
                "score_range": [
                    ASR_RELIABILITY_SCORE_MINIMUM,
                    ASR_RELIABILITY_SCORE_MAXIMUM,
                ],
                "decimal_places": ASR_RELIABILITY_SCORE_DECIMAL_PLACES,
            },
            "profile": {
                "key": ASR_RELIABILITY_PROFILE_V1.key,
                "version": ASR_RELIABILITY_PROFILE_V1.version,
                "sha256": self.profile_sha256,
            },
            "indices": {
                "reliability_performance_index": {
                    "aggregation": "equal_weight_geometric_mean",
                    "groups": {
                        "matched_control_robustness": 0.25,
                        "critical_number_integrity": 0.25,
                        "critical_identifier_integrity": 0.25,
                        "critical_terminology_integrity": 0.25,
                    },
                    "robustness_transform": (
                        "100 * clamp(1 - max(0, differential), 0, 1)"
                    ),
                    "correlated_wer_cer_group_rule": (
                        "minimum_available_signal_score"
                    ),
                },
                "evidence_assurance_index": {
                    "aggregation": "equal_weight_geometric_mean",
                    "components": {
                        "profile_and_evaluators_verified": 0.25,
                        "input_provenance_verified": 0.25,
                        "runtime_identity_verified": 0.25,
                        "reproducibility_verified": 0.25,
                    },
                },
                "operational_fitness_index": {
                    "aggregation": "equal_weight_geometric_mean",
                    "components": {
                        "execution_completion": 0.25,
                        "timeout_free": 0.25,
                        "cancellation_free": 0.25,
                        "provider_error_free": 0.25,
                    },
                },
                "hetren_reliability_index": {
                    "aggregation": "weighted_geometric_mean",
                    "pillars": {
                        "reliability_performance_index": 0.60,
                        "evidence_assurance_index": 0.25,
                        "operational_fitness_index": 0.15,
                    },
                },
            },
            "methodology": {
                "higher_scores_are_better": True,
                "zero_component_is_non_compensable": True,
                "missing_components_are_not_imputed": True,
                "partial_scores_are_provisional_and_not_comparable": True,
                "complete_score_requires_all_components": True,
                "known_hard_gate_failure_precedes_missing_evidence": True,
                "clear_gate_requires_complete_gate_observation": True,
            },
            "evidence_boundary": {
                "scoring_definition_only": True,
                "metric_values_computed": False,
                "scorecard_computed": False,
                "qualification_threshold_applied": False,
                "model_winner_declared": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()


def _component(
    *,
    key: str,
    label: str,
    interpretation: str,
    score: float | None,
    coverage: float,
    weight: float,
) -> ASRReliabilityIndexComponent:
    return ASRReliabilityIndexComponent(
        key=key,
        engineer_label=label,
        engineer_interpretation=interpretation,
        weight=weight,
        score=score,
        coverage_ratio=coverage,
        complete=coverage == 1.0,
    )


def _build_index(
    *,
    key: str,
    label: str,
    components: tuple[ASRReliabilityIndexComponent, ...],
) -> ASRReliabilityIndexResult:
    observed = tuple(
        (component.score, _decimal(component.weight))
        for component in components
        if component.score is not None
    )
    observed_score = _weighted_geometric_mean(observed)
    total_weight = sum(
        (_decimal(value.weight) for value in components),
        Decimal("0"),
    )
    weighted_coverage = sum(
        (
            _decimal(value.weight)
            * _decimal(value.coverage_ratio)
            for value in components
        ),
        Decimal("0"),
    ) / total_weight
    coverage_ratio = _score(weighted_coverage * _ONE_HUNDRED) / 100.0

    if all(value.complete for value in components):
        status = ASRReliabilityIndexStatus.COMPLETE
        score = observed_score
    elif observed_score is not None:
        status = ASRReliabilityIndexStatus.PROVISIONAL
        score = None
    else:
        status = ASRReliabilityIndexStatus.WITHHELD
        score = None

    return ASRReliabilityIndexResult(
        key=key,
        engineer_label=label,
        status=status,
        score=score,
        observed_score=observed_score,
        coverage_ratio=coverage_ratio,
        components=components,
    )


def _performance_index(
    evidence: ASRReliabilityPerformanceEvidence,
) -> ASRReliabilityIndexResult:
    robustness = evidence.matched_control_robustness

    def rate_component(
        *,
        key: str,
        label: str,
        interpretation: str,
        value: ASRReliabilityRateEvidence | None,
    ) -> ASRReliabilityIndexComponent:
        return _component(
            key=key,
            label=label,
            interpretation=interpretation,
            score=None if value is None else value.score,
            coverage=0.0 if value is None else value.coverage_ratio,
            weight=0.25,
        )

    components = (
        _component(
            key="matched_control_robustness",
            label="Matched-Control Acoustic Robustness",
            interpretation=(
                "Conservative candidate robustness retention across "
                "correlated WER and CER differentials."
            ),
            score=None if robustness is None else robustness.score,
            coverage=(
                0.0 if robustness is None else robustness.coverage_ratio
            ),
            weight=0.25,
        ),
        rate_component(
            key="critical_number_integrity",
            label="Critical Number Integrity",
            interpretation="Share of conclusive critical numbers preserved.",
            value=evidence.critical_number_integrity,
        ),
        rate_component(
            key="critical_identifier_integrity",
            label="Critical Identifier Integrity",
            interpretation="Share of conclusive identifiers preserved.",
            value=evidence.critical_identifier_integrity,
        ),
        rate_component(
            key="critical_terminology_integrity",
            label="Critical Terminology Integrity",
            interpretation="Share of registered critical terms preserved.",
            value=evidence.critical_terminology_integrity,
        ),
    )

    return _build_index(
        key="reliability_performance_index",
        label="Reliability Performance Index",
        components=components,
    )


def _assurance_index(
    evidence: ASREvidenceAssuranceEvidence,
) -> ASRReliabilityIndexResult:
    interpretations = {
        "profile_and_evaluators_verified": (
            "Canonical profile and evaluator identities were verified."
        ),
        "input_provenance_verified": (
            "Fixed input identities and provenance were verified."
        ),
        "runtime_identity_verified": (
            "Requested and observed model/runtime identities agree."
        ),
        "reproducibility_verified": (
            "Repeated evaluation produced reproducible evidence."
        ),
    }
    components = tuple(
        _component(
            key=key,
            label=key.replace("_", " ").title(),
            interpretation=interpretations[key],
            score=None if value is None else (100.0 if value else 0.0),
            coverage=0.0 if value is None else 1.0,
            weight=0.25,
        )
        for key, value in evidence.values
    )

    return _build_index(
        key="evidence_assurance_index",
        label="Evidence Assurance Index",
        components=components,
    )


def _operational_index(
    evidence: ASROperationalFitnessEvidence,
) -> ASRReliabilityIndexResult:
    interpretations = {
        "execution_completion": "Share of expected executions completed.",
        "timeout_free": "Share of observed executions without timeout.",
        "cancellation_free": (
            "Share of observed executions without cancellation."
        ),
        "provider_error_free": (
            "Share of observed executions without provider failure."
        ),
    }
    components = tuple(
        _component(
            key=key,
            label=key.replace("_", " ").title(),
            interpretation=interpretations[key],
            score=None if value is None else value.score,
            coverage=0.0 if value is None else value.coverage_ratio,
            weight=0.25,
        )
        for key, value in evidence.values
    )

    return _build_index(
        key="operational_fitness_index",
        label="Operational Fitness Index",
        components=components,
    )


def _gate_status(
    evidence: ASRReliabilityScoringEvidence,
) -> ASRReliabilityGateStatus:
    gates = (
        evidence.missing_output_gate,
        evidence.unexpected_output_gate,
    )

    if any(value is not None and value.triggered for value in gates):
        return ASRReliabilityGateStatus.TRIGGERED

    if all(value is not None and value.resolved for value in gates):
        return ASRReliabilityGateStatus.CLEAR

    return ASRReliabilityGateStatus.UNRESOLVED


@dataclass(frozen=True, slots=True)
class ASRReliabilityScorecard:
    scoring_definition_sha256: str
    profile_sha256: str
    gate_status: ASRReliabilityGateStatus
    maturity_status: ASRReliabilityMaturityStatus
    performance_index: ASRReliabilityIndexResult
    evidence_assurance_index: ASRReliabilityIndexResult
    operational_fitness_index: ASRReliabilityIndexResult
    hetren_reliability_index: ASRReliabilityIndexResult
    gate_evidence: tuple[ASRReliabilityGateEvidence | None, ...]

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema_version": ASR_RELIABILITY_SCORING_SCHEMA_VERSION,
            "artifact": {
                "key": "hetren.asr.reliability-scorecard",
                "version": ASR_RELIABILITY_SCORING_VERSION,
                "type": "descriptive_reliability_scorecard",
            },
            "methodology": {
                "scoring_definition_sha256": self.scoring_definition_sha256,
                "profile_sha256": self.profile_sha256,
            },
            "status": {
                "gate": self.gate_status.value,
                "maturity": self.maturity_status.value,
            },
            "indices": {
                "reliability_performance": self.performance_index.payload,
                "evidence_assurance": self.evidence_assurance_index.payload,
                "operational_fitness": self.operational_fitness_index.payload,
                "hetren_reliability": self.hetren_reliability_index.payload,
            },
            "hard_gates": [
                None if value is None else value.payload
                for value in self.gate_evidence
            ],
            "evidence_boundary": {
                "descriptive_scorecard_only": True,
                "aggregate_score_computed": (
                    self.hetren_reliability_index.score is not None
                ),
                "provisional_score_exposed": (
                    self.hetren_reliability_index.observed_score is not None
                    and self.hetren_reliability_index.score is None
                ),
                "missing_evidence_imputed": False,
                "qualification_threshold_applied": False,
                "model_winner_declared": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()

    def require_qualification_decision(self) -> None:
        raise ASRReliabilityScoringError(
            "B10H Reliability scoring is descriptive; no qualification "
            "threshold or release decision was applied."
        )


ASR_RELIABILITY_SCORING_V1 = ASRReliabilityScoringDefinitionV1()
ASR_RELIABILITY_SCORING_V1_SHA256 = (
    "752f3bbb1a6bda1c9134228f03f72eb6"
    "bd1a07ad32f64e65d1c61d07c03c903d"
)

if ASR_RELIABILITY_SCORING_V1.sha256 != ASR_RELIABILITY_SCORING_V1_SHA256:
    raise ASRReliabilityScoringError(
        "Canonical ASR Reliability scoring v1 SHA-256 changed: "
        f"{ASR_RELIABILITY_SCORING_V1.sha256}."
    )


def verify_asr_reliability_scoring_v1(
    value: ASRReliabilityScoringDefinitionV1,
) -> ASRReliabilityScoringDefinitionV1:
    if not isinstance(value, ASRReliabilityScoringDefinitionV1):
        raise ASRReliabilityScoringError(
            "ASR Reliability scoring verification requires a definition."
        )

    if (
        value.key != ASR_RELIABILITY_SCORING_KEY
        or value.version != ASR_RELIABILITY_SCORING_VERSION
        or value.profile_sha256 != ASR_RELIABILITY_PROFILE_V1_SHA256
        or value.payload != ASR_RELIABILITY_SCORING_V1.payload
        or value.sha256 != ASR_RELIABILITY_SCORING_V1_SHA256
    ):
        raise ASRReliabilityScoringError(
            "ASR Reliability scoring identity is unsupported or changed."
        )

    return value


def score_asr_reliability_v1(
    *,
    evidence: ASRReliabilityScoringEvidence,
    profile: ASRReliabilityProfileDefinition = ASR_RELIABILITY_PROFILE_V1,
) -> ASRReliabilityScorecard:
    if not isinstance(evidence, ASRReliabilityScoringEvidence):
        raise ASRReliabilityScoringError(
            "ASR Reliability scoring evidence is invalid."
        )

    try:
        verified_profile = verify_asr_reliability_profile_v1(profile)
    except Exception as error:
        raise ASRReliabilityScoringError(
            "ASR Reliability scoring requires the exact v1 profile."
        ) from error

    performance = _performance_index(evidence.performance)
    assurance = _assurance_index(evidence.assurance)
    operational = _operational_index(evidence.operational)
    gate_status = _gate_status(evidence)

    pillar_components = tuple(
        _component(
            key=result.key,
            label=result.engineer_label,
            interpretation=interpretation,
            score=result.observed_score,
            coverage=result.coverage_ratio,
            weight=weight,
        )
        for result, interpretation, weight in (
            (
                performance,
                "Reliability across robustness and critical content.",
                0.60,
            ),
            (
                assurance,
                "Confidence that evidence identity and provenance are sound.",
                0.25,
            ),
            (
                operational,
                "Fitness of the observed execution path.",
                0.15,
            ),
        )
    )
    aggregate = _build_index(
        key="hetren_reliability_index",
        label="Hetren Reliability Index",
        components=pillar_components,
    )

    if gate_status == ASRReliabilityGateStatus.TRIGGERED:
        aggregate = ASRReliabilityIndexResult(
            key=aggregate.key,
            engineer_label=aggregate.engineer_label,
            status=ASRReliabilityIndexStatus.HARD_GATE_TRIGGERED,
            score=0.0,
            observed_score=aggregate.observed_score,
            coverage_ratio=aggregate.coverage_ratio,
            components=aggregate.components,
        )
        maturity = ASRReliabilityMaturityStatus.HARD_GATE_FAILURE_OBSERVED
    elif (
        gate_status == ASRReliabilityGateStatus.CLEAR
        and aggregate.status == ASRReliabilityIndexStatus.COMPLETE
    ):
        maturity = ASRReliabilityMaturityStatus.COMPLETE_DESCRIPTIVE_EVIDENCE
    elif aggregate.observed_score is not None:
        if aggregate.status == ASRReliabilityIndexStatus.COMPLETE:
            aggregate = ASRReliabilityIndexResult(
                key=aggregate.key,
                engineer_label=aggregate.engineer_label,
                status=ASRReliabilityIndexStatus.PROVISIONAL,
                score=None,
                observed_score=aggregate.observed_score,
                coverage_ratio=aggregate.coverage_ratio,
                components=aggregate.components,
            )
        maturity = ASRReliabilityMaturityStatus.PARTIAL_DESCRIPTIVE_EVIDENCE
    else:
        maturity = ASRReliabilityMaturityStatus.INSUFFICIENT_EVIDENCE

    return ASRReliabilityScorecard(
        scoring_definition_sha256=ASR_RELIABILITY_SCORING_V1_SHA256,
        profile_sha256=verified_profile.sha256,
        gate_status=gate_status,
        maturity_status=maturity,
        performance_index=performance,
        evidence_assurance_index=assurance,
        operational_fitness_index=operational,
        hetren_reliability_index=aggregate,
        gate_evidence=(
            evidence.missing_output_gate,
            evidence.unexpected_output_gate,
        ),
    )
