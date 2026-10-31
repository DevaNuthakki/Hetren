"""Hetren-side evidence preparation (no environment or evaluator imports)."""

from .compact import COMPACT_FORMAT, EVIDENCE_TOKEN_BUDGET, compact_evidence, render_evidence


__all__ = [
    "COMPACT_FORMAT",
    "EVIDENCE_TOKEN_BUDGET",
    "compact_evidence",
    "render_evidence",
]
