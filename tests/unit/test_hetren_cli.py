"""CPU tests of the ``hetren`` CLI (Milestone 4, step 4).

No model, transformers or llama.cpp build is needed: ``llama-server`` is a small executable Python script that
serves ``/health``, ``/props`` and ``/completion`` with a fixed reply, the tokenizer is a fake, and the export
manifest is a temporary one listing tiny files. Run records come from the scripted support agent.
"""

from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
import threading

import pytest

from packages.hetren_cli import inputs, main as cli, models, report, runtime
from packages.hetren_cli.inputs import InputRejected
from packages.hetren_evidence import compact_evidence
from packages.hetren_serving.llama_server import SERVER_SETTINGS, server_arguments


REPO_ROOT = Path(__file__).resolve().parents[2]
IM_END = 151645


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- fixtures -------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def records() -> list[dict]:
    """Evidence payloads of scripted support runs (clean and faulty cases)."""
    from packages.support_evaluator.plan import cross_plan
    from packages.support_evaluator.sampling import run_planned_case

    return [run_planned_case(planned)[2].evidence_payload() for planned in cross_plan(per_cell=1, seed=7)[:6]]


@pytest.fixture
def model_dir(tmp_path, monkeypatch) -> Path:
    """Tiny 'GGUF' and tokenizer files, and a manifest that lists them."""
    folder = tmp_path / "models"
    (folder / "tokenizer").mkdir(parents=True)
    ggufs = {"hetren-qwen3-4b-ckpt0792-q4_k_m.gguf": b"q4 weights", "hetren-qwen3-4b-ckpt0792-q8_0.gguf": b"q8 weights",
             "hetren-qwen3-4b-ckpt0792-f16.gguf": b"f16 weights"}

    for name, data in ggufs.items():
        (folder / name).write_bytes(data)

    tokenizer = {"tokenizer.json": b"{}", "vocab.json": b"{\"a\": 1}"}

    for name, data in tokenizer.items():
        (folder / "tokenizer" / name).write_bytes(data)

    manifest = {
        "gguf": {name: {"sha256": _sha(data), "bytes": len(data)} for name, data in ggufs.items()},
        "merge": {"files": {**{name: _sha(data) for name, data in tokenizer.items()},
                            "model-00001-of-00002.safetensors": "0" * 64}},
        "llama_cpp": {"commit": runtime.VALIDATED_LLAMA_CPP, "release": "v0.7.0"},
    }
    path = tmp_path / "export.manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(models, "MANIFEST", path)
    monkeypatch.setenv("HETREN_CACHE", str(folder))
    return folder


class FakeTokenizer:
    """Prompt: ``prompt_tokens`` IDs. Reply: token IDs are character codes, ended by <|im_end|>."""

    def __init__(self, prompt_tokens: int = 300):
        self.prompt_tokens = prompt_tokens

    def apply_chat_template(self, messages, add_generation_prompt=True):
        assert [m["role"] for m in messages] == ["system", "user"] and add_generation_prompt
        return list(range(self.prompt_tokens))

    def decode(self, tokens, skip_special_tokens=True):
        return "".join(chr(t) for t in tokens if t < 128000)  # IDs from 128000 stand for special tokens


FAKE_SERVER = '''#!{python}
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
args = sys.argv[1:]
if args == ["--version"]:
    print("version: 0.7.0-dev (build 11669, commit {commit})")
    print("built with AppleClang 17.0.0.17000013 for Darwin x86_64")
    sys.exit(0)
with open({args_log!r}, "w") as f:
    json.dump(args, f)
model, port = args[args.index("-m") + 1], int(args[args.index("--port") + 1])
reply = json.load(open({reply!r}))
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, body):
        data = json.dumps(body).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        self.send({{"status": "ok"}} if self.path == "/health" else {{"model_path": model}})
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert request["samplers"] == ["top_k"] and request["top_k"] == 1 and request["cache_prompt"] is True
        tokens = reply["tokens"]
        self.send({{"tokens": tokens, "stop_type": reply.get("stop_type", "eos"), "tokens_cached": 0,
                   "tokens_evaluated": len(request["prompt"]),
                   "completion_probabilities": [{{"logprob": -0.1}} for _ in tokens], "timings": {{}}}})
HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


@pytest.fixture
def fake_server(tmp_path, monkeypatch):
    """An executable fake llama-server; ``set_reply(text)`` sets what it generates."""
    reply_path, args_log = tmp_path / "reply.json", tmp_path / "server-args.json"
    binary = tmp_path / "llama-server"
    binary.write_text(FAKE_SERVER.format(python=sys.executable, commit=runtime.VALIDATED_LLAMA_CPP[:9],
                                         reply=str(reply_path), args_log=str(args_log)), encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setenv("HETREN_LLAMA_SERVER", str(binary))

    def set_reply(text: str, last: int = IM_END, stop_type: str = "eos"):
        reply_path.write_text(json.dumps({"tokens": [ord(c) for c in text] + [last], "stop_type": stop_type}),
                              encoding="utf-8")

    set_reply('{"action": "decide", "verb": "no_intervention", "args": {}}')
    return {"binary": binary, "set_reply": set_reply, "args_log": args_log}


def _diagnose(argv: list[str], tokenizer=None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    args = cli._parser().parse_args(["diagnose", *argv])
    code = cli.diagnose(args, out, err, tokenizer_loader=lambda directory: tokenizer or FakeTokenizer())
    return code, out.getvalue(), err.getvalue()


def _write(tmp_path: Path, value: object, name: str = "input.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


# --- pinned values ----------------------------------------------------------------------------------------------

def test_the_packaged_manifest_is_the_export_manifest():
    assert (REPO_ROOT / "packages/hetren_cli/data/export.manifest.json").read_bytes() == \
        (REPO_ROOT / "docs/milestone-4/export.manifest.json").read_bytes()


def test_server_arguments_are_the_pilot_and_validation_runs():
    from packages.support_evaluator import gguf_pilot

    assert SERVER_SETTINGS == gguf_pilot.SERVER
    assert server_arguments("/bin/llama-server", "m.gguf", 6, 8123) == \
        gguf_pilot.server_command(Path("/bin/llama-server"), "m.gguf", 6, 8123)[2:]


def test_end_of_generation_and_validated_build_match_the_check_and_the_manifest():
    from packages.support_evaluator import gguf_check

    assert cli.END_OF_GENERATION == set(gguf_check.END_OF_GENERATION)
    assert runtime.VALIDATED_LLAMA_CPP == models.manifest()["llama_cpp"]["commit"]
    assert models.DEFAULT_VARIANT == gguf_check.SHIPPING_ORDER[0]


def test_the_reported_validation_numbers_are_the_logged_ones():
    log = (REPO_ROOT / "docs/milestone-4/EXPORT_LOG.md").read_text(encoding="utf-8")
    logged = log.split("## Acceptance and shipping (Amendment 2)", 1)[1]

    for text in ("−0.13 points, CI [−1.50, +1.25]", "79.6%", "92.6%", "by −0.75 points", "[−0.0138, −0.0025]",
                 "30 broken cases unfixed against fp16's 15", "0 of 54 wrong interventions", "fp16's 1 of 54",
                 "**Shipping decision: Q4_K_M.**"):
        assert text in logged, text

    assert "-0.13 points pooled (95% CI -1.50 to +1.25)" in report.VALIDATION["Q4_K_M"]
    assert "79.6%" in report.VALIDATION["Q4_K_M"] and "30 broken cases" in report.VALIDATION["Q4_K_M"]
    assert "-0.75 points pooled (95% CI -1.38 to -0.25)" in report.VALIDATION["Q8_0"]
    assert "92.6%" in report.VALIDATION["Q8_0"]


def test_the_real_manifest_lists_both_accepted_variants_and_the_tokenizer():
    files = models.gguf_files()
    assert files["Q4_K_M"]["sha256"] == "e3f50ba98ee7e800554dec7ec1c403e7f1d47d4595300e6a6a3e8bf7ffe8763e"
    assert files["Q8_0"]["sha256"] == "496c74a750ef32d0c52dd9644e51b36547dda762c498ac89eece1a24bab3ba29"
    assert "tokenizer.json" in models.tokenizer_files() and "chat_template.jinja" in models.tokenizer_files()
    assert not any(name.startswith("model") for name in models.tokenizer_files())


# --- inputs ---------------------------------------------------------------------------------------------------

def test_a_run_record_becomes_its_compact_first_step_input(records):
    for record in records:
        assert inputs.from_record(record) == compact_evidence(record)


def test_a_dataset_line_and_a_compact_input_are_accepted(records):
    compact = compact_evidence(records[0])
    assert inputs.from_compact(compact) == compact
    assert inputs.from_compact({"case_id": "case-000001", "steps": [{"input": compact, "target": {}}]}) == compact


@pytest.mark.parametrize("trace", [
    {"object": "trace", "id": "trace_abc", "workflow_name": "Agent workflow"},
    [{"object": "trace.span", "id": "span_1", "span_data": {"type": "function", "name": "read_ticket"}}],
    {"trace_id": "trace_abc", "spans": [{"span_data": {"type": "agent"}}]},
])
def test_sdk_trace_exports_are_rejected_with_how_to_record_a_run(trace):
    for load in (inputs.from_record, inputs.from_compact):
        with pytest.raises(InputRejected, match="trace export") as error:
            load(trace)

        assert inputs.HOW_TO_RECORD in str(error.value)


def test_runs_with_other_tools_are_out_of_scope(records):
    foreign = json.loads(json.dumps(records[0]))
    foreign["stage_records"][0]["tool_name"] = "send_email"

    with pytest.raises(InputRejected, match="out of scope"):
        inputs.from_record(foreign)

    extra = json.loads(json.dumps(records[0]))
    extra["tool_definitions"].append({"name": "issue_refund"})

    with pytest.raises(InputRejected, match="out of scope"):
        inputs.from_record(extra)

    compact = compact_evidence(records[0])
    compact["steps"][0]["tool"] = "send_email"

    with pytest.raises(InputRejected, match="out of scope"):
        inputs.from_compact(compact)


def test_malformed_and_tier2_inputs_are_rejected(records, tmp_path):
    broken = json.loads(json.dumps(records[0]))
    del broken["stage_records"][-1]["state_after_sha256"]

    with pytest.raises(InputRejected, match="not a valid AgentRunRecord"):
        inputs.from_record(broken)

    with pytest.raises(InputRejected, match="AgentRunRecord evidence payload"):
        inputs.from_record({"record_type": "ExecutionRecord"})

    with pytest.raises(InputRejected, match="tier 2"):
        inputs.from_compact({**compact_evidence(records[0]), "format": "compact-evidence-v2", "recoveries": []})

    with pytest.raises(InputRejected, match="not a valid compact-evidence-v1"):
        inputs.from_compact({**compact_evidence(records[0]), "model_id": "gpt-4.1"})

    two_lines = tmp_path / "two.jsonl"
    two_lines.write_text(json.dumps(records[0]) + "\n" + json.dumps(records[1]) + "\n", encoding="utf-8")

    with pytest.raises(InputRejected, match="2 JSON lines"):
        inputs.load_input(record=two_lines)

    with pytest.raises(InputRejected, match="cannot read"):
        inputs.load_input(record=tmp_path / "missing.json")


# --- models ---------------------------------------------------------------------------------------------------

def test_only_the_accepted_variants_and_the_merged_tokenizer_are_used(model_dir):
    resolved = models.resolve(None, None, None)
    assert resolved["variant"] == "Q4_K_M" and resolved["gguf"].endswith("q4_k_m.gguf")
    assert models.resolve(None, None, "Q8_0")["variant"] == "Q8_0"

    with pytest.raises(models.ModelError, match="not a validated Hetren GGUF"):
        models.resolve(model_dir / "hetren-qwen3-4b-ckpt0792-f16.gguf", None, None)

    with pytest.raises(models.ModelError, match="is the Q8_0 GGUF, not Q4_K_M"):
        models.resolve(model_dir / "hetren-qwen3-4b-ckpt0792-q8_0.gguf", None, "Q4_K_M")

    (model_dir / "tokenizer/vocab.json").write_bytes(b"changed")

    with pytest.raises(models.ModelError, match="merged model's sha256"):
        models.resolve(None, None, None)

    (model_dir / "tokenizer/vocab.json").unlink()

    with pytest.raises(models.ModelError, match="tokenizer file missing"):
        models.resolve(None, None, None)


class _Files(BaseHTTPRequestHandler):
    files: dict[str, bytes] = {}
    first: dict[str, bytes] = {}  # served once, before files[path] (a corrupted first download)
    truncate: set[str] = set()  # announce the full length, then send half and close (once)
    requested: list[str] = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.requested.append(self.path)
        data = self.first.pop(self.path, None) or self.files.get(self.path)

        if data is None:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

        if self.path in self.truncate:
            self.truncate.discard(self.path)
            self.wfile.write(data[: len(data) // 2])
            self.close_connection = True
            return

        self.wfile.write(data)


@pytest.fixture
def hub(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Files)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("HF_ENDPOINT", f"http://127.0.0.1:{server.server_address[1]}")
    _Files.files, _Files.first, _Files.truncate, _Files.requested = {}, {}, set(), []
    yield _Files
    server.shutdown()


def test_fetch_model_downloads_and_checks_every_file(model_dir, hub, tmp_path):
    for path in sorted(model_dir.rglob("*")):
        if path.is_file():
            hub.files[f"/org/hetren/resolve/main/{path.relative_to(model_dir).as_posix()}"] = path.read_bytes()

    cache = tmp_path / "cache"
    result = models.fetch("org/hetren", "Q4_K_M", cache=cache, log=lambda m: None)
    assert result["gguf_sha256"] == _sha(b"q4 weights")
    assert (cache / "tokenizer/vocab.json").read_bytes() == b'{"a": 1}'
    assert not list(cache.rglob("*.partial"))

    hub.requested.clear()
    models.fetch("org/hetren", "Q4_K_M", cache=cache, log=lambda m: None)
    assert hub.requested == []  # already cached and verified

    hub.files["/org/hetren/resolve/main/hetren-qwen3-4b-ckpt0792-q8_0.gguf"] = b"tampered"

    with pytest.raises(models.ModelError, match="nothing was kept"):
        models.fetch("org/hetren", "Q8_0", cache=cache, log=lambda m: None)

    assert not (cache / "hetren-qwen3-4b-ckpt0792-q8_0.gguf").exists()
    assert not list(cache.rglob("*.partial"))


def _publish(hub, model_dir):
    for path in sorted(model_dir.rglob("*")):
        if path.is_file():
            hub.files[f"/org/hetren/resolve/main/{path.relative_to(model_dir).as_posix()}"] = path.read_bytes()


Q8 = "/org/hetren/resolve/main/hetren-qwen3-4b-ckpt0792-q8_0.gguf"


def test_a_corrupted_download_is_retried_once(model_dir, hub, tmp_path):
    _publish(hub, model_dir)
    hub.first[Q8] = b"q8 weighXs"  # the right size, the wrong bytes (the 2026-11-09 Q8_0 fetch)
    lines = []
    result = models.fetch("org/hetren", "Q8_0", cache=tmp_path / "cache", log=lines.append)

    assert result["gguf_sha256"] == _sha(b"q8 weights") and hub.requested.count(Q8) == 2
    assert any("sha256" in line and "retrying once from the start" in line for line in lines)
    assert any("(attempt 2 of 2)" in line for line in lines)


def test_a_truncated_download_is_retried_and_a_wrong_size_never_kept(model_dir, hub, tmp_path):
    _publish(hub, model_dir)
    hub.truncate.add(Q8)
    lines = []
    models.fetch("org/hetren", "Q8_0", cache=tmp_path / "cache", log=lines.append)
    assert hub.requested.count(Q8) == 2 and any("retrying once" in line for line in lines)

    hub.files[Q8] = b"q8 weights, but longer"  # a different file: wrong size on both attempts
    with pytest.raises(models.ModelError, match=r"bytes, not the manifest's 10 \(after 2 attempts\); nothing was kept"):
        models.fetch("org/hetren", "Q8_0", cache=tmp_path / "other", log=lambda m: None)
    assert not list((tmp_path / "other").rglob("*.gguf*"))


def test_a_missing_file_is_not_retried(model_dir, hub, tmp_path):
    _publish(hub, model_dir)
    del hub.files[Q8]

    with pytest.raises(models.ModelError, match="HTTP 404"):
        models.fetch("org/hetren", "Q8_0", cache=tmp_path / "cache", log=lambda m: None)

    assert hub.requested.count(Q8) == 1


def test_tls_uses_certifi_only_when_python_has_no_certificates(monkeypatch, tmp_path):
    import ssl
    import certifi

    seen = []
    monkeypatch.setattr(ssl, "create_default_context", lambda cafile=None: seen.append(cafile) or "context")
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    paths = type("Paths", (), {})
    none = paths()
    none.cafile, none.capath = str(tmp_path / "missing.pem"), str(tmp_path / "missing-dir")
    monkeypatch.setattr(ssl, "get_default_verify_paths", lambda: none)
    models.tls_context()

    system = paths()
    (tmp_path / "cert.pem").write_text("x")
    system.cafile, system.capath = str(tmp_path / "cert.pem"), None
    monkeypatch.setattr(ssl, "get_default_verify_paths", lambda: system)
    models.tls_context()

    monkeypatch.setattr(ssl, "get_default_verify_paths", lambda: none)
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "corporate.pem"))
    models.tls_context()

    assert seen == [certifi.where(), None, None]


def test_fetch_model_needs_a_repository(monkeypatch):
    monkeypatch.delenv("HETREN_MODEL_REPO", raising=False)
    err = io.StringIO()
    assert cli.fetch_model(cli._parser().parse_args(["fetch-model"]), io.StringIO(), err) == cli.EXIT_INPUT
    assert "--repo" in err.getvalue()


# --- diagnose end to end with the fake server ------------------------------------------------------------------

def test_a_decision_is_reported_with_scope_validation_and_provenance(records, model_dir, fake_server, tmp_path):
    code, out, err = _diagnose(["--record", str(_write(tmp_path, records[0])), "--threads", "3"])

    assert code == cli.EXIT_OK, err
    assert out.startswith("Hetren diagnosis (proposed only; nothing was applied)")
    assert "Decision: no_intervention" in out and "The run needs no change." in out
    assert report.SCOPE in out and report.VALIDATION["Q4_K_M"] in out
    assert f"llama.cpp {runtime.VALIDATED_LLAMA_CPP[:9]} (the validated build), 3 threads" in out
    args = json.loads(fake_server["args_log"].read_text(encoding="utf-8"))
    assert args[:2] == ["-m", str(model_dir / "hetren-qwen3-4b-ckpt0792-q4_k_m.gguf")]
    assert args == server_arguments("x", args[1], 3, int(args[-1]))[1:]


def test_a_recovery_is_only_proposed_and_json_carries_provenance(records, model_dir, fake_server, tmp_path):
    fake_server["set_reply"]('```json\n{"action": "recover", "verb": "reroute", '
                             '"args": {"ticket_id": "T-1003", "queue_id": "Q-BILLING"}}\n```')
    code, out, err = _diagnose(["--record", str(_write(tmp_path, records[1])), "--format", "json"])

    assert code == cli.EXIT_OK, err
    result = json.loads(out)
    assert result["result"]["outcome"] == "proposed_recovery"
    assert result["result"]["action"] == {"action": "recover", "verb": "reroute",
                                          "args": {"ticket_id": "T-1003", "queue_id": "Q-BILLING"}}
    assert any("Not applied" in note for note in result["result"]["notes"])
    assert result["model"]["variant"] == "Q4_K_M" and result["model"]["gguf_sha256"] == _sha(b"q4 weights")
    assert result["prompt_version"] == 2 and result["cli_version"] == cli.CLI_VERSION
    assert result["server"]["validated_build"] is True and result["stopped_on_other_token"] is False
    assert result["scope"] == report.SCOPE and result["generation"]["prompt_tokens"] == 300
    assert result["input"] == {"format": "compact-evidence-v1", "task": records[1]["task_input"],
                               "status": records[1]["status"], "tool_calls": len(compact_evidence(records[1])["steps"]),
                               "probes": 0}


def test_a_probe_request_is_reported_as_needing_the_environment(records, model_dir, fake_server, tmp_path):
    fake_server["set_reply"]('{"action": "probe", "verb": "resolve", "args": {"customer_ref": "C-3103"}}')
    code, out, _ = _diagnose(["--compact", str(_write(tmp_path, compact_evidence(records[0])))])

    assert code == cli.EXIT_OK
    assert 'Needs probe: resolve {"customer_ref": "C-3103"}' in out
    assert "no decision or recovery was made" in out


def test_an_invalid_reply_and_an_unexpected_stop_are_reported(records, model_dir, fake_server, tmp_path):
    fake_server["set_reply"]("I think the ticket is fine.", last=128247)
    code, out, _ = _diagnose(["--record", str(_write(tmp_path, records[0]))])

    assert code == cli.EXIT_REPLY
    assert "not a valid action" in out and "'I think the ticket is fine.'" in out
    assert "ended on a token other than <|im_end|>" in out


def test_the_q8_0_variant_reports_its_own_validation(records, model_dir, fake_server, tmp_path):
    code, out, _ = _diagnose(["--record", str(_write(tmp_path, records[0])), "--variant", "Q8_0"])
    assert code == cli.EXIT_OK and report.VALIDATION["Q8_0"] in out


def test_rejections_and_failures_have_their_exit_codes(records, model_dir, fake_server, tmp_path):
    record = str(_write(tmp_path, records[0]))
    trace = str(_write(tmp_path, {"object": "trace", "id": "trace_1"}, "trace.json"))

    code, _, err = _diagnose(["--record", trace])
    assert code == cli.EXIT_INPUT and "trace export" in err

    code, _, err = _diagnose(["--record", record], tokenizer=FakeTokenizer(prompt_tokens=4000))
    assert code == cli.EXIT_INPUT and "4096-token context" in err

    code, _, err = _diagnose(["--record", record, "--model", str(model_dir / "hetren-qwen3-4b-ckpt0792-f16.gguf")])
    assert code == cli.EXIT_RUNTIME and "not a validated Hetren GGUF" in err

    code, _, err = _diagnose(["--record", record, "--llama-server", str(tmp_path / "no-such-binary")])
    assert code == cli.EXIT_RUNTIME and "llama-server not found" in err


def test_an_external_server_must_serve_the_chosen_variant(records, model_dir, fake_server, tmp_path):
    import subprocess
    import time

    port = runtime.free_port()
    process = subprocess.Popen([str(fake_server["binary"]), "-m", "/models/hetren-qwen3-4b-ckpt0792-q8_0.gguf",
                                "--port", str(port)])

    try:
        for _ in range(100):
            try:
                runtime.LlamaServer(f"http://127.0.0.1:{port}", timeout=1).request("/health")
                break
            except OSError:
                time.sleep(0.1)

        record = str(_write(tmp_path, records[0]))
        code, _, err = _diagnose(["--record", record, "--server-url", f"http://127.0.0.1:{port}"])
        assert code == cli.EXIT_RUNTIME and "not hetren-qwen3-4b-ckpt0792-q4_k_m.gguf" in err

        code, out, err = _diagnose(["--record", record, "--server-url", f"http://127.0.0.1:{port}",
                                    "--variant", "Q8_0", "--format", "json"])
        assert code == cli.EXIT_OK, err
        assert json.loads(out)["model"]["gguf_sha256"] is None
        assert json.loads(out)["server"]["validated_build"] is False
    finally:
        process.terminate()
        process.wait()


# --- runtime, help and version ---------------------------------------------------------------------------------

def test_build_info_recognises_the_validated_build():
    class Result:
        def __init__(self, text):
            self.stdout, self.stderr = text, ""

    validated = runtime.build_info("x", run=lambda *a, **k: Result("version: 0.7.0-dev (build 11669, commit 620d2225c)"))
    other = runtime.build_info("x", run=lambda *a, **k: Result("version: 0.8.0 (build 12000, commit 1234abcd)"))
    assert validated["validated_build"] is True and validated["commit"] == "620d2225c"
    assert other["validated_build"] is False


def test_help_states_the_scope_and_version_lists_the_files(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])

    help_text = capsys.readouterr().out
    assert "trained only on Hetren's synthetic support workflow" in help_text
    assert "not a general agent-trace diagnoser" in help_text
    assert "nothing is ever applied" in help_text
    assert "single-recovery (tier 1)" in " ".join(help_text.split())
    assert "two-step recovery is not supported" in " ".join(help_text.split())
    assert "single-recovery (tier 1) support runs only" in report.SCOPE
    assert "two-step recovery is not supported here, although the model was validated on it" in report.SCOPE

    assert cli.main(["version"]) == 0
    out = capsys.readouterr().out
    assert "e3f50ba98ee7e800554dec7ec1c403e7f1d47d4595300e6a6a3e8bf7ffe8763e" in out and "620d2225" in out


def test_cli_requirements_are_the_validation_runs_versions_without_torch_or_agents():
    def pins(name: str) -> dict[str, str]:
        lines = (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
        return dict(line.lower().split("==") for line in lines if line and not line.startswith("#"))

    cli_pins, pilot_pins = pins("requirements-cli.txt"), pins("requirements-gguf-pilot.txt")
    assert {name: cli_pins[name] for name in cli_pins if name in pilot_pins} == \
        {name: pilot_pins[name] for name in cli_pins if name in pilot_pins}
    assert {"transformers", "tokenizers", "jsonschema", "jinja2"} <= set(cli_pins)
    assert not {"torch", "openai-agents", "openai", "tiktoken"} & set(cli_pins)


def test_the_cpu_flag_check_names_what_is_missing(records, model_dir, fake_server, tmp_path, monkeypatch):
    cpuinfo = "processor\t: 0\nflags\t\t: fpu sse2 avx avx2 fma f16c bmi2\n"
    assert runtime.missing_cpu_flags("avx2 fma f16c", cpuinfo) == []
    assert runtime.missing_cpu_flags("avx2 fma f16c avx512f", cpuinfo) == ["avx512f"]
    assert runtime.missing_cpu_flags("", cpuinfo) == []  # not in the image: no requirement
    assert runtime.missing_cpu_flags("avx2", "no flags line here") == []  # not Linux

    with pytest.raises(runtime.RuntimeFailure, match="lacks avx2"):
        runtime.check_cpu("avx2 fma", "flags : sse2 fma\n")

    monkeypatch.setattr(runtime, "missing_cpu_flags", lambda *a, **k: ["avx2"])
    code, _, err = _diagnose(["--record", str(_write(tmp_path, records[0]))])
    assert code == cli.EXIT_RUNTIME and "this CPU lacks avx2" in err
