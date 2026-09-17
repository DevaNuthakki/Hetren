# Decision 0002 Qualification Record

**Decision:** `0002`
**Decision Key:** `governance.decision-system`
**Date:** `2026-09-17`
**Result:** PASS
**Qualification state:** VERIFIED
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`

## Scope

This qualification evaluates the shared Hetren decision-governance system
introduced by Decision 0002.

It covers engineering decisions and scientific-change governance for Native
Hetren Intelligence, Adaptive Intelligence, and cross-program research.

## Positive Qualification

PASS.

The validator accepted:

- the canonical current repository records;
- all eight declared scientific-change categories with their correct evidence
  consequences;
- a valid Native Intelligence research decision;
- a valid Adaptive Intelligence research decision;
- a valid cross-program research decision.

## Adversarial Qualification

PASS.

The final accepted-state mutation suite rejected 44 / 44 tested governance violations.

The tested failure classes include:

- duplicate Decision IDs;
- duplicate record references;
- unknown lifecycle statuses;
- unknown decision classes;
- obsolete authority use;
- obsolete authority resurrection;
- missing current authorities;
- governing-header drift;
- heading and metadata identity drift;
- missing or unregistered records;
- missing required metadata or sections;
- record-path escape;
- invalid reversibility;
- impossible calendar dates;
- invalid Decision Keys;
- canonical template corruption;
- scientific consequence-map drift;
- conflicting accepted Decision Keys;
- accepted decisions with pending qualification, implementation, or
  verification evidence;
- asymmetric supersession;
- supersession across different Decision Keys;
- invalid research programs;
- invalid research change categories;
- inconsistent program/category combinations;
- research categories without research programs;
- incorrect evidence consequence for each of `THESIS`, `METRIC`, `DATA`,
  `BASELINE`, `MODEL`, `ALGORITHM`, `BUG`, and `INFRA`.

## Scientific Change Contract

The qualified minimum consequences are:

| Category | Minimum evidence consequence |
|---|---|
| `THESIS` | `NEW_PROGRAM_VERSION_AND_RERUN` |
| `METRIC` | `RERUN_AFFECTED_QUALIFICATION` |
| `DATA` | `RERUN_AND_PRESERVE_DATA_DISTINCTIONS` |
| `BASELINE` | `RECOMPARE_STRONGEST_RESULT` |
| `MODEL` | `NEW_REPLICATION_RESULT` |
| `ALGORITHM` | `NEW_METHOD_VERSION_AND_PREREGISTRATION` |
| `BUG` | `INVALIDATE_AFFECTED_RESULTS_AND_RERUN` |
| `INFRA` | `SMOKE_AND_REGRESSION_RERUN_IF_NUMERICAL_CHANGE` |

These mappings govern evidence handling. They do not imply that any scientific
hypothesis is true.

## Historical Authority Treatment

PASS.

The qualification preserves earlier Product v1.4, MVP v2.0, Neural
Intelligence Research v1.0, Adaptive Intelligence v1.0, and Charter v1.0.0 as
historical source lineage.

They are not accepted as current authority metadata for new or normalized
active decisions.

Decision 0001 retains its historical MVP v2 origin while its active governance
metadata is normalized to the current unified MVP authority.

## Limitations

This qualification establishes the decision-governance mechanism.

It does not qualify:

- a Native Intelligence scientific result;
- an Adaptive Intelligence scientific result;
- HGP;
- a model architecture;
- a dataset;
- a metric;
- a research thesis;
- a future decision merely because that decision uses this template.

Every future decision remains responsible for its own required evidence.

## Acceptance Decision

Decision 0002 transitioned from `PROPOSED` to `ACCEPTED` after its
pre-acceptance qualification passed.

The final accepted-state qualification then passed without modification of the
qualification criteria:

- Decision 0002 status: `ACCEPTED`;
- decision register version: `1.0.0`;
- decision register status: `Active`;
- positive validator: PASS;
- adversarial mutation qualification: PASS, 44 / 44 mutations rejected;
- `git diff --check`: PASS.

The decision-governance mechanism is therefore verified in its accepted state.
