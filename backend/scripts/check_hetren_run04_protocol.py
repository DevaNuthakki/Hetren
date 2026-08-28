#!/usr/bin/env python3
"""Print and verify the frozen Run-04 preregistration identities."""

from __future__ import annotations

import json
import sys
from pathlib import Path


_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


from hvee.core.ai_change_set import verify_ai_change_set
from hvee.packs.asr.run04_protocol import (
    build_asr_run04_ai_change_set,
    build_asr_run04_protocol_v1,
    verify_asr_run04_protocol_v1,
)


def main() -> int:
    definition, change_set = build_asr_run04_ai_change_set()
    protocol = build_asr_run04_protocol_v1()

    change_verified = verify_ai_change_set(
        payload=change_set.payload,
        expected_sha256=change_set.sha256,
        definition=definition,
    )
    protocol_verified = verify_asr_run04_protocol_v1(
        payload=protocol.payload,
        expected_sha256=protocol.sha256,
    )

    print("HETREN RUN-04 PROTOCOL CHECK")
    print(json.dumps(
        {
            "ai_change_set_sha256": change_set.sha256,
            "ai_change_set_verified": change_verified,
            "asr_execution_performed": False,
            "execution_authorized": False,
            "protocol_sha256": protocol.sha256,
            "protocol_verified": protocol_verified,
            "run04_completed": False,
        },
        indent=2,
        sort_keys=True,
    ))

    if change_verified and protocol_verified:
        print("HETREN_RUN04_PROTOCOL=PASS")
        return 0

    print("HETREN_RUN04_PROTOCOL=FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
