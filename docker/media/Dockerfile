FROM python@sha256:00faa2debb87529f9f0764e9491d8ba400a3678976616c3bd7cb193745ac20d1

ARG FFMPEG_DEBIAN_VERSION=7:5.1.9-0+deb12u1
ARG FFPROBE_REPORTED_VERSION=5.1.9-0+deb12u1
ARG ESPEAK_NG_DEBIAN_VERSION=1.51+dfsg-10+deb12u2
ARG ESPEAK_NG_EXECUTABLE_SHA256=0a2f26e328f1dd4cec926987d3dc22bf841879132fd3aa497dd4fcad0d4d77a3
ARG ESPEAK_NG_COPYRIGHT_SHA256=bf721eede49d50f84bd2c50f96888629ced572b66ad4087c7a224c4a5e1193bb

LABEL org.opencontainers.image.title="Hetren Media CI"
LABEL org.opencontainers.image.description="Pinned Python and FFmpeg/FFprobe environment for Hetren media verification"
LABEL io.hetren.media.python.version="3.13.15"
LABEL io.hetren.media.ffmpeg.debian-version="${FFMPEG_DEBIAN_VERSION}"
LABEL io.hetren.media.ffprobe.reported-version="${FFPROBE_REPORTED_VERSION}"
LABEL io.hetren.media.espeak-ng.debian-version="${ESPEAK_NG_DEBIAN_VERSION}"
LABEL io.hetren.media.espeak-ng.executable-sha256="${ESPEAK_NG_EXECUTABLE_SHA256}"
LABEL io.hetren.media.espeak-ng.copyright-sha256="${ESPEAK_NG_COPYRIGHT_SHA256}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LC_ALL=C \
    LANG=C

RUN set -eux; \
    apt-get update; \
    apt-get install -y \
        --no-install-recommends \
        "ffmpeg=${FFMPEG_DEBIAN_VERSION}" \
        "espeak-ng=${ESPEAK_NG_DEBIAN_VERSION}" \
        "espeak-ng-data=${ESPEAK_NG_DEBIAN_VERSION}" \
        "libespeak-ng1=${ESPEAK_NG_DEBIAN_VERSION}"; \
    test "$(command -v ffprobe)" = "/usr/bin/ffprobe"; \
    test "$(command -v ffmpeg)" = "/usr/bin/ffmpeg"; \
    test "$(command -v espeak-ng)" = "/usr/bin/espeak-ng"; \
    test "$(dpkg-query -W -f='${Version}' ffmpeg)" = "${FFMPEG_DEBIAN_VERSION}"; \
    test "$(dpkg-query -W -f='${Version}' espeak-ng)" = "${ESPEAK_NG_DEBIAN_VERSION}"; \
    test "$(dpkg-query -W -f='${Version}' espeak-ng-data)" = "${ESPEAK_NG_DEBIAN_VERSION}"; \
    test "$(dpkg-query -W -f='${Version}' libespeak-ng1)" = "${ESPEAK_NG_DEBIAN_VERSION}"; \
    test "$(sha256sum /usr/bin/espeak-ng | cut -d' ' -f1)" = "${ESPEAK_NG_EXECUTABLE_SHA256}"; \
    test "$(sha256sum /usr/share/doc/espeak-ng/copyright | cut -d' ' -f1)" = "${ESPEAK_NG_COPYRIGHT_SHA256}"; \
    ffprobe -version | head -1 | grep -F \
        "ffprobe version ${FFPROBE_REPORTED_VERSION}"; \
    ffmpeg -version | head -1 | grep -F \
        "ffmpeg version ${FFPROBE_REPORTED_VERSION}"; \
    espeak-ng --version | head -1 | grep -F \
        "eSpeak NG text-to-speech: 1.51"; \
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
