import { proxyPath } from "@/lib/server-proxy";

type Context = { params: Promise<{ path: string[] }> };

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function POST(request: Request, context: Context) {
  return proxyPath(request, "/webhook", context.params);
}
