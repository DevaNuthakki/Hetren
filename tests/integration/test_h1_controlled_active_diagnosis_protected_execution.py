from dataclasses import replace
from pathlib import Path

import pytest

from environments.agent.h1_controlled_active_diagnosis import (
    H1ObservedExperiment,
    build_development_fixtures,
    execute_development_experiment,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    Verdict,
    canonical_sha256,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis import (
    H1Arm,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis_protected_evaluation import (
    evaluate_treatment_batch,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis_protected_execution import (
    parse_public_manifest_cases,
    reconstruct_public_case,
    run_treatment_batch_from_manifest,
)


TEST_HIDDEN_MANIFEST_SHA = (
    "f" * 64
)


def development_inputs():
    fixtures = (
        build_development_fixtures()
    )

    manifest = {
        "record_type": "H1PublicManifest",
        "schema_version": 1,
        "batch_id": "d1-development-only",
        "protocol_sha256": "1" * 64,
        "harness_commit_id": "2" * 40,
        "generator_id": "d1-development-test",
        "generator_version": "1",
        "cases": [
            {
                "case_id": fixture.public_case.case_id,
                "template_id": fixture.public_case.template_id,
                "singleton_target": fixture.public_case.singleton_target,
                "problem_sha256": (
                    fixture.public_case.problem.problem_sha256
                ),
            }
            for fixture
            in fixtures
        ],
    }

    truth_by_case = {
        fixture.truth.case_id:
            fixture.truth.hidden_fault_key
        for fixture
        in fixtures
    }

    truth_objects = {
        fixture.truth.case_id:
            fixture.truth
        for fixture
        in fixtures
    }

    def executor_factory(
        public_case,
    ):
        truth = truth_objects[
            public_case.case_id
        ]

        def execute(
            experiment_key,
        ):
            return (
                execute_development_experiment(
                    public_case=public_case,
                    truth=truth,
                    experiment_key=experiment_key,
                )
            )

        return execute

    return (
        fixtures,
        manifest,
        truth_by_case,
        executor_factory,
    )


def hidden_manifest_for_truth(
    truth_by_case,
    *,
    batch_id="d1-development-only",
):
    return {
        "record_type": "H1HiddenTruthManifest",
        "schema_version": 1,
        "batch_id": batch_id,
        "assignments": [
            {
                "case_id": case_id,
                "hidden_fault_key": (
                    truth_by_case[
                        case_id
                    ]
                ),
            }
            for case_id in sorted(
                truth_by_case
            )
        ],
    }


def development_batch():
    (
        _fixtures,
        manifest,
        _truth_by_case,
        executor_factory,
    ) = development_inputs()

    return run_treatment_batch_from_manifest(
        public_manifest=manifest,
        expected_public_manifest_sha256=(
            canonical_sha256(
                manifest
            )
        ),
        executor_factory=executor_factory,
    )


def development_evaluation():
    (
        _fixtures,
        _manifest,
        truth_by_case,
        _executor_factory,
    ) = development_inputs()

    batch = development_batch()

    hidden_manifest = (
        hidden_manifest_for_truth(
            truth_by_case
        )
    )

    return (
        batch,
        evaluate_treatment_batch(
            treatment_batch=batch,
            hidden_manifest=hidden_manifest,
            expected_hidden_manifest_sha256=(
                canonical_sha256(
                    hidden_manifest
                )
            ),
        ),
    )


def metrics_by_key(
    evaluation,
):
    return {
        (
            metric.group,
            metric.arm,
        ): metric
        for metric
        in evaluation.metric_slices
    }


def comparisons_by_id(
    evaluation,
):
    return {
        comparison.comparison_id:
            comparison
        for comparison
        in evaluation.paired_comparisons
    }


def math_isclose(
    left,
    right,
):
    return abs(
        left
        - right
    ) <= 1e-12


def test_public_manifest_parser_and_reconstruction_cover_all_development_cases():
    (
        fixtures,
        manifest,
        _truth,
        _factory,
    ) = development_inputs()

    (
        batch_id,
        refs,
    ) = parse_public_manifest_cases(
        manifest
    )

    assert batch_id == (
        "d1-development-only"
    )

    assert len(
        refs
    ) == len(
        fixtures
    ) == 32

    for ref in refs:
        public_case = (
            reconstruct_public_case(
                ref
            )
        )

        assert (
            public_case.case_id
            == ref.case_id
        )

        assert (
            public_case.problem.problem_sha256
            == ref.problem_sha256
        )


def test_public_manifest_parser_rejects_hidden_field():
    (
        _fixtures,
        manifest,
        _truth,
        _factory,
    ) = development_inputs()

    manifest = {
        **manifest,
        "cases": [
            dict(
                case
            )
            for case
            in manifest[
                "cases"
            ]
        ],
    }

    manifest[
        "cases"
    ][0][
        "hidden_fault_key"
    ] = "H1"

    with pytest.raises(
        ContractError,
        match="treatment-visible schema",
    ):
        parse_public_manifest_cases(
            manifest
        )


def test_reconstruction_rejects_problem_hash_mismatch():
    (
        _fixtures,
        manifest,
        _truth,
        _factory,
    ) = development_inputs()

    (
        _batch_id,
        refs,
    ) = parse_public_manifest_cases(
        manifest
    )

    bad_ref = replace(
        refs[
            0
        ],
        problem_sha256=(
            "0" * 64
        ),
    )

    with pytest.raises(
        ContractError,
        match="problem hash mismatch",
    ):
        reconstruct_public_case(
            bad_ref
        )


def test_treatment_batch_has_exact_case_arm_cardinality():
    batch = development_batch()

    assert len(
        batch.case_ids
    ) == 32

    assert len(
        batch.records
    ) == (
        32
        * 4
    )

    for case_id in batch.case_ids:
        arms = {
            record.arm
            for record
            in batch.records
            if record.case_id
            == case_id
        }

        assert arms == {
            arm.value
            for arm in H1Arm
        }


def test_treatment_batch_payload_contains_no_evaluator_truth():
    batch = development_batch()

    rendered = str(
        batch.to_payload()
    )

    assert (
        "hidden_fault_key"
        not in rendered
    )

    assert (
        "hidden_truth"
        not in rendered
    )

    assert (
        "raw_seed"
        not in rendered
    )


def test_treatment_batch_is_deterministic():
    first = development_batch()
    second = development_batch()

    assert (
        first.canonical_json_bytes
        == second.canonical_json_bytes
    )

    assert (
        first.batch_sha256
        == second.batch_sha256
    )


def test_wrong_case_executor_result_is_rejected():
    (
        _fixtures,
        manifest,
        _truth,
        _factory,
    ) = development_inputs()

    one_case_manifest = {
        **manifest,
        "cases": [
            manifest[
                "cases"
            ][0]
        ],
    }

    def bad_factory(
        public_case,
    ):
        def execute(
            experiment_key,
        ):
            experiment = {
                item.key: item
                for item
                in public_case.problem.experiments
            }[
                experiment_key
            ]

            return H1ObservedExperiment(
                case_id="wrong-case-id",
                experiment_key=experiment_key,
                verdict=Verdict.PASS,
                actual_cost_units=(
                    experiment.cost_units
                ),
                observed_output=1,
                expected_output=1,
                workflow_step_count=1,
                evidence_sha256=(
                    "a" * 64
                ),
            )

        return execute

    with pytest.raises(
        ContractError,
        match="case ID mismatch",
    ):
        run_treatment_batch_from_manifest(
            public_manifest=one_case_manifest,
            expected_public_manifest_sha256=(
                canonical_sha256(
                    one_case_manifest
                )
            ),
            executor_factory=bad_factory,
        )


def test_development_evaluation_matches_frozen_correct_diagnosis_counts():
    (
        _batch,
        evaluation,
    ) = development_evaluation()

    metrics = metrics_by_key(
        evaluation
    )

    assert metrics[
        (
            "overall",
            H1Arm.TRACE_ONLY.value,
        )
    ].correct_specific_count == 0

    assert metrics[
        (
            "overall",
            H1Arm.SEEDED_RANDOM_ACTIVE.value,
        )
    ].correct_specific_count == 11

    assert metrics[
        (
            "overall",
            H1Arm.MAX_INFORMATION_GAIN_ACTIVE.value,
        )
    ].correct_specific_count == 20

    assert metrics[
        (
            "overall",
            H1Arm.HEAL_INFORMATION_GAIN_PER_COST.value,
        )
    ].correct_specific_count == 32


def test_unfavorable_terminal_outcomes_remain_in_denominator():
    (
        _batch,
        evaluation,
    ) = development_evaluation()

    metrics = metrics_by_key(
        evaluation
    )

    for arm in H1Arm:
        metric = metrics[
            (
                "overall",
                arm.value,
            )
        ]

        assert metric.denominator == 32

        assert (
            metric.correct_specific_count
            + metric.false_specific_count
            + metric.inconclusive_count
            + metric.budget_exhausted_count
        ) == 32


def test_wrong_specific_diagnosis_is_false_not_invalid_or_dropped():
    (
        _fixtures,
        _manifest,
        truth_by_case,
        _factory,
    ) = development_inputs()

    batch = development_batch()

    target_index = next(
        index
        for index, record
        in enumerate(
            batch.records
        )
        if (
            record.arm
            == H1Arm.HEAL_INFORMATION_GAIN_PER_COST.value
        )
    )

    target = batch.records[
        target_index
    ]

    true_fault = truth_by_case[
        target.case_id
    ]

    wrong_fault = next(
        fault
        for fault in (
            "H1",
            "H2",
            "H3",
            "H4",
        )
        if fault != true_fault
    )

    mutated_record = replace(
        target,
        status=DiagnosisStatus.DIAGNOSED.value,
        diagnosed_hypothesis_key=wrong_fault,
    )

    records = list(
        batch.records
    )

    records[
        target_index
    ] = mutated_record

    mutated_batch = replace(
        batch,
        records=tuple(
            records
        ),
    )

    hidden_manifest = (
        hidden_manifest_for_truth(
            truth_by_case
        )
    )

    evaluation = evaluate_treatment_batch(
        treatment_batch=mutated_batch,
        hidden_manifest=hidden_manifest,
        expected_hidden_manifest_sha256=(
            canonical_sha256(
                hidden_manifest
            )
        ),
    )

    c3 = metrics_by_key(
        evaluation
    )[
        (
            "overall",
            H1Arm.HEAL_INFORMATION_GAIN_PER_COST.value,
        )
    ]

    assert c3.denominator == 32
    assert c3.false_specific_count == 1
    assert c3.correct_specific_count == 31


def test_evaluator_rejects_missing_truth_case():
    (
        _fixtures,
        _manifest,
        truth,
        _factory,
    ) = development_inputs()

    batch = development_batch()

    truth = dict(
        truth
    )

    truth.pop(
        next(
            iter(
                truth
            )
        )
    )

    with pytest.raises(
        ContractError,
        match="missing treatment cases",
    ):
        hidden_manifest = (
            hidden_manifest_for_truth(
                truth
            )
        )

        evaluate_treatment_batch(
            treatment_batch=batch,
            hidden_manifest=hidden_manifest,
            expected_hidden_manifest_sha256=(
                canonical_sha256(
                    hidden_manifest
                )
            ),
        )


def test_evaluator_rejects_extra_truth_case():
    (
        _fixtures,
        _manifest,
        truth,
        _factory,
    ) = development_inputs()

    batch = development_batch()

    truth = {
        **truth,
        "extra-case": "H1",
    }

    with pytest.raises(
        ContractError,
        match="extra cases",
    ):
        hidden_manifest = (
            hidden_manifest_for_truth(
                truth
            )
        )

        evaluate_treatment_batch(
            treatment_batch=batch,
            hidden_manifest=hidden_manifest,
            expected_hidden_manifest_sha256=(
                canonical_sha256(
                    hidden_manifest
                )
            ),
        )


def test_evaluator_rejects_unknown_truth_fault():
    (
        _fixtures,
        _manifest,
        truth,
        _factory,
    ) = development_inputs()

    batch = development_batch()

    truth = dict(
        truth
    )

    first = next(
        iter(
            truth
        )
    )

    truth[
        first
    ] = "H5"

    with pytest.raises(
        ContractError,
        match="unknown hidden fault",
    ):
        hidden_manifest = (
            hidden_manifest_for_truth(
                truth
            )
        )

        evaluate_treatment_batch(
            treatment_batch=batch,
            hidden_manifest=hidden_manifest,
            expected_hidden_manifest_sha256=(
                canonical_sha256(
                    hidden_manifest
                )
            ),
        )


def test_paired_comparisons_use_matched_case_denominators():
    (
        _batch,
        evaluation,
    ) = development_evaluation()

    comparisons = comparisons_by_id(
        evaluation
    )

    assert comparisons[
        "c3_vs_c0_overall"
    ].denominator == 32

    assert comparisons[
        "c3_vs_c1_cost_sensitive"
    ].denominator == 16

    assert comparisons[
        "c3_vs_c2_cost_sensitive"
    ].denominator == 16

    assert comparisons[
        "c3_vs_c2_neutral"
    ].denominator == 16

    for comparison in comparisons.values():
        assert (
            comparison.both_correct_count
            + comparison.target_only_correct_count
            + comparison.comparator_only_correct_count
            + comparison.neither_correct_count
        ) == comparison.denominator


def test_primary_registered_thresholds_are_mechanical_and_frozen():
    (
        _batch,
        evaluation,
    ) = development_evaluation()

    decision = evaluation.registered_criteria

    assert math_isclose(
        decision.primary_c3_minus_c0,
        1.0,
    )

    expected = (
        decision.primary_c3_minus_c0
        >= 0.25
        and decision.c3_false_specific_rate
        <= (
            decision.c0_false_specific_rate
            + 0.02
        )
    )

    assert (
        decision.primary_h1_criteria_met
        is expected
    )


def test_selection_policy_threshold_matches_registered_pair():
    (
        _batch,
        evaluation,
    ) = development_evaluation()

    decision = evaluation.registered_criteria

    value = comparisons_by_id(
        evaluation
    )[
        "c3_vs_c1_cost_sensitive"
    ].target_minus_comparator_rate

    assert math_isclose(
        decision.cost_sensitive_c3_minus_c1,
        value,
    )

    assert (
        decision.selection_policy_bound_met
        is (
            value
            >= 0.10
        )
    )


def test_cost_aware_threshold_uses_cost_sensitive_and_neutral_controls():
    (
        _batch,
        evaluation,
    ) = development_evaluation()

    decision = evaluation.registered_criteria

    comparisons = comparisons_by_id(
        evaluation
    )

    sensitive = comparisons[
        "c3_vs_c2_cost_sensitive"
    ].target_minus_comparator_rate

    neutral = comparisons[
        "c3_vs_c2_neutral"
    ].target_minus_comparator_rate

    assert math_isclose(
        decision.cost_sensitive_c3_minus_c2,
        sensitive,
    )

    assert math_isclose(
        decision.neutral_c3_minus_c2,
        neutral,
    )

    expected = (
        sensitive
        >= 0.20
        and abs(
            neutral
        )
        <= 0.05
    )

    assert (
        decision.cost_aware_bound_met
        is expected
    )


def test_template_fault_metrics_cover_every_case_for_every_arm():
    (
        batch,
        evaluation,
    ) = development_evaluation()

    by_arm = {}

    for metric in evaluation.template_fault_metrics:
        by_arm.setdefault(
            metric.arm,
            0,
        )

        by_arm[
            metric.arm
        ] += metric.denominator

    assert by_arm == {
        arm.value: len(
            batch.case_ids
        )
        for arm in H1Arm
    }


def test_resource_accounting_equals_sum_of_treatment_records():
    (
        batch,
        evaluation,
    ) = development_evaluation()

    metrics = metrics_by_key(
        evaluation
    )

    for arm in H1Arm:
        records = [
            record
            for record
            in batch.records
            if record.arm
            == arm.value
        ]

        metric = metrics[
            (
                "overall",
                arm.value,
            )
        ]

        assert (
            metric.total_declared_cost_units
            == sum(
                record.declared_cost_units
                for record
                in records
            )
        )

        assert (
            metric.total_actual_cost_units
            == sum(
                record.actual_cost_units
                for record
                in records
            )
        )

        assert (
            metric.total_experiment_count
            == sum(
                record.experiment_count
                for record
                in records
            )
        )

        assert (
            metric.total_workflow_step_count
            == sum(
                record.workflow_step_count
                for record
                in records
            )
        )


def test_evaluation_hash_is_deterministic():
    (
        _batch,
        first,
    ) = development_evaluation()

    (
        _batch,
        second,
    ) = development_evaluation()

    assert (
        first.canonical_json_bytes
        == second.canonical_json_bytes
    )

    assert (
        first.evaluation_sha256
        == second.evaluation_sha256
    )


def test_treatment_rejects_public_manifest_hash_mismatch():
    (
        _fixtures,
        manifest,
        _truth,
        factory,
    ) = development_inputs()

    with pytest.raises(
        ContractError,
        match="public manifest does not match",
    ):
        run_treatment_batch_from_manifest(
            public_manifest=manifest,
            expected_public_manifest_sha256=(
                "0" * 64
            ),
            executor_factory=factory,
        )


def test_active_arms_receive_fresh_arm_blind_executors():
    (
        fixtures,
        manifest,
        _truth,
        _factory,
    ) = development_inputs()

    fixture = fixtures[
        0
    ]

    one_case_manifest = {
        **manifest,
        "cases": [
            manifest[
                "cases"
            ][0]
        ],
    }

    factory_calls = []

    def factory(
        public_case,
    ):
        factory_calls.append(
            public_case.case_id
        )

        truth = fixture.truth

        def execute(
            experiment_key,
        ):
            return (
                execute_development_experiment(
                    public_case=public_case,
                    truth=truth,
                    experiment_key=(
                        experiment_key
                    ),
                )
            )

        return execute

    run_treatment_batch_from_manifest(
        public_manifest=one_case_manifest,
        expected_public_manifest_sha256=(
            canonical_sha256(
                one_case_manifest
            )
        ),
        executor_factory=factory,
    )

    assert factory_calls == [
        fixture.public_case.case_id,
        fixture.public_case.case_id,
        fixture.public_case.case_id,
    ]


def test_evaluator_rejects_hidden_manifest_hash_mismatch():
    (
        _fixtures,
        _manifest,
        truth,
        _factory,
    ) = development_inputs()

    batch = development_batch()

    hidden_manifest = (
        hidden_manifest_for_truth(
            truth
        )
    )

    with pytest.raises(
        ContractError,
        match="hidden manifest does not match",
    ):
        evaluate_treatment_batch(
            treatment_batch=batch,
            hidden_manifest=hidden_manifest,
            expected_hidden_manifest_sha256=(
                "0" * 64
            ),
        )


def test_evaluator_rejects_hidden_manifest_batch_mismatch():
    (
        _fixtures,
        _manifest,
        truth,
        _factory,
    ) = development_inputs()

    batch = development_batch()

    hidden_manifest = (
        hidden_manifest_for_truth(
            truth,
            batch_id="wrong-batch",
        )
    )

    with pytest.raises(
        ContractError,
        match="batch ID does not match",
    ):
        evaluate_treatment_batch(
            treatment_batch=batch,
            hidden_manifest=hidden_manifest,
            expected_hidden_manifest_sha256=(
                canonical_sha256(
                    hidden_manifest
                )
            ),
        )


def test_execution_and_evaluation_modules_preserve_directional_separation():
    execution_source = Path(
        "packages/engines/behavioral/"
        "h1_controlled_active_diagnosis_protected_execution.py"
    ).read_text(
        encoding="utf-8"
    )

    evaluation_source = Path(
        "packages/engines/behavioral/"
        "h1_controlled_active_diagnosis_protected_evaluation.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "execute_development_experiment"
        not in execution_source
    )

    assert (
        "H1DevelopmentTruth"
        not in execution_source
    )

    assert (
        "h1_controlled_active_diagnosis_generation"
        not in execution_source
    )

    assert (
        "h1_controlled_active_diagnosis_persistence"
        not in execution_source
    )

    assert (
        "execute_development_experiment"
        not in evaluation_source
    )

    assert (
        "H1DevelopmentTruth"
        not in evaluation_source
    )
