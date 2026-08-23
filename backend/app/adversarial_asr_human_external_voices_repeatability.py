"""Evaluate same-environment VOiCES campaign repeatability.

This B11F layer compares three complete, independently identified B9
two-model campaign executions over the exact same B5 cohort.  It reports
hash-level transcript stability, normalized transcript stability, WER/CER
drift envelopes, runtime-identity conformance, and comparison-direction
stability without embedding transcript or audio content.

Distinct campaign identities establish campaign-level repetition only.  This
contract deliberately does not claim independent operating-system processes,
cross-host reproduction, statistical generalization, model qualification, or
release authority.  In particular, B11F evidence must not be projected into
the v1 ``reproducibility_verified`` scorecard input.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Iterable

from app.adversarial_asr_human_external_voices_model_comparison import (
    ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE,
)
from app.adversarial_asr_human_external_voices_model_comparison_execution import (
    ASRAdversarialVOiCESModelComparisonExecutionBundle,
    ASRAdversarialVOiCESModelComparisonExecutionError,
    ASRAdversarialVOiCESModelComparisonExecutionStatus,
)


ASR_ADVERSARIAL_VOICES_REPEATABILITY_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_REPEATABILITY_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_REPEATABILITY_KEY = (
    "hetren.asr.adversarial-human-external-voices-"
    "same-environment-campaign-repeatability"
)
ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT = 3
ASR_ADVERSARIAL_VOICES_REPEATABILITY_MODEL_COUNT = 2
ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT = 32
ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT = (
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_MODEL_COUNT
    * ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT
)

_ROLES = ("baseline", "candidate")
_ARMS = ("babble", "control")
_SHA256_HEX = frozenset("0123456789abcdef")


class ASRAdversarialVOiCESRepeatabilityError(ValueError):
    """Raised when B9 executions cannot form trusted repeatability evidence."""


def _require_text(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialVOiCESRepeatabilityError(
            f"{name} must be non-empty trimmed text."
        )
    return value


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_HEX for character in value)
    ):
        raise ASRAdversarialVOiCESRepeatabilityError(
            f"{name} must be a lowercase SHA-256."
        )
    return value


def _require_positive_int(*, name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ASRAdversarialVOiCESRepeatabilityError(
            f"{name} must be a positive integer."
        )
    return value


def _require_finite(*, name: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ASRAdversarialVOiCESRepeatabilityError(
            f"{name} must be finite."
        )
    return float(value)


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
        raise ASRAdversarialVOiCESRepeatabilityError(
            "VOiCES repeatability evidence must be deterministic JSON."
        ) from error


def _canonical_metric(value: float) -> float:
    checked = _require_finite(name="VOiCES repeatability metric", value=value)
    if math.isclose(
        checked,
        0.0,
        rel_tol=0.0,
        abs_tol=ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE,
    ):
        return 0.0
    return checked


def _metric_stable(values: tuple[float, ...]) -> bool:
    anchor = values[0]
    return all(
        math.isclose(
            anchor,
            value,
            rel_tol=0.0,
            abs_tol=(
                ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE
            ),
        )
        for value in values[1:]
    )


def _drift(values: tuple[float, ...]) -> float:
    return _canonical_metric(max(values) - min(values))


def _mean(values: Iterable[float]) -> float:
    values = tuple(values)
    if not values:
        raise ASRAdversarialVOiCESRepeatabilityError(
            "VOiCES repeatability mean requires observations."
        )
    return _canonical_metric(math.fsum(values) / len(values))


def _direction(value: float) -> str:
    canonical = _canonical_metric(value)
    if canonical == 0.0:
        return "equal"
    return "candidate_better" if canonical < 0 else "candidate_worse"


def _rate_payload(*, successful: int, observed: int) -> dict[str, object]:
    if successful < 0 or observed <= 0 or successful > observed:
        raise ASRAdversarialVOiCESRepeatabilityError(
            "VOiCES repeatability rate counts are invalid."
        )
    return {
        "successful_count": successful,
        "observed_count": observed,
        "rate": successful / observed,
        "score_percent": (successful / observed) * 100.0,
    }


def _reverify_execution(
    value: object,
) -> ASRAdversarialVOiCESModelComparisonExecutionBundle:
    if not isinstance(
        value,
        ASRAdversarialVOiCESModelComparisonExecutionBundle,
    ):
        raise ASRAdversarialVOiCESRepeatabilityError(
            "VOiCES repeatability requires exact B9 execution bundles."
        )
    try:
        reverified = ASRAdversarialVOiCESModelComparisonExecutionBundle(
            matched_control_suite_sha256=value.matched_control_suite_sha256,
            baseline_campaign=value.baseline_campaign,
            candidate_campaign=value.candidate_campaign,
            baseline_metrics=value.baseline_metrics,
            candidate_metrics=value.candidate_metrics,
            comparison=value.comparison,
        )
    except (
        ASRAdversarialVOiCESModelComparisonExecutionError,
        ValueError,
    ) as error:
        raise ASRAdversarialVOiCESRepeatabilityError(
            "VOiCES B9 execution failed repeatability revalidation."
        ) from error
    if reverified.sha256 != value.sha256:
        raise ASRAdversarialVOiCESRepeatabilityError(
            "VOiCES B9 execution identity changed."
        )
    return reverified


@dataclass(frozen=True, slots=True, order=True)
class ASRAdversarialVOiCESRepeatabilityPairKey:
    """Portable matched-control identity used by B11F observations."""

    source_key: tuple[int, int, int]
    room: str
    microphone_id: int
    angle_degrees: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_key, tuple)
            or len(self.source_key) != 3
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
                for value in self.source_key
            )
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability source key is invalid."
            )
        _require_text(name="VOiCES repeatability room", value=self.room)
        _require_positive_int(
            name="VOiCES repeatability microphone id",
            value=self.microphone_id,
        )
        _require_positive_int(
            name="VOiCES repeatability angle",
            value=self.angle_degrees,
        )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "source_key": list(self.source_key),
            "room": self.room,
            "microphone_id": self.microphone_id,
            "angle_degrees": self.angle_degrees,
        }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESRepeatabilityCaseObservation:
    """One model/case output commitment from one complete B9 run."""

    run_id: str
    role: str
    provider_key: str
    model_key: str
    pair_key: ASRAdversarialVOiCESRepeatabilityPairKey
    arm: str
    case_id: str
    audio_asset_sha256: str
    reference_transcript_sha256: str
    normalized_reference_sha256: str
    execution_environment_sha256: str
    execution_evidence_sha256: str
    generated_transcript_sha256: str
    normalized_generated_sha256: str
    wer: float
    cer: float

    def __post_init__(self) -> None:
        _require_text(name="VOiCES repeatability run id", value=self.run_id)
        if self.role not in _ROLES:
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability role is invalid."
            )
        if self.arm not in _ARMS:
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability arm is invalid."
            )
        for name, value in (
            ("provider", self.provider_key),
            ("model", self.model_key),
            ("case id", self.case_id),
        ):
            _require_text(name=f"VOiCES repeatability {name}", value=value)
        if not isinstance(
            self.pair_key,
            ASRAdversarialVOiCESRepeatabilityPairKey,
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability pair key is invalid."
            )
        for name, value in (
            ("audio asset", self.audio_asset_sha256),
            ("reference transcript", self.reference_transcript_sha256),
            ("normalized reference", self.normalized_reference_sha256),
            ("execution environment", self.execution_environment_sha256),
            ("execution evidence", self.execution_evidence_sha256),
            ("generated transcript", self.generated_transcript_sha256),
            ("normalized generated transcript", self.normalized_generated_sha256),
        ):
            _require_sha256(name=f"VOiCES repeatability {name}", value=value)
        for name, value in (("WER", self.wer), ("CER", self.cer)):
            checked = _require_finite(
                name=f"VOiCES repeatability {name}",
                value=value,
            )
            if checked < 0:
                raise ASRAdversarialVOiCESRepeatabilityError(
                    f"VOiCES repeatability {name} cannot be negative."
                )

    @property
    def identity(self) -> tuple[str, str]:
        return (self.role, self.case_id)

    @property
    def fixed_input_identity(self) -> tuple[object, ...]:
        return (
            self.pair_key,
            self.arm,
            self.case_id,
            self.audio_asset_sha256,
            self.reference_transcript_sha256,
            self.normalized_reference_sha256,
        )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "role": self.role,
            "provider_key": self.provider_key,
            "model_key": self.model_key,
            "case_id": self.case_id,
            "arm": self.arm,
            "pair_key": self.pair_key.payload,
            "fixed_inputs": {
                "audio_asset_sha256": self.audio_asset_sha256,
                "reference_transcript_sha256": self.reference_transcript_sha256,
                "normalized_reference_utf8_sha256": (
                    self.normalized_reference_sha256
                ),
            },
            "outputs": {
                "execution_environment_sha256": (
                    self.execution_environment_sha256
                ),
                "execution_evidence_sha256": self.execution_evidence_sha256,
                "generated_transcript_sha256": (
                    self.generated_transcript_sha256
                ),
                "normalized_generated_utf8_sha256": (
                    self.normalized_generated_sha256
                ),
            },
            "metrics": {"wer": self.wer, "cer": self.cer},
        }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESRepeatabilityRunObservation:
    """Compact, content-free observation projected from one complete B9 run."""

    run_id: str
    execution_sha256: str
    matched_control_suite_sha256: str
    adversarial_suite_evidence_sha256: str
    baseline_campaign_id: str
    baseline_campaign_version: str
    baseline_campaign_sha256: str
    baseline_metrics_sha256: str
    baseline_provider_key: str
    baseline_model_key: str
    candidate_campaign_id: str
    candidate_campaign_version: str
    candidate_campaign_sha256: str
    candidate_metrics_sha256: str
    candidate_provider_key: str
    candidate_model_key: str
    cases: tuple[ASRAdversarialVOiCESRepeatabilityCaseObservation, ...]
    general_accuracy_wer_differential: float
    general_accuracy_cer_differential: float
    robustness_wer_differential: float
    robustness_cer_differential: float

    def __post_init__(self) -> None:
        _require_text(name="VOiCES repeatability run id", value=self.run_id)
        for name, value in (
            ("execution", self.execution_sha256),
            ("matched-control suite", self.matched_control_suite_sha256),
            ("adversarial suite", self.adversarial_suite_evidence_sha256),
            ("baseline campaign", self.baseline_campaign_sha256),
            ("baseline metrics", self.baseline_metrics_sha256),
            ("candidate campaign", self.candidate_campaign_sha256),
            ("candidate metrics", self.candidate_metrics_sha256),
        ):
            _require_sha256(name=f"VOiCES repeatability {name}", value=value)
        for name, value in (
            ("baseline campaign id", self.baseline_campaign_id),
            ("baseline campaign version", self.baseline_campaign_version),
            ("baseline provider", self.baseline_provider_key),
            ("baseline model", self.baseline_model_key),
            ("candidate campaign id", self.candidate_campaign_id),
            ("candidate campaign version", self.candidate_campaign_version),
            ("candidate provider", self.candidate_provider_key),
            ("candidate model", self.candidate_model_key),
        ):
            _require_text(name=f"VOiCES repeatability {name}", value=value)
        if (
            self.baseline_provider_key,
            self.baseline_model_key,
        ) == (
            self.candidate_provider_key,
            self.candidate_model_key,
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability requires two distinct model identities."
            )
        if (
            not isinstance(self.cases, tuple)
            or len(self.cases) != ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            or any(
                not isinstance(
                    value,
                    ASRAdversarialVOiCESRepeatabilityCaseObservation,
                )
                for value in self.cases
            )
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability run requires exactly 64 case-model units."
            )
        identities = tuple(value.identity for value in self.cases)
        if len(set(identities)) != len(identities):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability run case identity repeated."
            )
        for role, provider, model in (
            (
                "baseline",
                self.baseline_provider_key,
                self.baseline_model_key,
            ),
            (
                "candidate",
                self.candidate_provider_key,
                self.candidate_model_key,
            ),
        ):
            role_cases = tuple(value for value in self.cases if value.role == role)
            if (
                len(role_cases) != ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT
                or any(value.run_id != self.run_id for value in role_cases)
                or any(
                    (value.provider_key, value.model_key) != (provider, model)
                    for value in role_cases
                )
            ):
                raise ASRAdversarialVOiCESRepeatabilityError(
                    f"VOiCES repeatability {role} population changed."
                )
        baseline_by_case = {
            value.case_id: value
            for value in self.cases
            if value.role == "baseline"
        }
        candidate_by_case = {
            value.case_id: value
            for value in self.cases
            if value.role == "candidate"
        }
        if (
            tuple(baseline_by_case) != tuple(candidate_by_case)
            or any(
                baseline_by_case[case_id].fixed_input_identity
                != candidate_by_case[case_id].fixed_input_identity
                for case_id in baseline_by_case
            )
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability models did not use identical inputs."
            )
        for name, value in (
            (
                "general accuracy WER differential",
                self.general_accuracy_wer_differential,
            ),
            (
                "general accuracy CER differential",
                self.general_accuracy_cer_differential,
            ),
            ("robustness WER differential", self.robustness_wer_differential),
            ("robustness CER differential", self.robustness_cer_differential),
        ):
            _require_finite(name=f"VOiCES repeatability {name}", value=value)

    @property
    def model_identities(self) -> dict[str, tuple[str, str, str]]:
        return {
            "baseline": (
                self.baseline_provider_key,
                self.baseline_model_key,
                self.baseline_campaign_version,
            ),
            "candidate": (
                self.candidate_provider_key,
                self.candidate_model_key,
                self.candidate_campaign_version,
            ),
        }

    @property
    def payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "execution_sha256": self.execution_sha256,
            "upstream": {
                "matched_control_suite_sha256": self.matched_control_suite_sha256,
                "adversarial_suite_evidence_sha256": (
                    self.adversarial_suite_evidence_sha256
                ),
            },
            "models": {
                "baseline": {
                    "campaign_id": self.baseline_campaign_id,
                    "campaign_version": self.baseline_campaign_version,
                    "campaign_sha256": self.baseline_campaign_sha256,
                    "metrics_sha256": self.baseline_metrics_sha256,
                    "provider_key": self.baseline_provider_key,
                    "model_key": self.baseline_model_key,
                },
                "candidate": {
                    "campaign_id": self.candidate_campaign_id,
                    "campaign_version": self.candidate_campaign_version,
                    "campaign_sha256": self.candidate_campaign_sha256,
                    "metrics_sha256": self.candidate_metrics_sha256,
                    "provider_key": self.candidate_provider_key,
                    "model_key": self.candidate_model_key,
                },
            },
            "case_model_units": [value.payload for value in self.cases],
            "comparison_signals": {
                "general_accuracy_candidate_minus_baseline": {
                    "wer": self.general_accuracy_wer_differential,
                    "cer": self.general_accuracy_cer_differential,
                },
                "matched_control_robustness_candidate_minus_baseline": {
                    "wer": self.robustness_wer_differential,
                    "cer": self.robustness_cer_differential,
                },
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESRepeatabilityUnitResult:
    """Repeatability result for one fixed model and case across three runs."""

    observations: tuple[ASRAdversarialVOiCESRepeatabilityCaseObservation, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.observations, tuple)
            or len(self.observations)
            != ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT
            or any(
                not isinstance(
                    value,
                    ASRAdversarialVOiCESRepeatabilityCaseObservation,
                )
                for value in self.observations
            )
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability unit requires exactly three observations."
            )
        anchor = self.observations[0]
        if any(
            value.identity != anchor.identity
            or value.fixed_input_identity != anchor.fixed_input_identity
            or (value.provider_key, value.model_key)
            != (anchor.provider_key, anchor.model_key)
            for value in self.observations[1:]
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability unit identity changed across runs."
            )
        if len({value.run_id for value in self.observations}) != len(
            self.observations
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES repeatability unit repeated a run identity."
            )

    @property
    def raw_transcript_stable(self) -> bool:
        return len(
            {value.generated_transcript_sha256 for value in self.observations}
        ) == 1

    @property
    def normalized_transcript_stable(self) -> bool:
        return len(
            {value.normalized_generated_sha256 for value in self.observations}
        ) == 1

    @property
    def runtime_identity_conformant(self) -> bool:
        return len(
            {value.execution_environment_sha256 for value in self.observations}
        ) == 1

    @property
    def wer_values(self) -> tuple[float, ...]:
        return tuple(value.wer for value in self.observations)

    @property
    def cer_values(self) -> tuple[float, ...]:
        return tuple(value.cer for value in self.observations)

    @property
    def wer_stable(self) -> bool:
        return _metric_stable(self.wer_values)

    @property
    def cer_stable(self) -> bool:
        return _metric_stable(self.cer_values)

    @property
    def payload(self) -> dict[str, object]:
        anchor = self.observations[0]
        return {
            "role": anchor.role,
            "provider_key": anchor.provider_key,
            "model_key": anchor.model_key,
            "case_id": anchor.case_id,
            "arm": anchor.arm,
            "pair_key": anchor.pair_key.payload,
            "fixed_inputs": {
                "audio_asset_sha256": anchor.audio_asset_sha256,
                "reference_transcript_sha256": anchor.reference_transcript_sha256,
                "normalized_reference_utf8_sha256": (
                    anchor.normalized_reference_sha256
                ),
            },
            "run_observations": [
                {
                    "run_id": value.run_id,
                    "execution_environment_sha256": (
                        value.execution_environment_sha256
                    ),
                    "execution_evidence_sha256": (
                        value.execution_evidence_sha256
                    ),
                    "generated_transcript_sha256": (
                        value.generated_transcript_sha256
                    ),
                    "normalized_generated_utf8_sha256": (
                        value.normalized_generated_sha256
                    ),
                    "wer": value.wer,
                    "cer": value.cer,
                }
                for value in self.observations
            ],
            "metrics": {
                "raw_transcript_stable": self.raw_transcript_stable,
                "normalized_transcript_stable": (
                    self.normalized_transcript_stable
                ),
                "runtime_identity_conformant": (
                    self.runtime_identity_conformant
                ),
                "wer_stable": self.wer_stable,
                "cer_stable": self.cer_stable,
                "wer_drift_envelope": _drift(self.wer_values),
                "cer_drift_envelope": _drift(self.cer_values),
            },
        }


def _unit_results(
    runs: tuple[ASRAdversarialVOiCESRepeatabilityRunObservation, ...],
) -> tuple[ASRAdversarialVOiCESRepeatabilityUnitResult, ...]:
    identities = tuple(value.identity for value in runs[0].cases)
    by_run = tuple(
        {value.identity: value for value in run.cases}
        for run in runs
    )
    if any(tuple(values) != identities for values in by_run[1:]):
        raise ASRAdversarialVOiCESRepeatabilityError(
            "VOiCES repeatability case ordering changed across runs."
        )
    return tuple(
        ASRAdversarialVOiCESRepeatabilityUnitResult(
            observations=tuple(values[identity] for values in by_run)
        )
        for identity in identities
    )


def _unit_aggregate(
    values: tuple[ASRAdversarialVOiCESRepeatabilityUnitResult, ...],
) -> dict[str, object]:
    observed = len(values)
    wer_drifts = tuple(_drift(value.wer_values) for value in values)
    cer_drifts = tuple(_drift(value.cer_values) for value in values)
    return {
        "unit_count": observed,
        "exact_transcript_repeatability": _rate_payload(
            successful=sum(value.raw_transcript_stable for value in values),
            observed=observed,
        ),
        "normalized_transcript_repeatability": _rate_payload(
            successful=sum(
                value.normalized_transcript_stable for value in values
            ),
            observed=observed,
        ),
        "runtime_identity_conformance": _rate_payload(
            successful=sum(
                value.runtime_identity_conformant for value in values
            ),
            observed=observed,
        ),
        "wer_stability": _rate_payload(
            successful=sum(value.wer_stable for value in values),
            observed=observed,
        ),
        "cer_stability": _rate_payload(
            successful=sum(value.cer_stable for value in values),
            observed=observed,
        ),
        "wer_drift_envelope": {
            "maximum": max(wer_drifts),
            "macro_mean": _mean(wer_drifts),
        },
        "cer_drift_envelope": {
            "maximum": max(cer_drifts),
            "macro_mean": _mean(cer_drifts),
        },
    }


def _signal_stability(
    *,
    runs: tuple[ASRAdversarialVOiCESRepeatabilityRunObservation, ...],
    attribute: str,
) -> dict[str, object]:
    values = tuple(float(getattr(run, attribute)) for run in runs)
    directions = tuple(_direction(value) for value in values)
    return {
        "values_by_run": [
            {"run_id": run.run_id, "value": value, "direction": direction}
            for run, value, direction in zip(
                runs,
                values,
                directions,
                strict=True,
            )
        ],
        "metric_stable": _metric_stable(values),
        "direction_stable": len(set(directions)) == 1,
        "drift_envelope": _drift(values),
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESRepeatabilityBundle:
    """Deterministic, descriptive B11F evidence over three complete runs."""

    runs: tuple[ASRAdversarialVOiCESRepeatabilityRunObservation, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.runs, tuple)
            or len(self.runs) != ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT
            or any(
                not isinstance(
                    value,
                    ASRAdversarialVOiCESRepeatabilityRunObservation,
                )
                for value in self.runs
            )
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES B11F requires exactly three complete run observations."
            )
        if len({value.run_id for value in self.runs}) != len(self.runs):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES B11F run identities must be unique."
            )
        if len({value.execution_sha256 for value in self.runs}) != len(
            self.runs
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES B11F execution identities must be unique."
            )
        anchor = self.runs[0]
        if any(
            value.matched_control_suite_sha256
            != anchor.matched_control_suite_sha256
            or value.adversarial_suite_evidence_sha256
            != anchor.adversarial_suite_evidence_sha256
            or value.model_identities != anchor.model_identities
            for value in self.runs[1:]
        ):
            raise ASRAdversarialVOiCESRepeatabilityError(
                "VOiCES B11F cohort or model identity changed across runs."
            )
        for role in _ROLES:
            campaign_ids = {
                getattr(value, f"{role}_campaign_id")
                for value in self.runs
            }
            campaign_hashes = {
                getattr(value, f"{role}_campaign_sha256")
                for value in self.runs
            }
            metrics_hashes = {
                getattr(value, f"{role}_metrics_sha256")
                for value in self.runs
            }
            if (
                len(campaign_ids) != len(self.runs)
                or len(campaign_hashes) != len(self.runs)
                or len(metrics_hashes) != len(self.runs)
            ):
                raise ASRAdversarialVOiCESRepeatabilityError(
                    f"VOiCES B11F {role} campaigns were not independently identified."
                )
        _unit_results(self.runs)

    @property
    def units(self) -> tuple[ASRAdversarialVOiCESRepeatabilityUnitResult, ...]:
        return _unit_results(self.runs)

    @property
    def aggregate(self) -> dict[str, object]:
        units = self.units
        by_role = {
            role: tuple(
                value
                for value in units
                if value.observations[0].role == role
            )
            for role in _ROLES
        }
        signal_attributes = {
            "general_accuracy_wer": "general_accuracy_wer_differential",
            "general_accuracy_cer": "general_accuracy_cer_differential",
            "matched_control_robustness_wer": "robustness_wer_differential",
            "matched_control_robustness_cer": "robustness_cer_differential",
        }
        return {
            "overall": _unit_aggregate(units),
            "models": {
                role: _unit_aggregate(values)
                for role, values in by_role.items()
            },
            "comparison_signal_stability": {
                key: _signal_stability(
                    runs=self.runs,
                    attribute=attribute,
                )
                for key, attribute in signal_attributes.items()
            },
        }

    @property
    def status(self) -> str:
        overall = self.aggregate["overall"]
        signals = self.aggregate["comparison_signal_stability"]
        stable = (
            overall["exact_transcript_repeatability"]["successful_count"]
            == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            and overall["normalized_transcript_repeatability"][
                "successful_count"
            ]
            == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            and overall["runtime_identity_conformance"]["successful_count"]
            == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            and overall["wer_stability"]["successful_count"]
            == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            and overall["cer_stability"]["successful_count"]
            == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            and all(
                value["metric_stable"] and value["direction_stable"]
                for value in signals.values()
            )
        )
        return "stable" if stable else "variation_observed"

    @property
    def payload(self) -> dict[str, object]:
        anchor = self.runs[0]
        return {
            "schema_version": ASR_ADVERSARIAL_VOICES_REPEATABILITY_SCHEMA_VERSION,
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_REPEATABILITY_KEY,
                "version": ASR_ADVERSARIAL_VOICES_REPEATABILITY_VERSION,
                "type": "same_environment_campaign_repeatability_evidence",
            },
            "protocol": {
                "expected_run_count": (
                    ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT
                ),
                "run_unit": "fixed_model_and_case_across_complete_campaigns",
                "campaign_identity_rule": "distinct_per_role_per_run",
                "fixed_input_rule": "exact_hash_identity",
                "transcript_rule": "exact_sha256_equality",
                "normalized_transcript_rule": "exact_sha256_equality",
                "metric_equality": {
                    "absolute_tolerance": (
                        ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE
                    ),
                    "relative_tolerance": 0.0,
                    "canonical_zero": True,
                },
                "comparison_direction": "candidate_minus_baseline",
                "lower_error_values_are_better": True,
            },
            "upstream": {
                "matched_control_suite_sha256": (
                    anchor.matched_control_suite_sha256
                ),
                "adversarial_suite_evidence_sha256": (
                    anchor.adversarial_suite_evidence_sha256
                ),
                "ordered_run_observation_sha256s": [
                    value.sha256 for value in self.runs
                ],
                "ordered_b9_execution_sha256s": [
                    value.execution_sha256 for value in self.runs
                ],
            },
            "status": self.status,
            "models": {
                role: {
                    "provider_key": getattr(anchor, f"{role}_provider_key"),
                    "model_key": getattr(anchor, f"{role}_model_key"),
                    "campaign_version": getattr(
                        anchor,
                        f"{role}_campaign_version",
                    ),
                }
                for role in _ROLES
            },
            "population": {
                "run_count": len(self.runs),
                "model_count": ASR_ADVERSARIAL_VOICES_REPEATABILITY_MODEL_COUNT,
                "case_count_per_model": (
                    ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT
                ),
                "case_model_unit_count": len(self.units),
                "execution_count": (
                    ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT
                    * ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
                ),
                "ordered_run_ids": [value.run_id for value in self.runs],
            },
            "runs": [value.payload for value in self.runs],
            "repeatability": {
                "engineer_metrics": {
                    "exact_transcript_repeatability": (
                        "Exact generated-transcript commitment stability."
                    ),
                    "normalized_transcript_repeatability": (
                        "Normalized transcript commitment stability."
                    ),
                    "metric_drift_envelope": (
                        "Maximum and macro-mean WER/CER range across runs."
                    ),
                    "runtime_identity_conformance": (
                        "Fixed model/case environment commitment stability."
                    ),
                    "comparison_signal_stability": (
                        "Metric and direction stability of aggregate comparisons."
                    ),
                },
                "aggregate": self.aggregate,
                "case_model_units": [value.payload for value in self.units],
            },
            "evidence_boundary": {
                "development_evidence_only": True,
                "complete_b9_runs_reverified_before_projection": True,
                "fixed_cohort_and_model_identities_verified": True,
                "distinct_campaign_identities_verified": True,
                "same_environment_campaign_repeatability_evaluated": True,
                "raw_audio_embedded": False,
                "raw_reference_transcripts_embedded": False,
                "raw_generated_transcripts_embedded": False,
                "independent_operating_system_processes_verified": False,
                "cross_host_reproducibility_evaluated": False,
                "reproducibility_verified": None,
                "reproducibility_claimed": False,
                "repeatability_threshold_applied": False,
                "qualification_threshold_applied": False,
                "statistical_generalization_claimed": False,
                "model_winner_declared": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
                "v1_reliability_scorecard_modified": False,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()

    def require_reproducibility_verified(self) -> None:
        raise ASRAdversarialVOiCESRepeatabilityError(
            "Same-environment campaign repetition cannot establish "
            "cross-host reproducibility."
        )

    def require_repeatability_qualification(self) -> None:
        raise ASRAdversarialVOiCESRepeatabilityError(
            "B11F is descriptive repeatability evidence; no threshold or "
            "qualification verdict was applied."
        )


def project_asr_adversarial_voices_repeatability_run_v1(
    *,
    run_id: str,
    execution: ASRAdversarialVOiCESModelComparisonExecutionBundle,
) -> ASRAdversarialVOiCESRepeatabilityRunObservation:
    """Project one complete B9 execution into content-free B11F evidence."""

    run_id = _require_text(name="VOiCES repeatability run id", value=run_id)
    verified = _reverify_execution(execution)
    if (
        verified.status
        != ASRAdversarialVOiCESModelComparisonExecutionStatus.COMPLETED
        or verified.baseline_metrics is None
        or verified.candidate_metrics is None
    ):
        raise ASRAdversarialVOiCESRepeatabilityError(
            "VOiCES repeatability projection requires a complete B9 run."
        )
    comparison = verified.require_complete_comparison()

    def environment_by_case(role: str) -> dict[str, str]:
        campaign = getattr(verified, f"{role}_campaign")
        observed: dict[str, str] = {}
        for attempt in campaign.campaign.attempts:
            definition = attempt.execution_definition
            if definition is None:
                raise ASRAdversarialVOiCESRepeatabilityError(
                    f"VOiCES repeatability {role} execution identity is missing."
                )
            observed[attempt.case_id] = _require_sha256(
                name=f"VOiCES repeatability {role} environment",
                value=definition.execution_environment_sha256,
            )
        return observed

    observations = []
    for role in _ROLES:
        metrics = getattr(verified, f"{role}_metrics")
        environment = environment_by_case(role)
        definition = getattr(verified, f"{role}_campaign").campaign.definition
        for value in metrics.cases:
            key = value.pair_key
            observations.append(
                ASRAdversarialVOiCESRepeatabilityCaseObservation(
                    run_id=run_id,
                    role=role,
                    provider_key=definition.provider_key,
                    model_key=definition.model_key,
                    pair_key=ASRAdversarialVOiCESRepeatabilityPairKey(
                        source_key=key.source_key,
                        room=key.room,
                        microphone_id=key.microphone_id,
                        angle_degrees=key.angle_degrees,
                    ),
                    arm=value.arm,
                    case_id=value.case_id,
                    audio_asset_sha256=value.audio_asset_sha256,
                    reference_transcript_sha256=(
                        value.reference_transcript_sha256
                    ),
                    normalized_reference_sha256=(
                        value.normalized_reference_sha256
                    ),
                    execution_environment_sha256=environment[value.case_id],
                    execution_evidence_sha256=value.execution_evidence_sha256,
                    generated_transcript_sha256=(
                        value.generated_transcript_sha256
                    ),
                    normalized_generated_sha256=(
                        value.normalized_generated_sha256
                    ),
                    wer=value.evaluation.wer,
                    cer=value.evaluation.cer,
                )
            )

    aggregate = comparison.aggregate
    general = aggregate["case_macro_mean"]["all"][
        "candidate_minus_baseline"
    ]
    robustness = aggregate["pair_noise_degradation_macro_mean"][
        "candidate_minus_baseline"
    ]
    baseline_definition = verified.baseline_campaign.campaign.definition
    candidate_definition = verified.candidate_campaign.campaign.definition

    return ASRAdversarialVOiCESRepeatabilityRunObservation(
        run_id=run_id,
        execution_sha256=verified.sha256,
        matched_control_suite_sha256=verified.matched_control_suite_sha256,
        adversarial_suite_evidence_sha256=(
            verified.baseline_campaign.suite.evidence.sha256
        ),
        baseline_campaign_id=baseline_definition.campaign_id,
        baseline_campaign_version=baseline_definition.campaign_version,
        baseline_campaign_sha256=verified.baseline_campaign.sha256,
        baseline_metrics_sha256=verified.baseline_metrics.sha256,
        baseline_provider_key=baseline_definition.provider_key,
        baseline_model_key=baseline_definition.model_key,
        candidate_campaign_id=candidate_definition.campaign_id,
        candidate_campaign_version=candidate_definition.campaign_version,
        candidate_campaign_sha256=verified.candidate_campaign.sha256,
        candidate_metrics_sha256=verified.candidate_metrics.sha256,
        candidate_provider_key=candidate_definition.provider_key,
        candidate_model_key=candidate_definition.model_key,
        cases=tuple(observations),
        general_accuracy_wer_differential=general["wer"],
        general_accuracy_cer_differential=general["cer"],
        robustness_wer_differential=robustness["wer"],
        robustness_cer_differential=robustness["cer"],
    )


def evaluate_asr_adversarial_voices_repeatability_v1(
    *,
    runs: tuple[ASRAdversarialVOiCESRepeatabilityRunObservation, ...],
) -> ASRAdversarialVOiCESRepeatabilityBundle:
    """Evaluate three preregistered same-environment campaign observations."""

    return ASRAdversarialVOiCESRepeatabilityBundle(runs=runs)
