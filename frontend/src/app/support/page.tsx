"use client";

import { Send, FileText, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function SupportPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans pb-32 relative">
      
      {/* Consistent Sticky Header */}
      <header className="flex justify-between items-center p-4 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-slate-800/50 mb-6 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-cyan-400">پشتیبانی مشتریان</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors flex items-center gap-1 bg-slate-800/50 px-3 py-1.5 rounded-xl">
          بازگشت <ChevronRight className="w-5 h-5" />
        </button>
      </header>

      <main className="px-4 max-w-lg mx-auto flex flex-col gap-5 w-full">
        <div className="bg-gradient-to-b from-slate-800 to-slate-800/50 rounded-3xl p-6 border border-slate-700 text-center shadow-lg">
          <h4 className="font-bold text-white mb-2 text-lg">پشتیبانی آنلاین</h4>
          <p className="text-sm text-slate-400 mb-6">ما به صورت ۲۴ ساعته در تلگرام پاسخگوی شما هستیم.</p>
          <Button className="w-full bg-blue-600 hover:bg-blue-500 text-white py-6 rounded-xl flex items-center gap-2 text-md shadow-lg shadow-blue-500/20 transition-all active:scale-95">
            <Send className="w-5 h-5" /> ارسال پیام به پشتیبانی
          </Button>
        </div>

        <div className="bg-slate-800/40 rounded-3xl p-6 border border-slate-700/50 text-right shadow-md">
          <h4 className="font-bold text-sm text-white mb-5 flex items-center justify-end gap-2">
             سوالات متداول <FileText className="w-5 h-5 text-cyan-400" />
          </h4>
          <ul className="text-xs text-slate-300 space-y-5 pr-3 border-r-2 border-cyan-500/50">
            <li className="pb-2">
              زمان تحویل سفارش چقدر است؟<br/>
              <span className="text-cyan-400 mt-2 block font-medium">پاسخ: به صورت آنی پس از پرداخت.</span>
            </li>
            <li className="pb-2">
              آیا اکانت‌ها قانونی هستند؟<br/>
              <span className="text-cyan-400 mt-2 block font-medium">پاسخ: بله، تمام اکانت‌ها ۱۰۰٪ قانونی هستند.</span>
            </li>
            <li>
              در صورت قطعی چه کار کنم؟<br/>
              <span className="text-cyan-400 mt-2 block font-medium">پاسخ: بلافاصله به پشتیبانی پیام دهید.</span>
            </li>
          </ul>
        </div>
      </main>
    </div>
  );
}