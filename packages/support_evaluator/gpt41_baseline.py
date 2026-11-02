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

``<out>/ledger.json`` records usage after every call; ``<out>/calls.jsonl``
logs every call (case, usage, reply); ``<out>/rows-tier<N>.jsonl`` holds the
scored episodes. A restart skips cases already scored, and one cap covers
everything in ``<out>``. ``<out>/summary-tier<N>.json`` is written when a
split completes.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

CONFIRMATION_FLAG = "--confirm-live"
DEFAULT_MODEL = "gpt-4.1-2025-04-14"
DEFAULT_INPUT_USD_PER_MTOK = 2.00
DEFAULT_OUTPUT_USD_PER_MTOK = 8.00
MAX_OUTPUT_TOKENS = 128
# Role and message framing added by the API on top of the two messages' text.
CALL_OVERHEAD_TOKENS = 10
EXIT_BUDGET = 3
EXIT_API_ERROR = 4


class Halt(Exception):
    """Stop the run; the current episode is discarded."""


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", required=True, type=Path, help="dataset directory (v2 for tier 1, v3 for tier 2)")
    parser.add_argument("--split", required=True, type=Path, help="split file, e.g. docs/milestone-2/splits-v1/validation.txt")
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
    from packages.support_evaluator.episodes import prepare, run_episode, score, summarize

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

    members = set(Path(args.split).read_text(encoding="utf-8").split())
    visible = map(json.loads, (Path(args.dataset) / "hetren_visible.jsonl").open(encoding="utf-8"))
    evaluator = map(json.loads, (Path(args.dataset) / "evaluator" / "cases.jsonl").open(encoding="utf-8"))
    cases = [(v, e) for v, e in zip(visible, evaluator) if v["case_id"] in members and e["role"] == "primary"]
    tier = 2 if cases and cases[0][1].get("tier", 1) == 2 else 1
    rows_path = out / f"rows-tier{tier}.jsonl"
    done = {json.loads(line)["case_id"] for line in rows_path.open(encoding="utf-8")} if rows_path.exists() else set()
    pending = [(v, e) for v, e in cases if v["case_id"] not in done]

    if args.limit is not None:
        pending = pending[: args.limit]

    system = system_prompt(2 if tier == 2 else 1)
    system_tokens = len(encoding.encode(system))
    print(f"tier {tier}: {len(cases)} cases, {len(done)} done, scoring {len(pending)}")
    print(f"spent so far ${ledger.spent_usd:.4f} of ${ledger.cap_usd:.2f} cap")

    for v, e in pending:
        case_id = v["case_id"]
        halt: list[tuple[int, str]] = []
        calls = []

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
                "case_id": case_id, "call": len(calls), "estimate": estimate,
                "input_tokens": usage.input_tokens, "cached_tokens": getattr(details, "cached_tokens", None),
                "output_tokens": usage.output_tokens, "at_output_limit": usage.output_tokens >= MAX_OUTPUT_TOKENS,
                "reply": response.output_text,
            })
            return action_text(response.output_text or "")

        prepared = prepare(v, e)
        episode = run_episode(policy, prepared)

        with (out / "calls.jsonl").open("a", encoding="utf-8") as log:
            log.writelines(json.dumps({**c, "discarded": bool(halt)}) + "\n" for c in calls)

        if halt:
            code, reason = halt[0]
            print(f"STOP at {case_id}: {reason}; this episode is discarded", file=sys.stderr)
            print(f"spent ${ledger.spent_usd:.4f}; {len(done)} cases scored")
            return code

        row = score(prepared, episode)

        with rows_path.open("a", encoding="utf-8") as rows:
            rows.write(json.dumps(row, sort_keys=True) + "\n")

        done.add(case_id)
        print(f"{case_id}: {'correct' if row['correct'] else 'wrong'}, {len(calls)} calls, spent ${ledger.spent_usd:.4f}")

    if len(done) == len(cases):
        rows = [json.loads(line) for line in rows_path.open(encoding="utf-8")]
        tags = {t["case_id"]: t for t in map(json.loads, (Path(args.dataset) / "evaluator" / "tags.jsonl").open(encoding="utf-8"))}
        summary = summarize(rows, tags)
        (out / f"summary-tier{tier}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"done: {len(done)} of {len(cases)} cases scored, spent ${ledger.spent_usd:.4f}")
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

    for path in (args.dataset, args.split):
        if not path.exists():
            print(f"STOP: {path} does not exist", file=sys.stderr)
            return 2

    import tiktoken
    from openai import OpenAI

    client = OpenAI()
    return run_baseline(args, client.responses.create, tiktoken.get_encoding("o200k_base"))


if __name__ == "__main__":
    raise SystemExit(main())
