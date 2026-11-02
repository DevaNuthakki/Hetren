"""Run the ``gpt-4.1`` baseline on a split's primary cases (LIVE calls).

This makes live provider calls. It is never run by tests or CI, and it
refuses to start unless ``--confirm-live`` and ``--max-usd`` are given and
``OPENAI_API_KEY`` is set; all three checks happen before any client exists.

Each policy call is one stateless Responses API request: the shared system
prompt (``packages.hetren_baselines.prompt``) and the step's rendered
compact evidence, with ``store=False``, temperature 0 and a 128-token
output limit. Episodes run through ``packages.support_evaluator.episodes``
(probes on forks, tier 2 recoveries applied by the harness) and are scored
by execution. Run with ``python -m packages.support_evaluator.gpt41_baseline``
(the evaluator drives episodes, so the runner lives inside it).

Spending cap: before every call the projected spend (provider-reported
spend so far, plus the exact o200k_base token count of both messages and a
formatting allowance, with a 10% margin, plus the full output limit, at the
given prices) is checked against ``--max-usd``; if it would pass the cap,
nothing is sent, the episode is discarded and the script stops. Cached input
is charged at the full input price, so real spend is lower. API errors also
stop the script (they never count as model failures).

``<out>/ledger.json`` records usage after every call and the one dataset
used for each tier (a different dataset for a tier in the same ``<out>``
stops the script); ``<out>/calls.jsonl`` logs every call (tier, dataset,
case, usage, reply); ``<out>/rows-tier<N>-<split>.jsonl`` holds the scored episodes
(``rows-live.jsonl`` for the live split, given with ``--live`` instead of
``--dataset`` and ``--split``: live runs are replayed from their captures
and scored by their label category, see ``live_episodes``).
Case IDs repeat across datasets, so calls are matched to cases by tier,
dataset and case ID together. A restart skips cases already scored, and one
cap covers everything in ``<out>``. A case whose calls were logged (not
discarded) but which has no scored row, because the run stopped while
scoring it, is replayed from its logged replies without new calls, so
nothing is paid twice; if the replayed episode asks for a different number
of calls, the script stops. ``<out>/summary-tier<N>-<split>.json`` (``summary-live.json``)
is written when a split completes.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from packages.support_evaluator.case_sources import add_source_arguments, source_arguments_error

CONFIRMATION_FLAG = "--confirm-live"
DEFAULT_MODEL = "gpt-4.1-2025-04-14"
DEFAULT_INPUT_USD_PER_MTOK = 2.00
DEFAULT_OUTPUT_USD_PER_MTOK = 8.00
MAX_OUTPUT_TOKENS = 128
# Role and message framing added by the API on top of the two messages' text.
CALL_OVERHEAD_TOKENS = 10
EXIT_BUDGET = 3
EXIT_API_ERROR = 4
EXIT_REPLAY_MISMATCH = 5


class Halt(Exception):
    """Stop the run; the current episode is discarded."""


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_source_arguments(parser)
    parser.add_argument("--out", required=True, type=Path, help="output directory (holds ledger.json)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-usd", type=float, help="hard spending cap for everything in the ledger together")
    parser.add_argument("--limit", type=int, help="score at most this many new cases (pilot)")
    parser.add_argument("--input-usd-per-mtok", type=float, default=DEFAULT_INPUT_USD_PER_MTOK)
    parser.add_argument("--output-usd-per-mtok", type=float, default=DEFAULT_OUTPUT_USD_PER_MTOK)
    parser.add_argument(CONFIRMATION_FLAG, action="store_true", dest="confirm_live")
    return parser.parse_args(argv)


def run_baseline(args: argparse.Namespace, create, encoding) -> int:
    """Score pending cases; ``create(**request)`` sends one Responses API request."""
    from packages.hetren_baselines.prompt import PROMPT_VERSION, action_text, system_prompt, user_message
    from packages.hetren_evidence import render_evidence
    from packages.integrations.openai_agents.budget import INPUT_SAFETY_FACTOR, Prices, SpendLedger
    from packages.support_evaluator.case_sources import load_source
    from packages.support_evaluator.episodes import run_episode

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ledger_path = out / "ledger.json"
    prices = Prices(args.input_usd_per_mtok, args.output_usd_per_mtok)
    ledger = SpendLedger(cap_usd=args.max_usd, prices=prices)
    document: dict = {"model": args.model, "prompt_version": PROMPT_VERSION}

    if ledger_path.exists():
        document = json.loads(ledger_path.read_text(encoding="utf-8"))

        if (document["model"], document["prompt_version"]) != (args.model, PROMPT_VERSION) or (
            document["spend"]["prices"] != ledger.payload()["prices"]
        ):
            print("STOP: ledger was written for a different model, prompt or prices", file=sys.stderr)
            return 2

        ledger.input_tokens = document["spend"]["input_tokens"]
        ledger.output_tokens = document["spend"]["output_tokens"]
        ledger.calls = document["spend"]["calls"]

    def save() -> None:
        document["spend"] = ledger.payload()
        ledger_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    source = load_source(getattr(args, "dataset", None), getattr(args, "split", None), getattr(args, "live", None))
    tier, name, dataset = source.tier, source.name, source.dataset

    # Rows and summaries are per split: several splits of one tier can share an output directory and its cap.
    if tier != "live" and (out / f"rows-tier{tier}.jsonl").exists():
        print(f"STOP: {out} holds rows written before rows were named by split; use a new --out", file=sys.stderr)
        return 2

    recorded = document.setdefault("datasets", {}).setdefault(str(tier), dataset)

    if recorded != dataset:
        print(f"STOP: {out} holds {name} results for dataset {recorded['name']}, not {dataset['name']}", file=sys.stderr)
        return 2

    rows_path = out / f"rows-{name}.jsonl"
    done = {json.loads(line)["case_id"] for line in rows_path.open(encoding="utf-8")} if rows_path.exists() else set()
    pending = [case for case in source.cases if case.case_id not in done]

    if args.limit is not None:
        pending = pending[: args.limit]

    # Paid calls of this tier's cases that were never scored (the run stopped while scoring).
    logged: dict[str, list[dict]] = {}

    if (out / "calls.jsonl").exists():
        for line in (out / "calls.jsonl").open(encoding="utf-8"):
            call = json.loads(line)

            if "tier" not in call:
                print("STOP: calls.jsonl has calls without tier and dataset; annotate them first", file=sys.stderr)
                return 2

            if (call["tier"], call["dataset_sha256"]) != (tier, dataset["visible_sha256"]):
                continue

            if not call["discarded"] and call["case_id"] not in done:
                logged.setdefault(call["case_id"], []).append(call)

    system = system_prompt(source.recoveries)
    system_tokens = len(encoding.encode(system))
    print(f"{name}: {len(source.cases)} cases, {len(done)} done, scoring {len(pending)}")
    print(f"spent so far ${ledger.spent_usd:.4f} of ${ledger.cap_usd:.2f} cap")

    for case in pending:
        case_id = case.case_id
        halt: list[tuple[int, str]] = []
        calls = []
        replay = logged.get(case_id)

        def replayed(compact):
            if len(calls) == len(replay):
                halt.append((EXIT_REPLAY_MISMATCH, f"the replayed episode asked for more than {len(replay)} logged calls"))
                raise Halt

            calls.append(replay[len(calls)])
            return action_text(calls[-1]["reply"] or "")

        def policy(compact):
            user = user_message(render_evidence(compact))
            estimate = system_tokens + len(encoding.encode(user)) + CALL_OVERHEAD_TOKENS
            projected = ledger.spent_usd + prices.cost(estimate * INPUT_SAFETY_FACTOR, MAX_OUTPUT_TOKENS)

            if projected > ledger.cap_usd:
                halt.append((EXIT_BUDGET, f"next call could reach ${projected:.4f}, over the ${ledger.cap_usd:.2f} cap"))
                raise Halt

            try:
                response = create(
                    model=args.model, instructions=system, input=user,
                    max_output_tokens=MAX_OUTPUT_TOKENS, temperature=0, store=False,
                )
            except Exception as exc:  # network, rate limit, refusal by the API: stop, never score
                halt.append((EXIT_API_ERROR, f"{type(exc).__name__}: {exc}"))
                raise Halt from exc

            usage = response.usage
            ledger.charge(int(usage.input_tokens or 0), int(usage.output_tokens or 0))
            save()
            details = getattr(usage, "input_tokens_details", None)
            calls.append({
                "tier": tier, "dataset": dataset["name"], "dataset_sha256": dataset["visible_sha256"],
                "case_id": case_id, "call": len(calls), "estimate": estimate,
                "input_tokens": usage.input_tokens, "cached_tokens": getattr(details, "cached_tokens", None),
                "output_tokens": usage.output_tokens, "at_output_limit": usage.output_tokens >= MAX_OUTPUT_TOKENS,
                "reply": response.output_text,
            })
            return action_text(response.output_text or "")

        prepared = case.prepare()
        episode = run_episode(replayed if replay else policy, prepared)

        if replay and not halt and len(calls) != len(replay):
            halt.append((EXIT_REPLAY_MISMATCH, f"the replayed episode used {len(calls)} of {len(replay)} logged calls"))

        if not replay:
            with (out / "calls.jsonl").open("a", encoding="utf-8") as log:
                log.writelines(json.dumps({**c, "discarded": bool(halt)}) + "\n" for c in calls)

        if halt:
            code, reason = halt[0]
            print(f"STOP at {case_id}: {reason}; this episode is discarded", file=sys.stderr)
            print(f"spent ${ledger.spent_usd:.4f}; {len(done)} cases scored")
            return code

        row = case.score(prepared, episode)

        with rows_path.open("a", encoding="utf-8") as rows:
            rows.write(json.dumps(row, sort_keys=True) + "\n")

        done.add(case_id)
        replayed_note = " (replayed from the call log, no new calls)" if replay else ""
        print(f"{case_id}: {'correct' if row['correct'] else 'wrong'}, {len(calls)} calls{replayed_note}, spent ${ledger.spent_usd:.4f}")

    if len(done) == len(source.cases):
        rows = [json.loads(line) for line in rows_path.open(encoding="utf-8")]
        (out / f"summary-{name}.json").write_text(json.dumps(source.summarize(rows), indent=2) + "\n", encoding="utf-8")

    print(f"done: {len(done)} of {len(source.cases)} cases scored, spent ${ledger.spent_usd:.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if not args.confirm_live:
        print(f"STOP: live calls require {CONFIRMATION_FLAG}", file=sys.stderr)
        return 2

    if args.max_usd is None or args.max_usd <= 0:
        print("STOP: live calls require a positive --max-usd cap", file=sys.stderr)
        return 2

    if not os.environ.get("OPENAI_API_KEY"):
        print("STOP: OPENAI_API_KEY is not set", file=sys.stderr)
        return 2

    error = source_arguments_error(args)

    if error is not None:
        print(f"STOP: {error}", file=sys.stderr)
        return 2

    import tiktoken
    from openai import OpenAI

    client = OpenAI()
    return run_baseline(args, client.responses.create, tiktoken.get_encoding("o200k_base"))


if __name__ == "__main__":
    raise SystemExit(main())
