"""The full-episode demo (Milestone 4, step 8): one validation case, end to end, with the real model.

Evaluator side, run from the repository only (not shipped in the CLI or the image): the CLI diagnoses evidence
and proposes; only the evaluator holds the environment in which probes run and recoveries are verified.

    python -m packages.support_evaluator.sandbox_demo --case case-001478 --gguf-dir <dir> --tokenizer <dir> \\
        --llama-cpp <checkout> [--threads 6] [--port 8091] [--out <folder>]

For one tier 1 **validation** case (dataset v2, splits v1), it:
- rebuilds the run from the dataset (the same first input the dataset records) and prints what the model sees;
- runs ``episodes.run_episode`` with Q4_K_M on a local ``llama-server``, exactly as the GGUF validation ran it:
  prompt version 2, the merged model's chat template as token IDs, Amendment 2's greedy decoding and server
  settings. Each probe the model asks for runs in a sandboxed fork, and its result is printed;
- verifies the final action by execution: a recovery is applied in another fork (with the task re-run where the
  verb calls for it), and the target ticket's queue and account are shown before and after; a decision is checked
  against the run's end state. Then ``episodes.score`` gives the protocol's verdict;
- compares the episode with the logged Q4_K_M validation run's row for the case, when that log is present
  (``artifacts/milestone-4/validation-1``): on the validation platform (the pilot's Mac, ``-t 6``), the same
  actions are expected.

**Test cases are refused**, and so is any case outside the validation split: the protocol's test splits are used
once, for the logged test runs. The demo checks every input against its manifest first: the dataset files, the
GGUF and tokenizer, and the llama.cpp commit.

Outputs in ``--out`` (default ``artifacts/milestone-4/demo/<case>``): ``demo.json`` (the transcript's calls, the
episode, the verification and the score) and ``server.log``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable

from packages.support_evaluator.case_sources import Case, load_source
from packages.support_evaluator.selection_subset import REPO_ROOT, SOURCES


DATASET_DIR = REPO_ROOT / SOURCES[1][0]
SPLITS_DIR = REPO_ROOT / "docs/milestone-2/splits-v1"
VALIDATION_ROWS = REPO_ROOT / "artifacts/milestone-4/validation-1/Q4_K_M/tier1/rows-tier1-validation.jsonl"
REFUSED_SPLITS = ("test_in_distribution", "test_held_out")
VARIANT = "Q4_K_M"
DEFAULT_THREADS = 6  # the validation platform's setting (EXPORT_LOG.md, "Pilot choices")
RULE = "-" * 100


class DemoRefused(ValueError):
    pass


def _ids(splits_dir: Path, name: str) -> set[str]:
    return set((Path(splits_dir) / f"{name}.txt").read_text(encoding="utf-8").split())


def check_case(case_id: str, splits_dir: Path = SPLITS_DIR) -> None:
    """Refuse every case that is not in the tier 1 validation split; name the test split when it is in one."""
    for name in REFUSED_SPLITS:
        if case_id in _ids(splits_dir, name):
            raise DemoRefused(f"{case_id} is a {name} case: the demo never runs test cases (the protocol's test "
                              f"splits are used once, for the logged test runs)")

    if case_id not in _ids(splits_dir, "validation"):
        raise DemoRefused(f"{case_id} is not a tier 1 validation case (splits v1); the demo runs validation cases only")


def load_case(case_id: str, dataset_dir: Path = DATASET_DIR, splits_dir: Path = SPLITS_DIR) -> tuple[Case, dict]:
    """The case (prepared on demand) and its evaluator record (for the label rule)."""
    check_case(case_id, splits_dir)
    source = load_source(Path(dataset_dir), Path(splits_dir) / "validation.txt")
    case = next((c for c in source.cases if c.case_id == case_id), None)

    if case is None:
        raise DemoRefused(f"{case_id} is not a primary case of {Path(dataset_dir).name}'s validation split")

    with (Path(dataset_dir) / "evaluator" / "cases.jsonl").open(encoding="utf-8") as handle:
        record = next(r for r in map(json.loads, handle) if r["case_id"] == case_id and r["role"] == "primary")

    return case, record


def _short(value: Any, limit: int = 160) -> str:
    text = json.dumps(value, sort_keys=True, separators=(", ", ": "))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe_run(compact: dict) -> list[str]:
    lines = [f"task: {compact['task']}", f"run: {compact['run']['status']}"
             + (f" ({compact['run']['error_type']})" if compact["run"].get("error_type") else "")]

    for number, step in enumerate(compact["steps"], start=1):
        result = step.get("observation", step.get("error"))
        lines.append(f"  {number}. {step['tool']}({_short(step['args'], 60)}) -> {step['outcome']}: {_short(result)}")

    if compact.get("discrepancies"):
        lines.append(f"  discrepancies: {_short(compact['discrepancies'])}")

    return lines


def describe_probe(probe: dict) -> str:
    result = probe.get("observation", probe.get("error"))
    return (f"probe {probe['tool']}({_short(probe.get('args', {}), 60)}) in a sandboxed fork -> {probe.get('outcome')}: "
            f"{_short(result, 240)}")


def label_rule(record: dict) -> str:
    """The labeller's rule: on the record (dataset v3), or in its run label (dataset v2)."""
    run_label = record.get("run_label") or {}
    return record.get("rule") or (json.loads(run_label) if isinstance(run_label, str) else run_label)["rule"]


def verify(prepared, final: dict | None) -> dict[str, Any]:
    """Execute the final action on forks of the run's end state, and report the target ticket before and after."""
    from packages.support_evaluator.labeler import outcome_checks
    from packages.support_evaluator.sequences import apply_recovery

    truth = prepared.case.truth
    ticket_id = truth.target_ticket_id

    def state(environment) -> dict[str, Any]:
        ticket = environment.get_ticket(ticket_id)
        return {"queue": ticket.queue_id, "account": environment.directory_entry(ticket.customer_ref),
                "checks": outcome_checks(environment, truth)}

    result = {"expected": {"queue": truth.expected_queue_id, "account": truth.expected_account_id},
              "before": state(prepared.environment)}

    if final is not None and final["action"] == "recover":
        sandbox = prepared.environment.fork()
        applied = apply_recovery(sandbox, ticket_id, prepared.planned.behaviour, final)
        result["applied"] = {"records": list(applied.records), "changed": applied.changed,
                             "task_rerun": applied.rerun is not None}
        result["after"] = state(sandbox)

    return result


def run_demo(case_id: str, generate: Callable[[str, str], Any], *, dataset_dir: Path = DATASET_DIR,
             splits_dir: Path = SPLITS_DIR, validation_rows: Path = VALIDATION_ROWS, log=print) -> dict[str, Any]:
    """Run one validation case's episode with ``generate(system, user)`` (a ``Generation``) and verify it."""
    from packages.hetren_baselines.prompt import PROMPT_VERSION, action_text, system_prompt, user_message
    from packages.hetren_evidence import render_evidence
    from packages.support_evaluator.episodes import run_episode

    case, record = load_case(case_id, dataset_dir, splits_dir)
    prepared = case.prepare()
    planned = prepared.planned
    log(RULE)
    log(f"{case_id}: a tier 1 validation case (dataset v2). The family is shown for the viewer; the model never "
        f"sees it: {planned.case_kind}/{planned.case_variant}, agent behaviour '{planned.behaviour}'")
    log(RULE)
    system = system_prompt(1)
    calls: list[dict[str, Any]] = []
    shown = {"probes": 0}

    def policy(compact: dict) -> str:
        if not calls:
            log("What the model sees (the recorded run's compact evidence):")
            for line in describe_run(compact):
                log(line)

        for probe in compact.get("probes", [])[shown["probes"]:]:
            log(describe_probe(probe))
        shown["probes"] = len(compact.get("probes", []))

        started = time.perf_counter()
        generation = generate(system, user_message(render_evidence(compact)))
        seconds = round(time.perf_counter() - started, 1)
        text = action_text(generation.text)
        calls.append({"call": len(calls), "seconds": seconds, "reply": text,
                      "prompt_tokens": getattr(generation, "prompt_tokens", None),
                      "new_tokens": getattr(generation, "new_tokens", None)})
        log(f"model, call {len(calls)} ({seconds} s): {text}")
        return text

    episode = run_episode(policy, prepared)
    row = case.score(prepared, episode)
    checked = verify(prepared, episode["final"])
    log(RULE)
    log(f"label (by execution, rule '{label_rule(record)}'): {_short(prepared.label)}")
    log(f"target ticket {prepared.case.truth.target_ticket_id}: expected queue {checked['expected']['queue']}, "
        f"account {checked['expected']['account']}")
    log(f"  at the end of the recorded run: queue {checked['before']['queue']}, account "
        f"{checked['before']['account']}, checks {checked['before']['checks']}")

    if "after" in checked:
        log(f"  the proposed recovery, applied in a sandboxed fork"
            f"{' and the task re-run' if checked['applied']['task_rerun'] else ''}: queue "
            f"{checked['after']['queue']}, account {checked['after']['account']}, checks {checked['after']['checks']}")
    elif episode["final"] is not None:
        log("  a decision changes nothing: it is checked against the run's end state above")

    if episode["failure"]:
        log(f"  the episode ended without a final action: {episode['failure']}")

    log(f"verdict (episodes.score): {'CORRECT' if row['correct'] else 'WRONG'}"
        f"{', exactly the label' if row['exact'] else ''}"
        f"{'; the recovery call failed: ' + _short(row['recovery_failures']) if row['recovery_failures'] else ''}")
    logged = None

    if Path(validation_rows).is_file():
        with Path(validation_rows).open(encoding="utf-8") as handle:
            logged = next((r for r in map(json.loads, handle) if r["case_id"] == case_id), None)

    keys = ("probes", "recoveries", "final", "correct")
    matches = None if logged is None else all(logged[k] == row[k] for k in keys)
    log("the logged Q4_K_M validation run: " + ("not present" if logged is None else
        "the same probes, recoveries, final action and verdict" if matches else
        f"DIFFERENT: logged {_short({k: logged[k] for k in keys}, 400)}"))
    log(RULE)
    return {"case_id": case_id, "prompt_version": PROMPT_VERSION, "planned": record["planned"], "rule": label_rule(record),
            "calls": calls, "episode": episode, "verification": checked, "row": row,
            "matches_validation_run": matches}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", required=True, help="a tier 1 validation case ID (splits v1)")
    parser.add_argument("--gguf-dir", required=True, type=Path, help="the folder with the Q4_K_M GGUF")
    parser.add_argument("--tokenizer", required=True, type=Path, help="the merged model's tokenizer/ folder")
    parser.add_argument("--llama-cpp", required=True, type=Path, help="the llama.cpp checkout, built in build/")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS)
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--out", type=Path, help="default artifacts/milestone-4/demo/<case>")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    from packages.hetren_serving.export import LLAMA_CPP_COMMIT, verify_llama_cpp
    from packages.support_evaluator.gguf_check import DECLARED
    from packages.support_evaluator.gguf_pilot import MANIFEST, RunningServer, cpu_model, server_command
    from packages.support_evaluator.gguf_validation import PILOT_CPU, load_tokenizer, verify_dataset, verify_variant

    out = args.out or REPO_ROOT / "artifacts/milestone-4/demo" / args.case

    try:
        check_case(args.case)
        verify_dataset(1)
        manifest = json.loads((REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
        gguf = verify_variant(manifest, VARIANT, args.gguf_dir, args.tokenizer)
        verify_llama_cpp(args.llama_cpp, LLAMA_CPP_COMMIT)
    except (ValueError, OSError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

    from packages.hetren_serving.llama_server import DecodingSettings, LlamaServer, LlamaServerModel

    cpu = cpu_model()
    print(f"inputs checked: dataset v2, {VARIANT} and the tokenizer against the export manifest, llama.cpp "
          f"{LLAMA_CPP_COMMIT[:9]}. CPU {cpu}, -t {args.threads}"
          + ("" if cpu == PILOT_CPU and args.threads == DEFAULT_THREADS else
             " (not the validation platform: the actions may differ from the logged run)"), flush=True)
    out.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{args.port}"
    binary = Path(args.llama_cpp) / "build" / "bin" / "llama-server"

    with RunningServer(server_command(binary, gguf, args.threads, args.port), out / "server.log", url, gguf) as server:
        print(f"llama-server ready in {server.load_seconds} s", flush=True)
        model = LlamaServerModel(load_tokenizer(args.tokenizer), LlamaServer(url),
                                 DecodingSettings(cache_prompt=DECLARED["cache_prompt"]))
        result = run_demo(args.case, model, log=lambda message: print(message, flush=True))

    result |= {"variant": VARIANT, "gguf_sha256": manifest["gguf"][Path(gguf).name]["sha256"], "cpu": cpu,
               "threads": args.threads, "llama_cpp_commit": LLAMA_CPP_COMMIT}
    (out / "demo.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"written: {out / 'demo.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
