"""Adversarial regression tests for the optional offline reviewer mode.

All generated evidence is in-memory or under pytest-managed temporary paths.
The historical Hetren evidence directory must never be used by these tests.
"""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import socket

import pytest

from packages import portfolio_demo
from packages import portfolio_review as review
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


PREFIX = "artifacts/development_incident_reports/"
PAIR = PREFIX + "review-offline-test-001.json"
DEFAULT_SHA = (
    "dda7c69dc34b5ee614315dc339c2496905a90221c615907f052289adf87bc657"
)

EXPECTED_STATUSES = (
    "completed",
    "completed",
    "completed",
    "rejected",
    "recovery_exhausted",
    "budget_exhausted",
    "interrupted",
    "rejected",
)

EXPECTED_ATTEMPTS = (4, 4, 5, 4, 3, 2, 2, 3)
EXPECTED_CALLS = (4, 4, 5, 4, 3, 2, 3, 3)
EXPECTED_STEPS = (4, 4, 4, 2, 2, 2, 2, 2)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def invoke(args):
    stdout = StringIO()
    stderr = StringIO()

    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = review.main(args)

    return code, stdout.getvalue(), stderr.getvalue()


@pytest.fixture(autouse=True)
def forbid_network():
    attempted = []

    def reject(*args, **kwargs):
        attempted.append(True)
        raise AssertionError("Network forbidden in offline reviewer tests")

    with (
        patch.object(socket.socket, "connect", side_effect=reject),
        patch.object(socket.socket, "connect_ex", side_effect=reject),
        patch("socket.create_connection", side_effect=reject),
    ):
        yield

    assert attempted == []


@pytest.fixture
def private_root(tmp_path, monkeypatch):
    (tmp_path / "artifacts").mkdir(mode=0o700)
    monkeypatch.setattr(report_cli, "PROJECT_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def published_pair(private_root):
    verified = paired.export_paired_development_evidence(PAIR)

    folder = (
        private_root / "artifacts"
        / "development_incident_reports"
    )

    assert verified.case_count == 8
    assert verified.correct_count == 2
    assert verified.provider_authenticated is False

    report = folder / "review-offline-test-001.json"
    source = folder / "review-offline-test-001.source.json"
    marker = folder / "review-offline-test-001.pair.json"

    assert all(path.is_file() for path in (report, source, marker))

    args = [
        "--pair-input", PAIR,
        "--marker-sha256", sha(marker.read_bytes()),
        "--report-sha256", sha(report.read_bytes()),
        "--source-sha256", sha(source.read_bytes()),
    ]

    return folder, args


def test_original_default_json_remains_byte_identical(private_root):
    with patch.object(
        controls,
        "run_synthetic_control_suite",
        side_effect=AssertionError("Offline execution was not requested"),
    ):
        code, output, errors = invoke(["--format", "json"])

    assert code == 0
    assert errors == ""
    assert sha(output.encode("utf-8")) == DEFAULT_SHA

    document = json.loads(output)

    assert "offline_multistep_controls" not in document
    assert document["paired_synthetic_evidence"] is None


def test_default_text_does_not_execute_controls(private_root):
    with patch.object(
        controls,
        "run_synthetic_control_suite",
        side_effect=AssertionError("Unexpected offline execution"),
    ):
        code, output, errors = invoke([])

    assert code == 0
    assert errors == ""
    assert "Hetren evidence-backed portfolio review" in output
    assert "3. Fresh offline multi-step" not in output


def test_opt_in_json_preserves_original_demo(private_root):
    code, output, errors = invoke([
        "--format", "json", "--run-offline-controls",
    ])

    assert code == 0
    assert errors == ""

    document = json.loads(output)

    assert document["deterministic_demo"] == (
        portfolio_demo.build_demo_report()
    )
    assert len(document["deterministic_demo"]["scenarios"]) == 2
    assert document["execution_lineages_are_distinct"] is True
    assert document["paired_synthetic_evidence"] is None


def test_exact_offline_case_status_and_accounting(private_root):
    code, output, errors = invoke([
        "--format", "json", "--run-offline-controls",
    ])

    assert code == 0
    assert errors == ""

    offline = json.loads(output)["offline_multistep_controls"]
    cases = offline["cases"]

    assert offline["case_count"] == 8
    assert offline["correct_count"] == 2
    assert len(cases) == 8

    assert tuple(x["case_index"] for x in cases) == tuple(range(1, 9))
    assert tuple(x["status"] for x in cases) == EXPECTED_STATUSES
    assert tuple(x["attempts"] for x in cases) == EXPECTED_ATTEMPTS
    assert tuple(x["capture_calls"] for x in cases) == EXPECTED_CALLS
    assert tuple(x["executed_steps"] for x in cases) == EXPECTED_STEPS


def test_offline_provenance_limits_are_explicit(private_root):
    code, output, errors = invoke([
        "--format", "json", "--run-offline-controls",
    ])

    assert code == 0
    assert errors == ""

    offline = json.loads(output)["offline_multistep_controls"]

    assert offline["record_type"] == "synthetic_offline_multistep_controls"
    assert offline["development_only"] is True
    assert offline["execution_source"] == "fresh_offline_fixture_execution"
    assert offline["source_replayed"] is True
    assert offline["externally_anchored"] is False
    assert offline["provider_authenticated"] is False
    assert offline["artifact_persisted"] is False
    assert offline["fresh_evidence_byte_identity_claimed"] is False
    assert offline["same_execution_as_deterministic_demo"] is False


def test_opt_in_text_reports_all_cases(private_root):
    code, output, errors = invoke(["--run-offline-controls"])

    assert code == 0
    assert errors == ""
    assert "Fresh offline multi-step incident controls" in output
    assert "Cases: 8" in output
    assert "Correct cases: 2" in output
    assert "Source replay verified: True" in output
    assert "Provider authenticated: False" in output

    for number, status in enumerate(EXPECTED_STATUSES, 1):
        assert f"Case {number}: {status};" in output


def test_opt_in_does_not_create_evidence_directory(private_root):
    folder = (
        private_root / "artifacts"
        / "development_incident_reports"
    )

    assert not folder.exists()

    with patch.object(
        paired,
        "export_paired_development_evidence",
        side_effect=AssertionError("Publication forbidden"),
    ):
        code, output, errors = invoke([
            "--format", "json", "--run-offline-controls",
        ])

    assert code == 0
    assert errors == ""
    assert json.loads(output)["offline_multistep_controls"]["case_count"] == 8
    assert not folder.exists()


def test_source_reconstruction_is_actually_invoked(private_root):
    original = source_bundle.verify_synthetic_source_bundle

    with patch.object(
        source_bundle,
        "verify_synthetic_source_bundle",
        wraps=original,
    ) as verification:
        code, output, errors = invoke([
            "--format", "json", "--run-offline-controls",
        ])

    assert code == 0
    assert errors == ""
    assert verification.call_count == 1

    arguments = verification.call_args

    assert len(arguments.args) == 2
    assert (
        arguments.kwargs["expected_bundle_sha256"]
        == sha(arguments.args[0])
    )
    assert (
        arguments.kwargs["expected_report_sha256"]
        == sha(arguments.args[1])
    )

    assert json.loads(output)["offline_multistep_controls"]["source_replayed"]


def test_offline_verification_failure_prevents_demo(private_root):
    with (
        patch.object(
            source_bundle,
            "verify_synthetic_source_bundle",
            side_effect=ContractError("synthetic verification failed"),
        ),
        patch.object(
            portfolio_demo,
            "build_demo_report",
            side_effect=AssertionError("Must fail before demo"),
        ),
    ):
        code, output, errors = invoke([
            "--run-offline-controls",
        ])

    assert code == 2
    assert output == ""
    assert "ERROR:" in errors


@pytest.mark.parametrize("count,correct", [
    (7, 2),
    (9, 2),
    (8, 1),
    (8, 3),
])
def test_unexpected_control_summary_rejected(
    private_root, count, correct
):
    forged = SimpleNamespace(
        case_count=count,
        correct_count=correct,
    )

    with patch.object(
        source_bundle,
        "verify_synthetic_source_bundle",
        return_value=forged,
    ):
        code, output, errors = invoke([
            "--run-offline-controls",
        ])

    assert code == 2
    assert output == ""
    assert "ERROR:" in errors


def test_corrupted_portable_report_rejected(private_root):
    with patch.object(
        report_cli,
        "verify_portable_development_report",
        side_effect=ContractError("portable report invalid"),
    ):
        code, output, errors = invoke([
            "--run-offline-controls",
        ])

    assert code == 2
    assert output == ""
    assert "ERROR:" in errors


def test_corrupted_source_bundle_rejected(private_root):
    original = source_bundle.serialize_synthetic_source_bundle

    def corrupt(*args, **kwargs):
        return original(*args, **kwargs) + b"\n"

    with patch.object(
        source_bundle,
        "serialize_synthetic_source_bundle",
        side_effect=corrupt,
    ):
        code, output, errors = invoke([
            "--run-offline-controls",
        ])

    assert code == 2
    assert output == ""
    assert "ERROR:" in errors


def test_control_suite_failure_does_not_get_hidden(private_root):
    with (
        patch.object(
            controls,
            "run_synthetic_control_suite",
            side_effect=ContractError("synthetic control failure"),
        ),
        patch.object(
            portfolio_demo,
            "build_demo_report",
            side_effect=AssertionError("Unexpected fallback"),
        ),
    ):
        code, output, errors = invoke([
            "--run-offline-controls",
        ])

    assert code == 2
    assert output == ""
    assert "ERROR:" in errors


@pytest.mark.parametrize("value", [
    None,
    0,
    1,
    "true",
    [],
    {},
])
def test_programmatic_opt_in_requires_boolean(value):
    with pytest.raises(ValueError):
        review.build_review_report(
            run_offline_controls=value,
        )


def test_cli_help_documents_both_modes(private_root):
    output = StringIO()

    with redirect_stdout(output):
        with pytest.raises(SystemExit) as exc:
            review.main(["--help"])

    assert exc.value.code == 0
    assert "--run-offline-controls" in output.getvalue()
    assert "--pair-input" in output.getvalue()
    assert "--marker-sha256" in output.getvalue()
    assert "--report-sha256" in output.getvalue()
    assert "--source-sha256" in output.getvalue()


def test_pair_only_mode_unchanged(published_pair):
    _, pair_args = published_pair

    code, output, errors = invoke([
        "--format", "json", *pair_args,
    ])

    assert code == 0
    assert errors == ""

    document = json.loads(output)

    assert document["paired_synthetic_evidence"]["case_count"] == 8
    assert document["paired_synthetic_evidence"]["source_replayed"] is True
    assert "offline_multistep_controls" not in document


def test_pair_and_offline_modes_remain_separate(published_pair):
    _, pair_args = published_pair

    code, output, errors = invoke([
        "--format", "json",
        "--run-offline-controls",
        *pair_args,
    ])

    assert code == 0
    assert errors == ""

    document = json.loads(output)

    pair = document["paired_synthetic_evidence"]
    offline = document["offline_multistep_controls"]

    assert pair["externally_anchored"] is True
    assert offline["externally_anchored"] is False

    assert pair["source_replayed"] is True
    assert offline["source_replayed"] is True

    assert pair["provider_authenticated"] is False
    assert offline["provider_authenticated"] is False

    assert pair["same_execution_as_deterministic_demo"] is False
    assert offline["same_execution_as_deterministic_demo"] is False

    assert document["execution_lineages_are_distinct"] is True


def test_invalid_pair_anchor_fails_before_offline_execution(
    published_pair
):
    _, pair_args = published_pair
    args = list(pair_args)

    marker_index = args.index("--marker-sha256")
    args[marker_index + 1] = "0" * 64

    with patch.object(
        controls,
        "run_synthetic_control_suite",
        side_effect=AssertionError(
            "Invalid pair must fail before offline execution"
        ),
    ):
        code, output, errors = invoke([
            "--run-offline-controls", *args,
        ])

    assert code == 2
    assert output == ""
    assert "ERROR:" in errors


def test_missing_pair_anchors_fail_before_offline_execution(
    private_root
):
    with patch.object(
        controls,
        "run_synthetic_control_suite",
        side_effect=AssertionError(
            "Invalid arguments triggered offline execution"
        ),
    ):
        code, output, errors = invoke([
            "--run-offline-controls",
            "--pair-input", PAIR,
        ])

    assert code == 2
    assert output == ""
    assert "ERROR:" in errors


def test_no_fabricated_provider_details(private_root, monkeypatch):
    secret = "HETREN_OFFLINE_TEST_SECRET_NOT_A_PROVIDER_KEY"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    code, output, errors = invoke([
        "--format", "json",
        "--run-offline-controls",
    ])

    assert code == 0
    assert errors == ""
    assert secret not in output

    offline = json.loads(output)["offline_multistep_controls"]

    assert offline["provider_authenticated"] is False
    assert offline["externally_anchored"] is False
    assert "provider_response_id" not in offline
    assert "provider_reported_tokens" not in offline


def test_invalid_cli_flag_rejected(private_root):
    with redirect_stderr(StringIO()):
        with pytest.raises(SystemExit) as exc:
            review.main(["--run-offline-controls", "false"])

    assert exc.value.code == 2
