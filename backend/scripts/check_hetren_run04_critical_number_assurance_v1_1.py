#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from hvee.packs.asr.critical_number_assurance_v1_1 import (  # noqa: E402
    build_critical_number_assurance_v1_1_candidate,
    verify_critical_number_assurance_v1_1_candidate,
)


def main() -> int:
    bundle = build_critical_number_assurance_v1_1_candidate()
    verified = verify_critical_number_assurance_v1_1_candidate(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )
    baseline = verified.payload["inherited_baseline"]
    boundary = verified.payload["v1_1_boundary"]
    mutations = verified.payload["evaluator_mutation_suite"]
    measurements = verified.payload["qualification_measurements"]
    summary = {
        "assurance_candidate_sha256": verified.sha256,
        "evaluator": verified.payload["bindings"]["evaluator"],
        "historical_v1_assurance_sha256": verified.payload["bindings"][
            "historical_v1_assurance_sha256"
        ],
        "inherited_baseline": {
            "total_cases": baseline["total_cases"],
            "passed_cases": baseline["passed_cases"],
            "failed_cases": baseline["failed_cases"],
        },
        "v1_1_boundary": {
            "total_cases": boundary["total_cases"],
            "passed_cases": boundary["passed_cases"],
            "failed_cases": boundary["failed_cases"],
        },
        "mutation_suite": {
            "total_mutants": mutations["total_mutants"],
            "killed_mutants": mutations["killed_mutants"],
            "survived_mutants": mutations["survived_mutants"],
        },
        "qualification_measurements": measurements,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "run04_scoring_performed": False,
        "hidden_holdout_membership_opened": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
