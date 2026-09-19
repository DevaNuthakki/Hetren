#!/usr/bin/env python3

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

VALIDATOR = (
    ROOT
    / "scripts"
    / "check_research_hypotheses.py"
)

SPEC = "docs/mvp/06-research-hypotheses.md"

NATIVE_DECISION = (
    "docs/decisions/"
    "0006-native-intelligence-mvp-hypotheses.md"
)

ADAPTIVE_DECISION = (
    "docs/decisions/"
    "0007-adaptive-intelligence-mvp-hypotheses.md"
)

REGISTER = "docs/decisions/register.md"

NATIVE_QUALIFICATION = (
    "docs/decisions/qualification/"
    "0006-native-intelligence-mvp-hypotheses.md"
)

ADAPTIVE_QUALIFICATION = (
    "docs/decisions/qualification/"
    "0007-adaptive-intelligence-mvp-hypotheses.md"
)

DEVELOPMENT_MUTATIONS_EXPECTED = 36
FINAL_MUTATIONS_EXPECTED = 16
EXPECTED_MUTATIONS = 52

DEVELOPMENT_MUTATIONS_KILLED = 0
FINAL_MUTATIONS_KILLED = 0

assert (
    DEVELOPMENT_MUTATIONS_EXPECTED
    + FINAL_MUTATIONS_EXPECTED
    == EXPECTED_MUTATIONS
)


def make_repo() -> Path:
    temp = Path(
        tempfile.mkdtemp(
            prefix="hetren-research-hypotheses-test-"
        )
    )

    for relative in (
        SPEC,
        NATIVE_DECISION,
        ADAPTIVE_DECISION,
        REGISTER,
    ):
        source = ROOT / relative
        destination = temp / relative

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

    for relative in (
        NATIVE_QUALIFICATION,
        ADAPTIVE_QUALIFICATION,
    ):
        source = ROOT / relative

        if source.is_file():
            destination = temp / relative

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                source,
                destination,
            )

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


def replace_once(
    root: Path,
    relative: str,
    old: str,
    new: str,
) -> None:
    target = root / relative
    text = target.read_text()

    count = text.count(old)

    if count != 1:
        raise AssertionError(
            "mutation/state anchor count mismatch in "
            f"{relative}: expected 1, found {count}\n"
            f"anchor: {old}"
        )

    target.write_text(
        text.replace(
            old,
            new,
            1,
        )
    )


def regex_replace_once(
    root: Path,
    relative: str,
    pattern: str,
    replacement: str,
) -> None:
    target = root / relative
    text = target.read_text()

    updated, count = re.subn(
        pattern,
        replacement,
        text,
        count=1,
        flags=re.MULTILINE,
    )

    if count != 1:
        raise AssertionError(
            "regex replacement failed in "
            f"{relative}: {pattern}"
        )

    target.write_text(updated)


def replace_once_in_numbered_section(
    root: Path,
    relative: str,
    section_number: int,
    section_title: str,
    old: str,
    new: str,
) -> None:
    target = root / relative
    text = target.read_text()

    pattern = (
        rf"(?ms)^## {section_number}\. "
        rf"{re.escape(section_title)}\n"
        r"(.*?)(?=^## [0-9]+\. |\Z)"
    )

    match = re.search(pattern, text)

    if not match:
        raise AssertionError(
            "numbered section not found: "
            f"{section_number}. {section_title}"
        )

    body = match.group(1)

    count = body.count(old)

    if count != 1:
        raise AssertionError(
            "section-scoped mutation anchor count mismatch "
            f"in {relative}, section {section_number}: "
            f"expected 1, found {count}\n"
            f"anchor: {old}"
        )

    updated_body = body.replace(old, new, 1)

    updated = (
        text[:match.start(1)]
        + updated_body
        + text[match.end(1):]
    )

    target.write_text(updated)


def replace_markdown_section(
    root: Path,
    relative: str,
    heading: str,
    body: str,
) -> None:
    target = root / relative
    text = target.read_text()

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

    target.write_text(updated)


def set_spec_metadata(
    root: Path,
    *,
    version: str,
    status: str,
) -> None:
    regex_replace_once(
        root,
        SPEC,
        r"^\*\*Version:\*\* .+$",
        f"**Version:** {version}",
    )

    regex_replace_once(
        root,
        SPEC,
        r"^\*\*Status:\*\* .+$",
        f"**Status:** {status}",
    )


def set_decision_status(
    root: Path,
    relative: str,
    status: str,
) -> None:
    regex_replace_once(
        root,
        relative,
        r"^\*\*Status:\*\* .+$",
        f"**Status:** `{status}`",
    )


def set_register_status(
    root: Path,
    decision_id: str,
    status: str,
) -> None:
    target = root / REGISTER
    text = target.read_text()

    pattern = (
        rf"(?m)^(\|\s*`{re.escape(decision_id)}`\s*\|"
        r".*?\|\s*)`(?:PROPOSED|ACCEPTED)`"
        r"(\s*\|.*)$"
    )

    updated, count = re.subn(
        pattern,
        rf"\1`{status}`\2",
        text,
        count=1,
    )

    if count != 1:
        raise AssertionError(
            f"register status update failed for {decision_id}"
        )

    target.write_text(updated)


def remove_qualification_files(
    root: Path,
) -> None:
    for relative in (
        NATIVE_QUALIFICATION,
        ADAPTIVE_QUALIFICATION,
    ):
        target = root / relative

        if target.exists():
            target.unlink()


def restore_proposed_lifecycle_wording(
    root: Path,
) -> None:
    cases = (
        (
            NATIVE_DECISION,
            """Decision acceptance governs the Native thesis contract but is not
scientific evidence.""",
            """While this decision remains `PROPOSED`, it is not research implementation
authority.""",
        ),
        (
            ADAPTIVE_DECISION,
            """Decision acceptance governs the Adaptive thesis contract but is not
scientific evidence.""",
            """While this decision remains `PROPOSED`, it is not research implementation
authority.""",
        ),
    )

    for relative, accepted, proposed in cases:
        target = root / relative
        current = target.read_text()

        if proposed in current:
            continue

        if accepted not in current:
            raise AssertionError(
                "unable to normalize proposal lifecycle wording "
                f"in {relative}"
            )

        target.write_text(
            current.replace(
                accepted,
                proposed,
                1,
            )
        )


def set_development_state(
    root: Path,
) -> None:
    restore_proposed_lifecycle_wording(root)

    set_spec_metadata(
        root,
        version="0.1.0",
        status="Draft",
    )

    set_decision_status(
        root,
        NATIVE_DECISION,
        "PROPOSED",
    )

    set_decision_status(
        root,
        ADAPTIVE_DECISION,
        "PROPOSED",
    )

    set_register_status(
        root,
        "0006",
        "PROPOSED",
    )

    set_register_status(
        root,
        "0007",
        "PROPOSED",
    )

    replace_markdown_section(
        root,
        NATIVE_DECISION,
        "Implementation Evidence",
        "Pending while Decision `0006` remains `PROPOSED`.",
    )

    replace_markdown_section(
        root,
        NATIVE_DECISION,
        "Verification Evidence",
        "Pending while Decision `0006` remains `PROPOSED`.",
    )

    replace_markdown_section(
        root,
        ADAPTIVE_DECISION,
        "Implementation Evidence",
        "Pending while Decision `0007` remains `PROPOSED`.",
    )

    replace_markdown_section(
        root,
        ADAPTIVE_DECISION,
        "Verification Evidence",
        "Pending while Decision `0007` remains `PROPOSED`.",
    )

    remove_qualification_files(root)


def positive_control() -> None:
    root = make_repo()

    try:
        set_development_state(root)

        result = run_validator(root)

        if result.returncode != 0:
            raise AssertionError(
                "development positive control failed:\n"
                + result.stdout
                + result.stderr
            )

        print("PASS positive control")

    finally:
        shutil.rmtree(root)


def expect_fail(
    label: str,
    mutate,
) -> None:
    global DEVELOPMENT_MUTATIONS_KILLED

    root = make_repo()

    try:
        set_development_state(root)
        mutate(root)

        result = run_validator(root)

        if result.returncode == 0:
            raise AssertionError(
                f"mutation survived: {label}"
            )

        DEVELOPMENT_MUTATIONS_KILLED += 1
        print(f"PASS mutation killed: {label}")

    finally:
        shutil.rmtree(root)


# =========================================================
# Multi-edit mutations
# =========================================================


def mutate_uncertainty_to_90(root: Path) -> None:
    replace_once(
        root,
        SPEC,
        "a two-sided 95% interval or an equivalently conservative "
        "predeclared\n  interval;",
        "a two-sided 90% interval or an equivalently conservative "
        "predeclared\n  interval;",
    )

    replace_once(
        root,
        SPEC,
        "It may not weaken the 95% minimum confidence requirement "
        "after observing\nprotected evidence.",
        "It may not weaken the 90% minimum confidence requirement "
        "after observing\nprotected evidence.",
    )


def mutate_nh2_infrastructure_allowed(root: Path) -> None:
    replace_once(
        root,
        SPEC,
        "The following do not establish `N-H2` by themselves:",
        "The following may establish `N-H2` by themselves:",
    )


def mutate_ah1_self_certification(root: Path) -> None:
    replace_once(
        root,
        SPEC,
        "the proposing or adapting mechanism is not the sole authority "
        "certifying\n   success;",
        "the proposing or adapting mechanism may be the sole authority "
        "certifying\n   success;",
    )


def mutate_register_0007_accepted(root: Path) -> None:
    set_register_status(
        root,
        "0007",
        "ACCEPTED",
    )


# =========================================================
# Development-state mutations
# =========================================================


def run_development_mutations() -> None:
    cases = (
        (
            "wrong MVP execution authority",
            lambda root: replace_once(
                root,
                SPEC,
                "**Execution authority:** `AUTH-HETREN-MVP-3.0`",
                "**Execution authority:** `AUTH-HETREN-MVP-2.0`",
            ),
        ),
        (
            "wrong long-term authority",
            lambda root: replace_once(
                root,
                SPEC,
                "**Long-term authority:** `AUTH-HETREN-MASTER-2.0`",
                "**Long-term authority:** `AUTH-HETREN-MASTER-1.0`",
            ),
        ),
        (
            "section topology drift",
            lambda root: replace_once(
                root,
                SPEC,
                "## 50. Research-Hypothesis Principle",
                "## 50. Research Principle",
            ),
        ),
        (
            "qualification condition topology drift",
            lambda root: replace_once(
                root,
                SPEC,
                "50. Task 6 completion remains explicitly separate",
                "51. Task 6 completion remains explicitly separate",
            ),
        ),
        (
            "initial N-H1 hypothesis removed",
            lambda root: replace_once(
                root,
                SPEC,
                "- `N-H1` — Learned Investigation Value;",
                "- Learned Investigation Value;",
            ),
        ),
        (
            "Native evidence allowed to establish Adaptive hypothesis",
            lambda root: replace_once(
                root,
                SPEC,
                "Native evidence cannot establish an Adaptive hypothesis.",
                "Native evidence may establish an Adaptive hypothesis.",
            ),
        ),
        (
            "product result allowed to establish research hypothesis",
            lambda root: replace_once(
                root,
                SPEC,
                "A product result cannot establish either research "
                "hypothesis by itself.",
                "A product result may establish either research "
                "hypothesis by itself.",
            ),
        ),
        (
            "sixth evaluation outcome allowed",
            lambda root: replace_once(
                root,
                SPEC,
                "Task 6 does not introduce a sixth evaluation outcome.",
                "Task 6 may introduce a sixth evaluation outcome.",
            ),
        ),
        (
            "protected threshold freeze removed",
            lambda root: replace_once(
                root,
                SPEC,
                "Protected thresholds must be frozen before protected "
                "results are inspected.",
                "Protected thresholds may be chosen after protected "
                "results are inspected.",
            ),
        ),
        (
            "uncertainty requirement weakened to 90 percent",
            mutate_uncertainty_to_90,
        ),
        (
            "negative results no longer first-class evidence",
            lambda root: replace_once(
                root,
                SPEC,
                "Negative results are first-class research evidence.",
                "Negative results may be omitted from research evidence.",
            ),
        ),
        (
            "Task 7 split ownership stolen",
            lambda root: replace_once(
                root,
                SPEC,
                "Task 7 owns concrete:",
                "Task 6 owns concrete:",
            ),
        ),
        (
            "Task 8 baseline ownership stolen",
            lambda root: replace_once(
                root,
                SPEC,
                "Task 8 owns concrete:",
                "Task 6 owns concrete:",
            ),
        ),
        (
            "Task 9 cost ownership stolen",
            lambda root: replace_once(
                root,
                SPEC,
                "Task 9 owns concrete:",
                "Task 6 owns concrete:",
            ),
        ),
        (
            "N-H1 material-effect gate weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "measure by at least **5% relative** to the strongest "
                "matched baseline;",
                "measure by at least **1% relative** to the strongest "
                "matched baseline;",
            ),
        ),
        (
            "N-H1 positive confidence bound weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "improvement is greater than zero;",
                "improvement is at least zero;",
            ),
        ),
        (
            "N-H1 pseudo-replication allowed",
            lambda root: replace_once(
                root,
                SPEC,
                "resamples, or runs from the same governed unit do not "
                "by themselves create\n   a second independent unit;",
                "resamples, or runs from the same governed unit may "
                "by themselves create\n   a second independent unit;",
            ),
        ),
        (
            "N-H1 heuristic attribution protection removed",
            lambda root: replace_once(
                root,
                SPEC,
                "the claimed decision value is actually attributable "
                "only to an external\n  generator, deterministic "
                "heuristic, or authored strategy;",
                "the candidate uses an external generator;",
            ),
        ),
        (
            "N-H2 protected target gate weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "decision-quality measure by at least **3% relative** "
                "to the strongest\n   applicable non-transfer or "
                "non-learned comparator;",
                "decision-quality measure by at least **1% relative** "
                "to the strongest\n   applicable non-transfer or "
                "non-learned comparator;",
            ),
        ),
        (
            "N-H2 source advantage no longer strictly positive",
            lambda root: replace_once(
                root,
                SPEC,
                "comparator is strictly greater than zero under the "
                "predeclared comparison;",
                "comparator is at least zero under the "
                "predeclared comparison;",
            ),
        ),
        (
            "N-H2 retained advantage weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "retains at least **50% of that positive\n   "
                "source-side incremental advantage**;",
                "retains at least **10% of that positive\n   "
                "source-side incremental advantage**;",
            ),
        ),
        (
            "N-H2 infrastructure reuse allowed as transfer proof",
            mutate_nh2_infrastructure_allowed,
        ),
        (
            "A-H1 pre-adaptation gain weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "**5% relative** to its own pre-adaptation state;",
                "**1% relative** to its own pre-adaptation state;",
            ),
        ),
        (
            "A-H1 adaptation-baseline advantage weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "least **3% relative** to the strongest matched "
                "adaptation baseline;",
                "least **1% relative** to the strongest matched "
                "adaptation baseline;",
            ),
        ),
        (
            "A-H1 critical invariant protection weakened",
            lambda root: replace_once_in_numbered_section(
                root,
                SPEC,
                30,
                "A-H1 Qualification Criteria",
                "there are **zero critical-invariant violations**;",
                "there may be **one critical-invariant violation**;",
            ),
        ),
        (
            "A-H1 adaptive self-certification allowed",
            mutate_ah1_self_certification,
        ),
        (
            "A-H2 retention degradation tolerance weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "**2% relative** on the predeclared retention measure;",
                "**10% relative** on the predeclared retention measure;",
            ),
        ),
        (
            "A-H2 locality tolerance weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "**2% of that measure's governed normalized scale**;",
                "**10% of that measure's governed normalized scale**;",
            ),
        ),
        (
            "A-H2 executed rollback requirement weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "rollback is actually executed rather than merely "
                "described;",
                "rollback may be merely described without execution;",
            ),
        ),
        (
            "A-H2 rollback restoration tolerance weakened",
            lambda root: replace_once(
                root,
                SPEC,
                "within **1% relative** of the preserved "
                "pre-adaptation value;",
                "within **5% relative** of the preserved "
                "pre-adaptation value;",
            ),
        ),
        (
            "A-H1 allowed to imply A-H2",
            lambda root: replace_once(
                root,
                SPEC,
                "Passing `A-H1` does not imply `A-H2`.",
                "Passing `A-H1` implies `A-H2`.",
            ),
        ),
        (
            "stronger self-improvement exclusion removed",
            lambda root: replace_once(
                root,
                SPEC,
                "- autonomous self-improvement;",
                "- bounded optimization;",
            ),
        ),
        (
            "Native transfer allowed to establish Adaptive transfer",
            lambda root: replace_once(
                root,
                SPEC,
                "It does not establish Adaptive transfer.",
                "It establishes Adaptive transfer.",
            ),
        ),
        (
            "invalidated evidence allowed to remain authoritative",
            lambda root: replace_once(
                root,
                SPEC,
                "It must not silently remain authoritative.",
                "It may silently remain authoritative.",
            ),
        ),
        (
            "Decision 0006 research program drift",
            lambda root: replace_once(
                root,
                NATIVE_DECISION,
                "**Research Program:** `NATIVE`",
                "**Research Program:** `CROSS_PROGRAM`",
            ),
        ),
        (
            "Decision 0007 register prematurely accepted",
            mutate_register_0007_accepted,
        ),
    )

    if len(cases) != DEVELOPMENT_MUTATIONS_EXPECTED:
        raise AssertionError(
            "development mutation definition count mismatch: "
            f"{len(cases)} != {DEVELOPMENT_MUTATIONS_EXPECTED}"
        )

    for label, mutate in cases:
        expect_fail(label, mutate)



def write_synthetic_qualification(
    root: Path,
    *,
    decision_id: str,
    decision_key: str,
    title: str,
    relative: str,
) -> None:
    target = root / relative

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    content = f"""# Decision {decision_id} Qualification Record

**Task:** `6 / 100`
**Decision:** `{decision_id}`
**Decision Key:** `{decision_key}`
**Date:** `2026-09-18`
**Result:** `PASS`
**Qualification state:** `VERIFIED`
**Specification:** `docs/mvp/06-research-hypotheses.md`
**Specification version:** `1.0.0`
**Validator:** `scripts/check_research_hypotheses.py`
**Mutation suite:** `tests/qualification/test_research_hypotheses.py`
**Qualification conditions:** `50 / 50`
**Mutation result:** `52 / 52`
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Task 1 regression:** `PASS`
**Task 2 regression:** `PASS`
**Task 3 regression:** `PASS`
**Task 4 regression:** `PASS`
**Task 5 regression:** `PASS`
**Diff check:** `PASS`
**Scientific support established:** `NO`
**Final accepted-state qualification:** `PASS`

## Scope

This record qualifies the Task 6 research-hypothesis contract for:

{title}.

It does not establish scientific truth or scientific support for the governed
hypotheses.

## Positive Qualification

PASS.

The governed Task 6 specification contains exactly 50 numbered sections,
exactly 50 ordered qualification conditions, and exactly four initial
hypotheses.

## Structural Qualification

PASS.

The validator verifies the specification, all 50 conditions, Decision 0006,
Decision 0007, decision-register synchronization, and final qualification
evidence.

## Semantic Qualification

PASS.

Native and Adaptive evidence remain separate. Protected threshold,
falsification, negative-result, transfer, retention, locality, rollback, and
scientific support boundaries remain governed.

## Adversarial Qualification

PASS.

The frozen suite killed 52 / 52 mutations across development and final
accepted-state qualification.

## Authority And Regression Qualification

PASS.

Task 1: PASS.
Task 2: PASS.
Task 3: PASS.
Task 4: PASS.
Task 5: PASS.

## Limitations

This qualification accepts the research-hypothesis contract itself.

It does not establish scientific support for any Task 6 hypothesis.

The hypotheses remain scientifically unresolved until later valid
experimental evidence is produced under the applicable governed protocols.

## Acceptance Decision

Decision {decision_id} is `ACCEPTED`.

The Task 6 research-hypothesis specification is version `1.0.0` and
`Qualified`.

The governed adversarial qualification result is `52 / 52`.

Scientific support established: `NO`.

Final accepted-state qualification: PASS.
"""

    target.write_text(content)


def set_final_state(
    root: Path,
) -> None:
    set_development_state(root)

    set_spec_metadata(
        root,
        version="1.0.0",
        status="Qualified",
    )

    set_decision_status(
        root,
        NATIVE_DECISION,
        "ACCEPTED",
    )

    set_decision_status(
        root,
        ADAPTIVE_DECISION,
        "ACCEPTED",
    )

    set_register_status(
        root,
        "0006",
        "ACCEPTED",
    )

    set_register_status(
        root,
        "0007",
        "ACCEPTED",
    )

    replace_once(
        root,
        NATIVE_DECISION,
        """While this decision remains `PROPOSED`, it is not research implementation
authority.""",
        """Decision acceptance governs the Native thesis contract but is not
scientific evidence.""",
    )

    replace_once(
        root,
        ADAPTIVE_DECISION,
        """While this decision remains `PROPOSED`, it is not research implementation
authority.""",
        """Decision acceptance governs the Adaptive thesis contract but is not
scientific evidence.""",
    )

    replace_markdown_section(
        root,
        NATIVE_DECISION,
        "Implementation Evidence",
        """
Implemented and preserved in:

- `docs/mvp/06-research-hypotheses.md`;
- `scripts/check_research_hypotheses.py`;
- `tests/qualification/test_research_hypotheses.py`.

The governed Task 6 validator enforces the Native thesis contract.
""",
    )

    replace_markdown_section(
        root,
        NATIVE_DECISION,
        "Verification Evidence",
        """
Verified by:

- `docs/decisions/qualification/0006-native-intelligence-mvp-hypotheses.md`.

Final accepted-state qualification is required.
""",
    )

    replace_markdown_section(
        root,
        ADAPTIVE_DECISION,
        "Implementation Evidence",
        """
Implemented and preserved in:

- `docs/mvp/06-research-hypotheses.md`;
- `scripts/check_research_hypotheses.py`;
- `tests/qualification/test_research_hypotheses.py`.

The governed Task 6 validator enforces the Adaptive thesis contract.
""",
    )

    replace_markdown_section(
        root,
        ADAPTIVE_DECISION,
        "Verification Evidence",
        """
Verified by:

- `docs/decisions/qualification/0007-adaptive-intelligence-mvp-hypotheses.md`.

Final accepted-state qualification is required.
""",
    )

    write_synthetic_qualification(
        root,
        decision_id="0006",
        decision_key=(
            "research.native-intelligence.mvp-hypotheses"
        ),
        title=(
            "Govern initial Native Intelligence MVP hypotheses"
        ),
        relative=NATIVE_QUALIFICATION,
    )

    write_synthetic_qualification(
        root,
        decision_id="0007",
        decision_key=(
            "research.adaptive-intelligence.mvp-hypotheses"
        ),
        title=(
            "Govern initial Adaptive Intelligence MVP hypotheses"
        ),
        relative=ADAPTIVE_QUALIFICATION,
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
                "final-state positive control failed:\n"
                + result.stdout
                + result.stderr
            )

        print("PASS final-state positive control")

    finally:
        shutil.rmtree(root)


def expect_final_fail(
    label: str,
    mutate,
) -> None:
    global FINAL_MUTATIONS_KILLED

    root = make_repo()

    try:
        set_final_state(root)
        mutate(root)

        result = run_validator(
            root,
            "--require-qualified",
        )

        if result.returncode == 0:
            raise AssertionError(
                f"final mutation survived: {label}"
            )

        FINAL_MUTATIONS_KILLED += 1

        print(
            f"PASS final mutation killed: {label}"
        )

    finally:
        shutil.rmtree(root)


def remove_file(
    root: Path,
    relative: str,
) -> None:
    target = root / relative

    if not target.is_file():
        raise AssertionError(
            f"expected file missing before mutation: {relative}"
        )

    target.unlink()


def set_qualification_metadata(
    root: Path,
    relative: str,
    key: str,
    value: str,
) -> None:
    regex_replace_once(
        root,
        relative,
        rf"^\*\*{re.escape(key)}:\*\* .+$",
        f"**{key}:** `{value}`",
    )


def run_final_mutations() -> None:
    cases = (
        (
            "Native qualification record missing",
            lambda root: remove_file(
                root,
                NATIVE_QUALIFICATION,
            ),
        ),
        (
            "Adaptive qualification record missing",
            lambda root: remove_file(
                root,
                ADAPTIVE_QUALIFICATION,
            ),
        ),
        (
            "Native qualification result falsified",
            lambda root: set_qualification_metadata(
                root,
                NATIVE_QUALIFICATION,
                "Result",
                "FAIL",
            ),
        ),
        (
            "Adaptive qualification state not verified",
            lambda root: set_qualification_metadata(
                root,
                ADAPTIVE_QUALIFICATION,
                "Qualification state",
                "PENDING",
            ),
        ),
        (
            "final specification version drift",
            lambda root: set_spec_metadata(
                root,
                version="1.0.1",
                status="Qualified",
            ),
        ),
        (
            "Native mutation evidence incomplete",
            lambda root: set_qualification_metadata(
                root,
                NATIVE_QUALIFICATION,
                "Mutation result",
                "51 / 52",
            ),
        ),
        (
            "Adaptive qualification fabricates scientific support",
            lambda root: set_qualification_metadata(
                root,
                ADAPTIVE_QUALIFICATION,
                "Scientific support established",
                "YES",
            ),
        ),
        (
            "Native accepted decision demoted to proposed",
            lambda root: set_decision_status(
                root,
                NATIVE_DECISION,
                "PROPOSED",
            ),
        ),
        (
            "Adaptive accepted register demoted to proposed",
            lambda root: set_register_status(
                root,
                "0007",
                "PROPOSED",
            ),
        ),
        (
            "Native accepted implementation evidence returned to pending",
            lambda root: replace_markdown_section(
                root,
                NATIVE_DECISION,
                "Implementation Evidence",
                "Pending.",
            ),
        ),
        (
            "Adaptive accepted verification evidence returned to pending",
            lambda root: replace_markdown_section(
                root,
                ADAPTIVE_DECISION,
                "Verification Evidence",
                "Pending.",
            ),
        ),
        (
            "Native qualification decision key drift",
            lambda root: set_qualification_metadata(
                root,
                NATIVE_QUALIFICATION,
                "Decision Key",
                "research.native-intelligence.wrong",
            ),
        ),
        (
            "Adaptive qualification specification version drift",
            lambda root: set_qualification_metadata(
                root,
                ADAPTIVE_QUALIFICATION,
                "Specification version",
                "0.9.0",
            ),
        ),
        (
            "Native Task 5 regression not passing",
            lambda root: set_qualification_metadata(
                root,
                NATIVE_QUALIFICATION,
                "Task 5 regression",
                "FAIL",
            ),
        ),
        (
            "Adaptive final qualification not passing",
            lambda root: set_qualification_metadata(
                root,
                ADAPTIVE_QUALIFICATION,
                "Final accepted-state qualification",
                "FAIL",
            ),
        ),
        (
            "Native qualification date invalid",
            lambda root: set_qualification_metadata(
                root,
                NATIVE_QUALIFICATION,
                "Date",
                "2026-99-99",
            ),
        ),
    )

    if len(cases) != FINAL_MUTATIONS_EXPECTED:
        raise AssertionError(
            "final mutation definition count mismatch: "
            f"{len(cases)} != {FINAL_MUTATIONS_EXPECTED}"
        )

    for label, mutate in cases:
        expect_final_fail(
            label,
            mutate,
        )


def main() -> None:
    print("===== POSITIVE CONTROL =====")
    positive_control()

    print()
    print("===== FINAL-STATE POSITIVE CONTROL =====")
    final_positive_control()

    print()
    print("===== DEVELOPMENT MUTATIONS =====")
    run_development_mutations()

    print()

    if (
        DEVELOPMENT_MUTATIONS_KILLED
        != DEVELOPMENT_MUTATIONS_EXPECTED
    ):
        raise AssertionError(
            "development mutation cardinality mismatch: "
            f"killed {DEVELOPMENT_MUTATIONS_KILLED}, "
            f"expected {DEVELOPMENT_MUTATIONS_EXPECTED}"
        )

    print(
        "TASK 6 DEVELOPMENT MUTATIONS: PASS "
        f"({DEVELOPMENT_MUTATIONS_KILLED}/"
        f"{DEVELOPMENT_MUTATIONS_EXPECTED} mutations killed)"
    )

    print()
    print("===== FINAL-STATE MUTATIONS =====")
    run_final_mutations()

    print()

    if (
        FINAL_MUTATIONS_KILLED
        != FINAL_MUTATIONS_EXPECTED
    ):
        raise AssertionError(
            "final mutation cardinality mismatch: "
            f"killed {FINAL_MUTATIONS_KILLED}, "
            f"expected {FINAL_MUTATIONS_EXPECTED}"
        )

    print(
        "TASK 6 FINAL-STATE MUTATIONS: PASS "
        f"({FINAL_MUTATIONS_KILLED}/"
        f"{FINAL_MUTATIONS_EXPECTED} mutations killed)"
    )

    total = (
        DEVELOPMENT_MUTATIONS_KILLED
        + FINAL_MUTATIONS_KILLED
    )

    if total != EXPECTED_MUTATIONS:
        raise AssertionError(
            "Task 6 mutation cardinality mismatch: "
            f"killed {total}, expected {EXPECTED_MUTATIONS}"
        )

    print()
    print(
        "TASK 6 MUTATION SUITE: PASS "
        f"({total}/{EXPECTED_MUTATIONS} mutations killed)"
    )


if __name__ == "__main__":
    main()
