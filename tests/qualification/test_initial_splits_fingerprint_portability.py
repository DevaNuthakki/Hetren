from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "tests/qualification/test_initial_splits.py"
)

EXPECTED_CANONICAL_HASH = (
    "f86429996ed383358f3bc30b0875db32"
    "b812bcfcb6c76f6692bc68ce0a9d9560"
)

PYTHON_312_RAW_AST_DUMP_HASH = (
    "ebdb5d3e628210cf5c4e10a55cce89a8"
    "7211baba43c2fd0da41d9a6363def333"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "task7_fingerprint_contract",
        SOURCE,
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


def remove_empty_lists(
    value,
) -> None:
    if not isinstance(
        value,
        ast.AST,
    ):
        return

    for field_name in tuple(
        value._fields
    ):
        if not hasattr(
            value,
            field_name,
        ):
            continue

        field_value = getattr(
            value,
            field_name,
        )

        if isinstance(
            field_value,
            list,
        ):
            if not field_value:
                delattr(
                    value,
                    field_name,
                )

                continue

            for item in field_value:
                remove_empty_lists(
                    item
                )

            continue

        if isinstance(
            field_value,
            ast.AST,
        ):
            remove_empty_lists(
                field_value
            )


def main() -> None:
    module = load_module()

    actual = (
        module.development_attack_definition_hash()
    )

    assert actual == EXPECTED_CANONICAL_HASH, (
        "canonical development attack fingerprint drifted: "
        f"{actual}"
    )

    tree = ast.parse(
        SOURCE.read_text()
    )

    nodes = {
        node.name: node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            in module.DEVELOPMENT_ATTACK_DEFINITION_FUNCTIONS
        )
    }

    assert set(nodes) == set(
        module.DEVELOPMENT_ATTACK_DEFINITION_FUNCTIONS
    )

    stable = "\n".join(
        module._stable_ast_dump(
            nodes[name]
        )
        for name
        in module.DEVELOPMENT_ATTACK_DEFINITION_FUNCTIONS
    )

    independent_nodes = []

    for name in module.DEVELOPMENT_ATTACK_DEFINITION_FUNCTIONS:
        normalized = copy.deepcopy(
            nodes[name]
        )

        remove_empty_lists(
            normalized
        )

        independent_nodes.append(
            ast.dump(
                normalized,
                annotate_fields=True,
                include_attributes=False,
            )
        )

    independently_normalized = "\n".join(
        independent_nodes
    )

    assert stable == independently_normalized

    assert hashlib.sha256(
        stable.encode(
            "utf-8"
        )
    ).hexdigest() == EXPECTED_CANONICAL_HASH

    # Under Python 3.12 specifically, raw ast.dump() is the
    # representation that caused the GitHub CI portability failure.
    if sys.version_info[:2] == (3, 12):
        raw = "\n".join(
            ast.dump(
                nodes[name],
                annotate_fields=True,
                include_attributes=False,
            )
            for name
            in module.DEVELOPMENT_ATTACK_DEFINITION_FUNCTIONS
        )

        raw_hash = hashlib.sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()

        assert (
            raw_hash
            == PYTHON_312_RAW_AST_DUMP_HASH
        )

        assert (
            raw_hash
            != EXPECTED_CANONICAL_HASH
        )

    print(
        "TASK 7 FINGERPRINT PORTABILITY: PASS"
    )

    print(
        "- canonical fingerprint:",
        actual,
    )

    print(
        "- interpreter:",
        f"{sys.version_info.major}.{sys.version_info.minor}",
    )


if __name__ == "__main__":
    main()
