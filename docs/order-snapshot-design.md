# Order commercial snapshots and allocation order

Revision `015` makes every new checkout preserve the commercial facts used at sale time. The order stores the product title, brand, variant duration, displayed price label, currency, unit price, tax, fee, and total. The existing `total_amount` field and API numeric shape stay unchanged; complete snapshots require the stored total to equal unit price plus tax and fee.

Checkout takes shared locks on the active product and variant before reading their names and price. The displayed price label is derived from that locked numeric price, so stale stored label text cannot enter the order snapshot. Checkout writes the snapshot in the same transaction that debits the wallet, assigns stock, records the purchase transaction, and creates the order. An idempotent retry returns that same order row and therefore the same snapshot. The checkout response uses complete snapshot labels and total rather than the mutable catalog rows.

A database trigger rejects changes to every commercial snapshot field and both total fields after insertion. It also freezes the product, variant, and inventory ownership tuple for complete new orders. A quarantined legacy tuple can still be repaired to satisfy the composite key, but it never becomes a complete historical snapshot. Catalog title, brand, duration, price-label, price, or visibility changes cannot rewrite a prior sale.

## Legacy rows

The migration retains the exact historical value already held in `orders.total_amount`. It leaves every newly added snapshot value null for legacy rows. It does not copy current catalog labels or split historical totals into price, tax, and fee because the database cannot prove those values still match the sale. This avoids a table-wide rewrite during the schema release.

Every legacy order is marked `legacy_quarantined` with `historical_snapshot_unavailable`. A row whose product, variant, or inventory ownership does not agree is marked `ownership_mismatch`. These rows retain their original data for review, but are never presented as complete snapshots. No guessed historical value is written.

## Relational ownership

The variant table exposes a unique `(product_id, id)` target. Inventory uses a composite foreign key from `(product_id, variant_id)` to that target. Orders use a composite foreign key from `(inventory_item_id, product_id, variant_id)` to inventory. This blocks new cross-product inventory and order links.

The migration adds both composite foreign keys as `NOT VALID` so a bad legacy row cannot abort the whole expand release. Mismatched legacy inventory is disabled before the guard is added. Each constraint is validated immediately when its legacy table is clean; otherwise it still enforces all new writes and remains pending until an operator resolves the quarantined rows and validates it in a reviewed maintenance task.

## Deterministic allocation

Sellable inventory is selected under `FOR UPDATE SKIP LOCKED` in this exact order:

1. Earliest non-null expiry.
2. Creation time.
3. Numeric inventory ID.
4. Rows without expiry come last.

The supporting index starts with product, variant, and status, followed by expiry, creation time, and ID. Concurrent buyers can skip a row already locked by another checkout while still selecting the next deterministic candidate.

## Verification

Unit tests compile the PostgreSQL allocation query and verify `NULLS LAST`, creation time, and ID ordering. Model and migration tests verify the composite keys, quarantine-only legacy backfill, immutable trigger, and index shape. Disposable PostgreSQL tests exercise concurrent allocation, catalog mutation after sale, and visibility serialization. They remain skipped unless `KESHEPOOL_RUN_POSTGRES_TESTS=1` and a disposable `TEST_DATABASE_URL` whose database name contains `test` are supplied.
