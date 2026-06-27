"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, ChevronLeft, Copy, Headphones } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import ProductIcon from "@/components/ProductIcon";
import { getOrders, type UserOrder } from "@/lib/api";
import { toPersianDigits } from "@/lib/utils";

type OrderStatusFilter = "all" | "active" | "expired";

export default function OrdersPage() {
  const [activeTab, setActiveTab] = useState<OrderStatusFilter>("all");
  const [orders, setOrders] = useState<UserOrder[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<UserOrder | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  useEffect(() => {
    getOrders().then(setOrders).catch((error) => console.error("Orders load failed:", error));
  }, []);

  const filteredOrders = useMemo(
    () => orders.filter((order) => (activeTab === "all" ? true : order.status === activeTab)),
    [orders, activeTab]
  );

  const handleCopy = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (error) {
      console.error("Clipboard copy failed:", error);
    }
  };

  return (
    <div className="min-h-screen text-[#F5F5F5] font-sans pb-32">
      <header className="p-5 pt-6 flex justify-between items-center relative">
        <div className="w-6" />
        <h1 className="text-base font-bold text-[#F5F5F5] absolute left-1/2 -translate-x-1/2">سفارش‌ها</h1>
        <div className="w-6" />
      </header>

      <main className="px-5 mt-2">
        <div
          className="p-1 rounded-xl flex items-center justify-between mb-6"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
        >
          {(["all", "active", "expired"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="flex-1 py-2 text-xs font-medium rounded-lg transition-all"
              style={
                activeTab === tab
                  ? { background: "rgba(230,57,70,0.15)", color: "#E63946" }
                  : { color: "rgba(245,245,245,0.45)" }
              }
            >
              {tab === "all" ? "همه" : tab === "active" ? "فعال" : "منقضی"}
            </button>
          ))}
        </div>

        <div className="space-y-3">
          {filteredOrders.length === 0 ? (
            <div className="text-center py-10 text-sm text-[#F5F5F5]/50">سفارشی ثبت نشده است.</div>
          ) : (
            filteredOrders.map((order) => (
              <div
                key={order.id}
                onClick={() => setSelectedOrder(order)}
                className="rounded-2xl p-4 flex items-center justify-between cursor-pointer transition-all active:scale-[0.98]"
                style={{
                  background: "linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)",
                  border: "1px solid rgba(255,255,255,0.09)",
                }}
              >
                <div className="flex items-center gap-4">
                  <ProductIcon icon={order.icon} assetUrl={order.assetUrl} gradient={order.gradient} />
                  <div className="flex flex-col gap-1">
                    <h3 className="text-sm font-bold text-[#F5F5F5]">{order.brand}</h3>
                    <p className="text-[10px] text-[#F5F5F5]/70">{order.duration}</p>
                    <p className="text-[10px] text-[#F5F5F5]/50 mt-1">{new Date(order.createdAt).toLocaleDateString("fa-IR")}</p>
                  </div>
                </div>

                <div className={`text-[10px] font-bold px-3 py-1 rounded-full border ${order.status === "active" ? "text-emerald-400 border-emerald-400/40 bg-emerald-400/10" : "text-[#E63946] border-[#E63946]/20 bg-[#E63946]/5"}`}>
                  {order.status === "active" ? "فعال" : "منقضی"}
                </div>
              </div>
            ))
          )}
        </div>
      </main>

      <Dialog open={!!selectedOrder} onOpenChange={(open) => !open && setSelectedOrder(null)}>
        <DialogContent className="text-[#F5F5F5] w-full h-[100dvh] max-w-md mx-auto p-0 font-sans dir-rtl rounded-none flex flex-col border-none" style={{ background: "#0A0A0B" }}>
          <DialogTitle className="sr-only">Order Details</DialogTitle>

          <DialogHeader
            className="flex flex-row justify-between items-center px-5 py-4 sticky top-0 z-20"
            style={{ background: "rgba(10,10,11,0.9)", backdropFilter: "blur(20px)", borderBottom: "1px solid rgba(255,255,255,0.07)" }}
          >
            <button onClick={() => setSelectedOrder(null)} className="p-2 rounded-full hover:bg-white/10 transition-colors" style={{ background: "rgba(255,255,255,0.07)" }}>
              <ChevronLeft className="w-4 h-4" />
            </button>
            <h2 className="text-base font-bold">جزئیات سفارش</h2>
            <button className="p-2 rounded-full hover:bg-white/10 transition-colors" style={{ background: "rgba(255,255,255,0.07)" }}>
              <Headphones className="w-4 h-4 text-[#F5F5F5]/60" />
            </button>
          </DialogHeader>

          {selectedOrder && (
            <div className="p-5 space-y-5 flex-1 overflow-y-auto">
              <div className="rounded-2xl p-4 flex items-center justify-between" style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)" }}>
                <div className="flex items-center gap-3">
                  <ProductIcon icon={selectedOrder.icon} assetUrl={selectedOrder.assetUrl} gradient={selectedOrder.gradient} sizeClassName="w-10 h-10" iconSizeClassName="w-4 h-4" />
                  <div>
                    <h3 className="text-sm font-bold text-[#F5F5F5]">{selectedOrder.brand}</h3>
                    <p className="text-[10px] text-[#F5F5F5]/55 mt-0.5">{selectedOrder.duration}</p>
                  </div>
                </div>
                <div className={`text-[10px] font-bold px-3 py-1 rounded-full border ${selectedOrder.status === "active" ? "text-emerald-400 border-emerald-400/40 bg-emerald-400/10" : "text-[#E63946] border-[#E63946]/20 bg-[#E63946]/5"}`}>
                  {selectedOrder.status === "active" ? "فعال" : "منقضی"}
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
                  <span className="text-sm text-[#F5F5F5]/80 font-mono whitespace-pre-wrap break-all leading-relaxed flex-1">{selectedOrder.credentials}</span>
                  <button onClick={() => handleCopy(selectedOrder.credentials, "credentials")} className="text-[#F5F5F5]/40 hover:text-[#F5F5F5] transition-colors flex-shrink-0 mt-0.5">
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