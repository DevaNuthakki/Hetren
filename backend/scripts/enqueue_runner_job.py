#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, TextIO

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.runner_job_service import (
    RunnerJobEnqueueConflictError,
    RunnerJobProjectNotFoundError,
    enqueue_job,
)


SessionFactory = Callable[[], Session]


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


def json_object(value: str) -> dict[str, object]:
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            "Value must be valid JSON."
        ) from exc

    if not isinstance(parsed_value, dict):
        raise argparse.ArgumentTypeError(
            "Value must be a JSON object."
        )

    return parsed_value


def timezone_aware_datetime(value: str) -> datetime:
    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed_value = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Value must be a valid ISO 8601 datetime."
        ) from exc

    if (
        parsed_value.tzinfo is None
        or parsed_value.utcoffset() is None
    ):
        raise argparse.ArgumentTypeError(
            "Datetime must include a UTC offset."
        )

    return parsed_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Enqueue a controlled project-scoped Ovrin runner job. "
            "Only allowlisted job types are accepted."
        ),
    )

    parser.add_argument(
        "--project-id",
        required=True,
        type=positive_integer,
        help="Ovrin project ID that will own the job.",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Human-readable runner job name.",
    )
    parser.add_argument(
        "--job-type",
        required=True,
        help="Allowlisted runner job type.",
    )
    parser.add_argument(
        "--capability",
        action="append",
        default=[],
        help=(
            "Required runner capability. Repeat this option "
            "for multiple capabilities."
        ),
    )
    parser.add_argument(
        "--input-json",
        type=json_object,
        default=None,
        help=(
            "Structured JSON object passed to the runner. "
            "No shell commands are executed."
        ),
    )
    parser.add_argument(
        "--priority",
        type=int,
        default=0,
        help=(
            "Queue priority from -1000 to 1000. "
            "Higher values are claimed first."
        ),
    )
    parser.add_argument(
        "--available-at",
        type=timezone_aware_datetime,
        default=None,
        help=(
            "Optional ISO 8601 availability time with "
            "a UTC offset."
        ),
    )
    parser.add_argument(
        "--max-attempts",
        type=positive_integer,
        default=3,
        help="Maximum claim attempts. Default: 3.",
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
        job = enqueue_job(
            db,
            project_id=args.project_id,
            name=args.name,
            job_type=args.job_type,
            required_capabilities=args.capability,
            input_payload=args.input_json,
            priority=args.priority,
            available_at=args.available_at,
            max_attempts=args.max_attempts,
        )

        public_id = job.public_id
        project_id = job.project_id
        name = job.name
        job_type = job.job_type
        status = job.status
        priority = job.priority
        max_attempts = job.max_attempts
        available_at = job.available_at.isoformat()
        capabilities = list(job.required_capabilities)
    except RunnerJobProjectNotFoundError as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=error_output)
        return 2
    except ValueError as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=error_output)
        return 2
    except RunnerJobEnqueueConflictError:
        db.rollback()
        print(
            "ERROR: The runner job could not be enqueued.",
            file=error_output,
        )
        return 1
    except SQLAlchemyError:
        db.rollback()
        print(
            "ERROR: The runner job could not be enqueued.",
            file=error_output,
        )
        return 1
    finally:
        db.close()

    print("Runner job enqueued successfully.", file=output)
    print(f"Job public ID: {public_id}", file=output)
    print(f"Project ID: {project_id}", file=output)
    print(f"Name: {name}", file=output)
    print(f"Job type: {job_type}", file=output)
    print(f"Status: {status}", file=output)
    print(f"Priority: {priority}", file=output)
    print(f"Maximum attempts: {max_attempts}", file=output)
    print(f"Available at: {available_at}", file=output)
    print(
        "Required capabilities: "
        + (
            ", ".join(capabilities)
            if capabilities
            else "none"
        ),
        file=output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
