"""The weighted loss normalisation of ``qlora.micro_step`` on CPU, with a tiny
model: 16 micro-batches of one example, accumulated by accelerate, give the
same gradient as one effective batch of 16 with loss Σᵢ wᵢ·ℓᵢ / 16 (and not
Σᵢ wᵢ·ℓᵢ / Σᵢ wᵢ). Needs ``torch`` and ``accelerate``: the slow CI job
installs both (CPU torch) and checks they import, so it runs there; anywhere
without them it is skipped."""

import copy
import random
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.slow

torch = pytest.importorskip("torch")
accelerate = pytest.importorskip("accelerate")

from packages.hetren_baselines.qlora import SETTINGS, example_loss, micro_step  # noqa: E402


VOCAB = 50


class TinyLM(torch.nn.Module):
    """Embedding, one mixing layer and an output head; ``logits_to_keep`` as in transformers."""

    def __init__(self):
        super().__init__()
        self.embed = torch.nn.Embedding(VOCAB, 8)
        self.mix = torch.nn.Linear(8, 8)
        self.head = torch.nn.Linear(8, VOCAB)

    def forward(self, input_ids, logits_to_keep=0):
        hidden = torch.tanh(self.mix(self.embed(input_ids)).cumsum(dim=1))
        hidden = hidden[:, -logits_to_keep:] if logits_to_keep else hidden
        return SimpleNamespace(logits=self.head(hidden))


def _examples():
    rng = random.Random(2029)
    examples = []

    for _ in range(SETTINGS["effective_batch"]):
        prompt, target = rng.randint(3, 10), rng.randint(1, 6)
        ids = [rng.randrange(VOCAB) for _ in range(prompt + target)]
        examples.append((ids, prompt, rng.choice([1.0, 1.4, 3.0])))

    return examples


def _gradients(model):
    return [p.grad.detach().clone() for p in model.parameters()]


def test_sixteen_accumulated_micro_batches_equal_one_effective_batch_of_sixteen():
    torch.manual_seed(2029)
    model = TinyLM()
    reference, by_weight_sum = copy.deepcopy(model), copy.deepcopy(model)
    examples = _examples()
    batch = SETTINGS["effective_batch"]

    # One effective batch: Σ wᵢ·ℓᵢ / 16, one backward pass.
    (sum(w * example_loss(reference, ids, p) for ids, p, w in examples) / batch).backward()
    # The normalisation qlora does not use: Σ wᵢ·ℓᵢ / Σ wᵢ.
    (sum(w * example_loss(by_weight_sum, ids, p) for ids, p, w in examples)
     / sum(w for _, _, w in examples)).backward()

    # 16 micro-batches of one example, accumulated exactly as the pilot and training do.
    accelerator = accelerate.Accelerator(cpu=True, gradient_accumulation_steps=batch)
    prepared = accelerator.prepare(model)
    synced = []

    for ids, p, w in examples:
        with accelerator.accumulate(prepared):
            micro_step(accelerator, prepared, ids, p, w)
            synced.append(accelerator.sync_gradients)

    assert synced == [False] * (batch - 1) + [True]

    for accumulated, expected, other in zip(_gradients(model), _gradients(reference), _gradients(by_weight_sum)):
        assert torch.allclose(accumulated, expected, rtol=1e-5, atol=1e-7)

    assert not all(torch.allclose(a, o, rtol=1e-3) for a, o in zip(_gradients(model), _gradients(by_weight_sum)))
