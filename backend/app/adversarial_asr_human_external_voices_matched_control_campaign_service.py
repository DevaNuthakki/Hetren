"""Execute and reverify the frozen VOiCES matched-control ASR campaign.

This I4e-B6 application bridge consumes the exact execution-ready B5 suite,
derives its 32 verified absolute audio paths, and delegates execution to the
existing adversarial campaign service.  It then reverifies the generic suite,
aggregate campaign evidence, every completed child execution, provider/model
identity, and the matched-pair completion population.

The resulting artifact preserves partial outcomes without treating them as
paired metric evidence.  It does not calculate WER/CER, apply qualification
thresholds, certify a model, authorize production use, persist database state,
or modify release authority.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from app.adversarial_asr_campaign_service import (
    ASRAdversarialCampaignCaseExecutor,
    ASRAdversarialCampaignServiceError,
    ASRAdversarialCampaignServiceResult,
    ASRAdversarialCampaignStopEvent,
    execute_asr_adversarial_campaign,
)
from app.adversarial_asr_execution_service import (
    ASRAdversarialExecutionServiceResult,
    execute_asr_adversarial_case,
)
from app.adversarial_asr_human_external_voices_matched_control_suite_projection import (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
    ASRAdversarialVOiCESMatchedControlSuiteBundle,
)
from app.speech import ASRProvider
from hvee.core.contracts import HveeContractError
from hvee.packs.asr import (
    ASRAdversarialCampaignAttempt,
    ASRAdversarialExecutionStatus,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
    verify_asr_adversarial_campaign_evidence_v1,
    verify_asr_adversarial_evidence_v1,
    verify_asr_adversarial_execution_evidence_v1,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
)


ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_KEY = (
    "hetren.asr.adversarial-human-external-"
    "voices-babble-matched-control-campaign"
)


class ASRAdversarialVOiCESMatchedControlCampaignError(ValueError):
    """Raised when B5 media cannot form trusted B6 campaign evidence."""


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
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            f"{name} must be a lowercase SHA-256."
        )

    return value


def _require_non_empty_trimmed_text(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            f"{name} must be non-empty trimmed text."
        )

    return value


def _canonical_json_bytes(
    value: object,
) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            "VOiCES matched-control campaign must be deterministic JSON."
        ) from error


def _provider_key(
    provider: ASRProvider,
) -> str:
    return _require_non_empty_trimmed_text(
        name="VOiCES matched-control ASR provider",
        value=getattr(provider, "provider_name", None),
    )


def _validate_suite_boundary(
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
) -> None:
    positive_authority = (
        suite.development_evidence_only,
        suite.reference_transcripts_projected,
        suite.adversarial_suite_built,
        suite.execution_ready,
    )
    negative_authority = (
        suite.asr_execution_verified,
        suite.qualification_threshold_applied,
        suite.production_qualified,
        suite.release_enforcement_eligible,
        suite.official_release_verdict_modified,
    )

    if (
        any(value is not True for value in positive_authority)
        or any(value is not False for value in negative_authority)
    ):
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            "VOiCES matched-control B5 suite authority boundary changed."
        )


def _audio_paths(
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
) -> dict[str, Path]:
    paths: dict[str, Path] = {}

    for binding in suite.cases:
        path = binding.media.path

        if not isinstance(path, Path) or not path.is_absolute():
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control execution paths must be absolute."
            )

        if binding.case.case_id in paths:
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control execution case identity repeated."
            )

        paths[binding.case.case_id] = path

    if (
        len(paths)
        != ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
        or len(set(paths.values())) != len(paths)
    ):
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            "VOiCES matched-control execution path population changed."
        )

    return paths


def _status_counts(
    attempts: tuple[ASRAdversarialCampaignAttempt, ...],
) -> dict[str, int]:
    observed = Counter(attempt.status for attempt in attempts)

    return {
        status.value: observed[status]
        for status in ASRAdversarialExecutionStatus
    }


def _completed_pair_count(
    *,
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
    attempts: tuple[ASRAdversarialCampaignAttempt, ...],
) -> int:
    completed_case_ids = {
        attempt.case_id
        for attempt in attempts
        if attempt.status == ASRAdversarialExecutionStatus.COMPLETED
    }

    case_ids_by_pair: dict[object, set[str]] = {}

    for binding in suite.cases:
        case_ids_by_pair.setdefault(
            binding.pair_key,
            set(),
        ).add(binding.case.case_id)

    if (
        len(case_ids_by_pair)
        != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
        or any(len(case_ids) != 2 for case_ids in case_ids_by_pair.values())
    ):
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            "VOiCES matched-control pair population changed."
        )

    return sum(
        case_ids <= completed_case_ids
        for case_ids in case_ids_by_pair.values()
    )


def _attempt_payload(
    *,
    attempt: ASRAdversarialCampaignAttempt,
    arm: str,
) -> dict[str, object]:
    definition = attempt.execution_definition
    evidence = attempt.execution_evidence

    return {
        "case_id": attempt.case_id,
        "arm": arm,
        "execution_id": attempt.execution_id,
        "status": attempt.status.value,
        "status_detail": attempt.status_detail,
        "execution_environment_sha256": (
            None
            if definition is None
            else definition.execution_environment_sha256
        ),
        "generated_transcript_sha256": (
            None
            if definition is None
            else definition.generated_transcript_sha256
        ),
        "execution_evidence_sha256": (
            None if evidence is None else evidence.sha256
        ),
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESMatchedControlCampaignBundle:
    """Reverified B6 campaign outcome bound to the exact B5 suite."""

    matched_control_suite_sha256: str
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle
    campaign: ASRAdversarialCampaignServiceResult

    development_evidence_only: bool = True
    matched_control_suite_reverified: bool = True
    campaign_evidence_reverified: bool = True
    partial_outcomes_preserved: bool = True
    paired_metrics_computed: bool = False
    qualification_threshold_applied: bool = False
    production_qualified: bool = False
    release_enforcement_eligible: bool = False
    official_release_verdict_modified: bool = False

    def __post_init__(self) -> None:
        _require_sha256(
            name="VOiCES matched-control B5 suite",
            value=self.matched_control_suite_sha256,
        )

        if not isinstance(
            self.suite,
            ASRAdversarialVOiCESMatchedControlSuiteBundle,
        ):
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control campaign requires the exact B5 suite."
            )

        _validate_suite_boundary(self.suite)

        if self.matched_control_suite_sha256 != self.suite.sha256:
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control B5 suite identity changed."
            )

        if not isinstance(
            self.campaign,
            ASRAdversarialCampaignServiceResult,
        ):
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control campaign result is invalid."
            )

        try:
            verified_suite = verify_asr_adversarial_evidence_v1(
                payload=self.suite.evidence.payload,
                expected_sha256=self.suite.evidence.sha256,
                definition=self.suite.definition,
            )
        except HveeContractError as error:
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control B5 suite evidence failed revalidation."
            ) from error

        definition = self.campaign.definition
        attempts = self.campaign.attempts
        completed_results = self.campaign.completed_results

        expected_case_ids = tuple(
            binding.case.case_id
            for binding in self.suite.cases
        )
        observed_case_ids = tuple(
            attempt.case_id
            for attempt in attempts
        )

        if (
            definition.suite_sha256 != verified_suite.sha256
            or attempts != definition.attempts
            or observed_case_ids != expected_case_ids
            or len(attempts)
            != ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
        ):
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control campaign coverage changed."
            )

        try:
            verified_campaign = verify_asr_adversarial_campaign_evidence_v1(
                payload=self.campaign.evidence.payload,
                expected_sha256=self.campaign.evidence.sha256,
                definition=definition,
                suite=self.suite.definition,
                suite_evidence=self.suite.evidence,
            )
        except HveeContractError as error:
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control campaign evidence failed revalidation."
            ) from error

        if verified_campaign != self.campaign.evidence:
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control campaign evidence identity changed."
            )

        completed_attempts = tuple(
            attempt
            for attempt in attempts
            if attempt.status == ASRAdversarialExecutionStatus.COMPLETED
        )

        if (
            not isinstance(completed_results, tuple)
            or any(
                not isinstance(result, ASRAdversarialExecutionServiceResult)
                for result in completed_results
            )
            or tuple(result.case_id for result in completed_results)
            != tuple(attempt.case_id for attempt in completed_attempts)
        ):
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES completed campaign results changed."
            )

        binding_by_case_id = {
            binding.case.case_id: binding
            for binding in self.suite.cases
        }

        for attempt, result in zip(
            completed_attempts,
            completed_results,
            strict=True,
        ):
            binding = binding_by_case_id[result.case_id]

            if (
                attempt.execution_definition != result.execution_definition
                or attempt.execution_evidence != result.execution_evidence
                or result.audio_asset_sha256
                != binding.case.audio_asset_sha256
                or result.environment.provider != definition.provider_key
                or result.environment.model_name != definition.model_key
                or result.execution_definition.provider_key
                != definition.provider_key
                or result.execution_definition.model_key
                != definition.model_key
            ):
                raise ASRAdversarialVOiCESMatchedControlCampaignError(
                    "VOiCES completed execution identity changed."
                )

            try:
                verified_execution = (
                    verify_asr_adversarial_execution_evidence_v1(
                        payload=result.execution_evidence.payload,
                        expected_sha256=result.execution_evidence.sha256,
                        definition=result.execution_definition,
                        suite=self.suite.definition,
                        suite_evidence=self.suite.evidence,
                    )
                )
            except HveeContractError as error:
                raise ASRAdversarialVOiCESMatchedControlCampaignError(
                    "VOiCES completed execution evidence failed revalidation."
                ) from error

            if verified_execution != result.execution_evidence:
                raise ASRAdversarialVOiCESMatchedControlCampaignError(
                    "VOiCES completed execution evidence identity changed."
                )

        positive_authority = (
            self.development_evidence_only,
            self.matched_control_suite_reverified,
            self.campaign_evidence_reverified,
            self.partial_outcomes_preserved,
        )
        negative_authority = (
            self.paired_metrics_computed,
            self.qualification_threshold_applied,
            self.production_qualified,
            self.release_enforcement_eligible,
            self.official_release_verdict_modified,
        )

        if (
            any(value is not True for value in positive_authority)
            or any(value is not False for value in negative_authority)
        ):
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control campaign authority boundary changed."
            )

        _completed_pair_count(
            suite=self.suite,
            attempts=attempts,
        )

    @property
    def status_counts(self) -> dict[str, int]:
        return _status_counts(self.campaign.attempts)

    @property
    def completed_pair_count(self) -> int:
        return _completed_pair_count(
            suite=self.suite,
            attempts=self.campaign.attempts,
        )

    @property
    def all_cases_completed(self) -> bool:
        return (
            self.status_counts[
                ASRAdversarialExecutionStatus.COMPLETED.value
            ]
            == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
            and self.completed_pair_count
            == ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
        )

    @property
    def payload(self) -> dict[str, object]:
        arm_by_case_id = {
            binding.case.case_id: binding.arm
            for binding in self.suite.cases
        }

        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_SCHEMA_VERSION
            ),
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_KEY,
                "version": (
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_VERSION
                ),
                "type": "reverified_matched_control_asr_campaign",
            },
            "upstream": {
                "matched_control_suite_sha256": (
                    self.matched_control_suite_sha256
                ),
                "adversarial_suite_evidence_sha256": (
                    self.suite.evidence.sha256
                ),
                "campaign_evidence_sha256": self.campaign.evidence.sha256,
            },
            "campaign": {
                "campaign_id": self.campaign.definition.campaign_id,
                "campaign_version": self.campaign.definition.campaign_version,
                "provider_key": self.campaign.definition.provider_key,
                "model_key": self.campaign.definition.model_key,
                "attempt_count": len(self.campaign.attempts),
                "status_counts": self.status_counts,
                "completed_pair_count": self.completed_pair_count,
                "all_cases_completed": self.all_cases_completed,
                "ordered_attempts": [
                    _attempt_payload(
                        attempt=attempt,
                        arm=arm_by_case_id[attempt.case_id],
                    )
                    for attempt in self.campaign.attempts
                ],
            },
            "evidence_boundary": {
                "development_evidence_only": True,
                "matched_control_suite_reverified": True,
                "campaign_evidence_reverified": True,
                "completed_execution_evidence_reverified": True,
                "partial_outcomes_preserved": True,
                "raw_audio_embedded": False,
                "absolute_audio_paths_embedded": False,
                "raw_generated_transcripts_embedded": False,
                "paired_metrics_computed": False,
                "qualification_threshold_applied": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json_bytes(self.payload)
        ).hexdigest()

    def require_complete_for_paired_metrics(
        self,
    ) -> tuple[ASRAdversarialExecutionServiceResult, ...]:
        if not self.all_cases_completed:
            raise ASRAdversarialVOiCESMatchedControlCampaignError(
                "VOiCES matched-control paired metrics require all 32 cases "
                "and all 16 babble/control pairs to complete."
            )

        return self.campaign.completed_results


def execute_asr_adversarial_voices_babble_matched_control_campaign_v1(
    *,
    campaign_id: str,
    campaign_version: str,
    requested_model_name: str,
    provider: ASRProvider,
    terminology: ASRAdversarialTerminologyBinding,
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
    stop_event: ASRAdversarialCampaignStopEvent | None = None,
    case_executor: ASRAdversarialCampaignCaseExecutor = (
        execute_asr_adversarial_case
    ),
) -> ASRAdversarialVOiCESMatchedControlCampaignBundle:
    """Execute B5 through the existing campaign service and seal B6."""

    if not isinstance(
        suite,
        ASRAdversarialVOiCESMatchedControlSuiteBundle,
    ):
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            "VOiCES matched-control execution requires the exact B5 suite."
        )

    _validate_suite_boundary(suite)

    if (
        not isinstance(terminology, ASRAdversarialTerminologyBinding)
        or terminology.state
        != ASRAdversarialTerminologyState.NOT_CONFIGURED
        or terminology.profile is not None
    ):
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            "VOiCES matched-control semantic-control cases require "
            "terminology state not_configured."
        )

    provider_key = _provider_key(provider)
    model_key = _require_non_empty_trimmed_text(
        name="VOiCES matched-control requested model",
        value=requested_model_name,
    )
    audio_paths = _audio_paths(suite)

    try:
        campaign = execute_asr_adversarial_campaign(
            campaign_id=campaign_id,
            campaign_version=campaign_version,
            audio_paths=audio_paths,
            requested_model_name=model_key,
            provider=provider,
            terminology=terminology,
            suite=suite.definition,
            suite_evidence=suite.evidence,
            stop_event=stop_event,
            case_executor=case_executor,
        )
    except (ASRAdversarialCampaignServiceError, HveeContractError) as error:
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            "VOiCES matched-control campaign execution failed closed."
        ) from error

    if (
        campaign.definition.provider_key != provider_key
        or campaign.definition.model_key != model_key
        or campaign.definition.campaign_id != campaign_id
        or campaign.definition.campaign_version != campaign_version
    ):
        raise ASRAdversarialVOiCESMatchedControlCampaignError(
            "VOiCES matched-control campaign identity changed."
        )

    return ASRAdversarialVOiCESMatchedControlCampaignBundle(
        matched_control_suite_sha256=suite.sha256,
        suite=suite,
        campaign=campaign,
    )
