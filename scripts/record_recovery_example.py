#!/usr/bin/env python3
"""Record LIVE captures for the recovery example in one process.

Runs the support harness once: the faulty run, Hetren's diagnosis, probes,
gated correction and re-run, and the verifier's regression run. Every agent
run is recorded live into ``<output-root>/<run-id>/capture-NNNN.json``.

Guards, all checked before any client exists:

- ``--confirm-live`` must be given;
- ``OPENAI_API_KEY`` must be set;
- ``--first-run-id`` must be a neutral ``run-NNNN`` identifier;
- the directory for every run the example may need must be absent or empty.

``store=False`` comes from the agent definition and is enforced for live
runs. The run-ID-to-example mapping is never written to disk.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

CONFIRMATION_FLAG = "--confirm-live"
EXAMPLE = "example_verified_recovery"
RUNS_NEEDED = 3
NEUTRAL_RUN_ID = re.compile(r"run-([0-9]{4})")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, help="OpenAI model name to record")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--first-run-id", required=True, help="neutral run ID, run-NNNN")
    parser.add_argument(CONFIRMATION_FLAG, action="store_true", dest="confirm_live")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if not args.confirm_live:
        print(f"STOP: live recording requires {CONFIRMATION_FLAG}", file=sys.stderr)
        return 2

    if not os.environ.get("OPENAI_API_KEY"):
        print("STOP: OPENAI_API_KEY is not set", file=sys.stderr)
        return 2

    match = NEUTRAL_RUN_ID.fullmatch(args.first_run_id)

    if match is None:
        print("STOP: --first-run-id must be a neutral run-NNNN identifier", file=sys.stderr)
        return 2

    first = int(match.group(1))
    planned = [f"run-{number:04d}" for number in range(first, first + RUNS_NEEDED)]

    for run_id in planned:
        directory = args.output_root / run_id

        if directory.exists() and any(directory.iterdir()):
            print(f"STOP: {directory} must be empty or new", file=sys.stderr)
            return 2

    sys.path.insert(0, str(REPO_ROOT))

    from openai import AsyncOpenAI

    from packages.support_examples import SupportHarness, live_recording_source

    harness = SupportHarness(
        example_name=EXAMPLE,
        model_source=live_recording_source(
            root=args.output_root, model=args.model, client=AsyncOpenAI(),
        ),
        first_run_number=first,
    )
    result = harness.run_example()

    for run in result.runs:
        print(
            f"{run.record.run_id} [{run.role}]: {run.record.status.value}; "
            f"captures: {', '.join(run.record.recorded_capture_ids) or 'none'}"
        )

    print(f"hetren diagnosis: {result.frozen.outcome.diagnosis.outcome.value}")
    print(f"hetren claims fix: {result.frozen.outcome.claims_fix}")
    print(f"verifier verdict: {result.verification.evaluator_verdict.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
