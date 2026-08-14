"""Canonical integrity contract for the I2 eight-case ASR corpus."""

from __future__ import annotations

from pathlib import Path

from hvee.packs.asr.adversarial_corpus_manifest import (
    ASRAdversarialCorpusProvenanceType,
)
from hvee.packs.asr.adversarial_corpus_v1 import (
    ASR_ADVERSARIAL_CORPUS_V1_CASE_IDS,
    build_asr_adversarial_corpus_v1,
)
from hvee.packs.asr.adversarial_evidence import (
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialDurationBucket,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSpeakingRate,
)


ROOT = Path(
    "corpora/asr/adversarial/v1"
)


EXPECTED = {
    "clean.identifier-account-order": {
        "transcript": (
            "Account id C81 and order id D52."
        ),
        "audio_sha256": (
            "30ea53e9418e448b5ad826abe091e2c0"
            "0895c308781ce13b0e6da4b667e1bad7"
        ),
        "byte_length": 128_566,
        "duration_ms": 4_015,
        "provenance": (
            "36bf894c8d87bbc77f87952a205edaa3"
            "bdd1ef7f22a4b75d4dce676a8cdf76bf"
        ),
        "rights": (
            "0efb0b85af7394612abab52185fc43811"
            "ecd5f362a7976f696e01ed39952845c"
        ),
        "transformation": (
            "73a5476351d16890a6c13d67f61baaed"
            "4721978935b8123c640cde8cd025cf45"
        ),
        "numbers": 0,
        "identifiers": 2,
        "terminology": 0,
    },
    "clean.identifier-confirmation": {
        "transcript": (
            "Confirmation code AB7K92."
        ),
        "audio_sha256": (
            "ebfba31f5c69634d577718bfb9cec6a5"
            "51c1e2afaab2cb8f9b19b5e7536efc33"
        ),
        "byte_length": 109_212,
        "duration_ms": 3_410,
        "provenance": (
            "a11556ba44a0381a0e3e6035166b1263"
            "f62d9a6a5ae815fe5151e2a21f9efd02"
        ),
        "rights": (
            "ac9ded0f23b45f96d0f1842cf3d85e34"
            "3d275faba8a1b298c4bae84d6b1eff5b"
        ),
        "transformation": (
            "a19bc2dac6c67eaae14813cd6842ff01"
            "3a37ae2fdb114bb2c40a5aa646387139"
        ),
        "numbers": 0,
        "identifiers": 1,
        "terminology": 0,
    },
    "clean.identifier-multiple": {
        "transcript": (
            "Ticket id A12 then booking reference B34."
        ),
        "audio_sha256": (
            "5624e44f1b4ab3c8bb043aeb809a09c3"
            "3c798ce92d2f6f1ca903bcfdd0c3fdf2"
        ),
        "byte_length": 129_274,
        "duration_ms": 4_037,
        "provenance": (
            "d0de5c0b7de55db1b940f4fbac6f5018"
            "d2edc80f14e1003b58ca968c1ba6fdfd"
        ),
        "rights": (
            "8448ae71a3b9a4c157d9301451a4f86f"
            "f8b32a627829b94aa9a7305ac04bd9b6"
        ),
        "transformation": (
            "29cbce81a09fc05fad49931b77f5c9c3"
            "5ed4d5552d3cae843d99e3562c81dfd1"
        ),
        "numbers": 0,
        "identifiers": 2,
        "terminology": 0,
    },
    "clean.multi-number-id": {
        "transcript": (
            "Administer five milligrams at nine fifteen AM. "
            "Confirmation code AB7K92."
        ),
        "audio_sha256": (
            "23f9af39d01afe47e932bd061467bd0b"
            "5f49dc8bf520c2a8296a4556c54f1297"
        ),
        "byte_length": 220_560,
        "duration_ms": 6_890,
        "provenance": (
            "f804bf7391cc39286bc54d5727ebe01f"
            "61d3a460f169a1b9b4d9d43a903113b4"
        ),
        "rights": (
            "0b38e02c548a775ed4db61603fdcc6814"
            "8840d3396feaef59ac8d51c6b3c6ae7"
        ),
        "transformation": (
            "672cf776feddf77a79182103541b2b108"
            "80b8eeae0852c07c3ffdd73701b0044"
        ),
        "numbers": 2,
        "identifiers": 1,
        "terminology": 0,
    },
    "clean.number-currency-time": {
        "transcript": (
            "Pay 1200 US dollars at nine fifteen AM."
        ),
        "audio_sha256": (
            "236cbdcf2d6ca24fa6726eefff1cf075"
            "2bcb87c5db78765a483031deef290446"
        ),
        "byte_length": 140_890,
        "duration_ms": 4_400,
        "provenance": (
            "ae8dac7e2893bbe643950b1b6ec64261"
            "1a2bf5c38406c77e6bc9dcff7e44ba8a"
        ),
        "rights": (
            "f3b89d00b8c9be37055514fa6a429259"
            "2768bd797ccde8e9fb8776acfaaf10be"
        ),
        "transformation": (
            "c3ed7e3cee110ed91446506355e232fb"
            "7cb05bf03dd0c9cbf2cbe65ad0711b9e"
        ),
        "numbers": 2,
        "identifiers": 0,
        "terminology": 0,
    },
    "clean.number-measurement": {
        "transcript": (
            "Administer five milligrams now."
        ),
        "audio_sha256": (
            "a3045d975c99903e108281951cba856c"
            "695ca0cc96f8d77dcb3279dc1a24fd36"
        ),
        "byte_length": 78_422,
        "duration_ms": 2_448,
        "provenance": (
            "84474e713f6889d12c2baeb7fc08efe0"
            "cc7b17ef43ee33fb6facf23ab20bccef"
        ),
        "rights": (
            "aeb089aa364b4d2c0fec5731b74cda61"
            "b484c6433db68553e79c55665f07d5ec"
        ),
        "transformation": (
            "f9f87b23361bdb4b53aef1d28321b9db"
            "efbb26b846fc42fca7a8f81df84223bd"
        ),
        "numbers": 1,
        "identifiers": 0,
        "terminology": 0,
    },
    "clean.number-percentage": {
        "transcript": (
            "Apply a twenty percent discount today."
        ),
        "audio_sha256": (
            "6843b1466a34d03c5c8920d8fd7fa2f0"
            "4c1b59bffedd80371a8e44492d9edc17"
        ),
        "byte_length": 96_972,
        "duration_ms": 3_028,
        "provenance": (
            "a5ee833742b53fb0a79bfb2b039ff032"
            "55053538ed5895e699ab9aed25f06105"
        ),
        "rights": (
            "067555dd4af75f64c65343edc37614ca"
            "7fdf58d124fc379bf081ac9b8564c41b"
        ),
        "transformation": (
            "23ea98f530e1a258b230a508b45efaecc"
            "ce905843026e0ff4bfeb3a7d8220eac"
        ),
        "numbers": 1,
        "identifiers": 0,
        "terminology": 0,
    },
    "control.clean-critical": {
        "transcript": (
            "Administer Cardiovex 250 milligrams. "
            "Confirmation code AB-7391. "
            "Account number 408-221."
        ),
        "audio_sha256": (
            "f97e1d36b87676aaacf4dbd8059fa8fe"
            "f2d323d23cfb8468aa22426f05dbd3b3"
        ),
        "byte_length": 403_394,
        "duration_ms": 12_604,
        "provenance": (
            "30d7a75e8ad8dca1f03a3576d167a12b"
            "62bff7df2fbd5bfe7a2e825771dde1c4"
        ),
        "rights": (
            "cfcc0861946a6fe96da954f6efda69e7"
            "45e7bd2533e1f9b8718e0084d7bcdb14"
        ),
        "transformation": (
            "4cd349d56ca7c5fc60c773024dc36488"
            "b75f3944a4b1a98da260178c726c3f0f"
        ),
        "numbers": 1,
        "identifiers": 1,
        "terminology": 1,
    },
}


def test_i2_canonical_inventory_is_exact():
    (
        suite,
        _suite_evidence,
        definition,
        _manifest,
    ) = build_asr_adversarial_corpus_v1()

    expected_case_ids = tuple(
        EXPECTED
    )

    assert (
        expected_case_ids
        == ASR_ADVERSARIAL_CORPUS_V1_CASE_IDS
    )

    assert tuple(
        case.case_id
        for case in suite.cases
    ) == expected_case_ids

    assert tuple(
        asset.case_id
        for asset in definition.assets
    ) == expected_case_ids


def test_i2_canonical_transcripts_and_semantics_are_exact():
    (
        suite,
        _suite_evidence,
        _definition,
        _manifest,
    ) = build_asr_adversarial_corpus_v1()

    for case in suite.cases:
        expected = EXPECTED[
            case.case_id
        ]

        transcript_file = (
            ROOT
            / "specification/transcripts"
            / f"{case.case_id}.txt"
        )

        assert (
            transcript_file.read_text(
                encoding="utf-8"
            ).strip()
            == expected["transcript"]
        )

        assert (
            case.reference_transcript
            == expected["transcript"]
        )

        assert (
            case.audio_asset_sha256
            == expected["audio_sha256"]
        )

        semantic = case.semantic_load

        assert (
            semantic.critical_number_count
            == expected["numbers"]
        )
        assert (
            semantic.critical_identifier_count
            == expected["identifiers"]
        )
        assert (
            semantic.critical_terminology_count
            == expected["terminology"]
        )

        total = (
            expected["numbers"]
            + expected["identifiers"]
            + expected["terminology"]
        )

        assert semantic.total_critical_items == total
        assert (
            semantic.multiple_critical_items
            is (total > 1)
        )
        assert semantic.spoken_number_variation is False
        assert semantic.duplicate_critical_items is False
        assert semantic.ordering_challenge is False
        assert semantic.control_case is False


def test_i2_canonical_conditions_remain_clean_baseline():
    (
        suite,
        _suite_evidence,
        _definition,
        _manifest,
    ) = build_asr_adversarial_corpus_v1()

    for case in suite.cases:
        condition = case.condition

        assert (
            condition.channel
            == ASRAdversarialChannel.CLEAN
        )
        assert (
            condition.codec
            == ASRAdversarialCodec.LINEAR_PCM
        )
        assert condition.sample_rate_hz == 16_000
        assert (
            condition.microphone_class
            == "synthetic.direct"
        )
        assert (
            condition.noise
            == ASRAdversarialNoiseCondition.NONE
        )
        assert (
            condition.speaking_rate
            == ASRAdversarialSpeakingRate.NORMAL
        )
        assert (
            condition.speech_variety_key
            == "synthetic.espeak-ng.en-us"
        )
        assert (
            condition.overlap
            == ASRAdversarialOverlapCondition.NONE
        )
        assert (
            condition.duration
            == ASRAdversarialDurationBucket.SHORT
        )
        assert condition.active_stress_count == 0


def test_i2_manifest_exactly_binds_real_derivative_identities():
    (
        _suite,
        suite_evidence,
        definition,
        manifest,
    ) = build_asr_adversarial_corpus_v1()

    assert (
        definition.suite_sha256
        == suite_evidence.sha256
    )

    assert len(
        definition.assets
    ) == 8

    for asset in definition.assets:
        expected = EXPECTED[
            asset.case_id
        ]

        assert (
            asset.relative_audio_path
            == f"clean/{asset.case_id}.wav"
        )
        assert (
            asset.audio_asset_sha256
            == expected["audio_sha256"]
        )
        assert (
            asset.byte_length
            == expected["byte_length"]
        )
        assert (
            asset.duration_ms
            == expected["duration_ms"]
        )
        assert asset.sample_rate_hz == 16_000
        assert asset.channel_count == 1
        assert asset.codec_name == "pcm_s16le"

        assert (
            asset.provenance_type
            == (
                ASRAdversarialCorpusProvenanceType
                .DETERMINISTIC_DERIVATIVE
            )
        )
        assert (
            asset.provenance_record_sha256
            == expected["provenance"]
        )
        assert (
            asset.rights_record_sha256
            == expected["rights"]
        )
        assert (
            asset.transformation_record_sha256
            == expected["transformation"]
        )

    assert (
        manifest.payload[
            "corpus"
        ]["asset_count"]
        == 8
    )


def test_i2_coverage_is_exact_and_non_stress():
    (
        _suite,
        suite_evidence,
        _definition,
        _manifest,
    ) = build_asr_adversarial_corpus_v1()

    coverage = suite_evidence.payload[
        "coverage"
    ]

    assert coverage["total_cases"] == 8

    semantic = coverage[
        "semantic"
    ]

    assert semantic["critical_number_cases"] == 5
    assert semantic["critical_identifier_cases"] == 5
    assert semantic["critical_terminology_cases"] == 1
    assert semantic["multi_family_cases"] == 2
    assert semantic["three_family_cases"] == 1
    assert semantic["control_cases"] == 0

    assert (
        coverage[
            "audio"
        ]["compound_stress_cases"]
        == 0
    )
