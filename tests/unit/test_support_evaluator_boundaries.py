"""Import boundaries around the evaluator-only support data.

Rules:

1. Only ``packages/verification/support_verification.py`` (and the evaluator
   package itself) may import ``packages.support_evaluator``.
2. Restricted code must not reach ``packages.support_evaluator`` or
   ``packages.verification.support_verification`` directly or transitively,
   and must not name either module in a string (which would allow
   ``importlib`` access).
3. Importing any restricted module in a fresh interpreter must leave both
   modules out of ``sys.modules``.
4. Restricted source must not contain answer-revealing catalog literals
   (target and regression tickets, swapped customer refs, expected accounts
   and queues). ``environments/support/fixtures.py`` defines the world and
   is exempt.

The checkers are functions of a root directory so the planted-violation
tests can run them against a temporary tree.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from packages.support_evaluator import EXAMPLES, FAULTS


REPO_ROOT = Path(__file__).resolve().parents[2]

SCANNED_ROOTS = ("packages", "environments", "scripts")

EVALUATOR = "packages.support_evaluator"
VERIFIER = "packages.verification.support_verification"

EVALUATOR_IMPORTERS = frozenset({VERIFIER})

RESTRICTED_PREFIXES = (
    "packages.support_recovery",
    "packages.integrations",
    "packages.support_agent",
    "packages.action_gateway",
    "environments.support",
)

FORBIDDEN_FOR_RESTRICTED = (EVALUATOR, VERIFIER)

LITERAL_EXEMPT_MODULES = frozenset({"environments.support.fixtures"})


def _within(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _module_name(path: Path, root: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)

    if parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts)


def _collect_modules(root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}

    for top in SCANNED_ROOTS:
        base = root / top

        if not base.exists():
            continue

        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue

            modules[_module_name(path, root)] = path

    return modules


def _imported_names(module: str, path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    is_package = path.name == "__init__.py"
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package = module.split(".")
                if not is_package:
                    package = package[:-1]
                package = package[: len(package) - (node.level - 1)]
                base = ".".join(package + ([node.module] if node.module else []))
            else:
                base = node.module or ""

            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)

    return names


def _with_parents(name: str) -> set[str]:
    parts = name.split(".")
    return {".".join(parts[: index + 1]) for index in range(len(parts))}


def _import_graph(root: Path) -> tuple[dict[str, Path], dict[str, set[str]]]:
    modules = _collect_modules(root)
    graph: dict[str, set[str]] = {}

    for module, path in modules.items():
        resolved: set[str] = set()

        for name in _imported_names(module, path):
            resolved.update(
                candidate
                for candidate in _with_parents(name)
                if candidate in modules or candidate in (EVALUATOR, VERIFIER)
            )

        graph[module] = resolved

    return modules, graph


def _reachable(start: str, graph: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(graph.get(start, ()))

    while stack:
        current = stack.pop()

        if current in seen:
            continue

        seen.add(current)
        stack.extend(graph.get(current, ()))

    return seen


def find_violations(root: Path) -> list[str]:
    modules, graph = _import_graph(root)
    violations: list[str] = []

    for module in sorted(modules):
        if _within(module, EVALUATOR) or module in EVALUATOR_IMPORTERS:
            continue

        if any(_within(name, EVALUATOR) for name in graph[module]):
            violations.append(f"{module}: imports {EVALUATOR} directly")

    for module in sorted(modules):
        if not any(_within(module, prefix) for prefix in RESTRICTED_PREFIXES):
            continue

        reached = _reachable(module, graph)

        for forbidden in FORBIDDEN_FOR_RESTRICTED:
            if any(_within(name, forbidden) for name in reached):
                violations.append(f"{module}: reaches {forbidden}")

        source = modules[module].read_text(encoding="utf-8")

        for forbidden in FORBIDDEN_FOR_RESTRICTED:
            if forbidden.rsplit(".", 1)[-1] in source:
                violations.append(f"{module}: names {forbidden} in source")

    return violations


def restricted_modules(root: Path) -> list[str]:
    return [
        module
        for module in sorted(_collect_modules(root))
        if any(_within(module, prefix) for prefix in RESTRICTED_PREFIXES)
    ]


_RUNTIME_PROBE = """
import importlib, json, sys
sys.path.insert(0, sys.argv[1])
importlib.import_module(sys.argv[2])
print(json.dumps(sorted(name for name in sys.modules if name in sys.argv[3:])))
"""


def runtime_violations(root: Path, modules: list[str]) -> list[str]:
    """Import each module in a fresh interpreter and inspect sys.modules."""
    violations: list[str] = []
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    for module in modules:
        result = subprocess.run(
            [sys.executable, "-I", "-c", _RUNTIME_PROBE, str(root), module,
             *FORBIDDEN_FOR_RESTRICTED],
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            violations.append(f"{module}: import failed: {result.stderr.strip()}")
            continue

        for loaded in json.loads(result.stdout):
            violations.append(f"{module}: loads {loaded} at runtime")

    return violations


def answer_literals() -> frozenset[str]:
    literals: set[str] = set()

    for spec in EXAMPLES.values():
        literals.update(
            (spec.target_ticket_id, spec.expected_account_id, spec.expected_queue_id)
        )
        literals.update(spec.regression_expectations)
        literals.update(spec.regression_expectations.values())

    for definition in FAULTS.values():
        literals.update(definition.parameters.values())

    return frozenset(literals)


def literal_violations(root: Path) -> list[str]:
    modules = _collect_modules(root)
    patterns = {
        literal: re.compile(rf"(?<![A-Za-z0-9-]){re.escape(literal)}(?![A-Za-z0-9-])")
        for literal in sorted(answer_literals())
    }
    violations: list[str] = []

    for module in restricted_modules(root):
        if module in LITERAL_EXEMPT_MODULES:
            continue

        source = modules[module].read_text(encoding="utf-8")

        for literal, pattern in patterns.items():
            if pattern.search(source):
                violations.append(f"{module}: contains answer literal {literal}")

    return violations


def _plant(root: Path, relative: str, source: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


@pytest.fixture
def clean_tree(tmp_path: Path) -> Path:
    """A minimal tree that follows every rule."""
    _plant(tmp_path, "packages/support_evaluator/__init__.py", "from .catalog import X\n")
    _plant(tmp_path, "packages/support_evaluator/catalog.py", "X = 1\n")
    _plant(tmp_path, "packages/verification/__init__.py", "from .deterministic import Y\n")
    _plant(tmp_path, "packages/verification/deterministic.py", "Y = 1\n")
    _plant(
        tmp_path,
        "packages/verification/support_verification.py",
        "from packages.support_evaluator.catalog import X\n",
    )
    _plant(
        tmp_path,
        "packages/support_examples/harness.py",
        "from packages.verification.support_verification import register_run\n",
    )
    _plant(
        tmp_path,
        "packages/support_recovery/diagnosis.py",
        "from packages.verification import Y\nfrom packages.action_gateway import gate\n",
    )
    _plant(tmp_path, "packages/action_gateway/__init__.py", "gate = 1\n")
    _plant(tmp_path, "packages/support_agent/agent.py", "import json\n")
    _plant(tmp_path, "packages/integrations/openai_agents/hooks.py", "")
    _plant(tmp_path, "environments/support/tools.py", "from environments.support import fixtures\n")
    _plant(tmp_path, "environments/support/fixtures.py", "")
    return tmp_path


# The real repository


def test_repository_respects_evaluator_import_boundaries():
    assert find_violations(REPO_ROOT) == []


def test_evaluator_package_exists_and_is_scanned():
    modules = _collect_modules(REPO_ROOT)

    assert EVALUATOR in modules
    assert f"{EVALUATOR}.catalog" in modules
    assert "environments.support.tools" in modules
    assert "packages.action_gateway.gateway" in modules


# Planted violations


def test_clean_tree_has_no_violations(clean_tree):
    assert find_violations(clean_tree) == []


@pytest.mark.parametrize(
    ("relative", "source", "expected"),
    [
        (
            "packages/support_agent/agent.py",
            "from packages.support_evaluator.catalog import X\n",
            "packages.support_agent.agent: imports packages.support_evaluator directly",
        ),
        (
            "environments/support/tools.py",
            "import packages.support_evaluator\n",
            "environments.support.tools: imports packages.support_evaluator directly",
        ),
        (
            "packages/support_examples/harness.py",
            "from packages import support_evaluator\n",
            "packages.support_examples.harness: imports packages.support_evaluator directly",
        ),
        (
            "packages/integrations/openai_agents/hooks.py",
            "from packages.verification.support_verification import register_run\n",
            "packages.integrations.openai_agents.hooks: reaches "
            "packages.verification.support_verification",
        ),
        (
            "packages/action_gateway/__init__.py",
            "import importlib\nimportlib.import_module('packages.support_evaluator')\n",
            "packages.action_gateway: names packages.support_evaluator in source",
        ),
        (
            "packages/verification/deterministic.py",
            "from ..support_evaluator.catalog import X\nY = 1\n",
            "packages.verification.deterministic: imports packages.support_evaluator directly",
        ),
    ],
)
def test_planted_import_violations_are_caught(clean_tree, relative, source, expected):
    _plant(clean_tree, relative, source)

    assert expected in find_violations(clean_tree)


def test_planted_transitive_violation_is_caught(clean_tree):
    # verification/__init__ re-exporting the verifier would let any
    # `import packages.verification` reach the evaluator.
    _plant(
        clean_tree,
        "packages/verification/__init__.py",
        "from .deterministic import Y\nfrom .support_verification import register_run\n",
    )

    violations = find_violations(clean_tree)

    assert "packages.support_recovery.diagnosis: reaches packages.support_evaluator" in violations
    assert (
        "packages.support_recovery.diagnosis: reaches "
        "packages.verification.support_verification"
    ) in violations


def test_planted_relative_import_in_restricted_package_is_caught(clean_tree):
    _plant(clean_tree, "packages/support_recovery/__init__.py", "")
    _plant(
        clean_tree,
        "packages/support_recovery/sufficiency.py",
        "from ..verification import support_verification\n",
    )

    violations = find_violations(clean_tree)

    assert (
        "packages.support_recovery.sufficiency: reaches "
        "packages.verification.support_verification"
    ) in violations


# Runtime imports


def test_restricted_modules_never_load_evaluator_or_verifier_at_runtime():
    modules = restricted_modules(REPO_ROOT)

    assert "environments.support.tools" in modules
    assert "packages.action_gateway.gateway" in modules
    assert runtime_violations(REPO_ROOT, modules) == []


def test_planted_runtime_import_is_caught(clean_tree):
    _plant(clean_tree, "packages/support_evaluator/catalog.py", "X = 1\n")
    # Assembled at runtime, so the static string check cannot see it.
    _plant(
        clean_tree,
        "packages/support_agent/agent.py",
        "import importlib\n"
        "importlib.import_module('packages.' + 'support_' + 'evaluator')\n",
    )

    assert find_violations(clean_tree) == []
    assert runtime_violations(clean_tree, ["packages.support_agent.agent"]) == [
        "packages.support_agent.agent: loads packages.support_evaluator at runtime",
    ]


def test_planted_transitive_runtime_import_is_caught(clean_tree):
    _plant(
        clean_tree,
        "packages/verification/__init__.py",
        "from .deterministic import Y\nfrom .support_verification import X\n",
    )

    violations = runtime_violations(clean_tree, ["packages.support_recovery.diagnosis"])

    assert sorted(violations) == [
        "packages.support_recovery.diagnosis: loads packages.support_evaluator at runtime",
        "packages.support_recovery.diagnosis: loads "
        "packages.verification.support_verification at runtime",
    ]


# Answer literals in restricted source


def test_answer_literals_cover_the_catalog():
    assert answer_literals() == {
        "T-1003", "T-1002", "A-2003", "Q-PRIORITY", "Q-GENERAL", "C-3103", "C-3104",
    }


def test_restricted_source_contains_no_answer_literals():
    assert literal_violations(REPO_ROOT) == []


@pytest.mark.parametrize(
    ("relative", "source", "expected"),
    [
        (
            "packages/support_agent/agent.py",
            'TARGET = "T-1003"\n',
            "packages.support_agent.agent: contains answer literal T-1003",
        ),
        (
            "packages/support_recovery/diagnosis.py",
            "# swap C-3103 back\n",
            "packages.support_recovery.diagnosis: contains answer literal C-3103",
        ),
        (
            "environments/support/tools.py",
            "DEFAULT_QUEUE = 'Q-PRIORITY'\n",
            "environments.support.tools: contains answer literal Q-PRIORITY",
        ),
        (
            "packages/integrations/openai_agents/hooks.py",
            "EXPECTED = {'account': 'A-2003'}\n",
            "packages.integrations.openai_agents.hooks: contains answer literal A-2003",
        ),
    ],
)
def test_planted_answer_literals_are_caught(clean_tree, relative, source, expected):
    _plant(clean_tree, relative, source)

    assert expected in literal_violations(clean_tree)


def test_fixture_data_is_exempt_and_lookalikes_are_not_flagged(clean_tree):
    _plant(clean_tree, "environments/support/fixtures.py", 'SEED = ["T-1003", "Q-PRIORITY"]\n')
    _plant(clean_tree, "packages/support_agent/agent.py", 'OTHER = ["T-10031", "XT-1003"]\n')

    assert literal_violations(clean_tree) == []
