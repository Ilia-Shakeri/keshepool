# Legacy schema and guarded-DDL checks

## Scope

This change hardens only the local migration path. It does not connect to, alter, or stamp a remote database.

## Legacy baseline decision

`stamp_if_legacy.py` may stamp revision `001` only when every table, column, enum, and relational constraint created by revision `001` matches a checked compatibility manifest. The manifest also permits the four guarded additions from revisions `002` through `004` when they already exist with their exact expected shape. Unknown columns or constraints on a baseline table stop the stamp and require an operator-reviewed migration.

Enum labels may be canonical lowercase labels, their historical uppercase form, or both during the pre-`004` transition. Unrelated labels stop the stamp.

## Guarded-DDL decision

An additive revision after `015` checks every object created with `IF NOT EXISTS` in revisions `002` through `004`. It verifies column types, lengths, precision, nullability, the cashout enum and foreign key, and the exact index column/predicate contracts. A mismatch aborts the migration. It does not guess how to rewrite an unknown production shape.

## Compatibility and rollback

- Fresh databases still run revision `001` normally.
- Databases already tracked by Alembic are never stamped by the legacy detector.
- Compatible pre-Alembic databases are stamped at `001` and continue through the additive chain.
- Drifted databases fail before an Alembic stamp or application cutover.
- The assertion revision has no schema writes, so its downgrade is a no-op.

## Release proof

Local unit tests cover complete, missing, malformed, and unknown legacy shapes. Disposable PostgreSQL proof remains required before release.
