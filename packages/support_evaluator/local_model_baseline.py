"""Run the small model baseline on a split's primary cases (local GPU, no API).

Run on Kaggle (see ``notebooks/milestone-2/qwen_untrained_baseline.ipynb``
for validation and ``qwen_untrained_test.ipynb`` for the test splits) with
``python -m packages.support_evaluator.local_model_baseline`` and either
``--dataset`` and ``--split`` or ``--live`` (``case_sources``). Each
policy call is one stateless generation with the shared prompt
(``packages.hetren_baselines.prompt``) and the settings in
``packages.hetren_baselines.local_model``; episodes run and are scored
exactly as for ``gpt-4.1``.

Outputs in ``<out>``: ``metadata.json`` (model, revision, dtype, prompt
version, library versions; a restart with different settings stops),
``calls.jsonl`` (every call: tier, dataset and case, since case IDs repeat
across datasets; prompt and reply tokens, finite logits, token limit,
seconds, reply), ``rows-<name>.jsonl`` (scored episodes, named by tier and
split or ``live``; a restart skips cases already scored) and
``summary-<name>.json`` when the split is complete. A generation error stops the run and discards that episode.

It runs on exactly one visible GPU and stops otherwise; the GPU's name is
recorded in the metadata, with the code's commit (``bundle_commit``: from
the Kaggle bundle's ``BUNDLE.json``, else ``git rev-parse HEAD``; the run
stops if neither is available).

``--smoke N`` runs a seeded sample of N cases into ``<out>/smoke-<name>/``
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

from packages.support_evaluator.case_sources import add_source_arguments, load_source, source_arguments_error


REPO_ROOT = Path(__file__).resolve().parents[2]
EXIT_GENERATION_ERROR = 4
EXIT_SMOKE_FAILED = 5
SMOKE_SEED = "smoke"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    from packages.hetren_baselines.local_model import QWEN_MODEL, QWEN_REVISION

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_source_arguments(parser)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--model", default=QWEN_MODEL)
    parser.add_argument("--revision", default=QWEN_REVISION)
    parser.add_argument("--dtype", default="float16", choices=("float16",), help="fp16 only (protocol)")
    parser.add_argument("--smoke", type=int, help="fp16 smoke test on a seeded sample of this many cases")
    parser.add_argument("--limit", type=int, help="score at most this many new cases")
    return parser.parse_args(argv)


def smoke_sample(cases: list, tier: int, size: int) -> list:
    """The seeded smoke-test cases of a tier's source, in case-ID order (also the GGUF pilot's cases)."""
    return sorted(random.Random(f"{SMOKE_SEED}:{tier}").sample(list(cases), min(size, len(cases))),
                  key=lambda c: c.case_id)


def run_baseline(args: argparse.Namespace, generate, metadata: dict[str, object], *, show_results: bool = True) -> int:
    """Score pending cases; ``generate(system, user)`` returns a ``Generation``.

    ``show_results=False`` prints only each case's ID and call count, never whether it was correct (for runs whose
    results are read only after they are logged, such as the GGUF validation run)."""
    from packages.hetren_baselines.prompt import PROMPT_VERSION, action_text, system_prompt, user_message
    from packages.hetren_evidence import render_evidence
    from packages.support_evaluator.episodes import run_episode

    source = load_source(getattr(args, "dataset", None), getattr(args, "split", None), getattr(args, "live", None))
    tier, name, cases = source.tier, source.name, list(source.cases)
    out = Path(args.out)

    if args.smoke is not None:
        cases = smoke_sample(cases, tier, args.smoke)
        out = out / f"smoke-{name}"

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

    rows_path = out / f"rows-{name}.jsonl"
    done = {json.loads(line)["case_id"] for line in rows_path.open(encoding="utf-8")} if rows_path.exists() else set()
    pending = [case for case in cases if case.case_id not in done]

    if args.limit is not None:
        pending = pending[: args.limit]

    system = system_prompt(source.recoveries)
    print(f"{name}: {len(cases)} cases, {len(done)} done, scoring {len(pending)}")

    for case in pending:
        case_id = case.case_id
        halt: list[str] = []
        calls = []

        def policy(compact):
            started = time.perf_counter()

            try:
                generation = generate(system, user_message(render_evidence(compact)))
            except Exception as exc:  # out of memory, driver errors: stop, never score
                halt.append(f"{type(exc).__name__}: {exc}")
                raise

            calls.append({"tier": tier, "dataset": source.dataset["name"], "case_id": case_id, "call": len(calls),
                          **generation.payload(),
                          "seconds": round(time.perf_counter() - started, 3)})
            return action_text(generation.text)

        prepared = case.prepare()
        episode = run_episode(policy, prepared)

        with (out / "calls.jsonl").open("a", encoding="utf-8") as log:
            log.writelines(json.dumps({**c, "discarded": bool(halt)}) + "\n" for c in calls)

        if halt:
            print(f"STOP at {case_id}: {halt[0]}; this episode is discarded", file=sys.stderr)
            return EXIT_GENERATION_ERROR

        row = case.score(prepared, episode)

        with rows_path.open("a", encoding="utf-8") as rows:
            rows.write(json.dumps(row, sort_keys=True) + "\n")

        done.add(case_id)
        print(f"{case_id}: {'correct' if row['correct'] else 'wrong'}, {len(calls)} calls" if show_results
              else f"{case_id}: {len(calls)} calls", flush=True)

    if len(done) == len(cases):
        rows = [json.loads(line) for line in rows_path.open(encoding="utf-8")]
        (out / f"summary-{name}.json").write_text(json.dumps(source.summarize(rows), indent=2) + "\n", encoding="utf-8")

    if args.smoke is not None:
        return smoke_report(out, name)

    print(f"done: {len(done)} of {len(cases)} cases scored")
    return 0


def smoke_report(out: Path, name: str) -> int:
    calls = [json.loads(line) for line in (out / "calls.jsonl").open(encoding="utf-8")]
    rows = [json.loads(line) for line in (out / f"rows-{name}.jsonl").open(encoding="utf-8")]
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


def bundle_commit(root: Path = REPO_ROOT) -> str | None:
    """The commit the code comes from: the bundle's ``BUNDLE.json``, else git, else None."""
    import subprocess

    bundle = Path(root) / "BUNDLE.json"

    if bundle.exists():
        return json.loads(bundle.read_text(encoding="utf-8"))["commit"]

    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True,
                              text=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    error = source_arguments_error(args)

    if error is not None:
        print(f"STOP: {error}", file=sys.stderr)
        return 2

    commit = bundle_commit()

    if commit is None:
        print("STOP: the code's commit is unknown (no BUNDLE.json and no git checkout)", file=sys.stderr)
        return 2

    import torch

    from packages.hetren_baselines.local_model import MAX_NEW_TOKENS, TransformersModel, library_versions

    # The protocol evaluates on one T4; Kaggle's T4 option has two, so the notebook hides the second.
    if torch.cuda.device_count() != 1:
        print(f"STOP: {torch.cuda.device_count()} GPUs visible; exactly one is required (set CUDA_VISIBLE_DEVICES=0)",
              file=sys.stderr)
        return 2

    model = TransformersModel(args.model, args.revision, args.dtype)
    metadata = {
        "model": args.model, "revision": args.revision, "dtype": args.dtype,
        "max_new_tokens": MAX_NEW_TOKENS, "decoding": "greedy", "libraries": library_versions(),
        "gpu": torch.cuda.get_device_name(0), "visible_gpus": 1, "bundle_commit": commit,
    }
    return run_baseline(args, model, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
