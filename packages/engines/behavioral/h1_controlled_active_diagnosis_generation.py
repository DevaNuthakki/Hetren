"""Pure deterministic batch-generation contracts for P09.3 H1.

This module does NOT generate a protected seed.

It does NOT write files.

It does NOT execute an H1 treatment arm.

It accepts an already-supplied 32-byte seed and constructs:

- one treatment-visible public manifest;
- one evaluator-only hidden-truth manifest;
- one public SHA-256 seed commitment.

The public manifest is deliberately independent of the raw seed.
Changing the raw seed can change only evaluator-side assignment and its
commitment, never treatment-visible case construction.

The frozen harness is identified by its exact Git commit ID.

Protected seed creation and artifact persistence belong to a later,
explicitly gated step.
"""

from dataclasses import dataclass
import hashlib
import json
import re

from environments.agent.h1_controlled_active_diagnosis import (
    build_public_case,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    canonical_sha256,
)


_GENERATOR_ID = "h1-controlled-active-diagnosis-generator"
_GENERATOR_VERSION = "1"

_SHA256 = re.compile(
    r"^[0-9a-f]{64}$"
)

_GIT_COMMIT_ID = re.compile(
    r"^[0-9a-f]{40}$"
)

_HYPOTHESIS_KEYS = (
    "H1",
    "H2",
    "H3",
    "H4",
)

_COST_SENSITIVE_DOMINANT = {
    "T1": "H1",
    "T2": "H2",
    "T3": "H3",
    "T4": "H4",
}

_NEUTRAL_TEMPLATES = (
    "N1",
    "N2",
    "N3",
    "N4",
)


def _require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise ContractError(
            f"{name} must be non-empty text"
        )

    return value


def _require_sha256(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA256.fullmatch(value) is None
    ):
        raise ContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _require_git_commit_id(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or _GIT_COMMIT_ID.fullmatch(value) is None
    ):
        raise ContractError(
            f"{name} must be a lowercase 40-hex Git commit ID"
        )

    return value


def _require_raw_seed(
    raw_seed: object,
) -> bytes:
    if (
        not isinstance(raw_seed, bytes)
        or len(raw_seed) != 32
    ):
        raise ContractError(
            "raw_seed must contain exactly 32 bytes"
        )

    return raw_seed


def _canonical_json_bytes(
    payload: object,
) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
        allow_nan=False,
    ).encode(
        "utf-8"
    )


@dataclass(frozen=True)
class H1PublicManifestCase:
    case_id: str
    template_id: str
    singleton_target: str
    problem_sha256: str

    def __post_init__(self) -> None:
        _require_text(
            self.case_id,
            "case_id",
        )

        _require_text(
            self.template_id,
            "template_id",
        )

        _require_text(
            self.singleton_target,
            "singleton_target",
        )

        _require_sha256(
            self.problem_sha256,
            "problem_sha256",
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "template_id": self.template_id,
            "singleton_target": self.singleton_target,
            "problem_sha256": self.problem_sha256,
        }


@dataclass(frozen=True)
class H1PublicManifest:
    batch_id: str
    protocol_sha256: str
    harness_commit_id: str
    generator_id: str
    generator_version: str
    cases: tuple[H1PublicManifestCase, ...]

    def __post_init__(self) -> None:
        _require_text(
            self.batch_id,
            "batch_id",
        )

        _require_sha256(
            self.protocol_sha256,
            "protocol_sha256",
        )

        _require_git_commit_id(
            self.harness_commit_id,
            "harness_commit_id",
        )

        _require_text(
            self.generator_id,
            "generator_id",
        )

        _require_text(
            self.generator_version,
            "generator_version",
        )

        if not isinstance(
            self.cases,
            tuple,
        ):
            raise ContractError(
                "public manifest cases must be a tuple"
            )

        if len(
            self.cases
        ) != 96:
            raise ContractError(
                "public manifest must contain exactly 96 cases"
            )

        case_ids = tuple(
            case.case_id
            for case in self.cases
        )

        if len(
            case_ids
        ) != len(
            set(case_ids)
        ):
            raise ContractError(
                "public manifest case IDs must be unique"
            )

        if case_ids != tuple(
            sorted(case_ids)
        ):
            raise ContractError(
                "public manifest cases must be sorted by case ID"
            )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "record_type": "H1PublicManifest",
            "schema_version": 1,
            "batch_id": self.batch_id,
            "protocol_sha256": self.protocol_sha256,
            "harness_commit_id": (
                self.harness_commit_id
            ),
            "generator_id": self.generator_id,
            "generator_version": self.generator_version,
            "cases": [
                case.canonical_payload()
                for case in self.cases
            ],
        }

    @property
    def manifest_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )

    @property
    def canonical_json_bytes(
        self,
    ) -> bytes:
        return _canonical_json_bytes(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class H1HiddenTruthRecord:
    case_id: str
    hidden_fault_key: str

    def __post_init__(self) -> None:
        _require_text(
            self.case_id,
            "case_id",
        )

        if (
            self.hidden_fault_key
            not in _HYPOTHESIS_KEYS
        ):
            raise ContractError(
                "hidden_fault_key must be H1-H4"
            )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "hidden_fault_key": self.hidden_fault_key,
        }


@dataclass(frozen=True)
class H1HiddenTruthManifest:
    batch_id: str
    protocol_sha256: str
    harness_commit_id: str
    generator_id: str
    generator_version: str
    seed_commitment_sha256: str
    assignments: tuple[H1HiddenTruthRecord, ...]

    def __post_init__(self) -> None:
        _require_text(
            self.batch_id,
            "batch_id",
        )

        _require_sha256(
            self.protocol_sha256,
            "protocol_sha256",
        )

        _require_git_commit_id(
            self.harness_commit_id,
            "harness_commit_id",
        )

        _require_text(
            self.generator_id,
            "generator_id",
        )

        _require_text(
            self.generator_version,
            "generator_version",
        )

        _require_sha256(
            self.seed_commitment_sha256,
            "seed_commitment_sha256",
        )

        if not isinstance(
            self.assignments,
            tuple,
        ):
            raise ContractError(
                "hidden assignments must be a tuple"
            )

        if len(
            self.assignments
        ) != 96:
            raise ContractError(
                "hidden manifest must contain exactly 96 assignments"
            )

        case_ids = tuple(
            record.case_id
            for record in self.assignments
        )

        if len(
            case_ids
        ) != len(
            set(case_ids)
        ):
            raise ContractError(
                "hidden assignment case IDs must be unique"
            )

        if case_ids != tuple(
            sorted(case_ids)
        ):
            raise ContractError(
                "hidden assignments must be sorted by case ID"
            )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "record_type": "H1HiddenTruthManifest",
            "schema_version": 1,
            "batch_id": self.batch_id,
            "protocol_sha256": self.protocol_sha256,
            "harness_commit_id": (
                self.harness_commit_id
            ),
            "generator_id": self.generator_id,
            "generator_version": self.generator_version,
            "seed_commitment_sha256": (
                self.seed_commitment_sha256
            ),
            "assignments": [
                record.canonical_payload()
                for record in self.assignments
            ],
        }

    @property
    def manifest_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )

    @property
    def canonical_json_bytes(
        self,
    ) -> bytes:
        return _canonical_json_bytes(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class H1SeedCommitment:
    batch_id: str
    protocol_sha256: str
    harness_commit_id: str
    generator_id: str
    generator_version: str
    seed_sha256: str

    def __post_init__(self) -> None:
        _require_text(
            self.batch_id,
            "batch_id",
        )

        _require_sha256(
            self.protocol_sha256,
            "protocol_sha256",
        )

        _require_git_commit_id(
            self.harness_commit_id,
            "harness_commit_id",
        )

        _require_text(
            self.generator_id,
            "generator_id",
        )

        _require_text(
            self.generator_version,
            "generator_version",
        )

        _require_sha256(
            self.seed_sha256,
            "seed_sha256",
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "record_type": "H1SeedCommitment",
            "schema_version": 1,
            "batch_id": self.batch_id,
            "protocol_sha256": self.protocol_sha256,
            "harness_commit_id": (
                self.harness_commit_id
            ),
            "generator_id": self.generator_id,
            "generator_version": self.generator_version,
            "seed_sha256": self.seed_sha256,
        }

    @property
    def commitment_record_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )

    @property
    def canonical_json_bytes(
        self,
    ) -> bytes:
        return _canonical_json_bytes(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class H1GeneratedBatch:
    public_manifest: H1PublicManifest
    hidden_truth_manifest: H1HiddenTruthManifest
    seed_commitment: H1SeedCommitment

    def __post_init__(self) -> None:
        if (
            self.public_manifest.batch_id
            != self.hidden_truth_manifest.batch_id
            or self.public_manifest.batch_id
            != self.seed_commitment.batch_id
        ):
            raise ContractError(
                "generated batch IDs do not match"
            )

        if (
            self.public_manifest.protocol_sha256
            != self.hidden_truth_manifest.protocol_sha256
            or self.public_manifest.protocol_sha256
            != self.seed_commitment.protocol_sha256
        ):
            raise ContractError(
                "generated protocol identities do not match"
            )

        if (
            self.public_manifest.harness_commit_id
            != self.hidden_truth_manifest.harness_commit_id
            or self.public_manifest.harness_commit_id
            != self.seed_commitment.harness_commit_id
        ):
            raise ContractError(
                "generated harness commit identities do not match"
            )

        public_case_ids = tuple(
            case.case_id
            for case in self.public_manifest.cases
        )

        hidden_case_ids = tuple(
            record.case_id
            for record
            in self.hidden_truth_manifest.assignments
        )

        if public_case_ids != hidden_case_ids:
            raise ContractError(
                "public and hidden manifest case IDs do not match"
            )

        if (
            self.hidden_truth_manifest.seed_commitment_sha256
            != self.seed_commitment.seed_sha256
        ):
            raise ContractError(
                "hidden manifest seed commitment does not match "
                "public commitment"
            )


def _public_slot_specs(
) -> tuple[tuple[str, str], ...]:
    specs = []

    for template_id in (
        "T1",
        "T2",
        "T3",
        "T4",
    ):
        for index in range(
            1,
            21,
        ):
            specs.append(
                (
                    f"h1-{template_id.lower()}-{index:02d}",
                    template_id,
                )
            )

    for template_id in _NEUTRAL_TEMPLATES:
        for index in range(
            1,
            5,
        ):
            specs.append(
                (
                    f"h1-{template_id.lower()}-{index:02d}",
                    template_id,
                )
            )

    return tuple(
        sorted(specs)
    )


def _build_public_manifest(
    *,
    batch_id: str,
    protocol_sha256: str,
    harness_commit_id: str,
) -> H1PublicManifest:
    cases = []

    for case_id, template_id in _public_slot_specs():
        public_case = build_public_case(
            case_id=case_id,
            template_id=template_id,
        )

        cases.append(
            H1PublicManifestCase(
                case_id=case_id,
                template_id=template_id,
                singleton_target=public_case.singleton_target,
                problem_sha256=public_case.problem.problem_sha256,
            )
        )

    return H1PublicManifest(
        batch_id=batch_id,
        protocol_sha256=protocol_sha256,
        harness_commit_id=harness_commit_id,
        generator_id=_GENERATOR_ID,
        generator_version=_GENERATOR_VERSION,
        cases=tuple(
            sorted(
                cases,
                key=lambda case: case.case_id,
            )
        ),
    )


def _fault_multiset(
    template_id: str,
) -> tuple[str, ...]:
    if template_id in _COST_SENSITIVE_DOMINANT:
        dominant = _COST_SENSITIVE_DOMINANT[
            template_id
        ]

        values = [
            dominant
        ] * 14

        for hypothesis_key in _HYPOTHESIS_KEYS:
            if hypothesis_key == dominant:
                continue

            values.extend(
                [
                    hypothesis_key,
                ]
                * 2
            )

        return tuple(
            values
        )

    if template_id in _NEUTRAL_TEMPLATES:
        return _HYPOTHESIS_KEYS

    raise ContractError(
        f"unknown generation template: {template_id}"
    )


def _assignment_digest(
    *,
    raw_seed: bytes,
    batch_id: str,
    protocol_sha256: str,
    harness_commit_id: str,
    template_id: str,
    token: str,
) -> bytes:
    domain = (
        b"hetren-p09.3-h1-hidden-assignment-v1"
    )

    material = b"\x00".join(
        (
            domain,
            raw_seed,
            batch_id.encode(
                "utf-8"
            ),
            protocol_sha256.encode(
                "ascii"
            ),
            harness_commit_id.encode(
                "ascii"
            ),
            template_id.encode(
                "ascii"
            ),
            token.encode(
                "ascii"
            ),
        )
    )

    return hashlib.sha256(
        material
    ).digest()


def _shuffled_faults(
    *,
    raw_seed: bytes,
    batch_id: str,
    protocol_sha256: str,
    harness_commit_id: str,
    template_id: str,
) -> tuple[str, ...]:
    occurrences = []

    per_fault_count = {
        key: 0
        for key in _HYPOTHESIS_KEYS
    }

    for fault_key in _fault_multiset(
        template_id
    ):
        per_fault_count[
            fault_key
        ] += 1

        token = (
            fault_key
            + "#"
            + f"{per_fault_count[fault_key]:02d}"
        )

        occurrences.append(
            (
                fault_key,
                token,
            )
        )

    ranked = sorted(
        occurrences,
        key=lambda item: (
            _assignment_digest(
                raw_seed=raw_seed,
                batch_id=batch_id,
                protocol_sha256=protocol_sha256,
                harness_commit_id=harness_commit_id,
                template_id=template_id,
                token=item[1],
            ),
            item[1],
        ),
    )

    return tuple(
        fault_key
        for fault_key, _ in ranked
    )


def _build_hidden_truth_manifest(
    *,
    raw_seed: bytes,
    batch_id: str,
    protocol_sha256: str,
    harness_commit_id: str,
    seed_commitment_sha256: str,
    public_manifest: H1PublicManifest,
) -> H1HiddenTruthManifest:
    assignments = []

    for template_id in (
        "T1",
        "T2",
        "T3",
        "T4",
        "N1",
        "N2",
        "N3",
        "N4",
    ):
        public_cases = tuple(
            case
            for case in public_manifest.cases
            if case.template_id == template_id
        )

        shuffled_faults = _shuffled_faults(
            raw_seed=raw_seed,
            batch_id=batch_id,
            protocol_sha256=protocol_sha256,
            harness_commit_id=harness_commit_id,
            template_id=template_id,
        )

        if len(
            public_cases
        ) != len(
            shuffled_faults
        ):
            raise ContractError(
                "template slot count does not match hidden assignment count"
            )

        assignments.extend(
            H1HiddenTruthRecord(
                case_id=case.case_id,
                hidden_fault_key=fault_key,
            )
            for case, fault_key in zip(
                public_cases,
                shuffled_faults,
                strict=True,
            )
        )

    return H1HiddenTruthManifest(
        batch_id=batch_id,
        protocol_sha256=protocol_sha256,
        harness_commit_id=harness_commit_id,
        generator_id=_GENERATOR_ID,
        generator_version=_GENERATOR_VERSION,
        seed_commitment_sha256=seed_commitment_sha256,
        assignments=tuple(
            sorted(
                assignments,
                key=lambda record: record.case_id,
            )
        ),
    )


def build_h1_batch_manifests(
    *,
    raw_seed: bytes,
    batch_id: str,
    protocol_sha256: str,
    harness_commit_id: str,
) -> H1GeneratedBatch:
    """Build separated manifests from caller-supplied seed bytes.

    This function has no file-system side effects.

    It never creates a seed.

    It is suitable for development/isolation tests before any protected
    generation command exists.
    """

    raw_seed = _require_raw_seed(
        raw_seed
    )

    batch_id = _require_text(
        batch_id,
        "batch_id",
    )

    protocol_sha256 = _require_sha256(
        protocol_sha256,
        "protocol_sha256",
    )

    harness_commit_id = _require_git_commit_id(
        harness_commit_id,
        "harness_commit_id",
    )

    seed_sha256 = hashlib.sha256(
        raw_seed
    ).hexdigest()

    seed_commitment = H1SeedCommitment(
        batch_id=batch_id,
        protocol_sha256=protocol_sha256,
        harness_commit_id=harness_commit_id,
        generator_id=_GENERATOR_ID,
        generator_version=_GENERATOR_VERSION,
        seed_sha256=seed_sha256,
    )

    public_manifest = _build_public_manifest(
        batch_id=batch_id,
        protocol_sha256=protocol_sha256,
        harness_commit_id=harness_commit_id,
    )

    hidden_truth_manifest = (
        _build_hidden_truth_manifest(
            raw_seed=raw_seed,
            batch_id=batch_id,
            protocol_sha256=protocol_sha256,
            harness_commit_id=harness_commit_id,
            seed_commitment_sha256=seed_sha256,
            public_manifest=public_manifest,
        )
    )

    return H1GeneratedBatch(
        public_manifest=public_manifest,
        hidden_truth_manifest=hidden_truth_manifest,
        seed_commitment=seed_commitment,
    )


__all__ = [
    "H1GeneratedBatch",
    "H1HiddenTruthManifest",
    "H1HiddenTruthRecord",
    "H1PublicManifest",
    "H1PublicManifestCase",
    "H1SeedCommitment",
    "build_h1_batch_manifests",
]
