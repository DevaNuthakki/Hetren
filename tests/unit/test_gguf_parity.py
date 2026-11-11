"""The GGUF token-parity driver reads validation records only and checks every distinct text once."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.support_evaluator import gguf_parity


REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeTokenizer:
    def apply_chat_template(self, messages, add_generation_prompt, tokenize=True):
        assert add_generation_prompt
        text = "|".join(f"{m['role']}:{m['content']}" for m in messages) + "|assistant:"
        return text if not tokenize else [ord(c) for c in text]

    def encode(self, text, add_special_tokens):
        assert not add_special_tokens
        return [ord(c) for c in text]


def _tree(tmp_path: Path) -> Path:
    for tier, (dataset, split) in gguf_parity.SOURCES.items():
        (tmp_path / dataset).mkdir(parents=True)
        (tmp_path / split).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / split).write_text("case-1\ncase-2\n", encoding="utf-8")
        step = {"input": {"tier": tier}, "target": {"args": {}, "verb": "no_intervention", "action": "decide"}}
        records = [{"case_id": "case-1", "steps": [step, step]}, {"case_id": "case-2", "steps": [step]},
                   {"case_id": "case-3", "steps": [{"input": {"tier": tier, "train": True}, "target": step["target"]}]}]
        (tmp_path / dataset / "hetren_visible.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return tmp_path


def test_texts_cover_each_tiers_validation_prompts_and_targets_once(tmp_path, monkeypatch):
    monkeypatch.setattr(gguf_parity, "render_evidence", lambda evidence: json.dumps(evidence, sort_keys=True))
    items = list(gguf_parity.parity_texts(FakeTokenizer(), root=_tree(tmp_path)))
    labels = [label for label, _, _ in items]
    # One prompt per tier (identical steps repeat) and the target alone and with the end-of-turn token, which
    # is the same in both tiers and so is checked once.
    assert labels == ["tier 1 case-1 step 0 prompt", "tier 1 case-1 step 0 target", "tier 1 case-1 step 0 target+eot",
                      "tier 2 case-1 step 0 prompt"]
    assert items[1][1] == '{"action": "decide", "verb": "no_intervention", "args": {}}'
    assert items[2][1] == items[1][1] + "<|im_end|>"
    assert all(ids == [ord(c) for c in text] for _, text, ids in items)
    assert not any('"train"' in text for _, text, _ in items)  # case-3 is not in the split


def test_tier_prompts_use_prompt_version_2_for_each_tier(tmp_path, monkeypatch):
    from packages.hetren_baselines.prompt import system_prompt

    monkeypatch.setattr(gguf_parity, "render_evidence", lambda evidence: json.dumps(evidence, sort_keys=True))
    prompts = {label.split()[1]: text for label, text, _ in gguf_parity.parity_texts(FakeTokenizer(), root=_tree(tmp_path))
               if label.endswith("prompt")}
    assert prompts["1"].startswith(f"system:{system_prompt(1, 2)}|user:")
    assert prompts["2"].startswith(f"system:{system_prompt(2, 2)}|user:")


def test_run_stops_when_the_server_serves_another_file(tmp_path):
    class Server:
        def props(self):
            return {"model_path": "/models/other.gguf"}

    with pytest.raises(ValueError, match="serving 'other.gguf'"):
        gguf_parity.run(tmp_path, tmp_path / "hetren-qwen3-4b-ckpt0792-q8_0.gguf", Server(), FakeTokenizer(), root=tmp_path)


@pytest.mark.skipif(not all((REPO_ROOT / d / "hetren_visible.jsonl").exists() for d, _ in gguf_parity.SOURCES.values()),
                    reason="datasets are gitignored")
def test_real_validation_records_yield_prompts_and_targets_for_both_tiers():
    tiers = {}
    for tier in (1, 2):
        steps = list(gguf_parity.validation_steps(tier))
        members = set((REPO_ROOT / gguf_parity.SOURCES[tier][1]).read_text(encoding="utf-8").split())
        assert {case_id for case_id, _, _ in steps} == members
        tiers[tier] = len(steps)
    assert tiers[1] >= 1_028 and tiers[2] >= 757  # at least one step per validation record
