"use client";

import { Gift, Copy, Users, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function InvitePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans pb-32 relative">
      
      {/* Consistent Sticky Header */}
      <header className="flex justify-between items-center p-4 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-slate-800/50 mb-6 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-cyan-400">دعوت از دوستان</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors flex items-center gap-1 bg-slate-800/50 px-3 py-1.5 rounded-xl">
          بازگشت <ChevronRight className="w-5 h-5" />
        </button>
      </header>

      <main className="flex flex-col items-center gap-5 w-full px-4 max-w-lg mx-auto mt-4">
        <div className="w-24 h-24 bg-indigo-500/10 rounded-full flex items-center justify-center mb-2 shadow-lg shadow-indigo-500/10 border border-indigo-500/20 relative">
          <div className="absolute inset-0 rounded-full bg-indigo-400/20 animate-ping opacity-20"></div>
          <Gift className="w-12 h-12 text-indigo-400 relative z-10" />
        </div>
        
        <p className="text-center text-sm text-slate-300 leading-relaxed mb-4 px-2">
          با دعوت از هر دوست، <span className="text-cyan-400 font-bold">۲۰,۰۰۰ تومان</span> اعتبار هدیه بگیرید و دوست شما نیز ۱۰٪ تخفیف خرید اول دریافت میکند.
        </p>
        
        <div className="w-full">
          <label className="text-xs text-slate-400 mb-2 block text-right">لینک دعوت اختصاصی شما:</label>
          <div className="w-full bg-slate-950 p-4 rounded-2xl border border-slate-700 flex items-center justify-between gap-3 shadow-inner">
            <span className="text-xs text-slate-400 truncate dir-ltr select-all font-mono">https://t.me/ZoodSubBot?start=ref_8912</span>
            <Button size="icon" className="bg-cyan-500 hover:bg-cyan-400 text-white shrink-0 shadow-lg shadow-cyan-500/20 rounded-xl">
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="w-full bg-slate-800/50 backdrop-blur-sm rounded-2xl p-5 border border-slate-700 flex justify-between items-center mt-4 shadow-md">
          <span className="text-sm text-slate-300">تعداد دوستان دعوت شده</span>
          <span className="text-xl font-bold text-white flex items-center gap-2">
            <Users className="w-6 h-6 text-slate-400" /> ۰ نفر
          </span>
        </div>
      </main>
    </div>
  );
}