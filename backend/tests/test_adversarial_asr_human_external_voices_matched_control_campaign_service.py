from __future__ import annotations

from dataclasses import FrozenInstanceError
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from app.adversarial_asr_human_external_voices_matched_control_campaign_service import (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_KEY,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_VERSION,
    ASRAdversarialVOiCESMatchedControlCampaignBundle,
    ASRAdversarialVOiCESMatchedControlCampaignError,
    execute_asr_adversarial_voices_babble_matched_control_campaign_v1,
)
from app.adversarial_asr_human_external_voices_matched_control_projection import (
    project_asr_adversarial_voices_babble_matched_control_v1,
)
from app.adversarial_asr_human_external_voices_matched_control_suite_projection import (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
    ASRAdversarialVOiCESMatchedControlSuiteBundle,
    project_asr_adversarial_voices_babble_matched_control_suite_v1,
)
from app.adversarial_asr_human_external_voices_materialization_service import (
    ASRAdversarialVOiCESMaterializedCaptureCondition,
    ASRAdversarialVOiCESMaterializedEvidence,
    ASRAdversarialVOiCESMaterializedMedia,
)
from app.speech import TranscriptionError
from app.speech import TranscriptionResult
from hvee.packs.asr import (
    ASRAdversarialExecutionStatus,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
    verify_asr_adversarial_campaign_evidence_v1,
    verify_asr_adversarial_execution_evidence_v1,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
)


PROVIDER_KEY = "deterministic_test"
MODEL_KEY = "test-model-v1"
CAMPAIGN_ID = "voices-babble-control-test"
CAMPAIGN_VERSION = "1.0.0"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _audio_bytes(relative_path: str) -> bytes:
    return hashlib.sha256(
        relative_path.encode("utf-8")
    ).digest() * 1_000


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
    path, content = _write_audio(
        root=root,
        relative_path=relative_path,
    )

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
    path, content = _write_audio(
        root=root,
        relative_path=relative_path,
    )

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
        _source_media(
            root=root,
            source_key=source_key,
        )
        for source_key in (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
        )
    ]

    media.extend(
        _capture_media(
            root=root,
            source_key=source_key,
            room=room,
            distractor=distractor,
            microphone_id=microphone_id,
        )
        for source_key in (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
        )
        for room in ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS
        for distractor in ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS
        for microphone_id in (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS
        )
    )

    return ASRAdversarialVOiCESMaterializedEvidence(
        controlled_contract_sha256=(
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
        ),
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


def _suite(
    root: Path,
) -> ASRAdversarialVOiCESMatchedControlSuiteBundle:
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


class _DeterministicProvider:
    provider_name = PROVIDER_KEY

    def __init__(
        self,
        *,
        suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
        failed_case_id: str | None = None,
    ) -> None:
        self.transcripts = {
            binding.media.path: binding.case.reference_transcript
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
        self.calls: list[tuple[Path, str | None]] = []

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ) -> TranscriptionResult:
        path = Path(audio_path)
        self.calls.append((path, model_name))

        if path == self.failed_path:
            raise TranscriptionError("deterministic test failure")

        return TranscriptionResult(
            transcript=self.transcripts[path],
            provider=self.provider_name,
            model_name=model_name or MODEL_KEY,
            device="cpu",
            compute_type="test",
        )


class _Stopped:
    def is_set(self) -> bool:
        return True


def _execute(
    *,
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
    provider: _DeterministicProvider,
    model_name: str = MODEL_KEY,
    stop_event: object | None = None,
) -> ASRAdversarialVOiCESMatchedControlCampaignBundle:
    return (
        execute_asr_adversarial_voices_babble_matched_control_campaign_v1(
            campaign_id=CAMPAIGN_ID,
            campaign_version=CAMPAIGN_VERSION,
            requested_model_name=model_name,
            provider=provider,
            terminology=_terminology(),
            suite=suite,
            stop_event=stop_event,
        )
    )


@pytest.fixture(scope="module")
def completed_bundle(
    tmp_path_factory,
) -> ASRAdversarialVOiCESMatchedControlCampaignBundle:
    suite = _suite(tmp_path_factory.mktemp("b6-completed"))
    return _execute(
        suite=suite,
        provider=_DeterministicProvider(suite=suite),
    )


def test_campaign_constants_are_exact():
    assert ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_CAMPAIGN_KEY == (
        "hetren.asr.adversarial-human-external-"
        "voices-babble-matched-control-campaign"
    )


def test_executes_exact_complete_32_case_campaign(completed_bundle):
    assert len(completed_bundle.campaign.attempts) == 32
    assert len(completed_bundle.campaign.completed_results) == 32
    assert completed_bundle.all_cases_completed is True
    assert completed_bundle.completed_pair_count == 16
    assert completed_bundle.status_counts == {
        "completed": 32,
        "failed": 0,
        "timed_out": 0,
        "cancelled": 0,
        "invalid": 0,
    }


def test_campaign_binds_exact_b5_suite(completed_bundle):
    assert (
        completed_bundle.matched_control_suite_sha256
        == completed_bundle.suite.sha256
    )
    assert (
        completed_bundle.campaign.definition.suite_sha256
        == completed_bundle.suite.evidence.sha256
    )
    assert tuple(
        attempt.case_id
        for attempt in completed_bundle.campaign.attempts
    ) == tuple(
        binding.case.case_id
        for binding in completed_bundle.suite.cases
    )


def test_campaign_preserves_explicit_provider_and_model_identity(
    completed_bundle,
):
    definition = completed_bundle.campaign.definition
    assert definition.provider_key == PROVIDER_KEY
    assert definition.model_key == MODEL_KEY
    assert all(
        result.environment.provider == PROVIDER_KEY
        and result.environment.model_name == MODEL_KEY
        for result in completed_bundle.campaign.completed_results
    )


def test_all_completed_children_are_independently_reverifiable(
    completed_bundle,
):
    for result in completed_bundle.campaign.completed_results:
        assert verify_asr_adversarial_execution_evidence_v1(
            payload=result.execution_evidence.payload,
            expected_sha256=result.execution_evidence.sha256,
            definition=result.execution_definition,
            suite=completed_bundle.suite.definition,
            suite_evidence=completed_bundle.suite.evidence,
        ) == result.execution_evidence


def test_aggregate_campaign_is_independently_reverifiable(
    completed_bundle,
):
    campaign = completed_bundle.campaign
    assert verify_asr_adversarial_campaign_evidence_v1(
        payload=campaign.evidence.payload,
        expected_sha256=campaign.evidence.sha256,
        definition=campaign.definition,
        suite=completed_bundle.suite.definition,
        suite_evidence=completed_bundle.suite.evidence,
    ) == campaign.evidence


def test_complete_gate_returns_exact_ordered_results(completed_bundle):
    assert completed_bundle.require_complete_for_paired_metrics() is (
        completed_bundle.campaign.completed_results
    )


def test_payload_binds_campaign_evidence_and_ordered_attempts(
    completed_bundle,
):
    payload = completed_bundle.payload
    assert payload["upstream"]["matched_control_suite_sha256"] == (
        completed_bundle.suite.sha256
    )
    assert payload["upstream"]["campaign_evidence_sha256"] == (
        completed_bundle.campaign.evidence.sha256
    )
    assert [
        item["case_id"]
        for item in payload["campaign"]["ordered_attempts"]
    ] == [
        binding.case.case_id
        for binding in completed_bundle.suite.cases
    ]
    assert all(
        item["execution_evidence_sha256"] is not None
        and item["generated_transcript_sha256"] is not None
        for item in payload["campaign"]["ordered_attempts"]
    )


def test_payload_preserves_exact_balanced_arms(completed_bundle):
    arms = [
        item["arm"]
        for item in completed_bundle.payload["campaign"]["ordered_attempts"]
    ]
    assert arms.count(
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
    ) == 16
    assert arms.count(
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
    ) == 16


def test_payload_contains_no_raw_transcript_or_absolute_path(
    completed_bundle,
):
    serialized = json.dumps(
        completed_bundle.payload,
        sort_keys=True,
    )
    for binding, result in zip(
        completed_bundle.suite.cases,
        completed_bundle.campaign.completed_results,
        strict=True,
    ):
        assert str(binding.media.path) not in serialized
        assert result.generated_transcript not in serialized


def test_campaign_identity_is_deterministic_across_materialization_roots(
    completed_bundle,
    tmp_path,
):
    suite = _suite(tmp_path / "second-root")
    second = _execute(
        suite=suite,
        provider=_DeterministicProvider(suite=suite),
    )
    assert second.suite.sha256 == completed_bundle.suite.sha256
    assert second.campaign.evidence.sha256 == (
        completed_bundle.campaign.evidence.sha256
    )
    assert second.payload == completed_bundle.payload
    assert second.sha256 == completed_bundle.sha256


def test_same_suite_supports_explicit_second_model_identity(tmp_path):
    suite = _suite(tmp_path)
    first = _execute(
        suite=suite,
        provider=_DeterministicProvider(suite=suite),
    )
    second = _execute(
        suite=suite,
        provider=_DeterministicProvider(suite=suite),
        model_name="counterexample-model-v2",
    )
    assert first.suite is second.suite
    assert first.campaign.definition.model_key == MODEL_KEY
    assert second.campaign.definition.model_key == "counterexample-model-v2"
    assert first.campaign.evidence.sha256 != second.campaign.evidence.sha256
    assert first.sha256 != second.sha256


def test_one_provider_failure_is_preserved_without_pair_overclaim(tmp_path):
    suite = _suite(tmp_path)
    failed_case_id = suite.cases[0].case.case_id
    bundle = _execute(
        suite=suite,
        provider=_DeterministicProvider(
            suite=suite,
            failed_case_id=failed_case_id,
        ),
    )
    assert bundle.status_counts["failed"] == 1
    assert bundle.status_counts["completed"] == 31
    assert len(bundle.campaign.completed_results) == 31
    assert bundle.completed_pair_count == 15
    assert bundle.all_cases_completed is False
    assert bundle.campaign.attempts[0].status == (
        ASRAdversarialExecutionStatus.FAILED
    )
    assert bundle.campaign.attempts[0].execution_evidence is None
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="all 32 cases.*all 16",
    ):
        bundle.require_complete_for_paired_metrics()


def test_pre_requested_stop_preserves_all_cancelled_attempts(tmp_path):
    suite = _suite(tmp_path)
    provider = _DeterministicProvider(suite=suite)
    bundle = _execute(
        suite=suite,
        provider=provider,
        stop_event=_Stopped(),
    )
    assert bundle.status_counts["cancelled"] == 32
    assert bundle.campaign.completed_results == ()
    assert bundle.completed_pair_count == 0
    assert bundle.all_cases_completed is False
    assert provider.calls == []


def test_non_not_configured_terminology_is_rejected_before_execution(
    tmp_path,
):
    suite = _suite(tmp_path)
    provider = _DeterministicProvider(suite=suite)
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="not_configured",
    ):
        execute_asr_adversarial_voices_babble_matched_control_campaign_v1(
            campaign_id=CAMPAIGN_ID,
            campaign_version=CAMPAIGN_VERSION,
            requested_model_name=MODEL_KEY,
            provider=provider,
            terminology=object(),
            suite=suite,
        )
    assert provider.calls == []


def test_untrimmed_model_identity_is_rejected_before_execution(tmp_path):
    suite = _suite(tmp_path)
    provider = _DeterministicProvider(suite=suite)
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="requested model",
    ):
        _execute(
            suite=suite,
            provider=provider,
            model_name=" test-model-v1 ",
        )
    assert provider.calls == []


def test_wrong_b5_suite_type_is_rejected():
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="exact B5 suite",
    ):
        execute_asr_adversarial_voices_babble_matched_control_campaign_v1(
            campaign_id=CAMPAIGN_ID,
            campaign_version=CAMPAIGN_VERSION,
            requested_model_name=MODEL_KEY,
            provider=object(),
            terminology=_terminology(),
            suite=object(),
        )


def test_bundle_rejects_b5_suite_hash_substitution(completed_bundle):
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="suite identity",
    ):
        replace(
            completed_bundle,
            matched_control_suite_sha256="f" * 64,
        )


def test_bundle_rejects_campaign_definition_substitution(completed_bundle):
    changed_definition = replace(
        completed_bundle.campaign.definition,
        model_key="substituted-model",
    )
    changed_campaign = replace(
        completed_bundle.campaign,
        definition=changed_definition,
    )
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="campaign evidence",
    ):
        replace(
            completed_bundle,
            campaign=changed_campaign,
        )


def test_bundle_rejects_missing_attempt(completed_bundle):
    changed_campaign = replace(
        completed_bundle.campaign,
        attempts=completed_bundle.campaign.attempts[:-1],
    )
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="coverage",
    ):
        replace(
            completed_bundle,
            campaign=changed_campaign,
        )


def test_bundle_rejects_completed_result_reordering(completed_bundle):
    changed_campaign = replace(
        completed_bundle.campaign,
        completed_results=tuple(
            reversed(completed_bundle.campaign.completed_results)
        ),
    )
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="completed campaign results",
    ):
        replace(
            completed_bundle,
            campaign=changed_campaign,
        )


def test_bundle_rejects_completed_audio_identity_substitution(
    completed_bundle,
):
    results = list(completed_bundle.campaign.completed_results)
    results[0] = replace(
        results[0],
        audio_asset_sha256="f" * 64,
    )
    changed_campaign = replace(
        completed_bundle.campaign,
        completed_results=tuple(results),
    )
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="execution identity",
    ):
        replace(
            completed_bundle,
            campaign=changed_campaign,
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("development_evidence_only", False),
        ("matched_control_suite_reverified", False),
        ("campaign_evidence_reverified", False),
        ("partial_outcomes_preserved", False),
        ("paired_metrics_computed", True),
        ("qualification_threshold_applied", True),
        ("production_qualified", True),
        ("release_enforcement_eligible", True),
        ("official_release_verdict_modified", True),
    ),
)
def test_bundle_rejects_authority_boundary_change(
    completed_bundle,
    field,
    value,
):
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlCampaignError,
        match="authority boundary",
    ):
        replace(
            completed_bundle,
            **{field: value},
        )


def test_bundle_type_is_frozen_slots_dataclass(completed_bundle):
    with pytest.raises(FrozenInstanceError):
        completed_bundle.development_evidence_only = False
    with pytest.raises((AttributeError, TypeError)):
        completed_bundle.unexpected = True


def test_campaign_sha256_is_canonical_lowercase_digest(completed_bundle):
    assert len(completed_bundle.sha256) == 64
    assert completed_bundle.sha256 == completed_bundle.sha256.lower()
    assert set(completed_bundle.sha256) <= set("0123456789abcdef")


def test_campaign_evidence_boundary_is_exact(completed_bundle):
    assert completed_bundle.payload["evidence_boundary"] == {
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
    }


def test_campaign_object_authority_boundary_is_exact(completed_bundle):
    assert completed_bundle.development_evidence_only is True
    assert completed_bundle.matched_control_suite_reverified is True
    assert completed_bundle.campaign_evidence_reverified is True
    assert completed_bundle.partial_outcomes_preserved is True
    assert completed_bundle.paired_metrics_computed is False
    assert completed_bundle.qualification_threshold_applied is False
    assert completed_bundle.production_qualified is False
    assert completed_bundle.release_enforcement_eligible is False
    assert completed_bundle.official_release_verdict_modified is False


def test_case_population_constant_remains_32():
    assert ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT == 32
    assert ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT == 16
