#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


SPEC_RELATIVE = Path(
    "docs/mvp/07-initial-splits.md"
)

DECISION_RELATIVE = Path(
    "docs/decisions/0008-initial-split-protocol.md"
)

REGISTER_RELATIVE = Path(
    "docs/decisions/register.md"
)

QUALIFICATION_RELATIVE = Path(
    "docs/decisions/qualification/"
    "0008-initial-split-protocol.md"
)


EXPECTED_EXECUTION_AUTHORITY = (
    "AUTH-HETREN-MVP-3.0"
)

EXPECTED_LONG_TERM_AUTHORITY = (
    "AUTH-HETREN-MASTER-2.0"
)

EXPECTED_DECISION_ID = "0008"

EXPECTED_DECISION_KEY = (
    "research.evaluation.initial-splits"
)

EXPECTED_DECISION_TITLE = (
    "Govern the initial MVP split protocol"
)

EXPECTED_DECISION_CLASS = "DATA"

EXPECTED_RESEARCH_PROGRAM = "CROSS_PROGRAM"

EXPECTED_RESEARCH_CATEGORY = "DATA"

EXPECTED_EVIDENCE_CONSEQUENCE = (
    "RERUN_AND_PRESERVE_DATA_DISTINCTIONS"
)

EXPECTED_QUALIFICATION = (
    "Task 7 initial-splits qualification"
)

EXPECTED_DRAFT_VERSION = "0.1.0"
EXPECTED_FINAL_VERSION = "1.0.0"

EXPECTED_DEVELOPMENT_MUTATIONS = 52
EXPECTED_FINAL_MUTATIONS = 16
EXPECTED_MUTATIONS = 68

EXPECTED_MUTATION_RESULT = (
    f"{EXPECTED_MUTATIONS} / {EXPECTED_MUTATIONS}"
)


SECTION_TITLES = (
    "Purpose",
    "Authority And Scope",
    "Completion Does Not Manufacture Evidence",
    "Split Integrity Principle",
    "PartitionRole Vocabulary",
    "DEVELOPMENT Semantics",
    "VALIDATION Semantics",
    "PROTECTED Semantics",
    "PartitionPurpose Vocabulary",
    "Role And Purpose Are Separate Axes",
    "SplitPlan",
    "SplitVersion",
    "PartitionIdentity",
    "EvaluationUnit",
    "IndependenceGroup",
    "SplitManifest",
    "Membership And Provenance",
    "Protected Contract Freeze",
    "Protected Evidence Lifecycle",
    "PREPARING And FROZEN States",
    "SEALED State",
    "Candidate Freeze",
    "EVALUATING State",
    "DISCLOSED State",
    "ProtectedAccessEvent",
    "Leakage Taxonomy",
    "ContaminationState",
    "Repeated Protected Peeking",
    "Invalidation And Split Revision",
    "Fresh Protected Evidence",
    "N-H1 Split Binding",
    "N-H1 Independent Evaluation Units",
    "N-H1 Development And Validation Use",
    "N-H2 Split Binding",
    "N-H2 Leave-One-Family-Out Boundaries",
    "N-H2 Transfer Leakage Controls",
    "A-H1 Split Binding",
    "A-H1 Adaptation Input And Protected Outcome Separation",
    "A-H2 Split Binding",
    "A-H2 Paired Pre/Post/Rollback Evaluation",
    "Task 5 Capability Qualification Split Bindings",
    "Initial SplitPlan Registry",
    "Environment-Family Partitioning Rules",
    "Independent Verification And Authority Separation",
    "Task 8 Baseline Handoff",
    "Task 9 Cost And Resource Handoff",
    "Change Control And Evidence Consequence",
    "Governed Extension",
    "Task 7 Qualification Contract",
    "Split Protocol Principle",
)


EXPECTED_PARTITION_ROLES = (
    "DEVELOPMENT",
    "VALIDATION",
    "PROTECTED",
)


EXPECTED_PARTITION_PURPOSES = (
    "PRIMARY_OUTCOME",
    "TRANSFER_SOURCE",
    "TRANSFER_TARGET",
    "ADAPTATION_INPUT",
    "PRIOR_CAPABILITY",
    "LOCALITY",
    "CRITICAL_INVARIANT",
)


EXPECTED_LIFECYCLE_STATES = (
    "PREPARING",
    "FROZEN",
    "SEALED",
    "EVALUATING",
    "DISCLOSED",
    "INVALIDATED",
)


EXPECTED_CONTAMINATION_STATES = (
    "CLEAN",
    "SUSPECTED",
    "CONFIRMED",
    "UNKNOWN",
)


EXPECTED_SPLIT_PLANS = (
    "SPLIT-CAP-E1-RR",
    "SPLIT-CAP-E1-CI",
    "SPLIT-CAP-E2-RR",
    "SPLIT-CAP-E2-CI",
    "SPLIT-CAP-E3-RR",
    "SPLIT-CAP-E3-CI",
    "SPLIT-INT-CNN",
    "SPLIT-INT-TRANSFORMER",
    "SPLIT-COMBINED-BI",
    "SPLIT-NH1-DECISION",
    "SPLIT-NH2-XFAM",
    "SPLIT-AH1-ADAPT",
    "SPLIT-AH2-RETENTION",
)


EXPECTED_NH2_BOUNDARIES = (
    (
        "NH2-XFAM-E1-V1",
        ("E2_STRUCTURED_ML", "E3_VISION"),
        "E1_AGENT",
    ),
    (
        "NH2-XFAM-E2-V1",
        ("E1_AGENT", "E3_VISION"),
        "E2_STRUCTURED_ML",
    ),
    (
        "NH2-XFAM-E3-V1",
        ("E1_AGENT", "E2_STRUCTURED_ML"),
        "E3_VISION",
    ),
)


EXPECTED_LEAKAGE_CATEGORIES = (
    "EXACT_DUPLICATE_LEAKAGE",
    "DERIVED_RECORD_LEAKAGE",
    "NEAR_DUPLICATE_LEAKAGE",
    "LABEL_OR_OUTCOME_LEAKAGE",
    "SYSTEM_STATE_LEAKAGE",
    "TARGET_FAMILY_LEAKAGE",
    "HUMAN_TUNING_LEAKAGE",
    "RETRIEVAL_LEAKAGE",
    "PROMPT_OR_TRACE_LEAKAGE",
    "CACHE_OR_LOG_LEAKAGE",
    "EVALUATOR_FEEDBACK_LEAKAGE",
    "EXTERNAL_TOOL_LEAKAGE",
    "UNKNOWN_MATERIAL_EXPOSURE",
)


EXPECTED_DECISION_METADATA = {
    "Decision ID": EXPECTED_DECISION_ID,
    "Decision Key": EXPECTED_DECISION_KEY,
    "Title": EXPECTED_DECISION_TITLE,
    "Class": EXPECTED_DECISION_CLASS,
    "Authority": EXPECTED_EXECUTION_AUTHORITY,
    "Research Program": EXPECTED_RESEARCH_PROGRAM,
    "Research Change Category": EXPECTED_RESEARCH_CATEGORY,
    "Evidence Consequence": EXPECTED_EVIDENCE_CONSEQUENCE,
    "Supersedes": "None",
    "Superseded By": "None",
    "Reversibility": "CONDITIONALLY_REVERSIBLE",
    "Qualification": EXPECTED_QUALIFICATION,
}


EXPECTED_DECISION_SECTIONS = (
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


def strip_code(value: str) -> str:
    value = value.strip()

    if (
        len(value) >= 2
        and value.startswith("`")
        and value.endswith("`")
    ):
        return value[1:-1]

    return value


def normalize(text: str) -> str:
    return " ".join(
        text.split()
    )


def semantic_text(text: str) -> str:
    return normalize(text).lower()


def parse_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    for line in text.splitlines():
        match = re.match(
            r"^\*\*([^*]+):\*\*\s*(.+?)\s*$",
            line,
        )

        if not match:
            continue

        key = match.group(1).strip()
        value = strip_code(
            match.group(2).strip()
        )

        metadata[key] = value

    return metadata


def numbered_sections(
    text: str,
) -> list[tuple[int, str]]:
    return [
        (
            int(number),
            title.strip(),
        )
        for number, title in re.findall(
            r"^## ([0-9]+)\. (.+)$",
            text,
            flags=re.MULTILINE,
        )
    ]


def section_body(
    text: str,
    section_number: int,
    section_title: str,
) -> str:
    pattern = (
        rf"(?ms)^## {section_number}\. "
        rf"{re.escape(section_title)}\n"
        r"(.*?)"
        r"(?=^## [0-9]+\. |\Z)"
    )

    match = re.search(
        pattern,
        text,
    )

    if not match:
        return ""

    return match.group(1).strip()


def unnumbered_section_body(
    text: str,
    heading: str,
) -> str:
    pattern = (
        rf"(?ms)^## {re.escape(heading)}\n"
        r"(.*?)"
        r"(?=^## |\Z)"
    )

    match = re.search(
        pattern,
        text,
    )

    if not match:
        return ""

    return match.group(1).strip()


def numbered_conditions(
    text: str,
) -> list[int]:
    return [
        int(number)
        for number in re.findall(
            r"^([0-9]+)\. ",
            text,
            flags=re.MULTILINE,
        )
    ]


def parse_condition_bodies(
    text: str,
) -> dict[int, str]:
    conditions: dict[int, str] = {}

    pattern = (
        r"(?ms)^([0-9]+)\. "
        r"(.*?)"
        r"(?=^[0-9]+\. |"
        r"^Qualification must include:|\Z)"
    )

    for number, body in re.findall(
        pattern,
        text,
    ):
        conditions[int(number)] = (
            normalize(body)
        )

    return conditions


def extract_code_bullet_block(
    text: str,
    heading_sentence: str,
) -> tuple[str, ...]:
    start = text.find(
        heading_sentence
    )

    if start < 0:
        return ()

    tail = text[
        start + len(heading_sentence):
    ]

    values: list[str] = []

    for line in tail.splitlines():
        stripped = line.strip()

        if not stripped:
            if values:
                break

            continue

        match = re.fullmatch(
            r"- `([^`]+)`[;.]?",
            stripped,
        )

        if match:
            values.append(
                match.group(1)
            )
            continue

        if values:
            break

    return tuple(values)


def parse_register_0008(
    text: str,
) -> dict[str, str]:
    rows = [
        line
        for line in text.splitlines()
        if line.startswith(
            "| `0008` |"
        )
    ]

    if len(rows) != 1:
        return {}

    parts = [
        part.strip()
        for part in rows[0].split("|")[1:-1]
    ]

    if len(parts) != 7:
        return {}

    values = [
        strip_code(part)
        for part in parts
    ]

    keys = (
        "Decision ID",
        "Decision Key",
        "Title",
        "Status",
        "Class",
        "Authority",
        "Record",
    )

    return dict(
        zip(
            keys,
            values,
            strict=True,
        )
    )


def require_semantics(
    errors: list[str],
    text: str,
    label: str,
    required: tuple[str, ...],
) -> None:
    semantic = semantic_text(
        text
    )

    for phrase in required:
        if semantic_text(phrase) not in semantic:
            errors.append(
                f"{label} missing semantic requirement: "
                f"{phrase}"
            )



def forbid_semantic_patterns(
    errors: list[str],
    text: str,
    label: str,
    patterns: tuple[str, ...],
) -> None:
    """
    Reject dangerous semantic relationships even when the
    canonical positive rule is still present elsewhere.

    Patterns operate over whitespace-normalized lowercase text.
    They intentionally describe classes of contradictions rather
    than exact mutation sentences.
    """

    semantic = semantic_text(
        text
    )

    for pattern in patterns:
        if re.search(
            pattern,
            semantic,
            flags=re.IGNORECASE,
        ):
            errors.append(
                f"{label} contains forbidden semantic relationship: "
                f"{pattern}"
            )




def semantic_clauses(
    text: str,
) -> tuple[str, ...]:
    """
    Split normalized specification prose into local semantic
    clauses so permission/prohibition checks do not accidentally
    combine unrelated sentences.
    """

    semantic = semantic_text(
        text
    )

    clauses = re.split(
        (
            r"(?<=[.!?;])\s+"
            r"|\s+(?:"
            r"however|"
            r"although|"
            r"though|"
            r"because|"
            r"whereas|provided(?:\\s+that)?|"
            r"but"
            r")\s+"
        ),
        semantic,
    )

    return tuple(
        clause.strip()
        for clause in clauses
        if clause.strip()
    )


def forbid_permissive_relationship(
    errors: list[str],
    text: str,
    label: str,
    required_patterns: tuple[str, ...],
) -> None:
    """
    Reject a dangerous relationship only when the same local
    semantic clause grants affirmative permission for it.

    Permission and prohibition polarity are delegated to
    has_affirmative_permission() so every semantic relationship
    checker uses one canonical permission vocabulary.
    """

    for clause in semantic_clauses(
        text
    ):
        if not has_affirmative_permission(
            clause
        ):
            continue

        if all(
            re.search(
                pattern,
                clause,
                flags=re.IGNORECASE,
            )
            for pattern in required_patterns
        ):
            errors.append(
                f"{label} contains a permissive "
                "forbidden relationship: "
                f"{clause}"
            )




def validate_structure(
    root: Path,
    *,
    require_qualified: bool,
) -> list[str]:
    errors: list[str] = []

    spec_path = (
        root / SPEC_RELATIVE
    )
    decision_path = (
        root / DECISION_RELATIVE
    )
    register_path = (
        root / REGISTER_RELATIVE
    )
    qualification_path = (
        root / QUALIFICATION_RELATIVE
    )

    for label, target in (
        ("Task 7 specification", spec_path),
        ("Decision 0008", decision_path),
        ("decision register", register_path),
    ):
        if not target.is_file():
            errors.append(
                f"missing {label}: {target}"
            )

    if errors:
        return errors

    spec_text = spec_path.read_text()
    decision_text = decision_path.read_text()
    register_text = register_path.read_text()

    spec_metadata = parse_metadata(
        spec_text
    )

    decision_metadata = parse_metadata(
        decision_text
    )

    register = parse_register_0008(
        register_text
    )

    # ---------------------------------------------------------
    # Specification metadata and lifecycle.
    # ---------------------------------------------------------

    expected_spec_metadata = {
        "MVP Task": "7 / 100",
        "Execution authority":
            EXPECTED_EXECUTION_AUTHORITY,
        "Long-term authority":
            EXPECTED_LONG_TERM_AUTHORITY,
        "Governing decision":
            EXPECTED_DECISION_ID,
        "Research program":
            EXPECTED_RESEARCH_PROGRAM,
        "Research change category":
            EXPECTED_RESEARCH_CATEGORY,
        "Required evidence consequence":
            EXPECTED_EVIDENCE_CONSEQUENCE,
        "Governing success semantics":
            "docs/mvp/03-success-contracts.md",
        "Governing system taxonomy":
            "docs/mvp/04-system-taxonomy.md",
        "Governing support contract":
            "docs/mvp/05-support-matrix.md",
        "Governing research hypotheses":
            "docs/mvp/06-research-hypotheses.md",
    }

    for key, expected in (
        expected_spec_metadata.items()
    ):
        if spec_metadata.get(key) != expected:
            errors.append(
                "Task 7 specification metadata "
                f"{key!r} must be {expected!r}"
            )

    spec_status = spec_metadata.get(
        "Status",
        "",
    )

    spec_version = spec_metadata.get(
        "Version",
        "",
    )

    if spec_status not in (
        "Draft",
        "Requalifying",
        "Qualified",
    ):
        errors.append(
            "Task 7 specification Status must be "
            "Draft, Requalifying, or Qualified"
        )

    if spec_status == "Draft":
        if spec_version != EXPECTED_DRAFT_VERSION:
            errors.append(
                "Draft Task 7 specification version "
                f"must be {EXPECTED_DRAFT_VERSION}"
            )

    if spec_status in (
        "Requalifying",
        "Qualified",
    ):
        if spec_version != EXPECTED_FINAL_VERSION:
            errors.append(
                "Requalifying/Qualified Task 7 "
                "specification version must be "
                f"{EXPECTED_FINAL_VERSION}"
            )

    # ---------------------------------------------------------
    # Exact numbered section topology.
    # ---------------------------------------------------------

    sections = numbered_sections(
        spec_text
    )

    expected_sections = [
        (
            index,
            title,
        )
        for index, title in enumerate(
            SECTION_TITLES,
            start=1,
        )
    ]

    if sections != expected_sections:
        errors.append(
            "Task 7 numbered section topology "
            "does not match the frozen 50-section contract"
        )

    # ---------------------------------------------------------
    # Qualification-condition topology.
    # ---------------------------------------------------------

    qualification_body = section_body(
        spec_text,
        49,
        "Task 7 Qualification Contract",
    )

    condition_numbers = numbered_conditions(
        qualification_body
    )

    if condition_numbers != list(
        range(1, 51)
    ):
        errors.append(
            "Task 7 qualification contract must "
            "contain exactly ordered conditions 1..50"
        )

    condition_bodies = parse_condition_bodies(
        qualification_body
    )

    if set(condition_bodies) != set(
        range(1, 51)
    ):
        errors.append(
            "Task 7 qualification condition bodies "
            "must exist for all conditions 1..50"
        )

    # ---------------------------------------------------------
    # Decision 0008 structure and metadata.
    # ---------------------------------------------------------

    expected_heading = (
        "# Decision 0008: "
        "Govern the initial MVP split protocol"
    )

    first_line = (
        decision_text.splitlines()[0]
        if decision_text.splitlines()
        else ""
    )

    if first_line != expected_heading:
        errors.append(
            "Decision 0008 heading mismatch"
        )

    for key, expected in (
        EXPECTED_DECISION_METADATA.items()
    ):
        if decision_metadata.get(key) != expected:
            errors.append(
                "Decision 0008 metadata "
                f"{key!r} must be {expected!r}"
            )

    decision_status = (
        decision_metadata.get(
            "Status",
            "",
        )
    )

    if decision_status not in (
        "PROPOSED",
        "ACCEPTED",
    ):
        errors.append(
            "Decision 0008 Status must be "
            "PROPOSED or ACCEPTED"
        )

    for heading in EXPECTED_DECISION_SECTIONS:
        if not unnumbered_section_body(
            decision_text,
            heading,
        ):
            errors.append(
                "Decision 0008 missing or empty "
                f"section: {heading}"
            )

    # ---------------------------------------------------------
    # Register synchronization.
    # ---------------------------------------------------------

    if not register:
        errors.append(
            "Decision register must contain "
            "exactly one parseable Decision 0008 row"
        )

        register_status = ""

    else:
        expected_register = {
            "Decision ID":
                EXPECTED_DECISION_ID,
            "Decision Key":
                EXPECTED_DECISION_KEY,
            "Title":
                EXPECTED_DECISION_TITLE,
            "Class":
                EXPECTED_DECISION_CLASS,
            "Authority":
                EXPECTED_EXECUTION_AUTHORITY,
            "Record":
                "0008-initial-split-protocol.md",
        }

        for key, expected in (
            expected_register.items()
        ):
            if register.get(key) != expected:
                errors.append(
                    "Decision 0008 register "
                    f"{key!r} must be {expected!r}"
                )

        register_status = register.get(
            "Status",
            "",
        )

        if register_status not in (
            "PROPOSED",
            "ACCEPTED",
        ):
            errors.append(
                "Decision 0008 register status must "
                "be PROPOSED or ACCEPTED"
            )

        if (
            register_status
            and decision_status
            and register_status != decision_status
        ):
            errors.append(
                "Decision 0008 record/register "
                "status mismatch"
            )

    # ---------------------------------------------------------
    # Development / final lifecycle.
    # ---------------------------------------------------------

    if spec_status in (
        "Draft",
        "Requalifying",
    ):
        if decision_status != "PROPOSED":
            errors.append(
                "non-Qualified Task 7 specification "
                "requires Decision 0008 PROPOSED"
            )

        if register_status != "PROPOSED":
            errors.append(
                "non-Qualified Task 7 specification "
                "requires Decision 0008 register "
                "status PROPOSED"
            )

    if spec_status == "Qualified":
        if decision_status != "ACCEPTED":
            errors.append(
                "Qualified Task 7 specification "
                "requires Decision 0008 ACCEPTED"
            )

        if register_status != "ACCEPTED":
            errors.append(
                "Qualified Task 7 specification "
                "requires Decision 0008 register "
                "status ACCEPTED"
            )

    if decision_status == "ACCEPTED":
        if spec_status != "Qualified":
            errors.append(
                "Decision 0008 cannot be ACCEPTED "
                "while Task 7 specification is not "
                "Qualified"
            )

    if require_qualified:
        if spec_status != "Qualified":
            errors.append(
                "final qualification requires "
                "Task 7 specification status Qualified"
            )

        if spec_version != EXPECTED_FINAL_VERSION:
            errors.append(
                "final qualification requires "
                "Task 7 specification version "
                f"{EXPECTED_FINAL_VERSION}"
            )

        if decision_status != "ACCEPTED":
            errors.append(
                "final qualification requires "
                "Decision 0008 ACCEPTED"
            )

        if register_status != "ACCEPTED":
            errors.append(
                "final qualification requires "
                "Decision 0008 register status ACCEPTED"
            )

    final_evidence_required = (
        require_qualified
        or spec_status == "Qualified"
        or decision_status == "ACCEPTED"
        or register_status == "ACCEPTED"
    )

    if final_evidence_required:
        if not qualification_path.is_file():
            errors.append(
                "missing Decision 0008 qualification evidence"
            )
        else:
            errors.extend(validate_final_qualification_evidence(root))
    return errors

def parse_split_plan_registry(
    text: str,
) -> dict[str, str]:
    body = section_body(
        text,
        42,
        "Initial SplitPlan Registry",
    )

    plans: dict[str, str] = {}

    for line in body.splitlines():
        match = re.fullmatch(
            r"\| `([^`]+)` \| (.+) \|",
            line.strip(),
        )

        if not match:
            continue

        plan_id = match.group(1)
        use = match.group(2).strip()

        if not plan_id.startswith("SPLIT-"):
            continue

        if plan_id in plans:
            return {}

        plans[plan_id] = use

    return plans


def parse_task5_split_bindings(
    text: str,
) -> dict[str, str]:
    body = section_body(
        text,
        41,
        "Task 5 Capability Qualification Split Bindings",
    )

    bindings: dict[str, str] = {}

    for line in body.splitlines():
        stripped = line.strip()

        behavioral = re.fullmatch(
            r"\| `([^`]+)` \| `([^`]+)` \| `([^`]+)` \|",
            stripped,
        )

        if behavioral:
            family = behavioral.group(1)
            capability = behavioral.group(2)
            plan_id = behavioral.group(3)

            if family.startswith("E") and plan_id.startswith(
                "SPLIT-"
            ):
                key = f"{family}:{capability}"
                bindings[key] = plan_id

            continue

        obligation = re.fullmatch(
            r"\| ([^|]+?) \| `([^`]+)` \|",
            stripped,
        )

        if obligation:
            label = obligation.group(1).strip()
            plan_id = obligation.group(2)

            if plan_id.startswith("SPLIT-"):
                bindings[label] = plan_id

    return bindings


def parse_nh2_boundaries(
    text: str,
) -> tuple[
    tuple[
        str,
        tuple[str, ...],
        str,
    ],
    ...,
]:
    body = section_body(
        text,
        35,
        "N-H2 Leave-One-Family-Out Boundaries",
    )

    boundaries: list[
        tuple[
            str,
            tuple[str, ...],
            str,
        ]
    ] = []

    for line in body.splitlines():
        match = re.fullmatch(
            r"\| `([^`]+)` \| (.+) \| `([^`]+)` \|",
            line.strip(),
        )

        if not match:
            continue

        boundary_id = match.group(1)

        if not boundary_id.startswith(
            "NH2-XFAM-"
        ):
            continue

        sources = tuple(
            re.findall(
                r"`([^`]+)`",
                match.group(2),
            )
        )

        target = match.group(3)

        boundaries.append(
            (
                boundary_id,
                sources,
                target,
            )
        )

    return tuple(boundaries)


def validate_condition_semantics(
    qualification_body: str,
) -> list[str]:
    errors: list[str] = []

    conditions = parse_condition_bodies(
        qualification_body
    )

    requirements: dict[
        int,
        tuple[str, ...],
    ] = {
        1: (
            "AUTH-HETREN-MVP-3.0",
        ),
        2: (
            "AUTH-HETREN-MASTER-2.0",
        ),
        3: (
            "Decision `0008`",
        ),
        4: (
            "`DEVELOPMENT`",
            "`VALIDATION`",
            "`PROTECTED`",
        ),
        5: (
            "`PRIMARY_OUTCOME`",
            "`TRANSFER_SOURCE`",
            "`TRANSFER_TARGET`",
            "`ADAPTATION_INPUT`",
            "`PRIOR_CAPABILITY`",
            "`LOCALITY`",
            "`CRITICAL_INVARIANT`",
        ),
        6: (
            "separate axes",
        ),
        7: (
            "candidate production",
        ),
        8: (
            "candidate selection",
            "protected evidence",
        ),
        9: (
            "frozen governed contract",
        ),
        10: (
            "input visibility",
            "outcome visibility",
        ),
        11: (
            "stable logical partition-design identity",
        ),
        12: (
            "immutable once frozen",
        ),
        13: (
            "partition-membership changes",
            "new identity",
            "versioning",
        ),
        14: (
            "`PartitionIdentity`",
        ),
        15: (
            "`EvaluationUnit`",
        ),
        16: (
            "before protected results",
        ),
        17: (
            "runs",
            "seeds",
            "resamples",
            "independent units",
        ),
        18: (
            "`IndependenceGroup`",
        ),
        19: (
            "`SplitManifest`",
        ),
        20: (
            "duplicate",
            "derivation",
        ),
        21: (
            "hash inequality",
            "independence",
        ),
        22: (
            "protected membership",
            "independence boundaries",
            "before protected outcomes",
        ),
        23: (
            "protected outcome information",
            "sealed",
        ),
        24: (
            "frozen candidate",
        ),
        25: (
            "interactive feedback loop",
        ),
        26: (
            "does not retroactively invalidate",
            "historical evaluation",
        ),
        27: (
            "remove freshness",
            "descendant candidate lineages",
        ),
        28: (
            "`ProtectedAccessEvent`",
        ),
        29: (
            "duplicate",
            "outcome",
            "system-state",
            "human-tuning",
            "retrieval",
            "prompt",
            "cache",
            "evaluator-feedback",
            "external",
        ),
        30: (
            "`CLEAN`",
            "`SUSPECTED`",
            "`CONFIRMED`",
            "`UNKNOWN`",
        ),
        31: (
            "non-clean",
            "clean",
        ),
        32: (
            "repeated protected peeking",
            "predeclared governed protocol",
            "post-hoc",
        ),
        33: (
            "invalidated evidence",
            "original split identity",
            "preserved",
        ),
        34: (
            "RERUN_AND_PRESERVE_DATA_DISTINCTIONS",
        ),
        35: (
            "candidate lineage",
            "claim",
        ),
        36: (
            "`SPLIT-NH1-DECISION`",
        ),
        37: (
            "at least two",
            "independent protected governed",
            "evaluation units",
        ),
        38: (
            "exact decision behavior",
        ),
        39: (
            "`SPLIT-NH2-XFAM`",
        ),
        40: (
            "exactly the three",
            "E1",
            "E2",
            "E3",
            "leave-one-environment-family-out",
        ),
        41: (
            "predeclares",
            "primary protected target boundary",
            "before target outcomes",
        ),
        42: (
            "must not select",
            "post hoc",
            "failed",
            "negative",
        ),
        43: (
            "protected target outcomes",
            "must not tune",
            "transferred Native mechanism",
        ),
        44: (
            "`SPLIT-AH1-ADAPT`",
            "adaptation input",
            "protected target outcomes",
        ),
        45: (
            "protected primary-outcome",
            "critical-invariant",
        ),
        46: (
            "`SPLIT-AH2-RETENTION`",
            "prior-capability",
            "locality",
            "invariant",
        ),
        47: (
            "pre-adaptation",
            "post-adaptation",
            "post-rollback",
            "unit identity",
            "independent units",
        ),
        48: (
            "Task 5",
            "do not manufacture",
            "`QUALIFIED_SUPPORTED`",
        ),
        49: (
            "Task 8",
            "baseline ownership",
            "Task 9",
            "cost/resource ownership",
        ),
        50: (
            "split protocol only",
            "does not establish",
            "scientific support",
            "does not create",
            "experimental `PASS`",
            "does not promote Task 5",
        ),
    }

    if set(requirements) != set(
        range(1, 51)
    ):
        errors.append(
            "internal validator error: "
            "Task 7 condition requirement map "
            "must cover exactly conditions 1..50"
        )

        return errors

    for number in range(1, 51):
        body = conditions.get(
            number,
            "",
        )

        if not body:
            errors.append(
                "Task 7 qualification condition "
                f"{number} is missing"
            )

            continue

        semantic = semantic_text(
            body
        )

        for phrase in requirements[number]:
            if semantic_text(phrase) not in semantic:
                errors.append(
                    "Task 7 qualification condition "
                    f"{number} missing semantic "
                    f"requirement: {phrase}"
                )

    return errors




def contains_all_concepts(
    text: str,
    concept_patterns: tuple[str, ...],
) -> bool:
    """
    Return True when every governed concept appears somewhere in
    the supplied semantic scope, independent of ordering.
    """

    semantic = semantic_text(
        text
    )

    return all(
        re.search(
            pattern,
            semantic,
            flags=re.IGNORECASE,
        )
        is not None
        for pattern in concept_patterns
    )


def forbid_concept_cooccurrence(
    errors: list[str],
    text: str,
    label: str,
    concept_patterns: tuple[str, ...],
) -> None:
    """
    Reject a contract-wide conjunction of concepts representing
    an invalid governed relationship.

    This is intentionally order-independent and does not require
    the concepts to appear in one sentence.
    """

    if contains_all_concepts(
        text,
        concept_patterns,
    ):
        errors.append(
            f"{label} contains forbidden concept composition"
        )


def forbid_cross_document_composition(
    errors: list[str],
    scopes: tuple[str, ...],
    label: str,
    concept_patterns: tuple[str, ...],
) -> None:
    """
    Detect a forbidden composition distributed across multiple
    governed scopes.
    """

    combined = "\n".join(
        scopes
    )

    forbid_concept_cooccurrence(
        errors,
        combined,
        label,
        concept_patterns,
    )




def semantic_paragraphs(
    text: str,
) -> tuple[str, ...]:
    """
    Build local semantic scopes.

    Ordinary multi-sentence paragraphs remain intact so related
    meaning may span sentence boundaries.

    Semicolon-delimited numbered contracts such as:

        1. rule one; 2. rule two; 3. rule three

    are split into separate governed statements. This prevents an
    affirmative permission in one qualification condition from
    being combined with unrelated concepts in another condition.
    """

    raw_paragraphs = re.split(
        r"\n\s*\n+",
        text,
    )

    scopes: list[str] = []

    for raw_paragraph in raw_paragraphs:
        paragraph = semantic_text(
            raw_paragraph
        )

        if not paragraph:
            continue

        numbered_scopes = re.split(
            r";\s+(?=\d+\.\s)",
            paragraph,
        )

        scopes.extend(
            scope.strip()
            for scope in numbered_scopes
            if scope.strip()
        )

    return tuple(
        scopes
    )



def has_affirmative_permission(
    text: str,
) -> bool:
    """
    Return True when at least one local semantic clause grants
    permission instead of prohibiting the behavior.
    """

    permission_pattern = re.compile(
        r"\b(?:"
        r"may|can|"
        r"allow(?:ed|s)?|"
        r"permit(?:ted|s)?|"
        r"authoriz(?:e|es|ed)|"
        r"acceptable|"
        r"considered\s+valid(?:\s+when\s+configured)?|"
        r"sufficient"
        r")\b",
        flags=re.IGNORECASE,
    )

    prohibition_pattern = re.compile(
        r"\b(?:"
        r"must not|"
        r"may not|"
        r"cannot|"
        r"can not|"
        r"do not|"
        r"does not|"
        r"did not|"
        r"is not allowed|"
        r"are not allowed|"
        r"is not permitted|"
        r"are not permitted|"
        r"is not authorized|"
        r"are not authorized|"
        r"is not acceptable|"
        r"are not acceptable|"
        r"is not considered valid|"
        r"are not considered valid|"
        r"prohibited|"
        r"forbidden"
        r")\b",
        flags=re.IGNORECASE,
    )

    for clause in semantic_clauses(
        text
    ):
        if not permission_pattern.search(
            clause
        ):
            continue

        if prohibition_pattern.search(
            clause
        ):
            continue

        return True

    return False


def paragraph_has_permissive_relationship(
    text: str,
    concept_patterns: tuple[str, ...],
) -> bool:
    """
    Detect an affirmative permission whose complete semantic
    relationship is expressed within one governed paragraph.

    Concepts may span sentences in that paragraph, preventing a
    harmless second-sentence negation from cancelling an earlier
    affirmative permission.
    """

    for paragraph in semantic_paragraphs(
        text
    ):
        if not has_affirmative_permission(
            paragraph
        ):
            continue

        if contains_all_concepts(
            paragraph,
            concept_patterns,
        ):
            return True

    return False


def forbid_permissive_paragraph_relationship(
    errors: list[str],
    text: str,
    label: str,
    concept_patterns: tuple[str, ...],
) -> None:
    if paragraph_has_permissive_relationship(
        text,
        concept_patterns,
    ):
        errors.append(
            f"{label} contains forbidden permissive composition"
        )



def validate_global_contradictions(
    spec_text: str,
    decision_text: str,
) -> list[str]:
    """
    Detect contract-wide semantic contradictions.

    Canonical section validation proves that required rules exist.
    This layer separately proves that distant prose does not grant
    authority for relationships forbidden by those rules.
    """

    errors: list[str] = []

    # Closed controlled vocabularies must not be extended elsewhere
    # without governed revision.
    forbid_permissive_relationship(
        errors,
        spec_text,
        "global PartitionRole closure",
        (
            r"\bpartitionrole\b",
            r"\b(?:fourth|additional|extra|new)\b",
            r"\b(?:role|value)\b",
            r"\b(?:without revising|without revision|without governance|without changing)\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        spec_text,
        "global PartitionPurpose closure",
        (
            r"\bpartitionpurpose\b",
            r"\b(?:eighth|additional|extra|new)\b",
            r"\b(?:purpose|value)\b",
            r"\b(?:without revising|without revision|without governance|without changing)\b",
        ),
    )

    # Immutable governed identity must not be silently retained
    # across material mutation.
    forbid_permissive_relationship(
        errors,
        spec_text,
        "global SplitVersion immutability",
        (
            r"\bsplitversion\b",
            r"\bmembership\b",
            r"\b(?:edit|edited|change|changed|modify|modified|mutate|mutated)\b",
            r"\b(?:retain|retaining|same|existing|in place)\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        spec_text,
        "global candidate identity integrity",
        (
            r"\bcandidate identity\b",
            r"\bmaterial(?:ly)?\b",
            r"\b(?:change|changed|modify|modified)\b",
            r"\b(?:retain|retaining|reuse|same|existing)\b",
        ),
    )

    # Contamination cannot become clean merely through time,
    # silence, or absence of additional evidence.
    forbid_permissive_relationship(
        errors,
        spec_text,
        "global contamination anti-laundering",
        (
            r"\bunknown\b",
            r"\bclean\b",
            r"\b(?:transition|expire|expires|become|becomes|convert|converts)\b",
            r"\b(?:automatic|automatically|time|days|weeks|months|absence|no additional)\b",
        ),
    )

    # Aggregate output does not evade protected-peeking governance.
    forbid_permissive_relationship(
        errors,
        spec_text,
        "global protected-peeking bound",
        (
            r"\bprotected\b",
            r"\b(?:aggregate|summary)\b",
            r"\b(?:score|scores|outcome|outcomes)\b",
            r"\b(?:inspect|inspected|peek|peeking|query|queried)\b",
            r"\b(?:without.*limit|unlimited|no.*limit|unbounded)\b",
        ),
    )

    # Derived summaries remain capable of transmitting protected
    # information and therefore cannot be declared freshness-neutral.
    forbid_permissive_relationship(
        errors,
        spec_text,
        "global derived-artifact freshness integrity",
        (
            r"\b(?:"
            r"paraphrase|paraphrases|summary|summaries|"
            r"retrieval index|index|indexes|indices|"
            r"embedding|embeddings|retrieval artifact|retrieval artifacts|"
            r"derived representation|derived representations|"
            r"artifact|artifacts|cache|caches|digest|digests|"
            r"copy|copies|transform|transformed|transformation"
            r")\b",
            r"\b(?:protected|disclosed|exposed)\b",
            r"\bfresh(?:ness)?\b",
            r"\b(?:"
            r"treat|treated|qualif(?:y|ies|ied)|"
            r"consider|considered|declare|declared"
            r")\b",
        ),
    )

    # Changing evaluator identity does not manufacture an
    # independent scientific unit from the same evidence source.
    forbid_permissive_relationship(
        errors,
        spec_text,
        "global N-H1 anti-pseudoreplication",
        (
            r"\b(?:same underlying|same source|same protected case|derived from the same)\b",
            r"\b(?:evaluator|evaluators|reviewer|reviewers)\b",
            r"\b(?:independent|independence)\b",
            r"\b(?:unit|units|gate)\b",
        ),
    )

    # Finite observed family coverage cannot manufacture a
    # universal transfer claim.
    forbid_permissive_relationship(
        errors,
        spec_text,
        "global transfer-claim boundedness",
        (
            r"\b(?:boundary|boundaries|family|families)\b",
            r"\buniversal\b",
            r"\btransfer\b",
            r"\b(?:beyond|outside|unevaluated|unseen)\b",
        ),
    )

    # Success of one Adaptive hypothesis cannot automatically
    # satisfy the other.
    forbid_semantic_patterns(
        errors,
        spec_text,
        "global Adaptive hypothesis independence",
        (
            r"\ba-h1\b.{0,180}"
            r"\b(?:automatically|directly|necessarily)\b.{0,100}"
            r"\b(?:satisf(?:y|ies|ied)|implies?|establish(?:es|ed)?)\b"
            r".{0,100}\ba-h2\b",
            r"\ba-h2\b.{0,180}"
            r"\b(?:automatically|directly|necessarily)\b.{0,100}"
            r"\b(?:satisf(?:y|ies|ied)|implies?|establish(?:es|ed)?)\b"
            r".{0,100}\ba-h1\b",
        ),
    )

    # Auditability does not make the candidate-producing process
    # an independent certifier.
    forbid_permissive_relationship(
        errors,
        spec_text,
        "global anti-self-certification",
        (
            r"\b(?:originating|candidate-producing|candidate-construction|candidate construction)\b",
            r"\b(?:own certification|self-certif|certif)\b",
            r"\b(?:audit|audit log|logged)\b",
        ),
    )

    # Comparator/baseline selection cannot be moved after protected
    # outcomes to obtain a more favorable conclusion.
    forbid_permissive_relationship(
        errors,
        spec_text,
        "global post-result comparator integrity",
        (
            r"\b(?:after|following|once)\b",
            r"\bprotected outcomes?\b",
            r"\b(?:comparator|baseline)\b",
            r"\b(?:select|selected|switch|switched|replace|replaced|choose|chosen)\b",
            r"\b(?:favorable|advantage|efficiency|better)\b",
        ),
    )

    # Decision acceptance remains governance, never experimental
    # or scientific evidence.
    forbid_permissive_relationship(
        errors,
        decision_text,
        "global Decision 0008 evidence separation",
        (
            r"\bacceptance\b",
            r"\b(?:scientific|experimental)\b",
            r"\b(?:support|evidence|proof|pass|supported)\b",
        ),
    )


    # ---------------------------------------------------------
    # Set B architecture-level invariants.
    #
    # These defend governed relationships, aliases, information
    # flow, lineage, lifecycle, authority, and composition rather
    # than memorizing particular mutation sentences.
    # ---------------------------------------------------------

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "PartitionRole alias-bypass integrity",
        (
            r"\bpartitionrole\b",
            r"\b(?:alias|normalize|normalise|mapping)\b",
            r"\b(?:persist|stored|operational|report)\w*\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "PartitionPurpose alias-bypass integrity",
        (
            r"\b(?:partitionpurpose|purpose)\b",
            r"\b(?:"
            r"alias|normalize|normalise|mapping|"
            r"override|overrides|overridden|"
            r"control|controls|controlled|"
            r"govern|governs|governed|"
            r"determin(?:e|es|ed|ing)|"
            r"exercise|exercises"
            r")\b",
            r"\b(?:"
            r"persist|stored|operational|report|"
            r"authority|evidence|protected"
            r")\w*\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "SplitVersion identity-retention integrity",
        (
            r"\bfrozen\b",
            r"\bsplitversion\b",
            r"\bidentity\b",
            r"\b(?:retain|retains|retaining|keep|keeps|keeping|existing|same)\b",
            r"\b(?:"
            r"member|members|membership|"
            r"dataset|manifest|snapshot|registry|"
            r"population|partition|object|reference"
            r")\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "SplitVersion referential immutability",
        (
            r"\bfrozen\b",
            r"\bsplitversion\b",
            r"\b(?:member|members|membership|member set)\b",
            r"\b(?:repoint|repointed|redirect|retarget|revise|revised)\b",
            r"\b(?:retain|retaining|keep|keeps|same|existing)\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "protected-derived-signal lineage",
        (
            r"\bprotected\b",
            r"\b(?:metric|metrics|telemetry|dashboard|summary|summaries|aggregate|band|bands)\b",
            r"\b(?:candidate|method|mechanism)\b",
            r"\b(?:choose|chosen|select|selected|rank|ranked|influence|influences|adapt|tune|used)\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "non-clean effective-CLEAN integrity",
        (
            r"\b(?:suspected|confirmed|unknown)\b",
            r"\bclean\b",
            r"\b(?:"
            r"treat|treated|treating|"
            r"equivalent|operationally"
            r")\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "contamination effective-state integrity",
        (
            r"\b(?:suspected|confirmed|unknown)\b",
            r"\bclean\b",
            r"\b(?:treat|treated|equivalent|release gating|qualification)\b",
            r"\b(?:threshold|probability|confidence|stored state|without changing)\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "protected invalidation transition integrity",
        (
            r"\binvalidated\b",
            r"\b(?:disclosed|valid|restore|restored|return|returned|reinstate|reinstated)\b",
            r"\b(?:rerun|splitversion|new split|replacement)\b",
            r"\b(?:without|waive|waived|skip|skipped)\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "shared-source count-as-independent integrity",
        (
            r"(?<!\bno )(?<!\bwithout )"
            r"\b(?:same|shared|one)\b.{0,120}"
            r"\b(?:"
            r"source|upstream|lineage|ancestor|ancestry|"
            r"population|scenario seed bank|seed bank"
            r")\b",
            r"\b(?:"
            r"source|upstream|lineage|ancestor|ancestry|"
            r"population|scenario seed bank|seed bank"
            r")\b",
            r"\bcount(?:s|ed|ing)?\b",
            r"\bindependent\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "shared-ancestry independence integrity",
        (
            r"\b(?:same|shared|one)\b",
            r"\b(?:source|ancestor|ancestry|lineage|upstream)\b",
            r"\b(?:"
            r"window|windows|slice|slices|partition|partitions|"
            r"compression|serialization|encoding|packaging|"
            r"representation|representations|pipeline|pipelines|"
            r"mirror|mirrors|copy|copies"
            r")\b",
            r"\bindependent\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        spec_text,
        "protected-target-derived-selection integrity",
        (
            r"\bprotected\b",
            r"\btarget\b",
            r"\b(?:outcome|outcomes)\b",
            r"\b(?:method|methods|mechanism|mechanisms|candidate|candidates)\b",
            r"\b(?:"
            r"select(?:s|ed|ing|ion)?|"
            r"rank(?:s|ed|ing)?|"
            r"choose|chooses|choosing|chosen|"
            r"use|uses|used|using|"
            r"influenc(?:e|es|ed|ing)"
            r")\b",
            r"\b(?:before|pre)\b",
            r"\b(?:freeze|frozen)\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        spec_text,
        "N-H2 proxy-outcome leakage integrity",
        (
            r"\b(?:target(?:-family)?|protected)\b",
            r"\b(?:"
            r"performance|metric|score|band|bands|"
            r"ranking|rank|signal|grade|grades|"
            r"class|classes|classification|classifications|"
            r"severity|challenge|threshold|thresholds|"
            r"quartile|quartiles|timing|arrival"
            r")\b",
            r"\b(?:"
            r"method|mechanism|candidate|strategy|strategies"
            r")\b",
            r"\b(?:"
            r"select(?:s|ed|ing|ion)?|"
            r"rank(?:s|ed|ing)?|"
            r"choose|chooses|choosing|chosen|"
            r"use|uses|used|using|"
            r"revis(?:e|es|ed|ing)|"
            r"tun(?:e|es|ed|ing)|"
            r"adapt(?:s|ed|ing|ation)?|"
            r"influenc(?:e|es|ed|ing)"
            r")\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "Adaptive cross-hypothesis laundering integrity",
        (
            r"\ba-h1\b",
            r"\ba-h2\b",
            r"\b(?:retroactive|retroactively|repair|validate|validated|rescue)\b",
            r"\b(?:contaminat|incomplete|invalid|leak)\w*\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        spec_text,
        "verification shared-authority integrity",
        (
            r"\bverifier\b",
            r"\bcertif\w*\b",
            r"\b(?:share|shares|shared|same)\b",
            r"\b(?:"
            r"agent|controller|credential|credentials|"
            r"authority|evidence|store|storage|"
            r"database|repository|state|"
            r"secret|identity|principal"
            r")\b",
        ),
    )

    forbid_permissive_paragraph_relationship(
        errors,
        spec_text,
        "verification structural-independence integrity",
        (
            r"\b(?:separate process|separate operating-system process|different process)\b",
            r"\b(?:same|shared)\b",
            r"\b(?:controller|controlling agent|credential|credentials|writable evidence|evidence store)\b",
            r"\b(?:certif|verification|verify)\w*\b",
        ),
    )

    section_45 = section_body(
        spec_text,
        45,
        "Task 8 Baseline Handoff",
    )

    section_46 = section_body(
        spec_text,
        46,
        "Task 9 Cost And Resource Handoff",
    )

    baseline_resource_filter_is_gamed = (
        paragraph_has_permissive_relationship(
            section_45,
            (
                r"\b(?:baseline|baselines|comparator|comparators)\b",
                r"\b(?:"
                r"resource|cost|eligibility|report|reporting"
                r")\w*\b",
                r"\b(?:"
                r"determin|narrow|filter|remove|"
                r"decid|restrict|exclude"
                r")\w*\b",
            ),
        )
    )

    baseline_post_result_is_gamed = (
        paragraph_has_permissive_relationship(
            section_45,
            (
                r"\b(?:baseline|baselines|comparator|comparators)\b",
                r"\b(?:"
                r"after|once|observed|evaluation|"
                r"measurement|measurements|outcome|outcomes|"
                r"result|results|efficiency|preferred"
                r")\b",
                r"\b(?:"
                r"eligib|determin|narrow|filter|remove|"
                r"decid|restrict|exclude|switch|select"
                r")\w*\b",
            ),
        )
    )

    accounting_post_result_is_gamed = (
        paragraph_has_permissive_relationship(
            section_46,
            (
                r"\b(?:"
                r"protected|after|once|post(?:-result)?"
                r")\b",
                r"\b(?:"
                r"measurement|measurements|"
                r"outcome|outcomes|"
                r"result|results|evaluation"
                r")\b",
                r"\b(?:"
                r"eligibility|accounting|window|"
                r"resource|cost|boundary|boundaries|policy"
                r")\b",
                r"\b(?:"
                r"adjust|change|revis|exclude|"
                r"influenc|narrow|preserv|retain|keep"
                r")\w*\b",
            ),
        )
    )

    accounting_boundary_is_gamed = (
        paragraph_has_permissive_relationship(
            section_46,
            (
                r"\b(?:"
                r"accounting|resource|resources|cost|costs|"
                r"window|boundary|boundaries|policy"
                r")\b",
                r"\b(?:"
                r"adjust|change|revis|exclude|influenc|"
                r"narrow|preserv|retain|keep|remove|filter"
                r")\w*\b",
            ),
        )
    )

    baseline_side_is_gamed = (
        baseline_resource_filter_is_gamed
        or baseline_post_result_is_gamed
    )

    accounting_side_is_gamed = (
        accounting_post_result_is_gamed
        or accounting_boundary_is_gamed
    )

    if (
        baseline_side_is_gamed
        and accounting_side_is_gamed
    ):
        errors.append(
            "baseline-resource composition integrity "
            "contains distributed permissive gaming"
        )

    forbid_permissive_relationship(
        errors,
        (
            decision_text
            + "\n\n"
            + section_body(
                spec_text,
                47,
                "Change Control And Evidence Consequence",
            )
        ),
        "DATA evidence-consequence non-waiver",
        (
            r"\bmaterial\b",
            r"\b(?:revision|change|split)\b",
            r"\b(?:"
            r"waive|waived|waiver|"
            r"skip|skipped|"
            r"reuse|reused|"
            r"defer|deferred"
            r")\b",
            r"\b(?:"
            r"rerun(?:_and_preserve_data_distinctions)?|"
            r"prior (?:protected )?result|protected result"
            r")\b",
        ),
    )

    return errors



def validate_semantics(
    root: Path,
) -> list[str]:
    errors: list[str] = []

    spec_text = (
        root / SPEC_RELATIVE
    ).read_text()

    decision_text = (
        root / DECISION_RELATIVE
    ).read_text()

    errors.extend(
        validate_global_contradictions(
            spec_text,
            decision_text,
        )
    )

    # ---------------------------------------------------------
    # Exact controlled vocabularies.
    # ---------------------------------------------------------

    role_body = section_body(
        spec_text,
        5,
        "PartitionRole Vocabulary",
    )

    roles = extract_code_bullet_block(
        role_body,
        "The initial `PartitionRole` vocabulary is exactly:",
    )

    if roles != EXPECTED_PARTITION_ROLES:
        errors.append(
            "PartitionRole vocabulary must be exactly: "
            + ", ".join(
                EXPECTED_PARTITION_ROLES
            )
        )

    purpose_body = section_body(
        spec_text,
        9,
        "PartitionPurpose Vocabulary",
    )

    purposes = extract_code_bullet_block(
        purpose_body,
        "The initial purpose vocabulary is exactly:",
    )

    if purposes != EXPECTED_PARTITION_PURPOSES:
        errors.append(
            "PartitionPurpose vocabulary does not "
            "match the frozen seven-value contract"
        )

    lifecycle_body = section_body(
        spec_text,
        19,
        "Protected Evidence Lifecycle",
    )

    lifecycle = extract_code_bullet_block(
        lifecycle_body,
        "The initial `ProtectedLifecycleState` vocabulary is exactly:",
    )

    if lifecycle != EXPECTED_LIFECYCLE_STATES:
        errors.append(
            "ProtectedLifecycleState vocabulary "
            "does not match the frozen contract"
        )

    contamination_body = section_body(
        spec_text,
        27,
        "ContaminationState",
    )

    contamination = extract_code_bullet_block(
        contamination_body,
        "The initial contamination vocabulary is exactly:",
    )

    if contamination != EXPECTED_CONTAMINATION_STATES:
        errors.append(
            "ContaminationState vocabulary must be "
            "exactly CLEAN, SUSPECTED, CONFIRMED, UNKNOWN"
        )

    leakage_body = section_body(
        spec_text,
        26,
        "Leakage Taxonomy",
    )

    leakage = extract_code_bullet_block(
        leakage_body,
        "The initial governed leakage categories include:",
    )

    if leakage != EXPECTED_LEAKAGE_CATEGORIES:
        errors.append(
            "Task 7 leakage taxonomy does not match "
            "the frozen initial categories"
        )

    # ---------------------------------------------------------
    # Identity model.
    # ---------------------------------------------------------

    split_plan_body = section_body(
        spec_text,
        11,
        "SplitPlan",
    )

    require_semantics(
        errors,
        split_plan_body,
        "SplitPlan identity semantics",
        (
            "stable logical identity",
            "not itself one execution",
            "multiple `SplitVersion` records",
            "intentionally versionless",
            "Version identity belongs to `SplitVersion`",
        ),
    )

    split_version_body = section_body(
        spec_text,
        12,
        "SplitVersion",
    )

    require_semantics(
        errors,
        split_version_body,
        "SplitVersion semantics",
        (
            "immutable governed version",
            "membership rules",
            "partition identities",
            "evaluation-unit identities",
            "independence-group assignments",
            "protected access policy",
            "material change creates a new `SplitVersion`",
            "old version remains preserved",
        ),
    )

    if re.search(
        r"\bSPLIT-[A-Z0-9-]+-V[0-9]+\b",
        section_body(
            spec_text,
            42,
            "Initial SplitPlan Registry",
        ),
    ):
        errors.append(
            "SplitPlan IDs must be versionless; "
            "version identity belongs to SplitVersion"
        )

    registry = parse_split_plan_registry(
        spec_text
    )

    if tuple(registry.keys()) != (
        EXPECTED_SPLIT_PLANS
    ):
        errors.append(
            "initial SplitPlan registry must contain "
            "exactly the frozen 13 stable plan IDs "
            "in governed order"
        )

    expected_plan_uses = {
        "SPLIT-CAP-E1-RR":
            "E1 Behavioral regression-repair qualification",
        "SPLIT-CAP-E1-CI":
            "E1 Behavioral constrained-improvement qualification",
        "SPLIT-CAP-E2-RR":
            "E2 Behavioral regression-repair qualification",
        "SPLIT-CAP-E2-CI":
            "E2 Behavioral constrained-improvement qualification",
        "SPLIT-CAP-E3-RR":
            "E3 Behavioral regression-repair qualification",
        "SPLIT-CAP-E3-CI":
            "E3 Behavioral constrained-improvement qualification",
        "SPLIT-INT-CNN":
            "authorized Internal CNN-family qualification",
        "SPLIT-INT-TRANSFORMER":
            "authorized Internal Transformer-family qualification",
        "SPLIT-COMBINED-BI":
            "combined Behavioral and Internal qualification",
        "SPLIT-NH1-DECISION":
            "`N-H1` learned investigation-decision evaluation",
        "SPLIT-NH2-XFAM":
            "`N-H2` cross-family learned-transfer evaluation",
        "SPLIT-AH1-ADAPT":
            "`A-H1` bounded useful-adaptation evaluation",
        "SPLIT-AH2-RETENTION":
            "`A-H2` retention, locality, and rollback evaluation",
    }

    if registry != expected_plan_uses:
        errors.append(
            "initial SplitPlan registry uses or "
            "bindings have drifted"
        )

    # ---------------------------------------------------------
    # Task 5 split obligations.
    # ---------------------------------------------------------

    task5_bindings = parse_task5_split_bindings(
        spec_text
    )

    expected_task5_bindings = {
        "E1_AGENT:REGRESSION_REPAIR":
            "SPLIT-CAP-E1-RR",
        "E1_AGENT:CONSTRAINED_IMPROVEMENT":
            "SPLIT-CAP-E1-CI",
        "E2_STRUCTURED_ML:REGRESSION_REPAIR":
            "SPLIT-CAP-E2-RR",
        "E2_STRUCTURED_ML:CONSTRAINED_IMPROVEMENT":
            "SPLIT-CAP-E2-CI",
        "E3_VISION:REGRESSION_REPAIR":
            "SPLIT-CAP-E3-RR",
        "E3_VISION:CONSTRAINED_IMPROVEMENT":
            "SPLIT-CAP-E3-CI",
        "open CNN-family authorized Internal qualification":
            "SPLIT-INT-CNN",
        "open Transformer-family authorized Internal qualification":
            "SPLIT-INT-TRANSFORMER",
        "combined Behavioral plus authorized Internal qualification":
            "SPLIT-COMBINED-BI",
    }

    if task5_bindings != expected_task5_bindings:
        errors.append(
            "Task 5 capability qualification "
            "split bindings have drifted"
        )

    task5_body = section_body(
        spec_text,
        41,
        "Task 5 Capability Qualification Split Bindings",
    )

    require_semantics(
        errors,
        task5_body,
        "Task 5 split-binding semantics",
        (
            "do not establish that any Task 5 capability is",
            "`QUALIFIED_SUPPORTED`",
            "concrete `SystemVersion`",
            "concrete `SplitVersion`",
            "concrete partition membership",
            "all other Task 5 qualification requirements",
        ),
    )

    # ---------------------------------------------------------
    # Validation / role-purpose semantic direction.
    # ---------------------------------------------------------

    validation_body = section_body(
        spec_text,
        7,
        "VALIDATION Semantics",
    )

    require_semantics(
        errors,
        validation_body,
        "validation candidate-selection boundary semantics",
        (
            "validation evidence may be used for",
            "candidate selection",
            "the partition is not protected evidence for that candidate lineage",
            "must not be silently promoted to `PROTECTED`",
        ),
    )

    role_purpose_body = section_body(
        spec_text,
        10,
        "Role And Purpose Are Separate Axes",
    )

    require_semantics(
        errors,
        role_purpose_body,
        "role-purpose separation semantics",
        (
            "A split contract must record both",
            "`PartitionRole`",
            "`PartitionPurpose`",
            "The same purpose may exist under different roles",
            "The same role may serve different purposes",
            "Purpose must not be inferred from role",
        ),
    )

    # ---------------------------------------------------------
    # Evidence identity and independence.
    # ---------------------------------------------------------

    partition_identity_body = section_body(
        spec_text,
        13,
        "PartitionIdentity",
    )

    require_semantics(
        errors,
        partition_identity_body,
        "PartitionIdentity membership semantics",
        (
            "stable `PartitionIdentity`",
            "Changing membership does not silently preserve the same partition identity",
            "material membership change requires a new `SplitVersion` or new partition identity",
        ),
    )

    evaluation_unit_body = section_body(
        spec_text,
        14,
        "EvaluationUnit",
    )

    require_semantics(
        errors,
        evaluation_unit_body,
        "EvaluationUnit semantics",
        (
            "smallest governed unit",
            "declared before protected results",
            "Repeated observations",
            "Resampling one unit",
            "different random seed",
            "do not create new independent units",
        ),
    )

    require_semantics(
        errors,
        evaluation_unit_body,
        "evaluation-unit anti-pseudoreplication semantics",
        (
            "Repeated observations from one evaluation unit do not create new independent units merely by repetition",
            "Resampling one unit does not create another independent unit",
            "Rerunning one unit with a different random seed does not create another independent unit unless",
        ),
    )

    independence_body = section_body(
        spec_text,
        15,
        "IndependenceGroup",
    )

    require_semantics(
        errors,
        independence_body,
        "IndependenceGroup semantics",
        (
            "share a dependency",
            "different governed independence groups",
            "basis for that separation",
            "does not manufacture independence",
        ),
    )

    provenance_body = section_body(
        spec_text,
        17,
        "Membership And Provenance",
    )

    require_semantics(
        errors,
        provenance_body,
        "membership provenance semantics",
        (
            "exact duplicates",
            "derived copies",
            "near duplicates",
            "common-source leakage",
            "Hash inequality alone does not prove independence",
            "transformed copy of protected evidence remains derived",
        ),
    )

    # ---------------------------------------------------------
    # Protected freeze, lifecycle, access, and freshness.
    # ---------------------------------------------------------

    freeze_body = section_body(
        spec_text,
        18,
        "Protected Contract Freeze",
    )

    require_semantics(
        errors,
        freeze_body,
        "protected freeze semantics",
        (
            "Before a protected partition may produce evidence",
            "candidate identity or candidate-binding rule",
            "Protected membership must not be selected after",
            "Independence boundaries must not be redefined",
            "failed protected result must not be converted into `PASS`",
            EXPECTED_EVIDENCE_CONSEQUENCE,
        ),
    )

    protected_body = section_body(
        spec_text,
        8,
        "PROTECTED Semantics",
    )

    require_semantics(
        errors,
        protected_body,
        "PROTECTED semantics",
        (
            "must not be used to tune the candidate",
            "frozen split version",
            "controlled outcome access",
            "Input visibility must therefore be declared separately from outcome visibility",
        ),
    )

    sealed_body = section_body(
        spec_text,
        21,
        "SEALED State",
    )

    require_semantics(
        errors,
        sealed_body,
        "protected sealing semantics",
        (
            "withheld from unauthorized candidate-producing or tuning processes",
            "target labels",
            "aggregate protected scores",
            "per-case protected scores",
            "derived artifacts that reveal protected outcomes",
            "auditable outcome-access separation",
        ),
    )

    candidate_body = section_body(
        spec_text,
        22,
        "Candidate Freeze",
    )

    require_semantics(
        errors,
        candidate_body,
        "candidate freeze semantics",
        (
            "frozen sufficiently",
            "prevent protected outcomes from being tuned",
            "material candidate change",
            "new candidate identity",
            "must not be silently transferred",
        ),
    )

    evaluating_body = section_body(
        spec_text,
        23,
        "EVALUATING State",
    )

    require_semantics(
        errors,
        evaluating_body,
        "protected evaluation semantics",
        (
            "must not be returned to the candidate-producing path",
            "must not be used for interactive tuning",
            "access events must be recorded",
            "does not authorize receiving its protected expected outcome",
        ),
    )

    disclosure_body = section_body(
        spec_text,
        24,
        "DISCLOSED State",
    )

    require_semantics(
        errors,
        disclosure_body,
        "protected disclosure semantics",
        (
            "does not retroactively invalidate",
            "valid historical evidence",
            "not automatically fresh protected evidence",
            "descendant candidate",
            "same frozen candidate",
        ),
    )

    access_body = section_body(
        spec_text,
        25,
        "ProtectedAccessEvent",
    )

    require_semantics(
        errors,
        access_body,
        "ProtectedAccessEvent semantics",
        (
            "candidate lineage affected",
            "whether outcome information was exposed",
            "resulting contamination assessment",
            "Deleting access history does not restore freshness",
            "unrecorded material access",
        ),
    )

    peeking_body = section_body(
        spec_text,
        28,
        "Repeated Protected Peeking",
    )

    require_semantics(
        errors,
        peeking_body,
        "repeated protected peeking semantics",
        (
            "Repeated inspection of protected outcomes is not free evidence",
            "score probing",
            "adaptive querying",
            "allowed evaluation count or stopping rule",
            "when freshness is exhausted",
            "reporting only the best result",
            "preregistered governed protocol",
        ),
    )

    require_semantics(
        errors,
        peeking_body,
        "protected best-of-many semantics",
        (
            "Trying many candidates against one protected split",
            "reporting only the best result is not a valid single protected evaluation",
            "unless that selection process was itself part of the preregistered governed protocol",
        ),
    )

    freshness_body = section_body(
        spec_text,
        30,
        "Fresh Protected Evidence",
    )

    require_semantics(
        errors,
        freshness_body,
        "protected freshness semantics",
        (
            "relative to a governed candidate lineage and claim",
            "candidate construction",
            "selection",
            "tuning",
            "adaptation",
            "claim selection",
            "physically new file is not necessarily fresh evidence",
            "copied, transformed, resampled, or re-encoded descendant",
        ),
    )

    require_semantics(
        errors,
        freshness_body,
        "freshness descendant-inheritance invariant",
        (
            "A copied, transformed, resampled, or re-encoded descendant of exposed protected evidence inherits the relevant exposure unless a governed analysis establishes otherwise",
        ),
    )

    # ---------------------------------------------------------
    # Contamination and invalidation.
    # ---------------------------------------------------------

    require_semantics(
        errors,
        contamination_body,
        "contamination semantics",
        (
            "`CLEAN` requires",
            "`SUSPECTED`",
            "`CONFIRMED`",
            "`UNKNOWN`",
            "must not be silently represented as `CLEAN`",
            "`BLOCKED` or `INVALID`",
        ),
    )

    invalidation_body = section_body(
        spec_text,
        29,
        "Invalidation And Split Revision",
    )

    require_semantics(
        errors,
        invalidation_body,
        "split invalidation semantics",
        (
            "confirmed outcome leakage",
            "protected-case tuning",
            "false independence",
            "unauthorized protected access",
            "hidden target-specific adaptation",
            "original split version",
            "original result",
            "does not erase the invalid result",
            EXPECTED_EVIDENCE_CONSEQUENCE,
        ),
    )

    # ---------------------------------------------------------
    # N-H1.
    # ---------------------------------------------------------

    nh1_body = section_body(
        spec_text,
        31,
        "N-H1 Split Binding",
    )

    require_semantics(
        errors,
        nh1_body,
        "N-H1 split binding",
        (
            "`SPLIT-NH1-DECISION`",
            "protected `PRIMARY_OUTCOME` evidence",
            "at least two protected governed `EvaluationUnit` values",
            "candidate freeze",
            "independent verification",
            "exact decision behavior claimed",
        ),
    )

    require_semantics(
        errors,
        nh1_body,
        "N-H1 behavior-scope invariant",
        (
            "Evidence for one behavior must not silently establish another",
        ),
    )

    nh1_independence = section_body(
        spec_text,
        32,
        "N-H1 Independent Evaluation Units",
    )

    require_semantics(
        errors,
        nh1_independence,
        "N-H1 independence semantics",
        (
            "at least two protected `EvaluationUnit` identities",
            "different applicable `IndependenceGroup` values",
            "another random seed",
            "another bootstrap sample",
            "another resampling",
            "another run of the same system version",
            "transformed copy",
            "cannot satisfy the two-unit scientific gate",
        ),
    )

    nh1_development_body = section_body(
        spec_text,
        33,
        "N-H1 Development And Validation Use",
    )

    require_semantics(
        errors,
        nh1_development_body,
        "N-H1 validation-freshness invariant",
        (
            "Validation results used to choose the final Native candidate must not later be reported as fresh protected evidence for that candidate",
        ),
    )

    # ---------------------------------------------------------
    # N-H2.
    # ---------------------------------------------------------

    nh2_body = section_body(
        spec_text,
        34,
        "N-H2 Split Binding",
    )

    require_semantics(
        errors,
        nh2_body,
        "N-H2 split binding",
        (
            "`SPLIT-NH2-XFAM`",
            "`TRANSFER_SOURCE`",
            "`TRANSFER_TARGET`",
            "learned Native decision mechanism",
            "do not by themselves count as transferred learned capability",
            "predeclared before protected target outcomes",
        ),
    )

    boundaries = parse_nh2_boundaries(
        spec_text
    )

    if boundaries != EXPECTED_NH2_BOUNDARIES:
        errors.append(
            "N-H2 leave-one-family-out boundary "
            "registry must contain exactly the frozen "
            "E1, E2, and E3 protected target boundaries"
        )

    nh2_boundaries_body = section_body(
        spec_text,
        35,
        "N-H2 Leave-One-Family-Out Boundaries",
    )

    require_semantics(
        errors,
        nh2_boundaries_body,
        "N-H2 anti-cherry-picking semantics",
        (
            "predeclare its primary boundary",
            "multiplicity handling is declared",
            "not selected post hoc",
            "failed and negative boundaries remain preserved",
            "reporting only the most favorable one is not valid evidence",
            "do not establish universal Native transfer",
        ),
    )

    nh2_leakage_body = section_body(
        spec_text,
        36,
        "N-H2 Transfer Leakage Controls",
    )

    require_semantics(
        errors,
        nh2_leakage_body,
        "N-H2 leakage semantics",
        (
            "must not use protected target outcomes",
            "target-specific authored investigation strategy",
            "hidden target-specific adaptation",
            "retrieval of protected target examples",
            "evaluator feedback returned during candidate construction",
            "source/target duplicates or derived cases",
            "protected target-outcome tuning",
            "invalid for the claimed held-out transfer evidence",
        ),
    )

    require_semantics(
        errors,
        nh2_leakage_body,
        "N-H2 target-outcome prohibition invariant",
        (
            "The central prohibition is protected target-outcome tuning",
            "If protected target outcomes materially influence the transferred mechanism before protected evaluation, the affected `N-H2` result is invalid for the claimed held-out transfer evidence",
        ),
    )

    # ---------------------------------------------------------
    # A-H1.
    # ---------------------------------------------------------

    ah1_body = section_body(
        spec_text,
        37,
        "A-H1 Split Binding",
    )

    require_semantics(
        errors,
        ah1_body,
        "A-H1 split binding",
        (
            "`SPLIT-AH1-ADAPT`",
            "`ADAPTATION_INPUT`",
            "protected `PRIMARY_OUTCOME` evidence",
            "protected `CRITICAL_INVARIANT` evidence",
            "pre-adaptation candidate state",
            "frozen post-adaptation candidate identity",
            "protected outcome sealing",
            "independent evaluation",
        ),
    )

    ah1_separation = section_body(
        spec_text,
        38,
        "A-H1 Adaptation Input And Protected Outcome Separation",
    )

    require_semantics(
        errors,
        ah1_separation,
        "A-H1 separation semantics",
        (
            "Protected target outcomes must not be returned to the adapting mechanism",
            "before the post-adaptation candidate is frozen",
            "protected aggregate scores",
            "protected per-case scores",
            "protected invariant failures",
            "invalid for `A-H1`",
            "fresh or otherwise valid split contract",
        ),
    )

    # ---------------------------------------------------------
    # A-H2.
    # ---------------------------------------------------------

    ah2_body = section_body(
        spec_text,
        39,
        "A-H2 Split Binding",
    )

    require_semantics(
        errors,
        ah2_body,
        "A-H2 split binding",
        (
            "`SPLIT-AH2-RETENTION`",
            "`PRIOR_CAPABILITY`",
            "`LOCALITY`",
            "`CRITICAL_INVARIANT`",
            "pre-adaptation state",
            "post-adaptation state",
            "rollback target",
            "post-rollback state",
            "independent verification",
            "distinct from `A-H1` evidence",
        ),
    )

    ah2_paired = section_body(
        spec_text,
        40,
        "A-H2 Paired Pre/Post/Rollback Evaluation",
    )

    require_semantics(
        errors,
        ah2_paired,
        "A-H2 paired-evaluation semantics",
        (
            "same governed protected `EvaluationUnit`",
            "does not by itself create three independent evaluation units",
            "same declared unit",
            "`IndependenceGroup`",
            "raw pre-adaptation outcomes",
            "raw post-adaptation outcomes",
            "raw post-rollback outcomes",
            "must not be fed back into the adapting mechanism",
            "Rollback success requires actual execution",
            "description of rollback is not a rollback evaluation",
        ),
    )

    # ---------------------------------------------------------
    # Environment-family grouping.
    # ---------------------------------------------------------

    family_body = section_body(
        spec_text,
        43,
        "Environment-Family Partitioning Rules",
    )

    require_semantics(
        errors,
        family_body,
        "environment-family partition semantics",
        (
            "`E1_AGENT`",
            "scenario-generation lineage",
            "`E2_STRUCTURED_ML`",
            "entity or subject identity",
            "temporal boundary",
            "`E3_VISION`",
            "capture session",
            "near-duplicate image family",
            "random record-level split is invalid",
            "No fixed percentage such as 80/10/10 is universally mandated",
        ),
    )

    # ---------------------------------------------------------
    # Independent verification and Task 8/9 ownership.
    # ---------------------------------------------------------

    verification_body = section_body(
        spec_text,
        44,
        "Independent Verification And Authority Separation",
    )

    require_semantics(
        errors,
        verification_body,
        "independent verification semantics",
        (
            "does not replace `VerificationReport`",
            "process producing the candidate cannot manipulate",
            "same frozen candidate",
            "does not authorize iterative candidate tuning",
        ),
    )

    task8_body = section_body(
        spec_text,
        45,
        "Task 8 Baseline Handoff",
    )

    require_semantics(
        errors,
        task8_body,
        "Task 8 ownership semantics",
        (
            "Task 8 retains ownership",
            "implementation",
            "identity",
            "version",
            "configuration",
            "strongest matched baseline",
            "before applicable protected outcomes",
            "must not select a weak baseline",
        ),
    )

    task9_body = section_body(
        spec_text,
        46,
        "Task 9 Cost And Resource Handoff",
    )

    require_semantics(
        errors,
        task9_body,
        "Task 9 ownership semantics",
        (
            "Task 9 retains ownership",
            "compute-cost fields",
            "engineering-effort fields",
            "adaptation-cost fields",
            "Task 7 does not define the accounting values",
            "resource-binding rule must be frozen",
        ),
    )

    # ---------------------------------------------------------
    # Change control.
    # ---------------------------------------------------------

    change_body = section_body(
        spec_text,
        47,
        "Change Control And Evidence Consequence",
    )

    require_semantics(
        errors,
        change_body,
        "Task 7 change-control semantics",
        (
            "material split change requires governed revision",
            "protected membership",
            "independence-group boundary",
            "protected-access policy",
            "transfer target boundary",
            "adaptation-input/protected-outcome separation",
            "Historical evidence must retain the exact `SplitVersion`",
            EXPECTED_EVIDENCE_CONSEQUENCE,
        ),
    )

    extension_body = section_body(
        spec_text,
        48,
        "Governed Extension",
    )

    require_semantics(
        errors,
        extension_body,
        "Task 7 governed-extension semantics",
        (
            "three-value `PartitionRole` vocabulary",
            "seven-value `PartitionPurpose` vocabulary",
            "protected lifecycle vocabulary",
            "contamination-state vocabulary",
            "initial `N-H2` transfer-boundary semantics",
            "Instantiating a concrete `SplitVersion`",
            "does not by itself require a new Task 7 governance decision",
            "material semantic change requires Decision Governance",
        ),
    )

    # ---------------------------------------------------------
    # Qualification contract.
    # ---------------------------------------------------------

    qualification_body = section_body(
        spec_text,
        49,
        "Task 7 Qualification Contract",
    )

    errors.extend(
        validate_condition_semantics(
            qualification_body
        )
    )

    require_semantics(
        errors,
        qualification_body,
        "Task 7 qualification execution",
        (
            "structural validation",
            "semantic validation",
            "decision/register synchronization",
            "adversarial mutation qualification",
            "regression qualification for Tasks 1 through 6",
            "development-state qualification",
            "final accepted-state qualification",
            "must not be weakened merely to obtain a passing result",
        ),
    )

    principle_body = section_body(
        spec_text,
        50,
        "Split Protocol Principle",
    )

    require_semantics(
        errors,
        principle_body,
        "Task 7 final principle",
        (
            "not by a file name",
            "Development evidence may help create candidates",
            "Validation evidence may help choose candidates",
            "Protected evidence exists to test a frozen claim",
            "Negative evidence remains evidence",
            "Invalid evidence remains preserved",
            "new partition does not erase an old result",
            "Tasks 8 and 9 still determine baseline and resource bindings",
            "Actual experiments must still earn their outcomes",
        ),
    )

    # ---------------------------------------------------------
    # Decision 0008 semantics.
    # ---------------------------------------------------------

    decision_body = unnumbered_section_body(
        decision_text,
        "Decision",
    )

    require_semantics(
        errors,
        decision_body,
        "Decision 0008 semantics",
        (
            "docs/mvp/07-initial-splits.md",
            "`DEVELOPMENT`",
            "`VALIDATION`",
            "`PROTECTED`",
            "`PRIMARY_OUTCOME`",
            "`TRANSFER_TARGET`",
            "`ADAPTATION_INPUT`",
            "`PRIOR_CAPABILITY`",
            "`SplitPlan`",
            "`SplitVersion`",
            "`EvaluationUnit`",
            "`IndependenceGroup`",
            "Acceptance does not establish scientific support",
            "does not promote any Task 5 capability",
            "`QUALIFIED_SUPPORTED`",
            "not research implementation authority",
        ),
    )

    research_impact = unnumbered_section_body(
        decision_text,
        "Research Impact",
    )

    require_semantics(
        errors,
        research_impact,
        "Decision 0008 research impact",
        (
            "`CROSS_PROGRAM`",
            "`DATA`",
            "`RERUN_AND_PRESERVE_DATA_DISTINCTIONS`",
            "Native and Adaptive research",
            "historical and revised data partitions",
        ),
    )

    decision_qualification = unnumbered_section_body(
        decision_text,
        "Qualification Requirement",
    )

    require_semantics(
        errors,
        decision_qualification,
        "Decision 0008 qualification requirement",
        (
            "development, validation, and protected role semantics",
            "evaluation units and independence groups",
            "prevents repeated runs or resampling from manufacturing independence",
            "prevents protected-result tuning",
            "governs Native held-out transfer",
            "governs Adaptive input/evaluation separation",
            "passes adversarial mutation qualification",
            "must not be represented as scientific support",
        ),
    )

    # ---------------------------------------------------------
    # Task 7 generalized contradiction defense.
    #
    # Positive requirements are not sufficient by themselves.
    # A section must also remain free of language that grants
    # authority for the opposite relationship.
    # ---------------------------------------------------------

    forbid_semantic_patterns(
        errors,
        ah1_body,
        "A-H1 input/outcome separation",
        (
            r"\b(?:may|can|allowed|permitted)\b.{0,100}"
            r"\b(?:merge|combine|collapse|mix)\b.{0,120}"
            r"\badaptation input\b.{0,120}\bprotected outcome",
            r"\b(?:merge|combine|collapse|mix)\b.{0,120}"
            r"\bprotected outcome\b.{0,120}\badaptation input",
        ),
    )

    forbid_semantic_patterns(
        errors,
        ah1_separation,
        "A-H1 protected-outcome feedback",
        (
            r"\bprotected\b.{0,80}"
            r"\b(?:score|scores|label|labels|outcome|outcomes|"
            r"invariant failure|invariant failures|expected output|"
            r"expected outputs)\b.{0,120}"
            r"\b(?:may|can|allowed|permitted)\b.{0,80}"
            r"\b(?:adaptation input|returned|fed back|feedback)\b",
            r"\b(?:may|can|allowed|permitted)\b.{0,100}"
            r"\bprotected\b.{0,80}"
            r"\b(?:score|scores|label|labels|outcome|outcomes)\b"
            r".{0,120}\badaptation input\b",
            r"\b(?:leakage|protected outcome information)\b"
            r".{0,160}\b(?:valid|accepted|preserve)\b"
            r".{0,80}\b(?:a-h1|result)\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        ah1_separation,
        "A-H1 leakage-validity permission invariant",
        (
            r"\b(?:leakage|protected outcome|protected outcomes|protected outcome information)\b",
            r"\b(?:a-h1|result)\b",
            r"\b(?:valid|preserve|preserved|accept|accepted)\b",
        ),
    )

    forbid_semantic_patterns(
        errors,
        ah2_paired,
        "A-H2 paired-observation independence",
        (
            r"\b(?:pre-adaptation|preadaptation)\b.{0,160}"
            r"\b(?:post-adaptation|postadaptation)\b.{0,160}"
            r"\b(?:post-rollback|postrollback)\b.{0,160}"
            r"\b(?:three|3)\b.{0,80}\bindependent\b",
            r"\bsame\b.{0,100}\b(?:evaluation unit|unit)\b"
            r".{0,160}\b(?:may|can|allowed|permitted)\b"
            r".{0,100}\bindependent\b",
        ),
    )

    forbid_semantic_patterns(
        errors,
        ah2_paired,
        "A-H2 rollback-execution integrity",
        (
            r"\b(?:description|documentation|plan|specification)\b"
            r".{0,100}\brollback\b.{0,100}"
            r"\b(?:may|can|allowed|permitted|sufficient)\b"
            r".{0,100}\b(?:substitute|replace|stand in|count as)\b",
            r"\b(?:may|can|allowed|permitted)\b.{0,100}"
            r"\b(?:description|documentation)\b.{0,100}"
            r"\b(?:rollback evaluation|rollback execution)\b",
        ),
    )

    forbid_semantic_patterns(
        errors,
        task5_body,
        "Task 5 capability-promotion integrity",
        (
            r"\b(?:splitplan|split plan|split-plan)\b.{0,160}"
            r"\b(?:alone|itself|sufficient)\b.{0,120}"
            r"\bqualified_supported\b",
            r"\b(?:possession|existence)\b.{0,100}"
            r"\b(?:splitplan|split plan|split-plan)\b.{0,160}"
            r"\b(?:promote|qualify|establish)\b.{0,100}"
            r"\bqualified_supported\b",
        ),
    )

    forbid_semantic_patterns(
        errors,
        family_body,
        "environment-family grouped-leakage integrity",
        (
            r"\brandom record-level split"
            r".{0,160}\b(?:acceptable|allowed|valid|permitted)\b"
            r".{0,160}\b(?:grouped|group)\b"
            r".{0,120}\b(?:leak|leakage|crosses|cross)\b",
            r"\b(?:acceptable|allowed|valid|permitted)\b"
            r".{0,100}\brandom record-level"
            r".{0,180}\b(?:dependency|leak|leakage)\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        verification_body,
        "independent-verification authority separation",
        (
            r"\bcandidate-producing\b",
            r"\b(?:"
            r"alter|modify|manipulate|curate|rewrite|"
            r"rotate|approve|approval|"
            r"retain|retains|retained|retaining|"
            r"control|controls|controlled|controlling|"
            r"administer|administers|administered|administering|"
            r"delegate|delegates|delegated|delegating|"
            r"pre-filter|prefilter|filter|filters|filtered|"
            r"withhold|withholds|withheld|"
            r"deliver|delivers|delivered"
            r")\b",
            r"\b(?:"
            r"protected evidence|verification evidence|"
            r"protected verification evidence|"
            r"verification artifact|verification artifacts|"
            r"write credential|write credentials|"
            r"verifier credential|verifier credentials|"
            r"authorization policy|service account|"
            r"verification findings|certification record|"
            r"verification record|certification approval"
            r")\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        verification_body,
        "verification-replay anti-tuning integrity",
        (
            r"\breplay\b",
            r"\biterative\b",
            r"\b(?:tuning|adaptation)\b",
        ),
    )

    forbid_semantic_patterns(
        errors,
        task8_body,
        "baseline anti-gaming integrity",
        (
            r"\b(?:may|can|allowed|permitted)\b.{0,100}"
            r"\b(?:weak|weaker|inferior)\b.{0,80}\bbaseline\b"
            r".{0,160}\b(?:advantage|improve|better|clearer)\b",
            r"\b(?:weak|weaker|inferior)\b.{0,80}\bbaseline\b"
            r".{0,160}\b(?:candidate advantage|apparent result)\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        task9_body,
        "resource-accounting anti-gaming integrity",
        (
            r"\b(?:"
            r"after|once|later|post(?:-result)?|"
            r"protected results?|observed results?|evaluation results?"
            r")\b",
            r"\b(?:"
            r"accounting|resource|resources|cost|costs|"
            r"window|windows|boundary|boundaries|policy"
            r")\b",
            r"\b(?:"
            r"choose|chooses|chosen|select|selected|"
            r"adjust|change|changed|"
            r"revis(?:e|es|ed|ing)|"
            r"redefine|redefined|"
            r"exclude|narrow|filter|remove"
            r")\w*\b",
            r"\b(?:"
            r"result|results|outcome|outcomes|budget|"
            r"pass|passing|advantage|efficiency|favorable"
            r")\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        task9_body,
        "resource-accounting protected-result permission invariant",
        (
            r"\bresource accounting\b",
            r"\b(?:redefine|redefined|change|changed|adjust|adjusted)\b",
            r"\b(?:protected result|protected results|observed result|observed results)\b",
            r"\b(?:pass|passing|advantage)\b",
        ),
    )

    forbid_permissive_relationship(
        errors,
        spec_text,
        "historical-manifest preservation",
        (
            r"\b(?:"
            r"successor|predecessor|splitversion|"
            r"copy|copied|renam(?:e|ed|ing)"
            r")\b",
            r"\b(?:"
            r"overwrite|omit|omits|omitted|"
            r"drop|drops|dropped|discard|discarded|"
            r"erase|erased|restart|restarts|restarted|"
            r"reset|resets|detach|detaches|detached"
            r")\b",
            r"\b(?:"
            r"manifest|history|invalidation|contamination|"
            r"access|result|results|outcome|outcomes"
            r")\b",
        ),
    )

    forbid_semantic_patterns(
        errors,
        decision_body,
        "Decision 0008 evidence-boundary integrity",
        (
            r"\bacceptance\b.{0,180}"
            r"\b(?:may|can|allowed|permitted|sufficient)\b"
            r".{0,140}\bscientific\b.{0,80}"
            r"\b(?:evidence|support|proof)\b",
            r"\bacceptance\b.{0,180}"
            r"\b(?:mark|treat|declare)\b.{0,120}"
            r"\b(?:hypothesis|hypotheses)\b.{0,100}"
            r"\b(?:supported|pass|passing)\b",
            r"\b(?:no experiment|without experiment|"
            r"without experimental evidence)\b.{0,160}"
            r"\b(?:supported|scientific support|pass|passing)\b",
        ),
    )

    # ---------------------------------------------------------
    # Prevent governance acceptance from becoming evidence.
    # ---------------------------------------------------------

    forbidden = (
        "task 7 establishes scientific support",
        "decision 0008 establishes scientific support",
        "acceptance proves n-h1",
        "acceptance proves n-h2",
        "acceptance proves a-h1",
        "acceptance proves a-h2",
        "task 7 qualifies all capabilities",
        "task 7 makes capabilities qualified_supported",
        "split protocol proves transfer",
        "split protocol proves adaptation",
    )

    spec_semantic = semantic_text(
        spec_text
    )

    decision_semantic = semantic_text(
        decision_text
    )

    for phrase in forbidden:
        normalized_phrase = semantic_text(
            phrase
        )

        if normalized_phrase in spec_semantic:
            errors.append(
                "Task 7 specification improperly "
                "manufactures evidence: "
                f"{phrase}"
            )

        if normalized_phrase in decision_semantic:
            errors.append(
                "Decision 0008 improperly "
                "manufactures evidence: "
                f"{phrase}"
            )

    return errors



def validate_final_qualification_evidence(
    root: Path,
) -> list[str]:
    """
    Validate the accepted Task 7 governance-evidence state.

    This validates governance qualification only. It must not
    manufacture scientific support or Task 5 capability support.
    """

    errors: list[str] = []

    qualification_path = (
        root / QUALIFICATION_RELATIVE
    )

    decision_path = (
        root / DECISION_RELATIVE
    )

    spec_path = (
        root / SPEC_RELATIVE
    )

    qualification_text = (
        qualification_path.read_text()
    )

    decision_text = (
        decision_path.read_text()
    )

    spec_text = (
        spec_path.read_text()
    )

    qualification_metadata = parse_metadata(
        qualification_text
    )

    spec_metadata = parse_metadata(
        spec_text
    )

    # -----------------------------------------------------
    # Qualification identity.
    # -----------------------------------------------------

    expected_heading = (
        "# Decision 0008 Qualification Record"
    )

    first_line = (
        qualification_text.splitlines()[0]
        if qualification_text.splitlines()
        else ""
    )

    if first_line != expected_heading:
        errors.append(
            "Decision 0008 qualification heading mismatch"
        )

    expected_metadata = {
        "Task":
            "7 / 100",
        "Decision":
            EXPECTED_DECISION_ID,
        "Decision Key":
            EXPECTED_DECISION_KEY,
        "Result":
            "PASS",
        "Qualification state":
            "VERIFIED",
        "Specification":
            "docs/mvp/07-initial-splits.md",
        "Specification version":
            EXPECTED_FINAL_VERSION,
        "Validator":
            "scripts/check_initial_splits.py",
        "Mutation suite":
            "tests/qualification/test_initial_splits.py",
        "Qualification conditions":
            "50 / 50",
        "Mutation result":
            "68 / 68",
        "Execution authority":
            EXPECTED_EXECUTION_AUTHORITY,
        "Long-term authority":
            EXPECTED_LONG_TERM_AUTHORITY,
        "Task 1 regression":
            "PASS",
        "Task 2 regression":
            "PASS",
        "Task 3 regression":
            "PASS",
        "Task 4 regression":
            "PASS",
        "Task 5 regression":
            "PASS",
        "Task 6 regression":
            "PASS",
        "Diff check":
            "PASS",
        "Scientific support established":
            "NO",
        "Task 5 capability support promoted":
            "NO",
        "Final accepted-state qualification":
            "PASS",
    }

    for key, expected in expected_metadata.items():
        actual = qualification_metadata.get(
            key
        )

        if actual != expected:
            errors.append(
                "Decision 0008 qualification metadata "
                f"{key!r} must be {expected!r}"
            )

    # The qualification record and the actual governed
    # specification must describe the same final version.
    qualification_spec_version = (
        qualification_metadata.get(
            "Specification version",
            "",
        )
    )

    actual_spec_version = (
        spec_metadata.get(
            "Version",
            "",
        )
    )

    if (
        qualification_spec_version
        != actual_spec_version
    ):
        errors.append(
            "Decision 0008 qualification specification "
            "version must match the Task 7 specification"
        )

    # -----------------------------------------------------
    # Qualification date.
    #
    # Validity is enforced without hard-coding one calendar
    # date so a later governed requalification can carry its
    # own truthful date.
    # -----------------------------------------------------

    qualification_date = (
        qualification_metadata.get(
            "Date",
            "",
        )
    )

    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}",
        qualification_date,
    ):
        errors.append(
            "Decision 0008 qualification Date must use "
            "valid YYYY-MM-DD format"
        )

    else:
        try:
            date.fromisoformat(
                qualification_date
            )

        except ValueError:
            errors.append(
                "Decision 0008 qualification Date must "
                "be a valid calendar date"
            )

    # -----------------------------------------------------
    # Required evidence sections.
    # -----------------------------------------------------

    expected_sections = (
        "Scope",
        "Positive Qualification",
        "Adversarial Qualification",
        "Authority And Regression Qualification",
        "Evidence Interpretation",
        "Acceptance Decision",
    )

    for heading in expected_sections:
        if not unnumbered_section_body(
            qualification_text,
            heading,
        ):
            errors.append(
                "Decision 0008 qualification missing "
                f"or empty section: {heading}"
            )

    scope_body = unnumbered_section_body(
        qualification_text,
        "Scope",
    )

    require_semantics(
        errors,
        scope_body,
        "Decision 0008 qualification scope",
        (
            "does not establish scientific support",
            "does not promote any Task 5 capability",
            "`QUALIFIED_SUPPORTED`",
        ),
    )

    adversarial_body = unnumbered_section_body(
        qualification_text,
        "Adversarial Qualification",
    )

    require_semantics(
        errors,
        adversarial_body,
        "Decision 0008 adversarial qualification",
        (
            "68 / 68",
            "52 / 52",
            "16 / 16",
        ),
    )

    regression_body = unnumbered_section_body(
        qualification_text,
        "Authority And Regression Qualification",
    )

    require_semantics(
        errors,
        regression_body,
        "Decision 0008 regression qualification",
        (
            "Tasks 1 through 6 regression qualification",
            "PASS",
            "Development-state qualification",
            "Final accepted-state qualification",
        ),
    )

    interpretation_body = unnumbered_section_body(
        qualification_text,
        "Evidence Interpretation",
    )

    require_semantics(
        errors,
        interpretation_body,
        "Decision 0008 evidence interpretation",
        (
            "P1",
            "22 / 24",
            "Set D",
            "21 / 32",
            "do not rewrite",
            "Scientific support established",
            "NO",
            "Task 5 capability support promoted",
        ),
    )

    acceptance_body = unnumbered_section_body(
        qualification_text,
        "Acceptance Decision",
    )

    require_semantics(
        errors,
        acceptance_body,
        "Decision 0008 acceptance evidence",
        (
            "Decision 0008",
            "`ACCEPTED`",
            "1.0.0",
            "`Qualified`",
            "Final accepted-state qualification",
            "PASS",
        ),
    )

    # -----------------------------------------------------
    # Decision implementation / verification evidence.
    # -----------------------------------------------------

    implementation_body = unnumbered_section_body(
        decision_text,
        "Implementation Evidence",
    )

    verification_body = unnumbered_section_body(
        decision_text,
        "Verification Evidence",
    )

    if semantic_text(
        implementation_body
    ) in {
        "",
        "pending",
    }:
        errors.append(
            "Decision 0008 final state requires "
            "implemented Implementation Evidence"
        )

    else:
        require_semantics(
            errors,
            implementation_body,
            "Decision 0008 implementation evidence",
            (
                "Implemented",
                "Task 7",
                "split governance",
                "qualification validators",
                "structured qualification data",
                "preserved evidence",
                "Decision 0008",
            ),
        )

    if semantic_text(
        verification_body
    ) in {
        "",
        "pending",
    }:
        errors.append(
            "Decision 0008 final state requires "
            "verified Verification Evidence"
        )

    else:
        require_semantics(
            errors,
            verification_body,
            "Decision 0008 verification evidence",
            (
                "Verified",
                "development-state qualification",
                "adversarial mutation qualification",
                "Tasks 1 through 6 regression qualification",
                "structured evidence validation",
                "final accepted-state qualification",
            ),
        )

    return errors

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Hetren Task 7 governed "
            "initial split protocol."
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
            "ACCEPTED Decision 0008, and "
            "qualification evidence"
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
            validate_semantics(
                root
            )
        )

    if errors:
        print(
            "INITIAL SPLITS VALIDATION: FAIL"
        )

        for error in errors:
            print(
                f"- {error}"
            )

        return 1

    spec_metadata = parse_metadata(
        (root / SPEC_RELATIVE).read_text()
    )

    decision_metadata = parse_metadata(
        (root / DECISION_RELATIVE).read_text()
    )

    print(
        "INITIAL SPLITS VALIDATION: PASS"
    )
    print(
        f"- version: {spec_metadata.get('Version')}"
    )
    print(
        f"- status: {spec_metadata.get('Status')}"
    )
    print(
        "- decision: "
        f"{decision_metadata.get('Status')}"
    )
    print(
        f"- numbered sections: {len(SECTION_TITLES)}"
    )
    print(
        "- Task 7 qualification conditions: 50"
    )
    print(
        "- partition roles: "
        + ", ".join(
            EXPECTED_PARTITION_ROLES
        )
    )
    print(
        "- partition purposes: "
        + ", ".join(
            EXPECTED_PARTITION_PURPOSES
        )
    )
    print(
        "- protected lifecycle states: "
        + ", ".join(
            EXPECTED_LIFECYCLE_STATES
        )
    )
    print(
        "- contamination states: "
        + ", ".join(
            EXPECTED_CONTAMINATION_STATES
        )
    )
    print(
        f"- initial SplitPlans: {len(EXPECTED_SPLIT_PLANS)}"
    )
    print(
        f"- N-H2 transfer boundaries: "
        f"{len(EXPECTED_NH2_BOUNDARIES)}"
    )
    print(
        "- evidence consequence: "
        f"{EXPECTED_EVIDENCE_CONSEQUENCE}"
    )
    print(
        "- scientific support established by "
        "Task 7 specification: NO"
    )
    print(
        "- Task 5 capability support promoted by "
        "Task 7 specification: NO"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

