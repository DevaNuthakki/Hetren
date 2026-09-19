from __future__ import annotations

from collections import Counter
from pathlib import Path
import ast
import hashlib
import importlib.util
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

HISTORICAL = DATA_DIR / "historical_cases.json"
HISTORICAL_SCHEMA = DATA_DIR / "historical_cases.schema.json"
INVARIANTS = DATA_DIR / "invariants.json"
INVARIANTS_SCHEMA = DATA_DIR / "invariants.schema.json"

VALIDATOR = ROOT / "scripts/check_initial_splits.py"

SET_B = (
    ROOT
    / "tests"
    / "qualification"
    / "test_initial_splits_holdout_b.py"
)

SET_C = (
    ROOT
    / "tests"
    / "qualification"
    / "test_initial_splits_holdout_c.py"
)

EXPECTED_SUITE_COUNTS = {
    "CANONICAL": 52,
    "SET_A": 12,
    "SET_B": 12,
    "SET_C": 64,
}

EXPECTED_INVARIANT_COUNT = 44

EXPECTED_SET_C_INITIAL_REJECTED = {
    "C01.02",
    "C01.04",
    "C01.08",
    "C03.05",
    "C04.04",
    "C06.01",
    "C06.02",
    "C06.03",
    "C06.04",
    "C06.05",
    "C06.08",
    "C07.01",
    "C07.02",
    "C07.03",
    "C07.04",
    "C07.05",
    "C07.08",
}

SEMANTIC_HELPERS = {
    "forbid_semantic_patterns",
    "forbid_permissive_relationship",
    "forbid_permissive_paragraph_relationship",
    "forbid_concept_cooccurrence",
    "forbid_cross_document_composition",
}

C08_LABEL = "baseline-resource composition integrity"


def load_json(path: Path):
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_module(
    name: str,
    path: Path,
):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    if spec is None or spec.loader is None:
        raise AssertionError(
            f"cannot import {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return node.attr

    return None


def stable_slug(label: str) -> str:
    value = label.lower()

    for old, new in (
        ("a-h1", "ah1"),
        ("a-h2", "ah2"),
        ("n-h1", "nh1"),
        ("n-h2", "nh2"),
    ):
        value = value.replace(
            old,
            new,
        )

    value = re.sub(
        r"[^a-z0-9]+",
        ".",
        value,
    )

    value = value.strip(".")

    return re.sub(
        r"\.+",
        ".",
        value,
    )


def extract_live_invariants():
    source = VALIDATOR.read_text()

    tree = ast.parse(
        source,
        filename=str(VALIDATOR),
    )

    entries = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        helper = call_name(
            node.func
        )

        if helper not in SEMANTIC_HELPERS:
            continue

        if len(node.args) < 3:
            continue

        label_node = node.args[2]

        if not (
            isinstance(
                label_node,
                ast.Constant,
            )
            and isinstance(
                label_node.value,
                str,
            )
        ):
            continue

        label = label_node.value

        entries.append(
            {
                "invariant_id": (
                    "T7.INV."
                    + stable_slug(label)
                ),
                "label": label,
                "enforcement_kind": (
                    "SEMANTIC_HELPER"
                ),
                "helper": helper,
                "source_file": (
                    "scripts/check_initial_splits.py"
                ),
                "source_line": node.lineno,
                "status": "ACTIVE",
            }
        )

    c08_lines = [
        index
        for index, line in enumerate(
            source.splitlines(),
            start=1,
        )
        if C08_LABEL in line
    ]

    if len(c08_lines) != 1:
        raise AssertionError(
            "C08 invariant must occur exactly once "
            "in validator source"
        )

    entries.append(
        {
            "invariant_id": (
                "T7.INV."
                + stable_slug(C08_LABEL)
            ),
            "label": C08_LABEL,
            "enforcement_kind": (
                "DISTRIBUTED_COMPOSITION"
            ),
            "helper": None,
            "source_file": (
                "scripts/check_initial_splits.py"
            ),
            "source_line": c08_lines[0],
            "status": "ACTIVE",
        }
    )

    entries.sort(
        key=lambda item: (
            item["source_line"],
            item["label"],
        )
    )

    return entries


def validate_schemas(
    historical,
    invariants,
):
    historical_schema = load_json(
        HISTORICAL_SCHEMA
    )

    invariants_schema = load_json(
        INVARIANTS_SCHEMA
    )

    Draft202012Validator.check_schema(
        historical_schema
    )

    Draft202012Validator.check_schema(
        invariants_schema
    )

    Draft202012Validator(
        historical_schema
    ).validate(
        historical
    )

    Draft202012Validator(
        invariants_schema
    ).validate(
        invariants
    )


EXPECTED_CANONICAL_HISTORICAL_FILE_SHA256 = (
    "055d42d902c196ab6242126a9cad8f0483245d00d5af71c9a46ca66337b90a00"
)

EXPECTED_CANONICAL_HISTORICAL_SNAPSHOT_REF = (
    "docs/decisions/qualification/evidence/0008-post-set-d-data-boundary.sha256"
)

EXPECTED_CANONICAL_ATTACK_DEFINITION_SHA256 = (
    "f86429996ed383358f3bc30b0875db32b812bcfcb6c76f6692bc68ce0a9d9560"
)


def historical_manifest_entry(
    manifest_path: Path,
    relative_file: str,
) -> str:
    matches = []

    for line in manifest_path.read_text().splitlines():
        if not line.strip():
            continue

        digest, name = line.split(
            None,
            1,
        )

        if name.strip() == relative_file:
            matches.append(
                digest
            )

    assert len(
        matches
    ) == 1

    return matches[0]


def validate_historical_semantics(
    historical,
):
    cases = historical["cases"]

    assert historical[
        "historical_case_count"
    ] == 140

    assert len(cases) == 140

    suite_counts = Counter(
        item["suite"]
        for item in cases
    )

    assert dict(
        suite_counts
    ) == EXPECTED_SUITE_COUNTS

    case_ids = [
        item["case_id"]
        for item in cases
    ]

    assert len(case_ids) == len(
        set(case_ids)
    )

    expected_ids = {
        "CANONICAL": [
            f"T7-DEV-{number:03d}"
            for number in range(
                1,
                53,
            )
        ],
        "SET_A": [
            f"T7-A-{number:03d}"
            for number in range(
                1,
                13,
            )
        ],
        "SET_B": [
            f"T7-B-{number:03d}"
            for number in range(
                1,
                13,
            )
        ],
        "SET_C": [
            f"T7-C-{number:03d}"
            for number in range(
                1,
                65,
            )
        ],
    }

    for suite, ids in expected_ids.items():
        suite_cases = [
            item
            for item in cases
            if item["suite"] == suite
        ]

        assert [
            item["case_id"]
            for item in suite_cases
        ] == ids

        assert [
            item["ordinal"]
            for item in suite_cases
        ] == list(
            range(
                1,
                len(ids) + 1,
            )
        )

    assert all(
        item["expected"]
        == "MUST_REJECT"
        for item in cases
    )

    assert all(
        item["current_disposition"]
        == "REJECTED"
        for item in cases
    )

    canonical = [
        item
        for item in cases
        if item["suite"]
        == "CANONICAL"
    ]

    assert all(
        item["historical_unseen"]
        is False
        for item in canonical
    )

    assert all(
        item["first_run_disposition"]
        == "KNOWN_DEVELOPMENT_CASE"
        for item in canonical
    )

    for suite in (
        "SET_A",
        "SET_B",
    ):
        suite_cases = [
            item
            for item in cases
            if item["suite"] == suite
        ]

        assert all(
            item["historical_unseen"]
            is True
            for item in suite_cases
        )

        assert all(
            item["first_run_disposition"]
            == "SURVIVED"
            for item in suite_cases
        )

    set_c_cases = [
        item
        for item in cases
        if item["suite"] == "SET_C"
    ]

    assert all(
        item["historical_unseen"]
        is True
        for item in set_c_cases
    )

    generated_ids = [
        item["generated_case_id"]
        for item in set_c_cases
    ]

    expected_generated_ids = [
        f"C{family:02d}.{variant:02d}"
        for family in range(
            1,
            9,
        )
        for variant in range(
            1,
            9,
        )
    ]

    assert generated_ids == (
        expected_generated_ids
    )

    actual_initial_rejected = {
        item["generated_case_id"]
        for item in set_c_cases
        if item["first_run_disposition"]
        == "REJECTED"
    }

    assert actual_initial_rejected == (
        EXPECTED_SET_C_INITIAL_REJECTED
    )

    assert sum(
        item["first_run_disposition"]
        == "REJECTED"
        for item in set_c_cases
    ) == 17

    assert sum(
        item["first_run_disposition"]
        == "SURVIVED"
        for item in set_c_cases
    ) == 47

    canonical_source = historical[
        "sources"
    ][
        "canonical"
    ]

    canonical_path = (
        ROOT
        / canonical_source[
            "file"
        ]
    )

    assert canonical_path.is_file()

    assert canonical_source[
        "historical_file_sha256"
    ] == EXPECTED_CANONICAL_HISTORICAL_FILE_SHA256

    assert canonical_source[
        "historical_snapshot_ref"
    ] == EXPECTED_CANONICAL_HISTORICAL_SNAPSHOT_REF

    historical_manifest = (
        ROOT
        / canonical_source[
            "historical_snapshot_ref"
        ]
    )

    assert historical_manifest.is_file()

    assert historical_manifest_entry(
        historical_manifest,
        canonical_source[
            "file"
        ],
    ) == canonical_source[
        "historical_file_sha256"
    ]

    canonical = load_module(
        "task7_data_canonical",
        canonical_path,
    )

    assert canonical_source[
        "attack_definition_sha256"
    ] == EXPECTED_CANONICAL_ATTACK_DEFINITION_SHA256

    assert canonical_source[
        "attack_definition_sha256"
    ] == canonical.development_attack_definition_hash()

    for source_name in (
        "set_a",
        "set_b",
        "set_c",
    ):
        source = historical[
            "sources"
        ][
            source_name
        ]

        source_path = (
            ROOT
            / source[
                "file"
            ]
        )

        assert source_path.is_file()

        assert sha256_file(
            source_path
        ) == source[
            "file_sha256"
        ]

    set_b = load_module(
        "task7_data_set_b",
        SET_B,
    )

    set_c = load_module(
        "task7_data_set_c",
        SET_C,
    )

    assert historical[
        "sources"
    ][
        "set_b"
    ][
        "attack_definition_sha256"
    ] == set_b.attack_definition_hash()

    assert historical[
        "sources"
    ][
        "set_c"
    ][
        "attack_definition_sha256"
    ] == set_c.attack_definition_hash()


def validate_invariant_semantics(
    invariants,
):
    entries = invariants[
        "invariants"
    ]

    assert invariants[
        "invariant_count"
    ] == EXPECTED_INVARIANT_COUNT

    assert len(entries) == (
        EXPECTED_INVARIANT_COUNT
    )

    ids = [
        item["invariant_id"]
        for item in entries
    ]

    labels = [
        item["label"]
        for item in entries
    ]

    assert len(ids) == len(
        set(ids)
    )

    assert len(labels) == len(
        set(labels)
    )

    live_entries = (
        extract_live_invariants()
    )

    assert entries == live_entries

    distributed = [
        item
        for item in entries
        if item[
            "enforcement_kind"
        ] == "DISTRIBUTED_COMPOSITION"
    ]

    assert len(distributed) == 1

    assert distributed[0][
        "label"
    ] == C08_LABEL


def validate_all() -> None:
    historical = load_json(
        HISTORICAL
    )

    invariants = load_json(
        INVARIANTS
    )

    validate_schemas(
        historical,
        invariants,
    )

    validate_historical_semantics(
        historical
    )

    validate_invariant_semantics(
        invariants
    )


def main() -> int:
    try:
        validate_all()
    except Exception as exc:
        print(
            "INITIAL SPLITS DATA VALIDATION: FAIL"
        )
        print(
            f"- {type(exc).__name__}: {exc}"
        )
        return 1

    print(
        "INITIAL SPLITS DATA VALIDATION: PASS"
    )
    print(
        "- historical adversarial cases: 140"
    )
    print(
        "- canonical: 52"
    )
    print(
        "- Set A: 12"
    )
    print(
        "- Set B: 12"
    )
    print(
        "- Set C: 64"
    )
    print(
        "- Set C original unseen: "
        "17 rejected / 47 survived"
    )
    print(
        "- active explicit invariants: 44"
    )
    print(
        "- schemas: Draft 2020-12"
    )
    print(
        "- source hashes: verified"
    )
    print(
        "- Set B/C attack hashes: verified"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
