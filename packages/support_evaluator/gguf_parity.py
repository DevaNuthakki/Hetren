"""Token-parity check of a GGUF export before its pilot (EVAL_PROTOCOL.md, Amendment 2).

Runs both checks of ``packages.hetren_serving.parity`` and writes a report:

- the vocabulary of ``--gguf`` against the merged model's tokenizer files
  (``--merged``, the directory written by ``hetren_serving.export merge``);
- the round trip through a running ``llama-server`` (``--server``, serving
  that GGUF) of every validation input and target: for each labelled step of
  every record of the validation split (primaries and partners) of dataset v2
  (tier 1) and dataset v3 (tier 2), the full chat-templated prompt (prompt
  version 2 for the tier, the step's compact evidence) and the step's target
  action as JSON, alone and followed by the end-of-turn token. Each distinct
  text is checked once.

It reads visible records only; no case is prepared, run or scored, and no
model generates anything. Exit 0 only when both checks find nothing.

``python -m packages.support_evaluator.gguf_parity --merged <dir> --gguf <file> --server <url> --out <report.json>``
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from packages.hetren_baselines.prompt import system_prompt, user_message
from packages.hetren_evidence import render_evidence
from packages.support_evaluator.training_data import PROMPT_VERSION, target_text


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    1: ("artifacts/milestone-2/dataset-v2", "docs/milestone-2/splits-v1/validation.txt"),
    2: ("artifacts/milestone-2/dataset-v3", "docs/milestone-2/splits-v2/validation.txt"),
}
END_OF_TURN = "<|im_end|>"


def validation_steps(tier: int, root: Path = REPO_ROOT):
    """(case ID, step index, step) for every labelled step of the tier's validation records, in dataset order."""
    dataset, split = (root / p for p in SOURCES[tier])
    members = set(split.read_text(encoding="utf-8").split())

    with (dataset / "hetren_visible.jsonl").open(encoding="utf-8") as records:
        for line in records:
            record = json.loads(line)

            if record["case_id"] in members:
                for index, step in enumerate(record["steps"]):
                    yield record["case_id"], index, step


def parity_texts(tokenizer, tiers=(1, 2), root: Path = REPO_ROOT):
    """(label, text, Hugging Face token IDs) for every distinct validation prompt and target text."""
    seen: set[str] = set()

    for tier in tiers:
        system = system_prompt(tier, PROMPT_VERSION)

        for case_id, index, step in validation_steps(tier, root):
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": user_message(render_evidence(step["input"]))}]
            prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
            target = target_text(step["target"])
            texts = {"prompt": (prompt, [int(i) for i in tokenizer.apply_chat_template(messages, add_generation_prompt=True)])}

            for kind, text in (("target", target), ("target+eot", target + END_OF_TURN)):
                texts[kind] = (text, [int(i) for i in tokenizer.encode(text, add_special_tokens=False)])

            for kind, (text, ids) in texts.items():
                if text not in seen:
                    seen.add(text)
                    yield f"tier {tier} {case_id} step {index} {kind}", text, ids


def run(merged: Path, gguf: Path, server, tokenizer, root: Path = REPO_ROOT) -> dict:
    from packages.hetren_serving.parity import check_vocabulary, load_gguf_vocabulary, load_hf_vocabulary, roundtrip_problems

    props = server.props()
    served = Path(props.get("model_path", "")).name

    if served != Path(gguf).name:
        raise ValueError(f"the server is serving {served!r}, not {Path(gguf).name!r}")

    vocabulary = check_vocabulary(load_hf_vocabulary(merged), load_gguf_vocabulary(gguf))
    checked, roundtrip = roundtrip_problems(parity_texts(tokenizer, root=root), server)
    return {
        "gguf": Path(gguf).name, "gguf_sha256": hashlib.sha256(Path(gguf).read_bytes()).hexdigest(),
        "server_build": props.get("build_info"),
        "vocabulary_problems": vocabulary, "texts_checked": checked, "roundtrip_problems": roundtrip,
        "parity": not vocabulary and not roundtrip and checked > 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--merged", required=True, type=Path, help="merged model directory (tokenizer files)")
    parser.add_argument("--gguf", required=True, type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8080", help="llama-server serving --gguf")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    from transformers import AutoTokenizer

    from packages.hetren_serving.llama_server import LlamaServer

    report = run(args.merged, args.gguf, LlamaServer(args.server), AutoTokenizer.from_pretrained(str(args.merged)))
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("gguf", "texts_checked", "parity")}, indent=2))
    return 0 if report["parity"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
