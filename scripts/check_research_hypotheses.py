#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


SPEC_RELATIVE = Path("docs/mvp/06-research-hypotheses.md")

NATIVE_DECISION_RELATIVE = Path(
    "docs/decisions/0006-native-intelligence-mvp-hypotheses.md"
)

ADAPTIVE_DECISION_RELATIVE = Path(
    "docs/decisions/0007-adaptive-intelligence-mvp-hypotheses.md"
)

REGISTER_RELATIVE = Path("docs/decisions/register.md")

NATIVE_QUALIFICATION_RELATIVE = Path(
    "docs/decisions/qualification/"
    "0006-native-intelligence-mvp-hypotheses.md"
)

ADAPTIVE_QUALIFICATION_RELATIVE = Path(
    "docs/decisions/qualification/"
    "0007-adaptive-intelligence-mvp-hypotheses.md"
)


EXPECTED_MUTATIONS = 52

EXPECTED_SPEC_METADATA = {
    "MVP Task": "6 / 100",
    "Execution authority": "AUTH-HETREN-MVP-3.0",
    "Long-term authority": "AUTH-HETREN-MASTER-2.0",
    "Native governing decision": "0006",
    "Adaptive governing decision": "0007",
    "Native research program": "NATIVE",
    "Adaptive research program": "ADAPTIVE",
    "Research change category": "THESIS",
    "Required evidence consequence": "NEW_PROGRAM_VERSION_AND_RERUN",
    "Governing success semantics": "docs/mvp/03-success-contracts.md",
    "Governing support contract": "docs/mvp/05-support-matrix.md",
}

EXPECTED_NATIVE_DECISION_METADATA = {
    "Decision ID": "0006",
    "Decision Key": "research.native-intelligence.mvp-hypotheses",
    "Title": "Govern initial Native Intelligence MVP hypotheses",
    "Class": "RESEARCH_GOVERNANCE",
    "Authority": "AUTH-HETREN-MVP-3.0",
    "Scope": (
        "Task 6 Native Intelligence MVP hypotheses N-H1 and N-H2, "
        "thesis-level thresholds, falsification criteria, and scientific "
        "claim scope"
    ),
    "Research Program": "NATIVE",
    "Research Change Category": "THESIS",
    "Evidence Consequence": "NEW_PROGRAM_VERSION_AND_RERUN",
    "Supersedes": "None",
    "Superseded By": "None",
    "Reversibility": "CONDITIONALLY_REVERSIBLE",
    "Qualification": "Task 6 research-hypotheses qualification",
}

EXPECTED_ADAPTIVE_DECISION_METADATA = {
    "Decision ID": "0007",
    "Decision Key": "research.adaptive-intelligence.mvp-hypotheses",
    "Title": "Govern initial Adaptive Intelligence MVP hypotheses",
    "Class": "RESEARCH_GOVERNANCE",
    "Authority": "AUTH-HETREN-MVP-3.0",
    "Scope": (
        "Task 6 Adaptive Intelligence MVP hypotheses A-H1 and A-H2, "
        "thesis-level thresholds, falsification criteria, and scientific "
        "claim scope"
    ),
    "Research Program": "ADAPTIVE",
    "Research Change Category": "THESIS",
    "Evidence Consequence": "NEW_PROGRAM_VERSION_AND_RERUN",
    "Supersedes": "None",
    "Superseded By": "None",
    "Reversibility": "CONDITIONALLY_REVERSIBLE",
    "Qualification": "Task 6 research-hypotheses qualification",
}

EXPECTED_DECISION_DATE = "2026-09-17"

ALLOWED_SPEC_STATUSES = {
    "Draft",
    "Requalifying",
    "Qualified",
}

ALLOWED_DECISION_STATUSES = {
    "PROPOSED",
    "ACCEPTED",
}

TASK3_OUTCOMES = (
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
    "BLOCKED",
    "INVALID",
)

EXPECTED_HYPOTHESES = (
    "N-H1",
    "N-H2",
    "A-H1",
    "A-H2",
)

NATIVE_HYPOTHESES = (
    "N-H1",
    "N-H2",
)

ADAPTIVE_HYPOTHESES = (
    "A-H1",
    "A-H2",
)

SECTION_TITLES = (
    "Purpose",
    "Authority And Scope",
    "Research Programs Remain Separate",
    "Initial Hypothesis Set",
    "Hypothesis Record Contract",
    "Thesis Versioning",
    "Task 3 Outcome Separation",
    "Scientific Interpretation",
    "Numerical Threshold Principle",
    "Relative Improvement",
    "Uncertainty Requirement",
    "Multiplicity And Selective Reporting",
    "Hard Constraints",
    "Negative Results",
    "Protected-Evaluation Freeze",
    "Task 7 Dependency",
    "Task 8 Dependency",
    "Task 9 Dependency",
    "Native Intelligence Program Scope",
    "N-H1 — Learned Investigation Value",
    "N-H1 Claim Scope",
    "N-H1 Qualification Criteria",
    "N-H1 Falsification And Narrowing",
    "N-H2 — Cross-Family Learned Transfer",
    "N-H2 Transfer Meaning",
    "N-H2 Qualification Criteria",
    "N-H2 Falsification And Narrowing",
    "Adaptive Intelligence Program Scope",
    "A-H1 — Bounded Useful Adaptation",
    "A-H1 Qualification Criteria",
    "A-H1 Falsification And Narrowing",
    "A-H2 — Retention, Locality, And Rollback",
    "A-H2 Qualification Criteria",
    "A-H2 Falsification And Narrowing",
    "Stronger Claims Explicitly Excluded",
    "Native And Adaptive Transfer Are Separate",
    "Cross-Program Evidence Isolation",
    "External Models",
    "Independent Evaluation",
    "Invalidation",
    "Rerun And Requalification",
    "Claim Narrowing",
    "Product And Research Status Separation",
    "Task 6 Completion Versus Scientific Support",
    "Task 7 Through Task 9 Handoff",
    "Governed Extension",
    "Native Governing Decision",
    "Adaptive Governing Decision",
    "Task 6 Qualification Contract",
    "Research-Hypothesis Principle",
)

DECISION_SECTION_TITLES = (
    "Context And Trigger",
    "Decision",
    "Alternatives Considered",
    "Evidence And Rationale",
    "Assumptions",
    "Consequences",
    "Risks And Constraints",
    "Reversibility And Rollback",
    "Affected Contracts And Components",
    "Research Impact",
    "Qualification Requirement",
    "Implementation Evidence",
    "Verification Evidence",
    "Supersession",
)

QUALIFICATION_SECTION_TITLES = (
    "Scope",
    "Positive Qualification",
    "Structural Qualification",
    "Semantic Qualification",
    "Adversarial Qualification",
    "Authority And Regression Qualification",
    "Limitations",
    "Acceptance Decision",
)


CONDITION_REQUIREMENTS = {
    1: ("AUTH-HETREN-MVP-3.0",),
    2: ("AUTH-HETREN-MASTER-2.0",),
    3: ("N-H1", "N-H2", "A-H1", "A-H2"),
    4: ("N-H1", "N-H2", "Native"),
    5: ("A-H1", "A-H2", "Adaptive"),
    6: ("0006", "Native"),
    7: ("0007", "Adaptive"),
    8: ("THESIS",),
    9: ("NEW_PROGRAM_VERSION_AND_RERUN",),
    10: ("acceptance", "not", "scientific support"),
    11: ("PASS", "FAIL", "INCONCLUSIVE", "BLOCKED", "INVALID"),
    12: ("sixth", "outcome"),
    13: ("product", "capability"),
    14: ("Native", "Adaptive"),
    15: ("Adaptive", "Native"),
    16: ("threshold", "before", "protected"),
    17: ("threshold", "version", "rerun"),
    18: ("uncertainty",),
    19: ("95%",),
    20: ("negative", "null", "inconclusive", "blocked", "invalid"),
    21: ("N-H1", "investigation-decision"),
    22: ("N-H1", "5%", "baseline"),
    23: ("N-H1", "95%", "zero"),
    24: ("N-H1", "two", "independent"),
    25: ("N-H1", "external model", "heuristic", "authored strategy"),
    26: ("N-H2", "system-family"),
    27: ("N-H2", "3%"),
    28: ("N-H2", "95%", "positive"),
    29: ("N-H2", "positive", "50%"),
    30: ("N-H2", "infrastructure", "retrieval", "hand-written"),
    31: ("A-H1", "target adaptation"),
    32: ("A-H1", "5%", "pre-adaptation"),
    33: ("A-H1", "3%", "adaptation baseline"),
    34: ("A-H1", "zero", "critical-invariant"),
    35: ("A-H1", "independent"),
    36: ("A-H2", "retention", "locality", "rollback"),
    37: ("A-H2", "2%"),
    38: ("A-H2", "2%", "bounded", "normalized", "before protected"),
    39: ("A-H2", "zero", "critical-invariant"),
    40: ("A-H2", "rollback"),
    41: ("A-H2", "1%", "rollback"),
    42: ("A-H1", "A-H2", "does not imply"),
    43: ("Native transfer", "Adaptive transfer"),
    44: (
        "continual-learning",
        "cross-model",
        "cross-architecture",
        "multimodal",
        "scaling",
        "universal-transfer",
    ),
    45: ("Task 7", "split"),
    46: ("Task 8", "baseline"),
    47: ("Task 9", "cost", "effort"),
    48: ("invalidated", "preserved", "non-authoritative"),
    49: ("thesis", "version", "rerun"),
    50: ("Task 6 completion", "scientific support", "product qualification"),
}


def strip_code(value: str) -> str:
    value = value.strip()

    if (
        len(value) >= 2
        and value.startswith("`")
        and value.endswith("`")
    ):
        value = value[1:-1]

    return value.strip()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def semantic_text(text: str) -> str:
    text = text.lower()
    text = text.replace("`", "")
    text = text.replace("*", "")
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    for match in re.finditer(
        r"(?m)^\*\*([^*]+):\*\*\s*(.+?)\s*$",
        text,
    ):
        key = match.group(1).strip()
        value = strip_code(match.group(2))
        metadata[key] = value

    return metadata


def numbered_sections(text: str) -> list[tuple[int, str]]:
    return [
        (int(number), title.strip())
        for number, title in re.findall(
            r"(?m)^##\s+([0-9]+)\.\s+(.+?)\s*$",
            text,
        )
    ]


def section_body(
    text: str,
    number: int,
    title: str,
) -> str:
    heading = rf"##\s+{number}\.\s+{re.escape(title)}\s*$"

    match = re.search(
        rf"(?ms)^{heading}\n(.*?)(?=^##\s+[0-9]+\.\s+|\Z)",
        text,
    )

    if not match:
        return ""

    return match.group(1).strip()


def unnumbered_section_body(
    text: str,
    title: str,
) -> str:
    match = re.search(
        rf"(?ms)^##\s+{re.escape(title)}\s*$\n"
        r"(.*?)(?=^##\s+|\Z)",
        text,
    )

    if not match:
        return ""

    return match.group(1).strip()


def numbered_conditions(text: str) -> list[int]:
    return [
        int(value)
        for value in re.findall(
            r"(?m)^([0-9]+)\.\s+",
            text,
        )
    ]


def parse_condition_bodies(text: str) -> dict[int, str]:
    matches = list(
        re.finditer(
            r"(?m)^([0-9]+)\.\s+",
            text,
        )
    )

    result: dict[int, str] = {}

    for index, match in enumerate(matches):
        number = int(match.group(1))
        start = match.start()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        result[number] = normalize(text[start:end])

    return result


def decision_sections(text: str) -> list[str]:
    return [
        title.strip()
        for title in re.findall(
            r"(?m)^##\s+(.+?)\s*$",
            text,
        )
    ]


def parse_register_row(
    text: str,
    decision_id: str,
) -> dict[str, str] | None:
    pattern = (
        rf"(?m)^\|\s*`{re.escape(decision_id)}`\s*\|"
        r"\s*`([^`]+)`\s*\|"
        r"\s*([^|]+?)\s*\|"
        r"\s*`([^`]+)`\s*\|"
        r"\s*`([^`]+)`\s*\|"
        r"\s*`([^`]+)`\s*\|"
        r"\s*`([^`]+)`\s*\|\s*$"
    )

    match = re.search(pattern, text)

    if not match:
        return None

    return {
        "Decision Key": match.group(1).strip(),
        "Title": match.group(2).strip(),
        "Status": match.group(3).strip(),
        "Class": match.group(4).strip(),
        "Authority": match.group(5).strip(),
        "Record": match.group(6).strip(),
    }


def require_semantics(
    errors: list[str],
    body: str,
    label: str,
    phrases: tuple[str, ...],
) -> None:
    semantic = semantic_text(body)

    for phrase in phrases:
        if semantic_text(phrase) not in semantic:
            errors.append(
                f"{label} missing required semantic anchor: {phrase}"
            )


def validate_expected_metadata(
    errors: list[str],
    metadata: dict[str, str],
    expected: dict[str, str],
    label: str,
) -> None:
    for key, expected_value in expected.items():
        actual = metadata.get(key)

        if actual != expected_value:
            errors.append(
                f"{label} metadata {key!r} must be "
                f"{expected_value!r}, found {actual!r}"
            )


def validate_date(
    errors: list[str],
    metadata: dict[str, str],
    label: str,
) -> None:
    actual = metadata.get("Date", "")

    if actual != EXPECTED_DECISION_DATE:
        errors.append(
            f"{label} Date must be "
            f"{EXPECTED_DECISION_DATE!r}, found {actual!r}"
        )
        return

    try:
        date.fromisoformat(actual)
    except ValueError:
        errors.append(
            f"{label} Date is not a valid ISO date"
        )


def validate_decision_record(
    text: str,
    *,
    expected_metadata: dict[str, str],
    decision_id: str,
    label: str,
) -> list[str]:
    errors: list[str] = []
    metadata = parse_metadata(text)

    validate_expected_metadata(
        errors,
        metadata,
        expected_metadata,
        label,
    )
    validate_date(errors, metadata, label)

    status = metadata.get("Status")

    if status not in ALLOWED_DECISION_STATUSES:
        errors.append(
            f"{label} Status must be PROPOSED or ACCEPTED"
        )

    expected_heading = (
        f"# Decision {decision_id}: "
        f"{expected_metadata['Title']}"
    )

    first_line = text.splitlines()[0] if text.splitlines() else ""

    if first_line != expected_heading:
        errors.append(
            f"{label} heading mismatch"
        )

    sections = decision_sections(text)

    if sections != list(DECISION_SECTION_TITLES):
        errors.append(
            f"{label} must contain exact decision section topology"
        )

    decision_body = unnumbered_section_body(
        text,
        "Decision",
    )

    require_semantics(
        errors,
        decision_body,
        f"{label} Decision",
        (
            "Acceptance",
            "not establish",
            "scientific",
        ),
    )

    research_body = unnumbered_section_body(
        text,
        "Research Impact",
    )

    require_semantics(
        errors,
        research_body,
        f"{label} Research Impact",
        (
            expected_metadata["Research Program"],
            "THESIS",
            "NEW_PROGRAM_VERSION_AND_RERUN",
        ),
    )

    qualification_body = unnumbered_section_body(
        text,
        "Qualification Requirement",
    )

    require_semantics(
        errors,
        qualification_body,
        f"{label} Qualification Requirement",
        (
            "decision acceptance",
            "scientific support",
            "Task 7",
            "Task 8",
            "Task 9",
            "adversarial qualification",
        ),
    )

    implementation = unnumbered_section_body(
        text,
        "Implementation Evidence",
    )

    verification = unnumbered_section_body(
        text,
        "Verification Evidence",
    )

    if status == "PROPOSED":
        require_semantics(
            errors,
            decision_body,
            f"{label} proposed lifecycle",
            (
                "PROPOSED",
                "not research implementation authority",
            ),
        )

        if "Pending" not in implementation:
            errors.append(
                f"{label} PROPOSED state requires pending "
                "Implementation Evidence"
            )

        if "Pending" not in verification:
            errors.append(
                f"{label} PROPOSED state requires pending "
                "Verification Evidence"
            )

    if status == "ACCEPTED":
        if (
            "while this decision remains proposed"
            in semantic_text(decision_body)
        ):
            errors.append(
                f"{label} ACCEPTED state retains stale "
                "PROPOSED lifecycle wording"
            )

        if "Pending" in implementation:
            errors.append(
                f"{label} ACCEPTED state cannot retain pending "
                "Implementation Evidence"
            )

        if "Pending" in verification:
            errors.append(
                f"{label} ACCEPTED state cannot retain pending "
                "Verification Evidence"
            )

    return errors


def validate_condition_semantics(
    qualification_body: str,
) -> list[str]:
    errors: list[str] = []
    conditions = parse_condition_bodies(
        qualification_body
    )

    for number in range(1, 51):
        body = conditions.get(number)

        if body is None:
            errors.append(
                f"Task 6 qualification condition {number} missing"
            )
            continue

        semantic = semantic_text(body)

        for phrase in CONDITION_REQUIREMENTS[number]:
            if semantic_text(phrase) not in semantic:
                errors.append(
                    "Task 6 qualification condition "
                    f"{number} missing semantic anchor: {phrase}"
                )

    return errors


def validate_spec_semantics(text: str) -> list[str]:
    errors: list[str] = []

    # ---------------------------------------------------------
    # Exact initial hypothesis set and unresolved status.
    # ---------------------------------------------------------

    initial = section_body(
        text,
        4,
        "Initial Hypothesis Set",
    )

    for hypothesis_id in EXPECTED_HYPOTHESES:
        if hypothesis_id not in initial:
            errors.append(
                f"initial hypothesis set missing {hypothesis_id}"
            )

    require_semantics(
        errors,
        initial,
        "initial hypothesis set",
        (
            "required MVP scientific obligations",
            "govern and evaluate",
            "not requirements that all four hypotheses must receive PASS",
            "scientifically unresolved",
            "does not change that unresolved scientific status",
        ),
    )

    # ---------------------------------------------------------
    # Program isolation.
    # ---------------------------------------------------------

    programs = section_body(
        text,
        3,
        "Research Programs Remain Separate",
    )

    require_semantics(
        errors,
        programs,
        "research-program separation",
        (
            "Native evidence cannot establish an Adaptive hypothesis",
            "Adaptive evidence cannot establish a Native hypothesis",
            "product result cannot establish either research hypothesis",
        ),
    )

    # ---------------------------------------------------------
    # Exact Task 3 outcome vocabulary.
    # ---------------------------------------------------------

    outcomes = section_body(
        text,
        7,
        "Task 3 Outcome Separation",
    )

    for outcome in TASK3_OUTCOMES:
        if f"`{outcome}`" not in outcomes:
            errors.append(
                f"Task 3 outcome separation missing {outcome}"
            )

    require_semantics(
        errors,
        outcomes,
        "Task 3 outcome separation",
        (
            "does not introduce a sixth evaluation outcome",
            "FAIL is valid negative evidence",
            "BLOCKED is not evidence for or against",
            "INVALID evidence must not be reused",
        ),
    )

    # ---------------------------------------------------------
    # Threshold governance.
    # ---------------------------------------------------------

    threshold = section_body(
        text,
        9,
        "Numerical Threshold Principle",
    )

    require_semantics(
        errors,
        threshold,
        "numerical-threshold principle",
        (
            "smallest-effects-of-interest",
            "not universal scientific constants",
            "must not be used to tune the current threshold after the fact",
            "Protected thresholds must be frozen before protected results",
            "must not be weakened",
        ),
    )

    uncertainty = section_body(
        text,
        11,
        "Uncertainty Requirement",
    )

    require_semantics(
        errors,
        uncertainty,
        "uncertainty requirement",
        (
            "95%",
            "lower bound",
            "greater than zero",
            "not weaken",
        ),
    )

    # ---------------------------------------------------------
    # Negative results and freeze.
    # ---------------------------------------------------------

    negative = section_body(
        text,
        14,
        "Negative Results",
    )

    require_semantics(
        errors,
        negative,
        "negative-results contract",
        (
            "Negative results are first-class research evidence",
            "failed comparisons",
            "null effects",
            "falsifying evidence",
            "invalidated experiments",
            "must not be deleted",
        ),
    )

    freeze = section_body(
        text,
        15,
        "Protected-Evaluation Freeze",
    )

    require_semantics(
        errors,
        freeze,
        "protected-evaluation freeze",
        (
            "before protected or hidden evidence is inspected",
            "hypothesis version",
            "success threshold",
            "failure threshold",
            "baseline-binding rule",
            "invalidation conditions",
            "new governed version",
        ),
    )

    # ---------------------------------------------------------
    # Task 7 / 8 / 9 ownership boundaries.
    # ---------------------------------------------------------

    task7 = section_body(text, 16, "Task 7 Dependency")
    task8 = section_body(text, 17, "Task 8 Dependency")
    task9 = section_body(text, 18, "Task 9 Dependency")

    require_semantics(
        errors,
        task7,
        "Task 7 dependency",
        (
            "Task 7 owns concrete",
            "protected or held-out splits",
            "split identities",
            "does not choose",
        ),
    )

    require_semantics(
        errors,
        task8,
        "Task 8 dependency",
        (
            "Task 8 owns concrete",
            "baseline identities",
            "baseline versions",
            "does not choose",
        ),
    )

    require_semantics(
        errors,
        task9,
        "Task 9 dependency",
        (
            "Task 9 owns concrete",
            "cost",
            "effort",
            "does not choose",
        ),
    )

    # ---------------------------------------------------------
    # N-H1 identity and qualification.
    # ---------------------------------------------------------

    nh1 = section_body(
        text,
        20,
        "N-H1 — Learned Investigation Value",
    )

    require_semantics(
        errors,
        nh1,
        "N-H1 definition",
        (
            "Hypothesis ID",
            "N-H1",
            "Program",
            "NATIVE",
            "Thesis version",
            "1.0",
            "learned decision value",
            "not merely a claim",
        ),
    )

    nh1_q = section_body(
        text,
        22,
        "N-H1 Qualification Criteria",
    )

    require_semantics(
        errors,
        nh1_q,
        "N-H1 qualification",
        (
            "strongest applicable Task 8 matched baseline",
            "5% relative",
            "95%",
            "greater than zero",
            "two independent governed evaluation units",
            "do not by themselves create a second independent unit",
            "no applicable hard constraint",
            "independent verification",
        ),
    )

    nh1_f = section_body(
        text,
        23,
        "N-H1 Falsification And Narrowing",
    )

    require_semantics(
        errors,
        nh1_f,
        "N-H1 falsification",
        (
            "below the 5%",
            "does not outperform",
            "95%",
            "external generator",
            "deterministic heuristic",
            "authored strategy",
            "hard constraint",
        ),
    )

    # ---------------------------------------------------------
    # N-H2 identity, transfer meaning and qualification.
    # ---------------------------------------------------------

    nh2 = section_body(
        text,
        24,
        "N-H2 — Cross-Family Learned Transfer",
    )

    require_semantics(
        errors,
        nh2,
        "N-H2 definition",
        (
            "Hypothesis ID",
            "N-H2",
            "Program",
            "NATIVE",
            "held-out system-family boundary",
            "shared infrastructure",
            "hand-written target strategy",
        ),
    )

    nh2_meaning = section_body(
        text,
        25,
        "N-H2 Transfer Meaning",
    )

    require_semantics(
        errors,
        nh2_meaning,
        "N-H2 transfer meaning",
        (
            "transfer of learned decision capability",
            "do not establish N-H2",
            "retrieving examples",
            "hand-authored",
            "target-specific tuning",
        ),
    )

    nh2_q = section_body(
        text,
        26,
        "N-H2 Qualification Criteria",
    )

    require_semantics(
        errors,
        nh2_q,
        "N-H2 qualification",
        (
            "3% relative",
            "95%",
            "strictly greater than zero",
            "retains at least 50% of that positive source-side incremental advantage",
            "leakage controls",
            "independently verified",
        ),
    )

    nh2_f = section_body(
        text,
        27,
        "N-H2 Falsification And Narrowing",
    )

    require_semantics(
        errors,
        nh2_f,
        "N-H2 falsification",
        (
            "below the 3%",
            "source-side incremental advantage is not strictly positive",
            "below 50%",
            "protected target-outcome tuning",
            "shared infrastructure or retrieval",
        ),
    )

    # ---------------------------------------------------------
    # A-H1 identity and qualification.
    # ---------------------------------------------------------

    ah1 = section_body(
        text,
        29,
        "A-H1 — Bounded Useful Adaptation",
    )

    require_semantics(
        errors,
        ah1,
        "A-H1 definition",
        (
            "Hypothesis ID",
            "A-H1",
            "Program",
            "ADAPTIVE",
            "post-deployment plasticity",
            "critical invariants",
            "adaptation baseline",
        ),
    )

    ah1_q = section_body(
        text,
        30,
        "A-H1 Qualification Criteria",
    )

    require_semantics(
        errors,
        ah1_q,
        "A-H1 qualification",
        (
            "5% relative",
            "pre-adaptation state",
            "3% relative",
            "strongest matched adaptation baseline",
            "95%",
            "zero critical-invariant violations",
            "not the sole authority",
            "independent evaluation",
        ),
    )

    ah1_f = section_body(
        text,
        31,
        "A-H1 Falsification And Narrowing",
    )

    require_semantics(
        errors,
        ah1_f,
        "A-H1 falsification",
        (
            "below 5%",
            "below 3%",
            "critical invariant",
            "self-certifies",
            "cannot be reproduced",
        ),
    )

    # ---------------------------------------------------------
    # A-H2 identity and qualification.
    # ---------------------------------------------------------

    ah2 = section_body(
        text,
        32,
        "A-H2 — Retention, Locality, And Rollback",
    )

    require_semantics(
        errors,
        ah2,
        "A-H2 definition",
        (
            "Hypothesis ID",
            "A-H2",
            "Program",
            "ADAPTIVE",
            "protected prior capability",
            "bounded locality envelope",
            "rollback",
        ),
    )

    ah2_q = section_body(
        text,
        33,
        "A-H2 Qualification Criteria",
    )

    require_semantics(
        errors,
        ah2_q,
        "A-H2 qualification",
        (
            "2% relative",
            "2% of",
            "zero critical-invariant violations",
            "rollback is actually executed",
            "within 1% relative",
            "predeclared bounded normalized scale",
            "frozen before protected evidence",
            "post-result normalization",
        ),
    )

    ah2_f = section_body(
        text,
        34,
        "A-H2 Falsification And Narrowing",
    )

    require_semantics(
        errors,
        ah2_f,
        "A-H2 falsification",
        (
            "exceeds 2%",
            "rollback is not executed",
            "within 1%",
            "Passing A-H1 does not imply A-H2",
            "does not imply stronger continual-learning claims",
        ),
    )

    # ---------------------------------------------------------
    # Stronger-claim exclusions.
    # ---------------------------------------------------------

    stronger = section_body(
        text,
        35,
        "Stronger Claims Explicitly Excluded",
    )

    require_semantics(
        errors,
        stronger,
        "stronger-claim exclusions",
        (
            "general intelligence",
            "autonomous self-improvement",
            "indefinite continual learning",
            "Experience Capsule transfer",
            "cross-model Adaptive transfer",
            "cross-architecture Adaptive transfer",
            "multimodal Adaptive transfer",
            "universal Native transfer",
            "scaling-law superiority",
            "deployment authorization",
        ),
    )

    transfer_sep = section_body(
        text,
        36,
        "Native And Adaptive Transfer Are Separate",
    )

    require_semantics(
        errors,
        transfer_sep,
        "transfer-program separation",
        (
            "N-H2 concerns Native",
            "does not establish Adaptive transfer",
            "Native transfer evidence cannot be reused",
        ),
    )

    cross_program = section_body(
        text,
        37,
        "Cross-Program Evidence Isolation",
    )

    require_semantics(
        errors,
        cross_program,
        "cross-program evidence isolation",
        (
            "scientific interpretation remains separate",
            "do not authorize cross-program evidence borrowing",
            "governing program",
            "hypothesis ID",
        ),
    )

    # ---------------------------------------------------------
    # Independent evaluation and invalidation.
    # ---------------------------------------------------------

    independent = section_body(
        text,
        39,
        "Independent Evaluation",
    )

    require_semantics(
        errors,
        independent,
        "independent evaluation",
        (
            "No Native or Adaptive candidate may be the sole authority",
            "Consequential scientific claims require",
            "independent evaluation",
        ),
    )

    invalidation = section_body(
        text,
        40,
        "Invalidation",
    )

    require_semantics(
        errors,
        invalidation,
        "research invalidation",
        (
            "protected-data leakage",
            "evaluator defect",
            "baseline defect",
            "implementation bug",
            "corrupted provenance",
            "preserved as invalidated history",
            "must not silently remain authoritative",
        ),
    )

    rerun = section_body(
        text,
        41,
        "Rerun And Requalification",
    )

    require_semantics(
        errors,
        rerun,
        "research rerun",
        (
            "NEW_PROGRAM_VERSION_AND_RERUN",
            "failed result cannot be repaired",
            "editing the original thesis in place",
        ),
    )

    # ---------------------------------------------------------
    # Product/research separation and Task 6 completion.
    # ---------------------------------------------------------

    status_sep = section_body(
        text,
        43,
        "Product And Research Status Separation",
    )

    require_semantics(
        errors,
        status_sep,
        "product/research status separation",
        (
            "remain independent",
            "QUALIFIED_SUPPORTED",
            "hypothesis fails",
            "Neither state manufactures the other",
        ),
    )

    completion = section_body(
        text,
        44,
        "Task 6 Completion Versus Scientific Support",
    )

    require_semantics(
        errors,
        completion,
        "Task 6 completion separation",
        (
            "Task 6 may be complete",
            "does not mean",
            "N-H1 is supported",
            "N-H2 is supported",
            "A-H1 is supported",
            "A-H2 is supported",
            "later valid experimental evidence",
        ),
    )

    # ---------------------------------------------------------
    # Governing decisions.
    # ---------------------------------------------------------

    native_decision = section_body(
        text,
        47,
        "Native Governing Decision",
    )

    require_semantics(
        errors,
        native_decision,
        "Native governing decision",
        (
            "0006",
            "NATIVE",
            "THESIS",
            "NEW_PROGRAM_VERSION_AND_RERUN",
            "does not establish",
            "N-H1",
            "N-H2",
        ),
    )

    adaptive_decision = section_body(
        text,
        48,
        "Adaptive Governing Decision",
    )

    require_semantics(
        errors,
        adaptive_decision,
        "Adaptive governing decision",
        (
            "0007",
            "ADAPTIVE",
            "THESIS",
            "NEW_PROGRAM_VERSION_AND_RERUN",
            "does not establish",
            "A-H1",
            "A-H2",
        ),
    )

    qualification = section_body(
        text,
        49,
        "Task 6 Qualification Contract",
    )

    errors.extend(
        validate_condition_semantics(
            qualification
        )
    )

    principle = section_body(
        text,
        50,
        "Research-Hypothesis Principle",
    )

    require_semantics(
        errors,
        principle,
        "research-hypothesis principle",
        (
            "claim no more scientific knowledge",
            "hypothesis is allowed to fail",
            "allowed to remain inconclusive",
            "product may succeed while a research hypothesis fails",
            "without authorizing product use",
        ),
    )

    return errors


def expected_qualification_metadata(
    *,
    decision_id: str,
    decision_key: str,
) -> dict[str, str]:
    return {
        "Task": "6 / 100",
        "Decision": decision_id,
        "Decision Key": decision_key,
        "Result": "PASS",
        "Qualification state": "VERIFIED",
        "Specification": "docs/mvp/06-research-hypotheses.md",
        "Specification version": "1.0.0",
        "Validator": "scripts/check_research_hypotheses.py",
        "Mutation suite": "tests/qualification/test_research_hypotheses.py",
        "Qualification conditions": "50 / 50",
        "Mutation result": f"{EXPECTED_MUTATIONS} / {EXPECTED_MUTATIONS}",
        "Execution authority": "AUTH-HETREN-MVP-3.0",
        "Long-term authority": "AUTH-HETREN-MASTER-2.0",
        "Task 1 regression": "PASS",
        "Task 2 regression": "PASS",
        "Task 3 regression": "PASS",
        "Task 4 regression": "PASS",
        "Task 5 regression": "PASS",
        "Diff check": "PASS",
        "Scientific support established": "NO",
        "Final accepted-state qualification": "PASS",
    }


def validate_qualification_record(
    path: Path,
    *,
    decision_id: str,
    decision_key: str,
    expected_title: str,
) -> list[str]:
    errors: list[str] = []

    if not path.is_file():
        return [
            f"missing Decision {decision_id} qualification evidence"
        ]

    text = path.read_text()
    lines = text.splitlines()
    heading = lines[0] if lines else ""

    expected_heading = (
        f"# Decision {decision_id} Qualification Record"
    )

    if heading != expected_heading:
        errors.append(
            f"Decision {decision_id} qualification heading mismatch"
        )

    metadata = parse_metadata(text)
    expected = expected_qualification_metadata(
        decision_id=decision_id,
        decision_key=decision_key,
    )

    for key, expected_value in expected.items():
        actual = metadata.get(key)

        if actual != expected_value:
            errors.append(
                f"Decision {decision_id} qualification metadata "
                f"{key!r} must be {expected_value!r}, "
                f"found {actual!r}"
            )

    qualification_date = metadata.get("Date", "")

    if not qualification_date:
        errors.append(
            f"Decision {decision_id} qualification Date is required"
        )
    else:
        try:
            date.fromisoformat(qualification_date)
        except ValueError:
            errors.append(
                f"Decision {decision_id} qualification Date "
                "must be a valid ISO date"
            )

    sections = decision_sections(text)

    if sections != list(QUALIFICATION_SECTION_TITLES):
        errors.append(
            f"Decision {decision_id} qualification must contain "
            "exact qualification section topology"
        )

    scope = unnumbered_section_body(
        text,
        "Scope",
    )

    require_semantics(
        errors,
        scope,
        f"Decision {decision_id} qualification Scope",
        (
            "research-hypothesis contract",
            "does not",
            "scientific",
        ),
    )

    positive = unnumbered_section_body(
        text,
        "Positive Qualification",
    )

    require_semantics(
        errors,
        positive,
        f"Decision {decision_id} Positive Qualification",
        (
            "PASS",
            "50",
            "four",
            "hypotheses",
        ),
    )

    structural = unnumbered_section_body(
        text,
        "Structural Qualification",
    )

    require_semantics(
        errors,
        structural,
        f"Decision {decision_id} Structural Qualification",
        (
            "specification",
            "50",
            "Decision 0006",
            "Decision 0007",
            "register",
        ),
    )

    semantic = unnumbered_section_body(
        text,
        "Semantic Qualification",
    )

    require_semantics(
        errors,
        semantic,
        f"Decision {decision_id} Semantic Qualification",
        (
            "Native",
            "Adaptive",
            "threshold",
            "falsification",
            "scientific support",
        ),
    )

    adversarial = unnumbered_section_body(
        text,
        "Adversarial Qualification",
    )

    require_semantics(
        errors,
        adversarial,
        f"Decision {decision_id} Adversarial Qualification",
        (
            "PASS",
            str(EXPECTED_MUTATIONS),
            "development",
            "final",
        ),
    )

    authority = unnumbered_section_body(
        text,
        "Authority And Regression Qualification",
    )

    require_semantics(
        errors,
        authority,
        f"Decision {decision_id} Authority Qualification",
        (
            "Task 1",
            "Task 2",
            "Task 3",
            "Task 4",
            "Task 5",
            "PASS",
        ),
    )

    limitations = unnumbered_section_body(
        text,
        "Limitations",
    )

    require_semantics(
        errors,
        limitations,
        f"Decision {decision_id} Limitations",
        (
            "does not establish scientific support",
            "unresolved",
            "later",
            "experimental evidence",
        ),
    )

    acceptance = unnumbered_section_body(
        text,
        "Acceptance Decision",
    )

    require_semantics(
        errors,
        acceptance,
        f"Decision {decision_id} Acceptance Decision",
        (
            f"Decision {decision_id}",
            "ACCEPTED",
            "1.0.0",
            "Qualified",
            str(EXPECTED_MUTATIONS),
            "Final accepted-state qualification",
            "PASS",
            "Scientific support established",
            "NO",
        ),
    )

    if expected_title not in text:
        errors.append(
            f"Decision {decision_id} qualification does not "
            "identify the governed thesis"
        )

    return errors


def validate_structure(
    root: Path,
    *,
    require_qualified: bool,
) -> list[str]:
    errors: list[str] = []

    spec_path = root / SPEC_RELATIVE
    native_path = root / NATIVE_DECISION_RELATIVE
    adaptive_path = root / ADAPTIVE_DECISION_RELATIVE
    register_path = root / REGISTER_RELATIVE

    for path in (
        spec_path,
        native_path,
        adaptive_path,
        register_path,
    ):
        if not path.is_file():
            errors.append(
                f"required Task 6 file missing: "
                f"{path.relative_to(root)}"
            )

    if errors:
        return errors

    spec_text = spec_path.read_text()
    native_text = native_path.read_text()
    adaptive_text = adaptive_path.read_text()
    register_text = register_path.read_text()

    spec_metadata = parse_metadata(spec_text)
    native_metadata = parse_metadata(native_text)
    adaptive_metadata = parse_metadata(adaptive_text)
    register_metadata = parse_metadata(register_text)

    validate_expected_metadata(
        errors,
        spec_metadata,
        EXPECTED_SPEC_METADATA,
        "Task 6 specification",
    )

    spec_status = spec_metadata.get("Status")
    spec_version = spec_metadata.get("Version")

    if spec_status not in ALLOWED_SPEC_STATUSES:
        errors.append(
            "Task 6 specification Status must be "
            "Draft, Requalifying, or Qualified"
        )

    if spec_status == "Draft":
        if spec_version != "0.1.0":
            errors.append(
                "Task 6 Draft specification version must be 0.1.0"
            )

    if spec_status in {"Requalifying", "Qualified"}:
        if spec_version != "1.0.0":
            errors.append(
                "Task 6 final/requalifying specification version "
                "must be 1.0.0"
            )

    actual_sections = numbered_sections(spec_text)
    expected_sections = list(
        enumerate(SECTION_TITLES, start=1)
    )

    if actual_sections != expected_sections:
        errors.append(
            "Task 6 specification must contain exact "
            "50-section numbered topology"
        )

    qualification_body = section_body(
        spec_text,
        49,
        "Task 6 Qualification Contract",
    )

    condition_numbers = numbered_conditions(
        qualification_body
    )

    if condition_numbers != list(range(1, 51)):
        errors.append(
            "Task 6 qualification contract must contain "
            "exactly conditions 1 through 50"
        )

    errors.extend(
        validate_decision_record(
            native_text,
            expected_metadata=EXPECTED_NATIVE_DECISION_METADATA,
            decision_id="0006",
            label="Decision 0006",
        )
    )

    errors.extend(
        validate_decision_record(
            adaptive_text,
            expected_metadata=EXPECTED_ADAPTIVE_DECISION_METADATA,
            decision_id="0007",
            label="Decision 0007",
        )
    )

    native_status = native_metadata.get("Status")
    adaptive_status = adaptive_metadata.get("Status")

    register_version = register_metadata.get("Version")

    if register_version != "1.5.0":
        errors.append(
            "decision register Version must be 1.5.0 for Task 6"
        )

    native_row = parse_register_row(
        register_text,
        "0006",
    )
    adaptive_row = parse_register_row(
        register_text,
        "0007",
    )

    if native_row is None:
        errors.append(
            "Decision 0006 register row missing"
        )
    else:
        expected = {
            "Decision Key":
                "research.native-intelligence.mvp-hypotheses",
            "Title":
                "Govern initial Native Intelligence MVP hypotheses",
            "Class": "RESEARCH_GOVERNANCE",
            "Authority": "AUTH-HETREN-MVP-3.0",
            "Record":
                "0006-native-intelligence-mvp-hypotheses.md",
        }

        for key, value in expected.items():
            if native_row.get(key) != value:
                errors.append(
                    f"Decision 0006 register {key} mismatch"
                )

    if adaptive_row is None:
        errors.append(
            "Decision 0007 register row missing"
        )
    else:
        expected = {
            "Decision Key":
                "research.adaptive-intelligence.mvp-hypotheses",
            "Title":
                "Govern initial Adaptive Intelligence MVP hypotheses",
            "Class": "RESEARCH_GOVERNANCE",
            "Authority": "AUTH-HETREN-MVP-3.0",
            "Record":
                "0007-adaptive-intelligence-mvp-hypotheses.md",
        }

        for key, value in expected.items():
            if adaptive_row.get(key) != value:
                errors.append(
                    f"Decision 0007 register {key} mismatch"
                )

    native_register_status = (
        native_row.get("Status")
        if native_row
        else None
    )

    adaptive_register_status = (
        adaptive_row.get("Status")
        if adaptive_row
        else None
    )

    if native_register_status != native_status:
        errors.append(
            "Decision 0006 register status must match "
            "Decision 0006 record"
        )

    if adaptive_register_status != adaptive_status:
        errors.append(
            "Decision 0007 register status must match "
            "Decision 0007 record"
        )

    # ---------------------------------------------------------
    # Lifecycle synchronization.
    # ---------------------------------------------------------

    if spec_status == "Draft":
        if native_status != "PROPOSED":
            errors.append(
                "Draft Task 6 requires Decision 0006 PROPOSED"
            )

        if adaptive_status != "PROPOSED":
            errors.append(
                "Draft Task 6 requires Decision 0007 PROPOSED"
            )

        if native_register_status != "PROPOSED":
            errors.append(
                "Draft Task 6 requires Decision 0006 "
                "register status PROPOSED"
            )

        if adaptive_register_status != "PROPOSED":
            errors.append(
                "Draft Task 6 requires Decision 0007 "
                "register status PROPOSED"
            )

    if spec_status in {"Requalifying", "Qualified"}:
        if native_status != "ACCEPTED":
            errors.append(
                "final Task 6 state requires Decision 0006 ACCEPTED"
            )

        if adaptive_status != "ACCEPTED":
            errors.append(
                "final Task 6 state requires Decision 0007 ACCEPTED"
            )

        if native_register_status != "ACCEPTED":
            errors.append(
                "final Task 6 state requires Decision 0006 "
                "register status ACCEPTED"
            )

        if adaptive_register_status != "ACCEPTED":
            errors.append(
                "final Task 6 state requires Decision 0007 "
                "register status ACCEPTED"
            )

    if native_status == "ACCEPTED" and spec_status not in {
        "Requalifying",
        "Qualified",
    }:
        errors.append(
            "Decision 0006 cannot be ACCEPTED while "
            "Task 6 specification is Draft"
        )

    if adaptive_status == "ACCEPTED" and spec_status not in {
        "Requalifying",
        "Qualified",
    }:
        errors.append(
            "Decision 0007 cannot be ACCEPTED while "
            "Task 6 specification is Draft"
        )

    # ---------------------------------------------------------
    # Qualification-record lifecycle.
    # ---------------------------------------------------------

    qualification_required = (
        require_qualified
        or spec_status in {"Requalifying", "Qualified"}
        or native_status == "ACCEPTED"
        or adaptive_status == "ACCEPTED"
        or native_register_status == "ACCEPTED"
        or adaptive_register_status == "ACCEPTED"
    )

    if qualification_required:
        errors.extend(
            validate_qualification_record(
                root / NATIVE_QUALIFICATION_RELATIVE,
                decision_id="0006",
                decision_key=(
                    "research.native-intelligence.mvp-hypotheses"
                ),
                expected_title=(
                    "Govern initial Native Intelligence MVP hypotheses"
                ),
            )
        )

        errors.extend(
            validate_qualification_record(
                root / ADAPTIVE_QUALIFICATION_RELATIVE,
                decision_id="0007",
                decision_key=(
                    "research.adaptive-intelligence.mvp-hypotheses"
                ),
                expected_title=(
                    "Govern initial Adaptive Intelligence MVP hypotheses"
                ),
            )
        )

    # ---------------------------------------------------------
    # Final gate.
    # ---------------------------------------------------------

    if require_qualified:
        if spec_status != "Qualified":
            errors.append(
                "final qualification requires "
                "Task 6 specification status Qualified"
            )

        if spec_version != "1.0.0":
            errors.append(
                "final qualification requires "
                "Task 6 specification version 1.0.0"
            )

        if native_status != "ACCEPTED":
            errors.append(
                "final qualification requires "
                "Decision 0006 ACCEPTED"
            )

        if adaptive_status != "ACCEPTED":
            errors.append(
                "final qualification requires "
                "Decision 0007 ACCEPTED"
            )

        if native_register_status != "ACCEPTED":
            errors.append(
                "final qualification requires "
                "Decision 0006 register status ACCEPTED"
            )

        if adaptive_register_status != "ACCEPTED":
            errors.append(
                "final qualification requires "
                "Decision 0007 register status ACCEPTED"
            )

    return errors


def validate_semantics(root: Path) -> list[str]:
    errors: list[str] = []

    spec_text = (root / SPEC_RELATIVE).read_text()
    native_text = (
        root / NATIVE_DECISION_RELATIVE
    ).read_text()
    adaptive_text = (
        root / ADAPTIVE_DECISION_RELATIVE
    ).read_text()

    errors.extend(
        validate_spec_semantics(
            spec_text
        )
    )

    # ---------------------------------------------------------
    # Decision-specific hypothesis ownership.
    # ---------------------------------------------------------

    native_decision = unnumbered_section_body(
        native_text,
        "Decision",
    )

    require_semantics(
        errors,
        native_decision,
        "Decision 0006 thesis semantics",
        (
            "N-H1",
            "N-H2",
            "Learned Investigation Value",
            "Cross-Family Learned Transfer",
            "Acceptance would not establish",
            "scientifically supported",
        ),
    )

    if "A-H1" in native_decision or "A-H2" in native_decision:
        errors.append(
            "Decision 0006 must not govern Adaptive hypotheses"
        )

    adaptive_decision = unnumbered_section_body(
        adaptive_text,
        "Decision",
    )

    require_semantics(
        errors,
        adaptive_decision,
        "Decision 0007 thesis semantics",
        (
            "A-H1",
            "A-H2",
            "Bounded Useful Adaptation",
            "Retention, Locality, and Rollback",
            "Passing A-H1 does not imply passing A-H2",
            "Acceptance would not establish scientific support",
        ),
    )

    if "N-H1" in adaptive_decision or "N-H2" in adaptive_decision:
        errors.append(
            "Decision 0007 must not govern Native hypotheses"
        )

    # ---------------------------------------------------------
    # No acceptance-as-proof language.
    # ---------------------------------------------------------

    for decision_id, text in (
        ("0006", native_text),
        ("0007", adaptive_text),
    ):
        semantic = semantic_text(text)

        forbidden = (
            "acceptance proves the hypothesis",
            "acceptance establishes scientific support",
            "acceptance establishes a scientific pass",
        )

        for phrase in forbidden:
            if phrase in semantic:
                errors.append(
                    f"Decision {decision_id} improperly treats "
                    "governance acceptance as scientific evidence"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Hetren Task 6 governed "
            "research-hypothesis contract."
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
            "require final Qualified specification, "
            "ACCEPTED Decisions 0006/0007, and "
            "verified qualification records"
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
            "RESEARCH HYPOTHESES VALIDATION: FAIL"
        )

        for error in errors:
            print(f"- {error}")

        return 1

    spec_metadata = parse_metadata(
        (root / SPEC_RELATIVE).read_text()
    )

    native_metadata = parse_metadata(
        (root / NATIVE_DECISION_RELATIVE).read_text()
    )

    adaptive_metadata = parse_metadata(
        (root / ADAPTIVE_DECISION_RELATIVE).read_text()
    )

    print(
        "RESEARCH HYPOTHESES VALIDATION: PASS"
    )
    print(
        f"- version: {spec_metadata.get('Version')}"
    )
    print(
        f"- status: {spec_metadata.get('Status')}"
    )
    print(
        "- Native decision: "
        f"{native_metadata.get('Status')}"
    )
    print(
        "- Adaptive decision: "
        f"{adaptive_metadata.get('Status')}"
    )
    print(
        f"- numbered sections: {len(SECTION_TITLES)}"
    )
    print(
        "- Task 6 qualification conditions: 50"
    )
    print(
        "- hypothesis IDs: "
        + ", ".join(EXPECTED_HYPOTHESES)
    )
    print(
        "- research programs: NATIVE, ADAPTIVE"
    )
    print(
        "- thesis evidence consequence: "
        "NEW_PROGRAM_VERSION_AND_RERUN"
    )
    print(
        "- scientific support established by "
        "Task 6 specification: NO"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
