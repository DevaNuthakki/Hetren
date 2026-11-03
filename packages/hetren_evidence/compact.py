"""Compact, model-ready evidence built from a run record's evidence payload.

Kept: the task text, each tool call (tool, parsed arguments or the raw text
of malformed arguments, whether it was allowed and why not, outcome,
observation or error, and whether it changed state), the run status and
run-error type, SDK discrepancy kinds, and probe results in the same shape.

After a recovery (tier 2), the input also lists each recovery applied so
far: the action, its result, the task's re-run (``null`` for a reroute,
which re-runs nothing) and the probes made after it. Inputs without
recoveries carry no ``recoveries`` key and keep ``compact-evidence-v1``;
inputs with recoveries are ``compact-evidence-v2``.

Dropped: model ID and settings (they name the agent behaviour), provenance
and source provenance, capture IDs, every hash, invocation and call IDs,
sequence numbers, timestamps, SDK versions and hook events, instructions and
tool definitions (constant per workflow), the agent's name, and the agent's
final message.

Scripted, live and replayed runs therefore produce identically shaped input,
and two runs whose tool calls and observations match produce identical
input whatever agent produced them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any

from packages.contracts import ContractError


COMPACT_FORMAT = "compact-evidence-v1"
COMPACT_FORMAT_V2 = "compact-evidence-v2"

# Upper bound for one step's rendered input (o200k_base tokens, the gpt-4.1
# encoding). Measured over 300 sampled cases with 0-4 probes: max 585.
EVIDENCE_TOKEN_BUDGET = 800

# Tier 2 inputs after a recovery carry a second run: before probes they
# measured at most 583 tokens, and probes add up to about 300.
TIER2_EVIDENCE_TOKEN_BUDGET = 1200


def _steps(stage_records: Sequence[Mapping[str, Any]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, Mapping[str, Any]]] = {}

    for record in stage_records:
        grouped.setdefault(record["invocation_id"], {})[record["stage"]] = record

    steps: list[dict[str, object]] = []

    for stages in grouped.values():
        proposed = stages.get("proposed")
        authorized = stages.get("authorized")
        observed = stages.get("observed")
        first = proposed or authorized or observed
        step: dict[str, object] = {
            "tool": first["tool_name"],
            "args": dict((proposed or {}).get("payload", {}).get("arguments", {})),
        }

        if authorized is None:
            step["outcome"] = "not_authorized"
        elif authorized["status"] == "denied":
            step["outcome"] = "denied"
            step["reason"] = authorized["payload"]["reason"]
        elif observed is None:
            step["outcome"] = "not_observed"
        elif observed["status"] == "succeeded":
            step["outcome"] = "succeeded"
            step["observation"] = observed["payload"]["observation"]
            step["changed_state"] = observed["state_before_sha256"] != observed["state_after_sha256"]
        else:
            error = observed["payload"]["error"]
            step["outcome"] = "failed"
            step["error"] = {"type": error["type"], "message": error["message"]}
            step["changed_state"] = observed["state_before_sha256"] != observed["state_after_sha256"]

        steps.append(step)

    return steps


def _run(evidence: Mapping[str, Any]) -> dict[str, object]:
    if evidence.get("record_type") != "AgentRunRecord":
        raise ContractError("evidence must be an agent run record payload")

    error = evidence.get("error")
    return {"status": evidence["status"], "error_type": None if error is None else error["type"]}


def _recovery(recovery: Mapping[str, Any]) -> dict[str, object]:
    """One applied recovery: ``action``, its gateway ``records`` (none for
    ``rerun``), the ``rerun`` evidence payload or None, and ``probe_records``."""
    records = recovery.get("records") or []

    if records:
        result = {key: value for key, value in _steps(records)[0].items() if key not in ("tool", "args")}
    else:
        result = {"outcome": "succeeded", "changed_state": True}

    rerun = recovery.get("rerun")
    return {
        "action": dict(recovery["action"]),
        "result": result,
        "rerun": None if rerun is None else {"run": _run(rerun), "steps": _steps(rerun.get("stage_records") or [])},
        "probes": _steps(recovery.get("probe_records") or []),
    }


def compact_evidence(
    evidence: Mapping[str, Any],
    probe_records: Sequence[Mapping[str, Any]] = (),
    recoveries: Sequence[Mapping[str, Any]] = (),
) -> dict[str, object]:
    """Build the compact input from ``RunRecord.evidence_payload()`` JSON.

    ``probe_records`` are the probes made before any recovery; each of
    ``recoveries`` is described in ``_recovery``.
    """
    run = _run(evidence)
    compact = {
        "format": COMPACT_FORMAT_V2 if recoveries else COMPACT_FORMAT,
        "task": evidence["task_input"],
        "run": run,
        "steps": _steps(evidence.get("stage_records") or []),
        "discrepancies": sorted(
            item["kind"] for item in (evidence.get("sdk_evidence") or {}).get("discrepancies") or []
        ),
        "probes": _steps(probe_records),
    }

    if recoveries:
        compact["recoveries"] = [_recovery(recovery) for recovery in recoveries]

    return compact


def render_evidence(compact: Mapping[str, object]) -> str:
    """The exact text given to a model: canonical, whitespace-free JSON."""
    return json.dumps(compact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


__all__ = [
    "COMPACT_FORMAT",
    "COMPACT_FORMAT_V2",
    "EVIDENCE_TOKEN_BUDGET",
    "TIER2_EVIDENCE_TOKEN_BUDGET",
    "compact_evidence",
    "render_evidence",
]
