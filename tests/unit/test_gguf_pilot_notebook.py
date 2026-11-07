"""The Kaggle CPU pilot notebook keeps Amendment 2's pins and runs the pilot module on export 2's files."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from packages.hetren_serving import export
from packages.support_evaluator import gguf_pilot


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT / "notebooks/milestone-4/gguf_pilot.ipynb"


def _code() -> list[str]:
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    return ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]


def test_every_code_cell_is_python():
    for source in _code():
        ast.parse(source)


def test_pins_equal_the_export_module_and_the_committed_manifest():
    source = "\n".join(_code())
    manifest = hashlib.sha256((ROOT / gguf_pilot.MANIFEST).read_bytes()).hexdigest()
    assert f'LLAMA_CPP_COMMIT = "{export.LLAMA_CPP_COMMIT}"' in source
    assert f'EXPORT_MANIFEST_SHA256 = "{manifest}"' in source
    assert 'f"{WORK}/docs/milestone-4/export.manifest.json"' in source


def test_llama_cpp_is_built_with_the_exports_cpu_only_flags():
    source = "\n".join(_code())
    export_notebook = "\n".join("".join(c["source"]) for c in json.loads(
        (ROOT / "notebooks/milestone-4/gguf_export.ipynb").read_text(encoding="utf-8"))["cells"])
    flags = next(line for line in source.splitlines() if line.startswith("CMAKE_FLAGS = "))
    assert flags in export_notebook
    assert '"--target", "llama-server"' in source


def test_the_pilot_module_runs_on_kaggle_with_the_pilot_requirements_and_no_gpu():
    source = "\n".join(_code())
    assert '"-r", f"{WORK}/requirements-gguf-pilot.txt"' in source
    assert ('[sys.executable, "-m", "packages.support_evaluator.gguf_pilot", "run", "--platform", "kaggle",'
            in source)
    assert '"--gguf-dir", EXPORT, "--tokenizer", f"{EXPORT}/tokenizer", "--llama-cpp", LLAMA' in source
    assert "STOP: a GPU is attached" in source
    assert '"apt-get", "install", "-y", "-qq", "time"' in source
    assert "torch" not in (ROOT / "requirements-gguf-pilot.txt").read_text(encoding="utf-8").split("\n# The episode")[1]


def test_the_bundle_search_skips_code_copies_inside_attached_outputs(tmp_path):
    cell = _code()[0]
    function = cell[cell.index("def earlier_session"):cell.index("def sha256")]
    namespace = {"glob": __import__("glob")}
    exec(function, namespace)
    export_output = tmp_path / "hetren-gguf-export-2"
    (export_output / "gguf-export").mkdir(parents=True)
    (export_output / "hetren").mkdir()
    bundle = tmp_path / "hetren-m4-bundle-3"
    (bundle / "hetren").mkdir(parents=True)
    assert namespace["earlier_session"](f"{export_output}/hetren/BUNDLE.json")
    assert not namespace["earlier_session"](f"{bundle}/hetren/BUNDLE.json")
    assert not namespace["earlier_session"](f"{tmp_path}/hetren-m4-bundle-3/BUNDLE.json")


def test_outputs_are_listed_and_a_stopped_pilot_fails_the_notebook():
    source = "\n".join(_code())
    assert 'f"{OUT}/outputs.sha256"' in source and 'f"{OUT}/environment.json"' in source
    assert "if PILOT != 0:" in source


def test_the_committed_notebook_is_the_generators_output():
    import subprocess
    import sys

    result = subprocess.run([sys.executable, str(ROOT / "scripts/make_gguf_pilot_notebook.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
