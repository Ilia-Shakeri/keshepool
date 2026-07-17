export function safeRequestDiagnostic(request: Request) {
  const url = new URL(request.url);
  return {
    event: "unexpected_server_action_request",
    method: request.method,
    pathname: url.pathname,
    deploymentVersion: process.env.DEPLOYMENT_VERSION || "unknown",
    hasNextActionHeader: request.headers.has("Next-Action"),
  };
}
