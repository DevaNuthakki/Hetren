#!/usr/bin/env python3

from collections import Counter
from copy import deepcopy
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "baseline_requirements_gen3"
)

CONTRACT_FILE = DATA_DIR / "mutation_contract.json"
MUTATIONS_FILE = DATA_DIR / "mutations.json"
CASES_FILE = DATA_DIR / "cases.json"

GEN3_FILE = (
    ROOT
    / "docs"
    / "research"
    / "baselines"
    / "task-08-baseline-requirements-gen3.json"
)


def load_json(target_file):
    return json.loads(
        target_file.read_text()
    )


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
                f"unsupported mutation operation: {op}"
            )

    return facts


def main():
    contract = load_json(CONTRACT_FILE)
    mutation_doc = load_json(MUTATIONS_FILE)
    case_doc = load_json(CASES_FILE)
    gen3 = load_json(GEN3_FILE)

    assert contract["state"] == \
        "DEVELOPMENT_MUTATION_QUALIFICATION"

    assert contract["authoritative"] is False
    assert contract["scientific_support_established"] is False
    assert contract["fresh_holdout"] is False
    assert contract["protected_evaluation"] is False

    assert contract["case_source_class"] == \
        "KNOWN_DEVELOPMENT_MUTATION"

    assert mutation_doc["state"] == \
        "DEVELOPMENT_MUTATION_QUALIFICATION"

    assert mutation_doc["authoritative"] is False
    assert mutation_doc["scientific_support_established"] is False
    assert mutation_doc["fresh_holdout"] is False
    assert mutation_doc["protected_evaluation"] is False

    source_cases = {
        item["id"]: item
        for item in case_doc["cases"]
    }

    requirements = {
        item["id"]: item
        for item in gen3["requirements"]
    }

    mutations = mutation_doc["mutations"]

    assert len(mutations) == \
        contract["expected_mutation_count"]

    ids = [
        item["id"]
        for item in mutations
    ]

    assert ids == [
        f"G3-M-{number:03d}"
        for number in range(
            1,
            len(mutations) + 1,
        )
    ]

    assert len(ids) == len(set(ids))

    expectation_counts = Counter(
        item["expectation"]
        for item in mutations
    )

    assert expectation_counts["MUST_ACCEPT"] == \
        contract["expected_must_accept"]

    assert expectation_counts["MUST_REJECT"] == \
        contract["expected_must_reject"]

    allowed_expectations = set(
        contract["allowed_expectations"]
    )

    allowed_operations = set(
        contract["allowed_operations"]
    )

    covered_requirements = set()

    for item in mutations:
        assert set(item) == {
            "id",
            "source_case_id",
            "primary_requirement",
            "expectation",
            "operations",
            "expected_violation_codes",
            "rationale",
        }

        assert item["expectation"] in \
            allowed_expectations

        assert item["source_case_id"] in \
            source_cases

        assert item["primary_requirement"] in \
            requirements

        source_case = source_cases[
            item["source_case_id"]
        ]

        assert source_case["primary_requirement"] == \
            item["primary_requirement"]

        assert item["operations"]

        for operation in item["operations"]:
            assert operation["op"] in \
                allowed_operations

            assert operation["key"]

            if operation["op"] == "set":
                assert set(operation) == {
                    "op",
                    "key",
                    "value",
                }

            if operation["op"] == "delete":
                assert set(operation) == {
                    "op",
                    "key",
                }

        mutated_facts = apply_operations(
            source_case["facts"],
            item["operations"],
        )

        assert mutated_facts != \
            source_case["facts"]

        if item["expectation"] == "MUST_ACCEPT":
            assert item["expected_violation_codes"] == []

        else:
            assert item["expected_violation_codes"]

        assert item["rationale"].strip()

        covered_requirements.add(
            item["primary_requirement"]
        )

    expected_requirements = {
        f"G3-BR-{number:03d}"
        for number in range(1, 28)
    }

    assert covered_requirements == \
        expected_requirements

    print("PASS: mutation registry structural qualification")
    print("Mutations:", len(mutations))
    print(
        "MUST_ACCEPT:",
        expectation_counts["MUST_ACCEPT"],
    )
    print(
        "MUST_REJECT:",
        expectation_counts["MUST_REJECT"],
    )
    print(
        "G3 requirements covered:",
        len(covered_requirements),
    )
    print("Fresh holdout: NO")
    print("Scientific support established: NO")
    print("Task 8 authority established: NO")


if __name__ == "__main__":
    main()
