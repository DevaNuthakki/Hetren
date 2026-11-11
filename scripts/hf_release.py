"""Stage and verify the Hugging Face model and dataset repositories (Milestone 4, step 7). Standard library only.

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

``stage-dataset`` (step 7b) builds the dataset repository's folder from the local data, in the same way: it
checks every file against the manifests committed in this repository, and also checks that those manifests are
the ones in ``--commit`` (default HEAD), the commit the card names:

    python scripts/hf_release.py stage-dataset --repo <user>/<name> --out <empty folder> [--commit <sha>]

    dataset-v2/, dataset-v3/      hetren_visible.jsonl and evaluator/{cases,tags,labeling_time}.jsonl
    splits-v1/, splits-v2/        the four split lists and dropped.tsv
    live-test-v1/                 hetren_visible_final.jsonl, specs/, captures/, confirm/, confirm-captures/ and
                                  evaluator/{live_plan,live_labels_final,confirmations,confirmation_results}.jsonl
    training/                     the training file's manifest and budget record (the file itself is rebuildable)
    protocol/                     EVAL_PROTOCOL.md and its sha256
    manifests/                    the five committed manifests
    README.md (the dataset card), LICENSE (CC BY 4.0), SHA256SUMS

The live test's folders are checked with the manifest's own folder hashes: for ``captures/``, ``confirm/`` and
``confirm-captures/``, the sha256 of the sorted ``<relative path> <sha256>`` lines of every file below; for
``specs``, the sha256 of the sorted ``<run id> <sha256>`` lines of ``specs/run-*.json``. They are computed here
rather than imported, since scripts may not import the evaluator; a test checks that they agree with it.

``verify-remote`` (operator, after the upload) reads the repository's file list from the Hugging Face API,
page by page, without downloading. Each large file's LFS sha256 must equal the manifest's (the model) or the
staged copy's (the dataset); each small file's git blob id must equal the staged copy's. Nothing may be
missing or extra:

    python scripts/hf_release.py verify-remote --repo <user>/<name> --staged <folder> [--revision <sha>]
    python scripts/hf_release.py verify-remote --repo <user>/<name> --staged <folder> --type dataset

``refresh-card`` (after a model card change) rewrites a staged model folder's ``README.md`` from the committed
card and its ``SHA256SUMS`` to match, after checking that every other staged file is unchanged. The operator
then uploads those two files as one commit, and ``verify-remote`` checks the whole repository again:

    python scripts/hf_release.py refresh-card --repo <user>/<name> --staged <folder>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:  # run as `python scripts/hf_release.py`: the HTTPS helper is in packages/
    sys.path.insert(0, str(REPO_ROOT))
MANIFEST = REPO_ROOT / "docs/milestone-4/export.manifest.json"
CARD = REPO_ROOT / "docs/milestone-4/model-card.md"
LICENSE = REPO_ROOT / "LICENSE"
GGUF_DIR = REPO_ROOT / "artifacts/milestone-4/export-2/gguf-export"
ADAPTER_DIR = REPO_ROOT / "artifacts/milestone-3/training-session-2/qlora-train-session-2/checkpoint-0792/adapter"
RELEASED_GGUFS = ("hetren-qwen3-4b-ckpt0792-q4_k_m.gguf", "hetren-qwen3-4b-ckpt0792-q8_0.gguf")
REPO_PLACEHOLDER = "<this repository>"
CHUNK = 1 << 20

DATASET_CARD = REPO_ROOT / "docs/milestone-4/dataset-card.md"
DATA_DIR = REPO_ROOT / "artifacts/milestone-2"
COMMIT_PLACEHOLDER = "<commit>"
DATASETS = ("dataset-v2", "dataset-v3")
SPLITS = ("splits-v1", "splits-v2")
LIVE = "live-test-v1"
LIVE_DIRS = ("captures", "confirm", "confirm-captures")
# Committed files copied as they are: staged path -> path in this repository.
DATASET_DOCS = {
    **{f"manifests/{name}.manifest.json": f"docs/milestone-2/{name}.manifest.json" for name in (*DATASETS, LIVE)},
    **{f"manifests/{name}.manifest.json": f"docs/milestone-2/{name}/manifest.json" for name in SPLITS},
    "training/train-v1.manifest.json": "docs/milestone-3/train-v1.manifest.json",
    "training/train-v1-budget.json": "docs/milestone-3/train-v1-budget.json",
    "protocol/EVAL_PROTOCOL.md": "docs/milestone-2/EVAL_PROTOCOL.md",
    "protocol/EVAL_PROTOCOL.sha256": "docs/milestone-2/EVAL_PROTOCOL.sha256",
}
DATASET_LICENSE = """\
Hetren support-agent runs
Copyright 2026 Deva Harsha Nuthakki

This dataset is licensed under the Creative Commons Attribution 4.0 International licence (CC BY 4.0).
You may share and adapt it for any purpose, provided you give appropriate credit, link to the licence, and
indicate if changes were made.

Licence summary: https://creativecommons.org/licenses/by/4.0/
Legal code:      https://creativecommons.org/licenses/by/4.0/legalcode

The code that generates and labels this data (https://github.com/DevaNuthakki/Hetren) is licensed separately,
under the Apache License 2.0.
"""


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


def tree_digest(directory: Path) -> str:
    """The live manifest's hash of a folder: sha256 of the sorted "<relative path> <sha256>" lines of every file."""
    lines = sorted(f"{p.relative_to(directory).as_posix()} {sha256_file(p)}\n"
                   for p in Path(directory).rglob("*") if p.is_file())
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def specs_digest(directory: Path) -> str:
    """The live manifest's hash of specs/: sha256 of the sorted "<run id> <sha256>" lines of run-*.json."""
    lines = sorted(f"{p.stem} {sha256_file(p)}\n" for p in Path(directory).glob("run-*.json"))
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def dataset_files(repo_root: Path = REPO_ROOT, data_dir: Path = DATA_DIR) -> tuple[dict[str, tuple[Path, str]], dict]:
    """(staged path -> (source, the manifest's sha256) for every data file hashed one by one,
    staged folder -> (source folder, the manifest's folder hash, "tree" or "specs") for the live test's folders)."""
    files, folders = {}, {}

    for name in DATASETS:
        manifest = json.loads((repo_root / f"docs/milestone-2/{name}.manifest.json").read_text(encoding="utf-8"))
        for path, digest in {**manifest["files"], **manifest["timing_file"]}.items():
            files[f"{name}/{path}"] = (data_dir / name / path, digest)

    for name in SPLITS:
        manifest = json.loads((repo_root / f"docs/milestone-2/{name}/manifest.json").read_text(encoding="utf-8"))
        for path, digest in manifest["files"].items():
            files[f"{name}/{path}"] = (repo_root / f"docs/milestone-2/{name}" / path, digest)

    manifest = json.loads((repo_root / f"docs/milestone-2/{LIVE}.manifest.json").read_text(encoding="utf-8"))
    for path, digest in manifest["files"].items():
        if path == "specs":
            folders[f"{LIVE}/specs"] = (data_dir / LIVE / "specs", digest, "specs")
        elif path.endswith("/"):
            folders[f"{LIVE}/{path.rstrip('/')}"] = (data_dir / LIVE / path.rstrip("/"), digest, "tree")
        else:
            files[f"{LIVE}/{path}"] = (data_dir / LIVE / path, digest)

    expected_folders = {f"{LIVE}/{name}" for name in (*LIVE_DIRS, "specs")}
    if set(folders) != expected_folders:
        raise ReleaseError(f"the live manifest's folders are {sorted(folders)}, not {sorted(expected_folders)}")

    return files, folders


def _folder_hash(directory: Path, kind: str) -> str:
    return specs_digest(directory) if kind == "specs" else tree_digest(directory)


def _git_show(commit: str, path: str, repo_root: Path = REPO_ROOT) -> bytes:
    return subprocess.run(["git", "-C", str(repo_root), "show", f"{commit}:{path}"], check=True,
                          capture_output=True).stdout


def _git_commit(revision: str, repo_root: Path = REPO_ROOT) -> str:
    return subprocess.run(["git", "-C", str(repo_root), "rev-parse", "--verify", f"{revision}^{{commit}}"], check=True,
                          capture_output=True, text=True).stdout.strip()


def dataset_card_text(card: Path, repo: str, commit: str) -> str:
    text = card_text(card, repo)

    if COMMIT_PLACEHOLDER not in text:
        raise ReleaseError(f"{card} has no {COMMIT_PLACEHOLDER!r} to fill in")

    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ReleaseError(f"the commit must be a full 40-character sha, not {commit!r}")

    return text.replace(COMMIT_PLACEHOLDER, commit)


def stage_dataset(repo: str, out: Path, *, commit: str = "HEAD", repo_root: Path = REPO_ROOT,
                  data_dir: Path = DATA_DIR, card: Path = DATASET_CARD, git_show=None, git_commit=None,
                  log=print) -> dict[str, str]:
    """Stage the dataset repository into ``out``; returns staged path -> sha256 (also written as SHA256SUMS)."""
    if "/" not in repo or repo.count("/") != 1 or repo.startswith("/") or repo.endswith("/"):
        raise ReleaseError(f"--repo must be <user or organization>/<name>, not {repo!r}")

    out, repo_root = Path(out), Path(repo_root)

    if out.exists() and any(out.iterdir()):
        raise ReleaseError(f"{out} is not empty; stage into a new folder")

    show = git_show or (lambda c, path: _git_show(c, path, repo_root))
    sha = (git_commit or (lambda revision: _git_commit(revision, repo_root)))(commit)
    problems = []

    sources = list(DATASET_DOCS.values())

    if Path(card).resolve().is_relative_to(repo_root.resolve()):  # the card too: it names this commit
        sources.append(Path(card).resolve().relative_to(repo_root.resolve()).as_posix())

    for source in sources:  # the manifests the card points to are the committed ones
        try:
            if show(sha, source) != (repo_root / source).read_bytes():
                problems.append(f"{source}: differs from commit {sha}")
        except (subprocess.CalledProcessError, OSError) as exc:
            problems.append(f"{source}: not readable from commit {sha} or the working tree ({exc})")

    files, folders = dataset_files(repo_root, Path(data_dir))

    for path, (source, digest) in files.items():
        if not source.is_file():
            problems.append(f"{path}: missing ({source})")
        elif sha256_file(source) != digest:
            problems.append(f"{path}: sha256 differs from the manifest's {digest} ({source})")

    for path, (source, digest, kind) in folders.items():
        if not source.is_dir():
            problems.append(f"{path}/: missing ({source})")
        elif _folder_hash(source, kind) != digest:
            problems.append(f"{path}/: folder hash differs from the manifest's {digest} ({source})")

    if problems:
        raise ReleaseError("not staged:\n  " + "\n  ".join(problems))

    readme = dataset_card_text(Path(card), repo, sha)
    out.mkdir(parents=True, exist_ok=True)

    for path, (source, _) in files.items():
        _place(source, out / path)

    for path, (source, _, kind) in folders.items():
        members = source.glob("run-*.json") if kind == "specs" else source.rglob("*")
        for member in sorted(members):
            if member.is_file():
                _place(member, out / path / member.relative_to(source))

    for path, source in DATASET_DOCS.items():
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo_root / source, out / path)

    (out / "README.md").write_text(readme, encoding="utf-8")
    (out / "LICENSE").write_text(DATASET_LICENSE, encoding="utf-8")

    staged = {p.relative_to(out).as_posix(): sha256_file(p) for p in sorted(out.rglob("*")) if p.is_file()}
    wrong = [path for path, (_, digest) in files.items() if staged[path] != digest]
    wrong += [f"{path}/" for path, (_, digest, kind) in folders.items() if _folder_hash(out / path, kind) != digest]

    if wrong:  # a copy went wrong
        raise ReleaseError(f"staged copies differ from the manifests: {wrong}")

    (out / "SHA256SUMS").write_text("".join(f"{digest}  {path}\n" for path, digest in staged.items()),
                                    encoding="utf-8")
    log(f"staged {len(staged) + 1} files for {repo} in {out} "
        f"({sum((out / p).stat().st_size for p in staged) / 1e6:.1f} MB); every data file matches its manifest, "
        f"and the manifests match commit {sha}")
    return staged


def refresh_model_card(repo: str, staged: Path, *, card: Path = CARD, repo_root: Path = REPO_ROOT, git_show=None,
                       log=print) -> dict[str, str]:
    """Rewrite ``staged``'s README.md from the committed model card and SHA256SUMS to match; returns the new sums."""
    staged, repo_root = Path(staged), Path(repo_root)
    sums_path = staged / "SHA256SUMS"
    sums = dict(reversed(line.split("  ", 1)) for line in sums_path.read_text(encoding="utf-8").splitlines())
    local = {p.relative_to(staged).as_posix(): p for p in sorted(staged.rglob("*")) if p.is_file()}
    changed = sorted(path for path, digest in sums.items()
                     if path != "README.md" and (path not in local or sha256_file(local[path]) != digest))
    unlisted = sorted(set(local) - set(sums) - {"SHA256SUMS"})

    if changed or unlisted:
        raise ReleaseError(f"{staged} differs from its SHA256SUMS beyond the card: changed {changed}, unlisted {unlisted}")

    relative = Path(card).resolve().relative_to(repo_root.resolve()).as_posix()
    show = git_show or (lambda commit, path: _git_show(commit, path, repo_root))

    if show("HEAD", relative) != Path(card).read_bytes():
        raise ReleaseError(f"{relative} has uncommitted changes; commit the card first")

    old = sums.get("README.md")
    (staged / "README.md").write_text(card_text(Path(card), repo), encoding="utf-8")
    sums["README.md"] = sha256_file(staged / "README.md")
    sums_path.write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(sums.items())), encoding="utf-8")
    log(f"README.md {old} -> {sums['README.md']}; SHA256SUMS rewritten ({len(sums)} files, "
        f"sha256 {sha256_file(sums_path)}); upload README.md and SHA256SUMS together")
    return sums


def _next_page(link: str | None) -> str | None:
    """The "next" URL of a GitHub-style Link header, as the Hugging Face API paginates."""
    match = re.search(r'<([^>]+)>\s*;\s*rel="next"', link or "")
    return match.group(1) if match else None


def remote_files(repo: str, revision: str = "main", fetch=None, repo_type: str = "model") -> dict[str, dict]:
    """The repository's files from the Hugging Face API (no download): path -> {"oid", "size", "lfs_sha256"}.
    ``fetch(url)`` returns the page's entries, or (entries, the next page's URL or None)."""
    if repo_type not in ("model", "dataset"):
        raise ReleaseError(f"repository type {repo_type!r} is neither model nor dataset")

    endpoint = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
    url = f"{endpoint}/api/{repo_type}s/{repo}/tree/{urllib.parse.quote(revision, safe='')}?recursive=true"

    if fetch is None:
        def fetch(address: str) -> tuple[list, str | None]:
            request = urllib.request.Request(address, headers={"User-Agent": "hetren-release-check"})

            if os.environ.get("HF_TOKEN"):  # a private repository, before it is made public
                request.add_header("Authorization", f"Bearer {os.environ['HF_TOKEN']}")

            from packages.hetren_cli.models import tls_context  # certifi's bundle when Python has no certificates

            with urllib.request.urlopen(request, timeout=60, context=tls_context()) as response:
                return json.loads(response.read().decode("utf-8")), _next_page(response.headers.get("Link"))

    entries, pages = [], 0

    while url:
        page = fetch(url)
        page, url = page if isinstance(page, tuple) else (page, None)
        entries += page
        pages += 1

        if pages > 1000:
            raise ReleaseError("more than 1,000 pages of files; stopping")

    return {e["path"]: {"oid": e.get("oid"), "size": e.get("size"), "lfs_sha256": (e.get("lfs") or {}).get("oid")}
            for e in entries if e.get("type") == "file"}


def verify_remote(repo: str, staged: Path, revision: str = "main", *, manifest_path: Path = MANIFEST,
                  fetch=None, repo_type: str = "model", log=print) -> list[str]:
    """Problems found (empty when the repository holds exactly the staged files, by hash).

    For the model, LFS files are compared with the export manifest's sha256. For the dataset, the staged folder
    is first checked against its own SHA256SUMS (staging checked it against the manifests), and LFS files are
    compared with the staged copies."""
    staged = Path(staged)
    local = {p.relative_to(staged).as_posix(): p for p in sorted(staged.rglob("*")) if p.is_file()}

    if repo_type == "dataset":
        sums = dict(reversed(line.split("  ", 1)) for line in (staged / "SHA256SUMS").read_text(encoding="utf-8").splitlines())
        changed = sorted(path for path, digest in sums.items() if path not in local or sha256_file(local[path]) != digest)
        unlisted = sorted(set(local) - set(sums) - {"SHA256SUMS"})

        if changed or unlisted:
            raise ReleaseError(f"the staged folder no longer matches its SHA256SUMS: changed {changed}, unlisted {unlisted}")

        expected = sums
    else:
        expected = expected_files(json.loads(Path(manifest_path).read_text(encoding="utf-8")))

    remote = {path: entry for path, entry in remote_files(repo, revision, fetch, repo_type).items()
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
    dataset = commands.add_parser("stage-dataset", help="stage the dataset repository into an empty folder")
    dataset.add_argument("--repo", required=True, help="<user or organization>/<name> on Hugging Face")
    dataset.add_argument("--out", required=True, type=Path)
    dataset.add_argument("--commit", default="HEAD", help="the commit the card names (default HEAD)")
    refresh = commands.add_parser("refresh-card", help="rewrite a staged model folder's README.md and SHA256SUMS")
    refresh.add_argument("--repo", required=True)
    refresh.add_argument("--staged", required=True, type=Path)
    verify = commands.add_parser("verify-remote", help="compare the uploaded repository with the staged folder")
    verify.add_argument("--repo", required=True)
    verify.add_argument("--staged", required=True, type=Path)
    verify.add_argument("--revision", default="main")
    verify.add_argument("--type", default="model", choices=("model", "dataset"), help="the repository type")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        if args.command == "stage-model":
            stage_model(args.repo, args.out)
            return 0

        if args.command == "stage-dataset":
            stage_dataset(args.repo, args.out, commit=args.commit)
            return 0

        if args.command == "refresh-card":
            refresh_model_card(args.repo, args.staged)
            return 0

        return 1 if verify_remote(args.repo, args.staged, args.revision, repo_type=args.type) else 0
    except (ReleaseError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
