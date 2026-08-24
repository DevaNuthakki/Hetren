from copy import deepcopy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.counterexample_evidence import (
    COUNTEREXAMPLE_EVIDENCE_SCHEMA_VERSION,
    CounterexampleFailure,
    build_counterexample_evidence_bundle,
    calculate_counterexample_evidence_sha256,
    calculate_scenario_sha256,
    verify_counterexample_evidence_bundle,
)


def _sha(character: str) -> str:
    return character * 64


def _failure(
    *,
    key: str = "asr.numeric-fidelity",
    reason_code: str = "required-token-missing",
) -> CounterexampleFailure:
    return CounterexampleFailure(
        key=key,
        version="1.0.0",
        reason_code=reason_code,
        metric_key="asr.missing-numeric-token-count",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.numeric-preservation",
        evaluator_version="1.0.0",
    )


def _build(
    *,
    parameters: dict[str, object] | None = None,
    failures: tuple[CounterexampleFailure, ...] | None = None,
):
    return build_counterexample_evidence_bundle(
        evaluation_type="asr",
        scenario_key="hetren.asr.noise-search",
        scenario_version="1.0.0",
        case_id="account-number-01",
        parameters=(
            parameters
            if parameters is not None
            else {
                "noise_kind": "babble",
                "snr_db": 4.0,
            }
        ),
        result_provenance_sha256=_sha("a"),
        observation_evidence_sha256=_sha("b"),
        decision_evidence_sha256=_sha("c"),
        failures=(
            failures
            if failures is not None
            else (_failure(),)
        ),
    )


def test_builds_verifiable_canonical_counterexample_evidence():
    bundle = _build()

    assert bundle.payload["schema_version"] == (
        COUNTEREXAMPLE_EVIDENCE_SCHEMA_VERSION
    )
    assert bundle.payload["type"] == "counterexample_evidence"
    assert bundle.payload["decision"] == {
        "verdict": "fail",
        "evidence_sha256": _sha("c"),
    }
    assert bundle.payload["scenario"]["sha256"] == (
        bundle.scenario_sha256
    )
    assert verify_counterexample_evidence_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_counterexample_is_deterministic_across_input_order():
    first_failure = _failure()
    second_failure = _failure(
        key="asr.exact-match",
        reason_code="normalized-mismatch",
    )

    first = _build(
        parameters={
            "snr_db": 4,
            "noise_kind": "babble",
        },
        failures=(
            first_failure,
            second_failure,
        ),
    )
    second = _build(
        parameters={
            "noise_kind": "babble",
            "snr_db": 4,
        },
        failures=(
            second_failure,
            first_failure,
        ),
    )

    assert first == second
    assert [
        failure["key"]
        for failure in first.payload["failures"]
    ] == [
        "asr.exact-match",
        "asr.numeric-fidelity",
    ]


def test_scenario_identity_is_independently_reproducible():
    bundle = _build()
    scenario = bundle.payload["scenario"]

    assert bundle.scenario_sha256 == calculate_scenario_sha256(
        scenario_key=scenario["key"],
        scenario_version=scenario["version"],
        case_id=scenario["case_id"],
        parameters=scenario["parameters"],
    )


def test_builder_detaches_mutable_parameter_input():
    parameters = {
        "noise_kind": "babble",
        "snr_db": 4.0,
    }
    bundle = _build(parameters=parameters)

    parameters["snr_db"] = 99.0

    assert bundle.payload["scenario"]["parameters"]["snr_db"] == 4.0
    assert verify_counterexample_evidence_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


@pytest.mark.parametrize(
    "parameters",
    [
        {"Bad Key": 1},
        {"snr_db": float("nan")},
        {"snr_db": float("inf")},
        {"nested": {"value": 1}},
        {"sequence": [1, 2]},
        {"label": " surrounding "},
        {"label": ""},
    ],
)
def test_rejects_noncanonical_scenario_parameters(parameters):
    with pytest.raises(HveeContractError):
        _build(parameters=parameters)


def test_rejects_duplicate_failure_identity():
    duplicate = _failure()

    with pytest.raises(
        HveeContractError,
        match="identities must be unique",
    ):
        _build(failures=(duplicate, duplicate))


def test_requires_at_least_one_failure_claim():
    with pytest.raises(
        HveeContractError,
        match="requires failure claims",
    ):
        _build(failures=())


def test_rejects_noncanonical_evidence_digest():
    with pytest.raises(
        HveeContractError,
        match="lowercase SHA-256",
    ):
        build_counterexample_evidence_bundle(
            evaluation_type="asr",
            scenario_key="hetren.asr.noise-search",
            scenario_version="1.0.0",
            case_id="case-01",
            parameters={},
            result_provenance_sha256=_sha("A"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
            failures=(_failure(),),
        )


def test_verifier_rejects_tampered_scenario_parameter():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["scenario"]["parameters"]["snr_db"] = 3.0

    assert not verify_counterexample_evidence_bundle(
        payload=tampered,
        expected_sha256=bundle.sha256,
    )


def test_verifier_rejects_failure_tampering_against_trusted_digest():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["failures"][0]["reason_code"] = "different-reason"

    assert not verify_counterexample_evidence_bundle(
        payload=tampered,
        expected_sha256=bundle.sha256,
    )


def test_verifier_rejects_noncanonical_failure_order():
    first = _failure()
    second = _failure(
        key="asr.exact-match",
        reason_code="normalized-mismatch",
    )
    bundle = _build(failures=(first, second))
    tampered = deepcopy(bundle.payload)
    tampered["failures"].reverse()
    recomputed = calculate_counterexample_evidence_sha256(tampered)

    assert not verify_counterexample_evidence_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_extra_fields():
    bundle = _build()
    tampered = deepcopy(bundle.payload)
    tampered["database_id"] = 42
    recomputed = calculate_counterexample_evidence_sha256(tampered)

    assert not verify_counterexample_evidence_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_payload_excludes_local_identity_and_raw_content_fields():
    serialized = str(_build().payload).lower()

    for forbidden in (
        "evaluation_run_id",
        "test_case_id",
        "result_id",
        "created_at",
        "audio_file_path",
        "reference_transcript",
        "generated_transcript",
    ):
        assert forbidden not in serialized


def test_evidence_boundary_does_not_overclaim():
    boundary = _build().payload["evidence_boundary"]

    assert boundary == {
        "observed_failure": True,
        "causal_explanation_claimed": False,
        "minimality_claimed": False,
        "neighborhood_explored": False,
        "contract_promoted": False,
        "qualification_authority": False,
    }
