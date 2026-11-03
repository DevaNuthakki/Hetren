#!/usr/bin/env python3
"""Pack the code and the validation data for the Kaggle small-model baseline.

The bundle is ``git archive HEAD`` (committed code, docs and split lists)
plus the gitignored datasets v2 and v3 (visible records, evaluator cases,
tags and manifest) and the live test split (specs, plan, captures, final
labels and records). Each data file is checked against its committed
manifest before it is packed (the live specs and captures as the digests
the live manifest records), and ``BUNDLE.json`` records the commit and every
packed data file's hash. Uncommitted changes are refused,
so the bundle is exactly a commit plus verified data.

Upload the result as a private Kaggle Dataset and attach it to the notebook
``notebooks/milestone-2/qwen_untrained_baseline.ipynb`` (validation) or
``qwen_untrained_test.ipynb`` (test splits).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile


REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS = (
    ("artifacts/milestone-2/dataset-v2", "docs/milestone-2/dataset-v2.manifest.json"),
    ("artifacts/milestone-2/dataset-v3", "docs/milestone-2/dataset-v3.manifest.json"),
)
DATA_FILES = ("hetren_visible.jsonl", "evaluator/cases.jsonl", "evaluator/tags.jsonl")
LIVE = ("artifacts/milestone-2/live-test-v1", "docs/milestone-2/live-test-v1.manifest.json")
LIVE_FILES = ("evaluator/live_plan.jsonl", "evaluator/live_labels_final.jsonl", "hetren_visible_final.jsonl")
LIVE_DIRS = ("specs", "captures")


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, capture_output=True).stdout


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)

    return digest.hexdigest()


def _specs_digest(directory: Path) -> str:
    """The live export's digest: sha256 of the sorted "<run_id> <sha256 of its spec file>" lines."""
    lines = sorted(f"{p.stem} {_sha256(p)}\n" for p in directory.glob("run-*.json"))
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _directory_digest(directory: Path) -> str:
    """sha256 of the sorted "<relative path> <sha256>" lines of every file below ``directory``."""
    lines = sorted(f"{p.relative_to(directory).as_posix()} {_sha256(p)}\n" for p in directory.rglob("*") if p.is_file())
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _check_live() -> dict[str, str]:
    directory, manifest_path = LIVE
    expected = json.loads((REPO_ROOT / manifest_path).read_text(encoding="utf-8"))["files"]
    live = REPO_ROOT / directory
    found = {name: _sha256(live / name) for name in LIVE_FILES}
    found["specs"] = _specs_digest(live / "specs")
    found["captures/"] = _directory_digest(live / "captures")

    for name, digest in found.items():
        if digest != expected[name]:
            raise SystemExit(f"STOP: {directory}/{name} does not match {manifest_path}")

    return {f"{directory}/{name}": digest for name, digest in found.items()}


def build(out: Path) -> dict[str, object]:
    if _git("status", "--porcelain", "--untracked-files=no").strip():
        raise SystemExit("STOP: uncommitted changes; commit first so the bundle is exactly a commit")

    commit = _git("rev-parse", "HEAD").decode().strip()
    packed: dict[str, str] = {}

    for directory, manifest_path in DATASETS:
        expected = json.loads((REPO_ROOT / manifest_path).read_text(encoding="utf-8"))["files"]

        for name in DATA_FILES:
            digest = _sha256(REPO_ROOT / directory / name)

            if digest != expected[name]:
                raise SystemExit(f"STOP: {directory}/{name} does not match {manifest_path}")

            packed[f"{directory}/{name}"] = digest

    packed.update(_check_live())
    out.parent.mkdir(parents=True, exist_ok=True)
    code = tarfile.open(fileobj=io.BytesIO(_git("archive", "--format=tar", "HEAD")))
    info = {"commit": commit, "data": packed}

    with tarfile.open(out, "w:gz") as bundle:
        for member in code.getmembers():
            bundle.addfile(member, code.extractfile(member) if member.isfile() else None)

        for directory, _ in DATASETS:
            for name in (*DATA_FILES, "manifest.json"):
                bundle.add(REPO_ROOT / directory / name, arcname=f"{directory}/{name}")

        live = LIVE[0]

        for name in (*LIVE_FILES, "manifest.json"):
            bundle.add(REPO_ROOT / live / name, arcname=f"{live}/{name}")

        for name in LIVE_DIRS:
            for path in sorted((REPO_ROOT / live / name).rglob("*")):
                if path.is_file():
                    bundle.add(path, arcname=f"{live}/{path.relative_to(REPO_ROOT / live).as_posix()}")

        data = (json.dumps(info, indent=2, sort_keys=True) + "\n").encode("utf-8")
        member = tarfile.TarInfo("BUNDLE.json")
        member.size = len(data)
        bundle.addfile(member, io.BytesIO(data))

    return {**info, "bundle": str(out), "bundle_sha256": _sha256(out)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "artifacts/milestone-2/kaggle/hetren-m2-bundle.tar.gz")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.out.exists():
        print(f"STOP: {args.out} exists; choose another --out", file=sys.stderr)
        return 2

    print(json.dumps(build(args.out), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
