from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json

import pytest

from app import (
    adversarial_asr_human_external_voices_frozen_reliability_qualification
    as frozen_module,
)
from app.adversarial_asr_human_external_voices_frozen_reliability_qualification import (
    ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_KEY,
    ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_VERSION,
    ASRAdversarialVOiCESFrozenReliabilityQualificationBundle,
    ASRAdversarialVOiCESFrozenReliabilityQualificationError,
    evaluate_asr_adversarial_voices_frozen_reliability_file_v1,
    evaluate_asr_adversarial_voices_frozen_reliability_qualification_v1,
)
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.reliability_qualification_policy import (
    ASRCriticalIntegrityConfidencePolicyV1,
    ASRReliabilityQualificationPolicyV1,
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _metric(*, candidate: bool = False) -> dict[str, int | float]:
    if candidate:
        return {
            "cer": 0.05,
            "deletions": 0,
            "insertions": 0,
            "substitutions": 1,
            "wer": 0.10,
        }
    return {
        "cer": 0.10,
        "deletions": 1,
        "insertions": 0,
        "substitutions": 2,
        "wer": 0.20,
    }


def _delta() -> dict[str, int | float]:
    return {
        "cer": -0.05,
        "deletions": -1,
        "insertions": 0,
        "substitutions": -1,
        "wer": -0.10,
    }


def _pair_key(index: int) -> dict[str, object]:
    return {
        "angle_degrees": 10,
        "microphone_id": 1 if index % 2 == 0 else 5,
        "room": f"rm{index // 4 + 1}",
        "source_key": [650 + index, 120_000 + index, index + 1],
    }


def _attempt(
    *,
    label: str,
    arm: str,
    case_id: str,
    ordinal: int,
) -> dict[str, object]:
    prefix = "a" if label == "baseline" else "b"
    return {
        "arm": arm,
        "case_id": case_id,
        "execution_environment_sha256": "c" * 64,
        "execution_evidence_sha256": f"{ordinal + 1:064x}",
        "execution_id": f"{label}.{case_id}",
        "generated_transcript_sha256": (
            prefix * 60 + f"{ordinal + 1:04x}"
        ),
        "status": "completed",
        "status_detail": None,
    }


def _section_identity(key: str) -> dict[str, object]:
    return deepcopy(frozen_module._SECTION_ARTIFACT_IDENTITIES[key])


def _campaign_section(
    *,
    label: str,
    attempts: list[dict[str, object]],
    campaign_evidence_sha256: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "artifact": _section_identity(f"b6_{label}_campaign"),
        "upstream": {
            "matched_control_suite_sha256": (
                frozen_module.B10D_FROZEN_EVIDENCE[
                    "matched_control_suite_sha256"
                ]
            ),
            "adversarial_suite_evidence_sha256": (
                frozen_module._ADVERSARIAL_SUITE_SHA256
            ),
            "campaign_evidence_sha256": campaign_evidence_sha256,
        },
        "campaign": {
            **frozen_module._MODEL_IDENTITIES[label],
            "attempt_count": 32,
            "status_counts": deepcopy(frozen_module._STATUS_COUNTS),
            "completed_pair_count": 16,
            "all_cases_completed": True,
            "ordered_attempts": attempts,
        },
        "evidence_boundary": {"development_evidence_only": True},
    }


def _metric_section(
    *,
    label: str,
    campaign_sha256: str,
    campaign_evidence_sha256: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "artifact": _section_identity(f"b7_{label}_metrics"),
        "model_identity": deepcopy(frozen_module._MODEL_IDENTITIES[label]),
        "upstream": {
            "matched_control_campaign_sha256": campaign_sha256,
            "campaign_evidence_sha256": campaign_evidence_sha256,
            "adversarial_suite_evidence_sha256": (
                frozen_module._ADVERSARIAL_SUITE_SHA256
            ),
        },
        "methodology": deepcopy(frozen_module._EXPECTED_B7_METHODOLOGY),
        "population": {},
        "aggregate": {},
        "evidence_boundary": {"development_evidence_only": True},
    }


def _case(
    *,
    arm: str,
    pair_index: int,
    ordinal: int,
    baseline_attempt: dict[str, object],
    candidate_attempt: dict[str, object],
) -> dict[str, object]:
    normalized_reference = "d" * 64
    return {
        "arm": arm,
        "case_id": baseline_attempt["case_id"],
        "baseline": _metric(),
        "candidate": _metric(candidate=True),
        "candidate_minus_baseline": _delta(),
        "baseline_outputs": {
            "execution_evidence_sha256": baseline_attempt[
                "execution_evidence_sha256"
            ],
            "generated_transcript_sha256": baseline_attempt[
                "generated_transcript_sha256"
            ],
            "normalized_generated_utf8_sha256": "e" * 64,
        },
        "candidate_outputs": {
            "execution_evidence_sha256": candidate_attempt[
                "execution_evidence_sha256"
            ],
            "generated_transcript_sha256": candidate_attempt[
                "generated_transcript_sha256"
            ],
            "normalized_generated_utf8_sha256": "f" * 64,
        },
        "fixed_inputs": {
            "audio_asset_sha256": f"{ordinal + 100:064x}",
            "reference_transcript_sha256": normalized_reference,
            "normalized_reference_utf8_sha256": normalized_reference,
        },
        "pair_key": _pair_key(pair_index),
    }


def _comparison_section(
    *,
    cases: list[dict[str, object]],
    baseline_campaign_sha256: str,
    candidate_campaign_sha256: str,
    baseline_metrics_sha256: str,
    candidate_metrics_sha256: str,
) -> dict[str, object]:
    zero_delta = {
        "cer": 0.0,
        "deletions": 0,
        "insertions": 0,
        "substitutions": 0,
        "wer": 0.0,
    }
    pairs = [
        {
            "pair_key": _pair_key(index),
            "baseline": {"babble_minus_control": deepcopy(zero_delta)},
            "candidate": {"babble_minus_control": deepcopy(zero_delta)},
            "candidate_minus_baseline_noise_degradation": deepcopy(
                zero_delta
            ),
        }
        for index in range(16)
    ]
    return {
        "schema_version": 1,
        "artifact": _section_identity("b8_comparison"),
        "upstream": {
            "matched_control_suite_sha256": (
                frozen_module.B10D_FROZEN_EVIDENCE[
                    "matched_control_suite_sha256"
                ]
            ),
            "adversarial_suite_evidence_sha256": (
                frozen_module._ADVERSARIAL_SUITE_SHA256
            ),
            "baseline_metrics_sha256": baseline_metrics_sha256,
            "candidate_metrics_sha256": candidate_metrics_sha256,
        },
        "models": {
            "baseline": {
                **frozen_module._MODEL_IDENTITIES["baseline"],
                "campaign_sha256": baseline_campaign_sha256,
                "metrics_sha256": baseline_metrics_sha256,
            },
            "candidate": {
                **frozen_module._MODEL_IDENTITIES["candidate"],
                "campaign_sha256": candidate_campaign_sha256,
                "metrics_sha256": candidate_metrics_sha256,
            },
        },
        "methodology": {},
        "cases": cases,
        "pairs": pairs,
        "aggregate": deepcopy(frozen_module._EXPECTED_B8_AGGREGATE),
        "evidence_boundary": {"development_evidence_only": True},
    }


def _b9_summary(
    *,
    label: str,
    campaign_sha256: str,
    campaign_evidence_sha256: str,
    metrics_sha256: str,
) -> dict[str, object]:
    return {
        **frozen_module._MODEL_IDENTITIES[label],
        "campaign_sha256": campaign_sha256,
        "campaign_evidence_sha256": campaign_evidence_sha256,
        "status_counts": deepcopy(frozen_module._STATUS_COUNTS),
        "completed_pair_count": 16,
        "metrics_sha256": metrics_sha256,
    }


def _frozen_payload() -> dict[str, object]:
    baseline_attempts: list[dict[str, object]] = []
    candidate_attempts: list[dict[str, object]] = []
    cases: list[dict[str, object]] = []
    for arm_index, arm in enumerate(("babble", "control")):
        for pair_index in range(16):
            ordinal = arm_index * 16 + pair_index
            case_id = f"voices-{arm}-case-{pair_index + 1:02d}"
            baseline = _attempt(
                label="baseline",
                arm=arm,
                case_id=case_id,
                ordinal=ordinal,
            )
            candidate = _attempt(
                label="candidate",
                arm=arm,
                case_id=case_id,
                ordinal=ordinal + 32,
            )
            baseline_attempts.append(baseline)
            candidate_attempts.append(candidate)
            cases.append(
                _case(
                    arm=arm,
                    pair_index=pair_index,
                    ordinal=ordinal,
                    baseline_attempt=baseline,
                    candidate_attempt=candidate,
                )
            )
    baseline_campaign_evidence = "1" * 64
    candidate_campaign_evidence = "2" * 64
    artifacts = {
        "b6_baseline_campaign": _campaign_section(
            label="baseline",
            attempts=baseline_attempts,
            campaign_evidence_sha256=baseline_campaign_evidence,
        ),
        "b6_candidate_campaign": _campaign_section(
            label="candidate",
            attempts=candidate_attempts,
            campaign_evidence_sha256=candidate_campaign_evidence,
        ),
    }
    baseline_campaign_sha256 = _sha(artifacts["b6_baseline_campaign"])
    candidate_campaign_sha256 = _sha(artifacts["b6_candidate_campaign"])
    artifacts["b7_baseline_metrics"] = _metric_section(
        label="baseline",
        campaign_sha256=baseline_campaign_sha256,
        campaign_evidence_sha256=baseline_campaign_evidence,
    )
    artifacts["b7_candidate_metrics"] = _metric_section(
        label="candidate",
        campaign_sha256=candidate_campaign_sha256,
        campaign_evidence_sha256=candidate_campaign_evidence,
    )
    baseline_metrics_sha256 = _sha(artifacts["b7_baseline_metrics"])
    candidate_metrics_sha256 = _sha(artifacts["b7_candidate_metrics"])
    artifacts["b8_comparison"] = _comparison_section(
        cases=cases,
        baseline_campaign_sha256=baseline_campaign_sha256,
        candidate_campaign_sha256=candidate_campaign_sha256,
        baseline_metrics_sha256=baseline_metrics_sha256,
        candidate_metrics_sha256=candidate_metrics_sha256,
    )
    comparison_sha256 = _sha(artifacts["b8_comparison"])
    artifacts["b9_execution"] = {
        "schema_version": 1,
        "artifact": _section_identity("b9_execution"),
        "upstream": {
            "matched_control_suite_sha256": (
                frozen_module.B10D_FROZEN_EVIDENCE[
                    "matched_control_suite_sha256"
                ]
            ),
            "adversarial_suite_evidence_sha256": (
                frozen_module._ADVERSARIAL_SUITE_SHA256
            ),
        },
        "status": "completed",
        "baseline": _b9_summary(
            label="baseline",
            campaign_sha256=baseline_campaign_sha256,
            campaign_evidence_sha256=baseline_campaign_evidence,
            metrics_sha256=baseline_metrics_sha256,
        ),
        "candidate": _b9_summary(
            label="candidate",
            campaign_sha256=candidate_campaign_sha256,
            campaign_evidence_sha256=candidate_campaign_evidence,
            metrics_sha256=candidate_metrics_sha256,
        ),
        "comparison_sha256": comparison_sha256,
        "evidence_boundary": {"development_evidence_only": True},
    }
    section_sha256s = {key: _sha(value) for key, value in artifacts.items()}
    return {
        "schema_version": 1,
        "artifact": {
            "key": frozen_module.B10D_ARTIFACT_KEY,
            "version": frozen_module.B10D_ARTIFACT_VERSION,
            "type": frozen_module.B10D_ARTIFACT_TYPE,
        },
        "artifact_sha256s": section_sha256s,
        "artifacts": artifacts,
        "frozen_evidence": deepcopy(frozen_module.B10D_FROZEN_EVIDENCE),
        "models": deepcopy(frozen_module.B10D_MODELS),
        "runtime": deepcopy(frozen_module.B10D_RUNTIME),
        "source_code": {
            "branch": frozen_module.B10D_SOURCE_BRANCH,
            "git_head": frozen_module.B10D_SOURCE_GIT_HEAD,
        },
        "evidence_boundary": deepcopy(frozen_module._ROOT_EVIDENCE_BOUNDARY),
    }


def _pin(
    monkeypatch,
    payload: dict[str, object],
) -> bytes:
    artifacts = payload["artifacts"]
    section_sha256s = {key: _sha(value) for key, value in artifacts.items()}
    payload["artifact_sha256s"] = section_sha256s
    raw = _canonical(payload)
    monkeypatch.setattr(frozen_module, "B10D_ARTIFACT_BYTES", len(raw))
    monkeypatch.setattr(
        frozen_module,
        "B10D_ARTIFACT_SHA256",
        hashlib.sha256(raw).hexdigest(),
    )
    monkeypatch.setattr(
        frozen_module,
        "B10D_ARTIFACT_SHA256S",
        section_sha256s,
    )
    return raw


def _policy() -> ASRReliabilityQualificationPolicyV1:
    return ASRReliabilityQualificationPolicyV1(
        minimum_hetren_reliability_index=90.0,
        minimum_reliability_performance_index=90.0,
        minimum_evidence_assurance_index=100.0,
        minimum_operational_fitness_index=95.0,
        minimum_matched_control_robustness_score=90.0,
        minimum_critical_integrity_group_score=100.0,
        minimum_matched_control_pairs=16,
        matched_release_assurance=ASRMatchedReleaseAssurancePolicyV1(
            interval=PairedIntervalPolicy(
                method=PairedIntervalMethod.BOOTSTRAP_PERCENTILE_V1,
                confidence_level=0.95,
                minimum_usable_pairs=16,
                resamples=10_000,
                random_seed=20_260_822,
            ),
            normalized_wer_noninferiority_margin=0.02,
            normalized_cer_noninferiority_margin=0.01,
        ),
        critical_integrity_confidence=(
            ASRCriticalIntegrityConfidencePolicyV1(
                familywise_confidence_level_ppm=950_000,
                minimum_conclusive_observations_per_group=30,
                minimum_preservation_lower_bound_ppm=900_000,
            )
        ),
    )


@pytest.fixture
def pinned_artifact(monkeypatch):
    payload = _frozen_payload()
    return payload, _pin(monkeypatch, payload)


def test_constants_are_versioned_namespaced_and_pinned():
    assert ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_FROZEN_QUALIFICATION_KEY.startswith(
        "hetren.asr."
    )
    assert frozen_module.B10D_ARTIFACT_BYTES == 274_649
    assert len(frozen_module.B10D_ARTIFACT_SHA256) == 64
    assert set(frozen_module.B10D_ARTIFACT_SHA256S) == {
        "b6_baseline_campaign",
        "b6_candidate_campaign",
        "b7_baseline_metrics",
        "b7_candidate_metrics",
        "b8_comparison",
        "b9_execution",
    }


def test_parser_rejects_duplicate_keys():
    with pytest.raises(
        ASRAdversarialVOiCESFrozenReliabilityQualificationError,
        match="duplicate key",
    ):
        frozen_module._parse_json(b'{"schema_version":1,"schema_version":1}')


def test_exact_pinned_file_and_all_sections_verify(pinned_artifact):
    payload, raw = pinned_artifact
    verified = frozen_module._verify_frozen_artifact(raw)

    assert verified == payload
    assert len(verified["artifacts"]["b8_comparison"]["cases"]) == 32
    assert len(verified["artifacts"]["b8_comparison"]["pairs"]) == 16


def test_raw_byte_tampering_fails_before_json_projection(pinned_artifact):
    _payload, raw = pinned_artifact
    tampered = raw[:-1] + (b" " if raw[-1:] != b" " else b"\n")

    with pytest.raises(
        ASRAdversarialVOiCESFrozenReliabilityQualificationError,
        match="byte length|SHA-256",
    ):
        frozen_module._verify_frozen_artifact(tampered)


def test_independently_repinned_cross_link_tampering_fails(monkeypatch):
    payload = _frozen_payload()
    payload["artifacts"]["b9_execution"]["comparison_sha256"] = "0" * 64
    raw = _pin(monkeypatch, payload)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenReliabilityQualificationError,
        match="B9 status or upstream linkage",
    ):
        frozen_module._verify_frozen_artifact(raw)


def test_independently_repinned_b8_model_hash_link_tampering_fails(
    monkeypatch,
):
    payload = _frozen_payload()
    payload["artifacts"]["b8_comparison"]["models"]["baseline"][
        "campaign_sha256"
    ] = "0" * 64
    raw = _pin(monkeypatch, payload)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenReliabilityQualificationError,
        match="B8 identity, links, or aggregate",
    ):
        frozen_module._verify_frozen_artifact(raw)


def test_independently_repinned_case_output_link_tampering_fails(monkeypatch):
    payload = _frozen_payload()
    payload["artifacts"]["b8_comparison"]["cases"][0][
        "baseline_outputs"
    ]["execution_evidence_sha256"] = "9" * 64
    raw = _pin(monkeypatch, payload)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenReliabilityQualificationError,
        match="B6-to-B8 execution output linkage",
    ):
        frozen_module._verify_frozen_artifact(raw)


def test_frozen_metrics_project_to_local_ids_and_canonical_metrics(
    pinned_artifact,
):
    payload, _raw = pinned_artifact
    records = frozen_module._observation_records(payload)
    cohorts = frozen_module._cohorts(payload)

    assert len(records) == 128
    assert {record.evaluation_run_id for record in records} == {1, 2}
    assert {record.metric_key for record in records} == {
        NORMALIZED_WER_METRIC.key,
        NORMALIZED_CER_METRIC.key,
    }
    assert cohorts.total_cases == 32
    assert cohorts.complete is True
    assert cohorts.integrity_valid is True


def test_frozen_scoring_withholds_unsupported_critical_and_repeatability(
    pinned_artifact,
):
    payload, _raw = pinned_artifact
    evidence = frozen_module._scoring_evidence(payload)
    performance = evidence.performance

    assert performance.matched_control_robustness is not None
    assert performance.matched_control_robustness.wer_differential == (
        0.030505952380952384
    )
    assert performance.matched_control_robustness.cer_differential == (
        0.03417174796747967
    )
    assert performance.critical_number_integrity is None
    assert performance.critical_identifier_integrity is None
    assert performance.critical_terminology_integrity is None
    assert evidence.assurance.reproducibility_verified is None
    assert evidence.missing_output_gate.violation_count == 0
    assert evidence.unexpected_output_gate.violation_count == 0


def test_public_qualification_is_inconclusive_and_non_authoritative(
    pinned_artifact,
):
    _payload, raw = pinned_artifact
    bundle = (
        evaluate_asr_adversarial_voices_frozen_reliability_qualification_v1(
            artifact_bytes=raw,
            policy=_policy(),
        )
    )
    payload = bundle.payload

    assert payload["decision"]["verdict"] == "inconclusive"
    assert payload["support"]["critical_integrity"]["sufficient"] is False
    assert payload["run_identity"][
        "database_evaluation_run_identity_claimed"
    ] is False
    assert payload["methodology"]["raw_transcript_metric_recomputation"] is False
    assert payload["methodology"]["live_b9_object_rehydration"] is False
    boundary = payload["evidence_boundary"]
    assert boundary["non_authoritative_model_qualification_verdict_issued"]
    assert not boundary["critical_content_qualification_evidence_claimed"]
    assert not boundary["certification_issued"]
    assert not boundary["production_qualified"]
    assert not boundary["release_enforcement_eligible"]
    assert not boundary["official_release_verdict_modified"]
    assert len(bundle.sha256) == 64

    with pytest.raises(
        ASRAdversarialVOiCESFrozenReliabilityQualificationError,
        match="cannot rehydrate",
    ):
        bundle.require_live_b9_execution()
    with pytest.raises(
        ASRAdversarialVOiCESFrozenReliabilityQualificationError,
        match="does not certify",
    ):
        bundle.require_certification()
    with pytest.raises(
        ASRAdversarialVOiCESFrozenReliabilityQualificationError,
        match="does not authorize release enforcement",
    ):
        bundle.require_release_enforcement()


def test_file_api_reads_without_embedding_absolute_path(
    pinned_artifact,
    tmp_path,
):
    _payload, raw = pinned_artifact
    path = tmp_path / "b10d.json"
    path.write_bytes(raw)

    bundle = evaluate_asr_adversarial_voices_frozen_reliability_file_v1(
        artifact_path=path,
        policy=_policy(),
    )

    assert str(path) not in json.dumps(bundle.payload)


def test_bundle_is_frozen(pinned_artifact):
    _payload, raw = pinned_artifact
    bundle = ASRAdversarialVOiCESFrozenReliabilityQualificationBundle(
        artifact_bytes=raw,
        policy=_policy(),
    )

    with pytest.raises(FrozenInstanceError):
        bundle.policy = object()


def test_public_api_rejects_non_policy_before_artifact_use():
    with pytest.raises(
        ASRAdversarialVOiCESFrozenReliabilityQualificationError,
        match="exact B11A policy",
    ):
        evaluate_asr_adversarial_voices_frozen_reliability_qualification_v1(
            artifact_bytes=b"not-used",
            policy=object(),
        )
