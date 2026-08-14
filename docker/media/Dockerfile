FROM python@sha256:00faa2debb87529f9f0764e9491d8ba400a3678976616c3bd7cb193745ac20d1

ARG FFMPEG_DEBIAN_VERSION=7:5.1.9-0+deb12u1
ARG FFPROBE_REPORTED_VERSION=5.1.9-0+deb12u1

LABEL org.opencontainers.image.title="Hetren Media CI"
LABEL org.opencontainers.image.description="Pinned Python and FFmpeg/FFprobe environment for Hetren media verification"
LABEL io.hetren.media.python.version="3.13.15"
LABEL io.hetren.media.ffmpeg.debian-version="${FFMPEG_DEBIAN_VERSION}"
LABEL io.hetren.media.ffprobe.reported-version="${FFPROBE_REPORTED_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LC_ALL=C \
    LANG=C

RUN set -eux; \
    apt-get update; \
    apt-get install -y \
        --no-install-recommends \
        "ffmpeg=${FFMPEG_DEBIAN_VERSION}"; \
    test "$(command -v ffprobe)" = "/usr/bin/ffprobe"; \
    test "$(command -v ffmpeg)" = "/usr/bin/ffmpeg"; \
    test "$(dpkg-query -W -f='${Version}' ffmpeg)" = "${FFMPEG_DEBIAN_VERSION}"; \
    ffprobe -version | head -1 | grep -F \
        "ffprobe version ${FFPROBE_REPORTED_VERSION}"; \
    ffmpeg -version | head -1 | grep -F \
        "ffmpeg version ${FFPROBE_REPORTED_VERSION}"; \
    python --version | grep -F "Python 3.13.15"; \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt \
     backend/requirements-dev.txt \
     /tmp/hetren-requirements/

RUN set -eux; \
    python -m pip install \
        --no-cache-dir \
        -r /tmp/hetren-requirements/requirements-dev.txt; \
    rm -rf /tmp/hetren-requirements

WORKDIR /workspace/backend

CMD ["python", "--version"]
