"""Checkpoint selection (Amendment 1) without a GPU: a candidate's adapter is
checked against its logged hashes, and the choice is the highest S with exact
ties to the earlier checkpoint, among four candidates evaluated alike."""

import hashlib
import json

import pytest

from packages.support_evaluator.checkpoint_selection import REFERENCE_S, choose, verify_adapter


def _checkpoint(tmp_path, step=528, candidate=True):
    directory = tmp_path / f"checkpoint-{step:04d}"
    (directory / "adapter").mkdir(parents=True)
    (directory / "adapter" / "adapter_config.json").write_text('{"r": 16}', encoding="utf-8")
    (directory / "adapter" / "adapter_model.safetensors").write_bytes(b"weights")
    files = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
             for name in ("adapter/adapter_config.json", "adapter/adapter_model.safetensors")}
    state = {"step": step, "candidate": candidate, "bundle_commit": "7e9089e", "files": files}
    (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return directory, hashlib.sha256((directory / "state.json").read_bytes()).hexdigest()


def test_a_candidate_is_used_only_with_its_logged_hashes(tmp_path):
    directory, digest = _checkpoint(tmp_path)

    assert verify_adapter(directory, digest)["checkpoint"] == "checkpoint-0528"

    with pytest.raises(ValueError, match="logged sha256"):
        verify_adapter(directory, "0" * 64)

    (directory / "adapter" / "adapter_model.safetensors").write_bytes(b"other weights")

    with pytest.raises(ValueError, match="does not match"):
        verify_adapter(directory, digest)


def test_only_the_four_declared_candidates_are_evaluated(tmp_path):
    with pytest.raises(ValueError, match="declared candidates"):
        verify_adapter(*_checkpoint(tmp_path, step=66, candidate=False))


METADATA = {"platform": "kaggle", "gpu": "Tesla T4", "visible_gpus": 1, "libraries": {"torch": "2.11.0"},
            "bundle_commit": "abc", "model": "m", "revision": "r", "dtype": "float16", "max_new_tokens": 128,
            "decoding": "greedy", "prompt_version": 2}


def _result(step, s, **metadata):
    return {"checkpoint": f"checkpoint-{step:04d}", "step": step, "S": s, "A1": {}, "A2": {}, "W": {},
            "monitoring": {}, "state_sha256": f"state{step}", "adapter_sha256": f"adapter{step}",
            "metadata": {**METADATA, **metadata}}


def test_the_highest_s_is_chosen_and_exact_ties_go_to_the_earlier_checkpoint():
    choice = choose([_result(1055, 0.41), _result(264, 0.30), _result(792, 0.41), _result(528, 0.12)])

    assert choice["chosen"] == "checkpoint-0792" and choice["S"] == 0.41
    assert [c["step"] for c in choice["candidates"]] == [264, 528, 792, 1055]
    assert choice["reference_S"] == REFERENCE_S and choice["exceeds_reference"]
    assert not choose([_result(s, 0.10) for s in (264, 528, 792, 1055)])["exceeds_reference"]


def test_candidates_evaluated_differently_or_missing_cannot_be_compared():
    with pytest.raises(ValueError, match="same platform"):
        choose([_result(264, 0.3), _result(528, 0.3), _result(792, 0.3), _result(1055, 0.3, platform="colab")])

    with pytest.raises(ValueError, match="same libraries"):
        choose([_result(264, 0.3), _result(528, 0.3), _result(792, 0.3),
                _result(1055, 0.3, libraries={"torch": "2.12.0"})])

    with pytest.raises(ValueError, match="expected one result"):
        choose([_result(264, 0.3), _result(528, 0.3), _result(792, 0.3)])
