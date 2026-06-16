"use client";

import { Send, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function SupportPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32 relative">
      
      {/* Structural Anchor Configuration */}
      <header className="flex justify-between items-center p-4 bg-[#0F0F10]/80 backdrop-blur-md sticky top-0 z-40 border-b border-[#33383F] mb-6 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-[#E63946]">پشتیبانی مشتریان</h1>
        <button onClick={() => router.back()} className="text-[#F5F5F5]/70 hover:text-[#F5F5F5] transition-colors bg-[#33383F]/50 px-4 py-1.5 rounded-xl text-sm font-medium">
          بازگشت
        </button>
      </header>

      <main className="px-4 max-w-lg mx-auto flex flex-col gap-5 w-full">
        <div className="bg-gradient-to-b from-[#0B1D33] to-[#0B1D33]/50 rounded-3xl p-6 border border-[#33383F] text-center shadow-lg">
          <h4 className="font-bold text-[#F5F5F5] mb-2 text-lg">پشتیبانی آنلاین</h4>
          <p className="text-sm text-[#F5F5F5]/70 mb-6">ما به صورت ۲۴ ساعته در تلگرام پاسخگوی شما هستیم.</p>
          <Button className="w-full bg-[#1E3C5A] hover:bg-[#1E3C5A]/80 text-[#F5F5F5] py-6 rounded-xl flex items-center gap-2 text-md shadow-lg transition-all active:scale-95 border-none">
            <Send className="w-5 h-5" /> ارسال پیام به پشتیبانی
          </Button>
        </div>

        <div className="bg-[#33383F]/40 rounded-3xl p-6 border border-[#33383F]/50 text-right shadow-md">
          <h4 className="font-bold text-sm text-[#F5F5F5] mb-5 flex items-center justify-end gap-2">
             سوالات متداول <FileText className="w-5 h-5 text-[#E63946]" />
          </h4>
          <ul className="text-xs text-[#F5F5F5]/80 space-y-5 pr-3 border-r-2 border-[#1E3C5A]/50">
            <li className="pb-2">
              زمان تحویل سفارش چقدر است؟<br/>
              <span className="text-[#1E3C5A] mt-2 block font-medium">پاسخ: به صورت آنی پس از پرداخت.</span>
            </li>
            <li className="pb-2">
              آیا اکانت‌ها قانونی هستند؟<br/>
              <span className="text-[#1E3C5A] mt-2 block font-medium">پاسخ: بله، تمام اکانت‌ها ۱۰۰٪ قانونی هستند.</span>
            </li>
            <li>
              در صورت قطعی چه کار کنم؟<br/>
              <span className="text-[#1E3C5A] mt-2 block font-medium">پاسخ: بلافاصله به پشتیبانی پیام دهید.</span>
            </li>
          </ul>
        </div>
      </main>
    </div>
  );
}