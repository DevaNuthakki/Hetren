"""Infrastructure-neutral file content hashing helpers.

This module intentionally has no database, application-settings, HTTP,
ASR-provider, or persistence dependencies.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


DEFAULT_CONTENT_HASH_CHUNK_SIZE = 1024 * 1024


class ContentHashingError(ValueError):
    """Raised when content hashing configuration is invalid."""


def calculate_content_sha256(
    path: str | Path,
    *,
    chunk_size: int = DEFAULT_CONTENT_HASH_CHUNK_SIZE,
) -> tuple[str, int]:
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or chunk_size <= 0
    ):
        raise ContentHashingError(
            "chunk_size must be positive."
        )

    file_path = Path(path)

    digest = hashlib.sha256()
    byte_length = 0

    with file_path.open("rb") as source:
        while True:
            chunk = source.read(
                chunk_size
            )

            if not chunk:
                break

            digest.update(
                chunk
            )
            byte_length += len(
                chunk
            )

    return (
        digest.hexdigest(),
        byte_length,
    )
