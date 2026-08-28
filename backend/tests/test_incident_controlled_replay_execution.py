from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.incident_controlled_replay_execution as execution
from app.incident_environment_materialization_execution import (
    IncidentRunnerMaterializedContext,
)
from app.runner_config import LocalRunnerSettings
from app.speech import TranscriptionResult
from hvee.core.incident_controlled_replay import (
    IncidentControlledReplayBundle,
)


class _Control:
    def __init__(self):
        self.calls = 0

    def raise_if_stopped(self):
        self.calls += 1


def _settings(**overrides):
    values = {
        "HETREN_RUNNER_CREDENTIAL": (
            "runner-test-credential"
        ),
        "HETREN_RUNNER_CAPABILITIES": [
            "asr",
            "incident_materialization",
            "incident_replay",
        ],
        "HETREN_RUNNER_ASR_PROVIDER": (
            "mock_local"
        ),
        "HETREN_RUNNER_ASR_MODEL": (
            "mock-model"
        ),
    }

    values.update(overrides)

    return LocalRunnerSettings(
        _env_file=None,
        **values,
    )


def _audio_bytes():
    return b"incident-replay-audio"


def _audio_sha():
    return hashlib.sha256(
        _audio_bytes()
    ).hexdigest()


def _preparation(
    *,
    transport=False,
):
    receipts = [
        {
            "kind": "source_audio",
            "reference_sha256": _audio_sha(),
            "expected_byte_length": len(
                _audio_bytes()
            ),
            "media_type": "audio/wav",
            "observed_sha256": _audio_sha(),
            "observed_byte_length": len(
                _audio_bytes()
            ),
            "status": "verified",
        }
    ]

    operations = [
        "verify_intake_commitment",
        "verify_artifact_manifest",
        "restore_runtime_context",
        "restore_audio_context",
        "restore_transport_context",
        "stage_source_audio",
    ]

    if transport:
        trace = b"trace"

        receipts.append(
            {
                "kind": "transport_trace",
                "reference_sha256": (
                    hashlib.sha256(
                        trace
                    ).hexdigest()
                ),
                "expected_byte_length": len(
                    trace
                ),
                "media_type": (
                    "application/octet-stream"
                ),
                "observed_sha256": (
                    hashlib.sha256(
                        trace
                    ).hexdigest()
                ),
                "observed_byte_length": len(
                    trace
                ),
                "status": "verified",
            }
        )

        operations.append(
            "stage_transport_trace"
        )

    operations.extend(
        [
            "execute_isolated_replay",
            "capture_replay_output",
            "compare_behavior_commitments",
        ]
    )

    return {
        "artifact_verification": {
            "all_referenced_artifacts_verified": True,
            "runner_custody_status": "verified",
            "receipts": receipts,
        },
        "replay_plan": {
            "execution_started": False,
            "steps": [
                {
                    "ordinal": index,
                    "operation": operation,
                    "input_commitment_sha256s": [
                        "9" * 64
                    ],
                    "status": "planned",
                }
                for index, operation in enumerate(
                    operations,
                    start=1,
                )
            ],
        },
    }


def _materialized_context():
    return IncidentRunnerMaterializedContext(
        audio={
            "codec": {
                "name": "wav",
            },
        },
        transport={
            "kind": "offline",
        },
    )


def _artifact_provider(
    requirement,
    control,
):
    if requirement.kind == "source_audio":
        return execution.IncidentReplayArtifact(
            requirement=requirement,
            data=_audio_bytes(),
        )

    if requirement.kind == "transport_trace":
        return execution.IncidentReplayArtifact(
            requirement=requirement,
            data=b"trace",
        )

    raise AssertionError(
        "unexpected artifact"
    )


class _Adapter:
    def __init__(self):
        self.paths = []
        self.exists_during_execution = []

    def execute(
        self,
        *,
        source_audio_path,
        transport_trace_path,
        model_name,
        control,
    ):
        self.paths.append(
            (
                source_audio_path,
                transport_trace_path,
            )
        )

        self.exists_during_execution.append(
            source_audio_path.exists()
        )

        assert source_audio_path.read_bytes() == (
            _audio_bytes()
        )

        assert model_name == "mock-model"

        return TranscriptionResult(
            transcript="controlled replay output",
            provider="mock_local",
            model_name="mock-model",
            device="cpu",
            compute_type="float32",
        )


def _run_kwargs(
    *,
    preparation=None,
    artifact_provider=_artifact_provider,
    context_provider=None,
    adapter=None,
):
    return {
        "intake_payload": {
            "evaluation_type": "asr",
            "incident": {
                "key": "incident-1",
                "version": "1",
            },
        },
        "expected_intake_sha256": "a" * 64,
        "replay_preparation_payload": (
            preparation or _preparation()
        ),
        "expected_replay_preparation_sha256": (
            "b" * 64
        ),
        "environment_manifest_payload": {
            "type": "incident_environment_manifest",
        },
        "expected_environment_manifest_sha256": (
            "c" * 64
        ),
        "runner_compatibility_payload": {
            "type": "incident_runner_compatibility",
        },
        "expected_runner_compatibility_sha256": (
            "d" * 64
        ),
        "environment_materialization_payload": {
            "materialization": {
                "status": "materialized",
                "environment_materialized": True,
            },
            "evidence_boundary": {
                "operator_authorization_granted": True,
                "environment_materialized": True,
            },
        },
        "expected_environment_materialization_sha256": (
            "e" * 64
        ),
        "settings": _settings(),
        "artifact_provider": (
            artifact_provider
        ),
        "materialized_context_provider": (
            context_provider
            or (
                lambda control: (
                    _materialized_context()
                )
            )
        ),
        "replay_adapter": (
            adapter or _Adapter()
        ),
        "control": _Control(),
    }


@pytest.fixture(autouse=True)
def stub_controlled_replay_builder(
    monkeypatch,
):
    captured = {}
    monkeypatch.setattr(
        execution,
        "verify_incident_environment_materialization_bundle",
        lambda **kwargs: True,
    )


    def fake_build(**kwargs):
        captured.clear()
        captured.update(kwargs)

        return IncidentControlledReplayBundle(
            payload={
                "execution": {
                    "status": "executed",
                },
                "evidence_boundary": {
                    "replay_executed": True,
                    "behavior_commitments_compared": False,
                    "reproduction_claimed": False,
                },
            },
            sha256="f" * 64,
        )

    monkeypatch.setattr(
        execution,
        "build_incident_controlled_replay_bundle",
        fake_build,
    )

    return captured


def test_replay_reverifies_local_artifact_bytes(
    stub_controlled_replay_builder,
):
    result = (
        execution
        .execute_incident_controlled_replay(
            **_run_kwargs()
        )
    )

    observation = (
        stub_controlled_replay_builder[
            "execution_observation"
        ]
    )

    artifact = observation.artifacts[0]

    assert artifact.observed_sha256 == (
        _audio_sha()
    )

    assert artifact.observed_byte_length == (
        len(_audio_bytes())
    )

    assert result.bundle.sha256 == (
        "f" * 64
    )


def test_same_length_corrupted_artifact_never_reaches_adapter():
    corrupted = b"X" * len(
        _audio_bytes()
    )

    adapter = _Adapter()

    def provider(
        requirement,
        control,
    ):
        return execution.IncidentReplayArtifact(
            requirement=requirement,
            data=corrupted,
        )

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="digest or byte-length",
    ):
        execution.execute_incident_controlled_replay(
            **_run_kwargs(
                artifact_provider=provider,
                adapter=adapter,
            )
        )

    assert adapter.paths == []


def test_wrong_length_artifact_never_reaches_adapter():
    adapter = _Adapter()

    def provider(
        requirement,
        control,
    ):
        return execution.IncidentReplayArtifact(
            requirement=requirement,
            data=_audio_bytes() + b"x",
        )

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="digest or byte-length",
    ):
        execution.execute_incident_controlled_replay(
            **_run_kwargs(
                artifact_provider=provider,
                adapter=adapter,
            )
        )

    assert adapter.paths == []


def test_wrong_artifact_identity_is_rejected():
    def provider(
        requirement,
        control,
    ):
        wrong = (
            execution
            .IncidentReplayArtifactRequirement(
                kind=requirement.kind,
                reference_sha256="1" * 64,
                expected_byte_length=(
                    requirement
                    .expected_byte_length
                ),
                media_type=(
                    requirement.media_type
                ),
            )
        )

        return execution.IncidentReplayArtifact(
            requirement=wrong,
            data=_audio_bytes(),
        )

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="wrong artifact",
    ):
        execution.execute_incident_controlled_replay(
            **_run_kwargs(
                artifact_provider=provider
            )
        )


def test_raw_transcript_is_reduced_to_commitment(
    stub_controlled_replay_builder,
):
    execution.execute_incident_controlled_replay(
        **_run_kwargs()
    )

    observation = (
        stub_controlled_replay_builder[
            "execution_observation"
        ]
    )

    assert (
        observation.output
        .generated_transcript_sha256
        == hashlib.sha256(
            b"controlled replay output"
        ).hexdigest()
    )

    assert (
        observation.output
        .generated_transcript_utf8_bytes
        == len(
            b"controlled replay output"
        )
    )

    assert not hasattr(
        observation.output,
        "transcript",
    )


def test_temporary_workspace_is_removed_after_execution():
    adapter = _Adapter()

    execution.execute_incident_controlled_replay(
        **_run_kwargs(
            adapter=adapter
        )
    )

    assert adapter.exists_during_execution == [
        True
    ]

    source_path = adapter.paths[0][0]

    assert not source_path.exists()
    assert not source_path.parent.exists()


def test_control_is_checked_around_execution():
    control = _Control()

    kwargs = _run_kwargs()
    kwargs["control"] = control

    execution.execute_incident_controlled_replay(
        **kwargs
    )

    assert control.calls >= 6


def test_materialized_context_is_required():
    kwargs = _run_kwargs()
    kwargs["materialized_context_provider"] = None

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="materialized context provider",
    ):
        execution.execute_incident_controlled_replay(
            **kwargs
        )

def test_invalid_materialized_context_is_rejected():
    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="invalid value",
    ):
        execution.execute_incident_controlled_replay(
            **_run_kwargs(
                context_provider=(
                    lambda control: {
                        "audio": {}
                    }
                )
            )
        )


def test_provider_identity_drift_is_rejected():
    class Adapter:
        def execute(
            self,
            **kwargs,
        ):
            return TranscriptionResult(
                transcript="hello",
                provider="faster_whisper",
                model_name="mock-model",
            )

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="provider identity changed",
    ):
        execution.execute_incident_controlled_replay(
            **_run_kwargs(
                adapter=Adapter()
            )
        )


def test_model_identity_drift_is_rejected():
    class Adapter:
        def execute(
            self,
            **kwargs,
        ):
            return TranscriptionResult(
                transcript="hello",
                provider="mock_local",
                model_name="other-model",
            )

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="model identity changed",
    ):
        execution.execute_incident_controlled_replay(
            **_run_kwargs(
                adapter=Adapter()
            )
        )


def test_basic_asr_adapter_refuses_transport_trace():
    class Provider:
        provider_name = "mock_local"

        def transcribe(
            self,
            audio_path,
            model_name=None,
        ):
            raise AssertionError(
                "provider must not run "
                "when trace is required"
            )

    adapter = (
        execution
        .ASRProviderIncidentReplayAdapter(
            Provider()
        )
    )

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="cannot apply a transport trace",
    ):
        execution.execute_incident_controlled_replay(
            **_run_kwargs(
                preparation=_preparation(
                    transport=True
                ),
                adapter=adapter,
            )
        )


def test_basic_asr_adapter_checks_control_before_and_after_transcription():
    events = []

    class Control:
        def raise_if_stopped(self):
            events.append("control")

    class Provider:
        provider_name = "mock_local"

        def transcribe(
            self,
            audio_path,
            model_name=None,
        ):
            events.append("transcribe")

            return TranscriptionResult(
                transcript="hello",
                provider="mock_local",
                model_name="mock-model",
            )

    adapter = (
        execution
        .ASRProviderIncidentReplayAdapter(
            Provider()
        )
    )

    with TemporaryDirectoryForTest() as path:
        result = adapter.execute(
            source_audio_path=path,
            transport_trace_path=None,
            model_name="mock-model",
            control=Control(),
        )

    assert result.transcript == "hello"

    assert events == [
        "control",
        "transcribe",
        "control",
    ]


class TemporaryDirectoryForTest:
    def __enter__(self):
        self.path = Path(
            __file__
        )
        return self.path

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


def test_basic_asr_adapter_does_not_compare_behavior():
    source = (
        Path(__file__)
    )

    class Provider:
        provider_name = "mock_local"

        def transcribe(
            self,
            audio_path,
            model_name=None,
        ):
            return TranscriptionResult(
                transcript="hello",
                provider="mock_local",
                model_name="mock-model",
            )

    result = (
        execution
        .ASRProviderIncidentReplayAdapter(
            Provider()
        )
        .execute(
            source_audio_path=source,
            transport_trace_path=None,
            model_name="mock-model",
            control=_Control(),
        )
    )

    assert result.transcript == "hello"


def _runner_job():
    return SimpleNamespace(
        job_type="incident_controlled_replay",
        required_capabilities=[
            "asr",
            "incident_controlled_replay",
            "incident_materialization",
            "incident_replay",
        ],
        input_payload={
            "schema_version": 1,
            "type": "incident_controlled_replay_request",
            "evidence": {},
        },
    )


def test_runner_wrapper_returns_commitment_only_result(
    monkeypatch,
):
    request = SimpleNamespace(
        intake_payload={},
        intake_sha256="1" * 64,
        replay_preparation_payload={},
        replay_preparation_sha256="2" * 64,
        environment_manifest_payload={},
        environment_manifest_sha256="3" * 64,
        runner_compatibility_payload={},
        runner_compatibility_sha256="4" * 64,
        environment_materialization_payload={},
        environment_materialization_sha256="5" * 64,
    )

    monkeypatch.setattr(
        execution,
        "parse_incident_controlled_replay_request",
        lambda payload: request,
    )

    expected_bundle = (
        IncidentControlledReplayBundle(
            payload={
                "execution": {
                    "status": "executed",
                },
                "evidence_boundary": {
                    "replay_executed": True,
                    "reproduction_claimed": False,
                },
            },
            sha256="f" * 64,
        )
    )

    monkeypatch.setattr(
        execution,
        "execute_incident_controlled_replay",
        lambda **kwargs: (
            execution
            .IncidentControlledReplayExecutionResult(
                bundle=expected_bundle
            )
        ),
    )

    executor = (
        execution
        .IncidentControlledReplayRunnerJobExecutor(
            settings=_settings(),
            artifact_provider=_artifact_provider,
            materialized_context_provider=(
                lambda control: (
                    _materialized_context()
                )
            ),
            replay_adapter=_Adapter(),
        )
    )

    result = executor.execute(
        _runner_job(),
        _Control(),
    )

    assert result == {
        "schema_version": 1,
        "type": "incident_controlled_replay_result",
        "controlled_replay": {
            "payload": expected_bundle.payload,
            "sha256": expected_bundle.sha256,
        },
    }

    serialized = str(result)

    assert "controlled replay output" not in serialized


def test_default_runner_wrapper_fails_without_local_providers():
    executor = (
        execution
        .IncidentControlledReplayRunnerJobExecutor(
            settings=_settings(),
        )
    )

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="artifact provider is unavailable",
    ):
        executor.execute(
            _runner_job(),
            _Control(),
        )


def test_runner_wrapper_rejects_modified_scheduler_capabilities():
    job = _runner_job()

    job.required_capabilities = [
        "asr",
        "incident_replay",
    ]

    executor = (
        execution
        .IncidentControlledReplayRunnerJobExecutor(
            settings=_settings(),
        )
    )

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="capability contract is invalid",
    ):
        executor.execute(
            job,
            _Control(),
        )


def test_unverified_materialization_blocks_before_artifact_access(
    monkeypatch,
):
    artifact_calls = []
    adapter = _Adapter()

    def provider(
        requirement,
        control,
    ):
        artifact_calls.append(
            requirement
        )

        return execution.IncidentReplayArtifact(
            requirement=requirement,
            data=_audio_bytes(),
        )

    monkeypatch.setattr(
        execution,
        "verify_incident_environment_materialization_bundle",
        lambda **kwargs: False,
    )

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="requires verified environment materialization",
    ):
        execution.execute_incident_controlled_replay(
            **_run_kwargs(
                artifact_provider=provider,
                adapter=adapter,
            )
        )

    assert artifact_calls == []
    assert adapter.paths == []


def test_blocked_materialization_cannot_execute_even_when_signature_verifies(
    monkeypatch,
):
    artifact_calls = []
    adapter = _Adapter()

    def provider(
        requirement,
        control,
    ):
        artifact_calls.append(
            requirement
        )

        return execution.IncidentReplayArtifact(
            requirement=requirement,
            data=_audio_bytes(),
        )

    monkeypatch.setattr(
        execution,
        "verify_incident_environment_materialization_bundle",
        lambda **kwargs: True,
    )

    kwargs = _run_kwargs(
        artifact_provider=provider,
        adapter=adapter,
    )

    kwargs[
        "environment_materialization_payload"
    ] = {
        "materialization": {
            "status": "blocked_compatibility",
            "environment_materialized": False,
        },
        "evidence_boundary": {
            "operator_authorization_granted": True,
            "environment_materialized": False,
        },
    }

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="requires a materialized environment",
    ):
        execution.execute_incident_controlled_replay(
            **kwargs
        )

    assert artifact_calls == []
    assert adapter.paths == []


def test_missing_operator_authorization_blocks_before_artifact_access(
    monkeypatch,
):
    artifact_calls = []
    adapter = _Adapter()

    def provider(
        requirement,
        control,
    ):
        artifact_calls.append(
            requirement
        )

        return execution.IncidentReplayArtifact(
            requirement=requirement,
            data=_audio_bytes(),
        )

    monkeypatch.setattr(
        execution,
        "verify_incident_environment_materialization_bundle",
        lambda **kwargs: True,
    )

    kwargs = _run_kwargs(
        artifact_provider=provider,
        adapter=adapter,
    )

    kwargs[
        "environment_materialization_payload"
    ] = {
        "materialization": {
            "status": "materialized",
            "environment_materialized": True,
        },
        "evidence_boundary": {
            "operator_authorization_granted": False,
            "environment_materialized": True,
        },
    }

    with pytest.raises(
        execution.IncidentControlledReplayExecutionError,
        match="requires authorized materialization evidence",
    ):
        execution.execute_incident_controlled_replay(
            **kwargs
        )

    assert artifact_calls == []
    assert adapter.paths == []
