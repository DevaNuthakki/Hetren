"""Security tests for parent-manifest-derived adversarial ASR audio."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.adversarial_asr_corpus_derivative_service import (
    ASRAdversarialCorpusDerivativeError,
    generate_asr_adversarial_derived_case_v1,
)
from app.adversarial_asr_corpus_verification_service import (
    ASRAdversarialMeasuredMedia,
)
from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV,
    ASRAdversarialFFmpegTransformResult,
)
from hvee.packs.asr.adversarial_corpus_manifest import (
    ASRAdversarialCorpusAsset,
    ASRAdversarialCorpusManifestDefinition,
    ASRAdversarialCorpusProvenanceType,
    build_asr_adversarial_corpus_manifest_v1,
)
from hvee.packs.asr.adversarial_corpus_records import (
    ASRAdversarialCorpusDerivationPlan,
    ASRAdversarialCorpusDerivationPlanEntry,
    ASRAdversarialCorpusTransformationRecord,
    build_asr_adversarial_corpus_derivation_plan_v1,
    build_asr_adversarial_corpus_transformation_record_v1,
)
from hvee.packs.asr.adversarial_evidence import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCase,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialCondition,
    ASRAdversarialDurationBucket,
    ASRAdversarialLongContextPosition,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSemanticLoad,
    ASRAdversarialSpeakingRate,
    ASRAdversarialSuiteDefinition,
    build_asr_adversarial_evidence_v1,
)


PARENT_CASE_ID = "clean.parent-case"

DERIVED_CASE_ID = (
    "stress.codec-mulaw.parent-case"
)

PARENT_RELATIVE_PATH = (
    "clean/clean.parent-case.wav"
)

OUTPUT_RELATIVE_PATH = (
    "telephony/"
    "stress.codec-mulaw.parent-case.wav"
)

PARENT_BYTES = (
    b"canonical-parent-audio"
)

OUTPUT_BYTES = (
    b"deterministic-mulaw-output"
)


def _sha_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _sha_text(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


PARENT_SHA256 = _sha_bytes(
    PARENT_BYTES
)

PROVENANCE_SHA256 = _sha_text(
    "fixture-provenance"
)

RIGHTS_SHA256 = _sha_text(
    "fixture-rights"
)

PARENT_TRANSFORMATION_SHA256 = _sha_text(
    "fixture-parent-transform"
)

DERIVED_TRANSFORMER_ENVIRONMENT_SHA256 = (
    _sha_text(
        "fixture-mulaw-environment"
    )
)


def _write_bundle(
    path: Path,
    bundle,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            {
                "payload": bundle.payload,
                "sha256": bundle.sha256,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _parent_contract():
    condition = ASRAdversarialCondition(
        channel=ASRAdversarialChannel.CLEAN,
        codec=ASRAdversarialCodec.LINEAR_PCM,
        sample_rate_hz=16_000,
        microphone_class="synthetic.direct",
        noise=ASRAdversarialNoiseCondition.NONE,
        speaking_rate=(
            ASRAdversarialSpeakingRate.NORMAL
        ),
        speech_variety_key="declared.fixture",
        overlap=ASRAdversarialOverlapCondition.NONE,
        duration=ASRAdversarialDurationBucket.SHORT,
    )

    semantic = ASRAdversarialSemanticLoad(
        critical_number_count=1,
        critical_identifier_count=0,
        critical_terminology_count=0,
        spoken_number_variation=False,
        multiple_critical_items=False,
        duplicate_critical_items=False,
        ordering_challenge=False,
        long_context_position=(
            ASRAdversarialLongContextPosition.NONE
        ),
    )

    case = ASRAdversarialCase(
        case_id=PARENT_CASE_ID,
        audio_asset_sha256=PARENT_SHA256,
        reference_transcript="Take five milligrams.",
        condition=condition,
        semantic_load=semantic,
        description=(
            "Derived-case parent manifest fixture."
        ),
        tags=(
            "fixture",
        ),
    )

    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(
            case,
        ),
    )

    suite_evidence = (
        build_asr_adversarial_evidence_v1(
            suite
        )
    )

    definition = (
        ASRAdversarialCorpusManifestDefinition(
            corpus_id="qualification.fixture-parent",
            corpus_version="1.0.0",
            suite_sha256=suite_evidence.sha256,
            assets=(
                ASRAdversarialCorpusAsset(
                    case_id=PARENT_CASE_ID,
                    relative_audio_path=(
                        PARENT_RELATIVE_PATH
                    ),
                    audio_asset_sha256=(
                        PARENT_SHA256
                    ),
                    byte_length=len(
                        PARENT_BYTES
                    ),
                    duration_ms=1_234,
                    sample_rate_hz=16_000,
                    channel_count=1,
                    codec_name="pcm_s16le",
                    provenance_type=(
                        ASRAdversarialCorpusProvenanceType
                        .DETERMINISTIC_DERIVATIVE
                    ),
                    provenance_record_sha256=(
                        PROVENANCE_SHA256
                    ),
                    rights_record_sha256=(
                        RIGHTS_SHA256
                    ),
                    transformation_record_sha256=(
                        PARENT_TRANSFORMATION_SHA256
                    ),
                ),
            ),
        )
    )

    manifest = (
        build_asr_adversarial_corpus_manifest_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    return (
        suite,
        suite_evidence,
        definition,
        manifest,
    )


class FakeDerivedTransformer:
    tool_key = "ffmpeg"
    reported_version = "5.1.9-test"
    transform_environment_sha256 = (
        DERIVED_TRANSFORMER_ENVIRONMENT_SHA256
    )
    recipe_argv = (
        ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV
    )

    def __init__(
        self,
    ) -> None:
        self.calls = 0

    def transform(
        self,
        *,
        input_path: Path,
        output_path: Path,
    ):
        self.calls += 1

        parent = input_path.read_bytes()

        output_path.write_bytes(
            OUTPUT_BYTES
        )

        return (
            ASRAdversarialFFmpegTransformResult(
                parent_audio_sha256=(
                    _sha_bytes(
                        parent
                    )
                ),
                parent_byte_length=len(
                    parent
                ),
                output_audio_sha256=(
                    _sha_bytes(
                        OUTPUT_BYTES
                    )
                ),
                output_byte_length=len(
                    OUTPUT_BYTES
                ),
            )
        )


class FakeProbe:
    probe_key = "fixture.media-probe"
    probe_version = "1.0.0"
    probe_environment_sha256 = (
        _sha_text(
            "fixture-probe-environment"
        )
    )

    def __init__(
        self,
        *,
        sample_rate_hz: int = 8_000,
        channel_count: int = 1,
        codec_name: str = "pcm_mulaw",
    ) -> None:
        self.sample_rate_hz = sample_rate_hz
        self.channel_count = channel_count
        self.codec_name = codec_name

    def probe(
        self,
        audio_path: Path,
    ):
        assert audio_path.is_file()

        return ASRAdversarialMeasuredMedia(
            duration_ms=1_234,
            sample_rate_hz=self.sample_rate_hz,
            channel_count=self.channel_count,
            codec_name=self.codec_name,
        )


def _context(
    tmp_path: Path,
    *,
    plan_parent_manifest_sha256: str | None = None,
    plan_parent_audio_sha256: str | None = None,
    plan_provenance_sha256: str | None = None,
    plan_transformation_sha256: str | None = None,
):
    (
        suite,
        suite_evidence,
        definition,
        manifest,
    ) = _parent_contract()

    corpus = (
        tmp_path
        / "corpus"
    )

    generated = (
        tmp_path
        / "generated"
    )

    generated.mkdir(
        parents=True
    )

    parent_path = (
        generated
        / PARENT_RELATIVE_PATH
    )

    parent_path.parent.mkdir(
        parents=True
    )

    parent_path.write_bytes(
        PARENT_BYTES
    )

    transformation = (
        build_asr_adversarial_corpus_transformation_record_v1(
            ASRAdversarialCorpusTransformationRecord(
                record_id=(
                    "transform.stress-codec-mulaw-parent-case-v1"
                ),
                case_id=DERIVED_CASE_ID,
                parent_audio_sha256=PARENT_SHA256,
                tool_key="ffmpeg",
                tool_version="5.1.9-test",
                tool_environment_sha256=(
                    DERIVED_TRANSFORMER_ENVIRONMENT_SHA256
                ),
                argv=(
                    ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV
                ),
                output_relative_path=(
                    OUTPUT_RELATIVE_PATH
                ),
                expected_sample_rate_hz=8_000,
                expected_channel_count=1,
                expected_codec_name="pcm_mulaw",
            )
        )
    )

    derivation_plan = (
        build_asr_adversarial_corpus_derivation_plan_v1(
            ASRAdversarialCorpusDerivationPlan(
                corpus_id=(
                    "qualification.fixture-stress"
                ),
                corpus_version="1.0.0",
                parent_manifest_sha256=(
                    plan_parent_manifest_sha256
                    or manifest.sha256
                ),
                entries=(
                    ASRAdversarialCorpusDerivationPlanEntry(
                        case_id=DERIVED_CASE_ID,
                        parent_case_id=PARENT_CASE_ID,
                        parent_relative_path=(
                            PARENT_RELATIVE_PATH
                        ),
                        parent_audio_sha256=(
                            plan_parent_audio_sha256
                            or PARENT_SHA256
                        ),
                        output_relative_path=(
                            OUTPUT_RELATIVE_PATH
                        ),
                        provenance_record_sha256=(
                            plan_provenance_sha256
                            or PROVENANCE_SHA256
                        ),
                        rights_record_sha256=(
                            RIGHTS_SHA256
                        ),
                        transformation_record_sha256=(
                            plan_transformation_sha256
                            or transformation.sha256
                        ),
                    ),
                ),
            )
        )
    )

    _write_bundle(
        corpus
        / "specification"
        / "corpus-manifest.json",
        manifest,
    )

    _write_bundle(
        corpus
        / "specification"
        / "derivation-plan.json",
        derivation_plan,
    )

    _write_bundle(
        corpus
        / "records"
        / "transformations"
        / f"{DERIVED_CASE_ID}.json",
        transformation,
    )

    return {
        "corpus": corpus,
        "generated": generated,
        "parent_path": parent_path,
        "suite": suite,
        "suite_evidence": suite_evidence,
        "definition": definition,
        "manifest": manifest,
        "transformation": transformation,
        "derivation_plan": derivation_plan,
    }


def _generate(
    context,
    *,
    transformer=None,
    probe=None,
):
    return (
        generate_asr_adversarial_derived_case_v1(
            corpus_root=context[
                "corpus"
            ],
            generated_root=context[
                "generated"
            ],
            case_id=DERIVED_CASE_ID,
            parent_manifest_definition=context[
                "definition"
            ],
            parent_suite=context[
                "suite"
            ],
            parent_suite_evidence=context[
                "suite_evidence"
            ],
            transformer=(
                transformer
                or FakeDerivedTransformer()
            ),
            probe=(
                probe
                or FakeProbe()
            ),
        )
    )


def test_generates_verified_parent_manifest_derived_case(
    tmp_path: Path,
):
    context = _context(
        tmp_path
    )

    transformer = (
        FakeDerivedTransformer()
    )

    result = _generate(
        context,
        transformer=transformer,
    )

    destination = (
        context[
            "generated"
        ]
        / OUTPUT_RELATIVE_PATH
    )

    assert (
        destination.read_bytes()
        == OUTPUT_BYTES
    )

    assert transformer.calls == 1

    assert result.case_id == DERIVED_CASE_ID
    assert result.parent_case_id == PARENT_CASE_ID

    assert (
        result.parent_relative_path
        == PARENT_RELATIVE_PATH
    )

    assert (
        result.output_relative_path
        == OUTPUT_RELATIVE_PATH
    )

    assert (
        result.parent_audio_sha256
        == PARENT_SHA256
    )

    assert (
        result.audio_asset_sha256
        == _sha_bytes(
            OUTPUT_BYTES
        )
    )

    assert result.sample_rate_hz == 8_000
    assert result.channel_count == 1
    assert result.codec_name == "pcm_mulaw"

    assert (
        result.parent_manifest_sha256
        == context[
            "manifest"
        ].sha256
    )

    assert (
        result.derivation_plan_sha256
        == context[
            "derivation_plan"
        ].sha256
    )

    assert (
        result.transformation_record_sha256
        == context[
            "transformation"
        ].sha256
    )

    assert (
        result.development_evidence_only
        is True
    )


def test_regeneration_is_idempotent(
    tmp_path: Path,
):
    context = _context(
        tmp_path
    )

    transformer = (
        FakeDerivedTransformer()
    )

    first = _generate(
        context,
        transformer=transformer,
    )

    second = _generate(
        context,
        transformer=transformer,
    )

    assert (
        first.audio_asset_sha256
        == second.audio_asset_sha256
    )

    assert (
        first.byte_length
        == second.byte_length
    )

    assert transformer.calls == 2


def test_rejects_tampered_parent_manifest(
    tmp_path: Path,
):
    context = _context(
        tmp_path
    )

    manifest_path = (
        context[
            "corpus"
        ]
        / "specification"
        / "corpus-manifest.json"
    )

    document = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    document[
        "payload"
    ]["corpus"]["assets"][0][
        "byte_length"
    ] += 1

    manifest_path.write_text(
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="parent corpus manifest verification failed",
    ):
        _generate(
            context
        )


def test_rejects_wrong_parent_manifest_binding(
    tmp_path: Path,
):
    context = _context(
        tmp_path,
        plan_parent_manifest_sha256=(
            _sha_text(
                "wrong-parent-manifest"
            )
        ),
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="does not bind the verified parent manifest",
    ):
        _generate(
            context
        )


def test_rejects_parent_audio_binding_mismatch(
    tmp_path: Path,
):
    context = _context(
        tmp_path,
        plan_parent_audio_sha256=(
            _sha_text(
                "wrong-parent-audio"
            )
        ),
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="derivation parent binding",
    ):
        _generate(
            context
        )


def test_rejects_inherited_provenance_mismatch(
    tmp_path: Path,
):
    context = _context(
        tmp_path,
        plan_provenance_sha256=(
            _sha_text(
                "wrong-provenance"
            )
        ),
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="derivation parent binding",
    ):
        _generate(
            context
        )


def test_rejects_transformation_commitment_mismatch(
    tmp_path: Path,
):
    context = _context(
        tmp_path,
        plan_transformation_sha256=(
            _sha_text(
                "wrong-transform"
            )
        ),
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="transformation commitment",
    ):
        _generate(
            context
        )


def test_rejects_runtime_transformer_identity_mismatch(
    tmp_path: Path,
):
    context = _context(
        tmp_path
    )

    transformer = (
        FakeDerivedTransformer()
    )

    transformer.transform_environment_sha256 = (
        _sha_text(
            "different-environment"
        )
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="runtime derived transformer",
    ):
        _generate(
            context,
            transformer=transformer,
        )


def test_rejects_media_metadata_mismatch(
    tmp_path: Path,
):
    context = _context(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="media does not match",
    ):
        _generate(
            context,
            probe=FakeProbe(
                codec_name="pcm_s16le"
            ),
        )


def test_rejects_symlinked_parent_asset(
    tmp_path: Path,
):
    context = _context(
        tmp_path
    )

    external = (
        tmp_path
        / "external.wav"
    )

    external.write_bytes(
        PARENT_BYTES
    )

    parent_path = context[
        "parent_path"
    ]

    parent_path.unlink()

    parent_path.symlink_to(
        external
    )

    with pytest.raises(
        ASRAdversarialCorpusDerivativeError,
        match="cannot contain symlinks",
    ):
        _generate(
            context
        )
