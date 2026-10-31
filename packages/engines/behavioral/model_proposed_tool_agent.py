"""Bounded model-proposed tool execution for Hetren's portfolio.

A model provides a structured action proposal. Hetren validates it,
executes one allowlisted arithmetic tool, and independently evaluates
the result. No arbitrary code, shell, filesystem, or network tools.

The existing ModelCapture replay mechanism binds proposals to exact
model requests. The existing OpenAI Responses adapter is reused for
explicit opt-in live inference or injected offline transport.

This is a one-action development agent, not native provider function
calling, general-purpose autonomy, or scientific validation.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    EventKind,
    TraceEvent,
    canonical_sha256,
)
from packages.model_capture import (
    ModelCapture,
    ModelRequest,
    replay_json_capture,
)
from packages.openai_responses import (
    OpenAIResponsesResult,
    Transport,
    call_openai_responses,
)


MAX_OPERAND = 100

ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "tool": {
            "type": "string",
            "enum": ["add_ints", "multiply_ints"],
        },
        "a": {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_OPERAND,
        },
        "b": {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_OPERAND,
        },
    },
    "required": ["tool", "a", "b"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "You are an arithmetic tool-selection agent. "
    "Choose one listed tool and provide its two integer arguments. "
    "Return only the required JSON object. "
    "Do not invent or change the requested operands."
)


def _validate_task(left: int, right: int) -> None:
    for name, value in (("left", left), ("right", right)):
        if (
            type(value) is not int
            or value < 0
            or value > MAX_OPERAND
        ):
            raise ContractError(
                f"{name} must be an integer between 0 and {MAX_OPERAND}"
            )


def _validate_run_id(run_id: str) -> None:
    if (
        type(run_id) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}",
            run_id,
        ) is None
    ):
        raise ContractError("invalid agent run_id")


def build_addition_request(
    *,
    model: str,
    left: int,
    right: int,
) -> ModelRequest:
    """Bind a bounded addition task to an exact model request."""
    _validate_task(left, right)

    return ModelRequest(
        provider="openai",
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=(
            f"Compute the sum of {left} and {right}. "
            f"Use a or b exactly as supplied: a={left}, b={right}."
        ),
        response_schema_name="hetren_addition_tool_v1",
        response_schema=ACTION_SCHEMA,
        generation_parameters={},
    )


@dataclass(frozen=True)
class CapturedAdditionRun:
    run_id: str
    request_sha256: str
    capture_sha256: str
    proposal_sha256: str
    status: str
    rejection_reason: str | None
    selected_tool: str | None
    arguments: tuple[int, int] | None
    output: int | None
    expected_output: int
    trace: AgentTrace

    @property
    def passed(self) -> bool:
        return (
            self.status == "executed"
            and self.output == self.expected_output
        )

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "CapturedAdditionRun",
            "run_id": self.run_id,
            "request_sha256": self.request_sha256,
            "capture_sha256": self.capture_sha256,
            "proposal_sha256": self.proposal_sha256,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "selected_tool": self.selected_tool,
            "arguments": self.arguments,
            "output": self.output,
            "expected_output": self.expected_output,
            "trace_sha256": self.trace.trace_sha256,
        })


@dataclass(frozen=True)
class OpenAIAdditionExecution:
    """Provider result and subsequent independently evaluated execution."""
    provider_result: OpenAIResponsesResult
    agent_run: CapturedAdditionRun


def _validate_proposal(
    proposal: dict,
    *,
    left: int,
    right: int,
) -> tuple[str | None, str | None]:
    if set(proposal) != {"tool", "a", "b"}:
        return None, "invalid_proposal_shape"

    tool = proposal["tool"]
    a = proposal["a"]
    b = proposal["b"]

    if tool not in ("add_ints", "multiply_ints") or type(tool) is not str:
        return None, "tool_not_allowlisted"

    if (
        type(a) is not int
        or type(b) is not int
        or not 0 <= a <= MAX_OPERAND
        or not 0 <= b <= MAX_OPERAND
    ):
        return None, "invalid_arguments"

    if (a, b) != (left, right):
        return None, "arguments_do_not_match_task"

    return tool, None


def _event(
    sequence: int,
    kind: EventKind,
    component: str,
    operation: str,
    request: object,
    response: object,
    before: object,
    after: object,
) -> TraceEvent:
    return TraceEvent(
        sequence=sequence,
        kind=kind,
        component=component,
        operation=operation,
        input_sha256=canonical_sha256(request),
        output_sha256=canonical_sha256(response),
        state_before_sha256=canonical_sha256(before),
        state_after_sha256=canonical_sha256(after),
    )


def run_captured_addition_agent(
    *,
    request: ModelRequest,
    capture: ModelCapture,
    run_id: str,
    left: int,
    right: int,
) -> CapturedAdditionRun:
    """Replay model proposal, validate, execute, independently score."""
    _validate_run_id(run_id)
    _validate_task(left, right)

    if not isinstance(request, ModelRequest):
        raise ContractError("request must be a ModelRequest")

    expected_request = build_addition_request(
        model=request.model,
        left=left,
        right=right,
    )

    if request.request_sha256 != expected_request.request_sha256:
        raise ContractError(
            "model request does not match the trusted addition task"
        )

    # This rejects a mismatched request and a tampered raw capture.
    proposal = replay_json_capture(
        request=request,
        capture=capture,
    )

    proposal_hash = canonical_sha256(proposal)
    selected_tool, rejection = _validate_proposal(
        proposal, left=left, right=right,
    )

    initial_state = {"phase": "start"}
    proposal_state = {
        "phase": "proposed",
        "proposal_sha256": proposal_hash,
    }

    events = [
        _event(
            0,
            EventKind.DECISION,
            "model_capture",
            "propose_tool",
            {
                "request_sha256": request.request_sha256,
                "capture_sha256": capture.capture_sha256,
            },
            {"proposal_sha256": proposal_hash},
            initial_state,
            proposal_state,
        ),
    ]

    arguments = None
    output = None

    if rejection is not None:
        status = "rejected"
        result_state = {
            "phase": "rejected",
            "reason": rejection,
        }
        events.append(
            _event(
                1,
                EventKind.TERMINATION,
                "agent",
                "reject_proposal",
                {"proposal_sha256": proposal_hash},
                {"reason": rejection},
                proposal_state,
                result_state,
            )
        )
    else:
        arguments = (left, right)

        if selected_tool == "add_ints":
            output = left + right
        elif selected_tool == "multiply_ints":
            output = left * right
        else:
            raise ContractError("allowlist invariant violated")

        status = "executed"

        result_state = {
            "phase": "executed",
            "selected_tool": selected_tool,
            "output": output,
        }

        events.append(
            _event(
                1,
                EventKind.TOOL_CALL,
                selected_tool,
                "invoke",
                {
                    "tool": selected_tool,
                    "arguments": arguments,
                },
                {"output": output},
                proposal_state,
                result_state,
            )
        )

        events.append(
            _event(
                2,
                EventKind.TERMINATION,
                "evaluator",
                "evaluate_addition",
                {"output": output},
                {"correct": output == left + right},
                result_state,
                {
                    "phase": "complete",
                    "correct": output == left + right,
                },
            )
        )

    return CapturedAdditionRun(
        run_id=run_id,
        request_sha256=request.request_sha256,
        capture_sha256=capture.capture_sha256,
        proposal_sha256=proposal_hash,
        status=status,
        rejection_reason=rejection,
        selected_tool=selected_tool,
        arguments=arguments,
        output=output,
        expected_output=left + right,
        trace=AgentTrace(run_id=run_id, events=tuple(events)),
    )


def run_openai_addition_agent(
    *,
    model: str,
    left: int,
    right: int,
    run_id: str,
    api_key: str,
    transport: Transport | None = None,
) -> OpenAIAdditionExecution:
    """Explicit provider invocation; transport=None uses live HTTPS.

    This method never discovers credentials. Offline tests supply a
    transport that returns fixed provider-shaped response bytes.
    """
    _validate_run_id(run_id)

    request = build_addition_request(
        model=model, left=left, right=right,
    )

    provider_result = call_openai_responses(
        request=request,
        api_key=api_key,
        transport=transport,
    )

    agent_run = run_captured_addition_agent(
        request=request,
        capture=provider_result.capture,
        run_id=run_id,
        left=left,
        right=right,
    )

    return OpenAIAdditionExecution(
        provider_result=provider_result,
        agent_run=agent_run,
    )
