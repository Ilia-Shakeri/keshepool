"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, Bot, Code, Flame, Layout, MessageCircle, MoreHorizontal, Music, PlaySquare, Shield, User, X } from "lucide-react";
import ProductIcon from "@/components/ProductIcon";
import { getNotifications, getProducts, type UserNotification } from "@/lib/api";
import type { Product } from "@/lib/products";
import { toPersianDigits } from "@/lib/utils";

export default function Home() {
  const router = useRouter();
  const [tgUser, setTgUser] = useState<{ id?: number; first_name?: string; last_name?: string; username?: string } | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [notifications, setNotifications] = useState<UserNotification[]>([]);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (webApp) {
      setTgUser(webApp.initDataUnsafe?.user || null);
    }

    Promise.all([getProducts(), getNotifications()])
      .then(([productData, notificationData]) => {
        setProducts(productData);
        setNotifications(notificationData);
      })
      .catch((error) => console.error("Home data load failed:", error))
      .finally(() => setIsLoading(false));
  }, []);

  const hotItems = useMemo(() => products.slice(0, 6), [products]);
  const unreadCount = notifications.filter((item) => !item.isRead).length;

  return (
    <div className="min-h-screen font-sans pb-24 bg-[#0F0F10]">
      <header className="flex justify-between items-center p-5 pt-6 relative">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 bg-[#33383F] rounded-full flex items-center justify-center overflow-hidden border border-[#33383F]/80 cursor-pointer hover:opacity-80 transition-all active:scale-95"
            onClick={() => router.push("/profile")}
          >
            <User className="w-6 h-6 text-[#F5F5F5]/70" />
          </div>

          <div className="flex flex-col">
            <h1 className="text-sm font-bold text-[#F5F5F5]">سلام {tgUser?.first_name || "کاربر عزیز"}</h1>
            <p className="text-[10px] text-[#F5F5F5]/70 mt-0.5">بهترین سرویس‌ها، با بهترین قیمت</p>
          </div>
        </div>

        <div className="relative">
          <button
            onClick={() => setIsNotifOpen(!isNotifOpen)}
            className="relative p-2 bg-[#33383F]/50 rounded-full border border-[#33383F] cursor-pointer hover:bg-[#33383F]/80 active:scale-95 transition-all"
          >
            <Bell className="w-5 h-5 text-[#F5F5F5]" />
            {unreadCount > 0 && <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#E63946] rounded-full border border-[#0F0F10]" />}
          </button>

          {isNotifOpen && (
            <div className="absolute left-0 top-12 w-64 bg-[#0B1D33] border border-[#33383F] rounded-2xl shadow-xl z-50 overflow-hidden">
              <div className="flex justify-between items-center p-3 border-b border-[#33383F]">
                <span className="text-sm font-bold text-[#F5F5F5]">اعلانات</span>
                <button onClick={() => setIsNotifOpen(false)}>
                  <X className="w-4 h-4 text-[#F5F5F5]/70 hover:text-[#E63946] transition-colors" />
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="p-4 text-center text-xs text-[#F5F5F5]/50">اعلان جدیدی ندارید.</div>
                ) : (
                  notifications.map((notification) => (
                    <div key={notification.id} className={`p-3 border-b border-[#33383F] ${notification.isRead ? "opacity-70" : ""}`}>
                      <h4 className="text-xs font-bold text-[#F5F5F5]">{notification.title}</h4>
                      <p className="text-[10px] text-[#F5F5F5]/70 mt-1">{notification.description}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="px-5 space-y-8">
        <section>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-[#F5F5F5] flex items-center gap-2">
              <Flame className="w-4 h-4 text-[#E63946]" /> پیشنهاد ویژه
            </h3>
            <button onClick={() => router.push("/products")} className="text-xs text-[#E63946] font-bold cursor-pointer hover:opacity-80 transition-all active:scale-95">
              مشاهده همه
            </button>
          </div>

          <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide dir-rtl -mx-5 px-5">
            {isLoading
              ? Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="min-w-[240px] bg-[#0B1D33] border border-[#33383F] rounded-2xl p-4 animate-pulse flex flex-col justify-between h-[148px]">
                    <div className="flex justify-between items-start mb-4">
                      <div className="w-10 h-10 bg-[#33383F] rounded-xl" />
                      <div className="w-10 h-5 bg-[#33383F] rounded-md" />
                    </div>
                    <div className="space-y-2">
                      <div className="h-3 bg-[#33383F] rounded w-3/4" />
                      <div className="h-2 bg-[#33383F] rounded w-1/2" />
                      <div className="h-3 bg-[#33383F] rounded w-1/3 mt-3" />
                    </div>
                  </div>
                ))
              : hotItems.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => router.push("/products")}
                    className="min-w-[240px] bg-gradient-to-br from-[#0B1D33] to-[#0F0F10] border border-[#33383F] rounded-2xl p-4 flex flex-col justify-between cursor-pointer hover:border-[#E63946]/50 hover:shadow-lg hover:shadow-[#E63946]/10 transition-all active:scale-[0.98]"
                  >
                    <div className="flex justify-between items-start mb-4">
                      <ProductIcon icon={item.icon} assetUrl={item.assetUrl} gradient={item.gradient} sizeClassName="w-10 h-10" />
                      <span className="text-[10px] bg-[#E63946]/10 text-[#E63946] border border-[#E63946]/20 px-2 py-1 rounded-md font-bold">موجود</span>
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-[#F5F5F5]">{item.title}</h4>
                      <p className="text-[10px] text-[#F5F5F5]/70 mt-1">{item.subtitle}</p>
                      <p className="text-xs font-bold text-emerald-400 mt-3">{toPersianDigits(item.variants[0]?.priceLabel || "0")} تومان</p>
                    </div>
                  </div>
                ))}
          </div>
        </section>

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
            ].map((cat) => (
              <div key={cat.label} onClick={() => router.push("/products")} className="flex flex-col items-center gap-2 cursor-pointer group hover:opacity-90 active:scale-95 transition-all">
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