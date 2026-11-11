---
license: cc-by-4.0
language:
  - en
pretty_name: Hetren support-agent runs (synthetic, execution-labelled)
size_categories:
  - 10K<n<100K
task_categories:
  - text-classification
tags:
  - agents
  - agent-diagnosis
  - synthetic-data
  - evaluation
configs:
  - config_name: tier1
    data_files: dataset-v2/hetren_visible.jsonl
  - config_name: tier2
    data_files: dataset-v3/hetren_visible.jsonl
  - config_name: live
    data_files: live-test-v1/hetren_visible_final.jsonl
---

# Hetren support-agent runs

Recorded runs of a **synthetic customer-support agent**, each labelled with what a diagnoser should do about
it: leave it alone, probe for more evidence, propose a recovery, or escalate. **The labels come from executing
recoveries in a simulated environment, never from a model.** These are the training, validation and test data
of the [Hetren project](https://github.com/DevaNuthakki/Hetren), published with its frozen splits and its
evaluation protocol, so that every reported result can be checked.

The model trained on it is
[`Harsha1412/hetren-qwen3-4b-diagnosis`](https://huggingface.co/Harsha1412/hetren-qwen3-4b-diagnosis).

> **Scope.** Everything here is synthetic: the companies, accounts, tickets and customers are generated, and the
> world is a small support workflow with three tools (`read_ticket`, `lookup_account`, `route_ticket`). It is a
> benchmark for diagnosing that workflow, not a sample of real support traffic or of agent traces in general.

## What a run is

A world holds accounts, customer references, queues and tickets. An agent handles one ticket: it reads it,
looks up the account and routes it to a queue. Some worlds contain a fault that makes a plausible agent route
the ticket wrongly. The protocol's seven fault families:

| ID | family | role |
|---|---|---|
| F1 | customer-to-account mapping swap | train / validation / test |
| F2 | stale account record | train / validation / test |
| F3 | mishandled tool error | train / validation / test |
| F4 | misleading ticket text | train / validation / test |
| F5 | missing account | train / validation / test |
| F6 | queue misconfiguration | **held out: test only** |
| F7 | tier format drift | **held out: test only** |

The remaining worlds are healthy look-alikes, labelled `no_intervention`: a legitimately merged account, a
recent tier change, and a transient tool error that the agent retried successfully.

A diagnoser sees the run's **compact evidence**: the task, each tool call with its arguments, outcome and
observation, the run's status, and the results of any probes it asked for. It answers with one action per
step: a decision (`no_intervention`, `insufficient_evidence` or `abstain`), a recovery (for example
`restore_from_source` or `reroute`), or a probe. Tier 1 runs need at most one recovery; tier 2 runs (dataset v3)
can need a sequence of two.

## How the labels are made

From the protocol (`protocol/EVAL_PROTOCOL.md`, "Labels"):

> Labels come from execution, never from a model. A recovery label is a recovery that, applied in a sandboxed
> copy of the world and followed by re-running the task, passes verification, including regression checks on
> unaffected tickets. Probe labels come from simple counterfactual enumeration: a probe sequence is sufficient
> when every candidate world consistent with its observations has the same verified outcome.

Labels are per run, not per world. A run whose outcome is already correct is `no_intervention`, whatever
faults its world contains. The labeller applies fixed rules in order: `unexplained_absence` gives
`insufficient_evidence`; `outcome_correct` gives `no_intervention`; `persistent_tool_error` gives `abstain`
unless a re-run verifies; otherwise `smallest_verified_change` (tier 2: `shortest_verified_sequence`), or
`abstain` when nothing verifies. Each case records the rule that produced its label.

**Contrast partners.** Many primary cases have *partner* records. A partner is a counterfactual variant on the
same base world and ticket, consistent with the same opening evidence, but with a different label: one partner
per distinct label. The partners teach the probes that tell such cases apart. Each partner shares its primary's
`twin_group_id` and is always in the same split.

## Repository layout

| path | what |
|---|---|
| `dataset-v2/` | **tier 1**, seed 2026: 4,800 primary cases and 5,239 partners (10,039 records, 20,500 steps) |
| `dataset-v3/` | **tier 2**, seed 2028: 2,040 primary cases and 6,358 partners (8,398 records, 31,365 steps) |
| `…/hetren_visible.jsonl` | what a diagnoser may see: per case, its steps, each with `input` (compact evidence) and `target` (the labelled action) |
| `…/evaluator/cases.jsonl` | the evaluator's side: the plan (family, variant, agent behaviour, seeds), the truth (expected account and queue, the remedy, regression tickets), the label rule and twin group |
| `…/evaluator/tags.jsonl` | slice tags per primary case (held out, compound, distractors, first input tokens) |
| `…/evaluator/labeling_time.jsonl` | seconds the labeller took per case |
| `splits-v1/`, `splits-v2/` | the frozen splits of datasets v2 and v3: case-ID lists for `train`, `validation`, `test_in_distribution` and `test_held_out`, and `dropped.tsv` with a reason per dropped record |
| `live-test-v1/` | **live test**: 300 runs of a `gpt-4.1-mini-2025-04-14` agent on fresh worlds (seed 2027) |
| `live-test-v1/hetren_visible_final.jsonl` | the live runs' visible steps and labels |
| `live-test-v1/specs/` | what the recording script saw: the world and the ticket, per run |
| `live-test-v1/captures/` | the model's recorded outputs, call by call, replayed exactly to rebuild each run |
| `live-test-v1/confirm/`, `confirm-captures/` | the 120 live label confirmations and their captures |
| `live-test-v1/evaluator/` | the hidden plan, the final labels with their category, and the confirmation results |
| `training/` | the manifests of the fine-tuning file built from the train splits (counts per tier, step kind and verb; its sha256) and of its budget |
| `protocol/` | the evaluation protocol as frozen, with its amendments, and its sha256 |
| `manifests/` | the committed manifests of both datasets, both splits and the live test, with each file's sha256 and the command that regenerates it |
| `LICENSE` | CC BY 4.0 |
| `SHA256SUMS` | the sha256 of every other file in this repository |

All files are UTF-8 JSON Lines or plain text; nothing is compressed or converted. The bytes are exactly the
ones the project's results were computed from. Every hash matches the manifests committed in the Hetren
repository at commit `<commit>`, and the copies in `manifests/` are those files.

## Splits

Splits are by world seed, fault family and agent source:
- scripted agents produce `train`, `validation` and the two test splits;
- live runs form a separate test set;
- F6 and F7 appear only in `test_held_out`, never in training or validation, not even as contrast partners.

| split | dataset v2 (tier 1) | dataset v3 (tier 2) | use |
|---|---|---|---|
| `train` | 5,195 | 3,468 | training |
| `validation` | 1,028 | 757 | checkpoint selection and baselines |
| `test_in_distribution` | 1,074 | 773 | final evaluation only |
| `test_held_out` (F6, F7) | 1,908 | 1,608 | final evaluation only |
| live test | 300 runs | | final evaluation only |

The counts are records, primary cases and their partners together. The remaining records are listed in
`dropped.tsv`, with a reason each:
- "held-out partner outside test_held_out" (822 in v2, 1,788 in v3): an F6 or F7 partner of a training-family case;
- "seed reserved for held-out" (12 and 4): a case on a world seed reserved for held-out cases.

The viewer shows each dataset whole; to work with a split, filter by its list:

```python
from datasets import load_dataset
from huggingface_hub import hf_hub_download

tier1 = load_dataset("<this repository>", "tier1", split="train")
ids = set(open(hf_hub_download("<this repository>", "splits-v1/validation.txt", repo_type="dataset")).read().split())
validation = tier1.filter(lambda row: row["case_id"] in ids)
```

(The viewer's single split is named `train` by the library; it is the whole dataset, not the train split.)

## The test labels are public, deliberately

This repository includes the labels of every test split. The test runs reported for the project are done:
each system ran once per test set under the frozen protocol, and the results are logged. Publishing the labels
lets anyone recompute those results.

It also means **these test splits can no longer serve as a blind test**. Nothing is lost that was not already
public: the generator, the labeller, the seeds and the split lists are all in the Hetren repository, so anyone
could regenerate the test sets. A future held-out evaluation will use new, unpublished seeds and a new protocol
amendment.

## The live test

The live runs were recorded with the OpenAI Responses API, model `gpt-4.1-mini-2025-04-14`, with `store=False`,
at most 300 output tokens per call and 10 turns per run, by `scripts/record_live_test.py`. The total spend
was $0.3309, recording and confirmation together.
- **The captures** hold the model's output items (function calls with their arguments) and token usage. They
  also hold OpenAI's per-item IDs (`fc_…`, `call_…`), but no response ID, organisation, project, key or header.
- **How live runs are labelled:** each run is replayed from its captures on its world and labelled by the same
  labeller. Where the label needs an agent to re-run, the scripted behaviours whose evidence matches the live
  run stand in for it.
- **The label categories:** 277 runs are proxy-matched, 17 final-label-only and 6 live-confirmed (the target
  ticket was re-run live after the recovery); none are excluded. The categories are defined in the protocol's
  "Live test split" section.
- **Confirmation:** 120 recovery labels were re-run live once; all 120 were confirmed.

## Intended use

- Training and evaluating diagnosers for this workflow, and reproducing the Hetren results.
- Studying execution-based labelling, held-out-family generalisation, and when a diagnoser should abstain.

**Out of scope:** real customer-support decisions, and any claim about agent traces outside this synthetic
workflow.

## Limitations

- **Synthetic and narrow.** One workflow, three tools, seven fault families. Scripted agent behaviours produce
  all non-live runs.
- **Probe labels are short.** Probe sequences are found by enumerating a fixed hypothesis set; the protocol
  records the known limitations ("Known limitation: short probe sequences", "no partial fix and escalate").
- **Live regression checks were not run live.** Confirmation re-ran only the target ticket; regression checks on
  other tickets relied on scripted proxies.
- **Recorded with a model that is being retired.** `gpt-4.1-mini-2025-04-14` leaves the API on 2027-01-14. The
  captures replay without it, but new live runs with the same model will not be possible.

## Reproducing the data

Each dataset and split can be regenerated bit for bit from the Hetren repository. For dataset v2 and its
splits v1:

```sh
python -m packages.support_evaluator.dataset --out <dataset dir> --per-cell 96 --seed 2026 --withheld-per-cell 16 --processes <n>
python -m packages.support_evaluator.splits --dataset <dataset dir> --out <splits dir> --seed 2026 --validation-fraction 0.15 --test-fraction 0.15
```

The exact commands are in each manifest's `regenerate` field. The live runs cannot be regenerated without the
API; their captures are what make them replayable.

## Licence

The data is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): you may share and adapt it,
with credit. The Hetren code that generates and labels it is licensed separately, under Apache-2.0.

## Citation

```bibtex
@misc{hetren2026,
  title  = {Hetren: execution-labelled diagnosis of a synthetic support agent},
  author = {Nuthakki, Deva Harsha},
  year   = {2026},
  url    = {https://github.com/DevaNuthakki/Hetren}
}
```
