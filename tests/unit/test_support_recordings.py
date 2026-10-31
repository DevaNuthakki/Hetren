from pathlib import Path
import re

from packages.support_evaluator import (
    EXAMPLES,
    NEUTRAL_FILE_NAME,
    NEUTRAL_RUN_ID,
    assert_no_leaks,
    scan_identifiers,
)
from packages.support_evaluator.recordings import (
    RECORDED_RUNS,
    RECORDING_SOURCE_MODEL_ID,
    example_run_ids,
    first_run_number,
)
from packages.verification.support_verification import recorded_replay_plan


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "support_captures"


def test_mapping_covers_exactly_the_committed_run_directories():
    directories = sorted(path.name for path in FIXTURES.iterdir() if path.is_dir())

    assert directories == sorted(RECORDED_RUNS) == [
        "run-0001", "run-0002", "run-0003", "run-0004", "run-0005",
    ]


def test_mapping_assigns_every_example_and_role():
    assert {run.example_name for run in RECORDED_RUNS.values()} == set(EXAMPLES)
    assert example_run_ids("example_correct_run") == ("run-0001",)
    assert example_run_ids("example_insufficient_evidence") == ("run-0002",)
    assert example_run_ids("example_verified_recovery") == ("run-0003", "run-0004", "run-0005")
    assert [RECORDED_RUNS[run_id].role for run_id in example_run_ids("example_verified_recovery")] == [
        "initial", "rerun", "regression",
    ]


def test_each_example_occupies_consecutive_run_ids():
    for example_name in EXAMPLES:
        run_ids = example_run_ids(example_name)
        first = first_run_number(example_name)

        assert run_ids == tuple(f"run-{first + offset:04d}" for offset in range(len(run_ids)))


def test_run_ids_and_directory_names_are_neutral():
    assert_no_leaks(scan_identifiers("recorded_run_ids", list(RECORDED_RUNS), NEUTRAL_RUN_ID))
    assert_no_leaks(
        scan_identifiers(
            "fixture_directories", [f"{path.name}.json" for path in FIXTURES.iterdir()], NEUTRAL_FILE_NAME,
        )
    )


def test_mapping_is_not_stored_with_the_captures():
    files = [path for path in FIXTURES.rglob("*") if path.is_file()]

    assert files
    assert all(re.fullmatch(r"capture-[0-9]{4}\.json", path.name) for path in files)
    assert not any("example_" in path.read_text(encoding="utf-8") for path in files)


def test_verifier_replay_plan_mirrors_the_mapping():
    plan = recorded_replay_plan()

    assert [(entry.example_name, entry.first_run_number, entry.run_ids) for entry in plan] == [
        ("example_correct_run", 1, ("run-0001",)),
        ("example_insufficient_evidence", 2, ("run-0002",)),
        ("example_verified_recovery", 3, ("run-0003", "run-0004", "run-0005")),
    ]
    assert {entry.source_model_id for entry in plan} == {RECORDING_SOURCE_MODEL_ID}
