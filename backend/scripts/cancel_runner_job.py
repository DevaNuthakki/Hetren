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
    RunnerJobCancellationUnavailableError,
    RunnerJobNotFoundError,
    cancel_job,
)


SessionFactory = Callable[[], Session]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Cancel an Hetren runner job and invalidate "
            "any active claim."
        ),
    )

    parser.add_argument(
        "--job-public-id",
        required=True,
        help="Public ID of the runner job to cancel.",
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
        job = cancel_job(
            db,
            job_public_id=args.job_public_id,
        )

        public_id = job.public_id
        name = job.name
        status = job.status
        cancelled_at = job.cancelled_at.isoformat()
    except RunnerJobNotFoundError as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=error_output)
        return 2
    except RunnerJobCancellationUnavailableError as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=error_output)
        return 2
    except ValueError as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=error_output)
        return 2
    except SQLAlchemyError:
        db.rollback()
        print(
            "ERROR: The runner job could not be cancelled.",
            file=error_output,
        )
        return 1
    finally:
        db.close()

    print("Runner job cancelled successfully.", file=output)
    print(f"Job public ID: {public_id}", file=output)
    print(f"Job name: {name}", file=output)
    print(f"Status: {status}", file=output)
    print(f"Cancelled at: {cancelled_at}", file=output)
    print(
        "Any active claim token can no longer be used.",
        file=output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
