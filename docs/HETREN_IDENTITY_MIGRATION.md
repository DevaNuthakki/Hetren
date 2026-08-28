# Hetren identity migration policy

Hetren uses a compatibility migration from the former Ovrin identity. This is
not a global search-and-replace operation. Product-facing and active execution
paths use Hetren now, while identities that protect data access, verification,
or historical provenance remain unchanged until an explicit migration exists.

## Classification

| Category | Treatment now | Removal condition |
|---|---|---|
| Active product/runtime identity | Use Hetren immediately. | Not applicable. |
| Environment compatibility alias | Read Hetren first and Ovrin second. | Every deployed runner and environment has migrated. |
| Cryptographic identity | Preserve old token prefixes and the Ovrin hash namespace. | Never rewrite issued-secret hashes; retire only after all old secrets expire or are revoked. |
| Storage identity | Preserve the existing `backend/ovrin.db`, `ovrin`, `ovrin_test`, database-user, and Docker-volume names. | A tested dump/restore, rollback, and populated-snapshot migration is approved. |
| Historical identity | Preserve migration filenames, frozen test uploads, evidence, backups, hashes, and manifests exactly. | Never rename merely for branding. Add alias or supersession metadata instead. |
| Cleanup alias | Continue recognizing old seeded project names. | All supported databases have been cleaned or migrated. |

## Gate

Run the checker from the repository root:

```bash
cd backend
python scripts/check_hetren_identity_migration.py
```

For the complete classified inventory:

```bash
python scripts/check_hetren_identity_migration.py \
  --format json > hetren-identity-inventory.json
```

The command exits nonzero when an Ovrin occurrence appears outside the
approved compatibility, storage, cleanup, migration-control, or historical
boundaries. CI also runs the repository-level characterization test.

## Non-negotiable rules

1. Never recompute a historical hash to replace a product name.
2. Never rename the existing Docker volume as a cosmetic change; that would
   make the current data appear to disappear.
3. Never remove legacy secret prefixes without an explicit credential
   expiration or revocation plan.
4. New runtime code, fixtures, documentation, and APIs use Hetren unless they
   are deliberately exercising a documented compatibility boundary.
5. A future PostgreSQL identity migration must be additive, tested against a
   populated snapshot, reversible, and independently verified.
