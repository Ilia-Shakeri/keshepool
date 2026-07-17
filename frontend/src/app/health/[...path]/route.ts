import { headResponse, livenessResponse, readinessResponse } from "@/lib/health";

type Context = { params: Promise<{ path: string[] }> };

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function healthResponse(context: Context): Promise<Response> {
  const { path } = await context.params;
  if (path.length !== 1) return Response.json({ detail: "Not found." }, { status: 404 });
  if (path[0] === "live") return livenessResponse();
  if (path[0] === "ready") return readinessResponse();
  return Response.json({ detail: "Not found." }, { status: 404 });
}

export function GET(_request: Request, context: Context) {
  return healthResponse(context);
}

export async function HEAD(_request: Request, context: Context) {
  return headResponse(await healthResponse(context));
}
