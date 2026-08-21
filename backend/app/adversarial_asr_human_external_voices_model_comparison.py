"""Compare two complete VOiCES matched-control model metric bundles.

This I4e-B8 layer consumes two complete, reverified B7 metric bundles that
were produced from the exact same frozen 32-case/16-pair VOiCES suite.  The
provider/model identities must be distinct.  It calculates candidate-minus-
baseline deltas for every case and difference-in-differences for babble
sensitivity on every matched pair.

The artifact is descriptive evidence only.  It does not embed transcript
text or audio, apply thresholds, claim statistical significance, choose a
winner, qualify a model, persist state, or alter release authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

from app.adversarial_asr_human_external_voices_matched_control_metrics import (
    ASRAdversarialVOiCESMatchedControlCaseMetrics,
    ASRAdversarialVOiCESMatchedControlMetricsBundle,
    ASRAdversarialVOiCESMatchedControlMetricsError,
    ASRAdversarialVOiCESMatchedControlPairMetrics,
)
from app.adversarial_asr_human_external_voices_matched_control_projection import (
    ASRAdversarialVOiCESMatchedControlPairKey,
)
from app.adversarial_asr_human_external_voices_matched_control_suite_projection import (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
)


ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_KEY = (
    "hetren.asr.adversarial-human-external-"
    "voices-babble-matched-control-model-comparison"
)


class ASRAdversarialVOiCESModelComparisonError(ValueError):
    """Raised when two B7 bundles cannot form a trusted comparison."""


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ASRAdversarialVOiCESModelComparisonError(
            f"{name} must be a lowercase SHA-256."
        )
    return value


def _require_text(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialVOiCESModelComparisonError(
            f"{name} must be non-empty trimmed text."
        )
    return value


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
        raise ASRAdversarialVOiCESModelComparisonError(
            "VOiCES model comparison must be deterministic JSON."
        ) from error


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        raise ASRAdversarialVOiCESModelComparisonError(
            "VOiCES model comparison mean requires values."
        )
    return math.fsum(values) / len(values)


def _model_identity(
    metrics: ASRAdversarialVOiCESMatchedControlMetricsBundle,
) -> tuple[str, str]:
    definition = metrics.campaign.campaign.definition
    return (definition.provider_key, definition.model_key)


def _reverify_metrics(
    *,
    role: str,
    value: object,
) -> ASRAdversarialVOiCESMatchedControlMetricsBundle:
    if not isinstance(value, ASRAdversarialVOiCESMatchedControlMetricsBundle):
        raise ASRAdversarialVOiCESModelComparisonError(
            f"VOiCES {role} requires the exact B7 metrics bundle."
        )

    try:
        reverified = ASRAdversarialVOiCESMatchedControlMetricsBundle(
            matched_control_campaign_sha256=(
                value.matched_control_campaign_sha256
            ),
            campaign=value.campaign,
            cases=value.cases,
            pairs=value.pairs,
        )
    except (ASRAdversarialVOiCESMatchedControlMetricsError, ValueError) as error:
        raise ASRAdversarialVOiCESModelComparisonError(
            f"VOiCES {role} B7 metrics failed revalidation."
        ) from error

    if reverified.sha256 != value.sha256:
        raise ASRAdversarialVOiCESModelComparisonError(
            f"VOiCES {role} B7 metrics identity changed."
        )
    return reverified


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESModelIdentity:
    """Identity and evidence commitments for one comparison role."""

    campaign_id: str
    campaign_version: str
    provider_key: str
    model_key: str
    campaign_sha256: str
    metrics_sha256: str

    def __post_init__(self) -> None:
        for name, value in (
            ("campaign id", self.campaign_id),
            ("campaign version", self.campaign_version),
            ("provider key", self.provider_key),
            ("model key", self.model_key),
        ):
            _require_text(name=f"VOiCES model {name}", value=value)

        _require_sha256(
            name="VOiCES model campaign",
            value=self.campaign_sha256,
        )
        _require_sha256(
            name="VOiCES model metrics",
            value=self.metrics_sha256,
        )

    @property
    def provider_model(self) -> tuple[str, str]:
        return (self.provider_key, self.model_key)


def _identity(
    metrics: ASRAdversarialVOiCESMatchedControlMetricsBundle,
) -> ASRAdversarialVOiCESModelIdentity:
    definition = metrics.campaign.campaign.definition
    return ASRAdversarialVOiCESModelIdentity(
        campaign_id=definition.campaign_id,
        campaign_version=definition.campaign_version,
        provider_key=definition.provider_key,
        model_key=definition.model_key,
        campaign_sha256=metrics.campaign.sha256,
        metrics_sha256=metrics.sha256,
    )


def _identity_payload(
    value: ASRAdversarialVOiCESModelIdentity,
) -> dict[str, str]:
    return {
        "campaign_id": value.campaign_id,
        "campaign_version": value.campaign_version,
        "provider_key": value.provider_key,
        "model_key": value.model_key,
        "campaign_sha256": value.campaign_sha256,
        "metrics_sha256": value.metrics_sha256,
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESCaseModelComparison:
    """Candidate-minus-baseline metrics for one identical audio case."""

    pair_key: ASRAdversarialVOiCESMatchedControlPairKey
    arm: str
    case_id: str
    audio_asset_sha256: str
    reference_transcript_sha256: str
    baseline: ASRAdversarialVOiCESMatchedControlCaseMetrics
    candidate: ASRAdversarialVOiCESMatchedControlCaseMetrics

    def __post_init__(self) -> None:
        if not isinstance(
            self.pair_key,
            ASRAdversarialVOiCESMatchedControlPairKey,
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES case comparison pair key is invalid."
            )

        if self.arm not in {
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
        }:
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES case comparison arm is invalid."
            )

        _require_text(name="VOiCES comparison case id", value=self.case_id)
        _require_sha256(
            name="VOiCES comparison audio asset",
            value=self.audio_asset_sha256,
        )
        _require_sha256(
            name="VOiCES comparison reference transcript",
            value=self.reference_transcript_sha256,
        )

        if (
            not isinstance(
                self.baseline,
                ASRAdversarialVOiCESMatchedControlCaseMetrics,
            )
            or not isinstance(
                self.candidate,
                ASRAdversarialVOiCESMatchedControlCaseMetrics,
            )
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES case comparison metrics are invalid."
            )

        shared = (
            self.pair_key,
            self.arm,
            self.case_id,
            self.audio_asset_sha256,
            self.reference_transcript_sha256,
        )
        baseline_shared = (
            self.baseline.pair_key,
            self.baseline.arm,
            self.baseline.case_id,
            self.baseline.audio_asset_sha256,
            self.baseline.reference_transcript_sha256,
        )
        candidate_shared = (
            self.candidate.pair_key,
            self.candidate.arm,
            self.candidate.case_id,
            self.candidate.audio_asset_sha256,
            self.candidate.reference_transcript_sha256,
        )

        if (
            baseline_shared != shared
            or candidate_shared != shared
            or self.baseline.normalized_reference_sha256
            != self.candidate.normalized_reference_sha256
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES case comparison did not hold input evidence constant."
            )

    @property
    def wer_delta(self) -> float:
        return self.candidate.evaluation.wer - self.baseline.evaluation.wer

    @property
    def cer_delta(self) -> float:
        return self.candidate.evaluation.cer - self.baseline.evaluation.cer

    @property
    def substitutions_delta(self) -> int:
        return (
            self.candidate.evaluation.substitutions
            - self.baseline.evaluation.substitutions
        )

    @property
    def insertions_delta(self) -> int:
        return (
            self.candidate.evaluation.insertions
            - self.baseline.evaluation.insertions
        )

    @property
    def deletions_delta(self) -> int:
        return (
            self.candidate.evaluation.deletions
            - self.baseline.evaluation.deletions
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESPairModelComparison:
    """Difference-in-differences for one exact matched-control pair."""

    key: ASRAdversarialVOiCESMatchedControlPairKey
    baseline: ASRAdversarialVOiCESMatchedControlPairMetrics
    candidate: ASRAdversarialVOiCESMatchedControlPairMetrics

    def __post_init__(self) -> None:
        if not isinstance(
            self.key,
            ASRAdversarialVOiCESMatchedControlPairKey,
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES pair comparison key is invalid."
            )
        if (
            not isinstance(
                self.baseline,
                ASRAdversarialVOiCESMatchedControlPairMetrics,
            )
            or not isinstance(
                self.candidate,
                ASRAdversarialVOiCESMatchedControlPairMetrics,
            )
            or self.baseline.key != self.key
            or self.candidate.key != self.key
            or self.baseline.babble.audio_asset_sha256
            != self.candidate.babble.audio_asset_sha256
            or self.baseline.control.audio_asset_sha256
            != self.candidate.control.audio_asset_sha256
            or self.baseline.babble.reference_transcript_sha256
            != self.candidate.babble.reference_transcript_sha256
            or self.baseline.control.reference_transcript_sha256
            != self.candidate.control.reference_transcript_sha256
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES pair comparison did not hold matched inputs constant."
            )

    @property
    def wer_degradation_delta(self) -> float:
        return self.candidate.wer_delta - self.baseline.wer_delta

    @property
    def cer_degradation_delta(self) -> float:
        return self.candidate.cer_delta - self.baseline.cer_delta

    @property
    def substitutions_degradation_delta(self) -> int:
        return (
            self.candidate.substitutions_delta
            - self.baseline.substitutions_delta
        )

    @property
    def insertions_degradation_delta(self) -> int:
        return (
            self.candidate.insertions_delta
            - self.baseline.insertions_delta
        )

    @property
    def deletions_degradation_delta(self) -> int:
        return (
            self.candidate.deletions_delta
            - self.baseline.deletions_delta
        )


def _pair_key_payload(
    key: ASRAdversarialVOiCESMatchedControlPairKey,
) -> dict[str, object]:
    return {
        "source_key": list(key.source_key),
        "room": key.room,
        "microphone_id": key.microphone_id,
        "angle_degrees": key.angle_degrees,
    }


def _metric_payload(
    value: ASRAdversarialVOiCESMatchedControlCaseMetrics,
) -> dict[str, object]:
    return {
        "wer": value.evaluation.wer,
        "cer": value.evaluation.cer,
        "substitutions": value.evaluation.substitutions,
        "insertions": value.evaluation.insertions,
        "deletions": value.evaluation.deletions,
    }


def _case_payload(
    value: ASRAdversarialVOiCESCaseModelComparison,
) -> dict[str, object]:
    return {
        "case_id": value.case_id,
        "arm": value.arm,
        "pair_key": _pair_key_payload(value.pair_key),
        "fixed_inputs": {
            "audio_asset_sha256": value.audio_asset_sha256,
            "reference_transcript_sha256": (
                value.reference_transcript_sha256
            ),
            "normalized_reference_utf8_sha256": (
                value.baseline.normalized_reference_sha256
            ),
        },
        "baseline_outputs": {
            "generated_transcript_sha256": (
                value.baseline.generated_transcript_sha256
            ),
            "normalized_generated_utf8_sha256": (
                value.baseline.normalized_generated_sha256
            ),
            "execution_evidence_sha256": (
                value.baseline.execution_evidence_sha256
            ),
        },
        "candidate_outputs": {
            "generated_transcript_sha256": (
                value.candidate.generated_transcript_sha256
            ),
            "normalized_generated_utf8_sha256": (
                value.candidate.normalized_generated_sha256
            ),
            "execution_evidence_sha256": (
                value.candidate.execution_evidence_sha256
            ),
        },
        "baseline": _metric_payload(value.baseline),
        "candidate": _metric_payload(value.candidate),
        "candidate_minus_baseline": {
            "wer": value.wer_delta,
            "cer": value.cer_delta,
            "substitutions": value.substitutions_delta,
            "insertions": value.insertions_delta,
            "deletions": value.deletions_delta,
        },
    }


def _pair_metric_payload(
    value: ASRAdversarialVOiCESMatchedControlPairMetrics,
) -> dict[str, object]:
    return {
        "babble_minus_control": {
            "wer": value.wer_delta,
            "cer": value.cer_delta,
            "substitutions": value.substitutions_delta,
            "insertions": value.insertions_delta,
            "deletions": value.deletions_delta,
        }
    }


def _pair_payload(
    value: ASRAdversarialVOiCESPairModelComparison,
) -> dict[str, object]:
    return {
        "pair_key": _pair_key_payload(value.key),
        "baseline": _pair_metric_payload(value.baseline),
        "candidate": _pair_metric_payload(value.candidate),
        "candidate_minus_baseline_noise_degradation": {
            "wer": value.wer_degradation_delta,
            "cer": value.cer_degradation_delta,
            "substitutions": value.substitutions_degradation_delta,
            "insertions": value.insertions_degradation_delta,
            "deletions": value.deletions_degradation_delta,
        },
    }


def _direction_counts(values: tuple[float, ...]) -> dict[str, int]:
    return {
        "candidate_higher": sum(value > 0.0 for value in values),
        "equal": sum(value == 0.0 for value in values),
        "candidate_lower": sum(value < 0.0 for value in values),
    }


def _case_macro(
    values: tuple[ASRAdversarialVOiCESCaseModelComparison, ...],
) -> dict[str, object]:
    baseline_wer = tuple(value.baseline.evaluation.wer for value in values)
    baseline_cer = tuple(value.baseline.evaluation.cer for value in values)
    candidate_wer = tuple(value.candidate.evaluation.wer for value in values)
    candidate_cer = tuple(value.candidate.evaluation.cer for value in values)
    return {
        "case_count": len(values),
        "baseline": {
            "wer": _mean(baseline_wer),
            "cer": _mean(baseline_cer),
        },
        "candidate": {
            "wer": _mean(candidate_wer),
            "cer": _mean(candidate_cer),
        },
        "candidate_minus_baseline": {
            "wer": _mean(tuple(value.wer_delta for value in values)),
            "cer": _mean(tuple(value.cer_delta for value in values)),
        },
    }


def _alignment_totals(
    values: tuple[ASRAdversarialVOiCESCaseModelComparison, ...],
) -> dict[str, object]:
    def totals(role: str) -> dict[str, int]:
        metrics = tuple(getattr(value, role).evaluation for value in values)
        return {
            "substitutions": sum(value.substitutions for value in metrics),
            "insertions": sum(value.insertions for value in metrics),
            "deletions": sum(value.deletions for value in metrics),
        }

    baseline = totals("baseline")
    candidate = totals("candidate")
    return {
        "baseline": baseline,
        "candidate": candidate,
        "candidate_minus_baseline": {
            key: candidate[key] - baseline[key]
            for key in ("substitutions", "insertions", "deletions")
        },
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESModelComparisonBundle:
    """Deterministic two-model comparison on the same VOiCES evidence."""

    baseline_metrics_sha256: str
    candidate_metrics_sha256: str
    baseline: ASRAdversarialVOiCESMatchedControlMetricsBundle
    candidate: ASRAdversarialVOiCESMatchedControlMetricsBundle
    cases: tuple[ASRAdversarialVOiCESCaseModelComparison, ...]
    pairs: tuple[ASRAdversarialVOiCESPairModelComparison, ...]

    development_evidence_only: bool = True
    both_metrics_reverified: bool = True
    fixed_inputs_verified: bool = True
    distinct_model_identities_verified: bool = True
    paired_model_deltas_computed: bool = True
    statistical_significance_claimed: bool = False
    qualification_threshold_applied: bool = False
    model_winner_declared: bool = False
    production_qualified: bool = False
    release_enforcement_eligible: bool = False
    official_release_verdict_modified: bool = False

    def __post_init__(self) -> None:
        _require_sha256(
            name="VOiCES baseline B7 metrics",
            value=self.baseline_metrics_sha256,
        )
        _require_sha256(
            name="VOiCES candidate B7 metrics",
            value=self.candidate_metrics_sha256,
        )

        baseline = _reverify_metrics(role="baseline", value=self.baseline)
        candidate = _reverify_metrics(role="candidate", value=self.candidate)

        if (
            self.baseline_metrics_sha256 != baseline.sha256
            or self.candidate_metrics_sha256 != candidate.sha256
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES B7 metrics commitments changed."
            )

        if _model_identity(baseline) == _model_identity(candidate):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES comparison requires distinct provider/model identities."
            )

        if (
            baseline.campaign.matched_control_suite_sha256
            != candidate.campaign.matched_control_suite_sha256
            or baseline.campaign.suite.sha256 != candidate.campaign.suite.sha256
            or baseline.campaign.suite.evidence.sha256
            != candidate.campaign.suite.evidence.sha256
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES comparison requires the exact same frozen suite."
            )

        if (
            not isinstance(self.cases, tuple)
            or len(self.cases)
            != ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
            or any(
                not isinstance(value, ASRAdversarialVOiCESCaseModelComparison)
                for value in self.cases
            )
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES model comparison case population changed."
            )

        if (
            not isinstance(self.pairs, tuple)
            or len(self.pairs)
            != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
            or any(
                not isinstance(value, ASRAdversarialVOiCESPairModelComparison)
                for value in self.pairs
            )
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES model comparison pair population changed."
            )

        for expected_baseline, expected_candidate, observed in zip(
            baseline.cases,
            candidate.cases,
            self.cases,
            strict=True,
        ):
            if (
                observed.baseline != expected_baseline
                or observed.candidate != expected_candidate
            ):
                raise ASRAdversarialVOiCESModelComparisonError(
                    "VOiCES model comparison case ordering changed."
                )

        for expected_baseline, expected_candidate, observed in zip(
            baseline.pairs,
            candidate.pairs,
            self.pairs,
            strict=True,
        ):
            if (
                observed.baseline != expected_baseline
                or observed.candidate != expected_candidate
            ):
                raise ASRAdversarialVOiCESModelComparisonError(
                    "VOiCES model comparison pair ordering changed."
                )

        positive_authority = (
            self.development_evidence_only,
            self.both_metrics_reverified,
            self.fixed_inputs_verified,
            self.distinct_model_identities_verified,
            self.paired_model_deltas_computed,
        )
        negative_authority = (
            self.statistical_significance_claimed,
            self.qualification_threshold_applied,
            self.model_winner_declared,
            self.production_qualified,
            self.release_enforcement_eligible,
            self.official_release_verdict_modified,
        )
        if (
            any(value is not True for value in positive_authority)
            or any(value is not False for value in negative_authority)
        ):
            raise ASRAdversarialVOiCESModelComparisonError(
                "VOiCES model comparison authority boundary changed."
            )

    @property
    def baseline_identity(self) -> ASRAdversarialVOiCESModelIdentity:
        return _identity(self.baseline)

    @property
    def candidate_identity(self) -> ASRAdversarialVOiCESModelIdentity:
        return _identity(self.candidate)

    @property
    def aggregate(self) -> dict[str, object]:
        babble = tuple(
            value
            for value in self.cases
            if value.arm
            == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
        )
        control = tuple(
            value
            for value in self.cases
            if value.arm
            == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
        )
        wer_deltas = tuple(value.wer_delta for value in self.cases)
        cer_deltas = tuple(value.cer_delta for value in self.cases)
        pair_wer = tuple(value.wer_degradation_delta for value in self.pairs)
        pair_cer = tuple(value.cer_degradation_delta for value in self.pairs)

        return {
            "case_macro_mean": {
                "all": _case_macro(self.cases),
                "babble": _case_macro(babble),
                "control": _case_macro(control),
            },
            "case_direction_counts": {
                "wer": _direction_counts(wer_deltas),
                "cer": _direction_counts(cer_deltas),
            },
            "word_alignment_totals": _alignment_totals(self.cases),
            "pair_noise_degradation_macro_mean": {
                "baseline_babble_minus_control": {
                    "wer": _mean(
                        tuple(value.baseline.wer_delta for value in self.pairs)
                    ),
                    "cer": _mean(
                        tuple(value.baseline.cer_delta for value in self.pairs)
                    ),
                },
                "candidate_babble_minus_control": {
                    "wer": _mean(
                        tuple(value.candidate.wer_delta for value in self.pairs)
                    ),
                    "cer": _mean(
                        tuple(value.candidate.cer_delta for value in self.pairs)
                    ),
                },
                "candidate_minus_baseline": {
                    "wer": _mean(pair_wer),
                    "cer": _mean(pair_cer),
                },
            },
            "pair_noise_degradation_direction_counts": {
                "wer": _direction_counts(pair_wer),
                "cer": _direction_counts(pair_cer),
            },
        }

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema_version": ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_SCHEMA_VERSION,
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_KEY,
                "version": ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_VERSION,
                "type": "reverified_matched_control_model_comparison",
            },
            "upstream": {
                "matched_control_suite_sha256": (
                    self.baseline.campaign.matched_control_suite_sha256
                ),
                "adversarial_suite_evidence_sha256": (
                    self.baseline.campaign.suite.evidence.sha256
                ),
                "baseline_metrics_sha256": self.baseline_metrics_sha256,
                "candidate_metrics_sha256": self.candidate_metrics_sha256,
            },
            "models": {
                "baseline": _identity_payload(self.baseline_identity),
                "candidate": _identity_payload(self.candidate_identity),
            },
            "methodology": {
                "case_delta": "candidate_minus_baseline",
                "pair_noise_degradation": "babble_minus_control",
                "difference_in_differences": (
                    "candidate_babble_minus_control_minus_"
                    "baseline_babble_minus_control"
                ),
                "lower_metric_values_are_better": True,
                "equal_case_weighting": True,
                "raw_transcripts_compared": False,
                "precomputed_b7_metrics_reverified": True,
            },
            "cases": [_case_payload(value) for value in self.cases],
            "pairs": [_pair_payload(value) for value in self.pairs],
            "aggregate": self.aggregate,
            "evidence_boundary": {
                "development_evidence_only": True,
                "both_metrics_reverified": True,
                "fixed_inputs_verified": True,
                "distinct_model_identities_verified": True,
                "paired_model_deltas_computed": True,
                "raw_audio_embedded": False,
                "absolute_audio_paths_embedded": False,
                "raw_reference_transcripts_embedded": False,
                "raw_generated_transcripts_embedded": False,
                "statistical_significance_claimed": False,
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

    def require_model_winner_declared(self) -> None:
        raise ASRAdversarialVOiCESModelComparisonError(
            "VOiCES B8 is descriptive comparison evidence; no threshold, "
            "statistical significance claim, or model winner was declared."
        )


def build_asr_adversarial_voices_model_comparison_v1(
    *,
    baseline: ASRAdversarialVOiCESMatchedControlMetricsBundle,
    candidate: ASRAdversarialVOiCESMatchedControlMetricsBundle,
) -> ASRAdversarialVOiCESModelComparisonBundle:
    """Build deterministic comparison evidence from two complete B7 bundles."""

    baseline_verified = _reverify_metrics(role="baseline", value=baseline)
    candidate_verified = _reverify_metrics(role="candidate", value=candidate)

    cases = tuple(
        ASRAdversarialVOiCESCaseModelComparison(
            pair_key=baseline_case.pair_key,
            arm=baseline_case.arm,
            case_id=baseline_case.case_id,
            audio_asset_sha256=baseline_case.audio_asset_sha256,
            reference_transcript_sha256=(
                baseline_case.reference_transcript_sha256
            ),
            baseline=baseline_case,
            candidate=candidate_case,
        )
        for baseline_case, candidate_case in zip(
            baseline_verified.cases,
            candidate_verified.cases,
            strict=True,
        )
    )

    pairs = tuple(
        ASRAdversarialVOiCESPairModelComparison(
            key=baseline_pair.key,
            baseline=baseline_pair,
            candidate=candidate_pair,
        )
        for baseline_pair, candidate_pair in zip(
            baseline_verified.pairs,
            candidate_verified.pairs,
            strict=True,
        )
    )

    return ASRAdversarialVOiCESModelComparisonBundle(
        baseline_metrics_sha256=baseline_verified.sha256,
        candidate_metrics_sha256=candidate_verified.sha256,
        baseline=baseline_verified,
        candidate=candidate_verified,
        cases=cases,
        pairs=pairs,
    )
