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
MUTATION_CONTRACT_FILE = DATA_DIR / "mutation_contract.json"
MUTATIONS_FILE = DATA_DIR / "mutations.json"
MUTATION_FREEZE_FILE = DATA_DIR / "mutation_freeze_manifest.json"
FIRST_SEMANTIC_FILE = DATA_DIR / "semantic_wall_first_run.json"

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

MUTATION_CHECKER_FILE = (
    ROOT
    / "scripts"
    / "check_baseline_requirements_gen3_mutations.py"
)

RUNNER_FILE = Path(__file__).resolve()

RESULT_FILE = (
    DATA_DIR
    / "mutation_wall_first_run.json"
)


def sha256(target_file):
    return hashlib.sha256(
        target_file.read_bytes()
    ).hexdigest()


def apply_operations(source_facts, operations):
    facts = deepcopy(source_facts)

    for operation in operations:
        op = operation["op"]
        key = operation["key"]

        if op == "set":
            facts[key] = operation["value"]

        elif op == "delete":
            facts.pop(
                key,
                None,
            )

        else:
            raise AssertionError(
                f"unsupported operation: {op}"
            )

    return facts


def verify_mutation_freeze():
    manifest = json.loads(
        MUTATION_FREEZE_FILE.read_text()
    )

    assert manifest[
        "created_before_first_mutation_execution"
    ] is True

    assert manifest["historical_mutation_set"] is True

    assert manifest[
        "may_not_be_rewritten_to_satisfy_evaluator"
    ] is True

    for item in manifest["artifacts"]:
        target_file = ROOT / item["path"]

        actual = sha256(
            target_file
        )

        assert actual == item["sha256"], (
            f"mutation freeze drift: {item['path']}"
        )


def main():
    if RESULT_FILE.exists():
        raise RuntimeError(
            "Refusing to overwrite historical first "
            "mutation-wall result"
        )

    verify_mutation_freeze()

    source_cases = {
        item["id"]: item
        for item in json.loads(
            CASES_FILE.read_text()
        )["cases"]
    }

    mutation_contract = json.loads(
        MUTATION_CONTRACT_FILE.read_text()
    )

    mutation_doc = json.loads(
        MUTATIONS_FILE.read_text()
    )

    mutations = mutation_doc["mutations"]

    assert mutation_contract[
        "case_source_class"
    ] == "KNOWN_DEVELOPMENT_MUTATION"

    assert mutation_contract["fresh_holdout"] is False
    assert mutation_contract["protected_evaluation"] is False

    assert len(mutations) == \
        mutation_contract["expected_mutation_count"]

    #
    # Phase 1:
    # materialize evaluator inputs WITHOUT labels,
    # expected decisions, or expected violation codes.
    #
    evaluator_inputs = []

    materialized = {}

    for mutation in mutations:
        source_case = source_cases[
            mutation["source_case_id"]
        ]

        assert source_case[
            "primary_requirement"
        ] == mutation[
            "primary_requirement"
        ]

        mutated_facts = apply_operations(
            source_case["facts"],
            mutation["operations"],
        )

        assert mutated_facts != \
            source_case["facts"]

        materialized[
            mutation["id"]
        ] = {
            "source_case_id":
                mutation["source_case_id"],
            "primary_requirement":
                mutation["primary_requirement"],
            "environment":
                source_case["environment"],
            "facts":
                mutated_facts,
        }

        evaluator_inputs.append({
            "id":
                mutation["id"],
            "primary_requirement":
                mutation["primary_requirement"],
            "environment":
                source_case["environment"],
            "facts":
                mutated_facts,
        })

    #
    # Phase 2:
    # finish every semantic prediction before any
    # expectation is consulted.
    #
    predictions = {}

    for item in evaluator_inputs:
        outcome = evaluate(
            primary_requirement=
                item["primary_requirement"],
            facts=
                item["facts"],
            environment=
                item["environment"],
        )

        assert set(outcome) == {
            "decision",
            "violations",
        }

        assert outcome["decision"] in {
            "ACCEPT",
            "REJECT",
        }

        assert isinstance(
            outcome["violations"],
            list,
        )

        if outcome["decision"] == "ACCEPT":
            assert not outcome["violations"]
        else:
            assert outcome["violations"]

        predictions[
            item["id"]
        ] = {
            "decision":
                outcome["decision"],
            "violations":
                outcome["violations"],
        }

    #
    # Phase 3:
    # only now score against frozen expectations.
    #
    results = []

    false_accepts = []
    false_rejects = []
    violation_contract_mismatches = []

    for mutation in mutations:
        prediction = predictions[
            mutation["id"]
        ]

        expected_decision = (
            "ACCEPT"
            if mutation["expectation"] == "MUST_ACCEPT"
            else "REJECT"
        )

        decision_match = (
            prediction["decision"]
            == expected_decision
        )

        expected_codes = set(
            mutation["expected_violation_codes"]
        )

        actual_codes = set(
            prediction["violations"]
        )

        if expected_decision == "ACCEPT":
            violation_contract_match = (
                actual_codes == set()
            )

        else:
            violation_contract_match = (
                expected_codes.issubset(
                    actual_codes
                )
            )

        matched = (
            decision_match
            and violation_contract_match
        )

        if (
            expected_decision == "REJECT"
            and prediction["decision"] == "ACCEPT"
        ):
            false_accepts.append(
                mutation["id"]
            )

        if (
            expected_decision == "ACCEPT"
            and prediction["decision"] == "REJECT"
        ):
            false_rejects.append(
                mutation["id"]
            )

        if (
            decision_match
            and not violation_contract_match
        ):
            violation_contract_mismatches.append(
                mutation["id"]
            )

        materialized_input = materialized[
            mutation["id"]
        ]

        results.append({
            "mutation_id":
                mutation["id"],
            "source_case_id":
                mutation["source_case_id"],
            "primary_requirement":
                mutation["primary_requirement"],
            "environment":
                materialized_input["environment"],
            "expectation":
                mutation["expectation"],
            "expected_decision":
                expected_decision,
            "expected_violation_codes":
                mutation["expected_violation_codes"],
            "predicted_decision":
                prediction["decision"],
            "actual_violation_codes":
                prediction["violations"],
            "decision_match":
                decision_match,
            "violation_contract_match":
                violation_contract_match,
            "matched":
                matched,
            "operations":
                mutation["operations"],
            "materialized_facts":
                materialized_input["facts"],
        })

    match_count = sum(
        item["matched"]
        for item in results
    )

    mismatch_count = (
        len(results) - match_count
    )

    status = (
        "PASS"
        if mismatch_count == 0
        else "FAIL"
    )

    payload = {
        "schema_version": "1.0.0",
        "artifact_type":
            "TASK_8_GEN3_MUTATION_WALL_FIRST_RUN",
        "state":
            "DEVELOPMENT_MUTATION_QUALIFICATION",
        "authoritative":
            False,
        "scientific_support_established":
            False,
        "fresh_holdout":
            False,
        "protected_evaluation":
            False,
        "case_source_class":
            "KNOWN_DEVELOPMENT_MUTATION",
        "historical_first_execution":
            True,
        "may_not_be_rewritten":
            True,
        "target_generation":
            3,
        "input_hashes": {
            "generation_3_sha256":
                sha256(GEN3_FILE),
            "cases_sha256":
                sha256(CASES_FILE),
            "mutation_contract_sha256":
                sha256(MUTATION_CONTRACT_FILE),
            "mutations_sha256":
                sha256(MUTATIONS_FILE),
            "mutation_freeze_manifest_sha256":
                sha256(MUTATION_FREEZE_FILE),
            "semantic_evaluator_sha256":
                sha256(EVALUATOR_FILE),
            "mutation_checker_sha256":
                sha256(MUTATION_CHECKER_FILE),
            "historical_54_case_run_sha256":
                sha256(FIRST_SEMANTIC_FILE),
            "runner_sha256":
                sha256(RUNNER_FILE),
        },
        "summary": {
            "status":
                status,
            "mutation_count":
                len(results),
            "match_count":
                match_count,
            "mismatch_count":
                mismatch_count,
            "false_accept_count":
                len(false_accepts),
            "false_reject_count":
                len(false_rejects),
            "violation_contract_mismatch_count":
                len(
                    violation_contract_mismatches
                ),
            "false_accept_mutation_ids":
                false_accepts,
            "false_reject_mutation_ids":
                false_rejects,
            "violation_contract_mismatch_ids":
                violation_contract_mismatches,
        },
        "results":
            results,
        "interpretation":
            "This is the first execution of the frozen known-development "
            "Generation 3 mutation corpus. A failure is preserved as "
            "historical development evidence and must be classified before "
            "remediation. This result is not a fresh holdout, protected "
            "evaluation, independent verification, scientific support, or "
            "Task 8 authority."
    }

    RESULT_FILE.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=False,
        ) + "\n"
    )

    print(
        "FIRST MUTATION WALL STATUS:",
        status,
    )

    print(
        "Mutations:",
        len(results),
    )

    print(
        "Matches:",
        match_count,
    )

    print(
        "Mismatches:",
        mismatch_count,
    )

    print(
        "False accepts:",
        false_accepts,
    )

    print(
        "False rejects:",
        false_rejects,
    )

    print(
        "Violation-contract mismatches:",
        violation_contract_mismatches,
    )

    if mismatch_count:
        print()
        print("===== MUTATION MISMATCH DETAILS =====")

        for item in results:
            if not item["matched"]:
                print(
                    item["mutation_id"],
                    item["primary_requirement"],
                    "expected=",
                    item["expected_decision"],
                    "predicted=",
                    item["predicted_decision"],
                    "expected_codes=",
                    item["expected_violation_codes"],
                    "actual_codes=",
                    item["actual_violation_codes"],
                )

    sys.exit(
        0
        if status == "PASS"
        else 1
    )


if __name__ == "__main__":
    main()
