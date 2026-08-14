import assert from "node:assert/strict";
import test from "node:test";

import { resolveProductGradient } from "./product-gradient.ts";

test("product gradient resolver keeps only statically shipped classes", () => {
  assert.equal(
    resolveProductGradient("from-blue-500 to-indigo-800"),
    "from-blue-500 to-indigo-800",
  );
  assert.equal(
    resolveProductGradient("from-runtime-value to-missing-css", "from-amber-500 to-orange-800"),
    "from-amber-500 to-orange-800",
  );
  assert.equal(resolveProductGradient("arbitrary"), "from-gray-600 to-slate-900");
});
