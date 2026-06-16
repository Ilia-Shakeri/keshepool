"use client";

import { useEffect } from "react";
import { bootstrapUser } from "@/lib/api";

export default function TelegramBootstrap() {
  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) return;

    webApp.expand();
    webApp.ready();

    const startParam = webApp.initDataUnsafe?.start_param || "";
    const referrerTelegramId = startParam.startsWith("ref_") ? startParam.replace("ref_", "") : null;

    bootstrapUser(referrerTelegramId).catch((error) => {
      console.error("User bootstrap failed:", error);
    });
  }, []);

  return null;
}