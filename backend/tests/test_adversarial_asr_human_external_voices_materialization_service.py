from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

import app.adversarial_asr_human_external_voices_materialization_service as service
from app.adversarial_asr_human_external_voices_materialization_service import (
    ASRAdversarialVOiCESMaterializationDefinition,
    ASRAdversarialVOiCESMaterializationError,
    ASRAdversarialVOiCESMaterializedEvidence,
    ASRAdversarialVOiCESMaterializedMedia,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
)


SOURCE_AUDIO = (
    b"deterministic-voices-source-audio"
)

CAPTURE_AUDIO = (
    b"deterministic-voices-capture-audio"
)

SOURCE_KEY = (
    1,
    2,
    3,
)


def _sha256(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _canonical(
    value: object,
) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode(
        "utf-8"
    )


def _write_bytes(
    path: Path,
    value: bytes,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        value
    )


def _write_canonical_json(
    path: Path,
    value: object,
) -> bytes:
    raw = _canonical(
        value
    )

    _write_bytes(
        path,
        raw,
    )

    return raw


def _fixture(
    tmp_path: Path,
):
    root = (
        tmp_path
        / "evidence"
    )

    root.mkdir()

    materialization_root = (
        root
        / "materialized"
    )

    source_path = (
        materialization_root
        / "source"
        / "source.wav"
    )

    capture_path = (
        materialization_root
        / "capture"
        / "capture.wav"
    )

    _write_bytes(
        source_path,
        SOURCE_AUDIO,
    )

    _write_bytes(
        capture_path,
        CAPTURE_AUDIO,
    )

    source_relative = (
        "source/source.wav"
    )

    capture_relative = (
        "capture/capture.wav"
    )

    selection = {
        "artifact": {
            "key": "fixture-selection",
            "schema_version": 1,
            "version": "1.0.0",
        },
        "selection": {
            "partition": "train",
            "selected_source_count": 1,
            "selected_capture_count": 1,
            "captures_per_source": 1,
            "required_constant_angle_degrees": 10,
            "selected_source_keys": [
                list(
                    SOURCE_KEY
                ),
            ],
        },
        "sources": [
            {
                "source_key": list(
                    SOURCE_KEY
                ),
                "capture_count": 1,
                "constant_angle_degrees": 10,
                "source_path": (
                    source_relative
                ),
            },
        ],
        "captures": [
            {
                "source_key": list(
                    SOURCE_KEY
                ),
                "degrees": 10,
                "room": "rm1",
                "distractor": "none",
                "mic_id": 1,
                "filename": (
                    capture_relative
                ),
            },
        ],
    }

    selection_path = (
        root
        / "selection.json"
    )

    selection_raw = (
        _write_canonical_json(
            selection_path,
            selection,
        )
    )

    selection_sha256 = (
        _sha256(
            selection_raw
        )
    )

    manifest_files = [
        {
            "relative_path": (
                source_relative
            ),
            "sha256": (
                _sha256(
                    SOURCE_AUDIO
                )
            ),
            "bytes": len(
                SOURCE_AUDIO
            ),
            "kind": "source",
            "source_key": list(
                SOURCE_KEY
            ),
        },
        {
            "relative_path": (
                capture_relative
            ),
            "sha256": (
                _sha256(
                    CAPTURE_AUDIO
                )
            ),
            "bytes": len(
                CAPTURE_AUDIO
            ),
            "kind": "capture",
            "source_key": list(
                SOURCE_KEY
            ),
        },
    ]

    total_bytes = (
        len(
            SOURCE_AUDIO
        )
        + len(
            CAPTURE_AUDIO
        )
    )

    manifest = {
        "artifact": {
            "key": "fixture-manifest",
            "schema_version": 1,
            "version": "1.0.0",
        },
        "selection": {
            "sha256": (
                selection_sha256
            ),
            "bytes": len(
                selection_raw
            ),
        },
        "materialization": {
            "source_file_count": 1,
            "capture_file_count": 1,
            "total_file_count": 2,
            "total_bytes": (
                total_bytes
            ),
        },
        "files": (
            manifest_files
        ),
        "evidence_boundary": {
            "allowlist_only_materialization": True,
            "source_archive_member_bytes_hashed": True,
            "raw_audio_committed_to_repository": False,
            "audio_semantics_verified": False,
            "asr_execution_verified": False,
        },
    }

    manifest_path = (
        materialization_root
        / "manifest.json"
    )

    manifest_raw = (
        _write_canonical_json(
            manifest_path,
            manifest,
        )
    )

    manifest_sha256 = (
        _sha256(
            manifest_raw
        )
    )

    observations = [
        {
            "relative_path": (
                source_relative
            ),
            "sha256": (
                _sha256(
                    SOURCE_AUDIO
                )
            ),
            "bytes": len(
                SOURCE_AUDIO
            ),
            "kind": "source",
            "source_key": list(
                SOURCE_KEY
            ),
            "codec_name": (
                "pcm_s16le"
            ),
            "sample_rate_hz": 16_000,
            "channels": 1,
            "bits_per_sample": 16,
            "sample_width_bytes": 2,
            "sample_count": 100,
            "duration_seconds": "0.00625",
        },
        {
            "relative_path": (
                capture_relative
            ),
            "sha256": (
                _sha256(
                    CAPTURE_AUDIO
                )
            ),
            "bytes": len(
                CAPTURE_AUDIO
            ),
            "kind": "capture",
            "source_key": list(
                SOURCE_KEY
            ),
            "codec_name": (
                "pcm_s16le"
            ),
            "sample_rate_hz": 16_000,
            "channels": 1,
            "bits_per_sample": 16,
            "sample_width_bytes": 2,
            "sample_count": 100,
            "duration_seconds": "0.00625",
        },
    ]

    observation_sha256 = (
        _sha256(
            _canonical(
                observations
            )
        )
    )

    report = {
        "artifact": {
            "key": "fixture-report",
            "schema_version": 1,
            "version": "1.0.0",
        },
        "inputs": {
            "selection_sha256": (
                selection_sha256
            ),
            "materialization_manifest_sha256": (
                manifest_sha256
            ),
        },
        "observations": (
            observations
        ),
        "verification": {
            "source_file_count": 1,
            "capture_file_count": 1,
            "verified_file_count": 2,
            "total_bytes": (
                total_bytes
            ),
            "controlled_condition_lattice_verified": True,
            "post_probe_hash_stability": True,
            "observation_sha256": (
                observation_sha256
            ),
        },
        "evidence_boundary": {
            "external_development_evidence": True,
            "audio_bytes_verified": True,
            "media_probe_verified": True,
            "source_declared_transcripts_bound": True,
            "spoken_content_independently_verified": False,
            "asr_execution_verified": False,
            "live_human_in_room_diversity_established": False,
            "microphone_type_diversity_established": False,
            "production_qualification": False,
            "release_enforcement": False,
            "official_release_verdict": False,
        },
    }

    report_path = (
        root
        / "media"
        / "report.json"
    )

    report_raw = (
        _write_canonical_json(
            report_path,
            report,
        )
    )

    report_sha256 = (
        _sha256(
            report_raw
        )
    )

    rights_root = (
        root
        / "rights"
    )

    source_description = (
        b"fixture source description"
    )

    rights_evidence = (
        b"fixture rights evidence"
    )

    terms_evidence = (
        b"fixture terms evidence"
    )

    source_description_path = (
        rights_root
        / "readme.html"
    )

    rights_evidence_path = (
        rights_root
        / "evaluation-plan.pdf"
    )

    terms_evidence_path = (
        rights_root
        / "legalcode.txt"
    )

    _write_bytes(
        source_description_path,
        source_description,
    )

    _write_bytes(
        rights_evidence_path,
        rights_evidence,
    )

    _write_bytes(
        terms_evidence_path,
        terms_evidence,
    )

    rights_manifest = {
        "artifact": {
            "key": "fixture-rights",
            "schema_version": 1,
            "version": "1.0.0",
        },
    }

    rights_manifest_path = (
        rights_root
        / "manifest.json"
    )

    rights_manifest_raw = (
        _write_canonical_json(
            rights_manifest_path,
            rights_manifest,
        )
    )

    rights_manifest_sha256 = (
        _sha256(
            rights_manifest_raw
        )
    )

    docker_image_id = (
        "sha256:fixture-image"
    )

    python_version = (
        "Python fixture"
    )

    ffprobe_version = (
        "ffprobe fixture"
    )

    chain = {
        "artifact": {
            "key": (
                "hetren.asr.voices-controlled-"
                "capture-identity-chain"
            ),
            "schema_version": 1,
            "version": "1.0.0",
        },
        "controlled_selection": {
            "sha256": (
                selection_sha256
            ),
        },
        "materialization": {
            "manifest_sha256": (
                manifest_sha256
            ),
        },
        "media_verification": {
            "report_sha256": (
                report_sha256
            ),
            "observation_sha256": (
                observation_sha256
            ),
            "docker_image_id": (
                docker_image_id
            ),
            "python_version": (
                python_version
            ),
            "ffprobe_version": (
                ffprobe_version
            ),
        },
        "rights_evidence": {
            "manifest_sha256": (
                rights_manifest_sha256
            ),
        },
        "evidence_boundary": {
            "external_development_evidence": True,
            "base_train_test_source_disjointness_verified": True,
            "controlled_capture_lattice_verified": True,
            "current_selected_media_bytes_verified": True,
            "media_probe_verified": True,
            "source_declared_transcripts_bound": True,
            "raw_audio_committed_to_repository": False,
            "spoken_content_independently_verified": False,
            "asr_execution_verified": False,
            "live_human_in_room_diversity_established": False,
            "microphone_type_diversity_established": False,
            "human_acoustic_diversity_established": False,
            "rights_adjudicated": False,
            "production_qualification": False,
            "release_enforcement": False,
            "official_release_verdict": False,
        },
    }

    chain_path = (
        root
        / "chain.json"
    )

    chain_raw = (
        _write_canonical_json(
            chain_path,
            chain,
        )
    )

    definition = (
        ASRAdversarialVOiCESMaterializationDefinition(
            controlled_contract_sha256=(
                ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
            ),
            identity_chain_relative_path=(
                "chain.json"
            ),
            identity_chain_sha256=(
                _sha256(
                    chain_raw
                )
            ),
            identity_chain_byte_length=(
                len(
                    chain_raw
                )
            ),
            selection_relative_path=(
                "selection.json"
            ),
            selection_sha256=(
                selection_sha256
            ),
            selection_byte_length=(
                len(
                    selection_raw
                )
            ),
            materialization_root_relative_path=(
                "materialized"
            ),
            materialization_manifest_relative_path=(
                "materialized/manifest.json"
            ),
            materialization_manifest_sha256=(
                manifest_sha256
            ),
            materialization_manifest_byte_length=(
                len(
                    manifest_raw
                )
            ),
            media_report_relative_path=(
                "media/report.json"
            ),
            media_report_sha256=(
                report_sha256
            ),
            media_report_byte_length=(
                len(
                    report_raw
                )
            ),
            rights_manifest_relative_path=(
                "rights/manifest.json"
            ),
            rights_manifest_sha256=(
                rights_manifest_sha256
            ),
            rights_manifest_byte_length=(
                len(
                    rights_manifest_raw
                )
            ),
            source_description_relative_path=(
                "rights/readme.html"
            ),
            source_description_sha256=(
                _sha256(
                    source_description
                )
            ),
            source_description_byte_length=(
                len(
                    source_description
                )
            ),
            rights_evidence_relative_path=(
                "rights/evaluation-plan.pdf"
            ),
            rights_evidence_sha256=(
                _sha256(
                    rights_evidence
                )
            ),
            rights_evidence_byte_length=(
                len(
                    rights_evidence
                )
            ),
            terms_evidence_relative_path=(
                "rights/legalcode.txt"
            ),
            terms_evidence_sha256=(
                _sha256(
                    terms_evidence
                )
            ),
            terms_evidence_byte_length=(
                len(
                    terms_evidence
                )
            ),
            observation_sha256=(
                observation_sha256
            ),
            expected_source_file_count=1,
            expected_capture_file_count=1,
            expected_total_file_count=2,
            expected_total_bytes=(
                total_bytes
            ),
            expected_captures_per_source=1,
            expected_constant_angle_degrees=10,
            expected_source_keys=(
                SOURCE_KEY,
            ),
            expected_docker_image_id=(
                docker_image_id
            ),
            expected_python_version=(
                python_version
            ),
            expected_ffprobe_version=(
                ffprobe_version
            ),
        )
    )

    return {
        "root": root,
        "definition": definition,
        "chain": chain,
        "chain_path": chain_path,
        "selection": selection,
        "selection_path": (
            selection_path
        ),
        "manifest": manifest,
        "manifest_path": (
            manifest_path
        ),
        "report": report,
        "report_path": (
            report_path
        ),
        "rights_manifest_path": (
            rights_manifest_path
        ),
        "source_description_path": (
            source_description_path
        ),
        "rights_evidence_path": (
            rights_evidence_path
        ),
        "terms_evidence_path": (
            terms_evidence_path
        ),
        "materialization_root": (
            materialization_root
        ),
        "source_path": source_path,
        "capture_path": (
            capture_path
        ),
    }


def _materialize(
    fixture,
):
    return (
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=fixture[
                "root"
            ],
            definition=fixture[
                "definition"
            ],
        )
    )


def test_materializes_exact_controlled_fixture(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    result = _materialize(
        fixture
    )

    assert len(
        result.media
    ) == 2

    assert {
        value.kind
        for value in result.media
    } == {
        "source",
        "capture",
    }

    source_media = next(
        value
        for value in result.media
        if value.kind == "source"
    )

    capture_media = next(
        value
        for value in result.media
        if value.kind == "capture"
    )

    assert (
        source_media.capture_condition
        is None
    )

    assert (
        capture_media.require_capture_condition()
        == service.ASRAdversarialVOiCESMaterializedCaptureCondition(
            angle_degrees=10,
            room="rm1",
            distractor="none",
            microphone_id=1,
        )
    )

    assert all(
        value.path.is_absolute()
        for value in result.media
    )

    assert sum(
        value.byte_length
        for value in result.media
    ) == (
        len(
            SOURCE_AUDIO
        )
        + len(
            CAPTURE_AUDIO
        )
    )

    assert (
        result.controlled_contract_sha256
        == ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
    )

    assert (
        result.identity_chain_sha256
        == fixture[
            "definition"
        ].identity_chain_sha256
    )

    assert (
        result.development_evidence_only
        is True
    )

    assert (
        result.spoken_content_independently_verified
        is False
    )

    assert (
        result.asr_execution_verified
        is False
    )

    assert (
        result.production_qualified
        is False
    )

    assert (
        result.release_enforcement_eligible
        is False
    )


def test_invalid_definition_is_rejected_before_filesystem_use(
    tmp_path: Path,
):
    root = (
        tmp_path
        / "unused"
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="definition is invalid",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=root,
            definition=object(),
        )


def test_relative_root_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="root must be absolute",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=Path(
                "relative-evidence"
            ),
            definition=fixture[
                "definition"
            ],
        )


def test_missing_root_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    missing = (
        tmp_path
        / "missing"
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="root is unavailable",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=missing,
            definition=fixture[
                "definition"
            ],
        )


def test_root_file_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    root_file = (
        tmp_path
        / "root-file"
    )

    root_file.write_bytes(
        b"file"
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="root must be a directory",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=root_file,
            definition=fixture[
                "definition"
            ],
        )


def test_symlink_root_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    linked_root = (
        tmp_path
        / "linked-root"
    )

    try:
        linked_root.symlink_to(
            fixture[
                "root"
            ],
            target_is_directory=True,
        )
    except (
        OSError,
        NotImplementedError,
    ):
        pytest.skip(
            "symlinks unavailable"
        )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="root cannot be a symlink",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=(
                linked_root
            ),
            definition=fixture[
                "definition"
            ],
        )


def test_symlink_intermediate_component_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    actual = (
        fixture[
            "root"
        ]
        / "actual"
    )

    actual.mkdir()

    target = (
        actual
        / "chain.json"
    )

    target.write_bytes(
        fixture[
            "chain_path"
        ].read_bytes()
    )

    linked = (
        fixture[
            "root"
        ]
        / "linked"
    )

    try:
        linked.symlink_to(
            actual,
            target_is_directory=True,
        )
    except (
        OSError,
        NotImplementedError,
    ):
        pytest.skip(
            "symlinks unavailable"
        )

    definition = replace(
        fixture[
            "definition"
        ],
        identity_chain_relative_path=(
            "linked/chain.json"
        ),
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="cannot contain symlinks",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=fixture[
                "root"
            ],
            definition=definition,
        )


def test_symlink_chain_file_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    outside = (
        tmp_path
        / "outside-chain.json"
    )

    outside.write_bytes(
        fixture[
            "chain_path"
        ].read_bytes()
    )

    fixture[
        "chain_path"
    ].unlink()

    try:
        fixture[
            "chain_path"
        ].symlink_to(
            outside
        )
    except (
        OSError,
        NotImplementedError,
    ):
        pytest.skip(
            "symlinks unavailable"
        )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="cannot contain symlinks",
    ):
        _materialize(
            fixture
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "identity_chain_relative_path",
        "selection_relative_path",
        "materialization_root_relative_path",
        "materialization_manifest_relative_path",
        "media_report_relative_path",
        "rights_manifest_relative_path",
        "source_description_relative_path",
        "rights_evidence_relative_path",
        "terms_evidence_relative_path",
    ),
)
@pytest.mark.parametrize(
    "bad_path",
    (
        "../escape",
        "/absolute/path",
        "safe/../escape",
        "./safe/path",
    ),
)
def test_definition_rejects_unsafe_relative_paths(
    tmp_path: Path,
    field_name: str,
    bad_path: str,
):
    fixture = _fixture(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="is invalid",
    ):
        replace(
            fixture[
                "definition"
            ],
            **{
                field_name: (
                    bad_path
                ),
            },
        )


def test_wrong_controlled_contract_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    definition = replace(
        fixture[
            "definition"
        ],
        controlled_contract_sha256=(
            "0" * 64
        ),
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="contract identity changed",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=fixture[
                "root"
            ],
            definition=definition,
        )


def test_wrong_identity_chain_commitment_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    definition = replace(
        fixture[
            "definition"
        ],
        identity_chain_sha256=(
            "0" * 64
        ),
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="does not match its frozen commitment",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=fixture[
                "root"
            ],
            definition=definition,
        )


def test_noncanonical_chain_is_rejected_even_with_matching_hash(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    raw = json.dumps(
        fixture[
            "chain"
        ],
        indent=2,
        sort_keys=True,
    ).encode(
        "utf-8"
    )

    fixture[
        "chain_path"
    ].write_bytes(
        raw
    )

    definition = replace(
        fixture[
            "definition"
        ],
        identity_chain_sha256=(
            _sha256(
                raw
            )
        ),
        identity_chain_byte_length=(
            len(
                raw
            )
        ),
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="not canonical JSON",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=fixture[
                "root"
            ],
            definition=definition,
        )


def test_malformed_chain_json_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    raw = (
        b"{not-json}"
    )

    fixture[
        "chain_path"
    ].write_bytes(
        raw
    )

    definition = replace(
        fixture[
            "definition"
        ],
        identity_chain_sha256=(
            _sha256(
                raw
            )
        ),
        identity_chain_byte_length=(
            len(
                raw
            )
        ),
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="not valid UTF-8 JSON",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=fixture[
                "root"
            ],
            definition=definition,
        )


def test_chain_authority_escalation_is_rejected_even_if_rehashed(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    chain = copy.deepcopy(
        fixture[
            "chain"
        ]
    )

    chain[
        "evidence_boundary"
    ][
        "asr_execution_verified"
    ] = True

    raw = _canonical(
        chain
    )

    fixture[
        "chain_path"
    ].write_bytes(
        raw
    )

    definition = replace(
        fixture[
            "definition"
        ],
        identity_chain_sha256=(
            _sha256(
                raw
            )
        ),
        identity_chain_byte_length=(
            len(
                raw
            )
        ),
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="authority boundary changed",
    ):
        service._materialize_asr_adversarial_voices_evidence(
            evidence_root=fixture[
                "root"
            ],
            definition=definition,
        )


@pytest.mark.parametrize(
    (
        "path_key",
        "replacement",
        "message",
    ),
    (
        (
            "selection_path",
            b"X",
            "controlled selection does not match",
        ),
        (
            "manifest_path",
            b"X",
            "materialization manifest does not match",
        ),
        (
            "report_path",
            b"X",
            "media verification report does not match",
        ),
        (
            "rights_manifest_path",
            b"X",
            "rights manifest does not match",
        ),
        (
            "source_description_path",
            b"X",
            "source description does not match",
        ),
        (
            "rights_evidence_path",
            b"X",
            "rights evidence does not match",
        ),
        (
            "terms_evidence_path",
            b"X",
            "terms evidence does not match",
        ),
    ),
)
def test_committed_artifact_substitution_is_rejected(
    tmp_path: Path,
    path_key: str,
    replacement: bytes,
    message: str,
):
    fixture = _fixture(
        tmp_path
    )

    fixture[
        path_key
    ].write_bytes(
        replacement
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match=message,
    ):
        _materialize(
            fixture
        )


def test_extra_file_in_materialization_tree_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    extra = (
        fixture[
            "materialization_root"
        ]
        / "unexpected.wav"
    )

    extra.write_bytes(
        b"unexpected"
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="file allowlist changed",
    ):
        _materialize(
            fixture
        )


def test_missing_media_file_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    fixture[
        "capture_path"
    ].unlink()

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="file allowlist changed",
    ):
        _materialize(
            fixture
        )


def test_symlink_media_file_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    outside = (
        tmp_path
        / "outside.wav"
    )

    outside.write_bytes(
        CAPTURE_AUDIO
    )

    fixture[
        "capture_path"
    ].unlink()

    try:
        fixture[
            "capture_path"
        ].symlink_to(
            outside
        )
    except (
        OSError,
        NotImplementedError,
    ):
        pytest.skip(
            "symlinks unavailable"
        )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="cannot contain symlinks",
    ):
        _materialize(
            fixture
        )


def test_same_length_media_substitution_is_rejected(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    replacement = (
        b"X"
        * len(
            CAPTURE_AUDIO
        )
    )

    assert len(
        replacement
    ) == len(
        CAPTURE_AUDIO
    )

    fixture[
        "capture_path"
    ].write_bytes(
        replacement
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="current media does not match",
    ):
        _materialize(
            fixture
        )


def test_duplicate_manifest_media_paths_are_rejected():
    records = [
        {
            "relative_path": (
                "a/file.wav"
            ),
        },
        {
            "relative_path": (
                "a/file.wav"
            ),
        },
    ]

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="duplicate media paths",
    ):
        service._media_records_by_path(
            records=records,
            collection_name=(
                "fixture records"
            ),
        )


def test_duplicate_report_media_paths_are_rejected():
    records = [
        {
            "relative_path": (
                "a/file.wav"
            ),
        },
        {
            "relative_path": (
                "a/file.wav"
            ),
        },
    ]

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="duplicate media paths",
    ):
        service._media_records_by_path(
            records=records,
            collection_name=(
                "fixture observations"
            ),
        )


def test_media_mutation_between_first_and_second_hash_is_rejected(
    monkeypatch,
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    original_hash = (
        service._hash_file
    )

    mutated = False

    def mutating_hash(
        *,
        path: Path,
        name: str,
    ):
        nonlocal mutated

        result = original_hash(
            path=path,
            name=name,
        )

        if (
            path
            == fixture[
                "capture_path"
            ]
            and not mutated
        ):
            replacement = (
                b"Z"
                * len(
                    CAPTURE_AUDIO
                )
            )

            assert len(
                replacement
            ) == len(
                CAPTURE_AUDIO
            )

            path.write_bytes(
                replacement
            )

            mutated = True

        return result

    monkeypatch.setattr(
        service,
        "_hash_file",
        mutating_hash,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="media changed during verification",
    ):
        _materialize(
            fixture
        )

    assert mutated is True


def test_symlink_replacement_during_media_verification_is_rejected(
    monkeypatch,
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    outside = (
        tmp_path
        / "outside.wav"
    )

    outside.write_bytes(
        CAPTURE_AUDIO
    )

    original_hash = (
        service._hash_file
    )

    replaced = False

    def replacing_hash(
        *,
        path: Path,
        name: str,
    ):
        nonlocal replaced

        result = original_hash(
            path=path,
            name=name,
        )

        if (
            path
            == fixture[
                "capture_path"
            ]
            and not replaced
        ):
            path.unlink()

            try:
                path.symlink_to(
                    outside
                )
            except (
                OSError,
                NotImplementedError,
            ):
                pytest.skip(
                    "symlinks unavailable"
                )

            replaced = True

        return result

    monkeypatch.setattr(
        service,
        "_hash_file",
        replacing_hash,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="cannot contain symlinks",
    ):
        _materialize(
            fixture
        )

    assert replaced is True


def test_frozen_artifact_mutation_during_media_verification_is_rejected(
    monkeypatch,
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    original = (
        service._verify_current_media
    )

    mutated = False

    def mutating_verifier(
        **kwargs,
    ):
        nonlocal mutated

        result = original(
            **kwargs
        )

        fixture[
            "chain_path"
        ].write_bytes(
            b"{}"
        )

        mutated = True

        return result

    monkeypatch.setattr(
        service,
        "_verify_current_media",
        mutating_verifier,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="identity chain changed during verification",
    ):
        _materialize(
            fixture
        )

    assert mutated is True


def test_unexpected_hash_failure_is_not_swallowed(
    monkeypatch,
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    original_hash = (
        service._hash_file
    )

    def broken_hash(
        *,
        path: Path,
        name: str,
    ):
        if path == fixture[
            "capture_path"
        ]:
            raise RuntimeError(
                "hash implementation defect"
            )

        return original_hash(
            path=path,
            name=name,
        )

    monkeypatch.setattr(
        service,
        "_hash_file",
        broken_hash,
    )

    with pytest.raises(
        RuntimeError,
        match="hash implementation defect",
    ):
        _materialize(
            fixture
        )


@pytest.mark.parametrize(
    (
        "field_name",
        "unsafe_value",
    ),
    (
        (
            "development_evidence_only",
            False,
        ),
        (
            "spoken_content_independently_verified",
            True,
        ),
        (
            "asr_execution_verified",
            True,
        ),
        (
            "rights_adjudicated",
            True,
        ),
        (
            "human_acoustic_diversity_established",
            True,
        ),
        (
            "microphone_type_diversity_established",
            True,
        ),
        (
            "live_human_in_room_diversity_established",
            True,
        ),
        (
            "production_qualified",
            True,
        ),
        (
            "release_enforcement_eligible",
            True,
        ),
        (
            "official_release_verdict_modified",
            True,
        ),
    ),
)
def test_materialized_result_cannot_escalate_authority(
    tmp_path: Path,
    field_name: str,
    unsafe_value: bool,
):
    fixture = _fixture(
        tmp_path
    )

    result = _materialize(
        fixture
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
    ):
        replace(
            result,
            **{
                field_name: (
                    unsafe_value
                ),
            },
        )


def test_materialized_media_rejects_relative_path(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    result = _materialize(
        fixture
    )

    media = result.media[
        0
    ]

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="absolute Path",
    ):
        replace(
            media,
            path=Path(
                "relative.wav"
            ),
        )


def test_materialized_evidence_requires_media_tuple(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    result = _materialize(
        fixture
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="media collection is invalid",
    ):
        ASRAdversarialVOiCESMaterializedEvidence(
            controlled_contract_sha256=(
                result.controlled_contract_sha256
            ),
            identity_chain_sha256=(
                result.identity_chain_sha256
            ),
            selection_sha256=(
                result.selection_sha256
            ),
            materialization_manifest_sha256=(
                result.materialization_manifest_sha256
            ),
            media_report_sha256=(
                result.media_report_sha256
            ),
            observation_sha256=(
                result.observation_sha256
            ),
            rights_manifest_sha256=(
                result.rights_manifest_sha256
            ),
            media=[],
        )


def test_definition_rejects_boolean_source_key(
    tmp_path: Path,
):
    fixture = _fixture(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="source key is invalid",
    ):
        replace(
            fixture[
                "definition"
            ],
            expected_source_keys=(
                (
                    True,
                    2,
                    3,
                ),
            ),
        )


def test_materialized_media_type_is_frozen_slots_dataclass():
    assert (
        ASRAdversarialVOiCESMaterializedMedia.__dataclass_params__.frozen
        is True
    )

    assert (
        "__slots__"
        in ASRAdversarialVOiCESMaterializedMedia.__dict__
    )


def test_materialized_evidence_type_is_frozen_slots_dataclass():
    assert (
        ASRAdversarialVOiCESMaterializedEvidence.__dataclass_params__.frozen
        is True
    )

    assert (
        "__slots__"
        in ASRAdversarialVOiCESMaterializedEvidence.__dict__
    )


def test_generic_materializer_is_not_part_of_public_api():
    """Only the exact frozen-v1 materializer should be supported publicly."""

    assert (
        "materialize_asr_adversarial_voices_evidence"
        not in service.__all__
    )

    assert not hasattr(
        service,
        "materialize_asr_adversarial_voices_evidence",
    )

    assert hasattr(
        service,
        "_materialize_asr_adversarial_voices_evidence",
    )


def test_earlier_media_mutation_after_second_hash_is_rejected(
    monkeypatch,
    tmp_path: Path,
):
    """Detect mutation after an earlier file completed its second hash.

    Multi-file verification is sequential. A file that completed its second
    hash must not be allowed to change while later media are still being
    verified.
    """

    fixture = _fixture(
        tmp_path
    )

    original_hash = (
        service._hash_file
    )

    hash_counts = {
        fixture[
            "capture_path"
        ]: 0,
        fixture[
            "source_path"
        ]: 0,
    }

    mutated = False

    def mutating_hash(
        *,
        path: Path,
        name: str,
    ):
        nonlocal mutated

        # Sorted media order is capture/... then source/....
        #
        # Once capture has completed its second hash, mutate it immediately
        # before source receives its second hash. The current implementation
        # has no later check of capture, so this specifically exercises the
        # late multi-file publication window.
        if (
            path
            == fixture[
                "source_path"
            ]
            and hash_counts[
                fixture[
                    "capture_path"
                ]
            ]
            == 2
            and hash_counts[
                fixture[
                    "source_path"
                ]
            ]
            == 1
            and not mutated
        ):
            replacement = (
                b"Q"
                * len(
                    CAPTURE_AUDIO
                )
            )

            assert len(
                replacement
            ) == len(
                CAPTURE_AUDIO
            )

            fixture[
                "capture_path"
            ].write_bytes(
                replacement
            )

            mutated = True

        result = original_hash(
            path=path,
            name=name,
        )

        if path in hash_counts:
            hash_counts[
                path
            ] += 1

        return result

    monkeypatch.setattr(
        service,
        "_hash_file",
        mutating_hash,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match=(
            "media changed during verification"
            "|media filesystem identity changed"
        ),
    ):
        _materialize(
            fixture
        )

    assert mutated is True


def test_earlier_frozen_artifact_mutation_after_final_hash_is_rejected(
    monkeypatch,
    tmp_path: Path,
):
    """An earlier frozen input cannot change while later inputs are checked."""

    fixture = _fixture(
        tmp_path
    )

    original_hash = (
        service._hash_file
    )

    chain_final_hash_completed = False
    mutated = False

    def mutating_hash(
        *,
        path: Path,
        name: str,
    ):
        nonlocal chain_final_hash_completed
        nonlocal mutated

        result = original_hash(
            path=path,
            name=name,
        )

        if path == fixture[
            "chain_path"
        ]:
            chain_final_hash_completed = True

        elif (
            path
            == fixture[
                "selection_path"
            ]
            and chain_final_hash_completed
            and not mutated
        ):
            fixture[
                "chain_path"
            ].write_bytes(
                b"{}"
            )

            mutated = True

        return result

    monkeypatch.setattr(
        service,
        "_hash_file",
        mutating_hash,
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="identity chain changed during verification",
    ):
        _materialize(
            fixture
        )

    assert chain_final_hash_completed is True
    assert mutated is True


def test_selection_boolean_count_is_not_accepted_as_integer(
    tmp_path: Path,
):
    """JSON true must never satisfy an expected integer value of 1."""

    fixture = _fixture(
        tmp_path
    )

    selection = copy.deepcopy(
        fixture[
            "selection"
        ]
    )

    selection[
        "selection"
    ][
        "selected_source_count"
    ] = True

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="source count.*positive integer",
    ):
        service._selection_media_paths(
            selection=selection,
            definition=fixture[
                "definition"
            ],
        )


def test_manifest_boolean_count_is_not_accepted_as_integer(
    tmp_path: Path,
):
    """Manifest JSON booleans must not masquerade as integer counts."""

    fixture = _fixture(
        tmp_path
    )

    manifest = copy.deepcopy(
        fixture[
            "manifest"
        ]
    )

    manifest[
        "materialization"
    ][
        "source_file_count"
    ] = True

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="source file count.*positive integer",
    ):
        service._verify_cross_bindings(
            selection=fixture[
                "selection"
            ],
            manifest=manifest,
            report=fixture[
                "report"
            ],
            definition=fixture[
                "definition"
            ],
        )


def test_report_boolean_channel_count_is_not_accepted_as_integer(
    tmp_path: Path,
):
    """JSON true must not become channel_count=1 through int(True)."""

    fixture = _fixture(
        tmp_path
    )

    report = copy.deepcopy(
        fixture[
            "report"
        ]
    )

    report[
        "observations"
    ][0][
        "channels"
    ] = True

    observation_sha256 = _sha256(
        _canonical(
            report[
                "observations"
            ]
        )
    )

    report[
        "verification"
    ][
        "observation_sha256"
    ] = observation_sha256

    definition = replace(
        fixture[
            "definition"
        ],
        observation_sha256=(
            observation_sha256
        ),
    )

    with pytest.raises(
        ASRAdversarialVOiCESMaterializationError,
        match="channel count.*positive integer",
    ):
        service._verify_cross_bindings(
            selection=fixture[
                "selection"
            ],
            manifest=fixture[
                "manifest"
            ],
            report=report,
            definition=definition,
        )
