from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    EvaluatorVersion,
    MetricDefinition,
)
from hvee.core.evidence_readiness import (
    ObservationRequirement,
)
from hvee.packs.asr.evaluation import (
    ASR_EVALUATION_TYPE,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.numeric_preservation import (
    NUMERIC_TOKEN_PRESERVATION_EVALUATOR,
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
)
from hvee.packs.asr.transcript_integrity import (
    MISSING_OUTPUT_METRIC,
    TRANSCRIPT_INTEGRITY_EVALUATOR,
    UNEXPECTED_OUTPUT_METRIC,
)


ASR_TEST_CASE_DECISION_POLICY_KEY = (
    "hetren.asr.test-case-quality"
)
ASR_TEST_CASE_DECISION_POLICY_VERSION = "1.0.0"


class ASRRuleDisposition(StrEnum):
    """
    How one ASR rule participates in a decision.

    DISABLED:
        The rule is not part of this policy.

    CLAIM:
        A violation contradicts the normal quality claim.

    CRITICAL:
        A violation is a critical invariant failure.
    """

    DISABLED = "disabled"
    CLAIM = "claim"
    CRITICAL = "critical"


def _validate_optional_limit(
    *,
    name: str,
    value: float | None,
) -> None:
    if value is None:
        return

    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise HveeContractError(
            f"{name} must be a finite "
            "non-negative number or null"
        )


def _validate_disposition(
    *,
    name: str,
    value: object,
) -> None:
    if not isinstance(
        value,
        ASRRuleDisposition,
    ):
        raise HveeContractError(
            f"{name} must be an ASRRuleDisposition"
        )


@dataclass(frozen=True, slots=True)
class ASRTestCaseDecisionPolicyV1:
    """
    Versioned ASR test-case decision policy.

    This contract declares decision rules. It does not itself evaluate
    observations or produce a verdict.

    Normalized WER/CER limits are normal claim constraints.

    Transcript and numeric signals are explicitly assigned a
    disposition so a metric never becomes a critical failure merely
    because it exists.

    No default quality thresholds are provided. Thresholds should be
    chosen by an explicit policy and later calibrated against evidence.
    """

    max_normalized_wer: float | None = None
    max_normalized_cer: float | None = None

    missing_output: ASRRuleDisposition = (
        ASRRuleDisposition.DISABLED
    )
    unexpected_output: ASRRuleDisposition = (
        ASRRuleDisposition.DISABLED
    )
    numeric_sequence_match: ASRRuleDisposition = (
        ASRRuleDisposition.DISABLED
    )

    @property
    def key(self) -> str:
        return ASR_TEST_CASE_DECISION_POLICY_KEY

    @property
    def version(self) -> str:
        return ASR_TEST_CASE_DECISION_POLICY_VERSION

    def __post_init__(self) -> None:
        _validate_optional_limit(
            name="maximum normalized WER",
            value=self.max_normalized_wer,
        )
        _validate_optional_limit(
            name="maximum normalized CER",
            value=self.max_normalized_cer,
        )

        _validate_disposition(
            name="missing-output disposition",
            value=self.missing_output,
        )
        _validate_disposition(
            name="unexpected-output disposition",
            value=self.unexpected_output,
        )
        _validate_disposition(
            name="numeric-sequence disposition",
            value=self.numeric_sequence_match,
        )

        if (
            self.max_normalized_wer is None
            and self.max_normalized_cer is None
            and self.missing_output
            == ASRRuleDisposition.DISABLED
            and self.unexpected_output
            == ASRRuleDisposition.DISABLED
            and self.numeric_sequence_match
            == ASRRuleDisposition.DISABLED
        ):
            raise HveeContractError(
                "ASR decision policy must enable "
                "at least one decision rule"
            )


def _requirement(
    *,
    metric: MetricDefinition,
    evaluator: EvaluatorVersion,
) -> ObservationRequirement:
    if (
        metric.evaluation_type
        != ASR_EVALUATION_TYPE
        or evaluator.evaluation_type
        != ASR_EVALUATION_TYPE
    ):
        raise HveeContractError(
            "ASR decision requirements must use "
            "ASR metric and evaluator identities"
        )

    return ObservationRequirement(
        metric_key=metric.key,
        metric_version=metric.version,
        evaluator_key=evaluator.key,
        evaluator_version=evaluator.version,
        evaluation_type=ASR_EVALUATION_TYPE,
        scope="test_case",
        value_type=metric.value_type,
    )


def build_asr_test_case_requirements(
    policy: ASRTestCaseDecisionPolicyV1,
) -> tuple[ObservationRequirement, ...]:
    """
    Return the exact versioned observations required by a policy.

    Requirement selection is driven only by enabled rules. Rule
    disposition changes decision severity, not the scientific identity
    of the required evidence.
    """

    if not isinstance(
        policy,
        ASRTestCaseDecisionPolicyV1,
    ):
        raise HveeContractError(
            "ASR decision policy must be "
            "ASRTestCaseDecisionPolicyV1"
        )

    requirements: list[
        ObservationRequirement
    ] = []

    if policy.max_normalized_wer is not None:
        requirements.append(
            _requirement(
                metric=NORMALIZED_WER_METRIC,
                evaluator=NORMALIZED_WER_EVALUATOR,
            )
        )

    if policy.max_normalized_cer is not None:
        requirements.append(
            _requirement(
                metric=NORMALIZED_CER_METRIC,
                evaluator=NORMALIZED_CER_EVALUATOR,
            )
        )

    if (
        policy.missing_output
        != ASRRuleDisposition.DISABLED
    ):
        requirements.append(
            _requirement(
                metric=MISSING_OUTPUT_METRIC,
                evaluator=TRANSCRIPT_INTEGRITY_EVALUATOR,
            )
        )

    if (
        policy.unexpected_output
        != ASRRuleDisposition.DISABLED
    ):
        requirements.append(
            _requirement(
                metric=UNEXPECTED_OUTPUT_METRIC,
                evaluator=TRANSCRIPT_INTEGRITY_EVALUATOR,
            )
        )

    if (
        policy.numeric_sequence_match
        != ASRRuleDisposition.DISABLED
    ):
        requirements.append(
            _requirement(
                metric=REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
                evaluator=NUMERIC_TOKEN_PRESERVATION_EVALUATOR,
            )
        )
        requirements.append(
            _requirement(
                metric=NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
                evaluator=NUMERIC_TOKEN_PRESERVATION_EVALUATOR,
            )
        )

    return tuple(
        sorted(
            requirements,
            key=lambda requirement: (
                requirement.identity
            ),
        )
    )
