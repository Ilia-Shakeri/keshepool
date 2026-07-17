import { headResponse, livenessResponse } from "@/lib/health";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET() {
  return livenessResponse();
}

export function HEAD() {
  return headResponse(livenessResponse());
}
