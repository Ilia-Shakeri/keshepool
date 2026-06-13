"use client";

import { useEffect, useState } from "react";
import { Gift, Copy, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function InvitePage() {
  const router = useRouter();
  const [inviteLink, setInviteLink] = useState("https://t.me/keshepoolbot?start=ref_generic");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Dynamically retrieve Telegram execution contexts to identify specific users
    if (typeof window !== "undefined") {
      const telegramUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      if (telegramUserId) {
        setInviteLink(`https://t.me/keshepoolbot?start=ref_${telegramUserId}`);
      }
    }
  }, []);

  // Safe programmatic interaction layer with device string clipboards
  const handleCopyLink = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(inviteLink);
      } else {
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

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans pb-32 relative">
      <header className="flex justify-between items-center p-4 bg-zinc-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-zinc-800/50 mb-6 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-emerald-400">دعوت از دوستان</h1>
        <button onClick={() => router.back()} className="text-zinc-400 hover:text-white transition-colors bg-zinc-800/50 px-4 py-1.5 rounded-xl text-sm font-medium">
          بازگشت
        </button>
      </header>

      <main className="flex flex-col items-center gap-5 w-full px-4 max-w-lg mx-auto mt-4">
        <div className="w-24 h-24 bg-emerald-500/10 rounded-full flex items-center justify-center mb-2 shadow-lg shadow-emerald-500/10 border border-emerald-500/20 relative">
          <div className="absolute inset-0 rounded-full bg-emerald-400/20 animate-ping opacity-20"></div>
          <Gift className="w-12 h-12 text-emerald-400 relative z-10" />
        </div>
        
        <p className="text-center text-sm text-zinc-300 leading-relaxed mb-4 px-2">
          با دعوت از هر دوست، <span className="text-emerald-400 font-bold">تخفیف ویژه</span> دریافت کنید.
        </p>
        
        <div className="w-full">
          <label className="text-xs text-zinc-400 mb-2 block text-right">لینک دعوت اختصاصی شما:</label>
          <div className="w-full bg-zinc-900 p-4 rounded-2xl border border-zinc-700 flex items-center justify-between gap-3 shadow-inner">
            <span className="text-xs text-zinc-400 truncate dir-ltr select-all font-mono">{inviteLink}</span>
            <Button 
              onClick={handleCopyLink}
              size="icon" 
              className={`shrink-0 shadow-lg rounded-xl transition-all ${copied ? 'bg-green-600 hover:bg-green-500' : 'bg-emerald-500 hover:bg-emerald-400'} text-white`}
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
          {copied && (
            <span className="text-xs text-green-400 block text-right mt-1 animate-fade-in">لینک دعوت با موفقیت کپی شد!</span>
          )}
        </div>
      </main>
    </div>
  );
}