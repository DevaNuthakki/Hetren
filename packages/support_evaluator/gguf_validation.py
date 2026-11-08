"""The GGUF validation run (EVAL_PROTOCOL.md, Amendment 2, "Validation check"), on the platform the pilot chose.

``run --variant V`` runs one variant on the full validation split, tier 1 then
tier 2 (550 and 250 primary cases), with the pilot's choice
(``docs/milestone-4/EXPORT_LOG.md``, "Pilot choices", 2026-11-08): the
operator's Mac (the pilot's CPU), ``-t 6``, prompt caching on, ``-c 4096 -np 1
-ngl 0 -b 2048 -ub 512``, Amendment 2's greedy decoding. Validation splits
only: no option selects any other split. No separate smoke test (the pilot ran
the 20 smoke cases on this platform with these settings).

- **Checks first:** macOS on mains power with the pilot's CPU; the code's
  commit, with no tracked changes except the export log (so a stop can be
  logged before the run is resumed); the tier's dataset files against their
  committed manifests; the variant's GGUF and the tokenizer files against the
  committed export manifest; the llama.cpp checkout and ``llama-server
  --version`` against ``620d2225``. A ``caffeinate -dims`` assertion is held
  for the whole run.
- **CPU features:** the build's ``system_info`` line, from ``llama-server -lv 4``
  with no model (nothing is loaded), and the server binary's sha256, are
  recorded in the metadata.
- **Episodes:** ``local_model_baseline.run_baseline``, as in every fp16 run
  (the same prompt, episodes, scoring, rows, call log and resume by case),
  with ``show_results=False``: the console shows each case's ID and call
  count, never whether it was correct; results are read only after the run
  is logged. A fresh ``llama-server`` serves each tier (under
  ``/usr/bin/time`` for its peak memory), so every tier's first case starts
  from an empty cache.
- **Resume:** the same command completes the same declared run (a tier with
  a completion record is skipped; scored cases are kept; other settings
  stop). A later commit may be checked out (for example the logged stop)
  only if nothing the run uses changed since the tier's first session
  (``RUN_INPUTS``); the metadata keeps the first session's commit and each
  session records its own. ``sessions.jsonl`` records every start (the case it starts at, with
  an empty cache) and stop, and the completion record lists the restarts.
- **Unexpected stops:** every call keeps its generated token IDs; calls that
  did not end on ``<|im_end|>`` or ``<|endoftext|>`` (such as llama.cpp's
  added ``</s>``) are counted, with their cases, in the completion record.
  The runtime is not changed.

Outputs in ``<out>/<variant>/tier<N>/``: ``metadata.json``, ``calls.jsonl``,
``rows-tier<N>-validation.jsonl``, ``summary-tier<N>-validation.json``,
``sessions.jsonl``, ``server-<k>.log`` (one per session) and, when the tier is
complete, ``validation-<variant>-tier<N>.json``: the run's metadata, sessions,
restarts, unexpected stops, call counts and every file's sha256, which
``gguf_check`` verifies.

Command::

    python -m packages.support_evaluator.gguf_validation run --variant Q4_K_M --gguf-dir <dir> --tokenizer <dir> \\
        --llama-cpp <checkout> --out <root>
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from packages.support_evaluator.case_sources import load_source
from packages.support_evaluator.checkpoint_selection import VALIDATION_SIZES
from packages.support_evaluator.gguf_check import DECLARED, SHIPPING_ORDER, run_name, unexpected_stops
from packages.support_evaluator.gguf_pilot import (
    MANIFEST, PLATFORMS, SERVER, RunningServer, check_platform, cpu_model, hold_awake, peak_rss_bytes,
    read_jsonl, server_command, server_version, sha256_file, system_info, variant_files,
)
from packages.support_evaluator.local_model_baseline import run_baseline
from packages.support_evaluator.selection_subset import REPO_ROOT, SOURCES


PILOT_CPU = "Intel(R) Core(TM) i7-8850H CPU @ 2.60GHz"  # pilot 1's Mac (EXPORT_LOG.md)
TIERS = (1, 2)
EXPORT_LOG = "docs/milestone-4/EXPORT_LOG.md"  # the only tracked file that may differ from the commit
# What the run reads from the repository: a resume on a later commit needs these unchanged.
RUN_INPUTS = ("packages", "environments", "docs/milestone-2", "docs/milestone-4/export.manifest.json",
              "requirements-gguf-pilot.txt")
DATA_FILES = ("hetren_visible.jsonl", "evaluator/cases.jsonl", "evaluator/tags.jsonl")  # as the bundle builder checks
TIME = Path("/usr/bin/time")


def load_tokenizer(path: Path):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(str(path))


def git(*args: str, root: Path = REPO_ROOT) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def checkout_commit(root: Path = REPO_ROOT) -> str:
    """HEAD, after checking that no tracked file differs from it except the export log."""
    changed = [line[3:] for line in git("status", "--porcelain", "--untracked-files=no", root=root).splitlines()]
    other = [path for path in changed if path != EXPORT_LOG]

    if other:
        raise ValueError(f"tracked files differ from the commit: {other} (only {EXPORT_LOG} may)")

    return git("rev-parse", "HEAD", root=root).strip()


def changed_inputs(recorded: str, head: str, root: Path = REPO_ROOT) -> list[str]:
    """The run's inputs that differ between the tier's first commit and this one."""
    return git("diff", "--name-only", recorded, head, "--", *RUN_INPUTS, root=root).split()


def verify_dataset(tier: int, root: Path = REPO_ROOT) -> dict[str, str]:
    """The tier's dataset files, checked against the dataset's committed manifest."""
    dataset = Path(root) / SOURCES[tier][0]
    manifest = json.loads((Path(root) / "docs/milestone-2" / f"{dataset.name}.manifest.json").read_text(encoding="utf-8"))
    found = {name: sha256_file(dataset / name) for name in DATA_FILES}

    for name, digest in found.items():
        if digest != manifest["files"][name]:
            raise ValueError(f"{dataset / name} does not match docs/milestone-2/{dataset.name}.manifest.json")

    return found


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def record_name(variant: str, tier: int) -> str:
    return f"validation-{variant}-tier{tier}.json"


def verify_variant(manifest: dict, variant: str, gguf_dir: Path, tokenizer_dir: Path) -> str:
    """The variant's GGUF path after checking it and every tokenizer file against the manifest."""
    name = variant_files(manifest)[variant]
    path = Path(gguf_dir) / name

    if sha256_file(path) != manifest["gguf"][name]["sha256"]:
        raise ValueError(f"{path} does not have the manifest's sha256")

    for file, digest in sorted(manifest["merge"]["files"].items()):
        if not file.startswith("model") and sha256_file(Path(tokenizer_dir) / file) != digest:
            raise ValueError(f"{Path(tokenizer_dir) / file} does not have the merged model's sha256")

    return str(path)


def probe_system_info(binary: Path, threads: int, run=subprocess.run) -> dict[str, object] | None:
    """The build's ``system_info`` line: ``llama-server -lv 4`` prints it before loading, then stops on no model."""
    result = run([str(binary), "-lv", "4", "-t", str(threads), "-m", "/nonexistent/hetren-probe.gguf",
                  "--host", "127.0.0.1", "--port", "1"], capture_output=True, text=True, timeout=120)
    return system_info((result.stdout or "") + (result.stderr or ""))


def pending_cases(source, rows_path: Path) -> tuple[int, str | None]:
    """(cases already scored, the first case this session will score), in the runner's order."""
    done = {r["case_id"] for r in read_jsonl(rows_path)} if rows_path.exists() else set()
    pending = [c.case_id for c in source.cases if c.case_id not in done]
    return len(done), pending[0] if pending else None


def append(path: Path, entry: dict) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def completion_record(directory: Path, variant: str, tier: int) -> dict[str, object]:
    """The tier's record, after checking it holds every validation case once."""
    rows = read_jsonl(directory / f"rows-{run_name(tier)}.jsonl")
    ids = [r["case_id"] for r in rows]

    if len(ids) != VALIDATION_SIZES[tier] or len(set(ids)) != len(ids):
        raise ValueError(f"expected {VALIDATION_SIZES[tier]} validation cases once each, found {len(ids)}")

    calls = [c for c in read_jsonl(directory / "calls.jsonl") if not c.get("discarded")]
    sessions = read_jsonl(directory / "sessions.jsonl")
    starts = [s for s in sessions if s["event"] == "start"]
    return {
        "amendment": "EVAL_PROTOCOL.md, Amendment 2, Validation check",
        "variant": variant, "tier": tier, "cases": len(ids), "split": SOURCES[tier][1],
        "split_sha256": sha256_file(REPO_ROOT / SOURCES[tier][1]),
        "metadata": json.loads((directory / "metadata.json").read_text(encoding="utf-8")),
        "sessions": sessions,
        "restarts": [{"started_utc": s["started_utc"], "first_case": s["first_case"], "done_before": s["done"]}
                     for s in starts[1:]],
        "unexpected_stops": unexpected_stops(calls, tier),
        "calls": {"total": len(calls), "seconds": round(sum(c["seconds"] for c in calls), 1),
                  "at_token_limit": sum(c["at_limit"] for c in calls), "non_finite": sum(not c["finite"] for c in calls),
                  "discarded": sum(c.get("discarded", False) for c in read_jsonl(directory / "calls.jsonl"))},
        "files": {p.name: sha256_file(p) for p in sorted(directory.iterdir())
                  if p.is_file() and p.name != record_name(variant, tier)},
    }


def run(args: argparse.Namespace, log=print) -> int:
    from packages.hetren_baselines.local_model import MAX_NEW_TOKENS, QWEN_MODEL, QWEN_REVISION
    from packages.hetren_serving.export import LLAMA_CPP_COMMIT, library_versions, verify_llama_cpp

    platform, threads = DECLARED["platform"], DECLARED["threads"]

    try:
        check_platform(platform)

        if cpu_model() != PILOT_CPU:
            raise ValueError(f"the CPU is {cpu_model()!r}, not the pilot's {PILOT_CPU!r}")

        head = checkout_commit()
        datasets = {tier: verify_dataset(tier) for tier in TIERS}
        manifest = json.loads((REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
        gguf = verify_variant(manifest, args.variant, args.gguf_dir, args.tokenizer)
        verify_llama_cpp(args.llama_cpp, LLAMA_CPP_COMMIT)
        binary = Path(args.llama_cpp) / "build" / "bin" / "llama-server"
        version = server_version(binary)

        if not TIME.exists():
            raise ValueError(f"{TIME} is missing")
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

    from packages.hetren_serving.llama_server import DecodingSettings, LlamaServer, LlamaServerModel

    settings = DecodingSettings(cache_prompt=DECLARED["cache_prompt"])
    probe = probe_system_info(binary, threads)
    log(f"system_info: {probe['line'] if probe else 'not reported'}", flush=True)
    awake = hold_awake()
    tokenizer = load_tokenizer(args.tokenizer)
    url = f"http://127.0.0.1:{args.port}"

    try:
        for tier in TIERS:
            directory = Path(args.out) / args.variant / f"tier{tier}"

            if (directory / record_name(args.variant, tier)).exists():
                log(f"{args.variant} tier {tier}: complete, skipped", flush=True)
                continue

            directory.mkdir(parents=True, exist_ok=True)
            commit = head

            if (directory / "metadata.json").exists():  # a resume: the tier keeps its first session's commit
                commit = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))["bundle_commit"]
                changed = changed_inputs(commit, head) if commit != head else []

                if changed:
                    print(f"STOP: {args.variant} tier {tier} started at {commit}; the run's inputs changed since: "
                          f"{changed}", file=sys.stderr)
                    return 2

            source = load_source(REPO_ROOT / SOURCES[tier][0], REPO_ROOT / SOURCES[tier][1])
            done, first = pending_cases(source, directory / f"rows-{run_name(tier)}.jsonl")
            session = len([s for s in read_jsonl(directory / "sessions.jsonl") if s["event"] == "start"]) + 1 \
                if (directory / "sessions.jsonl").exists() else 1
            metadata = {
                "variant": args.variant, "tier": tier, "gguf": Path(gguf).name,
                "gguf_sha256": manifest["gguf"][Path(gguf).name]["sha256"],
                "manifest_sha256": sha256_file(REPO_ROOT / MANIFEST),
                "platform": platform, "cpu": PILOT_CPU, "threads": threads, "cache_prompt": settings.cache_prompt,
                "server": {**SERVER, "threads": threads}, "decoding_payload": settings.payload([]) | {"prompt": "<token IDs>"},
                "server_command": server_command(binary, "<gguf>", threads, args.port),
                "llama_cpp_commit": LLAMA_CPP_COMMIT, "server_version": version,
                "server_binary_sha256": sha256_file(binary), "system_info": probe,
                "model": QWEN_MODEL, "revision": QWEN_REVISION, "max_new_tokens": MAX_NEW_TOKENS, "decoding": "greedy",
                "libraries": library_versions(("transformers", "tokenizers", "huggingface_hub", "jinja2")),
                "bundle_commit": commit, "dataset_sha256": datasets[tier],
            }
            server_log = directory / f"server-{session}.log"
            append(directory / "sessions.jsonl", {"event": "start", "session": session, "started_utc": utc(),
                                                  "done": done, "first_case": first, "server_log": server_log.name, "head": head,
                                                  "empty_cache_at_first_case": True})
            log(f"{args.variant} tier {tier}: session {session}, {done} of {VALIDATION_SIZES[tier]} cases done"
                + (f", starting at {first} with an empty cache" if first else ""), flush=True)
            args_tier = argparse.Namespace(dataset=REPO_ROOT / SOURCES[tier][0], split=REPO_ROOT / SOURCES[tier][1],
                                           live=None, out=directory, smoke=None, limit=None)
            code, error = None, None

            try:
                with RunningServer(server_command(binary, gguf, threads, args.port), server_log, url, gguf):
                    model = LlamaServerModel(tokenizer, LlamaServer(url), settings)
                    code = run_baseline(args_tier, model, metadata, show_results=False)
            except Exception as exc:  # the server failed to start or died: stop; scored cases are kept
                error = f"{type(exc).__name__}: {exc}"

            text = server_log.read_text(encoding="utf-8", errors="replace") if server_log.exists() else ""
            append(directory / "sessions.jsonl", {"event": "stop", "session": session, "finished_utc": utc(),
                                                  "exit": code, "error": error, "peak_rss_bytes": peak_rss_bytes(text),
                                                  "done": pending_cases(source, directory / f"rows-{run_name(tier)}.jsonl")[0]})

            if error or code != 0:
                print(f"STOP in {args.variant} tier {tier}: {error or f'exit {code}'}; log the stop, then run the same "
                      f"command again to complete the run", file=sys.stderr)
                return code if code else 4

            try:
                record = completion_record(directory, args.variant, tier)
            except ValueError as exc:
                print(f"STOP: {args.variant} tier {tier}: {exc}", file=sys.stderr)
                return 2

            (directory / record_name(args.variant, tier)).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                                                                     encoding="utf-8")
            stops = record["unexpected_stops"]
            log(f"{args.variant} tier {tier}: complete, {record['cases']} cases, {record['calls']['total']} calls, "
                f"{len(record['restarts'])} restarts, {stops['calls']} calls ended on another token "
                f"{stops['cases'] or ''}; results are read only after the run is logged", flush=True)
    finally:
        if awake is not None:
            awake.terminate()

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("run", help="one variant on the full validation split, tier 1 then tier 2")
    one.add_argument("--variant", required=True, choices=SHIPPING_ORDER)
    one.add_argument("--gguf-dir", required=True, type=Path, help="the export's directory with the GGUF files")
    one.add_argument("--tokenizer", required=True, type=Path, help="the export's tokenizer/ directory")
    one.add_argument("--llama-cpp", required=True, type=Path, help="the llama.cpp checkout, built in build/")
    one.add_argument("--out", required=True, type=Path, help="the runs' root (<out>/<variant>/tier<N>/)")
    one.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if PLATFORMS[DECLARED["platform"]]["threads"] != DECLARED["threads"]:
        print("STOP: the declared threads differ from the pilot's", file=sys.stderr)
        return 2

    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
