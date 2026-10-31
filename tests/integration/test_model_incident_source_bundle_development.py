"""Adversarial tests for portable synthetic source-evidence verification.

All bundles and portable reports are generated in memory from offline controls.
No test writes into the actual Hetren artifacts directory.
"""
from dataclasses import replace
import hashlib
import json

import pytest

from packages.contracts import ContractError

from packages.engines.behavioral import (
    model_incident_control_suite_development as control_suite,
)

from packages.engines.behavioral import (
    model_incident_source_bundle_development as source,
)

from packages.engines.behavioral.model_incident_portable_report_development import (
    serialize_portable_development_report,
)


def canonical(document):
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@pytest.fixture(scope="module")
def good():
    suite = control_suite.run_synthetic_control_suite()
    portable = serialize_portable_development_report(suite)
    bundle = source.serialize_synthetic_source_bundle(suite, portable)
    return suite, portable, bundle


def altered(good, modify):
    document = json.loads(good[2])
    modify(document)
    return canonical(document)


def reject(good, bundle):
    with pytest.raises(ContractError):
        source.verify_synthetic_source_bundle(bundle, good[1])


def first_case(document):
    return document["source_records"]["items"][0]["fields"]


def first_attempt(document):
    return (
        first_case(document)["observed"]["fields"]
        ["run"]["fields"]["attempts"]["items"][0]["fields"]
    )


def first_call(document):
    return (
        first_case(document)["observed"]["fields"]
        ["calls"]["items"][0]["fields"]
    )


def first_state(document):
    return (
        first_case(document)["observed"]["fields"]
        ["run"]["fields"]["state"]["fields"]
    )


def first_event_kind(document):
    return (
        first_state(document)["steps"]["items"][0]
        ["fields"]["event"]["fields"]["kind"]
    )


def test_valid_bundle_recomputes_evaluation(good):
    suite, portable, bundle = good

    result = source.verify_synthetic_source_bundle(
        bundle,
        portable,
        expected_bundle_sha256=hashlib.sha256(bundle).hexdigest(),
        expected_report_sha256=hashlib.sha256(portable).hexdigest(),
    )

    assert result.case_count == 8
    assert result.correct_count == 2
    assert result.evaluation_sha256 == suite.report.report_sha256
    assert result.suite_evidence_sha256 == suite.evidence_sha256
    assert result.provider_authenticated is False


def test_serialization_is_deterministic_for_same_execution(good):
    suite, portable, bundle = good

    assert (
        source.serialize_synthetic_source_bundle(suite, portable)
        == bundle
    )


def test_verify_does_not_rerun_control_suite(good, monkeypatch):
    def forbidden():
        raise AssertionError("Verifier must not execute controls")

    monkeypatch.setattr(
        control_suite,
        "run_synthetic_control_suite",
        forbidden,
    )

    assert source.verify_synthetic_source_bundle(
        good[2],
        good[1],
    ).case_count == 8


@pytest.mark.parametrize(
    "trusted",
    ["0" * 64, "invalid", "A" * 64, ""],
)
def test_wrong_or_invalid_bundle_anchor_rejected(good, trusted):
    with pytest.raises(ContractError):
        source.verify_synthetic_source_bundle(
            good[2],
            good[1],
            expected_bundle_sha256=trusted,
        )


@pytest.mark.parametrize(
    "trusted",
    ["0" * 64, "invalid", "A" * 64, ""],
)
def test_wrong_or_invalid_report_anchor_rejected(good, trusted):
    with pytest.raises(ContractError):
        source.verify_synthetic_source_bundle(
            good[2],
            good[1],
            expected_report_sha256=trusted,
        )


@pytest.mark.parametrize("raw", [
    b"",
    b"{}",
    b"null",
    b"[]",
    b"42",
    b'{"x":NaN}',
    b'{"x":Infinity}',
    b'{"x":1,"x":2}',
    b"\xff\xfe",
    b"{invalid",
])
def test_malformed_untrusted_document_rejected(good, raw):
    reject(good, raw)


@pytest.mark.parametrize("extra", [
    b" ",
    b"\n",
    b"\t",
])
def test_noncanonical_whitespace_rejected(good, extra):
    reject(good, good[2] + extra)
    reject(good, extra + good[2])


def test_overlarge_document_rejected_before_parsing(good):
    reject(
        good,
        b"X" * (source.MAX_BUNDLE_BYTES + 1),
    )


@pytest.mark.parametrize(("field", "value"), [
    ("record_type", "UntrustedBundle"),
    ("schema_version", 2),
    ("schema_version", True),
    ("development_only", False),
    ("development_only", 1),
    ("manifest_sha256", "0" * 64),
    ("evaluation_sha256", "0" * 64),
    ("suite_evidence_sha256", "0" * 64),
    ("report_document_sha256", "0" * 64),
    ("report_document_sha256", "invalid"),
])
def test_forged_envelope_metadata_rejected(good, field, value):
    reject(
        good,
        altered(
            good,
            lambda data: data.__setitem__(field, value),
        ),
    )


@pytest.mark.parametrize("field", [
    "record_type",
    "schema_version",
    "development_only",
    "source_records",
    "report_document_sha256",
])
def test_missing_envelope_field_rejected(good, field):
    reject(
        good,
        altered(
            good,
            lambda data: data.pop(field),
        ),
    )


def test_extra_envelope_field_rejected(good):
    reject(
        good,
        altered(
            good,
            lambda data: data.__setitem__(
                "provider_authenticated",
                True,
            ),
        ),
    )


def test_duplicate_json_key_rejected(good):
    tampered = good[2].replace(
        b'"record_type":',
        b'"record_type":"forged","record_type":',
        1,
    )

    assert tampered != good[2]
    reject(good, tampered)


def test_forged_case_identity_rejected(good):
    def change(data):
        first_case(data)["case_id"] = "forged"

    reject(good, altered(good, change))


def test_changed_root_record_kind_rejected(good):
    def change(data):
        data["source_records"]["$kind"] = "list"

    reject(good, altered(good, change))


def test_missing_source_dataclass_field_rejected(good):
    def change(data):
        first_case(data).pop("scenario")

    reject(good, altered(good, change))


def test_extra_source_dataclass_field_rejected(good):
    def change(data):
        first_case(data)["injected"] = "not allowed"

    reject(good, altered(good, change))


@pytest.mark.parametrize("identity", [
    "os.system",
    "subprocess.Popen",
    "packages.fake.EvilClass",
])
def test_unallowlisted_dataclass_identity_rejected(good, identity):
    def change(data):
        data["source_records"]["items"][0]["class"] = identity

    reject(good, altered(good, change))


def test_unallowlisted_enum_identity_rejected(good):
    def change(data):
        first_event_kind(data)["class"] = "os.system"

    reject(good, altered(good, change))


def test_invalid_enum_value_rejected(good):
    def change(data):
        first_event_kind(data)["value"] = "not_a_valid_event_kind"

    reject(good, altered(good, change))


def test_modified_attempt_binding_rejected(good):
    def change(data):
        first_attempt(data)["request_sha256"] = "0" * 64

    reject(good, altered(good, change))


def test_modified_capture_order_rejected(good):
    def change(data):
        first_call(data)["number"] = 99

    reject(good, altered(good, change))


def test_modified_capture_origin_rejected(good):
    def change(data):
        first_call(data)["origin"] = "forged_provider"

    reject(good, altered(good, change))


def test_modified_workflow_state_rejected(good):
    def change(data):
        first_state(data)["phase"] = "forged_phase"

    reject(good, altered(good, change))


def test_modified_attempt_action_rejected(good):
    def change(data):
        first_attempt(data)["executed"] = False

    reject(good, altered(good, change))


def test_source_records_as_untrusted_scalar_rejected(good):
    reject(
        good,
        altered(
            good,
            lambda data: data.__setitem__(
                "source_records",
                True,
            ),
        ),
    )


def test_unsupported_tagged_node_rejected(good):
    def change(data):
        data["source_records"]["$kind"] = "execute_code"

    reject(good, altered(good, change))


def test_deeply_nested_source_evidence_rejected(good):
    node = None

    for _ in range(source.MAX_DEPTH + 3):
        node = {
            "$kind": "tuple",
            "items": [node],
        }

    reject(
        good,
        altered(
            good,
            lambda data: data.__setitem__(
                "source_records",
                node,
            ),
        ),
    )


def test_excessive_source_node_budget_rejected(good):
    node = {
        "$kind": "tuple",
        "items": [None] * (source.MAX_NODES + 1),
    }

    reject(
        good,
        altered(
            good,
            lambda data: data.__setitem__(
                "source_records",
                node,
            ),
        ),
    )


def test_noncanonical_bytes_record_rejected(good):
    node = {
        "$kind": "bytes",
        "hex": "0X",
    }

    reject(
        good,
        altered(
            good,
            lambda data: data.__setitem__(
                "source_records",
                node,
            ),
        ),
    )


def test_duplicate_mapping_key_rejected(good):
    node = {
        "$kind": "dict",
        "pairs": [
            ["duplicate", 1],
            ["duplicate", 2],
        ],
    }

    reject(
        good,
        altered(
            good,
            lambda data: data.__setitem__(
                "source_records",
                node,
            ),
        ),
    )


def test_invalid_mapping_key_rejected(good):
    node = {
        "$kind": "dict",
        "pairs": [
            [
                {
                    "$kind": "list",
                    "items": ["unhashable"],
                },
                1,
            ],
        ],
    }

    reject(
        good,
        altered(
            good,
            lambda data: data.__setitem__(
                "source_records",
                node,
            ),
        ),
    )


def test_serializer_rejects_wrong_suite_manifest(good):
    changed = replace(
        good[0],
        manifest_sha256="0" * 64,
    )

    with pytest.raises(ContractError):
        source.serialize_synthetic_source_bundle(
            changed,
            good[1],
        )


def test_serializer_rejects_wrong_report(good):
    with pytest.raises(ContractError):
        source.serialize_synthetic_source_bundle(
            good[0],
            good[1] + b"\n",
        )


def test_encoder_rejects_unallowlisted_objects():
    with pytest.raises(ContractError):
        source._encode(object(), set(), [0])


def test_encoder_rejects_cyclic_objects():
    cyclic = []
    cyclic.append(cyclic)

    with pytest.raises(ContractError):
        source._encode(cyclic, set(), [0])


def test_bundle_contains_only_synthetic_development_provenance(good):
    document = json.loads(good[2])

    assert document["record_type"] == source.RECORD_TYPE
    assert document["schema_version"] == 1
    assert document["development_only"] is True

    assert "provider_authenticated" not in document
    assert "source_records" in document
    assert "report_document_sha256" in document

    assert document["report_document_sha256"] == hashlib.sha256(
        good[1]
    ).hexdigest()


def test_valid_different_execution_cannot_be_substituted(good):
    second = control_suite.run_synthetic_control_suite()

    different_report = serialize_portable_development_report(
        second
    )

    if different_report == good[1]:
        pytest.skip(
            "Local timing produced identical report bytes"
        )

    with pytest.raises(ContractError):
        source.verify_synthetic_source_bundle(
            good[2],
            different_report,
        )
