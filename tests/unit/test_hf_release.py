"""The Hugging Face staging and verification script (step 7a), and the model card's numbers. Nothing is
downloaded or uploaded: the files are tiny stand-ins and the API is a fake."""

from __future__ import annotations

import hashlib
import json
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
