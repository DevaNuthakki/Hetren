"""Run the small model baseline on a split's primary cases (local GPU, no API).

Run on Kaggle (see ``notebooks/milestone-2/qwen_untrained_baseline.ipynb``)
with ``python -m packages.support_evaluator.local_model_baseline``. Each
policy call is one stateless generation with the shared prompt
(``packages.hetren_baselines.prompt``) and the settings in
``packages.hetren_baselines.local_model``; episodes run and are scored
exactly as for ``gpt-4.1``.

Outputs in ``<out>``: ``metadata.json`` (model, revision, dtype, prompt
version, library versions; a restart with different settings stops),
``calls.jsonl`` (every call: tier, dataset and case, since case IDs repeat
across datasets; prompt and reply tokens, finite logits, token limit,
seconds, reply), ``rows-tier<N>.jsonl`` (scored episodes; a restart
skips cases already scored) and ``summary-tier<N>.json`` when the split is
complete. A generation error stops the run and discards that episode.

``--smoke N`` runs a seeded sample of N cases into ``<out>/smoke-tier<N>/``
and checks fp16: it passes when every generated step's logits are finite
and no reply is empty. Parse failures are reported but do not fail it (they
measure the untrained model, not the precision).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys
import time


EXIT_GENERATION_ERROR = 4
EXIT_SMOKE_FAILED = 5
SMOKE_SEED = "smoke"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    from packages.hetren_baselines.local_model import QWEN_MODEL, QWEN_REVISION

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", required=True, type=Path, help="dataset directory (v2 for tier 1, v3 for tier 2)")
    parser.add_argument("--split", required=True, type=Path, help="split file, e.g. docs/milestone-2/splits-v1/validation.txt")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--model", default=QWEN_MODEL)
    parser.add_argument("--revision", default=QWEN_REVISION)
    parser.add_argument("--dtype", default="float16", choices=("float16",), help="fp16 only (protocol)")
    parser.add_argument("--smoke", type=int, help="fp16 smoke test on a seeded sample of this many cases")
    parser.add_argument("--limit", type=int, help="score at most this many new cases")
    return parser.parse_args(argv)


def _cases(dataset: Path, split: Path) -> list[tuple[dict, dict]]:
    members = set(Path(split).read_text(encoding="utf-8").split())
    visible = map(json.loads, (Path(dataset) / "hetren_visible.jsonl").open(encoding="utf-8"))
    evaluator = map(json.loads, (Path(dataset) / "evaluator" / "cases.jsonl").open(encoding="utf-8"))
    return [(v, e) for v, e in zip(visible, evaluator) if v["case_id"] in members and e["role"] == "primary"]


def run_baseline(args: argparse.Namespace, generate, metadata: dict[str, object]) -> int:
    """Score pending cases; ``generate(system, user)`` returns a ``Generation``."""
    from packages.hetren_baselines.prompt import PROMPT_VERSION, action_text, system_prompt, user_message
    from packages.hetren_evidence import render_evidence
    from packages.support_evaluator.episodes import prepare, run_episode, score, summarize

    cases = _cases(args.dataset, args.split)
    tier = 2 if cases and cases[0][1].get("tier", 1) == 2 else 1
    out = Path(args.out)

    if args.smoke is not None:
        cases = sorted(random.Random(f"{SMOKE_SEED}:{tier}").sample(cases, min(args.smoke, len(cases))),
                       key=lambda c: c[0]["case_id"])
        out = out / f"smoke-tier{tier}"

    out.mkdir(parents=True, exist_ok=True)
    metadata = {**metadata, "prompt_version": PROMPT_VERSION}
    metadata_path = out / "metadata.json"

    if metadata_path.exists():
        recorded = json.loads(metadata_path.read_text(encoding="utf-8"))

        if recorded != metadata:
            print("STOP: outputs were written with a different model, settings or libraries", file=sys.stderr)
            return 2
    else:
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rows_path = out / f"rows-tier{tier}.jsonl"
    done = {json.loads(line)["case_id"] for line in rows_path.open(encoding="utf-8")} if rows_path.exists() else set()
    pending = [(v, e) for v, e in cases if v["case_id"] not in done]

    if args.limit is not None:
        pending = pending[: args.limit]

    system = system_prompt(2 if tier == 2 else 1)
    print(f"tier {tier}: {len(cases)} cases, {len(done)} done, scoring {len(pending)}")

    for v, e in pending:
        case_id = v["case_id"]
        halt: list[str] = []
        calls = []

        def policy(compact):
            started = time.perf_counter()

            try:
                generation = generate(system, user_message(render_evidence(compact)))
            except Exception as exc:  # out of memory, driver errors: stop, never score
                halt.append(f"{type(exc).__name__}: {exc}")
                raise

            calls.append({"tier": tier, "dataset": Path(args.dataset).name, "case_id": case_id, "call": len(calls),
                          **generation.payload(),
                          "seconds": round(time.perf_counter() - started, 3)})
            return action_text(generation.text)

        prepared = prepare(v, e)
        episode = run_episode(policy, prepared)

        with (out / "calls.jsonl").open("a", encoding="utf-8") as log:
            log.writelines(json.dumps({**c, "discarded": bool(halt)}) + "\n" for c in calls)

        if halt:
            print(f"STOP at {case_id}: {halt[0]}; this episode is discarded", file=sys.stderr)
            return EXIT_GENERATION_ERROR

        row = score(prepared, episode)

        with rows_path.open("a", encoding="utf-8") as rows:
            rows.write(json.dumps(row, sort_keys=True) + "\n")

        done.add(case_id)
        print(f"{case_id}: {'correct' if row['correct'] else 'wrong'}, {len(calls)} calls")

    if len(done) == len(cases):
        rows = [json.loads(line) for line in rows_path.open(encoding="utf-8")]
        tags = {t["case_id"]: t for t in map(json.loads, (Path(args.dataset) / "evaluator" / "tags.jsonl").open(encoding="utf-8"))}
        (out / f"summary-tier{tier}.json").write_text(json.dumps(summarize(rows, tags), indent=2) + "\n", encoding="utf-8")

    if args.smoke is not None:
        return smoke_report(out, tier)

    print(f"done: {len(done)} of {len(cases)} cases scored")
    return 0


def smoke_report(out: Path, tier: int) -> int:
    calls = [json.loads(line) for line in (out / "calls.jsonl").open(encoding="utf-8")]
    rows = [json.loads(line) for line in (out / f"rows-tier{tier}.jsonl").open(encoding="utf-8")]
    report = {
        "cases": len(rows),
        "calls": len(calls),
        "non_finite_calls": sum(not c["finite"] for c in calls),
        "empty_replies": sum(not c["text"].strip() for c in calls),
        "at_token_limit": sum(c["at_limit"] for c in calls),
        "invalid_action_episodes": sum((r["failure"] or "").startswith("invalid_action") for r in rows),
        "correct": sum(r["correct"] for r in rows),
        "max_prompt_tokens": max((c["prompt_tokens"] for c in calls), default=0),
        "mean_seconds_per_call": round(sum(c["seconds"] for c in calls) / len(calls), 3) if calls else None,
    }
    report["fp16_ok"] = report["non_finite_calls"] == 0 and report["empty_replies"] == 0
    (out / "smoke_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["fp16_ok"] else EXIT_SMOKE_FAILED


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    for path in (args.dataset, args.split):
        if not path.exists():
            print(f"STOP: {path} does not exist", file=sys.stderr)
            return 2

    from packages.hetren_baselines.local_model import MAX_NEW_TOKENS, TransformersModel, library_versions

    model = TransformersModel(args.model, args.revision, args.dtype)
    metadata = {
        "model": args.model, "revision": args.revision, "dtype": args.dtype,
        "max_new_tokens": MAX_NEW_TOKENS, "decoding": "greedy", "libraries": library_versions(),
    }
    return run_baseline(args, model, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
