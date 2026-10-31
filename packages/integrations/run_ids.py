"""Neutral sequential run identifiers.

Run IDs are visible to Hetren, so they carry no meaning: ``run-0001``,
``run-0002``, ... in allocation order. Which example a run belongs to is
recorded only on the evaluator side.
"""

from __future__ import annotations

from packages.contracts import ContractError


class RunIdAllocator:
    def __init__(self, start: int = 1) -> None:
        if isinstance(start, bool) or not isinstance(start, int) or start < 1:
            raise ContractError("start must be a positive integer")

        self._next = start

    def allocate(self) -> str:
        if self._next > 9999:
            raise ContractError("run ID space exhausted")

        run_id = f"run-{self._next:04d}"
        self._next += 1
        return run_id


__all__ = [
    "RunIdAllocator",
]
