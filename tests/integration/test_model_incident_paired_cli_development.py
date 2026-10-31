"""End-to-end CLI regressions for synthetic paired evidence.

Every generated document is confined to pytest-managed temporary directories.
No test writes to the repository's real evidence namespace.
"""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import hashlib
import json
import stat
from unittest.mock import patch

import pytest

from packages.engines.behavioral import (
    model_incident_report_cli_development as cli,
)

PREFIX = "artifacts/development_incident_reports/"
PAIR = PREFIX + "paired-cli-test-001.json"
LEGACY = PREFIX + "legacy-cli-test-001.json"

REPORT = "paired-cli-test-001.json"
SOURCE = "paired-cli-test-001.source.json"
MARKER = "paired-cli-test-001.pair.json"

NAMES = (REPORT, SOURCE, MARKER)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def invoke(args):
    output = StringIO()
    errors = StringIO()

    with redirect_stdout(output), redirect_stderr(errors):
        code = cli.main(args)

    return code, output.getvalue(), errors.getvalue()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    (tmp_path / "artifacts").mkdir(mode=0o700)
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    return tmp_path


def folder(root):
    return root / "artifacts" / "development_incident_reports"


@pytest.fixture
def published(isolated):
    code, output, errors = invoke(
        ["generate-pair", "--output", PAIR]
    )

    assert code == 0
    assert not errors
    assert "EXPORTED: replay-verifiable synthetic evidence pair" in output

    directory = folder(isolated)
    assert {p.name for p in directory.iterdir()} == set(NAMES)

    return directory


def test_cli_help_retains_old_and_new_commands(isolated):
    stdout = StringIO()

    with redirect_stdout(stdout):
        with pytest.raises(SystemExit) as exc:
            cli.main(["--help"])

    assert exc.value.code == 0

    help_text = stdout.getvalue()

    for command in (
        "generate",
        "verify",
        "inspect",
        "generate-pair",
        "verify-pair",
    ):
        assert command in help_text

    assert not folder(isolated).exists()


@pytest.mark.parametrize("args", [
    [],
    ["generate"],
    ["verify"],
    ["inspect"],
    ["generate-pair"],
    ["verify-pair"],
    ["generate-pair", "--input", PAIR],
    ["verify-pair", "--output", PAIR],
])
def test_required_arguments_are_enforced(isolated, args):
    with redirect_stderr(StringIO()):
        with pytest.raises(SystemExit) as exc:
            cli.main(args)

    assert exc.value.code == 2
    assert not folder(isolated).exists()


@pytest.mark.parametrize("bad_path", [
    "/tmp/untrusted.json",
    "../untrusted.json",
    PREFIX + "../untrusted.json",
    PREFIX + "wrong.source.json",
    PREFIX + "wrong.pair.json",
    PREFIX + "wrong.txt",
])
def test_generate_pair_rejects_invalid_destinations_before_execution(
    isolated, bad_path
):
    with patch.object(
        cli,
        "run_synthetic_control_suite",
        side_effect=AssertionError(
            "Invalid destination triggered execution"
        ),
    ):
        code, output, errors = invoke([
            "generate-pair",
            "--output",
            bad_path,
        ])

    assert code == 2
    assert not output
    assert "ERROR:" in errors
    assert not folder(isolated).exists()


@pytest.mark.parametrize("bad_path", [
    "/tmp/untrusted.json",
    "../untrusted.json",
    PREFIX + "../untrusted.json",
    PREFIX + "wrong.source.json",
    PREFIX + "wrong.pair.json",
    PREFIX + "wrong.txt",
])
def test_verify_pair_rejects_invalid_paths_without_execution(
    isolated, bad_path
):
    with patch.object(
        cli,
        "run_synthetic_control_suite",
        side_effect=AssertionError(
            "Invalid verification triggered execution"
        ),
    ):
        code, output, errors = invoke([
            "verify-pair",
            "--input",
            bad_path,
        ])

    assert code == 2
    assert not output
    assert "ERROR:" in errors
    assert not folder(isolated).exists()


def test_pair_generation_executes_once_and_publishes_private_files(
    isolated
):
    actual_run = cli.run_synthetic_control_suite

    with patch.object(
        cli,
        "run_synthetic_control_suite",
        wraps=actual_run,
    ) as captured:
        code, output, errors = invoke([
            "generate-pair",
            "--output",
            PAIR,
        ])

    assert code == 0
    assert not errors
    assert captured.call_count == 1

    directory = folder(isolated)

    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert {p.name for p in directory.iterdir()} == set(NAMES)

    for name in NAMES:
        path = directory / name

        assert path.is_file()
        assert not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    assert "Report SHA256:" in output
    assert "Source SHA256:" in output
    assert "Completion marker SHA256:" in output
    assert "Provider authenticated: False" in output
    assert "Provider authenticated: True" not in output

    assert sha((directory / REPORT).read_bytes()) in output
    assert sha((directory / SOURCE).read_bytes()) in output
    assert sha((directory / MARKER).read_bytes()) in output


def test_verify_pair_recomputes_source_evidence(published):
    code, output, errors = invoke([
        "verify-pair",
        "--input",
        PAIR,
    ])

    assert code == 0
    assert not errors
    assert "SOURCE REPLAY PASS:" in output
    assert "Cases: 8" in output
    assert "Correct cases: 2" in output
    assert "Provider authenticated: False" in output
    assert "Externally anchored: False" in output


def test_pair_verification_does_not_rerun_controls(published):
    with patch.object(
        cli,
        "run_synthetic_control_suite",
        side_effect=AssertionError(
            "Evidence verification reran offline execution"
        ),
    ):
        code, output, errors = invoke([
            "verify-pair",
            "--input",
            PAIR,
        ])

    assert code == 0
    assert not errors
    assert "SOURCE REPLAY PASS:" in output


def test_all_three_trusted_sha256_anchors_are_accepted(published):
    code, output, errors = invoke([
        "verify-pair",
        "--input",
        PAIR,
        "--marker-sha256", sha((published / MARKER).read_bytes()),
        "--report-sha256", sha((published / REPORT).read_bytes()),
        "--source-sha256", sha((published / SOURCE).read_bytes()),
    ])

    assert code == 0
    assert not errors
    assert "SOURCE REPLAY PASS:" in output
    assert "Externally anchored: True" in output


@pytest.mark.parametrize(("argument", "filename"), [
    ("--marker-sha256", MARKER),
    ("--report-sha256", REPORT),
    ("--source-sha256", SOURCE),
])
def test_each_correct_external_anchor_is_accepted(
    published, argument, filename
):
    code, output, errors = invoke([
        "verify-pair",
        "--input",
        PAIR,
        argument,
        sha((published / filename).read_bytes()),
    ])

    assert code == 0
    assert not errors
    assert "Externally anchored: True" in output


@pytest.mark.parametrize("argument", [
    "--marker-sha256",
    "--report-sha256",
    "--source-sha256",
])
@pytest.mark.parametrize("wrong", [
    "0" * 64,
    "invalid",
    "A" * 64,
    "",
])
def test_wrong_or_malformed_external_anchor_rejected(
    published, argument, wrong
):
    code, output, errors = invoke([
        "verify-pair",
        "--input",
        PAIR,
        argument,
        wrong,
    ])

    assert code == 2
    assert not output
    assert "ERROR:" in errors


@pytest.mark.parametrize("filename", NAMES)
def test_missing_pair_member_rejected(published, filename):
    (published / filename).unlink()

    code, output, errors = invoke([
        "verify-pair",
        "--input",
        PAIR,
    ])

    assert code == 2
    assert not output
    assert "ERROR:" in errors


@pytest.mark.parametrize("filename", NAMES)
def test_tampered_pair_member_rejected(published, filename):
    path = published / filename
    path.write_bytes(path.read_bytes() + b"\n")

    code, output, errors = invoke([
        "verify-pair",
        "--input",
        PAIR,
    ])

    assert code == 2
    assert not output
    assert "ERROR:" in errors


def test_second_generation_preserves_original_artifacts(published):
    original = {
        name: (
            (published / name).read_bytes(),
            (published / name).stat().st_ino,
            (published / name).stat().st_mtime_ns,
        )
        for name in NAMES
    }

    code, output, errors = invoke([
        "generate-pair",
        "--output",
        PAIR,
    ])

    assert code == 2
    assert not output
    assert "ERROR:" in errors

    after = {
        name: (
            (published / name).read_bytes(),
            (published / name).stat().st_ino,
            (published / name).stat().st_mtime_ns,
        )
        for name in NAMES
    }

    assert after == original


@pytest.mark.parametrize("filename", NAMES)
def test_existing_pair_member_blocks_cli_publication(
    isolated, filename
):
    directory = folder(isolated)
    directory.mkdir(mode=0o700)

    target = directory / filename
    target.write_bytes(b"existing-protected-record")
    target.chmod(0o600)

    code, output, errors = invoke([
        "generate-pair",
        "--output",
        PAIR,
    ])

    assert code == 2
    assert not output
    assert "ERROR:" in errors
    assert {p.name for p in directory.iterdir()} == {filename}
    assert target.read_bytes() == b"existing-protected-record"


def test_verify_missing_pair_does_not_create_directory(isolated):
    code, output, errors = invoke([
        "verify-pair",
        "--input",
        PAIR,
    ])

    assert code == 2
    assert not output
    assert "ERROR:" in errors
    assert not folder(isolated).exists()


def test_pair_verification_is_read_only(published):
    before = {
        path.name: (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in published.iterdir()
    }

    code, output, errors = invoke([
        "verify-pair",
        "--input",
        PAIR,
    ])

    assert code == 0
    assert not errors
    assert "SOURCE REPLAY PASS:" in output

    after = {
        path.name: (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in published.iterdir()
    }

    assert after == before


def test_legacy_commands_still_work(isolated):
    code, output, errors = invoke([
        "generate",
        "--output",
        LEGACY,
    ])

    assert code == 0
    assert not errors
    assert "EXPORTED: synthetic development report" in output

    code, output, errors = invoke([
        "verify",
        "--input",
        LEGACY,
    ])

    assert code == 0
    assert not errors
    assert "INTEGRITY PASS:" in output

    code, output, errors = invoke([
        "inspect",
        "--input",
        LEGACY,
    ])

    assert code == 0
    assert not errors

    inspection = json.loads(output)

    assert len(inspection["cases"]) == 8
    assert inspection["provider_authenticity_verified"] is False
    assert inspection["source_execution_replayed"] is False

    assert {
        path.name for path in folder(isolated).iterdir()
    } == {"legacy-cli-test-001.json"}


def test_legacy_inspection_does_not_claim_source_replay(published):
    code, output, errors = invoke([
        "inspect",
        "--input",
        PAIR,
    ])

    assert code == 0
    assert not errors

    inspection = json.loads(output)

    assert inspection["integrity_checked"] is True
    assert inspection["source_execution_replayed"] is False
    assert inspection["provider_authenticity_verified"] is False


def test_legacy_verify_remains_document_only(published):
    code, output, errors = invoke([
        "verify",
        "--input",
        PAIR,
    ])

    assert code == 0
    assert not errors
    assert "INTEGRITY PASS:" in output
    assert "SOURCE REPLAY PASS:" not in output


def test_pair_verification_does_not_claim_provider_authentication(
    published
):
    code, output, errors = invoke([
        "verify-pair",
        "--input",
        PAIR,
    ])

    assert code == 0
    assert not errors
    assert "not provider authentication" in output
    assert "Provider authenticated: False" in output
    assert "Provider authenticated: True" not in output
