from pathlib import Path

from scripts.check_hetren_identity_migration import (
    classify_path,
    scan_repository,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_repository_has_no_unclassified_ovrin_identity():
    unresolved = [
        occurrence
        for occurrence in scan_repository(REPOSITORY_ROOT)
        if occurrence.category == "unresolved"
    ]

    assert unresolved == []


def test_unknown_active_source_is_not_silently_approved(tmp_path):
    active_source = tmp_path / "active_product.py"
    active_source.write_text(
        'PRODUCT_NAME = "Ovrin"\n',
        encoding="utf-8",
    )

    occurrences = scan_repository(tmp_path)

    assert len(occurrences) == 1
    assert occurrences[0].category == "unresolved"


def test_historical_migration_identity_is_preserved():
    category, _ = classify_path(
        "backend/alembic/versions/"
        "31039971356b_create_initial_ovrin_schema.py"
    )

    assert category == "historical_identity"
