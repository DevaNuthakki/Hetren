"""The QLoRA helpers that run without a GPU: the epoch-budget rule of
Amendment 1, the seeded training order, and the check that a training
prompt is exactly the prompt evaluation sends."""

import pytest

from packages.hetren_baselines import qlora
from packages.hetren_baselines.qlora import BUDGET_HOURS, END_OF_TURN, budget, encode, training_order


COUNTS = {"examples": 17_082, "tokens": 32_600_000, "probe_tokens": 14_000_000, "non_probe_tokens": 18_600_000}


def _pilot(configuration, rate, completed=True, non_finite=0):
    return {"configuration": configuration, "tokens_per_second": rate, "completed": completed,
            "non_finite_losses": non_finite}


def test_a_fast_enough_configuration_trains_one_full_epoch():
    result = budget([_pilot("1xGPU", 500.0), _pilot("2xGPU", 900.0)], COUNTS)

    assert result["configuration"] == "2xGPU" and result["decision"] == "full_epoch" and result["probe_rate"] == 1.0


def test_a_slow_configuration_keeps_every_non_probe_example_and_subsamples_probes_to_the_budget():
    result = budget([_pilot("1xGPU", 500.0)], COUNTS)
    kept_tokens = COUNTS["non_probe_tokens"] + result["probe_rate"] * COUNTS["probe_tokens"]

    assert result["decision"] == "subsample_probes"
    assert kept_tokens / 500.0 / 3600 == pytest.approx(BUDGET_HOURS, abs=0.01)


def test_unstable_or_failed_pilots_are_never_chosen_and_too_slow_means_no_training():
    assert budget([_pilot("2xGPU", 900.0, non_finite=1), _pilot("1xGPU", 500.0)], COUNTS)["configuration"] == "1xGPU"
    assert budget([_pilot("1xGPU", 0.0, completed=False)], COUNTS)["decision"] == "stop"
    assert budget([_pilot("1xGPU", 300.0)], COUNTS)["decision"] == "stop"


def test_the_training_order_is_seeded():
    assert training_order(100) == training_order(100) != list(range(100))


class FakeTokenizer:
    """A chat template in Qwen's format, one token per character."""

    def __init__(self, think=False):
        self.think = think

    def apply_chat_template(self, messages, add_generation_prompt=False, tokenize=True):
        text = "".join(f"<|im_start|>{m['role']}\n"
                       f"{'<think></think>' if self.think and m['role'] == 'assistant' else ''}"
                       f"{m['content']}{END_OF_TURN}\n" for m in messages)
        return list(text + ("<|im_start|>assistant\n" if add_generation_prompt else ""))

    def encode(self, text, add_special_tokens=False):
        return list(text)


ROW = {"tier": 1, "user": "evidence", "target": '{"action": "decide"}', "case_id": "case-1", "step": 0}


@pytest.fixture(autouse=True)
def short_system_prompt(monkeypatch):
    """The fake tokenizer counts characters, so the real system prompt would exceed the length limit."""
    monkeypatch.setattr(qlora, "system_prompt", lambda tier, version: f"system prompt v{version}, tier {tier}")


def test_training_examples_start_the_target_exactly_where_generation_starts():
    ids, prompt_length = encode(FakeTokenizer(), ROW)

    assert "".join(ids[prompt_length:]) == ROW["target"] + END_OF_TURN
    assert "".join(ids[:prompt_length]).endswith("<|im_start|>assistant\n")


def test_a_template_that_adds_text_before_the_target_is_refused():
    with pytest.raises(ValueError, match="chat template"):
        encode(FakeTokenizer(think=True), ROW)


def test_the_budgeted_epoch_has_1055_steps_and_checkpoints_at_each_quarter():
    from packages.hetren_baselines.qlora import checkpoint_steps, total_steps

    assert total_steps(16_869) == 1_055
    assert checkpoint_steps(1_055) == [264, 528, 792, 1_055]


def test_only_the_newest_resume_only_checkpoint_is_kept_and_candidates_never_go(tmp_path):
    from packages.hetren_baselines.qlora import RESUME_EVERY, checkpoint_name, checkpoint_steps, prune_resume_checkpoints

    for name in ("resume-0066", "resume-0132", "checkpoint-0264", "resume-0330"):
        (tmp_path / name).mkdir()

    assert prune_resume_checkpoints(tmp_path, 330) == ["resume-0066", "resume-0132"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["checkpoint-0264", "resume-0330"]
    assert prune_resume_checkpoints(tmp_path, 528) == ["resume-0330"]
    assert checkpoint_name(396, False) == "resume-0396" and checkpoint_name(528, True) == "checkpoint-0528"
    # Every candidate except the last falls on a resume interval, so the candidate is the resume point there.
    assert [step % RESUME_EVERY for step in checkpoint_steps(1_055)] == [0, 0, 0, 1_055 % RESUME_EVERY]
