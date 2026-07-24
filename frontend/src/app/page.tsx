"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, Bot, Code, Flame, Layout, MessageCircle, MoreHorizontal, Music, PlaySquare, Shield, X } from "lucide-react";
import ProductIcon from "@/features/products/components/ProductIcon";
import UserAvatar from "@/components/UserAvatar";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { getNotifications, getProducts, markNotificationsRead, type UserNotification } from "@/lib/api";
import type { Product } from "@/features/products/types";
import { toPersianDigits } from "@/lib/utils";

export default function Home() {
  const router = useRouter();
  const [tgUser, setTgUser] = useState<{ id?: number; first_name?: string; last_name?: string; username?: string } | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [notifications, setNotifications] = useState<UserNotification[]>([]);
  const [productError, setProductError] = useState<string | null>(null);
  const [notificationError, setNotificationError] = useState<string | null>(null);
  const [notificationLoading, setNotificationLoading] = useState(true);
  const [isMarkingRead, setIsMarkingRead] = useState(false);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const loadHomeData = useCallback(() => {
    setIsLoading(true);
    setNotificationLoading(true);
    setProductError(null);
    setNotificationError(null);
    const webApp = window.Telegram?.WebApp;
    if (webApp) setTgUser(webApp.initDataUnsafe?.user || null);

    return Promise.allSettled([getProducts(), getNotifications()])
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
          setNotificationError("دریافت اعلان‌ها ناموفق بود.");
          console.error("Notification data load failed:", notifData.reason);
        }
      })
      .finally(() => {
        setIsLoading(false);
        setNotificationLoading(false);
      });
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadHomeData);
  }, [loadHomeData]);

  const hotItems = useMemo(() => products.slice(0, 6), [products]);
  const unreadCount = notifications.filter((n) => !n.isRead).length;

  const markAllRead = useCallback(async () => {
    if (unreadCount === 0 || isMarkingRead) return;
    setIsMarkingRead(true);
    setNotificationError(null);
    try {
      await markNotificationsRead();
      setNotifications(await getNotifications());
    } catch (error) {
      setNotificationError(
        error instanceof Error ? error.message : "به‌روزرسانی اعلان‌ها ناموفق بود.",
      );
    } finally {
      setIsMarkingRead(false);
    }
  }, [isMarkingRead, unreadCount]);

  function getStartingPrice(product: Product): string {
    const startingVariant = product.variants.reduce<Product["variants"][number] | null>((lowest, variant) => {
      if (!lowest) return variant;
      return variant.rawPrice < lowest.rawPrice ? variant : lowest;
    }, null);

    return startingVariant?.priceLabel || "0";
  }

  return (
    <div className="min-h-[100dvh] pb-28 font-sans">
      {/* Background gradient orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0" aria-hidden="true">
        <div className="absolute -top-24 -right-24 w-72 h-72 bg-[#E63946]/[0.06] rounded-full blur-3xl" />
        <div className="absolute top-1/2 -left-32 w-80 h-80 bg-blue-600/[0.04] rounded-full blur-3xl" />
      </div>

      <header className="relative z-10 flex items-center justify-between gap-3 px-5 py-4">
        {/* Left: user profile */}
        <button
          onClick={() => router.push("/profile")}
          className="flex min-w-0 flex-1 items-center gap-3 transition-transform active:scale-95"
        >
          <UserAvatar
            firstName={tgUser?.first_name}
            username={tgUser?.username}
            telegramId={tgUser?.id}
            className="size-10 text-base"
          />
          <div className="flex min-w-0 flex-col items-start">
            <h1 className="max-w-full truncate text-sm font-bold leading-tight text-[#F5F5F5]">
              سلام، {tgUser?.first_name || "کاربر عزیز"} 👋
            </h1>
            <p className="mt-0.5 max-w-full truncate text-[10px] text-[#F5F5F5]/50">بهترین سرویس‌ها با بهترین قیمت</p>
          </div>
        </button>

        {/* Right: notification bell */}
        <div className="relative shrink-0">
          <button
            onClick={() => setIsNotifOpen(true)}
            className="relative grid size-10 place-items-center rounded-full border border-white/10 p-0 leading-none transition-all active:scale-95"
            style={{ background: "rgba(255,255,255,0.06)", backdropFilter: "blur(12px)" }}
            aria-label="اعلانات"
          >
            <Bell className="block size-[18px] text-[#F5F5F5]" aria-hidden="true" />
            {unreadCount > 0 && (
              <span className="absolute end-1 top-1 size-2 rounded-full border border-[#0F0F10] bg-[#E63946] shadow-sm" />
            )}
          </button>
        </div>
      </header>

      <Dialog open={isNotifOpen} onOpenChange={setIsNotifOpen}>
        <DialogContent
          dir="rtl"
          className="max-h-[min(82dvh,40rem)] overflow-hidden rounded-3xl border border-white/15 bg-[#111318] p-0 text-[#F5F5F5] shadow-[0_28px_90px_rgba(0,0,0,0.82)] sm:max-w-md"
        >
          <div className="flex items-start justify-between gap-4 border-b border-white/10 px-5 py-4">
            <div>
              <DialogTitle className="text-base font-black">اعلان‌ها</DialogTitle>
              <DialogDescription className="mt-1 text-xs text-[#F5F5F5]/55">
                {unreadCount > 0
                  ? `${toPersianDigits(String(unreadCount))} اعلان خوانده‌نشده`
                  : "همه اعلان‌ها خوانده شده‌اند."}
              </DialogDescription>
            </div>
            <DialogClose
              className="grid size-9 shrink-0 place-items-center rounded-full border border-white/10 bg-white/5"
              aria-label="بستن اعلان‌ها"
            >
              <X className="size-4" aria-hidden="true" />
            </DialogClose>
          </div>

          <div className="max-h-[55dvh] overflow-y-auto px-2 py-2">
            {notificationLoading ? (
              <p className="p-8 text-center text-xs text-[#F5F5F5]/55" role="status">
                در حال دریافت اعلان‌ها…
              </p>
            ) : notificationError ? (
              <div className="m-3 rounded-2xl border border-[#E63946]/30 bg-[#E63946]/10 p-4 text-center">
                <p className="text-xs text-[#F5F5F5]/80" role="alert">{notificationError}</p>
                <button
                  type="button"
                  onClick={() => void loadHomeData()}
                  className="mt-3 rounded-xl bg-white/10 px-4 py-2 text-xs font-bold"
                >
                  تلاش دوباره
                </button>
              </div>
            ) : notifications.length === 0 ? (
              <div className="p-8 text-center">
                <Bell className="mx-auto size-8 text-[#F5F5F5]/25" aria-hidden="true" />
                <p className="mt-3 text-xs text-[#F5F5F5]/50">هنوز اعلانی ندارید.</p>
              </div>
            ) : (
              notifications.map((notification) => (
                <article
                  key={notification.id}
                  className={`m-1 rounded-2xl border p-4 ${
                    notification.isRead
                      ? "border-white/5 bg-white/[0.025]"
                      : "border-[#E63946]/25 bg-[#E63946]/[0.07]"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!notification.isRead && (
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[#E63946]" />
                    )}
                    <div className="min-w-0">
                      <h3 className="text-sm font-bold">{notification.title}</h3>
                      <p className="mt-1 text-xs leading-6 text-[#F5F5F5]/65">
                        {notification.description}
                      </p>
                      <time className="mt-2 block text-[10px] text-[#F5F5F5]/35">
                        {new Intl.DateTimeFormat("fa-IR", {
                          dateStyle: "medium",
                          timeStyle: "short",
                        }).format(new Date(notification.createdAt))}
                      </time>
                    </div>
                  </div>
                </article>
              ))
            )}
          </div>

          <div className="border-t border-white/10 p-4">
            <button
              type="button"
              onClick={() => void markAllRead()}
              disabled={unreadCount === 0 || isMarkingRead}
              className="w-full rounded-2xl bg-[#E63946] px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-45"
            >
              {isMarkingRead ? "در حال ثبت…" : "خواندن همه اعلان‌ها"}
            </button>
          </div>
        </DialogContent>
      </Dialog>

      <main className="relative z-10 mx-auto mt-2 max-w-4xl space-y-8 px-5">
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
              <div className="min-w-full rounded-2xl border border-white/[0.08] bg-white/[0.04] p-5 text-center text-xs text-[#E63946]">
                <p>{productError}</p>
                <button
                  type="button"
                  onClick={() => void loadHomeData()}
                  className="mt-3 rounded-xl bg-[#E63946]/15 px-4 py-2 font-bold text-[#E63946]"
                >
                  تلاش دوباره
                </button>
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
                        style={item.variants.some((variant) => (variant.stockCount ?? 0) > 0)
                          ? { background: "rgba(16,185,129,0.12)", color: "#10b981", border: "1px solid rgba(16,185,129,0.2)" }
                          : { background: "rgba(230,57,70,0.12)", color: "#E63946", border: "1px solid rgba(230,57,70,0.2)" }}
                      >
                        {item.variants.some((variant) => (variant.stockCount ?? 0) > 0) ? "موجود" : "ناموجود"}
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
          <div className="grid grid-cols-4 gap-3 sm:grid-cols-8">
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
