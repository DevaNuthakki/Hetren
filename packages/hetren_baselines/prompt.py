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

Versions (each measured and reported separately; ``system_prompt`` keeps
every version reproducible):

- 1: the output format given only as ``"<probe|recover|decide>"``. On
  validation, ``gpt-4.1`` put the verb in the ``action`` field in 46% of
  replies.
- 2: format fix only. Every verb is listed with its action type, and each
  type has one example. Nothing else changes, and parsing stays strict.
"""

from __future__ import annotations

import json
import re

from packages.action_space import PROBE_BUDGET, VERBS


PROMPT_VERSION = 2
PROMPT_VERSIONS = (1, 2)

# One example per action type (version 2); the IDs are placeholders.
EXAMPLES = {
    "probe": {"action": "probe", "verb": "inspect", "args": {"entity": "ticket", "id": "T-0000"}},
    "recover": {"action": "recover", "verb": "set_mapping", "args": {"customer_ref": "C-0000", "account_id": "A-0000"}},
    "decide": {"action": "decide", "verb": "no_intervention", "args": {}},
}

_FENCE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _catalog(kind: str, version: int) -> str:
    lines = "\n".join(
        f"- {name}{f' (action \"{kind}\")' if version >= 2 else ''}: {spec.description} "
        f"args: {json.dumps(spec.args_schema, sort_keys=True, separators=(',', ':'))}"
        for name, spec in VERBS.items() if spec.kind == kind
    )

    if version >= 2:
        lines += f"\nExample: {json.dumps(EXAMPLES[kind])}"

    return lines


def system_prompt(max_recoveries: int = 1, version: int = PROMPT_VERSION) -> str:
    """The system prompt; ``max_recoveries`` 2 adds the tier 2 rules."""
    if version not in PROMPT_VERSIONS:
        raise ValueError(f"unknown prompt version {version}")

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

    if version >= 2:
        format_rule = (
            "Reply with exactly one action as a single JSON object and nothing else. \"action\" is the action "
            "type, one of \"probe\", \"recover\" or \"decide\", never the verb; \"verb\" is one of the verbs "
            "below; \"args\" are its arguments:"
        )
    else:
        format_rule = "Reply with exactly one action as a single JSON object and nothing else:"

    return f"""You review a customer-support agent's run and decide what, if anything, to do about it.

The user message is a JSON record of one run: the task, every tool call the agent made (arguments, outcome, observation or error, and whether it changed state), the run status, and the results of the probes you have made so far.

{format_rule}
{{"action": "<probe|recover|decide>", "verb": "<verb>", "args": {{...}}}}

Probes are read-only checks on a copy of the current system. You may make at most {PROBE_BUDGET} probes; asking for another ends the episode as a failure. Each probe's result is added to the record you see next.
{_catalog("probe", version)}

Recoveries change the real system and are checked by execution: the fix must make the run's outcome correct without breaking other tickets.
{_catalog("recover", version)}

Decisions end the episode.
{_catalog("decide", version)}

- no_intervention: the run's outcome is already correct.
- insufficient_evidence: an observation the task requires is absent from the record and nothing explains the absence (it was withheld, truncated or never attempted). A failed tool call is itself an observation, not missing evidence. List the missing observations as short snake_case codes.
- abstain: the evidence is complete, but no available recovery would make the run correct. Give the reason as a short snake_case code.

{ending}

IDs in args must be IDs that appear in the record{" (the IDs in the examples are placeholders)" if version >= 2 else ""}."""


def user_message(compact_text: str) -> str:
    """The user message: the rendered compact evidence, unchanged."""
    return compact_text


def action_text(reply: str) -> str:
    """The action JSON from a model reply (whitespace and one code fence stripped)."""
    text = reply.strip()
    fenced = _FENCE.match(text)
    return fenced.group(1).strip() if fenced else text


__all__ = [
    "EXAMPLES",
    "PROMPT_VERSION",
    "PROMPT_VERSIONS",
    "action_text",
    "system_prompt",
    "user_message",
]
