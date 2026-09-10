"""Deterministic offline scoring adapter for Run-04 Public-v2.

The real evidence entry point validates all frozen input hashes before parsing
transcript/reference semantics. Scored outputs intentionally exclude raw
reference and prediction text.

Importing this module performs no Run-04 evidence access and no scoring.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from hvee.packs.asr.critical_identifier_fidelity import (
    EN_US_CRITICAL_IDENTIFIER_PROFILE,
    evaluate_critical_identifier_fidelity,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    EN_US_CRITICAL_NUMBER_PROFILE,
    evaluate_critical_number_fidelity,
)
from hvee.packs.asr.normalized_evaluation import (
    evaluate_normalized_transcript_pair,
)
from hvee.packs.asr.run04_scoring_precommitment import (
    RUN04_EXECUTION_SUCCESS_STATUS,
    RUN04_EXPECTED_GLOBAL_COMPLETE_PAIRS,
    RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS,
    RUN04_EXPECTED_OPERATOR_INTERRUPTION_SLOTS,
    RUN04_EXPECTED_RECORDINGS,
    RUN04_EXPECTED_SUCCESSFUL_TRANSCRIPTS,
    RUN04_EXPECTED_TERMINAL_SLOTS,
    RUN04_INPUT_ARTIFACTS,
    RUN04_MODEL_ROLES,
    RUN04_OPERATOR_INTERRUPTION_MODEL_ROLE,
    RUN04_OPERATOR_INTERRUPTION_SLOT_ORDINAL,
    RUN04_OPERATOR_INTERRUPTION_STATUS,
    build_run04_scoring_precommitment_v1,
)


class Run04ScoringError(RuntimeError):
    """Raised when frozen Run-04 scoring invariants are violated."""


_PLAN_RESULT_BINDING_FIELDS = (
    "audio_expected_bytes",
    "audio_file_sha256",
    "audio_relative_path",
    "beam_size",
    "compute_type",
    "dataset_id",
    "device",
    "execution_id",
    "execution_slot_ordinal",
    "lane_roles",
    "model_bin_sha256",
    "model_repository_id",
    "model_revision",
    "model_role",
    "recording_id",
    "recording_identity_sha256",
    "schema_version",
)

_PRE_SCORING_FALSE_FLAGS = (
    "cer_scoring_performed",
    "critical_fidelity_scoring_performed",
    "lane_evaluation_performed",
    "wer_scoring_performed",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Run04ScoringError(
            "value is not deterministic JSON"
        ) from exc


def _read_jsonl(file_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise Run04ScoringError(
                    f"blank JSONL row: {file_path}:{line_number}"
                )

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise Run04ScoringError(
                    f"invalid JSONL row: "
                    f"{file_path}:{line_number}"
                ) from exc

            if not isinstance(record, dict):
                raise Run04ScoringError(
                    f"JSONL row is not an object: "
                    f"{file_path}:{line_number}"
                )

            records.append(record)

    return records


def _require_text(
    record: dict[str, Any],
    field: str,
) -> str:
    value = record.get(field)

    if not isinstance(value, str) or not value:
        raise Run04ScoringError(
            f"required non-empty string field is invalid: {field}"
        )

    return value


def _classify_run04_execution_status(
    record: dict[str, Any],
) -> str:
    """Classify one result using the exact frozen status encoding."""

    status = record.get("status")
    transcript = record.get("raw_transcript_text")

    if status == RUN04_EXECUTION_SUCCESS_STATUS:
        if not isinstance(transcript, str):
            raise Run04ScoringError(
                "SUCCESS execution must carry transcript text"
            )

        return "successful_transcript"

    if (
        status == RUN04_OPERATOR_INTERRUPTION_STATUS
        and record.get("model_role")
        == RUN04_OPERATOR_INTERRUPTION_MODEL_ROLE
        and record.get("execution_slot_ordinal")
        == RUN04_OPERATOR_INTERRUPTION_SLOT_ORDINAL
        and transcript is None
        and record.get("score_eligible") is False
        and record.get(
            "operator_interruption_terminalization"
        )
        is True
        and record.get("model_quality_failure") is False
    ):
        return "governed_operator_interruption"

    raise Run04ScoringError(
        "execution result violates frozen Run-04 status contract: "
        f"status={status!r}, "
        f"role={record.get('model_role')!r}, "
        f"slot={record.get('execution_slot_ordinal')!r}"
    )


def validate_run04_execution_status_contract(
    result_records: Iterable[dict[str, Any]],
) -> dict[str, int]:
    """Require the exact SUCCESS/ERROR distribution before scoring."""

    counts = Counter(
        _classify_run04_execution_status(record)
        for record in result_records
    )

    expected = {
        "successful_transcript": (
            RUN04_EXPECTED_SUCCESSFUL_TRANSCRIPTS
        ),
        "governed_operator_interruption": (
            RUN04_EXPECTED_OPERATOR_INTERRUPTION_SLOTS
        ),
    }

    observed = {
        key: counts.get(key, 0)
        for key in sorted(expected)
    }

    if observed != expected:
        raise Run04ScoringError(
            "Run-04 execution status distribution changed: "
            f"observed={observed!r}, expected={expected!r}"
        )

    return observed


def _metric_direction(
    baseline: float,
    candidate: float,
) -> str:
    if candidate < baseline:
        return "candidate_lower"

    if candidate > baseline:
        return "candidate_higher"

    return "unchanged"


def score_transcript_pair(
    *,
    reference_text: str,
    reference_text_sha256: str,
    baseline_text: str,
    candidate_text: str,
    recording_id: str,
    recording_identity_sha256: str,
    dataset_id: str,
    lane_roles: dict[str, Any],
    baseline_metadata: dict[str, Any] | None = None,
    candidate_metadata: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Score one already-authorized complete baseline/candidate pair.

    Raw text is consumed transiently and is never returned.
    """

    for name, value in (
        ("reference_text", reference_text),
        ("baseline_text", baseline_text),
        ("candidate_text", candidate_text),
        ("recording_id", recording_id),
        ("recording_identity_sha256", recording_identity_sha256),
        ("dataset_id", dataset_id),
    ):
        if not isinstance(value, str):
            raise Run04ScoringError(f"{name} must be a string")

    actual_reference_sha = _sha256_text(reference_text)

    if actual_reference_sha != reference_text_sha256:
        raise Run04ScoringError(
            "reference text does not match its frozen SHA-256"
        )

    normalized_baseline = evaluate_normalized_transcript_pair(
        reference_text=reference_text,
        generated_text=baseline_text,
    )
    normalized_candidate = evaluate_normalized_transcript_pair(
        reference_text=reference_text,
        generated_text=candidate_text,
    )

    number_baseline = evaluate_critical_number_fidelity(
        reference_text=reference_text,
        generated_text=baseline_text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    )
    number_candidate = evaluate_critical_number_fidelity(
        reference_text=reference_text,
        generated_text=candidate_text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    )

    identifier_baseline = evaluate_critical_identifier_fidelity(
        reference_text=reference_text,
        generated_text=baseline_text,
        profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
    )
    identifier_candidate = evaluate_critical_identifier_fidelity(
        reference_text=reference_text,
        generated_text=candidate_text,
        profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
    )

    baseline_metadata = dict(baseline_metadata or {})
    candidate_metadata = dict(candidate_metadata or {})

    return {
        "schema_version": 1,
        "recording_id": recording_id,
        "recording_identity_sha256": recording_identity_sha256,
        "dataset_id": dataset_id,
        "lane_roles": lane_roles,
        "reference_text_sha256": reference_text_sha256,
        "baseline": {
            **baseline_metadata,
            "prediction_text_sha256": _sha256_text(baseline_text),
            "normalized_wer": normalized_baseline.wer,
            "normalized_cer": normalized_baseline.cer,
            "substitutions": normalized_baseline.substitutions,
            "insertions": normalized_baseline.insertions,
            "deletions": normalized_baseline.deletions,
            "critical_number_outcome": (
                number_baseline.outcome.value
            ),
            "critical_number_reference_count": len(
                number_baseline.reference_entities
            ),
            "critical_number_generated_count": len(
                number_baseline.generated_entities
            ),
            "critical_identifier_outcome": (
                identifier_baseline.outcome.value
            ),
            "critical_identifier_reference_count": len(
                identifier_baseline.reference_entities
            ),
            "critical_identifier_generated_count": len(
                identifier_baseline.generated_entities
            ),
        },
        "candidate": {
            **candidate_metadata,
            "prediction_text_sha256": _sha256_text(candidate_text),
            "normalized_wer": normalized_candidate.wer,
            "normalized_cer": normalized_candidate.cer,
            "substitutions": normalized_candidate.substitutions,
            "insertions": normalized_candidate.insertions,
            "deletions": normalized_candidate.deletions,
            "critical_number_outcome": (
                number_candidate.outcome.value
            ),
            "critical_number_reference_count": len(
                number_candidate.reference_entities
            ),
            "critical_number_generated_count": len(
                number_candidate.generated_entities
            ),
            "critical_identifier_outcome": (
                identifier_candidate.outcome.value
            ),
            "critical_identifier_reference_count": len(
                identifier_candidate.reference_entities
            ),
            "critical_identifier_generated_count": len(
                identifier_candidate.generated_entities
            ),
        },
        "direction": {
            "normalized_wer": _metric_direction(
                normalized_baseline.wer,
                normalized_candidate.wer,
            ),
            "normalized_cer": _metric_direction(
                normalized_baseline.cer,
                normalized_candidate.cer,
            ),
        },
    }


def _numeric_summary(
    rows: list[dict[str, object]],
    metric: str,
) -> dict[str, object]:
    baseline_values = [
        float(row["baseline"][metric])  # type: ignore[index]
        for row in rows
    ]
    candidate_values = [
        float(row["candidate"][metric])  # type: ignore[index]
        for row in rows
    ]

    deltas = [
        candidate - baseline
        for baseline, candidate in zip(
            baseline_values,
            candidate_values,
            strict=True,
        )
    ]

    directions = Counter(
        _metric_direction(baseline, candidate)
        for baseline, candidate in zip(
            baseline_values,
            candidate_values,
            strict=True,
        )
    )

    if not rows:
        return {
            "pair_count": 0,
            "baseline_mean": None,
            "candidate_mean": None,
            "mean_delta": None,
            "median_delta": None,
            "candidate_lower_count": 0,
            "candidate_higher_count": 0,
            "unchanged_count": 0,
        }

    return {
        "pair_count": len(rows),
        "baseline_mean": statistics.fmean(baseline_values),
        "candidate_mean": statistics.fmean(candidate_values),
        "mean_delta": statistics.fmean(deltas),
        "median_delta": statistics.median(deltas),
        "candidate_lower_count": directions["candidate_lower"],
        "candidate_higher_count": directions["candidate_higher"],
        "unchanged_count": directions["unchanged"],
    }


def _outcome_summary(
    rows: list[dict[str, object]],
    outcome_field: str,
) -> dict[str, object]:
    baseline = Counter(
        str(row["baseline"][outcome_field])  # type: ignore[index]
        for row in rows
    )
    candidate = Counter(
        str(row["candidate"][outcome_field])  # type: ignore[index]
        for row in rows
    )

    transitions = Counter(
        (
            str(row["baseline"][outcome_field]),  # type: ignore[index]
            str(row["candidate"][outcome_field]),  # type: ignore[index]
        )
        for row in rows
    )

    return {
        "baseline_outcome_counts": dict(sorted(baseline.items())),
        "candidate_outcome_counts": dict(sorted(candidate.items())),
        "transitions": [
            {
                "baseline": baseline_outcome,
                "candidate": candidate_outcome,
                "count": count,
            }
            for (
                baseline_outcome,
                candidate_outcome,
            ), count in sorted(transitions.items())
        ],
    }


def summarize_scored_pairs(
    rows: Iterable[dict[str, object]],
) -> dict[str, object]:
    materialized = list(rows)

    return {
        "pair_count": len(materialized),
        "normalized_wer": _numeric_summary(
            materialized,
            "normalized_wer",
        ),
        "normalized_cer": _numeric_summary(
            materialized,
            "normalized_cer",
        ),
        "critical_number": _outcome_summary(
            materialized,
            "critical_number_outcome",
        ),
        "critical_identifier": _outcome_summary(
            materialized,
            "critical_identifier_outcome",
        ),
    }


def summarize_all_lane_categories(
    rows: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    materialized = list(rows)

    grouped: dict[
        tuple[str, str],
        tuple[object, list[dict[str, object]]],
    ] = {}

    for row in materialized:
        lane_roles = row.get("lane_roles")

        if not isinstance(lane_roles, dict):
            raise Run04ScoringError(
                "scored pair lane_roles must be an object"
            )

        for lane_key, role_value in lane_roles.items():
            role_json = json.dumps(
                role_value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )

            grouping_key = (str(lane_key), role_json)

            if grouping_key not in grouped:
                grouped[grouping_key] = (
                    role_value,
                    [],
                )

            grouped[grouping_key][1].append(row)

    results: list[dict[str, object]] = []

    for (
        lane_key,
        role_json,
    ), (
        role_value,
        lane_rows,
    ) in sorted(grouped.items()):
        results.append(
            {
                "lane_key": lane_key,
                "role_value": role_value,
                "role_value_canonical_json": role_json,
                "summary": summarize_scored_pairs(lane_rows),
            }
        )

    return results


def validate_run04_lane_complete_pair_denominators(
    rows: Iterable[dict[str, object]],
) -> dict[str, dict[str, int]]:
    """Verify every frozen Run-04 lane-role complete-pair count."""

    materialized = list(rows)

    if len(materialized) != RUN04_EXPECTED_GLOBAL_COMPLETE_PAIRS:
        raise Run04ScoringError(
            "global complete-pair denominator changed before "
            "lane verification"
        )

    expected_lane_keys = set(
        RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS
    )

    observed = {
        lane_key: Counter()
        for lane_key in sorted(expected_lane_keys)
    }

    for row_index, row in enumerate(materialized):
        lane_roles = row.get("lane_roles")

        if not isinstance(lane_roles, dict):
            raise Run04ScoringError(
                f"scored pair {row_index} lane_roles must "
                "be an object"
            )

        if set(lane_roles) != expected_lane_keys:
            raise Run04ScoringError(
                f"scored pair {row_index} lane-role key set "
                "does not match the frozen precommitment"
            )

        for lane_key in sorted(expected_lane_keys):
            role_value = lane_roles[lane_key]

            if not isinstance(role_value, str):
                raise Run04ScoringError(
                    f"scored pair {row_index} lane role must "
                    f"be a string: {lane_key}"
                )

            expected_roles = (
                RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS[
                    lane_key
                ]
            )

            if role_value not in expected_roles:
                raise Run04ScoringError(
                    f"unexpected Run-04 lane role: "
                    f"{lane_key}={role_value!r}"
                )

            observed[lane_key][role_value] += 1

    canonical_observed = {
        lane_key: dict(
            sorted(role_counts.items())
        )
        for lane_key, role_counts in sorted(
            observed.items()
        )
    }

    canonical_expected = {
        lane_key: dict(
            sorted(role_counts.items())
        )
        for lane_key, role_counts in sorted(
            RUN04_EXPECTED_LANE_COMPLETE_PAIR_COUNTS.items()
        )
    }

    if canonical_observed != canonical_expected:
        raise Run04ScoringError(
            "Run-04 lane denominator mismatch: "
            f"observed={canonical_observed!r} "
            f"expected={canonical_expected!r}"
        )

    return canonical_observed


def _verify_input_artifact(
    *,
    evidence_root: Path,
    artifact_name: str,
) -> Path:
    definition = RUN04_INPUT_ARTIFACTS[artifact_name]
    relative_path = definition["relative_path"]

    if not isinstance(relative_path, str):
        raise Run04ScoringError(
            f"invalid precommitted path: {artifact_name}"
        )

    file_path = evidence_root / relative_path

    if not file_path.is_file():
        raise Run04ScoringError(
            f"missing frozen artifact: {artifact_name}"
        )

    actual_sha = _sha256_file(file_path)
    expected_sha = definition["sha256"]

    if actual_sha != expected_sha:
        raise Run04ScoringError(
            f"frozen artifact SHA-256 changed: {artifact_name}"
        )

    expected_rows = definition.get("rows")

    if expected_rows is not None:
        with file_path.open("rb") as handle:
            actual_rows = sum(1 for _ in handle)

        if actual_rows != expected_rows:
            raise Run04ScoringError(
                f"frozen artifact row count changed: "
                f"{artifact_name}"
            )

    return file_path


def _validate_plan_result_binding(
    *,
    plan_records: list[dict[str, Any]],
    result_records: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    if len(plan_records) != RUN04_EXPECTED_TERMINAL_SLOTS:
        raise Run04ScoringError(
            "execution plan row count is invalid"
        )

    if len(result_records) != RUN04_EXPECTED_TERMINAL_SLOTS:
        raise Run04ScoringError(
            "execution result row count is invalid"
        )

    plan_by_execution: dict[str, dict[str, Any]] = {}
    result_by_execution: dict[str, dict[str, Any]] = {}

    for record in plan_records:
        execution_id = _require_text(record, "execution_id")

        if execution_id in plan_by_execution:
            raise Run04ScoringError(
                "duplicate execution_id in execution plan"
            )

        role = record.get("model_role")

        if role not in RUN04_MODEL_ROLES:
            raise Run04ScoringError(
                f"unexpected model_role in plan: {role!r}"
            )

        if not isinstance(record.get("lane_roles"), dict):
            raise Run04ScoringError(
                "execution-plan lane_roles must be an object"
            )

        plan_by_execution[execution_id] = record

    for record in result_records:
        execution_id = _require_text(record, "execution_id")

        if execution_id in result_by_execution:
            raise Run04ScoringError(
                "duplicate execution_id in raw results"
            )

        if execution_id not in plan_by_execution:
            raise Run04ScoringError(
                "raw result does not belong to frozen plan"
            )

        plan = plan_by_execution[execution_id]

        for field in _PLAN_RESULT_BINDING_FIELDS:
            if record.get(field) != plan.get(field):
                raise Run04ScoringError(
                    f"plan/result binding changed: "
                    f"{execution_id}:{field}"
                )

        for flag in _PRE_SCORING_FALSE_FLAGS:
            if record.get(flag) is not False:
                raise Run04ScoringError(
                    f"pre-scoring flag unexpectedly true: "
                    f"{execution_id}:{flag}"
                )

        if record.get("provider_result_text_field") != "transcript":
            raise Run04ScoringError(
                "unexpected provider result text field"
            )

        result_by_execution[execution_id] = record

    if set(plan_by_execution) != set(result_by_execution):
        raise Run04ScoringError(
            "execution-plan/result identity sets differ"
        )

    role_counts = Counter(
        record["model_role"]
        for record in plan_records
    )

    if role_counts != {
        "baseline": RUN04_EXPECTED_RECORDINGS,
        "candidate": RUN04_EXPECTED_RECORDINGS,
    }:
        raise Run04ScoringError(
            f"unexpected model role counts: {role_counts!r}"
        )

    return plan_by_execution, result_by_execution


def _validate_references(
    reference_records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if len(reference_records) != RUN04_EXPECTED_RECORDINGS:
        raise Run04ScoringError(
            "reference record count is invalid"
        )

    by_recording: dict[str, dict[str, Any]] = {}

    for record in reference_records:
        recording_id = _require_text(
            record,
            "recording_id",
        )
        reference_text = _require_text(
            record,
            "reference_text",
        )
        reference_sha = _require_text(
            record,
            "reference_text_sha256",
        )

        if _sha256_text(reference_text) != reference_sha:
            raise Run04ScoringError(
                f"reference text SHA mismatch: {recording_id}"
            )

        if recording_id in by_recording:
            raise Run04ScoringError(
                f"duplicate reference recording: {recording_id}"
            )

        by_recording[recording_id] = record

    return by_recording


def _build_complete_pairs(
    *,
    plan_records: list[dict[str, Any]],
    result_by_execution: dict[str, dict[str, Any]],
    reference_by_recording: dict[str, dict[str, Any]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
]:
    plan_by_recording: dict[
        str,
        dict[str, dict[str, Any]],
    ] = defaultdict(dict)

    for plan in plan_records:
        recording_id = _require_text(
            plan,
            "recording_id",
        )
        role = _require_text(
            plan,
            "model_role",
        )

        if role in plan_by_recording[recording_id]:
            raise Run04ScoringError(
                f"duplicate {role} plan for {recording_id}"
            )

        plan_by_recording[recording_id][role] = plan

    if len(plan_by_recording) != RUN04_EXPECTED_RECORDINGS:
        raise Run04ScoringError(
            "unexpected number of planned recordings"
        )

    if set(plan_by_recording) != set(reference_by_recording):
        raise Run04ScoringError(
            "reference and execution recording sets differ"
        )

    scored_rows: list[dict[str, object]] = []
    excluded_rows: list[dict[str, object]] = []

    ordered_recording_ids = sorted(
        plan_by_recording,
        key=lambda recording_id: (
            int(
                reference_by_recording[recording_id][
                    "source_index_record_ordinal"
                ]
            ),
            recording_id,
        ),
    )

    for recording_id in ordered_recording_ids:
        role_plans = plan_by_recording[recording_id]

        if set(role_plans) != set(RUN04_MODEL_ROLES):
            raise Run04ScoringError(
                f"incomplete model-role plan: {recording_id}"
            )

        baseline_plan = role_plans["baseline"]
        candidate_plan = role_plans["candidate"]

        baseline_result = result_by_execution[
            baseline_plan["execution_id"]
        ]
        candidate_result = result_by_execution[
            candidate_plan["execution_id"]
        ]

        reference = reference_by_recording[recording_id]

        for plan in (baseline_plan, candidate_plan):
            if (
                plan["recording_identity_sha256"]
                != reference["recording_identity_sha256"]
            ):
                raise Run04ScoringError(
                    "recording identity differs from reference"
                )

            if plan["dataset_id"] != reference["dataset_id"]:
                raise Run04ScoringError(
                    "dataset identity differs from reference"
                )

        if baseline_plan["lane_roles"] != candidate_plan["lane_roles"]:
            raise Run04ScoringError(
                "baseline/candidate lane roles differ"
            )

        baseline_text = baseline_result.get(
            "raw_transcript_text"
        )
        candidate_text = candidate_result.get(
            "raw_transcript_text"
        )

        if baseline_text is None or candidate_text is None:
            missing: list[
                tuple[str, dict[str, Any]]
            ] = []

            if baseline_text is None:
                missing.append(
                    ("baseline", baseline_result)
                )

            if candidate_text is None:
                missing.append(
                    ("candidate", candidate_result)
                )

            if len(missing) != 1:
                raise Run04ScoringError(
                    "unexpected multi-side missing pair"
                )

            missing_role, missing_result = missing[0]

            if (
                missing_role
                != RUN04_OPERATOR_INTERRUPTION_MODEL_ROLE
                or missing_result.get("execution_slot_ordinal")
                != RUN04_OPERATOR_INTERRUPTION_SLOT_ORDINAL
                or missing_result.get("status")
                != RUN04_OPERATOR_INTERRUPTION_STATUS
                or missing_result.get("score_eligible") is not False
                or missing_result.get(
                    "operator_interruption_terminalization"
                )
                is not True
                or missing_result.get("model_quality_failure")
                is not False
            ):
                raise Run04ScoringError(
                    "missing transcript is not the governed "
                    "slot-293 interruption"
                )

            excluded_rows.append(
                {
                    "recording_id": recording_id,
                    "recording_identity_sha256": (
                        reference["recording_identity_sha256"]
                    ),
                    "missing_model_role": missing_role,
                    "execution_slot_ordinal": (
                        RUN04_OPERATOR_INTERRUPTION_SLOT_ORDINAL
                    ),
                    "quality_semantics": (
                        "missing_quality_evidence"
                    ),
                    "excluded_from_model_quality_denominator": True,
                    "score_exclusion_reason": (
                        missing_result.get(
                            "score_exclusion_reason"
                        )
                    ),
                }
            )
            continue

        if not isinstance(baseline_text, str):
            raise Run04ScoringError(
                "baseline transcript must be text"
            )

        if not isinstance(candidate_text, str):
            raise Run04ScoringError(
                "candidate transcript must be text"
            )

        _classify_run04_execution_status(
            baseline_result
        )
        _classify_run04_execution_status(
            candidate_result
        )

        scored_rows.append(
            score_transcript_pair(
                reference_text=reference["reference_text"],
                reference_text_sha256=(
                    reference["reference_text_sha256"]
                ),
                baseline_text=baseline_text,
                candidate_text=candidate_text,
                recording_id=recording_id,
                recording_identity_sha256=(
                    reference["recording_identity_sha256"]
                ),
                dataset_id=reference["dataset_id"],
                lane_roles=dict(
                    baseline_plan["lane_roles"]
                ),
                baseline_metadata={
                    "execution_id": (
                        baseline_result["execution_id"]
                    ),
                    "execution_slot_ordinal": (
                        baseline_result[
                            "execution_slot_ordinal"
                        ]
                    ),
                    "model_repository_id": (
                        baseline_result[
                            "model_repository_id"
                        ]
                    ),
                    "model_revision": (
                        baseline_result["model_revision"]
                    ),
                    "model_bin_sha256": (
                        baseline_result["model_bin_sha256"]
                    ),
                },
                candidate_metadata={
                    "execution_id": (
                        candidate_result["execution_id"]
                    ),
                    "execution_slot_ordinal": (
                        candidate_result[
                            "execution_slot_ordinal"
                        ]
                    ),
                    "model_repository_id": (
                        candidate_result[
                            "model_repository_id"
                        ]
                    ),
                    "model_revision": (
                        candidate_result["model_revision"]
                    ),
                    "model_bin_sha256": (
                        candidate_result["model_bin_sha256"]
                    ),
                },
            )
        )

    if len(scored_rows) != RUN04_EXPECTED_GLOBAL_COMPLETE_PAIRS:
        raise Run04ScoringError(
            "complete-pair denominator does not match precommitment"
        )

    if len(excluded_rows) != 1:
        raise Run04ScoringError(
            "operator-interruption exclusion count is not one"
        )

    return scored_rows, excluded_rows


def score_frozen_run04_public_v2(
    *,
    evidence_root: Path,
    output_dir: Path,
    scoring_code_commit: str,
) -> dict[str, object]:
    """Run the precommitted scoring adapter on the frozen Run-04 evidence.

    This is the model-quality scoring boundary. Do not call this function
    until the scoring-precommitment code has been committed and sealed.
    """

    if not isinstance(scoring_code_commit, str) or len(
        scoring_code_commit
    ) != 40:
        raise Run04ScoringError(
            "scoring_code_commit must be a full Git SHA"
        )

    if output_dir.exists():
        raise Run04ScoringError(
            "scoring output directory already exists"
        )

    precommitment = build_run04_scoring_precommitment_v1()

    verified_paths = {
        artifact_name: _verify_input_artifact(
            evidence_root=evidence_root,
            artifact_name=artifact_name,
        )
        for artifact_name in RUN04_INPUT_ARTIFACTS
    }

    # Semantic JSONL parsing occurs only after every input artifact hash
    # has passed the precommitted identity gate.
    plan_records = _read_jsonl(
        verified_paths["execution_plan"]
    )
    result_records = _read_jsonl(
        verified_paths["raw_execution_results"]
    )
    reference_records = _read_jsonl(
        verified_paths["reference_records"]
    )

    (
        _,
        result_by_execution,
    ) = _validate_plan_result_binding(
        plan_records=plan_records,
        result_records=result_records,
    )

    execution_status_counts = (
        validate_run04_execution_status_contract(
            result_records
        )
    )

    reference_by_recording = _validate_references(
        reference_records
    )

    scored_rows, excluded_rows = _build_complete_pairs(
        plan_records=plan_records,
        result_by_execution=result_by_execution,
        reference_by_recording=reference_by_recording,
    )

    lane_complete_pair_counts = (
        validate_run04_lane_complete_pair_denominators(
            scored_rows
        )
    )

    global_summary = summarize_scored_pairs(scored_rows)
    lane_summaries = summarize_all_lane_categories(
        scored_rows
    )

    summary = {
        "schema_version": 1,
        "precommitment": {
            "key": precommitment.payload[
                "precommitment"
            ]["key"],
            "version": precommitment.payload[
                "precommitment"
            ]["version"],
            "sha256": precommitment.sha256,
            "scoring_code_commit": scoring_code_commit,
        },
        "input_artifacts": {
            key: {
                "relative_path": definition[
                    "relative_path"
                ],
                "sha256": definition["sha256"],
            }
            for key, definition in sorted(
                RUN04_INPUT_ARTIFACTS.items()
            )
        },
        "accounting": {
            "terminal_slots": RUN04_EXPECTED_TERMINAL_SLOTS,
            "recordings": RUN04_EXPECTED_RECORDINGS,
            "execution_status_counts": (
                execution_status_counts
            ),
            "complete_pairs": len(scored_rows),
            "excluded_pairs": len(excluded_rows),
            "lane_complete_pair_counts": (
                lane_complete_pair_counts
            ),
        },
        "excluded_pairs": excluded_rows,
        "global": global_summary,
        "lane_role_categories": lane_summaries,
        "authority": {
            "production_qualified": False,
            "release_decision_issued": False,
            "certification_issued": False,
        },
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    pair_file = output_dir / "paired-quality-results.jsonl"
    summary_file = output_dir / "scoring-summary.json"

    with pair_file.open(
        "wb",
    ) as handle:
        for row in scored_rows:
            handle.write(_canonical_json_bytes(row))
            handle.write(b"\n")

    summary_file.write_bytes(
        _canonical_json_bytes(summary) + b"\n"
    )

    output_hashes = {
        "paired-quality-results.jsonl": (
            _sha256_file(pair_file)
        ),
        "scoring-summary.json": _sha256_file(
            summary_file
        ),
    }

    freeze = {
        "schema_version": 1,
        "precommitment_sha256": precommitment.sha256,
        "scoring_code_commit": scoring_code_commit,
        "input_artifact_sha256": {
            key: definition["sha256"]
            for key, definition in sorted(
                RUN04_INPUT_ARTIFACTS.items()
            )
        },
        "output_artifact_sha256": output_hashes,
        "raw_reference_text_persisted": False,
        "raw_prediction_text_persisted": False,
        "hidden_holdout_opened": False,
        "asr_execution_performed": False,
        "release_decision_issued": False,
    }

    freeze_file = output_dir / "freeze-manifest.json"
    freeze_file.write_bytes(
        _canonical_json_bytes(freeze) + b"\n"
    )

    return {
        "precommitment_sha256": precommitment.sha256,
        "complete_pairs": len(scored_rows),
        "excluded_pairs": len(excluded_rows),
        "paired_results_sha256": output_hashes[
            "paired-quality-results.jsonl"
        ],
        "summary_sha256": output_hashes[
            "scoring-summary.json"
        ],
        "freeze_manifest_sha256": _sha256_file(
            freeze_file
        ),
        "output_dir": str(output_dir),
    }


__all__ = [
    "Run04ScoringError",
    "score_frozen_run04_public_v2",
    "score_transcript_pair",
    "summarize_all_lane_categories",
    "summarize_scored_pairs",
    "validate_run04_execution_status_contract",
    "validate_run04_lane_complete_pair_denominators",
]
