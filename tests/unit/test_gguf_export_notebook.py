"""The export notebook keeps Amendment 2's pins and the operator's decisions (2026-11-07)."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from packages.hetren_serving import export


NOTEBOOK = Path(__file__).resolve().parents[2] / "notebooks/milestone-4/gguf_export.ipynb"


def _code() -> list[str]:
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    return ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]


def test_every_code_cell_is_python_apart_from_pip_lines():
    for source in _code():
        ast.parse("\n".join(line for line in source.splitlines() if not line.lstrip().startswith("!")))


def test_pins_equal_the_export_modules():
    source = "\n".join(_code())
    for value in (export.CHOSEN["state_sha256"], export.CHOICE_SHA256, export.LLAMA_CPP_COMMIT):
        assert f'"{value}"' in source
    assert f"VARIANTS = {list(export.VARIANTS)!r}".replace("'", '"') in source
    assert f'f"{export.STEM}-{{variant.lower()}}.gguf"' in source  # the names export.commands writes


def test_merge_runs_on_one_t4_with_the_milestone_3_libraries():
    merge = next(s for s in _code() if '"merge"' in s)
    assert "transformers==4.56.2 accelerate==1.10.1 peft==0.17.1" in merge
    assert '"--device", "cuda"' in merge and '"CUDA_VISIBLE_DEVICES": "0"' in merge
    assert "[sys.executable, \"-m\", \"packages.hetren_serving.export\", \"merge\"" in merge


def test_conversion_uses_the_separate_venv_and_parity_the_evaluation_environment():
    source = "\n".join(_code())
    assert "requirements/requirements-convert_hf_to_gguf.txt" in source
    assert '[VPY, "-m", "packages.hetren_serving.export", "convert"' in source
    assert '[sys.executable, "-m", "packages.support_evaluator.gguf_parity"' in source
    assert '"--no-deps", f"{LLAMA}/gguf-py"' in source


def test_llama_cpp_is_built_cpu_only_and_the_server_runs_without_gpu_layers():
    source = "\n".join(_code())
    for flag in ("-DGGML_CUDA=OFF", "-DGGML_METAL=OFF", "-DGGML_BLAS=OFF", "-DGGML_NATIVE=OFF"):
        assert flag in source
    assert '"-ngl", "0"' in source and '"-np", "1"' in source


def test_outputs_keep_no_merged_weights_and_no_f16_gguf():
    source = "\n".join(_code())
    assert 'ignore_patterns("*.safetensors", "*.safetensors.index.json", "merge.json")' in source
    # Only the declared variants are copied from the conversion directory into the output.
    copied = [line.strip() for line in source.splitlines() if 'shutil.copy2(f"{GGUF}' in line]
    assert copied == ['shutil.copy2(f"{GGUF}/{name}", f"{OUT}/{name}")']
    assert "for variant, name in names.items():" in source and "f16" not in source.split("names = ", 1)[1].split("\n", 1)[0]
