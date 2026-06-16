"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, User, Flame, Shield, Music, PlaySquare, Bot, MessageCircle, Code, Layout, MoreHorizontal, X } from "lucide-react";
import { PRODUCTS } from "@/lib/products";
import { toPersianDigits, formatPrice } from "@/lib/utils";

export default function Home() {
  const router = useRouter();

  // State for dynamically storing Telegram User Info
  const [tgUser, setTgUser] = useState<{ id?: number; first_name?: string; last_name?: string; username?: string } | null>(null);
  
  // State for notification dropdown management
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  
  // Mock notification data store
  const notifications = [
    { id: 1, title: "سفارش جدید", desc: "سفارش V2Ray شما با موفقیت فعال شد.", time: "۱۰ دقیقه پیش", read: false },
    { id: 2, title: "افزایش موجودی", desc: `موجودی شما ${formatPrice(500000)} تومان شارژ شد.`, time: "۲ ساعت پیش", read: true },
    { id: 3, title: "به‌روزرسانی", desc: "محصولات جدید در دسته‌بندی استریم اضافه شد.", time: "۱ روز پیش", read: true }
  ];

  useEffect(() => {
    // Initialize Telegram WebApp SDK and retrieve user data securely
    if (typeof window !== "undefined" && window.Telegram?.WebApp) {
      window.Telegram.WebApp.expand();
      window.Telegram.WebApp.ready();
      
      const userPayload = window.Telegram.WebApp.initDataUnsafe?.user;
      if (userPayload) {
        setTgUser(userPayload);
      }
    }
  }, []);

  // Filter hot items prioritizing specific product categories
  const hotItems = PRODUCTS.filter(p => p.id === "vpn_config" || p.id === "telegram_premium" || p.id === "spotify");

  return (
    <div className="min-h-screen font-sans pb-24 bg-[#0F0F10]">
      {/* Top Header */}
      <header className="flex justify-between items-center p-5 pt-6 relative">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#33383F] rounded-full flex items-center justify-center overflow-hidden border border-[#33383F]/80 cursor-pointer hover:opacity-80 transition-all active:scale-95" onClick={() => router.push('/profile')}>
            <User className="w-6 h-6 text-[#F5F5F5]/70" />
          </div>
        
          <div className="flex flex-col">
            <h1 className="text-sm font-bold text-[#F5F5F5]">سلام {tgUser?.first_name || 'کاربر عزیز'}</h1>
            <p className="text-[10px] text-[#F5F5F5]/70 mt-0.5">بهترین سرویس‌ها، با بهترین قیمت</p>
          </div>
        </div>
        
        {/* Notification Bell Component */}
        <div className="relative">
          <button onClick={() => setIsNotifOpen(!isNotifOpen)} className="relative p-2 bg-[#33383F]/50 rounded-full border border-[#33383F] cursor-pointer hover:bg-[#33383F]/80 active:scale-95 transition-all">
            <Bell className="w-5 h-5 text-[#F5F5F5]" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#E63946] rounded-full border border-[#0F0F10]"></span>
          </button>

          {isNotifOpen && (
            <div className="absolute left-0 top-12 w-64 bg-[#0B1D33] border border-[#33383F] rounded-2xl shadow-xl z-50 overflow-hidden">
              <div className="flex justify-between items-center p-3 border-b border-[#33383F]">
                <span className="text-sm font-bold text-[#F5F5F5]">اعلانات</span>
                <button onClick={() => setIsNotifOpen(false)}><X className="w-4 h-4 text-[#F5F5F5]/70 hover:text-[#E63946] transition-colors" /></button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifications.map(n => (
                  <div key={n.id} className={`p-3 border-b border-[#33383F] hover:bg-[#1E3C5A]/50 transition-colors cursor-pointer ${n.read ? 'opacity-70' : ''}`}>
                     <h4 className="text-xs font-bold text-[#F5F5F5]">{n.title}</h4>
                     <p className="text-[10px] text-[#F5F5F5]/70 mt-1">{n.desc}</p>
                     <span className="text-[8px] text-[#F5F5F5]/50 mt-1 block">{n.time}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="px-5 space-y-8">
        {/* Highlighted Items Slider */}
        <section>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-[#F5F5F5] flex items-center gap-2">
              <Flame className="w-4 h-4 text-[#E63946]" /> پیشنهاد ویژه
            </h3>
            <button onClick={() => router.push('/products')} className="text-xs text-[#E63946] font-bold cursor-pointer hover:opacity-80 transition-all active:scale-95">مشاهده همه</button>
          </div>
          
          <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide dir-rtl -mx-5 px-5">
            {hotItems.map((item, i) => (
              <div 
                key={i} 
                onClick={() => router.push('/products')}
                className="min-w-[240px] bg-gradient-to-br from-[#0B1D33] to-[#0F0F10] border border-[#33383F] rounded-2xl p-4 flex flex-col justify-between cursor-pointer hover:border-[#E63946]/50 hover:shadow-lg hover:shadow-[#E63946]/10 transition-all active:scale-[0.98]"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${item.gradient} flex items-center justify-center shadow-lg`}>
                    {item.icon}
                  </div>
                  <span className="text-[10px] bg-[#E63946]/10 text-[#E63946] border border-[#E63946]/20 px-2 py-1 rounded-md font-bold">پرفروش</span>
                </div>
                <div>
                  <h4 className="text-sm font-bold text-[#F5F5F5]">{item.title}</h4>
                  <p className="text-[10px] text-[#F5F5F5]/70 mt-1">{item.subtitle}</p>
                  <p className="text-xs font-bold text-[#1E3C5A] mt-3 text-emerald-400">{toPersianDigits(item.variants[0].priceLabel)} تومان</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* System Categories Grid */}
        <section>
          <h3 className="text-sm font-bold text-[#F5F5F5] mb-4">دسته‌بندی‌ها</h3>
          <div className="grid grid-cols-4 gap-4">
            {[
              { icon: <Shield className="w-5 h-5" />, label: "تحریم‌شکن" },
              { icon: <Music className="w-5 h-5" />, label: "موسیقی" },
              { icon: <PlaySquare className="w-5 h-5" />, label: "استریم" },
              { icon: <Bot className="w-5 h-5" />, label: "هوش مصنوعی" },
              { icon: <MessageCircle className="w-5 h-5" />, label: "شبکه اجتماعی" },
              { icon: <Code className="w-5 h-5" />, label: "برنامه‌نویسی" },
              { icon: <Layout className="w-5 h-5" />, label: "طراحی" },
              { icon: <MoreHorizontal className="w-5 h-5" />, label: "بیشتر" },
            ].map((cat, i) => (
              <div key={i} onClick={() => router.push('/products')} className="flex flex-col items-center gap-2 cursor-pointer group hover:opacity-90 active:scale-95 transition-all">
                <div className="w-14 h-14 bg-[#33383F]/50 rounded-2xl border border-[#33383F] flex items-center justify-center text-[#F5F5F5]/80 group-hover:bg-[#33383F] transition-colors">
                  {cat.icon}
                </div>
                <span className="text-[10px] text-[#F5F5F5]/70 font-medium">{cat.label}</span>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}