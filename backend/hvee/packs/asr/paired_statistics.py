from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import (
    HveeContractError,
    MetricDirection,
)
from hvee.core.paired_statistics import (
    PairedDescriptiveStatistics,
    summarize_matched_observation_cohort,
)
from hvee.packs.asr.matched_evidence import (
    ASRMatchedQualityCohorts,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_METRIC,
)


@dataclass(frozen=True, slots=True)
class ASRDirectionalMetricStatistics:
    """
    ASR interpretation of one lower-is-better matched metric.

    For normalized WER/CER:

        candidate < baseline -> improved
        candidate > baseline -> regressed
        candidate == baseline -> unchanged

    These are descriptive directional labels only. They do not imply
    statistical significance, practical significance, or a release
    verdict.
    """

    metric_key: str
    metric_version: str
    statistics: PairedDescriptiveStatistics

    improved_count: int
    regressed_count: int
    unchanged_count: int

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
                    f"ASR {name} must be a "
                    "non-empty trimmed string"
                )

        if not isinstance(
            self.statistics,
            PairedDescriptiveStatistics,
        ):
            raise HveeContractError(
                "ASR metric statistics require "
                "PairedDescriptiveStatistics"
            )

        for name, value in (
            ("improved count", self.improved_count),
            ("regressed count", self.regressed_count),
            ("unchanged count", self.unchanged_count),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise HveeContractError(
                    f"{name} must be a non-negative integer"
                )

        if (
            self.improved_count
            + self.regressed_count
            + self.unchanged_count
            != self.statistics.usable_pairs
        ):
            raise HveeContractError(
                "ASR direction counts must account "
                "for every usable pair"
            )

    @property
    def total_cases(self) -> int:
        return self.statistics.total_cases

    @property
    def usable_pairs(self) -> int:
        return self.statistics.usable_pairs

    @property
    def incomplete_pairs(self) -> int:
        return self.statistics.incomplete_pairs

    @property
    def complete(self) -> bool:
        return self.statistics.complete

    @property
    def integrity_valid(self) -> bool:
        return self.statistics.integrity_valid

    @property
    def baseline_mean(self) -> float | None:
        return self.statistics.baseline_mean

    @property
    def candidate_mean(self) -> float | None:
        return self.statistics.candidate_mean

    @property
    def mean_delta(self) -> float | None:
        """
        Candidate minus baseline.

        For WER/CER, negative is directionally better and positive is
        directionally worse. No statistical conclusion is implied.
        """

        return self.statistics.mean_delta


@dataclass(frozen=True, slots=True)
class ASRMatchedQualityStatistics:
    """
    Descriptive matched normalized-WER/CER statistics.

    The object preserves exact cohort accounting from the matched
    evidence layer and adds only ASR-specific lower-is-better
    interpretation.

    It performs no inference and produces no release verdict.
    """

    baseline_run_id: int
    candidate_run_id: int
    declared_test_case_ids: tuple[int, ...]

    normalized_wer: ASRDirectionalMetricStatistics
    normalized_cer: ASRDirectionalMetricStatistics

    def __post_init__(self) -> None:
        if (
            self.baseline_run_id
            == self.candidate_run_id
        ):
            raise HveeContractError(
                "ASR quality statistics require "
                "different baseline and candidate runs"
            )

        if not self.declared_test_case_ids:
            raise HveeContractError(
                "ASR quality statistics require "
                "a declared test-case cohort"
            )

        expected_total = len(
            self.declared_test_case_ids
        )

        if (
            self.normalized_wer.total_cases
            != expected_total
            or self.normalized_cer.total_cases
            != expected_total
        ):
            raise HveeContractError(
                "ASR quality statistics must preserve "
                "the complete declared cohort"
            )

        if (
            self.normalized_wer.metric_key
            != NORMALIZED_WER_METRIC.key
            or self.normalized_wer.metric_version
            != NORMALIZED_WER_METRIC.version
        ):
            raise HveeContractError(
                "ASR WER statistics use the wrong "
                "scientific identity"
            )

        if (
            self.normalized_cer.metric_key
            != NORMALIZED_CER_METRIC.key
            or self.normalized_cer.metric_version
            != NORMALIZED_CER_METRIC.version
        ):
            raise HveeContractError(
                "ASR CER statistics use the wrong "
                "scientific identity"
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


def _interpret_lower_is_better(
    *,
    metric,
    statistics: PairedDescriptiveStatistics,
) -> ASRDirectionalMetricStatistics:
    if (
        metric.direction
        != MetricDirection.LOWER_IS_BETTER
    ):
        raise HveeContractError(
            "ASR directional statistics currently "
            "require a lower-is-better metric"
        )

    return ASRDirectionalMetricStatistics(
        metric_key=metric.key,
        metric_version=metric.version,
        statistics=statistics,
        improved_count=(
            statistics.candidate_lower_count
        ),
        regressed_count=(
            statistics.candidate_higher_count
        ),
        unchanged_count=(
            statistics.unchanged_count
        ),
    )


def summarize_asr_matched_quality(
    cohorts: ASRMatchedQualityCohorts,
) -> ASRMatchedQualityStatistics:
    """
    Add ASR directional semantics to matched WER/CER evidence.

    Negative candidate-minus-baseline WER/CER deltas are directionally
    favorable because these metrics are lower-is-better.

    This function intentionally performs no hypothesis test, confidence
    interval, practical-equivalence comparison, minimum-sample check,
    multiplicity correction, or release decision.
    """

    if not isinstance(
        cohorts,
        ASRMatchedQualityCohorts,
    ):
        raise HveeContractError(
            "ASR paired statistics require "
            "ASRMatchedQualityCohorts"
        )

    wer_statistics = (
        summarize_matched_observation_cohort(
            cohorts.normalized_wer
        )
    )

    cer_statistics = (
        summarize_matched_observation_cohort(
            cohorts.normalized_cer
        )
    )

    return ASRMatchedQualityStatistics(
        baseline_run_id=cohorts.baseline_run_id,
        candidate_run_id=cohorts.candidate_run_id,
        declared_test_case_ids=(
            cohorts.declared_test_case_ids
        ),
        normalized_wer=(
            _interpret_lower_is_better(
                metric=NORMALIZED_WER_METRIC,
                statistics=wer_statistics,
            )
        ),
        normalized_cer=(
            _interpret_lower_is_better(
                metric=NORMALIZED_CER_METRIC,
                statistics=cer_statistics,
            )
        ),
    )
