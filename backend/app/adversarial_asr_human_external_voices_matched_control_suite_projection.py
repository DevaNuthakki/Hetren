"""Project verified VOiCES matched-control media into executable ASR cases.

This I4e-B5 bridge combines:

- the verified 16-pair VOiCES babble/no-distractor media projection, and
- the frozen source-declared reference transcripts for both foreground files.

It produces 32 source-visible ASR case definitions while preserving the
absolute verified media objects needed by a later execution adapter.  Babble
is represented as physical-acoustic background-noise stress.  It is not
represented as verified conversational speaker overlap because secondary
speaker identities, words, and timing are not established by this evidence.

The resulting suite is execution-ready development evidence.  This module
does not execute an ASR model, apply qualification thresholds, certify a
system, or modify release authority.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json

from app.adversarial_asr_human_external_voices_matched_control_projection import (
    ASRAdversarialVOiCESMatchedControlPair,
    ASRAdversarialVOiCESMatchedControlPairKey,
    ASRAdversarialVOiCESMatchedControlProjectionBundle,
)
from app.adversarial_asr_human_external_voices_materialization_service import (
    ASRAdversarialVOiCESMaterializedMedia,
)
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_evidence import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCase,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialCondition,
    ASRAdversarialDurationBucket,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialLongContextPosition,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSemanticLoad,
    ASRAdversarialSpeakingRate,
    ASRAdversarialSuiteDefinition,
    build_asr_adversarial_evidence_v1,
    calculate_asr_adversarial_evidence_sha256,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE,
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS,
)
from hvee.packs.asr.adversarial_human_external_voices_reference_transcripts_v1 import (
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS,
    ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S,
    build_asr_adversarial_voices_reference_transcripts_v1,
)


ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_KEY = (
    "hetren.asr.adversarial-human-external-"
    "voices-babble-matched-control-suite"
)

ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT = 32
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_ARM = 16
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_SOURCE = 16
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_SOURCE_ARM = 8

ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM = "babble"
ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM = "control"


class ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
    ValueError,
):
    """Raised when verified pairs cannot form the frozen 32-case suite."""


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
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
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
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
            "VOiCES matched-control suite must be deterministic JSON."
        ) from error


def _reference_transcript_by_source(
) -> dict[
    tuple[int, int, int],
    tuple[str, str],
]:
    if (
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS
        != ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
        or len(
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS
        )
        != len(
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S
        )
        != len(
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS
        )
    ):
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
            "VOiCES matched-control transcript population changed."
        )

    result = {}

    for source_key, transcript, transcript_sha256 in zip(
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS,
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS,
        ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S,
        strict=True,
    ):
        observed_sha256 = hashlib.sha256(
            transcript.encode(
                "utf-8"
            )
        ).hexdigest()

        if observed_sha256 != transcript_sha256:
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES matched-control reference transcript changed."
            )

        result[
            source_key
        ] = (
            transcript,
            transcript_sha256,
        )

    return result


def _case_id(
    *,
    pair_key: ASRAdversarialVOiCESMatchedControlPairKey,
    arm: str,
) -> str:
    speaker_id, chapter_id, segment_id = (
        pair_key.source_key
    )

    return (
        f"voices-{arm}-"
        f"sp{speaker_id:04d}-"
        f"ch{chapter_id:06d}-"
        f"sg{segment_id:04d}-"
        f"{pair_key.room}-"
        f"mc{pair_key.microphone_id:02d}-"
        f"dg{pair_key.angle_degrees:03d}"
    )


def _microphone_class(
    microphone_id: int,
) -> str:
    if microphone_id == 1:
        return "studio-close"

    if microphone_id == 5:
        return "studio-far"

    raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
        "VOiCES matched-control microphone class is unsupported."
    )


def _case_tags(
    arm: str,
) -> tuple[str, ...]:
    condition_tag = (
        "babble-interference"
        if arm
        == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
        else "no-distractor-control"
    )

    return tuple(
        sorted(
            (
                condition_tag,
                "development",
                "physical-capture",
                "real-room",
                "semantic-control",
                "voices",
            )
        )
    )


def _description(
    arm: str,
) -> str:
    if (
        arm
        == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
    ):
        return (
            "Verified VOiCES real-room babble capture matched to an exact "
            "no-distractor control under the same foreground, room, "
            "microphone, angle, format, sample-count, and duration conditions."
        )

    return (
        "Verified VOiCES real-room no-distractor control matched to an exact "
        "babble capture under the same foreground, room, microphone, angle, "
        "format, sample-count, and duration conditions."
    )


def _expected_noise(
    arm: str,
) -> ASRAdversarialNoiseCondition:
    if (
        arm
        == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
    ):
        return ASRAdversarialNoiseCondition.MODERATE

    return ASRAdversarialNoiseCondition.NONE


def _semantic_control(
) -> ASRAdversarialSemanticLoad:
    return ASRAdversarialSemanticLoad(
        critical_number_count=0,
        critical_identifier_count=0,
        critical_terminology_count=0,
        spoken_number_variation=False,
        multiple_critical_items=False,
        duplicate_critical_items=False,
        ordering_challenge=False,
        long_context_position=(
            ASRAdversarialLongContextPosition.NONE
        ),
        control_case=True,
    )


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialVOiCESMatchedControlExecutionCase:
    """One ASR case bound to its verified local materialized capture."""

    pair_key: ASRAdversarialVOiCESMatchedControlPairKey
    arm: str
    case: ASRAdversarialCase
    media: ASRAdversarialVOiCESMaterializedMedia
    reference_transcript_sha256: str

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.pair_key,
            ASRAdversarialVOiCESMatchedControlPairKey,
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case pair key is invalid."
            )

        if self.arm not in {
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
        }:
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case arm is invalid."
            )

        if not isinstance(
            self.case,
            ASRAdversarialCase,
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case definition is invalid."
            )

        if (
            not isinstance(
                self.media,
                ASRAdversarialVOiCESMaterializedMedia,
            )
            or self.media.kind != "capture"
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case requires verified capture media."
            )

        if (
            self.media.codec_name != "pcm_s16le"
            or self.media.channel_count != 1
            or self.media.bits_per_sample != 16
            or self.media.sample_width_bytes != 2
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case linear-PCM mapping changed."
            )

        _require_sha256(
            name="VOiCES execution reference transcript",
            value=self.reference_transcript_sha256,
        )

        expected_case_id = _case_id(
            pair_key=self.pair_key,
            arm=self.arm,
        )

        expected_distractor = (
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE
            if self.arm
            == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
            else ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL
        )

        try:
            capture_condition = (
                self.media.require_capture_condition()
            )
        except ValueError as error:
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution capture condition is unavailable."
            ) from error

        if (
            self.case.case_id != expected_case_id
            or self.case.audio_asset_sha256
            != self.media.sha256
            or self.media.source_key
            != self.pair_key.source_key
            or capture_condition.room
            != self.pair_key.room
            or capture_condition.microphone_id
            != self.pair_key.microphone_id
            or capture_condition.angle_degrees
            != self.pair_key.angle_degrees
            or capture_condition.distractor
            != expected_distractor
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case media binding changed."
            )

        observed_transcript_sha256 = hashlib.sha256(
            self.case.reference_transcript.encode(
                "utf-8"
            )
        ).hexdigest()

        if (
            observed_transcript_sha256
            != self.reference_transcript_sha256
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case transcript binding changed."
            )

        expected_condition = ASRAdversarialCondition(
            channel=ASRAdversarialChannel.CLEAN,
            codec=ASRAdversarialCodec.LINEAR_PCM,
            sample_rate_hz=(
                self.media.sample_rate_hz
            ),
            microphone_class=_microphone_class(
                self.pair_key.microphone_id
            ),
            noise=_expected_noise(
                self.arm
            ),
            speaking_rate=(
                ASRAdversarialSpeakingRate.NORMAL
            ),
            speech_variety_key=(
                f"voices-source-{self.pair_key.source_key[0]:04d}"
            ),
            overlap=ASRAdversarialOverlapCondition.NONE,
            duration=ASRAdversarialDurationBucket.SHORT,
        )

        if self.case.condition != expected_condition:
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case condition mapping changed."
            )

        if (
            self.case.semantic_load
            != _semantic_control()
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case semantic boundary changed."
            )

        if self.case.description != _description(
            self.arm
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case description changed."
            )

        if self.case.tags != _case_tags(
            self.arm
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES execution case tags changed."
            )


def _execution_case(
    *,
    pair: ASRAdversarialVOiCESMatchedControlPair,
    arm: str,
    media: ASRAdversarialVOiCESMaterializedMedia,
    transcript: str,
    transcript_sha256: str,
) -> ASRAdversarialVOiCESMatchedControlExecutionCase:
    try:
        case = ASRAdversarialCase(
            case_id=_case_id(
                pair_key=pair.key,
                arm=arm,
            ),
            audio_asset_sha256=media.sha256,
            reference_transcript=transcript,
            condition=ASRAdversarialCondition(
                channel=ASRAdversarialChannel.CLEAN,
                codec=ASRAdversarialCodec.LINEAR_PCM,
                sample_rate_hz=(
                    media.sample_rate_hz
                ),
                microphone_class=(
                    _microphone_class(
                        pair.key.microphone_id
                    )
                ),
                noise=_expected_noise(
                    arm
                ),
                speaking_rate=(
                    ASRAdversarialSpeakingRate.NORMAL
                ),
                speech_variety_key=(
                    f"voices-source-{pair.key.source_key[0]:04d}"
                ),
                overlap=(
                    ASRAdversarialOverlapCondition.NONE
                ),
                duration=(
                    ASRAdversarialDurationBucket.SHORT
                ),
            ),
            semantic_load=_semantic_control(),
            description=_description(
                arm
            ),
            tags=_case_tags(
                arm
            ),
        )
    except HveeContractError as error:
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
            "VOiCES matched-control ASR case construction failed."
        ) from error

    return ASRAdversarialVOiCESMatchedControlExecutionCase(
        pair_key=pair.key,
        arm=arm,
        case=case,
        media=media,
        reference_transcript_sha256=(
            transcript_sha256
        ),
    )


def _binding_payload(
    binding: ASRAdversarialVOiCESMatchedControlExecutionCase,
) -> dict[str, object]:
    return {
        "case_id": binding.case.case_id,
        "arm": binding.arm,
        "pair_key": {
            "source_key": list(
                binding.pair_key.source_key
            ),
            "room": binding.pair_key.room,
            "microphone_id": (
                binding.pair_key.microphone_id
            ),
            "angle_degrees": (
                binding.pair_key.angle_degrees
            ),
        },
        "media_relative_path": (
            binding.media.relative_path
        ),
        "audio_asset_sha256": (
            binding.case.audio_asset_sha256
        ),
        "reference_transcript_sha256": (
            binding.reference_transcript_sha256
        ),
    }


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialVOiCESMatchedControlSuiteBundle:
    """Deterministic execution-ready, non-executed 32-case VOiCES suite."""

    matched_control_projection_sha256: str
    reference_transcripts_contract_sha256: str
    projection: ASRAdversarialVOiCESMatchedControlProjectionBundle
    definition: ASRAdversarialSuiteDefinition
    evidence: ASRAdversarialEvidenceBundle
    cases: tuple[
        ASRAdversarialVOiCESMatchedControlExecutionCase,
        ...,
    ]

    development_evidence_only: bool = True
    reference_transcripts_projected: bool = True
    adversarial_suite_built: bool = True
    execution_ready: bool = True
    asr_execution_verified: bool = False
    qualification_threshold_applied: bool = False
    production_qualified: bool = False
    release_enforcement_eligible: bool = False
    official_release_verdict_modified: bool = False

    def __post_init__(
        self,
    ) -> None:
        _require_sha256(
            name="VOiCES matched-control projection",
            value=self.matched_control_projection_sha256,
        )
        _require_sha256(
            name="VOiCES reference-transcript contract",
            value=self.reference_transcripts_contract_sha256,
        )

        if (
            self.reference_transcripts_contract_sha256
            != ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES suite reference-transcript identity changed."
            )

        if not isinstance(
            self.projection,
            ASRAdversarialVOiCESMatchedControlProjectionBundle,
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES suite matched-control projection is invalid."
            )

        if (
            self.matched_control_projection_sha256
            != self.projection.sha256
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES suite matched-control projection identity changed."
            )

        if not isinstance(
            self.definition,
            ASRAdversarialSuiteDefinition,
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES suite definition is invalid."
            )

        if not isinstance(
            self.evidence,
            ASRAdversarialEvidenceBundle,
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES suite evidence is invalid."
            )

        if (
            not isinstance(
                self.cases,
                tuple,
            )
            or len(
                self.cases
            )
            != ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
            or any(
                not isinstance(
                    case,
                    ASRAdversarialVOiCESMatchedControlExecutionCase,
                )
                for case in self.cases
            )
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES matched-control suite population changed."
            )

        case_definitions = tuple(
            binding.case
            for binding in self.cases
        )

        expected_projection_bindings = tuple(
            sorted(
                (
                    (
                        pair.key,
                        arm,
                        media,
                    )
                    for pair in self.projection.pairs
                    for arm, media in (
                        (
                            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
                            pair.interference,
                        ),
                        (
                            ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
                            pair.control,
                        ),
                    )
                ),
                key=lambda value: _case_id(
                    pair_key=value[0],
                    arm=value[1],
                ),
            )
        )

        observed_projection_bindings = tuple(
            (
                binding.pair_key,
                binding.arm,
                binding.media,
            )
            for binding in self.cases
        )

        if (
            observed_projection_bindings
            != expected_projection_bindings
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES suite matched-control projection binding changed."
            )

        transcript_by_source = (
            _reference_transcript_by_source()
        )

        if any(
            (
                binding.case.reference_transcript,
                binding.reference_transcript_sha256,
            )
            != transcript_by_source[
                binding.pair_key.source_key
            ]
            for binding in self.cases
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES suite reference-transcript binding changed."
            )

        if (
            self.definition.key
            != ASR_ADVERSARIAL_EVIDENCE_KEY
            or self.definition.version
            != ASR_ADVERSARIAL_EVIDENCE_VERSION
            or self.definition.cases
            != case_definitions
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES matched-control suite definition changed."
            )

        case_ids = tuple(
            binding.case.case_id
            for binding in self.cases
        )

        media_sha256s = tuple(
            binding.media.sha256
            for binding in self.cases
        )

        if (
            case_ids
            != tuple(
                sorted(
                    case_ids
                )
            )
            or len(
                case_ids
            )
            != len(
                set(
                    case_ids
                )
            )
            or len(
                media_sha256s
            )
            != len(
                set(
                    media_sha256s
                )
            )
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES suite cases must have unique ordered identities."
            )

        arm_counts = Counter(
            binding.arm
            for binding in self.cases
        )

        source_counts = Counter(
            binding.pair_key.source_key
            for binding in self.cases
        )

        source_arm_counts = Counter(
            (
                binding.pair_key.source_key,
                binding.arm,
            )
            for binding in self.cases
        )

        if arm_counts != Counter(
            {
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM: (
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_ARM
                ),
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM: (
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_ARM
                ),
            }
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES matched-control suite arm balance changed."
            )

        if source_counts != Counter(
            {
                source_key: (
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_SOURCE
                )
                for source_key in (
                    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
                )
            }
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES matched-control suite source balance changed."
            )

        expected_source_arm_counts = Counter(
            {
                (
                    source_key,
                    arm,
                ): (
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASES_PER_SOURCE_ARM
                )
                for source_key in (
                    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
                )
                for arm in (
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM,
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM,
                )
            }
        )

        if source_arm_counts != expected_source_arm_counts:
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES matched-control suite source-arm balance changed."
            )

        rebuilt_evidence = build_asr_adversarial_evidence_v1(
            self.definition
        )

        if (
            calculate_asr_adversarial_evidence_sha256(
                self.evidence.payload
            )
            != self.evidence.sha256
            or self.evidence != rebuilt_evidence
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES matched-control suite evidence changed."
            )

        positive_authority = (
            self.development_evidence_only,
            self.reference_transcripts_projected,
            self.adversarial_suite_built,
            self.execution_ready,
        )

        negative_authority = (
            self.asr_execution_verified,
            self.qualification_threshold_applied,
            self.production_qualified,
            self.release_enforcement_eligible,
            self.official_release_verdict_modified,
        )

        if (
            any(
                value is not True
                for value in positive_authority
            )
            or any(
                value is not False
                for value in negative_authority
            )
        ):
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES matched-control suite authority boundary changed."
            )

    @property
    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_SCHEMA_VERSION
            ),
            "artifact": {
                "key": (
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_KEY
                ),
                "version": (
                    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_VERSION
                ),
                "type": (
                    "execution_ready_verified_matched_control_asr_suite"
                ),
            },
            "upstream": {
                "matched_control_projection_sha256": (
                    self.matched_control_projection_sha256
                ),
                "reference_transcripts_contract_sha256": (
                    self.reference_transcripts_contract_sha256
                ),
                "adversarial_evidence_sha256": (
                    self.evidence.sha256
                ),
            },
            "suite": {
                "case_count": len(
                    self.cases
                ),
                "pair_count": (
                    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
                ),
                "babble_case_count": sum(
                    binding.arm
                    == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
                    for binding in self.cases
                ),
                "control_case_count": sum(
                    binding.arm
                    == ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
                    for binding in self.cases
                ),
                "ordered_case_ids": [
                    binding.case.case_id
                    for binding in self.cases
                ],
                "ordered_audio_asset_sha256s": [
                    binding.case.audio_asset_sha256
                    for binding in self.cases
                ],
                "case_bindings": [
                    _binding_payload(
                        binding
                    )
                    for binding in self.cases
                ],
            },
            "condition_methodology": {
                "physical_babble_presence_verified": True,
                "matched_no_distractor_control_verified": True,
                "room_microphone_angle_metadata_verified": True,
                "linear_pcm_transport_verified": True,
                "channel_clean_value_means_non_telephony_transport": True,
                "noise_severity_bucket_caller_declared": True,
                "speaking_rate_bucket_caller_declared": True,
                "duration_bucket_caller_declared": True,
                "conversational_speaker_overlap_declared": False,
                "critical_semantic_items_declared": False,
            },
            "evidence_boundary": {
                "development_evidence_only": True,
                "verified_materialized_media_consumed": True,
                "reference_transcripts_projected": True,
                "adversarial_suite_built": True,
                "execution_inputs_bound": True,
                "execution_ready": True,
                "raw_audio_embedded": False,
                "source_audio_spoken_content_independently_verified": False,
                "babble_speaker_transcripts_verified": False,
                "conversational_speaker_overlap_verified": False,
                "critical_semantic_qualification_supported": False,
                "asr_execution_verified": False,
                "qualification_threshold_applied": False,
                "certification_issued": False,
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

    def require_asr_execution_verified(
        self,
    ) -> None:
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
            "VOiCES matched-control suite is execution-ready but no ASR "
            "execution evidence has been verified."
        )


def project_asr_adversarial_voices_babble_matched_control_suite_v1(
    projection: ASRAdversarialVOiCESMatchedControlProjectionBundle,
) -> ASRAdversarialVOiCESMatchedControlSuiteBundle:
    """Build exactly 32 transcript-bound cases from 16 verified pairs."""

    if not isinstance(
        projection,
        ASRAdversarialVOiCESMatchedControlProjectionBundle,
    ):
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
            "VOiCES suite projection requires verified matched-control pairs."
        )

    if (
        projection.development_evidence_only
        is not True
        or projection.reference_transcripts_projected
        is not False
        or projection.adversarial_suite_built
        is not False
        or projection.asr_execution_verified
        is not False
        or projection.qualification_threshold_applied
        is not False
        or projection.production_qualified
        is not False
        or projection.release_enforcement_eligible
        is not False
        or projection.official_release_verdict_modified
        is not False
    ):
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
            "VOiCES matched-control projection authority boundary changed."
        )

    transcript_contract = (
        build_asr_adversarial_voices_reference_transcripts_v1()
    )

    if (
        transcript_contract.sha256
        != ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
    ):
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
            "VOiCES reference-transcript contract identity changed."
        )

    transcript_by_source = (
        _reference_transcript_by_source()
    )

    projected_cases = []

    for pair in projection.pairs:
        if pair.key.source_key not in transcript_by_source:
            raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
                "VOiCES matched-control source lacks a reference transcript."
            )

        transcript, transcript_sha256 = (
            transcript_by_source[
                pair.key.source_key
            ]
        )

        projected_cases.extend(
            (
                _execution_case(
                    pair=pair,
                    arm=(
                        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_BABBLE_ARM
                    ),
                    media=pair.interference,
                    transcript=transcript,
                    transcript_sha256=(
                        transcript_sha256
                    ),
                ),
                _execution_case(
                    pair=pair,
                    arm=(
                        ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CONTROL_ARM
                    ),
                    media=pair.control,
                    transcript=transcript,
                    transcript_sha256=(
                        transcript_sha256
                    ),
                ),
            )
        )

    cases = tuple(
        sorted(
            projected_cases,
            key=lambda binding: (
                binding.case.case_id
            ),
        )
    )

    try:
        definition = ASRAdversarialSuiteDefinition(
            key=ASR_ADVERSARIAL_EVIDENCE_KEY,
            version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
            cases=tuple(
                binding.case
                for binding in cases
            ),
        )

        evidence = build_asr_adversarial_evidence_v1(
            definition
        )
    except HveeContractError as error:
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
            "VOiCES matched-control adversarial suite construction failed."
        ) from error

    bundle = ASRAdversarialVOiCESMatchedControlSuiteBundle(
        matched_control_projection_sha256=(
            projection.sha256
        ),
        reference_transcripts_contract_sha256=(
            transcript_contract.sha256
        ),
        projection=projection,
        definition=definition,
        evidence=evidence,
        cases=cases,
    )

    if (
        len(
            bundle.cases
        )
        != ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
        or len(
            {
                binding.case.audio_asset_sha256
                for binding in bundle.cases
            }
        )
        != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT
    ):
        raise ASRAdversarialVOiCESMatchedControlSuiteProjectionError(
            "VOiCES matched-control adversarial suite population changed."
        )

    return bundle
