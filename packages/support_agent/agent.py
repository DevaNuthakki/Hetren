"""The Milestone 1 support agent definition (the subject, not Hetren).

The agent reads a ticket, looks up the account its customer reference
resolves to, and routes the ticket to the queue whose description matches
the account tier. It has no knowledge of faults, expected outcomes, or
evaluation.

Queue IDs are not hardcoded: ``queue_guide`` renders them from the
environment's queue metadata when the agent is built.

``MODEL_SETTINGS`` sets ``store=False`` so the provider does not retain live
responses. The settings are part of every replay key and run manifest.
``LIVE_TEST_MODEL_SETTINGS`` adds an output-token limit so a spending cap
can bound every live test call; it is used for the Milestone 2 live test
split only, so Milestone 1 replay keys are unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence

from agents import Agent, Model, ModelSettings, Tool

from environments.support.fixtures import SupportEnvironment


AGENT_NAME = "support-agent"

MODEL_SETTINGS = ModelSettings(store=False)
LIVE_TEST_MODEL_SETTINGS = ModelSettings(store=False, max_tokens=300)

BASE_INSTRUCTIONS = """\
You are a customer-support routing agent.

For the ticket named in the request:
1. Call read_ticket to read it. It reports the account_id that the ticket's
   customer reference resolves to.
2. Call lookup_account with that account_id to get the account tier.
3. Call route_ticket to assign the ticket to the queue whose description
   matches the account tier.
Then reply with one sentence stating the ticket and the queue you chose.
If a tool call fails or is denied, stop and say so instead of guessing.

Queues:
"""


def queue_guide(environment: SupportEnvironment) -> str:
    lines = []

    for queue_id in environment.queue_ids():
        queue = environment.get_queue(queue_id)
        lines.append(f"- {queue.queue_id} ({queue.name}): {queue.description}")

    return "\n".join(lines)


def support_instructions(environment: SupportEnvironment) -> str:
    return BASE_INSTRUCTIONS + queue_guide(environment) + "\n"


def task_message(ticket_id: str) -> str:
    return f"Please handle support ticket {ticket_id}."


def build_support_agent(
    *,
    environment: SupportEnvironment,
    tools: Sequence[Tool],
    model: Model | str,
    model_settings: ModelSettings = MODEL_SETTINGS,
) -> Agent:
    if model_settings.store is not False:
        raise ValueError("the support agent requires store=False")

    return Agent(
        name=AGENT_NAME,
        instructions=support_instructions(environment),
        tools=list(tools),
        model=model,
        model_settings=model_settings,
    )


__all__ = [
    "AGENT_NAME",
    "BASE_INSTRUCTIONS",
    "LIVE_TEST_MODEL_SETTINGS",
    "MODEL_SETTINGS",
    "build_support_agent",
    "queue_guide",
    "support_instructions",
    "task_message",
]
