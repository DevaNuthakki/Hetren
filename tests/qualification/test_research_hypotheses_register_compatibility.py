from pathlib import Path
import importlib.util
import re
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[2]

CHECKER_FILE = (
    ROOT
    / "scripts/check_research_hypotheses.py"
)


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "task6_register_compatibility_checker",
        CHECKER_FILE,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


def copy_governed_inputs(
    checker,
    destination_root: Path,
) -> None:
    required = (
        checker.SPEC_RELATIVE,
        checker.NATIVE_DECISION_RELATIVE,
        checker.ADAPTIVE_DECISION_RELATIVE,
        checker.REGISTER_RELATIVE,
        checker.NATIVE_QUALIFICATION_RELATIVE,
        checker.ADAPTIVE_QUALIFICATION_RELATIVE,
    )

    for relative in required:
        source_file = (
            ROOT
            / relative
        )

        destination_file = (
            destination_root
            / relative
        )

        assert source_file.is_file(), (
            f"missing governed source: {source_file}"
        )

        destination_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source_file,
            destination_file,
        )


def set_register_version(
    checker,
    root: Path,
    version: str,
) -> None:
    register_file = (
        root
        / checker.REGISTER_RELATIVE
    )

    text = register_file.read_text()

    updated, count = re.subn(
        r"^\*\*Version:\*\* .+$",
        f"**Version:** {version}",
        text,
        count=1,
        flags=re.MULTILINE,
    )

    assert count == 1

    register_file.write_text(
        updated
    )


def validate_version(
    checker,
    version: str,
) -> list[str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(
            temp_dir
        )

        copy_governed_inputs(
            checker,
            temp_root,
        )

        set_register_version(
            checker,
            temp_root,
            version,
        )

        return checker.validate_structure(
            temp_root,
            require_qualified=True,
        )


def main() -> None:
    checker = load_checker()

    valid_versions = (
        "1.5.0",
        "1.6.0",
        "1.7.0",
        "2.0.0",
    )

    for version in valid_versions:
        errors = validate_version(
            checker,
            version,
        )

        assert not errors, (
            f"compatible register version "
            f"{version} rejected:\n"
            + "\n".join(errors)
        )

        print(
            "PASS compatible register version:",
            version,
        )

    too_old_errors = validate_version(
        checker,
        "1.4.9",
    )

    assert (
        "decision register Version must be at least "
        "1.5.0 for Task 6"
        in too_old_errors
    )

    print(
        "PASS incompatible historical register "
        "version rejected: 1.4.9"
    )

    invalid_errors = validate_version(
        checker,
        "invalid-version",
    )

    assert (
        "decision register Version must be a valid "
        "semantic version for Task 6"
        in invalid_errors
    )

    print(
        "PASS malformed register version rejected"
    )

    print()
    print(
        "TASK 6 REGISTER COMPATIBILITY REGRESSION: PASS"
    )


if __name__ == "__main__":
    main()
