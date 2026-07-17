import assert from "node:assert/strict";
import test from "node:test";

import { safeRequestDiagnostic } from "./request-diagnostics.ts";

test("request diagnostics record header presence without its value", () => {
  const secretValue = "do-not-log-this";
  const diagnostic = safeRequestDiagnostic(
    new Request("https://example.test/products", {
      method: "POST",
      headers: { "Next-Action": secretValue, Cookie: "private-cookie" },
    }),
  );
  const output = JSON.stringify(diagnostic);
  assert.equal(diagnostic.hasNextActionHeader, true);
  assert.equal(diagnostic.pathname, "/products");
  assert.doesNotMatch(output, new RegExp(secretValue));
  assert.doesNotMatch(output, /private-cookie/);
});
