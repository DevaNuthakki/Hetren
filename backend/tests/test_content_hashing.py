from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.content_hashing import (
    ContentHashingError,
    calculate_content_sha256,
)


def test_calculates_sha256_and_byte_length(
    tmp_path: Path,
):
    path = tmp_path / "artifact.bin"
    content = b"hetren-content-hashing"

    path.write_bytes(content)

    digest, byte_length = (
        calculate_content_sha256(path)
    )

    assert digest == hashlib.sha256(
        content
    ).hexdigest()

    assert byte_length == len(content)


def test_chunk_size_does_not_change_result(
    tmp_path: Path,
):
    path = tmp_path / "chunked.bin"
    content = b"0123456789" * 100

    path.write_bytes(content)

    assert calculate_content_sha256(
        path
    ) == calculate_content_sha256(
        path,
        chunk_size=7,
    )


def test_empty_file_is_hashed_deterministically(
    tmp_path: Path,
):
    path = tmp_path / "empty.bin"

    path.write_bytes(b"")

    digest, byte_length = (
        calculate_content_sha256(path)
    )

    assert digest == hashlib.sha256(
        b""
    ).hexdigest()

    assert byte_length == 0


@pytest.mark.parametrize(
    "chunk_size",
    [
        0,
        -1,
        True,
    ],
)
def test_rejects_invalid_chunk_size(
    tmp_path: Path,
    chunk_size,
):
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"value")

    with pytest.raises(
        ContentHashingError,
        match="chunk_size must be positive",
    ):
        calculate_content_sha256(
            path,
            chunk_size=chunk_size,
        )
