"""Execution evidence for adversarial ASR development evaluation.

This module binds one sealed adversarial case to an ASR execution and to
already-produced semantic observations.

It deliberately does not:
- execute an ASR provider,
- execute semantic evaluators,
- infer acoustic conditions,
- store raw audio,
- store raw generated transcripts,
- calculate qualification thresholds,
- issue certification,
- authorize production use, or
- modify release authority.

Evaluator execution belongs to a later orchestration layer. This module only
validates identities and seals deterministic execution evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    EvaluatorVersion,
    HveeContractError,
    MetricDefinition,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.adversarial_evidence import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialSuiteDefinition,
    verify_asr_adversarial_evidence_v1,
)
from hvee.packs.asr.critical_identifier_fidelity import (
    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
    CRITICAL_IDENTIFIER_METRICS,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_METRICS,
)
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
    CRITICAL_TERMINOLOGY_METRICS,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
    ASRCriticalTerminologyProfile,
    calculate_critical_terminology_vocabulary_sha256,
)


ASR_ADVERSARIAL_EXECUTION_EVIDENCE_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_EXECUTION_EVIDENCE_KEY = (
    "hetren.asr.adversarial-execution-evidence.en-us"
)
ASR_ADVERSARIAL_EXECUTION_EVIDENCE_VERSION = "1.0.0"

ASR_ADVERSARIAL_TRANSCRIPT_COMMITMENT_SCHEME = (
    "sha256-domain-separated-utf8-json-v1"
)


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)


class ASRAdversarialExecutionStatus(StrEnum):
    """Outcome of the ASR execution before semantic evidence sealing."""

    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    INVALID = "invalid"


class ASRAdversarialTerminologyState(StrEnum):
    """Whether a terminology vocabulary was configured for this execution."""

    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not _IDENTIFIER_PATTERN.fullmatch(value)
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )

    return value


def _require_non_empty_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise HveeContractError(
            f"{name} must be a non-empty trimmed string"
        )

    return value


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
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _canonicalize_json_value(
    value: object,
) -> object:
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
            "adversarial execution JSON value must be "
            "valid deterministic JSON"
        ) from exc


def _canonical_json(
    value: object,
) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "adversarial execution evidence must contain "
            "valid deterministic JSON"
        ) from exc


def calculate_asr_adversarial_execution_evidence_sha256(
    payload: object,
) -> str:
    """Hash canonical adversarial execution evidence."""

    return hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()


def calculate_asr_adversarial_transcript_sha256(
    transcript: str,
) -> str:
    """Commit to a generated transcript without storing it in the artifact."""

    _require_non_empty_string(
        name="generated transcript",
        value=transcript,
    )

    commitment = {
        "domain": (
            ASR_ADVERSARIAL_EXECUTION_EVIDENCE_KEY
        ),
        "scheme": (
            ASR_ADVERSARIAL_TRANSCRIPT_COMMITMENT_SCHEME
        ),
        "kind": "generated_transcript",
        "text": transcript,
    }

    return hashlib.sha256(
        _canonical_json(commitment).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialTerminologyBinding:
    """Exact Critical Terminology configuration for one execution."""

    state: ASRAdversarialTerminologyState
    profile: ASRCriticalTerminologyProfile | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.state,
            ASRAdversarialTerminologyState,
        ):
            raise HveeContractError(
                "adversarial terminology binding requires "
                "a versioned state"
            )

        if (
            self.state
            == ASRAdversarialTerminologyState.NOT_CONFIGURED
        ):
            if self.profile is not None:
                raise HveeContractError(
                    "not-configured terminology binding "
                    "cannot contain a profile"
                )

            return

        if not isinstance(
            self.profile,
            ASRCriticalTerminologyProfile,
        ):
            raise HveeContractError(
                "configured terminology binding requires "
                "ASRCriticalTerminologyProfile"
            )

    @property
    def profile_key(self) -> str | None:
        if self.profile is None:
            return None

        return self.profile.key

    @property
    def profile_version(self) -> str | None:
        if self.profile is None:
            return None

        return self.profile.version

    @property
    def vocabulary_sha256(self) -> str | None:
        if self.profile is None:
            return None

        return (
            calculate_critical_terminology_vocabulary_sha256(
                self.profile
            )
        )


def _expected_observation_identity(
    *,
    metric: MetricDefinition,
    evaluator: EvaluatorVersion,
) -> tuple[
    str,
    str,
    str,
    str,
    str,
    MetricValueType,
]:
    return (
        metric.key,
        metric.version,
        evaluator.key,
        evaluator.version,
        evaluator.evaluation_type,
        metric.value_type,
    )


def _observation_identity(
    observation: Observation,
) -> tuple[
    str,
    str,
    str,
    str,
    str,
    MetricValueType,
]:
    return (
        observation.metric_key,
        observation.metric_version,
        observation.evaluator_key,
        observation.evaluator_version,
        observation.evaluation_type,
        observation.value_type,
    )


def _validate_observation_family(
    *,
    name: str,
    observations: tuple[Observation, ...],
    metrics: tuple[MetricDefinition, ...],
    evaluator: EvaluatorVersion,
) -> None:
    if (
        not isinstance(observations, tuple)
        or not all(
            isinstance(
                observation,
                Observation,
            )
            for observation in observations
        )
    ):
        raise HveeContractError(
            f"{name} observations must be "
            "a tuple of Observation values"
        )

    if len(observations) != len(metrics):
        raise HveeContractError(
            f"{name} observations must contain "
            f"exactly {len(metrics)} metrics"
        )

    for index, (
        observation,
        metric,
    ) in enumerate(
        zip(
            observations,
            metrics,
            strict=True,
        ),
        start=1,
    ):
        expected = _expected_observation_identity(
            metric=metric,
            evaluator=evaluator,
        )
        actual = _observation_identity(
            observation
        )

        if actual != expected:
            raise HveeContractError(
                f"{name} observation {index} "
                "does not match its canonical "
                "scientific identity and order"
            )


def _validate_terminology_vocabulary_binding(
    *,
    observations: tuple[Observation, ...],
    binding: ASRAdversarialTerminologyBinding,
) -> None:
    vocabulary_observation = next(
        (
            observation
            for observation in observations
            if observation.metric_key
            == (
                CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC.key
            )
        ),
        None,
    )

    if vocabulary_observation is None:
        raise HveeContractError(
            "configured terminology observations "
            "must contain vocabulary identity"
        )

    if (
        vocabulary_observation.status
        != ObservationStatus.SUCCESS
        or vocabulary_observation.value_type
        != MetricValueType.STRING
        or vocabulary_observation.value
        != binding.vocabulary_sha256
    ):
        raise HveeContractError(
            "terminology vocabulary observation "
            "does not match configured vocabulary"
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialSemanticObservations:
    """Already-produced semantic observations for one completed execution."""

    critical_number: tuple[Observation, ...]
    critical_identifier: tuple[Observation, ...]
    critical_terminology: tuple[Observation, ...]

    def __post_init__(self) -> None:
        _validate_observation_family(
            name="Critical Number",
            observations=self.critical_number,
            metrics=CRITICAL_NUMBER_METRICS,
            evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR,
        )

        _validate_observation_family(
            name="Critical Identifier",
            observations=self.critical_identifier,
            metrics=CRITICAL_IDENTIFIER_METRICS,
            evaluator=(
                CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR
            ),
        )

        if self.critical_terminology:
            _validate_observation_family(
                name="Critical Terminology",
                observations=self.critical_terminology,
                metrics=CRITICAL_TERMINOLOGY_METRICS,
                evaluator=(
                    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR
                ),
            )
        elif not isinstance(
            self.critical_terminology,
            tuple,
        ):
            raise HveeContractError(
                "Critical Terminology observations "
                "must be a tuple"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialExecutionDefinition:
    """Caller-owned execution inputs to be sealed as development evidence."""

    execution_id: str
    case_id: str
    provider_key: str
    model_key: str
    execution_environment_sha256: str
    status: ASRAdversarialExecutionStatus
    terminology: ASRAdversarialTerminologyBinding
    generated_transcript_sha256: str | None
    semantic_observations: (
        ASRAdversarialSemanticObservations
        | None
    )
    status_detail: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(
            name="adversarial execution id",
            value=self.execution_id,
        )
        _require_identifier(
            name="adversarial case id",
            value=self.case_id,
        )
        _require_non_empty_string(
            name="ASR provider key",
            value=self.provider_key,
        )
        _require_non_empty_string(
            name="ASR model key",
            value=self.model_key,
        )
        _require_sha256(
            name="execution environment",
            value=self.execution_environment_sha256,
        )

        if not isinstance(
            self.status,
            ASRAdversarialExecutionStatus,
        ):
            raise HveeContractError(
                "adversarial execution requires "
                "a versioned status"
            )

        if not isinstance(
            self.terminology,
            ASRAdversarialTerminologyBinding,
        ):
            raise HveeContractError(
                "adversarial execution requires "
                "terminology configuration"
            )

        if (
            self.status
            == ASRAdversarialExecutionStatus.COMPLETED
        ):
            _require_sha256(
                name="generated transcript commitment",
                value=self.generated_transcript_sha256,
            )

            if not isinstance(
                self.semantic_observations,
                ASRAdversarialSemanticObservations,
            ):
                raise HveeContractError(
                    "completed adversarial execution "
                    "requires semantic observations"
                )

            if self.status_detail is not None:
                raise HveeContractError(
                    "completed adversarial execution "
                    "cannot contain failure detail"
                )

            terminology_observations = (
                self.semantic_observations
                .critical_terminology
            )

            if (
                self.terminology.state
                == ASRAdversarialTerminologyState.CONFIGURED
            ):
                if not terminology_observations:
                    raise HveeContractError(
                        "configured terminology execution "
                        "requires Critical Terminology observations"
                    )

                _validate_terminology_vocabulary_binding(
                    observations=terminology_observations,
                    binding=self.terminology,
                )

            elif terminology_observations:
                raise HveeContractError(
                    "not-configured terminology execution "
                    "cannot contain Critical Terminology observations"
                )

            return

        if self.generated_transcript_sha256 is not None:
            raise HveeContractError(
                "non-completed adversarial execution "
                "cannot contain a generated transcript commitment"
            )

        if self.semantic_observations is not None:
            raise HveeContractError(
                "non-completed adversarial execution "
                "cannot contain semantic observations"
            )

        if (
            not isinstance(
                self.status_detail,
                str,
            )
            or not self.status_detail.strip()
        ):
            raise HveeContractError(
                "non-completed adversarial execution "
                "requires status detail"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialExecutionEvidenceBundle:
    """Deterministic non-certifying execution evidence."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "adversarial execution evidence "
                "payload must be an object"
            )

        _require_sha256(
            name="adversarial execution evidence",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_execution_evidence_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "adversarial execution evidence "
                "SHA-256 does not match its payload"
            )


def _canonical_observation_value(
    observation: Observation,
) -> object | None:
    if (
        observation.status
        != ObservationStatus.SUCCESS
    ):
        return None

    if (
        observation.value_type
        == MetricValueType.NUMBER
    ):
        return float(
            observation.value
        )

    if (
        observation.value_type
        == MetricValueType.JSON
    ):
        return _canonicalize_json_value(
            observation.value
        )

    return observation.value


def _observation_payload(
    observation: Observation,
) -> dict[str, object]:
    return {
        "metric": {
            "key": observation.metric_key,
            "version": observation.metric_version,
        },
        "evaluator": {
            "key": observation.evaluator_key,
            "version": (
                observation.evaluator_version
            ),
        },
        "evaluation_type": (
            observation.evaluation_type
        ),
        "status": observation.status.value,
        "value_type": (
            observation.value_type.value
        ),
        "value": _canonical_observation_value(
            observation
        ),
        "status_detail": (
            observation.status_detail
        ),
    }


def _family_payload(
    observations: tuple[Observation, ...],
) -> dict[str, object]:
    return {
        "count": len(observations),
        "observations": [
            _observation_payload(
                observation
            )
            for observation in observations
        ],
    }


def _terminology_binding_payload(
    binding: ASRAdversarialTerminologyBinding,
) -> dict[str, object]:
    if (
        binding.state
        == ASRAdversarialTerminologyState.NOT_CONFIGURED
    ):
        return {
            "state": binding.state.value,
            "profile": None,
        }

    return {
        "state": binding.state.value,
        "profile": {
            "key": binding.profile_key,
            "version": binding.profile_version,
            "vocabulary_sha256": (
                binding.vocabulary_sha256
            ),
        },
    }


def _semantic_payload(
    observations: ASRAdversarialSemanticObservations,
) -> dict[str, object]:
    return {
        "critical_number": _family_payload(
            observations.critical_number
        ),
        "critical_identifier": _family_payload(
            observations.critical_identifier
        ),
        "critical_terminology": _family_payload(
            observations.critical_terminology
        ),
    }


def _find_case(
    *,
    suite: ASRAdversarialSuiteDefinition,
    case_id: str,
):
    for case in suite.cases:
        if case.case_id == case_id:
            return case

    raise HveeContractError(
        "adversarial execution case does not "
        "exist in the sealed suite"
    )


def build_asr_adversarial_execution_evidence_v1(
    definition: ASRAdversarialExecutionDefinition,
    *,
    suite: ASRAdversarialSuiteDefinition,
    suite_evidence: ASRAdversarialEvidenceBundle,
) -> ASRAdversarialExecutionEvidenceBundle:
    """Build one deterministic execution-evidence artifact."""

    if not isinstance(
        definition,
        ASRAdversarialExecutionDefinition,
    ):
        raise HveeContractError(
            "adversarial execution evidence requires "
            "ASRAdversarialExecutionDefinition"
        )

    if not isinstance(
        suite,
        ASRAdversarialSuiteDefinition,
    ):
        raise HveeContractError(
            "adversarial execution evidence requires "
            "ASRAdversarialSuiteDefinition"
        )

    if not isinstance(
        suite_evidence,
        ASRAdversarialEvidenceBundle,
    ):
        raise HveeContractError(
            "adversarial execution evidence requires "
            "sealed suite evidence"
        )

    verified_suite = (
        verify_asr_adversarial_evidence_v1(
            payload=suite_evidence.payload,
            expected_sha256=suite_evidence.sha256,
            definition=suite,
        )
    )

    case = _find_case(
        suite=suite,
        case_id=definition.case_id,
    )

    if (
        case.semantic_load.critical_terminology_count
        > 0
        and definition.terminology.state
        != ASRAdversarialTerminologyState.CONFIGURED
    ):
        raise HveeContractError(
            "adversarial case declaring critical "
            "terminology requires configured vocabulary"
        )

    semantic_payload = (
        _semantic_payload(
            definition.semantic_observations
        )
        if definition.semantic_observations
        is not None
        else None
    )

    transcript_payload = (
        {
            "scheme": (
                ASR_ADVERSARIAL_TRANSCRIPT_COMMITMENT_SCHEME
            ),
            "sha256": (
                definition.generated_transcript_sha256
            ),
        }
        if definition.generated_transcript_sha256
        is not None
        else None
    )

    payload: dict[str, object] = {
        "schema_version": (
            ASR_ADVERSARIAL_EXECUTION_EVIDENCE_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_EXECUTION_EVIDENCE_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_EXECUTION_EVIDENCE_VERSION
            ),
            "type": (
                "source_visible_adversarial_"
                "execution_evidence"
            ),
        },
        "suite": {
            "key": ASR_ADVERSARIAL_EVIDENCE_KEY,
            "version": (
                ASR_ADVERSARIAL_EVIDENCE_VERSION
            ),
            "sha256": verified_suite.sha256,
        },
        "case": {
            "case_id": case.case_id,
            "audio_asset_sha256": (
                case.audio_asset_sha256
            ),
        },
        "execution": {
            "execution_id": (
                definition.execution_id
            ),
            "provider": {
                "key": definition.provider_key,
                "model_key": definition.model_key,
            },
            "environment_sha256": (
                definition.execution_environment_sha256
            ),
            "status": definition.status.value,
            "status_detail": (
                definition.status_detail
            ),
            "generated_transcript": (
                transcript_payload
            ),
        },
        "semantic_configuration": {
            "critical_terminology": (
                _terminology_binding_payload(
                    definition.terminology
                )
            ),
        },
        "semantic_evidence": (
            semantic_payload
        ),
        "scientific_boundary": {
            "sealed_suite_reverified": True,
            "audio_asset_inherited_from_sealed_suite": True,
            "raw_audio_in_artifact": False,
            "raw_generated_transcript_in_artifact": False,
            "semantic_observations_consumed_not_recomputed": True,
            "semantic_evaluator_methodology_modified": False,
            "acoustic_cause_inferred_from_transcript": False,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }

    return ASRAdversarialExecutionEvidenceBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_execution_evidence_sha256(
                payload
            )
        ),
    )


def verify_asr_adversarial_execution_evidence_v1(
    *,
    payload: object,
    expected_sha256: object,
    definition: ASRAdversarialExecutionDefinition,
    suite: ASRAdversarialSuiteDefinition,
    suite_evidence: ASRAdversarialEvidenceBundle,
) -> ASRAdversarialExecutionEvidenceBundle:
    """Require exact equality with rebuilt v1 execution evidence."""

    digest = _require_sha256(
        name="expected adversarial execution evidence",
        value=expected_sha256,
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError(
            "supplied adversarial execution "
            "evidence must be an object"
        )

    supplied = (
        ASRAdversarialExecutionEvidenceBundle(
            payload=payload,
            sha256=digest,
        )
    )

    rebuilt = (
        build_asr_adversarial_execution_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    if (
        supplied.payload != rebuilt.payload
        or supplied.sha256 != rebuilt.sha256
    ):
        raise HveeContractError(
            "adversarial execution evidence "
            "does not match the v1 definition"
        )

    return rebuilt
