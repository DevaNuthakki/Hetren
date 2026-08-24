"""Semantic-support contract for the I2 clean synthetic ASR corpus.

These tests prove that each new clean transcript remains conclusively
supported by the current Critical Number and Critical Identifier
evaluators before any audio is generated from it.

The tests do not claim qualification, production readiness, or
acoustic performance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hvee.packs.asr.critical_identifier_fidelity import (
    EN_US_CRITICAL_IDENTIFIER_PROFILE,
    evaluate_critical_identifier_fidelity,
)
from hvee.packs.asr.critical_number_fidelity import (
    EN_US_CRITICAL_NUMBER_PROFILE,
    evaluate_critical_number_fidelity,
)


BACKEND_ROOT = Path(__file__).resolve().parents[4]

TRANSCRIPT_ROOT = (
    BACKEND_ROOT
    / "corpora/asr/adversarial/v1/"
    "specification/transcripts"
)


CASES = (
    (
        "clean.identifier-account-order",
        0,
        2,
    ),
    (
        "clean.identifier-confirmation",
        0,
        1,
    ),
    (
        "clean.identifier-multiple",
        0,
        2,
    ),
    (
        "clean.multi-number-id",
        2,
        1,
    ),
    (
        "clean.number-currency-time",
        2,
        0,
    ),
    (
        "clean.number-measurement",
        1,
        0,
    ),
    (
        "clean.number-percentage",
        1,
        0,
    ),
)


def _reference_text(
    case_id: str,
) -> str:
    transcript_file = (
        TRANSCRIPT_ROOT
        / f"{case_id}.txt"
    )

    assert transcript_file.is_file()
    assert not transcript_file.is_symlink()

    text = transcript_file.read_text(
        encoding="utf-8"
    )

    # Corpus transcripts are committed with exactly one final newline,
    # while semantic evaluation operates on the spoken content.
    assert text.endswith("\n")
    assert not text.endswith("\n\n")

    reference = text.removesuffix("\n")

    assert reference
    assert reference == reference.strip()

    return reference


@pytest.mark.parametrize(
    (
        "case_id",
        "expected_number_count",
        "expected_identifier_count",
    ),
    CASES,
)
def test_i2_clean_transcript_has_conclusive_semantic_baseline(
    case_id: str,
    expected_number_count: int,
    expected_identifier_count: int,
):
    reference = _reference_text(
        case_id
    )

    number = (
        evaluate_critical_number_fidelity(
            reference_text=reference,
            generated_text=reference,
            profile=(
                EN_US_CRITICAL_NUMBER_PROFILE
            ),
        )
    )

    identifier = (
        evaluate_critical_identifier_fidelity(
            reference_text=reference,
            generated_text=reference,
            profile=(
                EN_US_CRITICAL_IDENTIFIER_PROFILE
            ),
        )
    )

    assert (
        len(number.reference_entities)
        == expected_number_count
    )

    assert (
        len(identifier.reference_entities)
        == expected_identifier_count
    )

    if expected_number_count:
        assert number.applicable is True
        assert number.preserved is True
        assert (
            number.outcome.value
            == "preserved"
        )

        assert all(
            entity.issue_reason_code is None
            for entity
            in number.reference_entities
        )
    else:
        assert number.applicable is False
        assert number.preserved is None
        assert (
            number.outcome.value
            == "not_applicable"
        )

    if expected_identifier_count:
        assert identifier.applicable is True
        assert identifier.preserved is True
        assert (
            identifier.outcome.value
            == "preserved"
        )

        assert all(
            entity.issue_reason_code is None
            for entity
            in identifier.reference_entities
        )
    else:
        assert identifier.applicable is False
        assert identifier.preserved is None
        assert (
            identifier.outcome.value
            == "not_applicable"
        )
