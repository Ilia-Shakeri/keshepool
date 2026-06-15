"use client";

import { useEffect, useState } from "react";
import { Gift, Copy, Share2, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function InvitePage() {
  const router = useRouter();
  const [inviteLink, setInviteLink] = useState("https://t.me/keshepoolbot?start=ref_generic");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Dynamically retrieve Telegram execution contexts
    if (typeof window !== "undefined") {
      const telegramUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      if (telegramUserId) {
        setInviteLink(`https://t.me/keshepoolbot?start=ref_${telegramUserId}`);
      }
    }
  }, []);

  const handleCopyLink = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(inviteLink);
      } else {
        // Fallback injection buffer for structural copy context
        const structuralFallbackBuffer = document.createElement("textarea");
        structuralFallbackBuffer.value = inviteLink;
        structuralFallbackBuffer.style.position = "fixed";
        document.body.appendChild(structuralFallbackBuffer);
        structuralFallbackBuffer.focus();
        structuralFallbackBuffer.select();
        document.execCommand("copy");
        document.body.removeChild(structuralFallbackBuffer);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed executing system text clipboard transaction context: ", err);
    }
  };

  const handleForwardLink = () => {
    if (typeof window !== "undefined" && window.Telegram?.WebApp) {
      const message = `سلام! با لینک زیر وارد ربات شو و تخفیف بگیر:\n${inviteLink}`;
      window.Telegram.WebApp.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(inviteLink)}&text=${encodeURIComponent('دعوت به Keshepool')}`);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-white font-sans pb-32 relative">
      <header className="flex justify-between items-center p-5 pt-6 bg-[#0a0a0c]/80 backdrop-blur-md sticky top-0 z-40 border-b border-zinc-800/50 mb-6">
        <h1 className="text-base font-bold text-red-500">دعوت از دوستان</h1>
        <button onClick={() => router.back()} className="text-zinc-400 hover:text-white transition-colors bg-zinc-900 px-4 py-1.5 rounded-xl text-xs font-medium cursor-pointer active:scale-95">
          بازگشت
        </button>
      </header>

      <main className="flex flex-col items-center gap-5 w-full px-5 mt-8">
        <div className="w-24 h-24 bg-red-500/10 rounded-full flex items-center justify-center mb-2 shadow-lg shadow-red-500/10 border border-red-500/20 relative">
          <div className="absolute inset-0 rounded-full bg-red-400/20 animate-ping opacity-20"></div>
          <Gift className="w-12 h-12 text-red-500 relative z-10" />
        </div>
        
        <p className="text-center text-sm text-zinc-300 leading-relaxed mb-6 px-4">
          با دعوت از هر دوست، <span className="text-red-500 font-bold">تخفیف ویژه و اعتبار</span> دریافت کنید.
        </p>
        
        <div className="w-full space-y-4">
          <div>
            <label className="text-xs text-zinc-400 mb-2 block font-medium">لینک دعوت اختصاصی شما:</label>
            <div className="w-full bg-[#121217] p-3 rounded-2xl border border-zinc-800 flex items-center justify-between gap-3 shadow-inner">
              <span className="text-xs text-zinc-300 truncate dir-ltr select-all font-mono opacity-80">{inviteLink}</span>
              <Button 
                onClick={handleCopyLink}
                size="icon" 
                className={`shrink-0 shadow-lg rounded-xl transition-all cursor-pointer active:scale-90 ${copied ? 'bg-green-600 hover:bg-green-500' : 'bg-red-600 hover:bg-red-500'} text-white`}
              >
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              </Button>
            </div>
            {copied && (
              <span className="text-[10px] text-green-400 block mt-2 text-center animate-fade-in">لینک دعوت با موفقیت کپی شد!</span>
            )}
          </div>

          <Button 
            onClick={handleForwardLink}
            className="w-full bg-zinc-800 hover:bg-zinc-700 text-white py-6 rounded-2xl text-sm font-bold shadow-lg transition-all active:scale-95 cursor-pointer mt-4 flex gap-2"
          >
            ارسال برای دوستان در تلگرام <Share2 className="w-4 h-4" />
          </Button>
        </div>
      </main>
    </div>
  );
}