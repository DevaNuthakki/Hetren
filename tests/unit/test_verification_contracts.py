"""Behavioral tests for the independent-verification contract."""

from dataclasses import FrozenInstanceError, fields, replace
import json
import unittest
from unittest.mock import patch

from packages.contracts import (
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


def context():
    goal = GoalContract(
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
        hard_constraints=(),
        invariants=(),
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

    snapshot = SystemSnapshot(
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

    proposal = MethodProposal(
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

    return goal, snapshot, proposal


def execution(
    goal=None,
    snapshot=None,
    proposal=None,
    *,
    execution_id="source-run",
    runner_id="runner-1",
    **changes,
):
    if goal is None:
        goal, snapshot, proposal = context()

    values = dict(
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
        environment_reference="environment-1",
        execution_manifest_reference=f"manifest-{execution_id}",
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        termination_reason=None,
        input_references=("input-1",),
        output_references=(f"output-{execution_id}",),
        trace_references=(f"trace-{execution_id}",),
        limitations=(),
    )

    values.update(changes)
    return ExecutionRecord(**values)


def evaluation(
    goal,
    run,
    *,
    evaluation_id,
    outcome=EvaluationOutcome.PASS,
    **changes,
):
    evidence = (
        ()
        if outcome in (
            EvaluationOutcome.BLOCKED,
            EvaluationOutcome.INVALID,
        )
        else (f"evidence-{evaluation_id}",)
    )

    measurements = (
        ()
        if outcome in (
            EvaluationOutcome.BLOCKED,
            EvaluationOutcome.INVALID,
        )
        else (f"measurement-{evaluation_id}",)
    )

    values = dict(
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
        measurement_references=measurements,
        evidence_references=evidence,
        rationale=f"Recorded {outcome.value} outcome",
        uncertainty="Bounded verification case only",
        limitations=(),
    )

    values.update(changes)
    return EvaluationRecord(**values)


def verification_context(
    *,
    verification_evaluation_outcome=EvaluationOutcome.PASS,
):
    goal, snapshot, proposal = context()

    source_run = execution(
        goal,
        snapshot,
        proposal,
        execution_id="source-run",
        runner_id="runner-source",
    )

    source_assessment = evaluation(
        goal,
        source_run,
        evaluation_id="source-eval",
        outcome=EvaluationOutcome.PASS,
    )

    verification_run = execution(
        goal,
        snapshot,
        proposal,
        execution_id="verification-run",
        runner_id="runner-verification",
        environment_reference="protected-environment-2",
        execution_manifest_reference="protected-manifest-2",
    )

    verification_assessment = evaluation(
        goal,
        verification_run,
        evaluation_id="verification-eval",
        outcome=verification_evaluation_outcome,
    )

    return (
        goal,
        snapshot,
        proposal,
        source_run,
        source_assessment,
        verification_run,
        verification_assessment,
    )


def report(
    *,
    goal=None,
    snapshot=None,
    source_run=None,
    source_assessment=None,
    verification_run=None,
    verification_assessment=None,
    outcome=VerificationOutcome.VERIFIED,
    **changes,
):
    if goal is None:
        (
            goal,
            snapshot,
            _,
            source_run,
            source_assessment,
            verification_run,
            verification_assessment,
        ) = verification_context(
            verification_evaluation_outcome={
                VerificationOutcome.VERIFIED: EvaluationOutcome.PASS,
                VerificationOutcome.REJECTED: EvaluationOutcome.FAIL,
                VerificationOutcome.INCONCLUSIVE: EvaluationOutcome.INCONCLUSIVE,
                VerificationOutcome.BLOCKED: EvaluationOutcome.BLOCKED,
                VerificationOutcome.INVALID: EvaluationOutcome.INVALID,
            }[outcome]
        )

    measured = outcome in (
        VerificationOutcome.VERIFIED,
        VerificationOutcome.REJECTED,
        VerificationOutcome.INCONCLUSIVE,
    )

    values = dict(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        verification_id="verification-report-1",
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=goal.contract_sha256,
        system_snapshot_id=snapshot.snapshot_id,
        system_snapshot_sha256=snapshot.snapshot_sha256,
        source_execution_id=source_run.execution_id,
        source_execution_sha256=source_run.execution_sha256,
        source_evaluation_id=source_assessment.evaluation_id,
        source_evaluation_sha256=source_assessment.evaluation_sha256,
        verification_execution_id=verification_run.execution_id,
        verification_execution_sha256=verification_run.execution_sha256,
        verification_evaluation_id=verification_assessment.evaluation_id,
        verification_evaluation_sha256=(
            verification_assessment.evaluation_sha256
        ),
        verifier_id="verifier-1",
        verifier_version="1",
        protocol_reference="verification-protocol-1",
        protocol_sha256=DIGEST,
        outcome=outcome,
        independence_references=(
            ("protected-run-attestation-1",)
            if measured
            else ()
        ),
        evidence_references=(
            ("verification-evidence-1",)
            if measured
            else ()
        ),
        rationale="Independent verification conclusion",
        uncertainty="Bounded case; no broader generalization",
        limitations=(),
    )

    values.update(changes)
    return VerificationReport(**values)


def validate(record, context_values):
    (
        goal,
        snapshot,
        _,
        source_run,
        source_assessment,
        verification_run,
        verification_assessment,
    ) = context_values

    record.validate_against(
        goal=goal,
        snapshot=snapshot,
        source_execution=source_run,
        source_evaluation=source_assessment,
        verification_execution=verification_run,
        verification_evaluation=verification_assessment,
    )


class VerificationContractTests(unittest.TestCase):
    def test_valid_verified_lineage(self):
        values = verification_context()
        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=values[4],
            verification_run=values[5],
            verification_assessment=values[6],
        )

        validate(record, values)

        self.assertIs(
            record.outcome,
            VerificationOutcome.VERIFIED,
        )

    def test_all_five_verification_outcomes_remain_distinct(self):
        mapping = {
            VerificationOutcome.VERIFIED: EvaluationOutcome.PASS,
            VerificationOutcome.REJECTED: EvaluationOutcome.FAIL,
            VerificationOutcome.INCONCLUSIVE: EvaluationOutcome.INCONCLUSIVE,
            VerificationOutcome.BLOCKED: EvaluationOutcome.BLOCKED,
            VerificationOutcome.INVALID: EvaluationOutcome.INVALID,
        }

        digests = set()

        for outcome, evaluation_outcome in mapping.items():
            with self.subTest(outcome=str(outcome)):
                values = verification_context(
                    verification_evaluation_outcome=evaluation_outcome
                )

                record = report(
                    goal=values[0],
                    snapshot=values[1],
                    source_run=values[3],
                    source_assessment=values[4],
                    verification_run=values[5],
                    verification_assessment=values[6],
                    outcome=outcome,
                )

                validate(record, values)

                self.assertEqual(
                    record.canonical_payload()["outcome"],
                    outcome.value,
                )

                digests.add(record.verification_sha256)

        self.assertEqual(len(digests), 5)

    def test_measured_verification_outcomes_require_evidence(self):
        for outcome in (
            VerificationOutcome.VERIFIED,
            VerificationOutcome.REJECTED,
            VerificationOutcome.INCONCLUSIVE,
        ):
            with self.subTest(outcome=str(outcome)):
                with self.assertRaises(ContractError):
                    report(
                        outcome=outcome,
                        evidence_references=(),
                    )

    def test_measured_verification_outcomes_require_independence_references(self):
        for outcome in (
            VerificationOutcome.VERIFIED,
            VerificationOutcome.REJECTED,
            VerificationOutcome.INCONCLUSIVE,
        ):
            with self.subTest(outcome=str(outcome)):
                with self.assertRaises(ContractError):
                    report(
                        outcome=outcome,
                        independence_references=(),
                    )

    def test_blocked_and_invalid_can_lack_usable_evidence(self):
        for outcome in (
            VerificationOutcome.BLOCKED,
            VerificationOutcome.INVALID,
        ):
            with self.subTest(outcome=str(outcome)):
                record = report(
                    outcome=outcome,
                    evidence_references=(),
                    independence_references=(),
                )

                self.assertIs(record.outcome, outcome)

    def test_source_evaluation_must_pass_before_verification(self):
        values = list(verification_context())

        source_assessment = evaluation(
            values[0],
            values[3],
            evaluation_id="source-eval",
            outcome=EvaluationOutcome.FAIL,
        )

        values[4] = source_assessment

        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=source_assessment,
            verification_run=values[5],
            verification_assessment=values[6],
        )

        with self.assertRaises(ContractError):
            validate(record, tuple(values))

    def test_verification_outcome_must_match_independent_evaluation(self):
        values = verification_context(
            verification_evaluation_outcome=EvaluationOutcome.FAIL
        )

        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=values[4],
            verification_run=values[5],
            verification_assessment=values[6],
            outcome=VerificationOutcome.VERIFIED,
        )

        with self.assertRaises(ContractError):
            validate(record, values)

    def test_verification_execution_identity_must_be_distinct(self):
        with self.assertRaises(ContractError):
            report(
                verification_execution_id="source-run",
            )

    def test_verification_execution_digest_must_be_distinct(self):
        values = verification_context()

        with self.assertRaises(ContractError):
            report(
                goal=values[0],
                snapshot=values[1],
                source_run=values[3],
                source_assessment=values[4],
                verification_run=values[5],
                verification_assessment=values[6],
                verification_execution_sha256=(
                    values[3].execution_sha256
                ),
            )

    def test_verification_evaluation_identity_must_be_distinct(self):
        with self.assertRaises(ContractError):
            report(
                verification_evaluation_id="source-eval",
            )

    def test_verification_evaluation_digest_must_be_distinct(self):
        values = verification_context()

        with self.assertRaises(ContractError):
            report(
                goal=values[0],
                snapshot=values[1],
                source_run=values[3],
                source_assessment=values[4],
                verification_run=values[5],
                verification_assessment=values[6],
                verification_evaluation_sha256=(
                    values[4].evaluation_sha256
                ),
            )

    def test_both_executions_must_target_the_same_candidate_snapshot(self):
        values = list(verification_context())

        different_snapshot = replace(
            values[1],
            snapshot_id="different-candidate",
            code_identity="b" * 64,
        )

        changed_run = replace(
            values[5],
            system_snapshot_id=different_snapshot.snapshot_id,
            system_snapshot_sha256=different_snapshot.snapshot_sha256,
        )

        changed_assessment = evaluation(
            values[0],
            changed_run,
            evaluation_id="verification-eval",
            outcome=EvaluationOutcome.PASS,
        )

        values[5] = changed_run
        values[6] = changed_assessment

        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=values[4],
            verification_run=changed_run,
            verification_assessment=changed_assessment,
        )

        with self.assertRaises(ContractError):
            validate(record, tuple(values))

    def test_goal_snapshot_target_identity_must_match(self):
        values = verification_context()

        changed_snapshot = replace(
            values[1],
            system_id="another-agent",
        )

        with self.assertRaises(ContractError):
            values_record = report(
                goal=values[0],
                snapshot=changed_snapshot,
                source_run=values[3],
                source_assessment=values[4],
                verification_run=values[5],
                verification_assessment=values[6],
            )
            values_record.validate_against(
                goal=values[0],
                snapshot=changed_snapshot,
                source_execution=values[3],
                source_evaluation=values[4],
                verification_execution=values[5],
                verification_evaluation=values[6],
            )

    def test_stale_source_execution_digest_is_rejected(self):
        values = verification_context()

        changed_source = replace(
            values[3],
            output_references=("changed-source-output",),
        )

        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=values[4],
            verification_run=values[5],
            verification_assessment=values[6],
        )

        with self.assertRaises(ContractError):
            record.validate_against(
                goal=values[0],
                snapshot=values[1],
                source_execution=changed_source,
                source_evaluation=values[4],
                verification_execution=values[5],
                verification_evaluation=values[6],
            )

    def test_stale_source_evaluation_digest_is_rejected(self):
        values = verification_context()

        changed_evaluation = replace(
            values[4],
            rationale="Changed source rationale",
        )

        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=values[4],
            verification_run=values[5],
            verification_assessment=values[6],
        )

        with self.assertRaises(ContractError):
            record.validate_against(
                goal=values[0],
                snapshot=values[1],
                source_execution=values[3],
                source_evaluation=changed_evaluation,
                verification_execution=values[5],
                verification_evaluation=values[6],
            )

    def test_stale_verification_execution_digest_is_rejected(self):
        values = verification_context()

        changed_run = replace(
            values[5],
            trace_references=("changed-verification-trace",),
        )

        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=values[4],
            verification_run=values[5],
            verification_assessment=values[6],
        )

        with self.assertRaises(ContractError):
            record.validate_against(
                goal=values[0],
                snapshot=values[1],
                source_execution=values[3],
                source_evaluation=values[4],
                verification_execution=changed_run,
                verification_evaluation=values[6],
            )

    def test_stale_verification_evaluation_digest_is_rejected(self):
        values = verification_context()

        changed_evaluation = replace(
            values[6],
            uncertainty="Changed verification uncertainty",
        )

        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=values[4],
            verification_run=values[5],
            verification_assessment=values[6],
        )

        with self.assertRaises(ContractError):
            record.validate_against(
                goal=values[0],
                snapshot=values[1],
                source_execution=values[3],
                source_evaluation=values[4],
                verification_execution=values[5],
                verification_evaluation=changed_evaluation,
            )

    def test_cross_scope_records_are_rejected(self):
        values = verification_context()

        for field in ("tenant_id", "project_id"):
            with self.subTest(field=field):
                changed_run = replace(
                    values[5],
                    **{field: "other"},
                )

                changed_assessment = evaluation(
                    values[0],
                    changed_run,
                    evaluation_id="verification-eval",
                    outcome=EvaluationOutcome.PASS,
                    **{field: "other"},
                )

                record = report(
                    goal=values[0],
                    snapshot=values[1],
                    source_run=values[3],
                    source_assessment=values[4],
                    verification_run=changed_run,
                    verification_assessment=changed_assessment,
                )

                with self.assertRaises(ContractError):
                    record.validate_against(
                        goal=values[0],
                        snapshot=values[1],
                        source_execution=values[3],
                        source_evaluation=values[4],
                        verification_execution=changed_run,
                        verification_evaluation=changed_assessment,
                    )

    def test_plain_strings_are_not_verification_outcomes(self):
        with self.assertRaises(ContractError):
            report(outcome="VERIFIED")

    def test_blank_required_text_is_rejected(self):
        for field in (
            "verification_id",
            "verifier_id",
            "verifier_version",
            "protocol_reference",
            "rationale",
            "uncertainty",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ContractError):
                    report(**{field: " "})

    def test_digests_are_strict_lowercase_sha256(self):
        for field in (
            "goal_contract_sha256",
            "system_snapshot_sha256",
            "source_execution_sha256",
            "source_evaluation_sha256",
            "verification_execution_sha256",
            "verification_evaluation_sha256",
            "protocol_sha256",
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
                        report(**{field: bad})

    def test_mutable_and_malformed_collections_are_rejected(self):
        for field in (
            "independence_references",
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
                        report(**{field: bad})

    def test_report_is_immutable(self):
        record = report()

        with self.assertRaises(FrozenInstanceError):
            record.rationale = "changed"

    def test_payload_mutation_does_not_change_record(self):
        record = report()
        digest = record.verification_sha256

        payload = record.canonical_payload()
        payload["rationale"] = "changed"

        self.assertEqual(
            record.verification_sha256,
            digest,
        )

    def test_hash_is_deterministic_and_payload_is_json_serializable(self):
        first = report()
        second = report()

        self.assertEqual(
            first.verification_sha256,
            second.verification_sha256,
        )

        self.assertIsInstance(
            json.loads(
                json.dumps(first.canonical_payload())
            ),
            dict,
        )

    def test_hash_tracks_material_verification_changes(self):
        original = report()

        for field, value in (
            ("verifier_version", "2"),
            ("protocol_sha256", "b" * 64),
            (
                "independence_references",
                ("another-independence-attestation",),
            ),
            (
                "evidence_references",
                ("another-verification-evidence",),
            ),
            (
                "uncertainty",
                "Different uncertainty statement",
            ),
        ):
            with self.subTest(field=field):
                changed = replace(
                    original,
                    **{field: value},
                )

                self.assertNotEqual(
                    original.verification_sha256,
                    changed.verification_sha256,
                )

    def test_same_evaluator_implementation_is_not_structurally_forbidden(self):
        values = verification_context()

        self.assertEqual(
            values[4].evaluator_id,
            values[6].evaluator_id,
        )

        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=values[4],
            verification_run=values[5],
            verification_assessment=values[6],
        )

        validate(record, values)

    def test_report_has_no_authorization_or_lifecycle_fields(self):
        names = {
            field.name
            for field in fields(VerificationReport)
        }

        forbidden = {
            "authorization",
            "approval",
            "deployment_authority",
            "lifecycle_state",
            "next_state",
            "complete",
            "is_complete",
        }

        self.assertTrue(names.isdisjoint(forbidden))

    def test_link_validation_rejects_untyped_inputs(self):
        values = verification_context()

        record = report(
            goal=values[0],
            snapshot=values[1],
            source_run=values[3],
            source_assessment=values[4],
            verification_run=values[5],
            verification_assessment=values[6],
        )

        with self.assertRaises(ContractError):
            record.validate_against(
                goal={},
                snapshot=values[1],
                source_execution=values[3],
                source_evaluation=values[4],
                verification_execution=values[5],
                verification_evaluation=values[6],
            )

    def test_record_operations_do_not_execute_or_resolve_references(self):
        values = verification_context()

        error = AssertionError(
            "Verification record attempted I/O or execution"
        )

        with patch("subprocess.run", side_effect=error), \
             patch("builtins.open", side_effect=error), \
             patch("pathlib.Path.open", side_effect=error), \
             patch("socket.socket", side_effect=error):

            record = report(
                goal=values[0],
                snapshot=values[1],
                source_run=values[3],
                source_assessment=values[4],
                verification_run=values[5],
                verification_assessment=values[6],
                protocol_reference="nonexistent://verification-protocol",
                independence_references=(
                    "nonexistent://independence-attestation",
                ),
                evidence_references=(
                    "nonexistent://verification-evidence",
                ),
            )

            validate(record, values)

            self.assertTrue(
                record.verification_sha256
            )


if __name__ == "__main__":
    unittest.main()
