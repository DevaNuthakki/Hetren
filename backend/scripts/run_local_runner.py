#!/usr/bin/env python3
from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path
from threading import Event
from typing import Callable, TextIO

from pydantic import ValidationError


BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.local_runner_client import (
    LocalRunnerClient,
    LocalRunnerClientError,
    build_local_runner_client,
)
from app.local_runner_execution import (
    LocalRunnerExecutionError,
    LocalRunnerLoopSummary,
    run_local_runner_loop,
)
from app.runner_config import (
    LocalRunnerSettings,
    get_local_runner_settings,
)


SettingsFactory = Callable[[], LocalRunnerSettings]
ClientFactory = Callable[
    [LocalRunnerSettings],
    LocalRunnerClient,
]
LoopRunner = Callable[..., LocalRunnerLoopSummary]


CI_EXIT_SUCCESS = 0
CI_EXIT_RUNNER_ERROR = 1
CI_EXIT_CONFIGURATION_ERROR = 2
CI_EXIT_NO_JOB = 3
CI_EXIT_JOB_FAILED = 4
CI_EXIT_JOB_CANCELLED = 5
CI_EXIT_STOPPED = 6


def resolve_ci_exit_code(
    summary: LocalRunnerLoopSummary,
) -> int:
    """
    Convert a one-cycle runner summary into a CI process result.

    CI succeeds only when exactly one job completes. Idle, failed,
    cancelled, and stopped outcomes use distinct nonzero exit codes.
    """
    if (
        summary.cycle_count == 1
        and summary.completed_count == 1
        and summary.idle_count == 0
        and summary.failed_count == 0
        and summary.cancelled_count == 0
        and summary.stopped is False
    ):
        return CI_EXIT_SUCCESS

    if summary.failed_count > 0:
        return CI_EXIT_JOB_FAILED

    if summary.cancelled_count > 0:
        return CI_EXIT_JOB_CANCELLED

    if summary.stopped:
        return CI_EXIT_STOPPED

    if summary.idle_count > 0:
        return CI_EXIT_NO_JOB

    return CI_EXIT_RUNNER_ERROR


def positive_integer(value: str) -> int:
    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Value must be an integer."
        ) from exc

    if parsed_value <= 0:
        raise argparse.ArgumentTypeError(
            "Value must be greater than zero."
        )

    return parsed_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the standalone Hetren local runner polling loop."
        ),
    )

    execution_mode = (
        parser.add_mutually_exclusive_group()
    )

    execution_mode.add_argument(
        "--max-cycles",
        type=positive_integer,
        default=None,
        help=(
            "Stop after this many polling cycles. "
            "By default, the runner continues until stopped."
        ),
    )

    execution_mode.add_argument(
        "--ci",
        action="store_true",
        help=(
            "Run exactly one polling cycle and return a "
            "CI-safe exit code based on the observed outcome."
        ),
    )

    return parser


def build_stop_handler(
    stop_event: Event,
):
    def request_stop(
        _signal_number: int,
        _frame: object | None,
    ) -> None:
        stop_event.set()

    return request_stop


def install_stop_signal_handlers(
    stop_event: Event,
) -> dict[int, object]:
    previous_handlers: dict[int, object] = {}
    stop_handler = build_stop_handler(stop_event)

    for signal_number in (
        signal.SIGINT,
        signal.SIGTERM,
    ):
        previous_handlers[signal_number] = (
            signal.getsignal(signal_number)
        )
        signal.signal(
            signal_number,
            stop_handler,
        )

    return previous_handlers


def restore_signal_handlers(
    previous_handlers: dict[int, object],
) -> None:
    for signal_number, handler in (
        previous_handlers.items()
    ):
        signal.signal(
            signal_number,
            handler,
        )


def run_cli(
    argv: list[str] | None = None,
    *,
    settings_factory: SettingsFactory = (
        get_local_runner_settings
    ),
    client_factory: ClientFactory = (
        build_local_runner_client
    ),
    loop_runner: LoopRunner = run_local_runner_loop,
    stop_event: Event | None = None,
    install_signal_handlers: bool = True,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    args = build_parser().parse_args(argv)

    runner_stop_event = stop_event or Event()
    previous_handlers: dict[int, object] = {}
    resolved_max_cycles = (
        1
        if args.ci
        else args.max_cycles
    )

    try:
        if install_signal_handlers:
            previous_handlers = (
                install_stop_signal_handlers(
                    runner_stop_event
                )
            )

        try:
            settings = settings_factory()
        except ValidationError:
            print(
                "ERROR: Local runner configuration is invalid.",
                file=error_output,
            )
            return CI_EXIT_CONFIGURATION_ERROR

        try:
            with client_factory(settings) as client:
                summary = loop_runner(
                    client=client,
                    settings=settings,
                    stop_event=runner_stop_event,
                    max_cycles=resolved_max_cycles,
                )
        except KeyboardInterrupt:
            runner_stop_event.set()
            print(
                "Local runner interrupted.",
                file=error_output,
            )
            return 130
        except (
            LocalRunnerClientError,
            LocalRunnerExecutionError,
        ):
            print(
                "ERROR: Local runner stopped because a "
                "runner API or execution operation failed.",
                file=error_output,
            )
            return CI_EXIT_RUNNER_ERROR
    finally:
        if previous_handlers:
            restore_signal_handlers(
                previous_handlers
            )

    print("Local runner stopped.", file=output)
    print(
        f"Cycles: {summary.cycle_count}",
        file=output,
    )
    print(
        f"Idle cycles: {summary.idle_count}",
        file=output,
    )
    print(
        f"Completed jobs: {summary.completed_count}",
        file=output,
    )
    print(
        f"Failed jobs: {summary.failed_count}",
        file=output,
    )
    print(
        f"Cancelled jobs: {summary.cancelled_count}",
        file=output,
    )
    print(
        f"Timed-out jobs: {summary.timed_out_count}",
        file=output,
    )
    print(
        "Stop requested: "
        + ("yes" if summary.stopped else "no"),
        file=output,
    )

    if args.ci:
        return resolve_ci_exit_code(summary)

    return CI_EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(run_cli())
