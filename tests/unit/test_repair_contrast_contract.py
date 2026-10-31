from dataclasses import (
    FrozenInstanceError,
    fields,
    replace,
)

import pytest

from packages.contracts import (
    ContractError,
    EvaluationOutcome,
    EvaluationRecord,
    ExecutionRecord,
    ExecutionStatus,
    GoalContract,
    MethodProposal,
    RepairContrastOutcome,
    RepairContrastRecord,
    SystemSnapshot,
)


ZERO = "0" * 64
ONE = "1" * 64
TWO = "2" * 64
THREE = "3" * 64

COMPARISON_CASE_REFERENCE = (
    "fixture://repair-contrast/target-case-v1"
)

COMPARISON_CASE_SHA = THREE

COMPARISON_CASE_BINDING = (
    f"{COMPARISON_CASE_REFERENCE}"
    f"#sha256={COMPARISON_CASE_SHA}"
)


def make_goal() -> GoalContract:
    return GoalContract(
        tenant_id="tenant-1",
        project_id="project-1",
        contract_id="goal-1",
        contract_version="1",
        system_id="system-1",
        system_version_id="baseline-v1",
        claim_scope="bounded repair contrast",
        objective="Restore the registered target behavior",
        metrics=(
            "exact-target-behavior",
        ),
        minimum_effect="known-bad fails and candidate passes",
        baseline_reference="baseline-1",
        acceptance_predicates=(
            "target behavior matches expected result",
        ),
        hard_constraints=(),
        invariants=(),
        eligible_changes=(
            "configuration",
        ),
        budget_constraints=(
            "bounded fixture budget",
        ),
        reviewer_version="reviewer-v1",
        evaluator_version="evaluator-v1",
        evidence_requirements=(
            "ordinary evaluation evidence",
        ),
        protected_evaluation_requirements=(
            "contrast frozen before protected evaluation",
        ),
        uncertainty_policy=(
            "report inconclusive when evidence is insufficient"
        ),
        failure_invalidity_policy=(
            "preserve failures and invalid attempts separately"
        ),
        verification_requirements=(
            "verification remains separate from Repair Contrast",
        ),
    )


def make_snapshot(
    *,
    snapshot_id: str,
    version: str,
    code_identity: str,
) -> SystemSnapshot:
    return SystemSnapshot(
        tenant_id="tenant-1",
        project_id="project-1",
        snapshot_id=snapshot_id,
        system_id="system-1",
        system_version_id=version,
        environment_family="controlled-agent",
        component_version_ids=(
            version,
        ),
        provider_binding_ids=(),
        adapter_binding_ids=(),
        evaluator_binding_ids=(
            "evaluator-v1",
        ),
        code_identity=code_identity,
        data_identity=None,
        prompt_identity=ZERO,
        runtime_identity="python-3.12",
        state_references=(
            f"state://{snapshot_id}",
        ),
        artifact_references=(),
    )


def make_proposal(
    *,
    goal: GoalContract,
    snapshot: SystemSnapshot,
    proposal_id: str,
) -> MethodProposal:
    return MethodProposal(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        proposal_id=proposal_id,
        proposal_version="1",
        goal_contract_id=goal.contract_id,
        system_snapshot_id=snapshot.snapshot_id,
        question="Does this state satisfy the target behavior?",
        alternatives=(
            "target fails",
            "target passes",
        ),
        expected_outcomes=(
            "registered evaluation outcome",
        ),
        controls=(
            "same evaluation protocol",
        ),
        generated_program="pass",
        dependencies=(),
        stopping_rule="one bounded evaluation",
    )


def make_execution(
    *,
    goal: GoalContract,
    snapshot: SystemSnapshot,
    proposal: MethodProposal,
    execution_id: str,
) -> ExecutionRecord:
    execution = ExecutionRecord(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        execution_id=execution_id,
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        system_snapshot_id=snapshot.snapshot_id,
        system_snapshot_sha256=snapshot.snapshot_sha256,
        method_proposal_id=proposal.proposal_id,
        method_proposal_sha256=proposal.proposal_sha256,
        runner_id="contrast-fixture-runner",
        runner_version="1",
        environment_reference="fixture://repair-contrast",
        execution_manifest_reference=(
            f"manifest://{execution_id}"
        ),
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        termination_reason=None,
        input_references=(
            f"snapshot-sha256:{snapshot.snapshot_sha256}",
            COMPARISON_CASE_BINDING,
        ),
        output_references=(
            f"output://{execution_id}",
        ),
        trace_references=(
            f"trace://{execution_id}",
        ),
        limitations=(
            "controlled unit fixture only",
        ),
    )

    execution.validate_against(
        goal=goal,
        snapshot=snapshot,
        proposal=proposal,
    )

    return execution


def make_evaluation(
    *,
    goal: GoalContract,
    execution: ExecutionRecord,
    evaluation_id: str,
    outcome: EvaluationOutcome,
    evaluator_id: str = "ordinary-evaluator",
    protocol_reference: str = "protocol://ordinary/target-v1",
    protocol_sha256: str = ONE,
) -> EvaluationRecord:
    return EvaluationRecord(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        evaluation_id=evaluation_id,
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        execution_id=execution.execution_id,
        execution_sha256=execution.execution_sha256,
        evaluator_id=evaluator_id,
        evaluator_version=goal.evaluator_version,
        protocol_reference=protocol_reference,
        protocol_sha256=protocol_sha256,
        outcome=outcome,
        measurement_references=(
            f"measurement://{evaluation_id}",
        ),
        evidence_references=(
            f"evidence://{evaluation_id}",
        ),
        rationale="ordinary bounded evaluation",
        uncertainty="controlled unit fixture only",
        limitations=(
            "not verification",
        ),
    )


def context(
    *,
    known_bad_outcome: EvaluationOutcome = EvaluationOutcome.FAIL,
    candidate_outcome: EvaluationOutcome = EvaluationOutcome.PASS,
):
    goal = make_goal()

    known_bad_snapshot = make_snapshot(
        snapshot_id="known-bad",
        version="bad-v1",
        code_identity=ZERO,
    )

    candidate_snapshot = make_snapshot(
        snapshot_id="candidate",
        version="candidate-v2",
        code_identity=ONE,
    )

    known_bad_proposal = make_proposal(
        goal=goal,
        snapshot=known_bad_snapshot,
        proposal_id="proposal-known-bad",
    )

    candidate_proposal = make_proposal(
        goal=goal,
        snapshot=candidate_snapshot,
        proposal_id="proposal-candidate",
    )

    known_bad_execution = make_execution(
        goal=goal,
        snapshot=known_bad_snapshot,
        proposal=known_bad_proposal,
        execution_id="execution-known-bad",
    )

    candidate_execution = make_execution(
        goal=goal,
        snapshot=candidate_snapshot,
        proposal=candidate_proposal,
        execution_id="execution-candidate",
    )

    known_bad_evaluation = make_evaluation(
        goal=goal,
        execution=known_bad_execution,
        evaluation_id="evaluation-known-bad",
        outcome=known_bad_outcome,
    )

    candidate_evaluation = make_evaluation(
        goal=goal,
        execution=candidate_execution,
        evaluation_id="evaluation-candidate",
        outcome=candidate_outcome,
    )

    return (
        goal,
        known_bad_snapshot,
        candidate_snapshot,
        known_bad_execution,
        known_bad_evaluation,
        candidate_execution,
        candidate_evaluation,
    )


def make_contrast(
    *,
    outcome=RepairContrastOutcome.REPAIR_DISCRIMINATING,
    context_values=None,
    **overrides,
) -> RepairContrastRecord:
    if context_values is None:
        context_values = context()

    (
        goal,
        known_bad_snapshot,
        candidate_snapshot,
        known_bad_execution,
        known_bad_evaluation,
        candidate_execution,
        candidate_evaluation,
    ) = context_values

    values = {
        "tenant_id": goal.tenant_id,
        "project_id": goal.project_id,
        "contrast_id": "repair-contrast-1",
        "goal_contract_id": goal.contract_id,
        "goal_contract_sha256": goal.contract_sha256,
        "known_bad_snapshot_id": known_bad_snapshot.snapshot_id,
        "known_bad_snapshot_sha256": (
            known_bad_snapshot.snapshot_sha256
        ),
        "candidate_snapshot_id": candidate_snapshot.snapshot_id,
        "candidate_snapshot_sha256": (
            candidate_snapshot.snapshot_sha256
        ),
        "known_bad_execution_id": known_bad_execution.execution_id,
        "known_bad_execution_sha256": (
            known_bad_execution.execution_sha256
        ),
        "known_bad_evaluation_id": known_bad_evaluation.evaluation_id,
        "known_bad_evaluation_sha256": (
            known_bad_evaluation.evaluation_sha256
        ),
        "candidate_execution_id": candidate_execution.execution_id,
        "candidate_execution_sha256": (
            candidate_execution.execution_sha256
        ),
        "candidate_evaluation_id": candidate_evaluation.evaluation_id,
        "candidate_evaluation_sha256": (
            candidate_evaluation.evaluation_sha256
        ),
        "claim_reference": "claim://repair/target-behavior-v1",
        "claim_sha256": TWO,
        "comparison_case_reference": (
            COMPARISON_CASE_REFERENCE
        ),
        "comparison_case_sha256": (
            COMPARISON_CASE_SHA
        ),
        "contrast_qualifier_id": "repair-contrast-qualifier",
        "contrast_qualifier_version": "1",
        "contrast_protocol_reference": (
            "protocol://heal/repair-contrast/v1"
        ),
        "contrast_protocol_sha256": ZERO,
        "outcome": outcome,
        "evidence_references": (
            "evidence://known-bad",
            "evidence://candidate",
        ),
        "rationale": (
            "known-bad and candidate ordinary evaluations are contrasted"
        ),
        "uncertainty": (
            "bounded contrast does not establish general repair correctness"
        ),
        "limitations": (
            "controlled contract test only",
            "not independent verification",
            "not eligibility",
            "not authorization",
        ),
    }

    values.update(
        overrides
    )

    return RepairContrastRecord(
        **values
    )


def validate(
    contrast,
    values,
):
    (
        goal,
        known_bad_snapshot,
        candidate_snapshot,
        known_bad_execution,
        known_bad_evaluation,
        candidate_execution,
        candidate_evaluation,
    ) = values

    contrast.validate_against(
        goal=goal,
        known_bad_snapshot=known_bad_snapshot,
        candidate_snapshot=candidate_snapshot,
        known_bad_execution=known_bad_execution,
        known_bad_evaluation=known_bad_evaluation,
        candidate_execution=candidate_execution,
        candidate_evaluation=candidate_evaluation,
    )


def test_fail_to_pass_is_repair_discriminating():
    values = context()

    contrast = make_contrast(
        context_values=values,
    )

    validate(
        contrast,
        values,
    )

    assert (
        contrast.outcome
        is RepairContrastOutcome.REPAIR_DISCRIMINATING
    )


@pytest.mark.parametrize(
    (
        "known_bad",
        "candidate",
    ),
    (
        (
            EvaluationOutcome.PASS,
            EvaluationOutcome.PASS,
        ),
        (
            EvaluationOutcome.FAIL,
            EvaluationOutcome.FAIL,
        ),
        (
            EvaluationOutcome.PASS,
            EvaluationOutcome.FAIL,
        ),
    ),
)
def test_other_conclusive_pairs_are_not_repair_discriminating(
    known_bad,
    candidate,
):
    values = context(
        known_bad_outcome=known_bad,
        candidate_outcome=candidate,
    )

    contrast = make_contrast(
        outcome=(
            RepairContrastOutcome.NOT_REPAIR_DISCRIMINATING
        ),
        context_values=values,
    )

    validate(
        contrast,
        values,
    )


def test_inconclusive_pair_maps_to_inconclusive():
    values = context(
        candidate_outcome=EvaluationOutcome.INCONCLUSIVE,
    )

    contrast = make_contrast(
        outcome=RepairContrastOutcome.INCONCLUSIVE,
        context_values=values,
    )

    validate(
        contrast,
        values,
    )


def test_blocked_pair_maps_to_blocked():
    values = context(
        known_bad_outcome=EvaluationOutcome.BLOCKED,
    )

    contrast = make_contrast(
        outcome=RepairContrastOutcome.BLOCKED,
        context_values=values,
        evidence_references=(),
    )

    validate(
        contrast,
        values,
    )


def test_invalid_pair_maps_to_invalid():
    values = context(
        candidate_outcome=EvaluationOutcome.INVALID,
    )

    contrast = make_contrast(
        outcome=RepairContrastOutcome.INVALID,
        context_values=values,
        evidence_references=(),
    )

    validate(
        contrast,
        values,
    )


def test_wrong_contrast_outcome_is_rejected():
    values = context()

    contrast = make_contrast(
        outcome=(
            RepairContrastOutcome.NOT_REPAIR_DISCRIMINATING
        ),
        context_values=values,
    )

    with pytest.raises(
        ContractError,
        match="outcome does not match",
    ):
        validate(
            contrast,
            values,
        )


def test_known_bad_and_candidate_must_use_same_evaluator():
    values = list(
        context()
    )

    values[6] = replace(
        values[6],
        evaluator_id="different-evaluator",
    )

    contrast = make_contrast(
        context_values=tuple(values),
        candidate_evaluation_sha256=(
            values[6].evaluation_sha256
        ),
    )

    with pytest.raises(
        ContractError,
        match="evaluator_id",
    ):
        validate(
            contrast,
            tuple(values),
        )


def test_known_bad_and_candidate_must_use_same_protocol():
    values = list(
        context()
    )

    values[6] = replace(
        values[6],
        protocol_reference="protocol://different",
        protocol_sha256="3" * 64,
    )

    contrast = make_contrast(
        context_values=tuple(values),
        candidate_evaluation_sha256=(
            values[6].evaluation_sha256
        ),
    )

    with pytest.raises(
        ContractError,
        match="protocol_reference",
    ):
        validate(
            contrast,
            tuple(values),
        )


def test_candidate_snapshot_must_differ_from_known_bad():
    values = context()

    with pytest.raises(
        ContractError,
        match="snapshot IDs must differ",
    ):
        make_contrast(
            context_values=values,
            candidate_snapshot_id=(
                values[1].snapshot_id
            ),
        )


def test_candidate_snapshot_digest_must_differ():
    values = context()

    with pytest.raises(
        ContractError,
        match="snapshot digests must differ",
    ):
        make_contrast(
            context_values=values,
            candidate_snapshot_sha256=(
                values[1].snapshot_sha256
            ),
        )


def test_both_states_must_belong_to_same_target_system():
    values = list(
        context()
    )

    values[2] = replace(
        values[2],
        system_id="different-system",
    )

    contrast = make_contrast(
        context_values=tuple(values),
    )

    with pytest.raises(
        ContractError,
        match="candidate_snapshot.system_id",
    ):
        validate(
            contrast,
            tuple(values),
        )


def test_both_states_must_use_same_execution_runner():
    values = list(
        context()
    )

    values[5] = replace(
        values[5],
        runner_id="different-runner",
    )

    contrast = make_contrast(
        context_values=tuple(values),
    )

    with pytest.raises(
        ContractError,
        match="candidate_execution.runner_id",
    ):
        validate(
            contrast,
            tuple(values),
        )


def test_known_bad_execution_must_bind_shared_comparison_case():
    values = list(
        context()
    )

    values[3] = replace(
        values[3],
        input_references=tuple(
            reference
            for reference
            in values[3].input_references
            if reference
            != COMPARISON_CASE_BINDING
        ),
    )

    contrast = make_contrast(
        context_values=tuple(values),
    )

    with pytest.raises(
        ContractError,
        match="known-bad execution must bind",
    ):
        validate(
            contrast,
            tuple(values),
        )


def test_candidate_execution_must_bind_shared_comparison_case():
    values = list(
        context()
    )

    values[5] = replace(
        values[5],
        input_references=tuple(
            reference
            for reference
            in values[5].input_references
            if reference
            != COMPARISON_CASE_BINDING
        ),
    )

    contrast = make_contrast(
        context_values=tuple(values),
    )

    with pytest.raises(
        ContractError,
        match="candidate execution must bind",
    ):
        validate(
            contrast,
            tuple(values),
        )


def test_measured_contrast_requires_evidence():
    values = context()

    with pytest.raises(
        ContractError,
        match="requires evidence references",
    ):
        make_contrast(
            context_values=values,
            evidence_references=(),
        )


def test_contrast_hash_binds_claim_case_and_protocol():
    values = context()

    original = make_contrast(
        context_values=values,
    )

    changed_claim = make_contrast(
        context_values=values,
        claim_sha256="4" * 64,
    )

    changed_case = make_contrast(
        context_values=values,
        comparison_case_sha256="5" * 64,
    )

    changed_protocol = make_contrast(
        context_values=values,
        contrast_protocol_sha256="6" * 64,
    )

    assert (
        original.contrast_sha256
        != changed_claim.contrast_sha256
    )

    assert (
        original.contrast_sha256
        != changed_case.contrast_sha256
    )

    assert (
        original.contrast_sha256
        != changed_protocol.contrast_sha256
    )


def test_contrast_is_frozen():
    contrast = make_contrast()

    with pytest.raises(
        FrozenInstanceError
    ):
        contrast.rationale = "changed"


def test_contrast_has_no_verification_eligibility_or_authority_surface():
    names = {
        field.name
        for field in fields(
            RepairContrastRecord
        )
    }

    assert names.isdisjoint(
        {
            "verified",
            "verification_outcome",
            "eligible",
            "eligibility",
            "authorization",
            "authorized",
            "approval",
            "approved",
            "can_execute",
            "can_deploy",
            "deployment_authority",
            "lifecycle_state",
            "complete",
            "is_complete",
        }
    )
