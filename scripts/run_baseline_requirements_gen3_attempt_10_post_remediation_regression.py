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


EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)

FAILED_EVALUATOR_FILE = (
    DATA
    / "semantic_evaluator_first_fresh_holdout_run.py"
)

REMEDIATION_BOUNDARY_FILE = (
    DATA
    / "fresh_holdout_attempt_10_remediation_boundary.json"
)

POST_PATCH_BOUNDARY_FILE = (
    DATA
    / "fresh_holdout_attempt_10_post_remediation_boundary.json"
)

DEVELOPMENT_CASES_FILE = (
    DATA
    / "cases.json"
)

MUTATIONS_FILE = (
    DATA
    / "mutations.json"
)

HOLDOUT_CASES_FILE = (
    DATA
    / "fresh_holdout_cases_attempt_10.json"
)

AUTHORITATIVE_FIRST_RUN_FILE = (
    DATA
    / "fresh_holdout_first_run.json"
)

HISTORICAL_REGRESSION_FILE = (
    DATA
    / "remediation_regression_result.json"
)

AUTHORIZATION_FILE = (
    DATA
    / "fresh_holdout_attempt_10_"
      "post_remediation_regression_authorization.json"
)

PREDICTIONS_FILE = (
    DATA
    / "fresh_holdout_attempt_10_"
      "post_remediation_predictions.json"
)

RESULT_FILE = (
    DATA
    / "fresh_holdout_attempt_10_"
      "post_remediation_regression_result.json"
)


EXPECTED = {
    "evaluator": (
        "37b4075c00a9bea3e249bb0f9c895a6a"
        "6ccf7481a255ae7e1ece0d64c1c0907e"
    ),

    "failed_evaluator": (
        "38e0a9f80e25da52fb4f310390505ded"
        "f0a57c0db4e02a9768747890f2f58c46"
    ),

    "remediation_boundary": (
        "063b6882d42ec9db5242f0ede9760aab"
        "677f5f3c68ab1ace4efb508e9daab1ff"
    ),

    "post_patch_boundary": (
        "ea04d06b5e151b78b80314601ce964cc"
        "3875a2ca28239a90f30e3ab5d6381347"
    ),

    "development_cases": (
        "b2187b08cbde20086d74901316b1a0778"
        "d55e6f165a4cc774c32df67d361194d"
    ),

    "mutations": (
        "f86885033501c61136fdfbdf34c639665"
        "e26a6936522ad03cb100cd41675796e"
    ),

    "holdout_cases": (
        "44013a265a0b3cddece2579168ece02dc"
        "d464b22d761d05f713a45b3fc94f089"
    ),

    "authoritative_first_run": (
        "e23948d2416aee500759ed9ca3249cf5"
        "afb32fe747dd54a38ec2f7ded32ec028"
    ),

    "historical_regression": (
        "da22d819a6cbfab8c5c076f80e2079512"
        "463b16d7b127b0b8d7e602a48d7d3ba"
    ),
}


def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(path):
    return json.loads(
        path.read_text()
    )


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


def atomic_write_json(
    path,
    artifact,
):
    if path.exists():
        raise RuntimeError(
            f"Refusing to overwrite evidence artifact: {path}"
        )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    if temporary.exists():
        raise RuntimeError(
            f"Unexpected temporary artifact: {temporary}"
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


def apply_operations(
    source_facts,
    operations,
):
    #
    # Exact historical mutation materialization semantics:
    # deepcopy + ordered set/delete operations.
    #
    facts = deepcopy(
        source_facts
    )

    for operation in operations:

        op = operation[
            "op"
        ]

        key = operation[
            "key"
        ]

        if op == "set":

            facts[
                key
            ] = deepcopy(
                operation[
                    "value"
                ]
            )

        elif op == "delete":

            facts.pop(
                key,
                None,
            )

        else:

            raise AssertionError(
                f"unsupported mutation operation: {op}"
            )

    return facts


def validate_outcome(
    outcome,
):
    if not isinstance(
        outcome,
        dict,
    ):
        raise TypeError(
            "Evaluator output must be dict."
        )

    if set(
        outcome
    ) != {
        "decision",
        "violations",
    }:
        raise ValueError(
            "Evaluator output keys changed."
        )

    if outcome[
        "decision"
    ] not in {
        "ACCEPT",
        "REJECT",
    }:
        raise ValueError(
            "Unknown evaluator decision."
        )

    if not isinstance(
        outcome[
            "violations"
        ],
        list,
    ):
        raise TypeError(
            "Evaluator violations must be list."
        )

    if not all(
        isinstance(
            code,
            str,
        )
        for code in outcome[
            "violations"
        ]
    ):
        raise TypeError(
            "Evaluator violation codes must be strings."
        )


def build_holdout_inputs(
    cases,
):
    return [
        {
            "id":
                case[
                    "id"
                ],

            "primary_requirement":
                case[
                    "primary_requirement"
                ],

            "environment":
                case[
                    "environment"
                ],

            "facts":
                deepcopy(
                    case[
                        "facts"
                    ]
                ),
        }
        for case in cases
    ]


def build_development_inputs(
    cases,
):
    return [
        {
            "id":
                case[
                    "id"
                ],

            "primary_requirement":
                case[
                    "primary_requirement"
                ],

            "environment":
                case[
                    "environment"
                ],

            "facts":
                deepcopy(
                    case[
                        "facts"
                    ]
                ),
        }
        for case in cases
    ]


def build_mutation_inputs(
    cases_by_id,
    mutations,
):
    evaluator_inputs = []

    for mutation in mutations:

        source_case = cases_by_id[
            mutation[
                "source_case_id"
            ]
        ]

        facts = apply_operations(
            source_case[
                "facts"
            ],
            mutation[
                "operations"
            ],
        )

        evaluator_inputs.append(
            {
                "id":
                    mutation[
                        "id"
                    ],

                "primary_requirement":
                    mutation[
                        "primary_requirement"
                    ],

                "environment":
                    source_case[
                        "environment"
                    ],

                "facts":
                    facts,
            }
        )

    return evaluator_inputs


def collect_predictions(
    corpus_name,
    evaluator_inputs,
    evaluate,
):
    predictions = []

    for item in evaluator_inputs:

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

        validate_outcome(
            outcome
        )

        predictions.append(
            {
                "corpus":
                    corpus_name,

                "id":
                    item[
                        "id"
                    ],

                "primary_requirement":
                    item[
                        "primary_requirement"
                    ],

                "environment":
                    item[
                        "environment"
                    ],

                "decision":
                    outcome[
                        "decision"
                    ],

                "violations":
                    list(
                        outcome[
                            "violations"
                        ]
                    ),
            }
        )

    return predictions


def score_holdout(
    cases,
    predictions,
):
    by_id = {
        item[
            "id"
        ]: item
        for item in predictions
    }

    results = []

    for case in cases:

        prediction = by_id[
            case[
                "id"
            ]
        ]

        expectation = case[
            "expectation"
        ]

        expected_codes = list(
            case[
                "expected_violation_codes"
            ]
        )

        actual_codes = list(
            prediction[
                "violations"
            ]
        )

        if expectation == "MUST_ACCEPT":

            decision_match = (
                prediction[
                    "decision"
                ]
                == "ACCEPT"
            )

            violation_contract_match = (
                actual_codes
                == []
            )

        elif expectation == "MUST_REJECT":

            decision_match = (
                prediction[
                    "decision"
                ]
                == "REJECT"
            )

            violation_contract_match = (
                set(
                    expected_codes
                )
                <= set(
                    actual_codes
                )
            )

        else:
            raise AssertionError(
                expectation
            )

        matched = (
            decision_match
            and violation_contract_match
        )

        results.append(
            {
                "case_id":
                    case[
                        "id"
                    ],

                "primary_requirement":
                    case[
                        "primary_requirement"
                    ],

                "expectation":
                    expectation,

                "expected_violation_codes":
                    expected_codes,

                "predicted_decision":
                    prediction[
                        "decision"
                    ],

                "actual_violation_codes":
                    actual_codes,

                "decision_match":
                    decision_match,

                "violation_contract_match":
                    violation_contract_match,

                "matched":
                    matched,
            }
        )

    return results


def score_development(
    cases,
    predictions,
):
    #
    # Preserve historical development-runner scoring:
    # decision match only.
    #
    by_id = {
        item[
            "id"
        ]: item
        for item in predictions
    }

    results = []

    for case in cases:

        prediction = by_id[
            case[
                "id"
            ]
        ]

        expected = (
            "ACCEPT"
            if case[
                "expectation"
            ] == "MUST_ACCEPT"
            else "REJECT"
        )

        results.append(
            {
                "case_id":
                    case[
                        "id"
                    ],

                "expected_decision":
                    expected,

                "predicted_decision":
                    prediction[
                        "decision"
                    ],

                "violations":
                    list(
                        prediction[
                            "violations"
                        ]
                    ),

                "matched": (
                    prediction[
                        "decision"
                    ]
                    == expected
                ),
            }
        )

    return results


def score_mutations(
    mutations,
    predictions,
):
    #
    # Preserve exact historical mutation scoring:
    # decision + violation contract.
    #
    by_id = {
        item[
            "id"
        ]: item
        for item in predictions
    }

    results = []

    for mutation in mutations:

        prediction = by_id[
            mutation[
                "id"
            ]
        ]

        expected = (
            "ACCEPT"
            if mutation[
                "expectation"
            ] == "MUST_ACCEPT"
            else "REJECT"
        )

        expected_codes = set(
            mutation[
                "expected_violation_codes"
            ]
        )

        actual_codes = set(
            prediction[
                "violations"
            ]
        )

        decision_match = (
            prediction[
                "decision"
            ]
            == expected
        )

        if expected == "ACCEPT":

            code_match = (
                actual_codes
                == set()
            )

        else:

            code_match = (
                expected_codes
                .issubset(
                    actual_codes
                )
            )

        results.append(
            {
                "mutation_id":
                    mutation[
                        "id"
                    ],

                "expected_decision":
                    expected,

                "predicted_decision":
                    prediction[
                        "decision"
                    ],

                "expected_violation_codes":
                    mutation[
                        "expected_violation_codes"
                    ],

                "actual_violation_codes":
                    prediction[
                        "violations"
                    ],

                "decision_match":
                    decision_match,

                "violation_contract_match":
                    code_match,

                "matched": (
                    decision_match
                    and code_match
                ),
            }
        )

    return results


def matched_count(
    results,
):
    return sum(
        bool(
            item[
                "matched"
            ]
        )
        for item in results
    )


def mismatched_ids(
    results,
    id_key,
):
    return [
        item[
            id_key
        ]
        for item in results
        if not item[
            "matched"
        ]
    ]


def main():
    #
    # Evidence outputs are immutable for this regression attempt.
    #
    if PREDICTIONS_FILE.exists():
        raise SystemExit(
            "ABORT: regression predictions already exist."
        )

    if RESULT_FILE.exists():
        raise SystemExit(
            "ABORT: regression result already exists."
        )


    #
    # Verify exact frozen post-remediation boundary before import.
    #
    bindings = {
        "evaluator":
            EVALUATOR_FILE,

        "failed_evaluator":
            FAILED_EVALUATOR_FILE,

        "remediation_boundary":
            REMEDIATION_BOUNDARY_FILE,

        "post_patch_boundary":
            POST_PATCH_BOUNDARY_FILE,

        "development_cases":
            DEVELOPMENT_CASES_FILE,

        "mutations":
            MUTATIONS_FILE,

        "holdout_cases":
            HOLDOUT_CASES_FILE,

        "authoritative_first_run":
            AUTHORITATIVE_FIRST_RUN_FILE,

        "historical_regression":
            HISTORICAL_REGRESSION_FILE,
    }


    for name, path in bindings.items():

        actual = sha256(
            path
        )

        expected = EXPECTED[
            name
        ]

        assert actual == expected, (
            name,
            expected,
            actual,
        )


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
        "state"
    ] == (
        "AUTHORIZED_NON_FRESH_REGRESSION_NOT_EXECUTED"
    )

    assert authorization[
        "runner"
    ][
        "sha256"
    ] == runner_sha

    assert authorization[
        "frozen_inputs"
    ][
        "remediated_evaluator_sha256"
    ] == EXPECTED[
        "evaluator"
    ]

    assert authorization[
        "frozen_inputs"
    ][
        "post_patch_boundary_sha256"
    ] == EXPECTED[
        "post_patch_boundary"
    ]

    assert authorization[
        "execution_contract"
    ][
        "holdout_calls"
    ] == 54

    assert authorization[
        "execution_contract"
    ][
        "development_calls"
    ] == 54

    assert authorization[
        "execution_contract"
    ][
        "mutation_calls"
    ] == 34

    assert authorization[
        "execution_contract"
    ][
        "expected_total_calls"
    ] == 142

    assert authorization[
        "execution_contract"
    ][
        "all_predictions_before_scoring"
    ] is True

    assert authorization[
        "evidence_class"
    ] == "REGRESSION_ONLY"


    #
    # Load frozen corpora.
    #
    holdout_document = load_json(
        HOLDOUT_CASES_FILE
    )

    development_document = load_json(
        DEVELOPMENT_CASES_FILE
    )

    mutation_document = load_json(
        MUTATIONS_FILE
    )

    first_run = load_json(
        AUTHORITATIVE_FIRST_RUN_FILE
    )


    holdout_cases = holdout_document[
        "cases"
    ]

    development_cases = development_document[
        "cases"
    ]

    mutations = mutation_document[
        "mutations"
    ]


    assert len(
        holdout_cases
    ) == 54

    assert len(
        development_cases
    ) == 54

    assert len(
        mutations
    ) == 34


    assert first_run[
        "summary"
    ][
        "qualification_result"
    ] == "FAIL"

    assert first_run[
        "summary"
    ][
        "passed_case_count"
    ] == 52

    assert first_run[
        "freshness_after_execution"
    ][
        "target_freshness_consumed"
    ] is True


    development_by_id = {
        case[
            "id"
        ]: case
        for case in development_cases
    }


    #
    # Build evaluator-only projections.
    #
    holdout_inputs = build_holdout_inputs(
        holdout_cases
    )

    development_inputs = build_development_inputs(
        development_cases
    )

    mutation_inputs = build_mutation_inputs(
        development_by_id,
        mutations,
    )


    assert len(
        holdout_inputs
    ) == 54

    assert len(
        development_inputs
    ) == 54

    assert len(
        mutation_inputs
    ) == 34


    allowed_input_keys = {
        "id",
        "primary_requirement",
        "environment",
        "facts",
    }


    assert all(
        set(
            item
        ) == allowed_input_keys
        for item in (
            holdout_inputs
            + development_inputs
            + mutation_inputs
        )
    )


    #
    # Target import occurs only after frozen-input validation
    # and evaluator-only projections are constructed.
    #
    from baseline_requirements_gen3_semantics import evaluate


    #
    # Collect ALL 142 predictions before consulting any oracle.
    #
    holdout_predictions = collect_predictions(
        "ATTEMPT_10_CONSUMED_HOLDOUT",
        holdout_inputs,
        evaluate,
    )

    development_predictions = collect_predictions(
        "KNOWN_DEVELOPMENT_CASES",
        development_inputs,
        evaluate,
    )

    mutation_predictions = collect_predictions(
        "KNOWN_DEVELOPMENT_MUTATIONS",
        mutation_inputs,
        evaluate,
    )


    assert len(
        holdout_predictions
    ) == 54

    assert len(
        development_predictions
    ) == 54

    assert len(
        mutation_predictions
    ) == 34


    total_predictions = (
        len(
            holdout_predictions
        )
        + len(
            development_predictions
        )
        + len(
            mutation_predictions
        )
    )

    assert total_predictions == 142


    #
    # Preserve raw predictions before any scoring.
    #
    predictions_artifact = {
        "schema_version":
            "1.0.0",

        "artifact_type": (
            "TASK_8_GEN3_ATTEMPT_10_"
            "POST_REMEDIATION_RAW_REGRESSION_PREDICTIONS"
        ),

        "state":
            "ALL_142_PREDICTIONS_COLLECTED_BEFORE_SCORING",

        "generation_attempt":
            10,

        "created_at_utc":
            now_utc(),

        "evidence_class":
            "REGRESSION_ONLY",

        "fresh":
            False,

        "historical_authoritative_first_run_result":
            "FAIL_52_OF_54",

        "bindings": {
            "runner_sha256":
                runner_sha,

            "authorization_sha256":
                authorization_sha,

            "remediated_evaluator_sha256":
                EXPECTED[
                    "evaluator"
                ],

            "post_patch_boundary_sha256":
                EXPECTED[
                    "post_patch_boundary"
                ],

            "holdout_cases_sha256":
                EXPECTED[
                    "holdout_cases"
                ],

            "development_cases_sha256":
                EXPECTED[
                    "development_cases"
                ],

            "mutations_sha256":
                EXPECTED[
                    "mutations"
                ],
        },

        "counts": {
            "holdout":
                54,

            "development":
                54,

            "mutations":
                34,

            "total":
                142,
        },

        "scoring_started":
            False,

        "predictions": {
            "attempt_10_consumed_holdout":
                holdout_predictions,

            "development":
                development_predictions,

            "mutations":
                mutation_predictions,
        },
    }


    predictions_sha = atomic_write_json(
        PREDICTIONS_FILE,
        predictions_artifact,
    )


    #
    # Scoring begins only after complete raw predictions exist.
    #
    try:

        holdout_results = score_holdout(
            holdout_cases,
            holdout_predictions,
        )

        development_results = score_development(
            development_cases,
            development_predictions,
        )

        mutation_results = score_mutations(
            mutations,
            mutation_predictions,
        )


        holdout_passed = matched_count(
            holdout_results
        )

        development_passed = matched_count(
            development_results
        )

        mutation_passed = matched_count(
            mutation_results
        )


        holdout_mismatches = mismatched_ids(
            holdout_results,
            "case_id",
        )

        development_mismatches = mismatched_ids(
            development_results,
            "case_id",
        )

        mutation_mismatches = mismatched_ids(
            mutation_results,
            "mutation_id",
        )


        holdout_by_id = {
            item[
                "case_id"
            ]: item
            for item in holdout_results
        }


        targeted = {
            "G3-H10-009": (
                holdout_by_id[
                    "G3-H10-009"
                ][
                    "predicted_decision"
                ] == "ACCEPT"
                and holdout_by_id[
                    "G3-H10-009"
                ][
                    "actual_violation_codes"
                ] == []
            ),

            "G3-H10-010": (
                holdout_by_id[
                    "G3-H10-010"
                ][
                    "predicted_decision"
                ] == "REJECT"
                and "PERSISTENT_STATE_NOT_MATCHED"
                in holdout_by_id[
                    "G3-H10-010"
                ][
                    "actual_violation_codes"
                ]
            ),

            "G3-H10-037": (
                holdout_by_id[
                    "G3-H10-037"
                ][
                    "predicted_decision"
                ] == "ACCEPT"
                and holdout_by_id[
                    "G3-H10-037"
                ][
                    "actual_violation_codes"
                ] == []
            ),

            "G3-H10-038": (
                holdout_by_id[
                    "G3-H10-038"
                ][
                    "predicted_decision"
                ] == "REJECT"
                and "TARGET_INFORMATION_CHANNEL_HIDDEN"
                in holdout_by_id[
                    "G3-H10-038"
                ][
                    "actual_violation_codes"
                ]
            ),
        }


        overall_pass = all([
            holdout_passed == 54,
            development_passed == 54,
            mutation_passed == 34,
            all(
                targeted.values()
            ),
        ])


        result_artifact = {
            "schema_version":
                "1.0.0",

            "artifact_type": (
                "TASK_8_GEN3_ATTEMPT_10_"
                "POST_REMEDIATION_REGRESSION_RESULT"
            ),

            "state":
                "POST_REMEDIATION_REGRESSION_COMPLETE",

            "generation_attempt":
                10,

            "completed_at_utc":
                now_utc(),

            "evidence_class":
                "REGRESSION_ONLY",

            "fresh":
                False,

            "historical_authoritative_result": {
                "qualification_result":
                    "FAIL",

                "passed_case_count":
                    52,

                "case_count":
                    54,

                "result_sha256":
                    EXPECTED[
                        "authoritative_first_run"
                    ],

                "unchanged_by_this_regression":
                    True,
            },

            "bindings": {
                "runner_sha256":
                    runner_sha,

                "authorization_sha256":
                    authorization_sha,

                "raw_predictions_sha256":
                    predictions_sha,

                "remediated_evaluator_sha256":
                    EXPECTED[
                        "evaluator"
                    ],

                "failed_evaluator_sha256":
                    EXPECTED[
                        "failed_evaluator"
                    ],

                "remediation_boundary_sha256":
                    EXPECTED[
                        "remediation_boundary"
                    ],

                "post_patch_boundary_sha256":
                    EXPECTED[
                        "post_patch_boundary"
                    ],

                "holdout_cases_sha256":
                    EXPECTED[
                        "holdout_cases"
                    ],

                "development_cases_sha256":
                    EXPECTED[
                        "development_cases"
                    ],

                "mutations_sha256":
                    EXPECTED[
                        "mutations"
                    ],

                "historical_regression_sha256":
                    EXPECTED[
                        "historical_regression"
                    ],
            },

            "execution": {
                "holdout_calls":
                    54,

                "development_calls":
                    54,

                "mutation_calls":
                    34,

                "total_target_calls":
                    142,

                "all_predictions_collected_before_scoring":
                    True,

                "raw_predictions_preserved_before_scoring":
                    True,

                "oracle_fields_passed_to_evaluator":
                    False,
            },

            "summary": {
                "qualification":
                    (
                        "PASS"
                        if overall_pass
                        else "FAIL"
                    ),

                "attempt_10_regression": {
                    "passed":
                        holdout_passed,

                    "total":
                        54,

                    "mismatches":
                        holdout_mismatches,
                },

                "development_regression": {
                    "passed":
                        development_passed,

                    "total":
                        54,

                    "mismatches":
                        development_mismatches,
                },

                "mutation_regression": {
                    "passed":
                        mutation_passed,

                    "total":
                        34,

                    "mismatches":
                        mutation_mismatches,
                },

                "targeted_remediation_checks":
                    targeted,
            },

            "attempt_10_case_results":
                holdout_results,

            "development_case_results":
                development_results,

            "mutation_results":
                mutation_results,

            "interpretation": (
                "This execution is regression evidence only. "
                "The authoritative Attempt-10 protected first "
                "run remains the historical 52/54 FAIL and "
                "freshness remains permanently consumed."
            ),

            "claim_limits": {
                "does_not_rewrite_first_run":
                    True,

                "does_not_restore_freshness":
                    True,

                "does_not_create_new_fresh_holdout_evidence":
                    True,

                "does_not_by_itself_establish_task_8_completion":
                    True,

                "does_not_by_itself_establish_scientific_support":
                    True,
            },
        }


        result_sha = atomic_write_json(
            RESULT_FILE,
            result_artifact,
        )


        print(
            "Raw regression predictions SHA-256:",
            predictions_sha,
        )

        print(
            "Regression result SHA-256:",
            result_sha,
        )

        print(
            "Overall regression:",
            result_artifact[
                "summary"
            ][
                "qualification"
            ],
        )

        print(
            "Attempt-10 consumed holdout:",
            holdout_passed,
            "/ 54",
        )

        print(
            "Development:",
            development_passed,
            "/ 54",
        )

        print(
            "Mutations:",
            mutation_passed,
            "/ 34",
        )

        print(
            "Attempt-10 mismatches:",
            holdout_mismatches,
        )

        print(
            "Development mismatches:",
            development_mismatches,
        )

        print(
            "Mutation mismatches:",
            mutation_mismatches,
        )

        print(
            "Targeted remediation checks:",
            targeted,
        )


    except BaseException as exc:

        failure = {
            "schema_version":
                "1.0.0",

            "artifact_type": (
                "TASK_8_GEN3_ATTEMPT_10_"
                "POST_REMEDIATION_REGRESSION_RESULT"
            ),

            "state":
                "POST_REMEDIATION_REGRESSION_SCORING_FAILURE",

            "generation_attempt":
                10,

            "failed_at_utc":
                now_utc(),

            "evidence_class":
                "REGRESSION_ONLY",

            "fresh":
                False,

            "raw_predictions_sha256":
                predictions_sha,

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

            "historical_authoritative_attempt_10_result":
                "FAIL_52_OF_54_UNCHANGED",
        }

        if not RESULT_FILE.exists():

            atomic_write_json(
                RESULT_FILE,
                failure,
            )

        raise


if __name__ == "__main__":
    main()
