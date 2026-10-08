"""Pure P09.3 H1 treatment-batch construction.

This module deliberately contains no protected-file access and no evaluator
truth API.

A caller supplies treatment-visible public-manifest data and an opaque
experiment-executor factory. The executor is the environment boundary: it may
internally know the latent environment, but the C0-C3 arm harness receives only
the callable and the observations that callable returns.

The resulting treatment batch contains no hidden fault key and performs no
scientific scoring. Scoring belongs to the separate evaluator module.

This module performs no filesystem I/O.
"""

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import re

from environments.agent.h1_controlled_active_diagnosis import (
    H1ObservedExperiment,
    H1PublicCase,
    build_public_case,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    canonical_sha256,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis import (
    H1Arm,
    H1ArmRunResult,
    run_h1_arm,
)


_SHA256 = re.compile(
    r"^[0-9a-f]{64}$"
)

_ALLOWED_CASE_KEYS = {
    "case_id",
    "template_id",
    "singleton_target",
    "problem_sha256",
}

ExperimentExecutor = Callable[
    [str],
    H1ObservedExperiment,
]

ExperimentExecutorFactory = Callable[
    [H1PublicCase],
    ExperimentExecutor,
]


def _require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
    ):
        raise ContractError(
            f"{name} must be non-empty text"
        )

    return value


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


def _json_bytes(
    payload: object,
) -> bytes:
    return json.dumps(
        payload,
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


@dataclass(frozen=True)
class H1ProtectedPublicCaseRef:
    """Treatment-visible reference used to reconstruct one frozen case."""

    case_id: str
    template_id: str
    singleton_target: str
    problem_sha256: str

    def __post_init__(
        self,
    ) -> None:
        _require_text(
            self.case_id,
            "case_id",
        )

        _require_text(
            self.template_id,
            "template_id",
        )

        _require_text(
            self.singleton_target,
            "singleton_target",
        )

        _require_sha256(
            self.problem_sha256,
            "problem_sha256",
        )

        if self.singleton_target not in {
            "H1",
            "H2",
            "H3",
            "H4",
        }:
            raise ContractError(
                "singleton_target must be H1, H2, H3 or H4"
            )

    def to_payload(
        self,
    ) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "template_id": self.template_id,
            "singleton_target": self.singleton_target,
            "problem_sha256": self.problem_sha256,
        }


@dataclass(frozen=True)
class H1ProtectedTreatmentRecord:
    """One treatment-only arm result.

    The record intentionally contains no evaluator truth.
    """

    case_id: str
    template_id: str
    arm: str
    status: str
    diagnosed_hypothesis_key: str | None
    posterior: tuple[
        tuple[
            str,
            float,
        ],
        ...,
    ]
    experiment_sequence: tuple[
        str,
        ...,
    ]
    verdict_sequence: tuple[
        str,
        ...,
    ]
    evidence_references: tuple[
        str,
        ...,
    ]
    declared_cost_units: int
    actual_cost_units: int
    workflow_step_count: int
    problem_sha256: str

    def __post_init__(
        self,
    ) -> None:
        _require_text(
            self.case_id,
            "case_id",
        )

        _require_text(
            self.template_id,
            "template_id",
        )

        if self.arm not in {
            arm.value
            for arm in H1Arm
        }:
            raise ContractError(
                "unknown H1 arm"
            )

        terminal_statuses = {
            DiagnosisStatus.DIAGNOSED.value,
            DiagnosisStatus.INCONCLUSIVE.value,
            DiagnosisStatus.BUDGET_EXHAUSTED.value,
        }

        if self.status not in terminal_statuses:
            raise ContractError(
                "treatment result must be terminal"
            )

        if (
            self.status
            == DiagnosisStatus.DIAGNOSED.value
            and self.diagnosed_hypothesis_key
            is None
        ):
            raise ContractError(
                "DIAGNOSED treatment result requires a hypothesis"
            )

        if (
            self.status
            != DiagnosisStatus.DIAGNOSED.value
            and self.diagnosed_hypothesis_key
            is not None
        ):
            raise ContractError(
                "non-DIAGNOSED result cannot carry a specific diagnosis"
            )

        if self.diagnosed_hypothesis_key is not None:
            if self.diagnosed_hypothesis_key not in {
                "H1",
                "H2",
                "H3",
                "H4",
            }:
                raise ContractError(
                    "unknown diagnosed hypothesis"
                )

        if (
            len(
                self.experiment_sequence
            )
            != len(
                self.verdict_sequence
            )
            or len(
                self.experiment_sequence
            )
            != len(
                self.evidence_references
            )
        ):
            raise ContractError(
                "experiment, verdict and evidence sequences "
                "must have equal length"
            )

        for value, name in (
            (
                self.declared_cost_units,
                "declared_cost_units",
            ),
            (
                self.actual_cost_units,
                "actual_cost_units",
            ),
            (
                self.workflow_step_count,
                "workflow_step_count",
            ),
        ):
            if (
                isinstance(
                    value,
                    bool,
                )
                or not isinstance(
                    value,
                    int,
                )
                or value < 0
            ):
                raise ContractError(
                    f"{name} must be a non-negative integer"
                )

        if (
            self.declared_cost_units
            != self.actual_cost_units
        ):
            raise ContractError(
                "declared and actual synthetic cost must match"
            )

        _require_sha256(
            self.problem_sha256,
            "problem_sha256",
        )

        for evidence_reference in self.evidence_references:
            _require_sha256(
                evidence_reference,
                "evidence_reference",
            )

    @property
    def experiment_count(
        self,
    ) -> int:
        return len(
            self.experiment_sequence
        )

    def to_payload(
        self,
    ) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "template_id": self.template_id,
            "arm": self.arm,
            "status": self.status,
            "diagnosed_hypothesis_key": (
                self.diagnosed_hypothesis_key
            ),
            "posterior": [
                [
                    key,
                    probability,
                ]
                for key, probability
                in self.posterior
            ],
            "experiment_sequence": list(
                self.experiment_sequence
            ),
            "verdict_sequence": list(
                self.verdict_sequence
            ),
            "evidence_references": list(
                self.evidence_references
            ),
            "declared_cost_units": (
                self.declared_cost_units
            ),
            "actual_cost_units": (
                self.actual_cost_units
            ),
            "workflow_step_count": (
                self.workflow_step_count
            ),
            "problem_sha256": (
                self.problem_sha256
            ),
        }


@dataclass(frozen=True)
class H1ProtectedTreatmentBatch:
    """Complete treatment-only result for one matched H1 batch."""

    batch_id: str
    public_manifest_sha256: str
    records: tuple[
        H1ProtectedTreatmentRecord,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:
        _require_text(
            self.batch_id,
            "batch_id",
        )

        _require_sha256(
            self.public_manifest_sha256,
            "public_manifest_sha256",
        )

        if not self.records:
            raise ContractError(
                "treatment batch requires records"
            )

        seen = set()
        arms_by_case: dict[
            str,
            set[str],
        ] = defaultdict(
            set
        )

        metadata_by_case = {}

        for record in self.records:
            key = (
                record.case_id,
                record.arm,
            )

            if key in seen:
                raise ContractError(
                    "duplicate case/arm treatment result"
                )

            seen.add(
                key
            )

            arms_by_case[
                record.case_id
            ].add(
                record.arm
            )

            metadata = (
                record.template_id,
                record.problem_sha256,
            )

            existing = metadata_by_case.get(
                record.case_id
            )

            if (
                existing is not None
                and existing != metadata
            ):
                raise ContractError(
                    "case metadata differs across arms"
                )

            metadata_by_case[
                record.case_id
            ] = metadata

        expected_arms = {
            arm.value
            for arm in H1Arm
        }

        for case_id, arms in arms_by_case.items():
            if arms != expected_arms:
                raise ContractError(
                    "each treatment case must contain exactly "
                    f"the four frozen arms: {case_id}"
                )

    @property
    def case_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    record.case_id
                    for record
                    in self.records
                }
            )
        )

    @property
    def batch_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.to_payload()
        )

    @property
    def canonical_json_bytes(
        self,
    ) -> bytes:
        return _json_bytes(
            self.to_payload()
        )

    def to_payload(
        self,
    ) -> dict[str, object]:
        return {
            "record_type": (
                "H1ProtectedTreatmentBatch"
            ),
            "schema_version": 1,
            "batch_id": self.batch_id,
            "public_manifest_sha256": (
                self.public_manifest_sha256
            ),
            "records": [
                record.to_payload()
                for record
                in self.records
            ],
        }


def parse_public_manifest_cases(
    public_manifest: Mapping[
        str,
        object,
    ],
) -> tuple[
    str,
    tuple[
        H1ProtectedPublicCaseRef,
        ...,
    ],
]:
    """Parse treatment-visible case references only."""

    if not isinstance(
        public_manifest,
        Mapping,
    ):
        raise ContractError(
            "public_manifest must be a mapping"
        )

    batch_id = _require_text(
        public_manifest.get(
            "batch_id"
        ),
        "public_manifest.batch_id",
    )

    raw_cases = public_manifest.get(
        "cases"
    )

    if not isinstance(
        raw_cases,
        list,
    ):
        raise ContractError(
            "public_manifest.cases must be a list"
        )

    if not raw_cases:
        raise ContractError(
            "public_manifest requires cases"
        )

    result = []
    seen_case_ids = set()

    for index, raw_case in enumerate(
        raw_cases
    ):
        if not isinstance(
            raw_case,
            Mapping,
        ):
            raise ContractError(
                f"public case {index} must be a mapping"
            )

        keys = set(
            raw_case
        )

        if keys != _ALLOWED_CASE_KEYS:
            raise ContractError(
                "public case fields differ from frozen "
                "treatment-visible schema"
            )

        ref = H1ProtectedPublicCaseRef(
            case_id=raw_case[
                "case_id"
            ],
            template_id=raw_case[
                "template_id"
            ],
            singleton_target=raw_case[
                "singleton_target"
            ],
            problem_sha256=raw_case[
                "problem_sha256"
            ],
        )

        if ref.case_id in seen_case_ids:
            raise ContractError(
                "duplicate public case ID"
            )

        seen_case_ids.add(
            ref.case_id
        )

        result.append(
            ref
        )

    return (
        batch_id,
        tuple(
            result
        ),
    )


def reconstruct_public_case(
    case_ref: H1ProtectedPublicCaseRef,
) -> H1PublicCase:
    """Reconstruct one case using treatment-visible fields only."""

    if not isinstance(
        case_ref,
        H1ProtectedPublicCaseRef,
    ):
        raise ContractError(
            "case_ref must be an H1ProtectedPublicCaseRef"
        )

    public_case = build_public_case(
        case_id=case_ref.case_id,
        template_id=case_ref.template_id,
    )

    if (
        public_case.singleton_target
        != case_ref.singleton_target
    ):
        raise ContractError(
            "reconstructed singleton target mismatch"
        )

    if (
        public_case.problem.problem_sha256
        != case_ref.problem_sha256
    ):
        raise ContractError(
            "reconstructed problem hash mismatch"
        )

    return public_case


def _record_from_arm_result(
    *,
    case_ref: H1ProtectedPublicCaseRef,
    result: H1ArmRunResult,
) -> H1ProtectedTreatmentRecord:
    if result.case_id != case_ref.case_id:
        raise ContractError(
            "arm result case ID mismatch"
        )

    if (
        result.problem_sha256
        != case_ref.problem_sha256
    ):
        raise ContractError(
            "arm result problem hash mismatch"
        )

    return H1ProtectedTreatmentRecord(
        case_id=result.case_id,
        template_id=case_ref.template_id,
        arm=result.arm.value,
        status=result.status.value,
        diagnosed_hypothesis_key=(
            result.diagnosed_hypothesis_key
        ),
        posterior=result.posterior,
        experiment_sequence=(
            result.experiment_sequence
        ),
        verdict_sequence=tuple(
            verdict.value
            for verdict
            in result.verdict_sequence
        ),
        evidence_references=(
            result.evidence_references
        ),
        declared_cost_units=(
            result.declared_cost_units
        ),
        actual_cost_units=(
            result.actual_cost_units
        ),
        workflow_step_count=(
            result.workflow_step_count
        ),
        problem_sha256=(
            result.problem_sha256
        ),
    )


def run_treatment_batch_from_manifest(
    *,
    public_manifest: Mapping[
        str,
        object,
    ],
    expected_public_manifest_sha256: str,
    executor_factory: ExperimentExecutorFactory,
) -> H1ProtectedTreatmentBatch:
    """Run C0-C3 over public cases without evaluator scoring.

    The treatment function never receives a truth mapping.

    ``executor_factory`` is the opaque environment boundary supplied by the
    caller. Each active arm receives a fresh executor created from the same
    treatment-visible public case. The factory is not told which arm requested
    it, preventing arm-specific environment behavior at this boundary.
    """

    _require_sha256(
        expected_public_manifest_sha256,
        "expected_public_manifest_sha256",
    )

    if not callable(
        executor_factory
    ):
        raise ContractError(
            "executor_factory must be callable"
        )

    (
        batch_id,
        case_refs,
    ) = parse_public_manifest_cases(
        public_manifest
    )

    manifest_sha256 = canonical_sha256(
        public_manifest
    )

    if (
        manifest_sha256
        != expected_public_manifest_sha256
    ):
        raise ContractError(
            "public manifest does not match frozen expected SHA-256"
        )

    records = []

    for case_ref in case_refs:
        public_case = reconstruct_public_case(
            case_ref
        )

        arm_results = []

        for arm in H1Arm:
            if arm is H1Arm.TRACE_ONLY:
                executor = None
            else:
                executor = executor_factory(
                    public_case
                )

                if not callable(
                    executor
                ):
                    raise ContractError(
                        "executor_factory must return a callable"
                    )

            result = run_h1_arm(
                public_case=public_case,
                arm=arm,
                execute_experiment=executor,
            )

            arm_results.append(
                result
            )

        if len(
            arm_results
        ) != len(
            tuple(
                H1Arm
            )
        ):
            raise ContractError(
                "frozen arm harness did not return exactly four arms"
            )

        for result in arm_results:
            records.append(
                _record_from_arm_result(
                    case_ref=case_ref,
                    result=result,
                )
            )

    return H1ProtectedTreatmentBatch(
        batch_id=batch_id,
        public_manifest_sha256=manifest_sha256,
        records=tuple(
            records
        ),
    )


__all__ = [
    "ExperimentExecutor",
    "ExperimentExecutorFactory",
    "H1ProtectedPublicCaseRef",
    "H1ProtectedTreatmentBatch",
    "H1ProtectedTreatmentRecord",
    "parse_public_manifest_cases",
    "reconstruct_public_case",
    "run_treatment_batch_from_manifest",
]
