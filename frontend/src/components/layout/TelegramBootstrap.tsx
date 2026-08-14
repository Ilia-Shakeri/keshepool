"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AUTH_SESSION_EXPIRED_EVENT,
  bootstrapUser,
  resetApiSession,
} from "@/lib/api";

type TelegramLifecycleApi = {
  onEvent?: (event: string, callback: () => void) => void;
  offEvent?: (event: string, callback: () => void) => void;
};

export default function TelegramBootstrap() {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [requiresReopen, setRequiresReopen] = useState(false);

  const runBootstrap = useCallback(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) {
      setErrorMessage("ارتباط با تلگرام برقرار نشد. برنامه را از داخل تلگرام دوباره باز کنید.");
      return Promise.resolve();
    }

    setIsRetrying(true);
    setRequiresReopen(false);
    setErrorMessage(null);
    webApp.expand();
    webApp.ready();

    return bootstrapUser()
      .then(() => undefined)
      .catch((error: unknown) => {
        setErrorMessage(error instanceof Error ? error.message : "نشست کاربری آماده نشد. دوباره تلاش کنید.");
      })
      .finally(() => setIsRetrying(false));
  }, []);

  useEffect(() => {
    const handleAuthExpired = () => {
      setIsRetrying(false);
      setRequiresReopen(true);
      setErrorMessage("نشست شما پایان یافته است. برنامه را ببندید و دوباره از تلگرام باز کنید.");
    };
    const handleActivation = () => {
      resetApiSession();
      void runBootstrap();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") handleActivation();
    };

    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, handleAuthExpired);

    const webApp = window.Telegram?.WebApp;
    const lifecycle = webApp as (typeof webApp & TelegramLifecycleApi) | undefined;
    const hasActivationEvent = (
      typeof lifecycle?.onEvent === "function"
      && typeof lifecycle.offEvent === "function"
    );
    if (hasActivationEvent) {
      lifecycle.onEvent?.("activated", handleActivation);
    } else {
      document.addEventListener("visibilitychange", handleVisibilityChange);
    }

    void Promise.resolve().then(runBootstrap);

    return () => {
      window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, handleAuthExpired);
      if (hasActivationEvent) {
        lifecycle.offEvent?.("activated", handleActivation);
      } else {
        document.removeEventListener("visibilitychange", handleVisibilityChange);
      }
    };
  }, [runBootstrap]);

  const recoverExpiredSession = useCallback(() => {
    resetApiSession();
    const webApp = window.Telegram?.WebApp;
    if (webApp?.initData) {
      webApp.close();
      return;
    }
    window.location.reload();
  }, []);

  if (!errorMessage) return null;

  return (
    <div className="relative z-30 mx-4 mt-3 flex items-center justify-between gap-3 rounded-2xl border border-[#E63946]/30 bg-[#181013]/95 p-3 text-right shadow-xl backdrop-blur-xl sm:mx-auto sm:max-w-xl">
      <p className="min-w-0 flex-1 text-xs leading-5 text-[#F5F5F5]/85">{errorMessage}</p>
      <button
        type="button"
        onClick={requiresReopen ? recoverExpiredSession : () => void runBootstrap()}
        disabled={!requiresReopen && isRetrying}
        className="shrink-0 rounded-xl bg-[#E63946] px-3 py-2 text-xs font-bold text-white disabled:opacity-60"
      >
        {requiresReopen ? "بستن و بازکردن دوباره" : isRetrying ? "در حال تلاش" : "تلاش دوباره"}
      </button>
    </div>
  );
}
