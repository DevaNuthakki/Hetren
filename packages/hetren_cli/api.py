"""``hetren serve``: the CLI's diagnosis as an HTTP API (Milestone 4, step 6), standard library only.

Same scope, inputs, model checks and record as ``hetren diagnose``: single-recovery (tier 1) runs of Hetren's
synthetic support workflow, one greedy step with the validated GGUF; nothing is ever applied.

- ``POST /diagnose``: a JSON object with exactly one of ``record`` (an AgentRunRecord evidence payload) or
  ``compact`` (compact-evidence-v1, or one ``hetren_visible.jsonl`` line). Replies:
  - 200: the diagnosis, the record that ``hetren diagnose --format json`` writes;
  - 400: the input was rejected (``message`` says why, as the CLI's exit 2);
  - 502: the model's reply was not a valid action (the record is included, as the CLI's exit 4);
  - 500: llama-server failed;
  - 503: not ready, draining, or the queue is full (``Retry-After``);
  - 411, 413, 404 and 405 for a missing or too large body, an unknown path or a wrong method.
- ``GET /healthz``: 200 while the process and its llama-server are alive (also while the model loads).
- ``GET /readyz``: 200 once the model is loaded and llama-server is serving it; 503 otherwise.
- ``GET /metrics``: Prometheus text format.

One diagnosis at a time (llama.cpp on the CPU gains nothing from concurrent requests on the same cores);
``--max-queue`` more may wait, and the rest get 503 at once. The model loads in the background so that
``/healthz`` answers during the load; if loading fails the process exits with status 3 (the CLI's), so
Kubernetes restarts it and ``kubectl logs --previous`` shows why. On SIGTERM it stops being ready, lets the
running and queued diagnoses finish, then exits. Request logs (one JSON line each, on stderr) never contain
the input.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import signal
import sys
import threading
import time
from typing import Any, Callable


BUCKETS = (5, 10, 20, 30, 45, 60, 90, 120, 180, 300, 600)  # seconds; a warm CPU diagnosis is 10-60 s
RETRY_AFTER_SECONDS = 30
DRAIN_SECONDS = 600.0  # at most one diagnosis plus the queue; Kubernetes' grace period bounds it too
OUTCOMES = ("decision", "proposed_recovery", "needs_probe", "invalid_reply")


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.responses: dict[int, int] = {}
        self.outcomes = dict.fromkeys(OUTCOMES, 0)
        self.rejected: dict[str, int] = {}
        self.request_buckets = [0] * (len(BUCKETS) + 1)
        self.request_sum = 0.0
        self.generation_sum, self.generation_count = 0.0, 0

    def response(self, status: int, seconds: float | None = None) -> None:
        with self.lock:
            self.responses[status] = self.responses.get(status, 0) + 1

            if seconds is not None:
                index = next((i for i, b in enumerate(BUCKETS) if seconds <= b), len(BUCKETS))
                self.request_buckets[index] += 1
                self.request_sum += seconds

    def reject(self, reason: str) -> None:
        with self.lock:
            self.rejected[reason] = self.rejected.get(reason, 0) + 1

    def diagnosis(self, outcome: str, generation_seconds: float) -> None:
        with self.lock:
            self.outcomes[outcome] = self.outcomes.get(outcome, 0) + 1
            self.generation_sum += generation_seconds
            self.generation_count += 1

    def render(self, gauges: dict[str, float], info: dict[str, str]) -> str:
        with self.lock:
            lines = []

            def metric(name: str, kind: str, text: str, samples: list[tuple[str, float]]) -> None:
                lines.extend([f"# HELP {name} {text}", f"# TYPE {name} {kind}"])
                lines.extend(f"{name}{labels} {value:g}" for labels, value in samples)

            labels = ",".join(f'{k}="{v}"' for k, v in sorted(info.items()))
            metric("hetren_info", "gauge", "The served model and build.", [(f"{{{labels}}}", 1)])

            for name, (text, value) in gauges.items():
                metric(f"hetren_{name}", "gauge", text, [("", value)])

            metric("hetren_http_responses_total", "counter", "HTTP responses to /diagnose by status.",
                   [(f'{{code="{c}"}}', n) for c, n in sorted(self.responses.items())])
            metric("hetren_diagnoses_total", "counter", "Diagnoses by outcome.",
                   [(f'{{outcome="{o}"}}', n) for o, n in sorted(self.outcomes.items())])
            metric("hetren_rejected_total", "counter", "Requests refused before a diagnosis, by reason.",
                   [(f'{{reason="{r}"}}', n) for r, n in sorted(self.rejected.items())])

            cumulative, samples = 0, []

            for bound, count in zip([*map(str, BUCKETS), "+Inf"], self.request_buckets):
                cumulative += count
                samples.append((f'_bucket{{le="{bound}"}}', cumulative))

            samples += [("_sum", round(self.request_sum, 3)), ("_count", cumulative)]
            lines.extend(["# HELP hetren_request_seconds /diagnose time, queueing included.",
                          "# TYPE hetren_request_seconds histogram"])
            lines.extend(f"hetren_request_seconds{suffix} {value:g}" for suffix, value in samples)
            metric("hetren_generation_seconds_sum", "counter", "llama-server time of the diagnoses.",
                   [("", round(self.generation_sum, 3))])
            metric("hetren_generation_seconds_count", "counter", "Diagnoses timed.", [("", self.generation_count)])
            return "\n".join(lines) + "\n"


class Service:
    """The model, its llama-server and the request queue; ``state`` is loading, ready, failed or draining."""

    def __init__(self, args: argparse.Namespace, *, tokenizer_loader: Callable | None = None,
                 local_server=None, build=None, log=None):
        self.args = args
        self.tokenizer_loader, self.local_server_class, self.build = tokenizer_loader, local_server, build
        self.log = log or (lambda entry: print(json.dumps(entry, sort_keys=True), file=sys.stderr, flush=True))
        self.state, self.reason = "loading", "the model is loading"
        self.metrics = Metrics()
        self.work = threading.Lock()  # one diagnosis at a time
        self.slots = threading.BoundedSemaphore(args.max_queue + 1)
        self.counts_lock = threading.Lock()
        self.waiting = self.running = 0
        self.diagnoser = self.server = self.server_info = self.local = None
        self.info: dict[str, str] = {}
        self.loaded = threading.Event()

    # --- loading -------------------------------------------------------------------------------------------

    def load(self) -> None:
        """Load the model and start (or check) llama-server; ``failed`` with the reason if anything stops it."""
        from packages.hetren_cli import main as cli
        from packages.hetren_cli.diagnosis import Diagnoser
        from packages.hetren_cli.models import ModelError
        from packages.hetren_cli.runtime import (LocalServer, RuntimeFailure, build_info, check_served,
                                                 default_threads, find_binary)
        from packages.hetren_serving.llama_server import LlamaServer
        from pathlib import Path

        started = time.perf_counter()

        try:
            model_info, tokenizer = cli.load_model(self.args, self.tokenizer_loader or cli.load_tokenizer)

            if self.args.server_url:
                self.server = LlamaServer(self.args.server_url)
                check_served(self.server, Path(model_info["gguf"]).name)
                self.server_info = {"url": self.args.server_url, "commit": None, "validated_build": False,
                                    "threads": None}
            else:
                binary = find_binary(self.args.llama_server)
                threads = self.args.threads or default_threads()
                info = (self.build or build_info)(binary)
                self.local = (self.local_server_class or LocalServer)(binary, model_info["gguf"], threads)
                self.local.__enter__()
                self.server = LlamaServer(self.local.url)
                self.server_info = {**info, "threads": threads, "command": self.local.command[1:]}

            self.diagnoser = Diagnoser(tokenizer, model_info, cli.CLI_VERSION, cli.code_commit())
            self.info = {"variant": str(model_info["variant"]), "gguf_sha256": str(model_info["gguf_sha256"] or ""),
                         "llama_cpp_commit": str(self.server_info.get("commit") or ""), "cli_version": cli.CLI_VERSION}
        except (ModelError, RuntimeFailure, OSError, ValueError) as exc:
            self.state, self.reason = "failed", str(exc)
            self.log({"event": "load_failed", "reason": str(exc)})
        else:
            if self.state == "loading":
                self.state, self.reason = "ready", "ready"

            self.log({"event": "ready", "seconds": round(time.perf_counter() - started, 1), **self.info,
                      "server": {k: v for k, v in self.server_info.items() if k != "command"}})
        finally:
            self.loaded.set()

    def stop(self) -> None:
        if self.local is not None:
            self.local.__exit__(None, None, None)
            self.local = None

    # --- state ---------------------------------------------------------------------------------------------

    def llama_alive(self) -> bool:
        process = getattr(self.local, "process", None)
        return process is None or process.poll() is None

    def healthy(self) -> bool:
        return self.state != "failed" and self.llama_alive()

    def ready(self) -> bool:
        return self.state == "ready" and self.llama_alive()

    def gauges(self) -> dict[str, tuple[str, float]]:
        with self.counts_lock:
            waiting, running = self.waiting, self.running

        return {"ready": ("1 when /readyz is 200.", 1.0 if self.ready() else 0.0),
                "queue_waiting": ("Requests waiting for the model.", waiting),
                "in_flight": ("Diagnoses running (at most 1).", running),
                "queue_capacity": ("Requests that may wait.", self.args.max_queue)}

    def idle(self) -> bool:
        with self.counts_lock:
            return self.waiting == 0 and self.running == 0

    # --- requests ------------------------------------------------------------------------------------------

    def diagnose(self, body: bytes) -> tuple[int, dict[str, Any]]:
        from packages.hetren_cli.diagnosis import OK
        from packages.hetren_cli.inputs import InputRejected, from_compact, from_record

        if not self.ready():
            self.metrics.reject("not_ready")
            return 503, {"error": "not_ready", "message": self.reason if self.state != "ready" else
                         "llama-server is not running"}

        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.metrics.reject("input")
            return 400, {"error": "input_rejected", "message": f"the body is not JSON: {exc}"}

        try:
            if not isinstance(value, dict) or len(value) != 1 or next(iter(value)) not in ("record", "compact"):
                raise InputRejected('the body must be a JSON object with exactly one of "record" (an '
                                    'AgentRunRecord evidence payload) or "compact" (compact-evidence-v1)')

            compact = from_record(value["record"]) if "record" in value else from_compact(value["compact"])
            messages = self.diagnoser.prompt(compact)
        except InputRejected as exc:
            self.metrics.reject("input")
            return 400, {"error": "input_rejected", "message": str(exc)}

        if not self.slots.acquire(blocking=False):
            self.metrics.reject("queue_full")
            return 503, {"error": "queue_full", "message": f"{self.args.max_queue} requests are already waiting"}

        try:
            with self.counts_lock:
                self.waiting += 1

            with self.work:
                with self.counts_lock:
                    self.waiting -= 1
                    self.running += 1

                try:
                    code, record = self.diagnoser.run(compact, self.server, self.server_info, messages)
                finally:
                    with self.counts_lock:
                        self.running -= 1
        except (OSError, ValueError) as exc:
            return 500, {"error": "llama_server_failed", "message": f"{type(exc).__name__}: {exc}"}
        finally:
            self.slots.release()

        self.metrics.diagnosis(record["result"]["outcome"], record["generation"]["seconds"])
        return (200, record) if code == OK else (502, record)


def handler_for(service: Service, max_body: int):
    class Handler(BaseHTTPRequestHandler):
        server_version = "hetren"
        sys_version = ""
        timeout = 60  # reading a request; a diagnosis itself does no socket I/O

        def log_message(self, *args) -> None:  # request logs are the service's JSON lines
            pass

        def reply(self, status: int, body: dict | str, content_type: str = "application/json") -> None:
            data = (body if isinstance(body, str) else json.dumps(body, sort_keys=True) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))

            if status == 503:
                self.send_header("Retry-After", str(RETRY_AFTER_SECONDS))

            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/healthz":
                healthy = service.healthy()
                self.reply(200 if healthy else 503, {"status": "ok" if healthy else "unhealthy",
                                                     "state": service.state})
            elif self.path == "/readyz":
                ready = service.ready()
                self.reply(200 if ready else 503, {"status": "ready" if ready else "not_ready",
                                                   "state": service.state, "reason": service.reason})
            elif self.path == "/metrics":
                self.reply(200, service.metrics.render(service.gauges(), service.info),
                           "text/plain; version=0.0.4; charset=utf-8")
            elif self.path == "/diagnose":
                self.reply(405, {"error": "method_not_allowed", "message": "POST /diagnose"})
            else:
                self.reply(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if self.path != "/diagnose":
                self.reply(404 if self.path not in ("/healthz", "/readyz", "/metrics") else 405,
                           {"error": "not_found"})
                return

            started = time.perf_counter()
            length = self.headers.get("Content-Length")

            if length is None or not length.isdigit():
                status, body = 411, {"error": "length_required"}
                service.metrics.reject("body")
            elif int(length) > max_body:
                status, body = 413, {"error": "too_large", "message": f"the body exceeds {max_body} bytes"}
                service.metrics.reject("body")
                self.close_connection = True
            else:
                status, body = service.diagnose(self.rfile.read(int(length)))

            seconds = time.perf_counter() - started
            service.metrics.response(status, seconds if status in (200, 502) else None)
            self.reply(status, body)
            service.log({"event": "diagnose", "status": status, "seconds": round(seconds, 3),
                         "outcome": body.get("result", {}).get("outcome") if isinstance(body, dict) else None,
                         "error": body.get("error") if isinstance(body, dict) else None})

    return Handler


def serve(args: argparse.Namespace, *, service: Service | None = None, ready_callback=None) -> int:
    """Listen at once (so /healthz answers), load in the background, serve until SIGTERM or SIGINT."""
    service = service or Service(args)
    httpd = ThreadingHTTPServer((args.host, args.port), handler_for(service, args.max_body_bytes))
    httpd.daemon_threads = True
    stopped = threading.Event()

    def drain() -> None:
        deadline = time.monotonic() + DRAIN_SECONDS

        while not service.idle() and time.monotonic() < deadline:
            time.sleep(0.2)

        httpd.shutdown()

    def on_signal(signum, frame) -> None:
        if not stopped.is_set():
            stopped.set()
            service.state, service.reason = "draining", "shutting down"
            service.log({"event": "draining", "signal": signal.Signals(signum).name})
            threading.Thread(target=drain, daemon=True).start()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, on_signal)
        signal.signal(signal.SIGINT, on_signal)

    def load() -> None:
        service.load()

        if service.state == "failed":  # a restart is the remedy (or the operator's fix); say why and exit
            stopped.set()
            httpd.shutdown()

    service.log({"event": "listening", "host": args.host, "port": httpd.server_address[1],
                 "max_queue": args.max_queue})
    threading.Thread(target=load, daemon=True).start()

    if ready_callback:
        ready_callback(httpd, on_signal)

    try:
        httpd.serve_forever(poll_interval=0.2)
    finally:
        httpd.server_close()
        service.stop()

    if service.state == "failed":
        print(f"hetren: {service.reason}", file=sys.stderr)
        return 3

    return 0


__all__ = ["BUCKETS", "Metrics", "Service", "handler_for", "serve"]
