"""Execute and persist ASR Brutal Validation v1 development evidence."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.adversarial_asr_brutal_campaign import (
    ASR_BRUTAL_VALIDATION_MEDIA_V1,
    ASR_BRUTAL_VALIDATION_MODELS_V1,
    ASRBrutalValidationSuiteBundle,
    execute_asr_brutal_validation_campaign_v1,
)
from app.adversarial_asr_campaign_service import (
    ASRAdversarialCampaignServiceResult,
)
from app.speech import ASRProvider, get_asr_provider
from hvee.packs.asr.adversarial_campaign_evidence import (
    verify_asr_adversarial_campaign_evidence_v1,
)
from hvee.packs.asr.adversarial_execution_evidence import (
    calculate_asr_adversarial_transcript_sha256,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_METRIC,
    build_normalized_error_observations,
    evaluate_normalized_transcript_pair,
)


ASR_BRUTAL_EXECUTION_RUN_SCHEMA_VERSION = 1
ASR_BRUTAL_EXECUTION_RUN_KEY = (
    "hetren.asr.brutal-validation-execution-run"
)
ASR_BRUTAL_EXECUTION_RUN_VERSION = "1.1.0"

_GIT_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


class ASRBrutalExecutionRunnerError(ValueError):
    """Raised when a Brutal-v1 run cannot produce trusted evidence."""


@dataclass(frozen=True, slots=True)
class ASRBrutalFrozenModel:
    role: str
    model_name: str
    repository: str
    revision: str
    model_binary_sha256: str
    model_binary_bytes: int


ASR_BRUTAL_FROZEN_MODELS_V1 = (
    ASRBrutalFrozenModel(
        role="baseline",
        model_name="small.en",
        repository="Systran/faster-whisper-small.en",
        revision="d1d751a5f8271d482d14ca55d9e2deeebbae577f",
        model_binary_sha256=(
            "62b2a45b05ee59acb4a5341b33ee35e0"
            "41395d378d418a18acfe4c9e768ee37a"
        ),
        model_binary_bytes=483_545_366,
    ),
    ASRBrutalFrozenModel(
        role="candidate",
        model_name="large-v3-turbo",
        repository=(
            "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
        ),
        revision="0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
        model_binary_sha256=(
            "e76620f83d5f5b69efd3d87e3dc180c1"
            "bd21df9fbebacfd4335e5e1efcc018da"
        ),
        model_binary_bytes=1_617_884_929,
    ),
)


@dataclass(frozen=True, slots=True)
class ASRBrutalExecutionRunResult:
    output_root: Path
    payload: dict[str, object]
    sha256: str

    @property
    def status(self) -> str:
        return str(self.payload["status"])


ProviderFactory = Callable[..., ASRProvider]
ModelVerifier = Callable[
    [ASRBrutalFrozenModel],
    dict[str, object],
]
CampaignExecutor = Callable[
    ...,
    ASRAdversarialCampaignServiceResult,
]


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {
            field.name: _jsonable(
                getattr(value, field.name)
            )
            for field in dataclasses.fields(value)
        }

    if isinstance(value, Enum):
        return _jsonable(value.value)

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]

    if value is None or isinstance(
        value,
        (bool, int, float, str),
    ):
        return value

    raise ASRBrutalExecutionRunnerError(
        "Brutal execution evidence contains an "
        f"unsupported value: {type(value).__name__}."
    )


def _write_bundle(
    path: Path,
    payload: dict[str, object],
) -> str:
    if path.exists():
        raise ASRBrutalExecutionRunnerError(
            f"Evidence output already exists: {path.name}."
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    digest = hashlib.sha256(
        _canonical_json_bytes(payload)
    ).hexdigest()
    document = {
        "payload": payload,
        "sha256": digest,
    }
    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(
                document,
                stream,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()

    return digest


def _require_repository_commit(value: str) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or _GIT_COMMIT_PATTERN.fullmatch(value) is None
    ):
        raise ASRBrutalExecutionRunnerError(
            "Repository commit must be a full lowercase Git SHA."
        )

    return value


def _prepare_output_root(
    *,
    output_root: str | Path,
    repository_root: str | Path,
) -> Path:
    repository = Path(repository_root).resolve(strict=True)
    requested = Path(output_root)

    if not requested.is_absolute():
        raise ASRBrutalExecutionRunnerError(
            "Brutal evidence output root must be absolute."
        )

    resolved = requested.resolve(strict=False)

    if (
        resolved == repository
        or resolved.is_relative_to(repository)
    ):
        raise ASRBrutalExecutionRunnerError(
            "Brutal evidence must be written outside the repository."
        )

    resolved.mkdir(
        parents=True,
        exist_ok=False,
    )
    return resolved


def verify_asr_brutal_frozen_model_v1(
    model: ASRBrutalFrozenModel,
) -> dict[str, object]:
    """Resolve and hash one frozen faster-whisper model offline."""

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

    try:
        from faster_whisper.utils import download_model
    except ImportError as error:
        raise ASRBrutalExecutionRunnerError(
            "faster-whisper is required for Brutal-v1 execution."
        ) from error

    snapshot = Path(
        download_model(
            model.model_name,
            local_files_only=True,
        )
    ).resolve(strict=True)
    model_binary = (
        snapshot / "model.bin"
    ).resolve(strict=True)

    expected_cache_name = (
        "models--" + model.repository.replace("/", "--")
    )
    observed_cache_name = snapshot.parents[1].name
    observed_revision = snapshot.name
    observed_bytes = model_binary.stat().st_size
    observed_sha256 = _sha256_file(model_binary)

    if observed_cache_name != expected_cache_name:
        raise ASRBrutalExecutionRunnerError(
            f"Frozen repository mismatch for {model.model_name}."
        )

    if observed_revision != model.revision:
        raise ASRBrutalExecutionRunnerError(
            f"Frozen revision mismatch for {model.model_name}."
        )

    if observed_bytes != model.model_binary_bytes:
        raise ASRBrutalExecutionRunnerError(
            f"Frozen model length mismatch for {model.model_name}."
        )

    if observed_sha256 != model.model_binary_sha256:
        raise ASRBrutalExecutionRunnerError(
            f"Frozen model hash mismatch for {model.model_name}."
        )

    return {
        "role": model.role,
        "model_name": model.model_name,
        "repository": model.repository,
        "revision": observed_revision,
        "model_binary_bytes": observed_bytes,
        "model_binary_sha256": observed_sha256,
        "resolved_offline": True,
    }


def _normalized_error_attachment(
    *,
    reference_transcript: str,
    generated_transcript: str,
) -> dict[str, object]:
    evaluation = evaluate_normalized_transcript_pair(
        reference_text=reference_transcript,
        generated_text=generated_transcript,
    )
    observations = build_normalized_error_observations(
        evaluation
    )

    by_key = {
        observation.metric_key: observation
        for observation in observations
    }

    try:
        wer_observation = by_key[
            NORMALIZED_WER_METRIC.key
        ]
        cer_observation = by_key[
            NORMALIZED_CER_METRIC.key
        ]
    except KeyError as error:
        raise ASRBrutalExecutionRunnerError(
            "Canonical normalized WER/CER observations are incomplete."
        ) from error

    return {
        "attachment_version": "1.0.0",
        "normalization": {
            "key": evaluation.normalization_key,
            "version": evaluation.normalization_version,
        },
        "reference_transcript_sha256": (
            calculate_asr_adversarial_transcript_sha256(
                reference_transcript
            )
        ),
        "generated_transcript_sha256": (
            calculate_asr_adversarial_transcript_sha256(
                generated_transcript
            )
        ),
        "wer": _jsonable(wer_observation),
        "cer": _jsonable(cer_observation),
    }


def _completed_result_payload(
    result: object,
    *,
    bundle: ASRBrutalValidationSuiteBundle,
) -> dict[str, object]:
    case_id = str(
        getattr(result, "case_id")
    )

    matching_cases = tuple(
        case
        for case in bundle.suite.cases
        if case.case_id == case_id
    )

    if len(matching_cases) != 1:
        raise ASRBrutalExecutionRunnerError(
            "Completed brutal result does not map to exactly one suite case."
        )

    reference_transcript = str(
        getattr(
            matching_cases[0],
            "reference_transcript",
        )
    )

    generated_transcript = str(
        getattr(
            result,
            "generated_transcript",
        )
    )

    normalized_error_evidence = (
        _normalized_error_attachment(
            reference_transcript=reference_transcript,
            generated_transcript=generated_transcript,
        )
    )

    return {
        "case_id": case_id,
        "audio_asset_sha256": str(
            getattr(result, "audio_asset_sha256")
        ),
        "audio_byte_length": int(
            getattr(result, "audio_byte_length")
        ),
        "generated_transcript": generated_transcript,
        "normalized_error_evidence": (
            normalized_error_evidence
        ),
        "environment": _jsonable(
            getattr(result, "environment")
        ),
        "semantic_observations": _jsonable(
            getattr(result, "semantic_observations")
        ),
        "execution_definition": _jsonable(
            getattr(result, "execution_definition")
        ),
        "execution_evidence": {
            "payload": _jsonable(
                getattr(result, "execution_evidence").payload
            ),
            "sha256": str(
                getattr(result, "execution_evidence").sha256
            ),
        },
    }


def _campaign_payload(
    *,
    role: str,
    repository_commit: str,
    model_identity: dict[str, object],
    result: ASRAdversarialCampaignServiceResult,
    bundle: ASRBrutalValidationSuiteBundle,
) -> dict[str, object]:
    verified_evidence = (
        verify_asr_adversarial_campaign_evidence_v1(
            payload=result.evidence.payload,
            expected_sha256=result.evidence.sha256,
            definition=result.definition,
            suite=bundle.suite,
            suite_evidence=bundle.suite_evidence,
        )
    )

    return {
        "schema_version": ASR_BRUTAL_EXECUTION_RUN_SCHEMA_VERSION,
        "artifact": {
            "key": ASR_BRUTAL_EXECUTION_RUN_KEY,
            "version": ASR_BRUTAL_EXECUTION_RUN_VERSION,
            "type": "single_model_brutal_campaign_execution",
        },
        "role": role,
        "repository_commit": repository_commit,
        "model_identity": model_identity,
        "campaign_definition": _jsonable(result.definition),
        "campaign_evidence": {
            "payload": verified_evidence.payload,
            "sha256": verified_evidence.sha256,
        },
        "completed_results": [
            _completed_result_payload(
                item,
                bundle=bundle,
            )
            for item in result.completed_results
        ],
        "evidence_boundary": {
            "raw_audio_embedded": False,
            "absolute_audio_paths_embedded": False,
            "raw_generated_transcripts_preserved": True,
            "normalized_error_observations_attached": True,
            "normalized_error_observations_use_existing_evaluator": True,
            "normalized_error_evaluator_methodology_modified": False,
            "partial_outcomes_preserved": True,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "statistical_significance_claimed": False,
            "model_winner_declared": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }


def _model_summary(
    *,
    model: ASRBrutalFrozenModel,
    model_identity: dict[str, object],
    campaign_payload: dict[str, object],
    artifact_sha256: str,
) -> dict[str, object]:
    campaign_evidence = campaign_payload["campaign_evidence"]
    if not isinstance(campaign_evidence, Mapping):
        raise ASRBrutalExecutionRunnerError(
            "Campaign evidence summary is invalid."
        )

    evidence_payload = campaign_evidence["payload"]
    if not isinstance(evidence_payload, Mapping):
        raise ASRBrutalExecutionRunnerError(
            "Campaign evidence payload is invalid."
        )

    campaign = evidence_payload["campaign"]
    if not isinstance(campaign, Mapping):
        raise ASRBrutalExecutionRunnerError(
            "Campaign evidence campaign is invalid."
        )

    status_counts = campaign["status_counts"]
    completed_results = campaign_payload["completed_results"]
    if not isinstance(completed_results, list):
        raise ASRBrutalExecutionRunnerError(
            "Completed result inventory is invalid."
        )

    return {
        "role": model.role,
        "model_identity": model_identity,
        "artifact_file": f"{model.role}.campaign.json",
        "artifact_sha256": artifact_sha256,
        "campaign_evidence_sha256": campaign_evidence["sha256"],
        "status_counts": status_counts,
        "completed_case_count": len(completed_results),
    }


def execute_asr_brutal_validation_run_v1(
    *,
    bundle: ASRBrutalValidationSuiteBundle,
    output_root: str | Path,
    repository_root: str | Path,
    repository_commit: str,
    provider_factory: ProviderFactory = get_asr_provider,
    model_verifier: ModelVerifier = (
        verify_asr_brutal_frozen_model_v1
    ),
    campaign_executor: CampaignExecutor = (
        execute_asr_brutal_validation_campaign_v1
    ),
) -> ASRBrutalExecutionRunResult:
    """Execute both frozen models and atomically persist their evidence."""

    commit = _require_repository_commit(
        repository_commit
    )
    planned_models = tuple(
        model.model_name
        for model in ASR_BRUTAL_FROZEN_MODELS_V1
    )

    if planned_models != ASR_BRUTAL_VALIDATION_MODELS_V1:
        raise ASRBrutalExecutionRunnerError(
            "Runner models differ from the frozen Brutal-v1 plan."
        )

    case_ids = tuple(
        case.case_id
        for case in bundle.suite.cases
    )
    expected_case_ids = tuple(
        sorted(
            identity.case_id
            for identity in ASR_BRUTAL_VALIDATION_MEDIA_V1
        )
    )
    if case_ids != expected_case_ids:
        raise ASRBrutalExecutionRunnerError(
            "Runner requires the exact ordered 13-case Brutal-v1 suite."
        )

    model_identities = {
        model.role: model_verifier(model)
        for model in ASR_BRUTAL_FROZEN_MODELS_V1
    }
    evidence_root = _prepare_output_root(
        output_root=output_root,
        repository_root=repository_root,
    )

    preflight_payload: dict[str, object] = {
        "schema_version": ASR_BRUTAL_EXECUTION_RUN_SCHEMA_VERSION,
        "artifact": {
            "key": ASR_BRUTAL_EXECUTION_RUN_KEY,
            "version": ASR_BRUTAL_EXECUTION_RUN_VERSION,
            "type": "brutal_execution_preflight",
        },
        "repository_commit": commit,
        "suite_evidence_sha256": bundle.suite_evidence.sha256,
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "models": [
            model_identities[model.role]
            for model in ASR_BRUTAL_FROZEN_MODELS_V1
        ],
        "runtime": {
            "provider": "faster_whisper",
            "device": "cpu",
            "compute_type": "int8_float32",
            "huggingface_hub_offline": True,
            "transformers_offline": True,
        },
        "execution_boundary": {
            "asr_execution_started": False,
            "transcription_performed": False,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "production_qualified": False,
        },
    }
    _write_bundle(
        evidence_root / "preflight.json",
        preflight_payload,
    )

    summaries: list[dict[str, object]] = []

    try:
        for model in ASR_BRUTAL_FROZEN_MODELS_V1:
            provider = provider_factory(
                "faster_whisper",
                model_name=model.model_name,
                device="cpu",
                compute_type="int8_float32",
            )
            result = campaign_executor(
                campaign_id=(
                    "brutal.validation.v1."
                    f"{model.role}"
                ),
                requested_model_name=model.model_name,
                provider=provider,
                bundle=bundle,
            )
            campaign_payload = _campaign_payload(
                role=model.role,
                repository_commit=commit,
                model_identity=(
                    model_identities[model.role]
                ),
                result=result,
                bundle=bundle,
            )
            artifact_sha256 = _write_bundle(
                evidence_root
                / f"{model.role}.campaign.json",
                campaign_payload,
            )
            summaries.append(
                _model_summary(
                    model=model,
                    model_identity=(
                        model_identities[model.role]
                    ),
                    campaign_payload=campaign_payload,
                    artifact_sha256=artifact_sha256,
                )
            )
    except Exception as error:
        fatal_payload: dict[str, object] = {
            "schema_version": ASR_BRUTAL_EXECUTION_RUN_SCHEMA_VERSION,
            "artifact": {
                "key": ASR_BRUTAL_EXECUTION_RUN_KEY,
                "version": ASR_BRUTAL_EXECUTION_RUN_VERSION,
                "type": "brutal_execution_fatal_outcome",
            },
            "repository_commit": commit,
            "completed_model_artifacts": summaries,
            "error": {
                "type": type(error).__name__,
                "detail": str(error),
            },
            "development_evidence_only": True,
        }
        _write_bundle(
            evidence_root / "fatal.json",
            fatal_payload,
        )
        raise

    expected_case_count = len(case_ids)
    complete = all(
        summary["completed_case_count"]
        == expected_case_count
        for summary in summaries
    )
    status = "completed" if complete else "partial"
    summary_payload: dict[str, object] = {
        "schema_version": ASR_BRUTAL_EXECUTION_RUN_SCHEMA_VERSION,
        "artifact": {
            "key": ASR_BRUTAL_EXECUTION_RUN_KEY,
            "version": ASR_BRUTAL_EXECUTION_RUN_VERSION,
            "type": "two_model_brutal_execution_summary",
        },
        "status": status,
        "repository_commit": commit,
        "suite_evidence_sha256": bundle.suite_evidence.sha256,
        "case_count": expected_case_count,
        "models": summaries,
        "evidence_boundary": {
            "both_model_outcomes_preserved": True,
            "partial_outcomes_preserved": True,
            "raw_audio_embedded": False,
            "absolute_audio_paths_embedded": False,
            "raw_generated_transcripts_preserved_in_child_artifacts": True,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "statistical_significance_claimed": False,
            "model_winner_declared": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }
    summary_sha256 = _write_bundle(
        evidence_root / "summary.json",
        summary_payload,
    )

    return ASRBrutalExecutionRunResult(
        output_root=evidence_root,
        payload=summary_payload,
        sha256=summary_sha256,
    )
