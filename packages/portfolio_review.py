"""Optional evidence-backed reviewer view of distinct Hetren demonstrations.

The deterministic repair demonstration and synthetic incident evidence pair
are separate executions. Presenting them together does not establish that
either execution repaired the other, or that any provider was authenticated.

The default mode works from a clean checkout. Optional paired verification
requires all three externally supplied document fingerprints.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from packages import portfolio_demo
from packages.contracts import ContractError


_REPORT_TYPE = "hetren_portfolio_review"
_SCHEMA_VERSION = 1

_CLAIM_LIMITS = (
    "Deterministic repair and paired synthetic incident evidence are separate executions.",
    "Paired evidence verification replays saved synthetic sources, not a live model.",
    "SHA-256 fingerprints check retained bytes; they do not authenticate a provider.",
    "This does not establish general agent repair, production safety, or deployment approval.",
)


def build_review_report(
    *,
    pair_input: str | None = None,
    marker_sha256: str | None = None,
    report_sha256: str | None = None,
    source_sha256: str | None = None,
) -> dict[str, object]:
    """Build a bounded, evidence-aware view without publishing anything."""
    anchors = (marker_sha256, report_sha256, source_sha256)

    if pair_input is None:
        if any(value is not None for value in anchors):
            raise ValueError(
                "trusted evidence hashes require --pair-input"
            )
    elif any(value is None for value in anchors):
        raise ValueError(
            "paired review requires marker, report and source SHA-256 anchors"
        )

    pair_summary = None

    if pair_input is not None:
        # Imported only on explicit request; default mode needs no evidence.
        from packages.engines.behavioral import (
            model_incident_paired_export_development as paired,
        )

        verified = paired.verify_paired_development_evidence(
            pair_input,
            expected_marker_sha256=marker_sha256,
            expected_report_sha256=report_sha256,
            expected_source_sha256=source_sha256,
        )

        if verified.provider_authenticated is not False:
            raise ContractError(
                "synthetic evidence unexpectedly claims provider authentication"
            )

        pair_summary = {
            "record_type": "synthetic_development_evidence_pair",
            "report_path": pair_input,
            "report_filename": verified.report_filename,
            "source_filename": verified.source_filename,
            "marker_filename": verified.marker_filename,
            "report_sha256": verified.report_sha256,
            "source_sha256": verified.source_sha256,
            "marker_sha256": verified.marker_sha256,
            "manifest_sha256": verified.manifest_sha256,
            "evaluation_sha256": verified.evaluation_sha256,
            "suite_evidence_sha256": verified.suite_evidence_sha256,
            "case_count": verified.case_count,
            "correct_count": verified.correct_count,
            "source_replayed": True,
            "externally_anchored": True,
            "provider_authenticated": False,
            "development_only": True,
            "same_execution_as_deterministic_demo": False,
        }

    # Preserve the existing deterministic demonstration implementation.
    deterministic = portfolio_demo.build_demo_report()

    return {
        "report_type": _REPORT_TYPE,
        "schema_version": _SCHEMA_VERSION,
        "deterministic_demo": deterministic,
        "paired_synthetic_evidence": pair_summary,
        "execution_lineages_are_distinct": True,
        "claim_limits": list(_CLAIM_LIMITS),
    }


def render_json(report: dict[str, object]) -> str:
    """Stable machine-readable reviewer output."""
    return json.dumps(
        report,
        sort_keys=True,
        indent=2,
        ensure_ascii=True,
        allow_nan=False,
    )


def render_text(report: dict[str, object]) -> str:
    """Render both evidence scopes without conflating their results."""
    lines = [
        "Hetren evidence-backed portfolio review",
        "======================================",
        "",
        "1. Deterministic repair and verification",
        "",
        portfolio_demo.render_text(report["deterministic_demo"]),
        "",
        "2. Separate synthetic incident evidence",
    ]

    pair = report["paired_synthetic_evidence"]

    if pair is None:
        lines.append(
            "  Not supplied (clean-checkout demonstration mode)."
        )
    else:
        lines.extend((
            "  SOURCE REPLAY PASS: retained synthetic evidence",
            f"  Report: {pair['report_path']}",
            f"  Cases: {pair['case_count']}",
            f"  Correct cases: {pair['correct_count']}",
            f"  Report SHA256: {pair['report_sha256']}",
            f"  Source SHA256: {pair['source_sha256']}",
            f"  Marker SHA256: {pair['marker_sha256']}",
            "  Externally anchored: True",
            "  Provider authenticated: False",
        ))

    lines.extend((
        "",
        "Execution boundaries:",
        "  These demonstrations have separate execution lineages.",
        "  Paired evidence does not establish live provider authenticity.",
        "",
        "Claim limits:",
    ))

    lines.extend(
        f"  - {limit}" for limit in report["claim_limits"]
    )

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Review deterministic Hetren behavior and optionally "
            "verify separately retained synthetic incident evidence."
        )
    )

    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    parser.add_argument(
        "--pair-input",
        default=None,
        help=(
            "Optional canonical repository-relative synthetic report path"
        ),
    )

    for part in ("marker", "report", "source"):
        parser.add_argument(
            f"--{part}-sha256",
            default=None,
            help=f"Externally trusted {part} SHA-256 for paired review",
        )

    args = parser.parse_args(argv)

    try:
        review = build_review_report(
            pair_input=args.pair_input,
            marker_sha256=args.marker_sha256,
            report_sha256=args.report_sha256,
            source_sha256=args.source_sha256,
        )

        output = (
            render_json(review)
            if args.format == "json"
            else render_text(review)
        )
    except (ContractError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
