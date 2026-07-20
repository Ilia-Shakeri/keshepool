import type { Product } from "@/features/products/types";

export interface BootstrapProfile {
  user: {
    id: number;
    telegramId: string;
    username?: string | null;
    firstName?: string | null;
    lastName?: string | null;
    photoUrl?: string | null;
    role: string;
  };
  walletBalance: number;
  orderCount: number;
  activeOrderCount: number;
}

export interface WalletTransaction {
  id: number;
  amount: number;
  type: string;
  status: "pending" | "success" | "failed";
  currency?: string;
  gateway?: string | null;
  referenceId?: string | null;
  description?: string | null;
  createdAt: string;
}

export interface UserOrder {
  id: string;
  title: string;
  brand: string;
  duration: string;
  status: "active" | "expired" | "cancelled" | "refunded";
  createdAt: string;
  expiresAt?: string | null;
  credentials: string;
  assetUrl?: string | null;
  icon: string;
  gradient: string;
  totalAmount: number;
}

export interface UserNotification {
  id: number;
  title: string;
  description: string;
  isRead: boolean;
  createdAt: string;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 12_000;
const pendingReads = new Map<string, Promise<unknown>>();
let bootstrapPromise: Promise<BootstrapProfile> | null = null;

export function getTelegramInitData(): string {
  if (typeof window === "undefined") return "";
  return window.Telegram?.WebApp?.initData || "";
}

export function getTelegramUserId(): string | null {
  if (typeof window === "undefined") return null;
  const id = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  return id ? String(id) : null;
}

function getReferrerTelegramId(): string | null {
  const startParam = window.Telegram?.WebApp?.initDataUnsafe?.start_param || "";
  return startParam.startsWith("ref_") ? startParam.slice(4) : null;
}

function mapApiError(status: number, detail?: unknown): string {
  if (typeof detail === "string" && /[\u0600-\u06ff]/.test(detail)) return detail;

  const normalized = typeof detail === "string" ? detail.toLowerCase() : "";
  if (normalized.includes("insufficient") || normalized.includes("not enough")) {
    return "موجودی کیف پول کافی نیست.";
  }
  if (normalized.includes("out of stock") || normalized.includes("unavailable")) {
    return "این محصول اکنون موجود نیست.";
  }

  if (status === 400) return "اطلاعات واردشده درست نیست.";
  if (status === 401) return "نشست شما پایان یافته است. برنامه را دوباره باز کنید.";
  if (status === 403) return "اجازه انجام این کار را ندارید.";
  if (status === 404) return "اطلاعات درخواستی پیدا نشد.";
  if (status === 409) return "این درخواست پیش‌تر ثبت شده یا با داده فعلی تداخل دارد.";
  if (status === 422) return "لطفاً اطلاعات فرم را بررسی کنید.";
  if (status === 429) return "درخواست‌ها زیاد است. کمی بعد دوباره تلاش کنید.";
  if (status >= 500) return "سرویس موقتاً در دسترس نیست. دوباره تلاش کنید.";
  return "انجام درخواست ناموفق بود.";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const initData = getTelegramInitData();

  const controller = new AbortController();
  let didTimeout = false;
  const timeout = window.setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  const abortFromCaller = () => controller.abort(init.signal?.reason);
  init.signal?.addEventListener("abort", abortFromCaller, { once: true });

  const headers = new Headers(init.headers);
  if (initData) headers.set("X-Telegram-Init-Data", initData);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error(didTimeout ? "پاسخ سرویس بیش از حد طول کشید. دوباره تلاش کنید." : "درخواست لغو شد.");
    }
    throw new Error("ارتباط با سرویس برقرار نشد. اینترنت خود را بررسی کنید.", { cause: error });
  } finally {
    window.clearTimeout(timeout);
    init.signal?.removeEventListener("abort", abortFromCaller);
  }

  if (response.status === 401) {
    window.Telegram?.WebApp?.showAlert("نشست شما پایان یافته است. لطفاً برنامه را دوباره باز کنید.");
  }

  if (!response.ok) {
    let detail: unknown;
    try {
      const errorPayload = await response.json();
      detail = errorPayload.detail;
    } catch {
      detail = undefined;
    }
    throw new Error(mapApiError(response.status, detail));
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function startBootstrap(referrerTelegramId?: string | null): Promise<BootstrapProfile> {
  if (bootstrapPromise) return bootstrapPromise;

  const currentPromise = request<BootstrapProfile>("/me/bootstrap", {
    method: "POST",
    body: JSON.stringify({ referrerTelegramId: referrerTelegramId || null }),
  });
  bootstrapPromise = currentPromise;
  void currentPromise.catch(() => {
    if (bootstrapPromise === currentPromise) bootstrapPromise = null;
  });
  return currentPromise;
}

export function bootstrapUser(referrerTelegramId?: string | null) {
  return startBootstrap(referrerTelegramId);
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  await startBootstrap(getReferrerTelegramId());

  const method = (init.method || "GET").toUpperCase();
  if (method !== "GET") return request<T>(path, init);

  const existing = pendingReads.get(path) as Promise<T> | undefined;
  if (existing) return existing;

  const current = request<T>(path, init);
  pendingReads.set(path, current);
  const removePending = () => {
    if (pendingReads.get(path) === current) pendingReads.delete(path);
  };
  void current.then(removePending, removePending);
  return current;
}

export function getProfile() {
  return apiFetch<BootstrapProfile>("/me");
}

export function getProducts() {
  return apiFetch<Product[]>("/products");
}

export function getWalletBalance() {
  return apiFetch<{ balance: number }>("/wallet/balance");
}

export function getWalletTransactions() {
  return apiFetch<WalletTransaction[]>("/wallet/transactions");
}

export function getOrders() {
  return apiFetch<UserOrder[]>("/orders");
}

export function getNotifications() {
  return apiFetch<UserNotification[]>("/notifications");
}

export function checkoutWithWallet(productId: string, variantId: string, idempotencyKey: string) {
  return apiFetch<{
    status: string;
    order: {
      id: string;
      productTitle: string;
      productBrand: string;
      variantDuration: string;
      credentials: string;
      createdAt: string;
      totalAmount: number;
    };
  }>("/checkout", {
    method: "POST",
    headers: { "X-Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ product_id: productId, variant_id: variantId, idempotencyKey }),
  });
}

export interface PublicConfig {
  botUsername: string;
  supportUsername?: string | null;
  supportUrl?: string | null;
}

export function getPublicConfig() {
  return apiFetch<PublicConfig>("/config");
}

export function createTetra98Payment(
  amount: number,
  productId?: string | null,
  variantId?: string | null,
) {
  return apiFetch<{
    status: string;
    transactionId: number;
    authority: string;
    paymentUrlWeb: string;
    paymentUrlBot: string;
    trackingId: string;
    currency: string;
  }>("/pay/tetra98", {
    method: "POST",
    body: JSON.stringify({ amount, product_id: productId ?? null, variant_id: variantId ?? null }),
  });
}

export function getUsdtRate() {
  return apiFetch<{ tomanPerUsdt: number; base: string; quote: string }>("/pay/crypto/rate");
}

export function getCryptoDepositAddress() {
  return apiFetch<{ address: string; network: string; currency: string }>("/pay/crypto/deposit-address");
}

export function initiateCryptoDeposit(
  amountUsdt: number,
  productId?: string | null,
  variantId?: string | null,
) {
  return apiFetch<{
    status: string;
    transactionId: number;
    depositAddress: string;
    network: string;
    expectedAmount: string;
    currency: string;
    message: string;
  }>("/pay/crypto/initiate", {
    method: "POST",
    body: JSON.stringify({
      amount_usdt: amountUsdt,
      product_id: productId ?? null,
      variant_id: variantId ?? null,
    }),
  });
}

export interface CashoutPlatform {
  value: string;
  label: string;
}

export function getCashoutPlatforms() {
  return apiFetch<{ platforms: CashoutPlatform[] }>("/cashout/platforms");
}

export function createCashoutRequest(
  sourcePlatform: string,
  detailsText: string,
  customSource?: string | null,
) {
  return apiFetch<{ status: string; requestId: number; message: string }>("/cashout", {
    method: "POST",
    body: JSON.stringify({
      source_platform: sourcePlatform,
      details_text: detailsText,
      custom_source: customSource ?? null,
    }),
  });
}

export function markNotificationsRead() {
  return apiFetch<{ marked: number }>("/notifications/mark-read", { method: "POST" });
}
