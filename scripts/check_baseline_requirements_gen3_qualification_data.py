#!/usr/bin/env python3

from collections import Counter, defaultdict
from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "baseline_requirements_gen3"
)

CONTRACT_FILE = DATA_DIR / "contract.json"
SCHEMA_FILE = DATA_DIR / "schema.json"
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


def main():
    contract = load_json(CONTRACT_FILE)
    schema = load_json(SCHEMA_FILE)
    cases_doc = load_json(CASES_FILE)
    gen3 = load_json(GEN3_FILE)

    assert contract["state"] == "DEVELOPMENT_QUALIFICATION"
    assert contract["authoritative"] is False
    assert contract["scientific_support_established"] is False
    assert contract["case_source_class"] == "KNOWN_DEVELOPMENT_CASE"
    assert contract["fresh_holdout"] is False
    assert contract["protected_evaluation"] is False

    assert schema["type"] == "object"
    assert schema["properties"]["case_source_class"]["const"] == \
        "KNOWN_DEVELOPMENT_CASE"

    assert cases_doc["state"] == "DEVELOPMENT_QUALIFICATION"
    assert cases_doc["authoritative"] is False
    assert cases_doc["scientific_support_established"] is False
    assert cases_doc["case_source_class"] == "KNOWN_DEVELOPMENT_CASE"

    requirements = gen3["requirements"]

    known_requirements = {
        item["id"]: item
        for item in requirements
    }

    assert len(known_requirements) == 27

    cases = cases_doc["cases"]

    assert len(cases) >= contract["minimum_case_count"]

    ids = [
        case["id"]
        for case in cases
    ]

    assert len(ids) == len(set(ids))

    assert ids == [
        f"G3-Q-{i:03d}"
        for i in range(1, len(cases) + 1)
    ]

    expectation_counts = Counter(
        case["expectation"]
        for case in cases
    )

    assert expectation_counts["MUST_ACCEPT"] >= \
        contract["minimum_must_accept"]

    assert expectation_counts["MUST_REJECT"] >= \
        contract["minimum_must_reject"]

    allowed_expectations = set(
        contract["allowed_expectations"]
    )

    allowed_environments = set(
        contract["allowed_environments"]
    )

    by_requirement = defaultdict(list)

    forbidden_source_markers = {
        "FRESH_HOLDOUT",
        "UNSEEN_HOLDOUT",
        "PROTECTED_HOLDOUT",
        "INDEPENDENT_SCIENTIFIC_EVIDENCE",
    }

    for case in cases:
        assert set(case) == {
            "id",
            "expectation",
            "source_class",
            "primary_requirement",
            "requirement_key",
            "environment",
            "title",
            "scenario",
            "facts",
            "rationale",
            "protected_outcomes_observed",
        }

        assert re.fullmatch(
            r"G3-Q-\d{3}",
            case["id"],
        )

        assert case["expectation"] in allowed_expectations
        assert case["environment"] in allowed_environments

        assert case["source_class"] == "KNOWN_DEVELOPMENT_CASE"

        assert case["source_class"] not in forbidden_source_markers

        assert case["protected_outcomes_observed"] is False

        requirement_id = case["primary_requirement"]

        assert requirement_id in known_requirements

        assert case["requirement_key"] == \
            known_requirements[requirement_id]["key"]

        assert case["title"].strip()
        assert case["scenario"].strip()
        assert case["rationale"].strip()

        assert isinstance(case["facts"], dict)
        assert case["facts"]

        by_requirement[requirement_id].append(case)

    expected_requirement_ids = {
        f"G3-BR-{i:03d}"
        for i in range(1, 28)
    }

    assert set(by_requirement) == expected_requirement_ids

    required_expectations = set(
        contract["required_expectations_per_requirement"]
    )

    for requirement_id in sorted(expected_requirement_ids):
        requirement_cases = by_requirement[requirement_id]

        assert len(requirement_cases) >= \
            contract["minimum_cases_per_requirement"]

        expectations = {
            case["expectation"]
            for case in requirement_cases
        }

        assert required_expectations.issubset(
            expectations
        )

    assert not (
        ROOT
        / "docs"
        / "mvp"
        / "08-baselines.md"
    ).exists()

    premature_decisions = list(
        (ROOT / "docs" / "decisions").glob(
            "0009-baseline*.md"
        )
    )

    assert not premature_decisions

    print("PASS: Task 8 Generation 3 qualification data")
    print(f"Cases: {len(cases)}")
    print(
        "MUST_ACCEPT:",
        expectation_counts["MUST_ACCEPT"],
    )
    print(
        "MUST_REJECT:",
        expectation_counts["MUST_REJECT"],
    )
    print(
        "Requirements covered:",
        len(by_requirement),
    )
    print(
        "Source class:",
        contract["case_source_class"],
    )
    print("Fresh holdout: NO")
    print("Scientific support established: NO")
    print("Task 8 authority established: NO")


if __name__ == "__main__":
    main()
