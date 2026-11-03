"""QLoRA fine-tuning of Qwen3-4B on the Milestone 3 training data, and the throughput pilot.

Every setting is fixed by ``EVAL_PROTOCOL.md``, Amendment 1 (``SETTINGS``).
Each example is the tier's system prompt (version 2), the step's compact
evidence and the target action, through the model's own chat template;
the prompt is exactly what evaluation sends (``apply_chat_template`` with
``add_generation_prompt``), and the loss covers only the target and its
end-of-turn token. Only the logits of the target positions are computed
(``logits_to_keep``).

Loss normalisation (``micro_step``):

- per example: ℓᵢ is the mean cross-entropy over that example's target
  tokens (per-token averaging within an example, so a long target does not
  count more than a short one);
- weighted: each micro-batch holds one example, and its loss is wᵢ·ℓᵢ with
  wᵢ the example's weight from the training file;
- across gradient accumulation: ``accelerator.backward`` divides each
  micro-batch's loss by the accumulation steps (16 on one GPU, 8 per process
  on two), and data-parallel training averages the processes' gradients;
  so one optimiser step follows the gradient of Σᵢ wᵢ·ℓᵢ / 16 over its 16
  examples. The sum is divided by the number of examples, not by Σᵢ wᵢ: a
  rare-label example raises the step's total weight instead of taking it
  from the others.

Throughput pilot (Amendment 1, "Epoch budget"), on one GPU:
``python -m packages.hetren_baselines.qlora pilot --data <train.jsonl> --out <dir> --minutes 15``;
on two: ``torchrun --nproc_per_node 2 -m packages.hetren_baselines.qlora pilot ...``.
``budget`` then applies the declared rule to the pilots' results. The pilot's
weights are never saved.

``torch``, ``transformers``, ``peft``, ``bitsandbytes`` and ``accelerate``
are imported only when a model is built, so the rest (and its tests) runs
without them.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import random
import sys
import time

from packages.hetren_baselines.local_model import QWEN_MODEL, QWEN_REVISION, platform_name
from packages.hetren_baselines.prompt import system_prompt


SETTINGS = {
    "model": QWEN_MODEL,
    "revision": QWEN_REVISION,
    "prompt_version": 2,
    "quantization": {"type": "nf4", "double_quant": True, "compute_dtype": "float16"},
    "lora": {"r": 16, "alpha": 32, "dropout": 0.05,
             "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]},
    "optimizer": "paged_adamw_8bit",
    "learning_rate": 1e-4,
    "weight_decay": 0.0,
    "schedule": "cosine",
    "warmup_ratio": 0.03,
    "max_grad_norm": 1.0,
    "effective_batch": 16,
    "max_length": 2560,
    "gradient_checkpointing": True,
    "seed": 2029,
}
BUDGET_HOURS = 14.0
END_OF_TURN = "<|im_end|>"


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).open(encoding="utf-8")]


def training_order(count: int, seed: int = SETTINGS["seed"]) -> list[int]:
    """The seeded order in which examples are seen (the pilot takes its examples from the start of it)."""
    order = list(range(count))
    random.Random(seed).shuffle(order)
    return order


def encode(tokenizer, row: dict) -> tuple[list[int], int]:
    """Token IDs of prompt plus target, and the prompt's length; stops if the template does anything unexpected."""
    messages = [{"role": "system", "content": system_prompt(row["tier"], SETTINGS["prompt_version"])},
                {"role": "user", "content": row["user"]}]
    prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
    full = tokenizer.apply_chat_template(messages + [{"role": "assistant", "content": row["target"]}], tokenize=True)
    completion = tokenizer.encode(row["target"] + END_OF_TURN, add_special_tokens=False)
    ids = full[:len(prompt) + len(completion)]

    if full[:len(prompt)] != prompt or ids[len(prompt):] != completion:
        raise ValueError(f"the chat template does not end the prompt where generation starts ({row['case_id']})")

    if len(ids) > SETTINGS["max_length"]:
        raise ValueError(f"{row['case_id']} step {row['step']} has {len(ids)} tokens, over {SETTINGS['max_length']}")

    return ids, len(prompt)


def token_counts(tokenizer, rows: list[dict]) -> dict[str, object]:
    """Tokens per epoch, in all and for the probe and non-probe examples (the budget rule needs both)."""
    lengths = [len(encode(tokenizer, row)[0]) for row in rows]
    probe = sum(n for n, row in zip(lengths, rows) if row["kind"].endswith("probe"))
    return {"examples": len(rows), "tokens": sum(lengths), "probe_tokens": probe,
            "non_probe_tokens": sum(lengths) - probe, "max_tokens": max(lengths)}


def budget(pilots: list[dict], counts: dict[str, object], hours: float = BUDGET_HOURS) -> dict[str, object]:
    """Amendment 1's rule: the fastest stable configuration; a full epoch if it takes at most ``hours``,
    otherwise every non-probe example and one seeded rate of probe examples; no training if even that is too long."""
    stable = [p for p in pilots if p["completed"] and p["non_finite_losses"] == 0]

    if not stable:
        return {"decision": "stop", "reason": "no configuration ran stably"}

    best = max(stable, key=lambda p: p["tokens_per_second"])
    rate = best["tokens_per_second"]
    epoch_hours = counts["tokens"] / rate / 3600
    result = {"configuration": best["configuration"], "tokens_per_second": rate, "epoch_hours": round(epoch_hours, 2),
              "sample_mean_tokens": best.get("timed_mean_tokens"),
              "dataset_mean_tokens": round(counts["tokens"] / counts["examples"], 1)}

    if epoch_hours <= hours:
        return {**result, "decision": "full_epoch", "probe_rate": 1.0}

    probe_rate = (hours * 3600 * rate - counts["non_probe_tokens"]) / counts["probe_tokens"]

    if probe_rate <= 0:
        return {**result, "decision": "stop", "reason": "the non-probe examples alone take longer than the budget"}

    return {**result, "decision": "subsample_probes", "probe_rate": round(probe_rate, 4)}


def library_versions() -> dict[str, str]:
    from importlib.metadata import version
    import platform

    versions = {"python": platform.python_version()}

    for name in ("torch", "transformers", "accelerate", "tokenizers", "peft", "bitsandbytes"):
        try:
            versions[name] = version(name)
        except Exception:
            versions[name] = "not installed"

    return versions


def build_model(accelerator):
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, set_seed

    set_seed(SETTINGS["seed"])
    quantization = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        QWEN_MODEL, revision=QWEN_REVISION, quantization_config=quantization, torch_dtype=torch.float16,
        device_map={"": accelerator.local_process_index},
    )
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    lora = SETTINGS["lora"]
    config = LoraConfig(r=lora["r"], lora_alpha=lora["alpha"], lora_dropout=lora["dropout"],
                        target_modules=lora["target_modules"], bias="none", task_type="CAUSAL_LM")
    return get_peft_model(model, config)


def example_loss(model, ids: list[int], prompt_length: int):
    """Mean cross-entropy over the target tokens, from the logits of those positions only."""
    import torch
    import torch.nn.functional as F

    device = next(p for p in model.parameters() if p.requires_grad).device
    input_ids = torch.tensor([ids], device=device)
    targets = input_ids[0, prompt_length:]
    logits = model(input_ids=input_ids, logits_to_keep=len(targets) + 1).logits[0, :-1]
    return F.cross_entropy(logits.float(), targets)


def micro_step(accelerator, model, ids: list[int], prompt_length: int, weight: float):
    """One example's weighted loss and its backward pass (``accelerator.backward`` divides by the accumulation steps)."""
    loss = example_loss(model, ids, prompt_length) * weight
    accelerator.backward(loss)
    return loss


def pilot(args: argparse.Namespace) -> int:
    import torch
    from accelerate import Accelerator, DistributedDataParallelKwargs
    from bitsandbytes.optim import PagedAdamW8bit
    from transformers import AutoTokenizer, get_cosine_schedule_with_warmup

    rows = load_rows(args.data)
    processes = int(os.environ.get("WORLD_SIZE", "1"))
    accumulation = SETTINGS["effective_batch"] // processes
    accelerator = Accelerator(
        mixed_precision="fp16", gradient_accumulation_steps=accumulation,
        kwargs_handlers=[DistributedDataParallelKwargs(find_unused_parameters=False)],
    )
    tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL, revision=QWEN_REVISION)
    model = build_model(accelerator)
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = PagedAdamW8bit(trainable, lr=SETTINGS["learning_rate"], weight_decay=SETTINGS["weight_decay"])
    steps_per_epoch = math.ceil(len(rows) / SETTINGS["effective_batch"])
    scheduler = get_cosine_schedule_with_warmup(
        optimizer, math.ceil(SETTINGS["warmup_ratio"] * steps_per_epoch), steps_per_epoch,
    )
    # The scheduler is stepped here once per optimiser step (accelerate's wrapper would step it once per process).
    model, optimizer = accelerator.prepare(model, optimizer)

    # The first optimiser step uses the 16 longest examples (peak memory). Every later step takes its examples
    # from the seeded training order, a random sample of the whole file, so the timed steps (from the third)
    # are representative; their mean tokens per example is recorded for comparison with the dataset's.
    encoded_lengths = {}
    longest = sorted(range(len(rows)), key=lambda i: -len(rows[i]["user"]))[:SETTINGS["effective_batch"]]
    first = set(longest)
    order = longest + [i for i in training_order(len(rows)) if i not in first]
    mine = order[accelerator.process_index::processes]

    record = {"configuration": f"{processes}xGPU", "processes": processes, "accumulation": accumulation,
              "platform": platform_name(), "gpu": torch.cuda.get_device_name(accelerator.device),
              "libraries": library_versions(), "settings": SETTINGS,
              "completed": False, "non_finite_losses": 0, "skipped_steps": 0}
    deadline = time.monotonic() + args.minutes * 60
    tokens, examples, losses, optimizer_steps, start = 0, 0, [], 0, None

    try:
        model.train()

        for index in mine:
            ids, prompt_length = encode(tokenizer, rows[index])
            encoded_lengths[index] = len(ids)

            with accelerator.accumulate(model):
                loss = micro_step(accelerator, model, ids, prompt_length, rows[index]["weight"])

                if not torch.isfinite(loss):
                    record["non_finite_losses"] += 1

                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(trainable, SETTINGS["max_grad_norm"])

                optimizer.step()
                optimizer.zero_grad()

            losses.append(float(loss))

            if start is not None:
                tokens += len(ids)
                examples += 1

            if accelerator.sync_gradients:
                optimizer_steps += 1
                skipped = accelerator.optimizer_step_was_skipped
                record["skipped_steps"] += int(skipped)

                if not skipped:
                    scheduler.step()

                if optimizer_steps == 2:  # steps 1-2 (longest examples, warm-up) are not timed
                    torch.cuda.synchronize()
                    start, tokens, examples = time.monotonic(), 0, 0
                elif start is not None:
                    # Every process stops at the same optimiser step, or data-parallel training would hang.
                    late = torch.tensor([float(time.monotonic() > deadline)], device=accelerator.device)

                    if accelerator.gather(late).max() > 0:
                        break

        torch.cuda.synchronize()
        elapsed = time.monotonic() - start
        totals = accelerator.gather(
            torch.tensor([tokens, examples, record["non_finite_losses"]], device=accelerator.device),
        )
        totals = totals.view(processes, 3).sum(0).tolist()
        peak = accelerator.gather(torch.tensor([torch.cuda.max_memory_allocated()], device=accelerator.device)).tolist()
        record.update({
            "completed": True, "optimizer_steps": optimizer_steps, "timed_seconds": round(elapsed, 1),
            "timed_tokens": int(totals[0]), "timed_examples": int(totals[1]),
            "timed_mean_tokens": round(totals[0] / totals[1], 1), "tokens_per_second": round(totals[0] / elapsed, 1),
            "non_finite_losses": int(totals[2]), "peak_memory_gib": [round(p / 2**30, 2) for p in peak],
            "longest_example_tokens": max(encoded_lengths[i] for i in longest if i in encoded_lengths),
            "loss_first_16": round(sum(losses[:16]) / len(losses[:16]), 4),
            "loss_last_16": round(sum(losses[-16:]) / len(losses[-16:]), 4),
        })
    except Exception as error:  # an out-of-memory error or a library failure is a pilot result too
        record["error"] = f"{type(error).__name__}: {error}"

    if accelerator.is_main_process:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / f"pilot-{record['configuration']}.json").write_text(json.dumps(record, indent=2) + "\n",
                                                                         encoding="utf-8")
        print(json.dumps({k: v for k, v in record.items() if k not in ("settings", "libraries")}, indent=2))

    return 0 if record["completed"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("pilot", help="time the training step for --minutes")
    run.add_argument("--data", required=True, type=Path)
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--minutes", type=float, default=15.0)
    count = commands.add_parser("tokens", help="count tokens per epoch with the model's chat template")
    count.add_argument("--data", required=True, type=Path)
    count.add_argument("--out", required=True, type=Path)
    decide = commands.add_parser("budget", help="apply the epoch-budget rule to the pilots' results")
    decide.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "pilot":
        return pilot(args)

    if args.command == "tokens":
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL, revision=QWEN_REVISION)
        counts = token_counts(tokenizer, load_rows(args.data))
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "tokens.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(counts, indent=2))
        return 0

    pilots = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.out.glob("pilot-*.json"))]
    counts = json.loads((args.out / "tokens.json").read_text(encoding="utf-8"))
    result = budget(pilots, counts)
    (args.out / "budget.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BUDGET_HOURS",
    "SETTINGS",
    "budget",
    "encode",
    "load_rows",
    "micro_step",
    "token_counts",
    "training_order",
]
