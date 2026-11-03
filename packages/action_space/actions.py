"""Parse and validate one action against the generic catalog."""

from __future__ import annotations

from dataclasses import dataclass
import json

from jsonschema import Draft202012Validator

from packages.action_gateway import json_object
from packages.contracts import ContractError, canonical_sha256
from packages.action_space.catalog import ACTION_KINDS, verb


@dataclass(frozen=True)
class Action:
    kind: str
    verb: str
    args: dict[str, object]

    def __post_init__(self) -> None:
        if self.kind not in ACTION_KINDS:
            raise ContractError("unknown action kind")

        spec = verb(self.verb)

        if spec.kind != self.kind:
            raise ContractError("verb does not belong to this action kind")

        args = json_object(self.args, "args")

        if not Draft202012Validator(spec.args_schema).is_valid(args):
            raise ContractError("args do not match the verb's schema")

        object.__setattr__(self, "args", args)

    def canonical_payload(self) -> dict[str, object]:
        return {"action": self.kind, "verb": self.verb, "args": self.args}

    @property
    def action_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


def parse_action(value: str | dict[str, object]) -> Action:
    """Parse model output (JSON text or object) into a validated Action."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ContractError("action is not valid JSON") from exc

    if not isinstance(value, dict) or set(value) != {"action", "verb", "args"}:
        raise ContractError("action must have exactly action, verb and args")

    return Action(kind=value["action"], verb=value["verb"], args=value["args"])


__all__ = [
    "Action",
    "parse_action",
]
