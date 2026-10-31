import inspect
from dataclasses import replace

import pytest

import environments.agent.h1_controlled_active_diagnosis as environment
import packages.engines.behavioral.h1_controlled_active_diagnosis as harness
from environments.agent.h1_controlled_active_diagnosis import (
    build_development_fixtures,
    execute_development_experiment,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
)
from packages.core.hetren_diagnosis.planner import (
    expected_information_gain,
    initial_posterior,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis import (
    H1Arm,
    run_h1_arm,
)


def fixtures():
    return build_development_fixtures()


def executor_for(fixture):
    return lambda experiment_key: execute_development_experiment(
        public_case=fixture.public_case,
        truth=fixture.truth,
        experiment_key=experiment_key,
    )


def run_fixture(
    fixture,
    arm,
):
    return run_h1_arm(
        public_case=fixture.public_case,
        arm=arm,
        execute_experiment=(
            None
            if arm is H1Arm.TRACE_ONLY
            else executor_for(
                fixture
            )
        ),
    )


def prediction_for(
    fixture,
    experiment_key,
):
    experiment = next(
        experiment
        for experiment
        in fixture.public_case.problem.experiments
        if experiment.key == experiment_key
    )

    return dict(
        experiment.predicted_verdicts
    )[
        fixture.truth.hidden_fault_key
    ]


def test_development_fixture_count_and_cross_product():
    values = fixtures()

    assert len(
        values
    ) == 32

    assert len(
        {
            fixture.public_case.case_id
            for fixture in values
        }
    ) == 32

    by_template = {}

    for fixture in values:
        by_template.setdefault(
            fixture.public_case.template_id,
            set(),
        ).add(
            fixture.truth.hidden_fault_key
        )

    assert set(
        by_template
    ) == {
        "T1",
        "T2",
        "T3",
        "T4",
        "N1",
        "N2",
        "N3",
        "N4",
    }

    assert all(
        fault_keys
        == {
            "H1",
            "H2",
            "H3",
            "H4",
        }
        for fault_keys in by_template.values()
    )


def test_public_case_shape_contains_no_evaluator_truth():
    names = {
        field.name
        for field in environment.H1PublicCase.__dataclass_fields__.values()
    }

    assert names == {
        "case_id",
        "template_id",
        "singleton_target",
        "problem",
    }


def test_initial_visible_trace_is_non_discriminating_within_template():
    values = fixtures()

    for template_id in (
        "T1",
        "T2",
        "T3",
        "T4",
        "N1",
        "N2",
        "N3",
        "N4",
    ):
        matching = [
            fixture
            for fixture in values
            if fixture.public_case.template_id == template_id
        ]

        event_payloads = {
            tuple(
                tuple(
                    sorted(
                        event.canonical_payload().items()
                    )
                )
                for event in fixture.public_case.problem.trace.events
            )
            for fixture in matching
        }

        assert len(
            event_payloads
        ) == 1


def test_real_workflow_execution_matches_registered_prediction_matrix():
    for fixture in fixtures():
        for experiment in fixture.public_case.problem.experiments:
            execution = execute_development_experiment(
                public_case=fixture.public_case,
                truth=fixture.truth,
                experiment_key=experiment.key,
            )

            assert (
                execution.verdict
                is prediction_for(
                    fixture,
                    experiment.key,
                )
            )

            assert execution.observed_output in {
                4,
                5,
            }

            assert execution.expected_output == 4
            assert execution.workflow_step_count == 4


def test_treatment_harness_source_has_no_development_truth_dependency():
    source = inspect.getsource(
        harness
    )

    assert "H1DevelopmentTruth" not in source
    assert "hidden_fault_key" not in source
    assert "build_development_fixtures" not in source


def test_trace_only_arm_is_inconclusive_for_all_development_cases():
    for fixture in fixtures():
        result = run_fixture(
            fixture,
            H1Arm.TRACE_ONLY,
        )

        assert (
            result.status
            is DiagnosisStatus.INCONCLUSIVE
        )

        assert (
            result.diagnosed_hypothesis_key
            is None
        )

        assert result.experiment_sequence == ()
        assert result.actual_cost_units == 0


def test_c2_cost_sensitive_development_mechanism_is_one_of_four():
    cost_sensitive = [
        fixture
        for fixture in fixtures()
        if fixture.public_case.template_id.startswith(
            "T"
        )
    ]

    results = [
        (
            fixture,
            run_fixture(
                fixture,
                H1Arm.MAX_INFORMATION_GAIN_ACTIVE,
            ),
        )
        for fixture in cost_sensitive
    ]

    correct = [
        result
        for fixture, result in results
        if (
            result.diagnosed_hypothesis_key
            == fixture.truth.hidden_fault_key
        )
    ]

    assert len(
        cost_sensitive
    ) == 16

    assert len(
        correct
    ) == 4

    assert all(
        result.experiment_sequence
        == (
            "SINGLETON_PROBE",
        )
        for _, result in results
    )


def test_c3_cost_sensitive_development_cases_all_diagnose_correctly():
    cost_sensitive = [
        fixture
        for fixture in fixtures()
        if fixture.public_case.template_id.startswith(
            "T"
        )
    ]

    for fixture in cost_sensitive:
        result = run_fixture(
            fixture,
            H1Arm.HEAL_INFORMATION_GAIN_PER_COST,
        )

        assert (
            result.status
            is DiagnosisStatus.DIAGNOSED
        )

        assert (
            result.diagnosed_hypothesis_key
            == fixture.truth.hidden_fault_key
        )

        assert result.actual_cost_units == 2


def test_cost_neutral_c2_and_c3_both_diagnose_all_cases():
    neutral = [
        fixture
        for fixture in fixtures()
        if fixture.public_case.template_id.startswith(
            "N"
        )
    ]

    for arm in (
        H1Arm.MAX_INFORMATION_GAIN_ACTIVE,
        H1Arm.HEAL_INFORMATION_GAIN_PER_COST,
    ):
        for fixture in neutral:
            result = run_fixture(
                fixture,
                arm,
            )

            assert (
                result.status
                is DiagnosisStatus.DIAGNOSED
            )

            assert (
                result.diagnosed_hypothesis_key
                == fixture.truth.hidden_fault_key
            )

            assert result.actual_cost_units == 2


def test_c1_is_exactly_reproducible_for_same_case():
    for fixture in fixtures():
        first = run_fixture(
            fixture,
            H1Arm.SEEDED_RANDOM_ACTIVE,
        )

        second = run_fixture(
            fixture,
            H1Arm.SEEDED_RANDOM_ACTIVE,
        )

        assert (
            first.result_sha256
            == second.result_sha256
        )

        assert (
            first.experiment_sequence
            == second.experiment_sequence
        )


def test_final_budget_resolution_remains_diagnosed():
    for fixture in fixtures():
        result = run_fixture(
            fixture,
            H1Arm.HEAL_INFORMATION_GAIN_PER_COST,
        )

        assert result.actual_cost_units == 2

        assert (
            result.status
            is DiagnosisStatus.DIAGNOSED
        )


def test_null_probe_has_zero_information_gain():
    for fixture in fixtures():
        posterior = initial_posterior(
            fixture.public_case.problem
        )

        null_probe = next(
            experiment
            for experiment
            in fixture.public_case.problem.experiments
            if experiment.key == "NULL_PROBE"
        )

        assert (
            expected_information_gain(
                posterior,
                null_probe,
            )
            == pytest.approx(
                0.0,
                abs=1e-12,
            )
        )


def test_harness_rejects_execution_cost_drift_from_registered_cost():
    fixture = next(
        fixture
        for fixture in fixtures()
        if fixture.public_case.template_id == "T1"
    )

    def bad_executor(experiment_key):
        execution = execute_development_experiment(
            public_case=fixture.public_case,
            truth=fixture.truth,
            experiment_key=experiment_key,
        )

        return replace(
            execution,
            actual_cost_units=(
                execution.actual_cost_units
                + 1
            ),
        )

    with pytest.raises(
        ContractError,
        match=(
            "experiment actual cost does not match "
            "registered synthetic cost"
        ),
    ):
        run_h1_arm(
            public_case=fixture.public_case,
            arm=H1Arm.HEAL_INFORMATION_GAIN_PER_COST,
            execute_experiment=bad_executor,
        )


def test_development_modules_have_no_protected_generation_capability():
    combined = (
        inspect.getsource(
            environment
        )
        + "\n"
        + inspect.getsource(
            harness
        )
    )

    forbidden = (
        "secrets.token_bytes",
        "protected_seed",
        "protected_manifest",
        "hidden_truth_manifest",
        "seed_commitment",
    )

    for marker in forbidden:
        assert marker not in combined
