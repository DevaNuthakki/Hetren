"""One diagnosis, shared by ``hetren diagnose`` and ``hetren serve``: the tier 1 prompt (version 2) on a checked
compact input, one greedy generation on ``llama-server``, and the report record.

``Diagnoser`` holds what does not change between diagnoses (the tokenizer, the model's identity, the decoding
settings), so the API builds it once and the CLI once per process; the record is the same either way.
"""

from __future__ import annotations

from typing import Any

from packages.hetren_cli.inputs import InputRejected


CONTEXT_TOKENS = 4096  # Amendment 2's -c
END_OF_GENERATION = {151645, 151643}  # <|im_end|>, <|endoftext|> (gguf_check.END_OF_GENERATION)
TIER1_RECOVERIES = 1  # one step on a recorded run: the tier 1 prompt (no recovery is ever applied)
OK, REPLY_INVALID = 0, 4  # the CLI's exit codes for a diagnosis and for a reply that is not an action


def input_summary(compact: dict[str, Any]) -> dict[str, object]:
    return {"format": compact["format"], "task": compact["task"], "status": compact["run"]["status"],
            "tool_calls": len(compact["steps"]), "probes": len(compact["probes"])}


class Diagnoser:
    def __init__(self, tokenizer, model_info: dict[str, object], cli_version: str, code_commit: str | None):
        from packages.hetren_serving.llama_server import DecodingSettings

        self.tokenizer, self.model_info = tokenizer, model_info
        self.cli_version, self.code_commit = cli_version, code_commit
        self.settings = DecodingSettings(cache_prompt=True)  # the validation run's setting

    def prompt(self, compact: dict[str, Any]) -> tuple[str, str]:
        """The system and user messages; ``InputRejected`` if the prompt and a full reply exceed the context."""
        from packages.hetren_baselines.local_model import MAX_NEW_TOKENS
        from packages.hetren_baselines.prompt import system_prompt, user_message
        from packages.hetren_evidence import render_evidence
        from packages.hetren_serving.llama_server import LlamaServerModel

        system, user = system_prompt(TIER1_RECOVERIES), user_message(render_evidence(compact))
        tokens = len(LlamaServerModel(self.tokenizer, None, self.settings).prompt_ids(system, user))

        if tokens + MAX_NEW_TOKENS > CONTEXT_TOKENS:
            raise InputRejected(f"the prompt is {tokens} tokens; with {MAX_NEW_TOKENS} reply tokens it exceeds the "
                                f"{CONTEXT_TOKENS}-token context the model was validated with")

        return system, user

    def run(self, compact: dict[str, Any], server, server_info: dict[str, object],
            messages: tuple[str, str] | None = None) -> tuple[int, dict[str, object]]:
        """(``OK`` or ``REPLY_INVALID``, the report record). Server failures propagate (``OSError``, ``ValueError``)."""
        from packages.action_space import parse_action
        from packages.hetren_baselines.prompt import PROMPT_VERSION, action_text
        from packages.hetren_cli import report as reports
        from packages.hetren_serving.llama_server import LlamaServerModel

        system, user = messages or self.prompt(compact)
        generation = LlamaServerModel(self.tokenizer, server, self.settings)(system, user)

        try:
            result = reports.summary(parse_action(action_text(generation.text)).canonical_payload())
            code = OK
        except Exception as exc:  # the episode loop's invalid_action
            result = {"outcome": "invalid_reply", "error": f"{type(exc).__name__}: {exc}", "reply": generation.text}
            code = REPLY_INVALID

        other_stop = generation.stop_type == "eos" and bool(generation.token_ids) \
            and generation.token_ids[-1] not in END_OF_GENERATION
        record = {
            "cli_version": self.cli_version, "code_commit": self.code_commit, "prompt_version": PROMPT_VERSION,
            "input": input_summary(compact), "result": result,
            "model": {k: self.model_info[k] for k in ("variant", "gguf", "gguf_sha256")},
            "server": server_info,
            "generation": {"prompt_tokens": generation.prompt_tokens, "new_tokens": generation.new_tokens,
                           "stop_type": generation.stop_type, "finite": generation.finite,
                           "seconds": generation.server_seconds, "reply": generation.text},
            "stopped_on_other_token": other_stop,
        }
        return code, record


__all__ = ["CONTEXT_TOKENS", "Diagnoser", "END_OF_GENERATION", "OK", "REPLY_INVALID", "TIER1_RECOVERIES",
           "input_summary"]
