# Milestone 1: support agent loop

Moved here from the repository README (as of `4f1fcc1`) when the README was rewritten for the v1.0.0 release: the text is unchanged, with its headings one level up.


## What it demonstrates

A real tool-using agent, built on the OpenAI Agents SDK, routes synthetic customer-support tickets. In one example, its customer-to-account mapping has been quietly corrupted, so the agent routes a ticket to the wrong queue with full confidence. Hetren reads only the run's evidence, notices that the ticket and the account it resolved to name different customers, checks which mapping entries are wrong, and corrects only those entries through a permission-scoped action. It then re-runs the task. A separate verifier, which is the only component that knows the right answers, confirms the fix and checks that an unaffected ticket still routes correctly.

Hetren is equally expected to stay quiet when nothing is wrong, and to say "insufficient evidence" (naming what is missing) instead of guessing when part of the evidence is withheld.

## Architecture

```text
environments/support/              subject world: synthetic tickets, accounts, queues;
                                   plain tools; fault injection (leaves no marker)
packages/support_agent/            the agent definition and a scripted test model
packages/action_gateway/           generic tool wrapper: proposed -> authorized ->
                                   attempted -> observed, with before/after state hashes
packages/integrations/openai_agents/
                                   SDK hooks, local-only tracing, reconciliation of SDK
                                   evidence against gateway records, run records with
                                   provenance, exact-key capture/replay
packages/support_recovery/         Hetren: evidence sufficiency, rule-based diagnosis,
                                   read-only probes, frozen candidate, scoped correction
packages/support_evaluator/        evaluator only: faults, expected values, verdicts,
                                   recordings map, leakage scanner
packages/verification/support_verification.py
                                   the only importer of the evaluator; verifies frozen outcomes
packages/support_examples/         trusted harness that runs each example end to end
```

The boundaries are enforced by tests, not convention:

- **Import boundaries:** only the verifier may import the evaluator. The agent, environment tools, gateway, integration and Hetren's recovery code are checked statically, transitively, and in a fresh interpreter, and their source may not contain answer values.
- **Leakage scans:** every surface the agent or Hetren sees (prompts, tool outputs, stage records, traces, run records, diagnosis inputs, run IDs, capture files) is scanned for evaluator field names, fault and verdict words, and ticket-answer pairs.
- **Authority:** gateway stage records are authoritative for actions and state. Disagreements between SDK hooks or spans and the gateway are recorded as evidence, not resolved silently.
- **Permissions:** the correction tool is never given to the agent. Hetren's correction gateway allows only the exact calls in the frozen candidate, and every correction records a rollback reference.

## Running the tests and the offline demo

No API key is needed. All tests run offline, and the demo replays the committed live recordings with network access blocked:

```bash
python -m pytest -q
python -m packages.support_examples.demo
```

## Results

```text
Example                Runs                          Hetren outcome                                        Verdict
---------------------  ----------------------------  ----------------------------------------------------  -----------------------------
Correct run            run-0001                      healthy                                               no_intervention_correct
Insufficient evidence  run-0002                      insufficient_evidence (4 items missing)               insufficient_evidence_correct
Verified recovery      run-0003, run-0004, run-0005  mapping_inconsistency -> 2 mapping entries corrected  recovery_verified
```

CI replays all three examples from `tests/fixtures/support_captures` on every push. It checks the verdicts, replay provenance with a live source, `store: false`, zero SDK discrepancies, and identical results across two replays.

## Live recording facts

- **Model:** `gpt-4.1-mini-2025-04-14`, with `openai==3.42.0` and `openai-agents==0.24.0`.
- **Volume and cost:** 5 recorded runs, 20 model calls, 9,115 input and 442 output tokens, about $0.005 at list prices.
- **Provider storage:** `store=False` on every live call, enforced in code and recorded in each run manifest.
- **Tracing:** local only. The SDK's default exporter is replaced, and sensitive-data capture in spans is off.
- **Data:** synthetic fixture data only. Run IDs and capture file names are neutral, and the run-to-example mapping lives only on the evaluator side.
- **Recording:** recording requires an explicit `--confirm-live` flag and an API key. It is never run by tests or CI.

## Limitations

- **Synthetic data:** all tickets, accounts and queues are synthetic.
- **One fault family:** corrupted customer-to-account identifier mappings.
- **Rule-based diagnosis:** a learned model replaces it in Milestone 3.
- **One workflow:** read a ticket, look up the account, route the ticket.
- **One SDK:** the OpenAI Agents SDK only.
- **Small sample:** live behaviour is shown on five recorded runs. That demonstrates the loop end to end; it does not measure reliability.

## What's next

- **Milestone 2:** a dataset of varied, execution-labeled agent runs (multiple fault families, healthy cases including legitimate mismatches, held-out fault types) with a frozen evaluation protocol and measured baselines.
- **Milestone 3:** a learned diagnosis model, a small open model fine-tuned with LoRA, in place of the Milestone 1 rules, compared against the rule-based baseline and a general model on held-out faults.
- **Milestone 4:** deployment and packaging: CPU model serving, Kubernetes and Terraform infrastructure with load testing and teardown, plus a CLI, Docker image, and published model and dataset for others to use.

