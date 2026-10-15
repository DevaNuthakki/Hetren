"""Reviewer integration tests; all generated pairs use temporary paths.

The persisted repository evidence files are never used as test fixtures.
"""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
import hashlib
import json
import os
import stat
from unittest.mock import patch

import pytest

from packages import portfolio_demo
from packages import portfolio_review as review
from packages.engines.behavioral import (
    model_incident_paired_export_development as paired,
)
from packages.engines.behavioral import (
    model_incident_report_cli_development as report_cli,
)


PREFIX = "artifacts/development_incident_reports/"
PAIR = PREFIX + "review-integration-001.json"

REPORT = "review-integration-001.json"
SOURCE = "review-integration-001.source.json"
MARKER = "review-integration-001.pair.json"

NAMES = (REPORT, SOURCE, MARKER)

ANCHOR_FLAGS = (
    "--marker-sha256",
    "--report-sha256",
    "--source-sha256",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def invoke(arguments):
    output = StringIO()
    errors = StringIO()

    with redirect_stdout(output), redirect_stderr(errors):
        code = review.main(arguments)

    return code, output.getvalue(), errors.getvalue()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    (tmp_path / "artifacts").mkdir(mode=0o700)
    monkeypatch.setattr(report_cli, "PROJECT_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def published(isolated):
    verified = paired.export_paired_development_evidence(PAIR)

    folder = (
        isolated / "artifacts"
        / "development_incident_reports"
    )

    assert {p.name for p in folder.iterdir()} == set(NAMES)

    anchors = {
        "--marker-sha256": sha((folder / MARKER).read_bytes()),
        "--report-sha256": sha((folder / REPORT).read_bytes()),
        "--source-sha256": sha((folder / SOURCE).read_bytes()),
    }

    assert verified.case_count == 8
    assert verified.correct_count == 2
    assert verified.provider_authenticated is False

    return folder, anchors, verified


def arguments(anchors, *, format="json"):
    return [
        "--format", format,
        "--pair-input", PAIR,
        "--marker-sha256", anchors["--marker-sha256"],
        "--report-sha256", anchors["--report-sha256"],
        "--source-sha256", anchors["--source-sha256"],
    ]


def unchanged(folder):
    return {
        name: (
            (folder / name).read_bytes(),
            (folder / name).stat().st_dev,
            (folder / name).stat().st_ino,
            (folder / name).stat().st_mtime_ns,
        )
        for name in NAMES
    }


def test_default_json_is_reproducible(isolated):
    first = invoke(["--format", "json"])
    second = invoke(["--format", "json"])

    assert first[0] == second[0] == 0
    assert first[1] == second[1]
    assert first[2] == second[2] == ""

    data = json.loads(first[1])

    assert data["report_type"] == "hetren_portfolio_review"
    assert data["schema_version"] == 1
    assert data["paired_synthetic_evidence"] is None
    assert data["execution_lineages_are_distinct"] is True
    assert len(data["deterministic_demo"]["scenarios"]) == 2
    assert not (
        isolated / "artifacts"
        / "development_incident_reports"
    ).exists()


def test_default_does_not_access_optional_evidence(isolated):
    with patch.object(
        paired,
        "verify_paired_development_evidence",
        side_effect=AssertionError(
            "Default review accessed paired evidence"
        ),
    ):
        code, output, errors = invoke(["--format", "json"])

    assert code == 0
    assert not errors
    assert json.loads(output)["paired_synthetic_evidence"] is None


def test_existing_deterministic_report_preserved(isolated):
    report = review.build_review_report()

    assert report["deterministic_demo"] == (
        portfolio_demo.build_demo_report()
    )

    assert report["paired_synthetic_evidence"] is None


def test_default_text_is_reviewer_facing(isolated):
    code, output, errors = invoke([])

    assert code == 0
    assert not errors
    assert "Hetren evidence-backed portfolio review" in output
    assert "Diagnosis:" in output
    assert "Repair:" in output
    assert "Verification: VERIFIED" in output
    assert "Eligibility: ELIGIBLE" in output
    assert "clean-checkout demonstration mode" in output
    assert "separate execution lineages" in output


def test_default_review_does_not_generate_evidence(isolated):
    with patch.object(
        paired,
        "export_paired_development_evidence",
        side_effect=AssertionError("Unexpected publication"),
    ):
        code, output, errors = invoke([])

    assert code == 0
    assert output
    assert not errors


@pytest.mark.parametrize("mask", range(1, 8))
def test_external_anchors_without_pair_path_rejected(
    isolated, mask
):
    args = []

    for index, flag in enumerate(ANCHOR_FLAGS):
        if mask & (1 << index):
            args.extend((flag, "a" * 64))

    with patch.object(
        portfolio_demo,
        "build_demo_report",
        side_effect=AssertionError(
            "Invalid arguments triggered demo execution"
        ),
    ):
        code, output, errors = invoke(args)

    assert code == 2
    assert not output
    assert "ERROR:" in errors


@pytest.mark.parametrize("mask", range(7))
def test_missing_pair_anchors_rejected_before_execution(
    isolated, mask
):
    args = ["--pair-input", PAIR]

    for index, flag in enumerate(ANCHOR_FLAGS):
        if mask & (1 << index):
            args.extend((flag, "a" * 64))

    with patch.object(
        portfolio_demo,
        "build_demo_report",
        side_effect=AssertionError(
            "Incomplete anchors triggered demo execution"
        ),
    ):
        code, output, errors = invoke(args)

    assert code == 2
    assert not output
    assert "ERROR:" in errors
    assert not (
        isolated / "artifacts"
        / "development_incident_reports"
    ).exists()


@pytest.mark.parametrize("path", [
    "/tmp/untrusted.json",
    "../untrusted.json",
    PREFIX + "../untrusted.json",
    PREFIX + "wrong.source.json",
    PREFIX + "wrong.pair.json",
    PREFIX + "wrong.txt",
    "",
])
def test_noncanonical_pair_path_rejected(
    isolated, path
):
    args = [
        "--pair-input", path,
        "--marker-sha256", "a" * 64,
        "--report-sha256", "b" * 64,
        "--source-sha256", "c" * 64,
    ]

    with patch.object(
        portfolio_demo,
        "build_demo_report",
        side_effect=AssertionError(
            "Invalid path triggered deterministic execution"
        ),
    ):
        code, output, errors = invoke(args)

    assert code == 2
    assert not output
    assert "ERROR:" in errors


def test_successful_anchored_pair_review(published):
    folder, anchors, _ = published

    code, output, errors = invoke(arguments(anchors))

    assert code == 0
    assert not errors

    document = json.loads(output)
    pair = document["paired_synthetic_evidence"]

    assert pair["record_type"] == "synthetic_development_evidence_pair"
    assert pair["source_replayed"] is True
    assert pair["externally_anchored"] is True
    assert pair["provider_authenticated"] is False
    assert pair["development_only"] is True
    assert pair["same_execution_as_deterministic_demo"] is False

    assert pair["case_count"] == 8
    assert pair["correct_count"] == 2

    assert pair["report_sha256"] == anchors["--report-sha256"]
    assert pair["source_sha256"] == anchors["--source-sha256"]
    assert pair["marker_sha256"] == anchors["--marker-sha256"]

    assert document["execution_lineages_are_distinct"] is True
    assert len(document["deterministic_demo"]["scenarios"]) == 2
    assert {p.name for p in folder.iterdir()} == set(NAMES)


def test_verified_pair_review_is_read_only(published):
    folder, anchors, _ = published

    before = unchanged(folder)

    code, output, errors = invoke(arguments(anchors))

    assert code == 0
    assert not errors
    assert json.loads(output)["paired_synthetic_evidence"]["source_replayed"]

    assert unchanged(folder) == before


def test_verified_pair_does_not_rerun_synthetic_controls(published):
    _, anchors, _ = published

    with patch.object(
        report_cli,
        "run_synthetic_control_suite",
        side_effect=AssertionError(
            "Reviewer reran synthetic control suite"
        ),
    ):
        code, output, errors = invoke(arguments(anchors))

    assert code == 0
    assert not errors
    assert json.loads(output)["paired_synthetic_evidence"]["source_replayed"]


def test_verified_pair_does_not_publish_again(published):
    _, anchors, _ = published

    with patch.object(
        paired,
        "export_paired_development_evidence",
        side_effect=AssertionError(
            "Reviewer attempted to publish evidence"
        ),
    ):
        code, output, errors = invoke(arguments(anchors))

    assert code == 0
    assert not errors
    assert json.loads(output)["paired_synthetic_evidence"]["source_replayed"]


def test_successful_pair_text_format(published):
    _, anchors, _ = published

    code, output, errors = invoke(
        arguments(anchors, format="text")
    )

    assert code == 0
    assert not errors
    assert "SOURCE REPLAY PASS:" in output
    assert "Cases: 8" in output
    assert "Correct cases: 2" in output
    assert "Externally anchored: True" in output
    assert "Provider authenticated: False" in output
    assert "separate execution lineages" in output


@pytest.mark.parametrize("flag", ANCHOR_FLAGS)
@pytest.mark.parametrize("wrong", [
    "0" * 64,
    "invalid",
    "A" * 64,
    "",
])
def test_incorrect_or_invalid_anchor_rejected(
    published, flag, wrong
):
    _, anchors, _ = published
    args = arguments(anchors)

    index = args.index(flag)
    args[index + 1] = wrong

    code, output, errors = invoke(args)

    assert code == 2
    assert not output
    assert "ERROR:" in errors


@pytest.mark.parametrize("filename", NAMES)
def test_missing_evidence_member_rejected(
    published, filename
):
    folder, anchors, _ = published
    (folder / filename).unlink()

    code, output, errors = invoke(arguments(anchors))

    assert code == 2
    assert not output
    assert "ERROR:" in errors


@pytest.mark.parametrize("filename", NAMES)
def test_tampered_evidence_member_rejected(
    published, filename
):
    folder, anchors, _ = published

    path = folder / filename
    path.write_bytes(path.read_bytes() + b"\n")

    code, output, errors = invoke(arguments(anchors))

    assert code == 2
    assert not output
    assert "ERROR:" in errors


@pytest.mark.parametrize("filename", NAMES)
def test_symlink_evidence_member_rejected(
    published, filename
):
    folder, anchors, _ = published

    target = folder / filename
    target.unlink()
    target.symlink_to(folder / REPORT)

    code, output, errors = invoke(arguments(anchors))

    assert code == 2
    assert not output
    assert "ERROR:" in errors


@pytest.mark.parametrize("filename", NAMES)
def test_insecure_file_permissions_rejected(
    published, filename
):
    folder, anchors, _ = published
    (folder / filename).chmod(0o644)

    code, output, errors = invoke(arguments(anchors))

    assert code == 2
    assert not output
    assert "ERROR:" in errors


def test_absent_evidence_directory_rejected(isolated):
    anchors = {
        "--marker-sha256": "a" * 64,
        "--report-sha256": "b" * 64,
        "--source-sha256": "c" * 64,
    }

    code, output, errors = invoke(arguments(anchors))

    assert code == 2
    assert not output
    assert "ERROR:" in errors

    assert not (
        isolated / "artifacts"
        / "development_incident_reports"
    ).exists()


def test_pair_verification_failure_precedes_demo_execution(
    published
):
    _, anchors, _ = published

    args = arguments(anchors)
    index = args.index("--marker-sha256")
    args[index + 1] = "0" * 64

    with patch.object(
        portfolio_demo,
        "build_demo_report",
        side_effect=AssertionError(
            "Failed pair triggered demo execution"
        ),
    ):
        code, output, errors = invoke(args)

    assert code == 2
    assert not output
    assert "ERROR:" in errors


def test_provider_authenticity_misclaim_rejected(published):
    _, anchors, verified = published

    forged = replace(
        verified,
        provider_authenticated=True,
    )

    with patch.object(
        paired,
        "verify_paired_development_evidence",
        return_value=forged,
    ):
        code, output, errors = invoke(arguments(anchors))

    assert code == 2
    assert not output
    assert "ERROR:" in errors


def test_review_preserves_scientific_claim_limits(published):
    _, anchors, _ = published

    code, output, errors = invoke(arguments(anchors))

    assert code == 0
    assert not errors

    document = json.loads(output)
    limits = document["claim_limits"]

    assert any("separate executions" in value for value in limits)
    assert any("not a live model" in value for value in limits)
    assert any("do not authenticate a provider" in value for value in limits)
    assert any("production safety" in value for value in limits)

    assert document["paired_synthetic_evidence"]["provider_authenticated"] is False
    assert document["paired_synthetic_evidence"]["same_execution_as_deterministic_demo"] is False


@pytest.mark.parametrize("args", [
    ["--format", "xml"],
    ["--pair-input"],
    ["--marker-sha256"],
    ["--report-sha256"],
    ["--source-sha256"],
    ["--unknown-option"],
])
def test_cli_parser_rejects_invalid_arguments(
    isolated, args
):
    with redirect_stderr(StringIO()):
        with pytest.raises(SystemExit) as exc:
            review.main(args)

    assert exc.value.code == 2


def test_cli_help_documents_optional_evidence(isolated):
    output = StringIO()

    with redirect_stdout(output):
        with pytest.raises(SystemExit) as exc:
            review.main(["--help"])

    assert exc.value.code == 0

    help_text = output.getvalue()

    assert "--pair-input" in help_text
    assert "--marker-sha256" in help_text
    assert "--report-sha256" in help_text
    assert "--source-sha256" in help_text
    assert "--format" in help_text


def test_original_portfolio_demo_remains_operational(isolated):
    old_report = portfolio_demo.build_demo_report()

    new_report = review.build_review_report()

    assert new_report["deterministic_demo"] == old_report
    assert portfolio_demo.render_json(old_report) == (
        portfolio_demo.render_json(
            new_report["deterministic_demo"]
        )
    )


def test_no_claim_of_live_execution_in_default_mode(isolated):
    code, output, errors = invoke(["--format", "json"])

    assert code == 0
    assert not errors

    document = json.loads(output)

    assert document["paired_synthetic_evidence"] is None
    assert document["execution_lineages_are_distinct"] is True
    assert "provider_authenticated" not in document
