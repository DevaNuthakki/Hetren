"""The shared model prompt: versions stay reproducible, version 2 is a format
fix only, and the prompt never names a fault family or agent behaviour."""

import hashlib
import json
import re

import pytest

from packages.action_space import VERBS, parse_action
from packages.contracts import ContractError
from packages.hetren_baselines.prompt import EXAMPLES, PROMPT_VERSION, PROMPT_VERSIONS, system_prompt
from packages.support_agent import BEHAVIOURS
from packages.support_evaluator.audit import FAULT_MARKERS
from packages.support_evaluator.cases import CASE_KINDS


# Recorded runs name the prompt version; the text of every version is pinned.
PINNED = {
    (1, 1): "a6aa572938b53fbec4be5d846898849a35c1afccdd71fc8d083edd720badf730",
    (1, 2): "72b1d27fadbcbcbbb184ae9f2a645a232e14cdf9e45a945a751b81d59523a336",
    (2, 1): "43324de829e9c353309b0bf0aa643510d2994af2ecc8c88d77c4a80fc7f288f6",
    (2, 2): "5337c091e1f293a71bb827cde86da032e2aa40db6a090fdd6926f3f305d236c4",
}


@pytest.mark.parametrize("version, max_recoveries", sorted(PINNED))
def test_every_prompt_version_is_pinned(version, max_recoveries):
    text = system_prompt(max_recoveries, version)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == PINNED[(version, max_recoveries)]


def test_current_version_is_two_and_unknown_versions_fail():
    assert PROMPT_VERSION == 2 and PROMPT_VERSIONS == (1, 2)
    assert system_prompt(1) == system_prompt(1, 2)

    with pytest.raises(ValueError):
        system_prompt(1, 3)


@pytest.mark.parametrize("max_recoveries", [1, 2])
def test_version_two_only_adds_format_guidance(max_recoveries):
    v1 = system_prompt(max_recoveries, 1)
    v2 = system_prompt(max_recoveries, 2)

    # Undo the four format additions; what remains must be version 1 exactly.
    stripped = re.sub(r' \(action "(probe|recover|decide)"\)', "", v2)
    stripped = re.sub(r"\nExample: \{.*\}", "", stripped)
    stripped = stripped.replace(" (the IDs in the examples are placeholders)", "")
    stripped = re.sub(
        r'Reply with exactly one action as a single JSON object and nothing else\. "action" is .*? its arguments:',
        "Reply with exactly one action as a single JSON object and nothing else:", stripped,
    )
    assert stripped == v1


def test_every_verb_is_listed_with_its_action_type_and_every_example_parses():
    text = system_prompt(2, 2)

    for name, spec in VERBS.items():
        assert f'- {name} (action "{spec.kind}"):' in text

    for kind, example in EXAMPLES.items():
        action = parse_action(example)
        assert action.kind == kind and f"Example: {json.dumps(example)}" in text

    assert '"action" is the action type' in text and "never the verb" in text


@pytest.mark.parametrize("version", PROMPT_VERSIONS)
def test_prompt_names_no_fault_family_or_behaviour(version):
    text = " ".join(system_prompt(r, version) for r in (1, 2)).lower()

    # "retry" is both a behaviour and a generic probe verb; verbs are allowed.
    for word in (set(CASE_KINDS) | set(BEHAVIOURS) | set(FAULT_MARKERS)) - set(VERBS):
        assert word.lower() not in text, word


def test_parsing_stays_strict():
    # The reply gpt-4.1 gave in 46% of version 1 calls is still invalid.
    with pytest.raises(ContractError, match="unknown action kind"):
        parse_action({"action": "insufficient_evidence", "verb": "insufficient_evidence", "args": {"missing": ["x"]}})
