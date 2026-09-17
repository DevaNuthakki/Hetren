#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def read_required(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        errors.append(f"missing required file: {path}")
        return ""
    return path.read_text(encoding="utf-8")


def section(text: str, start: str, end: str, errors: list[str]) -> str:
    start_pos = text.find(start)
    if start_pos == -1:
        errors.append(f"missing section: {start}")
        return ""

    end_pos = text.find(end, start_pos + len(start))
    if end_pos == -1:
        errors.append(f"missing section boundary: {end}")
        return ""

    return text[start_pos:end_pos]


def metadata(text: str, name: str) -> str | None:
    match = re.search(
        rf"^\*\*{re.escape(name)}:\*\*\s*(.+)$",
        text,
        flags=re.MULTILINE,
    )
    return match.group(1).strip() if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--require-qualified",
        action="store_true",
        help="Require the charter status to be Qualified.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    errors: list[str] = []

    charter_path = root / "docs/mvp/02-charter.md"
    authority_path = root / "docs/mvp/00-authority.md"

    charter = read_required(charter_path, errors)
    authority = read_required(authority_path, errors)

    if not charter or not authority:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    if metadata(charter, "Version") != "1.1.0":
        errors.append("charter version must be 1.1.0")

    status = metadata(charter, "Status")
    if status not in {"Requalifying", "Qualified"}:
        errors.append(
            "charter status must be Requalifying or Qualified"
        )

    if args.require_qualified and status != "Qualified":
        errors.append("charter must be Qualified for final qualification")

    expected_execution_authority = (
        "Hetren Unified MVP and Adaptive Intelligence Execution Plan "
        "v3.0 (`AUTH-HETREN-MVP-3.0`)"
    )

    expected_long_term_authority = (
        "Hetren Unified Product, Intelligence, and Adaptive Research "
        "Master Specification v2.0 (`AUTH-HETREN-MASTER-2.0`)"
    )

    if metadata(charter, "Execution authority") != expected_execution_authority:
        errors.append(
            "charter Execution authority metadata must exactly identify "
            "AUTH-HETREN-MVP-3.0"
        )

    if metadata(charter, "Long-term authority") != expected_long_term_authority:
        errors.append(
            "charter Long-term authority metadata must exactly identify "
            "AUTH-HETREN-MASTER-2.0"
        )

    canonical_ids = (
        "AUTH-HETREN-MASTER-2.0",
        "AUTH-HETREN-MVP-3.0",
    )

    for authority_id in canonical_ids:
        if authority_id not in authority:
            errors.append(
                f"authority file missing canonical authority: {authority_id}"
            )

    authority_section = section(
        charter,
        "## 2. Authority And Change Control",
        "## 3. MVP Outcomes",
        errors,
    )

    for authority_id in canonical_ids:
        if authority_id not in authority_section:
            errors.append(
                f"charter authority section missing canonical authority: "
                f"{authority_id}"
            )

    forbidden_current_authority = (
        "**Authority:** Hetren MVP Plan v2.0",
        "**Long-term boundary:** Hetren Product Specification v1.4",
        "**Research authority:** Hetren Neural Intelligence Research and MVP Design v1.0",
    )

    for forbidden in forbidden_current_authority:
        if forbidden in charter:
            errors.append(
                f"superseded authority still presented as current: {forbidden}"
            )

    headings = re.findall(
        r"^## (\d+)\. (.+)$",
        charter,
        flags=re.MULTILINE,
    )

    section_numbers = [int(number) for number, _ in headings]
    expected_sections = list(range(1, 34))

    if section_numbers != expected_sections:
        errors.append(
            "charter sections must be sequential from 1 through 33; "
            f"found {section_numbers}"
        )

    required_headings = {
        11: "Native Neural Intelligence Research",
        12: "Adaptive Intelligence Research",
        21: "Research Qualification",
        29: "MVP Falsification Conditions",
        30: "MVP Release Gate",
        32: "Task 1 Qualification Contract",
        33: "Charter Principle",
    }

    heading_map = {
        int(number): title
        for number, title in headings
    }

    for number, expected_title in required_headings.items():
        if heading_map.get(number) != expected_title:
            errors.append(
                f"section {number} must be '{expected_title}'"
            )

    release = section(
        charter,
        "## 30. MVP Release Gate",
        "## 31. Task-Level Definition Of Done",
        errors,
    )

    release_conditions = re.findall(
        r"(?m)^(\d+)\. ",
        release,
    )

    if release_conditions != [str(i) for i in range(1, 15)]:
        errors.append(
            "MVP release gate must contain exactly conditions 1 through 14"
        )

    task1 = section(
        charter,
        "## 32. Task 1 Qualification Contract",
        "## 33. Charter Principle",
        errors,
    )

    task1_conditions = re.findall(
        r"(?m)^(\d+)\. ",
        task1,
    )

    if task1_conditions != [str(i) for i in range(1, 26)]:
        errors.append(
            "Task 1 qualification contract must contain exactly "
            "conditions 1 through 25"
        )

    required_fragments = (
        "Native Hetren Intelligence and Adaptive Intelligence",
        "## 11. Native Neural Intelligence Research",
        "## 12. Adaptive Intelligence Research",
        "Hetren Governed Plasticity, or HGP, is a working research hypothesis.",
        "task-state revision as evidence arrives",
        "Failure of the native neural candidate to outperform a meaningful baseline",
        "Failure of HGP or another adaptive mechanism does not by itself invalidate",
        "The product release decision and Adaptive Intelligence scientific decision",
        "Research status and product status must remain separately reportable.",
        "`docs/research/native_intelligence/`",
        "`research/native_intelligence/`",
        "`docs/research/adaptive_intelligence/`",
        "`research/adaptive_intelligence/`",
    )

    for fragment in required_fragments:
        if fragment not in charter and fragment not in authority:
            errors.append(
                f"required charter/authority contract missing: {fragment}"
            )

    required_directories = (
        root / "docs/research/native_intelligence",
        root / "docs/research/adaptive_intelligence",
        root / "research/native_intelligence",
        root / "research/adaptive_intelligence",
    )

    for directory in required_directories:
        if not directory.is_dir():
            errors.append(
                f"missing research boundary directory: {directory}"
            )

    if errors:
        print("MVP CHARTER VALIDATION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("MVP CHARTER VALIDATION: PASS")
    print(f"- version: {metadata(charter, 'Version')}")
    print(f"- status: {status}")
    print("- numbered sections: 33")
    print("- MVP release conditions: 14")
    print("- Task 1 qualification conditions: 25")
    print("- canonical authorities: 2")
    print("- research programs: Native Intelligence + Adaptive Intelligence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
