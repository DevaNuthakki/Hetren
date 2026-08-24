"""Declare the versioned Hetren ASR Reliability Profile v1.

The profile is a semantic registry, not a score.  It tells engineers which
signals are primary reliability evidence, which are supporting diagnostics,
which are hard gates, and which correlated signals must not be independently
double-counted by a later aggregate.  Metric calculation, score transforms,
qualification thresholds, and release authority remain outside this layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json

from hvee.core.contracts import (
    EvaluatorVersion,
    MetricDefinition,
    MetricDirection,
    MetricValueType,
)
from hvee.packs.asr.critical_identifier_fidelity import (
    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
    CRITICAL_IDENTIFIER_PRESERVED_METRIC,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_PRESERVED_METRIC,
)
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
    CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
)
from hvee.packs.asr.evaluation import ASR_EVALUATION_TYPE
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
    NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
)
from hvee.packs.asr.transcript_integrity import (
    EXACT_NORMALIZED_MATCH_METRIC,
    MISSING_OUTPUT_METRIC,
    TRANSCRIPT_INTEGRITY_EVALUATOR,
    UNEXPECTED_OUTPUT_METRIC,
)


ASR_RELIABILITY_PROFILE_SCHEMA_VERSION = 1
ASR_RELIABILITY_PROFILE_VERSION = "1.0.0"
ASR_RELIABILITY_PROFILE_KEY = "hetren.asr.reliability-profile"
ASR_RELIABILITY_METRIC_VERSION = "1.0.0"
ASR_RELIABILITY_EVALUATOR_VERSION = "1.0.0"
ASR_RELIABILITY_METRIC_EQUALITY_ABSOLUTE_TOLERANCE = 1e-12


class ASRReliabilityProfileError(ValueError):
    """Raised when an ASR Reliability Profile contract is invalid."""


class ASRReliabilityAxis(StrEnum):
    GENERAL_ACCURACY = "general_accuracy"
    ACOUSTIC_ROBUSTNESS = "acoustic_robustness"
    CRITICAL_CONTENT_INTEGRITY = "critical_content_integrity"
    TRANSCRIPT_INTEGRITY = "transcript_integrity"


class ASRReliabilityMetricRole(StrEnum):
    PRIMARY = "primary_reliability_signal"
    SUPPORTING = "supporting_diagnostic"
    HARD_GATE = "hard_gate"


class ASRReliabilityAggregationUse(StrEnum):
    COMPONENT_CANDIDATE = "component_candidate"
    DIAGNOSTIC_ONLY = "diagnostic_only"
    GATE_ONLY = "gate_only"


class ASRReliabilityComparisonSemantics(StrEnum):
    ABSOLUTE_OBSERVATION = "absolute_observation"
    ERROR_COUNT = "error_count"
    WITHIN_MODEL_PAIRED_DELTA = "within_model_paired_delta"
    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"
    BOOLEAN_PRESERVATION = "boolean_preservation"
    BOOLEAN_FAILURE_GATE = "boolean_failure_gate"


class ASRReliabilityEvidenceRequirement(StrEnum):
    NORMALIZED_TRANSCRIPT_PAIR = "normalized_transcript_pair_v1"
    COMPLETE_MATCHED_CONTROL_PAIR = "complete_matched_control_pair_v1"
    COMPLETE_TWO_MODEL_COMPARISON = (
        "complete_two_model_matched_control_comparison_v1"
    )
    CRITICAL_NUMBER_EVIDENCE = "critical_number_evidence_en_us_v1"
    CRITICAL_IDENTIFIER_EVIDENCE = (
        "critical_identifier_evidence_en_us_v1"
    )
    CRITICAL_TERMINOLOGY_EVIDENCE = (
        "critical_terminology_evidence_en_us_v1"
    )


ASR_RELIABILITY_AXIS_DESCRIPTIONS = {
    ASRReliabilityAxis.GENERAL_ACCURACY: (
        "Broad normalized transcript-error diagnostics."
    ),
    ASRReliabilityAxis.ACOUSTIC_ROBUSTNESS: (
        "Matched-control sensitivity to an acoustic intervention."
    ),
    ASRReliabilityAxis.CRITICAL_CONTENT_INTEGRITY: (
        "Preservation of numbers, identifiers, and registered terminology."
    ),
    ASRReliabilityAxis.TRANSCRIPT_INTEGRITY: (
        "Output-presence and transcript-shape safety conditions."
    ),
}


MATCHED_CONTROL_WER_NOISE_DEGRADATION_METRIC = MetricDefinition(
    key=(
        "asr.matched-control.noise-degradation."
        "wer.normalized-basic"
    ),
    version=ASR_RELIABILITY_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.NUMBER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="ratio",
    description=(
        "Babble-minus-control normalized WER for one exact matched pair. "
        "Positive values mean the intervention increased error."
    ),
)

MATCHED_CONTROL_CER_NOISE_DEGRADATION_METRIC = MetricDefinition(
    key=(
        "asr.matched-control.noise-degradation."
        "cer.normalized-basic"
    ),
    version=ASR_RELIABILITY_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.NUMBER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="ratio",
    description=(
        "Babble-minus-control normalized CER for one exact matched pair. "
        "Positive values mean the intervention increased error."
    ),
)

MATCHED_CONTROL_WER_ROBUSTNESS_DIFFERENTIAL_METRIC = MetricDefinition(
    key=(
        "asr.matched-control.robustness-differential."
        "wer.normalized-basic"
    ),
    version=ASR_RELIABILITY_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.NUMBER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="ratio",
    description=(
        "Candidate-minus-baseline difference in matched-control WER "
        "degradation. Negative values favor the candidate."
    ),
)

MATCHED_CONTROL_CER_ROBUSTNESS_DIFFERENTIAL_METRIC = MetricDefinition(
    key=(
        "asr.matched-control.robustness-differential."
        "cer.normalized-basic"
    ),
    version=ASR_RELIABILITY_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.NUMBER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="ratio",
    description=(
        "Candidate-minus-baseline difference in matched-control CER "
        "degradation. Negative values favor the candidate."
    ),
)

MATCHED_CONTROL_RELIABILITY_EVALUATOR = EvaluatorVersion(
    key=(
        "hetren.asr.matched-control-robustness."
        "normalized-basic"
    ),
    version=ASR_RELIABILITY_EVALUATOR_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    description=(
        "Deterministic Hetren evaluator for exact matched-control "
        "noise degradation and two-model robustness differentials using "
        "normalized-basic WER/CER and canonical metric equality."
    ),
)


def _require_text(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRReliabilityProfileError(
            f"{name} must be non-empty trimmed text."
        )

    return value


def _metric_payload(value: MetricDefinition) -> dict[str, object]:
    return {
        "key": value.key,
        "version": value.version,
        "evaluation_type": value.evaluation_type,
        "value_type": value.value_type.value,
        "direction": value.direction.value,
        "unit": value.unit,
        "description": value.description,
    }


def _evaluator_payload(value: EvaluatorVersion) -> dict[str, object]:
    return {
        "key": value.key,
        "version": value.version,
        "evaluation_type": value.evaluation_type,
        "description": value.description,
    }


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
        raise ASRReliabilityProfileError(
            "ASR Reliability Profile must be deterministic JSON."
        ) from error


@dataclass(frozen=True, slots=True)
class ASRReliabilityMetricBinding:
    metric: MetricDefinition
    evaluator: EvaluatorVersion
    axis: ASRReliabilityAxis
    role: ASRReliabilityMetricRole
    aggregation_use: ASRReliabilityAggregationUse
    comparison_semantics: ASRReliabilityComparisonSemantics
    evidence_requirement: ASRReliabilityEvidenceRequirement
    aggregation_group: str
    engineer_label: str
    engineer_interpretation: str

    def __post_init__(self) -> None:
        if not isinstance(self.metric, MetricDefinition):
            raise ASRReliabilityProfileError(
                "Reliability binding metric is invalid."
            )

        if not isinstance(self.evaluator, EvaluatorVersion):
            raise ASRReliabilityProfileError(
                "Reliability binding evaluator is invalid."
            )

        for name, value, expected_type in (
            ("axis", self.axis, ASRReliabilityAxis),
            ("role", self.role, ASRReliabilityMetricRole),
            (
                "aggregation use",
                self.aggregation_use,
                ASRReliabilityAggregationUse,
            ),
            (
                "comparison semantics",
                self.comparison_semantics,
                ASRReliabilityComparisonSemantics,
            ),
            (
                "evidence requirement",
                self.evidence_requirement,
                ASRReliabilityEvidenceRequirement,
            ),
        ):
            if not isinstance(value, expected_type):
                raise ASRReliabilityProfileError(
                    f"Reliability binding {name} is invalid."
                )

        if (
            self.metric.evaluation_type != ASR_EVALUATION_TYPE
            or self.evaluator.evaluation_type != ASR_EVALUATION_TYPE
        ):
            raise ASRReliabilityProfileError(
                "Reliability bindings must use ASR identities."
            )

        expected_use = {
            ASRReliabilityMetricRole.PRIMARY: (
                ASRReliabilityAggregationUse.COMPONENT_CANDIDATE
            ),
            ASRReliabilityMetricRole.SUPPORTING: (
                ASRReliabilityAggregationUse.DIAGNOSTIC_ONLY
            ),
            ASRReliabilityMetricRole.HARD_GATE: (
                ASRReliabilityAggregationUse.GATE_ONLY
            ),
        }[self.role]

        if self.aggregation_use != expected_use:
            raise ASRReliabilityProfileError(
                "Reliability role and aggregation use are inconsistent."
            )

        if (
            self.role == ASRReliabilityMetricRole.HARD_GATE
            and (
                self.metric.value_type != MetricValueType.BOOLEAN
                or self.metric.direction
                != MetricDirection.LOWER_IS_BETTER
            )
        ):
            raise ASRReliabilityProfileError(
                "Reliability hard gates must be lower-is-better booleans."
            )

        if (
            self.role == ASRReliabilityMetricRole.PRIMARY
            and self.metric.direction == MetricDirection.INFORMATIONAL
        ):
            raise ASRReliabilityProfileError(
                "Primary reliability signals cannot be informational."
            )

        _require_text(
            name="Reliability aggregation group",
            value=self.aggregation_group,
        )
        _require_text(
            name="Reliability engineer label",
            value=self.engineer_label,
        )
        _require_text(
            name="Reliability engineer interpretation",
            value=self.engineer_interpretation,
        )

    @property
    def metric_identity(self) -> tuple[str, str]:
        return self.metric.key, self.metric.version

    @property
    def evaluator_identity(self) -> tuple[str, str]:
        return self.evaluator.key, self.evaluator.version

    @property
    def payload(self) -> dict[str, object]:
        return {
            "metric": _metric_payload(self.metric),
            "evaluator": _evaluator_payload(self.evaluator),
            "axis": self.axis.value,
            "role": self.role.value,
            "aggregation_use": self.aggregation_use.value,
            "comparison_semantics": self.comparison_semantics.value,
            "evidence_requirement": self.evidence_requirement.value,
            "aggregation_group": self.aggregation_group,
            "engineer_label": self.engineer_label,
            "engineer_interpretation": self.engineer_interpretation,
        }


@dataclass(frozen=True, slots=True)
class ASRReliabilityProfileDefinition:
    key: str
    version: str
    evaluation_type: str
    bindings: tuple[ASRReliabilityMetricBinding, ...]

    def __post_init__(self) -> None:
        _require_text(name="Reliability profile key", value=self.key)
        _require_text(
            name="Reliability profile version",
            value=self.version,
        )

        if self.evaluation_type != ASR_EVALUATION_TYPE:
            raise ASRReliabilityProfileError(
                "Reliability Profile evaluation type must be ASR."
            )

        if not self.bindings:
            raise ASRReliabilityProfileError(
                "Reliability Profile requires metric bindings."
            )

        if not all(
            isinstance(value, ASRReliabilityMetricBinding)
            for value in self.bindings
        ):
            raise ASRReliabilityProfileError(
                "Reliability Profile bindings are invalid."
            )

        metric_identities = tuple(
            value.metric_identity
            for value in self.bindings
        )

        if len(set(metric_identities)) != len(metric_identities):
            raise ASRReliabilityProfileError(
                "Reliability Profile metric identities must be unique."
            )

        observed_roles = {
            value.role
            for value in self.bindings
        }

        if observed_roles != set(ASRReliabilityMetricRole):
            raise ASRReliabilityProfileError(
                "Reliability Profile must declare primary, supporting, "
                "and hard-gate signals."
            )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema_version": ASR_RELIABILITY_PROFILE_SCHEMA_VERSION,
            "profile": {
                "key": self.key,
                "version": self.version,
                "evaluation_type": self.evaluation_type,
            },
            "methodology": {
                "metric_equality": {
                    "absolute_tolerance": (
                        ASR_RELIABILITY_METRIC_EQUALITY_ABSOLUTE_TOLERANCE
                    ),
                    "relative_tolerance": 0.0,
                    "canonical_zero": True,
                },
                "correlated_signals_share_aggregation_group": True,
                "direct_metric_averaging_permitted": False,
            },
            "axes": [
                {
                    "key": axis.value,
                    "description": ASR_RELIABILITY_AXIS_DESCRIPTIONS[axis],
                }
                for axis in ASRReliabilityAxis
            ],
            "bindings": [
                value.payload
                for value in self.bindings
            ],
            "evidence_boundary": {
                "declarative_profile_only": True,
                "metric_values_computed": False,
                "aggregate_score_computed": False,
                "score_transform_defined": False,
                "metric_weights_defined": False,
                "missing_evidence_policy_defined": False,
                "qualification_threshold_applied": False,
                "model_verdict_issued": False,
                "production_qualified": False,
                "release_decision_issued": False,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json_bytes(self.payload)
        ).hexdigest()

    def binding_for(
        self,
        *,
        metric_key: str,
        metric_version: str,
    ) -> ASRReliabilityMetricBinding:
        for binding in self.bindings:
            if binding.metric_identity == (
                metric_key,
                metric_version,
            ):
                return binding

        raise ASRReliabilityProfileError(
            "Metric identity is not bound to this Reliability Profile."
        )

    def require_aggregate_score(self) -> None:
        raise ASRReliabilityProfileError(
            "ASR Reliability Profile v1 is declarative B10G evidence; "
            "no aggregate score was computed."
        )

    def require_qualification_decision(self) -> None:
        raise ASRReliabilityProfileError(
            "ASR Reliability Profile v1 does not apply qualification "
            "thresholds or issue a model verdict."
        )


def _binding(
    *,
    metric: MetricDefinition,
    evaluator: EvaluatorVersion,
    axis: ASRReliabilityAxis,
    role: ASRReliabilityMetricRole,
    aggregation_use: ASRReliabilityAggregationUse,
    comparison_semantics: ASRReliabilityComparisonSemantics,
    evidence_requirement: ASRReliabilityEvidenceRequirement,
    aggregation_group: str,
    engineer_label: str,
    engineer_interpretation: str,
) -> ASRReliabilityMetricBinding:
    return ASRReliabilityMetricBinding(
        metric=metric,
        evaluator=evaluator,
        axis=axis,
        role=role,
        aggregation_use=aggregation_use,
        comparison_semantics=comparison_semantics,
        evidence_requirement=evidence_requirement,
        aggregation_group=aggregation_group,
        engineer_label=engineer_label,
        engineer_interpretation=engineer_interpretation,
    )


def build_asr_reliability_profile_v1() -> ASRReliabilityProfileDefinition:
    """Build the canonical, score-free ASR Reliability Profile v1."""

    diagnostic = ASRReliabilityMetricRole.SUPPORTING
    diagnostic_only = ASRReliabilityAggregationUse.DIAGNOSTIC_ONLY
    primary = ASRReliabilityMetricRole.PRIMARY
    component = ASRReliabilityAggregationUse.COMPONENT_CANDIDATE
    gate = ASRReliabilityMetricRole.HARD_GATE
    gate_only = ASRReliabilityAggregationUse.GATE_ONLY

    return ASRReliabilityProfileDefinition(
        key=ASR_RELIABILITY_PROFILE_KEY,
        version=ASR_RELIABILITY_PROFILE_VERSION,
        evaluation_type=ASR_EVALUATION_TYPE,
        bindings=(
            _binding(
                metric=NORMALIZED_WER_METRIC,
                evaluator=NORMALIZED_WER_EVALUATOR,
                axis=ASRReliabilityAxis.GENERAL_ACCURACY,
                role=diagnostic,
                aggregation_use=diagnostic_only,
                comparison_semantics=(
                    ASRReliabilityComparisonSemantics.ABSOLUTE_OBSERVATION
                ),
                evidence_requirement=(
                    ASRReliabilityEvidenceRequirement
                    .NORMALIZED_TRANSCRIPT_PAIR
                ),
                aggregation_group="general_accuracy",
                engineer_label="Normalized Word Error Rate",
                engineer_interpretation=(
                    "Broad word-level error diagnostic; not a standalone "
                    "reliability verdict."
                ),
            ),
            _binding(
                metric=NORMALIZED_CER_METRIC,
                evaluator=NORMALIZED_CER_EVALUATOR,
                axis=ASRReliabilityAxis.GENERAL_ACCURACY,
                role=diagnostic,
                aggregation_use=diagnostic_only,
                comparison_semantics=(
                    ASRReliabilityComparisonSemantics.ABSOLUTE_OBSERVATION
                ),
                evidence_requirement=(
                    ASRReliabilityEvidenceRequirement
                    .NORMALIZED_TRANSCRIPT_PAIR
                ),
                aggregation_group="general_accuracy",
                engineer_label="Normalized Character Error Rate",
                engineer_interpretation=(
                    "Character-level corroboration for transcript errors; "
                    "not independently averaged into reliability."
                ),
            ),
            *(
                _binding(
                    metric=metric,
                    evaluator=NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
                    axis=ASRReliabilityAxis.GENERAL_ACCURACY,
                    role=diagnostic,
                    aggregation_use=diagnostic_only,
                    comparison_semantics=(
                        ASRReliabilityComparisonSemantics.ERROR_COUNT
                    ),
                    evidence_requirement=(
                        ASRReliabilityEvidenceRequirement
                        .NORMALIZED_TRANSCRIPT_PAIR
                    ),
                    aggregation_group="word_alignment_errors",
                    engineer_label=label,
                    engineer_interpretation=interpretation,
                )
                for metric, label, interpretation in (
                    (
                        NORMALIZED_SUBSTITUTIONS_METRIC,
                        "Normalized Word Substitutions",
                        "Explains how much error came from replaced words.",
                    ),
                    (
                        NORMALIZED_INSERTIONS_METRIC,
                        "Normalized Word Insertions",
                        "Explains how much error came from extra words.",
                    ),
                    (
                        NORMALIZED_DELETIONS_METRIC,
                        "Normalized Word Deletions",
                        "Explains how much error came from missing words.",
                    ),
                )
            ),
            _binding(
                metric=EXACT_NORMALIZED_MATCH_METRIC,
                evaluator=TRANSCRIPT_INTEGRITY_EVALUATOR,
                axis=ASRReliabilityAxis.TRANSCRIPT_INTEGRITY,
                role=diagnostic,
                aggregation_use=diagnostic_only,
                comparison_semantics=(
                    ASRReliabilityComparisonSemantics.ABSOLUTE_OBSERVATION
                ),
                evidence_requirement=(
                    ASRReliabilityEvidenceRequirement
                    .NORMALIZED_TRANSCRIPT_PAIR
                ),
                aggregation_group="transcript_integrity",
                engineer_label="Exact Normalized Transcript Match",
                engineer_interpretation=(
                    "Useful strict-match context; a false value is not "
                    "automatically a reliability failure."
                ),
            ),
            *(
                _binding(
                    metric=metric,
                    evaluator=TRANSCRIPT_INTEGRITY_EVALUATOR,
                    axis=ASRReliabilityAxis.TRANSCRIPT_INTEGRITY,
                    role=gate,
                    aggregation_use=gate_only,
                    comparison_semantics=(
                        ASRReliabilityComparisonSemantics
                        .BOOLEAN_FAILURE_GATE
                    ),
                    evidence_requirement=(
                        ASRReliabilityEvidenceRequirement
                        .NORMALIZED_TRANSCRIPT_PAIR
                    ),
                    aggregation_group="transcript_integrity_gates",
                    engineer_label=label,
                    engineer_interpretation=interpretation,
                )
                for metric, label, interpretation in (
                    (
                        MISSING_OUTPUT_METRIC,
                        "Missing Output Gate",
                        "True means speech content produced no transcript.",
                    ),
                    (
                        UNEXPECTED_OUTPUT_METRIC,
                        "Unexpected Output Gate",
                        "True means output appeared without reference text.",
                    ),
                )
            ),
            *(
                _binding(
                    metric=metric,
                    evaluator=MATCHED_CONTROL_RELIABILITY_EVALUATOR,
                    axis=ASRReliabilityAxis.ACOUSTIC_ROBUSTNESS,
                    role=diagnostic,
                    aggregation_use=diagnostic_only,
                    comparison_semantics=(
                        ASRReliabilityComparisonSemantics
                        .WITHIN_MODEL_PAIRED_DELTA
                    ),
                    evidence_requirement=(
                        ASRReliabilityEvidenceRequirement
                        .COMPLETE_MATCHED_CONTROL_PAIR
                    ),
                    aggregation_group="matched_control_degradation",
                    engineer_label=label,
                    engineer_interpretation=interpretation,
                )
                for metric, label, interpretation in (
                    (
                        MATCHED_CONTROL_WER_NOISE_DEGRADATION_METRIC,
                        "Matched-Control Noise Degradation (WER)",
                        "Within-model word-error sensitivity to babble noise.",
                    ),
                    (
                        MATCHED_CONTROL_CER_NOISE_DEGRADATION_METRIC,
                        "Matched-Control Noise Degradation (CER)",
                        "Within-model character-error sensitivity to noise.",
                    ),
                )
            ),
            *(
                _binding(
                    metric=metric,
                    evaluator=MATCHED_CONTROL_RELIABILITY_EVALUATOR,
                    axis=ASRReliabilityAxis.ACOUSTIC_ROBUSTNESS,
                    role=primary,
                    aggregation_use=component,
                    comparison_semantics=(
                        ASRReliabilityComparisonSemantics
                        .DIFFERENCE_IN_DIFFERENCES
                    ),
                    evidence_requirement=(
                        ASRReliabilityEvidenceRequirement
                        .COMPLETE_TWO_MODEL_COMPARISON
                    ),
                    aggregation_group="matched_control_robustness",
                    engineer_label=label,
                    engineer_interpretation=interpretation,
                )
                for metric, label, interpretation in (
                    (
                        MATCHED_CONTROL_WER_ROBUSTNESS_DIFFERENTIAL_METRIC,
                        "Hetren Robustness Differential (WER)",
                        "Candidate-minus-baseline change in noise-driven "
                        "word-error degradation; lower is better.",
                    ),
                    (
                        MATCHED_CONTROL_CER_ROBUSTNESS_DIFFERENTIAL_METRIC,
                        "Hetren Robustness Differential (CER)",
                        "Correlated character-level robustness differential; "
                        "it shares one aggregation group with WER.",
                    ),
                )
            ),
            *(
                _binding(
                    metric=metric,
                    evaluator=evaluator,
                    axis=(
                        ASRReliabilityAxis.CRITICAL_CONTENT_INTEGRITY
                    ),
                    role=primary,
                    aggregation_use=component,
                    comparison_semantics=(
                        ASRReliabilityComparisonSemantics
                        .BOOLEAN_PRESERVATION
                    ),
                    evidence_requirement=evidence,
                    aggregation_group=group,
                    engineer_label=label,
                    engineer_interpretation=interpretation,
                )
                for (
                    metric,
                    evaluator,
                    evidence,
                    group,
                    label,
                    interpretation,
                ) in (
                    (
                        CRITICAL_NUMBER_PRESERVED_METRIC,
                        CRITICAL_NUMBER_FIDELITY_EVALUATOR,
                        ASRReliabilityEvidenceRequirement
                        .CRITICAL_NUMBER_EVIDENCE,
                        "critical_number_integrity",
                        "Critical Number Preservation",
                        "Whether all conclusive critical numbers survived.",
                    ),
                    (
                        CRITICAL_IDENTIFIER_PRESERVED_METRIC,
                        CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
                        ASRReliabilityEvidenceRequirement
                        .CRITICAL_IDENTIFIER_EVIDENCE,
                        "critical_identifier_integrity",
                        "Critical Identifier Preservation",
                        "Whether all conclusive identifiers survived.",
                    ),
                    (
                        CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
                        CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
                        ASRReliabilityEvidenceRequirement
                        .CRITICAL_TERMINOLOGY_EVIDENCE,
                        "critical_terminology_integrity",
                        "Critical Terminology Preservation",
                        "Whether all registered critical terms survived.",
                    ),
                )
            ),
        ),
    )


ASR_RELIABILITY_PROFILE_V1 = build_asr_reliability_profile_v1()
ASR_RELIABILITY_PROFILE_V1_SHA256 = (
    "fcfb829b4e598ffe2be35776a31c2d8a"
    "f98f68537888daddfc3a8a7c8413fdf3"
)

if ASR_RELIABILITY_PROFILE_V1.sha256 != ASR_RELIABILITY_PROFILE_V1_SHA256:
    raise ASRReliabilityProfileError(
        "Canonical ASR Reliability Profile v1 SHA-256 changed: "
        f"{ASR_RELIABILITY_PROFILE_V1.sha256}."
    )


def verify_asr_reliability_profile_v1(
    value: ASRReliabilityProfileDefinition,
) -> ASRReliabilityProfileDefinition:
    """Require the exact canonical ASR Reliability Profile v1."""

    if not isinstance(value, ASRReliabilityProfileDefinition):
        raise ASRReliabilityProfileError(
            "ASR Reliability Profile verification requires a profile."
        )

    if (
        value.key != ASR_RELIABILITY_PROFILE_KEY
        or value.version != ASR_RELIABILITY_PROFILE_VERSION
        or value.payload != ASR_RELIABILITY_PROFILE_V1.payload
        or value.sha256 != ASR_RELIABILITY_PROFILE_V1_SHA256
    ):
        raise ASRReliabilityProfileError(
            "ASR Reliability Profile identity is unsupported or changed."
        )

    return value
