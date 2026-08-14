import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

import {
  CSP_NONCE_REQUEST_HEADER,
  createContentSecurityPolicy,
  createCspNonce,
  isValidCspNonce,
} from "./content-security-policy.ts";

const TEST_NONCE = "1234567890abcdef1234567890abcdef";

test("CSP nonce generation removes UUID separators and stays valid", () => {
  const nonce = createCspNonce(() => "12345678-90ab-4cde-8f01-234567890abc");
  assert.equal(nonce, "1234567890ab4cde8f01234567890abc");
  assert.equal(isValidCspNonce(nonce), true);
  assert.equal(isValidCspNonce("short"), false);
});

test("enforced CSP allows only nonce scripts and the Telegram script host", () => {
  const policy = createContentSecurityPolicy(TEST_NONCE);
  assert.match(policy, new RegExp(`script-src 'self' 'nonce-${TEST_NONCE}' https://telegram\\.org`));
  assert.match(policy, /script-src-attr 'none'/);
  assert.doesNotMatch(policy, /unsafe-eval/);
  assert.doesNotMatch(policy, /script-src[^;]*unsafe-inline/);
  assert.match(
    policy,
    /frame-ancestors 'self' https:\/\/web\.telegram\.org https:\/\/\*\.telegram\.org/,
  );
  assert.equal(policy.match(/'unsafe-inline'/g)?.length, 1);
  assert.match(policy, /style-src-attr 'unsafe-inline'/);
  assert.doesNotMatch(policy, /report-uri|report-to/);
});

test("CSP builder rejects a nonce that could inject a directive", () => {
  assert.throws(
    () => createContentSecurityPolicy(`${TEST_NONCE}'; report-uri https://bad.test`),
    /valid CSP nonce/,
  );
});

test("page shell and edge keep one per-request CSP owner", () => {
  const root = resolve(process.cwd(), "..");
  const layout = readFileSync(resolve(process.cwd(), "src", "app", "layout.tsx"), "utf8");
  const proxySource = readFileSync(resolve(process.cwd(), "src", "proxy.ts"), "utf8");
  const caddyfile = readFileSync(resolve(root, "ops", "Caddyfile.example"), "utf8");

  assert.match(layout, /export const dynamic = "force-dynamic"/);
  assert.match(layout, /nonce=\{nonce\}/);
  assert.equal(CSP_NONCE_REQUEST_HEADER, "x-keshepool-csp-nonce");
  assert.match(proxySource, /requestHeaders\.set\(CSP_NONCE_REQUEST_HEADER, nonce\)/);
  assert.match(proxySource, /response\.headers\.set\("Content-Security-Policy"/);
  assert.doesNotMatch(caddyfile, /Content-Security-Policy/);
});
