"""Seal normalized WER/CER evidence for the complete VOiCES campaign.

This I4e-B7 layer consumes only a complete, reverified B6 campaign.  It uses
Hetren's existing normalized transcript evaluator v1.0.0 for all 32 cases,
binds every result to its execution evidence, and calculates the 16 exact
babble-minus-control paired deltas.

The artifact contains metric values and transcript commitments, never raw or
normalized transcript text.  It does not apply thresholds, issue a model
verdict, certify production use, persist database state, or alter release
authority.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math

from app.adversarial_asr_human_external_voices_matched_control_campaign_service import (
    ASRAdversarialVOiCESMatchedControlCampaignBundle,
    ASRAdversarialVOiCESMatchedControlCampaignError,
)
from app.adversarial_asr_human_external_voices_matched_control_projection import (
    ASRAdversarialVOiCESMatchedControlPairKey,
)
from app.adversarial_asr_human_external_voices_matched_control_suite_projection import (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
)
from hvee.packs.asr import (
    ASRNormalizedTextEvaluation,
    BASIC_TEXT_NORMALIZATION,
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
    NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
    calculate_asr_adversarial_transcript_sha256,
    evaluate_normalized_transcript_pair,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
)


ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_KEY = (
    "hetren.asr.adversarial-human-external-"
    "voices-babble-matched-control-normalized-metrics"
)


class ASRAdversarialVOiCESMatchedControlMetricsError(ValueError):
    """Raised when complete B6 results cannot form trusted B7 metrics."""


def _require_sha256(
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
        raise ASRAdversarialVOiCESMatchedControlMetricsError(
            f"{name} must be a lowercase SHA-256."
        )

    return value


def _require_metric(
    *,
    name: str,
    value: object,
) -> float:
    if (
        not isinstance(value, float)
        or not math.isfinite(value)
        or value < 0.0
    ):
        raise ASRAdversarialVOiCESMatchedControlMetricsError(
            f"{name} must be a finite non-negative float."
        )

    return value


def _require_count(
    *,
    name: str,
    value: object,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise ASRAdversarialVOiCESMatchedControlMetricsError(
            f"{name} must be a non-negative integer."
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
        raise ASRAdversarialVOiCESMatchedControlMetricsError(
            "VOiCES matched-control metrics must be deterministic JSON."
        ) from error


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        raise ASRAdversarialVOiCESMatchedControlMetricsError(
            "VOiCES matched-control metric mean requires values."
        )

    return math.fsum(values) / len(values)


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESMatchedControlCaseMetrics:
    """Canonical normalized metrics for one completed B6 execution."""

    pair_key: ASRAdversarialVOiCESMatchedControlPairKey
    arm: str
    case_id: str
    audio_asset_sha256: str
    reference_transcript_sha256: str
    generated_transcript_sha256: str
    execution_evidence_sha256: str
    normalized_reference_sha256: str
    normalized_generated_sha256: str
    evaluation: ASRNormalizedTextEvaluation

    def __post_init__(self) -> None:
        if not isinstance(
            self.pair_key,
            ASRAdversarialVOiCESMatchedControlPairKey,
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES case metrics pair key is invalid."
            )

        if self.arm not in {
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
        }:
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES case metrics arm is invalid."
            )

        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or self.case_id != self.case_id.strip()
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES case metrics identity is invalid."
            )

        for name, value in (
            ("audio asset", self.audio_asset_sha256),
            ("reference transcript", self.reference_transcript_sha256),
            ("generated transcript", self.generated_transcript_sha256),
            ("execution evidence", self.execution_evidence_sha256),
            ("normalized reference", self.normalized_reference_sha256),
            ("normalized generated", self.normalized_generated_sha256),
        ):
            _require_sha256(name=f"VOiCES {name}", value=value)

        if not isinstance(self.evaluation, ASRNormalizedTextEvaluation):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES case metrics evaluation is invalid."
            )

        if (
            self.evaluation.normalization_key
            != BASIC_TEXT_NORMALIZATION.key
            or self.evaluation.normalization_version
            != BASIC_TEXT_NORMALIZATION.version
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES case metrics normalization identity changed."
            )

        _require_metric(name="normalized WER", value=self.evaluation.wer)
        _require_metric(name="normalized CER", value=self.evaluation.cer)
        _require_count(
            name="normalized substitutions",
            value=self.evaluation.substitutions,
        )
        _require_count(
            name="normalized insertions",
            value=self.evaluation.insertions,
        )
        _require_count(
            name="normalized deletions",
            value=self.evaluation.deletions,
        )

        if (
            _text_sha256(self.evaluation.normalized_reference)
            != self.normalized_reference_sha256
            or _text_sha256(self.evaluation.normalized_generated)
            != self.normalized_generated_sha256
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES normalized transcript commitment changed."
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESMatchedControlPairMetrics:
    """One exact babble/no-distractor metric comparison."""

    key: ASRAdversarialVOiCESMatchedControlPairKey
    babble: ASRAdversarialVOiCESMatchedControlCaseMetrics
    control: ASRAdversarialVOiCESMatchedControlCaseMetrics

    def __post_init__(self) -> None:
        if not isinstance(
            self.key,
            ASRAdversarialVOiCESMatchedControlPairKey,
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES pair metrics key is invalid."
            )

        if (
            not isinstance(
                self.babble,
                ASRAdversarialVOiCESMatchedControlCaseMetrics,
            )
            or not isinstance(
                self.control,
                ASRAdversarialVOiCESMatchedControlCaseMetrics,
            )
            or self.babble.pair_key != self.key
            or self.control.pair_key != self.key
            or self.babble.arm
            != ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
            or self.control.arm
            != ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
            or self.babble.reference_transcript_sha256
            != self.control.reference_transcript_sha256
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES pair metric arms are not exact matched controls."
            )

    @property
    def wer_delta(self) -> float:
        return self.babble.evaluation.wer - self.control.evaluation.wer

    @property
    def cer_delta(self) -> float:
        return self.babble.evaluation.cer - self.control.evaluation.cer

    @property
    def substitutions_delta(self) -> int:
        return (
            self.babble.evaluation.substitutions
            - self.control.evaluation.substitutions
        )

    @property
    def insertions_delta(self) -> int:
        return (
            self.babble.evaluation.insertions
            - self.control.evaluation.insertions
        )

    @property
    def deletions_delta(self) -> int:
        return (
            self.babble.evaluation.deletions
            - self.control.evaluation.deletions
        )


def _case_payload(
    value: ASRAdversarialVOiCESMatchedControlCaseMetrics,
) -> dict[str, object]:
    return {
        "case_id": value.case_id,
        "arm": value.arm,
        "pair_key": {
            "source_key": list(value.pair_key.source_key),
            "room": value.pair_key.room,
            "microphone_id": value.pair_key.microphone_id,
            "angle_degrees": value.pair_key.angle_degrees,
        },
        "bindings": {
            "audio_asset_sha256": value.audio_asset_sha256,
            "reference_transcript_sha256": (
                value.reference_transcript_sha256
            ),
            "generated_transcript_sha256": (
                value.generated_transcript_sha256
            ),
            "execution_evidence_sha256": value.execution_evidence_sha256,
        },
        "normalization": {
            "key": value.evaluation.normalization_key,
            "version": value.evaluation.normalization_version,
            "normalized_reference_utf8_sha256": (
                value.normalized_reference_sha256
            ),
            "normalized_generated_utf8_sha256": (
                value.normalized_generated_sha256
            ),
        },
        "metrics": {
            "wer": value.evaluation.wer,
            "cer": value.evaluation.cer,
            "substitutions": value.evaluation.substitutions,
            "insertions": value.evaluation.insertions,
            "deletions": value.evaluation.deletions,
        },
    }


def _pair_payload(
    value: ASRAdversarialVOiCESMatchedControlPairMetrics,
) -> dict[str, object]:
    return {
        "pair_key": {
            "source_key": list(value.key.source_key),
            "room": value.key.room,
            "microphone_id": value.key.microphone_id,
            "angle_degrees": value.key.angle_degrees,
        },
        "babble_case_id": value.babble.case_id,
        "control_case_id": value.control.case_id,
        "babble": {
            "wer": value.babble.evaluation.wer,
            "cer": value.babble.evaluation.cer,
            "substitutions": value.babble.evaluation.substitutions,
            "insertions": value.babble.evaluation.insertions,
            "deletions": value.babble.evaluation.deletions,
        },
        "control": {
            "wer": value.control.evaluation.wer,
            "cer": value.control.evaluation.cer,
            "substitutions": value.control.evaluation.substitutions,
            "insertions": value.control.evaluation.insertions,
            "deletions": value.control.evaluation.deletions,
        },
        "babble_minus_control": {
            "wer": value.wer_delta,
            "cer": value.cer_delta,
            "substitutions": value.substitutions_delta,
            "insertions": value.insertions_delta,
            "deletions": value.deletions_delta,
        },
    }


def _direction_counts(
    values: tuple[float, ...],
) -> dict[str, int]:
    return {
        "babble_higher": sum(value > 0.0 for value in values),
        "equal": sum(value == 0.0 for value in values),
        "babble_lower": sum(value < 0.0 for value in values),
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESMatchedControlMetricsBundle:
    """Deterministic normalized metric evidence for all 16 exact pairs."""

    matched_control_campaign_sha256: str
    campaign: ASRAdversarialVOiCESMatchedControlCampaignBundle
    cases: tuple[ASRAdversarialVOiCESMatchedControlCaseMetrics, ...]
    pairs: tuple[ASRAdversarialVOiCESMatchedControlPairMetrics, ...]

    development_evidence_only: bool = True
    complete_campaign_reverified: bool = True
    normalized_evaluators_bound: bool = True
    paired_metrics_computed: bool = True
    qualification_threshold_applied: bool = False
    model_verdict_issued: bool = False
    production_qualified: bool = False
    release_enforcement_eligible: bool = False
    official_release_verdict_modified: bool = False

    def __post_init__(self) -> None:
        _require_sha256(
            name="VOiCES matched-control B6 campaign",
            value=self.matched_control_campaign_sha256,
        )

        if not isinstance(
            self.campaign,
            ASRAdversarialVOiCESMatchedControlCampaignBundle,
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES normalized metrics require the exact B6 campaign."
            )

        try:
            reverified_campaign = (
                ASRAdversarialVOiCESMatchedControlCampaignBundle(
                    matched_control_suite_sha256=(
                        self.campaign.matched_control_suite_sha256
                    ),
                    suite=self.campaign.suite,
                    campaign=self.campaign.campaign,
                )
            )
            completed_results = (
                reverified_campaign.require_complete_for_paired_metrics()
            )
        except (
            ASRAdversarialVOiCESMatchedControlCampaignError,
            ValueError,
        ) as error:
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES normalized metrics require a complete reverified "
                "B6 campaign."
            ) from error

        if (
            self.matched_control_campaign_sha256
            != reverified_campaign.sha256
            or reverified_campaign.sha256 != self.campaign.sha256
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES matched-control B6 campaign identity changed."
            )

        if (
            not isinstance(self.cases, tuple)
            or len(self.cases)
            != ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
            or any(
                not isinstance(
                    value,
                    ASRAdversarialVOiCESMatchedControlCaseMetrics,
                )
                for value in self.cases
            )
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES normalized case metric population changed."
            )

        if (
            not isinstance(self.pairs, tuple)
            or len(self.pairs)
            != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
            or any(
                not isinstance(
                    value,
                    ASRAdversarialVOiCESMatchedControlPairMetrics,
                )
                for value in self.pairs
            )
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES normalized pair metric population changed."
            )

        bindings = self.campaign.suite.cases
        expected_case_ids = tuple(
            binding.case.case_id
            for binding in bindings
        )
        observed_case_ids = tuple(value.case_id for value in self.cases)

        if (
            observed_case_ids != expected_case_ids
            or len(set(observed_case_ids)) != len(observed_case_ids)
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES normalized case metric ordering changed."
            )

        result_by_case_id = {
            result.case_id: result
            for result in completed_results
        }

        for binding, value in zip(bindings, self.cases, strict=True):
            result = result_by_case_id[value.case_id]
            expected_evaluation = evaluate_normalized_transcript_pair(
                reference_text=binding.case.reference_transcript,
                generated_text=result.generated_transcript,
            )

            if (
                value.pair_key != binding.pair_key
                or value.arm != binding.arm
                or value.audio_asset_sha256
                != binding.case.audio_asset_sha256
                or value.reference_transcript_sha256
                != binding.reference_transcript_sha256
                or value.generated_transcript_sha256
                != result.execution_definition.generated_transcript_sha256
                or value.generated_transcript_sha256
                != calculate_asr_adversarial_transcript_sha256(
                    result.generated_transcript
                )
                or value.execution_evidence_sha256
                != result.execution_evidence.sha256
                or value.evaluation != expected_evaluation
            ):
                raise ASRAdversarialVOiCESMatchedControlMetricsError(
                    "VOiCES normalized case metric binding changed."
                )

        metrics_by_pair: dict[
            ASRAdversarialVOiCESMatchedControlPairKey,
            dict[str, ASRAdversarialVOiCESMatchedControlCaseMetrics],
        ] = {}

        for value in self.cases:
            metrics_by_pair.setdefault(value.pair_key, {})[
                value.arm
            ] = value

        expected_pairs = tuple(
            ASRAdversarialVOiCESMatchedControlPairMetrics(
                key=key,
                babble=metrics_by_pair[key][
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
                ],
                control=metrics_by_pair[key][
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
                ],
            )
            for key in sorted(metrics_by_pair)
        )

        if self.pairs != expected_pairs:
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES normalized pair metric binding changed."
            )

        arm_counts = Counter(value.arm for value in self.cases)
        if arm_counts != Counter(
            {
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM: 16,
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM: 16,
            }
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES normalized metric arm balance changed."
            )

        positive_authority = (
            self.development_evidence_only,
            self.complete_campaign_reverified,
            self.normalized_evaluators_bound,
            self.paired_metrics_computed,
        )
        negative_authority = (
            self.qualification_threshold_applied,
            self.model_verdict_issued,
            self.production_qualified,
            self.release_enforcement_eligible,
            self.official_release_verdict_modified,
        )

        if (
            any(value is not True for value in positive_authority)
            or any(value is not False for value in negative_authority)
        ):
            raise ASRAdversarialVOiCESMatchedControlMetricsError(
                "VOiCES normalized metric authority boundary changed."
            )

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
        wer_deltas = tuple(value.wer_delta for value in self.pairs)
        cer_deltas = tuple(value.cer_delta for value in self.pairs)

        return {
            "macro_mean": {
                "babble": {
                    "wer": _mean(tuple(x.evaluation.wer for x in babble)),
                    "cer": _mean(tuple(x.evaluation.cer for x in babble)),
                },
                "control": {
                    "wer": _mean(tuple(x.evaluation.wer for x in control)),
                    "cer": _mean(tuple(x.evaluation.cer for x in control)),
                },
                "babble_minus_control": {
                    "wer": _mean(wer_deltas),
                    "cer": _mean(cer_deltas),
                },
            },
            "word_alignment_totals": {
                arm: {
                    "substitutions": sum(
                        x.evaluation.substitutions for x in values
                    ),
                    "insertions": sum(x.evaluation.insertions for x in values),
                    "deletions": sum(x.evaluation.deletions for x in values),
                }
                for arm, values in (
                    ("babble", babble),
                    ("control", control),
                )
            },
            "pair_direction_counts": {
                "wer": _direction_counts(wer_deltas),
                "cer": _direction_counts(cer_deltas),
            },
        }

    @property
    def payload(self) -> dict[str, object]:
        definition = self.campaign.campaign.definition

        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_SCHEMA_VERSION
            ),
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_KEY,
                "version": (
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_VERSION
                ),
                "type": "normalized_babble_control_paired_metrics",
            },
            "upstream": {
                "matched_control_campaign_sha256": (
                    self.matched_control_campaign_sha256
                ),
                "campaign_evidence_sha256": self.campaign.campaign.evidence.sha256,
                "adversarial_suite_evidence_sha256": (
                    self.campaign.suite.evidence.sha256
                ),
            },
            "model_identity": {
                "campaign_id": definition.campaign_id,
                "campaign_version": definition.campaign_version,
                "provider_key": definition.provider_key,
                "model_key": definition.model_key,
            },
            "methodology": {
                "normalization": {
                    "key": BASIC_TEXT_NORMALIZATION.key,
                    "version": BASIC_TEXT_NORMALIZATION.version,
                },
                "wer": {
                    "metric_key": NORMALIZED_WER_METRIC.key,
                    "metric_version": NORMALIZED_WER_METRIC.version,
                    "evaluator_key": NORMALIZED_WER_EVALUATOR.key,
                    "evaluator_version": NORMALIZED_WER_EVALUATOR.version,
                },
                "cer": {
                    "metric_key": NORMALIZED_CER_METRIC.key,
                    "metric_version": NORMALIZED_CER_METRIC.version,
                    "evaluator_key": NORMALIZED_CER_EVALUATOR.key,
                    "evaluator_version": NORMALIZED_CER_EVALUATOR.version,
                },
                "word_alignment": {
                    "evaluator_key": NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key,
                    "evaluator_version": (
                        NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version
                    ),
                    "substitutions": {
                        "metric_key": NORMALIZED_SUBSTITUTIONS_METRIC.key,
                        "metric_version": (
                            NORMALIZED_SUBSTITUTIONS_METRIC.version
                        ),
                    },
                    "insertions": {
                        "metric_key": NORMALIZED_INSERTIONS_METRIC.key,
                        "metric_version": NORMALIZED_INSERTIONS_METRIC.version,
                    },
                    "deletions": {
                        "metric_key": NORMALIZED_DELETIONS_METRIC.key,
                        "metric_version": NORMALIZED_DELETIONS_METRIC.version,
                    },
                },
                "pair_delta_direction": "babble_minus_control",
                "aggregate_method": "equal_weight_macro_mean_over_16_pairs",
            },
            "population": {
                "case_count": len(self.cases),
                "pair_count": len(self.pairs),
                "ordered_cases": [_case_payload(value) for value in self.cases],
                "ordered_pairs": [_pair_payload(value) for value in self.pairs],
            },
            "aggregate": self.aggregate,
            "evidence_boundary": {
                "development_evidence_only": True,
                "complete_campaign_reverified": True,
                "normalized_evaluators_bound": True,
                "paired_metrics_computed": True,
                "raw_audio_embedded": False,
                "absolute_audio_paths_embedded": False,
                "raw_generated_transcripts_embedded": False,
                "normalized_transcripts_embedded": False,
                "qualification_threshold_applied": False,
                "model_verdict_issued": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()

    def require_qualification_threshold_applied(self) -> None:
        raise ASRAdversarialVOiCESMatchedControlMetricsError(
            "VOiCES matched-control normalized metrics are descriptive B7 "
            "evidence; no qualification threshold or model verdict was applied."
        )


def build_asr_adversarial_voices_babble_matched_control_metrics_v1(
    campaign: ASRAdversarialVOiCESMatchedControlCampaignBundle,
) -> ASRAdversarialVOiCESMatchedControlMetricsBundle:
    """Evaluate all complete B6 transcripts with canonical normalized v1."""

    if not isinstance(
        campaign,
        ASRAdversarialVOiCESMatchedControlCampaignBundle,
    ):
        raise ASRAdversarialVOiCESMatchedControlMetricsError(
            "VOiCES normalized metrics require the exact B6 campaign."
        )

    try:
        completed_results = campaign.require_complete_for_paired_metrics()
    except ASRAdversarialVOiCESMatchedControlCampaignError as error:
        raise ASRAdversarialVOiCESMatchedControlMetricsError(
            "VOiCES normalized paired metrics require all 32 completed cases."
        ) from error

    result_by_case_id = {
        result.case_id: result
        for result in completed_results
    }
    cases = []

    for binding in campaign.suite.cases:
        result = result_by_case_id[binding.case.case_id]
        evaluation = evaluate_normalized_transcript_pair(
            reference_text=binding.case.reference_transcript,
            generated_text=result.generated_transcript,
        )

        cases.append(
            ASRAdversarialVOiCESMatchedControlCaseMetrics(
                pair_key=binding.pair_key,
                arm=binding.arm,
                case_id=binding.case.case_id,
                audio_asset_sha256=binding.case.audio_asset_sha256,
                reference_transcript_sha256=(
                    binding.reference_transcript_sha256
                ),
                generated_transcript_sha256=(
                    result.execution_definition.generated_transcript_sha256
                ),
                execution_evidence_sha256=result.execution_evidence.sha256,
                normalized_reference_sha256=(
                    _text_sha256(evaluation.normalized_reference)
                ),
                normalized_generated_sha256=(
                    _text_sha256(evaluation.normalized_generated)
                ),
                evaluation=evaluation,
            )
        )

    case_tuple = tuple(cases)
    cases_by_pair: dict[
        ASRAdversarialVOiCESMatchedControlPairKey,
        dict[str, ASRAdversarialVOiCESMatchedControlCaseMetrics],
    ] = {}

    for value in case_tuple:
        cases_by_pair.setdefault(value.pair_key, {})[value.arm] = value

    pairs = tuple(
        ASRAdversarialVOiCESMatchedControlPairMetrics(
            key=key,
            babble=cases_by_pair[key][
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
            ],
            control=cases_by_pair[key][
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
            ],
        )
        for key in sorted(cases_by_pair)
    )

    return ASRAdversarialVOiCESMatchedControlMetricsBundle(
        matched_control_campaign_sha256=campaign.sha256,
        campaign=campaign,
        cases=case_tuple,
        pairs=pairs,
    )
