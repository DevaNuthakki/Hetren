from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
)
from app.hvee_registry_service import (
    resolve_evaluator_version,
    resolve_metric_definition,
)
from hvee.packs.asr import (
    CER_EVALUATOR,
    CER_METRIC,
    WER_EVALUATOR,
    WER_METRIC,
)


@dataclass(frozen=True, slots=True)
class ASRTextErrorRegistry:
    wer_metric: HveeMetricDefinition
    wer_evaluator: HveeEvaluatorVersion
    cer_metric: HveeMetricDefinition
    cer_evaluator: HveeEvaluatorVersion


def resolve_asr_text_error_registry(
    db: Session,
) -> ASRTextErrorRegistry:
    """
    Resolve the canonical HVEE ASR WER/CER registry records.

    The caller owns the surrounding transaction.
    """

    wer_metric = resolve_metric_definition(
        db,
        WER_METRIC,
    )
    wer_evaluator = resolve_evaluator_version(
        db,
        WER_EVALUATOR,
    )
    cer_metric = resolve_metric_definition(
        db,
        CER_METRIC,
    )
    cer_evaluator = resolve_evaluator_version(
        db,
        CER_EVALUATOR,
    )

    return ASRTextErrorRegistry(
        wer_metric=wer_metric,
        wer_evaluator=wer_evaluator,
        cer_metric=cer_metric,
        cer_evaluator=cer_evaluator,
    )


from hvee.packs.asr import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
    NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
)


@dataclass(frozen=True, slots=True)
class ASRNormalizedTextErrorRegistry:
    wer_metric: HveeMetricDefinition
    wer_evaluator: HveeEvaluatorVersion
    cer_metric: HveeMetricDefinition
    cer_evaluator: HveeEvaluatorVersion
    substitutions_metric: HveeMetricDefinition
    insertions_metric: HveeMetricDefinition
    deletions_metric: HveeMetricDefinition
    word_alignment_evaluator: HveeEvaluatorVersion


def resolve_asr_normalized_text_error_registry(
    db: Session,
) -> ASRNormalizedTextErrorRegistry:
    """
    Resolve the canonical normalized-basic ASR registry records.

    Registry resolution participates in the caller's transaction and
    never commits independently.
    """

    wer_metric = resolve_metric_definition(
        db,
        NORMALIZED_WER_METRIC,
    )
    wer_evaluator = resolve_evaluator_version(
        db,
        NORMALIZED_WER_EVALUATOR,
    )

    cer_metric = resolve_metric_definition(
        db,
        NORMALIZED_CER_METRIC,
    )
    cer_evaluator = resolve_evaluator_version(
        db,
        NORMALIZED_CER_EVALUATOR,
    )

    substitutions_metric = resolve_metric_definition(
        db,
        NORMALIZED_SUBSTITUTIONS_METRIC,
    )
    insertions_metric = resolve_metric_definition(
        db,
        NORMALIZED_INSERTIONS_METRIC,
    )
    deletions_metric = resolve_metric_definition(
        db,
        NORMALIZED_DELETIONS_METRIC,
    )

    word_alignment_evaluator = resolve_evaluator_version(
        db,
        NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
    )

    return ASRNormalizedTextErrorRegistry(
        wer_metric=wer_metric,
        wer_evaluator=wer_evaluator,
        cer_metric=cer_metric,
        cer_evaluator=cer_evaluator,
        substitutions_metric=substitutions_metric,
        insertions_metric=insertions_metric,
        deletions_metric=deletions_metric,
        word_alignment_evaluator=(
            word_alignment_evaluator
        ),
    )
