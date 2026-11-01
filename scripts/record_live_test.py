#!/usr/bin/env python3
"""Record LIVE support-agent runs for the Milestone 2 live test split.

This makes live provider calls. It is never run by tests or CI, and it
refuses to start unless ``--confirm-live`` and ``--max-usd`` are given and
``OPENAI_API_KEY`` is set; all three checks happen before any client exists.

Input is the ``specs/`` directory written by ``packages.support_evaluator.live``:
one neutral world spec and ticket ID per run ID. This script never sees case
kinds, variants or truth. Each run is recorded with ``store=False`` and a
300-token output limit into ``<captures>/<run-id>/`` (captures only, one run
per directory).

Spending cap: before every model call the projected spend (provider-reported
spend so far, plus the estimated input with a 10% margin and the full output
limit, at the given prices) is checked against ``--max-usd``; if it would pass
the cap, nothing is sent, the partial run is moved to ``_aborted/`` and the
script stops. ``ledger.json`` records usage after every call, so a restart
resumes after the last completed run and the cap covers all runs together.
Cached input is charged at the full input price, so real spend is lower.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

CONFIRMATION_FLAG = "--confirm-live"
DEFAULT_INPUT_USD_PER_MTOK = 0.40
DEFAULT_OUTPUT_USD_PER_MTOK = 1.60
EXIT_BUDGET = 3


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--specs", required=True, type=Path, help="specs/ directory of the live test export")
    parser.add_argument("--captures", required=True, type=Path, help="capture root (one directory per run)")
    parser.add_argument("--model", required=True, help="OpenAI model name, e.g. gpt-4.1-mini-2025-04-14")
    parser.add_argument("--max-usd", type=float, help="hard spending cap for all runs in --captures together")
    parser.add_argument("--limit", type=int, help="record at most this many new runs (pilot)")
    parser.add_argument("--input-usd-per-mtok", type=float, default=DEFAULT_INPUT_USD_PER_MTOK)
    parser.add_argument("--output-usd-per-mtok", type=float, default=DEFAULT_OUTPUT_USD_PER_MTOK)
    parser.add_argument(CONFIRMATION_FLAG, action="store_true", dest="confirm_live")
    return parser.parse_args(argv)


def record_runs(args: argparse.Namespace, inner_factory, encoding) -> int:
    """Record pending runs; ``inner_factory()`` returns a fresh live model."""
    sys.path.insert(0, str(REPO_ROOT))

    from functools import partial

    from environments.support.fixtures import SupportEnvironment, WorldSpec
    from environments.support.tools import SUPPORT_TOOL_DESCRIPTIONS, SUPPORT_TOOL_SCHEMAS, SUPPORT_TOOLS
    from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
    from packages.integrations.openai_agents import (
        CaptureStore,
        RecordingModel,
        RunProvenance,
        gateway_function_tools,
        run_agent,
    )
    from packages.integrations.openai_agents.budget import BudgetExceeded, BudgetedModel, Prices, SpendLedger
    from packages.support_agent import LIVE_TEST_MODEL_SETTINGS, build_support_agent, task_message

    captures = Path(args.captures)
    captures.mkdir(parents=True, exist_ok=True)
    ledger_path = captures / "ledger.json"
    prices = Prices(args.input_usd_per_mtok, args.output_usd_per_mtok)
    ledger = SpendLedger(cap_usd=args.max_usd, prices=prices)
    completed: dict[str, dict] = {}

    if ledger_path.exists():
        saved = json.loads(ledger_path.read_text(encoding="utf-8"))

        if saved["model"] != args.model or saved["spend"]["prices"] != ledger.payload()["prices"]:
            print("STOP: ledger was written for a different model or prices", file=sys.stderr)
            return 2

        ledger.input_tokens = saved["spend"]["input_tokens"]
        ledger.output_tokens = saved["spend"]["output_tokens"]
        ledger.calls = saved["spend"]["calls"]
        completed = saved["completed"]

    def save() -> None:
        document = {"model": args.model, "spend": ledger.payload(), "completed": completed}
        ledger_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    specs = sorted(Path(args.specs).glob("run-*.json"))
    pending = [path for path in specs if path.stem not in completed]

    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"runs: {len(specs)} total, {len(completed)} done, recording {len(pending)}")
    print(f"spent so far ${ledger.spent_usd:.4f} of ${ledger.cap_usd:.2f} cap")

    for path in pending:
        spec = json.loads(path.read_text(encoding="utf-8"))
        run_id = spec["run_id"]
        run_dir = captures / run_id

        if run_dir.exists() and any(run_dir.iterdir()):
            print(f"STOP: {run_dir} is not empty and not in the ledger", file=sys.stderr)
            return 2

        environment = SupportEnvironment(WorldSpec.from_payload(spec["world"]))
        gateway = ToolGateway(
            tools=[
                GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
                for name, f in SUPPORT_TOOLS.items()
            ],
            policy=AllowListPolicy(SUPPORT_TOOLS),
            state_sha256=environment.state_sha256,
        )
        model = RecordingModel(
            inner=BudgetedModel(inner=inner_factory(), ledger=ledger, encoding=encoding, on_charge=lambda _: save()),
            store=CaptureStore(run_dir),
            source_provenance=RunProvenance.LIVE,
            source_model_id=args.model,
        )

        record = run_agent(
            agent=build_support_agent(
                environment=environment, tools=gateway_function_tools(gateway),
                model=model, model_settings=LIVE_TEST_MODEL_SETTINGS,
            ),
            task_input=task_message(spec["ticket_id"]),
            gateway=gateway,
            run_id=run_id,
            provenance=RunProvenance.LIVE,
        )

        # run_agent records model exceptions in the run instead of raising them.
        if (record.error or {}).get("type") == BudgetExceeded.__name__:
            aborted = captures / "_aborted" / f"{run_id}-after-{ledger.calls}-calls"

            if run_dir.exists():
                aborted.parent.mkdir(exist_ok=True)
                run_dir.rename(aborted)

            save()
            print(f"STOP at {run_id}: the next call could pass the ${ledger.cap_usd:.2f} cap; nothing was sent", file=sys.stderr)
            print(f"spent ${ledger.spent_usd:.4f}; {len(completed)} runs complete")
            return EXIT_BUDGET

        completed[run_id] = {"status": record.status.value, "calls": len(model.recorded_capture_ids)}
        save()
        print(f"{run_id}: {record.status.value}, {len(model.recorded_capture_ids)} calls, spent ${ledger.spent_usd:.4f}")

    print(f"done: {len(completed)} of {len(specs)} runs complete, spent ${ledger.spent_usd:.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if not args.confirm_live:
        print(f"STOP: live recording requires {CONFIRMATION_FLAG}", file=sys.stderr)
        return 2

    if args.max_usd is None or args.max_usd <= 0:
        print("STOP: live recording requires a positive --max-usd cap", file=sys.stderr)
        return 2

    if not os.environ.get("OPENAI_API_KEY"):
        print("STOP: OPENAI_API_KEY is not set", file=sys.stderr)
        return 2

    if not args.specs.is_dir():
        print(f"STOP: {args.specs} is not a directory", file=sys.stderr)
        return 2

    import tiktoken
    from agents import OpenAIResponsesModel
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    return record_runs(
        args,
        inner_factory=lambda: OpenAIResponsesModel(model=args.model, openai_client=client),
        encoding=tiktoken.get_encoding("o200k_base"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
