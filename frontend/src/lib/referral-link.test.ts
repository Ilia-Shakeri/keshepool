import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { buildInviteLink } from "../features/referrals/invite-link.ts";


const OPAQUE_CODE = "0123456789abcdef0123456789abcdef";


test("invite link uses only a fixed opaque referral code", () => {
  assert.equal(
    buildInviteLink("@Keshepool_bot", OPAQUE_CODE),
    `https://t.me/Keshepool_bot?startapp=ref_${OPAQUE_CODE}`,
  );
  for (const invalidCode of ["42", "00042", OPAQUE_CODE.toUpperCase(), `${OPAQUE_CODE}0`, ""]) {
    assert.equal(buildInviteLink("Keshepool_bot", invalidCode), null);
  }
  assert.equal(buildInviteLink("bad/name", OPAQUE_CODE), null);
});


test("invite screen never falls back to browser Telegram identity", () => {
  const source = readFileSync(
    resolve(process.cwd(), "src", "app", "invite", "page.tsx"),
    "utf8",
  );
  assert.doesNotMatch(source, /getTelegramUserId/);
  assert.doesNotMatch(source, /telegramUserId/);
  assert.match(source, /profile\.user\.referralCode/);
  assert.match(source, /buildInviteLink/);
});
