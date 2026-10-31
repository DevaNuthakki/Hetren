"""Exploratory, deterministic incident-triage diagnostic benchmark.

Three disclosed development cases. No blind holdout, real-world
generalization claim, protected execution, or deployment authority.

The evaluator reference labels are used only after policy predictions
have been obtained. All policies replay the same executed observations.
Attributed experiment cost is not wall-clock runtime.
"""

from __future__ import annotations

import argparse
import json
import re

from environments.agent.incident_triage import (
    IncidentFaultMode,
    expected_incident_ids,
    run_incident_triage,
)
from packages.core.hetren_diagnosis.contracts import (
    DiagnosisStatus,
    Observation,
    Verdict,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.lifecycle import (
    replay_observations,
    select_next_decision,
)
from packages.core.hetren_diagnosis.open_set import (
    select_next_open_set_decision,
)
from packages.engines.behavioral.incident_triage_diagnosis import (
    run_diagnosis_demo,
)
from packages.engines.behavioral.incident_triage_compound_open_set_development import (
    run_compound_open_set_development,
)

SCHEMA = "hetren.dev.incident-diagnostic-comparison.v1"

CASES = (
    "filter_tool_selection",
    "threshold_transformation",
    "compound_fault",
)

POLICIES = (
    "closed_world_one_probe",
    "open_set_one_probe",
    "predeclared_two_probe_challenge",
)

# Evaluator-only reference information, never passed to
# the planner or diagnostic lifecycle.
_EVALUATOR_REFERENCE = {
    "filter_tool_selection": "filter_tool_selection_fault",
    "threshold_transformation": "threshold_transformation_fault",
    "compound_fault": None,
}

_EXPECTED_PROBES = (
    "e1-replace-filter-tool",
    "e2-override-threshold",
)


def _validate_run_prefix(value: str) -> None:
    if (
        type(value) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}",
            value,
        ) is None
    ):
        raise ValueError("invalid development run prefix")


def _collect_case(case: str, prefix: str):
    """Execute the real fixture without evaluator reference labels."""

    if case == "compound_fault":
        result = run_compound_open_set_development(
            run_id=f"{prefix}-compound",
        )
        return (
            result.problem,
            result.observations,
            result.diagnostic_runs,
        )

    mode = IncidentFaultMode(case)

    diagnosis = run_diagnosis_demo(
        mode,
        run_id=f"{prefix}-{case}",
    )
    problem = diagnosis.problem

    if len(problem.experiments) != 2:
        raise RuntimeError("unexpected diagnostic experiment count")

    first_experiment, second_experiment = problem.experiments

    if (
        diagnosis.initial_decision.experiment_key
        != first_experiment.key
        or diagnosis.experiment_result.observation.experiment_key
        != first_experiment.key
    ):
        raise RuntimeError("unexpected initial experiment")

    second_run = run_incident_triage(
        mode,
        run_id=f"{prefix}-{case}-second",
        intervention=second_experiment.intervention_kind,
    )

    verdict = Verdict.PASS if second_run.passed else Verdict.FAIL

    counterexample = None
    if verdict is Verdict.FAIL:
        incident_ids = expected_incident_ids()
        counterexample = canonical_sha256({
            "expected_report": {
                "service": diagnosis.baseline_run.report.service,
                "incident_ids": incident_ids,
                "count": len(incident_ids),
            },
            "actual_report": (
                second_run.report.canonical_payload()
            ),
        })

    observation = Observation(
        sequence=1,
        experiment_key=second_experiment.key,
        experiment_sha256=second_experiment.experiment_sha256,
        verdict=verdict,
        actual_cost_units=second_experiment.cost_units,
        evidence_sha256=(
            second_run.execution_evidence_sha256
        ),
        counterexample_sha256=counterexample,
    )

    return (
        problem,
        (
            diagnosis.experiment_result.observation,
            observation,
        ),
        (
            diagnosis.experiment_result.agent_run,
            second_run,
        ),
    )


def validate_executed_evidence(
    problem,
    observations,
    runs,
) -> None:
    """Reject missing, fabricated-by-mismatch, or reordered references.

    These are local consistency checks, not cryptographic provenance
    or independently trusted observation attestations.
    """
    if (
        len(problem.experiments) != 2
        or tuple(item.key for item in problem.experiments)
        != _EXPECTED_PROBES
        or len(observations) != 2
        or len(runs) != 2
    ):
        raise ValueError("unexpected two-probe evidence structure")

    if runs[0].run_id == runs[1].run_id:
        raise ValueError("diagnostic executions share an identity")

    for index, (experiment, observation, run) in enumerate(
        zip(problem.experiments, observations, runs)
    ):
        if (
            observation.sequence != index
            or observation.experiment_key != experiment.key
            or observation.experiment_sha256
            != experiment.experiment_sha256
            or observation.actual_cost_units
            != experiment.cost_units
            or observation.evidence_sha256
            != run.execution_evidence_sha256
            or observation.verdict
            is not (
                Verdict.PASS if run.passed else Verdict.FAIL
            )
            or not run.trace.events
        ):
            raise ValueError(
                f"executed evidence mismatch at probe {index + 1}"
            )

        if observation.verdict is Verdict.FAIL:
            expected = expected_incident_ids()
            expected_counterexample = canonical_sha256({
                "expected_report": {
                    "service": run.report.service,
                    "incident_ids": expected,
                    "count": len(expected),
                },
                "actual_report": (
                    run.report.canonical_payload()
                ),
            })
            if (
                observation.counterexample_sha256
                != expected_counterexample
            ):
                raise ValueError(
                    f"counterexample mismatch at probe {index + 1}"
                )
        elif observation.counterexample_sha256 is not None:
            raise ValueError(
                f"unexpected counterexample at probe {index + 1}"
            )


def _closed_prediction(problem, first):
    decision = select_next_decision(problem, first)
    if decision.status is not DiagnosisStatus.DIAGNOSED:
        return decision.status, None, "closed_world"

    posterior = replay_observations(problem, first)

    surviving = tuple(
        key for key, probability in posterior.items()
        if probability > 1e-12
    )

    if len(surviving) != 1:
        raise RuntimeError("closed-world specific result is ambiguous")

    return decision.status, surviving[0], "closed_world"


def _open_prediction(problem, observations):
    decision = select_next_open_set_decision(
        problem, observations,
    )
    return (
        decision.status,
        decision.diagnosed_hypothesis_key,
        decision.reason.value,
    )


def classify_outcome(
    status: DiagnosisStatus,
    prediction: str | None,
    evaluator_reference: str | None,
) -> str:
    """Score terminal outcomes, keeping budget failures separate."""

    if status is DiagnosisStatus.DIAGNOSED:
        if not isinstance(prediction, str) or not prediction:
            raise ValueError("specific diagnosis lacks a hypothesis")
        if prediction == evaluator_reference:
            return "correct_specific"
        return "false_specific"

    if prediction is not None:
        raise ValueError("non-diagnosed result claims a hypothesis")

    if status is DiagnosisStatus.INCONCLUSIVE:
        return (
            "appropriate_abstention"
            if evaluator_reference is None
            else "missed_known_diagnosis"
        )

    if status is DiagnosisStatus.BUDGET_EXHAUSTED:
        return "budget_exhausted"

    raise ValueError("nonterminal diagnosis cannot be scored")


def run_development_benchmark(
    *,
    run_prefix: str = "a5-benchmark",
) -> dict:
    """Compare three policies against fixed, openly disclosed cases."""
    _validate_run_prefix(run_prefix)

    # Decisions are produced before looking up evaluation labels.
    pending = []

    for case in CASES:
        problem, observations, runs = _collect_case(
            case, run_prefix,
        )

        validate_executed_evidence(
            problem, observations, runs,
        )

        first = observations[:1]

        predictions = (
            _closed_prediction(problem, first),
            _open_prediction(problem, first),
            _open_prediction(problem, observations),
        )

        pending.append(
            (case, observations, predictions)
        )

    records = []

    # This is the evaluator-facing stage. Reference labels are not
    # passed to the decision functions or probe execution.
    for case, observations, predictions in pending:
        expected = _EVALUATOR_REFERENCE[case]

        for index, (
            status, prediction, reason
        ) in enumerate(predictions):
            used = (
                observations
                if index == 2
                else observations[:1]
            )

            records.append({
                "case": case,
                "reference_set_membership": (
                    "outside_single_fault_reference_set"
                    if expected is None
                    else "known_single_fault"
                ),
                "policy": POLICIES[index],
                "status": status.name,
                "reason": reason,
                "diagnosed_hypothesis": prediction,
                "evaluator_reference": expected,
                "classification": classify_outcome(
                    status, prediction, expected,
                ),
                "experiment_count": len(used),
                "attributed_cost_units": sum(
                    item.actual_cost_units
                    for item in used
                ),
                "observation_evidence_sha256": [
                    item.evidence_sha256 for item in used
                ],
            })

    summary = {}

    categories = (
        "correct_specific",
        "false_specific",
        "appropriate_abstention",
        "missed_known_diagnosis",
        "budget_exhausted",
    )

    for policy in POLICIES:
        rows = [
            item for item in records
            if item["policy"] == policy
        ]
        total_cost = sum(
            item["attributed_cost_units"]
            for item in rows
        )
        summary[policy] = {
            "cases": len(rows),
            **{
                category: sum(
                    item["classification"] == category
                    for item in rows
                )
                for category in categories
            },
            "total_attributed_cost_units": total_cost,
            "mean_attributed_cost_units": (
                total_cost / len(rows)
            ),
        }

    return {
        "schema": SCHEMA,
        "run_prefix": run_prefix,
        "case_count": len(CASES),
        "reference_set": (
            "two mutually exclusive incident-triage "
            "single-fault hypotheses"
        ),
        "method": (
            "counterfactual replay of common real "
            "development-fixture observations"
        ),
        "cost_definition": (
            "policy-attributed intervention units; "
            "not measured policy runtime"
        ),
        "claims": {
            "independent_scientific_evaluation": False,
            "unseen_holdout": False,
            "statistical_generalization_established": False,
            "production_accuracy_established": False,
            "deployment_authorized": False,
        },
        "summary": summary,
        "case_results": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fixed development-only Hetren "
            "diagnostic reliability comparison."
        )
    )
    parser.add_argument(
        "--run-prefix",
        default="a5-benchmark",
    )
    args = parser.parse_args(argv)

    try:
        report = run_development_benchmark(
            run_prefix=args.run_prefix,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
