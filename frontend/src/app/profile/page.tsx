"use client";

import { useEffect, useState } from "react";
import { User, ChevronLeft, Users, MessageSquare, FileText, Copy, Check } from "lucide-react";
import { useRouter } from "next/navigation";
import { toPersianDigits } from "@/lib/utils";

export default function ProfilePage() {
  const router = useRouter();
  const [tgUser, setTgUser] = useState<{ id?: number; first_name?: string; last_name?: string } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && window.Telegram?.WebApp) {
      const userPayload = window.Telegram.WebApp.initDataUnsafe?.user;
      if (userPayload) {
        setTgUser(userPayload);
      }
    }
  }, []);

  const copyId = async () => {
    if (tgUser?.id) {
      await navigator.clipboard.writeText(tgUser.id.toString());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32">
      <header className="p-5 pt-6 flex justify-center items-center relative">
        <h1 className="text-base font-bold text-[#F5F5F5]">پروفایل</h1>
      </header>

      <main className="px-5 mt-2">
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="w-20 h-20 bg-[#33383F] rounded-full flex items-center justify-center border-2 border-[#33383F] shadow-lg">
            <User className="w-10 h-10 text-[#F5F5F5]/70" />
          </div>
          <div className="text-center">
            <h2 className="text-lg font-bold text-[#F5F5F5]">{tgUser?.first_name || "کاربر"} {tgUser?.last_name || ""}</h2>
            
            <div 
              onClick={copyId}
              className="flex items-center justify-center gap-2 mt-2 bg-[#0B1D33] border border-[#33383F] px-3 py-1 rounded-lg cursor-pointer hover:bg-[#1E3C5A]/50 active:scale-95 transition-all"
            >
              <span className="text-xs text-[#F5F5F5]/70 font-mono">ID: {tgUser?.id || "نامشخص"}</span>
              {copied ? <Check className="w-3 h-3 text-[#1E3C5A]" /> : <Copy className="w-3 h-3 text-[#F5F5F5]/50" />}
            </div>
          </div>
        </div>

        <div className="flex justify-between items-center border-y border-[#33383F]/80 py-4 mb-8 px-4">
          <div className="flex flex-col items-center gap-1">
            <span className="text-lg font-bold text-[#F5F5F5]">{toPersianDigits(12)}</span>
            <span className="text-[10px] text-[#F5F5F5]/50">سفارش</span>
          </div>
          <div className="h-8 w-px bg-[#33383F]"></div>
          <div className="flex flex-col items-center gap-1">
            <span className="text-lg font-bold text-[#F5F5F5]">{toPersianDigits(8)}</span>
            <span className="text-[10px] text-[#F5F5F5]/50">سرویس فعال</span>
          </div>
          <div className="h-8 w-px bg-[#33383F]"></div>
          <div className="flex flex-col items-center gap-1 cursor-pointer hover:opacity-80 active:scale-95" onClick={() => router.push('/finance')}>
            <span className="text-lg font-bold text-[#F5F5F5]">{toPersianDigits("820")} هزار</span>
            <span className="text-[10px] text-[#F5F5F5]/50">تومان موجودی</span>
          </div>
        </div>

        <div className="space-y-1 mb-8">
          <button className="w-full flex items-center justify-between p-4 hover:bg-[#0B1D33] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <User className="w-5 h-5 text-[#F5F5F5]/70" />
              <span className="text-sm font-medium text-[#F5F5F5]/90">اطلاعات حساب کاربری</span>
            </div>
            <ChevronLeft className="w-5 h-5 text-[#F5F5F5]/50" />
          </button>
          
          <button onClick={() => router.push('/orders')} className="w-full flex items-center justify-between p-4 hover:bg-[#0B1D33] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <FileText className="w-5 h-5 text-[#F5F5F5]/70" />
              <span className="text-sm font-medium text-[#F5F5F5]/90">سفارش‌های من</span>
            </div>
            <ChevronLeft className="w-5 h-5 text-[#F5F5F5]/50" />
          </button>

          <button onClick={() => router.push('/support')} className="w-full flex items-center justify-between p-4 hover:bg-[#0B1D33] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <MessageSquare className="w-5 h-5 text-[#F5F5F5]/70" />
              <span className="text-sm font-medium text-[#F5F5F5]/90">تیکت‌های پشتیبانی</span>
            </div>
            <ChevronLeft className="w-5 h-5 text-[#F5F5F5]/50" />
          </button>

          <button onClick={() => router.push('/invite')} className="w-full flex items-center justify-between p-4 hover:bg-[#0B1D33] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <Users className="w-5 h-5 text-[#F5F5F5]/70" />
              <span className="text-sm font-medium text-[#F5F5F5]/90">دعوت از دوستان</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-bold text-[#E63946]">کسب درآمد <ChevronLeft className="w-3 h-3 inline" /></span>
            </div>
          </button>
        </div>

        <button 
          onClick={() => window.Telegram?.WebApp?.close()}
          className="w-full text-[#E63946] font-bold text-sm py-4 rounded-2xl hover:bg-[#E63946]/10 transition-all cursor-pointer active:scale-95"
        >
          بستن برنامه
        </button>
      </main>
    </div>
  );
}