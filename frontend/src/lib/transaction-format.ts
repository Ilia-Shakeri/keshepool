import type { WalletTransaction } from "./api.ts";
import { formatPrice } from "./utils.ts";

export function formatTransactionAmount(tx: WalletTransaction): string {
  const currency = (tx.currency || "IRR").toUpperCase();

  if (currency === "USDT" || currency === "USD") {
    const sign = tx.amount >= 0 ? "+" : "-";
    return `${sign}$${Math.abs(tx.amount).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  return `${tx.amount >= 0 ? "+" : ""}${formatPrice(tx.amount)} تومان`;
}
