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
  python -m packages.hetren_cli serve --host 0.0.0.0 --port 8000   (POST /diagnose; see packages/hetren_cli/api.py)

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


from packages.hetren_cli.diagnosis import CONTEXT_TOKENS, END_OF_GENERATION, TIER1_RECOVERIES  # noqa: F401


CLI_VERSION = "0.4.0rc1"
REPO_ROOT = Path(__file__).resolve().parents[2]
EXIT_OK, EXIT_INPUT, EXIT_RUNTIME, EXIT_REPLY = 0, 2, 3, 4


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
    _model_options(diagnose)
    diagnose.add_argument("--format", choices=("text", "json"), default="text")

    serve = commands.add_parser("serve", help="an HTTP API for diagnoses (POST /diagnose; nothing is applied)")
    _model_options(serve)
    serve.add_argument("--host", default="127.0.0.1", help="listen address (0.0.0.0 in a container)")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--max-queue", type=int, default=8,
                       help="requests that may wait behind the one being diagnosed; more get 503")
    serve.add_argument("--max-body-bytes", type=int, default=1 << 20)

    fetch = commands.add_parser("fetch-model", help="download a validated GGUF and the tokenizer, checking sha256")
    fetch.add_argument("--repo", default=os.environ.get("HETREN_MODEL_REPO"),
                       help="Hugging Face model repository (default $HETREN_MODEL_REPO)")
    fetch.add_argument("--variant", choices=VARIANTS, default="Q4_K_M")
    fetch.add_argument("--revision", default="main")
    fetch.add_argument("--cache", type=Path, help="default $HETREN_CACHE or ~/.cache/hetren")
    fetch.add_argument("--tokenizer-only", action="store_true",
                       help="only the tokenizer (for serve --server-url, where another process serves the GGUF)")

    commands.add_parser("version", help="the CLI's version, commit and validated model files")
    return parser


def _model_options(command: argparse.ArgumentParser) -> None:
    from packages.hetren_cli.models import VARIANTS

    command.add_argument("--variant", choices=VARIANTS, help="the cached GGUF to use (default Q4_K_M)")
    command.add_argument("--model", type=Path, help="a local GGUF file (checked against the export manifest)")
    command.add_argument("--tokenizer", type=Path, help="tokenizer folder (default: tokenizer/ beside the model)")
    command.add_argument("--llama-server", help="the llama-server binary (default $HETREN_LLAMA_SERVER or PATH)")
    command.add_argument("--threads", type=int, help="llama-server -t (default: half the logical CPUs)")
    command.add_argument("--server-url", help="use this running llama-server instead of starting one")


def load_model(args: argparse.Namespace, tokenizer_loader: Callable = load_tokenizer) -> tuple[dict, object]:
    """(model_info, tokenizer) for ``--model``/``--variant`` or ``--server-url``; raises ``ModelError`` or
    ``RuntimeFailure``. The CPU check runs first, unless an external server does the work."""
    from packages.hetren_cli.models import DEFAULT_VARIANT, ModelError, cache_dir, check_tokenizer, gguf_files, resolve
    from packages.hetren_cli.runtime import check_cpu

    if not args.server_url:
        check_cpu()  # before the model: the image's llama-server needs AVX2, FMA and F16C
        model_info = resolve(args.model, args.tokenizer, args.variant)
    else:
        if args.model is not None:
            raise ModelError("give --model or --server-url, not both")

        variant = args.variant or DEFAULT_VARIANT
        tokenizer_dir = args.tokenizer or cache_dir() / "tokenizer"
        check_tokenizer(tokenizer_dir)
        model_info = {"variant": variant, "gguf": gguf_files()[variant]["file"], "gguf_sha256": None,
                      "tokenizer": str(tokenizer_dir)}

    return model_info, tokenizer_loader(model_info["tokenizer"])


def diagnose(args: argparse.Namespace, out=None, err=None, *,
             tokenizer_loader: Callable = load_tokenizer, local_server=None, build=None) -> int:
    from packages.hetren_cli import report as reports
    from packages.hetren_cli.diagnosis import Diagnoser
    from packages.hetren_cli.inputs import InputRejected, load_input
    from packages.hetren_cli.models import ModelError
    from packages.hetren_cli.runtime import LocalServer, RuntimeFailure, build_info, check_served, default_threads, find_binary
    from packages.hetren_serving.llama_server import LlamaServer

    out, err = out or sys.stdout, err or sys.stderr
    local_server = local_server or LocalServer
    build = build or build_info

    try:
        compact = load_input(args.record, args.compact)
    except InputRejected as exc:
        print(f"hetren: input rejected: {exc}", file=err)
        return EXIT_INPUT

    try:
        model_info, tokenizer = load_model(args, tokenizer_loader)
    except (ModelError, RuntimeFailure) as exc:
        print(f"hetren: {exc}", file=err)
        return EXIT_RUNTIME

    diagnoser = Diagnoser(tokenizer, model_info, CLI_VERSION, code_commit())

    try:
        messages = diagnoser.prompt(compact)
    except InputRejected as exc:
        print(f"hetren: input rejected: {exc}", file=err)
        return EXIT_INPUT

    def run(server: LlamaServer, server_info: dict[str, object]) -> int:
        code, record = diagnoser.run(compact, server, server_info, messages)
        out.write(reports.as_json(record) if args.format == "json" else reports.text(record))
        return EXIT_OK if code == EXIT_OK else EXIT_REPLY

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
        result = fetch(args.repo, args.variant, args.revision, args.cache, log=lambda m: print(m, file=out),
                       tokenizer_only=args.tokenizer_only)
    except (ModelError, OSError) as exc:
        print(f"hetren: {exc}", file=err)
        return EXIT_RUNTIME

    if args.tokenizer_only:
        print(f"tokenizer ready: {result['tokenizer']}", file=out)
    else:
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

    if args.command == "serve":
        from packages.hetren_cli.api import serve

        return serve(args)

    return version()


__all__ = ["CLI_VERSION", "EXIT_INPUT", "EXIT_OK", "EXIT_REPLY", "EXIT_RUNTIME", "code_commit", "diagnose",
           "fetch_model", "load_model", "main", "version"]
