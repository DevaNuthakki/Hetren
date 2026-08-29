# Hetren Run-04 Fresh-Corpus Foundation

## Status

This stage freezes the allocation and materialization contracts for the fresh
Run-04 ASR corpus. It does not claim that the corpus has been acquired,
materialized, legally approved, sealed, evaluated, or executed.

The frozen allocation-plan identity is:

```text
99db3b3bd6f2e7ecf7bfcaab15c9505adabb0c906c145bed96df1bd520c49860
```

It is based on Run-04 protocol checkpoint commit:

```text
f04efd1b07f6d09cc384f768a673c318cf705859
```

## Why the allocation is frozen first

Selecting cases after inspecting model failures would allow cherry-picking and
would weaken any later selector comparison. Run-04 therefore fixes the case
slots, family quotas, partition sizes, speaker-source classes, and ordering
before real source identities or ASR outcomes are available.

The plan contains no:

- raw audio;
- raw transcript;
- source path or source speaker identity;
- rights approval;
- demographic inference;
- model output;
- evaluator result;
- failure label.

## Frozen allocation

| Property | Frozen value |
|---|---:|
| Valid cases | 128 |
| Deliberately invalid cases | 8 |
| Total cases | 136 |
| Development | 64 valid + 4 invalid |
| Validation | 32 valid + 2 invalid |
| Sealed holdout | 32 valid + 2 invalid |
| Semantic families | 8 families × 16 cases |
| Acoustic families | 8 families × 16 cases |
| Speaker slots | 16 |
| Human-source speaker slots | 8 |
| Synthetic-source speaker slots | 8 |
| Valid cases per speaker slot | 8 |

Each valid partition uses a balanced rotation between semantic and acoustic
families. Each speaker slot belongs to exactly one partition. The later source
binding must prove that the same real source speaker has not been assigned to
multiple slots or partitions.

The eight invalid families are each represented exactly once:

1. corrupt container;
2. empty audio;
3. excessive duration;
4. mismatched extension;
5. truncated media;
6. unsupported channel layout;
7. unsupported codec;
8. zero-byte input.

## Private materialization commitment

The commitment contract requires every frozen slot to bind to opaque SHA-256
identities for:

- source records;
- speaker provenance;
- rights records and review status;
- scenario metadata;
- media bytes;
- keyed HMAC-SHA256 transcript-label commitments for valid inputs;
- acoustic measurements for valid inputs;
- expected invalid dispositions for invalid inputs;
- coverage and limitation reports.

The commitment excludes raw content and personal source identifiers. A source
speaker is represented by an opaque identity commitment. Accent labels may be
recorded only when supplied by the source or speaker. Hetren may not infer
demographic or accent attributes from audio.

## Rights boundary

The code records one of three review states:

- `approved_for_declared_use`;
- `pending_review`;
- `rejected`.

The corpus contract cannot become ready for firewall sealing unless all 16
speaker rights records and all 136 case source records are approved for the
declared Run-04 use. Valid-case rights state must agree with its speaker
record. This approval is evidence of an authorized review; it is not legal
advice and does not guarantee that a license is valid in every jurisdiction.

Plain transcript hashes are forbidden. Short transcripts, identifiers, and
numbers can be guessed from an unkeyed digest. Valid labels therefore use
HMAC-SHA256 commitments whose secret key remains outside the public artifact.

## What comes next

The following work is still required:

1. acquire or generate every source under the frozen slot allocation;
2. preserve source, license, consent, and rights evidence;
3. materialize and hash all 136 media inputs;
4. produce transcript, acoustic, invalid-disposition, coverage, and limitation
   commitments;
5. obtain the required rights reviews;
6. build and verify the private corpus commitment;
7. qualify evaluator passports;
8. freeze selector implementations;
9. seal the holdout and pass a leakage dry run.

Only after all of those gates pass may a separate authorization artifact allow
the three full Run-04 ground-truth repetitions.

## Explicitly unauthorized claims

This foundation does not establish:

- that the fresh corpus exists;
- that rights are approved;
- that the holdout is sealed;
- that evaluator passports are qualified;
- that selector implementations exist;
- that Run-04 ASR execution is authorized;
- that AssuranceRank, BRF, or HCAS works;
- that any model is safer or better;
- production qualification, certification, or regulatory compliance.
