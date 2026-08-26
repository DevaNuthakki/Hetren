from dataclasses import replace

import pytest

from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_PRESERVED_METRIC,
)
from hvee.packs.asr.reliability_profile import (
    ASR_RELIABILITY_PROFILE_KEY,
    ASR_RELIABILITY_PROFILE_V1,
    ASR_RELIABILITY_PROFILE_V1_SHA256,
    ASR_RELIABILITY_PROFILE_V1_1,
    ASR_RELIABILITY_PROFILE_V1_1_SHA256,
    ASR_RELIABILITY_PROFILE_V1_1_VERSION,
    ASRReliabilityProfileError,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
    build_asr_reliability_profile_v1,
    build_asr_reliability_profile_v1_1,
    verify_asr_reliability_profile_v1,
    verify_asr_reliability_profile_v1_1,
)


EXPECTED_V1_SHA256 = (
    "fcfb829b4e598ffe2be35776a31c2d8a"
    "f98f68537888daddfc3a8a7c8413fdf3"
)

EXPECTED_V1_1_SHA256 = (
    "74af95a1ecaaf1f227872110b7e4c25b"
    "b848c68fdd2044dd55ef8df4340ddfc9"
)


def _critical_number_binding(profile):
    return profile.binding_for(
        metric_key=CRITICAL_NUMBER_PRESERVED_METRIC.key,
        metric_version=CRITICAL_NUMBER_PRESERVED_METRIC.version,
    )


def test_profile_1_1_has_exact_frozen_identity():
    assert ASR_RELIABILITY_PROFILE_V1_1.key == (
        ASR_RELIABILITY_PROFILE_KEY
    )
    assert ASR_RELIABILITY_PROFILE_V1_1_VERSION == "1.1.0"
    assert ASR_RELIABILITY_PROFILE_V1_1.version == "1.1.0"
    assert (
        ASR_RELIABILITY_PROFILE_V1_1_SHA256
        == EXPECTED_V1_1_SHA256
    )
    assert (
        ASR_RELIABILITY_PROFILE_V1_1.sha256
        == EXPECTED_V1_1_SHA256
    )


def test_profile_1_1_build_is_deterministic_and_verifiable():
    first = build_asr_reliability_profile_v1_1()
    second = build_asr_reliability_profile_v1_1()

    assert first is not ASR_RELIABILITY_PROFILE_V1_1
    assert first.payload == second.payload
    assert first.payload == ASR_RELIABILITY_PROFILE_V1_1.payload
    assert first.sha256 == second.sha256
    assert first.sha256 == EXPECTED_V1_1_SHA256

    assert verify_asr_reliability_profile_v1_1(first) is first


def test_profile_1_1_binds_live_critical_number_evaluator():
    historical = _critical_number_binding(
        ASR_RELIABILITY_PROFILE_V1
    )
    current = _critical_number_binding(
        ASR_RELIABILITY_PROFILE_V1_1
    )

    assert historical.evaluator == (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1
    )
    assert historical.evaluator.version == "1.0.0"

    assert current.evaluator == CRITICAL_NUMBER_FIDELITY_EVALUATOR
    assert current.evaluator.version == "1.1.0"


def test_profile_1_1_changes_only_profile_and_critical_evaluator_identity():
    historical = ASR_RELIABILITY_PROFILE_V1
    current = ASR_RELIABILITY_PROFILE_V1_1

    assert len(historical.bindings) == 15
    assert len(current.bindings) == 15

    critical_identity = (
        CRITICAL_NUMBER_PRESERVED_METRIC.key,
        CRITICAL_NUMBER_PRESERVED_METRIC.version,
    )

    changed = 0

    for old, new in zip(
        historical.bindings,
        current.bindings,
        strict=True,
    ):
        assert old.metric_identity == new.metric_identity

        if old.metric_identity == critical_identity:
            changed += 1

            assert old.metric == new.metric
            assert old.axis == new.axis
            assert old.role == new.role
            assert old.aggregation_use == new.aggregation_use
            assert (
                old.comparison_semantics
                == new.comparison_semantics
            )
            assert (
                old.evidence_requirement
                == new.evidence_requirement
            )
            assert old.aggregation_group == new.aggregation_group
            assert old.engineer_label == new.engineer_label
            assert (
                old.engineer_interpretation
                == new.engineer_interpretation
            )
            assert old.evaluator.key == new.evaluator.key
            assert (
                old.evaluator.evaluation_type
                == new.evaluator.evaluation_type
            )
            assert old.evaluator.version == "1.0.0"
            assert new.evaluator.version == "1.1.0"
        else:
            assert old == new

    assert changed == 1

    assert (
        historical.payload["methodology"]
        == current.payload["methodology"]
    )
    assert historical.payload["axes"] == current.payload["axes"]
    assert (
        historical.payload["evidence_boundary"]
        == current.payload["evidence_boundary"]
    )


def test_profile_verifiers_are_identity_specific():
    assert (
        verify_asr_reliability_profile_v1(
            ASR_RELIABILITY_PROFILE_V1
        )
        is ASR_RELIABILITY_PROFILE_V1
    )

    assert (
        verify_asr_reliability_profile_v1_1(
            ASR_RELIABILITY_PROFILE_V1_1
        )
        is ASR_RELIABILITY_PROFILE_V1_1
    )

    with pytest.raises(
        ASRReliabilityProfileError,
        match="unsupported or changed",
    ):
        verify_asr_reliability_profile_v1(
            ASR_RELIABILITY_PROFILE_V1_1
        )

    with pytest.raises(
        ASRReliabilityProfileError,
        match="unsupported or changed",
    ):
        verify_asr_reliability_profile_v1_1(
            ASR_RELIABILITY_PROFILE_V1
        )


def test_profile_1_1_verifier_rejects_tampering():
    changed = replace(
        ASR_RELIABILITY_PROFILE_V1_1,
        version="1.1.1",
    )

    with pytest.raises(
        ASRReliabilityProfileError,
        match="unsupported or changed",
    ):
        verify_asr_reliability_profile_v1_1(changed)


def test_freezing_profile_1_1_does_not_change_historical_v1():
    rebuilt = build_asr_reliability_profile_v1()

    assert ASR_RELIABILITY_PROFILE_V1.version == "1.0.0"
    assert ASR_RELIABILITY_PROFILE_V1_SHA256 == EXPECTED_V1_SHA256
    assert ASR_RELIABILITY_PROFILE_V1.sha256 == EXPECTED_V1_SHA256
    assert rebuilt.sha256 == EXPECTED_V1_SHA256
