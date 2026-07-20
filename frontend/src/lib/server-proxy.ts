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
const UPSTREAM_TIMEOUT_MS = 10_000;

function backendBaseUrl(): string {
  const rawUrl = process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";
  const url = new URL(rawUrl);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("BACKEND_INTERNAL_URL must use http or https.");
  }
  return url.toString().replace(/\/$/, "");
}

function forwardedHeaders(request: Request): Headers {
  const headers = new Headers(request.headers);
  for (const name of HOP_BY_HOP_HEADERS) headers.delete(name);

  const requestUrl = new URL(request.url);
  headers.set("x-forwarded-host", requestUrl.host);
  headers.set("x-forwarded-proto", requestUrl.protocol.slice(0, -1));
  return headers;
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
      body: hasBody ? await request.arrayBuffer() : undefined,
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
