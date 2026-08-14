"""Contract tests for deterministic adversarial corpus derivation plans."""

from __future__ import annotations

import copy
import hashlib

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_corpus_records import (
    ASRAdversarialCorpusDerivationPlan,
    ASRAdversarialCorpusDerivationPlanEntry,
    build_asr_adversarial_corpus_derivation_plan_v1,
    verify_asr_adversarial_corpus_record_v1,
)


def _sha(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _entry(
    *,
    case_id: str = (
        "stress.codec-mulaw.multi-number-id"
    ),
    parent_case_id: str = (
        "clean.multi-number-id"
    ),
    parent_path: str = (
        "clean/clean.multi-number-id.wav"
    ),
    output_path: str = (
        "telephony/"
        "stress.codec-mulaw.multi-number-id.wav"
    ),
) -> ASRAdversarialCorpusDerivationPlanEntry:
    return ASRAdversarialCorpusDerivationPlanEntry(
        case_id=case_id,
        parent_case_id=parent_case_id,
        parent_relative_path=parent_path,
        parent_audio_sha256=_sha(
            "canonical-parent-audio"
        ),
        output_relative_path=output_path,
        provenance_record_sha256=_sha(
            "provenance"
        ),
        rights_record_sha256=_sha(
            "rights"
        ),
        transformation_record_sha256=_sha(
            "transformation"
        ),
    )


def _plan(
) -> ASRAdversarialCorpusDerivationPlan:
    return ASRAdversarialCorpusDerivationPlan(
        corpus_id=(
            "qualification.synthetic-stress-v1"
        ),
        corpus_version="1.0.0",
        parent_manifest_sha256=_sha(
            "canonical-parent-manifest"
        ),
        entries=(
            _entry(),
        ),
    )


def test_derivation_plan_is_deterministic_and_verifiable():
    first = (
        build_asr_adversarial_corpus_derivation_plan_v1(
            _plan()
        )
    )

    second = (
        build_asr_adversarial_corpus_derivation_plan_v1(
            _plan()
        )
    )

    assert first == second

    assert (
        verify_asr_adversarial_corpus_record_v1(
            payload=first.payload,
            expected_sha256=first.sha256,
        )
        == first
    )


def test_derivation_plan_binds_exact_parent_lineage():
    bundle = (
        build_asr_adversarial_corpus_derivation_plan_v1(
            _plan()
        )
    )

    record = bundle.payload[
        "record"
    ]

    assert (
        record[
            "parent_manifest_sha256"
        ]
        == _sha(
            "canonical-parent-manifest"
        )
    )

    entry = record[
        "entries"
    ][0]

    assert (
        entry["case_id"]
        == "stress.codec-mulaw.multi-number-id"
    )

    assert (
        entry["parent_case_id"]
        == "clean.multi-number-id"
    )

    assert (
        entry["parent_relative_path"]
        == "clean/clean.multi-number-id.wav"
    )

    assert (
        entry["parent_audio_sha256"]
        == _sha(
            "canonical-parent-audio"
        )
    )

    assert (
        entry["output_relative_path"]
        == (
            "telephony/"
            "stress.codec-mulaw.multi-number-id.wav"
        )
    )


def test_derivation_plan_remains_non_authoritative():
    bundle = (
        build_asr_adversarial_corpus_derivation_plan_v1(
            _plan()
        )
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert (
        boundary[
            "development_evidence_only"
        ]
        is True
    )
    assert (
        boundary[
            "rights_adjudicated"
        ]
        is False
    )
    assert (
        boundary[
            "human_acoustic_diversity_established"
        ]
        is False
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


@pytest.mark.parametrize(
    (
        "case_id",
        "parent_case_id",
        "parent_path",
        "output_path",
    ),
    (
        (
            "clean.multi-number-id",
            "clean.multi-number-id",
            "clean/clean.multi-number-id.wav",
            (
                "telephony/"
                "stress.codec-mulaw.multi-number-id.wav"
            ),
        ),
        (
            "stress.codec-mulaw.multi-number-id",
            "clean.multi-number-id",
            "clean/clean.multi-number-id.wav",
            "clean/clean.multi-number-id.wav",
        ),
    ),
)
def test_derivation_entry_rejects_ambiguous_self_derivation(
    case_id: str,
    parent_case_id: str,
    parent_path: str,
    output_path: str,
):
    with pytest.raises(
        HveeContractError
    ):
        _entry(
            case_id=case_id,
            parent_case_id=parent_case_id,
            parent_path=parent_path,
            output_path=output_path,
        )


def test_derivation_plan_requires_sorted_unique_case_ids():
    later = _entry(
        case_id="stress.telephony-z",
        output_path="telephony/stress.telephony-z.wav",
    )

    earlier = _entry(
        case_id="stress.telephony-a",
        output_path="telephony/stress.telephony-a.wav",
    )

    with pytest.raises(
        HveeContractError
    ):
        ASRAdversarialCorpusDerivationPlan(
            corpus_id=(
                "qualification.synthetic-stress-v1"
            ),
            corpus_version="1.0.0",
            parent_manifest_sha256=_sha(
                "manifest"
            ),
            entries=(
                later,
                earlier,
            ),
        )


def test_derivation_plan_requires_unique_output_paths():
    first = _entry(
        case_id="stress.telephony-a",
        output_path="telephony/shared.wav",
    )

    second = _entry(
        case_id="stress.telephony-b",
        output_path="telephony/shared.wav",
    )

    with pytest.raises(
        HveeContractError
    ):
        ASRAdversarialCorpusDerivationPlan(
            corpus_id=(
                "qualification.synthetic-stress-v1"
            ),
            corpus_version="1.0.0",
            parent_manifest_sha256=_sha(
                "manifest"
            ),
            entries=(
                first,
                second,
            ),
        )


def test_derivation_plan_verifier_rejects_tampering():
    bundle = (
        build_asr_adversarial_corpus_derivation_plan_v1(
            _plan()
        )
    )

    payload = copy.deepcopy(
        bundle.payload
    )

    payload[
        "record"
    ]["entries"][0][
        "parent_relative_path"
    ] = "clean/another-parent.wav"

    with pytest.raises(
        HveeContractError
    ):
        verify_asr_adversarial_corpus_record_v1(
            payload=payload,
            expected_sha256=bundle.sha256,
        )
