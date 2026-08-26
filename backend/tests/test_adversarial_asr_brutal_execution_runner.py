from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

import app.adversarial_asr_brutal_execution_runner as runner_module
from app.adversarial_asr_brutal_campaign import (
    ASRBrutalValidationSuiteBundle,
    ASR_BRUTAL_VALIDATION_MEDIA_V1,
    build_asr_brutal_validation_suite_v1,
)
from app.adversarial_asr_brutal_execution_runner import (
    ASRBrutalExecutionRunnerError,
    ASR_BRUTAL_FROZEN_MODELS_V1,
    _canonical_json_bytes,
    _write_bundle,
    execute_asr_brutal_validation_run_v1,
)


_REPOSITORY_COMMIT = (
    "6c099e7829791a497afde821a41ce7644df29397"
)


def _bundle() -> ASRBrutalValidationSuiteBundle:
    suite, evidence = build_asr_brutal_validation_suite_v1()
    audio_paths = MappingProxyType(
        {
            case.case_id: Path(f"/{case.case_id}.wav")
            for case in suite.cases
        }
    )
    return ASRBrutalValidationSuiteBundle(
        suite=suite,
        suite_evidence=evidence,
        audio_paths=audio_paths,
    )


def _model_identity(model) -> dict[str, object]:
    return {
        "role": model.role,
        "model_name": model.model_name,
        "repository": model.repository,
        "revision": model.revision,
        "model_binary_bytes": model.model_binary_bytes,
        "model_binary_sha256": model.model_binary_sha256,
        "resolved_offline": True,
    }


def _campaign_payload(
    *,
    role,
    repository_commit,
    model_identity,
    result,
    bundle,
):
    del result
    completed_count = 13
    return {
        "role": role,
        "repository_commit": repository_commit,
        "model_identity": model_identity,
        "campaign_evidence": {
            "payload": {
                "campaign": {
                    "status_counts": {
                        "completed": completed_count,
                    },
                },
            },
            "sha256": role[0] * 64,
        },
        "completed_results": [
            {
                "case_id": case.case_id,
            }
            for case in bundle.suite.cases[:completed_count]
        ],
    }


def test_frozen_model_identities_are_exact():
    assert tuple(
        (
            model.role,
            model.model_name,
            model.repository,
            model.revision,
            model.model_binary_bytes,
            model.model_binary_sha256,
        )
        for model in ASR_BRUTAL_FROZEN_MODELS_V1
    ) == (
        (
            "baseline",
            "small.en",
            "Systran/faster-whisper-small.en",
            "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
            483_545_366,
            (
                "62b2a45b05ee59acb4a5341b33ee35e0"
                "41395d378d418a18acfe4c9e768ee37a"
            ),
        ),
        (
            "candidate",
            "large-v3-turbo",
            "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
            "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
            1_617_884_929,
            (
                "e76620f83d5f5b69efd3d87e3dc180c1"
                "bd21df9fbebacfd4335e5e1efcc018da"
            ),
        ),
    )


def test_atomic_bundle_is_hashed_and_refuses_overwrite(
    tmp_path: Path,
):
    path = tmp_path / "evidence.json"
    payload = {
        "artifact": "runner-test",
        "value": 39,
    }

    observed_sha256 = _write_bundle(path, payload)
    document = json.loads(path.read_text(encoding="utf-8"))
    expected_sha256 = hashlib.sha256(
        _canonical_json_bytes(payload)
    ).hexdigest()

    assert observed_sha256 == expected_sha256
    assert document == {
        "payload": payload,
        "sha256": expected_sha256,
    }

    with pytest.raises(
        ASRBrutalExecutionRunnerError,
        match="Evidence output already exists",
    ):
        _write_bundle(path, payload)


@pytest.mark.parametrize(
    "repository_commit",
    (
        "",
        "abc123",
        "A" * 40,
        " " + ("0" * 40),
        ("0" * 40) + "\n",
        "0" * 39,
        "0" * 41,
    ),
)
def test_invalid_commit_is_rejected_before_model_verification(
    tmp_path: Path,
    repository_commit: str,
):
    verifier_calls = []

    def forbidden_verifier(model):
        verifier_calls.append(model)
        raise AssertionError("Model verification must not run")

    with pytest.raises(
        ASRBrutalExecutionRunnerError,
        match="full lowercase Git SHA",
    ):
        execute_asr_brutal_validation_run_v1(
            bundle=_bundle(),
            output_root=tmp_path / "evidence",
            repository_root=tmp_path,
            repository_commit=repository_commit,
            model_verifier=forbidden_verifier,
        )

    assert verifier_calls == []
    assert not (tmp_path / "evidence").exists()


def test_repository_output_is_rejected_before_provider_creation(
    tmp_path: Path,
):
    provider_calls = []

    def forbidden_provider(*args, **kwargs):
        provider_calls.append((args, kwargs))
        raise AssertionError("Provider must not be created")

    with pytest.raises(
        ASRBrutalExecutionRunnerError,
        match="outside the repository",
    ):
        execute_asr_brutal_validation_run_v1(
            bundle=_bundle(),
            output_root=tmp_path / "inside-repository",
            repository_root=tmp_path,
            repository_commit=_REPOSITORY_COMMIT,
            provider_factory=forbidden_provider,
            model_verifier=_model_identity,
        )

    assert provider_calls == []
    assert not (tmp_path / "inside-repository").exists()


def test_substituted_case_is_rejected_before_model_verification(
    tmp_path: Path,
):
    case_ids = sorted(
        identity.case_id
        for identity in ASR_BRUTAL_VALIDATION_MEDIA_V1
    )
    case_ids[-1] = "brutal.substituted.invalid-case"
    bundle = SimpleNamespace(
        suite=SimpleNamespace(
            cases=tuple(
                SimpleNamespace(
                    case_id=case_id,
                    reference_transcript=(
                        f"reference transcript for {case_id}"
                    ),
                )
                for case_id in case_ids
            ),
        ),
        suite_evidence=SimpleNamespace(
            sha256="a" * 64,
        ),
    )
    verifier_calls = []

    def forbidden_verifier(model):
        verifier_calls.append(model)
        raise AssertionError("Model verification must not run")

    with pytest.raises(
        ASRBrutalExecutionRunnerError,
        match="exact ordered 13-case",
    ):
        execute_asr_brutal_validation_run_v1(
            bundle=bundle,
            output_root=tmp_path / "evidence",
            repository_root=tmp_path,
            repository_commit=_REPOSITORY_COMMIT,
            model_verifier=forbidden_verifier,
        )

    assert verifier_calls == []
    assert not (tmp_path / "evidence").exists()


def test_two_model_run_persists_complete_evidence(
    monkeypatch,
    tmp_path: Path,
):
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    output_root = tmp_path / "evidence"
    bundle = _bundle()
    provider_calls = []
    campaign_calls = []

    def fake_provider(provider_name, **configuration):
        provider_calls.append(
            {
                "provider_name": provider_name,
                **configuration,
            }
        )
        return SimpleNamespace(
            model_name=configuration["model_name"],
        )

    def fake_campaign(**arguments):
        campaign_calls.append(
            {
                "campaign_id": arguments["campaign_id"],
                "requested_model_name": (
                    arguments["requested_model_name"]
                ),
            }
        )
        return SimpleNamespace()

    monkeypatch.setattr(
        runner_module,
        "_campaign_payload",
        _campaign_payload,
    )

    result = execute_asr_brutal_validation_run_v1(
        bundle=bundle,
        output_root=output_root,
        repository_root=repository_root,
        repository_commit=_REPOSITORY_COMMIT,
        provider_factory=fake_provider,
        model_verifier=_model_identity,
        campaign_executor=fake_campaign,
    )

    assert result.status == "completed"
    assert result.output_root == output_root.resolve()
    assert sorted(path.name for path in output_root.iterdir()) == [
        "baseline.campaign.json",
        "candidate.campaign.json",
        "preflight.json",
        "summary.json",
    ]
    assert [
        call["model_name"]
        for call in provider_calls
    ] == [
        "small.en",
        "large-v3-turbo",
    ]
    assert [
        call["requested_model_name"]
        for call in campaign_calls
    ] == [
        "small.en",
        "large-v3-turbo",
    ]

    preflight = json.loads(
        (output_root / "preflight.json").read_text(
            encoding="utf-8",
        )
    )["payload"]
    summary_document = json.loads(
        (output_root / "summary.json").read_text(
            encoding="utf-8",
        )
    )
    summary = summary_document["payload"]

    assert preflight["execution_boundary"] == {
        "asr_execution_started": False,
        "transcription_performed": False,
        "development_evidence_only": True,
        "qualification_threshold_applied": False,
        "production_qualified": False,
    }
    assert summary["status"] == "completed"
    assert summary["case_count"] == 13
    assert len(summary["models"]) == 2
    assert all(
        model["completed_case_count"] == 13
        for model in summary["models"]
    )
    assert summary["evidence_boundary"] == {
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
    }
    assert summary_document["sha256"] == hashlib.sha256(
        _canonical_json_bytes(summary)
    ).hexdigest()
    assert result.sha256 == summary_document["sha256"]
    assert not (output_root / "fatal.json").exists()


def test_candidate_failure_preserves_baseline_and_fatal_evidence(
    monkeypatch,
    tmp_path: Path,
):
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    output_root = tmp_path / "evidence"

    def fake_provider(provider_name, **configuration):
        return SimpleNamespace(
            provider_name=provider_name,
            model_name=configuration["model_name"],
        )

    def failing_campaign(**arguments):
        if arguments["requested_model_name"] == "large-v3-turbo":
            raise RuntimeError("candidate campaign failed")
        return SimpleNamespace()

    monkeypatch.setattr(
        runner_module,
        "_campaign_payload",
        _campaign_payload,
    )

    with pytest.raises(
        RuntimeError,
        match="candidate campaign failed",
    ):
        execute_asr_brutal_validation_run_v1(
            bundle=_bundle(),
            output_root=output_root,
            repository_root=repository_root,
            repository_commit=_REPOSITORY_COMMIT,
            provider_factory=fake_provider,
            model_verifier=_model_identity,
            campaign_executor=failing_campaign,
        )

    assert sorted(path.name for path in output_root.iterdir()) == [
        "baseline.campaign.json",
        "fatal.json",
        "preflight.json",
    ]
    assert not (output_root / "candidate.campaign.json").exists()
    assert not (output_root / "summary.json").exists()

    fatal_document = json.loads(
        (output_root / "fatal.json").read_text(
            encoding="utf-8",
        )
    )
    fatal = fatal_document["payload"]

    assert fatal["artifact"]["type"] == (
        "brutal_execution_fatal_outcome"
    )
    assert fatal["error"] == {
        "type": "RuntimeError",
        "detail": "candidate campaign failed",
    }
    assert len(fatal["completed_model_artifacts"]) == 1
    assert fatal["completed_model_artifacts"][0]["role"] == (
        "baseline"
    )
    assert fatal["completed_model_artifacts"][0][
        "completed_case_count"
    ] == 13
    assert fatal["development_evidence_only"] is True
    assert fatal_document["sha256"] == hashlib.sha256(
        _canonical_json_bytes(fatal)
    ).hexdigest()


def test_incomplete_candidate_is_reported_as_partial(
    monkeypatch,
    tmp_path: Path,
):
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    output_root = tmp_path / "evidence"

    def fake_provider(provider_name, **configuration):
        return SimpleNamespace(
            provider_name=provider_name,
            model_name=configuration["model_name"],
        )

    def fake_campaign(**arguments):
        del arguments
        return SimpleNamespace()

    def partial_campaign_payload(**arguments):
        payload = _campaign_payload(**arguments)
        if arguments["role"] == "candidate":
            payload["completed_results"] = payload[
                "completed_results"
            ][:-1]
            payload["campaign_evidence"]["payload"][
                "campaign"
            ]["status_counts"] = {
                "completed": 12,
                "failed": 1,
            }
        return payload

    monkeypatch.setattr(
        runner_module,
        "_campaign_payload",
        partial_campaign_payload,
    )

    result = execute_asr_brutal_validation_run_v1(
        bundle=_bundle(),
        output_root=output_root,
        repository_root=repository_root,
        repository_commit=_REPOSITORY_COMMIT,
        provider_factory=fake_provider,
        model_verifier=_model_identity,
        campaign_executor=fake_campaign,
    )

    assert result.status == "partial"
    assert [
        model["completed_case_count"]
        for model in result.payload["models"]
    ] == [13, 12]
    assert result.payload["evidence_boundary"][
        "partial_outcomes_preserved"
    ] is True
    assert result.payload["evidence_boundary"][
        "model_winner_declared"
    ] is False
    assert result.payload["evidence_boundary"][
        "production_qualified"
    ] is False
    assert not (output_root / "fatal.json").exists()
