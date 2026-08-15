"""Human/external source contract for adversarial ASR evidence.

This module defines the source-visible methodology and immutable record
contracts used when Hetren evaluates real human speech obtained from either:

- a licensed external speech dataset, or
- a purpose-recorded source with separately retained consent evidence.

The contract binds content identities, transcript identities, source
metadata, source locators, and rights evidence by SHA-256. It intentionally
does not store raw source locators, consent documents, license documents,
speaker metadata, or recording metadata in these artifacts.

Speaker, accent, microphone, environment, demographic, and similar
attributes are never inferred from audio by this contract. Such metadata
may only be committed when it is explicitly supplied by the source.

Rights evidence is recorded but never legally adjudicated by Hetren.

This is development evidence only. It does not establish human acoustic
diversity, production qualification, certification, or release authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_corpus_manifest import (
    ASRAdversarialCorpusProvenanceType,
)


ASR_ADVERSARIAL_HUMAN_EXTERNAL_SCHEMA_VERSION = 1

ASR_ADVERSARIAL_HUMAN_EXTERNAL_VERSION = "1.0.0"

ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_KEY = (
    "hetren.asr.adversarial-human-external-methodology.en-us"
)

ASR_ADVERSARIAL_HUMAN_EXTERNAL_PROVENANCE_RECORD_KEY = (
    "hetren.asr.adversarial-human-external-provenance-record.en-us"
)

ASR_ADVERSARIAL_HUMAN_EXTERNAL_RIGHTS_RECORD_KEY = (
    "hetren.asr.adversarial-human-external-rights-record.en-us"
)

ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID = (
    "qualification.human-external-v1"
)

ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_VERSION = "1.0.0"

ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_SHA256 = (
    "099c36a4c21b4ae2307e7ab3624061b6"
    "265809ca76fd0edb50402ae559e2067e"
)


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)

_VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+$"
)

_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)


class ASRAdversarialHumanExternalSourceKind(StrEnum):
    """Declared origin class for one human source asset."""

    LICENSED_DATASET = "licensed_dataset"
    PURPOSE_RECORDED = "purpose_recorded"


class ASRAdversarialHumanExternalRightsBasis(StrEnum):
    """Declared evidence basis attached to one human source."""

    DATASET_LICENSE = "dataset_license"
    RECORDED_CONSENT = "recorded_consent"


class ASRAdversarialHumanExternalRepositoryMediaPolicy(StrEnum):
    """Repository handling policy for the raw source media."""

    NOT_COMMITTED = "not_committed"
    COMMITTED_WITH_SEPARATE_RIGHTS_EVIDENCE = (
        "committed_with_separate_rights_evidence"
    )


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _IDENTIFIER_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )

    return value


def _require_version(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _VERSION_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise HveeContractError(
            f"{name} must use semantic version text"
        )

    return value


def _require_non_empty_text(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value != value.strip()
    ):
        raise HveeContractError(
            f"{name} must be non-empty canonical text"
        )

    return value


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _SHA256_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _require_optional_sha256(
    *,
    name: str,
    value: object,
) -> str | None:
    if value is None:
        return None

    return _require_sha256(
        name=name,
        value=value,
    )


def _canonical_json(
    value: object,
) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "human external ASR evidence must "
            "contain deterministic JSON"
        ) from exc


def calculate_asr_adversarial_human_external_sha256(
    payload: object,
) -> str:
    """Hash canonical human/external ASR evidence."""

    return hashlib.sha256(
        _canonical_json(
            payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _require_exact_keys(
    *,
    name: str,
    value: object,
    expected: set[str],
) -> dict[str, object]:
    if (
        not isinstance(
            value,
            dict,
        )
        or set(
            value
        )
        != expected
    ):
        raise HveeContractError(
            f"{name} has invalid fields"
        )

    return value


def _parse_source_kind(
    value: object,
) -> ASRAdversarialHumanExternalSourceKind:
    try:
        return ASRAdversarialHumanExternalSourceKind(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "human external source kind is invalid"
        ) from exc


def _parse_rights_basis(
    value: object,
) -> ASRAdversarialHumanExternalRightsBasis:
    try:
        return ASRAdversarialHumanExternalRightsBasis(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "human external rights basis is invalid"
        ) from exc


def _parse_repository_media_policy(
    value: object,
) -> ASRAdversarialHumanExternalRepositoryMediaPolicy:
    try:
        return (
            ASRAdversarialHumanExternalRepositoryMediaPolicy(
                value
            )
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "human external repository media policy "
            "is invalid"
        ) from exc


def _evidence_boundary(
) -> dict[str, bool]:
    return {
        "development_evidence_only": True,
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


@dataclass(frozen=True, slots=True)
class ASRAdversarialHumanExternalMethodologyBundle:
    """Deterministic human/external methodology artifact."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "human external methodology payload "
                "must be an object"
            )

        _require_sha256(
            name="human external methodology",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_human_external_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "human external methodology SHA-256 "
                "does not match its payload"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialHumanExternalRecordBundle:
    """Deterministic provenance or rights record artifact."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "human external record payload "
                "must be an object"
            )

        _require_sha256(
            name="human external record",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_human_external_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "human external record SHA-256 "
                "does not match its payload"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialHumanExternalProvenanceRecord:
    """Immutable identity commitments for one human speech source."""

    record_id: str
    case_id: str
    source_kind: ASRAdversarialHumanExternalSourceKind
    source_collection_key: str
    source_collection_version: str
    source_item_id: str
    source_audio_sha256: str
    reference_transcript_sha256: str
    source_metadata_sha256: str
    source_locator_sha256: str
    declared_speaker_metadata_sha256: str | None = None
    declared_recording_metadata_sha256: str | None = None

    def __post_init__(
        self,
    ) -> None:
        _require_identifier(
            name="human provenance record id",
            value=self.record_id,
        )
        _require_identifier(
            name="human provenance case id",
            value=self.case_id,
        )

        if not isinstance(
            self.source_kind,
            ASRAdversarialHumanExternalSourceKind,
        ):
            raise HveeContractError(
                "human provenance source kind "
                "must be versioned"
            )

        _require_identifier(
            name="human source collection key",
            value=self.source_collection_key,
        )
        _require_non_empty_text(
            name="human source collection version",
            value=self.source_collection_version,
        )
        _require_non_empty_text(
            name="human source item id",
            value=self.source_item_id,
        )
        _require_sha256(
            name="human source audio",
            value=self.source_audio_sha256,
        )
        _require_sha256(
            name="human reference transcript",
            value=self.reference_transcript_sha256,
        )
        _require_sha256(
            name="human source metadata",
            value=self.source_metadata_sha256,
        )
        _require_sha256(
            name="human source locator",
            value=self.source_locator_sha256,
        )
        _require_optional_sha256(
            name="declared speaker metadata",
            value=self.declared_speaker_metadata_sha256,
        )
        _require_optional_sha256(
            name="declared recording metadata",
            value=self.declared_recording_metadata_sha256,
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialHumanExternalRightsRecord:
    """Non-adjudicating rights evidence for one human speech source."""

    record_id: str
    case_id: str
    source_kind: ASRAdversarialHumanExternalSourceKind
    source_audio_sha256: str
    source_locator_sha256: str
    rights_basis: ASRAdversarialHumanExternalRightsBasis
    rights_evidence_sha256: str
    terms_evidence_sha256: str
    repository_media_policy: (
        ASRAdversarialHumanExternalRepositoryMediaPolicy
    )
    review_status: str
    development_use_only: bool

    def __post_init__(
        self,
    ) -> None:
        _require_identifier(
            name="human rights record id",
            value=self.record_id,
        )
        _require_identifier(
            name="human rights case id",
            value=self.case_id,
        )

        if not isinstance(
            self.source_kind,
            ASRAdversarialHumanExternalSourceKind,
        ):
            raise HveeContractError(
                "human rights source kind "
                "must be versioned"
            )

        _require_sha256(
            name="human rights source audio",
            value=self.source_audio_sha256,
        )
        _require_sha256(
            name="human rights source locator",
            value=self.source_locator_sha256,
        )

        if not isinstance(
            self.rights_basis,
            ASRAdversarialHumanExternalRightsBasis,
        ):
            raise HveeContractError(
                "human rights basis must be versioned"
            )

        expected_basis = {
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
            self.source_kind
        ]

        if self.rights_basis != expected_basis:
            raise HveeContractError(
                "human rights basis does not match "
                "the declared source kind"
            )

        _require_sha256(
            name="human rights evidence",
            value=self.rights_evidence_sha256,
        )
        _require_sha256(
            name="human terms evidence",
            value=self.terms_evidence_sha256,
        )

        if not isinstance(
            self.repository_media_policy,
            ASRAdversarialHumanExternalRepositoryMediaPolicy,
        ):
            raise HveeContractError(
                "human repository media policy "
                "must be versioned"
            )

        if self.review_status != "not_adjudicated":
            raise HveeContractError(
                "human rights review status "
                "must remain not_adjudicated"
            )

        if self.development_use_only is not True:
            raise HveeContractError(
                "human external rights record must "
                "remain development-use-only"
            )


def _methodology_payload(
) -> dict[str, object]:
    return {
        "schema_version": (
            ASR_ADVERSARIAL_HUMAN_EXTERNAL_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_VERSION
            ),
            "type": (
                "source_visible_adversarial_"
                "human_external_methodology"
            ),
        },
        "methodology": {
            "corpus_slice": {
                "corpus_id": (
                    ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID
                ),
                "corpus_version": (
                    ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_VERSION
                ),
            },
            "source_classes": [
                {
                    "source_kind": (
                        ASRAdversarialHumanExternalSourceKind
                        .LICENSED_DATASET
                        .value
                    ),
                    "manifest_provenance_type": (
                        ASRAdversarialCorpusProvenanceType
                        .LICENSED_EXTERNAL
                        .value
                    ),
                    "rights_basis": (
                        ASRAdversarialHumanExternalRightsBasis
                        .DATASET_LICENSE
                        .value
                    ),
                },
                {
                    "source_kind": (
                        ASRAdversarialHumanExternalSourceKind
                        .PURPOSE_RECORDED
                        .value
                    ),
                    "manifest_provenance_type": (
                        ASRAdversarialCorpusProvenanceType
                        .PURPOSE_RECORDED
                        .value
                    ),
                    "rights_basis": (
                        ASRAdversarialHumanExternalRightsBasis
                        .RECORDED_CONSENT
                        .value
                    ),
                },
            ],
            "required_commitments": {
                "source_audio_sha256": True,
                "reference_transcript_sha256": True,
                "source_metadata_sha256": True,
                "source_locator_sha256": True,
                "rights_evidence_sha256": True,
                "terms_evidence_sha256": True,
            },
            "declared_metadata_policy": {
                "speaker_attributes_inferred_from_audio": False,
                "microphone_class_inferred_from_audio": False,
                "source_declared_speaker_metadata_may_be_committed": (
                    True
                ),
                "source_declared_recording_metadata_may_be_committed": (
                    True
                ),
                "raw_declared_metadata_required_in_artifact": False,
            },
            "source_locator_policy": {
                "raw_source_locator_in_artifact": False,
                "locator_commitment_required": True,
            },
            "rights_policy": {
                "review_status": "not_adjudicated",
                "development_use_only": True,
                "legal_validity_verified_by_hetren": False,
                "rights_evidence_must_be_retained_separately": True,
            },
            "repository_media_policies": [
                (
                    ASRAdversarialHumanExternalRepositoryMediaPolicy
                    .NOT_COMMITTED
                    .value
                ),
                (
                    ASRAdversarialHumanExternalRepositoryMediaPolicy
                    .COMMITTED_WITH_SEPARATE_RIGHTS_EVIDENCE
                    .value
                ),
            ],
        },
        "scientific_boundary": {
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
        },
    }


def build_asr_adversarial_human_external_methodology_v1(
) -> ASRAdversarialHumanExternalMethodologyBundle:
    """Build the deterministic I4 human/external methodology."""

    payload = _methodology_payload()

    bundle = ASRAdversarialHumanExternalMethodologyBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_human_external_sha256(
                payload
            )
        ),
    )

    if (
        bundle.sha256
        != ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_SHA256
    ):
        raise HveeContractError(
            "human external methodology v1 identity changed"
        )

    return bundle


def verify_asr_adversarial_human_external_methodology_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> ASRAdversarialHumanExternalMethodologyBundle:
    """Rebuild and verify the exact I4 methodology."""

    _require_sha256(
        name="expected human external methodology",
        value=expected_sha256,
    )

    if (
        expected_sha256
        != ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_SHA256
    ):
        raise HveeContractError(
            "human external methodology identity is unsupported"
        )

    expected = (
        build_asr_adversarial_human_external_methodology_v1()
    )

    if (
        payload != expected.payload
        or expected_sha256 != expected.sha256
    ):
        raise HveeContractError(
            "human external methodology "
            "failed canonical verification"
        )

    return expected


def _record_envelope(
    *,
    key: str,
    record_type: str,
    record: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": (
            ASR_ADVERSARIAL_HUMAN_EXTERNAL_SCHEMA_VERSION
        ),
        "artifact": {
            "key": key,
            "version": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_VERSION
            ),
            "type": record_type,
        },
        "record": record,
        "evidence_boundary": (
            _evidence_boundary()
        ),
    }


def _record_bundle(
    payload: dict[str, object],
) -> ASRAdversarialHumanExternalRecordBundle:
    return ASRAdversarialHumanExternalRecordBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_human_external_sha256(
                payload
            )
        ),
    )


def build_asr_adversarial_human_external_provenance_record_v1(
    record: ASRAdversarialHumanExternalProvenanceRecord,
) -> ASRAdversarialHumanExternalRecordBundle:
    """Build one immutable human-source provenance record."""

    if not isinstance(
        record,
        ASRAdversarialHumanExternalProvenanceRecord,
    ):
        raise HveeContractError(
            "human provenance record type is invalid"
        )

    return _record_bundle(
        _record_envelope(
            key=(
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_PROVENANCE_RECORD_KEY
            ),
            record_type=(
                "source_visible_adversarial_"
                "human_external_provenance_record"
            ),
            record={
                "record_id": record.record_id,
                "case_id": record.case_id,
                "source_kind": (
                    record.source_kind.value
                ),
                "source_collection": {
                    "key": (
                        record.source_collection_key
                    ),
                    "version": (
                        record.source_collection_version
                    ),
                    "item_id": (
                        record.source_item_id
                    ),
                },
                "commitments": {
                    "source_audio_sha256": (
                        record.source_audio_sha256
                    ),
                    "reference_transcript_sha256": (
                        record.reference_transcript_sha256
                    ),
                    "source_metadata_sha256": (
                        record.source_metadata_sha256
                    ),
                    "source_locator_sha256": (
                        record.source_locator_sha256
                    ),
                },
                "declared_metadata_commitments": {
                    "speaker_metadata_sha256": (
                        record.declared_speaker_metadata_sha256
                    ),
                    "recording_metadata_sha256": (
                        record.declared_recording_metadata_sha256
                    ),
                },
            },
        )
    )


def build_asr_adversarial_human_external_rights_record_v1(
    record: ASRAdversarialHumanExternalRightsRecord,
) -> ASRAdversarialHumanExternalRecordBundle:
    """Build one non-adjudicating human-source rights record."""

    if not isinstance(
        record,
        ASRAdversarialHumanExternalRightsRecord,
    ):
        raise HveeContractError(
            "human rights record type is invalid"
        )

    return _record_bundle(
        _record_envelope(
            key=(
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_RIGHTS_RECORD_KEY
            ),
            record_type=(
                "source_visible_adversarial_"
                "human_external_rights_record"
            ),
            record={
                "record_id": record.record_id,
                "case_id": record.case_id,
                "source_kind": (
                    record.source_kind.value
                ),
                "source_binding": {
                    "source_audio_sha256": (
                        record.source_audio_sha256
                    ),
                    "source_locator_sha256": (
                        record.source_locator_sha256
                    ),
                },
                "rights_basis": (
                    record.rights_basis.value
                ),
                "evidence": {
                    "rights_evidence_sha256": (
                        record.rights_evidence_sha256
                    ),
                    "terms_evidence_sha256": (
                        record.terms_evidence_sha256
                    ),
                },
                "repository_media_policy": (
                    record.repository_media_policy.value
                ),
                "review_status": (
                    record.review_status
                ),
                "development_use_only": (
                    record.development_use_only
                ),
            },
        )
    )


def _rebuild_record(
    payload: object,
) -> ASRAdversarialHumanExternalRecordBundle:
    envelope = _require_exact_keys(
        name="human external record envelope",
        value=payload,
        expected={
            "schema_version",
            "artifact",
            "record",
            "evidence_boundary",
        },
    )

    if (
        envelope[
            "schema_version"
        ]
        != ASR_ADVERSARIAL_HUMAN_EXTERNAL_SCHEMA_VERSION
    ):
        raise HveeContractError(
            "human external record schema "
            "version is unsupported"
        )

    if (
        envelope[
            "evidence_boundary"
        ]
        != _evidence_boundary()
    ):
        raise HveeContractError(
            "human external evidence boundary is invalid"
        )

    artifact = _require_exact_keys(
        name="human external record artifact",
        value=envelope[
            "artifact"
        ],
        expected={
            "key",
            "version",
            "type",
        },
    )

    if (
        artifact[
            "version"
        ]
        != ASR_ADVERSARIAL_HUMAN_EXTERNAL_VERSION
    ):
        raise HveeContractError(
            "human external record version "
            "is unsupported"
        )

    key = artifact[
        "key"
    ]

    record = envelope[
        "record"
    ]

    if (
        key
        == ASR_ADVERSARIAL_HUMAN_EXTERNAL_PROVENANCE_RECORD_KEY
    ):
        if (
            artifact[
                "type"
            ]
            != (
                "source_visible_adversarial_"
                "human_external_provenance_record"
            )
        ):
            raise HveeContractError(
                "human provenance artifact type is invalid"
            )

        provenance = _require_exact_keys(
            name="human provenance record",
            value=record,
            expected={
                "record_id",
                "case_id",
                "source_kind",
                "source_collection",
                "commitments",
                "declared_metadata_commitments",
            },
        )

        source_collection = _require_exact_keys(
            name="human source collection",
            value=provenance[
                "source_collection"
            ],
            expected={
                "key",
                "version",
                "item_id",
            },
        )

        commitments = _require_exact_keys(
            name="human provenance commitments",
            value=provenance[
                "commitments"
            ],
            expected={
                "source_audio_sha256",
                "reference_transcript_sha256",
                "source_metadata_sha256",
                "source_locator_sha256",
            },
        )

        declared_metadata = _require_exact_keys(
            name="human declared metadata commitments",
            value=provenance[
                "declared_metadata_commitments"
            ],
            expected={
                "speaker_metadata_sha256",
                "recording_metadata_sha256",
            },
        )

        return (
            build_asr_adversarial_human_external_provenance_record_v1(
                ASRAdversarialHumanExternalProvenanceRecord(
                    record_id=provenance[
                        "record_id"
                    ],
                    case_id=provenance[
                        "case_id"
                    ],
                    source_kind=_parse_source_kind(
                        provenance[
                            "source_kind"
                        ]
                    ),
                    source_collection_key=(
                        source_collection[
                            "key"
                        ]
                    ),
                    source_collection_version=(
                        source_collection[
                            "version"
                        ]
                    ),
                    source_item_id=(
                        source_collection[
                            "item_id"
                        ]
                    ),
                    source_audio_sha256=(
                        commitments[
                            "source_audio_sha256"
                        ]
                    ),
                    reference_transcript_sha256=(
                        commitments[
                            "reference_transcript_sha256"
                        ]
                    ),
                    source_metadata_sha256=(
                        commitments[
                            "source_metadata_sha256"
                        ]
                    ),
                    source_locator_sha256=(
                        commitments[
                            "source_locator_sha256"
                        ]
                    ),
                    declared_speaker_metadata_sha256=(
                        declared_metadata[
                            "speaker_metadata_sha256"
                        ]
                    ),
                    declared_recording_metadata_sha256=(
                        declared_metadata[
                            "recording_metadata_sha256"
                        ]
                    ),
                )
            )
        )

    if (
        key
        == ASR_ADVERSARIAL_HUMAN_EXTERNAL_RIGHTS_RECORD_KEY
    ):
        if (
            artifact[
                "type"
            ]
            != (
                "source_visible_adversarial_"
                "human_external_rights_record"
            )
        ):
            raise HveeContractError(
                "human rights artifact type is invalid"
            )

        rights = _require_exact_keys(
            name="human rights record",
            value=record,
            expected={
                "record_id",
                "case_id",
                "source_kind",
                "source_binding",
                "rights_basis",
                "evidence",
                "repository_media_policy",
                "review_status",
                "development_use_only",
            },
        )

        source_binding = _require_exact_keys(
            name="human rights source binding",
            value=rights[
                "source_binding"
            ],
            expected={
                "source_audio_sha256",
                "source_locator_sha256",
            },
        )

        evidence = _require_exact_keys(
            name="human rights evidence",
            value=rights[
                "evidence"
            ],
            expected={
                "rights_evidence_sha256",
                "terms_evidence_sha256",
            },
        )

        return (
            build_asr_adversarial_human_external_rights_record_v1(
                ASRAdversarialHumanExternalRightsRecord(
                    record_id=rights[
                        "record_id"
                    ],
                    case_id=rights[
                        "case_id"
                    ],
                    source_kind=_parse_source_kind(
                        rights[
                            "source_kind"
                        ]
                    ),
                    source_audio_sha256=(
                        source_binding[
                            "source_audio_sha256"
                        ]
                    ),
                    source_locator_sha256=(
                        source_binding[
                            "source_locator_sha256"
                        ]
                    ),
                    rights_basis=_parse_rights_basis(
                        rights[
                            "rights_basis"
                        ]
                    ),
                    rights_evidence_sha256=(
                        evidence[
                            "rights_evidence_sha256"
                        ]
                    ),
                    terms_evidence_sha256=(
                        evidence[
                            "terms_evidence_sha256"
                        ]
                    ),
                    repository_media_policy=(
                        _parse_repository_media_policy(
                            rights[
                                "repository_media_policy"
                            ]
                        )
                    ),
                    review_status=rights[
                        "review_status"
                    ],
                    development_use_only=rights[
                        "development_use_only"
                    ],
                )
            )
        )

    raise HveeContractError(
        "human external record artifact key "
        "is unsupported"
    )


def verify_asr_adversarial_human_external_record_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> ASRAdversarialHumanExternalRecordBundle:
    """Verify exact canonical reconstruction of one I4 record."""

    _require_sha256(
        name="expected human external record",
        value=expected_sha256,
    )

    rebuilt = _rebuild_record(
        payload
    )

    if (
        rebuilt.payload != payload
        or rebuilt.sha256
        != expected_sha256
    ):
        raise HveeContractError(
            "human external record "
            "failed canonical verification"
        )

    return rebuilt


def verify_asr_adversarial_human_external_record_pair_v1(
    *,
    provenance: ASRAdversarialHumanExternalRecordBundle,
    rights: ASRAdversarialHumanExternalRecordBundle,
) -> tuple[
    ASRAdversarialHumanExternalRecordBundle,
    ASRAdversarialHumanExternalRecordBundle,
]:
    """Verify provenance and rights bind the same exact human source."""

    if not isinstance(
        provenance,
        ASRAdversarialHumanExternalRecordBundle,
    ):
        raise HveeContractError(
            "human provenance bundle is invalid"
        )

    if not isinstance(
        rights,
        ASRAdversarialHumanExternalRecordBundle,
    ):
        raise HveeContractError(
            "human rights bundle is invalid"
        )

    verified_provenance = (
        verify_asr_adversarial_human_external_record_v1(
            payload=provenance.payload,
            expected_sha256=provenance.sha256,
        )
    )

    verified_rights = (
        verify_asr_adversarial_human_external_record_v1(
            payload=rights.payload,
            expected_sha256=rights.sha256,
        )
    )

    if (
        verified_provenance.payload[
            "artifact"
        ][
            "key"
        ]
        != ASR_ADVERSARIAL_HUMAN_EXTERNAL_PROVENANCE_RECORD_KEY
    ):
        raise HveeContractError(
            "human provenance bundle has wrong artifact type"
        )

    if (
        verified_rights.payload[
            "artifact"
        ][
            "key"
        ]
        != ASR_ADVERSARIAL_HUMAN_EXTERNAL_RIGHTS_RECORD_KEY
    ):
        raise HveeContractError(
            "human rights bundle has wrong artifact type"
        )

    provenance_record = (
        verified_provenance.payload[
            "record"
        ]
    )
    rights_record = (
        verified_rights.payload[
            "record"
        ]
    )

    provenance_commitments = (
        provenance_record[
            "commitments"
        ]
    )
    rights_binding = (
        rights_record[
            "source_binding"
        ]
    )

    if (
        provenance_record[
            "case_id"
        ]
        != rights_record[
            "case_id"
        ]
        or provenance_record[
            "source_kind"
        ]
        != rights_record[
            "source_kind"
        ]
        or provenance_commitments[
            "source_audio_sha256"
        ]
        != rights_binding[
            "source_audio_sha256"
        ]
        or provenance_commitments[
            "source_locator_sha256"
        ]
        != rights_binding[
            "source_locator_sha256"
        ]
    ):
        raise HveeContractError(
            "human provenance and rights records "
            "do not bind the same source"
        )

    return (
        verified_provenance,
        verified_rights,
    )


__all__ = [
    "ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID",
    "ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_VERSION",
    "ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_KEY",
    "ASR_ADVERSARIAL_HUMAN_EXTERNAL_METHODOLOGY_SHA256",
    "ASR_ADVERSARIAL_HUMAN_EXTERNAL_PROVENANCE_RECORD_KEY",
    "ASR_ADVERSARIAL_HUMAN_EXTERNAL_RIGHTS_RECORD_KEY",
    "ASR_ADVERSARIAL_HUMAN_EXTERNAL_SCHEMA_VERSION",
    "ASR_ADVERSARIAL_HUMAN_EXTERNAL_VERSION",
    "ASRAdversarialHumanExternalMethodologyBundle",
    "ASRAdversarialHumanExternalProvenanceRecord",
    "ASRAdversarialHumanExternalRecordBundle",
    "ASRAdversarialHumanExternalRepositoryMediaPolicy",
    "ASRAdversarialHumanExternalRightsBasis",
    "ASRAdversarialHumanExternalRightsRecord",
    "ASRAdversarialHumanExternalSourceKind",
    "build_asr_adversarial_human_external_methodology_v1",
    "build_asr_adversarial_human_external_provenance_record_v1",
    "build_asr_adversarial_human_external_rights_record_v1",
    "calculate_asr_adversarial_human_external_sha256",
    "verify_asr_adversarial_human_external_methodology_v1",
    "verify_asr_adversarial_human_external_record_pair_v1",
    "verify_asr_adversarial_human_external_record_v1",
]
