"""Evaluate same-host, process-isolated VOiCES reproducibility.

B11H strengthens B11F by requiring every complete two-model campaign run to
execute in a separately attested operating-system child process.  A controller
commits each launch before spawning it, observes the child PID and exit status,
and binds the child report to a unique launch challenge.  The child independently
reports its PID, parent PID, execution commitments, timing window, and exact B11F
run-observation identity.

The resulting evidence reports exact and normalized transcript reproduction,
WER/CER drift, runtime conformance, comparison-signal stability, process-link
integrity, and an explainable Process-Isolated Reproduction Index.  It remains
same-host development evidence: it does not establish cross-host reproducibility,
qualification, certification, production readiness, or release authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Iterable, Mapping

from app.adversarial_asr_human_external_voices_repeatability import (
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_MODEL_COUNT,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT,
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT,
    ASRAdversarialVOiCESRepeatabilityBundle,
    ASRAdversarialVOiCESRepeatabilityCaseObservation,
    ASRAdversarialVOiCESRepeatabilityError,
    ASRAdversarialVOiCESRepeatabilityPairKey,
    ASRAdversarialVOiCESRepeatabilityRunObservation,
    evaluate_asr_adversarial_voices_repeatability_v1,
)


ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_KEY = (
    "hetren.asr.adversarial-human-external-voices-"
    "same-host-process-isolated-reproducibility"
)
ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT = (
    ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT
)
ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_AXIS_WEIGHT = 0.25

_PROCESS_RUN_ARTIFACT = {
    "key": (
        "hetren.asr.adversarial-human-external-voices-"
        "process-isolated-run-observation"
    ),
    "version": "1.0.0",
    "type": "content-free-parent-and-child-process-attested-b9-run",
}
_PROCESS_RUN_BOUNDARY = {
    "development_evidence_only": True,
    "content_free_json_evidence_only": True,
    "raw_audio_embedded": False,
    "raw_reference_transcripts_embedded": False,
    "raw_generated_transcripts_embedded": False,
    "same_host_process_observation": True,
    "cross_host_reproducibility_evaluated": False,
    "qualification_threshold_applied": False,
    "release_enforcement_eligible": False,
}
_CHILD_RESULT_ARTIFACT = {
    "key": (
        "hetren.asr.adversarial-human-external-voices-"
        "child-process-result"
    ),
    "version": "1.0.0",
    "type": "content-free-child-reported-b9-run",
}
_CHILD_RESULT_BOUNDARY = {
    "development_evidence_only": True,
    "content_free_json_evidence_only": True,
    "child_process_identity_reported": True,
    "parent_process_observation_attached": False,
    "independent_operating_system_process_verified": False,
    "raw_audio_embedded": False,
    "raw_reference_transcripts_embedded": False,
    "raw_generated_transcripts_embedded": False,
    "qualification_threshold_applied": False,
    "release_enforcement_eligible": False,
}
_ROLES = ("baseline", "candidate")
_ARMS = ("babble", "control")
_SHA256_HEX = frozenset("0123456789abcdef")


class ASRAdversarialVOiCESProcessReproducibilityError(ValueError):
    """Raised when B11H process evidence is incomplete or inconsistent."""


def _require_text(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            f"{name} must be non-empty trimmed text."
        )
    return value


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_HEX for character in value)
    ):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            f"{name} must be a lowercase SHA-256."
        )
    return value


def _require_positive_int(*, name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            f"{name} must be a positive integer."
        )
    return value


def _require_nonnegative_int(*, name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            f"{name} must be a non-negative integer."
        )
    return value


def _require_finite(*, name: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            f"{name} must be finite."
        )
    return float(value)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "VOiCES process evidence must be deterministic JSON."
        ) from error


def _sha256_payload(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _rate_payload(*, successful: int, observed: int) -> dict[str, object]:
    if successful < 0 or observed <= 0 or successful > observed:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "VOiCES process reproduction rate counts are invalid."
        )
    rate = successful / observed
    return {
        "successful_count": successful,
        "observed_count": observed,
        "rate": rate,
        "score_percent": rate * 100.0,
    }


def _mean(values: Iterable[float]) -> float:
    checked = tuple(
        _require_finite(name="VOiCES process score component", value=value)
        for value in values
    )
    if not checked:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "VOiCES process score requires components."
        )
    return math.fsum(checked) / len(checked)


def calculate_python_executable_sha256_v1(
    path: str | Path | None = None,
) -> str:
    """Hash the resolved Python executable used by a B11H child process."""

    selected = Path(sys.executable if path is None else path).resolve()
    if not selected.is_file():
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H Python executable does not exist."
        )
    digest = hashlib.sha256()
    with selected.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESProcessLaunchDefinition:
    """Controller commitment fixed before one child process is spawned."""

    run_id: str
    launch_id: str
    launch_challenge_sha256: str
    controller_invocation_sha256: str
    controller_process_id: int
    source_code_sha256: str
    python_executable_sha256: str
    runtime_environment_sha256: str
    host_environment_sha256: str
    model_set_sha256: str
    matched_control_suite_sha256: str
    adversarial_suite_evidence_sha256: str

    def __post_init__(self) -> None:
        _require_text(name="B11H run id", value=self.run_id)
        _require_text(name="B11H launch id", value=self.launch_id)
        _require_positive_int(
            name="B11H controller process id",
            value=self.controller_process_id,
        )
        for name, value in (
            ("launch challenge", self.launch_challenge_sha256),
            ("controller invocation", self.controller_invocation_sha256),
            ("source code", self.source_code_sha256),
            ("Python executable", self.python_executable_sha256),
            ("runtime environment", self.runtime_environment_sha256),
            ("host environment", self.host_environment_sha256),
            ("model set", self.model_set_sha256),
            ("matched-control suite", self.matched_control_suite_sha256),
            ("adversarial suite", self.adversarial_suite_evidence_sha256),
        ):
            _require_sha256(name=f"B11H {name}", value=value)

    @property
    def fixed_commitment_identity(self) -> tuple[object, ...]:
        return (
            self.controller_invocation_sha256,
            self.controller_process_id,
            self.source_code_sha256,
            self.python_executable_sha256,
            self.runtime_environment_sha256,
            self.host_environment_sha256,
            self.model_set_sha256,
            self.matched_control_suite_sha256,
            self.adversarial_suite_evidence_sha256,
        )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "launch_id": self.launch_id,
            "launch_challenge_sha256": self.launch_challenge_sha256,
            "controller": {
                "invocation_sha256": self.controller_invocation_sha256,
                "process_id": self.controller_process_id,
            },
            "execution_commitments": {
                "source_code_sha256": self.source_code_sha256,
                "python_executable_sha256": self.python_executable_sha256,
                "runtime_environment_sha256": (
                    self.runtime_environment_sha256
                ),
                "host_environment_sha256": self.host_environment_sha256,
                "model_set_sha256": self.model_set_sha256,
                "matched_control_suite_sha256": (
                    self.matched_control_suite_sha256
                ),
                "adversarial_suite_evidence_sha256": (
                    self.adversarial_suite_evidence_sha256
                ),
            },
        }

    @property
    def sha256(self) -> str:
        return _sha256_payload(self.payload)


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESChildProcessReport:
    """Identity and output commitments reported from inside one child."""

    run_id: str
    launch_definition_sha256: str
    launch_challenge_sha256: str
    controller_invocation_sha256: str
    process_id: int
    parent_process_id: int
    started_at_unix_ns: int
    completed_at_unix_ns: int
    source_code_sha256: str
    python_executable_sha256: str
    runtime_environment_sha256: str
    host_environment_sha256: str
    model_set_sha256: str
    run_observation_sha256: str

    def __post_init__(self) -> None:
        _require_text(name="B11H child run id", value=self.run_id)
        for name, value in (
            ("process id", self.process_id),
            ("parent process id", self.parent_process_id),
            ("start time", self.started_at_unix_ns),
            ("completion time", self.completed_at_unix_ns),
        ):
            _require_positive_int(name=f"B11H child {name}", value=value)
        if self.completed_at_unix_ns < self.started_at_unix_ns:
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H child process timeline is invalid."
            )
        for name, value in (
            ("launch definition", self.launch_definition_sha256),
            ("launch challenge", self.launch_challenge_sha256),
            ("controller invocation", self.controller_invocation_sha256),
            ("source code", self.source_code_sha256),
            ("Python executable", self.python_executable_sha256),
            ("runtime environment", self.runtime_environment_sha256),
            ("host environment", self.host_environment_sha256),
            ("model set", self.model_set_sha256),
            ("run observation", self.run_observation_sha256),
        ):
            _require_sha256(name=f"B11H child {name}", value=value)

    @property
    def process_instance_payload(self) -> dict[str, object]:
        return {
            "process_id": self.process_id,
            "parent_process_id": self.parent_process_id,
            "started_at_unix_ns": self.started_at_unix_ns,
        }

    @property
    def process_instance_sha256(self) -> str:
        return _sha256_payload(self.process_instance_payload)

    @property
    def payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "launch_definition_sha256": self.launch_definition_sha256,
            "launch_challenge_sha256": self.launch_challenge_sha256,
            "controller_invocation_sha256": (
                self.controller_invocation_sha256
            ),
            "process": {
                "process_id": self.process_id,
                "parent_process_id": self.parent_process_id,
                "started_at_unix_ns": self.started_at_unix_ns,
                "completed_at_unix_ns": self.completed_at_unix_ns,
                "process_instance_sha256": self.process_instance_sha256,
            },
            "observed_commitments": {
                "source_code_sha256": self.source_code_sha256,
                "python_executable_sha256": self.python_executable_sha256,
                "runtime_environment_sha256": (
                    self.runtime_environment_sha256
                ),
                "host_environment_sha256": self.host_environment_sha256,
                "model_set_sha256": self.model_set_sha256,
                "run_observation_sha256": self.run_observation_sha256,
            },
        }

    @property
    def sha256(self) -> str:
        return _sha256_payload(self.payload)


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESChildProcessResult:
    """Portable child output awaiting the controller's subprocess facts."""

    launch: ASRAdversarialVOiCESProcessLaunchDefinition
    child_report: ASRAdversarialVOiCESChildProcessReport
    run_observation: ASRAdversarialVOiCESRepeatabilityRunObservation

    def __post_init__(self) -> None:
        if not isinstance(
            self.launch,
            ASRAdversarialVOiCESProcessLaunchDefinition,
        ) or not isinstance(
            self.child_report,
            ASRAdversarialVOiCESChildProcessReport,
        ) or not isinstance(
            self.run_observation,
            ASRAdversarialVOiCESRepeatabilityRunObservation,
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H child result requires exact launch, report, and run types."
            )
        launch = self.launch
        child = self.child_report
        run = self.run_observation
        expected = (
            launch.run_id,
            launch.sha256,
            launch.launch_challenge_sha256,
            launch.controller_invocation_sha256,
            launch.controller_process_id,
            launch.source_code_sha256,
            launch.python_executable_sha256,
            launch.runtime_environment_sha256,
            launch.host_environment_sha256,
            launch.model_set_sha256,
            run.sha256,
        )
        observed = (
            child.run_id,
            child.launch_definition_sha256,
            child.launch_challenge_sha256,
            child.controller_invocation_sha256,
            child.parent_process_id,
            child.source_code_sha256,
            child.python_executable_sha256,
            child.runtime_environment_sha256,
            child.host_environment_sha256,
            child.model_set_sha256,
            child.run_observation_sha256,
        )
        if observed != expected:
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H child result launch, process, or output links changed."
            )
        if (
            run.run_id != launch.run_id
            or run.matched_control_suite_sha256
            != launch.matched_control_suite_sha256
            or run.adversarial_suite_evidence_sha256
            != launch.adversarial_suite_evidence_sha256
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H child result cohort links changed."
            )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION
            ),
            "artifact": dict(_CHILD_RESULT_ARTIFACT),
            "launch_definition": self.launch.payload,
            "launch_definition_sha256": self.launch.sha256,
            "child_report": self.child_report.payload,
            "child_report_sha256": self.child_report.sha256,
            "run_observation": self.run_observation.payload,
            "run_observation_sha256": self.run_observation.sha256,
            "evidence_boundary": dict(_CHILD_RESULT_BOUNDARY),
        }

    @property
    def sha256(self) -> str:
        return _sha256_payload(self.payload)


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESProcessLaunchObservation:
    """Parent-observed launch joined to the exact child report."""

    launch: ASRAdversarialVOiCESProcessLaunchDefinition
    child_report: ASRAdversarialVOiCESChildProcessReport
    parent_spawn_started_at_unix_ns: int
    parent_observed_child_process_id: int
    parent_observed_exit_code: int
    parent_observed_completed_at_unix_ns: int

    def __post_init__(self) -> None:
        if not isinstance(
            self.launch,
            ASRAdversarialVOiCESProcessLaunchDefinition,
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H launch definition type is invalid."
            )
        if not isinstance(
            self.child_report,
            ASRAdversarialVOiCESChildProcessReport,
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H child report type is invalid."
            )
        _require_positive_int(
            name="B11H parent spawn start",
            value=self.parent_spawn_started_at_unix_ns,
        )
        _require_positive_int(
            name="B11H parent-observed child process id",
            value=self.parent_observed_child_process_id,
        )
        _require_nonnegative_int(
            name="B11H parent-observed exit code",
            value=self.parent_observed_exit_code,
        )
        _require_positive_int(
            name="B11H parent completion time",
            value=self.parent_observed_completed_at_unix_ns,
        )
        child = self.child_report
        launch = self.launch
        if self.parent_observed_exit_code != 0:
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H child process did not exit successfully."
            )
        if (
            self.parent_spawn_started_at_unix_ns
            > child.started_at_unix_ns
            or child.completed_at_unix_ns
            > self.parent_observed_completed_at_unix_ns
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H parent and child process timeline is invalid."
            )
        expected = (
            launch.run_id,
            launch.sha256,
            launch.launch_challenge_sha256,
            launch.controller_invocation_sha256,
            self.parent_observed_child_process_id,
            launch.controller_process_id,
            launch.source_code_sha256,
            launch.python_executable_sha256,
            launch.runtime_environment_sha256,
            launch.host_environment_sha256,
            launch.model_set_sha256,
        )
        observed = (
            child.run_id,
            child.launch_definition_sha256,
            child.launch_challenge_sha256,
            child.controller_invocation_sha256,
            child.process_id,
            child.parent_process_id,
            child.source_code_sha256,
            child.python_executable_sha256,
            child.runtime_environment_sha256,
            child.host_environment_sha256,
            child.model_set_sha256,
        )
        if observed != expected:
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H parent-child process identity or commitment changed."
            )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "launch_definition": self.launch.payload,
            "launch_definition_sha256": self.launch.sha256,
            "parent_observation": {
                "spawn_started_at_unix_ns": (
                    self.parent_spawn_started_at_unix_ns
                ),
                "observed_child_process_id": (
                    self.parent_observed_child_process_id
                ),
                "observed_exit_code": self.parent_observed_exit_code,
                "completed_at_unix_ns": (
                    self.parent_observed_completed_at_unix_ns
                ),
            },
            "child_report": self.child_report.payload,
            "child_report_sha256": self.child_report.sha256,
        }

    @property
    def sha256(self) -> str:
        return _sha256_payload(self.payload)


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESProcessRunObservation:
    """One complete B9 run with verified parent-child process linkage."""

    process_launch: ASRAdversarialVOiCESProcessLaunchObservation
    run_observation: ASRAdversarialVOiCESRepeatabilityRunObservation

    def __post_init__(self) -> None:
        if not isinstance(
            self.process_launch,
            ASRAdversarialVOiCESProcessLaunchObservation,
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H process launch observation type is invalid."
            )
        if not isinstance(
            self.run_observation,
            ASRAdversarialVOiCESRepeatabilityRunObservation,
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H run observation type is invalid."
            )
        launch = self.process_launch.launch
        child = self.process_launch.child_report
        run = self.run_observation
        if (
            run.run_id != launch.run_id
            or run.run_id != child.run_id
            or run.sha256 != child.run_observation_sha256
            or run.matched_control_suite_sha256
            != launch.matched_control_suite_sha256
            or run.adversarial_suite_evidence_sha256
            != launch.adversarial_suite_evidence_sha256
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H process launch and run observation links changed."
            )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION
            ),
            "artifact": dict(_PROCESS_RUN_ARTIFACT),
            "process_launch": self.process_launch.payload,
            "run_observation": self.run_observation.payload,
            "run_observation_sha256": self.run_observation.sha256,
            "evidence_boundary": dict(_PROCESS_RUN_BOUNDARY),
        }

    @property
    def sha256(self) -> str:
        return _sha256_payload(self.payload)


def capture_asr_adversarial_voices_child_process_report_v1(
    *,
    launch: ASRAdversarialVOiCESProcessLaunchDefinition,
    run_observation: ASRAdversarialVOiCESRepeatabilityRunObservation,
    child_started_at_unix_ns: int,
    observed_source_code_sha256: str,
    observed_runtime_environment_sha256: str,
    observed_host_environment_sha256: str,
    observed_model_set_sha256: str,
    python_executable_path: str | Path | None = None,
    child_completed_at_unix_ns: int | None = None,
) -> ASRAdversarialVOiCESChildProcessReport:
    """Capture actual PID/PPID and executable identity inside a child."""

    if not isinstance(
        launch,
        ASRAdversarialVOiCESProcessLaunchDefinition,
    ) or not isinstance(
        run_observation,
        ASRAdversarialVOiCESRepeatabilityRunObservation,
    ):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H child capture requires exact launch and run contracts."
        )
    completed = (
        time.time_ns()
        if child_completed_at_unix_ns is None
        else child_completed_at_unix_ns
    )
    observed_executable = calculate_python_executable_sha256_v1(
        python_executable_path
    )
    actual = (
        observed_source_code_sha256,
        observed_executable,
        observed_runtime_environment_sha256,
        observed_host_environment_sha256,
        observed_model_set_sha256,
    )
    expected = (
        launch.source_code_sha256,
        launch.python_executable_sha256,
        launch.runtime_environment_sha256,
        launch.host_environment_sha256,
        launch.model_set_sha256,
    )
    if actual != expected:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H child execution commitments do not match its launch."
        )
    if os.getppid() != launch.controller_process_id:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H child is not linked to the declared controller process."
        )
    return ASRAdversarialVOiCESChildProcessReport(
        run_id=launch.run_id,
        launch_definition_sha256=launch.sha256,
        launch_challenge_sha256=launch.launch_challenge_sha256,
        controller_invocation_sha256=launch.controller_invocation_sha256,
        process_id=os.getpid(),
        parent_process_id=os.getppid(),
        started_at_unix_ns=child_started_at_unix_ns,
        completed_at_unix_ns=completed,
        source_code_sha256=observed_source_code_sha256,
        python_executable_sha256=observed_executable,
        runtime_environment_sha256=observed_runtime_environment_sha256,
        host_environment_sha256=observed_host_environment_sha256,
        model_set_sha256=observed_model_set_sha256,
        run_observation_sha256=run_observation.sha256,
    )


def build_asr_adversarial_voices_child_process_result_v1(
    *,
    launch: ASRAdversarialVOiCESProcessLaunchDefinition,
    child_report: ASRAdversarialVOiCESChildProcessReport,
    run_observation: ASRAdversarialVOiCESRepeatabilityRunObservation,
) -> ASRAdversarialVOiCESChildProcessResult:
    """Build the content-free file a B11H child returns to its parent."""

    return ASRAdversarialVOiCESChildProcessResult(
        launch=launch,
        child_report=child_report,
        run_observation=run_observation,
    )


def finalize_asr_adversarial_voices_process_run_v1(
    *,
    launch: ASRAdversarialVOiCESProcessLaunchDefinition,
    child_report: ASRAdversarialVOiCESChildProcessReport,
    run_observation: ASRAdversarialVOiCESRepeatabilityRunObservation,
    parent_spawn_started_at_unix_ns: int,
    parent_observed_child_process_id: int,
    parent_observed_exit_code: int,
    parent_observed_completed_at_unix_ns: int,
) -> ASRAdversarialVOiCESProcessRunObservation:
    """Join parent subprocess observations to one child-produced B9 run."""

    return ASRAdversarialVOiCESProcessRunObservation(
        process_launch=ASRAdversarialVOiCESProcessLaunchObservation(
            launch=launch,
            child_report=child_report,
            parent_spawn_started_at_unix_ns=(
                parent_spawn_started_at_unix_ns
            ),
            parent_observed_child_process_id=(
                parent_observed_child_process_id
            ),
            parent_observed_exit_code=parent_observed_exit_code,
            parent_observed_completed_at_unix_ns=(
                parent_observed_completed_at_unix_ns
            ),
        ),
        run_observation=run_observation,
    )


def finalize_asr_adversarial_voices_child_process_result_v1(
    *,
    child_result: ASRAdversarialVOiCESChildProcessResult,
    parent_spawn_started_at_unix_ns: int,
    parent_observed_child_process_id: int,
    parent_observed_exit_code: int,
    parent_observed_completed_at_unix_ns: int,
) -> ASRAdversarialVOiCESProcessRunObservation:
    """Attach controller-observed subprocess facts to a child result file."""

    if not isinstance(
        child_result,
        ASRAdversarialVOiCESChildProcessResult,
    ):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H finalization requires an exact child process result."
        )
    return finalize_asr_adversarial_voices_process_run_v1(
        launch=child_result.launch,
        child_report=child_result.child_report,
        run_observation=child_result.run_observation,
        parent_spawn_started_at_unix_ns=parent_spawn_started_at_unix_ns,
        parent_observed_child_process_id=parent_observed_child_process_id,
        parent_observed_exit_code=parent_observed_exit_code,
        parent_observed_completed_at_unix_ns=(
            parent_observed_completed_at_unix_ns
        ),
    )


def _renamed_reproduction_aggregate(
    repeatability: ASRAdversarialVOiCESRepeatabilityBundle,
) -> dict[str, object]:
    source = repeatability.aggregate

    def rename_unit(value: Mapping[str, object]) -> dict[str, object]:
        return {
            "unit_count": value["unit_count"],
            "exact_transcript_reproduction": value[
                "exact_transcript_repeatability"
            ],
            "normalized_transcript_reproduction": value[
                "normalized_transcript_repeatability"
            ],
            "runtime_identity_conformance": value[
                "runtime_identity_conformance"
            ],
            "wer_reproduction": value["wer_stability"],
            "cer_reproduction": value["cer_stability"],
            "wer_cross_process_drift_envelope": value[
                "wer_drift_envelope"
            ],
            "cer_cross_process_drift_envelope": value[
                "cer_drift_envelope"
            ],
        }

    return {
        "overall": rename_unit(source["overall"]),
        "models": {
            role: rename_unit(source["models"][role])
            for role in _ROLES
        },
        "comparison_signal_reproduction": source[
            "comparison_signal_stability"
        ],
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESProcessReproducibilityBundle:
    """Descriptive B11H evidence over three independently spawned children."""

    runs: tuple[ASRAdversarialVOiCESProcessRunObservation, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.runs, tuple)
            or len(self.runs)
            != ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT
            or any(
                not isinstance(
                    value,
                    ASRAdversarialVOiCESProcessRunObservation,
                )
                for value in self.runs
            )
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "VOiCES B11H requires exactly three process-run observations."
            )
        launches = tuple(value.process_launch.launch for value in self.runs)
        reports = tuple(
            value.process_launch.child_report for value in self.runs
        )
        if len({value.run_id for value in launches}) != len(launches):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H run identities must be unique."
            )
        if len({value.launch_id for value in launches}) != len(launches):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H launch identities must be unique."
            )
        if len({value.launch_challenge_sha256 for value in launches}) != len(
            launches
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H launch challenges must be unique."
            )
        if len({value.process_instance_sha256 for value in reports}) != len(
            reports
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H child process instances must be unique."
            )
        anchor = launches[0]
        if any(
            value.fixed_commitment_identity
            != anchor.fixed_commitment_identity
            for value in launches[1:]
        ):
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H controller or fixed execution commitments changed."
            )
        try:
            evaluate_asr_adversarial_voices_repeatability_v1(
                runs=tuple(value.run_observation for value in self.runs)
            )
        except ASRAdversarialVOiCESRepeatabilityError as error:
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H process runs failed B11F cohort and output validation."
            ) from error

    @property
    def repeatability(self) -> ASRAdversarialVOiCESRepeatabilityBundle:
        return evaluate_asr_adversarial_voices_repeatability_v1(
            runs=tuple(value.run_observation for value in self.runs)
        )

    @property
    def process_integrity(self) -> dict[str, object]:
        observed = len(self.runs)
        return {
            "parent_child_pid_link_conformance": _rate_payload(
                successful=observed,
                observed=observed,
            ),
            "unique_launch_challenge_conformance": _rate_payload(
                successful=len(
                    {
                        value.process_launch.launch.launch_challenge_sha256
                        for value in self.runs
                    }
                ),
                observed=observed,
            ),
            "distinct_process_instance_conformance": _rate_payload(
                successful=len(
                    {
                        value.process_launch.child_report.process_instance_sha256
                        for value in self.runs
                    }
                ),
                observed=observed,
            ),
            "clean_child_exit_conformance": _rate_payload(
                successful=sum(
                    value.process_launch.parent_observed_exit_code == 0
                    for value in self.runs
                ),
                observed=observed,
            ),
            "fixed_execution_commitment_conformance": _rate_payload(
                successful=observed,
                observed=observed,
            ),
        }

    @property
    def reproduction(self) -> dict[str, object]:
        reproduced = _renamed_reproduction_aggregate(self.repeatability)
        overall = reproduced["overall"]
        signals = reproduced["comparison_signal_reproduction"]
        process = self.process_integrity
        output_axis = _mean(
            (
                overall["exact_transcript_reproduction"]["score_percent"],
                overall["normalized_transcript_reproduction"][
                    "score_percent"
                ],
            )
        )
        metric_axis = _mean(
            (
                overall["wer_reproduction"]["score_percent"],
                overall["cer_reproduction"]["score_percent"],
            )
        )
        execution_axis = _mean(
            (
                overall["runtime_identity_conformance"]["score_percent"],
                *(
                    value["score_percent"]
                    for value in process.values()
                ),
            )
        )
        signal_success = sum(
            value["metric_stable"] and value["direction_stable"]
            for value in signals.values()
        )
        signal_rate = _rate_payload(
            successful=signal_success,
            observed=len(signals),
        )
        axes = {
            "output_identity": {
                "weight": ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_AXIS_WEIGHT,
                "score_percent": output_axis,
            },
            "metric_stability": {
                "weight": ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_AXIS_WEIGHT,
                "score_percent": metric_axis,
            },
            "execution_and_process_integrity": {
                "weight": ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_AXIS_WEIGHT,
                "score_percent": execution_axis,
            },
            "comparison_signal_stability": {
                "weight": ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_AXIS_WEIGHT,
                "score_percent": signal_rate["score_percent"],
            },
        }
        index = math.fsum(
            value["weight"] * value["score_percent"]
            for value in axes.values()
        )
        hard_conditions = {
            "all_exact_transcripts_reproduced": (
                overall["exact_transcript_reproduction"]["successful_count"]
                == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            ),
            "all_normalized_transcripts_reproduced": (
                overall["normalized_transcript_reproduction"][
                    "successful_count"
                ]
                == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            ),
            "all_wer_values_reproduced": (
                overall["wer_reproduction"]["successful_count"]
                == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            ),
            "all_cer_values_reproduced": (
                overall["cer_reproduction"]["successful_count"]
                == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            ),
            "all_runtime_identities_conformant": (
                overall["runtime_identity_conformance"]["successful_count"]
                == ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
            ),
            "all_comparison_signals_reproduced": (
                signal_success == len(signals)
            ),
            "all_process_integrity_checks_passed": all(
                value["successful_count"] == value["observed_count"]
                for value in process.values()
            ),
        }
        return {
            **reproduced,
            "process_integrity": process,
            "comparison_signal_reproduction_rate": signal_rate,
            "process_isolated_reproduction_index": {
                "scale": "0_to_100",
                "aggregation": "equal_weight_macro_mean_over_four_axes",
                "axes": axes,
                "score_percent": index,
                "hard_conditions": hard_conditions,
                "hard_conditions_all_passed": all(hard_conditions.values()),
                "qualification_threshold_applied": False,
            },
        }

    @property
    def status(self) -> str:
        if self.reproduction["process_isolated_reproduction_index"][
            "hard_conditions_all_passed"
        ]:
            return "reproduced"
        return "variation_observed"

    @property
    def payload(self) -> dict[str, object]:
        repeatability = self.repeatability
        anchor = self.runs[0].process_launch.launch
        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION
            ),
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_KEY,
                "version": ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_VERSION,
                "type": "same_host_process_isolated_reproducibility_evidence",
            },
            "protocol": {
                "expected_process_run_count": (
                    ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_RUN_COUNT
                ),
                "controller_precommits_each_launch": True,
                "unique_challenge_per_launch": True,
                "parent_observes_child_pid_and_exit": True,
                "child_reports_pid_parent_pid_and_commitments": True,
                "parent_child_pid_equality_required": True,
                "child_parent_pid_equals_controller_required": True,
                "distinct_process_instance_commitment_required": True,
                "fixed_source_runtime_host_model_and_cohort_required": True,
                "process_timeline_containment_required": True,
                "comparison_direction": "candidate_minus_baseline",
                "lower_error_values_are_better": True,
            },
            "upstream": {
                "matched_control_suite_sha256": (
                    anchor.matched_control_suite_sha256
                ),
                "adversarial_suite_evidence_sha256": (
                    anchor.adversarial_suite_evidence_sha256
                ),
                "ordered_process_run_sha256s": [
                    value.sha256 for value in self.runs
                ],
                "ordered_b11f_run_observation_sha256s": [
                    value.run_observation.sha256 for value in self.runs
                ],
                "ordered_b9_execution_sha256s": [
                    value.run_observation.execution_sha256
                    for value in self.runs
                ],
            },
            "status": self.status,
            "models": repeatability.payload["models"],
            "population": {
                "process_run_count": len(self.runs),
                "model_count": ASR_ADVERSARIAL_VOICES_REPEATABILITY_MODEL_COUNT,
                "case_count_per_model": (
                    ASR_ADVERSARIAL_VOICES_REPEATABILITY_CASE_COUNT
                ),
                "case_model_unit_count": (
                    ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
                ),
                "execution_count": (
                    ASR_ADVERSARIAL_VOICES_REPEATABILITY_RUN_COUNT
                    * ASR_ADVERSARIAL_VOICES_REPEATABILITY_UNIT_COUNT
                ),
                "ordered_run_ids": [
                    value.run_observation.run_id for value in self.runs
                ],
                "ordered_process_instance_sha256s": [
                    value.process_launch.child_report.process_instance_sha256
                    for value in self.runs
                ],
            },
            "execution_commitments": {
                "controller_invocation_sha256": (
                    anchor.controller_invocation_sha256
                ),
                "source_code_sha256": anchor.source_code_sha256,
                "python_executable_sha256": (
                    anchor.python_executable_sha256
                ),
                "runtime_environment_sha256": (
                    anchor.runtime_environment_sha256
                ),
                "host_environment_sha256": (
                    anchor.host_environment_sha256
                ),
                "model_set_sha256": anchor.model_set_sha256,
            },
            "process_runs": [value.payload for value in self.runs],
            "reproducibility": {
                "engineer_metrics": {
                    "exact_transcript_reproduction": (
                        "Exact transcript commitment equality across child processes."
                    ),
                    "normalized_transcript_reproduction": (
                        "Normalized transcript commitment equality across children."
                    ),
                    "cross_process_metric_drift_envelope": (
                        "Maximum and macro-mean WER/CER range across processes."
                    ),
                    "process_integrity": (
                        "Parent-child PID, challenge, exit, and commitment checks."
                    ),
                    "comparison_signal_reproduction": (
                        "Aggregate metric and candidate-direction stability."
                    ),
                    "process_isolated_reproduction_index": (
                        "Equal-weight output, metric, execution, and signal score."
                    ),
                },
                "aggregate": self.reproduction,
            },
            "evidence_boundary": {
                "development_evidence_only": True,
                "content_free_json_evidence_only": True,
                "complete_b11f_run_observations_reverified": True,
                "controller_precommitments_verified": True,
                "parent_child_process_links_verified": True,
                "independent_operating_system_processes_verified": True,
                "same_host_process_isolated_reproducibility_evaluated": True,
                "same_host_process_reproducibility_verified": (
                    self.status == "reproduced"
                ),
                "cross_host_reproducibility_evaluated": False,
                "cross_host_reproducibility_verified": None,
                "reproducibility_verified": None,
                "cross_host_reproducibility_claimed": False,
                "raw_audio_embedded": False,
                "raw_reference_transcripts_embedded": False,
                "raw_generated_transcripts_embedded": False,
                "process_reproduction_threshold_applied": False,
                "qualification_threshold_applied": False,
                "statistical_generalization_claimed": False,
                "model_winner_declared": False,
                "certification_issued": False,
                "production_qualified": False,
                "release_enforcement_eligible": False,
                "official_release_verdict_modified": False,
                "v1_reliability_scorecard_modified": False,
            },
        }

    @property
    def sha256(self) -> str:
        return _sha256_payload(self.payload)

    def require_same_host_process_reproducibility_verified(self) -> None:
        if self.status != "reproduced":
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                "B11H same-host process reproduction contains variation."
            )

    def require_cross_host_reproducibility_verified(self) -> None:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "Same-host child processes cannot establish cross-host reproducibility."
        )

    def require_process_reproduction_qualification(self) -> None:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H is descriptive process evidence; no qualification threshold "
            "or release verdict was applied."
        )


def evaluate_asr_adversarial_voices_process_reproducibility_v1(
    *,
    runs: tuple[ASRAdversarialVOiCESProcessRunObservation, ...],
) -> ASRAdversarialVOiCESProcessReproducibilityBundle:
    """Evaluate three complete, parent-observed child-process runs."""

    return ASRAdversarialVOiCESProcessReproducibilityBundle(runs=runs)


def _require_exact_keys(
    value: object,
    *,
    keys: tuple[str, ...],
    name: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            f"{name} must contain exactly {list(keys)}."
        )
    return value


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ASRAdversarialVOiCESProcessReproducibilityError(
                f"B11H JSON contains duplicate key {key!r}."
            )
        result[key] = value
    return result


def _reject_non_finite(value: str) -> object:
    raise ASRAdversarialVOiCESProcessReproducibilityError(
        f"B11H JSON contains non-finite value {value}."
    )


def _parse_json(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes) or not raw:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H process-run evidence must be non-empty bytes."
        )
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except ASRAdversarialVOiCESProcessReproducibilityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H process-run evidence is not valid UTF-8 JSON."
        ) from error
    if not isinstance(value, dict):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H process-run JSON root must be an object."
        )
    return value


def _parse_pair_key(value: object) -> ASRAdversarialVOiCESRepeatabilityPairKey:
    pair = _require_exact_keys(
        value,
        keys=("source_key", "room", "microphone_id", "angle_degrees"),
        name="B11H pair key",
    )
    source = pair["source_key"]
    if (
        not isinstance(source, list)
        or len(source) != 3
        or any(
            isinstance(item, bool)
            or not isinstance(item, int)
            or item <= 0
            for item in source
        )
    ):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H pair source key is invalid."
        )
    return ASRAdversarialVOiCESRepeatabilityPairKey(
        source_key=tuple(source),
        room=_require_text(name="B11H pair room", value=pair["room"]),
        microphone_id=_require_positive_int(
            name="B11H pair microphone id",
            value=pair["microphone_id"],
        ),
        angle_degrees=_require_positive_int(
            name="B11H pair angle",
            value=pair["angle_degrees"],
        ),
    )


def _parse_case(
    value: object,
    *,
    run_id: str,
) -> ASRAdversarialVOiCESRepeatabilityCaseObservation:
    case = _require_exact_keys(
        value,
        keys=(
            "role",
            "provider_key",
            "model_key",
            "case_id",
            "arm",
            "pair_key",
            "fixed_inputs",
            "outputs",
            "metrics",
        ),
        name="B11H run case",
    )
    fixed = _require_exact_keys(
        case["fixed_inputs"],
        keys=(
            "audio_asset_sha256",
            "reference_transcript_sha256",
            "normalized_reference_utf8_sha256",
        ),
        name="B11H fixed inputs",
    )
    outputs = _require_exact_keys(
        case["outputs"],
        keys=(
            "execution_environment_sha256",
            "execution_evidence_sha256",
            "generated_transcript_sha256",
            "normalized_generated_utf8_sha256",
        ),
        name="B11H case outputs",
    )
    metrics = _require_exact_keys(
        case["metrics"],
        keys=("wer", "cer"),
        name="B11H case metrics",
    )
    role = _require_text(name="B11H case role", value=case["role"])
    arm = _require_text(name="B11H case arm", value=case["arm"])
    if role not in _ROLES or arm not in _ARMS:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H case role or arm is invalid."
        )
    return ASRAdversarialVOiCESRepeatabilityCaseObservation(
        run_id=run_id,
        role=role,
        provider_key=_require_text(
            name="B11H case provider",
            value=case["provider_key"],
        ),
        model_key=_require_text(
            name="B11H case model",
            value=case["model_key"],
        ),
        pair_key=_parse_pair_key(case["pair_key"]),
        arm=arm,
        case_id=_require_text(
            name="B11H case id",
            value=case["case_id"],
        ),
        audio_asset_sha256=_require_sha256(
            name="B11H audio asset",
            value=fixed["audio_asset_sha256"],
        ),
        reference_transcript_sha256=_require_sha256(
            name="B11H reference transcript",
            value=fixed["reference_transcript_sha256"],
        ),
        normalized_reference_sha256=_require_sha256(
            name="B11H normalized reference",
            value=fixed["normalized_reference_utf8_sha256"],
        ),
        execution_environment_sha256=_require_sha256(
            name="B11H execution environment",
            value=outputs["execution_environment_sha256"],
        ),
        execution_evidence_sha256=_require_sha256(
            name="B11H execution evidence",
            value=outputs["execution_evidence_sha256"],
        ),
        generated_transcript_sha256=_require_sha256(
            name="B11H generated transcript",
            value=outputs["generated_transcript_sha256"],
        ),
        normalized_generated_sha256=_require_sha256(
            name="B11H normalized generated transcript",
            value=outputs["normalized_generated_utf8_sha256"],
        ),
        wer=_require_finite(name="B11H WER", value=metrics["wer"]),
        cer=_require_finite(name="B11H CER", value=metrics["cer"]),
    )


def _parse_run_observation(
    value: object,
) -> ASRAdversarialVOiCESRepeatabilityRunObservation:
    run = _require_exact_keys(
        value,
        keys=(
            "run_id",
            "execution_sha256",
            "upstream",
            "models",
            "case_model_units",
            "comparison_signals",
        ),
        name="B11H B11F run observation",
    )
    run_id = _require_text(name="B11H run id", value=run["run_id"])
    upstream = _require_exact_keys(
        run["upstream"],
        keys=(
            "matched_control_suite_sha256",
            "adversarial_suite_evidence_sha256",
        ),
        name="B11H run upstream",
    )
    models = _require_exact_keys(
        run["models"],
        keys=_ROLES,
        name="B11H run models",
    )

    def parse_model(role: str) -> dict[str, object]:
        return _require_exact_keys(
            models[role],
            keys=(
                "campaign_id",
                "campaign_version",
                "campaign_sha256",
                "metrics_sha256",
                "provider_key",
                "model_key",
            ),
            name=f"B11H {role} model",
        )

    baseline = parse_model("baseline")
    candidate = parse_model("candidate")
    cases_value = run["case_model_units"]
    if not isinstance(cases_value, list):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H case-model units must be a list."
        )
    signals = _require_exact_keys(
        run["comparison_signals"],
        keys=(
            "general_accuracy_candidate_minus_baseline",
            "matched_control_robustness_candidate_minus_baseline",
        ),
        name="B11H comparison signals",
    )
    general = _require_exact_keys(
        signals["general_accuracy_candidate_minus_baseline"],
        keys=("wer", "cer"),
        name="B11H general comparison",
    )
    robust = _require_exact_keys(
        signals["matched_control_robustness_candidate_minus_baseline"],
        keys=("wer", "cer"),
        name="B11H robustness comparison",
    )

    def text(model: dict[str, object], key: str, role: str) -> str:
        return _require_text(
            name=f"B11H {role} {key}",
            value=model[key],
        )

    def sha(model: dict[str, object], key: str, role: str) -> str:
        return _require_sha256(
            name=f"B11H {role} {key}",
            value=model[key],
        )

    return ASRAdversarialVOiCESRepeatabilityRunObservation(
        run_id=run_id,
        execution_sha256=_require_sha256(
            name="B11H B9 execution",
            value=run["execution_sha256"],
        ),
        matched_control_suite_sha256=_require_sha256(
            name="B11H matched-control suite",
            value=upstream["matched_control_suite_sha256"],
        ),
        adversarial_suite_evidence_sha256=_require_sha256(
            name="B11H adversarial suite",
            value=upstream["adversarial_suite_evidence_sha256"],
        ),
        baseline_campaign_id=text(baseline, "campaign_id", "baseline"),
        baseline_campaign_version=text(
            baseline,
            "campaign_version",
            "baseline",
        ),
        baseline_campaign_sha256=sha(
            baseline,
            "campaign_sha256",
            "baseline",
        ),
        baseline_metrics_sha256=sha(
            baseline,
            "metrics_sha256",
            "baseline",
        ),
        baseline_provider_key=text(baseline, "provider_key", "baseline"),
        baseline_model_key=text(baseline, "model_key", "baseline"),
        candidate_campaign_id=text(candidate, "campaign_id", "candidate"),
        candidate_campaign_version=text(
            candidate,
            "campaign_version",
            "candidate",
        ),
        candidate_campaign_sha256=sha(
            candidate,
            "campaign_sha256",
            "candidate",
        ),
        candidate_metrics_sha256=sha(
            candidate,
            "metrics_sha256",
            "candidate",
        ),
        candidate_provider_key=text(candidate, "provider_key", "candidate"),
        candidate_model_key=text(candidate, "model_key", "candidate"),
        cases=tuple(_parse_case(item, run_id=run_id) for item in cases_value),
        general_accuracy_wer_differential=_require_finite(
            name="B11H general WER differential",
            value=general["wer"],
        ),
        general_accuracy_cer_differential=_require_finite(
            name="B11H general CER differential",
            value=general["cer"],
        ),
        robustness_wer_differential=_require_finite(
            name="B11H robustness WER differential",
            value=robust["wer"],
        ),
        robustness_cer_differential=_require_finite(
            name="B11H robustness CER differential",
            value=robust["cer"],
        ),
    )


def _parse_launch(value: object) -> ASRAdversarialVOiCESProcessLaunchDefinition:
    launch = _require_exact_keys(
        value,
        keys=(
            "run_id",
            "launch_id",
            "launch_challenge_sha256",
            "controller",
            "execution_commitments",
        ),
        name="B11H launch definition",
    )
    controller = _require_exact_keys(
        launch["controller"],
        keys=("invocation_sha256", "process_id"),
        name="B11H launch controller",
    )
    commitments = _require_exact_keys(
        launch["execution_commitments"],
        keys=(
            "source_code_sha256",
            "python_executable_sha256",
            "runtime_environment_sha256",
            "host_environment_sha256",
            "model_set_sha256",
            "matched_control_suite_sha256",
            "adversarial_suite_evidence_sha256",
        ),
        name="B11H launch commitments",
    )
    return ASRAdversarialVOiCESProcessLaunchDefinition(
        run_id=_require_text(name="B11H launch run id", value=launch["run_id"]),
        launch_id=_require_text(name="B11H launch id", value=launch["launch_id"]),
        launch_challenge_sha256=_require_sha256(
            name="B11H launch challenge",
            value=launch["launch_challenge_sha256"],
        ),
        controller_invocation_sha256=_require_sha256(
            name="B11H controller invocation",
            value=controller["invocation_sha256"],
        ),
        controller_process_id=_require_positive_int(
            name="B11H controller process id",
            value=controller["process_id"],
        ),
        **{
            key: _require_sha256(name=f"B11H {key}", value=commitments[key])
            for key in commitments
        },
    )


def _parse_child_report(
    value: object,
) -> ASRAdversarialVOiCESChildProcessReport:
    report = _require_exact_keys(
        value,
        keys=(
            "run_id",
            "launch_definition_sha256",
            "launch_challenge_sha256",
            "controller_invocation_sha256",
            "process",
            "observed_commitments",
        ),
        name="B11H child report",
    )
    process = _require_exact_keys(
        report["process"],
        keys=(
            "process_id",
            "parent_process_id",
            "started_at_unix_ns",
            "completed_at_unix_ns",
            "process_instance_sha256",
        ),
        name="B11H child process",
    )
    commitments = _require_exact_keys(
        report["observed_commitments"],
        keys=(
            "source_code_sha256",
            "python_executable_sha256",
            "runtime_environment_sha256",
            "host_environment_sha256",
            "model_set_sha256",
            "run_observation_sha256",
        ),
        name="B11H child commitments",
    )
    observed = ASRAdversarialVOiCESChildProcessReport(
        run_id=_require_text(name="B11H child run id", value=report["run_id"]),
        launch_definition_sha256=_require_sha256(
            name="B11H child launch definition",
            value=report["launch_definition_sha256"],
        ),
        launch_challenge_sha256=_require_sha256(
            name="B11H child challenge",
            value=report["launch_challenge_sha256"],
        ),
        controller_invocation_sha256=_require_sha256(
            name="B11H child controller invocation",
            value=report["controller_invocation_sha256"],
        ),
        process_id=_require_positive_int(
            name="B11H child process id",
            value=process["process_id"],
        ),
        parent_process_id=_require_positive_int(
            name="B11H child parent process id",
            value=process["parent_process_id"],
        ),
        started_at_unix_ns=_require_positive_int(
            name="B11H child start",
            value=process["started_at_unix_ns"],
        ),
        completed_at_unix_ns=_require_positive_int(
            name="B11H child completion",
            value=process["completed_at_unix_ns"],
        ),
        **{
            key: _require_sha256(
                name=f"B11H child {key}",
                value=commitments[key],
            )
            for key in commitments
        },
    )
    if process["process_instance_sha256"] != observed.process_instance_sha256:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H child process-instance identity changed."
        )
    return observed


def load_asr_adversarial_voices_process_launch_definition_v1(
    raw: bytes,
) -> ASRAdversarialVOiCESProcessLaunchDefinition:
    """Load the exact pre-spawn launch commitment received by a child."""

    return _parse_launch(_parse_json(raw))


def load_asr_adversarial_voices_child_process_result_v1(
    raw: bytes,
) -> ASRAdversarialVOiCESChildProcessResult:
    """Load and revalidate the portable result emitted inside one child."""

    root = _require_exact_keys(
        _parse_json(raw),
        keys=(
            "schema_version",
            "artifact",
            "launch_definition",
            "launch_definition_sha256",
            "child_report",
            "child_report_sha256",
            "run_observation",
            "run_observation_sha256",
            "evidence_boundary",
        ),
        name="B11H child-result root",
    )
    if (
        root["schema_version"]
        != ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION
        or root["artifact"] != _CHILD_RESULT_ARTIFACT
        or root["evidence_boundary"] != _CHILD_RESULT_BOUNDARY
    ):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H child-result schema, artifact, or boundary changed."
        )
    launch = _parse_launch(root["launch_definition"])
    child = _parse_child_report(root["child_report"])
    run = _parse_run_observation(root["run_observation"])
    if (
        root["launch_definition_sha256"] != launch.sha256
        or root["child_report_sha256"] != child.sha256
        or root["run_observation_sha256"] != run.sha256
    ):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H child-result derived identity changed."
        )
    return ASRAdversarialVOiCESChildProcessResult(
        launch=launch,
        child_report=child,
        run_observation=run,
    )


def _parse_process_launch(
    value: object,
) -> ASRAdversarialVOiCESProcessLaunchObservation:
    observed = _require_exact_keys(
        value,
        keys=(
            "launch_definition",
            "launch_definition_sha256",
            "parent_observation",
            "child_report",
            "child_report_sha256",
        ),
        name="B11H process launch observation",
    )
    launch = _parse_launch(observed["launch_definition"])
    child = _parse_child_report(observed["child_report"])
    if observed["launch_definition_sha256"] != launch.sha256:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H launch-definition identity changed."
        )
    if observed["child_report_sha256"] != child.sha256:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H child-report identity changed."
        )
    parent = _require_exact_keys(
        observed["parent_observation"],
        keys=(
            "spawn_started_at_unix_ns",
            "observed_child_process_id",
            "observed_exit_code",
            "completed_at_unix_ns",
        ),
        name="B11H parent observation",
    )
    return ASRAdversarialVOiCESProcessLaunchObservation(
        launch=launch,
        child_report=child,
        parent_spawn_started_at_unix_ns=_require_positive_int(
            name="B11H parent spawn start",
            value=parent["spawn_started_at_unix_ns"],
        ),
        parent_observed_child_process_id=_require_positive_int(
            name="B11H parent-observed child id",
            value=parent["observed_child_process_id"],
        ),
        parent_observed_exit_code=_require_nonnegative_int(
            name="B11H parent-observed exit code",
            value=parent["observed_exit_code"],
        ),
        parent_observed_completed_at_unix_ns=_require_positive_int(
            name="B11H parent completion",
            value=parent["completed_at_unix_ns"],
        ),
    )


def load_asr_adversarial_voices_process_run_observation_v1(
    raw: bytes,
) -> ASRAdversarialVOiCESProcessRunObservation:
    """Load and fully revalidate one content-free B11H process-run JSON."""

    root = _require_exact_keys(
        _parse_json(raw),
        keys=(
            "schema_version",
            "artifact",
            "process_launch",
            "run_observation",
            "run_observation_sha256",
            "evidence_boundary",
        ),
        name="B11H process-run root",
    )
    if (
        root["schema_version"]
        != ASR_ADVERSARIAL_VOICES_PROCESS_REPRODUCIBILITY_SCHEMA_VERSION
        or root["artifact"] != _PROCESS_RUN_ARTIFACT
        or root["evidence_boundary"] != _PROCESS_RUN_BOUNDARY
    ):
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H process-run schema, artifact, or evidence boundary changed."
        )
    run = _parse_run_observation(root["run_observation"])
    if root["run_observation_sha256"] != run.sha256:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H run-observation identity changed."
        )
    return ASRAdversarialVOiCESProcessRunObservation(
        process_launch=_parse_process_launch(root["process_launch"]),
        run_observation=run,
    )


def load_asr_adversarial_voices_process_run_file_v1(
    path: str | Path,
) -> ASRAdversarialVOiCESProcessRunObservation:
    """Load one B11H process-run observation without embedding its path."""

    try:
        raw = Path(path).read_bytes()
    except (OSError, TypeError, ValueError) as error:
        raise ASRAdversarialVOiCESProcessReproducibilityError(
            "B11H process-run file could not be read."
        ) from error
    return load_asr_adversarial_voices_process_run_observation_v1(raw)
