"""Treatment-visible P09.4 protected-slot baseline materialization.

This module is deterministic and inert with respect to protected-study
authority.

It does not generate random seed material.

It does not persist protected artifacts.

It does not execute a scientific arm.

It converts one already-validated public slot plus its evaluator-side hidden
assignment into a treatment-visible P09.4 replay baseline.

The returned baseline does not retain the hidden assignment object.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import permutations

import environments.agent.p09_4_multistep_incident as env

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.engines.behavioral.p09_4_checkpoint_replay import (
    P094ReplayBaseline,
    capture_p09_4_out_of_rfs_replay_baseline,
    capture_p09_4_replay_baseline,
)
from packages.engines.behavioral.p09_4_protected_generation import (
    CASES_PER_TEMPLATE,
    EXPECTED_HYPOTHESIS_BY_STRATUM,
    HIDDEN_STRATA,
    P094ProtectedHiddenAssignment,
    P094ProtectedPublicSlot,
    TEMPLATE_IDS,
)


_TARGET_SERVICE = "payments-api"

_OUT_OF_RFS = "out_of_rfs_report_assembly"


_FAULT_MODE_BY_STRATUM = {
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

    _OUT_OF_RFS:
        env.P094FaultMode.NONE,
}


def _nuisance_mapping(
    public_slot: P094ProtectedPublicSlot,
) -> dict[
    str,
    str,
]:
    mapping = dict(
        public_slot.nuisance_items
    )

    expected_replicate = (
        f"{public_slot.slot_index:03d}"
    )

    if mapping.get(
        "replicate"
    ) != expected_replicate:
        raise ContractError(
            "public nuisance replicate does not match slot index"
        )

    template_id = (
        public_slot.template_id
    )

    if template_id == "V1":
        expected = {
            "surface",
            "replicate",
        }

        if set(
            mapping
        ) != expected:
            raise ContractError(
                "V1 nuisance contract changed"
            )

        if mapping[
            "surface"
        ] != "canonical":
            raise ContractError(
                "V1 surface contract changed"
            )

    elif template_id == "V2":
        expected = {
            "surface",
            "event_order_variant",
            "replicate",
        }

        if set(
            mapping
        ) != expected:
            raise ContractError(
                "V2 nuisance contract changed"
            )

        if mapping[
            "surface"
        ] != "event_order_variation":
            raise ContractError(
                "V2 surface contract changed"
            )

        expected_group = (
            "order-"
            + str(
                (
                    (
                        public_slot.slot_index
                        - 1
                    )
                    % 6
                )
                + 1
            )
        )

        if mapping[
            "event_order_variant"
        ] != expected_group:
            raise ContractError(
                "V2 public order-group contract changed"
            )

    elif template_id == "V3":
        expected = {
            "surface",
            "benign_context_tag",
            "replicate",
        }

        if set(
            mapping
        ) != expected:
            raise ContractError(
                "V3 nuisance contract changed"
            )

        if mapping[
            "surface"
        ] != "benign_context_noise":
            raise ContractError(
                "V3 surface contract changed"
            )

        if mapping[
            "benign_context_tag"
        ] != (
            "context-"
            + expected_replicate
        ):
            raise ContractError(
                "V3 public context contract changed"
            )

    elif template_id == "V4":
        expected = {
            "surface",
            "identifier_variant",
            "replicate",
        }

        if set(
            mapping
        ) != expected:
            raise ContractError(
                "V4 nuisance contract changed"
            )

        if mapping[
            "surface"
        ] != "identifier_value_variation":
            raise ContractError(
                "V4 surface contract changed"
            )

        if mapping[
            "identifier_variant"
        ] != (
            "identifier-"
            + expected_replicate
        ):
            raise ContractError(
                "V4 public identifier contract changed"
            )

    else:
        raise ContractError(
            "unsupported protected nuisance template"
        )

    return mapping


def _canonical_parts():
    incidents = env._load_incidents()

    targets = tuple(
        row
        for row
        in incidents
        if row[
            1
        ]
        == _TARGET_SERVICE
    )

    non_targets = tuple(
        row
        for row
        in incidents
        if row[
            1
        ]
        != _TARGET_SERVICE
    )

    if len(
        targets
    ) != 3:
        raise ContractError(
            "materializer requires exactly three canonical target incidents"
        )

    if len(
        non_targets
    ) != 1:
        raise ContractError(
            "materializer requires exactly one canonical non-target incident"
        )

    return (
        incidents,
        targets,
        non_targets[
            0
        ],
    )


_CANONICAL_INCIDENTS, _TARGET_INCIDENTS, _CANONICAL_NON_TARGET = (
    _canonical_parts()
)


_V2_NON_TARGETS = (
    _CANONICAL_NON_TARGET,
    (
        "INC-V2-AUX-A",
        "ledger-worker",
        2,
    ),
    (
        "INC-V2-AUX-B",
        "ledger-worker",
        1,
    ),
)


def _build_v2_orders():
    items = (
        *_TARGET_INCIDENTS,
        *_V2_NON_TARGETS,
    )

    valid = []

    for candidate in permutations(
        items
    ):
        target_projection = tuple(
            row
            for row
            in candidate
            if row[
                1
            ]
            == _TARGET_SERVICE
        )

        if (
            target_projection
            != _TARGET_INCIDENTS
        ):
            continue

        valid.append(
            candidate
        )

    valid = tuple(
        sorted(
            valid,
            key=lambda rows:
                tuple(
                    row[
                        0
                    ]
                    for row
                    in rows
                ),
        )
    )

    if len(
        valid
    ) != 120:
        raise ContractError(
            "V2 admissible ordering domain changed"
        )

    selected = valid[
        :CASES_PER_TEMPLATE
    ]

    if len(
        selected
    ) != CASES_PER_TEMPLATE:
        raise ContractError(
            "V2 selected ordering count changed"
        )

    if len(
        set(
            selected
        )
    ) != CASES_PER_TEMPLATE:
        raise ContractError(
            "V2 selected orderings must be unique"
        )

    return selected


_V2_ORDERS = _build_v2_orders()


@dataclass(
    frozen=True
)
class P094PublicMaterializationSpec:
    case_id: str
    template_id: str
    slot_index: int
    public_configuration_sha256: str
    incidents: tuple[
        tuple[
            str,
            str,
            int,
        ],
        ...,
    ]
    context_overlay_items: tuple[
        tuple[
            str,
            str,
        ],
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:
        if self.template_id not in TEMPLATE_IDS:
            raise ContractError(
                "materialization spec has unsupported template"
            )

        if (
            isinstance(
                self.slot_index,
                bool,
            )
            or not isinstance(
                self.slot_index,
                int,
            )
            or not (
                1
                <= self.slot_index
                <= CASES_PER_TEMPLATE
            )
        ):
            raise ContractError(
                "materialization slot index must be in 1..36"
            )

        if (
            not isinstance(
                self.incidents,
                tuple,
            )
            or not self.incidents
        ):
            raise ContractError(
                "materialization incidents are required"
            )

        if (
            not isinstance(
                self.context_overlay_items,
                tuple,
            )
        ):
            raise ContractError(
                "context_overlay_items must be a tuple"
            )

        if (
            self.context_overlay_items
            != tuple(
                sorted(
                    self.context_overlay_items
                )
            )
        ):
            raise ContractError(
                "context overlay must be key-sorted"
            )

        keys = tuple(
            key
            for (
                key,
                _
            )
            in self.context_overlay_items
        )

        if len(
            keys
        ) != len(
            set(
                keys
            )
        ):
            raise ContractError(
                "context overlay keys must be unique"
            )

    def canonical_payload(
        self,
    ) -> dict[
        str,
        object,
    ]:
        return {
            "record_type":
                "P094PublicMaterializationSpec",

            "schema_version":
                1,

            "case_id":
                self.case_id,

            "template_id":
                self.template_id,

            "slot_index":
                self.slot_index,

            "public_configuration_sha256":
                self.public_configuration_sha256,

            "incidents":
                self.incidents,

            "context_overlay_items":
                self.context_overlay_items,
        }

    @property
    def materialization_spec_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


def build_public_materialization_spec(
    public_slot: P094ProtectedPublicSlot,
) -> P094PublicMaterializationSpec:
    if not isinstance(
        public_slot,
        P094ProtectedPublicSlot,
    ):
        raise ContractError(
            "public_slot must be a P094ProtectedPublicSlot"
        )

    nuisance = (
        _nuisance_mapping(
            public_slot
        )
    )

    if public_slot.template_id == "V1":
        incidents = (
            _CANONICAL_INCIDENTS
        )

        context_overlay = ()

    elif public_slot.template_id == "V2":
        incidents = (
            _V2_ORDERS[
                public_slot.slot_index
                - 1
            ]
        )

        context_overlay = ()

    elif public_slot.template_id == "V3":
        incidents = (
            _CANONICAL_INCIDENTS
        )

        context_overlay = (
            (
                "benign_context_tag",
                nuisance[
                    "benign_context_tag"
                ],
            ),
        )

    elif public_slot.template_id == "V4":
        identifier = (
            nuisance[
                "identifier_variant"
            ]
        )

        incidents = tuple(
            (
                identifier,
                row[
                    1
                ],
                row[
                    2
                ],
            )
            if row[
                1
            ]
            != _TARGET_SERVICE
            else row
            for row
            in _CANONICAL_INCIDENTS
        )

        context_overlay = ()

    else:
        raise ContractError(
            "unsupported protected nuisance template"
        )

    return P094PublicMaterializationSpec(
        case_id=(
            public_slot.case_id
        ),
        template_id=(
            public_slot.template_id
        ),
        slot_index=(
            public_slot.slot_index
        ),
        public_configuration_sha256=(
            public_slot.public_configuration_sha256
        ),
        incidents=incidents,
        context_overlay_items=tuple(
            sorted(
                context_overlay
            )
        ),
    )


def _require_assignment_binding(
    *,
    public_slot: P094ProtectedPublicSlot,
    hidden_assignment: P094ProtectedHiddenAssignment,
) -> None:
    if not isinstance(
        hidden_assignment,
        P094ProtectedHiddenAssignment,
    ):
        raise ContractError(
            "hidden_assignment must be a P094ProtectedHiddenAssignment"
        )

    if (
        hidden_assignment.case_id
        != public_slot.case_id
    ):
        raise ContractError(
            "hidden assignment case ID does not match public slot"
        )

    if (
        hidden_assignment.template_id
        != public_slot.template_id
    ):
        raise ContractError(
            "hidden assignment template does not match public slot"
        )

    if (
        hidden_assignment.public_configuration_sha256
        != public_slot.public_configuration_sha256
    ):
        raise ContractError(
            "hidden assignment public configuration does not match public slot"
        )

    if (
        hidden_assignment.hidden_stratum
        not in HIDDEN_STRATA
    ):
        raise ContractError(
            "hidden assignment stratum is not registered"
        )

    expected_hypothesis = (
        EXPECTED_HYPOTHESIS_BY_STRATUM[
            hidden_assignment.hidden_stratum
        ]
    )

    if (
        hidden_assignment.expected_hypothesis_key
        != expected_hypothesis
    ):
        raise ContractError(
            "hidden assignment hypothesis mapping changed"
        )


def _capture_reference_baseline(
    *,
    hidden_stratum: str,
    run_id: str,
) -> P094ReplayBaseline:
    if hidden_stratum == _OUT_OF_RFS:
        return capture_p09_4_out_of_rfs_replay_baseline(
            run_id=run_id,
        )

    return capture_p09_4_replay_baseline(
        _FAULT_MODE_BY_STRATUM[
            hidden_stratum
        ],
        run_id=run_id,
    )


def materialize_protected_replay_baseline(
    *,
    public_slot: P094ProtectedPublicSlot,
    hidden_assignment: P094ProtectedHiddenAssignment,
) -> P094ReplayBaseline:
    if not isinstance(
        public_slot,
        P094ProtectedPublicSlot,
    ):
        raise ContractError(
            "public_slot must be a P094ProtectedPublicSlot"
        )

    _require_assignment_binding(
        public_slot=public_slot,
        hidden_assignment=(
            hidden_assignment
        ),
    )

    spec = (
        build_public_materialization_spec(
            public_slot
        )
    )

    run_id = (
        public_slot.case_id
    )

    base = (
        _capture_reference_baseline(
            hidden_stratum=(
                hidden_assignment.hidden_stratum
            ),
            run_id=run_id,
        )
    )

    original_context_loader = (
        base._context_loader
    )

    overlay = dict(
        spec.context_overlay_items
    )

    if overlay:
        def context_loader(
            intervention,
            *,
            _loader=original_context_loader,
            _overlay=overlay,
        ):
            context = dict(
                _loader(
                    intervention
                )
            )

            context.update(
                _overlay
            )

            return context

    else:
        context_loader = (
            original_context_loader
        )

    service_rows = (
        env._scope_service(
            spec.incidents
        )
    )

    context = dict(
        context_loader(
            None
        )
    )

    (
        tool_name,
        threshold,
    ) = (
        base._strategy_selector(
            None
        )
    )

    filtered_rows = (
        env._filter_incidents(
            service_rows,
            tool_name=tool_name,
            threshold=threshold,
        )
    )

    enriched_rows = (
        base._enricher(
            filtered_rows,
            None,
        )
    )

    normalized_rows = (
        base._normalizer(
            filtered_rows,
            enriched_rows,
            None,
        )
    )

    validated_rows = (
        env._validate_incidents(
            normalized_rows,
            context=context,
        )
    )

    report = (
        base._report_builder(
            validated_rows
        )
    )

    fault_mode = (
        _FAULT_MODE_BY_STRATUM[
            hidden_assignment.hidden_stratum
        ]
    )

    trace = env._build_trace(
        run_id=run_id,
        incidents=spec.incidents,
        service_rows=service_rows,
        context=context,
        tool_name=tool_name,
        threshold=threshold,
        filtered_rows=filtered_rows,
        enriched_rows=enriched_rows,
        normalized_rows=normalized_rows,
        validated_rows=validated_rows,
        report=report,
        fault_mode=fault_mode,
        intervention=None,
    )

    run = env.P094IncidentRun(
        run_id=run_id,
        report=report,
        trace=trace,
    )

    context_items = tuple(
        context.items()
    )

    checkpoints = []

    for checkpoint in base.checkpoints:
        changes = {
            "baseline_trace_sha256":
                trace.trace_sha256,
        }

        if checkpoint.key in {
            "pre-filter",
            "post-filter",
        }:
            changes[
                "context_items"
            ] = context_items

        elif checkpoint.key == "pre-validation":
            if checkpoint.context_items:
                raise ContractError(
                    "canonical pre-validation checkpoint unexpectedly carries context"
                )

        else:
            raise ContractError(
                "unsupported replay checkpoint"
            )

        checkpoints.append(
            replace(
                checkpoint,
                **changes,
            )
        )

    materialized = replace(
        base,
        run=run,
        checkpoints=tuple(
            checkpoints
        ),
        _context_loader=(
            context_loader
        ),
    )

    if materialized.run.passed:
        raise ContractError(
            "protected nuisance materialization produced a passing baseline"
        )

    if (
        materialized.run.report
        != base.run.report
    ):
        raise ContractError(
            "protected nuisance materialization changed baseline report semantics"
        )

    if (
        materialized.checkpoint(
            "pre-filter"
        ).service_rows
        != base.checkpoint(
            "pre-filter"
        ).service_rows
    ):
        raise ContractError(
            "protected nuisance materialization changed target service scope"
        )

    return materialized


__all__ = [
    "P094PublicMaterializationSpec",
    "build_public_materialization_spec",
    "materialize_protected_replay_baseline",
]
