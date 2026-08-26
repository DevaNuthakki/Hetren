"""Frozen execution binding for ASR Brutal Validation v1.

This module assembles the declared 13-case development campaign, verifies every
audio asset before execution, and delegates execution to Hetren's generic ASR
campaign service. It grants no qualification or release authority.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from app.adversarial_asr_brutal_media import (
    ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION,
    ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION,
)
from app.adversarial_asr_campaign_service import (
    ASRAdversarialCampaignServiceResult,
    execute_asr_adversarial_campaign,
)
from app.speech import ASRProvider
from hvee.packs.asr import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCase,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialNoiseCondition,
    ASRAdversarialSuiteDefinition,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
    ASRCriticalTerminologyProfile,
    ASRCriticalTerminologyTerm,
    build_asr_adversarial_evidence_v1,
)
from hvee.packs.asr.adversarial_corpus_v1 import (
    build_asr_adversarial_corpus_v1,
)
from hvee.packs.asr.brutal_validation_plan import (
    ASR_BRUTAL_VALIDATION_CASES_V1,
)


ASR_BRUTAL_VALIDATION_CAMPAIGN_VERSION = "1.0.0"
ASR_BRUTAL_VALIDATION_MODELS_V1 = (
    "small.en",
    "large-v3-turbo",
)


class ASRBrutalValidationCampaignError(ValueError):
    """Raised when the frozen campaign cannot be assembled safely."""


@dataclass(frozen=True)
class ASRBrutalValidationMediaIdentity:
    case_id: str
    relative_path: str
    audio_asset_sha256: str
    brutal_generated: bool = False


@dataclass(frozen=True)
class ASRBrutalValidationStressDefinition:
    identity: ASRBrutalValidationMediaIdentity
    channel: ASRAdversarialChannel
    codec: ASRAdversarialCodec
    sample_rate_hz: int
    noise: ASRAdversarialNoiseCondition


@dataclass(frozen=True)
class ASRBrutalValidationSuiteBundle:
    suite: ASRAdversarialSuiteDefinition
    suite_evidence: ASRAdversarialEvidenceBundle
    audio_paths: Mapping[str, Path]


_CANONICAL_MEDIA = (
    ASRBrutalValidationMediaIdentity(
        case_id="clean.multi-number-id",
        relative_path="clean/clean.multi-number-id.wav",
        audio_asset_sha256=(
            "23f9af39d01afe47e932bd061467bd0b"
            "5f49dc8bf520c2a8296a4556c54f1297"
        ),
    ),
    ASRBrutalValidationMediaIdentity(
        case_id="clean.identifier-confirmation",
        relative_path="clean/clean.identifier-confirmation.wav",
        audio_asset_sha256=(
            "ebfba31f5c69634d577718bfb9cec6a"
            "551c1e2afaab2cb8f9b19b5e7536efc33"
        ),
    ),
    ASRBrutalValidationMediaIdentity(
        case_id="clean.number-measurement",
        relative_path="clean/clean.number-measurement.wav",
        audio_asset_sha256=(
            "a3045d975c99903e108281951cba856c"
            "695ca0cc96f8d77dcb3279dc1a24fd36"
        ),
    ),
    ASRBrutalValidationMediaIdentity(
        case_id="control.clean-critical",
        relative_path="clean/control.clean-critical.wav",
        audio_asset_sha256=(
            "f97e1d36b87676aaacf4dbd8059fa8fe"
            "f2d323d23cfb8468aa22426f05dbd3b3"
        ),
    ),
)


_STRESS_DEFINITIONS = (
    ASRBrutalValidationStressDefinition(
        identity=ASRBrutalValidationMediaIdentity(
            "stress.codec-mulaw.multi-number-id",
            "telephony/stress.codec-mulaw.multi-number-id.wav",
            (
                "496f71b707275a770c7bdab00a7c705d"
                "740e9cbfd9a1fab0519ffc69faf1e68b"
            ),
        ),
        channel=ASRAdversarialChannel.TELEPHONY,
        codec=ASRAdversarialCodec.MULAW,
        sample_rate_hz=8_000,
        noise=ASRAdversarialNoiseCondition.NONE,
    ),
    ASRBrutalValidationStressDefinition(
        identity=ASRBrutalValidationMediaIdentity(
            "stress.codec-alaw.multi-number-id",
            "telephony/stress.codec-alaw.multi-number-id.wav",
            (
                "b9c1b7fdb0b2426dea18fd7cbbbec677"
                "08170f5a93c3c85d3999c4ab3da7cc60"
            ),
        ),
        channel=ASRAdversarialChannel.TELEPHONY,
        codec=ASRAdversarialCodec.ALAW,
        sample_rate_hz=8_000,
        noise=ASRAdversarialNoiseCondition.NONE,
    ),
    ASRBrutalValidationStressDefinition(
        identity=ASRBrutalValidationMediaIdentity(
            "stress.telephony-bandwidth.multi-number-id",
            "telephony/stress.telephony-bandwidth.multi-number-id.wav",
            (
                "eca7b899ffece23f005586096e44ed9a"
                "039fdb29c493d17364e225894371f169"
            ),
        ),
        channel=ASRAdversarialChannel.TELEPHONY,
        codec=ASRAdversarialCodec.LINEAR_PCM,
        sample_rate_hz=8_000,
        noise=ASRAdversarialNoiseCondition.NONE,
    ),
    ASRBrutalValidationStressDefinition(
        identity=ASRBrutalValidationMediaIdentity(
            "stress.codec-aac.multi-number-id",
            "lossy/stress.codec-aac.multi-number-id.m4a",
            (
                "1f303beee42f35d86f920487fbbb67e8"
                "70576f7278a1d3b6bd97a7bd6e67fb09"
            ),
        ),
        channel=ASRAdversarialChannel.CLEAN,
        codec=ASRAdversarialCodec.LOSSY_COMPRESSED,
        sample_rate_hz=16_000,
        noise=ASRAdversarialNoiseCondition.NONE,
    ),
    ASRBrutalValidationStressDefinition(
        identity=ASRBrutalValidationMediaIdentity(
            "stress.codec-mp3.multi-number-id",
            "lossy/stress.codec-mp3.multi-number-id.mp3",
            (
                "938fc367f744dee780d57c8b7e64f9dd"
                "781fe1e8599abbe4bb0987b8f844d2f3"
            ),
        ),
        channel=ASRAdversarialChannel.CLEAN,
        codec=ASRAdversarialCodec.LOSSY_COMPRESSED,
        sample_rate_hz=16_000,
        noise=ASRAdversarialNoiseCondition.NONE,
    ),
    ASRBrutalValidationStressDefinition(
        identity=ASRBrutalValidationMediaIdentity(
            "stress.noise-moderate.multi-number-id",
            "noise/stress.noise-moderate.multi-number-id.wav",
            (
                "c82425954a14ce3f4276e3d902099a94"
                "7d1e8c0e773d758f0f4a68fd46e243cb"
            ),
        ),
        channel=ASRAdversarialChannel.CLEAN,
        codec=ASRAdversarialCodec.LINEAR_PCM,
        sample_rate_hz=16_000,
        noise=ASRAdversarialNoiseCondition.MODERATE,
    ),
    ASRBrutalValidationStressDefinition(
        identity=ASRBrutalValidationMediaIdentity(
            "stress.noise-severe-usable.multi-number-id",
            "noise/stress.noise-severe-usable.multi-number-id.wav",
            (
                "322bbee058df10d9f5a26f36c317f6be"
                "b4f3bc83900736afc724717cd1cc3779"
            ),
        ),
        channel=ASRAdversarialChannel.CLEAN,
        codec=ASRAdversarialCodec.LINEAR_PCM,
        sample_rate_hz=16_000,
        noise=ASRAdversarialNoiseCondition.SEVERE_USABLE,
    ),
)


_BRUTAL_MEDIA = (
    ASRBrutalValidationMediaIdentity(
        case_id=(
            ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION.case_id
        ),
        relative_path=(
            ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION
            .output_relative_path
        ),
        audio_asset_sha256=(
            ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION
            .audio_asset_sha256
        ),
        brutal_generated=True,
    ),
    ASRBrutalValidationMediaIdentity(
        case_id=(
            ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION.case_id
        ),
        relative_path=(
            ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION
            .output_relative_path
        ),
        audio_asset_sha256=(
            ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION
            .audio_asset_sha256
        ),
        brutal_generated=True,
    ),
)


ASR_BRUTAL_VALIDATION_MEDIA_V1 = (
    _CANONICAL_MEDIA[:3]
    + tuple(
        item.identity
        for item in _STRESS_DEFINITIONS
    )
    + _CANONICAL_MEDIA[3:]
    + _BRUTAL_MEDIA
)


ASR_BRUTAL_TERMINOLOGY_PROFILE_V1 = (
    ASRCriticalTerminologyProfile(
        key="brutal-validation.terminology-profile",
        version="1.0.0",
        language="en",
        locale="en-US",
        terms=(
            ASRCriticalTerminologyTerm(
                term_key="medication.cardiovex",
                canonical_text="Cardiovex",
                accepted_surfaces=(
                    "Cardiovex",
                ),
            ),
        ),
    )
)


ASR_BRUTAL_TERMINOLOGY_BINDING_V1 = (
    ASRAdversarialTerminologyBinding(
        state=(
            ASRAdversarialTerminologyState
            .CONFIGURED
        ),
        profile=ASR_BRUTAL_TERMINOLOGY_PROFILE_V1,
    )
)


def _sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _stress_case(
    source: ASRAdversarialCase,
    definition: ASRBrutalValidationStressDefinition,
) -> ASRAdversarialCase:
    condition = replace(
        source.condition,
        channel=definition.channel,
        codec=definition.codec,
        sample_rate_hz=(
            definition.sample_rate_hz
        ),
        noise=definition.noise,
    )

    return replace(
        source,
        case_id=definition.identity.case_id,
        audio_asset_sha256=(
            definition.identity.audio_asset_sha256
        ),
        condition=condition,
        description=(
            "Frozen ASR Brutal Validation v1 "
            "stress derivative."
        ),
        tags=(
            "asr",
            "brutal",
            "stress",
            "synthetic",
        ),
    )


def _brutal_case(
    source: ASRAdversarialCase,
    identity: ASRBrutalValidationMediaIdentity,
    *,
    codec: ASRAdversarialCodec,
    noise: ASRAdversarialNoiseCondition,
) -> ASRAdversarialCase:
    condition = replace(
        source.condition,
        channel=(
            ASRAdversarialChannel.TELEPHONY
        ),
        codec=codec,
        sample_rate_hz=8_000,
        noise=noise,
    )

    return replace(
        source,
        case_id=identity.case_id,
        audio_asset_sha256=(
            identity.audio_asset_sha256
        ),
        condition=condition,
        description=(
            "Frozen required-new ASR Brutal "
            "Validation v1 case."
        ),
        tags=(
            "asr",
            "brutal",
            "required-new",
            "synthetic",
            "telephony",
        ),
    )


def build_asr_brutal_validation_suite_v1(
) -> tuple[
    ASRAdversarialSuiteDefinition,
    ASRAdversarialEvidenceBundle,
]:
    (
        canonical_suite,
        _evidence,
        _definition,
        _manifest,
    ) = build_asr_adversarial_corpus_v1()

    canonical = {
        case.case_id: case
        for case in canonical_suite.cases
    }

    multi_number = canonical[
        "clean.multi-number-id"
    ]

    clean_critical = canonical[
        "control.clean-critical"
    ]

    cases_by_id = {
        case_id: canonical[case_id]
        for case_id in (
            "clean.multi-number-id",
            "clean.identifier-confirmation",
            "clean.number-measurement",
            "control.clean-critical",
        )
    }

    cases_by_id.update(
        {
            definition.identity.case_id: (
                _stress_case(
                    multi_number,
                    definition,
                )
            )
            for definition
            in _STRESS_DEFINITIONS
        }
    )

    cases_by_id[
        _BRUTAL_MEDIA[0].case_id
    ] = _brutal_case(
        clean_critical,
        _BRUTAL_MEDIA[0],
        codec=ASRAdversarialCodec.LINEAR_PCM,
        noise=ASRAdversarialNoiseCondition.MODERATE,
    )

    cases_by_id[
        _BRUTAL_MEDIA[1].case_id
    ] = _brutal_case(
        clean_critical,
        _BRUTAL_MEDIA[1],
        codec=ASRAdversarialCodec.MULAW,
        noise=ASRAdversarialNoiseCondition.SEVERE_USABLE,
    )

    planned_case_ids = tuple(
        planned.case_id for planned in ASR_BRUTAL_VALIDATION_CASES_V1
    )
    if set(cases_by_id) != set(planned_case_ids):
        raise ASRBrutalValidationCampaignError(
            "Frozen suite and brutal validation plan case IDs differ."
        )

    ordered_case_ids = tuple(sorted(planned_case_ids))

    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=tuple(cases_by_id[case_id] for case_id in ordered_case_ids),
    )
    return suite, build_asr_adversarial_evidence_v1(suite)


def _verified_path(
    root: Path,
    identity: ASRBrutalValidationMediaIdentity,
) -> Path:
    path = (
        root / identity.relative_path
    ).resolve(strict=True)

    if not path.is_relative_to(root):
        raise ASRBrutalValidationCampaignError(
            "Audio path escapes its declared root: "
            f"{identity.case_id}."
        )

    if not path.is_file():
        raise ASRBrutalValidationCampaignError(
            "Audio asset is not a file: "
            f"{identity.case_id}."
        )

    if _sha256_file(path) != identity.audio_asset_sha256:
        raise ASRBrutalValidationCampaignError(
            "Audio identity mismatch: "
            f"{identity.case_id}."
        )

    return path


def bind_asr_brutal_validation_media_v1(
    *,
    corpus_generated_root: str | Path,
    brutal_generated_root: str | Path,
) -> ASRBrutalValidationSuiteBundle:
    corpus_root = Path(
        corpus_generated_root
    ).resolve(strict=True)
    brutal_root = Path(
        brutal_generated_root
    ).resolve(strict=True)

    suite, suite_evidence = (
        build_asr_brutal_validation_suite_v1()
    )
    identities = {
        identity.case_id: identity
        for identity in ASR_BRUTAL_VALIDATION_MEDIA_V1
    }
    audio_paths = {}

    for case in suite.cases:
        identity = identities[case.case_id]
        root = (
            brutal_root
            if identity.brutal_generated
            else corpus_root
        )
        audio_paths[case.case_id] = _verified_path(
            root,
            identity,
        )

    return ASRBrutalValidationSuiteBundle(
        suite=suite,
        suite_evidence=suite_evidence,
        audio_paths=MappingProxyType(audio_paths),
    )


def execute_asr_brutal_validation_campaign_v1(
    *,
    campaign_id: str,
    requested_model_name: str,
    provider: ASRProvider,
    bundle: ASRBrutalValidationSuiteBundle,
) -> ASRAdversarialCampaignServiceResult:
    if requested_model_name not in ASR_BRUTAL_VALIDATION_MODELS_V1:
        raise ASRBrutalValidationCampaignError(
            "Model is outside the frozen Brutal "
            "Validation v1 comparison."
        )

    return execute_asr_adversarial_campaign(
        campaign_id=campaign_id,
        campaign_version=ASR_BRUTAL_VALIDATION_CAMPAIGN_VERSION,
        audio_paths=bundle.audio_paths,
        requested_model_name=requested_model_name,
        provider=provider,
        terminology=ASR_BRUTAL_TERMINOLOGY_BINDING_V1,
        suite=bundle.suite,
        suite_evidence=bundle.suite_evidence,
    )
