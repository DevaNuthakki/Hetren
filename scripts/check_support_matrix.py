#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


SPEC_RELATIVE = Path("docs/mvp/05-support-matrix.md")
DECISION_RELATIVE = Path(
    "docs/decisions/0005-mvp-support-matrix.md"
)
REGISTER_RELATIVE = Path("docs/decisions/register.md")
QUALIFICATION_RELATIVE = Path(
    "docs/decisions/qualification/0005-mvp-support-matrix.md"
)

EXPECTED_SPEC_METADATA = {
    "MVP Task": "5 / 100",
    "Execution authority": "AUTH-HETREN-MVP-3.0",
    "Long-term authority": "AUTH-HETREN-MASTER-2.0",
    "Governing decision": "0005",
    "Canonical capability record": "CapabilityProfile",
    "Governing taxonomy": "docs/mvp/04-system-taxonomy.md",
    "Governing success semantics": "docs/mvp/03-success-contracts.md",
}

EXPECTED_DECISION_METADATA = {
    "Decision ID": "0005",
    "Decision Key": "product.mvp-support-matrix",
    "Title": "Freeze the initial MVP capability-support matrix",
    "Class": "PRODUCT",
    "Authority": "AUTH-HETREN-MVP-3.0",
    "Research Program": "NONE",
    "Research Change Category": "NONE",
    "Evidence Consequence": "NONE",
    "Supersedes": "None",
    "Superseded By": "None",
    "Reversibility": "CONDITIONALLY_REVERSIBLE",
    "Qualification": "Task 5 support-matrix qualification",
}

EXPECTED_MUTATIONS = 46


ALLOWED_SPEC_STATUSES = {
    "Draft",
    "Requalifying",
    "Qualified",
}

ALLOWED_DECISION_STATUSES = {
    "PROPOSED",
    "ACCEPTED",
}

SECTION_TITLES = (
    "Purpose",
    "Authority And Scope",
    "Representability, Support, Authorization, And Outcome",
    "CapabilityKind",
    "MVPRequirement",
    "CapabilitySupportState",
    "Separation Rules",
    "Support Declaration Scope",
    "Cross-Domain Behavioral Product Matrix",
    "Behavioral Matrix Qualification Semantics",
    "Behavioral Engine Minimum Closed Loop",
    "Internal Engine Qualification Overlay",
    "Internal Binding Qualification Requirements",
    "Internal Authorization Boundary",
    "Combined Behavioral And Internal Qualification",
    "Why Internal Support Is Not A Full Cartesian Matrix",
    "CapabilityProfile Mapping",
    "Initial State Freeze",
    "Matrix-Cell Semantics",
    "Compatibility Semantics",
    "Qualification Evidence For QUALIFIED_SUPPORTED",
    "Promotion Rules",
    "Failure Does Not Automatically Mean Unsupported",
    "Capability-State Transition Governance",
    "Requirement-State Governance",
    "Negative And Uncertain Capability States",
    "Invalidation And Requalification",
    "Tenant, Identity, And Provenance Isolation",
    "Static MVP Matrix And Current Capability State",
    "Task 5 Completion Versus MVP Capability Completion",
    "Task 6 Through Task 9 Boundaries",
    "Governed Extension",
    "Task 5 Qualification Contract",
    "Support-Matrix Principle",
)

CAPABILITY_KINDS = (
    "REGRESSION_REPAIR",
    "CONSTRAINED_IMPROVEMENT",
)

MVP_REQUIREMENTS = (
    "REQUIRED",
    "PERMITTED",
    "EXCLUDED",
)

CAPABILITY_SUPPORT_STATES = (
    "QUALIFIED_SUPPORTED",
    "UNQUALIFIED",
    "UNSUPPORTED",
    "INCOMPATIBLE",
    "BLOCKED",
    "UNKNOWN",
)

TASK3_OUTCOMES = (
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
    "BLOCKED",
    "INVALID",
)

ENVIRONMENT_FAMILIES = (
    "E1_AGENT",
    "E2_STRUCTURED_ML",
    "E3_VISION",
)

INVESTIGATION_SURFACES = (
    "BEHAVIORAL",
    "AUTHORIZED_INTERNAL",
)

EXPECTED_BEHAVIORAL_CELLS = (
    (
        "E1_AGENT",
        "REGRESSION_REPAIR",
        "BEHAVIORAL",
        "REQUIRED",
        "UNQUALIFIED",
    ),
    (
        "E1_AGENT",
        "CONSTRAINED_IMPROVEMENT",
        "BEHAVIORAL",
        "REQUIRED",
        "UNQUALIFIED",
    ),
    (
        "E2_STRUCTURED_ML",
        "REGRESSION_REPAIR",
        "BEHAVIORAL",
        "REQUIRED",
        "UNQUALIFIED",
    ),
    (
        "E2_STRUCTURED_ML",
        "CONSTRAINED_IMPROVEMENT",
        "BEHAVIORAL",
        "REQUIRED",
        "UNQUALIFIED",
    ),
    (
        "E3_VISION",
        "REGRESSION_REPAIR",
        "BEHAVIORAL",
        "REQUIRED",
        "UNQUALIFIED",
    ),
    (
        "E3_VISION",
        "CONSTRAINED_IMPROVEMENT",
        "BEHAVIORAL",
        "REQUIRED",
        "UNQUALIFIED",
    ),
)

EXPECTED_INTERNAL_OBLIGATIONS = (
    (
        "small open CNN-family system binding",
        "AUTHORIZED_INTERNAL",
        "REQUIRED",
        "UNQUALIFIED",
    ),
    (
        "small open Transformer-family system binding",
        "AUTHORIZED_INTERNAL",
        "REQUIRED",
        "UNQUALIFIED",
    ),
)

EXPECTED_COMBINED_OBLIGATION = (
    "Behavioral and authorized Internal evidence used within "
    "the same governed investigation and decision path",
    "REQUIRED",
    "UNQUALIFIED",
)

QUALIFICATION_SECTIONS = (
    "Scope",
    "Positive Qualification",
    "Structural Qualification",
    "Semantic Qualification",
    "Adversarial Qualification",
    "Authority And Regression Qualification",
    "Limitations",
    "Acceptance Decision",
)


EXPECTED_QUALIFICATION_METADATA = {
    "Task": "5 / 100",
    "Decision": "0005",
    "Decision Key": "product.mvp-support-matrix",
    "Result": "PASS",
    "Qualification state": "VERIFIED",
    "Specification": "docs/mvp/05-support-matrix.md",
    "Validator": "scripts/check_support_matrix.py",
    "Mutation suite": "tests/qualification/test_support_matrix.py",
    "Qualification conditions": "50 / 50",
    "Execution authority": "AUTH-HETREN-MVP-3.0",
    "Long-term authority": "AUTH-HETREN-MASTER-2.0",
    "Task 1 regression": "PASS",
    "Task 2 regression": "PASS",
    "Task 3 regression": "PASS",
    "Task 4 regression": "PASS",
    "Diff check": "PASS",
    "Final accepted-state qualification": "PASS",
}


def strip_code(value: str) -> str:
    value = value.strip()

    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]

    return value


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def semantic_text(text: str) -> str:
    return normalize(text).replace("`", "").casefold()


def parse_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    pattern = re.compile(
        r"^\*\*(?P<key>[^*]+):\*\*\s*(?P<value>.+)$",
        re.MULTILINE,
    )

    for match in pattern.finditer(text):
        metadata[match.group("key").strip()] = strip_code(
            match.group("value")
        )

    return metadata


def numbered_sections(
    text: str,
) -> list[tuple[int, str]]:
    return [
        (int(number), title.strip())
        for number, title in re.findall(
            r"^## ([0-9]+)\. (.+)$",
            text,
            re.MULTILINE,
        )
    ]


def section_body(
    text: str,
    number: int,
    title: str,
) -> str:
    marker = f"## {number}. {title}"

    if marker not in text:
        return ""

    body = text.split(marker, 1)[1]
    body = body.split("\n## ", 1)[0]

    return body.strip()


def numbered_conditions(text: str) -> list[int]:
    return [
        int(value)
        for value in re.findall(
            r"^([0-9]+)\.\s+",
            text,
            re.MULTILINE,
        )
    ]


def parse_condition_bodies(
    text: str,
) -> dict[int, str]:
    conditions: dict[int, str] = {}

    matches = list(
        re.finditer(
            r"(?m)^([0-9]+)\.\s+",
            text,
        )
    )

    for index, match in enumerate(matches):
        number = int(match.group(1))
        start = match.end()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        conditions[number] = text[start:end].strip()

    return conditions


def parse_register_0005(
    text: str,
) -> dict[str, str] | None:
    pattern = re.compile(
        r"^\| `0005` "
        r"\| `(?P<key>[^`]+)` "
        r"\| (?P<title>[^|]+?) "
        r"\| `(?P<status>[^`]+)` "
        r"\| `(?P<class>[^`]+)` "
        r"\| `(?P<authority>[^`]+)` "
        r"\| `(?P<record>[^`]+)` \|$",
        re.MULTILINE,
    )

    match = pattern.search(text)

    if match is None:
        return None

    return {
        key: value.strip()
        for key, value in match.groupdict().items()
    }



def unnumbered_section_body(
    text: str,
    heading: str,
) -> str:
    marker = f"## {heading}"

    if marker not in text:
        return ""

    body = text.split(marker, 1)[1]
    body = body.split("\n## ", 1)[0]

    return body.strip()


def require_semantics(
    errors: list[str],
    body: str,
    label: str,
    fragments: tuple[str, ...],
) -> None:
    normalized = semantic_text(body)

    for fragment in fragments:
        if semantic_text(fragment) not in normalized:
            errors.append(
                f"{label} missing required semantic fragment: "
                f"{fragment}"
            )


EXPECTED_DECISION_DATE = "2026-09-17"

EXPECTED_DECISION_SCOPE = (
    "Task 5 initial MVP capability requirements, support states, "
    "Behavioral matrix, Internal qualification overlay, and "
    "CapabilityProfile support semantics"
)


def validate_structure(
    root: Path,
    require_qualified: bool = False,
) -> list[str]:
    errors: list[str] = []

    spec_path = root / SPEC_RELATIVE
    decision_path = root / DECISION_RELATIVE
    register_path = root / REGISTER_RELATIVE
    qualification_path = root / QUALIFICATION_RELATIVE

    for required_file, label in (
        (spec_path, str(SPEC_RELATIVE)),
        (decision_path, str(DECISION_RELATIVE)),
        (register_path, str(REGISTER_RELATIVE)),
    ):
        if not required_file.is_file():
            errors.append(f"missing {label}")

    if errors:
        return errors

    spec_text = spec_path.read_text()
    decision_text = decision_path.read_text()
    register_text = register_path.read_text()

    # ---------------------------------------------------------
    # Specification identity and metadata
    # ---------------------------------------------------------

    if not spec_text.startswith(
        "# Hetren MVP Support Matrix\n"
    ):
        errors.append(
            "support-matrix specification heading mismatch"
        )

    spec_metadata = parse_metadata(spec_text)

    for key, expected in EXPECTED_SPEC_METADATA.items():
        actual = spec_metadata.get(key)

        if actual != expected:
            errors.append(
                f"Task 5 specification metadata {key} "
                f"must be {expected!r}, got {actual!r}"
            )

    spec_status = spec_metadata.get("Status")
    spec_version = spec_metadata.get("Version")

    if spec_status not in ALLOWED_SPEC_STATUSES:
        errors.append(
            "Task 5 specification status must be "
            "Draft, Requalifying, or Qualified"
        )

    if spec_status == "Draft":
        if spec_version != "0.1.0":
            errors.append(
                "Task 5 Draft specification version "
                "must be 0.1.0"
            )

    elif spec_status == "Requalifying":
        if spec_version != "1.0.0":
            errors.append(
                "Task 5 Requalifying specification version "
                "must be 1.0.0"
            )

    elif spec_status == "Qualified":
        if spec_version != "1.0.0":
            errors.append(
                "Task 5 Qualified specification version "
                "must be 1.0.0"
            )

    # ---------------------------------------------------------
    # Exact section topology
    # ---------------------------------------------------------

    actual_sections = numbered_sections(spec_text)

    expected_sections = [
        (index, title)
        for index, title in enumerate(
            SECTION_TITLES,
            start=1,
        )
    ]

    if actual_sections != expected_sections:
        errors.append(
            "Task 5 specification must contain exactly "
            "34 numbered sections in the governed order"
        )

    # ---------------------------------------------------------
    # Exact qualification-condition topology
    # ---------------------------------------------------------

    qualification_body = section_body(
        spec_text,
        33,
        "Task 5 Qualification Contract",
    )

    conditions = numbered_conditions(
        qualification_body
    )

    if conditions != list(range(1, 51)):
        errors.append(
            "Task 5 qualification contract must contain "
            "exactly conditions 1 through 50 in order"
        )

    condition_bodies = parse_condition_bodies(
        qualification_body
    )

    if set(condition_bodies) != set(range(1, 51)):
        errors.append(
            "Task 5 qualification condition bodies must "
            "map exactly to conditions 1 through 50"
        )

    # ---------------------------------------------------------
    # Decision 0005 identity and metadata
    # ---------------------------------------------------------

    if not decision_text.startswith(
        "# Decision 0005: "
        "Freeze the initial MVP capability-support matrix\n"
    ):
        errors.append(
            "Decision 0005 heading mismatch"
        )

    decision_metadata = parse_metadata(
        decision_text
    )

    for key, expected in (
        EXPECTED_DECISION_METADATA.items()
    ):
        actual = decision_metadata.get(key)

        if actual != expected:
            errors.append(
                f"Decision 0005 metadata {key} "
                f"must be {expected!r}, got {actual!r}"
            )

    decision_scope = decision_metadata.get("Scope")

    if decision_scope != EXPECTED_DECISION_SCOPE:
        errors.append(
            "Decision 0005 Scope metadata mismatch"
        )

    decision_date = decision_metadata.get("Date")

    if decision_date != EXPECTED_DECISION_DATE:
        errors.append(
            "Decision 0005 Date metadata mismatch"
        )

    if decision_date:
        try:
            date.fromisoformat(decision_date)
        except ValueError:
            errors.append(
                "Decision 0005 Date must be a valid "
                "ISO calendar date"
            )

    decision_status = decision_metadata.get(
        "Status"
    )

    if (
        decision_status
        not in ALLOWED_DECISION_STATUSES
    ):
        errors.append(
            "Decision 0005 status must be "
            "PROPOSED or ACCEPTED"
        )

    # ---------------------------------------------------------
    # Decision-register synchronization
    # ---------------------------------------------------------

    register_entry = parse_register_0005(
        register_text
    )

    if register_entry is None:
        errors.append(
            "Decision register is missing Decision 0005"
        )
        register_status = None
    else:
        expected_register_fields = {
            "key": "product.mvp-support-matrix",
            "title": (
                "Freeze the initial MVP "
                "capability-support matrix"
            ),
            "class": "PRODUCT",
            "authority": "AUTH-HETREN-MVP-3.0",
            "record": "0005-mvp-support-matrix.md",
        }

        for key, expected in (
            expected_register_fields.items()
        ):
            actual = register_entry.get(key)

            if actual != expected:
                errors.append(
                    "Decision 0005 register field "
                    f"{key} must be {expected!r}, "
                    f"got {actual!r}"
                )

        register_status = register_entry.get(
            "status"
        )

        if (
            register_status
            not in ALLOWED_DECISION_STATUSES
        ):
            errors.append(
                "Decision 0005 register status must be "
                "PROPOSED or ACCEPTED"
            )

        if register_status != decision_status:
            errors.append(
                "Decision 0005 decision/register "
                "status mismatch"
            )

    # ---------------------------------------------------------
    # Development-state lifecycle
    # ---------------------------------------------------------

    if spec_status in {
        "Draft",
        "Requalifying",
    }:
        if decision_status != "PROPOSED":
            errors.append(
                "Task 5 development state requires "
                "Decision 0005 PROPOSED"
            )

        if register_status != "PROPOSED":
            errors.append(
                "Task 5 development state requires "
                "Decision 0005 register status PROPOSED"
            )

    # ---------------------------------------------------------
    # Accepted-state lifecycle
    # ---------------------------------------------------------

    if spec_status == "Qualified":
        if decision_status != "ACCEPTED":
            errors.append(
                "Qualified Task 5 specification requires "
                "Decision 0005 ACCEPTED"
            )

        if register_status != "ACCEPTED":
            errors.append(
                "Qualified Task 5 specification requires "
                "Decision 0005 register status ACCEPTED"
            )

    if decision_status == "ACCEPTED":
        if spec_status != "Qualified":
            errors.append(
                "Decision 0005 cannot be ACCEPTED while "
                "the Task 5 specification is not Qualified"
            )

    # ---------------------------------------------------------
    # Final qualification gate
    # ---------------------------------------------------------

    if require_qualified:
        if spec_version != "1.0.0":
            errors.append(
                "final qualification requires "
                "Task 5 specification version 1.0.0"
            )

        if spec_status != "Qualified":
            errors.append(
                "final qualification requires "
                "Task 5 specification status Qualified"
            )

        if decision_status != "ACCEPTED":
            errors.append(
                "final qualification requires "
                "Decision 0005 ACCEPTED"
            )

        if register_status != "ACCEPTED":
            errors.append(
                "final qualification requires "
                "Decision 0005 register status ACCEPTED"
            )

    final_state_requested = (
        require_qualified
        or spec_status == "Qualified"
        or decision_status == "ACCEPTED"
        or register_status == "ACCEPTED"
    )

    if final_state_requested:
        if not qualification_path.is_file():
            errors.append(
                "missing Decision 0005 qualification evidence"
            )
        else:
            errors.extend(
                validate_qualification_record(
                    qualification_path,
                    expected_spec_version=spec_version,
                )
            )

    return errors



CONDITION_REQUIREMENTS = {
    1: (
        "AUTH-HETREN-MVP-3.0",
        "execution authority",
    ),
    2: (
        "AUTH-HETREN-MASTER-2.0",
        "long-term authority",
    ),
    3: (
        "CapabilityProfile",
        "canonical capability record",
    ),
    4: (
        "Task 3",
        "governing success-semantic authority",
    ),
    5: (
        "Task 4",
        "governing taxonomy authority",
    ),
    6: (
        "CapabilityKind",
        "REGRESSION_REPAIR",
        "CONSTRAINED_IMPROVEMENT",
    ),
    7: (
        "MVPRequirement",
        "REQUIRED",
        "PERMITTED",
        "EXCLUDED",
    ),
    8: (
        "CapabilitySupportState",
        "QUALIFIED_SUPPORTED",
        "UNQUALIFIED",
        "UNSUPPORTED",
        "INCOMPATIBLE",
        "BLOCKED",
        "UNKNOWN",
    ),
    9: (
        "Task 3 evaluation outcomes",
        "PASS",
        "FAIL",
        "INCONCLUSIVE",
        "BLOCKED",
        "INVALID",
    ),
    10: (
        "capability support states",
        "not treated as Task 3 evaluation outcomes",
    ),
    11: (
        "taxonomy representability",
        "does not establish support",
    ),
    12: (
        "execution authorization",
        "does not establish support",
    ),
    13: (
        "qualified support",
        "does not itself grant execution authorization",
    ),
    14: (
        "MVP requirement",
        "does not establish qualified support",
    ),
    15: (
        "Behavioral product matrix",
        "exactly six required initial cells",
    ),
    16: (
        "E1_AGENT",
        "both required capability kinds",
    ),
    17: (
        "E2_STRUCTURED_ML",
        "both required capability kinds",
    ),
    18: (
        "E3_VISION",
        "both required capability kinds",
    ),
    19: (
        "all six initial product cells",
        "BEHAVIORAL",
    ),
    20: (
        "all six initial product cells",
        "REQUIRED + UNQUALIFIED",
    ),
    21: (
        "no additional mandatory Behavioral matrix cell",
        "silently introduced",
    ),
    22: (
        "small open CNN-family binding",
    ),
    23: (
        "small open Transformer-family binding",
    ),
    24: (
        "both required Internal bindings",
        "REQUIRED + UNQUALIFIED",
    ),
    25: (
        "activation capture",
    ),
    26: (
        "representation or component diagnostics",
    ),
    27: (
        "reversible intervention or ablation",
    ),
    28: (
        "pre/post behavior comparison",
    ),
    29: (
        "verification of intervention effect",
    ),
    30: (
        "Internal support",
        "not expanded into a mandatory E1/E2/E3 Cartesian product",
    ),
    31: (
        "combined Behavioral/Internal obligation exists",
    ),
    32: (
        "combined obligation",
        "REQUIRED + UNQUALIFIED",
    ),
    33: (
        "both evidence classes",
        "same governed investigation and decision path",
    ),
    34: (
        "correlation alone",
        "cannot establish a material causal Internal claim",
    ),
    35: (
        "CapabilityProfile",
        "governed support scope and state",
    ),
    36: (
        "support claims",
        "cannot exceed the scope justified by their evidence",
    ),
    37: (
        "promotion to QUALIFIED_SUPPORTED",
        "preserved qualification evidence",
    ),
    38: (
        "one successful execution",
        "cannot synthesize qualified support",
    ),
    39: (
        "one failed evaluation",
        "does not automatically establish UNSUPPORTED",
    ),
    40: (
        "capability-state transitions",
        "preserve historical state and transition evidence",
    ),
    41: (
        "invalidated qualified support",
        "cannot silently remain authoritative",
    ),
    42: (
        "UNSUPPORTED",
        "INCOMPATIBLE",
        "BLOCKED",
        "UNKNOWN",
        "UNQUALIFIED",
        "semantically distinct",
    ),
    43: (
        "provider, adapter, evaluator, or system-form similarity",
        "cannot silently broaden qualified support",
    ),
    44: (
        "qualification of one matrix row",
        "does not establish universal support",
    ),
    45: (
        "Task 5 completion",
        "nine mandatory capability obligations",
        "MVP is complete",
    ),
    46: (
        "Task 6 research hypotheses remain deferred",
    ),
    47: (
        "Task 7 concrete split identities remain deferred",
    ),
    48: (
        "Task 8 concrete baseline implementations remain deferred",
    ),
    49: (
        "Task 9 concrete cost and effort values remain deferred",
    ),
    50: (
        "material support-model changes",
        "governed revision",
        "requalification",
    ),
}


FORBIDDEN_SECTION_SEMANTICS = {
    3: (
        "representability establishes capability support",
        "support grants authorization",
        "authorization establishes support",
    ),
    5: (
        "required means qualified supported",
        "excluded means architecturally impossible",
    ),
    6: (
        "unqualified means fail",
        "unsupported means fail",
        "unknown means unqualified",
        "incompatible means unsupported",
    ),
    7: (
        "representable means supported",
        "authorized means supported",
        "required means qualified",
    ),
    12: (
        "every e1, e2, or e3 target requires internal access",
    ),
    14: (
        "authorized_internal grants permission",
        "internal support declaration may bypass authorization",
    ),
    16: (
        "internal support requires all six additional cells",
    ),
    17: (
        "successful discovery implies qualified_supported",
        "one successful execution implies qualified_supported",
    ),
    19: (
        "qualified_supported means hetren supports every possible system",
    ),
    22: (
        "one successful execution is sufficient to promote a capability",
        "mvp requirement is sufficient to promote a capability",
    ),
    23: (
        "a failed evaluation automatically converts the capability to unsupported",
    ),
    24: (
        "a later state erases the earlier state",
    ),
    26: (
        "absence of evidence for support automatically means unsupported",
    ),
    28: (
        "evidence from one tenant silently qualifies another tenant",
    ),
    30: (
        "task 5 completion means all nine obligations are qualified_supported",
        "task 5 completion means the mvp is complete",
    ),
    31: (
        "task 5 owns concrete research hypotheses",
        "task 5 owns concrete split identities",
        "task 5 owns concrete baseline implementations",
        "task 5 owns concrete cost values",
    ),
}


def extract_code_bullet_block(
    body: str,
    intro: str,
) -> tuple[str, ...]:
    intro_pattern = re.escape(intro).replace(
        r"\ ",
        r"\s+",
    )

    match = re.search(
        intro_pattern,
        body,
        re.MULTILINE,
    )

    if match is None:
        return ()

    tail = body[match.end():]
    values: list[str] = []
    started = False

    for raw_line in tail.splitlines():
        line = raw_line.strip()

        bullet_match = re.fullmatch(
            r"- `([^`]+)`[.;]?",
            line,
        )

        if bullet_match:
            values.append(
                bullet_match.group(1)
            )
            started = True
            continue

        if started and line:
            break

    return tuple(values)

def parse_behavioral_cells(
    body: str,
) -> tuple[tuple[str, str, str, str, str], ...]:
    rows = re.findall(
        r"(?m)^\| `(E[123]_[A-Z_]+)` "
        r"\| `(REGRESSION_REPAIR|CONSTRAINED_IMPROVEMENT)` "
        r"\| `(BEHAVIORAL|AUTHORIZED_INTERNAL)` "
        r"\| `(REQUIRED|PERMITTED|EXCLUDED)` "
        r"\| `(QUALIFIED_SUPPORTED|UNQUALIFIED|UNSUPPORTED|"
        r"INCOMPATIBLE|BLOCKED|UNKNOWN)` \|$",
        body,
    )

    return tuple(rows)


def parse_internal_obligations(
    body: str,
) -> tuple[tuple[str, str, str, str], ...]:
    rows = re.findall(
        r"(?m)^\| "
        r"(small open (?:CNN|Transformer)-family system binding) "
        r"\| `(BEHAVIORAL|AUTHORIZED_INTERNAL)` "
        r"\| `(REQUIRED|PERMITTED|EXCLUDED)` "
        r"\| `(QUALIFIED_SUPPORTED|UNQUALIFIED|UNSUPPORTED|"
        r"INCOMPATIBLE|BLOCKED|UNKNOWN)` \|$",
        body,
    )

    return tuple(rows)


def validate_condition_semantics(
    qualification_body: str,
) -> list[str]:
    errors: list[str] = []

    bodies = parse_condition_bodies(
        qualification_body
    )

    for number in range(1, 51):
        body = bodies.get(number, "")

        if not body:
            errors.append(
                f"Task 5 qualification condition "
                f"{number} missing body"
            )
            continue

        normalized = semantic_text(body)

        for fragment in CONDITION_REQUIREMENTS[number]:
            if semantic_text(fragment) not in normalized:
                errors.append(
                    f"Task 5 qualification condition "
                    f"{number} missing semantic requirement: "
                    f"{fragment}"
                )

    return errors


def validate_semantics(
    root: Path,
) -> list[str]:
    errors: list[str] = []

    spec_path = root / SPEC_RELATIVE
    decision_path = root / DECISION_RELATIVE

    if (
        not spec_path.is_file()
        or not decision_path.is_file()
    ):
        return errors

    spec_text = spec_path.read_text()
    decision_text = decision_path.read_text()

    # ---------------------------------------------------------
    # Exact owned vocabularies
    # ---------------------------------------------------------

    capability_body = section_body(
        spec_text,
        4,
        "CapabilityKind",
    )

    capability_values = extract_code_bullet_block(
        capability_body,
        "The initial Task 5 product capability vocabulary is exactly:",
    )

    if capability_values != CAPABILITY_KINDS:
        errors.append(
            "Task 5 CapabilityKind vocabulary must be "
            "exactly REGRESSION_REPAIR and "
            "CONSTRAINED_IMPROVEMENT"
        )

    requirement_body = section_body(
        spec_text,
        5,
        "MVPRequirement",
    )

    requirement_values = extract_code_bullet_block(
        requirement_body,
        "Every governed Task 5 capability declaration carries "
        "exactly one MVP requirement state:",
    )

    if requirement_values != MVP_REQUIREMENTS:
        errors.append(
            "Task 5 MVPRequirement vocabulary must be "
            "exactly REQUIRED, PERMITTED, and EXCLUDED"
        )

    support_body = section_body(
        spec_text,
        6,
        "CapabilitySupportState",
    )

    support_values = extract_code_bullet_block(
        support_body,
        "The initial Task 5 capability-support vocabulary is exactly:",
    )

    if support_values != CAPABILITY_SUPPORT_STATES:
        errors.append(
            "Task 5 CapabilitySupportState vocabulary "
            "must be exactly QUALIFIED_SUPPORTED, "
            "UNQUALIFIED, UNSUPPORTED, INCOMPATIBLE, "
            "BLOCKED, and UNKNOWN"
        )

    outcome_body = section_body(
        spec_text,
        3,
        "Representability, Support, Authorization, And Outcome",
    )

    outcome_values = extract_code_bullet_block(
        outcome_body,
        "The Task 3 outcome vocabulary remains exactly:",
    )

    if outcome_values != TASK3_OUTCOMES:
        errors.append(
            "Task 5 must preserve the exact Task 3 "
            "evaluation outcome vocabulary"
        )

    # ---------------------------------------------------------
    # Exact six-cell Behavioral matrix
    # ---------------------------------------------------------

    behavioral_body = section_body(
        spec_text,
        9,
        "Cross-Domain Behavioral Product Matrix",
    )

    behavioral_cells = parse_behavioral_cells(
        behavioral_body
    )

    if behavioral_cells != EXPECTED_BEHAVIORAL_CELLS:
        errors.append(
            "Task 5 Behavioral product matrix must contain "
            "exactly the six governed REQUIRED + UNQUALIFIED "
            "BEHAVIORAL cells"
        )

    if len(behavioral_cells) != 6:
        errors.append(
            "Task 5 Behavioral product matrix must contain "
            "exactly six data rows"
        )

    # ---------------------------------------------------------
    # Exact Internal overlay
    # ---------------------------------------------------------

    internal_body = section_body(
        spec_text,
        12,
        "Internal Engine Qualification Overlay",
    )

    internal_rows = parse_internal_obligations(
        internal_body
    )

    if internal_rows != EXPECTED_INTERNAL_OBLIGATIONS:
        errors.append(
            "Task 5 Internal overlay must contain exactly "
            "the required CNN-family and Transformer-family "
            "AUTHORIZED_INTERNAL obligations"
        )

    # ---------------------------------------------------------
    # Exact combined-engine obligation
    # ---------------------------------------------------------

    combined_body = section_body(
        spec_text,
        15,
        "Combined Behavioral And Internal Qualification",
    )

    expected_combined = normalize(
        "| Behavioral and authorized Internal evidence used "
        "within the same governed investigation and decision path "
        "| `REQUIRED` | `UNQUALIFIED` |"
    )

    if expected_combined not in normalize(
        combined_body
    ):
        errors.append(
            "Task 5 combined Behavioral/Internal obligation "
            "must remain REQUIRED + UNQUALIFIED"
        )

    # ---------------------------------------------------------
    # Exactly nine initial mandatory obligations
    # ---------------------------------------------------------

    governed_initial = "\n".join(
        (
            behavioral_body,
            internal_body,
            combined_body,
        )
    )

    initial_required_unqualified = len(
        re.findall(
            r"\| `REQUIRED` \| `UNQUALIFIED` \|",
            governed_initial,
        )
    )

    if initial_required_unqualified != 9:
        errors.append(
            "Task 5 must contain exactly nine initial "
            "REQUIRED + UNQUALIFIED obligations"
        )

    manufactured_supported = re.findall(
        r"(?m)^\|.*\| `QUALIFIED_SUPPORTED` \|$",
        governed_initial,
    )

    if manufactured_supported:
        errors.append(
            "Task 5 initial obligation tables must contain "
            "zero QUALIFIED_SUPPORTED rows"
        )

    # ---------------------------------------------------------
    # Behavioral closed-loop contract
    # ---------------------------------------------------------

    behavioral_engine_body = section_body(
        spec_text,
        11,
        "Behavioral Engine Minimum Closed Loop",
    )

    require_semantics(
        errors,
        behavioral_engine_body,
        "Task 5 Behavioral Engine closed loop",
        (
            "inspect available capabilities",
            "propose informative tests or experiments",
            "execute or request execution",
            "observe outcomes",
            "update hypotheses",
            "identify evidence gaps",
            "revise the investigation method",
            "bound a failure or improvement region",
            "recommend the next useful action",
            "shared planner and Core behavior",
        ),
    )

    # ---------------------------------------------------------
    # Internal qualification contract
    # ---------------------------------------------------------

    internal_requirements_body = section_body(
        spec_text,
        13,
        "Internal Binding Qualification Requirements",
    )

    require_semantics(
        errors,
        internal_requirements_body,
        "Task 5 Internal binding qualification",
        (
            "activation capture",
            "representation or component diagnostics",
            "at least one reversible intervention or ablation",
            "comparison of pre-intervention and post-intervention behavior",
            "verification of the intervention effect",
            "passive visualization alone",
        ),
    )

    authorization_body = section_body(
        spec_text,
        14,
        "Internal Authorization Boundary",
    )

    require_semantics(
        errors,
        authorization_body,
        "Task 5 Internal authorization boundary",
        (
            "`AUTHORIZED_INTERNAL` records an investigation surface",
            "It does not grant permission",
            "Every Internal execution must still satisfy applicable "
            "execution-time permission",
            "No Internal support declaration may be used to bypass "
            "authorization",
        ),
    )

    require_semantics(
        errors,
        combined_body,
        "Task 5 combined-engine obligation",
        (
            "`BEHAVIORAL`",
            "`AUTHORIZED_INTERNAL`",
            "same investigation and decision path",
            "Neither engine may establish causal understanding "
            "from correlation alone",
        ),
    )

    # ---------------------------------------------------------
    # CapabilityProfile and qualification evidence
    # ---------------------------------------------------------

    profile_body = section_body(
        spec_text,
        17,
        "CapabilityProfile Mapping",
    )

    require_semantics(
        errors,
        profile_body,
        "Task 5 CapabilityProfile mapping",
        (
            "`CapabilityProfile` remains the canonical runtime "
            "and persisted capability record",
            "`EnvironmentFamily`",
            "`CapabilityKind`",
            "`InvestigationSurface`",
            "`MVPRequirement`",
            "`CapabilitySupportState`",
            "qualification-evidence references",
            "known limitations",
            "invalidation or requalification conditions",
            "must not infer `QUALIFIED_SUPPORTED` from successful discovery",
            "must not infer `QUALIFIED_SUPPORTED` from one successful execution",
        ),
    )

    evidence_body = section_body(
        spec_text,
        21,
        "Qualification Evidence For QUALIFIED_SUPPORTED",
    )

    require_semantics(
        errors,
        evidence_body,
        "Task 5 QUALIFIED_SUPPORTED evidence",
        (
            "Promotion to `QUALIFIED_SUPPORTED` requires preserved "
            "governed qualification evidence",
            "immutable target `SystemVersion`",
            "adapter identity and binding",
            "evaluator identity and binding",
            "the governing `GoalContract`",
            "execution records",
            "evaluation records",
            "verification evidence",
            "qualification limitations",
            "known unsupported boundaries",
            "invalidation conditions",
        ),
    )

    promotion_body = section_body(
        spec_text,
        22,
        "Promotion Rules",
    )

    require_semantics(
        errors,
        promotion_body,
        "Task 5 promotion rules",
        (
            "`QUALIFIED_SUPPORTED` must be earned",
            "taxonomy classification",
            "execution authorization",
            "one successful execution",
            "requirement by the MVP",
            "Evidence about one capability kind must not silently qualify "
            "the other",
            "Evidence about one environment family must not silently "
            "qualify another",
        ),
    )

    # ---------------------------------------------------------
    # Failure, history, invalidation, and negative states
    # ---------------------------------------------------------

    failure_body = section_body(
        spec_text,
        23,
        "Failure Does Not Automatically Mean Unsupported",
    )

    require_semantics(
        errors,
        failure_body,
        "Task 5 failure/support separation",
        (
            "A failed governed evaluation remains a Task 3 `FAIL`",
            "It does not automatically convert the applicable capability "
            "to `UNSUPPORTED`",
            "The transition must be explicit",
        ),
    )

    transition_body = section_body(
        spec_text,
        24,
        "Capability-State Transition Governance",
    )

    require_semantics(
        errors,
        transition_body,
        "Task 5 capability-state transition governance",
        (
            "Capability support state is historical governed state",
            "the prior state",
            "the new state",
            "the reason for the transition",
            "the evidence or event causing the transition",
            "A later state must not erase the existence of an earlier state",
            "Demotion from `QUALIFIED_SUPPORTED` requires an explicit "
            "governed reason",
        ),
    )

    negative_body = section_body(
        spec_text,
        26,
        "Negative And Uncertain Capability States",
    )

    require_semantics(
        errors,
        negative_body,
        "Task 5 negative and uncertain states",
        (
            "`UNQUALIFIED`",
            "`UNSUPPORTED`",
            "`INCOMPATIBLE`",
            "`BLOCKED`",
            "`UNKNOWN`",
            "must not be hidden",
            "Absence of evidence for support is not automatically "
            "evidence of unsupported capability",
        ),
    )

    invalidation_body = section_body(
        spec_text,
        27,
        "Invalidation And Requalification",
    )

    require_semantics(
        errors,
        invalidation_body,
        "Task 5 invalidation and requalification",
        (
            "Qualification evidence is not permanent merely because "
            "it once passed",
            "target-system version change",
            "adapter change affecting interaction semantics",
            "evaluator change affecting measurement semantics",
            "qualification-contract change",
            "regression demonstrating that the supported capability "
            "no longer satisfies its contract",
            "Requalification must preserve the previous qualification result",
        ),
    )

    # ---------------------------------------------------------
    # Tenant and historical initial-state protections
    # ---------------------------------------------------------

    tenant_body = section_body(
        spec_text,
        28,
        "Tenant, Identity, And Provenance Isolation",
    )

    require_semantics(
        errors,
        tenant_body,
        "Task 5 tenant/provenance isolation",
        (
            "Evidence from one tenant must not silently qualify "
            "another tenant's target",
            "Secrets must not become support-declaration identity",
            "The Artifact Graph remains responsible for artifact provenance",
        ),
    )

    static_body = section_body(
        spec_text,
        29,
        "Static MVP Matrix And Current Capability State",
    )

    require_semantics(
        errors,
        static_body,
        "Task 5 static matrix/current state boundary",
        (
            "frozen initial MVP obligation baseline",
            "six Behavioral obligations are `UNQUALIFIED`",
            "two Internal binding obligations are `UNQUALIFIED`",
            "one combined-engine obligation is `UNQUALIFIED`",
            "Current and historical capability declarations belong "
            "in `CapabilityProfile`",
        ),
    )

    completion_body = section_body(
        spec_text,
        30,
        "Task 5 Completion Versus MVP Capability Completion",
    )

    require_semantics(
        errors,
        completion_body,
        "Task 5 completion boundary",
        (
            "Task 5 can be complete when the support contract itself "
            "has been correctly defined",
            "Task 5 completion does not mean that the nine mandatory "
            "capability obligations have already become "
            "`QUALIFIED_SUPPORTED`",
            "product MVP completion",
            "MVP release readiness",
        ),
    )

    deferred_body = section_body(
        spec_text,
        31,
        "Task 6 Through Task 9 Boundaries",
    )

    require_semantics(
        errors,
        deferred_body,
        "Task 5 deferred later-task boundaries",
        (
            "Task 6 owns",
            "Task 7 owns",
            "Task 8 owns",
            "Task 9 owns",
            "does not authorize Task 5 to choose their concrete values",
        ),
    )

    extension_body = section_body(
        spec_text,
        32,
        "Governed Extension",
    )

    require_semantics(
        errors,
        extension_body,
        "Task 5 governed extension",
        (
            "`CapabilityKind`",
            "`MVPRequirement`",
            "`CapabilitySupportState`",
            "the six required Behavioral matrix cells",
            "the two required Internal binding obligations",
            "the combined-engine obligation",
            "Accepted historical Task 5 semantics must not be "
            "silently rewritten in place",
        ),
    )

    # ---------------------------------------------------------
    # All 50 qualification conditions must preserve meaning
    # ---------------------------------------------------------

    qualification_body = section_body(
        spec_text,
        33,
        "Task 5 Qualification Contract",
    )

    errors.extend(
        validate_condition_semantics(
            qualification_body
        )
    )

    # ---------------------------------------------------------
    # Detect explicit semantic reversals in critical sections
    # ---------------------------------------------------------

    for number, forbidden_fragments in (
        FORBIDDEN_SECTION_SEMANTICS.items()
    ):
        title = SECTION_TITLES[number - 1]
        body = semantic_text(
            section_body(
                spec_text,
                number,
                title,
            )
        )

        for fragment in forbidden_fragments:
            if semantic_text(fragment) in body:
                errors.append(
                    f"section {number} {title!r} contains "
                    f"forbidden semantic reversal: "
                    f"{fragment}"
                )

    # ---------------------------------------------------------
    # Decision 0005 must preserve the same support boundaries
    # ---------------------------------------------------------

    require_semantics(
        errors,
        decision_text,
        "Decision 0005",
        (
            "CapabilityProfile",
            "exactly two initial `CapabilityKind` values",
            "`REGRESSION_REPAIR`",
            "`CONSTRAINED_IMPROVEMENT`",
            "exactly three `MVPRequirement` values",
            "`REQUIRED`",
            "`PERMITTED`",
            "`EXCLUDED`",
            "exactly six `CapabilitySupportState` values",
            "`QUALIFIED_SUPPORTED`",
            "`UNQUALIFIED`",
            "`UNSUPPORTED`",
            "`INCOMPATIBLE`",
            "`BLOCKED`",
            "`UNKNOWN`",
            "six required Behavioral product capability cells",
            "one small open CNN-family binding",
            "one small open Transformer-family binding",
            "one required combined Behavioral/Internal investigation obligation",
            "all nine initial mandatory obligations beginning as `UNQUALIFIED`",
            "No initial Task 5 obligation is declared `QUALIFIED_SUPPORTED`",
            "Task 6 through Task 9",
            "all 50 Task 5 qualification conditions",
            "Qualification criteria must not be weakened merely to "
            "obtain acceptance",
        ),
    )


    decision_metadata = parse_metadata(
        decision_text
    )

    if decision_metadata.get("Status") == "ACCEPTED":
        implementation_body = unnumbered_section_body(
            decision_text,
            "Implementation Evidence",
        )

        verification_body = unnumbered_section_body(
            decision_text,
            "Verification Evidence",
        )

        require_semantics(
            errors,
            implementation_body,
            "accepted Decision 0005 implementation evidence",
            (
                "docs/mvp/05-support-matrix.md",
                "scripts/check_support_matrix.py",
                "tests/qualification/test_support_matrix.py",
            ),
        )

        if "pending" in semantic_text(
            implementation_body
        ):
            errors.append(
                "accepted Decision 0005 implementation "
                "evidence cannot remain pending"
            )

        require_semantics(
            errors,
            verification_body,
            "accepted Decision 0005 verification evidence",
            (
                "docs/decisions/qualification/"
                "0005-mvp-support-matrix.md",
            ),
        )

        if "pending" in semantic_text(
            verification_body
        ):
            errors.append(
                "accepted Decision 0005 verification "
                "evidence cannot remain pending"
            )

    return errors



def validate_qualification_record(
    qualification_path: Path,
    expected_spec_version: str | None,
) -> list[str]:
    errors: list[str] = []

    if not qualification_path.is_file():
        return [
            "missing Decision 0005 qualification evidence"
        ]

    text = qualification_path.read_text()

    if not text.startswith(
        "# Decision 0005 Qualification Record\n"
    ):
        errors.append(
            "Decision 0005 qualification heading mismatch"
        )

    metadata = parse_metadata(text)

    for key, expected in (
        EXPECTED_QUALIFICATION_METADATA.items()
    ):
        actual = metadata.get(key)

        if actual != expected:
            errors.append(
                "Decision 0005 qualification metadata "
                f"{key} must be {expected!r}, "
                f"got {actual!r}"
            )

    specification_version = metadata.get(
        "Specification version"
    )

    if specification_version != expected_spec_version:
        errors.append(
            "Decision 0005 qualification Specification "
            "version must match the Task 5 specification"
        )

    qualification_date = metadata.get("Date", "")

    if not qualification_date:
        errors.append(
            "Decision 0005 qualification Date is required"
        )
    else:
        try:
            date.fromisoformat(
                qualification_date
            )
        except ValueError:
            errors.append(
                "Decision 0005 qualification Date must "
                "be a valid ISO calendar date"
            )

    mutation_result = metadata.get(
        "Mutation result",
        "",
    )

    mutation_match = re.fullmatch(
        r"([0-9]+) / ([0-9]+)",
        mutation_result,
    )

    if mutation_match is None:
        errors.append(
            "Decision 0005 qualification Mutation result "
            "must use N / N format"
        )
    else:
        killed = int(
            mutation_match.group(1)
        )
        total = int(
            mutation_match.group(2)
        )

        if total <= 0:
            errors.append(
                "Decision 0005 qualification requires "
                "a nonzero mutation-suite cardinality"
            )

        if total != EXPECTED_MUTATIONS:
            errors.append(
                "Decision 0005 qualification Mutation result "
                f"must use the frozen {EXPECTED_MUTATIONS} "
                "mutation cardinality"
            )

        if killed != total:
            errors.append(
                "Decision 0005 qualification requires "
                "all recorded mutations to be killed"
            )

    for heading in QUALIFICATION_SECTIONS:
        body = unnumbered_section_body(
            text,
            heading,
        )

        if not body:
            errors.append(
                "Decision 0005 qualification missing "
                f"section {heading}"
            )

    for heading in (
        "Positive Qualification",
        "Structural Qualification",
        "Semantic Qualification",
        "Adversarial Qualification",
        "Authority And Regression Qualification",
    ):
        body = unnumbered_section_body(
            text,
            heading,
        )

        if body and "pass" not in semantic_text(body):
            errors.append(
                "Decision 0005 qualification section "
                f"{heading} must record PASS"
            )

    acceptance_body = unnumbered_section_body(
        text,
        "Acceptance Decision",
    )

    if acceptance_body:
        require_semantics(
            errors,
            acceptance_body,
            "Decision 0005 qualification acceptance",
            (
                "Decision 0005",
                "ACCEPTED",
                "Final accepted-state qualification",
                "PASS",
            ),
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Hetren Task 5 MVP "
            "support-matrix structure."
        )
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )

    parser.add_argument(
        "--require-qualified",
        action="store_true",
        help=(
            "require final Qualified and ACCEPTED "
            "Task 5 state"
        ),
    )

    args = parser.parse_args()
    root = args.root.resolve()

    errors = validate_structure(
        root,
        require_qualified=args.require_qualified,
    )

    if not errors:
        errors.extend(
            validate_semantics(root)
        )

    if errors:
        print(
            "SUPPORT MATRIX VALIDATION: FAIL"
        )

        for error in errors:
            print(f"- {error}")

        return 1

    spec_metadata = parse_metadata(
        (root / SPEC_RELATIVE).read_text()
    )

    decision_metadata = parse_metadata(
        (root / DECISION_RELATIVE).read_text()
    )

    print(
        "SUPPORT MATRIX VALIDATION: PASS"
    )
    print(
        f"- version: "
        f"{spec_metadata.get('Version')}"
    )
    print(
        f"- status: "
        f"{spec_metadata.get('Status')}"
    )
    print(
        f"- decision: "
        f"{decision_metadata.get('Status')}"
    )
    print(
        f"- numbered sections: "
        f"{len(SECTION_TITLES)}"
    )
    print(
        "- Task 5 qualification conditions: 50"
    )
    print(
        "- capability kinds: "
        + ", ".join(CAPABILITY_KINDS)
    )
    print(
        "- MVP requirements: "
        + ", ".join(MVP_REQUIREMENTS)
    )
    print(
        "- capability support states: "
        + ", ".join(
            CAPABILITY_SUPPORT_STATES
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Semantic validation and full qualification-record validation
# are added in subsequent Task 5 qualification steps.
