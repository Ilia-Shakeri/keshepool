"use client";

import { Send, FileText, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function SupportPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans p-4 max-w-lg mx-auto">
      <header className="flex justify-between items-center mb-8 border-b border-slate-800/50 pb-4">
        <h1 className="text-xl font-bold text-cyan-400">پشتیبانی مشتریان</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors flex items-center gap-1">
          بازگشت <ChevronRight className="w-5 h-5" />
        </button>
      </header>

      <div className="flex flex-col gap-4 w-full">
        <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700 text-center">
          <h4 className="font-bold text-white mb-2">پشتیبانی آنلاین</h4>
          <p className="text-sm text-slate-400 mb-6">ما به صورت ۲۴ ساعته در تلگرام پاسخگوی شما هستیم.</p>
          <Button className="w-full bg-blue-600 hover:bg-blue-500 text-white py-6 rounded-xl flex items-center gap-2 text-md">
            <Send className="w-5 h-5" /> ارسال پیام به پشتیبانی
          </Button>
        </div>
        <div className="bg-slate-800/40 rounded-xl p-4 border border-slate-700/50 mt-4 text-right">
          <h4 className="font-bold text-sm text-white mb-4 flex items-center justify-end gap-2">
             سوالات متداول <FileText className="w-4 h-4 text-cyan-400" />
          </h4>
          <ul className="text-xs text-slate-300 space-y-4 pr-2 border-r-2 border-slate-700/50">
            <li className="pb-2">زمان تحویل سفارش چقدر است؟ <br/><span className="text-cyan-400 mt-1 block">پاسخ: به صورت آنی پس از پرداخت.</span></li>
            <li className="pb-2">آیا اکانت ها قانونی هستند؟ <br/><span className="text-cyan-400 mt-1 block">پاسخ: بله، تمام اکانت‌ها ۱۰۰٪ قانونی هستند.</span></li>
            <li>در صورت قطعی چه کار کنم؟ <br/><span className="text-cyan-400 mt-1 block">پاسخ: بلافاصله به پشتیبانی پیام دهید.</span></li>
          </ul>
        </div>
      </div>
    </div>
  );
}