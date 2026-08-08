import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import UploadFile


DEFAULT_UPLOAD_CHUNK_SIZE = 1024 * 1024


class UploadTooLargeError(ValueError):
    """Raised when an uploaded file exceeds its configured byte limit."""


def _validate_limit(max_bytes: int) -> int:
    if (
        isinstance(max_bytes, bool)
        or not isinstance(max_bytes, int)
        or max_bytes <= 0
    ):
        raise ValueError(
            "Upload byte limit must be a positive integer."
        )

    return max_bytes


async def read_upload_bytes_limited(
    upload: UploadFile,
    *,
    max_bytes: int,
    label: str,
    chunk_size: int = DEFAULT_UPLOAD_CHUNK_SIZE,
) -> bytes:
    """
    Read a small upload while enforcing the limit during streaming.

    Intended for bounded text-like inputs that must eventually be
    decoded in memory.
    """
    validated_limit = _validate_limit(max_bytes)

    if chunk_size <= 0:
        raise ValueError(
            "Upload chunk size must be positive."
        )

    content = bytearray()
    observed_bytes = 0

    while True:
        chunk = await upload.read(chunk_size)

        if not chunk:
            break

        observed_bytes += len(chunk)

        if observed_bytes > validated_limit:
            raise UploadTooLargeError(
                f"{label} exceeds the configured upload limit."
            )

        content.extend(chunk)

    return bytes(content)


async def write_upload_file_limited(
    upload: UploadFile,
    destination: str | Path,
    *,
    max_bytes: int,
    label: str,
    chunk_size: int = DEFAULT_UPLOAD_CHUNK_SIZE,
) -> int:
    """
    Stream an upload to a temporary file and atomically publish it.

    No complete copy of the upload is retained in application memory.
    The temporary file is removed on validation or write failure.
    """
    validated_limit = _validate_limit(max_bytes)

    if chunk_size <= 0:
        raise ValueError(
            "Upload chunk size must be positive."
        )

    destination_path = Path(destination)
    destination_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path: Path | None = None
    observed_bytes = 0

    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=destination_path.parent,
            prefix=f".{destination_path.name}.",
            suffix=".upload",
            delete=False,
        ) as temporary_file:
            temp_path = Path(temporary_file.name)

            while True:
                chunk = await upload.read(chunk_size)

                if not chunk:
                    break

                observed_bytes += len(chunk)

                if observed_bytes > validated_limit:
                    raise UploadTooLargeError(
                        f"{label} exceeds the configured upload limit."
                    )

                temporary_file.write(chunk)

            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(
            temp_path,
            destination_path,
        )

        temp_path = None

        return observed_bytes
    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()
