"""QLoRA fine-tuning of Qwen3-4B on the Milestone 3 training data: throughput pilot and resumable training.

Every setting is fixed by ``EVAL_PROTOCOL.md``, Amendment 1 (``SETTINGS``).
Each example is the tier's system prompt (version 2), the step's compact
evidence and the target action, through the model's own chat template;
the prompt is exactly what evaluation sends (``apply_chat_template`` with
``add_generation_prompt``), and the loss covers only the target and its
end-of-turn token. Only the logits of the target positions are computed
(``logits_to_keep``).

Loss normalisation (``train_step``):

- per example: ℓᵢ is the mean cross-entropy over that example's target
  tokens (per-token averaging within an example, so a long target does not
  count more than a short one);
- weighted: each micro-batch holds one example, and its loss is wᵢ·ℓᵢ with
  wᵢ the example's weight from the training file;
- one optimiser step: its B examples (16; the last step of an epoch may have
  fewer) are shared out over the P processes; each process divides each
  micro-batch's loss by B / P before its backward pass, gradients accumulate
  locally (``no_sync``) and are averaged over the processes once, at the last
  micro-batch. The step therefore follows the gradient of Σᵢ wᵢ·ℓᵢ / B. The
  sum is divided by the number of examples, not by Σᵢ wᵢ: a rare-label
  example raises the step's total weight instead of taking it from the others.

Training order: the examples of the training file in the seeded order of
``training_order``; optimiser step s takes examples s·16 to s·16 + 15 of it.
Checkpoints (``checkpoint_steps``) at 25%, 50%, 75% and 100% of the steps are
the four selection candidates (``checkpoint-<step>``); every ``RESUME_EVERY``
steps in between, a resume-only checkpoint (``resume-<step>``, never
evaluated) is written and older resume-only checkpoints are removed. Each
holds the trainable (LoRA) weights, the PEFT adapter for evaluation, the
optimiser, scheduler and fp16 loss-scaler states, every process's random
number generator states and the step reached (the position in the training
order); ``state.json`` lists every file's sha256 and is checked, file by
file, on resume. A resumed run continues exactly where the saved one stopped:
after a crash at the same learning rate, after a non-finite loss at half of it
(``--lr-scale 0.5``, Amendment 1). ``train-log.jsonl`` records every step,
every checkpoint with its ``state.json`` sha256, and every (re)start.

Commands (``torchrun --nproc_per_node 2 -m packages.hetren_baselines.qlora ...`` on two GPUs):

- ``pilot --data <train.jsonl> --out <dir> --minutes 12``: the throughput
  pilot; its weights are never saved.
- ``tokens`` and ``budget``: tokens per epoch, and the epoch-budget rule.
- ``train --data <train-budget.jsonl> --out <dir> --until-checkpoint K
  [--resume <checkpoint> --resume-sha256 <state.json sha256>] [--lr-scale 0.5]``.

``torch``, ``transformers``, ``peft``, ``bitsandbytes`` and ``accelerate``
are imported only when needed, so the rest (and its tests) runs without them.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
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
RESUME_EVERY = 66  # optimiser steps between resume-only checkpoints (never evaluated; only the latest is kept)
END_OF_TURN = "<|im_end|>"


class NonFiniteLoss(RuntimeError):
    """A loss was not finite (Amendment 1: resume from the last checkpoint at half the learning rate)."""


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).open(encoding="utf-8")]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)

    return digest.hexdigest()


def training_order(count: int, seed: int = SETTINGS["seed"]) -> list[int]:
    """The seeded order in which examples are seen (the pilot takes its examples from the start of it)."""
    order = list(range(count))
    random.Random(seed).shuffle(order)
    return order


def total_steps(examples: int) -> int:
    return math.ceil(examples / SETTINGS["effective_batch"])


def checkpoint_steps(steps: int) -> list[int]:
    """The four candidate checkpoints: 25%, 50%, 75% and 100% of the optimiser steps, rounded up."""
    return [math.ceil(steps * quarter / 4) for quarter in (1, 2, 3, 4)]


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


def cosine_schedule(optimizer, warmup: int, steps: int):
    """Linear warm-up, then cosine decay to zero (the same curve as transformers' cosine schedule)."""
    from torch.optim.lr_scheduler import LambdaLR

    def factor(step: int) -> float:
        if step < warmup:
            return step / max(1, warmup)

        return max(0.0, 0.5 * (1.0 + math.cos(math.pi * (step - warmup) / max(1, steps - warmup))))

    return LambdaLR(optimizer, factor)


def example_loss(model, ids: list[int], prompt_length: int):
    """Mean cross-entropy over the target tokens, from the logits of those positions only."""
    import torch
    import torch.nn.functional as F

    device = next(p for p in model.parameters() if p.requires_grad).device
    input_ids = torch.tensor([ids], device=device)
    targets = input_ids[0, prompt_length:]
    logits = model(input_ids=input_ids, logits_to_keep=len(targets) + 1).logits[0, :-1]
    return F.cross_entropy(logits.float(), targets)


def train_step(accelerator, model, optimizer, batch: list[tuple[list[int], int, float]], trainable,
               max_grad_norm: float = SETTINGS["max_grad_norm"]) -> dict[str, object]:
    """One optimiser step over ``batch`` (every process passes the same batch and trains on its share).

    Returns this process's weighted losses, whether any loss was not finite, and whether the fp16 loss scaler
    skipped the step.
    """
    import torch

    processes = accelerator.num_processes

    if len(batch) < processes:
        raise ValueError(f"a step of {len(batch)} examples cannot be shared out over {processes} processes")

    mine = batch[accelerator.process_index::processes]
    divisor = len(batch) / processes
    losses, finite = [], True

    for position, (ids, prompt_length, weight) in enumerate(mine):
        last = position == len(mine) - 1

        with nullcontext() if last else accelerator.no_sync(model):
            loss = example_loss(model, ids, prompt_length) * weight
            finite = finite and bool(torch.isfinite(loss))
            accelerator.backward(loss / divisor)

        losses.append(float(loss))

    accelerator.clip_grad_norm_(trainable, max_grad_norm)
    optimizer.step()
    optimizer.zero_grad()
    return {"losses": losses, "finite": finite, "skipped": bool(accelerator.optimizer_step_was_skipped)}


def _rng_state() -> dict[str, object]:
    import torch

    state = {"python": random.getstate(), "torch": torch.get_rng_state()}

    if torch.cuda.is_available():
        state["cuda"] = torch.cuda.get_rng_state()

    return state


def _set_rng_state(state: dict[str, object]) -> None:
    import torch

    random.setstate(state["python"])
    torch.set_rng_state(state["torch"])

    if "cuda" in state:
        torch.cuda.set_rng_state(state["cuda"])


def _trainable_names(model) -> list[str]:
    return [name for name, p in model.named_parameters() if p.requires_grad]


def save_checkpoint(directory: Path, accelerator, model, optimizer, scheduler, step: int,
                    meta: dict[str, object]) -> str | None:
    """Write a checkpoint; returns the sha256 of its ``state.json`` (on the main process)."""
    import torch

    directory = Path(directory)
    accelerator.wait_for_everyone()

    if accelerator.is_main_process:
        directory.mkdir(parents=True, exist_ok=False)

    accelerator.wait_for_everyone()
    torch.save(_rng_state(), directory / f"rng-{accelerator.process_index}.pt")

    if accelerator.is_main_process:
        unwrapped = accelerator.unwrap_model(model)
        parameters = dict(unwrapped.named_parameters())
        torch.save({name: parameters[name].detach().cpu() for name in _trainable_names(unwrapped)},
                   directory / "trainable.pt")

        if hasattr(unwrapped, "peft_config"):  # the adapter evaluation merges into the fp16 base
            unwrapped.save_pretrained(directory / "adapter")

        torch.save(optimizer.state_dict(), directory / "optimizer.pt")
        torch.save(scheduler.state_dict(), directory / "scheduler.pt")

        if accelerator.scaler is not None:
            torch.save(accelerator.scaler.state_dict(), directory / "scaler.pt")

    accelerator.wait_for_everyone()
    digest = None

    if accelerator.is_main_process:
        files = {p.relative_to(directory).as_posix(): sha256_file(p) for p in sorted(directory.rglob("*")) if p.is_file()}
        state = {**meta, "step": step, "processes": accelerator.num_processes, "files": files}
        (directory / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        digest = sha256_file(directory / "state.json")

    accelerator.wait_for_everyone()
    return digest


def verify_checkpoint(directory: Path, expected_state_sha256: str | None = None) -> dict[str, object]:
    """``state.json`` of a checkpoint whose files all match their recorded hashes (and ``state.json`` its expected hash)."""
    directory = Path(directory)
    path = directory / "state.json"

    if expected_state_sha256 is not None and sha256_file(path) != expected_state_sha256:
        raise ValueError(f"{path} does not have the expected sha256 {expected_state_sha256}")

    state = json.loads(path.read_text(encoding="utf-8"))
    found = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()} - {"state.json"}

    if found != set(state["files"]):
        raise ValueError(f"{directory} holds {sorted(found ^ set(state['files']))} unlike its state.json")

    for name, digest in state["files"].items():
        if sha256_file(directory / name) != digest:
            raise ValueError(f"{directory / name} does not match its sha256 in state.json")

    return state


def load_checkpoint(directory: Path, accelerator, model, optimizer, scheduler,
                    expected_state_sha256: str | None = None) -> dict[str, object]:
    """Restore a verified checkpoint into the model, optimiser, scheduler, loss scaler and this process's RNGs."""
    import torch

    directory = Path(directory)
    state = verify_checkpoint(directory, expected_state_sha256)

    if state["processes"] != accelerator.num_processes:
        raise ValueError(f"the checkpoint was written by {state['processes']} processes, "
                         f"this run has {accelerator.num_processes}")

    unwrapped = accelerator.unwrap_model(model)
    trainable = torch.load(directory / "trainable.pt", map_location="cpu", weights_only=True)

    if set(trainable) != set(_trainable_names(unwrapped)):
        raise ValueError("the checkpoint's trainable weights do not match this model's")

    unwrapped.load_state_dict(trainable, strict=False)
    optimizer.load_state_dict(torch.load(directory / "optimizer.pt", map_location=accelerator.device, weights_only=True))
    scheduler.load_state_dict(torch.load(directory / "scheduler.pt", weights_only=True))

    if accelerator.scaler is not None:
        accelerator.scaler.load_state_dict(torch.load(directory / "scaler.pt", weights_only=True))

    _set_rng_state(torch.load(directory / f"rng-{accelerator.process_index}.pt", weights_only=True))
    return state


def run_training(accelerator, model, optimizer, scheduler, example, order: list[int], *, start_step: int,
                 stop_step: int, checkpoints: list[int], save, resume_every: int | None = None, log=None) -> int:
    """Optimiser steps ``start_step`` to ``stop_step`` over the training order.

    ``save(step, candidate)`` runs at each candidate checkpoint (``candidate`` true) and, every ``resume_every``
    steps that are not candidates, for a resume-only checkpoint. ``example(index)`` gives (token IDs, prompt
    length, weight). Stops with ``NonFiniteLoss`` when any process saw a non-finite loss (that step's update is
    not saved). Returns the last step completed.
    """
    import torch

    batch_size = SETTINGS["effective_batch"]
    trainable = [p for p in model.parameters() if p.requires_grad]
    model.train()

    for step in range(start_step, stop_step):
        started = time.monotonic()
        batch = [example(i) for i in order[step * batch_size:(step + 1) * batch_size]]
        result = train_step(accelerator, model, optimizer, batch, trainable)
        flags = torch.tensor([float(not result["finite"]), float(result["skipped"])], device=accelerator.device)
        flags = accelerator.gather(flags).view(-1, 2).max(0).values.tolist()

        if flags[0]:
            raise NonFiniteLoss(f"non-finite loss at optimiser step {step + 1}")

        if not flags[1]:
            scheduler.step()

        if log is not None and accelerator.is_main_process:
            log({"step": step + 1, "loss": round(sum(result["losses"]) / len(result["losses"]), 5),
                 "lr": scheduler.get_last_lr()[0], "skipped": bool(flags[1]),
                 "seconds": round(time.monotonic() - started, 2)})

        if step + 1 in checkpoints:
            save(step + 1, True)
        elif resume_every and (step + 1) % resume_every == 0:
            save(step + 1, False)

    return stop_step


def checkpoint_name(step: int, candidate: bool) -> str:
    return f"{'checkpoint' if candidate else 'resume'}-{step:04d}"


def prune_resume_checkpoints(out: Path, newest_step: int) -> list[str]:
    """Remove resume-only checkpoints older than the newest checkpoint (candidates are always kept)."""
    import shutil

    removed = []

    for path in sorted(Path(out).glob("resume-*")):
        if path.is_dir() and int(path.name.split("-")[1]) < newest_step:
            shutil.rmtree(path)
            removed.append(path.name)

    return removed


def pilot(args: argparse.Namespace) -> int:
    import torch
    from accelerate import Accelerator, DistributedDataParallelKwargs
    from bitsandbytes.optim import PagedAdamW8bit
    from transformers import AutoTokenizer

    rows = load_rows(args.data)
    accelerator = Accelerator(mixed_precision="fp16",
                              kwargs_handlers=[DistributedDataParallelKwargs(find_unused_parameters=False)])
    processes = accelerator.num_processes
    tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL, revision=QWEN_REVISION)
    model = build_model(accelerator)
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = PagedAdamW8bit(trainable, lr=SETTINGS["learning_rate"], weight_decay=SETTINGS["weight_decay"])
    steps = total_steps(len(rows))
    scheduler = cosine_schedule(optimizer, math.ceil(SETTINGS["warmup_ratio"] * steps), steps)
    model, optimizer = accelerator.prepare(model, optimizer)

    # The first optimiser step uses the 16 longest examples (peak memory). Every later step takes its examples
    # from the seeded training order, a random sample of the whole file, so the timed steps (from the third)
    # are representative; their mean tokens per example is recorded for comparison with the dataset's.
    batch_size = SETTINGS["effective_batch"]
    longest = sorted(range(len(rows)), key=lambda i: -len(rows[i]["user"]))[:batch_size]
    first = set(longest)
    order = longest + [i for i in training_order(len(rows)) if i not in first]

    record = {"configuration": f"{processes}xGPU", "processes": processes,
              "platform": platform_name(), "gpu": torch.cuda.get_device_name(accelerator.device),
              "libraries": library_versions(), "settings": SETTINGS,
              "completed": False, "non_finite_losses": 0, "skipped_steps": 0}
    deadline = time.monotonic() + args.minutes * 60
    tokens, examples, losses, longest_tokens, start = 0, 0, [], 0, None

    try:
        model.train()

        for step in range(len(order) // batch_size):
            batch = [encode(tokenizer, rows[i]) + (rows[i]["weight"],)
                     for i in order[step * batch_size:(step + 1) * batch_size]]
            result = train_step(accelerator, model, optimizer, batch, trainable)
            mine = batch[accelerator.process_index::processes]
            record["non_finite_losses"] += int(not result["finite"])
            record["skipped_steps"] += int(result["skipped"])
            losses += result["losses"]

            if not result["skipped"]:
                scheduler.step()

            if step == 0:
                longest_tokens = max(len(ids) for ids, _, _ in mine)
            elif step == 1:  # steps 1-2 (longest examples, warm-up) are not timed
                torch.cuda.synchronize()
                start = time.monotonic()
            else:
                tokens += sum(len(ids) for ids, _, _ in mine)
                examples += len(mine)
                # Every process stops at the same optimiser step, or data-parallel training would hang.
                late = torch.tensor([float(time.monotonic() > deadline)], device=accelerator.device)

                if accelerator.gather(late).max() > 0:
                    break

        torch.cuda.synchronize()
        elapsed = time.monotonic() - start
        totals = accelerator.gather(
            torch.tensor([tokens, examples, record["non_finite_losses"], longest_tokens], device=accelerator.device),
        )
        totals = totals.view(processes, 4)
        sums = totals[:, :3].sum(0).tolist()
        peak = accelerator.gather(torch.tensor([torch.cuda.max_memory_allocated()], device=accelerator.device)).tolist()
        record.update({
            "completed": True, "optimizer_steps": step + 1, "timed_seconds": round(elapsed, 1),
            "timed_tokens": int(sums[0]), "timed_examples": int(sums[1]),
            "timed_mean_tokens": round(sums[0] / sums[1], 1), "tokens_per_second": round(sums[0] / elapsed, 1),
            "non_finite_losses": int(sums[2]), "peak_memory_gib": [round(p / 2**30, 2) for p in peak],
            "longest_example_tokens": int(totals[:, 3].max()),
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


def train(args: argparse.Namespace) -> int:
    import torch
    from accelerate import Accelerator, DistributedDataParallelKwargs
    from bitsandbytes.optim import PagedAdamW8bit
    from transformers import AutoTokenizer

    rows = load_rows(args.data)
    steps = total_steps(len(rows))
    checkpoints = checkpoint_steps(steps)
    stop_step = checkpoints[args.until_checkpoint - 1] if args.until_checkpoint else None

    if args.smoke_steps:  # GPU check of saving and resuming: a checkpoint after each of the first steps
        checkpoints, stop_step = list(range(1, args.smoke_steps + 1)), args.smoke_steps

    accelerator = Accelerator(mixed_precision="fp16",
                              kwargs_handlers=[DistributedDataParallelKwargs(find_unused_parameters=False)])
    tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL, revision=QWEN_REVISION)
    model = build_model(accelerator)
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = PagedAdamW8bit(trainable, lr=SETTINGS["learning_rate"], weight_decay=SETTINGS["weight_decay"])
    scheduler = cosine_schedule(optimizer, math.ceil(SETTINGS["warmup_ratio"] * steps), steps)
    model, optimizer = accelerator.prepare(model, optimizer)
    meta = {"settings": SETTINGS, "data_sha256": sha256_file(args.data), "examples": len(rows),
            "total_steps": steps, "checkpoint_steps": checkpoints, "bundle_commit": args.bundle_commit,
            "platform": platform_name(), "gpu": torch.cuda.get_device_name(accelerator.device),
            "libraries": library_versions(), "lr_scale": 1.0, "smoke": bool(args.smoke_steps)}
    start_step = 0

    if args.resume is not None:
        state = load_checkpoint(args.resume, accelerator, model, optimizer, scheduler, args.resume_sha256)

        if (state["data_sha256"], state["total_steps"], state["settings"]) != (meta["data_sha256"], steps, SETTINGS):
            raise SystemExit("STOP: the checkpoint was trained on other data or settings")

        start_step = state["step"]
        meta["lr_scale"] = state["lr_scale"]

    if args.lr_scale != 1.0:  # Amendment 1: after a non-finite loss, continue at half the learning rate
        meta["lr_scale"] *= args.lr_scale
        scheduler.base_lrs = [lr * args.lr_scale for lr in scheduler.base_lrs]

        for group, base, factor in zip(optimizer.param_groups, scheduler.base_lrs, scheduler.lr_lambdas):
            group["lr"] = base * factor(scheduler.last_epoch)

    run = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "start_step": start_step,
           "stop_step": stop_step, "resumed_from": str(args.resume) if args.resume else None,
           "resume_sha256": args.resume_sha256, "lr_scale_applied": args.lr_scale, "checkpoints_written": {}, **meta}
    log_path = args.out / "train-log.jsonl"
    args.out.mkdir(parents=True, exist_ok=True)

    def log(entry):
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def example(index: int):
        return encode(tokenizer, rows[index]) + (rows[index]["weight"],)

    def save(step: int, candidate: bool):
        name = checkpoint_name(step, candidate)
        digest = save_checkpoint(args.out / name, accelerator, model, optimizer, scheduler, step,
                                 {**meta, "candidate": candidate})

        if accelerator.is_main_process:
            removed = prune_resume_checkpoints(args.out, step)
            run["checkpoints_written"][name] = digest
            # The log names the latest checkpoint and its hash even if the session dies before run-*.json is written.
            log({"checkpoint": name, "step": step, "candidate": candidate, "state_sha256": digest, "removed": removed})
            print(f"{name} state.json sha256 {digest}", flush=True)

    if accelerator.is_main_process:
        log({"run_started": run["started"], "start_step": start_step, "stop_step": stop_step,
             "resumed_from": run["resumed_from"], "resume_sha256": args.resume_sha256, "lr_scale": meta["lr_scale"]})

    try:
        last = run_training(accelerator, model, optimizer, scheduler, example, training_order(len(rows)),
                            start_step=start_step, stop_step=stop_step, checkpoints=checkpoints, save=save,
                            resume_every=None if args.smoke_steps else RESUME_EVERY, log=log)
        run.update(outcome="completed", steps_reached=last)
        code = 0
    except NonFiniteLoss as error:
        run.update(outcome=f"stopped: {error}")
        code = 3

    if accelerator.is_main_process:
        run["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        name = f"run-steps-{start_step:04d}-{stop_step:04d}.json"
        (args.out / name).write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: run[k] for k in ("outcome", "start_step", "stop_step", "checkpoints_written")}, indent=2))

    return code


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
    fit = commands.add_parser("train", help="train up to a checkpoint, optionally resuming from one")
    fit.add_argument("--data", required=True, type=Path)
    fit.add_argument("--out", required=True, type=Path)
    fit.add_argument("--until-checkpoint", type=int, choices=(1, 2, 3, 4))
    fit.add_argument("--bundle-commit", required=True)
    fit.add_argument("--resume", type=Path)
    fit.add_argument("--resume-sha256", help="expected sha256 of the checkpoint's state.json")
    fit.add_argument("--lr-scale", type=float, default=1.0)
    fit.add_argument("--smoke-steps", type=int, help="GPU smoke check: this many steps, a checkpoint after each")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "pilot":
        return pilot(args)

    if args.command == "train":
        if args.resume is not None and args.resume_sha256 is None:
            parser.error("--resume needs --resume-sha256 (the state.json sha256 the earlier session printed)")

        if (args.until_checkpoint is None) == (args.smoke_steps is None):
            parser.error("give exactly one of --until-checkpoint and --smoke-steps")

        return train(args)

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
    "NonFiniteLoss",
    "RESUME_EVERY",
    "SETTINGS",
    "budget",
    "checkpoint_name",
    "checkpoint_steps",
    "cosine_schedule",
    "encode",
    "load_checkpoint",
    "load_rows",
    "prune_resume_checkpoints",
    "run_training",
    "save_checkpoint",
    "token_counts",
    "total_steps",
    "train_step",
    "training_order",
    "verify_checkpoint",
]
