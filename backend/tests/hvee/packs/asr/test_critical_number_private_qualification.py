from __future__ import annotations

import copy
import hashlib
import hmac
from dataclasses import replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs import asr
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
)
from hvee.packs.asr.critical_number_private_evidence import (
    ASRCriticalNumberPrivateEvidenceCaseDisclosure,
    ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
    ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
    ASRCriticalNumberPrivateEvidenceReplayState,
    ASRCriticalNumberPrivateEvidenceSigner,
    build_critical_number_private_disclosure_evidence_envelope,
    build_critical_number_private_evidence_disclosure_manifest,
    build_critical_number_private_holdout_blind_run_evidence_envelope,
    build_critical_number_private_holdout_plan_evidence_envelope,
    calculate_critical_number_private_evaluator_output_commitment,
    verify_critical_number_private_disclosure_evidence_envelope,
    verify_critical_number_private_holdout_blind_run_evidence_envelope,
    verify_critical_number_private_holdout_plan_evidence_envelope,
)
from hvee.packs.asr.critical_number_private_holdout import (
    ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    ASRCriticalNumberPrivateHoldoutCaseCommitment,
    ASRCriticalNumberPrivateHoldoutCaseExecution,
    ASRCriticalNumberPrivateHoldoutExecutionStatus,
    ASRCriticalNumberPrivateHoldoutPlanDefinition,
    build_critical_number_private_holdout_blind_run,
    build_critical_number_private_holdout_plan,
    calculate_critical_number_private_commitment,
)
from hvee.packs.asr.critical_number_private_qualification import (
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ADJUDICATION_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CAMPAIGN_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_KEY,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_VERSION,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1,
    ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    ASRCriticalNumberPrivateQualificationAdjudicationOutcome,
    ASRCriticalNumberPrivateQualificationAdjudicator,
    ASRCriticalNumberPrivateQualificationAdjudicatorRole,
    ASRCriticalNumberPrivateQualificationCampaignDefinition,
    ASRCriticalNumberPrivateQualificationCaseAdjudication,
    ASRCriticalNumberPrivateQualificationStatisticalCriteria,
    ASRCriticalNumberPrivateQualificationStratum,
    ASRCriticalNumberPrivateQualificationStratumDefinition,
    build_critical_number_private_qualification_adjudication,
    build_critical_number_private_qualification_campaign,
    build_critical_number_private_qualification_protocol,
    build_critical_number_private_qualification_protocol_revision,
    calculate_critical_number_private_qualification_adjudicator_roster_sha256,
    calculate_critical_number_private_qualification_sha256,
    verify_critical_number_private_qualification_adjudication,
    verify_critical_number_private_qualification_campaign,
    verify_critical_number_private_qualification_protocol,
)
from hvee.packs.asr.critical_number_private_assessment import (
    ASRCriticalNumberPrivateStatisticalAssessmentResult,
    build_critical_number_private_statistical_assessment_v1,
    verify_critical_number_private_statistical_assessment_v1,
)
from hvee.packs.asr.critical_number_private_statistics import (
    build_critical_number_private_statistical_method_manifest_v1,
)


_SIGNING_KEY = b"private-qualification-test-signing-key-not-production"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _salt(label: str) -> str:
    return f"private-qualification-{label}-" + ("s" * 32)


def _sign(message: bytes) -> bytes:
    return hmac.digest(_SIGNING_KEY, message, "sha256")


def _verify(message: bytes, signature: bytes) -> bool:
    return hmac.compare_digest(_sign(message), signature)


def _signer() -> ASRCriticalNumberPrivateEvidenceSigner:
    return ASRCriticalNumberPrivateEvidenceSigner(
        key_id="critical-number-private-qualification-test-key",
        algorithm="test-hmac-sha256",
        public_key_sha256=_digest("qualification-test-public-key"),
    )


def _private_case(label: str):
    disclosure = ASRCriticalNumberPrivateEvidenceCaseDisclosure(
        case_token_payload={"case_id": label},
        case_token_private_salt=_salt(f"{label}-token"),
        case_payload={
            "reference": f"private reference {label}",
            "generated": f"private generated {label}",
        },
        case_payload_private_salt=_salt(f"{label}-payload"),
        expected_result={"oracle": f"private expected {label}"},
        expected_result_private_salt=_salt(f"{label}-expected"),
        provenance={"source": f"private source {label}"},
        provenance_private_salt=_salt(f"{label}-provenance"),
        evaluator_output={"actual": f"private output {label}"},
        evaluator_output_private_salt=_salt(f"{label}-output"),
    )
    commitment = ASRCriticalNumberPrivateHoldoutCaseCommitment(
        case_token=calculate_critical_number_private_commitment(
            payload=disclosure.case_token_payload,
            private_salt=disclosure.case_token_private_salt,
        ),
        case_payload_sha256=calculate_critical_number_private_commitment(
            payload=disclosure.case_payload,
            private_salt=disclosure.case_payload_private_salt,
        ),
        expected_result_sha256=calculate_critical_number_private_commitment(
            payload=disclosure.expected_result,
            private_salt=disclosure.expected_result_private_salt,
        ),
        provenance_sha256=calculate_critical_number_private_commitment(
            payload=disclosure.provenance,
            private_salt=disclosure.provenance_private_salt,
        ),
        slice_keys=(label.replace("_", "-"),),
    )
    return commitment, disclosure


def _private_material():
    material = {}
    for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1:
        material[stratum] = _private_case(stratum.value)
    return material


def _strata(material=None):
    material = material or _private_material()
    return tuple(
        ASRCriticalNumberPrivateQualificationStratumDefinition(
            stratum=stratum,
            construction_protocol_sha256=_digest(
                f"construction-{stratum.value}"
            ),
            population_manifest_sha256=_digest(f"population-{stratum.value}"),
            selection_manifest_sha256=_digest(f"selection-{stratum.value}"),
            expected_behavior_sha256=_digest(f"expected-{stratum.value}"),
            case_tokens=(material[stratum][0].case_token,),
        )
        for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1
    )


def _criteria(**changes: object):
    values: dict[str, object] = {
        "method_key": "hetren.private.stratified-exact-interval",
        "method_version": "1.0.0",
        "method_manifest_sha256": _digest("statistical-method"),
        "multiplicity_control_key": "holm-familywise-control",
        "multiplicity_control_version": "1.0.0",
        "confidence_level_ppm": 950_000,
        "minimum_total_usable_cases": 7,
        "minimum_usable_cases_per_stratum": 1,
        "minimum_oracle_detection_lower_bound_ppm": 900_000,
        "maximum_control_false_positive_upper_bound_ppm": 50_000,
        "maximum_abstention_upper_bound_ppm": 50_000,
        "maximum_unresolved_fraction_ppm": 20_000,
        "maximum_execution_failure_fraction_ppm": 20_000,
    }
    values.update(changes)
    return ASRCriticalNumberPrivateQualificationStatisticalCriteria(**values)


def _campaign_definition(material=None, **changes: object):
    material = material or _private_material()
    values: dict[str, object] = {
        "campaign_id": "critical-number-private-qualification-campaign",
        "campaign_version": "1.0.0",
        "run_id": "critical-number-private-qualification-run-001",
        "holdout_set_key": "hetren.asr.critical-number-private-set.en-us",
        "holdout_set_version": "1.0.0",
        "protocol_owner_key_id": "critical-number-protocol-owner",
        "strata": _strata(material),
        "statistical_criteria": _criteria(),
        "adjudication_protocol_sha256": _digest("adjudication-protocol"),
        "adjudicator_roster_sha256": (
            calculate_critical_number_private_qualification_adjudicator_roster_sha256(
                _adjudicators()
            )
        ),
        "conflict_of_interest_policy_sha256": _digest("conflict-policy"),
        "data_handling_policy_sha256": _digest("data-handling-policy"),
    }
    values.update(changes)
    return ASRCriticalNumberPrivateQualificationCampaignDefinition(**values)


def _plan_definition(campaign_definition, protocol, material):
    cases = tuple(sorted((pair[0] for pair in material.values()), key=lambda c: c.case_token))
    return ASRCriticalNumberPrivateHoldoutPlanDefinition(
        plan_id="critical-number-private-qualification-plan",
        plan_version="1.0.0",
        run_id=campaign_definition.run_id,
        holdout_set_key=campaign_definition.holdout_set_key,
        holdout_set_version=campaign_definition.holdout_set_version,
        holdout_manifest_sha256=_digest("holdout-manifest"),
        population_snapshot_sha256=_digest("population-snapshot"),
        risk_register_sha256=_digest("risk-register"),
        historical_evidence_sha256=_digest("historical-evidence"),
        sampling_protocol_sha256=_digest("sampling-protocol"),
        analysis_protocol_sha256=protocol.sha256,
        cases=cases,
    )


def _envelope_definition(*, run_id: str, sequence: int, previous: str | None):
    return ASRCriticalNumberPrivateEvidenceEnvelopeDefinition(
        chain_id=run_id,
        envelope_id=f"critical-number-qualification-evidence-{sequence:03d}",
        sequence_number=sequence,
        issued_at_utc=f"2026-08-09T22:0{sequence}:00Z",
        nonce_sha256=_digest(f"qualification-nonce-{sequence}"),
        previous_envelope_sha256=previous,
        signer=_signer(),
    )


def _full_campaign(*, statistical_criteria=None, execution_statuses=None):
    material = _private_material()
    campaign_definition = _campaign_definition(
        material,
        **(
            {"statistical_criteria": statistical_criteria}
            if statistical_criteria is not None
            else {}
        ),
    )
    protocol = build_critical_number_private_qualification_protocol(
        campaign_definition
    )
    plan_definition = _plan_definition(campaign_definition, protocol, material)
    plan = build_critical_number_private_holdout_plan(plan_definition)

    disclosure_by_token = {
        commitment.case_token: disclosure
        for commitment, disclosure in material.values()
    }
    statuses = execution_statuses or (
        ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.FAILED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.TIMED_OUT,
    )
    if len(statuses) != len(plan_definition.cases):
        raise ValueError("execution statuses must cover every planned case")
    executions = tuple(
        ASRCriticalNumberPrivateHoldoutCaseExecution(
            case_token=case.case_token,
            status=status,
            evaluator_output_sha256=(
                calculate_critical_number_private_evaluator_output_commitment(
                    payload=disclosure_by_token[case.case_token].evaluator_output,
                    private_salt=(
                        disclosure_by_token[
                            case.case_token
                        ].evaluator_output_private_salt
                    ),
                )
            ),
        )
        for case, status in zip(plan_definition.cases, statuses, strict=True)
    )
    run_definition = ASRCriticalNumberPrivateHoldoutBlindRunDefinition(
        run_id=campaign_definition.run_id,
        plan_sha256=plan.sha256,
        executor_manifest_sha256=_digest("executor-manifest"),
        environment_manifest_sha256=_digest("environment-manifest"),
        blinding_attestation_sha256=_digest("blinding-attestation"),
        executions=executions,
    )
    run = build_critical_number_private_holdout_blind_run(
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )

    replay = ASRCriticalNumberPrivateEvidenceReplayState(
        chain_id=campaign_definition.run_id
    )
    plan_envelope = build_critical_number_private_holdout_plan_evidence_envelope(
        plan=plan,
        plan_definition=plan_definition,
        envelope_definition=_envelope_definition(
            run_id=campaign_definition.run_id,
            sequence=1,
            previous=None,
        ),
        sign=_sign,
    )
    verified_plan = verify_critical_number_private_holdout_plan_evidence_envelope(
        plan=plan,
        plan_definition=plan_definition,
        envelope=plan_envelope,
        trusted_signer=_signer(),
        replay_state=replay,
        verify_signature=_verify,
    )
    run_envelope = build_critical_number_private_holdout_blind_run_evidence_envelope(
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        plan_envelope=plan_envelope,
        envelope_definition=_envelope_definition(
            run_id=campaign_definition.run_id,
            sequence=2,
            previous=plan_envelope.sha256,
        ),
        sign=_sign,
    )
    verified_run = (
        verify_critical_number_private_holdout_blind_run_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            envelope=run_envelope,
            verified_plan_envelope=verified_plan,
            trusted_signer=_signer(),
            verify_signature=_verify,
        )
    )
    disclosures = tuple(
        disclosure_by_token[case.case_token] for case in plan_definition.cases
    )
    disclosure_definition = ASRCriticalNumberPrivateEvidenceDisclosureDefinition(
        verification_id="critical-number-private-qualification-verification",
        verification_version="1.0.0",
        verifier_key_id="critical-number-independent-verifier",
        verification_procedure_sha256=_digest("verification-procedure"),
        verification_environment_sha256=_digest("verification-environment"),
        independence_attestation_sha256=_digest("verification-independence"),
        disclosures=disclosures,
    )
    manifest = build_critical_number_private_evidence_disclosure_manifest(
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        verified_plan_envelope=verified_plan,
        verified_run_envelope=verified_run,
        definition=disclosure_definition,
    )
    disclosure_envelope = build_critical_number_private_disclosure_evidence_envelope(
        manifest=manifest,
        verified_run_envelope=verified_run,
        envelope_definition=_envelope_definition(
            run_id=campaign_definition.run_id,
            sequence=3,
            previous=run_envelope.sha256,
        ),
        sign=_sign,
    )
    verified_disclosure = verify_critical_number_private_disclosure_evidence_envelope(
        manifest=manifest,
        envelope=disclosure_envelope,
        verified_run_envelope=verified_run,
        trusted_signer=_signer(),
        verify_signature=_verify,
    )
    campaign = build_critical_number_private_qualification_campaign(
        protocol=protocol,
        definition=campaign_definition,
        plan=plan,
        plan_definition=plan_definition,
    )
    return {
        "material": material,
        "campaign_definition": campaign_definition,
        "protocol": protocol,
        "plan_definition": plan_definition,
        "plan": plan,
        "run_definition": run_definition,
        "run": run,
        "verified_plan": verified_plan,
        "verified_run": verified_run,
        "disclosure_definition": disclosure_definition,
        "manifest": manifest,
        "verified_disclosure": verified_disclosure,
        "campaign": campaign,
    }


def _adjudicators(**changes: object):
    adjudicators = tuple(
        ASRCriticalNumberPrivateQualificationAdjudicator(
            role=role,
            key_id=f"critical-number-{role.value}-adjudicator",
            affiliation_key=f"independent-{role.value}-organization",
            qualification_sha256=_digest(f"qualification-{role.value}"),
            independence_attestation_sha256=_digest(
                f"independence-{role.value}"
            ),
        )
        for role in ASRCriticalNumberPrivateQualificationAdjudicatorRole
    )
    if not changes:
        return adjudicators
    values = list(adjudicators)
    index = int(changes.pop("index", 0))
    values[index] = replace(values[index], **changes)
    return tuple(values)


def _adjudication_definition(context, *, cases=None, **changes: object):
    campaign_definition = context["campaign_definition"]
    stratum_by_token = {
        token: stratum.stratum
        for stratum in campaign_definition.strata
        for token in stratum.case_tokens
    }
    records = []
    for index, execution in enumerate(context["run_definition"].executions):
        stratum = stratum_by_token[execution.case_token]
        if execution.status != ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED:
            outcome = (
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.EXECUTION_FAILURE
            )
        elif stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1:
            outcome = ASRCriticalNumberPrivateQualificationAdjudicationOutcome.DETECTED
        else:
            outcome = (
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.TRUE_NEGATIVE
            )
        agreed = index != 2
        records.append(
            ASRCriticalNumberPrivateQualificationCaseAdjudication(
                case_token=execution.case_token,
                stratum=stratum,
                execution_status=execution.status,
                outcome=outcome,
                primary_record_sha256=_digest(f"primary-{execution.case_token}"),
                secondary_record_sha256=_digest(
                    f"secondary-{execution.case_token}"
                ),
                reviewers_agreed=agreed,
                resolution_record_sha256=(
                    None
                    if agreed
                    else _digest(f"resolution-{execution.case_token}")
                ),
            )
        )
    values: dict[str, object] = {
        "adjudication_id": "critical-number-private-adjudication-001",
        "adjudication_version": "1.0.0",
        "campaign_sha256": context["campaign"].sha256,
        "disclosure_manifest_sha256": context["manifest"].sha256,
        "adjudication_procedure_sha256": (
            campaign_definition.adjudication_protocol_sha256
        ),
        "adjudication_environment_sha256": _digest("adjudication-environment"),
        "independence_attestation_sha256": _digest(
            "adjudication-independence"
        ),
        "adjudicators": _adjudicators(),
        "cases": tuple(records) if cases is None else cases,
    }
    values.update(changes)
    return ASRCriticalNumberPrivateQualificationAdjudicationDefinition(**values)


def _build_adjudication(context, definition=None):
    definition = definition or _adjudication_definition(context)
    return build_critical_number_private_qualification_adjudication(
        campaign=context["campaign"],
        protocol=context["protocol"],
        campaign_definition=context["campaign_definition"],
        plan=context["plan"],
        plan_definition=context["plan_definition"],
        run=context["run"],
        run_definition=context["run_definition"],
        disclosure_manifest=context["manifest"],
        disclosure_definition=context["disclosure_definition"],
        verified_plan_envelope=context["verified_plan"],
        verified_run_envelope=context["verified_run"],
        verified_disclosure_envelope=context["verified_disclosure"],
        definition=definition,
    )


def _assessment_criteria(**changes: object):
    method_manifest = (
        build_critical_number_private_statistical_method_manifest_v1()
    )
    values: dict[str, object] = {
        "method_manifest_sha256": method_manifest.sha256,
        "minimum_oracle_detection_lower_bound_ppm": 0,
        "maximum_control_false_positive_upper_bound_ppm": 1_000_000,
        "maximum_abstention_upper_bound_ppm": 1_000_000,
        "maximum_unresolved_fraction_ppm": 0,
        "maximum_execution_failure_fraction_ppm": 0,
    }
    values.update(changes)
    return _criteria(**values)


def _all_completed_statuses():
    return tuple(
        ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED
        for _stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1
    )


def _build_assessment(context, adjudication_definition=None, adjudication=None):
    adjudication_definition = (
        adjudication_definition or _adjudication_definition(context)
    )
    adjudication = adjudication or _build_adjudication(
        context,
        adjudication_definition,
    )
    return build_critical_number_private_statistical_assessment_v1(
        method_manifest=(
            build_critical_number_private_statistical_method_manifest_v1()
        ),
        adjudication=adjudication,
        campaign=context["campaign"],
        protocol=context["protocol"],
        campaign_definition=context["campaign_definition"],
        plan=context["plan"],
        plan_definition=context["plan_definition"],
        run=context["run"],
        run_definition=context["run_definition"],
        disclosure_manifest=context["manifest"],
        disclosure_definition=context["disclosure_definition"],
        verified_plan_envelope=context["verified_plan"],
        verified_run_envelope=context["verified_run"],
        verified_disclosure_envelope=context["verified_disclosure"],
        adjudication_definition=adjudication_definition,
    )

def test_protocol_is_deterministic_and_binds_exact_experimental_v1_identity():
    definition = _campaign_definition()
    first = build_critical_number_private_qualification_protocol(definition)
    second = build_critical_number_private_qualification_protocol(definition)

    assert first == second
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_SCHEMA_VERSION
    )
    assert first.payload["protocol"] == {
        "key": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_KEY,
        "version": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_VERSION,
        "artifact": "preregistered_private_qualification_protocol",
    }
    assert first.payload["bindings"]["assurance_profile"]["sha256"] == (
        CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
    )
    assert first.payload["bindings"]["assurance_profile"]["status"] == (
        "experimental"
    )


def test_protocol_contains_exact_oracle_and_control_strata_and_frozen_criteria():
    bundle = build_critical_number_private_qualification_protocol(
        _campaign_definition()
    )
    preregistration = bundle.payload["preregistration"]
    strata = preregistration["strata"]

    assert tuple(item["key"] for item in strata) == tuple(
        stratum.value
        for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1
    )
    assert {
        item["key"] for item in strata if item["purpose"] == "oracle_mutation"
    } == {
        stratum.value
        for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1
    }
    assert {
        item["key"] for item in strata if item["purpose"] == "control"
    } == {
        stratum.value
        for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1
    }
    criteria = preregistration["statistical_acceptance_criteria"]
    assert criteria["rate_scale"] == (
        CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE
    )
    assert criteria["confidence_level_ppm"] == 950_000
    assert preregistration["locks"]["criteria_change_after_seal_allowed"] is False
    assert preregistration["locks"]["post_reveal_tuning_allowed"] is False


def test_protocol_exposes_only_opaque_case_tokens_and_commitments():
    bundle = build_critical_number_private_qualification_protocol(
        _campaign_definition()
    )
    serialized = repr(bundle.payload)

    assert "private reference" not in serialized
    assert "private expected" not in serialized
    assert "private source" not in serialized
    assert "private output" not in serialized
    assert _salt("substitution_mutation-token") not in serialized
    assert bundle.payload["confidentiality"] == {
        "private_case_content_in_artifact": False,
        "expected_results_in_artifact": False,
        "private_provenance_in_artifact": False,
        "private_salts_in_artifact": False,
        "opaque_case_tokens_only": True,
    }


def test_campaign_definition_requires_exact_sorted_v1_strata():
    strata = _strata()

    with pytest.raises(HveeContractError, match="exact sorted v1 set"):
        _campaign_definition(strata=strata[:-1])
    with pytest.raises(HveeContractError, match="exact sorted v1 set"):
        _campaign_definition(strata=tuple(reversed(strata)))


def test_campaign_definition_rejects_case_reuse_across_strata():
    strata = list(_strata())
    strata[1] = replace(strata[1], case_tokens=strata[0].case_tokens)

    with pytest.raises(HveeContractError, match="cannot cross strata"):
        _campaign_definition(strata=tuple(strata))


@pytest.mark.parametrize("confidence", [500_000, 1_000_000])
def test_statistical_criteria_reject_non_interior_confidence(confidence):
    with pytest.raises(HveeContractError, match="greater than 0.5"):
        _criteria(confidence_level_ppm=confidence)


def test_statistical_criteria_reject_invalid_rates_and_impossible_minimums():
    with pytest.raises(HveeContractError, match="integer from 0"):
        _criteria(maximum_unresolved_fraction_ppm=-1)
    with pytest.raises(HveeContractError, match="exceeds selection"):
        _campaign_definition(
            statistical_criteria=_criteria(minimum_total_usable_cases=8)
        )
    with pytest.raises(HveeContractError, match="per-stratum minimum"):
        _campaign_definition(
            statistical_criteria=_criteria(
                minimum_total_usable_cases=7,
                minimum_usable_cases_per_stratum=2,
            )
        )


def test_protocol_verification_rejects_tampering():
    definition = _campaign_definition()
    bundle = build_critical_number_private_qualification_protocol(definition)
    tampered = copy.deepcopy(bundle.payload)
    tampered["preregistration"]["statistical_acceptance_criteria"][
        "confidence_level_ppm"
    ] = 990_000

    with pytest.raises(HveeContractError, match="expected SHA-256"):
        verify_critical_number_private_qualification_protocol(
            payload=tampered,
            expected_sha256=bundle.sha256,
            definition=definition,
        )


def test_protocol_revision_requires_supersession_new_identity_and_new_run():
    previous_definition = _campaign_definition()
    previous = build_critical_number_private_qualification_protocol(
        previous_definition
    )

    with pytest.raises(HveeContractError, match="bind the previous"):
        build_critical_number_private_qualification_protocol_revision(
            previous_protocol=previous,
            previous_definition=previous_definition,
            revised_definition=replace(
                previous_definition,
                campaign_id="critical-number-private-campaign-revised",
                run_id="critical-number-private-qualification-run-002",
            ),
        )
    with pytest.raises(HveeContractError, match="new campaign identity"):
        build_critical_number_private_qualification_protocol_revision(
            previous_protocol=previous,
            previous_definition=previous_definition,
            revised_definition=replace(
                previous_definition,
                run_id="critical-number-private-qualification-run-002",
                supersedes_protocol_sha256=previous.sha256,
            ),
        )
    with pytest.raises(HveeContractError, match="new run id"):
        build_critical_number_private_qualification_protocol_revision(
            previous_protocol=previous,
            previous_definition=previous_definition,
            revised_definition=replace(
                previous_definition,
                campaign_id="critical-number-private-campaign-revised",
                supersedes_protocol_sha256=previous.sha256,
            ),
        )

    revised = build_critical_number_private_qualification_protocol_revision(
        previous_protocol=previous,
        previous_definition=previous_definition,
        revised_definition=replace(
            previous_definition,
            campaign_id="critical-number-private-campaign-revised",
            campaign_version="2.0.0",
            run_id="critical-number-private-qualification-run-002",
            supersedes_protocol_sha256=previous.sha256,
        ),
    )
    assert revised.payload["preregistration"]["supersedes_protocol_sha256"] == (
        previous.sha256
    )


def test_campaign_binds_protocol_through_holdout_analysis_commitment():
    context = _full_campaign()
    campaign = context["campaign"]

    assert campaign.payload["schema_version"] == (
        CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CAMPAIGN_SCHEMA_VERSION
    )
    assert campaign.payload["campaign"]["qualification_protocol_sha256"] == (
        context["protocol"].sha256
    )
    assert campaign.payload["campaign"]["private_holdout_plan_sha256"] == (
        context["plan"].sha256
    )
    assert campaign.payload["campaign"]["all_holdout_cases_assigned"] is True


def test_campaign_rejects_unbound_analysis_protocol():
    context = _full_campaign()
    wrong_definition = replace(
        context["plan_definition"],
        analysis_protocol_sha256=_digest("different-analysis-protocol"),
    )
    wrong_plan = build_critical_number_private_holdout_plan(wrong_definition)

    with pytest.raises(HveeContractError, match="does not bind"):
        build_critical_number_private_qualification_campaign(
            protocol=context["protocol"],
            definition=context["campaign_definition"],
            plan=wrong_plan,
            plan_definition=wrong_definition,
        )


def test_campaign_rejects_missing_or_reassigned_holdout_case():
    context = _full_campaign()
    plan_definition = context["plan_definition"]
    reduced_definition = replace(
        plan_definition,
        cases=plan_definition.cases[:-1],
    )
    reduced_plan = build_critical_number_private_holdout_plan(reduced_definition)

    with pytest.raises(HveeContractError, match="assign every holdout case"):
        build_critical_number_private_qualification_campaign(
            protocol=context["protocol"],
            definition=context["campaign_definition"],
            plan=reduced_plan,
            plan_definition=reduced_definition,
        )


def test_campaign_verification_rejects_substitution():
    context = _full_campaign()
    tampered = copy.deepcopy(context["campaign"].payload)
    tampered["campaign_state"]["statistical_qualification_assessed"] = True

    with pytest.raises(HveeContractError, match="expected SHA-256"):
        verify_critical_number_private_qualification_campaign(
            payload=tampered,
            expected_sha256=context["campaign"].sha256,
            protocol=context["protocol"],
            definition=context["campaign_definition"],
            plan=context["plan"],
            plan_definition=context["plan_definition"],
        )


def test_case_adjudication_enforces_stratum_specific_outcomes():
    token = _digest("case")
    common = {
        "case_token": token,
        "execution_status": ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
        "primary_record_sha256": _digest("primary"),
        "secondary_record_sha256": _digest("secondary"),
        "reviewers_agreed": True,
    }

    with pytest.raises(HveeContractError, match="incompatible"):
        ASRCriticalNumberPrivateQualificationCaseAdjudication(
            stratum=ASRCriticalNumberPrivateQualificationStratum.SUBSTITUTION_MUTATION,
            outcome=ASRCriticalNumberPrivateQualificationAdjudicationOutcome.TRUE_NEGATIVE,
            **common,
        )
    with pytest.raises(HveeContractError, match="incompatible"):
        ASRCriticalNumberPrivateQualificationCaseAdjudication(
            stratum=(
                ASRCriticalNumberPrivateQualificationStratum.EQUIVALENT_RENDERING_CONTROL
            ),
            outcome=ASRCriticalNumberPrivateQualificationAdjudicationOutcome.DETECTED,
            **common,
        )


def test_case_adjudication_keeps_execution_failures_out_of_success_outcomes():
    values = {
        "case_token": _digest("case"),
        "stratum": ASRCriticalNumberPrivateQualificationStratum.OMISSION_MUTATION,
        "primary_record_sha256": _digest("primary"),
        "secondary_record_sha256": _digest("secondary"),
        "reviewers_agreed": True,
    }
    with pytest.raises(HveeContractError, match="execution status"):
        ASRCriticalNumberPrivateQualificationCaseAdjudication(
            execution_status=ASRCriticalNumberPrivateHoldoutExecutionStatus.FAILED,
            outcome=ASRCriticalNumberPrivateQualificationAdjudicationOutcome.DETECTED,
            **values,
        )
    with pytest.raises(HveeContractError, match="execution status"):
        ASRCriticalNumberPrivateQualificationCaseAdjudication(
            execution_status=ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
            outcome=(
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.EXECUTION_FAILURE
            ),
            **values,
        )


def test_case_adjudication_requires_arbitration_only_for_disagreement():
    values = {
        "case_token": _digest("case"),
        "stratum": ASRCriticalNumberPrivateQualificationStratum.INSERTION_MUTATION,
        "execution_status": ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
        "outcome": ASRCriticalNumberPrivateQualificationAdjudicationOutcome.DETECTED,
        "primary_record_sha256": _digest("primary"),
        "secondary_record_sha256": _digest("secondary"),
    }
    with pytest.raises(HveeContractError, match="must be a lowercase"):
        ASRCriticalNumberPrivateQualificationCaseAdjudication(
            reviewers_agreed=False,
            **values,
        )
    with pytest.raises(HveeContractError, match="cannot contain arbitration"):
        ASRCriticalNumberPrivateQualificationCaseAdjudication(
            reviewers_agreed=True,
            resolution_record_sha256=_digest("resolution"),
            **values,
        )


def test_adjudication_definition_requires_three_ordered_distinct_roles():
    context = _full_campaign()
    adjudicators = _adjudicators()

    with pytest.raises(HveeContractError, match="ordered primary"):
        _adjudication_definition(
            context,
            adjudicators=tuple(reversed(adjudicators)),
        )
    duplicated = list(adjudicators)
    duplicated[1] = replace(duplicated[1], key_id=duplicated[0].key_id)
    with pytest.raises(HveeContractError, match="must be distinct"):
        _adjudication_definition(context, adjudicators=tuple(duplicated))


def test_adjudication_is_deterministic_complete_and_summary_only():
    context = _full_campaign()
    definition = _adjudication_definition(context)
    first = _build_adjudication(context, definition)
    second = _build_adjudication(context, definition)

    assert first == second
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ADJUDICATION_SCHEMA_VERSION
    )
    adjudication = first.payload["independent_adjudication"]
    assert adjudication["selected_case_count"] == 7
    assert adjudication["adjudicated_case_count"] == 7
    assert adjudication["all_selected_cases_retained"] is True
    assert adjudication["dual_independent_review_complete"] is True
    assert adjudication["all_disagreements_arbitrated"] is True
    assert adjudication["counts"]["arbitrated_disagreements"] == 1


def test_adjudication_retains_failed_and_timed_out_cases_without_replacement():
    context = _full_campaign()
    bundle = _build_adjudication(context)
    counts = bundle.payload["independent_adjudication"]["counts"]

    assert counts["execution_statuses"]["failed"] == 1
    assert counts["execution_statuses"]["timed_out"] == 1
    assert counts["outcomes"]["execution_failure"] == 2
    assert sum(counts["strata"].values()) == 7


def test_adjudication_requires_exact_verified_plan_run_disclosure_chain():
    context = _full_campaign()
    wrong_disclosure = replace(
        context["verified_disclosure"],
        artifact_sha256=_digest("substituted-manifest"),
    )

    with pytest.raises(HveeContractError, match="artifacts do not match"):
        build_critical_number_private_qualification_adjudication(
            campaign=context["campaign"],
            protocol=context["protocol"],
            campaign_definition=context["campaign_definition"],
            plan=context["plan"],
            plan_definition=context["plan_definition"],
            run=context["run"],
            run_definition=context["run_definition"],
            disclosure_manifest=context["manifest"],
            disclosure_definition=context["disclosure_definition"],
            verified_plan_envelope=context["verified_plan"],
            verified_run_envelope=context["verified_run"],
            verified_disclosure_envelope=wrong_disclosure,
            definition=_adjudication_definition(context),
        )


def test_adjudication_rejects_campaign_or_manifest_substitution():
    context = _full_campaign()
    with pytest.raises(HveeContractError, match="does not bind the qualification"):
        _build_adjudication(
            context,
            _adjudication_definition(
                context,
                campaign_sha256=_digest("other-campaign"),
            ),
        )
    with pytest.raises(HveeContractError, match="does not bind the disclosure"):
        _build_adjudication(
            context,
            _adjudication_definition(
                context,
                disclosure_manifest_sha256=_digest("other-manifest"),
            ),
        )


def test_adjudication_rejects_unregistered_procedure_or_reviewer_roster():
    context = _full_campaign()
    with pytest.raises(HveeContractError, match="preregistered procedure"):
        _build_adjudication(
            context,
            _adjudication_definition(
                context,
                adjudication_procedure_sha256=_digest("other-procedure"),
            ),
        )
    with pytest.raises(HveeContractError, match="roster does not match"):
        _build_adjudication(
            context,
            _adjudication_definition(
                context,
                adjudicators=_adjudicators(
                    index=0,
                    key_id="different-primary-adjudicator",
                ),
            ),
        )


def test_adjudication_rejects_missing_reordered_or_duplicate_cases():
    context = _full_campaign()
    definition = _adjudication_definition(context)

    missing = _adjudication_definition(context, cases=definition.cases[:-1])
    with pytest.raises(HveeContractError, match="retain every campaign case"):
        _build_adjudication(context, missing)

    with pytest.raises(HveeContractError, match="unique and sorted"):
        _adjudication_definition(
            context,
            cases=tuple(reversed(definition.cases)),
        )


def test_adjudication_rejects_stratum_and_execution_status_substitution():
    context = _full_campaign()
    definition = _adjudication_definition(context)
    first = definition.cases[0]
    other_stratum = next(
        stratum
        for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1
        if stratum != first.stratum
        and (
            stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1
        )
        == (
            first.stratum
            in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1
        )
    )
    changed = replace(first, stratum=other_stratum)
    cases = (changed, *definition.cases[1:])

    with pytest.raises(HveeContractError, match="does not match campaign evidence"):
        _build_adjudication(
            context,
            _adjudication_definition(context, cases=cases),
        )


def test_adjudication_verification_rejects_tampered_counts_or_verdict():
    context = _full_campaign()
    definition = _adjudication_definition(context)
    bundle = _build_adjudication(context, definition)
    tampered = copy.deepcopy(bundle.payload)
    tampered["statistical_assessment"]["qualification_verdict"] = "pass"

    with pytest.raises(HveeContractError, match="expected SHA-256"):
        verify_critical_number_private_qualification_adjudication(
            payload=tampered,
            expected_sha256=bundle.sha256,
            campaign=context["campaign"],
            protocol=context["protocol"],
            campaign_definition=context["campaign_definition"],
            plan=context["plan"],
            plan_definition=context["plan_definition"],
            run=context["run"],
            run_definition=context["run_definition"],
            disclosure_manifest=context["manifest"],
            disclosure_definition=context["disclosure_definition"],
            verified_plan_envelope=context["verified_plan"],
            verified_run_envelope=context["verified_run"],
            verified_disclosure_envelope=context["verified_disclosure"],
            definition=definition,
        )


def test_adjudication_artifact_preserves_private_content_boundary():
    context = _full_campaign()
    bundle = _build_adjudication(context)
    serialized = repr(bundle.payload)

    assert "private reference" not in serialized
    assert "private expected" not in serialized
    assert "private source" not in serialized
    assert "private output" not in serialized
    assert "private-qualification-" not in serialized
    assert bundle.payload["confidentiality"] == {
        "private_case_content_in_artifact": False,
        "expected_results_in_artifact": False,
        "private_provenance_in_artifact": False,
        "evaluator_outputs_in_artifact": False,
        "private_salts_in_artifact": False,
        "adjudication_record_contents_in_artifact": False,
        "opaque_commitments_and_outcomes_only": True,
    }


def test_campaign_and_adjudication_never_issue_qualification_or_enforcement():
    context = _full_campaign()
    adjudication = _build_adjudication(context)

    for artifact in (context["protocol"], context["campaign"], adjudication):
        boundary = artifact.payload["qualification"]
        assert boundary == {
            "campaign_mechanics_verified": True,
            "statistical_qualification_assessed": False,
            "evaluator_status": "experimental",
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        }
    assert adjudication.payload["statistical_assessment"] == {
        "criteria_sha256": calculate_critical_number_private_qualification_sha256(
            context["protocol"].payload["preregistration"][
                "statistical_acceptance_criteria"
            ]
        ),
        "criteria_frozen_before_outputs": True,
        "qualification_statistics_calculated": False,
        "acceptance_criteria_evaluated": False,
        "qualification_verdict": None,
    }


def test_statistical_assessment_rebuilds_chain_and_meets_extreme_criteria():
    context = _full_campaign(
        statistical_criteria=_assessment_criteria(),
        execution_statuses=_all_completed_statuses(),
    )
    definition = _adjudication_definition(context)
    adjudication = _build_adjudication(context, definition)
    first = _build_assessment(context, definition, adjudication)
    second = _build_assessment(context, definition, adjudication)

    assert first == second
    assert first.payload["sealed_evidence"]["complete_chain_reverified"] is True
    assert first.payload["readiness"]["all_minimums_met"] is True
    assert first.payload["statistical_claims"]["family_size"] == 14
    assert first.payload["statistical_claims"]["all_claims_met"] is True
    assert first.payload["result"] == {
        "value": (
            ASRCriticalNumberPrivateStatisticalAssessmentResult
            .MEETS_PREREGISTERED_CRITERIA.value
        ),
        "all_minimums_met": True,
        "all_fraction_gates_met": True,
        "all_statistical_claims_met": True,
    }

    verified = verify_critical_number_private_statistical_assessment_v1(
        payload=first.payload,
        expected_sha256=first.sha256,
        method_manifest=(
            build_critical_number_private_statistical_method_manifest_v1()
        ),
        adjudication=adjudication,
        campaign=context["campaign"],
        protocol=context["protocol"],
        campaign_definition=context["campaign_definition"],
        plan=context["plan"],
        plan_definition=context["plan_definition"],
        run=context["run"],
        run_definition=context["run_definition"],
        disclosure_manifest=context["manifest"],
        disclosure_definition=context["disclosure_definition"],
        verified_plan_envelope=context["verified_plan"],
        verified_run_envelope=context["verified_run"],
        verified_disclosure_envelope=context["verified_disclosure"],
        adjudication_definition=definition,
    )
    assert verified == first


def test_statistical_assessment_reports_non_meeting_holm_claim():
    context = _full_campaign(
        statistical_criteria=_assessment_criteria(),
        execution_statuses=_all_completed_statuses(),
    )
    definition = _adjudication_definition(context)
    detected_index = next(
        index
        for index, case in enumerate(definition.cases)
        if case.outcome
        == ASRCriticalNumberPrivateQualificationAdjudicationOutcome.DETECTED
    )
    changed_cases = list(definition.cases)
    changed_cases[detected_index] = replace(
        changed_cases[detected_index],
        outcome=ASRCriticalNumberPrivateQualificationAdjudicationOutcome.MISSED,
    )
    changed_definition = replace(definition, cases=tuple(changed_cases))
    assessment = _build_assessment(context, changed_definition)

    assert assessment.payload["readiness"]["all_minimums_met"] is True
    assert assessment.payload["result"]["value"] == (
        ASRCriticalNumberPrivateStatisticalAssessmentResult
        .DOES_NOT_MEET_PREREGISTERED_CRITERIA.value
    )
    failed = [
        claim
        for claim in assessment.payload["statistical_claims"]["claims"]
        if not claim["meets_criterion"]
    ]
    assert len(failed) == 1
    assert failed[0]["estimand"] == "oracle_detection"
    assert failed[0]["bound_meets_criterion"] is True
    assert failed[0]["holm_rejected"] is False


def test_statistical_assessment_stops_when_evidence_is_insufficient():
    context = _full_campaign(
        statistical_criteria=_assessment_criteria(),
    )
    assessment = _build_assessment(context)

    assert assessment.payload["readiness"]["all_minimums_met"] is False
    assert assessment.payload["statistical_claims"]["calculated"] is False
    assert assessment.payload["statistical_claims"]["claims"] == []
    assert assessment.payload["result"]["value"] == (
        ASRCriticalNumberPrivateStatisticalAssessmentResult.INSUFFICIENT_EVIDENCE.value
    )


def test_statistical_assessment_rejects_unbound_method_manifest():
    context = _full_campaign(
        statistical_criteria=_criteria(),
        execution_statuses=_all_completed_statuses(),
    )

    with pytest.raises(HveeContractError, match="do not bind the v1"):
        _build_assessment(context)


def test_statistical_assessment_is_aggregate_and_non_certifying():
    context = _full_campaign(
        statistical_criteria=_assessment_criteria(),
        execution_statuses=_all_completed_statuses(),
    )
    assessment = _build_assessment(context)
    serialized = repr(assessment.payload)

    assert all(
        case.case_token not in serialized
        for case in context["plan_definition"].cases
    )
    assert "private reference" not in serialized
    assert "private expected" not in serialized
    assert assessment.payload["qualification"] == {
        "campaign_mechanics_verified": True,
        "statistical_qualification_assessed": True,
        "evaluator_status": "experimental",
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }

def test_private_qualification_public_exports_are_complete():
    expected = {
        "ASRCriticalNumberPrivateStatisticalAssessmentBundle",
        "ASRCriticalNumberPrivateStatisticalAssessmentResult",
        "ASRCriticalNumberPrivateStatisticalMethodManifestBundle",
        "CRITICAL_NUMBER_PRIVATE_STATISTICAL_ASSESSMENT_SCHEMA_VERSION",
        "build_critical_number_private_statistical_assessment_v1",
        "build_critical_number_private_statistical_method_manifest_v1",
        "verify_critical_number_private_statistical_assessment_v1",
        "verify_critical_number_private_statistical_method_manifest_v1",
        "CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ADJUDICATION_SCHEMA_VERSION",
        "CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CAMPAIGN_SCHEMA_VERSION",
        "CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1",
        "CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1",
        "CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_KEY",
        "CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_SCHEMA_VERSION",
        "CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_VERSION",
        "CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE",
        "CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1",
        "ASRCriticalNumberPrivateQualificationAdjudicationBundle",
        "ASRCriticalNumberPrivateQualificationAdjudicationDefinition",
        "ASRCriticalNumberPrivateQualificationAdjudicationOutcome",
        "ASRCriticalNumberPrivateQualificationAdjudicator",
        "ASRCriticalNumberPrivateQualificationAdjudicatorRole",
        "ASRCriticalNumberPrivateQualificationCampaignBundle",
        "ASRCriticalNumberPrivateQualificationCampaignDefinition",
        "ASRCriticalNumberPrivateQualificationCaseAdjudication",
        "ASRCriticalNumberPrivateQualificationProtocolBundle",
        "ASRCriticalNumberPrivateQualificationStatisticalCriteria",
        "ASRCriticalNumberPrivateQualificationStratum",
        "ASRCriticalNumberPrivateQualificationStratumDefinition",
        "build_critical_number_private_qualification_adjudication",
        "build_critical_number_private_qualification_campaign",
        "build_critical_number_private_qualification_protocol",
        "build_critical_number_private_qualification_protocol_revision",
        "calculate_critical_number_private_qualification_adjudicator_roster_sha256",
        "calculate_critical_number_private_qualification_sha256",
        "verify_critical_number_private_qualification_adjudication",
        "verify_critical_number_private_qualification_campaign",
        "verify_critical_number_private_qualification_protocol",
    }

    assert expected <= set(asr.__all__)
    assert all(hasattr(asr, name) for name in expected)
