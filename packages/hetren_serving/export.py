"""Export the chosen checkpoint as GGUF files (EVAL_PROTOCOL.md, Amendment 2, "Export").

Two stages, both run by the operator:

``merge``
    Checks ``choice.json`` against its logged sha256 and the chosen
    checkpoint's ``state.json`` and adapter files against the hashes Amendment
    2 names, loads the fp16 base at the pinned revision, merges the adapter
    with ``peft merge_and_unload`` exactly as every fp16 evaluation does
    (``packages.hetren_baselines.local_model.TransformersModel``), and saves
    the merged model and tokenizer with ``merge.json`` (every file's sha256,
    device, library versions). Needs ``torch``, ``transformers`` and ``peft``.

``convert``
    Checks that the llama.cpp checkout is the pinned commit with a clean
    working tree and that the merged files still match ``merge.json``, runs
    ``convert_hf_to_gguf.py`` to an f16 GGUF and ``llama-quantize`` to each
    declared variant (no importance matrix), and writes the export manifest
    (``docs/milestone-4/export.manifest.json``). Needs the llama.cpp checkout,
    its built ``llama-quantize`` and the converter's Python requirements.

``python -m packages.hetren_serving.export merge --checkpoint <dir> --choice <choice.json> --out <dir>``
``python -m packages.hetren_serving.export convert --merged <dir> --llama-cpp <checkout> --out <dir> --manifest <path>``
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

from packages.hetren_baselines.local_model import QWEN_MODEL, QWEN_REVISION


# Amendment 2: the chosen checkpoint (Amendment 1) and the logged choice.json.
CHOSEN = {
    "checkpoint": "checkpoint-0792",
    "step": 792,
    "state_sha256": "d6230ff6e1780ac5286f0accc0a45298dd8db49fc11ed6fdb1330d98189276d5",
    "adapter_sha256": "5647f93f25c9f79c8e7fca0468d8aa7476afbcc348f3b42f420d1845098f4226",
}
CHOICE_SHA256 = "d41a7ef595e8882ff0dbb367e62b03b87c8f1006bb60da09811fb19f11992332"
ADAPTER_FILES = ("adapter/adapter_config.json", "adapter/adapter_model.safetensors")
LLAMA_CPP_RELEASE = "v0.7.0"
LLAMA_CPP_COMMIT = "620d2225cc436ab0b001e3200e590e3b286ef9ab"
VARIANTS = ("Q8_0", "Q4_K_M")
STEM = "hetren-qwen3-4b-ckpt0792"
MERGE_RECORD = "merge.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


def tree_hashes(directory: Path) -> dict[str, str]:
    """sha256 of every file under ``directory`` (relative POSIX paths), excluding the merge record."""
    directory = Path(directory)
    return {p.relative_to(directory).as_posix(): sha256_file(p) for p in sorted(directory.rglob("*"))
            if p.is_file() and p.name != MERGE_RECORD}


def verify_choice(choice_path: Path, choice_sha256: str = CHOICE_SHA256, chosen: dict = CHOSEN) -> dict:
    """``choice.json``, after checking its logged sha256 and that it names the chosen checkpoint."""
    if sha256_file(choice_path) != choice_sha256:
        raise ValueError(f"{choice_path} does not have the logged sha256 {choice_sha256}")

    choice = json.loads(Path(choice_path).read_text(encoding="utf-8"))
    recorded = {"checkpoint": choice["chosen"], "step": choice["step"],
                "state_sha256": choice["state_sha256"], "adapter_sha256": choice["adapter_sha256"]}

    if recorded != chosen:
        raise ValueError(f"{choice_path} does not name the chosen checkpoint: {recorded}")

    return choice


def verify_checkpoint(checkpoint: Path, chosen: dict = CHOSEN) -> dict[str, str]:
    """The adapter files' hashes, after checking ``state.json`` and every adapter file."""
    checkpoint = Path(checkpoint)
    state_path = checkpoint / "state.json"

    if sha256_file(state_path) != chosen["state_sha256"]:
        raise ValueError(f"{state_path} is not the chosen checkpoint's state.json ({chosen['state_sha256']})")

    state = json.loads(state_path.read_text(encoding="utf-8"))

    if state["step"] != chosen["step"] or state["files"]["adapter/adapter_model.safetensors"] != chosen["adapter_sha256"]:
        raise ValueError(f"{state_path} does not record the chosen step and adapter")

    hashes = {}

    for name in ADAPTER_FILES:
        hashes[name] = sha256_file(checkpoint / name)

        if hashes[name] != state["files"][name]:
            raise ValueError(f"{checkpoint / name} does not match its sha256 in state.json")

    return hashes


def library_versions(names=("torch", "transformers", "accelerate", "tokenizers", "peft", "safetensors",
                            "gguf", "numpy", "sentencepiece")) -> dict[str, str]:
    from importlib.metadata import version

    versions = {"python": platform.python_version()}

    for name in names:
        try:
            versions[name] = version(name)
        except Exception:
            versions[name] = "not installed"

    return versions


def merge(checkpoint: Path, choice_path: Path, out: Path, device: str = "cuda") -> dict:
    """Merge the chosen adapter into the fp16 base and save it (needs torch, transformers and peft)."""
    verify_choice(choice_path)
    adapter_hashes = verify_checkpoint(checkpoint)
    out = Path(out)

    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} is not empty")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    # As TransformersModel: fp16 base on the device, then merge_and_unload, then every parameter fp16.
    tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL, revision=QWEN_REVISION)
    model = AutoModelForCausalLM.from_pretrained(QWEN_MODEL, revision=QWEN_REVISION, torch_dtype=torch.float16).to(device)
    model = PeftModel.from_pretrained(model, str(Path(checkpoint) / "adapter")).merge_and_unload()

    if any(p.dtype != torch.float16 for p in model.parameters()):
        raise ValueError("the merged model is not entirely float16")

    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out, safe_serialization=True)
    tokenizer.save_pretrained(out)
    record = {
        "base": {"model": QWEN_MODEL, "revision": QWEN_REVISION, "dtype": "float16"},
        "checkpoint": {**CHOSEN, "files": adapter_hashes}, "choice_sha256": CHOICE_SHA256,
        "merge": "peft merge_and_unload into the fp16 base", "device": device,
        "device_name": torch.cuda.get_device_name(0) if device.startswith("cuda") else platform.processor() or "cpu",
        "libraries": library_versions(), "files": tree_hashes(out),
    }
    (out / MERGE_RECORD).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def verify_merged(merged: Path) -> dict:
    """``merge.json``, after checking that the merged files are still the ones it records."""
    record = json.loads((Path(merged) / MERGE_RECORD).read_text(encoding="utf-8"))

    if tree_hashes(merged) != record["files"]:
        raise ValueError(f"{merged}: the merged files differ from {MERGE_RECORD}")

    if (record["checkpoint"]["state_sha256"], record["checkpoint"]["adapter_sha256"]) != (
            CHOSEN["state_sha256"], CHOSEN["adapter_sha256"]):
        raise ValueError(f"{merged} was not merged from the chosen checkpoint")

    return record


def verify_llama_cpp(checkout: Path, commit: str = LLAMA_CPP_COMMIT) -> None:
    """Stop unless the checkout is exactly the pinned commit with no local changes."""
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(checkout), *args], check=True, capture_output=True, text=True).stdout

    head = git("rev-parse", "HEAD").strip()

    if head != commit:
        raise ValueError(f"{checkout} is at {head}, not the pinned llama.cpp commit {commit}")

    if git("status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError(f"{checkout} has local changes")


def commands(merged: Path, checkout: Path, out: Path, variants=VARIANTS) -> list[tuple[Path, list[str]]]:
    """(output file, command) for the f16 conversion and each quantisation, in order (no importance matrix)."""
    f16 = Path(out) / f"{STEM}-f16.gguf"
    steps = [(f16, [sys.executable, str(Path(checkout) / "convert_hf_to_gguf.py"), str(merged),
                    "--outtype", "f16", "--outfile", str(f16)])]
    quantize = Path(checkout) / "build" / "bin" / "llama-quantize"

    for variant in variants:
        target = Path(out) / f"{STEM}-{variant.lower()}.gguf"
        steps.append((target, [str(quantize), str(f16), str(target), variant]))

    return steps


def convert(merged: Path, checkout: Path, out: Path, manifest: Path, run=subprocess.run) -> dict:
    merge_record = verify_merged(merged)
    verify_llama_cpp(checkout)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    steps = commands(merged, checkout, out)

    for _, command in steps:
        run(command, check=True)

    record = {
        "amendment": "EVAL_PROTOCOL.md, Amendment 2",
        "llama_cpp": {"release": LLAMA_CPP_RELEASE, "commit": LLAMA_CPP_COMMIT},
        "importance_matrix": None,
        "merge": merge_record,
        "converter_libraries": library_versions(),
        # Paths reduced to file names, so the manifest does not depend on the operator's directories.
        "commands": [[Path(part).name if "/" in part else part for part in command] for _, command in steps],
        "gguf": {target.name: {"sha256": sha256_file(target), "bytes": target.stat().st_size} for target, _ in steps},
    }
    Path(manifest).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="stage", required=True)
    m = sub.add_parser("merge", help="merge the chosen adapter into the fp16 base")
    m.add_argument("--checkpoint", required=True, type=Path)
    m.add_argument("--choice", required=True, type=Path)
    m.add_argument("--out", required=True, type=Path)
    m.add_argument("--device", default="cuda")
    c = sub.add_parser("convert", help="convert to f16 GGUF and quantise")
    c.add_argument("--merged", required=True, type=Path)
    c.add_argument("--llama-cpp", required=True, type=Path)
    c.add_argument("--out", required=True, type=Path)
    c.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if args.stage == "merge":
            record = merge(args.checkpoint, args.choice, args.out, args.device)
            print(f"merged into {args.out} on {record['device_name']}; {len(record['files'])} files recorded")
        else:
            record = convert(args.merged, args.llama_cpp, args.out, args.manifest)
            print(json.dumps(record["gguf"], indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
