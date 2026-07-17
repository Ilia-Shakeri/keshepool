import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { safeRequestDiagnostic } from "@/lib/request-diagnostics";

export function proxy(request: NextRequest) {
  if (request.headers.has("Next-Action")) {
    console.warn(JSON.stringify(safeRequestDiagnostic(request)));
  }
  return NextResponse.next();
}

export const config = {
  matcher: [{ source: "/:path*", has: [{ type: "header", key: "Next-Action" }] }],
};
