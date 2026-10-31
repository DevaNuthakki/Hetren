from __future__ import annotations

from dataclasses import FrozenInstanceError
import ast
import hashlib
import inspect
import json

import pytest

from packages.core.hetren_diagnosis.contracts import ContractError

import packages.engines.behavioral.p09_4_c1_commitment as module

from packages.engines.behavioral.p09_4_c1_commitment import (
    build_development_c1_commitment,
    P094DevelopmentC1Commitment,
)


PROTOCOL = (
    "46ea27e825bedbfbd8ee0443173884f904f20881fc929a4c44fae30c550e7621"
)

SOURCE = "9c230e65e9f5375f7d0b4f923e314fe33c43ec43"

DEVELOPMENT_SEED = bytes(range(32))


def build(**overrides):
    arguments = {
        "raw_seed": DEVELOPMENT_SEED,
        "protocol_sha256": PROTOCOL,
        "source_commit": SOURCE,
    }
    arguments.update(overrides)
    return build_development_c1_commitment(**arguments)


def test_commitment_matches_supplied_synthetic_seed():
    result = build()

    assert result.seed_sha256 == hashlib.sha256(
        DEVELOPMENT_SEED
    ).hexdigest()

    assert result.protocol_sha256 == PROTOCOL
    assert result.source_commit == SOURCE


def test_commitment_is_deterministic():
    first = build()
    second = build()

    assert first == second
    assert first.canonical_json_bytes() == second.canonical_json_bytes()
    assert first.record_sha256() == second.record_sha256()


def test_raw_seed_is_not_published_in_candidate_record():
    result = build()

    payload = result.canonical_payload()
    serialized = result.canonical_json_bytes()

    assert payload["development_only"] is True
    assert payload["record_type"] == "P094DevelopmentC1Commitment"
    assert "raw_seed" not in payload
    assert DEVELOPMENT_SEED.hex().encode("ascii") not in serialized
    assert json.loads(serialized) == payload


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        "x" * 32,
        bytearray(range(32)),
        b"",
        b"x" * 31,
        b"x" * 33,
    ],
)
def test_invalid_seed_is_rejected(invalid):
    with pytest.raises(ContractError):
        build(raw_seed=invalid)


def test_distinct_development_seeds_have_distinct_commitments():
    first = build()

    second = build(
        raw_seed=bytes(reversed(range(32)))
    )

    assert first.seed_sha256 != second.seed_sha256


def test_generation_seed_commitment_collision_is_rejected():
    digest = hashlib.sha256(
        DEVELOPMENT_SEED
    ).hexdigest()

    with pytest.raises(ContractError):
        build(generation_seed_sha256=digest)


def test_distinct_generation_commitment_is_accepted():
    result = build(
        generation_seed_sha256="a" * 64
    )

    assert result.seed_sha256 != "a" * 64


@pytest.mark.parametrize(
    "field,value",
    [
        ("protocol_sha256", "invalid"),
        ("protocol_sha256", "A" * 64),
        ("source_commit", "invalid"),
        ("source_commit", "A" * 40),
        ("generation_seed_sha256", "invalid"),
    ],
)
def test_invalid_lineage_is_rejected(field, value):
    with pytest.raises(ContractError):
        build(**{field: value})


def test_commitment_is_immutable():
    result = build()

    with pytest.raises(FrozenInstanceError):
        result.seed_sha256 = "a" * 64


def test_direct_construction_validates_fingerprints():
    with pytest.raises(ContractError):
        P094DevelopmentC1Commitment(
            protocol_sha256=PROTOCOL,
            source_commit=SOURCE,
            seed_sha256="not-a-digest",
        )


def test_module_contains_no_randomness_or_filesystem_execution():
    tree = ast.parse(inspect.getsource(module))

    forbidden_modules = {
        "secrets",
        "random",
        "os",
        "subprocess",
        "pathlib",
    }

    forbidden_calls = {
        "open",
        "urandom",
        "token_bytes",
        "write_bytes",
        "write_text",
        "mkdir",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_modules

        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden_modules

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls

            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
