from copy import deepcopy

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.observation_evidence import (
    OBSERVATION_EVIDENCE_SCHEMA_VERSION,
    ObservationEvidenceRecord,
    build_observation_evidence_bundle,
    calculate_observation_evidence_sha256,
    verify_observation_evidence_bundle,
)


def record(
    *,
    metric_key: str,
    value_type: MetricValueType,
    value: object,
    status: ObservationStatus = (
        ObservationStatus.SUCCESS
    ),
    status_detail: str | None = None,
) -> ObservationEvidenceRecord:
    return ObservationEvidenceRecord(
        metric_key=metric_key,
        metric_version="1.0.0",
        evaluator_key=(
            "hetren.asr.test-evaluator"
        ),
        evaluator_version="1.0.0",
        evaluation_type="asr",
        scope="test_case",
        evaluation_run_id=11,
        test_case_id=22,
        status=status,
        value_type=value_type,
        value=value,
        status_detail=status_detail,
    )


def test_builds_canonical_observation_evidence_bundle():
    bundle = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.z-last",
                value_type=(
                    MetricValueType.BOOLEAN
                ),
                value=False,
            ),
            record(
                metric_key="asr.a-first",
                value_type=(
                    MetricValueType.NUMBER
                ),
                value=0.125,
            ),
        ]
    )

    assert bundle["schema_version"] == (
        OBSERVATION_EVIDENCE_SCHEMA_VERSION
    )
    assert bundle["count"] == 2

    observations = bundle[
        "observations"
    ]

    assert [
        observation["metric"]["key"]
        for observation in observations
    ] == [
        "asr.a-first",
        "asr.z-last",
    ]

    assert (
        len(bundle["sha256"])
        == 64
    )

    assert verify_observation_evidence_bundle(
        bundle
    )


def test_bundle_is_deterministic_across_input_order():
    first_record = record(
        metric_key="asr.first",
        value_type=MetricValueType.INTEGER,
        value=2,
    )
    second_record = record(
        metric_key="asr.second",
        value_type=MetricValueType.BOOLEAN,
        value=True,
    )

    first = build_observation_evidence_bundle(
        [
            first_record,
            second_record,
        ]
    )
    second = build_observation_evidence_bundle(
        [
            second_record,
            first_record,
        ]
    )

    assert first == second


def test_number_values_have_canonical_float_representation():
    bundle = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.number",
                value_type=MetricValueType.NUMBER,
                value=1,
            )
        ]
    )

    value = bundle["observations"][0][
        "value"
    ]

    assert value == 1.0
    assert isinstance(value, float)


def test_json_values_are_canonicalized():
    first = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.json",
                value_type=MetricValueType.JSON,
                value={
                    "z": 2,
                    "a": {
                        "y": 1,
                        "x": 0,
                    },
                },
            )
        ]
    )

    second = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.json",
                value_type=MetricValueType.JSON,
                value={
                    "a": {
                        "x": 0,
                        "y": 1,
                    },
                    "z": 2,
                },
            )
        ]
    )

    assert first == second


def test_non_success_record_requires_no_value_and_detail():
    valid = record(
        metric_key="asr.failed",
        value_type=MetricValueType.NUMBER,
        value=None,
        status=ObservationStatus.FAILED,
        status_detail="evaluator failure",
    )

    bundle = build_observation_evidence_bundle(
        [valid]
    )

    observation = bundle[
        "observations"
    ][0]

    assert observation["value"] is None
    assert (
        observation["status_detail"]
        == "evaluator failure"
    )
    assert verify_observation_evidence_bundle(
        bundle
    )

    with pytest.raises(
        HveeContractError,
        match="cannot contain a value",
    ):
        record(
            metric_key="asr.failed-value",
            value_type=MetricValueType.NUMBER,
            value=0.5,
            status=ObservationStatus.FAILED,
            status_detail="failure",
        )

    with pytest.raises(
        HveeContractError,
        match="requires status detail",
    ):
        record(
            metric_key="asr.failed-detail",
            value_type=MetricValueType.NUMBER,
            value=None,
            status=ObservationStatus.FAILED,
            status_detail=None,
        )


def test_scope_target_contract_is_enforced():
    with pytest.raises(
        HveeContractError,
        match="cannot target a test case",
    ):
        ObservationEvidenceRecord(
            metric_key="asr.run",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.test",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            scope="run",
            evaluation_run_id=1,
            test_case_id=2,
            status=ObservationStatus.SUCCESS,
            value_type=MetricValueType.INTEGER,
            value=1,
        )

    with pytest.raises(
        HveeContractError,
        match="test case id",
    ):
        ObservationEvidenceRecord(
            metric_key="asr.case",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.test",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            scope="test_case",
            evaluation_run_id=1,
            test_case_id=None,
            status=ObservationStatus.SUCCESS,
            value_type=MetricValueType.INTEGER,
            value=1,
        )


def test_duplicate_observation_identity_is_rejected():
    duplicate = record(
        metric_key="asr.duplicate",
        value_type=MetricValueType.INTEGER,
        value=1,
    )

    with pytest.raises(
        HveeContractError,
        match="duplicate identities",
    ):
        build_observation_evidence_bundle(
            [
                duplicate,
                duplicate,
            ]
        )


def test_verifier_rejects_value_tampering():
    bundle = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.number",
                value_type=MetricValueType.NUMBER,
                value=0.125,
            )
        ]
    )

    tampered = deepcopy(bundle)
    tampered["observations"][0][
        "value"
    ] = 0.5

    assert not verify_observation_evidence_bundle(
        tampered
    )


def test_verifier_rejects_identity_tampering():
    bundle = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.original",
                value_type=MetricValueType.INTEGER,
                value=1,
            )
        ]
    )

    tampered = deepcopy(bundle)
    tampered["observations"][0][
        "metric"
    ]["key"] = "asr.tampered"

    assert not verify_observation_evidence_bundle(
        tampered
    )


def test_verifier_rejects_count_tampering():
    bundle = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.count",
                value_type=MetricValueType.INTEGER,
                value=1,
            )
        ]
    )

    tampered = deepcopy(bundle)
    tampered["count"] = 2

    assert not verify_observation_evidence_bundle(
        tampered
    )


def test_verifier_rejects_noncanonical_order_even_with_recomputed_digest():
    bundle = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.first",
                value_type=MetricValueType.INTEGER,
                value=1,
            ),
            record(
                metric_key="asr.second",
                value_type=MetricValueType.INTEGER,
                value=2,
            ),
        ]
    )

    tampered = deepcopy(bundle)
    tampered["observations"].reverse()

    body = {
        "schema_version": tampered[
            "schema_version"
        ],
        "count": tampered["count"],
        "observations": tampered[
            "observations"
        ],
    }

    tampered["sha256"] = (
        calculate_observation_evidence_sha256(
            body
        )
    )

    assert not verify_observation_evidence_bundle(
        tampered
    )


def test_verifier_rejects_extra_fields_even_with_recomputed_digest():
    bundle = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.strict",
                value_type=MetricValueType.BOOLEAN,
                value=True,
            )
        ]
    )

    tampered = deepcopy(bundle)
    tampered["observations"][0][
        "database_id"
    ] = 999

    body = {
        "schema_version": tampered[
            "schema_version"
        ],
        "count": tampered["count"],
        "observations": tampered[
            "observations"
        ],
    }

    tampered["sha256"] = (
        calculate_observation_evidence_sha256(
            body
        )
    )

    assert not verify_observation_evidence_bundle(
        tampered
    )


@pytest.mark.parametrize(
    ("value_type", "value"),
    [
        (MetricValueType.NUMBER, float("nan")),
        (MetricValueType.NUMBER, float("inf")),
        (MetricValueType.INTEGER, True),
        (MetricValueType.BOOLEAN, 1),
        (MetricValueType.STRING, 123),
        (MetricValueType.JSON, None),
    ],
)
def test_record_rejects_invalid_typed_values(
    value_type,
    value,
):
    with pytest.raises(
        HveeContractError
    ):
        record(
            metric_key="asr.invalid-value",
            value_type=value_type,
            value=value,
        )


def test_bundle_contains_no_database_registry_ids_or_timestamps():
    bundle = build_observation_evidence_bundle(
        [
            record(
                metric_key="asr.portable",
                value_type=MetricValueType.INTEGER,
                value=7,
            )
        ]
    )

    serialized = str(bundle)

    assert "metric_definition_id" not in serialized
    assert "evaluator_version_id" not in serialized
    assert "created_at" not in serialized
    assert "observation_id" not in serialized
