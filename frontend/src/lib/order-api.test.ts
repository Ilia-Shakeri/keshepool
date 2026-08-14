import assert from "node:assert/strict";
import test from "node:test";
import type { TelegramWebApp } from "../types/telegram.ts";


test("order reads and checkout stay masked while reveal uses a separate post", async (context) => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const calls: Array<{ url: string; method: string; headers: Headers; body: string }> = [];
  const revealedValue = ["fixture", "value"].join("-");

  const webApp = {
    initData: "credential-reveal-test-session",
    showAlert: () => undefined,
  } as unknown as TelegramWebApp;
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { Telegram: { WebApp: webApp }, setTimeout, clearTimeout },
  });

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({
      url,
      method: (init?.method || "GET").toUpperCase(),
      headers: new Headers(init?.headers),
      body: String(init?.body || ""),
    });
    if (url.endsWith("/me/bootstrap")) {
      return Response.json({ user: {}, walletBalance: 0, orderCount: 0, activeOrderCount: 0 });
    }
    if (url.includes("/orders?limit=20")) {
      return Response.json([{
        id: "KP.fixture:1",
        title: "Fixture",
        brand: "Fixture",
        duration: "Fixture",
        status: "active",
        createdAt: "2026-01-01T00:00:00Z",
        expiresAt: null,
        credentialPreview: "........",
        credentialAvailable: true,
        assetUrl: null,
        icon: "Box",
        gradient: "fixture",
        totalAmount: 100,
      }], { headers: { "X-Next-Cursor": "fixture-next-cursor" } });
    }
    if (url.endsWith("/orders")) {
      return Response.json([{
        id: "KP.fixture:1",
        title: "Fixture",
        brand: "Fixture",
        duration: "Fixture",
        status: "active",
        createdAt: "2026-01-01T00:00:00Z",
        expiresAt: null,
        credentialPreview: "........",
        credentialAvailable: true,
        assetUrl: null,
        icon: "Box",
        gradient: "fixture",
        totalAmount: 100,
      }]);
    }
    if (url.endsWith("/checkout")) {
      return Response.json({
        status: "success",
        order: {
          id: "KP.fixture:1",
          productTitle: "Fixture",
          productBrand: "Fixture",
          variantDuration: "Fixture",
          credentialPreview: "........",
          credentialAvailable: true,
          createdAt: "2026-01-01T00:00:00Z",
          totalAmount: 100,
        },
      });
    }
    if (url.endsWith("/orders/KP.fixture%3A1/reveal-credential")) {
      return Response.json({ orderId: "KP.fixture:1", credential: revealedValue });
    }
    if (url.endsWith("/notifications/mark-read-through")) {
      const throughId = Number(JSON.parse(String(init?.body || "{}")).throughId);
      return Response.json({ marked: 1, throughId });
    }
    if (url.endsWith("/notifications/8/mark-read")) {
      return Response.json({ marked: 1, notificationId: 8 });
    }
    return new Response(null, { status: 404 });
  }) as typeof fetch;

  context.after(() => {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "window", { configurable: true, value: originalWindow });
  });

  const { checkoutWithWallet, getOrders, getOrdersPage, revealOrderCredential } = await import("../features/orders/api.ts");
  const { appendUniqueOrders } = await import("../features/orders/pagination.ts");
  const { markNotificationRead, markNotificationsReadThrough } = await import("./api.ts");
  const orders = await getOrders();
  const page = await getOrdersPage();
  const checkout = await checkoutWithWallet("product-fixture", "variant-fixture", "idempotency-fixture");
  const reveal = await revealOrderCredential("KP.fixture:1");
  const oneNotification = await markNotificationRead(8);
  const throughNotifications = await markNotificationsReadThrough(8);

  assert.equal("credentials" in orders[0], false);
  assert.equal(orders[0]?.credentialAvailable, true);
  assert.equal(page.nextCursor, "fixture-next-cursor");
  assert.deepEqual(
    appendUniqueOrders(page.orders, [page.orders[0], { ...page.orders[0], id: "KP.fixture:2" }]).map((order) => order.id),
    ["KP.fixture:1", "KP.fixture:2"],
  );
  assert.equal("credentials" in checkout.order, false);
  assert.equal(checkout.order.credentialAvailable, true);
  assert.equal(reveal.credential, revealedValue);
  assert.equal(oneNotification.notificationId, 8);
  assert.equal(throughNotifications.throughId, 8);

  const checkoutCall = calls.find((call) => call.url.endsWith("/checkout"));
  assert.equal(checkoutCall?.method, "POST");
  assert.equal(checkoutCall?.headers.get("X-Idempotency-Key"), "idempotency-fixture");
  assert.deepEqual(JSON.parse(checkoutCall?.body || "{}"), {
    product_id: "product-fixture",
    variant_id: "variant-fixture",
    idempotencyKey: "idempotency-fixture",
  });

  const revealCall = calls.find((call) => call.url.includes("/reveal-credential"));
  assert.equal(revealCall?.method, "POST");
  assert.equal(revealCall?.url.endsWith("/orders/KP.fixture%3A1/reveal-credential"), true);
  const pageCall = calls.find((call) => call.url.includes("/orders?limit=20"));
  assert.equal(pageCall?.method, "GET");
  const throughCall = calls.find((call) => call.url.endsWith("/notifications/mark-read-through"));
  assert.equal(throughCall?.method, "POST");
  assert.deepEqual(JSON.parse(throughCall?.body || "{}"), { throughId: 8 });
});
