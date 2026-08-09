from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
)
from app.evaluation_service import persist_evaluation_result
from app.hvee_decision_service import (
    HveeDecisionConflictError,
    HveeDecisionPersistenceError,
    stage_asr_hvee_matched_release_decision,
)
from app.hvee_models import (
    HveeMatchedReleaseDecision,
    HveeMatchedReleaseDecisionBinding,
    HveeObservation,
)
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
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


def _policy(
    *,
    normalized_wer_margin: float = 0.01,
) -> ASRMatchedReleaseAssurancePolicyV1:
    return ASRMatchedReleaseAssurancePolicyV1(
        interval=PairedIntervalPolicy(
            method=(
                PairedIntervalMethod
                .BOOTSTRAP_PERCENTILE_V1
            ),
            confidence_level=0.95,
            minimum_usable_pairs=4,
            resamples=512,
            random_seed=12345,
        ),
        normalized_wer_noninferiority_margin=(
            normalized_wer_margin
        ),
        normalized_cer_noninferiority_margin=None,
    )


def _create_matched_results(
    db: Session,
) -> tuple[
    models.EvaluationRun,
    models.EvaluationRun,
    tuple[int, ...],
    dict[int, tuple[int, int]],
]:
    project = models.Project(
        name="HVEE matched release service project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="HVEE matched release service dataset",
    )
    db.add(dataset)
    db.flush()

    test_cases = []

    for number in range(1, 5):
        test_case = models.TestCase(
            dataset_id=dataset.id,
            title=f"HVEE matched release case {number}",
            reference_transcript="the quick brown fox",
        )
        db.add(test_case)
        test_cases.append(test_case)

    db.flush()

    baseline_run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="HVEE matched baseline run",
        model_name="baseline-model",
    )
    candidate_run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="HVEE matched candidate run",
        model_name="candidate-model",
    )

    provenance_pairs = {}

    for test_case in test_cases:
        baseline_result = persist_evaluation_result(
            db=db,
            db_run=baseline_run,
            db_test_case=test_case,
            generated_text="the quick brown fox",
            execution_mode="uploaded_transcript",
        )
        candidate_result = persist_evaluation_result(
            db=db,
            db_run=candidate_run,
            db_test_case=test_case,
            generated_text="the quick brown fox",
            execution_mode="uploaded_transcript",
        )

        baseline_provenance = baseline_result.provenance
        candidate_provenance = candidate_result.provenance

        assert baseline_provenance is not None
        assert candidate_provenance is not None

        provenance_pairs[test_case.id] = (
            baseline_provenance.id,
            candidate_provenance.id,
        )

    return (
        baseline_run,
        candidate_run,
        tuple(
            test_case.id
            for test_case in test_cases
        ),
        provenance_pairs,
    )


def test_stages_matched_release_from_verified_provenance(
    db: Session,
):
    (
        baseline_run,
        candidate_run,
        declared_test_case_ids,
        provenance_pairs,
    ) = _create_matched_results(db)

    decision = (
        stage_asr_hvee_matched_release_decision(
            db,
            baseline_run_id=baseline_run.id,
            candidate_run_id=candidate_run.id,
            declared_test_case_ids=(
                declared_test_case_ids
            ),
            policy=_policy(),
        )
    )

    assert decision.id is not None
    assert decision.baseline_run_id == baseline_run.id
    assert decision.candidate_run_id == candidate_run.id
    assert decision.verdict == "pass"
    assert decision.reason == "claim_supported"
    assert decision.decision_payload["target"] == {
        "baseline_run_id": baseline_run.id,
        "candidate_run_id": candidate_run.id,
        "declared_test_case_ids": list(
            declared_test_case_ids
        ),
    }
    assert (
        decision.decision_payload["policy"]["sha256"]
        == decision.policy_sha256
    )

    bindings = (
        db.query(HveeMatchedReleaseDecisionBinding)
        .filter(
            HveeMatchedReleaseDecisionBinding
            .matched_release_decision_id
            == decision.id
        )
        .order_by(
            HveeMatchedReleaseDecisionBinding.test_case_id
        )
        .all()
    )

    assert tuple(
        binding.test_case_id
        for binding in bindings
    ) == declared_test_case_ids

    assert {
        binding.test_case_id: (
            binding.baseline_result_provenance_id,
            binding.candidate_result_provenance_id,
        )
        for binding in bindings
    } == provenance_pairs


def _stage_matched_decision(
    db: Session,
    *,
    baseline_run: models.EvaluationRun,
    candidate_run: models.EvaluationRun,
    declared_test_case_ids: tuple[int, ...],
    policy: (
        ASRMatchedReleaseAssurancePolicyV1
        | None
    ) = None,
) -> HveeMatchedReleaseDecision:
    selected_policy = (
        _policy()
        if policy is None
        else policy
    )

    return stage_asr_hvee_matched_release_decision(
        db,
        baseline_run_id=baseline_run.id,
        candidate_run_id=candidate_run.id,
        declared_test_case_ids=(
            declared_test_case_ids
        ),
        policy=selected_policy,
    )


def test_exact_replay_returns_same_immutable_decision(
    db: Session,
):
    (
        baseline_run,
        candidate_run,
        declared_test_case_ids,
        _,
    ) = _create_matched_results(db)

    first = _stage_matched_decision(
        db,
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        declared_test_case_ids=(
            declared_test_case_ids
        ),
    )
    replay = _stage_matched_decision(
        db,
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        declared_test_case_ids=(
            declared_test_case_ids
        ),
    )

    assert replay.id == first.id
    assert (
        replay.decision_sha256
        == first.decision_sha256
    )
    assert (
        db.query(
            HveeMatchedReleaseDecision
        ).count()
        == 1
    )
    assert (
        db.query(
            HveeMatchedReleaseDecisionBinding
        ).count()
        == len(declared_test_case_ids)
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "tampered_digest",
    ),
)
def test_rejects_missing_or_tampered_provenance(
    db: Session,
    mutation: str,
):
    (
        baseline_run,
        candidate_run,
        declared_test_case_ids,
        provenance_pairs,
    ) = _create_matched_results(db)

    provenance_id = provenance_pairs[
        declared_test_case_ids[0]
    ][0]
    provenance = db.get(
        models.EvaluationResultProvenance,
        provenance_id,
    )

    assert provenance is not None

    if mutation == "missing":
        db.delete(provenance)
    else:
        provenance.provenance_sha256 = "0" * 64

    db.flush()

    with pytest.raises(
        HveeDecisionPersistenceError,
        match="provenance",
    ):
        _stage_matched_decision(
            db,
            baseline_run=baseline_run,
            candidate_run=candidate_run,
            declared_test_case_ids=(
                declared_test_case_ids
            ),
        )


def test_rejects_observation_drift_after_binding(
    db: Session,
):
    (
        baseline_run,
        candidate_run,
        declared_test_case_ids,
        _,
    ) = _create_matched_results(db)

    observation = (
        db.query(HveeObservation)
        .filter(
            HveeObservation.evaluation_run_id
            == baseline_run.id,
            HveeObservation.test_case_id
            == declared_test_case_ids[0],
            HveeObservation.scope
            == "test_case",
            HveeObservation.number_value
            .is_not(None),
        )
        .order_by(HveeObservation.id)
        .first()
    )

    assert observation is not None

    observation.number_value = (
        0.99
        if observation.number_value != 0.99
        else 0.98
    )
    db.flush()

    with pytest.raises(
        HveeDecisionPersistenceError,
        match="no longer match",
    ):
        _stage_matched_decision(
            db,
            baseline_run=baseline_run,
            candidate_run=candidate_run,
            declared_test_case_ids=(
                declared_test_case_ids
            ),
        )


def test_rejects_incomplete_declared_cohort(
    db: Session,
):
    (
        baseline_run,
        candidate_run,
        declared_test_case_ids,
        _,
    ) = _create_matched_results(db)

    first_test_case = db.get(
        models.TestCase,
        declared_test_case_ids[0],
    )
    assert first_test_case is not None

    missing_case = models.TestCase(
        dataset_id=first_test_case.dataset_id,
        title="HVEE unmatched declared case",
        reference_transcript=(
            "this case has no matched results"
        ),
    )
    db.add(missing_case)
    db.flush()

    with pytest.raises(
        HveeDecisionPersistenceError,
        match="result was not found",
    ):
        _stage_matched_decision(
            db,
            baseline_run=baseline_run,
            candidate_run=candidate_run,
            declared_test_case_ids=(
                declared_test_case_ids
                + (missing_case.id,)
            ),
        )


def test_rejects_runs_from_different_projects(
    db: Session,
):
    (
        baseline_run,
        _,
        declared_test_case_ids,
        _,
    ) = _create_matched_results(db)

    foreign_project = models.Project(
        name="Foreign matched-release project",
    )
    db.add(foreign_project)
    db.flush()

    foreign_run = stage_evaluation_run_with_manifest(
        db,
        project_id=foreign_project.id,
        run_name="Foreign candidate run",
        model_name="foreign-model",
    )

    with pytest.raises(
        HveeDecisionPersistenceError,
        match="same project",
    ):
        _stage_matched_decision(
            db,
            baseline_run=baseline_run,
            candidate_run=foreign_run,
            declared_test_case_ids=(
                declared_test_case_ids
            ),
        )


def test_replay_detects_persisted_decision_tampering(
    db: Session,
):
    (
        baseline_run,
        candidate_run,
        declared_test_case_ids,
        _,
    ) = _create_matched_results(db)

    decision = _stage_matched_decision(
        db,
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        declared_test_case_ids=(
            declared_test_case_ids
        ),
    )

    decision.decision_sha256 = "0" * 64
    db.flush()

    with pytest.raises(
        HveeDecisionConflictError,
        match="conflicts with canonical evidence",
    ):
        _stage_matched_decision(
            db,
            baseline_run=baseline_run,
            candidate_run=candidate_run,
            declared_test_case_ids=(
                declared_test_case_ids
            ),
        )


def test_distinct_policy_creates_distinct_decision(
    db: Session,
):
    (
        baseline_run,
        candidate_run,
        declared_test_case_ids,
        _,
    ) = _create_matched_results(db)

    first = _stage_matched_decision(
        db,
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        declared_test_case_ids=(
            declared_test_case_ids
        ),
    )
    second = _stage_matched_decision(
        db,
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        declared_test_case_ids=(
            declared_test_case_ids
        ),
        policy=_policy(
            normalized_wer_margin=0.02,
        ),
    )

    assert second.id != first.id
    assert (
        second.target_sha256
        == first.target_sha256
    )
    assert (
        second.policy_sha256
        != first.policy_sha256
    )
    assert (
        db.query(
            HveeMatchedReleaseDecision
        ).count()
        == 2
    )
    assert (
        db.query(
            HveeMatchedReleaseDecisionBinding
        ).count()
        == 2 * len(declared_test_case_ids)
    )
