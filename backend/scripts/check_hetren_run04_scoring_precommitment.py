from __future__ import annotations

import json

from hvee.packs.asr.run04_scoring_precommitment import (
    build_run04_scoring_precommitment_v1,
)


def main() -> int:
    bundle = build_run04_scoring_precommitment_v1()
    payload = bundle.payload

    print(
        json.dumps(
            {
                "precommitment_key": payload[
                    "precommitment"
                ]["key"],
                "precommitment_version": payload[
                    "precommitment"
                ]["version"],
                "precommitment_sha256": bundle.sha256,
                "base_evaluator_commit": payload[
                    "precommitment"
                ]["base_evaluator_commit"],
                "historical_protocol_sha256": payload[
                    "historical_protocol"
                ]["sha256"],
                "historical_number_evaluator": payload[
                    "historical_protocol"
                ]["critical_number_evaluator_version"],
                "scoring_number_evaluator": payload[
                    "post_execution_pre_scoring_correction"
                ]["corrected_evaluator_version"],
                "critical_number_assurance_sha256": payload[
                    "post_execution_pre_scoring_correction"
                ]["assurance_sha256"],
                "terminal_slots": payload[
                    "accounting"
                ]["terminal_slots"],
                "global_complete_pairs": payload[
                    "accounting"
                ]["global_complete_pairs"],
                "prediction_text_opened": False,
                "reference_text_opened": False,
                "run04_scoring_performed": False,
                "hidden_holdout_opened": False,
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
