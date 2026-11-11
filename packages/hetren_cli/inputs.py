"""The CLI's inputs: a recorded run of the support workflow, or its compact first-step evidence.

Accepted:

- an ``AgentRunRecord`` evidence payload: ``RunRecord.evidence_payload()`` as JSON, from a run recorded with
  Hetren's OpenAI Agents SDK integration (``packages.integrations.openai_agents.run_agent`` with a
  ``ToolGateway``). The gateway's stage records carry what the model reads: each call's arguments, whether it
  was authorized (or denied, and why), its observation or error, and whether it changed state;
- ``compact-evidence-v1``: the model's first-step input itself, or one line of the published
  ``hetren_visible.jsonl`` (its first step's input is used).

Rejected, with a message: anything else, in particular an OpenAI Agents SDK trace export (traces and spans).
Spans never record authorization or state changes, and with ``trace_include_sensitive_data=False`` (Hetren's
setting) not even arguments or observations, so a trace cannot be turned into the input the model was
trained on without inventing facts. Runs that use tools other than the support workflow's three
(``read_ticket``, ``lookup_account``, ``route_ticket``) are rejected too: the model was trained only on that
workflow.
"""

from __future__ import annotations

from functools import cache
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from packages.action_space import PROBE_VERBS
from packages.hetren_evidence import COMPACT_FORMAT, compact_evidence


DATA = Path(__file__).resolve().parent / "data"
SUPPORT_TOOLS = ("read_ticket", "lookup_account", "route_ticket")

HOW_TO_RECORD = (
    "Record the run with Hetren's OpenAI Agents SDK integration instead: run the agent with "
    "packages.integrations.openai_agents.run_agent and a ToolGateway over the support tools, then save "
    "json.dumps(record.evidence_payload()) and pass that file with --record."
)


class InputRejected(ValueError):
    """The input is not one the CLI can diagnose; the message says why."""


@cache
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((DATA / name).read_text(encoding="utf-8")))


def _first_error(validator: Draft202012Validator, value: object) -> str | None:
    errors = sorted(validator.iter_errors(value), key=lambda e: list(e.absolute_path))

    if not errors:
        return None

    error = errors[0]
    where = "/".join(str(p) for p in error.absolute_path) or "(top level)"
    return f"{where}: {error.message}"


def is_sdk_trace(value: object) -> bool:
    """An OpenAI Agents SDK trace or span export (``object`` ``trace`` / ``trace.span``, ``span_data``, ``spans``)."""
    items = value if isinstance(value, list) else [value]

    for item in items:
        if isinstance(item, dict) and (item.get("object") in ("trace", "trace.span") or "span_data" in item
                                       or ("spans" in item and "stage_records" not in item)
                                       or item.get("record_type") in ("SpanRecord", "AgentTrace")):
            return True

    return False


def _scope_errors_in_record(record: dict[str, Any]) -> list[str]:
    tools = {d["name"] for d in record["tool_definitions"]}
    return [] if tools == set(SUPPORT_TOOLS) else [f"tool_definitions name {sorted(tools)}, not {list(SUPPORT_TOOLS)}"]


def from_record(record: object) -> dict[str, Any]:
    """The compact first-step input of a validated ``AgentRunRecord`` evidence payload."""
    if is_sdk_trace(record):
        raise InputRejected("this is an OpenAI Agents SDK trace export, which lacks the gateway records the model "
                            "reads (authorization, observations, state changes). " + HOW_TO_RECORD)

    if not isinstance(record, dict) or record.get("record_type") != "AgentRunRecord":
        raise InputRejected("--record needs an AgentRunRecord evidence payload (record_type AgentRunRecord). "
                            + HOW_TO_RECORD)

    error = _first_error(_validator("agent_run_record.schema.json"), record)

    if error is not None:
        if "is not one of ['read_ticket', 'lookup_account', 'route_ticket']" in error:
            raise InputRejected(f"out of scope: {error}. The model was trained only on the synthetic support "
                                f"workflow and its tools {', '.join(SUPPORT_TOOLS)}.")
        raise InputRejected(f"not a valid AgentRunRecord evidence payload: {error}")

    scope = _scope_errors_in_record(record)

    if scope:
        raise InputRejected(f"out of scope: {scope[0]}. The model was trained only on the synthetic support "
                            "workflow.")

    return check_compact(compact_evidence(record))


def check_compact(compact: object) -> dict[str, Any]:
    """A validated ``compact-evidence-v1`` first-step input."""
    if isinstance(compact, dict) and compact.get("format") == "compact-evidence-v2":
        raise InputRejected("compact-evidence-v2 is a tier 2 input after a recovery; the CLI diagnoses a recorded "
                            "run's first step (compact-evidence-v1) and never applies a recovery")

    error = _first_error(_validator("compact_evidence_v1.schema.json"), compact)

    if error is not None:
        raise InputRejected(f"not a valid {COMPACT_FORMAT} input: {error}")

    for step in compact["steps"]:
        if step["tool"] not in SUPPORT_TOOLS:
            raise InputRejected(f"out of scope: the run calls {step['tool']!r}; the model was trained only on the "
                                f"support workflow's tools {', '.join(SUPPORT_TOOLS)}")

    for probe in compact["probes"]:
        if probe["tool"] not in PROBE_VERBS:
            raise InputRejected(f"not a valid {COMPACT_FORMAT} input: probe {probe['tool']!r} is not a probe verb")

    return compact


def from_compact(value: object) -> dict[str, Any]:
    """A compact input given directly, or a ``hetren_visible.jsonl`` line (its first step's input)."""
    if is_sdk_trace(value):
        return from_record(value)  # the same rejection message

    if isinstance(value, dict) and "steps" in value and "case_id" in value and "format" not in value:
        steps = value["steps"]

        if not isinstance(steps, list) or not steps or not isinstance(steps[0], dict) or "input" not in steps[0]:
            raise InputRejected("a dataset line needs steps[0].input")

        value = steps[0]["input"]

    return check_compact(value)


def read_json(path: Path) -> object:
    """The JSON value in ``path`` (one object; a one-line JSONL file is accepted)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise InputRejected(f"cannot read {path}: {exc.strerror or exc}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        lines = [line for line in text.splitlines() if line.strip()]

        if len(lines) > 1:
            raise InputRejected(f"{path} holds {len(lines)} JSON lines; pass one run (or one dataset line)") from exc

        raise InputRejected(f"{path} is not JSON: {exc.msg} (line {exc.lineno})") from exc


def load_input(record: Path | None = None, compact: Path | None = None) -> dict[str, Any]:
    if (record is None) == (compact is None):
        raise InputRejected("give exactly one of --record and --compact")

    return from_record(read_json(record)) if record is not None else from_compact(read_json(compact))


__all__ = ["HOW_TO_RECORD", "InputRejected", "SUPPORT_TOOLS", "check_compact", "from_compact", "from_record",
           "is_sdk_trace", "load_input", "read_json"]
