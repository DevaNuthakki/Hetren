from __future__ import annotations

import pytest

from hvee.packs.asr.run04_scoring_adapter import (
    Run04ScoringError,
    _classify_run04_execution_status,
)
from hvee.packs.asr.run04_scoring_precommitment import (
    RUN04_EXECUTION_SUCCESS_STATUS,
    RUN04_OPERATOR_INTERRUPTION_STATUS,
    RUN04_PRIOR_SCORING_PRECOMMITMENT_SHA256,
    build_run04_scoring_precommitment_v1,
)


def _success_record(
    *,
    status: str = "SUCCESS",
):
    return {
        "status": status,
        "raw_transcript_text": "synthetic transcript",
        "model_role": "candidate",
        "execution_slot_ordinal": 1000,
    }


def _slot_293_record(
    *,
    status: str = "ERROR",
):
    return {
        "status": status,
        "raw_transcript_text": None,
        "model_role": "baseline",
        "execution_slot_ordinal": 293,
        "score_eligible": False,
        "operator_interruption_terminalization": True,
        "model_quality_failure": False,
    }


def test_corrected_precommitment_records_superseded_identity():
    bundle = build_run04_scoring_precommitment_v1()
    payload = bundle.payload

    assert payload["precommitment"]["version"] == "1.0.1"

    assert (
        payload["precommitment"][
            "supersedes_precommitment_sha256"
        ]
        == RUN04_PRIOR_SCORING_PRECOMMITMENT_SHA256
        == (
            "2bffc9b2a51d9b07f8fa6da5483cdbab"
            "9ca6c8ba32dffb55d3c32cea75c343d1"
        )
    )

    correction = payload[
        "post_unlock_pre_result_publication_correction"
    ]

    assert correction["applies"] is True
    assert (
        correction["observed_complete_result_status"]
        == "SUCCESS"
    )
    assert (
        correction[
            "observed_governed_interruption_status"
        ]
        == "ERROR"
    )
    assert (
        correction[
            "published_model_quality_summary_before_correction"
        ]
        is False
    )
    assert (
        correction[
            "persisted_scoring_artifacts_before_correction"
        ]
        is False
    )


def test_status_contract_is_exact_and_case_sensitive():
    payload = build_run04_scoring_precommitment_v1().payload

    policy = payload["pairing_policy"]

    assert RUN04_EXECUTION_SUCCESS_STATUS == "SUCCESS"
    assert RUN04_OPERATOR_INTERRUPTION_STATUS == "ERROR"

    assert policy["complete_result_status"] == "SUCCESS"
    assert policy["governed_interruption_status"] == "ERROR"
    assert policy["status_comparison_is_case_sensitive"] is True
    assert policy["unrecognized_execution_status_rejected"] is True

    assert (
        payload["accounting"]["expected_execution_status_counts"]
        == {
            "SUCCESS": 42471,
            "ERROR": 1,
        }
    )


def test_uppercase_success_is_accepted():
    assert (
        _classify_run04_execution_status(
            _success_record()
        )
        == "successful_transcript"
    )


@pytest.mark.parametrize(
    "status",
    (
        "success",
        "Success",
        "COMPLETED",
        "",
    ),
)
def test_non_frozen_success_encodings_are_rejected(
    status: str,
):
    with pytest.raises(
        Run04ScoringError,
        match="status contract",
    ):
        _classify_run04_execution_status(
            _success_record(status=status)
        )


def test_exact_governed_slot_293_error_is_accepted():
    assert (
        _classify_run04_execution_status(
            _slot_293_record()
        )
        == "governed_operator_interruption"
    )


def test_other_error_result_is_rejected():
    record = _slot_293_record()
    record["execution_slot_ordinal"] = 294

    with pytest.raises(
        Run04ScoringError,
        match="status contract",
    ):
        _classify_run04_execution_status(record)


def test_lowercase_error_is_not_silently_normalized():
    with pytest.raises(
        Run04ScoringError,
        match="status contract",
    ):
        _classify_run04_execution_status(
            _slot_293_record(status="error")
        )


def test_success_without_transcript_is_rejected():
    record = _success_record()
    record["raw_transcript_text"] = None

    with pytest.raises(
        Run04ScoringError,
        match="must carry transcript",
    ):
        _classify_run04_execution_status(record)
