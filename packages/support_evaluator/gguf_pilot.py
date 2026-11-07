"""Throughput pilot of the GGUF variants (EVAL_PROTOCOL.md, Amendment 2, "Throughput pilot"), validation only.

``run`` measures one platform (``--platform mac`` or ``kaggle``):

- inputs are checked first: both GGUF files and the tokenizer files against
  the committed ``docs/milestone-4/export.manifest.json``, the llama.cpp
  checkout against the pinned commit, ``llama-server --version`` against it,
  and the code's commit (``BUNDLE.json``, else a git checkout with no
  tracked changes). ``--out`` must be new or empty: a stopped pilot is
  logged and repeated into a new directory, never resumed;
- the cases are the 20 seeded fp16 smoke-test cases (10 per tier, the same
  ``smoke_sample`` as the fp16 validation run's smoke test);
- for each variant and caching setting (on, then off) a fresh
  ``llama-server`` (CPU-only build, one slot, context 4,096, ``-b 2048
  -ub 512``, ``-ngl 0``, the platform's fixed thread count) runs under
  ``/usr/bin/time`` (``-l`` on macOS, ``-v`` on Linux) for its peak memory,
  and serves every episode twice, pass after pass, through
  ``LlamaServerModel`` with Amendment 2's decoding settings;
- episodes run exactly as in the fp16 runs (``run_episode``, the same
  prompt version, evidence rendering and action parsing) but are **not
  scored**: the pilot's accuracy is neither computed, reported nor used;
- on macOS the run stops unless on mains power and holds a
  ``caffeinate -dims`` assertion for its whole duration.

Outputs in ``<out>``: ``episodes-<variant>-cache-<on|off>.jsonl`` (every
episode: its calls with token IDs, replies and timings, and the episode's
actions), ``server-<variant>-cache-<on|off>.log`` (the server's log, with
``/usr/bin/time``'s report at the end) and ``pilot-<platform>.json``: the
platform (CPU model, threads, OS, libraries, commits), the server command
and ``system_info`` line (the CPU features the build uses), and per variant
and caching setting the peak memory, seconds per call, prompt and generation
tokens per second, projected hours for the full validation split, and
whether the two repeats of every episode are byte-identical.

``decide`` applies Amendment 2's caching and platform rules to the two
platforms' ``pilot-<platform>.json`` files and writes the choice, which is
logged in ``docs/milestone-4/EXPORT_LOG.md`` before the validation run.

Commands::

    python -m packages.support_evaluator.gguf_pilot run --platform mac --gguf-dir <dir> --tokenizer <dir> \\
        --llama-cpp <checkout> --out <dir>
    python -m packages.support_evaluator.gguf_pilot decide --mac <pilot-mac.json> --kaggle <pilot-kaggle.json> \\
        --out <decision.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform as platform_module
import re
import signal
import subprocess
import sys
import time

from packages.support_evaluator.case_sources import load_source
from packages.support_evaluator.checkpoint_selection import SMOKE_CASES, VALIDATION_SIZES
from packages.support_evaluator.local_model_baseline import bundle_commit, smoke_sample
from packages.support_evaluator.selection_subset import REPO_ROOT, SOURCES


MANIFEST = Path("docs/milestone-4/export.manifest.json")
# Thread counts are fixed per platform (Amendment 2); a Kaggle session ends after 12 hours.
PLATFORMS = {"mac": {"threads": 6, "session_hours": None}, "kaggle": {"threads": 4, "session_hours": 12.0}}
SESSION_MARGIN = 0.20  # Kaggle qualifies if each variant's projected hours ≤ 12 × (1 − 0.2) = 9.6
SERVER = {"context": 4096, "batch": 2048, "ubatch": 512, "parallel": 1, "gpu_layers": 0}
CACHING = (("on", True), ("off", False))
REPEATS = 2
# The fp16 full validation of checkpoint-0792 (docs/milestone-3/VALIDATION_LOG.md): calls per tier.
FP16_VALIDATION_CALLS = {1: 743, 2: 703}
# A repeat is identical when these agree for every call, and the episode's actions agree; timings are excluded.
IDENTITY_FIELDS = ("prompt_tokens", "token_ids", "text", "new_tokens", "stop_type", "at_limit", "finite")
SERVER_SETTING_LINES = re.compile(r"llama_context:\s+(n_ctx|n_batch|n_ubatch|n_seq_max|flash_attn|n_threads)\b.*")
EXIT_GENERATION_ERROR = 4


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)

    return digest.hexdigest()


# --- inputs ---------------------------------------------------------------------------------------------------

def variant_files(manifest: dict) -> dict[str, str]:
    """The declared variants' GGUF file names, as the export wrote them."""
    from packages.hetren_serving.export import STEM, VARIANTS

    names = {variant: f"{STEM}-{variant.lower()}.gguf" for variant in VARIANTS}
    missing = [name for name in names.values() if name not in manifest["gguf"]]

    if missing:
        raise ValueError(f"the export manifest lists no {missing}")

    return names


def verify_inputs(manifest: dict, gguf_dir: Path, tokenizer_dir: Path) -> dict[str, str]:
    """Each variant's path after checking both GGUFs and every tokenizer file against the manifest."""
    names = variant_files(manifest)

    for variant, name in names.items():
        if sha256_file(Path(gguf_dir) / name) != manifest["gguf"][name]["sha256"]:
            raise ValueError(f"{Path(gguf_dir) / name} does not have the manifest's sha256")

    expected = {k: v for k, v in manifest["merge"]["files"].items() if not k.startswith("model")}

    for name, digest in sorted(expected.items()):
        if sha256_file(Path(tokenizer_dir) / name) != digest:
            raise ValueError(f"{Path(tokenizer_dir) / name} does not have the merged model's sha256")

    return {variant: str(Path(gguf_dir) / name) for variant, name in names.items()}


def code_commit(root: Path = REPO_ROOT) -> str:
    """The bundle's commit, or the checkout's HEAD when it has no tracked changes."""
    commit = bundle_commit(root)

    if commit is None:
        raise ValueError("the code's commit is unknown (no BUNDLE.json and no git checkout)")

    if not (Path(root) / "BUNDLE.json").exists():
        changes = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, check=True,
                                 capture_output=True, text=True).stdout.strip()

        if changes:
            raise ValueError(f"the checkout has uncommitted tracked changes:\n{changes}")

    return commit


def server_version(binary: Path) -> str:
    """``llama-server --version`` (it prints to stderr); stops unless it names the pinned commit."""
    from packages.hetren_serving.export import LLAMA_CPP_COMMIT

    result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=60)
    text = (result.stdout + result.stderr).strip()

    if LLAMA_CPP_COMMIT[:8] not in text:
        raise ValueError(f"{binary} --version does not name commit {LLAMA_CPP_COMMIT[:8]}: {text!r}")

    return text


# --- the platform ---------------------------------------------------------------------------------------------

def cpu_model(system: str = sys.platform) -> str:
    if system == "darwin":
        return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], check=True, capture_output=True,
                              text=True).stdout.strip()

    for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()

    return platform_module.processor() or "unknown"


def check_platform(name: str, system: str = sys.platform, power: str | None = None) -> None:
    """Stop if ``--platform`` does not match the machine, or a Mac is on battery."""
    if name == "mac":
        if system != "darwin":
            raise ValueError(f"--platform mac on {system}")

        power = power if power is not None else subprocess.run(["pmset", "-g", "batt"], check=True,
                                                               capture_output=True, text=True).stdout

        if "'AC Power'" not in power:
            raise ValueError("the Mac is not on mains power (pmset -g batt)")
    elif system != "linux":
        raise ValueError(f"--platform kaggle on {system}")


def hold_awake(system: str = sys.platform):
    """On macOS, a ``caffeinate -dims`` process tied to this one (it ends when the pilot does)."""
    if system != "darwin":
        return None

    return subprocess.Popen(["caffeinate", "-dims", "-w", str(os.getpid())])


def time_flag(system: str = sys.platform) -> str:
    return "-l" if system == "darwin" else "-v"


def server_command(binary: Path, gguf: str, threads: int, port: int, system: str = sys.platform) -> list[str]:
    return ["/usr/bin/time", time_flag(system), str(binary), "-m", str(gguf),
            "-c", str(SERVER["context"]), "-np", str(SERVER["parallel"]), "-ngl", str(SERVER["gpu_layers"]),
            "-t", str(threads), "-b", str(SERVER["batch"]), "-ub", str(SERVER["ubatch"]),
            "--host", "127.0.0.1", "--port", str(port)]


def peak_rss_bytes(log: str) -> int | None:
    """Peak resident memory from ``/usr/bin/time``: GNU ``-v`` reports kbytes, BSD ``-l`` bytes."""
    gnu = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", log)

    if gnu:
        return int(gnu.group(1)) * 1024

    bsd = re.search(r"^\s*(\d+)\s+maximum resident set size", log, re.MULTILINE)
    return int(bsd.group(1)) if bsd else None


def system_info(log: str) -> dict[str, object] | None:
    """The server's ``system_info`` line: its thread counts and the CPU features the build uses."""
    lines = [line for line in log.splitlines() if "system_info:" in line]

    if not lines:
        return None

    line = lines[-1].split("system_info:", 1)[1].strip()
    threads = re.search(r"n_threads\s*=\s*(\d+)\s*\(n_threads_batch\s*=\s*(\d+)\)", line)
    cpu = line.split("CPU :", 1)[1] if "CPU :" in line else ""
    return {"line": line, "threads": int(threads.group(1)) if threads else None,
            "threads_batch": int(threads.group(2)) if threads else None,
            "features": {k: int(v) for k, v in re.findall(r"([A-Za-z0-9_]+)\s*=\s*(\d+)", cpu)}}


def server_settings(log: str) -> list[str]:
    """The context's settings as the server reported them (batch sizes, flash attention, threads)."""
    found = []

    for line in log.splitlines():
        match = SERVER_SETTING_LINES.search(line)

        if match and match.group(0).strip() not in found:
            found.append(match.group(0).strip())

    return found


class RunningServer:
    """``llama-server`` under ``/usr/bin/time`` for one block; SIGINT on exit lets ``time`` report."""

    def __init__(self, command: list[str], log_path: Path, url: str, model_path: str, ready_seconds: float = 900.0):
        self.command, self.log_path, self.url = command, Path(log_path), url
        self.model_path, self.ready_seconds = model_path, ready_seconds
        self.process = None
        self.load_seconds = None

    def __enter__(self):
        self.log = open(self.log_path, "w", encoding="utf-8")

        try:
            return self._start()
        except BaseException:  # __exit__ is not called when __enter__ raises: stop the server here
            self.__exit__(None, None, None)
            raise

    def _start(self):
        from packages.hetren_serving.llama_server import LlamaServer

        started = time.perf_counter()
        self.process = subprocess.Popen(self.command, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        client = LlamaServer(self.url, timeout=10)

        while True:
            if self.process.poll() is not None:
                raise RuntimeError(f"llama-server exited with {self.process.returncode}; see {self.log_path}")

            try:
                if client.request("/health").get("status") == "ok":
                    break
            except Exception:  # refused while starting, 503 while loading
                pass

            if time.perf_counter() - started > self.ready_seconds:
                raise RuntimeError(f"llama-server not ready after {self.ready_seconds:.0f} s")

            time.sleep(1)

        self.load_seconds = round(time.perf_counter() - started, 1)
        served = Path(LlamaServer(self.url).props().get("model_path", "")).name

        if served != Path(self.model_path).name:
            raise RuntimeError(f"the server on {self.url} serves {served!r}, not {Path(self.model_path).name}")

        return self

    def __exit__(self, *exc):
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGINT)  # time ignores SIGINT; the server shuts down

            try:
                self.process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()

        self.log.close()
        return False


# --- episodes -------------------------------------------------------------------------------------------------

def pilot_cases(root: Path = REPO_ROOT) -> list[tuple[int, object, int]]:
    """(tier, case, recovery limit) for the 20 smoke-test cases, tier 1 first."""
    found = []

    for tier in (1, 2):
        source = load_source(Path(root) / SOURCES[tier][0], Path(root) / SOURCES[tier][1])
        found.extend((tier, case, source.recoveries) for case in smoke_sample(source.cases, tier, SMOKE_CASES))

    return found


def run_block(model, cases, variant: str, caching: str, out_path: Path, log=print) -> None:
    """Every case ``REPEATS`` times, pass after pass, one JSON line per episode; nothing is scored."""
    from packages.hetren_baselines.prompt import action_text, system_prompt, user_message
    from packages.hetren_evidence import render_evidence
    from packages.support_evaluator.episodes import run_episode

    with open(out_path, "a", encoding="utf-8") as out:
        for repeat in range(1, REPEATS + 1):
            for tier, case, recoveries in cases:
                system = system_prompt(recoveries)
                calls, halt = [], []

                def policy(compact):
                    started = time.perf_counter()

                    try:
                        generation = model(system, user_message(render_evidence(compact)))
                    except Exception as exc:  # run_episode would record it as an invalid action: stop instead
                        halt.append(exc)
                        raise

                    calls.append({**generation.payload(), "seconds": round(time.perf_counter() - started, 3)})
                    return action_text(generation.text)

                episode = run_episode(policy, case.prepare())

                if halt:
                    raise RuntimeError(f"generation failed at tier {tier} {case.case_id} (repeat {repeat}); "
                                       f"the episode is not written") from halt[0]

                out.write(json.dumps({"variant": variant, "caching": caching, "repeat": repeat, "tier": tier,
                                      "case_id": case.case_id, "calls": calls, "episode": episode},
                                     sort_keys=True) + "\n")
                out.flush()
                log(f"{variant} cache {caching} repeat {repeat} tier {tier} {case.case_id}: {len(calls)} calls, "
                    f"{sum(c['seconds'] for c in calls):.1f} s", flush=True)


def fingerprint(record: dict) -> str:
    """What must be byte-identical between repeats: every call's tokens and reply, and the episode's actions."""
    calls = [{k: c[k] for k in IDENTITY_FIELDS} for c in record["calls"]]
    return json.dumps({"calls": calls, "episode": record["episode"]}, sort_keys=True)


def _rate(tokens: float, ms: float) -> float | None:
    return round(tokens / ms * 1000, 2) if ms else None


def block_summary(records: list[dict]) -> dict[str, object]:
    """Throughput, projection and repeat identity for one variant and caching setting."""
    by_case: dict[tuple[int, str], dict[int, str]] = {}

    for r in records:
        by_case.setdefault((r["tier"], r["case_id"]), {})[r["repeat"]] = fingerprint(r)

    differing = sorted(f"tier {t} {c}" for (t, c), reps in by_case.items()
                       if len(reps) != REPEATS or len(set(reps.values())) != 1)
    calls = {tier: [c for r in records if r["tier"] == tier for c in r["calls"]] for tier in (1, 2)}
    episodes = {tier: len([r for r in records if r["tier"] == tier]) for tier in (1, 2)}
    every = calls[1] + calls[2]
    seconds = {t: round(sum(c["seconds"] for c in calls[t]) / len(calls[t]), 3) if calls[t] else None for t in (1, 2)}
    per_episode = {t: round(len(calls[t]) / episodes[t], 3) if episodes[t] else None for t in (1, 2)}
    complete = all(seconds[t] is not None for t in (1, 2))
    by_fp16 = sum(seconds[t] * FP16_VALIDATION_CALLS[t] for t in (1, 2)) / 3600 if complete else None
    by_pilot = sum(seconds[t] * per_episode[t] * VALIDATION_SIZES[t] for t in (1, 2)) / 3600 if complete else None
    return {
        "episodes": len(records), "cases": len(by_case),
        "repeats_identical": len(by_case) - len(differing), "differing": differing,
        "all_identical": not differing and len(by_case) == 2 * SMOKE_CASES,
        "calls": {f"tier{t}": len(calls[t]) for t in (1, 2)},
        "calls_per_episode": {f"tier{t}": per_episode[t] for t in (1, 2)},
        "seconds_per_call": {f"tier{t}": seconds[t] for t in (1, 2)},
        "seconds_per_call_by_repeat": {
            str(k): round(sum(c["seconds"] for r in records if r["repeat"] == k for c in r["calls"])
                          / max(1, sum(len(r["calls"]) for r in records if r["repeat"] == k)), 3)
            for k in range(1, REPEATS + 1)},
        "prompt_tokens_per_second": _rate(sum(c["prompt_n"] for c in every), sum(c["prompt_ms"] for c in every)),
        "generation_tokens_per_second": _rate(sum(c["predicted_n"] for c in every),
                                              sum(c["predicted_ms"] for c in every)),
        "mean_prompt_tokens": round(sum(c["prompt_tokens"] for c in every) / len(every), 1) if every else None,
        "mean_prompt_tokens_evaluated": round(sum(c["prompt_n"] for c in every) / len(every), 1) if every else None,
        "non_finite_calls": sum(not c["finite"] for c in every),
        "at_token_limit": sum(c["at_limit"] for c in every),
        "empty_replies": sum(not c["text"].strip() for c in every),
        "projected_hours": {
            "by_fp16_calls": round(by_fp16, 2) if by_fp16 is not None else None,
            "by_pilot_calls_per_episode": round(by_pilot, 2) if by_pilot is not None else None,
            "projected": round(max(by_fp16, by_pilot), 2) if complete else None,
        },
    }


def episodes_agree_across_caching(on: list[dict], off: list[dict]) -> int:
    """Informational: episodes whose first repeat is identical with caching on and off."""
    first = lambda records: {(r["tier"], r["case_id"]): fingerprint(r) for r in records if r["repeat"] == 1}
    a, b = first(on), first(off)
    return sum(a[k] == b.get(k) for k in a)


def installed_packages() -> list[str]:
    """Every installed distribution as ``name==version`` (requirements-gguf-pilot.txt pins only the top level)."""
    from importlib.metadata import distributions

    return sorted({f"{d.metadata['Name']}=={d.version}" for d in distributions()}, key=str.lower)


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


# --- run ------------------------------------------------------------------------------------------------------

def run(args: argparse.Namespace, log=print) -> int:
    from packages.hetren_serving.export import LLAMA_CPP_COMMIT, VARIANTS, library_versions, verify_llama_cpp

    out = Path(args.out)

    if out.exists() and any(out.iterdir()):
        print(f"STOP: {out} is not empty; a stopped pilot is logged and repeated into a new directory",
              file=sys.stderr)
        return 2

    try:
        check_platform(args.platform)
        commit = code_commit()
        manifest_path = REPO_ROOT / MANIFEST
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ggufs = verify_inputs(manifest, args.gguf_dir, args.tokenizer)
        verify_llama_cpp(args.llama_cpp, LLAMA_CPP_COMMIT)
        binary = Path(args.llama_cpp) / "build" / "bin" / "llama-server"
        version = server_version(binary)

        if not Path("/usr/bin/time").exists():
            raise ValueError("/usr/bin/time is missing")
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

    threads = PLATFORMS[args.platform]["threads"]

    if (os.cpu_count() or 0) < threads:
        print(f"STOP: {os.cpu_count()} logical CPUs, fewer than the platform's {threads} threads", file=sys.stderr)
        return 2

    from transformers import AutoTokenizer

    from packages.hetren_serving.llama_server import DecodingSettings, LlamaServer, LlamaServerModel

    awake = hold_awake()
    out.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer))
    cases = pilot_cases()
    url = f"http://127.0.0.1:{args.port}"
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    blocks: dict[str, dict[str, dict]] = {}
    log(f"pilot on {args.platform}: {len(cases)} cases × {REPEATS} repeats × {len(CACHING)} caching settings × "
        f"{len(VARIANTS)} variants, {threads} threads", flush=True)

    try:
        for variant in VARIANTS:
            for caching, cache_prompt in CACHING:
                stem = f"{variant}-cache-{caching}"
                command = server_command(binary, ggufs[variant], threads, args.port)
                began = time.perf_counter()

                try:
                    with RunningServer(command, out / f"server-{stem}.log", url, ggufs[variant]) as server:
                        model = LlamaServerModel(tokenizer, LlamaServer(url), DecodingSettings(cache_prompt=cache_prompt))
                        run_block(model, cases, variant, caching, out / f"episodes-{stem}.jsonl", log)
                except Exception as exc:  # generation or server errors: stop; the partial block stays for the log
                    print(f"STOP in {stem}: {type(exc).__name__}: {exc}", file=sys.stderr)
                    return EXIT_GENERATION_ERROR

                server_log = (out / f"server-{stem}.log").read_text(encoding="utf-8", errors="replace")
                blocks.setdefault(variant, {})[caching] = {
                    **block_summary(read_jsonl(out / f"episodes-{stem}.jsonl")),
                    "peak_rss_bytes": peak_rss_bytes(server_log), "system_info": system_info(server_log),
                    "server_settings": server_settings(server_log), "load_seconds": server.load_seconds,
                    "block_minutes": round((time.perf_counter() - began) / 60, 1),
                }
    finally:
        if awake is not None:
            awake.terminate()

    for variant in VARIANTS:
        blocks[variant]["episodes_agree_on_and_off"] = episodes_agree_across_caching(
            read_jsonl(out / f"episodes-{variant}-cache-on.jsonl"),
            read_jsonl(out / f"episodes-{variant}-cache-off.jsonl"))

    report = {
        "amendment": "EVAL_PROTOCOL.md, Amendment 2, Throughput pilot",
        "platform": args.platform, "cpu": cpu_model(), "logical_cpus": os.cpu_count(), "threads": threads,
        "os": platform_module.platform(), "libraries": library_versions(("transformers", "tokenizers",
                                                                          "huggingface_hub", "jinja2")),
        "environment": installed_packages(),
        "bundle_commit": commit, "llama_cpp_commit": LLAMA_CPP_COMMIT, "server_version": version,
        "server_command": server_command(binary, "<gguf>", threads, args.port),
        "settings": {**SERVER, "threads": threads, "decoding": DecodingSettings(cache_prompt=True).payload([])
                     | {"prompt": "<token IDs>", "cache_prompt": "per block"}},
        "manifest_sha256": sha256_file(manifest_path),
        "gguf_sha256": {v: manifest["gguf"][Path(p).name]["sha256"] for v, p in ggufs.items()},
        "cases": [f"tier {t} {case.case_id}" for t, case, _ in cases], "repeats": REPEATS,
        "started_utc": started_utc, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "variants": blocks,
        "files": {p.name: sha256_file(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    (out / f"pilot-{args.platform}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                                     encoding="utf-8")
    log(json.dumps({v: {c: {k: b[c][k] for k in ("repeats_identical", "seconds_per_call", "projected_hours",
                                                   "peak_rss_bytes")} for c, _ in CACHING}
                    for v, b in blocks.items()}, indent=2), flush=True)
    return 0


# --- decide ---------------------------------------------------------------------------------------------------

def decide(reports: dict[str, dict]) -> dict[str, object]:
    """Amendment 2's caching rule, then its platform rule, over both platforms' pilot reports."""
    from packages.hetren_serving.export import VARIANTS

    if sorted(reports) != sorted(PLATFORMS):
        raise ValueError(f"expected pilot reports for {sorted(PLATFORMS)}, found {sorted(reports)}")

    hashes = {json.dumps(r["gguf_sha256"], sort_keys=True) for r in reports.values()}
    commits = {r["llama_cpp_commit"] for r in reports.values()}

    if len(hashes) != 1 or len(commits) != 1:
        raise ValueError("the platforms ran different GGUF files or llama.cpp commits")

    differs = {caching: sorted(f"{name} {variant}" for name, r in reports.items() for variant in VARIANTS
                               if not r["variants"][variant][caching]["all_identical"])
               for caching, _ in CACHING}
    features = {name: {variant: {caching: (r["variants"][variant][caching]["system_info"] or {}).get("features")
                                 for caching, _ in CACHING} for variant in VARIANTS} for name, r in reports.items()}
    flat = {name: {json.dumps(f, sort_keys=True) for by in fs.values() for f in by.values()}
            for name, fs in features.items()}
    result = {
        "repeats_differ": differs,
        "cpu_features": {name: sorted(values) for name, values in flat.items()},
        "same_cpu_features": len(set().union(*flat.values())) == 1,
        "bundle_commits": {name: r["bundle_commit"] for name, r in reports.items()},
    }

    if differs["on"] and differs["off"]:
        return {**result, "caching": None, "qualifies": {}, "platform": None, "validation_starts": False,
                "reason": "repeated episodes differ with caching on and with it off; the validation run does not start"}

    caching = "off" if differs["on"] else "on"
    qualifies = {}

    for name, r in reports.items():
        limit = PLATFORMS[name]["session_hours"]
        hours = {v: r["variants"][v][caching]["projected_hours"]["projected"] for v in VARIANTS}
        fits = all(h is not None for h in hours.values()) and (
            limit is None or all(h <= limit * (1 - SESSION_MARGIN) for h in hours.values()))
        identical = all(r["variants"][v][caching]["all_identical"] for v in VARIANTS)
        qualifies[name] = {"projected_hours": hours, "session_hours": limit, "fits": fits, "identical": identical,
                           "qualifies": fits and identical}

    chosen = "kaggle" if qualifies["kaggle"]["qualifies"] else "mac" if qualifies["mac"]["qualifies"] else None
    return {**result, "caching": caching, "qualifies": qualifies, "platform": chosen,
            "validation_starts": chosen is not None,
            "reason": f"caching {caching}; " + (f"{chosen} qualifies" + (" (Kaggle is preferred)" if chosen == "kaggle"
                                                                         and qualifies["mac"]["qualifies"] else "")
                                                if chosen else "neither platform qualifies; the operator decides")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="the pilot on this platform")
    run_parser.add_argument("--platform", required=True, choices=sorted(PLATFORMS))
    run_parser.add_argument("--gguf-dir", required=True, type=Path, help="the export's directory with both GGUF files")
    run_parser.add_argument("--tokenizer", required=True, type=Path, help="the export's tokenizer/ directory")
    run_parser.add_argument("--llama-cpp", required=True, type=Path, help="the llama.cpp checkout, built in build/")
    run_parser.add_argument("--out", required=True, type=Path)
    run_parser.add_argument("--port", type=int, default=8080)
    decide_parser = commands.add_parser("decide", help="the caching and platform choice from both pilots")
    decide_parser.add_argument("--mac", required=True, type=Path)
    decide_parser.add_argument("--kaggle", required=True, type=Path)
    decide_parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "run":
        return run(args)

    reports = {"mac": json.loads(args.mac.read_text(encoding="utf-8")),
               "kaggle": json.loads(args.kaggle.read_text(encoding="utf-8"))}
    choice = decide(reports)
    args.out.write_text(json.dumps(choice, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(choice, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
