from __future__ import annotations

import pytest

from hvee.core.contracts import (
    HveeContractError,
    ObservationStatus,
)
from hvee.packs.asr.adversarial_execution_evidence import (
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
)
from hvee.packs.asr.adversarial_semantic_execution import (
    evaluate_asr_adversarial_semantics,
)
from hvee.packs.asr.critical_identifier_fidelity import (
    EN_US_CRITICAL_IDENTIFIER_PROFILE,
    build_critical_identifier_fidelity_observations,
    evaluate_critical_identifier_fidelity,
)
from hvee.packs.asr.critical_number_fidelity import (
    EN_US_CRITICAL_NUMBER_PROFILE,
    build_critical_number_fidelity_observations,
    evaluate_critical_number_fidelity,
)
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
    ASRCriticalTerminologyProfile,
    ASRCriticalTerminologyTerm,
    build_critical_terminology_fidelity_observations,
    calculate_critical_terminology_vocabulary_sha256,
    evaluate_critical_terminology_fidelity,
)


REFERENCE = (
    "Administer Cardiovex 250 mg "
    "using confirmation code AB-123."
)

GENERATED = (
    "Administer Cardiovex 250 mg "
    "using confirmation code AB-123."
)


def _profile() -> ASRCriticalTerminologyProfile:
    return ASRCriticalTerminologyProfile(
        key="qualification.terminology-profile",
        version="1.0.0",
        language="en",
        locale="en-US",
        terms=(
            ASRCriticalTerminologyTerm(
                term_key="medication.cardiovex",
                canonical_text="Cardiovex",
                accepted_surfaces=(
                    "Cardiovex",
                ),
            ),
        ),
    )


def _configured() -> ASRAdversarialTerminologyBinding:
    return ASRAdversarialTerminologyBinding(
        state=(
            ASRAdversarialTerminologyState.CONFIGURED
        ),
        profile=_profile(),
    )


def _not_configured() -> (
    ASRAdversarialTerminologyBinding
):
    return ASRAdversarialTerminologyBinding(
        state=(
            ASRAdversarialTerminologyState
            .NOT_CONFIGURED
        ),
    )


def test_configured_execution_returns_exact_family_sizes():
    result = evaluate_asr_adversarial_semantics(
        reference_text=REFERENCE,
        generated_text=GENERATED,
        terminology=_configured(),
    )

    assert len(result.critical_number) == 10
    assert len(result.critical_identifier) == 11
    assert len(result.critical_terminology) == 11


def test_not_configured_execution_skips_terminology():
    result = evaluate_asr_adversarial_semantics(
        reference_text=REFERENCE,
        generated_text=GENERATED,
        terminology=_not_configured(),
    )

    assert len(result.critical_number) == 10
    assert len(result.critical_identifier) == 11
    assert result.critical_terminology == ()


def test_orchestrator_matches_direct_number_evaluator_output():
    expected = (
        build_critical_number_fidelity_observations(
            evaluate_critical_number_fidelity(
                reference_text=REFERENCE,
                generated_text=GENERATED,
                profile=(
                    EN_US_CRITICAL_NUMBER_PROFILE
                ),
            )
        )
    )

    result = evaluate_asr_adversarial_semantics(
        reference_text=REFERENCE,
        generated_text=GENERATED,
        terminology=_not_configured(),
    )

    assert result.critical_number == expected


def test_orchestrator_matches_direct_identifier_evaluator_output():
    expected = (
        build_critical_identifier_fidelity_observations(
            evaluate_critical_identifier_fidelity(
                reference_text=REFERENCE,
                generated_text=GENERATED,
                profile=(
                    EN_US_CRITICAL_IDENTIFIER_PROFILE
                ),
            )
        )
    )

    result = evaluate_asr_adversarial_semantics(
        reference_text=REFERENCE,
        generated_text=GENERATED,
        terminology=_not_configured(),
    )

    assert result.critical_identifier == expected


def test_orchestrator_matches_direct_terminology_evaluator_output():
    profile = _profile()

    expected = (
        build_critical_terminology_fidelity_observations(
            evaluate_critical_terminology_fidelity(
                reference_text=REFERENCE,
                generated_text=GENERATED,
                profile=profile,
            ),
            profile=profile,
        )
    )

    result = evaluate_asr_adversarial_semantics(
        reference_text=REFERENCE,
        generated_text=GENERATED,
        terminology=(
            ASRAdversarialTerminologyBinding(
                state=(
                    ASRAdversarialTerminologyState
                    .CONFIGURED
                ),
                profile=profile,
            )
        ),
    )

    assert result.critical_terminology == expected


def test_configured_terminology_retains_exact_vocabulary_sha():
    profile = _profile()

    result = evaluate_asr_adversarial_semantics(
        reference_text=REFERENCE,
        generated_text=GENERATED,
        terminology=(
            ASRAdversarialTerminologyBinding(
                state=(
                    ASRAdversarialTerminologyState
                    .CONFIGURED
                ),
                profile=profile,
            )
        ),
    )

    observation = next(
        observation
        for observation
        in result.critical_terminology
        if observation.metric_key
        == (
            CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC.key
        )
    )

    assert (
        observation.status
        == ObservationStatus.SUCCESS
    )

    assert observation.value == (
        calculate_critical_terminology_vocabulary_sha256(
            profile
        )
    )


def test_orchestration_does_not_reinterpret_evaluator_outcomes():
    result = evaluate_asr_adversarial_semantics(
        reference_text=(
            "Administer Cardiovex 250 mg."
        ),
        generated_text=(
            "Administer Cardiovex 500 mg."
        ),
        terminology=_configured(),
    )

    preserved = next(
        observation
        for observation
        in result.critical_number
        if observation.metric_key
        == "asr.critical-number.preserved.en-us"
    )

    assert preserved.status == (
        ObservationStatus.SUCCESS
    )
    assert preserved.value is False


@pytest.mark.parametrize(
    ("reference_text", "generated_text"),
    [
        (None, "generated"),
        ("reference", None),
        (123, "generated"),
        ("reference", 123),
    ],
)
def test_rejects_non_string_transcripts(
    reference_text,
    generated_text,
):
    with pytest.raises(
        HveeContractError,
        match="string .* transcript",
    ):
        evaluate_asr_adversarial_semantics(
            reference_text=reference_text,
            generated_text=generated_text,
            terminology=_not_configured(),
        )


def test_rejects_invalid_terminology_configuration():
    with pytest.raises(
        HveeContractError,
        match="terminology configuration",
    ):
        evaluate_asr_adversarial_semantics(
            reference_text=REFERENCE,
            generated_text=GENERATED,
            terminology=None,
        )


def test_adversarial_semantic_execution_is_publicly_exported():
    import hvee.packs.asr as asr

    assert hasattr(
        asr,
        "evaluate_asr_adversarial_semantics",
    )
    assert (
        "evaluate_asr_adversarial_semantics"
        in asr.__all__
    )
