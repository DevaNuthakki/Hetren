"""The hetren-cli image's Dockerfile, image checks and CI job agree with the CLI and the validated settings.

Building the image is CI's docker job (and ``docker/hetren-cli/check-image.sh`` locally); these tests read files only.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re

from packages.hetren_cli import inputs
from packages.hetren_serving.export import LLAMA_CPP_COMMIT


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = (REPO_ROOT / "docker/hetren-cli/Dockerfile").read_text(encoding="utf-8")
CHECK_SCRIPT = REPO_ROOT / "docker/hetren-cli/check-image.sh"
FIXTURES = REPO_ROOT / "tests/fixtures/hetren_cli"


def _stage(name: str) -> str:
    """One stage's text, from its FROM line to the next FROM."""
    match = re.search(rf"^FROM .* AS {name}\n(.*?)(?=^FROM |\Z)", DOCKERFILE, re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def _module_file(name: str) -> Path | None:
    base = REPO_ROOT / Path(*name.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _imports(path: Path, module: str) -> set[str]:
    names = set()
    package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]

    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):  # function bodies included (lazy imports)
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""

            if node.level:
                parts = package.split(".")[: len(package.split(".")) - (node.level - 1)]
                base = ".".join(parts + ([node.module] if node.module else []))

            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)

    return {n for n in names if n.startswith("packages.")}


def cli_closure() -> set[str]:
    """Every repository module the CLI's modules can import, statically."""
    start = [f"packages.hetren_cli.{p.stem}" if p.name != "__init__.py" else "packages.hetren_cli"
             for p in (REPO_ROOT / "packages/hetren_cli").glob("*.py")]
    seen, stack = set(), list(start)

    while stack:
        name = stack.pop()

        if name in seen:
            continue

        path = _module_file(name)

        if path is None:
            continue  # a name imported from a module (a function or constant), not a module

        seen.add(name)
        parts = name.split(".")
        stack.extend(".".join(parts[:i]) for i in range(2, len(parts)))  # parent packages run their __init__
        stack.extend(_imports(path, name))

    return seen


def _folder(module: str) -> str:
    parts = module.split(".")
    return "/".join(parts[:3] if parts[1] == "core" else parts[:2])


def copied_packages() -> list[str]:
    return re.findall(r"^COPY (packages/\S+) \1$", _stage("runtime"), re.MULTILINE)


def test_the_image_copies_exactly_the_folders_the_cli_imports():
    assert sorted({_folder(m) for m in cli_closure()}) == sorted(copied_packages())
    assert "packages/hetren_cli" in copied_packages()


def test_no_evaluator_environment_verifier_or_data_is_copied():
    runtime = _stage("runtime")

    for forbidden in ("support_evaluator", "verification", "environments", "artifacts", "COPY . "):
        assert forbidden not in runtime, forbidden

    assert not any(_folder(m).startswith(("packages/support_", "packages/verification")) for m in cli_closure())


def test_base_images_are_pinned_amd64_digests():
    assert re.search(r"^ARG PYTHON_IMAGE=python:3\.13-slim-bookworm@sha256:[0-9a-f]{64}$", DOCKERFILE, re.MULTILINE)
    assert re.search(r"^ARG DEBIAN_IMAGE=debian:bookworm-slim@sha256:[0-9a-f]{64}$", DOCKERFILE, re.MULTILINE)
    froms = re.findall(r"^FROM .*$", DOCKERFILE, re.MULTILINE)
    assert froms and all("--platform=linux/amd64" in line or line == "FROM runtime AS check" for line in froms)


def test_llama_cpp_is_the_pinned_commit_built_for_a_fixed_cpu_feature_set():
    pins = set(re.findall(r"^ARG LLAMA_CPP_COMMIT=([0-9a-f]{40})$", DOCKERFILE, re.MULTILINE))
    manifest = json.loads((REPO_ROOT / "docs/milestone-4/export.manifest.json").read_text(encoding="utf-8"))
    assert pins == {LLAMA_CPP_COMMIT} == {manifest["llama_cpp"]["commit"]}
    assert 'test "$(git rev-parse HEAD)" = "${LLAMA_CPP_COMMIT}"' in DOCKERFILE

    build = _stage("llama-build")
    for flag in ("-DGGML_NATIVE=OFF", "-DGGML_AVX=ON", "-DGGML_AVX2=ON", "-DGGML_FMA=ON", "-DGGML_F16C=ON",
                 "-DGGML_BMI2=ON", "-DGGML_AVX512=OFF", "-DGGML_BLAS=OFF", "-DGGML_OPENMP=ON",
                 "-DGGML_CPU_ALL_VARIANTS=OFF", "-DLLAMA_OPENSSL=OFF", "-DBUILD_SHARED_LIBS=OFF"):
        assert flag in build, flag

    assert "--target llama-server" in build
    # The version string comes from git, not from set values: the whole history is cloned (blobless).
    assert 'git clone -q --filter=blob:none --no-checkout "${LLAMA_CPP_REPO}" llama.cpp' in build
    assert "--depth" not in build and "LLAMA_BUILD_NUMBER" not in DOCKERFILE and "LLAMA_BUILD_COMMIT" not in DOCKERFILE
    assert '"$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"' in build


def test_the_required_cpu_flags_are_the_build_features_the_cli_checks():
    flags = re.search(r'HETREN_REQUIRED_CPU_FLAGS="([^"]+)"', DOCKERFILE).group(1)
    assert flags == "avx2 fma f16c"
    build = _stage("llama-build")
    assert all(f"-DGGML_{flag.upper()}=ON" in build for flag in flags.split())


def test_python_dependencies_are_exactly_the_pinned_cli_requirements():
    deps = _stage("python-deps")
    assert "COPY requirements-cli.txt" in deps
    assert "--no-deps -r /tmp/requirements-cli.txt" in deps


def test_the_runtime_is_non_root_offline_ready_and_labelled():
    runtime = _stage("runtime")
    assert "USER 10001:10001" in runtime and "useradd --uid 10001" in runtime
    assert 'ENTRYPOINT ["hetren"]' in runtime and "PYTHONPATH=/app" in runtime
    assert "HETREN_CACHE=/models" in runtime and "HETREN_LLAMA_SERVER=/usr/local/bin/llama-server" in runtime
    assert 'io.hetren.llama-cpp.commit="${LLAMA_CPP_COMMIT}"' in runtime
    wrapper = (REPO_ROOT / "docker/hetren-cli/hetren").read_text(encoding="utf-8")
    assert 'exec python -m packages.hetren_cli "$@"' in wrapper


def test_the_check_stage_uses_the_repository_not_the_images_cli_copy():
    check = _stage("check")
    assert "requirements-gguf-pilot.txt" in check and " time" in check
    assert "ENV PYTHONPATH=\n" in check and "WORKDIR /repo" in check


def test_the_image_check_script_expects_the_copied_packages_and_is_executable():
    assert os.access(CHECK_SCRIPT, os.X_OK)
    script = CHECK_SCRIPT.read_text(encoding="utf-8")
    listed = sorted({folder.split("/")[1] for folder in copied_packages()})
    assert repr(listed).replace("'", "'") in script.replace("\\[", "[").replace("\\]", "]")
    for absent in ("packages.support_evaluator", "packages.verification", "environments", "agents", "torch"):
        assert absent in script


def test_the_image_check_fixtures_are_what_the_checks_say():
    compact = json.loads((FIXTURES / "compact_first_step.json").read_text(encoding="utf-8"))
    assert inputs.from_compact(compact) == compact
    trace = json.loads((FIXTURES / "sdk_trace.json").read_text(encoding="utf-8"))
    assert inputs.is_sdk_trace(trace)


def _job(workflow: str, name: str) -> str:
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z_-]+:\n|\Z)", workflow.split("\njobs:\n", 1)[1],
                      re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def test_ci_checks_the_image_on_every_push_with_read_only_permissions():
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    triggers = workflow.split("\njobs:", 1)[0]
    assert "      - 'v[0-9]+.[0-9]+.[0-9]+'\n      - 'v[0-9]+.[0-9]+.[0-9]+-rc.[0-9]+'\n" in triggers
    assert "'v*'" not in triggers  # milestone tags must not reach the publish job
    job = _job(workflow, "docker")
    assert not re.search(r"^    if:", job, re.MULTILINE)  # every push
    assert "    permissions:\n      contents: read\n\n" in job and "packages:" not in job
    for line in ("file: docker/hetren-cli/Dockerfile", "target: runtime", "platforms: linux/amd64", "load: true",
                 "push: false", "cache-to: type=gha,scope=hetren-cli,mode=max",
                 "docker/hetren-cli/check-image.sh hetren-cli:ci"):
        assert line in job, line
    assert "login-action" not in job and "docker push" not in job


def test_publishing_is_its_own_job_on_v_tags_and_pushes_only_the_image_it_checked():
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    job = _job(workflow, "publish")
    assert "    needs: docker\n" in job and "    if: startsWith(github.ref, 'refs/tags/v')\n" in job
    assert "      packages: write\n" in job
    assert "cache-from: type=gha,scope=hetren-cli" in job and "cache-to" not in job
    assert (job.index('python3 scripts/check_release_tag.py "$GITHUB_REF_NAME"') < job.index("docker/build-push-action")
            < job.index("check-image.sh hetren-cli:release") < job.index("docker/login-action") < job.index("docker push"))
    assert 'docker tag hetren-cli:release "$target"' in job
    assert 'target="ghcr.io/devanuthakki/hetren-cli:${GITHUB_REF_NAME}"' in job
    others = [_job(workflow, name) for name in ("repository", "slow", "docker")]
    assert not any("packages: write" in other or "docker push" in other for other in others)
