import type { TelegramBackButton } from "@/types/telegram";

type BackHandler = () => void;
type BackButtonResolver = () => TelegramBackButton | undefined;

export function createTelegramBackManager(resolveBackButton: BackButtonResolver) {
  const handlers: BackHandler[] = [];
  let attachedBackButton: TelegramBackButton | null = null;

  const dispatchBack = () => {
    handlers[handlers.length - 1]?.();
  };

  const sync = () => {
    const backButton = resolveBackButton();
    if (handlers.length > 0 && backButton) {
      if (attachedBackButton !== backButton) {
        attachedBackButton?.offClick(dispatchBack);
        backButton.onClick(dispatchBack);
        attachedBackButton = backButton;
      }
      backButton.show();
      return;
    }

    if (handlers.length === 0) {
      attachedBackButton?.offClick(dispatchBack);
      attachedBackButton?.hide();
      attachedBackButton = null;
    }
  };

  return {
    register(handler: BackHandler): () => void {
      handlers.push(handler);
      sync();

      return () => {
        const index = handlers.lastIndexOf(handler);
        if (index >= 0) handlers.splice(index, 1);
        sync();
      };
    },
  };
}

export const telegramBackManager = createTelegramBackManager(
  () => window.Telegram?.WebApp?.BackButton,
);
