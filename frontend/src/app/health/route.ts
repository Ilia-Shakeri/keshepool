import { proxyToBackend } from "@/lib/server-proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET(request: Request) {
  return proxyToBackend(request, "/health");
}

export function HEAD(request: Request) {
  return proxyToBackend(request, "/health");
}
