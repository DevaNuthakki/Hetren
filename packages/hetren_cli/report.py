"""The diagnosis report (text or JSON). Every report states the scope, that nothing was applied, and the
shipped variant's validation result."""

from __future__ import annotations

import json
from typing import Any

from packages.action_space import VERBS


SCOPE = ("Scope: the model was trained only on Hetren's synthetic support workflow (read_ticket, lookup_account, "
         "route_ticket). It is not a general agent-trace diagnoser; outside that workflow its output means nothing. "
         "The CLI handles single-recovery (tier 1) support runs only: two-step recovery is not supported here, "
         "although the model was validated on it.")

# docs/milestone-4/EXPORT_LOG.md, "Acceptance and shipping (Amendment 2)" (a test checks the numbers there).
VALIDATION = {
    "Q4_K_M": ("Validation (Amendment 2, on macOS x86_64): accepted and shipped by default. Decision accuracy "
               "vs the fp16 model: -0.13 points pooled (95% CI -1.50 to +1.25); same episode as fp16 in 79.6% of "
               "cases. More conservative than fp16 in tier 2: left 30 broken cases without intervention "
               "(fp16: 15) and made 0 wrong interventions on 54 healthy cases (fp16: 1)."),
    "Q8_0": ("Validation (Amendment 2, on macOS x86_64): accepted; the higher-fidelity alternative. Decision "
             "accuracy vs the fp16 model: -0.75 points pooled (95% CI -1.38 to -0.25); same episode as fp16 in "
             "92.6% of cases."),
}

KIND_TITLES = {"decide": "Decision", "recover": "Proposed recovery", "probe": "Needs probe"}


def summary(action: dict[str, Any]) -> dict[str, object]:
    """The outcome of one action: what the model chose and what it means here."""
    kind, verb = action["action"], action["verb"]
    notes = {
        "decide": [],
        "recover": ["Not applied. Check it against the real system before applying it."],
        "probe": ["The model asks for more evidence before deciding. This probe needs the support environment, "
                  "which an offline diagnosis does not have, so no decision or recovery was made."],
    }[kind]
    return {"outcome": {"decide": "decision", "recover": "proposed_recovery", "probe": "needs_probe"}[kind],
            "action": action, "meaning": VERBS[verb].description, "notes": notes}


def _call(action: dict[str, Any]) -> str:
    args = json.dumps(action["args"], sort_keys=True) if action["args"] else ""
    return f"{action['verb']} {args}".rstrip()


def text(report: dict[str, Any]) -> str:
    lines = ["Hetren diagnosis (proposed only; nothing was applied)", ""]
    result = report["result"]

    if result["outcome"] == "invalid_reply":
        lines += ["  The model's reply is not a valid action, so there is no diagnosis.",
                  f"  Reason: {result['error']}", f"  Reply: {result['reply']!r}"]
    else:
        action = result["action"]
        lines.append(f"  {KIND_TITLES[action['action']]}: {_call(action)}")
        lines.append(f"    {result['meaning']}")
        lines += [f"    {note}" for note in result["notes"]]

    run = report["input"]
    lines += ["", f"Run: {run['task']!r}, {run['tool_calls']} tool calls, status {run['status']}"
              + (f", {run['probes']} probe results" if run["probes"] else "")]

    model, server = report["model"], report["server"]
    build = server.get("commit") or "unknown build"
    validated = "the validated build" if server.get("validated_build") else "NOT the validated build"
    sha = model["gguf_sha256"][:12] + "…" if model.get("gguf_sha256") else "sha256 not checked (external server)"
    lines += [f"Model: {model['variant']} ({sha}), prompt version {report['prompt_version']}, "
              f"llama.cpp {build} ({validated})"
              + (f", {server['threads']} threads" if server.get("threads") else "")]

    if report.get("stopped_on_other_token"):
        lines.append("Note: generation ended on a token other than <|im_end|> or <|endoftext|>.")

    lines += [VALIDATION[model["variant"]], SCOPE]
    return "\n".join(lines) + "\n"


def as_json(report: dict[str, Any]) -> str:
    return json.dumps({**report, "scope": SCOPE, "validation": VALIDATION[report["model"]["variant"]]},
                      indent=2, sort_keys=True) + "\n"


__all__ = ["SCOPE", "VALIDATION", "as_json", "summary", "text"]
