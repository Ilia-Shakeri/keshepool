const BOT_USERNAME_PATTERN = /^[A-Za-z0-9_]{5,32}$/;
const REFERRAL_CODE_PATTERN = /^[0-9a-f]{32}$/;


export function buildInviteLink(
  rawBotUsername: string | null | undefined,
  referralCode: string | null | undefined,
): string | null {
  const botUsername = rawBotUsername?.replace(/^@/, "") || "";
  if (!BOT_USERNAME_PATTERN.test(botUsername) || !REFERRAL_CODE_PATTERN.test(referralCode || "")) {
    return null;
  }
  return `https://t.me/${botUsername}?startapp=ref_${referralCode}`;
}
