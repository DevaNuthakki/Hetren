#!/usr/bin/env python3
"""Verify the frozen, outcome-free Hetren Run-04 corpus allocation plan."""

from __future__ import annotations

import json
from pathlib import Path
import sys


_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from hvee.packs.asr.run04_corpus_plan import (
    ASR_RUN04_CORPUS_PLAN_SHA256,
    build_asr_run04_corpus_plan_v1,
    verify_asr_run04_corpus_plan_v1,
)


def main() -> int:
    plan = build_asr_run04_corpus_plan_v1()
    verified = verify_asr_run04_corpus_plan_v1(
        payload=plan.payload,
        expected_sha256=ASR_RUN04_CORPUS_PLAN_SHA256,
    )
    report = plan.payload["allocation_report"]
    boundary = plan.payload["evidence_boundary"]
    output = {
        "allocation_plan_frozen": boundary["allocation_plan_frozen"],
        "asr_execution_performed": boundary["asr_execution_performed"],
        "case_slot_count": report["total_case_count"],
        "corpus_plan_sha256": plan.sha256,
        "fresh_corpus_materialized": boundary[
            "fresh_corpus_materialized"
        ],
        "human_speaker_slot_count": report[
            "human_speaker_slot_count"
        ],
        "run04_completed": boundary["run04_completed"],
        "run04_execution_authorized": boundary[
            "run04_execution_authorized"
        ],
        "speaker_slot_count": report["distinct_speaker_slot_count"],
        "verified": verified,
    }
    print("HETREN RUN-04 CORPUS PLAN CHECK")
    print(json.dumps(output, indent=2, sort_keys=True))
    if not verified:
        print("HETREN_RUN04_CORPUS_PLAN=FAIL")
        return 1
    print("HETREN_RUN04_CORPUS_PLAN=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
