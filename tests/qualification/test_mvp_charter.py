#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/check_mvp_charter.py"


def make_fixture(base: Path) -> Path:
    root = base / "repo"

    (root / "docs/mvp").mkdir(parents=True)
    (root / "docs/research/native_intelligence").mkdir(parents=True)
    (root / "docs/research/adaptive_intelligence").mkdir(parents=True)
    (root / "research/native_intelligence").mkdir(parents=True)
    (root / "research/adaptive_intelligence").mkdir(parents=True)

    shutil.copy2(
        ROOT / "docs/mvp/00-authority.md",
        root / "docs/mvp/00-authority.md",
    )
    shutil.copy2(
        ROOT / "docs/mvp/02-charter.md",
        root / "docs/mvp/02-charter.md",
    )

    return root


def run_validator(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(VALIDATOR),
            "--root",
            str(root),
            *extra,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text, f"mutation source not found: {old}"
    path.write_text(text.replace(old, new, 1))


def expect_rejected(
    name: str,
    mutate,
    expected_error: str,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(Path(tmp))
        mutate(root)

        result = run_validator(root)

        assert result.returncode != 0, (
            f"{name}: validator unexpectedly passed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        combined = result.stdout + result.stderr

        assert expected_error in combined, (
            f"{name}: expected error not found: {expected_error}\n"
            f"output:\n{combined}"
        )

        print(f"PASS mutation rejected: {name}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(Path(tmp))

        result = run_validator(root)

        assert result.returncode == 0, (
            "positive control failed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        print("PASS positive control")

        charter_path = root / "docs/mvp/02-charter.md"
        charter_text = charter_path.read_text()

        if "**Status:** Requalifying" in charter_text:
            charter_path.write_text(
                charter_text.replace(
                    "**Status:** Requalifying",
                    "**Status:** Qualified",
                    1,
                )
            )

        qualified_result = run_validator(root, "--require-qualified")

        assert qualified_result.returncode == 0, (
            "Qualified fixture failed final qualification\n"
            f"stdout:\n{qualified_result.stdout}\n"
            f"stderr:\n{qualified_result.stderr}"
        )

        print("PASS Qualified status accepted by final check")

        replace_once(
            charter_path,
            "**Status:** Qualified",
            "**Status:** Requalifying",
        )

        requalifying_result = run_validator(
            root,
            "--require-qualified",
        )

        assert requalifying_result.returncode != 0, (
            "Requalifying charter unexpectedly passed final qualification"
        )

        assert "charter must be Qualified" in (
            requalifying_result.stdout + requalifying_result.stderr
        )

        print("PASS Requalifying status rejected by final check")

    expect_rejected(
        "missing canonical MVP authority",
        lambda root: replace_once(
            root / "docs/mvp/02-charter.md",
            "AUTH-HETREN-MVP-3.0",
            "AUTH-HETREN-MVP-9.9",
        ),
        "charter Execution authority metadata must exactly identify "
        "AUTH-HETREN-MVP-3.0",
    )

    expect_rejected(
        "adaptive research section removed",
        lambda root: replace_once(
            root / "docs/mvp/02-charter.md",
            "## 12. Adaptive Intelligence Research",
            "## 12. Experimental Research",
        ),
        "section 12 must be 'Adaptive Intelligence Research'",
    )

    def remove_release_14(root: Path) -> None:
        path = root / "docs/mvp/02-charter.md"
        text = path.read_text()

        line = (
            "14. engineering outcome and practical value are demonstrated "
            "through independent replay, complete effort/cost accounting, "
            "and recorded human review decisions.\n"
        )

        assert line in text
        path.write_text(text.replace(line, "", 1))

    expect_rejected(
        "MVP release condition 14 removed",
        remove_release_14,
        "MVP release gate must contain exactly conditions 1 through 14",
    )

    def remove_task1_25(root: Path) -> None:
        path = root / "docs/mvp/02-charter.md"
        text = path.read_text()

        line = (
            "25. legacy implementation structure is prevented from silently "
            "becoming the new architectural foundation.\n"
        )

        assert line in text
        path.write_text(text.replace(line, "", 1))

    expect_rejected(
        "Task 1 condition 25 removed",
        remove_task1_25,
        "Task 1 qualification contract must contain exactly conditions 1 through 25",
    )

    expect_rejected(
        "product and adaptive status separation removed",
        lambda root: replace_once(
            root / "docs/mvp/02-charter.md",
            "The product release decision and Adaptive Intelligence scientific decision",
            "The release decisions",
        ),
        "required charter/authority contract missing: "
        "The product release decision and Adaptive Intelligence scientific decision",
    )

    def resurrect_old_authority(root: Path) -> None:
        path = root / "docs/mvp/02-charter.md"
        text = path.read_text()
        text += "\n**Authority:** Hetren MVP Plan v2.0\n"
        path.write_text(text)

    expect_rejected(
        "superseded authority resurrected",
        resurrect_old_authority,
        "superseded authority still presented as current",
    )

    def remove_adaptive_boundary(root: Path) -> None:
        shutil.rmtree(root / "research/adaptive_intelligence")

    expect_rejected(
        "adaptive research implementation boundary removed",
        remove_adaptive_boundary,
        "missing research boundary directory",
    )

    print("MVP CHARTER MUTATION SUITE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
