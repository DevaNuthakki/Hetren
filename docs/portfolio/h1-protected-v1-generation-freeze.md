# P09.3 H1 Protected Generation Freeze — protected_v1

## Status

This record freezes the non-secret lineage and cryptographic commitments for
the one-shot P09.3 H1 protected batch named `protected_v1`.

Protected generation completed successfully exactly once before this record
was created.

This record does **not** contain the evaluator-only raw seed.

This record does **not** contain case-to-fault assignments.

No C0-C3 protected treatment arm had been executed when this record was
created.

This record is a provenance/freeze checkpoint. It is not an H1 experimental
result and does not establish scientific support for H1.

## Frozen Scientific Lineage

- P09.3 preregistration commit:
  `ed4a33823d78c18ad524a2bb9d5dfb7c8f06b790`
- P09.3 preregistration SHA-256:
  `6b738092e28036ea400f6498a4ad1663dd8cbb1e1c9c1e54e48ff4030ceb6ef8`
- Development harness commit:
  `ccc65a6a7e3e1745e0ceda3968287507a2de81d2`
- Development harness source SHA-256:
  `8acdddd206978d1374dc72bbb9d59cc5ad7efa5b41f78e39f24dda5679be9af9`
- Protected generator source SHA-256:
  `17424bd4cc7ea8bb2215b18ea9d19468b2dde8bb35c1d1d91bea69d2288ff39b`
- Protected persistence source SHA-256:
  `97cda29d10924d78cff121c3400688ce2c5a4b907b60ae8c24f4bf64faa7def1`
- One-shot production CLI SHA-256:
  `93dbad4b5db8a27be4cce24509959285bd06fa44a02b2d48359723eee3a20e50`
- Repository HEAD used for protected generation:
  `784e2ccfd0512bf8e986fa587d2a0696da08af47`

## Frozen protected_v1 Commitments

- Batch ID:
  `protected_v1`
- Seed commitment SHA-256:
  `c1cd47afe62a4ee303334c3cac443e5a263ff3725ddfec48b7695eafe783cf3d`
- Public manifest canonical SHA-256:
  `b88d9c3bd280f18a56ea9c9c6bb05127cacba8ebf6d7fbb91deb1b70a9e12c01`
- Evaluator-only hidden truth manifest canonical SHA-256:
  `b709a96d33d405d89c545b6c2fa2c923f6f4c66eb3380b0412faf501bae5e60c`
- Generation record file SHA-256:
  `5cff5a433c5cb841a7a06e37ddc01a0418534a9a68a3ea3172a4a6991264291f`

## Byte-Level Artifact Hashes

- `public/generation_disposition.json`:
  `95161cffe0db2aac8a8029243d57febafaba68f7198af71a9cfc2101b3c6a9c1`
- `public/seed_commitment.json`:
  `1a04be21e6c908e390ea17ba8701dd124e5cd886d0d4ab23b887094858593c53`
- `public/public_manifest.json`:
  `b88d9c3bd280f18a56ea9c9c6bb05127cacba8ebf6d7fbb91deb1b70a9e12c01`
- `public/generation_record.json`:
  `5cff5a433c5cb841a7a06e37ddc01a0418534a9a68a3ea3172a4a6991264291f`
- `evaluator/hidden_truth_manifest.json`:
  `b709a96d33d405d89c545b6c2fa2c923f6f4c66eb3380b0412faf501bae5e60c`

The evaluator-only `raw_seed.bin` is intentionally not copied into Git.
Its SHA-256 is already frozen by the public seed commitment above.

## Frozen Population Shape

The protected public manifest contains exactly 96 treatment-visible case
slots:

- 80 cost-sensitive slots:
  T1=20, T2=20, T3=20, T4=20.
- 16 cost-neutral slots:
  N1=4, N2=4, N3=4, N4=4.

The evaluator-only hidden population has the preregistered aggregate balance:

- H1=24
- H2=24
- H3=24
- H4=24

These aggregate counts were fixed by construction. They do not reveal the
case-to-fault assignment.

## Generation Boundary

Generation status: `SUCCEEDED`.

The raw seed remained evaluator-only during the generation review.

No case-to-fault mapping was printed during the protected-generation review.

The generated public and hidden manifests reconstructed exactly from the
frozen generator and evaluator-only seed.

The one-shot batch identity `protected_v1` is permanently consumed.

The protected generator must not be rerun for this batch identity.

## Experimental Boundary

At this freeze point:

- C0 TRACE_ONLY has not run on protected_v1.
- C1 SEEDED_RANDOM_ACTIVE has not run on protected_v1.
- C2 MAX_INFORMATION_GAIN_ACTIVE has not run on protected_v1.
- C3 HEAL_INFORMATION_GAIN_PER_COST has not run on protected_v1.
- No protected diagnosis result exists.
- No H1 support decision exists.
- No repair experiment exists.
- No verification/eligibility claim exists.

Protected-generation evidence is therefore frozen independently of the later
treatment outcomes.

## Limitation

This checkpoint binds local generated artifacts by cryptographic hash and Git
history. It does not itself prove hardware independence, organizational
independence, external custody, or real-world generalization.

The protected benchmark remains a deterministic controlled mechanism test
under the boundaries frozen in the P09.3 preregistration.
