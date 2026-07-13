import assert from "node:assert/strict";
import test from "node:test";
import type { TelegramWebApp } from "../types/telegram.ts";

test("concurrent reads share one bootstrap and one matching read", async (context) => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  let bootstrapCalls = 0;
  let productCalls = 0;
  let checkoutCalls = 0;
  let checkoutHeader = "";
  let checkoutBody: Record<string, unknown> | null = null;

  const webApp = {
    initData: "signed-init-data",
    initDataUnsafe: { start_param: "ref_42" },
    showAlert: () => undefined,
  } as unknown as TelegramWebApp;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { Telegram: { WebApp: webApp }, setTimeout, clearTimeout },
  });

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/me/bootstrap")) {
      bootstrapCalls += 1;
      return new Response(JSON.stringify({ user: {}, walletBalance: 0, orderCount: 0, activeOrderCount: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/products")) {
      productCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 5));
      return new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (url.endsWith("/checkout")) {
      checkoutCalls += 1;
      checkoutHeader = new Headers(init?.headers).get("X-Idempotency-Key") || "";
      checkoutBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
      return new Response(JSON.stringify({
        status: "success",
        order: {
          id: "order-1",
          productTitle: "Product",
          productBrand: "Brand",
          variantDuration: "1 month",
          credentials: "secret",
          createdAt: "2026-01-01T00:00:00Z",
          totalAmount: 100,
        },
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return new Response(null, { status: 404 });
  }) as typeof fetch;

  context.after(() => {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "window", { configurable: true, value: originalWindow });
  });

  const { checkoutWithWallet, getProducts } = await import("./api.ts");
  await Promise.all(Array.from({ length: 10 }, () => getProducts()));
  await checkoutWithWallet("product-1", "variant-1", "checkout-key-123");

  assert.equal(bootstrapCalls, 1);
  assert.equal(productCalls, 1);
  assert.equal(checkoutCalls, 1);
  assert.equal(checkoutHeader, "checkout-key-123");
  assert.deepEqual(checkoutBody, {
    product_id: "product-1",
    variant_id: "variant-1",
    idempotencyKey: "checkout-key-123",
  });
});
