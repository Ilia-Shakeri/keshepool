import type { TelegramWebApp } from "../types/telegram";

const BOT_HOSTS = new Set(["t.me", "telegram.me"]);

export function validatedHttpsUrl(rawValue: string): string | null {
  if (!rawValue || rawValue.length > 2_048) return null;
  try {
    const url = new URL(rawValue);
    if (url.protocol !== "https:" || url.username || url.password || !url.hostname) return null;
    return url.toString();
  } catch {
    return null;
  }
}

export function validatedBotUrl(rawValue: string): string | null {
  const safeUrl = validatedHttpsUrl(rawValue);
  if (!safeUrl) return null;
  return BOT_HOSTS.has(new URL(safeUrl).hostname.toLowerCase()) ? safeUrl : null;
}

type BrowserNavigation = {
  location: Pick<Location, "assign">;
};

export function openPaymentDestination(
  paymentUrlWeb: string,
  paymentUrlBot: string,
  webApp: TelegramWebApp | undefined,
  browser: BrowserNavigation,
): "telegram" | "webapp" | "browser" | null {
  const botUrl = validatedBotUrl(paymentUrlBot);
  const webUrl = validatedHttpsUrl(paymentUrlWeb);
  if (webApp && botUrl) {
    webApp.openTelegramLink(botUrl);
    return "telegram";
  }
  if (webApp && webUrl) {
    webApp.openLink(webUrl);
    return "webapp";
  }
  if (webUrl) {
    browser.location.assign(webUrl);
    return "browser";
  }
  return null;
}
