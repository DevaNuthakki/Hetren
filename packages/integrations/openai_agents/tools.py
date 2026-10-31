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
)


def tool_result_text(result: ToolInvocationResult) -> str:
    if result.status is StageStatus.SUCCEEDED:
        body: dict[str, object] = {"observation": result.observation}
    elif result.status is StageStatus.FAILED:
        body = {"error": result.error}
    else:
        body = {"denied": result.records[-1].payload["reason"]}

    return json.dumps(body, sort_keys=True, ensure_ascii=False)


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
    "tool_result_text",
]
