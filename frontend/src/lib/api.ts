import type { Product } from "@/lib/products";

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

export function getTelegramInitData(): string {
  if (typeof window === "undefined") return "";
  return window.Telegram?.WebApp?.initData || "";
}

export function getTelegramUserId(): string | null {
  if (typeof window === "undefined") return null;
  const id = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  return id ? String(id) : null;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const initData = getTelegramInitData();
  if (!initData) {
    throw new Error("Telegram authorization data is unavailable.");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData,
      ...(init.headers || {}),
    },
  });

  if (response.status === 401) {
    const webApp = window.Telegram?.WebApp;
    if (webApp) {
      webApp.showAlert("Session Expired - Please reopen the app.", () => {
        webApp.close();
      });
    }
    throw new Error("Session Expired - Please reopen the app.");
  }

  if (!response.ok) {
    let message = "Request failed.";
    try {
      const errorPayload = await response.json();
      message = errorPayload.detail || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function bootstrapUser(referrerTelegramId?: string | null) {
  return apiFetch<BootstrapProfile>("/me/bootstrap", {
    method: "POST",
    body: JSON.stringify({ referrerTelegramId: referrerTelegramId || null }),
  });
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

export function checkoutWithWallet(productId: string, variantId: string) {
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
    body: JSON.stringify({ product_id: productId, variant_id: variantId }),
  });
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