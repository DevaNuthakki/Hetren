from __future__ import annotations

import copy
import hashlib
import hmac
from dataclasses import replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs import asr
from hvee.packs.asr import critical_number_production_evidence as production_module
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
)
from hvee.packs.asr.critical_number_private_holdout import (
    ASRCriticalNumberPrivateHoldoutCaseCommitment,
    ASRCriticalNumberPrivateHoldoutPlanDefinition,
    build_critical_number_private_holdout_plan,
    calculate_critical_number_private_commitment,
)
from hvee.packs.asr.critical_number_production_evidence import (
    CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_KEY,
    CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_VERSION,
    CRITICAL_NUMBER_PRODUCTION_EVIDENCE_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRODUCTION_EXCLUSION_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRODUCTION_LINKAGE_SCHEME,
    ASRCriticalNumberPrivateHoldoutExclusionManifestBundle,
    ASRCriticalNumberProductionCaseCommitment,
    ASRCriticalNumberProductionEvidenceDefinition,
    ASRCriticalNumberProductionEvidenceManifestBundle,
    ASRCriticalNumberProductionUseAttestation,
    build_critical_number_private_holdout_exclusion_manifest,
    build_critical_number_production_evidence_manifest,
    calculate_critical_number_production_evidence_sha256,
    verify_critical_number_private_holdout_exclusion_manifest,
    verify_critical_number_production_evidence_manifest,
)


_LINKAGE_KEY = b"caller-owned-cross-set-linkage-key-for-tests"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _linkage_token(value: str) -> str:
    return hmac.digest(_LINKAGE_KEY, value.encode("utf-8"), "sha256").hex()


def _salt(label: str) -> str:
    return f"production-evidence-private-{label}-" + ("s" * 32)


def _private_case(label: str) -> ASRCriticalNumberPrivateHoldoutCaseCommitment:
    return ASRCriticalNumberPrivateHoldoutCaseCommitment(
        case_token=calculate_critical_number_private_commitment(
            payload={"private_case_id": label},
            private_salt=_salt(f"{label}-token"),
        ),
        case_payload_sha256=calculate_critical_number_private_commitment(
            payload={"private_payload": label},
            private_salt=_salt(f"{label}-payload"),
        ),
        expected_result_sha256=calculate_critical_number_private_commitment(
            payload={"private_expected": label},
            private_salt=_salt(f"{label}-expected"),
        ),
        provenance_sha256=calculate_critical_number_private_commitment(
            payload={"private_provenance": label},
            private_salt=_salt(f"{label}-provenance"),
        ),
        slice_keys=("critical-number",),
    )


def _private_plan_definition() -> ASRCriticalNumberPrivateHoldoutPlanDefinition:
    cases = tuple(
        sorted(
            (
                _private_case("private-case-one"),
                _private_case("private-case-two"),
                _private_case("private-case-three"),
            ),
            key=lambda case: case.case_token,
        )
    )
    return ASRCriticalNumberPrivateHoldoutPlanDefinition(
        plan_id="critical-number-private-exclusion-plan",
        plan_version="1.0.0",
        run_id="critical-number-private-exclusion-run-001",
        holdout_set_key="hetren.asr.critical-number-private-set.en-us",
        holdout_set_version="1.0.0",
        holdout_manifest_sha256=_digest("private-holdout-manifest"),
        population_snapshot_sha256=_digest("private-population-snapshot"),
        risk_register_sha256=_digest("private-risk-register"),
        historical_evidence_sha256=_digest("private-historical-evidence"),
        sampling_protocol_sha256=_digest("private-sampling-protocol"),
        analysis_protocol_sha256=_digest("private-analysis-protocol"),
        cases=cases,
    )


def _private_plan():
    definition = _private_plan_definition()
    return definition, build_critical_number_private_holdout_plan(definition)


def _private_tokens() -> tuple[str, ...]:
    return tuple(
        sorted(
            _linkage_token(label)
            for label in (
                "private-case-one",
                "private-case-two",
                "private-case-three",
            )
        )
    )


def _exclusion():
    plan_definition, plan = _private_plan()
    tokens = _private_tokens()
    exclusion = build_critical_number_private_holdout_exclusion_manifest(
        plan=plan,
        plan_definition=plan_definition,
        linkage_tokens=tokens,
    )
    return plan_definition, plan, tokens, exclusion


def _use_attestation(**changes: object):
    values: dict[str, object] = {
        "attested_at_utc": "2026-07-31T23:30:00Z",
        "production_data_use_authorized": True,
        "authorization_record_sha256": _digest("authorization-record"),
        "deidentification_completed": True,
        "deidentification_record_sha256": _digest("deidentification-record"),
        "retention_controls_confirmed": True,
        "retention_controls_record_sha256": _digest("retention-controls-record"),
        "evaluator_development_use_permitted": True,
        "permitted_use_record_sha256": _digest("permitted-use-record"),
    }
    values.update(changes)
    return ASRCriticalNumberProductionUseAttestation(**values)


def _production_case(label: str, observed_at_utc: str, **changes: object):
    values: dict[str, object] = {
        "case_id": f"production-case-{label}",
        "observed_at_utc": observed_at_utc,
        "source_record_sha256": _digest(f"source-record-{label}"),
        "deidentified_payload_sha256": _digest(f"deidentified-payload-{label}"),
        "lineage_sha256": _digest(f"lineage-{label}"),
        "cross_set_linkage_token": _linkage_token(f"production-case-{label}"),
    }
    values.update(changes)
    return ASRCriticalNumberProductionCaseCommitment(**values)


def _production_definition(exclusion_sha256: str, **changes: object):
    values: dict[str, object] = {
        "manifest_id": "critical-number-production-evidence-july-2026",
        "manifest_version": "1.0.0",
        "snapshot_at_utc": "2026-08-01T00:00:00Z",
        "source_window_started_at_utc": "2026-07-01T00:00:00Z",
        "source_window_ended_at_utc": "2026-07-31T23:59:59Z",
        "source_snapshot_sha256": _digest("production-source-snapshot"),
        "selection_protocol_sha256": _digest("production-selection-protocol"),
        "private_holdout_exclusion_sha256": exclusion_sha256,
        "cases": (
            _production_case("one", "2026-07-10T12:00:00Z"),
            _production_case("two", "2026-07-20T12:00:00Z"),
        ),
        "use_attestation": _use_attestation(),
    }
    values.update(changes)
    return ASRCriticalNumberProductionEvidenceDefinition(**values)


def _manifest():
    _, _, _, exclusion = _exclusion()
    definition = _production_definition(exclusion.sha256)
    manifest = build_critical_number_production_evidence_manifest(
        definition=definition,
        private_holdout_exclusion=exclusion,
    )
    return exclusion, definition, manifest


def test_private_exclusion_is_deterministic_and_bound_to_verified_plan():
    plan_definition, plan = _private_plan()
    tokens = _private_tokens()
    first = build_critical_number_private_holdout_exclusion_manifest(
        plan=plan,
        plan_definition=plan_definition,
        linkage_tokens=tokens,
    )
    second = build_critical_number_private_holdout_exclusion_manifest(
        plan=plan,
        plan_definition=plan_definition,
        linkage_tokens=tokens,
    )

    assert first == second
    assert first.sha256 == calculate_critical_number_production_evidence_sha256(
        first.payload
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRODUCTION_EXCLUSION_SCHEMA_VERSION
    )
    assert first.payload["protocol"] == {
        "key": CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_KEY,
        "version": CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_VERSION,
        "artifact": "private_holdout_exclusion_manifest",
        "linkage_scheme": CRITICAL_NUMBER_PRODUCTION_LINKAGE_SCHEME,
    }
    assert first.payload["private_holdout_binding"] == {
        "plan_sha256": plan.sha256,
        "case_count": len(plan_definition.cases),
        "complete_plan_coverage_attested": True,
        "linkage_tokens": list(tokens),
    }


def test_private_exclusion_contains_no_private_case_material_or_linkage_key():
    _, _, tokens, exclusion = _exclusion()
    serialized = repr(exclusion.payload)

    assert "private-case-one" not in serialized
    assert "private_payload" not in serialized
    assert _LINKAGE_KEY.decode("utf-8") not in serialized
    assert all(token in serialized for token in tokens)
    assert exclusion.payload["confidentiality"] == {
        "raw_audio_in_artifact": False,
        "raw_transcripts_in_artifact": False,
        "pii_in_artifact": False,
        "hmac_keys_in_artifact": False,
        "linkage_salts_in_artifact": False,
        "opaque_identifiers_and_commitments_only": True,
    }


def test_private_exclusion_requires_complete_unique_sorted_linkage_tokens():
    plan_definition, plan = _private_plan()
    tokens = _private_tokens()

    with pytest.raises(HveeContractError, match="one linkage token per case"):
        build_critical_number_private_holdout_exclusion_manifest(
            plan=plan,
            plan_definition=plan_definition,
            linkage_tokens=tokens[:-1],
        )
    with pytest.raises(HveeContractError, match="ordered by token"):
        build_critical_number_private_holdout_exclusion_manifest(
            plan=plan,
            plan_definition=plan_definition,
            linkage_tokens=tuple(reversed(tokens)),
        )
    duplicate_tokens = tuple(sorted((tokens[0], tokens[0], tokens[1])))
    with pytest.raises(HveeContractError, match="must be unique"):
        build_critical_number_private_holdout_exclusion_manifest(
            plan=plan,
            plan_definition=plan_definition,
            linkage_tokens=duplicate_tokens,
        )
    malformed = tuple(sorted((tokens[0], tokens[1], "A" * 64)))
    with pytest.raises(HveeContractError, match="lowercase SHA-256"):
        build_critical_number_private_holdout_exclusion_manifest(
            plan=plan,
            plan_definition=plan_definition,
            linkage_tokens=malformed,
        )


def test_private_exclusion_verifier_rejects_tampering_and_wrong_tokens():
    plan_definition, plan, tokens, exclusion = _exclusion()
    tampered = copy.deepcopy(exclusion.payload)
    tampered["evidence_boundary"]["release_enforcement_eligible"] = True
    tampered_sha256 = calculate_critical_number_production_evidence_sha256(tampered)

    with pytest.raises(HveeContractError, match="verified plan and tokens"):
        verify_critical_number_private_holdout_exclusion_manifest(
            payload=tampered,
            expected_sha256=tampered_sha256,
            plan=plan,
            plan_definition=plan_definition,
            linkage_tokens=tokens,
        )
    different_tokens = tuple(
        sorted(_linkage_token(f"different-private-{index}") for index in range(3))
    )
    with pytest.raises(HveeContractError, match="verified plan and tokens"):
        verify_critical_number_private_holdout_exclusion_manifest(
            payload=exclusion.payload,
            expected_sha256=exclusion.sha256,
            plan=plan,
            plan_definition=plan_definition,
            linkage_tokens=different_tokens,
        )


def test_production_manifest_is_deterministic_and_sealed():
    exclusion, definition, first = _manifest()
    second = build_critical_number_production_evidence_manifest(
        definition=definition,
        private_holdout_exclusion=exclusion,
    )

    assert first == second
    assert first.sha256 == calculate_critical_number_production_evidence_sha256(
        first.payload
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRODUCTION_EVIDENCE_SCHEMA_VERSION
    )
    assert first.payload["protocol"] == {
        "key": CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_KEY,
        "version": CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_VERSION,
        "artifact": "production_derived_evidence_manifest",
        "linkage_scheme": CRITICAL_NUMBER_PRODUCTION_LINKAGE_SCHEME,
    }
    snapshot = first.payload["production_snapshot"]
    assert snapshot["snapshot_at_utc"] == definition.snapshot_at_utc
    assert snapshot["source_window"] == {
        "started_at_utc": definition.source_window_started_at_utc,
        "ended_at_utc": definition.source_window_ended_at_utc,
    }
    assert snapshot["private_holdout_exclusion_sha256"] == exclusion.sha256
    assert snapshot["case_count"] == len(definition.cases)


def test_production_manifest_binds_exact_v1_evaluator_profile_and_assurance():
    _, _, manifest = _manifest()

    assert manifest.payload["bindings"] == {
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
            "key": "hetren.asr.critical-number-evaluator-assurance-profile.en-us",
            "version": "1.0.0",
            "status": "experimental",
            "sha256": CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
        },
    }


def test_production_manifest_records_attestations_without_compliance_claims():
    _, definition, manifest = _manifest()
    attestations = manifest.payload["production_snapshot"]["use_attestations"]

    assert attestations == {
        "attested_at_utc": definition.use_attestation.attested_at_utc,
        "production_data_use": {
            "authorized": True,
            "record_sha256": definition.use_attestation.authorization_record_sha256,
        },
        "deidentification": {
            "completed": True,
            "record_sha256": (
                definition.use_attestation.deidentification_record_sha256
            ),
        },
        "retention_controls": {
            "confirmed": True,
            "record_sha256": (
                definition.use_attestation.retention_controls_record_sha256
            ),
        },
        "permitted_use": {
            "evaluator_development": True,
            "record_sha256": definition.use_attestation.permitted_use_record_sha256,
        },
    }
    assert manifest.payload["evidence_boundary"] == {
        "evaluator_development_use_only": True,
        "production_origin_attested_not_independently_verified": True,
        "legal_compliance_determined": False,
        "privacy_compliance_determined": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


@pytest.mark.parametrize(
    "field",
    (
        "production_data_use_authorized",
        "deidentification_completed",
        "retention_controls_confirmed",
        "evaluator_development_use_permitted",
    ),
)
def test_use_attestation_fails_closed_when_any_attestation_is_false(field):
    with pytest.raises(HveeContractError, match="explicitly attested true"):
        _use_attestation(**{field: False})


@pytest.mark.parametrize(
    "field",
    (
        "authorization_record_sha256",
        "deidentification_record_sha256",
        "retention_controls_record_sha256",
        "permitted_use_record_sha256",
    ),
)
def test_use_attestation_requires_every_supporting_record_hash(field):
    with pytest.raises(HveeContractError, match="lowercase SHA-256"):
        _use_attestation(**{field: "missing"})


def test_production_definition_rejects_invalid_or_future_temporal_evidence():
    _, _, _, exclusion = _exclusion()

    with pytest.raises(HveeContractError, match="canonical UTC timestamp"):
        _production_definition(
            exclusion.sha256,
            snapshot_at_utc="2026-08-01T00:00:00+00:00",
        )
    with pytest.raises(HveeContractError, match="start must not follow"):
        _production_definition(
            exclusion.sha256,
            source_window_started_at_utc="2026-07-31T23:59:59Z",
            source_window_ended_at_utc="2026-07-01T00:00:00Z",
        )
    with pytest.raises(HveeContractError, match="past the snapshot"):
        _production_definition(
            exclusion.sha256,
            source_window_ended_at_utc="2026-08-02T00:00:00Z",
        )
    with pytest.raises(HveeContractError, match="must not postdate"):
        _production_definition(
            exclusion.sha256,
            use_attestation=_use_attestation(
                attested_at_utc="2026-08-02T00:00:00Z"
            ),
        )
    with pytest.raises(HveeContractError, match="within the source window"):
        _production_definition(
            exclusion.sha256,
            cases=(_production_case("late", "2026-08-01T00:00:00Z"),),
        )


@pytest.mark.parametrize(
    ("field", "match"),
    (
        ("case_id", "case ids must be unique"),
        (
            "deidentified_payload_sha256",
            "de-identified payload commitments must be unique",
        ),
        ("source_record_sha256", "source-record commitments must be unique"),
        ("lineage_sha256", "lineage commitments must be unique"),
        ("cross_set_linkage_token", "cross-set linkage tokens must be unique"),
    ),
)
def test_production_definition_rejects_duplicate_case_evidence(field, match):
    _, _, _, exclusion = _exclusion()
    first = _production_case("one", "2026-07-10T12:00:00Z")
    second = _production_case("two", "2026-07-20T12:00:00Z")
    duplicate = replace(second, **{field: getattr(first, field)})
    cases = tuple(sorted((first, duplicate), key=lambda case: case.case_id))

    with pytest.raises(HveeContractError, match=match):
        _production_definition(exclusion.sha256, cases=cases)


def test_production_definition_requires_deterministic_case_order():
    _, _, _, exclusion = _exclusion()
    cases = (
        _production_case("two", "2026-07-20T12:00:00Z"),
        _production_case("one", "2026-07-10T12:00:00Z"),
    )

    with pytest.raises(HveeContractError, match="ordered by case id"):
        _production_definition(exclusion.sha256, cases=cases)


def test_production_manifest_rejects_private_holdout_overlap():
    _, _, private_tokens, exclusion = _exclusion()
    overlapping = _production_case(
        "overlap",
        "2026-07-15T12:00:00Z",
        cross_set_linkage_token=private_tokens[0],
    )
    definition = _production_definition(exclusion.sha256, cases=(overlapping,))

    with pytest.raises(HveeContractError, match="overlaps the private holdout"):
        build_critical_number_production_evidence_manifest(
            definition=definition,
            private_holdout_exclusion=exclusion,
        )


def test_production_manifest_requires_exact_exclusion_manifest_binding():
    _, _, _, exclusion = _exclusion()
    definition = _production_definition(_digest("different-exclusion"))

    with pytest.raises(HveeContractError, match="does not bind"):
        build_critical_number_production_evidence_manifest(
            definition=definition,
            private_holdout_exclusion=exclusion,
        )


def test_production_manifest_rejects_mutated_exclusion_boundary():
    _, _, _, exclusion = _exclusion()
    tampered_payload = copy.deepcopy(exclusion.payload)
    tampered_payload["evidence_boundary"]["production_qualified"] = True
    tampered = ASRCriticalNumberPrivateHoldoutExclusionManifestBundle(
        payload=tampered_payload,
        sha256=calculate_critical_number_production_evidence_sha256(
            tampered_payload
        ),
    )
    definition = _production_definition(tampered.sha256)

    with pytest.raises(HveeContractError, match="evidence boundary changed"):
        build_critical_number_production_evidence_manifest(
            definition=definition,
            private_holdout_exclusion=tampered,
        )


def test_production_verifier_rejects_tampering_with_recomputed_digest():
    exclusion, definition, manifest = _manifest()
    tampered = copy.deepcopy(manifest.payload)
    tampered["evidence_boundary"]["release_enforcement_eligible"] = True
    tampered_sha256 = calculate_critical_number_production_evidence_sha256(tampered)

    with pytest.raises(HveeContractError, match="does not match its definition"):
        verify_critical_number_production_evidence_manifest(
            payload=tampered,
            expected_sha256=tampered_sha256,
            definition=definition,
            private_holdout_exclusion=exclusion,
        )


def test_manifest_bundles_reject_payload_digest_mismatch():
    _, _, _, exclusion = _exclusion()
    with pytest.raises(HveeContractError, match="does not match its payload"):
        ASRCriticalNumberPrivateHoldoutExclusionManifestBundle(
            payload=exclusion.payload,
            sha256="0" * 64,
        )

    _, _, manifest = _manifest()
    with pytest.raises(HveeContractError, match="does not match its payload"):
        ASRCriticalNumberProductionEvidenceManifestBundle(
            payload=manifest.payload,
            sha256="0" * 64,
        )


def test_production_manifest_contains_no_raw_evidence_or_hmac_secret():
    _, definition, manifest = _manifest()
    serialized = repr(manifest.payload)

    assert "raw production transcript" not in serialized
    assert "customer@example.com" not in serialized
    assert _LINKAGE_KEY.decode("utf-8") not in serialized
    for case in definition.cases:
        assert case.case_id in serialized
        assert case.deidentified_payload_sha256 in serialized
    assert manifest.payload["confidentiality"] == {
        "raw_audio_in_artifact": False,
        "raw_transcripts_in_artifact": False,
        "pii_in_artifact": False,
        "hmac_keys_in_artifact": False,
        "linkage_salts_in_artifact": False,
        "opaque_identifiers_and_commitments_only": True,
    }


def test_same_version_evaluator_identity_change_fails_closed(monkeypatch):
    monkeypatch.setattr(
        production_module,
        "CRITICAL_NUMBER_FIDELITY_EVALUATOR",
        replace(CRITICAL_NUMBER_FIDELITY_EVALUATOR, version="1.0.1"),
    )
    plan_definition, plan = _private_plan()

    with pytest.raises(HveeContractError, match="evaluator identity changed"):
        build_critical_number_private_holdout_exclusion_manifest(
            plan=plan,
            plan_definition=plan_definition,
            linkage_tokens=_private_tokens(),
        )


def test_production_evidence_api_is_exported_from_asr_pack():
    exported = {
        "ASRCriticalNumberPrivateHoldoutExclusionManifestBundle",
        "ASRCriticalNumberProductionCaseCommitment",
        "ASRCriticalNumberProductionEvidenceDefinition",
        "ASRCriticalNumberProductionEvidenceManifestBundle",
        "ASRCriticalNumberProductionUseAttestation",
        "CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_KEY",
        "CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_VERSION",
        "CRITICAL_NUMBER_PRODUCTION_EVIDENCE_SCHEMA_VERSION",
        "CRITICAL_NUMBER_PRODUCTION_EXCLUSION_SCHEMA_VERSION",
        "CRITICAL_NUMBER_PRODUCTION_LINKAGE_SCHEME",
        "build_critical_number_private_holdout_exclusion_manifest",
        "build_critical_number_production_evidence_manifest",
        "calculate_critical_number_production_evidence_sha256",
        "verify_critical_number_private_holdout_exclusion_manifest",
        "verify_critical_number_production_evidence_manifest",
    }

    assert exported.issubset(set(asr.__all__))
    assert all(hasattr(asr, name) for name in exported)
