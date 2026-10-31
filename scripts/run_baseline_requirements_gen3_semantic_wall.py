#!/usr/bin/env python3

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
CONTRACT_FILE = DATA_DIR / "contract.json"
FREEZE_FILE = DATA_DIR / "dev_case_freeze_manifest.json"

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

RUNNER_FILE = Path(__file__).resolve()

RESULT_FILE = (
    DATA_DIR
    / "semantic_wall_first_run.json"
)


def sha256(target_file):
    return hashlib.sha256(
        target_file.read_bytes()
    ).hexdigest()


def main():
    if RESULT_FILE.exists():
        raise RuntimeError(
            "Refusing to overwrite historical first-run result"
        )

    cases_doc = json.loads(
        CASES_FILE.read_text()
    )

    contract = json.loads(
        CONTRACT_FILE.read_text()
    )

    freeze = json.loads(
        FREEZE_FILE.read_text()
    )

    assert contract["case_source_class"] == \
        "KNOWN_DEVELOPMENT_CASE"

    assert contract["fresh_holdout"] is False
    assert contract["protected_evaluation"] is False

    assert freeze["historical_case_set"] is True
    assert freeze["fresh_holdout"] is False

    cases = cases_doc["cases"]

    assert len(cases) == 54

    #
    # Build evaluator inputs WITHOUT expectation labels.
    #
    evaluator_inputs = [
        {
            "id": case["id"],
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

    #
    # Complete every semantic decision before consulting
    # MUST_ACCEPT / MUST_REJECT for scoring.
    #
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

        predictions[item["id"]] = {
            "decision":
                outcome["decision"],
            "violations":
                outcome["violations"],
        }

    #
    # Only after all predictions exist do we score them
    # against the frozen development expectations.
    #
    results = []

    false_accepts = []
    false_rejects = []

    for case in cases:
        prediction = predictions[
            case["id"]
        ]

        expected_decision = (
            "ACCEPT"
            if case["expectation"] == "MUST_ACCEPT"
            else "REJECT"
        )

        matched = (
            prediction["decision"]
            == expected_decision
        )

        if (
            case["expectation"] == "MUST_REJECT"
            and prediction["decision"] == "ACCEPT"
        ):
            false_accepts.append(
                case["id"]
            )

        if (
            case["expectation"] == "MUST_ACCEPT"
            and prediction["decision"] == "REJECT"
        ):
            false_rejects.append(
                case["id"]
            )

        results.append({
            "case_id":
                case["id"],
            "primary_requirement":
                case["primary_requirement"],
            "requirement_key":
                case["requirement_key"],
            "environment":
                case["environment"],
            "expectation":
                case["expectation"],
            "expected_decision":
                expected_decision,
            "predicted_decision":
                prediction["decision"],
            "violations":
                prediction["violations"],
            "matched":
                matched,
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
            "TASK_8_GEN3_SEMANTIC_WALL_FIRST_RUN",
        "state":
            "DEVELOPMENT_QUALIFICATION",
        "authoritative":
            False,
        "scientific_support_established":
            False,
        "fresh_holdout":
            False,
        "protected_evaluation":
            False,
        "case_source_class":
            "KNOWN_DEVELOPMENT_CASE",
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
            "contract_sha256":
                sha256(CONTRACT_FILE),
            "freeze_manifest_sha256":
                sha256(FREEZE_FILE),
            "semantic_evaluator_sha256":
                sha256(EVALUATOR_FILE),
            "runner_sha256":
                sha256(RUNNER_FILE),
        },
        "summary": {
            "status":
                status,
            "case_count":
                len(results),
            "match_count":
                match_count,
            "mismatch_count":
                mismatch_count,
            "false_accept_count":
                len(false_accepts),
            "false_reject_count":
                len(false_rejects),
            "false_accept_case_ids":
                false_accepts,
            "false_reject_case_ids":
                false_rejects,
        },
        "results":
            results,
        "interpretation":
            "This is the first semantic execution against the frozen known-"
            "development Generation 3 case set. It is development evidence, "
            "not a fresh holdout, protected evaluation, independent scientific "
            "verification, scientific support, or Task 8 authority."
    }

    RESULT_FILE.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=False,
        ) + "\n"
    )

    print(
        "FIRST SEMANTIC WALL STATUS:",
        status,
    )

    print(
        "Cases:",
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

    if mismatch_count:
        print()
        print("===== MISMATCH DETAILS =====")

        for item in results:
            if not item["matched"]:
                print(
                    item["case_id"],
                    item["primary_requirement"],
                    "expected=",
                    item["expected_decision"],
                    "predicted=",
                    item["predicted_decision"],
                    "violations=",
                    item["violations"],
                )

    sys.exit(
        0
        if status == "PASS"
        else 1
    )


if __name__ == "__main__":
    main()
