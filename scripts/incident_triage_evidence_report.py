"""Development-only evidence reporting for incident-triage agents.

This module reuses the existing deterministic lifecycle. It neither
implements a new agent controller nor grants scientific/deployment
authority. Verification is a second run in the same local process.
"""

from __future__ import annotations

import argparse
import json
import re

from environments.agent.incident_triage import IncidentFaultMode
from packages.verification.incident_triage_verification import (
    run_verification_eligibility_demo,
)

SCHEMA = "hetren.dev.incident-triage-evidence-report.v1"
SCENARIOS = tuple(mode.value for mode in IncidentFaultMode)


def build_report(
    scenario: str,
    run_id: str,
    *,
    exclude_candidate_policy: bool = False,
) -> dict:
    """Execute the existing fixture and project its actual evidence."""

    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError("unsupported development scenario")

    if (
        type(run_id) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}",
            run_id,
        ) is None
    ):
        raise ValueError("invalid run identifier")

    if type(exclude_candidate_policy) is not bool:
        raise TypeError("policy flag must be boolean")

    options = {}

    if exclude_candidate_policy:
        # Controlled negative fixture: the candidate's component
        # is excluded from the permitted-component policy.
        options["permitted_component_ids"] = (
            "noncandidate-component",
        )

    result = run_verification_eligibility_demo(
        IncidentFaultMode(scenario),
        run_id=run_id,
        **options,
    )

    source = result.source
    verification = result.verification_report

    source_evidence = (
        source.candidate_run.execution_evidence_sha256
    )
    verification_evidence = (
        result.verification_run.execution_evidence_sha256
    )

    if (
        source.execution.execution_id
        == result.verification_execution.execution_id
        or source.execution.runner_id
        == result.verification_execution.runner_id
        or source.evaluation.evaluator_id
        == result.verification_evaluation.evaluator_id
        or source_evidence == verification_evidence
    ):
        raise RuntimeError(
            "distinct verification evidence is not established"
        )

    if (
        source.snapshot.snapshot_sha256
        != source.execution.system_snapshot_sha256
        or source.snapshot.snapshot_sha256
        != result.verification_execution.system_snapshot_sha256
    ):
        raise RuntimeError(
            "source and verification candidate lineage differ"
        )

    if "same local Python process" not in verification.limitations:
        raise RuntimeError(
            "required verification-independence limitation absent"
        )

    return {
        "schema": SCHEMA,
        "fixture": "deterministic-incident-triage",
        "scenario": scenario,
        "run_id": run_id,
        "diagnosis": {
            "status": source.diagnosis.final_decision.status.name,
            "hypothesis_key": (
                source.diagnosis.diagnosed_hypothesis_key
            ),
        },
        "repair": {
            "kind": source.repair_kind.value,
            "candidate_snapshot_sha256": (
                source.snapshot.snapshot_sha256
            ),
        },
        "ordinary_evaluation": {
            "outcome": source.evaluation.outcome.name,
            "execution_id": source.execution.execution_id,
            "execution_evidence_sha256": source_evidence,
            "limitations": list(source.evaluation.limitations),
        },
        "verification": {
            "outcome": verification.outcome.name,
            "execution_id": (
                result.verification_execution.execution_id
            ),
            "execution_evidence_sha256": verification_evidence,
            "limitations": list(verification.limitations),
        },
        "eligibility": {
            "outcome": result.eligibility_decision.outcome.name,
            "policy_sha256": (
                result.eligibility_decision.policy_sha256
            ),
            "candidate_excluded_by_test_policy": (
                exclude_candidate_policy
            ),
        },
        "authority": {
            "deployment_authorized": False,
            "protected_scientific_execution_authorized": False,
            "independent_process_verification": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report the existing deterministic Hetren "
            "diagnosis, repair and verification workflow."
        )
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        required=True,
    )
    parser.add_argument(
        "--run-id",
        default="local-evidence-report",
    )
    parser.add_argument(
        "--exclude-candidate-policy",
        action="store_true",
        help=(
            "Use a controlled negative policy fixture "
            "that excludes the candidate component."
        ),
    )

    args = parser.parse_args(argv)

    try:
        report = build_report(
            args.scenario,
            args.run_id,
            exclude_candidate_policy=(
                args.exclude_candidate_policy
            ),
        )
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))

    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
