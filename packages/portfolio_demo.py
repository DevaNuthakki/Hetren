"""Reproducible executable demonstration for the Hetren portfolio slice.

Run:

    python -m packages.portfolio_demo
    python -m packages.portfolio_demo --format json

The demonstration executes the already-implemented deterministic chain. It does
not add repair, verification, eligibility, authorization, deployment, or
lifecycle semantics.

The generated report intentionally contains no timestamps, random values, or
machine-specific paths so identical inputs produce identical report bytes.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from packages.contracts import (
    CandidateEligibilityOutcome,
    EvaluationOutcome,
    VerificationOutcome,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.contracts import (
    DiagnosisStatus,
    InterventionKind,
)
from packages.engines.behavioral import FaultMode
from packages.verification import (
    review_candidate_eligibility,
    run_verification_eligibility_demo,
)


_REPORT_TYPE = "HetrenDeterministicPortfolioDemo"
_SCHEMA_VERSION = 1
_DEMO_VERSION = "p07.7d-v1"

_SCENARIOS = (
    FaultMode.TOOL_SELECTION,
    FaultMode.PARAMETER_TRANSFORMATION,
)

_EXPECTED_DIAGNOSIS = {
    FaultMode.TOOL_SELECTION: (
        "tool_selection_fault"
    ),
    FaultMode.PARAMETER_TRANSFORMATION: (
        "parameter_transformation_fault"
    ),
}

_EXPECTED_REPAIR = {
    FaultMode.TOOL_SELECTION: (
        InterventionKind.REPLACE_TOOL
    ),
    FaultMode.PARAMETER_TRANSFORMATION: (
        InterventionKind.OVERRIDE_PARAMETER
    ),
}

_CLAIM_LIMITS = (
    "deterministic portfolio fixture only",
    "does not establish repair of arbitrary AI agents",
    "procedural verification separation is not proof of infrastructure independence",
    "VERIFIED does not automatically imply ELIGIBLE",
    "ELIGIBLE is not authorization or deployment approval",
)


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            f"portfolio demonstration invariant failed: {message}"
        )


def _scenario_payload(
    mode: FaultMode,
    result,
) -> dict[str, object]:
    """Validate and render one already-executed vertical slice."""
    diagnosis = result.source.diagnosis

    _require(
        diagnosis.baseline_run.output == 2,
        f"{mode.value}: baseline output must remain 2",
    )

    _require(
        diagnosis.final_decision.status
        is DiagnosisStatus.DIAGNOSED,
        f"{mode.value}: diagnosis must reach DIAGNOSED",
    )

    _require(
        diagnosis.diagnosed_hypothesis_key
        == _EXPECTED_DIAGNOSIS[mode],
        f"{mode.value}: diagnosed hypothesis changed",
    )

    _require(
        result.source.repair_kind
        is _EXPECTED_REPAIR[mode],
        f"{mode.value}: selected repair changed",
    )

    _require(
        result.source.candidate_run.output == 12,
        f"{mode.value}: candidate output must be 12",
    )

    _require(
        result.source.evaluation.outcome
        is EvaluationOutcome.PASS,
        f"{mode.value}: source evaluation must PASS",
    )

    _require(
        result.verification_evaluation.outcome
        is EvaluationOutcome.PASS,
        f"{mode.value}: verification evaluation must PASS",
    )

    _require(
        result.verification_report.outcome
        is VerificationOutcome.VERIFIED,
        f"{mode.value}: verification must be VERIFIED",
    )

    _require(
        result.eligibility_decision.outcome
        is CandidateEligibilityOutcome.ELIGIBLE,
        f"{mode.value}: default bounded policy must be ELIGIBLE",
    )

    _require(
        result.source.execution.execution_id
        != result.verification_execution.execution_id,
        f"{mode.value}: verification execution must be distinct",
    )

    _require(
        result.source.evaluation.evaluation_id
        != result.verification_evaluation.evaluation_id,
        f"{mode.value}: verification evaluation must be distinct",
    )

    _require(
        result.source.execution.system_snapshot_sha256
        == result.verification_execution.system_snapshot_sha256
        == result.source.snapshot.snapshot_sha256,
        f"{mode.value}: both lineages must bind exact candidate",
    )

    return {
        "fault_fixture": mode.value,
        "baseline": {
            "output": (
                diagnosis.baseline_run.output
            ),
            "trace_sha256": (
                diagnosis.baseline_run.trace.trace_sha256
            ),
        },
        "diagnosis": {
            "status": (
                diagnosis.final_decision.status.value
            ),
            "hypothesis": (
                diagnosis.diagnosed_hypothesis_key
            ),
            "selected_experiment": (
                diagnosis.initial_decision.experiment_key
            ),
            "problem_sha256": (
                diagnosis.problem.problem_sha256
            ),
        },
        "repair": {
            "kind": (
                result.source.repair_kind.value
            ),
            "proposal_id": (
                result.source.proposal.proposal_id
            ),
            "proposal_sha256": (
                result.source.proposal.proposal_sha256
            ),
        },
        "candidate": {
            "snapshot_id": (
                result.source.snapshot.snapshot_id
            ),
            "snapshot_sha256": (
                result.source.snapshot.snapshot_sha256
            ),
            "system_version_id": (
                result.source.snapshot.system_version_id
            ),
            "output": (
                result.source.candidate_run.output
            ),
            "execution_evidence_sha256": (
                result.source.candidate_run
                .execution_evidence_sha256
            ),
        },
        "source_evaluation": {
            "execution_id": (
                result.source.execution.execution_id
            ),
            "execution_sha256": (
                result.source.execution.execution_sha256
            ),
            "evaluation_id": (
                result.source.evaluation.evaluation_id
            ),
            "evaluation_sha256": (
                result.source.evaluation.evaluation_sha256
            ),
            "outcome": (
                result.source.evaluation.outcome.value
            ),
        },
        "verification": {
            "execution_id": (
                result.verification_execution.execution_id
            ),
            "execution_sha256": (
                result.verification_execution.execution_sha256
            ),
            "evaluation_id": (
                result.verification_evaluation.evaluation_id
            ),
            "evaluation_sha256": (
                result.verification_evaluation.evaluation_sha256
            ),
            "evaluation_outcome": (
                result.verification_evaluation.outcome.value
            ),
            "verification_id": (
                result.verification_report.verification_id
            ),
            "verification_sha256": (
                result.verification_report.verification_sha256
            ),
            "outcome": (
                result.verification_report.outcome.value
            ),
        },
        "eligibility": {
            "decision_id": (
                result.eligibility_decision.decision_id
            ),
            "decision_sha256": (
                result.eligibility_decision.eligibility_sha256
            ),
            "policy_sha256": (
                result.eligibility_decision.policy_sha256
            ),
            "outcome": (
                result.eligibility_decision.outcome.value
            ),
        },
    }


def build_demo_report() -> dict[str, object]:
    """Execute and return the complete deterministic portfolio report."""
    results = {}

    for mode in _SCENARIOS:
        results[mode] = (
            run_verification_eligibility_demo(
                mode,
                run_id=(
                    "portfolio-demo-"
                    f"{mode.value}"
                ),
            )
        )

    scenarios = [
        _scenario_payload(
            mode,
            results[mode],
        )
        for mode in _SCENARIOS
    ]

    control_source = (
        results[FaultMode.TOOL_SELECTION]
    )

    restricted_decision = (
        review_candidate_eligibility(
            source=control_source.source,
            verification=(
                control_source.verification_report
            ),
            permitted_component_ids=(
                "policy-excluded-component-v1",
            ),
        )
    )

    _require(
        control_source.verification_report.outcome
        is VerificationOutcome.VERIFIED,
        "policy control requires VERIFIED candidate",
    )

    _require(
        control_source.eligibility_decision.outcome
        is CandidateEligibilityOutcome.ELIGIBLE,
        "default policy control must be ELIGIBLE",
    )

    _require(
        restricted_decision.outcome
        is CandidateEligibilityOutcome.INELIGIBLE,
        "restricted policy control must be INELIGIBLE",
    )

    _require(
        control_source.eligibility_decision.policy_sha256
        != restricted_decision.policy_sha256,
        "policy control must change policy identity",
    )

    body = {
        "report_type": _REPORT_TYPE,
        "schema_version": _SCHEMA_VERSION,
        "demo_version": _DEMO_VERSION,
        "scenarios": scenarios,
        "policy_control": {
            "fault_fixture": (
                FaultMode.TOOL_SELECTION.value
            ),
            "candidate_snapshot_sha256": (
                control_source.source.snapshot.snapshot_sha256
            ),
            "verification_sha256": (
                control_source.verification_report.verification_sha256
            ),
            "verification_outcome": (
                control_source.verification_report.outcome.value
            ),
            "default_policy": {
                "policy_sha256": (
                    control_source.eligibility_decision.policy_sha256
                ),
                "outcome": (
                    control_source.eligibility_decision.outcome.value
                ),
            },
            "restricted_policy": {
                "policy_sha256": (
                    restricted_decision.policy_sha256
                ),
                "outcome": (
                    restricted_decision.outcome.value
                ),
            },
            "conclusion": (
                "VERIFIED does not automatically imply ELIGIBLE"
            ),
        },
        "claim_limits": list(
            _CLAIM_LIMITS
        ),
    }

    return {
        **body,
        "report_sha256": canonical_sha256(
            body
        ),
    }


def render_json(
    report: dict[str, object],
) -> str:
    """Render stable, human-readable JSON."""
    return json.dumps(
        report,
        sort_keys=True,
        indent=2,
        ensure_ascii=True,
    )


def render_text(
    report: dict[str, object],
) -> str:
    """Render a concise reviewer-facing terminal summary."""
    lines = [
        "Hetren deterministic executable portfolio demonstration",
        "=" * 53,
        "",
    ]

    for scenario in report["scenarios"]:
        lines.extend(
            (
                f"Fixture: {scenario['fault_fixture']}",
                (
                    "  Failure: "
                    f"output={scenario['baseline']['output']}"
                ),
                (
                    "  Diagnosis: "
                    f"{scenario['diagnosis']['hypothesis']}"
                ),
                (
                    "  Repair: "
                    f"{scenario['repair']['kind']}"
                ),
                (
                    "  Candidate: "
                    f"output={scenario['candidate']['output']}"
                ),
                (
                    "  Evaluation: "
                    f"{scenario['source_evaluation']['outcome']}"
                ),
                (
                    "  Verification: "
                    f"{scenario['verification']['outcome']}"
                ),
                (
                    "  Eligibility: "
                    f"{scenario['eligibility']['outcome']}"
                ),
                "",
            )
        )

    control = report["policy_control"]

    lines.extend(
        (
            "Policy separation control:",
            (
                "  Verification: "
                f"{control['verification_outcome']}"
            ),
            (
                "  Default policy: "
                f"{control['default_policy']['outcome']}"
            ),
            (
                "  Restricted policy: "
                f"{control['restricted_policy']['outcome']}"
            ),
            (
                "  Conclusion: "
                f"{control['conclusion']}"
            ),
            "",
            (
                "Report SHA-256: "
                f"{report['report_sha256']}"
            ),
            "",
            "Claim limits:",
        )
    )

    for limit in report["claim_limits"]:
        lines.append(
            f"  - {limit}"
        )

    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the deterministic Hetren executable "
            "portfolio demonstration."
        )
    )

    parser.add_argument(
        "--format",
        choices=(
            "text",
            "json",
        ),
        default="text",
        help=(
            "output format; JSON is deterministic "
            "and suitable for redirection to an artifact"
        ),
    )

    args = parser.parse_args(
        argv
    )

    report = build_demo_report()

    if args.format == "json":
        output = render_json(
            report
        )
    else:
        output = render_text(
            report
        )

    print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )


__all__ = [
    "build_demo_report",
    "main",
    "render_json",
    "render_text",
]
