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
its sha256 matches.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
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


def _download(url: str, target: Path, digest: str, log) -> None:
    if target.is_file() and sha256_file(target) == digest:
        log(f"{target.name}: already in the cache, sha256 matches")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "hetren-cli"})

    if os.environ.get("HF_TOKEN"):
        request.add_header("Authorization", f"Bearer {os.environ['HF_TOKEN']}")

    log(f"{target.name}: downloading {url}")
    hasher = hashlib.sha256()

    with urllib.request.urlopen(request, timeout=60) as response, open(partial, "wb") as out:
        for block in iter(lambda: response.read(CHUNK), b""):
            hasher.update(block)
            out.write(block)

    if hasher.hexdigest() != digest:
        partial.unlink()
        raise ModelError(f"{url} has sha256 {hasher.hexdigest()}, not the manifest's {digest}; nothing was kept")

    partial.replace(target)
    log(f"{target.name}: sha256 matches the manifest")


def fetch(repo: str, variant: str = DEFAULT_VARIANT, revision: str = "main", cache: Path | None = None,
          log=print, tokenizer_only: bool = False) -> dict[str, object]:
    """Download ``variant``'s GGUF and the tokenizer into the cache, checking every sha256 (only the tokenizer
    with ``tokenizer_only``: for ``serve --server-url``, where another process serves the GGUF)."""
    cache = cache_dir() if cache is None else Path(cache)
    entry = gguf_files()[variant]

    for name, digest in tokenizer_files().items():
        _download(_url(repo, revision, f"{TOKENIZER_DIR}/{name}"), cache / TOKENIZER_DIR / name, digest, log)

    if not tokenizer_only:
        _download(_url(repo, revision, entry["file"]), cache / entry["file"], entry["sha256"], log)

    return {"variant": variant, "gguf": None if tokenizer_only else str(cache / entry["file"]),
            "gguf_sha256": entry["sha256"], "tokenizer": str(cache / TOKENIZER_DIR)}


__all__ = ["DEFAULT_VARIANT", "ModelError", "VARIANTS", "cache_dir", "check_tokenizer", "fetch", "gguf_files",
           "identify", "manifest", "resolve", "sha256_file", "tokenizer_files"]
