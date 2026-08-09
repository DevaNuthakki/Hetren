from __future__ import annotations

import json
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.core.decision_evidence import (
    calculate_decision_sha256,
    calculate_policy_sha256,
)
from hvee.core.matched_evidence import (
    MatchedEvidenceSide,
    MatchedObservationCohort,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.core.paired_interval import (
    PairedMeanDeltaInterval,
)
from hvee.packs.asr.matched_evidence import (
    ASRMatchedQualityCohorts,
    build_asr_matched_quality_cohorts,
)
from hvee.packs.asr.paired_statistics import (
    ASRDirectionalMetricStatistics,
    ASRMatchedQualityStatistics,
    summarize_asr_matched_quality,
)
from hvee.packs.asr.release_assurance import (
    ASRMetricNoninferiorityAssessment,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.release_decision import (
    ASRMatchedReleaseDecisionResult,
    evaluate_asr_matched_release_decision,
)


ASR_MATCHED_RELEASE_DECISION_EVIDENCE_SCHEMA_VERSION = 1


def _require_positive_integer(
    *,
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        raise HveeContractError(
            f"{name} must be a positive integer"
        )

    return value


def _require_sha256_hex(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase "
            "SHA-256 hex digest"
        )

    return value


def _canonicalize_json_value(
    value: object,
    *,
    name: str,
) -> object:
    """
    Normalize through Hetren's deterministic JSON convention.

    Core decision evidence intentionally keeps its canonicalization
    helper private. This module therefore follows the same public
    evidence convention without importing a private implementation.
    """

    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        return json.loads(serialized)

    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid "
            "deterministic JSON"
        ) from exc


@dataclass(frozen=True, slots=True)
class ASRMatchedCaseEvidenceBinding:
    """
    Immutable-evidence identities for one matched test case.

    These digests are opaque to the pure HVEE layer. The future
    application persistence adapter must independently verify that
    every supplied provenance/bundle digest belongs to the identified
    persisted result before constructing release evidence.
    """

    test_case_id: int

    baseline_result_provenance_id: int
    baseline_provenance_sha256: str
    baseline_observation_evidence_sha256: str

    candidate_result_provenance_id: int
    candidate_provenance_sha256: str
    candidate_observation_evidence_sha256: str

    def __post_init__(self) -> None:
        _require_positive_integer(
            name="test case id",
            value=self.test_case_id,
        )
        _require_positive_integer(
            name="baseline result provenance id",
            value=(
                self.baseline_result_provenance_id
            ),
        )
        _require_positive_integer(
            name="candidate result provenance id",
            value=(
                self.candidate_result_provenance_id
            ),
        )

        if (
            self.baseline_result_provenance_id
            == self.candidate_result_provenance_id
        ):
            raise HveeContractError(
                "baseline and candidate evidence "
                "must use different result provenances"
            )

        _require_sha256_hex(
            name="baseline provenance SHA-256",
            value=self.baseline_provenance_sha256,
        )
        _require_sha256_hex(
            name=(
                "baseline observation evidence SHA-256"
            ),
            value=(
                self
                .baseline_observation_evidence_sha256
            ),
        )
        _require_sha256_hex(
            name="candidate provenance SHA-256",
            value=self.candidate_provenance_sha256,
        )
        _require_sha256_hex(
            name=(
                "candidate observation evidence SHA-256"
            ),
            value=(
                self
                .candidate_observation_evidence_sha256
            ),
        )


@dataclass(frozen=True, slots=True)
class ASRMatchedReleaseDecisionEvidenceBundle:
    payload: dict[str, object]
    policy_sha256: str
    decision_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "ASR matched release evidence payload "
                "must be a JSON object"
            )

        _require_sha256_hex(
            name="release policy SHA-256",
            value=self.policy_sha256,
        )
        _require_sha256_hex(
            name="release decision SHA-256",
            value=self.decision_sha256,
        )


def build_asr_matched_release_policy_snapshot(
    policy: ASRMatchedReleaseAssurancePolicyV1,
) -> dict[str, object]:
    if not isinstance(
        policy,
        ASRMatchedReleaseAssurancePolicyV1,
    ):
        raise HveeContractError(
            "ASR matched release policy snapshot "
            "requires ASRMatchedReleaseAssurancePolicyV1"
        )

    return {
        "interval": {
            "method": policy.interval.method.value,
            "confidence_level": (
                policy.interval.confidence_level
            ),
            "minimum_usable_pairs": (
                policy.interval.minimum_usable_pairs
            ),
            "resamples": (
                policy.interval.resamples
            ),
            "random_seed": (
                policy.interval.random_seed
            ),
        },
        "normalized_wer_noninferiority_margin": (
            policy
            .normalized_wer_noninferiority_margin
        ),
        "normalized_cer_noninferiority_margin": (
            policy
            .normalized_cer_noninferiority_margin
        ),
    }


def _binding_snapshot(
    binding: ASRMatchedCaseEvidenceBinding,
) -> dict[str, object]:
    return {
        "test_case_id": binding.test_case_id,
        "baseline": {
            "result_provenance_id": (
                binding
                .baseline_result_provenance_id
            ),
            "provenance_sha256": (
                binding
                .baseline_provenance_sha256
            ),
            "observation_evidence_sha256": (
                binding
                .baseline_observation_evidence_sha256
            ),
        },
        "candidate": {
            "result_provenance_id": (
                binding
                .candidate_result_provenance_id
            ),
            "provenance_sha256": (
                binding
                .candidate_provenance_sha256
            ),
            "observation_evidence_sha256": (
                binding
                .candidate_observation_evidence_sha256
            ),
        },
    }


def _side_snapshot(
    side: MatchedEvidenceSide,
) -> dict[str, object]:
    return {
        "evaluation_run_id": (
            side.evaluation_run_id
        ),
        "test_case_id": side.test_case_id,
        "state": side.state.value,
        "value": side.value,
        "observation_status": (
            None
            if side.observation_status is None
            else side.observation_status.value
        ),
        "status_detail": side.status_detail,
    }


def _cohort_snapshot(
    cohort: MatchedObservationCohort,
) -> dict[str, object]:
    requirement = cohort.requirement

    return {
        "scientific_identity": {
            "metric": {
                "key": requirement.metric_key,
                "version": (
                    requirement.metric_version
                ),
            },
            "evaluator": {
                "key": requirement.evaluator_key,
                "version": (
                    requirement.evaluator_version
                ),
            },
            "evaluation_type": (
                requirement.evaluation_type
            ),
            "scope": requirement.scope,
            "value_type": (
                requirement.value_type.value
            ),
        },
        "total_cases": cohort.total_cases,
        "usable_pairs": cohort.usable_pairs,
        "incomplete_pairs": (
            cohort.incomplete_pairs
        ),
        "complete": cohort.complete,
        "integrity_valid": (
            cohort.integrity_valid
        ),
        "pairs": [
            {
                "test_case_id": pair.test_case_id,
                "baseline": _side_snapshot(
                    pair.baseline
                ),
                "candidate": _side_snapshot(
                    pair.candidate
                ),
                "usable": pair.usable,
                "delta": pair.delta,
            }
            for pair
            in cohort.pairs
        ],
    }


def _statistics_snapshot(
    statistics: ASRDirectionalMetricStatistics,
) -> dict[str, object]:
    descriptive = statistics.statistics

    return {
        "total_cases": descriptive.total_cases,
        "usable_pairs": descriptive.usable_pairs,
        "incomplete_pairs": (
            descriptive.incomplete_pairs
        ),
        "complete": descriptive.complete,
        "integrity_valid": (
            descriptive.integrity_valid
        ),
        "baseline_mean": (
            descriptive.baseline_mean
        ),
        "candidate_mean": (
            descriptive.candidate_mean
        ),
        "mean_delta": descriptive.mean_delta,
        "median_delta": (
            descriptive.median_delta
        ),
        "minimum_delta": (
            descriptive.minimum_delta
        ),
        "maximum_delta": (
            descriptive.maximum_delta
        ),
        "candidate_lower_count": (
            descriptive.candidate_lower_count
        ),
        "candidate_higher_count": (
            descriptive.candidate_higher_count
        ),
        "improved_count": (
            statistics.improved_count
        ),
        "regressed_count": (
            statistics.regressed_count
        ),
        "unchanged_count": (
            statistics.unchanged_count
        ),
    }


def _interval_snapshot(
    interval: PairedMeanDeltaInterval,
) -> dict[str, object]:
    return {
        "method": interval.method.value,
        "confidence_level": (
            interval.confidence_level
        ),
        "minimum_usable_pairs": (
            interval.minimum_usable_pairs
        ),
        "resamples": interval.resamples,
        "random_seed": interval.random_seed,
        "total_cases": interval.total_cases,
        "usable_pairs": interval.usable_pairs,
        "integrity": interval.integrity.value,
        "evidence": interval.evidence.value,
        "reason": interval.reason.value,
        "ready": interval.ready,
        "mean_delta": interval.mean_delta,
        "lower_bound": interval.lower_bound,
        "upper_bound": interval.upper_bound,
    }


def _metric_snapshot(
    *,
    cohort: MatchedObservationCohort,
    statistics: ASRDirectionalMetricStatistics,
    assessment: ASRMetricNoninferiorityAssessment,
) -> dict[str, object]:
    return {
        "cohort": _cohort_snapshot(
            cohort
        ),
        "statistics": _statistics_snapshot(
            statistics
        ),
        "noninferiority": {
            "margin": (
                assessment
                .noninferiority_margin
            ),
            "interval": _interval_snapshot(
                assessment.interval
            ),
            "claim": assessment.claim.value,
        },
    }


def _normalize_bindings(
    *,
    bindings: tuple[
        ASRMatchedCaseEvidenceBinding,
        ...,
    ],
    declared_test_case_ids: tuple[int, ...],
) -> tuple[
    ASRMatchedCaseEvidenceBinding,
    ...,
]:
    if not isinstance(
        bindings,
        tuple,
    ):
        raise HveeContractError(
            "matched release evidence bindings "
            "must be a tuple"
        )

    if not all(
        isinstance(
            binding,
            ASRMatchedCaseEvidenceBinding,
        )
        for binding
        in bindings
    ):
        raise HveeContractError(
            "matched release evidence bindings "
            "contain an invalid binding"
        )

    binding_ids = tuple(
        binding.test_case_id
        for binding
        in bindings
    )

    if len(binding_ids) != len(
        set(binding_ids)
    ):
        raise HveeContractError(
            "matched release evidence bindings "
            "contain duplicate test-case ids"
        )

    ordered = tuple(
        sorted(
            bindings,
            key=lambda item: item.test_case_id,
        )
    )

    if tuple(
        binding.test_case_id
        for binding
        in ordered
    ) != declared_test_case_ids:
        raise HveeContractError(
            "matched release evidence bindings "
            "must exactly cover the declared cohort"
        )

    return ordered


def _enabled_metric_snapshots(
    *,
    cohorts: ASRMatchedQualityCohorts,
    statistics: ASRMatchedQualityStatistics,
    result: ASRMatchedReleaseDecisionResult,
) -> dict[str, object]:
    wer = None

    if (
        result.assurance.normalized_wer
        is not None
    ):
        wer = _metric_snapshot(
            cohort=cohorts.normalized_wer,
            statistics=statistics.normalized_wer,
            assessment=(
                result.assurance.normalized_wer
            ),
        )

    cer = None

    if (
        result.assurance.normalized_cer
        is not None
    ):
        cer = _metric_snapshot(
            cohort=cohorts.normalized_cer,
            statistics=statistics.normalized_cer,
            assessment=(
                result.assurance.normalized_cer
            ),
        )

    return {
        "normalized_wer": wer,
        "normalized_cer": cer,
    }


def build_asr_matched_release_decision_evidence(
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    declared_test_case_ids: tuple[int, ...],
    records: tuple[
        ObservationEvidenceRecord,
        ...,
    ],
    evidence_bindings: tuple[
        ASRMatchedCaseEvidenceBinding,
        ...,
    ],
    policy: ASRMatchedReleaseAssurancePolicyV1,
) -> ASRMatchedReleaseDecisionEvidenceBundle:
    """
    Rebuild the complete matched ASR release decision from raw inputs.

    Precomputed cohorts, statistics, assurance assessments, or verdicts
    are intentionally not accepted. This prevents a caller from
    rebinding legitimate evidence identities to fabricated scientific
    results.

    The application layer remains responsible for verifying that each
    evidence binding actually belongs to its persisted result
    provenance and observation bundle.
    """

    if not isinstance(
        policy,
        ASRMatchedReleaseAssurancePolicyV1,
    ):
        raise HveeContractError(
            "ASR matched release evidence requires "
            "ASRMatchedReleaseAssurancePolicyV1"
        )

    cohorts = (
        build_asr_matched_quality_cohorts(
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            declared_test_case_ids=(
                declared_test_case_ids
            ),
            records=records,
        )
    )

    bindings = _normalize_bindings(
        bindings=evidence_bindings,
        declared_test_case_ids=(
            cohorts.declared_test_case_ids
        ),
    )

    statistics = (
        summarize_asr_matched_quality(
            cohorts
        )
    )

    result = (
        evaluate_asr_matched_release_decision(
            cohorts=cohorts,
            policy=policy,
        )
    )

    policy_snapshot = (
        build_asr_matched_release_policy_snapshot(
            policy
        )
    )

    policy_sha256 = calculate_policy_sha256(
        policy_key=policy.key,
        policy_version=policy.version,
        policy_snapshot=policy_snapshot,
    )

    payload = {
        "schema_version": (
            ASR_MATCHED_RELEASE_DECISION_EVIDENCE_SCHEMA_VERSION
        ),
        "evaluation_type": "asr",
        "target": {
            "baseline_run_id": (
                cohorts.baseline_run_id
            ),
            "candidate_run_id": (
                cohorts.candidate_run_id
            ),
            "declared_test_case_ids": list(
                cohorts.declared_test_case_ids
            ),
        },
        "policy": {
            "key": policy.key,
            "version": policy.version,
            "snapshot": policy_snapshot,
            "sha256": policy_sha256,
        },
        "evidence_bindings": [
            _binding_snapshot(binding)
            for binding
            in bindings
        ],
        "metrics": (
            _enabled_metric_snapshots(
                cohorts=cohorts,
                statistics=statistics,
                result=result,
            )
        ),
        "assessments": {
            "integrity": (
                result
                .assurance
                .integrity
                .value
            ),
            "evidence": (
                result
                .assurance
                .evidence
                .value
            ),
            "critical": (
                result.critical.value
            ),
            "claim": (
                result
                .assurance
                .claim
                .value
            ),
        },
        "decision": {
            "verdict": (
                result.decision.verdict.value
            ),
            "reason": (
                result.decision.reason.value
            ),
        },
    }

    canonical_payload = (
        _canonicalize_json_value(
            payload,
            name=(
                "ASR matched release "
                "decision evidence payload"
            ),
        )
    )

    if not isinstance(
        canonical_payload,
        dict,
    ):
        raise HveeContractError(
            "ASR matched release evidence "
            "must canonicalize to a JSON object"
        )

    return (
        ASRMatchedReleaseDecisionEvidenceBundle(
            payload=canonical_payload,
            policy_sha256=policy_sha256,
            decision_sha256=(
                calculate_decision_sha256(
                    canonical_payload
                )
            ),
        )
    )


def verify_asr_matched_release_decision_evidence(
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    declared_test_case_ids: tuple[int, ...],
    records: tuple[
        ObservationEvidenceRecord,
        ...,
    ],
    evidence_bindings: tuple[
        ASRMatchedCaseEvidenceBinding,
        ...,
    ],
    policy: ASRMatchedReleaseAssurancePolicyV1,
    payload: object,
    expected_decision_sha256: object,
) -> ASRMatchedReleaseDecisionEvidenceBundle:
    """
    Verify hash integrity and reproducibly rebuild the full decision.

    Recomputing a SHA over a modified caller payload is insufficient:
    the supplied payload must also exactly equal the result rebuilt
    from the raw records, evidence bindings, and explicit policy.
    """

    expected_digest = _require_sha256_hex(
        name=(
            "expected ASR matched release "
            "decision SHA-256"
        ),
        value=expected_decision_sha256,
    )

    supplied_payload = (
        _canonicalize_json_value(
            payload,
            name=(
                "supplied ASR matched release "
                "decision evidence payload"
            ),
        )
    )

    if not isinstance(
        supplied_payload,
        dict,
    ):
        raise HveeContractError(
            "supplied ASR matched release "
            "evidence payload must be a JSON object"
        )

    supplied_digest = (
        calculate_decision_sha256(
            supplied_payload
        )
    )

    if supplied_digest != expected_digest:
        raise HveeContractError(
            "supplied ASR matched release evidence "
            "does not match expected SHA-256"
        )

    rebuilt = (
        build_asr_matched_release_decision_evidence(
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            declared_test_case_ids=(
                declared_test_case_ids
            ),
            records=records,
            evidence_bindings=evidence_bindings,
            policy=policy,
        )
    )

    if supplied_payload != rebuilt.payload:
        raise HveeContractError(
            "ASR matched release evidence does not "
            "match reproducibly rebuilt evidence"
        )

    if (
        expected_digest
        != rebuilt.decision_sha256
    ):
        raise HveeContractError(
            "ASR matched release decision SHA-256 "
            "does not match reproducibly rebuilt evidence"
        )

    return rebuilt
