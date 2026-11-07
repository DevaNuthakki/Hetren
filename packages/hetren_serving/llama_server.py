"""A policy model served by ``llama-server`` (EVAL_PROTOCOL.md, Amendment 2, "Runtime and decoding").

``LlamaServerModel(system, user)`` is a drop-in for
``packages.hetren_baselines.local_model.TransformersModel``:

- the prompt is rendered with the Hugging Face chat template and tokenizer at
  the pinned revision, exactly as the fp16 runs, and sent to ``/completion``
  as **token IDs** (a token-array prompt gets no BOS from the server), so
  tokenisation equals the fp16 runs by construction;
- decoding is greedy (only the ``top_k`` sampler, k = 1, temperature 0), at
  most 128 new tokens, no repetition, presence, frequency or DRY penalty;
  generation ends at the model's end-of-generation token;
- the reply is the generated token IDs decoded by the same tokenizer with
  ``skip_special_tokens=True``, as ``TransformersModel`` decodes.

``finite`` is the closest check the server allows to the fp16 runs' raw-logit
check: every generated token's reported log-probability (``n_probs`` 1) is a
finite number. ``new_tokens`` counts the token IDs the server returns, and
``stop_type`` records why generation ended (``eos`` or ``limit``);
``token_ids`` are the generated IDs and ``prompt_ms``, ``predicted_ms``,
``prompt_n`` and ``predicted_n`` the server's own timings, for the
throughput pilot.

Only the standard library is used for HTTP; the tokenizer is passed in.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import time
import urllib.request

from packages.hetren_baselines.local_model import MAX_NEW_TOKENS, Generation


@dataclass(frozen=True)
class DecodingSettings:
    """Amendment 2's settings; ``cache_prompt`` is fixed by the pilot's caching rule before the validation run."""

    cache_prompt: bool
    n_predict: int = MAX_NEW_TOKENS

    def payload(self, prompt_ids: list[int]) -> dict[str, object]:
        return {
            "prompt": list(prompt_ids),
            "n_predict": self.n_predict,
            "samplers": ["top_k"],
            "top_k": 1,
            "temperature": 0.0,
            "repeat_penalty": 1.0,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "dry_multiplier": 0.0,
            "ignore_eos": False,
            "cache_prompt": self.cache_prompt,
            "n_probs": 1,
            "return_tokens": True,
            "stream": False,
            "id_slot": 0,
        }


@dataclass(frozen=True)
class LlamaGeneration(Generation):
    stop_type: str = ""
    probabilities: int = 0  # entries in completion_probabilities (compared with new_tokens by the pilot)
    tokens_cached: int = 0
    tokens_evaluated: int = 0
    server_seconds: float = 0.0
    token_ids: tuple[int, ...] = ()  # the generated IDs as returned (the pilot compares repeats on them)
    prompt_ms: float = 0.0  # the server's own timings: prompt evaluation and generation
    predicted_ms: float = 0.0
    prompt_n: int = 0  # prompt tokens the server evaluated (fewer than prompt_tokens when the cache was used)
    predicted_n: int = 0


class LlamaServer:
    """A minimal JSON client for one ``llama-server`` (default ``http://127.0.0.1:8080``)."""

    def __init__(self, url: str = "http://127.0.0.1:8080", timeout: float = 600.0):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def request(self, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.url + path, data=data, method="GET" if body is None else "POST",
                                         headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def completion(self, body: dict) -> dict:
        return self.request("/completion", body)

    def tokenize(self, text: str) -> list[int]:
        return self.request("/tokenize", {"content": text, "add_special": False, "parse_special": True})["tokens"]

    def detokenize(self, tokens: list[int]) -> str:
        return self.request("/detokenize", {"tokens": list(tokens)})["content"]

    def props(self) -> dict:
        return self.request("/props")


def _finite(probabilities: list[dict]) -> bool:
    values = [p.get("logprob") for p in probabilities]
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)


class LlamaServerModel:
    def __init__(self, tokenizer, server: LlamaServer, settings: DecodingSettings):
        self.tokenizer = tokenizer
        self.server = server
        self.settings = settings

    def prompt_ids(self, system: str, user: str) -> list[int]:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return [int(i) for i in self.tokenizer.apply_chat_template(messages, add_generation_prompt=True)]

    def __call__(self, system: str, user: str) -> LlamaGeneration:
        ids = self.prompt_ids(system, user)
        started = time.perf_counter()
        response = self.server.completion(self.settings.payload(ids))
        seconds = time.perf_counter() - started
        tokens = response.get("tokens")
        stop_type = response.get("stop_type")

        if not isinstance(tokens, list) or stop_type not in ("eos", "limit"):
            raise ValueError(f"unexpected llama-server response: stop_type {stop_type!r}, tokens {type(tokens).__name__}")

        probabilities = response.get("completion_probabilities") or []

        if tokens and not probabilities:
            raise ValueError("llama-server returned no token probabilities (n_probs was 1)")

        timings = response.get("timings") or {}

        return LlamaGeneration(
            text=self.tokenizer.decode(tokens, skip_special_tokens=True),
            prompt_tokens=len(ids),
            new_tokens=len(tokens),
            finite=_finite(probabilities),
            at_limit=stop_type == "limit",
            stop_type=stop_type,
            probabilities=len(probabilities),
            tokens_cached=int(response.get("tokens_cached", 0)),
            tokens_evaluated=int(response.get("tokens_evaluated", 0)),
            server_seconds=round(seconds, 3),
            token_ids=tuple(int(t) for t in tokens),
            prompt_ms=float(timings.get("prompt_ms", 0.0)),
            predicted_ms=float(timings.get("predicted_ms", 0.0)),
            prompt_n=int(timings.get("prompt_n", 0)),
            predicted_n=int(timings.get("predicted_n", 0)),
        )


__all__ = ["DecodingSettings", "LlamaGeneration", "LlamaServer", "LlamaServerModel"]
