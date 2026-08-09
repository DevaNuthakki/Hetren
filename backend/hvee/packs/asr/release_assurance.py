from __future__ import annotations

import math
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.core.decision import (
    ClaimAssessment,
    EvidenceAssessment,
    IntegrityAssessment,
)
from hvee.core.paired_interval import (
    PairedMeanDeltaInterval,
    calculate_paired_mean_delta_interval,
)
from hvee.packs.asr.matched_evidence import (
    ASRMatchedQualityCohorts,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)


@dataclass(frozen=True, slots=True)
class ASRMetricNoninferiorityAssessment:
    """
    Assurance result for one lower-is-better ASR metric.

    The statistical target is the mean paired per-test-case delta:

        candidate - baseline

    A positive non-inferiority margin is the largest mean degradation
    permitted by the explicitly supplied policy.

    v1 uses the upper bound of the configured two-sided paired
    percentile-bootstrap interval:

        upper <= margin -> SUPPORTED

    Strong evidence that the complete interval lies beyond the margin:

        lower > margin -> CONTRADICTED

    If the interval overlaps the margin, the claim is UNRESOLVED.

    Failure to establish non-inferiority is therefore not silently
    converted into evidence of inferiority.
    """

    metric_key: str
    metric_version: str
    noninferiority_margin: float
    interval: PairedMeanDeltaInterval
    claim: ClaimAssessment

    def __post_init__(self) -> None:
        for name, value in (
            ("metric key", self.metric_key),
            ("metric version", self.metric_version),
        ):
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
            ):
                raise HveeContractError(
                    f"ASR assurance {name} must be "
                    "a non-empty trimmed string"
                )

        if (
            isinstance(
                self.noninferiority_margin,
                bool,
            )
            or not isinstance(
                self.noninferiority_margin,
                (int, float),
            )
            or not math.isfinite(
                float(
                    self.noninferiority_margin
                )
            )
            or float(
                self.noninferiority_margin
            ) < 0.0
        ):
            raise HveeContractError(
                "ASR non-inferiority margin must be "
                "a finite non-negative number"
            )

        if not isinstance(
            self.interval,
            PairedMeanDeltaInterval,
        ):
            raise HveeContractError(
                "ASR non-inferiority assessment "
                "requires PairedMeanDeltaInterval"
            )

        if not isinstance(
            self.claim,
            ClaimAssessment,
        ):
            raise HveeContractError(
                "ASR non-inferiority claim must be "
                "ClaimAssessment"
            )

        expected = _classify_noninferiority(
            interval=self.interval,
            margin=float(
                self.noninferiority_margin
            ),
        )

        if self.claim != expected:
            raise HveeContractError(
                "ASR non-inferiority claim does not "
                "match its interval and margin"
            )


@dataclass(frozen=True, slots=True)
class ASRMatchedReleaseAssuranceResult:
    """
    Combined matched ASR release-assurance evidence.

    Enabled policy metrics are evaluated independently and then
    combined into domain-level integrity, evidence, and claim
    assessments.

    This object does not produce the universal four-state verdict.
    """

    policy_key: str
    policy_version: str

    baseline_run_id: int
    candidate_run_id: int
    declared_test_case_ids: tuple[int, ...]

    normalized_wer: (
        ASRMetricNoninferiorityAssessment
        | None
    )
    normalized_cer: (
        ASRMetricNoninferiorityAssessment
        | None
    )

    integrity: IntegrityAssessment
    evidence: EvidenceAssessment
    claim: ClaimAssessment

    def __post_init__(self) -> None:
        if (
            not isinstance(
                self.policy_key,
                str,
            )
            or not self.policy_key
            or self.policy_key
            != self.policy_key.strip()
        ):
            raise HveeContractError(
                "ASR assurance policy key must be "
                "a non-empty trimmed string"
            )

        if (
            not isinstance(
                self.policy_version,
                str,
            )
            or not self.policy_version
            or self.policy_version
            != self.policy_version.strip()
        ):
            raise HveeContractError(
                "ASR assurance policy version must be "
                "a non-empty trimmed string"
            )

        if (
            isinstance(
                self.baseline_run_id,
                bool,
            )
            or not isinstance(
                self.baseline_run_id,
                int,
            )
            or self.baseline_run_id < 1
            or isinstance(
                self.candidate_run_id,
                bool,
            )
            or not isinstance(
                self.candidate_run_id,
                int,
            )
            or self.candidate_run_id < 1
            or self.baseline_run_id
            == self.candidate_run_id
        ):
            raise HveeContractError(
                "ASR assurance requires different "
                "positive run identities"
            )

        if not self.declared_test_case_ids:
            raise HveeContractError(
                "ASR assurance requires a declared cohort"
            )

        enabled = tuple(
            assessment
            for assessment
            in (
                self.normalized_wer,
                self.normalized_cer,
            )
            if assessment is not None
        )

        if not enabled:
            raise HveeContractError(
                "ASR assurance requires at least "
                "one enabled metric"
            )

        expected_integrity = (
            IntegrityAssessment.INVALID
            if any(
                assessment.interval.integrity
                == IntegrityAssessment.INVALID
                for assessment
                in enabled
            )
            else IntegrityAssessment.VALID
        )

        expected_evidence = (
            EvidenceAssessment.SUFFICIENT
            if all(
                assessment.interval.evidence
                == EvidenceAssessment.SUFFICIENT
                for assessment
                in enabled
            )
            else EvidenceAssessment.INSUFFICIENT
        )

        claims = tuple(
            assessment.claim
            for assessment
            in enabled
        )

        if (
            ClaimAssessment.CONTRADICTED
            in claims
        ):
            expected_claim = (
                ClaimAssessment.CONTRADICTED
            )
        elif all(
            claim == ClaimAssessment.SUPPORTED
            for claim
            in claims
        ):
            expected_claim = (
                ClaimAssessment.SUPPORTED
            )
        else:
            expected_claim = (
                ClaimAssessment.UNRESOLVED
            )

        if (
            self.integrity
            != expected_integrity
        ):
            raise HveeContractError(
                "ASR combined integrity does not "
                "match metric assurance results"
            )

        if self.evidence != expected_evidence:
            raise HveeContractError(
                "ASR combined evidence does not "
                "match metric assurance results"
            )

        if self.claim != expected_claim:
            raise HveeContractError(
                "ASR combined claim does not "
                "match metric assurance results"
            )


def _classify_noninferiority(
    *,
    interval: PairedMeanDeltaInterval,
    margin: float,
) -> ClaimAssessment:
    if not interval.ready:
        return ClaimAssessment.UNRESOLVED

    if (
        interval.lower_bound is None
        or interval.upper_bound is None
    ):
        raise HveeContractError(
            "ready ASR assurance interval "
            "is missing bounds"
        )

    if interval.upper_bound <= margin:
        return ClaimAssessment.SUPPORTED

    if interval.lower_bound > margin:
        return ClaimAssessment.CONTRADICTED

    return ClaimAssessment.UNRESOLVED


def _evaluate_metric(
    *,
    metric,
    cohort,
    margin: float,
    policy: ASRMatchedReleaseAssurancePolicyV1,
) -> ASRMetricNoninferiorityAssessment:
    interval = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=policy.interval,
        )
    )

    claim = _classify_noninferiority(
        interval=interval,
        margin=margin,
    )

    return ASRMetricNoninferiorityAssessment(
        metric_key=metric.key,
        metric_version=metric.version,
        noninferiority_margin=margin,
        interval=interval,
        claim=claim,
    )


def evaluate_asr_matched_release_assurance(
    *,
    cohorts: ASRMatchedQualityCohorts,
    policy: ASRMatchedReleaseAssurancePolicyV1,
) -> ASRMatchedReleaseAssuranceResult:
    """
    Evaluate matched normalized-WER/CER non-inferiority claims.

    The policy explicitly determines which metrics participate.

    This function returns integrity, evidence, and claim assessments,
    but intentionally does not call the universal decision kernel yet.
    """

    if not isinstance(
        cohorts,
        ASRMatchedQualityCohorts,
    ):
        raise HveeContractError(
            "ASR release assurance requires "
            "ASRMatchedQualityCohorts"
        )

    if not isinstance(
        policy,
        ASRMatchedReleaseAssurancePolicyV1,
    ):
        raise HveeContractError(
            "ASR release assurance requires "
            "ASRMatchedReleaseAssurancePolicyV1"
        )

    wer = None

    if (
        policy
        .normalized_wer_noninferiority_margin
        is not None
    ):
        wer = _evaluate_metric(
            metric=NORMALIZED_WER_METRIC,
            cohort=cohorts.normalized_wer,
            margin=float(
                policy
                .normalized_wer_noninferiority_margin
            ),
            policy=policy,
        )

    cer = None

    if (
        policy
        .normalized_cer_noninferiority_margin
        is not None
    ):
        cer = _evaluate_metric(
            metric=NORMALIZED_CER_METRIC,
            cohort=cohorts.normalized_cer,
            margin=float(
                policy
                .normalized_cer_noninferiority_margin
            ),
            policy=policy,
        )

    enabled = tuple(
        assessment
        for assessment
        in (
            wer,
            cer,
        )
        if assessment is not None
    )

    integrity = (
        IntegrityAssessment.INVALID
        if any(
            assessment.interval.integrity
            == IntegrityAssessment.INVALID
            for assessment
            in enabled
        )
        else IntegrityAssessment.VALID
    )

    evidence = (
        EvidenceAssessment.SUFFICIENT
        if all(
            assessment.interval.evidence
            == EvidenceAssessment.SUFFICIENT
            for assessment
            in enabled
        )
        else EvidenceAssessment.INSUFFICIENT
    )

    claims = tuple(
        assessment.claim
        for assessment
        in enabled
    )

    if (
        ClaimAssessment.CONTRADICTED
        in claims
    ):
        claim = ClaimAssessment.CONTRADICTED
    elif all(
        item == ClaimAssessment.SUPPORTED
        for item
        in claims
    ):
        claim = ClaimAssessment.SUPPORTED
    else:
        claim = ClaimAssessment.UNRESOLVED

    return ASRMatchedReleaseAssuranceResult(
        policy_key=policy.key,
        policy_version=policy.version,
        baseline_run_id=(
            cohorts.baseline_run_id
        ),
        candidate_run_id=(
            cohorts.candidate_run_id
        ),
        declared_test_case_ids=(
            cohorts.declared_test_case_ids
        ),
        normalized_wer=wer,
        normalized_cer=cer,
        integrity=integrity,
        evidence=evidence,
        claim=claim,
    )
