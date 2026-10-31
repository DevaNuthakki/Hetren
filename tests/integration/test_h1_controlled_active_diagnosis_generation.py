from collections import Counter
import inspect
import json

import pytest

from environments.agent.h1_controlled_active_diagnosis import (
    build_public_case,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis_generation import (
    build_h1_batch_manifests,
)


PROTOCOL_SHA = (
    "6b738092e28036ea400f6498a4ad1663"
    "dd8cbb1e1c9c1e54e48ff4030ceb6ef8"
)

HARNESS_COMMIT_ID = (
    "ccc65a6a7e3e1745e0ceda3968287507a2de81d2"
)

BATCH_ID = "development-isolation-check-v1"

SEED_A = bytes.fromhex(
    "00" * 32
)

SEED_B = bytes.fromhex(
    "11" * 32
)


def build(
    seed=SEED_A,
    *,
    protocol_sha=PROTOCOL_SHA,
    harness_commit_id=HARNESS_COMMIT_ID,
):
    return build_h1_batch_manifests(
        raw_seed=seed,
        batch_id=BATCH_ID,
        protocol_sha256=protocol_sha,
        harness_commit_id=harness_commit_id,
    )


def assignments_by_template(
    generated,
):
    public_by_id = {
        case.case_id: case
        for case in generated.public_manifest.cases
    }

    result = {}

    for assignment in (
        generated.hidden_truth_manifest.assignments
    ):
        template_id = public_by_id[
            assignment.case_id
        ].template_id

        result.setdefault(
            template_id,
            [],
        ).append(
            assignment.hidden_fault_key
        )

    return result


def test_public_manifest_has_exact_96_case_shape():
    generated = build()

    cases = generated.public_manifest.cases

    assert len(
        cases
    ) == 96

    counts = Counter(
        case.template_id
        for case in cases
    )

    assert counts == Counter(
        {
            "T1": 20,
            "T2": 20,
            "T3": 20,
            "T4": 20,
            "N1": 4,
            "N2": 4,
            "N3": 4,
            "N4": 4,
        }
    )


def test_cost_sensitive_hidden_composition_is_exact():
    generated = build()

    assignments = assignments_by_template(
        generated
    )

    expected_dominant = {
        "T1": "H1",
        "T2": "H2",
        "T3": "H3",
        "T4": "H4",
    }

    for template_id, dominant in expected_dominant.items():
        counts = Counter(
            assignments[
                template_id
            ]
        )

        assert counts[
            dominant
        ] == 14

        for key in (
            "H1",
            "H2",
            "H3",
            "H4",
        ):
            if key == dominant:
                continue

            assert counts[
                key
            ] == 2


def test_neutral_hidden_composition_is_exact_cross_product():
    generated = build()

    assignments = assignments_by_template(
        generated
    )

    for template_id in (
        "N1",
        "N2",
        "N3",
        "N4",
    ):
        assert Counter(
            assignments[
                template_id
            ]
        ) == Counter(
            {
                "H1": 1,
                "H2": 1,
                "H3": 1,
                "H4": 1,
            }
        )


def test_full_hidden_population_is_balanced_24_each():
    generated = build()

    counts = Counter(
        record.hidden_fault_key
        for record
        in generated.hidden_truth_manifest.assignments
    )

    assert counts == Counter(
        {
            "H1": 24,
            "H2": 24,
            "H3": 24,
            "H4": 24,
        }
    )


def test_public_manifest_is_raw_seed_independent():
    first = build(
        SEED_A
    )

    second = build(
        SEED_B
    )

    assert (
        first.public_manifest.canonical_json_bytes
        == second.public_manifest.canonical_json_bytes
    )

    assert (
        first.public_manifest.manifest_sha256
        == second.public_manifest.manifest_sha256
    )


def test_hidden_manifest_changes_with_raw_seed():
    first = build(
        SEED_A
    )

    second = build(
        SEED_B
    )

    assert (
        first.seed_commitment.seed_sha256
        != second.seed_commitment.seed_sha256
    )

    assert (
        first.hidden_truth_manifest.manifest_sha256
        != second.hidden_truth_manifest.manifest_sha256
    )


def test_generation_is_exactly_reproducible_for_same_inputs():
    first = build(
        SEED_A
    )

    second = build(
        SEED_A
    )

    assert (
        first.public_manifest.canonical_json_bytes
        == second.public_manifest.canonical_json_bytes
    )

    assert (
        first.hidden_truth_manifest.canonical_json_bytes
        == second.hidden_truth_manifest.canonical_json_bytes
    )

    assert (
        first.seed_commitment.canonical_json_bytes
        == second.seed_commitment.canonical_json_bytes
    )


def test_public_manifest_contains_no_hidden_truth_or_seed_fields():
    generated = build()

    payload = json.dumps(
        generated.public_manifest.canonical_payload(),
        sort_keys=True,
    )

    forbidden = (
        "hidden_fault_key",
        "hidden_truth",
        "raw_seed",
        "seed_sha256",
        "seed_commitment",
        "oracle",
        "reference_diagnosis",
    )

    for marker in forbidden:
        assert marker not in payload


def test_case_ids_are_public_slots_and_do_not_encode_fault_labels():
    generated = build()

    case_ids = tuple(
        case.case_id
        for case in generated.public_manifest.cases
    )

    assert case_ids == tuple(
        sorted(
            case_ids
        )
    )

    assert len(
        case_ids
    ) == len(
        set(
            case_ids
        )
    )

    for case_id in case_ids:
        assert case_id.startswith(
            "h1-"
        )

        for fault_key in (
            "H1",
            "H2",
            "H3",
            "H4",
        ):
            assert (
                "-"
                + fault_key.lower()
                + "-"
            ) not in case_id


def test_seed_commitment_binds_raw_seed_without_storing_raw_seed():
    first = build(
        SEED_A
    )

    second = build(
        SEED_B
    )

    assert (
        first.seed_commitment.seed_sha256
        != second.seed_commitment.seed_sha256
    )

    payload = (
        first.seed_commitment.canonical_payload()
    )

    assert "seed_sha256" in payload
    assert "raw_seed" not in payload

    serialized = (
        first.seed_commitment.canonical_json_bytes
    )

    assert SEED_A not in serialized


def test_protocol_or_harness_identity_changes_hidden_manifest_digest():
    baseline = build()

    changed_protocol = build(
        protocol_sha=(
            "f" * 64
        )
    )

    changed_harness = build(
        harness_commit_id=(
            "e" * 40
        )
    )

    assert (
        baseline.hidden_truth_manifest.manifest_sha256
        != changed_protocol.hidden_truth_manifest.manifest_sha256
    )

    assert (
        baseline.hidden_truth_manifest.manifest_sha256
        != changed_harness.hidden_truth_manifest.manifest_sha256
    )


def test_generator_rejects_wrong_seed_size_invalid_sha_and_invalid_commit_id():
    with pytest.raises(
        ContractError,
        match="raw_seed must contain exactly 32 bytes",
    ):
        build_h1_batch_manifests(
            raw_seed=b"x" * 31,
            batch_id=BATCH_ID,
            protocol_sha256=PROTOCOL_SHA,
            harness_commit_id=HARNESS_COMMIT_ID,
        )

    with pytest.raises(
        ContractError,
        match="protocol_sha256 must be a lowercase SHA-256 digest",
    ):
        build_h1_batch_manifests(
            raw_seed=SEED_A,
            batch_id=BATCH_ID,
            protocol_sha256="not-a-sha",
            harness_commit_id=HARNESS_COMMIT_ID,
        )

    with pytest.raises(
        ContractError,
        match="harness_commit_id must be a lowercase 40-hex Git commit ID",
    ):
        build_h1_batch_manifests(
            raw_seed=SEED_A,
            batch_id=BATCH_ID,
            protocol_sha256=PROTOCOL_SHA,
            harness_commit_id="not-a-git-commit",
        )


def test_public_problem_hashes_reconstruct_exactly():
    generated = build()

    for record in generated.public_manifest.cases:
        rebuilt = build_public_case(
            case_id=record.case_id,
            template_id=record.template_id,
        )

        assert (
            rebuilt.singleton_target
            == record.singleton_target
        )

        assert (
            rebuilt.problem.problem_sha256
            == record.problem_sha256
        )


def test_generator_source_has_no_seed_creation_or_file_write():
    import packages.engines.behavioral.h1_controlled_active_diagnosis_generation as generation

    source = inspect.getsource(
        generation
    )

    for forbidden in (
        "secrets.token_bytes",
        "secrets.token_hex",
        "open(",
        "write_text(",
        "write_bytes(",
    ):
        assert forbidden not in source
