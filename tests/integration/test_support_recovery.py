from dataclasses import FrozenInstanceError, replace
from functools import partial
import json
import socket

import pytest

from environments.support.faults import IdentifierMappingSwap, inject_fault
from environments.support.fixtures import SupportEnvironment
from environments.support.tools import (
    DIAGNOSTIC_TOOLS,
    MAINTENANCE_TOOL_DESCRIPTIONS,
    MAINTENANCE_TOOL_SCHEMAS,
    RECOVERY_TOOLS,
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, StageStatus, ToolGateway
from packages.contracts import ContractError
from packages.integrations.openai_agents import (
    RunProvenance,
    gateway_function_tools,
    run_agent,
)
from packages.integrations.run_ids import RunIdAllocator
from packages.support_agent import ScriptedSupportModel, build_support_agent, task_message
from packages.support_evaluator import (
    EXAMPLES,
    SupportVerdict,
    assert_no_leaks,
    fault,
    scan_content,
)
from packages.support_recovery import (
    ApplicationStatus,
    CandidateStatus,
    CorrectionAction,
    DiagnosisOutcome,
    EvidenceStatus,
    FrozenOutcome,
    apply_candidate,
    assess_evidence,
    diagnose,
    freeze_outcome,
    propose_candidate,
    recover,
    rollback_application,
    run_probes,
)
from packages.support_recovery.recovery import HetrenOutcome
from packages.verification.support_verification import SupportVerifier


AGENT_TOOLS = ("read_ticket", "lookup_account", "route_ticket")
SWAP = ("C-3103", "C-3104")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


# Test harness


def _environment(swap=None) -> SupportEnvironment:
    environment = SupportEnvironment()

    if swap is not None:
        inject_fault(environment, IdentifierMappingSwap(*swap))

    return environment


def _gated(environment, registry, descriptions, schemas):
    return [
        GatedTool(name, partial(function, environment), schemas[name], descriptions[name])
        for name, function in registry.items()
    ]


def _diagnostic_tools(environment):
    return _gated(environment, DIAGNOSTIC_TOOLS, MAINTENANCE_TOOL_DESCRIPTIONS, MAINTENANCE_TOOL_SCHEMAS)


def _recovery_tools(environment):
    return _gated(environment, RECOVERY_TOOLS, MAINTENANCE_TOOL_DESCRIPTIONS, MAINTENANCE_TOOL_SCHEMAS)


def _run(environment, ticket_id, run_id, allowed=AGENT_TOOLS):
    gateway = ToolGateway(
        tools=_gated(environment, SUPPORT_TOOLS, SUPPORT_TOOL_DESCRIPTIONS, SUPPORT_TOOL_SCHEMAS),
        policy=AllowListPolicy(allowed),
        state_sha256=environment.state_sha256,
    )
    agent = build_support_agent(
        environment=environment, tools=gateway_function_tools(gateway),
        model=ScriptedSupportModel(),
    )
    return run_agent(
        agent=agent, task_input=task_message(ticket_id), gateway=gateway,
        run_id=run_id, provenance=RunProvenance.SCRIPTED,
    )


def _withhold_account_observation(diagnosis_input):
    """Harness-side evidence loss: drop the account call's execution records."""
    withheld = json.loads(json.dumps(diagnosis_input))
    lookup = next(
        record["invocation_id"] for record in withheld["stage_records"]
        if record["tool_name"] == "lookup_account"
    )
    withheld["stage_records"] = [
        record for record in withheld["stage_records"]
        if not (record["invocation_id"] == lookup and record["stage"] in ("attempted", "observed"))
    ]
    return withheld


class Harness:
    """Runs one example end to end the way the real harness will."""

    def __init__(self, example_name, regression_allowed=AGENT_TOOLS):
        self.spec = EXAMPLES[example_name]
        self.example_name = example_name
        self.swap = (
            None if self.spec.fault_id is None
            else tuple(fault(self.spec.fault_id).parameters.values())
        )
        self.environment = _environment(self.swap)
        self.run_ids = RunIdAllocator()
        self.verifier = SupportVerifier()
        self.regression_allowed = regression_allowed
        self.diagnosis_inputs = []

    def run(self):
        run_id = self.run_ids.allocate()
        self.verifier.register_run(
            run_id=run_id,
            example_name=self.example_name,
            fault_payload=(
                None if self.swap is None
                else IdentifierMappingSwap(*self.swap).canonical_payload()
            ),
        )
        record = _run(self.environment, self.spec.target_ticket_id, run_id)
        diagnosis_input = record.evidence_payload()

        if self.spec.evidence_condition.value == "account_observation_withheld":
            diagnosis_input = _withhold_account_observation(diagnosis_input)

        self.diagnosis_inputs.append(diagnosis_input)

        def rerun():
            rerun_input = _run(
                self.environment, self.spec.target_ticket_id, self.run_ids.allocate(),
            ).evidence_payload()
            self.diagnosis_inputs.append(rerun_input)
            return rerun_input

        self.frozen = recover(
            diagnosis_input,
            diagnostic_tools=_diagnostic_tools(self.environment),
            recovery_tools=_recovery_tools(self.environment),
            state_sha256=self.environment.state_sha256,
            rerun=rerun,
        )
        return self.frozen

    def verify(self):
        return self.verifier.verify(
            frozen=self.frozen,
            environment=self.environment,
            regression_runner=lambda ticket_id: _run(
                self.environment, ticket_id, self.run_ids.allocate(), self.regression_allowed,
            ),
        )


# Evidence sufficiency


def test_complete_evidence_is_sufficient():
    record = _run(_environment(), "T-1003", "run-0001")

    assessment = assess_evidence(record.evidence_payload())

    assert assessment.status is EvidenceStatus.SUFFICIENT
    assert assessment.missing == ()


def test_withheld_account_observation_names_every_missing_item():
    record = _run(_environment(SWAP), "T-1003", "run-0001")
    withheld = _withhold_account_observation(record.evidence_payload())

    assessment = assess_evidence(withheld)

    assert assessment.status is EvidenceStatus.INSUFFICIENT
    assert list(assessment.missing) == [
        {"requirement": "contiguous_stage_records", "expected_sequence": 6},
        {"requirement": "attempted_stage", "invocation_id": "call-0002", "tool_name": "lookup_account"},
        {"requirement": "observed_stage", "invocation_id": "call-0002", "tool_name": "lookup_account"},
        {"requirement": "account_observation", "tool_name": "lookup_account", "for_invocation_id": "call-0001"},
    ]


def test_insufficient_evidence_is_not_inconclusive_and_claims_no_fix():
    record = _run(_environment(SWAP), "T-1003", "run-0001")
    withheld = _withhold_account_observation(record.evidence_payload())

    diagnosis = diagnose(withheld)

    assert diagnosis.outcome is DiagnosisOutcome.INSUFFICIENT_EVIDENCE
    assert diagnosis.findings == ()
    assert "inconclusive" not in json.dumps(diagnosis.canonical_payload()).lower()


@pytest.mark.parametrize(
    ("mutate", "requirement"),
    [
        (lambda data: data.update(record_type="Other"), "agent_run_record"),
        (
            lambda data: data.update(stage_records=[r for r in data["stage_records"] if r["sequence"] != 3]),
            "observed_stage",
        ),
        (
            lambda data: data["sdk_evidence"]["discrepancies"].append({"kind": "trace_missing"}),
            "consistent_sdk_evidence",
        ),
        (lambda data: data.update(stage_records=[]), "ticket_observation"),
        (
            lambda data: data.update(stage_records=data["stage_records"][:4]),
            "gateway_records_for_finished_tool",
        ),
    ],
)
def test_each_sufficiency_requirement_is_enforced(mutate, requirement):
    data = json.loads(json.dumps(_run(_environment(), "T-1003", "run-0001").evidence_payload()))
    mutate(data)

    assessment = assess_evidence(data)

    assert assessment.status is EvidenceStatus.INSUFFICIENT
    assert requirement in [item["requirement"] for item in assessment.missing]


# Diagnosis


@pytest.mark.parametrize("ticket_id", ["T-1001", "T-1002", "T-1003", "T-1004", "T-1005"])
def test_healthy_runs_are_diagnosed_healthy_and_nothing_is_proposed(ticket_id):
    environment = _environment()
    record = _run(environment, ticket_id, "run-0001")
    before = environment.state_sha256()

    frozen = recover(
        record.evidence_payload(),
        diagnostic_tools=_diagnostic_tools(environment),
        recovery_tools=_recovery_tools(environment),
        state_sha256=environment.state_sha256,
        rerun=lambda: pytest.fail("healthy runs must not be re-run"),
    )

    assert frozen.outcome.diagnosis.outcome is DiagnosisOutcome.HEALTHY
    assert frozen.outcome.probe_records == ()
    assert frozen.outcome.candidate is None
    assert frozen.outcome.claims_fix is False
    assert environment.state_sha256() == before


def test_faulty_run_on_an_unaffected_ticket_is_healthy():
    record = _run(_environment(SWAP), "T-1002", "run-0001")

    assert diagnose(record.evidence_payload()).outcome is DiagnosisOutcome.HEALTHY


def test_mapping_inconsistency_is_detected_from_evidence():
    record = _run(_environment(SWAP), "T-1003", "run-0001")

    diagnosis = diagnose(record.evidence_payload())

    assert diagnosis.outcome is DiagnosisOutcome.MAPPING_INCONSISTENCY
    (finding,) = diagnosis.findings
    assert finding.canonical_payload() == {
        "ticket_invocation_id": "call-0001",
        "account_invocation_id": "call-0002",
        "ticket_id": "T-1003",
        "ticket_customer_ref": "C-3103",
        "resolved_account_id": "A-2004",
        "account_customer_ref": "C-3104",
    }
    assert diagnosis.implicated_customer_refs == ("C-3103", "C-3104")
    assert diagnosis.diagnosis_sha256 == diagnose(record.evidence_payload()).diagnosis_sha256


# Probes, candidate, application, rollback


def _diagnosed():
    environment = _environment(SWAP)
    record = _run(environment, "T-1003", "run-0001")
    return environment, diagnose(record.evidence_payload())


def test_probes_are_read_only_and_cover_only_implicated_references():
    environment, diagnosis = _diagnosed()
    before = environment.state_sha256()

    probes = run_probes(
        diagnosis, diagnostic_tools=_diagnostic_tools(environment),
        state_sha256=environment.state_sha256,
    )

    assert environment.state_sha256() == before
    observed = [r["payload"]["observation"] for r in probes if r["stage"] == "observed"]
    assert {o["customer_ref"] for o in observed} == {"C-3103", "C-3104"}
    assert {r["payload"]["policy_id"] for r in probes if r["stage"] == "authorized"} == {"allow_list"}


def test_candidate_changes_only_the_implicated_entries():
    environment, diagnosis = _diagnosed()
    probes = run_probes(
        diagnosis, diagnostic_tools=_diagnostic_tools(environment),
        state_sha256=environment.state_sha256,
    )

    candidate = propose_candidate(diagnosis, probes)

    assert candidate.status is CandidateStatus.PROPOSED
    assert candidate.actions == (
        CorrectionAction("C-3103", "A-2003"),
        CorrectionAction("C-3104", "A-2004"),
    )
    assert candidate.diagnosis_sha256 == diagnosis.diagnosis_sha256
    with pytest.raises(FrozenInstanceError):
        candidate.actions = ()  # type: ignore[misc]


def test_candidate_is_undetermined_when_the_owner_is_not_unique():
    _, diagnosis = _diagnosed()
    probes = (
        {"tool_name": "resolve_customer_ref", "stage": "observed", "status": "succeeded",
         "payload": {"observation": {"customer_ref": "C-3103", "account_id": "A-2004"}}},
        {"tool_name": "find_accounts_by_customer_ref", "stage": "observed", "status": "succeeded",
         "payload": {"observation": {"customer_ref": "C-3103", "account_ids": []}}},
    )

    candidate = propose_candidate(diagnosis, probes)

    assert candidate.status is CandidateStatus.UNDETERMINED
    assert candidate.actions == ()


def test_application_is_gated_recorded_and_reversible():
    environment, diagnosis = _diagnosed()
    probes = run_probes(
        diagnosis, diagnostic_tools=_diagnostic_tools(environment),
        state_sha256=environment.state_sha256,
    )
    candidate = propose_candidate(diagnosis, probes)
    faulty_state = environment.state_sha256()

    application = apply_candidate(
        candidate, recovery_tools=_recovery_tools(environment),
        state_sha256=environment.state_sha256,
    )

    assert application.status is ApplicationStatus.APPLIED
    assert application.candidate_sha256 == candidate.candidate_sha256
    assert application.state_before_sha256 == faulty_state
    assert application.state_after_sha256 == environment.state_sha256() != faulty_state
    assert environment.resolve_customer("C-3103") == "A-2003"
    assert environment.resolve_customer("C-3104") == "A-2004"
    authorized = [r for r in application.stage_records if r["stage"] == "authorized"]
    assert {r["payload"]["policy_id"] for r in authorized} == {"all_of"}
    assert application.rollback_actions == (
        CorrectionAction("C-3104", "A-2003"),
        CorrectionAction("C-3103", "A-2004"),
    )
    assert len(application.rollback_reference) == 64

    rollback_application(
        application, recovery_tools=_recovery_tools(environment),
        state_sha256=environment.state_sha256,
    )
    assert environment.state_sha256() == faulty_state


def test_recovery_permission_is_separate_and_scoped_to_the_candidate():
    environment, diagnosis = _diagnosed()
    probes = run_probes(
        diagnosis, diagnostic_tools=_diagnostic_tools(environment),
        state_sha256=environment.state_sha256,
    )
    candidate = propose_candidate(diagnosis, probes)
    widened = replace(candidate, actions=candidate.actions + (CorrectionAction("C-3101", "A-2002"),))
    tampered_scope = replace(widened, actions=(CorrectionAction("C-3101", "A-2002"),))

    from packages.support_recovery.recovery import _scoped_gateway

    gateway = _scoped_gateway(_recovery_tools(environment), environment.state_sha256, candidate.actions)
    result = gateway.invoke("set_customer_mapping", {"customer_ref": "C-3101", "account_id": "A-2002"})
    assert result.status is StageStatus.DENIED
    assert result.records[-1].payload["reason"] == "call_outside_scope"
    assert environment.resolve_customer("C-3101") == "A-2001"

    agent_gateway = ToolGateway(
        tools=_gated(environment, SUPPORT_TOOLS, SUPPORT_TOOL_DESCRIPTIONS, SUPPORT_TOOL_SCHEMAS),
        policy=AllowListPolicy(AGENT_TOOLS),
        state_sha256=environment.state_sha256,
    )
    denied = agent_gateway.invoke("set_customer_mapping", {"customer_ref": "C-3103", "account_id": "A-2003"})
    assert denied.records[-1].payload["reason"] == "unknown_tool"

    with pytest.raises(ContractError, match="exactly"):
        apply_candidate(
            tampered_scope, recovery_tools=_diagnostic_tools(environment),
            state_sha256=environment.state_sha256,
        )


def test_frozen_outcomes_detect_tampering():
    harness = Harness("example_verified_recovery")
    frozen = harness.run()
    frozen.verify_integrity()

    tampered = FrozenOutcome(replace(frozen.outcome, post_recovery_run_id="run-0099"), frozen.frozen_sha256)

    with pytest.raises(ContractError, match="does not match its digest"):
        tampered.verify_integrity()


# End to end with the verifier


def test_correct_run_is_verified_as_no_intervention():
    harness = Harness("example_correct_run")
    frozen = harness.run()

    verification = harness.verify()

    assert frozen.outcome.diagnosis.outcome is DiagnosisOutcome.HEALTHY
    assert verification.evaluator_verdict is SupportVerdict.NO_INTERVENTION_CORRECT
    assert all(check.passed for check in verification.checks)
    assert verification.regression_run_ids == ()


def test_faulty_run_recovers_and_is_verified_with_a_regression_check():
    harness = Harness("example_verified_recovery")
    frozen = harness.run()
    outcome = frozen.outcome

    assert outcome.diagnosis.outcome is DiagnosisOutcome.MAPPING_INCONSISTENCY
    assert outcome.claims_fix is True
    assert outcome.post_recovery_run_id == "run-0002"
    assert outcome.post_recovery_diagnosis.outcome is DiagnosisOutcome.HEALTHY
    assert harness.environment.get_ticket("T-1003").queue_id == "Q-PRIORITY"

    verification = harness.verify()

    assert verification.evaluator_verdict is SupportVerdict.RECOVERY_VERIFIED
    assert verification.regression_run_ids == ("run-0003",)
    assert [(c.name, c.subject, c.passed) for c in verification.checks if c.name == "regression_queue"] == [
        ("regression_queue", "T-1002", True),
    ]
    assert verification.frozen_sha256 == frozen.frozen_sha256


def test_failed_regression_rejects_the_recovery():
    harness = Harness("example_verified_recovery", regression_allowed=("read_ticket", "lookup_account"))
    harness.run()

    verification = harness.verify()

    assert verification.evaluator_verdict is SupportVerdict.RECOVERY_REJECTED


def test_withheld_evidence_is_verified_as_correctly_insufficient():
    harness = Harness("example_insufficient_evidence")
    frozen = harness.run()

    assert frozen.outcome.diagnosis.outcome is DiagnosisOutcome.INSUFFICIENT_EVIDENCE
    assert frozen.outcome.candidate is None
    assert frozen.outcome.probe_records == ()
    assert frozen.outcome.claims_fix is False

    verification = harness.verify()

    assert verification.evaluator_verdict is SupportVerdict.INSUFFICIENT_EVIDENCE_CORRECT


def test_missing_recovery_is_an_incorrect_outcome():
    harness = Harness("example_verified_recovery")
    harness.run()
    harness.frozen = freeze_outcome(
        HetrenOutcome(
            harness.frozen.outcome.run_id, diagnose({"record_type": "AgentRunRecord"}),
            (), None, None, None, None,
        )
    )

    assert harness.verify().evaluator_verdict is SupportVerdict.INCORRECT_OUTCOME


def test_verifier_requires_a_frozen_registered_outcome_and_verifies_once():
    harness = Harness("example_correct_run")
    frozen = harness.run()

    with pytest.raises(ContractError, match="frozen"):
        harness.verifier.verify(
            frozen=frozen.outcome, environment=harness.environment,
            regression_runner=lambda ticket_id: None,
        )

    harness.verify()

    with pytest.raises(ContractError, match="already been verified"):
        harness.verify()

    unregistered = freeze_outcome(replace(frozen.outcome, run_id="run-0042"))
    with pytest.raises(ContractError, match="not registered"):
        harness.verifier.verify(
            frozen=unregistered, environment=harness.environment,
            regression_runner=lambda ticket_id: None,
        )


# Leakage: the exact diagnosis inputs and Hetren's outputs


@pytest.mark.parametrize("example_name", sorted(EXAMPLES))
def test_diagnosis_inputs_and_hetren_outputs_contain_no_evaluator_content(example_name):
    harness = Harness(example_name)
    frozen = harness.run()

    assert harness.diagnosis_inputs

    for index, diagnosis_input in enumerate(harness.diagnosis_inputs):
        assert_no_leaks(scan_content({f"diagnosis_input[{index}]": diagnosis_input}))

    assert_no_leaks(scan_content({"hetren_outcome": frozen.outcome.canonical_payload()}))


@pytest.mark.parametrize("example_name", sorted(EXAMPLES))
def test_harness_passes_only_run_record_evidence_to_hetren(example_name):
    harness = Harness(example_name)
    harness.run()
    allowed_keys = set(_run(_environment(), "T-1001", "run-0001").evidence_payload())

    for diagnosis_input in harness.diagnosis_inputs:
        assert diagnosis_input["record_type"] == "AgentRunRecord"
        assert set(diagnosis_input) == allowed_keys
        assert "agent_output" not in diagnosis_input
        assert "final_message" not in json.dumps(diagnosis_input)


def test_hetren_vocabulary_never_collides_with_evaluator_tokens():
    from packages.support_evaluator import sensitive_tokens
    from packages.support_recovery import EvidenceStatus as Evidence
    import packages.support_recovery.recovery as recovery_module
    import packages.support_recovery.sufficiency as sufficiency_module
    import inspect
    import re

    vocabulary = {item.value for enum in (DiagnosisOutcome, CandidateStatus, ApplicationStatus, Evidence) for item in enum}
    for module in (recovery_module, sufficiency_module):
        vocabulary.update(re.findall(r'"([a-z][a-z0-9_]+)"', inspect.getsource(module)))

    collisions = {
        word for word in vocabulary for token in sensitive_tokens()
        if token.casefold() in word.casefold()
    }

    assert collisions == set()
