#!/usr/bin/env python3
"""Record LIVE model captures for one support-agent run.

This is the only place a live provider call is made. It is never run by
tests or CI, and it refuses to start unless both ``--confirm-live`` is given
and ``OPENAI_API_KEY`` is set. Both checks happen before any client exists.

Each model call is written by ``RecordingModel`` as ``capture-NNNN.json``
(source provenance ``live``) into the output directory, which must be empty
or new so one directory holds exactly one recorded run. Only synthetic
fixture data is used. Fault injection is optional and given explicitly; the
harness that maps runs to examples is responsible for choosing it and for
reporting it to the verifier.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

CONFIRMATION_FLAG = "--confirm-live"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ticket", required=True, help="synthetic ticket ID, e.g. T-1001")
    parser.add_argument("--model", required=True, help="OpenAI model name to record")
    parser.add_argument("--run-id", required=True, help="neutral run ID, run-NNNN")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--swap", nargs=2, metavar=("CUSTOMER_REF_A", "CUSTOMER_REF_B"),
        help="inject an identifier-mapping swap before the run",
    )
    parser.add_argument(CONFIRMATION_FLAG, action="store_true", dest="confirm_live")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if not args.confirm_live:
        print(f"STOP: live recording requires {CONFIRMATION_FLAG}", file=sys.stderr)
        return 2

    if not os.environ.get("OPENAI_API_KEY"):
        print("STOP: OPENAI_API_KEY is not set", file=sys.stderr)
        return 2

    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        print("STOP: output directory must be empty or new", file=sys.stderr)
        return 2

    sys.path.insert(0, str(REPO_ROOT))

    from functools import partial

    from agents import OpenAIResponsesModel
    from openai import AsyncOpenAI

    from environments.support.faults import IdentifierMappingSwap, inject_fault
    from environments.support.fixtures import SupportEnvironment
    from environments.support.tools import (
        SUPPORT_TOOL_DESCRIPTIONS,
        SUPPORT_TOOL_SCHEMAS,
        SUPPORT_TOOLS,
    )
    from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
    from packages.integrations.openai_agents import (
        CaptureStore,
        RecordingModel,
        RunProvenance,
        gateway_function_tools,
        run_agent,
    )
    from packages.support_agent import build_support_agent, task_message

    environment = SupportEnvironment()

    if args.swap:
        inject_fault(environment, IdentifierMappingSwap(*args.swap))

    gateway = ToolGateway(
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
    model = RecordingModel(
        inner=OpenAIResponsesModel(model=args.model, openai_client=AsyncOpenAI()),
        store=CaptureStore(args.output_dir),
        source_provenance=RunProvenance.LIVE,
        source_model_id=args.model,
    )
    record = run_agent(
        agent=build_support_agent(
            environment=environment, tools=gateway_function_tools(gateway), model=model,
        ),
        task_input=task_message(args.ticket),
        gateway=gateway,
        run_id=args.run_id,
        provenance=RunProvenance.LIVE,
    )

    print(f"run {record.run_id}: {record.status.value}")
    print(f"captures: {', '.join(record.recorded_capture_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
