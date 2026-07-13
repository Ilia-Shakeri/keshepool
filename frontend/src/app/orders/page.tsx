"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ChevronRight, Copy, Headphones } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import ProductIcon from "@/components/ProductIcon";
import PageHeader from "@/components/PageHeader";
import { getOrders, getPublicConfig, type UserOrder } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { filterOrdersByStatus, getOrderStatusLabel, type OrderStatus, type OrderStatusFilter } from "@/lib/order-status";
import { useTelegramBackButton } from "@/hooks/useTelegramBackButton";
import { toPersianDigits } from "@/lib/utils";

const STATUS_TABS: Array<{ value: OrderStatusFilter; label: string }> = [
  { value: "all", label: "همه" },
  { value: "active", label: "فعال" },
  { value: "expired", label: "منقضی" },
  { value: "cancelled", label: "لغوشده" },
  { value: "refunded", label: "بازپرداخت" },
];

function statusClass(status: OrderStatus): string {
  if (status === "active") return "border-emerald-400/40 bg-emerald-400/10 text-emerald-400";
  if (status === "refunded") return "border-blue-400/30 bg-blue-400/10 text-blue-300";
  if (status === "cancelled") return "border-amber-400/30 bg-amber-400/10 text-amber-300";
  return "border-[#E63946]/20 bg-[#E63946]/5 text-[#E63946]";
}

export default function OrdersPage() {
  const [activeTab, setActiveTab] = useState<OrderStatusFilter>("all");
  const [orders, setOrders] = useState<UserOrder[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<UserOrder | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [supportLink, setSupportLink] = useState<string | null>(null);

  const loadOrders = useCallback(async () => {
    setIsLoading(true);
    setOrderError(null);
    try {
      setOrders(await getOrders());
    } catch (error) {
      setOrderError(error instanceof Error ? error.message : "سفارش‌ها دریافت نشدند.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadOrders);
    void getPublicConfig()
      .then((config) => setSupportLink(config.supportUrl || (config.supportUsername ? `https://t.me/${config.supportUsername.replace(/^@/, "")}` : null)))
      .catch((error) => console.error("Support config load failed:", error));
  }, [loadOrders]);

  useTelegramBackButton(() => setSelectedOrder(null), Boolean(selectedOrder));

  const filteredOrders = useMemo(
    () => filterOrdersByStatus(orders, activeTab),
    [orders, activeTab]
  );

  const handleCopy = async (text: string, field: string) => {
    try {
      if (await copyText(text)) {
        setCopiedField(field);
        setTimeout(() => setCopiedField(null), 2000);
      } else {
        window.Telegram?.WebApp?.showAlert(`متن را دستی کپی کنید:\n${text}`);
      }
    } catch {
      window.Telegram?.WebApp?.showAlert(`متن را دستی کپی کنید:\n${text}`);
    }
  };

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
      <PageHeader title="سفارش‌ها" />

      <main className="mx-auto mt-2 max-w-3xl px-5">
        <div
          className="p-1 rounded-xl flex items-center justify-between mb-6"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div className="flex w-full gap-1 overflow-x-auto scrollbar-hide">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className="min-w-fit flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-xs font-medium transition-all"
              style={
                activeTab === tab.value
                  ? { background: "rgba(230,57,70,0.15)", color: "#E63946" }
                  : { color: "rgba(245,245,245,0.45)" }
              }
            >
              {tab.label}
            </button>
          ))}
          </div>
        </div>

        <div className="space-y-3">
          {isLoading ? (
            <div className="py-10 text-center text-sm text-[#F5F5F5]/50">در حال دریافت سفارش‌ها...</div>
          ) : orderError ? (
            <div className="rounded-2xl border border-[#E63946]/20 bg-[#E63946]/[0.06] p-5 text-center text-sm text-[#E63946]">
              <p>{orderError}</p>
              <button type="button" onClick={() => void loadOrders()} className="mt-3 rounded-xl px-4 text-xs font-bold">تلاش دوباره</button>
            </div>
          ) : filteredOrders.length === 0 ? (
            <div className="text-center py-10 text-sm text-[#F5F5F5]/50">سفارشی ثبت نشده است.</div>
          ) : (
            filteredOrders.map((order) => (
              <div
                key={order.id}
                onClick={() => setSelectedOrder(order)}
                className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl p-4 transition-all active:scale-[0.98]"
                style={{
                  background: "linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)",
                  border: "1px solid rgba(255,255,255,0.09)",
                }}
              >
                <div className="flex min-w-0 items-center gap-4">
                  <ProductIcon icon={order.icon} assetUrl={order.assetUrl} gradient={order.gradient} />
                  <div className="flex min-w-0 flex-col gap-1">
                    <h3 className="truncate text-sm font-bold text-[#F5F5F5]">{order.brand}</h3>
                    <p className="text-[10px] text-[#F5F5F5]/70">{order.duration}</p>
                    <p className="text-[10px] text-[#F5F5F5]/50 mt-1">{new Date(order.createdAt).toLocaleDateString("fa-IR")}</p>
                  </div>
                </div>

                <div className={`shrink-0 rounded-full border px-3 py-1 text-[10px] font-bold ${statusClass(order.status)}`}>
                  {getOrderStatusLabel(order.status)}
                </div>
              </div>
            ))
          )}
        </div>
      </main>

      <Dialog open={!!selectedOrder} onOpenChange={(open) => !open && setSelectedOrder(null)}>
        <DialogContent className="dialog-safe-area flex h-[100dvh] w-full max-w-md flex-col rounded-none border-none p-0 font-sans text-[#F5F5F5] sm:h-auto sm:max-h-[90dvh] sm:rounded-3xl" style={{ background: "#0A0A0B" }}>
          <DialogTitle className="sr-only">جزئیات سفارش</DialogTitle>
          <DialogDescription className="sr-only">وضعیت، تاریخ و اطلاعات دسترسی سفارش</DialogDescription>

          <DialogHeader
            className="flex flex-row justify-between items-center px-5 py-4 sticky top-0 z-20"
            style={{ background: "rgba(10,10,11,0.9)", backdropFilter: "blur(20px)", borderBottom: "1px solid rgba(255,255,255,0.07)" }}
          >
            <button type="button" onClick={() => setSelectedOrder(null)} className="p-2 rounded-full hover:bg-white/10 transition-colors" style={{ background: "rgba(255,255,255,0.07)" }} aria-label="بستن جزئیات سفارش">
              <ChevronRight className="w-4 h-4" />
            </button>
            <h2 className="text-base font-bold">جزئیات سفارش</h2>
            <button type="button" onClick={openSupport} className="p-2 rounded-full hover:bg-white/10 transition-colors" style={{ background: "rgba(255,255,255,0.07)" }} aria-label="ارتباط با پشتیبانی">
              <Headphones className="w-4 h-4 text-[#F5F5F5]/60" />
            </button>
          </DialogHeader>

          {selectedOrder && (
            <div className="p-5 space-y-5 flex-1 overflow-y-auto">
              <div className="flex items-center justify-between gap-3 rounded-2xl p-4" style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)" }}>
                <div className="flex min-w-0 items-center gap-3">
                  <ProductIcon icon={selectedOrder.icon} assetUrl={selectedOrder.assetUrl} gradient={selectedOrder.gradient} sizeClassName="w-10 h-10" iconSizeClassName="w-4 h-4" />
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-bold text-[#F5F5F5]">{selectedOrder.brand}</h3>
                    <p className="text-[10px] text-[#F5F5F5]/55 mt-0.5">{selectedOrder.duration}</p>
                  </div>
                </div>
                <div className={`shrink-0 rounded-full border px-3 py-1 text-[10px] font-bold ${statusClass(selectedOrder.status)}`}>
                  {getOrderStatusLabel(selectedOrder.status)}
                </div>
              </div>

              <div className="space-y-3 px-1">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#F5F5F5]/45">تاریخ خرید</span>
                  <span className="text-[#F5F5F5]/80 font-medium">{new Date(selectedOrder.createdAt).toLocaleString("fa-IR")}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#F5F5F5]/45">شماره سفارش</span>
                  <span className="text-[#F5F5F5]/80 font-mono">{toPersianDigits(selectedOrder.id)}</span>
                </div>
              </div>

              <div className="pt-4" style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
                <h4 className="text-sm font-bold text-[#F5F5F5] mb-3">اطلاعات سرویس</h4>
                <div className="rounded-2xl p-4 flex items-start justify-between gap-3" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
                  <span className="flex-1 select-text whitespace-pre-wrap break-all font-mono text-sm leading-relaxed text-[#F5F5F5]/80">{selectedOrder.credentials}</span>
                  <button type="button" onClick={() => handleCopy(selectedOrder.credentials, "credentials")} className="mt-0.5 flex-shrink-0 text-[#F5F5F5]/40 transition-colors hover:text-[#F5F5F5]" aria-label="کپی اطلاعات سرویس">
                    {copiedField === "credentials" ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
