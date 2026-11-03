"""Resumable QLoRA training on CPU, with a tiny model: training N steps
straight gives exactly the same weights, optimiser and scheduler state and
random number generator state as training K steps, saving a checkpoint (a
selection candidate or a resume-only one), resuming from it in a fresh model
and continuing to N. A checkpoint whose
files or ``state.json`` do not match their hashes is refused. Needs ``torch``
and ``accelerate`` (the slow CI job installs both)."""

import json

import pytest

pytestmark = pytest.mark.slow

torch = pytest.importorskip("torch")
accelerate = pytest.importorskip("accelerate")

from packages.hetren_baselines.qlora import (  # noqa: E402
    checkpoint_name, checkpoint_steps, cosine_schedule, load_checkpoint, run_training, save_checkpoint, total_steps,
    training_order, verify_checkpoint,
)
from tests.unit.test_qlora_accumulation import TinyLM, examples  # noqa: E402


EXAMPLES = examples(72)  # 5 optimiser steps: four of 16 and a last one of 8
STEPS = total_steps(len(EXAMPLES))
CHECKPOINTS = checkpoint_steps(STEPS)


def _setup():
    torch.manual_seed(2029)
    accelerator = accelerate.Accelerator(cpu=True)
    model = TinyLM(dropout=0.2)  # dropout makes the result depend on the restored RNG state
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-2, weight_decay=0.0)
    scheduler = cosine_schedule(optimizer, warmup=1, steps=STEPS)
    model, optimizer = accelerator.prepare(model, optimizer)
    return accelerator, model, optimizer, scheduler


def _train(directory, start_step, stop_step, parts):
    accelerator, model, optimizer, scheduler = parts
    written = {}

    def save(step, candidate):
        name = checkpoint_name(step, candidate)
        written[name] = save_checkpoint(directory / name, accelerator, model, optimizer, scheduler, step,
                                        {"total_steps": STEPS})

    # A resume-only checkpoint after every step that is not a candidate (here only step 1).
    run_training(accelerator, model, optimizer, scheduler, lambda i: EXAMPLES[i], training_order(len(EXAMPLES)),
                 start_step=start_step, stop_step=stop_step, checkpoints=CHECKPOINTS, save=save, resume_every=1)
    return written


def _state(parts):
    _, model, optimizer, scheduler = parts
    return ([p.detach().clone() for p in model.parameters()], optimizer.state_dict(), scheduler.state_dict(),
            torch.get_rng_state())


@pytest.mark.parametrize("name", ["checkpoint-0002", "resume-0001"])
def test_training_straight_and_training_with_a_resume_end_identically(tmp_path, name):
    assert STEPS == 5 and CHECKPOINTS == [2, 3, 4, 5]

    straight = _setup()
    assert set(_train(tmp_path / "straight", 0, STEPS, straight)) == {
        "resume-0001", "checkpoint-0002", "checkpoint-0003", "checkpoint-0004", "checkpoint-0005"}

    stop = int(name.split("-")[1])
    written = _train(tmp_path / "resumed", 0, stop, _setup())  # a session that ends (or dies) after this step
    resumed = _setup()  # a fresh model, optimiser and scheduler, as in a new session
    state = load_checkpoint(tmp_path / "resumed" / name, *resumed, written[name])
    _train(tmp_path / "resumed", state["step"], STEPS, resumed)

    weights, optimizer, scheduler, rng = _state(straight)
    weights_r, optimizer_r, scheduler_r, rng_r = _state(resumed)

    assert all(torch.equal(a, b) for a, b in zip(weights, weights_r))
    assert scheduler == scheduler_r and torch.equal(rng, rng_r)
    assert optimizer["param_groups"] == optimizer_r["param_groups"]
    assert all(torch.equal(optimizer["state"][k][name], optimizer_r["state"][k][name])
               for k in optimizer["state"] for name in ("exp_avg", "exp_avg_sq"))
    # Both runs wrote the same final checkpoint, file for file.
    files = json.loads((tmp_path / "straight" / "checkpoint-0005" / "state.json").read_text())["files"]
    assert files["trainable.pt"] == json.loads((tmp_path / "resumed" / "checkpoint-0005" / "state.json").read_text())[
        "files"]["trainable.pt"]


def test_a_checkpoint_that_does_not_match_its_hashes_is_refused(tmp_path):
    written = _train(tmp_path, 0, CHECKPOINTS[0], _setup())
    checkpoint = tmp_path / "checkpoint-0002"

    assert verify_checkpoint(checkpoint, written["checkpoint-0002"])["step"] == 2

    with pytest.raises(ValueError, match="expected sha256"):
        verify_checkpoint(checkpoint, "0" * 64)

    (checkpoint / "scheduler.pt").write_bytes(b"tampered")

    with pytest.raises(ValueError, match="scheduler.pt does not match"):
        load_checkpoint(checkpoint, *_setup())
