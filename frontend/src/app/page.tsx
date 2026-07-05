"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, Bot, Code, Flame, Layout, MessageCircle, MoreHorizontal, Music, PlaySquare, Shield, User, X } from "lucide-react";
import ProductIcon from "@/components/ProductIcon";
import { getNotifications, getProducts, markNotificationsRead, type UserNotification } from "@/lib/api";
import type { Product } from "@/lib/products";
import { toPersianDigits } from "@/lib/utils";

export default function Home() {
  const router = useRouter();
  const [tgUser, setTgUser] = useState<{ id?: number; first_name?: string; last_name?: string; username?: string } | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [notifications, setNotifications] = useState<UserNotification[]>([]);
  const [productError, setProductError] = useState<string | null>(null);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const bellRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (webApp) setTgUser(webApp.initDataUnsafe?.user || null);

    // Load catalog data from the backend so the mini-app stays synced with admin-bot inventory.
    Promise.allSettled([getProducts(), getNotifications()])
      .then(([productData, notifData]) => {
        if (productData.status === "fulfilled") {
          setProducts(productData.value);
          setProductError(null);
        } else {
          setProducts([]);
          setProductError("خطا در دریافت محصولات.");
          console.error("Product data load failed:", productData.reason);
        }

        if (notifData.status === "fulfilled") {
          setNotifications(notifData.value);
        } else {
          setNotifications([]);
          console.error("Notification data load failed:", notifData.reason);
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  const hotItems = useMemo(() => products.slice(0, 6), [products]);
  const unreadCount = notifications.filter((n) => !n.isRead).length;

  function getStartingPrice(product: Product): string {
    const startingVariant = product.variants.reduce<Product["variants"][number] | null>((lowest, variant) => {
      if (!lowest) return variant;
      return variant.rawPrice < lowest.rawPrice ? variant : lowest;
    }, null);

    return startingVariant?.priceLabel || "0";
  }

  return (
    <div className="min-h-screen font-sans pb-28">
      {/* Background gradient orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0" aria-hidden="true">
        <div className="absolute -top-24 -right-24 w-72 h-72 bg-[#E63946]/[0.06] rounded-full blur-3xl" />
        <div className="absolute top-1/2 -left-32 w-80 h-80 bg-blue-600/[0.04] rounded-full blur-3xl" />
      </div>

      <header className="relative z-10 flex justify-between items-center px-5 py-4">
        {/* Left: user profile */}
        <button
          onClick={() => router.push("/profile")}
          className="flex items-center gap-3 active:scale-95 transition-transform"
        >
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center overflow-hidden border border-white/10"
            style={{ background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.04) 100%)" }}
          >
            <User className="w-5 h-5 text-[#F5F5F5]/60" />
          </div>
          <div className="flex flex-col items-start">
            <h1 className="text-sm font-bold text-[#F5F5F5] leading-tight">
              سلام، {tgUser?.first_name || "کاربر عزیز"} 👋
            </h1>
            <p className="text-[10px] text-[#F5F5F5]/50 mt-0.5">بهترین سرویس‌ها با بهترین قیمت</p>
          </div>
        </button>

        {/* Right: notification bell */}
        <div className="relative">
          <button
            ref={bellRef}
            onClick={() => {
              const opening = !isNotifOpen;
              setIsNotifOpen(opening);
              if (opening && unreadCount > 0) {
                markNotificationsRead().then(() =>
                  setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })))
                ).catch(() => {});
              }
            }}
            className="relative p-2.5 rounded-full border border-white/10 active:scale-95 transition-all"
            style={{ background: "rgba(255,255,255,0.06)", backdropFilter: "blur(12px)" }}
            aria-label="اعلانات"
          >
            <Bell className="w-[18px] h-[18px] text-[#F5F5F5]" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#E63946] rounded-full border border-[#0F0F10] shadow-sm" />
            )}
          </button>
        </div>
      </header>

      {/* Notification dropdown — rendered outside header to escape its stacking context */}
      {isNotifOpen && (
        <>
          {/* Full-screen overlay — catches outside clicks */}
          <div
            className="fixed inset-0 z-[9998]"
            onClick={() => setIsNotifOpen(false)}
            aria-hidden="true"
          />
          {/* Panel — fixed so it always floats above everything including BottomNav */}
          <div
            className="fixed right-5 z-[9999] w-72 rounded-2xl overflow-hidden"
            style={{
              top: "72px",
              background: "#111318",
              border: "1px solid rgba(255,255,255,0.12)",
              boxShadow: "0 24px 64px rgba(0,0,0,0.7), 0 4px 16px rgba(0,0,0,0.4)",
            }}
          >
            <div
              className="flex justify-between items-center px-4 py-3"
              style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
            >
              <span className="text-sm font-bold text-[#F5F5F5]">اعلانات</span>
              <button
                onClick={() => setIsNotifOpen(false)}
                className="p-1 rounded-lg transition-colors hover:bg-white/10"
              >
                <X className="w-3.5 h-3.5 text-[#F5F5F5]/60" />
              </button>
            </div>
            <div className="max-h-72 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="p-6 text-center text-xs text-[#F5F5F5]/40">اعلان جدیدی ندارید.</div>
              ) : (
                notifications.map((notification) => (
                  <div
                    key={notification.id}
                    className={`px-4 py-3 ${notification.isRead ? "opacity-50" : ""}`}
                    style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
                  >
                    <div className="flex items-center gap-2 mb-0.5">
                      {!notification.isRead && (
                        <span className="w-1.5 h-1.5 rounded-full bg-[#E63946] flex-shrink-0" />
                      )}
                      <h4 className="text-xs font-bold text-[#F5F5F5]">{notification.title}</h4>
                    </div>
                    <p className="text-[10px] text-[#F5F5F5]/55 leading-relaxed">{notification.description}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}

      <main className="relative z-10 px-5 space-y-8 mt-2">
        {/* Featured products horizontal scroll */}
        <section>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-[#F5F5F5] flex items-center gap-2">
              <Flame className="w-4 h-4 text-[#E63946]" />
              پیشنهاد ویژه
            </h3>
            <button
              onClick={() => router.push("/products")}
              className="text-xs text-[#E63946] font-bold active:scale-95 transition-transform hover:opacity-80"
            >
              مشاهده همه
            </button>
          </div>

          <div className="flex gap-3 overflow-x-auto pb-4 scrollbar-hide dir-rtl -mx-5 px-5">
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={i}
                    className="min-w-[210px] h-[148px] rounded-2xl animate-pulse flex-shrink-0"
                    style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
                  />
                ))
            ) : productError ? (
              <div className="min-w-full rounded-2xl p-5 text-center text-xs text-[#E63946] bg-white/[0.04] border border-white/[0.08]">
                {productError}
              </div>
            ) : hotItems.length === 0 ? (
              <div className="min-w-full rounded-2xl p-5 text-center text-xs text-[#F5F5F5]/40 bg-white/[0.04] border border-white/[0.08]">
                محصول فعالی برای نمایش وجود ندارد.
              </div>
            ) : (
              hotItems.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => router.push(`/products?category=${item.category}`)}
                    className="min-w-[210px] rounded-2xl p-4 flex flex-col justify-between cursor-pointer transition-all duration-300 active:scale-[0.97] hover:scale-[1.02] flex-shrink-0"
                    style={{
                      background: "linear-gradient(135deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.02) 100%)",
                      backdropFilter: "blur(20px)",
                      WebkitBackdropFilter: "blur(20px)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
                    }}
                  >
                    <div className="flex justify-between items-start mb-3">
                      <ProductIcon
                        icon={item.icon}
                        assetUrl={item.assetUrl}
                        gradient={item.gradient}
                        category={item.category}
                        sizeClassName="w-11 h-11"
                        iconSizeClassName="w-5 h-5"
                      />
                      <span
                        className="text-[9px] px-2 py-0.5 rounded-full font-bold"
                        style={{ background: "rgba(16,185,129,0.12)", color: "#10b981", border: "1px solid rgba(16,185,129,0.2)" }}
                      >
                        موجود
                      </span>
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-[#F5F5F5] leading-tight">{item.title}</h4>
                      <p className="text-[10px] text-[#F5F5F5]/50 mt-1 line-clamp-1">{item.subtitle}</p>
                      <p className="text-xs font-bold text-emerald-400 mt-2.5">
                        {toPersianDigits(getStartingPrice(item))}
                        <span className="text-[9px] font-normal text-[#F5F5F5]/40 mr-1">تومان</span>
                      </p>
                    </div>
                  </div>
                ))
            )}
          </div>
        </section>

        {/* Category grid */}
        <section className="pb-4">
          <h3 className="text-sm font-bold text-[#F5F5F5] mb-4">دسته‌بندی‌ها</h3>
          <div className="grid grid-cols-4 gap-3">
            {[
              { icon: <Shield className="w-5 h-5" />, label: "تحریم‌شکن", category: "vpn" },
              { icon: <Music className="w-5 h-5" />, label: "موسیقی", category: "music" },
              { icon: <PlaySquare className="w-5 h-5" />, label: "استریم", category: "video" },
              { icon: <Bot className="w-5 h-5" />, label: "هوش مصنوعی", category: "ai" },
              { icon: <MessageCircle className="w-5 h-5" />, label: "اجتماعی", category: "social" },
              { icon: <Code className="w-5 h-5" />, label: "برنامه‌نویسی", category: "tools" },
              { icon: <Layout className="w-5 h-5" />, label: "آموزش", category: "edu" },
              { icon: <MoreHorizontal className="w-5 h-5" />, label: "بیشتر", category: "all" },
            ].map((cat) => (
              <button
                key={cat.label}
                onClick={() => router.push(`/products?category=${cat.category}`)}
                className="flex flex-col items-center gap-2 group active:scale-95 transition-transform"
              >
                <div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center text-[#F5F5F5]/70 group-hover:text-[#F5F5F5] transition-all group-hover:scale-105"
                  style={{
                    background: "linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    backdropFilter: "blur(12px)",
                  }}
                >
                  {cat.icon}
                </div>
                <span className="text-[10px] text-[#F5F5F5]/55 font-medium group-hover:text-[#F5F5F5]/80 transition-colors text-center leading-tight">
                  {cat.label}
                </span>
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
