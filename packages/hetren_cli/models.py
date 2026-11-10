"""The validated GGUF files and tokenizer, checked against the export manifest.

``data/export.manifest.json`` is a copy of ``docs/milestone-4/export.manifest.json`` (a test keeps them equal).
A model file is used only if its sha256 is one of the two accepted variants' (Q4_K_M ships by default under
Amendment 2's rule; Q8_0 is the higher-fidelity alternative), and the tokenizer only if every file has the
merged model's sha256, as the validation run checked (``gguf_validation.verify_variant``).

``fetch`` downloads both from a Hugging Face model repository laid out as::

    <variant's GGUF file name>         e.g. hetren-qwen3-4b-ckpt0792-q4_k_m.gguf
    tokenizer/<file>                   the merged model's tokenizer files

into the cache (default ``~/.cache/hetren``, or ``$HETREN_CACHE``), with the standard library only
(``$HF_ENDPOINT`` and ``$HF_TOKEN`` are honoured). A download is written to a temporary file and kept only if
its size (for a GGUF, the manifest's; otherwise the server's ``Content-Length``) and sha256 match; a download
that fails these checks or breaks off is retried once from the start. HTTPS uses the system's certificates, or
certifi's bundle when Python has none (python.org's macOS Python before "Install Certificates").
"""

from __future__ import annotations

import hashlib
import json
import http.client
import os
from pathlib import Path
import ssl
import urllib.error
import urllib.parse
import urllib.request


DATA = Path(__file__).resolve().parent / "data"
MANIFEST = DATA / "export.manifest.json"
VARIANTS = ("Q4_K_M", "Q8_0")
DEFAULT_VARIANT = "Q4_K_M"  # Amendment 2's shipping rule (docs/milestone-4/EXPORT_LOG.md, "Acceptance and shipping")
TOKENIZER_DIR = "tokenizer"
CHUNK = 1 << 20


class ModelError(RuntimeError):
    """A model or tokenizer file is missing or is not the validated one."""


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def gguf_files(m: dict | None = None) -> dict[str, dict]:
    """Variant -> {"file", "sha256", "bytes"} for the accepted variants, from the manifest."""
    m = manifest() if m is None else m
    files = {}

    for name, entry in m["gguf"].items():
        for variant in VARIANTS:
            if name.endswith(f"-{variant.lower()}.gguf"):
                files[variant] = {"file": name, "sha256": entry["sha256"], "bytes": entry["bytes"]}

    if sorted(files) != sorted(VARIANTS):
        raise ModelError(f"the manifest lists {sorted(files)}, not {list(VARIANTS)}")

    return files


def tokenizer_files(m: dict | None = None) -> dict[str, str]:
    """Tokenizer file -> sha256: the merged model's files other than its weights."""
    m = manifest() if m is None else m
    return {name: digest for name, digest in sorted(m["merge"]["files"].items()) if not name.startswith("model")}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)

    return digest.hexdigest()


def cache_dir() -> Path:
    return Path(os.environ.get("HETREN_CACHE") or Path.home() / ".cache" / "hetren")


def identify(path: Path, m: dict | None = None) -> tuple[str, str]:
    """(variant, sha256) of a GGUF file, if it is one of the accepted variants."""
    if not Path(path).is_file():
        raise ModelError(f"no model file at {path} (run fetch-model, or pass --model)")

    digest = sha256_file(path)

    for variant, entry in gguf_files(m).items():
        if digest == entry["sha256"]:
            return variant, digest

    raise ModelError(f"{path} (sha256 {digest}) is not a validated Hetren GGUF; the accepted variants are "
                     + ", ".join(f"{v} {e['sha256']}" for v, e in gguf_files(m).items()))


def check_tokenizer(directory: Path, m: dict | None = None) -> None:
    for name, digest in tokenizer_files(m).items():
        path = Path(directory) / name

        if not path.is_file():
            raise ModelError(f"tokenizer file missing: {path} (run fetch-model, or pass --tokenizer)")

        if sha256_file(path) != digest:
            raise ModelError(f"{path} does not have the merged model's sha256 {digest}")


def resolve(model: Path | None, tokenizer: Path | None, variant: str | None, cache: Path | None = None
            ) -> dict[str, object]:
    """The checked model and tokenizer: ``--model`` (and ``--tokenizer``, default ``<model's folder>/tokenizer``)
    or the cache's copy of ``variant`` (default Q4_K_M)."""
    cache = cache_dir() if cache is None else Path(cache)

    if model is None:
        variant = variant or DEFAULT_VARIANT
        model = cache / gguf_files()[variant]["file"]

    tokenizer = Path(tokenizer) if tokenizer is not None else Path(model).parent / TOKENIZER_DIR
    found, digest = identify(Path(model))

    if variant is not None and found != variant:
        raise ModelError(f"{model} is the {found} GGUF, not {variant}")

    check_tokenizer(tokenizer)
    return {"variant": found, "gguf": str(model), "gguf_sha256": digest, "tokenizer": str(tokenizer)}


def _url(repo: str, revision: str, path: str) -> str:
    endpoint = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
    return f"{endpoint}/{repo}/resolve/{urllib.parse.quote(revision, safe='')}/{urllib.parse.quote(path)}"


def tls_context() -> ssl.SSLContext:
    """The system's certificates when Python finds any (or ``$SSL_CERT_FILE``/``$SSL_CERT_DIR`` names them);
    otherwise certifi's bundle, if installed. python.org's macOS Python has no certificates until its "Install
    Certificates" step, and every HTTPS request then fails with CERTIFICATE_VERIFY_FAILED."""
    paths = ssl.get_default_verify_paths()
    has_system = bool(os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR")) \
        or bool(paths.cafile and os.path.isfile(paths.cafile)) \
        or bool(paths.capath and os.path.isdir(paths.capath) and os.listdir(paths.capath))

    if not has_system:
        try:
            import certifi
        except ImportError:
            pass
        else:
            return ssl.create_default_context(cafile=certifi.where())

    return ssl.create_default_context()


def _fetch_once(url: str, partial: Path) -> tuple[str, int, int | None]:
    """(sha256, bytes received, Content-Length or None), written to ``partial``."""
    request = urllib.request.Request(url, headers={"User-Agent": "hetren-cli"})

    if os.environ.get("HF_TOKEN"):
        request.add_header("Authorization", f"Bearer {os.environ['HF_TOKEN']}")

    hasher, received = hashlib.sha256(), 0
    context = tls_context() if url.startswith("https:") else None

    with urllib.request.urlopen(request, timeout=60, context=context) as response, open(partial, "wb") as out:
        length = response.headers.get("Content-Length")

        for block in iter(lambda: response.read(CHUNK), b""):
            hasher.update(block)
            out.write(block)
            received += len(block)

    return hasher.hexdigest(), received, int(length) if length and length.isdigit() else None


def _download(url: str, target: Path, digest: str, log, size: int | None = None, attempts: int = 2) -> None:
    if target.is_file() and sha256_file(target) == digest:
        log(f"{target.name}: already in the cache, sha256 matches")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    problem = ""

    for attempt in range(1, attempts + 1):
        log(f"{target.name}: downloading {url}" + (f" (attempt {attempt} of {attempts})" if attempt > 1 else ""))

        try:
            got, received, length = _fetch_once(url, partial)
        except urllib.error.HTTPError as exc:
            partial.unlink(missing_ok=True)

            if exc.code < 500:  # not found, unauthorised: retrying cannot help
                raise ModelError(f"{url}: HTTP {exc.code} {exc.reason}; nothing was kept") from exc

            problem = f"HTTP {exc.code} {exc.reason}"
        except (OSError, http.client.HTTPException) as exc:  # broken connection, timeout, short read
            problem = f"the download broke off ({type(exc).__name__}: {exc})"
        else:
            if size is not None and received != size:
                problem = f"{received} bytes, not the manifest's {size}"
            elif length is not None and received != length:
                problem = f"{received} bytes, not the {length} the server announced"
            elif got != digest:
                problem = f"sha256 {got}, not the manifest's {digest}"
            else:
                partial.replace(target)
                log(f"{target.name}: sha256 matches the manifest")
                return

        partial.unlink(missing_ok=True)

        if attempt < attempts:
            log(f"{target.name}: {problem}; retrying once from the start")

    raise ModelError(f"{url}: {problem} (after {attempts} attempts); nothing was kept")


def fetch(repo: str, variant: str = DEFAULT_VARIANT, revision: str = "main", cache: Path | None = None,
          log=print, tokenizer_only: bool = False) -> dict[str, object]:
    """Download ``variant``'s GGUF and the tokenizer into the cache, checking every sha256 (only the tokenizer
    with ``tokenizer_only``: for ``serve --server-url``, where another process serves the GGUF)."""
    cache = cache_dir() if cache is None else Path(cache)
    entry = gguf_files()[variant]

    for name, digest in tokenizer_files().items():
        _download(_url(repo, revision, f"{TOKENIZER_DIR}/{name}"), cache / TOKENIZER_DIR / name, digest, log)

    if not tokenizer_only:
        _download(_url(repo, revision, entry["file"]), cache / entry["file"], entry["sha256"], log, size=entry["bytes"])

    return {"variant": variant, "gguf": None if tokenizer_only else str(cache / entry["file"]),
            "gguf_sha256": entry["sha256"], "tokenizer": str(cache / TOKENIZER_DIR)}


__all__ = ["DEFAULT_VARIANT", "ModelError", "VARIANTS", "cache_dir", "check_tokenizer", "fetch", "gguf_files",
           "identify", "manifest", "resolve", "sha256_file", "tls_context", "tokenizer_files"]
