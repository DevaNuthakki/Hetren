"""Fault injection for the synthetic support environment.

Only the trusted harness calls ``inject_fault``. Injection mutates the
environment's customer directory and leaves no marker behind: the
environment does not remember that a fault is active, and tool observations
never name it. The harness reports the active fault to the verifier, which
keeps it on the evaluator side.

``SupportEnvironment.reset()`` removes any injected fault.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts import ContractError

from environments.support.fixtures import SupportEnvironment


@dataclass(frozen=True)
class IdentifierMappingSwap:
    """Swap the accounts two customer references resolve to."""

    customer_ref_a: str
    customer_ref_b: str

    def __post_init__(self) -> None:
        if self.customer_ref_a == self.customer_ref_b:
            raise ContractError(
                "identifier mapping swap needs two distinct references"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "fault_type": "identifier_mapping_swap",
            "customer_ref_a": self.customer_ref_a,
            "customer_ref_b": self.customer_ref_b,
        }


SupportFault = IdentifierMappingSwap


def inject_fault(
    environment: SupportEnvironment,
    fault: SupportFault,
) -> None:
    if not isinstance(environment, SupportEnvironment):
        raise ContractError(
            "environment must be a SupportEnvironment"
        )

    if not isinstance(fault, IdentifierMappingSwap):
        raise ContractError(
            "unsupported support fault"
        )

    account_a = environment.resolve_customer(fault.customer_ref_a)
    account_b = environment.resolve_customer(fault.customer_ref_b)

    if account_a == account_b:
        raise ContractError(
            "references already resolve to the same account"
        )

    environment.set_directory_entry(fault.customer_ref_a, account_b)
    environment.set_directory_entry(fault.customer_ref_b, account_a)


__all__ = [
    "IdentifierMappingSwap",
    "SupportFault",
    "inject_fault",
]
