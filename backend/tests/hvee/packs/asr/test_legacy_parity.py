import pytest
from jiwer import cer as legacy_cer
from jiwer import process_words

from app.evaluation_service import build_error_summary
from hvee.packs.asr import evaluate_transcript_pair


@pytest.mark.parametrize(
    ("reference_text", "generated_text"),
    [
        (
            "the quick brown fox",
            "the quick brown fox",
        ),
        (
            "the quick brown fox",
            "the quick fox",
        ),
        (
            "hello world",
            "hello there",
        ),
        (
            "one two",
            "zero one two three",
        ),
        (
            "Case-sensitive punctuation.",
            "case-sensitive punctuation",
        ),
    ],
)
def test_hvee_asr_matches_previous_jiwer_computation(
    reference_text: str,
    generated_text: str,
):
    previous_words = process_words(
        reference_text,
        generated_text,
    )
    previous_wer = float(previous_words.wer)
    previous_cer = float(
        legacy_cer(
            reference_text,
            generated_text,
        )
    )

    evaluation = evaluate_transcript_pair(
        reference_text=reference_text,
        generated_text=generated_text,
    )

    assert evaluation.wer == previous_wer
    assert evaluation.cer == previous_cer
    assert (
        evaluation.substitutions
        == previous_words.substitutions
    )
    assert (
        evaluation.insertions
        == previous_words.insertions
    )
    assert (
        evaluation.deletions
        == previous_words.deletions
    )


def test_legacy_error_summary_format_is_preserved():
    reference_text = "the quick brown fox"
    generated_text = "the quick fox"

    evaluation = evaluate_transcript_pair(
        reference_text=reference_text,
        generated_text=generated_text,
    )

    wer_score, cer_score, summary = build_error_summary(
        reference_text=reference_text,
        generated_text=generated_text,
    )

    assert wer_score == evaluation.wer
    assert cer_score == evaluation.cer

    assert summary == (
        f"WER={evaluation.wer:.3f}, "
        f"CER={evaluation.cer:.3f}. "
        f"Substitutions={evaluation.substitutions}, "
        f"insertions={evaluation.insertions}, "
        f"deletions={evaluation.deletions}."
    )
