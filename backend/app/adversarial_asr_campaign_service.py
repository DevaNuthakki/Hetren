"""Application orchestration for adversarial ASR campaigns.

The campaign service walks the exact case inventory from a verified
adversarial suite, executes cases through the existing single-case
application service, and seals aggregate campaign evidence.

Cancellation is cooperative. This service never attempts to forcibly
terminate provider inference. A stop signal observed after provider
execution causes that result to be discarded and the current/remaining
cases to be represented as cancelled.

Per-case timeout enforcement is intentionally supplied by a controlled
execution wrapper through ASRAdversarialCampaignCaseTimedOutError. This
service does not create unsafe thread-killing timeout machinery.

The service does not persist database state, apply qualification
thresholds, issue certification, authorize production use, or modify
release authority.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.adversarial_asr_execution_service import (
    ASRAdversarialExecutionServiceError,
    ASRAdversarialExecutionServiceResult,
    execute_asr_adversarial_case,
)
from app.speech import (
    ASRProvider,
    TranscriptionError,
)
from hvee.packs.asr import (
    ASRAdversarialCampaignAttempt,
    ASRAdversarialCampaignDefinition,
    ASRAdversarialCampaignEvidenceBundle,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialExecutionStatus,
    ASRAdversarialSuiteDefinition,
    ASRAdversarialTerminologyBinding,
    build_asr_adversarial_campaign_evidence_v1,
    verify_asr_adversarial_evidence_v1,
)


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)
_VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+$"
)


FAILED_DETAIL = (
    "ASR provider transcription failed."
)
INVALID_DETAIL = (
    "Adversarial case execution was invalid."
)
MISSING_AUDIO_DETAIL = (
    "Adversarial case audio was not supplied."
)
TIMED_OUT_DETAIL = (
    "Adversarial case execution timed out."
)
CANCELLED_DETAIL = (
    "Adversarial campaign execution was cancelled."
)


class ASRAdversarialCampaignServiceError(ValueError):
    """Raised when campaign orchestration inputs are invalid."""


class ASRAdversarialCampaignCaseTimedOutError(
    TimeoutError
):
    """Controlled signal that one case exceeded its execution deadline."""


class ASRAdversarialCampaignCancelledError(
    Exception
):
    """Controlled signal that campaign execution was cancelled."""


class ASRAdversarialCampaignStopEvent(Protocol):
    """Minimal cooperative cancellation signal."""

    def is_set(self) -> bool:
        ...


class ASRAdversarialCampaignCaseExecutor(Protocol):
    """Single-case executor contract used by the campaign service."""

    def __call__(
        self,
        *,
        execution_id: str,
        case_id: str,
        audio_path: str | Path,
        requested_model_name: str,
        provider: ASRProvider,
        terminology: ASRAdversarialTerminologyBinding,
        suite: ASRAdversarialSuiteDefinition,
        suite_evidence: ASRAdversarialEvidenceBundle,
    ) -> ASRAdversarialExecutionServiceResult:
        ...


@dataclass(frozen=True, slots=True)
class ASRAdversarialCampaignServiceResult:
    """In-memory outcome of one complete campaign orchestration."""

    definition: ASRAdversarialCampaignDefinition
    evidence: ASRAdversarialCampaignEvidenceBundle
    attempts: tuple[
        ASRAdversarialCampaignAttempt,
        ...,
    ]
    completed_results: tuple[
        ASRAdversarialExecutionServiceResult,
        ...,
    ]


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
        raise ASRAdversarialCampaignServiceError(
            f"{name} must be a canonical lowercase identifier."
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
        raise ASRAdversarialCampaignServiceError(
            f"{name} must be a semantic version."
        )

    return value


def _require_non_empty_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise ASRAdversarialCampaignServiceError(
            f"{name} must be non-empty text."
        )

    return value.strip()


def _provider_key(
    provider: object,
) -> str:
    return _require_non_empty_string(
        name="campaign ASR provider",
        value=getattr(
            provider,
            "provider_name",
            None,
        ),
    )


def _stop_requested(
    stop_event: (
        ASRAdversarialCampaignStopEvent
        | None
    ),
) -> bool:
    if stop_event is None:
        return False

    return bool(
        stop_event.is_set()
    )


def _execution_id(
    *,
    campaign_id: str,
    case_id: str,
) -> str:
    value = (
        f"{campaign_id}.{case_id}"
    )

    return _require_identifier(
        name="campaign case execution id",
        value=value,
    )


def _noncompleted_attempt(
    *,
    case_id: str,
    execution_id: str,
    status: ASRAdversarialExecutionStatus,
    status_detail: str,
) -> ASRAdversarialCampaignAttempt:
    return ASRAdversarialCampaignAttempt(
        case_id=case_id,
        execution_id=execution_id,
        status=status,
        status_detail=status_detail,
    )


def _validate_audio_mapping(
    *,
    audio_paths: object,
    expected_case_ids: tuple[str, ...],
) -> Mapping[
    str,
    str | Path,
]:
    if not isinstance(
        audio_paths,
        Mapping,
    ):
        raise ASRAdversarialCampaignServiceError(
            "campaign audio paths must be a mapping."
        )

    supplied_case_ids: set[str] = set()

    for key in audio_paths:
        if not isinstance(
            key,
            str,
        ):
            raise ASRAdversarialCampaignServiceError(
                "campaign audio mapping keys "
                "must be case-id text."
            )

        supplied_case_ids.add(
            key
        )

    undeclared = (
        supplied_case_ids
        - set(expected_case_ids)
    )

    if undeclared:
        raise ASRAdversarialCampaignServiceError(
            "campaign audio mapping contains "
            "undeclared suite cases."
        )

    return audio_paths


def execute_asr_adversarial_campaign(
    *,
    campaign_id: str,
    campaign_version: str,
    audio_paths: Mapping[
        str,
        str | Path,
    ],
    requested_model_name: str,
    provider: ASRProvider,
    terminology: ASRAdversarialTerminologyBinding,
    suite: ASRAdversarialSuiteDefinition,
    suite_evidence: ASRAdversarialEvidenceBundle,
    stop_event: (
        ASRAdversarialCampaignStopEvent
        | None
    ) = None,
    case_executor: (
        ASRAdversarialCampaignCaseExecutor
    ) = execute_asr_adversarial_case,
) -> ASRAdversarialCampaignServiceResult:
    """Execute every sealed suite case and build Slice E evidence."""

    normalized_campaign_id = (
        _require_identifier(
            name="adversarial campaign id",
            value=campaign_id,
        )
    )

    normalized_campaign_version = (
        _require_version(
            name="adversarial campaign version",
            value=campaign_version,
        )
    )

    normalized_model = (
        _require_non_empty_string(
            name="requested ASR model",
            value=requested_model_name,
        )
    )

    provider_key = _provider_key(
        provider
    )

    if not isinstance(
        terminology,
        ASRAdversarialTerminologyBinding,
    ):
        raise ASRAdversarialCampaignServiceError(
            "campaign requires terminology configuration."
        )

    if not callable(
        case_executor
    ):
        raise ASRAdversarialCampaignServiceError(
            "campaign case executor must be callable."
        )

    if (
        stop_event is not None
        and not callable(
            getattr(
                stop_event,
                "is_set",
                None,
            )
        )
    ):
        raise ASRAdversarialCampaignServiceError(
            "campaign stop event is invalid."
        )

    # Verify once before any provider execution. Slice D will
    # independently reverify for every executed case.
    verified_suite = (
        verify_asr_adversarial_evidence_v1(
            payload=suite_evidence.payload,
            expected_sha256=(
                suite_evidence.sha256
            ),
            definition=suite,
        )
    )

    expected_case_ids = tuple(
        case.case_id
        for case in suite.cases
    )

    validated_audio_paths = (
        _validate_audio_mapping(
            audio_paths=audio_paths,
            expected_case_ids=(
                expected_case_ids
            ),
        )
    )

    attempts: list[
        ASRAdversarialCampaignAttempt
    ] = []

    completed_results: list[
        ASRAdversarialExecutionServiceResult
    ] = []

    cancellation_observed = False

    for case in suite.cases:
        execution_id = _execution_id(
            campaign_id=(
                normalized_campaign_id
            ),
            case_id=case.case_id,
        )

        if (
            cancellation_observed
            or _stop_requested(
                stop_event
            )
        ):
            cancellation_observed = True

            attempts.append(
                _noncompleted_attempt(
                    case_id=case.case_id,
                    execution_id=(
                        execution_id
                    ),
                    status=(
                        ASRAdversarialExecutionStatus
                        .CANCELLED
                    ),
                    status_detail=(
                        CANCELLED_DETAIL
                    ),
                )
            )

            continue

        if (
            case.case_id
            not in validated_audio_paths
        ):
            attempts.append(
                _noncompleted_attempt(
                    case_id=case.case_id,
                    execution_id=(
                        execution_id
                    ),
                    status=(
                        ASRAdversarialExecutionStatus
                        .INVALID
                    ),
                    status_detail=(
                        MISSING_AUDIO_DETAIL
                    ),
                )
            )

            continue

        audio_path = (
            validated_audio_paths[
                case.case_id
            ]
        )

        try:
            result = case_executor(
                execution_id=execution_id,
                case_id=case.case_id,
                audio_path=audio_path,
                requested_model_name=(
                    normalized_model
                ),
                provider=provider,
                terminology=terminology,
                suite=suite,
                suite_evidence=(
                    suite_evidence
                ),
            )

        except ASRAdversarialCampaignCancelledError:
            cancellation_observed = True

            attempts.append(
                _noncompleted_attempt(
                    case_id=case.case_id,
                    execution_id=(
                        execution_id
                    ),
                    status=(
                        ASRAdversarialExecutionStatus
                        .CANCELLED
                    ),
                    status_detail=(
                        CANCELLED_DETAIL
                    ),
                )
            )

            continue

        except ASRAdversarialCampaignCaseTimedOutError:
            if _stop_requested(
                stop_event
            ):
                cancellation_observed = True

                attempts.append(
                    _noncompleted_attempt(
                        case_id=case.case_id,
                        execution_id=(
                            execution_id
                        ),
                        status=(
                            ASRAdversarialExecutionStatus
                            .CANCELLED
                        ),
                        status_detail=(
                            CANCELLED_DETAIL
                        ),
                    )
                )

                continue

            attempts.append(
                _noncompleted_attempt(
                    case_id=case.case_id,
                    execution_id=(
                        execution_id
                    ),
                    status=(
                        ASRAdversarialExecutionStatus
                        .TIMED_OUT
                    ),
                    status_detail=(
                        TIMED_OUT_DETAIL
                    ),
                )
            )

            continue

        except TranscriptionError:
            if _stop_requested(
                stop_event
            ):
                cancellation_observed = True

                attempts.append(
                    _noncompleted_attempt(
                        case_id=case.case_id,
                        execution_id=(
                            execution_id
                        ),
                        status=(
                            ASRAdversarialExecutionStatus
                            .CANCELLED
                        ),
                        status_detail=(
                            CANCELLED_DETAIL
                        ),
                    )
                )

                continue

            attempts.append(
                _noncompleted_attempt(
                    case_id=case.case_id,
                    execution_id=(
                        execution_id
                    ),
                    status=(
                        ASRAdversarialExecutionStatus
                        .FAILED
                    ),
                    status_detail=(
                        FAILED_DETAIL
                    ),
                )
            )

            continue

        except ASRAdversarialExecutionServiceError:
            if _stop_requested(
                stop_event
            ):
                cancellation_observed = True

                attempts.append(
                    _noncompleted_attempt(
                        case_id=case.case_id,
                        execution_id=(
                            execution_id
                        ),
                        status=(
                            ASRAdversarialExecutionStatus
                            .CANCELLED
                        ),
                        status_detail=(
                            CANCELLED_DETAIL
                        ),
                    )
                )

                continue

            attempts.append(
                _noncompleted_attempt(
                    case_id=case.case_id,
                    execution_id=(
                        execution_id
                    ),
                    status=(
                        ASRAdversarialExecutionStatus
                        .INVALID
                    ),
                    status_detail=(
                        INVALID_DETAIL
                    ),
                )
            )

            continue

        # Mirror the runner's late-stop safety check. If cancellation
        # arrived while provider inference was running, discard the
        # apparently successful result rather than sealing it.
        if _stop_requested(
            stop_event
        ):
            cancellation_observed = True

            attempts.append(
                _noncompleted_attempt(
                    case_id=case.case_id,
                    execution_id=(
                        execution_id
                    ),
                    status=(
                        ASRAdversarialExecutionStatus
                        .CANCELLED
                    ),
                    status_detail=(
                        CANCELLED_DETAIL
                    ),
                )
            )

            continue

        if not isinstance(
            result,
            ASRAdversarialExecutionServiceResult,
        ):
            raise ASRAdversarialCampaignServiceError(
                "campaign case executor returned "
                "an invalid result."
            )

        if (
            result.case_id
            != case.case_id
        ):
            raise ASRAdversarialCampaignServiceError(
                "campaign case executor returned "
                "the wrong case identity."
            )

        attempts.append(
            ASRAdversarialCampaignAttempt(
                case_id=case.case_id,
                execution_id=execution_id,
                status=(
                    ASRAdversarialExecutionStatus
                    .COMPLETED
                ),
                execution_definition=(
                    result.execution_definition
                ),
                execution_evidence=(
                    result.execution_evidence
                ),
            )
        )

        completed_results.append(
            result
        )

    definition = (
        ASRAdversarialCampaignDefinition(
            campaign_id=(
                normalized_campaign_id
            ),
            campaign_version=(
                normalized_campaign_version
            ),
            suite_sha256=(
                verified_suite.sha256
            ),
            provider_key=provider_key,
            model_key=normalized_model,
            attempts=tuple(
                attempts
            ),
        )
    )

    evidence = (
        build_asr_adversarial_campaign_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    return ASRAdversarialCampaignServiceResult(
        definition=definition,
        evidence=evidence,
        attempts=tuple(
            attempts
        ),
        completed_results=tuple(
            completed_results
        ),
    )
