"""The prompt shared by every model baseline (``gpt-4.1`` and the untrained and
fine-tuned small model).

A model policy makes one stateless call per action: the system prompt
(``system_prompt``) describes the task, the generic action catalog and the
output format; the user message is the step's compact evidence exactly as
``render_evidence`` writes it (probe results and, in tier 2, applied
recoveries included). Nothing names a fault family, a case kind or an
agent behaviour.

``action_text`` takes the model's reply and strips surrounding whitespace
and one enclosing Markdown code fence, the same for every model; the rest
must parse with ``parse_action``, otherwise the episode ends with an
invalid-action failure.
"""

from __future__ import annotations

import json
import re

from packages.action_space import PROBE_BUDGET, VERBS


PROMPT_VERSION = 1

_FENCE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _catalog(kind: str) -> str:
    return "\n".join(
        f"- {name}: {spec.description} args: {json.dumps(spec.args_schema, sort_keys=True, separators=(',', ':'))}"
        for name, spec in VERBS.items() if spec.kind == kind
    )


def system_prompt(max_recoveries: int = 1) -> str:
    """The system prompt; ``max_recoveries`` 2 adds the tier 2 rules."""
    if max_recoveries == 1:
        ending = (
            "The episode ends at your first recover or decide action. Choose the smallest change that fixes "
            "the run."
        )
    else:
        ending = (
            f"You may recover up to {max_recoveries} times. After a recovery the harness applies it to the "
            "real system (re-running the task where the action calls for it) and shows you the result under "
            "\"recoveries\", with any probes you make after it; probes remain read-only and share the same "
            "budget. After a recovery, either recover once more or stop with no_intervention when the run "
            "is now correct. Any other decision after a recovery is wrong. The episode ends at a decision or "
            f"at your recovery number {max_recoveries}. Choose the smallest changes that fix the run."
        )

    return f"""You review a customer-support agent's run and decide what, if anything, to do about it.

The user message is a JSON record of one run: the task, every tool call the agent made (arguments, outcome, observation or error, and whether it changed state), the run status, and the results of the probes you have made so far.

Reply with exactly one action as a single JSON object and nothing else:
{{"action": "<probe|recover|decide>", "verb": "<verb>", "args": {{...}}}}

Probes are read-only checks on a copy of the current system. You may make at most {PROBE_BUDGET} probes; asking for another ends the episode as a failure. Each probe's result is added to the record you see next.
{_catalog("probe")}

Recoveries change the real system and are checked by execution: the fix must make the run's outcome correct without breaking other tickets.
{_catalog("recover")}

Decisions end the episode.
{_catalog("decide")}

- no_intervention: the run's outcome is already correct.
- insufficient_evidence: an observation the task requires is absent from the record and nothing explains the absence (it was withheld, truncated or never attempted). A failed tool call is itself an observation, not missing evidence. List the missing observations as short snake_case codes.
- abstain: the evidence is complete, but no available recovery would make the run correct. Give the reason as a short snake_case code.

{ending}

IDs in args must be IDs that appear in the record."""


def user_message(compact_text: str) -> str:
    """The user message: the rendered compact evidence, unchanged."""
    return compact_text


def action_text(reply: str) -> str:
    """The action JSON from a model reply (whitespace and one code fence stripped)."""
    text = reply.strip()
    fenced = _FENCE.match(text)
    return fenced.group(1).strip() if fenced else text


__all__ = [
    "PROMPT_VERSION",
    "action_text",
    "system_prompt",
    "user_message",
]
