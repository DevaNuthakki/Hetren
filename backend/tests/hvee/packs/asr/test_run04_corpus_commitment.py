import hashlib
from copy import deepcopy
from dataclasses import replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.run04_corpus_commitment import (
    ASRRun04AccentEvidenceKind,
    ASRRun04CaseBinding,
    ASRRun04LabelCommitmentScheme,
    ASRRun04RightsReviewStatus,
    ASRRun04SpeakerBinding,
    build_asr_run04_corpus_commitment_v1,
    calculate_asr_run04_corpus_commitment_sha256,
    verify_asr_run04_corpus_commitment_v1,
)
from hvee.packs.asr.run04_corpus_plan import (
    ASR_RUN04_CORPUS_PLAN_SHA256,
    build_asr_run04_corpus_plan_v1,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _definitions(
    *,
    rights_status: ASRRun04RightsReviewStatus = (
        ASRRun04RightsReviewStatus.APPROVED_FOR_DECLARED_USE
    ),
):
    plan = build_asr_run04_corpus_plan_v1().payload
    speaker_bindings = tuple(
        ASRRun04SpeakerBinding(
            speaker_slot_key=speaker["key"],
            source_speaker_identity_sha256=_digest(
                f"source-speaker:{speaker['key']}"
            ),
            speaker_provenance_sha256=_digest(
                f"speaker-provenance:{speaker['key']}"
            ),
            rights_record_sha256=_digest(
                f"speaker-rights:{speaker['key']}"
            ),
            rights_review_status=rights_status,
            accent_coverage_key=(
                f"accent.source-label-{index:02d}"
            ),
            accent_evidence_kind=(
                ASRRun04AccentEvidenceKind.SOURCE_DECLARED
            ),
            demographic_record_sha256=None,
            demographic_attributes_inferred=False,
        )
        for index, speaker in enumerate(
            plan["speaker_slots"],
            start=1,
        )
    )
    speaker_by_slot = {
        binding.speaker_slot_key: binding
        for binding in speaker_bindings
    }

    cases = []
    for case in plan["case_slots"]:
        is_valid = case["validity_class"] == "valid"
        is_zero_byte = case["invalid_family"] == "zero-byte-input"
        if is_valid:
            rights_sha256 = speaker_by_slot[
                case["speaker_slot_key"]
            ].rights_record_sha256
        else:
            rights_sha256 = _digest(
                f"invalid-rights:{case['key']}"
            )
        cases.append(
            ASRRun04CaseBinding(
                case_slot_key=case["key"],
                source_record_sha256=_digest(
                    f"source-record:{case['key']}"
                ),
                rights_record_sha256=rights_sha256,
                rights_review_status=rights_status,
                scenario_metadata_sha256=_digest(
                    f"scenario:{case['key']}"
                ),
                media_sha256=(
                    hashlib.sha256(b"").hexdigest()
                    if is_zero_byte
                    else _digest(f"media:{case['key']}")
                ),
                media_byte_length=(
                    0 if is_zero_byte else 10_000 + case["ordinal"]
                ),
                media_duration_ms=(
                    2_000 + case["ordinal"] if is_valid else 0
                ),
                media_container_key=(
                    "wav.pcm-s16le" if is_valid else "invalid.container"
                ),
                reference_label_commitment_sha256=(
                    _digest(f"transcript:{case['key']}")
                    if is_valid
                    else None
                ),
                reference_label_commitment_scheme=(
                    ASRRun04LabelCommitmentScheme.HMAC_SHA256
                    if is_valid
                    else None
                ),
                acoustic_measurement_sha256=(
                    _digest(f"acoustics:{case['key']}")
                    if is_valid
                    else None
                ),
                invalid_disposition_sha256=(
                    None
                    if is_valid
                    else _digest(f"invalid:{case['key']}")
                ),
            )
        )
    return speaker_bindings, tuple(cases)


def _reports() -> dict[str, str]:
    return {
        "accent_coverage_report_sha256": _digest("accent-report"),
        "demographic_balance_report_sha256": _digest(
            "demographic-report"
        ),
        "rights_review_report_sha256": _digest("rights-report"),
        "corpus_limitations_sha256": _digest("limitations"),
    }


def _build(
    *,
    speaker_bindings=None,
    case_bindings=None,
):
    default_speakers, default_cases = _definitions()
    speakers = (
        default_speakers
        if speaker_bindings is None
        else speaker_bindings
    )
    cases = default_cases if case_bindings is None else case_bindings
    reports = _reports()
    bundle = build_asr_run04_corpus_commitment_v1(
        speaker_bindings=speakers,
        case_bindings=cases,
        **reports,
    )
    return bundle, speakers, cases, reports


def test_complete_run04_corpus_commitment_verifies():
    bundle, speakers, cases, reports = _build()

    assert bundle.payload["corpus_plan_sha256"] == (
        ASR_RUN04_CORPUS_PLAN_SHA256
    )
    assert calculate_asr_run04_corpus_commitment_sha256(
        bundle.payload
    ) == bundle.sha256
    assert verify_asr_run04_corpus_commitment_v1(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
        speaker_bindings=speakers,
        case_bindings=cases,
        **reports,
    )


def test_complete_run04_corpus_commitment_has_exact_counts():
    bundle, _, _, _ = _build()
    report = bundle.payload["materialization_report"]

    assert report == {
        "speaker_binding_count": 16,
        "case_binding_count": 136,
        "valid_case_count": 128,
        "invalid_case_count": 8,
        "rights_approved_count": 16,
        "rights_pending_count": 0,
        "rights_rejected_count": 0,
        "case_rights_approved_count": 136,
        "case_rights_pending_count": 0,
        "case_rights_rejected_count": 0,
        "source_speaker_overlap_count": 0,
    }


def test_complete_run04_corpus_commitment_is_not_execution_authority():
    bundle, _, _, _ = _build()

    assert bundle.payload["evidence_boundary"] == {
        "fresh_corpus_materialized": True,
        "all_frozen_slots_bound": True,
        "rights_evidence_review_complete": True,
        "corpus_contract_satisfied": True,
        "ready_for_firewall_sealing": True,
        "holdout_membership_opened": False,
        "asr_execution_performed": False,
        "run04_execution_authorized": False,
        "run04_completed": False,
        "legal_advice_issued": False,
        "production_qualified": False,
    }


def test_run04_corpus_commitment_contains_only_opaque_content():
    bundle, _, _, _ = _build()
    serialized = str(bundle.payload)

    assert bundle.payload["content_boundary"][
        "opaque_commitments_only"
    ] is True
    assert "transcript_text" not in serialized
    assert "audio_bytes" not in serialized
    assert "source_path_value" not in serialized
    assert "model_output_text" not in serialized
    assert "reference_transcript_sha256" not in serialized


def test_pending_rights_prevent_corpus_contract_readiness():
    speakers, cases = _definitions()
    pending_speakers = (
        replace(
            speakers[0],
            rights_review_status=(
                ASRRun04RightsReviewStatus.PENDING_REVIEW
            ),
        ),
        *speakers[1:],
    )
    plan_cases = {
        case["key"]: case
        for case in build_asr_run04_corpus_plan_v1().payload[
            "case_slots"
        ]
    }
    pending_cases = tuple(
        replace(
            case,
            rights_review_status=(
                ASRRun04RightsReviewStatus.PENDING_REVIEW
            ),
        )
        if plan_cases[case.case_slot_key]["speaker_slot_key"]
        == speakers[0].speaker_slot_key
        else case
        for case in cases
    )
    bundle, _, _, _ = _build(
        speaker_bindings=pending_speakers,
        case_bindings=pending_cases,
    )

    report = bundle.payload["materialization_report"]
    boundary = bundle.payload["evidence_boundary"]
    assert report["rights_approved_count"] == 15
    assert report["rights_pending_count"] == 1
    assert report["case_rights_pending_count"] == 8
    assert boundary["corpus_contract_satisfied"] is False
    assert boundary["ready_for_firewall_sealing"] is False


def test_rejected_rights_prevent_corpus_contract_readiness():
    speakers, cases = _definitions()
    rejected_speakers = (
        replace(
            speakers[0],
            rights_review_status=ASRRun04RightsReviewStatus.REJECTED,
        ),
        *speakers[1:],
    )
    plan_cases = {
        case["key"]: case
        for case in build_asr_run04_corpus_plan_v1().payload[
            "case_slots"
        ]
    }
    rejected_cases = tuple(
        replace(
            case,
            rights_review_status=ASRRun04RightsReviewStatus.REJECTED,
        )
        if plan_cases[case.case_slot_key]["speaker_slot_key"]
        == speakers[0].speaker_slot_key
        else case
        for case in cases
    )
    bundle, _, _, _ = _build(
        speaker_bindings=rejected_speakers,
        case_bindings=rejected_cases,
    )

    report = bundle.payload["materialization_report"]
    assert report["rights_rejected_count"] == 1
    assert report["case_rights_rejected_count"] == 8
    assert bundle.payload["evidence_boundary"][
        "corpus_contract_satisfied"
    ] is False


def test_pending_invalid_case_rights_prevent_readiness():
    speakers, cases = _definitions()
    invalid_index = next(
        index
        for index, case in enumerate(cases)
        if case.reference_label_commitment_sha256 is None
    )
    changed = list(cases)
    changed[invalid_index] = replace(
        changed[invalid_index],
        rights_review_status=ASRRun04RightsReviewStatus.PENDING_REVIEW,
    )
    bundle, _, _, _ = _build(
        speaker_bindings=speakers,
        case_bindings=tuple(changed),
    )

    report = bundle.payload["materialization_report"]
    assert report["case_rights_pending_count"] == 1
    assert bundle.payload["evidence_boundary"][
        "ready_for_firewall_sealing"
    ] is False


def test_valid_case_rights_status_must_match_speaker():
    speakers, cases = _definitions()
    changed = (
        replace(
            cases[0],
            rights_review_status=(
                ASRRun04RightsReviewStatus.PENDING_REVIEW
            ),
        ),
        *cases[1:],
    )

    with pytest.raises(HveeContractError, match="status must match"):
        _build(
            speaker_bindings=speakers,
            case_bindings=changed,
        )


def test_run04_corpus_commitment_rejects_missing_case_slot():
    speakers, cases = _definitions()

    with pytest.raises(HveeContractError, match="every frozen case"):
        _build(
            speaker_bindings=speakers,
            case_bindings=cases[:-1],
        )


def test_run04_corpus_commitment_rejects_duplicate_media_identity():
    speakers, cases = _definitions()
    duplicated = (
        cases[0],
        replace(cases[1], media_sha256=cases[0].media_sha256),
        *cases[2:],
    )

    with pytest.raises(HveeContractError, match="media identities"):
        _build(
            speaker_bindings=speakers,
            case_bindings=duplicated,
        )


def test_run04_corpus_commitment_rejects_speaker_overlap():
    speakers, cases = _definitions()
    overlapped = (
        speakers[0],
        replace(
            speakers[1],
            source_speaker_identity_sha256=(
                speakers[0].source_speaker_identity_sha256
            ),
        ),
        *speakers[2:],
    )

    with pytest.raises(HveeContractError, match="cannot overlap"):
        _build(
            speaker_bindings=overlapped,
            case_bindings=cases,
        )


def test_run04_corpus_commitment_rejects_case_rights_mismatch():
    speakers, cases = _definitions()
    mismatched = (
        replace(cases[0], rights_record_sha256=_digest("wrong-rights")),
        *cases[1:],
    )

    with pytest.raises(HveeContractError, match="rights must match"):
        _build(
            speaker_bindings=speakers,
            case_bindings=mismatched,
        )


def test_run04_corpus_commitment_rejects_valid_case_without_acoustics():
    speakers, cases = _definitions()
    invalid = (
        replace(cases[0], acoustic_measurement_sha256=None),
        *cases[1:],
    )

    with pytest.raises(HveeContractError, match="acoustic measurements"):
        _build(
            speaker_bindings=speakers,
            case_bindings=invalid,
        )


def test_run04_corpus_commitment_requires_keyed_transcript_labels():
    speakers, cases = _definitions()
    invalid = (
        replace(cases[0], reference_label_commitment_scheme=None),
        *cases[1:],
    )

    with pytest.raises(HveeContractError, match="require HMAC-SHA256"):
        _build(
            speaker_bindings=speakers,
            case_bindings=invalid,
        )


def test_run04_corpus_commitment_rejects_invalid_transcript_label():
    speakers, cases = _definitions()
    invalid_index = next(
        index
        for index, case in enumerate(cases)
        if case.reference_label_commitment_sha256 is None
    )
    changed = list(cases)
    changed[invalid_index] = replace(
        changed[invalid_index],
        reference_label_commitment_sha256=_digest("not-allowed"),
        reference_label_commitment_scheme=(
            ASRRun04LabelCommitmentScheme.HMAC_SHA256
        ),
    )

    with pytest.raises(HveeContractError, match="cannot bind transcript"):
        _build(
            speaker_bindings=speakers,
            case_bindings=tuple(changed),
        )


def test_run04_corpus_commitment_enforces_zero_byte_slot():
    speakers, cases = _definitions()
    plan_cases = build_asr_run04_corpus_plan_v1().payload["case_slots"]
    zero_key = next(
        case["key"]
        for case in plan_cases
        if case["invalid_family"] == "zero-byte-input"
    )
    zero_index = next(
        index
        for index, case in enumerate(cases)
        if case.case_slot_key == zero_key
    )
    changed = list(cases)
    changed[zero_index] = replace(
        changed[zero_index],
        media_byte_length=1,
    )

    with pytest.raises(HveeContractError, match="must contain zero bytes"):
        _build(
            speaker_bindings=speakers,
            case_bindings=tuple(changed),
        )


def test_run04_speaker_binding_rejects_inferred_attributes():
    with pytest.raises(HveeContractError, match="cannot be inferred"):
        ASRRun04SpeakerBinding(
            speaker_slot_key="run04.speaker.test.human.01",
            source_speaker_identity_sha256=_digest("speaker"),
            speaker_provenance_sha256=_digest("provenance"),
            rights_record_sha256=_digest("rights"),
            rights_review_status=(
                ASRRun04RightsReviewStatus.APPROVED_FOR_DECLARED_USE
            ),
            accent_coverage_key=None,
            accent_evidence_kind=(
                ASRRun04AccentEvidenceKind.NOT_PROVIDED
            ),
            demographic_attributes_inferred=True,
        )


def test_run04_corpus_commitment_verifier_rejects_tampering():
    bundle, speakers, cases, reports = _build()
    tampered = deepcopy(bundle.payload)
    tampered["case_bindings"][0]["media_byte_length"] += 1

    assert not verify_asr_run04_corpus_commitment_v1(
        payload=tampered,
        expected_sha256=bundle.sha256,
        speaker_bindings=speakers,
        case_bindings=cases,
        **reports,
    )
