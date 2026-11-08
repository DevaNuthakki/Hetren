"""The GGUF throughput pilot (Amendment 2): the fp16 smoke cases, unscored episodes, repeat identity and the rules."""

from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path

import pytest

from packages.hetren_serving.export import STEM, VARIANTS
from packages.hetren_serving.llama_server import LlamaGeneration
from packages.support_evaluator import gguf_pilot as pilot
from packages.support_evaluator import local_model_baseline


class Case:
    def __init__(self, case_id):
        self.case_id = case_id

    def prepare(self):
        return {"case": self.case_id}

    def score(self, *args):  # the pilot never scores
        raise AssertionError("the pilot scored an episode")


def test_smoke_sample_is_the_fp16_runs_seeded_sample_in_case_order():
    cases = [Case(f"case-{i:06d}") for i in range(550)]
    expected = sorted(random.Random("smoke:2").sample(cases, 10), key=lambda c: c.case_id)  # the earlier inline code
    assert local_model_baseline.smoke_sample(cases, 2, 10) == expected
    assert local_model_baseline.smoke_sample(cases[:3], 1, 10) == cases[:3]


def test_pilot_cases_are_ten_smoke_cases_per_tier_with_each_tiers_recovery_limit(monkeypatch):
    seen = []

    def load_source(dataset, split):
        seen.append((Path(dataset).name, Path(split).name))
        tier = 1 if "dataset-v2" in str(dataset) else 2
        return argparse.Namespace(cases=[Case(f"t{tier}-{i:03d}") for i in range(40)], recoveries=tier)

    monkeypatch.setattr(pilot, "load_source", load_source)
    cases = pilot.pilot_cases()
    assert seen == [("dataset-v2", "validation.txt"), ("dataset-v3", "validation.txt")]
    assert [(t, r) for t, _, r in cases] == [(1, 1)] * 10 + [(2, 2)] * 10
    assert [c.case_id for t, c, _ in cases if t == 2] == [c.case_id for c in local_model_baseline.smoke_sample(
        [Case(f"t2-{i:03d}") for i in range(40)], 2, 10)]


def test_server_command_has_amendment_2s_settings_under_usr_bin_time():
    for system, flag in (("darwin", "-l"), ("linux", "-v")):
        assert pilot.server_command(Path("/b/llama-server"), "/m/x.gguf", 6, 8080, system) == [
            "/usr/bin/time", flag, "/b/llama-server", "-m", "/m/x.gguf", "-c", "4096", "-np", "1", "-ngl", "0",
            "-t", "6", "-b", "2048", "-ub", "512", "--host", "127.0.0.1", "--port", "8080"]
    assert pilot.PLATFORMS["mac"]["threads"] == 6 and pilot.PLATFORMS["kaggle"]["threads"] == 4


SYSTEM_INFO = ("main: system_info: n_threads = 4 (n_threads_batch = 4) / 4 | CPU : SSE3 = 1 | SSSE3 = 1 | AVX = 1 | "
               "AVX2 = 1 | F16C = 1 | FMA = 1 | BMI2 = 1 | LLAMAFILE = 1 | OPENMP = 1 | REPACK = 1 |")


def test_peak_memory_system_info_and_settings_are_read_from_the_server_log():
    gnu = "srv done\n\tCommand terminated by signal 2\n\tMaximum resident set size (kbytes): 4300000\n"
    bsd = "srv done\n        4402446336  maximum resident set size\n           0  average shared memory size\n"
    assert pilot.peak_rss_bytes(gnu) == 4300000 * 1024
    assert pilot.peak_rss_bytes(bsd) == 4402446336
    assert pilot.peak_rss_bytes("no report") is None
    info = pilot.system_info(f"build: b11669\n{SYSTEM_INFO}\n")
    assert (info["threads"], info["threads_batch"]) == (4, 4)
    assert info["features"] == {"SSE3": 1, "SSSE3": 1, "AVX": 1, "AVX2": 1, "F16C": 1, "FMA": 1, "BMI2": 1,
                                "LLAMAFILE": 1, "OPENMP": 1, "REPACK": 1}
    assert pilot.system_info("nothing") is None
    log = ("llama_context: n_ctx         = 4096\nllama_context: n_ctx_per_seq = 4096\n"
           "llama_context: n_batch       = 2048\nllama_context: n_ubatch      = 512\n"
           "llama_context: flash_attn    = auto\nllama_context: n_batch       = 2048\n")
    assert pilot.server_settings(log) == ["llama_context: n_ctx         = 4096", "llama_context: n_batch       = 2048",
                                          "llama_context: n_ubatch      = 512", "llama_context: flash_attn    = auto"]


def _call(text="{}", tokens=(1, 2), seconds=4.0, **timings):
    return {"prompt_tokens": 1500, "token_ids": list(tokens), "text": text, "new_tokens": len(tokens),
            "stop_type": "eos", "at_limit": False, "finite": True, "seconds": seconds, "server_seconds": seconds,
            "prompt_n": timings.get("prompt_n", 500), "prompt_ms": timings.get("prompt_ms", 2500.0),
            "predicted_n": len(tokens), "predicted_ms": timings.get("predicted_ms", 200.0),
            "tokens_cached": timings.get("tokens_cached", 1000), "tokens_evaluated": 1500}


def _records(change=None, calls_per_episode=(1, 2), seconds=(4.0, 5.0)):
    records = []

    for repeat in (1, 2):
        for tier in (1, 2):
            for i in range(10):
                calls = [_call(seconds=seconds[tier - 1], tokens=(1, 2), tokens_cached=repeat * 7)
                         for _ in range(calls_per_episode[tier - 1])]
                records.append({"variant": "Q8_0", "caching": "on", "repeat": repeat, "tier": tier,
                                "case_id": f"case-{tier}{i}", "calls": calls,
                                "episode": {"final": {"action": "decide"}, "failure": None}})

    if change:
        change(records)

    return records


def test_repeats_are_identical_when_only_timings_and_cache_counts_differ():
    summary = pilot.block_summary(_records())
    assert summary["all_identical"] and summary["repeats_identical"] == 20 and summary["differing"] == []
    assert summary["calls"] == {"tier1": 20, "tier2": 40}
    assert summary["seconds_per_call"] == {"tier1": 4.0, "tier2": 5.0}
    assert summary["prompt_tokens_per_second"] == 200.0 and summary["generation_tokens_per_second"] == 10.0
    # 4.0 s × 743 + 5.0 s × 703 = 6,487 s; 4.0 s × 1 × 550 + 5.0 s × 2 × 250 = 4,700 s; the larger is projected.
    assert summary["projected_hours"] == {"by_fp16_calls": 1.8, "by_pilot_calls_per_episode": 1.31, "projected": 1.8}


@pytest.mark.parametrize("field, value", [("token_ids", [1, 3]), ("text", "{ }"), ("stop_type", "limit"),
                                          ("prompt_tokens", 1501), ("finite", False)])
def test_any_difference_in_a_calls_tokens_or_reply_breaks_identity(field, value):
    def change(records):
        records[25]["calls"][0][field] = value  # repeat 2, tier 1, case-15

    summary = pilot.block_summary(_records(change))
    assert not summary["all_identical"] and summary["differing"] == ["tier 1 case-15"]


def test_a_different_action_or_a_missing_repeat_breaks_identity():
    def other_action(records):
        records[30]["episode"] = {"final": {"action": "recover"}, "failure": None}

    assert pilot.block_summary(_records(other_action))["differing"] == ["tier 2 case-20"]
    assert pilot.block_summary(_records(lambda r: r.pop()))["differing"] == ["tier 2 case-29"]


def test_run_block_runs_every_case_twice_pass_after_pass_and_never_scores(tmp_path, monkeypatch):
    import packages.support_evaluator.episodes as episodes

    def run_episode(policy, prepared):
        policy({"evidence": prepared["case"]})
        return {"final": {"action": "decide"}, "case": prepared["case"]}

    monkeypatch.setattr(episodes, "run_episode", run_episode)
    prompts = []

    def model(system, user):
        prompts.append((system, user))
        return LlamaGeneration(text='{"action": "decide"}', prompt_tokens=10, new_tokens=2, finite=True,
                               at_limit=False, stop_type="eos", token_ids=(5, 6), prompt_ms=10.0, predicted_n=2)

    cases = [(1, Case("a"), 1), (2, Case("b"), 2)]
    path = tmp_path / "episodes.jsonl"
    pilot.run_block(model, cases, "Q8_0", "on", path, log=lambda *a, **k: None)
    records = pilot.read_jsonl(path)
    assert [(r["repeat"], r["tier"], r["case_id"]) for r in records] == [(1, 1, "a"), (1, 2, "b"), (2, 1, "a"), (2, 2, "b")]
    assert records[0]["calls"][0]["token_ids"] == [5, 6] and "seconds" in records[0]["calls"][0]
    assert "correct" not in json.dumps(records)
    from packages.hetren_baselines.prompt import system_prompt
    assert prompts[0][0] == system_prompt(1) and prompts[1][0] == system_prompt(2)


def test_a_generation_error_stops_the_block_instead_of_becoming_an_invalid_action(tmp_path, monkeypatch):
    import packages.support_evaluator.episodes as episodes

    def run_episode(policy, prepared):  # as run_episode does: a policy exception becomes an invalid action
        try:
            policy({})
        except Exception:
            return {"final": None, "failure": "invalid_action:RuntimeError"}

    monkeypatch.setattr(episodes, "run_episode", run_episode)

    def model(system, user):
        raise ConnectionError("server gone")

    path = tmp_path / "episodes.jsonl"

    with pytest.raises(RuntimeError, match="generation failed at tier 1 a"):
        pilot.run_block(model, [(1, Case("a"), 1)], "Q8_0", "on", path, log=lambda *a, **k: None)

    assert path.read_text() == ""


def _report(platform, identical=None, hours=2.0, features=None, missing_features=False):
    identical = identical or {}
    info = None if missing_features else {"features": features or {"AVX2": 1, "FMA": 1}}
    variants = {v: {c: {"all_identical": identical.get((v, c), True), "projected_hours": {"projected": hours},
                        "system_info": info} for c in ("on", "off")} for v in VARIANTS}
    return {"platform": platform, "gguf_sha256": {"Q8_0": "a", "Q4_K_M": "b"}, "llama_cpp_commit": "620d",
            "bundle_commit": "c0ffee", "variants": variants}


def test_decide_prefers_kaggle_with_caching_on_when_everything_is_identical():
    choice = pilot.decide({"mac": _report("mac", hours=5.0), "kaggle": _report("kaggle", hours=8.0)})
    assert (choice["caching"], choice["platform"], choice["validation_starts"]) == ("on", "kaggle", True)
    assert choice["same_cpu_features"] and choice["qualifies"]["mac"]["qualifies"]


def test_kaggle_needs_a_20_percent_margin_within_its_12_hours_so_at_most_9_6_hours():
    assert pilot.decide({"mac": _report("mac"), "kaggle": _report("kaggle", hours=9.6)})["platform"] == "kaggle"
    choice = pilot.decide({"mac": _report("mac", hours=30.0), "kaggle": _report("kaggle", hours=9.61)})
    assert choice["platform"] == "mac" and not choice["qualifies"]["kaggle"]["fits"]


def test_caching_is_off_when_repeats_differ_only_with_caching_on():
    mac = _report("mac", identical={("Q4_K_M", "on"): False})
    choice = pilot.decide({"mac": mac, "kaggle": _report("kaggle")})
    assert (choice["caching"], choice["platform"]) == ("off", "kaggle")
    assert choice["repeats_differ"] == {"on": ["mac Q4_K_M"], "off": []}


def test_a_platform_whose_repeats_differ_under_the_chosen_setting_does_not_qualify():
    kaggle = _report("kaggle", identical={("Q8_0", "off"): False})
    choice = pilot.decide({"mac": _report("mac"), "kaggle": kaggle})
    assert choice["caching"] == "on" and choice["platform"] == "kaggle"  # off differs, on does not: caching on
    neither = pilot.decide({"mac": _report("mac", hours=None), "kaggle": _report("kaggle", hours=11.0)})
    assert neither["platform"] is None and not neither["validation_starts"]


def test_no_validation_run_when_repeats_differ_with_caching_on_and_off():
    mac = _report("mac", identical={("Q8_0", "on"): False})
    kaggle = _report("kaggle", identical={("Q8_0", "off"): False})
    choice = pilot.decide({"mac": mac, "kaggle": kaggle})
    assert choice["caching"] is None and not choice["validation_starts"]


def test_decide_needs_both_platforms_on_the_same_files_and_reports_feature_differences():
    with pytest.raises(ValueError, match="expected pilot reports"):
        pilot.decide({"mac": _report("mac")})

    other = _report("kaggle")
    other["gguf_sha256"] = {"Q8_0": "z", "Q4_K_M": "b"}

    with pytest.raises(ValueError, match="different GGUF files"):
        pilot.decide({"mac": _report("mac"), "kaggle": other})

    choice = pilot.decide({"mac": _report("mac"), "kaggle": _report("kaggle", features={"AVX2": 1, "AVX512": 1})})
    assert not choice["same_cpu_features"] and choice["platform"] == "kaggle"  # informational, not a gate


def _manifest(tmp_path):
    gguf, tok = tmp_path / "gguf", tmp_path / "tokenizer"
    gguf.mkdir()
    tok.mkdir()
    files = {"model-00001-of-00002.safetensors": "x"}
    entries = {}

    for variant in VARIANTS:
        path = gguf / f"{STEM}-{variant.lower()}.gguf"
        path.write_bytes(variant.encode())
        entries[path.name] = {"sha256": pilot.sha256_file(path), "bytes": path.stat().st_size}

    for name in ("tokenizer.json", "chat_template.jinja"):
        (tok / name).write_text(name)
        files[name] = pilot.sha256_file(tok / name)

    return {"gguf": entries, "merge": {"files": files}}, gguf, tok


def test_inputs_are_checked_against_the_committed_export_manifest(tmp_path):
    manifest, gguf, tok = _manifest(tmp_path)
    paths = pilot.verify_inputs(manifest, gguf, tok)
    assert sorted(paths) == sorted(VARIANTS) and paths["Q8_0"].endswith(f"{STEM}-q8_0.gguf")

    broken = copy.deepcopy(manifest)
    broken["gguf"][f"{STEM}-q4_k_m.gguf"]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="q4_k_m.gguf does not have"):
        pilot.verify_inputs(broken, gguf, tok)

    (tok / "chat_template.jinja").write_text("changed")

    with pytest.raises(ValueError, match="chat_template.jinja does not have"):
        pilot.verify_inputs(manifest, gguf, tok)


def test_committed_manifest_names_both_variants():
    manifest = json.loads((pilot.REPO_ROOT / pilot.MANIFEST).read_text(encoding="utf-8"))
    assert set(pilot.variant_files(manifest).values()) <= set(manifest["gguf"])
    assert manifest["llama_cpp"]["commit"] == "620d2225cc436ab0b001e3200e590e3b286ef9ab"


def test_platform_checks():
    pilot.check_platform("mac", "darwin", power="Now drawing from 'AC Power'\n")
    pilot.check_platform("kaggle", "linux")

    with pytest.raises(ValueError, match="mains power"):
        pilot.check_platform("mac", "darwin", power="Now drawing from 'Battery Power'\n")

    with pytest.raises(ValueError, match="--platform mac on linux"):
        pilot.check_platform("mac", "linux")

    with pytest.raises(ValueError, match="--platform kaggle on darwin"):
        pilot.check_platform("kaggle", "darwin")

    assert pilot.hold_awake("linux") is None


def test_the_bundles_commit_is_used_when_there_is_no_git_checkout(tmp_path):
    (tmp_path / "BUNDLE.json").write_text(json.dumps({"commit": "abc123"}))
    assert pilot.code_commit(tmp_path) == "abc123"


def test_a_non_empty_output_directory_stops_the_pilot(tmp_path, capsys):
    (tmp_path / "old.jsonl").write_text("{}\n")
    args = argparse.Namespace(out=tmp_path, platform="kaggle", gguf_dir=tmp_path, tokenizer=tmp_path,
                              llama_cpp=tmp_path, port=8080)
    assert pilot.run(args) == 2
    assert "is not empty" in capsys.readouterr().err


FAKE_SERVER = '''
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

port, model = int(sys.argv[sys.argv.index("--port") + 1]), sys.argv[sys.argv.index("-m") + 1]
print("main: system_info: n_threads = 2 (n_threads_batch = 2) / 8 | CPU : AVX2 = 1 | FMA = 1 |", file=sys.stderr, flush=True)
print("llama_context: n_batch       = 2048", file=sys.stderr, flush=True)

class Handler(BaseHTTPRequestHandler):
    def _reply(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._reply({"status": "ok"} if self.path == "/health" else {"model_path": model})

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self._reply({"tokens": [65], "stop_type": "eos", "completion_probabilities": [{"id": 65, "logprob": -0.1}],
                     "timings": {"prompt_n": 3, "prompt_ms": 1.0, "predicted_n": 1, "predicted_ms": 1.0}})

    def log_message(self, *args):
        pass

try:
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
except KeyboardInterrupt:
    print("shutting down", file=sys.stderr, flush=True)
'''


@pytest.mark.skipif(not Path("/usr/bin/time").exists(), reason="/usr/bin/time is not installed")
def test_server_runs_under_usr_bin_time_and_reports_peak_memory_after_sigint(tmp_path):
    import socket
    import sys as _sys

    from packages.hetren_serving.llama_server import DecodingSettings, LlamaServer, LlamaServerModel

    script = tmp_path / "fake_llama_server.py"
    script.write_text(FAKE_SERVER)

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    command = pilot.server_command(Path(script), "/models/x-q8_0.gguf", 2, port)
    command[2:3] = [_sys.executable, str(script)]  # the fake server in place of the binary
    url = f"http://127.0.0.1:{port}"
    log = tmp_path / "server.log"

    class Tokenizer:
        def apply_chat_template(self, messages, add_generation_prompt):
            return [1, 2, 3]

        def decode(self, tokens, skip_special_tokens):
            return "".join(chr(t) for t in tokens)

    with pilot.RunningServer(command, log, url, "/elsewhere/x-q8_0.gguf", ready_seconds=60) as server:
        generation = LlamaServerModel(Tokenizer(), LlamaServer(url), DecodingSettings(cache_prompt=True))("s", "u")

    text = log.read_text()
    assert server.process.returncode is not None and "shutting down" in text
    assert generation.text == "A" and generation.token_ids == (65,)
    assert pilot.peak_rss_bytes(text) > 1_000_000
    assert pilot.system_info(text)["features"] == {"AVX2": 1, "FMA": 1}
    assert pilot.server_settings(text) == ["llama_context: n_batch       = 2048"]


def test_a_server_serving_another_model_stops_the_block(tmp_path):
    import socket
    import sys as _sys

    script = tmp_path / "fake_llama_server.py"
    script.write_text(FAKE_SERVER)

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    command = [_sys.executable, str(script), "-m", "/models/other.gguf", "--port", str(port)]

    server = pilot.RunningServer(command, tmp_path / "server.log", f"http://127.0.0.1:{port}", "/m/x-q8_0.gguf",
                                 ready_seconds=60)

    with pytest.raises(RuntimeError, match="serves 'other.gguf'"):
        with server:
            pass

    assert server.process.poll() is not None and server.log.closed  # stopped, although __exit__ never ran


def test_cpu_features_are_unknown_when_either_platform_did_not_record_them():
    # Pilot 1: llama-server wrote no system_info line at its default verbosity, so both sides were empty.
    choice = pilot.decide({"mac": _report("mac", missing_features=True), "kaggle": _report("kaggle", missing_features=True)})
    assert choice["same_cpu_features"] is None and choice["platform"] == "kaggle"
    assert pilot.decide({"mac": _report("mac"), "kaggle": _report("kaggle", missing_features=True)})["same_cpu_features"] is None
