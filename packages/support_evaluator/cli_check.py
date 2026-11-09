"""Descriptive check of the ``hetren`` CLI on the real model (Milestone 4, step 4; operator-run, not acceptance).

For the 20 pilot cases (``gguf_pilot.pilot_cases``: the fp16 smoke-test cases, 10 per tier), the CLI is run
as a user would run it: ``python -m packages.hetren_cli diagnose --compact <first-step input> --format json``,
one process (and one fresh ``llama-server``) per case, with the validated variant's GGUF, the export's
tokenizer and ``-t 6``. Its action is compared with the GGUF validation run's first call for the same case
(``calls.jsonl``, call 0).

- Tier 1 is like for like: the same input and the same tier 1 prompt; only the prompt cache differs (the
  validation run's server had served the previous case, the CLI's starts empty), which the pilot showed can
  change a Q4_K_M reply.
- Tier 2 is reported separately and is not like for like: the validation run used the tier 2 prompt (two
  recoveries allowed), and the CLI always uses the tier 1 prompt.

Nothing here gates anything. Run on the Mac from the repository::

    ~/.hetren-pilot/bin/python -m packages.support_evaluator.cli_check run --variant Q4_K_M \\
        --gguf-dir artifacts/milestone-4/export-2/gguf-export \\
        --tokenizer artifacts/milestone-4/export-2/gguf-export/tokenizer \\
        --llama-server ~/hetren-tools/llama.cpp/build/bin/llama-server \\
        --runs artifacts/milestone-4/validation-1 --out artifacts/milestone-4/cli-check-1

With ``--docker-image <image>`` instead of ``--llama-server``, each diagnosis runs in the published image as a
user runs it offline (``docker run --network none --read-only``, the input, GGUF and tokenizer mounted
read-only, the image's own ``llama-server``): the Docker step's real-model check of the offline path, one
container at a time.

Outputs in ``<out>/<variant>/``: ``inputs/`` (each case's first-step input), ``reports/`` (each CLI report,
JSON), ``cases.jsonl`` (one line per case: tier, case, exit status, the CLI's action, the validation run's
first action, same or not) and ``summary.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from packages.support_evaluator.gguf_check import action_sequences, read_jsonl, sha256_file


REPO_ROOT = Path(__file__).resolve().parents[2]
THREADS = 6  # the validation run's
GGUF_NAMES = {"Q4_K_M": "hetren-qwen3-4b-ckpt0792-q4_k_m.gguf", "Q8_0": "hetren-qwen3-4b-ckpt0792-q8_0.gguf"}


def cli_command(compact_path: Path, gguf: Path, tokenizer: Path, llama_server: Path,
                python: str = sys.executable) -> list[str]:
    return [python, "-m", "packages.hetren_cli", "diagnose", "--compact", str(compact_path), "--model", str(gguf),
            "--tokenizer", str(tokenizer), "--llama-server", str(llama_server), "--threads", str(THREADS),
            "--format", "json"]


def docker_command(image: str, compact_path: Path, gguf: Path, tokenizer: Path) -> list[str]:
    """The same diagnosis in the published image, offline: no network, a read-only root file system, the input,
    GGUF and tokenizer mounted read-only, and the image's own llama-server."""
    compact_path, gguf, tokenizer = Path(compact_path).resolve(), Path(gguf).resolve(), Path(tokenizer).resolve()
    return ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp",
            "-v", f"{compact_path.parent}:/inputs:ro", "-v", f"{gguf.parent}:/models:ro", "-v", f"{tokenizer}:/tokenizer:ro",
            image, "diagnose", "--compact", f"/inputs/{compact_path.name}", "--model", f"/models/{gguf.name}",
            "--tokenizer", "/tokenizer", "--threads", str(THREADS), "--format", "json"]


def first_actions(calls_path: Path) -> dict[str, dict]:
    """Each case's first action in a validation run (call 0)."""
    return {case: actions[0] for case, actions in action_sequences(read_jsonl(calls_path)).items() if actions}


def cli_action(report: dict | None) -> dict | None:
    if report is None:
        return None

    result = report["result"]
    return result["action"] if "action" in result else {"unparsable": result.get("reply", "").strip()}


def summarize(rows: list[dict]) -> dict[str, object]:
    tiers = {}

    for tier, comparison in ((1, "like for like (same input and prompt; prompt cache differs)"),
                             (2, "not like for like (the validation run used the tier 2 prompt)")):
        mine = [r for r in rows if r["tier"] == tier]
        same = [r["case_id"] for r in mine if r["same"]]
        tiers[f"tier{tier}"] = {"cases": len(mine), "same_first_action": len(same),
                                "differing": sorted(r["case_id"] for r in mine if not r["same"]),
                                "cli_failures": sorted(r["case_id"] for r in mine if r["exit"] not in (0, 4)),
                                "comparison": comparison}

    return {"cases": len(rows), "tiers": tiers}


def run(args: argparse.Namespace, log=lambda message: print(message, flush=True)) -> int:
    from packages.support_evaluator.gguf_pilot import pilot_cases
    from packages.support_evaluator.gguf_validation import SOURCES

    out = Path(args.out) / args.variant
    (out / "inputs").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(exist_ok=True)
    gguf = Path(args.gguf_dir) / GGUF_NAMES[args.variant]
    cases = pilot_cases()
    visible = {}

    for tier in (1, 2):
        path = REPO_ROOT / SOURCES[tier][0] / "hetren_visible.jsonl"
        wanted = {case.case_id for t, case, _ in cases if t == tier}

        for line in path.open(encoding="utf-8"):
            record = json.loads(line)

            if record["case_id"] in wanted:
                visible[(tier, record["case_id"])] = record["steps"][0]["input"]

    validation = {tier: first_actions(Path(args.runs) / args.variant / f"tier{tier}" / "calls.jsonl") for tier in (1, 2)}
    rows = []
    where = f"in the image {args.docker_image} (--network none)" if args.docker_image else "on this machine"
    log(f"{args.variant}: {len(cases)} pilot cases, one CLI process each, {where}")

    for tier, case, _ in cases:
        compact_path = out / "inputs" / f"tier{tier}-{case.case_id}.json"
        compact_path.write_text(json.dumps(visible[(tier, case.case_id)], sort_keys=True) + "\n", encoding="utf-8")
        started = time.perf_counter()
        command = (docker_command(args.docker_image, compact_path, gguf, Path(args.tokenizer)) if args.docker_image
                   else cli_command(compact_path, gguf, Path(args.tokenizer), Path(args.llama_server)))
        result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
        seconds = round(time.perf_counter() - started, 1)
        report = json.loads(result.stdout) if result.stdout.strip().startswith("{") else None

        if report is not None:
            (out / "reports" / f"tier{tier}-{case.case_id}.json").write_text(result.stdout, encoding="utf-8")

        mine, theirs = cli_action(report), validation[tier].get(case.case_id)
        row = {"tier": tier, "case_id": case.case_id, "exit": result.returncode, "seconds": seconds,
               "cli_action": mine, "validation_first_action": theirs, "same": mine is not None and mine == theirs,
               "stderr": result.stderr.strip()[-500:] if result.returncode not in (0, 4) else ""}
        rows.append(row)
        log(f"tier {tier} {case.case_id}: exit {result.returncode}, {'same' if row['same'] else 'different'} "
            f"first action, {seconds} s" + (f"; {row['stderr']}" if row["stderr"] else ""))

    with open(out / "cases.jsonl", "w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(r, sort_keys=True) + "\n" for r in rows)

    image = None

    if args.docker_image:
        image = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", args.docker_image],
                               capture_output=True, text=True).stdout.strip() or None

    summary = {"variant": args.variant, "gguf_sha256": sha256_file(gguf), "threads": THREADS, **summarize(rows),
               "where": {"docker_image": args.docker_image, "image_id": image} if args.docker_image else "local",
               "validation_calls_sha256": {f"tier{t}": sha256_file(Path(args.runs) / args.variant / f"tier{t}" / "calls.jsonl")
                                           for t in (1, 2)}}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log(json.dumps(summary["tiers"], indent=2))
    return 0 if not any(t["cli_failures"] for t in summary["tiers"].values()) else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("run")
    one.add_argument("--variant", required=True, choices=tuple(GGUF_NAMES))
    one.add_argument("--gguf-dir", required=True, type=Path)
    one.add_argument("--tokenizer", required=True, type=Path)
    where = one.add_mutually_exclusive_group(required=True)
    where.add_argument("--llama-server", type=Path, help="run the CLI here, with this llama-server")
    where.add_argument("--docker-image", help="run the CLI in this image, offline (docker run --network none)")
    one.add_argument("--runs", required=True, type=Path, help="the validation runs' root (<root>/<variant>/tier<N>/)")
    one.add_argument("--out", required=True, type=Path)
    return run(parser.parse_args(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
