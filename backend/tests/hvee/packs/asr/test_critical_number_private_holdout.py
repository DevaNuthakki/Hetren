from __future__ import annotations

import copy
import hashlib
from dataclasses import replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr import critical_number_private_holdout as holdout_module
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
)
from hvee.packs.asr.critical_number_private_holdout import (
    CRITICAL_NUMBER_PRIVATE_COMMITMENT_SCHEME,
    CRITICAL_NUMBER_PRIVATE_HOLDOUT_PLAN_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_KEY,
    CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_VERSION,
    CRITICAL_NUMBER_PRIVATE_HOLDOUT_RUN_SCHEMA_VERSION,
    ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    ASRCriticalNumberPrivateHoldoutCaseCommitment,
    ASRCriticalNumberPrivateHoldoutCaseExecution,
    ASRCriticalNumberPrivateHoldoutExecutionStatus,
    ASRCriticalNumberPrivateHoldoutPlanBundle,
    ASRCriticalNumberPrivateHoldoutPlanDefinition,
    build_critical_number_private_holdout_blind_run,
    build_critical_number_private_holdout_plan,
    build_critical_number_private_holdout_plan_revision,
    calculate_critical_number_private_commitment,
    calculate_critical_number_private_holdout_sha256,
    verify_critical_number_private_holdout_blind_run,
    verify_critical_number_private_holdout_plan,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _salt(label: str) -> str:
    return f"private-{label}-" + ("s" * 32)


def _commitment(
    *,
    case_id: str,
    slices: tuple[str, ...],
) -> ASRCriticalNumberPrivateHoldoutCaseCommitment:
    return ASRCriticalNumberPrivateHoldoutCaseCommitment(
        case_token=calculate_critical_number_private_commitment(
            payload={"case_id": case_id},
            private_salt=_salt(f"{case_id}-token"),
        ),
        case_payload_sha256=calculate_critical_number_private_commitment(
            payload={
                "reference": f"private reference {case_id}",
                "generated": f"private generated {case_id}",
            },
            private_salt=_salt(f"{case_id}-payload"),
        ),
        expected_result_sha256=calculate_critical_number_private_commitment(
            payload={"expected": f"private expected {case_id}"},
            private_salt=_salt(f"{case_id}-expected"),
        ),
        provenance_sha256=calculate_critical_number_private_commitment(
            payload={"provenance": f"private source {case_id}"},
            private_salt=_salt(f"{case_id}-provenance"),
        ),
        slice_keys=slices,
    )


def _cases() -> tuple[ASRCriticalNumberPrivateHoldoutCaseCommitment, ...]:
    values = (
        _commitment(
            case_id="dosage-substitution",
            slices=("dangerous", "measurement", "substitution"),
        ),
        _commitment(
            case_id="currency-equivalence",
            slices=("currency", "equivalence"),
        ),
        _commitment(
            case_id="unsupported-fraction",
            slices=("unsupported",),
        ),
    )
    return tuple(sorted(values, key=lambda value: value.case_token))


def _plan_definition(
    **changes: object,
) -> ASRCriticalNumberPrivateHoldoutPlanDefinition:
    values: dict[str, object] = {
        "plan_id": "critical-number-private-certification-plan",
        "plan_version": "1.0.0",
        "run_id": "critical-number-private-certification-run-001",
        "holdout_set_key": "hetren.asr.critical-number-private-set.en-us",
        "holdout_set_version": "1.0.0",
        "holdout_manifest_sha256": _digest("holdout-manifest"),
        "population_snapshot_sha256": _digest("population-snapshot"),
        "risk_register_sha256": _digest("risk-register"),
        "historical_evidence_sha256": _digest("history-snapshot"),
        "sampling_protocol_sha256": _digest("sampling-protocol"),
        "analysis_protocol_sha256": _digest("analysis-protocol"),
        "cases": _cases(),
        "supersedes_plan_sha256": None,
    }
    values.update(changes)
    return ASRCriticalNumberPrivateHoldoutPlanDefinition(**values)


def _plan():
    definition = _plan_definition()
    return definition, build_critical_number_private_holdout_plan(definition)


def _run_definition(
    *,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    statuses: tuple[ASRCriticalNumberPrivateHoldoutExecutionStatus, ...] | None = None,
    **changes: object,
) -> ASRCriticalNumberPrivateHoldoutBlindRunDefinition:
    selected_statuses = statuses or tuple(
        ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED
        for _ in plan_definition.cases
    )
    executions = tuple(
        ASRCriticalNumberPrivateHoldoutCaseExecution(
            case_token=case.case_token,
            status=status,
            evaluator_output_sha256=_digest(
                f"opaque-evaluator-output-{index}-{status.value}"
            ),
        )
        for index, (case, status) in enumerate(
            zip(plan_definition.cases, selected_statuses, strict=True)
        )
    )
    values: dict[str, object] = {
        "run_id": plan_definition.run_id,
        "plan_sha256": plan.sha256,
        "executor_manifest_sha256": _digest("executor-manifest"),
        "environment_manifest_sha256": _digest("environment-manifest"),
        "blinding_attestation_sha256": _digest("blinding-attestation"),
        "executions": executions,
    }
    values.update(changes)
    return ASRCriticalNumberPrivateHoldoutBlindRunDefinition(**values)


def test_private_commitments_are_deterministic_salted_and_domain_separated():
    payload = {"reference": "dose five milligrams"}
    first = calculate_critical_number_private_commitment(
        payload=payload,
        private_salt=_salt("first"),
    )
    second = calculate_critical_number_private_commitment(
        payload=payload,
        private_salt=_salt("first"),
    )
    different_salt = calculate_critical_number_private_commitment(
        payload=payload,
        private_salt=_salt("second"),
    )
    generic_digest = calculate_critical_number_private_holdout_sha256(payload)

    assert first == second
    assert first != different_salt
    assert first != generic_digest
    assert len(first) == 64
    assert "dose" not in first


def test_private_commitment_rejects_weak_salt_and_nondeterministic_json():
    with pytest.raises(HveeContractError, match="at least 32"):
        calculate_critical_number_private_commitment(
            payload={"secret": True},
            private_salt="too-short",
        )

    with pytest.raises(HveeContractError, match="deterministic JSON"):
        calculate_critical_number_private_commitment(
            payload={"invalid": object()},
            private_salt=_salt("invalid-json"),
        )


def test_preregistered_plan_is_deterministic_and_sealed():
    definition = _plan_definition()
    first = build_critical_number_private_holdout_plan(definition)
    second = build_critical_number_private_holdout_plan(definition)

    assert first == second
    assert first.sha256 == calculate_critical_number_private_holdout_sha256(
        first.payload
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRIVATE_HOLDOUT_PLAN_SCHEMA_VERSION
    )
    assert first.payload["protocol"] == {
        "key": CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_KEY,
        "version": CRITICAL_NUMBER_PRIVATE_HOLDOUT_PROTOCOL_VERSION,
        "artifact": "preregistered_private_holdout_plan",
        "commitment_scheme": CRITICAL_NUMBER_PRIVATE_COMMITMENT_SCHEME,
    }


def test_plan_binds_exact_evaluator_profile_and_assurance_artifact():
    _, plan = _plan()
    bindings = plan.payload["bindings"]

    assert bindings == {
        "evaluator": {
            "key": "hetren.asr.critical-number-fidelity.en-us",
            "version": "1.0.0",
            "evaluation_type": "asr",
        },
        "evaluation_profile": {
            "key": "hetren.asr.critical-number-profile.en-us",
            "version": "1.0.0",
            "language": "en",
            "locale": "en-US",
        },
        "assurance_profile": {
            "key": ("hetren.asr.critical-number-evaluator-assurance-profile.en-us"),
            "version": "1.0.0",
            "status": "experimental",
            "sha256": CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
        },
    }


def test_plan_contains_only_commitments_not_private_material():
    _, plan = _plan()
    serialized = repr(plan.payload)

    assert "private reference" not in serialized
    assert "private generated" not in serialized
    assert "private expected" not in serialized
    assert "private source" not in serialized
    assert "private-dosage" not in serialized
    assert plan.payload["confidentiality"] == {
        "private_case_content_in_artifact": False,
        "expected_results_in_artifact": False,
        "private_salts_in_artifact": False,
        "salted_commitments_only": True,
    }


def test_plan_records_risk_population_history_and_pre_reveal_locks():
    definition, plan = _plan()
    preregistration = plan.payload["preregistration"]

    assert preregistration["design_commitments"] == {
        "population_snapshot_sha256": (definition.population_snapshot_sha256),
        "risk_register_sha256": definition.risk_register_sha256,
        "historical_evidence_sha256": (definition.historical_evidence_sha256),
        "sampling_protocol_sha256": definition.sampling_protocol_sha256,
        "analysis_protocol_sha256": definition.analysis_protocol_sha256,
    }
    assert preregistration["locks"] == {
        "sealed_before_evaluator_outputs": True,
        "case_replacement_after_seal_allowed": False,
        "expected_result_change_after_seal_allowed": False,
        "post_reveal_plan_tuning_allowed": False,
        "redesign_requires_new_plan_and_run": True,
    }


def test_plan_records_deterministic_sample_and_slice_counts():
    definition, plan = _plan()
    sample = plan.payload["preregistration"]["selected_sample"]

    assert sample["case_count"] == 3
    assert sample["slice_counts"] == {
        "currency": 1,
        "dangerous": 1,
        "equivalence": 1,
        "measurement": 1,
        "substitution": 1,
        "unsupported": 1,
    }
    assert [item["case_token"] for item in sample["cases"]] == [
        case.case_token for case in definition.cases
    ]


def test_plan_cannot_issue_certification_or_enable_release_enforcement():
    _, plan = _plan()

    assert plan.payload["qualification"] == {
        "evaluator_status": "experimental",
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }
    serialized = repr(plan.payload)
    assert "ReleaseReport" not in serialized
    assert "release_decision" not in serialized


def test_any_preregistered_design_or_case_change_changes_plan_seal():
    definition, plan = _plan()
    changed_analysis = build_critical_number_private_holdout_plan(
        replace(
            definition,
            analysis_protocol_sha256=_digest("changed-analysis"),
        )
    )
    changed_case = replace(
        definition.cases[0],
        provenance_sha256=_digest("changed-provenance"),
    )
    changed_cases = tuple(
        sorted(
            (changed_case, *definition.cases[1:]),
            key=lambda value: value.case_token,
        )
    )
    changed_sample = build_critical_number_private_holdout_plan(
        replace(definition, cases=changed_cases)
    )

    assert changed_analysis.sha256 != plan.sha256
    assert changed_sample.sha256 != plan.sha256


def test_plan_verifier_rejects_tampering_even_with_recomputed_digest():
    definition, plan = _plan()
    tampered = copy.deepcopy(plan.payload)
    tampered["qualification"]["certification_issued"] = True
    tampered_sha256 = calculate_critical_number_private_holdout_sha256(tampered)

    with pytest.raises(HveeContractError, match="preregistered definition"):
        verify_critical_number_private_holdout_plan(
            payload=tampered,
            expected_sha256=tampered_sha256,
            definition=definition,
        )


def test_plan_bundle_rejects_payload_digest_mismatch():
    _, plan = _plan()

    with pytest.raises(HveeContractError, match="does not match its payload"):
        ASRCriticalNumberPrivateHoldoutPlanBundle(
            payload=plan.payload,
            sha256="0" * 64,
        )


def test_plan_rejects_duplicate_unsorted_or_malformed_case_commitments():
    cases = _cases()

    with pytest.raises(HveeContractError, match="ordered by case token"):
        _plan_definition(cases=tuple(reversed(cases)))

    with pytest.raises(HveeContractError, match="case tokens must be unique"):
        _plan_definition(cases=(cases[0], cases[0]))

    with pytest.raises(HveeContractError, match="unique and sorted"):
        replace(cases[0], slice_keys=("substitution", "dangerous"))

    with pytest.raises(HveeContractError, match="SHA-256"):
        replace(cases[0], case_payload_sha256="not-a-digest")


def test_revision_requires_previous_seal_new_plan_identity_and_new_run():
    previous_definition, previous = _plan()
    revised_definition = replace(
        previous_definition,
        plan_version="1.1.0",
        run_id="critical-number-private-certification-run-002",
        analysis_protocol_sha256=_digest("revised-analysis"),
        supersedes_plan_sha256=previous.sha256,
    )
    revised = build_critical_number_private_holdout_plan_revision(
        previous_plan=previous,
        previous_definition=previous_definition,
        revised_definition=revised_definition,
    )

    assert revised.sha256 != previous.sha256
    assert revised.payload["preregistration"]["supersedes_plan_sha256"] == (
        previous.sha256
    )

    with pytest.raises(HveeContractError, match="new plan identity"):
        build_critical_number_private_holdout_plan_revision(
            previous_plan=previous,
            previous_definition=previous_definition,
            revised_definition=replace(
                revised_definition,
                plan_version=previous_definition.plan_version,
            ),
        )

    with pytest.raises(HveeContractError, match="new run id"):
        build_critical_number_private_holdout_plan_revision(
            previous_plan=previous,
            previous_definition=previous_definition,
            revised_definition=replace(
                revised_definition,
                run_id=previous_definition.run_id,
            ),
        )


def test_blind_run_is_deterministic_sealed_and_complete():
    plan_definition, plan = _plan()
    run_definition = _run_definition(
        plan_definition=plan_definition,
        plan=plan,
    )
    first = build_critical_number_private_holdout_blind_run(
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )
    second = build_critical_number_private_holdout_blind_run(
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )

    assert first == second
    assert first.sha256 == calculate_critical_number_private_holdout_sha256(
        first.payload
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRIVATE_HOLDOUT_RUN_SCHEMA_VERSION
    )
    assert first.payload["execution"]["selected_case_count"] == 3
    assert first.payload["execution"]["retained_case_count"] == 3


def test_blind_run_contains_only_output_commitments_before_label_reveal():
    plan_definition, plan = _plan()
    run_definition = _run_definition(
        plan_definition=plan_definition,
        plan=plan,
    )
    run = build_critical_number_private_holdout_blind_run(
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )
    serialized = repr(run.payload)

    assert "private expected" not in serialized
    assert "opaque-evaluator-output" not in serialized
    assert run.payload["blinding"] == {
        "sealed_before_expected_result_reveal": True,
        "expected_results_in_artifact": False,
        "evaluator_outputs_in_artifact": False,
        "evaluator_output_commitments_only": True,
        "all_selected_cases_retained": True,
        "failed_case_replacement_allowed": False,
    }
    assert run.payload["qualification"]["certification_issued"] is False


def test_failed_and_timed_out_cases_are_retained_not_replaced():
    plan_definition, plan = _plan()
    statuses = (
        ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.FAILED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.TIMED_OUT,
    )
    run_definition = _run_definition(
        plan_definition=plan_definition,
        plan=plan,
        statuses=statuses,
    )
    run = build_critical_number_private_holdout_blind_run(
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )

    assert run.payload["execution"]["status_counts"] == {
        "completed": 1,
        "failed": 1,
        "timed_out": 1,
        "cancelled": 0,
        "invalid": 0,
    }
    assert run.payload["execution"]["retained_case_count"] == 3


def test_blind_run_rejects_missing_or_substituted_cases():
    plan_definition, plan = _plan()
    complete = _run_definition(
        plan_definition=plan_definition,
        plan=plan,
    )

    with pytest.raises(HveeContractError, match="retain every"):
        build_critical_number_private_holdout_blind_run(
            plan=plan,
            plan_definition=plan_definition,
            run_definition=replace(
                complete,
                executions=complete.executions[:-1],
            ),
        )

    substituted = replace(
        complete.executions[-1],
        case_token=_digest("unregistered-private-case"),
    )
    substituted_executions = tuple(
        sorted(
            (*complete.executions[:-1], substituted),
            key=lambda value: value.case_token,
        )
    )
    with pytest.raises(HveeContractError, match="retain every"):
        build_critical_number_private_holdout_blind_run(
            plan=plan,
            plan_definition=plan_definition,
            run_definition=replace(
                complete,
                executions=substituted_executions,
            ),
        )


def test_blind_run_rejects_wrong_plan_or_run_identity():
    plan_definition, plan = _plan()
    run_definition = _run_definition(
        plan_definition=plan_definition,
        plan=plan,
    )

    with pytest.raises(HveeContractError, match="bind the sealed plan"):
        build_critical_number_private_holdout_blind_run(
            plan=plan,
            plan_definition=plan_definition,
            run_definition=replace(
                run_definition,
                plan_sha256=_digest("different-plan"),
            ),
        )

    with pytest.raises(HveeContractError, match="does not match"):
        build_critical_number_private_holdout_blind_run(
            plan=plan,
            plan_definition=plan_definition,
            run_definition=replace(
                run_definition,
                run_id="critical-number-private-certification-run-999",
            ),
        )


def test_blind_run_verifier_rejects_tampering_with_recomputed_digest():
    plan_definition, plan = _plan()
    run_definition = _run_definition(
        plan_definition=plan_definition,
        plan=plan,
    )
    run = build_critical_number_private_holdout_blind_run(
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )
    tampered = copy.deepcopy(run.payload)
    tampered["qualification"]["production_qualified"] = True
    tampered_sha256 = calculate_critical_number_private_holdout_sha256(tampered)

    with pytest.raises(HveeContractError, match="preregistered execution"):
        verify_critical_number_private_holdout_blind_run(
            payload=tampered,
            expected_sha256=tampered_sha256,
            plan=plan,
            plan_definition=plan_definition,
            run_definition=run_definition,
        )


def test_blind_run_bundle_rejects_payload_digest_mismatch():
    plan_definition, plan = _plan()
    run_definition = _run_definition(
        plan_definition=plan_definition,
        plan=plan,
    )
    run = build_critical_number_private_holdout_blind_run(
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )

    with pytest.raises(HveeContractError, match="does not match its payload"):
        ASRCriticalNumberPrivateHoldoutBlindRunBundle(
            payload=run.payload,
            sha256="0" * 64,
        )


def test_same_version_evaluator_identity_change_fails_closed(monkeypatch):
    monkeypatch.setattr(
        holdout_module,
        "CRITICAL_NUMBER_FIDELITY_EVALUATOR",
        replace(CRITICAL_NUMBER_FIDELITY_EVALUATOR, version="1.0.1"),
    )

    with pytest.raises(HveeContractError, match="evaluator identity changed"):
        build_critical_number_private_holdout_plan(_plan_definition())
