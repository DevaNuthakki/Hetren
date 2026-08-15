"""Deterministic human/external ASR source portfolio evidence.

This artifact summarizes what Hetren can truthfully establish about the
currently bound human/external source population.

The portfolio distinguishes:

- source-defined identifiers,
- cryptographically bound source records,
- verified technical media facts,
- optional source-declared metadata,
- scientific claims that remain explicitly unestablished.

Source speaker IDs and chapter IDs are identifiers supplied by the source
dataset. They are not interpreted as demographic, accent, microphone,
recording-session, room, or recording-environment labels.

Technical variation is reported as measured fact only. It does not establish
human acoustic diversity, production qualification, certification, or release
authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_evidence import (
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID,
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_VERSION,
    calculate_asr_adversarial_human_external_sha256,
)
from hvee.packs.asr.adversarial_human_external_minilibrispeech_v1 import (
    ASR_ADVERSARIAL_MINILIBRISPEECH_CASES,
    ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_KEY,
    ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_VERSION,
    ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_KEY,
    ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256,
    ASR_ADVERSARIAL_MINILIBRISPEECH_VERSION,
    build_asr_adversarial_minilibrispeech_record_pairs_v1,
    build_asr_adversarial_minilibrispeech_selection_v1,
)


ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SCHEMA_VERSION = 1

ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_KEY = (
    "hetren.asr.adversarial-human-external-source-portfolio"
)

ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_VERSION = "1.0.0"

# Frozen after the deterministic payload below is independently calculated.
ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SHA256 = (
    "1b6a2bf814ce1eed43b522452610ddee57a183a08d5d86092fae64f0822366b5"
)


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
        or len(value) != 64
        or any(
            character
            not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256"
        )

    return value


def _require_dict(
    *,
    name: str,
    value: object,
) -> dict[str, object]:
    if not isinstance(
        value,
        dict,
    ):
        raise HveeContractError(
            f"{name} must be an object"
        )

    return value


def calculate_asr_adversarial_human_external_portfolio_sha256(
    payload: object,
) -> str:
    """Calculate the canonical portfolio evidence digest."""

    return (
        calculate_asr_adversarial_human_external_sha256(
            payload
        )
    )


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialHumanExternalPortfolioBundle:
    """Immutable identity wrapper for one source portfolio artifact."""

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
                "human external portfolio payload "
                "must be an object"
            )

        _require_sha256(
            name="human external portfolio",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_human_external_portfolio_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "human external portfolio SHA-256 "
                "does not match its payload"
            )


def _record_pairs_by_source_item(
):
    pairs = (
        build_asr_adversarial_minilibrispeech_record_pairs_v1()
    )

    if len(pairs) != len(
        ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
    ):
        raise HveeContractError(
            "human external portfolio record-pair "
            "population is incomplete"
        )

    indexed = {}

    for provenance, rights in pairs:
        provenance_record = _require_dict(
            name="human portfolio provenance record",
            value=provenance.payload.get(
                "record"
            ),
        )

        source_collection = _require_dict(
            name="human portfolio source collection",
            value=provenance_record.get(
                "source_collection"
            ),
        )

        source_item_id = source_collection.get(
            "item_id"
        )

        if (
            not isinstance(
                source_item_id,
                str,
            )
            or not source_item_id
        ):
            raise HveeContractError(
                "human portfolio source item id "
                "is invalid"
            )

        if source_item_id in indexed:
            raise HveeContractError(
                "human portfolio source item ids "
                "must be unique"
            )

        indexed[source_item_id] = (
            provenance,
            rights,
        )

    expected_source_items = {
        case.utterance_id
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    }

    if set(indexed) != expected_source_items:
        raise HveeContractError(
            "human external portfolio record pairs "
            "do not match the selected population"
        )

    return indexed


def _case_snapshot(
    *,
    case,
    provenance,
    rights,
) -> dict[str, object]:
    provenance_record = _require_dict(
        name="human portfolio provenance record",
        value=provenance.payload.get(
            "record"
        ),
    )

    rights_record = _require_dict(
        name="human portfolio rights record",
        value=rights.payload.get(
            "record"
        ),
    )

    source_collection = _require_dict(
        name="human portfolio source collection",
        value=provenance_record.get(
            "source_collection"
        ),
    )

    commitments = _require_dict(
        name="human portfolio commitments",
        value=provenance_record.get(
            "commitments"
        ),
    )

    declared_metadata = _require_dict(
        name="human portfolio declared metadata",
        value=provenance_record.get(
            "declared_metadata_commitments"
        ),
    )

    rights_binding = _require_dict(
        name="human portfolio rights binding",
        value=rights_record.get(
            "source_binding"
        ),
    )

    if (
        provenance_record.get(
            "case_id"
        )
        != case.case_id
        or rights_record.get(
            "case_id"
        )
        != case.case_id
        or source_collection.get(
            "item_id"
        )
        != case.utterance_id
    ):
        raise HveeContractError(
            "human portfolio source identity "
            "does not match the selected case"
        )

    expected_commitments = {
        "source_audio_sha256": (
            case.source_audio_sha256
        ),
        "reference_transcript_sha256": (
            case.reference_transcript_sha256
        ),
        "source_metadata_sha256": (
            case.source_metadata_sha256
        ),
        "source_locator_sha256": (
            case.source_locator_sha256
        ),
    }

    if commitments != expected_commitments:
        raise HveeContractError(
            "human portfolio provenance commitments "
            "do not match the selected case"
        )

    if rights_binding != {
        "source_audio_sha256": (
            case.source_audio_sha256
        ),
        "source_locator_sha256": (
            case.source_locator_sha256
        ),
    }:
        raise HveeContractError(
            "human portfolio rights binding "
            "does not match the selected case"
        )

    expected_declared_metadata = {
        "speaker_metadata_sha256": None,
        "recording_metadata_sha256": None,
    }

    if declared_metadata != expected_declared_metadata:
        raise HveeContractError(
            "Mini LibriSpeech portfolio unexpectedly "
            "contains declared speaker or recording metadata"
        )

    if (
        rights_record.get(
            "review_status"
        )
        != "not_adjudicated"
        or rights_record.get(
            "development_use_only"
        )
        is not True
        or rights_record.get(
            "repository_media_policy"
        )
        != "not_committed"
    ):
        raise HveeContractError(
            "human portfolio rights boundary changed"
        )

    return {
        "case_id": case.case_id,
        "source_item_id": (
            case.utterance_id
        ),
        "source_defined_speaker_id": (
            case.speaker_id
        ),
        "source_defined_chapter_id": (
            case.chapter_id
        ),
        "selection_reason": (
            case.selection_reason
        ),
        "commitments": {
            "source_audio_sha256": (
                case.source_audio_sha256
            ),
            "audio_bytes": (
                case.audio_bytes
            ),
            "reference_transcript_sha256": (
                case.reference_transcript_sha256
            ),
            "source_metadata_sha256": (
                case.source_metadata_sha256
            ),
            "source_locator_sha256": (
                case.source_locator_sha256
            ),
            "provenance_record_sha256": (
                provenance.sha256
            ),
            "rights_record_sha256": (
                rights.sha256
            ),
        },
        "verified_media": {
            "codec_name": (
                case.codec_name
            ),
            "format_name": (
                case.format_name
            ),
            "sample_rate_hz": (
                case.sample_rate_hz
            ),
            "channel_count": (
                case.channel_count
            ),
            "duration_ms": (
                case.duration_ms
            ),
        },
        "declared_metadata_commitments": {
            "speaker_metadata_sha256": None,
            "recording_metadata_sha256": None,
        },
        "rights_boundary": {
            "rights_basis": (
                rights_record[
                    "rights_basis"
                ]
            ),
            "repository_media_policy": (
                rights_record[
                    "repository_media_policy"
                ]
            ),
            "review_status": (
                rights_record[
                    "review_status"
                ]
            ),
            "development_use_only": (
                rights_record[
                    "development_use_only"
                ]
            ),
        },
    }


def _portfolio_payload(
) -> dict[str, object]:
    selection = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    if (
        selection.sha256
        != ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256
    ):
        raise HveeContractError(
            "human portfolio requires the frozen "
            "Mini LibriSpeech selection"
        )

    pairs_by_source_item = (
        _record_pairs_by_source_item()
    )

    case_snapshots = []

    for case in (
        ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
    ):
        provenance, rights = (
            pairs_by_source_item[
                case.utterance_id
            ]
        )

        case_snapshots.append(
            _case_snapshot(
                case=case,
                provenance=provenance,
                rights=rights,
            )
        )

    selected_asset_count = len(
        ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
    )

    speaker_ids = {
        case.speaker_id
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    }

    chapter_ids = {
        case.chapter_id
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    }

    audio_sha256_values = {
        case.source_audio_sha256
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    }

    transcript_sha256_values = {
        case.reference_transcript_sha256
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    }

    codec_names = sorted({
        case.codec_name
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    })

    format_names = sorted({
        case.format_name
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    })

    sample_rates_hz = sorted({
        case.sample_rate_hz
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    })

    channel_counts = sorted({
        case.channel_count
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    })

    durations_ms = tuple(
        case.duration_ms
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    )

    total_audio_bytes = sum(
        case.audio_bytes
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    )

    speaker_metadata_count = sum(
        snapshot[
            "declared_metadata_commitments"
        ][
            "speaker_metadata_sha256"
        ]
        is not None
        for snapshot in case_snapshots
    )

    recording_metadata_count = sum(
        snapshot[
            "declared_metadata_commitments"
        ][
            "recording_metadata_sha256"
        ]
        is not None
        for snapshot in case_snapshots
    )

    rights_policies = sorted({
        snapshot[
            "rights_boundary"
        ][
            "repository_media_policy"
        ]
        for snapshot in case_snapshots
    })

    rights_bases = sorted({
        snapshot[
            "rights_boundary"
        ][
            "rights_basis"
        ]
        for snapshot in case_snapshots
    })

    not_adjudicated_count = sum(
        snapshot[
            "rights_boundary"
        ][
            "review_status"
        ]
        == "not_adjudicated"
        for snapshot in case_snapshots
    )

    development_use_only_count = sum(
        snapshot[
            "rights_boundary"
        ][
            "development_use_only"
        ]
        is True
        for snapshot in case_snapshots
    )

    return {
        "schema_version": (
            ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_VERSION
            ),
            "type": (
                "source_visible_adversarial_"
                "human_external_source_portfolio"
            ),
        },
        "human_external_corpus": {
            "corpus_id": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID
            ),
            "corpus_version": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_VERSION
            ),
        },
        "source_slices": [
            {
                "slice_key": (
                    "minilibrispeech-slr31-dev-clean-2"
                ),
                "collection_key": (
                    ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_KEY
                ),
                "collection_version": (
                    ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_VERSION
                ),
                "selection_key": (
                    ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_KEY
                ),
                "selection_version": (
                    ASR_ADVERSARIAL_MINILIBRISPEECH_VERSION
                ),
                "selection_sha256": (
                    selection.sha256
                ),
                "selected_asset_count": (
                    selected_asset_count
                ),
            }
        ],
        "population": {
            "selected_asset_count": (
                selected_asset_count
            ),
            "distinct_source_defined_speaker_id_count": (
                len(
                    speaker_ids
                )
            ),
            "distinct_source_defined_chapter_id_count": (
                len(
                    chapter_ids
                )
            ),
            "distinct_source_audio_sha256_count": (
                len(
                    audio_sha256_values
                )
            ),
            "distinct_reference_transcript_sha256_count": (
                len(
                    transcript_sha256_values
                )
            ),
        },
        "technical_portfolio": {
            "codec_names": (
                codec_names
            ),
            "format_names": (
                format_names
            ),
            "sample_rates_hz": (
                sample_rates_hz
            ),
            "channel_counts": (
                channel_counts
            ),
            "duration_ms": {
                "minimum": min(
                    durations_ms
                ),
                "maximum": max(
                    durations_ms
                ),
                "total": sum(
                    durations_ms
                ),
                "distinct_value_count": len(
                    set(
                        durations_ms
                    )
                ),
            },
            "audio_bytes": {
                "total": (
                    total_audio_bytes
                ),
            },
        },
        "declared_metadata_coverage": {
            "selected_asset_count": (
                selected_asset_count
            ),
            "speaker_metadata_commitment_count": (
                speaker_metadata_count
            ),
            "recording_metadata_commitment_count": (
                recording_metadata_count
            ),
            "speaker_metadata_complete": (
                speaker_metadata_count
                == selected_asset_count
            ),
            "recording_metadata_complete": (
                recording_metadata_count
                == selected_asset_count
            ),
        },
        "rights_portfolio": {
            "record_count": (
                selected_asset_count
            ),
            "not_adjudicated_record_count": (
                not_adjudicated_count
            ),
            "development_use_only_record_count": (
                development_use_only_count
            ),
            "rights_bases": (
                rights_bases
            ),
            "repository_media_policies": (
                rights_policies
            ),
        },
        "cases": (
            case_snapshots
        ),
        "evidence_boundary": {
            "source_speaker_ids_are_source_defined": True,
            "source_chapter_ids_are_source_defined": True,
            "source_chapter_ids_treated_as_recording_sessions": False,
            "source_chapter_ids_treated_as_recording_environments": False,
            "speaker_attributes_inferred": False,
            "accent_inferred": False,
            "microphone_class_inferred": False,
            "recording_environment_inferred": False,
            "technical_variation_establishes_acoustic_diversity": False,
            "human_acoustic_diversity_established": False,
            "rights_adjudicated": False,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }


def build_asr_adversarial_human_external_portfolio_v1(
) -> ASRAdversarialHumanExternalPortfolioBundle:
    """Build the exact deterministic I4d human-source portfolio."""

    payload = _portfolio_payload()

    bundle = (
        ASRAdversarialHumanExternalPortfolioBundle(
            payload=payload,
            sha256=(
                calculate_asr_adversarial_human_external_portfolio_sha256(
                    payload
                )
            ),
        )
    )

    if (
        bundle.sha256
        != ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SHA256
    ):
        raise HveeContractError(
            "human external portfolio v1 identity changed"
        )

    return bundle


def verify_asr_adversarial_human_external_portfolio_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> ASRAdversarialHumanExternalPortfolioBundle:
    """Rebuild and verify the exact frozen I4d portfolio."""

    _require_sha256(
        name="expected human external portfolio",
        value=expected_sha256,
    )

    if (
        expected_sha256
        != ASR_ADVERSARIAL_HUMAN_EXTERNAL_PORTFOLIO_SHA256
    ):
        raise HveeContractError(
            "human external portfolio identity "
            "is unsupported"
        )

    expected = (
        build_asr_adversarial_human_external_portfolio_v1()
    )

    if (
        payload != expected.payload
        or expected_sha256
        != expected.sha256
    ):
        raise HveeContractError(
            "human external portfolio failed "
            "canonical verification"
        )

    return expected
