from __future__ import annotations

import json

import pytest

from hvee.packs.asr.run04_scoring_adapter import (
    Run04ScoringError,
    score_transcript_pair,
    summarize_all_lane_categories,
    summarize_scored_pairs,
    validate_run04_lane_complete_pair_denominators,
)
from hvee.packs.asr.run04_scoring_precommitment import (
    RUN04_EXPECTED_GLOBAL_COMPLETE_PAIRS,
    RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS,
    RUN04_INPUT_ARTIFACTS,
    build_run04_scoring_precommitment_v1,
    calculate_run04_scoring_precommitment_sha256,
)


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def _pair(
    reference: str,
    baseline: str,
    candidate: str,
    *,
    recording_id: str = "synthetic-1",
    lane_roles=None,
):
    return score_transcript_pair(
        reference_text=reference,
        reference_text_sha256=_sha(reference),
        baseline_text=baseline,
        candidate_text=candidate,
        recording_id=recording_id,
        recording_identity_sha256="1" * 64,
        dataset_id="synthetic-dataset",
        lane_roles=lane_roles
        or {
            "prompt_generalization": "development",
            "critical_number_prompt_generalization": (
                "not_member"
            ),
        },
        baseline_metadata={
            "execution_id": "a" * 64,
            "execution_slot_ordinal": 1,
        },
        candidate_metadata={
            "execution_id": "b" * 64,
            "execution_slot_ordinal": 2,
        },
    )


def test_precommitment_is_deterministic():
    first = build_run04_scoring_precommitment_v1()
    second = build_run04_scoring_precommitment_v1()

    assert first == second
    assert first.sha256 == second.sha256
    assert first.sha256 == (
        calculate_run04_scoring_precommitment_sha256(
            first.payload
        )
    )


def test_precommitment_binds_exact_frozen_input_artifacts():
    payload = build_run04_scoring_precommitment_v1().payload

    assert (
        payload["input_artifacts"]
        == RUN04_INPUT_ARTIFACTS
    )

    assert payload["accounting"]["terminal_slots"] == 42472
    assert payload["accounting"]["recordings"] == 21236
    assert (
        payload["accounting"]["global_complete_pairs"]
        == RUN04_EXPECTED_GLOBAL_COMPLETE_PAIRS
        == 21235
    )


def test_precommitment_records_v1_2_as_correction_not_rewritten_history():
    payload = build_run04_scoring_precommitment_v1().payload

    assert (
        payload["historical_protocol"][
            "critical_number_evaluator_version"
        ]
        == "1.1.0"
    )
    assert (
        payload[
            "post_execution_pre_scoring_correction"
        ]["corrected_evaluator_version"]
        == "1.2.0"
    )
    assert (
        payload["historical_protocol"][
            "protocol_is_not_rewritten"
        ]
        is True
    )


def test_precommitment_separates_diagnostic_and_report_only_oracles():
    payload = build_run04_scoring_precommitment_v1().payload

    active = payload["active_oracles"]

    assert active["normalized_wer"]["role"] == "diagnostic_only"
    assert active["normalized_cer"]["role"] == "diagnostic_only"
    assert active["critical_number"]["role"] == "report_only"
    assert active["critical_identifier"]["role"] == "report_only"

    deferred = payload[
        "not_activated_by_this_scoring_pass"
    ]

    assert "critical_terminology" in deferred
    assert "negation_fidelity" in deferred
    assert "media_validity" in deferred


def test_precommitment_grants_no_release_or_certification_authority():
    payload = build_run04_scoring_precommitment_v1().payload

    assert (
        payload["precommitment"]["production_qualified"]
        is False
    )
    assert (
        payload["precommitment"]["release_decision_authority"]
        is False
    )
    assert (
        payload["precommitment"]["certification_issued"]
        is False
    )


def test_pair_scoring_detects_original_terminal_number_regression():
    row = _pair(
        "The value is 2.",
        "The value is 2.",
        "The value is 3.",
    )

    assert (
        row["baseline"]["critical_number_outcome"]
        == "preserved"
    )
    assert (
        row["candidate"]["critical_number_outcome"]
        == "not_preserved"
    )

    assert row["baseline"]["normalized_wer"] == 0.0
    assert row["candidate"]["normalized_wer"] > 0.0


def test_pair_scoring_returns_hashes_and_never_raw_transcripts():
    reference = "The first value is 10 and the second value is 2."
    baseline = "The first value is 10 and the second value is 2."
    candidate = "The first value is 10 and the second value is 3."

    row = _pair(
        reference,
        baseline,
        candidate,
    )

    serialized = json.dumps(
        row,
        sort_keys=True,
    )

    assert reference not in serialized
    assert baseline not in serialized
    assert candidate not in serialized

    assert (
        row["reference_text_sha256"]
        == _sha(reference)
    )
    assert (
        row["baseline"]["prediction_text_sha256"]
        == _sha(baseline)
    )
    assert (
        row["candidate"]["prediction_text_sha256"]
        == _sha(candidate)
    )


def test_pair_scoring_rejects_reference_digest_mismatch():
    with pytest.raises(
        Run04ScoringError,
        match="reference text",
    ):
        score_transcript_pair(
            reference_text="The value is 2.",
            reference_text_sha256="0" * 64,
            baseline_text="The value is 2.",
            candidate_text="The value is 3.",
            recording_id="synthetic",
            recording_identity_sha256="1" * 64,
            dataset_id="synthetic",
            lane_roles={},
        )


def test_global_summary_reports_direction_without_claiming_release():
    first = _pair(
        "hello world",
        "hello word",
        "hello world",
        recording_id="one",
    )
    second = _pair(
        "The value is 2.",
        "The value is 2.",
        "The value is 3.",
        recording_id="two",
    )

    summary = summarize_scored_pairs(
        (first, second)
    )

    assert summary["pair_count"] == 2

    wer = summary["normalized_wer"]

    assert (
        wer["candidate_lower_count"]
        + wer["candidate_higher_count"]
        + wer["unchanged_count"]
        == 2
    )


def test_all_observed_lane_role_categories_are_reported():
    first = _pair(
        "hello",
        "hello",
        "hello",
        recording_id="one",
        lane_roles={
            "prompt_generalization": "development",
            "speaker_generalization": "not_member",
        },
    )
    second = _pair(
        "world",
        "world",
        "word",
        recording_id="two",
        lane_roles={
            "prompt_generalization": "validation",
            "speaker_generalization": "validation",
        },
    )

    categories = summarize_all_lane_categories(
        (first, second)
    )

    observed = {
        (
            item["lane_key"],
            item["role_value_canonical_json"],
        )
        for item in categories
    }

    assert (
        "prompt_generalization",
        '"development"',
    ) in observed

    assert (
        "prompt_generalization",
        '"validation"',
    ) in observed

    assert (
        "speaker_generalization",
        '"validation"',
    ) in observed


def test_precommitment_output_policy_forbids_raw_text_persistence():
    policy = build_run04_scoring_precommitment_v1().payload[
        "reporting_policy"
    ]

    assert (
        policy[
            "raw_reference_text_persisted_in_scored_output"
        ]
        is False
    )
    assert (
        policy[
            "raw_prediction_text_persisted_in_scored_output"
        ]
        is False
    )
    assert (
        policy["reference_text_sha256_persisted"]
        is True
    )
    assert (
        policy["prediction_text_sha256_persisted"]
        is True
    )



def _synthetic_frozen_lane_rows():
    rows = [
        {
            "lane_roles": {},
        }
        for _ in range(
            RUN04_EXPECTED_GLOBAL_COMPLETE_PAIRS
        )
    ]

    for (
        lane_key,
        role_counts,
    ) in RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS.items():
        cursor = 0

        for role_value, count in role_counts.items():
            end = cursor + count

            for row in rows[cursor:end]:
                lane_roles = row["lane_roles"]

                assert isinstance(lane_roles, dict)

                lane_roles[lane_key] = role_value

            cursor = end

        assert cursor == len(rows)

    return rows


def test_precommitment_binds_every_exact_lane_role_denominator():
    payload = build_run04_scoring_precommitment_v1().payload

    assert (
        payload["accounting"][
            "expected_lane_role_complete_pairs"
        ]
        == RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS
    )


def test_lane_denominator_gate_accepts_exact_frozen_distribution():
    rows = _synthetic_frozen_lane_rows()

    observed = (
        validate_run04_lane_complete_pair_denominators(
            rows
        )
    )

    assert observed == RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS


def test_lane_denominator_gate_rejects_single_pair_membership_drift():
    rows = _synthetic_frozen_lane_rows()

    lane_roles = rows[0]["lane_roles"]

    assert isinstance(lane_roles, dict)

    assert (
        lane_roles["prompt_generalization"]
        == "development"
    )

    lane_roles["prompt_generalization"] = "validation"

    with pytest.raises(
        Run04ScoringError,
        match="lane denominator mismatch",
    ):
        validate_run04_lane_complete_pair_denominators(
            rows
        )


def test_lane_denominator_gate_rejects_unknown_lane_role():
    rows = _synthetic_frozen_lane_rows()

    lane_roles = rows[0]["lane_roles"]

    assert isinstance(lane_roles, dict)

    lane_roles[
        "critical_number_prompt_generalization"
    ] = "invented_after_scoring"

    with pytest.raises(
        Run04ScoringError,
        match="unexpected Run-04 lane role",
    ):
        validate_run04_lane_complete_pair_denominators(
            rows
        )
