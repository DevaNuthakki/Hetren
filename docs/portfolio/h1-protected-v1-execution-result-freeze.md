P09.3 H1 Protected Execution Result Freeze
==========================================

Status
------

**PROTECTED EXECUTION COMPLETED — RESULT BYTES FROZEN — SCIENTIFIC INTERPRETATION PENDING**

This document freezes the exact byte identity and lineage of the one-shot
P09.3 H1 protected execution before scientific metric disclosure or broader
interpretation.

This is a provenance and result-freeze record. It does not state whether any
registered scientific criterion passed or failed.

Authorized execution identity
-----------------------------

- Protected batch: `protected_v1`
- One-shot attempt: `execution_v1`
- Authorized D3 HEAD: `b3c8a563843e4d5d7a3ef939414073e8f9719d5d`
- D2 execution checkpoint: `a11391cf90985e035dc091d117ea6eb68c774af7`
- D1 contract checkpoint: `e00358f781cb23581a7bb6b8a423081350a6830d`
- Generation-freeze checkpoint: `aba783582336b9add67ed7d93bb1185e1243f430`

Separate explicit human authorization was supplied before the production
invocation. The production command was invoked once.

No second production invocation is permitted for `execution_v1`.

D3 authorization contract
-------------------------

Path:

`docs/portfolio/h1-protected-v1-execution-authorization-contract.md`

SHA-256:

`eff9d3683337f816bd0d5a4ead5207f957ebd4e799518d0bafd590237a1a51f3`

Frozen execution source bytes
-----------------------------

- Controlled environment SHA-256:
  `960c5a058bb92266e4c54430722f3a1e99933423f6fe9f0dda923bd250fdfd2e`
- Treatment contract SHA-256:
  `22a2b6b6e88cddd9057d79c500aa4f620f0081daf634bf566b31ad7a6488656f`
- Evaluator contract SHA-256:
  `c8f38aed18859ecb4f8720ef5839539790ef1723d46517c547852dcc5deec167`
- One-shot persistence SHA-256:
  `ee976830cf84ea7dcc17e6e9431902c28ed87a3b23d1243197d5bae44e974184`
- Production CLI SHA-256:
  `444de92f1a8cec928a6846a55bcbdd03fae32b875afef801da613cfea2b2ca2d`

Frozen generation evidence
--------------------------

- Generation disposition SHA-256:
  `95161cffe0db2aac8a8029243d57febafaba68f7198af71a9cfc2101b3c6a9c1`
- Seed commitment file SHA-256:
  `1a04be21e6c908e390ea17ba8701dd124e5cd886d0d4ab23b887094858593c53`
- Public seed commitment / raw-seed SHA-256:
  `c1cd47afe62a4ee303334c3cac443e5a263ff3725ddfec48b7695eafe783cf3d`
- Public manifest SHA-256:
  `b88d9c3bd280f18a56ea9c9c6bb05127cacba8ebf6d7fbb91deb1b70a9e12c01`
- Hidden-truth manifest SHA-256:
  `b709a96d33d405d89c545b6c2fa2c923f6f4c66eb3380b0412faf501bae5e60c`
- Generation record SHA-256:
  `5cff5a433c5cb841a7a06e37ddc01a0418534a9a68a3ea3172a4a6991264291f`

The raw seed itself is not copied into this tracked record.
No individual case-to-fault assignment is copied into this tracked record.

Frozen one-shot execution artifact bytes
----------------------------------------

- Execution disposition SHA-256:
  `b649e8124ea62775f788e919297577852a1dde352672bbaf96ce879fa566f827`
- Treatment batch SHA-256:
  `d0075af51e5682e63f5fa790df9cf5e4927ddc0e4d46969791edcebe41a9989b`
- Execution record SHA-256:
  `d170ceb300e5b52829852bfd759507ec878c94ea6701de0564a115af86d50f0d`
- Evaluator result SHA-256:
  `f1f0ec239791105540d847a29e6764b8f713c6890818960f9e50e348ca20bbc6`

The evaluator result remains outside Git. This tracked freeze records its
cryptographic identity only.

Frozen result surface
---------------------

The successful `execution_v1` artifact surface contains exactly four files:
the public execution disposition, public treatment batch, public execution
record, and evaluator-side evaluation.

The treatment batch contains exactly 96 protected cases and four frozen arms
per case, for 384 matched treatment records.

The public treatment result contains no hidden-truth field.
The evaluator result is hash-bound to the exact treatment result and exact
hidden-truth manifest.

One-shot rule
-------------

`execution_v1` is permanently consumed.

Do not rerun the production command, delete and recreate the result, replace
unfavorable cases, reroll hidden assignments, alter treatment/evaluator
bytes, or rerun to obtain a preferred result.

Any later analysis must use these exact frozen bytes.

Interpretation boundary
-----------------------

No registered H1 metric, paired difference, criterion decision, treatment-arm
success rate, false-specific rate, template-by-fault result, or resource
result is recorded in this checkpoint.

The purpose of this freeze is to establish result identity before scientific
interpretation.

The next step must mechanically read the already-frozen evaluator result and
report the preregistered quantities without modifying or rerunning the
experiment.

Scientific scope
----------------

This remains a deterministic controlled mechanism experiment.

Freezing these bytes does not establish realistic-agent effectiveness, model
robustness, unknown-fault performance, multi-fault performance, production
reliability, external validity, causal repair correctness, or state-of-the-art
performance.

Any later claim must remain bounded to the frozen preregistration and the
actual frozen evaluator result.
