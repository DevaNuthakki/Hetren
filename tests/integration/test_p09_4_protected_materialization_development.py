from __future__ import annotations

from collections import defaultdict
import inspect

import pytest

import environments.agent.p09_4_multistep_incident as env

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
)
import packages.engines.behavioral.p09_4_protected_materialization as materialization
from packages.engines.behavioral.p09_4_checkpoint_replay import (
    capture_p09_4_out_of_rfs_replay_baseline,
    capture_p09_4_replay_baseline,
    execute_checkpoint_replay,
)
from packages.engines.behavioral.p09_4_protected_generation import (
    EXPECTED_HYPOTHESIS_BY_STRATUM,
    HIDDEN_STRATA,
    P094ProtectedHiddenAssignment,
    build_development_generation_plan,
)
from packages.engines.behavioral.p09_4_protected_materialization import (
    build_public_materialization_spec,
    materialize_protected_replay_baseline,
)
from packages.engines.behavioral.p09_4_scientific_arms import (
    CALIBRATED_REPLAY_COSTS,
    build_scientific_development_problem,
)


PROTOCOL_SHA = (
    "46ea27e825bedbfbd8ee0443173884f904f20881fc929a4c44fae30c550e7621"
)

SOURCE_COMMIT = (
    "50f663e01edf27bb2b6add5b72bc385cd1eb5d41"
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


FAULT_BY_STRATUM = {
    "tool_selection":
        env.P094FaultMode.TOOL_SELECTION,

    "parameter_transformation":
        env.P094FaultMode.PARAMETER_TRANSFORMATION,

    "sequencing_orchestration":
        env.P094FaultMode.SEQUENCING_ORCHESTRATION,

    "state_context":
        env.P094FaultMode.STATE_CONTEXT,

    "environment_interaction":
        env.P094FaultMode.ENVIRONMENT_INTERACTION,

    "out_of_rfs_report_assembly":
        env.P094FaultMode.NONE,
}


EXPECTED_PASSING_PROBE = {
    "tool_selection":
        "p1-canonical-tool",

    "parameter_transformation":
        "p2-canonical-parameter",

    "sequencing_orchestration":
        "p3-canonical-prerequisite-order",

    "state_context":
        "p4-fresh-context",

    "environment_interaction":
        "p5-environment-contract",

    "out_of_rfs_report_assembly":
        None,
}


EXPECTED_COSTS = {
    "p1-canonical-tool": 4,
    "p2-canonical-parameter": 4,
    "p3-canonical-prerequisite-order": 3,
    "p4-fresh-context": 3,
    "p5-environment-contract": 3,
}


def _plan(
    seed=SEED_A,
):
    return build_development_generation_plan(
        raw_seed=seed,
        protocol_sha256=PROTOCOL_SHA,
        source_commit=SOURCE_COMMIT,
    )


def _assignment(
    slot,
    hidden_stratum,
):
    return P094ProtectedHiddenAssignment(
        case_id=slot.case_id,
        template_id=slot.template_id,
        hidden_stratum=hidden_stratum,
        expected_hypothesis_key=(
            EXPECTED_HYPOTHESIS_BY_STRATUM[
                hidden_stratum
            ]
        ),
        public_configuration_sha256=(
            slot.public_configuration_sha256
        ),
    )


def _reference(
    *,
    case_id,
    hidden_stratum,
):
    if hidden_stratum == "out_of_rfs_report_assembly":
        return capture_p09_4_out_of_rfs_replay_baseline(
            run_id=case_id,
        )

    return capture_p09_4_replay_baseline(
        FAULT_BY_STRATUM[
            hidden_stratum
        ],
        run_id=case_id,
    )


def test_public_materialization_specs_are_seed_independent_and_metadata_bound():
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

    first_specs = tuple(
        build_public_materialization_spec(
            slot
        )
        for slot
        in first.public_slots
    )

    second_specs = tuple(
        build_public_materialization_spec(
            slot
        )
        for slot
        in second.public_slots
    )

    assert (
        first_specs
        == second_specs
    )

    assert len(
        first_specs
    ) == 144

    assert len(
        {
            spec.materialization_spec_sha256
            for spec
            in first_specs
        }
    ) == 144

    for (
        slot,
        spec,
    ) in zip(
        first.public_slots,
        first_specs,
    ):
        nuisance = dict(
            slot.nuisance_items
        )

        assert (
            spec.case_id
            == slot.case_id
        )

        assert (
            spec.public_configuration_sha256
            == slot.public_configuration_sha256
        )

        assert (
            nuisance[
                "replicate"
            ]
            == f"{slot.slot_index:03d}"
        )

        if slot.template_id == "V3":
            assert (
                dict(
                    spec.context_overlay_items
                )[
                    "benign_context_tag"
                ]
                == nuisance[
                    "benign_context_tag"
                ]
            )

        else:
            assert (
                spec.context_overlay_items
                == ()
            )


def test_v2_exposes_exactly_36_real_orders_without_reordering_targets():
    plan = _plan()

    canonical = (
        env._load_incidents()
    )

    canonical_targets = tuple(
        row
        for row
        in canonical
        if row[
            1
        ]
        == "payments-api"
    )

    canonical_scope = (
        env._scope_service(
            canonical
        )
    )

    specs = tuple(
        build_public_materialization_spec(
            slot
        )
        for slot
        in plan.public_slots
        if slot.template_id
        == "V2"
    )

    assert len(
        specs
    ) == 36

    assert len(
        {
            spec.incidents
            for spec
            in specs
        }
    ) == 36

    for spec in specs:
        targets = tuple(
            row
            for row
            in spec.incidents
            if row[
                1
            ]
            == "payments-api"
        )

        assert (
            targets
            == canonical_targets
        )

        assert (
            env._scope_service(
                spec.incidents
            )
            == canonical_scope
        )


def test_v3_exposes_exactly_36_public_context_values():
    plan = _plan()

    specs = tuple(
        (
            slot,
            build_public_materialization_spec(
                slot
            ),
        )
        for slot
        in plan.public_slots
        if slot.template_id
        == "V3"
    )

    assert len(
        specs
    ) == 36

    tags = set()

    for (
        slot,
        spec,
    ) in specs:
        nuisance = dict(
            slot.nuisance_items
        )

        overlay = dict(
            spec.context_overlay_items
        )

        assert (
            overlay[
                "benign_context_tag"
            ]
            == nuisance[
                "benign_context_tag"
            ]
        )

        tags.add(
            overlay[
                "benign_context_tag"
            ]
        )

    assert len(
        tags
    ) == 36


def test_v4_exposes_exactly_36_public_identifier_variants():
    plan = _plan()

    canonical = (
        env._load_incidents()
    )

    canonical_targets = tuple(
        row
        for row
        in canonical
        if row[
            1
        ]
        == "payments-api"
    )

    canonical_non_target = next(
        row
        for row
        in canonical
        if row[
            1
        ]
        != "payments-api"
    )

    canonical_scope = (
        env._scope_service(
            canonical
        )
    )

    specs = tuple(
        (
            slot,
            build_public_materialization_spec(
                slot
            ),
        )
        for slot
        in plan.public_slots
        if slot.template_id
        == "V4"
    )

    assert len(
        specs
    ) == 36

    identifiers = set()

    for (
        slot,
        spec,
    ) in specs:
        nuisance = dict(
            slot.nuisance_items
        )

        targets = tuple(
            row
            for row
            in spec.incidents
            if row[
                1
            ]
            == "payments-api"
        )

        assert (
            targets
            == canonical_targets
        )

        non_target = next(
            row
            for row
            in spec.incidents
            if row[
                1
            ]
            != "payments-api"
        )

        assert (
            non_target[
                0
            ]
            == nuisance[
                "identifier_variant"
            ]
        )

        assert (
            non_target[
                1:
            ]
            == canonical_non_target[
                1:
            ]
        )

        assert (
            env._scope_service(
                spec.incidents
            )
            == canonical_scope
        )

        identifiers.add(
            non_target[
                0
            ]
        )

    assert len(
        identifiers
    ) == 36


def test_materializer_rejects_public_hidden_binding_mismatch():
    plan = _plan()

    first = plan.public_slots[
        0
    ]

    second = plan.public_slots[
        1
    ]

    wrong = _assignment(
        second,
        "tool_selection",
    )

    with pytest.raises(
        ContractError
    ):
        materialize_protected_replay_baseline(
            public_slot=first,
            hidden_assignment=wrong,
        )


def test_all_864_possible_slot_stratum_materializations_are_valid():
    plan = _plan()

    cells = 0

    changed = defaultdict(
        int
    )

    for slot in plan.public_slots:
        for hidden_stratum in HIDDEN_STRATA:
            truth = _assignment(
                slot,
                hidden_stratum,
            )

            reference = _reference(
                case_id=slot.case_id,
                hidden_stratum=hidden_stratum,
            )

            baseline = (
                materialize_protected_replay_baseline(
                    public_slot=slot,
                    hidden_assignment=truth,
                )
            )

            cells += 1

            assert (
                baseline.run.run_id
                == slot.case_id
            )

            assert (
                baseline.run.passed
                is False
            )

            assert (
                baseline.run.report
                == reference.run.report
            )

            assert (
                baseline.checkpoint(
                    "pre-filter"
                ).service_rows
                == reference.checkpoint(
                    "pre-filter"
                ).service_rows
            )

            assert all(
                checkpoint.baseline_trace_sha256
                == baseline.run.trace.trace_sha256
                for checkpoint
                in baseline.checkpoints
            )

            assert (
                baseline.checkpoint(
                    "pre-validation"
                ).context_items
                == ()
            )

            if slot.template_id == "V1":
                assert (
                    baseline.run.trace.trace_sha256
                    == reference.run.trace.trace_sha256
                )

            else:
                assert (
                    baseline.run.trace.trace_sha256
                    != reference.run.trace.trace_sha256
                )

                changed[
                    slot.template_id
                ] += 1

    assert cells == 864

    assert changed == {
        "V2": 216,
        "V3": 216,
        "V4": 216,
    }


def test_all_4320_replays_preserve_registered_probe_semantics_and_cost():
    assert (
        CALIBRATED_REPLAY_COSTS
        == EXPECTED_COSTS
    )

    plan = _plan()

    replay_count = 0

    for slot in plan.public_slots:
        for hidden_stratum in HIDDEN_STRATA:
            truth = _assignment(
                slot,
                hidden_stratum,
            )

            baseline = (
                materialize_protected_replay_baseline(
                    public_slot=slot,
                    hidden_assignment=truth,
                )
            )

            problem = (
                build_scientific_development_problem(
                    baseline.run.trace
                )
            )

            passing = []

            for (
                sequence,
                experiment,
            ) in enumerate(
                problem.experiments
            ):
                replay = (
                    execute_checkpoint_replay(
                        baseline=baseline,
                        problem=problem,
                        experiment_key=(
                            experiment.key
                        ),
                        sequence=sequence,
                    )
                )

                replay_count += 1

                assert (
                    replay.tool_interaction_count
                    == EXPECTED_COSTS[
                        experiment.key
                    ]
                )

                if replay.passed:
                    passing.append(
                        experiment.key
                    )

            expected = (
                EXPECTED_PASSING_PROBE[
                    hidden_stratum
                ]
            )

            assert tuple(
                passing
            ) == (
                ()
                if expected
                is None
                else (
                    expected,
                )
            )

    assert replay_count == 4320


def test_v3_context_respects_checkpoint_boundary_and_fresh_context_replay():
    plan = _plan()

    v3_slots = tuple(
        slot
        for slot
        in plan.public_slots
        if slot.template_id
        == "V3"
    )

    assert len(
        v3_slots
    ) == 36

    for slot in v3_slots:
        truth = _assignment(
            slot,
            "state_context",
        )

        baseline = (
            materialize_protected_replay_baseline(
                public_slot=slot,
                hidden_assignment=truth,
            )
        )

        expected_tag = dict(
            slot.nuisance_items
        )[
            "benign_context_tag"
        ]

        assert (
            baseline.checkpoint(
                "pre-filter"
            ).context_mapping()[
                "benign_context_tag"
            ]
            == expected_tag
        )

        assert (
            baseline.checkpoint(
                "post-filter"
            ).context_mapping()[
                "benign_context_tag"
            ]
            == expected_tag
        )

        assert (
            baseline.checkpoint(
                "pre-validation"
            ).context_items
            == ()
        )

        problem = (
            build_scientific_development_problem(
                baseline.run.trace
            )
        )

        p4 = next(
            experiment
            for experiment
            in problem.experiments
            if experiment.key
            == "p4-fresh-context"
        )

        intervention = (
            env.P094DiagnosticIntervention(
                kind=p4.intervention_kind,
                target=p4.intervention_target,
            )
        )

        fresh_context = (
            baseline._context_loader(
                intervention
            )
        )

        assert (
            fresh_context[
                "benign_context_tag"
            ]
            == expected_tag
        )

        replay = (
            execute_checkpoint_replay(
                baseline=baseline,
                problem=problem,
                experiment_key=(
                    "p4-fresh-context"
                ),
                sequence=0,
            )
        )

        assert (
            replay.passed
            is True
        )

        assert (
            replay.tool_interaction_count
            == 3
        )


def test_materialization_is_exactly_deterministic():
    plan = _plan()

    for truth in plan.hidden_assignments:
        slot = next(
            slot
            for slot
            in plan.public_slots
            if slot.case_id
            == truth.case_id
        )

        first = (
            materialize_protected_replay_baseline(
                public_slot=slot,
                hidden_assignment=truth,
            )
        )

        second = (
            materialize_protected_replay_baseline(
                public_slot=slot,
                hidden_assignment=truth,
            )
        )

        assert (
            first.run.trace.trace_sha256
            == second.run.trace.trace_sha256
        )

        assert (
            tuple(
                checkpoint.state_sha256
                for checkpoint
                in first.checkpoints
            )
            == tuple(
                checkpoint.state_sha256
                for checkpoint
                in second.checkpoints
            )
        )


def test_treatment_visible_run_identity_contains_only_public_case_identity():
    plan = _plan()

    for slot in plan.public_slots:
        for hidden_stratum in HIDDEN_STRATA:
            truth = _assignment(
                slot,
                hidden_stratum,
            )

            baseline = (
                materialize_protected_replay_baseline(
                    public_slot=slot,
                    hidden_assignment=truth,
                )
            )

            assert (
                baseline.run.run_id
                == slot.case_id
            )

            assert (
                hidden_stratum
                not in baseline.run.run_id
            )

            expected_hypothesis = (
                EXPECTED_HYPOTHESIS_BY_STRATUM[
                    hidden_stratum
                ]
            )

            if expected_hypothesis is not None:
                assert (
                    expected_hypothesis
                    not in baseline.run.run_id
                )


def test_materializer_source_has_no_randomness_persistence_or_treatment_execution():
    source = inspect.getsource(
        materialization
    )

    for forbidden in (
        "os.urandom",
        "secrets.",
        "write_text",
        "write_bytes",
        "run_scientific_arm",
        "evaluate_protected_records",
    ):
        assert forbidden not in source
