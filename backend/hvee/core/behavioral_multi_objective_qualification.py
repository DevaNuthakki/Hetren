from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import random

from hvee.core.behavioral_evidence_gain_planner import (
    build_behavioral_evidence_gain_planner_bundle,
)
from hvee.core.behavioral_multi_objective_engine import (
    build_behavioral_multi_objective_engine_closed_loop_step_bundle,
    build_behavioral_multi_objective_engine_observation_return_bundle,
)
from hvee.core.behavioral_multi_objective_planner_adapter import (
    build_behavioral_multi_objective_planner_adapter_bundle,
)
from hvee.core.behavioral_multi_region_search_v2_1 import (
    build_behavioral_multi_region_search_v2_1_bundle,
)
from hvee.core.behavioral_qualification_comparators import (
    BehavioralQualificationComparatorStrategy,
    run_behavioral_qualification_comparator,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
)


SCHEMA_VERSION = 1

DEVELOPMENT_NAMESPACE = "HETREN_FRESH_MULTI_OBJECTIVE_DEVELOPMENT_C52EB1B_V1"

QUALIFICATION_NAMESPACE = "HETREN_FRESH_MULTI_OBJECTIVE_QUALIFICATION_C52EB1B_V1"

DEVELOPMENT_CANDIDATE_COUNTS = (
    20,
    26,
    34,
)

QUALIFICATION_CANDIDATE_COUNTS = (
    22,
    28,
    36,
)

PROBLEMS_PER_STRATUM = 19

BASE_TOPOLOGY_FAMILIES = (
    "MONOTONIC_SINGLE_TRANSITION",
    "SINGLE_INTERIOR_REGION",
    "TWO_DISJOINT_REGIONS",
    "THREE_DISJOINT_REGIONS",
    "ALTERNATING_BANDS",
    "IRREGULAR_CLUSTERED_REGIONS",
)

TOPOLOGY_STRATA = tuple(
    item
    for family in BASE_TOPOLOGY_FAMILIES
    for item in (
        family,
        family + "_COMPLEMENT",
    )
)


class FreshQualificationPartition(str, Enum):
    DEVELOPMENT = "development"
    QUALIFICATION = "qualification"


class FreshBehavioralQualificationStrategy(str, Enum):
    HETREN_MULTI_OBJECTIVE = "sealed_hetren_multi_objective_behavioral_engine_v1"
    FARTHEST_GAP_COVERAGE = "farthest_gap_coverage"
    SEQUENTIAL_GRID = "sequential_grid"
    EVIDENCE_GAIN_V1 = "behavioral_evidence_gain_planner_v1"
    MULTI_REGION_V2_1 = "behavioral_multi_region_v2_1"
    SEEDED_RANDOM = "seeded_random"
    CURRENT_ADAPTIVE_V1 = "current_adaptive_v1"


@dataclass(frozen=True)
class FreshQualificationProblem:
    problem_key: str
    partition: str
    namespace: str
    candidate_count: int
    topology_stratum: str
    ordinal: int
    pattern: str
    topology_sha256: str
    problem_sha256: str


@dataclass(frozen=True)
class FreshQualificationTrace:
    strategy: str
    candidate_count: int
    maximum_evaluations: int
    observations: tuple[
        tuple[int, str],
        ...,
    ]
    terminal_status: str
    seed: int | None
    sha256: str

    @property
    def evaluation_count(self) -> int:
        return len(self.observations)


@dataclass(frozen=True)
class FreshQualificationScore:
    failure_region_recall_auc: float
    boundary_recall_auc: float
    discovery_auc: float
    first_failure_cost: int
    full_budget_failure_region_recall: float
    full_budget_boundary_recall: float
    evaluation_count: int
    duplicate_evaluation_count: int
    terminal_status: str
    deterministic_replay_identity: str


def _canonical_bytes(
    value: object,
) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "qualification value is not canonically JSON serializable"
        ) from exc


def _sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _evidence_sha(
    *parts: object,
) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def _seed_int(
    *parts: object,
) -> int:
    digest = hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).digest()

    return int.from_bytes(
        digest[:8],
        "big",
        signed=False,
    )


def _complement_pattern(
    pattern: str,
) -> str:
    return "".join("F" if value == "P" else "P" for value in pattern)


def _transition_count(
    pattern: str,
) -> int:
    return sum(
        left != right
        for left, right in zip(
            pattern,
            pattern[1:],
        )
    )


def _validate_pattern(
    pattern: object,
    *,
    candidate_count: int,
) -> str:
    if (
        not isinstance(
            pattern,
            str,
        )
        or len(pattern) != candidate_count
        or any(
            value
            not in (
                "P",
                "F",
            )
            for value in pattern
        )
        or "P" not in pattern
        or "F" not in pattern
    ):
        raise HveeContractError(
            "qualification pattern must be a nonconstant P/F string "
            "matching candidate_count"
        )

    return pattern


def _generate_base_patterns(
    *,
    namespace: str,
    family: str,
    candidate_count: int,
    count: int,
) -> tuple[str, ...]:
    if (
        isinstance(
            candidate_count,
            bool,
        )
        or not isinstance(
            candidate_count,
            int,
        )
        or candidate_count < 8
    ):
        raise HveeContractError(
            "qualification topology generator requires candidate_count >= 8"
        )

    if (
        isinstance(
            count,
            bool,
        )
        or not isinstance(
            count,
            int,
        )
        or count < 1
    ):
        raise HveeContractError("qualification topology count must be positive")

    if family not in BASE_TOPOLOGY_FAMILIES:
        raise HveeContractError("unsupported qualification topology family")

    if family == "MONOTONIC_SINGLE_TRANSITION":
        if count > candidate_count - 1:
            raise HveeContractError(
                "requested monotonic topology count exceeds unique limit"
            )

        transition_positions = list(
            range(
                1,
                candidate_count,
            )
        )

        random.Random(
            _seed_int(
                namespace,
                family,
                candidate_count,
                "transition_positions",
            )
        ).shuffle(transition_positions)

        return tuple(
            ("F" * transition_position + "P" * (candidate_count - transition_position))
            for transition_position in transition_positions[:count]
        )

    patterns = []
    seen = set()
    attempt = 0

    while len(patterns) < count:
        if attempt >= 200000:
            raise HveeContractError(
                "unable to generate required unique qualification topologies"
            )

        generator = random.Random(
            _seed_int(
                namespace,
                family,
                candidate_count,
                attempt,
            )
        )

        attempt += 1

        pattern = None

        if family == "SINGLE_INTERIOR_REGION":
            lower = generator.randint(
                1,
                candidate_count - 2,
            )

            upper = generator.randint(
                lower,
                candidate_count - 2,
            )

            pattern = "".join(
                "F" if lower <= index <= upper else "P"
                for index in range(candidate_count)
            )

        elif family == "TWO_DISJOINT_REGIONS":
            cuts = sorted(
                generator.sample(
                    range(
                        1,
                        candidate_count,
                    ),
                    4,
                )
            )

            a, b, c, d = cuts

            pattern = "".join(
                "F" if (a <= index < b or c <= index < d) else "P"
                for index in range(candidate_count)
            )

        elif family == "THREE_DISJOINT_REGIONS":
            cuts = sorted(
                generator.sample(
                    range(
                        1,
                        candidate_count,
                    ),
                    6,
                )
            )

            a, b, c, d, e, f = cuts

            pattern = "".join(
                "F" if (a <= index < b or c <= index < d or e <= index < f) else "P"
                for index in range(candidate_count)
            )

        elif family == "ALTERNATING_BANDS":
            maximum_width = max(
                1,
                candidate_count // 5,
            )

            pass_width = generator.randint(
                1,
                maximum_width,
            )

            fail_width = generator.randint(
                1,
                maximum_width,
            )

            cycle = pass_width + fail_width

            phase = generator.randint(
                0,
                cycle - 1,
            )

            pattern = "".join(
                ("P" if ((index + phase) % cycle) < pass_width else "F")
                for index in range(candidate_count)
            )

            if _transition_count(pattern) < 3:
                continue

        elif family == "IRREGULAR_CLUSTERED_REGIONS":
            values = []
            widths = []
            current = "P"

            while len(values) < candidate_count:
                width = generator.randint(
                    1,
                    min(
                        6,
                        candidate_count - len(values),
                    ),
                )

                widths.append(width)

                values.extend([current] * width)

                current = "F" if current == "P" else "P"

            pattern = "".join(values[:candidate_count])

            if _transition_count(pattern) < 3 or len(set(widths)) < 2:
                continue

        if pattern is None:
            raise HveeContractError("qualification topology generation failed")

        _validate_pattern(
            pattern,
            candidate_count=(candidate_count),
        )

        if pattern in seen:
            continue

        seen.add(pattern)

        patterns.append(pattern)

    return tuple(patterns)


def _generate_partition_problems(
    *,
    partition: str,
    namespace: str,
    candidate_counts: tuple[int, ...],
    problems_per_stratum: int,
) -> tuple[
    FreshQualificationProblem,
    ...,
]:
    problems = []

    for candidate_count in candidate_counts:
        for base_family in BASE_TOPOLOGY_FAMILIES:
            base_patterns = _generate_base_patterns(
                namespace=(namespace),
                family=(base_family),
                candidate_count=(candidate_count),
                count=(problems_per_stratum),
            )

            for complement in (
                False,
                True,
            ):
                stratum = base_family + ("_COMPLEMENT" if complement else "")

                stratum_topology_hashes = set()

                for ordinal, base_pattern in enumerate(base_patterns):
                    pattern = (
                        _complement_pattern(base_pattern)
                        if complement
                        else base_pattern
                    )

                    topology_sha256 = _sha256(
                        {
                            "candidate_count": (candidate_count),
                            "pattern": (pattern),
                        }
                    )

                    if topology_sha256 in stratum_topology_hashes:
                        raise HveeContractError(
                            "qualification stratum contains duplicate topology"
                        )

                    stratum_topology_hashes.add(topology_sha256)

                    problem_payload = {
                        "schema_version": (SCHEMA_VERSION),
                        "partition": (partition),
                        "namespace": (namespace),
                        "candidate_count": (candidate_count),
                        "topology_stratum": (stratum),
                        "ordinal": (ordinal),
                        "pattern": (pattern),
                        "topology_sha256": (topology_sha256),
                    }

                    problem_sha256 = _sha256(problem_payload)

                    problem_key = (
                        partition
                        + ":"
                        + str(candidate_count)
                        + ":"
                        + stratum
                        + ":"
                        + f"{ordinal:02d}"
                    )

                    problems.append(
                        FreshQualificationProblem(
                            problem_key=(problem_key),
                            partition=(partition),
                            namespace=(namespace),
                            candidate_count=(candidate_count),
                            topology_stratum=(stratum),
                            ordinal=(ordinal),
                            pattern=(pattern),
                            topology_sha256=(topology_sha256),
                            problem_sha256=(problem_sha256),
                        )
                    )

    if len({problem.problem_sha256 for problem in problems}) != len(problems):
        raise HveeContractError(
            "qualification partition contains duplicate problem identity"
        )

    return tuple(problems)


def build_fresh_behavioral_qualification_corpus(
    *,
    partition: FreshQualificationPartition,
    qualification_open_authorized: bool = False,
) -> tuple[
    FreshQualificationProblem,
    ...,
]:
    if not isinstance(
        partition,
        FreshQualificationPartition,
    ):
        raise HveeContractError("qualification partition must use strict enum")

    if partition is FreshQualificationPartition.DEVELOPMENT:
        if qualification_open_authorized:
            raise HveeContractError(
                "development generation must not receive qualification authorization"
            )

        return _generate_partition_problems(
            partition=(partition.value),
            namespace=(DEVELOPMENT_NAMESPACE),
            candidate_counts=(DEVELOPMENT_CANDIDATE_COUNTS),
            problems_per_stratum=(PROBLEMS_PER_STRATUM),
        )

    if qualification_open_authorized is not True:
        raise HveeContractError(
            "qualification corpus materialization requires explicit authorization"
        )

    return _generate_partition_problems(
        partition=(partition.value),
        namespace=(QUALIFICATION_NAMESPACE),
        candidate_counts=(QUALIFICATION_CANDIDATE_COUNTS),
        problems_per_stratum=(PROBLEMS_PER_STRATUM),
    )


def verify_fresh_behavioral_qualification_corpus(
    *,
    problems: tuple[
        FreshQualificationProblem,
        ...,
    ],
    partition: FreshQualificationPartition,
) -> bool:
    try:
        if not isinstance(
            partition,
            FreshQualificationPartition,
        ):
            return False

        if not isinstance(
            problems,
            tuple,
        ):
            return False

        expected_counts = (
            DEVELOPMENT_CANDIDATE_COUNTS
            if partition is FreshQualificationPartition.DEVELOPMENT
            else QUALIFICATION_CANDIDATE_COUNTS
        )

        expected_total = (
            len(expected_counts) * len(TOPOLOGY_STRATA) * PROBLEMS_PER_STRATUM
        )

        if len(problems) != expected_total:
            return False

        problem_hashes = set()

        grouped_topologies = {}

        for problem in problems:
            if not isinstance(
                problem,
                FreshQualificationProblem,
            ):
                return False

            if problem.partition != partition.value:
                return False

            if problem.candidate_count not in expected_counts:
                return False

            if problem.topology_stratum not in TOPOLOGY_STRATA:
                return False

            _validate_pattern(
                problem.pattern,
                candidate_count=(problem.candidate_count),
            )

            expected_topology_sha = _sha256(
                {
                    "candidate_count": (problem.candidate_count),
                    "pattern": (problem.pattern),
                }
            )

            if problem.topology_sha256 != expected_topology_sha:
                return False

            expected_problem_sha = _sha256(
                {
                    "schema_version": (SCHEMA_VERSION),
                    "partition": (problem.partition),
                    "namespace": (problem.namespace),
                    "candidate_count": (problem.candidate_count),
                    "topology_stratum": (problem.topology_stratum),
                    "ordinal": (problem.ordinal),
                    "pattern": (problem.pattern),
                    "topology_sha256": (problem.topology_sha256),
                }
            )

            if problem.problem_sha256 != expected_problem_sha:
                return False

            if problem.problem_sha256 in problem_hashes:
                return False

            problem_hashes.add(problem.problem_sha256)

            key = (
                problem.candidate_count,
                problem.topology_stratum,
            )

            grouped_topologies.setdefault(
                key,
                set(),
            )

            if problem.topology_sha256 in grouped_topologies[key]:
                return False

            grouped_topologies[key].add(problem.topology_sha256)

        if any(
            len(hashes) != PROBLEMS_PER_STRATUM
            for hashes in grouped_topologies.values()
        ):
            return False

        expected_group_count = len(expected_counts) * len(TOPOLOGY_STRATA)

        if len(grouped_topologies) != expected_group_count:
            return False

        return True

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False


def _failure_family_observation(
    *,
    problem: FreshQualificationProblem,
    strategy: str,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
) -> FailureFamilyObservation:
    return FailureFamilyObservation(
        sequence=(sequence),
        candidate_index=(candidate_index),
        verdict=(verdict),
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=_evidence_sha(
            problem.problem_sha256,
            strategy,
            "scenario",
            candidate_index,
        ),
        result_provenance_sha256=_evidence_sha(
            problem.problem_sha256,
            strategy,
            "result",
            sequence,
            candidate_index,
        ),
        observation_evidence_sha256=_evidence_sha(
            problem.problem_sha256,
            strategy,
            "observation",
            sequence,
            candidate_index,
        ),
        decision_evidence_sha256=_evidence_sha(
            problem.problem_sha256,
            strategy,
            "decision",
            sequence,
            candidate_index,
        ),
        counterexample_evidence_sha256=(
            _evidence_sha(
                problem.problem_sha256,
                strategy,
                "counterexample",
                sequence,
                candidate_index,
            )
            if verdict is DecisionVerdict.FAIL
            else None
        ),
    )


def _problem_oracle(
    problem: FreshQualificationProblem,
):
    def oracle(
        candidate_index: int,
    ) -> DecisionVerdict:
        if (
            isinstance(
                candidate_index,
                bool,
            )
            or not isinstance(
                candidate_index,
                int,
            )
            or candidate_index < 0
            or candidate_index >= problem.candidate_count
        ):
            raise HveeContractError(
                "qualification oracle candidate is outside problem grid"
            )

        return (
            DecisionVerdict.FAIL
            if problem.pattern[candidate_index] == "F"
            else DecisionVerdict.PASS
        )

    return oracle


def _trace_sha(
    *,
    strategy: str,
    candidate_count: int,
    maximum_evaluations: int,
    observations: tuple[
        tuple[int, str],
        ...,
    ],
    terminal_status: str,
    seed: int | None,
) -> str:
    return _sha256(
        {
            "strategy": (strategy),
            "candidate_count": (candidate_count),
            "maximum_evaluations": (maximum_evaluations),
            "observations": [
                [
                    candidate_index,
                    verdict,
                ]
                for candidate_index, verdict in observations
            ],
            "terminal_status": (terminal_status),
            "seed": (seed),
        }
    )


def _make_trace(
    *,
    strategy: FreshBehavioralQualificationStrategy,
    candidate_count: int,
    maximum_evaluations: int,
    observations: list[
        tuple[
            int,
            DecisionVerdict,
        ]
    ],
    terminal_status: str,
    seed: int | None,
) -> FreshQualificationTrace:
    seen = set()

    normalized = []

    for candidate_index, verdict in observations:
        if (
            candidate_index in seen
            or candidate_index < 0
            or candidate_index >= candidate_count
        ):
            raise HveeContractError(
                "qualification trace contains invalid or duplicate candidate"
            )

        seen.add(candidate_index)

        if not isinstance(
            verdict,
            DecisionVerdict,
        ) or verdict not in (
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        ):
            raise HveeContractError("qualification trace contains invalid verdict")

        normalized.append(
            (
                candidate_index,
                verdict.value,
            )
        )

    if len(normalized) > maximum_evaluations:
        raise HveeContractError("qualification trace exceeds evaluation budget")

    normalized_tuple = tuple(normalized)

    digest = _trace_sha(
        strategy=(strategy.value),
        candidate_count=(candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=(normalized_tuple),
        terminal_status=(terminal_status),
        seed=seed,
    )

    return FreshQualificationTrace(
        strategy=(strategy.value),
        candidate_count=(candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=(normalized_tuple),
        terminal_status=(terminal_status),
        seed=seed,
        sha256=(digest),
    )


def _run_generic_comparator(
    *,
    problem: FreshQualificationProblem,
    strategy: FreshBehavioralQualificationStrategy,
    maximum_evaluations: int,
    seed: int | None,
) -> FreshQualificationTrace:
    mapping = {
        FreshBehavioralQualificationStrategy.FARTHEST_GAP_COVERAGE: (
            BehavioralQualificationComparatorStrategy.FARTHEST_GAP_COVERAGE
        ),
        FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID: (
            BehavioralQualificationComparatorStrategy.SEQUENTIAL_GRID
        ),
        FreshBehavioralQualificationStrategy.SEEDED_RANDOM: (
            BehavioralQualificationComparatorStrategy.SEEDED_RANDOM
        ),
        FreshBehavioralQualificationStrategy.CURRENT_ADAPTIVE_V1: (
            BehavioralQualificationComparatorStrategy.CURRENT_ADAPTIVE_V1
        ),
    }

    comparator_trace = run_behavioral_qualification_comparator(
        strategy=(mapping[strategy]),
        candidate_count=(problem.candidate_count),
        maximum_evaluations=(maximum_evaluations),
        oracle=(_problem_oracle(problem)),
        seed=seed,
    )

    observations = [
        (
            candidate_index,
            DecisionVerdict(verdict_value),
        )
        for candidate_index, verdict_value in comparator_trace.observations
    ]

    return _make_trace(
        strategy=(strategy),
        candidate_count=(problem.candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=(observations),
        terminal_status=(comparator_trace.terminal_status),
        seed=(comparator_trace.seed),
    )


def _run_evidence_gain(
    *,
    problem: FreshQualificationProblem,
    maximum_evaluations: int,
) -> FreshQualificationTrace:
    native = []
    observations = []

    while True:
        bundle = build_behavioral_evidence_gain_planner_bundle(
            evaluation_type=("fresh_behavioral_qualification"),
            planner_key=("hetren.fresh.qualification.evidence_gain"),
            planner_version=("1.0.0"),
            boundary_key=("hetren.fresh.qualification.boundary"),
            boundary_version=("1.0.0"),
            axis_key=("synthetic.index"),
            axis_version=("1.0.0"),
            axis_unit=("index"),
            candidate_values=tuple(
                float(index) for index in range(problem.candidate_count)
            ),
            invariant_parameters={
                "qualification_problem_sha256": (problem.problem_sha256),
            },
            maximum_evaluations=(maximum_evaluations),
            observations=tuple(native),
        )

        proposal = bundle.payload["outcome"]["next_proposal"]

        terminal_status = bundle.payload["planner"]["status"]

        if proposal is None:
            return _make_trace(
                strategy=(FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1),
                candidate_count=(problem.candidate_count),
                maximum_evaluations=(maximum_evaluations),
                observations=(observations),
                terminal_status=(terminal_status),
                seed=None,
            )

        candidate_index = int(proposal["candidate_index"])

        verdict = _problem_oracle(problem)(candidate_index)

        sequence = len(native) + 1

        native.append(
            _failure_family_observation(
                problem=(problem),
                strategy=(FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1.value),
                sequence=(sequence),
                candidate_index=(candidate_index),
                verdict=(verdict),
            )
        )

        observations.append(
            (
                candidate_index,
                verdict,
            )
        )


def _run_multi_region_v2_1(
    *,
    problem: FreshQualificationProblem,
    maximum_evaluations: int,
) -> FreshQualificationTrace:
    native = []
    observations = []

    while True:
        bundle = build_behavioral_multi_region_search_v2_1_bundle(
            evaluation_type=("fresh_behavioral_qualification"),
            search_key=("hetren.fresh.qualification.multi_region_v2_1"),
            search_version=("1.0.0"),
            boundary_key=("hetren.fresh.qualification.boundary"),
            boundary_version=("1.0.0"),
            axis_key=("synthetic.index"),
            axis_version=("1.0.0"),
            axis_unit=("index"),
            candidate_values=tuple(
                float(index) for index in range(problem.candidate_count)
            ),
            invariant_parameters={
                "qualification_problem_sha256": (problem.problem_sha256),
            },
            maximum_evaluations=(maximum_evaluations),
            observations=tuple(native),
        )

        proposal = bundle.payload["outcome"]["next_proposal"]

        terminal_status = bundle.payload["search"]["status"]

        if proposal is None:
            return _make_trace(
                strategy=(FreshBehavioralQualificationStrategy.MULTI_REGION_V2_1),
                candidate_count=(problem.candidate_count),
                maximum_evaluations=(maximum_evaluations),
                observations=(observations),
                terminal_status=(terminal_status),
                seed=None,
            )

        candidate_index = int(proposal["candidate_index"])

        verdict = _problem_oracle(problem)(candidate_index)

        sequence = len(native) + 1

        native.append(
            _failure_family_observation(
                problem=(problem),
                strategy=(FreshBehavioralQualificationStrategy.MULTI_REGION_V2_1.value),
                sequence=(sequence),
                candidate_index=(candidate_index),
                verdict=(verdict),
            )
        )

        observations.append(
            (
                candidate_index,
                verdict,
            )
        )


def _run_hetren_multi_objective(
    *,
    problem: FreshQualificationProblem,
    maximum_evaluations: int,
) -> FreshQualificationTrace:
    candidate_targets = tuple(
        _evidence_sha(
            problem.problem_sha256,
            "candidate_target",
            candidate_index,
        )
        for candidate_index in range(problem.candidate_count)
    )

    adapter = build_behavioral_multi_objective_planner_adapter_bundle(
        campaign_key=("hetren.fresh.behavioral.qualification"),
        campaign_version=("1.0.0"),
        subject_sha256=(problem.problem_sha256),
        axis_key=("synthetic.index"),
        axis_version=("1.0.0"),
        axis_unit=("index"),
        candidate_values=tuple(
            float(index) for index in range(problem.candidate_count)
        ),
        candidate_target_sha256s=(candidate_targets),
        maximum_evaluations=(maximum_evaluations),
        observations=(),
    )

    observations = []

    while True:
        status = adapter.payload["adapter"]["status"]

        if status != "ready":
            return _make_trace(
                strategy=(FreshBehavioralQualificationStrategy.HETREN_MULTI_OBJECTIVE),
                candidate_count=(problem.candidate_count),
                maximum_evaluations=(maximum_evaluations),
                observations=(observations),
                terminal_status=(status),
                seed=None,
            )

        selected_candidate_index = int(
            adapter.payload["planner_decision"]["selected_candidate_index"]
        )

        verdict = _problem_oracle(problem)(selected_candidate_index)

        sequence = len(observations) + 1

        result_sha = _evidence_sha(
            problem.problem_sha256,
            "hetren",
            "result",
            sequence,
            selected_candidate_index,
        )

        observation_sha = _evidence_sha(
            problem.problem_sha256,
            "hetren",
            "observation",
            sequence,
            selected_candidate_index,
        )

        decision_sha = _evidence_sha(
            problem.problem_sha256,
            "hetren",
            "decision",
            sequence,
            selected_candidate_index,
        )

        counterexample_sha = (
            _evidence_sha(
                problem.problem_sha256,
                "hetren",
                "counterexample",
                sequence,
                selected_candidate_index,
            )
            if verdict is DecisionVerdict.FAIL
            else None
        )

        returned = build_behavioral_multi_objective_engine_observation_return_bundle(
            adapter_bundle=(adapter),
            verdict=(verdict),
            result_provenance_sha256=(result_sha),
            observation_evidence_sha256=(observation_sha),
            decision_evidence_sha256=(decision_sha),
            counterexample_evidence_sha256=(counterexample_sha),
            actual_cost_units=1,
        )

        step = build_behavioral_multi_objective_engine_closed_loop_step_bundle(
            adapter_bundle=(adapter),
            observation_return_bundle=(returned),
        )

        observations.append(
            (
                selected_candidate_index,
                verdict,
            )
        )

        adapter = step.advanced_adapter_bundle


def run_fresh_behavioral_qualification_strategy(
    *,
    problem: FreshQualificationProblem,
    strategy: FreshBehavioralQualificationStrategy,
    maximum_evaluations: int | None = None,
    seed: int | None = None,
) -> FreshQualificationTrace:
    if not isinstance(
        problem,
        FreshQualificationProblem,
    ):
        raise HveeContractError(
            "qualification strategy requires FreshQualificationProblem"
        )

    if not isinstance(
        strategy,
        FreshBehavioralQualificationStrategy,
    ):
        raise HveeContractError("qualification strategy must use strict enum")

    _validate_pattern(
        problem.pattern,
        candidate_count=(problem.candidate_count),
    )

    if maximum_evaluations is None:
        maximum_evaluations = problem.candidate_count

    if (
        isinstance(
            maximum_evaluations,
            bool,
        )
        or not isinstance(
            maximum_evaluations,
            int,
        )
        or maximum_evaluations < 1
        or maximum_evaluations > problem.candidate_count
    ):
        raise HveeContractError("qualification maximum_evaluations is invalid")

    generic = {
        FreshBehavioralQualificationStrategy.FARTHEST_GAP_COVERAGE,
        FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID,
        FreshBehavioralQualificationStrategy.SEEDED_RANDOM,
        FreshBehavioralQualificationStrategy.CURRENT_ADAPTIVE_V1,
    }

    if strategy in generic:
        return _run_generic_comparator(
            problem=(problem),
            strategy=(strategy),
            maximum_evaluations=(maximum_evaluations),
            seed=seed,
        )

    if seed is not None:
        raise HveeContractError("only seeded-random strategy accepts a seed")

    if strategy is FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1:
        return _run_evidence_gain(
            problem=(problem),
            maximum_evaluations=(maximum_evaluations),
        )

    if strategy is FreshBehavioralQualificationStrategy.MULTI_REGION_V2_1:
        return _run_multi_region_v2_1(
            problem=(problem),
            maximum_evaluations=(maximum_evaluations),
        )

    if strategy is FreshBehavioralQualificationStrategy.HETREN_MULTI_OBJECTIVE:
        return _run_hetren_multi_objective(
            problem=(problem),
            maximum_evaluations=(maximum_evaluations),
        )

    raise HveeContractError("unsupported qualification strategy")


def _true_failure_regions(
    pattern: str,
) -> tuple[
    tuple[int, int],
    ...,
]:
    regions = []

    index = 0

    while index < len(pattern):
        if pattern[index] != "F":
            index += 1
            continue

        lower = index

        while index + 1 < len(pattern) and pattern[index + 1] == "F":
            index += 1

        regions.append(
            (
                lower,
                index,
            )
        )

        index += 1

    return tuple(regions)


def _true_boundaries(
    pattern: str,
) -> tuple[
    tuple[int, int],
    ...,
]:
    return tuple(
        (
            index,
            index + 1,
        )
        for index in range(len(pattern) - 1)
        if pattern[index] != pattern[index + 1]
    )


def _maximum_boundary_count_by_prefix(
    *,
    candidate_count: int,
    boundaries: tuple[
        tuple[int, int],
        ...,
    ],
) -> tuple[int, ...]:
    boundary_set = set(boundaries)

    dynamic = {
        (
            0,
            0,
        ): 0
    }

    for candidate_index in range(candidate_count):
        next_dynamic = {}

        for (
            selected_count,
            previous_selected,
        ), score in dynamic.items():
            not_selected_key = (
                selected_count,
                0,
            )

            next_dynamic[not_selected_key] = max(
                next_dynamic.get(
                    not_selected_key,
                    -1,
                ),
                score,
            )

            added = (
                1
                if (
                    previous_selected
                    and candidate_index > 0
                    and (
                        candidate_index - 1,
                        candidate_index,
                    )
                    in boundary_set
                )
                else 0
            )

            selected_key = (
                selected_count + 1,
                1,
            )

            next_dynamic[selected_key] = max(
                next_dynamic.get(
                    selected_key,
                    -1,
                ),
                score + added,
            )

        dynamic = next_dynamic

    result = []

    for selected_count in range(candidate_count + 1):
        values = [
            score
            for (
                count,
                _previous_selected,
            ), score in dynamic.items()
            if count == selected_count
        ]

        result.append(max(values) if values else 0)

    return tuple(result)


def _trapezoid_area(
    values: tuple[
        float,
        ...,
    ],
) -> float:
    if len(values) < 2:
        raise HveeContractError("qualification AUC requires at least two prefix values")

    denominator = len(values) - 1

    return (
        sum((values[index] + values[index + 1]) / 2.0 for index in range(denominator))
        / denominator
    )


def _normalized_auc(
    *,
    observed: tuple[
        float,
        ...,
    ],
    maximum: tuple[
        float,
        ...,
    ],
) -> float:
    if len(observed) != len(maximum):
        raise HveeContractError(
            "observed and maximum AUC curves must have equal length"
        )

    observed_area = _trapezoid_area(observed)

    maximum_area = _trapezoid_area(maximum)

    if maximum_area <= 0.0:
        return 1.0

    value = observed_area / maximum_area

    if not math.isfinite(value) or value < -1e-12 or value > 1.0 + 1e-12:
        raise HveeContractError("normalized qualification AUC is outside [0,1]")

    return min(
        1.0,
        max(
            0.0,
            value,
        ),
    )


def score_fresh_behavioral_qualification_trace(
    *,
    problem: FreshQualificationProblem,
    trace: FreshQualificationTrace,
) -> FreshQualificationScore:
    if trace.candidate_count != problem.candidate_count:
        raise HveeContractError("qualification trace candidate count mismatch")

    if trace.maximum_evaluations > problem.candidate_count:
        raise HveeContractError("qualification trace budget exceeds problem grid")

    expected_trace_sha = _trace_sha(
        strategy=(trace.strategy),
        candidate_count=(trace.candidate_count),
        maximum_evaluations=(trace.maximum_evaluations),
        observations=(trace.observations),
        terminal_status=(trace.terminal_status),
        seed=(trace.seed),
    )

    if trace.sha256 != expected_trace_sha:
        raise HveeContractError("qualification trace identity mismatch")

    seen = set()

    validated = []

    for candidate_index, verdict_value in trace.observations:
        if (
            candidate_index in seen
            or candidate_index < 0
            or candidate_index >= problem.candidate_count
        ):
            raise HveeContractError(
                "qualification trace contains duplicate or invalid candidate"
            )

        seen.add(candidate_index)

        try:
            verdict = DecisionVerdict(verdict_value)

        except ValueError as exc:
            raise HveeContractError(
                "qualification trace contains invalid verdict"
            ) from exc

        expected = (
            DecisionVerdict.FAIL
            if problem.pattern[candidate_index] == "F"
            else DecisionVerdict.PASS
        )

        if verdict != expected:
            raise HveeContractError(
                "qualification trace verdict disagrees with ground truth"
            )

        validated.append(
            (
                candidate_index,
                verdict,
            )
        )

    duplicate_count = len(trace.observations) - len(seen)

    regions = _true_failure_regions(problem.pattern)

    boundaries = _true_boundaries(problem.pattern)

    if not regions:
        raise HveeContractError(
            "qualification problem must contain at least one failure region"
        )

    if not boundaries:
        raise HveeContractError(
            "qualification problem must contain at least one boundary"
        )

    candidate_count = problem.candidate_count

    region_curve = [0.0]

    boundary_curve = [0.0]

    discovery_curve = [0.0]

    observed_map = {}

    first_failure_cost = candidate_count + 1

    for sequence in range(
        1,
        candidate_count + 1,
    ):
        if sequence <= len(validated):
            candidate_index, verdict = validated[sequence - 1]

            observed_map[candidate_index] = verdict

            if (
                verdict is DecisionVerdict.FAIL
                and first_failure_cost == candidate_count + 1
            ):
                first_failure_cost = sequence

        touched_regions = sum(
            any(
                lower <= candidate_index <= upper and verdict is DecisionVerdict.FAIL
                for candidate_index, verdict in observed_map.items()
            )
            for lower, upper in regions
        )

        region_curve.append(touched_regions / len(regions))

        observed_boundaries = sum(
            (lower in observed_map and upper in observed_map)
            for lower, upper in boundaries
        )

        boundary_curve.append(observed_boundaries / len(boundaries))

        discovery_curve.append(
            1.0
            if any(verdict is DecisionVerdict.FAIL for verdict in observed_map.values())
            else 0.0
        )

    maximum_region_curve = tuple(
        (
            0.0
            if prefix == 0
            else min(
                prefix,
                len(regions),
            )
            / len(regions)
        )
        for prefix in range(candidate_count + 1)
    )

    maximum_boundary_counts = _maximum_boundary_count_by_prefix(
        candidate_count=(candidate_count),
        boundaries=(boundaries),
    )

    maximum_boundary_curve = tuple(
        (count / len(boundaries)) for count in maximum_boundary_counts
    )

    maximum_discovery_curve = tuple(
        0.0 if prefix == 0 else 1.0 for prefix in range(candidate_count + 1)
    )

    return FreshQualificationScore(
        failure_region_recall_auc=(
            _normalized_auc(
                observed=tuple(region_curve),
                maximum=(maximum_region_curve),
            )
        ),
        boundary_recall_auc=(
            _normalized_auc(
                observed=tuple(boundary_curve),
                maximum=(maximum_boundary_curve),
            )
        ),
        discovery_auc=(
            _normalized_auc(
                observed=tuple(discovery_curve),
                maximum=(maximum_discovery_curve),
            )
        ),
        first_failure_cost=(first_failure_cost),
        full_budget_failure_region_recall=(region_curve[-1]),
        full_budget_boundary_recall=(boundary_curve[-1]),
        evaluation_count=(len(validated)),
        duplicate_evaluation_count=(duplicate_count),
        terminal_status=(trace.terminal_status),
        deterministic_replay_identity=(trace.sha256),
    )


__all__ = [
    "BASE_TOPOLOGY_FAMILIES",
    "DEVELOPMENT_CANDIDATE_COUNTS",
    "DEVELOPMENT_NAMESPACE",
    "FreshBehavioralQualificationStrategy",
    "FreshQualificationPartition",
    "FreshQualificationProblem",
    "FreshQualificationScore",
    "FreshQualificationTrace",
    "PROBLEMS_PER_STRATUM",
    "QUALIFICATION_CANDIDATE_COUNTS",
    "QUALIFICATION_NAMESPACE",
    "TOPOLOGY_STRATA",
    "build_fresh_behavioral_qualification_corpus",
    "run_fresh_behavioral_qualification_strategy",
    "score_fresh_behavioral_qualification_trace",
    "verify_fresh_behavioral_qualification_corpus",
]
