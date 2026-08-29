from collections import Counter
from copy import deepcopy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.run04_corpus_plan import (
    ASR_RUN04_CORPUS_PLAN_PREREQUISITE_COMMIT,
    ASR_RUN04_CORPUS_PLAN_SHA256,
    ASRRun04CaseSlot,
    ASRRun04Partition,
    ASRRun04SourceClass,
    ASRRun04ValidityClass,
    build_asr_run04_corpus_plan_v1,
    calculate_asr_run04_corpus_plan_sha256,
    verify_asr_run04_corpus_plan_v1,
)
from hvee.packs.asr.run04_protocol import (
    ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS,
    ASR_RUN04_INVALID_CASE_FAMILIES,
    ASR_RUN04_SEMANTIC_FAMILY_QUOTAS,
    build_asr_run04_protocol_v1,
)


def test_run04_corpus_plan_has_frozen_identity():
    plan = build_asr_run04_corpus_plan_v1()

    assert plan.sha256 == ASR_RUN04_CORPUS_PLAN_SHA256
    assert calculate_asr_run04_corpus_plan_sha256(plan.payload) == (
        ASR_RUN04_CORPUS_PLAN_SHA256
    )
    assert verify_asr_run04_corpus_plan_v1(
        payload=plan.payload,
        expected_sha256=ASR_RUN04_CORPUS_PLAN_SHA256,
    )


def test_run04_corpus_plan_binds_protocol_and_checkpoint():
    plan = build_asr_run04_corpus_plan_v1()
    protocol = build_asr_run04_protocol_v1()

    assert plan.payload["protocol_sha256"] == protocol.sha256
    assert plan.payload["prerequisite_commit"] == (
        ASR_RUN04_CORPUS_PLAN_PREREQUISITE_COMMIT
    )
    assert len(ASR_RUN04_CORPUS_PLAN_PREREQUISITE_COMMIT) == 40


def test_run04_corpus_plan_freezes_exact_case_counts():
    plan = build_asr_run04_corpus_plan_v1()
    cases = plan.payload["case_slots"]
    report = plan.payload["allocation_report"]

    assert len(cases) == 136
    assert report["total_case_count"] == 136
    assert report["valid_case_count"] == 128
    assert report["invalid_case_count"] == 8
    assert [case["ordinal"] for case in cases] == list(range(1, 137))


def test_run04_corpus_plan_freezes_partition_counts():
    cases = build_asr_run04_corpus_plan_v1().payload["case_slots"]
    counts = Counter(
        (case["partition"], case["validity_class"])
        for case in cases
    )

    assert counts == {
        ("development", "valid"): 64,
        ("development", "invalid"): 4,
        ("validation", "valid"): 32,
        ("validation", "invalid"): 2,
        ("sealed_holdout", "valid"): 32,
        ("sealed_holdout", "invalid"): 2,
    }


def test_run04_corpus_plan_freezes_semantic_quotas():
    cases = build_asr_run04_corpus_plan_v1().payload["case_slots"]
    counts = Counter(
        case["semantic_family"]
        for case in cases
        if case["semantic_family"] is not None
    )

    assert counts == Counter(ASR_RUN04_SEMANTIC_FAMILY_QUOTAS)


def test_run04_corpus_plan_balances_acoustic_families_exactly():
    cases = build_asr_run04_corpus_plan_v1().payload["case_slots"]
    counts = Counter(
        case["acoustic_family"]
        for case in cases
        if case["acoustic_family"] is not None
    )

    assert counts == Counter(ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS)
    assert set(counts.values()) == {16}


def test_run04_corpus_plan_balances_families_within_partitions():
    cases = build_asr_run04_corpus_plan_v1().payload["case_slots"]

    expected_per_partition = {
        "development": 8,
        "validation": 4,
        "sealed_holdout": 4,
    }
    for partition, expected_count in expected_per_partition.items():
        partition_cases = [
            case
            for case in cases
            if case["partition"] == partition
            and case["validity_class"] == "valid"
        ]
        assert set(
            Counter(
                case["semantic_family"] for case in partition_cases
            ).values()
        ) == {expected_count}
        assert set(
            Counter(
                case["acoustic_family"] for case in partition_cases
            ).values()
        ) == {expected_count}


def test_run04_corpus_plan_assigns_each_invalid_family_once():
    cases = build_asr_run04_corpus_plan_v1().payload["case_slots"]
    invalid_families = tuple(
        case["invalid_family"]
        for case in cases
        if case["validity_class"] == "invalid"
    )

    assert sorted(invalid_families) == sorted(
        ASR_RUN04_INVALID_CASE_FAMILIES
    )
    assert len(set(invalid_families)) == 8


def test_run04_corpus_plan_separates_speaker_slots_by_partition():
    plan = build_asr_run04_corpus_plan_v1().payload
    speakers = plan["speaker_slots"]
    cases = plan["case_slots"]
    partition_by_speaker = {
        speaker["key"]: speaker["partition"] for speaker in speakers
    }

    assert len(speakers) == 16
    assert len({speaker["key"] for speaker in speakers}) == 16
    assert sum(
        speaker["source_class"] == "human" for speaker in speakers
    ) == 8
    assert sum(
        speaker["source_class"] == "synthetic" for speaker in speakers
    ) == 8
    for case in cases:
        if case["speaker_slot_key"] is not None:
            assert partition_by_speaker[case["speaker_slot_key"]] == (
                case["partition"]
            )


def test_run04_corpus_plan_assigns_eight_cases_per_speaker_slot():
    cases = build_asr_run04_corpus_plan_v1().payload["case_slots"]
    counts = Counter(
        case["speaker_slot_key"]
        for case in cases
        if case["speaker_slot_key"] is not None
    )

    assert len(counts) == 16
    assert set(counts.values()) == {8}


def test_run04_corpus_plan_contains_no_sources_labels_or_outcomes():
    payload = build_asr_run04_corpus_plan_v1().payload
    serialized = str(payload)

    assert payload["evidence_boundary"] == {
        "allocation_plan_frozen": True,
        "fresh_corpus_materialized": False,
        "source_and_rights_records_bound": False,
        "partition_commitments_bound": False,
        "holdout_membership_sealed": False,
        "asr_execution_performed": False,
        "run04_execution_authorized": False,
        "run04_completed": False,
        "production_qualified": False,
    }
    assert "transcript_text" not in serialized
    assert "audio_bytes" not in serialized
    assert "model_output_text" not in serialized
    assert "observed_failure_label" not in serialized


def test_run04_corpus_plan_rebuild_is_deterministic():
    first = build_asr_run04_corpus_plan_v1()
    second = build_asr_run04_corpus_plan_v1()

    assert first == second


def test_run04_corpus_plan_verifier_rejects_tampering():
    plan = build_asr_run04_corpus_plan_v1()
    tampered = deepcopy(plan.payload)
    tampered["case_slots"][0]["acoustic_family"] = "telephony"

    assert not verify_asr_run04_corpus_plan_v1(
        payload=tampered,
        expected_sha256=plan.sha256,
    )


def test_run04_case_slot_rejects_valid_slot_without_speaker():
    with pytest.raises(HveeContractError, match="require a speaker"):
        ASRRun04CaseSlot(
            ordinal=1,
            key="run04.test.valid.01",
            partition=ASRRun04Partition.DEVELOPMENT,
            validity_class=ASRRun04ValidityClass.VALID,
            semantic_family="critical-numbers",
            acoustic_family="clean",
            invalid_family=None,
            speaker_slot_key=None,
            source_class=ASRRun04SourceClass.HUMAN,
        )


def test_run04_case_slot_rejects_invalid_slot_with_semantics():
    with pytest.raises(HveeContractError, match="cannot declare a semantic"):
        ASRRun04CaseSlot(
            ordinal=1,
            key="run04.test.invalid.01",
            partition=ASRRun04Partition.DEVELOPMENT,
            validity_class=ASRRun04ValidityClass.INVALID,
            semantic_family="critical-numbers",
            acoustic_family=None,
            invalid_family="empty-audio",
            speaker_slot_key=None,
            source_class=ASRRun04SourceClass.INVALID_MEDIA,
        )
