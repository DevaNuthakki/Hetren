from __future__ import annotations

import inspect
from collections import Counter

import pytest

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
)
import packages.engines.behavioral.p09_4_protected_generation as generation
from packages.engines.behavioral.p09_4_protected_generation import (
    HIDDEN_STRATA,
    TEMPLATE_IDS,
    build_development_generation_plan,
)


PROTOCOL_SHA = (
    "46ea27e825bedbfbd8ee0443173884f904f20881fc929a4c44fae30c550e7621"
)

SOURCE_COMMIT = (
    "08aa58c6dba26f2ff7f88b82f5d7448fc84d29f9"
)

SEED_A = bytes(
    range(
        32
    )
)

SEED_B = bytes(
    reversed(
        range(
            32
        )
    )
)


def _plan(
    seed=SEED_A,
):
    return build_development_generation_plan(
        raw_seed=seed,
        protocol_sha256=PROTOCOL_SHA,
        source_commit=SOURCE_COMMIT,
    )


def test_public_slot_shape_is_exactly_144_and_36_per_template():
    plan = _plan()

    assert len(
        plan.public_slots
    ) == 144

    assert Counter(
        slot.template_id
        for slot
        in plan.public_slots
    ) == {
        "V1": 36,
        "V2": 36,
        "V3": 36,
        "V4": 36,
    }


def test_public_case_ids_follow_frozen_contract_and_do_not_encode_truth():
    plan = _plan()

    case_ids = tuple(
        slot.case_id
        for slot
        in plan.public_slots
    )

    assert len(
        case_ids
    ) == len(
        set(
            case_ids
        )
    ) == 144

    assert case_ids == tuple(
        sorted(
            case_ids
        )
    )

    forbidden = (
        "tool_selection",
        "parameter_transformation",
        "sequencing_orchestration",
        "state_context",
        "environment_interaction",
        "out_of_rfs",
        "_fault",
    )

    assert all(
        all(
            marker
            not in case_id
            for marker
            in forbidden
        )
        for case_id
        in case_ids
    )


def test_all_public_nuisance_configuration_fingerprints_are_unique():
    plan = _plan()

    fingerprints = tuple(
        slot.public_configuration_sha256
        for slot
        in plan.public_slots
    )

    assert len(
        fingerprints
    ) == 144

    assert len(
        set(
            fingerprints
        )
    ) == 144


def test_public_slot_construction_is_raw_seed_independent():
    first = _plan(
        SEED_A
    )

    second = _plan(
        SEED_B
    )

    assert (
        first.public_slots
        == second.public_slots
    )

    assert (
        first.public_plan_sha256
        == second.public_plan_sha256
    )


def test_hidden_population_is_balanced_24_per_stratum():
    plan = _plan()

    assert Counter(
        assignment.hidden_stratum
        for assignment
        in plan.hidden_assignments
    ) == {
        hidden_stratum:
            24
        for hidden_stratum
        in HIDDEN_STRATA
    }


def test_each_template_hidden_stratum_cell_contains_exactly_six_cases():
    plan = _plan()

    counts = Counter(
        (
            assignment.template_id,
            assignment.hidden_stratum,
        )
        for assignment
        in plan.hidden_assignments
    )

    assert counts == {
        (
            template_id,
            hidden_stratum,
        ):
            6
        for template_id
        in TEMPLATE_IDS
        for hidden_stratum
        in HIDDEN_STRATA
    }


def test_hidden_assignment_changes_with_seed_without_changing_public_slots():
    first = _plan(
        SEED_A
    )

    second = _plan(
        SEED_B
    )

    assert (
        first.public_slots
        == second.public_slots
    )

    assert (
        first.hidden_assignments
        != second.hidden_assignments
    )

    assert (
        first.seed_commitment.seed_sha256
        != second.seed_commitment.seed_sha256
    )


def test_same_inputs_are_exactly_reproducible():
    first = _plan()
    second = _plan()

    assert first == second

    assert (
        first.public_plan_sha256
        == second.public_plan_sha256
    )

    assert (
        first.hidden_assignment_sha256
        == second.hidden_assignment_sha256
    )


def test_seed_contract_requires_exactly_32_bytes_and_binds_commitment():
    plan = _plan()

    import hashlib

    assert (
        plan.seed_commitment.seed_sha256
        == hashlib.sha256(
            SEED_A
        ).hexdigest()
    )

    with pytest.raises(
        ContractError
    ):
        build_development_generation_plan(
            raw_seed=b"short",
            protocol_sha256=PROTOCOL_SHA,
            source_commit=SOURCE_COMMIT,
        )


def test_generation_plan_source_creates_no_randomness_files_or_treatment():
    source = inspect.getsource(
        generation
    )

    for forbidden in (
        "os.urandom",
        "secrets.",
        "Path(",
        "open(",
        "write_text",
        "write_bytes",
        "run_scientific_arm",
        "capture_p09_4_replay_baseline",
        "capture_p09_4_out_of_rfs_replay_baseline",
    ):
        assert forbidden not in source
