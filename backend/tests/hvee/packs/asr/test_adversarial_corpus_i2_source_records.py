"""Integrity tests for the I2 synthetic ASR source inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hvee.packs.asr.adversarial_corpus_records import (
    verify_asr_adversarial_corpus_record_v1,
)


BACKEND_ROOT = Path(__file__).resolve().parents[4]

CORPUS_ROOT = (
    BACKEND_ROOT
    / "corpora/asr/adversarial/v1"
)

TRANSCRIPT_ROOT = (
    CORPUS_ROOT
    / "specification/transcripts"
)

PROVENANCE_ROOT = (
    CORPUS_ROOT
    / "records/provenance"
)

RIGHTS_ROOT = (
    CORPUS_ROOT
    / "records/rights"
)

GENERATION_PLAN_PATH = (
    CORPUS_ROOT
    / "specification/generation-plan.json"
)


GENERATOR_EXECUTABLE_SHA256 = (
    "0a2f26e328f1dd4cec926987d3dc22bf"
    "841879132fd3aa497dd4fcad0d4d77a3"
)

PACKAGED_COPYRIGHT_SHA256 = (
    "bf721eede49d50f84bd2c50f96888629"
    "ced572b66ad4087c7a224c4a5e1193bb"
)

GENERATION_PLAN_SHA256 = (
    "7c3f4a729a490ea2471f86ef4077e1c4"
    "eb38f5c095ba29e66373c139a14e1c57"
)


CASE_IDENTITIES = {
    "clean.identifier-account-order": {
        "transcript": (
            "11d6c34c81e191689d12c25a58e0c9ac"
            "632b4823120fb4c497932844cee52bf7"
        ),
        "provenance": (
            "36bf894c8d87bbc77f87952a205edaa3"
            "bdd1ef7f22a4b75d4dce676a8cdf76bf"
        ),
        "rights": (
            "0efb0b85af7394612abab52185fc43811"
            "ecd5f362a7976f696e01ed39952845c"
        ),
    },
    "clean.identifier-confirmation": {
        "transcript": (
            "97156fd122354ef16e51ec12411d5f194"
            "1768364004ab2ea3e7827d77e9acd26"
        ),
        "provenance": (
            "a11556ba44a0381a0e3e6035166b1263"
            "f62d9a6a5ae815fe5151e2a21f9efd02"
        ),
        "rights": (
            "ac9ded0f23b45f96d0f1842cf3d85e34"
            "3d275faba8a1b298c4bae84d6b1eff5b"
        ),
    },
    "clean.identifier-multiple": {
        "transcript": (
            "fe01d5cac4e97a7835d12a7469c524c0"
            "5c90d47cafbce1a9dc5b0bad67bfef6d"
        ),
        "provenance": (
            "d0de5c0b7de55db1b940f4fbac6f5018"
            "d2edc80f14e1003b58ca968c1ba6fdfd"
        ),
        "rights": (
            "8448ae71a3b9a4c157d9301451a4f86f"
            "f8b32a627829b94aa9a7305ac04bd9b6"
        ),
    },
    "clean.multi-number-id": {
        "transcript": (
            "18fcfcdfdd4c14da6b5333366455beaa"
            "70d90ada78b8c2de5eff96edd4ac9584"
        ),
        "provenance": (
            "f804bf7391cc39286bc54d5727ebe01f"
            "61d3a460f169a1b9b4d9d43a903113b4"
        ),
        "rights": (
            "0b38e02c548a775ed4db61603fdcc681"
            "48840d3396feaef59ac8d51c6b3c6ae7"
        ),
    },
    "clean.number-currency-time": {
        "transcript": (
            "4bac8f9591f3baa62018f15676bb91f6"
            "b61d876cef773e8e99f783c8b7e30f82"
        ),
        "provenance": (
            "ae8dac7e2893bbe643950b1b6ec64261"
            "1a2bf5c38406c77e6bc9dcff7e44ba8a"
        ),
        "rights": (
            "f3b89d00b8c9be37055514fa6a429259"
            "2768bd797ccde8e9fb8776acfaaf10be"
        ),
    },
    "clean.number-measurement": {
        "transcript": (
            "400070fbb7cd86169cdd52c476bf1fd5"
            "d868a92f9d0cad48ad447758178ac3f2"
        ),
        "provenance": (
            "84474e713f6889d12c2baeb7fc08efe0"
            "cc7b17ef43ee33fb6facf23ab20bccef"
        ),
        "rights": (
            "aeb089aa364b4d2c0fec5731b74cda61"
            "b484c6433db68553e79c55665f07d5ec"
        ),
    },
    "clean.number-percentage": {
        "transcript": (
            "7d23314ebbe3ff3e971dd7394c57822e"
            "9ec8cb0dde3451a063a7c726b79fff70"
        ),
        "provenance": (
            "a5ee833742b53fb0a79bfb2b039ff032"
            "55053538ed5895e699ab9aed25f06105"
        ),
        "rights": (
            "067555dd4af75f64c65343edc37614ca"
            "7fdf58d124fc379bf081ac9b8564c41b"
        ),
    },
    "control.clean-critical": {
        "transcript": (
            "cb85655794bc5b0c2a5d5d5c1626b0e"
            "3b208bc28ecfce4aa3275ed73ea2e6744"
        ),
        "provenance": (
            "30d7a75e8ad8dca1f03a3576d167a12b"
            "62bff7df2fbd5bfe7a2e825771dde1c4"
        ),
        "rights": (
            "cfcc0861946a6fe96da954f6efda69e7"
            "45e7bd2533e1f9b8718e0084d7bcdb14"
        ),
    },
}


CASE_IDS = tuple(
    CASE_IDENTITIES
)


def _load_document(
    file_path: Path,
) -> dict[str, object]:
    document = json.loads(
        file_path.read_text(
            encoding="utf-8"
        )
    )

    assert set(document) == {
        "payload",
        "sha256",
    }

    return document


def _sha256_file(
    file_path: Path,
) -> str:
    return hashlib.sha256(
        file_path.read_bytes()
    ).hexdigest()


def _verify_document(
    file_path: Path,
):
    document = _load_document(
        file_path
    )

    verified = (
        verify_asr_adversarial_corpus_record_v1(
            payload=document["payload"],
            expected_sha256=document["sha256"],
        )
    )

    assert verified.payload == document["payload"]
    assert verified.sha256 == document["sha256"]

    return verified


@pytest.mark.parametrize(
    "case_id",
    CASE_IDS,
)
def test_i2_source_record_identity_and_binding(
    case_id: str,
):
    identities = CASE_IDENTITIES[
        case_id
    ]

    transcript_path = (
        TRANSCRIPT_ROOT
        / f"{case_id}.txt"
    )

    assert transcript_path.is_file()
    assert not transcript_path.is_symlink()

    assert (
        _sha256_file(
            transcript_path
        )
        == identities["transcript"]
    )

    provenance = _verify_document(
        PROVENANCE_ROOT
        / f"{case_id}.json"
    )

    rights = _verify_document(
        RIGHTS_ROOT
        / f"{case_id}.json"
    )

    assert (
        provenance.sha256
        == identities["provenance"]
    )

    assert (
        rights.sha256
        == identities["rights"]
    )

    provenance_record = (
        provenance.payload["record"]
    )

    assert (
        provenance_record["case_id"]
        == case_id
    )

    assert (
        provenance_record[
            "transcript_sha256"
        ]
        == identities["transcript"]
    )

    assert (
        provenance_record["source_kind"]
        == "synthetic_tts"
    )

    generator = (
        provenance_record["generator"]
    )

    assert generator == {
        "amplitude": 100,
        "executable_sha256": (
            GENERATOR_EXECUTABLE_SHA256
        ),
        "key": "espeak-ng",
        "pitch": 50,
        "platform_key": "linux-amd64",
        "speed_wpm": 150,
        "version": (
            "1.51+dfsg-10+deb12u2"
        ),
        "voice_key": "en-us",
    }

    rights_record = (
        rights.payload["record"]
    )

    assert (
        rights_record["case_id"]
        == case_id
    )

    assert (
        rights_record["review_status"]
        == "not_adjudicated"
    )

    assert (
        rights_record[
            "development_use_only"
        ]
        is True
    )

    assert (
        rights_record["source_package"]
        == {
            "key": "debian.espeak-ng",
            "version": (
                "1.51+dfsg-10+deb12u2"
            ),
            "packaged_copyright_sha256": (
                PACKAGED_COPYRIGHT_SHA256
            ),
        }
    )


def test_i2_generation_plan_binds_exact_source_inventory():
    plan = _verify_document(
        GENERATION_PLAN_PATH
    )

    assert (
        plan.sha256
        == GENERATION_PLAN_SHA256
    )

    record = plan.payload[
        "record"
    ]

    assert (
        record["corpus_id"]
        == "qualification.synthetic-v1"
    )

    assert (
        record["corpus_version"]
        == "1.0.0"
    )

    entries = record["entries"]

    assert len(entries) == 8

    assert tuple(
        entry["case_id"]
        for entry in entries
    ) == CASE_IDS

    for entry in entries:
        case_id = entry[
            "case_id"
        ]

        identities = (
            CASE_IDENTITIES[
                case_id
            ]
        )

        assert (
            entry[
                "output_relative_path"
            ]
            == f"source/{case_id}.wav"
        )

        assert (
            entry[
                "provenance_record_sha256"
            ]
            == identities["provenance"]
        )

        assert (
            entry[
                "rights_record_sha256"
            ]
            == identities["rights"]
        )

        assert (
            entry[
                "transformation_record_sha256"
            ]
            is None
        )


def test_i2_source_evidence_remains_non_certifying():
    documents = [
        _load_document(
            GENERATION_PLAN_PATH
        )
    ]

    for case_id in CASE_IDS:
        documents.extend(
            (
                _load_document(
                    PROVENANCE_ROOT
                    / f"{case_id}.json"
                ),
                _load_document(
                    RIGHTS_ROOT
                    / f"{case_id}.json"
                ),
            )
        )

    for document in documents:
        boundary = document[
            "payload"
        ]["evidence_boundary"]

        assert (
            boundary[
                "development_evidence_only"
            ]
            is True
        )

        assert (
            boundary[
                "qualification_threshold_applied"
            ]
            is False
        )

        assert (
            boundary[
                "certification_issued"
            ]
            is False
        )

        assert (
            boundary[
                "production_qualified"
            ]
            is False
        )

        assert (
            boundary[
                "release_enforcement_eligible"
            ]
            is False
        )

        assert (
            boundary[
                "official_release_verdict_modified"
            ]
            is False
        )
