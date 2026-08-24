"""Evaluate VOiCES reproducibility across two independently attested hosts.

B11J compares two complete B11H process-reproducibility bundles produced on
distinct host instances.  It requires the same source, runtime contract,
models, and frozen VOiCES cohort while allowing the host environment and
Python executable identities to differ.  It then recomputes transcript,
WER/CER, and comparison-signal reproduction across all six child-process
runs from both hosts.

This layer remains descriptive development evidence.  It does not apply a
qualification threshold, declare a model winner, certify production use, or
authorize release enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

from app.adversarial_asr_human_external_voices_model_comparison import (
    ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE,
)
from app.adversarial_asr_human_external_voices_process_reproducibility import (
    ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT,
    ASRAdversarialVOiCESProcessReproducibilityBundle,
    ASRAdversarialVOiCESProcessReproducibilityError,
    evaluate_asr_adversarial_voices_process_reproducibility_v1,
)
from app.adversarial_asr_human_external_voices_repeatability import (
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_MODEL_COUNT,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT,
    ASRAdversarialVOiCESRepeatabilityCaseObservation,
)


ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_KEY = (
    "hetren.asr.adversarial-human-external-voices-"
    "cross-host-process-isolated-reproducibility"
)
ASR_ADVERSARIAL_VOICES_CROSS_HOST_COUNT = 2
ASR_ADVERSARIAL_VOICES_CROSS_HOST_AXIS_WEIGHT = 0.2
ASR_ADVERSARIAL_VOICES_CROSS_HOST_ATTESTATION_SCHEMES = frozenset(
    {
        "operator_witnessed_distinct_host_v1",
        "cloud_instance_identity_document_v1",
        "hardware_backed_host_attestation_v1",
    }
)

_HOST_ROLES = ("reference_host", "reproduction_host")
_MODEL_ROLES = ("baseline", "candidate")
_SHA256_HEX = frozenset("0123456789abcdef")
_SIGNAL_ATTRIBUTES = {
    "general_accuracy_wer": "general_accuracy_wer_differential",
    "general_accuracy_cer": "general_accuracy_cer_differential",
    "matched_control_robustness_wer": "robustness_wer_differential",
    "matched_control_robustness_cer": "robustness_cer_differential",
}


class ASRAdversarialVOiCESCrossHostReproducibilityError(ValueError):
    """Raised when B11J evidence is invalid or cannot support comparison."""


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
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J evidence must be deterministic JSON."
        ) from error


def _sha256_payload(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _require_text(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            f"{name} must be non-empty trimmed text."
        )
    return value


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_HEX for character in value)
    ):
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            f"{name} must be a lowercase SHA-256."
        )
    return value


def _require_finite(*, name: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            f"{name} must be finite."
        )
    return float(value)


def _rate_payload(*, successful: int, observed: int) -> dict[str, object]:
    if (
        isinstance(successful, bool)
        or isinstance(observed, bool)
        or not isinstance(successful, int)
        or not isinstance(observed, int)
        or observed <= 0
        or successful < 0
        or successful > observed
    ):
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J rate counts are invalid."
        )
    return {
        "successful_count": successful,
        "observed_count": observed,
        "rate": successful / observed,
        "score_percent": (successful / observed) * 100.0,
    }


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J cannot aggregate an empty population."
        )
    return math.fsum(values) / len(values)


def _drift(values: tuple[float, ...]) -> float:
    checked = tuple(
        _require_finite(name="B11J metric", value=value)
        for value in values
    )
    if not checked:
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J cannot compute drift over an empty population."
        )
    return max(checked) - min(checked)


def _metric_reproduced(values: tuple[float, ...]) -> bool:
    return _drift(values) <= (
        ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE
    )


def _direction(value: float) -> str:
    checked = _require_finite(name="B11J comparison value", value=value)
    tolerance = ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE
    if math.isclose(checked, 0.0, rel_tol=0.0, abs_tol=tolerance):
        return "equivalent"
    if checked < 0.0:
        return "candidate_better"
    return "candidate_worse"


def _reverify_process_bundle(
    value: object,
) -> ASRAdversarialVOiCESProcessReproducibilityBundle:
    if not isinstance(value, ASRAdversarialVOiCESProcessReproducibilityBundle):
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J requires exact B11H process-reproducibility bundles."
        )
    try:
        reverified = evaluate_asr_adversarial_voices_process_reproducibility_v1(
            runs=tuple(value.runs)
        )
    except ASRAdversarialVOiCESProcessReproducibilityError as error:
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J host process evidence failed B11H revalidation."
        ) from error
    if reverified.sha256 != value.sha256:
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J host process-evidence identity changed."
        )
    return reverified


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESCrossHostObservation:
    """One independently attested host and its complete B11H bundle."""

    host_role: str
    cross_host_experiment_sha256: str
    host_challenge_sha256: str
    host_instance_sha256: str
    host_attestation_evidence_sha256: str
    host_attestation_scheme: str
    process_reproducibility: ASRAdversarialVOiCESProcessReproducibilityBundle

    def __post_init__(self) -> None:
        if self.host_role not in _HOST_ROLES:
            raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                "B11J host role is invalid."
            )
        for name, value in (
            ("experiment", self.cross_host_experiment_sha256),
            ("host challenge", self.host_challenge_sha256),
            ("host instance", self.host_instance_sha256),
            ("host attestation evidence", self.host_attestation_evidence_sha256),
        ):
            _require_sha256(name=f"B11J {name}", value=value)
        if (
            not isinstance(self.host_attestation_scheme, str)
            or self.host_attestation_scheme
            not in ASR_ADVERSARIAL_VOICES_CROSS_HOST_ATTESTATION_SCHEMES
        ):
            raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                "B11J host attestation scheme is unsupported."
            )
        _reverify_process_bundle(self.process_reproducibility)

    @property
    def process_bundle(self) -> ASRAdversarialVOiCESProcessReproducibilityBundle:
        return _reverify_process_bundle(self.process_reproducibility)

    @property
    def anchor(self):
        return self.process_bundle.runs[0].process_launch.launch

    @property
    def portable_fixed_commitment_identity(self) -> tuple[str, ...]:
        anchor = self.anchor
        return (
            anchor.source_code_sha256,
            anchor.runtime_environment_sha256,
            anchor.model_set_sha256,
            anchor.matched_control_suite_sha256,
            anchor.adversarial_suite_evidence_sha256,
        )

    @property
    def payload(self) -> dict[str, object]:
        process = self.process_bundle
        anchor = process.runs[0].process_launch.launch
        return {
            "host_role": self.host_role,
            "cross_host_experiment_sha256": (
                self.cross_host_experiment_sha256
            ),
            "host_identity": {
                "host_instance_sha256": self.host_instance_sha256,
                "host_attestation_evidence_sha256": (
                    self.host_attestation_evidence_sha256
                ),
                "host_attestation_scheme": self.host_attestation_scheme,
                "host_environment_sha256": anchor.host_environment_sha256,
            },
            "host_challenge_sha256": self.host_challenge_sha256,
            "execution_commitments": {
                "controller_invocation_sha256": (
                    anchor.controller_invocation_sha256
                ),
                "source_code_sha256": anchor.source_code_sha256,
                "python_executable_sha256": anchor.python_executable_sha256,
                "runtime_environment_sha256": (
                    anchor.runtime_environment_sha256
                ),
                "model_set_sha256": anchor.model_set_sha256,
                "matched_control_suite_sha256": (
                    anchor.matched_control_suite_sha256
                ),
                "adversarial_suite_evidence_sha256": (
                    anchor.adversarial_suite_evidence_sha256
                ),
            },
            "process_reproducibility_sha256": process.sha256,
            "process_reproducibility": process.payload,
        }

    @property
    def sha256(self) -> str:
        return _sha256_payload(self.payload)


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESCrossHostUnitResult:
    """One fixed model/case unit compared over all six child runs."""

    reference_observations: tuple[
        ASRAdversarialVOiCESRepeatabilityCaseObservation,
        ...,
    ]
    reproduction_observations: tuple[
        ASRAdversarialVOiCESRepeatabilityCaseObservation,
        ...,
    ]

    def __post_init__(self) -> None:
        for role, values in (
            ("reference host", self.reference_observations),
            ("reproduction host", self.reproduction_observations),
        ):
            if (
                not isinstance(values, tuple)
                or len(values)
                != ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT
                or any(
                    not isinstance(
                        value,
                        ASRAdversarialVOiCESRepeatabilityCaseObservation,
                    )
                    for value in values
                )
            ):
                raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                    f"B11J {role} unit population changed."
                )
        observations = self.observations
        anchor = observations[0]
        if any(
            value.identity != anchor.identity
            or value.fixed_input_identity != anchor.fixed_input_identity
            or (value.provider_key, value.model_key)
            != (anchor.provider_key, anchor.model_key)
            for value in observations[1:]
        ):
            raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                "B11J case, model, or fixed-input identity changed across hosts."
            )
        for name, values in (
            ("reference host", self.reference_observations),
            ("reproduction host", self.reproduction_observations),
        ):
            if len({value.run_id for value in values}) != len(values):
                raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                    f"B11J {name} repeated a run identity."
                )

    @property
    def observations(
        self,
    ) -> tuple[ASRAdversarialVOiCESRepeatabilityCaseObservation, ...]:
        return (*self.reference_observations, *self.reproduction_observations)

    @property
    def exact_transcript_reproduced(self) -> bool:
        return len(
            {value.generated_transcript_sha256 for value in self.observations}
        ) == 1

    @property
    def normalized_transcript_reproduced(self) -> bool:
        return len(
            {value.normalized_generated_sha256 for value in self.observations}
        ) == 1

    @property
    def wer_values(self) -> tuple[float, ...]:
        return tuple(value.wer for value in self.observations)

    @property
    def cer_values(self) -> tuple[float, ...]:
        return tuple(value.cer for value in self.observations)

    @property
    def wer_reproduced(self) -> bool:
        return _metric_reproduced(self.wer_values)

    @property
    def cer_reproduced(self) -> bool:
        return _metric_reproduced(self.cer_values)

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
                "reference_transcript_sha256": (
                    anchor.reference_transcript_sha256
                ),
                "normalized_reference_utf8_sha256": (
                    anchor.normalized_reference_sha256
                ),
            },
            "host_observations": {
                "reference_host": [
                    _case_output_payload(value)
                    for value in self.reference_observations
                ],
                "reproduction_host": [
                    _case_output_payload(value)
                    for value in self.reproduction_observations
                ],
            },
            "metrics": {
                "exact_transcript_reproduced": (
                    self.exact_transcript_reproduced
                ),
                "normalized_transcript_reproduced": (
                    self.normalized_transcript_reproduced
                ),
                "wer_reproduced": self.wer_reproduced,
                "cer_reproduced": self.cer_reproduced,
                "wer_cross_host_drift_envelope": _drift(self.wer_values),
                "cer_cross_host_drift_envelope": _drift(self.cer_values),
            },
        }


def _case_output_payload(
    value: ASRAdversarialVOiCESRepeatabilityCaseObservation,
) -> dict[str, object]:
    return {
        "run_id": value.run_id,
        "execution_environment_sha256": (
            value.execution_environment_sha256
        ),
        "execution_evidence_sha256": value.execution_evidence_sha256,
        "generated_transcript_sha256": value.generated_transcript_sha256,
        "normalized_generated_utf8_sha256": (
            value.normalized_generated_sha256
        ),
        "wer": value.wer,
        "cer": value.cer,
    }


def _host_runs(observation: ASRAdversarialVOiCESCrossHostObservation):
    return tuple(
        value.run_observation for value in observation.process_bundle.runs
    )


def _unit_results(
    observations: tuple[ASRAdversarialVOiCESCrossHostObservation, ...],
) -> tuple[ASRAdversarialVOiCESCrossHostUnitResult, ...]:
    reference_runs = _host_runs(observations[0])
    reproduction_runs = _host_runs(observations[1])
    identities = tuple(value.identity for value in reference_runs[0].cases)
    all_runs = (*reference_runs, *reproduction_runs)
    by_run = tuple(
        {value.identity: value for value in run.cases}
        for run in all_runs
    )
    if any(tuple(values) != identities for values in by_run[1:]):
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J case ordering changed across hosts."
        )
    return tuple(
        ASRAdversarialVOiCESCrossHostUnitResult(
            reference_observations=tuple(
                values[identity] for values in by_run[:3]
            ),
            reproduction_observations=tuple(
                values[identity] for values in by_run[3:]
            ),
        )
        for identity in identities
    )


def _unit_aggregate(
    values: tuple[ASRAdversarialVOiCESCrossHostUnitResult, ...],
) -> dict[str, object]:
    observed = len(values)
    wer_drifts = tuple(_drift(value.wer_values) for value in values)
    cer_drifts = tuple(_drift(value.cer_values) for value in values)
    return {
        "unit_count": observed,
        "exact_transcript_reproduction": _rate_payload(
            successful=sum(
                value.exact_transcript_reproduced for value in values
            ),
            observed=observed,
        ),
        "normalized_transcript_reproduction": _rate_payload(
            successful=sum(
                value.normalized_transcript_reproduced for value in values
            ),
            observed=observed,
        ),
        "wer_reproduction": _rate_payload(
            successful=sum(value.wer_reproduced for value in values),
            observed=observed,
        ),
        "cer_reproduction": _rate_payload(
            successful=sum(value.cer_reproduced for value in values),
            observed=observed,
        ),
        "wer_cross_host_drift_envelope": {
            "maximum": max(wer_drifts),
            "macro_mean": _mean(wer_drifts),
        },
        "cer_cross_host_drift_envelope": {
            "maximum": max(cer_drifts),
            "macro_mean": _mean(cer_drifts),
        },
    }


def _signal_reproduction(
    *,
    observations: tuple[ASRAdversarialVOiCESCrossHostObservation, ...],
    attribute: str,
) -> dict[str, object]:
    values_by_host_run: list[dict[str, object]] = []
    numeric: list[float] = []
    directions: list[str] = []
    for host in observations:
        for run in _host_runs(host):
            value = float(getattr(run, attribute))
            direction = _direction(value)
            numeric.append(value)
            directions.append(direction)
            values_by_host_run.append(
                {
                    "host_role": host.host_role,
                    "run_id": run.run_id,
                    "value": value,
                    "direction": direction,
                }
            )
    values = tuple(numeric)
    return {
        "values_by_host_run": values_by_host_run,
        "metric_reproduced": _metric_reproduced(values),
        "direction_reproduced": len(set(directions)) == 1,
        "cross_host_drift_envelope": _drift(values),
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESCrossHostReproducibilityBundle:
    """Descriptive B11J evidence over two distinct host instances."""

    observations: tuple[ASRAdversarialVOiCESCrossHostObservation, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.observations, tuple)
            or len(self.observations)
            != ASR_ADVERSARIAL_VOICES_CROSS_HOST_COUNT
            or any(
                not isinstance(
                    value,
                    ASRAdversarialVOiCESCrossHostObservation,
                )
                for value in self.observations
            )
        ):
            raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                "B11J requires exactly two cross-host observations."
            )
        if tuple(value.host_role for value in self.observations) != _HOST_ROLES:
            raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                "B11J host observations must use the canonical role order."
            )
        anchor = self.observations[0]
        if any(
            value.cross_host_experiment_sha256
            != anchor.cross_host_experiment_sha256
            for value in self.observations[1:]
        ):
            raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                "B11J host observations changed the experiment identity."
            )
        for name, values in (
            (
                "host-instance commitments",
                {value.host_instance_sha256 for value in self.observations},
            ),
            (
                "host-attestation evidence",
                {
                    value.host_attestation_evidence_sha256
                    for value in self.observations
                },
            ),
            (
                "host challenges",
                {value.host_challenge_sha256 for value in self.observations},
            ),
            (
                "B11H process bundles",
                {
                    value.process_bundle.sha256
                    for value in self.observations
                },
            ),
        ):
            if len(values) != ASR_ADVERSARIAL_VOICES_CROSS_HOST_COUNT:
                raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                    f"B11J requires distinct {name}."
                )
        if any(
            value.portable_fixed_commitment_identity
            != anchor.portable_fixed_commitment_identity
            for value in self.observations[1:]
        ):
            raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                "B11J source, runtime, model, or cohort commitment changed."
            )
        models = tuple(
            value.process_bundle.payload["models"]
            for value in self.observations
        )
        if models[1:] != models[:1]:
            raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                "B11J provider, model, or campaign version changed."
            )
        _unit_results(self.observations)

    @property
    def units(self) -> tuple[ASRAdversarialVOiCESCrossHostUnitResult, ...]:
        return _unit_results(self.observations)

    @property
    def comparison_signal_reproduction(self) -> dict[str, object]:
        return {
            name: _signal_reproduction(
                observations=self.observations,
                attribute=attribute,
            )
            for name, attribute in _SIGNAL_ATTRIBUTES.items()
        }

    @property
    def aggregate(self) -> dict[str, object]:
        units = self.units
        overall = _unit_aggregate(units)
        models = {
            role: _unit_aggregate(
                tuple(
                    value
                    for value in units
                    if value.observations[0].role == role
                )
            )
            for role in _MODEL_ROLES
        }
        signals = self.comparison_signal_reproduction
        host_process_reproduction = _rate_payload(
            successful=sum(
                value.process_bundle.status == "reproduced"
                for value in self.observations
            ),
            observed=len(self.observations),
        )
        signal_success = sum(
            value["metric_reproduced"]
            and value["direction_reproduced"]
            for value in signals.values()
        )
        signal_rate = _rate_payload(
            successful=signal_success,
            observed=len(signals),
        )
        attestation_rate = _rate_payload(
            successful=len(self.observations),
            observed=len(self.observations),
        )
        output_axis = _mean(
            (
                overall["exact_transcript_reproduction"]["score_percent"],
                overall["normalized_transcript_reproduction"][
                    "score_percent"
                ],
            )
        )
        metric_axis = _mean(
            (
                overall["wer_reproduction"]["score_percent"],
                overall["cer_reproduction"]["score_percent"],
            )
        )
        axes = {
            "distinct_host_attestation": {
                "weight": ASR_ADVERSARIAL_VOICES_CROSS_HOST_AXIS_WEIGHT,
                "score_percent": attestation_rate["score_percent"],
            },
            "within_host_process_reproduction": {
                "weight": ASR_ADVERSARIAL_VOICES_CROSS_HOST_AXIS_WEIGHT,
                "score_percent": host_process_reproduction["score_percent"],
            },
            "cross_host_output_identity": {
                "weight": ASR_ADVERSARIAL_VOICES_CROSS_HOST_AXIS_WEIGHT,
                "score_percent": output_axis,
            },
            "cross_host_metric_identity": {
                "weight": ASR_ADVERSARIAL_VOICES_CROSS_HOST_AXIS_WEIGHT,
                "score_percent": metric_axis,
            },
            "comparison_signal_reproduction": {
                "weight": ASR_ADVERSARIAL_VOICES_CROSS_HOST_AXIS_WEIGHT,
                "score_percent": signal_rate["score_percent"],
            },
        }
        hard_conditions = {
            "distinct_host_instances_attested": True,
            "both_hosts_process_reproduced": (
                host_process_reproduction["successful_count"]
                == host_process_reproduction["observed_count"]
            ),
            "all_exact_transcripts_reproduced": (
                overall["exact_transcript_reproduction"]["successful_count"]
                == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            ),
            "all_normalized_transcripts_reproduced": (
                overall["normalized_transcript_reproduction"][
                    "successful_count"
                ]
                == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            ),
            "all_wer_values_reproduced": (
                overall["wer_reproduction"]["successful_count"]
                == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            ),
            "all_cer_values_reproduced": (
                overall["cer_reproduction"]["successful_count"]
                == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            ),
            "all_comparison_signals_reproduced": (
                signal_success == len(signals)
            ),
        }
        index = math.fsum(
            value["weight"] * value["score_percent"]
            for value in axes.values()
        )
        return {
            "overall": overall,
            "models": models,
            "comparison_signal_reproduction": signals,
            "host_process_reproduction": host_process_reproduction,
            "comparison_signal_reproduction_rate": signal_rate,
            "cross_host_reproduction_index": {
                "scale": "0_to_100",
                "aggregation": "equal_weight_macro_mean_over_five_axes",
                "axes": axes,
                "score_percent": index,
                "hard_conditions": hard_conditions,
                "hard_conditions_all_passed": all(hard_conditions.values()),
                "qualification_threshold_applied": False,
            },
        }

    @property
    def status(self) -> str:
        if self.aggregate["cross_host_reproduction_index"][
            "hard_conditions_all_passed"
        ]:
            return "reproduced"
        return "variation_observed"

    @property
    def payload(self) -> dict[str, object]:
        anchor = self.observations[0].anchor
        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_SCHEMA_VERSION
            ),
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_KEY,
                "version": (
                    ASR_ADVERSARIAL_VOICES_CROSS_HOST_REPRODUCIBILITY_VERSION
                ),
                "type": (
                    "content-free-distinct-host-process-reproducibility-evidence"
                ),
            },
            "protocol": {
                "expected_host_count": ASR_ADVERSARIAL_VOICES_CROSS_HOST_COUNT,
                "expected_process_run_count_per_host": (
                    ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT
                ),
                "distinct_host_instance_commitments_required": True,
                "distinct_host_attestation_evidence_required": True,
                "unique_coordinator_challenge_per_host_required": True,
                "same_cross_host_experiment_required": True,
                "same_source_runtime_model_and_cohort_required": True,
                "host_environment_identity_may_differ": True,
                "python_executable_identity_may_differ": True,
                "comparison_direction": "candidate_minus_baseline",
                "lower_error_values_are_better": True,
            },
            "status": self.status,
            "population": {
                "host_count": len(self.observations),
                "process_run_count": (
                    len(self.observations)
                    * ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT
                ),
                "model_count": ASR_ADVERSARIAL_VOICES_REPEATABILITY_MODEL_COUNT,
                "case_count_per_model": (
                    ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT
                ),
                "case_model_unit_count": (
                    ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
                ),
                "execution_count": (
                    len(self.observations)
                    * ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT
                    * ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
                ),
                "ordered_host_roles": [
                    value.host_role for value in self.observations
                ],
            },
            "portable_execution_commitments": {
                "source_code_sha256": anchor.source_code_sha256,
                "runtime_environment_sha256": (
                    anchor.runtime_environment_sha256
                ),
                "model_set_sha256": anchor.model_set_sha256,
                "matched_control_suite_sha256": (
                    anchor.matched_control_suite_sha256
                ),
                "adversarial_suite_evidence_sha256": (
                    anchor.adversarial_suite_evidence_sha256
                ),
            },
            "host_observations": [
                value.payload for value in self.observations
            ],
            "reproducibility": {
                "engineer_metrics": {
                    "cross_host_output_identity": (
                        "Transcript commitments across all six child runs."
                    ),
                    "cross_host_metric_identity": (
                        "WER/CER equality across all six child runs."
                    ),
                    "host_process_reproduction": (
                        "Complete B11H hard-condition conformance per host."
                    ),
                    "comparison_signal_reproduction": (
                        "Aggregate metric and candidate-direction stability."
                    ),
                    "cross_host_reproduction_index": (
                        "Equal-weight attestation, process, output, metric, "
                        "and comparison-signal score."
                    ),
                },
                "aggregate": self.aggregate,
            },
            "evidence_boundary": {
                "development_evidence_only": True,
                "content_free_json_evidence_only": True,
                "two_distinct_host_instance_commitments_verified": True,
                "host_attestation_documents_embedded": False,
                "six_independent_operating_system_processes_verified": True,
                "cross_host_reproducibility_evaluated": True,
                "cross_host_reproducibility_verified": (
                    self.status == "reproduced"
                ),
                "reproducibility_verified": self.status == "reproduced",
                "raw_audio_embedded": False,
                "raw_reference_transcripts_embedded": False,
                "raw_generated_transcripts_embedded": False,
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
        return _sha256_payload(self.payload)

    def require_cross_host_reproducibility_verified(self) -> None:
        if self.status != "reproduced":
            raise ASRAdversarialVOiCESCrossHostReproducibilityError(
                "B11J cross-host evidence contains variation."
            )

    def require_qualification(self) -> None:
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J is descriptive development evidence; no qualification "
            "threshold was applied."
        )

    def require_release_enforcement(self) -> None:
        raise ASRAdversarialVOiCESCrossHostReproducibilityError(
            "B11J cross-host evidence does not authorize release enforcement."
        )


def evaluate_asr_adversarial_voices_cross_host_reproducibility_v1(
    *,
    observations: tuple[ASRAdversarialVOiCESCrossHostObservation, ...],
) -> ASRAdversarialVOiCESCrossHostReproducibilityBundle:
    """Evaluate two independently attested complete B11H host bundles."""

    return ASRAdversarialVOiCESCrossHostReproducibilityBundle(
        observations=observations
    )
