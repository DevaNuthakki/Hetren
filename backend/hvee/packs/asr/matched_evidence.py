from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.core.evidence_readiness import (
    ObservationRequirement,
)
from hvee.core.matched_evidence import (
    MatchedObservationCohort,
    build_matched_observation_cohort,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
)


def _requirement(
    *,
    metric,
    evaluator,
) -> ObservationRequirement:
    return ObservationRequirement(
        metric_key=metric.key,
        metric_version=metric.version,
        evaluator_key=evaluator.key,
        evaluator_version=evaluator.version,
        evaluation_type="asr",
        scope="test_case",
        value_type=metric.value_type,
    )


ASR_NORMALIZED_WER_REQUIREMENT = _requirement(
    metric=NORMALIZED_WER_METRIC,
    evaluator=NORMALIZED_WER_EVALUATOR,
)

ASR_NORMALIZED_CER_REQUIREMENT = _requirement(
    metric=NORMALIZED_CER_METRIC,
    evaluator=NORMALIZED_CER_EVALUATOR,
)


@dataclass(frozen=True, slots=True)
class ASRMatchedQualityCohorts:
    """
    Matched normalized-WER and normalized-CER evidence.

    Both metrics use the exact same explicitly declared test-case
    cohort and exact baseline/candidate run identities.

    This object contains evidence accounting only. It performs no
    statistical inference and produces no release verdict.
    """

    baseline_run_id: int
    candidate_run_id: int
    declared_test_case_ids: tuple[int, ...]
    normalized_wer: MatchedObservationCohort
    normalized_cer: MatchedObservationCohort

    def __post_init__(self) -> None:
        if (
            self.normalized_wer.baseline_run_id
            != self.baseline_run_id
            or self.normalized_cer.baseline_run_id
            != self.baseline_run_id
            or self.normalized_wer.candidate_run_id
            != self.candidate_run_id
            or self.normalized_cer.candidate_run_id
            != self.candidate_run_id
        ):
            raise HveeContractError(
                "ASR matched quality cohorts must "
                "share run identities"
            )

        if (
            self.normalized_wer.declared_test_case_ids
            != self.declared_test_case_ids
            or self.normalized_cer.declared_test_case_ids
            != self.declared_test_case_ids
        ):
            raise HveeContractError(
                "ASR matched quality cohorts must "
                "share the exact declared test-case cohort"
            )

        if (
            self.normalized_wer.requirement
            != ASR_NORMALIZED_WER_REQUIREMENT
        ):
            raise HveeContractError(
                "ASR matched WER cohort uses "
                "the wrong scientific identity"
            )

        if (
            self.normalized_cer.requirement
            != ASR_NORMALIZED_CER_REQUIREMENT
        ):
            raise HveeContractError(
                "ASR matched CER cohort uses "
                "the wrong scientific identity"
            )

    @property
    def total_cases(self) -> int:
        return len(
            self.declared_test_case_ids
        )

    @property
    def complete(self) -> bool:
        return (
            self.normalized_wer.complete
            and self.normalized_cer.complete
        )

    @property
    def integrity_valid(self) -> bool:
        return (
            self.normalized_wer.integrity_valid
            and self.normalized_cer.integrity_valid
        )


def build_asr_matched_quality_cohorts(
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    declared_test_case_ids: tuple[int, ...],
    records: tuple[
        ObservationEvidenceRecord,
        ...,
    ],
) -> ASRMatchedQualityCohorts:
    """
    Build matched normalized-WER and normalized-CER cohorts.

    The same declared test-case cohort is used for both metrics.
    Missing or unusable evidence remains explicit in the respective
    cohort rather than being silently removed from aggregation.

    This function performs no release policy evaluation.
    """

    wer = build_matched_observation_cohort(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        declared_test_case_ids=(
            declared_test_case_ids
        ),
        requirement=(
            ASR_NORMALIZED_WER_REQUIREMENT
        ),
        records=records,
    )

    cer = build_matched_observation_cohort(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        declared_test_case_ids=(
            declared_test_case_ids
        ),
        requirement=(
            ASR_NORMALIZED_CER_REQUIREMENT
        ),
        records=records,
    )

    return ASRMatchedQualityCohorts(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        declared_test_case_ids=(
            wer.declared_test_case_ids
        ),
        normalized_wer=wer,
        normalized_cer=cer,
    )
