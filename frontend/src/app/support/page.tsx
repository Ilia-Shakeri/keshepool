"use client";

import { Send, FileText, ChevronDown } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";

const FAQ = [
  { q: "زمان تحویل سفارش چقدر است؟", a: "به صورت آنی پس از تأیید پرداخت." },
  { q: "آیا اکانت‌ها قانونی هستند؟", a: "بله، تمام اکانت‌ها ۱۰۰٪ اصل و قانونی هستند." },
  { q: "در صورت قطعی چه کار کنم؟", a: "بلافاصله به پشتیبانی پیام دهید — گارانتی ۷ روزه داریم." },
];

export default function SupportPage() {
  const router = useRouter();
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="min-h-screen text-[#F5F5F5] font-sans pb-32">
      <header className="px-5 py-4 flex justify-between items-center">
        <h1 className="text-base font-bold text-[#F5F5F5]">پشتیبانی</h1>
        <button
          onClick={() => router.back()}
          className="text-[#F5F5F5]/50 text-xs px-3 py-1.5 rounded-xl transition-colors hover:text-[#F5F5F5] hover:bg-white/[0.06]"
        >
          بازگشت
        </button>
      </header>

      <main className="px-5 space-y-4">
        {/* Live support card */}
        <div
          className="rounded-3xl p-6 text-center"
          style={{
            background: "linear-gradient(135deg, rgba(230,57,70,0.12) 0%, rgba(230,57,70,0.04) 100%)",
            border: "1px solid rgba(230,57,70,0.2)",
          }}
        >
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{ background: "rgba(230,57,70,0.15)", border: "1px solid rgba(230,57,70,0.25)" }}
          >
            <Send className="w-5 h-5 text-[#E63946]" />
          </div>
          <h4 className="font-bold text-[#F5F5F5] mb-1.5 text-base">پشتیبانی آنلاین ۲۴/۷</h4>
          <p className="text-sm text-[#F5F5F5]/50 mb-5 leading-relaxed">کارشناسان ما در تلگرام پاسخگوی شما هستند.</p>
          <button
            className="w-full py-3.5 rounded-2xl text-sm font-bold transition-all active:scale-95 flex items-center justify-center gap-2"
            style={{ background: "linear-gradient(135deg, #E63946 0%, #c0303c 100%)", color: "white", boxShadow: "0 8px 24px rgba(230,57,70,0.25)" }}
          >
            <Send className="w-4 h-4" /> ارسال پیام به پشتیبانی
          </button>
        </div>

        {/* FAQ section uses explicit RTL rules for Persian text. */}
        <div dir="rtl" className="text-right">
          <h3 className="text-sm font-bold text-[#F5F5F5] mb-3 flex items-center gap-2">
            <FileText className="w-4 h-4 text-[#E63946]" /> سوالات متداول
          </h3>
          <div className="space-y-2 text-right" dir="rtl">
            {FAQ.map((item, i) => (
              <div
                key={i}
                className="rounded-2xl overflow-hidden transition-all"
                style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
              >
                <button
                  className="w-full flex flex-row-reverse items-center justify-between gap-3 px-4 py-3.5 text-right"
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  dir="rtl"
                >
                  <ChevronDown
                    className="w-4 h-4 text-[#F5F5F5]/40 transition-transform flex-shrink-0"
                    style={{ transform: openFaq === i ? "rotate(180deg)" : "rotate(0deg)" }}
                  />
                  <span className="text-sm font-medium text-[#F5F5F5]/85 text-right flex-1">{item.q}</span>
                </button>
                {openFaq === i && (
                  <div className="px-4 pb-4 text-sm text-[#F5F5F5]/55 leading-relaxed border-t border-white/[0.06] pt-3 text-right" dir="rtl">
                    {item.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
