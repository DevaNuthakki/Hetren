"""``llama-server`` for one diagnosis: started with Amendment 2's settings and stopped afterwards, or an
already-running server (``--server-url``).

The binary is ``--llama-server``, else ``$HETREN_LLAMA_SERVER``, else ``llama-server`` on ``PATH``. Its build
is recorded (``--version``); a build other than the validated one (``620d2225``) is reported as such, since
the validation describes that build only.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time

from packages.hetren_serving.llama_server import LlamaServer, server_arguments


VALIDATED_LLAMA_CPP = "620d2225cc436ab0b001e3200e590e3b286ef9ab"  # Amendment 2; export.manifest.json
READY_SECONDS = 600.0


class RuntimeFailure(RuntimeError):
    """The server could not be found, started or used."""


def default_threads() -> int:
    """Physical cores, approximated as half the logical CPUs (the validation used 6 of the Mac's 12)."""
    return max(1, (os.cpu_count() or 2) // 2)


def missing_cpu_flags(required: str | None = None, cpuinfo: str | None = None) -> list[str]:
    """The CPU flags ``$HETREN_REQUIRED_CPU_FLAGS`` names (set in the Docker image, whose llama-server is built for
    AVX2, FMA and F16C) that ``/proc/cpuinfo`` lacks; none when the variable is unset or there is no
    ``/proc/cpuinfo`` (not Linux)."""
    required = os.environ.get("HETREN_REQUIRED_CPU_FLAGS", "") if required is None else required
    wanted = required.split()

    if not wanted:
        return []

    if cpuinfo is None:
        try:
            cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8")
        except OSError:
            return []

    lines = [line for line in cpuinfo.splitlines() if line.startswith("flags")]

    if not lines:
        return []

    flags = set(lines[0].split(":", 1)[1].split())
    return [flag for flag in wanted if flag not in flags]


def check_cpu(required: str | None = None, cpuinfo: str | None = None) -> None:
    missing = missing_cpu_flags(required, cpuinfo)

    if missing:
        raise RuntimeFailure(f"this CPU lacks {', '.join(missing)}; this llama-server build needs "
                             f"{(required or os.environ.get('HETREN_REQUIRED_CPU_FLAGS', '')).strip()} "
                             "(the image is built for exactly that feature set)")


def find_binary(binary: str | None) -> str:
    candidate = binary or os.environ.get("HETREN_LLAMA_SERVER") or shutil.which("llama-server")

    if not candidate or not Path(candidate).is_file():
        raise RuntimeFailure("llama-server not found: pass --llama-server, set HETREN_LLAMA_SERVER, or put it on "
                             f"PATH (build llama.cpp at {VALIDATED_LLAMA_CPP[:8]}, CPU only)")

    return str(candidate)


def build_info(binary: str, run=subprocess.run) -> dict[str, object]:
    """``llama-server --version``: the build's text and commit, and whether it is the validated build."""
    result = run([binary, "--version"], capture_output=True, text=True, timeout=60)
    text = ((result.stdout or "") + (result.stderr or "")).strip()
    match = re.search(r"commit ([0-9a-f]{7,40})", text)
    commit = match.group(1) if match else None
    return {"version": text.splitlines()[-2:] if text else [], "commit": commit,
            "validated_build": bool(commit) and VALIDATED_LLAMA_CPP.startswith(commit)}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LocalServer:
    """A ``llama-server`` child process for one diagnosis; its log goes to a temporary file."""

    def __init__(self, binary: str, gguf: str, threads: int, port: int | None = None,
                 ready_seconds: float = READY_SECONDS):
        self.port = port or free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.command = server_arguments(binary, gguf, threads, self.port)
        self.gguf, self.ready_seconds = gguf, ready_seconds
        self.process = None
        self.log = None

    def __enter__(self) -> "LocalServer":
        self.log = tempfile.NamedTemporaryFile("w+", prefix="hetren-llama-server-", suffix=".log", delete=False)

        try:
            self._start()
        except BaseException:
            self.__exit__(None, None, None)
            raise

        return self

    def _start(self) -> None:
        self.process = subprocess.Popen(self.command, stdout=self.log, stderr=subprocess.STDOUT,
                                        start_new_session=True)
        client = LlamaServer(self.url, timeout=10)
        started = time.perf_counter()

        while True:
            if self.process.poll() is not None:
                raise RuntimeFailure(f"llama-server exited with {self.process.returncode}; log: {self.log.name}")

            try:
                if client.request("/health").get("status") == "ok":
                    break
            except Exception:  # refused while starting, 503 while loading
                pass

            if time.perf_counter() - started > self.ready_seconds:
                raise RuntimeFailure(f"llama-server not ready after {self.ready_seconds:.0f} s; log: {self.log.name}")

            time.sleep(0.5)

        check_served(LlamaServer(self.url), Path(self.gguf).name)

    def __exit__(self, *exc) -> bool:
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)

            try:
                self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()

        if self.log is not None:
            self.log.close()

            if exc[0] is None:  # keep the log only when something went wrong
                Path(self.log.name).unlink(missing_ok=True)

        return False


def check_served(server: LlamaServer, file_name: str) -> None:
    """The server serves ``file_name`` (by the ``model_path`` it reports)."""
    try:
        served = Path(server.props().get("model_path", "")).name
    except Exception as exc:
        raise RuntimeFailure(f"cannot read the server's properties from {server.url}: {exc}") from exc

    if served != file_name:
        raise RuntimeFailure(f"the server on {server.url} serves {served!r}, not {file_name}")


__all__ = ["LocalServer", "RuntimeFailure", "VALIDATED_LLAMA_CPP", "build_info", "check_cpu", "check_served",
           "default_threads", "find_binary", "free_port", "missing_cpu_flags"]
