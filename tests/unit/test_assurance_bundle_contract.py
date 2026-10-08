from dataclasses import (
    FrozenInstanceError,
    fields,
    replace,
)

import pytest

from packages.contracts import (
    AssuranceBundle,
    AssuranceBundleEvidenceRoleReference,
    ClaimBoundary,
    ClaimBoundaryDemonstration,
    ClaimBoundaryExternalStatus,
    ClaimBoundarySource,
    ContractError,
    EvidenceRole,
    EvidenceRoleAssignment,
    GoalContract,
    RepairContrastOutcome,
    RepairContrastRecord,
    SystemSnapshot,
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
EIGHT = "8" * 64
NINE = "9" * 64
A_SHA = "a" * 64
B_SHA = "b" * 64
C_SHA = "c" * 64
D_SHA = "d" * 64
E_SHA = "e" * 64
F_SHA = "f" * 64


def make_goal():
    return GoalContract(
        tenant_id="tenant-1",
        project_id="project-1",
        contract_id="goal-1",
        contract_version="1",
        system_id="system-1",
        system_version_id="candidate-v1",
        claim_scope="bounded HEAL assurance",
        objective="Assess the registered repair claim",
        metrics=(
            "bounded-correctness",
        ),
        minimum_effect="registered threshold",
        baseline_reference="baseline-1",
        acceptance_predicates=(
            "registered target behavior",
        ),
        hard_constraints=(),
        invariants=(),
        eligible_changes=(
            "configuration",
        ),
        budget_constraints=(
            "bounded evaluation budget",
        ),
        reviewer_version="reviewer-v1",
        evaluator_version="evaluator-v1",
        evidence_requirements=(
            "bounded evidence",
        ),
        protected_evaluation_requirements=(
            "protected outcomes remain isolated",
        ),
        uncertainty_policy="preserve uncertainty",
        failure_invalidity_policy="preserve invalid runs",
        verification_requirements=(
            "separate verification required",
        ),
    )


def make_snapshot():
    return SystemSnapshot(
        tenant_id="tenant-1",
        project_id="project-1",
        snapshot_id="candidate-snapshot",
        system_id="system-1",
        system_version_id="candidate-v1",
        environment_family="controlled-agent",
        component_version_ids=(
            "candidate-v1",
        ),
        provider_binding_ids=(),
        adapter_binding_ids=(),
        evaluator_binding_ids=(
            "evaluator-v1",
        ),
        code_identity=ZERO,
        data_identity=None,
        prompt_identity=ONE,
        runtime_identity="python-3.12",
        state_references=(
            "state://candidate",
        ),
        artifact_references=(),
    )


def make_evidence_assignment(
    *,
    assignment_id="evidence-role-1",
    evidence_reference="evidence://repair-contrast",
    evidence_sha256=TWO,
):
    return EvidenceRoleAssignment(
        tenant_id="tenant-1",
        project_id="project-1",
        assignment_id=assignment_id,
        evidence_reference=evidence_reference,
        evidence_sha256=evidence_sha256,
        qualifier_id="evidence-role-qualifier",
        qualifier_version="1",
        qualification_reference=(
            "protocol://heal/evidence-role/v1"
        ),
        qualification_sha256=THREE,
        roles=(
            EvidenceRole.REPAIR_DISCRIMINATING,
        ),
        rationale="bounded semantic role assignment",
        uncertainty="role assignment does not prove evidence truth",
        limitations=(
            "contract fixture only",
        ),
    )


def make_repair_contrast(
    *,
    goal,
    snapshot,
):
    return RepairContrastRecord(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        contrast_id="repair-contrast-1",
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        known_bad_snapshot_id="known-bad-snapshot",
        known_bad_snapshot_sha256=FOUR,
        candidate_snapshot_id=snapshot.snapshot_id,
        candidate_snapshot_sha256=snapshot.snapshot_sha256,
        known_bad_execution_id="execution-known-bad",
        known_bad_execution_sha256=FIVE,
        known_bad_evaluation_id="evaluation-known-bad",
        known_bad_evaluation_sha256=SIX,
        candidate_execution_id="execution-candidate",
        candidate_execution_sha256=SEVEN,
        candidate_evaluation_id="evaluation-candidate",
        candidate_evaluation_sha256=EIGHT,
        claim_reference="claim://repair/target-v1",
        claim_sha256=NINE,
        comparison_case_reference="fixture://repair-case-v1",
        comparison_case_sha256=A_SHA,
        contrast_qualifier_id="repair-contrast-qualifier",
        contrast_qualifier_version="1",
        contrast_protocol_reference=(
            "protocol://heal/repair-contrast/v1"
        ),
        contrast_protocol_sha256=B_SHA,
        outcome=RepairContrastOutcome.REPAIR_DISCRIMINATING,
        evidence_references=(
            "evidence://candidate",
            "evidence://known-bad",
        ),
        rationale="bounded FAIL to PASS contrast",
        uncertainty="does not establish general repair correctness",
        limitations=(
            "controlled fixture only",
        ),
    )


def make_verification(
    *,
    goal,
    snapshot,
):
    return VerificationReport(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        verification_id="verification-1",
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        system_snapshot_id=snapshot.snapshot_id,
        system_snapshot_sha256=snapshot.snapshot_sha256,
        source_execution_id="source-execution",
        source_execution_sha256=C_SHA,
        source_evaluation_id="source-evaluation",
        source_evaluation_sha256=D_SHA,
        verification_execution_id="verification-execution",
        verification_execution_sha256=E_SHA,
        verification_evaluation_id="verification-evaluation",
        verification_evaluation_sha256=F_SHA,
        verifier_id="verifier-1",
        verifier_version="1",
        protocol_reference="protocol://verification/v1",
        protocol_sha256=TWO,
        outcome=VerificationOutcome.VERIFIED,
        independence_references=(
            "separation://execution",
        ),
        evidence_references=(
            "evidence://verification",
        ),
        rationale="separate bounded verification",
        uncertainty="separation references do not prove independence",
        limitations=(
            "contract fixture only",
        ),
    )


def make_vsp(
    *,
    verification,
):
    dimensions = (
        VerifierSeparationDimension.EXECUTION_ATTEMPT,
        VerifierSeparationDimension.EVALUATOR,
        VerifierSeparationDimension.TEST_OR_EVIDENCE_ORIGIN,
        VerifierSeparationDimension.RUNTIME_ENVIRONMENT,
        VerifierSeparationDimension.INFRASTRUCTURE,
        VerifierSeparationDimension.ORGANIZATION,
    )

    assessments = tuple(
        VerifierSeparationAssessment(
            dimension=dimension,
            state=(
                VerifierSeparationState.SEPARATE
                if dimension
                is VerifierSeparationDimension.EXECUTION_ATTEMPT
                else VerifierSeparationState.UNKNOWN
            ),
            evidence_references=(
                (
                    "separation://execution",
                )
                if dimension
                is VerifierSeparationDimension.EXECUTION_ATTEMPT
                else ()
            ),
            rationale="bounded separation description",
            limitations=(
                "does not prove independence",
            ),
        )
        for dimension in dimensions
    )

    return VerifierSeparationProfile(
        tenant_id=verification.tenant_id,
        project_id=verification.project_id,
        profile_id="vsp-1",
        verification_id=verification.verification_id,
        verification_sha256=verification.verification_sha256,
        profiler_id="vsp-profiler",
        profiler_version="1",
        protocol_reference="protocol://heal/vsp/v1",
        protocol_sha256=THREE,
        assessments=assessments,
        rationale="categorical separation description",
        uncertainty="unsupported dimensions remain unknown",
        limitations=(
            "does not prove independence",
        ),
    )


def make_claim_boundary(
    *,
    goal,
    snapshot,
):
    sources = (
        ClaimBoundarySource(
            reference="artifact://repair-contrast",
            sha256=FOUR,
        ),
        ClaimBoundarySource(
            reference="artifact://verification",
            sha256=FIVE,
        ),
        ClaimBoundarySource(
            reference="artifact://vsp",
            sha256=SIX,
        ),
    )

    return ClaimBoundary(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        boundary_id="claim-boundary-1",
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        system_snapshot_id=snapshot.snapshot_id,
        system_snapshot_sha256=snapshot.snapshot_sha256,
        qualifier_id="claim-boundary-qualifier",
        qualifier_version="1",
        protocol_reference="protocol://heal/claim-boundary/v1",
        protocol_sha256=SEVEN,
        sources=sources,
        demonstrated_properties=(
            ClaimBoundaryDemonstration(
                statement=(
                    "the registered bounded repair was supported "
                    "under the packaged procedure"
                ),
                source_references=(
                    "artifact://repair-contrast",
                    "artifact://verification",
                ),
            ),
        ),
        assumptions=(
            "packaged source identities are authentic",
        ),
        unresolved_uncertainty=(
            "realistic stochastic workload performance is unestablished",
        ),
        unsupported_generalizations=(
            "does not establish general agent reliability",
        ),
        authorization_status=(
            ClaimBoundaryExternalStatus.NOT_ESTABLISHED
        ),
        deployment_status=(
            ClaimBoundaryExternalStatus.NOT_ESTABLISHED
        ),
        rationale="bounded claim only",
        limitations=(
            "not deployment authority",
        ),
    )


def make_context():
    goal = make_goal()
    snapshot = make_snapshot()

    evidence = (
        make_evidence_assignment(),
    )

    repair_contrast = make_repair_contrast(
        goal=goal,
        snapshot=snapshot,
    )

    verification = make_verification(
        goal=goal,
        snapshot=snapshot,
    )

    vsp = make_vsp(
        verification=verification,
    )

    claim_boundary = make_claim_boundary(
        goal=goal,
        snapshot=snapshot,
    )

    return (
        goal,
        snapshot,
        evidence,
        repair_contrast,
        verification,
        vsp,
        claim_boundary,
    )


def make_bundle(
    *,
    context_values=None,
    **overrides,
):
    if context_values is None:
        context_values = make_context()

    (
        goal,
        snapshot,
        evidence,
        repair_contrast,
        verification,
        vsp,
        claim_boundary,
    ) = context_values

    evidence_refs = tuple(
        AssuranceBundleEvidenceRoleReference(
            assignment_id=assignment.assignment_id,
            assignment_sha256=assignment.assignment_sha256,
        )
        for assignment in evidence
    )

    values = {
        "tenant_id": goal.tenant_id,
        "project_id": goal.project_id,
        "bundle_id": "assurance-bundle-1",
        "goal_contract_id": goal.contract_id,
        "goal_contract_sha256": goal.contract_sha256,
        "system_snapshot_id": snapshot.snapshot_id,
        "system_snapshot_sha256": snapshot.snapshot_sha256,
        "assembler_id": "assurance-bundle-assembler",
        "assembler_version": "1",
        "protocol_reference": "protocol://heal/assurance-bundle/v1",
        "protocol_sha256": EIGHT,
        "evidence_role_assignments": evidence_refs,
        "repair_contrast_id": repair_contrast.contrast_id,
        "repair_contrast_sha256": repair_contrast.contrast_sha256,
        "verification_id": verification.verification_id,
        "verification_sha256": verification.verification_sha256,
        "verifier_separation_profile_id": vsp.profile_id,
        "verifier_separation_profile_sha256": vsp.profile_sha256,
        "claim_boundary_id": claim_boundary.boundary_id,
        "claim_boundary_sha256": claim_boundary.boundary_sha256,
        "provenance_references": (
            "provenance://bundle-inputs",
        ),
        "limitations": (
            "bundle packaging does not prove underlying evidence",
        ),
    }

    values.update(
        overrides
    )

    return AssuranceBundle(
        **values
    )


def validate(
    bundle,
    values,
):
    (
        goal,
        snapshot,
        evidence,
        repair_contrast,
        verification,
        vsp,
        claim_boundary,
    ) = values

    bundle.validate_against(
        goal=goal,
        snapshot=snapshot,
        evidence_role_assignments=evidence,
        repair_contrast=repair_contrast,
        verification=verification,
        verifier_separation_profile=vsp,
        claim_boundary=claim_boundary,
    )


def test_valid_bundle_packages_exact_lineage():
    values = make_context()
    bundle = make_bundle(
        context_values=values,
    )

    validate(
        bundle,
        values,
    )


def test_bundle_hash_is_deterministic_and_claim_boundary_bound():
    values = make_context()

    first = make_bundle(
        context_values=values,
    )

    second = make_bundle(
        context_values=values,
    )

    changed = make_bundle(
        context_values=values,
        claim_boundary_sha256="1" * 64,
    )

    assert (
        first.bundle_sha256
        == second.bundle_sha256
    )

    assert (
        first.bundle_sha256
        != changed.bundle_sha256
    )


def test_evidence_role_reference_is_frozen():
    reference = AssuranceBundleEvidenceRoleReference(
        assignment_id="assignment-1",
        assignment_sha256=ZERO,
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        reference.assignment_id = "changed"


def test_bundle_is_frozen():
    bundle = make_bundle()

    with pytest.raises(
        FrozenInstanceError
    ):
        bundle.bundle_id = "changed"


def test_evidence_role_assignments_must_be_tuple():
    with pytest.raises(
        ContractError,
        match="must be a tuple",
    ):
        make_bundle(
            evidence_role_assignments=[],
        )


def test_evidence_role_assignment_members_must_be_references():
    with pytest.raises(
        ContractError,
        match="AssuranceBundleEvidenceRoleReference",
    ):
        make_bundle(
            evidence_role_assignments=(
                "not-a-reference",
            ),
        )


def test_duplicate_evidence_role_assignment_ids_rejected():
    reference = AssuranceBundleEvidenceRoleReference(
        assignment_id="same",
        assignment_sha256=ZERO,
    )

    with pytest.raises(
        ContractError,
        match="IDs must be unique",
    ):
        make_bundle(
            evidence_role_assignments=(
                reference,
                reference,
            ),
        )


def test_evidence_role_assignments_must_be_sorted():
    first = AssuranceBundleEvidenceRoleReference(
        assignment_id="a",
        assignment_sha256=ZERO,
    )

    second = AssuranceBundleEvidenceRoleReference(
        assignment_id="b",
        assignment_sha256=ONE,
    )

    with pytest.raises(
        ContractError,
        match="sorted by assignment_id",
    ):
        make_bundle(
            evidence_role_assignments=(
                second,
                first,
            ),
        )


def test_provenance_references_required():
    with pytest.raises(
        ContractError,
        match="requires provenance references",
    ):
        make_bundle(
            provenance_references=(),
        )


def test_explicit_limitations_required():
    with pytest.raises(
        ContractError,
        match="requires explicit limitations",
    ):
        make_bundle(
            limitations=(),
        )


def test_goal_identity_must_match():
    values = make_context()
    bundle = make_bundle(
        context_values=values,
    )

    changed = list(values)

    changed[0] = replace(
        changed[0],
        contract_id="different-goal",
    )

    with pytest.raises(
        ContractError,
        match="goal_contract_id",
    ):
        validate(
            bundle,
            tuple(changed),
        )


def test_snapshot_identity_must_match():
    values = make_context()
    bundle = make_bundle(
        context_values=values,
    )

    changed = list(values)

    changed[1] = replace(
        changed[1],
        snapshot_id="different-snapshot",
    )

    with pytest.raises(
        ContractError,
        match="system_snapshot_id",
    ):
        validate(
            bundle,
            tuple(changed),
        )


def test_repair_contrast_must_target_packaged_candidate():
    values = make_context()
    bundle = make_bundle(
        context_values=values,
    )

    changed = list(values)

    changed[3] = replace(
        changed[3],
        candidate_snapshot_id="different-candidate",
    )

    with pytest.raises(
        ContractError,
        match="repair_contrast",
    ):
        validate(
            bundle,
            tuple(changed),
        )


def test_verification_must_target_packaged_candidate():
    values = make_context()
    bundle = make_bundle(
        context_values=values,
    )

    changed = list(values)

    changed[4] = replace(
        changed[4],
        system_snapshot_id="different-candidate",
    )

    with pytest.raises(
        ContractError,
        match="verification",
    ):
        validate(
            bundle,
            tuple(changed),
        )


def test_vsp_must_bind_packaged_verification():
    values = make_context()
    bundle = make_bundle(
        context_values=values,
    )

    changed = list(values)

    changed[5] = replace(
        changed[5],
        verification_id="different-verification",
    )

    with pytest.raises(
        ContractError,
        match="verifier_separation_profile",
    ):
        validate(
            bundle,
            tuple(changed),
        )


def test_claim_boundary_must_target_packaged_candidate():
    values = make_context()
    bundle = make_bundle(
        context_values=values,
    )

    changed = list(values)

    changed[6] = replace(
        changed[6],
        system_snapshot_id="different-candidate",
    )

    with pytest.raises(
        ContractError,
        match="claim_boundary",
    ):
        validate(
            bundle,
            tuple(changed),
        )


def test_supplied_evidence_assignment_order_is_not_semantic():
    values = list(
        make_context()
    )

    first = make_evidence_assignment(
        assignment_id="a-assignment",
        evidence_reference="evidence://a",
        evidence_sha256="1" * 64,
    )

    second = make_evidence_assignment(
        assignment_id="b-assignment",
        evidence_reference="evidence://b",
        evidence_sha256="2" * 64,
    )

    values[2] = (
        first,
        second,
    )

    canonical_values = tuple(
        values
    )

    bundle = make_bundle(
        context_values=canonical_values,
    )

    reversed_values = list(
        canonical_values
    )

    reversed_values[2] = (
        second,
        first,
    )

    validate(
        bundle,
        tuple(
            reversed_values
        ),
    )


def test_packaged_evidence_role_assignments_must_match_exactly():
    values = make_context()

    bundle = make_bundle(
        context_values=values,
    )

    changed = list(values)

    changed[2] = (
        make_evidence_assignment(
            assignment_id="different-assignment",
            evidence_reference="evidence://different",
            evidence_sha256="1" * 64,
        ),
    )

    with pytest.raises(
        ContractError,
        match="do not match supplied assignments",
    ):
        validate(
            bundle,
            tuple(changed),
        )


def test_bundle_has_no_outcome_or_authority_surface():
    names = {
        field.name
        for field in fields(
            AssuranceBundle
        )
    }

    assert names.isdisjoint(
        {
            "outcome",
            "passed",
            "verified",
            "verification_outcome",
            "eligible",
            "eligibility",
            "authorized",
            "authorization",
            "approved",
            "deployed",
            "can_deploy",
            "deployment_authority",
            "lifecycle_state",
            "complete",
            "is_complete",
        }
    )
