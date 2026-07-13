"use client";

import { useEffect, useLayoutEffect, useRef } from "react";
import { telegramBackManager } from "@/lib/telegram-back";

type BackHandler = () => void;

export function useTelegramBackButton(handler: BackHandler, enabled = true) {
  const handlerRef = useRef(handler);

  useLayoutEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => {
    if (!enabled) return;
    return telegramBackManager.register(() => handlerRef.current());
  }, [enabled]);
}
