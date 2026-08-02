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
const cachedReads = new Map<string, { expiresAt: number; value: unknown }>();
let bootstrapPromise: Promise<BootstrapProfile> | null = null;
let activeSessionFingerprint = "";
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

function fingerprintSession(initData: string): string {
  let hash = 2166136261;
  for (let index = 0; index < initData.length; index += 1) {
    hash ^= initData.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${initData.length}:${(hash >>> 0).toString(36)}`;
}

function ensureSessionScope(): number {
  const nextFingerprint = fingerprintSession(getTelegramInitData());
  if (nextFingerprint !== activeSessionFingerprint) {
    activeSessionFingerprint = nextFingerprint;
    cacheGeneration += 1;
    pendingReads.clear();
    cachedReads.clear();
    bootstrapPromise = null;
  }
  return cacheGeneration;
}

function scopedCacheKey(path: string): string {
  return `${activeSessionFingerprint}:${path}`;
}

function clearCachedPaths(paths: string[]): void {
  for (const path of paths) cachedReads.delete(scopedCacheKey(path));
}

function invalidateAfterWrite(path: string): void {
  if (path === "/notifications/mark-read") {
    clearCachedPaths(["/notifications"]);
    return;
  }
  if (path === "/checkout") {
    clearCachedPaths(["/products", "/wallet/balance", "/wallet/transactions", "/orders", "/me"]);
    return;
  }
  if (path === "/cashout") {
    clearCachedPaths(["/notifications"]);
    return;
  }
  if (path.startsWith("/pay/")) {
    clearCachedPaths(["/wallet/balance", "/wallet/transactions", "/me"]);
  }
}

export function getTelegramInitData(): string {
  if (typeof window === "undefined") return "";
  return window.Telegram?.WebApp?.initData || "";
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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  ensureSessionScope();
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

export function startBootstrap(): Promise<BootstrapProfile> {
  ensureSessionScope();
  if (bootstrapPromise) return bootstrapPromise;

  const currentPromise = request<BootstrapProfile>("/me/bootstrap", {
    method: "POST",
    body: JSON.stringify({}),
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

  const current = request<T>(path, init).then((value) => {
    const ttl = READ_TTL_MS[path] || 0;
    if (ttl > 0 && requestGeneration === cacheGeneration) {
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
