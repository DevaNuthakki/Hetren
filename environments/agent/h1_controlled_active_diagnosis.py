"""Development-only controlled H1 active-diagnosis environment.

This module implements the deterministic mechanism benchmark preregistered in
P09.3B.

It is development infrastructure only.

No protected seed, protected manifest, protected case, or protected result is
created here.

The environment contains four distinct single-stage latent faults. Every fault
produces the same treatment-visible initial failure. Diagnostic experiments
then replace registered subsets of pipeline stages with known-good behavior
and execute the real four-stage deterministic pipeline again.

Experiment verdicts are therefore produced by workflow execution rather than
by directly returning the latent fault label.
"""

from dataclasses import dataclass

from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    ContractError,
    DiagnosisProblem,
    EventKind,
    Experiment,
    Hypothesis,
    InterventionKind,
    TraceEvent,
    Verdict,
    canonical_sha256,
)


_HYPOTHESIS_KEYS = (
    "H1",
    "H2",
    "H3",
    "H4",
)

_STAGES = (
    "stage_1",
    "stage_2",
    "stage_3",
    "stage_4",
)

_HYPOTHESIS_TO_STAGE = {
    "H1": "stage_1",
    "H2": "stage_2",
    "H3": "stage_3",
    "H4": "stage_4",
}

_EXPECTED_OUTPUT = 4
_BASELINE_FAILED_OUTPUT = 5
_WORKFLOW_STEP_COUNT = 4


@dataclass(frozen=True)
class H1Template:
    """Treatment-visible benchmark template."""

    template_id: str
    priors: tuple[tuple[str, float], ...]
    singleton_target: str
    cost_sensitive: bool


@dataclass(frozen=True)
class H1PublicCase:
    """Treatment-visible case passed to diagnosis arms."""

    case_id: str
    template_id: str
    singleton_target: str
    problem: DiagnosisProblem


@dataclass(frozen=True)
class H1DevelopmentTruth:
    """Development-only evaluator truth; never passed to the arm harness."""

    case_id: str
    hidden_fault_key: str


@dataclass(frozen=True)
class H1DevelopmentFixture:
    """Inspectable development pairing of public case and evaluator truth."""

    public_case: H1PublicCase
    truth: H1DevelopmentTruth


@dataclass(frozen=True)
class H1ObservedExperiment:
    """Treatment-visible result of one real deterministic intervention."""

    case_id: str
    experiment_key: str
    verdict: Verdict
    actual_cost_units: int
    observed_output: int
    expected_output: int
    workflow_step_count: int
    evidence_sha256: str


_TEMPLATES = (
    H1Template(
        template_id="T1",
        priors=(
            ("H1", 0.70),
            ("H2", 0.10),
            ("H3", 0.10),
            ("H4", 0.10),
        ),
        singleton_target="H1",
        cost_sensitive=True,
    ),
    H1Template(
        template_id="T2",
        priors=(
            ("H1", 0.10),
            ("H2", 0.70),
            ("H3", 0.10),
            ("H4", 0.10),
        ),
        singleton_target="H2",
        cost_sensitive=True,
    ),
    H1Template(
        template_id="T3",
        priors=(
            ("H1", 0.10),
            ("H2", 0.10),
            ("H3", 0.70),
            ("H4", 0.10),
        ),
        singleton_target="H3",
        cost_sensitive=True,
    ),
    H1Template(
        template_id="T4",
        priors=(
            ("H1", 0.10),
            ("H2", 0.10),
            ("H3", 0.10),
            ("H4", 0.70),
        ),
        singleton_target="H4",
        cost_sensitive=True,
    ),
    H1Template(
        template_id="N1",
        priors=(
            ("H1", 0.25),
            ("H2", 0.25),
            ("H3", 0.25),
            ("H4", 0.25),
        ),
        singleton_target="H1",
        cost_sensitive=False,
    ),
    H1Template(
        template_id="N2",
        priors=(
            ("H1", 0.25),
            ("H2", 0.25),
            ("H3", 0.25),
            ("H4", 0.25),
        ),
        singleton_target="H2",
        cost_sensitive=False,
    ),
    H1Template(
        template_id="N3",
        priors=(
            ("H1", 0.25),
            ("H2", 0.25),
            ("H3", 0.25),
            ("H4", 0.25),
        ),
        singleton_target="H3",
        cost_sensitive=False,
    ),
    H1Template(
        template_id="N4",
        priors=(
            ("H1", 0.25),
            ("H2", 0.25),
            ("H3", 0.25),
            ("H4", 0.25),
        ),
        singleton_target="H4",
        cost_sensitive=False,
    ),
)


def _require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise ContractError(
            f"{name} must be non-empty text"
        )

    return value


def _template_by_id(
    template_id: str,
) -> H1Template:
    _require_text(
        template_id,
        "template_id",
    )

    for template in _TEMPLATES:
        if template.template_id == template_id:
            return template

    raise ContractError(
        f"unknown H1 template: {template_id}"
    )


def _prediction_tuple(
    *,
    pass_keys: frozenset[str],
) -> tuple[tuple[str, Verdict], ...]:
    return tuple(
        (
            key,
            (
                Verdict.PASS
                if key in pass_keys
                else Verdict.FAIL
            ),
        )
        for key in _HYPOTHESIS_KEYS
    )


def _build_experiments(
    template: H1Template,
) -> tuple[Experiment, ...]:
    singleton_cost = (
        2
        if template.cost_sensitive
        else 1
    )

    return (
        Experiment(
            key="BIT_A",
            intervention_kind=InterventionKind.REPLACE_TOOL,
            intervention_target="repair_group_a",
            cost_units=1,
            predicted_verdicts=_prediction_tuple(
                pass_keys=frozenset(
                    {
                        "H1",
                        "H2",
                    }
                )
            ),
        ),
        Experiment(
            key="BIT_B",
            intervention_kind=InterventionKind.REPLACE_TOOL,
            intervention_target="repair_group_b",
            cost_units=1,
            predicted_verdicts=_prediction_tuple(
                pass_keys=frozenset(
                    {
                        "H1",
                        "H3",
                    }
                )
            ),
        ),
        Experiment(
            key="NULL_PROBE",
            intervention_kind=InterventionKind.REPLAY,
            intervention_target="baseline_replay",
            cost_units=1,
            predicted_verdicts=_prediction_tuple(
                pass_keys=frozenset()
            ),
        ),
        Experiment(
            key="SINGLETON_PROBE",
            intervention_kind=InterventionKind.REPLACE_TOOL,
            intervention_target=(
                "repair_singleton:"
                + _HYPOTHESIS_TO_STAGE[
                    template.singleton_target
                ]
            ),
            cost_units=singleton_cost,
            predicted_verdicts=_prediction_tuple(
                pass_keys=frozenset(
                    {
                        template.singleton_target,
                    }
                )
            ),
        ),
    )


def _build_initial_trace(
    case_id: str,
) -> AgentTrace:
    event = TraceEvent(
        sequence=0,
        kind=EventKind.TERMINATION,
        component="controlled-pipeline-agent",
        operation="initial_failure",
        input_sha256=canonical_sha256(
            {
                "input": 0,
            }
        ),
        output_sha256=canonical_sha256(
            {
                "observed_output": _BASELINE_FAILED_OUTPUT,
                "expected_output": _EXPECTED_OUTPUT,
            }
        ),
        state_before_sha256=canonical_sha256(
            {
                "phase": "start",
            }
        ),
        state_after_sha256=canonical_sha256(
            {
                "phase": "failed",
            }
        ),
    )

    return AgentTrace(
        run_id=case_id,
        events=(
            event,
        ),
    )


def build_public_case(
    *,
    case_id: str,
    template_id: str,
) -> H1PublicCase:
    """Build one treatment-visible development case."""

    _require_text(
        case_id,
        "case_id",
    )

    template = _template_by_id(
        template_id
    )

    hypotheses = tuple(
        Hypothesis(
            key=key,
            description=(
                "registered controlled pipeline "
                f"fault {key}"
            ),
            prior_probability=prior,
        )
        for key, prior in template.priors
    )

    problem = DiagnosisProblem(
        trace=_build_initial_trace(
            case_id
        ),
        hypotheses=hypotheses,
        experiments=_build_experiments(
            template
        ),
        budget_units=2,
    )

    return H1PublicCase(
        case_id=case_id,
        template_id=template.template_id,
        singleton_target=template.singleton_target,
        problem=problem,
    )


def build_development_fixtures() -> tuple[H1DevelopmentFixture, ...]:
    """Return the inspectable 8-template x 4-fault development matrix."""

    fixtures = []

    for template in _TEMPLATES:
        for index, hidden_fault_key in enumerate(
            _HYPOTHESIS_KEYS,
            start=1,
        ):
            case_id = (
                "dev-"
                + template.template_id.lower()
                + f"-{index:02d}"
            )

            fixtures.append(
                H1DevelopmentFixture(
                    public_case=build_public_case(
                        case_id=case_id,
                        template_id=template.template_id,
                    ),
                    truth=H1DevelopmentTruth(
                        case_id=case_id,
                        hidden_fault_key=hidden_fault_key,
                    ),
                )
            )

    return tuple(
        fixtures
    )


def _repair_stages_for_experiment(
    public_case: H1PublicCase,
    experiment_key: str,
) -> frozenset[str]:
    if experiment_key == "BIT_A":
        return frozenset(
            {
                "stage_1",
                "stage_2",
            }
        )

    if experiment_key == "BIT_B":
        return frozenset(
            {
                "stage_1",
                "stage_3",
            }
        )

    if experiment_key == "SINGLETON_PROBE":
        return frozenset(
            {
                _HYPOTHESIS_TO_STAGE[
                    public_case.singleton_target
                ],
            }
        )

    if experiment_key == "NULL_PROBE":
        return frozenset()

    raise ContractError(
        f"unsupported H1 experiment: {experiment_key}"
    )


def _execute_pipeline(
    *,
    faulty_stage: str,
    repaired_stages: frozenset[str],
) -> int:
    """Execute the actual four-stage deterministic pipeline."""

    value = 0

    for stage in _STAGES:
        faulty_and_unrepaired = (
            stage == faulty_stage
            and stage not in repaired_stages
        )

        value += (
            2
            if faulty_and_unrepaired
            else 1
        )

    return value


def execute_development_experiment(
    *,
    public_case: H1PublicCase,
    truth: H1DevelopmentTruth,
    experiment_key: str,
) -> H1ObservedExperiment:
    """Execute one development intervention against the latent environment."""

    if not isinstance(
        public_case,
        H1PublicCase,
    ):
        raise ContractError(
            "public_case must be an H1PublicCase"
        )

    if not isinstance(
        truth,
        H1DevelopmentTruth,
    ):
        raise ContractError(
            "truth must be an H1DevelopmentTruth"
        )

    if public_case.case_id != truth.case_id:
        raise ContractError(
            "public case and development truth case IDs differ"
        )

    if truth.hidden_fault_key not in _HYPOTHESIS_TO_STAGE:
        raise ContractError(
            "unknown development hidden fault"
        )

    experiments = {
        experiment.key: experiment
        for experiment in public_case.problem.experiments
    }

    experiment = experiments.get(
        experiment_key
    )

    if experiment is None:
        raise ContractError(
            "experiment is not registered by public case"
        )

    repaired_stages = (
        _repair_stages_for_experiment(
            public_case,
            experiment_key,
        )
    )

    observed_output = _execute_pipeline(
        faulty_stage=_HYPOTHESIS_TO_STAGE[
            truth.hidden_fault_key
        ],
        repaired_stages=repaired_stages,
    )

    verdict = (
        Verdict.PASS
        if observed_output == _EXPECTED_OUTPUT
        else Verdict.FAIL
    )

    evidence_sha256 = canonical_sha256(
        {
            "record_type": "H1DevelopmentExperimentEvidence",
            "schema_version": 1,
            "case_id": public_case.case_id,
            "experiment_key": experiment.key,
            "experiment_sha256": experiment.experiment_sha256,
            "observed_output": observed_output,
            "expected_output": _EXPECTED_OUTPUT,
            "workflow_step_count": _WORKFLOW_STEP_COUNT,
        }
    )

    return H1ObservedExperiment(
        case_id=public_case.case_id,
        experiment_key=experiment.key,
        verdict=verdict,
        actual_cost_units=experiment.cost_units,
        observed_output=observed_output,
        expected_output=_EXPECTED_OUTPUT,
        workflow_step_count=_WORKFLOW_STEP_COUNT,
        evidence_sha256=evidence_sha256,
    )


def development_template_ids() -> tuple[str, ...]:
    return tuple(
        template.template_id
        for template in _TEMPLATES
    )


__all__ = [
    "H1DevelopmentFixture",
    "H1DevelopmentTruth",
    "H1ObservedExperiment",
    "H1PublicCase",
    "H1Template",
    "build_development_fixtures",
    "build_public_case",
    "development_template_ids",
    "execute_development_experiment",
]
