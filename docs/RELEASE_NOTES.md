# Hetren v1.0.0

The first release of Hetren: a diagnosis model for a tool-using support agent's recorded runs, with its data,
evaluation protocol, command-line tool, HTTP API, Docker image and deployment code.

Given a run's recorded evidence, the model decides whether to leave the run alone, ask for a probe, propose a
recovery, or escalate to a human. Every label it was trained and tested on comes from executing recoveries in a
sandboxed copy of the agent's world.

> **Scope.** One synthetic customer-support workflow (`read_ticket`, `lookup_account`, `route_ticket`) and its
> seven fault families. The model is not a general agent-trace diagnoser, and outside that workflow its outputs
> are not meaningful. The CLI and API handle single-recovery (tier 1) runs only, and they propose; they never
> apply anything.

## Results at a glance

The fine-tuned Qwen3-4B (checkpoint 792), in fp16, on the frozen test sets. Each system ran once per test set.

| test set | fine-tuned | GPT-4.1 | Qwen untrained | rules v1 |
|---|---|---|---|---|
| Tier 1 in-distribution, accuracy | 73.8% | 33.8% | 30.4% | 99.5% |
| Tier 1 held-out families, accuracy | 41.5% | 24.8% | 14.3% | 45.7% |
| Tier 2 in-distribution, accuracy | 71.1% | 17.6% | 13.3% | 84.4% |
| Tier 2 held-out families, accuracy | 31.2% | 19.2% | 15.2% | 28.2% |
| Live (`gpt-4.1-mini` runs), accuracy | 66.3% | 28.0% | 36.7% | 80.3% |

- **Against the model baselines:** more accurate than GPT-4.1 and the untrained base on every set (paired
  bootstrap, 95%).
- **Against the hand-written rules:** behind them on four of the five sets, the faults they were written for.
- **Wrong interventions on healthy runs:** 0.0% against GPT-4.1's 33.0% in tier 1 in-distribution, and 0.8%
  against 31.4% live. But on held-out families it intervenes more: 7.4% against 0.0% in tier 1, and 42.9% against
  10.7% in tier 2.
- **Escalation:** on the held-out queue-misconfiguration family, its abstain recall is 0.0% (0/400).
- **The CPU export:** Q4_K_M is within the predeclared 2-point margin of fp16, at −0.13 points pooled
  [−1.50, +1.25].

## Get it

| | |
|---|---|
| Image | `ghcr.io/devanuthakki/hetren-cli:v1.0.0@sha256:efafa907ab9cd6c87965fc8c00d8818c70e49faa869ee3e15f6f9d21f60e2bc0` (`linux/amd64`; the CPU needs AVX2, FMA and F16C) |
| Model | [`Harsha1412/hetren-qwen3-4b-diagnosis`](https://huggingface.co/Harsha1412/hetren-qwen3-4b-diagnosis), revision `3e875e4e8719acef839dc18e220a3ae498a1975b` (Apache-2.0) |
| Data | [`Harsha1412/hetren-support-runs`](https://huggingface.co/datasets/Harsha1412/hetren-support-runs), revision `10942d316e0c1c9b3c3cb46915f971eed66ad7b4` (CC BY 4.0) |
| Technical report | [`docs/TECHNICAL_REPORT.md`](https://github.com/DevaNuthakki/Hetren/blob/v1.0.0/docs/TECHNICAL_REPORT.md), and the PDF attached to this release |
| Demo video | to follow |

```sh
IMAGE=ghcr.io/devanuthakki/hetren-cli:v1.0.0@sha256:efafa907ab9cd6c87965fc8c00d8818c70e49faa869ee3e15f6f9d21f60e2bc0
docker run --rm -v ~/.cache/hetren:/models "$IMAGE" fetch-model --repo Harsha1412/hetren-qwen3-4b-diagnosis
docker run --rm --network none -v ~/.cache/hetren:/models:ro -v "$PWD":/work:ro "$IMAGE" diagnose --record /work/run.json
```

`fetch-model` downloads the released revision by default, and checks every file against the export manifest.

## Checksums

| file | sha256 |
|---|---|
| `export.manifest.json` (pins every model file) | `4a2431a46a31045d74bf48da291fcbf09692a794e58d66d7135ede1cdc433ee0` |
| `hetren-qwen3-4b-ckpt0792-q4_k_m.gguf` (default) | `e3f50ba98ee7e800554dec7ec1c403e7f1d47d4595300e6a6a3e8bf7ffe8763e` |
| `hetren-qwen3-4b-ckpt0792-q8_0.gguf` | `496c74a750ef32d0c52dd9644e51b36547dda762c498ac89eece1a24bab3ba29` |
| image `hetren-cli:v1.0.0` | `efafa907ab9cd6c87965fc8c00d8818c70e49faa869ee3e15f6f9d21f60e2bc0` |
| `TECHNICAL_REPORT.pdf` (attached) | `bd2baabcd8d8681027f640fd469a02e8d3c9beca44f84109ffa64a00b2dac77d` |

## Known limitations

- **Escalation:** the model rarely abstains when it should. On F6 (held-out queue misconfiguration) it never
  did, 0/400, and on live runs it abstained on 0 of 44 abstain labels.
- **Held-out families:** both accuracy and restraint drop.
- **Tier 1 only in the tools:** the model was validated on two-step recovery, but no released tool supports it.
- **One validation platform for the GGUF:** the acceptance run was on one Mac's CPU. In the Linux image, Q4_K_M
  took the same episode on 18 of 20 pilot cases.
- **Performance is descriptive:** one GKE session, on small nodes and at 2 threads, with load-test latencies that
  are a cached best case. The session cost $3.79 gross, all paid by Free Trial credits.
- **Retiring baselines:** `gpt-4.1` and `gpt-4.1-mini` leave the API on 2027-01-14. Their logged results stand,
  but cannot be re-run.

## Provenance

- **The tags:** annotated tag `v1.0.0` (with `milestone-4` on the same commit) on
  `679c131c143a8583d5ac1bab133f7f3584ac9a45`, the merge of pull request #92.
- **The image:** CI run #244 published it, after its tag check (`CLI_VERSION 1.0.0, chart appVersion 1.0.0`)
  and image checks.
- **The PDF:** a layout-only rebuild of the report as tagged. Its table column widths, ragged-right text and
  headings kept with the text that follows changed; no word or number did. It was built on `release/v1.0.0-docs`
  with the same pinned pandoc and Typst image, and it is reproducible: `scripts/build_report_pdf.sh` gives these
  exact bytes (sha256 `bd2baabcd8d8…`) from any commit with the same report and layout files. The commit and CI run
  it was taken from: recorded after the build. The tag run's own PDF (`e3476fc7a9d0…`) is not attached.
- **The protocol:** frozen on 2026-11-02, with dated amendments. The results are in `docs/milestone-3/RESULTS.md`
  and `docs/milestone-4/EXPORT_LOG.md`.
