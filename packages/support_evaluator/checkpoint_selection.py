"""Checkpoint selection for the fine-tuned Qwen3-4B (EVAL_PROTOCOL.md, Amendment 1), validation only.

``evaluate`` runs one candidate checkpoint on the 300-case selection subset
(``docs/milestone-3/selection-subset-v1``) on one GPU:

- the checkpoint's ``state.json`` must have the sha256 logged when it was
  saved, and its adapter files the hashes ``state.json`` lists;
- the adapter is merged into the fp16 base and evaluated with the declared
  settings (``packages.hetren_baselines.local_model``), one generation at a
  time, through ``local_model_baseline.run_baseline``: the same prompt,
  episodes, scoring, call log and resumable rows as the untrained baseline;
- the fp16 smoke test first (10 seeded subset cases per tier): every
  generated step's logits finite and no reply empty, else the subset run
  does not start;
- then the 200 tier 1 and 100 tier 2 subset cases, and
  ``<out>/selection.json``: S = ½(A₁ + A₂) − W with the monitored rates
  (``selection_subset.selection_score``), the checkpoint's step and hashes,
  the run's metadata and every output file's sha256.

A restart with the same ``--out`` resumes (cases already scored are kept);
a restart with other settings, libraries or adapter stops.

``choose`` reads the four ``selection.json`` files, checks they are the four
declared candidates evaluated on the same platform, GPU type, library
versions and bundle commit, and applies the rule: the highest S, exact ties
to the earlier checkpoint. It writes ``choice.json`` with the untrained
reference S (0.1947, logged before any checkpoint was evaluated) for
comparison; the comparison never changes the choice.

Commands::

    python -m packages.support_evaluator.checkpoint_selection evaluate \\
        --checkpoint <checkpoint-0264> --state-sha256 <sha256> --out <root>/checkpoint-0264
    python -m packages.support_evaluator.checkpoint_selection choose --out <root>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from packages.support_evaluator.case_sources import load_source
from packages.support_evaluator.local_model_baseline import EXIT_SMOKE_FAILED, bundle_commit, run_baseline
from packages.support_evaluator.selection_subset import (
    REPO_ROOT, SIZES, SOURCES, SUBSET_DIR, selection_score, subset_rows,
)


CANDIDATE_STEPS = (264, 528, 792, 1055)
SMOKE_CASES = 10  # per tier: the protocol's 20-case fp16 smoke test
REFERENCE_S = 0.1947  # untrained Qwen3-4B on the same subset (VALIDATION_LOG.md)
ADAPTER_FILES = ("adapter/adapter_config.json", "adapter/adapter_model.safetensors")
SAME_FOR_ALL = ("platform", "gpu", "visible_gpus", "libraries", "bundle_commit", "model", "revision", "dtype",
                "max_new_tokens", "decoding", "prompt_version")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


def verify_adapter(checkpoint: Path, state_sha256: str) -> dict[str, object]:
    """The candidate's step and hashes, after checking ``state.json`` and the adapter files against them."""
    checkpoint = Path(checkpoint)
    state_path = checkpoint / "state.json"

    if sha256_file(state_path) != state_sha256.strip():
        raise ValueError(f"{state_path} does not have the logged sha256 {state_sha256}")

    state = json.loads(state_path.read_text(encoding="utf-8"))

    for name in ADAPTER_FILES:
        if sha256_file(checkpoint / name) != state["files"][name]:
            raise ValueError(f"{checkpoint / name} does not match its sha256 in state.json")

    if not state.get("candidate") or state["step"] not in CANDIDATE_STEPS:
        raise ValueError(f"{checkpoint} is not one of the declared candidates {CANDIDATE_STEPS}")

    return {"checkpoint": f"checkpoint-{state['step']:04d}", "step": state["step"], "state_sha256": state_sha256.strip(),
            "adapter_sha256": state["files"]["adapter/adapter_model.safetensors"],
            "adapter_config_sha256": state["files"]["adapter/adapter_config.json"],
            "training_bundle_commit": state["bundle_commit"]}


def _source_args(tier: int, out: Path, root: Path, subset_dir: Path, smoke: int | None) -> argparse.Namespace:
    return argparse.Namespace(dataset=Path(root) / SOURCES[tier][0], split=Path(subset_dir) / f"tier{tier}.txt",
                              live=None, out=out, smoke=smoke, limit=None)


def evaluate(candidate: dict[str, object], out: Path, generate, metadata: dict[str, object], *, root: Path = REPO_ROOT,
             subset_dir: Path = SUBSET_DIR, sizes: dict[int, int] = SIZES) -> int:
    """Smoke test, then the subset cases of both tiers; writes ``selection.json`` when both are complete."""
    out = Path(out)
    metadata = {**metadata, "candidate": candidate}

    for tier in (1, 2):  # fp16 smoke test first
        code = run_baseline(_source_args(tier, out, root, subset_dir, SMOKE_CASES), generate, metadata)

        if code != 0:
            reason = "did not pass" if code == EXIT_SMOKE_FAILED else f"stopped (exit {code})"
            print(f"STOP: the fp16 smoke test {reason} on tier {tier}; the subset run does not start", file=sys.stderr)
            return code

    rows = {}

    for tier in (1, 2):
        args = _source_args(tier, out, root, subset_dir, None)
        code = run_baseline(args, generate, metadata)

        if code != 0:
            return code

        rows[tier] = out / f"rows-{load_source(args.dataset, args.split).name}.jsonl"

    scored = {tier: subset_rows(rows[tier], tier, subset_dir) for tier in (1, 2)}

    if {tier: len(r) for tier, r in scored.items()} != sizes:
        print(f"STOP: expected {sizes} subset cases, found {({t: len(r) for t, r in scored.items()})}", file=sys.stderr)
        return 2

    calls = [json.loads(line) for line in (out / "calls.jsonl").open(encoding="utf-8")]
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "selection.json")
    result = {
        **candidate,
        **selection_score(scored[1], scored[2]),
        "cases": {f"tier{t}": len(scored[t]) for t in (1, 2)},
        "subset_lists": {f"tier{t}": sha256_file(Path(subset_dir) / f"tier{t}.txt") for t in (1, 2)},
        "calls": {"total": len(calls), "non_finite": sum(not c["finite"] for c in calls),
                  "empty": sum(not c["text"].strip() for c in calls), "at_token_limit": sum(c["at_limit"] for c in calls),
                  "discarded": sum(c.get("discarded", False) for c in calls),
                  "seconds": round(sum(c["seconds"] for c in calls), 1)},
        "metadata": json.loads((out / "metadata.json").read_text(encoding="utf-8")),
        "files": {p.relative_to(out).as_posix(): sha256_file(p) for p in files},
    }
    (out / "selection.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("checkpoint", "S", "A1", "A2", "W")}, indent=2))
    return 0


def choose(results: list[dict[str, object]]) -> dict[str, object]:
    """Amendment 1's rule over the four candidates: the highest S; exact ties go to the earlier checkpoint."""
    steps = sorted(r["step"] for r in results)

    if steps != list(CANDIDATE_STEPS):
        raise ValueError(f"expected one result for each of {CANDIDATE_STEPS}, found {steps}")

    for key in SAME_FOR_ALL:
        values = {json.dumps(r["metadata"].get(key), sort_keys=True) for r in results}

        if len(values) != 1:
            raise ValueError(f"the candidates were not evaluated with the same {key}: {sorted(values)}")

    ordered = sorted(results, key=lambda r: r["step"])
    best = max(ordered, key=lambda r: r["S"])  # max keeps the first (earliest) of equal values
    return {
        "chosen": best["checkpoint"], "step": best["step"], "S": best["S"],
        "state_sha256": best["state_sha256"], "adapter_sha256": best["adapter_sha256"],
        "candidates": [{k: r[k] for k in ("checkpoint", "step", "S", "A1", "A2", "W", "monitoring", "adapter_sha256")}
                       for r in ordered],
        "reference_S": REFERENCE_S, "exceeds_reference": best["S"] > REFERENCE_S,
        "platform": ordered[0]["metadata"]["platform"], "gpu": ordered[0]["metadata"]["gpu"],
        "bundle_commit": ordered[0]["metadata"]["bundle_commit"], "libraries": ordered[0]["metadata"]["libraries"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("evaluate", help="evaluate one candidate checkpoint on the selection subset (one GPU)")
    run.add_argument("--checkpoint", required=True, type=Path)
    run.add_argument("--state-sha256", required=True, help="the checkpoint's state.json sha256 logged when it was saved")
    run.add_argument("--out", required=True, type=Path)
    pick = commands.add_parser("choose", help="choose among the four evaluated candidates")
    pick.add_argument("--out", required=True, type=Path, help="the directory holding checkpoint-*/selection.json")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "choose":
        results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.out.glob("checkpoint-*/selection.json"))]
        choice = choose(results)
        (args.out / "choice.json").write_text(json.dumps(choice, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: choice[k] for k in ("chosen", "S", "reference_S", "exceeds_reference")}, indent=2))
        print("\n".join(f"{c['checkpoint']}: S {c['S']}" for c in choice["candidates"]))
        return 0

    candidate = verify_adapter(args.checkpoint, args.state_sha256)
    commit = bundle_commit()

    if commit is None:
        print("STOP: the code's commit is unknown (no BUNDLE.json and no git checkout)", file=sys.stderr)
        return 2

    import torch

    from packages.hetren_baselines.local_model import (
        MAX_NEW_TOKENS, QWEN_MODEL, QWEN_REVISION, TransformersModel, library_versions, platform_name,
    )

    if torch.cuda.device_count() != 1:
        print(f"STOP: {torch.cuda.device_count()} GPUs visible; exactly one is required (set CUDA_VISIBLE_DEVICES)",
              file=sys.stderr)
        return 2

    if "T4" not in torch.cuda.get_device_name(0):  # Amendment 1: evaluation on one T4
        print(f"STOP: the GPU is {torch.cuda.get_device_name(0)}, not a T4", file=sys.stderr)
        return 2

    model = TransformersModel(QWEN_MODEL, QWEN_REVISION, "float16", adapter=str(args.checkpoint / "adapter"))
    metadata = {
        "model": QWEN_MODEL, "revision": QWEN_REVISION, "dtype": "float16", "max_new_tokens": MAX_NEW_TOKENS,
        "decoding": "greedy", "adapter_merge": "peft merge_and_unload into the fp16 base",
        "libraries": library_versions(), "gpu": torch.cuda.get_device_name(0), "visible_gpus": 1,
        "platform": platform_name(), "bundle_commit": commit,
    }
    # Which physical GPU is printed, not recorded: a resumed run may continue on the other one.
    print(f"{candidate['checkpoint']} on CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}", flush=True)
    return evaluate(candidate, args.out, model, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
