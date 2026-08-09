from __future__ import annotations

import copy
import hashlib
import hmac
from dataclasses import replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs import asr
from hvee.packs.asr import critical_number_private_evidence as evidence_module
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
)
from hvee.packs.asr.critical_number_private_evidence import (
    CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEME,
    CRITICAL_NUMBER_PRIVATE_EVIDENCE_ENVELOPE_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_KEY,
    CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_VERSION,
    CRITICAL_NUMBER_PRIVATE_EVIDENCE_SIGNATURE_ENCODING,
    ASRCriticalNumberPrivateEvidenceArtifactType,
    ASRCriticalNumberPrivateEvidenceCaseDisclosure,
    ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
    ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    ASRCriticalNumberPrivateEvidenceEnvelopeBundle,
    ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
    ASRCriticalNumberPrivateEvidenceReplayState,
    ASRCriticalNumberPrivateEvidenceSigner,
    build_critical_number_private_disclosure_evidence_envelope,
    build_critical_number_private_evidence_disclosure_manifest,
    build_critical_number_private_holdout_blind_run_evidence_envelope,
    build_critical_number_private_holdout_plan_evidence_envelope,
    calculate_critical_number_private_evaluator_output_commitment,
    calculate_critical_number_private_evidence_sha256,
    verify_critical_number_private_disclosure_evidence_envelope,
    verify_critical_number_private_evidence_disclosure_manifest,
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


_SIGNING_KEY = b"private-evidence-test-signing-key-not-production"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _salt(label: str) -> str:
    return f"private-evidence-{label}-" + ("s" * 32)


def _sign(message: bytes) -> bytes:
    return hmac.digest(_SIGNING_KEY, message, "sha256")


def _verify(message: bytes, signature: bytes) -> bool:
    return hmac.compare_digest(_sign(message), signature)


def _signer(**changes: object) -> ASRCriticalNumberPrivateEvidenceSigner:
    values: dict[str, object] = {
        "key_id": "critical-number-private-evidence-test-key",
        "algorithm": "test-hmac-sha256",
        "public_key_sha256": _digest("test-public-key-material"),
    }
    values.update(changes)
    return ASRCriticalNumberPrivateEvidenceSigner(**values)


def _private_case(case_id: str, slices: tuple[str, ...]):
    disclosure = ASRCriticalNumberPrivateEvidenceCaseDisclosure(
        case_token_payload={"case_id": case_id},
        case_token_private_salt=_salt(f"{case_id}-token"),
        case_payload={
            "reference": f"private reference {case_id}",
            "generated": f"private generated {case_id}",
        },
        case_payload_private_salt=_salt(f"{case_id}-payload"),
        expected_result={"expected": f"private oracle {case_id}"},
        expected_result_private_salt=_salt(f"{case_id}-expected"),
        provenance={"source": f"private source {case_id}"},
        provenance_private_salt=_salt(f"{case_id}-provenance"),
        evaluator_output={"actual": f"private evaluator output {case_id}"},
        evaluator_output_private_salt=_salt(f"{case_id}-output"),
    )
    case = ASRCriticalNumberPrivateHoldoutCaseCommitment(
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
        slice_keys=slices,
    )
    return case, disclosure


def _cases_and_disclosures():
    pairs = (
        _private_case(
            "dosage-substitution",
            ("dangerous", "measurement", "substitution"),
        ),
        _private_case("currency-equivalence", ("currency", "equivalence")),
        _private_case("unsupported-fraction", ("unsupported",)),
    )
    ordered = tuple(sorted(pairs, key=lambda pair: pair[0].case_token))
    return (
        tuple(pair[0] for pair in ordered),
        tuple(pair[1] for pair in ordered),
    )


def _plan_definition():
    cases, _ = _cases_and_disclosures()
    return ASRCriticalNumberPrivateHoldoutPlanDefinition(
        plan_id="critical-number-private-certification-plan",
        plan_version="1.0.0",
        run_id="critical-number-private-certification-run-001",
        holdout_set_key="hetren.asr.critical-number-private-set.en-us",
        holdout_set_version="1.0.0",
        holdout_manifest_sha256=_digest("holdout-manifest"),
        population_snapshot_sha256=_digest("population-snapshot"),
        risk_register_sha256=_digest("risk-register"),
        historical_evidence_sha256=_digest("history-snapshot"),
        sampling_protocol_sha256=_digest("sampling-protocol"),
        analysis_protocol_sha256=_digest("analysis-protocol"),
        cases=cases,
    )


def _holdout():
    plan_definition = _plan_definition()
    plan = build_critical_number_private_holdout_plan(plan_definition)
    _, disclosures = _cases_and_disclosures()
    statuses = (
        ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.FAILED,
        ASRCriticalNumberPrivateHoldoutExecutionStatus.TIMED_OUT,
    )
    executions = tuple(
        ASRCriticalNumberPrivateHoldoutCaseExecution(
            case_token=case.case_token,
            status=status,
            evaluator_output_sha256=(
                calculate_critical_number_private_evaluator_output_commitment(
                    payload=disclosure.evaluator_output,
                    private_salt=disclosure.evaluator_output_private_salt,
                )
            ),
        )
        for case, disclosure, status in zip(
            plan_definition.cases,
            disclosures,
            statuses,
            strict=True,
        )
    )
    run_definition = ASRCriticalNumberPrivateHoldoutBlindRunDefinition(
        run_id=plan_definition.run_id,
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
    return plan_definition, plan, run_definition, run, disclosures


def _envelope_definition(
    *,
    run_id: str,
    sequence: int,
    previous: str | None,
    **changes: object,
) -> ASRCriticalNumberPrivateEvidenceEnvelopeDefinition:
    values: dict[str, object] = {
        "chain_id": run_id,
        "envelope_id": f"critical-number-private-evidence-{sequence:03d}",
        "sequence_number": sequence,
        "issued_at_utc": f"2026-08-09T20:0{sequence}:00Z",
        "nonce_sha256": _digest(f"nonce-{sequence}"),
        "previous_envelope_sha256": previous,
        "signer": _signer(),
    }
    values.update(changes)
    return ASRCriticalNumberPrivateEvidenceEnvelopeDefinition(**values)


def _signed_and_verified_run_chain():
    plan_definition, plan, run_definition, run, disclosures = _holdout()
    replay = ASRCriticalNumberPrivateEvidenceReplayState(
        chain_id=plan_definition.run_id
    )
    plan_envelope = build_critical_number_private_holdout_plan_evidence_envelope(
        plan=plan,
        plan_definition=plan_definition,
        envelope_definition=_envelope_definition(
            run_id=plan_definition.run_id,
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
            run_id=plan_definition.run_id,
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
    return (
        plan_definition,
        plan,
        run_definition,
        run,
        disclosures,
        plan_envelope,
        verified_plan,
        run_envelope,
        verified_run,
    )


def _disclosure_definition(
    disclosures: tuple[ASRCriticalNumberPrivateEvidenceCaseDisclosure, ...],
    **changes: object,
) -> ASRCriticalNumberPrivateEvidenceDisclosureDefinition:
    values: dict[str, object] = {
        "verification_id": "critical-number-private-independent-verification",
        "verification_version": "1.0.0",
        "verifier_key_id": "critical-number-private-independent-verifier",
        "verification_procedure_sha256": _digest("verification-procedure"),
        "verification_environment_sha256": _digest("verification-environment"),
        "independence_attestation_sha256": _digest("independence-attestation"),
        "disclosures": disclosures,
    }
    values.update(changes)
    return ASRCriticalNumberPrivateEvidenceDisclosureDefinition(**values)


def _manifest_chain():
    chain = _signed_and_verified_run_chain()
    (
        plan_definition,
        plan,
        run_definition,
        run,
        disclosures,
        plan_envelope,
        verified_plan,
        run_envelope,
        verified_run,
    ) = chain
    definition = _disclosure_definition(disclosures)
    manifest = build_critical_number_private_evidence_disclosure_manifest(
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        verified_plan_envelope=verified_plan,
        verified_run_envelope=verified_run,
        definition=definition,
    )
    return (*chain, definition, manifest)


def _tampered_envelope(
    envelope: ASRCriticalNumberPrivateEvidenceEnvelopeBundle,
    mutate,
) -> ASRCriticalNumberPrivateEvidenceEnvelopeBundle:
    payload = copy.deepcopy(envelope.payload)
    mutate(payload)
    return ASRCriticalNumberPrivateEvidenceEnvelopeBundle(
        payload=payload,
        sha256=calculate_critical_number_private_evidence_sha256(payload),
    )


def test_plan_envelope_is_deterministic_signed_and_bound_to_exact_v1_artifacts():
    plan_definition, plan, *_ = _holdout()
    definition = _envelope_definition(
        run_id=plan_definition.run_id,
        sequence=1,
        previous=None,
    )
    first = build_critical_number_private_holdout_plan_evidence_envelope(
        plan=plan,
        plan_definition=plan_definition,
        envelope_definition=definition,
        sign=_sign,
    )
    second = build_critical_number_private_holdout_plan_evidence_envelope(
        plan=plan,
        plan_definition=plan_definition,
        envelope_definition=definition,
        sign=_sign,
    )

    assert first == second
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRIVATE_EVIDENCE_ENVELOPE_SCHEMA_VERSION
    )
    assert first.payload["protocol"] == {
        "key": CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_KEY,
        "version": CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_VERSION,
        "artifact": "signed_evidence_envelope",
        "signature_encoding": CRITICAL_NUMBER_PRIVATE_EVIDENCE_SIGNATURE_ENCODING,
    }
    assert first.payload["artifact"] == {
        "type": "preregistered_private_holdout_plan",
        "sha256": plan.sha256,
    }
    assert first.payload["bindings"]["assurance_profile"]["sha256"] == (
        CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
    )
    assert first.payload["signature"]["value"]


def test_envelope_signing_callback_is_external_and_fail_closed():
    plan_definition, plan, *_ = _holdout()
    definition = _envelope_definition(
        run_id=plan_definition.run_id,
        sequence=1,
        previous=None,
    )

    with pytest.raises(HveeContractError, match="1-4096 bytes"):
        build_critical_number_private_holdout_plan_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            envelope_definition=definition,
            sign=lambda _: b"",
        )

    def failing_signer(_: bytes) -> bytes:
        raise RuntimeError("hardware signer unavailable")

    with pytest.raises(HveeContractError, match="callback failed"):
        build_critical_number_private_holdout_plan_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            envelope_definition=definition,
            sign=failing_signer,
        )


def test_plan_and_blind_run_form_a_verified_replay_resistant_chain():
    *_, plan_envelope, verified_plan, run_envelope, verified_run = (
        _signed_and_verified_run_chain()
    )

    assert verified_plan.replay_state.last_sequence_number == 1
    assert verified_plan.replay_state.last_envelope_sha256 == plan_envelope.sha256
    assert verified_run.replay_state.last_sequence_number == 2
    assert verified_run.replay_state.last_envelope_sha256 == run_envelope.sha256
    assert verified_run.definition.previous_envelope_sha256 == plan_envelope.sha256
    assert len(verified_run.replay_state.consumed_envelope_ids) == 2
    assert len(verified_run.replay_state.consumed_nonce_sha256s) == 2


def test_exact_envelope_replay_is_rejected():
    (
        plan_definition,
        plan,
        _,
        _,
        _,
        plan_envelope,
        verified_plan,
        _,
        _,
    ) = _signed_and_verified_run_chain()

    with pytest.raises(HveeContractError, match="missing or replayed"):
        verify_critical_number_private_holdout_plan_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            envelope=plan_envelope,
            trusted_signer=_signer(),
            replay_state=verified_plan.replay_state,
            verify_signature=_verify,
        )


def test_reused_nonce_and_non_increasing_timestamp_are_rejected():
    (
        plan_definition,
        plan,
        run_definition,
        run,
        _,
        plan_envelope,
        verified_plan,
        _,
        _,
    ) = _signed_and_verified_run_chain()
    reused_nonce = _envelope_definition(
        run_id=plan_definition.run_id,
        sequence=2,
        previous=plan_envelope.sha256,
        nonce_sha256=verified_plan.definition.nonce_sha256,
    )
    envelope = build_critical_number_private_holdout_blind_run_evidence_envelope(
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        plan_envelope=plan_envelope,
        envelope_definition=reused_nonce,
        sign=_sign,
    )
    with pytest.raises(HveeContractError, match="nonce was already consumed"):
        verify_critical_number_private_holdout_blind_run_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            envelope=envelope,
            verified_plan_envelope=verified_plan,
            trusted_signer=_signer(),
            verify_signature=_verify,
        )

    stale_time = replace(
        reused_nonce,
        nonce_sha256=_digest("fresh-nonce"),
        issued_at_utc=verified_plan.definition.issued_at_utc,
    )
    envelope = build_critical_number_private_holdout_blind_run_evidence_envelope(
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        plan_envelope=plan_envelope,
        envelope_definition=stale_time,
        sign=_sign,
    )
    with pytest.raises(HveeContractError, match="timestamp must increase"):
        verify_critical_number_private_holdout_blind_run_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            envelope=envelope,
            verified_plan_envelope=verified_plan,
            trusted_signer=_signer(),
            verify_signature=_verify,
        )


def test_broken_or_out_of_order_envelope_chain_is_rejected_before_signing():
    plan_definition, plan, run_definition, run, *_ = _holdout()
    plan_envelope = build_critical_number_private_holdout_plan_evidence_envelope(
        plan=plan,
        plan_definition=plan_definition,
        envelope_definition=_envelope_definition(
            run_id=plan_definition.run_id,
            sequence=1,
            previous=None,
        ),
        sign=_sign,
    )
    with pytest.raises(HveeContractError, match="follow the signed plan"):
        build_critical_number_private_holdout_blind_run_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            plan_envelope=plan_envelope,
            envelope_definition=_envelope_definition(
                run_id=plan_definition.run_id,
                sequence=3,
                previous=_digest("wrong-previous"),
            ),
            sign=_sign,
        )


def test_tampered_signature_artifact_and_untrusted_signer_are_rejected():
    plan_definition, plan, _, _, _, plan_envelope, *_ = (
        _signed_and_verified_run_chain()
    )
    replay = ASRCriticalNumberPrivateEvidenceReplayState(
        chain_id=plan_definition.run_id
    )
    tampered_signature = _tampered_envelope(
        plan_envelope,
        lambda payload: payload["signature"].update({"value": "00" * 32}),
    )
    with pytest.raises(HveeContractError, match="signature is invalid"):
        verify_critical_number_private_holdout_plan_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            envelope=tampered_signature,
            trusted_signer=_signer(),
            replay_state=replay,
            verify_signature=_verify,
        )

    tampered_artifact = _tampered_envelope(
        plan_envelope,
        lambda payload: payload["artifact"].update(
            {"sha256": _digest("substituted-plan")}
        ),
    )
    with pytest.raises(HveeContractError, match="artifact SHA-256"):
        verify_critical_number_private_holdout_plan_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            envelope=tampered_artifact,
            trusted_signer=_signer(),
            replay_state=replay,
            verify_signature=_verify,
        )

    with pytest.raises(HveeContractError, match="signer is not trusted"):
        verify_critical_number_private_holdout_plan_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            envelope=plan_envelope,
            trusted_signer=_signer(key_id="untrusted-private-evidence-key"),
            replay_state=replay,
            verify_signature=_verify,
        )


def test_signature_verifier_exception_and_false_result_fail_closed():
    plan_definition, plan, _, _, _, plan_envelope, *_ = (
        _signed_and_verified_run_chain()
    )
    replay = ASRCriticalNumberPrivateEvidenceReplayState(
        chain_id=plan_definition.run_id
    )
    with pytest.raises(HveeContractError, match="signature is invalid"):
        verify_critical_number_private_holdout_plan_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            envelope=plan_envelope,
            trusted_signer=_signer(),
            replay_state=replay,
            verify_signature=lambda _message, _signature: False,
        )

    def failing_verifier(_message: bytes, _signature: bytes) -> bool:
        raise RuntimeError("verifier unavailable")

    with pytest.raises(HveeContractError, match="callback failed"):
        verify_critical_number_private_holdout_plan_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            envelope=plan_envelope,
            trusted_signer=_signer(),
            replay_state=replay,
            verify_signature=failing_verifier,
        )


def test_disclosure_manifest_recomputes_all_cases_and_is_deterministic():
    *chain, definition, first = _manifest_chain()
    (
        plan_definition,
        plan,
        run_definition,
        run,
        _,
        _,
        verified_plan,
        _,
        verified_run,
    ) = chain
    second = build_critical_number_private_evidence_disclosure_manifest(
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        verified_plan_envelope=verified_plan,
        verified_run_envelope=verified_run,
        definition=definition,
    )

    assert first == second
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEMA_VERSION
    )
    assert first.payload["protocol"]["disclosure_scheme"] == (
        CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEME
    )
    verification = first.payload["independent_verification"]
    assert verification["selected_case_count"] == 3
    assert verification["verified_case_count"] == 3
    assert verification["all_selected_cases_retained"] is True
    assert verification["all_commitments_recomputed"] is True
    assert all(case["commitments_recomputed"] for case in verification["cases"])


def test_disclosure_manifest_contains_addresses_not_private_material():
    *_, manifest = _manifest_chain()
    serialized = str(manifest.payload)

    for forbidden in (
        "private reference",
        "private generated",
        "private oracle",
        "private source",
        "private evaluator output",
        "private-evidence-dosage",
    ):
        assert forbidden not in serialized
    assert manifest.payload["confidentiality"] == {
        "private_case_content_in_artifact": False,
        "expected_results_in_artifact": False,
        "private_provenance_in_artifact": False,
        "evaluator_outputs_in_artifact": False,
        "private_salts_in_artifact": False,
        "content_addresses_only": True,
    }


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("case_payload", "case payload"),
        ("expected_result", "expected result"),
        ("provenance", "provenance"),
        ("evaluator_output", "evaluator output"),
    ),
)
def test_independent_recomputation_rejects_each_tampered_private_component(
    field: str,
    message: str,
):
    chain = _signed_and_verified_run_chain()
    (
        plan_definition,
        plan,
        run_definition,
        run,
        disclosures,
        _,
        verified_plan,
        _,
        verified_run,
    ) = chain
    changed = list(disclosures)
    changed[0] = replace(changed[0], **{field: {"tampered": True}})

    with pytest.raises(HveeContractError, match=message):
        build_critical_number_private_evidence_disclosure_manifest(
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            verified_plan_envelope=verified_plan,
            verified_run_envelope=verified_run,
            definition=_disclosure_definition(tuple(changed)),
        )


def test_disclosure_rejects_wrong_token_missing_case_and_case_substitution():
    chain = _signed_and_verified_run_chain()
    (
        plan_definition,
        plan,
        run_definition,
        run,
        disclosures,
        _,
        verified_plan,
        _,
        verified_run,
    ) = chain
    wrong_token = replace(disclosures[0], case_token_payload={"case_id": "wrong"})
    with pytest.raises(HveeContractError, match="case token"):
        build_critical_number_private_evidence_disclosure_manifest(
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            verified_plan_envelope=verified_plan,
            verified_run_envelope=verified_run,
            definition=_disclosure_definition((wrong_token, *disclosures[1:])),
        )

    with pytest.raises(HveeContractError, match="retain every"):
        build_critical_number_private_evidence_disclosure_manifest(
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            verified_plan_envelope=verified_plan,
            verified_run_envelope=verified_run,
            definition=_disclosure_definition(disclosures[:-1]),
        )

    with pytest.raises(HveeContractError, match="case token"):
        build_critical_number_private_evidence_disclosure_manifest(
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            verified_plan_envelope=verified_plan,
            verified_run_envelope=verified_run,
            definition=_disclosure_definition(
                (disclosures[1], disclosures[0], disclosures[2])
            ),
        )


def test_disclosure_requires_the_verified_plan_and_run_chain():
    chain = _signed_and_verified_run_chain()
    (
        plan_definition,
        plan,
        run_definition,
        run,
        disclosures,
        _,
        verified_plan,
        _,
        verified_run,
    ) = chain
    unrelated_run = replace(
        verified_run,
        artifact_sha256=_digest("unrelated-run"),
    )

    with pytest.raises(HveeContractError, match="verified plan and blind-run"):
        build_critical_number_private_evidence_disclosure_manifest(
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            verified_plan_envelope=verified_plan,
            verified_run_envelope=unrelated_run,
            definition=_disclosure_definition(disclosures),
        )


def test_disclosure_manifest_verification_rebuilds_exact_evidence():
    (
        plan_definition,
        plan,
        run_definition,
        run,
        _,
        _,
        verified_plan,
        _,
        verified_run,
        definition,
        manifest,
    ) = _manifest_chain()
    assert verify_critical_number_private_evidence_disclosure_manifest(
        payload=manifest.payload,
        expected_sha256=manifest.sha256,
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        verified_plan_envelope=verified_plan,
        verified_run_envelope=verified_run,
        definition=definition,
    ) == manifest

    payload = copy.deepcopy(manifest.payload)
    payload["independent_verification"]["verified_case_count"] = 2
    digest = calculate_critical_number_private_evidence_sha256(payload)
    with pytest.raises(HveeContractError, match="independently recomputed"):
        verify_critical_number_private_evidence_disclosure_manifest(
            payload=payload,
            expected_sha256=digest,
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            verified_plan_envelope=verified_plan,
            verified_run_envelope=verified_run,
            definition=definition,
        )


def test_disclosure_manifest_can_be_signed_as_chain_sequence_three():
    (
        plan_definition,
        _,
        _,
        _,
        _,
        _,
        _,
        run_envelope,
        verified_run,
        _,
        manifest,
    ) = _manifest_chain()
    envelope = build_critical_number_private_disclosure_evidence_envelope(
        manifest=manifest,
        verified_run_envelope=verified_run,
        envelope_definition=_envelope_definition(
            run_id=plan_definition.run_id,
            sequence=3,
            previous=run_envelope.sha256,
        ),
        sign=_sign,
    )
    verified = verify_critical_number_private_disclosure_evidence_envelope(
        manifest=manifest,
        envelope=envelope,
        verified_run_envelope=verified_run,
        trusted_signer=_signer(),
        verify_signature=_verify,
    )

    assert verified.artifact_type == (
        ASRCriticalNumberPrivateEvidenceArtifactType.DISCLOSURE_MANIFEST
    )
    assert verified.artifact_sha256 == manifest.sha256
    assert verified.replay_state.last_sequence_number == 3
    assert verified.replay_state.last_envelope_sha256 == envelope.sha256


def test_verification_never_claims_certification_or_release_enforcement():
    *_, manifest = _manifest_chain()
    qualification = manifest.payload["qualification"]

    assert qualification == {
        "evidence_integrity_verified": True,
        "evaluator_status": "experimental",
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }
    assert "verdict" not in manifest.payload
    assert "certified" not in manifest.payload


def test_v1_binding_drift_is_rejected(monkeypatch):
    monkeypatch.setattr(
        evidence_module,
        "CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1",
        "0" * 64,
    )
    plan_definition, plan, *_ = _holdout()

    with pytest.raises(HveeContractError, match="assurance binding changed"):
        build_critical_number_private_holdout_plan_evidence_envelope(
            plan=plan,
            plan_definition=plan_definition,
            envelope_definition=_envelope_definition(
                run_id=plan_definition.run_id,
                sequence=1,
                previous=None,
            ),
            sign=_sign,
        )


def test_public_asr_pack_exports_private_evidence_contracts():
    expected = (
        "ASRCriticalNumberPrivateEvidenceArtifactType",
        "ASRCriticalNumberPrivateEvidenceCaseDisclosure",
        "ASRCriticalNumberPrivateEvidenceDisclosureDefinition",
        "ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle",
        "ASRCriticalNumberPrivateEvidenceEnvelopeBundle",
        "ASRCriticalNumberPrivateEvidenceEnvelopeDefinition",
        "ASRCriticalNumberPrivateEvidenceReplayState",
        "ASRCriticalNumberPrivateEvidenceSigner",
        "ASRCriticalNumberPrivateEvidenceVerifiedEnvelope",
        "build_critical_number_private_disclosure_evidence_envelope",
        "build_critical_number_private_evidence_disclosure_manifest",
        "build_critical_number_private_holdout_blind_run_evidence_envelope",
        "build_critical_number_private_holdout_plan_evidence_envelope",
        "calculate_critical_number_private_evaluator_output_commitment",
        "calculate_critical_number_private_evidence_sha256",
        "verify_critical_number_private_disclosure_evidence_envelope",
        "verify_critical_number_private_evidence_disclosure_manifest",
        "verify_critical_number_private_holdout_blind_run_evidence_envelope",
        "verify_critical_number_private_holdout_plan_evidence_envelope",
    )
    for name in expected:
        assert name in asr.__all__
        assert getattr(asr, name) is getattr(evidence_module, name)


def test_contract_validation_rejects_invalid_timestamps_signatures_and_replay_state():
    with pytest.raises(HveeContractError, match="canonical UTC"):
        _envelope_definition(
            run_id="critical-number-private-certification-run-001",
            sequence=1,
            previous=None,
            issued_at_utc="2026-08-09T20:01:00-05:00",
        )

    with pytest.raises(HveeContractError, match="replay history"):
        ASRCriticalNumberPrivateEvidenceReplayState(
            chain_id="critical-number-private-certification-run-001",
            last_sequence_number=1,
            last_envelope_sha256=_digest("envelope"),
            last_issued_at_utc="2026-08-09T20:01:00Z",
        )

    with pytest.raises(HveeContractError, match="SHA-256"):
        ASRCriticalNumberPrivateEvidenceEnvelopeBundle(
            payload={"invalid": True},
            sha256="not-a-digest",
        )


def test_manifest_bundle_rejects_tampered_payload_digest():
    *_, manifest = _manifest_chain()
    payload = copy.deepcopy(manifest.payload)
    payload["qualification"]["certification_issued"] = True

    with pytest.raises(HveeContractError, match="does not match its payload"):
        ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle(
            payload=payload,
            sha256=manifest.sha256,
        )
