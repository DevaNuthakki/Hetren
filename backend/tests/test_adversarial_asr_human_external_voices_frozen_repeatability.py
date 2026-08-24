from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest

import app.adversarial_asr_human_external_voices_frozen_repeatability as frozen
from app.adversarial_asr_human_external_voices_frozen_repeatability import (
    ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_KEY,
    ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_VERSION,
    ASRAdversarialVOiCESFrozenRepeatabilityError,
    evaluate_asr_adversarial_voices_frozen_repeatability_files_v1,
    evaluate_asr_adversarial_voices_frozen_repeatability_v1,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _encode(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _pair(index: int) -> dict[str, object]:
    pair = (index // 2) + 1
    return {
        "source_key": [pair, pair + 100, pair + 200],
        "room": "rm1",
        "microphone_id": 1,
        "angle_degrees": 10,
    }


def _case(*, run: int, role: str, index: int) -> dict[str, object]:
    model = frozen._INNER_MODELS[role]
    return {
        "role": role,
        "provider_key": model["provider_key"],
        "model_key": model["model_key"],
        "case_id": f"voices-case-{index:02d}",
        "arm": "babble" if index % 2 == 0 else "control",
        "pair_key": _pair(index),
        "fixed_inputs": {
            "audio_asset_sha256": _sha(f"audio-{index}"),
            "reference_transcript_sha256": _sha(f"reference-{index}"),
            "normalized_reference_utf8_sha256": _sha(
                f"normalized-reference-{index}"
            ),
        },
        "outputs": {
            "execution_environment_sha256": (
                frozen._EXECUTION_ENVIRONMENT_SHA256S[role]
            ),
            "execution_evidence_sha256": _sha(
                f"execution-{run}-{role}-{index}"
            ),
            "generated_transcript_sha256": _sha(
                f"generated-{role}-{index}"
            ),
            "normalized_generated_utf8_sha256": _sha(
                f"normalized-generated-{role}-{index}"
            ),
        },
        "metrics": {
            "wer": (0.10 if role == "baseline" else 0.05) + index / 1000,
            "cer": (0.08 if role == "baseline" else 0.03) + index / 2000,
        },
    }


def _run(index: int) -> dict[str, object]:
    units = [
        _case(run=index, role=role, index=case_index)
        for role in ("baseline", "candidate")
        for case_index in range(32)
    ]
    return {
        "run_id": frozen.B11F_RUN_IDS[index - 1],
        "execution_sha256": frozen.B11F_B9_EXECUTION_SHA256S[index - 1],
        "upstream": {
            "matched_control_suite_sha256": (
                frozen.B11F_MATCHED_CONTROL_SUITE_SHA256
            ),
            "adversarial_suite_evidence_sha256": (
                frozen.B11F_ADVERSARIAL_SUITE_EVIDENCE_SHA256
            ),
        },
        "models": deepcopy(frozen._RUN_MODELS[index - 1]),
        "case_model_units": units,
        "comparison_signals": {
            "general_accuracy_candidate_minus_baseline": {
                "wer": -0.05,
                "cer": -0.05,
            },
            "matched_control_robustness_candidate_minus_baseline": {
                "wer": 0.0,
                "cer": 0.0,
            },
        },
    }


def _checkpoint(run: dict[str, object], run_sha256: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "artifact": {
            "key": "hetren.asr.b11f-real-repeatability-run-observation",
            "type": "content-free-complete-b9-run-observation",
            "version": "1.0.0",
        },
        "source_code": deepcopy(frozen._SOURCE_CODE),
        "execution_protocol": deepcopy(frozen._EXECUTION_PROTOCOL),
        "models": deepcopy(frozen._MODELS),
        "runtime_environment": deepcopy(frozen._RUNTIME_ENVIRONMENT),
        "runtime_environment_sha256": (
            frozen.B11F_RUNTIME_ENVIRONMENT_SHA256
        ),
        "run_observation": run,
        "run_observation_sha256": run_sha256,
        "evidence_boundary": deepcopy(frozen._CHECKPOINT_BOUNDARY),
    }


def _build_pinned_evidence(monkeypatch):
    runs = tuple(_run(value) for value in range(1, 4))
    observation_sha256s = tuple(
        hashlib.sha256(frozen._canonical_json_bytes(run)).hexdigest()
        for run in runs
    )
    monkeypatch.setattr(
        frozen,
        "B11F_RUN_OBSERVATION_SHA256S",
        observation_sha256s,
    )
    units, aggregate, status = frozen._derive_repeatability(runs)
    inner = {
        "schema_version": 1,
        "artifact": deepcopy(frozen._INNER_ARTIFACT),
        "protocol": deepcopy(frozen._INNER_PROTOCOL),
        "upstream": {
            "matched_control_suite_sha256": (
                frozen.B11F_MATCHED_CONTROL_SUITE_SHA256
            ),
            "adversarial_suite_evidence_sha256": (
                frozen.B11F_ADVERSARIAL_SUITE_EVIDENCE_SHA256
            ),
            "ordered_run_observation_sha256s": list(observation_sha256s),
            "ordered_b9_execution_sha256s": list(
                frozen.B11F_B9_EXECUTION_SHA256S
            ),
        },
        "status": status,
        "models": deepcopy(frozen._INNER_MODELS),
        "population": {
            "run_count": 3,
            "model_count": 2,
            "case_count_per_model": 32,
            "case_model_unit_count": 64,
            "execution_count": 192,
            "ordered_run_ids": list(frozen.B11F_RUN_IDS),
        },
        "runs": list(runs),
        "repeatability": {
            "engineer_metrics": deepcopy(frozen._ENGINEER_METRICS),
            "aggregate": aggregate,
            "case_model_units": list(units),
        },
        "evidence_boundary": deepcopy(frozen._INNER_BOUNDARY),
    }
    repeatability_sha256 = hashlib.sha256(
        frozen._canonical_json_bytes(inner)
    ).hexdigest()
    monkeypatch.setattr(
        frozen,
        "B11F_REPEATABILITY_SHA256",
        repeatability_sha256,
    )
    checkpoints = tuple(
        _encode(_checkpoint(run, observation_sha256s[index]))
        for index, run in enumerate(runs)
    )
    checkpoint_sha256s = tuple(
        hashlib.sha256(value).hexdigest() for value in checkpoints
    )
    monkeypatch.setattr(
        frozen,
        "B11F_RUN_CHECKPOINT_BYTES",
        tuple(len(value) for value in checkpoints),
    )
    monkeypatch.setattr(
        frozen,
        "B11F_RUN_CHECKPOINT_FILE_SHA256S",
        checkpoint_sha256s,
    )
    root = {
        "schema_version": 1,
        "artifact": {
            "key": frozen.B11F_ARTIFACT_KEY,
            "type": frozen.B11F_ARTIFACT_TYPE,
            "version": frozen.B11F_ARTIFACT_VERSION,
        },
        "source_code": deepcopy(frozen._SOURCE_CODE),
        "execution_protocol": deepcopy(frozen._EXECUTION_PROTOCOL),
        "models": deepcopy(frozen._MODELS),
        "runtime_environment": deepcopy(frozen._RUNTIME_ENVIRONMENT),
        "runtime_environment_sha256": (
            frozen.B11F_RUNTIME_ENVIRONMENT_SHA256
        ),
        "upstream": {
            "adversarial_suite_evidence_sha256": (
                frozen.B11F_ADVERSARIAL_SUITE_EVIDENCE_SHA256
            ),
            "matched_control_projection_sha256": (
                frozen.B11F_MATCHED_CONTROL_PROJECTION_SHA256
            ),
            "matched_control_suite_sha256": (
                frozen.B11F_MATCHED_CONTROL_SUITE_SHA256
            ),
            "ordered_run_checkpoint_file_sha256s": list(
                checkpoint_sha256s
            ),
            "ordered_run_observation_sha256s": list(observation_sha256s),
        },
        "repeatability": inner,
        "repeatability_sha256": repeatability_sha256,
        "evidence_boundary": deepcopy(frozen._ROOT_BOUNDARY),
    }
    artifact = _encode(root)
    monkeypatch.setattr(frozen, "B11F_ARTIFACT_BYTES", len(artifact))
    monkeypatch.setattr(
        frozen,
        "B11F_ARTIFACT_SHA256",
        hashlib.sha256(artifact).hexdigest(),
    )
    return artifact, checkpoints, root


def _repin_artifact(monkeypatch, root: dict[str, object]) -> bytes:
    artifact = _encode(root)
    monkeypatch.setattr(frozen, "B11F_ARTIFACT_BYTES", len(artifact))
    monkeypatch.setattr(
        frozen,
        "B11F_ARTIFACT_SHA256",
        hashlib.sha256(artifact).hexdigest(),
    )
    return artifact


def test_constants_pin_the_real_b11f_evidence():
    assert ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_FROZEN_REPEATABILITY_KEY.endswith(
        "frozen-real-repeatability-verification"
    )
    assert frozen.B11F_ARTIFACT_BYTES == 501_439
    assert frozen.B11F_ARTIFACT_SHA256 == (
        "d4e68272debfdbc1e1980ef798e3a596"
        "eb11c14b657a6491c69ac3a283bf41fb"
    )
    assert frozen.B11F_REPEATABILITY_SHA256 == (
        "0291eedfd15f885b48176939c364316c"
        "c95228bb9fff612b41dc0e035950b420"
    )
    assert frozen.B11F_RUN_CHECKPOINT_BYTES == (91_940, 91_940, 91_940)


def test_exact_pinned_files_recompute_all_engineer_metrics(monkeypatch):
    artifact, checkpoints, _ = _build_pinned_evidence(monkeypatch)

    bundle = evaluate_asr_adversarial_voices_frozen_repeatability_v1(
        artifact_bytes=artifact,
        run_checkpoint_bytes=checkpoints,
    )
    result = bundle.payload["result"]

    assert result["status"] == "stable"
    assert result["population"] == {
        "run_count": 3,
        "model_count": 2,
        "case_count_per_model": 32,
        "case_model_unit_count": 64,
        "execution_count": 192,
    }
    assert result["overall"]["exact_transcript_repeatability"][
        "score_percent"
    ] == 100.0
    assert result["overall"]["wer_drift_envelope"] == {
        "maximum": 0.0,
        "macro_mean": 0.0,
    }
    assert all(
        value["metric_stable"] and value["direction_stable"]
        for value in result["comparison_signal_stability"].values()
    )
    assert len(bundle.sha256) == 64


def test_parser_rejects_duplicate_keys():
    with pytest.raises(
        ASRAdversarialVOiCESFrozenRepeatabilityError,
        match="repeated key",
    ):
        frozen._parse_json(b'{"schema_version":1,"schema_version":1}', name="x")


def test_raw_artifact_tampering_fails_before_projection(monkeypatch):
    artifact, checkpoints, _ = _build_pinned_evidence(monkeypatch)
    changed = artifact.replace(b'"status": "stable"', b'"status": "broken"', 1)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenRepeatabilityError,
        match="artifact (byte length|file identity)",
    ):
        evaluate_asr_adversarial_voices_frozen_repeatability_v1(
            artifact_bytes=changed,
            run_checkpoint_bytes=checkpoints,
        )


def test_independently_repinned_source_tampering_still_fails(monkeypatch):
    _, checkpoints, root = _build_pinned_evidence(monkeypatch)
    root["source_code"]["git_head"] = "0" * 40
    artifact = _repin_artifact(monkeypatch, root)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenRepeatabilityError,
        match="source_code changed",
    ):
        evaluate_asr_adversarial_voices_frozen_repeatability_v1(
            artifact_bytes=artifact,
            run_checkpoint_bytes=checkpoints,
        )


def test_independently_repinned_aggregate_tampering_still_fails(monkeypatch):
    _, checkpoints, root = _build_pinned_evidence(monkeypatch)
    aggregate = root["repeatability"]["repeatability"]["aggregate"]
    aggregate["overall"]["wer_stability"]["successful_count"] = 63
    changed_repeatability_sha256 = hashlib.sha256(
        frozen._canonical_json_bytes(root["repeatability"])
    ).hexdigest()
    root["repeatability_sha256"] = changed_repeatability_sha256
    monkeypatch.setattr(
        frozen,
        "B11F_REPEATABILITY_SHA256",
        changed_repeatability_sha256,
    )
    artifact = _repin_artifact(monkeypatch, root)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenRepeatabilityError,
        match="derived aggregate changed",
    ):
        evaluate_asr_adversarial_voices_frozen_repeatability_v1(
            artifact_bytes=artifact,
            run_checkpoint_bytes=checkpoints,
        )


def test_repinned_checkpoint_link_tampering_still_fails(monkeypatch):
    _, checkpoints, root = _build_pinned_evidence(monkeypatch)
    changed = json.loads(checkpoints[0])
    changed["run_observation"]["execution_sha256"] = _sha("changed")
    changed_raw = _encode(changed)
    changed_checkpoints = (changed_raw, checkpoints[1], checkpoints[2])
    changed_hashes = (
        hashlib.sha256(changed_raw).hexdigest(),
        *frozen.B11F_RUN_CHECKPOINT_FILE_SHA256S[1:],
    )
    monkeypatch.setattr(
        frozen,
        "B11F_RUN_CHECKPOINT_BYTES",
        (len(changed_raw), *frozen.B11F_RUN_CHECKPOINT_BYTES[1:]),
    )
    monkeypatch.setattr(
        frozen,
        "B11F_RUN_CHECKPOINT_FILE_SHA256S",
        changed_hashes,
    )
    root["upstream"]["ordered_run_checkpoint_file_sha256s"] = list(
        changed_hashes
    )
    artifact = _repin_artifact(monkeypatch, root)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenRepeatabilityError,
        match="checkpoint run_observation changed",
    ):
        evaluate_asr_adversarial_voices_frozen_repeatability_v1(
            artifact_bytes=artifact,
            run_checkpoint_bytes=changed_checkpoints,
        )


def test_checkpoint_order_is_part_of_the_frozen_identity(monkeypatch):
    artifact, checkpoints, _ = _build_pinned_evidence(monkeypatch)

    with pytest.raises(
        ASRAdversarialVOiCESFrozenRepeatabilityError,
        match="checkpoint (byte length|file identity)",
    ):
        evaluate_asr_adversarial_voices_frozen_repeatability_v1(
            artifact_bytes=artifact,
            run_checkpoint_bytes=(checkpoints[1], checkpoints[0], checkpoints[2]),
        )


def test_file_api_does_not_embed_absolute_paths(monkeypatch, tmp_path: Path):
    artifact, checkpoints, _ = _build_pinned_evidence(monkeypatch)
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_bytes(artifact)
    checkpoint_paths = []
    for index, raw in enumerate(checkpoints, start=1):
        path = tmp_path / f"checkpoint-{index}.json"
        path.write_bytes(raw)
        checkpoint_paths.append(path)

    bundle = evaluate_asr_adversarial_voices_frozen_repeatability_files_v1(
        artifact_path=artifact_path,
        run_checkpoint_paths=tuple(checkpoint_paths),
    )
    encoded = frozen._canonical_json_bytes(bundle.payload)

    assert str(tmp_path).encode("utf-8") not in encoded
    assert b".wav" not in encoded
    assert b"generated transcript text" not in encoded


def test_bundle_is_frozen_and_refuses_unsupported_authority(monkeypatch):
    artifact, checkpoints, _ = _build_pinned_evidence(monkeypatch)
    bundle = evaluate_asr_adversarial_voices_frozen_repeatability_v1(
        artifact_bytes=artifact,
        run_checkpoint_bytes=checkpoints,
    )

    with pytest.raises((FrozenInstanceError, AttributeError)):
        bundle.artifact_bytes = b"changed"
    with pytest.raises(
        ASRAdversarialVOiCESFrozenRepeatabilityError,
        match="cross-host reproducibility",
    ):
        bundle.require_reproducibility_verified()
    with pytest.raises(
        ASRAdversarialVOiCESFrozenRepeatabilityError,
        match="no qualification",
    ):
        bundle.require_repeatability_qualification()


@pytest.mark.parametrize(
    ("artifact", "checkpoints", "match"),
    [
        ("not-bytes", (), "artifact must be immutable bytes"),
        (b"{}", [], "exactly three immutable checkpoint files"),
        (b"{}", (b"{}", b"{}"), "exactly three immutable checkpoint files"),
    ],
)
def test_public_api_rejects_invalid_input_types(artifact, checkpoints, match):
    with pytest.raises(
        ASRAdversarialVOiCESFrozenRepeatabilityError,
        match=match,
    ):
        evaluate_asr_adversarial_voices_frozen_repeatability_v1(
            artifact_bytes=artifact,
            run_checkpoint_bytes=checkpoints,
        )
