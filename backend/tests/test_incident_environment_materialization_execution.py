from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.incident_environment_materialization_execution as execution
from app.incident_runner_compatibility_service import (
    IncidentReplayCompatibilityRequest,
)
from app.runner_config import LocalRunnerSettings
from hvee.core.contracts import HveeContractError
from hvee.core.incident_environment_materialization import (
    calculate_incident_materialized_value_commitment,
)
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerCompatibilityBundle,
)


def _sha(value: str) -> str:
    return value * 64


def _settings(**overrides) -> LocalRunnerSettings:
    values = {
        "OVRIN_RUNNER_CREDENTIAL": (
            "runner-test-credential"
        ),
        "OVRIN_RUNNER_CAPABILITIES": [
            "incident_replay",
            "asr",
        ],
        "OVRIN_RUNNER_ASR_PROVIDER": (
            "faster_whisper"
        ),
        "OVRIN_RUNNER_ASR_MODEL": (
            "large-v3-turbo"
        ),
    }
    values.update(overrides)

    return LocalRunnerSettings(
        _env_file=None,
        **values,
    )


def _request() -> IncidentReplayCompatibilityRequest:
    return IncidentReplayCompatibilityRequest(
        intake_payload={
            "evaluation_type": "asr",
            "incident": {
                "key": "incident-1",
                "version": "1",
            },
            "context": {
                "audio": {
                    "codec": {
                        "name": "opus",
                        "profile": "fullband",
                    },
                },
                "transport": {
                    "kind": "webrtc",
                },
            },
        },
        intake_sha256=_sha("1"),
        replay_preparation_payload={
            "type": "preparation",
        },
        replay_preparation_sha256=_sha("2"),
        environment_manifest_payload={
            "type": "manifest",
        },
        environment_manifest_sha256=_sha("3"),
    )


def _compatibility() -> IncidentRunnerCompatibilityBundle:
    return IncidentRunnerCompatibilityBundle(
        payload={
            "compatibility": {
                "status": "exact",
                "ready_for_materialization": True,
                "requirements": [
                    {
                        "requirement": (
                            "audio.codec_name"
                        ),
                        "level": "exact",
                        "expected_commitment_sha256": (
                            _sha("4")
                        ),
                        "observed_commitment_sha256": (
                            _sha("4")
                        ),
                    },
                    {
                        "requirement": (
                            "runtime.source_code_sha256"
                        ),
                        "level": "exact",
                        "expected_commitment_sha256": (
                            _sha("5")
                        ),
                        "observed_commitment_sha256": (
                            _sha("5")
                        ),
                    },
                    {
                        "requirement": (
                            "transport.kind"
                        ),
                        "level": "exact",
                        "expected_commitment_sha256": (
                            _sha("6")
                        ),
                        "observed_commitment_sha256": (
                            _sha("6")
                        ),
                    },
                ],
            },
        },
        sha256=_sha("a"),
    )


def _materialized_context(
    *,
    codec_name: str = "opus",
    transport_kind: str = "webrtc",
):
    return (
        execution
        .IncidentRunnerMaterializedContext(
            audio={
                "codec": {
                    "name": codec_name,
                },
            },
            transport={
                "kind": transport_kind,
            },
        )
    )


def test_runtime_observation_uses_runner_local_identity():
    observation = (
        execution
        .build_incident_materialization_compatibility_observation(
            _settings(
                HETREN_RUNNER_INCIDENT_DEPLOYMENT_KEY=(
                    "prod-us"
                ),
                HETREN_RUNNER_INCIDENT_DEPLOYMENT_VERSION=(
                    "2026.08"
                ),
                HETREN_RUNNER_INCIDENT_PROVIDER_VERSION=(
                    "1.1.0"
                ),
                HETREN_RUNNER_INCIDENT_MODEL_VERSION=(
                    "v3"
                ),
                HETREN_RUNNER_INCIDENT_MODEL_ARTIFACT_SHA256=(
                    _sha("1")
                ),
                HETREN_RUNNER_INCIDENT_SOURCE_CODE_SHA256=(
                    _sha("2")
                ),
                HETREN_RUNNER_INCIDENT_CONFIGURATION_SHA256=(
                    _sha("3")
                ),
                HETREN_RUNNER_INCIDENT_RUNTIME_ENVIRONMENT_SHA256=(
                    _sha("4")
                ),
                HETREN_RUNNER_INCIDENT_HOST_ENVIRONMENT_SHA256=(
                    _sha("5")
                ),
            )
        )
    )

    assert observation.capabilities == (
        "asr",
        "incident_replay",
    )
    assert observation.deployment_key == "prod-us"
    assert observation.provider_key == (
        "faster_whisper"
    )
    assert observation.model_key == (
        "large-v3-turbo"
    )
    assert observation.source_code_sha256 == (
        _sha("2")
    )

    assert (
        observation.exact_context_components
        == ()
    )


def test_settings_alone_cannot_claim_exact_context():
    observation = (
        execution
        .build_incident_materialization_compatibility_observation(
            _settings()
        )
    )

    assert (
        observation.exact_context_components
        == ()
    )


def test_actual_local_context_establishes_exact_components():
    observation = (
        execution
        .build_incident_materialization_compatibility_observation(
            _settings(),
            materialized_context=(
                _materialized_context()
            ),
        )
    )

    assert (
        observation.exact_context_components
        == (
            "audio",
            "transport",
        )
    )


def test_missing_runner_local_identity_stays_unobserved():
    observation = (
        execution
        .build_incident_materialization_compatibility_observation(
            _settings()
        )
    )

    assert observation.deployment_key is None
    assert observation.deployment_version is None
    assert observation.provider_version is None
    assert observation.model_version is None
    assert (
        observation.model_artifact_sha256
        is None
    )
    assert observation.source_code_sha256 is None
    assert observation.configuration_sha256 is None
    assert (
        observation.runtime_environment_sha256
        is None
    )
    assert (
        observation.host_environment_sha256
        is None
    )


def test_audio_commitment_comes_from_actual_local_context():
    observation = (
        execution
        .build_incident_materialization_compatibility_observation(
            _settings(),
            materialized_context=(
                _materialized_context(
                    codec_name="pcm_s16le"
                )
            ),
        )
    )

    values = (
        execution
        .build_incident_materialization_observations(
            compatibility=_compatibility(),
            compatibility_observation=(
                observation
            ),
            materialized_context=(
                _materialized_context(
                    codec_name="pcm_s16le"
                )
            ),
        )
    )

    by_requirement = {
        value.requirement: value
        for value in values
    }

    local_commitment = (
        calculate_incident_materialized_value_commitment(
            "pcm_s16le"
        )
    )

    expected_target_commitment = (
        calculate_incident_materialized_value_commitment(
            "opus"
        )
    )

    assert (
        by_requirement[
            "audio.codec_name"
        ].observed_commitment_sha256
        == local_commitment
    )

    assert (
        local_commitment
        != expected_target_commitment
    )


def test_incident_request_itself_cannot_substitute_for_local_context():
    observation = (
        execution
        .build_incident_materialization_compatibility_observation(
            _settings()
        )
    )

    values = (
        execution
        .build_incident_materialization_observations(
            compatibility=_compatibility(),
            compatibility_observation=(
                observation
            ),
            materialized_context=None,
        )
    )

    by_requirement = {
        value.requirement: value
        for value in values
    }

    assert (
        by_requirement[
            "audio.codec_name"
        ].observed_commitment_sha256
        is None
    )

    assert (
        by_requirement[
            "transport.kind"
        ].observed_commitment_sha256
        is None
    )


def test_runtime_commitment_comes_from_compatibility_observation():
    observation = (
        execution
        .build_incident_materialization_compatibility_observation(
            _settings()
        )
    )

    values = (
        execution
        .build_incident_materialization_observations(
            compatibility=_compatibility(),
            compatibility_observation=(
                observation
            ),
            materialized_context=None,
        )
    )

    source = next(
        value
        for value in values
        if value.requirement
        == "runtime.source_code_sha256"
    )

    assert (
        source.observed_commitment_sha256
        == _sha("5")
    )


def test_materialized_context_is_independent_from_source_mutation():
    source = {
        "codec": {
            "name": "opus",
        },
    }

    context = (
        execution
        .IncidentRunnerMaterializedContext(
            audio=source,
        )
    )

    source["codec"]["name"] = "mutated"

    assert (
        context.audio["codec"]["name"]
        == "opus"
    )


def test_non_json_materialized_context_is_rejected():
    with pytest.raises(
        HveeContractError,
    ):
        (
            execution
            .IncidentRunnerMaterializedContext(
                audio={
                    "invalid": object(),
                },
            )
        )


def test_materialization_authorization_is_runner_local(
    monkeypatch,
):
    request = _request()
    compatibility = _compatibility()

    monkeypatch.setattr(
        execution,
        "parse_incident_replay_compatibility_request",
        lambda payload: request,
    )

    monkeypatch.setattr(
        execution,
        "evaluate_incident_replay_compatibility_request",
        lambda **kwargs: compatibility,
    )

    captured = {}

    expected_materialization = SimpleNamespace(
        payload={
            "materialization": {
                "status": "materialized"
            }
        },
        sha256=_sha("b"),
    )

    def fake_build(**kwargs):
        captured.update(kwargs)
        return expected_materialization

    monkeypatch.setattr(
        execution,
        "build_incident_environment_materialization_bundle",
        fake_build,
    )

    result = (
        execution
        .materialize_incident_environment_request(
            request_payload={
                "request": "placeholder"
            },
            settings=_settings(
                HETREN_RUNNER_INCIDENT_MATERIALIZATION_AUTHORIZATION_SHA256=(
                    _sha("c")
                ),
            ),
            materialized_context=(
                _materialized_context()
            ),
        )
    )

    assert (
        result.compatibility
        is compatibility
    )

    assert (
        result.materialization
        is expected_materialization
    )

    authorization = captured[
        "authorization"
    ]

    assert authorization.granted is True
    assert (
        authorization.authorization_sha256
        == _sha("c")
    )


def test_missing_local_authorization_is_not_fabricated(
    monkeypatch,
):
    request = _request()
    compatibility = _compatibility()

    monkeypatch.setattr(
        execution,
        "parse_incident_replay_compatibility_request",
        lambda payload: request,
    )

    monkeypatch.setattr(
        execution,
        "evaluate_incident_replay_compatibility_request",
        lambda **kwargs: compatibility,
    )

    captured = {}

    def fake_build(**kwargs):
        captured.update(kwargs)

        return SimpleNamespace(
            payload={},
            sha256=_sha("d"),
        )

    monkeypatch.setattr(
        execution,
        "build_incident_environment_materialization_bundle",
        fake_build,
    )

    execution.materialize_incident_environment_request(
        request_payload={},
        settings=_settings(),
        materialized_context=None,
    )

    authorization = captured[
        "authorization"
    ]

    assert authorization.granted is False
    assert (
        authorization.authorization_sha256
        is None
    )


def test_invalid_incident_digest_setting_is_rejected():
    with pytest.raises(
        ValueError,
    ):
        _settings(
            HETREN_RUNNER_INCIDENT_SOURCE_CODE_SHA256=(
                "not-a-sha"
            ),
        )


class _ExecutionControl:
    def __init__(self):
        self.calls = 0

    def raise_if_stopped(self):
        self.calls += 1


def _materialization_job():
    return SimpleNamespace(
        job_type="incident_environment_materialization",
        required_capabilities=[
            "asr",
            "incident_materialization",
            "incident_replay",
        ],
        input_payload={
            "request": "target-only",
        },
    )


def test_materialization_runner_executor_uses_only_provider_context(
    monkeypatch,
):
    actual_context = _materialized_context(
        codec_name="pcm_s16le",
        transport_kind="rtp",
    )

    provider_calls = []

    def provider(job, control):
        provider_calls.append(job)
        return actual_context

    captured = {}

    compatibility = SimpleNamespace(
        payload={"compatibility": {"status": "exact"}},
        sha256=_sha("a"),
    )

    materialization = SimpleNamespace(
        payload={
            "materialization": {
                "status": "materialized",
                "environment_materialized": True,
            },
            "evidence_boundary": {
                "models_loaded": False,
                "replay_executed": False,
                "reproduction_claimed": False,
                "qualification_authority": False,
            },
        },
        sha256=_sha("b"),
    )

    def fake_materialize(**kwargs):
        captured.update(kwargs)

        return (
            execution
            .IncidentRunnerMaterializationResult(
                compatibility=compatibility,
                materialization=materialization,
            )
        )

    monkeypatch.setattr(
        execution,
        "materialize_incident_environment_request",
        fake_materialize,
    )

    executor = (
        execution
        .IncidentEnvironmentMaterializationRunnerJobExecutor(
            settings=_settings(),
            materialized_context_provider=provider,
        )
    )

    result = executor.execute(
        _materialization_job(),
        _ExecutionControl(),
    )

    assert provider_calls
    assert (
        captured["materialized_context"]
        is actual_context
    )

    assert result["materialization"]["sha256"] == (
        _sha("b")
    )

    serialized = str(result)

    assert "pcm_s16le" not in serialized
    assert "'rtp'" not in serialized


def test_default_materialization_executor_never_fabricates_context(
    monkeypatch,
):
    captured = {}

    compatibility = SimpleNamespace(
        payload={
            "compatibility": {
                "status": "blocked_unobserved"
            }
        },
        sha256=_sha("c"),
    )

    materialization = SimpleNamespace(
        payload={
            "materialization": {
                "status": "blocked_compatibility",
                "environment_materialized": False,
            }
        },
        sha256=_sha("d"),
    )

    def fake_materialize(**kwargs):
        captured.update(kwargs)

        return (
            execution
            .IncidentRunnerMaterializationResult(
                compatibility=compatibility,
                materialization=materialization,
            )
        )

    monkeypatch.setattr(
        execution,
        "materialize_incident_environment_request",
        fake_materialize,
    )

    executor = (
        execution
        .IncidentEnvironmentMaterializationRunnerJobExecutor(
            settings=_settings(),
        )
    )

    result = executor.execute(
        _materialization_job(),
        _ExecutionControl(),
    )

    assert captured["materialized_context"] is None

    assert (
        result["materialization"]["payload"][
            "materialization"
        ]["environment_materialized"]
        is False
    )


def test_materialization_executor_rejects_modified_capability_contract():
    job = _materialization_job()
    job.required_capabilities = [
        "asr",
        "incident_replay",
    ]

    executor = (
        execution
        .IncidentEnvironmentMaterializationRunnerJobExecutor(
            settings=_settings(),
        )
    )

    with pytest.raises(
        execution
        .IncidentEnvironmentMaterializationRunnerExecutionError,
        match="capability contract is invalid",
    ):
        executor.execute(
            job,
            _ExecutionControl(),
        )
