import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import {
  CSP_NONCE_REQUEST_HEADER,
  createContentSecurityPolicy,
  createCspNonce,
} from "@/lib/content-security-policy";
import { safeRequestDiagnostic } from "@/lib/request-diagnostics";

export function proxy(request: NextRequest) {
  if (request.headers.has("Next-Action")) {
    console.warn(JSON.stringify(safeRequestDiagnostic(request)));
  }

  const nonce = createCspNonce();
  const contentSecurityPolicy = createContentSecurityPolicy(nonce);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.delete("content-security-policy-report-only");
  requestHeaders.set("content-security-policy", contentSecurityPolicy);
  requestHeaders.set(CSP_NONCE_REQUEST_HEADER, nonce);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.delete("Content-Security-Policy-Report-Only");
  response.headers.set("Content-Security-Policy", contentSecurityPolicy);
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = {
  matcher: [
    "/((?!api|health|static|webhook|_next|fonts|logo|favicon.ico|robots.txt|sitemap.xml).*)",
  ],
};
