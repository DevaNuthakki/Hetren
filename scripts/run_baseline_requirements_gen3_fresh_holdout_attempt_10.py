from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sys
import traceback


ROOT = Path(__file__).resolve().parents[1]

DATA = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "baseline_requirements_gen3"
)

CASES_FILE = (
    DATA
    / "fresh_holdout_cases_attempt_10.json"
)

FREEZE_FILE = (
    DATA
    / "fresh_holdout_freeze_manifest.json"
)

AUTHORIZATION_FILE = (
    DATA
    / "fresh_holdout_execution_authorization_attempt_10.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)

START_RECEIPT_FILE = (
    DATA
    / "fresh_holdout_first_run_started.json"
)

PREDICTIONS_FILE = (
    DATA
    / "fresh_holdout_first_predictions.json"
)

RESULT_FILE = (
    DATA
    / "fresh_holdout_first_run.json"
)


EXPECTED_CASES_SHA = (
    "44013a265a0b3cddece2579168ece02dc"
    "d464b22d761d05f713a45b3fc94f089"
)

EXPECTED_FREEZE_SHA = (
    "64c3e69417e74dda898109f324573fa7d"
    "15924f479e426804363fb15eb622d48"
)

EXPECTED_EVALUATOR_SHA = (
    "38e0a9f80e25da52fb4f310390505ded"
    "f0a57c0db4e02a9768747890f2f58c46"
)


def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def now_utc():
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def load_json(path):
    return json.loads(
        path.read_text()
    )


def atomic_write_json(
    path,
    artifact,
):
    if path.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing evidence artifact: {path}"
        )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    if temporary.exists():
        raise RuntimeError(
            f"Unexpected temporary artifact already exists: {temporary}"
        )

    payload = (
        json.dumps(
            artifact,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    with temporary.open(
        "xb"
    ) as handle:
        handle.write(
            payload
        )
        handle.flush()
        os.fsync(
            handle.fileno()
        )

    os.replace(
        temporary,
        path,
    )

    return sha256(
        path
    )


def build_evaluator_inputs(
    cases,
):
    inputs = []

    for case in cases:
        inputs.append(
            {
                "id": case[
                    "id"
                ],

                "primary_requirement": case[
                    "primary_requirement"
                ],

                "facts": deepcopy(
                    case[
                        "facts"
                    ]
                ),

                "environment": case[
                    "environment"
                ],
            }
        )

    return inputs


def validate_outcome(
    outcome,
):
    if not isinstance(
        outcome,
        dict,
    ):
        raise TypeError(
            "Evaluator outcome must be a dictionary."
        )

    if set(
        outcome
    ) != {
        "decision",
        "violations",
    }:
        raise ValueError(
            "Evaluator outcome must contain exactly "
            "'decision' and 'violations'."
        )

    if outcome[
        "decision"
    ] not in {
        "ACCEPT",
        "REJECT",
    }:
        raise ValueError(
            "Evaluator decision outside frozen public vocabulary."
        )

    violations = outcome[
        "violations"
    ]

    if not isinstance(
        violations,
        list,
    ):
        raise TypeError(
            "Evaluator violations must be a list."
        )

    if not all(
        isinstance(
            code,
            str,
        )
        for code in violations
    ):
        raise TypeError(
            "Every evaluator violation must be a string."
        )


def collect_predictions(
    evaluator_inputs,
    evaluate,
    predictions,
    progress,
):
    for item in evaluator_inputs:

        progress[
            "calls_attempted"
        ] += 1

        outcome = evaluate(
            primary_requirement=
                item[
                    "primary_requirement"
                ],

            facts=
                item[
                    "facts"
                ],

            environment=
                item[
                    "environment"
                ],
        )

        progress[
            "calls_completed"
        ] += 1

        validate_outcome(
            outcome
        )

        predictions.append(
            {
                "id": item[
                    "id"
                ],

                "primary_requirement": item[
                    "primary_requirement"
                ],

                "environment": item[
                    "environment"
                ],

                "decision": outcome[
                    "decision"
                ],

                "violations": list(
                    outcome[
                        "violations"
                    ]
                ),
            }
        )


def score_predictions(
    cases,
    predictions,
):
    predictions_by_id = {
        prediction[
            "id"
        ]: prediction
        for prediction in predictions
    }

    results = []

    false_accept_ids = []
    false_reject_ids = []
    violation_contract_failure_ids = []

    must_accept_correct = 0
    must_reject_correct = 0

    for case in cases:

        case_id = case[
            "id"
        ]

        prediction = predictions_by_id[
            case_id
        ]

        expectation = case[
            "expectation"
        ]

        expected_codes = list(
            case[
                "expected_violation_codes"
            ]
        )

        actual_decision = prediction[
            "decision"
        ]

        actual_violations = list(
            prediction[
                "violations"
            ]
        )

        if expectation == "MUST_ACCEPT":

            decision_correct = (
                actual_decision
                == "ACCEPT"
            )

            violation_contract_correct = (
                actual_violations
                == []
            )

            if actual_decision == "REJECT":
                false_reject_ids.append(
                    case_id
                )

            passed = (
                decision_correct
                and violation_contract_correct
            )

            if passed:
                must_accept_correct += 1

        elif expectation == "MUST_REJECT":

            decision_correct = (
                actual_decision
                == "REJECT"
            )

            violation_contract_correct = (
                set(
                    expected_codes
                )
                <= set(
                    actual_violations
                )
            )

            if actual_decision == "ACCEPT":
                false_accept_ids.append(
                    case_id
                )

            if not violation_contract_correct:
                violation_contract_failure_ids.append(
                    case_id
                )

            passed = (
                decision_correct
                and violation_contract_correct
            )

            if passed:
                must_reject_correct += 1

        else:
            raise ValueError(
                f"Unknown expectation for {case_id}: "
                f"{expectation}"
            )

        results.append(
            {
                "id": case_id,

                "primary_requirement": case[
                    "primary_requirement"
                ],

                "environment": case[
                    "environment"
                ],

                "expectation": expectation,

                "expected_violation_codes": expected_codes,

                "actual_decision": actual_decision,

                "actual_violations": actual_violations,

                "decision_correct": decision_correct,

                "violation_contract_correct":
                    violation_contract_correct,

                "passed": passed,
            }
        )


    passed_case_count = sum(
        result[
            "passed"
        ]
        for result in results
    )

    summary = {
        "case_count": len(
            cases
        ),

        "passed_case_count":
            passed_case_count,

        "failed_case_count":
            len(cases)
            - passed_case_count,

        "must_accept_correct":
            must_accept_correct,

        "must_accept_total": 27,

        "must_reject_correct":
            must_reject_correct,

        "must_reject_total": 27,

        "false_accept_count": len(
            false_accept_ids
        ),

        "false_accept_ids":
            false_accept_ids,

        "false_reject_count": len(
            false_reject_ids
        ),

        "false_reject_ids":
            false_reject_ids,

        "violation_contract_failure_count":
            len(
                violation_contract_failure_ids
            ),

        "violation_contract_failure_ids":
            violation_contract_failure_ids,

        "qualification_result": (
            "PASS"
            if passed_case_count
            == len(
                cases
            )
            else "FAIL"
        ),
    }

    return (
        results,
        summary,
    )


def create_start_receipt(
    runner_sha,
    authorization_sha,
):
    if START_RECEIPT_FILE.exists():
        raise RuntimeError(
            "Single-use start receipt already exists. "
            "A fresh rerun is prohibited."
        )

    artifact = {
        "schema_version": "1.0.0",

        "artifact_type": (
            "TASK_8_GEN3_FRESH_HOLDOUT_"
            "FIRST_TARGET_RUN_START_RECEIPT"
        ),

        "state": (
            "SINGLE_USE_EXECUTION_STARTED_BEFORE_TARGET_IMPORT"
        ),

        "generation_attempt": 10,

        "started_at_utc":
            now_utc(),

        "runner_sha256":
            runner_sha,

        "authorization_sha256":
            authorization_sha,

        "fresh_holdout_cases_sha256":
            EXPECTED_CASES_SHA,

        "freeze_manifest_sha256":
            EXPECTED_FREEZE_SHA,

        "target_evaluator_sha256":
            EXPECTED_EVALUATOR_SHA,

        "target_imported_at_receipt_creation":
            False,

        "target_calls_attempted_at_receipt_creation":
            0,

        "target_predictions_available_at_receipt_creation":
            False,

        "purpose": (
            "Irreversibly mark the single protected "
            "Attempt-10 first-run execution as started "
            "before target import so an interrupted run "
            "cannot later be rerun and misrepresented as fresh."
        ),
    }

    payload = (
        json.dumps(
            artifact,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    with START_RECEIPT_FILE.open(
        "xb"
    ) as handle:
        handle.write(
            payload
        )
        handle.flush()
        os.fsync(
            handle.fileno()
        )

    return sha256(
        START_RECEIPT_FILE
    )


def main():
    #
    # Never permit a second execution attempt.
    #
    if START_RECEIPT_FILE.exists():
        raise SystemExit(
            "ABORT: single-use first-run start receipt "
            "already exists; rerun as fresh is prohibited."
        )

    if PREDICTIONS_FILE.exists():
        raise SystemExit(
            "ABORT: first-run prediction evidence already exists."
        )

    if RESULT_FILE.exists():
        raise SystemExit(
            "ABORT: first-run result already exists."
        )


    #
    # Exact frozen byte boundary, still before target import.
    #
    assert sha256(
        CASES_FILE
    ) == EXPECTED_CASES_SHA

    assert sha256(
        FREEZE_FILE
    ) == EXPECTED_FREEZE_SHA

    assert sha256(
        EVALUATOR_FILE
    ) == EXPECTED_EVALUATOR_SHA


    freeze = load_json(
        FREEZE_FILE
    )

    assert freeze[
        "state"
    ] == (
        "FROZEN_BEFORE_FIRST_TARGET_EXECUTION"
    )

    assert freeze[
        "frozen_inputs"
    ][
        "fresh_holdout_cases_attempt_10"
    ][
        "sha256"
    ] == EXPECTED_CASES_SHA

    assert freeze[
        "frozen_inputs"
    ][
        "frozen_target_evaluator"
    ][
        "sha256"
    ] == EXPECTED_EVALUATOR_SHA

    assert freeze[
        "execution_state_at_freeze"
    ][
        "target_freshness_consumed"
    ] is False


    runner_sha = sha256(
        Path(__file__).resolve()
    )

    authorization = load_json(
        AUTHORIZATION_FILE
    )

    authorization_sha = sha256(
        AUTHORIZATION_FILE
    )

    assert authorization[
        "artifact_type"
    ] == (
        "TASK_8_GEN3_ATTEMPT_10_"
        "PROTECTED_EXECUTION_AUTHORIZATION"
    )

    assert authorization[
        "state"
    ] == "AUTHORIZED_NOT_EXECUTED"

    assert authorization[
        "generation_attempt"
    ] == 10

    assert authorization[
        "runner"
    ][
        "sha256"
    ] == runner_sha

    assert authorization[
        "frozen_inputs"
    ][
        "cases_sha256"
    ] == EXPECTED_CASES_SHA

    assert authorization[
        "frozen_inputs"
    ][
        "freeze_manifest_sha256"
    ] == EXPECTED_FREEZE_SHA

    assert authorization[
        "frozen_inputs"
    ][
        "target_evaluator_sha256"
    ] == EXPECTED_EVALUATOR_SHA

    assert authorization[
        "execution_contract"
    ][
        "maximum_fresh_execution_attempts"
    ] == 1

    assert authorization[
        "execution_contract"
    ][
        "calls_per_case"
    ] == 1

    assert authorization[
        "execution_contract"
    ][
        "all_predictions_before_scoring"
    ] is True


    cases_artifact = load_json(
        CASES_FILE
    )

    assert cases_artifact[
        "state"
    ] == "GENERATED_NOT_EXECUTED"

    cases = cases_artifact[
        "cases"
    ]

    expected_ids = [
        f"G3-H10-{i:03d}"
        for i in range(
            1,
            55,
        )
    ]

    assert [
        case[
            "id"
        ]
        for case in cases
    ] == expected_ids

    assert len(
        cases
    ) == 54


    #
    # Build evaluator-only projections before target import.
    # No expectation/oracle fields enter this structure.
    #
    evaluator_inputs = build_evaluator_inputs(
        cases
    )

    assert len(
        evaluator_inputs
    ) == 54

    assert all(
        set(
            item
        )
        == {
            "id",
            "primary_requirement",
            "facts",
            "environment",
        }
        for item in evaluator_inputs
    )


    #
    # Irreversible single-use marker is created BEFORE
    # target evaluator import.
    #
    start_receipt_sha = create_start_receipt(
        runner_sha,
        authorization_sha,
    )


    predictions = []

    progress = {
        "calls_attempted": 0,
        "calls_completed": 0,
    }

    target_imported = False


    try:
        #
        # This is the first permitted import of the frozen target
        # for Attempt 10.
        #
        from baseline_requirements_gen3_semantics import evaluate

        target_imported = True


        #
        # Collect ALL target predictions before any scoring.
        #
        collect_predictions(
            evaluator_inputs,
            evaluate,
            predictions,
            progress,
        )

        assert progress[
            "calls_attempted"
        ] == 54

        assert progress[
            "calls_completed"
        ] == 54

        assert len(
            predictions
        ) == 54

        assert [
            prediction[
                "id"
            ]
            for prediction in predictions
        ] == expected_ids


        #
        # Preserve raw predictions before scoring.
        #
        predictions_artifact = {
            "schema_version": "1.0.0",

            "artifact_type": (
                "TASK_8_GEN3_FRESH_HOLDOUT_"
                "FIRST_TARGET_PREDICTIONS_ATTEMPT_10"
            ),

            "state": (
                "ALL_PREDICTIONS_COLLECTED_BEFORE_SCORING"
            ),

            "generation_attempt": 10,

            "evidence_class": (
                "FRESH_PROTECTED_HOLDOUT_FIRST_EXECUTION"
            ),

            "created_at_utc":
                now_utc(),

            "fresh_holdout_cases_sha256":
                EXPECTED_CASES_SHA,

            "freeze_manifest_sha256":
                EXPECTED_FREEZE_SHA,

            "target_evaluator_sha256":
                EXPECTED_EVALUATOR_SHA,

            "runner_sha256":
                runner_sha,

            "authorization_sha256":
                authorization_sha,

            "start_receipt_sha256":
                start_receipt_sha,

            "target_evaluator_imported":
                True,

            "evaluator_calls_attempted":
                progress[
                    "calls_attempted"
                ],

            "evaluator_calls_completed":
                progress[
                    "calls_completed"
                ],

            "all_predictions_collected":
                True,

            "scoring_started":
                False,

            "predictions":
                predictions,
        }

        predictions_sha = atomic_write_json(
            PREDICTIONS_FILE,
            predictions_artifact,
        )


        #
        # Only now may oracle/scoring fields be consulted.
        #
        results, summary = score_predictions(
            cases,
            predictions,
        )


        result_artifact = {
            "schema_version": "1.0.0",

            "artifact_type": (
                "TASK_8_GEN3_FRESH_HOLDOUT_"
                "FIRST_TARGET_RUN_ATTEMPT_10"
            ),

            "state": (
                "FIRST_TARGET_EXECUTION_COMPLETE"
            ),

            "generation_attempt": 10,

            "evidence_class": (
                "FRESH_PROTECTED_HOLDOUT_FIRST_EXECUTION"
            ),

            "completed_at_utc":
                now_utc(),

            "frozen_inputs": {
                "fresh_holdout_cases_sha256":
                    EXPECTED_CASES_SHA,

                "freeze_manifest_sha256":
                    EXPECTED_FREEZE_SHA,

                "target_evaluator_sha256":
                    EXPECTED_EVALUATOR_SHA,

                "runner_sha256":
                    runner_sha,

                "authorization_sha256":
                    authorization_sha,

                "start_receipt_sha256":
                    start_receipt_sha,

                "raw_predictions_sha256":
                    predictions_sha,
            },

            "execution": {
                "single_use_start_receipt_created_before_target_import":
                    True,

                "target_evaluator_imported":
                    True,

                "evaluator_calls_attempted":
                    progress[
                        "calls_attempted"
                    ],

                "evaluator_calls_completed":
                    progress[
                        "calls_completed"
                    ],

                "calls_per_case":
                    1,

                "secondary_requirements_triggered_additional_calls":
                    False,

                "expectation_passed_to_evaluator":
                    False,

                "expected_violation_codes_passed_to_evaluator":
                    False,

                "all_predictions_collected_before_scoring":
                    True,

                "raw_predictions_preserved_before_scoring":
                    True,
            },

            "predictions":
                predictions,

            "case_results":
                results,

            "summary":
                summary,

            "freshness_after_execution": {
                "target_freshness_consumed":
                    True,

                "cases_remain_fresh":
                    False,

                "future_use_class":
                    "REGRESSION_EVIDENCE_ONLY",

                "rerun_as_fresh_permitted":
                    False,

                "case_rewrite_can_restore_freshness":
                    False,
            },

            "claim_limits": {
                "pass_does_not_establish_scientific_support":
                    True,

                "pass_does_not_establish_task_8_authority":
                    True,

                "pass_does_not_establish_task_5_support":
                    True,

                "pass_does_not_prove_universal_generalization":
                    True,
            },
        }


        result_sha = atomic_write_json(
            RESULT_FILE,
            result_artifact,
        )


        print(
            "First-run start receipt SHA-256:",
            start_receipt_sha,
        )

        print(
            "Raw predictions SHA-256:",
            predictions_sha,
        )

        print(
            "First-run result SHA-256:",
            result_sha,
        )

        print(
            "Qualification result:",
            summary[
                "qualification_result"
            ],
        )

        print(
            "Passed:",
            summary[
                "passed_case_count"
            ],
            "/",
            summary[
                "case_count"
            ],
        )

        print(
            "False accepts:",
            summary[
                "false_accept_count"
            ],
        )

        print(
            "False rejects:",
            summary[
                "false_reject_count"
            ],
        )

        print(
            "Violation-contract failures:",
            summary[
                "violation_contract_failure_count"
            ],
        )


    except BaseException as exc:
        #
        # Any failure after creation of the start receipt is itself
        # immutable first-run evidence. Never silently retry.
        #
        failure_artifact = {
            "schema_version": "1.0.0",

            "artifact_type": (
                "TASK_8_GEN3_FRESH_HOLDOUT_"
                "FIRST_TARGET_RUN_ATTEMPT_10"
            ),

            "state": (
                "FIRST_TARGET_EXECUTION_FAILED_AFTER_SINGLE_USE_START"
            ),

            "generation_attempt": 10,

            "evidence_class": (
                "FRESH_PROTECTED_HOLDOUT_FIRST_EXECUTION"
            ),

            "failed_at_utc":
                now_utc(),

            "fresh_holdout_cases_sha256":
                EXPECTED_CASES_SHA,

            "freeze_manifest_sha256":
                EXPECTED_FREEZE_SHA,

            "target_evaluator_sha256":
                EXPECTED_EVALUATOR_SHA,

            "runner_sha256":
                runner_sha,

            "authorization_sha256":
                authorization_sha,

            "start_receipt_sha256":
                start_receipt_sha,

            "target_evaluator_imported":
                target_imported,

            "evaluator_calls_attempted":
                progress[
                    "calls_attempted"
                ],

            "evaluator_calls_completed":
                progress[
                    "calls_completed"
                ],

            "all_predictions_collected": (
                progress[
                    "calls_completed"
                ]
                == 54
            ),

            "raw_predictions_artifact_exists":
                PREDICTIONS_FILE.exists(),

            "partial_predictions":
                predictions,

            "scoring_completed":
                False,

            "exception_type":
                type(
                    exc
                ).__name__,

            "exception_message":
                str(
                    exc
                ),

            "traceback":
                traceback.format_exc(),

            "rerun_as_fresh_permitted":
                False,

            "interpretation": (
                "The protected single-use execution had already "
                "started. Preserve this failure exactly; do not "
                "retry and represent a later run as fresh."
            ),
        }

        if not RESULT_FILE.exists():
            atomic_write_json(
                RESULT_FILE,
                failure_artifact,
            )

        print(
            "Protected first execution failed after "
            "single-use start.",
            file=sys.stderr,
        )

        print(
            "Preserved result:",
            RESULT_FILE,
            file=sys.stderr,
        )

        raise


if __name__ == "__main__":
    main()
