import asyncio
import json
import socket

import pytest
from agents import ModelSettings
from openai.types.responses import ResponseOutputMessage, ResponseOutputText
from agents import ModelResponse, Usage

from packages.action_gateway import AllowAllPolicy, GatedTool, ToolGateway
from packages.contracts import ContractError, canonical_sha256
from packages.integrations.openai_agents import (
    CaptureConflictError,
    CaptureStore,
    RecordingModel,
    ReplayMissError,
    ReplayModel,
    ReplayModelProvider,
    ReplayVersionError,
    RunProvenance,
    gateway_function_tools,
    installed_versions,
    replay_key,
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


def _tools(description="Add an amount."):
    gateway = ToolGateway(
        tools=[GatedTool("add", lambda **kwargs: {}, SCHEMA, description)],
        policy=AllowAllPolicy(),
        state_sha256=lambda: canonical_sha256({}),
    )
    return gateway_function_tools(gateway)


def _items(user="Add two.", output='{"observation": {"value": 2}}', item_id="fc_1", call_id="call_a"):
    return [
        {"role": "user", "content": user},
        {
            "type": "function_call", "id": item_id, "call_id": call_id,
            "name": "add", "arguments": '{"amount": 2}', "status": "completed",
        },
        {"type": "function_call_output", "call_id": call_id, "output": output},
    ]


class OutputSchema:
    def __init__(self, schema):
        self._schema = schema

    def json_schema(self):
        return self._schema


class Handoff:
    def __init__(self, tool_name):
        self.tool_name = tool_name


BASE = dict(
    model_id="model-a",
    system_instructions="Be precise.",
    input_items=_items(),
    model_settings=ModelSettings(),
    tools=_tools(),
    output_schema=None,
    handoffs=[],
    prompt=None,
)


def _key(**overrides):
    return replay_key(**{**BASE, **overrides})


def _response(text="ok") -> ModelResponse:
    return ModelResponse(
        output=[
            ResponseOutputMessage(
                type="message", id="msg_1", role="assistant", status="completed",
                content=[ResponseOutputText(type="output_text", text=text, annotations=[])],
            )
        ],
        usage=Usage(requests=1, input_tokens=10, output_tokens=3, total_tokens=13),
        response_id="resp_provider_123",
    )


def _store_with_base(tmp_path) -> CaptureStore:
    store = CaptureStore(tmp_path / "captures")
    store.append(
        key=_key(), response=_response(),
        source_provenance=RunProvenance.SCRIPTED, source_model_id="model-a",
    )
    return store


# Replay key: each component alone causes a miss


@pytest.mark.parametrize(
    ("component", "overrides"),
    [
        ("model", {"model_id": "model-b"}),
        ("model", {"model_settings": ModelSettings(temperature=0.0)}),
        ("system_instructions", {"system_instructions": "Be brief."}),
        ("input_items", {"input_items": _items(user="Add three.")}),
        ("prior_observations", {"input_items": _items(output='{"observation": {"value": 9}}')}),
        ("tool_definitions", {"tools": _tools(description="Add any amount.")}),
        ("output_schema", {"output_schema": OutputSchema({"type": "object"})}),
        ("handoffs", {"handoffs": [Handoff("transfer_to_billing")]}),
        ("prompt", {"prompt": {"id": "pmpt_1"}}),
    ],
)
def test_changing_one_component_alone_is_a_miss(tmp_path, component, overrides):
    store = _store_with_base(tmp_path)
    changed = _key(**overrides)

    differing = [
        name for name, digest in changed.component_digests.items()
        if _key().component_digests[name] != digest
    ]
    assert differing == [component]

    with pytest.raises(ReplayMissError, match=f"differs in: {component}$"):
        store.lookup(changed)


@pytest.mark.parametrize(
    "overrides",
    [
        {"input_items": _items(item_id="fc_other")},
        {"input_items": _items(call_id="call_renamed")},
        {"input_items": _items(item_id="fc_x", call_id="call_y")},
    ],
)
def test_sdk_and_provider_ids_are_excluded(tmp_path, overrides):
    store = _store_with_base(tmp_path)

    assert _key(**overrides).key_sha256 == _key().key_sha256
    assert store.lookup(_key(**overrides)).capture_id == "capture-0001"


def test_call_structure_is_kept_even_though_ids_are_not():
    items = _items()
    unlinked = [dict(item) for item in items]
    unlinked[2]["call_id"] = "call_unrelated"

    assert _key(input_items=unlinked).key_sha256 != _key().key_sha256


def test_replay_model_ignores_response_and_conversation_ids(tmp_path):
    store = _store_with_base(tmp_path)
    model = ReplayModel(
        store=store, source_provenance=RunProvenance.SCRIPTED, source_model_id="model-a",
    )

    for previous, conversation, tracing in (
        (None, None, None), ("resp_1", "conv_1", object()), ("resp_2", None, "tracing"),
    ):
        response = asyncio.run(
            model.get_response(
                BASE["system_instructions"], BASE["input_items"], BASE["model_settings"],
                BASE["tools"], None, [], tracing,
                previous_response_id=previous, conversation_id=conversation, prompt=None,
            )
        )
        assert response.output[0].content[0].text == "ok"

    assert model.used_capture_ids == ["capture-0001"] * 3


# Capture store


def test_capture_documents_are_versioned_and_neutral(tmp_path):
    store = _store_with_base(tmp_path)
    path = store.directory / "capture-0001.json"
    document = json.loads(path.read_text(encoding="utf-8"))

    assert sorted(document) == [
        "capture_id", "component_digests", "format", "format_version", "key_sha256",
        "response", "source_model_id", "source_provenance", "versions",
    ]
    assert document["format"] == "hetren-model-capture"
    assert document["format_version"] == 1
    assert document["key_sha256"] == _key().key_sha256
    assert document["versions"] == installed_versions()
    assert document["versions"] == {"openai": "3.42.0", "openai-agents": "0.24.0"}
    assert document["source_provenance"] == "scripted"
    assert document["response"]["usage"] == {
        "requests": 1, "input_tokens": 10, "output_tokens": 3, "total_tokens": 13,
    }
    assert "resp_provider_123" not in path.read_text(encoding="utf-8")
    assert "Be precise." not in path.read_text(encoding="utf-8")


def test_capture_ids_are_sequential_and_files_are_never_overwritten(tmp_path):
    store = _store_with_base(tmp_path)
    second = store.append(
        key=_key(system_instructions="Other."), response=_response("two"),
        source_provenance=RunProvenance.LIVE, source_model_id="model-a",
    )

    assert second.capture_id == "capture-0002"
    assert sorted(path.name for path in store.directory.iterdir()) == [
        "capture-0001.json", "capture-0002.json",
    ]
    with pytest.raises(CaptureConflictError, match="already exists"):
        store.append(
            key=_key(), response=_response("again"),
            source_provenance=RunProvenance.SCRIPTED, source_model_id="model-a",
        )


def test_reloaded_store_replays_the_same_response(tmp_path):
    _store_with_base(tmp_path)
    reloaded = CaptureStore(tmp_path / "captures")

    capture = reloaded.lookup(_key())
    response = capture.model_response()

    assert response.output[0].content[0].text == "ok"
    assert response.usage.total_tokens == 13
    assert response.response_id is None


@pytest.mark.parametrize(
    ("name", "mutate", "message"),
    [
        ("verified_recovery.json", None, "non-neutral capture file name"),
        ("capture-0001.json", {"format_version": 2}, "unsupported capture format"),
        ("capture-0001.json", {"format": "other"}, "unsupported capture format"),
        ("capture-0001.json", {"source_provenance": "replay"}, "malformed|live or scripted"),
        ("capture-0001.json", {"capture_id": "capture-0009"}, "does not match its file name"),
    ],
)
def test_store_refuses_bad_capture_files(tmp_path, name, mutate, message):
    store = _store_with_base(tmp_path)
    path = store.directory / "capture-0001.json"
    document = json.loads(path.read_text(encoding="utf-8"))

    if mutate is not None:
        document.update(mutate)

    path.unlink()
    (store.directory / name).write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ContractError, match=message):
        CaptureStore(store.directory).captures()


def test_version_mismatch_is_refused_with_a_clear_error(tmp_path):
    store = _store_with_base(tmp_path)
    path = store.directory / "capture-0001.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["versions"]["openai-agents"] = "0.23.1"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReplayVersionError) as raised:
        CaptureStore(store.directory).lookup(_key())

    message = str(raised.value)
    assert "capture-0001" in message
    assert "'openai-agents': '0.23.1'" in message
    assert "'openai-agents': '0.24.0'" in message


# Provenance of replay and recording models


def test_replay_source_must_match_the_capture(tmp_path):
    store = _store_with_base(tmp_path)

    for source, model_id, message in (
        (RunProvenance.LIVE, "model-a", "source provenance scripted, not live"),
        (RunProvenance.SCRIPTED, "model-b", "no capture matches"),
    ):
        model = ReplayModel(store=store, source_provenance=source, source_model_id=model_id)

        with pytest.raises(ReplayMissError, match=message):
            asyncio.run(
                model.get_response(
                    BASE["system_instructions"], BASE["input_items"], BASE["model_settings"],
                    BASE["tools"], None, [], None,
                    previous_response_id=None, conversation_id=None, prompt=None,
                )
            )


def test_replay_and_recording_provenance_rules(tmp_path):
    store = CaptureStore(tmp_path)

    with pytest.raises(ContractError):
        ReplayModel(store=store, source_provenance=RunProvenance.REPLAY, source_model_id="m")

    class Labelled:
        hetren_provenance = RunProvenance.SCRIPTED
        hetren_model_id = "scripted-x"

    class Unlabelled:
        pass

    with pytest.raises(ContractError, match="does not match the inner model"):
        RecordingModel(inner=Labelled(), store=store, source_provenance=RunProvenance.LIVE)
    with pytest.raises(ContractError, match="only be recorded as live"):
        RecordingModel(
            inner=Unlabelled(), store=store, source_provenance=RunProvenance.SCRIPTED,
            source_model_id="m",
        )

    recording = RecordingModel(inner=Labelled(), store=store, source_provenance=RunProvenance.SCRIPTED)
    assert recording.hetren_provenance is RunProvenance.SCRIPTED
    assert recording.hetren_model_id == "scripted-x"

    replay = ReplayModelProvider(store=store, source_provenance=RunProvenance.LIVE).get_model("model-a")
    assert replay.hetren_provenance is RunProvenance.REPLAY
    assert replay.hetren_source_provenance is RunProvenance.LIVE
    assert replay.hetren_model_id == "replay:model-a"
