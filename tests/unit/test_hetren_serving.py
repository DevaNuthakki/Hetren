"""CPU tests of the GGUF export tooling, the llama-server policy and the token-parity checks (Amendment 2).

No model, GPU, torch, gguf package or llama.cpp build is needed: hashes are
checked on temporary files, llama.cpp is a temporary git repository, the
server is a local stdlib HTTP server or a fake, and the tokenizer is a fake.
"""

from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import subprocess
import threading

import pytest

from packages.hetren_serving import export, llama_server, parity
from packages.hetren_serving.llama_server import DecodingSettings, LlamaServer, LlamaServerModel


REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- export: the pinned values agree with the protocol and the logs -------------------------------------------

def test_pinned_values_are_the_ones_amendment_2_and_the_validation_log_record():
    protocol = (REPO_ROOT / "docs/milestone-2/EVAL_PROTOCOL.md").read_text(encoding="utf-8")
    amendment = protocol.split("### Amendment 2 ", 1)[1].split("\n## ", 1)[0]
    validation_log = (REPO_ROOT / "docs/milestone-3/VALIDATION_LOG.md").read_text(encoding="utf-8")

    for value in (export.CHOSEN["state_sha256"], export.CHOSEN["adapter_sha256"], export.LLAMA_CPP_COMMIT,
                  f"`{export.LLAMA_CPP_RELEASE}`", "**Q8_0**", "**Q4_K_M**"):
        assert value in amendment
    assert export.VARIANTS == ("Q8_0", "Q4_K_M")
    assert f"`choice.json` `{export.CHOICE_SHA256}`" in validation_log
    assert f"**Chosen: `{export.CHOSEN['checkpoint']}`** (step {export.CHOSEN['step']};" in validation_log


@pytest.mark.skipif(not (REPO_ROOT / "artifacts/milestone-3/selection-run-1/qlora-selection/choice.json").exists(),
                    reason="selection outputs are gitignored")
def test_the_logged_choice_file_passes_verification():
    choice = export.verify_choice(REPO_ROOT / "artifacts/milestone-3/selection-run-1/qlora-selection/choice.json")
    assert choice["chosen"] == "checkpoint-0792"


# --- export: verification of inputs -------------------------------------------------------------------------

def _checkpoint(tmp_path: Path, step: int = 792) -> tuple[Path, dict]:
    checkpoint = tmp_path / "checkpoint"
    (checkpoint / "adapter").mkdir(parents=True)
    (checkpoint / "adapter/adapter_config.json").write_text('{"r": 16}', encoding="utf-8")
    (checkpoint / "adapter/adapter_model.safetensors").write_bytes(b"weights")
    files = {name: _sha(checkpoint / name) for name in export.ADAPTER_FILES}
    (checkpoint / "state.json").write_text(json.dumps({"step": step, "candidate": True, "files": files}), encoding="utf-8")
    chosen = {"checkpoint": f"checkpoint-{step:04d}", "step": step, "state_sha256": _sha(checkpoint / "state.json"),
              "adapter_sha256": files["adapter/adapter_model.safetensors"]}
    return checkpoint, chosen


def test_checkpoint_verification_accepts_the_chosen_files_and_rejects_any_change(tmp_path):
    checkpoint, chosen = _checkpoint(tmp_path)
    assert export.verify_checkpoint(checkpoint, chosen)["adapter/adapter_model.safetensors"] == chosen["adapter_sha256"]

    with pytest.raises(ValueError, match="not the chosen checkpoint's state.json"):
        export.verify_checkpoint(checkpoint, {**chosen, "state_sha256": "0" * 64})

    (checkpoint / "adapter/adapter_model.safetensors").write_bytes(b"other weights")
    with pytest.raises(ValueError, match="does not match its sha256 in state.json"):
        export.verify_checkpoint(checkpoint, chosen)


def test_checkpoint_verification_rejects_another_step(tmp_path):
    checkpoint, chosen = _checkpoint(tmp_path, step=264)
    with pytest.raises(ValueError, match="chosen step and adapter"):
        export.verify_checkpoint(checkpoint, {**chosen, "step": 792})


def test_choice_verification_checks_the_logged_hash_and_the_chosen_checkpoint(tmp_path):
    _, chosen = _checkpoint(tmp_path)
    path = tmp_path / "choice.json"
    path.write_text(json.dumps({"chosen": chosen["checkpoint"], "step": 792, "S": 0.7322,
                                "state_sha256": chosen["state_sha256"], "adapter_sha256": chosen["adapter_sha256"]}),
                    encoding="utf-8")
    assert export.verify_choice(path, _sha(path), chosen)["S"] == 0.7322

    with pytest.raises(ValueError, match="logged sha256"):
        export.verify_choice(path, "0" * 64, chosen)
    with pytest.raises(ValueError, match="does not name the chosen checkpoint"):
        export.verify_choice(path, _sha(path), {**chosen, "step": 1055})


def test_merged_directory_must_still_match_its_record(tmp_path, monkeypatch):
    merged = tmp_path / "merged"
    merged.mkdir()
    (merged / "model.safetensors").write_bytes(b"merged weights")
    (merged / "tokenizer.json").write_text("{}", encoding="utf-8")
    record = {"checkpoint": dict(export.CHOSEN), "files": export.tree_hashes(merged)}
    (merged / export.MERGE_RECORD).write_text(json.dumps(record), encoding="utf-8")
    assert export.verify_merged(merged)["files"] == record["files"]
    assert export.MERGE_RECORD not in record["files"]

    (merged / "model.safetensors").write_bytes(b"changed")
    with pytest.raises(ValueError, match="differ from merge.json"):
        export.verify_merged(merged)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _llama_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "llama.cpp"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "convert_hf_to_gguf.py").write_text("# converter\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "pinned")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_llama_cpp_checkout_must_be_the_pinned_commit_without_changes(tmp_path):
    repo, head = _llama_repo(tmp_path)
    export.verify_llama_cpp(repo, head)

    with pytest.raises(ValueError, match="not the pinned llama.cpp commit"):
        export.verify_llama_cpp(repo, export.LLAMA_CPP_COMMIT)

    (repo / "convert_hf_to_gguf.py").write_text("# patched\n", encoding="utf-8")
    with pytest.raises(ValueError, match="local changes"):
        export.verify_llama_cpp(repo, head)


def test_commands_convert_to_f16_then_quantise_each_variant_without_an_importance_matrix(tmp_path):
    steps = export.commands(tmp_path / "merged", tmp_path / "llama.cpp", tmp_path / "out")
    assert [target.name for target, _ in steps] == [
        "hetren-qwen3-4b-ckpt0792-f16.gguf", "hetren-qwen3-4b-ckpt0792-q8_0.gguf", "hetren-qwen3-4b-ckpt0792-q4_k_m.gguf"]
    assert steps[0][1][1:] == [str(tmp_path / "llama.cpp/convert_hf_to_gguf.py"), str(tmp_path / "merged"),
                               "--outtype", "f16", "--outfile", str(steps[0][0])]
    assert [command[3] for _, command in steps[1:]] == ["Q8_0", "Q4_K_M"]
    assert all(command[1] == str(steps[0][0]) for _, command in steps[1:])
    assert not any("imatrix" in part for _, command in steps for part in command)


def test_convert_runs_each_step_and_records_every_output_hash(tmp_path, monkeypatch):
    merged = tmp_path / "merged"
    merged.mkdir()
    (merged / "model.safetensors").write_bytes(b"merged weights")
    (merged / export.MERGE_RECORD).write_text(
        json.dumps({"checkpoint": dict(export.CHOSEN), "files": export.tree_hashes(merged)}), encoding="utf-8")
    monkeypatch.setattr(export, "verify_llama_cpp", lambda checkout: None)
    ran = []

    def fake_run(command, check):
        ran.append(command)
        target = Path(command[-1] if len(ran) == 1 else command[2])
        target.write_bytes(f"gguf {len(ran)}".encode())

    manifest = tmp_path / "export.manifest.json"
    record = export.convert(merged, tmp_path / "llama.cpp", tmp_path / "out", manifest, run=fake_run)
    assert len(ran) == 3 and json.loads(manifest.read_text(encoding="utf-8")) == record
    assert {name: entry["bytes"] for name, entry in record["gguf"].items()} == {
        "hetren-qwen3-4b-ckpt0792-f16.gguf": 6, "hetren-qwen3-4b-ckpt0792-q8_0.gguf": 6,
        "hetren-qwen3-4b-ckpt0792-q4_k_m.gguf": 6}
    assert record["llama_cpp"] == {"release": "v0.7.0", "commit": "620d2225cc436ab0b001e3200e590e3b286ef9ab"}
    assert record["importance_matrix"] is None
    assert str(tmp_path) not in json.dumps(record["commands"])


def test_merge_stops_before_loading_any_model_when_the_choice_is_wrong(tmp_path):
    choice = tmp_path / "choice.json"
    choice.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="logged sha256"):
        export.merge(tmp_path / "checkpoint", choice, tmp_path / "out")
    assert not (tmp_path / "out").exists()


# --- llama-server policy ------------------------------------------------------------------------------------

def test_decoding_payload_is_amendment_2s_greedy_settings():
    assert DecodingSettings(cache_prompt=False).payload([1, 2, 3]) == {
        "prompt": [1, 2, 3], "n_predict": 128, "samplers": ["top_k"], "top_k": 1, "temperature": 0.0,
        "repeat_penalty": 1.0, "presence_penalty": 0.0, "frequency_penalty": 0.0, "dry_multiplier": 0.0,
        "ignore_eos": False, "cache_prompt": False, "n_probs": 1, "return_tokens": True, "stream": False, "id_slot": 0,
    }
    assert DecodingSettings(cache_prompt=True).payload([7])["cache_prompt"] is True


class FakeTokenizer:
    def apply_chat_template(self, messages, add_generation_prompt):
        assert add_generation_prompt and [m["role"] for m in messages] == ["system", "user"]
        return [100, 101, len(messages[1]["content"])]

    def decode(self, tokens, skip_special_tokens):
        assert skip_special_tokens
        return "".join(chr(t) for t in tokens)


class FakeServer:
    def __init__(self, response):
        self.response = response
        self.bodies = []

    def completion(self, body):
        self.bodies.append(body)
        return self.response


def _response(tokens, stop_type="eos", logprobs=None):
    logprobs = [-0.01] * len(tokens) if logprobs is None else logprobs
    return {"tokens": tokens, "stop_type": stop_type, "tokens_cached": 90, "tokens_evaluated": 103,
            "completion_probabilities": [{"id": t, "logprob": p} for t, p in zip(tokens, logprobs)],
            "timings": {"prompt_n": 13, "prompt_ms": 650.5, "predicted_n": len(tokens), "predicted_ms": 120.25}}


def test_model_sends_the_chat_template_ids_and_decodes_the_returned_tokens():
    server = FakeServer(_response([ord(c) for c in '{"a"}']))
    generation = LlamaServerModel(FakeTokenizer(), server, DecodingSettings(cache_prompt=True))("system", "user text")
    assert server.bodies[0]["prompt"] == [100, 101, 9]
    assert (generation.text, generation.prompt_tokens, generation.new_tokens) == ('{"a"}', 3, 5)
    assert generation.finite and not generation.at_limit and generation.stop_type == "eos"
    assert (generation.probabilities, generation.tokens_cached, generation.tokens_evaluated) == (5, 90, 103)
    assert generation.token_ids == tuple(ord(c) for c in '{"a"}')
    assert (generation.prompt_n, generation.prompt_ms, generation.predicted_n, generation.predicted_ms) == (13, 650.5, 5, 120.25)
    assert {"text", "prompt_tokens", "new_tokens", "finite", "at_limit", "stop_type"} <= set(generation.payload())


@pytest.mark.parametrize("logprob", [None, math.nan, math.inf, "x", True])
def test_a_missing_or_non_finite_log_probability_is_not_finite(logprob):
    server = FakeServer(_response([65, 66], logprobs=[-0.1, logprob]))
    assert not LlamaServerModel(FakeTokenizer(), server, DecodingSettings(cache_prompt=False))("s", "u").finite


def test_the_token_limit_is_reported_and_unexpected_responses_stop():
    model = LlamaServerModel(FakeTokenizer(), FakeServer(_response([65] * 128, stop_type="limit")),
                             DecodingSettings(cache_prompt=False))
    assert model("s", "u").at_limit

    for response, message in (({"stop_type": "word", "tokens": []}, "unexpected llama-server response"),
                              ({"stop_type": "eos"}, "unexpected llama-server response"),
                              ({"stop_type": "eos", "tokens": [65]}, "no token probabilities")):
        with pytest.raises(ValueError, match=message):
            LlamaServerModel(FakeTokenizer(), FakeServer(response), DecodingSettings(cache_prompt=False))("s", "u")


def test_http_client_posts_json_and_reads_props():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, payload):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            seen.append(("GET", self.path, None))
            self._reply({"model_path": "/models/x.gguf", "build_info": "b1-620d222"})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(("POST", self.path, body))
            self._reply({"tokens": [1, 2]} if self.path == "/tokenize" else {"content": "ab"})

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    try:
        client = LlamaServer(f"http://127.0.0.1:{httpd.server_address[1]}/", timeout=10)
        assert client.tokenize("ab") == [1, 2]
        assert client.detokenize([1, 2]) == "ab"
        assert client.props()["model_path"] == "/models/x.gguf"
    finally:
        httpd.shutdown()

    assert seen == [("POST", "/tokenize", {"content": "ab", "add_special": False, "parse_special": True}),
                    ("POST", "/detokenize", {"tokens": [1, 2]}), ("GET", "/props", None)]


# --- vocabulary and round-trip parity -----------------------------------------------------------------------

def _hf():
    return parity.Vocabulary(tokens=["a", "b", "ab", "<|endoftext|>", "<|im_end|>", "<think>"], merges=["a b"],
                             special=frozenset({3, 4}), added=frozenset({3, 4, 5}), eos=(4, 3))


def _gguf(**changes):
    values = dict(tokens=["a", "b", "ab", "<|endoftext|>", "<|im_end|>", "<think>", "[PAD6]"], merges=["a b"],
                  types=[1, 1, 1, 3, 3, 4, 5], eos=(4,), add_bos=False, pre="qwen2")
    values.update(changes)
    return parity.Vocabulary(**values)


def test_identical_vocabularies_have_parity():
    assert parity.check_vocabulary(_hf(), _gguf()) == []
    assert parity.check_vocabulary(_hf(), _gguf(types=[1, 1, 1, 3, 3, 3, 5])) == []  # added non-special: control allowed


@pytest.mark.parametrize("changes, expected", [
    ({"tokens": ["a", "c", "ab", "<|endoftext|>", "<|im_end|>", "<think>", "[PAD6]"]}, "token: 1: 'b' != 'c'"),
    ({"merges": ["b a"]}, "merges: 1 Hugging Face, 1 GGUF, first difference at 0"),
    ({"types": [1, 1, 1, 3, 4, 4, 5]}, "type: 4 '<|im_end|>': GGUF type 4, expected 3"),
    ({"types": [1, 1, 1, 3, 3, 4, 3]}, "padding: 6 '[PAD6]': GGUF type 3, expected unused"),
    ({"eos": (2,)}, "eos: GGUF end-of-sequence (2,) is not among the model's (4, 3)"),
    ({"add_bos": True}, "bos: the GGUF adds a BOS token"),
    ({"pre": "llama-bpe"}, "pre-tokenizer: 'llama-bpe', expected 'qwen2'"),
    ({"tokens": ["a"], "types": [1]}, "sizes: 6 Hugging Face tokens, 1 GGUF tokens, 1 GGUF token types"),
])
def test_each_vocabulary_difference_is_reported(changes, expected):
    problems = parity.check_vocabulary(_hf(), _gguf(**changes))
    assert any(p.startswith(expected) for p in problems), problems


def test_end_of_generation_tokens_must_be_control_tokens():
    problems = parity.check_vocabulary(_hf(), _gguf(types=[1, 1, 1, 1, 3, 4, 5]))
    assert "end of generation: 3: GGUF type 1, expected control" in problems


@pytest.mark.parametrize("merges", [["a b"], [["a", "b"]]])
def test_hugging_face_vocabulary_is_read_from_the_tokenizer_files(tmp_path, merges):
    (tmp_path / "tokenizer.json").write_text(json.dumps({
        "model": {"vocab": {"a": 0, "b": 1, "ab": 2}, "merges": merges},
        "added_tokens": [{"id": 3, "content": "<|endoftext|>", "special": True},
                         {"id": 4, "content": "<|im_end|>", "special": True},
                         {"id": 5, "content": "<think>", "special": False}],
    }), encoding="utf-8")
    (tmp_path / "generation_config.json").write_text(json.dumps({"eos_token_id": [4, 3]}), encoding="utf-8")
    assert parity.load_hf_vocabulary(tmp_path) == _hf()


def test_non_contiguous_hugging_face_ids_stop(tmp_path):
    (tmp_path / "tokenizer.json").write_text(json.dumps({"model": {"vocab": {"a": 0, "b": 2}, "merges": []}}),
                                             encoding="utf-8")
    (tmp_path / "generation_config.json").write_text('{"eos_token_id": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="not contiguous"):
        parity.load_hf_vocabulary(tmp_path)


class RoundTripServer:
    def __init__(self, tokenize=None, detokenize=None):
        self._tokenize = tokenize or {}
        self._detokenize = detokenize or {}

    def tokenize(self, text):
        return self._tokenize.get(text, [ord(c) for c in text])

    def detokenize(self, ids):
        return self._detokenize.get(tuple(ids), "".join(chr(i) for i in ids))


def test_round_trip_reports_tokenisation_and_detokenisation_differences():
    items = [("one", "ab", [97, 98]), ("two", "cd", [99, 100]), ("three", "ef", [101, 102])]
    server = RoundTripServer(tokenize={"cd": [99]}, detokenize={(101, 102): "eF"})
    assert parity.roundtrip_problems(items, server) == (3, ["two: tokenisation differs", "three: detokenisation differs"])
    assert parity.roundtrip_problems(items[:1], server) == (1, [])
