import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import type { TelegramWebApp } from "../types/telegram.ts";

test("concurrent reads share one bootstrap and one matching read", async (context) => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  let bootstrapCalls = 0;
  let productCalls = 0;
  let checkoutCalls = 0;
  let bootstrapBody: Record<string, unknown> | null = null;
  let checkoutHeader = "";
  let checkoutBody: Record<string, unknown> | null = null;

  const webAppState = {
    initData: "signed-init-data",
    showAlert: () => undefined,
  };
  const webApp = webAppState as unknown as TelegramWebApp;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { Telegram: { WebApp: webApp }, setTimeout, clearTimeout },
  });

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/me/bootstrap")) {
      bootstrapCalls += 1;
      bootstrapBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
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
          credentialPreview: "........",
          credentialAvailable: true,
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

  const { getProducts } = await import("./api.ts");
  const { checkoutWithWallet } = await import("../features/orders/api.ts");
  await Promise.all(Array.from({ length: 10 }, () => getProducts()));
  await checkoutWithWallet("product-1", "variant-1", "checkout-key-123");
  await getProducts();
  webAppState.initData = "signed-init-data-for-next-user";
  await getProducts();

  assert.equal(bootstrapCalls, 2);
  assert.deepEqual(bootstrapBody, {});
  assert.equal(productCalls, 3);
  assert.equal(checkoutCalls, 1);
  assert.equal(checkoutHeader, "checkout-key-123");
  assert.deepEqual(checkoutBody, {
    product_id: "product-1",
    variant_id: "variant-1",
    idempotencyKey: "checkout-key-123",
  });
});

test("card transfer sends multipart receipt without forcing a JSON content type", async (context) => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  let submittedBody: BodyInit | null | undefined;
  let submittedContentType: string | null = null;

  const webApp = {
    initData: "card-transfer-session",
    showAlert: () => undefined,
  } as unknown as TelegramWebApp;
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { Telegram: { WebApp: webApp }, setTimeout, clearTimeout, dispatchEvent: () => true },
  });

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/me/bootstrap")) {
      return new Response(JSON.stringify({ user: {}, walletBalance: 0, orderCount: 0, activeOrderCount: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/pay/card-transfer")) {
      submittedBody = init?.body;
      submittedContentType = new Headers(init?.headers).get("Content-Type");
      return new Response(JSON.stringify({
        status: "pending_review",
        transactionId: 41,
        amount: 250000,
        currency: "IRR",
        adminDelivery: "sent",
        message: "stored",
      }), { status: 201, headers: { "Content-Type": "application/json" } });
    }
    return new Response(null, { status: 404 });
  }) as typeof fetch;

  context.after(() => {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "window", { configurable: true, value: originalWindow });
  });

  const { resetApiSession, submitCardTransfer } = await import("./api.ts");
  resetApiSession();
  const receipt = new File([new Uint8Array([1, 2, 3])], "receipt.png", { type: "image/png" });
  const result = await submitCardTransfer(250000, receipt);

  assert.equal(result.transactionId, 41);
  assert.equal(submittedContentType, null);
  assert.ok(submittedBody instanceof FormData);
  assert.equal(submittedBody.get("amount"), "250000");
  assert.equal((submittedBody.get("receipt") as File).name, "receipt.png");
});

test("write invalidation cannot let an older in-flight read refill the cache", async (context) => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  let productCalls = 0;
  let resolveFirstProduct!: (response: Response) => void;
  let markFirstProductStarted!: () => void;
  const firstProductResponse = new Promise<Response>((resolve) => {
    resolveFirstProduct = resolve;
  });
  const firstProductStarted = new Promise<void>((resolve) => {
    markFirstProductStarted = resolve;
  });

  const webApp = {
    initData: "cache-race-session",
    showAlert: () => undefined,
  } as unknown as TelegramWebApp;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { Telegram: { WebApp: webApp }, setTimeout, clearTimeout },
  });

  globalThis.fetch = (async (input: string | URL | Request) => {
    const url = String(input);
    if (url.endsWith("/me/bootstrap")) {
      return new Response(JSON.stringify({ user: {}, walletBalance: 0, orderCount: 0, activeOrderCount: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/products")) {
      productCalls += 1;
      if (productCalls === 1) {
        markFirstProductStarted();
        return firstProductResponse;
      }
      return new Response(JSON.stringify([{ id: "fresh" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/checkout")) {
      return new Response(JSON.stringify({ status: "success", order: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(null, { status: 404 });
  }) as typeof fetch;

  context.after(() => {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "window", { configurable: true, value: originalWindow });
  });

  const { getProducts } = await import("./api.ts");
  const { checkoutWithWallet } = await import("../features/orders/api.ts");
  const staleRead = getProducts();
  await firstProductStarted;

  await checkoutWithWallet("product-1", "variant-1", "cache-race-key");
  const freshProducts = await getProducts();

  resolveFirstProduct(new Response(JSON.stringify([{ id: "stale" }]), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  }));
  const staleProducts = await staleRead;
  const cachedProducts = await getProducts();

  assert.equal(productCalls, 2);
  assert.equal(staleProducts[0]?.id, "stale");
  assert.equal(freshProducts[0]?.id, "fresh");
  assert.equal(cachedProducts[0]?.id, "fresh");
});

test("same-length legacy hash collisions still use separate session caches", async (context) => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const webAppState = {
    initData: "000008u1sah5f5",
    showAlert: () => undefined,
  };
  let bootstrapCalls = 0;
  let productCalls = 0;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      Telegram: { WebApp: webAppState as unknown as TelegramWebApp },
      setTimeout,
      clearTimeout,
    },
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
      const session = new Headers(init?.headers).get("X-Telegram-Init-Data");
      return new Response(JSON.stringify([{ id: session }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(null, { status: 404 });
  }) as typeof fetch;

  context.after(() => {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "window", { configurable: true, value: originalWindow });
  });

  const { getProducts } = await import("./api.ts");
  const first = await getProducts();
  webAppState.initData = "0000ge48t41scy";
  const second = await getProducts();

  assert.equal(first[0]?.id, "000008u1sah5f5");
  assert.equal(second[0]?.id, "0000ge48t41scy");
  assert.equal(bootstrapCalls, 2);
  assert.equal(productCalls, 2);
});

test("current-session 401 clears bootstrap and read caches", async (context) => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const windowEvents = new EventTarget();
  let bootstrapCalls = 0;
  let productCalls = 0;
  let expiredEvents = 0;
  let alerts = 0;
  const webApp = {
    initData: "expired-session",
    showAlert: () => {
      alerts += 1;
    },
  } as unknown as TelegramWebApp;
  const fakeWindow = Object.assign(windowEvents, {
    Telegram: { WebApp: webApp },
    setTimeout,
    clearTimeout,
  });

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: fakeWindow,
  });

  globalThis.fetch = (async (input: string | URL | Request) => {
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
      return new Response(JSON.stringify([{ id: `product-${productCalls}` }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/wallet/balance")) {
      return new Response(JSON.stringify({ detail: "expired" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(null, { status: 404 });
  }) as typeof fetch;

  context.after(() => {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "window", { configurable: true, value: originalWindow });
  });

  const api = await import("./api.ts");
  fakeWindow.addEventListener(api.AUTH_SESSION_EXPIRED_EVENT, () => {
    expiredEvents += 1;
  });

  const beforeExpiry = await api.getProducts();
  await assert.rejects(api.getWalletBalance());
  const afterExpiry = await api.getProducts();

  assert.equal(beforeExpiry[0]?.id, "product-1");
  assert.equal(afterExpiry[0]?.id, "product-2");
  assert.equal(bootstrapCalls, 2);
  assert.equal(productCalls, 2);
  assert.equal(expiredEvents, 1);
  assert.equal(alerts, 1);
});

test("an old-session 401 cannot clear a newer session cache", async (context) => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const windowEvents = new EventTarget();
  const webAppState = {
    initData: "old-session",
    showAlert: () => undefined,
  };
  let bootstrapCalls = 0;
  let productCalls = 0;
  let expiredEvents = 0;
  let resolveOldRequest!: (response: Response) => void;
  let markOldRequestStarted!: () => void;
  const oldResponse = new Promise<Response>((resolve) => {
    resolveOldRequest = resolve;
  });
  const oldRequestStarted = new Promise<void>((resolve) => {
    markOldRequestStarted = resolve;
  });
  const fakeWindow = Object.assign(windowEvents, {
    Telegram: { WebApp: webAppState as unknown as TelegramWebApp },
    setTimeout,
    clearTimeout,
  });

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: fakeWindow,
  });

  globalThis.fetch = (async (input: string | URL | Request) => {
    const url = String(input);
    if (url.endsWith("/me/bootstrap")) {
      bootstrapCalls += 1;
      return new Response(JSON.stringify({ user: {}, walletBalance: 0, orderCount: 0, activeOrderCount: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/wallet/balance")) {
      markOldRequestStarted();
      return oldResponse;
    }
    if (url.endsWith("/products")) {
      productCalls += 1;
      return new Response(JSON.stringify([{ id: "new-session-product" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(null, { status: 404 });
  }) as typeof fetch;

  context.after(() => {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "window", { configurable: true, value: originalWindow });
  });

  const api = await import("./api.ts");
  fakeWindow.addEventListener(api.AUTH_SESSION_EXPIRED_EVENT, () => {
    expiredEvents += 1;
  });

  const oldRequest = api.getWalletBalance();
  await oldRequestStarted;
  webAppState.initData = "new-session";
  await api.getProducts();
  resolveOldRequest(new Response(JSON.stringify({ detail: "expired" }), {
    status: 401,
    headers: { "Content-Type": "application/json" },
  }));
  await assert.rejects(oldRequest);
  await api.getProducts();

  assert.equal(bootstrapCalls, 2);
  assert.equal(productCalls, 1);
  assert.equal(expiredEvents, 0);
});

test("session reset during bootstrap waits for a fresh bootstrap", async (context) => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const webApp = {
    initData: "activation-reset-session",
    showAlert: () => undefined,
  } as unknown as TelegramWebApp;
  let bootstrapCalls = 0;
  let productCalls = 0;
  let markFirstBootstrapStarted!: () => void;
  let resolveFirstBootstrap!: (response: Response) => void;
  const firstBootstrapStarted = new Promise<void>((resolve) => {
    markFirstBootstrapStarted = resolve;
  });
  const firstBootstrapResponse = new Promise<Response>((resolve) => {
    resolveFirstBootstrap = resolve;
  });

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { Telegram: { WebApp: webApp }, setTimeout, clearTimeout },
  });

  globalThis.fetch = (async (input: string | URL | Request) => {
    const url = String(input);
    if (url.endsWith("/me/bootstrap")) {
      bootstrapCalls += 1;
      if (bootstrapCalls === 1) {
        markFirstBootstrapStarted();
        return firstBootstrapResponse;
      }
      return new Response(JSON.stringify({ user: {}, walletBalance: 0, orderCount: 0, activeOrderCount: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/products")) {
      productCalls += 1;
      return new Response(JSON.stringify([{ id: "fresh-after-activation" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(null, { status: 404 });
  }) as typeof fetch;

  context.after(() => {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "window", { configurable: true, value: originalWindow });
  });

  const api = await import("./api.ts");
  const productsRequest = api.getProducts();
  await firstBootstrapStarted;
  api.resetApiSession();
  resolveFirstBootstrap(new Response(
    JSON.stringify({ user: {}, walletBalance: 0, orderCount: 0, activeOrderCount: 0 }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  ));
  const products = await productsRequest;

  assert.equal(products[0]?.id, "fresh-after-activation");
  assert.equal(bootstrapCalls, 2);
  assert.equal(productCalls, 1);
});

test("bootstrap surface provides activation refresh and close-or-reload recovery", () => {
  const bootstrapSource = readFileSync(
    resolve(process.cwd(), "src", "components", "layout", "TelegramBootstrap.tsx"),
    "utf8",
  );

  assert.match(bootstrapSource, /AUTH_SESSION_EXPIRED_EVENT/);
  assert.match(bootstrapSource, /"activated"/);
  assert.match(bootstrapSource, /resetApiSession\(\)/);
  assert.match(bootstrapSource, /webApp\.close\(\)/);
  assert.match(bootstrapSource, /window\.location\.reload\(\)/);
});
