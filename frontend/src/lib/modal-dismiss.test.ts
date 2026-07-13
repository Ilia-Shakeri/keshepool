import assert from "node:assert/strict";
import test from "node:test";
import { shouldBlockFinancialDismiss } from "./modal-dismiss.ts";

test("financial modal blocks overlay and Escape dismiss only while request is pending", () => {
  assert.equal(shouldBlockFinancialDismiss(true), true);
  assert.equal(shouldBlockFinancialDismiss(false), false);
});
