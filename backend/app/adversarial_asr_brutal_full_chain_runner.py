"""Execute the complete ASR Brutal Validation v1 evidence workflow.

The existing brutal execution runner is intentionally only the first stage:
it executes the two frozen models and preserves their campaign evidence.  This
module consumes that real execution in the same run and builds the remaining
cross-stage evidence without changing evaluator methodology.

The final governance stage fails closed.  It records that independent human
review is required; it never invents reviewers, promotes a contract, issues a
certificate, or grants qualification/release authority.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import sys
import wave
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from app.adversarial_asr_brutal_campaign import (
    ASRBrutalValidationSuiteBundle,
    execute_asr_brutal_validation_campaign_v1,
)
from app.adversarial_asr_brutal_execution_runner import (
    ASRBrutalExecutionRunResult,
    ASRBrutalFrozenModel,
    ASR_BRUTAL_FROZEN_MODELS_V1,
    _canonical_json_bytes,
    _write_bundle,
    execute_asr_brutal_validation_run_v1,
    verify_asr_brutal_frozen_model_v1,
)
from app.incident_controlled_replay_execution import (
    ASRProviderIncidentReplayAdapter,
    IncidentReplayArtifact,
    execute_incident_controlled_replay,
)
from app.incident_environment_materialization_execution import (
    IncidentRunnerMaterializedContext,
    build_incident_materialization_compatibility_observation,
    build_incident_materialization_observations,
)
from app.incident_runner_compatibility_service import (
    INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES,
)
from app.runner_config import LocalRunnerSettings
from app.speech import ASRProvider, get_asr_provider
from hvee.core.adaptive_scenario_search import (
    AdaptiveScenarioObservation,
    build_adaptive_scenario_search_bundle,
)
from hvee.core.counterexample_contract_promotion import (
    RegressionContractDefinition,
    build_counterexample_contract_proposal_bundle,
)
from hvee.core.counterexample_evidence import (
    CounterexampleEvidenceBundle,
    CounterexampleFailure,
    build_counterexample_evidence_bundle,
    calculate_scenario_sha256,
)
from hvee.core.decision import DecisionVerdict
from hvee.core.incident_environment_manifest import (
    build_incident_environment_manifest_bundle,
)
from hvee.core.incident_environment_materialization import (
    IncidentOperatorAuthorization,
    build_incident_environment_materialization_bundle,
)
from hvee.core.incident_intake import (
    IncidentAffectedStage,
    IncidentArtifactKind,
    IncidentArtifactReference,
    IncidentAudioContext,
    IncidentClaim,
    IncidentProcessingState,
    IncidentRuntimeContext,
    IncidentSeverity,
    IncidentTransportContext,
    IncidentTransportKind,
    build_incident_intake_bundle,
)
from hvee.core.incident_integration_gate import (
    build_incident_integration_gate_bundle,
)
from hvee.core.incident_replay_preparation import (
    IncidentArtifactMaterial,
    build_incident_replay_preparation_bundle,
)
from hvee.core.incident_reproduction_evidence import (
    IncidentReproductionComparisonBasis,
    IncidentReproductionComparisonObservation,
    build_incident_reproduction_evidence_bundle,
)
from hvee.core.incident_runner_compatibility import (
    build_incident_runner_compatibility_bundle,
)
from hvee.core.minimal_counterexample_reduction import (
    CounterexampleReductionObservation,
    CounterexampleReductionUnit,
    build_minimal_counterexample_reduction_bundle,
)
from hvee.core.neighborhood_generation import (
    NeighborhoodCandidate,
    NeighborhoodMutationDirection,
    NeighborhoodObservation,
    build_neighborhood_generation_bundle,
)
from hvee.packs.asr.adversarial_execution_evidence import (
    calculate_asr_adversarial_execution_evidence_sha256,
    calculate_asr_adversarial_transcript_sha256,
)
from hvee.packs.asr.brutal_validation_plan import (
    ASR_BRUTAL_VALIDATION_CASES_V1,
    ASR_BRUTAL_VALIDATION_WORKFLOW_V1,
    build_asr_brutal_validation_plan_v1,
)
from hvee.core.incident_controlled_replay import (
    calculate_incident_generated_transcript_sha256,
)


ASR_BRUTAL_FULL_CHAIN_RUN_SCHEMA_VERSION = 1
ASR_BRUTAL_FULL_CHAIN_RUN_KEY = (
    "hetren.asr.brutal-validation-full-chain-run"
)
ASR_BRUTAL_FULL_CHAIN_RUN_VERSION = "1.0.0"

_PRIMARY_COUNTEREXAMPLE_CASE_ID = (
    "stress.noise-severe-usable.multi-number-id"
)
_NOISE_SEARCH_CASE_IDS = (
    "clean.multi-number-id",
    _PRIMARY_COUNTEREXAMPLE_CASE_ID,
    "stress.noise-moderate.multi-number-id",
)
_NEIGHBORHOOD_CASES = (
    (
        "stress.noise-moderate.multi-number-id",
        "noise",
        NeighborhoodMutationDirection.LOWER,
        1,
    ),
    (
        "clean.multi-number-id",
        "noise",
        NeighborhoodMutationDirection.LOWER,
        2,
    ),
    (
        "stress.telephony-bandwidth.multi-number-id",
        "channel-bandwidth",
        NeighborhoodMutationDirection.ALTERNATE,
        1,
    ),
    (
        "stress.codec-aac.multi-number-id",
        "codec-aac",
        NeighborhoodMutationDirection.ALTERNATE,
        1,
    ),
    (
        "stress.codec-alaw.multi-number-id",
        "codec-alaw",
        NeighborhoodMutationDirection.ALTERNATE,
        1,
    ),
    (
        "stress.codec-mp3.multi-number-id",
        "codec-mp3",
        NeighborhoodMutationDirection.ALTERNATE,
        1,
    ),
    (
        "stress.codec-mulaw.multi-number-id",
        "codec-mulaw",
        NeighborhoodMutationDirection.ALTERNATE,
        1,
    ),
)

_PRESERVED_METRIC_BY_DIMENSION = {
    "critical_number": "asr.critical-number.preserved.en-us",
    "critical_identifier": (
        "asr.critical-identifier.preserved.en-us"
    ),
    "critical_terminology": (
        "asr.critical-terminology.preserved.en-us"
    ),
}


class ASRBrutalFullChainRunnerError(ValueError):
    """Raised when a full-chain run cannot produce trusted evidence."""


@dataclass(frozen=True, slots=True)
class ASRBrutalFullChainRunResult:
    output_root: Path
    payload: dict[str, object]
    sha256: str

    @property
    def status(self) -> str:
        return str(self.payload["status"])


@dataclass(frozen=True, slots=True)
class _CaseEvaluation:
    role: str
    case_id: str
    verdict: DecisionVerdict
    result_provenance_sha256: str
    observation_evidence_sha256: str
    decision_evidence_sha256: str
    wer: float
    cer: float
    required_observations: tuple[dict[str, object], ...]
    failures: tuple[CounterexampleFailure, ...]
    generated_transcript: str
    audio_asset_sha256: str
    audio_byte_length: int
    environment: dict[str, object]


ProviderFactory = Callable[..., ASRProvider]
ModelVerifier = Callable[[ASRBrutalFrozenModel], dict[str, object]]
CampaignExecutor = Callable[..., object]
ExecutionRunner = Callable[..., ASRBrutalExecutionRunResult]
RepositoryVerifier = Callable[[Path, str], str]


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(value)
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha256(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ASRBrutalFullChainRunnerError(
            f"{name} must be a lowercase SHA-256 digest."
        )
    return value


def _read_bundle_document(path: Path) -> tuple[dict[str, object], str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ASRBrutalFullChainRunnerError(
            f"Cannot read evidence bundle: {path.name}."
        ) from error

    if not isinstance(document, dict) or set(document) != {
        "payload",
        "sha256",
    }:
        raise ASRBrutalFullChainRunnerError(
            f"Evidence bundle has an invalid envelope: {path.name}."
        )

    payload = document["payload"]
    sha256 = _require_sha256(
        f"{path.name} envelope",
        document["sha256"],
    )
    if not isinstance(payload, dict) or _canonical_sha256(payload) != sha256:
        raise ASRBrutalFullChainRunnerError(
            f"Evidence bundle digest mismatch: {path.name}."
        )
    return payload, sha256


def _persist_core_bundle(path: Path, bundle) -> str:
    observed = _write_bundle(path, bundle.payload)
    if observed != bundle.sha256:
        raise ASRBrutalFullChainRunnerError(
            f"Core evidence digest disagreement: {path.name}."
        )
    return observed


def _verify_repository_identity(
    repository_root: Path,
    repository_commit: str,
) -> str:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        tree = subprocess.run(
            [
                "git",
                "ls-tree",
                "-r",
                "--full-tree",
                repository_commit,
            ],
            cwd=repository_root,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise ASRBrutalFullChainRunnerError(
            "Repository identity verification failed."
        ) from error

    if head != repository_commit:
        raise ASRBrutalFullChainRunnerError(
            "Repository HEAD differs from the authorized commit."
        )
    if status:
        raise ASRBrutalFullChainRunnerError(
            "Repository must be clean before full-chain execution."
        )
    return hashlib.sha256(tree).hexdigest()


def _prepare_full_chain_root(
    *,
    output_root: str | Path,
    repository_root: Path,
) -> Path:
    requested = Path(output_root)
    if not requested.is_absolute():
        raise ASRBrutalFullChainRunnerError(
            "Full-chain evidence output root must be absolute."
        )
    resolved = requested.resolve(strict=False)
    if resolved == repository_root or resolved.is_relative_to(repository_root):
        raise ASRBrutalFullChainRunnerError(
            "Full-chain evidence must be written outside the repository."
        )
    if resolved.exists():
        raise ASRBrutalFullChainRunnerError(
            "Full-chain evidence output already exists."
        )
    return resolved


def _execution_documents(
    *,
    execution_root: Path,
    bundle: ASRBrutalValidationSuiteBundle,
    repository_commit: str,
) -> tuple[
    dict[str, object],
    str,
    dict[str, dict[str, object]],
    dict[str, str],
]:
    summary, summary_sha256 = _read_bundle_document(
        execution_root / "summary.json"
    )
    if (
        summary.get("status") != "completed"
        or summary.get("repository_commit") != repository_commit
        or summary.get("case_count") != len(bundle.suite.cases)
    ):
        raise ASRBrutalFullChainRunnerError(
            "Audio execution summary is not a complete authorized run."
        )

    model_summaries = summary.get("models")
    if not isinstance(model_summaries, list):
        raise ASRBrutalFullChainRunnerError(
            "Audio execution model summaries are missing."
        )
    summaries_by_role = {
        value.get("role"): value
        for value in model_summaries
        if isinstance(value, dict)
    }
    if set(summaries_by_role) != {"baseline", "candidate"}:
        raise ASRBrutalFullChainRunnerError(
            "Audio execution requires baseline and candidate evidence."
        )

    campaigns: dict[str, dict[str, object]] = {}
    campaign_sha256s: dict[str, str] = {}
    expected_case_ids = {case.case_id for case in bundle.suite.cases}

    for model in ASR_BRUTAL_FROZEN_MODELS_V1:
        payload, sha256 = _read_bundle_document(
            execution_root / f"{model.role}.campaign.json"
        )
        model_summary = summaries_by_role[model.role]
        if (
            payload.get("role") != model.role
            or payload.get("repository_commit") != repository_commit
            or model_summary.get("artifact_sha256") != sha256
        ):
            raise ASRBrutalFullChainRunnerError(
                f"{model.role} campaign identity is inconsistent."
            )

        identity = payload.get("model_identity")
        if not isinstance(identity, dict) or (
            identity.get("model_name") != model.model_name
            or identity.get("repository") != model.repository
            or identity.get("revision") != model.revision
            or identity.get("model_binary_sha256")
            != model.model_binary_sha256
            or identity.get("model_binary_bytes")
            != model.model_binary_bytes
            or identity.get("resolved_offline") is not True
        ):
            raise ASRBrutalFullChainRunnerError(
                f"{model.role} frozen model identity is invalid."
            )

        results = payload.get("completed_results")
        if not isinstance(results, list) or {
            item.get("case_id")
            for item in results
            if isinstance(item, dict)
        } != expected_case_ids:
            raise ASRBrutalFullChainRunnerError(
                f"{model.role} does not contain the exact 13 completed cases."
            )
        if len(results) != len(expected_case_ids):
            raise ASRBrutalFullChainRunnerError(
                f"{model.role} contains duplicate completed cases."
            )

        campaigns[model.role] = payload
        campaign_sha256s[model.role] = sha256

    return summary, summary_sha256, campaigns, campaign_sha256s


def _verify_audio_and_child_evidence(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    campaigns: Mapping[str, dict[str, object]],
) -> None:
    expected_audio = {
        case_id: (
            _sha256_file(path),
            path.stat().st_size,
        )
        for case_id, path in bundle.audio_paths.items()
    }

    for role, campaign in campaigns.items():
        results = campaign["completed_results"]
        if not isinstance(results, list):
            raise ASRBrutalFullChainRunnerError(
                f"{role} completed results are invalid."
            )
        for result in results:
            if not isinstance(result, dict):
                raise ASRBrutalFullChainRunnerError(
                    f"{role} contains an invalid completed result."
                )
            case_id = result.get("case_id")
            if not isinstance(case_id, str) or case_id not in expected_audio:
                raise ASRBrutalFullChainRunnerError(
                    f"{role} contains an unknown case."
                )
            observed = (
                result.get("audio_asset_sha256"),
                result.get("audio_byte_length"),
            )
            if observed != expected_audio[case_id]:
                raise ASRBrutalFullChainRunnerError(
                    f"{role}/{case_id} audio evidence does not match bytes."
                )

            child = result.get("execution_evidence")
            if not isinstance(child, dict) or set(child) != {
                "payload",
                "sha256",
            }:
                raise ASRBrutalFullChainRunnerError(
                    f"{role}/{case_id} child execution evidence is invalid."
                )
            child_payload = child["payload"]
            child_sha256 = _require_sha256(
                f"{role}/{case_id} child execution evidence",
                child["sha256"],
            )
            if (
                not isinstance(child_payload, dict)
                or calculate_asr_adversarial_execution_evidence_sha256(
                    child_payload
                )
                != child_sha256
            ):
                raise ASRBrutalFullChainRunnerError(
                    f"{role}/{case_id} child evidence digest mismatch."
                )


def _normalized_metric(
    result: dict[str, object],
    metric_name: str,
) -> float:
    evidence = result.get("normalized_error_evidence")
    observation = (
        evidence.get(metric_name)
        if isinstance(evidence, dict)
        else None
    )
    if (
        not isinstance(observation, dict)
        or observation.get("status") != "success"
        or isinstance(observation.get("value"), bool)
        or not isinstance(observation.get("value"), (int, float))
        or not math.isfinite(float(observation.get("value")))
        or float(observation.get("value")) < 0.0
    ):
        raise ASRBrutalFullChainRunnerError(
            f"Canonical normalized {metric_name.upper()} is unavailable."
        )
    return float(observation["value"])


def _required_dimensions() -> dict[str, tuple[str, ...]]:
    return {
        requirement.case_id: tuple(
            dimension.value
            for dimension in requirement.semantic_dimensions
        )
        for requirement in ASR_BRUTAL_VALIDATION_CASES_V1
    }


def _critical_case_evaluation(
    *,
    role: str,
    result: dict[str, object],
    required_dimensions: tuple[str, ...],
) -> tuple[_CaseEvaluation, dict[str, object], dict[str, object]]:
    case_id = result.get("case_id")
    if not isinstance(case_id, str):
        raise ASRBrutalFullChainRunnerError(
            "Completed result case identity is invalid."
        )
    semantic = result.get("semantic_observations")
    if not isinstance(semantic, dict):
        raise ASRBrutalFullChainRunnerError(
            f"{role}/{case_id} semantic observations are unavailable."
        )

    selected: list[dict[str, object]] = []
    failures: list[CounterexampleFailure] = []
    inconclusive_reasons: list[str] = []

    for dimension in required_dimensions:
        metric_key = _PRESERVED_METRIC_BY_DIMENSION[dimension]
        family = semantic.get(dimension)
        matches = (
            [
                item
                for item in family
                if isinstance(item, dict)
                and item.get("metric_key") == metric_key
            ]
            if isinstance(family, list)
            else []
        )
        if len(matches) != 1:
            inconclusive_reasons.append(
                f"{dimension}-preservation-observation-count"
            )
            continue

        observation = matches[0]
        selected.append(observation)
        if observation.get("status") != "success":
            inconclusive_reasons.append(
                f"{dimension}-preservation-{observation.get('status')}"
            )
            continue
        if not isinstance(observation.get("value"), bool):
            raise ASRBrutalFullChainRunnerError(
                f"{role}/{case_id} preservation metric is not boolean."
            )
        if observation["value"] is False:
            failures.append(
                CounterexampleFailure(
                    key=f"asr.{dimension.replace('_', '-')}-fidelity",
                    version="1.0.0",
                    reason_code=(
                        f"{dimension.replace('_', '-')}-not-preserved"
                    ),
                    metric_key=str(observation["metric_key"]),
                    metric_version=str(observation["metric_version"]),
                    evaluator_key=str(observation["evaluator_key"]),
                    evaluator_version=str(
                        observation["evaluator_version"]
                    ),
                )
            )

    if failures:
        verdict = DecisionVerdict.FAIL
    elif inconclusive_reasons:
        verdict = DecisionVerdict.INCONCLUSIVE
    else:
        verdict = DecisionVerdict.PASS

    child = result["execution_evidence"]
    if not isinstance(child, dict):
        raise ASRBrutalFullChainRunnerError(
            f"{role}/{case_id} child evidence is invalid."
        )
    result_provenance_sha256 = str(child["sha256"])

    observation_record: dict[str, object] = {
        "schema_version": 1,
        "type": "brutal_critical_fidelity_observation",
        "role": role,
        "case_id": case_id,
        "result_provenance_sha256": result_provenance_sha256,
        "required_dimensions": list(required_dimensions),
        "preservation_observations": sorted(
            selected,
            key=lambda value: str(value.get("metric_key")),
        ),
    }
    observation_evidence_sha256 = _canonical_sha256(
        observation_record
    )
    observation_record["sha256"] = observation_evidence_sha256

    decision_record: dict[str, object] = {
        "schema_version": 1,
        "type": "brutal_critical_fidelity_decision",
        "role": role,
        "case_id": case_id,
        "observation_evidence_sha256": observation_evidence_sha256,
        "verdict": verdict.value,
        "failure_reason_codes": sorted(
            failure.reason_code for failure in failures
        ),
        "inconclusive_reasons": sorted(inconclusive_reasons),
        "rule": (
            "fail_on_any_required_preserved_false;"
            "inconclusive_on_missing_or_non-success;"
            "pass_only_when_all_required_preserved_true"
        ),
    }
    decision_evidence_sha256 = _canonical_sha256(decision_record)
    decision_record["sha256"] = decision_evidence_sha256

    generated_transcript = result.get("generated_transcript")
    environment = result.get("environment")
    if not isinstance(generated_transcript, str) or not isinstance(
        environment,
        dict,
    ):
        raise ASRBrutalFullChainRunnerError(
            f"{role}/{case_id} completed output is invalid."
        )
    expected_model = (
        "small.en" if role == "baseline" else "large-v3-turbo"
    )
    if environment != {
        "provider": "faster_whisper",
        "model_name": expected_model,
        "device": "cpu",
        "compute_type": "int8_float32",
    }:
        raise ASRBrutalFullChainRunnerError(
            f"{role}/{case_id} runtime identity differs from the frozen run."
        )

    return (
        _CaseEvaluation(
            role=role,
            case_id=case_id,
            verdict=verdict,
            result_provenance_sha256=result_provenance_sha256,
            observation_evidence_sha256=observation_evidence_sha256,
            decision_evidence_sha256=decision_evidence_sha256,
            wer=_normalized_metric(result, "wer"),
            cer=_normalized_metric(result, "cer"),
            required_observations=tuple(selected),
            failures=tuple(failures),
            generated_transcript=generated_transcript,
            audio_asset_sha256=str(result["audio_asset_sha256"]),
            audio_byte_length=int(result["audio_byte_length"]),
            environment=environment,
        ),
        observation_record,
        decision_record,
    )


def _critical_fidelity_evidence(
    campaigns: Mapping[str, dict[str, object]],
) -> tuple[
    dict[str, object],
    dict[tuple[str, str], _CaseEvaluation],
]:
    dimensions = _required_dimensions()
    evaluations: dict[tuple[str, str], _CaseEvaluation] = {}
    records: list[dict[str, object]] = []

    for role in ("baseline", "candidate"):
        results = campaigns[role]["completed_results"]
        if not isinstance(results, list):
            raise ASRBrutalFullChainRunnerError(
                f"{role} completed results are invalid."
            )
        for result in sorted(
            results,
            key=lambda value: str(value.get("case_id")),
        ):
            if not isinstance(result, dict):
                raise ASRBrutalFullChainRunnerError(
                    f"{role} completed result is invalid."
                )
            case_id = str(result.get("case_id"))
            evaluation, observation, decision = (
                _critical_case_evaluation(
                    role=role,
                    result=result,
                    required_dimensions=dimensions[case_id],
                )
            )
            evaluations[(role, case_id)] = evaluation
            records.append(
                {
                    "role": role,
                    "case_id": case_id,
                    "normalized_wer": evaluation.wer,
                    "normalized_cer": evaluation.cer,
                    "critical_fidelity_verdict": (
                        evaluation.verdict.value
                    ),
                    "observation_evidence": observation,
                    "decision_evidence": decision,
                }
            )

    summaries: dict[str, dict[str, object]] = {}
    for role in ("baseline", "candidate"):
        selected = [
            value
            for (selected_role, _case_id), value in evaluations.items()
            if selected_role == role
        ]
        summaries[role] = {
            "case_count": len(selected),
            "macro_wer": sum(value.wer for value in selected)
            / len(selected),
            "macro_cer": sum(value.cer for value in selected)
            / len(selected),
            "critical_fidelity_verdict_counts": {
                verdict.value: sum(
                    value.verdict == verdict for value in selected
                )
                for verdict in (
                    DecisionVerdict.PASS,
                    DecisionVerdict.FAIL,
                    DecisionVerdict.INCONCLUSIVE,
                )
            },
        }

    return (
        {
            "schema_version": 1,
            "type": "critical_fidelity_evaluation",
            "stage": "critical_fidelity_evaluation",
            "records": records,
            "model_summaries": summaries,
            "comparison": {
                "candidate_minus_baseline_macro_wer": (
                    float(summaries["candidate"]["macro_wer"])
                    - float(summaries["baseline"]["macro_wer"])
                ),
                "candidate_minus_baseline_macro_cer": (
                    float(summaries["candidate"]["macro_cer"])
                    - float(summaries["baseline"]["macro_cer"])
                ),
                "model_winner_declared": False,
            },
            "evidence_boundary": {
                "existing_evaluators_only": True,
                "wer_cer_attached": True,
                "critical_semantic_preservation_evaluated": True,
                "qualification_threshold_applied": False,
                "statistical_significance_claimed": False,
                "certification_issued": False,
            },
        },
        evaluations,
    )


def _case_by_id(bundle: ASRBrutalValidationSuiteBundle):
    return {case.case_id: case for case in bundle.suite.cases}


def _scenario_parameters(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    evaluation: _CaseEvaluation,
) -> dict[str, object]:
    case = _case_by_id(bundle)[evaluation.case_id]
    condition = case.condition
    return {
        "role": evaluation.role,
        "model_name": str(evaluation.environment["model_name"]),
        "audio_asset_sha256": evaluation.audio_asset_sha256,
        "reference_transcript_sha256": (
            calculate_asr_adversarial_transcript_sha256(
                case.reference_transcript
            )
        ),
        "channel": condition.channel.value,
        "codec": condition.codec.value,
        "sample_rate_hz": condition.sample_rate_hz,
        "noise": condition.noise.value,
        "speaking_rate": condition.speaking_rate.value,
        "speech_variety_key": condition.speech_variety_key,
        "overlap": condition.overlap.value,
        "duration": condition.duration.value,
    }


def _scenario_sha256(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    evaluation: _CaseEvaluation,
) -> str:
    return calculate_scenario_sha256(
        scenario_key="hetren.asr.brutal-validation-case",
        scenario_version="1.0.0",
        case_id=evaluation.case_id,
        parameters=_scenario_parameters(
            bundle=bundle,
            evaluation=evaluation,
        ),
    )


def _counterexample_inventory(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    evaluations: Mapping[tuple[str, str], _CaseEvaluation],
) -> tuple[
    dict[str, object],
    dict[str, CounterexampleEvidenceBundle],
]:
    counterexamples: dict[str, CounterexampleEvidenceBundle] = {}
    for (role, case_id), evaluation in sorted(evaluations.items()):
        if role != "candidate" or evaluation.verdict != DecisionVerdict.FAIL:
            continue
        counterexamples[case_id] = build_counterexample_evidence_bundle(
            evaluation_type="asr",
            scenario_key="hetren.asr.brutal-validation-case",
            scenario_version="1.0.0",
            case_id=case_id,
            parameters=_scenario_parameters(
                bundle=bundle,
                evaluation=evaluation,
            ),
            result_provenance_sha256=(
                evaluation.result_provenance_sha256
            ),
            observation_evidence_sha256=(
                evaluation.observation_evidence_sha256
            ),
            decision_evidence_sha256=(
                evaluation.decision_evidence_sha256
            ),
            failures=evaluation.failures,
        )

    primary = counterexamples.get(_PRIMARY_COUNTEREXAMPLE_CASE_ID)
    if primary is None:
        raise ASRBrutalFullChainRunnerError(
            "The locked severe-noise critical-identifier counterexample "
            "was not observed; the downstream chain cannot be fabricated."
        )

    return (
        {
            "schema_version": 1,
            "type": "brutal_counterexample_inventory",
            "stage": "counterexample_evidence",
            "primary_case_id": _PRIMARY_COUNTEREXAMPLE_CASE_ID,
            "primary": {
                "payload": primary.payload,
                "sha256": primary.sha256,
            },
            "additional": [
                {
                    "case_id": case_id,
                    "payload": value.payload,
                    "sha256": value.sha256,
                }
                for case_id, value in sorted(counterexamples.items())
                if case_id != _PRIMARY_COUNTEREXAMPLE_CASE_ID
            ],
            "evidence_boundary": {
                "observed_failures_only": True,
                "causal_explanation_claimed": False,
                "contract_promoted": False,
                "qualification_authority": False,
            },
        },
        counterexamples,
    )


def _adaptive_search(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    evaluations: Mapping[tuple[str, str], _CaseEvaluation],
    counterexamples: Mapping[str, CounterexampleEvidenceBundle],
):
    clean = evaluations[("candidate", _NOISE_SEARCH_CASE_IDS[0])]
    severe = evaluations[("candidate", _NOISE_SEARCH_CASE_IDS[1])]
    moderate = evaluations[("candidate", _NOISE_SEARCH_CASE_IDS[2])]
    ordered = (
        (1, 0, clean),
        (2, 2, severe),
        (3, 1, moderate),
    )
    observations = []
    for sequence, candidate_index, evaluation in ordered:
        if evaluation.verdict not in {
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        }:
            raise ASRBrutalFullChainRunnerError(
                "Noise boundary search requires decisive real observations."
            )
        counterexample = counterexamples.get(evaluation.case_id)
        observations.append(
            AdaptiveScenarioObservation(
                sequence=sequence,
                candidate_index=candidate_index,
                scenario_sha256=_scenario_sha256(
                    bundle=bundle,
                    evaluation=evaluation,
                ),
                verdict=evaluation.verdict,
                result_provenance_sha256=(
                    evaluation.result_provenance_sha256
                ),
                observation_evidence_sha256=(
                    evaluation.observation_evidence_sha256
                ),
                decision_evidence_sha256=(
                    evaluation.decision_evidence_sha256
                ),
                counterexample_evidence_sha256=(
                    counterexample.sha256
                    if counterexample is not None
                    else None
                ),
            )
        )

    reference = _case_by_id(bundle)[clean.case_id].reference_transcript
    search = build_adaptive_scenario_search_bundle(
        evaluation_type="asr",
        search_key="hetren.asr.brutal-noise-severity-search",
        search_version="1.0.0",
        boundary_key="hetren.asr.brutal-noise-observed-boundary",
        boundary_version="1.0.0",
        axis_key="asr.noise.severity-rank",
        axis_version="1.0.0",
        axis_unit="ordinal",
        candidate_values=(0, 1, 2),
        invariant_parameters={
            "model_name": str(clean.environment["model_name"]),
            "utterance_family": "multi-number-id",
            "reference_transcript_sha256": (
                calculate_asr_adversarial_transcript_sha256(reference)
            ),
        },
        maximum_observations=3,
        observations=tuple(observations),
    )
    if search.observed_boundary is None:
        raise ASRBrutalFullChainRunnerError(
            "Executed noise observations did not establish a boundary."
        )
    return search


def _minimal_reduction(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    evaluations: Mapping[tuple[str, str], _CaseEvaluation],
    primary: CounterexampleEvidenceBundle,
):
    clean = evaluations[("candidate", "clean.multi-number-id")]
    if clean.verdict != DecisionVerdict.PASS:
        raise ASRBrutalFullChainRunnerError(
            "Removing the declared severe-noise unit was not a passing "
            "executed control; one-minimality cannot be claimed."
        )
    unit_commitment = _canonical_sha256(
        {
            "unit": "severe-noise-mutation",
            "source_case_id": _PRIMARY_COUNTEREXAMPLE_CASE_ID,
            "source_audio_sha256": (
                evaluations[
                    ("candidate", _PRIMARY_COUNTEREXAMPLE_CASE_ID)
                ].audio_asset_sha256
            ),
            "removed_to_case_id": clean.case_id,
            "removed_to_audio_sha256": clean.audio_asset_sha256,
            "suite_evidence_sha256": bundle.suite_evidence.sha256,
        }
    )
    observation = CounterexampleReductionObservation(
        sequence=1,
        removed_unit_index=0,
        scenario_sha256=_scenario_sha256(
            bundle=bundle,
            evaluation=clean,
        ),
        verdict=DecisionVerdict.PASS,
        result_provenance_sha256=clean.result_provenance_sha256,
        observation_evidence_sha256=(
            clean.observation_evidence_sha256
        ),
        decision_evidence_sha256=clean.decision_evidence_sha256,
    )
    return build_minimal_counterexample_reduction_bundle(
        evaluation_type="asr",
        reduction_key="hetren.asr.brutal-minimal-counterexample",
        reduction_version="1.0.0",
        source_scenario_sha256=primary.scenario_sha256,
        source_counterexample_evidence_sha256=primary.sha256,
        units=(
            CounterexampleReductionUnit(
                key="severe-noise-mutation",
                version="1.0.0",
                content_sha256=unit_commitment,
            ),
        ),
        maximum_observations=1,
        observations=(observation,),
    )


def _neighborhood(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    evaluations: Mapping[tuple[str, str], _CaseEvaluation],
    counterexamples: Mapping[str, CounterexampleEvidenceBundle],
    primary: CounterexampleEvidenceBundle,
    reduction,
):
    source_reference = _case_by_id(bundle)[
        _PRIMARY_COUNTEREXAMPLE_CASE_ID
    ].reference_transcript
    candidates = []
    observations = []
    for index, (
        case_id,
        dimension,
        direction,
        ordinal_distance,
    ) in enumerate(_NEIGHBORHOOD_CASES):
        evaluation = evaluations[("candidate", case_id)]
        case = _case_by_id(bundle)[case_id]
        if case.reference_transcript != source_reference:
            raise ASRBrutalFullChainRunnerError(
                f"{case_id} is not a same-content neighborhood candidate."
            )
        if evaluation.verdict not in {
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        }:
            raise ASRBrutalFullChainRunnerError(
                f"{case_id} has no decisive neighborhood observation."
            )
        specification_sha256 = _canonical_sha256(
            {
                "case_id": case_id,
                "audio_asset_sha256": evaluation.audio_asset_sha256,
                "scenario_sha256": _scenario_sha256(
                    bundle=bundle,
                    evaluation=evaluation,
                ),
                "source_scenario_sha256": primary.scenario_sha256,
                "declared_single_dimension": dimension,
            }
        )
        candidates.append(
            NeighborhoodCandidate(
                key=case_id,
                version="1.0.0",
                dimension_key=dimension,
                generator_key=(
                    "hetren.asr.brutal-preexecuted-neighbor"
                ),
                generator_version="1.0.0",
                direction=direction,
                ordinal_distance=ordinal_distance,
                specification_sha256=specification_sha256,
            )
        )
        counterexample = counterexamples.get(case_id)
        observations.append(
            NeighborhoodObservation(
                sequence=index + 1,
                candidate_index=index,
                scenario_sha256=_scenario_sha256(
                    bundle=bundle,
                    evaluation=evaluation,
                ),
                verdict=evaluation.verdict,
                result_provenance_sha256=(
                    evaluation.result_provenance_sha256
                ),
                observation_evidence_sha256=(
                    evaluation.observation_evidence_sha256
                ),
                decision_evidence_sha256=(
                    evaluation.decision_evidence_sha256
                ),
                counterexample_evidence_sha256=(
                    counterexample.sha256
                    if counterexample is not None
                    else None
                ),
            )
        )

    return build_neighborhood_generation_bundle(
        evaluation_type="asr",
        neighborhood_key="hetren.asr.brutal-local-neighborhood",
        neighborhood_version="1.0.0",
        source_scenario_sha256=primary.scenario_sha256,
        source_counterexample_evidence_sha256=primary.sha256,
        source_minimal_reduction_sha256=reduction.sha256,
        candidates=tuple(candidates),
        maximum_observations=len(candidates),
        observations=tuple(observations),
    )


def _audio_context(path: Path) -> tuple[
    IncidentAudioContext,
    dict[str, object],
]:
    try:
        with wave.open(str(path), "rb") as source:
            if source.getcomptype() != "NONE":
                raise ASRBrutalFullChainRunnerError(
                    "Incident source must be an uncompressed WAV."
                )
            channels = source.getnchannels()
            sample_rate = source.getframerate()
            sample_width = source.getsampwidth()
            frame_count = source.getnframes()
    except (OSError, wave.Error) as error:
        raise ASRBrutalFullChainRunnerError(
            "Incident source WAV metadata could not be verified."
        ) from error

    duration_ms = max(1, round(frame_count * 1000 / sample_rate))
    codec_name = f"pcm_s{sample_width * 8}le"
    context = IncidentAudioContext(
        codec_name=codec_name,
        codec_profile=f"signed-{sample_width * 8}-bit-little-endian",
        container_name="wav",
        sample_rate_hz=sample_rate,
        channel_count=channels,
        bit_rate_bps=sample_rate * channels * sample_width * 8,
        duration_ms=duration_ms,
        variable_bit_rate=False,
        sample_rate_shift_observed=False,
        automatic_gain_control=IncidentProcessingState.UNKNOWN,
        noise_suppression=IncidentProcessingState.UNKNOWN,
        echo_cancellation=IncidentProcessingState.UNKNOWN,
        input_device_class="generated-audio",
    )
    materialized = {
        "codec": {
            "name": context.codec_name,
            "profile": context.codec_profile,
        },
        "container_name": context.container_name,
        "sample_rate_hz": context.sample_rate_hz,
        "channel_count": context.channel_count,
        "bit_rate_bps": context.bit_rate_bps,
        "duration_ms": context.duration_ms,
        "variable_bit_rate": context.variable_bit_rate,
        "sample_rate_shift_observed": (
            context.sample_rate_shift_observed
        ),
        "capture_processing": {
            "automatic_gain_control": (
                context.automatic_gain_control.value
            ),
            "noise_suppression": context.noise_suppression.value,
            "echo_cancellation": context.echo_cancellation.value,
        },
        "input_device_class": context.input_device_class,
    }
    return context, materialized


def _transport_materialized() -> dict[str, object]:
    return {
        "kind": "local_file",
        "packet_loss_percent": None,
        "network_jitter_ms": None,
        "jitter_buffer_ms": None,
        "round_trip_time_ms": None,
        "burst_loss_max_packets": None,
        "concealed_audio_ms": None,
        "codec_switch_count": None,
        "sample_rate_shift_count": None,
    }


class _NeverStoppedControl:
    def raise_if_stopped(self) -> None:
        return None


def _incident_chain(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    evaluation: _CaseEvaluation,
    primary: CounterexampleEvidenceBundle,
    candidate_model_identity: dict[str, object],
    repository_commit: str,
    source_code_sha256: str,
    execution_summary_sha256: str,
    operator_authorization_sha256: str,
    provider_factory: ProviderFactory,
) -> dict[str, object]:
    authorization = _require_sha256(
        "Incident operator authorization",
        operator_authorization_sha256,
    )
    source_audio_path = bundle.audio_paths[evaluation.case_id]
    source_audio = source_audio_path.read_bytes()
    if hashlib.sha256(source_audio).hexdigest() != evaluation.audio_asset_sha256:
        raise ASRBrutalFullChainRunnerError(
            "Incident source bytes changed after campaign execution."
        )

    case = _case_by_id(bundle)[evaluation.case_id]
    provider_version = importlib.metadata.version("faster-whisper")
    configuration_sha256 = _canonical_sha256(
        {
            "suite_evidence_sha256": bundle.suite_evidence.sha256,
            "execution_summary_sha256": execution_summary_sha256,
            "provider": "faster_whisper",
            "model_name": candidate_model_identity["model_name"],
            "device": "cpu",
            "compute_type": "int8_float32",
        }
    )
    runtime_environment_sha256 = _canonical_sha256(
        {
            "python": sys.version,
            "implementation": platform.python_implementation(),
            "faster_whisper": provider_version,
            "platform": platform.platform(),
        }
    )
    host_environment_sha256 = _canonical_sha256(
        {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "node": platform.node(),
        }
    )
    runtime = IncidentRuntimeContext(
        deployment_key="hetren.asr.brutal-validation-runner",
        deployment_version=ASR_BRUTAL_FULL_CHAIN_RUN_VERSION,
        provider_key="faster_whisper",
        provider_version=provider_version,
        model_key=str(candidate_model_identity["model_name"]),
        model_version=str(candidate_model_identity["revision"]),
        model_artifact_sha256=str(
            candidate_model_identity["model_binary_sha256"]
        ),
        source_code_sha256=source_code_sha256,
        configuration_sha256=configuration_sha256,
        runtime_environment_sha256=runtime_environment_sha256,
        host_environment_sha256=host_environment_sha256,
    )
    audio, materialized_audio = _audio_context(source_audio_path)
    transport = IncidentTransportContext(
        kind=IncidentTransportKind.LOCAL_FILE
    )

    expected_behavior = calculate_incident_generated_transcript_sha256(
        case.reference_transcript
    )
    observed_behavior = calculate_incident_generated_transcript_sha256(
        evaluation.generated_transcript
    )
    if expected_behavior == observed_behavior:
        raise ASRBrutalFullChainRunnerError(
            "Incident claim requires distinct expected and observed behavior."
        )

    intake = build_incident_intake_bundle(
        evaluation_type="asr",
        incident_key="hetren.asr.brutal-severe-noise-identifier",
        incident_version="1.0.0",
        source_event_commitment_sha256=primary.sha256,
        claim=IncidentClaim(
            key="asr.critical-identifier-fidelity",
            version="1.0.0",
            reason_code="critical-identifier-not-preserved",
            severity=IncidentSeverity.HIGH,
            affected_stage=IncidentAffectedStage.INFERENCE,
            reporter_evidence_sha256=primary.sha256,
            expected_behavior_commitment_sha256=expected_behavior,
            observed_behavior_commitment_sha256=observed_behavior,
        ),
        runtime=runtime,
        audio=audio,
        transport=transport,
        artifacts=(
            IncidentArtifactReference(
                kind=IncidentArtifactKind.SOURCE_AUDIO,
                sha256=evaluation.audio_asset_sha256,
                byte_length=evaluation.audio_byte_length,
                media_type="audio/wav",
            ),
        ),
    )
    preparation = build_incident_replay_preparation_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        artifact_materials=(
            IncidentArtifactMaterial(
                kind=IncidentArtifactKind.SOURCE_AUDIO,
                reference_sha256=evaluation.audio_asset_sha256,
                content=source_audio,
            ),
        ),
    )
    manifest = build_incident_environment_manifest_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
    )

    settings = LocalRunnerSettings(
        _env_file=None,
        HETREN_RUNNER_CREDENTIAL="local-full-chain-runner",
        HETREN_RUNNER_VERSION=ASR_BRUTAL_FULL_CHAIN_RUN_VERSION,
        HETREN_RUNNER_CAPABILITIES=list(
            INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
        ),
        HETREN_RUNNER_ASR_PROVIDER="faster_whisper",
        HETREN_RUNNER_ASR_MODEL=str(
            candidate_model_identity["model_name"]
        ),
        HETREN_RUNNER_ASR_DEVICE="cpu",
        HETREN_RUNNER_ASR_COMPUTE_TYPE="int8_float32",
        HETREN_RUNNER_INCIDENT_DEPLOYMENT_KEY=runtime.deployment_key,
        HETREN_RUNNER_INCIDENT_DEPLOYMENT_VERSION=(
            runtime.deployment_version
        ),
        HETREN_RUNNER_INCIDENT_PROVIDER_VERSION=runtime.provider_version,
        HETREN_RUNNER_INCIDENT_MODEL_VERSION=runtime.model_version,
        HETREN_RUNNER_INCIDENT_MODEL_ARTIFACT_SHA256=(
            runtime.model_artifact_sha256
        ),
        HETREN_RUNNER_INCIDENT_SOURCE_CODE_SHA256=(
            runtime.source_code_sha256
        ),
        HETREN_RUNNER_INCIDENT_CONFIGURATION_SHA256=(
            runtime.configuration_sha256
        ),
        HETREN_RUNNER_INCIDENT_RUNTIME_ENVIRONMENT_SHA256=(
            runtime.runtime_environment_sha256
        ),
        HETREN_RUNNER_INCIDENT_HOST_ENVIRONMENT_SHA256=(
            runtime.host_environment_sha256
        ),
        HETREN_RUNNER_INCIDENT_MATERIALIZATION_AUTHORIZATION_SHA256=(
            authorization
        ),
    )
    materialized_context = IncidentRunnerMaterializedContext(
        audio=materialized_audio,
        transport=_transport_materialized(),
    )
    compatibility_observation = (
        build_incident_materialization_compatibility_observation(
            settings,
            materialized_context=materialized_context,
        )
    )
    compatibility = build_incident_runner_compatibility_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
        environment_manifest_payload=manifest.payload,
        expected_environment_manifest_sha256=manifest.sha256,
        required_capabilities=(
            INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
        ),
        observation=compatibility_observation,
    )
    materialization_observations = (
        build_incident_materialization_observations(
            compatibility=compatibility,
            compatibility_observation=compatibility_observation,
            materialized_context=materialized_context,
        )
    )
    materialization = build_incident_environment_materialization_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
        environment_manifest_payload=manifest.payload,
        expected_environment_manifest_sha256=manifest.sha256,
        runner_compatibility_payload=compatibility.payload,
        expected_runner_compatibility_sha256=compatibility.sha256,
        required_capabilities=(
            INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
        ),
        compatibility_observation=compatibility_observation,
        authorization=IncidentOperatorAuthorization(
            granted=True,
            authorization_sha256=authorization,
        ),
        materialization_observations=materialization_observations,
    )

    provider = provider_factory(
        "faster_whisper",
        model_name=str(candidate_model_identity["model_name"]),
        device="cpu",
        compute_type="int8_float32",
    )
    control = _NeverStoppedControl()

    def artifact_provider(requirement, replay_control):
        replay_control.raise_if_stopped()
        return IncidentReplayArtifact(
            requirement=requirement,
            data=source_audio,
        )

    def context_provider(replay_control):
        replay_control.raise_if_stopped()
        return materialized_context

    controlled_replay = execute_incident_controlled_replay(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
        environment_manifest_payload=manifest.payload,
        expected_environment_manifest_sha256=manifest.sha256,
        runner_compatibility_payload=compatibility.payload,
        expected_runner_compatibility_sha256=compatibility.sha256,
        environment_materialization_payload=materialization.payload,
        expected_environment_materialization_sha256=(
            materialization.sha256
        ),
        settings=settings,
        artifact_provider=artifact_provider,
        materialized_context_provider=context_provider,
        replay_adapter=ASRProviderIncidentReplayAdapter(provider),
        control=control,
    ).bundle

    comparison = IncidentReproductionComparisonObservation(
        basis=IncidentReproductionComparisonBasis.UNAVAILABLE
    )
    reproduction = build_incident_reproduction_evidence_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
        environment_manifest_payload=manifest.payload,
        expected_environment_manifest_sha256=manifest.sha256,
        runner_compatibility_payload=compatibility.payload,
        expected_runner_compatibility_sha256=compatibility.sha256,
        required_capabilities=(
            INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
        ),
        compatibility_observation=compatibility_observation,
        environment_materialization_payload=materialization.payload,
        expected_environment_materialization_sha256=(
            materialization.sha256
        ),
        controlled_replay_payload=controlled_replay.payload,
        expected_controlled_replay_sha256=controlled_replay.sha256,
        comparison_observation=comparison,
    )
    integration = build_incident_integration_gate_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
        environment_manifest_payload=manifest.payload,
        expected_environment_manifest_sha256=manifest.sha256,
        runner_compatibility_payload=compatibility.payload,
        expected_runner_compatibility_sha256=compatibility.sha256,
        required_capabilities=(
            INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
        ),
        compatibility_observation=compatibility_observation,
        environment_materialization_payload=materialization.payload,
        expected_environment_materialization_sha256=(
            materialization.sha256
        ),
        controlled_replay_payload=controlled_replay.payload,
        expected_controlled_replay_sha256=controlled_replay.sha256,
        reproduction_evidence_payload=reproduction.payload,
        expected_reproduction_evidence_sha256=reproduction.sha256,
        comparison_observation=comparison,
    )

    return {
        "schema_version": 1,
        "type": "brutal_incident_mode_chain",
        "stage": "incident_mode",
        "repository_commit": repository_commit,
        "source_case_id": evaluation.case_id,
        "artifacts": {
            "intake": {"payload": intake.payload, "sha256": intake.sha256},
            "replay_preparation": {
                "payload": preparation.payload,
                "sha256": preparation.sha256,
            },
            "environment_manifest": {
                "payload": manifest.payload,
                "sha256": manifest.sha256,
            },
            "runner_compatibility": {
                "payload": compatibility.payload,
                "sha256": compatibility.sha256,
            },
            "environment_materialization": {
                "payload": materialization.payload,
                "sha256": materialization.sha256,
            },
            "controlled_replay": {
                "payload": controlled_replay.payload,
                "sha256": controlled_replay.sha256,
            },
            "reproduction_evidence": {
                "payload": reproduction.payload,
                "sha256": reproduction.sha256,
            },
            "integration_gate": {
                "payload": integration.payload,
                "sha256": integration.sha256,
            },
        },
        "outcome": {
            "controlled_replay_executed": True,
            "integration_verified": bool(
                integration.payload["integration"]["integration_verified"]
            ),
            "reproduction_verdict": reproduction.payload["comparison"][
                "verdict"
            ],
            "reproduction_claimed": False,
        },
        "evidence_boundary": {
            "raw_audio_embedded": False,
            "raw_transcript_embedded": False,
            "operator_authorization_committed": True,
            "model_failure_verified_by_incident_stage": False,
            "causal_explanation_claimed": False,
            "governance_assurance_completed": False,
            "release_authority_granted": False,
            "qualification_authority": False,
        },
    }


def _persist_incident_children(
    root: Path,
    incident_payload: dict[str, object],
) -> None:
    artifacts = incident_payload["artifacts"]
    if not isinstance(artifacts, dict):
        raise ASRBrutalFullChainRunnerError(
            "Incident artifact inventory is invalid."
        )
    incident_root = root / "incident"
    for index, (name, value) in enumerate(artifacts.items(), start=1):
        if not isinstance(value, dict):
            raise ASRBrutalFullChainRunnerError(
                "Incident child evidence is invalid."
            )
        observed = _write_bundle(
            incident_root / f"{index:02d}.{name}.json",
            value["payload"],
        )
        if observed != value["sha256"]:
            raise ASRBrutalFullChainRunnerError(
                f"Incident child digest disagreement: {name}."
            )


def execute_asr_brutal_full_chain_run_v1(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    output_root: str | Path,
    repository_root: str | Path,
    repository_commit: str,
    operator_authorization_sha256: str,
    provider_factory: ProviderFactory = get_asr_provider,
    model_verifier: ModelVerifier = verify_asr_brutal_frozen_model_v1,
    campaign_executor: CampaignExecutor = (
        execute_asr_brutal_validation_campaign_v1
    ),
    execution_runner: ExecutionRunner = (
        execute_asr_brutal_validation_run_v1
    ),
    repository_verifier: RepositoryVerifier = (
        _verify_repository_identity
    ),
) -> ASRBrutalFullChainRunResult:
    """Execute the real ten-stage evidence workflow and fail closed."""

    repository = Path(repository_root).resolve(strict=True)
    root = _prepare_full_chain_root(
        output_root=output_root,
        repository_root=repository,
    )
    source_code_sha256 = repository_verifier(
        repository,
        repository_commit,
    )
    _require_sha256("Repository source tree", source_code_sha256)
    _require_sha256(
        "Incident operator authorization",
        operator_authorization_sha256,
    )

    completed_stages: list[str] = []
    try:
        plan = build_asr_brutal_validation_plan_v1()
        execution_result = execution_runner(
            bundle=bundle,
            output_root=root / "execution",
            repository_root=repository,
            repository_commit=repository_commit,
            provider_factory=provider_factory,
            model_verifier=model_verifier,
            campaign_executor=campaign_executor,
        )
        if execution_result.status != "completed":
            raise ASRBrutalFullChainRunnerError(
                "Two-model audio execution did not complete."
            )
        (
            execution_summary,
            execution_summary_sha256,
            campaigns,
            campaign_sha256s,
        ) = _execution_documents(
            execution_root=root / "execution",
            bundle=bundle,
            repository_commit=repository_commit,
        )
        _verify_audio_and_child_evidence(
            bundle=bundle,
            campaigns=campaigns,
        )
        _write_bundle(
            root / "adversarial_audio_execution.json",
            {
                "schema_version": 1,
                "type": "adversarial_audio_execution",
                "stage": "adversarial_audio_execution",
                "execution_summary_sha256": execution_summary_sha256,
                "campaign_artifact_sha256s": campaign_sha256s,
                "case_count": execution_summary["case_count"],
                "model_count": len(execution_summary["models"]),
                "planned_result_count": 26,
                "completed_result_count": 26,
                "audio_executed": True,
                "model_execution_performed": True,
                "development_evidence_only": True,
            },
        )
        completed_stages.append("adversarial_audio_execution")

        fidelity_payload, evaluations = _critical_fidelity_evidence(
            campaigns
        )
        _write_bundle(
            root / "critical_fidelity_evaluation.json",
            fidelity_payload,
        )
        completed_stages.append("critical_fidelity_evaluation")

        inventory, counterexamples = _counterexample_inventory(
            bundle=bundle,
            evaluations=evaluations,
        )
        _write_bundle(root / "counterexample_evidence.json", inventory)
        completed_stages.append("counterexample_evidence")
        primary = counterexamples[_PRIMARY_COUNTEREXAMPLE_CASE_ID]

        search = _adaptive_search(
            bundle=bundle,
            evaluations=evaluations,
            counterexamples=counterexamples,
        )
        _persist_core_bundle(
            root / "adaptive_scenario_search.json",
            search,
        )
        completed_stages.append("adaptive_scenario_search")
        boundary = search.observed_boundary
        if boundary is None:
            raise ASRBrutalFullChainRunnerError(
                "Adaptive search did not produce observed boundary evidence."
            )
        _persist_core_bundle(root / "observed_boundary.json", boundary)
        completed_stages.append("observed_boundary")

        reduction = _minimal_reduction(
            bundle=bundle,
            evaluations=evaluations,
            primary=primary,
        )
        _persist_core_bundle(
            root / "minimal_counterexample_reduction.json",
            reduction,
        )
        completed_stages.append("minimal_counterexample_reduction")

        neighborhood = _neighborhood(
            bundle=bundle,
            evaluations=evaluations,
            counterexamples=counterexamples,
            primary=primary,
            reduction=reduction,
        )
        _persist_core_bundle(
            root / "neighborhood_generation.json",
            neighborhood,
        )
        completed_stages.append("neighborhood_generation")

        proposal = build_counterexample_contract_proposal_bundle(
            definition=RegressionContractDefinition(
                key=(
                    "hetren.asr.severe-noise-critical-identifier-regression"
                ),
                version="1.0.0",
                suite_key="hetren.asr.brutal-validation-regression-suite",
                suite_version="1.0.0",
            ),
            source_counterexample_payload=primary.payload,
            source_counterexample_sha256=primary.sha256,
            source_minimal_reduction_payload=reduction.payload,
            source_minimal_reduction_sha256=reduction.sha256,
            source_neighborhood_payload=neighborhood.payload,
            source_neighborhood_sha256=neighborhood.sha256,
        )
        _persist_core_bundle(
            root / "counterexample_contract_proposal.json",
            proposal,
        )
        completed_stages.append("counterexample_contract_proposal")

        candidate_identity = campaigns["candidate"]["model_identity"]
        if not isinstance(candidate_identity, dict):
            raise ASRBrutalFullChainRunnerError(
                "Candidate model identity is invalid."
            )
        incident = _incident_chain(
            bundle=bundle,
            evaluation=evaluations[
                ("candidate", _PRIMARY_COUNTEREXAMPLE_CASE_ID)
            ],
            primary=primary,
            candidate_model_identity=candidate_identity,
            repository_commit=repository_commit,
            source_code_sha256=source_code_sha256,
            execution_summary_sha256=execution_summary_sha256,
            operator_authorization_sha256=(
                operator_authorization_sha256
            ),
            provider_factory=provider_factory,
        )
        _persist_incident_children(root, incident)
        _write_bundle(root / "incident_mode.json", incident)
        completed_stages.append("incident_mode")

        governance = {
            "schema_version": 1,
            "type": "governance_assurance_gate",
            "stage": "governance_assurance",
            "status": "withheld_pending_authorized_human_review",
            "incident_integration_gate_sha256": incident["artifacts"][
                "integration_gate"
            ]["sha256"],
            "review_requirements": {
                "independent_human_roles_required": [
                    "evaluation_reviewer",
                    "risk_reviewer",
                    "governance_approver",
                ],
                "qualification_records_required": True,
                "authorization_records_required": True,
                "independence_attestations_required": True,
                "signed_decision_records_required": True,
            },
            "execution_boundary": {
                "governance_gate_evaluated": True,
                "governance_review_executed": False,
                "governance_assurance_completed": False,
            },
            "authority_boundary": {
                "ai_generated_approval_allowed": False,
                "reviewers_invented": False,
                "contract_promoted": False,
                "blocking_release_gate_enabled": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_authority_granted": False,
                "qualification_authority": False,
            },
        }
        governance_sha256 = _write_bundle(
            root / "governance_assurance.json",
            governance,
        )
        completed_stages.append("governance_assurance")

        if tuple(completed_stages) != ASR_BRUTAL_VALIDATION_WORKFLOW_V1:
            raise ASRBrutalFullChainRunnerError(
                "Completed stage order differs from the frozen plan."
            )

        summary_payload: dict[str, object] = {
            "schema_version": ASR_BRUTAL_FULL_CHAIN_RUN_SCHEMA_VERSION,
            "artifact": {
                "key": ASR_BRUTAL_FULL_CHAIN_RUN_KEY,
                "version": ASR_BRUTAL_FULL_CHAIN_RUN_VERSION,
                "type": "brutal_full_chain_execution_summary",
            },
            "status": "evidence_chain_completed_governance_withheld",
            "repository_commit": repository_commit,
            "source_code_sha256": source_code_sha256,
            "plan_sha256": plan.sha256,
            "required_stages": list(ASR_BRUTAL_VALIDATION_WORKFLOW_V1),
            "executed_stages": completed_stages,
            "stage_artifacts": {
                "execution_summary_sha256": execution_summary_sha256,
                "critical_fidelity_evaluation_sha256": _read_bundle_document(
                    root / "critical_fidelity_evaluation.json"
                )[1],
                "counterexample_evidence_sha256": _read_bundle_document(
                    root / "counterexample_evidence.json"
                )[1],
                "adaptive_scenario_search_sha256": search.sha256,
                "observed_boundary_sha256": boundary.sha256,
                "minimal_counterexample_reduction_sha256": (
                    reduction.sha256
                ),
                "neighborhood_generation_sha256": neighborhood.sha256,
                "counterexample_contract_proposal_sha256": proposal.sha256,
                "incident_mode_sha256": _read_bundle_document(
                    root / "incident_mode.json"
                )[1],
                "governance_assurance_sha256": governance_sha256,
            },
            "execution_boundary": {
                "brutal_validation_execution_started": True,
                "audio_executed": True,
                "model_execution_performed": True,
                "cross_stage_chain_executed": True,
                "incident_chain_executed": True,
                "governance_gate_evaluated": True,
                "governance_review_executed": False,
                "brutal_validation_completed": False,
            },
            "authority_boundary": {
                "development_evidence_only": True,
                "production_certification": False,
                "contract_proposed": True,
                "contract_promoted": False,
                "blocking_release_gate_enabled": False,
                "release_authority_granted": False,
                "qualification_authority": False,
                "model_winner_declared": False,
                "statistical_significance_claimed": False,
            },
        }
        summary_sha256 = _write_bundle(
            root / "summary.json",
            summary_payload,
        )
        return ASRBrutalFullChainRunResult(
            output_root=root,
            payload=summary_payload,
            sha256=summary_sha256,
        )
    except Exception as error:
        if root.exists() and not (root / "full_chain_fatal.json").exists():
            try:
                _write_bundle(
                    root / "full_chain_fatal.json",
                    {
                        "schema_version": 1,
                        "type": "brutal_full_chain_fatal_outcome",
                        "status": "failed_preserved",
                        "repository_commit": repository_commit,
                        "completed_stages": completed_stages,
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                        "preserve_output_and_do_not_rerun": True,
                        "certification_issued": False,
                        "production_qualified": False,
                    },
                )
            except Exception:
                pass
        raise


__all__ = [
    "ASR_BRUTAL_FULL_CHAIN_RUN_KEY",
    "ASR_BRUTAL_FULL_CHAIN_RUN_SCHEMA_VERSION",
    "ASR_BRUTAL_FULL_CHAIN_RUN_VERSION",
    "ASRBrutalFullChainRunResult",
    "ASRBrutalFullChainRunnerError",
    "execute_asr_brutal_full_chain_run_v1",
]
