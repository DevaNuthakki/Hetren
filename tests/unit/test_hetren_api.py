"""CPU tests of ``hetren serve`` (Milestone 4, step 6): the API around the CLI's diagnosis.

The model side is the CLI tests' (a fake executable ``llama-server``, a fake tokenizer, a temporary manifest);
the API runs in a thread on a free port and is called over real HTTP.
"""

from __future__ import annotations

import http.client
import json
import signal
import subprocess
import threading
import time

import pytest

from packages.hetren_cli import api, main as cli, runtime

from test_hetren_cli import REPO_ROOT, FakeTokenizer, fake_server, model_dir, records  # noqa: F401  (fixtures)


def _args(*extra: str) -> object:
    return cli._parser().parse_args(["serve", "--port", "0", "--threads", "2", *extra])


class Running:
    """``serve`` in a thread; ``call`` makes one HTTP request and returns (status, headers, body)."""

    def __init__(self, args, tokenizer=None, **service_kwargs):
        self.service = api.Service(args, tokenizer_loader=lambda directory: tokenizer or FakeTokenizer(),
                                   log=lambda entry: None, **service_kwargs)
        self.started = threading.Event()
        self.result = None

        def callback(httpd, on_signal):
            self.port, self.on_signal = httpd.server_address[1], on_signal
            self.started.set()

        def target():
            self.result = api.serve(args, service=self.service, ready_callback=callback)

        self.thread = threading.Thread(target=target, daemon=True)
        self.thread.start()
        assert self.started.wait(10)

    def call(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read().decode("utf-8")
        connection.close()
        return response.status, dict(response.getheaders()), data

    def post(self, value) -> tuple[int, dict]:
        status, _, data = self.call("POST", "/diagnose", json.dumps(value).encode("utf-8"),
                                    {"Content-Type": "application/json"})
        return status, json.loads(data)

    def wait_ready(self) -> None:
        assert self.service.loaded.wait(30)
        assert self.service.state == "ready", self.service.reason

    def stop(self) -> int:
        self.on_signal(signal.SIGTERM, None)
        self.thread.join(30)
        assert not self.thread.is_alive()
        return self.result


@pytest.fixture
def running(model_dir, fake_server):  # noqa: F811
    server = Running(_args())
    server.wait_ready()
    yield server

    if server.thread.is_alive():
        server.stop()


def test_a_record_is_diagnosed_with_the_clis_record(running, records):  # noqa: F811
    status, body = running.post({"record": records[0]})

    assert status == 200, body
    assert body["result"]["outcome"] == "decision" and body["result"]["action"]["verb"] == "no_intervention"
    assert body["model"]["variant"] == "Q4_K_M" and body["model"]["gguf_sha256"]
    assert body["server"]["validated_build"] is True and body["server"]["threads"] == 2
    assert body["prompt_version"] == 2 and body["cli_version"] == cli.CLI_VERSION


def test_probes_and_metrics(running, records):  # noqa: F811
    assert running.call("GET", "/healthz")[0] == 200
    status, _, data = running.call("GET", "/readyz")
    assert status == 200 and json.loads(data)["status"] == "ready"

    running.post({"record": records[0]})
    running.post({"compact": {"format": "nonsense"}})
    status, headers, text = running.call("GET", "/metrics")

    assert status == 200 and headers["Content-Type"].startswith("text/plain; version=0.0.4")
    assert "hetren_ready 1" in text and 'hetren_diagnoses_total{outcome="decision"} 1' in text
    assert 'hetren_http_responses_total{code="200"} 1' in text and 'hetren_http_responses_total{code="400"} 1' in text
    assert 'hetren_rejected_total{reason="input"} 1' in text and "hetren_request_seconds_count 1" in text
    assert 'variant="Q4_K_M"' in text and f'llama_cpp_commit="{runtime.VALIDATED_LLAMA_CPP[:9]}"' in text


def test_inputs_are_rejected_as_the_cli_rejects_them(running, records):  # noqa: F811
    trace = {"object": "trace", "id": "trace_1", "spans": []}
    cases = [{"record": trace}, {"compact": {"format": "compact-evidence-v2"}}, {"record": records[0], "compact": {}},
             ["not", "an", "object"], {"evidence": records[0]}]

    for value in cases:
        status, body = running.post(value)
        assert status == 400 and body["error"] == "input_rejected", (value, body)

    status, _, data = running.call("POST", "/diagnose", b"{not json", {"Content-Type": "application/json"})
    assert status == 400 and "not JSON" in json.loads(data)["message"]


def test_http_errors(model_dir, fake_server):  # noqa: F811
    running = Running(_args("--max-body-bytes", "100"))
    running.wait_ready()
    assert running.call("GET", "/diagnose")[0] == 405
    assert running.call("POST", "/healthz", b"{}")[0] == 405
    assert running.call("GET", "/nothing")[0] == 404
    assert running.call("POST", "/diagnose", b"x" * 101)[0] == 413

    connection = http.client.HTTPConnection("127.0.0.1", running.port, timeout=10)
    connection.putrequest("POST", "/diagnose")
    connection.endheaders()
    assert connection.getresponse().status == 411
    connection.close()
    assert running.stop() == 0


def test_an_invalid_reply_is_a_502_with_the_record(model_dir, fake_server, records):  # noqa: F811
    fake_server["set_reply"]("I think the run is fine.")  # before the server starts: it reads the reply once
    running = Running(_args())
    running.wait_ready()
    status, body = running.post({"record": records[0]})
    assert status == 502 and body["result"]["outcome"] == "invalid_reply"
    assert body["generation"]["reply"] == "I think the run is fine."
    assert running.stop() == 0


def test_a_context_overflow_is_an_input_rejection(model_dir, fake_server, records):  # noqa: F811
    server = Running(_args(), tokenizer=FakeTokenizer(prompt_tokens=4000))
    server.wait_ready()
    status, body = server.post({"record": records[0]})
    assert status == 400 and "4096-token context" in body["message"]
    assert server.stop() == 0


class BlockingDiagnoser:
    def __init__(self):
        self.release, self.entered = threading.Event(), threading.Semaphore(0)

    def prompt(self, compact):
        return "system", "user"

    def run(self, compact, server, server_info, messages):
        self.entered.release()
        assert self.release.wait(10)
        return 0, {"result": {"outcome": "decision"}, "generation": {"seconds": 0.1}}


def test_one_diagnosis_at_a_time_and_a_full_queue_is_refused(model_dir):  # noqa: F811
    service = api.Service(_args("--max-queue", "1"), log=lambda entry: None)
    service.state, service.diagnoser = "ready", BlockingDiagnoser()
    compact = json.loads((REPO_ROOT / "tests/fixtures/hetren_cli/compact_first_step.json").read_text(encoding="utf-8"))
    body = json.dumps({"compact": compact}).encode("utf-8")
    results = []
    threads = [threading.Thread(target=lambda: results.append(service.diagnose(body))) for _ in range(2)]

    threads[0].start()
    assert service.diagnoser.entered.acquire(timeout=10)  # the first is running
    threads[1].start()

    for _ in range(100):  # the second is waiting
        if service.gauges()["queue_waiting"][1] == 1:
            break
        time.sleep(0.05)

    assert service.gauges()["in_flight"][1] == 1 and service.gauges()["queue_waiting"][1] == 1
    status, refused = service.diagnose(body)
    assert status == 503 and refused["error"] == "queue_full"

    service.diagnoser.release.set()
    for thread in threads:
        thread.join(10)

    assert [status for status, _ in results] == [200, 200] and service.idle()


def test_not_ready_until_loaded_and_a_failed_load_exits_3(model_dir, fake_server, tmp_path):  # noqa: F811
    service = api.Service(_args(), log=lambda entry: None)
    assert service.diagnose(b"{}")[0] == 503 and not service.ready() and service.healthy()

    server = Running(_args("--model", str(tmp_path / "missing.gguf")))
    server.thread.join(30)
    assert server.result == 3 and server.service.state == "failed" and "missing.gguf" in server.service.reason


def test_sigterm_drains_then_exits_0(running, records):  # noqa: F811
    running.on_signal(signal.SIGTERM, None)
    assert running.service.state == "draining" and not running.service.ready()
    running.thread.join(30)
    assert running.result == 0


def test_a_dead_llama_server_makes_the_pod_unhealthy(running):
    process = running.service.local.process
    process.kill()
    process.wait()
    assert running.call("GET", "/healthz")[0] == 503 and running.call("GET", "/readyz")[0] == 503


def test_an_external_server_url_serving_the_variant(model_dir, fake_server, records):  # noqa: F811
    port = runtime.free_port()
    process = subprocess.Popen([str(fake_server["binary"]), "-m", "/models/hetren-qwen3-4b-ckpt0792-q4_k_m.gguf",
                                "--port", str(port)])

    try:
        for _ in range(100):
            try:
                runtime.LlamaServer(f"http://127.0.0.1:{port}", timeout=1).request("/health")
                break
            except OSError:
                time.sleep(0.1)

        server = Running(_args("--server-url", f"http://127.0.0.1:{port}"))
        server.wait_ready()
        status, body = server.post({"record": records[0]})
        assert status == 200 and body["server"]["url"].endswith(str(port)) and body["model"]["gguf_sha256"] is None
        assert server.stop() == 0
    finally:
        process.terminate()
        process.wait()


def test_serve_defaults_listen_locally_with_a_bounded_queue():
    args = cli._parser().parse_args(["serve"])
    assert (args.host, args.port, args.max_queue, args.max_body_bytes) == ("127.0.0.1", 8000, 8, 1 << 20)
    assert "``record``" in api.__doc__ and "``compact``" in api.__doc__
