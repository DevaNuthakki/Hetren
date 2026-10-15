"""Filesystem and integrity regressions for synthetic paired exports.

All publication tests operate under pytest temporary directories.
No test publishes evidence into the real repository artifacts directory.
"""
import hashlib
import json
import os
import stat
from unittest.mock import patch

import pytest

from packages.contracts import ContractError
from packages.engines.behavioral import (
    model_incident_control_suite_development as controls,
)
from packages.engines.behavioral import (
    model_incident_paired_export_development as paired,
)
from packages.engines.behavioral import (
    model_incident_report_cli_development as report_cli,
)
from packages.engines.behavioral import (
    model_incident_source_bundle_development as source_bundle,
)

DEST = "artifacts/development_incident_reports/controls-002.json"
REPORT = "controls-002.json"
SOURCE = "controls-002.source.json"
MARKER = "controls-002.pair.json"

NAMES = (REPORT, SOURCE, MARKER)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(data):
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def private_file(path, content):
    path.write_bytes(content)
    path.chmod(0o600)


@pytest.fixture(scope="module")
def materials():
    suite = controls.run_synthetic_control_suite()
    report = report_cli.serialize_portable_development_report(suite)
    source = source_bundle.serialize_synthetic_source_bundle(
        suite, report
    )
    verified = source_bundle.verify_synthetic_source_bundle(
        source, report
    )
    marker = paired._make_marker(
        REPORT, SOURCE, report, source, verified
    )

    assert verified.case_count == 8
    assert verified.correct_count == 2

    return {
        REPORT: report,
        SOURCE: source,
        MARKER: marker,
    }


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    (tmp_path / "artifacts").mkdir(mode=0o700)
    monkeypatch.setattr(report_cli, "PROJECT_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def published(isolated, materials):
    folder = (
        isolated / "artifacts" / "development_incident_reports"
    )
    folder.mkdir(mode=0o700)

    for name, raw in materials.items():
        private_file(folder / name, raw)

    return folder


def check_rejected():
    with pytest.raises((ContractError, OSError)):
        paired.verify_paired_development_evidence(DEST)


def update_marker(folder, modify):
    marker = json.loads((folder / MARKER).read_bytes())
    modify(marker)
    private_file(folder / MARKER, canonical(marker))


def test_independent_verification_with_all_trusted_anchors(
    published, materials
):
    result = paired.verify_paired_development_evidence(
        DEST,
        expected_marker_sha256=digest(materials[MARKER]),
        expected_report_sha256=digest(materials[REPORT]),
        expected_source_sha256=digest(materials[SOURCE]),
    )

    assert result.report_filename == REPORT
    assert result.source_filename == SOURCE
    assert result.marker_filename == MARKER
    assert result.case_count == 8
    assert result.correct_count == 2
    assert result.provider_authenticated is False


def test_verification_never_reruns_synthetic_controls(published):
    with patch.object(
        report_cli,
        "run_synthetic_control_suite",
        side_effect=AssertionError("Unexpected execution"),
    ):
        assert paired.verify_paired_development_evidence(
            DEST
        ).case_count == 8


def test_verification_does_not_modify_published_files(published):
    before = {
        p.name: (
            p.read_bytes(),
            p.stat().st_ino,
            p.stat().st_mtime_ns,
        )
        for p in published.iterdir()
    }

    paired.verify_paired_development_evidence(DEST)

    after = {
        p.name: (
            p.read_bytes(),
            p.stat().st_ino,
            p.stat().st_mtime_ns,
        )
        for p in published.iterdir()
    }

    assert after == before


@pytest.mark.parametrize("argument", [
    "expected_marker_sha256",
    "expected_report_sha256",
    "expected_source_sha256",
])
@pytest.mark.parametrize("value", [
    "0" * 64,
    "invalid",
    "A" * 64,
    "",
])
def test_invalid_external_integrity_anchor_rejected(
    published, argument, value
):
    with pytest.raises(ContractError):
        paired.verify_paired_development_evidence(
            DEST, **{argument: value}
        )


@pytest.mark.parametrize("filename", NAMES)
def test_missing_member_rejected(published, filename):
    (published / filename).unlink()
    check_rejected()


@pytest.mark.parametrize("filename", NAMES)
def test_modified_member_rejected(published, filename):
    path = published / filename
    private_file(path, path.read_bytes() + b"\n")
    check_rejected()


@pytest.mark.parametrize("filename", NAMES)
def test_insecure_file_permissions_rejected(published, filename):
    (published / filename).chmod(0o644)
    check_rejected()


@pytest.mark.parametrize("filename", NAMES)
def test_symbolic_link_rejected(published, filename, isolated):
    path = published / filename
    content = path.read_bytes()

    target = isolated / (filename + ".target")
    private_file(target, content)

    path.unlink()
    path.symlink_to(target)

    check_rejected()


@pytest.mark.parametrize("filename", NAMES)
def test_hard_linked_member_rejected(published, filename, isolated):
    path = published / filename
    content = path.read_bytes()

    other = isolated / (filename + ".original")
    private_file(other, content)

    path.unlink()
    os.link(other, path)

    assert path.stat().st_nlink == 2
    check_rejected()


@pytest.mark.parametrize("filename", NAMES)
def test_fifo_is_not_accepted_as_regular_evidence(
    published, filename
):
    path = published / filename
    path.unlink()
    os.mkfifo(path, 0o600)

    check_rejected()


@pytest.mark.parametrize("raw", [
    b"",
    b"null",
    b"[]",
    b"42",
    b"{invalid",
    b'{"x":NaN}',
    b'{"x":Infinity}',
    b"\xff\xfe",
])
def test_invalid_completion_manifest_rejected(published, raw):
    private_file(published / MARKER, raw)
    check_rejected()


def test_duplicate_completion_manifest_key_rejected(published):
    raw = (published / MARKER).read_bytes()
    changed = raw.replace(
        b'"publication_state":',
        b'"publication_state":"forged","publication_state":',
        1,
    )
    assert changed != raw

    private_file(published / MARKER, changed)
    check_rejected()


@pytest.mark.parametrize(("field", "value"), [
    ("record_type", "ForgedEvidencePair"),
    ("schema_version", 2),
    ("schema_version", True),
    ("development_only", False),
    ("development_only", 1),
    ("publication_state", "pending"),
    ("publication_state", "aborted"),
    ("report_filename", "unrelated.json"),
    ("source_filename", "unrelated.source.json"),
    ("report_sha256", "0" * 64),
    ("source_sha256", "0" * 64),
    ("manifest_sha256", "0" * 64),
    ("evaluation_sha256", "0" * 64),
    ("suite_evidence_sha256", "0" * 64),
    ("report_sha256", "invalid"),
    ("source_sha256", True),
])
def test_forged_completion_manifest_fields_rejected(
    published, field, value
):
    update_marker(
        published,
        lambda document: document.__setitem__(field, value),
    )
    check_rejected()


@pytest.mark.parametrize("field", [
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
])
def test_missing_completion_manifest_field_rejected(
    published, field
):
    update_marker(
        published,
        lambda document: document.pop(field),
    )
    check_rejected()


def test_extra_completion_manifest_field_rejected(published):
    update_marker(
        published,
        lambda document: document.__setitem__(
            "provider_authenticated", True
        ),
    )
    check_rejected()


def test_oversized_completion_manifest_rejected(published):
    private_file(
        published / MARKER,
        b"X" * (paired.MAX_MARKER_BYTES + 1),
    )
    check_rejected()


def test_noncanonical_manifest_rejected(published):
    path = published / MARKER
    private_file(path, b" " + path.read_bytes())
    check_rejected()


@pytest.mark.parametrize("destination", [
    "/tmp/controls-002.json",
    "../controls-002.json",
    "artifacts/development_incident_reports/../controls-002.json",
    "artifacts/development_incident_reports/controls-002.source.json",
    "artifacts/development_incident_reports/controls-002.pair.json",
])
def test_invalid_publication_destinations_rejected(destination):
    with pytest.raises(ContractError):
        paired._names(destination)


def test_one_offline_execution_publishes_three_private_files(
    isolated
):
    execute = report_cli.run_synthetic_control_suite

    with patch.object(
        report_cli,
        "run_synthetic_control_suite",
        wraps=execute,
    ) as captured:
        result = paired.export_paired_development_evidence(DEST)

    assert captured.call_count == 1

    folder = (
        isolated / "artifacts" / "development_incident_reports"
    )

    assert {p.name for p in folder.iterdir()} == set(NAMES)
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700

    for name in NAMES:
        path = folder / name
        assert path.is_file()
        assert not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    assert result.case_count == 8
    assert result.correct_count == 2
    assert result.provider_authenticated is False

    with patch.object(
        report_cli,
        "run_synthetic_control_suite",
        side_effect=AssertionError("Verification reran controls"),
    ):
        second = paired.verify_paired_development_evidence(DEST)

    assert second == result


def test_publication_order_has_completion_marker_last(isolated):
    original = report_cli._publish_new
    seen = []

    def record(directory_fd, filename, raw):
        seen.append(filename)
        return original(directory_fd, filename, raw)

    with patch.object(
        report_cli, "_publish_new", side_effect=record
    ):
        paired.export_paired_development_evidence(DEST)

    assert seen == [REPORT, SOURCE, MARKER]


def test_second_publication_never_overwrites_complete_pair(isolated):
    first = paired.export_paired_development_evidence(DEST)

    folder = (
        isolated / "artifacts" / "development_incident_reports"
    )

    before = {
        name: (folder / name).read_bytes()
        for name in NAMES
    }

    with pytest.raises((ContractError, FileExistsError)):
        paired.export_paired_development_evidence(DEST)

    after = {
        name: (folder / name).read_bytes()
        for name in NAMES
    }

    assert after == before
    assert paired.verify_paired_development_evidence(DEST) == first


@pytest.mark.parametrize("blocked", NAMES)
def test_preexisting_member_blocks_publication_without_overwrite(
    isolated, blocked
):
    folder = (
        isolated / "artifacts" / "development_incident_reports"
    )
    folder.mkdir(mode=0o700)

    private_file(folder / blocked, b"existing-and-protected")

    with pytest.raises((ContractError, FileExistsError)):
        paired.export_paired_development_evidence(DEST)

    assert sorted(p.name for p in folder.iterdir()) == [blocked]
    assert (folder / blocked).read_bytes() == b"existing-and-protected"


@pytest.mark.parametrize("failure_at", [1, 2, 3])
def test_interrupted_publication_is_not_accepted(
    isolated, failure_at
):
    original = report_cli._publish_new
    count = 0

    def interrupted(directory_fd, filename, raw):
        nonlocal count
        count += 1

        if count == failure_at:
            raise OSError("Injected publication interruption")

        return original(directory_fd, filename, raw)

    with patch.object(
        report_cli,
        "_publish_new",
        side_effect=interrupted,
    ):
        with pytest.raises(OSError):
            paired.export_paired_development_evidence(DEST)

    folder = (
        isolated / "artifacts" / "development_incident_reports"
    )

    assert {p.name for p in folder.iterdir()} == set(
        NAMES[:failure_at - 1]
    )
    assert MARKER not in {p.name for p in folder.iterdir()}

    with pytest.raises((ContractError, OSError)):
        paired.verify_paired_development_evidence(DEST)


def test_competing_source_publication_cannot_be_overwritten(
    isolated
):
    original = report_cli._publish_new
    injected = False

    def collision(directory_fd, filename, raw):
        nonlocal injected

        if filename == SOURCE and not injected:
            injected = True

            fd = os.open(
                filename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=directory_fd,
            )

            with os.fdopen(fd, "wb") as stream:
                stream.write(b"competing-writer-evidence")

        return original(directory_fd, filename, raw)

    with patch.object(
        report_cli,
        "_publish_new",
        side_effect=collision,
    ):
        with pytest.raises(FileExistsError):
            paired.export_paired_development_evidence(DEST)

    folder = (
        isolated / "artifacts" / "development_incident_reports"
    )

    assert (folder / SOURCE).read_bytes() == b"competing-writer-evidence"
    assert not (folder / MARKER).exists()

    with pytest.raises((ContractError, OSError)):
        paired.verify_paired_development_evidence(DEST)


def test_no_provider_authentication_claim(published):
    outcome = paired.verify_paired_development_evidence(DEST)
    assert outcome.provider_authenticated is False
    assert outcome.case_count == 8
    assert outcome.correct_count == 2
