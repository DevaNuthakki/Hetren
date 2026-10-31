"""Restricted CLI for exporting and inspecting offline development incident reports.

Only synthetic control-suite reports are accepted.  A digest checks document
integrity; it does not authenticate live provider decisions or source captures.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from typing import Sequence

from packages.contracts import ContractError
from packages.engines.behavioral.model_incident_control_suite_development import (
    run_synthetic_control_suite,
)
from packages.engines.behavioral.model_incident_portable_report_development import (
    VerifiedPortableDevelopmentReport,
    serialize_portable_development_report,
    verify_portable_development_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORT_SUBDIR = "development_incident_reports"
REPORT_PREFIX = "artifacts/development_incident_reports/"
MAX_REPORT_BYTES = 262144
_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,95}\.json\Z")
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW


def _failure(reason: str) -> None:
    raise ContractError(f"synthetic development report CLI: {reason}")


def _file_name(destination: str) -> str:
    """Only a canonical, repo-relative filename inside the ignored directory."""
    if not isinstance(destination, str) or not destination.startswith(REPORT_PREFIX):
        _failure("path must be under artifacts/development_incident_reports/")
    filename = destination[len(REPORT_PREFIX):]
    if _NAME.fullmatch(filename) is None or destination != REPORT_PREFIX + filename:
        _failure("invalid or noncanonical report filename")
    return filename


def _report_directory_fd(*, create: bool) -> int:
    # Directory descriptors and O_NOFOLLOW prevent traversal through symlinks.
    artifacts_fd = os.open(PROJECT_ROOT / "artifacts", _DIRECTORY_FLAGS)
    try:
        if create:
            try:
                os.mkdir(REPORT_SUBDIR, 0o700, dir_fd=artifacts_fd)
            except FileExistsError:
                pass
        return os.open(REPORT_SUBDIR, _DIRECTORY_FLAGS, dir_fd=artifacts_fd)
    finally:
        os.close(artifacts_fd)


def _read_from_directory(directory_fd: int, filename: str) -> bytes:
    fd = os.open(filename, _READ_FLAGS, dir_fd=directory_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_REPORT_BYTES:
            _failure("report must be a regular JSON file within the size limit")
        with os.fdopen(os.dup(fd), "rb") as stream:
            raw = stream.read(MAX_REPORT_BYTES + 1)
        after = os.fstat(fd)
        if (
            len(raw) != before.st_size
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
            or before.st_ino != after.st_ino
        ):
            _failure("report changed while being read")
        return raw
    finally:
        os.close(fd)


def _publish_new(directory_fd: int, filename: str, raw: bytes) -> None:
    # Prepare a complete private file, then atomically publish via a hard link.
    # os.link fails if the final filename already exists. No replace/overwrite.
    staging = ".pending-" + secrets.token_hex(16)
    fd = os.open(staging, _WRITE_FLAGS, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(
            staging, filename,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
    finally:
        os.unlink(staging, dir_fd=directory_fd)


def generate_development_report(destination: str) -> VerifiedPortableDevelopmentReport:
    filename = _file_name(destination)
    # The suite runs entirely offline; no provider transport is used.
    result = run_synthetic_control_suite()
    raw = serialize_portable_development_report(result)
    verified = verify_portable_development_report(raw)
    directory_fd = _report_directory_fd(create=True)
    try:
        _publish_new(directory_fd, filename, raw)
        stored = _read_from_directory(directory_fd, filename)
        if stored != raw:
            _failure("exported bytes did not match verified report")
    finally:
        os.close(directory_fd)
    return verified


def _verified_file(
    location: str, *, trusted_sha256: str | None = None,
) -> tuple[bytes, VerifiedPortableDevelopmentReport]:
    filename = _file_name(location)
    directory_fd = _report_directory_fd(create=False)
    try:
        raw = _read_from_directory(directory_fd, filename)
    finally:
        os.close(directory_fd)
    result = verify_portable_development_report(
        raw, expected_document_sha256=trusted_sha256,
    )
    return raw, result


def verify_development_report_file(
    location: str, *, trusted_sha256: str | None = None,
) -> VerifiedPortableDevelopmentReport:
    return _verified_file(location, trusted_sha256=trusted_sha256)[1]


def inspect_development_report_file(
    location: str, *, trusted_sha256: str | None = None,
) -> dict[str, object]:
    raw, result = _verified_file(location, trusted_sha256=trusted_sha256)
    payload = json.loads(raw)["payload"]
    cases = []
    for record in payload["case_records"]:
        score = record["score"]
        cases.append({
            "case_id": score["case_id"],
            "status": score["status"],
            "completed": score["completed"],
            "correct": score["correct"],
            "attempts": score["attempts"],
            "executed_actions": score["executed_actions"],
            "injected_failures": score["injected_failures"],
            "recovered_correctly": score["recovered_correctly"],
            "observed_sha256": score["observed_sha256"],
            "timeline_sha256": score["timeline_sha256"],
            "case_evidence_sha256": record["case_evidence_sha256"],
            "reported_tokens": score["complete_reported_tokens"],
        })
    return {
        "record_kind": "synthetic_development",
        "integrity_checked": True,
        "provider_authenticity_verified": False,
        "source_execution_replayed": False,
        "document_sha256": result.document_sha256,
        "manifest_sha256": result.manifest_sha256,
        "evaluation_sha256": result.evaluation_sha256,
        "summary": payload["summary"],
        "cases": cases,
        "limitations": list(result.limitations),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline synthetic incident report exporter and integrity checker"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Run offline controls and export a new report")
    generate.add_argument("--output", required=True, help=REPORT_PREFIX + "NAME.json")
    for command in ("verify", "inspect"):
        selected = commands.add_parser(command, help="Read an existing report without rerunning controls")
        selected.add_argument("--input", required=True, help=REPORT_PREFIX + "NAME.json")
        selected.add_argument("--sha256", default=None, help="Externally trusted document SHA-256")
    paired_generate = commands.add_parser(
        "generate-pair",
        help="Run offline controls and publish a replay-verifiable evidence pair",
    )
    paired_generate.add_argument(
        "--output", required=True, help=REPORT_PREFIX + "NAME.json",
    )
    paired_verify = commands.add_parser(
        "verify-pair",
        help="Verify a completed evidence pair without rerunning controls",
    )
    paired_verify.add_argument(
        "--input", required=True, help=REPORT_PREFIX + "NAME.json",
    )
    for part in ("marker", "report", "source"):
        paired_verify.add_argument(
            f"--{part}-sha256",
            default=None,
            help=f"Externally trusted {part} SHA-256",
        )
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            verified = generate_development_report(args.output)
            print("EXPORTED: synthetic development report")
            print("Path:", args.output)
            print("Document SHA256:", verified.document_sha256)
        elif args.command == "verify":
            verified = verify_development_report_file(
                args.input, trusted_sha256=args.sha256,
            )
            print("INTEGRITY PASS: synthetic development report (not provider authentication)")
            print("Document SHA256:", verified.document_sha256)
            print("Cases:", verified.case_count)
            print("Correct cases:", verified.correct_count)
            print("Externally anchored:", args.sha256 is not None)
        elif args.command == "generate-pair":
            # Lazy import avoids the paired-export module's CLI dependency cycle.
            from packages.engines.behavioral import (
                model_incident_paired_export_development as paired_export,
            )
            verified = paired_export.export_paired_development_evidence(
                args.output,
            )
            print("EXPORTED: replay-verifiable synthetic evidence pair")
            print("Report:", args.output)
            print("Source:", REPORT_PREFIX + verified.source_filename)
            print("Completion marker:", REPORT_PREFIX + verified.marker_filename)
            print("Report SHA256:", verified.report_sha256)
            print("Source SHA256:", verified.source_sha256)
            print("Completion marker SHA256:", verified.marker_sha256)
            print("Provider authenticated: False")
        elif args.command == "verify-pair":
            from packages.engines.behavioral import (
                model_incident_paired_export_development as paired_export,
            )
            verified = paired_export.verify_paired_development_evidence(
                args.input,
                expected_marker_sha256=args.marker_sha256,
                expected_report_sha256=args.report_sha256,
                expected_source_sha256=args.source_sha256,
            )
            print(
                "SOURCE REPLAY PASS: synthetic development evidence pair "
                "(not provider authentication)"
            )
            print("Report SHA256:", verified.report_sha256)
            print("Source SHA256:", verified.source_sha256)
            print("Completion marker SHA256:", verified.marker_sha256)
            print("Cases:", verified.case_count)
            print("Correct cases:", verified.correct_count)
            print("Provider authenticated: False")
            print(
                "Externally anchored:",
                any(
                    value is not None
                    for value in (
                        args.marker_sha256,
                        args.report_sha256,
                        args.source_sha256,
                    )
                ),
            )
        else:
            inspection = inspect_development_report_file(
                args.input, trusted_sha256=args.sha256,
            )
            print(json.dumps(inspection, indent=2, sort_keys=True, allow_nan=False))
    except (ContractError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
