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
