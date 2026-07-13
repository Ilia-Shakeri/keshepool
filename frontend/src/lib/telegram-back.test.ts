import assert from "node:assert/strict";
import test from "node:test";
import type { TelegramBackButton } from "../types/telegram.ts";
import { createTelegramBackManager } from "./telegram-back.ts";

test("Telegram back uses the top view and cleans up the shared button", () => {
  let clickHandler: (() => void) | null = null;
  let showCount = 0;
  let hideCount = 0;
  let attachCount = 0;
  let detachCount = 0;
  const calls: string[] = [];

  const backButton = {
    isVisible: false,
    show: () => { showCount += 1; },
    hide: () => { hideCount += 1; },
    onClick: (handler: () => void) => {
      attachCount += 1;
      clickHandler = handler;
    },
    offClick: (handler: () => void) => {
      detachCount += 1;
      if (clickHandler === handler) clickHandler = null;
    },
  } satisfies TelegramBackButton;

  const manager = createTelegramBackManager(() => backButton);
  const removePage = manager.register(() => calls.push("page"));
  const removeModal = manager.register(() => calls.push("modal"));
  assert.ok(clickHandler);
  (clickHandler as () => void)();
  removeModal();
  assert.ok(clickHandler);
  (clickHandler as () => void)();
  removePage();

  assert.deepEqual(calls, ["modal", "page"]);
  assert.equal(attachCount, 1);
  assert.equal(detachCount, 1);
  assert.equal(showCount, 3);
  assert.equal(hideCount, 1);
  assert.equal(clickHandler, null);
});
