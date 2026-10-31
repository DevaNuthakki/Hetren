"""Expose ``ToolGateway`` tools to the OpenAI Agents SDK.

Each gateway tool becomes an SDK ``FunctionTool`` whose handler passes the
model's raw argument text to ``ToolGateway.invoke_raw``. Every call,
including malformed or denied ones, is therefore recorded by the gateway
before anything is returned to the model.

The text returned to the model is deterministic JSON: the observation, the
recorded error, or the denial reason.
"""

from __future__ import annotations

import json
from typing import Any

from agents import FunctionTool

from packages.action_gateway import (
    StageStatus,
    ToolGateway,
    ToolInvocationResult,
    ToolStageRecord,
)


def result_text_from_records(records: tuple[ToolStageRecord, ...]) -> str:
    """The exact text the model receives for one invocation's records."""
    last = records[-1]

    if last.status is StageStatus.SUCCEEDED:
        body: dict[str, object] = {"observation": last.payload["observation"]}
    elif last.status is StageStatus.FAILED:
        body = {"error": last.payload["error"]}
    else:
        body = {"denied": last.payload["reason"]}

    return json.dumps(body, sort_keys=True, ensure_ascii=False)


def tool_result_text(result: ToolInvocationResult) -> str:
    return result_text_from_records(result.records)


def gateway_function_tools(gateway: ToolGateway) -> list[FunctionTool]:
    tools: list[FunctionTool] = []

    for definition in gateway.tool_definitions():
        name = str(definition["name"])

        async def on_invoke_tool(
            context: Any,
            raw_arguments: str,
            *,
            _name: str = name,
        ) -> str:
            return tool_result_text(gateway.invoke_raw(_name, raw_arguments))

        tools.append(
            FunctionTool(
                name=name,
                description=str(definition["description"]),
                params_json_schema=dict(definition["parameters"]),
                on_invoke_tool=on_invoke_tool,
                strict_json_schema=True,
            )
        )

    return tools


__all__ = [
    "gateway_function_tools",
    "result_text_from_records",
    "tool_result_text",
]
