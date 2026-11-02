"""Greedy generation with a local Hugging Face model (small model baseline).

The protocol fixes the settings, identical for the untrained baseline and
the fine-tuned model: fp16 weights on one GPU (Kaggle T4 has no bf16), the
model's own chat template, greedy decoding, ``max_new_tokens=128``, no
repetition penalty. ``TransformersModel(system, user)`` returns the reply
with what the fp16 smoke test needs: whether every generated step's raw
logits were finite, and whether the reply reached the token limit.

``torch`` and ``transformers`` are imported only when a model is loaded, so
the rest of the baseline code (and its tests) runs without them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


QWEN_MODEL = "Qwen/Qwen3-4B-Instruct-2507"
QWEN_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
MAX_NEW_TOKENS = 128


@dataclass(frozen=True)
class Generation:
    text: str
    prompt_tokens: int
    new_tokens: int
    finite: bool  # every raw logit of every generated step was finite
    at_limit: bool

    def payload(self) -> dict[str, object]:
        return asdict(self)


class TransformersModel:
    def __init__(self, model_id: str = QWEN_MODEL, revision: str = QWEN_REVISION, dtype: str = "float16",
                 device: str = "cuda"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, revision=revision, torch_dtype=getattr(torch, dtype),
        ).to(device).eval()

    def __call__(self, system: str, user: str) -> Generation:
        torch = self.torch
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        ids = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt")
        ids = ids.to(self.model.device)

        with torch.inference_mode():
            out = self.model.generate(
                ids, attention_mask=torch.ones_like(ids),
                do_sample=False, temperature=None, top_p=None, top_k=None, repetition_penalty=1.0,
                max_new_tokens=MAX_NEW_TOKENS, pad_token_id=self.tokenizer.eos_token_id,
                output_logits=True, return_dict_in_generate=True,
            )

        new = out.sequences[0, ids.shape[1]:]
        return Generation(
            text=self.tokenizer.decode(new, skip_special_tokens=True),
            prompt_tokens=int(ids.shape[1]),
            new_tokens=int(new.shape[0]),
            finite=all(bool(torch.isfinite(step).all()) for step in out.logits),
            at_limit=int(new.shape[0]) >= MAX_NEW_TOKENS,
        )


def library_versions() -> dict[str, str]:
    from importlib.metadata import version
    import platform

    names = ("torch", "transformers", "accelerate", "tokenizers", "jsonschema", "openai-agents", "tiktoken")
    versions = {"python": platform.python_version()}

    for name in names:
        try:
            versions[name] = version(name)
        except Exception:
            versions[name] = "not installed"

    return versions


__all__ = [
    "Generation",
    "MAX_NEW_TOKENS",
    "QWEN_MODEL",
    "QWEN_REVISION",
    "TransformersModel",
    "library_versions",
]
