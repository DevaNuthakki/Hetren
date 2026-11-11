"""Writes notebooks/milestone-4/gguf_pilot.ipynb (the Kaggle CPU throughput pilot, Milestone 4 step 2).

    python scripts/make_gguf_pilot_notebook.py           # (re)write the notebook
    python scripts/make_gguf_pilot_notebook.py --check   # exit 1 if the committed notebook differs
"""
import argparse
import json
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks/milestone-4/gguf_pilot.ipynb"

md = lambda text: {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}
code = lambda text: {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                     "source": text.strip("\n").splitlines(keepends=True)}

cells = [
    md("""
# GGUF throughput pilot on a Kaggle CPU (Milestone 4, step 2)

Implements `docs/milestone-2/EVAL_PROTOCOL.md`, Amendment 2, "Throughput pilot", on the Kaggle half of the two platforms (the Mac runs the same module locally). Settings: accelerator **None** (CPU, 4 vCPUs), internet **on** (to clone llama.cpp), environment **pinned**.

1. **Bundle and inputs:** the bundle at the commit set below, and export 2's output (`hetren-gguf-export-2`), whose `export.manifest.json` must equal the committed one.
2. **Environment:** `requirements-gguf-pilot.txt` (the episode code and the tokenizer side; no torch) and `/usr/bin/time` for peak memory.
3. **llama.cpp** at the pinned commit, built CPU-only with the export's flags (`llama-server` only).
4. **Pilot:** `python -m packages.support_evaluator.gguf_pilot run --platform kaggle`: the 20 fp16 smoke-test cases, each episode twice with prompt caching on and twice with it off, per variant, `-t 4 -b 2048 -ub 512`. It checks both GGUFs and the tokenizer against the committed manifest first.

**Not an evaluation.** Episodes are run but not scored; the pilot's accuracy is neither computed, reported nor used. No test split is run. Every run of this notebook, including failed ones, is logged in `docs/milestone-4/EXPORT_LOG.md` before its results are read.

**Outputs** (`/kaggle/working/gguf-pilot/`): `pilot-kaggle.json`, `episodes-<variant>-cache-<on|off>.jsonl`, `server-<variant>-cache-<on|off>.log`, `environment.json` and `outputs.sha256`.
"""),
    code("""
BUNDLE_COMMIT = ""  # the bundle's commit (full sha); the notebook stops if the bundle found is another
LLAMA_CPP_COMMIT = "620d2225cc436ab0b001e3200e590e3b286ef9ab"  # release v0.7.0 (Amendment 2)
EXPORT_MANIFEST_SHA256 = "4a2431a46a31045d74bf48da291fcbf09692a794e58d66d7135ede1cdc433ee0"  # export 2 (EXPORT_LOG.md)

import glob, hashlib, json, os, platform, shutil, subprocess, sys, tarfile, time

INPUTS, WORK, SCRATCH, OUT = "/kaggle/input", "/kaggle/working/hetren", "/tmp/hetren-pilot", "/kaggle/working/gguf-pilot"


def earlier_session(path):  # a copy of the code inside an attached notebook output (training, selection, export)
    if "/hetren/" not in path:
        return False

    root = path.split("/hetren/")[0]
    return bool(glob.glob(f"{root}/qlora-*") or glob.glob(f"{root}/gguf-*"))


def sha256(path):
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


if not os.path.exists(WORK):
    unpacked = [p for p in glob.glob(f"{INPUTS}/**/BUNDLE.json", recursive=True) if not earlier_session(p)]
    packed = [p for p in glob.glob(f"{INPUTS}/**/hetren-*bundle*.tar.gz", recursive=True) if not earlier_session(p)]

    if len(unpacked) > 1 or (not unpacked and len(packed) != 1):
        raise SystemExit(f"STOP: attach exactly one bundle; found {unpacked or packed}")

    if unpacked:  # Kaggle may unpack archives on upload
        shutil.copytree(os.path.dirname(unpacked[0]), WORK)
    else:
        os.makedirs(WORK)
        tarfile.open(packed[0]).extractall(WORK)

    print("bundle from", unpacked[0] if unpacked else packed[0])

COMMIT = json.load(open(f"{WORK}/BUNDLE.json"))["commit"]
print("bundle commit:", COMMIT)

if not BUNDLE_COMMIT or COMMIT != BUNDLE_COMMIT.strip():
    raise SystemExit(f"STOP: the bundle is commit {COMMIT}, not BUNDLE_COMMIT {BUNDLE_COMMIT!r}")

if os.path.exists(OUT) and os.listdir(OUT):
    raise SystemExit(f"STOP: {OUT} is not empty; this notebook runs the pilot once per session")

if shutil.which("nvidia-smi") and subprocess.run(["nvidia-smi", "-L"], capture_output=True).returncode == 0:
    raise SystemExit("STOP: a GPU is attached; the pilot runs with accelerator None")

manifests = [p for p in glob.glob(f"{INPUTS}/**/gguf-export/export.manifest.json", recursive=True)
             if sha256(p) == EXPORT_MANIFEST_SHA256]

if len(manifests) != 1:
    raise SystemExit(f"STOP: attach export 2's output once; manifests with the logged sha256: {manifests}")

EXPORT = os.path.dirname(manifests[0])

if sha256(f"{WORK}/docs/milestone-4/export.manifest.json") != EXPORT_MANIFEST_SHA256:
    raise SystemExit("STOP: the bundle's committed export manifest is not export 2's")

print("export:", EXPORT, "\\nCPUs:", os.cpu_count(), "|", platform.processor() or platform.machine())
os.makedirs(SCRATCH, exist_ok=True)
os.chdir(WORK)
"""),
    md("""
## 1. Environment: the pilot's requirements and `/usr/bin/time`
"""),
    code("""
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", f"{WORK}/requirements-gguf-pilot.txt"], check=True)
TIME_INSTALLED = not os.path.exists("/usr/bin/time")

if TIME_INSTALLED:  # GNU time, for the server's peak memory (-v)
    subprocess.run(["apt-get", "update", "-qq"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["apt-get", "install", "-y", "-qq", "time"], check=True, stdout=subprocess.DEVNULL)

if not os.path.exists("/usr/bin/time"):
    raise SystemExit("STOP: /usr/bin/time is missing")

print("transformers", subprocess.run([sys.executable, "-c", "import transformers; print(transformers.__version__)"],
                                     capture_output=True, text=True, check=True).stdout.strip(),
      "| /usr/bin/time", "installed by this notebook" if TIME_INSTALLED else "from the platform")
"""),
    md("""
## 2. Build llama.cpp at the pinned commit (CPU only, the export's flags)
"""),
    code("""
LLAMA = f"{SCRATCH}/llama.cpp"

if not os.path.exists(LLAMA):
    subprocess.run(["git", "clone", "--quiet", "https://github.com/ggml-org/llama.cpp", LLAMA], check=True)

subprocess.run(["git", "-C", LLAMA, "checkout", "--quiet", LLAMA_CPP_COMMIT], check=True)
head = subprocess.run(["git", "-C", LLAMA, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

if head != LLAMA_CPP_COMMIT:
    raise SystemExit(f"STOP: llama.cpp is at {head}, not {LLAMA_CPP_COMMIT}")

CMAKE_FLAGS = ["-DCMAKE_BUILD_TYPE=Release", "-DGGML_CUDA=OFF", "-DGGML_METAL=OFF", "-DGGML_BLAS=OFF", "-DGGML_NATIVE=OFF"]
started = time.time()
subprocess.run(["cmake", "-S", LLAMA, "-B", f"{LLAMA}/build", *CMAKE_FLAGS], check=True, stdout=subprocess.DEVNULL)
subprocess.run(["cmake", "--build", f"{LLAMA}/build", "--target", "llama-server", "-j", str(os.cpu_count())],
               check=True, stdout=subprocess.DEVNULL)
print(f"built llama-server in {(time.time() - started) / 60:.1f} min")
"""),
    md("""
## 3. The pilot (about 2 hours)

Progress is printed per episode (calls and seconds only; nothing is scored). A stop is logged before anything is repeated.
"""),
    code("""
started = time.time()
PILOT = subprocess.run([sys.executable, "-m", "packages.support_evaluator.gguf_pilot", "run", "--platform", "kaggle",
                        "--gguf-dir", EXPORT, "--tokenizer", f"{EXPORT}/tokenizer", "--llama-cpp", LLAMA,
                        "--out", OUT]).returncode
print(f"pilot exit {PILOT} after {(time.time() - started) / 3600:.2f} h")
"""),
    md("""
## Outputs
"""),
    code("""
os.makedirs(OUT, exist_ok=True)
environment = {
    "bundle_commit": COMMIT, "llama_cpp_commit": head, "cmake_flags": CMAKE_FLAGS, "export": EXPORT,
    "platform": platform.platform(), "cpu": subprocess.run(["lscpu"], capture_output=True, text=True).stdout,
    "usr_bin_time_installed_by_notebook": TIME_INSTALLED,
    "evaluation_environment": subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True,
                                             text=True).stdout.splitlines(),
    "pilot_exit": PILOT,
}
json.dump(environment, open(f"{OUT}/environment.json", "w"), indent=2)

with open(f"{OUT}/outputs.sha256", "w") as listing:
    for path in sorted(glob.glob(f"{OUT}/**/*", recursive=True)):
        if os.path.isfile(path) and not path.endswith("outputs.sha256"):
            listing.write(f"{sha256(path)}  {os.path.relpath(path, OUT)}\\n")

print(open(f"{OUT}/outputs.sha256").read())

if PILOT != 0:
    raise SystemExit(f"the pilot stopped with exit {PILOT}; log the run before anything else")
"""),
]

notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


def render() -> str:
    return json.dumps(notebook, indent=1) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with the committed notebook instead of writing")
    parser.add_argument("--out", type=Path, default=NOTEBOOK)
    args = parser.parse_args(argv)

    if args.check:
        same = args.out.exists() and args.out.read_text(encoding="utf-8") == render()
        print(f"{args.out}: {'up to date' if same else 'differs from the generator'}")
        return 0 if same else 1

    args.out.write_text(render(), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
