"use client";

import { useEffect, useState } from "react";
import { Check, ChevronLeft, Copy, FileText, MessageSquare, User, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { getProfile, type BootstrapProfile } from "@/lib/api";
import { formatPrice, toPersianDigits } from "@/lib/utils";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<BootstrapProfile | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getProfile().then(setProfile).catch((error) => console.error("Profile load failed:", error));
  }, []);

  const copyId = async () => {
    const id = profile?.user.telegramId;
    if (!id) return;

    await navigator.clipboard.writeText(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fullName = `${profile?.user.firstName || "کاربر"} ${profile?.user.lastName || ""}`.trim();

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32">
      <header className="p-5 pt-6 flex justify-center items-center relative">
        <h1 className="text-base font-bold text-[#F5F5F5]">پروفایل</h1>
      </header>

      <main className="px-5 mt-2">
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="w-20 h-20 bg-[#33383F] rounded-full flex items-center justify-center border-2 border-[#33383F] shadow-lg overflow-hidden">
            {profile?.user.photoUrl ? <img src={profile.user.photoUrl} alt="" className="w-full h-full object-cover" /> : <User className="w-10 h-10 text-[#F5F5F5]/70" />}
          </div>
          <div className="text-center">
            <h2 className="text-lg font-bold text-[#F5F5F5]">{fullName}</h2>

            <div onClick={copyId} className="flex items-center justify-center gap-2 mt-2 bg-[#0B1D33] border border-[#33383F] px-3 py-1 rounded-lg cursor-pointer hover:bg-[#1E3C5A]/50 active:scale-95 transition-all">
              <span className="text-xs text-[#F5F5F5]/70 font-mono">ID: {profile?.user.telegramId || "نامشخص"}</span>
              {copied ? <Check className="w-3 h-3 text-[#1E3C5A]" /> : <Copy className="w-3 h-3 text-[#F5F5F5]/50" />}
            </div>
          </div>
        </div>

        <div className="flex justify-between items-center border-y border-[#33383F]/80 py-4 mb-8 px-4">
          <div className="flex flex-col items-center gap-1">
            <span className="text-lg font-bold text-[#F5F5F5]">{toPersianDigits(profile?.orderCount || 0)}</span>
            <span className="text-[10px] text-[#F5F5F5]/50">سفارش</span>
          </div>
          <div className="h-8 w-px bg-[#33383F]" />
          <div className="flex flex-col items-center gap-1">
            <span className="text-lg font-bold text-[#F5F5F5]">{toPersianDigits(profile?.activeOrderCount || 0)}</span>
            <span className="text-[10px] text-[#F5F5F5]/50">سرویس فعال</span>
          </div>
          <div className="h-8 w-px bg-[#33383F]" />
          <div className="flex flex-col items-center gap-1 cursor-pointer hover:opacity-80 active:scale-95" onClick={() => router.push("/finance")}>
            <span className="text-lg font-bold text-[#F5F5F5]">{formatPrice(profile?.walletBalance || 0)}</span>
            <span className="text-[10px] text-[#F5F5F5]/50">تومان موجودی</span>
          </div>
        </div>

        <div className="space-y-1 mb-8">
          <button onClick={() => router.push("/orders")} className="w-full flex items-center justify-between p-4 hover:bg-[#0B1D33] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <FileText className="w-5 h-5 text-[#F5F5F5]/70" />
              <span className="text-sm font-medium text-[#F5F5F5]/90">سفارش‌های من</span>
            </div>
            <ChevronLeft className="w-5 h-5 text-[#F5F5F5]/50" />
          </button>

          <button onClick={() => router.push("/support")} className="w-full flex items-center justify-between p-4 hover:bg-[#0B1D33] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <MessageSquare className="w-5 h-5 text-[#F5F5F5]/70" />
              <span className="text-sm font-medium text-[#F5F5F5]/90">تیکت‌های پشتیبانی</span>
            </div>
            <ChevronLeft className="w-5 h-5 text-[#F5F5F5]/50" />
          </button>

          <button onClick={() => router.push("/invite")} className="w-full flex items-center justify-between p-4 hover:bg-[#0B1D33] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <Users className="w-5 h-5 text-[#F5F5F5]/70" />
              <span className="text-sm font-medium text-[#F5F5F5]/90">دعوت از دوستان</span>
            </div>
            <span className="text-[10px] font-bold text-[#E63946]">کسب درآمد</span>
          </button>
        </div>

        <button onClick={() => window.Telegram?.WebApp?.close()} className="w-full text-[#E63946] font-bold text-sm py-4 rounded-2xl hover:bg-[#E63946]/10 transition-all cursor-pointer active:scale-95">
          بستن برنامه
        </button>
      </main>
    </div>
  );
}