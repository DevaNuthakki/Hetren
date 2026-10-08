"""One-shot persistence for the P09.3 H1 protected execution attempt.

This module is trusted orchestration around the frozen treatment/evaluator
contracts.

Scientific boundary:

* treatment receives treatment-visible public data and an opaque executor;
* latent truth is used only behind the controlled-environment executor;
* treatment results are persisted before evaluator scoring;
* evaluator output remains evaluator-side;
* the attempt directory is claimed before protected truth is parsed or any
  protected treatment executes.

The environment and evaluator currently execute in the same local Python
process. This is logical information-flow separation, not process,
infrastructure, organizational, or data-custodian independence.

Operational failure permanently consumes the attempt identity. Where the
filesystem remains writable, FAILED disposition evidence preserves the failure
phase, whether treatment began, active case/arm context available at the
executor boundary, and treatment evidence already observed.

Sudden power loss or unrecoverable filesystem failure can still prevent a final
FAILED disposition. This implementation does not claim hardware-level
transactional atomicity.

This module does not authorize protected execution.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re

from environments.agent.h1_controlled_active_diagnosis import (
    H1DevelopmentTruth,
    H1ObservedExperiment,
    H1PublicCase,
    execute_development_experiment,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis import (
    H1Arm,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis_persistence import (
    _atomic_replace,
    _atomic_write_new,
    _fsync_directory,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis_protected_evaluation import (
    _parse_hidden_manifest,
    evaluate_treatment_batch,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis_protected_execution import (
    parse_public_manifest_cases,
    run_treatment_batch_from_manifest,
)


_SHA256 = re.compile(
    r"^[0-9a-f]{64}$"
)

_GIT_COMMIT = re.compile(
    r"^[0-9a-f]{40}$"
)

_SAFE_ID = re.compile(
    r"^[A-Za-z0-9._-]+$"
)


EXECUTION_INVALIDATION_CATEGORIES = (
    "SETUP_FAILURE",
    "INPUT_BINDING_FAILURE",
    "TREATMENT_EXECUTION_FAILURE",
    "TREATMENT_PERSISTENCE_FAILURE",
    "EVALUATION_FAILURE",
    "EVALUATION_PERSISTENCE_FAILURE",
    "RECORD_PERSISTENCE_FAILURE",
    "FINALIZATION_FAILURE",
    "UNKNOWN_OPERATIONAL_FAILURE",
)


@dataclass(frozen=True)
class H1ProtectedExecutionPersistenceResult:
    """Safe success summary without evaluator outcome payloads."""

    attempt_directory: Path
    treatment_batch_sha256: str
    evaluation_sha256: str
    execution_record_sha256: str


def _require_sha256(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA256.fullmatch(value) is None
    ):
        raise ContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _require_commit(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or _GIT_COMMIT.fullmatch(value) is None
    ):
        raise ContractError(
            f"{name} must be a 40-hex Git commit ID"
        )

    return value


def _require_safe_id(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or _SAFE_ID.fullmatch(value) is None
    ):
        raise ContractError(
            f"{name} must be a safe non-empty identifier"
        )

    return value


def _json_bytes(
    value: object,
) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode(
        "utf-8"
    )


def _load_json_mapping(
    path: Path,
    name: str,
) -> dict[str, object]:
    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, dict):
        raise ContractError(
            f"{name} must contain a JSON object"
        )

    return payload


def _failure_category_for_phase(
    phase: str,
) -> str:
    if phase in {
        "CLAIMED",
        "FSYNC_ATTEMPT_CLAIM",
        "CREATE_PUBLIC_DIRECTORY",
        "PERSIST_STARTED_DISPOSITION",
        "CREATE_EVALUATOR_DIRECTORY",
    }:
        return "SETUP_FAILURE"

    if phase in {
        "LOAD_PUBLIC_MANIFEST",
        "BIND_PUBLIC_MANIFEST",
        "LOAD_HIDDEN_MANIFEST",
        "BIND_HIDDEN_MANIFEST",
    }:
        return "INPUT_BINDING_FAILURE"

    if phase == "RUN_TREATMENT":
        return "TREATMENT_EXECUTION_FAILURE"

    if phase == "PERSIST_TREATMENT":
        return "TREATMENT_PERSISTENCE_FAILURE"

    if phase == "RUN_EVALUATION":
        return "EVALUATION_FAILURE"

    if phase == "PERSIST_EVALUATION":
        return "EVALUATION_PERSISTENCE_FAILURE"

    if phase == "PERSIST_EXECUTION_RECORD":
        return "RECORD_PERSISTENCE_FAILURE"

    if phase == "PERSIST_SUCCESS_DISPOSITION":
        return "FINALIZATION_FAILURE"

    return "UNKNOWN_OPERATIONAL_FAILURE"


def _disposition_payload(
    *,
    batch_id: str,
    attempt_id: str,
    status: str,
    phase: str,
    repository_head_commit_id: str,
    d1_contract_commit_id: str,
    generation_freeze_commit_id: str,
    generation_record_sha256: str,
    public_manifest_sha256: str,
    hidden_truth_manifest_sha256: str,
    environment_module_sha256: str,
    treatment_module_sha256: str,
    evaluation_module_sha256: str,
    execution_persistence_module_sha256: str,
    treatment_started: bool,
    current_case_id: str | None,
    attempted_arm: str | None,
    observed_events: list[dict[str, object]],
    treatment_batch_sha256: str | None,
    evaluation_sha256: str | None,
    execution_record_sha256: str | None,
    failure_category: str | None,
    failure_type: str | None,
) -> dict[str, object]:
    return {
        "record_type": "H1ProtectedExecutionDisposition",
        "schema_version": 1,
        "batch_id": batch_id,
        "attempt_id": attempt_id,
        "status": status,
        "phase": phase,
        "repository_head_commit_id": repository_head_commit_id,
        "d1_contract_commit_id": d1_contract_commit_id,
        "generation_freeze_commit_id": generation_freeze_commit_id,
        "generation_record_sha256": generation_record_sha256,
        "public_manifest_sha256": public_manifest_sha256,
        "hidden_truth_manifest_sha256": (
            hidden_truth_manifest_sha256
        ),
        "environment_module_sha256": environment_module_sha256,
        "treatment_module_sha256": treatment_module_sha256,
        "evaluation_module_sha256": evaluation_module_sha256,
        "execution_persistence_module_sha256": (
            execution_persistence_module_sha256
        ),
        "treatment_started": treatment_started,
        "current_case_id": current_case_id,
        "attempted_arm": attempted_arm,
        "completed_observation_count": len(
            observed_events
        ),
        "available_evidence_references": [
            event["evidence_sha256"]
            for event in observed_events
        ],
        "observed_events": [
            dict(event)
            for event in observed_events
        ],
        "treatment_batch_sha256": treatment_batch_sha256,
        "evaluation_sha256": evaluation_sha256,
        "execution_record_sha256": execution_record_sha256,
        "failure_category": failure_category,
        "failure_type": failure_type,
    }


def _execution_record_payload(
    *,
    batch_id: str,
    attempt_id: str,
    protocol_sha256: str,
    harness_commit_id: str,
    repository_head_commit_id: str,
    d1_contract_commit_id: str,
    generation_freeze_commit_id: str,
    generation_record_sha256: str,
    public_manifest_sha256: str,
    hidden_truth_manifest_sha256: str,
    environment_module_sha256: str,
    treatment_module_sha256: str,
    evaluation_module_sha256: str,
    execution_persistence_module_sha256: str,
    treatment_batch_sha256: str,
    evaluation_sha256: str,
) -> dict[str, object]:
    return {
        "record_type": "H1ProtectedExecutionRecord",
        "schema_version": 1,
        "batch_id": batch_id,
        "attempt_id": attempt_id,
        "protocol_sha256": protocol_sha256,
        "harness_commit_id": harness_commit_id,
        "repository_head_commit_id": repository_head_commit_id,
        "d1_contract_commit_id": d1_contract_commit_id,
        "generation_freeze_commit_id": generation_freeze_commit_id,
        "generation_record_sha256": generation_record_sha256,
        "public_manifest_sha256": public_manifest_sha256,
        "hidden_truth_manifest_sha256": (
            hidden_truth_manifest_sha256
        ),
        "environment_module_sha256": environment_module_sha256,
        "treatment_module_sha256": treatment_module_sha256,
        "evaluation_module_sha256": evaluation_module_sha256,
        "execution_persistence_module_sha256": (
            execution_persistence_module_sha256
        ),
        "treatment_batch_sha256": treatment_batch_sha256,
        "evaluation_sha256": evaluation_sha256,
        "treatment_batch_path": "public/treatment_batch.json",
        "evaluation_path": "evaluator/evaluation.json",
        "execution_disposition_path": (
            "public/execution_disposition.json"
        ),
    }


def persist_h1_protected_execution_attempt(
    *,
    batch_directory: Path,
    batch_id: str,
    attempt_id: str,
    public_manifest_path: Path,
    hidden_manifest_path: Path,
    expected_public_manifest_sha256: str,
    expected_hidden_manifest_sha256: str,
    repository_head_commit_id: str,
    d1_contract_commit_id: str,
    generation_freeze_commit_id: str,
    generation_record_sha256: str,
    environment_module_sha256: str,
    treatment_module_sha256: str,
    evaluation_module_sha256: str,
    execution_persistence_module_sha256: str,
) -> H1ProtectedExecutionPersistenceResult:
    """Consume one protected execution attempt identity exactly once."""

    if not isinstance(batch_directory, Path):
        raise ContractError(
            "batch_directory must be a pathlib.Path"
        )

    if not isinstance(public_manifest_path, Path):
        raise ContractError(
            "public_manifest_path must be a pathlib.Path"
        )

    if not isinstance(hidden_manifest_path, Path):
        raise ContractError(
            "hidden_manifest_path must be a pathlib.Path"
        )

    _require_safe_id(
        batch_id,
        "batch_id",
    )

    _require_safe_id(
        attempt_id,
        "attempt_id",
    )

    _require_sha256(
        expected_public_manifest_sha256,
        "expected_public_manifest_sha256",
    )

    _require_sha256(
        expected_hidden_manifest_sha256,
        "expected_hidden_manifest_sha256",
    )

    _require_commit(
        repository_head_commit_id,
        "repository_head_commit_id",
    )

    _require_commit(
        d1_contract_commit_id,
        "d1_contract_commit_id",
    )

    _require_commit(
        generation_freeze_commit_id,
        "generation_freeze_commit_id",
    )

    for value, name in (
        (
            generation_record_sha256,
            "generation_record_sha256",
        ),
        (
            environment_module_sha256,
            "environment_module_sha256",
        ),
        (
            treatment_module_sha256,
            "treatment_module_sha256",
        ),
        (
            evaluation_module_sha256,
            "evaluation_module_sha256",
        ),
        (
            execution_persistence_module_sha256,
            "execution_persistence_module_sha256",
        ),
    ):
        _require_sha256(
            value,
            name,
        )

    if (
        not batch_directory.exists()
        or not batch_directory.is_dir()
    ):
        raise ContractError(
            "batch_directory must be an existing directory"
        )

    if batch_directory.is_symlink():
        raise ContractError(
            "batch_directory must not be a symbolic link"
        )

    attempt_directory = (
        batch_directory
        / attempt_id
    )

    public_directory = (
        attempt_directory
        / "public"
    )

    evaluator_directory = (
        attempt_directory
        / "evaluator"
    )

    disposition_path = (
        public_directory
        / "execution_disposition.json"
    )

    treatment_path = (
        public_directory
        / "treatment_batch.json"
    )

    execution_record_path = (
        public_directory
        / "execution_record.json"
    )

    evaluation_path = (
        evaluator_directory
        / "evaluation.json"
    )

    if (
        attempt_directory.exists()
        or attempt_directory.is_symlink()
    ):
        raise FileExistsError(
            str(
                attempt_directory
            )
        )

    state: dict[str, object] = {
        "phase": "PRE_CLAIM",
        "treatment_started": False,
        "current_case_id": None,
        "attempted_arm": None,
        "observed_events": [],
        "treatment_batch_sha256": None,
        "evaluation_sha256": None,
        "execution_record_sha256": None,
    }

    attempt_claimed = False

    def disposition(
        *,
        status: str,
        failure_category: str | None = None,
        failure_type: str | None = None,
        phase_override: str | None = None,
    ) -> dict[str, object]:
        return _disposition_payload(
            batch_id=batch_id,
            attempt_id=attempt_id,
            status=status,
            phase=(
                str(
                    state["phase"]
                )
                if phase_override is None
                else phase_override
            ),
            repository_head_commit_id=(
                repository_head_commit_id
            ),
            d1_contract_commit_id=(
                d1_contract_commit_id
            ),
            generation_freeze_commit_id=(
                generation_freeze_commit_id
            ),
            generation_record_sha256=(
                generation_record_sha256
            ),
            public_manifest_sha256=(
                expected_public_manifest_sha256
            ),
            hidden_truth_manifest_sha256=(
                expected_hidden_manifest_sha256
            ),
            environment_module_sha256=(
                environment_module_sha256
            ),
            treatment_module_sha256=(
                treatment_module_sha256
            ),
            evaluation_module_sha256=(
                evaluation_module_sha256
            ),
            execution_persistence_module_sha256=(
                execution_persistence_module_sha256
            ),
            treatment_started=bool(
                state["treatment_started"]
            ),
            current_case_id=state[
                "current_case_id"
            ],
            attempted_arm=state[
                "attempted_arm"
            ],
            observed_events=state[
                "observed_events"
            ],
            treatment_batch_sha256=state[
                "treatment_batch_sha256"
            ],
            evaluation_sha256=state[
                "evaluation_sha256"
            ],
            execution_record_sha256=state[
                "execution_record_sha256"
            ],
            failure_category=failure_category,
            failure_type=failure_type,
        )

    def replace_started_disposition() -> None:
        _atomic_replace(
            disposition_path,
            _json_bytes(
                disposition(
                    status="STARTED"
                )
            ),
            mode=0o600,
        )

    try:
        os.mkdir(
            attempt_directory,
            0o700,
        )

        attempt_claimed = True

        os.chmod(
            attempt_directory,
            0o700,
        )

        state["phase"] = "CLAIMED"

        state["phase"] = (
            "FSYNC_ATTEMPT_CLAIM"
        )

        _fsync_directory(
            batch_directory
        )

        state["phase"] = (
            "CREATE_PUBLIC_DIRECTORY"
        )

        os.mkdir(
            public_directory,
            0o700,
        )

        os.chmod(
            public_directory,
            0o700,
        )

        _fsync_directory(
            attempt_directory
        )

        state["phase"] = (
            "PERSIST_STARTED_DISPOSITION"
        )

        _atomic_write_new(
            disposition_path,
            _json_bytes(
                disposition(
                    status="STARTED"
                )
            ),
            mode=0o600,
        )

        state["phase"] = (
            "CREATE_EVALUATOR_DIRECTORY"
        )

        os.mkdir(
            evaluator_directory,
            0o700,
        )

        os.chmod(
            evaluator_directory,
            0o700,
        )

        _fsync_directory(
            attempt_directory
        )

        state["phase"] = (
            "LOAD_PUBLIC_MANIFEST"
        )

        replace_started_disposition()

        public_manifest = _load_json_mapping(
            public_manifest_path,
            "public_manifest",
        )

        state["phase"] = (
            "BIND_PUBLIC_MANIFEST"
        )

        replace_started_disposition()

        actual_public_sha256 = (
            canonical_sha256(
                public_manifest
            )
        )

        if (
            actual_public_sha256
            != expected_public_manifest_sha256
        ):
            raise ContractError(
                "public manifest does not match "
                "frozen expected SHA-256"
            )

        (
            manifest_batch_id,
            public_case_refs,
        ) = parse_public_manifest_cases(
            public_manifest
        )

        if (
            manifest_batch_id
            != batch_id
        ):
            raise ContractError(
                "public manifest batch ID does not "
                "match execution batch"
            )

        state["phase"] = (
            "LOAD_HIDDEN_MANIFEST"
        )

        replace_started_disposition()

        hidden_manifest = _load_json_mapping(
            hidden_manifest_path,
            "hidden_manifest",
        )

        state["phase"] = (
            "BIND_HIDDEN_MANIFEST"
        )

        replace_started_disposition()

        hidden_truth_by_case = (
            _parse_hidden_manifest(
                hidden_manifest=(
                    hidden_manifest
                ),
                expected_hidden_manifest_sha256=(
                    expected_hidden_manifest_sha256
                ),
                expected_batch_id=(
                    batch_id
                ),
            )
        )

        public_case_ids = {
            case_ref.case_id
            for case_ref
            in public_case_refs
        }

        if (
            public_case_ids
            != set(
                hidden_truth_by_case
            )
        ):
            raise ContractError(
                "public and hidden manifests cover "
                "different case IDs"
            )

        active_arms = tuple(
            arm
            for arm in H1Arm
            if arm
            is not H1Arm.TRACE_ONLY
        )

        factory_counts: dict[
            str,
            int,
        ] = defaultdict(
            int
        )

        def executor_factory(
            public_case: H1PublicCase,
        ):
            case_id = (
                public_case.case_id
            )

            sequence = factory_counts[
                case_id
            ]

            if sequence >= len(
                active_arms
            ):
                raise ContractError(
                    "executor factory invoked too many "
                    "times for case"
                )

            arm = active_arms[
                sequence
            ]

            factory_counts[
                case_id
            ] = sequence + 1

            state[
                "current_case_id"
            ] = case_id

            state[
                "attempted_arm"
            ] = arm.value

            replace_started_disposition()

            truth = H1DevelopmentTruth(
                case_id=case_id,
                hidden_fault_key=(
                    hidden_truth_by_case[
                        case_id
                    ]
                ),
            )

            def execute(
                experiment_key: str,
            ) -> H1ObservedExperiment:
                observed = (
                    execute_development_experiment(
                        public_case=(
                            public_case
                        ),
                        truth=truth,
                        experiment_key=(
                            experiment_key
                        ),
                    )
                )

                state[
                    "observed_events"
                ].append(
                    {
                        "case_id": (
                            case_id
                        ),
                        "attempted_arm": (
                            arm.value
                        ),
                        "executor_instance_sequence": (
                            sequence
                        ),
                        "experiment_key": (
                            observed
                            .experiment_key
                        ),
                        "verdict": (
                            observed
                            .verdict
                            .value
                        ),
                        "actual_cost_units": (
                            observed
                            .actual_cost_units
                        ),
                        "workflow_step_count": (
                            observed
                            .workflow_step_count
                        ),
                        "evidence_sha256": (
                            observed
                            .evidence_sha256
                        ),
                    }
                )

                replace_started_disposition()

                return observed

            return execute

        state["phase"] = (
            "RUN_TREATMENT"
        )

        state[
            "treatment_started"
        ] = True

        state[
            "current_case_id"
        ] = None

        state[
            "attempted_arm"
        ] = None

        replace_started_disposition()

        treatment_batch = (
            run_treatment_batch_from_manifest(
                public_manifest=(
                    public_manifest
                ),
                expected_public_manifest_sha256=(
                    expected_public_manifest_sha256
                ),
                executor_factory=(
                    executor_factory
                ),
            )
        )

        state[
            "current_case_id"
        ] = None

        state[
            "attempted_arm"
        ] = None

        state["phase"] = (
            "PERSIST_TREATMENT"
        )

        state[
            "treatment_batch_sha256"
        ] = treatment_batch.batch_sha256

        replace_started_disposition()

        _atomic_write_new(
            treatment_path,
            treatment_batch.canonical_json_bytes,
            mode=0o600,
        )

        state["phase"] = (
            "RUN_EVALUATION"
        )

        replace_started_disposition()

        evaluation = (
            evaluate_treatment_batch(
                treatment_batch=(
                    treatment_batch
                ),
                hidden_manifest=(
                    hidden_manifest
                ),
                expected_hidden_manifest_sha256=(
                    expected_hidden_manifest_sha256
                ),
            )
        )

        state[
            "evaluation_sha256"
        ] = (
            evaluation.evaluation_sha256
        )

        state["phase"] = (
            "PERSIST_EVALUATION"
        )

        replace_started_disposition()

        _atomic_write_new(
            evaluation_path,
            evaluation.canonical_json_bytes,
            mode=0o600,
        )

        protocol_sha256 = (
            public_manifest.get(
                "protocol_sha256"
            )
        )

        harness_commit_id = (
            public_manifest.get(
                "harness_commit_id"
            )
        )

        _require_sha256(
            protocol_sha256,
            "public_manifest.protocol_sha256",
        )

        _require_commit(
            harness_commit_id,
            "public_manifest.harness_commit_id",
        )

        execution_record = (
            _execution_record_payload(
                batch_id=batch_id,
                attempt_id=attempt_id,
                protocol_sha256=(
                    protocol_sha256
                ),
                harness_commit_id=(
                    harness_commit_id
                ),
                repository_head_commit_id=(
                    repository_head_commit_id
                ),
                d1_contract_commit_id=(
                    d1_contract_commit_id
                ),
                generation_freeze_commit_id=(
                    generation_freeze_commit_id
                ),
                generation_record_sha256=(
                    generation_record_sha256
                ),
                public_manifest_sha256=(
                    expected_public_manifest_sha256
                ),
                hidden_truth_manifest_sha256=(
                    expected_hidden_manifest_sha256
                ),
                environment_module_sha256=(
                    environment_module_sha256
                ),
                treatment_module_sha256=(
                    treatment_module_sha256
                ),
                evaluation_module_sha256=(
                    evaluation_module_sha256
                ),
                execution_persistence_module_sha256=(
                    execution_persistence_module_sha256
                ),
                treatment_batch_sha256=(
                    treatment_batch.batch_sha256
                ),
                evaluation_sha256=(
                    evaluation.evaluation_sha256
                ),
            )
        )

        execution_record_sha256 = (
            canonical_sha256(
                execution_record
            )
        )

        state[
            "execution_record_sha256"
        ] = execution_record_sha256

        state["phase"] = (
            "PERSIST_EXECUTION_RECORD"
        )

        replace_started_disposition()

        _atomic_write_new(
            execution_record_path,
            _json_bytes(
                execution_record
            ),
            mode=0o600,
        )

        state["phase"] = (
            "PERSIST_SUCCESS_DISPOSITION"
        )

        replace_started_disposition()

        _atomic_replace(
            disposition_path,
            _json_bytes(
                disposition(
                    status="SUCCEEDED",
                    phase_override="SUCCEEDED",
                )
            ),
            mode=0o600,
        )

        state["phase"] = (
            "SUCCEEDED"
        )

        return (
            H1ProtectedExecutionPersistenceResult(
                attempt_directory=(
                    attempt_directory
                ),
                treatment_batch_sha256=(
                    treatment_batch
                    .batch_sha256
                ),
                evaluation_sha256=(
                    evaluation
                    .evaluation_sha256
                ),
                execution_record_sha256=(
                    execution_record_sha256
                ),
            )
        )

    except Exception as exc:
        if attempt_claimed:
            failed_phase = str(
                state["phase"]
            )

            try:
                if not public_directory.exists():
                    os.mkdir(
                        public_directory,
                        0o700,
                    )

                    os.chmod(
                        public_directory,
                        0o700,
                    )

                    _fsync_directory(
                        attempt_directory
                    )

                failed_payload = (
                    _disposition_payload(
                        batch_id=batch_id,
                        attempt_id=attempt_id,
                        status="FAILED",
                        phase=failed_phase,
                        repository_head_commit_id=(
                            repository_head_commit_id
                        ),
                        d1_contract_commit_id=(
                            d1_contract_commit_id
                        ),
                        generation_freeze_commit_id=(
                            generation_freeze_commit_id
                        ),
                        generation_record_sha256=(
                            generation_record_sha256
                        ),
                        public_manifest_sha256=(
                            expected_public_manifest_sha256
                        ),
                        hidden_truth_manifest_sha256=(
                            expected_hidden_manifest_sha256
                        ),
                        environment_module_sha256=(
                            environment_module_sha256
                        ),
                        treatment_module_sha256=(
                            treatment_module_sha256
                        ),
                        evaluation_module_sha256=(
                            evaluation_module_sha256
                        ),
                        execution_persistence_module_sha256=(
                            execution_persistence_module_sha256
                        ),
                        treatment_started=bool(
                            state[
                                "treatment_started"
                            ]
                        ),
                        current_case_id=state[
                            "current_case_id"
                        ],
                        attempted_arm=state[
                            "attempted_arm"
                        ],
                        observed_events=state[
                            "observed_events"
                        ],
                        treatment_batch_sha256=state[
                            "treatment_batch_sha256"
                        ],
                        evaluation_sha256=state[
                            "evaluation_sha256"
                        ],
                        execution_record_sha256=state[
                            "execution_record_sha256"
                        ],
                        failure_category=(
                            _failure_category_for_phase(
                                failed_phase
                            )
                        ),
                        failure_type=(
                            type(exc).__name__
                        ),
                    )
                )

                if disposition_path.exists():
                    _atomic_replace(
                        disposition_path,
                        _json_bytes(
                            failed_payload
                        ),
                        mode=0o600,
                    )

                else:
                    _atomic_write_new(
                        disposition_path,
                        _json_bytes(
                            failed_payload
                        ),
                        mode=0o600,
                    )

            except Exception as disposition_exc:
                raise RuntimeError(
                    "protected execution attempt was consumed, "
                    "and FAILED disposition persistence also "
                    "failed "
                    f"({type(disposition_exc).__name__})"
                ) from exc

        raise


__all__ = [
    "EXECUTION_INVALIDATION_CATEGORIES",
    "H1ProtectedExecutionPersistenceResult",
    "persist_h1_protected_execution_attempt",
]
