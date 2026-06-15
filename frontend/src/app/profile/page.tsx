"use client";

import { useEffect, useState } from "react";
import { User, ChevronLeft, Settings, Users, MessageSquare, FileText, LogOut, Copy, Check } from "lucide-react";
import { useRouter } from "next/navigation";

export default function ProfilePage() {
  const router = useRouter();
  
  const [tgUser, setTgUser] = useState<{ id?: number; first_name?: string; last_name?: string } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Parse WebApp payload context for user profile rendering
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
    <div className="min-h-screen bg-[#0a0a0c] text-white font-sans pb-32">
      <header className="p-5 pt-6 flex justify-center items-center relative">
        <h1 className="text-base font-bold text-white">پروفایل</h1>
      </header>

      <main className="px-5 mt-2">
        {/* User Info Extracted from Telegram */}
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="w-20 h-20 bg-zinc-800 rounded-full flex items-center justify-center border-2 border-zinc-700 shadow-lg">
            <User className="w-10 h-10 text-zinc-400" />
          </div>
          <div className="text-center">
            <h2 className="text-lg font-bold text-white">{tgUser?.first_name || "کاربر"} {tgUser?.last_name || ""}</h2>
            
            <div 
              onClick={copyId}
              className="flex items-center justify-center gap-2 mt-2 bg-zinc-900 border border-zinc-800 px-3 py-1 rounded-lg cursor-pointer hover:bg-zinc-800 active:scale-95 transition-all"
            >
              <span className="text-xs text-zinc-400 font-mono">ID: {tgUser?.id || "نامشخص"}</span>
              {copied ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3 text-zinc-500" />}
            </div>
          </div>
        </div>

        {/* Stats Row */}
        <div className="flex justify-between items-center border-y border-zinc-800/80 py-4 mb-8 px-4">
          <div className="flex flex-col items-center gap-1">
            <span className="text-lg font-bold text-white">12</span>
            <span className="text-[10px] text-zinc-500">سفارش</span>
          </div>
          <div className="h-8 w-px bg-zinc-800"></div>
          <div className="flex flex-col items-center gap-1">
            <span className="text-lg font-bold text-white">8</span>
            <span className="text-[10px] text-zinc-500">سرویس فعال</span>
          </div>
          <div className="h-8 w-px bg-zinc-800"></div>
          <div className="flex flex-col items-center gap-1 cursor-pointer hover:opacity-80 active:scale-95" onClick={() => router.push('/finance')}>
            <span className="text-lg font-bold text-white">820K</span>
            <span className="text-[10px] text-zinc-500">تومان موجودی</span>
          </div>
        </div>

        {/* Menu Links with hover states and pointers */}
        <div className="space-y-1 mb-8">
          <button className="w-full flex items-center justify-between p-4 hover:bg-[#121217] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <User className="w-5 h-5 text-zinc-400" />
              <span className="text-sm font-medium text-zinc-200">اطلاعات حساب کاربری</span>
            </div>
            <ChevronLeft className="w-5 h-5 text-zinc-600" />
          </button>
          
          <button onClick={() => router.push('/orders')} className="w-full flex items-center justify-between p-4 hover:bg-[#121217] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <FileText className="w-5 h-5 text-zinc-400" />
              <span className="text-sm font-medium text-zinc-200">سفارش‌های من</span>
            </div>
            <ChevronLeft className="w-5 h-5 text-zinc-600" />
          </button>

          <button onClick={() => router.push('/support')} className="w-full flex items-center justify-between p-4 hover:bg-[#121217] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <MessageSquare className="w-5 h-5 text-zinc-400" />
              <span className="text-sm font-medium text-zinc-200">تیکت‌های پشتیبانی</span>
            </div>
            <ChevronLeft className="w-5 h-5 text-zinc-600" />
          </button>

          <button onClick={() => router.push('/invite')} className="w-full flex items-center justify-between p-4 hover:bg-[#121217] rounded-2xl transition-all cursor-pointer active:scale-[0.98]">
            <div className="flex items-center gap-4">
              <Users className="w-5 h-5 text-zinc-400" />
              <span className="text-sm font-medium text-zinc-200">دعوت از دوستان</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-bold text-red-500">کسب درآمد <ChevronLeft className="w-3 h-3 inline" /></span>
            </div>
          </button>
        </div>

        {/* Logout */}
        <button 
          onClick={() => window.Telegram?.WebApp?.close()}
          className="w-full text-red-500 font-bold text-sm py-4 rounded-2xl hover:bg-red-500/10 transition-all cursor-pointer active:scale-95"
        >
          بستن برنامه
        </button>
      </main>
    </div>
  );
}