"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Gift, Share2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { getTelegramUserId, apiFetch } from "@/lib/api";

export default function InvitePage() {
  const router = useRouter();
  const [inviteLink, setInviteLink] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const telegramUserId = getTelegramUserId();
    apiFetch<{ botUsername: string }>("/config")
      .then((res) => {
        const botUsername = res.botUsername || "keshepoolbot";
        setInviteLink(`https://t.me/${botUsername}?start=ref_${telegramUserId || "guest"}`);
      })
      .catch(() => {
        setInviteLink(`https://t.me/keshepoolbot?start=ref_${getTelegramUserId() || "guest"}`);
      });
  }, []);

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(inviteLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (error) {
      console.error("Clipboard copy failed:", error);
    }
  };

  const handleShare = () => {
    if (!inviteLink) return;
    window.Telegram?.WebApp?.openTelegramLink(
      `https://t.me/share/url?url=${encodeURIComponent(inviteLink)}&text=${encodeURIComponent("دوستت رو دعوت کن و کشه‌پول را با هم تجربه کنیم 🎁")}`
    );
  };

  return (
    <div className="min-h-screen text-[#F5F5F5] font-sans pb-32">
      <header className="px-5 py-4 flex justify-between items-center">
        <h1 className="text-base font-bold text-[#F5F5F5]">دعوت از دوستان</h1>
        <button
          onClick={() => router.back()}
          className="text-[#F5F5F5]/50 text-xs px-3 py-1.5 rounded-xl transition-colors hover:text-[#F5F5F5] hover:bg-white/[0.06]"
        >
          بازگشت
        </button>
      </header>

      <main className="px-5 flex flex-col items-center gap-6 mt-4">
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
            برای هر دوستی که دعوت کنی، <span className="text-[#E63946] font-semibold">تخفیف و اعتبار</span> هدیه می‌گیری.
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
              {inviteLink || "در حال بارگذاری..."}
            </span>
          </div>

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
