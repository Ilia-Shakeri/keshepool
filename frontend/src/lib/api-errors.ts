import { currentUiLocale, type UiLocale } from "./locale";

export type KnownApiErrorCode =
  | "AUTH_SESSION_EXPIRED"
  | "CONFLICT"
  | "FORBIDDEN"
  | "INSUFFICIENT_BALANCE"
  | "INVALID_INPUT"
  | "NOT_FOUND"
  | "OUT_OF_STOCK"
  | "PAYMENT_GATEWAY_UNAVAILABLE"
  | "RATE_LIMITED"
  | "SERVICE_UNAVAILABLE";

type LocalizedMessage = Record<UiLocale, string>;

const CODE_MESSAGES: Record<KnownApiErrorCode, LocalizedMessage> = {
  AUTH_SESSION_EXPIRED: {
    fa: "نشست شما پایان یافته است. برنامه را دوباره باز کنید.",
    en: "Your session expired. Reopen the app.",
  },
  CONFLICT: {
    fa: "این درخواست با وضعیت فعلی سازگار نیست. داده‌ها را تازه کنید.",
    en: "This request conflicts with the current state. Refresh the data.",
  },
  FORBIDDEN: {
    fa: "اجازه انجام این کار را ندارید.",
    en: "You do not have permission to do this.",
  },
  INSUFFICIENT_BALANCE: {
    fa: "موجودی کیف پول کافی نیست.",
    en: "Your wallet balance is insufficient.",
  },
  INVALID_INPUT: {
    fa: "اطلاعات واردشده درست نیست.",
    en: "The submitted information is invalid.",
  },
  NOT_FOUND: {
    fa: "اطلاعات درخواستی پیدا نشد.",
    en: "The requested information was not found.",
  },
  OUT_OF_STOCK: {
    fa: "این گزینه اکنون موجود نیست.",
    en: "This option is currently out of stock.",
  },
  PAYMENT_GATEWAY_UNAVAILABLE: {
    fa: "درگاه پرداخت موقتاً پاسخ نمی‌دهد. بعداً دوباره تلاش کنید.",
    en: "The payment gateway is temporarily unavailable. Try again later.",
  },
  RATE_LIMITED: {
    fa: "درخواست‌ها زیاد است. کمی بعد دوباره تلاش کنید.",
    en: "There are too many requests. Try again shortly.",
  },
  SERVICE_UNAVAILABLE: {
    fa: "سرویس موقتاً در دسترس نیست. دوباره تلاش کنید.",
    en: "The service is temporarily unavailable. Try again.",
  },
};

const STATUS_MESSAGES: Record<number, LocalizedMessage> = {
  400: { fa: "اطلاعات واردشده درست نیست.", en: "The submitted information is invalid." },
  401: { fa: "نشست شما پایان یافته است. برنامه را دوباره باز کنید.", en: "Your session expired. Reopen the app." },
  403: { fa: "اجازه انجام این کار را ندارید.", en: "You do not have permission to do this." },
  404: { fa: "اطلاعات درخواستی پیدا نشد.", en: "The requested information was not found." },
  408: { fa: "زمان درخواست پایان یافت. دوباره تلاش کنید.", en: "The request timed out. Try again." },
  409: { fa: "درخواست با وضعیت فعلی سازگار نیست. داده‌ها را تازه کنید.", en: "The request conflicts with the current state. Refresh the data." },
  413: { fa: "حجم داده ارسالی بیش از حد مجاز است.", en: "The submitted data is too large." },
  422: { fa: "اطلاعات فرم را بررسی کنید.", en: "Check the form information." },
  429: { fa: "درخواست‌ها زیاد است. کمی بعد دوباره تلاش کنید.", en: "There are too many requests. Try again shortly." },
  500: { fa: "خطای داخلی رخ داد. دوباره تلاش کنید.", en: "An internal error occurred. Try again." },
  502: { fa: "سرویس بالادستی پاسخ درست نداد. دوباره تلاش کنید.", en: "An upstream service returned an invalid response. Try again." },
  503: { fa: "سرویس موقتاً در دسترس نیست. دوباره تلاش کنید.", en: "The service is temporarily unavailable. Try again." },
  504: { fa: "پاسخ سرویس بیش از حد طول کشید. دوباره تلاش کنید.", en: "The service took too long to respond. Try again." },
};

const DEFAULT_MESSAGE: LocalizedMessage = {
  fa: "انجام درخواست ناموفق بود.",
  en: "The request failed.",
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly retryable: boolean;

  constructor(message: string, status: number, code: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryable = status === 408 || status === 429 || status >= 500;
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function normalizeCode(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim().toUpperCase().replaceAll("-", "_");
  return /^[A-Z][A-Z0-9_]{1,63}$/.test(normalized) ? normalized : null;
}

function extractCode(payload: unknown, responseCode?: string | null): string | null {
  const root = asRecord(payload);
  const detail = asRecord(root?.detail);
  return normalizeCode(responseCode)
    || normalizeCode(root?.code)
    || normalizeCode(root?.errorCode)
    || normalizeCode(detail?.code)
    || normalizeCode(detail?.errorCode);
}

function persianDetail(payload: unknown): string | null {
  const root = asRecord(payload);
  const detail = root?.detail;
  const nested = asRecord(detail);
  const candidate = typeof detail === "string"
    ? detail
    : typeof nested?.message === "string"
      ? nested.message
      : null;
  if (!candidate || candidate.length > 500 || !/[\u0600-\u06ff]/.test(candidate)) return null;
  return candidate;
}

export function apiErrorFromPayload(
  status: number,
  payload?: unknown,
  responseCode?: string | null,
  locale: UiLocale = currentUiLocale(),
): ApiError {
  const code = extractCode(payload, responseCode);
  const known = code && code in CODE_MESSAGES ? code as KnownApiErrorCode : null;
  const message = known
    ? CODE_MESSAGES[known][locale]
    : locale === "fa"
      ? persianDetail(payload) || (STATUS_MESSAGES[status] || DEFAULT_MESSAGE).fa
      : (STATUS_MESSAGES[status] || DEFAULT_MESSAGE).en;
  return new ApiError(message, status, code);
}
