#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path
from typing import Callable, TextIO

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.runner_service import (
    RunnerProjectNotFoundError,
    issue_registration_token,
)


SessionFactory = Callable[[], Session]


def positive_integer(value: str) -> int:
    parsed_value = int(value)

    if parsed_value <= 0:
        raise argparse.ArgumentTypeError(
            "Value must be greater than zero."
        )

    return parsed_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Issue a one-time Ovrin runner registration token. "
            "The plaintext token is displayed only once."
        ),
    )

    parser.add_argument(
        "--project-id",
        required=True,
        type=positive_integer,
        help="Ovrin project ID that will own the runner.",
    )
    parser.add_argument(
        "--label",
        default="Runner registration token",
        help="Administrative label for the token.",
    )
    parser.add_argument(
        "--ttl-minutes",
        default=30,
        type=positive_integer,
        help="Token lifetime in minutes. Default: 30.",
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
        issued = issue_registration_token(
            db,
            project_id=args.project_id,
            label=args.label,
            ttl=timedelta(minutes=args.ttl_minutes),
        )

        project_id = issued.record.project_id
        label = issued.record.label
        expires_at = issued.record.expires_at.isoformat()
        plaintext_token = issued.token
    except RunnerProjectNotFoundError as exc:
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
            "ERROR: The registration token could not be persisted.",
            file=error_output,
        )
        return 1
    finally:
        db.close()

    print("Runner registration token issued successfully.", file=output)
    print(f"Project ID: {project_id}", file=output)
    print(f"Label: {label}", file=output)
    print(f"Expires at: {expires_at}", file=output)
    print(
        "Store this token securely. It will not be shown again.",
        file=output,
    )
    print(
        f"Registration token: {plaintext_token}",
        file=output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
