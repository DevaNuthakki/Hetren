from __future__ import annotations

import copy
import hashlib

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_corpus_manifest import (
    ASRAdversarialCorpusProvenanceType,
)
from hvee.packs.asr.adversarial_human_external_evidence import (
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID,
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_SHA256,
    ASRAdversarialHumanExternalProvenanceRecord,
    ASRAdversarialHumanExternalRepositoryMediaPolicy,
    ASRAdversarialHumanExternalRightsBasis,
    ASRAdversarialHumanExternalRightsRecord,
    ASRAdversarialHumanExternalSourceKind,
    build_asr_adversarial_human_external_methodology_v1,
    build_asr_adversarial_human_external_provenance_record_v1,
    build_asr_adversarial_human_external_rights_record_v1,
    calculate_asr_adversarial_human_external_sha256,
    verify_asr_adversarial_human_external_methodology_v1,
    verify_asr_adversarial_human_external_record_pair_v1,
    verify_asr_adversarial_human_external_record_v1,
)


def _digest(
    label: str,
) -> str:
    return hashlib.sha256(
        label.encode(
            "utf-8"
        )
    ).hexdigest()


def _provenance(
    *,
    source_kind: (
        ASRAdversarialHumanExternalSourceKind
    ) = (
        ASRAdversarialHumanExternalSourceKind
        .LICENSED_DATASET
    ),
    source_audio_sha256: str | None = None,
    source_locator_sha256: str | None = None,
) -> ASRAdversarialHumanExternalProvenanceRecord:
    return ASRAdversarialHumanExternalProvenanceRecord(
        record_id=(
            "source.human-example-v1"
        ),
        case_id=(
            "human.clean-example"
        ),
        source_kind=source_kind,
        source_collection_key=(
            "example-speech-corpus"
        ),
        source_collection_version=(
            "2026.08"
        ),
        source_item_id=(
            "speaker-001/utterance-009"
        ),
        source_audio_sha256=(
            source_audio_sha256
            or _digest(
                "audio"
            )
        ),
        reference_transcript_sha256=(
            _digest(
                "transcript"
            )
        ),
        source_metadata_sha256=(
            _digest(
                "metadata"
            )
        ),
        source_locator_sha256=(
            source_locator_sha256
            or _digest(
                "locator"
            )
        ),
        declared_speaker_metadata_sha256=(
            _digest(
                "speaker-metadata"
            )
        ),
        declared_recording_metadata_sha256=(
            _digest(
                "recording-metadata"
            )
        ),
    )


def _rights(
    *,
    source_kind: (
        ASRAdversarialHumanExternalSourceKind
    ) = (
        ASRAdversarialHumanExternalSourceKind
        .LICENSED_DATASET
    ),
    source_audio_sha256: str | None = None,
    source_locator_sha256: str | None = None,
) -> ASRAdversarialHumanExternalRightsRecord:
    basis = {
        (
            ASRAdversarialHumanExternalSourceKind
            .LICENSED_DATASET
        ): (
            ASRAdversarialHumanExternalRightsBasis
            .DATASET_LICENSE
        ),
        (
            ASRAdversarialHumanExternalSourceKind
            .PURPOSE_RECORDED
        ): (
            ASRAdversarialHumanExternalRightsBasis
            .RECORDED_CONSENT
        ),
    }[
        source_kind
    ]

    return ASRAdversarialHumanExternalRightsRecord(
        record_id=(
            "rights.human-example-v1"
        ),
        case_id=(
            "human.clean-example"
        ),
        source_kind=source_kind,
        source_audio_sha256=(
            source_audio_sha256
            or _digest(
                "audio"
            )
        ),
        source_locator_sha256=(
            source_locator_sha256
            or _digest(
                "locator"
            )
        ),
        rights_basis=basis,
        rights_evidence_sha256=(
            _digest(
                "rights-evidence"
            )
        ),
        terms_evidence_sha256=(
            _digest(
                "terms-evidence"
            )
        ),
        repository_media_policy=(
            ASRAdversarialHumanExternalRepositoryMediaPolicy
            .NOT_COMMITTED
        ),
        review_status=(
            "not_adjudicated"
        ),
        development_use_only=True,
    )


def test_human_external_methodology_is_deterministic():
    first = (
        build_asr_adversarial_human_external_methodology_v1()
    )
    second = (
        build_asr_adversarial_human_external_methodology_v1()
    )

    assert first == second
    assert first.sha256 == second.sha256
    assert len(
        first.sha256
    ) == 64

    verified = (
        verify_asr_adversarial_human_external_methodology_v1(
            payload=first.payload,
            expected_sha256=first.sha256,
        )
    )

    assert verified == first


def test_human_external_methodology_v1_identity_is_frozen():
    bundle = (
        build_asr_adversarial_human_external_methodology_v1()
    )

    assert (
        ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_SHA256
        == (
            "099c36a4c21b4ae2307e7ab3624061b6"
            "265809ca76fd0edb50402ae559e2067e"
        )
    )

    assert (
        bundle.sha256
        == ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_SHA256
    )


def test_human_external_methodology_rejects_other_expected_identity():
    bundle = (
        build_asr_adversarial_human_external_methodology_v1()
    )

    with pytest.raises(
        HveeContractError,
        match="identity is unsupported",
    ):
        verify_asr_adversarial_human_external_methodology_v1(
            payload=bundle.payload,
            expected_sha256=_digest(
                "other-methodology"
            ),
        )


def test_human_external_methodology_uses_separate_corpus_slice():
    bundle = (
        build_asr_adversarial_human_external_methodology_v1()
    )

    assert (
        ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID
        == "qualification.human-external-v1"
    )

    assert bundle.payload[
        "methodology"
    ][
        "corpus_slice"
    ] == {
        "corpus_id": (
            "qualification.human-external-v1"
        ),
        "corpus_version": "1.0.0",
    }


def test_human_external_methodology_maps_source_classes_to_manifest():
    bundle = (
        build_asr_adversarial_human_external_methodology_v1()
    )

    classes = bundle.payload[
        "methodology"
    ][
        "source_classes"
    ]

    assert classes == [
        {
            "source_kind": (
                "licensed_dataset"
            ),
            "manifest_provenance_type": (
                ASRAdversarialCorpusProvenanceType
                .LICENSED_EXTERNAL
                .value
            ),
            "rights_basis": (
                "dataset_license"
            ),
        },
        {
            "source_kind": (
                "purpose_recorded"
            ),
            "manifest_provenance_type": (
                ASRAdversarialCorpusProvenanceType
                .PURPOSE_RECORDED
                .value
            ),
            "rights_basis": (
                "recorded_consent"
            ),
        },
    ]


def test_human_external_methodology_keeps_scientific_boundary_negative():
    bundle = (
        build_asr_adversarial_human_external_methodology_v1()
    )

    assert bundle.payload[
        "scientific_boundary"
    ] == {
        "human_external_source_contract_defined": True,
        "human_source_material_present": False,
        "human_source_audio_verified": False,
        "rights_adjudicated": False,
        "speaker_attributes_inferred": False,
        "microphone_class_inferred": False,
        "human_acoustic_diversity_established": False,
        "qualification_threshold_applied": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def test_human_external_methodology_forbids_attribute_inference():
    bundle = (
        build_asr_adversarial_human_external_methodology_v1()
    )

    policy = bundle.payload[
        "methodology"
    ][
        "declared_metadata_policy"
    ]

    assert (
        policy[
            "speaker_attributes_inferred_from_audio"
        ]
        is False
    )
    assert (
        policy[
            "microphone_class_inferred_from_audio"
        ]
        is False
    )
    assert (
        policy[
            "source_declared_speaker_metadata_may_be_committed"
        ]
        is True
    )
    assert (
        policy[
            "source_declared_recording_metadata_may_be_committed"
        ]
        is True
    )


def test_human_external_provenance_is_deterministic_and_commitment_only():
    first = (
        build_asr_adversarial_human_external_provenance_record_v1(
            _provenance()
        )
    )
    second = (
        build_asr_adversarial_human_external_provenance_record_v1(
            _provenance()
        )
    )

    assert first == second
    assert first.sha256 == second.sha256

    record = first.payload[
        "record"
    ]

    assert record[
        "source_kind"
    ] == "licensed_dataset"

    assert record[
        "commitments"
    ][
        "source_audio_sha256"
    ] == _digest(
        "audio"
    )

    assert record[
        "declared_metadata_commitments"
    ] == {
        "speaker_metadata_sha256": (
            _digest(
                "speaker-metadata"
            )
        ),
        "recording_metadata_sha256": (
            _digest(
                "recording-metadata"
            )
        ),
    }

    serialized = str(
        first.payload
    )

    assert "https://" not in serialized
    assert "speaker accent" not in serialized


def test_human_external_rights_remain_non_adjudicating():
    bundle = (
        build_asr_adversarial_human_external_rights_record_v1(
            _rights()
        )
    )

    record = bundle.payload[
        "record"
    ]

    assert record[
        "rights_basis"
    ] == "dataset_license"
    assert record[
        "review_status"
    ] == "not_adjudicated"
    assert record[
        "development_use_only"
    ] is True

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "rights_adjudicated"
    ] is False
    assert boundary[
        "speaker_attributes_inferred"
    ] is False
    assert boundary[
        "human_acoustic_diversity_established"
    ] is False


def test_purpose_recorded_source_requires_consent_basis():
    record = _rights(
        source_kind=(
            ASRAdversarialHumanExternalSourceKind
            .PURPOSE_RECORDED
        )
    )

    assert (
        record.rights_basis
        == ASRAdversarialHumanExternalRightsBasis
        .RECORDED_CONSENT
    )

    bundle = (
        build_asr_adversarial_human_external_rights_record_v1(
            record
        )
    )

    assert bundle.payload[
        "record"
    ][
        "rights_basis"
    ] == "recorded_consent"


def test_rights_record_rejects_mismatched_source_kind_and_basis():
    with pytest.raises(
        HveeContractError,
        match="does not match",
    ):
        ASRAdversarialHumanExternalRightsRecord(
            record_id=(
                "rights.bad-source-v1"
            ),
            case_id=(
                "human.bad-source"
            ),
            source_kind=(
                ASRAdversarialHumanExternalSourceKind
                .LICENSED_DATASET
            ),
            source_audio_sha256=(
                _digest(
                    "audio"
                )
            ),
            source_locator_sha256=(
                _digest(
                    "locator"
                )
            ),
            rights_basis=(
                ASRAdversarialHumanExternalRightsBasis
                .RECORDED_CONSENT
            ),
            rights_evidence_sha256=(
                _digest(
                    "rights"
                )
            ),
            terms_evidence_sha256=(
                _digest(
                    "terms"
                )
            ),
            repository_media_policy=(
                ASRAdversarialHumanExternalRepositoryMediaPolicy
                .NOT_COMMITTED
            ),
            review_status=(
                "not_adjudicated"
            ),
            development_use_only=True,
        )


@pytest.mark.parametrize(
    (
        "review_status",
        "development_use_only",
    ),
    (
        (
            "approved",
            True,
        ),
        (
            "not_adjudicated",
            False,
        ),
    ),
)
def test_rights_record_cannot_claim_adjudication_or_production_use(
    review_status: str,
    development_use_only: bool,
):
    with pytest.raises(
        HveeContractError,
    ):
        ASRAdversarialHumanExternalRightsRecord(
            record_id=(
                "rights.invalid-boundary-v1"
            ),
            case_id=(
                "human.invalid-boundary"
            ),
            source_kind=(
                ASRAdversarialHumanExternalSourceKind
                .LICENSED_DATASET
            ),
            source_audio_sha256=(
                _digest(
                    "audio"
                )
            ),
            source_locator_sha256=(
                _digest(
                    "locator"
                )
            ),
            rights_basis=(
                ASRAdversarialHumanExternalRightsBasis
                .DATASET_LICENSE
            ),
            rights_evidence_sha256=(
                _digest(
                    "rights"
                )
            ),
            terms_evidence_sha256=(
                _digest(
                    "terms"
                )
            ),
            repository_media_policy=(
                ASRAdversarialHumanExternalRepositoryMediaPolicy
                .NOT_COMMITTED
            ),
            review_status=review_status,
            development_use_only=(
                development_use_only
            ),
        )


def test_human_external_record_pair_binds_same_exact_source():
    provenance = (
        build_asr_adversarial_human_external_provenance_record_v1(
            _provenance()
        )
    )
    rights = (
        build_asr_adversarial_human_external_rights_record_v1(
            _rights()
        )
    )

    verified = (
        verify_asr_adversarial_human_external_record_pair_v1(
            provenance=provenance,
            rights=rights,
        )
    )

    assert verified == (
        provenance,
        rights,
    )


def test_rehashed_pair_substitution_is_new_pair_identity():
    substituted_audio_sha256 = _digest(
        "substituted-audio"
    )

    provenance = (
        build_asr_adversarial_human_external_provenance_record_v1(
            _provenance(
                source_audio_sha256=(
                    substituted_audio_sha256
                )
            )
        )
    )

    rights = (
        build_asr_adversarial_human_external_rights_record_v1(
            _rights(
                source_audio_sha256=(
                    substituted_audio_sha256
                )
            )
        )
    )

    original_provenance = (
        build_asr_adversarial_human_external_provenance_record_v1(
            _provenance()
        )
    )

    original_rights = (
        build_asr_adversarial_human_external_rights_record_v1(
            _rights()
        )
    )

    assert (
        provenance.sha256
        != original_provenance.sha256
    )

    assert (
        rights.sha256
        != original_rights.sha256
    )

    verified = (
        verify_asr_adversarial_human_external_record_pair_v1(
            provenance=provenance,
            rights=rights,
        )
    )

    assert verified == (
        provenance,
        rights,
    )


def test_human_external_record_pair_rejects_audio_substitution():
    provenance = (
        build_asr_adversarial_human_external_provenance_record_v1(
            _provenance()
        )
    )
    rights = (
        build_asr_adversarial_human_external_rights_record_v1(
            _rights(
                source_audio_sha256=(
                    _digest(
                        "substituted-audio"
                    )
                )
            )
        )
    )

    with pytest.raises(
        HveeContractError,
        match="same source",
    ):
        verify_asr_adversarial_human_external_record_pair_v1(
            provenance=provenance,
            rights=rights,
        )


def test_human_external_record_pair_rejects_locator_substitution():
    provenance = (
        build_asr_adversarial_human_external_provenance_record_v1(
            _provenance()
        )
    )
    rights = (
        build_asr_adversarial_human_external_rights_record_v1(
            _rights(
                source_locator_sha256=(
                    _digest(
                        "other-locator"
                    )
                )
            )
        )
    )

    with pytest.raises(
        HveeContractError,
        match="same source",
    ):
        verify_asr_adversarial_human_external_record_pair_v1(
            provenance=provenance,
            rights=rights,
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "speaker_metadata_sha256",
        "recording_metadata_sha256",
    ),
)
def test_human_provenance_verifier_rejects_metadata_tampering_without_rehash(
    field_name: str,
):
    original = (
        build_asr_adversarial_human_external_provenance_record_v1(
            _provenance()
        )
    )

    payload = copy.deepcopy(
        original.payload
    )

    payload[
        "record"
    ][
        "declared_metadata_commitments"
    ][
        field_name
    ] = _digest(
        "tampered"
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_human_external_record_v1(
            payload=payload,
            expected_sha256=original.sha256,
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "speaker_metadata_sha256",
        "recording_metadata_sha256",
    ),
)
def test_human_provenance_rehashed_metadata_substitution_changes_identity(
    field_name: str,
):
    original = (
        build_asr_adversarial_human_external_provenance_record_v1(
            _provenance()
        )
    )

    payload = copy.deepcopy(
        original.payload
    )

    substituted_sha256 = _digest(
        "substituted-metadata"
    )

    payload[
        "record"
    ][
        "declared_metadata_commitments"
    ][
        field_name
    ] = substituted_sha256

    substituted_record_sha256 = (
        calculate_asr_adversarial_human_external_sha256(
            payload
        )
    )

    assert (
        substituted_record_sha256
        != original.sha256
    )

    verified = (
        verify_asr_adversarial_human_external_record_v1(
            payload=payload,
            expected_sha256=(
                substituted_record_sha256
            ),
        )
    )

    assert (
        verified.sha256
        == substituted_record_sha256
    )

    assert (
        verified.payload[
            "record"
        ][
            "declared_metadata_commitments"
        ][
            field_name
        ]
        == substituted_sha256
    )


def test_human_rights_rehashed_policy_substitution_changes_identity():
    original = (
        build_asr_adversarial_human_external_rights_record_v1(
            _rights()
        )
    )

    payload = copy.deepcopy(
        original.payload
    )

    payload[
        "record"
    ][
        "repository_media_policy"
    ] = (
        "committed_with_separate_rights_evidence"
    )

    substituted_record_sha256 = (
        calculate_asr_adversarial_human_external_sha256(
            payload
        )
    )

    assert (
        substituted_record_sha256
        != original.sha256
    )

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_human_external_record_v1(
            payload=payload,
            expected_sha256=original.sha256,
        )

    verified = (
        verify_asr_adversarial_human_external_record_v1(
            payload=payload,
            expected_sha256=(
                substituted_record_sha256
            ),
        )
    )

    assert (
        verified.sha256
        == substituted_record_sha256
    )

    assert verified.payload[
        "record"
    ][
        "repository_media_policy"
    ] == (
        "committed_with_separate_rights_evidence"
    )


def test_human_rights_verifier_rejects_unknown_field_even_if_rehashed():
    original = (
        build_asr_adversarial_human_external_rights_record_v1(
            _rights()
        )
    )

    payload = copy.deepcopy(
        original.payload
    )

    payload[
        "record"
    ][
        "legal_valid"
    ] = True

    forged_sha256 = (
        calculate_asr_adversarial_human_external_sha256(
            payload
        )
    )

    with pytest.raises(
        HveeContractError,
        match="invalid fields",
    ):
        verify_asr_adversarial_human_external_record_v1(
            payload=payload,
            expected_sha256=forged_sha256,
        )


def test_human_methodology_rejects_tampering_even_if_rehashed():
    original = (
        build_asr_adversarial_human_external_methodology_v1()
    )

    payload = copy.deepcopy(
        original.payload
    )

    payload[
        "scientific_boundary"
    ][
        "human_acoustic_diversity_established"
    ] = True

    forged_sha256 = (
        calculate_asr_adversarial_human_external_sha256(
            payload
        )
    )

    with pytest.raises(
        HveeContractError,
        match="identity is unsupported",
    ):
        verify_asr_adversarial_human_external_methodology_v1(
            payload=payload,
            expected_sha256=forged_sha256,
        )


def test_human_external_contract_is_publicly_exported():
    import hvee.packs.asr as asr_pack

    expected = {
        "ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID",
        "ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_SHA256",
        "ASRAdversarialHumanExternalProvenanceRecord",
        "ASRAdversarialHumanExternalRightsRecord",
        "ASRAdversarialHumanExternalSourceKind",
        "build_asr_adversarial_human_external_methodology_v1",
        "verify_asr_adversarial_human_external_record_pair_v1",
    }

    assert expected.issubset(
        set(
            asr_pack.__all__
        )
    )

    for name in expected:
        assert hasattr(
            asr_pack,
            name,
        )
