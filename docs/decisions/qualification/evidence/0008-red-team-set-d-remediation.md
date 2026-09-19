# Decision 0008 Set D Remediation History

## Remediation Attempt 1

**Original fresh Set D evidence:** `21 / 32`

**Purpose:** Remediate architectural gaps discovered by frozen Set D.

**Validator SHA-256:**

`7b8cfaeafd571783fd5a4a651aacbe2dc92d8e8edb149a54ab460a4a1105450f`

**Invariant registry SHA-256:**

`bffe8bd08eaf4981ce16824864fe1e5c582d201dce6c3830fc7be1ece317e152`

### Result

P1 MUST_ACCEPT:

`24 / 24` accepted.

Canonical development mutations:

`52 / 52` rejected.

Set A:

`12 / 12` rejected.

Set B:

`11 / 12` rejected.

Set B survivor:

- `distributed baseline and cost rules manufacture preferred comparison`

Set C:

`56 / 64` rejected.

Set C survivors:

- `C08.01 distributed baseline/resource gaming`
- `C08.02 distributed baseline/resource gaming`
- `C08.03 distributed baseline/resource gaming`
- `C08.04 distributed baseline/resource gaming`
- `C08.05 distributed baseline/resource gaming`
- `C08.06 distributed baseline/resource gaming`
- `C08.07 distributed baseline/resource gaming`
- `C08.08 distributed baseline/resource gaming`

Set D regression:

`31 / 32` correct.

Remaining Set D miss:

- `T7-D-05-04` expected `MUST_ACCEPT`

This remediation attempt is **not accepted** because historical Set B and Set C
regressed and one Set D false positive remains.

### Raw Evidence

`docs/decisions/qualification/evidence/0008-red-team-set-d-remediation-1-wall.txt`

SHA-256:

`97f8505997cfde15a13d6debfc01e5bf8a065773341c3af335d97c9981e4612e`

### Evidence Interpretation

The original frozen Set D result remains permanently `21 / 32`.

The `31 / 32` result is remediation/regression evidence only.

No Set D definition was changed.

No failed historical result is erased.

**Scientific support established:** `NO`

**Task 5 capability support promoted:** `NO`
