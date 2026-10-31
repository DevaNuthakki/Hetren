"""Evaluator-side run registration.

The harness reports each run through the verifier's ``register_run``; the
verifier stores it here. A registration binds a neutral run ID to the example
it belongs to and the fault payload the harness actually injected. This is
the only place that mapping exists.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from packages.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.support_evaluator.catalog import (
    ExampleSpec,
    example,
    fault,
)


NEUTRAL_RUN_ID = re.compile(r"run-[0-9]{4}")


@dataclass(frozen=True)
class RunRegistration:
    run_id: str
    example_name: str
    fault_id: str | None
    fault_payload: dict[str, object] | None

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "SupportRunRegistration",
            "schema_version": 1,
            "run_id": self.run_id,
            "example_name": self.example_name,
            "fault_id": self.fault_id,
            "fault_payload": self.fault_payload,
        }

    @property
    def registration_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())

    @property
    def spec(self) -> ExampleSpec:
        return example(self.example_name)


class RunRegistry:
    def __init__(self) -> None:
        self._registrations: dict[str, RunRegistration] = {}

    def register(
        self,
        *,
        run_id: str,
        example_name: str,
        fault_payload: dict[str, object] | None,
    ) -> RunRegistration:
        if (
            not isinstance(run_id, str)
            or NEUTRAL_RUN_ID.fullmatch(run_id) is None
        ):
            raise ContractError("run_id must be a neutral run-NNNN identifier")

        if run_id in self._registrations:
            raise ContractError("run_id is already registered")

        spec = example(example_name)

        if spec.fault_id is None:
            if fault_payload is not None:
                raise ContractError("example expects no injected fault")
        else:
            expected = fault(spec.fault_id).fault_payload()

            if fault_payload != expected:
                raise ContractError(
                    "injected fault does not match the example definition"
                )

        registration = RunRegistration(
            run_id=run_id,
            example_name=example_name,
            fault_id=spec.fault_id,
            fault_payload=None if fault_payload is None else dict(fault_payload),
        )
        self._registrations[run_id] = registration
        return registration

    def lookup(self, run_id: str) -> RunRegistration:
        try:
            return self._registrations[run_id]
        except KeyError:
            raise ContractError("run_id is not registered") from None

    def run_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))


__all__ = [
    "NEUTRAL_RUN_ID",
    "RunRegistration",
    "RunRegistry",
]
