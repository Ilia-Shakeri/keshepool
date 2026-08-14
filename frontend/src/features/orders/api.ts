import { apiFetch, apiFetchWithHeaders } from "../../lib/api";
import type { CheckoutResult, CredentialReveal, UserOrder, UserOrdersPage } from "./types";


const ORDER_PAGE_LIMIT = 20;
const NEXT_CURSOR_HEADER = "X-Next-Cursor";

export function getOrders() {
  return apiFetch<UserOrder[]>("/orders");
}

export async function getOrdersPage(cursor?: string | null): Promise<UserOrdersPage> {
  const params = new URLSearchParams({ limit: String(ORDER_PAGE_LIMIT) });
  if (cursor) params.set("cursor", cursor);
  const result = await apiFetchWithHeaders<UserOrder[]>(`/orders?${params.toString()}`);
  return {
    orders: result.data,
    nextCursor: result.headers.get(NEXT_CURSOR_HEADER),
  };
}

export function revealOrderCredential(orderId: string) {
  return apiFetch<CredentialReveal>(
    `/orders/${encodeURIComponent(orderId)}/reveal-credential`,
    { method: "POST" },
  );
}

export function checkoutWithWallet(
  productId: string,
  variantId: string,
  idempotencyKey: string,
) {
  return apiFetch<CheckoutResult>("/checkout", {
    method: "POST",
    headers: { "X-Idempotency-Key": idempotencyKey },
    body: JSON.stringify({
      product_id: productId,
      variant_id: variantId,
      idempotencyKey,
    }),
  });
}
