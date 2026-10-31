"""Portable synthetic report serialization and adversarial validation."""

import hashlib
import json

import pytest

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.engines.behavioral.model_incident_control_suite_development import (
    CONTROL_CASES,
    control_manifest_sha256,
    run_synthetic_control_suite,
)
from packages.engines.behavioral.model_incident_portable_report_development import (
    serialize_portable_development_report,
    verify_portable_development_report,
)


def encode(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def repack(payload):
    return encode({
        "payload": payload,
        "payload_sha256": canonical_sha256(payload),
    })


@pytest.fixture(scope="module")
def suite_result():
    return run_synthetic_control_suite()


@pytest.fixture(scope="module")
def raw_report(suite_result):
    return serialize_portable_development_report(suite_result)


def test_eight_case_portable_round_trip(raw_report, suite_result):
    verified = verify_portable_development_report(raw_report)

    assert verified.case_count == 8
    assert verified.correct_count == 2
    assert verified.record_kind == "synthetic_development"
    assert verified.manifest_sha256 == control_manifest_sha256()
    assert verified.evaluation_sha256 == suite_result.report.report_sha256
    assert verified.suite_sha256 == suite_result.evidence_sha256
    assert verified.document_sha256 == hashlib.sha256(raw_report).hexdigest()


def test_manifest_version_and_report_id_are_distinct(raw_report):
    payload = json.loads(raw_report)["payload"]

    assert payload["manifest"]["version"] == "a5-10h-cc-development-v1"
    assert payload["report"]["report_id"] == "a510h-cc-development-v1"
    assert payload["manifest"]["version"] != payload["report"]["report_id"]


def test_fully_rehashed_wrong_report_id_is_rejected(raw_report):
    payload = json.loads(raw_report)["payload"]

    payload["report"]["report_id"] = payload["manifest"]["version"]

    payload["report_sha256"] = canonical_sha256(payload["report"])

    payload["suite_evidence_sha256"] = canonical_sha256({
        "record_type": "SyntheticIncidentControlSuiteResult",
        "schema_version": 1,
        "development_only": True,
        "manifest_sha256": payload["manifest_sha256"],
        "report_sha256": payload["report_sha256"],
    })

    rewritten = repack(payload)

    with pytest.raises(
        ContractError,
        match="embedded evaluation report is inconsistent",
    ):
        verify_portable_development_report(rewritten)


def test_canonical_encoding_and_payload_digest(raw_report):
    envelope = json.loads(raw_report)

    assert encode(envelope) == raw_report
    assert envelope["payload_sha256"] == canonical_sha256(
        envelope["payload"]
    )

    assert envelope["payload"]["dataset_kind"] == "synthetic_development"
    assert envelope["payload"]["development_only"] is True


def test_ordered_manifest_and_evidence_references(raw_report):
    payload = json.loads(raw_report)["payload"]

    assert payload["manifest_sha256"] == control_manifest_sha256()

    assert [
        record["score"]["case_id"]
        for record in payload["case_records"]
    ] == [
        definition.case_id for definition in CONTROL_CASES
    ]

    assert len(payload["case_records"]) == 8

    for record in payload["case_records"]:
        score = record["score"]

        assert record["case_evidence_sha256"] == canonical_sha256(score)
        assert len(score["observed_sha256"]) == 64
        assert len(score["timeline_sha256"]) == 64


def test_same_evidence_serializes_identically(raw_report, suite_result):
    again = serialize_portable_development_report(suite_result)

    assert again == raw_report
    assert hashlib.sha256(again).hexdigest() == (
        hashlib.sha256(raw_report).hexdigest()
    )


def test_trusted_document_digest_accepts_exact_bytes(raw_report):
    trusted_sha = hashlib.sha256(raw_report).hexdigest()

    result = verify_portable_development_report(
        raw_report,
        expected_document_sha256=trusted_sha,
    )

    assert result.document_sha256 == trusted_sha


def test_mismatched_trusted_digest_rejected(raw_report):
    with pytest.raises(ContractError, match="trusted document"):
        verify_portable_development_report(
            raw_report,
            expected_document_sha256="0" * 64,
        )


@pytest.mark.parametrize(
    "value",
    ["invalid", b"", bytearray(b"{}"), None, b"x" * 262145],
)
def test_invalid_input_types_and_sizes_rejected(value):
    with pytest.raises(ContractError):
        verify_portable_development_report(value)


@pytest.mark.parametrize(
    "value",
    [
        b"not-json",
        b'{"payload":NaN,"payload_sha256":"invalid"}',
        b"\xff",
        b"[]",
        b"null",
    ],
)
def test_malformed_json_and_invalid_documents_rejected(value):
    with pytest.raises(ContractError):
        verify_portable_development_report(value)


def test_extra_whitespace_not_canonical(raw_report):
    with pytest.raises(ContractError, match="noncanonical"):
        verify_portable_development_report(raw_report + b"\n")


def test_nonfinite_json_preserves_specific_rejection():
    with pytest.raises(
        ContractError,
        match="nonfinite JSON number",
    ):
        verify_portable_development_report(
            b'{"payload":NaN,"payload_sha256":"invalid"}'
        )


def test_nested_duplicate_property_preserves_specific_rejection(raw_report):
    original = b'"schema_version":1'
    duplicate = b'"schema_version":1,"schema_version":1'

    assert original in raw_report

    modified = raw_report.replace(original, duplicate, 1)

    with pytest.raises(
        ContractError,
        match="duplicate JSON property",
    ):
        verify_portable_development_report(modified)


def test_duplicate_json_keys_rejected(raw_report):
    assert raw_report.startswith(b'{"payload":')

    modified = raw_report.replace(
        b'{"payload":',
        b'{"payload":null,"payload":',
        1,
    )

    with pytest.raises(ContractError, match="duplicate JSON property"):
        verify_portable_development_report(modified)


def test_single_byte_modification_rejected(raw_report):
    modified = raw_report.replace(
        b"synthetic_development",
        b"synthetic_developmenx",
        1,
    )

    assert modified != raw_report

    with pytest.raises(ContractError):
        verify_portable_development_report(modified)


def test_missing_required_payload_field_rejected(raw_report):
    payload = json.loads(raw_report)["payload"]

    del payload["summary"]

    with pytest.raises(ContractError):
        verify_portable_development_report(repack(payload))


def test_unknown_payload_field_rejected(raw_report):
    payload = json.loads(raw_report)["payload"]

    payload["unrecognized"] = True

    with pytest.raises(ContractError):
        verify_portable_development_report(repack(payload))


def test_case_reordering_rejected_even_after_envelope_rehash(raw_report):
    payload = json.loads(raw_report)["payload"]

    payload["case_records"].reverse()

    with pytest.raises(ContractError):
        verify_portable_development_report(repack(payload))


def test_manifest_change_rejected_even_after_envelope_rehash(raw_report):
    payload = json.loads(raw_report)["payload"]

    payload["manifest"]["cases"][0]["behavior"] = "fabricated"

    with pytest.raises(ContractError, match="manifest"):
        verify_portable_development_report(repack(payload))


def test_corrupted_case_hash_rejected(raw_report):
    payload = json.loads(raw_report)["payload"]

    payload["case_records"][0]["case_evidence_sha256"] = "0" * 64

    with pytest.raises(ContractError):
        verify_portable_development_report(repack(payload))


def test_falsified_correctness_rejected(raw_report):
    payload = json.loads(raw_report)["payload"]

    payload["case_records"][0]["score"]["correct"] = False

    with pytest.raises(ContractError):
        verify_portable_development_report(repack(payload))


def test_falsified_aggregate_rejected(raw_report):
    payload = json.loads(raw_report)["payload"]

    payload["summary"]["correct_cases"] = 8

    with pytest.raises(ContractError):
        verify_portable_development_report(repack(payload))


def test_fabricated_offline_provider_tokens_rejected(raw_report):
    payload = json.loads(raw_report)["payload"]

    score = payload["case_records"][0]["score"]
    score["known_call_token_sum"] = 20
    score["complete_reported_tokens"] = 20
    score["calls_with_reported_tokens"] = 4
    score["calls_without_reported_tokens"] = 0

    with pytest.raises(ContractError):
        verify_portable_development_report(repack(payload))


def test_report_hash_inconsistency_rejected(raw_report):
    payload = json.loads(raw_report)["payload"]

    payload["report_sha256"] = "0" * 64

    with pytest.raises(ContractError):
        verify_portable_development_report(repack(payload))


def test_invalid_trusted_digest_format_rejected(raw_report):
    with pytest.raises(ContractError):
        verify_portable_development_report(
            raw_report,
            expected_document_sha256="not-a-sha256",
        )


def test_fully_rehashed_report_requires_external_trust(raw_report):
    """Internal rehashing is not authentication or independent verification."""

    payload = json.loads(raw_report)["payload"]

    record = payload["case_records"][0]
    score = record["score"]

    score["local_capture_elapsed_ns"] += 1
    payload["summary"]["local_capture_elapsed_ns"] += 1

    changed_case_sha = canonical_sha256(score)
    record["case_evidence_sha256"] = changed_case_sha

    embedded = payload["report"]
    embedded["case_evidence_hashes"][0] = changed_case_sha
    embedded["summary"]["local_capture_elapsed_ns"] += 1

    payload["report_sha256"] = canonical_sha256(embedded)

    payload["suite_evidence_sha256"] = canonical_sha256({
        "record_type": "SyntheticIncidentControlSuiteResult",
        "schema_version": 1,
        "development_only": True,
        "manifest_sha256": payload["manifest_sha256"],
        "report_sha256": payload["report_sha256"],
    })

    rewritten = repack(payload)

    assert rewritten != raw_report

    # It is structurally self-consistent, but not authenticated.
    unanchored = verify_portable_development_report(rewritten)
    assert unanchored.case_count == 8

    original_trusted_digest = hashlib.sha256(raw_report).hexdigest()

    with pytest.raises(ContractError, match="trusted document"):
        verify_portable_development_report(
            rewritten,
            expected_document_sha256=original_trusted_digest,
        )


def test_verifier_limitations_are_explicit(raw_report):
    verified = verify_portable_development_report(raw_report)

    text = " ".join(verified.limitations).lower()

    assert "integrity" in text
    assert "raw model captures" in text
    assert "rehashed forgery" in text
    assert "not a live provider" in text
