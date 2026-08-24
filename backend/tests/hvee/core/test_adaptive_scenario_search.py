from copy import deepcopy

import pytest

from hvee.core.adaptive_scenario_search import (
    ADAPTIVE_SCENARIO_SEARCH_SCHEMA_VERSION,
    AdaptiveScenarioObservation,
    build_adaptive_scenario_search_bundle,
    calculate_adaptive_scenario_search_sha256,
    calculate_candidate_values_sha256,
    verify_adaptive_scenario_search_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.observed_boundary import (
    verify_observed_boundary_bundle,
)


def _sha(character: str) -> str:
    return character * 64


def _observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
    character: str,
) -> AdaptiveScenarioObservation:
    return AdaptiveScenarioObservation(
        sequence=sequence,
        candidate_index=candidate_index,
        scenario_sha256=_sha(character),
        verdict=verdict,
        result_provenance_sha256=_sha("a"),
        observation_evidence_sha256=_sha("b"),
        decision_evidence_sha256=_sha("c"),
        counterexample_evidence_sha256=(
            _sha("d")
            if verdict == DecisionVerdict.FAIL
            else None
        ),
    )


def _terminal_observations():
    return (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
        _observation(
            sequence=2,
            candidate_index=8,
            verdict=DecisionVerdict.FAIL,
            character="2",
        ),
        _observation(
            sequence=3,
            candidate_index=4,
            verdict=DecisionVerdict.PASS,
            character="3",
        ),
        _observation(
            sequence=4,
            candidate_index=6,
            verdict=DecisionVerdict.FAIL,
            character="4",
        ),
        _observation(
            sequence=5,
            candidate_index=5,
            verdict=DecisionVerdict.FAIL,
            character="5",
        ),
    )


def _build(
    *,
    candidates=None,
    invariants: dict[str, object] | None = None,
    maximum_observations: int = 6,
    observations=(),
):
    return build_adaptive_scenario_search_bundle(
        evaluation_type="asr",
        search_key="hetren.asr.noise-search",
        search_version="1.0.0",
        boundary_key="hetren.asr.observed-boundary",
        boundary_version="1.0.0",
        axis_key="asr.noise.snr-db",
        axis_version="1.0.0",
        axis_unit="dB",
        candidate_values=(
            candidates
            if candidates is not None
            else tuple(range(9))
        ),
        invariant_parameters=(
            invariants
            if invariants is not None
            else {
                "codec": "pcm-s16le",
                "sample_rate_hz": 16000,
            }
        ),
        maximum_observations=maximum_observations,
        observations=observations,
    )


def test_empty_search_proposes_lower_endpoint():
    bundle = _build()

    assert bundle.payload["schema_version"] == (
        ADAPTIVE_SCENARIO_SEARCH_SCHEMA_VERSION
    )
    assert bundle.payload["type"] == "adaptive_scenario_search"
    assert bundle.payload["search"]["status"] == "ready"
    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 0,
        "axis_value": 0.0,
        "reason": "initial_lower",
    }
    assert bundle.payload["observations"] == []
    assert bundle.observed_boundary is None
    assert verify_adaptive_scenario_search_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_first_observation_proposes_upper_endpoint():
    bundle = _build(
        observations=(
            _observation(
                sequence=1,
                candidate_index=0,
                verdict=DecisionVerdict.PASS,
                character="1",
            ),
        )
    )

    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 8,
        "axis_value": 8.0,
        "reason": "initial_upper",
    }


def test_opposing_endpoints_propose_bracket_midpoint():
    bundle = _build(
        observations=_terminal_observations()[:2]
    )

    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 4,
        "axis_value": 4.0,
        "reason": "refine_observed_bracket",
    }
    assert bundle.payload["outcome"]["observed_bracket"] == {
        "lower": {
            "candidate_index": 0,
            "axis_value": 0.0,
            "scenario_sha256": _sha("1"),
            "verdict": "pass",
        },
        "upper": {
            "candidate_index": 8,
            "axis_value": 8.0,
            "scenario_sha256": _sha("2"),
            "verdict": "fail",
        },
        "candidate_gap": 8,
        "axis_width": 8.0,
        "adjacent_candidates": False,
    }


def test_same_verdict_endpoints_explore_largest_gap():
    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
        _observation(
            sequence=2,
            candidate_index=8,
            verdict=DecisionVerdict.PASS,
            character="2",
        ),
    )
    bundle = _build(observations=observations)

    assert bundle.payload["outcome"]["observed_bracket"] is None
    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 4,
        "axis_value": 4.0,
        "reason": "explore_largest_gap",
    }


def test_largest_gap_tie_selects_lower_interval():
    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
        _observation(
            sequence=2,
            candidate_index=8,
            verdict=DecisionVerdict.PASS,
            character="2",
        ),
        _observation(
            sequence=3,
            candidate_index=4,
            verdict=DecisionVerdict.PASS,
            character="3",
        ),
    )
    bundle = _build(observations=observations)

    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 2,
        "axis_value": 2.0,
        "reason": "explore_largest_gap",
    }


def test_terminal_adjacent_bracket_builds_observed_boundary():
    bundle = _build(observations=_terminal_observations())
    boundary = bundle.observed_boundary

    assert bundle.payload["search"]["status"] == (
        "boundary_bracketed"
    )
    assert bundle.payload["outcome"]["next_proposal"] is None
    assert bundle.payload["outcome"]["observed_bracket"][
        "candidate_gap"
    ] == 1
    assert boundary is not None
    assert bundle.payload["outcome"][
        "observed_boundary_sha256"
    ] == boundary.sha256
    assert boundary.payload["axis"]["interval"] == {
        "lower": 4.0,
        "upper": 5.0,
        "width": 1.0,
    }
    assert verify_observed_boundary_bundle(
        payload=boundary.payload,
        expected_sha256=boundary.sha256,
    )
    assert verify_adaptive_scenario_search_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_bundle_is_deterministic_across_invariant_key_order():
    first = _build(
        invariants={
            "codec": "pcm-s16le",
            "sample_rate_hz": 16000,
        },
        observations=_terminal_observations()[:2],
    )
    second = _build(
        invariants={
            "sample_rate_hz": 16000,
            "codec": "pcm-s16le",
        },
        observations=_terminal_observations()[:2],
    )

    assert first == second


def test_builder_detaches_mutable_inputs():
    candidates = list(range(9))
    invariants = {"codec": "pcm-s16le"}
    bundle = _build(
        candidates=candidates,
        invariants=invariants,
    )

    candidates[0] = -99
    invariants["codec"] = "changed"

    assert bundle.payload["axis"]["candidate_values"][0] == 0.0
    assert bundle.payload["invariants"]["parameters"] == {
        "codec": "pcm-s16le"
    }


def test_candidate_identity_is_independently_reproducible():
    bundle = _build()

    assert bundle.candidate_values_sha256 == (
        calculate_candidate_values_sha256(tuple(range(9)))
    )


def test_budget_exhaustion_stops_with_unexplored_candidates():
    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
        _observation(
            sequence=2,
            candidate_index=8,
            verdict=DecisionVerdict.PASS,
            character="2",
        ),
    )
    bundle = _build(
        maximum_observations=2,
        observations=observations,
    )

    assert bundle.payload["search"]["status"] == (
        "budget_exhausted"
    )
    assert bundle.payload["budget"] == {
        "maximum_observations": 2,
        "observed_count": 2,
        "remaining_observations": 0,
    }
    assert bundle.payload["outcome"]["next_proposal"] is None


def test_candidate_grid_exhaustion_is_distinct_from_budget():
    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
        _observation(
            sequence=2,
            candidate_index=1,
            verdict=DecisionVerdict.PASS,
            character="2",
        ),
    )
    bundle = _build(
        candidates=(0, 1),
        maximum_observations=2,
        observations=observations,
    )

    assert bundle.payload["search"]["status"] == (
        "candidate_grid_exhausted"
    )


@pytest.mark.parametrize(
    "maximum",
    [
        True,
        1,
        10,
    ],
)
def test_rejects_invalid_observation_budget(maximum):
    with pytest.raises(
        HveeContractError,
        match="maximum observations",
    ):
        _build(maximum_observations=maximum)


@pytest.mark.parametrize(
    "candidates",
    [
        (),
        (1,),
        (0, 0, 1),
        (1, 0),
        (0, True),
        (0, float("nan")),
        (0, float("inf")),
        (-1e308, 1e308),
        (-1e308, 0, 1e308),
    ],
)
def test_rejects_invalid_candidate_grid(candidates):
    with pytest.raises(HveeContractError):
        _build(
            candidates=candidates,
            maximum_observations=2,
        )


def test_rejects_noncontiguous_observation_sequence():
    with pytest.raises(
        HveeContractError,
        match="sequences must be contiguous",
    ):
        _build(
            observations=(
                _observation(
                    sequence=2,
                    candidate_index=0,
                    verdict=DecisionVerdict.PASS,
                    character="1",
                ),
            )
        )


def test_rejects_observation_outside_deterministic_trajectory():
    observations = (
        *_terminal_observations()[:2],
        _observation(
            sequence=3,
            candidate_index=3,
            verdict=DecisionVerdict.PASS,
            character="3",
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="deterministic proposal trajectory",
    ):
        _build(observations=observations)


def test_rejects_observations_after_terminal_boundary():
    observations = (
        *_terminal_observations(),
        _observation(
            sequence=6,
            candidate_index=7,
            verdict=DecisionVerdict.FAIL,
            character="6",
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="cannot continue after",
    ):
        _build(
            maximum_observations=7,
            observations=observations,
        )


def test_rejects_duplicate_scenario_identity():
    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
        _observation(
            sequence=2,
            candidate_index=8,
            verdict=DecisionVerdict.FAIL,
            character="1",
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="distinct scenarios",
    ):
        _build(observations=observations)


def test_failing_observation_requires_counterexample_evidence():
    with pytest.raises(
        HveeContractError,
        match="counterexample evidence SHA-256",
    ):
        AdaptiveScenarioObservation(
            sequence=1,
            candidate_index=0,
            scenario_sha256=_sha("1"),
            verdict=DecisionVerdict.FAIL,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        )


def test_passing_observation_rejects_counterexample_evidence():
    with pytest.raises(
        HveeContractError,
        match="passing adaptive observations",
    ):
        AdaptiveScenarioObservation(
            sequence=1,
            candidate_index=0,
            scenario_sha256=_sha("1"),
            verdict=DecisionVerdict.PASS,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
            counterexample_evidence_sha256=_sha("d"),
        )


@pytest.mark.parametrize(
    "verdict",
    [
        DecisionVerdict.INCONCLUSIVE,
        DecisionVerdict.INVALID,
    ],
)
def test_observation_rejects_nonbinary_verdict(verdict):
    with pytest.raises(
        HveeContractError,
        match="pass or fail verdicts",
    ):
        AdaptiveScenarioObservation(
            sequence=1,
            candidate_index=0,
            scenario_sha256=_sha("1"),
            verdict=verdict,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        )


def test_verifier_rejects_observation_tampering():
    bundle = _build(
        observations=_terminal_observations()[:2]
    )
    tampered = deepcopy(bundle.payload)
    tampered["observations"][0]["axis_value"] = -1.0
    recomputed = calculate_adaptive_scenario_search_sha256(
        tampered
    )

    assert not verify_adaptive_scenario_search_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_proposal_tampering():
    bundle = _build(
        observations=_terminal_observations()[:2]
    )
    tampered = deepcopy(bundle.payload)
    tampered["outcome"]["next_proposal"][
        "candidate_index"
    ] = 3
    recomputed = calculate_adaptive_scenario_search_sha256(
        tampered
    )

    assert not verify_adaptive_scenario_search_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_budget_tampering():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["budget"]["remaining_observations"] = 99
    recomputed = calculate_adaptive_scenario_search_sha256(
        tampered
    )

    assert not verify_adaptive_scenario_search_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_candidate_digest_tampering():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["axis"]["candidate_values_sha256"] = _sha("e")
    recomputed = calculate_adaptive_scenario_search_sha256(
        tampered
    )

    assert not verify_adaptive_scenario_search_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_boundary_digest_tampering():
    bundle = _build(observations=_terminal_observations())
    tampered = deepcopy(bundle.payload)
    tampered["outcome"]["observed_boundary_sha256"] = _sha("e")
    recomputed = calculate_adaptive_scenario_search_sha256(
        tampered
    )

    assert not verify_adaptive_scenario_search_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_extra_fields():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["estimated_failure_probability"] = 0.5
    recomputed = calculate_adaptive_scenario_search_sha256(
        tampered
    )

    assert not verify_adaptive_scenario_search_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_payload_excludes_local_identity_and_raw_content_fields():
    serialized = str(
        _build(observations=_terminal_observations()).payload
    ).lower()

    for forbidden in (
        "evaluation_run_id",
        "result_id",
        "created_at",
        "audio_file_path",
        "reference_transcript",
        "generated_transcript",
    ):
        assert forbidden not in serialized


def test_evidence_boundary_explicitly_limits_claims():
    boundary = _build().payload["evidence_boundary"]

    assert boundary == {
        "observations_require_execution_evidence": True,
        "next_proposal_is_an_observation": False,
        "unexecuted_outcomes_inferred": False,
        "causal_explanation_claimed": False,
        "minimality_claimed": False,
        "qualification_authority": False,
    }
