import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr import (
    BASIC_TEXT_NORMALIZATION,
    normalize_text_basic,
)


def test_basic_normalization_identity_is_versioned():
    assert (
        BASIC_TEXT_NORMALIZATION.key
        == "hetren.asr.text.basic"
    )
    assert (
        BASIC_TEXT_NORMALIZATION.version
        == "1.0.0"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            " Hello,   WORLD! ",
            "hello world",
        ),
        (
            "hello\tworld\nagain",
            "hello world again",
        ),
        (
            "state-of-the-art",
            "state of the art",
        ),
        (
            "[noise] Hello (again)",
            "noise hello again",
        ),
        (
            "Ｃａｆｅ́",
            "café",
        ),
        (
            "Café déjà vu",
            "café déjà vu",
        ),
        (
            "$100 €50",
            "$100 €50",
        ),
        (
            "",
            "",
        ),
        (
            "   ",
            "",
        ),
    ],
)
def test_basic_normalization_golden_vectors(
    source: str,
    expected: str,
):
    assert normalize_text_basic(source) == expected


def test_basic_normalization_does_not_remove_diacritics():
    assert normalize_text_basic(
        "résumé"
    ) == "résumé"


def test_basic_normalization_does_not_remove_content_markers():
    assert normalize_text_basic(
        "[laughter]"
    ) == "laughter"


def test_basic_normalization_rejects_non_strings():
    with pytest.raises(
        HveeContractError,
        match="requires a string",
    ):
        normalize_text_basic(  # type: ignore[arg-type]
            123
        )
