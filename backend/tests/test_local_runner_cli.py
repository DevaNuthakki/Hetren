import argparse
from io import StringIO
from threading import Event

import pytest
from pydantic import ValidationError

from app.local_runner_client import (
    LocalRunnerClientError,
)
from app.local_runner_execution import (
    LocalRunnerLoopSummary,
)
from app.runner_config import LocalRunnerSettings
from scripts.run_local_runner import (
    build_stop_handler,
    positive_integer,
    run_cli,
)


def build_settings() -> LocalRunnerSettings:
    return LocalRunnerSettings(
        _env_file=None,
        OVRIN_RUNNER_API_URL=(
            "https://ovrin.example.com"
        ),
        OVRIN_RUNNER_CREDENTIAL=(
            "ovrin_runner_test-credential"
        ),
        OVRIN_RUNNER_LEASE_SECONDS=600,
        OVRIN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS=60,
    )


class FakeClient:
    def __enter__(self):
        return self

    def __exit__(
        self,
        _exception_type,
        _exception,
        _traceback,
    ):
        return None


def test_positive_integer_validation():
    assert positive_integer("3") == 3

    with pytest.raises(
        argparse.ArgumentTypeError,
    ):
        positive_integer("0")


def test_run_cli_runs_bounded_loop_and_reports_summary():
    output = StringIO()
    error_output = StringIO()
    captured: dict[str, object] = {}

    def loop_runner(**kwargs):
        captured.update(kwargs)

        return LocalRunnerLoopSummary(
            cycle_count=3,
            idle_count=1,
            completed_count=1,
            failed_count=1,
            stopped=False,
        )

    exit_code = run_cli(
        ["--max-cycles", "3"],
        settings_factory=build_settings,
        client_factory=lambda _settings: FakeClient(),
        loop_runner=loop_runner,
        install_signal_handlers=False,
        stdout=output,
        stderr=error_output,
    )

    assert exit_code == 0
    assert captured["max_cycles"] == 3
    assert isinstance(captured["stop_event"], Event)

    assert output.getvalue() == (
        "Local runner stopped.\n"
        "Cycles: 3\n"
        "Idle cycles: 1\n"
        "Completed jobs: 1\n"
        "Failed jobs: 1\n"
        "Stop requested: no\n"
    )
    assert error_output.getvalue() == ""


def test_run_cli_maps_invalid_configuration():
    output = StringIO()
    error_output = StringIO()

    def invalid_settings():
        try:
            LocalRunnerSettings(_env_file=None)
        except ValidationError as exc:
            raise exc

        raise AssertionError(
            "Validation error was expected."
        )

    exit_code = run_cli(
        [],
        settings_factory=invalid_settings,
        client_factory=lambda _settings: FakeClient(),
        install_signal_handlers=False,
        stdout=output,
        stderr=error_output,
    )

    assert exit_code == 2
    assert output.getvalue() == ""
    assert error_output.getvalue() == (
        "ERROR: Local runner configuration is invalid.\n"
    )


def test_run_cli_hides_runner_failure_details():
    output = StringIO()
    error_output = StringIO()

    def failing_loop(**_kwargs):
        raise LocalRunnerClientError(
            "Sensitive API failure details."
        )

    exit_code = run_cli(
        [],
        settings_factory=build_settings,
        client_factory=lambda _settings: FakeClient(),
        loop_runner=failing_loop,
        install_signal_handlers=False,
        stdout=output,
        stderr=error_output,
    )

    assert exit_code == 1
    assert output.getvalue() == ""
    assert "Sensitive API" not in (
        error_output.getvalue()
    )
    assert error_output.getvalue() == (
        "ERROR: Local runner stopped because a "
        "runner API or execution operation failed.\n"
    )


def test_stop_handler_sets_event():
    stop_event = Event()
    handler = build_stop_handler(stop_event)

    assert stop_event.is_set() is False

    handler(2, None)

    assert stop_event.is_set() is True
