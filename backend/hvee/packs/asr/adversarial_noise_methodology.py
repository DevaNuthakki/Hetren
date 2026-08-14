"""Deterministic acoustic-noise methodology for adversarial ASR evidence.

This module defines Hetren's first numeric background-noise methodology.

The labels ``moderate`` and ``severe_usable`` are Hetren v1 operational
categories backed by explicit target signal-to-noise ratios. They are not
claimed to be universal acoustic-severity definitions.

This contract defines methodology only. It does not by itself establish
that any audio asset satisfies the methodology, issue certification,
qualify an evaluator for production, or modify release authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_evidence import (
    ASRAdversarialNoiseCondition,
)


ASR_ADVERSARIAL_NOISE_METHODOLOGY_SCHEMA_VERSION = 1

ASR_ADVERSARIAL_NOISE_METHODOLOGY_KEY = (
    "hetren.asr.adversarial-noise-methodology.en-us"
)

ASR_ADVERSARIAL_NOISE_METHODOLOGY_VERSION = "1.0.0"


ASR_ADVERSARIAL_NOISE_V1_SEED = 39_039

ASR_ADVERSARIAL_NOISE_V1_SAMPLE_RATE_HZ = 16_000

ASR_ADVERSARIAL_NOISE_V1_CHANNEL_COUNT = 1

ASR_ADVERSARIAL_NOISE_V1_SNR_TOLERANCE_MILLIDB = 100

ASR_ADVERSARIAL_NOISE_V1_MODERATE_SNR_MILLIDB = 10_000

ASR_ADVERSARIAL_NOISE_V1_SEVERE_USABLE_SNR_MILLIDB = 5_000


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(
            character not in (
                "abcdefghijklmnopqrstuvwxyz"
                "0123456789._-"
            )
            for character in value
        )
        or not value[0].isalpha()
    ):
        raise HveeContractError(
            f"{name} must be canonical identifier text"
        )

    return value


def _require_positive_integer(
    *,
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise HveeContractError(
            f"{name} must be a positive integer"
        )

    return value


def _canonical_json(
    value: object,
) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "noise methodology must be deterministic JSON"
        ) from exc


def calculate_asr_adversarial_noise_methodology_sha256(
    payload: object,
) -> str:
    """Hash canonical noise-methodology evidence."""

    return hashlib.sha256(
        _canonical_json(
            payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialNoiseTier:
    """One Hetren v1 numeric noise-severity tier."""

    condition: ASRAdversarialNoiseCondition
    target_snr_millidb: int

    def __post_init__(self) -> None:
        if not isinstance(
            self.condition,
            ASRAdversarialNoiseCondition,
        ):
            raise HveeContractError(
                "noise tier condition requires a versioned enum"
            )

        if (
            self.condition
            == ASRAdversarialNoiseCondition.NONE
        ):
            raise HveeContractError(
                "noise methodology tier cannot use none"
            )

        _require_positive_integer(
            name="noise target SNR",
            value=self.target_snr_millidb,
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialNoiseMethodology:
    """Numeric and deterministic noise-generation methodology."""

    noise_family: str
    generator_key: str
    seed: int
    sample_rate_hz: int
    channel_count: int
    signal_measurement_key: str
    noise_measurement_key: str
    snr_formula_key: str
    snr_tolerance_millidb: int
    mixer_key: str
    normalize_mix: bool
    mix_duration_key: str
    dropout_transition_milliseconds: int
    volume_precision_key: str
    clipping_policy_key: str
    tiers: tuple[
        ASRAdversarialNoiseTier,
        ...,
    ]

    def __post_init__(self) -> None:
        for name, value in (
            (
                "noise family",
                self.noise_family,
            ),
            (
                "noise generator",
                self.generator_key,
            ),
            (
                "signal measurement",
                self.signal_measurement_key,
            ),
            (
                "noise measurement",
                self.noise_measurement_key,
            ),
            (
                "SNR formula",
                self.snr_formula_key,
            ),
            (
                "noise mixer",
                self.mixer_key,
            ),
            (
                "mix duration",
                self.mix_duration_key,
            ),
            (
                "volume precision",
                self.volume_precision_key,
            ),
            (
                "clipping policy",
                self.clipping_policy_key,
            ),
        ):
            _require_identifier(
                name=name,
                value=value,
            )

        if (
            isinstance(self.seed, bool)
            or not isinstance(
                self.seed,
                int,
            )
            or not 0
            <= self.seed
            <= 4_294_967_295
        ):
            raise HveeContractError(
                "noise seed must fit FFmpeg anoisesrc uint32"
            )

        if (
            isinstance(
                self.sample_rate_hz,
                bool,
            )
            or not isinstance(
                self.sample_rate_hz,
                int,
            )
            or not 8_000
            <= self.sample_rate_hz
            <= 192_000
        ):
            raise HveeContractError(
                "noise sample rate must be 8000..192000 Hz"
            )

        _require_positive_integer(
            name="noise channel count",
            value=self.channel_count,
        )

        _require_positive_integer(
            name="noise SNR tolerance",
            value=self.snr_tolerance_millidb,
        )

        if not isinstance(
            self.normalize_mix,
            bool,
        ):
            raise HveeContractError(
                "noise normalize_mix must be boolean"
            )

        if (
            isinstance(
                self.dropout_transition_milliseconds,
                bool,
            )
            or not isinstance(
                self.dropout_transition_milliseconds,
                int,
            )
            or self.dropout_transition_milliseconds < 0
        ):
            raise HveeContractError(
                "noise dropout transition must be non-negative"
            )

        if (
            not isinstance(
                self.tiers,
                tuple,
            )
            or not self.tiers
            or not all(
                isinstance(
                    tier,
                    ASRAdversarialNoiseTier,
                )
                for tier in self.tiers
            )
        ):
            raise HveeContractError(
                "noise methodology requires tiers"
            )

        conditions = tuple(
            tier.condition.value
            for tier in self.tiers
        )

        if conditions != tuple(
            sorted(
                conditions
            )
        ):
            raise HveeContractError(
                "noise tiers must be ordered by condition"
            )

        if len(
            conditions
        ) != len(
            set(
                conditions
            )
        ):
            raise HveeContractError(
                "noise tier conditions must be unique"
            )

        target_snrs = tuple(
            tier.target_snr_millidb
            for tier in self.tiers
        )

        if len(
            target_snrs
        ) != len(
            set(
                target_snrs
            )
        ):
            raise HveeContractError(
                "noise target SNR values must be unique"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialNoiseMethodologyBundle:
    """Canonical methodology payload and digest."""

    payload: dict[str, object]
    sha256: str


def build_asr_adversarial_noise_methodology_v1(
) -> ASRAdversarialNoiseMethodologyBundle:
    """Build Hetren's exact deterministic white-noise methodology v1."""

    methodology = ASRAdversarialNoiseMethodology(
        noise_family="white",
        generator_key="ffmpeg.anoisesrc",
        seed=(
            ASR_ADVERSARIAL_NOISE_V1_SEED
        ),
        sample_rate_hz=(
            ASR_ADVERSARIAL_NOISE_V1_SAMPLE_RATE_HZ
        ),
        channel_count=(
            ASR_ADVERSARIAL_NOISE_V1_CHANNEL_COUNT
        ),
        signal_measurement_key=(
            "pcm16.full-record-mean-square-v1"
        ),
        noise_measurement_key=(
            "pcm16.residual-mean-square-v1"
        ),
        snr_formula_key=(
            "power-ratio-10log10-v1"
        ),
        snr_tolerance_millidb=(
            ASR_ADVERSARIAL_NOISE_V1_SNR_TOLERANCE_MILLIDB
        ),
        mixer_key="ffmpeg.amix",
        normalize_mix=False,
        mix_duration_key="first",
        dropout_transition_milliseconds=0,
        volume_precision_key="double",
        clipping_policy_key="reject",
        tiers=(
            ASRAdversarialNoiseTier(
                condition=(
                    ASRAdversarialNoiseCondition.MODERATE
                ),
                target_snr_millidb=(
                    ASR_ADVERSARIAL_NOISE_V1_MODERATE_SNR_MILLIDB
                ),
            ),
            ASRAdversarialNoiseTier(
                condition=(
                    ASRAdversarialNoiseCondition.SEVERE_USABLE
                ),
                target_snr_millidb=(
                    ASR_ADVERSARIAL_NOISE_V1_SEVERE_USABLE_SNR_MILLIDB
                ),
            ),
        ),
    )

    payload: dict[str, object] = {
        "artifact": {
            "schema_version": (
                ASR_ADVERSARIAL_NOISE_METHODOLOGY_SCHEMA_VERSION
            ),
            "key": (
                ASR_ADVERSARIAL_NOISE_METHODOLOGY_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_NOISE_METHODOLOGY_VERSION
            ),
            "type": (
                "adversarial_noise_methodology"
            ),
        },
        "methodology": {
            "noise": {
                "family": methodology.noise_family,
                "generator_key": (
                    methodology.generator_key
                ),
                "seed": methodology.seed,
                "sample_rate_hz": (
                    methodology.sample_rate_hz
                ),
                "channel_count": (
                    methodology.channel_count
                ),
            },
            "measurement": {
                "signal_key": (
                    methodology.signal_measurement_key
                ),
                "noise_key": (
                    methodology.noise_measurement_key
                ),
                "snr_formula_key": (
                    methodology.snr_formula_key
                ),
                "snr_tolerance_millidb": (
                    methodology.snr_tolerance_millidb
                ),
            },
            "mixing": {
                "mixer_key": (
                    methodology.mixer_key
                ),
                "normalize": (
                    methodology.normalize_mix
                ),
                "duration_key": (
                    methodology.mix_duration_key
                ),
                "dropout_transition_milliseconds": (
                    methodology
                    .dropout_transition_milliseconds
                ),
                "volume_precision_key": (
                    methodology.volume_precision_key
                ),
                "clipping_policy_key": (
                    methodology.clipping_policy_key
                ),
            },
            "tiers": [
                {
                    "condition": (
                        tier.condition.value
                    ),
                    "target_snr_millidb": (
                        tier.target_snr_millidb
                    ),
                }
                for tier in methodology.tiers
            ],
        },
        "scientific_boundary": {
            "synthetic_white_noise_only": True,
            "natural_environmental_noise_represented": False,
            "universal_noise_severity_standard_claimed": False,
            "development_evidence_only": True,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
        },
    }

    return ASRAdversarialNoiseMethodologyBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_noise_methodology_sha256(
                payload
            )
        ),
    )


def verify_asr_adversarial_noise_methodology_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> ASRAdversarialNoiseMethodologyBundle:
    """Verify exact canonical Hetren noise methodology v1."""

    if (
        not isinstance(
            expected_sha256,
            str,
        )
        or len(
            expected_sha256
        ) != 64
        or any(
            character
            not in "0123456789abcdef"
            for character in expected_sha256
        )
    ):
        raise HveeContractError(
            "noise methodology expected SHA-256 is invalid"
        )

    canonical = (
        build_asr_adversarial_noise_methodology_v1()
    )

    if (
        payload
        != canonical.payload
        or expected_sha256
        != canonical.sha256
    ):
        raise HveeContractError(
            "noise methodology verification failed"
        )

    return canonical


__all__ = [
    "ASR_ADVERSARIAL_NOISE_METHODOLOGY_KEY",
    "ASR_ADVERSARIAL_NOISE_METHODOLOGY_SCHEMA_VERSION",
    "ASR_ADVERSARIAL_NOISE_METHODOLOGY_VERSION",
    "ASR_ADVERSARIAL_NOISE_V1_CHANNEL_COUNT",
    "ASR_ADVERSARIAL_NOISE_V1_MODERATE_SNR_MILLIDB",
    "ASR_ADVERSARIAL_NOISE_V1_SAMPLE_RATE_HZ",
    "ASR_ADVERSARIAL_NOISE_V1_SEED",
    "ASR_ADVERSARIAL_NOISE_V1_SEVERE_USABLE_SNR_MILLIDB",
    "ASR_ADVERSARIAL_NOISE_V1_SNR_TOLERANCE_MILLIDB",
    "ASRAdversarialNoiseMethodology",
    "ASRAdversarialNoiseMethodologyBundle",
    "ASRAdversarialNoiseTier",
    "build_asr_adversarial_noise_methodology_v1",
    "calculate_asr_adversarial_noise_methodology_sha256",
    "verify_asr_adversarial_noise_methodology_v1",
]
