import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    verify_critical_number_assurance_profile_v1,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
    EN_US_CRITICAL_NUMBER_PROFILE,
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberReasonCode,
    ASRCriticalNumberType,
    build_critical_number_fidelity_observations,
    evaluate_critical_number_fidelity,
)
from hvee.core.contracts import EvaluatorVersion


def _evaluate(generated_text, evaluator):
    return evaluate_critical_number_fidelity(
        reference_text="meet at nine fifteen AM tomorrow",
        generated_text=generated_text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
        evaluator=evaluator,
    )


def test_evaluator_v1_and_v1_1_have_distinct_exact_identities():
    assert CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.key == (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.key
    )
    assert CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.version == "1.0.0"
    assert CRITICAL_NUMBER_FIDELITY_EVALUATOR.version == "1.1.0"
    assert (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.evaluation_type
        == CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type
        == "asr"
    )


def test_historical_v1_preserves_colon_clock_semantics():
    evaluation = _evaluate(
        "meet at 9:15 AM tomorrow",
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
    )

    assert evaluation.outcome == ASRCriticalNumberFidelityOutcome.PRESERVED
    assert evaluation.evaluator_version == "1.0.0"
    assert evaluation.generated_entities[0].numeric_type == (
        ASRCriticalNumberType.CLOCK_TIME
    )
    assert evaluation.generated_entities[0].canonical_value == "09:15"


def test_historical_v1_does_not_reinterpret_dot_decimal_as_clock_time():
    evaluation = _evaluate(
        "meet at 9.15 AM tomorrow",
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
    )

    assert evaluation.evaluator_version == "1.0.0"
    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
    )
    assert evaluation.generated_entities[0].numeric_type == (
        ASRCriticalNumberType.CARDINAL_DECIMAL
    )
    assert any(
        finding.reason_code
        == ASRCriticalNumberReasonCode.TYPE_SUBSTITUTION
        for finding in evaluation.findings
    )


def test_evaluator_v1_1_interprets_explicit_meridiem_dot_time():
    evaluation = _evaluate(
        "meet at 9.15 AM tomorrow",
        CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    )

    assert evaluation.evaluator_version == "1.1.0"
    assert evaluation.outcome == ASRCriticalNumberFidelityOutcome.PRESERVED
    assert evaluation.generated_entities[0].numeric_type == (
        ASRCriticalNumberType.CLOCK_TIME
    )
    assert evaluation.generated_entities[0].canonical_value == "09:15"


def test_observations_preserve_selected_evaluator_identity():
    historical = build_critical_number_fidelity_observations(
        _evaluate(
            "meet at 9:15 AM tomorrow",
            CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
        )
    )

    current = build_critical_number_fidelity_observations(
        _evaluate(
            "meet at 9.15 AM tomorrow",
            CRITICAL_NUMBER_FIDELITY_EVALUATOR,
        )
    )

    assert {
        observation.evaluator_version
        for observation in historical
    } == {"1.0.0"}

    assert {
        observation.evaluator_version
        for observation in current
    } == {"1.1.0"}


def test_unknown_evaluator_identity_fails_closed():
    unsupported = EvaluatorVersion(
        key=CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        version="9.9.9",
        evaluation_type="asr",
        description="Unsupported test evaluator.",
    )

    with pytest.raises(
        HveeContractError,
        match="evaluator identity is unsupported",
    ):
        _evaluate(
            "meet at 9:15 AM tomorrow",
            unsupported,
        )


def test_historical_assurance_v1_rebuilds_original_sealed_digest():
    evidence = verify_critical_number_assurance_profile_v1()

    assert evidence.sha256 == (
        CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
    )

    assert evidence.sha256 == (
        "e8459e209a022883007f5c6f72972c43"
        "f48758c0c6442e0d4d31d4ad20c24a72"
    )

    bindings = evidence.payload["bindings"]

    assert bindings["evaluator"]["version"] == "1.0.0"
