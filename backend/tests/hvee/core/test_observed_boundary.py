from copy import deepcopy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.observed_boundary import (
    OBSERVED_BOUNDARY_SCHEMA_VERSION,
    ObservedBoundaryEndpoint,
    build_observed_boundary_bundle,
    calculate_observed_boundary_sha256,
    verify_observed_boundary_bundle,
)


def _sha(character: str) -> str:
    return character * 64


def _endpoint(
    *,
    axis_value: float,
    verdict: DecisionVerdict,
    character: str,
) -> ObservedBoundaryEndpoint:
    return ObservedBoundaryEndpoint(
        axis_value=axis_value,
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


def _build(
    *,
    endpoints=None,
    invariants: dict[str, object] | None = None,
):
    return build_observed_boundary_bundle(
        evaluation_type="asr",
        boundary_key="hetren.asr.observed-boundary",
        boundary_version="1.0.0",
        search_key="hetren.asr.noise-search",
        search_version="1.0.0",
        axis_key="asr.noise.snr-db",
        axis_version="1.0.0",
        axis_unit="dB",
        invariant_parameters=(
            invariants
            if invariants is not None
            else {
                "codec": "pcm-s16le",
                "sample_rate_hz": 16000,
            }
        ),
        endpoints=(
            endpoints
            if endpoints is not None
            else (
                _endpoint(
                    axis_value=8.0,
                    verdict=DecisionVerdict.PASS,
                    character="1",
                ),
                _endpoint(
                    axis_value=4.0,
                    verdict=DecisionVerdict.FAIL,
                    character="2",
                ),
            )
        ),
    )


def test_builds_canonical_observed_boundary():
    bundle = _build()

    assert bundle.payload["schema_version"] == (
        OBSERVED_BOUNDARY_SCHEMA_VERSION
    )
    assert bundle.payload["type"] == "observed_boundary"
    assert bundle.payload["boundary"] == {
        "key": "hetren.asr.observed-boundary",
        "version": "1.0.0",
        "status": "bracketed",
        "direction": "fail_to_pass",
    }
    assert bundle.payload["axis"]["interval"] == {
        "lower": 4.0,
        "upper": 8.0,
        "width": 4.0,
    }
    assert [
        endpoint["position"]
        for endpoint in bundle.payload["endpoints"]
    ] == ["lower", "upper"]
    assert verify_observed_boundary_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_boundary_is_deterministic_across_endpoint_and_key_order():
    passing = _endpoint(
        axis_value=8.0,
        verdict=DecisionVerdict.PASS,
        character="1",
    )
    failing = _endpoint(
        axis_value=4.0,
        verdict=DecisionVerdict.FAIL,
        character="2",
    )

    first = _build(
        endpoints=(passing, failing),
        invariants={
            "codec": "pcm-s16le",
            "sample_rate_hz": 16000,
        },
    )
    second = _build(
        endpoints=(failing, passing),
        invariants={
            "sample_rate_hz": 16000,
            "codec": "pcm-s16le",
        },
    )

    assert first == second


def test_boundary_direction_reports_pass_to_fail():
    bundle = _build(
        endpoints=(
            _endpoint(
                axis_value=1.0,
                verdict=DecisionVerdict.PASS,
                character="1",
            ),
            _endpoint(
                axis_value=2.0,
                verdict=DecisionVerdict.FAIL,
                character="2",
            ),
        )
    )

    assert (
        bundle.payload["boundary"]["direction"]
        == "pass_to_fail"
    )


def test_builder_detaches_mutable_invariant_input():
    invariants = {
        "codec": "pcm-s16le",
        "sample_rate_hz": 16000,
    }
    bundle = _build(invariants=invariants)

    invariants["sample_rate_hz"] = 8000

    assert (
        bundle.payload["invariants"]["parameters"]
        ["sample_rate_hz"]
        == 16000
    )


def test_failing_endpoint_requires_counterexample_evidence():
    with pytest.raises(
        HveeContractError,
        match="counterexample evidence SHA-256",
    ):
        ObservedBoundaryEndpoint(
            axis_value=4.0,
            scenario_sha256=_sha("1"),
            verdict=DecisionVerdict.FAIL,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        )


def test_passing_endpoint_rejects_counterexample_evidence():
    with pytest.raises(
        HveeContractError,
        match="passing boundary endpoints",
    ):
        ObservedBoundaryEndpoint(
            axis_value=8.0,
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
def test_endpoint_rejects_non_binary_verdict(verdict):
    with pytest.raises(
        HveeContractError,
        match="pass or fail verdicts",
    ):
        ObservedBoundaryEndpoint(
            axis_value=4.0,
            scenario_sha256=_sha("1"),
            verdict=verdict,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        float("nan"),
        float("inf"),
        float("-inf"),
        "4.0",
    ],
)
def test_endpoint_rejects_invalid_axis_value(value):
    with pytest.raises(
        HveeContractError,
        match="finite numbers",
    ):
        _endpoint(
            axis_value=value,
            verdict=DecisionVerdict.FAIL,
            character="1",
        )


def test_boundary_requires_two_distinct_axis_values():
    with pytest.raises(
        HveeContractError,
        match="distinct axis values",
    ):
        _build(
            endpoints=(
                _endpoint(
                    axis_value=4.0,
                    verdict=DecisionVerdict.PASS,
                    character="1",
                ),
                _endpoint(
                    axis_value=4.0,
                    verdict=DecisionVerdict.FAIL,
                    character="2",
                ),
            )
        )


def test_boundary_requires_opposing_verdicts():
    with pytest.raises(
        HveeContractError,
        match="different verdicts",
    ):
        _build(
            endpoints=(
                _endpoint(
                    axis_value=4.0,
                    verdict=DecisionVerdict.PASS,
                    character="1",
                ),
                _endpoint(
                    axis_value=8.0,
                    verdict=DecisionVerdict.PASS,
                    character="2",
                ),
            )
        )


def test_boundary_requires_distinct_scenario_identities():
    with pytest.raises(
        HveeContractError,
        match="distinct scenarios",
    ):
        _build(
            endpoints=(
                _endpoint(
                    axis_value=4.0,
                    verdict=DecisionVerdict.FAIL,
                    character="1",
                ),
                _endpoint(
                    axis_value=8.0,
                    verdict=DecisionVerdict.PASS,
                    character="1",
                ),
            )
        )


def test_boundary_rejects_non_finite_interval_width():
    with pytest.raises(
        HveeContractError,
        match="width must be finite",
    ):
        _build(
            endpoints=(
                _endpoint(
                    axis_value=-1e308,
                    verdict=DecisionVerdict.PASS,
                    character="1",
                ),
                _endpoint(
                    axis_value=1e308,
                    verdict=DecisionVerdict.FAIL,
                    character="2",
                ),
            )
        )


def test_verifier_rejects_endpoint_tampering():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["endpoints"][0]["axis_value"] = 3.0

    assert not verify_observed_boundary_bundle(
        payload=tampered,
        expected_sha256=bundle.sha256,
    )


def test_verifier_rejects_recomputed_direction_tampering():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["boundary"]["direction"] = "pass_to_fail"
    recomputed = calculate_observed_boundary_sha256(tampered)

    assert not verify_observed_boundary_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_recomputed_invariant_digest_tampering():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["invariants"]["sha256"] = _sha("e")
    recomputed = calculate_observed_boundary_sha256(tampered)

    assert not verify_observed_boundary_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_extra_fields():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["estimated_boundary"] = 6.0
    recomputed = calculate_observed_boundary_sha256(tampered)

    assert not verify_observed_boundary_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_evidence_boundary_explicitly_limits_claims():
    boundary = _build().payload["evidence_boundary"]

    assert boundary == {
        "observed_endpoint_count": 2,
        "unobserved_values_evaluated": False,
        "interpolation_claimed": False,
        "causal_boundary_claimed": False,
        "minimality_claimed": False,
        "qualification_authority": False,
    }
