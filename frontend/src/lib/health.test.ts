import assert from "node:assert/strict";
import test from "node:test";

import { livenessResponse, readinessResponse } from "./health.ts";

test("liveness succeeds without contacting backend", async () => {
  const response = livenessResponse();
  assert.equal(response.status, 200);
  assert.equal((await response.json()).status, "alive");
});

test("readiness succeeds when backend is ready", async () => {
  const fetcher: typeof fetch = async () =>
    Response.json({ status: "ready", ready: true }, { status: 200 });
  const response = await readinessResponse(fetcher);
  assert.equal(response.status, 200);
  assert.equal((await response.json()).ready, true);
});

test("readiness fails when backend is unavailable", async () => {
  const fetcher: typeof fetch = async () => {
    throw new TypeError("connection refused");
  };
  const response = await readinessResponse(fetcher);
  assert.equal(response.status, 502);
  assert.equal((await response.json()).ready, false);
});

test("readiness reports upstream timeout", async () => {
  const fetcher: typeof fetch = async () =>
    new Promise((_resolve, reject) => {
      setTimeout(() => reject(new DOMException("timed out", "TimeoutError")), 5);
    });
  const response = await readinessResponse(fetcher, 5);
  assert.equal(response.status, 504);
  assert.match((await response.json()).detail, /timed out/);
});

test("readiness rejects malformed backend response", async () => {
  const fetcher: typeof fetch = async () => new Response("not-json", { status: 200 });
  const response = await readinessResponse(fetcher);
  assert.equal(response.status, 502);
  assert.match((await response.json()).detail, /malformed/);
});
