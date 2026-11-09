"""Linux agreement check (Milestone 4, step 5; operator-run, descriptive, never part of acceptance).

The validation ran on macOS (llama.cpp with Accelerate); the shipped image runs Linux x86_64 with a fixed
AVX2 build (``docker/hetren-cli/Dockerfile``). This check runs the 20 pilot cases (``gguf_pilot.pilot_cases``,
10 per tier, tier 1 first) as full episodes in the image's ``check`` stage, which has the same ``llama-server``
binary as the published image, for each variant in turn, with the validation run's settings (Amendment 2's
server settings and decoding, prompt caching on, ``-t 6``), and reports each variant's episode agreement with
the Mac validation run's episodes for the same cases (``calls.jsonl``; a case's episode is its sequence of
actions). It is reported and never changes an acceptance decision (docs/milestone-4/EXPORT_LOG.md,
"Limitation: the validation platform is not the shipped platform").

One ``llama-server`` at a time (variants in turn, one server session each, cases in the pilot's order): the
check's memory need is one server plus this process. It stops before starting if the VM has less than
``MIN_MEMORY_BYTES``, and records the VM's memory and each server's peak resident memory. The validation run's
server had served every earlier validation case, so the two runs' prompt caches differ; agreement is reported
as measured, not attributed.

Run in the check image, with the repository (and its gitignored datasets and validation runs) mounted
read-only and an empty output directory::

    docker run --rm -v "$PWD":/repo:ro -v "$PWD/artifacts/milestone-4/linux-check-1":/out hetren-cli:check \\
        python -m packages.support_evaluator.linux_agreement run \\
        --gguf-dir /repo/artifacts/milestone-4/export-2/gguf-export \\
        --tokenizer /repo/artifacts/milestone-4/export-2/gguf-export/tokenizer \\
        --runs /repo/artifacts/milestone-4/validation-1 --out /out

Outputs in ``<out>``: ``episodes-<variant>.jsonl`` (one line per case: tier, case, calls, episode),
``server-<variant>.log`` and ``linux-agreement.json`` (environment, memory, ``system_info``, peak memory and
the agreement per variant and tier, with every output file's sha256).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform as platform_module
import sys
import time

from packages.support_evaluator.gguf_check import action_sequences, read_jsonl, sha256_file


REPO_ROOT = Path(__file__).resolve().parents[2]
BINARY = Path("/usr/local/bin/llama-server")  # the image's
BUILD_INFO = Path("/usr/share/hetren/build-info.json")  # written by the image's llama-build stage
THREADS = 6  # the validation run's
MIN_MEMORY_BYTES = 7 * 1024 ** 3  # one server: Q8_0 peaked at 5.10 GB on the Mac (mostly the mapped GGUF)
VARIANTS = ("Q4_K_M", "Q8_0")


def meminfo(text: str | None = None) -> dict[str, int]:
    """``MemTotal`` and ``MemAvailable`` from ``/proc/meminfo``, in bytes."""
    text = Path("/proc/meminfo").read_text(encoding="utf-8") if text is None else text
    values = {}

    for line in text.splitlines():
        key, _, rest = line.partition(":")

        if key in ("MemTotal", "MemAvailable"):
            values[key] = int(rest.split()[0]) * 1024

    return values


def agreement(linux_calls: list[dict], mac_calls: list[dict], case_ids: list[str]) -> dict[str, object]:
    """Same episode (action sequence) and same first action, case by case."""
    linux, mac = action_sequences(linux_calls), action_sequences(mac_calls)
    same = [c for c in case_ids if linux.get(c, []) == mac.get(c, []) and c in linux]
    first = [c for c in case_ids if linux.get(c) and mac.get(c) and linux[c][0] == mac[c][0]]
    return {"cases": len(case_ids), "same_episode": len(same), "same_first_action": len(first),
            "differing_episodes": sorted(set(case_ids) - set(same))}


def run_cases(model, cases, out_path: Path, log) -> list[dict]:
    """Each case once, as a full episode; one JSON line per case. Returns every call (with tier and case)."""
    from packages.hetren_baselines.prompt import action_text, system_prompt, user_message
    from packages.hetren_evidence import render_evidence
    from packages.support_evaluator.episodes import run_episode

    every_call = []

    with open(out_path, "w", encoding="utf-8") as out:
        for tier, case, recoveries in cases:
            system = system_prompt(recoveries)
            calls, halt = [], []

            def policy(compact):
                started = time.perf_counter()

                try:
                    generation = model(system, user_message(render_evidence(compact)))
                except Exception as exc:  # run_episode would record an invalid action: stop instead
                    halt.append(exc)
                    raise

                calls.append({"tier": tier, "case_id": case.case_id, "call": len(calls), **generation.payload(),
                              "seconds": round(time.perf_counter() - started, 3)})
                return action_text(generation.text)

            episode = run_episode(policy, case.prepare())

            if halt:
                raise RuntimeError(f"generation failed at tier {tier} {case.case_id}") from halt[0]

            out.write(json.dumps({"tier": tier, "case_id": case.case_id, "calls": calls, "episode": episode},
                                 sort_keys=True) + "\n")
            out.flush()
            every_call.extend(calls)
            log(f"tier {tier} {case.case_id}: {len(calls)} calls, {sum(c['seconds'] for c in calls):.1f} s")

    return every_call


def run(args: argparse.Namespace, log=lambda message: print(message, flush=True)) -> int:
    from packages.hetren_serving.export import LLAMA_CPP_COMMIT, library_versions
    from packages.support_evaluator.gguf_pilot import (MANIFEST, RunningServer, code_commit, cpu_model,
                                                       peak_rss_bytes, pilot_cases, server_command, server_settings,
                                                       server_version, system_info, verify_inputs)

    out = Path(args.out)

    try:
        if sys.platform != "linux" or not BUILD_INFO.exists():
            raise ValueError("run this in the hetren-cli check image (Linux, with /usr/share/hetren/build-info.json)")

        if not args.preflight and out.exists() and any(out.iterdir()):
            raise ValueError(f"{out} is not empty; a stopped check is logged and repeated into a new directory")

        memory = meminfo()

        if memory["MemTotal"] < MIN_MEMORY_BYTES:
            raise ValueError(f"the VM has {memory['MemTotal'] / 1024 ** 3:.2f} GiB; the check needs at least "
                             f"{MIN_MEMORY_BYTES / 1024 ** 3:.0f} GiB for one server at a time")

        if (os.cpu_count() or 0) < THREADS:
            raise ValueError(f"{os.cpu_count()} logical CPUs, fewer than the validation run's {THREADS} threads")

        commit = code_commit()
        manifest = json.loads((REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
        ggufs = verify_inputs(manifest, args.gguf_dir, args.tokenizer)
        version = server_version(BINARY)
        validation = {(v, t): read_jsonl(Path(args.runs) / v / f"tier{t}" / "calls.jsonl")
                      for v in VARIANTS for t in (1, 2)}
    except (ValueError, OSError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

    if args.preflight:
        log(json.dumps({"preflight": "ok", "commit": commit, "memory": memory, "logical_cpus": os.cpu_count(),
                        "cpu": cpu_model(), "server_version": version,
                        "image_build": json.loads(BUILD_INFO.read_text(encoding="utf-8")),
                        "validation_calls": {f"{v}/tier{t}": len(c) for (v, t), c in validation.items()}}, indent=2))
        return 0

    from transformers import AutoTokenizer

    from packages.hetren_serving.llama_server import DecodingSettings, LlamaServer, LlamaServerModel

    out.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer))
    cases = pilot_cases()
    url = f"http://127.0.0.1:{args.port}"
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    variants = {}
    log(f"Linux agreement check: {len(cases)} cases × {len(VARIANTS)} variants, one server at a time, "
        f"{THREADS} threads, caching on; VM memory {memory['MemTotal'] / 1024 ** 3:.2f} GiB "
        f"({memory['MemAvailable'] / 1024 ** 3:.2f} GiB available)")

    for variant in VARIANTS:
        log(f"{variant}: starting llama-server")
        began = time.perf_counter()

        try:
            with RunningServer(server_command(BINARY, ggufs[variant], THREADS, args.port), out / f"server-{variant}.log",
                               url, ggufs[variant]) as server:
                model = LlamaServerModel(tokenizer, LlamaServer(url), DecodingSettings(cache_prompt=True))
                calls = run_cases(model, cases, out / f"episodes-{variant}.jsonl", log)
        except Exception as exc:
            print(f"STOP in {variant}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 4

        server_log = (out / f"server-{variant}.log").read_text(encoding="utf-8", errors="replace")
        tiers = {}

        for tier in (1, 2):
            ids = [case.case_id for t, case, _ in cases if t == tier]
            tiers[f"tier{tier}"] = agreement([c for c in calls if c["tier"] == tier], validation[(variant, tier)], ids)

        variants[variant] = {
            "tiers": tiers,
            "same_episode": sum(t["same_episode"] for t in tiers.values()), "cases": len(cases),
            "calls": len(calls), "seconds_per_call": round(sum(c["seconds"] for c in calls) / len(calls), 2),
            "peak_rss_bytes": peak_rss_bytes(server_log), "system_info": system_info(server_log),
            "server_settings": server_settings(server_log), "load_seconds": server.load_seconds,
            "minutes": round((time.perf_counter() - began) / 60, 1),
        }
        log(f"{variant}: {variants[variant]['same_episode']} of {len(cases)} episodes as on the Mac "
            f"(tier 1 {tiers['tier1']['same_episode']} of {tiers['tier1']['cases']}, tier 2 "
            f"{tiers['tier2']['same_episode']} of {tiers['tier2']['cases']}); peak memory "
            f"{(variants[variant]['peak_rss_bytes'] or 0) / 1e9:.2f} GB")

    report = {
        "check": "Linux agreement (descriptive; docs/milestone-4/EXPORT_LOG.md, platform limitation)",
        "image_build": json.loads(BUILD_INFO.read_text(encoding="utf-8")),
        "os": platform_module.platform(), "cpu": cpu_model(), "logical_cpus": os.cpu_count(), "threads": THREADS,
        "memory_at_start": memory, "python": platform_module.python_version(),
        "libraries": library_versions(("transformers", "tokenizers", "huggingface_hub", "jinja2")),
        "bundle_commit": commit, "llama_cpp_commit": LLAMA_CPP_COMMIT, "server_version": version,
        "server_command": server_command(BINARY, "<gguf>", THREADS, args.port),
        "decoding": DecodingSettings(cache_prompt=True).payload([]) | {"prompt": "<token IDs>"},
        "manifest_sha256": sha256_file(REPO_ROOT / MANIFEST),
        "gguf_sha256": {v: manifest["gguf"][Path(p).name]["sha256"] for v, p in ggufs.items()},
        "validation_calls_sha256": {f"{v}/tier{t}": sha256_file(Path(args.runs) / v / f"tier{t}" / "calls.jsonl")
                                    for v in VARIANTS for t in (1, 2)},
        "cases": [f"tier {t} {case.case_id}" for t, case, _ in cases],
        "started_utc": started_utc, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "variants": variants,
        "files": {p.name: sha256_file(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    (out / "linux-agreement.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("run", help="both variants, one server at a time")
    one.add_argument("--gguf-dir", required=True, type=Path)
    one.add_argument("--tokenizer", required=True, type=Path)
    one.add_argument("--runs", required=True, type=Path, help="the validation runs' root (<root>/<variant>/tier<N>/)")
    one.add_argument("--out", required=True, type=Path)
    one.add_argument("--port", type=int, default=8080)
    one.add_argument("--preflight", action="store_true",
                     help="run every check (image, memory, CPUs, commit, inputs, server build), start nothing")
    return run(parser.parse_args(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
