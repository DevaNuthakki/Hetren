from dataclasses import FrozenInstanceError
from itertools import count
from pathlib import Path
import re

import pytest

from packages.action_gateway import (
    AllowAllPolicy,
    AllowListPolicy,
    AuthorizationDecision,
    GatedTool,
    StageStatus,
    ToolGateway,
    ToolStage,
    ToolStageRecord,
    stage_records_sha256,
    to_agent_trace,
)
from packages.contracts import ContractError, canonical_sha256
from packages.core.hetren_diagnosis.contracts import AgentTrace, EventKind


GATEWAY_ROOT = (
    Path(__file__).resolve().parents[2] / "packages" / "action_gateway"
)

AMOUNT_SCHEMA = {
    "type": "object",
    "properties": {"amount": {"type": "integer", "minimum": 1}},
    "required": ["amount"],
    "additionalProperties": False,
}

EMPTY_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


class Counter:
    """Minimal non-support environment used to show the wrapper is generic."""

    def __init__(self) -> None:
        self.value = 0
        self.calls: list[str] = []

    def state_sha256(self) -> str:
        return canonical_sha256({"value": self.value})

    def increment(self, *, amount: int) -> dict[str, object]:
        self.calls.append("increment")
        self.value += amount
        return {"value": self.value}

    def read(self) -> dict[str, object]:
        self.calls.append("read")
        return {"value": self.value}

    def explode(self) -> dict[str, object]:
        self.calls.append("explode")
        raise LookupError("unknown counter")

    def mutate_then_explode(self) -> dict[str, object]:
        self.calls.append("mutate_then_explode")
        self.value += 100
        raise RuntimeError("partial failure")

    def opaque(self) -> object:
        self.calls.append("opaque")
        return object()


def _gateway(counter: Counter, policy=None, clock=None) -> ToolGateway:
    return ToolGateway(
        tools=[
            GatedTool("increment", counter.increment, AMOUNT_SCHEMA, "Add to the counter."),
            GatedTool("read", counter.read, EMPTY_SCHEMA, "Read the counter."),
            GatedTool("explode", counter.explode, EMPTY_SCHEMA, "Always fails."),
            GatedTool(
                "mutate_then_explode", counter.mutate_then_explode,
                EMPTY_SCHEMA, "Changes state, then fails.",
            ),
            GatedTool("opaque", counter.opaque, EMPTY_SCHEMA, "Returns a non-JSON value."),
        ],
        policy=policy or AllowAllPolicy(),
        state_sha256=counter.state_sha256,
        clock=clock,
    )


def _stages(records) -> list[tuple[str, str]]:
    return [(record.stage.value, record.status.value) for record in records]


# Allowed calls


def test_allowed_call_records_four_stages_in_order():
    counter = Counter()
    gateway = _gateway(counter)
    start = counter.state_sha256()

    result = gateway.invoke("increment", {"amount": 3})

    assert result.status is StageStatus.SUCCEEDED
    assert result.observation == {"value": 3}
    assert result.error is None
    assert result.invocation_id == "call-0001"
    assert result.records == gateway.records
    assert _stages(result.records) == [
        ("proposed", "proposed"),
        ("authorized", "allowed"),
        ("attempted", "started"),
        ("observed", "succeeded"),
    ]
    assert [record.sequence for record in result.records] == [0, 1, 2, 3]

    proposed, authorized, attempted, observed = result.records
    assert proposed.payload == {"arguments": {"amount": 3}}
    assert authorized.payload == {
        "allowed": True, "reason": "allowed", "policy_id": "allow_all",
    }
    assert attempted.payload == {}
    assert observed.payload == {"observation": {"value": 3}}

    for record in (proposed, authorized, attempted):
        assert record.state_before_sha256 == record.state_after_sha256 == start

    assert observed.state_before_sha256 == start
    assert observed.state_after_sha256 == counter.state_sha256() != start
    assert len({record.arguments_sha256 for record in result.records}) == 1


def test_read_only_call_shows_unchanged_state():
    counter = Counter()
    observed = _gateway(counter).invoke("read", {}).records[-1]

    assert observed.status is StageStatus.SUCCEEDED
    assert observed.state_before_sha256 == observed.state_after_sha256


def test_sequences_are_contiguous_across_invocations():
    gateway = _gateway(Counter())

    first = gateway.invoke("increment", {"amount": 1})
    denied = gateway.invoke("missing_tool", {})
    failed = gateway.invoke("explode", {})

    assert [r.invocation_id for r in (first, denied, failed)] == [
        "call-0001", "call-0002", "call-0003",
    ]
    assert [record.sequence for record in gateway.records] == list(range(10))
    assert gateway.records == first.records + denied.records + failed.records


# Denied calls


@pytest.mark.parametrize(
    ("tool_name", "arguments", "policy", "reason", "policy_id"),
    [
        ("increment", {"amount": 1}, AllowListPolicy({"read"}), "tool_not_allowed", "allow_list"),
        ("missing_tool", {}, None, "unknown_tool", "gateway"),
        ("increment", {"amount": 0}, None, "arguments_schema_invalid", "gateway"),
        ("increment", {"amount": 1, "extra": True}, None, "arguments_schema_invalid", "gateway"),
        ("increment", {}, None, "arguments_schema_invalid", "gateway"),
    ],
)
def test_denied_call_records_only_proposed_and_authorized(
    tool_name, arguments, policy, reason, policy_id,
):
    counter = Counter()
    gateway = _gateway(counter, policy=policy)
    start = counter.state_sha256()

    result = gateway.invoke(tool_name, arguments)

    assert result.status is StageStatus.DENIED
    assert result.observation is None and result.error is None
    assert _stages(result.records) == [
        ("proposed", "proposed"),
        ("authorized", "denied"),
    ]
    assert result.records[1].payload == {
        "allowed": False, "reason": reason, "policy_id": policy_id,
    }
    assert counter.calls == []
    assert counter.state_sha256() == start
    for record in result.records:
        assert record.state_before_sha256 == record.state_after_sha256 == start


class RaisingPolicy:
    policy_id = "raising"

    def authorize(self, proposal):
        raise RuntimeError("policy backend unavailable")


class JunkPolicy:
    policy_id = "junk"

    def authorize(self, proposal):
        return True


@pytest.mark.parametrize(
    ("policy", "reason"),
    [(RaisingPolicy(), "policy_error"), (JunkPolicy(), "policy_invalid_decision")],
)
def test_policy_failures_fail_closed(policy, reason):
    counter = Counter()
    result = _gateway(counter, policy=policy).invoke("increment", {"amount": 1})

    assert result.status is StageStatus.DENIED
    assert result.records[1].payload["reason"] == reason
    assert counter.calls == []
    assert counter.value == 0


def test_policy_sees_the_proposal():
    seen = []

    class RecordingPolicy:
        policy_id = "recording"

        def authorize(self, proposal):
            seen.append(proposal)
            return AuthorizationDecision(True, "recorded", self.policy_id)

    _gateway(Counter(), policy=RecordingPolicy()).invoke("increment", {"amount": 2})

    assert len(seen) == 1
    assert (seen[0].invocation_id, seen[0].tool_name, seen[0].arguments) == (
        "call-0001", "increment", {"amount": 2},
    )


# Failed observations


def test_tool_exception_becomes_failed_observation_without_state_change():
    counter = Counter()
    start = counter.state_sha256()

    result = _gateway(counter).invoke("explode", {})

    assert result.status is StageStatus.FAILED
    assert result.observation is None
    assert result.error == {"type": "LookupError", "message": "unknown counter"}
    assert _stages(result.records)[-2:] == [
        ("attempted", "started"),
        ("observed", "failed"),
    ]
    observed = result.records[-1]
    assert observed.payload == {"error": result.error}
    assert observed.state_before_sha256 == observed.state_after_sha256 == start


def test_failed_observation_reports_partial_state_change_honestly():
    counter = Counter()
    start = counter.state_sha256()

    observed = _gateway(counter).invoke("mutate_then_explode", {}).records[-1]

    assert observed.status is StageStatus.FAILED
    assert observed.state_before_sha256 == start
    assert observed.state_after_sha256 == counter.state_sha256() != start


def test_non_json_observation_becomes_failed_observation():
    result = _gateway(Counter()).invoke("opaque", {})

    assert result.status is StageStatus.FAILED
    assert result.error["type"] == "InvalidObservation"


def test_non_json_arguments_are_a_caller_error_and_record_nothing():
    gateway = _gateway(Counter())

    with pytest.raises(ContractError):
        gateway.invoke("increment", {"amount": object()})

    assert gateway.records == ()
    assert gateway.invoke("read", {}).invocation_id == "call-0001"


# Determinism and timestamps


def _scripted_calls(gateway: ToolGateway) -> None:
    gateway.invoke("increment", {"amount": 2})
    gateway.invoke("missing_tool", {})
    gateway.invoke("explode", {})
    gateway.invoke("read", {})


def test_identical_calls_produce_identical_record_hashes():
    first = _gateway(Counter())
    second = _gateway(Counter())

    _scripted_calls(first)
    _scripted_calls(second)

    assert stage_records_sha256(first.records) == stage_records_sha256(second.records)


def test_wall_clock_timestamps_are_excluded_from_hashes():
    ticks = count()
    clocked = _gateway(Counter(), clock=lambda: f"2026-10-31T12:00:{next(ticks):02d}Z")
    unclocked = _gateway(Counter())

    _scripted_calls(clocked)
    _scripted_calls(unclocked)

    assert all(record.recorded_at for record in clocked.records)
    assert all(record.recorded_at is None for record in unclocked.records)
    assert len({record.recorded_at for record in clocked.records}) == len(clocked.records)
    assert [r.record_sha256 for r in clocked.records] == [
        r.record_sha256 for r in unclocked.records
    ]
    assert stage_records_sha256(clocked.records) == stage_records_sha256(unclocked.records)
    for record in clocked.records:
        assert "recorded_at" not in record.canonical_payload()


# AgentTrace projection


def test_records_project_into_agent_trace():
    gateway = _gateway(Counter())
    _scripted_calls(gateway)

    trace = to_agent_trace("run-0001", gateway.records)

    assert isinstance(trace, AgentTrace)
    assert trace.run_id == "run-0001"
    assert len(trace.events) == len(gateway.records)

    expected_kinds = {
        ToolStage.PROPOSED: EventKind.DECISION,
        ToolStage.AUTHORIZED: EventKind.DECISION,
        ToolStage.ATTEMPTED: EventKind.TOOL_CALL,
        ToolStage.OBSERVED: EventKind.TOOL_RESULT,
    }

    for record, event in zip(gateway.records, trace.events):
        assert event.sequence == record.sequence
        assert event.kind is expected_kinds[record.stage]
        assert event.component == record.tool_name
        assert event.operation == f"{record.stage.value}:{record.status.value}"
        assert event.input_sha256 == record.arguments_sha256
        assert event.output_sha256 == record.payload_sha256
        assert event.state_before_sha256 == record.state_before_sha256
        assert event.state_after_sha256 == record.state_after_sha256


def test_trace_projection_is_deterministic():
    first = _gateway(Counter())
    second = _gateway(Counter(), clock=lambda: "2026-10-31T00:00:00Z")
    _scripted_calls(first)
    _scripted_calls(second)

    assert (
        to_agent_trace("run-0001", first.records).trace_sha256
        == to_agent_trace("run-0001", second.records).trace_sha256
    )


def test_projection_requires_contiguous_records():
    gateway = _gateway(Counter())
    _scripted_calls(gateway)

    with pytest.raises(Exception):
        to_agent_trace("run-0001", gateway.records[1:])

    with pytest.raises(ContractError):
        to_agent_trace("run-0001", list(gateway.records))  # type: ignore[arg-type]


# Contract validation


def _record(**overrides) -> ToolStageRecord:
    values = {
        "sequence": 0,
        "invocation_id": "call-0001",
        "tool_name": "read",
        "stage": ToolStage.PROPOSED,
        "status": StageStatus.PROPOSED,
        "arguments_sha256": "a" * 64,
        "payload": {"arguments": {}},
        "state_before_sha256": "b" * 64,
        "state_after_sha256": "b" * 64,
    }
    values.update(overrides)
    return ToolStageRecord(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"sequence": -1},
        {"sequence": True},
        {"invocation_id": "run-0001"},
        {"tool_name": "Read Ticket"},
        {"status": StageStatus.SUCCEEDED},
        {"stage": ToolStage.AUTHORIZED, "status": StageStatus.STARTED},
        {"state_after_sha256": "c" * 64},
        {"arguments_sha256": "A" * 64},
        {"payload": ["not", "an", "object"]},
        {"recorded_at": ""},
    ],
)
def test_invalid_stage_records_are_rejected(overrides):
    with pytest.raises(ContractError):
        _record(**overrides)


def test_only_observed_records_may_change_state():
    record = _record(
        stage=ToolStage.OBSERVED,
        status=StageStatus.SUCCEEDED,
        payload={"observation": {}},
        state_after_sha256="c" * 64,
    )

    assert record.state_before_sha256 != record.state_after_sha256


def test_stage_records_are_frozen_and_detached_from_inputs():
    payload = {"arguments": {"amount": 1}}
    record = _record(payload=payload)
    payload["arguments"]["amount"] = 99

    assert record.payload == {"arguments": {"amount": 1}}
    with pytest.raises(FrozenInstanceError):
        record.sequence = 5  # type: ignore[misc]


def test_gated_tool_and_gateway_validation():
    counter = Counter()

    with pytest.raises(ContractError):
        GatedTool("read", counter.read, {"type": "not-a-type"}, "Bad schema.")
    with pytest.raises(ContractError):
        GatedTool("read", "not callable", EMPTY_SCHEMA, "Not callable.")  # type: ignore[arg-type]
    with pytest.raises(ContractError):
        GatedTool("read", counter.read, EMPTY_SCHEMA, " ")

    tool = GatedTool("read", counter.read, EMPTY_SCHEMA, "Read the counter.")

    with pytest.raises(ContractError):
        ToolGateway(tools=[tool, tool], policy=AllowAllPolicy(), state_sha256=counter.state_sha256)
    with pytest.raises(ContractError):
        ToolGateway(tools=[object()], policy=AllowAllPolicy(), state_sha256=counter.state_sha256)  # type: ignore[list-item]


def test_tool_definitions_expose_name_description_and_schema_only():
    definitions = _gateway(Counter()).tool_definitions()

    assert [definition["name"] for definition in definitions] == sorted(
        ["increment", "read", "explode", "mutate_then_explode", "opaque"]
    )
    assert definitions[1] == {
        "name": "increment",
        "description": "Add to the counter.",
        "parameters": AMOUNT_SCHEMA,
    }


@pytest.mark.parametrize(
    "decision",
    [
        {"allowed": "yes", "reason": "ok", "policy_id": "p"},
        {"allowed": True, "reason": "Not A Code", "policy_id": "p"},
        {"allowed": True, "reason": "ok", "policy_id": ""},
    ],
)
def test_invalid_authorization_decisions_are_rejected(decision):
    with pytest.raises(ContractError):
        AuthorizationDecision(**decision)


# Genericity


def test_gateway_source_has_no_environment_specific_logic():
    forbidden = re.compile(
        r"\b(support|ticket|account|queue|customer|environments)\b",
        re.IGNORECASE,
    )

    for path in sorted(GATEWAY_ROOT.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert forbidden.search(source) is None, path.name


# Raw (unparsed) arguments from a model


def test_invoke_raw_parses_valid_json_like_invoke():
    raw = _gateway(Counter()).invoke_raw("increment", '{"amount": 4}')
    parsed = _gateway(Counter()).invoke("increment", {"amount": 4})

    assert raw.status is StageStatus.SUCCEEDED
    assert stage_records_sha256(raw.records) == stage_records_sha256(parsed.records)


def test_invoke_raw_treats_empty_text_as_no_arguments():
    assert _gateway(Counter()).invoke_raw("read", "").status is StageStatus.SUCCEEDED


@pytest.mark.parametrize(
    "raw",
    ['{"amount": 4', "not json", "[1, 2]", '"text"', "NaN", '{"amount": NaN}'],
)
def test_malformed_raw_arguments_are_recorded_as_denied_evidence(raw):
    counter = Counter()
    gateway = _gateway(counter)

    result = gateway.invoke_raw("increment", raw)

    assert result.status is StageStatus.DENIED
    assert _stages(result.records) == [("proposed", "proposed"), ("authorized", "denied")]
    assert result.records[0].payload == {"arguments": {"raw_arguments": raw}}
    assert result.records[1].payload == {
        "allowed": False, "reason": "arguments_not_json", "policy_id": "gateway",
    }
    assert counter.calls == []
    assert gateway.records == result.records


def test_malformed_raw_arguments_skip_the_policy():
    seen = []

    class RecordingPolicy:
        policy_id = "recording"

        def authorize(self, proposal):
            seen.append(proposal)
            return AuthorizationDecision(True, "recorded", self.policy_id)

    _gateway(Counter(), policy=RecordingPolicy()).invoke_raw("increment", "{oops")

    assert seen == []
