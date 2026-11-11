"""A stand-in for ``llama-server`` in the kind test (CI only; never in the published image or on GKE).

It answers the three endpoints ``hetren serve --server-url`` uses: ``/health``, ``/props`` (the served file's
name: the CLI checks it against the chosen variant) and ``/completion``. Every completion returns the same
recorded reply after ``STUB_SECONDS``: the token IDs Q4_K_M generated for one pilot case in the Linux check
(``artifacts/milestone-4/linux-check-1/episodes-Q4_K_M.jsonl``, ``case-000071`` call 0), which the real
tokenizer decodes to ``{"action": "decide", "verb": "abstain", "args": {"reason": "persistent_tool_error"}}``.
It checks that the request uses Amendment 2's greedy decoding, so the test also covers what the API sends.

This tests the deployment's plumbing (probes, Service, queue, load test), not inference.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time


MODEL_PATH = os.environ.get("STUB_MODEL_PATH", "/models/hetren-qwen3-4b-ckpt0792-q4_k_m.gguf")
SECONDS = float(os.environ.get("STUB_SECONDS", "2"))
PORT = int(os.environ.get("STUB_PORT", "8080"))
REPLY = [4913, 1311, 788, 330, 8169, 577, 497, 330, 22328, 788, 330, 370, 267, 466, 497, 330, 2116, 788, 5212,
         19895, 788, 330, 69389, 22785, 4096, 30975, 151645]
GREEDY = {"samplers": ["top_k"], "top_k": 1, "temperature": 0.0, "cache_prompt": True, "n_predict": 128}
ONE_AT_A_TIME = threading.Lock()  # like llama-server with one slot


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def send(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send(200, {"status": "ok"})
        elif self.path == "/props":
            self.send(200, {"model_path": MODEL_PATH, "stub": True})
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/completion":
            self.send(404, {"error": "not found"})
            return

        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        wrong = {k: request.get(k) for k, v in GREEDY.items() if request.get(k) != v}

        if wrong or not isinstance(request.get("prompt"), list) or not request["prompt"]:
            self.send(400, {"error": f"not Amendment 2's decoding or no token prompt: {wrong}"})
            return

        with ONE_AT_A_TIME:
            time.sleep(SECONDS)

        self.send(200, {"tokens": REPLY, "stop_type": "eos", "tokens_cached": 0,
                        "tokens_evaluated": len(request["prompt"]),
                        "completion_probabilities": [{"id": t, "logprob": -0.01} for t in REPLY],
                        "timings": {"prompt_n": len(request["prompt"]), "predicted_n": len(REPLY),
                                    "prompt_ms": SECONDS * 900, "predicted_ms": SECONDS * 100}})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
