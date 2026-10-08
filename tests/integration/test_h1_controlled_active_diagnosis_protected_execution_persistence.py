import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from environments.agent.h1_controlled_active_diagnosis import (
    build_development_fixtures,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis import (
    H1Arm,
)
import packages.engines.behavioral.h1_controlled_active_diagnosis_protected_execution_persistence as persistence


DUMMY_REPOSITORY_HEAD = "a" * 40
DUMMY_D1_COMMIT = "b" * 40
DUMMY_GENERATION_FREEZE_COMMIT = "c" * 40

DUMMY_GENERATION_RECORD_SHA = "d" * 64
DUMMY_ENVIRONMENT_SHA = "e" * 64
DUMMY_TREATMENT_SHA = "f" * 64
DUMMY_EVALUATION_SHA = "1" * 64
DUMMY_PERSISTENCE_SHA = "2" * 64


def _canonical_json_bytes(
    value,
):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode(
        "utf-8"
    )


def _development_input(
    tmp_path,
    *,
    full=False,
):
    fixtures = (
        build_development_fixtures()
    )

    cost_sensitive = next(
        fixture
        for fixture in fixtures
        if fixture
        .public_case
        .template_id
        .startswith("T")
    )

    neutral = next(
        fixture
        for fixture in fixtures
        if fixture
        .public_case
        .template_id
        .startswith("N")
    )

    if full:
        selected = tuple(
            fixtures
        )
    else:
        selected = (
            cost_sensitive,
            neutral,
        )

    batch_id = (
        "d2-development-batch"
    )

    public_manifest = {
        "record_type": "H1PublicManifest",
        "schema_version": 1,
        "batch_id": batch_id,
        "protocol_sha256": "3" * 64,
        "harness_commit_id": "4" * 40,
        "generator_id": "d2-development-test",
        "generator_version": "1",
        "cases": [
            {
                "case_id": (
                    fixture
                    .public_case
                    .case_id
                ),
                "template_id": (
                    fixture
                    .public_case
                    .template_id
                ),
                "singleton_target": (
                    fixture
                    .public_case
                    .singleton_target
                ),
                "problem_sha256": (
                    fixture
                    .public_case
                    .problem
                    .problem_sha256
                ),
            }
            for fixture in selected
        ],
    }

    hidden_manifest = {
        "record_type": (
            "H1HiddenTruthManifest"
        ),
        "schema_version": 1,
        "batch_id": batch_id,
        "assignments": [
            {
                "case_id": (
                    fixture
                    .truth
                    .case_id
                ),
                "hidden_fault_key": (
                    fixture
                    .truth
                    .hidden_fault_key
                ),
            }
            for fixture in selected
        ],
    }

    batch_directory = (
        tmp_path
        / "protected_v1"
    )

    batch_directory.mkdir(
        mode=0o700
    )

    public_manifest_path = (
        tmp_path
        / "public_manifest.json"
    )

    hidden_manifest_path = (
        tmp_path
        / "hidden_manifest.json"
    )

    public_manifest_path.write_bytes(
        _canonical_json_bytes(
            public_manifest
        )
    )

    hidden_manifest_path.write_bytes(
        _canonical_json_bytes(
            hidden_manifest
        )
    )

    kwargs = {
        "batch_directory": (
            batch_directory
        ),
        "batch_id": batch_id,
        "attempt_id": "execution_v1",
        "public_manifest_path": (
            public_manifest_path
        ),
        "hidden_manifest_path": (
            hidden_manifest_path
        ),
        "expected_public_manifest_sha256": (
            canonical_sha256(
                public_manifest
            )
        ),
        "expected_hidden_manifest_sha256": (
            canonical_sha256(
                hidden_manifest
            )
        ),
        "repository_head_commit_id": (
            DUMMY_REPOSITORY_HEAD
        ),
        "d1_contract_commit_id": (
            DUMMY_D1_COMMIT
        ),
        "generation_freeze_commit_id": (
            DUMMY_GENERATION_FREEZE_COMMIT
        ),
        "generation_record_sha256": (
            DUMMY_GENERATION_RECORD_SHA
        ),
        "environment_module_sha256": (
            DUMMY_ENVIRONMENT_SHA
        ),
        "treatment_module_sha256": (
            DUMMY_TREATMENT_SHA
        ),
        "evaluation_module_sha256": (
            DUMMY_EVALUATION_SHA
        ),
        "execution_persistence_module_sha256": (
            DUMMY_PERSISTENCE_SHA
        ),
    }

    return {
        "kwargs": kwargs,
        "batch_directory": batch_directory,
        "public_manifest": public_manifest,
        "hidden_manifest": hidden_manifest,
    }


def _run_success(
    tmp_path,
):
    data = _development_input(
        tmp_path
    )

    result = (
        persistence
        .persist_h1_protected_execution_attempt(
            **data["kwargs"]
        )
    )

    return (
        data,
        result,
    )


def _read_json(
    path,
):
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def test_post_claim_setup_failure_records_failed_and_consumes_attempt(
    tmp_path,
    monkeypatch,
):
    data = _development_input(
        tmp_path
    )

    original = (
        persistence
        ._fsync_directory
    )

    calls = {
        "count": 0,
    }

    def fail_first(
        directory,
    ):
        calls[
            "count"
        ] += 1

        if calls[
            "count"
        ] == 1:
            raise OSError(
                "injected post-claim fsync failure"
            )

        return original(
            directory
        )

    monkeypatch.setattr(
        persistence,
        "_fsync_directory",
        fail_first,
    )

    with pytest.raises(
        OSError,
        match="post-claim fsync",
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data[
                "kwargs"
            ]
        )

    disposition = _read_json(
        data[
            "batch_directory"
        ]
        / "execution_v1"
        / "public"
        / "execution_disposition.json"
    )

    assert (
        disposition[
            "status"
        ]
        == "FAILED"
    )

    assert (
        disposition[
            "phase"
        ]
        == "FSYNC_ATTEMPT_CLAIM"
    )

    assert (
        disposition[
            "failure_category"
        ]
        == "SETUP_FAILURE"
    )

    assert (
        disposition[
            "treatment_started"
        ]
        is False
    )

    with pytest.raises(
        FileExistsError,
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data[
                "kwargs"
            ]
        )


def test_initial_started_disposition_failure_recovers_failed_without_treatment(
    tmp_path,
    monkeypatch,
):
    data = _development_input(
        tmp_path
    )

    original = (
        persistence
        ._atomic_write_new
    )

    injected = {
        "done": False,
    }

    def fail_first_started(
        file_path,
        data_bytes,
        *,
        mode,
    ):
        payload = json.loads(
            data_bytes.decode(
                "utf-8"
            )
        )

        if (
            file_path.name
            == "execution_disposition.json"
            and payload.get(
                "status"
            )
            == "STARTED"
            and not injected[
                "done"
            ]
        ):
            injected[
                "done"
            ] = True

            raise OSError(
                "injected initial disposition failure"
            )

        return original(
            file_path,
            data_bytes,
            mode=mode,
        )

    monkeypatch.setattr(
        persistence,
        "_atomic_write_new",
        fail_first_started,
    )

    with pytest.raises(
        OSError,
        match="initial disposition",
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data[
                "kwargs"
            ]
        )

    disposition = _read_json(
        data[
            "batch_directory"
        ]
        / "execution_v1"
        / "public"
        / "execution_disposition.json"
    )

    assert (
        disposition[
            "status"
        ]
        == "FAILED"
    )

    assert (
        disposition[
            "phase"
        ]
        == "PERSIST_STARTED_DISPOSITION"
    )

    assert (
        disposition[
            "failure_category"
        ]
        == "SETUP_FAILURE"
    )

    assert (
        disposition[
            "treatment_started"
        ]
        is False
    )

    assert (
        disposition[
            "completed_observation_count"
        ]
        == 0
    )


def test_final_success_disposition_failure_is_finalization_failure(
    tmp_path,
    monkeypatch,
):
    data = _development_input(
        tmp_path
    )

    original = (
        persistence
        ._atomic_replace
    )

    injected = {
        "done": False,
    }

    def fail_success(
        file_path,
        data_bytes,
        *,
        mode,
    ):
        payload = json.loads(
            data_bytes.decode(
                "utf-8"
            )
        )

        if (
            file_path.name
            == "execution_disposition.json"
            and payload.get(
                "status"
            )
            == "SUCCEEDED"
            and not injected[
                "done"
            ]
        ):
            injected[
                "done"
            ] = True

            raise OSError(
                "injected final disposition failure"
            )

        return original(
            file_path,
            data_bytes,
            mode=mode,
        )

    monkeypatch.setattr(
        persistence,
        "_atomic_replace",
        fail_success,
    )

    with pytest.raises(
        OSError,
        match="final disposition",
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data[
                "kwargs"
            ]
        )

    attempt = (
        data[
            "batch_directory"
        ]
        / "execution_v1"
    )

    assert (
        attempt
        / "public"
        / "treatment_batch.json"
    ).exists()

    assert (
        attempt
        / "evaluator"
        / "evaluation.json"
    ).exists()

    assert (
        attempt
        / "public"
        / "execution_record.json"
    ).exists()

    disposition = _read_json(
        attempt
        / "public"
        / "execution_disposition.json"
    )

    assert (
        disposition[
            "status"
        ]
        == "FAILED"
    )

    assert (
        disposition[
            "phase"
        ]
        == "PERSIST_SUCCESS_DISPOSITION"
    )

    assert (
        disposition[
            "failure_category"
        ]
        == "FINALIZATION_FAILURE"
    )

    assert (
        disposition[
            "failure_type"
        ]
        == "OSError"
    )

    assert (
        disposition[
            "treatment_batch_sha256"
        ]
        is not None
    )

    assert (
        disposition[
            "evaluation_sha256"
        ]
        is not None
    )

    assert (
        disposition[
            "execution_record_sha256"
        ]
        is not None
    )

    with pytest.raises(
        FileExistsError,
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data[
                "kwargs"
            ]
        )


def test_full_development_orchestration_preserves_frozen_diagnosis_counts(
    tmp_path,
):
    data = _development_input(
        tmp_path,
        full=True,
    )

    result = (
        persistence
        .persist_h1_protected_execution_attempt(
            **data[
                "kwargs"
            ]
        )
    )

    attempt = (
        data[
            "batch_directory"
        ]
        / "execution_v1"
    )

    treatment = _read_json(
        attempt
        / "public"
        / "treatment_batch.json"
    )

    evaluation = _read_json(
        attempt
        / "evaluator"
        / "evaluation.json"
    )

    assert len(
        treatment[
            "records"
        ]
    ) == (
        32
        * 4
    )

    metrics = {
        (
            metric[
                "group"
            ],
            metric[
                "arm"
            ],
        ): metric
        for metric
        in evaluation[
            "metric_slices"
        ]
    }

    expected_correct = {
        H1Arm.TRACE_ONLY.value:
            0,

        H1Arm.SEEDED_RANDOM_ACTIVE.value:
            11,

        H1Arm.MAX_INFORMATION_GAIN_ACTIVE.value:
            20,

        H1Arm.HEAL_INFORMATION_GAIN_PER_COST.value:
            32,
    }

    for arm in H1Arm:
        metric = metrics[
            (
                "overall",
                arm.value,
            )
        ]

        assert (
            metric[
                "denominator"
            ]
            == 32
        )

        assert (
            metric[
                "correct_specific_count"
            ]
            == expected_correct[
                arm.value
            ]
        )

    assert (
        canonical_sha256(
            treatment
        )
        == result
        .treatment_batch_sha256
    )

    assert (
        canonical_sha256(
            evaluation
        )
        == result
        .evaluation_sha256
    )


def test_success_persists_exact_four_artifacts_and_restrictive_modes(
    tmp_path,
):
    data, result = _run_success(
        tmp_path
    )

    attempt = (
        data["batch_directory"]
        / "execution_v1"
    )

    expected = {
        "public/execution_disposition.json",
        "public/treatment_batch.json",
        "public/execution_record.json",
        "evaluator/evaluation.json",
    }

    actual = {
        str(path.relative_to(attempt))
        for path in attempt.rglob("*")
        if path.is_file()
    }

    assert actual == expected

    assert (
        result.attempt_directory
        == attempt
    )

    for directory in (
        attempt,
        attempt / "public",
        attempt / "evaluator",
    ):
        assert (
            os.stat(directory).st_mode
            & 0o777
        ) == 0o700

    for path in (
        attempt
        / "public"
        / "execution_disposition.json",

        attempt
        / "public"
        / "treatment_batch.json",

        attempt
        / "public"
        / "execution_record.json",

        attempt
        / "evaluator"
        / "evaluation.json",
    ):
        assert (
            os.stat(path).st_mode
            & 0o777
        ) == 0o600


def test_success_record_hashes_bind_treatment_evaluation_and_lineage(
    tmp_path,
):
    data, result = _run_success(
        tmp_path
    )

    attempt = (
        data["batch_directory"]
        / "execution_v1"
    )

    treatment = _read_json(
        attempt
        / "public"
        / "treatment_batch.json"
    )

    evaluation = _read_json(
        attempt
        / "evaluator"
        / "evaluation.json"
    )

    record = _read_json(
        attempt
        / "public"
        / "execution_record.json"
    )

    assert (
        canonical_sha256(treatment)
        == result.treatment_batch_sha256
        == record[
            "treatment_batch_sha256"
        ]
    )

    assert (
        canonical_sha256(evaluation)
        == result.evaluation_sha256
        == record[
            "evaluation_sha256"
        ]
    )

    assert (
        canonical_sha256(record)
        == result.execution_record_sha256
    )

    assert (
        record[
            "repository_head_commit_id"
        ]
        == DUMMY_REPOSITORY_HEAD
    )

    assert (
        record[
            "d1_contract_commit_id"
        ]
        == DUMMY_D1_COMMIT
    )

    assert (
        record[
            "generation_freeze_commit_id"
        ]
        == DUMMY_GENERATION_FREEZE_COMMIT
    )


def test_public_treatment_contains_no_hidden_truth(
    tmp_path,
):
    data, _result = _run_success(
        tmp_path
    )

    text = (
        data["batch_directory"]
        / "execution_v1"
        / "public"
        / "treatment_batch.json"
    ).read_text(
        encoding="utf-8"
    )

    assert "hidden_fault_key" not in text
    assert "hidden_truth" not in text
    assert "raw_seed" not in text


def test_evaluation_is_evaluator_side_and_hash_bound(
    tmp_path,
):
    data, result = _run_success(
        tmp_path
    )

    attempt = (
        data["batch_directory"]
        / "execution_v1"
    )

    assert not (
        attempt
        / "public"
        / "evaluation.json"
    ).exists()

    evaluation = _read_json(
        attempt
        / "evaluator"
        / "evaluation.json"
    )

    assert (
        evaluation[
            "hidden_manifest_sha256"
        ]
        == data[
            "kwargs"
        ][
            "expected_hidden_manifest_sha256"
        ]
    )

    assert (
        canonical_sha256(evaluation)
        == result.evaluation_sha256
    )


def test_second_attempt_refuses_before_treatment(
    tmp_path,
    monkeypatch,
):
    data, _result = _run_success(
        tmp_path
    )

    def forbidden(
        **_kwargs,
    ):
        raise AssertionError(
            "treatment must not run on "
            "a consumed attempt"
        )

    monkeypatch.setattr(
        persistence,
        "run_treatment_batch_from_manifest",
        forbidden,
    )

    with pytest.raises(
        FileExistsError,
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data["kwargs"]
        )


def test_hidden_manifest_hash_failure_consumes_attempt_and_records_failed(
    tmp_path,
):
    data = _development_input(
        tmp_path
    )

    data["kwargs"][
        "expected_hidden_manifest_sha256"
    ] = "0" * 64

    with pytest.raises(
        ContractError,
        match="hidden manifest does not match",
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data["kwargs"]
        )

    disposition = _read_json(
        data["batch_directory"]
        / "execution_v1"
        / "public"
        / "execution_disposition.json"
    )

    assert (
        disposition["status"]
        == "FAILED"
    )

    assert (
        disposition["phase"]
        == "BIND_HIDDEN_MANIFEST"
    )

    assert (
        disposition[
            "failure_category"
        ]
        == "INPUT_BINDING_FAILURE"
    )

    assert (
        disposition[
            "treatment_started"
        ]
        is False
    )

    with pytest.raises(
        FileExistsError,
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data["kwargs"]
        )


def test_treatment_executor_failure_records_case_and_active_arm(
    tmp_path,
    monkeypatch,
):
    data = _development_input(
        tmp_path
    )

    def fail_executor(
        **_kwargs,
    ):
        raise RuntimeError(
            "injected executor failure"
        )

    monkeypatch.setattr(
        persistence,
        "execute_development_experiment",
        fail_executor,
    )

    with pytest.raises(
        RuntimeError,
        match="injected executor failure",
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data["kwargs"]
        )

    disposition = _read_json(
        data["batch_directory"]
        / "execution_v1"
        / "public"
        / "execution_disposition.json"
    )

    assert (
        disposition["status"]
        == "FAILED"
    )

    assert (
        disposition[
            "failure_category"
        ]
        == "TREATMENT_EXECUTION_FAILURE"
    )

    assert (
        disposition[
            "treatment_started"
        ]
        is True
    )

    assert (
        disposition[
            "current_case_id"
        ]
        is not None
    )

    assert (
        disposition[
            "attempted_arm"
        ]
        == "seeded_random_active"
    )

    assert (
        disposition[
            "completed_observation_count"
        ]
        == 0
    )


def test_failure_after_observation_preserves_available_evidence(
    tmp_path,
    monkeypatch,
):
    data = _development_input(
        tmp_path
    )

    original = (
        persistence
        .execute_development_experiment
    )

    calls = {
        "count": 0,
    }

    def fail_second(
        **kwargs,
    ):
        calls["count"] += 1

        if calls["count"] == 2:
            raise RuntimeError(
                "injected second-experiment failure"
            )

        return original(
            **kwargs
        )

    monkeypatch.setattr(
        persistence,
        "execute_development_experiment",
        fail_second,
    )

    with pytest.raises(
        RuntimeError,
        match="second-experiment",
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data["kwargs"]
        )

    disposition = _read_json(
        data["batch_directory"]
        / "execution_v1"
        / "public"
        / "execution_disposition.json"
    )

    assert (
        disposition[
            "completed_observation_count"
        ]
        >= 1
    )

    assert len(
        disposition[
            "available_evidence_references"
        ]
    ) >= 1

    for reference in (
        disposition[
            "available_evidence_references"
        ]
    ):
        assert len(reference) == 64
        int(reference, 16)


def test_evaluation_failure_preserves_completed_treatment(
    tmp_path,
    monkeypatch,
):
    data = _development_input(
        tmp_path
    )

    def fail_evaluation(
        **_kwargs,
    ):
        raise RuntimeError(
            "injected evaluation failure"
        )

    monkeypatch.setattr(
        persistence,
        "evaluate_treatment_batch",
        fail_evaluation,
    )

    with pytest.raises(
        RuntimeError,
        match="injected evaluation failure",
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data["kwargs"]
        )

    attempt = (
        data["batch_directory"]
        / "execution_v1"
    )

    assert (
        attempt
        / "public"
        / "treatment_batch.json"
    ).exists()

    assert not (
        attempt
        / "evaluator"
        / "evaluation.json"
    ).exists()

    disposition = _read_json(
        attempt
        / "public"
        / "execution_disposition.json"
    )

    assert (
        disposition[
            "failure_category"
        ]
        == "EVALUATION_FAILURE"
    )

    assert (
        disposition[
            "treatment_batch_sha256"
        ]
        is not None
    )


def test_execution_record_write_failure_preserves_treatment_and_evaluation(
    tmp_path,
    monkeypatch,
):
    data = _development_input(
        tmp_path
    )

    original = (
        persistence
        ._atomic_write_new
    )

    def fail_record(
        path,
        data_bytes,
        *,
        mode,
    ):
        if (
            path.name
            == "execution_record.json"
        ):
            raise OSError(
                "injected execution-record "
                "persistence failure"
            )

        return original(
            path,
            data_bytes,
            mode=mode,
        )

    monkeypatch.setattr(
        persistence,
        "_atomic_write_new",
        fail_record,
    )

    with pytest.raises(
        OSError,
        match="execution-record persistence",
    ):
        persistence.persist_h1_protected_execution_attempt(
            **data["kwargs"]
        )

    attempt = (
        data["batch_directory"]
        / "execution_v1"
    )

    assert (
        attempt
        / "public"
        / "treatment_batch.json"
    ).exists()

    assert (
        attempt
        / "evaluator"
        / "evaluation.json"
    ).exists()

    disposition = _read_json(
        attempt
        / "public"
        / "execution_disposition.json"
    )

    assert (
        disposition[
            "failure_category"
        ]
        == "RECORD_PERSISTENCE_FAILURE"
    )


def test_success_result_exposes_hashes_not_evaluator_payload(
    tmp_path,
):
    _data, result = _run_success(
        tmp_path
    )

    assert result.treatment_batch_sha256
    assert result.evaluation_sha256
    assert result.execution_record_sha256

    assert not hasattr(
        result,
        "evaluation",
    )

    assert not hasattr(
        result,
        "hidden_truth_by_case",
    )

    assert not hasattr(
        result,
        "registered_criteria",
    )


def test_failure_categories_are_frozen():
    assert (
        persistence
        .EXECUTION_INVALIDATION_CATEGORIES
    ) == (
        "SETUP_FAILURE",
        "INPUT_BINDING_FAILURE",
        "TREATMENT_EXECUTION_FAILURE",
        "TREATMENT_PERSISTENCE_FAILURE",
        "EVALUATION_FAILURE",
        "EVALUATION_PERSISTENCE_FAILURE",
        "RECORD_PERSISTENCE_FAILURE",
        "FINALIZATION_FAILURE",
        "UNKNOWN_OPERATIONAL_FAILURE",
    )


def test_persistence_source_uses_exclusive_claim_and_atomic_helpers():
    source = Path(
        "packages/engines/behavioral/"
        "h1_controlled_active_diagnosis_protected_execution_persistence.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "os.mkdir(\n            attempt_directory"
        in source
    )

    assert "_atomic_write_new" in source
    assert "_atomic_replace" in source
    assert "_fsync_directory" in source
    assert "FileExistsError" in source


def test_cli_has_fixed_attempt_confirmation_and_persistence_binding():
    source = Path(
        "scripts/"
        "run_h1_controlled_active_diagnosis_protected.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        'BATCH_ID = "protected_v1"'
        in source
    )

    assert (
        'ATTEMPT_ID = "execution_v1"'
        in source
    )

    assert (
        "EXECUTE_P09_3_H1_PROTECTED_V1_ONCE"
        in source
    )

    assert (
        "sys.path.insert"
        in source
    )

    persistence_sha = hashlib.sha256(
        Path(
            "packages/engines/behavioral/"
            "h1_controlled_active_diagnosis_protected_execution_persistence.py"
        ).read_bytes()
    ).hexdigest()

    assert (
        persistence_sha
        in source
    )


def test_cli_wrong_confirmation_fails_before_repository_or_artifact_access():
    command = Path(
        "scripts/"
        "run_h1_controlled_active_diagnosis_protected.py"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(command),
            "--expected-head",
            "0" * 40,
            "--confirm",
            "WRONG_CONFIRMATION",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "protected-execution confirmation phrase "
        "does not match"
        in combined
    )


def test_cli_help_is_side_effect_free_at_argument_layer():
    command = Path(
        "scripts/"
        "run_h1_controlled_active_diagnosis_protected.py"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(command),
            "--help",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0

    assert (
        "One-shot P09.3 H1 protected execution"
        in result.stdout
    )


def test_cli_main_guard_and_single_persistence_invocation():
    path = Path(
        "scripts/"
        "run_h1_controlled_active_diagnosis_protected.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        ),
        filename=str(path),
    )

    calls = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "persist_h1_protected_execution_attempt"
        )
    ]

    assert len(calls) == 1

    guards = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.If,
        )
    ]

    assert any(
        isinstance(
            node.test,
            ast.Compare,
        )
        and isinstance(
            node.test.left,
            ast.Name,
        )
        and node.test.left.id
        == "__name__"
        for node in guards
    )


def test_success_evaluation_contains_registered_criteria_only_evaluator_side(
    tmp_path,
):
    data, _result = _run_success(
        tmp_path
    )

    attempt = (
        data["batch_directory"]
        / "execution_v1"
    )

    evaluation = _read_json(
        attempt
        / "evaluator"
        / "evaluation.json"
    )

    treatment = _read_json(
        attempt
        / "public"
        / "treatment_batch.json"
    )

    assert (
        "registered_criteria"
        in evaluation
    )

    assert (
        "registered_criteria"
        not in treatment
    )
