from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import sys

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = (
    ROOT
    / "tests"
    / "qualification"
    / "data"
    / "initial_splits"
)

EVIDENCE_DIR = (
    ROOT
    / "docs"
    / "decisions"
    / "qualification"
    / "evidence"
)


QUALIFICATION = (
    DATA_DIR
    / "qualification_cases.json"
)

QUALIFICATION_SCHEMA = (
    DATA_DIR
    / "qualification_cases.schema.json"
)

HISTORICAL = (
    DATA_DIR
    / "historical_cases.json"
)

POSITIVE = (
    DATA_DIR
    / "positive_cases.json"
)

SET_D = (
    DATA_DIR
    / "set_d_cases.json"
)

P1_FIRST_RUN = (
    EVIDENCE_DIR
    / "0008-positive-boundary-set-p1-first-run.txt"
)

SET_D_FIRST_RUN = (
    EVIDENCE_DIR
    / "0008-red-team-set-d-first-run.txt"
)

SET_E = (
    DATA_DIR
    / "set_e_cases.json"
)

POST_SET_E = (
    DATA_DIR
    / "set_e_remediation_cases.json"
)

SET_E_FIRST_RUN = (
    EVIDENCE_DIR
    / "0008-red-team-set-e-first-run.txt"
)

SET_E_REGRESSION = (
    EVIDENCE_DIR
    / "0008-red-team-set-e-remediation-2-regression.txt"
)

SET_E_PREREGISTRATION = (
    EVIDENCE_DIR
    / "0008-red-team-set-e-preregistration.md"
)

SET_E_PRE_RUN_FREEZE = (
    EVIDENCE_DIR
    / "0008-set-e-pre-run-freeze.sha256"
)

CURRENT_WALL = (
    EVIDENCE_DIR
    / "0008-set-e-remediation-attempt-2-wall.txt"
)

CURRENT_RECORD = (
    EVIDENCE_DIR
    / "0008-set-e-remediation-attempt-2.md"
)


EXPECTED_SUITE_COUNTS = {
    "CANONICAL": 52,
    "SET_A": 12,
    "SET_B": 12,
    "SET_C": 64,
    "P1": 24,
    "SET_D": 32,
    "SET_E": 32,
    "SET_E_REMEDIATION": 13,
}

EXPECTED_EXPECTATION_COUNTS = {
    "MUST_REJECT": 181,
    "MUST_ACCEPT": 60,
}

EXPECTED_FIRST_RUN_SUMMARY = {
    "KNOWN_DEVELOPMENT_CASE": 52,
    "ACCEPTED": 144,
    "REJECTED": 32,
    "KNOWN_REGRESSION_CASE": 13,
}

EXPECTED_CURRENT_SUMMARY = {
    "ACCEPTED": 60,
    "REJECTED": 181,
}

EXPECTED_P1_FIRST_REJECTED = {
    "T7-POS-C05-01",
    "T7-POS-C05-03",
}

EXPECTED_SET_D_FIRST_INCORRECT = {
    "T7-D-01-01": "MUST_REJECT",
    "T7-D-01-02": "MUST_REJECT",
    "T7-D-04-02": "MUST_REJECT",
    "T7-D-05-01": "MUST_REJECT",
    "T7-D-05-04": "MUST_ACCEPT",
    "T7-D-06-01": "MUST_REJECT",
    "T7-D-06-02": "MUST_REJECT",
    "T7-D-07-01": "MUST_REJECT",
    "T7-D-07-02": "MUST_REJECT",
    "T7-D-08-01": "MUST_REJECT",
    "T7-D-08-02": "MUST_REJECT",
}

EXPECTED_SET_E_FIRST_INCORRECT = {
    "T7-E-01-02": "MUST_REJECT",
    "T7-E-02-02": "MUST_REJECT",
    "T7-E-03-01": "MUST_REJECT",
    "T7-E-03-03": "MUST_ACCEPT",
    "T7-E-04-01": "MUST_REJECT",
    "T7-E-04-02": "MUST_REJECT",
    "T7-E-05-02": "MUST_REJECT",
    "T7-E-06-01": "MUST_REJECT",
    "T7-E-06-02": "MUST_REJECT",
    "T7-E-07-01": "MUST_REJECT",
    "T7-E-07-02": "MUST_REJECT",
    "T7-E-08-02": "MUST_REJECT",
}


def load_json(
    path: Path,
):
    return json.loads(
        path.read_text()
    )


def sha256(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def disposition_for_expected(
    expected: str,
) -> str:
    if expected == "MUST_ACCEPT":
        return "ACCEPTED"

    if expected == "MUST_REJECT":
        return "REJECTED"

    raise AssertionError(
        f"unknown expected value: {expected}"
    )


def source_hashes() -> dict[str, str]:
    paths = (
        HISTORICAL,
        POSITIVE,
        SET_D,
        SET_E,
        POST_SET_E,
        P1_FIRST_RUN,
        SET_D_FIRST_RUN,
        SET_E_FIRST_RUN,
        SET_E_REGRESSION,
        SET_E_PREREGISTRATION,
        SET_E_PRE_RUN_FREEZE,
        CURRENT_WALL,
        CURRENT_RECORD,
    )

    return {
        str(
            path.relative_to(
                ROOT
            )
        ): sha256(
            path
        )
        for path in paths
    }


def parse_p1_first_run(
    positive: dict,
) -> tuple[set[str], set[str]]:
    log = P1_FIRST_RUN.read_text()

    accepted = set(
        re.findall(
            r"PASS MUST_ACCEPT accepted: "
            r"(T7-POS-[A-Z0-9-]+)",
            log,
        )
    )

    case_ids = {
        case["case_id"]
        for case in positive[
            "cases"
        ]
    }

    assert len(
        case_ids
    ) == 24

    assert len(
        accepted
    ) == 22

    assert accepted <= case_ids

    rejected = (
        case_ids
        - accepted
    )

    assert (
        rejected
        == EXPECTED_P1_FIRST_REJECTED
    )

    assert (
        "Accepted: 22/24"
        in log
    )

    return (
        accepted,
        rejected,
    )


def parse_set_d_first_run() -> dict[str, str]:
    log = SET_D_FIRST_RUN.read_text()

    incorrect = {
        case_id: expected
        for case_id, expected in re.findall(
            r"^- (T7-D-[0-9-]+) "
            r"expected=(MUST_[A-Z]+)$",
            log,
            flags=re.MULTILINE,
        )
    }

    assert (
        incorrect
        == EXPECTED_SET_D_FIRST_INCORRECT
    )

    assert (
        "Correct: 21/32"
        in log
    )

    assert (
        "Incorrect: 11/32"
        in log
    )

    return incorrect



def parse_set_e_first_run() -> dict[str, str]:
    log = SET_E_FIRST_RUN.read_text()

    incorrect = {
        case_id: expected
        for case_id, expected in re.findall(
            r"^- (T7-E-[0-9-]+) "
            r"expected=(MUST_[A-Z]+)$",
            log,
            flags=re.MULTILINE,
        )
    }

    assert (
        incorrect
        == EXPECTED_SET_E_FIRST_INCORRECT
    )

    assert (
        "Correct: 20/32"
        in log
    )

    assert (
        "Incorrect: 12/32"
        in log
    )

    assert (
        "TASK 7 SET E HOLDOUT: FAIL (20/32 correct)"
        in log
    )

    return incorrect


def validate_set_e_regression() -> None:
    log = SET_E_REGRESSION.read_text()

    assert (
        "Correct: 32/32"
        in log
    )

    assert (
        "Incorrect: 0/32"
        in log
    )

    assert (
        "TASK 7 SET E HOLDOUT: PASS (32/32 correct)"
        in log
    )

    pass_ids = set(
        re.findall(
            r"^PASS "
            r"(T7-E-[0-9-]+) "
            r"(?:MUST_REJECT|MUST_ACCEPT)$",
            log,
            flags=re.MULTILINE,
        )
    )

    set_e = load_json(
        SET_E
    )

    expected_ids = {
        item["case_id"]
        for item in set_e[
            "cases"
        ]
    }

    assert len(
        expected_ids
    ) == 32

    assert pass_ids == expected_ids


def validate_current_wall() -> None:
    wall = CURRENT_WALL.read_text()
    record = CURRENT_RECORD.read_text()

    assert (
        "Set E execution in this wall: NO"
        in wall
    )

    expected_zero_lines = (
        "REAL DRAFT VALIDATOR: 0",
        "FROZEN CANONICAL 68: 0",
        "P1 MUST_ACCEPT: 0",
        "SET A REGRESSION: 0",
        "SET B REGRESSION: 0",
        "SET C REGRESSION: 0",
        "SET D REGRESSION: 0",
        "HISTORICAL STRUCTURED DATA: 0",
        "HISTORICAL DATA MUTATIONS: 0",
        "UNIFIED 196-CASE REGISTRY: 0",
        "QUALIFICATION DATA MUTATIONS: 0",
        "POST-SET-E KNOWN REGRESSIONS: 0",
        "DIFF CHECK: 0",
    )

    for expected_line in expected_zero_lines:
        assert expected_line in wall, (
            f"Attempt 2 wall missing success line: "
            f"{expected_line}"
        )

    assert (
        "**Status:** `PRE-SET-E REGRESSION WALL PASS`"
        in record
    )

    assert (
        "authoritative Set E unseen first run "
        "remains permanently `20 / 32`"
        in record
    )

    assert (
        "regression evidence only"
        in record
    )


def expected_cases() -> list[dict]:
    historical = load_json(
        HISTORICAL
    )

    positive = load_json(
        POSITIVE
    )

    set_d = load_json(
        SET_D
    )

    set_e = load_json(
        SET_E
    )

    post_set_e = load_json(
        POST_SET_E
    )

    p1_accepted, _ = (
        parse_p1_first_run(
            positive
        )
    )

    set_d_incorrect = (
        parse_set_d_first_run()
    )

    set_e_incorrect = (
        parse_set_e_first_run()
    )

    validate_set_e_regression()

    current_ref = str(
        CURRENT_WALL.relative_to(
            ROOT
        )
    )

    set_e_current_ref = str(
        SET_E_REGRESSION.relative_to(
            ROOT
        )
    )

    result = []

    historical_first_map = {
        "KNOWN_DEVELOPMENT_CASE":
            "KNOWN_DEVELOPMENT_CASE",
        "SURVIVED":
            "ACCEPTED",
        "REJECTED":
            "REJECTED",
    }

    for item in historical[
        "cases"
    ]:
        result.append(
            {
                "case_id":
                    item["case_id"],
                "suite":
                    item["suite"],
                "ordinal":
                    item["ordinal"],
                "label":
                    item["label"],
                "family_id":
                    None,
                "family":
                    None,
                "expected":
                    item["expected"],
                "evidence_class":
                    item[
                        "evidence_class"
                    ],
                "historical_unseen":
                    item[
                        "historical_unseen"
                    ],
                "first_run_disposition":
                    historical_first_map[
                        item[
                            "first_run_disposition"
                        ]
                    ],
                "current_disposition":
                    "REJECTED",
                "definition_ref":
                    item[
                        "source_file"
                    ],
                "first_run_evidence_ref":
                    item[
                        "evidence_ref"
                    ],
                "current_evidence_ref":
                    current_ref,
            }
        )

    for ordinal, item in enumerate(
        positive["cases"],
        start=1,
    ):
        case_id = item[
            "case_id"
        ]

        result.append(
            {
                "case_id":
                    case_id,
                "suite":
                    "P1",
                "ordinal":
                    ordinal,
                "label":
                    item[
                        "family"
                    ],
                "family_id":
                    item[
                        "family_id"
                    ],
                "family":
                    item[
                        "family"
                    ],
                "expected":
                    item[
                        "expected"
                    ],
                "evidence_class":
                    "FROZEN_POSITIVE_BOUNDARY",
                "historical_unseen":
                    True,
                "first_run_disposition":
                    (
                        "ACCEPTED"
                        if case_id
                        in p1_accepted
                        else "REJECTED"
                    ),
                "current_disposition":
                    "ACCEPTED",
                "definition_ref":
                    str(
                        POSITIVE.relative_to(
                            ROOT
                        )
                    ),
                "first_run_evidence_ref":
                    str(
                        P1_FIRST_RUN.relative_to(
                            ROOT
                        )
                    ),
                "current_evidence_ref":
                    current_ref,
            }
        )

    for ordinal, item in enumerate(
        set_d["cases"],
        start=1,
    ):
        case_id = item[
            "case_id"
        ]

        expected = item[
            "expected"
        ]

        if case_id in set_d_incorrect:
            first = (
                "REJECTED"
                if expected
                == "MUST_ACCEPT"
                else "ACCEPTED"
            )
        else:
            first = (
                disposition_for_expected(
                    expected
                )
            )

        result.append(
            {
                "case_id":
                    case_id,
                "suite":
                    "SET_D",
                "ordinal":
                    ordinal,
                "label":
                    item[
                        "description"
                    ],
                "family_id":
                    item[
                        "family_id"
                    ],
                "family":
                    item[
                        "family"
                    ],
                "expected":
                    expected,
                "evidence_class":
                    "FROZEN_FRESH_HOLDOUT",
                "historical_unseen":
                    True,
                "first_run_disposition":
                    first,
                "current_disposition":
                    disposition_for_expected(
                        expected
                    ),
                "definition_ref":
                    str(
                        SET_D.relative_to(
                            ROOT
                        )
                    ),
                "first_run_evidence_ref":
                    str(
                        SET_D_FIRST_RUN.relative_to(
                            ROOT
                        )
                    ),
                "current_evidence_ref":
                    current_ref,
            }
        )

    for ordinal, item in enumerate(
        set_e["cases"],
        start=1,
    ):
        case_id = item[
            "case_id"
        ]

        expected = item[
            "expected"
        ]

        if case_id in set_e_incorrect:
            first = (
                "REJECTED"
                if expected
                == "MUST_ACCEPT"
                else "ACCEPTED"
            )
        else:
            first = (
                disposition_for_expected(
                    expected
                )
            )

        result.append(
            {
                "case_id":
                    case_id,
                "suite":
                    "SET_E",
                "ordinal":
                    ordinal,
                "label":
                    item[
                        "description"
                    ],
                "family_id":
                    item[
                        "family_id"
                    ],
                "family":
                    item[
                        "family"
                    ],
                "expected":
                    expected,
                "evidence_class":
                    "FROZEN_FINAL_UNSEEN_HOLDOUT",
                "historical_unseen":
                    True,
                "first_run_disposition":
                    first,
                "current_disposition":
                    disposition_for_expected(
                        expected
                    ),
                "definition_ref":
                    str(
                        SET_E.relative_to(
                            ROOT
                        )
                    ),
                "first_run_evidence_ref":
                    str(
                        SET_E_FIRST_RUN.relative_to(
                            ROOT
                        )
                    ),
                "current_evidence_ref":
                    set_e_current_ref,
            }
        )

    for ordinal, item in enumerate(
        post_set_e["cases"],
        start=1,
    ):
        result.append(
            {
                "case_id":
                    item[
                        "case_id"
                    ],
                "suite":
                    "SET_E_REMEDIATION",
                "ordinal":
                    ordinal,
                "label":
                    (
                        item[
                            "expected_label"
                        ]
                        or item[
                            "addition"
                        ]
                    ),
                "family_id":
                    None,
                "family":
                    None,
                "expected":
                    item[
                        "expected"
                    ],
                "evidence_class":
                    "KNOWN_REGRESSION",
                "historical_unseen":
                    False,
                "first_run_disposition":
                    "KNOWN_REGRESSION_CASE",
                "current_disposition":
                    disposition_for_expected(
                        item[
                            "expected"
                        ]
                    ),
                "definition_ref":
                    str(
                        POST_SET_E.relative_to(
                            ROOT
                        )
                    ),
                "first_run_evidence_ref":
                    current_ref,
                "current_evidence_ref":
                    current_ref,
            }
        )

    return result


def validate_qualification_semantics(
    qualification: dict,
) -> None:
    validate_current_wall()

    parse_set_e_first_run()
    validate_set_e_regression()

    assert qualification[
        "qualification_case_count"
    ] == 241

    cases = qualification[
        "cases"
    ]

    assert len(
        cases
    ) == 241

    assert len(
        {
            item["case_id"]
            for item in cases
        }
    ) == 241

    actual_suite_counts = dict(
        Counter(
            item["suite"]
            for item in cases
        )
    )

    assert (
        actual_suite_counts
        == EXPECTED_SUITE_COUNTS
    )

    actual_expectation_counts = dict(
        Counter(
            item["expected"]
            for item in cases
        )
    )

    assert (
        actual_expectation_counts
        == EXPECTED_EXPECTATION_COUNTS
    )

    actual_first_run_summary = dict(
        Counter(
            item[
                "first_run_disposition"
            ]
            for item in cases
        )
    )

    assert (
        actual_first_run_summary
        == EXPECTED_FIRST_RUN_SUMMARY
    )

    actual_current_summary = dict(
        Counter(
            item[
                "current_disposition"
            ]
            for item in cases
        )
    )

    assert (
        actual_current_summary
        == EXPECTED_CURRENT_SUMMARY
    )

    assert qualification[
        "suite_counts"
    ] == EXPECTED_SUITE_COUNTS

    assert qualification[
        "expectation_counts"
    ] == EXPECTED_EXPECTATION_COUNTS

    assert qualification[
        "first_run_summary"
    ] == EXPECTED_FIRST_RUN_SUMMARY

    assert qualification[
        "current_summary"
    ] == EXPECTED_CURRENT_SUMMARY

    assert qualification[
        "source_hashes"
    ] == source_hashes()

    expected = expected_cases()

    assert cases == expected, (
        "qualification case registry no longer "
        "matches authoritative source evidence"
    )

    for item in cases:
        expected_current = (
            disposition_for_expected(
                item["expected"]
            )
        )

        assert (
            item[
                "current_disposition"
            ]
            == expected_current
        )

    p1 = [
        item
        for item in cases
        if item["suite"]
        == "P1"
    ]

    p1_original_rejected = {
        item["case_id"]
        for item in p1
        if item[
            "first_run_disposition"
        ] == "REJECTED"
    }

    assert (
        p1_original_rejected
        == EXPECTED_P1_FIRST_REJECTED
    )

    set_d = [
        item
        for item in cases
        if item["suite"]
        == "SET_D"
    ]

    set_d_original_incorrect = {
        item["case_id"]
        for item in set_d
        if (
            item[
                "first_run_disposition"
            ]
            != disposition_for_expected(
                item["expected"]
            )
        )
    }

    assert (
        set_d_original_incorrect
        == set(
            EXPECTED_SET_D_FIRST_INCORRECT
        )
    )

    set_e = [
        item
        for item in cases
        if item["suite"]
        == "SET_E"
    ]

    assert len(
        set_e
    ) == 32

    assert all(
        item[
            "historical_unseen"
        ]
        for item in set_e
    )

    assert all(
        item[
            "evidence_class"
        ]
        == "FROZEN_FINAL_UNSEEN_HOLDOUT"
        for item in set_e
    )

    set_e_original_incorrect = {
        item["case_id"]
        for item in set_e
        if (
            item[
                "first_run_disposition"
            ]
            != disposition_for_expected(
                item["expected"]
            )
        )
    }

    assert (
        set_e_original_incorrect
        == set(
            EXPECTED_SET_E_FIRST_INCORRECT
        )
    )

    assert (
        Counter(
            item[
                "first_run_disposition"
            ]
            for item in set_e
        )
        == Counter(
            {
                "ACCEPTED": 26,
                "REJECTED": 6,
            }
        )
    )

    set_e_current_ref = str(
        SET_E_REGRESSION.relative_to(
            ROOT
        )
    )

    assert all(
        item[
            "current_evidence_ref"
        ]
        == set_e_current_ref
        for item in set_e
    )

    remediation = [
        item
        for item in cases
        if item["suite"]
        == "SET_E_REMEDIATION"
    ]

    assert len(
        remediation
    ) == 13

    assert all(
        not item[
            "historical_unseen"
        ]
        for item in remediation
    )

    assert all(
        item[
            "evidence_class"
        ]
        == "KNOWN_REGRESSION"
        for item in remediation
    )

    assert all(
        item[
            "first_run_disposition"
        ]
        == "KNOWN_REGRESSION_CASE"
        for item in remediation
    )

    assert (
        Counter(
            item[
                "expected"
            ]
            for item in remediation
        )
        == Counter(
            {
                "MUST_REJECT": 9,
                "MUST_ACCEPT": 4,
            }
        )
    )


def main() -> int:
    qualification = load_json(
        QUALIFICATION
    )

    schema = load_json(
        QUALIFICATION_SCHEMA
    )

    Draft202012Validator.check_schema(
        schema
    )

    Draft202012Validator(
        schema
    ).validate(
        qualification
    )

    validate_qualification_semantics(
        qualification
    )

    print(
        "INITIAL SPLITS QUALIFICATION DATA: PASS"
    )

    print(
        "- unified qualification cases: 241"
    )

    print(
        "- historical adversarial: 140"
    )

    print(
        "- P1 positive boundary: 24"
    )

    print(
        "- Set D mixed holdout: 32"
    )

    print(
        "- Set E final unseen holdout: 32"
    )

    print(
        "- post-Set-E known regressions: 13"
    )

    print(
        "- expected MUST_REJECT: 181"
    )

    print(
        "- expected MUST_ACCEPT: 60"
    )

    print(
        "- P1 original first run: 22 accepted / 2 rejected"
    )

    print(
        "- Set D original first run: 21 correct / 11 incorrect"
    )

    print(
        "- Set E original unseen first run: 20 correct / 12 incorrect"
    )

    print(
        "- Set E current regression: 32/32 correct"
    )

    print(
        "- current regression dispositions: 241/241 correct"
    )

    print(
        "- source hashes: verified"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
