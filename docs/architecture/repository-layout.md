# Repository layout

## Architectural rule

Hetren is a modular monorepo.

Logical product responsibilities are separated without prematurely turning
every module into an independently deployed service. The private runner is
a distinct execution boundary.

## Deployable applications

### `apps/control_plane`

The FastAPI composition root and external control-plane API.

It exposes product capabilities but should contain little domain logic.
Reusable logic belongs in `packages/`.

### `apps/runner`

The private execution runtime.

It executes approved work near authorized data, code, models, and system
state. It is a separate trust and failure boundary from the control plane.

### `apps/studio`

The React/TypeScript Hetren Studio.

Studio reads the same authoritative records used by APIs and integrations.

## Shared packages

### `packages/contracts`

Canonical records, identities, enums, and typed interfaces shared across
the product.

### `packages/core`

Experiment and workflow semantics that coordinate evidence-bearing work.

### `packages/capabilities`

Capability discovery, qualification state, compatibility, and invalidation.

### `packages/intelligence`

Shared task state and planner/policy interfaces.

### `packages/engines`

Behavioral and Internal Engine implementations.

### `packages/evidence`

Execution, evaluation, provenance, artifact identity, and evidence lineage.

### `packages/verification`

Independent verification contracts and implementation verification.

### `packages/memory`

Experience Memory, Release Memory, recurrence, applicability, and
known-good relationships.

### `packages/action_gateway`

Authorization, action eligibility, budget checks, and execution authority.

### `packages/persistence`

PostgreSQL persistence, repositories, and migration-facing data access.

### `packages/integrations`

GitHub, MCP, model/provider, and future external integration adapters.

## Qualification environments

`environments/agent`, `environments/tabular`, and `environments/vision`
contain the three initial system families required by MVP v2.

Environment code provides system semantics, fixtures, and qualified
evaluators. It must not embed a hidden investigation strategy.

## Native research

`research/native_intelligence` contains Hetren-developed neural mechanisms.

`research/baselines`, `research/training`, `research/evaluation`, and
`research/benchmarks` separate comparative research responsibilities.

Research artifacts do not become product authority merely because they
exist in this repository.

## Tests

- `tests/unit`
- `tests/integration`
- `tests/qualification`
- `tests/adversarial`
- `tests/acceptance`

Scientific evaluation assets that require stronger access separation may
live outside the ordinary developer checkout.

## Infrastructure

`infra/` contains reproducible container and local-development
infrastructure.

Runtime evidence, model checkpoints, generated datasets, uploads, secrets,
and experiment outputs are not source-tree architecture and should not be
committed by default.
