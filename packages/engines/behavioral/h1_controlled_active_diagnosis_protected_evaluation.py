"""Evaluator-only scoring for the P09.3 H1 controlled experiment.

This module scores an already-completed treatment batch.

It does not execute experiments and does not create environment observations.
The evaluator truth mapping is supplied only after treatment results exist.

Normal unfavorable outcomes remain in the denominator:

- wrong specific diagnosis;
- INCONCLUSIVE;
- BUDGET_EXHAUSTED.

Malformed or incomplete treatment/evaluator inputs raise ContractError rather
than being silently replaced, dropped, or converted into favorable outcomes.

This module performs no filesystem I/O.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import json
import re

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    canonical_sha256,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis import (
    H1Arm,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis_protected_execution import (
    H1ProtectedTreatmentBatch,
    H1ProtectedTreatmentRecord,
)


_SHA256 = re.compile(
    r"^[0-9a-f]{64}$"
)

_EPSILON = 1e-12

_PRIMARY_MINIMUM_DELTA = 0.25
_PRIMARY_MAXIMUM_FALSE_SPECIFIC_INCREASE = 0.02

_SELECTION_POLICY_MINIMUM_DELTA = 0.10

_COST_AWARE_MINIMUM_COST_SENSITIVE_DELTA = 0.20
_COST_AWARE_MAXIMUM_NEUTRAL_ABSOLUTE_DELTA = 0.05


class H1DiagnosisOutcome(
    str,
    Enum,
):
    CORRECT_SPECIFIC_DIAGNOSIS = (
        "correct_specific_diagnosis"
    )
    FALSE_SPECIFIC_DIAGNOSIS = (
        "false_specific_diagnosis"
    )
    INCONCLUSIVE = "inconclusive"
    BUDGET_EXHAUSTED = (
        "budget_exhausted"
    )


@dataclass(frozen=True)
class H1ScoredTreatmentRecord:
    case_id: str
    template_id: str
    arm: str
    outcome: H1DiagnosisOutcome

    def to_payload(
        self,
    ) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "template_id": self.template_id,
            "arm": self.arm,
            "outcome": self.outcome.value,
        }


@dataclass(frozen=True)
class H1MetricSlice:
    group: str
    arm: str
    denominator: int
    correct_specific_count: int
    false_specific_count: int
    inconclusive_count: int
    budget_exhausted_count: int
    total_declared_cost_units: int
    total_actual_cost_units: int
    total_experiment_count: int
    total_workflow_step_count: int

    @property
    def correct_specific_rate(
        self,
    ) -> float:
        return (
            self.correct_specific_count
            / self.denominator
        )

    @property
    def false_specific_rate(
        self,
    ) -> float:
        return (
            self.false_specific_count
            / self.denominator
        )

    def to_payload(
        self,
    ) -> dict[str, object]:
        return {
            "group": self.group,
            "arm": self.arm,
            "denominator": self.denominator,
            "correct_specific_count": self.correct_specific_count,
            "correct_specific_rate": self.correct_specific_rate,
            "false_specific_count": self.false_specific_count,
            "false_specific_rate": self.false_specific_rate,
            "inconclusive_count": self.inconclusive_count,
            "budget_exhausted_count": self.budget_exhausted_count,
            "total_declared_cost_units": self.total_declared_cost_units,
            "total_actual_cost_units": self.total_actual_cost_units,
            "total_experiment_count": self.total_experiment_count,
            "total_workflow_step_count": self.total_workflow_step_count,
        }


@dataclass(frozen=True)
class H1PairedComparison:
    comparison_id: str
    group: str
    comparator_arm: str
    target_arm: str
    denominator: int
    both_correct_count: int
    target_only_correct_count: int
    comparator_only_correct_count: int
    neither_correct_count: int
    target_minus_comparator_rate: float

    def to_payload(
        self,
    ) -> dict[str, object]:
        return {
            "comparison_id": self.comparison_id,
            "group": self.group,
            "comparator_arm": self.comparator_arm,
            "target_arm": self.target_arm,
            "denominator": self.denominator,
            "both_correct_count": self.both_correct_count,
            "target_only_correct_count": self.target_only_correct_count,
            "comparator_only_correct_count": self.comparator_only_correct_count,
            "neither_correct_count": self.neither_correct_count,
            "target_minus_comparator_rate": self.target_minus_comparator_rate,
        }


@dataclass(frozen=True)
class H1TemplateFaultMetric:
    """Evaluator-only aggregate; never a case-to-fault mapping."""

    template_id: str
    hidden_fault_key: str
    arm: str
    denominator: int
    correct_specific_count: int
    false_specific_count: int
    inconclusive_count: int
    budget_exhausted_count: int

    def to_payload(
        self,
    ) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "hidden_fault_key": self.hidden_fault_key,
            "arm": self.arm,
            "denominator": self.denominator,
            "correct_specific_count": self.correct_specific_count,
            "false_specific_count": self.false_specific_count,
            "inconclusive_count": self.inconclusive_count,
            "budget_exhausted_count": self.budget_exhausted_count,
        }


@dataclass(frozen=True)
class H1RegisteredCriteriaDecision:
    """Mechanical preregistered threshold evaluation."""

    primary_c3_minus_c0: float
    c0_false_specific_rate: float
    c3_false_specific_rate: float
    primary_h1_criteria_met: bool

    cost_sensitive_c3_minus_c1: float
    selection_policy_bound_met: bool

    cost_sensitive_c3_minus_c2: float
    neutral_c3_minus_c2: float
    cost_aware_bound_met: bool

    def to_payload(
        self,
    ) -> dict[str, object]:
        return {
            "primary_c3_minus_c0": self.primary_c3_minus_c0,
            "c0_false_specific_rate": self.c0_false_specific_rate,
            "c3_false_specific_rate": self.c3_false_specific_rate,
            "primary_h1_criteria_met": self.primary_h1_criteria_met,
            "cost_sensitive_c3_minus_c1": self.cost_sensitive_c3_minus_c1,
            "selection_policy_bound_met": self.selection_policy_bound_met,
            "cost_sensitive_c3_minus_c2": self.cost_sensitive_c3_minus_c2,
            "neutral_c3_minus_c2": self.neutral_c3_minus_c2,
            "cost_aware_bound_met": self.cost_aware_bound_met,
        }


@dataclass(frozen=True)
class H1ProtectedEvaluation:
    batch_id: str
    treatment_batch_sha256: str
    hidden_manifest_sha256: str
    scored_records: tuple[
        H1ScoredTreatmentRecord,
        ...,
    ]
    metric_slices: tuple[
        H1MetricSlice,
        ...,
    ]
    paired_comparisons: tuple[
        H1PairedComparison,
        ...,
    ]
    template_fault_metrics: tuple[
        H1TemplateFaultMetric,
        ...,
    ]
    registered_criteria: H1RegisteredCriteriaDecision

    @property
    def evaluation_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.to_payload()
        )

    @property
    def canonical_json_bytes(
        self,
    ) -> bytes:
        return json.dumps(
            self.to_payload(),
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=False,
            allow_nan=False,
        ).encode(
            "utf-8"
        )

    def to_payload(
        self,
    ) -> dict[str, object]:
        return {
            "record_type": "H1ProtectedEvaluation",
            "schema_version": 1,
            "batch_id": self.batch_id,
            "treatment_batch_sha256": self.treatment_batch_sha256,
            "hidden_manifest_sha256": self.hidden_manifest_sha256,
            "scored_records": [
                record.to_payload()
                for record
                in self.scored_records
            ],
            "metric_slices": [
                metric.to_payload()
                for metric
                in self.metric_slices
            ],
            "paired_comparisons": [
                comparison.to_payload()
                for comparison
                in self.paired_comparisons
            ],
            "template_fault_metrics": [
                metric.to_payload()
                for metric
                in self.template_fault_metrics
            ],
            "registered_criteria": self.registered_criteria.to_payload(),
        }


def _require_sha256(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _SHA256.fullmatch(
            value
        ) is None
    ):
        raise ContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _group_for_template(
    template_id: str,
) -> str:
    if template_id.startswith(
        "T"
    ):
        return "cost_sensitive"

    if template_id.startswith(
        "N"
    ):
        return "neutral"

    raise ContractError(
        "unknown protected template family"
    )


def _score_record(
    *,
    record: H1ProtectedTreatmentRecord,
    hidden_fault_key: str,
) -> H1DiagnosisOutcome:
    if hidden_fault_key not in {
        "H1",
        "H2",
        "H3",
        "H4",
    }:
        raise ContractError(
            "unknown evaluator hidden fault"
        )

    if (
        record.status
        == DiagnosisStatus.DIAGNOSED.value
    ):
        if (
            record.diagnosed_hypothesis_key
            == hidden_fault_key
        ):
            return (
                H1DiagnosisOutcome
                .CORRECT_SPECIFIC_DIAGNOSIS
            )

        return (
            H1DiagnosisOutcome
            .FALSE_SPECIFIC_DIAGNOSIS
        )

    if (
        record.status
        == DiagnosisStatus.INCONCLUSIVE.value
    ):
        return H1DiagnosisOutcome.INCONCLUSIVE

    if (
        record.status
        == DiagnosisStatus.BUDGET_EXHAUSTED.value
    ):
        return (
            H1DiagnosisOutcome
            .BUDGET_EXHAUSTED
        )

    raise ContractError(
        "unexpected treatment terminal status"
    )


def _case_metadata(
    treatment_batch: H1ProtectedTreatmentBatch,
) -> dict[
    str,
    str,
]:
    result = {}

    for record in treatment_batch.records:
        existing = result.get(
            record.case_id
        )

        if (
            existing is not None
            and existing
            != record.template_id
        ):
            raise ContractError(
                "case template differs across treatment arms"
            )

        result[
            record.case_id
        ] = record.template_id

    return result


def _metric_slice(
    *,
    group: str,
    arm: str,
    treatment_batch: H1ProtectedTreatmentBatch,
    scored_by_key: Mapping[
        tuple[
            str,
            str,
        ],
        H1ScoredTreatmentRecord,
    ],
) -> H1MetricSlice:
    records = []

    for record in treatment_batch.records:
        if record.arm != arm:
            continue

        if group != "overall":
            if (
                _group_for_template(
                    record.template_id
                )
                != group
            ):
                continue

        records.append(
            record
        )

    if not records:
        raise ContractError(
            "metric slice has zero denominator"
        )

    outcomes = [
        scored_by_key[
            (
                record.case_id,
                record.arm,
            )
        ].outcome
        for record
        in records
    ]

    return H1MetricSlice(
        group=group,
        arm=arm,
        denominator=len(
            records
        ),
        correct_specific_count=sum(
            outcome
            is H1DiagnosisOutcome
            .CORRECT_SPECIFIC_DIAGNOSIS
            for outcome
            in outcomes
        ),
        false_specific_count=sum(
            outcome
            is H1DiagnosisOutcome
            .FALSE_SPECIFIC_DIAGNOSIS
            for outcome
            in outcomes
        ),
        inconclusive_count=sum(
            outcome
            is H1DiagnosisOutcome
            .INCONCLUSIVE
            for outcome
            in outcomes
        ),
        budget_exhausted_count=sum(
            outcome
            is H1DiagnosisOutcome
            .BUDGET_EXHAUSTED
            for outcome
            in outcomes
        ),
        total_declared_cost_units=sum(
            record.declared_cost_units
            for record
            in records
        ),
        total_actual_cost_units=sum(
            record.actual_cost_units
            for record
            in records
        ),
        total_experiment_count=sum(
            record.experiment_count
            for record
            in records
        ),
        total_workflow_step_count=sum(
            record.workflow_step_count
            for record
            in records
        ),
    )


def _paired_comparison(
    *,
    comparison_id: str,
    group: str,
    comparator_arm: str,
    target_arm: str,
    treatment_batch: H1ProtectedTreatmentBatch,
    scored_by_key: Mapping[
        tuple[
            str,
            str,
        ],
        H1ScoredTreatmentRecord,
    ],
) -> H1PairedComparison:
    case_metadata = _case_metadata(
        treatment_batch
    )

    case_ids = []

    for case_id, template_id in sorted(
        case_metadata.items()
    ):
        if (
            group != "overall"
            and _group_for_template(
                template_id
            )
            != group
        ):
            continue

        case_ids.append(
            case_id
        )

    if not case_ids:
        raise ContractError(
            "paired comparison has zero denominator"
        )

    both = 0
    target_only = 0
    comparator_only = 0
    neither = 0

    for case_id in case_ids:
        comparator = scored_by_key[
            (
                case_id,
                comparator_arm,
            )
        ].outcome

        target = scored_by_key[
            (
                case_id,
                target_arm,
            )
        ].outcome

        comparator_correct = (
            comparator
            is H1DiagnosisOutcome
            .CORRECT_SPECIFIC_DIAGNOSIS
        )

        target_correct = (
            target
            is H1DiagnosisOutcome
            .CORRECT_SPECIFIC_DIAGNOSIS
        )

        if (
            target_correct
            and comparator_correct
        ):
            both += 1

        elif (
            target_correct
            and not comparator_correct
        ):
            target_only += 1

        elif (
            comparator_correct
            and not target_correct
        ):
            comparator_only += 1

        else:
            neither += 1

    denominator = len(
        case_ids
    )

    difference = (
        target_only
        - comparator_only
    ) / denominator

    return H1PairedComparison(
        comparison_id=comparison_id,
        group=group,
        comparator_arm=comparator_arm,
        target_arm=target_arm,
        denominator=denominator,
        both_correct_count=both,
        target_only_correct_count=target_only,
        comparator_only_correct_count=comparator_only,
        neither_correct_count=neither,
        target_minus_comparator_rate=difference,
    )


def _template_fault_metrics(
    *,
    treatment_batch: H1ProtectedTreatmentBatch,
    hidden_truth_by_case: Mapping[
        str,
        str,
    ],
    scored_by_key: Mapping[
        tuple[
            str,
            str,
        ],
        H1ScoredTreatmentRecord,
    ],
) -> tuple[
    H1TemplateFaultMetric,
    ...,
]:
    grouped: dict[
        tuple[
            str,
            str,
            str,
        ],
        list[
            H1DiagnosisOutcome
        ],
    ] = defaultdict(
        list
    )

    for record in treatment_batch.records:
        hidden_fault = hidden_truth_by_case[
            record.case_id
        ]

        scored = scored_by_key[
            (
                record.case_id,
                record.arm,
            )
        ]

        grouped[
            (
                record.template_id,
                hidden_fault,
                record.arm,
            )
        ].append(
            scored.outcome
        )

    metrics = []

    for (
        template_id,
        hidden_fault,
        arm,
    ), outcomes in sorted(
        grouped.items()
    ):
        metrics.append(
            H1TemplateFaultMetric(
                template_id=template_id,
                hidden_fault_key=hidden_fault,
                arm=arm,
                denominator=len(
                    outcomes
                ),
                correct_specific_count=sum(
                    outcome
                    is H1DiagnosisOutcome
                    .CORRECT_SPECIFIC_DIAGNOSIS
                    for outcome
                    in outcomes
                ),
                false_specific_count=sum(
                    outcome
                    is H1DiagnosisOutcome
                    .FALSE_SPECIFIC_DIAGNOSIS
                    for outcome
                    in outcomes
                ),
                inconclusive_count=sum(
                    outcome
                    is H1DiagnosisOutcome
                    .INCONCLUSIVE
                    for outcome
                    in outcomes
                ),
                budget_exhausted_count=sum(
                    outcome
                    is H1DiagnosisOutcome
                    .BUDGET_EXHAUSTED
                    for outcome
                    in outcomes
                ),
            )
        )

    return tuple(
        metrics
    )


def _parse_hidden_manifest(
    *,
    hidden_manifest: Mapping[
        str,
        object,
    ],
    expected_hidden_manifest_sha256: str,
    expected_batch_id: str,
) -> dict[
    str,
    str,
]:
    if not isinstance(
        hidden_manifest,
        Mapping,
    ):
        raise ContractError(
            "hidden_manifest must be a mapping"
        )

    _require_sha256(
        expected_hidden_manifest_sha256,
        "expected_hidden_manifest_sha256",
    )

    actual_sha256 = canonical_sha256(
        hidden_manifest
    )

    if (
        actual_sha256
        != expected_hidden_manifest_sha256
    ):
        raise ContractError(
            "hidden manifest does not match frozen expected SHA-256"
        )

    if (
        hidden_manifest.get(
            "record_type"
        )
        != "H1HiddenTruthManifest"
    ):
        raise ContractError(
            "unexpected hidden manifest record type"
        )

    if (
        hidden_manifest.get(
            "schema_version"
        )
        != 1
    ):
        raise ContractError(
            "unexpected hidden manifest schema version"
        )

    if (
        hidden_manifest.get(
            "batch_id"
        )
        != expected_batch_id
    ):
        raise ContractError(
            "hidden manifest batch ID does not match treatment batch"
        )

    assignments = hidden_manifest.get(
        "assignments"
    )

    if not isinstance(
        assignments,
        list,
    ):
        raise ContractError(
            "hidden manifest assignments must be a list"
        )

    truth_by_case = {}

    for index, assignment in enumerate(
        assignments
    ):
        if not isinstance(
            assignment,
            Mapping,
        ):
            raise ContractError(
                f"hidden assignment {index} must be a mapping"
            )

        if set(
            assignment
        ) != {
            "case_id",
            "hidden_fault_key",
        }:
            raise ContractError(
                "hidden assignment fields differ from frozen schema"
            )

        case_id = assignment[
            "case_id"
        ]

        hidden_fault = assignment[
            "hidden_fault_key"
        ]

        if (
            not isinstance(
                case_id,
                str,
            )
            or not case_id
        ):
            raise ContractError(
                "hidden assignment case ID must be non-empty text"
            )

        if hidden_fault not in {
            "H1",
            "H2",
            "H3",
            "H4",
        }:
            raise ContractError(
                "evaluator truth contains unknown hidden fault"
            )

        if case_id in truth_by_case:
            raise ContractError(
                "hidden manifest contains duplicate case ID"
            )

        truth_by_case[
            case_id
        ] = hidden_fault

    return truth_by_case


def evaluate_treatment_batch(
    *,
    treatment_batch: H1ProtectedTreatmentBatch,
    hidden_manifest: Mapping[
        str,
        object,
    ],
    expected_hidden_manifest_sha256: str,
) -> H1ProtectedEvaluation:
    """Score a completed treatment batch against evaluator truth."""

    if not isinstance(
        treatment_batch,
        H1ProtectedTreatmentBatch,
    ):
        raise ContractError(
            "treatment_batch must be an H1ProtectedTreatmentBatch"
        )

    hidden_truth_by_case = _parse_hidden_manifest(
        hidden_manifest=hidden_manifest,
        expected_hidden_manifest_sha256=(
            expected_hidden_manifest_sha256
        ),
        expected_batch_id=(
            treatment_batch.batch_id
        ),
    )

    case_ids = set(
        treatment_batch.case_ids
    )

    truth_case_ids = set(
        hidden_truth_by_case
    )

    missing = (
        case_ids
        - truth_case_ids
    )

    extra = (
        truth_case_ids
        - case_ids
    )

    if missing:
        raise ContractError(
            "evaluator truth is missing treatment cases"
        )

    if extra:
        raise ContractError(
            "evaluator truth contains extra cases"
        )

    scored_records = []

    for record in treatment_batch.records:
        outcome = _score_record(
            record=record,
            hidden_fault_key=(
                hidden_truth_by_case[
                    record.case_id
                ]
            ),
        )

        scored_records.append(
            H1ScoredTreatmentRecord(
                case_id=record.case_id,
                template_id=record.template_id,
                arm=record.arm,
                outcome=outcome,
            )
        )

    scored_records = tuple(
        scored_records
    )

    scored_by_key = {
        (
            record.case_id,
            record.arm,
        ): record
        for record
        in scored_records
    }

    metric_slices = tuple(
        _metric_slice(
            group=group,
            arm=arm.value,
            treatment_batch=treatment_batch,
            scored_by_key=scored_by_key,
        )
        for group in (
            "overall",
            "cost_sensitive",
            "neutral",
        )
        for arm in H1Arm
    )

    metrics_by_key = {
        (
            metric.group,
            metric.arm,
        ): metric
        for metric
        in metric_slices
    }

    c0 = H1Arm.TRACE_ONLY.value
    c1 = H1Arm.SEEDED_RANDOM_ACTIVE.value
    c2 = H1Arm.MAX_INFORMATION_GAIN_ACTIVE.value
    c3 = H1Arm.HEAL_INFORMATION_GAIN_PER_COST.value

    paired_comparisons = (
        _paired_comparison(
            comparison_id="c3_vs_c0_overall",
            group="overall",
            comparator_arm=c0,
            target_arm=c3,
            treatment_batch=treatment_batch,
            scored_by_key=scored_by_key,
        ),
        _paired_comparison(
            comparison_id="c3_vs_c1_cost_sensitive",
            group="cost_sensitive",
            comparator_arm=c1,
            target_arm=c3,
            treatment_batch=treatment_batch,
            scored_by_key=scored_by_key,
        ),
        _paired_comparison(
            comparison_id="c3_vs_c2_cost_sensitive",
            group="cost_sensitive",
            comparator_arm=c2,
            target_arm=c3,
            treatment_batch=treatment_batch,
            scored_by_key=scored_by_key,
        ),
        _paired_comparison(
            comparison_id="c3_vs_c2_neutral",
            group="neutral",
            comparator_arm=c2,
            target_arm=c3,
            treatment_batch=treatment_batch,
            scored_by_key=scored_by_key,
        ),
    )

    comparisons_by_id = {
        comparison.comparison_id:
            comparison
        for comparison
        in paired_comparisons
    }

    primary = comparisons_by_id[
        "c3_vs_c0_overall"
    ]

    selection = comparisons_by_id[
        "c3_vs_c1_cost_sensitive"
    ]

    cost_sensitive = comparisons_by_id[
        "c3_vs_c2_cost_sensitive"
    ]

    neutral = comparisons_by_id[
        "c3_vs_c2_neutral"
    ]

    c0_overall = metrics_by_key[
        (
            "overall",
            c0,
        )
    ]

    c3_overall = metrics_by_key[
        (
            "overall",
            c3,
        )
    ]

    primary_met = (
        primary.target_minus_comparator_rate
        + _EPSILON
        >= _PRIMARY_MINIMUM_DELTA
        and c3_overall.false_specific_rate
        <= (
            c0_overall.false_specific_rate
            + _PRIMARY_MAXIMUM_FALSE_SPECIFIC_INCREASE
            + _EPSILON
        )
    )

    selection_met = (
        selection.target_minus_comparator_rate
        + _EPSILON
        >= _SELECTION_POLICY_MINIMUM_DELTA
    )

    cost_aware_met = (
        cost_sensitive.target_minus_comparator_rate
        + _EPSILON
        >= _COST_AWARE_MINIMUM_COST_SENSITIVE_DELTA
        and abs(
            neutral.target_minus_comparator_rate
        )
        <= (
            _COST_AWARE_MAXIMUM_NEUTRAL_ABSOLUTE_DELTA
            + _EPSILON
        )
    )

    registered_criteria = (
        H1RegisteredCriteriaDecision(
            primary_c3_minus_c0=(
                primary.target_minus_comparator_rate
            ),
            c0_false_specific_rate=(
                c0_overall.false_specific_rate
            ),
            c3_false_specific_rate=(
                c3_overall.false_specific_rate
            ),
            primary_h1_criteria_met=primary_met,
            cost_sensitive_c3_minus_c1=(
                selection.target_minus_comparator_rate
            ),
            selection_policy_bound_met=selection_met,
            cost_sensitive_c3_minus_c2=(
                cost_sensitive.target_minus_comparator_rate
            ),
            neutral_c3_minus_c2=(
                neutral.target_minus_comparator_rate
            ),
            cost_aware_bound_met=cost_aware_met,
        )
    )

    return H1ProtectedEvaluation(
        batch_id=treatment_batch.batch_id,
        treatment_batch_sha256=(
            treatment_batch.batch_sha256
        ),
        hidden_manifest_sha256=(
            expected_hidden_manifest_sha256
        ),
        scored_records=scored_records,
        metric_slices=metric_slices,
        paired_comparisons=paired_comparisons,
        template_fault_metrics=(
            _template_fault_metrics(
                treatment_batch=treatment_batch,
                hidden_truth_by_case=hidden_truth_by_case,
                scored_by_key=scored_by_key,
            )
        ),
        registered_criteria=registered_criteria,
    )


__all__ = [
    "H1DiagnosisOutcome",
    "H1MetricSlice",
    "H1PairedComparison",
    "H1ProtectedEvaluation",
    "H1RegisteredCriteriaDecision",
    "H1ScoredTreatmentRecord",
    "H1TemplateFaultMetric",
    "evaluate_treatment_batch",
]
