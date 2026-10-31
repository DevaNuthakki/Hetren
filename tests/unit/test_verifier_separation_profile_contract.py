from dataclasses import (
    FrozenInstanceError,
    fields,
    replace,
)

import pytest

from packages.contracts import (
    ContractError,
    VerificationOutcome,
    VerificationReport,
    VerifierSeparationAssessment,
    VerifierSeparationDimension,
    VerifierSeparationProfile,
    VerifierSeparationState,
)


ZERO = "0" * 64
ONE = "1" * 64
TWO = "2" * 64
THREE = "3" * 64
FOUR = "4" * 64
FIVE = "5" * 64
SIX = "6" * 64
SEVEN = "7" * 64


SEPARATION_REFERENCES = (
    "separation://evaluator",
    "separation://execution",
    "separation://infrastructure",
    "separation://runtime-environment",
    "separation://test-origin",
)


def make_verification(
    *,
    outcome=VerificationOutcome.VERIFIED,
    independence_references=SEPARATION_REFERENCES,
    evidence_references=(
        "evidence://verification",
    ),
    **overrides,
) -> VerificationReport:
    values = {
        "tenant_id": "tenant-1",
        "project_id": "project-1",
        "verification_id": "verification-1",
        "goal_contract_id": "goal-1",
        "goal_contract_sha256": ZERO,
        "system_snapshot_id": "candidate-1",
        "system_snapshot_sha256": ONE,
        "source_execution_id": "source-execution",
        "source_execution_sha256": TWO,
        "source_evaluation_id": "source-evaluation",
        "source_evaluation_sha256": THREE,
        "verification_execution_id": "verification-execution",
        "verification_execution_sha256": FOUR,
        "verification_evaluation_id": "verification-evaluation",
        "verification_evaluation_sha256": FIVE,
        "verifier_id": "verifier-1",
        "verifier_version": "1",
        "protocol_reference": "protocol://verification/v1",
        "protocol_sha256": SIX,
        "outcome": outcome,
        "independence_references": independence_references,
        "evidence_references": evidence_references,
        "rationale": "separate verification attempt completed",
        "uncertainty": (
            "separation references do not prove independence"
        ),
        "limitations": (
            "bounded verification record only",
        ),
    }

    values.update(
        overrides
    )

    return VerificationReport(
        **values
    )


def assessment(
    dimension,
    state,
    evidence_references=(),
    rationale="categorical separation assessment",
):
    return VerifierSeparationAssessment(
        dimension=dimension,
        state=state,
        evidence_references=evidence_references,
        rationale=rationale,
        limitations=(
            "profile state is profiler-reported",
        ),
    )


def mixed_assessments():
    return (
        assessment(
            VerifierSeparationDimension.EXECUTION_ATTEMPT,
            VerifierSeparationState.SEPARATE,
            (
                "separation://execution",
            ),
        ),
        assessment(
            VerifierSeparationDimension.EVALUATOR,
            VerifierSeparationState.SEPARATE,
            (
                "separation://evaluator",
            ),
        ),
        assessment(
            VerifierSeparationDimension.TEST_OR_EVIDENCE_ORIGIN,
            VerifierSeparationState.SAME,
            (
                "separation://test-origin",
            ),
        ),
        assessment(
            VerifierSeparationDimension.RUNTIME_ENVIRONMENT,
            VerifierSeparationState.SAME,
            (
                "separation://runtime-environment",
            ),
        ),
        assessment(
            VerifierSeparationDimension.INFRASTRUCTURE,
            VerifierSeparationState.SAME,
            (
                "separation://infrastructure",
            ),
        ),
        assessment(
            VerifierSeparationDimension.ORGANIZATION,
            VerifierSeparationState.UNKNOWN,
        ),
    )


def make_profile(
    *,
    verification=None,
    assessments=None,
    **overrides,
):
    if verification is None:
        verification = make_verification()

    if assessments is None:
        assessments = mixed_assessments()

    values = {
        "tenant_id": verification.tenant_id,
        "project_id": verification.project_id,
        "profile_id": "vsp-1",
        "verification_id": verification.verification_id,
        "verification_sha256": (
            verification.verification_sha256
        ),
        "profiler_id": "vsp-profiler",
        "profiler_version": "1",
        "protocol_reference": "protocol://heal/vsp/v1",
        "protocol_sha256": SEVEN,
        "assessments": assessments,
        "rationale": (
            "verification separation described "
            "without an aggregate independence score"
        ),
        "uncertainty": (
            "unknown dimensions remain explicitly unknown"
        ),
        "limitations": (
            "categorical profile does not prove independence",
        ),
    }

    values.update(
        overrides
    )

    return VerifierSeparationProfile(
        **values
    )


def test_dimension_vocabulary_is_exact():
    assert tuple(
        item.value
        for item in VerifierSeparationDimension
    ) == (
        "EXECUTION_ATTEMPT",
        "EVALUATOR",
        "TEST_OR_EVIDENCE_ORIGIN",
        "RUNTIME_ENVIRONMENT",
        "INFRASTRUCTURE",
        "ORGANIZATION",
    )


def test_state_vocabulary_is_exact():
    assert tuple(
        item.value
        for item in VerifierSeparationState
    ) == (
        "SAME",
        "SEPARATE",
        "UNKNOWN",
        "NOT_APPLICABLE",
    )


def test_mixed_profile_validates_against_verification():
    verification = make_verification()

    profile = make_profile(
        verification=verification,
    )

    profile.validate_against(
        verification=verification,
    )

    assert (
        profile.assessments[0].state
        is VerifierSeparationState.SEPARATE
    )

    assert (
        profile.assessments[-1].state
        is VerifierSeparationState.UNKNOWN
    )


def test_profile_hash_is_deterministic_and_state_bound():
    first = make_profile()
    second = make_profile()

    changed_assessments = list(
        mixed_assessments()
    )

    changed_assessments[-1] = assessment(
        VerifierSeparationDimension.ORGANIZATION,
        VerifierSeparationState.NOT_APPLICABLE,
    )

    changed = make_profile(
        assessments=tuple(
            changed_assessments
        )
    )

    assert (
        first.profile_sha256
        == second.profile_sha256
    )

    assert (
        first.profile_sha256
        != changed.profile_sha256
    )


def test_assessment_is_frozen():
    item = mixed_assessments()[0]

    with pytest.raises(
        FrozenInstanceError
    ):
        item.rationale = "changed"


def test_profile_is_frozen():
    profile = make_profile()

    with pytest.raises(
        FrozenInstanceError
    ):
        profile.rationale = "changed"


def test_assessments_must_be_a_tuple():
    with pytest.raises(
        ContractError,
        match="assessments must be a tuple",
    ):
        make_profile(
            assessments=list(
                mixed_assessments()
            ),
        )


def test_assessment_members_must_have_correct_type():
    items = list(
        mixed_assessments()
    )

    items[0] = "not-an-assessment"

    with pytest.raises(
        ContractError,
        match="VerifierSeparationAssessment",
    ):
        make_profile(
            assessments=tuple(
                items
            ),
        )


def test_same_requires_evidence():
    with pytest.raises(
        ContractError,
        match="SAME requires evidence",
    ):
        assessment(
            VerifierSeparationDimension.INFRASTRUCTURE,
            VerifierSeparationState.SAME,
        )


def test_separate_requires_evidence():
    with pytest.raises(
        ContractError,
        match="SEPARATE requires evidence",
    ):
        assessment(
            VerifierSeparationDimension.EVALUATOR,
            VerifierSeparationState.SEPARATE,
        )


def test_unknown_may_preserve_missing_evidence():
    item = assessment(
        VerifierSeparationDimension.ORGANIZATION,
        VerifierSeparationState.UNKNOWN,
    )

    assert item.evidence_references == ()


def test_duplicate_or_missing_dimension_set_is_rejected():
    items = list(
        mixed_assessments()
    )

    items[-1] = assessment(
        VerifierSeparationDimension.INFRASTRUCTURE,
        VerifierSeparationState.SAME,
        (
            "separation://infrastructure",
        ),
    )

    with pytest.raises(
        ContractError,
        match="each required separation dimension exactly once",
    ):
        make_profile(
            assessments=tuple(
                items
            ),
        )


def test_dimension_order_is_canonical():
    items = list(
        mixed_assessments()
    )

    items[0], items[1] = (
        items[1],
        items[0],
    )

    with pytest.raises(
        ContractError,
        match="canonical order",
    ):
        make_profile(
            assessments=tuple(
                items
            ),
        )


def test_profile_evidence_must_be_declared_by_verification_report():
    verification = make_verification(
        independence_references=(
            "separation://execution",
        ),
    )

    profile = make_profile(
        verification=verification,
    )

    with pytest.raises(
        ContractError,
        match="not declared by VerificationReport",
    ):
        profile.validate_against(
            verification=verification,
        )


def test_verification_identity_is_hash_bound():
    verification = make_verification()

    profile = make_profile(
        verification=verification,
    )

    different = replace(
        verification,
        verification_id="verification-2",
    )

    with pytest.raises(
        ContractError,
        match="verification_id",
    ):
        profile.validate_against(
            verification=different,
        )


def test_profile_scope_must_match_verification_scope():
    verification = make_verification()

    profile = make_profile(
        verification=verification,
    )

    different = replace(
        verification,
        project_id="different-project",
    )

    with pytest.raises(
        ContractError,
        match="verification.project_id",
    ):
        profile.validate_against(
            verification=different,
        )


def test_all_unknown_profile_can_describe_blocked_verification():
    blocked = make_verification(
        outcome=VerificationOutcome.BLOCKED,
        independence_references=(),
        evidence_references=(),
    )

    unknown = tuple(
        assessment(
            dimension,
            VerifierSeparationState.UNKNOWN,
        )
        for dimension in (
            VerifierSeparationDimension.EXECUTION_ATTEMPT,
            VerifierSeparationDimension.EVALUATOR,
            VerifierSeparationDimension.TEST_OR_EVIDENCE_ORIGIN,
            VerifierSeparationDimension.RUNTIME_ENVIRONMENT,
            VerifierSeparationDimension.INFRASTRUCTURE,
            VerifierSeparationDimension.ORGANIZATION,
        )
    )

    profile = make_profile(
        verification=blocked,
        assessments=unknown,
    )

    profile.validate_against(
        verification=blocked,
    )


def test_profile_has_no_scalar_independence_or_authority_surface():
    names = {
        field.name
        for field in fields(
            VerifierSeparationProfile
        )
    }

    assert names.isdisjoint(
        {
            "score",
            "independence_score",
            "separation_score",
            "grade",
            "level",
            "percentage",
            "overall_state",
            "independent",
            "is_independent",
            "verified",
            "eligible",
            "authorization",
            "approval",
            "can_deploy",
            "deployment_authority",
            "lifecycle_state",
            "complete",
        }
    )
