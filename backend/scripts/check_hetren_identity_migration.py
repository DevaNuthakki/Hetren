"""Classify remaining Ovrin identities during the Hetren migration.

The migration is intentionally not a blind text replacement. Some legacy
values are compatibility or cryptographic identities, while unclassified
uses in active code are errors. This checker makes that boundary executable.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import fnmatch
import json
from pathlib import Path
import re
from typing import Iterable


TOKEN_PATTERN = re.compile(r"ovrin", re.IGNORECASE)

EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "venv",
}

CONTENT_EXCLUDED_PREFIXES = (
    "backend/corpora/",
    "backend/uploads/",
    "local-backups/",
)

TEXT_SUFFIXES = {
    ".example",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class IdentityRule:
    category: str
    reason: str
    path_patterns: tuple[str, ...]


@dataclass(frozen=True)
class IdentityOccurrence:
    path: str
    line: int
    column: int
    value: str
    category: str
    reason: str


IDENTITY_RULES = (
    IdentityRule(
        category="compatibility_alias",
        reason=(
            "Pre-Hetren environment names remain readable during the "
            "compatibility window."
        ),
        path_patterns=(
            "backend/app/config.py",
            "backend/app/runner_config.py",
            "backend/app/speech/registry.py",
            "backend/tests/test_config.py",
            "backend/tests/test_runner_config.py",
            "backend/tests/test_speech_providers.py",
        ),
    ),
    IdentityRule(
        category="cryptographic_identity",
        reason=(
            "Legacy prefixes select the historical hash namespace; changing "
            "them would invalidate issued credentials."
        ),
        path_patterns=(
            "backend/app/runner_security.py",
            "backend/tests/test_runner_security.py",
        ),
    ),
    IdentityRule(
        category="storage_identity",
        reason=(
            "Existing SQLite/PostgreSQL databases, users, test safety checks, "
            "and Docker volumes require an explicit data migration."
        ),
        path_patterns=(
            ".env.example",
            ".github/workflows/ci.yml",
            "README.md",
            "backend/ovrin.db",
            "backend/tests/conftest.py",
            "compose.yml",
        ),
    ),
    IdentityRule(
        category="historical_identity",
        reason=(
            "Historical migrations, backups, and one-time legacy tools retain "
            "their original identity."
        ),
        path_patterns=(
            "backend/alembic/versions/"
            "31039971356b_create_initial_ovrin_schema.py",
            "backend/scripts/migrate_debug_result_details.py",
            "backend/test-upload/*",
            "local-backups/*",
        ),
    ),
    IdentityRule(
        category="cleanup_alias",
        reason=(
            "Seed cleanup recognizes old project names so reruns do not leave "
            "duplicate legacy data."
        ),
        path_patterns=(
            "backend/scripts/seed_phase_one_demo.py",
            "backend/scripts/seed_phase_two_demo.py",
        ),
    ),
    IdentityRule(
        category="migration_control",
        reason=(
            "Migration policy, checker, and checker tests must name the legacy "
            "identity they govern."
        ),
        path_patterns=(
            "backend/scripts/check_hetren_identity_migration.py",
            "backend/tests/test_hetren_identity_migration.py",
            "docs/HETREN_IDENTITY_MIGRATION.md",
        ),
    ),
)


def classify_path(relative_path: str) -> tuple[str, str]:
    for rule in IDENTITY_RULES:
        if any(
            fnmatch.fnmatch(relative_path, pattern)
            for pattern in rule.path_patterns
        ):
            return rule.category, rule.reason

    return (
        "unresolved",
        "No approved compatibility, storage, or historical rule exists.",
    )


def _is_excluded_path(relative_path: Path) -> bool:
    if any(
        part in EXCLUDED_DIRECTORY_NAMES
        for part in relative_path.parts
    ):
        return True

    path_text = relative_path.as_posix()
    if path_text == ".env":
        return True

    if path_text.startswith(".env.") and path_text != ".env.example":
        return True

    return False


def _candidate_files(repository_root: Path) -> Iterable[Path]:
    for candidate in sorted(repository_root.rglob("*")):
        if not candidate.is_file() or candidate.is_symlink():
            continue

        relative_path = candidate.relative_to(repository_root)
        if _is_excluded_path(relative_path):
            continue

        yield candidate


def _should_scan_content(relative_path: str, path: Path) -> bool:
    if relative_path.startswith(CONTENT_EXCLUDED_PREFIXES):
        return False

    if path.name in {"Dockerfile", "Makefile"}:
        return True

    return path.suffix.lower() in TEXT_SUFFIXES


def _path_occurrences(relative_path: str) -> list[IdentityOccurrence]:
    category, reason = classify_path(relative_path)
    return [
        IdentityOccurrence(
            path=relative_path,
            line=0,
            column=match.start() + 1,
            value=match.group(0),
            category=category,
            reason=reason,
        )
        for match in TOKEN_PATTERN.finditer(relative_path)
    ]


def _content_occurrences(
    relative_path: str,
    path: Path,
) -> list[IdentityOccurrence]:
    if not _should_scan_content(relative_path, path):
        return []

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    category, reason = classify_path(relative_path)
    occurrences: list[IdentityOccurrence] = []

    for line_number, line in enumerate(content.splitlines(), start=1):
        for match in TOKEN_PATTERN.finditer(line):
            occurrences.append(
                IdentityOccurrence(
                    path=relative_path,
                    line=line_number,
                    column=match.start() + 1,
                    value=match.group(0),
                    category=category,
                    reason=reason,
                )
            )

    return occurrences


def scan_repository(
    repository_root: Path,
) -> list[IdentityOccurrence]:
    root = repository_root.resolve()
    occurrences: list[IdentityOccurrence] = []

    for path in _candidate_files(root):
        relative_path = path.relative_to(root).as_posix()
        occurrences.extend(_path_occurrences(relative_path))
        occurrences.extend(_content_occurrences(relative_path, path))

    return occurrences


def _category_counts(
    occurrences: Iterable[IdentityOccurrence],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for occurrence in occurrences:
        counts[occurrence.category] = (
            counts.get(occurrence.category, 0) + 1
        )
    return dict(sorted(counts.items()))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Classify every remaining Ovrin identity and fail on "
            "unapproved active uses."
        )
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    occurrences = scan_repository(args.repository_root)
    unresolved = [
        occurrence
        for occurrence in occurrences
        if occurrence.category == "unresolved"
    ]

    if args.format == "json":
        print(
            json.dumps(
                {
                    "repository_root": str(
                        args.repository_root.resolve()
                    ),
                    "counts": _category_counts(occurrences),
                    "unresolved_count": len(unresolved),
                    "occurrences": [
                        asdict(occurrence)
                        for occurrence in occurrences
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("HETREN IDENTITY MIGRATION CHECK")
        for category, count in _category_counts(occurrences).items():
            print(f"{category}={count}")

        if args.verbose or unresolved:
            print()
            print("OCCURRENCES")
            selected = occurrences if args.verbose else unresolved
            for occurrence in selected:
                location = occurrence.path
                if occurrence.line:
                    location += (
                        f":{occurrence.line}:{occurrence.column}"
                    )
                print(
                    f"{occurrence.category}\t{location}\t"
                    f"{occurrence.reason}"
                )

        print()
        if unresolved:
            print("HETREN_IDENTITY_MIGRATION=FAIL")
        else:
            print("HETREN_IDENTITY_MIGRATION=PASS")

    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
