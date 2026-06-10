"use client";

import { Gift, Copy, Users, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function InvitePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans p-4 max-w-lg mx-auto pb-32">
      <header className="flex justify-between items-center mb-8 border-b border-slate-800/50 pb-4">
        <h1 className="text-xl font-bold text-cyan-400">دعوت از دوستان</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors flex items-center gap-1">
          بازگشت <ChevronRight className="w-5 h-5" />
        </button>
      </header>

      <div className="flex flex-col items-center gap-5 w-full pt-4">
        <div className="w-20 h-20 bg-indigo-500/20 rounded-full flex items-center justify-center mb-2 shadow-lg shadow-indigo-500/10 border border-indigo-500/30">
          <Gift className="w-10 h-10 text-indigo-400" />
        </div>
        <p className="text-center text-sm text-slate-300 leading-relaxed mb-4">
          با دعوت از هر دوست، <span className="text-cyan-400 font-bold">۲۰,۰۰۰ تومان</span> اعتبار هدیه بگیرید و دوست شما نیز ۱۰٪ تخفیف خرید اول دریافت میکند.
        </p>
        
        <div className="w-full">
          <label className="text-xs text-slate-400 mb-2 block text-right">لینک دعوت اختصاصی شما:</label>
          <div className="w-full bg-slate-950 p-3 rounded-xl border border-slate-700 flex items-center justify-between gap-2">
            <span className="text-xs text-slate-400 truncate dir-ltr select-all">https://t.me/ZoodSubBot?start=ref_8912</span>
            <Button size="icon" className="bg-cyan-500 hover:bg-cyan-400 text-white shrink-0 shadow-lg shadow-cyan-500/20">
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="w-full bg-slate-800/50 rounded-xl p-5 border border-slate-700 flex justify-between items-center mt-6">
          <span className="text-sm text-slate-300">تعداد دوستان دعوت شده</span>
          <span className="text-xl font-bold text-white flex items-center gap-2">
            <Users className="w-6 h-6 text-slate-400" /> ۰ نفر
          </span>
        </div>
      </div>
    </div>
  );
}