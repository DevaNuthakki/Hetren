"""The live recording path sends store=False, and live runs cannot omit it.

No network: the real SDK ``OpenAIResponsesModel`` is driven against a fake
client that captures the ``responses.create`` arguments and then stops.
"""

import asyncio
from functools import partial
from pathlib import Path
import socket

import pytest
from agents import Agent, ModelSettings, OpenAIResponsesModel

from environments.support.fixtures import SupportEnvironment
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.contracts import ContractError
from packages.integrations.openai_agents import (
    CaptureStore,
    RecordingModel,
    RunProvenance,
    RunStatus,
    gateway_function_tools,
    run_agent,
    run_manifest,
)
from packages.support_agent import ScriptedSupportModel, build_support_agent, task_message
from packages.support_agent.agent import MODEL_SETTINGS


REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_MODEL = "gpt-4.1-mini-2025-04-14"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


class StopAfterRequest(Exception):
    pass


class FakeResponses:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        raise StopAfterRequest("request captured")


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def _gateway(environment):
    return ToolGateway(
        tools=[
            GatedTool(
                name, partial(function, environment),
                SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name],
            )
            for name, function in SUPPORT_TOOLS.items()
        ],
        policy=AllowListPolicy(SUPPORT_TOOLS),
        state_sha256=environment.state_sha256,
    )


def test_agent_definition_sets_store_false():
    assert MODEL_SETTINGS.store is False
    agent = build_support_agent(
        environment=SupportEnvironment(), tools=[], model=ScriptedSupportModel(),
    )
    assert agent.model_settings.store is False


def test_live_recording_path_sends_store_false(tmp_path):
    """Same construction as scripts/record_support_captures.py, fake client."""
    environment = SupportEnvironment()
    gateway = _gateway(environment)
    client = FakeClient()
    model = RecordingModel(
        inner=OpenAIResponsesModel(model=LIVE_MODEL, openai_client=client),
        store=CaptureStore(tmp_path),
        source_provenance=RunProvenance.LIVE,
        source_model_id=LIVE_MODEL,
    )

    record = run_agent(
        agent=build_support_agent(
            environment=environment, tools=gateway_function_tools(gateway), model=model,
        ),
        task_input=task_message("T-1001"),
        gateway=gateway,
        run_id="run-0001",
        provenance=RunProvenance.LIVE,
    )

    (request,) = client.responses.requests
    assert request["store"] is False
    assert request["model"] == LIVE_MODEL
    assert record.status is RunStatus.ERROR
    assert record.error["type"] == "StopAfterRequest"
    assert record.model_settings == {"store": False}
    assert run_manifest(record)["store"] is False
    assert list(tmp_path.iterdir()) == []


def test_live_runs_without_store_false_are_refused(tmp_path):
    environment = SupportEnvironment()
    gateway = _gateway(environment)

    for settings in (ModelSettings(), ModelSettings(store=True)):
        agent = Agent(
            name="support-agent",
            instructions="Route the ticket.",
            tools=gateway_function_tools(gateway),
            model=LIVE_MODEL,
            model_settings=settings,
        )

        with pytest.raises(ContractError, match="store=False"):
            run_agent(
                agent=agent, task_input=task_message("T-1001"), gateway=gateway,
                run_id="run-0001", provenance=RunProvenance.LIVE,
            )


def test_recording_model_refuses_a_live_call_without_store_false(tmp_path):
    client = FakeClient()
    model = RecordingModel(
        inner=OpenAIResponsesModel(model=LIVE_MODEL, openai_client=client),
        store=CaptureStore(tmp_path),
        source_provenance=RunProvenance.LIVE,
        source_model_id=LIVE_MODEL,
    )

    with pytest.raises(ContractError, match="store=False"):
        asyncio.run(
            model.get_response(
                "instructions", "input", ModelSettings(), [], None, [], None,
                previous_response_id=None, conversation_id=None, prompt=None,
            )
        )

    assert client.responses.requests == []


def test_scripted_and_replay_manifests_record_the_store_setting():
    environment = SupportEnvironment()
    gateway = _gateway(environment)
    record = run_agent(
        agent=build_support_agent(
            environment=environment, tools=gateway_function_tools(gateway),
            model=ScriptedSupportModel(),
        ),
        task_input=task_message("T-1001"), gateway=gateway,
        run_id="run-0001", provenance=RunProvenance.SCRIPTED,
    )

    assert record.model_settings == {"store": False}
    assert record.evidence_payload()["model_settings"] == {"store": False}
    assert run_manifest(record)["store"] is False


def test_recording_script_uses_the_agent_definition_settings():
    source = (REPO_ROOT / "scripts" / "record_support_captures.py").read_text(encoding="utf-8")

    assert "build_support_agent(" in source
    assert "model_settings" not in source
    assert "RunProvenance.LIVE" in source
