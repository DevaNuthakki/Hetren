"""Deterministic campaign evidence for adversarial ASR development runs.

This module aggregates one controlled attempt for every case in a sealed
adversarial suite.

Completed attempts must bind and reverify their Slice B execution evidence.
Non-completed attempts deliberately contain no transcript, semantic evidence,
or observed execution-environment claim.

This artifact is descriptive development evidence only. It does not define
qualification thresholds, issue certification, authorize production use, or
modify a release verdict.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_evidence import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialSuiteDefinition,
    verify_asr_adversarial_evidence_v1,
)
from hvee.packs.asr.adversarial_execution_evidence import (
    ASRAdversarialExecutionDefinition,
    ASRAdversarialExecutionEvidenceBundle,
    ASRAdversarialExecutionStatus,
    verify_asr_adversarial_execution_evidence_v1,
)


ASR_ADVERSARIAL_CAMPAIGN_EVIDENCE_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_CAMPAIGN_EVIDENCE_KEY = (
    "hetren.asr.adversarial-campaign-evidence.en-us"
)
ASR_ADVERSARIAL_CAMPAIGN_EVIDENCE_VERSION = "1.0.0"


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)
_VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+$"
)


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or _IDENTIFIER_PATTERN.fullmatch(value)
        is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )

    return value


def _require_version(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _VERSION_PATTERN.fullmatch(value)
        is None
    ):
        raise HveeContractError(
            f"{name} must be a semantic version"
        )

    return value


def _require_non_empty_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise HveeContractError(
            f"{name} must be a non-empty trimmed string"
        )

    return value


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _canonical_json(
    value: object,
) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "adversarial campaign evidence must contain "
            "valid deterministic JSON"
        ) from exc


def calculate_asr_adversarial_campaign_evidence_sha256(
    payload: object,
) -> str:
    """Hash canonical adversarial campaign evidence."""

    return hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialCampaignAttempt:
    """One controlled post-execution record for one sealed suite case."""

    case_id: str
    execution_id: str
    status: ASRAdversarialExecutionStatus
    execution_definition: (
        ASRAdversarialExecutionDefinition
        | None
    ) = None
    execution_evidence: (
        ASRAdversarialExecutionEvidenceBundle
        | None
    ) = None
    status_detail: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(
            name="adversarial campaign case id",
            value=self.case_id,
        )
        _require_identifier(
            name="adversarial campaign execution id",
            value=self.execution_id,
        )

        if not isinstance(
            self.status,
            ASRAdversarialExecutionStatus,
        ):
            raise HveeContractError(
                "adversarial campaign attempt requires "
                "a versioned execution status"
            )

        if (
            self.status
            == ASRAdversarialExecutionStatus.COMPLETED
        ):
            if not isinstance(
                self.execution_definition,
                ASRAdversarialExecutionDefinition,
            ):
                raise HveeContractError(
                    "completed campaign attempt requires "
                    "an execution definition"
                )

            if not isinstance(
                self.execution_evidence,
                ASRAdversarialExecutionEvidenceBundle,
            ):
                raise HveeContractError(
                    "completed campaign attempt requires "
                    "execution evidence"
                )

            if (
                self.execution_definition.status
                != ASRAdversarialExecutionStatus.COMPLETED
            ):
                raise HveeContractError(
                    "completed campaign attempt requires "
                    "a completed execution definition"
                )

            if (
                self.execution_definition.case_id
                != self.case_id
                or self.execution_definition.execution_id
                != self.execution_id
            ):
                raise HveeContractError(
                    "completed campaign attempt identity "
                    "does not match its execution definition"
                )

            if self.status_detail is not None:
                raise HveeContractError(
                    "completed campaign attempt cannot "
                    "contain failure detail"
                )

            return

        if (
            self.execution_definition is not None
            or self.execution_evidence is not None
        ):
            raise HveeContractError(
                "non-completed campaign attempt cannot "
                "claim Slice B execution evidence"
            )

        _require_non_empty_string(
            name="non-completed campaign status detail",
            value=self.status_detail,
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCampaignDefinition:
    """Caller-owned post-run inputs for deterministic campaign sealing."""

    campaign_id: str
    campaign_version: str
    suite_sha256: str
    provider_key: str
    model_key: str
    attempts: tuple[
        ASRAdversarialCampaignAttempt,
        ...,
    ]

    def __post_init__(self) -> None:
        _require_identifier(
            name="adversarial campaign id",
            value=self.campaign_id,
        )
        _require_version(
            name="adversarial campaign version",
            value=self.campaign_version,
        )
        _require_sha256(
            name="adversarial campaign suite",
            value=self.suite_sha256,
        )
        _require_non_empty_string(
            name="adversarial campaign provider",
            value=self.provider_key,
        )
        _require_non_empty_string(
            name="adversarial campaign model",
            value=self.model_key,
        )

        if (
            not isinstance(self.attempts, tuple)
            or not self.attempts
            or not all(
                isinstance(
                    attempt,
                    ASRAdversarialCampaignAttempt,
                )
                for attempt in self.attempts
            )
        ):
            raise HveeContractError(
                "adversarial campaign requires attempts"
            )

        case_ids = tuple(
            attempt.case_id
            for attempt in self.attempts
        )

        if tuple(sorted(case_ids)) != case_ids:
            raise HveeContractError(
                "adversarial campaign attempts must "
                "be ordered by case id"
            )

        if len(case_ids) != len(set(case_ids)):
            raise HveeContractError(
                "adversarial campaign case ids "
                "must be unique"
            )

        execution_ids = tuple(
            attempt.execution_id
            for attempt in self.attempts
        )

        if len(execution_ids) != len(
            set(execution_ids)
        ):
            raise HveeContractError(
                "adversarial campaign execution ids "
                "must be unique"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCampaignEvidenceBundle:
    """Deterministic non-certifying aggregate campaign evidence."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "adversarial campaign evidence "
                "payload must be an object"
            )

        _require_sha256(
            name="adversarial campaign evidence",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_campaign_evidence_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "adversarial campaign evidence SHA-256 "
                "does not match its payload"
            )


def _attempt_payload(
    *,
    attempt: ASRAdversarialCampaignAttempt,
    execution_evidence_sha256: str | None,
) -> dict[str, object]:
    return {
        "case_id": attempt.case_id,
        "execution_id": attempt.execution_id,
        "status": attempt.status.value,
        "status_detail": attempt.status_detail,
        "execution_evidence_sha256": (
            execution_evidence_sha256
        ),
    }


def _status_counts(
    attempts: tuple[
        ASRAdversarialCampaignAttempt,
        ...,
    ],
) -> dict[str, int]:
    return {
        status.value: sum(
            attempt.status == status
            for attempt in attempts
        )
        for status in ASRAdversarialExecutionStatus
    }


def build_asr_adversarial_campaign_evidence_v1(
    definition: ASRAdversarialCampaignDefinition,
    *,
    suite: ASRAdversarialSuiteDefinition,
    suite_evidence: ASRAdversarialEvidenceBundle,
) -> ASRAdversarialCampaignEvidenceBundle:
    """Build deterministic post-run campaign evidence."""

    if not isinstance(
        definition,
        ASRAdversarialCampaignDefinition,
    ):
        raise HveeContractError(
            "adversarial campaign evidence requires "
            "ASRAdversarialCampaignDefinition"
        )

    if not isinstance(
        suite,
        ASRAdversarialSuiteDefinition,
    ):
        raise HveeContractError(
            "adversarial campaign evidence requires "
            "ASRAdversarialSuiteDefinition"
        )

    if not isinstance(
        suite_evidence,
        ASRAdversarialEvidenceBundle,
    ):
        raise HveeContractError(
            "adversarial campaign evidence requires "
            "sealed suite evidence"
        )

    verified_suite = (
        verify_asr_adversarial_evidence_v1(
            payload=suite_evidence.payload,
            expected_sha256=suite_evidence.sha256,
            definition=suite,
        )
    )

    if definition.suite_sha256 != verified_suite.sha256:
        raise HveeContractError(
            "adversarial campaign does not bind "
            "the sealed suite evidence"
        )

    expected_case_ids = tuple(
        case.case_id
        for case in suite.cases
    )

    recorded_case_ids = tuple(
        attempt.case_id
        for attempt in definition.attempts
    )

    if recorded_case_ids != expected_case_ids:
        raise HveeContractError(
            "adversarial campaign must retain "
            "every sealed suite case exactly"
        )

    attempt_payloads: list[
        dict[str, object]
    ] = []

    completed_evidence_sha256s: list[
        str
    ] = []

    for attempt in definition.attempts:
        execution_evidence_sha256: str | None = None

        if (
            attempt.status
            == ASRAdversarialExecutionStatus.COMPLETED
        ):
            execution_definition = (
                attempt.execution_definition
            )
            execution_evidence = (
                attempt.execution_evidence
            )

            assert isinstance(
                execution_definition,
                ASRAdversarialExecutionDefinition,
            )
            assert isinstance(
                execution_evidence,
                ASRAdversarialExecutionEvidenceBundle,
            )

            if (
                execution_definition.provider_key
                != definition.provider_key
            ):
                raise HveeContractError(
                    "completed campaign execution "
                    "provider does not match campaign"
                )

            if (
                execution_definition.model_key
                != definition.model_key
            ):
                raise HveeContractError(
                    "completed campaign execution "
                    "model does not match campaign"
                )

            verified_execution = (
                verify_asr_adversarial_execution_evidence_v1(
                    payload=(
                        execution_evidence.payload
                    ),
                    expected_sha256=(
                        execution_evidence.sha256
                    ),
                    definition=(
                        execution_definition
                    ),
                    suite=suite,
                    suite_evidence=(
                        suite_evidence
                    ),
                )
            )

            execution_evidence_sha256 = (
                verified_execution.sha256
            )

            completed_evidence_sha256s.append(
                execution_evidence_sha256
            )

        attempt_payloads.append(
            _attempt_payload(
                attempt=attempt,
                execution_evidence_sha256=(
                    execution_evidence_sha256
                ),
            )
        )

    if len(completed_evidence_sha256s) != len(
        set(completed_evidence_sha256s)
    ):
        raise HveeContractError(
            "completed campaign execution evidence "
            "commitments must be unique"
        )

    payload: dict[str, object] = {
        "schema_version": (
            ASR_ADVERSARIAL_CAMPAIGN_EVIDENCE_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_CAMPAIGN_EVIDENCE_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_CAMPAIGN_EVIDENCE_VERSION
            ),
            "type": (
                "source_visible_adversarial_"
                "campaign_evidence"
            ),
        },
        "suite": {
            "key": ASR_ADVERSARIAL_EVIDENCE_KEY,
            "version": (
                ASR_ADVERSARIAL_EVIDENCE_VERSION
            ),
            "sha256": verified_suite.sha256,
        },
        "campaign": {
            "campaign_id": definition.campaign_id,
            "campaign_version": (
                definition.campaign_version
            ),
            "requested_execution": {
                "provider_key": (
                    definition.provider_key
                ),
                "model_key": (
                    definition.model_key
                ),
            },
            "coverage": {
                "expected_case_count": (
                    len(expected_case_ids)
                ),
                "recorded_case_count": (
                    len(recorded_case_ids)
                ),
                "coverage_complete": True,
                "expected_case_ids": list(
                    expected_case_ids
                ),
                "recorded_case_ids": list(
                    recorded_case_ids
                ),
            },
            "status_counts": _status_counts(
                definition.attempts
            ),
            "attempts": attempt_payloads,
        },
        "scientific_boundary": {
            "sealed_suite_reverified": True,
            "exact_suite_case_inventory_retained": True,
            "completed_child_execution_evidence_reverified_when_present": True,
            "noncompleted_attempts_contain_execution_evidence": False,
            "noncompleted_attempts_claim_observed_environment": False,
            "noncompleted_attempts_contain_transcript_commitment": False,
            "noncompleted_attempts_contain_semantic_evidence": False,
            "requested_provider_model_are_not_observed_runtime_for_failures": True,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }

    return ASRAdversarialCampaignEvidenceBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_campaign_evidence_sha256(
                payload
            )
        ),
    )


def verify_asr_adversarial_campaign_evidence_v1(
    *,
    payload: object,
    expected_sha256: object,
    definition: ASRAdversarialCampaignDefinition,
    suite: ASRAdversarialSuiteDefinition,
    suite_evidence: ASRAdversarialEvidenceBundle,
) -> ASRAdversarialCampaignEvidenceBundle:
    """Require exact equality with rebuilt v1 campaign evidence."""

    digest = _require_sha256(
        name="expected adversarial campaign evidence",
        value=expected_sha256,
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError(
            "supplied adversarial campaign "
            "evidence must be an object"
        )

    supplied = (
        ASRAdversarialCampaignEvidenceBundle(
            payload=payload,
            sha256=digest,
        )
    )

    rebuilt = (
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    if (
        supplied.payload != rebuilt.payload
        or supplied.sha256 != rebuilt.sha256
    ):
        raise HveeContractError(
            "adversarial campaign evidence "
            "does not match the v1 definition"
        )

    return rebuilt
