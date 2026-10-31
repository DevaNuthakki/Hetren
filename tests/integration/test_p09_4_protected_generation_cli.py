from __future__ import annotations

import argparse
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest


REPO_ROOT = Path(
    __file__
).resolve().parents[
    2
]

CLI_PATH = (
    REPO_ROOT
    / "scripts"
    / "generate_p09_4_protected_population.py"
)

PROTECTED_ROOT = (
    REPO_ROOT
    / "artifacts"
    / "p09_4_scientific_arms"
    / "protected_v1"
)

EXPECTED_SOURCE_COMMIT = (
    "dab6585c751ac457b2b6578a622ea25d49847d4f"
)

EXPECTED_PROTOCOL_SHA = (
    "46ea27e825bedbfbd8ee0443173884f904f20881fc929a4c44fae30c550e7621"
)

EXPECTED_GENERATOR_SHA = (
    "adff1938a5709ffd04ae27f8bd7744e25e2bcc295bfd7dca857994ba6572ac6b"
)

EXPECTED_MATERIALIZER_SHA = (
    "b5861344b66c9a3cf8ea6e4c8921441fd34410f52fbce3d5745eba67fa71d027"
)

EXPECTED_PERSISTENCE_SHA = (
    "4aafffdba38b86aa3836bc62f8258bbcea54d09bf98c01661c481b0ee08b40a4"
)


def _load_cli():
    spec = (
        importlib.util.spec_from_file_location(
            "p09_4_protected_generation_cli_test_module",
            CLI_PATH,
        )
    )

    assert spec is not None
    assert spec.loader is not None

    module = (
        importlib.util.module_from_spec(
            spec
        )
    )

    spec.loader.exec_module(
        module
    )

    return module


def test_cli_constants_bind_frozen_protocol_modules_and_source_commit():
    cli = (
        _load_cli()
    )

    assert (
        cli.BATCH_ID
        == "protected_v1"
    )

    assert (
        cli.PROTOCOL_SHA256
        == EXPECTED_PROTOCOL_SHA
    )

    assert (
        cli.SOURCE_COMMIT
        == EXPECTED_SOURCE_COMMIT
    )

    assert (
        cli.EXPECTED_GENERATOR_MODULE_SHA256
        == EXPECTED_GENERATOR_SHA
    )

    assert (
        cli.EXPECTED_MATERIALIZER_MODULE_SHA256
        == EXPECTED_MATERIALIZER_SHA
    )

    assert (
        cli.EXPECTED_PERSISTENCE_MODULE_SHA256
        == EXPECTED_PERSISTENCE_SHA
    )

    result = subprocess.run(
        [
            "/usr/bin/git",
            "merge-base",
            "--is-ancestor",
            EXPECTED_SOURCE_COMMIT,
            "HEAD",
        ],
        cwd=REPO_ROOT,
        check=False,
    )

    assert (
        result.returncode
        == 0
    )


def test_cli_import_is_side_effect_free():
    assert not (
        PROTECTED_ROOT.exists()
    )

    _load_cli()

    assert not (
        PROTECTED_ROOT.exists()
    )


def test_help_is_side_effect_free():
    assert not (
        PROTECTED_ROOT.exists()
    )

    result = subprocess.run(
        [
            sys.executable,
            str(
                CLI_PATH
            ),
            "--help",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert (
        result.returncode
        == 0
    )

    assert (
        "--expected-head"
        in result.stdout
    )

    assert (
        "--confirm"
        in result.stdout
    )

    assert not (
        PROTECTED_ROOT.exists()
    )


def test_wrong_confirmation_stops_before_protected_identity():
    head = subprocess.check_output(
        [
            "/usr/bin/git",
            "rev-parse",
            "HEAD",
        ],
        cwd=REPO_ROOT,
        text=True,
    ).strip()

    result = subprocess.run(
        [
            sys.executable,
            str(
                CLI_PATH
            ),
            "--expected-head",
            head,
            "--confirm",
            "WRONG_CONFIRMATION",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert (
        result.returncode
        != 0
    )

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "confirmation phrase does not match"
        in combined
    )

    assert not (
        PROTECTED_ROOT.exists()
    )


PROTECTED_BRANCH = (
    "portfolio/v1-foundation"
)

WRONG_HEAD_STOP = (
    "repository HEAD does not match explicitly expected HEAD"
)

WRONG_BRANCH_STOP = (
    "protected generation requires portfolio/v1-foundation"
)


def _current_branch() -> str:
    return subprocess.run(
        [
            "/usr/bin/git",
            "branch",
            "--show-current",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _artifact_files() -> frozenset[Path]:
    artifacts_root = (
        REPO_ROOT
        / "artifacts"
    )

    if not artifacts_root.exists():
        return frozenset()

    return frozenset(
        path
        for path in artifacts_root.rglob("*")
        if path.is_file()
    )


def test_wrong_expected_head_stops_before_protected_identity():
    cli = (
        _load_cli()
    )

    # The CLI checks the branch before HEAD, so the exact HEAD error is
    # only reachable on the protected branch.
    on_protected_branch = (
        _current_branch()
        == PROTECTED_BRANCH
    )

    artifacts_before = (
        _artifact_files()
    )

    result = subprocess.run(
        [
            sys.executable,
            str(
                CLI_PATH
            ),
            "--expected-head",
            "0" * 40,
            "--confirm",
            cli.CONFIRMATION_TEXT,
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert (
        result.returncode
        != 0
    )

    combined = (
        result.stdout
        + result.stderr
    )

    if on_protected_branch:
        assert (
            WRONG_HEAD_STOP
            in combined
        )
    else:
        assert (
            WRONG_HEAD_STOP in combined
            or WRONG_BRANCH_STOP in combined
        )

    assert not (
        PROTECTED_ROOT.exists()
    )

    assert (
        _artifact_files()
        == artifacts_before
    )


def test_frozen_byte_gate_detects_generator_mismatch(
    monkeypatch,
):
    cli = (
        _load_cli()
    )

    monkeypatch.setattr(
        cli,
        "EXPECTED_GENERATOR_MODULE_SHA256",
        "0" * 64,
    )

    with pytest.raises(
        SystemExit,
        match="protected generator bytes changed",
    ):
        cli._require_frozen_bytes()

    assert not (
        PROTECTED_ROOT.exists()
    )


def test_safe_artifact_boundary_rejects_existing_identity(
    tmp_path,
    monkeypatch,
):
    cli = (
        _load_cli()
    )

    artifact_root = (
        tmp_path
        / "artifacts"
        / "p09_4_scientific_arms"
    )

    batch = (
        artifact_root
        / cli.BATCH_ID
    )

    batch.mkdir(
        parents=True
    )

    monkeypatch.setattr(
        cli,
        "REPO_ROOT",
        tmp_path,
    )

    monkeypatch.setattr(
        cli,
        "ARTIFACT_ROOT",
        artifact_root,
    )

    monkeypatch.setattr(
        cli,
        "_git_ignored",
        lambda path: True,
    )

    with pytest.raises(
        SystemExit,
        match="protected_v1 already exists",
    ):
        cli._require_safe_artifact_boundary()


def test_safe_artifact_boundary_rejects_unignored_output(
    tmp_path,
    monkeypatch,
):
    cli = (
        _load_cli()
    )

    artifact_root = (
        tmp_path
        / "artifacts"
        / "p09_4_scientific_arms"
    )

    artifact_root.mkdir(
        parents=True
    )

    monkeypatch.setattr(
        cli,
        "REPO_ROOT",
        tmp_path,
    )

    monkeypatch.setattr(
        cli,
        "ARTIFACT_ROOT",
        artifact_root,
    )

    monkeypatch.setattr(
        cli,
        "_git_ignored",
        lambda path: False,
    )

    with pytest.raises(
        SystemExit,
        match="not Git-ignored",
    ):
        cli._require_safe_artifact_boundary()


def test_success_path_wiring_is_structurally_qualified_without_generation(
    monkeypatch,
    capsys,
):
    cli = (
        _load_cli()
    )

    authorized_head = (
        "a" * 40
    )

    monkeypatch.setattr(
        cli,
        "parse_args",
        lambda:
            argparse.Namespace(
                expected_head=(
                    authorized_head
                ),
                confirm=(
                    cli.CONFIRMATION_TEXT
                ),
            ),
    )

    monkeypatch.setattr(
        cli,
        "_require_repository_ready",
        lambda expected_head:
            authorized_head,
    )

    monkeypatch.setattr(
        cli,
        "_require_frozen_bytes",
        lambda:
            None,
    )

    monkeypatch.setattr(
        cli,
        "_require_safe_artifact_boundary",
        lambda:
            None,
    )

    captured = {}


    def fake_persist(
        **kwargs,
    ):
        captured.update(
            kwargs
        )

        return SimpleNamespace(
            batch_directory=(
                Path(
                    "/synthetic/protected_v1"
                )
            ),
            repository_head_commit_id=(
                authorized_head
            ),
            source_commit=(
                cli.SOURCE_COMMIT
            ),
            generator_module_sha256=(
                cli.EXPECTED_GENERATOR_MODULE_SHA256
            ),
            materializer_module_sha256=(
                cli.EXPECTED_MATERIALIZER_MODULE_SHA256
            ),
            persistence_module_sha256=(
                cli.EXPECTED_PERSISTENCE_MODULE_SHA256
            ),
            generation_seed_sha256=(
                "1" * 64
            ),
            generation_seed_commitment_file_sha256=(
                "2" * 64
            ),
            public_population_manifest_sha256=(
                "3" * 64
            ),
            hidden_assignment_manifest_sha256=(
                "4" * 64
            ),
            generation_record_sha256=(
                "5" * 64
            ),
        )


    monkeypatch.setattr(
        cli,
        "_persist_generation_attempt",
        fake_persist,
    )

    rc = (
        cli.main()
    )

    assert (
        rc
        == 0
    )

    assert (
        captured[
            "artifact_root"
        ]
        == cli.ARTIFACT_ROOT
    )

    assert (
        captured[
            "batch_id"
        ]
        == cli.BATCH_ID
    )

    assert (
        captured[
            "protocol_sha256"
        ]
        == cli.PROTOCOL_SHA256
    )

    assert (
        captured[
            "source_commit"
        ]
        == cli.SOURCE_COMMIT
    )

    assert (
        captured[
            "repository_head_commit_id"
        ]
        == authorized_head
    )

    assert (
        captured[
            "generator_module_sha256"
        ]
        == cli.EXPECTED_GENERATOR_MODULE_SHA256
    )

    assert (
        captured[
            "materializer_module_sha256"
        ]
        == cli.EXPECTED_MATERIALIZER_MODULE_SHA256
    )

    assert (
        captured[
            "persistence_module_sha256"
        ]
        == cli.EXPECTED_PERSISTENCE_MODULE_SHA256
    )

    assert (
        captured[
            "seed_factory"
        ]
        is cli.secrets.token_bytes
    )

    output = (
        capsys.readouterr().out
    )

    assert (
        "Raw generation-seed bytes were not printed."
        in output
    )

    assert (
        "does not authorize treatment execution"
        in output
    )

    assert not (
        PROTECTED_ROOT.exists()
    )


def test_cli_ast_has_single_persistence_call_and_no_direct_seed_generation():
    tree = ast.parse(
        CLI_PATH.read_text(
            encoding="utf-8"
        )
    )

    persistence_calls = []

    direct_token_calls = []

    main_function = None

    has_main_guard = False


    for node in tree.body:
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == "main"
        ):
            main_function = node

        if isinstance(
            node,
            ast.If,
        ):
            rendered = ast.unparse(
                node.test
            )

            if (
                "__name__ == '__main__'"
                in rendered
                or '__name__ == "__main__"'
                in rendered
            ):
                has_main_guard = True


    assert (
        main_function
        is not None
    )

    assert (
        has_main_guard
        is True
    )


    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "_persist_generation_attempt"
        ):
            persistence_calls.append(
                node
            )

        if (
            isinstance(
                node.func,
                ast.Attribute,
            )
            and isinstance(
                node.func.value,
                ast.Name,
            )
            and node.func.value.id
            == "secrets"
            and node.func.attr
            == "token_bytes"
        ):
            direct_token_calls.append(
                node
            )


    assert len(
        persistence_calls
    ) == 1

    assert len(
        direct_token_calls
    ) == 0

    call = persistence_calls[
        0
    ]

    assert (
        main_function.lineno
        <= call.lineno
        <= main_function.end_lineno
    )

    keyword_map = {
        keyword.arg:
            keyword.value
        for keyword
        in call.keywords
    }

    seed_factory = (
        keyword_map[
            "seed_factory"
        ]
    )

    assert isinstance(
        seed_factory,
        ast.Attribute
    )

    assert isinstance(
        seed_factory.value,
        ast.Name
    )

    assert (
        seed_factory.value.id
        == "secrets"
    )

    assert (
        seed_factory.attr
        == "token_bytes"
    )


def test_cli_has_no_c1_treatment_or_evaluator_execution_surface():
    text = CLI_PATH.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        text
    )

    forbidden_names = {
        "run_scientific_arm",
        "execute_checkpoint_replay",
        "evaluate_protected_records",
        "c1_raw_seed",
    }


    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Name,
        ):
            assert (
                node.id
                not in forbidden_names
            )

        if isinstance(
            node,
            ast.Attribute,
        ):
            assert (
                node.attr
                not in forbidden_names
            )


    assert (
        "execution_v1"
        not in text
    )

    assert not (
        PROTECTED_ROOT.exists()
    )
