#!/usr/bin/env python3

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "check_system_taxonomy.py"

SPEC = "docs/mvp/04-system-taxonomy.md"
DECISION = "docs/decisions/0004-system-taxonomy.md"
REGISTER = "docs/decisions/register.md"
QUALIFICATION = (
    "docs/decisions/qualification/0004-system-taxonomy.md"
)

EXPECTED_MUTATIONS = 34
MUTATIONS_KILLED = 0


def make_repo() -> Path:
    temp = Path(
        tempfile.mkdtemp(
            prefix="hetren-system-taxonomy-test-"
        )
    )

    for relative in (
        SPEC,
        DECISION,
        REGISTER,
    ):
        source = ROOT / relative
        target = temp / relative
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        shutil.copy2(source, target)

    return temp


def run_validator(
    root: Path,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(root),
            *extra,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def mutate_file(
    root: Path,
    relative: str,
    old: str,
    new: str,
) -> None:
    path = root / relative
    text = path.read_text()

    if old not in text:
        raise AssertionError(
            f"mutation anchor missing in {relative}: {old}"
        )

    path.write_text(
        text.replace(old, new, 1)
    )


def replace_markdown_section(
    root: Path,
    relative: str,
    heading: str,
    body: str,
) -> None:
    path = root / relative
    text = path.read_text()

    pattern = (
        rf"(## {re.escape(heading)}\n)"
        r".*?"
        r"(?=\n## |\Z)"
    )

    replacement = (
        rf"\1"
        + "\n"
        + body.strip()
        + "\n"
    )

    updated, count = re.subn(
        pattern,
        replacement,
        text,
        count=1,
        flags=re.DOTALL,
    )

    if count != 1:
        raise AssertionError(
            f"section replacement failed: {heading}"
        )

    path.write_text(updated)


def expect_fail(
    name: str,
    mutate,
    expected: str,
) -> None:
    global MUTATIONS_KILLED

    root = make_repo()

    try:
        set_development_state(root)
        mutate(root)
        result = run_validator(root)
        output = result.stdout + result.stderr

        if result.returncode == 0:
            raise AssertionError(
                f"{name}: validator unexpectedly passed"
            )

        if expected not in output:
            raise AssertionError(
                f"{name}: expected {expected!r}, "
                f"got:\n{output}"
            )

        MUTATIONS_KILLED += 1
        print(f"PASS mutation killed: {name}")
    finally:
        shutil.rmtree(
            root,
            ignore_errors=True,
        )


def expect_final_fail(
    name: str,
    mutate,
    expected: str,
) -> None:
    global MUTATIONS_KILLED

    root = make_repo()

    try:
        set_final_state(root)
        mutate(root)

        result = run_validator(
            root,
            "--require-qualified",
        )
        output = result.stdout + result.stderr

        if result.returncode == 0:
            raise AssertionError(
                f"{name}: final validator "
                "unexpectedly passed"
            )

        if expected not in output:
            raise AssertionError(
                f"{name}: expected {expected!r}, "
                f"got:\n{output}"
            )

        MUTATIONS_KILLED += 1
        print(
            f"PASS final mutation killed: {name}"
        )
    finally:
        shutil.rmtree(
            root,
            ignore_errors=True,
        )



def set_development_state(root: Path) -> None:
    """Reconstruct the pre-acceptance Task 4 state in a temporary fixture."""

    ensure_replace(
        root,
        SPEC,
        "**Version:** 0.1.0",
        "**Version:** 1.0.0",
    )

    ensure_replace(
        root,
        SPEC,
        "**Status:** Draft",
        "**Status:** Qualified",
        "**Status:** Requalifying",
    )

    ensure_replace(
        root,
        DECISION,
        "**Status:** `PROPOSED`",
        "**Status:** `ACCEPTED`",
    )

    ensure_replace(
        root,
        REGISTER,
        "| `0004` | `architecture.system-taxonomy` | "
        "Define governed MVP system taxonomy | "
        "`PROPOSED` | `ARCHITECTURE` |",
        "| `0004` | `architecture.system-taxonomy` | "
        "Define governed MVP system taxonomy | "
        "`ACCEPTED` | `ARCHITECTURE` |",
    )

    qualification_path = root / QUALIFICATION

    if qualification_path.exists():
        qualification_path.unlink()

def positive_control() -> None:
    root = make_repo()

    try:
        set_development_state(root)
        result = run_validator(root)

        if result.returncode != 0:
            raise AssertionError(
                "development positive control failed\n"
                f"{result.stdout}{result.stderr}"
            )

        print("PASS positive control")
    finally:
        shutil.rmtree(
            root,
            ignore_errors=True,
        )


def ensure_replace(
    root: Path,
    relative: str,
    desired: str,
    *alternatives: str,
) -> None:
    path = root / relative
    text = path.read_text()

    if desired in text:
        return

    for old in alternatives:
        if old in text:
            path.write_text(
                text.replace(
                    old,
                    desired,
                    1,
                )
            )
            return

    raise AssertionError(
        "final-state fixture anchor missing "
        f"for {relative}: {desired}"
    )


def set_final_state(root: Path) -> None:
    ensure_replace(
        root,
        SPEC,
        "**Version:** 1.0.0",
        "**Version:** 0.1.0",
    )

    ensure_replace(
        root,
        SPEC,
        "**Status:** Qualified",
        "**Status:** Draft",
        "**Status:** Requalifying",
    )

    ensure_replace(
        root,
        DECISION,
        "**Status:** `ACCEPTED`",
        "**Status:** `PROPOSED`",
    )

    ensure_replace(
        root,
        REGISTER,
        "| `0004` | `architecture.system-taxonomy` | "
        "Define governed MVP system taxonomy | "
        "`ACCEPTED` | `ARCHITECTURE` |",
        "| `0004` | `architecture.system-taxonomy` | "
        "Define governed MVP system taxonomy | "
        "`PROPOSED` | `ARCHITECTURE` |",
    )

    replace_markdown_section(
        root,
        DECISION,
        "Implementation Evidence",
        """
Implemented and preserved in:

- `docs/mvp/04-system-taxonomy.md`;
- `scripts/check_system_taxonomy.py`;
- `tests/qualification/test_system_taxonomy.py`.
""",
    )

    replace_markdown_section(
        root,
        DECISION,
        "Verification Evidence",
        """
Verified by
`docs/decisions/qualification/0004-system-taxonomy.md`
with structural, semantic, adversarial, mutation, authority,
regression, and accepted-state qualification.
""",
    )

    qualification_path = (
        root / QUALIFICATION
    )
    qualification_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    qualification_path.write_text(
        "# Decision 0004 Qualification Record\n\n"
        "**Task:** `4 / 100`\n"
        "**Decision:** `0004`\n"
        "**Decision Key:** "
        "`architecture.system-taxonomy`\n"
        "**Date:** `2026-09-17`\n"
        "**Result:** `PASS`\n"
        "**Qualification state:** `VERIFIED`\n"
        "**Specification:** "
        "`docs/mvp/04-system-taxonomy.md`\n"
        "**Specification version:** `1.0.0`\n"
        "**Validator:** "
        "`scripts/check_system_taxonomy.py`\n"
        "**Mutation suite:** "
        "`tests/qualification/test_system_taxonomy.py`\n"
        "**Qualification conditions:** `50 / 50`\n"
        "**Mutation result:** `34 / 34`\n"
        "**Execution authority:** "
        "`AUTH-HETREN-MVP-3.0`\n"
        "**Long-term authority:** "
        "`AUTH-HETREN-MASTER-2.0`\n"
        "**Task 1 regression:** `PASS`\n"
        "**Task 2 regression:** `PASS`\n"
        "**Task 3 regression:** `PASS`\n"
        "**Diff check:** `PASS`\n"
        "**Final accepted-state qualification:** "
        "`PASS`\n\n"
        "## Scope\n\n"
        "Task 4 system-taxonomy qualification.\n\n"
        "## Positive Qualification\n\n"
        "PASS.\n\n"
        "## Structural Qualification\n\n"
        "PASS.\n\n"
        "## Semantic Qualification\n\n"
        "PASS.\n\n"
        "## Adversarial Qualification\n\n"
        "PASS.\n\n"
        "## Authority And Regression Qualification\n\n"
        "PASS.\n\n"
        "## Limitations\n\n"
        "This qualification does not establish "
        "Task 5 capability support or a scientific "
        "hypothesis.\n\n"
        "## Acceptance Decision\n\n"
        "Decision 0004 accepted-state "
        "qualification: PASS.\n"
    )


def final_positive_control() -> None:
    root = make_repo()

    try:
        set_final_state(root)

        result = run_validator(
            root,
            "--require-qualified",
        )

        if result.returncode != 0:
            raise AssertionError(
                "final-state positive control failed\n"
                f"{result.stdout}{result.stderr}"
            )

        print(
            "PASS final-state positive control"
        )
    finally:
        shutil.rmtree(
            root,
            ignore_errors=True,
        )


def main() -> int:
    positive_control()
    final_positive_control()

    expect_fail(
        "wrong MVP execution authority",
        lambda root: mutate_file(
            root,
            SPEC,
            "**Execution authority:** "
            "`AUTH-HETREN-MVP-3.0`",
            "**Execution authority:** "
            "`AUTH-HETREN-MVP-9.9`",
        ),
        "system-taxonomy metadata "
        "Execution authority",
    )

    expect_fail(
        "section topology changed",
        lambda root: mutate_file(
            root,
            SPEC,
            "## 22. Versioned System Graph",
            "## 22. Optional System Graph",
        ),
        "exactly ordered sections 1 through 36",
    )

    expect_fail(
        "SystemForm vocabulary expanded",
        lambda root: mutate_file(
            root,
            SPEC,
            "- `COMPOSITE` —",
            "- `UNKNOWN_FORM` — temporary form;\n"
            "- `COMPOSITE` —",
        ),
        "SystemForm vocabulary must be exactly",
    )

    expect_fail(
        "EnvironmentFamily vocabulary expanded",
        lambda root: mutate_file(
            root,
            SPEC,
            "- `E3_VISION` — vision models, "
            "pipelines, or services.",
            "- `E3_VISION` — vision models, "
            "pipelines, or services.\n"
            "- `E4_AUDIO` — audio systems.",
        ),
        "EnvironmentFamily vocabulary "
        "must be exactly",
    )

    expect_fail(
        "InvestigationSurface vocabulary expanded",
        lambda root: mutate_file(
            root,
            SPEC,
            "- `AUTHORIZED_INTERNAL`.",
            "- `AUTHORIZED_INTERNAL`;\n"
            "- `UNRESTRICTED_INTERNAL`.",
        ),
        "InvestigationSurface vocabulary "
        "must be exactly",
    )

    expect_fail(
        "graph relationship vocabulary changed",
        lambda root: mutate_file(
            root,
            SPEC,
            "`EXPOSES_SURFACE` — which "
            "investigation surfaces",
            "`GRANTS_SURFACE` — which "
            "investigation surfaces",
        ),
        "Versioned System Graph relationship "
        "vocabulary must be exactly",
    )

    expect_fail(
        "qualification condition 6 weakened",
        lambda root: mutate_file(
            root,
            SPEC,
            "6. tenant-owned graph identities and "
            "relationships cannot cross tenant boundaries;",
            "6. tenant-owned graph identities and "
            "relationships may cross tenant boundaries;",
        ),
        "Task 4 qualification condition 6",
    )

    expect_fail(
        "tenant isolation weakened",
        lambda root: mutate_file(
            root,
            SPEC,
            "No graph relationship may directly connect "
            "tenant-owned system or component\n"
            "nodes across tenant boundaries.",
            "Graph relationships may directly connect "
            "tenant-owned system or component\n"
            "nodes across tenant boundaries.",
        ),
        "section 5",
    )

    expect_fail(
        "SystemVersion made mutable",
        lambda root: mutate_file(
            root,
            SPEC,
            "Existing system versions are immutable.",
            "Existing system versions may be mutable.",
        ),
        "section 7",
    )

    expect_fail(
        "provider determines environment family",
        lambda root: mutate_file(
            root,
            SPEC,
            "Provider identity must not determine "
            "environment family.",
            "Provider identity determines "
            "environment family.",
        ),
        "section 9",
    )

    expect_fail(
        "adapter allowed to define success",
        lambda root: mutate_file(
            root,
            SPEC,
            "It must not define\n"
            "whether an evaluation passes, whether a "
            "capability is qualified, or what the\n"
            "shared planner should conclude.",
            "It may define\n"
            "whether an evaluation passes, whether a "
            "capability is qualified, or what the\n"
            "shared planner should conclude.",
        ),
        "section 17",
    )

    expect_fail(
        "evaluator allowed to redefine outcomes",
        lambda root: mutate_file(
            root,
            SPEC,
            "It does not redefine the Task 3 meanings "
            "of `PASS`, `FAIL`,\n"
            "`INCONCLUSIVE`, `BLOCKED`, or `INVALID`.",
            "It redefines the Task 3 meanings "
            "of `PASS`, `FAIL`,\n"
            "`INCONCLUSIVE`, `BLOCKED`, or `INVALID`.",
        ),
        "section 18",
    )

    expect_fail(
        "Internal declaration treated as authorization",
        lambda root: mutate_file(
            root,
            SPEC,
            "declaration of `AUTHORIZED_INTERNAL` "
            "does not itself grant\n"
            "authorization.",
            "declaration of `AUTHORIZED_INTERNAL` "
            "does itself grant\n"
            "authorization.",
        ),
        "section 19",
    )

    expect_fail(
        "Internal access inference allowed",
        lambda root: mutate_file(
            root,
            SPEC,
            "Internal access must never be inferred "
            "merely because:",
            "Internal access may be inferred "
            "merely because:",
        ),
        "section 21",
    )

    expect_fail(
        "system graph treated as support evidence",
        lambda root: mutate_file(
            root,
            SPEC,
            "The graph is not itself evidence that a "
            "capability is supported, a result is\n"
            "valid, or an investigation succeeded.",
            "The graph is itself evidence that a "
            "capability is supported, a result is\n"
            "valid, or an investigation succeeded.",
        ),
        "section 22",
    )

    expect_fail(
        "target provider change no longer versions system",
        lambda root: mutate_file(
            root,
            SPEC,
            "or a provider binding that is\n"
            "part of target behavior requires a new "
            "`SystemVersion`.",
            "or a provider binding that is\n"
            "part of target behavior does not require "
            "a new `SystemVersion`.",
        ),
        "section 25",
    )

    expect_fail(
        "classification allowed to synthesize capability",
        lambda root: mutate_file(
            root,
            SPEC,
            "Neither the system graph nor successful "
            "target classification may synthesize a\n"
            "qualified `CapabilityProfile` entry "
            "without the required qualification\n"
            "evidence.",
            "Either the system graph or successful "
            "target classification may synthesize a\n"
            "qualified `CapabilityProfile` entry "
            "without the required qualification\n"
            "evidence.",
        ),
        "section 27",
    )

    expect_fail(
        "external model output treated as evidence",
        lambda root: mutate_file(
            root,
            SPEC,
            "External-model output is not evidence "
            "merely because it was produced by a\n"
            "capable model or provider.",
            "External-model output is evidence "
            "merely because it was produced by a\n"
            "capable model or provider.",
        ),
        "section 29",
    )

    expect_fail(
        "provider allowed to define Hetren Core",
        lambda root: mutate_file(
            root,
            SPEC,
            "No provider may define Hetren Core "
            "semantics, shared intelligence behavior,\n"
            "success semantics, or verification authority.",
            "A provider may define Hetren Core "
            "semantics, shared intelligence behavior,\n"
            "success semantics, or verification authority.",
        ),
        "section 29",
    )

    expect_fail(
        "research programs create parallel architecture",
        lambda root: mutate_file(
            root,
            SPEC,
            "Neither research program creates a parallel:",
            "Native Intelligence and Adaptive Intelligence "
            "create a parallel:",
        ),
        "section 30",
    )

    expect_fail(
        "historical retirement becomes deletion",
        lambda root: mutate_file(
            root,
            SPEC,
            "Retirement is not deletion.",
            "Retirement is deletion.",
        ),
        "section 32",
    )

    expect_fail(
        "taxonomy may force target into E1",
        lambda root: mutate_file(
            root,
            SPEC,
            "It must not be forced into `E1_AGENT`, "
            "`E2_STRUCTURED_ML`, or `E3_VISION`",
            "It may be forced into `E1_AGENT`, "
            "`E2_STRUCTURED_ML`, or `E3_VISION`",
        ),
        "section 33",
    )

    expect_fail(
        "Task 5 ownership moved into Task 4",
        lambda root: mutate_file(
            root,
            SPEC,
            "Task 5 owns:",
            "Task 4 owns:",
        ),
        "section 34",
    )

    expect_fail(
        "classification allowed to manufacture support",
        lambda root: mutate_file(
            root,
            SPEC,
            "Classification must not manufacture support.",
            "Classification may manufacture support.",
        ),
        "section 36",
    )

    expect_fail(
        "Decision 0004 authority drift",
        lambda root: mutate_file(
            root,
            DECISION,
            "**Authority:** `AUTH-HETREN-MVP-3.0`",
            "**Authority:** `AUTH-HETREN-MVP-9.9`",
        ),
        "Decision 0004 metadata Authority",
    )

    expect_fail(
        "Decision 0004 register mismatch",
        lambda root: mutate_file(
            root,
            REGISTER,
            "| `0004` | `architecture.system-taxonomy` | "
            "Define governed MVP system taxonomy | "
            "`PROPOSED` | `ARCHITECTURE` |",
            "| `0004` | `architecture.system-taxonomy` | "
            "Define governed MVP system taxonomy | "
            "`ACCEPTED` | `ARCHITECTURE` |",
        ),
        "register row must match",
    )

    expect_final_fail(
        "qualification record missing",
        lambda root: (
            root / QUALIFICATION
        ).unlink(),
        "missing Decision 0004 qualification evidence",
    )

    expect_final_fail(
        "qualification condition evidence incomplete",
        lambda root: mutate_file(
            root,
            QUALIFICATION,
            "**Qualification conditions:** `50 / 50`",
            "**Qualification conditions:** `49 / 50`",
        ),
        "qualification metadata Qualification conditions",
    )

    expect_final_fail(
        "mutation qualification incomplete",
        lambda root: mutate_file(
            root,
            QUALIFICATION,
            "**Mutation result:** `34 / 34`",
            "**Mutation result:** `33 / 34`",
        ),
        "requires all recorded mutations to be rejected",
    )

    expect_final_fail(
        "qualification state not verified",
        lambda root: mutate_file(
            root,
            QUALIFICATION,
            "**Qualification state:** `VERIFIED`",
            "**Qualification state:** `DRAFT`",
        ),
        "qualification metadata Qualification state",
    )

    expect_final_fail(
        "qualification version mismatch",
        lambda root: mutate_file(
            root,
            QUALIFICATION,
            "**Specification version:** `1.0.0`",
            "**Specification version:** `1.1.0`",
        ),
        "Specification version must match system-taxonomy Version",
    )

    expect_final_fail(
        "implementation evidence returned to pending",
        lambda root: mutate_file(
            root,
            DECISION,
            "Implemented and preserved in:",
            "Pending implementation preserved in:",
        ),
        "Implementation Evidence remains pending",
    )

    expect_final_fail(
        "verification evidence returned to pending",
        lambda root: mutate_file(
            root,
            DECISION,
            "Verified by",
            "Pending verification by",
        ),
        "Verification Evidence remains pending",
    )

    expect_final_fail(
        "accepted register returned to proposed",
        lambda root: mutate_file(
            root,
            REGISTER,
            "| `0004` | `architecture.system-taxonomy` | "
            "Define governed MVP system taxonomy | "
            "`ACCEPTED` | `ARCHITECTURE` |",
            "| `0004` | `architecture.system-taxonomy` | "
            "Define governed MVP system taxonomy | "
            "`PROPOSED` | `ARCHITECTURE` |",
        ),
        "register row must match",
    )

    if MUTATIONS_KILLED != EXPECTED_MUTATIONS:
        raise AssertionError(
            "mutation-suite cardinality drift: "
            f"expected {EXPECTED_MUTATIONS}, "
            f"executed {MUTATIONS_KILLED}"
        )

    print()
    print(
        "SYSTEM TAXONOMY MUTATION SUITE: PASS "
        f"({MUTATIONS_KILLED}/{EXPECTED_MUTATIONS} "
        "mutations killed)"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
