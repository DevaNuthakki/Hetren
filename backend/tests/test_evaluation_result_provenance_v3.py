from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    EVALUATION_RESULT_PROVENANCE_HVEE_ASR_EVIDENCE_SCHEMA_VERSION,
    build_evaluation_result_provenance_payload,
    build_hvee_asr_normalized_evidence,
    calculate_manifest_sha256,
    calculate_text_sha256,
    stage_evaluation_run_with_manifest,
    verify_evaluation_result_provenance,
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


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine)
    session = factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_resources(
    db: Session,
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
    models.EvaluationResult,
]:
    project = models.Project(
        name="HVEE ASR provenance v3 project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="HVEE ASR provenance v3 dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="HVEE ASR provenance v3 case",
        reference_transcript="Hello, WORLD!",
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="HVEE ASR provenance v3 run",
        model_name="test-model",
    )

    result = models.EvaluationResult(
        run_id=run.id,
        test_case_id=test_case.id,
        generated_transcript="hello there",
        wer=0.5,
        cer=0.4,
        quality_label="regression",
        error_summary="test result",
    )
    db.add(result)
    db.flush()

    return run, test_case, result


def _stage_v3_provenance(
    db: Session,
    *,
    run: models.EvaluationRun,
    test_case: models.TestCase,
    result: models.EvaluationResult,
) -> models.EvaluationResultProvenance:
    payload = build_evaluation_result_provenance_payload(
        result=result,
        evaluation_run=run,
        test_case=test_case,
        execution_mode="uploaded_transcript",
    )

    payload["schema_version"] = (
        EVALUATION_RESULT_PROVENANCE_HVEE_ASR_EVIDENCE_SCHEMA_VERSION
    )
    payload["hvee_asr"] = (
        build_hvee_asr_normalized_evidence(
            reference_text=(
                test_case.reference_transcript
            ),
            generated_text=(
                result.generated_transcript
            ),
        )
    )

    provenance = models.EvaluationResultProvenance(
        result_id=result.id,
        schema_version=(
            EVALUATION_RESULT_PROVENANCE_HVEE_ASR_EVIDENCE_SCHEMA_VERSION
        ),
        evaluation_type="asr",
        execution_mode="uploaded_transcript",
        provenance_payload=payload,
        provenance_sha256=(
            calculate_manifest_sha256(payload)
        ),
    )

    db.add(provenance)
    db.flush()

    return provenance


def test_v3_normalized_evidence_is_privacy_conscious():
    reference = "Hello, WORLD!"
    generated = "HELLO -- there"

    evidence = build_hvee_asr_normalized_evidence(
        reference_text=reference,
        generated_text=generated,
    )

    normalized_reference = normalize_text_basic(
        reference
    )
    normalized_generated = normalize_text_basic(
        generated
    )

    serialized = str(evidence)

    assert reference not in serialized
    assert generated not in serialized
    assert normalized_reference not in serialized
    assert normalized_generated not in serialized

    assert evidence["normalization"] == {
        "key": BASIC_TEXT_NORMALIZATION.key,
        "version": BASIC_TEXT_NORMALIZATION.version,
    }

    reference_evidence = evidence[
        "derived_text"
    ]["reference"]

    generated_evidence = evidence[
        "derived_text"
    ]["generated"]

    assert reference_evidence[
        "source_sha256"
    ] == calculate_text_sha256(reference)

    assert reference_evidence[
        "normalized_sha256"
    ] == calculate_text_sha256(
        normalized_reference
    )

    assert reference_evidence[
        "normalized_utf8_bytes"
    ] == len(
        normalized_reference.encode("utf-8")
    )

    assert generated_evidence[
        "source_sha256"
    ] == calculate_text_sha256(generated)

    assert generated_evidence[
        "normalized_sha256"
    ] == calculate_text_sha256(
        normalized_generated
    )


def test_v3_binds_expected_observation_contracts():
    evidence = build_hvee_asr_normalized_evidence(
        reference_text="one two",
        generated_text="one three",
    )

    assert evidence[
        "observation_contracts"
    ] == [
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
            "metric_version": NORMALIZED_SUBSTITUTIONS_METRIC.version,
            "evaluator_key": NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key,
            "evaluator_version": NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version,
        },
        {
            "metric_key": NORMALIZED_INSERTIONS_METRIC.key,
            "metric_version": NORMALIZED_INSERTIONS_METRIC.version,
            "evaluator_key": NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key,
            "evaluator_version": NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version,
        },
        {
            "metric_key": NORMALIZED_DELETIONS_METRIC.key,
            "metric_version": NORMALIZED_DELETIONS_METRIC.version,
            "evaluator_key": NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key,
            "evaluator_version": NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version,
        },
    ]


def test_v3_provenance_verifier_accepts_valid_evidence(
    db: Session,
):
    run, test_case, result = _create_resources(db)

    provenance = _stage_v3_provenance(
        db,
        run=run,
        test_case=test_case,
        result=result,
    )

    assert provenance.schema_version == 3
    assert verify_evaluation_result_provenance(
        provenance
    )


def test_v3_verifier_rejects_normalization_identity_rewrite(
    db: Session,
):
    run, test_case, result = _create_resources(db)

    provenance = _stage_v3_provenance(
        db,
        run=run,
        test_case=test_case,
        result=result,
    )

    payload = dict(
        provenance.provenance_payload
    )
    hvee_asr = dict(payload["hvee_asr"])
    normalization = dict(
        hvee_asr["normalization"]
    )
    normalization["version"] = "999.0.0"
    hvee_asr["normalization"] = normalization
    payload["hvee_asr"] = hvee_asr

    provenance.provenance_payload = payload

    # Recalculate the outer hash to prove that v3 semantic
    # validation is stronger than merely checking that digest.
    provenance.provenance_sha256 = (
        calculate_manifest_sha256(payload)
    )

    assert not verify_evaluation_result_provenance(
        provenance
    )


def test_v3_verifier_rejects_broken_source_linkage(
    db: Session,
):
    run, test_case, result = _create_resources(db)

    provenance = _stage_v3_provenance(
        db,
        run=run,
        test_case=test_case,
        result=result,
    )

    payload = dict(
        provenance.provenance_payload
    )
    hvee_asr = dict(payload["hvee_asr"])
    derived_text = dict(
        hvee_asr["derived_text"]
    )
    reference = dict(
        derived_text["reference"]
    )

    reference["source_sha256"] = "f" * 64
    derived_text["reference"] = reference
    hvee_asr["derived_text"] = derived_text
    payload["hvee_asr"] = hvee_asr

    provenance.provenance_payload = payload
    provenance.provenance_sha256 = (
        calculate_manifest_sha256(payload)
    )

    assert not verify_evaluation_result_provenance(
        provenance
    )


def test_v3_verifier_rejects_changed_observation_contract(
    db: Session,
):
    run, test_case, result = _create_resources(db)

    provenance = _stage_v3_provenance(
        db,
        run=run,
        test_case=test_case,
        result=result,
    )

    payload = dict(
        provenance.provenance_payload
    )
    hvee_asr = dict(payload["hvee_asr"])

    contracts = [
        dict(contract)
        for contract in hvee_asr[
            "observation_contracts"
        ]
    ]

    contracts[0]["metric_version"] = "999.0.0"

    hvee_asr["observation_contracts"] = (
        contracts
    )
    payload["hvee_asr"] = hvee_asr

    provenance.provenance_payload = payload
    provenance.provenance_sha256 = (
        calculate_manifest_sha256(payload)
    )

    assert not verify_evaluation_result_provenance(
        provenance
    )


def test_v3_verifier_rejects_unexpected_derived_plaintext(
    db: Session,
):
    run, test_case, result = _create_resources(db)

    provenance = _stage_v3_provenance(
        db,
        run=run,
        test_case=test_case,
        result=result,
    )

    payload = dict(
        provenance.provenance_payload
    )
    hvee_asr = dict(payload["hvee_asr"])
    derived_text = dict(
        hvee_asr["derived_text"]
    )
    reference = dict(
        derived_text["reference"]
    )

    reference["normalized_text"] = (
        "this plaintext must never be accepted"
    )

    derived_text["reference"] = reference
    hvee_asr["derived_text"] = derived_text
    payload["hvee_asr"] = hvee_asr

    provenance.provenance_payload = payload
    provenance.provenance_sha256 = (
        calculate_manifest_sha256(payload)
    )

    assert not verify_evaluation_result_provenance(
        provenance
    )
