from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable

from hvee.core.capability_registry import (
    ModelAccessTier,
)


CAPABILITY_TRANSFER_QUALIFICATION_SCHEMA_VERSION = "1.0.0"


class CapabilityTransferQualificationError(
    ValueError
):
    pass


class TransferGateKind(
    str,
    Enum,
):
    BINDING_IDENTITY = "binding_identity"
    EVIDENCE_INTEGRITY = "evidence_integrity"
    CAPABILITY_DISCOVERY = "capability_discovery"
    BEHAVIORAL_BASELINE = "behavioral_baseline"
    REPLAYABILITY = "replayability"
    EGRESS_POLICY = "egress_policy"
    NON_PERTURBATION = "non_perturbation"
    REVERSIBILITY = "reversibility"
    STATE_RESTORATION = "state_restoration"
    RESOURCE_BUDGET = "resource_budget"


class TransferGateStatus(
    str,
    Enum,
):
    PASS = "pass"
    FAIL = "fail"
    NOT_RUN = "not_run"
    NOT_APPLICABLE = "not_applicable"


class TransferCapabilityDisposition(
    str,
    Enum,
):
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


class TransferPackVerdict(
    str,
    Enum,
):
    PASS = "pass"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAIL = "fail"


_ACCESS_RANK = {
    ModelAccessTier.CLOSED_API: 1,
    ModelAccessTier.PRIVATE_INFERENCE: 2,
    ModelAccessTier.AUTHORIZED_INTERNALS: 3,
}


STANDARD_BEHAVIORAL_REQUIRED_GATES = (
    "binding_identity",
    "evidence_integrity",
    "capability_discovery",
    "behavioral_baseline",
    "replayability",
    "egress_policy",
)


STANDARD_INTERNAL_CAPTURE_REQUIRED_GATES = (
    *STANDARD_BEHAVIORAL_REQUIRED_GATES,
    "non_perturbation",
)


STANDARD_REVERSIBLE_INTERVENTION_REQUIRED_GATES = (
    *STANDARD_BEHAVIORAL_REQUIRED_GATES,
    "reversibility",
    "state_restoration",
)


def _require_nonempty(
    value: object,
    *,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise CapabilityTransferQualificationError(
            f"{field_name} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise CapabilityTransferQualificationError(
            f"{field_name} must not be empty"
        )

    return normalized


def _require_sha256(
    value: object,
    *,
    field_name: str,
) -> str:
    normalized = _require_nonempty(
        value,
        field_name=field_name,
    ).lower()

    if re.fullmatch(
        r"[0-9a-f]{64}",
        normalized,
    ) is None:
        raise CapabilityTransferQualificationError(
            f"{field_name} must be a lowercase-compatible SHA256"
        )

    return normalized


def _require_unique_strings(
    values: Iterable[str],
    *,
    field_name: str,
) -> tuple[str, ...]:
    normalized = tuple(
        _require_nonempty(
            value,
            field_name=field_name,
        )
        for value in values
    )

    if len(
        normalized
    ) != len(
        set(
            normalized
        )
    ):
        raise CapabilityTransferQualificationError(
            f"{field_name} must contain unique values"
        )

    return normalized


def _require_sha256_tuple(
    values: Iterable[str],
    *,
    field_name: str,
) -> tuple[str, ...]:
    normalized = tuple(
        _require_sha256(
            value,
            field_name=field_name,
        )
        for value in values
    )

    if len(
        normalized
    ) != len(
        set(
            normalized
        )
    ):
        raise CapabilityTransferQualificationError(
            f"{field_name} must contain unique SHA256 values"
        )

    return normalized


def _primitive(
    value: Any,
) -> Any:
    if isinstance(
        value,
        Enum,
    ):
        return value.value

    if hasattr(
        value,
        "__dataclass_fields__",
    ):
        return {
            key: _primitive(
                item
            )
            for key, item in asdict(
                value
            ).items()
        }

    if isinstance(
        value,
        tuple,
    ):
        return [
            _primitive(
                item
            )
            for item in value
        ]

    if isinstance(
        value,
        list,
    ):
        return [
            _primitive(
                item
            )
            for item in value
        ]

    if isinstance(
        value,
        dict,
    ):
        return {
            str(
                key
            ): _primitive(
                item
            )
            for key, item in sorted(
                value.items(),
                key=lambda item: str(
                    item[0]
                ),
            )
        }

    return value


def _sha256_payload(
    payload: Any,
) -> str:
    encoded = json.dumps(
        _primitive(
            payload
        ),
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()


@dataclass(
    frozen=True
)
class TransferGateResult:
    gate_key: str
    gate_kind: TransferGateKind
    status: TransferGateStatus
    evidence_sha256: tuple[str, ...] = ()
    reason_code: str | None = None

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "gate_key",
            _require_nonempty(
                self.gate_key,
                field_name="gate_key",
            ),
        )

        if not isinstance(
            self.gate_kind,
            TransferGateKind,
        ):
            raise CapabilityTransferQualificationError(
                "gate_kind must be a TransferGateKind"
            )

        if not isinstance(
            self.status,
            TransferGateStatus,
        ):
            raise CapabilityTransferQualificationError(
                "status must be a TransferGateStatus"
            )

        object.__setattr__(
            self,
            "evidence_sha256",
            _require_sha256_tuple(
                self.evidence_sha256,
                field_name="evidence_sha256",
            ),
        )

        if self.reason_code is not None:
            object.__setattr__(
                self,
                "reason_code",
                _require_nonempty(
                    self.reason_code,
                    field_name="reason_code",
                ),
            )

        if (
            self.status
            is TransferGateStatus.PASS
            and not self.evidence_sha256
        ):
            raise CapabilityTransferQualificationError(
                "a passing transfer gate requires evidence"
            )

        if (
            self.status
            in {
                TransferGateStatus.FAIL,
                TransferGateStatus.NOT_RUN,
            }
            and self.reason_code
            is None
        ):
            raise CapabilityTransferQualificationError(
                "failed or not-run transfer gates require a reason_code"
            )

        if (
            self.status
            is TransferGateStatus.NOT_RUN
            and self.evidence_sha256
        ):
            raise CapabilityTransferQualificationError(
                "a not-run gate cannot claim execution evidence"
            )


@dataclass(
    frozen=True
)
class CapabilityTransferCase:
    case_key: str
    capability_key: str
    capability_version: str
    source_binding_identity_sha256: str
    source_capability_sha256: str
    target_binding_identity_sha256: str
    required_access_tier: ModelAccessTier
    required_gate_keys: tuple[str, ...]
    optional_gate_keys: tuple[str, ...] = ()

    def __post_init__(
        self,
    ) -> None:
        for field_name in (
            "case_key",
            "capability_key",
            "capability_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_nonempty(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name=field_name,
                ),
            )

        for field_name in (
            "source_binding_identity_sha256",
            "source_capability_sha256",
            "target_binding_identity_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_sha256(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name=field_name,
                ),
            )

        if not isinstance(
            self.required_access_tier,
            ModelAccessTier,
        ):
            raise CapabilityTransferQualificationError(
                "required_access_tier must be a ModelAccessTier"
            )

        object.__setattr__(
            self,
            "required_gate_keys",
            _require_unique_strings(
                self.required_gate_keys,
                field_name="required_gate_keys",
            ),
        )

        object.__setattr__(
            self,
            "optional_gate_keys",
            _require_unique_strings(
                self.optional_gate_keys,
                field_name="optional_gate_keys",
            ),
        )

        if not self.required_gate_keys:
            raise CapabilityTransferQualificationError(
                "required_gate_keys must not be empty"
            )

        overlap = (
            set(
                self.required_gate_keys
            )
            & set(
                self.optional_gate_keys
            )
        )

        if overlap:
            raise CapabilityTransferQualificationError(
                "required and optional transfer gates must not overlap"
            )


@dataclass(
    frozen=True
)
class CapabilityTransferEvaluation:
    case: CapabilityTransferCase
    target_access_tier: ModelAccessTier
    gate_results: tuple[
        TransferGateResult,
        ...
    ]
    disposition: TransferCapabilityDisposition
    reason_code: str
    qualification_evidence_sha256: tuple[str, ...]

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.case,
            CapabilityTransferCase,
        ):
            raise CapabilityTransferQualificationError(
                "case must be a CapabilityTransferCase"
            )

        if not isinstance(
            self.target_access_tier,
            ModelAccessTier,
        ):
            raise CapabilityTransferQualificationError(
                "target_access_tier must be a ModelAccessTier"
            )

        if not isinstance(
            self.disposition,
            TransferCapabilityDisposition,
        ):
            raise CapabilityTransferQualificationError(
                "disposition must be a TransferCapabilityDisposition"
            )

        object.__setattr__(
            self,
            "reason_code",
            _require_nonempty(
                self.reason_code,
                field_name="reason_code",
            ),
        )

        object.__setattr__(
            self,
            "qualification_evidence_sha256",
            _require_sha256_tuple(
                self.qualification_evidence_sha256,
                field_name="qualification_evidence_sha256",
            ),
        )


def calculate_transfer_case_sha256(
    case: CapabilityTransferCase,
) -> str:
    if not isinstance(
        case,
        CapabilityTransferCase,
    ):
        raise CapabilityTransferQualificationError(
            "case must be a CapabilityTransferCase"
        )

    return _sha256_payload(
        case
    )


def calculate_transfer_evaluation_sha256(
    evaluation: CapabilityTransferEvaluation,
) -> str:
    if not isinstance(
        evaluation,
        CapabilityTransferEvaluation,
    ):
        raise CapabilityTransferQualificationError(
            "evaluation must be a CapabilityTransferEvaluation"
        )

    return _sha256_payload(
        evaluation
    )


def _access_satisfies(
    *,
    available: ModelAccessTier,
    required: ModelAccessTier,
) -> bool:
    return (
        _ACCESS_RANK[
            available
        ]
        >= _ACCESS_RANK[
            required
        ]
    )


def evaluate_capability_transfer(
    *,
    case: CapabilityTransferCase,
    target_access_tier: ModelAccessTier,
    gate_results: Iterable[
        TransferGateResult
    ],
) -> CapabilityTransferEvaluation:
    if not isinstance(
        case,
        CapabilityTransferCase,
    ):
        raise CapabilityTransferQualificationError(
            "case must be a CapabilityTransferCase"
        )

    if not isinstance(
        target_access_tier,
        ModelAccessTier,
    ):
        raise CapabilityTransferQualificationError(
            "target_access_tier must be a ModelAccessTier"
        )

    normalized_results = tuple(
        sorted(
            gate_results,
            key=lambda item: (
                item.gate_key,
                item.gate_kind.value,
            ),
        )
    )

    if not all(
        isinstance(
            item,
            TransferGateResult,
        )
        for item in normalized_results
    ):
        raise CapabilityTransferQualificationError(
            "all gate_results must be TransferGateResult values"
        )

    gate_keys = [
        item.gate_key
        for item in normalized_results
    ]

    if len(
        gate_keys
    ) != len(
        set(
            gate_keys
        )
    ):
        raise CapabilityTransferQualificationError(
            "gate_results must contain unique gate_key values"
        )

    allowed_gate_keys = (
        set(
            case.required_gate_keys
        )
        | set(
            case.optional_gate_keys
        )
    )

    unexpected = (
        set(
            gate_keys
        )
        - allowed_gate_keys
    )

    if unexpected:
        raise CapabilityTransferQualificationError(
            "unexpected gate_results: "
            + ",".join(
                sorted(
                    unexpected
                )
            )
        )

    if not _access_satisfies(
        available=target_access_tier,
        required=case.required_access_tier,
    ):
        return CapabilityTransferEvaluation(
            case=case,
            target_access_tier=target_access_tier,
            gate_results=normalized_results,
            disposition=(
                TransferCapabilityDisposition.UNAVAILABLE
            ),
            reason_code=(
                "TARGET_ACCESS_TIER_INSUFFICIENT"
            ),
            qualification_evidence_sha256=(),
        )

    by_key = {
        item.gate_key: item
        for item in normalized_results
    }

    missing = [
        key
        for key in case.required_gate_keys
        if key not in by_key
    ]

    if missing:
        return CapabilityTransferEvaluation(
            case=case,
            target_access_tier=target_access_tier,
            gate_results=normalized_results,
            disposition=(
                TransferCapabilityDisposition.BLOCKED
            ),
            reason_code=(
                "REQUIRED_GATE_NOT_RECORDED:"
                + ",".join(
                    sorted(
                        missing
                    )
                )
            ),
            qualification_evidence_sha256=(),
        )

    required_results = tuple(
        by_key[
            key
        ]
        for key in case.required_gate_keys
    )

    failed = tuple(
        item
        for item in required_results
        if item.status
        is TransferGateStatus.FAIL
    )

    if failed:
        return CapabilityTransferEvaluation(
            case=case,
            target_access_tier=target_access_tier,
            gate_results=normalized_results,
            disposition=(
                TransferCapabilityDisposition.UNQUALIFIED
            ),
            reason_code=(
                "REQUIRED_GATE_FAILED:"
                + ",".join(
                    sorted(
                        item.gate_key
                        for item in failed
                    )
                )
            ),
            qualification_evidence_sha256=tuple(
                sorted(
                    {
                        sha
                        for item in required_results
                        for sha in item.evidence_sha256
                    }
                )
            ),
        )

    not_applicable = tuple(
        item
        for item in required_results
        if item.status
        is TransferGateStatus.NOT_APPLICABLE
    )

    if not_applicable:
        return CapabilityTransferEvaluation(
            case=case,
            target_access_tier=target_access_tier,
            gate_results=normalized_results,
            disposition=(
                TransferCapabilityDisposition.UNQUALIFIED
            ),
            reason_code=(
                "REQUIRED_GATE_NOT_APPLICABLE:"
                + ",".join(
                    sorted(
                        item.gate_key
                        for item in not_applicable
                    )
                )
            ),
            qualification_evidence_sha256=tuple(
                sorted(
                    {
                        sha
                        for item in required_results
                        for sha in item.evidence_sha256
                    }
                )
            ),
        )

    not_run = tuple(
        item
        for item in required_results
        if item.status
        is TransferGateStatus.NOT_RUN
    )

    if not_run:
        return CapabilityTransferEvaluation(
            case=case,
            target_access_tier=target_access_tier,
            gate_results=normalized_results,
            disposition=(
                TransferCapabilityDisposition.BLOCKED
            ),
            reason_code=(
                "REQUIRED_GATE_NOT_RUN:"
                + ",".join(
                    sorted(
                        item.gate_key
                        for item in not_run
                    )
                )
            ),
            qualification_evidence_sha256=tuple(
                sorted(
                    {
                        sha
                        for item in required_results
                        for sha in item.evidence_sha256
                    }
                )
            ),
        )

    if not all(
        item.status
        is TransferGateStatus.PASS
        for item in required_results
    ):
        raise CapabilityTransferQualificationError(
            "required transfer gates resolved to an unsupported state"
        )

    evidence = tuple(
        sorted(
            {
                sha
                for item in required_results
                for sha in item.evidence_sha256
            }
        )
    )

    return CapabilityTransferEvaluation(
        case=case,
        target_access_tier=target_access_tier,
        gate_results=normalized_results,
        disposition=(
            TransferCapabilityDisposition.QUALIFIED
        ),
        reason_code="ALL_REQUIRED_GATES_PASS",
        qualification_evidence_sha256=evidence,
    )


@dataclass(
    frozen=True
)
class CapabilityTransferPack:
    target_binding_identity_sha256: str
    evaluations: tuple[
        CapabilityTransferEvaluation,
        ...
    ]

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "target_binding_identity_sha256",
            _require_sha256(
                self.target_binding_identity_sha256,
                field_name="target_binding_identity_sha256",
            ),
        )

        if not self.evaluations:
            raise CapabilityTransferQualificationError(
                "a transfer pack must contain at least one evaluation"
            )

        if not all(
            isinstance(
                item,
                CapabilityTransferEvaluation,
            )
            for item in self.evaluations
        ):
            raise CapabilityTransferQualificationError(
                "evaluations must contain CapabilityTransferEvaluation values"
            )

        for item in self.evaluations:
            if (
                item.case.target_binding_identity_sha256
                != self.target_binding_identity_sha256
            ):
                raise CapabilityTransferQualificationError(
                    "all transfer evaluations must target the same binding"
                )

        identities = [
            (
                item.case.capability_key,
                item.case.capability_version,
            )
            for item in self.evaluations
        ]

        if len(
            identities
        ) != len(
            set(
                identities
            )
        ):
            raise CapabilityTransferQualificationError(
                "transfer pack capabilities must be unique"
            )

    @property
    def verdict(
        self,
    ) -> TransferPackVerdict:
        dispositions = tuple(
            item.disposition
            for item in self.evaluations
        )

        if all(
            item
            is TransferCapabilityDisposition.QUALIFIED
            for item in dispositions
        ):
            return TransferPackVerdict.PASS

        qualified_count = sum(
            item
            is TransferCapabilityDisposition.QUALIFIED
            for item in dispositions
        )

        if qualified_count:
            return TransferPackVerdict.PARTIAL

        if any(
            item
            is TransferCapabilityDisposition.BLOCKED
            for item in dispositions
        ):
            return TransferPackVerdict.BLOCKED

        return TransferPackVerdict.FAIL

    def snapshot_payload(
        self,
    ) -> dict[str, Any]:
        ordered = tuple(
            sorted(
                self.evaluations,
                key=lambda item: (
                    item.case.capability_key,
                    item.case.capability_version,
                    calculate_transfer_evaluation_sha256(
                        item
                    ),
                ),
            )
        )

        return {
            "schema_version": (
                CAPABILITY_TRANSFER_QUALIFICATION_SCHEMA_VERSION
            ),
            "target_binding_identity_sha256": (
                self.target_binding_identity_sha256
            ),
            "verdict": self.verdict.value,
            "evaluations": [
                _primitive(
                    item
                )
                for item in ordered
            ],
        }

    def snapshot_sha256(
        self,
    ) -> str:
        return _sha256_payload(
            self.snapshot_payload()
        )


def build_behavioral_transfer_case(
    *,
    case_key: str,
    capability_key: str,
    capability_version: str,
    source_binding_identity_sha256: str,
    source_capability_sha256: str,
    target_binding_identity_sha256: str,
) -> CapabilityTransferCase:
    return CapabilityTransferCase(
        case_key=case_key,
        capability_key=capability_key,
        capability_version=capability_version,
        source_binding_identity_sha256=(
            source_binding_identity_sha256
        ),
        source_capability_sha256=(
            source_capability_sha256
        ),
        target_binding_identity_sha256=(
            target_binding_identity_sha256
        ),
        required_access_tier=(
            ModelAccessTier.CLOSED_API
        ),
        required_gate_keys=(
            STANDARD_BEHAVIORAL_REQUIRED_GATES
        ),
        optional_gate_keys=(
            (
                "resource_budget",
            )
        ),
    )


def build_internal_capture_transfer_case(
    *,
    case_key: str,
    capability_key: str,
    capability_version: str,
    source_binding_identity_sha256: str,
    source_capability_sha256: str,
    target_binding_identity_sha256: str,
) -> CapabilityTransferCase:
    return CapabilityTransferCase(
        case_key=case_key,
        capability_key=capability_key,
        capability_version=capability_version,
        source_binding_identity_sha256=(
            source_binding_identity_sha256
        ),
        source_capability_sha256=(
            source_capability_sha256
        ),
        target_binding_identity_sha256=(
            target_binding_identity_sha256
        ),
        required_access_tier=(
            ModelAccessTier.AUTHORIZED_INTERNALS
        ),
        required_gate_keys=(
            STANDARD_INTERNAL_CAPTURE_REQUIRED_GATES
        ),
        optional_gate_keys=(
            (
                "resource_budget",
            )
        ),
    )


def build_reversible_intervention_transfer_case(
    *,
    case_key: str,
    capability_key: str,
    capability_version: str,
    source_binding_identity_sha256: str,
    source_capability_sha256: str,
    target_binding_identity_sha256: str,
) -> CapabilityTransferCase:
    return CapabilityTransferCase(
        case_key=case_key,
        capability_key=capability_key,
        capability_version=capability_version,
        source_binding_identity_sha256=(
            source_binding_identity_sha256
        ),
        source_capability_sha256=(
            source_capability_sha256
        ),
        target_binding_identity_sha256=(
            target_binding_identity_sha256
        ),
        required_access_tier=(
            ModelAccessTier.AUTHORIZED_INTERNALS
        ),
        required_gate_keys=(
            STANDARD_REVERSIBLE_INTERVENTION_REQUIRED_GATES
        ),
        optional_gate_keys=(
            (
                "resource_budget",
            )
        ),
    )
