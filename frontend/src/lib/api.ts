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
    referralCode: string;
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
  hasReceipt?: boolean;
  createdAt: string;
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
export const AUTH_SESSION_EXPIRED_EVENT = "keshepool:auth-session-expired";
const pendingReads = new Map<string, Promise<unknown>>();
const cachedReads = new Map<string, { expiresAt: number; value: unknown }>();
const cacheVersions = new Map<string, number>();
let bootstrapPromise: Promise<BootstrapProfile> | null = null;
let activeSessionInitData: string | null = null;
let cacheGeneration = 0;
const READ_TTL_MS: Record<string, number> = {
  "/config": 300_000,
  "/products": 10_000,
  "/notifications": 5_000,
  "/me": 15_000,
  "/wallet/balance": 3_000,
  "/wallet/transactions": 3_000,
  "/orders": 3_000,
  "/cashout/platforms": 300_000,
  "/pay/crypto/rate": 15_000,
  "/pay/crypto/deposit-address": 300_000,
};

function clearSessionState(nextInitData: string): void {
  activeSessionInitData = nextInitData;
  cacheGeneration += 1;
  pendingReads.clear();
  cachedReads.clear();
  cacheVersions.clear();
  bootstrapPromise = null;
}

function ensureSessionScope(): number {
  const nextInitData = getTelegramInitData();
  if (nextInitData !== activeSessionInitData) clearSessionState(nextInitData);
  return cacheGeneration;
}

function scopedCacheKey(path: string): string {
  return `${cacheGeneration}:${path}`;
}

function invalidateCachedPaths(paths: string[]): void {
  for (const path of paths) {
    const cacheKey = scopedCacheKey(path);
    cachedReads.delete(cacheKey);
    pendingReads.delete(cacheKey);
    cacheVersions.set(cacheKey, (cacheVersions.get(cacheKey) || 0) + 1);
  }
}

function invalidateAfterWrite(path: string): void {
  if (path === "/notifications/mark-read" || path.startsWith("/notifications/")) {
    invalidateCachedPaths(["/notifications"]);
    return;
  }
  if (path === "/checkout") {
    invalidateCachedPaths(["/products", "/wallet/balance", "/wallet/transactions", "/orders", "/me"]);
    return;
  }
  if (path === "/cashout") {
    invalidateCachedPaths(["/notifications"]);
    return;
  }
  if (path.startsWith("/pay/")) {
    invalidateCachedPaths(["/wallet/balance", "/wallet/transactions", "/me"]);
  }
}

export function getTelegramInitData(): string {
  if (typeof window === "undefined") return "";
  return window.Telegram?.WebApp?.initData || "";
}

export function resetApiSession(): void {
  clearSessionState(getTelegramInitData());
}

export function getTelegramUserId(): string | null {
  if (typeof window === "undefined") return null;
  const id = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  return id ? String(id) : null;
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

async function request<T>(
  path: string,
  init: RequestInit = {},
  captureResponse?: (response: Response) => void,
): Promise<T> {
  const requestGeneration = ensureSessionScope();
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
  const bodyIsFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body && !bodyIsFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

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

  if (
    response.status === 401
    && requestGeneration === cacheGeneration
    && initData === activeSessionInitData
  ) {
    resetApiSession();
    if (typeof window.dispatchEvent === "function") {
      window.dispatchEvent(new Event(AUTH_SESSION_EXPIRED_EVENT));
    }
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

  captureResponse?.(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function startBootstrap(): Promise<BootstrapProfile> {
  const bootstrapGeneration = ensureSessionScope();
  if (bootstrapPromise) return bootstrapPromise;

  const requestPromise = request<BootstrapProfile>("/me/bootstrap", {
    method: "POST",
    body: JSON.stringify({}),
  });
  const currentPromise: Promise<BootstrapProfile> = requestPromise.then((profile) => {
    if (bootstrapGeneration !== cacheGeneration) {
      if (bootstrapPromise === currentPromise) bootstrapPromise = null;
      return startBootstrap();
    }
    return profile;
  });
  bootstrapPromise = currentPromise;
  void currentPromise.catch(() => {
    if (bootstrapPromise === currentPromise) bootstrapPromise = null;
  });
  return currentPromise;
}

export function bootstrapUser() {
  return startBootstrap();
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  await startBootstrap();
  const requestGeneration = ensureSessionScope();

  const method = (init.method || "GET").toUpperCase();
  if (method !== "GET") {
    const result = await request<T>(path, init);
    invalidateAfterWrite(path);
    return result;
  }

  const cacheKey = scopedCacheKey(path);
  const cached = cachedReads.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) return cached.value as T;
  if (cached) cachedReads.delete(cacheKey);

  const existing = pendingReads.get(cacheKey) as Promise<T> | undefined;
  if (existing) return existing;

  const requestCacheVersion = cacheVersions.get(cacheKey) || 0;
  const current = request<T>(path, init).then((value) => {
    const ttl = READ_TTL_MS[path] || 0;
    if (
      ttl > 0
      && requestGeneration === cacheGeneration
      && requestCacheVersion === (cacheVersions.get(cacheKey) || 0)
    ) {
      cachedReads.set(cacheKey, { expiresAt: Date.now() + ttl, value });
    }
    return value;
  });
  pendingReads.set(cacheKey, current);
  const removePending = () => {
    if (pendingReads.get(cacheKey) === current) pendingReads.delete(cacheKey);
  };
  void current.then(removePending, removePending);
  return current;
}

export async function apiFetchWithHeaders<T>(
  path: string,
  init: RequestInit = {},
): Promise<{ data: T; headers: Headers }> {
  if ((init.method || "GET").toUpperCase() !== "GET") {
    throw new Error("Header-aware reads support GET only.");
  }
  await startBootstrap();
  const requestGeneration = ensureSessionScope();
  let responseHeaders = new Headers();
  const data = await request<T>(path, init, (response) => {
    responseHeaders = new Headers(response.headers);
  });
  if (requestGeneration !== cacheGeneration) {
    return apiFetchWithHeaders<T>(path, init);
  }
  return { data, headers: responseHeaders };
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

export function getNotifications() {
  return apiFetch<UserNotification[]>("/notifications");
}

export interface PublicConfig {
  botUsername: string;
  supportUsername?: string | null;
  supportUrl?: string | null;
  payments: {
    tetra98Enabled: boolean;
    cardToCard: {
      enabled: boolean;
      cardNumber: string | null;
      cardHolder: string | null;
      maxReceiptBytes: number;
    };
  };
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

export function submitCardTransfer(amount: number, receipt: File) {
  const form = new FormData();
  form.set("amount", String(amount));
  form.set("receipt", receipt, receipt.name);
  return apiFetch<{
    status: "pending_review";
    transactionId: number;
    amount: number;
    currency: "IRR";
    adminDelivery: "sent" | "queued";
    message: string;
  }>("/pay/card-transfer", {
    method: "POST",
    body: form,
  });
}

export function markNotificationRead(notificationId: number) {
  return apiFetch<{ marked: number; notificationId: number }>(
    `/notifications/${notificationId}/mark-read`,
    { method: "POST" },
  );
}

export function markNotificationsReadThrough(throughId: number) {
  return apiFetch<{ marked: number; throughId: number }>("/notifications/mark-read-through", {
    method: "POST",
    body: JSON.stringify({ throughId }),
  });
}
