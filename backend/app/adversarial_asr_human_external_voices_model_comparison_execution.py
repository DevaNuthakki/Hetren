"""Execute two VOiCES campaigns and preserve comparison readiness.

This I4e-B9 orchestration layer runs a baseline and candidate ASR system on
the exact same frozen B5 suite.  Each run is sealed independently through
B6, complete runs receive B7 normalized metrics, and two complete distinct
model runs receive the B8 matched comparison.

Partial campaign outcomes remain visible and hash-bound.  No transcript or
audio content is embedded in the B9 payload.  This layer does not apply a
threshold, declare a winner, qualify production use, persist state, or alter
release authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from enum import StrEnum

from app.adversarial_asr_human_external_voices_matched_control_campaign_service import (
    ASRAdversarialVOiCESMatchedControlCampaignBundle,
    ASRAdversarialVOiCESMatchedControlCampaignError,
    execute_asr_adversarial_voices_babble_matched_control_campaign_v1,
)
from app.adversarial_asr_human_external_voices_matched_control_metrics import (
    ASRAdversarialVOiCESMatchedControlMetricsBundle,
    ASRAdversarialVOiCESMatchedControlMetricsError,
    build_asr_adversarial_voices_babble_matched_control_metrics_v1,
)
from app.adversarial_asr_human_external_voices_matched_control_suite_projection import (
    ASRAdversarialVOiCESMatchedControlSuiteBundle,
)
from app.adversarial_asr_human_external_voices_model_comparison import (
    ASRAdversarialVOiCESModelComparisonBundle,
    ASRAdversarialVOiCESModelComparisonError,
    build_asr_adversarial_voices_model_comparison_v1,
)
from app.speech.base import ASRProvider
from hvee.packs.asr import ASRAdversarialTerminologyBinding


ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_KEY = (
    "hetren.asr.adversarial-human-external-"
    "voices-babble-matched-control-model-comparison-execution"
)


class ASRAdversarialVOiCESModelComparisonExecutionError(ValueError):
    """Raised when two model executions cannot form trusted B9 evidence."""


class ASRAdversarialVOiCESModelComparisonExecutionStatus(StrEnum):
    COMPLETED = "completed"
    BASELINE_INCOMPLETE = "baseline_incomplete"
    CANDIDATE_INCOMPLETE = "candidate_incomplete"
    BOTH_INCOMPLETE = "both_incomplete"


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            f"{name} must be a lowercase SHA-256."
        )
    return value


def _require_text(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            f"{name} must be non-empty trimmed text."
        )
    return value


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            "VOiCES model comparison execution must be deterministic JSON."
        ) from error


def _campaign_identity(
    value: ASRAdversarialVOiCESMatchedControlCampaignBundle,
) -> tuple[str, str]:
    definition = value.campaign.definition
    return (definition.provider_key, definition.model_key)


def _execution_identity(
    *,
    provider: ASRProvider,
    model_name: str,
) -> tuple[str, str]:
    provider_key = _require_text(
        name="VOiCES ASR provider",
        value=getattr(provider, "provider_name", None),
    )
    model_key = _require_text(
        name="VOiCES requested ASR model",
        value=model_name,
    )
    return (provider_key, model_key)


def _reverify_campaign(
    *,
    role: str,
    value: object,
) -> ASRAdversarialVOiCESMatchedControlCampaignBundle:
    if not isinstance(value, ASRAdversarialVOiCESMatchedControlCampaignBundle):
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            f"VOiCES {role} requires the exact B6 campaign bundle."
        )
    try:
        reverified = ASRAdversarialVOiCESMatchedControlCampaignBundle(
            matched_control_suite_sha256=value.matched_control_suite_sha256,
            suite=value.suite,
            campaign=value.campaign,
        )
    except (ASRAdversarialVOiCESMatchedControlCampaignError, ValueError) as error:
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            f"VOiCES {role} B6 campaign failed revalidation."
        ) from error
    if reverified.sha256 != value.sha256:
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            f"VOiCES {role} B6 campaign identity changed."
        )
    return reverified


def _reverify_metrics(
    *,
    role: str,
    value: object,
) -> ASRAdversarialVOiCESMatchedControlMetricsBundle:
    if not isinstance(value, ASRAdversarialVOiCESMatchedControlMetricsBundle):
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            f"VOiCES complete {role} requires the exact B7 metrics bundle."
        )
    try:
        reverified = ASRAdversarialVOiCESMatchedControlMetricsBundle(
            matched_control_campaign_sha256=(
                value.matched_control_campaign_sha256
            ),
            campaign=value.campaign,
            cases=value.cases,
            pairs=value.pairs,
        )
    except (ASRAdversarialVOiCESMatchedControlMetricsError, ValueError) as error:
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            f"VOiCES {role} B7 metrics failed revalidation."
        ) from error
    if reverified.sha256 != value.sha256:
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            f"VOiCES {role} B7 metrics identity changed."
        )
    return reverified


def _reverify_comparison(
    value: object,
) -> ASRAdversarialVOiCESModelComparisonBundle:
    if not isinstance(value, ASRAdversarialVOiCESModelComparisonBundle):
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            "VOiCES two complete campaigns require the exact B8 comparison."
        )
    try:
        reverified = ASRAdversarialVOiCESModelComparisonBundle(
            baseline_metrics_sha256=value.baseline_metrics_sha256,
            candidate_metrics_sha256=value.candidate_metrics_sha256,
            baseline=value.baseline,
            candidate=value.candidate,
            cases=value.cases,
            pairs=value.pairs,
        )
    except (ASRAdversarialVOiCESModelComparisonError, ValueError) as error:
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            "VOiCES B8 model comparison failed revalidation."
        ) from error
    if reverified.sha256 != value.sha256:
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            "VOiCES B8 model comparison identity changed."
        )
    return reverified


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESModelComparisonExecutionBundle:
    """B9 outcome preserving complete and partial two-model evidence."""

    matched_control_suite_sha256: str
    baseline_campaign: ASRAdversarialVOiCESMatchedControlCampaignBundle
    candidate_campaign: ASRAdversarialVOiCESMatchedControlCampaignBundle
    baseline_metrics: (
        ASRAdversarialVOiCESMatchedControlMetricsBundle | None
    )
    candidate_metrics: (
        ASRAdversarialVOiCESMatchedControlMetricsBundle | None
    )
    comparison: ASRAdversarialVOiCESModelComparisonBundle | None

    development_evidence_only: bool = True
    both_campaigns_reverified: bool = True
    partial_outcomes_preserved: bool = True
    distinct_model_identities_verified: bool = True
    complete_metrics_reverified: bool = True
    comparison_reverified_when_complete: bool = True
    qualification_threshold_applied: bool = False
    statistical_significance_claimed: bool = False
    model_winner_declared: bool = False
    production_qualified: bool = False
    release_enforcement_eligible: bool = False
    official_release_verdict_modified: bool = False

    def __post_init__(self) -> None:
        _require_sha256(
            name="VOiCES B9 matched-control suite",
            value=self.matched_control_suite_sha256,
        )
        baseline = _reverify_campaign(
            role="baseline",
            value=self.baseline_campaign,
        )
        candidate = _reverify_campaign(
            role="candidate",
            value=self.candidate_campaign,
        )

        if (
            self.matched_control_suite_sha256
            != baseline.matched_control_suite_sha256
            or self.matched_control_suite_sha256
            != candidate.matched_control_suite_sha256
            or baseline.suite.sha256 != candidate.suite.sha256
            or baseline.suite.evidence.sha256
            != candidate.suite.evidence.sha256
        ):
            raise ASRAdversarialVOiCESModelComparisonExecutionError(
                "VOiCES B9 requires the exact same frozen suite."
            )

        if _campaign_identity(baseline) == _campaign_identity(candidate):
            raise ASRAdversarialVOiCESModelComparisonExecutionError(
                "VOiCES B9 requires distinct provider/model identities."
            )

        baseline_complete = baseline.all_cases_completed
        candidate_complete = candidate.all_cases_completed

        if baseline_complete:
            baseline_metrics = _reverify_metrics(
                role="baseline",
                value=self.baseline_metrics,
            )
            if (
                baseline_metrics.campaign.sha256 != baseline.sha256
                or baseline_metrics.matched_control_campaign_sha256
                != baseline.sha256
            ):
                raise ASRAdversarialVOiCESModelComparisonExecutionError(
                    "VOiCES baseline B7 metrics bind the wrong campaign."
                )
        elif self.baseline_metrics is not None:
            raise ASRAdversarialVOiCESModelComparisonExecutionError(
                "VOiCES incomplete baseline cannot contain B7 metrics."
            )

        if candidate_complete:
            candidate_metrics = _reverify_metrics(
                role="candidate",
                value=self.candidate_metrics,
            )
            if (
                candidate_metrics.campaign.sha256 != candidate.sha256
                or candidate_metrics.matched_control_campaign_sha256
                != candidate.sha256
            ):
                raise ASRAdversarialVOiCESModelComparisonExecutionError(
                    "VOiCES candidate B7 metrics bind the wrong campaign."
                )
        elif self.candidate_metrics is not None:
            raise ASRAdversarialVOiCESModelComparisonExecutionError(
                "VOiCES incomplete candidate cannot contain B7 metrics."
            )

        if baseline_complete and candidate_complete:
            comparison = _reverify_comparison(self.comparison)
            if (
                comparison.baseline_metrics_sha256
                != self.baseline_metrics.sha256
                or comparison.candidate_metrics_sha256
                != self.candidate_metrics.sha256
            ):
                raise ASRAdversarialVOiCESModelComparisonExecutionError(
                    "VOiCES B8 comparison binds the wrong B7 metrics."
                )
        elif self.comparison is not None:
            raise ASRAdversarialVOiCESModelComparisonExecutionError(
                "VOiCES partial campaigns cannot contain a B8 comparison."
            )

        positive_authority = (
            self.development_evidence_only,
            self.both_campaigns_reverified,
            self.partial_outcomes_preserved,
            self.distinct_model_identities_verified,
            self.complete_metrics_reverified,
            self.comparison_reverified_when_complete,
        )
        negative_authority = (
            self.qualification_threshold_applied,
            self.statistical_significance_claimed,
            self.model_winner_declared,
            self.production_qualified,
            self.release_enforcement_eligible,
            self.official_release_verdict_modified,
        )
        if (
            any(value is not True for value in positive_authority)
            or any(value is not False for value in negative_authority)
        ):
            raise ASRAdversarialVOiCESModelComparisonExecutionError(
                "VOiCES B9 authority boundary changed."
            )

    @property
    def status(self) -> ASRAdversarialVOiCESModelComparisonExecutionStatus:
        baseline_complete = self.baseline_campaign.all_cases_completed
        candidate_complete = self.candidate_campaign.all_cases_completed
        if baseline_complete and candidate_complete:
            return ASRAdversarialVOiCESModelComparisonExecutionStatus.COMPLETED
        if not baseline_complete and not candidate_complete:
            return (
                ASRAdversarialVOiCESModelComparisonExecutionStatus.BOTH_INCOMPLETE
            )
        if not baseline_complete:
            return (
                ASRAdversarialVOiCESModelComparisonExecutionStatus.BASELINE_INCOMPLETE
            )
        return (
            ASRAdversarialVOiCESModelComparisonExecutionStatus.CANDIDATE_INCOMPLETE
        )

    @property
    def payload(self) -> dict[str, object]:
        baseline_definition = self.baseline_campaign.campaign.definition
        candidate_definition = self.candidate_campaign.campaign.definition
        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_SCHEMA_VERSION
            ),
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_KEY,
                "version": (
                    ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_VERSION
                ),
                "type": "two_model_matched_control_execution",
            },
            "upstream": {
                "matched_control_suite_sha256": (
                    self.matched_control_suite_sha256
                ),
                "adversarial_suite_evidence_sha256": (
                    self.baseline_campaign.suite.evidence.sha256
                ),
            },
            "status": self.status.value,
            "baseline": {
                "campaign_id": baseline_definition.campaign_id,
                "campaign_version": baseline_definition.campaign_version,
                "provider_key": baseline_definition.provider_key,
                "model_key": baseline_definition.model_key,
                "campaign_sha256": self.baseline_campaign.sha256,
                "campaign_evidence_sha256": (
                    self.baseline_campaign.campaign.evidence.sha256
                ),
                "status_counts": self.baseline_campaign.status_counts,
                "completed_pair_count": (
                    self.baseline_campaign.completed_pair_count
                ),
                "metrics_sha256": (
                    None
                    if self.baseline_metrics is None
                    else self.baseline_metrics.sha256
                ),
            },
            "candidate": {
                "campaign_id": candidate_definition.campaign_id,
                "campaign_version": candidate_definition.campaign_version,
                "provider_key": candidate_definition.provider_key,
                "model_key": candidate_definition.model_key,
                "campaign_sha256": self.candidate_campaign.sha256,
                "campaign_evidence_sha256": (
                    self.candidate_campaign.campaign.evidence.sha256
                ),
                "status_counts": self.candidate_campaign.status_counts,
                "completed_pair_count": (
                    self.candidate_campaign.completed_pair_count
                ),
                "metrics_sha256": (
                    None
                    if self.candidate_metrics is None
                    else self.candidate_metrics.sha256
                ),
            },
            "comparison_sha256": (
                None if self.comparison is None else self.comparison.sha256
            ),
            "evidence_boundary": {
                "development_evidence_only": True,
                "both_campaigns_reverified": True,
                "partial_outcomes_preserved": True,
                "distinct_model_identities_verified": True,
                "complete_metrics_reverified": True,
                "comparison_reverified_when_complete": True,
                "raw_audio_embedded": False,
                "absolute_audio_paths_embedded": False,
                "raw_reference_transcripts_embedded": False,
                "raw_generated_transcripts_embedded": False,
                "qualification_threshold_applied": False,
                "statistical_significance_claimed": False,
                "model_winner_declared": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()

    def require_complete_comparison(
        self,
    ) -> ASRAdversarialVOiCESModelComparisonBundle:
        if (
            self.status
            != ASRAdversarialVOiCESModelComparisonExecutionStatus.COMPLETED
            or self.comparison is None
        ):
            raise ASRAdversarialVOiCESModelComparisonExecutionError(
                "VOiCES B9 requires both 32-case campaigns before comparison."
            )
        return self.comparison


def execute_asr_adversarial_voices_model_comparison_v1(
    *,
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
    terminology: ASRAdversarialTerminologyBinding,
    baseline_campaign_id: str,
    baseline_campaign_version: str,
    baseline_model_name: str,
    baseline_provider: ASRProvider,
    candidate_campaign_id: str,
    candidate_campaign_version: str,
    candidate_model_name: str,
    candidate_provider: ASRProvider,
) -> ASRAdversarialVOiCESModelComparisonExecutionBundle:
    """Execute both models and build every evidence layer that is supported."""

    if not isinstance(suite, ASRAdversarialVOiCESMatchedControlSuiteBundle):
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            "VOiCES B9 requires the exact B5 matched-control suite."
        )
    if not isinstance(terminology, ASRAdversarialTerminologyBinding):
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            "VOiCES B9 terminology binding is invalid."
        )

    baseline_identity = _execution_identity(
        provider=baseline_provider,
        model_name=baseline_model_name,
    )
    candidate_identity = _execution_identity(
        provider=candidate_provider,
        model_name=candidate_model_name,
    )
    if baseline_identity == candidate_identity:
        raise ASRAdversarialVOiCESModelComparisonExecutionError(
            "VOiCES B9 requires distinct provider/model identities."
        )

    baseline_campaign = (
        execute_asr_adversarial_voices_babble_matched_control_campaign_v1(
            campaign_id=baseline_campaign_id,
            campaign_version=baseline_campaign_version,
            requested_model_name=baseline_model_name,
            provider=baseline_provider,
            terminology=terminology,
            suite=suite,
        )
    )
    candidate_campaign = (
        execute_asr_adversarial_voices_babble_matched_control_campaign_v1(
            campaign_id=candidate_campaign_id,
            campaign_version=candidate_campaign_version,
            requested_model_name=candidate_model_name,
            provider=candidate_provider,
            terminology=terminology,
            suite=suite,
        )
    )

    baseline_metrics = (
        build_asr_adversarial_voices_babble_matched_control_metrics_v1(
            baseline_campaign
        )
        if baseline_campaign.all_cases_completed
        else None
    )
    candidate_metrics = (
        build_asr_adversarial_voices_babble_matched_control_metrics_v1(
            candidate_campaign
        )
        if candidate_campaign.all_cases_completed
        else None
    )
    comparison = (
        build_asr_adversarial_voices_model_comparison_v1(
            baseline=baseline_metrics,
            candidate=candidate_metrics,
        )
        if baseline_metrics is not None and candidate_metrics is not None
        else None
    )

    return ASRAdversarialVOiCESModelComparisonExecutionBundle(
        matched_control_suite_sha256=suite.sha256,
        baseline_campaign=baseline_campaign,
        candidate_campaign=candidate_campaign,
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        comparison=comparison,
    )
