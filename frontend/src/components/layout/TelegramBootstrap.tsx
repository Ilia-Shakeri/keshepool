"use client";

import { useCallback, useEffect, useState } from "react";
import { bootstrapUser } from "@/lib/api";

export default function TelegramBootstrap() {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  const runBootstrap = useCallback(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) {
      setErrorMessage("ارتباط با تلگرام برقرار نشد. برنامه را از داخل تلگرام دوباره باز کنید.");
      return Promise.resolve();
    }

    setIsRetrying(true);
    setErrorMessage(null);
    webApp.expand();
    webApp.ready();

    const startParam = webApp.initDataUnsafe?.start_param || "";
    const referrerTelegramId = startParam.startsWith("ref_") ? startParam.slice(4) : null;

    return bootstrapUser(referrerTelegramId)
      .then(() => undefined)
      .catch((error: unknown) => {
        setErrorMessage(error instanceof Error ? error.message : "نشست کاربری آماده نشد. دوباره تلاش کنید.");
      })
      .finally(() => setIsRetrying(false));
  }, []);

  useEffect(() => {
    void Promise.resolve().then(runBootstrap);
  }, [runBootstrap]);

  if (!errorMessage) return null;

  return (
    <div className="fixed inset-x-4 top-[calc(var(--app-header-height)+var(--safe-area-top)+0.75rem)] z-[10000] mx-auto flex max-w-xl items-center justify-between gap-3 rounded-2xl border border-[#E63946]/30 bg-[#181013]/95 p-3 text-right shadow-2xl backdrop-blur-xl">
      <p className="text-xs leading-5 text-[#F5F5F5]/85">{errorMessage}</p>
      <button
        type="button"
        onClick={() => void runBootstrap()}
        disabled={isRetrying}
        className="shrink-0 rounded-xl bg-[#E63946] px-3 py-2 text-xs font-bold text-white disabled:opacity-60"
      >
        {isRetrying ? "در حال تلاش" : "تلاش دوباره"}
      </button>
    </div>
  );
}
