import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.hvee_observation_evidence import (
    HveeObservationEvidenceError,
    build_test_case_observation_evidence_bundle,
)
from hvee.core.observation_evidence import (
    verify_observation_evidence_bundle,
)
from hvee.packs.asr.normalization import (
    BASIC_TEXT_NORMALIZATION,
    normalize_text_basic,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
    NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
)


EVALUATION_MANIFEST_SCHEMA_VERSION = 1
ASR_EVALUATION_TYPE = "asr"
HETREN_EVALUATOR_ENGINE = "hetren"
ASR_EVALUATOR_CONTRACT_VERSION = "asr-v1"


def canonicalize_json(
    payload: dict[str, Any],
) -> str:
    """
    Serialize structured provenance deterministically.

    Sorting keys and removing insignificant whitespace ensures that the
    same logical manifest always produces the same SHA-256 digest.
    """
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Evaluation provenance must contain valid "
            "JSON-serializable values."
        ) from exc


def calculate_manifest_sha256(
    payload: dict[str, Any],
) -> str:
    canonical_payload = canonicalize_json(payload)

    return hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()


def build_evaluation_run_manifest_payload(
    *,
    run_id: int,
    project_id: int,
    run_name: str,
    model_name: str,
    evaluation_type: str = ASR_EVALUATION_TYPE,
) -> dict[str, Any]:
    """
    Build the creation-time facts known when an ASR run is created.

    Test cases, artifacts, runner identity, provider metadata, and
    generated outputs are intentionally excluded because they are not
    necessarily known at run-creation time.
    """
    if evaluation_type != ASR_EVALUATION_TYPE:
        raise ValueError(
            "Unsupported evaluation type."
        )

    return {
        "schema_version": (
            EVALUATION_MANIFEST_SCHEMA_VERSION
        ),
        "evaluation_type": evaluation_type,
        "run": {
            "id": run_id,
            "project_id": project_id,
            "name": run_name,
        },
        "model": {
            "name": model_name,
        },
        "evaluator": {
            "engine": HETREN_EVALUATOR_ENGINE,
            "contract_version": (
                ASR_EVALUATOR_CONTRACT_VERSION
            ),
        },
    }


def stage_evaluation_run_manifest(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
) -> models.EvaluationRunManifest:
    """
    Stage one sealed manifest for a newly created evaluation run.

    The caller owns the transaction so run creation and manifest
    creation can commit atomically.
    """
    if evaluation_run.id is None:
        raise ValueError(
            "Evaluation run must be flushed before "
            "creating its manifest."
        )

    payload = build_evaluation_run_manifest_payload(
        run_id=evaluation_run.id,
        project_id=evaluation_run.project_id,
        run_name=evaluation_run.run_name,
        model_name=evaluation_run.model_name,
        evaluation_type=evaluation_run.evaluation_type,
    )

    manifest = models.EvaluationRunManifest(
        run_id=evaluation_run.id,
        schema_version=(
            EVALUATION_MANIFEST_SCHEMA_VERSION
        ),
        evaluation_type=evaluation_run.evaluation_type,
        manifest_payload=payload,
        manifest_sha256=(
            calculate_manifest_sha256(payload)
        ),
    )

    db.add(manifest)

    return manifest



def stage_evaluation_run_with_manifest(
    db: Session,
    *,
    project_id: int,
    run_name: str,
    model_name: str = "not_configured",
    evaluation_type: str = ASR_EVALUATION_TYPE,
    status: str = "created",
) -> models.EvaluationRun:
    """
    Stage a new evaluation run and its sealed manifest together.

    The caller owns the transaction. Flushing assigns the run ID
    before the manifest is built, so both records can be committed
    atomically.
    """
    if evaluation_type != ASR_EVALUATION_TYPE:
        raise ValueError(
            "Unsupported evaluation type."
        )

    evaluation_run = models.EvaluationRun(
        project_id=project_id,
        run_name=run_name,
        evaluation_type=evaluation_type,
        model_name=model_name,
        status=status,
    )

    db.add(evaluation_run)
    db.flush()

    stage_evaluation_run_manifest(
        db,
        evaluation_run=evaluation_run,
    )

    return evaluation_run


def verify_evaluation_run_manifest(
    manifest: models.EvaluationRunManifest,
) -> bool:
    """
    Verify that the stored manifest payload still matches its digest
    and its indexed schema/type fields.
    """
    payload = manifest.manifest_payload

    if not isinstance(payload, dict):
        return False

    if (
        payload.get("schema_version")
        != manifest.schema_version
    ):
        return False

    if (
        payload.get("evaluation_type")
        != manifest.evaluation_type
    ):
        return False

    return (
        calculate_manifest_sha256(payload)
        == manifest.manifest_sha256
    )


EVALUATION_RESULT_PROVENANCE_SCHEMA_VERSION = 1

EVALUATION_RESULT_PROVENANCE_INPUT_ARTIFACT_SCHEMA_VERSION = 2

EVALUATION_RESULT_PROVENANCE_HVEE_ASR_EVIDENCE_SCHEMA_VERSION = 3

EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION = 4

SUPPORTED_EVALUATION_RESULT_PROVENANCE_SCHEMA_VERSIONS = (
    frozenset(
        {
            EVALUATION_RESULT_PROVENANCE_SCHEMA_VERSION,
            EVALUATION_RESULT_PROVENANCE_INPUT_ARTIFACT_SCHEMA_VERSION,
            EVALUATION_RESULT_PROVENANCE_HVEE_ASR_EVIDENCE_SCHEMA_VERSION,
            EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION,
        }
    )
)

SUPPORTED_RESULT_EXECUTION_MODES = frozenset(
    {
        "uploaded_transcript",
        "server_asr",
        "runner_asr",
        "seed_fixture",
    }
)


def calculate_text_sha256(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Evidence text must be a string."
        )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _is_sha256_hex(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(
            character in "0123456789abcdef"
            for character in value.lower()
        )
    )


def _build_hvee_asr_observation_contracts(
) -> list[dict[str, str]]:
    """
    Describe the normalized ASR observation semantics expected from
    the current HVEE ASR evidence profile.

    These identities bind provenance to immutable metric/evaluator
    versions without relying on database-assigned registry IDs.
    """

    return [
        {
            "metric_key": NORMALIZED_WER_METRIC.key,
            "metric_version": NORMALIZED_WER_METRIC.version,
            "evaluator_key": NORMALIZED_WER_EVALUATOR.key,
            "evaluator_version": NORMALIZED_WER_EVALUATOR.version,
        },
        {
            "metric_key": NORMALIZED_CER_METRIC.key,
            "metric_version": NORMALIZED_CER_METRIC.version,
            "evaluator_key": NORMALIZED_CER_EVALUATOR.key,
            "evaluator_version": NORMALIZED_CER_EVALUATOR.version,
        },
        {
            "metric_key": NORMALIZED_SUBSTITUTIONS_METRIC.key,
            "metric_version": (
                NORMALIZED_SUBSTITUTIONS_METRIC.version
            ),
            "evaluator_key": (
                NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key
            ),
            "evaluator_version": (
                NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version
            ),
        },
        {
            "metric_key": NORMALIZED_INSERTIONS_METRIC.key,
            "metric_version": (
                NORMALIZED_INSERTIONS_METRIC.version
            ),
            "evaluator_key": (
                NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key
            ),
            "evaluator_version": (
                NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version
            ),
        },
        {
            "metric_key": NORMALIZED_DELETIONS_METRIC.key,
            "metric_version": (
                NORMALIZED_DELETIONS_METRIC.version
            ),
            "evaluator_key": (
                NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key
            ),
            "evaluator_version": (
                NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version
            ),
        },
    ]


def build_hvee_asr_normalized_evidence(
    *,
    reference_text: str,
    generated_text: str,
) -> dict[str, object]:
    """
    Build privacy-conscious reproducibility evidence for normalized ASR.

    Plain normalized transcripts are deliberately not persisted here.
    Their SHA-256 digests and exact UTF-8 byte lengths bind the derived
    representations to the versioned normalization profile.
    """

    normalized_reference = normalize_text_basic(
        reference_text
    )
    normalized_generated = normalize_text_basic(
        generated_text
    )

    return {
        "normalization": {
            "key": BASIC_TEXT_NORMALIZATION.key,
            "version": BASIC_TEXT_NORMALIZATION.version,
        },
        "derived_text": {
            "reference": {
                "source_sha256": calculate_text_sha256(
                    reference_text
                ),
                "normalized_sha256": calculate_text_sha256(
                    normalized_reference
                ),
                "normalized_utf8_bytes": len(
                    normalized_reference.encode("utf-8")
                ),
            },
            "generated": {
                "source_sha256": calculate_text_sha256(
                    generated_text
                ),
                "normalized_sha256": calculate_text_sha256(
                    normalized_generated
                ),
                "normalized_utf8_bytes": len(
                    normalized_generated.encode("utf-8")
                ),
            },
        },
        "observation_contracts": (
            _build_hvee_asr_observation_contracts()
        ),
    }


def _build_run_manifest_evidence(
    evaluation_run: models.EvaluationRun,
) -> dict[str, object]:
    manifest = evaluation_run.manifest

    if manifest is None:
        return {
            "status": "legacy_unsealed",
            "schema_version": None,
            "sha256": None,
        }

    if (
        manifest.run_id != evaluation_run.id
        or manifest.evaluation_type
        != evaluation_run.evaluation_type
        or not verify_evaluation_run_manifest(
            manifest
        )
    ):
        raise ValueError(
            "Evaluation run manifest is invalid."
        )

    return {
        "status": "sealed",
        "schema_version": (
            manifest.schema_version
        ),
        "sha256": manifest.manifest_sha256,
    }


def _build_input_artifact_evidence(
    *,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    input_artifact_seal: (
        models.EvaluationInputArtifactSeal
    ),
) -> dict[str, object]:
    from app.evaluation_artifacts import (
        ASR_INPUT_AUDIO_ROLE,
        AUDIO_ARTIFACT_TYPE,
        verify_evaluation_input_artifact_seal,
    )

    if input_artifact_seal.id is None:
        raise ValueError(
            "Evaluation input artifact seal must "
            "be persisted before result provenance."
        )

    if (
        input_artifact_seal.run_id
        != evaluation_run.id
        or input_artifact_seal.test_case_id
        != test_case.id
    ):
        raise ValueError(
            "Evaluation input artifact seal "
            "resources do not match."
        )

    if (
        input_artifact_seal.evaluation_type
        != ASR_EVALUATION_TYPE
        or input_artifact_seal.artifact_role
        != ASR_INPUT_AUDIO_ROLE
        or input_artifact_seal.artifact_type
        != AUDIO_ARTIFACT_TYPE
    ):
        raise ValueError(
            "Evaluation input artifact seal "
            "contract is invalid."
        )

    run_manifest = (
        _build_run_manifest_evidence(
            evaluation_run
        )
    )

    if run_manifest["status"] != "sealed":
        raise ValueError(
            "Sealed input artifact requires "
            "a sealed evaluation run manifest."
        )

    run_manifest_sha256 = (
        run_manifest["sha256"]
    )

    if not isinstance(
        run_manifest_sha256,
        str,
    ):
        raise ValueError(
            "Evaluation run manifest digest "
            "is unavailable."
        )

    if not verify_evaluation_input_artifact_seal(
        input_artifact_seal,
        expected_run_manifest_sha256=(
            run_manifest_sha256
        ),
    ):
        raise ValueError(
            "Evaluation input artifact seal "
            "is invalid."
        )

    return {
        "status": "sealed",
        "seal_id": input_artifact_seal.id,
        "seal_schema_version": (
            input_artifact_seal.schema_version
        ),
        "seal_sha256": (
            input_artifact_seal.seal_sha256
        ),
        "artifact_role": (
            input_artifact_seal.artifact_role
        ),
        "artifact_type": (
            input_artifact_seal.artifact_type
        ),
        "content_sha256": (
            input_artifact_seal.content_sha256
        ),
        "byte_length": (
            input_artifact_seal.byte_length
        ),
        "media_type": (
            input_artifact_seal.media_type
        ),
        "run_manifest_sha256": (
            run_manifest_sha256
        ),
    }


def _observation_evidence_bundle_matches_result(
    *,
    bundle: object,
    evaluation_type: str,
    evaluation_run_id: int,
    test_case_id: int,
) -> bool:
    """
    Verify that one canonical observation bundle belongs to the
    evaluation result that will carry it.

    Result provenance binds only immutable test-case observations.
    Run-level aggregates are intentionally outside this contract.
    """

    if not verify_observation_evidence_bundle(
        bundle
    ):
        return False

    if not isinstance(bundle, dict):
        return False

    count = bundle.get("count")
    observations = bundle.get(
        "observations"
    )

    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or count < 1
        or not isinstance(
            observations,
            list,
        )
    ):
        return False

    expected_target = {
        "evaluation_run_id": (
            evaluation_run_id
        ),
        "test_case_id": test_case_id,
    }

    for observation in observations:
        if not isinstance(
            observation,
            dict,
        ):
            return False

        if (
            observation.get(
                "evaluation_type"
            )
            != evaluation_type
            or observation.get("scope")
            != "test_case"
            or observation.get("target")
            != expected_target
        ):
            return False

    return True


def build_evaluation_result_provenance_payload(
    *,
    result: models.EvaluationResult,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    execution_mode: str,
    server_observed: dict[str, object] | None = None,
    external_reported: dict[str, object] | None = None,
    input_artifact_seal: (
        models.EvaluationInputArtifactSeal | None
    ) = None,
    observation_evidence_bundle: (
        dict[str, object] | None
    ) = None,
) -> dict[str, object]:
    normalized_mode = (
        execution_mode.strip()
        if isinstance(execution_mode, str)
        else ""
    )

    if (
        normalized_mode
        not in SUPPORTED_RESULT_EXECUTION_MODES
    ):
        raise ValueError(
            "Unsupported evaluation execution mode."
        )

    if (
        evaluation_run.evaluation_type
        != ASR_EVALUATION_TYPE
    ):
        raise ValueError(
            "Unsupported evaluation type."
        )

    if result.id is None:
        raise ValueError(
            "Evaluation result must be flushed "
            "before provenance is built."
        )

    if (
        result.run_id != evaluation_run.id
        or result.test_case_id != test_case.id
    ):
        raise ValueError(
            "Evaluation result provenance resources "
            "do not match."
        )

    reference_text = test_case.reference_transcript
    generated_text = result.generated_transcript

    if not isinstance(reference_text, str):
        raise ValueError(
            "Reference transcript is unavailable."
        )

    if not isinstance(generated_text, str):
        raise ValueError(
            "Generated transcript is unavailable."
        )

    reference_bytes = reference_text.encode(
        "utf-8"
    )
    generated_bytes = generated_text.encode(
        "utf-8"
    )

    input_artifact_evidence: (
        dict[str, object] | None
    ) = None

    observation_evidence_snapshot: (
        dict[str, object] | None
    ) = None

    if observation_evidence_bundle is not None:
        if not _observation_evidence_bundle_matches_result(
            bundle=observation_evidence_bundle,
            evaluation_type=(
                evaluation_run.evaluation_type
            ),
            evaluation_run_id=(
                evaluation_run.id
            ),
            test_case_id=test_case.id,
        ):
            raise ValueError(
                "HVEE observation evidence does not "
                "match the evaluation result."
            )

        # Canonical JSON round-trip creates a detached snapshot so
        # later caller mutation cannot alter the payload by reference.
        observation_evidence_snapshot = (
            json.loads(
                canonicalize_json(
                    observation_evidence_bundle
                )
            )
        )

    schema_version = (
        EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION
        if observation_evidence_snapshot is not None
        else EVALUATION_RESULT_PROVENANCE_HVEE_ASR_EVIDENCE_SCHEMA_VERSION
    )

    if input_artifact_seal is not None:
        if normalized_mode not in {
            "server_asr",
            "runner_asr",
        }:
            raise ValueError(
                "Input artifact evidence is only "
                "supported for ASR execution modes."
            )

        input_artifact_evidence = (
            _build_input_artifact_evidence(
                evaluation_run=evaluation_run,
                test_case=test_case,
                input_artifact_seal=(
                    input_artifact_seal
                ),
            )
        )

    payload: dict[str, object] = {
        "schema_version": schema_version,
        "evaluation_type": (
            evaluation_run.evaluation_type
        ),
        "result": {
            "id": result.id,
            "run_id": result.run_id,
            "test_case_id": result.test_case_id,
        },
        "run_manifest": (
            _build_run_manifest_evidence(
                evaluation_run
            )
        ),
        "evidence": {
            "reference_transcript": {
                "sha256": calculate_text_sha256(
                    reference_text
                ),
                "utf8_bytes": len(
                    reference_bytes
                ),
            },
            "generated_transcript": {
                "sha256": calculate_text_sha256(
                    generated_text
                ),
                "utf8_bytes": len(
                    generated_bytes
                ),
            },
        },
        "hvee_asr": build_hvee_asr_normalized_evidence(
            reference_text=reference_text,
            generated_text=generated_text,
        ),
        "evaluation": {
            "engine": HETREN_EVALUATOR_ENGINE,
            "contract_version": (
                ASR_EVALUATOR_CONTRACT_VERSION
            ),
            "wer": result.wer,
            "cer": result.cer,
            "quality_label": (
                result.quality_label
            ),
        },
        "execution": {
            "mode": normalized_mode,
            "requested_model": (
                evaluation_run.model_name
            ),
            "server_observed": dict(
                server_observed or {}
            ),
            "external_reported": dict(
                external_reported or {}
            ),
        },
    }

    if input_artifact_evidence is not None:
        payload["input_artifact"] = (
            input_artifact_evidence
        )

    if observation_evidence_snapshot is not None:
        payload["hvee_observations"] = (
            observation_evidence_snapshot
        )

    # Validate that the complete evidence payload is
    # deterministic JSON before it can be persisted.
    canonicalize_json(payload)

    return payload


def stage_evaluation_result_provenance(
    db: Session,
    *,
    result: models.EvaluationResult,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    execution_mode: str,
    server_observed: dict[str, object] | None = None,
    external_reported: dict[str, object] | None = None,
    input_artifact_seal: (
        models.EvaluationInputArtifactSeal | None
    ) = None,
    bind_observation_evidence: bool = True,
) -> models.EvaluationResultProvenance:
    if result.id is None:
        db.flush()

    if result.provenance is not None:
        raise ValueError(
            "Evaluation result provenance already exists."
        )

    normalized_mode = (
        execution_mode.strip()
        if isinstance(execution_mode, str)
        else ""
    )

    if (
        not bind_observation_evidence
        and normalized_mode != "seed_fixture"
    ):
        raise ValueError(
            "HVEE observation evidence may only be "
            "omitted for explicit seed fixtures."
        )

    observation_evidence_bundle: (
        dict[str, object] | None
    ) = None

    if bind_observation_evidence:
        observation_evidence_bundle = (
            build_test_case_observation_evidence_bundle(
                db,
                evaluation_run_id=evaluation_run.id,
                test_case_id=test_case.id,
            )
        )

    payload = (
        build_evaluation_result_provenance_payload(
            result=result,
            evaluation_run=evaluation_run,
            test_case=test_case,
            execution_mode=execution_mode,
            server_observed=server_observed,
            external_reported=external_reported,
            input_artifact_seal=(
                input_artifact_seal
            ),
            observation_evidence_bundle=(
                observation_evidence_bundle
            ),
        )
    )

    provenance = models.EvaluationResultProvenance(
        result_id=result.id,
        schema_version=int(
            payload["schema_version"]
        ),
        evaluation_type=(
            evaluation_run.evaluation_type
        ),
        execution_mode=execution_mode.strip(),
        provenance_payload=payload,
        provenance_sha256=(
            calculate_manifest_sha256(payload)
        ),
    )

    db.add(provenance)

    # Keep the in-memory one-to-one relationship synchronized with
    # the provenance row staged through result_id. The relationship
    # may already be loaded as None by the duplicate-provenance check
    # above, so SQLAlchemy will not otherwise update it automatically
    # until the result is expired or refreshed.
    result.provenance = provenance

    return provenance


def _verify_v2_input_artifact_evidence(
    *,
    payload: dict[str, object],
    provenance: models.EvaluationResultProvenance,
) -> bool:
    """
    Verify the self-contained input-artifact evidence carried by
    result provenance schema v2.

    The seal payload can be reconstructed without exposing or reading
    an internal filesystem path.
    """
    from app.evaluation_artifacts import (
        INPUT_ARTIFACT_SEAL_SCHEMA_VERSION,
        build_evaluation_input_artifact_seal_payload,
        calculate_artifact_seal_sha256,
    )

    result = payload.get("result")
    run_manifest = payload.get("run_manifest")
    input_artifact = payload.get(
        "input_artifact"
    )
    execution = payload.get("execution")

    if (
        not isinstance(result, dict)
        or not isinstance(run_manifest, dict)
        or not isinstance(
            input_artifact,
            dict,
        )
        or not isinstance(execution, dict)
    ):
        return False

    run_id = result.get("run_id")
    test_case_id = result.get(
        "test_case_id"
    )

    if (
        type(run_id) is not int
        or run_id <= 0
        or type(test_case_id) is not int
        or test_case_id <= 0
        or execution.get("mode")
        not in {"server_asr", "runner_asr"}
        or input_artifact.get("status")
        != "sealed"
        or input_artifact.get(
            "artifact_role"
        )
        != "input_audio"
        or input_artifact.get(
            "artifact_type"
        )
        != "audio"
        or type(
            input_artifact.get(
                "seal_id"
            )
        )
        is not int
        or input_artifact["seal_id"] <= 0
        or input_artifact.get(
            "seal_schema_version"
        )
        != INPUT_ARTIFACT_SEAL_SCHEMA_VERSION
        or not _is_sha256_hex(
            input_artifact.get(
                "seal_sha256"
            )
        )
        or not _is_sha256_hex(
            input_artifact.get(
                "content_sha256"
            )
        )
        or type(
            input_artifact.get(
                "byte_length"
            )
        )
        is not int
        or input_artifact[
            "byte_length"
        ]
        <= 0
        or not isinstance(
            input_artifact.get(
                "media_type"
            ),
            str,
        )
        or not input_artifact[
            "media_type"
        ].startswith("audio/")
        or not _is_sha256_hex(
            input_artifact.get(
                "run_manifest_sha256"
            )
        )
        or run_manifest.get("status")
        != "sealed"
        or run_manifest.get("sha256")
        != input_artifact.get(
            "run_manifest_sha256"
        )
    ):
        return False

    try:
        reconstructed_seal_payload = (
            build_evaluation_input_artifact_seal_payload(
                evaluation_run_id=run_id,
                test_case_id=test_case_id,
                evaluation_type=(
                    provenance.evaluation_type
                ),
                artifact_role=(
                    input_artifact[
                        "artifact_role"
                    ]
                ),
                artifact_type=(
                    input_artifact[
                        "artifact_type"
                    ]
                ),
                content_sha256=(
                    input_artifact[
                        "content_sha256"
                    ]
                ),
                byte_length=(
                    input_artifact[
                        "byte_length"
                    ]
                ),
                media_type=(
                    input_artifact[
                        "media_type"
                    ]
                ),
                run_manifest_sha256=(
                    input_artifact[
                        "run_manifest_sha256"
                    ]
                ),
            )
        )

        reconstructed_seal_sha256 = (
            calculate_artifact_seal_sha256(
                reconstructed_seal_payload
            )
        )
    except (TypeError, ValueError):
        return False

    return (
        reconstructed_seal_sha256
        == input_artifact["seal_sha256"]
    )


def _verify_v3_hvee_asr_evidence(
    *,
    payload: dict[str, object],
) -> bool:
    """
    Verify schema-v3 normalized ASR evidence structure and identities.

    This validates internal evidence consistency and the expected
    versioned transformation/evaluator contracts. It does not claim
    cryptographic authenticity against an attacker able to rewrite all
    persisted application state.
    """

    hvee_asr = payload.get("hvee_asr")
    source_evidence = payload.get("evidence")

    if (
        not isinstance(hvee_asr, dict)
        or not isinstance(source_evidence, dict)
    ):
        return False

    if set(hvee_asr) != {
        "normalization",
        "derived_text",
        "observation_contracts",
    }:
        return False

    normalization = hvee_asr.get(
        "normalization"
    )

    if normalization != {
        "key": BASIC_TEXT_NORMALIZATION.key,
        "version": BASIC_TEXT_NORMALIZATION.version,
    }:
        return False

    derived_text = hvee_asr.get(
        "derived_text"
    )

    if (
        not isinstance(derived_text, dict)
        or set(derived_text)
        != {"reference", "generated"}
    ):
        return False

    reference_source = source_evidence.get(
        "reference_transcript"
    )
    generated_source = source_evidence.get(
        "generated_transcript"
    )

    reference_derived = derived_text.get(
        "reference"
    )
    generated_derived = derived_text.get(
        "generated"
    )

    pairs = (
        (
            reference_source,
            reference_derived,
        ),
        (
            generated_source,
            generated_derived,
        ),
    )

    for source, derived in pairs:
        if (
            not isinstance(source, dict)
            or not isinstance(derived, dict)
        ):
            return False

        if set(derived) != {
            "source_sha256",
            "normalized_sha256",
            "normalized_utf8_bytes",
        }:
            return False

        source_sha256 = source.get("sha256")
        normalized_sha256 = derived.get(
            "normalized_sha256"
        )
        normalized_utf8_bytes = derived.get(
            "normalized_utf8_bytes"
        )

        if not _is_sha256_hex(source_sha256):
            return False

        if (
            derived.get("source_sha256")
            != source_sha256
        ):
            return False

        if not _is_sha256_hex(
            normalized_sha256
        ):
            return False

        if (
            not isinstance(
                normalized_utf8_bytes,
                int,
            )
            or isinstance(
                normalized_utf8_bytes,
                bool,
            )
            or normalized_utf8_bytes < 0
        ):
            return False

    return (
        hvee_asr.get(
            "observation_contracts"
        )
        == _build_hvee_asr_observation_contracts()
    )


def _verify_v4_observation_evidence(
    *,
    payload: dict[str, object],
) -> bool:
    """
    Verify schema-v4 observation evidence and parent-resource binding.

    This validates internal integrity and binding. It does not prove
    authenticity against an attacker able to rewrite all persisted
    application state and recompute digests.
    """

    if not _verify_v3_hvee_asr_evidence(
        payload=payload,
    ):
        return False

    expected_keys = {
        "schema_version",
        "evaluation_type",
        "result",
        "run_manifest",
        "evidence",
        "hvee_asr",
        "hvee_observations",
        "evaluation",
        "execution",
    }

    if "input_artifact" in payload:
        expected_keys.add(
            "input_artifact"
        )

    if set(payload) != expected_keys:
        return False

    result = payload.get("result")

    if (
        not isinstance(result, dict)
        or set(result)
        != {
            "id",
            "run_id",
            "test_case_id",
        }
    ):
        return False

    result_id = result.get("id")
    run_id = result.get("run_id")
    test_case_id = result.get(
        "test_case_id"
    )

    for identifier in (
        result_id,
        run_id,
        test_case_id,
    ):
        if (
            isinstance(identifier, bool)
            or not isinstance(
                identifier,
                int,
            )
            or identifier < 1
        ):
            return False

    return _observation_evidence_bundle_matches_result(
        bundle=payload.get(
            "hvee_observations"
        ),
        evaluation_type=payload.get(
            "evaluation_type"
        ),
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
    )


def verify_evaluation_result_provenance(
    provenance: models.EvaluationResultProvenance,
) -> bool:
    payload = provenance.provenance_payload

    if not isinstance(payload, dict):
        return False

    if (
        provenance.schema_version
        not in (
            SUPPORTED_EVALUATION_RESULT_PROVENANCE_SCHEMA_VERSIONS
        )
        or provenance.evaluation_type
        != ASR_EVALUATION_TYPE
        or payload.get("schema_version")
        != provenance.schema_version
        or payload.get("evaluation_type")
        != provenance.evaluation_type
    ):
        return False

    execution = payload.get("execution")

    if (
        not isinstance(execution, dict)
        or execution.get("mode")
        != provenance.execution_mode
    ):
        return False

    if (
        provenance.schema_version
        == EVALUATION_RESULT_PROVENANCE_SCHEMA_VERSION
    ):
        if "input_artifact" in payload:
            return False

    elif (
        provenance.schema_version
        == EVALUATION_RESULT_PROVENANCE_INPUT_ARTIFACT_SCHEMA_VERSION
    ):
        if not _verify_v2_input_artifact_evidence(
            payload=payload,
            provenance=provenance,
        ):
            return False

    elif (
        provenance.schema_version
        == EVALUATION_RESULT_PROVENANCE_HVEE_ASR_EVIDENCE_SCHEMA_VERSION
    ):
        if not _verify_v3_hvee_asr_evidence(
            payload=payload,
        ):
            return False

        # Schema v3 can also carry the existing sealed audio evidence.
        # Reuse the established v2 artifact verification contract.
        if (
            "input_artifact" in payload
            and not _verify_v2_input_artifact_evidence(
                payload=payload,
                provenance=provenance,
            )
        ):
            return False

    elif (
        provenance.schema_version
        == EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION
    ):
        if not _verify_v4_observation_evidence(
            payload=payload,
        ):
            return False

        if (
            "input_artifact" in payload
            and not _verify_v2_input_artifact_evidence(
                payload=payload,
                provenance=provenance,
            )
        ):
            return False

    try:
        expected_sha256 = (
            calculate_manifest_sha256(
                payload
            )
        )
    except ValueError:
        return False

    return (
        provenance.provenance_sha256
        == expected_sha256
    )



def verify_evaluation_result_observation_binding(
    db: Session,
    provenance: models.EvaluationResultProvenance,
) -> bool:
    """
    Compare stored schema-v4 evidence with current persisted observations.

    The normal provenance verifier checks the self-contained evidence
    payload. This verifier additionally detects later changes to the
    persisted HVEE observation rows.
    """

    if (
        provenance.schema_version
        != EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION
        or not verify_evaluation_result_provenance(
            provenance
        )
    ):
        return False

    payload = provenance.provenance_payload

    if not isinstance(payload, dict):
        return False

    result = payload.get("result")

    if not isinstance(result, dict):
        return False

    run_id = result.get("run_id")
    test_case_id = result.get(
        "test_case_id"
    )

    if (
        isinstance(run_id, bool)
        or not isinstance(run_id, int)
        or run_id < 1
        or isinstance(test_case_id, bool)
        or not isinstance(test_case_id, int)
        or test_case_id < 1
    ):
        return False

    try:
        current_bundle = (
            build_test_case_observation_evidence_bundle(
                db,
                evaluation_run_id=run_id,
                test_case_id=test_case_id,
            )
        )
    except HveeObservationEvidenceError:
        return False

    return (
        payload.get("hvee_observations")
        == current_bundle
    )
