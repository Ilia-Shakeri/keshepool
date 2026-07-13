import assert from "node:assert/strict";
import test from "node:test";
import type { WalletTransaction } from "./api.ts";
import { formatTransactionAmount } from "./transaction-format.ts";

function transaction(amount: number, currency: string): WalletTransaction {
  return {
    id: 1,
    amount,
    currency,
    type: "purchase",
    status: "success",
    createdAt: "2026-01-01T00:00:00Z",
  };
}

test("negative dollar and USDT amounts keep the minus sign", () => {
  assert.equal(formatTransactionAmount(transaction(-15, "USDT")), "-$15.00");
  assert.equal(formatTransactionAmount(transaction(-2.5, "USD")), "-$2.50");
  assert.equal(formatTransactionAmount(transaction(3, "USDT")), "+$3.00");
});
