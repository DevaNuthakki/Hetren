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
from app.runner_service import (
    RunnerNotFoundError,
    revoke_runner,
)


SessionFactory = Callable[[], Session]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Revoke an Hetren runner and invalidate its credential."
        ),
    )

    parser.add_argument(
        "--runner-public-id",
        required=True,
        help="Public ID returned when the runner was registered.",
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
        runner = revoke_runner(
            db,
            public_id=args.runner_public_id,
        )

        public_id = runner.public_id
        name = runner.name
        revoked_at = runner.revoked_at.isoformat()
    except RunnerNotFoundError as exc:
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
            "ERROR: The runner could not be revoked.",
            file=error_output,
        )
        return 1
    finally:
        db.close()

    print("Runner revoked successfully.", file=output)
    print(f"Runner public ID: {public_id}", file=output)
    print(f"Runner name: {name}", file=output)
    print(f"Revoked at: {revoked_at}", file=output)
    print(
        "The runner credential can no longer authenticate.",
        file=output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
