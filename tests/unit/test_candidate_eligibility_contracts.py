"""Behavioral tests for the candidate-eligibility policy contract."""

from dataclasses import FrozenInstanceError, fields, replace
import json
import unittest
from unittest.mock import patch

from packages.contracts import (
    CandidateEligibilityDecision,
    CandidateEligibilityOutcome,
    ContractError,
    EvaluationOutcome,
    EvaluationRecord,
    ExecutionRecord,
    ExecutionStatus,
    GoalContract,
    MethodProposal,
    SystemSnapshot,
    VerificationOutcome,
    VerificationReport,
)


DIGEST = "a" * 64


def make_goal(**changes):
    values = dict(
        tenant_id="local",
        project_id="agent-repair",
        contract_id="goal-1",
        contract_version="1",
        system_id="agent-1",
        system_version_id="baseline-v1",
        claim_scope="bounded agent repair",
        objective="Return the correct tool result",
        metrics=("correct-result",),
        minimum_effect="all required checks pass",
        baseline_reference="baseline-1",
        acceptance_predicates=("correct tool result",),
        hard_constraints=("preserve protected behavior",),
        invariants=("no unrelated regression",),
        eligible_changes=("adapter code",),
        budget_constraints=("declared call budget",),
        reviewer_version="reviewer-v1",
        evaluator_version="evaluator-v1",
        evidence_requirements=("tool trace",),
        protected_evaluation_requirements=("frozen grader",),
        uncertainty_policy="preserve uncertainty",
        failure_invalidity_policy="retain both",
        verification_requirements=("separate protected run",),
    )
    values.update(changes)
    return GoalContract(**values)


def make_snapshot(goal=None, **changes):
    goal = goal or make_goal()

    values = dict(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        snapshot_id="candidate-snapshot",
        system_id=goal.system_id,
        system_version_id="candidate-v2",
        environment_family="agent",
        component_version_ids=("adapter-v2",),
        provider_binding_ids=(),
        adapter_binding_ids=("adapter-1",),
        evaluator_binding_ids=("evaluator-1",),
        code_identity=DIGEST,
        data_identity=None,
        prompt_identity=DIGEST,
        runtime_identity="python-runner-v1",
        state_references=("candidate-state",),
        artifact_references=(),
    )

    values.update(changes)
    return SystemSnapshot(**values)


def make_proposal(goal, snapshot):
    return MethodProposal(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        proposal_id="proposal-1",
        proposal_version="1",
        goal_contract_id=goal.contract_id,
        system_snapshot_id=snapshot.snapshot_id,
        question="Does the candidate satisfy the frozen objective?",
        alternatives=("candidate fails", "candidate succeeds"),
        expected_outcomes=("bounded evidence",),
        controls=("unchanged rerun",),
        generated_program='raise AssertionError("proposal must stay inert")',
        dependencies=(),
        stopping_rule="stop at the declared budget",
    )


def make_execution(
    goal,
    snapshot,
    proposal,
    *,
    execution_id,
    runner_id,
):
    return ExecutionRecord(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        execution_id=execution_id,
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        system_snapshot_id=snapshot.snapshot_id,
        system_snapshot_sha256=snapshot.snapshot_sha256,
        method_proposal_id=proposal.proposal_id,
        method_proposal_sha256=proposal.proposal_sha256,
        runner_id=runner_id,
        runner_version="1",
        environment_reference=f"environment-{execution_id}",
        execution_manifest_reference=f"manifest-{execution_id}",
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        termination_reason=None,
        input_references=("input-1",),
        output_references=(f"output-{execution_id}",),
        trace_references=(f"trace-{execution_id}",),
        limitations=(),
    )


def make_evaluation(
    goal,
    run,
    *,
    evaluation_id,
    outcome,
):
    measured = outcome in (
        EvaluationOutcome.PASS,
        EvaluationOutcome.FAIL,
        EvaluationOutcome.INCONCLUSIVE,
    )

    return EvaluationRecord(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        evaluation_id=evaluation_id,
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        execution_id=run.execution_id,
        execution_sha256=run.execution_sha256,
        evaluator_id="evaluator-1",
        evaluator_version=goal.evaluator_version,
        protocol_reference="frozen-evaluation-protocol",
        protocol_sha256=DIGEST,
        outcome=outcome,
        measurement_references=(
            (f"measurement-{evaluation_id}",)
            if measured
            else ()
        ),
        evidence_references=(
            (f"evidence-{evaluation_id}",)
            if measured
            else ()
        ),
        rationale=f"Recorded {outcome.value} outcome",
        uncertainty="Bounded case only",
        limitations=(),
    )


def make_verification_context(
    *,
    verification_outcome=VerificationOutcome.VERIFIED,
):
    goal = make_goal()
    snapshot = make_snapshot(goal)
    proposal = make_proposal(goal, snapshot)

    source_run = make_execution(
        goal,
        snapshot,
        proposal,
        execution_id="source-run",
        runner_id="source-runner",
    )

    source_evaluation = make_evaluation(
        goal,
        source_run,
        evaluation_id="source-eval",
        outcome=EvaluationOutcome.PASS,
    )

    verification_run = make_execution(
        goal,
        snapshot,
        proposal,
        execution_id="verification-run",
        runner_id="verification-runner",
    )

    evaluation_outcome = {
        VerificationOutcome.VERIFIED: EvaluationOutcome.PASS,
        VerificationOutcome.REJECTED: EvaluationOutcome.FAIL,
        VerificationOutcome.INCONCLUSIVE: EvaluationOutcome.INCONCLUSIVE,
        VerificationOutcome.BLOCKED: EvaluationOutcome.BLOCKED,
        VerificationOutcome.INVALID: EvaluationOutcome.INVALID,
    }[verification_outcome]

    verification_evaluation = make_evaluation(
        goal,
        verification_run,
        evaluation_id="verification-eval",
        outcome=evaluation_outcome,
    )

    measured = verification_outcome in (
        VerificationOutcome.VERIFIED,
        VerificationOutcome.REJECTED,
        VerificationOutcome.INCONCLUSIVE,
    )

    verification = VerificationReport(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        verification_id="verification-1",
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        system_snapshot_id=snapshot.snapshot_id,
        system_snapshot_sha256=snapshot.snapshot_sha256,
        source_execution_id=source_run.execution_id,
        source_execution_sha256=source_run.execution_sha256,
        source_evaluation_id=source_evaluation.evaluation_id,
        source_evaluation_sha256=source_evaluation.evaluation_sha256,
        verification_execution_id=verification_run.execution_id,
        verification_execution_sha256=verification_run.execution_sha256,
        verification_evaluation_id=verification_evaluation.evaluation_id,
        verification_evaluation_sha256=verification_evaluation.evaluation_sha256,
        verifier_id="verifier-1",
        verifier_version="1",
        protocol_reference="verification-protocol-1",
        protocol_sha256=DIGEST,
        outcome=verification_outcome,
        independence_references=(
            ("protected-run-attestation",)
            if measured
            else ()
        ),
        evidence_references=(
            ("verification-evidence",)
            if measured
            else ()
        ),
        rationale="Verification conclusion",
        uncertainty="Bounded verification only",
        limitations=(),
    )

    verification.validate_against(
        goal=goal,
        snapshot=snapshot,
        source_execution=source_run,
        source_evaluation=source_evaluation,
        verification_execution=verification_run,
        verification_evaluation=verification_evaluation,
    )

    return goal, snapshot, verification


def make_decision(
    goal=None,
    snapshot=None,
    verification=None,
    *,
    outcome=CandidateEligibilityOutcome.ELIGIBLE,
    **changes,
):
    if goal is None:
        goal, snapshot, verification = make_verification_context()

    measured = outcome in (
        CandidateEligibilityOutcome.ELIGIBLE,
        CandidateEligibilityOutcome.INELIGIBLE,
        CandidateEligibilityOutcome.INCONCLUSIVE,
    )

    values = dict(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        decision_id="eligibility-1",
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        system_snapshot_id=snapshot.snapshot_id,
        system_snapshot_sha256=snapshot.snapshot_sha256,
        verification_id=verification.verification_id,
        verification_sha256=verification.verification_sha256,
        reviewer_id="reviewer-1",
        reviewer_version=goal.reviewer_version,
        policy_reference="candidate-eligibility-policy-v1",
        policy_sha256=DIGEST,
        outcome=outcome,
        policy_input_references=(
            "candidate-change-manifest-1",
            "capability-profile-1",
        ),
        evidence_references=(
            ("eligibility-evidence-1",)
            if measured
            else ()
        ),
        rationale="Candidate reviewed against frozen eligibility policy",
        uncertainty="Decision is limited to the declared goal and candidate",
        limitations=(),
    )

    values.update(changes)
    return CandidateEligibilityDecision(**values)


class CandidateEligibilityContractTests(unittest.TestCase):
    def test_valid_eligible_decision(self):
        goal, snapshot, verification = make_verification_context()
        decision = make_decision(goal, snapshot, verification)

        decision.validate_against(
            goal=goal,
            snapshot=snapshot,
            verification=verification,
        )

        self.assertIs(
            decision.outcome,
            CandidateEligibilityOutcome.ELIGIBLE,
        )

    def test_all_outcomes_are_distinct(self):
        digests = set()

        for outcome in CandidateEligibilityOutcome:
            with self.subTest(outcome=outcome):
                decision = make_decision(outcome=outcome)

                self.assertEqual(
                    decision.canonical_payload()["outcome"],
                    outcome.value,
                )

                digests.add(decision.eligibility_sha256)

        self.assertEqual(len(digests), 5)

    def test_measured_outcomes_require_evidence(self):
        for outcome in (
            CandidateEligibilityOutcome.ELIGIBLE,
            CandidateEligibilityOutcome.INELIGIBLE,
            CandidateEligibilityOutcome.INCONCLUSIVE,
        ):
            with self.subTest(outcome=outcome):
                with self.assertRaises(ContractError):
                    make_decision(
                        outcome=outcome,
                        evidence_references=(),
                    )

    def test_blocked_and_invalid_need_no_invented_evidence(self):
        for outcome in (
            CandidateEligibilityOutcome.BLOCKED,
            CandidateEligibilityOutcome.INVALID,
        ):
            with self.subTest(outcome=outcome):
                decision = make_decision(
                    outcome=outcome,
                    evidence_references=(),
                )
                self.assertIs(decision.outcome, outcome)

    def test_eligible_requires_verified_report(self):
        for verification_outcome in (
            VerificationOutcome.REJECTED,
            VerificationOutcome.INCONCLUSIVE,
            VerificationOutcome.BLOCKED,
            VerificationOutcome.INVALID,
        ):
            with self.subTest(
                verification_outcome=verification_outcome
            ):
                goal, snapshot, verification = (
                    make_verification_context(
                        verification_outcome=verification_outcome
                    )
                )

                decision = make_decision(
                    goal,
                    snapshot,
                    verification,
                    outcome=CandidateEligibilityOutcome.ELIGIBLE,
                )

                with self.assertRaises(ContractError):
                    decision.validate_against(
                        goal=goal,
                        snapshot=snapshot,
                        verification=verification,
                    )

    def test_verified_candidate_can_still_be_ineligible(self):
        goal, snapshot, verification = make_verification_context()

        decision = make_decision(
            goal,
            snapshot,
            verification,
            outcome=CandidateEligibilityOutcome.INELIGIBLE,
            rationale="Verified behavior violates the governed change policy",
        )

        decision.validate_against(
            goal=goal,
            snapshot=snapshot,
            verification=verification,
        )

        self.assertIs(
            verification.outcome,
            VerificationOutcome.VERIFIED,
        )
        self.assertIs(
            decision.outcome,
            CandidateEligibilityOutcome.INELIGIBLE,
        )

    def test_reviewer_version_must_match_frozen_goal(self):
        goal, snapshot, verification = make_verification_context()

        decision = make_decision(
            goal,
            snapshot,
            verification,
            reviewer_version="other-reviewer-version",
        )

        with self.assertRaises(ContractError):
            decision.validate_against(
                goal=goal,
                snapshot=snapshot,
                verification=verification,
            )

    def test_stale_goal_digest_is_rejected(self):
        goal, snapshot, verification = make_verification_context()
        decision = make_decision(goal, snapshot, verification)

        changed_goal = replace(
            goal,
            objective="Different frozen objective",
        )

        with self.assertRaises(ContractError):
            decision.validate_against(
                goal=changed_goal,
                snapshot=snapshot,
                verification=verification,
            )

    def test_stale_snapshot_digest_is_rejected(self):
        goal, snapshot, verification = make_verification_context()
        decision = make_decision(goal, snapshot, verification)

        changed_snapshot = replace(
            snapshot,
            state_references=("different-state",),
        )

        with self.assertRaises(ContractError):
            decision.validate_against(
                goal=goal,
                snapshot=changed_snapshot,
                verification=verification,
            )

    def test_stale_verification_digest_is_rejected(self):
        goal, snapshot, verification = make_verification_context()
        decision = make_decision(goal, snapshot, verification)

        changed_verification = replace(
            verification,
            uncertainty="Different verification uncertainty",
        )

        with self.assertRaises(ContractError):
            decision.validate_against(
                goal=goal,
                snapshot=snapshot,
                verification=changed_verification,
            )

    def test_verification_must_bind_same_goal(self):
        goal, snapshot, verification = make_verification_context()

        changed = replace(
            verification,
            goal_contract_id="other-goal",
        )

        decision = make_decision(
            goal,
            snapshot,
            changed,
            verification_sha256=changed.verification_sha256,
        )

        with self.assertRaises(ContractError):
            decision.validate_against(
                goal=goal,
                snapshot=snapshot,
                verification=changed,
            )

    def test_verification_must_bind_same_candidate(self):
        goal, snapshot, verification = make_verification_context()

        changed = replace(
            verification,
            system_snapshot_id="other-snapshot",
        )

        decision = make_decision(
            goal,
            snapshot,
            changed,
            verification_sha256=changed.verification_sha256,
        )

        with self.assertRaises(ContractError):
            decision.validate_against(
                goal=goal,
                snapshot=snapshot,
                verification=changed,
            )

    def test_goal_and_snapshot_must_name_same_system(self):
        goal, snapshot, verification = make_verification_context()

        changed_snapshot = replace(
            snapshot,
            system_id="other-system",
        )

        decision = make_decision(
            goal,
            changed_snapshot,
            verification,
            system_snapshot_sha256=changed_snapshot.snapshot_sha256,
        )

        with self.assertRaises(ContractError):
            decision.validate_against(
                goal=goal,
                snapshot=changed_snapshot,
                verification=verification,
            )

    def test_cross_scope_verification_is_rejected(self):
        goal, snapshot, verification = make_verification_context()

        changed = replace(
            verification,
            tenant_id="other-tenant",
        )

        decision = make_decision(
            goal,
            snapshot,
            changed,
            tenant_id=goal.tenant_id,
            verification_sha256=changed.verification_sha256,
        )

        with self.assertRaises(ContractError):
            decision.validate_against(
                goal=goal,
                snapshot=snapshot,
                verification=changed,
            )

    def test_plain_string_is_not_typed_outcome(self):
        with self.assertRaises(ContractError):
            make_decision(outcome="ELIGIBLE")

    def test_blank_required_text_is_rejected(self):
        for field in (
            "decision_id",
            "reviewer_id",
            "reviewer_version",
            "policy_reference",
            "rationale",
            "uncertainty",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ContractError):
                    make_decision(**{field: " "})

    def test_digests_are_strict_lowercase_sha256(self):
        for field in (
            "goal_contract_sha256",
            "system_snapshot_sha256",
            "verification_sha256",
            "policy_sha256",
        ):
            for bad in (
                None,
                7,
                "a" * 63,
                "g" * 64,
                "A" * 64,
                DIGEST + "\n",
            ):
                with self.subTest(field=field, bad=bad):
                    with self.assertRaises(ContractError):
                        make_decision(**{field: bad})

    def test_collection_fields_reject_mutable_or_malformed_values(self):
        for field in (
            "policy_input_references",
            "evidence_references",
            "limitations",
        ):
            for bad in (
                ["reference"],
                "reference",
                ([],),
                (" ",),
                (1,),
            ):
                with self.subTest(field=field, bad=bad):
                    with self.assertRaises(ContractError):
                        make_decision(**{field: bad})

    def test_decision_is_immutable(self):
        decision = make_decision()

        with self.assertRaises(FrozenInstanceError):
            decision.rationale = "changed"

    def test_payload_mutation_does_not_mutate_record(self):
        decision = make_decision()
        digest = decision.eligibility_sha256

        payload = decision.canonical_payload()
        payload["rationale"] = "changed"

        self.assertEqual(
            decision.eligibility_sha256,
            digest,
        )

    def test_hash_is_deterministic_and_json_serializable(self):
        first = make_decision()
        second = make_decision()

        self.assertEqual(
            first.eligibility_sha256,
            second.eligibility_sha256,
        )

        self.assertIsInstance(
            json.loads(
                json.dumps(first.canonical_payload())
            ),
            dict,
        )

    def test_hash_tracks_material_policy_changes(self):
        original = make_decision()

        for field, value in (
            ("reviewer_version", "reviewer-v2"),
            ("policy_sha256", "b" * 64),
            (
                "policy_input_references",
                ("different-policy-input",),
            ),
            (
                "evidence_references",
                ("different-policy-evidence",),
            ),
            (
                "uncertainty",
                "Different eligibility uncertainty",
            ),
        ):
            with self.subTest(field=field):
                changed = replace(
                    original,
                    **{field: value},
                )

                self.assertNotEqual(
                    original.eligibility_sha256,
                    changed.eligibility_sha256,
                )

    def test_decision_contains_no_authority_or_execution_fields(self):
        names = {
            field.name
            for field in fields(CandidateEligibilityDecision)
        }

        forbidden = {
            "authorization",
            "authorized",
            "approval",
            "approved",
            "execution_authority",
            "can_execute",
            "can_deploy",
            "deployment_authority",
            "promotion_authority",
            "lifecycle_state",
            "next_state",
            "complete",
            "is_complete",
        }

        self.assertTrue(names.isdisjoint(forbidden))

    def test_link_validation_rejects_untyped_inputs(self):
        goal, snapshot, verification = make_verification_context()
        decision = make_decision(goal, snapshot, verification)

        with self.assertRaises(ContractError):
            decision.validate_against(
                goal={},
                snapshot=snapshot,
                verification=verification,
            )

    def test_policy_record_does_not_execute_or_resolve_references(self):
        goal, snapshot, verification = make_verification_context()

        error = AssertionError(
            "Eligibility contract attempted I/O or execution"
        )

        with patch("subprocess.run", side_effect=error), \
             patch("builtins.open", side_effect=error), \
             patch("pathlib.Path.open", side_effect=error), \
             patch("socket.socket", side_effect=error):

            decision = make_decision(
                goal,
                snapshot,
                verification,
                policy_reference="nonexistent://policy",
                policy_input_references=(
                    "nonexistent://capability-profile",
                    "nonexistent://change-manifest",
                ),
                evidence_references=(
                    "nonexistent://policy-evidence",
                ),
            )

            decision.validate_against(
                goal=goal,
                snapshot=snapshot,
                verification=verification,
            )

            self.assertTrue(
                decision.eligibility_sha256
            )


if __name__ == "__main__":
    unittest.main()
