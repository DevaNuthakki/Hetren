"""The Hugging Face staging and verification script (step 7a), and the model card's numbers. Nothing is
downloaded or uploaded: the files are tiny stand-ins and the API is a fake."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from scripts import hf_release as release


REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def sources(tmp_path):
    """A tiny export (2 GGUFs, the f16 left out, 2 tokenizer files) and adapter, with a manifest listing them."""
    gguf, adapter = tmp_path / "gguf-export", tmp_path / "adapter"
    (gguf / "tokenizer").mkdir(parents=True)
    adapter.mkdir()
    data = {"hetren-qwen3-4b-ckpt0792-q4_k_m.gguf": b"q4", "hetren-qwen3-4b-ckpt0792-q8_0.gguf": b"q8",
            "tokenizer/tokenizer.json": b"{}", "tokenizer/vocab.json": b"{\"a\": 1}"}
    for path, content in data.items():
        (gguf / path).write_bytes(content)
    (adapter / "adapter_model.safetensors").write_bytes(b"lora")
    (adapter / "adapter_config.json").write_bytes(b"{\"r\": 16}")
    (adapter / "README.md").write_bytes(b"PEFT template")
    manifest = {
        "gguf": {"hetren-qwen3-4b-ckpt0792-q4_k_m.gguf": {"sha256": _sha(b"q4")},
                 "hetren-qwen3-4b-ckpt0792-q8_0.gguf": {"sha256": _sha(b"q8")},
                 "hetren-qwen3-4b-ckpt0792-f16.gguf": {"sha256": "0" * 64}},
        "merge": {"files": {"tokenizer.json": _sha(b"{}"), "vocab.json": _sha(b"{\"a\": 1}"),
                            "model-00001-of-00002.safetensors": "1" * 64},
                  "checkpoint": {"files": {"adapter/adapter_model.safetensors": _sha(b"lora"),
                                           "adapter/adapter_config.json": _sha(b"{\"r\": 16}")}}},
    }
    manifest_path = tmp_path / "export.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    card = tmp_path / "card.md"
    card.write_text("# card\nfetch-model --repo <this repository>\n", encoding="utf-8")
    licence = tmp_path / "LICENSE"
    licence.write_text("Apache License\n", encoding="utf-8")
    return {"manifest_path": manifest_path, "card": card, "license_path": licence, "gguf_dir": gguf,
            "adapter_dir": adapter}


def test_staging_checks_every_hash_and_lays_out_what_fetch_model_reads(sources, tmp_path):
    out = tmp_path / "staged"
    staged = release.stage_model("someone/hetren-test", out, log=lambda m: None, **sources)

    assert sorted(staged) == ["LICENSE", "README.md", "adapter/adapter_config.json", "adapter/adapter_model.safetensors",
                              "export.manifest.json", "hetren-qwen3-4b-ckpt0792-q4_k_m.gguf",
                              "hetren-qwen3-4b-ckpt0792-q8_0.gguf", "tokenizer/tokenizer.json", "tokenizer/vocab.json"]
    assert "--repo someone/hetren-test" in (out / "README.md").read_text(encoding="utf-8")
    assert not (out / "adapter/README.md").exists() and not list(out.glob("*f16*"))
    sums = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert f"{_sha(b'q4')}  hetren-qwen3-4b-ckpt0792-q4_k_m.gguf" in sums and len(sums) == 9


def test_a_wrong_or_missing_file_stages_nothing(sources, tmp_path):
    (sources["gguf_dir"] / "hetren-qwen3-4b-ckpt0792-q8_0.gguf").write_bytes(b"tampered")
    (sources["adapter_dir"] / "adapter_config.json").unlink()
    out = tmp_path / "staged"

    with pytest.raises(release.ReleaseError) as caught:
        release.stage_model("someone/hetren-test", out, log=lambda m: None, **sources)

    assert "q8_0.gguf: sha256 differs" in str(caught.value) and "adapter/adapter_config.json: missing" in str(caught.value)
    assert not out.exists()


def test_staging_refuses_a_non_empty_folder_and_a_bad_repo_name(sources, tmp_path):
    out = tmp_path / "staged"
    out.mkdir()
    (out / "old").write_text("x")

    with pytest.raises(release.ReleaseError, match="not empty"):
        release.stage_model("someone/hetren-test", out, log=lambda m: None, **sources)

    with pytest.raises(release.ReleaseError, match="<user or organization>/<name>"):
        release.stage_model("hetren-test", tmp_path / "other", log=lambda m: None, **sources)


def _remote(out: Path, lfs: set[str]) -> list[dict]:
    entries = [{"type": "file", "path": ".gitattributes", "oid": "x", "size": 1}]
    for path in sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()):
        size = (out / path).stat().st_size
        entry = {"type": "file", "path": path, "size": size, "oid": release.git_blob_id(out / path)}
        if path in lfs:
            entry["lfs"] = {"oid": release.sha256_file(out / path), "size": size}
        entries.append(entry)
    return entries + [{"type": "directory", "path": "tokenizer"}]


def test_verify_remote_accepts_exactly_the_staged_files(sources, tmp_path):
    out = tmp_path / "staged"
    release.stage_model("someone/hetren-test", out, log=lambda m: None, **sources)
    lfs = {"hetren-qwen3-4b-ckpt0792-q4_k_m.gguf", "hetren-qwen3-4b-ckpt0792-q8_0.gguf",
           "adapter/adapter_model.safetensors"}
    seen = []
    problems = release.verify_remote("someone/hetren-test", out, "abc123", manifest_path=sources["manifest_path"],
                                     fetch=lambda url: seen.append(url) or _remote(out, lfs), log=lambda m: None)
    assert problems == []
    assert seen == ["https://huggingface.co/api/models/someone/hetren-test/tree/abc123?recursive=true"]


def test_verify_remote_reports_wrong_missing_and_extra_files(sources, tmp_path):
    out = tmp_path / "staged"
    release.stage_model("someone/hetren-test", out, log=lambda m: None, **sources)
    entries = _remote(out, {"hetren-qwen3-4b-ckpt0792-q4_k_m.gguf"})
    for entry in entries:
        if entry["path"] == "hetren-qwen3-4b-ckpt0792-q4_k_m.gguf":
            entry["lfs"]["oid"] = "f" * 64
        if entry["path"] == "README.md":
            entry["oid"] = "0" * 40
    entries = [e for e in entries if e["path"] != "LICENSE"] + [{"type": "file", "path": "notes.txt", "oid": "1", "size": 1}]
    problems = release.verify_remote("someone/hetren-test", out, manifest_path=sources["manifest_path"],
                                     fetch=lambda url: entries, log=lambda m: None)
    assert any("q4_k_m.gguf: LFS sha256" in p for p in problems)
    assert any(p.startswith("README.md: git blob") for p in problems)
    assert "LICENSE: not in the repository" in problems and "notes.txt: in the repository but not staged" in problems


def test_the_real_release_is_both_ggufs_the_tokenizer_and_the_adapter():
    files = release.expected_files(json.loads(release.MANIFEST.read_text(encoding="utf-8")))
    assert len(files) == 13 and sum(p.startswith("tokenizer/") for p in files) == 9
    assert files["adapter/adapter_model.safetensors"] == "5647f93f25c9f79c8e7fca0468d8aa7476afbcc348f3b42f420d1845098f4226"
    assert not any("f16" in p for p in files)


# --- Step 7b: the dataset repository ------------------------------------------------------------------------------

def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha(data)


def _folder(directory: Path) -> str:
    lines = sorted(f"{p.relative_to(directory).as_posix()} {_sha(p.read_bytes())}\n" for p in directory.rglob("*") if p.is_file())
    return _sha("".join(lines).encode())


@pytest.fixture
def dataset_sources(tmp_path):
    """A tiny copy of the repository's manifests and docs, and of artifacts/milestone-2, consistent with each other."""
    root, data = tmp_path / "repo", tmp_path / "data"
    for name in ("dataset-v2", "dataset-v3"):
        files = {path: _write(data / name / path, f"{name} {path}\n".encode())
                 for path in ("hetren_visible.jsonl", "evaluator/cases.jsonl", "evaluator/tags.jsonl")}
        timing = {"evaluator/labeling_time.jsonl": _write(data / name / "evaluator/labeling_time.jsonl", b"t\n")}
        _write(root / f"docs/milestone-2/{name}.manifest.json", json.dumps({"files": files, "timing_file": timing}).encode())
    for name in ("splits-v1", "splits-v2"):
        files = {path: _write(root / f"docs/milestone-2/{name}" / path, f"{name} {path}\n".encode())
                 for path in ("train.txt", "validation.txt", "test_in_distribution.txt", "test_held_out.txt", "dropped.tsv")}
        _write(root / f"docs/milestone-2/{name}/manifest.json", json.dumps({"files": files}).encode())
    live = data / "live-test-v1"
    files = {path: _write(live / path, f"live {path}\n".encode())
             for path in ("hetren_visible_final.jsonl", "evaluator/live_plan.jsonl", "evaluator/live_labels_final.jsonl",
                          "evaluator/confirmations.jsonl", "evaluator/confirmation_results.jsonl")}
    _write(live / "hetren_visible.jsonl", b"not final: never staged\n")
    _write(live / "evaluator/live_labels.jsonl", b"not final: never staged\n")
    for run in ("run-0001", "run-0002"):
        _write(live / "captures" / run / "capture-0001.json", f"{run} capture\n".encode())
    _write(live / "captures/ledger.json", b"{}\n")
    _write(live / "confirm/run-0001.json", b"confirm\n")
    _write(live / "confirm-captures/run-0001/capture-0001.json", b"confirm capture\n")
    specs = {run: _write(live / "specs" / f"{run}.json", f"{run} spec\n".encode()) for run in ("run-0001", "run-0002")}
    files["specs"] = _sha("".join(f"{k} {v}\n" for k, v in sorted(specs.items())).encode())
    for name in ("captures", "confirm", "confirm-captures"):
        files[f"{name}/"] = _folder(live / name)
    _write(root / "docs/milestone-2/live-test-v1.manifest.json", json.dumps({"files": files}).encode())
    for path in ("docs/milestone-3/train-v1.manifest.json", "docs/milestone-3/train-v1-budget.json",
                 "docs/milestone-2/EVAL_PROTOCOL.md", "docs/milestone-2/EVAL_PROTOCOL.sha256"):
        _write(root / path, f"{path}\n".encode())
    card = tmp_path / "dataset-card.md"
    card.write_text("# data\nload_dataset(\"<this repository>\")\nat commit `<commit>`\n", encoding="utf-8")
    return {"repo_root": root, "data_dir": data, "card": card, "commit": "HEAD",
            "git_show": lambda commit, path: (root / path).read_bytes(), "git_commit": lambda revision: "c" * 40}


DATASET_LAYOUT = sorted([
    "LICENSE", "README.md",
    *(f"{n}/{p}" for n in ("dataset-v2", "dataset-v3")
      for p in ("hetren_visible.jsonl", "evaluator/cases.jsonl", "evaluator/tags.jsonl", "evaluator/labeling_time.jsonl")),
    *(f"{n}/{p}" for n in ("splits-v1", "splits-v2")
      for p in ("train.txt", "validation.txt", "test_in_distribution.txt", "test_held_out.txt", "dropped.tsv")),
    "live-test-v1/hetren_visible_final.jsonl", "live-test-v1/evaluator/live_plan.jsonl",
    "live-test-v1/evaluator/live_labels_final.jsonl", "live-test-v1/evaluator/confirmations.jsonl",
    "live-test-v1/evaluator/confirmation_results.jsonl", "live-test-v1/specs/run-0001.json", "live-test-v1/specs/run-0002.json",
    "live-test-v1/captures/ledger.json", "live-test-v1/captures/run-0001/capture-0001.json",
    "live-test-v1/captures/run-0002/capture-0001.json", "live-test-v1/confirm/run-0001.json",
    "live-test-v1/confirm-captures/run-0001/capture-0001.json",
    *(f"manifests/{n}.manifest.json" for n in ("dataset-v2", "dataset-v3", "splits-v1", "splits-v2", "live-test-v1")),
    "training/train-v1.manifest.json", "training/train-v1-budget.json",
    "protocol/EVAL_PROTOCOL.md", "protocol/EVAL_PROTOCOL.sha256",
])


def test_dataset_staging_checks_every_hash_and_lays_out_the_repository(dataset_sources, tmp_path):
    out = tmp_path / "staged"
    staged = release.stage_dataset("someone/hetren-runs", out, log=lambda m: None, **dataset_sources)
    assert sorted(staged) == DATASET_LAYOUT  # the live test's non-final files are left out
    sums = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert sums == [f"{digest}  {path}" for path, digest in staged.items()]
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert 'load_dataset("someone/hetren-runs")' in readme and f"at commit `{'c' * 40}`" in readme
    licence = (out / "LICENSE").read_text(encoding="utf-8")
    assert "CC BY 4.0" in licence and "https://creativecommons.org/licenses/by/4.0/legalcode" in licence
    root = dataset_sources["repo_root"]
    assert (out / "manifests/splits-v2.manifest.json").read_bytes() == (root / "docs/milestone-2/splits-v2/manifest.json").read_bytes()


def test_a_changed_data_file_or_live_folder_stages_nothing(dataset_sources, tmp_path):
    data = dataset_sources["data_dir"]
    (data / "dataset-v3/evaluator/tags.jsonl").write_bytes(b"edited\n")
    (data / "live-test-v1/captures/run-0002/extra.json").write_bytes(b"{}\n")
    (data / "live-test-v1/specs/run-0002.json").write_bytes(b"edited\n")
    out = tmp_path / "staged"
    with pytest.raises(release.ReleaseError) as stop:
        release.stage_dataset("someone/hetren-runs", out, log=lambda m: None, **dataset_sources)
    assert "dataset-v3/evaluator/tags.jsonl: sha256 differs" in str(stop.value)
    assert "live-test-v1/captures/: folder hash differs" in str(stop.value)
    assert "live-test-v1/specs/: folder hash differs" in str(stop.value)
    assert not out.exists()


def test_dataset_staging_refuses_manifests_that_differ_from_the_commit(dataset_sources, tmp_path):
    committed = dict(dataset_sources, git_show=lambda commit, path: b"older\n" if path.endswith("splits-v1/manifest.json")
                     else (dataset_sources["repo_root"] / path).read_bytes())
    with pytest.raises(release.ReleaseError, match=r"docs/milestone-2/splits-v1/manifest.json: differs from commit c{40}"):
        release.stage_dataset("someone/hetren-runs", tmp_path / "staged", log=lambda m: None, **committed)
    with pytest.raises(release.ReleaseError, match="not empty"):
        (tmp_path / "full").mkdir()
        (tmp_path / "full/x").write_text("x")
        release.stage_dataset("someone/hetren-runs", tmp_path / "full", log=lambda m: None, **dataset_sources)


def test_the_folder_hashes_agree_with_the_evaluators(tmp_path):
    from packages.support_evaluator.live_episodes import directory_digest

    for path, data in {"run-0001/capture-0001.json": b"a", "run-0002/capture-0001.json": b"b", "ledger.json": b"{}"}.items():
        _write(tmp_path / "captures" / path, data)
    assert release.tree_digest(tmp_path / "captures") == directory_digest(tmp_path / "captures")
    live = REPO_ROOT / "artifacts/milestone-2/live-test-v1"
    if not live.is_dir():
        pytest.skip("the live test's data is not present (it is gitignored)")
    manifest = json.loads((REPO_ROOT / "docs/milestone-2/live-test-v1.manifest.json").read_text(encoding="utf-8"))["files"]
    assert release.specs_digest(live / "specs") == manifest["specs"]
    for name in ("captures", "confirm", "confirm-captures"):
        assert release.tree_digest(live / name) == directory_digest(live / name) == manifest[f"{name}/"]


def _dataset_remote(out: Path, lfs: set[str]) -> list[dict]:
    entries = []
    for p in sorted(out.rglob("*")):
        if p.is_file():
            path = p.relative_to(out).as_posix()
            entry = {"type": "file", "path": path, "oid": release.git_blob_id(p), "size": p.stat().st_size}
            if path in lfs:
                entry["lfs"] = {"oid": _sha(p.read_bytes()), "size": p.stat().st_size}
            entries.append(entry)
    return entries


def test_verify_remote_reads_a_dataset_repository_page_by_page(dataset_sources, tmp_path):
    out = tmp_path / "staged"
    release.stage_dataset("someone/hetren-runs", out, log=lambda m: None, **dataset_sources)
    entries = _dataset_remote(out, {"dataset-v2/hetren_visible.jsonl"}) + [{"type": "file", "path": ".gitattributes"},
                                                                         {"type": "directory", "path": "dataset-v2"}]
    first = "https://huggingface.co/api/datasets/someone/hetren-runs/tree/main?recursive=true"
    second = first + "&cursor=abc"
    pages = {first: (entries[:10], second), second: (entries[10:], None)}
    seen = []
    problems = release.verify_remote("someone/hetren-runs", out, fetch=lambda url: seen.append(url) or pages[url],
                                     repo_type="dataset", log=lambda m: None)
    assert problems == [] and seen == [first, second]

    wrong = [dict(e, lfs={"oid": "f" * 64}) if e["path"] == "dataset-v2/hetren_visible.jsonl" else e for e in entries]
    wrong = [e for e in wrong if e["path"] != "LICENSE"]
    problems = release.verify_remote("someone/hetren-runs", out, fetch=lambda url: wrong, repo_type="dataset",
                                     log=lambda m: None)
    assert any(p.startswith("dataset-v2/hetren_visible.jsonl: LFS sha256 " + "f" * 64) for p in problems)
    assert "LICENSE: not in the repository" in problems

    (out / "splits-v1/train.txt").write_bytes(b"edited after staging\n")
    with pytest.raises(release.ReleaseError, match=r"no longer matches its SHA256SUMS: changed \['splits-v1/train.txt'\]"):
        release.verify_remote("someone/hetren-runs", out, fetch=lambda url: entries, repo_type="dataset", log=lambda m: None)


def test_the_next_page_comes_from_the_link_header():
    assert release._next_page('<https://huggingface.co/api/x?cursor=a%3D>; rel="next"') == \
        "https://huggingface.co/api/x?cursor=a%3D"
    assert release._next_page(None) is None and release._next_page('<https://x>; rel="prev"') is None


def test_the_real_dataset_release_lists_what_the_card_describes():
    files, folders = release.dataset_files()
    assert len(files) == 8 + 10 + 5  # 2 datasets x 4, 2 splits x 5, the live test's 5 files
    assert sorted(folders) == ["live-test-v1/captures", "live-test-v1/confirm", "live-test-v1/confirm-captures",
                               "live-test-v1/specs"]
    card = release.DATASET_CARD.read_text(encoding="utf-8")
    front = card.split("---\n")[1]
    assert "license: cc-by-4.0\n" in front
    for path in re.findall(r"data_files: (\S+)", front):  # the dataset viewer's files are all staged
        assert path in files, path
    assert card.count("<this repository>") >= 1 and card.count("<commit>") == 1
    assert "Harsha1412/hetren-qwen3-4b-diagnosis" in card and 'author = {Nuthakki, Deva Harsha}' in card
    for path in release.DATASET_DOCS.values():
        assert (REPO_ROOT / path).is_file(), path


@pytest.mark.skipif(not (REPO_ROOT / "artifacts/milestone-2/live-test-v1").is_dir(), reason="the data is gitignored")
def test_the_real_dataset_stages_from_the_local_data(tmp_path):
    # The data against the working tree's manifests; whether they are committed is the operator's run's check.
    staged = release.stage_dataset("Harsha1412/hetren-support-runs", tmp_path / "staged", log=lambda m: None,
                                   git_show=lambda commit, path: (REPO_ROOT / path).read_bytes(),
                                   git_commit=lambda revision: "0" * 40)
    assert len(staged) == 23 + 300 + 1081 + 120 + 480 + 9 + 2  # files, specs, captures, confirm, confirm captures, docs, card and licence
    assert "Harsha1412/hetren-support-runs" in (tmp_path / "staged/README.md").read_text(encoding="utf-8")


def test_dataset_staging_refuses_a_card_that_differs_from_the_commit(dataset_sources, tmp_path):
    root = dataset_sources["repo_root"]
    card = root / "docs/milestone-4/dataset-card.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("# data\n<this repository> at `<commit>`, edited after the commit\n", encoding="utf-8")
    committed = dict(dataset_sources, card=card, git_show=lambda commit, path: b"# data\n" if path.endswith("dataset-card.md")
                     else (root / path).read_bytes())
    with pytest.raises(release.ReleaseError, match="docs/milestone-4/dataset-card.md: differs from commit"):
        release.stage_dataset("someone/hetren-runs", tmp_path / "staged", log=lambda m: None, **committed)


def test_verify_remote_runs_as_the_runbook_runs_it(dataset_sources, tmp_path):
    """`python scripts/hf_release.py verify-remote …` from the repository root, without PYTHONPATH, against a local
    stand-in for the Hub API: the HTTPS path imports packages.hetren_cli.models, which once failed this way."""
    import os
    import subprocess
    import sys
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    out = tmp_path / "staged"
    release.stage_dataset("someone/hetren-runs", out, log=lambda m: None, **dataset_sources)
    entries = _dataset_remote(out, set())
    requests = []

    class Hub(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append((self.path, self.headers.get("Authorization")))
            body = json.dumps(entries[:5] if "cursor" not in self.path else entries[5:]).encode()
            self.send_response(200)
            if "cursor" not in self.path:
                self.send_header("Link", f'<http://127.0.0.1:{server.server_port}{self.path}&cursor=2>; rel="next"')
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Hub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "HF_TOKEN")}
    env["HF_ENDPOINT"] = f"http://127.0.0.1:{server.server_port}"
    try:
        run = subprocess.run([sys.executable, "scripts/hf_release.py", "verify-remote", "--repo", "someone/hetren-runs",
                              "--staged", str(out), "--type", "dataset", "--revision", "abc"],
                             cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60)
    finally:
        server.shutdown()
    assert run.returncode == 0, run.stdout + run.stderr
    assert f"ok    someone/hetren-runs@abc: {len(entries)} files, each equal to the staged copy" in run.stdout
    assert [path for path, _ in requests] == ["/api/datasets/someone/hetren-runs/tree/abc?recursive=true",
                                              "/api/datasets/someone/hetren-runs/tree/abc?recursive=true&cursor=2"]
    assert all(auth is None for _, auth in requests)  # no token is sent when HF_TOKEN is unset


def test_refresh_card_rewrites_only_the_readme_and_its_sum(sources, tmp_path):
    out = tmp_path / "staged"
    release.stage_model("someone/hetren-test", out, log=lambda m: None, **sources)
    (out / "SHA256SUMS").write_text("".join(f"{_sha((out / p).read_bytes())}  {p}\n" for p in
                                            sorted(q.relative_to(out).as_posix() for q in out.rglob("*") if q.is_file()
                                                   and q.name != "SHA256SUMS")), encoding="utf-8")
    before = {p: (out / p).read_bytes() for p in ("LICENSE", "hetren-qwen3-4b-ckpt0792-q4_k_m.gguf")}
    card = sources["card"]
    card.write_text("# card, now with the dataset link\nfetch-model --repo <this repository>\n", encoding="utf-8")
    committed = lambda commit, path: card.read_bytes()
    sums = release.refresh_model_card("someone/hetren-test", out, card=card, repo_root=card.parent, git_show=committed,
                                      log=lambda m: None)
    assert (out / "README.md").read_text(encoding="utf-8") == "# card, now with the dataset link\nfetch-model --repo someone/hetren-test\n"
    assert sums["README.md"] == _sha((out / "README.md").read_bytes())
    assert (out / "SHA256SUMS").read_text(encoding="utf-8") == "".join(f"{d}  {p}\n" for p, d in sorted(sums.items()))
    assert all((out / p).read_bytes() == data for p, data in before.items())

    with pytest.raises(release.ReleaseError, match="uncommitted changes"):
        release.refresh_model_card("someone/hetren-test", out, card=card, repo_root=card.parent,
                                   git_show=lambda commit, path: b"older", log=lambda m: None)
    (out / "LICENSE").write_text("edited\n", encoding="utf-8")
    with pytest.raises(release.ReleaseError, match=r"changed \['LICENSE'\]"):
        release.refresh_model_card("someone/hetren-test", out, card=card, repo_root=card.parent, git_show=committed,
                                   log=lambda m: None)
