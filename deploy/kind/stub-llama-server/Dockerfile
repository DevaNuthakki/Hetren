# check=skip=FromPlatformFlagConstDisallowed
# The kind test's stand-in for llama-server (deploy/kind/stub-llama-server/stub_llama_server.py). CI only.
ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:f3dac913ab53b78c64f26d5518fcd7043d5a1a46522d6a493b598c3ed12f62a6
FROM --platform=linux/amd64 ${PYTHON_IMAGE}
COPY stub_llama_server.py /stub/stub_llama_server.py
USER 10001:10001
ENTRYPOINT ["python", "/stub/stub_llama_server.py"]
