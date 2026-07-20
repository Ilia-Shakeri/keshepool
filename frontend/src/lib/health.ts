const DEFAULT_UPSTREAM_TIMEOUT_MS = 3_000;

type ReadinessPayload = {
  ready?: unknown;
};

function deploymentVersion(): string {
  return process.env.DEPLOYMENT_VERSION || "unknown";
}

function backendReadyUrl(): string {
  const base = new URL(process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000");
  if (base.protocol !== "http:" && base.protocol !== "https:") {
    throw new Error("BACKEND_INTERNAL_URL must use http or https.");
  }
  return new URL("/health/ready", base).toString();
}

function noStoreJson(payload: object, status: number): Response {
  return Response.json(payload, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export function livenessResponse(): Response {
  return noStoreJson(
    { status: "alive", deploymentVersion: deploymentVersion() },
    200,
  );
}

export async function readinessResponse(
  fetcher: typeof fetch = fetch,
  timeoutMs = DEFAULT_UPSTREAM_TIMEOUT_MS,
): Promise<Response> {
  try {
    const upstream = await fetcher(backendReadyUrl(), {
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(timeoutMs),
    });
    const body = await upstream.text();
    let payload: ReadinessPayload;
    try {
      payload = JSON.parse(body) as ReadinessPayload;
    } catch {
      return noStoreJson(
        {
          status: "not_ready",
          ready: false,
          detail: "Backend readiness response was malformed.",
          upstreamStatus: upstream.status,
          deploymentVersion: deploymentVersion(),
        },
        502,
      );
    }

    if (!upstream.ok || payload.ready !== true) {
      return noStoreJson(
        {
          status: "not_ready",
          ready: false,
          detail: "Backend is not ready.",
          upstreamStatus: upstream.status,
          deploymentVersion: deploymentVersion(),
        },
        503,
      );
    }

    return noStoreJson(
      {
        status: "ready",
        ready: true,
        upstreamStatus: upstream.status,
        deploymentVersion: deploymentVersion(),
      },
      200,
    );
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    return noStoreJson(
      {
        status: "not_ready",
        ready: false,
        detail: timedOut ? "Backend readiness check timed out." : "Backend is unavailable.",
        deploymentVersion: deploymentVersion(),
      },
      timedOut ? 504 : 502,
    );
  }
}

export function headResponse(response: Response): Response {
  return new Response(null, { status: response.status, headers: response.headers });
}
