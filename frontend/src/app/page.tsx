"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, User, Star, Flame, Code, Layout, Music, PlaySquare, Bot, Shield, BookOpen, MoreHorizontal, MessageCircle } from "lucide-react";
import { PRODUCTS } from "@/lib/products";

export default function Home() {
  const router = useRouter();
  
  // State for dynamically storing Telegram User Info
  const [tgUser, setTgUser] = useState<{ id?: number; first_name?: string; last_name?: string; username?: string } | null>(null);

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

  // Filter hot items (VPN Configs as requested)
  const hotItems = PRODUCTS.filter(p => p.id === "vpn_config" || p.id === "telegram_premium" || p.id === "spotify");

  return (
    <div className="min-h-screen font-sans pb-24">
      {/* Top Header */}
      <header className="flex justify-between items-center p-5 pt-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-zinc-800 rounded-full flex items-center justify-center overflow-hidden border border-zinc-700 cursor-pointer hover:opacity-80 transition-all active:scale-95" onClick={() => router.push('/profile')}>
            <User className="w-6 h-6 text-zinc-400" />
          </div>
          <div className="flex flex-col">
            <h1 className="text-sm font-bold text-white">سلام {tgUser?.first_name || 'کاربر عزیز'}</h1>
            <p className="text-[10px] text-zinc-400 mt-0.5">بهترین سرویس‌ها، با بهترین قیمت</p>
          </div>
        </div>
        <button className="relative p-2 bg-zinc-900 rounded-full border border-zinc-800 cursor-pointer hover:bg-zinc-800 active:scale-95 transition-all">
          <Bell className="w-5 h-5 text-zinc-300" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border border-zinc-900"></span>
        </button>
      </header>

      <main className="px-5 space-y-8">
        {/* Hot Items Slider (VPN Configs Focus) */}
        <section>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Flame className="w-4 h-4 text-orange-500" /> پیشنهاد ویژه
            </h3>
            <button onClick={() => router.push('/products')} className="text-xs text-red-500 font-bold cursor-pointer hover:opacity-80 transition-all active:scale-95">مشاهده همه</button>
          </div>
          
          <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide dir-rtl -mx-5 px-5">
            {hotItems.map((item, i) => (
              <div 
                key={i} 
                onClick={() => router.push('/products')}
                className="min-w-[240px] bg-gradient-to-br from-[#1a1a24] to-[#0f0f13] border border-zinc-800/80 rounded-2xl p-4 flex flex-col justify-between cursor-pointer hover:border-red-500/30 hover:shadow-lg hover:shadow-red-500/10 transition-all active:scale-[0.98]"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${item.gradient} flex items-center justify-center shadow-lg`}>
                    {item.icon}
                  </div>
                  <span className="text-[10px] bg-red-500/10 text-red-500 border border-red-500/20 px-2 py-1 rounded-md font-bold">پرفروش</span>
                </div>
                <div>
                  <h4 className="text-sm font-bold text-white">{item.title}</h4>
                  <p className="text-[10px] text-zinc-400 mt-1">{item.subtitle}</p>
                  <p className="text-xs font-bold text-emerald-400 mt-3">{item.variants[0].priceLabel} تومان</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Categories Grid */}
        <section>
          <h3 className="text-sm font-bold text-white mb-4">دسته‌بندی‌ها</h3>
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
                <div className="w-14 h-14 bg-zinc-900 rounded-2xl border border-zinc-800 flex items-center justify-center text-zinc-300 group-hover:bg-zinc-800 transition-colors">
                  {cat.icon}
                </div>
                <span className="text-[10px] text-zinc-400 font-medium">{cat.label}</span>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}