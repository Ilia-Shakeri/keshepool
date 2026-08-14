import type { TelegramWebApp, TelegramWebAppInsets } from "../types/telegram";

export const APP_ACTIVATED_EVENT = "keshepool:app-activated";

export type DevicePerformanceClass = "low" | "medium" | "high";

export interface DeviceSignals {
  hardwareConcurrency?: number;
  deviceMemory?: number;
  saveData?: boolean;
  reducedMotion: boolean;
  supportsBackdropFilter: boolean;
}

export function classifyDevicePerformance(signals: DeviceSignals): DevicePerformanceClass {
  if (
    signals.reducedMotion
    || signals.saveData
    || (signals.deviceMemory !== undefined && signals.deviceMemory <= 2)
    || (signals.hardwareConcurrency !== undefined && signals.hardwareConcurrency <= 2)
  ) {
    return "low";
  }
  if (
    signals.supportsBackdropFilter
    && (signals.deviceMemory === undefined || signals.deviceMemory >= 4)
    && (signals.hardwareConcurrency === undefined || signals.hardwareConcurrency >= 4)
  ) {
    return "high";
  }
  return "medium";
}

function safeColor(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const color = value.trim();
  return /^#[0-9a-f]{6}$/i.test(color) ? color : null;
}

function safeInset(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(128, Math.max(0, value))
    : 0;
}

function applyInsets(style: CSSStyleDeclaration, prefix: string, insets?: TelegramWebAppInsets): void {
  for (const side of ["top", "right", "bottom", "left"] as const) {
    style.setProperty(`${prefix}-${side}`, `${safeInset(insets?.[side])}px`);
  }
}

export function applyTelegramTheme(webApp: TelegramWebApp, root: HTMLElement): void {
  const colors = {
    "--app-theme-bg": webApp.themeParams.bg_color,
    "--app-theme-text": webApp.themeParams.text_color,
    "--app-theme-hint": webApp.themeParams.hint_color,
    "--app-theme-link": webApp.themeParams.link_color,
    "--app-theme-button": webApp.themeParams.button_color,
    "--app-theme-button-text": webApp.themeParams.button_text_color,
  };
  for (const [name, value] of Object.entries(colors)) {
    const color = safeColor(value);
    if (color) root.style.setProperty(name, color);
    else root.style.removeProperty(name);
  }
  root.dataset.telegramTheme = webApp.colorScheme === "light" ? "light" : "dark";
  applyInsets(root.style, "--telegram-safe-area", webApp.safeAreaInset);
  applyInsets(root.style, "--telegram-content-safe-area", webApp.contentSafeAreaInset);
}

export function browserDeviceSignals(reducedMotion: boolean): DeviceSignals {
  const navigatorWithHints = navigator as Navigator & {
    deviceMemory?: number;
    connection?: { saveData?: boolean };
  };
  return {
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: navigatorWithHints.deviceMemory,
    saveData: navigatorWithHints.connection?.saveData,
    reducedMotion,
    supportsBackdropFilter: typeof CSS !== "undefined" && (
      CSS.supports("backdrop-filter", "blur(1px)")
      || CSS.supports("-webkit-backdrop-filter", "blur(1px)")
    ),
  };
}

export function applyDevicePerformance(root: HTMLElement, signals: DeviceSignals): void {
  const performanceClass = classifyDevicePerformance(signals);
  root.dataset.performance = performanceClass;
  root.dataset.reducedMotion = signals.reducedMotion ? "true" : "false";
  root.classList.toggle(
    "effects-enhanced",
    performanceClass === "high" && !signals.reducedMotion && signals.supportsBackdropFilter,
  );
}

export function bindTelegramEnvironment(webApp: TelegramWebApp, root: HTMLElement): () => void {
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const applyEnvironment = () => {
    applyTelegramTheme(webApp, root);
    applyDevicePerformance(root, browserDeviceSignals(motionQuery.matches));
  };
  const themeEvents = [
    "themeChanged",
    "safeAreaChanged",
    "contentSafeAreaChanged",
    "viewportChanged",
  ] as const;
  applyEnvironment();
  for (const event of themeEvents) webApp.onEvent?.(event, applyEnvironment);
  motionQuery.addEventListener?.("change", applyEnvironment);
  return () => {
    for (const event of themeEvents) webApp.offEvent?.(event, applyEnvironment);
    motionQuery.removeEventListener?.("change", applyEnvironment);
  };
}
