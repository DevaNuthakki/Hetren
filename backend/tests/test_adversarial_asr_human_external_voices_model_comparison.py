from __future__ import annotations

from dataclasses import FrozenInstanceError
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from app.adversarial_asr_human_external_voices_matched_control_campaign_service import (
    execute_asr_adversarial_voices_babble_matched_control_campaign_v1,
)
from app.adversarial_asr_human_external_voices_matched_control_metrics import (
    ASRAdversarialVOiCESMatchedControlMetricsBundle,
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
from app.adversarial_asr_human_external_voices_model_comparison import (
    ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_KEY,
    ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_VERSION,
    ASRAdversarialVOiCESModelComparisonBundle,
    ASRAdversarialVOiCESModelComparisonError,
    build_asr_adversarial_voices_model_comparison_v1,
)
from app.speech import TranscriptionResult
from hvee.packs.asr import (
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
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


PROVIDER_KEY = "deterministic_comparator"
BASELINE_MODEL_KEY = "baseline-model-v1"
CANDIDATE_MODEL_KEY = "candidate-model-v2"
CAMPAIGN_ID = "voices-model-comparison-test"
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


class _ComparisonProvider:
    provider_name = PROVIDER_KEY

    def __init__(
        self,
        *,
        suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
        error_arm: str | None,
    ) -> None:
        self.generated = {
            binding.media.path: (
                _remove_first_word(binding.case.reference_transcript)
                if binding.arm == error_arm
                else binding.case.reference_transcript
            )
            for binding in suite.cases
        }

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ) -> TranscriptionResult:
        return TranscriptionResult(
            transcript=self.generated[Path(audio_path)],
            provider=self.provider_name,
            model_name=model_name or "missing-model",
            device="cpu",
            compute_type="test",
        )


def _metrics(
    *,
    suite: ASRAdversarialVOiCESMatchedControlSuiteBundle,
    model_name: str,
    error_arm: str | None,
) -> ASRAdversarialVOiCESMatchedControlMetricsBundle:
    campaign = execute_asr_adversarial_voices_babble_matched_control_campaign_v1(
        campaign_id=CAMPAIGN_ID,
        campaign_version=CAMPAIGN_VERSION,
        requested_model_name=model_name,
        provider=_ComparisonProvider(suite=suite, error_arm=error_arm),
        terminology=_terminology(),
        suite=suite,
    )
    return build_asr_adversarial_voices_babble_matched_control_metrics_v1(
        campaign
    )


@pytest.fixture(scope="module")
def model_metrics(tmp_path_factory):
    suite = _suite(tmp_path_factory.mktemp("b8-model-comparison"))
    baseline = _metrics(
        suite=suite,
        model_name=BASELINE_MODEL_KEY,
        error_arm=ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
    )
    candidate = _metrics(
        suite=suite,
        model_name=CANDIDATE_MODEL_KEY,
        error_arm=None,
    )
    return baseline, candidate


@pytest.fixture(scope="module")
def comparison(
    model_metrics,
) -> ASRAdversarialVOiCESModelComparisonBundle:
    baseline, candidate = model_metrics
    return build_asr_adversarial_voices_model_comparison_v1(
        baseline=baseline,
        candidate=candidate,
    )


def test_constants_are_exact():
    assert ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_MODEL_COMPARISON_KEY == (
        "hetren.asr.adversarial-human-external-"
        "voices-babble-matched-control-model-comparison"
    )


def test_builds_exact_case_and_pair_population(comparison):
    assert len(comparison.cases) == 32
    assert len(comparison.pairs) == 16
    assert len({value.case_id for value in comparison.cases}) == 32
    assert len({value.key for value in comparison.pairs}) == 16


def test_binds_both_exact_b7_metric_artifacts(comparison):
    assert comparison.baseline_metrics_sha256 == comparison.baseline.sha256
    assert comparison.candidate_metrics_sha256 == comparison.candidate.sha256
    assert comparison.baseline.sha256 != comparison.candidate.sha256


def test_requires_distinct_provider_model_identity(comparison):
    assert comparison.baseline_identity.provider_key == PROVIDER_KEY
    assert comparison.candidate_identity.provider_key == PROVIDER_KEY
    assert comparison.baseline_identity.model_key == BASELINE_MODEL_KEY
    assert comparison.candidate_identity.model_key == CANDIDATE_MODEL_KEY
    assert (
        comparison.baseline_identity.provider_model
        != comparison.candidate_identity.provider_model
    )


def test_campaign_labels_do_not_replace_provider_model_identity(comparison):
    assert comparison.baseline_identity.campaign_id == CAMPAIGN_ID
    assert comparison.candidate_identity.campaign_id == CAMPAIGN_ID
    assert comparison.baseline_identity.campaign_version == CAMPAIGN_VERSION
    assert comparison.candidate_identity.campaign_version == CAMPAIGN_VERSION


def test_holds_suite_identity_constant(comparison):
    assert (
        comparison.baseline.campaign.matched_control_suite_sha256
        == comparison.candidate.campaign.matched_control_suite_sha256
    )
    assert (
        comparison.baseline.campaign.suite.evidence.sha256
        == comparison.candidate.campaign.suite.evidence.sha256
    )


def test_every_case_holds_audio_and_reference_constant(comparison):
    assert all(
        value.baseline.audio_asset_sha256
        == value.candidate.audio_asset_sha256
        == value.audio_asset_sha256
        and value.baseline.reference_transcript_sha256
        == value.candidate.reference_transcript_sha256
        == value.reference_transcript_sha256
        and value.baseline.normalized_reference_sha256
        == value.candidate.normalized_reference_sha256
        for value in comparison.cases
    )


def test_every_case_preserves_pair_key_arm_and_case_id(comparison):
    assert all(
        value.baseline.pair_key
        == value.candidate.pair_key
        == value.pair_key
        and value.baseline.arm == value.candidate.arm == value.arm
        and value.baseline.case_id == value.candidate.case_id == value.case_id
        for value in comparison.cases
    )


def test_candidate_is_lower_on_all_deliberate_babble_errors(comparison):
    babble = tuple(
        value
        for value in comparison.cases
        if value.arm
        == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
    )
    assert len(babble) == 16
    assert all(value.wer_delta < 0.0 for value in babble)
    assert all(value.cer_delta < 0.0 for value in babble)
    assert all(value.deletions_delta == -1 for value in babble)


def test_candidate_equals_baseline_on_all_controls(comparison):
    control = tuple(
        value
        for value in comparison.cases
        if value.arm
        == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
    )
    assert len(control) == 16
    assert all(value.wer_delta == 0.0 for value in control)
    assert all(value.cer_delta == 0.0 for value in control)
    assert all(value.deletions_delta == 0 for value in control)


def test_pair_difference_in_differences_is_exact(comparison):
    assert all(value.baseline.wer_delta > 0.0 for value in comparison.pairs)
    assert all(value.candidate.wer_delta == 0.0 for value in comparison.pairs)
    assert all(
        value.wer_degradation_delta == -value.baseline.wer_delta
        for value in comparison.pairs
    )
    assert all(
        value.cer_degradation_delta == -value.baseline.cer_delta
        for value in comparison.pairs
    )
    assert all(
        value.deletions_degradation_delta == -1
        for value in comparison.pairs
    )


def test_case_direction_counts_are_descriptive(comparison):
    assert comparison.aggregate["case_direction_counts"] == {
        "wer": {
            "candidate_higher": 0,
            "equal": 16,
            "candidate_lower": 16,
        },
        "cer": {
            "candidate_higher": 0,
            "equal": 16,
            "candidate_lower": 16,
        },
    }


def test_pair_direction_counts_are_descriptive(comparison):
    assert comparison.aggregate[
        "pair_noise_degradation_direction_counts"
    ] == {
        "wer": {
            "candidate_higher": 0,
            "equal": 0,
            "candidate_lower": 16,
        },
        "cer": {
            "candidate_higher": 0,
            "equal": 0,
            "candidate_lower": 16,
        },
    }


def test_word_alignment_totals_are_exact(comparison):
    assert comparison.aggregate["word_alignment_totals"] == {
        "baseline": {
            "substitutions": 0,
            "insertions": 0,
            "deletions": 16,
        },
        "candidate": {
            "substitutions": 0,
            "insertions": 0,
            "deletions": 0,
        },
        "candidate_minus_baseline": {
            "substitutions": 0,
            "insertions": 0,
            "deletions": -16,
        },
    }


def test_macro_means_use_equal_case_weighting(comparison):
    macro = comparison.aggregate["case_macro_mean"]
    assert macro["all"]["case_count"] == 32
    assert macro["babble"]["case_count"] == 16
    assert macro["control"]["case_count"] == 16
    assert macro["all"]["baseline"]["wer"] > 0.0
    assert macro["all"]["candidate"]["wer"] == 0.0
    assert macro["all"]["candidate"]["cer"] == 0.0
    assert macro["all"]["candidate_minus_baseline"]["wer"] < 0.0


def test_pair_macro_equals_mean_of_pair_differences(comparison):
    macro = comparison.aggregate["pair_noise_degradation_macro_mean"]
    expected_wer = sum(
        value.wer_degradation_delta for value in comparison.pairs
    ) / 16
    expected_cer = sum(
        value.cer_degradation_delta for value in comparison.pairs
    ) / 16
    assert macro["candidate_minus_baseline"]["wer"] == expected_wer
    assert macro["candidate_minus_baseline"]["cer"] == expected_cer


def test_payload_names_delta_directions_explicitly(comparison):
    methodology = comparison.payload["methodology"]
    assert methodology["case_delta"] == "candidate_minus_baseline"
    assert methodology["pair_noise_degradation"] == "babble_minus_control"
    assert methodology["difference_in_differences"] == (
        "candidate_babble_minus_control_minus_"
        "baseline_babble_minus_control"
    )
    assert methodology["lower_metric_values_are_better"] is True


def test_payload_binds_both_model_and_evidence_identities(comparison):
    payload = comparison.payload
    assert payload["models"]["baseline"]["model_key"] == BASELINE_MODEL_KEY
    assert payload["models"]["candidate"]["model_key"] == CANDIDATE_MODEL_KEY
    assert payload["upstream"]["baseline_metrics_sha256"] == (
        comparison.baseline.sha256
    )
    assert payload["upstream"]["candidate_metrics_sha256"] == (
        comparison.candidate.sha256
    )


def test_payload_contains_no_raw_transcripts_or_absolute_paths(comparison):
    encoded = json.dumps(comparison.payload, sort_keys=True)
    for metrics in (comparison.baseline, comparison.candidate):
        for binding in metrics.campaign.suite.cases:
            assert binding.case.reference_transcript not in encoded
            assert str(binding.media.path) not in encoded
        for result in metrics.campaign.campaign.completed_results:
            assert result.generated_transcript not in encoded


def test_payload_has_only_hash_commitments_for_model_outputs(comparison):
    first = comparison.payload["cases"][0]
    assert set(first["baseline_outputs"]) == {
        "generated_transcript_sha256",
        "normalized_generated_utf8_sha256",
        "execution_evidence_sha256",
    }
    assert set(first["candidate_outputs"]) == {
        "generated_transcript_sha256",
        "normalized_generated_utf8_sha256",
        "execution_evidence_sha256",
    }


def test_hash_is_canonical_and_reproducible(comparison, model_metrics):
    baseline, candidate = model_metrics
    rebuilt = build_asr_adversarial_voices_model_comparison_v1(
        baseline=baseline,
        candidate=candidate,
    )
    assert rebuilt == comparison
    assert rebuilt.payload == comparison.payload
    assert rebuilt.sha256 == comparison.sha256
    assert len(comparison.sha256) == 64


def test_rejects_identical_provider_model_identity(model_metrics):
    baseline, _candidate = model_metrics
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="distinct provider/model",
    ):
        build_asr_adversarial_voices_model_comparison_v1(
            baseline=baseline,
            candidate=baseline,
        )


@pytest.mark.parametrize("role", ["baseline", "candidate"])
def test_build_rejects_non_b7_input(model_metrics, role):
    baseline, candidate = model_metrics
    values = {"baseline": baseline, "candidate": candidate}
    values[role] = object()
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match=f"{role} requires the exact B7",
    ):
        build_asr_adversarial_voices_model_comparison_v1(**values)


@pytest.mark.parametrize(
    "field",
    ["baseline_metrics_sha256", "candidate_metrics_sha256"],
)
def test_rejects_changed_b7_commitment(comparison, field):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="B7 metrics commitments changed",
    ):
        replace(comparison, **{field: "0" * 64})


def test_case_type_rejects_changed_audio_identity(comparison):
    value = comparison.cases[0]
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="hold input evidence constant",
    ):
        replace(value, audio_asset_sha256="f" * 64)


def test_case_type_rejects_changed_reference_identity(comparison):
    value = comparison.cases[0]
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="hold input evidence constant",
    ):
        replace(value, reference_transcript_sha256="f" * 64)


def test_case_type_rejects_cross_case_candidate(comparison):
    value = comparison.cases[0]
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="hold input evidence constant",
    ):
        replace(value, candidate=comparison.cases[1].candidate)


def test_pair_type_rejects_cross_pair_candidate(comparison):
    value = comparison.pairs[0]
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="hold matched inputs constant",
    ):
        replace(value, candidate=comparison.pairs[1].candidate)


def test_bundle_rejects_case_reordering(comparison):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="case ordering changed",
    ):
        replace(comparison, cases=tuple(reversed(comparison.cases)))


def test_bundle_rejects_pair_reordering(comparison):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="pair ordering changed",
    ):
        replace(comparison, pairs=tuple(reversed(comparison.pairs)))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("development_evidence_only", False),
        ("both_metrics_reverified", False),
        ("fixed_inputs_verified", False),
        ("distinct_model_identities_verified", False),
        ("paired_model_deltas_computed", False),
        ("statistical_significance_claimed", True),
        ("qualification_threshold_applied", True),
        ("model_winner_declared", True),
        ("production_qualified", True),
        ("release_enforcement_eligible", True),
        ("official_release_verdict_modified", True),
    ],
)
def test_authority_boundary_fails_closed(comparison, field, value):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="authority boundary changed",
    ):
        replace(comparison, **{field: value})


def test_model_identity_rejects_untrimmed_fields(comparison):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="non-empty trimmed text",
    ):
        replace(comparison.baseline_identity, model_key=" model ")


def test_model_identity_rejects_invalid_hash(comparison):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="lowercase SHA-256",
    ):
        replace(comparison.baseline_identity, metrics_sha256="invalid")


def test_require_winner_fails_closed(comparison):
    with pytest.raises(
        ASRAdversarialVOiCESModelComparisonError,
        match="no threshold.*model winner",
    ):
        comparison.require_model_winner_declared()


def test_evidence_boundary_is_explicitly_non_qualifying(comparison):
    boundary = comparison.payload["evidence_boundary"]
    assert boundary["development_evidence_only"] is True
    assert boundary["statistical_significance_claimed"] is False
    assert boundary["qualification_threshold_applied"] is False
    assert boundary["model_winner_declared"] is False
    assert boundary["production_qualified"] is False
    assert boundary["release_enforcement_eligible"] is False
    assert boundary["official_release_verdict_modified"] is False


def test_population_constants_remain_exact(comparison):
    assert len(comparison.cases) == (
        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
    )
    assert len(comparison.pairs) == (
        ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
    )


def test_projection_types_are_frozen_slots_dataclasses(comparison):
    identity = comparison.baseline_identity
    case = comparison.cases[0]
    pair = comparison.pairs[0]
    for value in (identity, case, pair, comparison):
        with pytest.raises(
            (FrozenInstanceError, AttributeError, TypeError),
        ):
            value.unexpected = True
