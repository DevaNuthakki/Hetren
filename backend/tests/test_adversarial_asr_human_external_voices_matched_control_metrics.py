from __future__ import annotations

from dataclasses import FrozenInstanceError
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from app.adversarial_asr_human_external_voices_matched_control_campaign_service import (
    ASRAdversarialVOiCESMatchedControlCampaignBundle,
    execute_asr_adversarial_voices_babble_matched_control_campaign_v1,
)
from app.adversarial_asr_human_external_voices_matched_control_metrics import (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_KEY,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_VERSION,
    ASRAdversarialVOiCESMatchedControlCaseMetrics,
    ASRAdversarialVOiCESMatchedControlMetricsBundle,
    ASRAdversarialVOiCESMatchedControlMetricsError,
    ASRAdversarialVOiCESMatchedControlPairMetrics,
    build_asr_adversarial_voices_babble_matched_control_metrics_v1,
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
    BASIC_TEXT_NORMALIZATION,
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
    NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
    ASRAdversarialExecutionStatus,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
    calculate_asr_adversarial_transcript_sha256,
    evaluate_normalized_transcript_pair,
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
CAMPAIGN_ID = "voices-babble-control-metrics-test"
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


def _remove_first_word(value: str) -> str:
    return " ".join(value.split()[1:])


class _MetricsProvider:
    provider_name = PROVIDER_KEY

    def __init__(
        self,
        *,
        suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
        error_arm: str | None = (
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
        ),
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

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ) -> TranscriptionResult:
        path = Path(audio_path)
        if path == self.failed_path:
            raise TranscriptionError("deterministic metric test failure")

        return TranscriptionResult(
            transcript=self.generated[path],
            provider=self.provider_name,
            model_name=model_name or MODEL_KEY,
            device="cpu",
            compute_type="test",
        )


def _campaign(
    *,
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
    provider: _MetricsProvider,
    model_name: str = MODEL_KEY,
) -> ASRAdversarialVOiCESMatchedControlCampaignBundle:
    return (
        execute_asr_adversarial_voices_babble_matched_control_campaign_v1(
            campaign_id=CAMPAIGN_ID,
            campaign_version=CAMPAIGN_VERSION,
            requested_model_name=model_name,
            provider=provider,
            terminology=_terminology(),
            suite=suite,
        )
    )


def _metrics(
    *,
    root: Path,
    error_arm: str | None = (
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
    ),
    model_name: str = MODEL_KEY,
) -> ASRAdversarialVOiCESMatchedControlMetricsBundle:
    suite = _suite(root)
    campaign = _campaign(
        suite=suite,
        provider=_MetricsProvider(
            suite=suite,
            error_arm=error_arm,
        ),
        model_name=model_name,
    )
    return build_asr_adversarial_voices_babble_matched_control_metrics_v1(
        campaign
    )


@pytest.fixture(scope="module")
def metrics_bundle(
    tmp_path_factory,
) -> ASRAdversarialVOiCESMatchedControlMetricsBundle:
    return _metrics(root=tmp_path_factory.mktemp("b7-metrics"))


def test_metrics_constants_are_exact():
    assert ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_METRICS_KEY == (
        "hetren.asr.adversarial-human-external-"
        "voices-babble-matched-control-normalized-metrics"
    )


def test_builds_exact_32_case_16_pair_population(metrics_bundle):
    assert len(metrics_bundle.cases) == 32
    assert len(metrics_bundle.pairs) == 16
    assert len({value.case_id for value in metrics_bundle.cases}) == 32
    assert len({value.key for value in metrics_bundle.pairs}) == 16


def test_binds_exact_complete_b6_campaign(metrics_bundle):
    assert metrics_bundle.matched_control_campaign_sha256 == (
        metrics_bundle.campaign.sha256
    )
    assert metrics_bundle.campaign.all_cases_completed is True
    assert metrics_bundle.campaign.completed_pair_count == 16


def test_every_case_equals_canonical_normalized_evaluator(metrics_bundle):
    binding_by_case_id = {
        binding.case.case_id: binding
        for binding in metrics_bundle.campaign.suite.cases
    }
    result_by_case_id = {
        result.case_id: result
        for result in metrics_bundle.campaign.campaign.completed_results
    }
    for value in metrics_bundle.cases:
        binding = binding_by_case_id[value.case_id]
        result = result_by_case_id[value.case_id]
        assert value.evaluation == evaluate_normalized_transcript_pair(
            reference_text=binding.case.reference_transcript,
            generated_text=result.generated_transcript,
        )


def test_every_case_binds_exact_execution_evidence(metrics_bundle):
    result_by_case_id = {
        result.case_id: result
        for result in metrics_bundle.campaign.campaign.completed_results
    }
    for value in metrics_bundle.cases:
        result = result_by_case_id[value.case_id]
        assert value.execution_evidence_sha256 == (
            result.execution_evidence.sha256
        )
        assert value.generated_transcript_sha256 == (
            calculate_asr_adversarial_transcript_sha256(
                result.generated_transcript
            )
        )


def test_every_pair_preserves_exact_matching_key_and_reference(metrics_bundle):
    assert all(
        value.babble.pair_key == value.key
        and value.control.pair_key == value.key
        and value.babble.reference_transcript_sha256
        == value.control.reference_transcript_sha256
        for value in metrics_bundle.pairs
    )


def test_deliberate_babble_deletion_produces_positive_paired_deltas(
    metrics_bundle,
):
    assert all(value.wer_delta > 0.0 for value in metrics_bundle.pairs)
    assert all(value.cer_delta > 0.0 for value in metrics_bundle.pairs)
    assert all(value.deletions_delta == 1 for value in metrics_bundle.pairs)
    assert all(value.substitutions_delta == 0 for value in metrics_bundle.pairs)
    assert all(value.insertions_delta == 0 for value in metrics_bundle.pairs)


def test_control_arm_is_exact_for_deliberate_fixture(metrics_bundle):
    controls = tuple(
        value
        for value in metrics_bundle.cases
        if value.arm
        == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
    )
    assert all(value.evaluation.wer == 0.0 for value in controls)
    assert all(value.evaluation.cer == 0.0 for value in controls)
    assert all(value.evaluation.substitutions == 0 for value in controls)
    assert all(value.evaluation.insertions == 0 for value in controls)
    assert all(value.evaluation.deletions == 0 for value in controls)


def test_aggregate_macro_delta_matches_equal_weight_pair_mean(metrics_bundle):
    aggregate = metrics_bundle.aggregate["macro_mean"]
    expected_wer = sum(value.wer_delta for value in metrics_bundle.pairs) / 16
    expected_cer = sum(value.cer_delta for value in metrics_bundle.pairs) / 16
    assert aggregate["babble_minus_control"]["wer"] == expected_wer
    assert aggregate["babble_minus_control"]["cer"] == expected_cer
    assert aggregate["control"] == {"wer": 0.0, "cer": 0.0}


def test_aggregate_word_alignment_totals_are_exact(metrics_bundle):
    assert metrics_bundle.aggregate["word_alignment_totals"] == {
        "babble": {
            "substitutions": 0,
            "insertions": 0,
            "deletions": 16,
        },
        "control": {
            "substitutions": 0,
            "insertions": 0,
            "deletions": 0,
        },
    }


def test_pair_direction_counts_are_descriptive_not_thresholds(metrics_bundle):
    assert metrics_bundle.aggregate["pair_direction_counts"] == {
        "wer": {
            "babble_higher": 16,
            "equal": 0,
            "babble_lower": 0,
        },
        "cer": {
            "babble_higher": 16,
            "equal": 0,
            "babble_lower": 0,
        },
    }


def test_payload_binds_canonical_metric_and_evaluator_versions(metrics_bundle):
    methodology = metrics_bundle.payload["methodology"]
    assert methodology["normalization"] == {
        "key": BASIC_TEXT_NORMALIZATION.key,
        "version": BASIC_TEXT_NORMALIZATION.version,
    }
    assert methodology["wer"] == {
        "metric_key": NORMALIZED_WER_METRIC.key,
        "metric_version": NORMALIZED_WER_METRIC.version,
        "evaluator_key": NORMALIZED_WER_EVALUATOR.key,
        "evaluator_version": NORMALIZED_WER_EVALUATOR.version,
    }
    assert methodology["cer"] == {
        "metric_key": NORMALIZED_CER_METRIC.key,
        "metric_version": NORMALIZED_CER_METRIC.version,
        "evaluator_key": NORMALIZED_CER_EVALUATOR.key,
        "evaluator_version": NORMALIZED_CER_EVALUATOR.version,
    }
    assert methodology["word_alignment"] == {
        "evaluator_key": NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key,
        "evaluator_version": NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version,
        "substitutions": {
            "metric_key": NORMALIZED_SUBSTITUTIONS_METRIC.key,
            "metric_version": NORMALIZED_SUBSTITUTIONS_METRIC.version,
        },
        "insertions": {
            "metric_key": NORMALIZED_INSERTIONS_METRIC.key,
            "metric_version": NORMALIZED_INSERTIONS_METRIC.version,
        },
        "deletions": {
            "metric_key": NORMALIZED_DELETIONS_METRIC.key,
            "metric_version": NORMALIZED_DELETIONS_METRIC.version,
        },
    }


def test_payload_preserves_explicit_provider_and_model_identity(metrics_bundle):
    assert metrics_bundle.payload["model_identity"] == {
        "campaign_id": CAMPAIGN_ID,
        "campaign_version": CAMPAIGN_VERSION,
        "provider_key": PROVIDER_KEY,
        "model_key": MODEL_KEY,
    }


def test_payload_contains_no_raw_or_normalized_transcript_or_path(
    metrics_bundle,
):
    serialized = json.dumps(metrics_bundle.payload, sort_keys=True)
    result_by_case_id = {
        result.case_id: result
        for result in metrics_bundle.campaign.campaign.completed_results
    }
    for binding in metrics_bundle.campaign.suite.cases:
        result = result_by_case_id[binding.case.case_id]
        evaluation = evaluate_normalized_transcript_pair(
            reference_text=binding.case.reference_transcript,
            generated_text=result.generated_transcript,
        )
        assert str(binding.media.path) not in serialized
        assert binding.case.reference_transcript not in serialized
        assert result.generated_transcript not in serialized
        assert evaluation.normalized_reference not in serialized
        assert evaluation.normalized_generated not in serialized


def test_normalized_transcript_commitments_are_exact(metrics_bundle):
    for value in metrics_bundle.cases:
        assert value.normalized_reference_sha256 == _sha256_text(
            value.evaluation.normalized_reference
        )
        assert value.normalized_generated_sha256 == _sha256_text(
            value.evaluation.normalized_generated
        )


def test_metrics_are_deterministic_across_materialization_roots(
    metrics_bundle,
    tmp_path,
):
    second = _metrics(root=tmp_path / "second-root")
    assert second.campaign.sha256 == metrics_bundle.campaign.sha256
    assert second.cases == metrics_bundle.cases
    assert second.pairs == metrics_bundle.pairs
    assert second.payload == metrics_bundle.payload
    assert second.sha256 == metrics_bundle.sha256


def test_same_metric_population_binds_second_model_identity(tmp_path):
    first = _metrics(root=tmp_path / "first")
    second = _metrics(
        root=tmp_path / "second",
        model_name="counterexample-model-v2",
    )
    assert tuple(value.evaluation for value in first.cases) == tuple(
        value.evaluation for value in second.cases
    )
    assert first.campaign.suite.sha256 == second.campaign.suite.sha256
    assert first.payload["model_identity"]["model_key"] == MODEL_KEY
    assert second.payload["model_identity"]["model_key"] == (
        "counterexample-model-v2"
    )
    assert first.sha256 != second.sha256


def test_negative_deltas_are_preserved_without_reinterpretation(tmp_path):
    bundle = _metrics(
        root=tmp_path,
        error_arm=ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
    )
    assert all(value.wer_delta < 0.0 for value in bundle.pairs)
    assert all(value.cer_delta < 0.0 for value in bundle.pairs)
    assert bundle.aggregate["pair_direction_counts"]["wer"] == {
        "babble_higher": 0,
        "equal": 0,
        "babble_lower": 16,
    }


def test_equal_deltas_are_preserved_without_reinterpretation(tmp_path):
    bundle = _metrics(root=tmp_path, error_arm=None)
    assert all(value.wer_delta == 0.0 for value in bundle.pairs)
    assert all(value.cer_delta == 0.0 for value in bundle.pairs)
    assert bundle.aggregate["pair_direction_counts"]["wer"] == {
        "babble_higher": 0,
        "equal": 16,
        "babble_lower": 0,
    }


def test_partial_b6_campaign_is_rejected(tmp_path):
    suite = _suite(tmp_path)
    failed_case_id = suite.cases[0].case.case_id
    campaign = _campaign(
        suite=suite,
        provider=_MetricsProvider(
            suite=suite,
            failed_case_id=failed_case_id,
        ),
    )
    assert campaign.campaign.attempts[0].status == (
        ASRAdversarialExecutionStatus.FAILED
    )
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="all 32 completed cases",
    ):
        build_asr_adversarial_voices_babble_matched_control_metrics_v1(
            campaign
        )


def test_wrong_b6_input_type_is_rejected():
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="exact B6 campaign",
    ):
        build_asr_adversarial_voices_babble_matched_control_metrics_v1(
            object()
        )


def test_bundle_rejects_campaign_hash_substitution(metrics_bundle):
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="campaign identity",
    ):
        replace(
            metrics_bundle,
            matched_control_campaign_sha256="f" * 64,
        )


def test_bundle_rejects_missing_case_metric(metrics_bundle):
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="case metric population",
    ):
        replace(metrics_bundle, cases=metrics_bundle.cases[:-1])


def test_bundle_rejects_case_metric_reordering(metrics_bundle):
    changed = list(metrics_bundle.cases)
    changed[0], changed[1] = changed[1], changed[0]
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="ordering",
    ):
        replace(metrics_bundle, cases=tuple(changed))


def test_bundle_rejects_missing_pair_metric(metrics_bundle):
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="pair metric population",
    ):
        replace(metrics_bundle, pairs=metrics_bundle.pairs[:-1])


def test_bundle_rejects_recomputed_metric_substitution(metrics_bundle):
    changed = list(metrics_bundle.cases)
    changed[0] = replace(
        changed[0],
        evaluation=replace(
            changed[0].evaluation,
            wer=changed[0].evaluation.wer + 0.1,
        ),
    )
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="case metric binding",
    ):
        replace(metrics_bundle, cases=tuple(changed))


def test_case_metric_rejects_normalized_commitment_substitution(
    metrics_bundle,
):
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="normalized transcript commitment",
    ):
        replace(
            metrics_bundle.cases[0],
            normalized_generated_sha256="f" * 64,
        )


def test_bundle_rejects_execution_evidence_substitution(metrics_bundle):
    changed = list(metrics_bundle.cases)
    changed[0] = replace(
        changed[0],
        execution_evidence_sha256="f" * 64,
    )
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="case metric binding",
    ):
        replace(metrics_bundle, cases=tuple(changed))


def test_pair_metric_rejects_arm_reversal(metrics_bundle):
    pair = metrics_bundle.pairs[0]
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="exact matched controls",
    ):
        ASRAdversarialVOiCESMatchedControlPairMetrics(
            key=pair.key,
            babble=pair.control,
            control=pair.babble,
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("development_evidence_only", False),
        ("complete_campaign_reverified", False),
        ("normalized_evaluators_bound", False),
        ("paired_metrics_computed", False),
        ("qualification_threshold_applied", True),
        ("model_verdict_issued", True),
        ("production_qualified", True),
        ("release_enforcement_eligible", True),
        ("official_release_verdict_modified", True),
    ),
)
def test_bundle_rejects_authority_boundary_change(
    metrics_bundle,
    field,
    value,
):
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="authority boundary",
    ):
        replace(metrics_bundle, **{field: value})


def test_threshold_requirement_fails_closed(metrics_bundle):
    with pytest.raises(
        ASRAdversarialVOiCESMatchedControlMetricsError,
        match="no qualification threshold or model verdict",
    ):
        metrics_bundle.require_qualification_threshold_applied()


def test_metrics_evidence_boundary_is_exact(metrics_bundle):
    assert metrics_bundle.payload["evidence_boundary"] == {
        "development_evidence_only": True,
        "complete_campaign_reverified": True,
        "normalized_evaluators_bound": True,
        "paired_metrics_computed": True,
        "raw_audio_embedded": False,
        "absolute_audio_paths_embedded": False,
        "raw_generated_transcripts_embedded": False,
        "normalized_transcripts_embedded": False,
        "qualification_threshold_applied": False,
        "model_verdict_issued": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def test_metrics_object_authority_boundary_is_exact(metrics_bundle):
    assert metrics_bundle.development_evidence_only is True
    assert metrics_bundle.complete_campaign_reverified is True
    assert metrics_bundle.normalized_evaluators_bound is True
    assert metrics_bundle.paired_metrics_computed is True
    assert metrics_bundle.qualification_threshold_applied is False
    assert metrics_bundle.model_verdict_issued is False
    assert metrics_bundle.production_qualified is False
    assert metrics_bundle.release_enforcement_eligible is False
    assert metrics_bundle.official_release_verdict_modified is False


def test_metrics_types_are_frozen_slots_dataclasses(metrics_bundle):
    with pytest.raises(FrozenInstanceError):
        metrics_bundle.paired_metrics_computed = False
    with pytest.raises(FrozenInstanceError):
        metrics_bundle.cases[0].arm = "control"
    with pytest.raises(FrozenInstanceError):
        metrics_bundle.pairs[0].key = metrics_bundle.pairs[1].key
    with pytest.raises((AttributeError, TypeError)):
        metrics_bundle.unexpected = True


def test_metrics_sha256_is_canonical_lowercase_digest(metrics_bundle):
    assert len(metrics_bundle.sha256) == 64
    assert metrics_bundle.sha256 == metrics_bundle.sha256.lower()
    assert set(metrics_bundle.sha256) <= set("0123456789abcdef")


def test_all_metric_values_are_finite_nonnegative(metrics_bundle):
    assert all(
        value.evaluation.wer >= 0.0
        and value.evaluation.cer >= 0.0
        for value in metrics_bundle.cases
    )


def test_population_constants_remain_exact():
    assert ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT == 32
    assert ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT == 16
