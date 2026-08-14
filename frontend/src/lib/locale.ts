export type UiLocale = "fa" | "en";

export const UI_TEXT = {
  bootstrapFailed: {
    fa: "نشست کاربری آماده نشد. دوباره تلاش کنید.",
    en: "Your session could not be prepared. Try again.",
  },
  checkPayment: {
    fa: "بررسی وضعیت",
    en: "Check status",
  },
  close: {
    fa: "بستن",
    en: "Close",
  },
  invalidPaymentUrl: {
    fa: "نشانی امن درگاه دریافت نشد.",
    en: "A secure payment address was not received.",
  },
  loading: {
    fa: "در حال آماده‌سازی…",
    en: "Loading…",
  },
  offline: {
    fa: "اینترنت قطع است. داده‌های تازه در دسترس نیست.",
    en: "You are offline. Fresh data is unavailable.",
  },
  offlineCatalog: {
    fa: "دیدن فهرست ذخیره‌شده",
    en: "View saved catalog",
  },
  paymentFailed: {
    fa: "پرداخت ناموفق بود و موجودی افزایش نیافت.",
    en: "Payment failed and the wallet was not credited.",
  },
  paymentPending: {
    fa: "پرداخت هنوز در انتظار تأیید است.",
    en: "Payment is still awaiting confirmation.",
  },
  paymentSuccess: {
    fa: "پرداخت تأیید شد و موجودی به‌روز شد.",
    en: "Payment was confirmed and the wallet was updated.",
  },
  reload: {
    fa: "بارگذاری دوباره",
    en: "Reload",
  },
  reopen: {
    fa: "بستن و بازکردن دوباره",
    en: "Close and reopen",
  },
  retry: {
    fa: "تلاش دوباره",
    en: "Try again",
  },
  routeError: {
    fa: "این صفحه درست باز نشد. می‌توانید دوباره تلاش کنید.",
    en: "This page did not load correctly. You can try again.",
  },
  serviceUnavailable: {
    fa: "اینترنت وصل است، اما سرویس پاسخ نمی‌دهد.",
    en: "You are online, but the service is not responding.",
  },
  sessionExpired: {
    fa: "نشست شما پایان یافته است. برنامه را دوباره بارگذاری یا باز کنید.",
    en: "Your session expired. Reload or reopen the app.",
  },
  telegramMissing: {
    fa: "ارتباط با تلگرام برقرار نشد. برنامه را از داخل تلگرام باز کنید.",
    en: "Telegram could not be reached. Open the app from Telegram.",
  },
} as const;

export type UiTextKey = keyof typeof UI_TEXT;

export function detectUiLocale(languageCode?: string | null): UiLocale {
  if (languageCode?.trim().toLowerCase().startsWith("en")) return "en";
  return "fa";
}

export function currentUiLocale(): UiLocale {
  if (typeof window === "undefined") return "fa";
  return detectUiLocale(window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code);
}

export function uiText(key: UiTextKey, locale: UiLocale = currentUiLocale()): string {
  return UI_TEXT[key][locale];
}

export function bilingualUiText(key: UiTextKey): string {
  return `${UI_TEXT[key].fa} / ${UI_TEXT[key].en}`;
}
