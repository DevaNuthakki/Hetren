"""Deterministic matched-control projection for verified VOiCES media.

This application-layer bridge consumes the fail-closed materialization result
for Hetren's controlled VOiCES slice and projects the exact babble/no-distractor
capture pairs selected by the source-visible I4e-A evidence contract.

The projection deliberately stops before constructing ASR adversarial cases.
The controlled evidence binds source-declared transcript commitments, but raw
reference transcripts are not exposed by the trusted materialization result.
An ASRAdversarialCase requires the raw reference transcript, so treating this
projection as execution-ready would exceed the established evidence boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from app.adversarial_asr_human_external_voices_materialization_service import (
    ASRAdversarialVOiCESMaterializedEvidence,
    ASRAdversarialVOiCESMaterializedMedia,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ANGLE_DEGREES,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_IDS,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ROOMS,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256,
    build_asr_adversarial_voices_babble_matched_control_v1,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
)


class ASRAdversarialVOiCESMatchedControlProjectionError(
    ValueError,
):
    """Raised when verified media cannot form the frozen matched design."""


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
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise ASRAdversarialVOiCESMatchedControlProjectionError(
            f"{name} must be a lowercase SHA-256."
        )

    return value


def _canonical_json_bytes(
    value: object,
) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            allow_nan=False,
        ).encode(
            "utf-8"
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ASRAdversarialVOiCESMatchedControlProjectionError(
            "VOiCES matched-control projection must be deterministic JSON."
        ) from error


@dataclass(
    frozen=True,
    slots=True,
    order=True,
)
class ASRAdversarialVOiCESMatchedControlPairKey:
    """Condition identity shared by one babble/control capture pair."""

    source_key: tuple[int, int, int]
    room: str
    microphone_id: int
    angle_degrees: int

    def __post_init__(
        self,
    ) -> None:
        if (
            not isinstance(
                self.source_key,
                tuple,
            )
            or len(self.source_key) != 3
            or any(
                isinstance(
                    value,
                    bool,
                )
                or not isinstance(
                    value,
                    int,
                )
                or value <= 0
                for value in self.source_key
            )
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control source key is invalid."
            )

        if self.source_key not in (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control source is outside the frozen selection."
            )

        if self.room not in (
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ROOMS
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control room is outside the frozen design."
            )

        if self.microphone_id not in (
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_IDS
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control microphone is outside the frozen design."
            )

        if (
            isinstance(
                self.angle_degrees,
                bool,
            )
            or self.angle_degrees
            != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ANGLE_DEGREES
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control angle is outside the frozen design."
            )


_MATCHED_MEDIA_FIELDS = (
    "codec_name",
    "sample_rate_hz",
    "channel_count",
    "bits_per_sample",
    "sample_width_bytes",
    "sample_count",
    "duration_seconds",
)


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialVOiCESMatchedControlPair:
    """One verified physical-acoustic babble/no-distractor capture pair."""

    key: ASRAdversarialVOiCESMatchedControlPairKey
    interference: ASRAdversarialVOiCESMaterializedMedia
    control: ASRAdversarialVOiCESMaterializedMedia

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.key,
            ASRAdversarialVOiCESMatchedControlPairKey,
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control pair key is invalid."
            )

        for name, media, distractor in (
            (
                "interference",
                self.interference,
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE,
            ),
            (
                "control",
                self.control,
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL,
            ),
        ):
            if not isinstance(
                media,
                ASRAdversarialVOiCESMaterializedMedia,
            ):
                raise ASRAdversarialVOiCESMatchedControlProjectionError(
                    f"VOiCES matched-control {name} media is invalid."
                )

            if media.kind != "capture":
                raise ASRAdversarialVOiCESMatchedControlProjectionError(
                    f"VOiCES matched-control {name} must be capture media."
                )

            try:
                condition = media.require_capture_condition()
            except ValueError as error:
                raise ASRAdversarialVOiCESMatchedControlProjectionError(
                    f"VOiCES matched-control {name} condition is unavailable."
                ) from error

            if (
                media.source_key != self.key.source_key
                or condition.room != self.key.room
                or condition.microphone_id
                != self.key.microphone_id
                or condition.angle_degrees
                != self.key.angle_degrees
                or condition.distractor != distractor
            ):
                raise ASRAdversarialVOiCESMatchedControlProjectionError(
                    f"VOiCES matched-control {name} condition changed."
                )

        if (
            self.interference.relative_path
            == self.control.relative_path
            or self.interference.sha256
            == self.control.sha256
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control pair requires distinct media."
            )

        for field_name in _MATCHED_MEDIA_FIELDS:
            if getattr(
                self.interference,
                field_name,
            ) != getattr(
                self.control,
                field_name,
            ):
                raise ASRAdversarialVOiCESMatchedControlProjectionError(
                    "VOiCES matched-control media format, sample count, "
                    f"or duration changed: {field_name}."
                )


def _pair_payload(
    pair: ASRAdversarialVOiCESMatchedControlPair,
) -> dict[str, object]:
    return {
        "key": {
            "source_key": list(
                pair.key.source_key
            ),
            "room": pair.key.room,
            "microphone_id": (
                pair.key.microphone_id
            ),
            "angle_degrees": (
                pair.key.angle_degrees
            ),
        },
        "interference": {
            "distractor": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE
            ),
            "relative_path": (
                pair.interference.relative_path
            ),
            "sha256": pair.interference.sha256,
            "bytes": (
                pair.interference.byte_length
            ),
        },
        "control": {
            "distractor": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL
            ),
            "relative_path": (
                pair.control.relative_path
            ),
            "sha256": pair.control.sha256,
            "bytes": pair.control.byte_length,
        },
        "matched_media": {
            field_name: getattr(
                pair.control,
                field_name,
            )
            for field_name in _MATCHED_MEDIA_FIELDS
        },
    }


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialVOiCESMatchedControlProjectionBundle:
    """Deterministic non-executing bridge over verified matched captures."""

    controlled_contract_sha256: str
    matched_control_contract_sha256: str
    identity_chain_sha256: str
    selection_sha256: str
    materialization_manifest_sha256: str
    media_report_sha256: str
    observation_sha256: str
    rights_manifest_sha256: str
    pairs: tuple[
        ASRAdversarialVOiCESMatchedControlPair,
        ...,
    ]

    development_evidence_only: bool = True
    reference_transcripts_projected: bool = False
    adversarial_suite_built: bool = False
    asr_execution_verified: bool = False
    qualification_threshold_applied: bool = False
    production_qualified: bool = False
    release_enforcement_eligible: bool = False
    official_release_verdict_modified: bool = False

    def __post_init__(
        self,
    ) -> None:
        for name, value in (
            (
                "controlled VOiCES contract",
                self.controlled_contract_sha256,
            ),
            (
                "VOiCES matched-control contract",
                self.matched_control_contract_sha256,
            ),
            (
                "VOiCES identity chain",
                self.identity_chain_sha256,
            ),
            (
                "VOiCES selection",
                self.selection_sha256,
            ),
            (
                "VOiCES materialization manifest",
                self.materialization_manifest_sha256,
            ),
            (
                "VOiCES media report",
                self.media_report_sha256,
            ),
            (
                "VOiCES media observation",
                self.observation_sha256,
            ),
            (
                "VOiCES rights manifest",
                self.rights_manifest_sha256,
            ),
        ):
            _require_sha256(
                name=name,
                value=value,
            )

        if (
            self.controlled_contract_sha256
            != ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
            or self.matched_control_contract_sha256
            != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control upstream identity changed."
            )

        if (
            not isinstance(
                self.pairs,
                tuple,
            )
            or len(
                self.pairs
            )
            != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
            or any(
                not isinstance(
                    pair,
                    ASRAdversarialVOiCESMatchedControlPair,
                )
                for pair in self.pairs
            )
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control projection population changed."
            )

        pair_keys = tuple(
            pair.key
            for pair in self.pairs
        )

        if (
            pair_keys
            != tuple(
                sorted(
                    pair_keys
                )
            )
            or len(
                pair_keys
            )
            != len(
                set(
                    pair_keys
                )
            )
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control pairs must be uniquely ordered."
            )

        media_sha256s = tuple(
            sha256
            for pair in self.pairs
            for sha256 in (
                pair.interference.sha256,
                pair.control.sha256,
            )
        )

        if (
            len(
                media_sha256s
            )
            != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT
            or len(
                media_sha256s
            )
            != len(
                set(
                    media_sha256s
                )
            )
        ):
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control audio identities changed."
            )

        authority = {
            "development_evidence_only": (
                self.development_evidence_only
            ),
            "reference_transcripts_projected": (
                self.reference_transcripts_projected
            ),
            "adversarial_suite_built": (
                self.adversarial_suite_built
            ),
            "asr_execution_verified": (
                self.asr_execution_verified
            ),
            "qualification_threshold_applied": (
                self.qualification_threshold_applied
            ),
            "production_qualified": (
                self.production_qualified
            ),
            "release_enforcement_eligible": (
                self.release_enforcement_eligible
            ),
            "official_release_verdict_modified": (
                self.official_release_verdict_modified
            ),
        }

        if authority[
            "development_evidence_only"
        ] is not True:
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control projection must remain "
                "development-evidence-only."
            )

        for field_name in (
            "reference_transcripts_projected",
            "adversarial_suite_built",
            "asr_execution_verified",
            "qualification_threshold_applied",
            "production_qualified",
            "release_enforcement_eligible",
            "official_release_verdict_modified",
        ):
            if authority[
                field_name
            ] is not False:
                raise ASRAdversarialVOiCESMatchedControlProjectionError(
                    "VOiCES matched-control projection cannot "
                    f"escalate {field_name}."
                )

    @property
    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "artifact": {
                "key": (
                    "hetren.asr.adversarial-human-external-"
                    "voices-babble-matched-control-projection"
                ),
                "version": "1.0.0",
                "type": (
                    "verified_matched_control_media_projection"
                ),
            },
            "upstream": {
                "controlled_contract_sha256": (
                    self.controlled_contract_sha256
                ),
                "matched_control_contract_sha256": (
                    self.matched_control_contract_sha256
                ),
                "identity_chain_sha256": (
                    self.identity_chain_sha256
                ),
                "selection_sha256": (
                    self.selection_sha256
                ),
                "materialization_manifest_sha256": (
                    self.materialization_manifest_sha256
                ),
                "media_report_sha256": (
                    self.media_report_sha256
                ),
                "observation_sha256": (
                    self.observation_sha256
                ),
                "rights_manifest_sha256": (
                    self.rights_manifest_sha256
                ),
            },
            "matched_control": {
                "pair_count": len(
                    self.pairs
                ),
                "audio_file_count": sum(
                    2
                    for _pair in self.pairs
                ),
                "pairs": [
                    _pair_payload(
                        pair
                    )
                    for pair in self.pairs
                ],
            },
            "evidence_boundary": {
                "development_evidence_only": True,
                "verified_materialized_media_consumed": True,
                "matched_babble_control_pairs_projected": True,
                "raw_audio_embedded": False,
                "reference_transcripts_projected": False,
                "adversarial_suite_built": False,
                "asr_execution_verified": False,
                "qualification_threshold_applied": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
            },
        }

    @property
    def sha256(
        self,
    ) -> str:
        return hashlib.sha256(
            _canonical_json_bytes(
                self.payload
            )
        ).hexdigest()

    def require_adversarial_suite_ready(
        self,
    ) -> None:
        raise ASRAdversarialVOiCESMatchedControlProjectionError(
            "VOiCES matched-control projection requires trusted raw "
            "reference transcripts before an adversarial suite can be built."
        )


def _expected_pair_keys(
) -> tuple[
    ASRAdversarialVOiCESMatchedControlPairKey,
    ...,
]:
    return tuple(
        sorted(
            ASRAdversarialVOiCESMatchedControlPairKey(
                source_key=source_key,
                room=room,
                microphone_id=microphone_id,
                angle_degrees=(
                    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ANGLE_DEGREES
                ),
            )
            for source_key in (
                ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
            )
            for room in (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ROOMS
            )
            for microphone_id in (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_IDS
            )
        )
    )


def project_asr_adversarial_voices_babble_matched_control_v1(
    materialized: ASRAdversarialVOiCESMaterializedEvidence,
) -> ASRAdversarialVOiCESMatchedControlProjectionBundle:
    """Project exact verified babble/control pairs without ASR authority."""

    if not isinstance(
        materialized,
        ASRAdversarialVOiCESMaterializedEvidence,
    ):
        raise ASRAdversarialVOiCESMatchedControlProjectionError(
            "VOiCES matched-control projection requires verified "
            "materialized evidence."
        )

    matched_control = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    if (
        materialized.controlled_contract_sha256
        != ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
        or matched_control.sha256
        != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
    ):
        raise ASRAdversarialVOiCESMatchedControlProjectionError(
            "VOiCES matched-control projection upstream identity changed."
        )

    if (
        materialized.development_evidence_only
        is not True
        or materialized.asr_execution_verified
        is not False
        or materialized.production_qualified
        is not False
        or materialized.release_enforcement_eligible
        is not False
        or materialized.official_release_verdict_modified
        is not False
    ):
        raise ASRAdversarialVOiCESMatchedControlProjectionError(
            "VOiCES materialized evidence authority boundary changed."
        )

    source_keys = tuple(
        sorted(
            media.source_key
            for media in materialized.media
            if media.kind == "source"
        )
    )

    if source_keys != tuple(
        sorted(
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
        )
    ):
        raise ASRAdversarialVOiCESMatchedControlProjectionError(
            "VOiCES matched-control source population changed."
        )

    selected: dict[
        ASRAdversarialVOiCESMatchedControlPairKey,
        dict[str, ASRAdversarialVOiCESMaterializedMedia],
    ] = {}

    for media in materialized.media:
        if media.kind != "capture":
            continue

        try:
            condition = media.require_capture_condition()
        except ValueError as error:
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES capture condition is unavailable during projection."
            ) from error

        if condition.distractor not in {
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE,
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL,
        }:
            continue

        key = ASRAdversarialVOiCESMatchedControlPairKey(
            source_key=media.source_key,
            room=condition.room,
            microphone_id=(
                condition.microphone_id
            ),
            angle_degrees=(
                condition.angle_degrees
            ),
        )

        by_distractor = selected.setdefault(
            key,
            {},
        )

        if condition.distractor in by_distractor:
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control projection contains a duplicate "
                "capture condition."
            )

        by_distractor[
            condition.distractor
        ] = media

    expected_keys = _expected_pair_keys()

    if set(
        selected
    ) != set(
        expected_keys
    ):
        raise ASRAdversarialVOiCESMatchedControlProjectionError(
            "VOiCES matched-control projection lattice changed."
        )

    pairs = []

    for key in expected_keys:
        captures = selected[
            key
        ]

        if set(
            captures
        ) != {
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE,
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL,
        }:
            raise ASRAdversarialVOiCESMatchedControlProjectionError(
                "VOiCES matched-control pair is incomplete."
            )

        pairs.append(
            ASRAdversarialVOiCESMatchedControlPair(
                key=key,
                interference=captures[
                    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE
                ],
                control=captures[
                    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL
                ],
            )
        )

    return ASRAdversarialVOiCESMatchedControlProjectionBundle(
        controlled_contract_sha256=(
            materialized.controlled_contract_sha256
        ),
        matched_control_contract_sha256=(
            matched_control.sha256
        ),
        identity_chain_sha256=(
            materialized.identity_chain_sha256
        ),
        selection_sha256=(
            materialized.selection_sha256
        ),
        materialization_manifest_sha256=(
            materialized.materialization_manifest_sha256
        ),
        media_report_sha256=(
            materialized.media_report_sha256
        ),
        observation_sha256=(
            materialized.observation_sha256
        ),
        rights_manifest_sha256=(
            materialized.rights_manifest_sha256
        ),
        pairs=tuple(
            pairs
        ),
    )


__all__ = [
    "ASRAdversarialVOiCESMatchedControlPair",
    "ASRAdversarialVOiCESMatchedControlPairKey",
    "ASRAdversarialVOiCESMatchedControlProjectionBundle",
    "ASRAdversarialVOiCESMatchedControlProjectionError",
    "project_asr_adversarial_voices_babble_matched_control_v1",
]
