"use client";

import { Send, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function SupportPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans pb-32 relative">
      
      {/* Consistent Sticky Header */}
      <header className="flex justify-between items-center p-4 bg-zinc-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-zinc-800/50 mb-6 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-emerald-400">پشتیبانی مشتریان</h1>
        <button onClick={() => router.back()} className="text-zinc-400 hover:text-white transition-colors bg-zinc-800/50 px-4 py-1.5 rounded-xl text-sm font-medium">
          بازگشت
        </button>
      </header>

      <main className="px-4 max-w-lg mx-auto flex flex-col gap-5 w-full">
        <div className="bg-gradient-to-b from-zinc-800 to-zinc-800/50 rounded-3xl p-6 border border-zinc-700 text-center shadow-lg">
          <h4 className="font-bold text-white mb-2 text-lg">پشتیبانی آنلاین</h4>
          <p className="text-sm text-zinc-400 mb-6">ما به صورت ۲۴ ساعته در تلگرام پاسخگوی شما هستیم.</p>
          <Button className="w-full bg-emerald-600 hover:bg-emerald-500 text-white py-6 rounded-xl flex items-center gap-2 text-md shadow-lg shadow-emerald-500/20 transition-all active:scale-95">
            <Send className="w-5 h-5" /> ارسال پیام به پشتیبانی
          </Button>
        </div>

        <div className="bg-zinc-800/40 rounded-3xl p-6 border border-zinc-700/50 text-right shadow-md">
          <h4 className="font-bold text-sm text-white mb-5 flex items-center justify-end gap-2">
             سوالات متداول <FileText className="w-5 h-5 text-emerald-400" />
          </h4>
          <ul className="text-xs text-zinc-300 space-y-5 pr-3 border-r-2 border-emerald-500/50">
            <li className="pb-2">
              زمان تحویل سفارش چقدر است؟<br/>
              <span className="text-emerald-400 mt-2 block font-medium">پاسخ: به صورت آنی پس از پرداخت.</span>
            </li>
            <li className="pb-2">
              آیا اکانت‌ها قانونی هستند؟<br/>
              <span className="text-emerald-400 mt-2 block font-medium">پاسخ: بله، تمام اکانت‌ها ۱۰۰٪ قانونی هستند.</span>
            </li>
            <li>
              در صورت قطعی چه کار کنم؟<br/>
              <span className="text-emerald-400 mt-2 block font-medium">پاسخ: بلافاصله به پشتیبانی پیام دهید.</span>
            </li>
          </ul>
        </div>
      </main>
    </div>
  );
}