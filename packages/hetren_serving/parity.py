"""Token parity between the GGUF export and the Hugging Face tokenizer (Amendment 2).

Two checks, both required before the pilot:

- **Vocabulary** (``check_vocabulary``, offline): every token ID of the Hugging
  Face tokenizer (``tokenizer.json``, base vocabulary and added tokens) has the
  same token string in the GGUF file, the BPE merges are identical, special
  tokens are control tokens, every end-of-generation ID of the model's
  ``generation_config.json`` is a control token and the GGUF end-of-sequence
  ID is one of them, the GGUF adds no BOS token, and the pre-tokenizer is
  ``qwen2``. GGUF IDs beyond the Hugging Face vocabulary (padding up to the
  embedding size) must be unused tokens.
- **Round trip** (``roundtrip_problems``, against a running ``llama-server``):
  for each text, the server's tokenisation equals the Hugging Face token IDs,
  and detokenising those IDs gives back the text exactly.

``load_hf_vocabulary`` reads the merged model directory; ``load_gguf_vocabulary``
needs the ``gguf`` package from the pinned llama.cpp checkout (``gguf-py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


# gguf.TokenType
NORMAL, CONTROL, USER_DEFINED, UNUSED = 1, 3, 4, 5
PRE_TOKENIZER = "qwen2"


@dataclass(frozen=True)
class Vocabulary:
    tokens: list[str]                     # index = token ID
    merges: list[str]                     # "left right"
    types: list[int] = field(default_factory=list)   # GGUF token types (empty for Hugging Face)
    special: frozenset[int] = frozenset()            # Hugging Face: added tokens marked special
    added: frozenset[int] = frozenset()              # Hugging Face: every added token
    eos: tuple[int, ...] = ()                        # end-of-generation IDs (HF) or the EOS ID (GGUF)
    add_bos: bool | None = None
    pre: str | None = None


def _merge_text(merge) -> str:
    return merge if isinstance(merge, str) else " ".join(merge)


def load_hf_vocabulary(model_dir: Path) -> Vocabulary:
    model_dir = Path(model_dir)
    spec = json.loads((model_dir / "tokenizer.json").read_text(encoding="utf-8"))
    by_id = {int(i): t for t, i in spec["model"]["vocab"].items()}
    added = {int(t["id"]): t for t in spec.get("added_tokens", [])}
    by_id.update({i: t["content"] for i, t in added.items()})

    if sorted(by_id) != list(range(len(by_id))):
        raise ValueError(f"{model_dir}/tokenizer.json: token IDs are not contiguous from 0")

    generation = json.loads((model_dir / "generation_config.json").read_text(encoding="utf-8"))
    eos = generation["eos_token_id"]
    return Vocabulary(
        tokens=[by_id[i] for i in range(len(by_id))],
        merges=[_merge_text(m) for m in spec["model"]["merges"]],
        special=frozenset(i for i, t in added.items() if t.get("special")),
        added=frozenset(added),
        eos=tuple(eos if isinstance(eos, list) else [eos]),
    )


def load_gguf_vocabulary(path: Path) -> Vocabulary:
    from gguf import GGUFReader

    reader = GGUFReader(str(path))

    def value(key: str, default=None):
        found = reader.get_field(key)
        return default if found is None else found.contents()

    return Vocabulary(
        tokens=list(value("tokenizer.ggml.tokens")),
        merges=list(value("tokenizer.ggml.merges", [])),
        types=[int(t) for t in value("tokenizer.ggml.token_type")],
        eos=(int(value("tokenizer.ggml.eos_token_id")),),
        add_bos=bool(value("tokenizer.ggml.add_bos_token", False)),
        pre=value("tokenizer.ggml.pre"),
    )


def check_vocabulary(hf: Vocabulary, gguf: Vocabulary, limit: int = 20) -> list[str]:
    """Every difference found (at most ``limit`` per kind); an empty list means parity."""
    problems: list[str] = []

    def report(kind: str, items: list[str]) -> None:
        problems.extend(f"{kind}: {item}" for item in items[:limit])

        if len(items) > limit:
            problems.append(f"{kind}: … {len(items) - limit} more")

    if len(gguf.tokens) < len(hf.tokens) or len(gguf.types) != len(gguf.tokens):
        problems.append(f"sizes: {len(hf.tokens)} Hugging Face tokens, {len(gguf.tokens)} GGUF tokens, "
                        f"{len(gguf.types)} GGUF token types")
        return problems

    report("token", [f"{i}: {hf.tokens[i]!r} != {gguf.tokens[i]!r}"
                     for i in range(len(hf.tokens)) if hf.tokens[i] != gguf.tokens[i]])

    if hf.merges != gguf.merges:
        first = next((i for i, (a, b) in enumerate(zip(hf.merges, gguf.merges)) if a != b), min(len(hf.merges), len(gguf.merges)))
        problems.append(f"merges: {len(hf.merges)} Hugging Face, {len(gguf.merges)} GGUF, first difference at {first}")

    expected = {i: CONTROL if i in hf.special else (CONTROL, USER_DEFINED) if i in hf.added else NORMAL
                for i in range(len(hf.tokens))}
    report("type", [f"{i} {hf.tokens[i]!r}: GGUF type {gguf.types[i]}, expected {want}"
                    for i, want in expected.items()
                    if gguf.types[i] not in (want if isinstance(want, tuple) else (want,))])
    report("padding", [f"{i} {gguf.tokens[i]!r}: GGUF type {gguf.types[i]}, expected unused"
                       for i in range(len(hf.tokens), len(gguf.tokens)) if gguf.types[i] != UNUSED])
    report("end of generation", [f"{i}: GGUF type {gguf.types[i]}, expected control"
                                 for i in hf.eos if gguf.types[i] != CONTROL])

    if not set(gguf.eos) <= set(hf.eos):
        problems.append(f"eos: GGUF end-of-sequence {gguf.eos} is not among the model's {hf.eos}")

    if gguf.add_bos:
        problems.append("bos: the GGUF adds a BOS token; the Hugging Face tokenizer does not")

    if gguf.pre != PRE_TOKENIZER:
        problems.append(f"pre-tokenizer: {gguf.pre!r}, expected {PRE_TOKENIZER!r}")

    return problems


def roundtrip_problems(items, server, limit: int = 20) -> tuple[int, list[str]]:
    """(texts checked, problems) for ``items`` of (label, text, Hugging Face token IDs)."""
    problems: list[str] = []
    checked = 0

    for label, text, ids in items:
        checked += 1
        found = []

        if server.tokenize(text) != list(ids):
            found.append("tokenisation differs")

        if server.detokenize(ids) != text:
            found.append("detokenisation differs")

        if found and len(problems) < limit:
            problems.append(f"{label}: {', '.join(found)}")
        elif found:
            problems.append(f"{label}: …")

    return checked, problems


__all__ = ["Vocabulary", "check_vocabulary", "load_gguf_vocabulary", "load_hf_vocabulary", "roundtrip_problems"]
