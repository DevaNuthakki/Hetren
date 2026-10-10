"""Pure development-qualified generation contracts for P09.4 protected-v1.

This module does not create randomness.

It does not write protected artifacts.

It does not materialize protected replay baselines.

It accepts caller-supplied 32-byte seed material and produces:

- deterministic public protected-slot specifications;
- evaluator-only balanced hidden assignments;
- and a public SHA-256 seed commitment.

Public slot construction is independent of hidden seed material.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    canonical_sha256,
)


STUDY_VERSION = "p09.4-protected-v1"

GENERATOR_ID = "p09.4-protected-generation-plan"

GENERATOR_VERSION = "1"

TEMPLATE_IDS = (
    "V1",
    "V2",
    "V3",
    "V4",
)

HIDDEN_STRATA = (
    "tool_selection",
    "parameter_transformation",
    "sequencing_orchestration",
    "state_context",
    "environment_interaction",
    "out_of_rfs_report_assembly",
)

EXPECTED_HYPOTHESIS_BY_STRATUM = {
    "tool_selection":
        "tool_selection_fault",

    "parameter_transformation":
        "parameter_transformation_fault",

    "sequencing_orchestration":
        "sequencing_orchestration_fault",

    "state_context":
        "state_context_fault",

    "environment_interaction":
        "environment_interaction_fault",

    "out_of_rfs_report_assembly":
        None,
}

CASES_PER_TEMPLATE = 36

CASES_PER_TEMPLATE_STRATUM = 6

TOTAL_CASES = 144

IN_RFS_CASES = 120

OUT_OF_RFS_CASES = 24


_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_CASE_ID_RE = re.compile(
    r"^p09-4-protected-v1-v[1-4]-[0-9]{3}$"
)


def _require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
    ):
        raise ContractError(
            f"{name} is required"
        )

    return value


def _require_sha256(
    value: object,
    name: str,
) -> str:
    value = _require_text(
        value,
        name,
    )

    if _SHA256_RE.fullmatch(
        value
    ) is None:
        raise ContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _require_commit(
    value: object,
) -> str:
    value = _require_text(
        value,
        "source_commit",
    )

    if _COMMIT_RE.fullmatch(
        value
    ) is None:
        raise ContractError(
            "source_commit must be a 40-character lowercase Git commit"
        )

    return value


def _require_raw_seed(
    raw_seed: object,
) -> bytes:
    if (
        not isinstance(
            raw_seed,
            bytes,
        )
        or len(
            raw_seed
        )
        != 32
    ):
        raise ContractError(
            "raw_seed must contain exactly 32 bytes"
        )

    return raw_seed


def _nuisance_items(
    template_id: str,
    slot_index: int,
) -> tuple[
    tuple[
        str,
        str,
    ],
    ...,
]:
    replicate = f"{slot_index:03d}"

    if template_id == "V1":
        items = (
            (
                "surface",
                "canonical",
            ),
            (
                "replicate",
                replicate,
            ),
        )

    elif template_id == "V2":
        items = (
            (
                "surface",
                "event_order_variation",
            ),
            (
                "event_order_variant",
                f"order-{((slot_index - 1) % 6) + 1}",
            ),
            (
                "replicate",
                replicate,
            ),
        )

    elif template_id == "V3":
        items = (
            (
                "surface",
                "benign_context_noise",
            ),
            (
                "benign_context_tag",
                f"context-{replicate}",
            ),
            (
                "replicate",
                replicate,
            ),
        )

    elif template_id == "V4":
        items = (
            (
                "surface",
                "identifier_value_variation",
            ),
            (
                "identifier_variant",
                f"identifier-{replicate}",
            ),
            (
                "replicate",
                replicate,
            ),
        )

    else:
        raise ContractError(
            "unknown nuisance template"
        )

    return tuple(
        sorted(
            items
        )
    )


@dataclass(
    frozen=True
)
class P094ProtectedPublicSlot:
    case_id: str
    template_id: str
    slot_index: int
    nuisance_items: tuple[
        tuple[
            str,
            str,
        ],
        ...,
    ]
    public_configuration_sha256: str

    def __post_init__(
        self,
    ) -> None:
        _require_text(
            self.case_id,
            "case_id",
        )

        if _CASE_ID_RE.fullmatch(
            self.case_id
        ) is None:
            raise ContractError(
                "case_id does not match protected-v1 public contract"
            )

        if self.template_id not in TEMPLATE_IDS:
            raise ContractError(
                "template_id must be V1-V4"
            )

        if (
            isinstance(
                self.slot_index,
                bool,
            )
            or not isinstance(
                self.slot_index,
                int,
            )
            or not (
                1
                <= self.slot_index
                <= CASES_PER_TEMPLATE
            )
        ):
            raise ContractError(
                "slot_index must be in 1..36"
            )

        if (
            not isinstance(
                self.nuisance_items,
                tuple,
            )
            or not self.nuisance_items
        ):
            raise ContractError(
                "nuisance_items are required"
            )

        if self.nuisance_items != tuple(
            sorted(
                self.nuisance_items
            )
        ):
            raise ContractError(
                "nuisance_items must be key-sorted"
            )

        keys = tuple(
            key
            for (
                key,
                _
            )
            in self.nuisance_items
        )

        if len(
            keys
        ) != len(
            set(
                keys
            )
        ):
            raise ContractError(
                "nuisance item keys must be unique"
            )

        _require_sha256(
            self.public_configuration_sha256,
            "public_configuration_sha256",
        )

        expected = canonical_sha256(
            {
                "study_version":
                    STUDY_VERSION,

                "template_id":
                    self.template_id,

                "slot_index":
                    self.slot_index,

                "nuisance_items":
                    self.nuisance_items,
            }
        )

        if (
            self.public_configuration_sha256
            != expected
        ):
            raise ContractError(
                "public configuration fingerprint mismatch"
            )

    def canonical_payload(
        self,
    ) -> dict[
        str,
        object,
    ]:
        return {
            "case_id":
                self.case_id,

            "template_id":
                self.template_id,

            "slot_index":
                self.slot_index,

            "nuisance_items":
                [
                    [
                        key,
                        value,
                    ]
                    for (
                        key,
                        value,
                    )
                    in self.nuisance_items
                ],

            "public_configuration_sha256":
                self.public_configuration_sha256,
        }


@dataclass(
    frozen=True
)
class P094ProtectedHiddenAssignment:
    case_id: str
    template_id: str
    hidden_stratum: str
    expected_hypothesis_key: str | None
    public_configuration_sha256: str

    def __post_init__(
        self,
    ) -> None:
        _require_text(
            self.case_id,
            "case_id",
        )

        if self.template_id not in TEMPLATE_IDS:
            raise ContractError(
                "template_id must be V1-V4"
            )

        if self.hidden_stratum not in HIDDEN_STRATA:
            raise ContractError(
                "hidden_stratum is not registered"
            )

        expected = (
            EXPECTED_HYPOTHESIS_BY_STRATUM[
                self.hidden_stratum
            ]
        )

        if (
            self.expected_hypothesis_key
            != expected
        ):
            raise ContractError(
                "hidden-stratum hypothesis mapping mismatch"
            )

        _require_sha256(
            self.public_configuration_sha256,
            "public_configuration_sha256",
        )

    @property
    def in_rfs(
        self,
    ) -> bool:
        return (
            self.expected_hypothesis_key
            is not None
        )

    def canonical_payload(
        self,
    ) -> dict[
        str,
        object,
    ]:
        return {
            "case_id":
                self.case_id,

            "template_id":
                self.template_id,

            "hidden_stratum":
                self.hidden_stratum,

            "expected_hypothesis_key":
                self.expected_hypothesis_key,

            "public_configuration_sha256":
                self.public_configuration_sha256,
        }


@dataclass(
    frozen=True
)
class P094GenerationSeedCommitment:
    study_version: str
    protocol_sha256: str
    source_commit: str
    seed_sha256: str

    def __post_init__(
        self,
    ) -> None:
        if self.study_version != STUDY_VERSION:
            raise ContractError(
                "unexpected study version"
            )

        _require_sha256(
            self.protocol_sha256,
            "protocol_sha256",
        )

        _require_commit(
            self.source_commit
        )

        _require_sha256(
            self.seed_sha256,
            "seed_sha256",
        )

    def canonical_payload(
        self,
    ) -> dict[
        str,
        object,
    ]:
        return {
            "record_type":
                "P094GenerationSeedCommitment",

            "schema_version":
                1,

            "study_version":
                self.study_version,

            "protocol_sha256":
                self.protocol_sha256,

            "source_commit":
                self.source_commit,

            "generator_id":
                GENERATOR_ID,

            "generator_version":
                GENERATOR_VERSION,

            "seed_sha256":
                self.seed_sha256,
        }

    @property
    def commitment_record_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


@dataclass(
    frozen=True
)
class P094ProtectedGenerationPlan:
    protocol_sha256: str
    source_commit: str
    public_slots: tuple[
        P094ProtectedPublicSlot,
        ...,
    ]
    hidden_assignments: tuple[
        P094ProtectedHiddenAssignment,
        ...,
    ]
    seed_commitment: P094GenerationSeedCommitment

    def __post_init__(
        self,
    ) -> None:
        _require_sha256(
            self.protocol_sha256,
            "protocol_sha256",
        )

        _require_commit(
            self.source_commit
        )

        if len(
            self.public_slots
        ) != TOTAL_CASES:
            raise ContractError(
                "public generation plan must contain exactly 144 slots"
            )

        if len(
            self.hidden_assignments
        ) != TOTAL_CASES:
            raise ContractError(
                "hidden generation plan must contain exactly 144 assignments"
            )

        public_ids = tuple(
            slot.case_id
            for slot
            in self.public_slots
        )

        hidden_ids = tuple(
            assignment.case_id
            for assignment
            in self.hidden_assignments
        )

        if public_ids != tuple(
            sorted(
                public_ids
            )
        ):
            raise ContractError(
                "public slots must be sorted by case ID"
            )

        if hidden_ids != tuple(
            sorted(
                hidden_ids
            )
        ):
            raise ContractError(
                "hidden assignments must be sorted by case ID"
            )

        if len(
            set(
                public_ids
            )
        ) != TOTAL_CASES:
            raise ContractError(
                "public case IDs must be unique"
            )

        if public_ids != hidden_ids:
            raise ContractError(
                "public and hidden case IDs must match exactly"
            )

        fingerprints = tuple(
            slot.public_configuration_sha256
            for slot
            in self.public_slots
        )

        if len(
            set(
                fingerprints
            )
        ) != TOTAL_CASES:
            raise ContractError(
                "public nuisance configurations must be unique"
            )

        public_by_id = {
            slot.case_id:
                slot
            for slot
            in self.public_slots
        }

        for assignment in self.hidden_assignments:
            public = public_by_id[
                assignment.case_id
            ]

            if (
                assignment.template_id
                != public.template_id
            ):
                raise ContractError(
                    "public/hidden template identity mismatch"
                )

            if (
                assignment.public_configuration_sha256
                != public.public_configuration_sha256
            ):
                raise ContractError(
                    "public/hidden configuration fingerprint mismatch"
                )

        template_counts = {
            template_id:
                sum(
                    slot.template_id
                    == template_id
                    for slot
                    in self.public_slots
                )
            for template_id
            in TEMPLATE_IDS
        }

        if any(
            count != CASES_PER_TEMPLATE
            for count
            in template_counts.values()
        ):
            raise ContractError(
                "every public template must contain exactly 36 slots"
            )

        stratum_counts = {
            hidden_stratum:
                sum(
                    assignment.hidden_stratum
                    == hidden_stratum
                    for assignment
                    in self.hidden_assignments
                )
            for hidden_stratum
            in HIDDEN_STRATA
        }

        if any(
            count != 24
            for count
            in stratum_counts.values()
        ):
            raise ContractError(
                "every hidden stratum must contain exactly 24 cases"
            )

        for template_id in TEMPLATE_IDS:
            for hidden_stratum in HIDDEN_STRATA:
                count = sum(
                    (
                        assignment.template_id
                        == template_id
                        and assignment.hidden_stratum
                        == hidden_stratum
                    )
                    for assignment
                    in self.hidden_assignments
                )

                if (
                    count
                    != CASES_PER_TEMPLATE_STRATUM
                ):
                    raise ContractError(
                        "every template/hidden-stratum cell must contain exactly six cases"
                    )

        if (
            self.seed_commitment.protocol_sha256
            != self.protocol_sha256
            or self.seed_commitment.source_commit
            != self.source_commit
        ):
            raise ContractError(
                "generation-plan lineage mismatch"
            )

    @property
    def public_plan_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            {
                "record_type":
                    "P094ProtectedPublicSlotPlan",

                "schema_version":
                    1,

                "study_version":
                    STUDY_VERSION,

                "protocol_sha256":
                    self.protocol_sha256,

                "source_commit":
                    self.source_commit,

                "generator_id":
                    GENERATOR_ID,

                "generator_version":
                    GENERATOR_VERSION,

                "slots":
                    [
                        slot.canonical_payload()
                        for slot
                        in self.public_slots
                    ],
            }
        )

    @property
    def hidden_assignment_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            {
                "record_type":
                    "P094ProtectedHiddenAssignmentPlan",

                "schema_version":
                    1,

                "study_version":
                    STUDY_VERSION,

                "protocol_sha256":
                    self.protocol_sha256,

                "source_commit":
                    self.source_commit,

                "seed_commitment_sha256":
                    self.seed_commitment.seed_sha256,

                "assignments":
                    [
                        assignment.canonical_payload()
                        for assignment
                        in self.hidden_assignments
                    ],
            }
        )


def _public_slots(
) -> tuple[
    P094ProtectedPublicSlot,
    ...,
]:
    slots = []

    for template_id in TEMPLATE_IDS:
        for slot_index in range(
            1,
            CASES_PER_TEMPLATE + 1,
        ):
            case_id = (
                f"p09-4-protected-v1-"
                f"{template_id.lower()}-"
                f"{slot_index:03d}"
            )

            nuisance_items = (
                _nuisance_items(
                    template_id,
                    slot_index,
                )
            )

            fingerprint = (
                canonical_sha256(
                    {
                        "study_version":
                            STUDY_VERSION,

                        "template_id":
                            template_id,

                        "slot_index":
                            slot_index,

                        "nuisance_items":
                            nuisance_items,
                    }
                )
            )

            slots.append(
                P094ProtectedPublicSlot(
                    case_id=case_id,
                    template_id=template_id,
                    slot_index=slot_index,
                    nuisance_items=(
                        nuisance_items
                    ),
                    public_configuration_sha256=(
                        fingerprint
                    ),
                )
            )

    return tuple(
        sorted(
            slots,
            key=lambda slot:
                slot.case_id,
        )
    )


def _assignment_digest(
    *,
    raw_seed: bytes,
    protocol_sha256: str,
    source_commit: str,
    template_id: str,
    token: str,
) -> bytes:
    material = b"\x00".join(
        (
            b"hetren-p09.4-protected-hidden-assignment-v1",
            raw_seed,
            protocol_sha256.encode(
                "utf-8"
            ),
            source_commit.encode(
                "utf-8"
            ),
            template_id.encode(
                "utf-8"
            ),
            token.encode(
                "utf-8"
            ),
        )
    )

    return hashlib.sha256(
        material
    ).digest()


def _shuffled_strata(
    *,
    raw_seed: bytes,
    protocol_sha256: str,
    source_commit: str,
    template_id: str,
) -> tuple[
    str,
    ...,
]:
    occurrences = tuple(
        (
            hidden_stratum,
            occurrence,
        )
        for hidden_stratum
        in HIDDEN_STRATA
        for occurrence
        in range(
            CASES_PER_TEMPLATE_STRATUM
        )
    )

    ranked = sorted(
        occurrences,
        key=lambda item: (
            _assignment_digest(
                raw_seed=raw_seed,
                protocol_sha256=(
                    protocol_sha256
                ),
                source_commit=source_commit,
                template_id=template_id,
                token=(
                    item[
                        0
                    ]
                    + ":"
                    + str(
                        item[
                            1
                        ]
                    )
                ),
            ),
            item[
                0
            ],
            item[
                1
            ],
        ),
    )

    return tuple(
        hidden_stratum
        for (
            hidden_stratum,
            _
        )
        in ranked
    )


def build_development_generation_plan(
    *,
    raw_seed: bytes,
    protocol_sha256: str,
    source_commit: str,
) -> P094ProtectedGenerationPlan:
    raw_seed = _require_raw_seed(
        raw_seed
    )

    protocol_sha256 = _require_sha256(
        protocol_sha256,
        "protocol_sha256",
    )

    source_commit = _require_commit(
        source_commit
    )

    public_slots = _public_slots()

    assignments = []

    for template_id in TEMPLATE_IDS:
        template_slots = tuple(
            slot
            for slot
            in public_slots
            if slot.template_id
            == template_id
        )

        hidden_strata = (
            _shuffled_strata(
                raw_seed=raw_seed,
                protocol_sha256=(
                    protocol_sha256
                ),
                source_commit=source_commit,
                template_id=template_id,
            )
        )

        if (
            len(
                template_slots
            )
            != len(
                hidden_strata
            )
        ):
            raise ContractError(
                "template slot and assignment counts differ"
            )

        assignments.extend(
            P094ProtectedHiddenAssignment(
                case_id=slot.case_id,
                template_id=(
                    slot.template_id
                ),
                hidden_stratum=(
                    hidden_stratum
                ),
                expected_hypothesis_key=(
                    EXPECTED_HYPOTHESIS_BY_STRATUM[
                        hidden_stratum
                    ]
                ),
                public_configuration_sha256=(
                    slot.public_configuration_sha256
                ),
            )
            for (
                slot,
                hidden_stratum,
            )
            in zip(
                template_slots,
                hidden_strata,
            )
        )

    commitment = (
        P094GenerationSeedCommitment(
            study_version=(
                STUDY_VERSION
            ),
            protocol_sha256=(
                protocol_sha256
            ),
            source_commit=source_commit,
            seed_sha256=(
                hashlib.sha256(
                    raw_seed
                ).hexdigest()
            ),
        )
    )

    return P094ProtectedGenerationPlan(
        protocol_sha256=(
            protocol_sha256
        ),
        source_commit=source_commit,
        public_slots=public_slots,
        hidden_assignments=tuple(
            sorted(
                assignments,
                key=lambda assignment:
                    assignment.case_id,
            )
        ),
        seed_commitment=commitment,
    )


__all__ = [
    "CASES_PER_TEMPLATE",
    "CASES_PER_TEMPLATE_STRATUM",
    "EXPECTED_HYPOTHESIS_BY_STRATUM",
    "GENERATOR_ID",
    "GENERATOR_VERSION",
    "HIDDEN_STRATA",
    "IN_RFS_CASES",
    "OUT_OF_RFS_CASES",
    "P094GenerationSeedCommitment",
    "P094ProtectedGenerationPlan",
    "P094ProtectedHiddenAssignment",
    "P094ProtectedPublicSlot",
    "STUDY_VERSION",
    "TEMPLATE_IDS",
    "TOTAL_CASES",
    "build_development_generation_plan",
]
