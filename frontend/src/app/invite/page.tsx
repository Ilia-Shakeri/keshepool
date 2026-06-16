"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Gift, Share2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { getTelegramUserId, apiFetch } from "@/lib/api";

export default function InvitePage() {
  const router = useRouter();
  const [inviteLink, setInviteLink] = useState("");
  const [copied, setCopied] = useState(false);
  
  useEffect(() => {
    const telegramUserId = getTelegramUserId();
    
    apiFetch<{botUsername: string}>("/config")
      .then(res => {
        const botUsername = res.botUsername || "keshepoolbot";
        setInviteLink(`https://t.me/${botUsername}?start=ref_${telegramUserId || "guest"}`);
      })
      .catch(error => {
        console.error("Config fetch failed:", error);
        setInviteLink(`https://t.me/keshepoolbot?start=ref_${telegramUserId || "guest"}`);
      });
  }, []);

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(inviteLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error("Clipboard copy failed:", error);
    }
  };

  const handleForwardLink = () => {
    if (!inviteLink) return;
    window.Telegram?.WebApp?.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(inviteLink)}&text=${encodeURIComponent("دعوت به Keshepool")}`);
  };

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32 relative">
      <header className="flex justify-between items-center p-5 pt-6 bg-[#0F0F10]/80 backdrop-blur-md sticky top-0 z-40 border-b border-[#33383F]/50 mb-6">
        <h1 className="text-base font-bold text-[#E63946]">دعوت از دوستان</h1>
        <button onClick={() => router.back()} className="text-[#F5F5F5]/70 hover:text-[#F5F5F5] transition-colors bg-[#33383F] px-4 py-1.5 rounded-xl text-xs font-medium cursor-pointer active:scale-95">
          بازگشت
        </button>
      </header>

      <main className="flex flex-col items-center gap-5 w-full px-5 mt-8">
        <div className="w-24 h-24 bg-[#E63946]/10 rounded-full flex items-center justify-center mb-2 shadow-lg shadow-[#E63946]/10 border border-[#E63946]/20 relative">
          <div className="absolute inset-0 rounded-full bg-[#E63946]/20 animate-ping opacity-20" />
          <Gift className="w-12 h-12 text-[#E63946] relative z-10" />
        </div>

        <p className="text-center text-sm text-[#F5F5F5]/80 leading-relaxed mb-6 px-4">
          با دعوت از هر دوست، <span className="text-[#E63946] font-bold">تخفیف ویژه و اعتبار</span> دریافت کنید.
        </p>

        <div className="w-full space-y-4">
          <div>
            <label className="text-xs text-[#F5F5F5]/70 mb-2 block font-medium">لینک دعوت اختصاصی شما:</label>
            <div className="w-full bg-[#0B1D33] p-3 rounded-2xl border border-[#33383F] flex items-center justify-between gap-3 shadow-inner">
              <span className="text-xs text-[#F5F5F5]/80 truncate dir-ltr select-all font-mono opacity-80">{inviteLink}</span>
              <Button onClick={handleCopyLink} size="icon" className={`shrink-0 shadow-lg rounded-xl transition-all cursor-pointer active:scale-90 ${copied ? "bg-[#1E3C5A] hover:bg-[#1E3C5A]/80" : "bg-[#E63946] hover:bg-[#E63946]/90"} text-[#F5F5F5]`}>
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              </Button>
            </div>
            {copied && <span className="text-[10px] text-[#1E3C5A] block mt-2 text-center animate-fade-in">لینک دعوت با موفقیت کپی شد!</span>}
          </div>

          <Button onClick={handleForwardLink} className="w-full bg-[#33383F] hover:bg-[#33383F]/80 text-[#F5F5F5] py-6 rounded-2xl text-sm font-bold shadow-lg transition-all active:scale-95 cursor-pointer mt-4 flex gap-2 border-none">
            ارسال برای دوستان در تلگرام <Share2 className="w-4 h-4" />
          </Button>
        </div>
      </main>
    </div>
  );
}