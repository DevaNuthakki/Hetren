"""A5-10H-B2: per-request provider observability for bounded incident recovery.

Development-only evidence sidecar. Existing B1/B2/B3 run and evidence hashes
remain unchanged. Captured JSON alone has UNKNOWN token usage; only a validated
OpenAIResponsesResult carries provider-REPORTED usage. Elapsed time measures
local capture-source wall duration, NOT provider-side processing latency.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from time import perf_counter_ns
from typing import Callable

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.model_incident_multistep_agent_development import CaptureSource
from packages.engines.behavioral.model_incident_multistep_recovery_development import (
    FaultInjector, ResilientMultistepIncidentRun, run_resilient_multistep_incident,
)
from packages.model_capture import ModelCapture, ModelRequest, replay_json_capture
from packages.openai_responses import (
    OpenAIResponsesResult, Transport, call_openai_responses,
)

_HEX = re.compile(r"[0-9a-f]{64}")


def _sha_ok(value: object) -> bool:
    return type(value) is str and _HEX.fullmatch(value) is not None


@dataclass(frozen=True)
class CaptureCallObservation:
    """One observed capture-source invocation; never stores secrets or payloads."""

    number: int
    request_sha256: str
    outcome: str
    origin: str
    capture_sha256: str | None
    provider_result_sha256: str | None
    reported_model: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    elapsed_ns: int

    def __post_init__(self) -> None:
        if type(self.number) is not int or not 1 <= self.number <= 12:
            raise ContractError("invalid capture call number")
        if not _sha_ok(self.request_sha256):
            raise ContractError("invalid capture request digest")
        if type(self.elapsed_ns) is not int or self.elapsed_ns < 0:
            raise ContractError("invalid measured capture duration")
        for field in ("capture_sha256", "provider_result_sha256"):
            value = getattr(self, field)
            if value is not None and not _sha_ok(value):
                raise ContractError(f"invalid {field}")
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(self, field)
            if value is not None and (type(value) is not int or value < 0):
                raise ContractError(f"invalid provider-reported {field}")

        if self.outcome == "interrupted":
            if (
                self.origin != "capture_source_exception"
                or any(getattr(self, name) is not None for name in (
                    "capture_sha256", "provider_result_sha256", "reported_model",
                    "input_tokens", "output_tokens", "total_tokens",
                ))
            ):
                raise ContractError("interruption cannot report a response")
        elif self.outcome == "captured":
            if self.origin == "offline_capture":
                if (
                    self.capture_sha256 is None
                    or any(getattr(self, name) is not None for name in (
                        "provider_result_sha256", "reported_model", "input_tokens",
                        "output_tokens", "total_tokens",
                    ))
                ):
                    raise ContractError("offline capture cannot report provider usage")
            elif self.origin == "injected_provider_result":
                if (
                    self.capture_sha256 is None
                    or self.provider_result_sha256 is None
                    or type(self.reported_model) is not str
                    or not self.reported_model
                ):
                    raise ContractError("provider observation lacks provenance")
            else:
                raise ContractError("invalid captured-result origin")
        else:
            raise ContractError("invalid capture call outcome")

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed_ns / 1_000_000

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "CaptureCallObservation", "schema_version": 1,
            "development_only": True, "number": self.number,
            "request_sha256": self.request_sha256, "outcome": self.outcome,
            "origin": self.origin, "capture_sha256": self.capture_sha256,
            "provider_result_sha256": self.provider_result_sha256,
            "reported_model": self.reported_model,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens, "elapsed_ns": self.elapsed_ns,
        }

    @property
    def observation_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class ObservedResilientIncidentRun:
    """Validated sidecar for attempted provider/capture calls in an agent run."""

    run: ResilientMultistepIncidentRun
    calls: tuple[CaptureCallObservation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.run, ResilientMultistepIncidentRun):
            raise ContractError("invalid observed recovery run")
        if type(self.calls) is not tuple:
            raise ContractError("calls must be immutable")
        expected_count = len(self.run.attempts) + (1 if self.run.interruption else 0)
        if len(self.calls) != expected_count:
            raise ContractError("observed calls do not match recovery attempts")
        for index, attempt in enumerate(self.run.attempts):
            call = self.calls[index]
            if (
                not isinstance(call, CaptureCallObservation)
                or call.number != index + 1
                or call.outcome != "captured"
                or call.request_sha256 != attempt.request_sha256
                or call.capture_sha256 != attempt.capture_sha256
            ):
                raise ContractError("capture and recovery evidence mismatch")
        if self.run.interruption is not None:
            last = self.calls[-1]
            if (
                not isinstance(last, CaptureCallObservation)
                or last.outcome != "interrupted"
                or last.number != expected_count
                or last.request_sha256 != self.run.interruption.pending_request_sha256
            ):
                raise ContractError("interruption/capture evidence mismatch")

    @property
    def passed(self) -> bool:
        return self.run.passed

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "ObservedResilientIncidentRun", "schema_version": 1,
            "development_only": True,
            "underlying_run_sha256": self.run.execution_evidence_sha256,
            "call_evidence_sha256": [call.observation_sha256 for call in self.calls],
        })

    @property
    def local_capture_elapsed_ns(self) -> int:
        return sum(call.elapsed_ns for call in self.calls)

    def _complete_usage_total(self, field: str) -> int | None:
        # An incomplete response, missing usage field, or offline fixture makes
        # the complete total UNKNOWN. In particular, unknown is never zero.
        values = [getattr(call, field) for call in self.calls]
        if not values or any(value is None for value in values):
            return None
        return sum(values)

    @property
    def total_input_tokens(self) -> int | None:
        return self._complete_usage_total("input_tokens")

    @property
    def total_output_tokens(self) -> int | None:
        return self._complete_usage_total("output_tokens")

    @property
    def total_reported_tokens(self) -> int | None:
        return self._complete_usage_total("total_tokens")

    @property
    def cost_usd(self) -> None:
        # No price schedule or billing evidence exists in this development run.
        return None

    @property
    def limitations(self) -> tuple[str, ...]:
        return self.run.limitations + (
            "provider usage is provider-reported, not independently metered",
            "injected responses do not authenticate provider or model identity",
            "local capture duration is not provider-side processing latency",
            "missing usage fields remain unknown, not zero",
            "no observed billing price or USD cost",
            "no live inference, external recovery, or independent verification",
        )


# Source returns a bare offline fixture OR a structured provider result.
ObservedCaptureSource = Callable[[ModelRequest], ModelCapture | OpenAIResponsesResult]


def run_observed_resilient_incident(
    *, scenario: IncidentScenario, model: str, run_id: str,
    capture_source: ObservedCaptureSource,
    failure_injector: FaultInjector | None = None,
    max_steps: int = 4, max_attempts: int = 6, max_recoveries: int = 1,
) -> ObservedResilientIncidentRun:
    """Run existing recovery unchanged while retaining observed call provenance."""
    if not callable(capture_source):
        raise ContractError("explicit capture source is required")
    calls: list[CaptureCallObservation] = []

    def observed_source(request: ModelRequest) -> ModelCapture:
        start_ns = perf_counter_ns()
        try:
            response = capture_source(request)
        except (ContractError, AssertionError):
            # Invalid contracts remain fail-closed; never synthesize valid usage.
            raise
        except Exception:
            calls.append(CaptureCallObservation(
                number=len(calls) + 1,
                request_sha256=request.request_sha256,
                outcome="interrupted", origin="capture_source_exception",
                capture_sha256=None, provider_result_sha256=None,
                reported_model=None, input_tokens=None, output_tokens=None,
                total_tokens=None,
                elapsed_ns=max(0, perf_counter_ns() - start_ns),
            ))
            raise

        if isinstance(response, OpenAIResponsesResult):
            capture = response.capture
            # Validate the exact request BEFORE accepting provider evidence.
            replay_json_capture(request=request, capture=capture)
            call = CaptureCallObservation(
                number=len(calls) + 1,
                request_sha256=request.request_sha256,
                outcome="captured", origin="injected_provider_result",
                capture_sha256=capture.capture_sha256,
                provider_result_sha256=response.evidence_sha256,
                reported_model=response.response_model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                elapsed_ns=max(0, perf_counter_ns() - start_ns),
            )
        elif isinstance(response, ModelCapture):
            replay_json_capture(request=request, capture=response)
            capture = response
            call = CaptureCallObservation(
                number=len(calls) + 1,
                request_sha256=request.request_sha256,
                outcome="captured", origin="offline_capture",
                capture_sha256=capture.capture_sha256,
                provider_result_sha256=None,
                reported_model=None,
                input_tokens=None, output_tokens=None, total_tokens=None,
                elapsed_ns=max(0, perf_counter_ns() - start_ns),
            )
        else:
            raise ContractError("capture source returned unsupported type")
        calls.append(call)
        return capture

    run = run_resilient_multistep_incident(
        scenario=scenario, model=model, run_id=run_id,
        capture_source=observed_source, failure_injector=failure_injector,
        max_steps=max_steps, max_attempts=max_attempts,
        max_recoveries=max_recoveries,
    )
    return ObservedResilientIncidentRun(run=run, calls=tuple(calls))


def run_injected_openai_observed_resilient_incident(
    *, scenario: IncidentScenario, model: str, run_id: str,
    api_key: str, transport: Transport,
    failure_injector: FaultInjector | None = None,
    max_steps: int = 4, max_attempts: int = 6, max_recoveries: int = 1,
) -> ObservedResilientIncidentRun:
    """Use only an explicitly injected provider-shaped transport; never HTTPS."""
    if not callable(transport):
        raise ContractError("injected transport is required")

    def source(request: ModelRequest) -> OpenAIResponsesResult:
        return call_openai_responses(
            request=request, api_key=api_key, transport=transport,
        )

    return run_observed_resilient_incident(
        scenario=scenario, model=model, run_id=run_id,
        capture_source=source, failure_injector=failure_injector,
        max_steps=max_steps, max_attempts=max_attempts,
        max_recoveries=max_recoveries,
    )
