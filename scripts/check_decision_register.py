#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ALLOWED_STATUSES = {"PROPOSED", "ACCEPTED", "SUPERSEDED", "REJECTED", "RETIRED"}
ALLOWED_CLASSES = {
    "ARCHITECTURE",
    "PRODUCT",
    "GOVERNANCE",
    "RESEARCH_GOVERNANCE",
    "EVALUATION",
    "SECURITY",
    "DATA",
    "OPERATIONS",
    "INTEGRATION",
}
ALLOWED_REVERSIBILITY = {"REVERSIBLE", "CONDITIONALLY_REVERSIBLE", "IRREVERSIBLE"}

CURRENT_AUTHORITIES = {
    "AUTH-HETREN-MASTER-2.0",
    "AUTH-HETREN-MVP-3.0",
}

ALLOWED_RESEARCH_PROGRAMS = {
    "NONE",
    "NATIVE",
    "ADAPTIVE",
    "CROSS_PROGRAM",
}

RESEARCH_EVIDENCE_CONSEQUENCES = {
    "THESIS": "NEW_PROGRAM_VERSION_AND_RERUN",
    "METRIC": "RERUN_AFFECTED_QUALIFICATION",
    "DATA": "RERUN_AND_PRESERVE_DATA_DISTINCTIONS",
    "BASELINE": "RECOMPARE_STRONGEST_RESULT",
    "MODEL": "NEW_REPLICATION_RESULT",
    "ALGORITHM": "NEW_METHOD_VERSION_AND_PREREGISTRATION",
    "BUG": "INVALIDATE_AFFECTED_RESULTS_AND_RERUN",
    "INFRA": "SMOKE_AND_REGRESSION_RERUN_IF_NUMERICAL_CHANGE",
}

ALLOWED_RESEARCH_CHANGE_CATEGORIES = {
    "NONE",
    *RESEARCH_EVIDENCE_CONSEQUENCES.keys(),
}

REQUIRED_METADATA = [
    "Decision ID",
    "Decision Key",
    "Title",
    "Status",
    "Class",
    "Date",
    "Authority",
    "Scope",
    "Research Program",
    "Research Change Category",
    "Evidence Consequence",
    "Supersedes",
    "Superseded By",
    "Reversibility",
    "Qualification",
]

REQUIRED_SECTIONS = [
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
]

@dataclass(frozen=True)
class RegisterRow:
    decision_id: str
    key: str
    title: str
    status: str
    decision_class: str
    authority: str
    record: str

@dataclass
class DecisionRecord:
    path: Path
    heading_id: str
    title: str
    metadata: dict[str, str]
    text: str

def strip_code(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value

def parse_authorities(text: str) -> set[str]:
    marker = "## 2. Canonical Authority References"
    if marker not in text:
        return set()

    section = text.split(marker, 1)[1]
    section = section.split("## 3. Decision Lifecycle", 1)[0]

    return set(
        re.findall(
            r"^\| `(AUTH-[A-Z0-9.-]+)` \| [^|]+ \|$",
            section,
            re.MULTILINE,
        )
    )

def parse_research_consequences(text: str) -> dict[str, str]:
    marker = "The required evidence consequence for each scientific-change category is:"

    if marker not in text:
        return {}

    section = text.split(marker, 1)[1]
    section = section.split(
        "These consequences are minimum governance requirements.",
        1,
    )[0]

    return dict(
        re.findall(
            r"^\| `([A-Z_]+)` \| `([A-Z_]+)` \|$",
            section,
            re.MULTILINE,
        )
    )


def parse_register(text: str) -> list[RegisterRow]:
    rows = []
    pattern = re.compile(
        r"^\| `(?P<id>[0-9]{4})` \| `(?P<key>[^`]+)` \| "
        r"(?P<title>[^|]+?) \| `(?P<status>[^`]+)` \| "
        r"`(?P<class>[^`]+)` \| `(?P<authority>[^`]+)` \| "
        r"`(?P<record>[^`]+)` \|$",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        rows.append(RegisterRow(
            decision_id=match.group("id"),
            key=match.group("key"),
            title=match.group("title").strip(),
            status=match.group("status"),
            decision_class=match.group("class"),
            authority=match.group("authority"),
            record=match.group("record"),
        ))
    return rows

def parse_record(path: Path) -> DecisionRecord:
    text = path.read_text()
    heading = re.search(r"^# Decision ([0-9]{4}): (.+)$", text, re.MULTILINE)
    heading_id = heading.group(1) if heading else ""
    title = heading.group(2).strip() if heading else ""

    metadata = {}
    for key in REQUIRED_METADATA:
        match = re.search(
            rf"^\*\*{re.escape(key)}:\*\* (.+)$",
            text,
            re.MULTILINE,
        )
        if match:
            metadata[key] = strip_code(match.group(1))

    return DecisionRecord(
        path=path,
        heading_id=heading_id,
        title=title,
        metadata=metadata,
        text=text,
    )

def normalize_ref(value: str) -> str | None:
    value = strip_code(value)
    if value == "None":
        return None
    return value


def section_body(text: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in text:
        return ""

    body = text.split(marker, 1)[1]
    body = body.split("\n## ", 1)[0]
    return body.strip()

def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    decisions_dir = root / "docs" / "decisions"
    register_path = decisions_dir / "register.md"
    template_path = decisions_dir / "template.md"

    if not register_path.is_file():
        return ["missing docs/decisions/register.md"]

    if not template_path.is_file():
        return ["missing docs/decisions/template.md"]

    template_text = template_path.read_text()

    for key in REQUIRED_METADATA:
        if f"**{key}:**" not in template_text:
            errors.append(
                f"decision template missing metadata {key}"
            )

    for required_section in REQUIRED_SECTIONS:
        if f"## {required_section}" not in template_text:
            errors.append(
                f"decision template missing section {required_section}"
            )

    for research_program in ALLOWED_RESEARCH_PROGRAMS:
        if research_program not in template_text:
            errors.append(
                f"decision template missing Research Program "
                f"{research_program}"
            )

    for research_category in ALLOWED_RESEARCH_CHANGE_CATEGORIES:
        if research_category not in template_text:
            errors.append(
                f"decision template missing Research Change Category "
                f"{research_category}"
            )

    register_text = register_path.read_text()

    version_match = re.search(
        r"^\*\*Version:\*\* ([0-9]+\.[0-9]+\.[0-9]+)$",
        register_text,
        re.MULTILINE,
    )
    if not version_match:
        errors.append(
            "register has invalid semantic Version"
        )

    status_match = re.search(
        r"^\*\*Status:\*\* (.+)$",
        register_text,
        re.MULTILINE,
    )
    if not status_match or status_match.group(1).strip() != "Active":
        errors.append(
            "register Status must be Active"
        )

    required_register_headers = {
        "**MVP Task:** 2 / 100",
        "**Governing execution authority:** `AUTH-HETREN-MVP-3.0`",
        "**Long-term authority:** `AUTH-HETREN-MASTER-2.0`",
        "**Governing charter:** Hetren MVP Charter v1.1.0",
    }

    for required_header in sorted(required_register_headers):
        if required_header not in register_text:
            errors.append(
                f"register missing required governing metadata: "
                f"{required_header}"
            )

    rows = parse_register(register_text)
    authorities = parse_authorities(register_text)
    declared_research_consequences = parse_research_consequences(
        register_text
    )

    if declared_research_consequences != RESEARCH_EVIDENCE_CONSEQUENCES:
        errors.append(
            "register research evidence consequence map does not "
            "match validator contract"
        )

    if not rows:
        errors.append("register contains no decision rows")
        return errors

    missing_authorities = CURRENT_AUTHORITIES - authorities
    extra_authorities = authorities - CURRENT_AUTHORITIES

    for authority in sorted(missing_authorities):
        errors.append(f"register missing current authority {authority}")

    for authority in sorted(extra_authorities):
        errors.append(f"register contains non-current authority {authority}")

    ids = [row.decision_id for row in rows]
    for decision_id, count in Counter(ids).items():
        if count > 1:
            errors.append(f"duplicate Decision ID in register: {decision_id}")

    record_refs = [row.record for row in rows]
    for record_ref, count in Counter(record_refs).items():
        if count > 1:
            errors.append(
                f"duplicate decision-record reference: {record_ref}"
            )

    accepted_keys = [
        row.key for row in rows if row.status == "ACCEPTED"
    ]
    for key, count in Counter(accepted_keys).items():
        if count > 1:
            errors.append(f"conflicting ACCEPTED Decision Key: {key}")

    row_by_id = {row.decision_id: row for row in rows}
    records: dict[str, DecisionRecord] = {}

    for row in rows:
        if row.status not in ALLOWED_STATUSES:
            errors.append(f"{row.decision_id}: unknown status {row.status}")
        if row.decision_class not in ALLOWED_CLASSES:
            errors.append(f"{row.decision_id}: unknown class {row.decision_class}")
        if row.authority not in authorities:
            errors.append(f"{row.decision_id}: unknown authority {row.authority}")

        record_ref = Path(row.record)

        if record_ref.is_absolute() or record_ref.name != row.record:
            errors.append(
                f"{row.decision_id}: invalid record path {row.record}"
            )
            continue

        record_path = decisions_dir / row.record
        if not record_path.is_file():
            errors.append(f"{row.decision_id}: missing record {row.record}")
            continue

        filename_match = re.match(r"^([0-9]{4})-.+\.md$", row.record)
        if not filename_match or filename_match.group(1) != row.decision_id:
            errors.append(f"{row.decision_id}: filename does not match Decision ID")

        record = parse_record(record_path)
        records[row.decision_id] = record

        for key in REQUIRED_METADATA:
            if key not in record.metadata:
                errors.append(f"{row.decision_id}: missing metadata {key}")

        for section in REQUIRED_SECTIONS:
            if f"## {section}" not in record.text:
                errors.append(f"{row.decision_id}: missing section {section}")

        if record.heading_id != row.decision_id:
            errors.append(f"{row.decision_id}: heading Decision ID mismatch")

        if record.metadata.get("Decision ID") != row.decision_id:
            errors.append(f"{row.decision_id}: record Decision ID mismatch")
        if record.metadata.get("Decision Key") != row.key:
            errors.append(f"{row.decision_id}: Decision Key mismatch")
        if record.metadata.get("Title") != row.title:
            errors.append(f"{row.decision_id}: metadata Title mismatch")
        if record.metadata.get("Status") != row.status:
            errors.append(f"{row.decision_id}: status mismatch")
        if record.metadata.get("Class") != row.decision_class:
            errors.append(f"{row.decision_id}: class mismatch")
        if record.metadata.get("Authority") != row.authority:
            errors.append(f"{row.decision_id}: authority mismatch")
        if record.title != row.title:
            errors.append(f"{row.decision_id}: title mismatch")

        reversibility = record.metadata.get("Reversibility")
        if reversibility and reversibility not in ALLOWED_REVERSIBILITY:
            errors.append(
                f"{row.decision_id}: unknown reversibility {reversibility}"
            )

        date_value = record.metadata.get("Date", "")
        if date_value:
            try:
                parsed_date = date.fromisoformat(date_value)
                if parsed_date.isoformat() != date_value:
                    raise ValueError
            except ValueError:
                errors.append(
                    f"{row.decision_id}: invalid calendar date {date_value}"
                )

        key_value = record.metadata.get("Decision Key", "")
        if key_value and not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", key_value):
            errors.append(f"{row.decision_id}: invalid Decision Key {key_value}")

        research_program = record.metadata.get("Research Program", "")
        research_category = record.metadata.get(
            "Research Change Category",
            "",
        )
        evidence_consequence = record.metadata.get(
            "Evidence Consequence",
            "",
        )

        if research_program not in ALLOWED_RESEARCH_PROGRAMS:
            errors.append(
                f"{row.decision_id}: invalid Research Program "
                f"{research_program}"
            )

        if research_category not in ALLOWED_RESEARCH_CHANGE_CATEGORIES:
            errors.append(
                f"{row.decision_id}: invalid Research Change Category "
                f"{research_category}"
            )
        elif research_category == "NONE":
            if research_program != "NONE":
                errors.append(
                    f"{row.decision_id}: research program/category mismatch"
                )
            if evidence_consequence != "NONE":
                errors.append(
                    f"{row.decision_id}: non-research decision must use "
                    "Evidence Consequence NONE"
                )
        else:
            if research_program == "NONE":
                errors.append(
                    f"{row.decision_id}: research category requires "
                    "a research program"
                )

            expected_consequence = RESEARCH_EVIDENCE_CONSEQUENCES[
                research_category
            ]

            if evidence_consequence != expected_consequence:
                errors.append(
                    f"{row.decision_id}: {research_category} requires "
                    f"Evidence Consequence {expected_consequence}"
                )

        if row.status == "ACCEPTED":
            qualification = record.metadata.get("Qualification", "")
            if qualification.lower() in {"pending", "none", ""}:
                errors.append(
                    f"{row.decision_id}: ACCEPTED decision lacks qualification"
                )

            implementation_body = section_body(
                record.text,
                "Implementation Evidence",
            )
            verification_body = section_body(
                record.text,
                "Verification Evidence",
            )

            if not implementation_body:
                errors.append(
                    f"{row.decision_id}: ACCEPTED decision lacks "
                    "implementation evidence"
                )
            elif re.search(
                r"\bPending\b",
                implementation_body,
                re.IGNORECASE,
            ):
                errors.append(
                    f"{row.decision_id}: ACCEPTED decision has pending "
                    "implementation evidence"
                )

            if not verification_body:
                errors.append(
                    f"{row.decision_id}: ACCEPTED decision lacks "
                    "verification evidence"
                )
            elif re.search(
                r"\bPending\b",
                verification_body,
                re.IGNORECASE,
            ):
                errors.append(
                    f"{row.decision_id}: ACCEPTED decision has pending "
                    "verification"
                )

    registered_files = {row.record for row in rows}
    governed_files = {
        path.name
        for path in decisions_dir.glob("[0-9][0-9][0-9][0-9]-*.md")
    }
    for filename in sorted(governed_files - registered_files):
        errors.append(f"unregistered decision file: {filename}")

    for decision_id, record in records.items():
        status = record.metadata.get("Status")
        supersedes = normalize_ref(record.metadata.get("Supersedes", "None"))
        superseded_by = normalize_ref(record.metadata.get("Superseded By", "None"))

        if status == "SUPERSEDED":
            if not superseded_by:
                errors.append(f"{decision_id}: SUPERSEDED decision lacks successor")
            elif superseded_by not in records:
                errors.append(f"{decision_id}: unknown successor {superseded_by}")
            else:
                successor = records[superseded_by]
                if successor.metadata.get("Status") != "ACCEPTED":
                    errors.append(f"{decision_id}: successor is not ACCEPTED")
                if successor.metadata.get("Decision Key") != record.metadata.get("Decision Key"):
                    errors.append(
                        f"{decision_id}: supersession Decision Key mismatch"
                    )
                if normalize_ref(successor.metadata.get("Supersedes", "None")) != decision_id:
                    errors.append(f"{decision_id}: asymmetric supersession")

        if status == "ACCEPTED" and supersedes:
            if supersedes not in records:
                errors.append(f"{decision_id}: unknown predecessor {supersedes}")
            else:
                predecessor = records[supersedes]
                if predecessor.metadata.get("Status") != "SUPERSEDED":
                    errors.append(f"{decision_id}: predecessor is not SUPERSEDED")
                if predecessor.metadata.get("Decision Key") != record.metadata.get("Decision Key"):
                    errors.append(
                        f"{decision_id}: supersession Decision Key mismatch"
                    )
                if normalize_ref(predecessor.metadata.get("Superseded By", "None")) != decision_id:
                    errors.append(f"{decision_id}: asymmetric supersession")

    return errors

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    errors = validate_repository(args.root.resolve())

    if errors:
        print("DECISION REGISTER VALIDATION: FAIL")
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("DECISION REGISTER VALIDATION: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
