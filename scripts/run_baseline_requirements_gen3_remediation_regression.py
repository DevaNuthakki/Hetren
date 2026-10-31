#!/usr/bin/env python3

from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys

from baseline_requirements_gen3_semantics import evaluate


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "baseline_requirements_gen3"
)

CASES_FILE = DATA_DIR / "cases.json"
MUTATIONS_FILE = DATA_DIR / "mutations.json"

FIRST_SEMANTIC_FILE = (
    DATA_DIR
    / "semantic_wall_first_run.json"
)

FIRST_MUTATION_FILE = (
    DATA_DIR
    / "mutation_wall_first_run.json"
)

CLASSIFICATION_FILE = (
    DATA_DIR
    / "mutation_wall_first_run_classification.json"
)

HISTORICAL_EVALUATOR_FILE = (
    DATA_DIR
    / "semantic_evaluator_first_mutation_run.py"
)

BOUNDARY_FILE = (
    DATA_DIR
    / "remediation_regression_boundary.json"
)

RESULT_FILE = (
    DATA_DIR
    / "remediation_regression_result.json"
)

GEN3_FILE = (
    ROOT
    / "docs"
    / "research"
    / "baselines"
    / "task-08-baseline-requirements-gen3.json"
)

EVALUATOR_FILE = (
    ROOT
    / "scripts"
    / "baseline_requirements_gen3_semantics.py"
)


def sha256(target_file):
    return hashlib.sha256(
        target_file.read_bytes()
    ).hexdigest()


def apply_operations(source_facts, operations):
    facts = deepcopy(
        source_facts
    )

    for operation in operations:
        if operation["op"] == "set":
            facts[
                operation["key"]
            ] = operation["value"]

        elif operation["op"] == "delete":
            facts.pop(
                operation["key"],
                None,
            )

        else:
            raise AssertionError(
                operation
            )

    return facts


def verify_boundary():
    boundary = json.loads(
        BOUNDARY_FILE.read_text()
    )

    assert boundary[
        "created_before_regression_execution"
    ] is True

    assert boundary["regression_only"] is True
    assert boundary["fresh_holdout"] is False

    for item in boundary["artifacts"]:
        target_file = ROOT / item["path"]

        actual = sha256(
            target_file
        )

        assert actual == item["sha256"], (
            f"regression-boundary drift: "
            f"{item['path']}"
        )


def evaluate_development_cases(cases):
    evaluator_inputs = [
        {
            "id":
                case["id"],
            "primary_requirement":
                case["primary_requirement"],
            "environment":
                case["environment"],
            "facts":
                case["facts"],
        }
        for case in cases
    ]

    predictions = {}

    for item in evaluator_inputs:
        predictions[
            item["id"]
        ] = evaluate(
            primary_requirement=
                item["primary_requirement"],
            facts=
                item["facts"],
            environment=
                item["environment"],
        )

    results = []

    for case in cases:
        outcome = predictions[
            case["id"]
        ]

        expected = (
            "ACCEPT"
            if case["expectation"] == "MUST_ACCEPT"
            else "REJECT"
        )

        results.append({
            "case_id":
                case["id"],
            "expected_decision":
                expected,
            "predicted_decision":
                outcome["decision"],
            "violations":
                outcome["violations"],
            "matched":
                outcome["decision"] == expected,
        })

    return results


def evaluate_mutations(
    cases_by_id,
    mutations,
):
    evaluator_inputs = []

    materialized = {}

    for mutation in mutations:
        source_case = cases_by_id[
            mutation["source_case_id"]
        ]

        facts = apply_operations(
            source_case["facts"],
            mutation["operations"],
        )

        materialized[
            mutation["id"]
        ] = facts

        evaluator_inputs.append({
            "id":
                mutation["id"],
            "primary_requirement":
                mutation["primary_requirement"],
            "environment":
                source_case["environment"],
            "facts":
                facts,
        })

    predictions = {}

    for item in evaluator_inputs:
        predictions[
            item["id"]
        ] = evaluate(
            primary_requirement=
                item["primary_requirement"],
            facts=
                item["facts"],
            environment=
                item["environment"],
        )

    results = []

    for mutation in mutations:
        outcome = predictions[
            mutation["id"]
        ]

        expected = (
            "ACCEPT"
            if mutation["expectation"] == "MUST_ACCEPT"
            else "REJECT"
        )

        expected_codes = set(
            mutation[
                "expected_violation_codes"
            ]
        )

        actual_codes = set(
            outcome["violations"]
        )

        decision_match = (
            outcome["decision"]
            == expected
        )

        if expected == "ACCEPT":
            code_match = (
                actual_codes == set()
            )
        else:
            code_match = (
                expected_codes.issubset(
                    actual_codes
                )
            )

        results.append({
            "mutation_id":
                mutation["id"],
            "expected_decision":
                expected,
            "predicted_decision":
                outcome["decision"],
            "expected_violation_codes":
                mutation[
                    "expected_violation_codes"
                ],
            "actual_violation_codes":
                outcome["violations"],
            "decision_match":
                decision_match,
            "violation_contract_match":
                code_match,
            "matched":
                decision_match
                and code_match,
        })

    return results


def main():
    if RESULT_FILE.exists():
        raise RuntimeError(
            "Refusing to overwrite remediation regression result"
        )

    verify_boundary()

    cases = json.loads(
        CASES_FILE.read_text()
    )["cases"]

    mutations = json.loads(
        MUTATIONS_FILE.read_text()
    )["mutations"]

    cases_by_id = {
        case["id"]: case
        for case in cases
    }

    dev_results = evaluate_development_cases(
        cases
    )

    mutation_results = evaluate_mutations(
        cases_by_id,
        mutations,
    )

    dev_matches = sum(
        item["matched"]
        for item in dev_results
    )

    mutation_matches = sum(
        item["matched"]
        for item in mutation_results
    )

    dev_failures = [
        item["case_id"]
        for item in dev_results
        if not item["matched"]
    ]

    mutation_failures = [
        item["mutation_id"]
        for item in mutation_results
        if not item["matched"]
    ]

    status = (
        "PASS"
        if (
            dev_matches == len(dev_results)
            and mutation_matches == len(
                mutation_results
            )
        )
        else "FAIL"
    )

    historical_first_mutation = json.loads(
        FIRST_MUTATION_FILE.read_text()
    )

    assert historical_first_mutation[
        "summary"
    ]["status"] == "FAIL"

    assert historical_first_mutation[
        "summary"
    ]["match_count"] == 25

    assert historical_first_mutation[
        "summary"
    ]["mismatch_count"] == 9

    payload = {
        "schema_version": "1.0.0",
        "artifact_type":
            "TASK_8_GEN3_EVALUATOR_REMEDIATION_REGRESSION",
        "state":
            "DEVELOPMENT_REMEDIATION_REGRESSION",
        "authoritative":
            False,
        "scientific_support_established":
            False,
        "fresh_holdout":
            False,
        "protected_evaluation":
            False,
        "regression_only":
            True,
        "historical_first_mutation_wall_preserved":
            True,
        "historical_first_mutation_status":
            "FAIL",
        "historical_first_mutation_match_count":
            25,
        "historical_first_mutation_mismatch_count":
            9,
        "input_hashes": {
            "boundary_sha256":
                sha256(BOUNDARY_FILE),
            "generation_3_sha256":
                sha256(GEN3_FILE),
            "cases_sha256":
                sha256(CASES_FILE),
            "mutations_sha256":
                sha256(MUTATIONS_FILE),
            "remediated_evaluator_sha256":
                sha256(EVALUATOR_FILE),
            "historical_evaluator_sha256":
                sha256(
                    HISTORICAL_EVALUATOR_FILE
                ),
            "historical_54_case_run_sha256":
                sha256(
                    FIRST_SEMANTIC_FILE
                ),
            "historical_first_mutation_run_sha256":
                sha256(
                    FIRST_MUTATION_FILE
                ),
            "classification_sha256":
                sha256(
                    CLASSIFICATION_FILE
                ),
            "runner_sha256":
                sha256(
                    Path(__file__).resolve()
                ),
        },
        "summary": {
            "status":
                status,
            "development_case_count":
                len(dev_results),
            "development_match_count":
                dev_matches,
            "development_mismatch_ids":
                dev_failures,
            "mutation_count":
                len(mutation_results),
            "mutation_match_count":
                mutation_matches,
            "mutation_mismatch_ids":
                mutation_failures,
        },
        "development_results":
            dev_results,
        "mutation_results":
            mutation_results,
        "interpretation":
            "This is regression evidence after remediation of the nine "
            "classified semantic-evaluator defects. The original 54 cases "
            "and 34 mutations are already known development evidence. "
            "Neither section is a fresh holdout or new independent "
            "scientific evaluation."
    }

    RESULT_FILE.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=False,
        ) + "\n"
    )

    print(
        "REMEDIATION REGRESSION STATUS:",
        status,
    )

    print(
        "54-case regression:",
        f"{dev_matches}/{len(dev_results)}",
    )

    print(
        "34-mutation regression:",
        f"{mutation_matches}/{len(mutation_results)}",
    )

    print(
        "Development mismatches:",
        dev_failures,
    )

    print(
        "Mutation mismatches:",
        mutation_failures,
    )

    sys.exit(
        0
        if status == "PASS"
        else 1
    )


if __name__ == "__main__":
    main()
