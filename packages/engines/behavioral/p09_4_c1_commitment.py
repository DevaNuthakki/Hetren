"""Pure development candidate for a P09.4 C1 seed commitment.

This module neither generates a seed nor persists protected state.
The candidate record is not a frozen protected artifact schema.
Real K5D C1 seed creation requires separate authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from packages.core.hetren_diagnosis.contracts import ContractError


_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def _require_hex(
    value: str,
    pattern: re.Pattern[str],
    label: str,
) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ContractError(f"{label} has an invalid fingerprint")


@dataclass(frozen=True)
class P094DevelopmentC1Commitment:
    protocol_sha256: str
    source_commit: str
    seed_sha256: str

    def __post_init__(self) -> None:
        _require_hex(
            self.protocol_sha256,
            _HEX_64,
            "protocol_sha256",
        )
        _require_hex(
            self.source_commit,
            _HEX_40,
            "source_commit",
        )
        _require_hex(
            self.seed_sha256,
            _HEX_64,
            "seed_sha256",
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "P094DevelopmentC1Commitment",
            "schema_version": 1,
            "development_only": True,
            "protocol_sha256": self.protocol_sha256,
            "source_commit": self.source_commit,
            "seed_sha256": self.seed_sha256,
        }

    def canonical_json_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def record_sha256(self) -> str:
        return hashlib.sha256(
            self.canonical_json_bytes()
        ).hexdigest()


def build_development_c1_commitment(
    *,
    raw_seed: bytes,
    protocol_sha256: str,
    source_commit: str,
    generation_seed_sha256: str | None = None,
) -> P094DevelopmentC1Commitment:
    """Commit a caller-provided synthetic seed without persisting it."""

    if type(raw_seed) is not bytes or len(raw_seed) != 32:
        raise ContractError(
            "C1 raw seed must be exactly 32 bytes"
        )

    if generation_seed_sha256 is not None:
        _require_hex(
            generation_seed_sha256,
            _HEX_64,
            "generation_seed_sha256",
        )

    seed_sha256 = hashlib.sha256(raw_seed).hexdigest()

    if seed_sha256 == generation_seed_sha256:
        raise ContractError(
            "C1 and generation seed commitments must differ"
        )

    return P094DevelopmentC1Commitment(
        protocol_sha256=protocol_sha256,
        source_commit=source_commit,
        seed_sha256=seed_sha256,
    )
