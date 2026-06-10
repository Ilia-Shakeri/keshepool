"use client";

import { User, LogOut, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function ProfilePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans p-4 max-w-lg mx-auto pb-32">
      <header className="flex justify-between items-center mb-8 border-b border-slate-800/50 pb-4">
        <h1 className="text-xl font-bold text-cyan-400">پروفایل کاربری</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors flex items-center gap-1">
          بازگشت <ChevronRight className="w-5 h-5" />
        </button>
      </header>

      <div className="flex flex-col items-center gap-6 w-full pt-4">
        <div className="relative">
          <div className="w-24 h-24 bg-slate-800 rounded-full border-2 border-cyan-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <User className="w-12 h-12 text-cyan-400" />
          </div>
          <div className="absolute bottom-0 right-0 bg-cyan-500 text-white text-[10px] px-2 py-1 rounded-full font-bold">VIP</div>
        </div>
        <div className="text-center w-full">
          <h3 className="text-xl font-bold text-white">ایلیا شاکری</h3>
          <p className="text-sm text-slate-400">0912***1234</p>
        </div>
        <div className="w-full bg-slate-800/50 rounded-xl p-4 border border-slate-700 flex justify-between items-center">
          <span className="text-sm text-slate-300">موجودی کیف پول</span>
          <span className="text-lg font-bold text-cyan-400 flex items-center gap-1">
            ۰ <span className="text-xs font-normal">تومان</span>
          </span>
        </div>
        <Button className="w-full bg-slate-800 hover:bg-slate-700 text-red-400 border border-red-500/20 flex items-center gap-2 py-6 rounded-xl mt-4">
          <LogOut className="w-5 h-5" /> خروج از حساب
        </Button>
      </div>
    </div>
  );
}