from __future__ import annotations

import copy
import hashlib

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_corpus_records import (
    ASRAdversarialCorpusGenerationPlan,
    ASRAdversarialCorpusGenerationPlanEntry,
    ASRAdversarialCorpusProvenanceRecord,
    ASRAdversarialCorpusRightsRecord,
    ASRAdversarialCorpusTransformationRecord,
    build_asr_adversarial_corpus_generation_plan_v1,
    build_asr_adversarial_corpus_provenance_record_v1,
    build_asr_adversarial_corpus_rights_record_v1,
    build_asr_adversarial_corpus_transformation_record_v1,
    verify_asr_adversarial_corpus_record_v1,
)


def _sha(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _provenance():
    return ASRAdversarialCorpusProvenanceRecord(
        record_id="source.clean-critical-v1",
        case_id="control.clean-critical",
        transcript_sha256=_sha(
            "transcript"
        ),
        generator_key="espeak-ng",
        generator_version="1.51+dfsg-10+deb12u2",
        generator_executable_sha256=_sha(
            "espeak"
        ),
        voice_key="en-us",
        speed_wpm=150,
        pitch=50,
        amplitude=100,
        platform_key="linux-amd64",
    )


def _rights():
    return ASRAdversarialCorpusRightsRecord(
        record_id="rights.clean-critical-v1",
        case_id="control.clean-critical",
        source_package_key="debian.espeak-ng",
        source_package_version="1.51+dfsg-10+deb12u2",
        packaged_copyright_sha256=_sha(
            "copyright"
        ),
        review_status="not_adjudicated",
        development_use_only=True,
    )


def _transformation():
    return ASRAdversarialCorpusTransformationRecord(
        record_id="transform.telephony-mulaw-v1",
        case_id="stress.telephony-mulaw",
        parent_audio_sha256=_sha(
            "parent"
        ),
        tool_key="ffmpeg",
        tool_version="5.1.9-0+deb12u1",
        tool_environment_sha256=_sha(
            "environment"
        ),
        argv=(
            "-ar",
            "8000",
            "-ac",
            "1",
            "-c:a",
            "pcm_mulaw",
        ),
        output_relative_path=(
            "telephony/stress.telephony-mulaw.wav"
        ),
        expected_sample_rate_hz=8_000,
        expected_channel_count=1,
        expected_codec_name="pcm_mulaw",
    )


def test_provenance_record_is_deterministic_and_verifiable():
    first = (
        build_asr_adversarial_corpus_provenance_record_v1(
            _provenance()
        )
    )
    second = (
        build_asr_adversarial_corpus_provenance_record_v1(
            _provenance()
        )
    )

    assert first == second

    assert (
        first.payload["record"]["source_kind"]
        == "synthetic_tts"
    )

    assert (
        verify_asr_adversarial_corpus_record_v1(
            payload=first.payload,
            expected_sha256=first.sha256,
        )
        == first
    )


def test_rights_record_remains_non_adjudicating():
    bundle = (
        build_asr_adversarial_corpus_rights_record_v1(
            _rights()
        )
    )

    assert (
        bundle.payload["record"]["review_status"]
        == "not_adjudicated"
    )
    assert (
        bundle.payload["record"]["development_use_only"]
        is True
    )
    assert (
        bundle.payload["evidence_boundary"][
            "rights_adjudicated"
        ]
        is False
    )


def test_transformation_record_commits_exact_argv():
    bundle = (
        build_asr_adversarial_corpus_transformation_record_v1(
            _transformation()
        )
    )

    assert bundle.payload["record"]["argv"] == [
        "-ar",
        "8000",
        "-ac",
        "1",
        "-c:a",
        "pcm_mulaw",
    ]

    assert (
        bundle.payload["record"][
            "expected_output"
        ]["codec_name"]
        == "pcm_mulaw"
    )


def test_generation_plan_binds_source_records():
    provenance = (
        build_asr_adversarial_corpus_provenance_record_v1(
            _provenance()
        )
    )
    rights = (
        build_asr_adversarial_corpus_rights_record_v1(
            _rights()
        )
    )

    plan = ASRAdversarialCorpusGenerationPlan(
        corpus_id="qualification.synthetic-v1",
        corpus_version="1.0.0",
        entries=(
            ASRAdversarialCorpusGenerationPlanEntry(
                case_id="control.clean-critical",
                output_relative_path=(
                    "clean/control.clean-critical.wav"
                ),
                provenance_record_sha256=(
                    provenance.sha256
                ),
                rights_record_sha256=(
                    rights.sha256
                ),
                transformation_record_sha256=None,
            ),
        ),
    )

    first = (
        build_asr_adversarial_corpus_generation_plan_v1(
            plan
        )
    )
    second = (
        build_asr_adversarial_corpus_generation_plan_v1(
            plan
        )
    )

    assert first == second


def test_generation_plan_requires_sorted_unique_cases():
    provenance = (
        build_asr_adversarial_corpus_provenance_record_v1(
            _provenance()
        )
    )
    rights = (
        build_asr_adversarial_corpus_rights_record_v1(
            _rights()
        )
    )

    with pytest.raises(
        HveeContractError,
        match="ordered by case id",
    ):
        ASRAdversarialCorpusGenerationPlan(
            corpus_id="qualification.synthetic-v1",
            corpus_version="1.0.0",
            entries=(
                ASRAdversarialCorpusGenerationPlanEntry(
                    case_id="stress.z",
                    output_relative_path="clean/z.wav",
                    provenance_record_sha256=(
                        provenance.sha256
                    ),
                    rights_record_sha256=rights.sha256,
                    transformation_record_sha256=None,
                ),
                ASRAdversarialCorpusGenerationPlanEntry(
                    case_id="control.a",
                    output_relative_path="clean/a.wav",
                    provenance_record_sha256=(
                        provenance.sha256
                    ),
                    rights_record_sha256=rights.sha256,
                    transformation_record_sha256=None,
                ),
            ),
        )


def test_derivative_record_requires_valid_parent_digest():
    with pytest.raises(
        HveeContractError,
        match="parent audio",
    ):
        ASRAdversarialCorpusTransformationRecord(
            record_id="transform.bad-v1",
            case_id="stress.bad",
            parent_audio_sha256="bad",
            tool_key="ffmpeg",
            tool_version="5.1.9-0+deb12u1",
            tool_environment_sha256=_sha(
                "environment"
            ),
            argv=("-ar", "8000"),
            output_relative_path="telephony/bad.wav",
            expected_sample_rate_hz=8_000,
            expected_channel_count=1,
            expected_codec_name="pcm_mulaw",
        )


def test_verifier_rejects_authority_escalation():
    bundle = (
        build_asr_adversarial_corpus_provenance_record_v1(
            _provenance()
        )
    )

    mutated = copy.deepcopy(
        bundle.payload
    )
    mutated["evidence_boundary"][
        "production_qualified"
    ] = True

    with pytest.raises(
        HveeContractError,
        match="verification failed|evidence boundary",
    ):
        verify_asr_adversarial_corpus_record_v1(
            payload=mutated,
            expected_sha256=bundle.sha256,
        )


def test_verifier_rejects_rehashed_unknown_artifact_key():
    bundle = (
        build_asr_adversarial_corpus_provenance_record_v1(
            _provenance()
        )
    )

    mutated = copy.deepcopy(
        bundle.payload
    )

    mutated["artifact"]["key"] = (
        "hetren.asr.unsupported-record.en-us"
    )

    from hvee.packs.asr.adversarial_corpus_records import (
        calculate_asr_adversarial_corpus_record_sha256,
    )

    mutated_sha = (
        calculate_asr_adversarial_corpus_record_sha256(
            mutated
        )
    )

    with pytest.raises(
        HveeContractError,
        match="artifact key is unsupported",
    ):
        verify_asr_adversarial_corpus_record_v1(
            payload=mutated,
            expected_sha256=mutated_sha,
        )


def test_verifier_rejects_rehashed_nested_schema_extension():
    bundle = (
        build_asr_adversarial_corpus_provenance_record_v1(
            _provenance()
        )
    )

    mutated = copy.deepcopy(
        bundle.payload
    )

    mutated["record"]["generator"][
        "uncommitted_behavior"
    ] = "unsafe"

    from hvee.packs.asr.adversarial_corpus_records import (
        calculate_asr_adversarial_corpus_record_sha256,
    )

    mutated_sha = (
        calculate_asr_adversarial_corpus_record_sha256(
            mutated
        )
    )

    with pytest.raises(
        HveeContractError,
        match="generator has an invalid schema",
    ):
        verify_asr_adversarial_corpus_record_v1(
            payload=mutated,
            expected_sha256=mutated_sha,
        )


def test_verifier_rejects_rehashed_authority_escalation():
    bundle = (
        build_asr_adversarial_corpus_rights_record_v1(
            _rights()
        )
    )

    mutated = copy.deepcopy(
        bundle.payload
    )

    mutated["evidence_boundary"][
        "production_qualified"
    ] = True

    from hvee.packs.asr.adversarial_corpus_records import (
        calculate_asr_adversarial_corpus_record_sha256,
    )

    mutated_sha = (
        calculate_asr_adversarial_corpus_record_sha256(
            mutated
        )
    )

    with pytest.raises(
        HveeContractError,
        match="evidence boundary is invalid",
    ):
        verify_asr_adversarial_corpus_record_v1(
            payload=mutated,
            expected_sha256=mutated_sha,
        )
