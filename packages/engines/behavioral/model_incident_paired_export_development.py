"""Marker-committed paired exports for offline synthetic incident evidence.

A pair is considered published only after its report, source bundle, and
completion manifest all exist and pass independent read-only verification.

Publication uses create-exclusive files; it never overwrites or automatically
deletes an orphaned artifact. Missing/invalid manifests are not accepted.

This module does not authenticate model providers or genuine executions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import re
import stat

from packages.contracts import ContractError
from packages.engines.behavioral import (
    model_incident_report_cli_development as report_cli,
)
from packages.engines.behavioral import (
    model_incident_source_bundle_development as source_bundle,
)

PAIR_RECORD_TYPE = "SyntheticIncidentDevelopmentEvidencePair"
PAIR_SCHEMA_VERSION = 1
MAX_MARKER_BYTES = 8192
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")

_READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def _fail(reason: str) -> None:
    raise ContractError(f"synthetic development evidence pair: {reason}")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ContractError("invalid paired evidence JSON") from exc


def _anchor(
    actual: str,
    expected: str | None,
    label: str,
) -> None:
    if expected is None:
        return
    if (
        type(expected) is not str
        or _DIGEST.fullmatch(expected) is None
    ):
        _fail(f"invalid trusted {label}")
    if not hmac.compare_digest(actual, expected):
        _fail(f"{label} mismatch")


def _names(
    destination: str,
) -> tuple[str, str, str]:
    report_name = report_cli._file_name(destination)
    stem = report_name[:-5]

    if stem.endswith((".source", ".pair")):
        _fail("destination must name the primary evaluation report")

    source_name = stem + ".source.json"
    marker_name = stem + ".pair.json"

    for name in (source_name, marker_name):
        report_cli._file_name(report_cli.REPORT_PREFIX + name)

    if len({report_name, source_name, marker_name}) != 3:
        _fail("paired filenames are not distinct")

    return report_name, source_name, marker_name


def _must_be_absent(directory_fd: int, name: str) -> None:
    try:
        os.stat(
            name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    _fail(f"destination already exists: {name}")


def _read_regular(
    directory_fd: int,
    name: str,
    limit: int,
) -> bytes:
    fd = os.open(name, _READ_FLAGS, dir_fd=directory_fd)
    try:
        before = os.fstat(fd)

        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_mode & 0o077
            or not 0 < before.st_size <= limit
        ):
            _fail("unsafe or oversized evidence file")

        with os.fdopen(os.dup(fd), "rb") as stream:
            raw = stream.read(limit + 1)

        after = os.fstat(fd)

        if (
            len(raw) != before.st_size
            or len(raw) != after.st_size
            or before.st_ino != after.st_ino
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
            or before.st_nlink != after.st_nlink
        ):
            _fail("evidence file changed during read")

        return raw
    finally:
        os.close(fd)


def _unique_pairs(pairs):
    output = {}

    for key, value in pairs:
        if key in output:
            _fail("duplicate completion-manifest key")
        output[key] = value

    return output


def _parse_marker(raw: bytes) -> dict:
    if not 0 < len(raw) <= MAX_MARKER_BYTES:
        _fail("completion manifest size invalid")

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: _fail(
                "nonfinite completion-manifest number"
            ),
        )

        if _canonical(parsed) != raw:
            _fail("noncanonical completion manifest")

    except ContractError:
        raise
    except (
        UnicodeError,
        ValueError,
        TypeError,
        RecursionError,
    ) as exc:
        raise ContractError(
            "invalid completion-manifest JSON"
        ) from exc

    if type(parsed) is not dict:
        _fail("completion manifest must be an object")

    return parsed


@dataclass(frozen=True)
class VerifiedPairedDevelopmentEvidence:
    report_filename: str
    source_filename: str
    marker_filename: str
    report_sha256: str
    source_sha256: str
    marker_sha256: str
    manifest_sha256: str
    evaluation_sha256: str
    suite_evidence_sha256: str
    case_count: int
    correct_count: int
    provider_authenticated: bool = False


def _make_marker(
    report_name: str,
    source_name: str,
    report_raw: bytes,
    source_raw: bytes,
    verified,
) -> bytes:
    return _canonical({
        "record_type": PAIR_RECORD_TYPE,
        "schema_version": PAIR_SCHEMA_VERSION,
        "development_only": True,
        "publication_state": "complete",
        "report_filename": report_name,
        "source_filename": source_name,
        "report_sha256": _sha(report_raw),
        "source_sha256": _sha(source_raw),
        "manifest_sha256": verified.manifest_sha256,
        "evaluation_sha256": verified.evaluation_sha256,
        "suite_evidence_sha256": verified.suite_evidence_sha256,
    })


def verify_paired_development_evidence(
    report_destination: str,
    *,
    expected_marker_sha256: str | None = None,
    expected_report_sha256: str | None = None,
    expected_source_sha256: str | None = None,
) -> VerifiedPairedDevelopmentEvidence:
    """Read and verify a complete pair without executing the control suite."""
    report_name, source_name, marker_name = _names(
        report_destination
    )

    directory_fd = report_cli._report_directory_fd(
        create=False
    )

    try:
        # The marker is the publication commit record.
        # An absent marker means there is no accepted complete pair.
        marker_raw = _read_regular(
            directory_fd,
            marker_name,
            MAX_MARKER_BYTES,
        )

        marker = _parse_marker(marker_raw)

        _anchor(
            _sha(marker_raw),
            expected_marker_sha256,
            "completion-manifest SHA-256",
        )

        if (
            set(marker) != {
                "record_type",
                "schema_version",
                "development_only",
                "publication_state",
                "report_filename",
                "source_filename",
                "report_sha256",
                "source_sha256",
                "manifest_sha256",
                "evaluation_sha256",
                "suite_evidence_sha256",
            }
            or marker["record_type"] != PAIR_RECORD_TYPE
            or type(marker["schema_version"]) is not int
            or marker["schema_version"] != PAIR_SCHEMA_VERSION
            or marker["development_only"] is not True
            or marker["publication_state"] != "complete"
            or marker["report_filename"] != report_name
            or marker["source_filename"] != source_name
        ):
            _fail("completion-manifest contract mismatch")

        for field in (
            "report_sha256",
            "source_sha256",
            "manifest_sha256",
            "evaluation_sha256",
            "suite_evidence_sha256",
        ):
            value = marker[field]
            if (
                type(value) is not str
                or _DIGEST.fullmatch(value) is None
            ):
                _fail(f"invalid manifest field: {field}")

        report_raw = _read_regular(
            directory_fd,
            report_name,
            report_cli.MAX_REPORT_BYTES,
        )

        source_raw = _read_regular(
            directory_fd,
            source_name,
            source_bundle.MAX_BUNDLE_BYTES,
        )

    finally:
        os.close(directory_fd)

    _anchor(
        _sha(report_raw),
        marker["report_sha256"],
        "published report SHA-256",
    )

    _anchor(
        _sha(source_raw),
        marker["source_sha256"],
        "published source SHA-256",
    )

    _anchor(
        _sha(report_raw),
        expected_report_sha256,
        "trusted report SHA-256",
    )

    _anchor(
        _sha(source_raw),
        expected_source_sha256,
        "trusted source SHA-256",
    )

    verified = source_bundle.verify_synthetic_source_bundle(
        source_raw,
        report_raw,
        expected_bundle_sha256=marker["source_sha256"],
        expected_report_sha256=marker["report_sha256"],
    )

    if (
        verified.manifest_sha256 != marker["manifest_sha256"]
        or verified.evaluation_sha256
        != marker["evaluation_sha256"]
        or verified.suite_evidence_sha256
        != marker["suite_evidence_sha256"]
        or verified.case_count != 8
        or verified.correct_count != 2
        or verified.provider_authenticated is not False
    ):
        _fail("recomputed source evidence contradicts completion manifest")

    return VerifiedPairedDevelopmentEvidence(
        report_filename=report_name,
        source_filename=source_name,
        marker_filename=marker_name,
        report_sha256=_sha(report_raw),
        source_sha256=_sha(source_raw),
        marker_sha256=_sha(marker_raw),
        manifest_sha256=verified.manifest_sha256,
        evaluation_sha256=verified.evaluation_sha256,
        suite_evidence_sha256=verified.suite_evidence_sha256,
        case_count=verified.case_count,
        correct_count=verified.correct_count,
        provider_authenticated=False,
    )


def export_paired_development_evidence(
    report_destination: str,
) -> VerifiedPairedDevelopmentEvidence:
    """Publish report and source first; publish completion marker last.

    If publication is interrupted, orphan files may remain. They must
    not be treated as a complete pair and are never overwritten or
    automatically removed. Verification requires the final marker.
    """
    report_name, source_name, marker_name = _names(
        report_destination
    )

    # Exactly one offline execution produces BOTH documents.
    suite = report_cli.run_synthetic_control_suite()

    report_raw = report_cli.serialize_portable_development_report(
        suite
    )

    report_cli.verify_portable_development_report(report_raw)

    source_raw = source_bundle.serialize_synthetic_source_bundle(
        suite,
        report_raw,
    )

    verified = source_bundle.verify_synthetic_source_bundle(
        source_raw,
        report_raw,
        expected_bundle_sha256=_sha(source_raw),
        expected_report_sha256=_sha(report_raw),
    )

    marker_raw = _make_marker(
        report_name,
        source_name,
        report_raw,
        source_raw,
        verified,
    )

    if not 0 < len(marker_raw) <= MAX_MARKER_BYTES:
        _fail("completion manifest exceeds size limit")

    directory_fd = report_cli._report_directory_fd(
        create=True
    )

    try:
        for name in (report_name, source_name, marker_name):
            _must_be_absent(directory_fd, name)

        # No existing file may be replaced. The marker is published
        # ONLY after both documents have been fully published.
        report_cli._publish_new(
            directory_fd,
            report_name,
            report_raw,
        )

        report_cli._publish_new(
            directory_fd,
            source_name,
            source_raw,
        )

        if (
            _read_regular(
                directory_fd,
                report_name,
                report_cli.MAX_REPORT_BYTES,
            ) != report_raw
            or _read_regular(
                directory_fd,
                source_name,
                source_bundle.MAX_BUNDLE_BYTES,
            ) != source_raw
        ):
            _fail("published source/report bytes differ")

        report_cli._publish_new(
            directory_fd,
            marker_name,
            marker_raw,
        )

    finally:
        os.close(directory_fd)

    # This second read revalidates stored bytes, without source calls.
    return verify_paired_development_evidence(
        report_destination,
        expected_marker_sha256=_sha(marker_raw),
        expected_report_sha256=_sha(report_raw),
        expected_source_sha256=_sha(source_raw),
    )
