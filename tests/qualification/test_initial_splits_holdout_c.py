#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CANONICAL = (
    ROOT
    / "tests"
    / "qualification"
    / "test_initial_splits.py"
)

module_spec = importlib.util.spec_from_file_location(
    "hetren_task7_set_c_helpers",
    CANONICAL,
)

if module_spec is None or module_spec.loader is None:
    raise RuntimeError(
        "could not load canonical Task 7 helpers"
    )

helpers = importlib.util.module_from_spec(
    module_spec
)

module_spec.loader.exec_module(
    helpers
)

SPEC = helpers.SPEC
DECISION = helpers.DECISION

SET_C_FAMILIES = 8
SET_C_VARIANTS_PER_FAMILY = 8
SET_C_EXPECTED = (
    SET_C_FAMILIES
    * SET_C_VARIANTS_PER_FAMILY
)


def append_to_numbered_section(
    root: Path,
    section_number: int,
    section_title: str,
    addition: str,
) -> None:
    target = root / SPEC
    text = target.read_text()

    pattern = (
        rf"(?ms)^## {section_number}\. "
        rf"{re.escape(section_title)}\n"
        r"(.*?)"
        r"(?=^## [0-9]+\. |\Z)"
    )

    match = re.search(
        pattern,
        text,
    )

    if not match:
        raise AssertionError(
            "numbered section not found: "
            f"{section_number}. {section_title}"
        )

    body = match.group(1).rstrip()

    target.write_text(
        text[:match.start(1)]
        + body
        + "\n\n"
        + addition.strip()
        + "\n"
        + text[match.end(1):]
    )


def append_to_decision_section(
    root: Path,
    section_title: str,
    addition: str,
) -> None:
    target = root / DECISION
    text = target.read_text()

    pattern = (
        rf"(?ms)^## {re.escape(section_title)}\n"
        r"(.*?)"
        r"(?=^## |\Z)"
    )

    match = re.search(
        pattern,
        text,
    )

    if not match:
        raise AssertionError(
            f"decision section not found: {section_title}"
        )

    body = match.group(1).rstrip()

    target.write_text(
        text[:match.start(1)]
        + body
        + "\n\n"
        + addition.strip()
        + "\n"
        + text[match.end(1):]
    )


MODALS = (
    "may",
    "can",
    "is allowed to",
    "is permitted to",
    "is authorized to",
    "is acceptable to",
    "is considered valid when configured to",
    "is operationally permitted to",
)


def family_proxy_feedback():
    proxies = (
        "traffic-light status",
        "quantized performance bucket",
        "binary improved-or-worse indicator",
        "percentile band",
        "coarsened success tier",
        "aggregate quality flag",
        "threshold-crossing signal",
        "red-yellow-green dashboard value",
    )

    cases = []

    for index, proxy in enumerate(proxies):
        modal = MODALS[index]

        sentence = (
            f"The candidate-producing process {modal} use a "
            f"{proxy} derived from protected target outcomes "
            "to choose the next method before candidate freeze, "
            "provided raw protected cases remain hidden."
        )

        cases.append(
            (
                f"C01.{index + 1:02d} protected proxy feedback: {proxy}",
                lambda root, sentence=sentence:
                    append_to_numbered_section(
                        root,
                        36,
                        "N-H2 Transfer Leakage Controls",
                        sentence,
                    ),
            )
        )

    return cases


def family_pseudoreplication():
    separators = (
        "different annotators",
        "different calendar days",
        "different cloud regions",
        "different worker pools",
        "different file shards",
        "different API sessions",
        "different evaluation scripts",
        "different review queues",
    )

    cases = []

    for index, separator in enumerate(separators):
        modal = MODALS[index]

        sentence = (
            f"Two evaluations derived from one shared upstream "
            f"evidence source {modal} count as independent when "
            f"they use {separator}, even though the source lineage "
            "is unchanged."
        )

        cases.append(
            (
                f"C02.{index + 1:02d} pseudoreplication via {separator}",
                lambda root, sentence=sentence:
                    append_to_numbered_section(
                        root,
                        32,
                        "N-H1 Independent Evaluation Units",
                        sentence,
                    ),
            )
        )

    return cases


def family_split_identity_laundering():
    changes = (
        "move the membership pointer to a refreshed dataset snapshot",
        "replace the manifest member index",
        "remap the partition membership table",
        "refresh the referenced dataset revision",
        "redirect the manifest to a corrected member collection",
        "substitute a newer membership snapshot",
        "rebind the member registry to a revised population",
        "swap the underlying membership object",
    )

    cases = []

    for index, change in enumerate(changes):
        modal = MODALS[index]

        sentence = (
            f"A frozen `SplitVersion` {modal} retain its existing "
            f"identity after operators {change}, as long as the "
            "previous digest remains recoverable."
        )

        cases.append(
            (
                f"C03.{index + 1:02d} SplitVersion identity laundering",
                lambda root, sentence=sentence:
                    append_to_numbered_section(
                        root,
                        12,
                        "SplitVersion",
                        sentence,
                    ),
            )
        )

    return cases


def family_contamination_laundering():
    excuses = (
        "a heuristic risk score falls below five percent",
        "a reviewer judges exposure unlikely",
        "no new evidence appears for thirty days",
        "a confidence model predicts low leakage probability",
        "only aggregate information was exposed",
        "the exposed artifact is no longer accessible",
        "the suspected source has been archived",
        "the candidate later performs consistently",
    )

    cases = []

    for index, excuse in enumerate(excuses):
        modal = MODALS[index]

        sentence = (
            f"A `SUSPECTED` contamination state {modal} be treated "
            f"as operationally `CLEAN` when {excuse}, without a "
            "governed contamination-resolution event."
        )

        cases.append(
            (
                f"C04.{index + 1:02d} contamination laundering",
                lambda root, sentence=sentence:
                    append_to_numbered_section(
                        root,
                        27,
                        "ContaminationState",
                        sentence,
                    ),
            )
        )

    return cases


def family_fake_verification_independence():
    boundaries = (
        "a different operating-system process",
        "a separate container",
        "another cloud account",
        "a separate service endpoint",
        "a different CI job",
        "another execution host",
        "a separate orchestration worker",
        "a distinct runtime namespace",
    )

    shared = (
        "same controlling agent",
        "same writable evidence store",
        "same credentials",
        "same candidate-producing authority",
        "same mutable verification database",
        "same operator-controlled secret",
        "same write-capable storage identity",
        "same authority principal",
    )

    cases = []

    for index, (boundary, shared_authority) in enumerate(
        zip(boundaries, shared)
    ):
        modal = MODALS[index]

        sentence = (
            f"A verifier running in {boundary} {modal} certify the "
            f"candidate even when it shares the {shared_authority} "
            "with the candidate-producing path."
        )

        cases.append(
            (
                f"C05.{index + 1:02d} fake verifier independence",
                lambda root, sentence=sentence:
                    append_to_numbered_section(
                        root,
                        44,
                        "Independent Verification And Authority Separation",
                        sentence,
                    ),
            )
        )

    return cases


def family_adaptive_laundering():
    rescue = (
        "rollback succeeds",
        "locality remains within limits",
        "prior capability is retained",
        "critical invariants remain green",
        "post-rollback behavior returns to baseline",
        "retention metrics pass",
        "rollback evidence is reproducible",
        "the adapted candidate remains stable",
    )

    cases = []

    for index, condition in enumerate(rescue):
        modal = MODALS[index]

        sentence = (
            f"A passing `A-H2` result {modal} retroactively validate "
            f"an `A-H1` result with incomplete protected-outcome "
            f"separation when {condition}."
        )

        cases.append(
            (
                f"C06.{index + 1:02d} Adaptive hypothesis laundering",
                lambda root, sentence=sentence:
                    append_to_numbered_section(
                        root,
                        39,
                        "A-H2 Split Binding",
                        sentence,
                    ),
            )
        )

    return cases


def family_data_consequence_waiver():
    excuses = (
        "an authorized reviewer expects the conclusion to remain stable",
        "the membership delta is considered small",
        "the previous score is comfortably above threshold",
        "the revised records appear equivalent",
        "the change is operationally inconvenient to rerun",
        "the prior evidence is expensive to reproduce",
        "the reviewer considers the defect low risk",
        "the historical result is internally consistent",
    )

    cases = []

    for index, excuse in enumerate(excuses):
        modal = MODALS[index]

        sentence = (
            f"For a material split revision, governance {modal} "
            "reuse the prior result instead of executing "
            "`RERUN_AND_PRESERVE_DATA_DISTINCTIONS` when "
            f"{excuse}."
        )

        cases.append(
            (
                f"C07.{index + 1:02d} DATA consequence waiver",
                lambda root, sentence=sentence:
                    append_to_decision_section(
                        root,
                        "Decision",
                        sentence,
                    ),
            )
        )

    return cases


def family_distributed_baseline_cost():
    baseline_phrases = (
        "resource eligibility may later determine which frozen comparator is reported",
        "cost eligibility can later narrow the frozen comparator set",
        "reporting eligibility is allowed to filter frozen comparators",
        "a resource rule is permitted to remove a frozen comparator from reporting",
        "cost classification is authorized to decide which comparator remains visible",
        "resource eligibility is acceptable as a later comparator filter",
        "a later accounting rule is considered valid when configured to restrict comparator reporting",
        "resource policy is operationally permitted to narrow the reportable comparator set",
    )

    accounting_phrases = (
        "after protected results are known, the accounting window may be adjusted to preserve the preferred efficiency conclusion",
        "once protected outcomes are visible, cost boundaries can be changed to keep the favorable comparison",
        "protected measurements may be used to revise the accounting window toward the preferred comparator",
        "after protected evaluation, accounting is permitted to exclude costs that reverse the favorable result",
        "observed protected results are authorized to influence which resource window is reportable",
        "post-result resource accounting is acceptable when it retains the preferred efficiency conclusion",
        "protected measurements are considered valid inputs when configured to narrow accounting eligibility toward the favorable comparator",
        "after outcomes are known, resource policy is operationally permitted to preserve only the advantageous comparison",
    )

    cases = []

    for index, (baseline_sentence, accounting_sentence) in enumerate(
        zip(
            baseline_phrases,
            accounting_phrases,
        )
    ):
        def mutate(
            root,
            baseline_sentence=baseline_sentence,
            accounting_sentence=accounting_sentence,
        ):
            append_to_numbered_section(
                root,
                45,
                "Task 8 Baseline Handoff",
                baseline_sentence + ".",
            )

            append_to_numbered_section(
                root,
                46,
                "Task 9 Cost And Resource Handoff",
                accounting_sentence + ".",
            )

        cases.append(
            (
                f"C08.{index + 1:02d} distributed baseline/resource gaming",
                mutate,
            )
        )

    return cases


def set_c_cases():
    families = (
        family_proxy_feedback(),
        family_pseudoreplication(),
        family_split_identity_laundering(),
        family_contamination_laundering(),
        family_fake_verification_independence(),
        family_adaptive_laundering(),
        family_data_consequence_waiver(),
        family_distributed_baseline_cost(),
    )

    assert len(families) == SET_C_FAMILIES

    for family in families:
        assert len(family) == SET_C_VARIANTS_PER_FAMILY

    return tuple(
        itertools.chain.from_iterable(
            families
        )
    )


def attack_definition_hash() -> str:
    source = Path(__file__).read_text()

    start = source.index(
        "MODALS = ("
    )

    end = source.index(
        "\ndef attack_definition_hash()",
        start,
    )

    attack_source = source[
        start:end
    ]

    return hashlib.sha256(
        attack_source.encode()
    ).hexdigest()


def run_set_c() -> tuple[int, list[str]]:
    killed = 0
    survived: list[str] = []

    cases = set_c_cases()

    if len(cases) != SET_C_EXPECTED:
        raise AssertionError(
            "Set C cardinality mismatch: "
            f"{len(cases)} != {SET_C_EXPECTED}"
        )

    for label, mutate in cases:
        root = helpers.make_repo()

        try:
            helpers.set_development_state(
                root
            )

            mutate(
                root
            )

            result = helpers.run_validator(
                root
            )

            if result.returncode == 0:
                survived.append(
                    label
                )

                print(
                    f"FAIL Set C survived: {label}"
                )

            else:
                killed += 1

                print(
                    f"PASS Set C killed: {label}"
                )

        finally:
            shutil.rmtree(
                root
            )

    return killed, survived


def main() -> None:
    print(
        "===== SET C POSITIVE CONTROL ====="
    )

    root = helpers.make_repo()

    try:
        helpers.set_development_state(
            root
        )

        result = helpers.run_validator(
            root
        )

        if result.returncode != 0:
            raise AssertionError(
                "Set C positive control failed:\n"
                + result.stdout
                + result.stderr
            )

        print(
            "PASS Set C positive control"
        )

    finally:
        shutil.rmtree(
            root
        )

    print()
    print(
        "===== SET C DISCOVERED GENERATED REGRESSION ====="
    )

    print(
        "Families: "
        f"{SET_C_FAMILIES}"
    )

    print(
        "Variants per family: "
        f"{SET_C_VARIANTS_PER_FAMILY}"
    )

    print(
        "Total generated attacks: "
        f"{SET_C_EXPECTED}"
    )

    print(
        "Attack-definition SHA-256: "
        + attack_definition_hash()
    )

    killed, survived = run_set_c()

    print()
    print(
        "===== SET C RESULT ====="
    )

    print(
        f"Killed: {killed}/{SET_C_EXPECTED}"
    )

    print(
        f"Survived: {len(survived)}/{SET_C_EXPECTED}"
    )

    if survived:
        print(
            "Survivors:"
        )

        for label in survived:
            print(
                f"- {label}"
            )

        raise AssertionError(
            "Task 7 validator has Set C regression survivors"
        )

    print(
        "TASK 7 SET C GENERATED REGRESSION: PASS "
        f"({killed}/{SET_C_EXPECTED} attacks killed)"
    )


if __name__ == "__main__":
    main()
