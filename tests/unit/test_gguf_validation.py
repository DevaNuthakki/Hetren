"""The GGUF validation run: the declared settings, the layout gguf_check reads, resume logging and stops."""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
from pathlib import Path

import pytest

from packages.hetren_serving import export
from packages.support_evaluator import gguf_check, gguf_validation as validation


CASES = {1: ["case-1", "case-2", "case-3"], 2: ["case-1", "case-9"]}  # a case ID shared by both tiers
SIZES = {1: 3, 2: 2}
MANIFEST = json.loads((validation.REPO_ROOT / validation.MANIFEST).read_text(encoding="utf-8"))


class FakeRunner:
    """Stands in for run_baseline: the same metadata check and resume by case, rows and calls with token IDs."""

    def __init__(self, fail_after=None, last_token=151645):
        self.fail_after, self.last_token, self.calls = fail_after, last_token, []

    def __call__(self, args, generate, metadata, *, show_results=True):
        assert show_results is False and args.smoke is None and "validation.txt" in str(args.split)
        self.calls.append(metadata)
        out = Path(args.out)
        path = out / "metadata.json"

        if path.exists():
            if json.loads(path.read_text()) != {**metadata, "prompt_version": 2}:
                return 2
        else:
            path.write_text(json.dumps({**metadata, "prompt_version": 2}))

        tier = metadata["tier"]
        rows = out / f"rows-tier{tier}-validation.jsonl"
        done = {json.loads(line)["case_id"] for line in rows.open()} if rows.exists() else set()

        for i, case in enumerate(c for c in CASES[tier] if c not in done):
            if self.fail_after is not None and i == self.fail_after:
                self.fail_after = None
                return 4

            token = self.last_token if case == "case-9" else 151645
            with (out / "calls.jsonl").open("a") as calls:
                calls.write(json.dumps({"tier": tier, "case_id": case, "call": 0, "text": "{}", "seconds": 3.0,
                                        "finite": True, "at_limit": False, "token_ids": [5, token],
                                        "discarded": False}) + "\n")
            with rows.open("a") as handle:
                handle.write(json.dumps({"case_id": case, "correct": True}) + "\n")

        return 0


class FakeServer:
    def __init__(self, command, log_path, url, model_path):
        self.command, self.log_path = command, Path(log_path)

    def __enter__(self):
        self.log_path.write_text("srv ready\n")
        return self

    def __exit__(self, *exc):
        with self.log_path.open("a") as log:
            log.write("        5000000000  maximum resident set size\n")
        return False


@pytest.fixture
def harness(tmp_path, monkeypatch):
    llama = tmp_path / "llama.cpp"
    (llama / "build" / "bin").mkdir(parents=True)
    (llama / "build" / "bin" / "llama-server").write_text("binary")
    gguf = f"{export.STEM}-q4_k_m.gguf"
    monkeypatch.setattr(validation, "check_platform", lambda name: None)
    monkeypatch.setattr(validation, "cpu_model", lambda: validation.PILOT_CPU)
    monkeypatch.setattr(validation, "checkout_commit", lambda: "c0ffee")
    monkeypatch.setattr(validation, "verify_dataset", lambda tier: {"hetren_visible.jsonl": f"d{tier}"})
    monkeypatch.setattr(validation, "verify_variant", lambda manifest, variant, d, t: str(tmp_path / gguf))
    monkeypatch.setattr(export, "verify_llama_cpp", lambda checkout, commit: None)
    monkeypatch.setattr(validation, "server_version", lambda binary: "version: 0.7.0-dev (build 11669, commit 620d2225c)")
    monkeypatch.setattr(validation, "probe_system_info", lambda binary, threads: {"line": "n_threads = 6 | CPU : AVX2 = 1 |",
                                                                                 "features": {"AVX2": 1}})
    monkeypatch.setattr(validation, "TIME", tmp_path)  # exists
    monkeypatch.setattr(validation, "hold_awake", lambda: None)
    monkeypatch.setattr(validation, "load_tokenizer", lambda path: object())
    monkeypatch.setattr(validation, "RunningServer", FakeServer)
    monkeypatch.setattr(validation, "load_source", lambda dataset, split: argparse.Namespace(
        cases=[argparse.Namespace(case_id=c) for c in CASES[1 if "dataset-v2" in str(dataset) else 2]]))
    monkeypatch.setattr(validation, "VALIDATION_SIZES", SIZES)
    monkeypatch.setattr(gguf_check, "VALIDATION_SIZES", SIZES)
    args = argparse.Namespace(variant="Q4_K_M", gguf_dir=tmp_path, tokenizer=tmp_path, llama_cpp=llama,
                              out=tmp_path / "runs", port=8080)
    return args, monkeypatch


def test_a_completed_run_is_what_gguf_check_reads(harness):
    args, monkeypatch = harness
    runner = FakeRunner()
    monkeypatch.setattr(validation, "run_baseline", runner)
    assert validation.run(args, log=lambda *a, **k: None) == 0

    loaded = gguf_check.load_gguf(args.out, "Q4_K_M", MANIFEST)  # hashes, declared settings and case counts
    assert {t: len(loaded[t]["rows"]) for t in (1, 2)} == {1: 3, 2: 2}
    metadata = loaded[1]["metadata"]
    assert (metadata["platform"], metadata["threads"], metadata["cache_prompt"]) == ("mac", 6, True)
    assert metadata["gguf_sha256"] == MANIFEST["gguf"][f"{export.STEM}-q4_k_m.gguf"]["sha256"]
    assert metadata["server"] == {"context": 4096, "batch": 2048, "ubatch": 512, "parallel": 1, "gpu_layers": 0, "threads": 6}
    assert metadata["decoding_payload"]["cache_prompt"] is True and metadata["decoding_payload"]["top_k"] == 1
    assert metadata["system_info"]["features"] == {"AVX2": 1} and metadata["bundle_commit"] == "c0ffee"
    record = json.loads((args.out / "Q4_K_M" / "tier1" / "validation-Q4_K_M-tier1.json").read_text())
    assert record["restarts"] == [] and record["unexpected_stops"]["calls"] == 0
    assert [s["event"] for s in record["sessions"]] == ["start", "stop"]
    assert record["sessions"][1]["peak_rss_bytes"] == 5_000_000_000

    # A completed tier is skipped by the same command.
    assert validation.run(args, log=lambda *a, **k: None) == 0 and len(runner.calls) == 2


def test_a_stopped_tier_resumes_and_the_restart_case_is_logged(harness, capsys):
    args, monkeypatch = harness
    monkeypatch.setattr(validation, "run_baseline", FakeRunner(fail_after=1))
    assert validation.run(args, log=lambda *a, **k: None) == 4
    assert "run the same command again" in capsys.readouterr().err
    assert not (args.out / "Q4_K_M" / "tier1" / "validation-Q4_K_M-tier1.json").exists()

    assert validation.run(args, log=lambda *a, **k: None) == 0
    directory = args.out / "Q4_K_M" / "tier1"
    record = json.loads((directory / "validation-Q4_K_M-tier1.json").read_text())
    assert record["restarts"] == [{"started_utc": record["restarts"][0]["started_utc"], "first_case": "case-2",
                                   "done_before": 1}]
    assert sorted(p.name for p in directory.glob("server-*.log")) == ["server-1.log", "server-2.log"]
    stops = [s for s in record["sessions"] if s["event"] == "stop"]
    assert [(s["exit"], s["done"]) for s in stops] == [(4, 1), (0, 3)]
    gguf_check.load_gguf(args.out, "Q4_K_M", MANIFEST)


def test_a_resume_on_a_commit_that_changed_the_runs_inputs_stops(harness, capsys):
    args, monkeypatch = harness
    monkeypatch.setattr(validation, "run_baseline", FakeRunner(fail_after=1))
    assert validation.run(args, log=lambda *a, **k: None) == 4
    monkeypatch.setattr(validation, "checkout_commit", lambda: "beef")
    monkeypatch.setattr(validation, "changed_inputs", lambda old, new: ["packages/support_evaluator/episodes.py"])
    assert validation.run(args, log=lambda *a, **k: None) == 2
    assert "the run's inputs changed since" in capsys.readouterr().err

    # Only the log changed: the resume keeps the first commit in the metadata and records its own HEAD.
    monkeypatch.setattr(validation, "changed_inputs", lambda old, new: [])
    assert validation.run(args, log=lambda *a, **k: None) == 0
    sessions = [json.loads(line) for line in (args.out / "Q4_K_M" / "tier1" / "sessions.jsonl").open()]
    assert [s["head"] for s in sessions if s["event"] == "start"][-1] == "beef"
    assert json.loads((args.out / "Q4_K_M" / "tier1" / "metadata.json").read_text())["bundle_commit"] == "c0ffee"


def test_a_generation_not_ending_on_the_models_end_tokens_is_recorded_with_its_case(harness):
    args, monkeypatch = harness
    monkeypatch.setattr(validation, "run_baseline", FakeRunner(last_token=128247))
    assert validation.run(args, log=lambda *a, **k: None) == 0
    record = json.loads((args.out / "Q4_K_M" / "tier2" / "validation-Q4_K_M-tier2.json").read_text())
    assert record["unexpected_stops"] == {"calls": 1, "cases": ["tier 2 case-9"], "last_tokens": [128247]}


def test_another_cpu_or_a_missing_input_stops_before_anything_runs(harness, capsys):
    args, monkeypatch = harness
    monkeypatch.setattr(validation, "run_baseline", lambda *a, **k: pytest.fail("ran"))
    monkeypatch.setattr(validation, "cpu_model", lambda: "Intel(R) Xeon(R) CPU @ 2.20GHz")
    assert validation.run(args) == 2 and "not the pilot's" in capsys.readouterr().err

    monkeypatch.setattr(validation, "cpu_model", lambda: validation.PILOT_CPU)
    monkeypatch.setattr(validation, "verify_variant", lambda *a: (_ for _ in ()).throw(ValueError("bad gguf")))
    assert validation.run(args) == 2 and "bad gguf" in capsys.readouterr().err


def test_only_validation_splits_and_the_declared_variants_can_be_run():
    with pytest.raises(SystemExit):
        validation.main(["run", "--variant", "Q4_K_M", "--gguf-dir", "x", "--tokenizer", "x", "--llama-cpp", "x",
                         "--out", "x", "--split", "test_held_out"])

    with pytest.raises(SystemExit):
        validation.main(["run", "--variant", "F16", "--gguf-dir", "x", "--tokenizer", "x", "--llama-cpp", "x", "--out", "x"])

    assert all(path.endswith("/validation.txt") for _, path in validation.SOURCES.values())


def _repo(tmp_path):
    root = tmp_path / "repo"
    (root / "docs/milestone-4").mkdir(parents=True)
    (root / "packages").mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)
    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    (root / validation.EXPORT_LOG).write_text("log\n")
    (root / "packages/x.py").write_text("x = 1\n")
    run("add", ".")
    run("commit", "-qm", "one")
    return root, run


def test_only_the_export_log_may_differ_from_the_commit(tmp_path):
    root, run = _repo(tmp_path)
    head = validation.checkout_commit(root)
    (root / validation.EXPORT_LOG).write_text("log\nstop logged\n")
    assert validation.checkout_commit(root) == head
    (root / "packages/x.py").write_text("x = 2\n")

    with pytest.raises(ValueError, match="packages/x.py"):
        validation.checkout_commit(root)


def test_changed_inputs_lists_only_the_runs_inputs(tmp_path):
    root, run = _repo(tmp_path)
    first = validation.checkout_commit(root)
    (root / validation.EXPORT_LOG).write_text("log\nstop logged\n")
    run("commit", "-qam", "log")
    second = validation.checkout_commit(root)
    assert validation.changed_inputs(first, second, root) == []
    (root / "packages/x.py").write_text("x = 2\n")
    run("commit", "-qam", "code")
    assert validation.changed_inputs(first, validation.checkout_commit(root), root) == ["packages/x.py"]


def test_datasets_are_checked_against_their_committed_manifests(tmp_path):
    for tier, (dataset, _) in validation.SOURCES.items():
        d = tmp_path / dataset
        (d / "evaluator").mkdir(parents=True)

        for name in validation.DATA_FILES:
            (d / name).write_text(name)

        (tmp_path / "docs/milestone-2").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs/milestone-2" / f"{Path(dataset).name}.manifest.json").write_text(json.dumps(
            {"files": {name: validation.sha256_file(d / name) for name in validation.DATA_FILES}}))

    assert set(validation.verify_dataset(1, tmp_path)) == set(validation.DATA_FILES)
    (tmp_path / validation.SOURCES[2][0] / "hetren_visible.jsonl").write_text("changed")

    with pytest.raises(ValueError, match="does not match docs/milestone-2/dataset-v3.manifest.json"):
        validation.verify_dataset(2, tmp_path)


def test_the_system_info_probe_loads_no_model():
    seen = []

    def run(command, **kwargs):
        seen.append(command)
        return argparse.Namespace(stdout="", stderr="0.00 I cmn common_param: system_info: n_threads = 6 "
                                                    "(n_threads_batch = 6) / 12 | CPU : AVX2 = 1 | FMA = 1 |\nerror\n")

    info = validation.probe_system_info(Path("/b/llama-server"), 6, run=run)
    assert info["features"] == {"AVX2": 1, "FMA": 1} and info["threads"] == 6
    assert seen[0][:5] == ["/b/llama-server", "-lv", "4", "-t", "6"] and "/nonexistent/" in seen[0][6]
