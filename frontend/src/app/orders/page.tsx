"use client";

import { Clock, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function OrdersPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans p-4 max-w-lg mx-auto">
      <header className="flex justify-between items-center mb-8 border-b border-slate-800/50 pb-4">
        <h1 className="text-xl font-bold text-cyan-400">سفارشات من</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors flex items-center gap-1">
          بازگشت <ChevronRight className="w-5 h-5" />
        </button>
      </header>

      <div className="flex flex-col gap-4 w-full">
        {[1, 2, 3].map((order, idx) => (
          <div key={idx} className="bg-slate-800/50 rounded-xl p-4 border border-slate-700 flex flex-col gap-3">
            <div className="flex justify-between items-center border-b border-slate-700/50 pb-2">
              <span className={`text-xs px-2 py-1 rounded-full ${idx === 0 ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-slate-700/50 text-slate-400'}`}>
                {idx === 0 ? 'فعال' : 'پایان یافته'}
              </span>
              <span className="text-xs text-slate-400 flex items-center gap-1"><Clock className="w-3 h-3" /> ۱۴۰۳/۰۳/۱{idx}</span>
            </div>
            <div className="flex justify-between items-center mt-2">
              <div className="text-right">
                <h4 className="font-bold text-sm text-white">اسپاتیفای پرمیوم ۱ ماهه</h4>
                <p className="text-xs text-slate-400 mt-1">کد سفارش: ORD-98{idx}X</p>
              </div>
              <Button variant="outline" size="sm" className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 shrink-0 ml-2">مشاهده</Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}