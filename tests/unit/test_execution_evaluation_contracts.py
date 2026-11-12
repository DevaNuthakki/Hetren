"""Behavioral contract tests; runnable with unittest or pytest."""

from dataclasses import FrozenInstanceError, replace
import json
import unittest
from unittest.mock import patch

from packages.contracts import (
    ContractError, EvaluationOutcome, EvaluationRecord, ExecutionRecord,
    ExecutionStatus, GoalContract, MethodProposal, SystemSnapshot,
)


DIGEST = "a" * 64


def context():
    goal = GoalContract(
        tenant_id="local", project_id="agent-repair", contract_id="goal-1",
        contract_version="1", system_id="agent-1", system_version_id="agent-v1",
        claim_scope="bounded agent repair", objective="Return the correct tool result",
        metrics=("correct-result",), minimum_effect="all required checks pass",
        baseline_reference="baseline-1", acceptance_predicates=("correct tool result",),
        hard_constraints=(), invariants=(), eligible_changes=("adapter code",),
        budget_constraints=("declared call budget",), reviewer_version="reviewer-v1",
        evaluator_version="evaluator-v1", evidence_requirements=("tool trace",),
        protected_evaluation_requirements=("frozen grader",),
        uncertainty_policy="preserve uncertainty", failure_invalidity_policy="retain both",
        verification_requirements=("separate protected run",),
    )
    snapshot = SystemSnapshot(
        tenant_id=goal.tenant_id, project_id=goal.project_id, snapshot_id="snapshot-1",
        system_id=goal.system_id, system_version_id=goal.system_version_id,
        environment_family="agent", component_version_ids=("adapter-v1",),
        provider_binding_ids=(), adapter_binding_ids=("adapter-1",),
        evaluator_binding_ids=("evaluator-1",), code_identity=DIGEST,
        data_identity=None, prompt_identity=DIGEST, runtime_identity="python-runner-v1",
        state_references=("initial-state-1",), artifact_references=(),
    )
    proposal = MethodProposal(
        tenant_id=goal.tenant_id, project_id=goal.project_id, proposal_id="proposal-1",
        proposal_version="1", goal_contract_id=goal.contract_id,
        system_snapshot_id=snapshot.snapshot_id, question="Is serialization responsible?",
        alternatives=("wrong argument", "wrong serialization"),
        expected_outcomes=("different tool payload",), controls=("unchanged rerun",),
        generated_program='raise AssertionError("proposal must stay inert")',
        dependencies=(), stopping_rule="stop at the declared budget",
    )
    return goal, snapshot, proposal


def execution(goal=None, snapshot=None, proposal=None, **changes):
    if goal is None:
        goal, snapshot, proposal = context()
    values = dict(
        tenant_id=goal.tenant_id, project_id=goal.project_id, execution_id="run-1",
        goal_contract_id=goal.contract_id, goal_contract_sha256=goal.contract_sha256,
        system_snapshot_id=snapshot.snapshot_id,
        system_snapshot_sha256=snapshot.snapshot_sha256,
        method_proposal_id=proposal.proposal_id,
        method_proposal_sha256=proposal.proposal_sha256,
        runner_id="runner-1", runner_version="1", environment_reference="environment-1",
        execution_manifest_reference="manifest-1", status=ExecutionStatus.COMPLETED,
        exit_code=0, termination_reason=None, input_references=("input-1",),
        output_references=("output-1",), trace_references=("trace-1",), limitations=(),
    )
    values.update(changes)
    return ExecutionRecord(**values)


def evaluation(goal=None, run=None, **changes):
    if goal is None:
        goal, snapshot, proposal = context()
        run = execution(goal, snapshot, proposal)
    values = dict(
        tenant_id=goal.tenant_id, project_id=goal.project_id, evaluation_id="eval-1",
        goal_contract_id=goal.contract_id, goal_contract_sha256=goal.contract_sha256,
        execution_id=run.execution_id, execution_sha256=run.execution_sha256,
        evaluator_id="evaluator-1", evaluator_version=goal.evaluator_version,
        protocol_reference="protocol-1", protocol_sha256=DIGEST,
        outcome=EvaluationOutcome.FAIL, measurement_references=("measurement-1",),
        evidence_references=("evidence-1",), rationale="The observed tool result is wrong",
        uncertainty="One controlled case; no generalization claim", limitations=(),
    )
    values.update(changes)
    return EvaluationRecord(**values)


class ExecutionEvaluationContractTests(unittest.TestCase):
    def test_valid_execution_links(self):
        goal, snapshot, proposal = context()
        execution(goal, snapshot, proposal).validate_against(
            goal=goal, snapshot=snapshot, proposal=proposal,
        )

    def test_completed_execution_can_fail_evaluation(self):
        goal, snapshot, proposal = context()
        run = execution(goal, snapshot, proposal)
        assessment = evaluation(goal, run)
        assessment.validate_against(goal=goal, execution=run)
        self.assertIs(run.status, ExecutionStatus.COMPLETED)
        self.assertIs(assessment.outcome, EvaluationOutcome.FAIL)

    def test_timeout_can_decisively_fail_a_deadline(self):
        goal, snapshot, proposal = context()
        run = execution(goal, snapshot, proposal, status=ExecutionStatus.TIMED_OUT,
                        exit_code=None, termination_reason="Deadline exceeded")
        evaluation(goal, run, rationale="Mandatory deadline exceeded").validate_against(
            goal=goal, execution=run,
        )

    def test_blocked_attempt_needs_no_invented_runtime_outputs(self):
        goal, snapshot, proposal = context()
        run = execution(
            goal, snapshot, proposal, status=ExecutionStatus.BLOCKED, exit_code=None,
            environment_reference=None, execution_manifest_reference=None,
            termination_reason="Required tool unavailable before launch",
            output_references=(), trace_references=(),
        )
        run.validate_against(goal=goal, snapshot=snapshot, proposal=proposal)
        evaluation(
            goal, run, outcome=EvaluationOutcome.BLOCKED,
            evidence_references=(), measurement_references=(),
            rationale="No target execution available",
        ).validate_against(goal=goal, execution=run)

    def test_blocked_prelaunch_attempt_rejects_exit_code(self):
        with self.assertRaises(ContractError):
            execution(status=ExecutionStatus.BLOCKED, termination_reason="No tool")

    def test_abnormal_execution_requires_explanation(self):
        for status in ExecutionStatus:
            if status is ExecutionStatus.COMPLETED:
                continue
            with self.subTest(status=str(status)), self.assertRaises(ContractError):
                execution(status=status, exit_code=None)

    def test_all_terminal_statuses_can_be_preserved(self):
        for status in ExecutionStatus:
            with self.subTest(status=str(status)):
                record = execution(status=status, exit_code=None,
                                   termination_reason="Recorded terminal condition")
                self.assertIs(record.status, status)

    def test_completed_runner_rejects_nonzero_exit(self):
        for code in (1, -9):
            with self.subTest(code=code), self.assertRaises(ContractError):
                execution(exit_code=code)

    def test_exit_code_rejects_bool_float_and_text(self):
        for code in (True, False, 0.0, "0"):
            with self.subTest(code=code), self.assertRaises(ContractError):
                execution(exit_code=code)

    def test_failed_runner_can_preserve_negative_exit_code(self):
        run = execution(status=ExecutionStatus.FAILED, exit_code=-9,
                        termination_reason="Runner killed")
        self.assertEqual(run.exit_code, -9)

    def test_enum_strings_are_not_accepted_as_typed_states(self):
        for status in ("completed", EvaluationOutcome.PASS):
            with self.subTest(status=str(status)), self.assertRaises(ContractError):
                execution(status=status)
        for outcome in ("PASS", ExecutionStatus.COMPLETED):
            with self.subTest(outcome=str(outcome)), self.assertRaises(ContractError):
                evaluation(outcome=outcome)

    def test_all_five_evaluation_outcomes_remain_distinct(self):
        digests = set()
        for outcome in EvaluationOutcome:
            record = evaluation(outcome=outcome)
            self.assertEqual(record.canonical_payload()["outcome"], outcome.value)
            digests.add(record.evaluation_sha256)
        self.assertEqual(len(digests), 5)

    def test_measured_outcomes_require_evidence_references(self):
        for outcome in (EvaluationOutcome.PASS, EvaluationOutcome.FAIL,
                        EvaluationOutcome.INCONCLUSIVE):
            with self.subTest(outcome=str(outcome)), self.assertRaises(ContractError):
                evaluation(outcome=outcome, evidence_references=())

    def test_unavailable_or_invalid_evidence_is_recordable(self):
        for outcome in (EvaluationOutcome.BLOCKED, EvaluationOutcome.INVALID):
            with self.subTest(outcome=str(outcome)):
                record = evaluation(outcome=outcome, evidence_references=(),
                                    measurement_references=())
                self.assertIs(record.outcome, outcome)

    def test_blank_explanations_are_rejected(self):
        for field in ("rationale", "uncertainty"):
            with self.subTest(field=field), self.assertRaises(ContractError):
                evaluation(**{field: "  "})

    def test_blank_identities_and_optional_references_are_rejected(self):
        for make, names in (
            (execution, ("execution_id", "runner_version", "environment_reference",
                         "execution_manifest_reference", "termination_reason")),
            (evaluation, ("evaluation_id", "evaluator_id", "protocol_reference")),
        ):
            for name in names:
                with self.subTest(name=name), self.assertRaises(ContractError):
                    make(**{name: " "})

    def test_digests_are_strict_lowercase_sha256(self):
        for make, names in (
            (execution, ("goal_contract_sha256", "system_snapshot_sha256",
                         "method_proposal_sha256")),
            (evaluation, ("goal_contract_sha256", "execution_sha256", "protocol_sha256")),
        ):
            for name in names:
                for bad in (None, 7, "a" * 63, "g" * 64, "A" * 64, DIGEST + "\n"):
                    with self.subTest(field=name, bad=bad), self.assertRaises(ContractError):
                        make(**{name: bad})

    def test_mutable_and_malformed_collections_are_rejected(self):
        for make, names in (
            (execution, ("input_references", "output_references", "trace_references", "limitations")),
            (evaluation, ("measurement_references", "evidence_references", "limitations")),
        ):
            for name in names:
                for bad in (["reference"], "reference", ([],), (" ",), (1,)):
                    with self.subTest(name=name, bad=bad), self.assertRaises(ContractError):
                        make(**{name: bad})

    def test_both_records_are_immutable(self):
        for record, field in ((execution(), "runner_version"), (evaluation(), "rationale")):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(record, field, "changed")

    def test_payload_mutation_does_not_change_record(self):
        for record, field, digest_name in (
            (execution(), "runner_version", "execution_sha256"),
            (evaluation(), "rationale", "evaluation_sha256"),
        ):
            digest = getattr(record, digest_name)
            payload = record.canonical_payload()
            payload[field] = "changed"
            self.assertEqual(getattr(record, digest_name), digest)

    def test_hashes_are_deterministic_and_payloads_json_serializable(self):
        for make, digest_name in ((execution, "execution_sha256"),
                                  (evaluation, "evaluation_sha256")):
            first, second = make(), make()
            self.assertEqual(getattr(first, digest_name), getattr(second, digest_name))
            self.assertIsInstance(json.loads(json.dumps(first.canonical_payload())), dict)

    def test_execution_hash_tracks_material_changes(self):
        original = execution()
        for name, value in (
            ("runner_version", "2"), ("environment_reference", "env-2"),
            ("execution_manifest_reference", "manifest-2"),
            ("goal_contract_sha256", "b" * 64), ("system_snapshot_sha256", "b" * 64),
            ("method_proposal_sha256", "b" * 64), ("trace_references", ("trace-2",)),
        ):
            with self.subTest(name=name):
                self.assertNotEqual(original.execution_sha256,
                                    replace(original, **{name: value}).execution_sha256)

    def test_evaluation_hash_tracks_material_changes(self):
        original = evaluation()
        for name, value in (
            ("protocol_sha256", "b" * 64), ("execution_sha256", "b" * 64),
            ("evaluator_version", "2"), ("evidence_references", ("evidence-2",)),
            ("measurement_references", ("measurement-2",)), ("uncertainty", "Changed limits"),
        ):
            with self.subTest(name=name):
                self.assertNotEqual(original.evaluation_sha256,
                                    replace(original, **{name: value}).evaluation_sha256)

    def test_execution_rejects_changed_goal_snapshot_or_proposal(self):
        goal, snapshot, proposal = context()
        run = execution(goal, snapshot, proposal)
        for name, changed in (
            ("goal", replace(goal, objective="Another objective")),
            ("snapshot", replace(snapshot, state_references=("other-state",))),
            ("proposal", replace(proposal, generated_program="another program")),
        ):
            args = dict(goal=goal, snapshot=snapshot, proposal=proposal)
            args[name] = changed
            with self.subTest(name=name), self.assertRaises(ContractError):
                run.validate_against(**args)

    def test_execution_rejects_wrong_ids_even_with_matching_hashes(self):
        goal, snapshot, proposal = context()
        run = execution(goal, snapshot, proposal)
        for name in ("goal_contract_id", "system_snapshot_id", "method_proposal_id"):
            with self.subTest(name=name), self.assertRaises(ContractError):
                replace(run, **{name: "other"}).validate_against(
                    goal=goal, snapshot=snapshot, proposal=proposal,
                )

    def test_execution_rejects_cross_scope_objects_even_when_hashes_match(self):
        goal, snapshot, proposal = context()
        for field in ("tenant_id", "project_id"):
            for name in ("snapshot", "proposal"):
                args = dict(goal=goal, snapshot=snapshot, proposal=proposal)
                args[name] = replace(args[name], **{field: "other"})
                run = execution(**args)
                with self.subTest(name=name, field=field), self.assertRaises(ContractError):
                    run.validate_against(**args)

    def test_execution_rejects_snapshot_for_another_target(self):
        goal, snapshot, proposal = context()
        changed = replace(snapshot, system_id="other")
        with self.assertRaises(ContractError):
            execution(goal, changed, proposal).validate_against(
                goal=goal, snapshot=changed, proposal=proposal,
            )

    def test_candidate_version_links_do_not_rewrite_frozen_goal(self):
        goal, snapshot, proposal = context()
        original_goal_digest = goal.contract_sha256
        candidate = replace(snapshot, snapshot_id="candidate-snapshot",
                            system_version_id="candidate-v2", code_identity="b" * 64)
        candidate_proposal = replace(proposal, system_snapshot_id=candidate.snapshot_id)
        run = execution(goal, candidate, candidate_proposal)
        run.validate_against(goal=goal, snapshot=candidate, proposal=candidate_proposal)
        self.assertEqual(goal.contract_sha256, original_goal_digest)
        # Link consistency is not permission to use this candidate version.

    def test_execution_rejects_misbound_proposal_even_with_matching_hash(self):
        goal, snapshot, proposal = context()
        for field in ("goal_contract_id", "system_snapshot_id"):
            changed = replace(proposal, **{field: "other"})
            with self.subTest(field=field), self.assertRaises(ContractError):
                execution(goal, snapshot, changed).validate_against(
                    goal=goal, snapshot=snapshot, proposal=changed,
                )

    def test_evaluation_rejects_stale_execution_digest(self):
        goal, snapshot, proposal = context()
        run = execution(goal, snapshot, proposal)
        with self.assertRaises(ContractError):
            evaluation(goal, run).validate_against(
                goal=goal, execution=replace(run, output_references=("other-output",)),
            )

    def test_evaluation_rejects_ids_goal_digest_and_evaluator_mismatch(self):
        goal, snapshot, proposal = context()
        run = execution(goal, snapshot, proposal)
        for name, value in (
            ("execution_id", "other"), ("goal_contract_id", "other"),
            ("goal_contract_sha256", "b" * 64), ("evaluator_version", "other"),
        ):
            with self.subTest(name=name), self.assertRaises(ContractError):
                evaluation(goal, run, **{name: value}).validate_against(goal=goal, execution=run)

    def test_evaluation_rejects_execution_bound_to_another_goal(self):
        goal, snapshot, proposal = context()
        for name, value in (("goal_contract_id", "other"),
                            ("goal_contract_sha256", "b" * 64)):
            run = execution(goal, snapshot, proposal, **{name: value})
            with self.subTest(name=name), self.assertRaises(ContractError):
                evaluation(goal, run).validate_against(goal=goal, execution=run)

    def test_evaluation_rejects_cross_scope_execution_even_with_matching_hash(self):
        goal, snapshot, proposal = context()
        for field in ("tenant_id", "project_id"):
            run = execution(goal, snapshot, proposal, **{field: "other"})
            with self.subTest(field=field), self.assertRaises(ContractError):
                evaluation(goal, run).validate_against(goal=goal, execution=run)

    def test_link_validation_rejects_untyped_inputs(self):
        goal, snapshot, proposal = context()
        with self.assertRaises(ContractError):
            execution(goal, snapshot, proposal).validate_against(
                goal={}, snapshot=snapshot, proposal=proposal,
            )
        with self.assertRaises(ContractError):
            evaluation().validate_against(goal=goal, execution={})

    def test_record_operations_do_not_execute_programs_or_resolve_references(self):
        goal, snapshot, proposal = context()
        error = AssertionError("Record attempted I/O or execution")
        with patch("subprocess.run", side_effect=error), \
             patch("builtins.open", side_effect=error), \
             patch("pathlib.Path.open", side_effect=error), \
             patch("socket.socket", side_effect=error):
            run = execution(goal, snapshot, proposal,
                            execution_manifest_reference="nonexistent://manifest")
            run.validate_against(goal=goal, snapshot=snapshot, proposal=proposal)
            assessment = evaluation(goal, run, evidence_references=("nonexistent://evidence",))
            assessment.validate_against(goal=goal, execution=run)
            self.assertTrue(assessment.evaluation_sha256)


if __name__ == "__main__":
    unittest.main()
