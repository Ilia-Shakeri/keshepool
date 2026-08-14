export const CSP_NONCE_REQUEST_HEADER = "x-keshepool-csp-nonce";

const CSP_NONCE_PATTERN = /^[A-Za-z0-9+/_-]{16,128}={0,2}$/;

export function isValidCspNonce(value: string | null | undefined): value is string {
  return typeof value === "string" && CSP_NONCE_PATTERN.test(value);
}

export function createCspNonce(uuidFactory: () => string = () => crypto.randomUUID()): string {
  const nonce = uuidFactory().replaceAll("-", "");
  if (!isValidCspNonce(nonce)) {
    throw new Error("The generated CSP nonce is invalid.");
  }
  return nonce;
}

export function createContentSecurityPolicy(nonce: string): string {
  if (!isValidCspNonce(nonce)) {
    throw new TypeError("A valid CSP nonce is required.");
  }

  return [
    "default-src 'self'",
    "base-uri 'self'",
    "connect-src 'self'",
    "font-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org",
    "frame-src 'none'",
    "img-src 'self' data: https:",
    "manifest-src 'self'",
    "media-src 'none'",
    "object-src 'none'",
    `script-src 'self' 'nonce-${nonce}' https://telegram.org`,
    "script-src-attr 'none'",
    `style-src 'self' 'nonce-${nonce}'`,
    `style-src-elem 'self' 'nonce-${nonce}'`,
    "style-src-attr 'unsafe-inline'",
    "worker-src 'none'",
  ].join("; ");
}
