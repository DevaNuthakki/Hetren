# Reproducible executable demonstration — P07.7D

Date: 2026-10-06.
Scope: reviewer-facing evidence surface for the deterministic Hetren portfolio
slice.
Status: implementation candidate; validation required before checkpoint.

## Purpose

P07.7A through P07.7C established the executable system.

P07.7D does not add another reasoning, repair, verification, policy,
authorization or lifecycle layer.

Its purpose is to make the existing vertical slice immediately reproducible
and inspectable by another engineer.

## Entry point

From the repository root:

    python -m packages.portfolio_demo

produces a concise human-readable report.

For machine-readable evidence:

    python -m packages.portfolio_demo --format json

produces deterministic JSON on stdout.

A reviewer may redirect that output when an artifact is desired:

    python -m packages.portfolio_demo --format json > hetren-demo.json

P07.7D itself does not write generated evidence files into the repository.

## Why a module entry point

The repository had no existing tracked CLI, console-script packaging,
Makefile, justfile or other command convention when P07.7D was introduced.

A single executable module therefore provides the smallest demonstration
surface without adding a packaging framework solely for presentation.

## Demonstrated chain

Both controlled hidden-fault fixtures execute:

    visible failure
        -> actual trace
        -> deterministic diagnosis
        -> bounded repair selection
        -> candidate SystemSnapshot
        -> actual candidate execution
        -> ordinary EvaluationRecord(PASS)
        -> separate actual verification execution
        -> separate verification evaluation
        -> VerificationReport(VERIFIED)
        -> CandidateEligibilityDecision(ELIGIBLE)

The scenarios are:

    tool_selection
        -> tool_selection_fault
        -> replace_tool

    parameter_transformation
        -> parameter_transformation_fault
        -> override_parameter

Both begin with visible output 2 and finish with candidate output 12.

## Policy separation control

The report also applies a second policy input to the already VERIFIED
tool-selection candidate.

The verification result is unchanged.

The default bounded policy produces:

    ELIGIBLE

The restricted component policy produces:

    INELIGIBLE

Therefore the executable report demonstrates:

    VERIFIED != automatically ELIGIBLE

without manufacturing a new verification run to obtain the policy difference.

## Machine-readable provenance

The JSON report includes bounded provenance such as:

- baseline trace digest,
- diagnosis-problem digest,
- repair proposal digest,
- candidate snapshot digest,
- candidate execution-evidence digest,
- source execution/evaluation identities and digests,
- verification execution/evaluation identities and digests,
- VerificationReport digest,
- CandidateEligibilityDecision digest,
- policy digest,
- report digest.

The report digest is calculated over the report body before the digest field
is added.

## Determinism

The report intentionally excludes:

- timestamps,
- randomness,
- temporary paths,
- machine-specific paths,
- network results,
- environment-dependent identifiers.

The same code and inputs therefore produce the same report structure and
bytes.

This is a reproducibility property of the deterministic fixture, not evidence
that arbitrary real-world agents are deterministic.

## Claim limits

The demonstration states its limits directly.

It does not establish:

- repair of arbitrary AI agents,
- autonomous general program repair,
- external LLM repair quality,
- production safety,
- infrastructure or organizational independence,
- production authorization,
- deployment approval,
- research superiority.

Procedural verification separation remains distinct from proof of stronger
independence.

ELIGIBLE remains distinct from authorization or deployment approval.

## Acceptance checks

Before checkpointing P07.7D:

- no P07.7A, P07.7B or P07.7C implementation is changed,
- the module executes from the repository root,
- text mode communicates the complete chain concisely,
- JSON mode is valid and deterministic,
- both controlled fault fixtures are represented,
- both cases reach candidate output 12,
- both ordinary evaluations PASS,
- verification executions/evaluations remain distinct,
- both VerificationReports are VERIFIED,
- default policy decisions are ELIGIBLE,
- the restricted-policy control remains VERIFIED but INELIGIBLE,
- report SHA-256 binds the complete report body,
- claim limits are visible in text and JSON,
- focused tests pass,
- complete integration regression passes,
- unit plus integration regression remains green.
