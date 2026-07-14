import { proxyPath } from "@/lib/server-proxy";

type Context = { params: Promise<{ path: string[] }> };

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET(request: Request, context: Context) {
  return proxyPath(request, "/api", context.params);
}

export function POST(request: Request, context: Context) {
  return proxyPath(request, "/api", context.params);
}

export function PUT(request: Request, context: Context) {
  return proxyPath(request, "/api", context.params);
}

export function PATCH(request: Request, context: Context) {
  return proxyPath(request, "/api", context.params);
}

export function DELETE(request: Request, context: Context) {
  return proxyPath(request, "/api", context.params);
}

export function HEAD(request: Request, context: Context) {
  return proxyPath(request, "/api", context.params);
}

export function OPTIONS(request: Request, context: Context) {
  return proxyPath(request, "/api", context.params);
}
