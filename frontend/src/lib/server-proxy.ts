import { isIP } from "node:net";

const HOP_BY_HOP_HEADERS = [
  "connection",
  "content-encoding",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
];
const CLIENT_PROVENANCE_HEADERS = [
  "forwarded",
  "x-forwarded-for",
  "x-forwarded-host",
  "x-forwarded-proto",
  "x-forwarded-port",
  "x-real-ip",
  "client-ip",
  "true-client-ip",
  "cf-connecting-ip",
  "fly-client-ip",
  "fastly-client-ip",
  "x-cluster-client-ip",
];
const UPSTREAM_TIMEOUT_MS = 10_000;
const MAX_PROXY_BODY_BYTES = 1_048_576;

function backendBaseUrl(): string {
  const rawUrl = process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";
  const url = new URL(rawUrl);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("BACKEND_INTERNAL_URL must use http or https.");
  }
  return url.toString().replace(/\/$/, "");
}

function forwardedHeaders(request: Request): Headers {
  const rebuiltClientIp = request.headers.get("x-forwarded-for")?.trim() || "";
  const headers = new Headers(request.headers);
  for (const name of HOP_BY_HOP_HEADERS) headers.delete(name);
  for (const name of CLIENT_PROVENANCE_HEADERS) headers.delete(name);
  headers.delete("x-admin-token");

  const requestUrl = new URL(request.url);
  if (isIP(rebuiltClientIp)) headers.set("x-forwarded-for", rebuiltClientIp);
  headers.set("x-forwarded-host", requestUrl.host);
  headers.set("x-forwarded-proto", requestUrl.protocol.slice(0, -1));
  return headers;
}

async function readBoundedBody(request: Request): Promise<ArrayBuffer | undefined> {
  if (!request.body) return undefined;
  const declaredLength = Number(request.headers.get("content-length") || "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_PROXY_BODY_BYTES) {
    throw new RangeError("Request body is too large.");
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_PROXY_BODY_BYTES) {
      await reader.cancel();
      throw new RangeError("Request body is too large.");
    }
    chunks.push(value);
  }
  const output = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return output.buffer;
}

function responseHeaders(upstream: Response): Headers {
  const headers = new Headers(upstream.headers);
  for (const name of HOP_BY_HOP_HEADERS) headers.delete(name);
  return headers;
}

export async function proxyToBackend(request: Request, pathname: string): Promise<Response> {
  try {
    const incomingUrl = new URL(request.url);
    const targetUrl = `${backendBaseUrl()}${pathname}${incomingUrl.search}`;
    const hasBody = request.method !== "GET" && request.method !== "HEAD";
    const upstream = await fetch(targetUrl, {
      method: request.method,
      headers: forwardedHeaders(request),
      body: hasBody ? await readBoundedBody(request) : undefined,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(UPSTREAM_TIMEOUT_MS)]),
    });

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders(upstream),
    });
  } catch (error) {
    if (error instanceof RangeError) {
      return Response.json(
        { detail: "Request body is too large." },
        { status: 413, headers: { "Cache-Control": "no-store" } },
      );
    }
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    return Response.json(
      { detail: timedOut ? "Upstream service timed out." : "Upstream service unavailable." },
      { status: timedOut ? 504 : 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}

export async function proxyPath(
  request: Request,
  prefix: string,
  params: Promise<{ path: string[] }>,
): Promise<Response> {
  const { path } = await params;
  const safePath = path.map(encodeURIComponent).join("/");
  return proxyToBackend(request, `${prefix}/${safePath}`);
}
