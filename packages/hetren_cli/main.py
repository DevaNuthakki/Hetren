"""hetren: offline diagnosis of agent runs recorded with Hetren's OpenAI Agents SDK integration.

The model was trained only on Hetren's synthetic support workflow (read_ticket, lookup_account,
route_ticket); it is not a general agent-trace diagnoser. The CLI handles single-recovery (tier 1)
support runs only: two-step recovery is not supported here, although the model was validated on it.
A diagnosis is one policy step on the run's evidence, exactly as the GGUF validation ran it (Amendment 2:
the tier 1 prompt, version 2; greedy decoding; llama-server on the CPU). Its result is a decision, a
proposed recovery, or a probe the model would need; nothing is ever applied.

  python -m packages.hetren_cli diagnose --record run.json
  python -m packages.hetren_cli diagnose --compact evidence.json --format json
  python -m packages.hetren_cli fetch-model --repo <huggingface repo> [--variant Q8_0]

Exit status: 0 a diagnosis was made; 2 the input was rejected; 3 the model or llama-server failed;
4 the model's reply was not a valid action.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


CLI_VERSION = "0.4.0.dev0"
REPO_ROOT = Path(__file__).resolve().parents[2]
EXIT_OK, EXIT_INPUT, EXIT_RUNTIME, EXIT_REPLY = 0, 2, 3, 4
CONTEXT_TOKENS = 4096  # Amendment 2's -c
END_OF_GENERATION = {151645, 151643}  # <|im_end|>, <|endoftext|> (gguf_check.END_OF_GENERATION)
TIER1_RECOVERIES = 1  # one step on a recorded run: the tier 1 prompt (no recovery is ever applied)


def code_commit(root: Path = REPO_ROOT) -> str | None:
    """``$HETREN_COMMIT`` (set in the Docker image), else ``git rev-parse HEAD``, else None."""
    if os.environ.get("HETREN_COMMIT"):
        return os.environ["HETREN_COMMIT"]

    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True,
                              text=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def load_tokenizer(directory: str):
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")  # no "PyTorch not found" notice: only the tokenizer is used

    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        from packages.hetren_cli.models import ModelError

        raise ModelError("transformers is not installed: pip install -r requirements-cli.txt") from exc

    return AutoTokenizer.from_pretrained(directory)


def _parser() -> argparse.ArgumentParser:
    from packages.hetren_cli.models import VARIANTS

    parser = argparse.ArgumentParser(prog="hetren", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    diagnose = commands.add_parser("diagnose", help="diagnose one recorded run (nothing is applied)")
    source = diagnose.add_mutually_exclusive_group(required=True)
    source.add_argument("--record", type=Path, help="an AgentRunRecord evidence payload (JSON)")
    source.add_argument("--compact", type=Path, help="compact-evidence-v1 JSON, or one hetren_visible.jsonl line")
    diagnose.add_argument("--variant", choices=VARIANTS, help="the cached GGUF to use (default Q4_K_M)")
    diagnose.add_argument("--model", type=Path, help="a local GGUF file (checked against the export manifest)")
    diagnose.add_argument("--tokenizer", type=Path, help="tokenizer folder (default: tokenizer/ beside the model)")
    diagnose.add_argument("--llama-server", help="the llama-server binary (default $HETREN_LLAMA_SERVER or PATH)")
    diagnose.add_argument("--threads", type=int, help="llama-server -t (default: half the logical CPUs)")
    diagnose.add_argument("--server-url", help="use this running llama-server instead of starting one")
    diagnose.add_argument("--format", choices=("text", "json"), default="text")

    fetch = commands.add_parser("fetch-model", help="download a validated GGUF and the tokenizer, checking sha256")
    fetch.add_argument("--repo", default=os.environ.get("HETREN_MODEL_REPO"),
                       help="Hugging Face model repository (default $HETREN_MODEL_REPO)")
    fetch.add_argument("--variant", choices=VARIANTS, default="Q4_K_M")
    fetch.add_argument("--revision", default="main")
    fetch.add_argument("--cache", type=Path, help="default $HETREN_CACHE or ~/.cache/hetren")

    commands.add_parser("version", help="the CLI's version, commit and validated model files")
    return parser


def _input_summary(compact: dict[str, Any]) -> dict[str, object]:
    return {"format": compact["format"], "task": compact["task"], "status": compact["run"]["status"],
            "tool_calls": len(compact["steps"]), "probes": len(compact["probes"])}


def diagnose(args: argparse.Namespace, out=None, err=None, *,
             tokenizer_loader: Callable = load_tokenizer, local_server=None, build=None) -> int:
    from packages.action_space import parse_action
    from packages.hetren_baselines.local_model import MAX_NEW_TOKENS
    from packages.hetren_baselines.prompt import PROMPT_VERSION, action_text, system_prompt, user_message
    from packages.hetren_cli import report as reports
    from packages.hetren_cli.inputs import InputRejected, load_input
    from packages.hetren_cli.models import DEFAULT_VARIANT, ModelError, cache_dir, check_tokenizer, gguf_files, resolve
    from packages.hetren_cli.runtime import (LocalServer, RuntimeFailure, build_info, check_served, default_threads,
                                             find_binary)
    from packages.hetren_evidence import render_evidence
    from packages.hetren_serving.llama_server import DecodingSettings, LlamaServer, LlamaServerModel

    out, err = out or sys.stdout, err or sys.stderr
    local_server = local_server or LocalServer
    build = build or build_info

    try:
        compact = load_input(args.record, args.compact)
    except InputRejected as exc:
        print(f"hetren: input rejected: {exc}", file=err)
        return EXIT_INPUT

    try:
        if args.server_url:
            if args.model is not None:
                raise ModelError("give --model or --server-url, not both")

            variant = args.variant or DEFAULT_VARIANT
            tokenizer_dir = args.tokenizer or cache_dir() / "tokenizer"
            check_tokenizer(tokenizer_dir)
            model_info = {"variant": variant, "gguf": gguf_files()[variant]["file"], "gguf_sha256": None,
                          "tokenizer": str(tokenizer_dir)}
        else:
            model_info = resolve(args.model, args.tokenizer, args.variant)

        tokenizer = tokenizer_loader(model_info["tokenizer"])
    except ModelError as exc:
        print(f"hetren: {exc}", file=err)
        return EXIT_RUNTIME

    settings = DecodingSettings(cache_prompt=True)  # the validation run's setting
    system = system_prompt(TIER1_RECOVERIES)
    user = user_message(render_evidence(compact))
    prompt_tokens = len(LlamaServerModel(tokenizer, None, settings).prompt_ids(system, user))

    if prompt_tokens + MAX_NEW_TOKENS > CONTEXT_TOKENS:
        print(f"hetren: input rejected: the prompt is {prompt_tokens} tokens; with {MAX_NEW_TOKENS} reply tokens "
              f"it exceeds the {CONTEXT_TOKENS}-token context the model was validated with", file=err)
        return EXIT_INPUT

    def run(server: LlamaServer, server_info: dict[str, object]) -> int:
        generation = LlamaServerModel(tokenizer, server, settings)(system, user)

        try:
            result = reports.summary(parse_action(action_text(generation.text)).canonical_payload())
            code = EXIT_OK
        except Exception as exc:  # the episode loop's invalid_action
            result = {"outcome": "invalid_reply", "error": f"{type(exc).__name__}: {exc}", "reply": generation.text}
            code = EXIT_REPLY

        other_stop = generation.stop_type == "eos" and bool(generation.token_ids) \
            and generation.token_ids[-1] not in END_OF_GENERATION
        record = {
            "cli_version": CLI_VERSION, "code_commit": code_commit(), "prompt_version": PROMPT_VERSION,
            "input": _input_summary(compact), "result": result,
            "model": {k: model_info[k] for k in ("variant", "gguf", "gguf_sha256")},
            "server": server_info,
            "generation": {"prompt_tokens": generation.prompt_tokens, "new_tokens": generation.new_tokens,
                           "stop_type": generation.stop_type, "finite": generation.finite,
                           "seconds": generation.server_seconds, "reply": generation.text},
            "stopped_on_other_token": other_stop,
        }
        out.write(reports.as_json(record) if args.format == "json" else reports.text(record))
        return code

    try:
        if args.server_url:
            server = LlamaServer(args.server_url)
            check_served(server, Path(model_info["gguf"]).name)
            return run(server, {"url": args.server_url, "commit": None, "validated_build": False, "threads": None})

        binary = find_binary(args.llama_server)
        threads = args.threads or default_threads()
        info = build(binary)

        with local_server(binary, model_info["gguf"], threads) as running:
            return run(LlamaServer(running.url), {**info, "threads": threads,
                                                  "command": running.command[1:]})
    except (RuntimeFailure, ModelError) as exc:
        print(f"hetren: {exc}", file=err)
        return EXIT_RUNTIME
    except (OSError, ValueError) as exc:  # connection errors, unexpected server responses
        print(f"hetren: llama-server failed: {type(exc).__name__}: {exc}", file=err)
        return EXIT_RUNTIME


def fetch_model(args: argparse.Namespace, out=None, err=None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    from packages.hetren_cli.models import ModelError, fetch

    if not args.repo:
        print("hetren: give --repo (or set HETREN_MODEL_REPO): the Hugging Face model repository", file=err)
        return EXIT_INPUT

    try:
        result = fetch(args.repo, args.variant, args.revision, args.cache, log=lambda m: print(m, file=out))
    except (ModelError, OSError) as exc:
        print(f"hetren: {exc}", file=err)
        return EXIT_RUNTIME

    print(f"{result['variant']} ready: {result['gguf']} (sha256 {result['gguf_sha256']}), tokenizer "
          f"{result['tokenizer']}", file=out)
    return EXIT_OK


def version(out=None) -> int:
    out = out or sys.stdout
    from packages.hetren_cli.models import gguf_files, manifest

    print(f"hetren {CLI_VERSION} (commit {code_commit() or 'unknown'})", file=out)
    print(f"llama.cpp validated build: {manifest()['llama_cpp']['commit']}", file=out)

    for variant, entry in gguf_files().items():
        print(f"{variant}: {entry['file']} sha256 {entry['sha256']}", file=out)

    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "diagnose":
        return diagnose(args)

    if args.command == "fetch-model":
        return fetch_model(args)

    return version()


__all__ = ["CLI_VERSION", "EXIT_INPUT", "EXIT_OK", "EXIT_REPLY", "EXIT_RUNTIME", "code_commit", "diagnose",
           "fetch_model", "main", "version"]
