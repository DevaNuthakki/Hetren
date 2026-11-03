"""Extended rules baseline: a deterministic policy over compact evidence.

Written from the training families only (identifier mapping, stale record,
tool errors, misleading text, missing account, and the healthy look-alikes);
it has no rule for the held-out families. Input is the compact evidence a
learned model sees (``compact-evidence-v1``, probes included); output is one
action ``{"action", "verb", "args"}`` per call. It is called again after each
probe until it decides or recovers.

Rules, in order:

1. An agent step that was not observed -> ``insufficient_evidence``.
2. A tool-unavailable failure never followed by a success of the same call:
   probe ``retry``; still failing -> ``abstain``, otherwise ``rerun``.
3. ``lookup_account`` failed with an unknown account -> reroute the ticket
   to the policy's ``unresolved`` queue.
4. The ticket's reference resolves to no account (``read_ticket`` failed
   with an unknown reference, or reported no account) -> ``inspect`` the
   ticket for its reference, then ``find_owners``; one owner ->
   ``set_mapping``, otherwise reroute to ``unresolved``.
5. The account's own customer reference differs from the ticket's ->
   ``find_owners``; an owner other than the resolved account ->
   ``set_mapping`` (no owner: a merged account, continue).
6. Proactive checks: ``inspect routing_policy`` and ``compare_with_source``
   on the account. Working tier differs from source -> ``restore_from_source``;
   the ticket is not in the policy queue for its tier (or was never routed)
   -> ``reroute`` there; otherwise ``no_intervention``.
"""

from __future__ import annotations

from typing import Any


RULES_POLICY_VERSION = 1
UNAVAILABLE = "ToolUnavailableError"


def _action(kind: str, verb: str, **args: Any) -> dict[str, Any]:
    return {"action": kind, "verb": verb, "args": args}


def _probed(compact: dict[str, Any], verb: str, args: dict[str, Any]) -> dict[str, Any] | None:
    for probe in compact["probes"]:
        if probe["tool"] == verb and probe["args"] == args:
            return probe

    return None


def _probe_or(compact, verb, args):
    """``(probe action, None)`` if not probed yet, else ``(None, observation)``."""
    done = _probed(compact, verb, args)

    if done is None:
        return _action("probe", verb, **args), None

    return None, done.get("observation") or {}


def _last(steps, tool, outcome=None):
    matches = [s for s in steps if s["tool"] == tool and (outcome is None or s["outcome"] == outcome)]
    return matches[-1] if matches else None


def rules_policy(compact: dict[str, Any]) -> dict[str, Any]:
    steps = compact["steps"]

    # 1. Unexplained absence.
    absent = [s["tool"] for s in steps if s["outcome"] == "not_observed"]

    if absent:
        return _action("decide", "insufficient_evidence", missing=[f"observation_{tool}" for tool in dict.fromkeys(absent)])

    # 2. Tool unavailable with no later success of the same call.
    for index, step in enumerate(steps):
        if step["outcome"] != "failed" or step.get("error", {}).get("type") != UNAVAILABLE:
            continue

        recovered = any(
            later["tool"] == step["tool"] and later["args"] == step["args"] and later["outcome"] == "succeeded"
            for later in steps[index + 1:]
        )

        if recovered:
            continue

        target = next(iter(step["args"].values()))
        probe, observation = _probe_or(compact, "retry", {"tool": step["tool"], "target": target})

        if probe:
            return probe

        if observation.get("status") == "failed":
            return _action("decide", "abstain", reason="persistent_tool_error")

        return _action("recover", "rerun")

    ticket_step = _last(steps, "read_ticket", "succeeded")
    probe, policy = _probe_or(compact, "inspect", {"entity": "routing_policy"})

    if ticket_step is None:
        failed_read = _last(steps, "read_ticket", "failed")

        if failed_read is None:
            return _action("decide", "abstain", reason="no_ticket_observation")

        ticket_probe, inspected = _probe_or(compact, "inspect", {"entity": "ticket", "id": failed_read["args"]["ticket_id"]})

        if ticket_probe:
            return ticket_probe

        ticket = {**inspected["record"], "account_id": None}
    else:
        ticket = ticket_step["observation"]

    ticket_id, ref = ticket["ticket_id"], ticket["customer_ref"]

    def reroute_to(queue_id):
        if queue_id is None:
            return _action("decide", "abstain", reason="no_policy_queue")

        return _action("recover", "reroute", ticket_id=ticket_id, queue_id=queue_id)

    # 3. The resolved account does not exist.
    failed_lookup = _last(steps, "lookup_account", "failed")
    account_step = _last(steps, "lookup_account", "succeeded")

    if account_step is None and failed_lookup is not None:
        return probe or reroute_to(policy["record"].get("unresolved"))

    # 4. The reference resolves to no account.
    if ticket.get("account_id") is None:
        owners_probe, owners = _probe_or(compact, "find_owners", {"customer_ref": ref})

        if owners_probe:
            return owners_probe

        if len(owners.get("account_ids", [])) == 1:
            return _action("recover", "set_mapping", customer_ref=ref, account_id=owners["account_ids"][0])

        return probe or reroute_to(policy["record"].get("unresolved"))

    if account_step is None:
        return _action("decide", "abstain", reason="no_account_observation")

    account = account_step["observation"]

    # 5. Mapping consistency.
    if account.get("customer_ref") != ref:
        owners_probe, owners = _probe_or(compact, "find_owners", {"customer_ref": ref})

        if owners_probe:
            return owners_probe

        others = [a for a in owners.get("account_ids", []) if a != account["account_id"]]

        if len(others) == 1:
            return _action("recover", "set_mapping", customer_ref=ref, account_id=others[0])

    # 6. Proactive checks.
    if probe:
        return probe

    source_probe, comparison = _probe_or(compact, "compare_with_source", {"entity": "account", "id": account["account_id"]})

    if source_probe:
        return source_probe

    working, source = comparison.get("working", {}), comparison.get("source", {})

    if working.get("tier") != source.get("tier"):
        return _action("recover", "restore_from_source", entity="account", id=account["account_id"])

    expected = policy["record"].get(working.get("tier"))
    routed = _last(steps, "route_ticket", "succeeded")

    if routed is None or routed["observation"]["queue_id"] != expected:
        return reroute_to(expected)

    return _action("decide", "no_intervention")


__all__ = [
    "RULES_POLICY_VERSION",
    "rules_policy",
]
