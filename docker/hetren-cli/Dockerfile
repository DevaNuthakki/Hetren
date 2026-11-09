# check=skip=FromPlatformFlagConstDisallowed
# (the image is linux/amd64 only by design, so every FROM names that platform.)
# The hetren CLI image (Milestone 4, step 5): offline diagnosis with the validated GGUF on llama-server.
#
#   docker build -f docker/hetren-cli/Dockerfile --target runtime --build-arg HETREN_COMMIT=$(git rev-parse HEAD) \
#       -t hetren-cli:dev .
#
# linux/amd64 only; the CPU needs AVX2, FMA and F16C (llama.cpp is built for exactly that feature set, so every
# host runs the same kernels). Weights are not in the image: mount them at /models or run fetch-model.
# Stages: llama-build (llama.cpp at the pinned commit), python-deps (requirements-cli.txt, every package pinned),
# runtime (published), check (never published: adds the pilot environment for the Linux agreement check).

# Base images pinned by their linux/amd64 manifest digests (python:3.13-slim-bookworm and debian:bookworm-slim,
# resolved on 2026-11-09).
ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:f3dac913ab53b78c64f26d5518fcd7043d5a1a46522d6a493b598c3ed12f62a6
ARG DEBIAN_IMAGE=debian:bookworm-slim@sha256:c67e92c8099ba22853ab4cfda7cfb494d253d6012ca82dee98ba8976772af018

# --- llama.cpp ------------------------------------------------------------------------------------------------
FROM --platform=linux/amd64 ${DEBIAN_IMAGE} AS llama-build

ARG LLAMA_CPP_COMMIT=620d2225cc436ab0b001e3200e590e3b286ef9ab
ARG LLAMA_CPP_REPO=https://github.com/ggml-org/llama.cpp.git
ARG BUILD_JOBS=4

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# The whole commit history (a blobless clone: every commit and tree, file contents only for the checkout), so
# llama.cpp's own build script derives its version string from git (build 11669, commit 620d2225c), as on the
# Mac's validated build; a depth-1 clone would report build 1.
WORKDIR /src
RUN git clone -q --filter=blob:none --no-checkout "${LLAMA_CPP_REPO}" llama.cpp \
 && cd llama.cpp \
 && git checkout -q "${LLAMA_CPP_COMMIT}" \
 && test "$(git rev-parse HEAD)" = "${LLAMA_CPP_COMMIT}"

# CPU only, static, OpenMP, no BLAS, no HTTPS client; a fixed x86_64 feature set (AVX, AVX2, FMA, F16C, BMI2;
# no AVX-512), not the build machine's (GGML_NATIVE off).
RUN cd llama.cpp \
 && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
      -DGGML_NATIVE=OFF -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON -DGGML_BMI2=ON \
      -DGGML_AVX512=OFF -DGGML_BLAS=OFF -DGGML_OPENMP=ON -DGGML_CPU_ALL_VARIANTS=OFF -DGGML_BACKEND_DL=OFF \
      -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF \
 && cmake --build build --target llama-server -j "${BUILD_JOBS}" \
 && install -m 0755 build/bin/llama-server /usr/local/bin/llama-server \
 && mkdir -p /out \
 && printf '{"llama_cpp_commit": "%s", "build_number": %s, "build_commit": "%s", "version_from": "git (blobless clone of the whole history)", "compiler": "%s", "cmake": "%s", "cpu_features": "AVX AVX2 FMA F16C BMI2", "openmp": true, "blas": false}\n' \
      "$(git rev-parse HEAD)" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)" \
      "$(gcc --version | head -n 1)" "$(cmake --version | head -n 1)" > /out/build-info.json \
 && dpkg-query -W -f '${Package}=${Version}\n' build-essential cmake gcc g++ libgomp1 > /out/build-packages.txt

# --- Python environment ---------------------------------------------------------------------------------------
FROM --platform=linux/amd64 ${PYTHON_IMAGE} AS python-deps

COPY requirements-cli.txt /tmp/requirements-cli.txt
# --no-deps: every package must be pinned in the file, or the CLI fails to import (the build test catches it).
RUN python -m venv /opt/hetren \
 && /opt/hetren/bin/pip install --no-cache-dir --disable-pip-version-check --no-deps -r /tmp/requirements-cli.txt

# --- runtime (published) --------------------------------------------------------------------------------------
FROM --platform=linux/amd64 ${PYTHON_IMAGE} AS runtime

ARG HETREN_COMMIT=unknown
ARG LLAMA_CPP_COMMIT=620d2225cc436ab0b001e3200e590e3b286ef9ab

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --create-home --shell /usr/sbin/nologin hetren \
 && mkdir -p /models /usr/share/hetren \
 && chown hetren:hetren /models

COPY --from=python-deps /opt/hetren /opt/hetren
COPY --from=llama-build /usr/local/bin/llama-server /usr/local/bin/llama-server
COPY --from=llama-build /out/ /usr/share/hetren/

# Only what the CLI's imports reach (a test keeps this list equal to the import graph): no evaluator, verifier,
# environment, dataset or label is in the image.
WORKDIR /app
COPY packages/action_gateway packages/action_gateway
COPY packages/action_space packages/action_space
COPY packages/contracts packages/contracts
COPY packages/core/hetren_diagnosis packages/core/hetren_diagnosis
COPY packages/hetren_baselines packages/hetren_baselines
COPY packages/hetren_cli packages/hetren_cli
COPY packages/hetren_evidence packages/hetren_evidence
COPY packages/hetren_serving packages/hetren_serving
COPY requirements-cli.txt requirements-cli.txt
COPY --chmod=0755 docker/hetren-cli/hetren /usr/local/bin/hetren

ENV PATH=/opt/hetren/bin:${PATH} \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HETREN_CACHE=/models \
    HETREN_LLAMA_SERVER=/usr/local/bin/llama-server \
    HETREN_REQUIRED_CPU_FLAGS="avx2 fma f16c" \
    HETREN_COMMIT=${HETREN_COMMIT}

LABEL org.opencontainers.image.title="hetren-cli" \
      org.opencontainers.image.description="Offline diagnosis of support-workflow agent runs recorded with Hetren's OpenAI Agents SDK integration" \
      org.opencontainers.image.source="https://github.com/DevaNuthakki/Hetren" \
      org.opencontainers.image.revision="${HETREN_COMMIT}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      io.hetren.llama-cpp.commit="${LLAMA_CPP_COMMIT}"

USER 10001:10001
VOLUME ["/models"]
EXPOSE 8000
ENTRYPOINT ["hetren"]
CMD ["--help"]

# --- check (never published) ----------------------------------------------------------------------------------
# The Linux agreement check: the runtime image (the same llama-server binary) plus the pilot environment, with the
# repository mounted read-only at /repo and outputs at /out.
FROM runtime AS check

USER root
COPY requirements-gguf-pilot.txt /tmp/requirements-gguf-pilot.txt
RUN apt-get update \
 && apt-get install -y --no-install-recommends git time \
 && rm -rf /var/lib/apt/lists/* \
 && /opt/hetren/bin/pip install --no-cache-dir --disable-pip-version-check -r /tmp/requirements-gguf-pilot.txt \
 && git config --system --add safe.directory /repo
USER 10001:10001
# The mounted repository's packages only (not /app's copy of the CLI's).
ENV PYTHONPATH=
WORKDIR /repo
ENTRYPOINT []
CMD ["python", "-m", "packages.support_evaluator.linux_agreement", "--help"]
