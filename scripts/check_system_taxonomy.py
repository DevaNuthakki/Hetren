#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


SPEC_RELATIVE = Path("docs/mvp/04-system-taxonomy.md")
DECISION_RELATIVE = Path("docs/decisions/0004-system-taxonomy.md")
REGISTER_RELATIVE = Path("docs/decisions/register.md")
QUALIFICATION_RELATIVE = Path(
    "docs/decisions/qualification/0004-system-taxonomy.md"
)

EXPECTED_SPEC_METADATA = {
    "MVP Task": "4 / 100",
    "Execution authority": "AUTH-HETREN-MVP-3.0",
    "Long-term authority": "AUTH-HETREN-MASTER-2.0",
    "Governing decision": "0004",
    "Canonical captured-state record": "SystemSnapshot",
    "Canonical capability record": "CapabilityProfile",
    "Canonical artifact-provenance structure": "Artifact Graph",
}

EXPECTED_DECISION_METADATA = {
    "Decision ID": "0004",
    "Decision Key": "architecture.system-taxonomy",
    "Title": "Define governed MVP system taxonomy",
    "Class": "ARCHITECTURE",
    "Authority": "AUTH-HETREN-MVP-3.0",
    "Research Program": "NONE",
    "Research Change Category": "NONE",
    "Evidence Consequence": "NONE",
    "Supersedes": "None",
    "Superseded By": "None",
    "Reversibility": "CONDITIONALLY_REVERSIBLE",
    "Qualification": "Task 4 system-taxonomy qualification",
}

SECTION_TITLES = (
    "Purpose",
    "Authority And Scope",
    "Taxonomy Versus Support",
    "Target-System And Hetren-Implementation Boundary",
    "Tenant Boundary",
    "System Identity",
    "System Version",
    "System Form",
    "Environment Family",
    "E1 Tool-Using Agent",
    "E2 Structured-Data ML Pipeline",
    "E3 Vision System",
    "Future Environment Families",
    "Component Identity And Role",
    "Component Version",
    "Provider Identity And Binding",
    "Adapter Identity And Binding",
    "Evaluator Identity And Binding",
    "Investigation Surface",
    "Behavioral Investigation Surface",
    "Authorized Internal Investigation Surface",
    "Versioned System Graph",
    "Graph Planes And Relationship Vocabulary",
    "Graph Validity And Cardinality Rules",
    "Version And Provenance Semantics",
    "Relationship To SystemSnapshot",
    "Relationship To CapabilityProfile",
    "Relationship To Artifact Graph",
    "External Models And Services",
    "Native And Adaptive Research Boundary",
    "Isolation And Cross-Tenant Prohibitions",
    "Historical Identity And Invalidation",
    "Extension And Taxonomy Evolution",
    "Deferred Task 5-9 Artifacts",
    "Task 4 Qualification Contract",
    "System-Taxonomy Principle",
)

SYSTEM_FORMS = (
    "AGENT",
    "PIPELINE",
    "MODEL",
    "SERVICE",
    "COMPOSITE",
)

ENVIRONMENT_FAMILIES = (
    "E1_AGENT",
    "E2_STRUCTURED_ML",
    "E3_VISION",
)

INVESTIGATION_SURFACES = (
    "BEHAVIORAL",
    "AUTHORIZED_INTERNAL",
)

GRAPH_RELATIONSHIPS = (
    "HAS_SYSTEM_VERSION",
    "HAS_COMPONENT",
    "HAS_COMPONENT_VERSION",
    "INCLUDES_COMPONENT_VERSION",
    "DEPENDS_ON",
    "INTERACTS_VIA",
    "EVALUATED_VIA",
    "EXPOSES_SURFACE",
)

QUALIFICATION_SECTIONS = (
    "Scope",
    "Positive Qualification",
    "Structural Qualification",
    "Semantic Qualification",
    "Adversarial Qualification",
    "Authority And Regression Qualification",
    "Limitations",
    "Acceptance Decision",
)

EXPECTED_QUALIFICATION_METADATA = {
    "Task": "4 / 100",
    "Decision": "0004",
    "Decision Key": "architecture.system-taxonomy",
    "Result": "PASS",
    "Qualification state": "VERIFIED",
    "Specification": "docs/mvp/04-system-taxonomy.md",
    "Validator": "scripts/check_system_taxonomy.py",
    "Mutation suite": "tests/qualification/test_system_taxonomy.py",
    "Qualification conditions": "50 / 50",
    "Mutation result": "34 / 34",
    "Execution authority": "AUTH-HETREN-MVP-3.0",
    "Long-term authority": "AUTH-HETREN-MASTER-2.0",
    "Task 1 regression": "PASS",
    "Task 2 regression": "PASS",
    "Task 3 regression": "PASS",
    "Diff check": "PASS",
    "Final accepted-state qualification": "PASS",
}

CONDITION_REQUIREMENTS = {
    1: "the specification contains exactly 36 numbered sections in the governed order",
    2: "AUTH-HETREN-MVP-3.0 is the execution authority and AUTH-HETREN-MASTER-2.0 remains the long-term authority",
    3: "SystemSnapshot, CapabilityProfile, and the Artifact Graph retain their canonical responsibilities and no competing canonical SystemGraphRecord is introduced",
    4: "taxonomy membership remains explicitly separate from capability support",
    5: "every governed System belongs to exactly one tenant",
    6: "tenant-owned graph identities and relationships cannot cross tenant boundaries",
    7: "System remains a stable logical identity rather than an execution, snapshot, checkpoint, provider account, adapter, evaluator, or environment family",
    8: "SystemVersion is immutable and identifies a materially defined target state",
    9: "a material target-side change that can alter behavior, compatibility, reproducibility, evidence applicability, or governed meaning requires a new SystemVersion",
    10: "a change confined to Hetren-side adapter, evaluator, investigation-method, Studio, or planner state does not by itself create a new target SystemVersion",
    11: "the initial SystemForm vocabulary is exactly AGENT, PIPELINE, MODEL, SERVICE, and COMPOSITE, with exactly one primary form per governed SystemVersion",
    12: "the initial EnvironmentFamily vocabulary is exactly E1_AGENT, E2_STRUCTURED_ML, and E3_VISION, with exactly one primary family per governed SystemVersion",
    13: "SystemForm and EnvironmentFamily remain independent classification axes",
    14: "a COMPOSITE target does not automatically count as multiple required MVP environment-family demonstrations",
    15: "E1 classification requires materially relevant multi-step action, tool/API, state, sequencing, or recovery behavior rather than merely containing a language model",
    16: "E2 classification requires materially relevant structured-data machine-learning behavior rather than merely containing structured metadata",
    17: "E3 classification requires materially relevant visual-input or vision behavior rather than merely containing visual artifacts",
    18: "future environment families require governed extension and existing E1/E2/E3 meanings cannot be silently widened",
    19: "every target Component belongs to exactly one owning System",
    20: "ComponentVersion is immutable and historical evidence does not silently move to later component versions",
    21: "component representation is required only when separate identity materially improves topology, provenance, diagnosis, intervention, compatibility, or evidence truth",
    22: "ProviderIdentity remains distinct from tenant, system, environment-family, system-form, capability, and credential identity",
    23: "ProviderBinding is tenant-scoped and secret credential material is not embedded in taxonomy identity",
    24: "a material target-side provider-binding change is reflected in a new applicable target version and preserved provenance",
    25: "AdapterIdentity and AdapterBinding remain Hetren-side interaction identities rather than automatic target components",
    26: "an adapter defines interaction and does not define shared success semantics, qualified capability, or planner conclusions",
    27: "EvaluatorIdentity and EvaluatorBinding remain separately identifiable and historically attributable",
    28: "an evaluator may define environment-specific measures but does not redefine the Task 3 outcome vocabulary or shared success semantics",
    29: "the investigation-surface vocabulary is exactly BEHAVIORAL and AUTHORIZED_INTERNAL",
    30: "AUTHORIZED_INTERNAL representation or availability never substitutes for execution-time authorization",
    31: "Behavioral investigation does not embed a hidden environment-specific investigation strategy in place of shared Core behavior",
    32: "Internal observations do not receive stronger evidentiary status merely because internals were accessed",
    33: "the Versioned System Graph represents target identity, version, topology, provider, interaction, evaluation, surface, and artifact-reference context without becoming a support or success declaration",
    34: "the governed relationship vocabulary preserves HAS_SYSTEM_VERSION, HAS_COMPONENT, HAS_COMPONENT_VERSION, INCLUDES_COMPONENT_VERSION, DEPENDS_ON, INTERACTS_VIA, EVALUATED_VIA, and EXPOSES_SURFACE semantics",
    35: "ownership relationships are acyclic while genuine material DEPENDS_ON target dependency cycles may be represented",
    36: "required graph references cannot dangle and graph invariants must hold before consequential governed use",
    37: "environment family and system form remain explicit rather than being inferred from provider, adapter, evaluator, path, model name, or naming convention",
    38: "SystemSnapshot can capture or reference the material graph and interaction/evaluation state needed to interpret evidence",
    39: "multiple SystemSnapshot records may refer to one immutable SystemVersion without mutating that target version",
    40: "CapabilityProfile remains the authority for discovered and qualified capability state, including honest unsupported, unqualified, incompatible, blocked, or unknown states",
    41: "the Artifact Graph remains distinct from logical system/component identity and content equality does not authorize cross-tenant access",
    42: "external models and services have explicit roles and their outputs do not become evidence merely because a capable model produced them",
    43: "Native Intelligence and Adaptive Intelligence do not create duplicate target identity, Core, graph, evidence, permission, success, or verification systems",
    44: "existence of a Native or Adaptive research artifact does not itself make that artifact a qualified product capability",
    45: "product qualification, Native Intelligence research status, and Adaptive Intelligence scientific status remain separately inspectable",
    46: "historical invalid, superseded, retired, or corrected identities and evidence remain preserved rather than being deleted or silently rewritten",
    47: "material taxonomy evolution is versioned, governed, migration-aware, and requalified where required instead of reusing existing vocabulary with changed meaning",
    48: "a target that cannot be classified truthfully is not forced into E1, E2, or E3 merely to satisfy MVP evidence requirements",
    49: "Task 5 through Task 9 concrete support, hypothesis, split, baseline, and cost/effort values remain explicitly deferred",
    50: "the resulting taxonomy is sufficient to represent multiple systems, components, versions, and providers per tenant through a versioned graph with isolation checks while preserving the shared Hetren Core boundary",
}


def normalize(text: str) -> str:
    return " ".join(text.split())


def semantic_text(text: str) -> str:
    return normalize(text).replace("`", "").casefold()


def strip_code(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def parse_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    for match in re.finditer(
        r"^\*\*([^*]+):\*\*\s+(.+?)\s*$",
        text,
        re.MULTILINE,
    ):
        metadata[match.group(1).strip()] = strip_code(
            match.group(2).strip()
        )

    return metadata


def numbered_sections(text: str) -> list[tuple[int, str]]:
    return [
        (int(number), title.strip())
        for number, title in re.findall(
            r"^## ([0-9]+)\. (.+)$",
            text,
            re.MULTILINE,
        )
    ]


def section_body(
    text: str,
    number: int,
    title: str,
) -> str:
    marker = f"## {number}. {title}\n"

    if marker not in text:
        return ""

    body = text.split(marker, 1)[1]
    body = re.split(r"\n## [0-9]+\.", body, maxsplit=1)[0]

    return body.strip()


def markdown_section(
    text: str,
    heading: str,
) -> str:
    marker = f"## {heading}\n"

    if marker not in text:
        return ""

    body = text.split(marker, 1)[1]
    body = body.split("\n## ", 1)[0]

    return body.strip()


def parse_condition_bodies(text: str) -> dict[int, str]:
    matches = re.findall(
        r"^([0-9]+)\.\s+(.*?)(?=^[0-9]+\.\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )

    return {
        int(number): normalize(body)
        for number, body in matches
    }


def require_semantics(
    errors: list[str],
    text: str,
    label: str,
    fragments: tuple[str, ...],
) -> None:
    normalized = semantic_text(text)

    for fragment in fragments:
        if semantic_text(fragment) not in normalized:
            errors.append(
                f"{label} missing semantic requirement: {fragment}"
            )


DECISION_SECTIONS = (
    "Context And Trigger",
    "Decision",
    "Alternatives Considered",
    "Evidence And Rationale",
    "Assumptions",
    "Consequences",
    "Risks And Constraints",
    "Reversibility And Rollback",
    "Affected Contracts And Components",
    "Research Impact",
    "Qualification Requirement",
    "Implementation Evidence",
    "Verification Evidence",
    "Supersession",
)


def validate_semver(
    value: str,
    label: str,
    errors: list[str],
) -> tuple[int, int, int] | None:
    match = re.fullmatch(
        r"([0-9]+)\.([0-9]+)\.([0-9]+)",
        value,
    )

    if match is None:
        errors.append(f"{label} must be semantic version X.Y.Z")
        return None

    return tuple(int(part) for part in match.groups())


def declared_dash_code_values(text: str) -> tuple[str, ...]:
    return tuple(
        re.findall(
            r"^- `([A-Z][A-Z0-9_]*)`\s+—",
            text,
            re.MULTILINE,
        )
    )


def declared_surface_values(text: str) -> tuple[str, ...]:
    return tuple(
        re.findall(
            r"^- `([A-Z][A-Z0-9_]*)`[;.]?\s*$",
            text,
            re.MULTILINE,
        )
    )


def parse_register_row(
    text: str,
    decision_id: str,
) -> tuple[str, ...] | None:
    prefix = f"| `{decision_id}` |"

    matching = [
        line
        for line in text.splitlines()
        if line.startswith(prefix)
    ]

    if len(matching) != 1:
        return None

    cells = [
        cell.strip()
        for cell in matching[0].strip().strip("|").split("|")
    ]

    if len(cells) != 7:
        return None

    return tuple(strip_code(cell) for cell in cells)


def validate_spec_structure(
    spec_text: str,
    *,
    require_qualified: bool,
) -> list[str]:
    errors: list[str] = []

    if not spec_text.startswith("# Hetren MVP System Taxonomy\n"):
        errors.append("system-taxonomy heading mismatch")

    metadata = parse_metadata(spec_text)

    version = metadata.get("Version", "")
    parsed_version = validate_semver(
        version,
        "system-taxonomy metadata Version",
        errors,
    )

    status = metadata.get("Status", "")

    if status not in {"Draft", "Requalifying", "Qualified"}:
        errors.append(
            "system-taxonomy metadata Status must be "
            "Draft, Requalifying, or Qualified"
        )

    if require_qualified:
        if status != "Qualified":
            errors.append(
                "final system-taxonomy validation requires Status Qualified"
            )

        if parsed_version is None or parsed_version[0] < 1:
            errors.append(
                "Qualified system-taxonomy Version must have "
                "major version at least 1"
            )

    for key, expected in EXPECTED_SPEC_METADATA.items():
        actual = metadata.get(key)

        if actual != expected:
            errors.append(
                f"system-taxonomy metadata {key} must be "
                f"{expected!r}; got {actual!r}"
            )

    actual_sections = numbered_sections(spec_text)
    expected_sections = [
        (number, title)
        for number, title in enumerate(SECTION_TITLES, start=1)
    ]

    if actual_sections != expected_sections:
        errors.append(
            "system-taxonomy must contain exactly ordered sections "
            "1 through 36"
        )

    for number, title in expected_sections:
        if not section_body(spec_text, number, title):
            errors.append(
                f"system-taxonomy section {number} {title!r} is empty"
            )

    qualification_body = section_body(
        spec_text,
        35,
        "Task 4 Qualification Contract",
    )
    conditions = parse_condition_bodies(qualification_body)

    if tuple(conditions) != tuple(range(1, 51)):
        errors.append(
            "Task 4 qualification contract must contain exactly "
            "conditions 1 through 50"
        )

    system_forms = declared_dash_code_values(
        section_body(spec_text, 8, "System Form")
    )

    if system_forms != SYSTEM_FORMS:
        errors.append(
            "SystemForm vocabulary must be exactly "
            + ", ".join(SYSTEM_FORMS)
        )

    environment_families = declared_dash_code_values(
        section_body(spec_text, 9, "Environment Family")
    )

    if environment_families != ENVIRONMENT_FAMILIES:
        errors.append(
            "EnvironmentFamily vocabulary must be exactly "
            + ", ".join(ENVIRONMENT_FAMILIES)
        )

    investigation_surfaces = declared_surface_values(
        section_body(spec_text, 19, "Investigation Surface")
    )

    if investigation_surfaces != INVESTIGATION_SURFACES:
        errors.append(
            "InvestigationSurface vocabulary must be exactly "
            + ", ".join(INVESTIGATION_SURFACES)
        )

    graph_relationships = declared_dash_code_values(
        section_body(
            spec_text,
            23,
            "Graph Planes And Relationship Vocabulary",
        )
    )

    if graph_relationships != GRAPH_RELATIONSHIPS:
        errors.append(
            "Versioned System Graph relationship vocabulary must be exactly "
            + ", ".join(GRAPH_RELATIONSHIPS)
        )

    return errors


def validate_decision_structure(
    decision_text: str,
    *,
    require_qualified: bool,
) -> list[str]:
    errors: list[str] = []

    expected_heading = (
        "# Decision 0004: Define governed MVP system taxonomy\n"
    )

    if not decision_text.startswith(expected_heading):
        errors.append("Decision 0004 heading mismatch")

    metadata = parse_metadata(decision_text)

    for key, expected in EXPECTED_DECISION_METADATA.items():
        actual = metadata.get(key)

        if actual != expected:
            errors.append(
                f"Decision 0004 metadata {key} must be "
                f"{expected!r}; got {actual!r}"
            )

    status = metadata.get("Status", "")

    if status not in {"PROPOSED", "ACCEPTED"}:
        errors.append(
            "Decision 0004 status must be PROPOSED or ACCEPTED"
        )

    if require_qualified and status != "ACCEPTED":
        errors.append(
            "final system-taxonomy validation requires "
            "Decision 0004 ACCEPTED"
        )

    date_value = metadata.get("Date", "")

    try:
        date.fromisoformat(date_value)
    except ValueError:
        errors.append("Decision 0004 Date must be valid ISO date")

    actual_sections = tuple(
        re.findall(
            r"^## ([^\n]+)$",
            decision_text,
            re.MULTILINE,
        )
    )

    if actual_sections != DECISION_SECTIONS:
        errors.append(
            "Decision 0004 must contain exactly the governed "
            "decision sections in order"
        )

    for heading in DECISION_SECTIONS:
        if not markdown_section(decision_text, heading):
            errors.append(
                f"Decision 0004 section {heading!r} is empty"
            )

    return errors


def validate_register_state(
    register_text: str,
    decision_text: str,
    *,
    require_qualified: bool,
) -> list[str]:
    errors: list[str] = []

    metadata = parse_metadata(register_text)

    validate_semver(
        metadata.get("Version", ""),
        "decision-register metadata Version",
        errors,
    )

    if metadata.get("Status") != "Active":
        errors.append("decision-register Status must be Active")

    if (
        metadata.get("Governing execution authority")
        != "AUTH-HETREN-MVP-3.0"
    ):
        errors.append(
            "decision-register governing execution authority mismatch"
        )

    if (
        metadata.get("Long-term authority")
        != "AUTH-HETREN-MASTER-2.0"
    ):
        errors.append(
            "decision-register long-term authority mismatch"
        )

    row = parse_register_row(register_text, "0004")

    if row is None:
        errors.append(
            "Decision 0004 must appear exactly once as a valid register row"
        )
        return errors

    (
        decision_id,
        key,
        title,
        status,
        decision_class,
        authority,
        record,
    ) = row

    expected = (
        "0004",
        "architecture.system-taxonomy",
        "Define governed MVP system taxonomy",
        parse_metadata(decision_text).get("Status", ""),
        "ARCHITECTURE",
        "AUTH-HETREN-MVP-3.0",
        "0004-system-taxonomy.md",
    )

    actual = (
        decision_id,
        key,
        title,
        status,
        decision_class,
        authority,
        record,
    )

    if actual != expected:
        errors.append(
            "Decision 0004 register row must match Decision 0004 record"
        )

    if require_qualified and status != "ACCEPTED":
        errors.append(
            "final system-taxonomy validation requires "
            "Decision 0004 register status ACCEPTED"
        )

    return errors


def validate_qualification_record(
    qualification_path: Path,
    spec_metadata: dict[str, str],
) -> list[str]:
    errors: list[str] = []

    if not qualification_path.is_file():
        return ["missing Decision 0004 qualification evidence"]

    text = qualification_path.read_text()

    if not text.startswith("# Decision 0004 Qualification Record\n"):
        errors.append("Decision 0004 qualification heading mismatch")

    metadata = parse_metadata(text)

    for key, expected in EXPECTED_QUALIFICATION_METADATA.items():
        actual = metadata.get(key)

        if actual != expected:
            errors.append(
                f"Decision 0004 qualification metadata {key} must be "
                f"{expected!r}; got {actual!r}"
            )

    specification_version = metadata.get(
        "Specification version",
        "",
    )

    if specification_version != spec_metadata.get("Version", ""):
        errors.append(
            "Decision 0004 qualification Specification version must "
            "match system-taxonomy Version"
        )

    parsed_version = re.fullmatch(
        r"([0-9]+)\.([0-9]+)\.([0-9]+)",
        specification_version,
    )

    if (
        parsed_version is None
        or int(parsed_version.group(1)) < 1
    ):
        errors.append(
            "Qualified system-taxonomy Specification version must "
            "have major version at least 1"
        )

    qualification_date = metadata.get("Date", "")

    try:
        date.fromisoformat(qualification_date)
    except ValueError:
        errors.append(
            "Decision 0004 qualification Date must be valid ISO date"
        )

    mutation_result = metadata.get("Mutation result", "")
    mutation_match = re.fullmatch(
        r"([0-9]+) / ([0-9]+)",
        mutation_result,
    )

    if mutation_match is None:
        errors.append(
            "Decision 0004 qualification Mutation result "
            "must use N / N format"
        )
    else:
        killed = int(mutation_match.group(1))
        total = int(mutation_match.group(2))

        if killed != total or total < 1:
            errors.append(
                "Decision 0004 qualification requires all recorded "
                "mutations to be rejected"
            )

    for heading in QUALIFICATION_SECTIONS:
        if not markdown_section(text, heading):
            errors.append(
                f"Decision 0004 qualification missing section {heading}"
            )

    return errors


def validate_final_decision_evidence(
    decision_text: str,
) -> list[str]:
    errors: list[str] = []

    implementation = markdown_section(
        decision_text,
        "Implementation Evidence",
    )
    verification = markdown_section(
        decision_text,
        "Verification Evidence",
    )

    if not implementation:
        errors.append(
            "Decision 0004 missing Implementation Evidence"
        )
    elif "pending" in semantic_text(implementation):
        errors.append(
            "Decision 0004 Implementation Evidence remains pending"
        )

    if not verification:
        errors.append(
            "Decision 0004 missing Verification Evidence"
        )
    elif "pending" in semantic_text(verification):
        errors.append(
            "Decision 0004 Verification Evidence remains pending"
        )

    for required in (
        "docs/mvp/04-system-taxonomy.md",
        "scripts/check_system_taxonomy.py",
        "tests/qualification/test_system_taxonomy.py",
    ):
        if required not in implementation:
            errors.append(
                f"Decision 0004 Implementation Evidence missing {required}"
            )

    verification_required = (
        "docs/decisions/qualification/0004-system-taxonomy.md",
        "structural",
        "semantic",
        "adversarial",
        "mutation",
        "authority",
        "regression",
        "accepted-state",
    )

    normalized_verification = semantic_text(verification)

    for required in verification_required:
        if semantic_text(required) not in normalized_verification:
            errors.append(
                f"Decision 0004 Verification Evidence missing {required}"
            )

    return errors


def validate_structure(
    root: Path,
    *,
    require_qualified: bool = False,
) -> list[str]:
    errors: list[str] = []

    spec_path = root / SPEC_RELATIVE
    decision_path = root / DECISION_RELATIVE
    register_path = root / REGISTER_RELATIVE
    qualification_path = root / QUALIFICATION_RELATIVE

    required = (
        (spec_path, "Task 4 system-taxonomy specification"),
        (decision_path, "Decision 0004 record"),
        (register_path, "decision register"),
    )

    for path, label in required:
        if not path.is_file():
            errors.append(f"missing {label}: {path}")

    if errors:
        return errors

    spec_text = spec_path.read_text()
    decision_text = decision_path.read_text()
    register_text = register_path.read_text()

    errors.extend(
        validate_spec_structure(
            spec_text,
            require_qualified=require_qualified,
        )
    )

    errors.extend(
        validate_decision_structure(
            decision_text,
            require_qualified=require_qualified,
        )
    )

    errors.extend(
        validate_register_state(
            register_text,
            decision_text,
            require_qualified=require_qualified,
        )
    )

    spec_metadata = parse_metadata(spec_text)
    decision_metadata = parse_metadata(decision_text)

    if (
        decision_metadata.get("Status") == "ACCEPTED"
        and spec_metadata.get("Status") != "Qualified"
    ):
        errors.append(
            "Decision 0004 cannot be ACCEPTED while "
            "system-taxonomy Status is not Qualified"
        )

    if (
        require_qualified
        or decision_metadata.get("Status") == "ACCEPTED"
    ):
        errors.extend(
            validate_qualification_record(
                qualification_path,
                spec_metadata,
            )
        )

        errors.extend(
            validate_final_decision_evidence(decision_text)
        )

    return errors


def validate_condition_semantics(
    qualification_body: str,
) -> list[str]:
    errors: list[str] = []
    bodies = parse_condition_bodies(qualification_body)

    for number, requirement in CONDITION_REQUIREMENTS.items():
        body = bodies.get(number, "")

        if semantic_text(requirement) not in semantic_text(body):
            errors.append(
                f"Task 4 qualification condition {number} missing "
                f"required semantics: {requirement}"
            )

    return errors


SECTION_REQUIREMENTS = {
    3: (
        "Taxonomy membership and Hetren support are separate facts.",
        "Task 5 answers whether Hetren has a qualified capability",
        "Qualified support state belongs in `CapabilityProfile`",
    ),
    4: (
        "Adapters and evaluators are therefore not automatically target components.",
        "Changing a Hetren adapter or evaluator does not by itself create a new target `SystemVersion`.",
        "must not become a second implementation of shared Core semantics.",
    ),
    5: (
        "Every governed `System` belongs to exactly one tenant.",
        "No graph relationship may directly connect tenant-owned system or component nodes across tenant boundaries.",
        "A violation of these isolation rules makes the affected graph state invalid for governed use.",
    ),
    6: (
        "A `System` is the stable logical identity of a target",
        "A materially different logical target must receive a different system identity",
        "ordinary evolution of the same logical target must be represented through `SystemVersion`",
    ),
    7: (
        "A `SystemVersion` is an immutable governed identity",
        "A new `SystemVersion` is required when a target change could materially alter",
        "Existing system versions are immutable.",
        "does not by itself create a new target `SystemVersion`.",
    ),
    8: (
        "Each `SystemVersion` has exactly one primary `SystemForm`.",
        "`SystemForm` must not encode provider identity",
        "Using `COMPOSITE` does not permit heterogeneous components to be hidden.",
    ),
    9: (
        "Each governed `SystemVersion` has exactly one primary `EnvironmentFamily`.",
        "Environment family and `SystemForm` are independent axes.",
        "Support remains governed by Task 5 and `CapabilityProfile`.",
        "Provider identity must not determine environment family.",
        "Investigation surface must not determine environment family.",
        "Model architecture must not determine environment family.",
    ),
    10: (
        "A target does not become E1 merely because it contains a language model.",
        "does not imply that any particular agent framework, model provider, tool protocol, memory implementation, or orchestration library is supported.",
    ),
    11: (
        "A target does not become E2 merely because structured metadata appears somewhere in its graph.",
        "E2 classification requires that structured-data machine-learning behavior be material",
        "E2 does not require one particular algorithm family",
    ),
    12: (
        "A system does not become E3 merely because it contains screenshots",
        "E3 classification does not imply support for every vision task",
        "qualification coverage, not the definition of E3 itself.",
    ),
    13: (
        "A new primary environment family requires governed taxonomy extension.",
        "A new family must not be created merely because a new:",
        "Existing family meanings must not be widened or reinterpreted silently",
        "does not permit one `SystemVersion` to count as multiple required MVP family demonstrations.",
    ),
    14: (
        "A component belongs to exactly one owning `System`.",
        "They are not Task 5 capability declarations.",
        "every implementation detail need not become a component.",
        "are not target components merely because they interact with the target.",
    ),
    15: (
        "A `ComponentVersion` is an immutable governed identity",
        "A `SystemVersion` must be able to reference the material",
        "Historical evidence must not silently float to a later component version.",
        "the taxonomy must not duplicate artifact provenance",
    ),
    16: (
        "`ProviderIdentity` identifies an external organization",
        "Provider identity is distinct from:",
        "A `ProviderBinding` is the tenant-scoped configured relationship",
        "Credentials, tokens, secrets, and private keys must never be embedded directly in taxonomy identity.",
        "Provider identity must not determine environment family, success semantics, or Hetren intelligence behavior.",
    ),
    17: (
        "An `AdapterIdentity` identifies a Hetren integration implementation",
        "An `AdapterBinding` identifies the configured association",
        "Changing an adapter implementation or adapter binding does not by itself create a new target `SystemVersion`.",
        "It must not define whether an evaluation passes, whether a capability is qualified, or what the shared planner should conclude.",
    ),
    18: (
        "An `EvaluatorIdentity` identifies a qualified or candidate evaluator",
        "An `EvaluatorBinding` identifies the configured association",
        "It does not redefine the Task 3 meanings of `PASS`, `FAIL`, `INCONCLUSIVE`, `BLOCKED`, or `INVALID`.",
        "Historical `EvaluationRecord` and verification evidence must preserve the evaluator identity",
    ),
    19: (
        "Investigation surface is independent of:",
        "Representability of a surface does not establish that Hetren has a qualified capability",
        "declaration of `AUTHORIZED_INTERNAL` does not itself grant authorization.",
    ),
    20: (
        "`BEHAVIORAL` represents investigation through externally observable behavior",
        "Shared Core remains responsible for investigation-state and method semantics",
        "must not contain a hidden environment-specific investigation strategy.",
    ),
    21: (
        "`AUTHORIZED_INTERNAL` represents investigation that uses explicitly permitted access",
        "Every Internal action must be authorized",
        "Internal access must never be inferred merely because:",
        "Internal observations do not receive stronger evidentiary status merely because they expose internals.",
    ),
    22: (
        "Task 4 does not introduce a competing canonical runtime record named `SystemGraphRecord`.",
        "`SystemSnapshot` remains the canonical captured-state record.",
        "The graph is not itself evidence that a capability is supported, a result is valid, or an investigation succeeded.",
    ),
    23: (
        "Provider binding is explicit rather than inferred",
        "These relationships describe interaction and evaluation context.",
        "They do not become target-system components merely because they appear in the graph.",
        "rather than a second artifact-lineage implementation inside the system taxonomy.",
    ),
    24: (
        "no tenant-owned graph relationship may cross tenant boundaries;",
        "no required graph reference may dangle;",
        "`AUTHORIZED_INTERNAL` availability does not substitute for execution-time authorization.",
        "invalid for consequential evaluation until the representation is corrected",
    ),
    25: (
        "A material change to target-owned topology, component versions, target configuration, model state, tool configuration, or a provider binding that is part of target behavior requires a new `SystemVersion`.",
        "Changing only Hetren's:",
        "does not by itself create a new target `SystemVersion`.",
        "Later changes must create later identities or records rather than mutate the meaning of preserved historical evidence.",
    ),
    26: (
        "`SystemSnapshot` remains the canonical captured-state record",
        "Multiple `SystemSnapshot` records may legitimately refer to the same immutable `SystemVersion`.",
        "A snapshot must not silently rewrite its referenced immutable identities",
    ),
    27: (
        "`CapabilityProfile` remains the canonical record for discovered and qualified capability state.",
        "The taxonomy describes what a target is.",
        "`CapabilityProfile` describes what Hetren has established it can or cannot do",
        "Task 5 governs the first concrete supported capability matrix.",
        "Neither the system graph nor successful target classification may synthesize a qualified `CapabilityProfile` entry without the required qualification evidence.",
    ),
    28: (
        "The Artifact Graph and Versioned System Graph have different responsibilities.",
        "A component identity must not replace artifact identity.",
        "An artifact identity must not replace the logical `System`",
        "Content-address equality or reuse of an artifact does not itself authorize cross-tenant discovery or access.",
    ),
    29: (
        "Those roles are not interchangeable.",
        "External-model output is not evidence merely because it was produced by a capable model or provider.",
        "roles must be recorded separately enough to prevent target evidence from being confused with Hetren-side assistance.",
        "No provider may define Hetren Core semantics",
    ),
    30: (
        "Neither research program creates a parallel:",
        "does not become a qualified product capability merely because it exists in `research/`",
        "`NATIVE` and `ADAPTIVE` are research-program classifications, not `EnvironmentFamily` values.",
        "remain separately inspectable.",
    ),
    31: (
        "Tenant isolation is a validity property of the taxonomy, not merely a user interface filter.",
        "do not authorize cross-tenant discovery or access.",
        "Task 4 does not create such a mechanism.",
        "must not weaken logical tenant isolation.",
        "A cross-tenant graph violation makes the affected representation invalid",
    ),
    32: (
        "the original record and affected evidence remain preserved;",
        "Retirement is not deletion.",
        "Supersession is not retroactive mutation.",
        "Invalidation is not permission to erase a negative or inconvenient result.",
        "must not silently float to a replacement identity.",
    ),
    33: (
        "requires an explicit governed taxonomy change.",
        "Existing enum or relationship names must not be reused with materially changed semantics.",
        "requires a versioned specification revision and applicable requalification",
        "A target that cannot be classified truthfully under the current taxonomy",
        "It must not be forced into `E1_AGENT`, `E2_STRUCTURED_ML`, or `E3_VISION`",
    ),
    34: (
        "Task 5 owns:",
        "Task 6 owns:",
        "Task 7 owns:",
        "Task 8 owns:",
        "Task 9 owns:",
        "Task 4 must be revised through governed change rather than being bypassed.",
    ),
    36: (
        "Classification must not manufacture support.",
        "Representability must not manufacture authorization.",
        "Access must not manufacture evidence.",
        "Shared artifacts must not manufacture cross-tenant permission.",
        "Research existence must not manufacture product capability.",
        "Later versions must not rewrite historical identity.",
    ),
}


FORBIDDEN_SECTION_SEMANTICS = {
    3: (
        "taxonomy membership and hetren support are the same fact",
    ),
    4: (
        "adapters and evaluators are automatically target components",
    ),
    5: (
        "graph relationships may cross tenant boundaries",
    ),
    8: (
        "systemform may encode provider identity",
    ),
    9: (
        "provider identity determines environment family",
        "investigation surface determines environment family",
        "model architecture determines environment family",
    ),
    13: (
        "new family may be created merely because a new provider",
    ),
    17: (
        "an adapter defines whether an evaluation passes",
        "an adapter defines whether a capability is qualified",
    ),
    18: (
        "an evaluator redefines the task 3 meanings",
    ),
    19: (
        "authorized_internal grants authorization",
    ),
    21: (
        "internal access may be inferred",
    ),
    22: (
        "systemgraphrecord remains the canonical captured-state record",
        "the graph is itself evidence that a capability is supported",
    ),
    24: (
        "a tenant-owned graph relationship may cross tenant boundaries",
        "authorized_internal availability substitutes for execution-time authorization",
    ),
    27: (
        "either the system graph or successful target classification may synthesize a qualified capabilityprofile entry",
    ),
    29: (
        "external-model output is evidence merely because",
        "a provider may define hetren core semantics",
    ),
    30: (
        "native intelligence and adaptive intelligence create a parallel",
    ),
    31: (
        "caching, deduplication, content addressing, shared infrastructure, or provider reuse may weaken logical tenant isolation",
    ),
    32: (
        "retirement is deletion",
        "supersession is retroactive mutation",
        "invalidation is permission to erase",
    ),
    33: (
        "target may be forced into e1_agent",
        "target may be forced into e2_structured_ml",
        "target may be forced into e3_vision",
    ),
    36: (
        "classification may manufacture support",
        "representability may manufacture authorization",
        "access may manufacture evidence",
        "shared artifacts may manufacture cross-tenant permission",
        "research existence may manufacture product capability",
        "later versions may rewrite historical identity",
    ),
}


def validate_semantics(root: Path) -> list[str]:
    errors: list[str] = []

    spec_path = root / SPEC_RELATIVE
    decision_path = root / DECISION_RELATIVE

    if not spec_path.is_file() or not decision_path.is_file():
        return errors

    spec_text = spec_path.read_text()
    decision_text = decision_path.read_text()

    qualification_body = section_body(
        spec_text,
        35,
        "Task 4 Qualification Contract",
    )

    errors.extend(
        validate_condition_semantics(qualification_body)
    )

    for number, fragments in SECTION_REQUIREMENTS.items():
        title = SECTION_TITLES[number - 1]
        body = section_body(spec_text, number, title)

        require_semantics(
            errors,
            body,
            f"section {number} {title!r}",
            fragments,
        )

    for number, forbidden_fragments in (
        FORBIDDEN_SECTION_SEMANTICS.items()
    ):
        title = SECTION_TITLES[number - 1]
        body = semantic_text(
            section_body(spec_text, number, title)
        )

        for fragment in forbidden_fragments:
            if semantic_text(fragment) in body:
                errors.append(
                    f"section {number} {title!r} contains forbidden "
                    f"semantic reversal: {fragment}"
                )

    require_semantics(
        errors,
        decision_text,
        "Decision 0004",
        (
            "stable tenant-scoped `System` identities",
            "immutable `SystemVersion` identities",
            "`SystemForm` as an operational-shape classification",
            "`EnvironmentFamily` as a separate primary qualification classification",
            "provider identities and tenant-scoped provider bindings",
            "Hetren-side adapter identities and bindings",
            "evaluator identities and bindings",
            "Behavioral and authorized Internal investigation surfaces",
            "Versioned System Graph semantics and relationship vocabulary",
            "tenant-isolation and graph-validity requirements",
            "integration with `SystemSnapshot`, `CapabilityProfile`, and the Artifact Graph",
            "This decision does not declare that every taxonomy member is supported.",
            "Task 5 remains responsible for the initial supported capability matrix.",
            "This decision remains non-authoritative while its status is `PROPOSED`.",
            "Representability and qualified support are different facts.",
            "`SystemSnapshot` already owns captured target-state responsibility.",
            "all 50 Task 4 qualification conditions",
            "Qualification criteria must not be weakened merely to obtain acceptance.",
        ),
    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Hetren Task 4 system taxonomy."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    parser.add_argument(
        "--require-qualified",
        action="store_true",
        help="require final Qualified and ACCEPTED state",
    )
    args = parser.parse_args()

    root = args.root.resolve()

    errors = validate_structure(
        root,
        require_qualified=args.require_qualified,
    )

    if not errors:
        errors.extend(validate_semantics(root))

    if errors:
        print("SYSTEM TAXONOMY VALIDATION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    spec_text = (root / SPEC_RELATIVE).read_text()
    decision_text = (root / DECISION_RELATIVE).read_text()

    spec_metadata = parse_metadata(spec_text)
    decision_metadata = parse_metadata(decision_text)

    print("SYSTEM TAXONOMY VALIDATION: PASS")
    print(f"- version: {spec_metadata.get('Version')}")
    print(f"- status: {spec_metadata.get('Status')}")
    print(f"- decision: {decision_metadata.get('Status')}")
    print(f"- numbered sections: {len(SECTION_TITLES)}")
    print(
        "- Task 4 qualification conditions: "
        f"{len(CONDITION_REQUIREMENTS)}"
    )
    print("- system forms: " + ", ".join(SYSTEM_FORMS))
    print(
        "- environment families: "
        + ", ".join(ENVIRONMENT_FAMILIES)
    )
    print(
        "- investigation surfaces: "
        + ", ".join(INVESTIGATION_SURFACES)
    )
    print(
        "- graph relationships: "
        + ", ".join(GRAPH_RELATIONSHIPS)
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
