import asyncio
import json
import socket

import pytest
from agents import Agent, Model, ModelResponse, Usage
from openai.types.responses import ResponseOutputMessage, ResponseOutputText

from packages.action_gateway import (
    AllowAllPolicy,
    AllowListPolicy,
    GatedTool,
    StageStatus,
    ToolGateway,
)
from packages.contracts import ContractError, canonical_sha256
from packages.integrations.openai_agents import (
    RunProvenance,
    RunRecord,
    RunStatus,
    SdkEvidence,
    gateway_function_tools,
    model_identity,
    model_provenance,
    run_agent,
)


SCHEMA = {
    "type": "object",
    "properties": {"amount": {"type": "integer"}},
    "required": ["amount"],
    "additionalProperties": False,
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


class Store:
    def __init__(self) -> None:
        self.value = 0

    def state_sha256(self) -> str:
        return canonical_sha256({"value": self.value})

    def add(self, *, amount: int) -> dict[str, object]:
        self.value += amount
        return {"value": self.value}


def _gateway(store: Store, policy=None) -> ToolGateway:
    return ToolGateway(
        tools=[GatedTool("add", store.add, SCHEMA, "Add an amount.")],
        policy=policy or AllowAllPolicy(),
        state_sha256=store.state_sha256,
    )


class ReplyModel(Model):
    """Generic offline model that answers immediately."""

    hetren_provenance = RunProvenance.SCRIPTED
    hetren_model_id = "reply-model"

    async def get_response(self, *args, **kwargs) -> ModelResponse:
        return ModelResponse(
            output=[
                ResponseOutputMessage(
                    type="message", id="msg_1", role="assistant", status="completed",
                    content=[ResponseOutputText(type="output_text", text="done", annotations=[])],
                )
            ],
            usage=Usage(),
            response_id=None,
        )

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError


class FailingModel(ReplyModel):
    async def get_response(self, *args, **kwargs) -> ModelResponse:
        raise RuntimeError("model unavailable")


class UnlabelledModel(ReplyModel):
    hetren_provenance = None


def _agent(gateway: ToolGateway, model=None) -> Agent:
    return Agent(
        name="generic-agent",
        instructions="Answer.",
        tools=gateway_function_tools(gateway),
        model=model or ReplyModel(),
    )


def _invoke(tool, raw: str) -> dict[str, object]:
    return json.loads(asyncio.run(tool.on_invoke_tool(None, raw)))


# Provenance


def test_model_provenance_and_identity():
    assert model_provenance("gpt-test") is RunProvenance.LIVE
    assert model_identity("gpt-test") == "gpt-test"
    assert model_provenance(ReplyModel()) is RunProvenance.SCRIPTED
    assert model_identity(ReplyModel()) == "reply-model"

    with pytest.raises(ContractError):
        model_provenance(UnlabelledModel())


def test_declared_provenance_must_match_the_model():
    store = Store()
    gateway = _gateway(store)

    for declared in (RunProvenance.LIVE, RunProvenance.REPLAY):
        with pytest.raises(ContractError, match="provenance"):
            run_agent(
                agent=_agent(gateway), task_input="go", gateway=gateway,
                run_id="run-0001", provenance=declared,
            )


# Tool bridge


def test_function_tools_mirror_gateway_definitions():
    (tool,) = gateway_function_tools(_gateway(Store()))

    assert tool.name == "add"
    assert tool.description == "Add an amount."
    assert tool.params_json_schema == SCHEMA
    assert tool.strict_json_schema is True


def test_tool_bridge_returns_observation_error_or_denial():
    store = Store()
    gateway = _gateway(store, policy=AllowListPolicy({"add"}))
    (tool,) = gateway_function_tools(gateway)

    assert _invoke(tool, '{"amount": 2}') == {"observation": {"value": 2}}
    assert _invoke(tool, '{"amount": "two"}') == {"denied": "arguments_schema_invalid"}
    assert _invoke(tool, "{broken") == {"denied": "arguments_not_json"}


def test_malformed_model_arguments_are_recorded_not_lost():
    store = Store()
    gateway = _gateway(store)
    (tool,) = gateway_function_tools(gateway)

    _invoke(tool, '{"amount": 1')

    proposed, authorized = gateway.records
    assert proposed.payload == {"arguments": {"raw_arguments": '{"amount": 1'}}
    assert authorized.status is StageStatus.DENIED
    assert authorized.payload["reason"] == "arguments_not_json"
    assert store.value == 0


# Runner


def test_runner_produces_a_record_with_provenance():
    gateway = _gateway(Store())

    record = run_agent(
        agent=_agent(gateway), task_input="go", gateway=gateway,
        run_id="run-0001", provenance=RunProvenance.SCRIPTED,
    )

    assert record.provenance is RunProvenance.SCRIPTED
    assert record.status is RunStatus.COMPLETED
    assert record.final_message == "done"
    assert record.model_id == "reply-model"
    assert record.stage_records == ()
    assert record.evidence_payload()["provenance"] == "scripted"
    assert "final_message" not in json.dumps(record.evidence_payload())
    assert record.canonical_payload()["agent_output"] == {"final_message": "done"}


def test_runner_records_model_errors_as_evidence():
    gateway = _gateway(Store())

    record = run_agent(
        agent=_agent(gateway, FailingModel()), task_input="go", gateway=gateway,
        run_id="run-0001", provenance=RunProvenance.SCRIPTED,
    )

    assert record.status is RunStatus.ERROR
    assert record.error == {
        "type": "RuntimeError",
        "message_sha256": canonical_sha256({"text": "model unavailable"}),
    }
    assert "model unavailable" not in json.dumps(record.canonical_payload())
    assert record.final_message is None


def test_runner_requires_fresh_gateway_and_matching_tools():
    store = Store()
    used = _gateway(store)
    used.invoke("add", {"amount": 1})

    with pytest.raises(ContractError, match="fresh"):
        run_agent(
            agent=_agent(used), task_input="go", gateway=used,
            run_id="run-0001", provenance=RunProvenance.SCRIPTED,
        )

    fresh = _gateway(store)
    toolless = Agent(name="generic-agent", instructions="Answer.", tools=[], model=ReplyModel())

    with pytest.raises(ContractError, match="exactly the gateway"):
        run_agent(
            agent=toolless, task_input="go", gateway=fresh,
            run_id="run-0001", provenance=RunProvenance.SCRIPTED,
        )


@pytest.mark.parametrize("run_id", ["run-1", "correct-0001", "run-00001", ""])
def test_run_records_require_neutral_run_ids(run_id):
    gateway = _gateway(Store())

    with pytest.raises(ContractError, match="run_id"):
        run_agent(
            agent=_agent(gateway), task_input="go", gateway=gateway,
            run_id=run_id, provenance=RunProvenance.SCRIPTED,
        )


def test_run_record_validation():
    values = dict(
        run_id="run-0001", provenance=RunProvenance.SCRIPTED,
        source_provenance=None, model_id="m",
        agent_name="a", instructions_sha256="0" * 64, task_input="go",
        tool_definitions=(), initial_state_sha256="1" * 64,
        final_state_sha256="1" * 64, stage_records=(),
        sdk_evidence=SdkEvidence(hook_events=(), spans=(), discrepancies=()),
        replay_capture_ids=(), recorded_capture_ids=(),
        status=RunStatus.COMPLETED, error=None, final_message=None,
        limitations=("limit",),
    )
    RunRecord(**values)

    for overrides in (
        {"provenance": "scripted"},
        {"status": RunStatus.ERROR},
        {"error": {"type": "X", "message_sha256": "0" * 64}},
        {"status": RunStatus.ERROR, "error": {"type": "X", "message": "free text"}},
        {"sdk_evidence": None},
        {"source_provenance": RunProvenance.LIVE},
        {"replay_capture_ids": ("capture-0001",)},
        {"provenance": RunProvenance.REPLAY},
        {"provenance": RunProvenance.REPLAY, "source_provenance": RunProvenance.REPLAY},
        {
            "provenance": RunProvenance.REPLAY,
            "source_provenance": RunProvenance.LIVE,
            "recorded_capture_ids": ("capture-0001",),
        },
        {"limitations": ()},
        {"stage_records": ({"not": "a record"},)},
        {"task_input": " "},
    ):
        with pytest.raises(ContractError):
            RunRecord(**{**values, **overrides})
