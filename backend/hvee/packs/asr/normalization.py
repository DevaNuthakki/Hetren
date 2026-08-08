from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError


@dataclass(frozen=True, slots=True)
class ASRTextNormalizationProfile:
    key: str
    version: str
    description: str


BASIC_TEXT_NORMALIZATION = ASRTextNormalizationProfile(
    key="hetren.asr.text.basic",
    version="1.0.0",
    description=(
        "Hetren basic ASR transcript normalization: Unicode NFKC, "
        "Unicode case folding, punctuation-to-space conversion, "
        "and whitespace collapsing while preserving letters, "
        "digits, diacritics, and non-punctuation symbols."
    ),
)


def normalize_text_basic(
    text: str,
) -> str:
    """
    Normalize transcript text using the Hetren basic profile v1.0.0.

    This profile is intentionally conservative. It does not expand
    contractions, remove bracketed content, transliterate diacritics,
    convert numbers to words, or perform language-specific rewriting.
    """

    if not isinstance(text, str):
        raise HveeContractError(
            "ASR transcript normalization requires a string"
        )

    normalized = unicodedata.normalize(
        "NFKC",
        text,
    ).casefold()

    characters: list[str] = []

    for character in normalized:
        category = unicodedata.category(
            character
        )

        if (
            character.isspace()
            or category.startswith("P")
        ):
            characters.append(" ")
        else:
            characters.append(character)

    return " ".join(
        "".join(characters).split()
    )
