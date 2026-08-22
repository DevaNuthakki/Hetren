from __future__ import annotations

from dataclasses import FrozenInstanceError
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from app.adversarial_asr_human_external_voices_matched_control_projection import (
    project_asr_adversarial_voices_babble_matched_control_v1,
)
from app.adversarial_asr_human_external_voices_matched_control_suite_projection import (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
    ASRAdversarialVOiCESMatchedControlSuiteBundle,
    project_asr_adversarial_voices_babble_matched_control_suite_v1,
)
from app.adversarial_asr_human_external_voices_materialization_service import (
    ASRAdversarialVOiCESMaterializedCaptureCondition,
    ASRAdversarialVOiCESMaterializedEvidence,
    ASRAdversarialVOiCESMaterializedMedia,
)
from app.adversarial_asr_human_external_voices_model_comparison_execution import (
    ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_KEY,
    ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_VERSION,
    ASRAdversarialVOiCESModelComparisonExecutionBundle,
    ASRAdversarialVOiCESModelComparisonExecutionError,
    ASRAdversarialVOiCESModelComparisonExecutionStatus,
    execute_asr_adversarial_voices_model_comparison_v1,
)
from app.speech import TranscriptionError
from app.speech import TranscriptionResult
from hvee.packs.asr import (
    ASRAdversarialExecutionStatus,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
)


PROVIDER_KEY = "deterministic_b9"
BASELINE_MODEL_KEY = "baseline-model-v1"
CANDIDATE_MODEL_KEY = "candidate-model-v2"
BASELINE_CAMPAIGN_ID = "voices-b9-baseline"
CANDIDATE_CAMPAIGN_ID = "voices-b9-candidate"
CAMPAIGN_VERSION = "1.0.0"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _audio_bytes(relative_path: str) -> bytes:
    return hashlib.sha256(relative_path.encode("utf-8")).digest() * 1_000


def _write_audio(
    *,
    root: Path,
    relative_path: str,
) -> tuple[Path, bytes]:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _audio_bytes(relative_path)
    path.write_bytes(content)
    return path.resolve(), content


def _source_media(
    *,
    root: Path,
    source_key: tuple[int, int, int],
) -> ASRAdversarialVOiCESMaterializedMedia:
    source_id = "-".join(str(value) for value in source_key)
    relative_path = f"source/{source_id}.wav"
    path, content = _write_audio(root=root, relative_path=relative_path)
    return ASRAdversarialVOiCESMaterializedMedia(
        relative_path=relative_path,
        path=path,
        sha256=_sha256_bytes(content),
        byte_length=len(content),
        kind="source",
        source_key=source_key,
        codec_name="pcm_s16le",
        sample_rate_hz=16_000,
        channel_count=1,
        bits_per_sample=16,
        sample_width_bytes=2,
        sample_count=16_000,
        duration_seconds="1.000000",
    )


def _capture_media(
    *,
    root: Path,
    source_key: tuple[int, int, int],
    room: str,
    distractor: str,
    microphone_id: int,
) -> ASRAdversarialVOiCESMaterializedMedia:
    source_id = "-".join(str(value) for value in source_key)
    relative_path = (
        "capture/"
        f"{source_id}-{room}-{distractor}-mic{microphone_id}.wav"
    )
    path, content = _write_audio(root=root, relative_path=relative_path)
    return ASRAdversarialVOiCESMaterializedMedia(
        relative_path=relative_path,
        path=path,
        sha256=_sha256_bytes(content),
        byte_length=len(content),
        kind="capture",
        source_key=source_key,
        codec_name="pcm_s16le",
        sample_rate_hz=16_000,
        channel_count=1,
        bits_per_sample=16,
        sample_width_bytes=2,
        sample_count=16_000,
        duration_seconds="1.000000",
        capture_condition=(
            ASRAdversarialVOiCESMaterializedCaptureCondition(
                angle_degrees=10,
                room=room,
                distractor=distractor,
                microphone_id=microphone_id,
            )
        ),
    )


def _materialized_evidence(
    root: Path,
) -> ASRAdversarialVOiCESMaterializedEvidence:
    media = [
        _source_media(root=root, source_key=source_key)
        for source_key in ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
    ]
    media.extend(
        _capture_media(
            root=root,
            source_key=source_key,
            room=room,
            distractor=distractor,
            microphone_id=microphone_id,
        )
        for source_key in ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
        for room in ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS
        for distractor in ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS
        for microphone_id in ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS
    )
    return ASRAdversarialVOiCESMaterializedEvidence(
        controlled_contract_sha256=ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
        identity_chain_sha256=_sha256_text("identity-chain"),
        selection_sha256=_sha256_text("selection"),
        materialization_manifest_sha256=(
            _sha256_text("materialization-manifest")
        ),
        media_report_sha256=_sha256_text("media-report"),
        observation_sha256=_sha256_text("observation"),
        rights_manifest_sha256=_sha256_text("rights-manifest"),
        media=tuple(media),
    )


def _suite(root: Path) -> ASRAdversarialVOiCESMatchedControlSuiteBundle:
    projection = project_asr_adversarial_voices_babble_matched_control_v1(
        _materialized_evidence(root)
    )
    return project_asr_adversarial_voices_babble_matched_control_suite_v1(
        projection
    )


def _terminology() -> ASRAdversarialTerminologyBinding:
    return ASRAdversarialTerminologyBinding(
        state=ASRAdversarialTerminologyState.NOT_CONFIGURED,
    )


def _remove_first_word(value: str) -> str:
    return " ".join(value.split()[1:])


class _ExecutionProvider:
    provider_name = PROVIDER_KEY

    def __init__(
        self,
        *,
        suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
        error_arm: str | None,
        failed_case_id: str | None = None,
    ) -> None:
        self.generated = {
            binding.media.path: (
                _remove_first_word(binding.case.reference_transcript)
                if binding.arm == error_arm
                else binding.case.reference_transcript
            )
            for binding in suite.cases
        }
        self.failed_path = (
            None
            if failed_case_id is None
            else next(
                binding.media.path
                for binding in suite.cases
                if binding.case.case_id == failed_case_id
            )
        )
        self.calls = 0

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ) -> TranscriptionResult:
        self.calls += 1
        path = Path(audio_path)
        if path == self.failed_path:
            raise TranscriptionError("deterministic B9 failure")
        return TranscriptionResult(
            transcript=self.generated[path],
            provider=self.provider_name,
            model_name=model_name or "missing-model",
            device="cpu",
            compute_type="test",
        )


def _execute(
    *,
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
    baseline_failed_case_id: str | None = None,
    candidate_failed_case_id: str | None = None,
) -> ASRAdversarialVOiCESModelComparisonExecutionBundle:
    return execute_asr_adversarial_voices_model_comparison_v1(
        suite=suite,
        terminology=_terminology(),
        baseline_campaign_id=BASELINE_CAMPAIGN_ID,
        baseline_campaign_version=CAMPAIGN_VERSION,
        baseline_model_name=BASELINE_MODEL_KEY,
        baseline_provider=_ExecutionProvider(
            suite=suite,
            error_arm=ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
            failed_case_id=baseline_failed_case_id,
        ),
        candidate_campaign_id=CANDIDATE_CAMPAIGN_ID,
        candidate_campaign_version=CAMPAIGN_VERSION,
        candidate_model_name=CANDIDATE_MODEL_KEY,
        candidate_provider=_ExecutionProvider(
            suite=suite,
            error_arm=None,
            failed_case_id=candidate_failed_case_id,
        ),
    )


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    return _suite(tmp_path_factory.mktemp("b9-comparison-execution"))


@pytest.fixture(scope="module")
def complete(suite):
    return _execute(suite=suite)


@pytest.fixture(scope="module")
def first_case_id(suite):
    return suite.cases[0].case.case_id


@pytest.fixture(scope="module")
def baseline_incomplete(suite, first_case_id):
    return _execute(
        suite=suite,
        baseline_failed_case_id=first_case_id,
    )


@pytest.fixture(scope="module")
def candidate_incomplete(suite, first_case_id):
    return _execute(
        suite=suite,
        candidate_failed_case_id=first_case_id,
    )


@pytest.fixture(scope="module")
def both_incomplete(suite, first_case_id):
    return _execute(
        suite=suite,
        baseline_failed_case_id=first_case_id,
        candidate_failed_case_id=first_case_id,
    )


def test_constants_are_exact():
    assert ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_EXECUTION_KEY == (
        "hetren.asr.adversarial-human-external-"
        "voices-babble-matched-control-model-comparison-execution"
    )


def test_complete_execution_builds_every_evidence_layer(complete):
    assert complete.baseline_campaign.all_cases_completed is True
    assert complete.candidate_campaign.all_cases_completed is True
    assert complete.baseline_metrics is not None
    assert complete.candidate_metrics is not None
    assert complete.comparison is not None


def test_complete_status_is_exact(complete):
    assert complete.status == (
        ASRAdversarialVOiCESModelComparisonExecutionStatus.COMPLETED
    )
    assert complete.payload["status"] == "completed"


def test_complete_binds_same_suite_to_both_campaigns(complete):
    assert complete.matched_control_suite_sha256 == (
        complete.baseline_campaign.matched_control_suite_sha256
    )
    assert complete.matched_control_suite_sha256 == (
        complete.candidate_campaign.matched_control_suite_sha256
    )
    assert complete.baseline_campaign.suite.sha256 == (
        complete.candidate_campaign.suite.sha256
    )


def test_complete_binds_distinct_models(complete):
    baseline = complete.baseline_campaign.campaign.definition
    candidate = complete.candidate_campaign.campaign.definition
    assert baseline.provider_key == candidate.provider_key == PROVIDER_KEY
    assert baseline.model_key == BASELINE_MODEL_KEY
    assert candidate.model_key == CANDIDATE_MODEL_KEY


def test_complete_metrics_bind_their_own_campaigns(complete):
    assert complete.baseline_metrics.matched_control_campaign_sha256 == (
        complete.baseline_campaign.sha256
    )
    assert complete.candidate_metrics.matched_control_campaign_sha256 == (
        complete.candidate_campaign.sha256
    )


def test_complete_comparison_binds_both_metrics(complete):
    assert complete.comparison.baseline_metrics_sha256 == (
        complete.baseline_metrics.sha256
    )
    assert complete.comparison.candidate_metrics_sha256 == (
        complete.candidate_metrics.sha256
    )
    assert complete.require_complete_comparison() == complete.comparison


def test_complete_executes_exact_32_cases_per_model(complete):
    assert len(complete.baseline_campaign.campaign.attempts) == 32
    assert len(complete.candidate_campaign.campaign.attempts) == 32
    assert complete.baseline_campaign.completed_pair_count == 16
    assert complete.candidate_campaign.completed_pair_count == 16


def test_baseline_incomplete_preserves_both_campaigns(baseline_incomplete):
    assert baseline_incomplete.status == (
        ASRAdversarialVOiCESModelComparisonExecutionStatus.BASELINE_INCOMPLETE
    )
    assert baseline_incomplete.baseline_metrics is None
    assert baseline_incomplete.candidate_metrics is not None
    assert baseline_incomplete.comparison is None
    assert baseline_incomplete.baseline_campaign.all_cases_completed is False
    assert baseline_incomplete.candidate_campaign.all_cases_completed is True


def test_candidate_incomplete_preserves_both_campaigns(candidate_incomplete):
    assert candidate_incomplete.status == (
        ASRAdversarialVOiCESModelComparisonExecutionStatus.CANDIDATE_INCOMPLETE
    )
    assert candidate_incomplete.baseline_metrics is not None
    assert candidate_incomplete.candidate_metrics is None
    assert candidate_incomplete.comparison is None
    assert candidate_incomplete.baseline_campaign.all_cases_completed is True
    assert candidate_incomplete.candidate_campaign.all_cases_completed is False


def test_both_incomplete_preserves_both_campaigns(both_incomplete):
    assert both_incomplete.status == (
        ASRAdversarialVOiCESModelComparisonExecutionStatus.BOTH_INCOMPLETE
    )
    assert both_incomplete.baseline_metrics is None
    assert both_incomplete.candidate_metrics is None
    assert both_incomplete.comparison is None
    assert both_incomplete.baseline_campaign.all_cases_completed is False
    assert both_incomplete.candidate_campaign.all_cases_completed is False


def _assert_partial_retains_failed_attempt_evidence(value):
    campaigns = (
        value.baseline_campaign,
        value.candidate_campaign,
    )
    assert any(
        attempt.status == ASRAdversarialExecutionStatus.FAILED
        for campaign in campaigns
        for attempt in campaign.campaign.attempts
    )
    assert all(campaign.campaign.evidence.sha256 for campaign in campaigns)


def test_baseline_partial_retains_failed_attempt_evidence(baseline_incomplete):
    _assert_partial_retains_failed_attempt_evidence(baseline_incomplete)


def test_candidate_partial_retains_failed_attempt_evidence(candidate_incomplete):
    _assert_partial_retains_failed_attempt_evidence(candidate_incomplete)


def test_both_partial_retains_failed_attempt_evidence(both_incomplete):
    _assert_partial_retains_failed_attempt_evidence(both_incomplete)


def _assert_partial_require_complete_fails_closed(bundle):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="requires both 32-case campaigns",
    ):
        bundle.require_complete_comparison()


def test_baseline_partial_require_complete_fails_closed(baseline_incomplete):
    _assert_partial_require_complete_fails_closed(baseline_incomplete)


def test_candidate_partial_require_complete_fails_closed(candidate_incomplete):
    _assert_partial_require_complete_fails_closed(candidate_incomplete)


def test_both_partial_require_complete_fails_closed(both_incomplete):
    _assert_partial_require_complete_fails_closed(both_incomplete)


def test_partial_payload_uses_null_for_unsupported_layers(baseline_incomplete):
    payload = baseline_incomplete.payload
    assert payload["baseline"]["metrics_sha256"] is None
    assert payload["candidate"]["metrics_sha256"] is not None
    assert payload["comparison_sha256"] is None


def test_preflight_rejects_identical_model_before_transcription(suite):
    baseline_provider = _ExecutionProvider(
        suite=suite,
        error_arm=None,
    )
    candidate_provider = _ExecutionProvider(
        suite=suite,
        error_arm=None,
    )
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="distinct provider/model",
    ):
        execute_asr_adversarial_voices_model_comparison_v1(
            suite=suite,
            terminology=_terminology(),
            baseline_campaign_id=BASELINE_CAMPAIGN_ID,
            baseline_campaign_version=CAMPAIGN_VERSION,
            baseline_model_name=BASELINE_MODEL_KEY,
            baseline_provider=baseline_provider,
            candidate_campaign_id=CANDIDATE_CAMPAIGN_ID,
            candidate_campaign_version=CAMPAIGN_VERSION,
            candidate_model_name=BASELINE_MODEL_KEY,
            candidate_provider=candidate_provider,
        )
    assert baseline_provider.calls == 0
    assert candidate_provider.calls == 0


@pytest.mark.parametrize(
    ("argument", "value", "message"),
    [
        ("suite", object(), "exact B5"),
        ("terminology", object(), "terminology binding"),
    ],
)
def test_preflight_rejects_invalid_contract_input(
    suite,
    argument,
    value,
    message,
):
    arguments = {
        "suite": suite,
        "terminology": _terminology(),
        "baseline_campaign_id": BASELINE_CAMPAIGN_ID,
        "baseline_campaign_version": CAMPAIGN_VERSION,
        "baseline_model_name": BASELINE_MODEL_KEY,
        "baseline_provider": _ExecutionProvider(suite=suite, error_arm=None),
        "candidate_campaign_id": CANDIDATE_CAMPAIGN_ID,
        "candidate_campaign_version": CAMPAIGN_VERSION,
        "candidate_model_name": CANDIDATE_MODEL_KEY,
        "candidate_provider": _ExecutionProvider(suite=suite, error_arm=None),
    }
    arguments[argument] = value
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match=message,
    ):
        execute_asr_adversarial_voices_model_comparison_v1(**arguments)


def test_payload_binds_complete_evidence_hashes(complete):
    payload = complete.payload
    assert payload["baseline"]["campaign_sha256"] == (
        complete.baseline_campaign.sha256
    )
    assert payload["candidate"]["campaign_sha256"] == (
        complete.candidate_campaign.sha256
    )
    assert payload["comparison_sha256"] == complete.comparison.sha256


def test_payload_contains_no_raw_transcripts_or_paths(complete):
    encoded = json.dumps(complete.payload, sort_keys=True)
    for campaign in (
        complete.baseline_campaign,
        complete.candidate_campaign,
    ):
        for binding in campaign.suite.cases:
            assert binding.case.reference_transcript not in encoded
            assert str(binding.media.path) not in encoded
        for result in campaign.campaign.completed_results:
            assert result.generated_transcript not in encoded


def test_hash_is_canonical_and_reproducible(complete):
    rebuilt = ASRAdversarialVOiCESModelComparisonExecutionBundle(
        matched_control_suite_sha256=complete.matched_control_suite_sha256,
        baseline_campaign=complete.baseline_campaign,
        candidate_campaign=complete.candidate_campaign,
        baseline_metrics=complete.baseline_metrics,
        candidate_metrics=complete.candidate_metrics,
        comparison=complete.comparison,
    )
    assert rebuilt == complete
    assert rebuilt.payload == complete.payload
    assert rebuilt.sha256 == complete.sha256
    assert len(complete.sha256) == 64


def test_rejects_changed_suite_commitment(complete):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="exact same frozen suite",
    ):
        replace(complete, matched_control_suite_sha256="0" * 64)


def test_rejects_complete_campaign_without_metrics(complete):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="complete baseline requires the exact B7",
    ):
        replace(complete, baseline_metrics=None)


def test_rejects_complete_campaign_without_comparison(complete):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="two complete campaigns require the exact B8",
    ):
        replace(complete, comparison=None)


def test_rejects_metrics_bound_to_wrong_campaign(complete):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="baseline B7 metrics bind the wrong campaign",
    ):
        replace(complete, baseline_metrics=complete.candidate_metrics)


def test_rejects_comparison_bound_to_wrong_metrics(complete):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="exact B8 comparison",
    ):
        replace(complete, comparison=object())


def test_rejects_metrics_on_incomplete_campaign(baseline_incomplete, complete):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="incomplete baseline cannot contain B7",
    ):
        replace(
            baseline_incomplete,
            baseline_metrics=complete.baseline_metrics,
        )


def test_rejects_comparison_on_partial_campaign(baseline_incomplete, complete):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="partial campaigns cannot contain a B8",
    ):
        replace(baseline_incomplete, comparison=complete.comparison)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("development_evidence_only", False),
        ("both_campaigns_reverified", False),
        ("partial_outcomes_preserved", False),
        ("distinct_model_identities_verified", False),
        ("complete_metrics_reverified", False),
        ("comparison_reverified_when_complete", False),
        ("qualification_threshold_applied", True),
        ("statistical_significance_claimed", True),
        ("model_winner_declared", True),
        ("production_qualified", True),
        ("release_enforcement_eligible", True),
        ("official_release_verdict_modified", True),
    ],
)
def test_authority_boundary_fails_closed(complete, field, value):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonExecutionError,
        match="authority boundary changed",
    ):
        replace(complete, **{field: value})


def test_evidence_boundary_is_explicitly_non_qualifying(complete):
    boundary = complete.payload["evidence_boundary"]
    assert boundary["development_evidence_only"] is True
    assert boundary["partial_outcomes_preserved"] is True
    assert boundary["qualification_threshold_applied"] is False
    assert boundary["statistical_significance_claimed"] is False
    assert boundary["model_winner_declared"] is False
    assert boundary["production_qualified"] is False
    assert boundary["release_enforcement_eligible"] is False
    assert boundary["official_release_verdict_modified"] is False


def test_execution_bundle_is_frozen_slots_dataclass(complete):
    with pytest.raises(
        (FrozenInstanceError, AttributeError, TypeError),
    ):
        complete.unexpected = True
