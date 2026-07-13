import { rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(root, ".test-dist");
const compiler = resolve(root, "node_modules", "typescript", "bin", "tsc");
const testFile = resolve(output, "lib", "all.test.js");

let exitCode = 1;
try {
  const compile = spawnSync(process.execPath, [compiler, "-p", "tsconfig.tests.json"], {
    cwd: root,
    stdio: "inherit",
  });
  if (compile.status !== 0) {
    exitCode = compile.status ?? 1;
  } else {
    const tests = spawnSync(process.execPath, ["--test", testFile], {
      cwd: root,
      stdio: "inherit",
    });
    exitCode = tests.status ?? 1;
  }
} finally {
  rmSync(output, { recursive: true, force: true });
}

process.exit(exitCode);
