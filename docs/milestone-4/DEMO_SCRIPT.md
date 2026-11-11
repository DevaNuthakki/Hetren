# Demo video script (Milestone 4, step 8)

About 3 minutes 10 seconds, recorded by the operator on the validation Mac (Intel i7-8850H, macOS) from these commands.
The video shows:
- a healthy run left alone;
- a mapping swap probed, then recovered and verified in the sandbox;
- a failure to abstain, with the held-out F6 result from the logged test runs;
- the offline Docker run with `--network none`;
- the GKE load test;
- the results at a glance.

**The three cases are tier 1 validation cases, approved by the operator on 2026-11-11.** No test case is run:
`sandbox_demo` refuses them, and the F6 numbers are quoted from the logged test results. The model calls are real
(Q4_K_M, `-t 6`) and are shown sped up, with an on-screen note saying so.

## Before recording

1. **Record after `v1.0.0` is published** (step 8.7), so that the Docker segment shows the release image. Its link
   goes into the release notes in step 8.8.
2. **One terminal, about 150 columns wide, with a large font.** The transcript's lines are up to about 200
   characters, so set the terminal to wrap long lines. Use a short prompt (`PS1='%# '`) and a dark theme.
3. **Nothing private on screen:** no tokens, `HF_TOKEN` unset, and no browser tabs with accounts open. The GKE
   screenshots should have the project ID and account email blurred.
4. **Fetch the model into the image's cache** (network on, once), and get the mapping swap's dataset line for the
   Docker segment:

   ```zsh
   cd ~/Documents/personal-projects/hetren
   unset HF_TOKEN
   docker pull ghcr.io/devanuthakki/hetren-cli:v1.0.0
   docker run --rm -v ~/.cache/hetren:/models ghcr.io/devanuthakki/hetren-cli:v1.0.0 fetch-model --repo Harsha1412/hetren-qwen3-4b-diagnosis --revision 3e875e4e8719acef839dc18e220a3ae498a1975b
   mkdir -p artifacts/milestone-4/demo/case-001478
   grep -m1 '"case_id":"case-001478"' artifacts/milestone-2/dataset-v2/hetren_visible.jsonl > artifacts/milestone-4/demo/case-001478/visible.jsonl
   ```

5. **The demo command, used three times below.** `DEMO` is a shell function, so each segment's line stays short
   on screen:

   ```zsh
   DEMO() { caffeinate -i ~/.hetren-pilot/bin/python -m packages.support_evaluator.sandbox_demo --case "$1" --gguf-dir artifacts/milestone-4/export-2/gguf-export --tokenizer artifacts/milestone-4/export-2/gguf-export/tokenizer --llama-cpp ~/hetren-tools/llama.cpp; }
   ```

6. **Rehearse each segment once.** Check that every case ends with `the logged Q4_K_M validation run: the same
   probes, recoveries, final action and verdict`. If one says `DIFFERENT`, stop and send the output: the video
   must not show a result that differs from the logged run without saying so.

## The segments

Times are the edited video's. The narration is a suggestion; the on-screen notes are required.

### 1. What Hetren is (0:00–0:15)

**Screen:** the repository's README title, or a title card.

**Narration:** "Hetren diagnoses failed runs of a support agent: it decides whether to leave a run alone, ask for
more evidence, propose a repair, or escalate. It was trained and tested on a synthetic support workflow, and
every label comes from executing repairs in a sandbox, never from a model."

### 2. A healthy run, left alone (0:15–0:45)

```zsh
DEMO case-000123
```

**On screen:** "Validation case. Model calls sped up; real time is shown in each line."

**What appears:**
- the run: `read_ticket`, `lookup_account` and `route_ticket` all succeeded. The ticket's customer reference
  `C-6835` differs from the account's `C-6557`;
- the model probes `find_owners(C-6835)`. The probe runs in a sandboxed fork and finds that no other account
  owns the reference, so nothing points to a swap. In this world the account was legitimately merged (the
  family line at the top says so; the model never sees it);
- the model decides `no_intervention`. The verdict is `CORRECT, exactly the label` (rule `outcome_correct`).

**Narration:** "This run looks suspicious: the ticket and the account name different customer references. The
model checks who owns the ticket's reference, finds that no other account does, and leaves the run alone. That
is right: the account was legitimately merged. Staying out of healthy runs matters as much as fixing broken
ones."

### 3. A mapping swap, probed and repaired (0:45–1:20)

```zsh
DEMO case-001478
```

**On screen:** the same note.

**What appears:**
- the run routed ticket `T-2072` to `Q-STANDARD`, through account `A-4465`, whose customer reference is
  `C-2118`, not the ticket's `C-3983`;
- the model probes `find_owners(C-3983)`, which returns `A-4512`;
- it proposes `set_mapping(C-3983 → A-4512)`;
- in a sandboxed fork, with the task re-run, the ticket goes to `Q-GOLD` through `A-4512`, and both checks turn
  true. The verdict is `CORRECT, exactly the label` (rule `smallest_verified_change`).

**Narration:** "Here the customer reference points at the wrong account, so the ticket went to the wrong queue.
The model finds the real owner and proposes remapping it. The sandbox applies the repair, re-runs the agent, and
the ticket now reaches the right queue. That check is what a label means here."

### 4. A failure to escalate (1:20–1:55)

```zsh
DEMO case-002332
```

**On screen:** the same note; then, over the verdict, "A known weakness, shown on a validation case."

**What appears:**
- `lookup_account` failed with "service unavailable";
- the model proposes `rerun` without probing. In the sandbox, the re-run leaves the ticket unrouted: the tool is
  still down;
- the label is `abstain` (rule `persistent_tool_error`): escalate to a human. The verdict is `WRONG`.

Then show the logged test results:

```zsh
grep -n "0.0% (0/400)\|0 of 44 abstain labels" docs/milestone-4/model-card.md
```

**On screen:** "Logged test results, not run here."

**Narration:** "When the right answer is to escalate, the model often retries instead: on validation runs like
this one, it re-ran 25 times out of 30 (the logged Q4_K_M validation run). On the held-out queue-misconfiguration family it never abstained, 0 of
400, and on live runs it never abstained either, 0 of 44. Those numbers come from the logged test runs, which are
never repeated. Don't rely on this model to escalate."

### 5. Offline, in Docker (1:55–2:25)

```zsh
docker run --rm --network none -v ~/.cache/hetren:/models:ro -v "$PWD/artifacts/milestone-4/demo/case-001478":/work:ro ghcr.io/devanuthakki/hetren-cli:v1.0.0 diagnose --compact /work/visible.jsonl
```

**On screen:** "No network. The CLI proposes; it never applies anything."

**What appears:** `Hetren diagnosis (proposed only; nothing was applied)`, then `Needs probe: find_owners
{"customer_ref": "C-3983"}`, with the note that offline diagnosis has no support environment to run the probe in.
Below that come the model line (Q4_K_M, the validated llama.cpp build), the validation result and the scope.

In validation, this case's first action was this probe. If the container's answer differs (another platform, or
a different number of threads), show what it printed and say so.

**Narration:** "The same mapping swap, through the released command-line tool, with the network switched off. On
its own, the tool can only read the evidence: it asks for the probe the sandbox ran a moment ago, and it never
changes anything."

### 6. On Kubernetes (2:25–2:45)

```zsh
python3 -c "import json; s=json.load(open('docs/milestone-4/loadtest-gke.json'))['k6']['steps_summary']; [print(k, v['concurrency'], 'users:', round(v['diagnoses_per_second'], 3), 'diagnoses/s, p50', round(v['latency_ms']['p50']/1000, 1), 's, rejected or failed', format(v['error_rate'], '.0%')) for k, v in sorted(s.items())]"
```

**Screen:** the output, then the GKE console screenshots (cluster, workloads, the two nodes during the scale-up).

**On screen:** "Cached best case: every request sent the same input, so the prompt cache was reused. A fresh
prompt takes about 150 s on these nodes."

At 16 users the line shows a p50 near 0 s and 98% rejected. Those are immediate "queue full" replies (each replica
takes 9 requests at a time), retried at once by that version of the load test; diagnoses stayed at 0.27 per
second. **On screen at that line:** "16 users: most requests turned away at once (queue full), not failed
diagnoses."

**Narration:** "On GKE, two replicas on two nodes level off at about 0.27 diagnoses per second. When the first
diagnosis loaded the CPU, the autoscaler added a node and a second replica was serving 171 seconds later. These
latencies are a best case: the test repeated one input, so the prompt cache did most of the work."

### 7. Results at a glance (2:45–2:58)

**Screen:** a title card with exactly these lines. The numbers are the model card's test results and GGUF
acceptance tables (`docs/milestone-4/model-card.md`); a test checks every one.

```text
Results at a glance: frozen protocol, each system ran once per test set

Decision accuracy           fine-tuned   GPT-4.1   untrained Qwen
Tier 1 in-distribution         73.8%       33.8%       30.4%
Tier 1 held-out families       41.5%       24.8%       14.3%
Tier 2 in-distribution         71.1%       17.6%       13.3%
Tier 2 held-out families       31.2%       19.2%       15.2%
Live gpt-4.1-mini runs         66.3%       28.0%       36.7%
More accurate than both on every set (paired bootstrap, 95%).

Wrong interventions on healthy runs: 0.0% vs GPT-4.1 33.0% (tier 1 in-distribution); 0.8% vs 31.4% (live)
but more on held-out families: 7.4% vs 0.0% (tier 1), 42.9% vs 10.7% (tier 2)
Rules v1, hand-written for the training faults, is more accurate on familiar faults: 99.5% vs 73.8% (tier 1), 84.4% vs 71.1% (tier 2)
Known failure: held-out queue misconfiguration, abstain recall 0.0% (0/400)
CPU export: Q4_K_M within the 2-point margin of fp16: -0.13 points pooled [-1.50, +1.25]
```

**Narration:** none, or one line: "Better than both model baselines on every test set; behind the hand-written
rules on the faults they were written for; and still not escalating when it should."

### 8. Close (2:58–3:10)

**Screen:** the links: the repository, the Hugging Face model and dataset, and the image.

**Narration:** "The model, the data with its frozen splits, the protocol and every log are public. The links are
below."

## Editing notes

- **Speed-ups:** model calls only (about 15–40 s each in real time), at a stated factor. The note stays on screen
  while a speed-up is in effect. Don't cut a call out entirely.
- **Never edit a verdict line,** and don't trim the `the logged Q4_K_M validation run: …` line.
- **Captions:** the narration as subtitles.
- **Credits:** none needed beyond the links; the data is CC BY 4.0, and the model and code are Apache-2.0.

## Rehearsal log

| date (UTC) | case | outcome |
|---|---|---|
| 2026-11-11 | `case-001478` | operator's real run, before this script: CPU i7-8850H, `-t 6`; llama-server ready in 4.1 s. Call 1 (37.3 s): `probe find_owners(C-3983)` → `A-4512`; call 2 (13.4 s): `set_mapping(C-3983 → A-4512)`. Sandbox: `Q-STANDARD`/`A-4465` (both checks false) → `Q-GOLD`/`A-4512` (both true). `CORRECT, exactly the label`; "the same probes, recoveries, final action and verdict" as the logged run |
