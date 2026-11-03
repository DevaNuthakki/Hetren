"""Hetren-side evidence preparation (no environment or evaluator imports)."""

from .compact import (
    COMPACT_FORMAT,
    COMPACT_FORMAT_V2,
    EVIDENCE_TOKEN_BUDGET,
    TIER2_EVIDENCE_TOKEN_BUDGET,
    compact_evidence,
    render_evidence,
)


__all__ = [
    "COMPACT_FORMAT",
    "COMPACT_FORMAT_V2",
    "EVIDENCE_TOKEN_BUDGET",
    "TIER2_EVIDENCE_TOKEN_BUDGET",
    "compact_evidence",
    "render_evidence",
]
