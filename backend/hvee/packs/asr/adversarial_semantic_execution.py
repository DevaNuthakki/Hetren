"""Pure semantic-evaluator orchestration for adversarial ASR evaluation.

This module is intentionally thin. It invokes the existing versioned
Critical Number, Critical Identifier, and optionally Critical Terminology
evaluators, then returns their canonical Observation families.

It does not:
- execute an ASR provider,
- read audio,
- infer acoustic conditions,
- duplicate evaluator methodology,
- persist evidence,
- calculate qualification thresholds,
- issue certification, or
- modify release authority.
"""

from __future__ import annotations

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_execution_evidence import (
    ASRAdversarialSemanticObservations,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
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
    build_critical_terminology_fidelity_observations,
    evaluate_critical_terminology_fidelity,
)


def evaluate_asr_adversarial_semantics(
    *,
    reference_text: str,
    generated_text: str,
    terminology: ASRAdversarialTerminologyBinding,
) -> ASRAdversarialSemanticObservations:
    """Execute the existing semantic evaluators for one transcript pair.

    Number and Identifier are deliberately pinned to their canonical en-US
    profiles. Critical Terminology executes only when an exact terminology
    profile is configured.

    The returned object contains evaluator-produced observations only. This
    orchestration function does not reinterpret their values or outcomes.
    """

    if not isinstance(reference_text, str):
        raise HveeContractError(
            "adversarial semantic execution requires "
            "a string reference transcript"
        )

    if not isinstance(generated_text, str):
        raise HveeContractError(
            "adversarial semantic execution requires "
            "a string generated transcript"
        )

    if not isinstance(
        terminology,
        ASRAdversarialTerminologyBinding,
    ):
        raise HveeContractError(
            "adversarial semantic execution requires "
            "terminology configuration"
        )

    number_evaluation = (
        evaluate_critical_number_fidelity(
            reference_text=reference_text,
            generated_text=generated_text,
            profile=EN_US_CRITICAL_NUMBER_PROFILE,
        )
    )

    number_observations = (
        build_critical_number_fidelity_observations(
            number_evaluation
        )
    )

    identifier_evaluation = (
        evaluate_critical_identifier_fidelity(
            reference_text=reference_text,
            generated_text=generated_text,
            profile=(
                EN_US_CRITICAL_IDENTIFIER_PROFILE
            ),
        )
    )

    identifier_observations = (
        build_critical_identifier_fidelity_observations(
            identifier_evaluation
        )
    )

    if (
        terminology.state
        == ASRAdversarialTerminologyState.CONFIGURED
    ):
        profile = terminology.profile

        if profile is None:
            # ASRAdversarialTerminologyBinding already enforces this.
            # Keep this defensive check so orchestration itself fails closed
            # if the contract is ever changed incorrectly.
            raise HveeContractError(
                "configured adversarial terminology "
                "requires an exact profile"
            )

        terminology_evaluation = (
            evaluate_critical_terminology_fidelity(
                reference_text=reference_text,
                generated_text=generated_text,
                profile=profile,
            )
        )

        terminology_observations = (
            build_critical_terminology_fidelity_observations(
                terminology_evaluation,
                profile=profile,
            )
        )
    else:
        terminology_observations = ()

    return ASRAdversarialSemanticObservations(
        critical_number=number_observations,
        critical_identifier=(
            identifier_observations
        ),
        critical_terminology=(
            terminology_observations
        ),
    )
