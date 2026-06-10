"use client";

import { Clock, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function OrdersPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans pb-32 relative">
      
      {/* Consistent Sticky Header */}
      <header className="flex justify-between items-center p-4 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-slate-800/50 mb-6 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-cyan-400">سفارشات من</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors flex items-center gap-1 bg-slate-800/50 px-3 py-1.5 rounded-xl">
          بازگشت <ChevronRight className="w-5 h-5" />
        </button>
      </header>

      <main className="flex flex-col gap-4 w-full px-4 max-w-lg mx-auto">
        {[1, 2, 3].map((order, idx) => (
          <div key={idx} className="bg-slate-800/60 backdrop-blur-sm rounded-3xl p-5 border border-slate-700 flex flex-col gap-3 shadow-md hover:border-cyan-500/30 transition-colors">
            <div className="flex justify-between items-center border-b border-slate-700/50 pb-3">
              <span className={`text-xs px-3 py-1 rounded-full font-medium ${idx === 0 ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-slate-700/50 text-slate-400 border border-slate-600/50'}`}>
                {idx === 0 ? 'فعال' : 'پایان یافته'}
              </span>
              <span className="text-xs text-slate-400 flex items-center gap-1"><Clock className="w-3 h-3" /> ۱۴۰۳/۰۳/۱{idx}</span>
            </div>
            <div className="flex justify-between items-center mt-2">
              <div className="text-right">
                <h4 className="font-bold text-sm text-white mb-1">اسپاتیفای پرمیوم ۱ ماهه</h4>
                <p className="text-[10px] text-slate-400 font-mono">کد سفارش: ORD-98{idx}X</p>
              </div>
              <Button variant="outline" size="sm" className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 shrink-0 ml-2 rounded-xl">مشاهده</Button>
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}