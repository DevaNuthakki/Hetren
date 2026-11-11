# Hetren

Hetren diagnoses failed runs of a tool-using support agent. Given a run's recorded evidence, it decides whether
to leave the run alone, ask for one more piece of evidence, propose a repair, or escalate to a human. Every
label it was trained and tested on comes from **executing** repairs in a sandboxed copy of the agent's world,
never from a model.

> **Scope.** Everything here is built on one synthetic customer-support workflow (three tools: `read_ticket`,
> `lookup_account`, `route_ticket`) and its seven fault families. The released model is not a general
> agent-trace diagnoser, and outside that workflow its outputs are not meaningful. It proposes; it never applies
> anything. The command-line tool and API handle single-recovery (tier 1) runs only.

**What is in this repository:**
- the environment, the fault generator and the execution-based labeller;
- a frozen evaluation protocol with its splits;
- the baselines and the fine-tuned model's training and selection;
- a CPU export (GGUF) with its acceptance check;
- a command-line tool, an HTTP API and a Docker image;
- a Helm chart and Terraform for GKE, with a load test.

Every result is logged with the commit that produced it.

| | |
|---|---|
| Model | [`Harsha1412/hetren-qwen3-4b-diagnosis`](https://huggingface.co/Harsha1412/hetren-qwen3-4b-diagnosis) (Apache-2.0), revision `3e875e4e8719acef839dc18e220a3ae498a1975b` |
| Data | [`Harsha1412/hetren-support-runs`](https://huggingface.co/datasets/Harsha1412/hetren-support-runs) (CC BY 4.0): datasets, frozen splits, live test, protocol |
| Image | `ghcr.io/devanuthakki/hetren-cli:v1.0.0` (`linux/amd64`) |
| Protocol | [`docs/milestone-2/EVAL_PROTOCOL.md`](docs/milestone-2/EVAL_PROTOCOL.md), frozen 2026-11-02, with dated amendments |
| Report | `docs/TECHNICAL_REPORT.md` (to follow, with v1.0.0) |

## Results at a glance

The fine-tuned model is Qwen3-4B-Instruct-2507 with a QLoRA adapter (checkpoint 792), evaluated in fp16. Each
system ran once per test set under the frozen protocol. Rates are k / n, with Wilson 95% intervals in
[`docs/milestone-3/RESULTS.md`](docs/milestone-3/RESULTS.md).

**Decision accuracy** (the final action verified by execution):

| test set | cases | rules v1 | GPT-4.1 | Qwen untrained | **fine-tuned** |
|---|---|---|---|---|---|
| Tier 1 in-distribution | 560 | 99.5% | 33.8% | 30.4% | **73.8%** |
| Tier 1 held-out families | 960 | 45.7% | 24.8% | 14.3% | **41.5%** |
| Tier 2 in-distribution | 256 | 84.4% | 17.6% | 13.3% | **71.1%** |
| Tier 2 held-out families | 400 | 28.2% | 19.2% | 15.2% | **31.2%** |
| Live (`gpt-4.1-mini` agent runs) | 300 | 80.3% | 28.0% | 36.7% | **66.3%** |

**Wrong interventions on healthy runs** (lower is better):

| test set | healthy runs | rules v1 | GPT-4.1 | Qwen untrained | **fine-tuned** |
|---|---|---|---|---|---|
| Tier 1 in-distribution | 176 | 0.0% | 33.0% | 0.0% | **0.0%** |
| Tier 1 held-out families | 121 | 100.0% | 0.0% | 0.0% | **7.4%** |
| Tier 2 in-distribution | 45 | 2.2% | 51.1% | 0.0% | **4.4%** |
| Tier 2 held-out families | 56 | 92.9% | 10.7% | 0.0% | **42.9%** |
| Live | 121 | 24.8% | 31.4% | 0.0% | **0.8%** |

**What this shows** (paired bootstrap, 10,000 resamples; a claim needs the 95% interval to exclude zero):
- **Better than both model baselines:** the fine-tuned model is more accurate than GPT-4.1 and the untrained
  base on every set.
- **Below the rules on familiar faults:** the hand-written rules policy, built for the training families, is
  more accurate on four of the five sets. On tier 2 held-out the difference is not significant.
- **Restraint did not transfer to unseen families:** on tier 2 held-out it intervened on 42.9% of healthy runs.
  The untrained base intervenes on almost nothing, which is also why its accuracy is low.
- **It does not escalate when it should:** on the held-out `queue_misconfiguration` family, where the right answer
  is `abstain`, its abstain recall is **0.0% (0/400)**. On live runs it abstained on 0 of 44 abstain labels.
- **The CPU export holds:** Q4_K_M (2.5 GB, the default) matches fp16 within the predeclared 2-point margin.
  The pooled difference is −0.13 points [−1.50, +1.25] on the full validation split.

## Try it

### Docker (offline diagnosis)

The image is `linux/amd64` only and needs a CPU with **AVX2, FMA and F16C**. Fetch the model once, then
diagnose with the network off:

```sh
docker run --rm -v ~/.cache/hetren:/models ghcr.io/devanuthakki/hetren-cli:v1.0.0 \
  fetch-model --repo Harsha1412/hetren-qwen3-4b-diagnosis --revision 3e875e4e8719acef839dc18e220a3ae498a1975b
docker run --rm --network none -v ~/.cache/hetren:/models:ro -v "$PWD":/work:ro \
  ghcr.io/devanuthakki/hetren-cli:v1.0.0 diagnose --compact /work/tests/fixtures/hetren_cli/compact_first_step.json
```

`fetch-model` checks every file's sha256 against the export manifest. `diagnose` accepts:
- a run recorded with Hetren's OpenAI Agents SDK integration (`--record`, an `AgentRunRecord`);
- its compact evidence (`--compact`), or one line of the dataset's `hetren_visible.jsonl`.

An SDK trace export is rejected, because it lacks the gateway records the model reads. The output is a decision,
a **proposed** recovery, or the probe the model would need; `--format json` adds the full provenance.

### From source

```sh
python3 -m venv ~/.hetren-cli && ~/.hetren-cli/bin/pip install -r requirements-cli.txt
~/.hetren-cli/bin/python -m packages.hetren_cli fetch-model --repo Harsha1412/hetren-qwen3-4b-diagnosis --revision 3e875e4e8719acef839dc18e220a3ae498a1975b
~/.hetren-cli/bin/python -m packages.hetren_cli diagnose --compact tests/fixtures/hetren_cli/compact_first_step.json --llama-server <path to llama-server>
```

`llama-server` must be llama.cpp at commit `620d2225c` (build 11669), the validated build. The report says
whether the build in use is the validated one.

### The HTTP API and Kubernetes

`hetren serve` exposes `POST /diagnose`, with `/healthz`, `/readyz` and `/metrics`. It runs one diagnosis at a
time with a bounded queue. The Helm chart, the Terraform stacks and the load test are in
[`deploy/`](deploy/README.md).

### The full episode, in the sandbox

The CLI only reads evidence. The full loop is evaluator-side and runs from the repository:
- probes executed in a sandboxed fork;
- the proposed repair applied and the agent re-run;
- the result checked by execution.

It accepts validation cases only, and refuses every test case:

```sh
python -m packages.support_evaluator.sandbox_demo --case case-001478 --gguf-dir <dir> --tokenizer <dir> --llama-cpp <checkout>
```

The demo video's script is [`docs/milestone-4/DEMO_SCRIPT.md`](docs/milestone-4/DEMO_SCRIPT.md).

## How it works

```text
agent run (OpenAI Agents SDK)  ->  gateway records: every tool call, allowed or denied, its observation, state change
        ->  compact evidence (the model's input)  ->  one action per step: decide | probe | recover
evaluation only:  probes run in a sandboxed fork;  a recovery is applied, the task re-run, and verified
```

- **The environment** (`environments/support/`): synthetic tickets, accounts and queues, and seven fault families.
  - Five are used in training: mapping swap, stale account record, mishandled tool error, misleading ticket
    text, missing account.
  - Two are held out for testing only: queue misconfiguration and tier format drift.
  - There are also healthy look-alikes: a legitimately merged account, a recent tier change, and a transient
    error that was retried.
- **Labels** (`packages/support_evaluator/`): fixed rules, applied in order. A recovery label is the smallest
  recovery that passes verification in a sandboxed fork, including regression checks on other tickets. A probe
  sequence is sufficient when every world still consistent with its observations has the same verified outcome.
- **Isolation:** only the evaluator knows the answers. Tests enforce import boundaries, leakage scans and
  scoped permissions, so the agent, the environment's tools and the diagnoser cannot reach them.
- **The protocol:** splits by world seed, fault family and agent source. Test splits were used once per system,
  and every change after the freeze is a dated amendment.

## Milestones

| milestone | what it added | record |
|---|---|---|
| 1 | the support agent loop: a real SDK agent, the action gateway, a rule-based diagnosis and a verified repair, replayed offline in CI | [`docs/milestone-1/`](docs/milestone-1/README.md) |
| 2 | datasets v2 (tier 1) and v3 (tier 2), splits, a live test of 300 `gpt-4.1-mini` runs, the frozen protocol and three baselines | [`docs/milestone-2/`](docs/milestone-2/RESULTS.md) |
| 3 | QLoRA fine-tuning of Qwen3-4B, checkpoint selection on validation, the test runs | [`docs/milestone-3/RESULTS.md`](docs/milestone-3/RESULTS.md) |
| 4 | the GGUF export and its acceptance, the CLI, API and image, Kubernetes and Terraform, the Hugging Face release | [`docs/milestone-4/`](docs/milestone-4/PLAN.md) |

## Deployment, measured

One session on GKE (Free Trial), on 1–2 `e2-standard-4` nodes with the HPA and cluster autoscaler, ran the k6
load test against two replicas ([`docs/milestone-4/DEPLOY_LOG.md`](docs/milestone-4/DEPLOY_LOG.md)):
- **The first diagnosis on GKE** took 162 s: a fresh 1,744-token prompt on 2 cores.
- **The scale-up:** the HPA rescaled during that diagnosis, and the second replica was serving 171 s later,
  on a new node.
- **Throughput** levelled off at about 0.27 diagnoses per second with two replicas.

**These load-test latencies are a cached best case:** every request sent the same input, so llama-server's
prompt cache did most of the work (about 8 s per diagnosis against about 150 s fresh). The load test now sends 16
distinct inputs, for any future run.

The session cost an estimated $2.27 in Free Trial credits. The cluster stayed up overnight before its teardown,
against $0.48 had it been torn down at once. The billing report will confirm the figure.

## Reproducing

- **Datasets and splits:** regenerated bit for bit by the commands in each manifest's `regenerate` field
  (`docs/milestone-2/*.manifest.json`); CI's slow job re-labels samples and checks the hashes.
- **Baselines and test runs:** `docs/milestone-2/TEST_RUN_LOG.md` (runs #1–#6, never repeated).
- **Training and selection:** `docs/milestone-3/VALIDATION_LOG.md`, and the notebooks in `notebooks/milestone-3/`.
- **The CPU export and its validation:** `docs/milestone-4/EXPORT_LOG.md` and `docs/milestone-4/EXPORT_RUNBOOK.md`.
- **The GKE session:** `docs/milestone-4/DEPLOY_RUNBOOK.md`.

Tests: `python -m pytest -q -m "not slow"` (Python 3.12, `pip install -r requirements-dev.txt`).

## Limitations

- **Synthetic and narrow:** one workflow, three tools, seven fault families. Scripted agents produce all
  non-live runs.
- **Escalation:** the model rarely abstains when it should (above).
- **Held-out families:** both accuracy and restraint drop sharply.
- **Tier 1 only in the tools:** the model was validated on two-step recovery, but no released tool supports it.
- **Live regression checks:** label confirmation re-ran only the target ticket live. Regression checks relied
  on scripted proxies.
- **A retiring baseline:** `gpt-4.1` and `gpt-4.1-mini` leave the API on 2027-01-14. Their logged results
  stand, but cannot be re-run.
- **One platform for the GGUF check:** the acceptance run was on one Mac's CPU. In the Docker image, on the 20
  pilot cases, Q4_K_M took the same episode as the Mac on 18 of 20. The other two took one extra probe and
  reached the same decision. Q8_0 matched on 20 of 20 ([`EXPORT_LOG.md`](docs/milestone-4/EXPORT_LOG.md),
  "Linux checks"). Other CPUs are untested.
- **Performance is descriptive:** the GKE numbers describe one session on small nodes, at 2 threads rather
  than the validated 6.

## Licence and citation

Code and model: Apache-2.0 ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE)). Data: CC BY 4.0.

```bibtex
@misc{hetren2026,
  title  = {Hetren: execution-labelled diagnosis of a synthetic support agent},
  author = {Nuthakki, Deva Harsha},
  year   = {2026},
  url    = {https://github.com/DevaNuthakki/Hetren}
}
```

## Earlier work in this repository

The repository began as a deterministic portfolio slice: a diagnosis, bounded repair, evaluation and
verification lifecycle with explicit claim limits (`PASS != VERIFIED`, `VERIFIED != ELIGIBLE`). It still runs:
`python -m packages.portfolio_demo`. Its description, claim limits and design notes are in
[`docs/portfolio/`](docs/portfolio/README.md), and the historical working material is on the
`archive/sept-2026-evidence` branch. The earlier qualification
system under `tests/qualification` is script-driven, with its `scripts/check_*` validators. Historical evidence
snapshots under `docs/decisions/` are preserved as they were.
