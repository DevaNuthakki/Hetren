#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, TextIO

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.runner_job_service import (
    MAX_EXPIRED_JOB_RECOVERY_BATCH,
    RunnerJobTransitionUnavailableError,
    recover_expired_jobs,
)


SessionFactory = Callable[[], Session]


def recovery_limit(value: str) -> int:
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

    if parsed_value > MAX_EXPIRED_JOB_RECOVERY_BATCH:
        raise argparse.ArgumentTypeError(
            "Value must not exceed 1000."
        )

    return parsed_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recover Hetren runner jobs whose claim leases "
            "have expired."
        ),
    )

    parser.add_argument(
        "--limit",
        type=recovery_limit,
        default=100,
        help=(
            "Maximum number of expired jobs to recover. "
            "Default: 100. Maximum: 1000."
        ),
    )

    return parser


def run_cli(
    argv: list[str] | None = None,
    *,
    session_factory: SessionFactory = SessionLocal,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    args = build_parser().parse_args(argv)

    db = session_factory()

    try:
        summary = recover_expired_jobs(
            db,
            limit=args.limit,
        )
    except ValueError as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=error_output)
        return 2
    except RunnerJobTransitionUnavailableError:
        db.rollback()
        print(
            "ERROR: Expired runner jobs could not be recovered.",
            file=error_output,
        )
        return 1
    except SQLAlchemyError:
        db.rollback()
        print(
            "ERROR: Expired runner jobs could not be recovered.",
            file=error_output,
        )
        return 1
    finally:
        db.close()

    print(
        "Expired runner-job recovery completed.",
        file=output,
    )
    print(
        f"Recovered jobs: {summary.recovered_count}",
        file=output,
    )
    print(
        f"Requeued jobs: {summary.requeued_count}",
        file=output,
    )
    print(
        f"Failed jobs: {summary.failed_count}",
        file=output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
