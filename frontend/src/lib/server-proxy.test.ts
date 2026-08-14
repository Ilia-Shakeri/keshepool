import assert from "node:assert/strict";
import test from "node:test";

import { proxyToBackend } from "./server-proxy.ts";


test("server proxy strips client provenance and rebuilds one safe chain", async () => {
  const originalFetch = globalThis.fetch;
  const originalBaseUrl = process.env.BACKEND_INTERNAL_URL;
  const capturedHeaders: Headers[] = [];
  process.env.BACKEND_INTERNAL_URL = "http://backend.test:8000";
  globalThis.fetch = (async (_input, init) => {
    capturedHeaders.push(new Headers(init?.headers));
    return new Response("{}", {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;

  try {
    await proxyToBackend(
      new Request("https://keshepool.example.com/api/products", {
        headers: {
          Forwarded: "for=198.51.100.8",
          "X-Forwarded-For": "203.0.113.9",
          "X-Forwarded-Port": "1234",
          "X-Real-IP": "198.51.100.9",
          "Client-IP": "198.51.100.10",
          "True-Client-IP": "198.51.100.11",
          "CF-Connecting-IP": "198.51.100.12",
          "Fly-Client-IP": "198.51.100.13",
          "Fastly-Client-IP": "198.51.100.14",
          "X-Cluster-Client-IP": "198.51.100.15",
          "X-Admin-Token": "must-not-pass",
          "X-Telegram-Init-Data": "signed-session",
        },
      }),
      "/api/products",
    );
    await proxyToBackend(
      new Request("https://keshepool.example.com/api/products", {
        headers: {
          "X-Forwarded-For": "203.0.113.9, 198.51.100.8",
        },
      }),
      "/api/products",
    );
  } finally {
    globalThis.fetch = originalFetch;
    if (originalBaseUrl === undefined) {
      delete process.env.BACKEND_INTERNAL_URL;
    } else {
      process.env.BACKEND_INTERNAL_URL = originalBaseUrl;
    }
  }

  const safeHeaders = capturedHeaders[0];
  assert.equal(safeHeaders.get("forwarded"), null);
  assert.equal(safeHeaders.get("x-forwarded-for"), "203.0.113.9");
  assert.equal(safeHeaders.get("x-forwarded-host"), "keshepool.example.com");
  assert.equal(safeHeaders.get("x-forwarded-proto"), "https");
  assert.equal(safeHeaders.get("x-forwarded-port"), null);
  assert.equal(safeHeaders.get("x-real-ip"), null);
  assert.equal(safeHeaders.get("client-ip"), null);
  assert.equal(safeHeaders.get("true-client-ip"), null);
  assert.equal(safeHeaders.get("cf-connecting-ip"), null);
  assert.equal(safeHeaders.get("fly-client-ip"), null);
  assert.equal(safeHeaders.get("fastly-client-ip"), null);
  assert.equal(safeHeaders.get("x-cluster-client-ip"), null);
  assert.equal(safeHeaders.get("x-admin-token"), null);
  assert.equal(safeHeaders.get("x-telegram-init-data"), "signed-session");
  assert.equal(capturedHeaders[1].get("x-forwarded-for"), null);
});
