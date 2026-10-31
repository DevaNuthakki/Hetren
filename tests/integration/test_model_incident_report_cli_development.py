"""Offline development report CLI: filesystem, integrity, and command tests."""

import hashlib
import json
import os
from pathlib import Path
import stat

import pytest

from packages.contracts import ContractError
import packages.engines.behavioral.model_incident_report_cli_development as cli


REPORT = cli.REPORT_PREFIX + "controls-001.json"
SECOND_REPORT = cli.REPORT_PREFIX + "controls-002.json"


@pytest.fixture(autouse=True)
def isolated_artifacts(tmp_path, monkeypatch):
    """Never exercise CLI filesystem operations against the real repository."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "artifacts").mkdir()
    monkeypatch.setattr(cli, "PROJECT_ROOT", sandbox)
    return sandbox


def report_directory(sandbox):
    return sandbox / "artifacts" / cli.REPORT_SUBDIR


def test_filename_accepts_expected_canonical_path(isolated_artifacts):
    assert cli._file_name(REPORT) == "controls-001.json"
    assert cli._file_name(SECOND_REPORT) == "controls-002.json"
    assert not report_directory(isolated_artifacts).exists()


@pytest.mark.parametrize("destination", [
    "controls-001.json", "/tmp/controls-001.json", "../controls-001.json",
    "artifacts/p09_4_scientific_arms/controls-001.json",
    "artifacts/development_incident_reports/../controls-001.json",
    "artifacts/development_incident_reports/sub/controls-001.json",
    "artifacts/development_incident_reports/.hidden.json",
    "artifacts/development_incident_reports/UPPER.json",
    "artifacts/development_incident_reports/controls-001.txt",
    "artifacts/development_incident_reports/controls-001.json/",
    "artifacts/development_incident_reports/controls-001.json/../else.json",
    "artifacts/development_incident_reports/controls-001.json\x00suffix",
    "artifacts/development_incident_reports/é.json",
    "artifacts/development_incident_reports/" + "z" * 100 + ".json",
    "artifacts\\development_incident_reports\\controls.json",
    "artifacts/development_incident_reports//controls.json",
    None,
    123,
])
def test_filename_rejects_unsafe_or_noncanonical_paths(isolated_artifacts, destination):
    with pytest.raises(ContractError):
        cli._file_name(destination)
    assert not report_directory(isolated_artifacts).exists()


def test_generate_creates_private_report_and_validates(isolated_artifacts):
    verified = cli.generate_development_report(REPORT)
    folder = report_directory(isolated_artifacts)
    target = folder / "controls-001.json"
    assert folder.is_dir()
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert target.is_file() and not target.is_symlink()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    raw = target.read_bytes()
    assert verified.document_sha256 == hashlib.sha256(raw).hexdigest()
    assert verified.case_count == 8
    assert verified.correct_count == 2
    assert cli.verify_development_report_file(REPORT) == verified
    assert sorted(path.name for path in folder.iterdir()) == [target.name]


def test_verify_and_inspect_preserve_file_bytes(isolated_artifacts):
    cli.generate_development_report(REPORT)
    target = report_directory(isolated_artifacts) / "controls-001.json"
    original = target.read_bytes()
    before = target.stat()
    verified = cli.verify_development_report_file(REPORT)
    inspection = cli.inspect_development_report_file(REPORT)
    after = target.stat()
    assert original == target.read_bytes()
    assert before.st_mtime_ns == after.st_mtime_ns
    assert verified.document_sha256 == inspection["document_sha256"]
    assert inspection["record_kind"] == "synthetic_development"
    assert inspection["integrity_checked"] is True
    assert inspection["provider_authenticity_verified"] is False
    assert inspection["source_execution_replayed"] is False
    assert inspection["summary"]["denominator_cases"] == 8
    assert inspection["summary"]["correct_cases"] == 2
    assert [case["case_id"] for case in inspection["cases"]] == [
        "correct", "wrong", "recovery", "repeat", "exhaust", "budget",
        "interrupt", "reject",
    ]
    assert inspection["cases"][1]["status"] == "completed"
    assert inspection["cases"][1]["correct"] is False
    assert all(case["reported_tokens"] is None for case in inspection["cases"])


def test_correct_trusted_digest_is_accepted(isolated_artifacts):
    verified = cli.generate_development_report(REPORT)
    assert cli.verify_development_report_file(
        REPORT, trusted_sha256=verified.document_sha256,
    ).document_sha256 == verified.document_sha256
    assert cli.inspect_development_report_file(
        REPORT, trusted_sha256=verified.document_sha256,
    )["document_sha256"] == verified.document_sha256


def test_wrong_or_invalid_trusted_digest_is_rejected(isolated_artifacts):
    cli.generate_development_report(REPORT)
    for trusted in ("0" * 64, "invalid"):
        with pytest.raises(ContractError):
            cli.verify_development_report_file(REPORT, trusted_sha256=trusted)
        with pytest.raises(ContractError):
            cli.inspect_development_report_file(REPORT, trusted_sha256=trusted)


def test_regeneration_refuses_overwrite_and_preserves_original(isolated_artifacts):
    first = cli.generate_development_report(REPORT)
    target = report_directory(isolated_artifacts) / "controls-001.json"
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        cli.generate_development_report(REPORT)
    assert target.read_bytes() == original
    assert cli.verify_development_report_file(REPORT) == first
    assert [path.name for path in target.parent.iterdir()] == [target.name]


def test_distinct_exports_are_kept_independently(isolated_artifacts):
    cli.generate_development_report(REPORT)
    cli.generate_development_report(SECOND_REPORT)
    folder = report_directory(isolated_artifacts)
    assert sorted(path.name for path in folder.iterdir()) == [
        "controls-001.json", "controls-002.json",
    ]
    for name in (REPORT, SECOND_REPORT):
        assert cli.verify_development_report_file(name).case_count == 8


def test_verify_missing_report_does_not_create_directory(isolated_artifacts):
    with pytest.raises(FileNotFoundError):
        cli.verify_development_report_file(REPORT)
    with pytest.raises(FileNotFoundError):
        cli.inspect_development_report_file(REPORT)
    assert not report_directory(isolated_artifacts).exists()


def test_existing_directory_at_filename_is_not_replaced(isolated_artifacts):
    folder = report_directory(isolated_artifacts)
    folder.mkdir()
    target = folder / "controls-001.json"
    target.mkdir()
    with pytest.raises(FileExistsError):
        cli.generate_development_report(REPORT)
    assert target.is_dir()
    assert sorted(path.name for path in folder.iterdir()) == [target.name]


def test_symlink_report_file_cannot_be_read_or_replaced(isolated_artifacts):
    folder = report_directory(isolated_artifacts)
    folder.mkdir()
    external = isolated_artifacts / "outside.json"
    external.write_bytes(b"historical-placeholder")
    target = folder / "controls-001.json"
    target.symlink_to(external)
    with pytest.raises(OSError):
        cli.verify_development_report_file(REPORT)
    with pytest.raises(OSError):
        cli.generate_development_report(REPORT)
    assert target.is_symlink()
    assert external.read_bytes() == b"historical-placeholder"
    assert sorted(path.name for path in folder.iterdir()) == [target.name]


def test_symlink_export_directory_rejected(isolated_artifacts):
    external = isolated_artifacts / "outside"
    external.mkdir()
    folder = report_directory(isolated_artifacts)
    folder.symlink_to(external, target_is_directory=True)
    with pytest.raises(OSError):
        cli.generate_development_report(REPORT)
    with pytest.raises(OSError):
        cli.verify_development_report_file(REPORT)
    assert list(external.iterdir()) == []
    assert folder.is_symlink()


def test_symlink_artifacts_directory_rejected(isolated_artifacts):
    artifacts = isolated_artifacts / "artifacts"
    artifacts.rmdir()
    external = isolated_artifacts / "outside"
    external.mkdir()
    artifacts.symlink_to(external, target_is_directory=True)
    with pytest.raises(OSError):
        cli.generate_development_report(REPORT)
    assert artifacts.is_symlink()
    assert list(external.iterdir()) == []


def test_empty_nonjson_and_oversized_files_rejected(isolated_artifacts):
    folder = report_directory(isolated_artifacts)
    folder.mkdir()
    target = folder / "controls-001.json"
    for raw in (b"", b"{}", b"X" * 262145):
        target.write_bytes(raw)
        with pytest.raises(ContractError):
            cli.verify_development_report_file(REPORT)


def test_tampered_report_rejected(isolated_artifacts):
    cli.generate_development_report(REPORT)
    target = report_directory(isolated_artifacts) / "controls-001.json"
    original = target.read_bytes()
    tampered = original.replace(b"synthetic_development", b"synthetic_developmenX", 1)
    assert tampered != original
    target.write_bytes(tampered)
    with pytest.raises(ContractError):
        cli.verify_development_report_file(REPORT)
    with pytest.raises(ContractError):
        cli.inspect_development_report_file(REPORT)


def test_verify_and_inspect_do_not_run_offline_suite(isolated_artifacts, monkeypatch):
    cli.generate_development_report(REPORT)
    def forbidden():
        raise AssertionError("verify/inspect must not rerun the agent")
    monkeypatch.setattr(cli, "run_synthetic_control_suite", forbidden)
    assert cli.verify_development_report_file(REPORT).correct_count == 2
    assert len(cli.inspect_development_report_file(REPORT)["cases"]) == 8


def test_failed_serialization_never_creates_export(isolated_artifacts, monkeypatch):
    monkeypatch.setattr(cli, "serialize_portable_development_report", lambda _: b"{}")
    with pytest.raises(ContractError):
        cli.generate_development_report(REPORT)
    assert not report_directory(isolated_artifacts).exists()


def test_cli_main_generate_verify_inspect(isolated_artifacts, capsys):
    assert cli.main(["generate", "--output", REPORT]) == 0
    exported = capsys.readouterr()
    assert "EXPORTED: synthetic development report" in exported.out
    assert "Document SHA256:" in exported.out
    assert not exported.err
    assert cli.main(["verify", "--input", REPORT]) == 0
    checked = capsys.readouterr()
    assert "INTEGRITY PASS:" in checked.out
    assert "Externally anchored: False" in checked.out
    assert not checked.err
    assert cli.main(["inspect", "--input", REPORT]) == 0
    inspected = capsys.readouterr()
    document = json.loads(inspected.out)
    assert len(document["cases"]) == 8
    assert document["provider_authenticity_verified"] is False
    assert not inspected.err


def test_cli_main_trusted_anchor(isolated_artifacts, capsys):
    verified = cli.generate_development_report(REPORT)
    assert cli.main([
        "verify", "--input", REPORT,
        "--sha256", verified.document_sha256,
    ]) == 0
    assert "Externally anchored: True" in capsys.readouterr().out
    assert cli.main([
        "verify", "--input", REPORT,
        "--sha256", "0" * 64,
    ]) == 2
    assert "ERROR:" in capsys.readouterr().err


def test_cli_main_rejects_invalid_path_and_missing_file(isolated_artifacts, capsys):
    assert cli.main(["generate", "--output", "../bad.json"]) == 2
    assert "ERROR:" in capsys.readouterr().err
    assert cli.main(["verify", "--input", REPORT]) == 2
    assert "ERROR:" in capsys.readouterr().err
    assert not report_directory(isolated_artifacts).exists()


def test_cli_main_refuses_second_generation(isolated_artifacts, capsys):
    assert cli.main(["generate", "--output", REPORT]) == 0
    capsys.readouterr()
    assert cli.main(["generate", "--output", REPORT]) == 2
    assert "ERROR:" in capsys.readouterr().err
    assert sorted(path.name for path in report_directory(isolated_artifacts).iterdir()) == [
        "controls-001.json"
    ]


def test_cli_requires_explicit_command_and_required_flags(isolated_artifacts):
    for argv in ([], ["generate"], ["verify"], ["inspect"]):
        with pytest.raises(SystemExit) as exc:
            cli.main(argv)
        assert exc.value.code == 2
    assert not report_directory(isolated_artifacts).exists()
