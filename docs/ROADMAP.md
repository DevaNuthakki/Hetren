# Roadmap

> **Planned, not done.** Nothing on this page exists yet unless it is described under "Today". There are no
> dates. Any item that touches the evaluation needs a dated protocol amendment first, and the frozen test splits
> are never run again.

Each item says what Hetren does today, with the file that shows it, and what is planned.

## Near term (v1.0.x)

- **Dependency upgrades.**
  - **Today:** the image pins `transformers` 4.56.2 and `fsspec` 2025.12.0 (`requirements-cli.txt`). Both have
    open advisories, none of them reachable in Hetren's use (`docs/RELEASE_NOTES.md`, "Known limitations").
  - **Planned:**
    - `fsspec` 2026.6.0 on its own;
    - `transformers` 5.x, accepted only if the token-parity check (`packages/support_evaluator/gguf_parity.py`)
      and the CLI agreement checks (`packages/support_evaluator/cli_check.py`, `linux_agreement.py`) pass
      again on the new version.
- **A realistic, non-cached load test.**
  - **Today:** the one GKE session repeated a single input, so its latencies are a cached best case: about 8 s
    per diagnosis, against about 150 s for a fresh prompt (`docs/milestone-4/DEPLOY_LOG.md`). The load test now
    ships 16 distinct inputs, taken from training examples only (`deploy/loadtest/inputs.json`), but no session
    has run with them.
  - **Planned:** a session with those inputs, reporting fresh-prompt latency and throughput.
- **An arm64 (Apple Silicon) image.**
  - **Today:** CI builds and publishes `linux/amd64` only (`.github/workflows/ci.yml`), and the image needs AVX2,
    FMA and F16C.
  - **Planned:** a `linux/arm64` build, accepted on its own agreement check, like the amd64 image's.
- **A pip-installable package.**
  - **Today:** there is no `pyproject.toml`. The code runs from a checkout under the top-level namespace
    `packages` (`python -m packages.hetren_cli`).
  - **Planned:** rename that namespace to a distinct package name, then publish the CLI as a package.
- **A Hugging Face Space demo of the example cases.**
  - **Today:** the example is `examples/v2-case-001478.jsonl`, and the demo runs locally
    (`packages/support_evaluator/sandbox_demo.py`, validation cases only).
  - **Planned:** a Space that runs the released model on validation example cases. Test cases are never shown.

## The model

- **Fixing escalation.**
  - **Today:** this is the main failure. On the held-out queue-misconfiguration family, abstain recall is 0.0%
    (0/400), and on live runs 0 of 44 abstain labels (`docs/milestone-4/model-card.md`). The checkpoint
    selection score is S = ½(A₁ + A₂) − W, and abstain recall is monitored but never used for the choice
    (`docs/milestone-2/EVAL_PROTOCOL.md`, Amendment 1). The model outputs one action, with no confidence.
  - **Planned:**
    - targeted training data for `abstain`;
    - abstain recall as part of the selection score;
    - calibrated uncertainty, so that a low-confidence case can be escalated.
- **Two-step (tier 2) recovery in the CLI and API.**
  - **Today:** the model was trained and tested on tier 2, but the CLI rejects `compact-evidence-v2` inputs and
    diagnoses a run's first step only (`packages/hetren_cli/inputs.py`).
  - **Planned:** tier 2 inputs in the CLI and API, still proposing only.
- **The contrast-partner ablation.**
  - **Today:** training used primaries and their contrast partners together. A comparison with and without
    partners "is a possible later experiment and needs its own amendment" (`EVAL_PROTOCOL.md`, Amendment 1), and
    it was not tested (`docs/milestone-3/RESULTS.md`).
  - **Planned:** that comparison, on validation and on a fresh test set (below).
- **Other small open models.**
  - **Today:** the comparisons are rules v1, GPT-4.1 and untrained Qwen3-4B (`docs/milestone-3/RESULTS.md`).
  - **Planned:** fine-tuning and comparing other small open models under the same protocol.
- **Reinforcement learning with the execution verifier as the reward.**
  - **Today:** training is supervised: QLoRA, with the loss on the target action's tokens (Amendment 1). The
    verifier exists, but only as the labeller and the evaluator: it applies recoveries in a sandboxed fork and
    re-runs the task (`packages/support_evaluator/`).
  - **Planned:** using that verified outcome as the reward signal.

## Evaluation

- **A fresh held-out test set.**
  - **Today:** every test split's labels are public, so they can no longer serve as a blind test
    (`docs/milestone-4/dataset-card.md`).
  - **Planned:** new, unpublished seeds under a new protocol amendment, as the dataset card states.
- **More fault families.**
  - **Today:** there are seven, five for training and two held out (`environments/support/`).
  - **Planned:** new families, including new held-out ones.
- **A new live test set.**
  - **Today:** the live test was recorded with `gpt-4.1-mini-2025-04-14`, which leaves the API on 2027-01-14.
    Its captures replay without it, but no new run with that model will be possible
    (`docs/milestone-4/dataset-card.md`).
  - **Planned:** a live test set recorded with a current model.

## Real-world use

- **Workflows and tools beyond the support workflow.**
  - **Today:** the CLI accepts runs of the three support tools only (`SUPPORT_TOOLS` in
    `packages/hetren_cli/inputs.py`), and it rejects SDK trace exports.
  - **Planned:** recording runs, and making labels, for other workflows and tools.
- **Adapters for other agent frameworks.**
  - **Today:** runs are recorded with the OpenAI Agents SDK only (`packages/integrations/openai_agents/`).
  - **Planned:** recorders for other frameworks that produce the same evidence.
- **A human-in-the-loop approval step.**
  - **Today:** the CLI and API apply nothing. Recoveries are applied only in sandboxed forks, by the evaluator.
    The action gateway (`packages/action_gateway/`) already records every tool call as proposed, authorised,
    attempted and observed, under a policy.
  - **Planned:** a step where a person approves a verified recovery, which the gateway then applies.
- **Monitoring dashboards.**
  - **Today:** the API serves Prometheus metrics at `/metrics` (`packages/hetren_cli/api.py`): diagnoses,
    rejections, HTTP responses, request and generation time. The deployment ships no dashboard, and the GKE
    stack leaves managed Prometheus off (`deploy/terraform/gke/cluster.tf`).
  - **Planned:** dashboards built on those metrics.

## Research

- **An open benchmark for agent-failure diagnosis.**
  - **Today:** the protocol, datasets and splits are public under CC BY 4.0 (`docs/milestone-4/dataset-card.md`).
  - **Planned:** publish them as a benchmark, with a blind test set (the fresh held-out set above) and a way to
    submit results for scoring.
