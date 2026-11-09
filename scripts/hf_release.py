"""Stage and verify the Hugging Face model repository (Milestone 4, step 7a). Standard library only.

``stage-model`` builds the upload folder from the local export and checkpoint. It writes nothing outside
``--out``, refuses a non-empty folder, and checks every file's sha256 against the committed export manifest
before staging it:

    python scripts/hf_release.py stage-model --repo <user>/<name> --out <empty folder>

The staged layout is the one ``hetren fetch-model`` reads:

    hetren-qwen3-4b-ckpt0792-q4_k_m.gguf, hetren-qwen3-4b-ckpt0792-q8_0.gguf   (the f16 GGUF was never kept)
    tokenizer/<the 9 files in the manifest's merge.files>
    adapter/adapter_model.safetensors, adapter/adapter_config.json             (PEFT's generated README is left out)
    export.manifest.json, README.md (the model card), LICENSE, SHA256SUMS

Large files are hard links to the sources (same filesystem), or copies otherwise; either way the staged
bytes are hashed again. The operator reviews the folder and uploads it with ``hf upload``.

``verify-remote`` (operator, after the upload) reads the repository's file list from the Hugging Face API,
without downloading. Each large file's LFS sha256 must equal the manifest's; each small file's git blob id
must equal the staged copy's. Nothing may be missing or extra:

    python scripts/hf_release.py verify-remote --repo <user>/<name> --staged <folder> [--revision <sha>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.parse
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "docs/milestone-4/export.manifest.json"
CARD = REPO_ROOT / "docs/milestone-4/model-card.md"
LICENSE = REPO_ROOT / "LICENSE"
GGUF_DIR = REPO_ROOT / "artifacts/milestone-4/export-2/gguf-export"
ADAPTER_DIR = REPO_ROOT / "artifacts/milestone-3/training-session-2/qlora-train-session-2/checkpoint-0792/adapter"
RELEASED_GGUFS = ("hetren-qwen3-4b-ckpt0792-q4_k_m.gguf", "hetren-qwen3-4b-ckpt0792-q8_0.gguf")
REPO_PLACEHOLDER = "<this repository>"
CHUNK = 1 << 20


class ReleaseError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)

    return digest.hexdigest()


def git_blob_id(path: Path) -> str:
    """Git's object id for a file (what the Hugging Face API reports for files not stored in LFS)."""
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def expected_files(manifest: dict) -> dict[str, str]:
    """Staged path -> the manifest's sha256, for every file taken from the export or the checkpoint."""
    files = {name: manifest["gguf"][name]["sha256"] for name in RELEASED_GGUFS}
    files.update({f"tokenizer/{name}": digest for name, digest in manifest["merge"]["files"].items()
                  if not name.startswith("model")})
    files.update({path: digest for path, digest in manifest["merge"]["checkpoint"]["files"].items()
                  if path.startswith("adapter/")})
    return files


def source_of(path: str, gguf_dir: Path, adapter_dir: Path) -> Path:
    if path.startswith("adapter/"):
        return adapter_dir / path.split("/", 1)[1]

    return gguf_dir / path  # the GGUFs at the top, tokenizer/ beside them


def card_text(card: Path, repo: str) -> str:
    text = card.read_text(encoding="utf-8")

    if REPO_PLACEHOLDER not in text:
        raise ReleaseError(f"{card} has no {REPO_PLACEHOLDER!r} to fill in")

    return text.replace(REPO_PLACEHOLDER, repo)


def _place(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)


def stage_model(repo: str, out: Path, *, manifest_path: Path = MANIFEST, card: Path = CARD,
                license_path: Path = LICENSE, gguf_dir: Path = GGUF_DIR, adapter_dir: Path = ADAPTER_DIR,
                log=print) -> dict[str, str]:
    """Stage the repository into ``out``; returns staged path -> sha256 (also written as SHA256SUMS)."""
    if "/" not in repo or repo.count("/") != 1 or repo.startswith("/") or repo.endswith("/"):
        raise ReleaseError(f"--repo must be <user or organization>/<name>, not {repo!r}")

    out = Path(out)

    if out.exists() and any(out.iterdir()):
        raise ReleaseError(f"{out} is not empty; stage into a new folder")

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    local_manifest = Path(gguf_dir) / "export.manifest.json"

    if local_manifest.is_file() and sha256_file(local_manifest) != sha256_file(manifest_path):
        raise ReleaseError(f"{local_manifest} differs from the committed {manifest_path}")

    expected = expected_files(manifest)
    problems = []

    for path, digest in expected.items():
        source = source_of(path, Path(gguf_dir), Path(adapter_dir))

        if not source.is_file():
            problems.append(f"{path}: missing ({source})")
        elif sha256_file(source) != digest:
            problems.append(f"{path}: sha256 differs from the manifest's {digest} ({source})")

    if problems:
        raise ReleaseError("not staged:\n  " + "\n  ".join(problems))

    out.mkdir(parents=True, exist_ok=True)

    for path in expected:
        _place(source_of(path, Path(gguf_dir), Path(adapter_dir)), out / path)

    shutil.copyfile(manifest_path, out / "export.manifest.json")
    shutil.copyfile(license_path, out / "LICENSE")
    (out / "README.md").write_text(card_text(Path(card), repo), encoding="utf-8")

    staged = {p.relative_to(out).as_posix(): sha256_file(p) for p in sorted(out.rglob("*")) if p.is_file()}
    mismatched = [path for path, digest in expected.items() if staged[path] != digest]

    if mismatched:  # a copy went wrong
        raise ReleaseError(f"staged copies differ from the manifest: {mismatched}")

    (out / "SHA256SUMS").write_text("".join(f"{digest}  {path}\n" for path, digest in staged.items()),
                                    encoding="utf-8")
    log(f"staged {len(staged)} files for {repo} in {out} ({sum((out / p).stat().st_size for p in staged) / 1e9:.2f} GB); "
        "every file from the export and checkpoint matches the manifest")
    return staged


def remote_files(repo: str, revision: str = "main", fetch=None) -> dict[str, dict]:
    """The repository's files from the Hugging Face API (no download): path -> {"oid", "size", "lfs_sha256"}."""
    endpoint = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
    url = f"{endpoint}/api/models/{repo}/tree/{urllib.parse.quote(revision, safe='')}?recursive=true"

    if fetch is None:
        def fetch(address: str) -> list:
            request = urllib.request.Request(address, headers={"User-Agent": "hetren-release-check"})

            if os.environ.get("HF_TOKEN"):  # a private repository, before it is made public
                request.add_header("Authorization", f"Bearer {os.environ['HF_TOKEN']}")

            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))

    entries = fetch(url)
    return {e["path"]: {"oid": e.get("oid"), "size": e.get("size"), "lfs_sha256": (e.get("lfs") or {}).get("oid")}
            for e in entries if e.get("type") == "file"}


def verify_remote(repo: str, staged: Path, revision: str = "main", *, manifest_path: Path = MANIFEST,
                  fetch=None, log=print) -> list[str]:
    """Problems found (empty when the repository holds exactly the staged files, by hash)."""
    staged = Path(staged)
    local = {p.relative_to(staged).as_posix(): p for p in sorted(staged.rglob("*")) if p.is_file()}
    expected = expected_files(json.loads(Path(manifest_path).read_text(encoding="utf-8")))
    remote = {path: entry for path, entry in remote_files(repo, revision, fetch).items()
              if path != ".gitattributes"}  # Hugging Face creates it with the repository
    problems = [f"{path}: not in the repository" for path in local if path not in remote]
    problems += [f"{path}: in the repository but not staged" for path in remote if path not in local]

    for path, entry in remote.items():
        if path not in local:
            continue

        if entry["lfs_sha256"]:
            want = expected.get(path) or sha256_file(local[path])

            if entry["lfs_sha256"] != want:
                problems.append(f"{path}: LFS sha256 {entry['lfs_sha256']}, expected {want}")
        elif entry["oid"] != git_blob_id(local[path]):
            problems.append(f"{path}: git blob {entry['oid']}, expected {git_blob_id(local[path])}")

        if entry["size"] is not None and entry["size"] != local[path].stat().st_size:
            problems.append(f"{path}: {entry['size']} bytes, expected {local[path].stat().st_size}")

    for problem in problems:
        log(f"FAIL  {problem}")

    if not problems:
        log(f"ok    {repo}@{revision}: {len(remote)} files, each equal to the staged copy "
            f"({sum(1 for e in remote.values() if e['lfs_sha256'])} by LFS sha256, the rest by git blob id)")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage-model", help="stage the model repository into an empty folder")
    stage.add_argument("--repo", required=True, help="<user or organization>/<name> on Hugging Face")
    stage.add_argument("--out", required=True, type=Path)
    verify = commands.add_parser("verify-remote", help="compare the uploaded repository with the staged folder")
    verify.add_argument("--repo", required=True)
    verify.add_argument("--staged", required=True, type=Path)
    verify.add_argument("--revision", default="main")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        if args.command == "stage-model":
            stage_model(args.repo, args.out)
            return 0

        return 1 if verify_remote(args.repo, args.staged, args.revision) else 0
    except (ReleaseError, OSError, ValueError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
