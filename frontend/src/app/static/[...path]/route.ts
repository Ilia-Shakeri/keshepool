import { proxyPath } from "@/lib/server-proxy";

type Context = { params: Promise<{ path: string[] }> };

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET(request: Request, context: Context) {
  return proxyPath(request, "/static", context.params);
}

export function HEAD(request: Request, context: Context) {
  return proxyPath(request, "/static", context.params);
}
