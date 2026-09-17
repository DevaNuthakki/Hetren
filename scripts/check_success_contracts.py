#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


OUTCOMES = (
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
    "BLOCKED",
    "INVALID",
)

SECTION_TITLES = (
    "Purpose",
    "Authority And Scope",
    "No Parallel SuccessContract Runtime Object",
    "Three Independent Success Planes",
    "Required GoalContract Semantics",
    "Evaluation Outcome Vocabulary",
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
    "BLOCKED",
    "INVALID",
    "Evidence-Validity Gate",
    "Baseline Semantics",
    "Protected Criteria And Threshold Freeze",
    "Hard Constraints And Invariants",
    "Budget Semantics",
    "Regression Repair Success",
    "Constrained Improvement Success",
    "Product Success",
    "Native Intelligence Research Success",
    "Adaptive Intelligence Scientific Success",
    "Transfer Claims",
    "E1, E2, And E3 Applicability",
    "Independent Verification",
    "Claim Narrowing And Honest Status",
    "Deferred Concrete Artifacts",
    "Relationship To Release And Completion",
    "Task 3 Qualification Contract",
    "Success-Contract Principle",
)

EXPECTED_SPEC_METADATA = {
    "MVP Task": "3 / 100",
    "Execution authority": "AUTH-HETREN-MVP-3.0",
    "Long-term authority": "AUTH-HETREN-MASTER-2.0",
    "Governing decision": "0003",
    "Canonical declaration record": "GoalContract",
    "Canonical measured-outcome record": "EvaluationRecord",
    "Canonical independent-verification record": "VerificationReport",
}

EXPECTED_DECISION_METADATA = {
    "Decision ID": "0003",
    "Decision Key": "evaluation.success-contracts",
    "Title": "Define shared success-contract semantics",
    "Class": "EVALUATION",
    "Authority": "AUTH-HETREN-MVP-3.0",
    "Research Program": "NONE",
    "Research Change Category": "NONE",
    "Evidence Consequence": "NONE",
}

ALLOWED_SPEC_STATUSES = {"Draft", "Requalifying", "Qualified"}
ALLOWED_DECISION_STATUSES = {"PROPOSED", "ACCEPTED"}

SPEC_RELATIVE = Path("docs/mvp/03-success-contracts.md")
DECISION_RELATIVE = Path("docs/decisions/0003-success-contracts.md")
REGISTER_RELATIVE = Path("docs/decisions/register.md")
QUALIFICATION_RELATIVE = Path(
    "docs/decisions/qualification/0003-success-contracts.md"
)


def strip_code(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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


def numbered_sections(text: str) -> list[tuple[int, str]]:
    return [
        (int(number), title.strip())
        for number, title in re.findall(
            r"^## ([0-9]+)\. (.+)$",
            text,
            re.MULTILINE,
        )
    ]


def section_body(text: str, number: int, title: str) -> str:
    marker = f"## {number}. {title}"
    if marker not in text:
        return ""
    body = text.split(marker, 1)[1]
    body = body.split("\n## ", 1)[0]
    return body.strip()


def numbered_conditions(text: str) -> list[int]:
    return [
        int(value)
        for value in re.findall(r"^([0-9]+)\.", text, re.MULTILINE)
    ]


def parse_register_0003(text: str) -> dict[str, str] | None:
    pattern = re.compile(
        r"^\| `0003` \| `(?P<key>[^`]+)` \| "
        r"(?P<title>[^|]+?) \| `(?P<status>[^`]+)` \| "
        r"`(?P<class>[^`]+)` \| `(?P<authority>[^`]+)` \| "
        r"`(?P<record>[^`]+)` \|$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match is None:
        return None
    return {
        key: value.strip()
        for key, value in match.groupdict().items()
    }


def validate_structure(
    root: Path,
    require_qualified: bool = False,
) -> list[str]:
    errors: list[str] = []

    spec_path = root / SPEC_RELATIVE
    decision_path = root / DECISION_RELATIVE
    register_path = root / REGISTER_RELATIVE
    qualification_path = root / QUALIFICATION_RELATIVE

    for path, label in (
        (spec_path, str(SPEC_RELATIVE)),
        (decision_path, str(DECISION_RELATIVE)),
        (register_path, str(REGISTER_RELATIVE)),
    ):
        if not path.is_file():
            errors.append(f"missing {label}")

    if errors:
        return errors

    spec_text = spec_path.read_text()
    decision_text = decision_path.read_text()
    register_text = register_path.read_text()

    if not spec_text.startswith("# Hetren MVP Success Contracts\n"):
        errors.append("success-contract specification heading mismatch")

    spec_metadata = parse_metadata(spec_text)

    version = spec_metadata.get("Version", "")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        errors.append("success-contract Version must be semantic version")

    spec_status = spec_metadata.get("Status", "")
    if spec_status not in ALLOWED_SPEC_STATUSES:
        errors.append(
            f"success-contract Status is invalid: {spec_status!r}"
        )

    for key, expected in EXPECTED_SPEC_METADATA.items():
        actual = spec_metadata.get(key)
        if actual != expected:
            errors.append(
                f"success-contract metadata {key} must be {expected!r}; "
                f"got {actual!r}"
            )

    expected_sections = [
        (number, title)
        for number, title in enumerate(SECTION_TITLES, start=1)
    ]
    actual_sections = numbered_sections(spec_text)

    if actual_sections != expected_sections:
        errors.append(
            "success-contract specification must contain exactly ordered "
            "sections 1 through 29"
        )

    qualification_body = section_body(
        spec_text,
        28,
        "Task 3 Qualification Contract",
    )
    conditions = numbered_conditions(qualification_body)

    if conditions != list(range(1, 41)):
        errors.append(
            "Task 3 qualification contract must contain exactly "
            "conditions 1 through 40"
        )

    outcome_body = section_body(
        spec_text,
        6,
        "Evaluation Outcome Vocabulary",
    )
    declared_outcomes = tuple(
        re.findall(
            r"^- `([A-Z_]+)`$",
            outcome_body,
            re.MULTILINE,
        )
    )

    if declared_outcomes != OUTCOMES:
        errors.append(
            "evaluation outcome vocabulary must be exactly "
            "PASS, FAIL, INCONCLUSIVE, BLOCKED, INVALID"
        )

    expected_decision_heading = (
        "# Decision 0003: Define shared success-contract semantics"
    )
    if expected_decision_heading not in decision_text.splitlines():
        errors.append("Decision 0003 heading mismatch")

    decision_metadata = parse_metadata(decision_text)

    for key, expected in EXPECTED_DECISION_METADATA.items():
        actual = decision_metadata.get(key)
        if actual != expected:
            errors.append(
                f"Decision 0003 metadata {key} must be {expected!r}; "
                f"got {actual!r}"
            )

    decision_status = decision_metadata.get("Status", "")
    if decision_status not in ALLOWED_DECISION_STATUSES:
        errors.append(
            f"Decision 0003 Status is invalid: {decision_status!r}"
        )

    register_row = parse_register_0003(register_text)

    if register_row is None:
        errors.append("decision register missing Decision 0003 row")
    else:
        expected_row = {
            "key": "evaluation.success-contracts",
            "title": "Define shared success-contract semantics",
            "class": "EVALUATION",
            "authority": "AUTH-HETREN-MVP-3.0",
            "record": "0003-success-contracts.md",
        }

        for key, expected in expected_row.items():
            actual = register_row.get(key)
            if actual != expected:
                errors.append(
                    f"Decision 0003 register {key} must be "
                    f"{expected!r}; got {actual!r}"
                )

        if register_row.get("status") != decision_status:
            errors.append(
                "Decision 0003 register status must match record status"
            )

    if require_qualified:
        if spec_status != "Qualified":
            errors.append(
                "success-contract specification must be Qualified"
            )

        if decision_status != "ACCEPTED":
            errors.append(
                "Decision 0003 must be ACCEPTED for final qualification"
            )

        errors.extend(
            validate_qualification_record(
                qualification_path,
                spec_metadata,
            )
        )
        errors.extend(
            validate_final_decision_evidence(decision_text)
        )

    return errors





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
    "Task": "3 / 100",
    "Decision": "0003",
    "Decision Key": "evaluation.success-contracts",
    "Result": "PASS",
    "Qualification state": "VERIFIED",
    "Specification": "docs/mvp/03-success-contracts.md",
    "Validator": "scripts/check_success_contracts.py",
    "Mutation suite": "tests/qualification/test_success_contracts.py",
    "Qualification conditions": "40 / 40",
    "Execution authority": "AUTH-HETREN-MVP-3.0",
    "Long-term authority": "AUTH-HETREN-MASTER-2.0",
    "Task 1 regression": "PASS",
    "Task 2 regression": "PASS",
    "Diff check": "PASS",
    "Final accepted-state qualification": "PASS",
}


def markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in text:
        return ""

    body = text.split(marker, 1)[1]
    body = body.split("\n## ", 1)[0]
    return body.strip()


def validate_qualification_record(
    qualification_path: Path,
    spec_metadata: dict[str, str],
) -> list[str]:
    errors: list[str] = []

    if not qualification_path.is_file():
        return ["missing Decision 0003 qualification evidence"]

    text = qualification_path.read_text()

    if not text.startswith("# Decision 0003 Qualification Record\n"):
        errors.append("Decision 0003 qualification heading mismatch")

    metadata = parse_metadata(text)

    for key, expected in EXPECTED_QUALIFICATION_METADATA.items():
        actual = metadata.get(key)
        if actual != expected:
            errors.append(
                f"Decision 0003 qualification metadata {key} must be "
                f"{expected!r}; got {actual!r}"
            )

    specification_version = metadata.get("Specification version", "")
    if specification_version != spec_metadata.get("Version", ""):
        errors.append(
            "Decision 0003 qualification Specification version must "
            "match success-contract Version"
        )

    version_match = re.fullmatch(
        r"([0-9]+)\.([0-9]+)\.([0-9]+)",
        specification_version,
    )
    if version_match is None or int(version_match.group(1)) < 1:
        errors.append(
            "Qualified success-contract Specification version must "
            "have major version at least 1"
        )

    qualification_date = metadata.get("Date", "")
    try:
        date.fromisoformat(qualification_date)
    except ValueError:
        errors.append("Decision 0003 qualification Date must be valid ISO date")

    mutation_result = metadata.get("Mutation result", "")
    mutation_match = re.fullmatch(r"([0-9]+) / ([0-9]+)", mutation_result)
    if mutation_match is None:
        errors.append(
            "Decision 0003 qualification Mutation result must use N / N format"
        )
    else:
        killed = int(mutation_match.group(1))
        total = int(mutation_match.group(2))
        if killed != total or total < 1:
            errors.append(
                "Decision 0003 qualification requires all recorded "
                "mutations to be rejected"
            )

    for heading in QUALIFICATION_SECTIONS:
        if not markdown_section(text, heading):
            errors.append(
                f"Decision 0003 qualification missing section {heading}"
            )

    return errors

def validate_final_decision_evidence(
    decision_text: str,
) -> list[str]:
    errors: list[str] = []

    implementation = markdown_section(
        decision_text,
        "Implementation Evidence",
    )
    verification = markdown_section(
        decision_text,
        "Verification Evidence",
    )

    if not implementation:
        errors.append("Decision 0003 missing Implementation Evidence")
    elif "pending" in semantic_text(implementation):
        errors.append(
            "Decision 0003 Implementation Evidence remains pending"
        )

    if not verification:
        errors.append("Decision 0003 missing Verification Evidence")
    elif "pending" in semantic_text(verification):
        errors.append(
            "Decision 0003 Verification Evidence remains pending"
        )

    for required in (
        "docs/mvp/03-success-contracts.md",
        "scripts/check_success_contracts.py",
        "tests/qualification/test_success_contracts.py",
    ):
        if required not in implementation:
            errors.append(
                f"Decision 0003 Implementation Evidence missing {required}"
            )

    verification_required = (
        "docs/decisions/qualification/0003-success-contracts.md",
        "structural",
        "semantic",
        "mutation",
        "authority",
        "regression",
        "accepted-state",
    )

    normalized_verification = semantic_text(verification)
    for required in verification_required:
        if semantic_text(required) not in normalized_verification:
            errors.append(
                f"Decision 0003 Verification Evidence missing {required}"
            )

    return errors

CONDITION_REQUIREMENTS = {
    1: "governed by AUTH-HETREN-MVP-3.0 and AUTH-HETREN-MASTER-2.0",
    2: "GoalContract remains the canonical declaration of the governed objective",
    3: "EvaluationRecord remains the canonical measured-outcome record",
    4: "VerificationReport remains the canonical independent-verification record",
    5: "no competing canonical runtime record named SuccessContract",
    6: "Product, Native Intelligence, and Adaptive Intelligence success remain independently reportable",
    7: "shared evaluation outcome vocabulary is exactly PASS, FAIL, INCONCLUSIVE, BLOCKED, and INVALID",
    8: "evaluation outcome states remain distinct from task-lifecycle states",
    9: "PASS is conjunctive across all mandatory acceptance predicates",
    10: "valid evidence demonstrating a failed mandatory predicate produces FAIL",
    11: "invalid evidence cannot establish either PASS or FAIL",
    12: "INCONCLUSIVE means valid but insufficiently discriminating evidence",
    13: "inability to complete the governed evaluation is represented as BLOCKED",
    14: "comparison claims require an identified and materially compatible baseline or reference condition",
    15: "concrete baseline implementations remain deferred to Task 8",
    16: "protected predicates, metrics, thresholds, evaluators, and qualification rules are frozen before the protected evidence they govern is inspected",
    17: "material post-result changes to protected criteria preserve historical evidence, require governed revision, and trigger applicable requalification",
    18: "hard constraints and invariants are non-compensatory and cannot be averaged or weighted away",
    19: "mandatory budget constraints participate in the governed success decision",
    20: "budget exhaustion that prevents evaluation completion is distinguished from demonstrated target-system failure",
    21: "regression repair has explicit success semantics covering governed failure, repair, constraints, regressions, verification, and preserved evidence",
    22: "constrained improvement requires a baseline, predeclared improvement predicate, non-regression requirements, constraints, and applicable verification",
    23: "consequential success claims require meaningfully separated independent verification",
    24: "candidate under consequential verification is frozen sufficiently to prevent verification-driven tuning",
    25: "Native Intelligence success requires separate research evidence appropriate to the learned-capability claim",
    26: "failure of a Native Intelligence hypothesis remains valid negative research evidence and does not automatically invalidate product success",
    27: "Adaptive Intelligence success requires separate scientific evidence appropriate to adaptation, retention, locality, rollback, stability",
    28: "no Adaptive Intelligence candidate may be the sole authority certifying its own scientific success",
    29: "Native learned transfer, Adaptive Intelligence transfer, and authored infrastructure or method reuse remain distinct claims",
    30: "E1 tool-using agent, E2 structured-data ML, and E3 vision use the same outcome and evidence semantics",
    31: "environment adapters define interaction rather than success semantics",
    32: "evidence supports only the strongest justified claim, with narrower claims required when broader claims are unsupported",
    33: "negative, falsifying, blocked, invalid, unsupported, and inconclusive results remain preserved evidence",
    34: "concrete taxonomy, support boundaries, hypotheses, splits, baselines, and cost ledgers remain deferred respectively to Tasks 4 through 9",
    35: "product release status, Native Intelligence research status, and Adaptive Intelligence scientific status remain independently inspectable",
    36: "no weighted or aggregate success score may convert failure of a mandatory predicate, hard constraint, invariant, budget, or verification requirement into PASS",
    37: "authority-required acceptance predicates, constraints, invariants, budgets, evidence requirements, and verification requirements cannot be omitted from a GoalContract to manufacture PASS",
    38: "consequential-claim requirements cannot be bypassed merely by labeling a materially consequential claim non-consequential",
    39: "primary outcome resolution is deterministic when valid failure, invalid evidence, blocked execution, or inconclusive evidence coexist",
    40: "unsupported, negative, and falsifying remain claim or evidence characterizations rather than additional evaluation outcome states",
}


def parse_condition_bodies(text: str) -> dict[int, str]:
    matches = re.findall(
        r"^([0-9]+)\.\s+(.*?)(?=^[0-9]+\.\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return {
        int(number): normalize(body)
        for number, body in matches
    }


def validate_condition_semantics(text: str) -> list[str]:
    errors: list[str] = []
    bodies = parse_condition_bodies(text)

    for number, requirement in CONDITION_REQUIREMENTS.items():
        body = bodies.get(number, "")
        if semantic_text(requirement) not in semantic_text(body):
            errors.append(
                f"Task 3 qualification condition {number} missing "
                f"required semantics: {requirement}"
            )

    return errors

def semantic_text(text: str) -> str:
    return normalize(text).replace("`", "").casefold()


def require_semantics(
    errors: list[str],
    text: str,
    label: str,
    fragments: tuple[str, ...],
) -> None:
    normalized = semantic_text(text)
    for fragment in fragments:
        if semantic_text(fragment) not in normalized:
            errors.append(
                f"{label} missing semantic requirement: {fragment}"
            )


def validate_semantics(root: Path) -> list[str]:
    errors: list[str] = []

    spec_path = root / SPEC_RELATIVE
    decision_path = root / DECISION_RELATIVE

    if not spec_path.is_file() or not decision_path.is_file():
        return errors

    spec_text = spec_path.read_text()
    decision_text = decision_path.read_text()

    qualification_body = section_body(
        spec_text,
        28,
        "Task 3 Qualification Contract",
    )
    errors.extend(
        validate_condition_semantics(qualification_body)
    )

    section_requirements = {
        2: (
            "a claim is consequential when it is used to justify a material deployment",
            "does not become non-consequential merely because a producing process labels it that way",
            "consequence is determined by how the claim is used and by the governing authority",
        ),
        5: (
            "contract completeness is governed by applicable authority",
            "must not omit an authority-required acceptance predicate",
            "materially incomplete contract cannot establish pass",
        ),
        6: (
            "each governed evaluation has one primary outcome",
            "pass is possible only when all mandatory predicates",
            "fail applies when valid evidence decisively demonstrates violation",
            "invalid applies when material evidence or protocol required to decide the claim is invalid",
            "blocked applies when required evaluation cannot complete",
            "inconclusive applies when the required evaluation is valid",
        ),
        14: (
            "protected acceptance predicates, metrics, thresholds, evaluators",
            "must be declared before the protected evidence they govern is inspected",
            "the protected-evaluation identity must be preserved",
            "a material post-result change",
            "preservation of the historical result and its original contract",
            "an explicit governed revision",
            "requalification of the affected claim",
            "a failed protected result may not be converted into pass",
            "otherwise redefining success after observing the result",
        ),
        15: (
            "hard constraints and invariants are non-compensatory",
            "cannot be averaged",
        ),
        16: (
            "budget exhaustion",
            "blocked",
        ),
        20: (
            "meaningful neural and non-neural baselines",
            "valid negative research evidence",
            "claim must be narrowed accordingly",
        ),
        21: (
            "strong adaptation baselines",
            "retention of protected prior capability",
            "no adaptive candidate may certify its own scientific success",
            "valid scientific evidence",
        ),
        22: (
            "these are not interchangeable claims",
            "native intelligence transfer claim",
            "adaptive intelligence transfer is a separate scientific claim",
        ),
        23: (
            "environment adapters define how hetren interacts with a system",
            "they do not define whether an evaluation result counts as success",
        ),
        24: (
            "meaningfully separated from the path that proposed or produced the candidate result",
            "candidate under consequential verification must be frozen",
            "must not become the sole authority certifying its own consequential success",
        ),
        25: (
            "the evidence governs the claim",
            "terms such as unsupported, negative, and falsifying",
            "they are not additional evaluation outcome states",
            "resolves to exactly one of pass, fail, inconclusive, blocked, or invalid",
        ),
        26: (
            "final system taxonomy — task 4",
            "initial supported capability matrix — task 5",
            "task 7",
            "task 8",
            "task 9",
            "must not silently select their final concrete values",
        ),
        27: (
            "product release status",
            "native intelligence research status",
            "adaptive intelligence scientific status",
            "task completion also remains separate from evaluation success",
        ),
        29: (
            "hetren does not succeed because one number became larger",
            "success is therefore a property of the governed claim and its evidence",
            "desirable-looking result for a verified result",
        ),
    }

    for number, fragments in section_requirements.items():
        title = SECTION_TITLES[number - 1]
        body = section_body(spec_text, number, title)
        require_semantics(
            errors,
            body,
            f"section {number} {title!r}",
            fragments,
        )

    require_semantics(
        errors,
        decision_text,
        "Decision 0003",
        (
            "prevents authority-required contract elements from being omitted to manufacture pass",
            "verification requirements from being bypassed by relabeling",
            "deterministic outcome resolution",
            "unsupported, negative, and falsifying characterizations",
            "prevents hard-constraint or invariant failure from being averaged away",
        ),
    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Hetren Task 3 success contracts."
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
        help="require final Qualified and ACCEPTED state",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    errors = validate_structure(
        root,
        require_qualified=args.require_qualified,
    )

    if not errors:
        errors.extend(validate_semantics(root))

    if errors:
        print("SUCCESS CONTRACT VALIDATION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    spec_text = (root / SPEC_RELATIVE).read_text()
    decision_text = (root / DECISION_RELATIVE).read_text()
    spec_metadata = parse_metadata(spec_text)
    decision_metadata = parse_metadata(decision_text)

    print("SUCCESS CONTRACT VALIDATION: PASS")
    print(f"- version: {spec_metadata.get('Version')}")
    print(f"- status: {spec_metadata.get('Status')}")
    print(f"- decision: {decision_metadata.get('Status')}")
    print(f"- numbered sections: {len(SECTION_TITLES)}")
    print("- Task 3 qualification conditions: 40")
    print("- evaluation outcomes: " + ", ".join(OUTCOMES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
