"""The weighted loss normalisation of ``qlora.train_step`` on CPU, with a tiny
model: one optimiser step over B examples, as B accumulated micro-batches of
one example, gives the same update as one batch with loss Σᵢ wᵢ·ℓᵢ / B (and
not Σᵢ wᵢ·ℓᵢ / Σᵢ wᵢ), for a full step of 16 and for a short last step of 5.
Needs ``torch`` and ``accelerate``: the slow CI job installs both (CPU torch)
and checks they import, so it runs there; anywhere without them it is
skipped."""

import copy
import random
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.slow

torch = pytest.importorskip("torch")
accelerate = pytest.importorskip("accelerate")

from packages.hetren_baselines.qlora import example_loss, train_step  # noqa: E402


VOCAB = 50


class TinyLM(torch.nn.Module):
    """A frozen embedding (like the quantised base), one trainable mixing layer with dropout (like LoRA) and an
    output head; ``logits_to_keep`` as in transformers."""

    def __init__(self, dropout=0.0):
        super().__init__()
        self.embed = torch.nn.Embedding(VOCAB, 8)
        self.embed.weight.requires_grad_(False)
        self.mix = torch.nn.Linear(8, 8)
        self.drop = torch.nn.Dropout(dropout)
        self.head = torch.nn.Linear(8, VOCAB)

    def forward(self, input_ids, logits_to_keep=0):
        hidden = torch.tanh(self.drop(self.mix(self.embed(input_ids))).cumsum(dim=1))
        hidden = hidden[:, -logits_to_keep:] if logits_to_keep else hidden
        return SimpleNamespace(logits=self.head(hidden))


def examples(count, seed=2029):
    rng = random.Random(seed)
    result = []

    for _ in range(count):
        prompt, target = rng.randint(3, 10), rng.randint(1, 6)
        result.append(([rng.randrange(VOCAB) for _ in range(prompt + target)], prompt, rng.choice([1.0, 1.4, 3.0])))

    return result


def _trainable(model):
    return [p for p in model.parameters() if p.requires_grad]


def _reference_step(model, batch, divisor):
    """One batch: loss Σᵢ wᵢ·ℓᵢ / divisor, one backward pass, one SGD step of learning rate 1."""
    optimizer = torch.optim.SGD(_trainable(model), lr=1.0)
    (sum(w * example_loss(model, ids, p) for ids, p, w in batch) / divisor).backward()
    optimizer.step()


@pytest.mark.parametrize("size", [16, 5])
def test_one_step_of_accumulated_micro_batches_equals_one_batch_divided_by_its_size(size):
    torch.manual_seed(2029)
    model = TinyLM()
    reference, by_weight_sum = copy.deepcopy(model), copy.deepcopy(model)
    batch = examples(size)

    _reference_step(reference, batch, size)
    _reference_step(by_weight_sum, batch, sum(w for _, _, w in batch))

    accelerator = accelerate.Accelerator(cpu=True)
    optimizer = torch.optim.SGD(_trainable(model), lr=1.0)
    model, optimizer = accelerator.prepare(model, optimizer)
    result = train_step(accelerator, model, optimizer, batch, _trainable(model), max_grad_norm=1e9)

    assert len(result["losses"]) == size and result["finite"] and not result["skipped"]

    for trained, expected in zip(_trainable(model), _trainable(reference)):
        assert torch.allclose(trained, expected, rtol=1e-5, atol=1e-7)

    assert not all(torch.allclose(t, o, rtol=1e-4) for t, o in zip(_trainable(model), _trainable(by_weight_sum)))
    assert torch.equal(model.embed.weight, reference.embed.weight)  # frozen weights never move
