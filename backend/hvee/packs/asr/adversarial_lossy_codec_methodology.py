"""Deterministic lossy-codec methodology for adversarial ASR evidence.

This module defines Hetren's first lossy-compression methodology for the
current ASR product ingestion surface.

Version 1 binds two production-representative formats:

- MP3 encoded with libmp3lame and stored as .mp3.
- AAC encoded with FFmpeg's native AAC encoder and stored as .m4a.

The profiles are anchored to Hetren's sealed synthetic multi-number/ID
reference asset and to measurements obtained inside the pinned Phase 3.9
media environment.

Encoder delay and padding are treated as measured codec/container
properties. Decoded sample-count equality with the PCM parent is therefore
not required.

This contract defines methodology and frozen reference observations only.
It does not by itself establish production qualification, issue
certification, or modify release authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_evidence import (
    ASRAdversarialCodec,
)


ASR_ADVERSARIAL_LOSSY_CODEC_METHODOLOGY_SCHEMA_VERSION = 1

ASR_ADVERSARIAL_LOSSY_CODEC_METHODOLOGY_KEY = (
    "hetren.asr.adversarial-lossy-codec-methodology.en-us"
)

ASR_ADVERSARIAL_LOSSY_CODEC_METHODOLOGY_VERSION = "1.0.0"


ASR_ADVERSARIAL_LOSSY_CODEC_V1_SAMPLE_RATE_HZ = 16_000

ASR_ADVERSARIAL_LOSSY_CODEC_V1_CHANNEL_COUNT = 1

ASR_ADVERSARIAL_LOSSY_CODEC_V1_BITRATE_BPS = 32_000

ASR_ADVERSARIAL_LOSSY_CODEC_V1_PARENT_SAMPLE_COUNT = 110_241

ASR_ADVERSARIAL_LOSSY_CODEC_V1_REPRODUCIBILITY_RUNS = 3

ASR_ADVERSARIAL_LOSSY_CODEC_V1_PARENT_AUDIO_SHA256 = (
    "23f9af39d01afe47e932bd061467bd0b"
    "5f49dc8bf520c2a8296a4556c54f1297"
)

ASR_ADVERSARIAL_LOSSY_CODEC_V1_FFMPEG_PACKAGE_VERSION = (
    "7:5.1.9-0+deb12u1"
)


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


def _require_non_empty_text(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise HveeContractError(
            f"{name} must be non-empty canonical text"
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


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _require_extension(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) < 2
        or not value.startswith(".")
        or value != value.lower()
        or any(
            character not in (
                ".abcdefghijklmnopqrstuvwxyz0123456789"
            )
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase extension"
        )

    return value


def _require_controls(
    *,
    name: str,
    controls: object,
) -> tuple[
    tuple[str, str | int | bool],
    ...,
]:
    if (
        not isinstance(controls, tuple)
        or not controls
    ):
        raise HveeContractError(
            f"{name} must contain explicit controls"
        )

    names: list[str] = []

    for control in controls:
        if (
            not isinstance(control, tuple)
            or len(control) != 2
        ):
            raise HveeContractError(
                f"{name} contains an invalid control"
            )

        control_name = _require_identifier(
            name=f"{name} control name",
            value=control[0],
        )

        control_value = control[1]

        if (
            isinstance(control_value, str)
            and (
                not control_value
                or control_value
                != control_value.strip()
            )
        ):
            raise HveeContractError(
                f"{name} contains an invalid control value"
            )

        if not isinstance(
            control_value,
            (str, int, bool),
        ):
            raise HveeContractError(
                f"{name} contains an invalid control value"
            )

        names.append(
            control_name
        )

    if len(names) != len(
        set(names)
    ):
        raise HveeContractError(
            f"{name} control names must be unique"
        )

    return controls


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
            "lossy codec methodology must be deterministic JSON"
        ) from exc


def calculate_asr_adversarial_lossy_codec_methodology_sha256(
    payload: object,
) -> str:
    """Hash canonical lossy-codec methodology evidence."""

    return hashlib.sha256(
        _canonical_json(
            payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialLossyCodecLibraryPin:
    """One dynamically linked library identity."""

    package_name: str
    package_version: str
    soname: str
    sha256: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="lossy codec package name",
            value=self.package_name,
        )

        _require_non_empty_text(
            name="lossy codec package version",
            value=self.package_version,
        )

        _require_non_empty_text(
            name="lossy codec library soname",
            value=self.soname,
        )

        _require_sha256(
            name="lossy codec library",
            value=self.sha256,
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialLossyCodecProfile:
    """One deterministic product-representative lossy profile."""

    profile_key: str
    codec_name: str
    container_key: str
    output_extension: str
    encoder_key: str
    bitrate_bps: int
    sample_rate_hz: int
    channel_count: int
    encoder_controls: tuple[
        tuple[str, str | int | bool],
        ...,
    ]
    muxer_controls: tuple[
        tuple[str, str | int | bool],
        ...,
    ]
    product_ingestion_supported: bool
    reference_encoded_sha256: str
    reference_encoded_byte_length: int
    reference_decoded_sha256: str
    reference_decoded_sample_count: int
    reference_decoded_sample_delta: int
    reference_probe_duration_ms: int

    def __post_init__(self) -> None:
        _require_identifier(
            name="lossy codec profile key",
            value=self.profile_key,
        )

        _require_identifier(
            name="lossy codec name",
            value=self.codec_name,
        )

        _require_identifier(
            name="lossy codec container",
            value=self.container_key,
        )

        _require_extension(
            name="lossy codec output extension",
            value=self.output_extension,
        )

        _require_identifier(
            name="lossy codec encoder",
            value=self.encoder_key,
        )

        _require_positive_integer(
            name="lossy codec bitrate",
            value=self.bitrate_bps,
        )

        _require_positive_integer(
            name="lossy codec sample rate",
            value=self.sample_rate_hz,
        )

        _require_positive_integer(
            name="lossy codec channel count",
            value=self.channel_count,
        )

        _require_controls(
            name="lossy codec encoder controls",
            controls=self.encoder_controls,
        )

        _require_controls(
            name="lossy codec muxer controls",
            controls=self.muxer_controls,
        )

        if (
            not isinstance(
                self.product_ingestion_supported,
                bool,
            )
            or self.product_ingestion_supported
            is not True
        ):
            raise HveeContractError(
                "lossy codec v1 profile must be product-ingestable"
            )

        _require_sha256(
            name="lossy codec encoded reference",
            value=self.reference_encoded_sha256,
        )

        _require_positive_integer(
            name="lossy codec encoded byte length",
            value=self.reference_encoded_byte_length,
        )

        _require_sha256(
            name="lossy codec decoded reference",
            value=self.reference_decoded_sha256,
        )

        _require_positive_integer(
            name="lossy codec decoded sample count",
            value=self.reference_decoded_sample_count,
        )

        _require_positive_integer(
            name="lossy codec decoded sample delta",
            value=self.reference_decoded_sample_delta,
        )

        _require_positive_integer(
            name="lossy codec probe duration",
            value=self.reference_probe_duration_ms,
        )

        observed_delta = (
            self.reference_decoded_sample_count
            - ASR_ADVERSARIAL_LOSSY_CODEC_V1_PARENT_SAMPLE_COUNT
        )

        if (
            observed_delta
            != self.reference_decoded_sample_delta
        ):
            raise HveeContractError(
                "lossy codec decoded sample delta is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialLossyCodecMethodology:
    """Pinned lossy-codec qualification methodology."""

    parent_audio_sha256: str
    parent_sample_count: int
    sample_rate_hz: int
    channel_count: int
    ffmpeg_package_version: str
    reproducibility_run_count: int
    encoded_byte_identity_required: bool
    decoded_byte_identity_required: bool
    metadata_policy_key: str
    thread_count: int
    duration_policy_key: str
    library_pins: tuple[
        ASRAdversarialLossyCodecLibraryPin,
        ...,
    ]
    profiles: tuple[
        ASRAdversarialLossyCodecProfile,
        ...,
    ]

    def __post_init__(self) -> None:
        _require_sha256(
            name="lossy codec parent audio",
            value=self.parent_audio_sha256,
        )

        _require_positive_integer(
            name="lossy codec parent sample count",
            value=self.parent_sample_count,
        )

        _require_positive_integer(
            name="lossy codec sample rate",
            value=self.sample_rate_hz,
        )

        _require_positive_integer(
            name="lossy codec channel count",
            value=self.channel_count,
        )

        _require_non_empty_text(
            name="lossy codec FFmpeg package version",
            value=self.ffmpeg_package_version,
        )

        _require_positive_integer(
            name="lossy codec reproducibility run count",
            value=self.reproducibility_run_count,
        )

        if self.reproducibility_run_count < 2:
            raise HveeContractError(
                "lossy codec reproducibility requires multiple runs"
            )

        if (
            self.encoded_byte_identity_required
            is not True
            or self.decoded_byte_identity_required
            is not True
        ):
            raise HveeContractError(
                "lossy codec reproducibility must require byte identity"
            )

        _require_identifier(
            name="lossy codec metadata policy",
            value=self.metadata_policy_key,
        )

        _require_positive_integer(
            name="lossy codec thread count",
            value=self.thread_count,
        )

        _require_identifier(
            name="lossy codec duration policy",
            value=self.duration_policy_key,
        )

        if (
            not isinstance(
                self.library_pins,
                tuple,
            )
            or not self.library_pins
            or not all(
                isinstance(
                    pin,
                    ASRAdversarialLossyCodecLibraryPin,
                )
                for pin in self.library_pins
            )
        ):
            raise HveeContractError(
                "lossy codec methodology requires library pins"
            )

        package_names = tuple(
            pin.package_name
            for pin in self.library_pins
        )

        if package_names != tuple(
            sorted(
                package_names
            )
        ):
            raise HveeContractError(
                "lossy codec library pins must be ordered"
            )

        if len(package_names) != len(
            set(
                package_names
            )
        ):
            raise HveeContractError(
                "lossy codec library pins must be unique"
            )

        if (
            not isinstance(
                self.profiles,
                tuple,
            )
            or not self.profiles
            or not all(
                isinstance(
                    profile,
                    ASRAdversarialLossyCodecProfile,
                )
                for profile in self.profiles
            )
        ):
            raise HveeContractError(
                "lossy codec methodology requires profiles"
            )

        profile_keys = tuple(
            profile.profile_key
            for profile in self.profiles
        )

        if profile_keys != tuple(
            sorted(
                profile_keys
            )
        ):
            raise HveeContractError(
                "lossy codec profiles must be ordered"
            )

        if len(profile_keys) != len(
            set(
                profile_keys
            )
        ):
            raise HveeContractError(
                "lossy codec profiles must be unique"
            )

        for profile in self.profiles:
            if (
                profile.sample_rate_hz
                != self.sample_rate_hz
                or profile.channel_count
                != self.channel_count
            ):
                raise HveeContractError(
                    "lossy codec profile media shape is inconsistent"
                )


@dataclass(frozen=True, slots=True)
class ASRAdversarialLossyCodecMethodologyBundle:
    """Canonical lossy-codec methodology payload and digest."""

    payload: dict[str, object]
    sha256: str


def _controls_payload(
    controls: tuple[
        tuple[str, str | int | bool],
        ...,
    ],
) -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "value": value,
        }
        for name, value in controls
    ]


def build_asr_adversarial_lossy_codec_methodology_v1(
) -> ASRAdversarialLossyCodecMethodologyBundle:
    """Build Hetren's exact deterministic lossy-codec methodology v1."""

    methodology = ASRAdversarialLossyCodecMethodology(
        parent_audio_sha256=(
            ASR_ADVERSARIAL_LOSSY_CODEC_V1_PARENT_AUDIO_SHA256
        ),
        parent_sample_count=(
            ASR_ADVERSARIAL_LOSSY_CODEC_V1_PARENT_SAMPLE_COUNT
        ),
        sample_rate_hz=(
            ASR_ADVERSARIAL_LOSSY_CODEC_V1_SAMPLE_RATE_HZ
        ),
        channel_count=(
            ASR_ADVERSARIAL_LOSSY_CODEC_V1_CHANNEL_COUNT
        ),
        ffmpeg_package_version=(
            ASR_ADVERSARIAL_LOSSY_CODEC_V1_FFMPEG_PACKAGE_VERSION
        ),
        reproducibility_run_count=(
            ASR_ADVERSARIAL_LOSSY_CODEC_V1_REPRODUCIBILITY_RUNS
        ),
        encoded_byte_identity_required=True,
        decoded_byte_identity_required=True,
        metadata_policy_key="strip-input-metadata-v1",
        thread_count=1,
        duration_policy_key=(
            "container-duration-and-decoded-sample-count-bound-v1"
        ),
        library_pins=(
            ASRAdversarialLossyCodecLibraryPin(
                package_name="libavcodec59",
                package_version="7:5.1.9-0+deb12u1",
                soname="libavcodec.so.59",
                sha256=(
                    "4af5d9cffe2721f5c2cabf35d63c5c6a"
                    "039b400df5721aaedf69995e37bd2a0d"
                ),
            ),
            ASRAdversarialLossyCodecLibraryPin(
                package_name="libavformat59",
                package_version="7:5.1.9-0+deb12u1",
                soname="libavformat.so.59",
                sha256=(
                    "28aadd0a03e3e83d3aa6d4797b6a8569"
                    "c15e09a5f49e6d71ff4866180871de8d"
                ),
            ),
            ASRAdversarialLossyCodecLibraryPin(
                package_name="libavutil57",
                package_version="7:5.1.9-0+deb12u1",
                soname="libavutil.so.57",
                sha256=(
                    "c46ee8987cacb9f9af711f676cc98bb6d"
                    "465a340566dad9c678d21baa26e2c9d"
                ),
            ),
            ASRAdversarialLossyCodecLibraryPin(
                package_name="libmp3lame0",
                package_version="3.100-6",
                soname="libmp3lame.so.0",
                sha256=(
                    "33aec7029d42a903d0a127c549021c4e8"
                    "86273d29e97422b6f5b7fc6d49b8d1b"
                ),
            ),
            ASRAdversarialLossyCodecLibraryPin(
                package_name="libswresample4",
                package_version="7:5.1.9-0+deb12u1",
                soname="libswresample.so.4",
                sha256=(
                    "8858da6d309d6f62d89bc78a541112b1b"
                    "d62ad0ae714ecc54aa61c14219e73b4"
                ),
            ),
        ),
        profiles=(
            ASRAdversarialLossyCodecProfile(
                profile_key="aac-m4a-cbr32",
                codec_name="aac",
                container_key="ipod",
                output_extension=".m4a",
                encoder_key="aac",
                bitrate_bps=32_000,
                sample_rate_hz=16_000,
                channel_count=1,
                encoder_controls=(
                    ("aac_coder", "twoloop"),
                    ("aac_ms", False),
                    ("aac_is", True),
                    ("aac_pns", True),
                    ("aac_tns", True),
                    ("aac_ltp", False),
                    ("aac_pred", False),
                    ("aac_pce", False),
                ),
                muxer_controls=(
                    ("movflags", "+faststart"),
                    ("use_editlist", True),
                    ("write_btrt", False),
                    ("write_prft", False),
                    ("movie_timescale", 1_000),
                ),
                product_ingestion_supported=True,
                reference_encoded_sha256=(
                    "1f303beee42f35d86f920487fbbb67e8"
                    "70576f7278a1d3b6bd97a7bd6e67fb09"
                ),
                reference_encoded_byte_length=28_701,
                reference_decoded_sha256=(
                    "0ff95374a2f6c66b85aa77371df5baf8"
                    "e935a33b2935896c538dcf4fb431eb1e"
                ),
                reference_decoded_sample_count=110_592,
                reference_decoded_sample_delta=351,
                reference_probe_duration_ms=6_891,
            ),
            ASRAdversarialLossyCodecProfile(
                profile_key="mp3-cbr32",
                codec_name="mp3",
                container_key="mp3",
                output_extension=".mp3",
                encoder_key="libmp3lame",
                bitrate_bps=32_000,
                sample_rate_hz=16_000,
                channel_count=1,
                encoder_controls=(
                    ("abr", False),
                    ("reservoir", True),
                    ("joint_stereo", False),
                ),
                muxer_controls=(
                    ("id3v2_version", 3),
                    ("write_id3v1", False),
                    ("write_xing", False),
                ),
                product_ingestion_supported=True,
                reference_encoded_sha256=(
                    "938fc367f744dee780d57c8b7e64f9dd"
                    "781fe1e8599abbe4bb0987b8f844d2f3"
                ),
                reference_encoded_byte_length=27_981,
                reference_decoded_sha256=(
                    "f6b6bd6ecc25d752dbca6bbc1fff6de8"
                    "fa68bdc970c21b78a7a876599f3da222"
                ),
                reference_decoded_sample_count=111_744,
                reference_decoded_sample_delta=1_503,
                reference_probe_duration_ms=6_984,
            ),
        ),
    )

    payload: dict[str, object] = {
        "artifact": {
            "schema_version": (
                ASR_ADVERSARIAL_LOSSY_CODEC_METHODOLOGY_SCHEMA_VERSION
            ),
            "key": (
                ASR_ADVERSARIAL_LOSSY_CODEC_METHODOLOGY_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_LOSSY_CODEC_METHODOLOGY_VERSION
            ),
            "type": (
                "adversarial_lossy_codec_methodology"
            ),
        },
        "methodology": {
            "semantic_family": (
                ASRAdversarialCodec
                .LOSSY_COMPRESSED
                .value
            ),
            "reference_parent": {
                "audio_sha256": (
                    methodology.parent_audio_sha256
                ),
                "sample_count": (
                    methodology.parent_sample_count
                ),
                "sample_rate_hz": (
                    methodology.sample_rate_hz
                ),
                "channel_count": (
                    methodology.channel_count
                ),
            },
            "reproducibility": {
                "independent_container_runs": (
                    methodology.reproducibility_run_count
                ),
                "encoded_byte_identity_required": (
                    methodology.encoded_byte_identity_required
                ),
                "decoded_byte_identity_required": (
                    methodology.decoded_byte_identity_required
                ),
                "metadata_policy_key": (
                    methodology.metadata_policy_key
                ),
                "thread_count": (
                    methodology.thread_count
                ),
                "duration_policy_key": (
                    methodology.duration_policy_key
                ),
                "decoded_sample_count_must_equal_parent": False,
            },
            "toolchain": {
                "ffmpeg_package_version": (
                    methodology.ffmpeg_package_version
                ),
                "libraries": [
                    {
                        "package_name": pin.package_name,
                        "package_version": (
                            pin.package_version
                        ),
                        "soname": pin.soname,
                        "sha256": pin.sha256,
                    }
                    for pin in methodology.library_pins
                ],
            },
            "profiles": [
                {
                    "profile_key": profile.profile_key,
                    "declared_codec_family": (
                        ASRAdversarialCodec
                        .LOSSY_COMPRESSED
                        .value
                    ),
                    "codec_name": profile.codec_name,
                    "container_key": (
                        profile.container_key
                    ),
                    "output_extension": (
                        profile.output_extension
                    ),
                    "encoder_key": (
                        profile.encoder_key
                    ),
                    "bitrate_bps": (
                        profile.bitrate_bps
                    ),
                    "sample_rate_hz": (
                        profile.sample_rate_hz
                    ),
                    "channel_count": (
                        profile.channel_count
                    ),
                    "encoder_controls": (
                        _controls_payload(
                            profile.encoder_controls
                        )
                    ),
                    "muxer_controls": (
                        _controls_payload(
                            profile.muxer_controls
                        )
                    ),
                    "product_ingestion_supported": (
                        profile.product_ingestion_supported
                    ),
                    "reference_observation": {
                        "encoded_sha256": (
                            profile.reference_encoded_sha256
                        ),
                        "encoded_byte_length": (
                            profile.reference_encoded_byte_length
                        ),
                        "decoded_sha256": (
                            profile.reference_decoded_sha256
                        ),
                        "decoded_sample_count": (
                            profile.reference_decoded_sample_count
                        ),
                        "decoded_sample_delta": (
                            profile.reference_decoded_sample_delta
                        ),
                        "probe_duration_ms": (
                            profile.reference_probe_duration_ms
                        ),
                    },
                }
                for profile in methodology.profiles
            ],
        },
        "scientific_boundary": {
            "current_product_ingestion_extensions_only": True,
            "adts_aac_qualification_claimed": False,
            "opus_qualification_claimed": False,
            "lossy_codec_quality_standard_claimed": False,
            "encoder_delay_padding_treated_as_failure": False,
            "cross_platform_reproducibility_established": False,
            "development_evidence_only": True,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
        },
    }

    return ASRAdversarialLossyCodecMethodologyBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_lossy_codec_methodology_sha256(
                payload
            )
        ),
    )


def verify_asr_adversarial_lossy_codec_methodology_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> ASRAdversarialLossyCodecMethodologyBundle:
    """Verify exact canonical Hetren lossy-codec methodology v1."""

    _require_sha256(
        name="lossy codec methodology expected SHA-256",
        value=expected_sha256,
    )

    canonical = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    if (
        payload
        != canonical.payload
        or expected_sha256
        != canonical.sha256
    ):
        raise HveeContractError(
            "lossy codec methodology verification failed"
        )

    return canonical


__all__ = [
    "ASR_ADVERSARIAL_LOSSY_CODEC_METHODOLOGY_KEY",
    "ASR_ADVERSARIAL_LOSSY_CODEC_METHODOLOGY_SCHEMA_VERSION",
    "ASR_ADVERSARIAL_LOSSY_CODEC_METHODOLOGY_VERSION",
    "ASR_ADVERSARIAL_LOSSY_CODEC_V1_BITRATE_BPS",
    "ASR_ADVERSARIAL_LOSSY_CODEC_V1_CHANNEL_COUNT",
    "ASR_ADVERSARIAL_LOSSY_CODEC_V1_FFMPEG_PACKAGE_VERSION",
    "ASR_ADVERSARIAL_LOSSY_CODEC_V1_PARENT_AUDIO_SHA256",
    "ASR_ADVERSARIAL_LOSSY_CODEC_V1_PARENT_SAMPLE_COUNT",
    "ASR_ADVERSARIAL_LOSSY_CODEC_V1_REPRODUCIBILITY_RUNS",
    "ASR_ADVERSARIAL_LOSSY_CODEC_V1_SAMPLE_RATE_HZ",
    "ASRAdversarialLossyCodecLibraryPin",
    "ASRAdversarialLossyCodecMethodology",
    "ASRAdversarialLossyCodecMethodologyBundle",
    "ASRAdversarialLossyCodecProfile",
    "build_asr_adversarial_lossy_codec_methodology_v1",
    "calculate_asr_adversarial_lossy_codec_methodology_sha256",
    "verify_asr_adversarial_lossy_codec_methodology_v1",
]
