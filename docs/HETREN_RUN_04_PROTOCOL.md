# Hetren Run-04: Renamed Ground-Truth Protocol

Status: preregistration only. No ASR execution, qualification, certification,
production approval, or release authority is granted by this document.

## Purpose

Run-04 creates a clean, replayable Hetren baseline before AssuranceRank,
Behavioral Response Field, HCAS, or any other adaptive algorithm is tested.
It answers whether the evidence pipeline, fresh corpus, evaluators, holdout
firewall, and simple selector baselines can be trusted. It does not try to
prove that a Hetren algorithm beats those baselines.

The exact machine-readable protocol is built by
`hvee.packs.asr.run04_protocol`. Its canonical SHA-256 is the authority; this
document explains the design in human-readable form.

## Historical evidence boundary

Two existing bodies of evidence remain immutable calibration inputs:

- B11H: 32 cases per model, two models, three fresh processes, and 192 real
  transcriptions. It established same-host process reproducibility only.
- Brutal v1: the frozen 13-case, two-model full-chain workflow. A replay under
  Hetren naming is a renamed control only.

Neither population may enter Run-04 primary metrics, fresh holdout membership,
or algorithm tuning. Their old identities, files, and hashes are never
rewritten.

## Declared change

Run-04 evaluates one content-addressed model substitution:

- baseline: `small.en`;
- candidate: `large-v3-turbo`;
- provider: `faster_whisper`;
- device: CPU;
- compute type: `int8_float32`;
- network: disabled.

The domain-neutral `AIChangeSet` records the before and after model identities,
declared behavior impacts, and known unknowns. It does not contain observed
outcomes or a release conclusion.

## Fresh population

Run-04 requires 128 fresh valid cases and eight invalid-input cases. The valid
population has exact quotas of 16 for each semantic family:

- compound critical semantics;
- controls with no critical content;
- critical identifiers;
- critical numbers;
- critical terminology and names;
- long-form and multi-utterance speech;
- negation and polarity;
- silence, overlap, and nonspeech.

The corpus must also contain at least 16 cases in each acoustic family: clean,
lossy codec, microphone and room, mixed stress, noise, overlap, speed and
prosody, and telephony. These requirements can overlap through a frozen
crossed design; they do not imply 256 separate cases.

The eight invalid families are corrupt container, empty audio, excessive
duration, mismatched extension, truncated media, unsupported channel layout,
unsupported codec, and zero-byte input. Their correct outcome is `INVALID`,
not `PASS` or an ordinary model failure.

The partitions are:

| Partition | Valid | Invalid | Tuning |
|---|---:|---:|---|
| Development | 64 | 4 | Allowed before freeze |
| Validation | 32 | 2 | Prohibited |
| Sealed holdout | 32 | 2 | Prohibited |

Speakers cannot overlap across partitions. At least 16 distinct speakers are
required, including at least eight human speakers when usage rights permit.
Demographic and accent coverage reports are mandatory and remain limitations,
not universal-coverage claims.

## Evaluator gate

Existing critical-number, critical-identifier, critical-terminology, normalized
WER, and normalized CER identities are bound by the protocol. WER and CER are
diagnostics; they cannot override meaning-critical failures.

Negation fidelity and media validity evaluators must be implemented and
qualified before real Run-04 execution. Every evaluator needs a passport with
identity, applicability, dependencies, calibration or mutation evidence,
abstention behavior, known limitations, expiry, and supersession rules.
Unresolved deterministic oracle mutations block execution.

Human review is blind to model role and selector. Two independent reviewers
inspect every critical evaluator disagreement and every unknown or conflicting
result. A third authorized adjudicator resolves disagreement. Reviewer
identity, authority, rationale, and evidence are recorded.

## Ground-truth execution

Each fresh valid case is executed against both frozen models in three fresh
process repetitions:

- 256 valid transcriptions per repetition;
- 768 planned valid transcriptions total;
- 16 invalid attempts per repetition;
- 48 planned invalid attempts total.

Transcript, normalized transcript, deterministic evaluator output, and failure
label identities must match across repetitions. Runtime duration, PID,
timestamp, and run ID may differ and are compared separately.

Full replay creates the ground-truth matrix before selectors are scored.
Selectors never see result labels while ranking.

## Selector baselines

Run-04 reports five baselines:

1. full replay;
2. deterministic TF-IDF similarity retrieval;
3. a static metadata-only risk heuristic;
4. stratified random;
5. uniform random.

Random selectors use all 30 frozen seeds. Results are reported at 5%, 10%,
20%, 40%, and 100% of measured model-second cost. Every selector is evaluated
both alone and with the same mandatory safety floor. The report includes the
entire seed distribution, never only the best seed.

Primary measurements are critical-failure recall at matched cost, critical
failures per model second, and unsafe false-pass rate. Secondary measurements
include APFDc, invalid classification, stability, time to first critical
failure, total failure recall, and unknown/conflict rate.

Run-04 has no algorithmic improvement threshold. Baselines are measured even
when they perform badly. The 3x research and approximately 5x commercial gates
begin only when AssuranceRank is tested on later untouched evidence.

## Holdout firewall

Case membership commitments, selector source hashes, evaluator identities, and
allowed metadata are frozen before hidden labels open. A dry run uses synthetic
non-holdout records and must prove that selectors cannot access labels or
result-derived features. Any change after unsealing requires a new protocol
version and a fresh holdout.

## Exit gate

Run-04 completes only when:

- the mandatory repository gate remains green;
- every protocol and input identity verifies;
- the fresh corpus contract is satisfied;
- all three ground-truth repetitions complete and semantic outputs reproduce;
- evaluator passports qualify;
- the holdout firewall dry run passes;
- every selector baseline and seed distribution is reported;
- human adjudication is complete;
- negative, unknown, invalid, partial, and failed results are preserved;
- an independent replay package is complete.

Run-04 cannot authorize claims of AssuranceRank superiority, cross-domain
generality, cross-company transfer, cross-host reproducibility, production
safety, regulatory compliance, or release certification.
