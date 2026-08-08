import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.upload_io import (
    UploadTooLargeError,
    read_upload_bytes_limited,
    write_upload_file_limited,
)


def _upload(
    content: bytes,
    *,
    filename: str = "sample.bin",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
    )


def test_read_upload_accepts_exact_limit() -> None:
    upload = _upload(b"12345678")

    content = asyncio.run(
        read_upload_bytes_limited(
            upload,
            max_bytes=8,
            label="Transcript",
            chunk_size=3,
        )
    )

    assert content == b"12345678"


def test_read_upload_rejects_limit_plus_one() -> None:
    upload = _upload(b"123456789")

    with pytest.raises(
        UploadTooLargeError,
        match="Transcript exceeds",
    ):
        asyncio.run(
            read_upload_bytes_limited(
                upload,
                max_bytes=8,
                label="Transcript",
                chunk_size=3,
            )
        )


def test_streamed_upload_accepts_exact_limit(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "audio.wav"

    byte_length = asyncio.run(
        write_upload_file_limited(
            _upload(b"12345678"),
            destination,
            max_bytes=8,
            label="Audio file",
            chunk_size=3,
        )
    )

    assert byte_length == 8
    assert destination.read_bytes() == b"12345678"


def test_streamed_upload_rejects_limit_plus_one_without_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "audio.wav"

    with pytest.raises(
        UploadTooLargeError,
        match="Audio file exceeds",
    ):
        asyncio.run(
            write_upload_file_limited(
                _upload(b"123456789"),
                destination,
                max_bytes=8,
                label="Audio file",
                chunk_size=3,
            )
        )

    assert not destination.exists()

    assert not list(
        tmp_path.glob(".audio.wav.*.upload")
    )
