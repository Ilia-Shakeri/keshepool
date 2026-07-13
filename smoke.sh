#!/bin/sh
set -eu

# Run every check from the frontend container to prove service DNS and ingress routing.
docker compose exec -T frontend node <<'NODE'
const publicBaseUrl = (process.env.PUBLIC_BASE_URL || "").replace(/\/$/, "");

if (!publicBaseUrl) {
  throw new Error("PUBLIC_BASE_URL is not configured in the frontend container.");
}

const checks = [
  ["backend service readiness", "http://backend:8000/health/ready", [200]],
  ["same-origin readiness", "http://127.0.0.1:3000/health/ready", [200]],
  ["same-origin public config", "http://127.0.0.1:3000/api/config", [200]],
  ["same-origin product auth", "http://127.0.0.1:3000/api/products", [401, 403]],
  ["public readiness", `${publicBaseUrl}/health/ready`, [200]],
  ["public config", `${publicBaseUrl}/api/config`, [200]],
  ["public product auth", `${publicBaseUrl}/api/products`, [401, 403]],
];

(async () => {
  for (const [name, url, expectedStatuses] of checks) {
    const response = await fetch(url, { signal: AbortSignal.timeout(10000) });
    if (!expectedStatuses.includes(response.status)) {
      throw new Error(`${name} returned ${response.status}; expected ${expectedStatuses.join(" or ")}.`);
    }
    console.log(`[smoke] ${name}: ${response.status}`);
  }
})().catch((error) => {
  console.error(`[smoke] ${error.message}`);
  process.exit(1);
});
NODE
