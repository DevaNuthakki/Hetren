"""Run the frozen rules baseline (rules v1) on a split or the live split (offline, free).

``python -m packages.support_evaluator.rules_baseline --out <dir> --processes <n>``
with either ``--dataset`` and ``--split`` or ``--live`` (``case_sources``).
Rules v1 runs as a single-recovery policy in both tiers
(EVAL_PROTOCOL.md, "Rules baseline (v1)"): its episode ends at its first
recovery, which counts as an implicit stop in tier 2.

Outputs in ``<out>``: ``metadata.json`` (rules version, policy settings and
the code's commit; a restart with different metadata stops),
``rows-<name>.jsonl`` (scored episodes in case order, named by tier and
split or ``live``; a restart skips cases already scored) and
``summary-<name>.json`` when the split is complete.
"""

from __future__ import annotations

import argparse
import json
from multiprocessing import get_context
from pathlib import Path
import sys

from packages.support_evaluator.case_sources import add_source_arguments, load_source, source_arguments_error


MAX_RECOVERIES = 1  # rules v1 is a single-recovery policy in both tiers

_SOURCE = None


def _init(dataset, split, live) -> None:
    global _SOURCE
    _SOURCE = load_source(dataset, split, live)


def _run(index: int) -> dict:
    from packages.hetren_baselines import rules_policy
    from packages.support_evaluator.episodes import run_episode

    case = _SOURCE.cases[index]
    prepared = case.prepare()
    return case.score(prepared, run_episode(rules_policy, prepared, max_recoveries=MAX_RECOVERIES))


def run_rules(args: argparse.Namespace, metadata: dict[str, object]) -> int:
    source = load_source(args.dataset, args.split, args.live)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    metadata_path = out / "metadata.json"

    if metadata_path.exists():
        if json.loads(metadata_path.read_text(encoding="utf-8")) != metadata:
            print("STOP: outputs were written with a different rules version, settings or code", file=sys.stderr)
            return 2
    else:
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rows_path = out / f"rows-{source.name}.jsonl"
    done = {json.loads(line)["case_id"] for line in rows_path.open(encoding="utf-8")} if rows_path.exists() else set()
    pending = [i for i, case in enumerate(source.cases) if case.case_id not in done]
    print(f"{source.name}: {len(source.cases)} cases, {len(done)} done, scoring {len(pending)}", flush=True)

    with get_context("spawn").Pool(args.processes, initializer=_init, initargs=(args.dataset, args.split, args.live)) as pool:
        with rows_path.open("a", encoding="utf-8") as rows:
            for count, row in enumerate(pool.imap(_run, pending, chunksize=1), 1):
                rows.write(json.dumps(row, sort_keys=True) + "\n")
                rows.flush()

                if count % 100 == 0:
                    print(f"scored {count}/{len(pending)}", flush=True)

    rows = [json.loads(line) for line in rows_path.open(encoding="utf-8")]

    if len(rows) == len(source.cases):
        (out / f"summary-{source.name}.json").write_text(json.dumps(source.summarize(rows), indent=2) + "\n",
                                                          encoding="utf-8")

    print(f"done: {len(rows)} of {len(source.cases)} cases scored")
    return 0


def main(argv: list[str] | None = None) -> int:
    from packages.hetren_baselines import RULES_POLICY_VERSION
    from packages.support_evaluator.local_model_baseline import bundle_commit

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_source_arguments(parser)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--processes", type=int, default=1)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    error = source_arguments_error(args)

    if error is not None:
        print(f"STOP: {error}", file=sys.stderr)
        return 2

    commit = bundle_commit()

    if commit is None:
        print("STOP: the code's commit is unknown", file=sys.stderr)
        return 2

    metadata = {"policy": "rules", "rules_policy_version": RULES_POLICY_VERSION,
                "max_recoveries": MAX_RECOVERIES, "commit": commit}
    return run_rules(args, metadata)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_RECOVERIES",
    "run_rules",
]
