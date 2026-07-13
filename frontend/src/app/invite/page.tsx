"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Copy, Gift, Share2 } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { getPublicConfig, getTelegramUserId } from "@/lib/api";
import { copyText } from "@/lib/clipboard";

export default function InvitePage() {
  const [inviteLink, setInviteLink] = useState("");
  const [copied, setCopied] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadInviteLink = useCallback(async () => {
    setLoadError(null);
    try {
      const config = await getPublicConfig();
      const botUsername = config.botUsername?.replace(/^@/, "");
      const telegramUserId = getTelegramUserId();
      if (!botUsername) throw new Error("نام کاربری ربات تنظیم نشده است.");
      setInviteLink(
        telegramUserId
          ? `https://t.me/${botUsername}?startapp=ref_${telegramUserId}`
          : `https://t.me/${botUsername}`,
      );
    } catch (error) {
      setInviteLink("");
      setLoadError(error instanceof Error ? error.message : "لینک دعوت آماده نشد.");
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadInviteLink);
  }, [loadInviteLink]);

  const handleCopyLink = async () => {
    try {
      if (!inviteLink) return;
      if (await copyText(inviteLink)) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2500);
      } else {
        window.Telegram?.WebApp?.showAlert(`لینک را دستی کپی کنید:\n${inviteLink}`);
      }
    } catch {
      window.Telegram?.WebApp?.showAlert(`لینک را دستی کپی کنید:\n${inviteLink}`);
    }
  };

  const handleShare = () => {
    if (!inviteLink) return;
    window.Telegram?.WebApp?.openTelegramLink(
      `https://t.me/share/url?url=${encodeURIComponent(inviteLink)}&text=${encodeURIComponent("دوستت رو دعوت کن و کشه‌پول را با هم تجربه کنیم 🎁")}`
    );
  };

  return (
    <div className="min-h-[100dvh] pb-32 font-sans text-[#F5F5F5]">
      <PageHeader title="دعوت از دوستان" />

      <main className="mx-auto mt-4 flex max-w-lg flex-col items-center gap-6 px-5">
        {/* Gift icon */}
        <div className="relative">
          <div
            className="w-24 h-24 rounded-3xl flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, rgba(230,57,70,0.15) 0%, rgba(230,57,70,0.05) 100%)",
              border: "1px solid rgba(230,57,70,0.2)",
              boxShadow: "0 0 40px rgba(230,57,70,0.1)",
            }}
          >
            <Gift className="w-10 h-10 text-[#E63946]" />
          </div>
        </div>

        <div className="text-center">
          <h2 className="text-lg font-bold text-[#F5F5F5] mb-2">دوست‌هایت را دعوت کن</h2>
          <p className="text-sm text-[#F5F5F5]/50 leading-relaxed max-w-xs mx-auto">
            این لینک، دعوت شما را هنگام ورود دوستتان ثبت می‌کند. ثبت دعوت به‌تنهایی به معنی پاداش مالی قطعی نیست.
          </p>
        </div>

        {/* Invite link */}
        <div className="w-full space-y-3">
          <div
            className="w-full rounded-2xl p-3.5 flex items-center justify-between gap-3"
            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)" }}
          >
            <button
              onClick={handleCopyLink}
              className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-all active:scale-90"
              style={
                copied
                  ? { background: "rgba(16,185,129,0.15)", border: "1px solid rgba(16,185,129,0.25)" }
                  : { background: "rgba(230,57,70,0.15)", border: "1px solid rgba(230,57,70,0.25)" }
              }
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-[#E63946]" />}
            </button>
            <span className="text-xs text-[#F5F5F5]/60 truncate dir-ltr font-mono flex-1 text-right">
              {inviteLink || (loadError ? "لینک در دسترس نیست" : "در حال بارگذاری...")}
            </span>
          </div>

          {loadError && (
            <div className="text-center text-xs text-[#E63946]">
              <p>{loadError}</p>
              <button type="button" onClick={() => void loadInviteLink()} className="mt-2 rounded-xl px-4 font-bold">تلاش دوباره</button>
            </div>
          )}

          {copied && (
            <p className="text-center text-xs text-emerald-400">لینک کپی شد!</p>
          )}

          <button
            onClick={handleShare}
            className="w-full py-4 rounded-2xl text-sm font-bold transition-all active:scale-95 flex items-center justify-center gap-2"
            style={{ background: "rgba(255,255,255,0.07)", color: "#F5F5F5", border: "1px solid rgba(255,255,255,0.1)" }}
          >
            <Share2 className="w-4 h-4" />
            ارسال برای دوستان در تلگرام
          </button>
        </div>
      </main>
    </div>
  );
}
