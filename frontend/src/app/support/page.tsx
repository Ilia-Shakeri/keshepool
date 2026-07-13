"use client";

import { Send, FileText, ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { getPublicConfig } from "@/lib/api";

const FAQ = [
  { q: "تحویل سفارش چقدر زمان می‌برد؟", a: "اگر پرداخت تأیید شده و موجودی همان گزینه آماده باشد، اطلاعات سفارش معمولاً همان زمان در بخش سفارش‌ها نمایش داده می‌شود. اختلال شبکه یا بررسی پرداخت می‌تواند تحویل را عقب بیندازد." },
  { q: "اگر محصول موجود نباشد چه می‌شود؟", a: "گزینه‌ای که موجودی ندارد قابل خرید نیست. می‌توانید بعداً دوباره موجودی را بررسی کنید یا برای زمان تقریبی تأمین با پشتیبانی تماس بگیرید." },
  { q: "اطلاعات دسترسی را کجا می‌بینم؟", a: "پس از خرید موفق، اطلاعات دسترسی در نتیجه خرید و سپس در بخش «سفارش‌ها» و جزئیات همان سفارش دیده می‌شود." },
  { q: "چه روش‌های پرداختی پشتیبانی می‌شود؟", a: "خرید از موجودی کیف پول انجام می‌شود. روش‌های افزایش موجودی که در صفحه مالی فعال و تنظیم شده‌اند، از جمله درگاه تومانی یا واریز USDT، همان‌جا نمایش داده می‌شوند." },
  { q: "پرداخت من در انتظار مانده؛ چه کنم؟", a: "ابتدا چند دقیقه برای ثبت نتیجه پرداخت صبر کنید و صفحه مالی را دوباره بررسی کنید. اگر وضعیت تغییر نکرد، شناسه تراکنش و زمان پرداخت را برای پشتیبانی بفرستید؛ اطلاعات محرمانه کارت یا کیف پول را ارسال نکنید." },
  { q: "برای واریز USDT از کدام شبکه استفاده کنم؟", a: "فقط شبکه TRC20 و آدرسی را که برنامه هنگام ثبت واریز نشان می‌دهد به کار ببرید. مبلغ را دقیق بفرستید و تا تأییدهای لازم شبکه صبر کنید. ارسال از شبکه اشتباه ممکن است قابل بازیابی نباشد." },
  { q: "چه زمانی بازپرداخت انجام می‌شود؟", a: "بازپرداخت به علت، وضعیت تحویل و امکان بررسی سرویس بستگی دارد. سفارش تحویل‌شده یا مشکلی که از استفاده نادرست ایجاد شده باشد لزوماً قابل بازپرداخت نیست. پشتیبانی هر مورد را جداگانه بررسی می‌کند." },
  { q: "ضمانت شامل چه مواردی است؟", a: "دامنه ضمانت فقط طبق شرایط همان محصول و ایراد قابل بررسی است. تغییر رمز یا تنظیمات، اشتراک‌گذاری دسترسی، نقض قوانین سرویس و محدودیت‌های دستگاه یا منطقه می‌تواند خارج از پوشش باشد." },
  { q: "چطور از اطلاعات حساب یا کانفیگ نگهداری کنم؟", a: "اطلاعات دسترسی را با دیگران به اشتراک نگذارید، آن را در فضای عمومی ذخیره نکنید و تنظیمات حساب را بدون نیاز تغییر ندهید. پشتیبانی هرگز رمز کارت بانکی یا عبارت بازیابی کیف پول را درخواست نمی‌کند." },
  { q: "سرویس من خودکار تمدید می‌شود؟", a: "خیر، مگر این‌که در توضیح همان محصول صریحاً تمدید خودکار ذکر شده باشد. تاریخ پایان سرویس‌های مدت‌دار در سفارش ثبت می‌شود و برای ادامه باید گزینه مناسب را دوباره تهیه کنید." },
  { q: "آیا سرویس روی همه دستگاه‌ها و کشورها کار می‌کند؟", a: "خیر. محدودیت دستگاه، منطقه، شماره تلفن، نشانی شبکه یا قوانین ارائه‌دهنده ممکن است برای هر محصول متفاوت باشد. پیش از خرید توضیحات و ویژگی‌های همان گزینه را بررسی کنید." },
  { q: "چطور سفارش‌های قبلی را پیدا کنم؟", a: "از نوار پایین وارد «سفارش‌ها» شوید. سفارش‌های فعال، منقضی، لغوشده و بازپرداخت‌شده جداگانه قابل فیلتر هستند." },
  { q: "درخواست نقد کردن درآمد ارزی چگونه است؟", a: "در صفحه مالی، منبع درآمد و توضیحات لازم را ثبت کنید. پس از بررسی، مسئول مربوط از راه حساب تلگرام شما تماس می‌گیرد. زمان انجام به نوع منبع، مبلغ و بررسی‌های لازم بستگی دارد و فوری تضمین نمی‌شود." },
  { q: "پشتیبانی چه اطلاعاتی از من می‌بیند؟", a: "برای پیگیری، مدیران مجاز می‌توانند شناسه تلگرام، اطلاعات سفارش، وضعیت پرداخت و متن درخواست شما را ببینند. اطلاعات دسترسی سفارش فقط در جریان‌های لازم برای تحویل و پشتیبانی بررسی می‌شود." },
  { q: "چه زمانی با پشتیبانی تماس بگیرم؟", a: "برای پرداخت تأییدنشده، اطلاعات تحویل‌نشده، خرابی قابل تکرار یا ابهام پیش از خرید پیام دهید. شناسه سفارش یا تراکنش، زمان رخداد و شرح کوتاه مشکل را همراه پیام بفرستید." },
  { q: "اگر هنگام خرید خطا دیدم چه کنم؟", a: "پیش از تکرار خرید، سفارش‌ها و موجودی کیف پول را بررسی کنید. اگر مبلغ کم شده ولی سفارش ساخته نشده، دوباره پرداخت نکنید و موضوع را با شناسه و زمان رخداد به پشتیبانی بدهید." },
  { q: "وضعیت لغوشده یا بازپرداخت‌شده یعنی چه؟", a: "لغوشده یعنی سفارش نهایی نشده یا ادامه آن متوقف شده است. بازپرداخت‌شده یعنی مبلغ طبق نتیجه بررسی برگردانده شده است. جزئیات مالی را در تاریخچه کیف پول بررسی کنید." },
];

export default function SupportPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [supportLink, setSupportLink] = useState<string | null>(null);

  useEffect(() => {
    void getPublicConfig()
      .then((config) => setSupportLink(config.supportUrl || (config.supportUsername ? `https://t.me/${config.supportUsername.replace(/^@/, "")}` : null)))
      .catch((error) => console.error("Support config load failed:", error));
  }, []);

  const openSupport = () => {
    if (!supportLink) {
      window.Telegram?.WebApp?.showAlert("راه ارتباط با پشتیبانی هنوز تنظیم نشده است.");
      return;
    }
    if (/^https:\/\/(t\.me|telegram\.me)\//i.test(supportLink)) {
      window.Telegram?.WebApp?.openTelegramLink(supportLink);
    } else if (/^https:\/\//i.test(supportLink)) {
      window.Telegram?.WebApp?.openLink(supportLink);
    } else {
      window.Telegram?.WebApp?.showAlert("نشانی پشتیبانی معتبر نیست.");
    }
  };

  return (
    <div className="min-h-[100dvh] pb-32 font-sans text-[#F5F5F5]">
      <PageHeader title="پشتیبانی" />

      <main className="mx-auto max-w-2xl space-y-4 px-5">
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
          <h4 className="font-bold text-[#F5F5F5] mb-1.5 text-base">پشتیبانی در تلگرام</h4>
          <p className="text-sm text-[#F5F5F5]/50 mb-5 leading-relaxed">پیام شما از راه حساب پشتیبانی تنظیم‌شده بررسی می‌شود.</p>
          <button
            type="button"
            onClick={openSupport}
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
                  type="button"
                  className="w-full flex flex-row-reverse items-center justify-between gap-3 px-4 py-3.5 text-right"
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  dir="rtl"
                  aria-expanded={openFaq === i}
                  aria-controls={`faq-panel-${i}`}
                >
                  <ChevronDown
                    className="w-4 h-4 text-[#F5F5F5]/40 transition-transform flex-shrink-0"
                    style={{ transform: openFaq === i ? "rotate(180deg)" : "rotate(0deg)" }}
                  />
                  <span className="text-sm font-medium text-[#F5F5F5]/85 text-right flex-1">{item.q}</span>
                </button>
                {openFaq === i && (
                  <div id={`faq-panel-${i}`} role="region" className="px-4 pb-4 text-sm text-[#F5F5F5]/55 leading-relaxed border-t border-white/[0.06] pt-3 text-right" dir="rtl">
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
