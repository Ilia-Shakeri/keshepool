import type { WalletTransaction } from "./api";

export const PAYMENT_INTENT_STORAGE_KEY = "keshepool:payment-intent:v1";
export const PAYMENT_POLL_INTERVAL_MS = 3_000;
export const PAYMENT_POLL_WINDOW_MS = 5 * 60_000;
const PAYMENT_RESULT_RETENTION_MS = 24 * 60 * 60_000;

export type PaymentIntentStatus = "pending" | "success" | "failed";

export interface StoredPaymentIntent {
  version: 1;
  ownerUserId: number;
  transactionId: number;
  trackingId: string;
  status: PaymentIntentStatus;
  createdAt: number;
  updatedAt: number;
  pollUntil: number;
}

type PaymentStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function isSafeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function parseIntent(value: unknown): StoredPaymentIntent | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (
    record.version !== 1
    || !isSafeInteger(record.ownerUserId)
    || !isSafeInteger(record.transactionId)
    || typeof record.trackingId !== "string"
    || record.trackingId.length > 160
    || !["pending", "success", "failed"].includes(String(record.status))
    || !isSafeInteger(record.createdAt)
    || !isSafeInteger(record.updatedAt)
    || !isSafeInteger(record.pollUntil)
    || record.updatedAt < record.createdAt
    || record.pollUntil < record.createdAt
  ) {
    return null;
  }
  return record as unknown as StoredPaymentIntent;
}

export function createPaymentIntent(
  ownerUserId: number,
  transactionId: number,
  trackingId: string,
  now = Date.now(),
): StoredPaymentIntent {
  if (!isSafeInteger(ownerUserId) || !isSafeInteger(transactionId) || !isSafeInteger(now)) {
    throw new TypeError("Payment intent identifiers are invalid.");
  }
  return {
    version: 1,
    ownerUserId,
    transactionId,
    trackingId: trackingId.trim().slice(0, 160),
    status: "pending",
    createdAt: now,
    updatedAt: now,
    pollUntil: now + PAYMENT_POLL_WINDOW_MS,
  };
}

export function savePaymentIntent(storage: PaymentStorage, intent: StoredPaymentIntent): void {
  storage.setItem(PAYMENT_INTENT_STORAGE_KEY, JSON.stringify(intent));
}

export function clearPaymentIntent(storage: PaymentStorage): void {
  storage.removeItem(PAYMENT_INTENT_STORAGE_KEY);
}

export function loadPaymentIntent(
  storage: PaymentStorage,
  ownerUserId: number,
  now = Date.now(),
): StoredPaymentIntent | null {
  let parsed: StoredPaymentIntent | null = null;
  try {
    const raw = storage.getItem(PAYMENT_INTENT_STORAGE_KEY);
    parsed = raw ? parseIntent(JSON.parse(raw)) : null;
  } catch {
    parsed = null;
  }
  if (
    !parsed
    || parsed.ownerUserId !== ownerUserId
    || now - parsed.updatedAt > PAYMENT_RESULT_RETENTION_MS
  ) {
    clearPaymentIntent(storage);
    return null;
  }
  return parsed;
}

export function updatePaymentIntent(
  intent: StoredPaymentIntent,
  transactions: readonly WalletTransaction[],
  now = Date.now(),
): StoredPaymentIntent {
  if (intent.status !== "pending") return intent;
  const transaction = transactions.find((item) => item.id === intent.transactionId);
  if (!transaction || transaction.status === "pending") return intent;
  return {
    ...intent,
    status: transaction.status,
    updatedAt: now,
  };
}

export function shouldPollPayment(intent: StoredPaymentIntent, now = Date.now()): boolean {
  return intent.status === "pending" && now < intent.pollUntil;
}

export function paymentPollingEnded(intent: StoredPaymentIntent, now = Date.now()): boolean {
  return intent.status === "pending" && now >= intent.pollUntil;
}
