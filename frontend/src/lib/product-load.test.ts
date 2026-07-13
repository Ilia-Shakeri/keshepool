import assert from "node:assert/strict";
import test from "node:test";
import type { Product } from "./products.ts";
import { resolveProductWalletLoad } from "./product-load.ts";

test("catalog stays available when wallet loading fails", () => {
  const products = [{ id: "kept" }] as Product[];
  const result = resolveProductWalletLoad(
    { status: "fulfilled", value: products },
    { status: "rejected", reason: new Error("wallet down") },
  );

  assert.equal(result.products, products);
  assert.equal(result.productError, null);
  assert.equal(result.walletBalance, null);
  assert.equal(result.walletError, "wallet down");
});
